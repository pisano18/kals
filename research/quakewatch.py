#!/usr/bin/env python3
"""quakewatch.py -- READ-ONLY shadow watcher for the biggest-quake lock
(IDEAS_2026-09-24 idea #4, KXBIGGESTQUAKE). Places NO orders. GET only.

    python research/quakewatch.py --selftest    # planted quakes, no network
    python research/quakewatch.py               # watch, log to results/
    python research/quakewatch.py --report      # running tally against the bar

PRE-REGISTERED BAR -- written 2026-09-24 ~08:00Z BEFORE any shadow data was
read (the only prior data is the 52-market / 931-trade tape study in
IDEAS_2026-09-24.md). Over 14 days of shadow, BOTH of:

  1. Money: on at least HALF of the quake-days, at least $10 of resting YES
     depth at <= 97c on the locked strikes is visible >= 30 s after the
     quake was first seen on the USGS feed. Dollars = contracts x
     (1 - price - taker fee), the gross a taker would collect if the lock
     holds. Per quake-day: for each locked market the most seen in one
     snapshot taken >= 30 s after first sight, summed over that day's
     locked markets.
  2. Safety: ZERO false locks. A false lock is a strike we called locked
     (a USGS magnitude at or above it) whose market then settled NO, or
     whose locking quake was revised below the strike.

Fail either and the idea is dropped. --report prints the tally next to
these numbers; nothing in this file learns the bar from the data.

WHAT IT WATCHES

USGS public GeoJSON (no key):
    https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson
        &starttime=<now-36h>&minmagnitude=4.8&orderby=time
polled every 60 s. Every event id is remembered with the magnitude we FIRST
saw and every later revision (USGS revises; an initial 5.4 that becomes
5.3 is the false-lock case the bar exists for). 4.8 not 5.0 so an upward
revision into a strike is not missed.

Kalshi KXBIGGESTQUAKE markets: `KXBIGGESTQUAKE-24SEP26-6.6` = the UTC day
2026-09-24, strike_type greater_or_equal on floor_strike 6.6 (rules: "the
highest USGS-reported earthquake magnitude worldwide during <day> from
12:00:00 AM through 11:59:59 PM UTC is 6.6 or higher"). Open markets are
re-listed every 5 min. While any is open its book is read every 60 s; a
market that has just locked is read every 10 s for the first 10 min so the
"+30 s" snapshot the bar asks for exists.

A LOCK: a USGS event with origin time inside the market's UTC day whose
CURRENTLY known magnitude is >= the strike. Logged once per market with
the seconds since we first saw the event and since its origin. If a later
revision drops the day's max below the strike the lock is logged as
broken (and counts as false).

THE PAPER RULE ("would buy"): on a locked market, the first book snapshot
taken >= 30 s after the locking quake was first seen that shows any YES
resting at <= 97c -> "would buy N @ p", N = the whole ladder to 97c capped
at CAP (50), p = volume-weighted, taker fee included. One per market.
Refusals ("too early", "no YES offer <= 97c", "book unreadable") are logged
so the empty population is visible.

WHAT IT LOGS -- results/quakewatch-<startUTC>.jsonl, one JSON object per
line, field `k`:

  quake        first sight of a USGS event >= 4.8: id, mag, origin, place,
               seconds from origin to our first sight, USGS status/magType.
  quake_rev    a magnitude revision: id, old, new.
  market       first sight of a KXBIGGESTQUAKE market, and status changes.
  lock         a strike locked: ticker, strike, event, mag, s since first
               sight, s since origin, the YES ask before the lock.
  lock_broken  a revision un-locked a strike (false lock).
  book         a book snapshot: ticker, strike, locked?, s since first
               sight of the locking quake, best YES ask + size, ladder to
               97c, depth (contracts) and dollars at <= 97c, decision.
               Unlocked markets log a line only when the ladder changed or
               10 min passed, so the file stays small; the poll itself is
               every 60 s.
  would_buy    the paper trade.
  settle       result, expiration_value (USGS max for the day), lock mag,
               false_lock flag, paper win/loss and money.
  err          a failed fetch.

Memory: events older than 48 h and settled markets are dropped.

NOTHING HERE PLACES AN ORDER. The only Kalshi client is research/kauth.py,
which can only GET; USGS is a public unauthenticated GET.
"""

import argparse
import datetime as dt
import glob
import json
import math
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")

SERIES = "KXBIGGESTQUAKE"
USGS_URL = ("https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson"
            "&starttime=%s&minmagnitude=%.1f&orderby=time")
USGS_MIN_MAG = 4.8
USGS_LOOKBACK = 36 * 3600

MAX_PX = 0.97
CAP = 50
MIN_AFTER_S = 30            # the bar's "visible >= 30 s after first sight"

USGS_EVERY = 60
DISCOVER_EVERY = 300
BOOK_EVERY = 60
BURST_EVERY = 10
BURST_FOR = 600
QUIET_LOG_EVERY = 600       # unlocked, unchanged book: log at most this often
SETTLE_EVERY = 600
SETTLE_GIVEUP = 36 * 3600
EVENT_KEEP = 48 * 3600
MIN_GAP = 0.15

FEE_RATE = 0.07
MON = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6, "JUL": 7,
       "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}


def fee_per(p):
    return FEE_RATE * p * (1 - p)


def fee_cents(n, p):
    return math.ceil(FEE_RATE * n * p * (1 - p) * 100 - 1e-9)


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def day_of(ticker):
    """UTC day (epoch of 00:00Z) from KXBIGGESTQUAKE-24SEP26-6.6, else None."""
    m = re.search(r"-(\d\d)([A-Z]{3})(\d\d)-", ticker)
    if not m or m.group(2) not in MON:
        return None
    d = dt.datetime(2000 + int(m.group(3)), MON[m.group(2)], int(m.group(1)), tzinfo=dt.timezone.utc)
    return d.timestamp()


# ---------------------------------------------------------------- network
_kauth = None
_last_req = [0.0]


def _throttle():
    gap = time.time() - _last_req[0]
    if gap < MIN_GAP:
        time.sleep(MIN_GAP - gap)
    _last_req[0] = time.time()


def kalshi_get(path, params=None):
    global _kauth
    if _kauth is None:
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        import kauth
        _kauth = kauth
    _throttle()
    return _kauth.get(path, params)


def fetch_usgs(now):
    st = dt.datetime.fromtimestamp(now - USGS_LOOKBACK, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    req = urllib.request.Request(USGS_URL % (st, USGS_MIN_MAG), method="GET",
                                 headers={"User-Agent": "kals-quakewatch/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read().decode())
    except Exception as e:  # noqa: BLE001
        return -1, str(e)[:200]


def yes_ladder(ob, max_px=MAX_PX):
    """YES asks (1 - NO bids) cheapest first, [[px, size]...], px <= max_px.
    None when the body is unreadable."""
    if not isinstance(ob, dict):
        return None
    book = ob.get("orderbook_fp")
    if not isinstance(book, dict):
        return None
    out = []
    for lvl in book.get("no_dollars") or []:
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


def depth_dollars(ladder):
    return round(sum(sz * (1 - px - fee_per(px)) for px, sz in ladder), 2)


def take(ladder, cap):
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
    def __init__(self, log, clock=time.time, get_usgs=fetch_usgs, kget=kalshi_get,
                 cap=CAP, out=None):
        self.log, self.clock, self.get_usgs, self.kget = log, clock, get_usgs, kget
        self.cap = cap
        self.out = out or (lambda s: None)
        self.events = {}        # id -> dict(first_seen, first_mag, mag, origin, ...)
        self.markets = {}       # ticker -> dict
        self.usgs_polls_ok = 0  # events on the very first read were NOT first seen by us
        self.next_usgs = 0.0
        self.next_discover = 0.0
        self.next_settle = {}   # event_ticker -> t
        self.polls = 0

    # -- USGS -------------------------------------------------------
    def poll_usgs(self, now):
        st, body = self.get_usgs(now)
        if st != 200 or not isinstance(body, dict):
            self.log({"k": "err", "t": now, "what": "usgs", "http": st, "body": str(body)[:200]})
            return
        startup = self.usgs_polls_ok == 0
        self.usgs_polls_ok += 1
        for f in body.get("features") or []:
            try:
                eid = f["id"]
                pr = f["properties"]
                mag = float(pr["mag"])
                origin = float(pr["time"]) / 1000.0
            except (KeyError, TypeError, ValueError):
                continue
            ev = self.events.get(eid)
            if ev is None:
                ev = {"id": eid, "first_seen": now, "first_mag": mag, "mag": mag, "origin": origin,
                      "place": pr.get("place"), "status": pr.get("status"), "magType": pr.get("magType"),
                      "updated": (float(pr["updated"]) / 1000.0) if pr.get("updated") else None,
                      "revs": [], "startup": startup}
                self.events[eid] = ev
                self.log({"k": "quake", "t": now, "id": eid, "mag": mag, "origin": origin,
                          "origin_iso": iso(origin), "place": ev["place"], "startup": startup,
                          "first_seen_lag_s": round(now - origin, 1),
                          "usgs_updated_lag_s": None if ev["updated"] is None else round(ev["updated"] - origin, 1),
                          "status": ev["status"], "magType": ev["magType"]})
                if mag >= 5.0:
                    self.out("%s QUAKE M%.1f %s (origin %s, first seen %.0f s after)"
                             % (iso(now), mag, ev["place"], iso(origin), now - origin))
            elif abs(mag - ev["mag"]) > 1e-9:
                self.log({"k": "quake_rev", "t": now, "id": eid, "old": ev["mag"], "new": mag,
                          "status": pr.get("status"), "magType": pr.get("magType")})
                ev["revs"].append((now, ev["mag"], mag))
                ev["mag"] = mag
                ev["status"] = pr.get("status")
        for eid in [e for e, v in self.events.items() if v["origin"] < now - EVENT_KEEP]:
            del self.events[eid]

    def day_max(self, day0):
        """(mag, event) of the biggest CURRENTLY known event on that UTC day."""
        best = (None, None)
        for ev in self.events.values():
            if day0 <= ev["origin"] < day0 + 86400:
                if best[0] is None or ev["mag"] > best[0]:
                    best = (ev["mag"], ev)
        return best

    # -- markets ----------------------------------------------------
    def discover(self, now):
        st, body = self.kget("/markets", {"series_ticker": SERIES, "limit": 100,
                                          "min_close_ts": int(now) - 6 * 3600})
        if st != 200 or not isinstance(body, dict):
            self.log({"k": "err", "t": now, "what": "discover", "http": st, "body": str(body)[:200]})
            return
        for m in body.get("markets") or []:
            tkr = m.get("ticker")
            if not tkr or m.get("floor_strike") is None:
                continue
            if m.get("strike_type") not in ("greater_or_equal", "greater"):
                continue
            day0 = day_of(tkr)
            if day0 is None:
                continue
            try:
                close = parse_iso(m["close_time"])
            except (KeyError, ValueError):
                continue
            rec = self.markets.get(tkr)
            if rec is None:
                rec = {"ticker": tkr, "event": m.get("event_ticker"), "day0": day0,
                       "strike": float(m["floor_strike"]), "ge": m.get("strike_type") == "greater_or_equal",
                       "close": close, "status": m.get("status"), "next_book": 0.0,
                       "lock": None, "paper": None, "settled": False, "polls": 0,
                       "last_ladder": None, "last_logged": 0.0, "pre_ask": None,
                       "best_after30_dollars": 0.0, "refused_once": False}
                self.markets[tkr] = rec
                self.log({"k": "market", "t": now, "ticker": tkr, "day": iso(day0)[:10],
                          "strike": rec["strike"], "close": close, "close_iso": iso(close),
                          "status": rec["status"], "yes_ask": m.get("yes_ask_dollars")})
            else:
                if m.get("status") != rec["status"] or abs(close - rec["close"]) > 1:
                    self.log({"k": "market", "t": now, "ticker": tkr, "status": m.get("status"),
                              "was": rec["status"], "close": close, "close_iso": iso(close),
                              "early_close": close < rec["day0"] + 86400 - 1})
                    rec["status"] = m.get("status")
                    rec["close"] = close
        for tkr in [t for t, r in self.markets.items()
                    if r["settled"] or now > r["close"] + SETTLE_GIVEUP + 3600]:
            self.markets.pop(tkr)

    # -- locks ------------------------------------------------------
    def qualifies(self, rec, mag):
        return mag >= rec["strike"] - 1e-9 if rec["ge"] else mag > rec["strike"] + 1e-9

    def check_locks(self, now):
        for rec in self.markets.values():
            if rec["settled"]:
                continue
            mag, ev = self.day_max(rec["day0"])
            if rec["lock"] is None:
                if mag is not None and self.qualifies(rec, mag):
                    rec["lock"] = {"t": now, "id": ev["id"], "mag": mag, "first_mag": ev["first_mag"],
                                   "first_seen": ev["first_seen"], "origin": ev["origin"],
                                   "startup": ev.get("startup", False),
                                   "s_after_first_seen": round(now - ev["first_seen"], 1),
                                   "s_after_origin": round(now - ev["origin"], 1),
                                   "pre_ask": rec["pre_ask"], "broken": False}
                    rec["next_book"] = 0.0
                    self.log(dict({"k": "lock", "ticker": rec["ticker"], "strike": rec["strike"],
                                   "day": iso(rec["day0"])[:10], "place": ev["place"]}, **rec["lock"]))
                    self.out("%s LOCK %s (strike %.1f) by %s M%.1f, %.0f s after first sight, YES ask before %s"
                             % (iso(now), rec["ticker"], rec["strike"], ev["id"], mag,
                                now - ev["first_seen"], rec["pre_ask"]))
            elif not rec["lock"]["broken"]:
                if mag is None or not self.qualifies(rec, mag):
                    rec["lock"]["broken"] = True
                    rec["lock"]["broken_t"] = now
                    rec["lock"]["mag_now"] = mag
                    self.log({"k": "lock_broken", "t": now, "ticker": rec["ticker"], "strike": rec["strike"],
                              "id": rec["lock"]["id"], "lock_mag": rec["lock"]["mag"], "mag_now": mag})
                    self.out("%s LOCK BROKEN %s: day max now %s < strike %.1f (FALSE LOCK)"
                             % (iso(now), rec["ticker"], mag, rec["strike"]))

    # -- books ------------------------------------------------------
    def poll_book(self, rec, now):
        st, ob = self.kget("/markets/%s/orderbook" % rec["ticker"])
        rec["polls"] += 1
        full = yes_ladder(ob, max_px=1.0) if st == 200 else None
        if st != 200:
            self.log({"k": "err", "t": now, "what": "book", "ticker": rec["ticker"], "http": st,
                      "body": str(ob)[:200]})
        ladder = None if full is None else [lv for lv in full if lv[0] <= MAX_PX + 1e-9]
        best = (full[0][0] if full else None) if full is not None else None
        if rec["lock"] is None and best is not None:
            rec["pre_ask"] = best
        depth = sum(sz for _p, sz in (ladder or []))
        dollars = depth_dollars(ladder or [])
        lk = rec["lock"]
        since = None if lk is None else round(now - lk["first_seen"], 1)
        decision = None
        if lk is not None and not lk["broken"]:
            if since is not None and since >= MIN_AFTER_S:
                rec["best_after30_dollars"] = max(rec["best_after30_dollars"], dollars)
            if rec["paper"] is not None:
                decision = "refuse: already bought this market"
            elif since < MIN_AFTER_S:
                decision = "refuse: too early (%.0fs < %ds after first USGS sight)" % (since, MIN_AFTER_S)
            elif ladder is None:
                decision = "refuse: book unreadable"
            elif not ladder:
                decision = "refuse: no YES offer <= 97c (best %s)" % ("none" if best is None else "%.0fc" % (best * 100))
            else:
                n, px = take(ladder, self.cap)
                decision = "would buy %d @ %.2f" % (n, px)
        elif lk is not None:
            decision = "refuse: lock broken by a USGS revision"
        changed = ladder != rec["last_ladder"]
        if lk is not None or changed or now - rec["last_logged"] >= QUIET_LOG_EVERY:
            rec["last_ladder"] = ladder
            rec["last_logged"] = now
            self.log({"k": "book", "t": now, "ticker": rec["ticker"], "strike": rec["strike"],
                      "day": iso(rec["day0"])[:10], "locked": lk is not None and not lk["broken"],
                      "s_since_first_seen": since,
                      "s_since_lock": None if lk is None else round(now - lk["t"], 1),
                      "best_yes_ask": best, "best_size": ladder[0][1] if ladder else None,
                      "ladder97": ladder, "depth97": depth, "dollars97": dollars,
                      "http": st, "decision": decision})
        if decision and decision.startswith("would buy"):
            n, px = take(ladder, self.cap)
            rec["paper"] = {"t": now, "n": n, "px": px, "cost_c": round(n * px * 100),
                            "fee_c": fee_cents(n, px), "s_since_first_seen": since,
                            "lock_mag": lk["mag"], "depth97": depth, "dollars97": dollars}
            self.log(dict({"k": "would_buy", "ticker": rec["ticker"], "strike": rec["strike"],
                           "day": iso(rec["day0"])[:10]}, **rec["paper"]))
            self.out("%s WOULD BUY %s YES %d @ %.2f (%.0f s after first sight; $%.2f resting at <=97c)"
                     % (iso(now), rec["ticker"], n, px, since, dollars))

    # -- settlement -------------------------------------------------
    def poll_settle(self, event, now):
        st, body = self.kget("/markets", {"event_ticker": event, "limit": 100})
        if st != 200 or not isinstance(body, dict):
            self.log({"k": "err", "t": now, "what": "settle", "event": event, "http": st,
                      "body": str(body)[:200]})
            return
        ms = {m.get("ticker"): m for m in body.get("markets") or []}
        for tkr, rec in self.markets.items():
            if rec["settled"] or rec["event"] != event:
                continue
            m = ms.get(tkr)
            if m is None:
                continue
            result = m.get("result")
            give_up = now > rec["close"] + SETTLE_GIVEUP
            if result not in ("yes", "no") and not give_up:
                continue
            try:
                evf = float(m.get("expiration_value"))
            except (TypeError, ValueError):
                evf = None
            lk = rec["lock"]
            false_lock = None
            if lk is not None:
                false_lock = lk["broken"] or (result == "no")
            line = {"k": "settle", "t": now, "ticker": tkr, "strike": rec["strike"],
                    "day": iso(rec["day0"])[:10], "result": result or None, "expiration_value": evf,
                    "locked": lk is not None, "lock_mag": None if lk is None else lk["mag"],
                    "lock_first_mag": None if lk is None else lk["first_mag"],
                    "lock_s_after_first_seen": None if lk is None else lk["s_after_first_seen"],
                    "lock_startup": None if lk is None else lk.get("startup", False),
                    "false_lock": false_lock, "best_after30_dollars": rec["best_after30_dollars"],
                    "book_polls": rec["polls"], "close": rec["close"], "close_iso": iso(rec["close"]),
                    "gave_up": give_up and result not in ("yes", "no")}
            p = rec["paper"]
            if p is not None:
                win = None if result not in ("yes", "no") else (result == "yes")
                pnl = None if win is None else (round(p["n"] * (1 - p["px"]) * 100 - p["fee_c"]) if win
                                                else -round(p["n"] * p["px"] * 100 + p["fee_c"]))
                line["paper"] = dict(p, win=win, pnl_c=pnl)
                self.out("%s SETTLED %s %s paper YES %d @ %.2f -> %s %s"
                         % (iso(now), tkr, result, p["n"], p["px"],
                            "WIN" if win else "LOSS" if win is False else "?",
                            "" if pnl is None else "%+d c" % pnl))
            if false_lock:
                self.out("%s FALSE LOCK %s: locked at M%s, settled %s" % (iso(now), tkr, lk["mag"], result))
            self.log(line)
            rec["settled"] = True

    # -- scheduler --------------------------------------------------
    def step(self, now=None):
        now = self.clock() if now is None else now
        if now >= self.next_usgs:
            self.next_usgs = now + USGS_EVERY
            self.poll_usgs(now)
            self.check_locks(now)
        if now >= self.next_discover:
            self.next_discover = now + DISCOVER_EVERY
            self.discover(now)
            self.check_locks(now)
        for rec in list(self.markets.values()):
            if rec["settled"] or now >= rec["close"]:
                continue
            if rec["status"] not in ("active", "open", None):
                continue
            if now >= rec["next_book"]:
                lk = rec["lock"]
                burst = lk is not None and not lk["broken"] and now - lk["t"] < BURST_FOR
                rec["next_book"] = now + (BURST_EVERY if burst else BOOK_EVERY)
                self.poll_book(rec, now)
        events = {}
        for rec in self.markets.values():
            if not rec["settled"] and now >= rec["close"] + 60 and rec["event"]:
                events[rec["event"]] = True
        for event in events:
            if now >= self.next_settle.get(event, 0.0):
                self.next_settle[event] = now + SETTLE_EVERY
                self.poll_settle(event, now)
        self.polls += 1


# ------------------------------------------------------------------ report
def report(paths=None):
    paths = paths or sorted(glob.glob(os.path.join(RESULTS, "quakewatch-*.jsonl")))
    rows = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    if not rows:
        print("quakewatch --report: no quakewatch-*.jsonl under results/ yet")
        return
    t0 = min(r["t"] for r in rows)
    t1 = max(r["t"] for r in rows)
    days = (t1 - t0) / 86400
    print("quakewatch report: %s .. %s UTC (%.2f days of the 14 the bar asks for, %d lines)"
          % (iso(t0), iso(t1), days, len(rows)))
    quakes = [r for r in rows if r.get("k") == "quake"]
    big = [r for r in quakes if r["mag"] >= 5.0]
    fresh = [r for r in quakes if not r.get("startup")]
    lags = sorted(r["first_seen_lag_s"] for r in fresh)
    print("quakes seen: %d at >= 4.8, %d at >= 5.0 (%d were already on the feed when a watcher started);"
          " typical delay from the shake to our first sight %s min (%d fresh)"
          % (len(quakes), len(big), len(quakes) - len(fresh),
             "-" if not lags else "%.1f" % (lags[len(lags) // 2] / 60), len(fresh)))
    revs = [r for r in rows if r.get("k") == "quake_rev"]
    print("magnitude revisions logged: %d (%d downward)" % (len(revs), sum(1 for r in revs if r["new"] < r["old"])))
    locks = [r for r in rows if r.get("k") == "lock"]
    broken = [r for r in rows if r.get("k") == "lock_broken"]
    settles = [r for r in rows if r.get("k") == "settle"]
    false_settled = [r for r in settles if r.get("false_lock")]
    print()
    print("BAR 2 -- safety: zero false locks")
    print("  locks called: %d; broken by a USGS revision: %d; settled against us: %d  -> %s"
          % (len(locks), len(broken), len(false_settled),
             "PASS so far" if not broken and not false_settled else "FAIL"))
    for r in broken:
        print("    !! %s %s locked at M%.1f, day max revised to %s" % (iso(r["t"]), r["ticker"], r["lock_mag"], r["mag_now"]))
    for r in false_settled:
        print("    !! %s %s locked at M%s, settled %s" % (iso(r["t"]), r["ticker"], r["lock_mag"], r["result"]))
    print()
    print("BAR 1 -- money: >= $10 of resting YES at <= 97c visible >= 30 s after first sight,"
          " on at least half of the quake-days")
    # per quake-day: sum over locked markets of the best snapshot >= 30 s after first sight
    by_day = {}
    books = [r for r in rows if r.get("k") == "book" and r.get("locked")
             and r.get("s_since_first_seen") is not None and r["s_since_first_seen"] >= MIN_AFTER_S]
    best = {}
    for r in books:
        best[(r["day"], r["ticker"])] = max(best.get((r["day"], r["ticker"]), 0.0), r.get("dollars97") or 0.0)
    for (day, _tk), v in best.items():
        by_day[day] = by_day.get(day, 0.0) + v
    fresh_locks = [r for r in locks if not r.get("startup")]
    startup_locks = [r for r in locks if r.get("startup")]
    lock_days = sorted(set(r["day"] for r in fresh_locks))
    for d in lock_days:
        by_day.setdefault(d, 0.0)
    if startup_locks:
        print("  (%d lock(s) on %s came from quakes already on the feed when a watcher started;"
              " their '+30 s' timing is not real and they are left out of this tally)"
              % (len(startup_locks), ", ".join(sorted(set(r["day"] for r in startup_locks)))))
    if not lock_days:
        print("  no quake-day yet (no strike has locked on a quake we saw arrive)")
    else:
        ok = sum(1 for d in lock_days if by_day[d] >= 10)
        for d in lock_days:
            print("    %s  locked strikes %d  best resting money seen >= 30 s after first sight $%.2f"
                  % (d, sum(1 for r in fresh_locks if r["day"] == d), by_day[d]))
        print("  quake-days %d, with >= $10: %d  -> %s" % (
            len(lock_days), ok, "PASS so far" if ok * 2 >= len(lock_days) else "FAIL so far"))
    wb = [r for r in rows if r.get("k") == "would_buy"]
    paper = [r for r in settles if r.get("paper")]
    pnl = sum((r["paper"]["pnl_c"] or 0) for r in paper)
    print()
    print("paper trades: %d logged, %d settled (%d won, %d lost), money %+.2f $"
          % (len(wb), len(paper), sum(1 for r in paper if r["paper"]["win"]),
             sum(1 for r in paper if r["paper"]["win"] is False), pnl / 100))
    pre = [r["pre_ask"] for r in locks if r.get("pre_ask") is not None]
    if pre:
        print("YES ask just before the lock: %s" % ", ".join("%.0fc" % (p * 100) for p in pre))
    errs = [r for r in rows if r.get("k") == "err"]
    print("fetch errors: %d (%s)" % (len(errs), ", ".join(sorted(set(str(e.get("what")) for e in errs))) or "-"))


# ---------------------------------------------------------------- selftest
def selftest():
    fails = []

    def ck(cond, msg):
        if not cond:
            fails.append(msg)

    D = 1_800_057_600          # a UTC midnight (1_800_057_600 % 86400 == 0)
    ck(D % 86400 == 0, "test day is not a UTC midnight")
    day_tag = dt.datetime.fromtimestamp(D, dt.timezone.utc).strftime("%d%b%y").upper()

    def market(strike, result="", ev="", status="active", close=None):
        return {"ticker": "%s-%s-%.1f" % (SERIES, day_tag, strike), "event_ticker": "%s-%s" % (SERIES, day_tag),
                "strike_type": "greater_or_equal", "floor_strike": strike, "status": status,
                "close_time": iso(close if close is not None else D + 86399), "result": result,
                "expiration_value": ev}

    def world(features, markets, books, now):
        logs = []
        clock = {"now": now}
        state = {"features": features, "markets": markets, "books": books}

        def usgs(t):
            return 200, {"features": [f for f in state["features"] if f["_visible_at"] <= clock["now"]]}

        def kg(path, params=None):
            if path == "/markets":
                return 200, {"markets": state["markets"]}
            if path.endswith("/orderbook"):
                tkr = path.split("/")[2]
                b = state["books"].get(tkr)
                if callable(b):
                    b = b(clock["now"])
                return (200, {"orderbook_fp": {"no_dollars": b, "yes_dollars": []}}) if b is not None else (404, {})
            return 404, {}
        w = Watch(log=logs.append, clock=lambda: clock["now"], get_usgs=usgs, kget=kg)
        real = w.step

        def step(t):
            clock["now"] = t
            real(t)
        w.step = step
        return w, logs, state

    def feat(eid, mag, origin, visible_at):
        return {"id": eid, "_visible_at": visible_at,
                "properties": {"mag": mag, "time": origin * 1000, "updated": (origin + 400) * 1000,
                               "place": "test", "status": "automatic", "magType": "mww"}}

    def kinds(logs, k):
        return [r for r in logs if r["k"] == k]

    # world A: M5.5 at D+10:00, seen at T0; strikes 5.2/5.4/5.6/5.8; book YES 95c x 30 + 97c x 20
    T0 = D + 36000 + 300
    mk = [market(s) for s in (5.2, 5.4, 5.6, 5.8)]
    books = {m["ticker"]: [["0.0500", "30.00"], ["0.0300", "20.00"], ["0.0100", "500.00"]] for m in mk}
    w, logs, st = world([feat("usA", 5.5, D + 36000, T0)], mk, books, T0 - 120)
    w.step(T0 - 120)                  # before the quake: markets found, books polled, no lock
    ck(len(kinds(logs, "market")) == 4, "A: 4 markets expected, got %d" % len(kinds(logs, "market")))
    ck(not kinds(logs, "lock") and not kinds(logs, "quake"), "A: locked/quaked before the quake")
    ck(len(kinds(logs, "book")) == 4, "A: pre-quake books should be logged once (changed), got %d" % len(kinds(logs, "book")))
    w.step(T0)                        # quake appears
    q = kinds(logs, "quake")
    ck(len(q) == 1 and q[0]["mag"] == 5.5 and q[0]["first_seen_lag_s"] == 300.0, "A: quake line wrong %r" % q)
    lk = kinds(logs, "lock")
    ck(sorted(r["strike"] for r in lk) == [5.2, 5.4], "A: locks should be 5.2 and 5.4 only, got %r" % [r["strike"] for r in lk])
    ck(all(r["s_after_first_seen"] == 0.0 and r["s_after_origin"] == 300.0 and r["pre_ask"] == 0.95 for r in lk),
       "A: lock timing/pre_ask wrong %r" % lk)
    # books right after the lock are 'too early'
    dec = [r["decision"] for r in kinds(logs, "book") if r["locked"]]
    ck(dec and all(d.startswith("refuse: too early") for d in dec), "A: expected too-early refusals, got %r" % dec)
    ck(not kinds(logs, "would_buy"), "A: bought inside 30 s")
    w.step(T0 + 10)                   # burst poll still too early
    ck(not kinds(logs, "would_buy"), "A: bought at +10 s")
    w.step(T0 + 30)                   # +30 s: buys 50 (30@95 + 20@97) on both locked strikes
    wb = kinds(logs, "would_buy")
    ck(len(wb) == 2 and all(r["n"] == 50 and r["px"] == 0.958 and r["s_since_first_seen"] == 30.0 for r in wb),
       "A: would_buy wrong %r" % wb)
    ck(all(abs(r["dollars97"] - round(30 * (1 - .95 - fee_per(.95)) + 20 * (1 - .97 - fee_per(.97)), 2)) < 0.011
           for r in wb), "A: dollars97 wrong %r" % [r["dollars97"] for r in wb])
    ck(not [r for r in wb if r["strike"] >= 5.6], "A: bought an unlocked strike")
    w.step(T0 + 40)
    ck(len(kinds(logs, "would_buy")) == 2, "A: bought twice")
    ck([r["decision"] for r in kinds(logs, "book")][-1].startswith("refuse: already bought") or
       [r for r in kinds(logs, "book") if r["t"] == T0 + 40 and r["locked"]][0]["decision"].startswith("refuse: already"),
       "A: second buy not refused")
    # settle: results yes for 5.2/5.4, no for 5.6/5.8; expiration 5.5
    for m in st["markets"]:
        m["result"] = "yes" if m["floor_strike"] <= 5.5 else "no"
        m["expiration_value"] = "5.5"
        m["close_time"] = iso(T0 + 3600)   # early close
    w.step(T0 + 300)                  # discover picks up the early close
    ck(any(r.get("early_close") for r in kinds(logs, "market")), "A: early close not logged")
    w.step(T0 + 3700)
    se = kinds(logs, "settle")
    ck(len(se) == 4, "A: 4 settle lines expected, got %d" % len(se))
    ck(all(r["false_lock"] is False for r in se if r["locked"]) and
       all(r["false_lock"] is None for r in se if not r["locked"]), "A: false_lock flags wrong %r" % [(r["ticker"], r["false_lock"]) for r in se])
    pw = [r["paper"] for r in se if r.get("paper")]
    ck(len(pw) == 2 and all(p["win"] and p["pnl_c"] == round(50 * (1 - .958) * 100) - fee_cents(50, .958) for p in pw),
       "A: paper P&L wrong %r" % pw)
    ck(all(r["best_after30_dollars"] > 0 for r in se if r["locked"]), "A: best_after30_dollars not tracked")

    # world B: revision 5.5 -> 5.3 breaks the 5.4 lock; 5.4 settles NO -> false lock
    mk = [market(s) for s in (5.2, 5.4)]
    books = {m["ticker"]: [["0.0500", "30.00"]] for m in mk}
    fB = feat("usB", 5.5, D + 36000, T0)
    w, logs, st = world([fB], mk, books, T0)
    w.step(T0)
    ck(sorted(r["strike"] for r in kinds(logs, "lock")) == [5.2, 5.4], "B: initial locks wrong")
    fB["properties"]["mag"] = 5.3
    w.step(T0 + 60)
    rv = kinds(logs, "quake_rev")
    ck(len(rv) == 1 and rv[0]["old"] == 5.5 and rv[0]["new"] == 5.3, "B: revision not logged %r" % rv)
    br = kinds(logs, "lock_broken")
    ck(len(br) == 1 and br[0]["strike"] == 5.4 and br[0]["mag_now"] == 5.3, "B: 5.4 lock not broken %r" % br)
    w.step(T0 + 120)
    ck(not [r for r in kinds(logs, "would_buy") if r["strike"] == 5.4], "B: bought a broken lock")
    ck([r for r in kinds(logs, "would_buy") if r["strike"] == 5.2], "B: the still-good 5.2 lock never bought")
    for m in st["markets"]:
        m["result"] = "yes" if m["floor_strike"] <= 5.3 else "no"
        m["expiration_value"] = "5.3"
        m["close_time"] = iso(T0 + 600)
    w.step(T0 + 900)
    w.step(T0 + 1300)
    se = {r["strike"]: r for r in kinds(logs, "settle")}
    ck(5.4 in se and se[5.4]["false_lock"] is True and 5.2 in se and se[5.2]["false_lock"] is False,
       "B: false lock not flagged at settlement %r" % {k: v.get("false_lock") for k, v in se.items()})

    # world C (null): a quake on the PREVIOUS UTC day must not lock today; a 4.9 must not lock 5.2
    mk = [market(5.2)]
    w, logs, st = world([feat("usC1", 6.0, D - 3600, T0), feat("usC2", 4.9, D + 100, T0)], mk,
                        {mk[0]["ticker"]: [["0.0500", "30.00"]]}, T0)
    w.step(T0)
    w.step(T0 + 60)
    ck(not kinds(logs, "lock") and not kinds(logs, "would_buy"), "C (null): locked on a wrong-day or too-small quake")
    ck(len(kinds(logs, "quake")) == 2, "C: both events should still be logged as quakes")
    ck(all(r["startup"] for r in kinds(logs, "quake")), "C: events on the first read must be flagged startup")
    ck(all(r["decision"] is None for r in kinds(logs, "book")), "C: an unlocked book carried a decision")
    # world C2: an event that arrives on a LATER read is fresh, and a startup event's lock says so
    mk = [market(5.2), market(5.6)]
    w, logs, st = world([feat("usC3", 5.3, D + 100, T0 - 1000), feat("usC4", 5.8, D + 200, T0 + 60)], mk,
                        {m["ticker"]: [["0.0500", "30.00"]] for m in mk}, T0)
    w.step(T0)
    w.step(T0 + 60)
    qs = {r["id"]: r for r in kinds(logs, "quake")}
    ck(qs["usC3"]["startup"] is True and qs["usC4"]["startup"] is False, "C2: startup flags wrong %r" % qs)
    lks = {r["strike"]: r for r in kinds(logs, "lock")}
    ck(lks[5.2]["startup"] is True and lks[5.6]["startup"] is False, "C2: lock startup flags wrong %r" % lks)

    # world D: locked, but nothing resting under 97c -> refusal, no paper, dollars 0
    mk = [market(5.2)]
    w, logs, st = world([feat("usD", 5.5, D + 36000, T0)], mk, {mk[0]["ticker"]: [["0.0100", "500.00"]]}, T0)
    w.step(T0)
    w.step(T0 + 30)
    d = [r["decision"] for r in kinds(logs, "book") if r["locked"]]
    ck(d and d[-1] == "refuse: no YES offer <= 97c (best 99c)", "D: %r" % d)
    ck(not kinds(logs, "would_buy"), "D: bought with nothing under 97c")
    # unreadable book
    st["books"][mk[0]["ticker"]] = None
    w.step(T0 + 40)
    ck([r["decision"] for r in kinds(logs, "book") if r["locked"]][-1] == "refuse: book unreadable", "D: unreadable book not refused")

    # helpers
    ck(day_of("KXBIGGESTQUAKE-24SEP26-6.6") == parse_iso("2026-09-24T00:00:00Z"), "day_of wrong")
    ck(day_of("NOPE") is None, "day_of should be None on junk")
    ck(yes_ladder({"orderbook_fp": {"no_dollars": [["0.0100", "5"], ["0.0500", "7"], ["0.0300", "9"]]}}) ==
       [[0.95, 7.0], [0.97, 9.0]], "yes_ladder wrong")
    ck(fee_cents(50, 0.958) == 15, "fee 50 @ 95.8c should be 15c, got %d" % fee_cents(50, 0.958))
    # the file can never send an order
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    body = src[:src.rindex("def selftest")]
    ck("port" + "folio/orders" not in body, "an order path appears in the working code")
    ck('method="POST"' not in body and "'POST'" not in body and "data=" not in body, "a non-GET request appears")
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
    ap.add_argument("--cap", type=int, default=CAP)
    ap.add_argument("--out", default=None)
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
    path = a.out or os.path.join(RESULTS, "quakewatch-%s.jsonl" % iso(start).replace(":", "").replace("-", ""))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fh = open(path, "a", encoding="utf-8")

    def log(obj):
        fh.write(json.dumps(obj, separators=(",", ":")) + "\n")
        fh.flush()

    def out(s):
        print(s, flush=True)

    stop = os.path.join(RESULTS, "quakewatch.stop")
    out("%s quakewatch start pid %d -> %s (cap %d, USGS >= %.1f every %ds)"
        % (iso(start), os.getpid(), path, a.cap, USGS_MIN_MAG, USGS_EVERY))
    w = Watch(log=log, cap=a.cap, out=out)
    log({"k": "start", "t": start, "pid": os.getpid(), "series": SERIES,
         "rule": {"cap": a.cap, "max_px": MAX_PX, "min_after_s": MIN_AFTER_S, "usgs_min_mag": USGS_MIN_MAG}})
    last_beat = 0.0
    while True:
        if os.path.exists(stop):
            out("%s stop file present, exiting" % iso(time.time()))
            log({"k": "stop", "t": time.time()})
            break
        try:
            w.step()
        except Exception as e:  # noqa: BLE001
            log({"k": "err", "t": time.time(), "what": "step", "body": repr(e)[:300]})
            out("%s step error: %r" % (iso(time.time()), e))
        now = time.time()
        if now - last_beat >= 600:
            last_beat = now
            locked = [t for t, r in w.markets.items() if r["lock"] and not r["lock"]["broken"]]
            out("%s alive: events %d, markets %d (locked %d), rss %s MB"
                % (iso(now), len(w.events), len(w.markets), len(locked),
                   "?" if rss_mb() is None else "%.0f" % rss_mb()))
        time.sleep(1.0)
    fh.close()


if __name__ == "__main__":
    main()
