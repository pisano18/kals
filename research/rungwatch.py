#!/usr/bin/env python3
"""rungwatch.py -- READ-ONLY depth watcher for the FAR rungs of Kalshi's hourly
crypto ladders (KXBTCD, KXETHD, KXSOLD, KXXRPD). Places NO orders. GET only.

    python research/rungwatch.py --selftest      # planted worlds, no network, no tape
    python research/rungwatch.py                  # watch, log to results/rungwatch-<startUTC>.jsonl
    python research/rungwatch.py --report         # tally by cushion band and tau

THE QUESTION (results/FAR_RUNG_2026-09-25.md). On the hourly ladder a rung
$300+ from the index with 45 s left is near-certain: the 60-second settlement
average cannot plausibly cross it. Those rungs trade at 99c with thousands of
contracts resting. The 15-minute bot refuses anything over 98c because 99c
fills there were the pick-off population -- but a $300 cushion on BTC is a
different animal from a $20 one. This watcher measures the SUPPLY: how many
contracts are really offered at <= 99c on the safe side, by cushion, at 45 /
30 / 15 s, per close. The crossing PROBABILITY comes from the index tape
(part 1 of the report), not from here; this file only records what the
settlement did to each rung it saw.

WHAT IT WATCHES, every 15 s inside the last 90 s of every hour (polls at
tau = 90, 75, 60, 45, 30, 15, 5; the actual tau is logged):

  * the settlement index from the recorder's OWN tape
    (C:\\kals\\kalshi_data\\cfbenchmarks_value, read-only, streamed): the newest
    print per index and the locked prints of the settlement window
    [close-60, close-1] (settlewin.partial's window), from which the bot-style
    projection is (locked_sum + remaining x newest) / 60. The cushion of a
    rung is projection - strike, signed; the SAFE side is YES when it is
    positive, NO when negative.
  * GET /markets?event_ticker=<series>-<yyMONddHH> (paged): every rung's best
    bid/ask and their sizes. The NO side is implied: a NO ask is 1 - the YES
    bid with the YES bid's size.
  * GET /markets/{ticker}/orderbook for the rungs in the cushion band of
    interest ($100-650 on BTC, the same 12-77 basis-point band on the
    siblings, capped per side): the whole safe-side ask ladder, from which
    "contracts at <= 99c" is the sum of sizes at asks <= 0.99. All four
    ladders tick in WHOLE CENTS (price_level_structure linear_cent, step
    0.01, read live 2026-09-25), so <= 99.0c, <= 99.5c and <= 99.9c are the
    same number; 99c is the last price under $1.
  * five minutes after the close: the settlement from the tape (the mean of
    the 60 prints, and the exchange's own avg_60s_data on the print AT the
    close, which the recorder carries), and every rung's `result` from
    GET /markets -- so each rung seen at each poll is marked won/lost for
    its safe side. A rung whose safe side lost is a CROSSING.

WHAT IT LOGS -- results/rungwatch-<startUTC>.jsonl, one JSON object per line,
field `k`:

  start     rule and schedule.
  index     per poll: close, tau, per index id the newest print, the locked
            count/sum and the projection.
  rungs     per poll per series: close, tau, spot, projection, rung spacing,
            and every rung within 2% of spot: strike, cushion (dollars and
            bp), safe side, safe-side best ask and its size (from the row).
  book      per poll per fetched rung: ticker, cushion, safe side, the ask
            ladder at >= 90c, depth at <= 97 / 98 / 99c.
  noevent   an hour Kalshi lists no event for (02:00-05:00 ET has none).
  settle    per close per series: settle mean, n prints, exchange avg,
            |settle - projection| at each poll, every rung's result, and the
            list of crossings (rung, tau, cushion, safe side).
  err       a failed fetch or tape read.

All timestamps are UTC epoch seconds (`t`) or ISO-Z strings. Memory: nothing
is kept beyond the current close; the tape is streamed. NOTHING HERE PLACES
AN ORDER: the only Kalshi client is research/kauth.py, which can only GET.
"""

import argparse
import calendar
import datetime as dt
import glob
import gzip
import json
import math
import os
import re
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
TAPE_DIR = r"C:\kals\kalshi_data\cfbenchmarks_value"

# series -> (settlement index id, rung spacing in dollars)
LADDERS = {"KXBTCD": ("BRTI", 100.0), "KXETHD": ("ETHUSD_RTI", 5.0),
           "KXSOLD": ("SOLUSD_RTI", 0.25), "KXXRPD": ("XRPUSD_RTI", 0.02)}
N_AVG = 60
SCHEDULE = (90, 75, 60, 45, 30, 15, 5)     # seconds before the close
SETTLE_WAIT_S = 300                        # first settle read after the close
SETTLE_RETRY_S = 60
SETTLE_GIVEUP_S = 1800
ROW_SPAN_FRAC = 0.02                       # rungs logged from the rows: within 2% of spot
BOOK_BP_LO, BOOK_BP_HI = 11.0, 77.0        # $93-650 on BTC at ~$84.5k (rung $100 apart -> 6 a side)
BOOK_PER_SIDE = {"KXBTCD": 6, "KXETHD": 3, "KXSOLD": 3, "KXXRPD": 3}
BOOK_TAU_MAX_SIBLING = 45                  # siblings' books only at tau <= 45
MIN_GAP = 0.2                              # seconds between GETs (the money bot shares the key)
FEE_RATE = 0.07
BANDS_USD = ((0, 100), (100, 200), (200, 300), (300, 500), (500, float("inf")))
BANDS_BP = ((0, 12), (12, 24), (24, 36), (36, 60), (60, float("inf")))
PX_MAX = 0.99


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))


def event_ticker(series, close_s):
    """KXBTCD-26SEP2423 for the event closing 2026-09-25T03:00:00Z: the date and
    HOUR are the Eastern wall clock of the close (pinrun.ladder_event_ticker)."""
    try:
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        from downtime import et_offset
        off = et_offset(close_s)
    except Exception:                                    # noqa: BLE001
        off = -4 * 3600
    et = time.gmtime(int(close_s) + int(off))
    return "%s-%02d%s%02d%02d" % (series, et.tm_year % 100,
                                   calendar.month_abbr[et.tm_mon].upper(),
                                   et.tm_mday, et.tm_hour)


def band_of(x, bands):
    for lo, hi in bands:
        if lo <= x < hi:
            return "%g-%g" % (lo, hi) if hi != float("inf") else "%g+" % lo
    return None


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


def fetch_event_rows(get_fn, ev, status=None, page_max=4):
    """All rows of an event, following the cursor. Returns (rows, why)."""
    rows, cursor, why = [], None, None
    for _ in range(page_max):
        p = {"event_ticker": ev, "limit": "200"}
        if status:
            p["status"] = status
        if cursor:
            p["cursor"] = cursor
        st, b = get_fn("/markets", p)
        if st != 200 or not isinstance(b, dict):
            why = "http_%s" % st
            break
        rows.extend(b.get("markets") or [])
        cursor = b.get("cursor")
        if not cursor:
            break
    return rows, why


def ask_ladder(ob, side, min_px=0.90):
    """Asks for buying `side`, cheapest first, [[px, size], ...] with px >=
    min_px, from a /orderbook body. Kalshi's REST book lists BIDS in dollars;
    a YES ask is 1 - a NO bid, a NO ask is 1 - a YES bid (pinracearm.book_ask)."""
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
            if ask >= min_px - 1e-9:
                out.append([ask, sz])
    out.sort()
    return out


def depth_at(ladder, max_px):
    return round(sum(sz for px, sz in ladder if px <= max_px + 1e-9), 2)


def row_side(row, safe):
    """(best ask, size) for buying `safe` from a /markets row. NO is implied
    from the YES bid."""
    try:
        if safe == "yes":
            ask = float(row.get("yes_ask_dollars"))
            sz = float(row.get("yes_ask_size_fp") or 0)
        else:
            bid = float(row.get("yes_bid_dollars"))
            ask = round(1.0 - bid, 4)
            sz = float(row.get("yes_bid_size_fp") or 0)
    except (TypeError, ValueError):
        return None, None
    if ask <= 0 or ask >= 1.0 or sz <= 0:
        return None, None
    return ask, sz


# ------------------------------------------------------------------- tape
_ID_RE = re.compile(r'\\"time\\":\s*(\d+),\s*\\"id\\":\s*\\"([A-Z_]+)\\",\s*\\"value\\":\s*\\"([0-9.]+)\\"')
_AVG_RE = re.compile(r'"avg_60s_data":\s*\{\s*"value":\s*"([0-9.]+)",\s*"window_size":\s*(\d+)')


def tape_prints(ids, t_lo, t_hi, tape_dir=TAPE_DIR):
    """{id: {sec: value}} for prints with t_lo <= sec <= t_hi, plus
    {id: {sec: exchange_avg_60s}} for the same prints, streamed from the hour
    files that cover the span. Read-only; a truncated (still-growing) gzip
    yields what was readable. Never json-decodes a line it does not need."""
    out = {i: {} for i in ids}
    avg = {i: {} for i in ids}
    needles = [('"%s"' % i).encode() if False else '"%s"' % i for i in ids]
    h0, h1 = int(t_lo) // 3600, int(t_hi) // 3600
    for h in range(h0, h1 + 1):
        path = os.path.join(tape_dir, time.strftime("%Y%m%dT%H", time.gmtime(h * 3600)) + ".jsonl.gz")
        if not os.path.exists(path):
            continue
        try:
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
                try:
                    for line in fh:
                        if not any(n in line for n in needles):
                            continue
                        m = _ID_RE.search(line)
                        if not m:
                            continue
                        sec = int(m.group(1)) // 1000
                        if sec < t_lo or sec > t_hi:
                            continue
                        iid = m.group(2)
                        if iid not in out:
                            continue
                        out[iid][sec] = float(m.group(3))
                        a = _AVG_RE.search(line)
                        if a and int(a.group(2)) == N_AVG:
                            avg[iid][sec] = float(a.group(1))
                except (EOFError, OSError, gzip.BadGzipFile, zlib.error):
                    pass                                 # growing file: keep what we have
        except OSError:
            continue
    return out, avg


def projection(prints, close_s, now_s):
    """(proj, locked_n, locked_sum, newest_sec, newest_val) the way the bot
    prices it: locked prints [close-60, min(now, close-1)], the remainder
    filled with the newest print. None without a newest print."""
    if not prints:
        return None
    newest = max(prints)
    cur = prints[newest]
    lo, hi = close_s - N_AVG, min(int(now_s), close_s - 1)
    locked = [prints[s] for s in range(lo, hi + 1) if s in prints]
    n = len(locked)
    want = max(0, hi - lo + 1)
    if want and n < want * 0.95:
        return None                                       # window too holey to trust
    lsum = sum(locked) * (want / n) if n else 0.0
    r = N_AVG - want
    proj = (lsum + r * cur) / N_AVG
    return proj, want, lsum, newest, cur


def settle_of(prints, close_s):
    got = [prints[s] for s in range(close_s - N_AVG, close_s) if s in prints]
    if len(got) < N_AVG:
        return None, len(got)
    return sum(got) / N_AVG, N_AVG


# ------------------------------------------------------------------ watch
class Watch:
    """Every external edge injectable so the self-test drives a whole close
    with a fake clock, fake GETs and a fake tape."""

    def __init__(self, log, clock=time.time, get_fn=kalshi_get, tape_fn=tape_prints,
                 out=print, series=None):
        self.log, self.clock, self.get, self.tape, self.out = log, clock, get_fn, tape_fn, out
        self.series = list(series or LADDERS)
        self.done = set()          # (close, tau) polled
        self.noevent = set()       # (close, series)
        self.seen = {}             # close -> {series: {ticker: [(tau, cushion, safe)]}}
        self.proj_at = {}          # close -> {series: {tau: proj}}
        self.settle_due = {}       # close -> next attempt time
        self.settled = set()
        self.gets = 0

    # ---- one poll ----
    def poll(self, close_s, tau_sched):
        now = self.clock()
        tau = round(close_s - now, 1)
        ids = [LADDERS[s][0] for s in self.series]
        try:
            prints, _ = self.tape(ids, close_s - 120, int(now) + 1)
        except Exception as e:                            # noqa: BLE001
            self.log({"k": "err", "t": now, "what": "tape", "body": repr(e)[:300]})
            prints = {i: {} for i in ids}
        idx = {}
        for s in self.series:
            iid = LADDERS[s][0]
            pr = projection(prints.get(iid) or {}, close_s, now)
            if pr is None:
                idx[iid] = None
                continue
            proj, n_locked, lsum, nsec, nval = pr
            idx[iid] = {"proj": round(proj, 6), "locked_n": n_locked, "locked_sum": round(lsum, 4),
                        "newest_t": nsec, "newest": nval, "age_s": round(now - nsec, 2)}
        self.log({"k": "index", "t": now, "close": close_s, "tau": tau, "tau_sched": tau_sched, "idx": idx})
        for s in self.series:
            if (close_s, s) in self.noevent:
                continue
            iid, spacing = LADDERS[s]
            st_idx = idx.get(iid)
            ev = event_ticker(s, close_s)
            rows, why = fetch_event_rows(self.get, ev)
            self.gets += 1
            if not rows:
                self.noevent.add((close_s, s))
                self.log({"k": "noevent", "t": now, "close": close_s, "series": s, "event": ev, "why": why})
                continue
            if st_idx is None:
                self.log({"k": "err", "t": now, "what": "no_index", "series": s, "close": close_s})
                continue
            proj, spot = st_idx["proj"], st_idx["newest"]
            self.proj_at.setdefault(close_s, {}).setdefault(s, {})[str(tau_sched)] = proj
            rungs = []
            for m in rows:
                try:
                    k = float(m.get("floor_strike"))
                    if parse_iso(m.get("close_time")) != close_s:
                        continue
                except (TypeError, ValueError):
                    continue
                cush = proj - k
                if abs(cush) > ROW_SPAN_FRAC * spot:
                    continue
                safe = "yes" if cush > 0 else "no"
                ask, sz = row_side(m, safe)
                bp = abs(cush) / spot * 1e4
                rungs.append({"tk": m.get("ticker"), "k": k, "cush": round(cush, 4), "bp": round(bp, 2),
                              "safe": safe, "ask": ask, "sz": sz, "spot_cush": round(spot - k, 4)})
                self.seen.setdefault(close_s, {}).setdefault(s, {}).setdefault(m.get("ticker"), []).append(
                    (tau_sched, round(cush, 4), safe, round(bp, 2)))
            rungs.sort(key=lambda r: r["k"])
            self.log({"k": "rungs", "t": now, "close": close_s, "tau": tau, "tau_sched": tau_sched,
                      "series": s, "event": ev, "spot": spot, "proj": proj, "spacing": spacing,
                      "n_rows": len(rows), "why": why, "rungs": rungs})
            # order books for the band of interest
            if s != "KXBTCD" and tau_sched > BOOK_TAU_MAX_SIBLING:
                continue
            per_side = BOOK_PER_SIDE.get(s, 3)
            for safe in ("yes", "no"):
                cand = [r for r in rungs if r["safe"] == safe and BOOK_BP_LO <= r["bp"] <= BOOK_BP_HI]
                cand.sort(key=lambda r: r["bp"])
                for r in cand[:per_side]:
                    st, ob = self.get("/markets/%s/orderbook" % r["tk"], None)
                    self.gets += 1
                    lad = ask_ladder(ob, safe) if st == 200 else None
                    rec = {"k": "book", "t": self.clock(), "close": close_s, "tau": round(close_s - self.clock(), 1),
                           "tau_sched": tau_sched, "series": s, "tk": r["tk"], "strike": r["k"],
                           "cush": r["cush"], "bp": r["bp"], "safe": safe, "status": st}
                    if lad is None:
                        rec["why"] = "no_book"
                    else:
                        rec.update(ladder=lad, le97=depth_at(lad, 0.97), le98=depth_at(lad, 0.98),
                                   le99=depth_at(lad, PX_MAX),
                                   best=(lad[0][0] if lad else None), best_sz=(lad[0][1] if lad else None))
                    self.log(rec)

    # ---- settle ----
    def settle(self, close_s):
        now = self.clock()
        ids = [LADDERS[s][0] for s in self.series]
        try:
            prints, avgs = self.tape(ids, close_s - N_AVG - 1, close_s + 1)
        except Exception as e:                            # noqa: BLE001
            self.log({"k": "err", "t": now, "what": "tape_settle", "body": repr(e)[:300]})
            prints, avgs = {i: {} for i in ids}, {i: {} for i in ids}
        all_ok = True
        for s in self.series:
            if (close_s, s) in self.noevent:
                continue
            iid = LADDERS[s][0]
            sm, n = settle_of(prints.get(iid) or {}, close_s)
            xavg = (avgs.get(iid) or {}).get(close_s)
            ev = event_ticker(s, close_s)
            rows, why = fetch_event_rows(self.get, ev)
            self.gets += 1
            results = {}
            for m in rows:
                r = m.get("result")
                if r in ("yes", "no"):
                    results[m.get("ticker")] = r
            seen = (self.seen.get(close_s) or {}).get(s) or {}
            if not results and seen:
                all_ok = False
            crossings, marked = [], 0
            for tk, looks in seen.items():
                res = results.get(tk)
                if res is None:
                    continue
                for tau_s, cush, safe, bp in looks:
                    marked += 1
                    if res != safe:
                        crossings.append({"tk": tk, "tau": tau_s, "cush": cush, "bp": bp, "safe": safe, "result": res})
            pa = (self.proj_at.get(close_s) or {}).get(s) or {}
            miss = {t: (round(sm - p, 4) if sm is not None else None) for t, p in pa.items()}
            self.log({"k": "settle", "t": now, "close": close_s, "series": s, "event": ev, "settle": sm,
                      "n_prints": n, "exchange_avg": xavg,
                      "agree": (None if (sm is None or xavg is None) else abs(sm - xavg) < 0.01),
                      "settle_minus_proj": miss, "n_results": len(results), "n_seen": len(seen),
                      "n_marked": marked, "crossings": crossings, "why": why,
                      "results": {tk: results[tk] for tk in seen if tk in results}})
        return all_ok

    # ---- the loop body ----
    def step(self, now=None):
        now = self.clock() if now is None else now
        close_s = (int(now) // 3600 + 1) * 3600
        for tau in SCHEDULE:
            if now >= close_s - tau and (close_s, tau) not in self.done:
                self.done.add((close_s, tau))
                if all((close_s, s) in self.noevent for s in self.series):
                    continue
                self.poll(close_s, tau)
                break                                     # one poll per step
        # settle any past close whose time has come
        for c in sorted(set(c for c, _ in self.done)):
            if c in self.settled or now < c + SETTLE_WAIT_S:
                continue
            if all((c, s) in self.noevent for s in self.series):
                self.settled.add(c)
                continue
            due = self.settle_due.get(c, 0)
            if now < due:
                continue
            ok = self.settle(c)
            if ok or now > c + SETTLE_GIVEUP_S:
                self.settled.add(c)
            else:
                self.settle_due[c] = now + SETTLE_RETRY_S
        # forget closes long settled
        for c in [c for c in self.settled if now > c + SETTLE_GIVEUP_S + 3600]:
            self.seen.pop(c, None)
            self.proj_at.pop(c, None)
            self.done = set(d for d in self.done if d[0] != c)
            self.noevent = set(d for d in self.noevent if d[0] != c)
            self.settled.discard(c)


# ----------------------------------------------------------------- report
def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    i = (len(xs) - 1) * q
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def tally(paths):
    """Per (series, tau_sched, band): contracts at <= 99c summed over the rungs
    whose books were read (both sides), one number per close; crossings from
    the settle records; misses |settle - proj| per close. Returns a dict."""
    books = {}      # (series, close, tau) -> {band: [le99 per rung]}
    rows_best = {}  # (series, close, tau) -> {band: sum of best-level size at <= 99c}
    settles = {}    # (series, close) -> record
    nrungs = {}
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except Exception:                         # noqa: BLE001
                    continue
                k = r.get("k")
                if k == "book" and r.get("le99") is not None:
                    bands = BANDS_USD if r["series"] == "KXBTCD" else BANDS_BP
                    b = band_of(abs(r["cush"]) if r["series"] == "KXBTCD" else r["bp"], bands)
                    key = (r["series"], r["close"], r["tau_sched"])
                    books.setdefault(key, {}).setdefault(b, []).append(r["le99"])
                elif k == "rungs":
                    bands = BANDS_USD if r["series"] == "KXBTCD" else BANDS_BP
                    key = (r["series"], r["close"], r["tau_sched"])
                    d = rows_best.setdefault(key, {})
                    for g in r["rungs"]:
                        b = band_of(abs(g["cush"]) if r["series"] == "KXBTCD" else g["bp"], bands)
                        if g.get("ask") is not None and g["ask"] <= PX_MAX + 1e-9:
                            d[b] = d.get(b, 0.0) + (g.get("sz") or 0.0)
                        nrungs[(r["series"], r["close"], r["tau_sched"], b)] = \
                            nrungs.get((r["series"], r["close"], r["tau_sched"], b), 0) + 1
                elif k == "settle":
                    settles[(r["series"], r["close"])] = r
    return books, rows_best, settles, nrungs


def report(paths=None, out=print):
    paths = paths or sorted(glob.glob(os.path.join(RESULTS, "rungwatch-*.jsonl")))
    if not paths:
        out("rungwatch --report: no rungwatch-*.jsonl under results/ yet")
        return None
    books, rows_best, settles, nrungs = tally(paths)
    closes = sorted(set(c for (_, c) in settles))
    out("rungwatch report: %d file(s), %d settled close(s): %s"
        % (len(paths), len(closes), ", ".join(iso(c) for c in closes)))
    summary = {}
    for s in LADDERS:
        bands = BANDS_USD if s == "KXBTCD" else BANDS_BP
        unit = "$" if s == "KXBTCD" else "bp"
        scl = [c for (ss, c) in settles if ss == s]
        if not scl:
            continue
        out("\n== %s  (%d settled closes; bands in %s of cushion; contracts at <= 99c on the SAFE side)" % (s, len(scl), unit))
        out("  from the ORDER BOOKS (rungs fetched in the 12-77 bp band; sum over both sides, per close):")
        out("  %-8s %-10s %6s %10s %10s %10s %8s" % ("tau", "band", "closes", "median", "min", "max", "cross"))
        for tau in (45, 30, 15):
            for lo, hi in bands:
                b = band_of(lo, bands)
                vals = []
                for c in scl:
                    d = books.get((s, c, tau))
                    if d and b in d:
                        vals.append(sum(d[b]))
                nx = 0
                for c in scl:
                    rec = settles[(s, c)]
                    for x in rec.get("crossings") or []:
                        cb = band_of(abs(x["cush"]) if s == "KXBTCD" else x["bp"], bands)
                        if cb == b and x["tau"] == tau:
                            nx += 1
                summary[(s, tau, b)] = (len(vals), pct(vals, 0.5), min(vals) if vals else None, nx)
                if vals:
                    out("  %-8s %-10s %6d %10.0f %10.0f %10.0f %8d" % (tau, b, len(vals), pct(vals, 0.5), min(vals), max(vals), nx))
                else:
                    out("  %-8s %-10s %6d %10s %10s %10s %8d" % (tau, b, 0, "-", "-", "-", nx))
        out("  from the ROWS (best level only, every rung within 2%%; lower bound; per close):")
        for tau in (45, 30, 15):
            parts = []
            for lo, hi in bands:
                b = band_of(lo, bands)
                vals = [rows_best[(s, c, tau)].get(b, 0.0) for c in scl if (s, c, tau) in rows_best]
                parts.append("%s: med %s min %s" % (b, "-" if not vals else "%.0f" % pct(vals, 0.5),
                                                    "-" if not vals else "%.0f" % min(vals)))
            out("  tau %2d  %s" % (tau, " | ".join(parts)))
        out("  settlement vs the projection, per close (|settle - proj| at tau 45 / 30 / 15), and crossings:")
        for c in scl:
            rec = settles[(s, c)]
            miss = rec.get("settle_minus_proj") or {}
            fm = lambda t: ("%.2f" % abs(miss[str(t)])) if miss.get(str(t)) is not None else "-"   # noqa: E731
            out("   %s  settle %s  exch %s agree %s  miss45 %s miss30 %s miss15 %s  marked %d  crossings %d  results %d"
                % (iso(c), "-" if rec.get("settle") is None else "%.4f" % rec["settle"],
                   "-" if rec.get("exchange_avg") is None else "%.4f" % rec["exchange_avg"], rec.get("agree"),
                   fm(45), fm(30), fm(15), rec.get("n_marked", 0), len(rec.get("crossings") or []), rec.get("n_results", 0)))
            for x in rec.get("crossings") or []:
                out("      CROSSING %s tau %s cushion %s (%s bp) safe %s -> result %s" % (x["tk"], x["tau"], x["cush"], x["bp"], x["safe"], x["result"]))
    return summary


# --------------------------------------------------------------- selftest
def selftest():
    fails = []

    def ck(cond, msg):
        if not cond:
            fails.append(msg)

    # -- pure helpers
    ck(event_ticker("KXBTCD", parse_iso("2026-09-25T03:00:00Z")) == "KXBTCD-26SEP2423",
       "event ticker: 03:00Z on 09-25 is the 23:00 ET event of 09-24")
    ck(event_ticker("KXETHD", parse_iso("2026-09-24T14:00:00Z")) == "KXETHD-26SEP2410",
       "event ticker: 14:00Z is 10am EDT (read off GET /events 2026-09-24)")
    lad = ask_ladder({"orderbook_fp": {"no_dollars": [["0.0100", "8939.89"], ["0.0200", "1479.55"], ["0.0300", "1153.00"]],
                                       "yes_dollars": [["0.0100", "132043.21"], ["0.9700", "5.00"]]}}, "yes")
    ck(lad == [[0.97, 1153.0], [0.98, 1479.55], [0.99, 8939.89]],
       "YES asks are 1 - NO bids, cheapest first, >= 90c: got %r" % lad)
    ck(depth_at(lad, 0.99) == 11572.44 and depth_at(lad, 0.98) == 2632.55 and depth_at(lad, 0.97) == 1153.0,
       "depth at <= 99c sums the 97, 98 and 99c levels")
    lad_no = ask_ladder({"orderbook_fp": {"no_dollars": [["0.0100", "1.00"]],
                                          "yes_dollars": [["0.0100", "500.00"], ["0.0200", "7.00"], ["0.5000", "3.00"]]}}, "no")
    ck(lad_no == [[0.98, 7.0], [0.99, 500.0]], "NO asks are 1 - YES bids: got %r" % lad_no)
    ck(ask_ladder({}, "yes") is None and ask_ladder(None, "no") is None, "no book -> None, not an empty ladder")
    ck(row_side({"yes_ask_dollars": "0.9900", "yes_ask_size_fp": "7619.00", "yes_bid_dollars": "0.9800", "yes_bid_size_fp": "12.00"}, "yes") == (0.99, 7619.0),
       "row: YES best ask and size")
    ck(row_side({"yes_ask_dollars": "0.0200", "yes_ask_size_fp": "3.00", "yes_bid_dollars": "0.0100", "yes_bid_size_fp": "18567.00"}, "no") == (0.99, 18567.0),
       "row: NO best ask is 1 - YES bid, with the YES bid's size")
    ck(row_side({"yes_ask_dollars": "1.0000", "yes_ask_size_fp": "0.00", "yes_bid_dollars": "0.0000", "yes_bid_size_fp": "0.00"}, "yes") == (None, None),
       "row: an empty side is None")
    ck(band_of(150, BANDS_USD) == "100-200" and band_of(500, BANDS_USD) == "500+" and band_of(99.9, BANDS_USD) == "0-100"
       and band_of(30, BANDS_BP) == "24-36", "bands")
    # -- projection: 60-tau locked, tau x newest
    close = 1790298000
    pr = {close - 60 + i: 100.0 for i in range(60)}
    pr[close - 45] = 160.0                                  # the newest print at tau 45
    p = projection({s: v for s, v in pr.items() if s <= close - 45}, close, close - 45)
    ck(p is not None and abs(p[0] - (15 * 100.0 + 45 * 160.0) / 60) < 1e-9 and p[1] == 16,
       "projection at tau 45: prints [close-60, close-45] locked (16), the newest fills the rest: %r" % (p,))
    p60 = projection({close - 61: 5.0}, close, close - 61)
    ck(p60 is not None and p60[0] == 5.0 and p60[1] == 0, "before the window nothing is locked")
    ck(projection({}, close, close - 10) is None, "no prints -> None")
    holey = {close - 60 + i: 100.0 for i in range(0, 30, 2)}
    ck(projection(holey, close, close - 30) is None, "a window missing half its prints is refused")
    sm, n = settle_of({close - 60 + i: float(i) for i in range(60)}, close)
    ck(sm == 29.5 and n == 60, "settle is the mean of [close-60, close-1]")
    ck(settle_of({close - 60 + i: 1.0 for i in range(59)}, close) == (None, 59), "59 prints is not a settlement")
    # -- the tape reader on a planted gzip (never the real tape)
    import tempfile
    td = tempfile.mkdtemp(prefix="far_rw_")
    hour = close // 3600 * 3600
    path = os.path.join(td, time.strftime("%Y%m%dT%H", time.gmtime(hour)) + ".jsonl.gz")
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for i in range(0, 120):
            sec = close - 120 + i
            for iid, val in (("BRTI", 84000.0 + i), ("ETHUSD_RTI", 3400.0), ("DOGEUSD_RTI", 0.1)):
                # the recorder's compact form (no spaces); the regexes also tolerate spaces
                fh.write(json.dumps({"type": "cfbenchmarks_value", "msg": {
                    "index_id": iid, "data": json.dumps({"type": "value", "time": sec * 1000, "id": iid, "value": "%.2f" % val},
                                                        separators=(",", ":")),
                    "avg_60s_data": {"value": "%.8f" % (val - 0.5), "window_size": 60, "window_start_ts_ms": (sec - 60) * 1000,
                                     "window_end_ts_exclusive": sec * 1000}}}, separators=(",", ":")) + "\n")
        fh.write('{"type":"cfbenchmarks_value","msg":{"index_id":"BRTI","data":"{\\"type\\":\\"value\\",\\"time\\":' + str(close * 1000) + ',\\"id\\":\\"BRTI\\",\\"value\\":\\"99999.00\\"}","avg_60s_data":{"value":"84089.50000000","window_size":60}}}\n')
    ck(hour == (close - 120) // 3600 * 3600 or True, "planted hour")
    pr, av = tape_prints(["BRTI", "ETHUSD_RTI"], close - 60, close, tape_dir=td)
    ck(len(pr["BRTI"]) == 61 and pr["BRTI"][close - 60] == 84060.0 and pr["BRTI"][close] == 99999.0
       and "DOGEUSD_RTI" not in pr and len(pr["ETHUSD_RTI"]) == 60,
       "tape reader: the wanted ids, the wanted seconds, nothing else (%d BRTI, %d ETH)" % (len(pr["BRTI"]), len(pr["ETHUSD_RTI"])))
    ck(av["BRTI"].get(close) == 84089.5, "tape reader: the exchange avg on the print AT the close")
    # a truncated gzip yields what was readable
    with open(path, "rb") as fh:
        raw = fh.read()
    with open(path, "wb") as fh:
        fh.write(raw[: len(raw) * 2 // 3])
    pr2, _ = tape_prints(["BRTI"], close - 120, close, tape_dir=td)
    ck(0 < len(pr2["BRTI"]) < 121, "a growing/truncated gzip yields the readable prefix (%d prints)" % len(pr2["BRTI"]))
    # -- drive a whole close through the watcher with fakes
    logs = []
    clock = [close - 95.0]
    spot = 84500.0
    strikes = [spot - 1000 + 100 * i - 0.01 for i in range(21)]     # 83499.99 .. 85499.99
    ev = event_ticker("KXBTCD", close)
    settled = [False]
    gets = []

    def rows_for(res=False):
        rows = []
        for k in strikes:
            row = {"ticker": "KXBTCD-X-T%.2f" % k, "floor_strike": k, "close_time": iso(close), "event_ticker": ev,
                   "yes_ask_dollars": "0.9900", "yes_ask_size_fp": "7000.00", "yes_bid_dollars": "0.0100", "yes_bid_size_fp": "18000.00"}
            if res:
                # settle at 84450: rungs below win YES, above win NO -- EXCEPT the
                # planted crossing at 84199.99 ($300 under the index) marked NO
                row["result"] = "yes" if k < 84450 else "no"
                if abs(k - 84199.99) < 1e-6:
                    row["result"] = "no"
            rows.append(row)
        return rows

    def fake_get(path, params):
        gets.append((path, params))
        if path == "/markets":
            if params.get("event_ticker") != ev:
                return 200, {"markets": [], "cursor": None}
            return 200, {"markets": rows_for(settled[0]), "cursor": None}
        if path.endswith("/orderbook"):
            return 200, {"orderbook_fp": {"no_dollars": [["0.0100", "5000.00"], ["0.0200", "100.00"]],
                                          "yes_dollars": [["0.0100", "9000.00"], ["0.0200", "50.00"]]}}
        return 404, {}

    def fake_tape(ids, lo, hi, tape_dir=None):
        pr = {i: {} for i in ids}
        for s in range(int(lo), int(min(hi, clock[0])) + 1):
            if "BRTI" in pr:
                pr["BRTI"][s] = spot if s < close - 30 else spot - 100.0     # the index drops $100 at tau 30
        return pr, {i: {} for i in ids}

    w = Watch(log=logs.append, clock=lambda: clock[0], get_fn=fake_get, tape_fn=fake_tape, out=lambda s: None, series=["KXBTCD"])
    while clock[0] < close + SETTLE_WAIT_S + 1:
        w.step()
        if clock[0] >= close:
            settled[0] = True
        clock[0] += 1.0
    polls = [r for r in logs if r["k"] == "rungs"]
    ck([r["tau_sched"] for r in polls] == list(SCHEDULE), "one rungs record per scheduled tau: %r" % [r["tau_sched"] for r in polls])
    ck(all(abs(r["tau"] - r["tau_sched"]) < 1.5 for r in polls), "polls fire within a second of schedule")
    p45 = [r for r in polls if r["tau_sched"] == 45][0]
    ck(abs(p45["proj"] - spot) < 1e-6 and p45["spot"] == spot, "at tau 45 the projection is the flat index")
    r_below = [g for g in p45["rungs"] if abs(g["k"] - 84199.99) < 1e-6][0]
    r_above = [g for g in p45["rungs"] if abs(g["k"] - 84799.99) < 1e-6][0]
    ck(r_below["safe"] == "yes" and abs(r_below["cush"] - 300.01) < 1e-6 and r_below["ask"] == 0.99 and r_below["sz"] == 7000.0,
       "a rung $300 below: safe YES, cushion +300.01, row ask 99c x 7000: %r" % r_below)
    ck(r_above["safe"] == "no" and abs(r_above["cush"] + 299.99) < 1e-6 and r_above["ask"] == 0.99 and r_above["sz"] == 18000.0,
       "a rung $300 above: safe NO, cushion -299.99, NO ask 99c x 18000 (from the YES bid): %r" % r_above)
    p15 = [r for r in polls if r["tau_sched"] == 15][0]
    # at tau 15: locked 45 prints = 30 x spot + 15 x (spot-100), 15 remaining x (spot-100)
    exp15 = (30 * spot + 15 * (spot - 100) + 15 * (spot - 100)) / 60
    ck(abs(p15["proj"] - exp15) < 1e-6, "at tau 15 the projection carries the locked prints: %.3f vs %.3f" % (p15["proj"], exp15))
    bks = [r for r in logs if r["k"] == "book"]
    b45 = [r for r in bks if r["tau_sched"] == 45]
    ck(len(b45) == 2 * BOOK_PER_SIDE["KXBTCD"] and all(93 <= abs(r["cush"]) <= 651 for r in b45),
       "books at tau 45: %d per side, all inside $93-651 (the six rungs $100-600 out): %r"
       % (BOOK_PER_SIDE["KXBTCD"], sorted(round(r["cush"]) for r in b45)))
    by = [r for r in b45 if r["safe"] == "yes"][0]
    bn = [r for r in b45 if r["safe"] == "no"][0]
    ck(by["le99"] == 5100.0 and by["le98"] == 100.0 and by["best"] == 0.98, "YES book: 98c x 100 + 99c x 5000")
    ck(bn["le99"] == 9050.0 and bn["best"] == 0.98 and bn["best_sz"] == 50.0, "NO book from the YES bids: 98c x 50 + 99c x 9000")
    st = [r for r in logs if r["k"] == "settle"]
    ck(len(st) == 1, "exactly one settle record")
    if st:
        st = st[0]
        ck(st["settle"] is not None and abs(st["settle"] - (30 * spot + 30 * (spot - 100)) / 60) < 1e-6, "settle = mean of the 60 prints")
        xs = st["crossings"]
        planted = [x for x in xs if x["tk"].endswith("T84199.99")]
        edge = [x for x in xs if x["tk"].endswith("T84499.99")]
        ck(len(planted) == len(SCHEDULE) and all(x["safe"] == "yes" and x["result"] == "no" for x in planted),
           "the planted crossing (84199.99 marked NO, $300 under the index) is caught at every poll: %r" % planted)
        ck(len(edge) == 4 and sorted(x["tau"] for x in edge) == [45, 60, 75, 90] and all(abs(x["cush"] - 0.01) < 1e-6 for x in edge),
           "the 1-cent rung (84499.99) is a real crossing at the four polls before the $100 drop, and not after: %r" % edge)
        ck(len(xs) == len(planted) + len(edge), "no other crossing: %r" % [x for x in xs if x not in planted and x not in edge])
        ck(st["n_marked"] == len(SCHEDULE) * len(strikes), "every seen rung at every poll is marked")
        ck(abs(st["settle_minus_proj"]["45"] - (-50.0)) < 1e-6, "|settle - proj| at 45 is the $50 the drop cost")
    ck(not any(g[0] == "/markets" and g[1].get("event_ticker") not in (ev,) for g in gets), "only this close's event is fetched")
    # no-event hour: nothing polled after the first empty page
    logs2, gets2 = [], []
    clock2 = [close + 3600 - 95.0]

    def fake_get2(path, params):
        gets2.append(path)
        return 200, {"markets": [], "cursor": None}
    w2 = Watch(log=logs2.append, clock=lambda: clock2[0], get_fn=fake_get2, tape_fn=fake_tape, out=lambda s: None, series=["KXBTCD"])
    while clock2[0] < close + 3600 + SETTLE_WAIT_S + 1:
        w2.step()
        clock2[0] += 1.0
    ck(sum(1 for r in logs2 if r["k"] == "noevent") == 1 and len(gets2) == 1 and not [r for r in logs2 if r["k"] in ("rungs", "book", "settle")],
       "an hour with no event: one GET, one noevent record, no polls, no settle (%d gets)" % len(gets2))
    # -- report on the planted log
    rp = os.path.join(td, "rungwatch-planted.jsonl")
    with open(rp, "w", encoding="utf-8") as fh:
        for r in logs:
            fh.write(json.dumps(r) + "\n")
    lines = []
    summ = report([rp], out=lines.append)
    ck(summ is not None and summ.get(("KXBTCD", 45, "300-500")) is not None, "report tallies the 300-500 band at tau 45")
    if summ:
        n, med, mn, nx = summ[("KXBTCD", 45, "300-500")]
        # YES rungs at $300 and $400 (5100 each) + NO rungs at $300 and $400 (9050 each)
        ck(n == 1 and mn == med and nx == 1 and abs(med - 28300.0) < 1e-6,
           "300-500 at 45: one close, the planted crossing, depth summed over both sides: %r" % ((n, med, mn, nx),))
        ck(summ[("KXBTCD", 45, "100-200")][3] == 0 and summ[("KXBTCD", 45, "0-100")][3] == 1,
           "the 1-cent rung's crossing lands in 0-100, none in 100-200")
        ck(summ[("KXBTCD", 30, "200-300")][3] == 1, "at tau 30 the planted rung sits $250 out: crossing counted in 200-300")
    ck(any("CROSSING" in l for l in lines), "report prints the crossing")
    # -- this file cannot order and never writes the tape
    with open(os.path.abspath(__file__), encoding="utf-8") as fh:
        src = fh.read()
    # the working code is everything above the REAL def line (a newline then
    # the def); a literal "def selftest" inside this test must not be the cut
    body = src[:src.index("\ndef selftest():")]
    ck("portfolio/orders" not in body and "POST" not in body and "urlopen" not in body,
       "no order path, no POST, no raw urlopen: kauth.get is the only client")
    ck(body.count("gzip.open(") == 1 and '"rt"' in body, "the tape is opened read-only, once, as text")
    ck("feed_data" not in body, "never touches feed_data")
    try:
        import shutil
        shutil.rmtree(td, ignore_errors=True)
    except Exception:                                      # noqa: BLE001
        pass
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
    except Exception:                                      # noqa: BLE001
        pass
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--series", nargs="+", default=None, choices=sorted(LADDERS))
    ap.add_argument("--out", default=None, help="jsonl path (default results/rungwatch-<startUTC>.jsonl)")
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
    path = a.out or os.path.join(RESULTS, "rungwatch-%s.jsonl" % iso(start).replace(":", "").replace("-", ""))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fh = open(path, "a", encoding="utf-8")

    def log(obj):
        fh.write(json.dumps(obj, separators=(",", ":")) + "\n")
        fh.flush()

    def out(s):
        print(s, flush=True)

    stop = os.path.join(RESULTS, "rungwatch.stop")
    series = a.series or sorted(LADDERS)
    out("%s rungwatch start pid %d -> %s  (series %s; polls at tau %s; books %s-%s bp)"
        % (iso(start), os.getpid(), path, ",".join(series), SCHEDULE, BOOK_BP_LO, BOOK_BP_HI))
    log({"k": "start", "t": start, "pid": os.getpid(), "series": series, "schedule": SCHEDULE,
         "book_bp": [BOOK_BP_LO, BOOK_BP_HI], "book_per_side": BOOK_PER_SIDE, "tape": TAPE_DIR})
    w = Watch(log=log, out=out, series=series)
    last_beat = 0.0
    while True:
        if os.path.exists(stop):
            out("%s stop file present, exiting" % iso(time.time()))
            log({"k": "stop", "t": time.time()})
            break
        try:
            w.step()
        except Exception as e:                             # noqa: BLE001 -- a watcher must not die on one bad body
            log({"k": "err", "t": time.time(), "what": "step", "body": repr(e)[:300]})
            out("%s step error: %r" % (iso(time.time()), e))
        now = time.time()
        if now - last_beat >= 600:
            last_beat = now
            out("%s alive: gets %d, rss %s MB, closes settled %d"
                % (iso(now), w.gets, "?" if rss_mb() is None else "%.0f" % rss_mb(), len(w.settled)))
        time.sleep(0.5)
    fh.close()


if __name__ == "__main__":
    main()
