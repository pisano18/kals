#!/usr/bin/env python3
# VERSION: 2026-09-24-mm1
"""
makersim.py -- a MEMORY-BOUNDED, streaming queue simulation of the two-sided
1-contract maker quote at the touch (10c-90c) on the up/down series, driven by
the RAW tape one hour-file at a time.

    python research/makersim.py --selftest
    python research/makersim.py --data C:\\kals\\kalshi_data --out <dir> \\
                                --from 20260918T00 --to 20260923T23
    python research/makersim.py --report <dir>          # tables from the hour files

WHAT IS BEING DECIDED

IDEAS_2026-09-24.md sec.1 item 3: rest 1 contract at the best bid and 1 at
the best ask of every KXBTC15M / KXETH15M / KXSOL15M / KXXRP15M market while
that side's touch sits inside 10c-90c, re-post at the BACK of the queue
whenever the touch moves, hold every fill to settlement. Makers pay no fee on
these series (fee_type `quadratic`, verified 2026-09-06).

The 2026-09-06 `queuesim.py` answered this on a ONE-SECOND cached book
(flow_cache) with a pro-rata cancel guess, no latency, and an oldest-tape
sample; it said ~44,000 fills/day and +0.8c a fill. This file re-asks the
question from the millisecond tape, with the exchange's own timestamps, an
explicit reaction latency, and the pick-off that latency causes.

WHY IT STREAMS

The money bot shares the laptop and the shell has been killed for low memory
three times today. One hour of orderbook_delta is ~140 MB gzipped and ~3.8M
lines. Nothing here holds more than: the current book of the handful of open
markets, our order state, one hour of trades for four series (~50k tuples),
and the fills of the markets still open. The whole-tape quote loader in
replay.py is never imported (the self-test scans the import lines). RSS is printed every 10 minutes and the run aborts under 1.2 GB
free.

THE TAPE FACTS THIS RESTS ON (measured 2026-09-24 on 20260920T14)

* A trade print and the negative orderbook_delta that removes the resting
  size it consumed carry the SAME exchange `ts_ms` -- 21,545 of 21,545
  trades on KXXRP15M+KXSOL15M matched at offset 0 ms. So a trade is merged
  BEFORE the deltas of its own millisecond, and its consumption is netted
  against the next negative delta at that level; what is left of that delta
  is a cancel.
* The trade channel reaches the collector 4-6 s late (`_rx_ms` - `ts_ms`),
  the delta channel ~26 ms late. Merging on `_rx_ms` would put every trade
  after the deltas of the following four seconds. Everything is merged on
  `ts_ms`; snapshots (which carry no `ts_ms`) are ordered against deltas by
  `_rx_ms`, which the collector writes in receive order on the same `sid`.
* Prints at the same ms and taker side are one taker walking the queue
  (per resting order). `delta_fp` and `count_fp` are fractional.
* `market_lifecycle_v2` carries `event_type: determined` with `result`
  yes/no for every market. `fulltape/markets.json` stops at 2026-09-18, so
  lifecycle is the settlement source here. It is the exchange's own word,
  not a replay.

THE QUEUE MODEL -- every rule is exercised by the self-test

We hold at most one live order per side per variant, 1.00 contract. A
"variant" is (queue model, reaction latency L ms). The book is reconstructed
from snapshot + deltas; our own contract is NOT added to it (assumption A1).

1. POST. When a side's touch (best price on that side, in that side's own
   price units) is inside the band and the inventory cap allows it, we post
   at the touch. The order LANDS at t + L and joins the BACK: at landing,
   `ahead` = the displayed size at that price.
2. RE-POST. Decisions are taken at the END of each exchange millisecond (a
   sweep is atomic; nobody reacts inside it). If the touch differs from our
   order's price, the order is cancelled and a new one is posted (lands at
   t + L). A cancel needs the order id, which arrives with the ack one
   round-trip after posting, so the old order dies at max(t + L, land_at +
   L). Between then and now it is STILL LIVE at its old price with its
   queue position -- that is the pick-off, and it is deliberately kept.
   Orders in flight count as exposure against the inventory cap.
3. FILL BY QUEUE. A print of q at our price fills min(rem, max(0, q -
   ahead)); ahead falls by q.
4. FILL BY WALK. A print at a price WORSE for the taker than ours, while our
   level shows no size in front of us (displayed minus already-printed
   consumption == 0), means the taker went past us: fill min(rem, q). If
   the level still shows size, the credit is DEFERRED: if a delta in the
   same millisecond empties that level (a cancel the tape lists after the
   print, since trades are merged first) it is credited then; otherwise it
   is counted as an anomaly and never credited.
5. FILL BY CROSS. A positive delta arriving on the OPPOSITE side at a price
   that crosses our live order (yes_price + no_price >= 100c) is an order
   that would have matched us before resting; fill min(rem, delta), again
   only when nothing shows in front of us.
6. CANCELS. A negative delta beyond the netted trade consumption is a cancel
   and the tape cannot say whether it was in front of us:
       last          ahead is ALWAYS the displayed size: every arrival is in
                     front of us, every cancel comes off the top. Fills only
                     by WALK/CROSS or a print larger than the level. This is
                     the requested "we were LAST" bound.
       fifo_behind   arrivals after us are behind us; cancels are assumed
                     to come from behind (ahead only capped at displayed)
       fifo_prorata  cancels spread over the level in proportion
       fifo_front    cancels come from in front of us
   ahead is capped at the displayed size under every model.
7. INVENTORY. Net yes position per market per variant is capped at +-CAP;
   a side at its cap is not quoted. Fills accumulate to settlement.
8. AFTER A FULL FILL the side is re-posted at the touch, landing at t + L.
   A partial fill keeps its remainder where it is (true FIFO).

WHAT THE TAPE CANNOT VERIFY (assumptions, all stated in the report)
   A1 our contract does not change anyone else's behaviour or the touch;
   A2 L is a guess (0 / 300 / 1000 ms are run); the exchange's own matching
      latency and REST round-trip are not on the tape;
   A3 the pin bot never lifts our own ask (live: self_trade_prevention);
   A4 a taker who cleared a level and did NOT walk or rest a remainder is
      assumed to have wanted exactly the level (no fill) -- conservative;
   A5 the collector subscribes ~2 minutes after each market opens; those
      minutes are not simulated.

THE SELF-TEST IS THE DELIVERABLE. It writes a synthetic tape in the real
file format, runs the whole streaming path on it, and checks the fill of
every variant against a hand-computed closed form; a queue-ignoring mutant
and a band-ignoring mutant must both be REJECTED; the money check plants an
outcome and recovers it exactly, and a sign-scrambled companion must sit
inside its own MDE.

NOTHING HERE PLACES AN ORDER. NOTHING HERE WRITES OUTSIDE --out.
"""

import argparse
import ctypes
import glob
import gzip
import json
import math
import os
import random
import sys
import tempfile
import time
import zlib
from collections import defaultdict
from statistics import mean, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tdist import crit as _tcrit                            # noqa: E402

SERIES = ("KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M")
BAND = (100, 900)              # tenths of a cent, inclusive, yes price of OUR order
MODELS = ("last", "fifo_behind", "fifo_prorata", "fifo_front")
LATENCIES = (0, 300, 1000)     # ms
VARIANTS = tuple((m, L) for L in LATENCIES for m in MODELS)
CAP = 10                       # net contracts per market per variant
PEND_TTL = 2000                # ms a print's consumption waits for its delta
GAP_MS = 60000                 # a market silent this long is dropped
YES, NO = 0, 1
EPS = 1e-6
RSS_LIMIT_MB = 400
FREE_ABORT_MB = 1200
TAU_BANDS = ((600, 10 ** 9), (300, 600), (120, 300), (60, 120), (30, 60),
             (10, 30), (0, 10))
PRICE_BANDS = ((100, 300), (300, 500), (500, 700), (700, 900))


# ===========================================================================
# memory -- stdlib only, Windows first
# ===========================================================================
def rss_mb():
    try:
        if sys.platform == "win32":
            class PMC(ctypes.Structure):
                _fields_ = [("cb", ctypes.c_uint32),
                            ("PageFaultCount", ctypes.c_uint32),
                            ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]
            pmc = PMC()
            pmc.cb = ctypes.sizeof(PMC)
            k32 = ctypes.windll.kernel32
            h = k32.GetCurrentProcess()
            fn = getattr(k32, "K32GetProcessMemoryInfo", None)
            if fn is None:
                fn = ctypes.windll.psapi.GetProcessMemoryInfo
            fn.restype = ctypes.c_int
            fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
            if not fn(h, ctypes.byref(pmc), pmc.cb):
                return -1.0
            return pmc.WorkingSetSize / 1048576.0
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except Exception:
        return -1.0


def free_ram_mb():
    try:
        if sys.platform == "win32":
            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_uint32),
                            ("dwMemoryLoad", ctypes.c_uint32),
                            ("ullTotalPhys", ctypes.c_uint64),
                            ("ullAvailPhys", ctypes.c_uint64),
                            ("ullTotalPageFile", ctypes.c_uint64),
                            ("ullAvailPageFile", ctypes.c_uint64),
                            ("ullTotalVirtual", ctypes.c_uint64),
                            ("ullAvailVirtual", ctypes.c_uint64),
                            ("ullAvailExtendedVirtual", ctypes.c_uint64)]
            ms = MS()
            ms.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
            return ms.ullAvailPhys / 1048576.0
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable"):
                    return int(line.split()[1]) / 1024.0
    except Exception:
        pass
    return -1.0


def lower_priority():
    try:
        if sys.platform == "win32":
            h = ctypes.windll.kernel32.GetCurrentProcess()
            ctypes.windll.kernel32.SetPriorityClass(h, 0x4000)   # BELOW_NORMAL
        else:
            os.nice(10)
    except Exception:
        pass


# ===========================================================================
# gzip streaming that survives the collector's broken members
# ===========================================================================
def gz_lines(fp):
    """Yield bytes lines. A truncated or concatenated-after-crash member costs
    what it costs, not the whole file (see gzsalvage.py for why)."""
    try:
        with gzip.open(fp, "rb") as f:
            for line in f:
                yield line
    except (EOFError, OSError, zlib.error):
        return


def px(s):
    """'0.7800' -> 780 (tenths of a cent). Never inferred from magnitude."""
    return int(float(s) * 1000.0 + 0.5)


# ===========================================================================
# the simulator
# ===========================================================================
class Order(object):
    __slots__ = ("price", "rem", "ahead", "ahead0", "land_at", "die_at",
                 "landed")

    def __init__(self, price, land_at):
        self.price = price
        self.rem = 1.0
        self.ahead = 0.0
        self.ahead0 = -1.0
        self.land_at = land_at
        self.die_at = None
        self.landed = False


class Market(object):
    __slots__ = ("tk", "series", "books", "best", "pending", "orders", "inv",
                 "last_ts", "close_ms", "dirty", "fills", "first_ts",
                 "opened", "nsnap", "posts_out_of_band", "n_events",
                 "walk_pending", "touch0")

    def __init__(self, tk, nvar):
        self.tk = tk
        self.series = tk.split("-")[0]
        self.books = ({}, {})
        self.best = [None, None]
        self.pending = {}
        self.orders = [[[], []] for _ in range(nvar)]
        self.inv = [0.0] * nvar
        self.last_ts = None
        self.close_ms = None
        self.dirty = True
        self.fills = []
        self.first_ts = None
        self.opened = False
        self.nsnap = 0
        self.posts_out_of_band = 0
        self.n_events = 0
        self.walk_pending = []       # [s, price, ts, v, order, q] this ms
        self.touch0 = [None, None]   # the touch at the START of this ms


class Sim(object):
    def __init__(self, variants=VARIANTS, cap=CAP, band=BAND,
                 ignore_queue=False, no_band=False, results=None):
        self.variants = list(variants)
        self.cap = cap
        self.band = band
        self.ignore_queue = ignore_queue      # the mutant the self-test rejects
        self.no_band = no_band                # the other mutant
        self.results = results or {}
        self.markets = {}
        self.stat = defaultdict(int)
        self.closed = []                      # (market records) flushed per hour
        self.ahead0_samples = []

    # -- book helpers ------------------------------------------------------
    @staticmethod
    def _recompute_best(m, s):
        b = m.books[s]
        best = None
        for p, sz in b.items():
            if sz > EPS and (best is None or p > best):
                best = p
        m.best[s] = best

    def _deff(self, m, s, p, ts):
        d = m.books[s].get(p, 0.0)
        pe = m.pending.get((s, p))
        if pe is not None and ts - pe[1] <= PEND_TTL:
            d -= pe[0]
        return d if d > 0.0 else 0.0

    @staticmethod
    def _live(o, ts):
        return o.landed and (o.die_at is None or o.die_at > ts)

    def _cap_ok(self, inv, s):
        return (inv < self.cap - EPS) if s == YES else (inv > -self.cap + EPS)

    # -- lifecycle at the end of a millisecond ------------------------------
    def _advance(self, m, ts):
        """Bring market m to time ts. Returns False if the market closed."""
        if m.close_ms is not None and ts >= m.close_ms:
            self._close_market(m, "close")
            return False
        if m.last_ts is None:
            m.last_ts = ts
            m.first_ts = ts
            m.touch0 = [m.best[YES], m.best[NO]]
            if m.close_ms is None:
                m.close_ms = (ts // 900000 + 1) * 900000
            return True
        if ts <= m.last_ts:
            return True
        if ts - m.last_ts > GAP_MS:
            self._close_market(m, "gap")
            return False
        base = m.last_ts
        if m.walk_pending:
            self.stat["anom_walk_past_nonempty_uncredited"] += \
                len(m.walk_pending)
            m.walk_pending = []
        if m.dirty:
            for v, (model, L) in enumerate(self.variants):
                for s in (YES, NO):
                    touch = m.best[s]
                    lst = m.orders[v][s]
                    target = None
                    for o in lst:
                        if o.die_at is None:
                            target = o.price
                    desired = None
                    if touch is not None and (self.no_band or
                                              (self.band[0] <= touch
                                               <= self.band[1])):
                        if target == touch:
                            desired = touch
                        else:
                            # everything on this side is about to be
                            # cancelled, and until those cancels land it
                            # is still exposure: count it against the cap
                            exp = sum(o.rem for o in lst)
                            inv = m.inv[v] + (exp if s == YES else -exp)
                            if self._cap_ok(inv, s):
                                desired = touch
                    if desired != target:
                        for o in lst:
                            if o.die_at is None:
                                # a cancel needs the order's id, which only
                                # arrives with the ack one round-trip after
                                # posting: nothing dies before land_at + L
                                o.die_at = max(base + L, o.land_at + L)
                        if desired is not None:
                            lst.append(Order(desired, base + L))
                            self.stat["posts"] += 1
                            if not (self.band[0] <= desired <= self.band[1]):
                                m.posts_out_of_band += 1
            m.dirty = False
        for v, (model, L) in enumerate(self.variants):
            for s in (YES, NO):
                lst = m.orders[v][s]
                if not lst:
                    continue
                keep = []
                for o in lst:
                    if o.die_at is not None and o.die_at <= ts:
                        continue
                    if not o.landed and o.land_at <= ts:
                        o.landed = True
                        o.ahead = self._deff(m, s, o.price, ts)
                        o.ahead0 = o.ahead
                        if v == 0 and len(self.ahead0_samples) < 200000:
                            self.ahead0_samples.append(o.ahead)
                    keep.append(o)
                m.orders[v][s] = keep
        m.last_ts = ts
        m.touch0 = [m.best[YES], m.best[NO]]
        return True

    # -- fills ---------------------------------------------------------------
    def _fill(self, m, v, s, o, f, ts, mech):
        o.rem -= f
        if s == YES:
            m.inv[v] += f
        else:
            m.inv[v] -= f
        # stale: our price was not this side's touch when the ms began, so
        # the fill is a pick-off during the cancel/re-post round trip
        stale = 1 if o.price != m.touch0[s] else 0
        m.fills.append((v, s, o.price, round(f, 6), ts, mech, stale,
                        round(o.ahead0, 3), o.land_at))
        self.stat["fills"] += 1
        m.dirty = True

    def _prune(self, m, v, s):
        lst = m.orders[v][s]
        if any(o.rem <= EPS for o in lst):
            m.orders[v][s] = [o for o in lst if o.rem > EPS]

    # -- events --------------------------------------------------------------
    def on_snapshot(self, tk, yes_levels, no_levels, rx):
        m = self.markets.get(tk)
        if not yes_levels and not no_levels:
            if m is not None:
                self._close_market(m, "empty_snapshot")
            self.stat["snap_empty"] += 1
            return
        if m is None:
            m = self.markets[tk] = Market(tk, len(self.variants))
            m.close_ms = self.results.get(tk, (None, None))[1]
        else:
            self.stat["resnapshot"] += 1
        m.nsnap += 1
        m.opened = True
        m.books = ({}, {})
        for p, sz in yes_levels:
            m.books[YES][px(p)] = float(sz)
        for p, sz in no_levels:
            m.books[NO][px(p)] = float(sz)
        self._recompute_best(m, YES)
        self._recompute_best(m, NO)
        m.pending.clear()
        m.dirty = True
        self.stat["snap"] += 1

    def on_delta(self, tk, side, p, dq, ts):
        m = self.markets.get(tk)
        if m is None or not m.opened:
            self.stat["delta_before_snapshot"] += 1
            return
        if not self._advance(m, ts):
            return
        m.n_events += 1
        s = YES if side == "yes" else NO
        book = m.books[s]
        d0 = book.get(p, 0.0)
        if dq < 0.0:
            c = -dq
            used = 0.0
            pe = m.pending.get((s, p))
            if pe is not None:
                if ts - pe[1] <= PEND_TTL:
                    used = min(c, pe[0])
                    pe[0] -= used
                    if pe[0] <= EPS:
                        del m.pending[(s, p)]
                else:
                    del m.pending[(s, p)]
            cancel = c - used
            d_after = d0 - c
            if d_after < -EPS:
                self.stat["anom_level_negative"] += 1
            if d_after < 0.0:
                d_after = 0.0
            if cancel > EPS:
                self.stat["cancel_events"] += 1
                d_bc = d0 - used
                if d_bc < 0.0:
                    d_bc = 0.0
                for v, (model, L) in enumerate(self.variants):
                    if model == "last":
                        continue
                    for o in m.orders[v][s]:
                        if not o.landed or o.price != p:
                            continue
                        if model == "fifo_behind":
                            pass
                        elif model == "fifo_prorata":
                            o.ahead = (o.ahead * d_after / d_bc) if d_bc > EPS \
                                else 0.0
                        else:                       # fifo_front
                            o.ahead = o.ahead - cancel
                            if o.ahead < 0.0:
                                o.ahead = 0.0
                        if o.ahead > d_after:
                            o.ahead = d_after
            if d_after > EPS:
                book[p] = d_after
            else:
                book.pop(p, None)
                if m.best[s] == p:
                    self._recompute_best(m, s)
                    m.dirty = True
                if m.walk_pending:
                    # a taker printed PAST this level earlier in the same
                    # ms while it still showed size; the size has now gone
                    # in the same ms (a cancel we saw after the print), so
                    # the level was in truth empty when the taker walked:
                    # credit the walk now
                    keep = []
                    for w in m.walk_pending:
                        ws, wp, wts, wv, wo, wq = w
                        if ws == s and wp == p and wts == ts:
                            if wo.rem > EPS and self._live(wo, ts):
                                f = min(wo.rem, wq)
                                self._fill(m, wv, ws, wo, f, ts, "walk")
                                self.stat["walk_deferred"] += 1
                                self._prune(m, wv, ws)
                        else:
                            keep.append(w)
                    m.walk_pending = keep
        else:
            book[p] = d0 + dq
            if m.best[s] is None or p > m.best[s]:
                m.best[s] = p
                m.dirty = True
            # an arrival that crosses our live order on the other side
            s2 = 1 - s
            lim = 1000 - p
            for v, (model, L) in enumerate(self.variants):
                lst = m.orders[v][s2]
                if not lst:
                    continue
                hit = False
                for o in lst:
                    if o.price >= lim and self._live(o, ts):
                        if self._deff(m, s2, o.price, ts) <= EPS:
                            f = min(o.rem, dq)
                            if f > EPS:
                                self._fill(m, v, s2, o, f, ts, "cross")
                                hit = True
                        else:
                            self.stat["anom_cross_nonempty"] += 1
                if hit:
                    self._prune(m, v, s2)

    def on_trade(self, tk, taker_side, yes_t, no_t, q, ts):
        m = self.markets.get(tk)
        if m is None or not m.opened:
            self.stat["trade_no_market"] += 1
            return
        if not self._advance(m, ts):
            return
        m.n_events += 1
        if taker_side == "yes":
            s, p = NO, no_t
        else:
            s, p = YES, yes_t
        deff = self._deff(m, s, p, ts)
        if q > deff + EPS:
            self.stat["anom_print_exceeds_level"] += 1
            q_eff = deff
        else:
            q_eff = q
        self.stat["prints"] += 1
        self.stat["print_qty"] += q
        for v, (model, L) in enumerate(self.variants):
            lst = m.orders[v][s]
            if not lst:
                continue
            hit = False
            q_walk = q
            for o in sorted(lst, key=lambda x: -x.price):
                if not self._live(o, ts):
                    continue
                if o.price == p:
                    if self.ignore_queue:
                        f = min(o.rem, q)
                    else:
                        ahead = deff if model == "last" else o.ahead
                        f = q_eff - ahead
                        if f > o.rem:
                            f = o.rem
                        if model != "last":
                            o.ahead -= q_eff
                            if o.ahead < 0.0:
                                o.ahead = 0.0
                    if f > EPS:
                        self._fill(m, v, s, o, f, ts, "queue")
                        hit = True
                elif o.price > p:
                    if self._deff(m, s, o.price, ts) <= EPS:
                        f = min(o.rem, q_walk)
                        if f > EPS:
                            self._fill(m, v, s, o, f, ts, "walk")
                            q_walk -= f
                            hit = True
                    else:
                        self.stat["anom_walk_past_nonempty"] += 1
                        m.walk_pending.append([s, o.price, ts, v, o,
                                               min(o.rem, q_walk)])
            if hit:
                self._prune(m, v, s)
        pe = m.pending.get((s, p))
        if pe is not None and ts - pe[1] <= PEND_TTL:
            pe[0] += q
            pe[1] = ts
        else:
            m.pending[(s, p)] = [q, ts]

    def _close_market(self, m, reason):
        self.stat["closed_" + reason] += 1
        rec = {"tk": m.tk, "ser": m.series, "close": m.close_ms,
               "first_ts": m.first_ts, "reason": reason,
               "events": m.n_events, "oob_posts": m.posts_out_of_band,
               "fills": [f for f in m.fills
                         if m.close_ms is None or f[4] < m.close_ms],
               "inv": [round(x, 6) for x in m.inv]}
        self.stat["fills_after_close"] += len(m.fills) - len(rec["fills"])
        self.closed.append(rec)
        del self.markets[m.tk]

    def close_all(self, reason="end"):
        for tk in list(self.markets):
            self._close_market(self.markets[tk], reason)


# ===========================================================================
# the streaming driver
# ===========================================================================
def hour_list(h0, h1):
    """'20260918T00' .. '20260923T23' inclusive, every hour."""
    import datetime as _dt
    a = _dt.datetime.strptime(h0, "%Y%m%dT%H")
    b = _dt.datetime.strptime(h1, "%Y%m%dT%H")
    out = []
    while a <= b:
        out.append(a.strftime("%Y%m%dT%H"))
        a += _dt.timedelta(hours=1)
    return out


def next_hour(h):
    import datetime as _dt
    return (_dt.datetime.strptime(h, "%Y%m%dT%H")
            + _dt.timedelta(hours=1)).strftime("%Y%m%dT%H")


def load_results(data_dir, hours, series=SERIES):
    """ticker -> (1.0/0.0, close_ms) from market_lifecycle_v2 `determined`."""
    out = {}
    pref = tuple(s + "-" for s in series)
    want = set(hours)
    if hours:
        want.add(next_hour(hours[-1]))
    for fp in sorted(glob.glob(os.path.join(data_dir, "market_lifecycle_v2",
                                            "*.jsonl.gz"))):
        if os.path.basename(fp)[:11] not in want:
            continue
        for line in gz_lines(fp):
            if b'"determined"' not in line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            msg = d.get("msg") or {}
            tk = msg.get("market_ticker") or ""
            if not tk.startswith(pref):
                continue
            r = str(msg.get("result", "")).lower()
            if r not in ("yes", "no"):
                continue
            dts = msg.get("determination_ts")
            close_ms = int(dts) * 1000 if isinstance(dts, (int, float)) \
                else None
            out[tk] = (1.0 if r == "yes" else 0.0, close_ms)
    return out


def load_snapshots(fp, pref_b):
    out = []
    for line in gz_lines(fp):
        if not any(k in line for k in pref_b):
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        msg = d.get("msg") or {}
        out.append((d.get("_rx_ms", 0), msg.get("market_ticker"),
                    msg.get("yes_dollars_fp") or [],
                    msg.get("no_dollars_fp") or []))
    out.sort(key=lambda x: x[0])
    return out


def load_trades(fp, pref_b, stat):
    out = []
    for line in gz_lines(fp):
        if not any(k in line for k in pref_b):
            continue
        try:
            d = json.loads(line)
        except Exception:
            stat["trade_unparsed"] += 1
            continue
        msg = d.get("msg") or {}
        if msg.get("is_block_trade"):
            stat["trade_block_skipped"] += 1
            continue
        try:
            out.append((int(msg["ts_ms"]), int(d.get("seq", 0)),
                        msg["market_ticker"], msg["taker_side"],
                        px(msg["yes_price_dollars"]),
                        px(msg["no_price_dollars"]),
                        float(msg["count_fp"])))
        except (KeyError, TypeError, ValueError):
            stat["trade_bad_fields"] += 1
    return out


def run_range(data_dir, out_dir, hours, series=SERIES, variants=VARIANTS,
              cap=CAP, say=print, ignore_queue=False, no_band=False,
              rss_every_s=600, free_abort_mb=FREE_ABORT_MB, resume=False):
    os.makedirs(out_dir, exist_ok=True)
    done = set()
    prior_stat = {}
    warm = None
    if resume:
        for fp in glob.glob(os.path.join(out_dir, "mm_hour_*.json")):
            tag = os.path.basename(fp)[8:-5]
            if tag in hours:
                done.add(tag)
        if done:
            # the last finished hour is re-run as a WARM-UP: it rebuilds the
            # state of the markets that were open at the boundary, and its
            # own output is discarded (it is already on disk). So a restart
            # loses nothing.
            warm = max(done)
            done.discard(warm)
            with open(os.path.join(out_dir, "mm_hour_%s.json" % warm)) as f:
                prior_stat = json.load(f).get("stat", {})
            say("  resuming: %d hour(s) kept on disk, re-running %s as a "
                "warm-up whose output is discarded" % (len(done), warm))
    pref_b = tuple(('"' + s + "-").encode() for s in series)
    results = load_results(data_dir, hours, series)
    with open(os.path.join(out_dir, "mm_results.json"), "w") as f:
        json.dump({k: [v[0], v[1]] for k, v in results.items()}, f)
    say("  settlements from market_lifecycle_v2: %d markets" % len(results))
    with open(os.path.join(out_dir, "mm_variants.json"), "w") as f:
        json.dump({"variants": [list(v) for v in variants], "cap": cap,
                   "band": list(BAND), "series": list(series)}, f)
    sim = Sim(variants=variants, cap=cap, ignore_queue=ignore_queue,
              no_band=no_band, results=results)
    for k, v in prior_stat.items():
        sim.stat[k] = v
    if done:
        sim.stat["resume_restarts"] = sim.stat.get("resume_restarts", 0) + 1
    tbuf = []
    loaded = set()
    t_start = time.time()
    t_rss = t_start
    peak_rss = 0.0

    def load_trade_file(h):
        if h in loaded:
            return
        loaded.add(h)
        fp = os.path.join(data_dir, "trade", h + ".jsonl.gz")
        if os.path.exists(fp):
            tbuf.extend(load_trades(fp, pref_b, sim.stat))
            tbuf.sort()

    for h in hours:
        if h in done:
            continue
        warm_mode = (h == warm)
        if warm_mode:
            saved_stat = dict(sim.stat)
        t_h = time.time()
        dfp = os.path.join(data_dir, "orderbook_delta", h + ".jsonl.gz")
        sfp = os.path.join(data_dir, "orderbook_snapshot", h + ".jsonl.gz")
        summ_fp = os.path.join(out_dir, "mm_hour_%s.json" % h)
        if not os.path.exists(dfp):
            say("  %s: no delta file -- skipped" % h)
            if not warm_mode:
                with open(summ_fp, "w") as f:
                    json.dump({"hour": h, "missing": True}, f)
            continue
        load_trade_file(h)
        load_trade_file(next_hour(h))
        snaps = load_snapshots(sfp, pref_b) if os.path.exists(sfp) else []
        si = 0
        ti = 0
        n_lines = n_kept = 0
        sim.stat["hour_start_fills"] = sim.stat["fills"]
        for line in gz_lines(dfp):
            n_lines += 1
            if not any(k in line for k in pref_b):
                continue
            n_kept += 1
            try:
                d = json.loads(line)
            except Exception:
                sim.stat["delta_unparsed"] += 1
                continue
            msg = d.get("msg") or {}
            rx = d.get("_rx_ms", 0)
            while si < len(snaps) and snaps[si][0] <= rx:
                _, tk, yl, nl = snaps[si]
                sim.on_snapshot(tk, yl, nl, snaps[si][0])
                si += 1
            try:
                ts = int(msg["ts_ms"])
                tk = msg["market_ticker"]
                p = px(msg["price_dollars"])
                dq = float(msg["delta_fp"])
                side = msg["side"]
            except (KeyError, TypeError, ValueError):
                sim.stat["delta_bad_fields"] += 1
                continue
            while ti < len(tbuf) and tbuf[ti][0] <= ts:
                t = tbuf[ti]
                sim.on_trade(t[2], t[3], t[4], t[5], t[6], t[0])
                ti += 1
            sim.on_delta(tk, side, p, dq, ts)
            if (n_kept & 0xFFFF) == 0:
                now = time.time()
                if now - t_rss >= rss_every_s:
                    t_rss = now
                    r, fr = rss_mb(), free_ram_mb()
                    peak_rss = max(peak_rss, r)
                    say("  [mem] %s rss %.0f MB, free %.0f MB, %d lines"
                        % (h, r, fr, n_lines))
                    if 0 <= fr < free_abort_mb:
                        say("  ABORT: free RAM %.0f MB under %d MB"
                            % (fr, free_abort_mb))
                        if warm_mode:
                            return False
                        sim.close_all("abort")
                        _flush(sim, out_dir, h + "_abort", say)
                        return False
        while si < len(snaps):
            _, tk, yl, nl = snaps[si]
            sim.on_snapshot(tk, yl, nl, snaps[si][0])
            si += 1
        del tbuf[:ti]
        r, fr = rss_mb(), free_ram_mb()
        peak_rss = max(peak_rss, r)
        n_closed = len(sim.closed)
        n_fills_h = sum(len(c["fills"]) for c in sim.closed)
        if warm_mode:
            sim.closed = []
            sim.stat = defaultdict(int)
            for k, v in saved_stat.items():
                sim.stat[k] = v
            say("  %s: warm-up re-run done (%d markets rebuilt, output "
                "discarded), %.0fs" % (h, len(sim.markets), time.time() - t_h))
            continue
        _flush(sim, out_dir, h, say, extra={
            "lines": n_lines, "kept": n_kept, "snapshots": len(snaps),
            "markets_closed": n_closed, "fills_in_closed": n_fills_h,
            "open_markets": len(sim.markets), "trade_buffer": len(tbuf),
            "rss_mb": round(r, 1), "free_mb": round(fr, 0),
            "secs": round(time.time() - t_h, 1)})
        say("  %s: %s lines, %s kept, %d markets closed, %d fills, "
            "%.0fs, rss %.0f MB, free %.0f MB"
            % (h, format(n_lines, ","), format(n_kept, ","), n_closed,
               n_fills_h, time.time() - t_h, r, fr))
        if 0 <= fr < free_abort_mb:
            say("  ABORT: free RAM %.0f MB under %d MB" % (fr, free_abort_mb))
            sim.close_all("abort")
            _flush(sim, out_dir, h + "_abort", say)
            return False
    # trades left in the buffer belong to the tail of the last hour
    while ti < len(tbuf):
        t = tbuf[ti]
        sim.on_trade(t[2], t[3], t[4], t[5], t[6], t[0])
        ti += 1
    sim.close_all("end")
    _flush(sim, out_dir, "end", say, extra={"peak_rss_mb": round(peak_rss, 1),
                                            "secs_total": round(
                                                time.time() - t_start, 1)})
    with open(os.path.join(out_dir, "mm_ahead0.json"), "w") as f:
        json.dump(sim.ahead0_samples, f)
    say("  done: %d fills, peak rss %.0f MB, %.0f s"
        % (sim.stat["fills"], peak_rss, time.time() - t_start))
    return True


def _flush(sim, out_dir, tag, say, extra=None):
    fp = os.path.join(out_dir, "mm_fills_%s.jsonl.gz" % tag)
    with gzip.open(fp, "wt", encoding="utf-8") as f:
        for rec in sim.closed:
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")
    sim.closed = []
    summ = {"hour": tag, "stat": dict(sim.stat)}
    if extra:
        summ.update(extra)
    with open(os.path.join(out_dir, "mm_hour_%s.json" % tag), "w") as f:
        json.dump(summ, f)


# ===========================================================================
# statistics
# ===========================================================================
def clustered(by_close):
    """Equal-weight close clusters: {close: [sum_pnl_cents, qty]}."""
    cl = [s / n for s, n in by_close.values() if n > 0]
    G = len(cl)
    if G < 30:
        return {"G": G, "mean": mean(cl) if cl else None, "t": None,
                "mde": None}
    mu = mean(cl)
    sd = pstdev(cl) * math.sqrt(G / (G - 1.0))
    se = sd / math.sqrt(G)
    return {"G": G, "mean": mu, "t": (mu / se if se > 0 else 0.0),
            "mde": _tcrit(0.05, G - 1) * se}


def quantiles(v, fracs):
    if not v:
        return [None] * len(fracs)
    w = sorted(v)
    return [w[min(len(w) - 1, int(f * len(w)))] for f in fracs]


def pnl_cents(s, p, Y):
    """Our BID bought YES at yes-price p; our ASK sold YES at 1000 - p(no)."""
    return (Y - p) / 10.0 if s == YES else ((1000 - p) - Y) / 10.0


def load_run(out_dir, stream=False):
    with open(os.path.join(out_dir, "mm_variants.json")) as f:
        meta = json.load(f)
    with open(os.path.join(out_dir, "mm_results.json")) as f:
        results = json.load(f)
    recs = None if stream else list(iter_recs(out_dir))
    hours = []
    for fp in sorted(glob.glob(os.path.join(out_dir, "mm_hour_*.json"))):
        with open(fp) as f:
            hours.append(json.load(f))
    return meta, results, recs, hours


def iter_recs(out_dir):
    """Stream the closed-market records one at a time, never all in RAM."""
    for fp in sorted(glob.glob(os.path.join(out_dir, "mm_fills_*.jsonl.gz"))):
        with gzip.open(fp, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)


def _day_of(ms):
    import datetime as _dt
    return _dt.datetime.fromtimestamp(ms / 1000.0, _dt.timezone.utc
                                      ).strftime("%Y-%m-%d")


def _hour_of(ms):
    import datetime as _dt
    return _dt.datetime.fromtimestamp(ms / 1000.0, _dt.timezone.utc
                                      ).strftime("%Y-%m-%d %H")


def analyse(meta, results, recs, cap_filter=None):
    """Per-variant tables in ONE streaming pass over the market records.
    cap_filter=k drops fills that would have taken |net| beyond k, post hoc
    (approximate: queue positions are the uncapped run's)."""
    variants = [tuple(v) for v in meta["variants"]]
    nv = len(variants)

    def acc():
        return {"by_close": defaultdict(lambda: [0.0, 0.0]),
                "by_day": defaultdict(lambda: [0.0, 0.0, 0]),
                "by_hour": defaultdict(float),
                "by_band": defaultdict(lambda: [0.0, 0.0, 0]),
                "by_tau": defaultdict(lambda: [0.0, 0.0, 0]),
                "by_mech": defaultdict(lambda: [0.0, 0.0, 0]),
                "by_side": defaultdict(lambda: [0.0, 0.0, 0]),
                "by_series": defaultdict(lambda: [0.0, 0.0, 0]),
                "by_series_day": defaultdict(lambda: [0.0, 0.0, 0]),
                "stale": [0.0, 0.0, 0], "n_fill": 0, "qty": 0.0,
                "pnl": 0.0, "paired": 0.0, "inv_pnl": 0.0,
                "loss_events": 0, "net_abs": [], "inv_nonzero": 0,
                "inv_markets": 0, "worst_close": (0.0, None),
                "close_pnl": defaultdict(float)}
    A = [acc() for _ in range(nv)]
    n_no_result = 0
    n_markets = 0
    for rec in recs:
        r = results.get(rec["tk"])
        if r is None:
            n_no_result += 1
            continue
        n_markets += 1
        Y = 1000.0 if r[0] >= 0.5 else 0.0
        close = rec["close"]
        day = _day_of(close)
        net = [0.0] * nv
        bq = [0.0] * nv
        bs = [0.0] * nv
        bc = [0.0] * nv
        sp = [0.0] * nv
        mpnl = [0.0] * nv
        for f in rec["fills"]:
            v = f[0]
            s, p, q, ts, mech, st = f[1], f[2], f[3], f[4], f[5], f[6]
            if cap_filter is not None:
                nn = net[v] + (q if s == YES else -q)
                if abs(nn) > cap_filter + EPS:
                    continue
            net[v] += q if s == YES else -q
            c = pnl_cents(s, p, Y)
            yes_p = p if s == YES else 1000 - p
            tau = (close - ts) / 1000.0 if close else -1
            a = A[v]
            a["n_fill"] += 1
            a["qty"] += q
            a["pnl"] += c * q
            mpnl[v] += c * q
            if c < 0:
                a["loss_events"] += 1
            a["by_close"][close][0] += c * q
            a["by_close"][close][1] += q
            a["close_pnl"][close] += c * q
            a["by_day"][day][0] += c * q
            a["by_day"][day][1] += q
            a["by_day"][day][2] += 1
            a["by_hour"][_hour_of(ts)] += c * q
            for lo, hi in PRICE_BANDS:
                if lo <= yes_p < hi or (hi == 900 and yes_p == 900):
                    a["by_band"][(lo, hi)][0] += c * q
                    a["by_band"][(lo, hi)][1] += q
                    a["by_band"][(lo, hi)][2] += 1
                    break
            for lo, hi in TAU_BANDS:
                if lo <= tau < hi:
                    a["by_tau"][(lo, hi)][0] += c * q
                    a["by_tau"][(lo, hi)][1] += q
                    a["by_tau"][(lo, hi)][2] += 1
                    break
            for key, d in (((mech), a["by_mech"]), (s, a["by_side"]),
                           (rec["ser"], a["by_series"]),
                           ((rec["ser"], day), a["by_series_day"])):
                d[key][0] += c * q
                d[key][1] += q
                d[key][2] += 1
            if st:
                a["stale"][0] += c * q
                a["stale"][1] += q
                a["stale"][2] += 1
            if s == YES:
                bq[v] += q
                bc[v] += p * q
            else:
                bs[v] += q
                sp[v] += (1000 - p) * q
        for v in range(nv):
            a = A[v]
            if bq[v] > 0 or bs[v] > 0:
                matched = min(bq[v], bs[v])
                ab = bc[v] / bq[v] if bq[v] > 0 else 0.0
                asx = sp[v] / bs[v] if bs[v] > 0 else 0.0
                pp = matched * (asx - ab) / 10.0
                a["paired"] += pp
                a["inv_pnl"] += mpnl[v] - pp
                a["inv_markets"] += 1
                a["net_abs"].append(abs(net[v]))
                if abs(net[v]) > EPS:
                    a["inv_nonzero"] += 1
    out = []
    for v in range(nv):
        a = A[v]
        wc = min(a["close_pnl"].items(), key=lambda kv: kv[1]) \
            if a["close_pnl"] else (None, 0.0)
        out.append({
            "variant": variants[v], "n_fill": a["n_fill"], "qty": a["qty"],
            "pnl_c": a["pnl"], "cl": clustered(a["by_close"]),
            "days": sorted(a["by_day"].items()), "by_hour": a["by_hour"],
            "by_band": dict(a["by_band"]), "by_tau": dict(a["by_tau"]),
            "by_mech": dict(a["by_mech"]), "by_side": dict(a["by_side"]),
            "by_series": dict(a["by_series"]),
            "by_series_day": dict(a["by_series_day"]),
            "stale": a["stale"], "paired_pnl_c": a["paired"],
            "inv_pnl_c": a["inv_pnl"], "inv_markets": a["inv_markets"],
            "inv_nonzero": a["inv_nonzero"], "net_abs": a["net_abs"],
            "loss_events": a["loss_events"],
            "n_closes": len(a["by_close"]),
            "worst_close": (wc[0], wc[1]),
            "close_pnl": a["close_pnl"]})
    return out, n_markets, n_no_result


# ===========================================================================
# THE SELF-TEST -- the deliverable
# ===========================================================================
def _write_world(tmp, t0, close_ms, events, result="yes",
                 tk="KXBTC15M-TEST0101-00"):
    """events: list of ('snap', rx, yes_levels, no_levels) |
    ('delta', ts, side, price_str, delta_str) | ('trade', ts, taker, yes_str,
    no_str, count_str) | ('empty', rx). Writes the real file layout."""
    import datetime as _dt
    h = _dt.datetime.fromtimestamp(t0 / 1000.0, _dt.timezone.utc
                                   ).strftime("%Y%m%dT%H")
    for ch in ("orderbook_snapshot", "orderbook_delta", "trade",
               "market_lifecycle_v2"):
        os.makedirs(os.path.join(tmp, ch), exist_ok=True)
    seq = 1000
    tseq = 1
    files = {ch: gzip.open(os.path.join(tmp, ch, h + ".jsonl.gz"), "at")
             for ch in ("orderbook_snapshot", "orderbook_delta", "trade")}
    for ev in events:
        seq += 1
        if ev[0] == "snap":
            _, rx, yl, nl = ev
            msg = {"market_ticker": tk, "market_id": "x",
                   "yes_dollars_fp": [[a, b] for a, b in yl],
                   "no_dollars_fp": [[a, b] for a, b in nl]}
            files["orderbook_snapshot"].write(json.dumps(
                {"type": "orderbook_snapshot", "sid": 4, "seq": seq,
                 "msg": msg, "_rx_ms": rx}) + "\n")
        elif ev[0] == "empty":
            files["orderbook_snapshot"].write(json.dumps(
                {"type": "orderbook_snapshot", "sid": 4, "seq": seq,
                 "msg": {"market_ticker": tk, "market_id": "x"},
                 "_rx_ms": ev[1]}) + "\n")
        elif ev[0] == "delta":
            _, ts, side, p, dq = ev
            files["orderbook_delta"].write(json.dumps(
                {"type": "orderbook_delta", "sid": 4, "seq": seq,
                 "msg": {"market_ticker": tk, "market_id": "x",
                         "price_dollars": p, "delta_fp": dq, "side": side,
                         "ts": "x", "ts_ms": ts}, "_rx_ms": ts + 30}) + "\n")
        elif ev[0] == "trade":
            _, ts, taker, yp, np_, cnt = ev
            tseq += 1
            files["trade"].write(json.dumps(
                {"type": "trade", "sid": 5, "seq": tseq,
                 "msg": {"trade_id": "t%d" % tseq, "market_ticker": tk,
                         "yes_price_dollars": yp, "no_price_dollars": np_,
                         "count_fp": cnt, "taker_side": taker,
                         "is_block_trade": False, "ts": ts // 1000,
                         "ts_ms": ts}, "_rx_ms": ts + 4500}) + "\n")
    for f in files.values():
        f.close()
    with gzip.open(os.path.join(tmp, "market_lifecycle_v2", h + ".jsonl.gz"),
                   "at") as f:
        f.write(json.dumps({"type": "market_lifecycle_v2", "sid": 1,
                            "seq": 5, "msg": {"market_ticker": tk,
                                              "determination_ts": close_ms
                                              // 1000,
                                              "result": result,
                                              "event_type": "determined"},
                            "_rx_ms": close_ms + 500}) + "\n")
    return h


def _planted_world(t0):
    """The hand-computed world. Every step's expected fill per variant is
    written next to it. Prices: yes bid 50c (D=5), 49c (100); no bid 48c
    (= yes ask 52c, D=5), 47c (100). Re-posts land at t + L, so the steps
    that discriminate the cancel policies are spaced > 1000 ms apart."""
    ev = [("snap", t0, [("0.5000", "5.00"), ("0.4900", "100.00")],
           [("0.4800", "5.00"), ("0.4700", "100.00")]),
          ("delta", t0 + 1, "yes", "0.4900", "1.00"),        # first event
          # 2. +10 arrive at yes 50c (FIFO: behind us; LAST: in front)
          ("delta", t0 + 2000, "yes", "0.5000", "10.00"),
          # 3. taker sells 7 at 50c -> FIFO fill 1 (7 > 5); LAST none (7<15)
          #    FIFO re-posts land at 3000+L with ahead 8
          ("trade", t0 + 3000, "no", "0.5000", "0.5000", "7.00"),
          ("delta", t0 + 3000, "yes", "0.5000", "-7.00"),
          # 3b. +10 arrive (D 8 -> 18) after every re-post has landed
          ("delta", t0 + 4500, "yes", "0.5000", "10.00"),
          # 4. cancel 6 (D 18 -> 12): behind 8, prorata 8*12/18=5.333,
          #    front 2, last 12
          ("delta", t0 + 5000, "yes", "0.5000", "-6.00"),
          # 5. taker sells 6: behind no; prorata 0.6667; front 1; last no
          ("trade", t0 + 6000, "no", "0.5000", "0.5000", "6.00"),
          ("delta", t0 + 6000, "yes", "0.5000", "-6.00"),
          # 6. taker sells 0.5: prorata's remainder 0.3333 (ahead 0) fills
          ("trade", t0 + 7000, "no", "0.5000", "0.5000", "0.50"),
          ("delta", t0 + 7000, "yes", "0.5000", "-0.50"),
          # 7. ASK side: taker buys 5 at 52c (clears the level exactly) and
          #    walks to 53c with 2 in the same ms -> WALK fill 1, ALL variants
          ("trade", t0 + 8000, "yes", "0.5200", "0.4800", "5.00"),
          ("trade", t0 + 8000, "yes", "0.5300", "0.4700", "2.00"),
          ("delta", t0 + 8000, "no", "0.4800", "-5.00"),
          ("delta", t0 + 8000, "no", "0.4700", "-2.00"),
          # 8. bid side: the 50c level is cancelled away (D 5.5 -> 0), the
          #    touch drops to 49c; 100 ms later a NO bid arrives at 50c
          #    (= yes ask 50c) -> CROSS fill for every order still live at
          #    50c: the L=300 and L=1000 variants only (pick-off)
          ("delta", t0 + 9000, "yes", "0.5000", "-5.50"),
          ("delta", t0 + 9100, "no", "0.5000", "3.00"),
          ("delta", t0 + 9200, "no", "0.5000", "-3.00"),
          # 9. LATENCY: +2 at 49.5c (new touch); 100 ms later a taker clears
          #    it (2) and walks to 49c with 1 -> only the L=0 orders are at
          #    49.5c -> WALK fill 1 for the four L=0 variants; the L>0
          #    orders sit at 49c behind ahead=101 and do not fill
          ("delta", t0 + 10000, "yes", "0.4950", "2.00"),
          ("trade", t0 + 10100, "no", "0.4950", "0.5050", "2.00"),
          ("trade", t0 + 10100, "no", "0.4900", "0.5100", "1.00"),
          ("delta", t0 + 10100, "yes", "0.4950", "-2.00"),
          ("delta", t0 + 10100, "yes", "0.4900", "-1.00"),
          # 10. BAND: the ask side empties (so a 95c bid is consistent), then
          #     +4 at 95c makes the bid touch 95c (out of band): no order may
          #     be posted there. A taker clears it and walks to 49c with 1.
          #     In band: nothing fills (the 49c orders have ahead 100 and
          #     the 95c print is BETTER than 49c, not worse). Without the
          #     band an L=0 order at 95c would WALK-fill.
          ("delta", t0 + 10500, "no", "0.4700", "-98.00"),
          ("delta", t0 + 11600, "yes", "0.9500", "4.00"),
          ("trade", t0 + 12000, "no", "0.9500", "0.0500", "4.00"),
          ("trade", t0 + 12000, "no", "0.4900", "0.5100", "1.00"),
          ("delta", t0 + 12000, "yes", "0.9500", "-4.00"),
          ("delta", t0 + 12000, "yes", "0.4900", "-1.00"),
          # 11. DEFERRED WALK: the touch is back at 49c (D=99) and every
          #     variant has a live 49c order. In one ms the tape shows a
          #     sell print at 48c (past our level) and THEN the 99 at 49c
          #     cancelled. The print is seen first, the level still shows
          #     size, so the credit is deferred; the cancel empties the
          #     level in the same ms and the walk fill (1) is credited to
          #     every variant.
          ("trade", t0 + 12500, "no", "0.4800", "0.5200", "1.00"),
          ("delta", t0 + 12500, "yes", "0.4900", "-99.00"),
          ("empty", t0 + 13500)]
    return ev


def _expected():
    """(bid fills, ask fills) contracts per (model, L) in the planted world.
    bid: step3 (FIFO only) + step5/6 (behind 0, prorata 1, front 1, last 0)
         + step8 cross (L>0 only) + step9 walk (L=0 only)
         + step11 deferred walk at 49c (everyone)
    ask: step7 walk = 1 for everyone."""
    exp = {}
    for L in LATENCIES:
        for model in MODELS:
            bid = 0.0
            if model != "last":
                bid += 1.0                      # step 3
            if model in ("fifo_prorata", "fifo_front"):
                bid += 1.0                      # steps 5+6
            if L > 0:
                bid += 1.0                      # step 8 cross (pick-off)
            else:
                bid += 1.0                      # step 9 walk at 49.5c
            bid += 1.0                          # step 11 deferred walk
            exp[(model, L)] = (bid, 1.0)
    return exp


def selftest(verbose=True):
    ok = True

    def check(label, cond, detail=""):
        nonlocal ok
        if not cond:
            ok = False
        if verbose:
            print("    [%s] %s%s" % ("ok" if cond else "FAIL", label,
                                     ("   " + detail) if detail else ""))
        return cond

    if verbose:
        print("=" * 78)
        print("MAKERSIM SELF-TEST")
        print("=" * 78)
    t0 = 1767225600000 + 120000              # 2026-01-01T00:02:00Z
    close_ms = 1767225600000 + 900000        # 00:15:00Z
    tmp = tempfile.mkdtemp(prefix="mm_selftest_")
    h = _write_world(tmp, t0, close_ms, _planted_world(t0), result="yes")
    out = os.path.join(tmp, "out")
    ok_run = run_range(tmp, out, [h], say=(lambda *a: None))
    check("the streaming path ran on the synthetic tape", ok_run)
    meta, results, recs, hours = load_run(out)
    check("exactly one market closed, with a lifecycle result",
          len(recs) == 1 and recs[0]["tk"] in results,
          "%d records" % len(recs))
    check("no order was ever posted outside the band",
          recs and recs[0]["oob_posts"] == 0)
    if verbose:
        print("\n  (a) planted fills, EXACT per variant (bid, ask)")
    exp = _expected()
    got = {}
    for v, var in enumerate(meta["variants"]):
        var = tuple(var)
        b = sum(f[3] for f in recs[0]["fills"] if f[0] == v and f[1] == YES)
        a = sum(f[3] for f in recs[0]["fills"] if f[0] == v and f[1] == NO)
        got[var] = (round(b, 6), round(a, 6))
        check("%-13s L=%-4d bid %.4f ask %.4f" % (var[0], var[1], b, a),
              abs(b - exp[var][0]) < 1e-6 and abs(a - exp[var][1]) < 1e-6,
              "want %s" % (exp[var],))
    # mechanism labels on the planted fills
    mechs = defaultdict(float)
    for f in recs[0]["fills"]:
        mechs[(tuple(meta["variants"][f[0]]), f[5])] += f[3]
    check("the LAST L=300 fills are one CROSS (bid) and two WALKs (ask, "
          "deferred bid)",
          abs(mechs[(("last", 300), "cross")] - 1.0) < 1e-6
          and abs(mechs[(("last", 300), "walk")] - 2.0) < 1e-6
          and mechs[(("last", 300), "queue")] == 0.0)
    st0 = hours[-1]["stat"]
    check("the deferred walk was credited once per variant (%d) and "
          "nothing was left uncredited (%d)"
          % (st0.get("walk_deferred", 0),
             st0.get("anom_walk_past_nonempty_uncredited", 0)),
          st0.get("walk_deferred", 0) == len(meta["variants"])
          and st0.get("anom_walk_past_nonempty_uncredited", 0) == 0)
    check("the prorata L=0 queue fills total 2.0 over 3 prints (7, 6, 0.5)",
          abs(mechs[(("fifo_prorata", 0), "queue")] - 2.0) < 1e-6)
    stale = [f for f in recs[0]["fills"] if f[6] == 1]
    check("the cross fill is flagged STALE (price no longer the touch)",
          any(f[5] == "cross" and f[6] == 1 for f in recs[0]["fills"])
          and all(f[5] != "cross" or f[6] == 1 for f in recs[0]["fills"]),
          "%d stale fills" % len(stale))
    # the money: result YES -> bid fills at 50c earn +50c, at 49.5c +50.5c;
    # the ask fill sold YES at 52c and it settled at 100c: -48c
    if verbose:
        print("\n  (b) the money against a planted YES settlement")
    rows, nm, nnr = analyse(meta, results, recs)
    want_c = {}
    for var, (b, a) in exp.items():
        c = -48.0 + 51.0                      # ask at 52c; deferred walk 49c
        if var[1] > 0:
            c += (b - 1.0) * 50.0             # the other bid fills at 50c
        else:
            c += (b - 2.0) * 50.0 + 50.5      # ... and the walk at 49.5c
        want_c[var] = c
    for r in rows:
        var = tuple(r["variant"])
        check("%-13s L=%-4d P&L %+.2fc" % (var[0], var[1], r["pnl_c"]),
              abs(r["pnl_c"] - want_c[var]) < 1e-6,
              "want %+.2f" % want_c[var])
    # inventory: paired + inventory P&L must sum to the total
    for r in rows[:1]:
        check("paired + inventory P&L == total",
              abs(r["paired_pnl_c"] + r["inv_pnl_c"] - r["pnl_c"]) < 1e-6)

    # (c) MUTATION 1: a queue-ignoring estimator must be REJECTED by (a)
    if verbose:
        print("\n  (c) mutants")
    out2 = os.path.join(tmp, "out_mut1")
    run_range(tmp, out2, [h], say=(lambda *a: None), ignore_queue=True)
    _, _, recs2, _ = load_run(out2)
    bad = sum(f[3] for f in recs2[0]["fills"] if f[0] == 0 and f[1] == YES)
    check("MUTATION queue-ignoring estimator is rejected (LAST L=0 bid %.2f "
          "vs planted %.2f)" % (bad, exp[("last", 0)][0]),
          abs(bad - exp[("last", 0)][0]) > 1e-6)
    # MUTATION 2: ignoring the band must post at 95c and fill there
    out3 = os.path.join(tmp, "out_mut2")
    run_range(tmp, out3, [h], say=(lambda *a: None), no_band=True)
    _, _, recs3, _ = load_run(out3)
    oob = recs3[0]["oob_posts"]
    f95 = [f for f in recs3[0]["fills"] if f[2] == 950]
    check("MUTATION band-ignoring quoter posts out of band (%d) and is "
          "filled at 95c (%d)" % (oob, len(f95)), oob > 0 and len(f95) > 0)

    # (d) a closed-form world: a 1000-deep level swept by 900 every second
    #     and refilled in the SAME ms. LAST (ahead = displayed = 1000) can
    #     never fill. FIFO moves up to 100 after the first sweep and is
    #     filled by the second, re-posts at the back, so it fills on every
    #     even sweep: 149 of 299 -- on each side.
    if verbose:
        print("\n  (d) closed form: LAST zero, FIFO one fill per two sweeps")
    tmp2 = tempfile.mkdtemp(prefix="mm_selftest0_")
    ev = [("snap", t0, [("0.5000", "1000.00")], [("0.4800", "1000.00")]),
          ("delta", t0 + 1, "yes", "0.5000", "0.00")]
    for i in range(1, 300):
        ts = t0 + i * 1000
        ev.append(("trade", ts, "no", "0.5000", "0.5000", "900.00"))
        ev.append(("delta", ts, "yes", "0.5000", "-900.00"))
        ev.append(("delta", ts, "yes", "0.5000", "900.00"))
        ev.append(("trade", ts + 2, "yes", "0.5200", "0.4800", "900.00"))
        ev.append(("delta", ts + 2, "no", "0.4800", "-900.00"))
        ev.append(("delta", ts + 2, "no", "0.4800", "900.00"))
    ev.append(("empty", t0 + 400000))
    h2 = _write_world(tmp2, t0, close_ms, ev)
    out4 = os.path.join(tmp2, "out")
    run_range(tmp2, out4, [h2], say=(lambda *a: None))
    meta4, _, recs4, hours4 = load_run(out4)
    st = hours4[-1]["stat"]
    for v, var in enumerate(meta4["variants"]):
        var = tuple(var)
        b = sum(f[3] for f in recs4[0]["fills"] if f[0] == v and f[1] == YES)
        a = sum(f[3] for f in recs4[0]["fills"] if f[0] == v and f[1] == NO)
        want = 0.0 if var[0] == "last" else 149.0
        check("%-13s L=%-4d bid %.0f ask %.0f (want %.0f each)"
              % (var[0], var[1], b, a, want),
              abs(b - want) < 1e-6 and abs(a - want) < 1e-6)
    check("the prints were seen (%d of 598)" % st.get("prints", 0),
          st.get("prints", 0) == 598)
    check("no anomaly was counted on a consistent book",
          st.get("anom_print_exceeds_level", 0) == 0
          and st.get("anom_walk_past_nonempty", 0) == 0
          and st.get("anom_cross_nonempty", 0) == 0
          and st.get("anom_level_negative", 0) == 0)

    # (e) inventory cap
    if verbose:
        print("\n  (e) inventory cap")
    tmp3 = tempfile.mkdtemp(prefix="mm_selftest_cap_")
    ev = [("snap", t0, [("0.5000", "2.00")], [("0.4000", "2.00")]),
          ("delta", t0 + 1, "yes", "0.5000", "0.00")]
    for i in range(1, 6):        # five sweeps of the bid level, each 2 + walk
        ts = t0 + i * 1000
        ev.append(("trade", ts, "no", "0.5000", "0.5000", "2.00"))
        ev.append(("trade", ts, "no", "0.4900", "0.5100", "1.00"))
        ev.append(("delta", ts, "yes", "0.5000", "-2.00"))
        ev.append(("delta", ts + 1, "yes", "0.5000", "2.00"))
    ev.append(("empty", t0 + 20000))
    h3 = _write_world(tmp3, t0, close_ms, ev)
    outc = os.path.join(tmp3, "out_cap1")
    run_range(tmp3, outc, [h3], say=(lambda *a: None), cap=1)
    _, _, recsc, _ = load_run(outc)
    outn = os.path.join(tmp3, "out_cap10")
    run_range(tmp3, outn, [h3], say=(lambda *a: None), cap=10)
    _, _, recsn, _ = load_run(outn)
    b1 = sum(f[3] for f in recsc[0]["fills"] if f[0] == 0 and f[1] == YES)
    b10 = sum(f[3] for f in recsn[0]["fills"] if f[0] == 0 and f[1] == YES)
    check("cap=1 stops after ONE bid fill (%.0f) where cap=10 takes all "
          "five (%.0f)" % (b1, b10), abs(b1 - 1.0) < 1e-6
          and abs(b10 - 5.0) < 1e-6)

    # (f) sign-scrambled money control, clustered by close
    if verbose:
        print("\n  (f) sign-scrambled control on the money")
    rnd = random.Random(7)
    real, shuf = defaultdict(lambda: [0.0, 0.0]), defaultdict(
        lambda: [0.0, 0.0])
    for k in range(80):
        close = 1767225600000 + k * 900000
        for _ in range(3):
            q = 1.0
            c = pnl_cents(YES, 500, 1000.0)          # +50c planted
            real[close][0] += c * q
            real[close][1] += q
            shuf[close][0] += rnd.choice((1.0, -1.0)) * c * q
            shuf[close][1] += q
    r, s = clustered(real), clustered(shuf)
    check("planted +50.000c per contract is recovered exactly",
          r["mean"] is not None and abs(r["mean"] - 50.0) < 1e-9)
    check("sign-scrambled control sits inside its own MDE",
          s["mde"] is not None and abs(s["mean"]) < s["mde"],
          "%+.3fc vs MDE %.3fc" % (s["mean"], s["mde"]))

    # (g) memory probes work and the working code never imports replay
    if verbose:
        print("\n  (g) plumbing")
    check("rss probe returns a number (%.0f MB)" % rss_mb(), rss_mb() > 0)
    check("free-RAM probe returns a number (%.0f MB)" % free_ram_mb(),
          free_ram_mb() > 0)
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    work = src[src.index("import argparse"):src.rindex("def " + "selftest")]
    imports = [ln for ln in work.splitlines()
               if ln.lstrip().startswith(("import ", "from "))]
    check("no import line in the working code names replay (%d import "
          "lines scanned)" % len(imports),
          imports and not any("replay" in ln for ln in imports))

    if verbose:
        print("\n" + ("  SELF-TEST PASSED" if ok else "  SELF-TEST FAILED"))
    return ok


# ===========================================================================
# the report
# ===========================================================================
def _fmt_cell(v):
    s, q, n = v
    return "%+.2fc x %s = $%+.2f" % ((s / q) if q else 0.0, format(n, ","),
                                     s * 1.0 / 100.0)


def report(out_dir, say=print, cap_filter=None):
    meta, results, recs, hours = load_run(out_dir, stream=True)
    rows, n_markets, n_no_result = analyse(meta, results, iter_recs(out_dir),
                                           cap_filter)
    hs = [h for h in hours if "stat" in h]
    stat = hs[-1]["stat"] if hs else {}
    n_hours = sum(1 for h in hours if "lines" in h)
    n_missing = sum(1 for h in hours if h.get("missing"))
    days = [d for d, _ in rows[0]["days"]] if rows else []
    say("markets simulated %d (settled result known %d, unknown %d), hours "
        "%d, missing hour files %d, days %s"
        % (n_markets + n_no_result, n_markets, n_no_result, n_hours,
           n_missing, ", ".join(days)))
    say("prints %s, contracts printed %s, cancel events %s, posts %s"
        % (format(stat.get("prints", 0), ","),
           format(int(stat.get("print_qty", 0)), ","),
           format(stat.get("cancel_events", 0), ","),
           format(stat.get("posts", 0), ",")))
    say("anomalies: print>level %d, walk-past-nonempty %d, cross-nonempty "
        "%d, level<0 %d, fills after close %d, closed by gap %d, "
        "resnapshot %d"
        % (stat.get("anom_print_exceeds_level", 0),
           stat.get("anom_walk_past_nonempty", 0),
           stat.get("anom_cross_nonempty", 0),
           stat.get("anom_level_negative", 0),
           stat.get("fills_after_close", 0), stat.get("closed_gap", 0),
           stat.get("resnapshot", 0)))
    peak = max((h.get("rss_mb", 0) for h in hours), default=0)
    say("peak RSS %.0f MB" % peak)
    return rows, n_markets, days, stat


def _c(x):
    return "%+.2fc" % x


def _d(cents):
    return "$%+.2f" % (cents / 100.0)


def _rowkey(v):
    return "%s L=%d" % (v[0], v[1])


def write_md(out_dir, path, old_claim_per_day=44044, old_claim_series=9,
             title="## Results"):
    """Append the result sections to the report file. Streams the fills."""
    meta, results, _recs, hours = load_run(out_dir, stream=True)
    rows, n_markets, n_no_result = analyse(meta, results, iter_recs(out_dir))
    hs = [h for h in hours if "stat" in h]
    stat = hs[-1]["stat"] if hs else {}
    n_hours = sum(1 for h in hours if "lines" in h)
    n_missing = sum(1 for h in hours if h.get("missing"))
    peak = max((h.get("rss_mb", 0) for h in hours), default=0)
    secs = sum(h.get("secs", 0) for h in hours)
    days = [d for d, _ in rows[0]["days"]] if rows else []
    nd = max(1, len(days))
    a0 = []
    try:
        with open(os.path.join(out_dir, "mm_ahead0.json")) as f:
            a0 = json.load(f)
    except Exception:
        pass
    by = {tuple(r["variant"]): r for r in rows}
    L = []
    w = L.append
    w(title)
    w("")
    w("Run: %d hour files (%d missing on the tape), %d markets with a settled "
      "result (%d without, excluded), days %s. Peak RSS %.0f MB, %.0f min of "
      "CPU. Prints seen %s (%s contracts), cancel events %s, our posts %s."
      % (n_hours, n_missing, n_markets, n_no_result, ", ".join(days), peak,
         secs / 60.0, format(stat.get("prints", 0), ","),
         format(int(stat.get("print_qty", 0)), ","),
         format(stat.get("cancel_events", 0), ","),
         format(stat.get("posts", 0), ",")))
    w("")
    w("Book-consistency counters (each is a case the model refused to credit "
      "or had to clamp): print larger than the displayed level %s of %s "
      "prints; taker walked past our level while it still showed size %s, "
      "of which %s were credited when the level emptied in the same "
      "millisecond and %s never were; crossing arrival against a non-empty "
      "level %s; level driven below zero %s; markets dropped for a >60 s "
      "gap %d; fills after close %d."
      % (format(stat.get("anom_print_exceeds_level", 0), ","),
         format(stat.get("prints", 0), ","),
         format(stat.get("anom_walk_past_nonempty", 0), ","),
         format(stat.get("walk_deferred", 0), ","),
         format(stat.get("anom_walk_past_nonempty_uncredited", 0), ","),
         format(stat.get("anom_cross_nonempty", 0), ","),
         format(stat.get("anom_level_negative", 0), ","),
         stat.get("closed_gap", 0), stat.get("fills_after_close", 0)))
    if a0:
        q = quantiles(a0, (0.10, 0.25, 0.50, 0.75, 0.90))
        w("")
        w("Size resting in front of us when an order lands at the touch "
          "(%s landings): p10 %.0f, p25 %.0f, median %.0f, p75 %.0f, p90 "
          "%.0f contracts." % (format(len(a0), ","), q[0], q[1], q[2], q[3],
                               q[4]))
    # ---- 1. headline per variant
    w("")
    w("### 1. Fills and money per queue model and latency (1 contract a side)")
    w("")
    w("`last` = we are behind everything displayed at all times (the "
      "requested conservative bound). `fifo_*` = arrivals after us queue "
      "behind us; the suffix is the cancel guess (behind / prorata / front "
      "of us). L = milliseconds from an exchange event to our order landing "
      "or dying. Per-contract P&L is clustered by close (all four series "
      "settle on the same quarter hour); MDE is the smallest per-contract "
      "effect this many closes could have detected at 95%.")
    w("")
    w("| model | L ms | fills/day | contracts/day | $/day | per contract "
      "(pooled) | per contract (close-weighted) | "
      "t | MDE | closes | days + | worst day | worst close | worst hour |")
    w("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        v = r["variant"]
        cl = r["cl"]
        dd = r["days"]
        pos = sum(1 for _, x in dd if x[0] > 0)
        worst_day = min(dd, key=lambda kv: kv[1][0]) if dd else ("", [0.0])
        wh = min(r["by_hour"].items(), key=lambda kv: kv[1]) \
            if r["by_hour"] else ("", 0.0)
        wc = r["worst_close"]
        w("| %s | %d | %s | %s | %s | %s | %s | %s | %s | %d | %d of %d | "
          "%s (%s) | %s | %s (%s) |"
          % (v[0], v[1], format(int(round(r["n_fill"] / nd)), ","),
             format(int(round(r["qty"] / nd)), ","),
             _d(r["pnl_c"] / nd),
             _c(r["pnl_c"] / r["qty"]) if r["qty"] else "n/a",
             _c(cl["mean"]) if cl["mean"] is not None else "n/a",
             ("%.2f" % cl["t"]) if cl["t"] is not None else "n/a",
             ("%.2fc" % cl["mde"]) if cl["mde"] is not None else "n/a",
             cl["G"], pos, len(dd), _d(worst_day[1][0]), worst_day[0],
             _d(wc[1]), _d(wh[1]), wh[0]))
    # ---- 2. per day for the headline variants
    heads = [("last", 300), ("last", 0), ("fifo_prorata", 300),
             ("fifo_prorata", 0), ("fifo_behind", 300), ("fifo_front", 0)]
    heads = [h for h in heads if h in by]
    w("")
    w("### 2. Day by day ($ and fills) for the variants that matter")
    w("")
    w("| day | " + " | ".join(_rowkey(h) for h in heads) + " |")
    w("|---|" + "---|" * len(heads))
    for d in days:
        cells = []
        for h in heads:
            dd = dict(by[h]["days"])
            x = dd.get(d, [0.0, 0.0, 0])
            cells.append("%s / %s fills" % (_d(x[0]), format(x[2], ",")))
        w("| %s | %s |" % (d, " | ".join(cells)))
    # ---- 3. by price band and tau
    w("")
    w("### 3. Per-contract P&L by yes-price band and by seconds to close")
    w("")
    for h in heads[:4]:
        r = by[h]
        w("**%s** -- by the yes price of our order:" % _rowkey(h))
        w("")
        w("| band | contracts | per contract | $ total |")
        w("|---|---|---|---|")
        for k in sorted(r["by_band"]):
            x = r["by_band"][k]
            w("| %d-%dc | %s | %s | %s |" % (k[0] // 10, k[1] // 10,
                                            format(int(x[1]), ","),
                                            _c(x[0] / x[1]) if x[1] else "n/a",
                                            _d(x[0])))
        w("")
        w("by seconds to close at the fill:")
        w("")
        w("| seconds left | contracts | per contract | $ total |")
        w("|---|---|---|---|")
        for k in sorted(r["by_tau"], reverse=True):
            x = r["by_tau"][k]
            lab = (">%d" % k[0]) if k[1] > 10 ** 8 else "%d-%d" % k
            w("| %s | %s | %s | %s |" % (lab, format(int(x[1]), ","),
                                        _c(x[0] / x[1]) if x[1] else "n/a",
                                        _d(x[0])))
        w("")
    # ---- 4. mechanism and pick-off
    w("### 4. Where the fills come from, and the pick-off")
    w("")
    w("`queue` = a print at our price consumed everything in front of us; "
      "`walk` = a taker cleared our level and kept going; `cross` = an "
      "order arrived that would have matched us before resting. `stale` = "
      "our price was no longer the touch when the millisecond began, i.e. "
      "we were filled during our own cancel/re-post round trip.")
    w("")
    w("| model | L ms | queue | walk | cross | stale fills | stale $ | "
      "stale per contract | bid $ | ask $ |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        v = r["variant"]
        m = r["by_mech"]
        st = r["stale"]
        bs = r["by_side"]
        w("| %s | %d | %s | %s | %s | %s (%.0f%%) | %s | %s | %s | %s |"
          % (v[0], v[1],
             format(m.get("queue", [0, 0, 0])[2], ","),
             format(m.get("walk", [0, 0, 0])[2], ","),
             format(m.get("cross", [0, 0, 0])[2], ","),
             format(st[2], ","), 100.0 * st[2] / max(1, r["n_fill"]),
             _d(st[0]), _c(st[0] / st[1]) if st[1] else "n/a",
             _d(bs.get(YES, [0, 0, 0])[0]), _d(bs.get(NO, [0, 0, 0])[0])))
    # ---- 5. inventory
    w("")
    w("### 5. Inventory at the close")
    w("")
    w("A bid fill and an ask fill in the same market cancel to the spread "
      "between them (`paired`); what is left is a one-sided position that "
      "settles at 0 or 100 (`inventory`). The cap is 10 net contracts a "
      "market.")
    w("")
    w("| model | L ms | markets with fills | one-sided at close | share | "
      "median abs net | p90 abs net | paired $ | inventory $ |")
    w("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        v = r["variant"]
        na = r["net_abs"]
        q = quantiles(na, (0.5, 0.9))
        w("| %s | %d | %s | %s | %.0f%% | %.1f | %.1f | %s | %s |"
          % (v[0], v[1], format(r["inv_markets"], ","),
             format(r["inv_nonzero"], ","),
             100.0 * r["inv_nonzero"] / max(1, r["inv_markets"]),
             q[0] or 0.0, q[1] or 0.0, _d(r["paired_pnl_c"]),
             _d(r["inv_pnl_c"])))
    # ---- 6. series
    w("")
    w("### 6. By series (per contract, $ total) for the headline variants")
    w("")
    w("| series | " + " | ".join(_rowkey(h) for h in heads[:4]) + " |")
    w("|---|" + "---|" * len(heads[:4]))
    sers = sorted({k for h in heads[:4] for k in by[h]["by_series"]})
    for s_ in sers:
        cells = []
        for h in heads[:4]:
            x = by[h]["by_series"].get(s_, [0.0, 0.0, 0])
            cells.append("%s, %s, %s fills"
                         % (_c(x[0] / x[1]) if x[1] else "n/a", _d(x[0]),
                            format(x[2], ",")))
        w("| %s | %s |" % (s_, " | ".join(cells)))
    # ---- 7. the old claim
    w("")
    w("### 7. Against the 2026-09-06 simulator's %s fills/day"
      % format(old_claim_per_day, ","))
    w("")
    per_sd_old = old_claim_per_day / float(old_claim_series)
    w("The old figure was 1 contract a side over %d series on the "
      "08-25..09-03 cache, i.e. about %s fills per series-day. This run "
      "covers 4 series, so the like-for-like old number is about %s "
      "fills/day."
      % (old_claim_series, format(int(per_sd_old), ","),
         format(int(per_sd_old * 4), ",")))
    w("")
    w("| model | L ms | fills/day here | per series-day | ratio to old |")
    w("|---|---|---|---|---|")
    for r in rows:
        v = r["variant"]
        fpd = r["n_fill"] / nd
        w("| %s | %d | %s | %s | %.2fx |" % (v[0], v[1], format(int(fpd), ","),
                                         format(int(fpd / 4), ","),
                                         fpd / (per_sd_old * 4)))
    w("")
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--out", default=None)
    ap.add_argument("--from", dest="h0", default=None)
    ap.add_argument("--to", dest="h1", default=None)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--report", default=None,
                    help="print the tables for a finished run directory")
    ap.add_argument("--cap", type=int, default=CAP)
    ap.add_argument("--cap-filter", type=int, default=None)
    ap.add_argument("--md", default=None,
                    help="with --report: append the result tables to this "
                         "markdown file")
    ap.add_argument("--md-title", default="## Results")
    ap.add_argument("--resume", action="store_true",
                    help="skip hours whose summary file already exists")
    a = ap.parse_args()
    if a.selftest:
        return 0 if selftest() else 1
    if not os.environ.get("KALS_SELFTESTED"):
        if not selftest(verbose=False):
            print("  self-test FAILED -- refusing to touch real data")
            return 1
        print("  self-test passed")
    if a.report:
        report(a.report, cap_filter=a.cap_filter)
        if a.md:
            write_md(a.report, a.md, title=a.md_title)
            print("  tables appended to %s" % a.md)
        return 0
    if not (a.out and a.h0 and a.h1):
        print("need --out, --from and --to")
        return 1
    lower_priority()
    fr = free_ram_mb()
    print("  free RAM %.0f MB, rss %.0f MB" % (fr, rss_mb()))
    if 0 <= fr < FREE_ABORT_MB:
        print("  refusing to start: free RAM under %d MB" % FREE_ABORT_MB)
        return 1
    hours = hour_list(a.h0, a.h1)
    okr = run_range(a.data, a.out, hours, cap=a.cap, resume=a.resume)
    return 0 if okr else 2


if __name__ == "__main__":
    sys.exit(main())
