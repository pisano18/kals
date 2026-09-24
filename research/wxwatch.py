#!/usr/bin/env python3
"""wxwatch.py -- READ-ONLY shadow watcher for the hourly temperature "pin"
(IDEAS_2026-09-24 section 1, idea #1). Places NO orders. GET only.

    python research/wxwatch.py --selftest      # planted worlds, no network
    python research/wxwatch.py                  # watch, log to results/
    python research/wxwatch.py --report         # running tally against the bar

PRE-REGISTERED BAR -- written 2026-09-24 ~08:00Z BEFORE any shadow data was
read (the only prior data is the 7-day tape study in IDEAS_2026-09-24.md).
Over 3-5 days of shadow, ALL of:

  1. Index freshness: the age of the newest published index point (fetch
     time minus the point's own timestamp) has p90 < 7 minutes (420 s),
     per city.
  2. Supply: at least 50 OFFERED (not traded) index-side contracts per day
     per city at <= 97c while the index is >= 1 F clear of the strike.
     Counted per (market, close) as the most contracts seen in one book
     snapshot, summed over the city-day, so a resting order is never
     counted twice.
  3. Safety: ZERO closes where the index, at the close minute, ended on the
     other side of the strike from where it was (by >= 1 F) at the would-be
     entry.

Fail any one and the idea stops. This file never learns the bar from the
data; --report prints the tally next to the numbers above.

WHAT IT WATCHES

Kalshi's own public minute temperature index, which the hourly directional
markets settle on (rules: "Synoptic Data ... Kalshi Weather Index
Methodology"; the verifier found settlement == the index value at the close
minute on 165/165 Miami and 164/165 NYC closes). The index is public and
needs no key:

    GET https://api.elections.kalshi.com/trade-api/v2/live_data/weather/{city}

The four live hourly series this week and their index city codes (probed
2026-09-24 -- KXTEMPNYCH / KXTEMPLAXH / KXTEMPCHIH return zero markets, the
"S" variants are the live ones):

    miami      KXTEMPMIAH
    nyc        KXTEMPNYCHS
    la-coastal KXTEMPLAXHS   ("Coastal Los Angeles")
    chicago    KXTEMPCHIHS   ("Chicago Metro Area")

Every market is strike_type "greater" on floor_strike (e.g. T78.99 -> YES
if the index at the close minute is above 78.99 F). The "index side" is YES
when the newest index value is above the strike, NO when below.

THE PAPER RULE (what "would buy" means)

At every book poll inside the last WINDOW_S (360 s) before close, using the
newest index point we actually hold at that moment:
    margin  = |index - strike|            must be >= MARGIN_F (1.0 F)
    age     = now - index point time      must be <= MAX_AGE_S (420 s)
    lead    = close - index point time    must be <= MAX_LEAD_S (420 s)
    best index-side ask                   must be in [MIN_PX, MAX_PX] = [50c, 97c]
Then "would buy N @ p": every resting contract at <= 97c on the index side,
capped at CAP (50) per market, p = the volume-weighted price through that
ladder, taker fee included. One paper trade per market per close, at the
first poll that qualifies. Everything else is logged as a refusal with its
reason, so the population that DID NOT qualify is visible too.

`lead` is the honest clock: the index publishes about 5.5 minutes late, so
at 6 minutes before close the newest point is ~11.5 minutes before close.
The 7-day study measured the index's move over 6-7 minutes ("<1 F"); over
10 minutes a 1 F margin took one loss. So the rule waits until the known
point is within 7 minutes of the close, which in practice is the last ~90 s.
Every book line carries `lead_s` so --report can also show what a looser
rule would have faced.

WHAT IT LOGS -- results/wxwatch-<startUTC>.jsonl, one JSON object per line,
field `k` says which kind:

  index      every 60 s per city: newest point (t, v), its age, status,
             contributors, points returned.
  market     first sight of a market: ticker, city, close, strike.
  book       every 30 s per open market in the last 8 min: tau, strike,
             index value/time, age, lead, margin, side, best ask + size,
             ladder to 97c, depth at <=97c, and the decision string.
  would_buy  the paper trade: n, px, cost, fee, and the index state.
  settle     when result and the close-minute index point are both known:
             result, expiration_value, index at the close minute, whether
             they match (the 165/165 claim), and for the paper trade its
             win/loss, money, and whether the index crossed the strike
             after entry.
  err        a failed fetch (status, what).

All timestamps in the file are UTC epoch seconds (`t`) or ISO-Z strings.
Memory: the index history is trimmed to 12 h per city; books are not kept.

NOTHING HERE PLACES AN ORDER. The only Kalshi client is research/kauth.py,
which can only GET, plus one unauthenticated public GET for the index.
"""

import argparse
import datetime as dt
import glob
import json
import math
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")

CITIES = {"miami": "KXTEMPMIAH", "nyc": "KXTEMPNYCHS",
          "la-coastal": "KXTEMPLAXHS", "chicago": "KXTEMPCHIHS"}
WX_URL = "https://api.elections.kalshi.com/trade-api/v2/live_data/weather/%s?last_sec=%d"

# The rule (see docstring). Flags may override for a paper arm; the bar does
# not move with them.
MARGIN_F = 1.0
MAX_AGE_S = 420
MAX_LEAD_S = 420
WINDOW_S = 360
MIN_PX, MAX_PX = 0.50, 0.97
CAP = 50

# Cadence.
INDEX_EVERY = 60
BOOK_EVERY = 30
BOOK_WINDOW = 480
DISCOVER_EVERY = 300
SETTLE_EVERY = 300
SETTLE_GIVEUP = 8 * 3600
INDEX_KEEP = 12 * 3600
MIN_GAP = 0.15          # seconds between any two Kalshi requests (<7/s)

FEE_RATE = 0.07


def fee_cents(n, p):
    """Kalshi taker fee for n contracts at price p, rounded UP to the cent
    per order, in cents."""
    return math.ceil(FEE_RATE * n * p * (1 - p) * 100 - 1e-9)


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


# ---------------------------------------------------------------- network
_kauth = None
_last_req = [0.0]


def _throttle():
    gap = time.time() - _last_req[0]
    if gap < MIN_GAP:
        time.sleep(MIN_GAP - gap)
    _last_req[0] = time.time()


def kalshi_get(path, params=None):
    """Signed GET via research/kauth.py (GET-only by construction)."""
    global _kauth
    if _kauth is None:
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        import kauth
        _kauth = kauth
    _throttle()
    return _kauth.get(path, params)


def fetch_index(city, last_sec=1800):
    """Public, unauthenticated. Returns (status, body-or-error-string)."""
    _throttle()
    req = urllib.request.Request(WX_URL % (city, last_sec), method="GET",
                                 headers={"User-Agent": "kals-wxwatch/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode())
    except Exception as e:  # noqa: BLE001 -- logged, never fatal
        return -1, str(e)[:200]


def ladder_for(ob, side, max_px=MAX_PX):
    """Asks for buying `side`, cheapest first, as [[px, size], ...] with
    px <= max_px. Kalshi's REST book lists BIDS in dollars:
    {"orderbook_fp": {"yes_dollars": [["0.07","2"]], "no_dollars": [...]}}
    A YES ask is 1 - a NO bid (pinracearm.book_ask, checked 2026-09-22)."""
    if not isinstance(ob, dict):
        return None
    book = ob.get("orderbook_fp")
    if not isinstance(book, dict):
        return None
    other = book.get("no_dollars" if side == "yes" else "yes_dollars") or []
    out = []
    for lvl in other:
        try:
            px, sz = float(lvl[0]), float(lvl[1])
        except (TypeError, ValueError, IndexError):
            continue
        if sz > 0 and 0.0 < px < 1.0:
            ask = round(1.0 - px, 4)
            if ask <= max_px + 1e-9:
                out.append([ask, sz])
    out.sort()
    return out


def take(ladder, cap):
    """(n, vwap) of buying up to `cap` contracts through `ladder`."""
    n = 0.0
    cost = 0.0
    for px, sz in ladder:
        want = min(sz, cap - n)
        if want <= 0:
            break
        n += want
        cost += want * px
    return (n, round(cost / n, 4)) if n > 0 else (0, None)


# ------------------------------------------------------------------ watch
class Watch:
    """The whole watcher with every external edge injectable, so the
    self-test drives it with a fake clock, index, book and settlement."""

    def __init__(self, log, clock=time.time, get_index=fetch_index,
                 kget=kalshi_get, cities=None, margin=MARGIN_F,
                 max_age=MAX_AGE_S, max_lead=MAX_LEAD_S, window=WINDOW_S,
                 cap=CAP, out=None):
        self.log, self.clock, self.get_index, self.kget = log, clock, get_index, kget
        self.cities = dict(cities or CITIES)
        self.margin, self.max_age, self.max_lead = margin, max_age, max_lead
        self.window, self.cap = window, cap
        self.out = out or (lambda s: None)
        self.idx = {c: {} for c in self.cities}       # city -> {t_sec: v}
        self.newest = {c: None for c in self.cities}  # city -> (t, v, status, contrib, fetched)
        self.markets = {}                             # ticker -> dict
        self.closes = {}                              # (city, close) -> event_ticker
        self.next_index = {c: 0.0 for c in self.cities}
        self.next_discover = 0.0
        self.next_settle = {}                         # (city, close) -> t
        self.settle_started = {}
        self.polls = 0

    # -- index ------------------------------------------------------
    def poll_index(self, city, now):
        st, body = self.get_index(city)
        if st != 200 or not isinstance(body, dict):
            self.log({"k": "err", "t": now, "what": "index", "city": city,
                      "http": st, "body": str(body)[:200]})
            return
        ts = body.get("timeseries") or []
        pts = []
        for p in ts:
            try:
                t = float(p["t"])
                t = t / 1000.0 if t > 1e11 else t
                pts.append((int(t), float(p["v"]), p.get("status"), p.get("contributors")))
            except (KeyError, TypeError, ValueError):
                continue
        if not pts:
            self.log({"k": "err", "t": now, "what": "index-empty", "city": city, "http": st})
            return
        pts.sort()
        d = self.idx[city]
        for t, v, _s, _c in pts:
            d[t] = v
        for t in [t for t in d if t < now - INDEX_KEEP]:
            del d[t]
        t, v, s, c = pts[-1]
        self.newest[city] = (t, v, s, c, now)
        self.log({"k": "index", "t": now, "city": city, "idx_t": t, "idx_iso": iso(t),
                  "v": v, "age_s": round(now - t, 1), "status": s,
                  "contributors": c, "n": len(pts)})

    # -- markets ----------------------------------------------------
    def discover(self, now):
        for city, series in self.cities.items():
            st, body = self.kget("/markets", {"series_ticker": series, "limit": 100,
                                              "min_close_ts": int(now) - 3600})
            if st != 200 or not isinstance(body, dict):
                self.log({"k": "err", "t": now, "what": "discover", "city": city, "http": st,
                          "body": str(body)[:200]})
                continue
            for m in body.get("markets") or []:
                tkr = m.get("ticker")
                if not tkr or m.get("strike_type") != "greater" or m.get("floor_strike") is None:
                    continue
                try:
                    close = parse_iso(m["close_time"])
                    opn = parse_iso(m.get("open_time") or m["close_time"])
                except (KeyError, ValueError):
                    continue
                rec = self.markets.get(tkr)
                if rec is None:
                    rec = {"ticker": tkr, "city": city, "series": series, "close": close,
                           "open": opn, "strike": float(m["floor_strike"]),
                           "event": m.get("event_ticker"), "status": m.get("status"),
                           "next_book": 0.0, "paper": None, "settled": False,
                           "max_depth97": 0.0, "max_depth97_lead_ok": 0.0, "polls": 0}
                    self.markets[tkr] = rec
                    self.closes[(city, close)] = m.get("event_ticker")
                    self.log({"k": "market", "t": now, "city": city, "ticker": tkr,
                              "close": close, "close_iso": iso(close), "strike": rec["strike"],
                              "status": rec["status"], "event": rec["event"]})
                else:
                    rec["status"] = m.get("status")
        # forget finished markets so memory stays flat
        for tkr in [t for t, r in self.markets.items()
                    if r["settled"] or now > r["close"] + SETTLE_GIVEUP + 3600]:
            r = self.markets.pop(tkr)
            self.closes.pop((r["city"], r["close"]), None)
            self.next_settle.pop((r["city"], r["close"]), None)
            self.settle_started.pop((r["city"], r["close"]), None)

    # -- the decision -----------------------------------------------
    def decide(self, rec, now, ladder, best):
        """Returns (decision string, side, margin, lead, age, idx_t, idx_v).
        `ladder` is the index-side asks to 97c (None = book unreadable)."""
        nw = self.newest.get(rec["city"])
        if nw is None:
            return "refuse: no index yet", None, None, None, None, None, None
        idx_t, idx_v = nw[0], nw[1]
        age = now - idx_t
        lead = rec["close"] - idx_t
        tau = rec["close"] - now
        side = "yes" if idx_v > rec["strike"] else "no"
        margin = abs(idx_v - rec["strike"])
        why = None
        if rec["paper"] is not None:
            why = "already bought this market"
        elif tau > self.window:
            why = "tau %.0fs > %ds window" % (tau, self.window)
        elif margin < self.margin - 1e-9:
            why = "margin %.2fF < %.1fF" % (margin, self.margin)
        elif age > self.max_age:
            why = "index stale: age %.0fs > %ds" % (age, self.max_age)
        elif lead > self.max_lead:
            why = "known index point is %.0fs before close > %ds" % (lead, self.max_lead)
        elif ladder is None:
            why = "book unreadable"
        elif not ladder:
            why = ("no %s offer <= %dc (best %s)"
                   % (side, round(MAX_PX * 100), "none" if best is None else "%.0fc" % (best * 100)))
        elif ladder[0][0] < MIN_PX - 1e-9:
            why = "best %s ask %.0fc under %dc floor -- market disagrees hard" % (
                side, ladder[0][0] * 100, round(MIN_PX * 100))
        if why:
            return "refuse: " + why, side, margin, lead, age, idx_t, idx_v
        n, px = take(ladder, self.cap)
        return "would buy %d @ %.2f" % (n, px), side, margin, lead, age, idx_t, idx_v

    # -- books ------------------------------------------------------
    def poll_book(self, rec, now):
        st, ob = self.kget("/markets/%s/orderbook" % rec["ticker"])
        rec["polls"] += 1
        nw = self.newest.get(rec["city"])
        side = None
        if nw is not None:
            side = "yes" if nw[1] > rec["strike"] else "no"
        ladder = None
        best = None
        if st == 200 and side is not None:
            full = ladder_for(ob, side, max_px=1.0)
            if full is not None:
                best = full[0][0] if full else None
                ladder = [lv for lv in full if lv[0] <= MAX_PX + 1e-9]
        elif st != 200:
            self.log({"k": "err", "t": now, "what": "book", "ticker": rec["ticker"], "http": st,
                      "body": str(ob)[:200]})
        decision, side, margin, lead, age, idx_t, idx_v = self.decide(rec, now, ladder, best)
        depth97 = sum(sz for _p, sz in (ladder or []))
        if margin is not None and margin >= self.margin - 1e-9 and age is not None and age <= self.max_age:
            rec["max_depth97"] = max(rec["max_depth97"], depth97)
            if lead is not None and lead <= self.max_lead:
                rec["max_depth97_lead_ok"] = max(rec["max_depth97_lead_ok"], depth97)
        line = {"k": "book", "t": now, "city": rec["city"], "ticker": rec["ticker"],
                "close": rec["close"], "tau_s": round(rec["close"] - now, 1),
                "strike": rec["strike"], "idx_t": idx_t, "idx_v": idx_v,
                "age_s": None if age is None else round(age, 1),
                "lead_s": None if lead is None else round(lead, 1),
                "margin_f": None if margin is None else round(margin, 2),
                "side": side, "best_ask": best,
                "best_size": (ladder[0][1] if ladder else None) if ladder is not None else None,
                "ladder97": ladder, "depth97": depth97, "http": st, "decision": decision}
        self.log(line)
        if decision.startswith("would buy"):
            n, px = take(ladder, self.cap)
            fee = fee_cents(n, px)
            rec["paper"] = {"t": now, "side": side, "n": n, "px": px,
                            "cost_c": round(n * px * 100), "fee_c": fee,
                            "idx_v": idx_v, "idx_t": idx_t, "margin_f": round(margin, 2),
                            "lead_s": round(lead, 1), "age_s": round(age, 1),
                            "tau_s": round(rec["close"] - now, 1)}
            self.log(dict({"k": "would_buy", "city": rec["city"], "ticker": rec["ticker"],
                           "close": rec["close"], "strike": rec["strike"]}, **rec["paper"]))
            self.out("%s WOULD BUY %s %s %d @ %.2f (margin %.2fF, lead %.0fs, age %.0fs)"
                     % (iso(now), rec["ticker"], side, n, px, margin, lead, age))

    # -- settlement -------------------------------------------------
    def close_index(self, city, close):
        """(t, v, exact) -- the index value at the close minute, or the
        nearest within 60 s flagged exact=False, or (None, None, None)."""
        d = self.idx.get(city, {})
        c = int(close)
        if c in d:
            return c, d[c], True
        for off in (60, -60):
            if c + off in d:
                return c + off, d[c + off], False
        return None, None, None

    def poll_settle(self, city, close, event, now):
        st, body = self.kget("/markets", {"event_ticker": event, "limit": 100})
        if st != 200 or not isinstance(body, dict):
            self.log({"k": "err", "t": now, "what": "settle", "event": event, "http": st,
                      "body": str(body)[:200]})
            return
        ms = {m.get("ticker"): m for m in body.get("markets") or []}
        ct, cv, exact = self.close_index(city, close)
        give_up = now > close + SETTLE_GIVEUP
        for tkr, rec in self.markets.items():
            if rec["settled"] or (rec["city"], rec["close"]) != (city, close):
                continue
            m = ms.get(tkr)
            if m is None:
                continue
            result = m.get("result")
            if result not in ("yes", "no") and not give_up:
                continue
            if cv is None and not give_up:
                continue                       # wait for the close-minute point
            ev = m.get("expiration_value")
            try:
                evf = float(ev)
            except (TypeError, ValueError):
                evf = None
            eq = None if (evf is None or cv is None) else abs(evf - cv) < 0.006
            line = {"k": "settle", "t": now, "city": city, "ticker": tkr, "close": close,
                    "close_iso": iso(close), "strike": rec["strike"], "result": result or None,
                    "expiration_value": evf, "idx_close_t": ct, "idx_close_v": cv,
                    "idx_close_exact": exact, "settle_eq_index": eq,
                    "max_depth97": rec["max_depth97"],
                    "max_depth97_lead_ok": rec["max_depth97_lead_ok"],
                    "book_polls": rec["polls"], "gave_up": give_up and result not in ("yes", "no")}
            p = rec["paper"]
            if p is not None:
                win = None if result not in ("yes", "no") else (p["side"] == result)
                if win is None:
                    pnl = None
                elif win:
                    pnl = round(p["n"] * (1 - p["px"]) * 100 - p["fee_c"])
                else:
                    pnl = -round(p["n"] * p["px"] * 100 + p["fee_c"])
                close_side = None if cv is None else ("yes" if cv > rec["strike"] else "no")
                crossed = None if close_side is None else (close_side != p["side"])
                line["paper"] = dict(p, win=win, pnl_c=pnl, crossed=crossed,
                                     idx_move_f=None if cv is None else round(cv - p["idx_v"], 2))
                self.out("%s SETTLED %s %s paper %s %d @ %.2f -> %s %s"
                         % (iso(now), tkr, result, p["side"], p["n"], p["px"],
                            "WIN" if win else "LOSS" if win is False else "?",
                            "" if pnl is None else "%+d c" % pnl))
            self.log(line)
            rec["settled"] = True

    # -- scheduler --------------------------------------------------
    def step(self, now=None):
        now = self.clock() if now is None else now
        for city in self.cities:
            if now >= self.next_index[city]:
                self.next_index[city] = now + INDEX_EVERY
                self.poll_index(city, now)
        if now >= self.next_discover:
            self.next_discover = now + DISCOVER_EVERY
            self.discover(now)
        for rec in list(self.markets.values()):
            tau = rec["close"] - now
            if 0 < tau <= BOOK_WINDOW and now >= rec["open"] and now >= rec["next_book"]:
                if rec["status"] in ("active", "open", None):
                    rec["next_book"] = now + BOOK_EVERY
                    self.poll_book(rec, now)
        for (city, close), event in list(self.closes.items()):
            if now < close + 120 or not event:
                continue
            if any(r["polls"] == 0 for r in self.markets.values()
                   if (r["city"], r["close"]) == (city, close)) and \
               all(r["polls"] == 0 for r in self.markets.values()
                   if (r["city"], r["close"]) == (city, close)):
                # never saw a book for this close (market was not open in
                # our window): nothing to settle against, drop quietly
                for r in self.markets.values():
                    if (r["city"], r["close"]) == (city, close):
                        r["settled"] = True
                continue
            if now >= self.next_settle.get((city, close), 0.0):
                self.next_settle[(city, close)] = now + SETTLE_EVERY
                self.poll_settle(city, close, event, now)
        self.polls += 1


# ------------------------------------------------------------------ report
def pct(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(math.ceil(q * len(xs)) - 1))]


def report(paths=None):
    paths = paths or sorted(glob.glob(os.path.join(RESULTS, "wxwatch-*.jsonl")))
    rows = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    if not rows:
        print("wxwatch --report: no wxwatch-*.jsonl under results/ yet")
        return
    t0 = min(r["t"] for r in rows)
    t1 = max(r["t"] for r in rows)
    days = (t1 - t0) / 86400
    print("wxwatch report: %s .. %s UTC (%.2f days, %d lines, %d files)"
          % (iso(t0), iso(t1), days, len(rows), len(paths)))
    print()
    print("BAR 1 -- index freshness: p90 age under 7 min (420 s) per city")
    for city in CITIES:
        ages = [r["age_s"] for r in rows if r.get("k") == "index" and r.get("city") == city]
        if not ages:
            print("  %-10s no index reads" % city)
            continue
        over = sum(1 for a in ages if a > 420)
        p50, p90, mx = pct(ages, .5), pct(ages, .9), max(ages)
        print("  %-10s reads %5d  typical age %.1f min  9-in-10 under %.1f min  worst %.1f min"
              "  over 7 min: %d of %d  -> %s"
              % (city, len(ages), p50 / 60, p90 / 60, mx / 60, over, len(ages),
                 "PASS so far" if p90 < 420 else "FAIL"))
    print()
    print("BAR 2 -- supply: >= 50 offered index-side contracts per day per city at <= 97c,"
          " margin >= 1 F (most seen in one snapshot per market, summed)")
    books = [r for r in rows if r.get("k") == "book"]
    per = {}       # (city, day, ticker) -> max depth97 with margin ok & age ok
    per_lead = {}
    for r in books:
        if r.get("margin_f") is None or r["margin_f"] < 1.0 or r.get("age_s") is None or r["age_s"] > 420:
            continue
        key = (r["city"], iso(r["close"])[:10], r["ticker"])
        per[key] = max(per.get(key, 0), r.get("depth97") or 0)
        if r.get("lead_s") is not None and r["lead_s"] <= 420:
            per_lead[key] = max(per_lead.get(key, 0), r.get("depth97") or 0)
    for city in CITIES:
        by_day = {}
        by_day_lead = {}
        for (c, day, _tk), v in per.items():
            if c == city:
                by_day[day] = by_day.get(day, 0) + v
        for (c, day, _tk), v in per_lead.items():
            if c == city:
                by_day_lead[day] = by_day_lead.get(day, 0) + v
        n_polls = sum(1 for r in books if r["city"] == city)
        if not by_day:
            print("  %-10s %d book polls, no qualifying snapshot yet" % (city, n_polls))
            continue
        parts = ", ".join("%s: %.0f (%.0f in last 7 min)" % (d, v, by_day_lead.get(d, 0))
                          for d, v in sorted(by_day.items()))
        full = [v for d, v in by_day.items() if d not in (iso(t0)[:10], iso(t1)[:10])] or list(by_day.values())
        print("  %-10s %d book polls; contracts/day %s  -> %s"
              % (city, n_polls, parts,
                 "PASS so far" if min(full) >= 50 else "FAIL so far (needs 50 every day)"))
    print()
    print("BAR 3 -- safety: zero closes where the index crossed the strike after a >= 1 F entry")
    settles = [r for r in rows if r.get("k") == "settle"]
    paper = [r for r in settles if r.get("paper")]
    crossed = [r for r in paper if r["paper"].get("crossed")]
    lost = [r for r in paper if r["paper"].get("win") is False]
    won = [r for r in paper if r["paper"].get("win") is True]
    pend = [r for r in rows if r.get("k") == "would_buy"]
    pnl = sum(r["paper"]["pnl_c"] or 0 for r in paper)
    print("  paper trades: %d logged, %d settled (%d won, %d lost), money %+.2f $ ; crossed after entry: %d"
          % (len(pend), len(paper), len(won), len(lost), pnl / 100, len(crossed)))
    for r in crossed + [x for x in lost if x not in crossed]:
        p = r["paper"]
        print("    !! %s %s bought %s %d @ %.2f with margin %.2fF, index moved %+.2fF, result %s, %+d c"
              % (iso(r["t"]), r["ticker"], p["side"], p["n"], p["px"], p["margin_f"],
                 p.get("idx_move_f") or 0, r["result"], p["pnl_c"] or 0))
    # hypothetical: every polled (market, close) with margin >= 1 F at any lead
    by_mc = {}
    for r in books:
        if r.get("margin_f") is None or r["margin_f"] < 1.0 or r.get("lead_s") is None:
            continue
        by_mc.setdefault(r["ticker"], []).append(r)
    idx_close = {r["ticker"]: r for r in settles if r.get("idx_close_v") is not None}
    buckets = {"lead <= 7 min": [0, 0], "7-10 min": [0, 0], "> 10 min": [0, 0]}
    for tkr, rs in by_mc.items():
        s = idx_close.get(tkr)
        if s is None:
            continue
        close_side = "yes" if s["idx_close_v"] > s["strike"] else "no"
        for r in rs:
            b = ("lead <= 7 min" if r["lead_s"] <= 420 else "7-10 min" if r["lead_s"] <= 600 else "> 10 min")
            buckets[b][0] += 1
            if r["side"] != close_side:
                buckets[b][1] += 1
    print("  every book poll with >= 1 F margin, by how far the known index point was before the close:")
    for b, (n, x) in buckets.items():
        print("    %-14s %6d polls, index ended on the other side of the strike %d times" % (b, n, x))
    print("  -> %s" % ("PASS so far" if not crossed else "FAIL"))
    print()
    eq = [r for r in settles if r.get("settle_eq_index") is not None]
    yes = sum(1 for r in eq if r["settle_eq_index"])
    print("Settlement == index at the close minute: %d of %d compared%s"
          % (yes, len(eq), "" if yes == len(eq) else "  <-- MISMATCHES, read the settle lines"))
    for r in eq:
        if not r["settle_eq_index"]:
            print("    %s settled %s, index at close minute %s (%s)"
                  % (r["ticker"], r["expiration_value"], r["idx_close_v"],
                     "exact minute" if r["idx_close_exact"] else "nearest minute"))
    errs = [r for r in rows if r.get("k") == "err"]
    print("Fetch errors: %d (%s)" % (len(errs), ", ".join(sorted(set(str(e.get("what")) for e in errs))) or "-"))
    print("Shadow days so far: %.2f of the 3-5 the bar asks for." % days)


# ---------------------------------------------------------------- selftest
def selftest():
    """Planted worlds. Fails if the rule misses a plant or fires on nothing."""
    fails = []

    def ck(cond, msg):
        if not cond:
            fails.append(msg)

    # world clock: a market closing at C, we are at C - 60 s
    C = 1_800_000_000
    strike = 78.99

    def mk_world(idx_v, idx_t, no_bids, now, extra_markets=None, result=None, ev=None,
                 idx_close_v=None):
        logs = []
        markets = [{"ticker": "KXTEMPMIAH-TEST-T78.99", "series_ticker": "KXTEMPMIAH",
                    "event_ticker": "KXTEMPMIAH-TEST", "strike_type": "greater",
                    "floor_strike": strike, "close_time": iso(C), "open_time": iso(C - 3600),
                    "status": "active", "result": result or "", "expiration_value": ev or ""}]
        markets += extra_markets or []
        ts = [{"t": idx_t * 1000, "v": idx_v, "status": "normal", "contributors": 5}]
        if idx_close_v is not None:
            ts.append({"t": C * 1000, "v": idx_close_v, "status": "normal", "contributors": 5})
        clock = {"now": now}

        def gi(city):
            # the real feed only ever holds points already in the past
            return 200, {"city": city,
                         "timeseries": [p for p in ts if p["t"] / 1000 <= clock["now"]]}

        def kg(path, params=None):
            if path == "/markets":
                return 200, {"markets": markets}
            if path.endswith("/orderbook"):
                return 200, {"orderbook_fp": {"no_dollars": no_bids, "yes_dollars": [["0.0100", "10.00"]]}}
            return 404, {}
        w = Watch(log=logs.append, clock=lambda: clock["now"], get_index=gi, kget=kg,
                  cities={"miami": "KXTEMPMIAH"})
        real_step = w.step

        def step(t=None):
            clock["now"] = clock["now"] if t is None else t
            return real_step(clock["now"])
        w.step = step
        return w, logs

    def decisions(logs):
        return [r["decision"] for r in logs if r["k"] == "book"]

    # 1. plant: index 80.5 (margin 1.51), age 300, lead 360, NO bids 5c x 40 -> YES ask 95c x 40
    now = C - 60
    w, logs = mk_world(80.5, C - 360, [["0.0500", "40.00"], ["0.0200", "100.00"]], now)
    w.step(now)
    d = decisions(logs)
    # 40 at 95c only (the 100 at 98c are above the 97c cap) -> 40 @ 0.95
    ck(d == ["would buy 40 @ 0.95"], "plant 1: expected 'would buy 40 @ 0.95', got %r" % d)
    wb = [r for r in logs if r["k"] == "would_buy"]
    ck(len(wb) == 1 and wb[0]["side"] == "yes" and wb[0]["n"] == 40 and wb[0]["px"] == 0.95
       and wb[0]["fee_c"] == fee_cents(40, 0.95), "plant 1: would_buy record wrong: %r" % wb)
    ck(fee_cents(40, 0.95) == 14, "fee: 40 @ 95c should be 14c (0.07*40*.95*.05=13.3 -> 14), got %d" % fee_cents(40, 0.95))
    # second poll must NOT buy again
    w.step(now + 30)
    ck(decisions(logs)[-1].startswith("refuse: already bought"), "plant 1: bought twice: %r" % decisions(logs))
    bk = [r for r in logs if r["k"] == "book"][0]
    ck(bk["age_s"] == 300.0 and bk["lead_s"] == 360.0 and bk["margin_f"] == 1.51 and bk["depth97"] == 40,
       "plant 1: book line fields wrong: age %s lead %s margin %s depth %s"
       % (bk["age_s"], bk["lead_s"], bk["margin_f"], bk["depth97"]))
    idx = [r for r in logs if r["k"] == "index"]
    ck(idx and idx[0]["age_s"] == 300.0, "index age not computed from the point's own time")
    # 1b. NO side: index 77.0 (margin 1.99 below strike) -> buy NO from YES bids
    logs = []

    def kg_no(path, params=None):
        if path == "/markets":
            return 200, {"markets": [{"ticker": "KXTEMPMIAH-TEST-T78.99", "event_ticker": "E",
                                      "strike_type": "greater", "floor_strike": strike,
                                      "close_time": iso(C), "open_time": iso(C - 3600), "status": "active"}]}
        return 200, {"orderbook_fp": {"yes_dollars": [["0.0400", "25.00"]], "no_dollars": []}}
    w = Watch(log=logs.append, clock=lambda: now,
              get_index=lambda c: (200, {"timeseries": [{"t": (C - 360) * 1000, "v": 77.0}]}),
              kget=kg_no, cities={"miami": "KXTEMPMIAH"})
    w.step(now)
    ck(decisions(logs) == ["would buy 25 @ 0.96"], "plant 1b (NO side): got %r" % decisions(logs))
    # 2. margin too small (0.6 F) -> refused, and no would_buy
    w, logs = mk_world(79.59, C - 360, [["0.0500", "40.00"]], now)
    w.step(now)
    ck(decisions(logs) == ["refuse: margin 0.60F < 1.0F"], "null 2 (margin): %r" % decisions(logs))
    ck(not [r for r in logs if r["k"] == "would_buy"], "null 2 fired")
    # 3. stale index (age 500 s) -> refused
    w, logs = mk_world(80.5, C - 560, [["0.0500", "40.00"]], now)
    w.step(now)
    ck(decisions(logs)[0].startswith("refuse: index stale: age 500s"), "null 3 (stale): %r" % decisions(logs))
    # 4. lead too long: age fine (300) but point is 660 s before close (we are at C-360)
    w, logs = mk_world(80.5, C - 660, [["0.0500", "40.00"]], C - 360)
    w.step(C - 360)
    ck(decisions(logs)[0].startswith("refuse: known index point is 660s before close"),
       "null 4 (lead): %r" % decisions(logs))
    # 5. no offer under 97c (best 99c) -> refused, best_ask logged as 0.99
    w, logs = mk_world(80.5, C - 360, [["0.0100", "500.00"]], now)
    w.step(now)
    ck(decisions(logs) == ["refuse: no yes offer <= 97c (best 99c)"], "null 5 (no offer): %r" % decisions(logs))
    bk = [r for r in logs if r["k"] == "book"][0]
    ck(bk["best_ask"] == 0.99 and bk["depth97"] == 0, "null 5: best_ask/depth wrong: %r" % bk)
    # 6. outside the window (tau 400 > 360) but inside the 480 s book window -> polled, refused
    w, logs = mk_world(80.5, C - 700, [["0.0500", "40.00"]], C - 400)
    w.step(C - 400)
    ck(decisions(logs) == ["refuse: tau 400s > 360s window"], "null 6 (window): %r" % decisions(logs))
    # 7. before the book window (tau 500) -> no book poll at all
    w, logs = mk_world(80.5, C - 700, [["0.0500", "40.00"]], C - 500)
    w.step(C - 500)
    ck(decisions(logs) == [], "null 7: polled a book outside the last 8 min")
    # 8. ask under 50c -> refused (market disagrees hard)
    w, logs = mk_world(80.5, C - 360, [["0.6000", "40.00"]], now)
    w.step(now)
    ck(decisions(logs)[0].startswith("refuse: best yes ask 40c under 50c floor"), "null 8: %r" % decisions(logs))
    # 9. settlement: paper YES wins, settle == index, not crossed
    w, logs = mk_world(80.5, C - 360, [["0.0500", "40.00"]], now, result="yes", ev="80.61", idx_close_v=80.61)
    w.step(now)
    w.step(C + 130)
    st = [r for r in logs if r["k"] == "settle"]
    ck(len(st) == 1, "settle 9: expected one settle line, got %d" % len(st))
    if st:
        s = st[0]
        ck(s["settle_eq_index"] is True and s["idx_close_exact"] is True, "settle 9: eq/exact wrong %r" % s)
        p = s["paper"]
        ck(p["win"] is True and p["crossed"] is False and p["pnl_c"] == 200 - fee_cents(40, 0.95),
           "settle 9: paper outcome wrong %r" % p)
        ck(p["idx_move_f"] == 0.11, "settle 9: idx_move %r" % p["idx_move_f"])
    # 10. settlement: index crossed after entry, paper LOSES, money negative, settle != index flagged
    w, logs = mk_world(80.5, C - 360, [["0.0500", "40.00"]], now, result="no", ev="78.50", idx_close_v=78.50)
    w.step(now)
    w.step(C + 130)
    s = [r for r in logs if r["k"] == "settle"][0]
    p = s["paper"]
    ck(p["win"] is False and p["crossed"] is True and p["pnl_c"] == -(3800 + fee_cents(40, 0.95)),
       "settle 10: loss not booked: %r" % p)
    ck(s["settle_eq_index"] is True, "settle 10: eq should be True (78.50 == 78.50)")
    # 10b. settle value differs from the index -> mismatch flagged
    w, logs = mk_world(80.5, C - 360, [["0.0500", "40.00"]], now, result="yes", ev="80.80", idx_close_v=80.61)
    w.step(now)
    w.step(C + 130)
    s = [r for r in logs if r["k"] == "settle"][0]
    ck(s["settle_eq_index"] is False, "settle 10b: mismatch not flagged")
    # 11. result not yet set -> no settle line, retried later
    w, logs = mk_world(80.5, C - 360, [["0.0500", "40.00"]], now, result="", ev="", idx_close_v=80.61)
    w.step(now)
    w.step(C + 130)
    ck(not [r for r in logs if r["k"] == "settle"], "settle 11: settled without a result")
    # 12. no index at all -> refused, never buys
    logs = []
    w = Watch(log=logs.append, clock=lambda: now, get_index=lambda c: (500, "boom"),
              kget=lambda p, q=None: (200, {"markets": [{"ticker": "X-T78.99", "event_ticker": "E",
                                                          "strike_type": "greater", "floor_strike": strike,
                                                          "close_time": iso(C), "open_time": iso(C - 3600),
                                                          "status": "active"}]}) if p == "/markets"
              else (200, {"orderbook_fp": {"no_dollars": [["0.0500", "40.00"]], "yes_dollars": []}}),
              cities={"miami": "KXTEMPMIAH"})
    w.step(now)
    ck(decisions(logs) == ["refuse: no index yet"], "null 12: %r" % decisions(logs))
    ck([r for r in logs if r["k"] == "err" and r["what"] == "index"], "null 12: index error not logged")
    # 13. ladder helper: YES ask = 1 - NO bid, sorted cheapest first, capped at 97c
    lad = ladder_for({"orderbook_fp": {"no_dollars": [["0.0100", "5"], ["0.0500", "7"], ["0.0300", "9"]]}}, "yes")
    ck(lad == [[0.95, 7.0], [0.97, 9.0]], "ladder: %r" % lad)
    ck(take([[0.95, 7.0], [0.97, 9.0]], 10) == (10, 0.956), "take: %r" % (take([[0.95, 7.0], [0.97, 9.0]], 10),))
    # 14. this file can never send an order: no non-GET verb, no order path
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    body = src[:src.rindex("def selftest")]
    ck("port" + "folio/orders" not in body, "an order path appears in the working code")
    ck('method="POST"' not in body and "'POST'" not in body and "data=" not in body,
       "a non-GET request appears in the working code")
    ck("kalshi_data" not in body and "feed_data" not in body, "touches the tape directories")
    for f in fails:
        print("FAIL:", f)
    print("selftest: %s (%d checks failed)" % ("PASS" if not fails else "FAIL", len(fails)))
    return 0 if not fails else 1


# -------------------------------------------------------------------- main
def rss_mb():
    try:
        import ctypes
        import ctypes.wintypes as wt

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = wt.HANDLE
        fn = k32.K32GetProcessMemoryInfo
        fn.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]
        fn.restype = wt.BOOL
        if fn(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
            return pmc.WorkingSetSize / 1048576
    except Exception:  # noqa: BLE001
        pass
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--margin", type=float, default=MARGIN_F)
    ap.add_argument("--max-age", type=float, default=MAX_AGE_S)
    ap.add_argument("--max-lead", type=float, default=MAX_LEAD_S)
    ap.add_argument("--window", type=float, default=WINDOW_S)
    ap.add_argument("--cap", type=int, default=CAP)
    ap.add_argument("--out", default=None, help="jsonl path (default results/wxwatch-<startUTC>.jsonl)")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if a.report:
        report()
        return
    if os.environ.get("KALS_SELFTESTED") != "1" and selftest() != 0:
        print("self-test failed; refusing to watch real data")
        sys.exit(1)
    start = time.time()
    path = a.out or os.path.join(RESULTS, "wxwatch-%s.jsonl" % iso(start).replace(":", "").replace("-", ""))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fh = open(path, "a", encoding="utf-8")

    def log(obj):
        fh.write(json.dumps(obj, separators=(",", ":")) + "\n")
        fh.flush()

    def out(s):
        print(s, flush=True)

    stop = os.path.join(RESULTS, "wxwatch.stop")
    out("%s wxwatch start pid %d -> %s  (rule: margin>=%.1fF age<=%.0fs lead<=%.0fs window %.0fs cap %d)"
        % (iso(start), os.getpid(), path, a.margin, a.max_age, a.max_lead, a.window, a.cap))
    w = Watch(log=log, margin=a.margin, max_age=a.max_age, max_lead=a.max_lead,
              window=a.window, cap=a.cap, out=out)
    log({"k": "start", "t": start, "pid": os.getpid(), "cities": CITIES,
         "rule": {"margin_f": a.margin, "max_age_s": a.max_age, "max_lead_s": a.max_lead,
                  "window_s": a.window, "cap": a.cap, "min_px": MIN_PX, "max_px": MAX_PX}})
    last_beat = 0.0
    while True:
        if os.path.exists(stop):
            out("%s stop file present, exiting" % iso(time.time()))
            log({"k": "stop", "t": time.time()})
            break
        try:
            w.step()
        except Exception as e:  # noqa: BLE001 -- a watcher must not die on one bad body
            log({"k": "err", "t": time.time(), "what": "step", "body": repr(e)[:300]})
            out("%s step error: %r" % (iso(time.time()), e))
        now = time.time()
        if now - last_beat >= 600:
            last_beat = now
            nw = {c: (None if v is None else "%.2fF age %.0fs" % (v[1], now - v[0]))
                  for c, v in w.newest.items()}
            out("%s alive: markets %d, rss %s MB, index %s"
                % (iso(now), len(w.markets), "?" if rss_mb() is None else "%.0f" % rss_mb(), nw))
        time.sleep(1.0)
    fh.close()


if __name__ == "__main__":
    main()
