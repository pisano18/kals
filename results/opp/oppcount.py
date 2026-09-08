#!/usr/bin/env python3
"""oppcount.py -- COUNT the frozen pin rule's opportunities on the recorded tape.

Answers exactly one question: "did we see opportunities left open multiple
times a day, every day?"  It does not reason from any backtest summary; it
replays the orderbook (snapshot + delta, merged by seq) and the 1/sec index
and applies the LIVE frozen rule event by event.

THE RULE (results/PREREG_pin_live.md, as coded in pinrun.py):
  3 <= tau <= 20 s ; fair >= 0.98 -> buy YES at the yes ask
                    ; fair <= 0.02 -> buy NO  at the no ask
  net edge = gross - ceil(0.07*p*(1-p) to $0.0001) >= 0.005
  resting size at that level >= 1.0 whole contract
  at most one fire per close (earliest qualifying market)

FAIR VALUE, exactly as pinrun.fair/IndexWS.partial computes it:
  window [close-60, close-1]; locked ends at the NEWEST print actually held,
  every later second counted in `remaining` and modelled with spot;
  interior gaps filled from the nearest print held; >=95% of the window must
  be present.  mu = (locked + remaining*spot)/60.
  K_eff = floor_strike - 0.5*10^-round_digits, round_digits READ FROM THE
  EXCHANGE per series (never assumed).  sd = sigma*sqrt(var_factor(remaining)).
  sigma = sample SD of 1-second index diffs over the trailing 300 s.

MEMORY: one hour file at a time, book state only, no raw rows retained.
"""
import argparse
import bisect
import calendar
import gzip
import json
import math
import os
import sys
import time
import zlib
from collections import defaultdict
from statistics import NormalDist

RESEARCH = r"C:\kals-repo\research"
sys.path.insert(0, RESEARCH)          # inserted LAST => highest priority
from engine import var_factor, N_AVG                        # noqa: E402

ND = NormalDist()
DATA = r"C:\kals\kalshi_data"
MKTS = r"C:\kals-repo\results\opp\mkts.json"

SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI",
    "KXBNB15M": "BNBUSD_RTI", "KXBCH15M": "BCHUSD_RTI",
    "KXZEC15M": "ZECUSD_RTI", "KXHYPE15M": "HYPEUSD_RTI",
    "KXNEAR15M": "NEARUSD_RTI", "KXADA15M": "ADAUSD_RTI",
}

PIN = 0.98
TAU_MAX, TAU_MIN = 20, 3
EDGE_FLOOR = 0.005
MIN_LEVEL = 1.0
MAX_INDEX_AGE_S = 2
SIGMA_WIN = 300
MAX_BOOK_AGE_MS = 2000
EPS = 0.005            # a level below this is gone (racecheck.py uses the same)

TIMEQ = chr(92) + '"time' + chr(92) + '":'
VALQ = chr(92) + '"value' + chr(92) + '":' + chr(92) + '"'
BS = chr(92)


# ---------------------------------------------------------------- pricing --
def billed_fee(price, count=1):
    """ceil(0.07*p*(1-p)*count to the next $0.0001) -- pinrun.billed_fee."""
    return math.ceil(0.07 * price * (1.0 - price) * count * 10000.0) / 10000.0


def net_edge(f, price, want):
    gross = (f - price) if want == "yes" else ((1.0 - f) - price)
    return gross - billed_fee(price, 1)


def eff_strike(K, d):
    return float(K) - 0.5 * (10.0 ** (-int(d)))


def sigma_at(ticks, now_s, win=SIGMA_WIN):
    secs = [s for s in range(now_s - win, now_s + 1) if s in ticks]
    diffs = [ticks[secs[i]] - ticks[secs[i - 1]]
             for i in range(1, len(secs)) if secs[i] - secs[i - 1] == 1]
    if len(diffs) < 20:
        return None
    mu = sum(diffs) / len(diffs)
    return math.sqrt(sum((x - mu) ** 2 for x in diffs) / (len(diffs) - 1))


def fair_at(ticks, close_s, now_s, K, d, sigma):
    """pinrun.fair + IndexWS.partial, replayed. None if not computable."""
    lo = close_s - N_AVG
    hi0 = min(now_s, close_s - 1)
    if hi0 < lo:
        return None
    have = [s for s in range(lo, hi0 + 1) if s in ticks]
    if not have:
        return None
    hi = have[-1]
    want = hi - lo + 1
    got = {s: ticks[s] for s in have}
    if len(got) < want * 0.95:
        return None
    if len(got) == want:
        locked = sum(got.values())
    else:
        keys = sorted(got)
        locked = 0.0
        for s in range(lo, hi + 1):
            v = got.get(s)
            if v is None:
                i = bisect.bisect_left(keys, s)
                cand = [k for k in (keys[i] if i < len(keys) else None,
                                    keys[i - 1] if i > 0 else None)
                        if k is not None]
                v = got[min(cand, key=lambda k: (abs(k - s), k))]
            locked += v
    r = N_AVG - want
    spot = ticks[hi]                       # newest print held == idx.spot()
    Keff = eff_strike(K, d)
    mu = (locked + r * spot) / N_AVG
    if r <= 0:
        return 1.0 if mu >= Keff else 0.0
    sd = sigma * math.sqrt(var_factor(int(r), [1.0]))
    if sd <= 0:
        return 1.0 if mu >= Keff else 0.0
    return ND.cdf((mu - Keff) / sd)


def qualifies(f, y_ask_dc, y_ask_sz, n_ask_dc, n_ask_sz):
    """Return (want, price, size, edge) or None. Mirrors pinrun's scan block."""
    if f >= PIN:
        if y_ask_dc is None or y_ask_dc >= 1000:
            return None
        want, dc, sz = "yes", y_ask_dc, y_ask_sz
    elif f <= 1.0 - PIN:
        if n_ask_dc is None or n_ask_dc >= 1000:
            return None
        want, dc, sz = "no", n_ask_dc, n_ask_sz
    else:
        return None
    if sz is None or sz < MIN_LEVEL:
        return None
    price = dc / 1000.0
    e = net_edge(f, price, want)
    if e < EDGE_FLOOR:
        return None
    return want, price, sz, e


# ------------------------------------------------------------------ books --
class Book:
    __slots__ = ("yes", "no", "have_snap", "last_ms")

    def __init__(self):
        self.yes = {}
        self.no = {}
        self.have_snap = False
        self.last_ms = None


def best_of(d):
    b = None
    for k, v in d.items():
        if v > EPS and (b is None or k > b):
            b = k
    return (b, d[b]) if b is not None else (None, None)


# ---------------------------------------------------------------- parsing --
def parse_delta(line):
    try:
        i = line.index('"market_ticker":"') + 17
        j = line.index('"', i)
        tk = line[i:j]
        i = line.index('"price_dollars":"', j) + 17
        j = line.index('"', i)
        p = line[i:j]
        i = line.index('"delta_fp":"', j) + 12
        j = line.index('"', i)
        dl = line[i:j]
        i = line.index('"side":"', j) + 8
        j = line.index('"', i)
        sd = line[i:j]
        i = line.index('"ts_ms":', j) + 8
        j = line.index('}', i)
        ts = int(line[i:j])
        i = line.index('"seq":') + 6
        j = line.index(',', i)
        sq = int(line[i:j])
        return tk, sd, int(round(float(p) * 1000)), float(dl), ts, sq
    except Exception:
        return None


def gz_lines(fp):
    """Yield lines; a live/truncated gzip yields what parsed."""
    try:
        with gzip.open(fp, "rt") as fh:
            for line in fh:
                yield line
    except (EOFError, zlib.error, OSError):
        return


# ----------------------------------------------------------------- driver --
class Run:
    def __init__(self, mkts, report_lo, report_hi, log=print):
        self.MK = mkts               # tk -> dict(close,K,d,series)
        self.lo, self.hi = report_lo, report_hi
        self.books = defaultdict(Book)
        self.ticks = defaultdict(dict)          # iid -> {sec: value}
        self.armed = {}                         # tk -> list of events
        self.done = set()
        self.log = log
        self.stat = defaultdict(int)
        self.episodes = []
        self.closes_seen = set()
        self.sig_cache = {}
        sched = [(int((m["close"] - TAU_MAX) * 1000), tk)
                 for tk, m in mkts.items()]
        self.arm_sched = sorted(sched)
        self.arm_i = 0
        flush = [(int((m["close"] - TAU_MIN + 1) * 1000), tk)
                 for tk, m in mkts.items()]
        self.flush_sched = sorted(flush)
        self.flush_i = 0
        cand = [1 << 62]
        if self.arm_sched:
            cand.append(self.arm_sched[0][0])
        if self.flush_sched:
            cand.append(self.flush_sched[0][0])
        self.next_evt = min(cand)

    # ---- index ----
    def load_index_hour(self, stamp):
        fp = os.path.join(DATA, "cfbenchmarks_value", stamp + ".jsonl.gz")
        if not os.path.exists(fp):
            self.stat["index_hour_missing"] += 1
            return
        n = 0
        for line in gz_lines(fp):
            try:
                i = line.index('"index_id": "') + 13
                j = line.index('"', i)
                iid = line[i:j]
                i = line.index(TIMEQ, j) + len(TIMEQ)
                j = line.index(',', i)
                sec = int(line[i:j]) // 1000
                i = line.index(VALQ, j) + len(VALQ)
                j = line.index(BS, i)
                val = float(line[i:j])
            except Exception:
                try:
                    d = json.loads(line)
                    m = d.get("msg") or {}
                    iid = m.get("index_id")
                    dd = json.loads(m.get("data"))
                    sec = int(dd["time"]) // 1000
                    val = float(dd["value"])
                except Exception:
                    self.stat["bad_tick"] += 1
                    continue
            self.ticks[iid][sec] = val
            n += 1
        self.stat["index_ticks"] += n

    def prune_index(self, before_sec):
        for iid, d in self.ticks.items():
            for s in [s for s in d if s < before_sec]:
                del d[s]

    def sigma(self, iid, now_s):
        k = (iid, now_s)
        MISS = "miss"
        v = self.sig_cache.get(k, MISS)
        if v is MISS:
            v = sigma_at(self.ticks[iid], now_s)
            self.sig_cache[k] = v
        return v

    # ---- arming / flushing ----
    def advance(self, ts):
        while (self.arm_i < len(self.arm_sched)
               and self.arm_sched[self.arm_i][0] <= ts):
            _, tk = self.arm_sched[self.arm_i]
            self.arm_i += 1
            if tk in self.done:
                continue
            b = self.books.get(tk)
            if b is None or not b.have_snap:
                self.stat["arm_no_book"] += 1
                self.done.add(tk)
                continue
            ybd, ybs = best_of(b.yes)
            nbd, nbs = best_of(b.no)
            t0 = int((self.MK[tk]["close"] - TAU_MAX) * 1000)
            self.armed[tk] = [(t0, ybd, ybs, nbd, nbs, b.last_ms)]
            self.stat["armed"] += 1
        while (self.flush_i < len(self.flush_sched)
               and self.flush_sched[self.flush_i][0] <= ts):
            _, tk = self.flush_sched[self.flush_i]
            self.flush_i += 1
            if tk in self.armed:
                self.evaluate(tk, self.armed.pop(tk))
            self.done.add(tk)
        na = (self.arm_sched[self.arm_i][0]
              if self.arm_i < len(self.arm_sched) else (1 << 62))
        nf = (self.flush_sched[self.flush_i][0]
              if self.flush_i < len(self.flush_sched) else (1 << 62))
        self.next_evt = min(na, nf)

    def flush_all(self):
        for tk, ev in list(self.armed.items()):
            self.evaluate(tk, ev)
        self.armed.clear()

    # ---- the rule, on one market's window ----
    def evaluate(self, tk, events):
        """Walk the window event by event and cut out qualifying episodes.

        TWO VARIANTS, both recorded, because they differ by an artefact class
        that is large and must not be hidden:
          strict -- the LIVE rule, which includes pinrun's MAX_BOOK_AGE_MS.
                    A book with no message in 2 s is skipped live.
          loose  -- the same without that gate. The difference is dominated by
                    books frozen at their ~50c opening state that no delta ever
                    touched, which price as 40-50c "edges" and are not real.
        """
        m = self.MK[tk]
        C = int(m["close"])
        if not (self.lo <= C < self.hi):
            return
        iid = SERIES_TO_INDEX[m["series"]]
        ticks = self.ticks[iid]
        fairs = {}
        for now_s in range(C - TAU_MAX, C - TAU_MIN + 1):
            sp = None
            for back in range(0, MAX_INDEX_AGE_S + 1):
                if (now_s - back) in ticks:
                    sp = now_s - back
                    break
            if sp is None:
                continue
            sg = self.sigma(iid, now_s)
            if sg is None:          # pinrun skips on None only, not on 0.0
                continue
            f = fair_at(ticks, C, now_s, m["K"], m["d"], sg)
            if f is not None:
                fairs[now_s] = f
        if not fairs:
            self.stat["no_fair_window"] += 1
            return
        self.closes_seen.add(C)
        self.stat["window_evaluated"] += 1
        self.stat["decided_seconds"] += sum(
            1 for f in fairs.values() if f >= PIN or f <= 1 - PIN)

        w0 = (C - TAU_MAX) * 1000
        end_ms = (C - TAU_MIN + 1) * 1000
        pts = {}
        for (ts, ybd, ybs, nbd, nbs, lastms) in events:
            pts[ts] = (ybd, ybs, nbd, nbs, lastms)
            stale = (lastms or 0) + MAX_BOOK_AGE_MS + 1
            if w0 < stale < end_ms:
                pts.setdefault(stale, None)
        for now_s in range(C - TAU_MAX, C - TAU_MIN + 1):
            t = now_s * 1000
            pts.setdefault(t, None)
        tl = sorted(pts)
        cur = None
        runs = {"strict": None, "loose": None}
        for t in tl:
            v = pts[t]
            if v is not None:
                cur = v
            if cur is None:
                continue
            ybd, ybs, nbd, nbs, lastms = cur
            now_s = t // 1000
            f = fairs.get(now_s)
            q = None
            if f is not None:
                ya = (1000 - nbd) if nbd is not None else None
                na = (1000 - ybd) if ybd is not None else None
                q = qualifies(f, ya, nbs, na, ybs)
            age = (t - lastms) if lastms is not None else None
            fresh = age is not None and age <= MAX_BOOK_AGE_MS
            for mode in ("strict", "loose"):
                ok = q is not None and (fresh or mode == "loose")
                run = runs[mode]
                if ok:
                    want, price, sz, e = q
                    if run is None:
                        runs[mode] = dict(
                            tk=tk, series=m["series"], close=C, t0=t,
                            tau0=C - now_s, want=want, price0=price,
                            fair0=round(f, 6), edge0=e, size0=sz, emax=e,
                            smin=sz, smax=sz, age0=age, mode=mode,
                            ybid=(ybd / 1000.0 if ybd is not None else None),
                            nbid=(nbd / 1000.0 if nbd is not None else None))
                    else:
                        run["emax"] = max(run["emax"], e)
                        run["smin"] = min(run["smin"], sz)
                        run["smax"] = max(run["smax"], sz)
                elif run is not None:
                    run["dur"] = t - run["t0"]
                    run["censored"] = False
                    self.episodes.append(run)
                    runs[mode] = None
        for mode in ("strict", "loose"):
            run = runs[mode]
            if run is not None:
                run["dur"] = end_ms - run["t0"]
                run["censored"] = True
                self.episodes.append(run)

    # ---- the tape ----
    def do_hour(self, stamp):
        t0 = time.time()
        self.load_index_hour(stamp)
        snaps = []
        sp = os.path.join(DATA, "orderbook_snapshot", stamp + ".jsonl.gz")
        if os.path.exists(sp):
            for line in gz_lines(sp):
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                snaps.append((d.get("seq") or 0, d))
        snaps.sort(key=lambda x: x[0])
        si = 0
        dp = os.path.join(DATA, "orderbook_delta", stamp + ".jsonl.gz")
        if not os.path.exists(dp):
            self.stat["delta_hour_missing"] += 1
            return
        n = bad = 0
        MK = self.MK
        books = self.books
        armed = self.armed
        for line in gz_lines(dp):
            r = parse_delta(line)
            if r is None:
                bad += 1
                continue
            tk, side, dc, dl, ts, sq = r
            while si < len(snaps) and snaps[si][0] < sq:
                self.apply_snap(snaps[si][1])
                si += 1
            n += 1
            if tk not in MK:
                continue
            b = books[tk]
            b.last_ms = ts
            d = b.yes if side == "yes" else b.no
            nv = d.get(dc, 0.0) + dl
            if nv <= EPS:
                d.pop(dc, None)
            else:
                d[dc] = nv
            if ts >= self.next_evt:
                self.advance(ts)
            if tk in armed:
                ybd, ybs = best_of(b.yes)
                nbd, nbs = best_of(b.no)
                armed[tk].append((ts, ybd, ybs, nbd, nbs, ts))
        while si < len(snaps):
            self.apply_snap(snaps[si][1])
            si += 1
        self.stat["deltas"] += n
        self.stat["unparsed"] += bad
        self.log("    %s: %s deltas, %d snaps, %d unparsed, %.0fs, eps=%d"
                 % (stamp, format(n, ","), len(snaps), bad,
                    time.time() - t0, len(self.episodes)))

    def apply_snap(self, d):
        m = d.get("msg") or {}
        tk = m.get("market_ticker")
        if tk is None:
            return
        b = self.books[tk]
        b.yes, b.no, b.have_snap = {}, {}, True
        rx = d.get("_rx_ms")
        if rx is not None:
            b.last_ms = int(rx)
        for key, tgt in (("yes_dollars_fp", b.yes), ("no_dollars_fp", b.no)):
            for pair in (m.get(key) or []):
                try:
                    tgt[int(round(float(pair[0]) * 1000))] = float(pair[1])
                except Exception:
                    pass
        self.stat["snapshots"] += 1

    def sweep_done(self, now_ms_):
        drop = [tk for tk in self.books
                if tk in self.MK
                and self.MK[tk]["close"] * 1000 + 60000 < now_ms_]
        for tk in drop:
            del self.books[tk]


# ------------------------------------------------------------------ tests --
def selftest():
    print("SELF-TEST -- oppcount")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    ck(abs(billed_fee(0.95, 1) - 0.0034) < 1e-12,
       "billed fee at p=0.95 is $0.0034 (%s)" % billed_fee(0.95, 1))
    e = net_edge(0.995, 0.99, "yes")
    ck(abs(e - (0.005 - billed_fee(0.99, 1))) < 1e-12,
       "net edge subtracts the fee (%.3fc)" % (100 * e))

    C = 1_000_000
    flat = {s: 100.0 for s in range(C - 400, C)}
    f_hi = fair_at(flat, C, C - 10, 90.0, 2, 0.5)
    f_lo = fair_at(flat, C, C - 10, 110.0, 2, 0.5)
    ck(f_hi > 0.999 and f_lo < 0.001,
       "flat index far from strike prices 1/0 (%.4f, %.4f)" % (f_hi, f_lo))

    f7 = fair_at(flat, C, C - 10, 100.0000004, 7, 1e-9)
    f2 = fair_at(flat, C, C - 10, 100.0000004, 2, 1e-9)
    ck(f7 < 0.5 < f2,
       "round_digits changes the call at the band edge (d=7 %.3f, d=2 %.3f)"
       % (f7, f2))

    # END TO END, PLANTED: fair == 1, a cheap YES ask (a NO bid at 0.10)
    # resting for exactly 4.0 s inside the tau window.
    MK = {"T": {"close": C, "K": 90.0, "d": 2, "series": "KXBTC15M"}}
    r = Run(MK, C - 100, C + 100, log=lambda *a: None)
    r.ticks["BRTI"] = dict(flat)
    ev = [((C - 20) * 1000, None, None, None, None, (C - 30) * 1000),
          ((C - 15) * 1000, None, None, 100, 25.0, (C - 15) * 1000),
          ((C - 11) * 1000, None, None, None, None, (C - 11) * 1000)]
    r.evaluate("T", ev)
    loose = [e for e in r.episodes if e["mode"] == "loose"]
    strict = [e for e in r.episodes if e["mode"] == "strict"]
    ck(len(loose) == 1 and len(strict) == 1,
       "planted opportunity found once in each mode (%d loose, %d strict)"
       % (len(loose), len(strict)))
    if loose:
        ep = loose[0]
        ck(ep["dur"] == 4000,
           "loose duration is the 4000 ms it was planted for (%s)" % ep["dur"])
        ck(strict and strict[0]["dur"] == MAX_BOOK_AGE_MS + 1,
           "strict duration is capped by the 2 s book-age gate (%s)"
           % (strict[0]["dur"] if strict else None))
        want_e = 1.0 - 0.90 - billed_fee(0.90, 1)
        ck(abs(ep["edge0"] - want_e) < 1e-9,
           "edge is 1 - 0.90 - fee = %.2fc (got %.2fc)"
           % (100 * want_e, 100 * ep["edge0"]))
        ck(ep["want"] == "yes" and ep["size0"] == 25.0,
           "side and resting size read off the opposing bid (%s, %s)"
           % (ep["want"], ep["size0"]))

    r2 = Run(MK, C - 100, C + 100, log=lambda *a: None)
    r2.ticks["BRTI"] = dict(flat)
    r2.evaluate("T", [((C - 20) * 1000, None, None, None, None,
                       (C - 20) * 1000),
                      ((C - 15) * 1000, None, None, 5, 25.0,
                       (C - 15) * 1000)])
    ck(len(r2.episodes) == 0,
       "a fairly-priced ask yields nothing (%d)" % len(r2.episodes))

    # A BOOK NOBODY HAS TOUCHED FOR 10 s IS NOT AN OPPORTUNITY LIVE. This is
    # the artefact class that dominated the first run: a book frozen at its
    # ~50c opening state prices as a 40-50c "edge" forever.
    r2b = Run(MK, C - 100, C + 100, log=lambda *a: None)
    r2b.ticks["BRTI"] = dict(flat)
    r2b.evaluate("T", [((C - 20) * 1000, None, None, 100, 25.0,
                        (C - 45) * 1000)])
    ck(sum(1 for e in r2b.episodes if e["mode"] == "strict") == 0
       and sum(1 for e in r2b.episodes if e["mode"] == "loose") == 1,
       "a 25 s stale book counts loose but NOT strict (%s)"
       % [e["mode"] for e in r2b.episodes])

    r3 = Run(MK, C - 100, C + 100, log=lambda *a: None)
    r3.ticks["BRTI"] = dict(flat)
    r3.evaluate("T", [((C - 20) * 1000, None, None, None, None,
                       (C - 20) * 1000),
                      ((C - 15) * 1000, None, None, 100, 0.4,
                       (C - 15) * 1000)])
    ck(len(r3.episodes) == 0,
       "a 0.4-contract level is not a fill (%d)" % len(r3.episodes))

    r4 = Run(MK, C - 100, C + 100, log=lambda *a: None)
    r4.ticks["BRTI"] = dict(flat)
    r4.evaluate("T", [((C - 20) * 1000, None, None, None, None,
                       (C - 20) * 1000),
                      ((C - 2) * 1000, None, None, 100, 25.0,
                       (C - 2) * 1000)])
    ck(len(r4.episodes) == 0,
       "an ask that only appears at tau<3 is not counted (%d)"
       % len(r4.episodes))

    r5 = Run({"T": {"close": C, "K": 110.0, "d": 2, "series": "KXBTC15M"}},
             C - 100, C + 100, log=lambda *a: None)
    r5.ticks["BRTI"] = dict(flat)
    r5.evaluate("T", [((C - 20) * 1000, None, None, None, None,
                       (C - 20) * 1000),
                      ((C - 15) * 1000, 100, 7.0, None, None,
                       (C - 15) * 1000)])
    ck(len([e for e in r5.episodes if e["mode"] == "loose"]) == 1
       and r5.episodes[0]["want"] == "no",
       "the NO side fires symmetrically (%s)"
       % [x["want"] for x in r5.episodes])

    line = ('{"type":"orderbook_delta","sid":4,"seq":19639244,"msg":'
            '{"market_ticker":"KXBTC15M-26SEP010800-00","market_id":"x",'
            '"price_dollars":"0.9790","delta_fp":"17.00","side":"no",'
            '"ts":"2026-09-01T11:59:59.993352Z","ts_ms":1788263999993},'
            '"_rx_ms":1788264000020}')
    got = parse_delta(line)
    ck(got == ("KXBTC15M-26SEP010800-00", "no", 979, 17.0,
               1788263999993, 19639244), "delta parser %s" % (got,))

    print("SELF-TEST " + ("PASSED" if not fails
                          else "*** FAILED (%d) ***" % len(fails)))
    return 0 if not fails else 1


# ------------------------------------------------------------------- main --
def hours_between(a, b):
    out = []
    t = calendar.timegm(time.strptime(a, "%Y%m%dT%H"))
    e = calendar.timegm(time.strptime(b, "%Y%m%dT%H"))
    while t <= e:
        out.append(time.strftime("%Y%m%dT%H", time.gmtime(t)))
        t += 3600
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--day", help="YYYYMMDD to report on")
    ap.add_argument("--warm", type=int, default=2, help="warm-up hours")
    ap.add_argument("--out", default=r"C:\kals-repo\results\opp")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(selftest())
    if selftest() != 0:
        raise SystemExit("self-test failed; refusing to touch real data")

    allm = json.load(open(MKTS))
    d0 = calendar.timegm(time.strptime(a.day, "%Y%m%d"))
    lo, hi = d0, d0 + 86400
    MK = {tk: m for tk, m in allm.items()
          if lo - 7200 <= m["close"] < hi + 3600
          and m["series"] in SERIES_TO_INDEX}
    print("[%s] %d markets in range" % (a.day, len(MK)))
    first = time.strftime("%Y%m%dT%H", time.gmtime(lo - 3600 - a.warm * 3600))
    last = time.strftime("%Y%m%dT%H", time.gmtime(hi - 3600))
    hrs = [h for h in hours_between(first, last)
           if os.path.exists(os.path.join(DATA, "orderbook_delta",
                                          h + ".jsonl.gz"))]
    run = Run(MK, lo, hi)
    for h in hrs:
        run.do_hour(h)
        hs = calendar.timegm(time.strptime(h, "%Y%m%dT%H"))
        run.prune_index(hs - 3600)
        run.sweep_done(hs * 1000)
    run.flush_all()
    out = dict(day=a.day, hours=hrs, stat=dict(run.stat),
               closes_evaluated=sorted(run.closes_seen),
               episodes=run.episodes)
    fp = os.path.join(a.out, "ep_%s.json" % a.day)
    json.dump(out, open(fp, "w"))
    print("[%s] DONE hours=%d closes=%d episodes=%d stat=%s"
          % (a.day, len(hrs), len(run.closes_seen), len(run.episodes),
             dict(run.stat)))


if __name__ == "__main__":
    main()
