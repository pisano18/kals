#!/usr/bin/env python3
# VERSION: 2026-09-08-pi2
"""pinimpact.py -- MARKET IMPACT.  What does it cost to buy 125 instead of 10?

WHY THIS FILE EXISTS

Two decisions worth real money rest on one unmeasured number.

  1. The live rule buys 10 contracts.  Across 19 live orders the median depth
     on offer when it fires is 125 contracts and the largest seen is 2,399, so
     we consume a few percent of the visible depth.  Taking the whole offer is
     ~12x the profit IF THE PRICE DOES NOT MOVE AGAINST US.  Nobody has
     measured whether it does.

  2. research/pinladder2.py prices a sweep of every EV-clearing level at
     $83.14 per close on $3,763 of capital, and its own last line says:
     "buying the whole ladder would move the price -- this assumes it does
     not, which flatters the sweep."  That assumption has never been tested.

WHAT IS MEASURED, AND FROM WHAT

  (a) TEMPORARY IMPACT / SLIPPAGE.  Kalshi reports one taker sweep as several
      prints, one per price level, all carrying the SAME `ts_ms`.  So a sweep
      is directly visible: group the trade channel by (market_ticker, ts_ms)
      and the group IS the walk down the book.  Two estimators, because each
      can fail in a way the other cannot:

          slip_own  = VWAP(group) - best price IN THE GROUP
          slip_tick = VWAP(group) - the `ticker` channel top of book at T-1s

      The first needs no other channel; the second is independent of the
      taker's own fills.  They are reported side by side and their difference
      is printed as TOUCH ALIGNMENT.  Units: CENTS PER CONTRACT.

  (b) PERMANENT IMPACT / REFILL.  The `ticker` channel republishes best bid,
      best ask and both sizes about once a second per market.  For each sweep,
      what a SECOND taker in the same direction would pay at T+1s / T+5s /
      T+15s versus T-1s.  Positive = the book did not come back.

  (c) THE POPULATION THAT MATTERS.  tau 3-30 s, market already decided.
      research/pinoffer.py measured that in a decided market the LOSING side's
      BID book is empty in 33,427 of 33,431 moments while the winning side
      carries a median 84 price levels.  So the decided tape splits into two
      populations that are NOT interchangeable and are never pooled here:

        SELL_WINNER  the taker walks the WINNING side's bid book (dumping a
                     near-certain winner into bids at >=95c).  Plentiful.
        BUY_WINNER   the taker consumes the LOSING side's bids, i.e. pays
                     >=95c for the near-certain winner.  THIS IS OUR TRADE.

      Membership is decided from the RESTING BID the print consumed, never
      from the outcome, so it is computable live.  Where fulltape knows the
      settlement the label is scored against it and the hit rate is printed.

  (d) The corrected numbers: what 10 / 125 / 530 / the whole ladder cost off
      the DISPLAYED book at tau 3-30, and the corrected pinladder2 sweep.

THE CONTROLS, because a busy book trends whether or not anybody sweeps

  * SLIPPAGE CONTROL: for every real group of k simultaneous prints, take the
    next k prints in the same market on the same taker side that are ADJACENT
    IN TIME BUT NEVER SIMULTANEOUS and run the identical statistic.  If the
    estimator merely read "prices move about", the control would score the
    same.  (Same control design that settled sweep shape in informed.py.)
  * REFILL CONTROL: market-seconds with NO trade in the current or preceding
    second, stratified by (taker direction, tau bucket, 5c price bucket) and
    differenced WITHIN STRATUM AND WITHIN HOUR.  A drift common to sweep and
    non-sweep moments cancels exactly; the self-test plants such a drift and
    checks that it does.
  * FADE DIAGNOSTIC (d1): the displayed touch minus the sweep's own touch.  If
    the book channel led the trade channel the displayed book would already be
    eaten and the fade estimate would be biased; the number says whether it is.

UNITS, DECIDED ONCE FROM THE WHOLE SAMPLE.  The tape writes prices as dollar
strings, "0.0010" to "0.9990": 0.1c to 99.9c on the tapered tick.  This file
multiplies by 100 exactly once, in `cents()`, and every number below is CENTS
PER CONTRACT.  Nothing here ever tests a price against 1.

CLUSTERING.  n is reported as CLOSES.  All nine crypto series settle on the
same quarter hour at rho ~ 0.8, so the cluster is the close timestamp and every
series inside it contributes to that one cluster.  Standard errors are
between-cluster, the MDE table is printed BEFORE the estimates, and no cell
with fewer than 30 closes is called significant.

READ-ONLY.  Opens files under C:\\kals\\kalshi_data for reading and writes
nothing at all.
"""
import argparse
import glob
import gzip
import json
import math
import os
import random
import sys
import time
import zlib
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from tdist import crit                                       # noqa: E402

DATA = r"C:\kals\kalshi_data"
FULLTAPE = r"C:\kals\fulltape\markets.json"

SERIES = ("KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M",
          "KXBNB15M", "KXZEC15M", "KXHYPE15M", "KXNEAR15M")

QUARTER = 900

# the first bucket starts at 0, not 1: count_fp is fractional on this tape
# (0.17 contracts is a real print) and a `lo=1` bucket silently threw those
# sweeps away.
N_BUCKETS = (("1-10", 0.0, 10.0), ("11-50", 10.0, 50.0),
             ("51-125", 50.0, 125.0), ("126-500", 125.0, 500.0),
             ("500+", 500.0, float("inf")))
TAU_BUCKETS = (("3-30", 3, 30), ("31-90", 31, 90), ("91-300", 91, 300),
               ("301-900", 301, 900))
HORIZONS = (1, 5, 15)

DECIDED_HI = 95.0        # resting bid >= 95c -> the taker sold a near-certainty
DECIDED_LO = 5.0         # resting bid <= 5c  -> the taker bought one

MIN_CLUSTERS = 30

# the live EV arithmetic, copied from research/pinladder2.py so the corrected
# profit is comparable line for line
MEASURED_FLIP = 0.0090
EV_FLOOR_C = 0.30        # cents per contract
GRID_SIZES = (10, 125, 530)
# The live rule's ceiling is 98.8c and its cheapest live fill so far was 89c,
# so the bands run down to 90c.  BELOW 95c THE "EV bought" COLUMN IS NOT
# TRUSTWORTHY: MEASURED_FLIP = 0.90% was calibrated on trades the model called
# >=98% certain, and applying it to a 92c contract is precisely the error that
# made pinladder2's first version print a 680%/day fantasy.  The cost and
# slippage columns are model-free and stand at every band.
PRICE_BANDS = ((90.0, 95.0), (95.0, 97.0), (97.0, 98.5), (98.5, 99.5),
               (99.5, 100.0))
EV_TRUSTED_FROM = 95.0


# ===========================================================================
# primitives -- the unit decision lives here and nowhere else
# ===========================================================================
def cents(x):
    """Tape price (a dollar string like '0.0050') -> cents (0.5).

    NEVER infer the unit from the magnitude.  The tick is tapered, so a half
    cent is written 0.0050 and an `x > 1` test would read it as fifty cents.
    """
    return round(100.0 * float(x), 4)


def billed_fee_c(p_c, n=1.0):
    """Kalshi's taker fee in CENTS for n contracts at price p_c cents."""
    p = p_c / 100.0
    return 100.0 * (math.ceil(0.07 * p * (1 - p) * n * 10000) / 10000)


def ev_c(p_c, flip=MEASURED_FLIP):
    """Expected profit in cents on ONE contract bought at p_c cents."""
    p = p_c / 100.0
    return 100.0 * ((1 - flip) * (1 - p) - flip * p) - billed_fee_c(p_c, 1.0)


def close_of(ts_ms):
    """The close second of the market a trade at ts_ms belongs to.

    Every 15-minute market closes on a quarter hour and lives exactly the
    quarter hour before it, so the close is the next 900-second boundary at or
    after the print.  Checked against fulltape on real data by
    `check_close_rule()` and asserted in the self-test.
    """
    return -(-int(ts_ms) // (QUARTER * 1000)) * QUARTER


def bucket_of(n, buckets):
    for name, lo, hi in buckets:
        if lo < n <= hi:
            return name
    return None


def tau_bucket_of(tau):
    for name, lo, hi in TAU_BUCKETS:
        if lo <= tau <= hi:
            return name
    return None


def band_of(p_c):
    for lo, hi in PRICE_BANDS:
        if lo <= p_c < hi:
            return f"{lo:.1f}-{hi:.1f}c"
    return None


def sweep_stat(prints):
    """One (ticker, ts_ms) group -> the sweep it represents, or None.

    prints: [(side, taker_cost_cents, qty)].  `side` is the taker side.
    """
    sides = set(p[0] for p in prints)
    if len(sides) != 1:
        return None                    # two takers in the same ms; not one sweep
    side = sides.pop()
    tot = 0.0
    costs = []
    for _s, c, q in prints:
        if q <= 0:
            continue
        tot += q
        costs.append((c, q))
    if tot <= 0 or not costs:
        return None
    touch = min(c for c, _ in costs)   # a marketable order fills the touch first
    # slippage as a weighted mean of (level - touch), NOT (sum/qty - touch):
    # the second form subtracts two large numbers and leaves 1e-16 of noise on
    # a group that never left the touch -- a false positive of exactly the
    # kind this file exists to avoid.
    slip = sum(q * (c - touch) for c, q in costs) / tot
    return {"side": side, "n": tot, "vwap": touch + slip, "touch": touch,
            "slip": slip, "worst": max(c for c, _ in costs) - touch,
            "levels": len(set(c for c, _ in costs)), "prints": len(prints),
            "bid_hit": 100.0 - touch}


def walk_cost(levels, want):
    """Cost of buying `want` contracts off a displayed ladder.

    levels: [(cost_cents, size)] in ANY order; cheapest is taken first.
    returns (filled, total_cost_cents, ev_cents_earned).  Partial fills are
    honest -- a thin ladder gives you less than you asked for and that IS the
    answer.
    """
    got = 0.0
    cost = 0.0
    evc = 0.0
    for c, s in sorted(levels):
        if got >= want:
            break
        take = min(s, want - got)
        got += take
        cost += take * c
        evc += take * ev_c(c)
    return got, cost, evc


def ev_gated(levels):
    """The sub-ladder pinladder2 would actually buy."""
    return [(c, s) for c, s in levels if ev_c(c) >= EV_FLOOR_C]


# ===========================================================================
# clustered inference -- n is CLOSES
# ===========================================================================
class Acc:
    __slots__ = ("n", "s", "ss")

    def __init__(self):
        self.n = 0
        self.s = 0.0
        self.ss = 0.0

    def add(self, x):
        self.n += 1
        self.s += x
        self.ss += x * x

    @property
    def mean(self):
        return self.s / self.n if self.n else float("nan")


def new_cell():
    return defaultdict(Acc)            # cluster (close second) -> Acc


def clustered(cell, alpha=0.05, power_z=0.8416):
    """Between-cluster mean, se, t and MDE for one cell.

    The MDE is what this cell COULD have detected at 80% power, and it is
    printed before any estimate is read.  "No impact" and "no power to detect
    impact" are different results.
    """
    if not cell:
        return None
    ms = [a.mean for a in cell.values() if a.n > 0]
    k = len(ms)
    if k < 2:
        return None
    m = sum(ms) / k
    var = sum((x - m) ** 2 for x in ms) / (k - 1)
    sd = math.sqrt(var)
    se = sd / math.sqrt(k)
    tc = crit(alpha, k - 1)
    return {"mean": m, "sd": sd, "se": se, "k": k,
            "obs": sum(a.n for a in cell.values()),
            "t": (m / se) if se > 0 else 0.0,
            "mde": (tc + power_z) * se,
            "lo": m - tc * se, "hi": m + tc * se}


def fmt(r, unit="c"):
    if r is None:
        return "        --"
    star = "" if r["k"] >= MIN_CLUSTERS else "  (k<30, NOT significant)"
    return (f"{r['mean']:+8.3f}{unit}  t={r['t']:+6.2f}  "
            f"MDE {r['mde']:6.3f}{unit}  closes {r['k']:>5,}  "
            f"obs {r['obs']:>10,}{star}")


# ===========================================================================
# tape readers -- string slicing, because json.loads on 5.5M deltas an hour is
# the whole runtime
# ===========================================================================
def hour_files(channel, hours, end_skip=1):
    fs = sorted(glob.glob(os.path.join(DATA, channel, "2026*.jsonl.gz")))
    if end_skip:
        fs = fs[:-end_skip]            # the newest file is still being written
    return fs[-hours:] if hours else fs


def _str_field(line, key, start=0):
    """Value of a "key":"value" pair, or None."""
    i = line.find(key, start)
    if i < 0:
        return None, start
    i += len(key)
    j = line.find('"', i)
    return line[i:j], j


def _num_field(line, key, start=0):
    i = line.find(key, start)
    if i < 0:
        return None, start
    i += len(key)
    j = i
    n = len(line)
    while j < n and (line[j].isdigit() or line[j] in "-+.eE"):
        j += 1
    try:
        return float(line[i:j]), j
    except ValueError:
        return None, j


def read_trades(path, series=SERIES):
    """Yield (ticker, ts_ms, side, taker_cost_cents, qty) for wanted series.

    A taker buying YES pays yes_price; a taker buying NO pays no_price.  Block
    trades are dropped.
    """
    try:
        fh = gzip.open(path, "rt")
    except (EOFError, zlib.error, OSError):
        return
    try:
        for line in fh:
            i = line.find('"market_ticker":"')
            if i < 0:
                continue
            j = line.find('"', i + 17)
            tk = line[i + 17:j]
            if not tk.startswith(series):
                continue
            if '"is_block_trade":true' in line:
                continue
            side, _ = _str_field(line, '"taker_side":"', j)
            if side is None:
                continue
            key = ('"yes_price_dollars":"' if side == "yes"
                   else '"no_price_dollars":"')
            px, _ = _str_field(line, key, j)
            q, _ = _num_field(line, '"count_fp":"', j)
            ts, _ = _num_field(line, '"ts_ms":', j)
            if px is None or q is None or ts is None:
                continue
            try:
                yield tk, int(ts), side, cents(px), q
            except ValueError:
                continue
    except (EOFError, zlib.error, OSError):
        return
    finally:
        try:
            fh.close()
        except Exception:
            pass


def read_ticker(path, series=SERIES):
    """Yield (ticker, ts_ms, yes_bid_c, yes_ask_c, bid_size, ask_size)."""
    try:
        fh = gzip.open(path, "rt")
    except (EOFError, zlib.error, OSError):
        return
    try:
        for line in fh:
            i = line.find('"market_ticker":"')
            if i < 0:
                continue
            j = line.find('"', i + 17)
            tk = line[i + 17:j]
            if not tk.startswith(series):
                continue
            yb, _ = _str_field(line, '"yes_bid_dollars":"', j)
            ya, _ = _str_field(line, '"yes_ask_dollars":"', j)
            bs, _ = _num_field(line, '"yes_bid_size_fp":"', j)
            asz, _ = _num_field(line, '"yes_ask_size_fp":"', j)
            ts, _ = _num_field(line, '"ts_ms":', j)
            if yb is None or ya is None or ts is None:
                continue
            try:
                yield (tk, int(ts), cents(yb), cents(ya),
                       bs or 0.0, asz or 0.0)
            except ValueError:
                continue
    except (EOFError, zlib.error, OSError):
        return
    finally:
        try:
            fh.close()
        except Exception:
            pass


def read_deltas(path, series=SERIES):
    """Yield (ticker, ts_ms, side, price_cents, delta_qty)."""
    try:
        fh = gzip.open(path, "rt")
    except (EOFError, zlib.error, OSError):
        return
    try:
        for line in fh:
            i = line.find('"market_ticker":"')
            if i < 0:
                continue
            j = line.find('"', i + 17)
            tk = line[i + 17:j]
            if not tk.startswith(series):
                continue
            px, _ = _str_field(line, '"price_dollars":"', j)
            dq, _ = _num_field(line, '"delta_fp":"', j)
            side, _ = _str_field(line, '"side":"', j)
            ts, _ = _num_field(line, '"ts_ms":', j)
            if px is None or dq is None or side is None or ts is None:
                continue
            try:
                yield tk, int(ts), side, cents(px), dq
            except ValueError:
                continue
    except (EOFError, zlib.error, OSError):
        return
    finally:
        try:
            fh.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# top-of-book helpers.  The ticker channel writes yes_ask "1.0000" when there
# is NO ask and yes_bid "0.0000" when there is no bid, so a cost of exactly
# 100c means "unbuyable", not "expensive".  The previous version of this file
# had no such guard on the sweep side and would have booked those 100c
# non-quotes as real prices.
# ---------------------------------------------------------------------------
def cost_at(row, side):
    """What a taker going `side` would pay per contract, or None if unquoted."""
    _tk, _ts, ybid, yask, _bs, _as = row
    c = yask if side == "yes" else 100.0 - ybid
    return c if 0.0 < c < 100.0 else None


def size_at(row, side):
    _tk, _ts, _yb, _ya, bs, asz = row
    return asz if side == "yes" else bs


def idx_before(rows, ts):
    """Index of the last row strictly before ts (binary search)."""
    lo, hi = 0, len(rows)
    while lo < hi:
        mid = (lo + hi) // 2
        if rows[mid][1] < ts:
            lo = mid + 1
        else:
            hi = mid
    return lo - 1


def idx_at_or_after(rows, ts):
    lo, hi = 0, len(rows)
    while lo < hi:
        mid = (lo + hi) // 2
        if rows[mid][1] < ts:
            lo = mid + 1
        else:
            hi = mid
    return lo if lo < len(rows) else -1


def event_delta(rows, ts, side, h):
    """(base_cost, cost_change, i_base, i_future) over [last row before ts,
    ts+h], or None.

    Used for BOTH the sweep and its control, so the two can never be measured
    over windows of different length.  The self-test plants a pure drift and
    fails if they differ: an earlier version took the sweep's base at T-1s and
    the control's at T, which turned a 0.10c/s drift into a spurious +0.10c of
    "impact" at every horizon.
    """
    ib = idx_before(rows, ts)
    if ib < 0 or ts - rows[ib][1] > 3000:
        return None
    base = cost_at(rows[ib], side)
    if base is None:
        return None
    ia = idx_at_or_after(rows, ts + h * 1000)
    if ia < 0 or rows[ia][1] - (ts + h * 1000) > 2000:
        return None
    nxt = cost_at(rows[ia], side)
    if nxt is None:
        return None
    return base, nxt - base, ib, ia


def quiet_window(traded_secs, sec, h):
    """True if nothing traded in this market from sec-1 through sec+h.

    A control has to be a window in which NOBODY swept, or it absorbs the very
    impact it is meant to net out.  Under the looser "no trade at sec or
    sec-1" rule the self-test's permanent-impact world returned +0.32c where
    +2.00c was planted, because the control window kept running into the NEXT
    sweep.  The direction of that bias is therefore known and recorded: a
    looser control UNDERSTATES impact.
    """
    for k in range(-1, h + 1):
        if (sec + k) in traded_secs:
            return False
    return True


def stratum_of(side, tau, base_c):
    """The refill control's matching key."""
    tb = tau_bucket_of(tau)
    if tb is None:
        return None
    return (side, tb, int(base_c // 5) * 5)


def adjust(delta, stratum, ctl):
    """Sweep change minus its matched control change, or None if unmatched.

    ctl: {stratum: [sum, n]} for one horizon within one hour.
    """
    v = ctl.get(stratum)
    if not v or v[1] < 5:
        return None
    return delta - v[0] / v[1]


# ===========================================================================
# (a) + (b) + (c) -- one pass over trade + ticker
# ===========================================================================
def population_of(sw, tau):
    """Which decided population this sweep belongs to, from the RESTING BID."""
    if not (3 <= tau <= 30):
        return "LIVE"
    if sw["bid_hit"] >= DECIDED_HI:
        return "SELL_WINNER"
    if sw["bid_hit"] <= DECIDED_LO:
        return "BUY_WINNER"
    return "UNDECIDED"


def scan(hours, verbose=True, series=SERIES, seed=7, ctl_frac=0.25,
         settled=None):
    """Stage (a)+(b)+(c).  Returns (cells, meta, size_samples, label_check)."""
    rnd = random.Random(seed)
    tfiles = hour_files("trade", hours)
    tickby = {os.path.basename(p)[:11]: p for p in sorted(glob.glob(
        os.path.join(DATA, "ticker", "2026*.jsonl.gz")))}
    tkeys = sorted(tickby)

    C = {
        "slip": defaultdict(new_cell),      # (pop, nbucket)
        "slip_ctl": defaultdict(new_cell),
        "slip_tick": defaultdict(new_cell),
        "worst": defaultdict(new_cell),
        "align": defaultdict(new_cell),     # (pop,)
        "imp": defaultdict(new_cell),       # (pop, nbucket, h) raw
        "imp_adj": defaultdict(new_cell),   # (pop, nbucket, h) control-matched
        "imp_ctl": defaultdict(new_cell),   # (h,) pooled control level
        "dep": defaultdict(new_cell),       # (pop, nbucket, h) depth ratio
    }
    meta = defaultdict(int)
    sizes = defaultdict(list)
    label = defaultdict(int)

    for tf in tfiles:
        stamp = os.path.basename(tf)[:11]
        if stamp not in tickby:
            meta["hours_no_ticker"] += 1
            continue
        k = tkeys.index(stamp)
        top = defaultdict(list)
        for row in read_ticker(tickby[stamp], series):
            top[row[0]].append(row)
        if k + 1 < len(tkeys):
            # the next hour too, so a T+15s horizon that crosses the hour
            # boundary is not silently scored as missing
            for row in read_ticker(tickby[tkeys[k + 1]], series):
                if row[0] in top:
                    top[row[0]].append(row)
        for v in top.values():
            v.sort(key=lambda r: r[1])

        groups = defaultdict(list)
        seq = defaultdict(list)
        for tk, ts, side, cost, q in read_trades(tf, series):
            groups[(tk, ts)].append((side, cost, q))
            seq[tk].append((ts, side, cost, q))
        for v in seq.values():
            v.sort(key=lambda x: x[0])
        pos = {}
        for tk, v in seq.items():
            d = {}
            for i, rec in enumerate(v):
                d.setdefault(rec[0], i)
            pos[tk] = d

        traded = defaultdict(set)
        for (tk, ts) in groups:
            traded[tk].add(ts // 1000)

        # ---- the refill CONTROL first, so sweeps can be differenced within
        #      hour and within stratum
        ctl = {h: defaultdict(lambda: [0.0, 0]) for h in HORIZONS}
        for tk, rows in top.items():
            tr = traded.get(tk, set())
            for r in rows:
                ts = r[1]
                sec = ts // 1000
                if sec in tr or (sec - 1) in tr:
                    continue
                if rnd.random() > ctl_frac:
                    continue
                close = close_of(ts)
                tau = close - ts / 1000.0
                if not (0 <= tau <= QUARTER):
                    continue
                for h in HORIZONS:
                    if not quiet_window(tr, sec, h):
                        meta["ctl_window_had_a_trade"] += 1
                        continue
                    for side in ("yes", "no"):
                        ed = event_delta(rows, ts, side, h)
                        if ed is None:
                            continue
                        base, d, _ib, _ia = ed
                        st = stratum_of(side, tau, base)
                        if st is None:
                            continue
                        cell = ctl[h][st]
                        cell[0] += d
                        cell[1] += 1
                        C["imp_ctl"][(h,)][close].add(d)
                        meta["ctl_obs"] += 1

        # ---- sweeps
        for (tk, ts), prints in groups.items():
            meta["groups"] += 1
            sw = sweep_stat(prints)
            if sw is None:
                meta["dropped_mixed_side"] += 1
                continue
            close = close_of(ts)
            tau = close - ts / 1000.0
            if not (0 <= tau <= QUARTER):
                meta["dropped_tau"] += 1
                continue
            nb = bucket_of(sw["n"], N_BUCKETS)
            if nb is None:
                meta["dropped_zero_size"] += 1
                continue
            pop = population_of(sw, tau)
            meta["kept"] += 1
            meta["pop_" + pop] += 1
            if settled is not None and pop in ("BUY_WINNER", "SELL_WINNER"):
                res = settled.get(tk)
                if res is not None:
                    won_yes = res >= 0.5
                    right = (sw["side"] == "yes") == won_yes
                    label[pop + ("_right" if right else "_wrong")] += 1

            for key in ((pop, nb), ("ALL", nb)):
                C["slip"][key][close].add(sw["slip"])
                C["worst"][key][close].add(sw["worst"])
                if len(sizes[key]) < 200000:
                    sizes[key].append(sw["n"])

            # ---- slippage control: the next k prints, same side, never
            #      simultaneous with one another
            i0 = pos.get(tk, {}).get(ts)
            if i0 is not None:
                v = seq[tk]
                want = sw["prints"]
                got = []
                seen_ts = set()
                j = i0 + len(prints)
                while j < len(v) and len(got) < want:
                    tj, sj, cj, qj = v[j]
                    if tj - ts > 30000:
                        break
                    if sj == sw["side"] and tj not in seen_ts:
                        seen_ts.add(tj)
                        got.append((sj, cj, qj))
                    j += 1
                if len(got) == want:
                    cs = sweep_stat(got)
                    if cs is not None:
                        for key in ((pop, nb), ("ALL", nb)):
                            C["slip_ctl"][key][close].add(cs["slip"])

            # ---- permanent impact from the ticker top of book
            rows = top.get(tk)
            if not rows:
                meta["no_ticker"] += 1
                continue
            ib = idx_before(rows, ts)
            if ib < 0 or ts - rows[ib][1] > 3000:
                meta["no_pre_ticker"] += 1
                continue
            base0 = cost_at(rows[ib], sw["side"])
            if base0 is None:
                meta["pre_ticker_unquoted"] += 1
                continue
            base_sz = size_at(rows[ib], sw["side"])
            C["align"][(pop,)][close].add(base0 - sw["touch"])
            for key in ((pop, nb), ("ALL", nb)):
                C["slip_tick"][key][close].add(sw["vwap"] - base0)
            st = stratum_of(sw["side"], tau, base0)
            for h in HORIZONS:
                ed = event_delta(rows, ts, sw["side"], h)
                if ed is None:
                    continue
                _base, d, _ib, ia = ed
                for key in ((pop, nb, h), ("ALL", nb, h)):
                    C["imp"][key][close].add(d)
                if st is not None:
                    adj = adjust(d, st, ctl[h])
                    if adj is not None:
                        for key in ((pop, nb, h), ("ALL", nb, h)):
                            C["imp_adj"][key][close].add(adj)
                if base_sz > 0:
                    sz = size_at(rows[ia], sw["side"])
                    # SHARE of the pre-sweep depth that is back, capped at 1.
                    # The raw ratio is unusable: a touch holding 0.01 contracts
                    # before the sweep and 60 after scores 6,000x and one such
                    # moment owns the mean.  Capped, 1.00 reads as "the depth
                    # is fully back" and 0.30 as "only 30% of it returned".
                    for key in ((pop, nb, h), ("ALL", nb, h)):
                        C["dep"][key][close].add(min(sz / base_sz, 1.0))

        if verbose:
            print(f"    {stamp}  groups {meta['groups']:,}  kept "
                  f"{meta['kept']:,}  ctl {meta['ctl_obs']:,}", flush=True)
        groups.clear()
        seq.clear()
        pos.clear()
        top.clear()
        ctl.clear()

    return C, meta, sizes, label


# ===========================================================================
# (d) the DISPLAYED ladder, from a book replay
# ===========================================================================
SNAP_KEYS = (("yes_dollars_fp", "no_dollars_fp"), ("yes_dollars", "no_dollars"))


def seed_book(msg, book):
    """Seed a book from an orderbook_snapshot message; returns the key used.

    research/pindata.py reads msg['yes_dollars']/['no_dollars'].  Every
    non-empty snapshot on this tape carries the book under 'yes_dollars_fp' /
    'no_dollars_fp' (1,027 of 1,027 non-empty snapshots in a 20-file sample),
    so pindata's seed is ALWAYS empty.  Both keys are tried here.
    """
    y, n = book
    for ky, kn in SNAP_KEYS:
        if msg.get(ky) or msg.get(kn):
            for key, d in ((ky, y), (kn, n)):
                for pr in (msg.get(key) or []):
                    try:
                        p, q = round(cents(pr[0]), 4), float(pr[1])
                    except (TypeError, ValueError, IndexError):
                        continue
                    if q > 0:
                        d[p] = d.get(p, 0.0) + q
            return ky
    return None


def apply_delta(book, side, price_c, dq):
    d = book[0] if side == "yes" else book[1]
    p = round(price_c, 4)
    v = d.get(p, 0.0) + dq
    if v <= 1e-9:
        d.pop(p, None)
    else:
        d[p] = v


def ladder_for(book, side):
    """Cost ladder [(cost_cents, size)] for a taker buying `side`.

    Buying YES means crossing resting NO bids, so cost = 100 - (no bid).
    """
    src = book[1] if side == "yes" else book[0]
    return [(round(100.0 - p, 4), s) for p, s in src.items() if s > 0]


def replay_books(hours, verbose=True, series=SERIES, sizes=GRID_SIZES,
                 birth_guard=800):
    """Replay orderbook_snapshot + orderbook_delta and answer two questions
    the trade channel cannot.

    d1. DOES THE DISPLAYED LADDER FILL?  For every real sweep, walk the
        PRE-SWEEP displayed book for the sweep's own size and compare the cost
        against what the taker actually paid.  Positive = quotes left when
        they were hit.  The displayed-touch-minus-sweep-touch diagnostic says
        whether the two channels are aligned in time.
    d2. WHAT DOES BUYING n COST US?  On an exogenous 1-second grid at tau
        3-30, wherever a near-certain side (cost >= 95c) is buyable, price
        10 / 125 / 530 / the whole ladder / the EV-gated ladder off the
        displayed book.

    Books are rebuilt per hour file.  Every 15-minute market is born and dies
    inside one hour file, so a delta-only replay of that file is complete from
    the market's birth -- but only if we saw the birth.  `birth_guard` seconds
    of observed life are required before a market is scored, and the rejects
    are counted so the guard cannot silently discard everything.
    """
    dfiles = hour_files("orderbook_delta", hours)
    snapall = {os.path.basename(p)[:11]: p for p in sorted(glob.glob(
        os.path.join(DATA, "orderbook_snapshot", "2026*.jsonl.gz")))}
    tradeby = {os.path.basename(p)[:11]: p for p in sorted(glob.glob(
        os.path.join(DATA, "trade", "2026*.jsonl.gz")))}

    R = {
        "fade": defaultdict(new_cell),       # (nbucket,) realised - displayed
        "fillable": defaultdict(new_cell),
        "touchdiff": defaultdict(new_cell),  # (nbucket,) displayed - sweep touch
        "cost": defaultdict(new_cell),       # (band, want) cents over touch
        "vwap": defaultdict(new_cell),       # (band, want) absolute vwap
        "avail": defaultdict(new_cell),      # (band, want) share fillable
        "profit": defaultdict(new_cell),     # (band, want) cents of EV bought
        "got": defaultdict(new_cell),        # (band, want) contracts filled
        "depth": defaultdict(new_cell),      # (band,) contracts on the ladder
        "touchsz": defaultdict(new_cell),    # (band,) contracts AT the touch
    }
    meta = defaultdict(int)

    for df in dfiles:
        stamp = os.path.basename(df)[:11]
        books = defaultdict(lambda: ({}, {}))
        birth = {}
        sp = snapall.get(stamp)
        if sp:
            try:
                with gzip.open(sp, "rt") as fh:
                    for line in fh:
                        i = line.find('"market_ticker":"')
                        if i < 0:
                            continue
                        j = line.find('"', i + 17)
                        tk = line[i + 17:j]
                        if not tk.startswith(series):
                            continue
                        try:
                            m = json.loads(line)["msg"]
                        except (ValueError, KeyError):
                            continue
                        key = seed_book(m, books[tk])
                        meta["seeded_" + key if key else "snap_empty"] += 1
                        if key:
                            birth[tk] = 0      # seeded: treat as fully known
            except (EOFError, zlib.error, OSError):
                pass

        sweeps = defaultdict(list)
        tp = tradeby.get(stamp)
        if tp:
            g = defaultdict(list)
            for tk, ts, side, cost, q in read_trades(tp, series):
                g[(tk, ts)].append((side, cost, q))
            for (tk, ts), v in g.items():
                s = sweep_stat(v)
                if s is not None:
                    sweeps[tk].append((ts, s))
            g.clear()
        for v in sweeps.values():
            v.sort(key=lambda x: x[0])
        cursor = defaultdict(int)
        grid_done = defaultdict(set)
        first_bite = set()

        for tk, ts, side, pc, dq in read_deltas(df, series):
            bk = books[tk]
            if tk not in birth:
                birth[tk] = ts // 1000

            # ---- score every sweep at or before this delta, on the book as
            #      it stood BEFORE the delta lands
            pl = sweeps.get(tk)
            if pl:
                c = cursor[tk]
                while c < len(pl) and pl[c][0] <= ts:
                    sts, sw = pl[c]
                    c += 1
                    close = close_of(sts)
                    if close - birth[tk] < birth_guard:
                        meta["sweep_book_incomplete"] += 1
                        continue
                    lad = ladder_for(bk, sw["side"])
                    if not lad:
                        meta["sweep_ladder_empty"] += 1
                        continue
                    nb = bucket_of(sw["n"], N_BUCKETS)
                    if nb is None:
                        continue
                    got, cost, _ = walk_cost(lad, sw["n"])
                    if got > 0:
                        R["fillable"][(nb,)][close].add(got / sw["n"])
                        R["touchdiff"][(nb,)][close].add(
                            min(x for x, _ in lad) - sw["touch"])
                    if got >= sw["n"] - 1e-9:
                        R["fade"][(nb,)][close].add(sw["vwap"] - cost / got)
                        meta["sweep_scored"] += 1
                    else:
                        meta["sweep_ladder_thin"] += 1
                cursor[tk] = c

            # ---- the exogenous tau 3-30 one-second grid
            sec = ts // 1000
            close = close_of(ts)
            tau = close - sec
            if 3 <= tau <= 30 and sec not in grid_done[tk]:
                grid_done[tk].add(sec)
                if close - birth[tk] < birth_guard:
                    meta["grid_book_incomplete"] += 1
                else:
                    meta["grid_seconds"] += 1
                    hit = False
                    for buy in ("yes", "no"):
                        lad = ladder_for(bk, buy)
                        if not lad:
                            continue
                        touch = min(c for c, _ in lad)
                        band = band_of(touch)
                        if band is None:
                            continue        # not a near-certain buy
                        hit = True
                        meta["grid_buyable"] += 1
                        # FIRST-BITE: the earliest second in this market's
                        # final 30 s at which anything near-certain could be
                        # bought.  That is when the live rule fires, and it is
                        # ONE observation per market, so the per-close numbers
                        # are a bite that could actually be taken rather than
                        # an average over 28 re-reads of the same book.
                        firsts = ()
                        if tk not in first_bite:
                            first_bite.add(tk)
                            meta["grid_first_bite"] += 1
                            firsts = ("FIRST:" + band, "FIRST:ALL")
                        tot = sum(s for _, s in lad)
                        tsz = sum(s for c, s in lad if c == touch)
                        for b in ((band,), ("ALL",)) + tuple((x,)
                                                             for x in firsts):
                            R["depth"][b][close].add(tot)
                            R["touchsz"][b][close].add(tsz)
                        gate = ev_gated(lad)
                        for want, ll in ([(w, lad) for w in sizes]
                                         + [("all", lad), ("ev_gated", gate)]):
                            if not ll:
                                continue
                            n_want = (sum(s for _, s in ll)
                                      if isinstance(want, str) else want)
                            if n_want <= 0:
                                continue
                            got, cost, evc = walk_cost(ll, n_want)
                            if got <= 0:
                                continue
                            for key in ([(band, want), ("ALL", want)]
                                        + [(b, want) for b in firsts]):
                                R["cost"][key][close].add(cost / got - touch)
                                R["vwap"][key][close].add(cost / got)
                                R["avail"][key][close].add(got / n_want)
                                R["profit"][key][close].add(evc)
                                R["got"][key][close].add(got)
                    if not hit:
                        meta["grid_no_near_certain"] += 1

            apply_delta(bk, side, pc, dq)

        if verbose:
            print(f"    book {stamp}  scored {meta['sweep_scored']:,}  "
                  f"grid {meta['grid_seconds']:,}  "
                  f"buyable {meta['grid_buyable']:,}", flush=True)
        books.clear()
        sweeps.clear()
        grid_done.clear()
    return R, meta


# ===========================================================================
# real-data sanity checks
# ===========================================================================
def load_settled():
    if not os.path.exists(FULLTAPE):
        return {}, {}
    res, cl = {}, {}
    try:
        d = json.load(open(FULLTAPE, encoding="utf-8"))
    except (ValueError, OSError):
        return {}, {}
    for v in d.values():
        for r in v:
            if r["series"] in SERIES:
                res[r["ticker"]] = float(r["result"])
                cl[r["ticker"]] = int(float(r["close"]))
    return res, cl


def check_close_rule(closes, hours=3):
    """Does close_of() reproduce fulltape's close on real trade prints?"""
    if not closes:
        return None
    agree = dis = unk = 0
    for tf in hour_files("trade", hours):
        for tk, ts, _s, _c, _q in read_trades(tf):
            a = closes.get(tk)
            if a is None:
                unk += 1
            elif a == close_of(ts):
                agree += 1
            else:
                dis += 1
    return agree, dis, unk


# ===========================================================================
# SELF-TEST -- plant a known impact function and recover it; plant nothing and
# get nothing back.  This is the deliverable; the estimator is the easy part.
# ===========================================================================
PLANTED_LADDER = [(90.0, 10.0), (91.0, 40.0), (92.0, 75.0),
                  (93.0, 375.0), (94.0, 1500.0)]


def _mk(side, price_c, qty):
    return (side, price_c, qty)


def _analytic_slip(want):
    got, cost, _ = walk_cost(PLANTED_LADDER, want)
    return cost / got - PLANTED_LADDER[0][0]


def _mk_ticker(tk, sec, cost_yes, bs=100.0, asz=100.0):
    """A ticker row whose 'yes' taker cost is cost_yes."""
    return (tk, sec * 1000, 100.0 - cost_yes, cost_yes, bs, asz)


def selftest(verbose=True):
    print("SELF-TEST -- pinimpact")
    fails = []

    def ck(c, m):
        if verbose or not c:
            print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    # ---- 0. units, decided once, never inferred from magnitude ----------
    ck(abs(cents("0.0050") - 0.5) < 1e-12,
       "a half-cent quote '0.0050' reads as 0.5c, not 50c")
    ck(abs(cents("0.9990") - 99.9) < 1e-12, "'0.9990' reads as 99.9c")
    ck(abs(cents("0.5000") - 50.0) < 1e-12, "'0.5000' reads as 50c")
    ck(abs(billed_fee_c(16.0, 12.37) - 11.64) < 1e-9,
       f"the fee reproduces the operator's real charge of $0.1164 on 12.37 "
       f"contracts at 16c ({billed_fee_c(16.0, 12.37):.4f}c)")

    # ---- 1. the close rule ----------------------------------------------
    ck(close_of(1788879600000) == 1788879600,
       "a trade exactly on a quarter hour belongs to that close")
    ck(close_of(1788879600001) == 1788879600 + 900,
       "one ms later it belongs to the next close")
    ck(close_of(1788879599999) == 1788879600,
       "one ms earlier it belongs to this close")

    # ---- 2. the ladder walk ---------------------------------------------
    got, cost, _ = walk_cost(PLANTED_LADDER, 5)
    ck(got == 5 and abs(cost - 450.0) < 1e-9,
       "5 contracts fill entirely at the 90c touch")
    got, cost, _ = walk_cost(PLANTED_LADDER, 125)
    ck(got == 125 and abs(cost / got - 91.52) < 1e-9,
       f"125 contracts VWAP 91.52c off the planted ladder ({cost/got:.4f})")
    got, cost, _ = walk_cost(PLANTED_LADDER, 99999)
    ck(abs(got - 2000.0) < 1e-9,
       "asking for more than the ladder holds returns a PARTIAL fill, not a lie")
    _g, _c, evc = walk_cost([(97.0, 10.0)], 10)
    ck(abs(evc - 10 * ev_c(97.0)) < 1e-12 and 1.5 < ev_c(97.0) < 2.5,
       f"EV at 97c is {ev_c(97.0):.3f}c per contract and scales with size")
    ck(ev_c(99.5) < 0 < ev_c(96.0),
       "the EV test rejects the dear end and accepts 96c")

    # ---- 3. the estimator recovers the planted impact function ----------
    cells = defaultdict(new_cell)
    for c in range(60):
        close = 1788800000 + c * 900
        for want in (5, 30, 100, 300, 1200):
            prints = []
            rem = want
            for pc, sz in PLANTED_LADDER:
                if rem <= 0:
                    break
                take = min(sz, rem)
                rem -= take
                prints.append(_mk("yes", pc, take))
            sw = sweep_stat(prints)
            cells[bucket_of(sw["n"], N_BUCKETS)][close].add(sw["slip"])
    for want, nb in ((5, "1-10"), (30, "11-50"), (100, "51-125"),
                     (300, "126-500"), (1200, "500+")):
        r = clustered(cells[nb])
        planted = _analytic_slip(want)
        ck(r is not None and abs(r["mean"] - planted) < 1e-9,
           f"bucket {nb:>8}: recovered {r['mean']:.4f}c, planted "
           f"{planted:.4f}c")
    ck(clustered(cells["500+"])["mean"]
       > clustered(cells["1-10"])["mean"] + 1.0,
       "and the recovered impact function is increasing in size, by over 1c")

    # ---- 4. a world with NO impact returns nothing -----------------------
    flat = defaultdict(new_cell)
    rnd = random.Random(12)
    for c in range(60):
        close = 1788800000 + c * 900
        touch = rnd.uniform(20.0, 95.0)      # the price wanders between closes
        for want in (5, 30, 100, 300, 1200):
            sw = sweep_stat([_mk("yes", touch, want)])
            flat[bucket_of(sw["n"], N_BUCKETS)][close].add(sw["slip"])
    worst = 0.0
    for nb, _lo, _hi in N_BUCKETS:
        r = clustered(flat[nb])
        worst = max(worst, abs(r["mean"]))
        ck(abs(r["mean"]) < 1e-12 and abs(r["t"]) < 2.0,
           f"null world, bucket {nb:>8}: {r['mean']:.2e}c, |t| {abs(r['t']):.2f}")
    ck(worst == 0.0, "the no-impact world returns EXACTLY zero, not 'small'")

    wander = new_cell()
    rnd = random.Random(112)
    for c in range(60):
        close = 1788800000 + c * 900
        for _ in range(20):
            p = rnd.uniform(1.0, 99.0)
            sw = sweep_stat([_mk("no", p, 40.0), _mk("no", p, 60.0)])
            wander[close].add(sw["slip"])
    ck(clustered(wander)["mean"] == 0.0,
       "many prints at ONE price is not a walk, whatever the price is")

    # ---- 5. a sweep whose prints are not simultaneous is not a sweep -----
    ck(sweep_stat([_mk("yes", 90.0, 10), _mk("no", 91.0, 10)]) is None,
       "two takers in the same millisecond are not one sweep")
    b = sweep_stat([_mk("yes", 90.0, 10)])
    ck(b is not None and b["slip"] == 0.0 and b["bid_hit"] == 10.0,
       "a single print has zero slippage and its bid_hit is 100 - cost")
    ck(population_of(sweep_stat([_mk("yes", 97.0, 5)]), 10) == "BUY_WINNER",
       "paying 97c at tau=10 is BUYING the near-certain winner")
    ck(population_of(sweep_stat([_mk("yes", 3.0, 5)]), 10) == "SELL_WINNER",
       "paying 3c at tau=10 means the resting bid was 97c: somebody SOLD one")
    ck(population_of(sweep_stat([_mk("yes", 50.0, 5)]), 10) == "UNDECIDED",
       "a coin flip is neither")
    ck(population_of(sweep_stat([_mk("yes", 97.0, 5)]), 400) == "LIVE",
       "and tau 400 is outside the population that matters")

    # ---- 6. the 100c non-quote guard -------------------------------------
    ck(cost_at(_mk_ticker("T", 10, 100.0), "yes") is None,
       "yes_ask '1.0000' means NO ASK and must not be read as a 100c price")
    ck(cost_at(("T", 10000, 0.0, 50.0, 0.0, 5.0), "no") is None,
       "yes_bid '0.0000' means NO BID, so buying NO is unquoted, not 100c")
    ck(abs(cost_at(_mk_ticker("T", 10, 97.0), "yes") - 97.0) < 1e-9,
       "a real quote passes the guard unchanged")

    # ---- 7. permanent impact: recovered when planted, zero when not ------
    def refill_world(decay, drift=0.0, n_close=60):
        """Ticker rows where a sweep at T raises the cost by 2c and it decays
        at `decay` per second, plus a drift on EVERY second whether or not
        anybody swept."""
        raw = defaultdict(new_cell)
        adj = defaultdict(new_cell)
        ctlcell = defaultdict(new_cell)
        for c in range(n_close):
            close = 1788800000 + c * 900
            t0 = close - 600
            sweep_ts = set(t0 + k for k in range(0, 400, 37))
            rows = []
            for i in range(420):
                sec = t0 + i
                extra = sum(2.0 * (decay ** (sec - s))
                            for s in sweep_ts if sec >= s)
                rows.append(_mk_ticker("T", sec, 60.0 + drift * i + extra))
            # the control, built through the SAME event_delta the real scan
            # uses, and required to be a window nobody traded in
            ctl = {h: defaultdict(lambda: [0.0, 0]) for h in HORIZONS}
            for r in rows:
                sec = r[1] // 1000
                for h in HORIZONS:
                    if not quiet_window(sweep_ts, sec, h):
                        continue
                    ed = event_delta(rows, sec * 1000, "yes", h)
                    if ed is None:
                        continue
                    base, d, _ib, _ia = ed
                    st = stratum_of("yes", close - sec, base)
                    ctl[h][st][0] += d
                    ctl[h][st][1] += 1
                    ctlcell[h][close].add(d)
            for s in sorted(sweep_ts):
                for h in HORIZONS:
                    ed = event_delta(rows, s * 1000, "yes", h)
                    if ed is None:
                        continue
                    base, d, _ib, _ia = ed
                    st = stratum_of("yes", close - s, base)
                    raw[h][close].add(d)
                    a = adjust(d, st, ctl[h])
                    if a is not None:
                        adj[h][close].add(a)
        return raw, adj, ctlcell

    raw, adj, _c = refill_world(decay=0.0)
    ck(abs(clustered(raw[1])["mean"]) < 1e-9
       and abs(clustered(raw[5])["mean"]) < 1e-9,
       "a book that refills instantly shows zero permanent impact")
    raw, adj, _c = refill_world(decay=1.0)
    r1, r15 = clustered(raw[1]), clustered(raw[15])
    ck(abs(r1["mean"] - 2.0) < 1e-9 and abs(r15["mean"] - 2.0) < 1e-9,
       f"a book that never refills shows the planted +2.00c at every horizon "
       f"({r1['mean']:.4f}, {r15['mean']:.4f})")
    a15 = clustered(adj[15])
    ck(a15 is not None and abs(a15["mean"] - 2.0) < 1e-9,
       f"and the matched control leaves the planted 2.00c intact "
       f"({(a15['mean'] if a15 else float('nan')):.4f}c)")

    # ---- 8. the CONTROL kills a pure drift -------------------------------
    raw, adj, ctlc = refill_world(decay=0.0, drift=0.10)
    r5 = clustered(raw[5])
    a5 = clustered(adj[5])
    ck(r5["mean"] > 0.4,
       f"in a drifting world the RAW post-sweep change fires ({r5['mean']:+.3f}c)")
    ck(a5 is not None and abs(a5["mean"]) < 1e-9,
       f"and the matched control cancels it to zero "
       f"({(a5['mean'] if a5 else float('nan')):+.3e}c) -- so the estimator "
       f"reads impact, not that a busy book trends")
    ck(a5["obs"] > 0 and a5["k"] >= 30,
       f"the control matched {a5['obs']:,} sweep observations over "
       f"{a5['k']} closes, so the cancellation is not an empty cell")
    ck(adjust(1.0, ("yes", "3-30", 95), {}) is None,
       "an unmatched stratum returns None rather than an unadjusted number")
    ck(adjust(1.0, ("yes", "3-30", 95),
              {("yes", "3-30", 95): [0.0, 3]}) is None,
       "and a stratum with fewer than 5 control observations is refused")

    # ---- 9. clustered inference behaves ----------------------------------
    cell = new_cell()
    rnd = random.Random(14)
    for c in range(40):
        for _ in range(50):
            cell[c].add(rnd.gauss(0.0, 1.0))
    r = clustered(cell)
    ck(r["k"] == 40 and r["obs"] == 2000,
       "n is reported as CLOSES (40), not trades (2000)")
    ck(abs(r["t"]) < 3.0, "pure noise does not produce a large clustered t")
    ck(r["mde"] > 0, "and an MDE is available before the estimate is read")
    tiny = new_cell()
    tiny[1].add(5.0)
    ck(clustered(tiny) is None, "one cluster is not an estimate")

    # ---- 10. the snapshot key, both ways ---------------------------------
    bk = ({}, {})
    k = seed_book({"yes_dollars_fp": [["0.6000", "100"]],
                   "no_dollars_fp": [["0.3900", "50"]]}, bk)
    ck(k == "yes_dollars_fp" and bk[0] == {60.0: 100.0}
       and bk[1] == {39.0: 50.0},
       "the snapshot seeds from yes_dollars_fp, which is what the tape writes")
    lad = ladder_for(bk, "yes")
    ck(lad == [(61.0, 50.0)],
       f"buying YES crosses the NO bid at 39c, so it costs 61c ({lad})")
    bk2 = ({}, {})
    ck(seed_book({"yes_dollars": [["0.6000", "100"]]}, bk2) == "yes_dollars"
       and bk2[0] == {60.0: 100.0},
       "and the legacy key still works if Kalshi ever renames back")
    ck(seed_book({"market_ticker": "X"}, ({}, {})) is None,
       "an empty snapshot reports that it seeded nothing")

    # ---- 11. the delta book, and the EV-gated ladder ---------------------
    bk = ({}, {})
    for p, q in ((4.0, 100.0), (3.0, 50.0), (2.0, 20.0), (1.0, 500.0)):
        apply_delta(bk, "yes", p, q)
    lad = sorted(ladder_for(bk, "no"))
    ck([c for c, _ in lad] == [96.0, 97.0, 98.0, 99.0],
       f"deeper levels are DEARER, not cheaper -- the ladder runs the wrong "
       f"way from intuition ({[c for c, _ in lad]})")
    gate = ev_gated(lad)
    ck(len(gate) == 3 and gate[-1][0] == 98.0,
       f"the EV floor trims the dear end: 4 levels -> {len(gate)}")
    ck(sum(s for _, s in lad) - sum(s for _, s in gate) == 500.0,
       "and the trimmed level held the most depth -- size sits where the "
       "money is not")
    apply_delta(bk, "yes", 4.0, -100.0)
    ck(4.0 not in bk[0], "a level emptied by a delta is removed")

    # ---- 12. the field readers, on the exact bytes the tape writes -------
    import tempfile
    tmp = tempfile.mkdtemp()
    tp = os.path.join(tmp, "t.jsonl.gz")
    with gzip.open(tp, "wt") as fh:
        fh.write('{"type":"trade","msg":{"market_ticker":"KXBTC15M-A",'
                 '"yes_price_dollars":"0.9970","no_price_dollars":"0.0030",'
                 '"count_fp":"0.17","taker_side":"yes","is_block_trade":false,'
                 '"ts":1788894023,"ts_ms":1788894023543}}\n')
        fh.write('{"type":"trade","msg":{"market_ticker":"KXBTC15M-A",'
                 '"yes_price_dollars":"0.5000","no_price_dollars":"0.5000",'
                 '"count_fp":"50.00","taker_side":"no","is_block_trade":true,'
                 '"ts":1788894023,"ts_ms":1788894023544}}\n')
        fh.write('{"type":"trade","msg":{"market_ticker":"KXSILVER15M-A",'
                 '"yes_price_dollars":"0.5000","no_price_dollars":"0.5000",'
                 '"count_fp":"9.00","taker_side":"no","is_block_trade":false,'
                 '"ts":1788894023,"ts_ms":1788894023545}}\n')
    rows = list(read_trades(tp))
    ck(len(rows) == 1, f"a block trade and a non-crypto series are both "
                       f"dropped by the reader ({len(rows)} row kept)")
    ck(rows[0] == ("KXBTC15M-A", 1788894023543, "yes", 99.7, 0.17),
       f"a YES taker's cost is the YES price, and 0.17 contracts is a real "
       f"print, not a rounding error ({rows[0]})")
    ck(bucket_of(0.17, N_BUCKETS) == "1-10",
       "and a fractional sweep lands in the smallest bucket instead of being "
       "silently discarded")
    kp = os.path.join(tmp, "k.jsonl.gz")
    with gzip.open(kp, "wt") as fh:
        fh.write('{"type":"ticker","msg":{"market_ticker":"KXBTC15M-A",'
                 '"price_dollars":"0.0010","yes_bid_dollars":"0.0000",'
                 '"yes_ask_dollars":"0.0010","yes_bid_size_fp":"0.00",'
                 '"yes_ask_size_fp":"209624.17","ts_ms":1788894000000}}\n')
    rows = list(read_ticker(kp))
    ck(rows and rows[0][2] == 0.0 and abs(rows[0][3] - 0.1) < 1e-9
       and abs(rows[0][5] - 209624.17) < 1e-6,
       f"the ticker reader gets a 0.1c ask and its 209,624 contracts ({rows})")
    ck(cost_at(rows[0], "no") is None,
       "and with no yes bid there is nothing to buy on the NO side")
    dp = os.path.join(tmp, "d.jsonl.gz")
    with gzip.open(dp, "wt") as fh:
        fh.write('{"type":"orderbook_delta","msg":{"market_ticker":'
                 '"KXBNB15M-A","price_dollars":"0.9590","delta_fp":"50.00",'
                 '"side":"no","ts":"2026-09-08T18:59:59.9807Z",'
                 '"ts_ms":1788893999980}}\n')
    rows = list(read_deltas(dp))
    ck(rows == [("KXBNB15M-A", 1788893999980, "no", 95.9, 50.0)],
       f"the delta reader must take ts_ms and not the ISO 'ts' string ({rows})")
    for f in (tp, kp, dp):
        os.unlink(f)
    os.rmdir(tmp)

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


# ===========================================================================
def report(C, meta, sizes, label, R=None, rmeta=None):
    import statistics as st

    pops = ["ALL", "BUY_WINNER", "SELL_WINNER", "UNDECIDED", "LIVE"]
    print("\n" + "=" * 78)
    print("COVERAGE  (trade + ticker pass)")
    print("=" * 78)
    for k in sorted(meta):
        print(f"  {k:<28} {meta[k]:>14,}")
    if label:
        print("\n  POPULATION LABEL vs SETTLEMENT (only markets fulltape knows)")
        for pop in ("BUY_WINNER", "SELL_WINNER"):
            r, w = label.get(pop + "_right", 0), label.get(pop + "_wrong", 0)
            if r + w:
                print(f"    {pop:<12} taker was right on {r:,} of {r+w:,} "
                      f"sweeps ({100.0*r/(r+w):.2f}%)")

    print("\n" + "=" * 78)
    print("MDE FIRST -- what each slippage cell COULD have detected at 80%")
    print("power, before any estimate below is read.  cents per contract.")
    print("=" * 78)
    print(f"    {'population':<13}" + "".join(f"{b:>11}"
                                              for b, _l, _h in N_BUCKETS))
    for pop in pops:
        row = []
        for nb, _l, _h in N_BUCKETS:
            r = clustered(C["slip"].get((pop, nb), {}))
            row.append(f"{r['mde']:>10.3f}c" if r else f"{'--':>11}")
        print(f"    {pop:<13}" + "".join(row))

    print("\n" + "=" * 78)
    print("(a) TEMPORARY IMPACT -- cents per contract paid ABOVE the touch")
    print("    slip_own  = VWAP(sweep) - best price in the same sweep")
    print("    slip_tick = VWAP(sweep) - ticker top of book at T-1s")
    print("    control   = next k prints, same side, never simultaneous")
    print("=" * 78)
    for pop in pops:
        rows = []
        for nb, _l, _h in N_BUCKETS:
            r = clustered(C["slip"].get((pop, nb), {}))
            if r is None:
                continue
            rows.append((nb, r,
                         clustered(C["slip_ctl"].get((pop, nb), {})),
                         clustered(C["slip_tick"].get((pop, nb), {})),
                         clustered(C["worst"].get((pop, nb), {})),
                         sizes.get((pop, nb), [])))
        if not rows:
            continue
        print(f"\n  {pop}")
        print(f"    {'size':>9} {'medN':>8} {'slip_own':>10} {'t':>7} "
              f"{'control':>9} {'slip_tick':>10} {'walked':>9} "
              f"{'closes':>7} {'sweeps':>11}")
        for nb, r, c, tk, w, szs in rows:
            mn = st.median(szs) if szs else float("nan")
            print(f"    {nb:>9} {mn:>8.1f} {r['mean']:>9.3f}c {r['t']:>7.1f} "
                  f"{(c['mean'] if c else float('nan')):>8.3f}c "
                  f"{(tk['mean'] if tk else float('nan')):>9.3f}c "
                  f"{(w['mean'] if w else float('nan')):>8.3f}c "
                  f"{r['k']:>7,} {r['obs']:>11,}")

    print("\n" + "=" * 78)
    print("(b) PERMANENT IMPACT -- what a SECOND taker in the same direction")
    print("    pays at T+h versus T-1s.  positive = the book did not come back")
    print("    adj = minus the matched no-trade control (same side, tau")
    print("    bucket, 5c price bucket, same hour)")
    print("=" * 78)
    print("\n  the matched control's own level (all strata pooled):")
    for h in HORIZONS:
        print(f"    T+{h:<3}s  {fmt(clustered(C['imp_ctl'].get((h,), {})))}")
    for pop in pops:
        any_row = False
        for nb, _l, _h in N_BUCKETS:
            raw = [clustered(C["imp"].get((pop, nb, h), {})) for h in HORIZONS]
            adj = [clustered(C["imp_adj"].get((pop, nb, h), {}))
                   for h in HORIZONS]
            dep = [clustered(C["dep"].get((pop, nb, h), {})) for h in HORIZONS]
            if not any(raw):
                continue
            if not any_row:
                print(f"\n  {pop}")
                print(f"    {'size':>9} "
                      + "".join(f"{'raw+' + str(h):>10}" for h in HORIZONS)
                      + "".join(f"{'adj+' + str(h):>10}" for h in HORIZONS)
                      + "".join(f"{'dep+' + str(h):>9}" for h in HORIZONS)
                      + f"{'closes':>8}")
                any_row = True
            k = max((x["k"] for x in raw if x), default=0)
            print(f"    {nb:>9} "
                  + "".join(f"{(x['mean'] if x else float('nan')):>9.3f}c"
                            for x in raw)
                  + "".join(f"{(x['mean'] if x else float('nan')):>9.3f}c"
                            for x in adj)
                  + "".join(f"{(x['mean'] if x else float('nan')):>8.2f}x"
                            for x in dep)
                  + f"{k:>8,}")

    print("\n  TOUCH ALIGNMENT -- ticker top of book at T-1s minus the sweep's")
    print("  own best price.  Large positive = the sweep's best fill was NOT")
    print("  the touch and (a) understates slippage.")
    for pop in pops:
        r = clustered(C["align"].get((pop,), {}))
        if r:
            print(f"    {pop:<14} {fmt(r)}")

    if not R:
        return
    print("\n" + "=" * 78)
    print("BOOK REPLAY COVERAGE")
    print("=" * 78)
    for k in sorted(rmeta or {}):
        print(f"  {k:<28} {rmeta[k]:>14,}")

    print("\n" + "=" * 78)
    print("(d1) DOES THE DISPLAYED LADDER ACTUALLY FILL?")
    print("     realised sweep VWAP minus the cost of walking the PRE-SWEEP")
    print("     displayed book for the same number of contracts.")
    print("     positive = quotes LEFT when they were hit (fade).")
    print("     touchdiff is the artefact check: displayed touch minus the")
    print("     sweep's own touch.  If the book channel ran AHEAD of the trade")
    print("     channel this is positive and the fade number is inflated.")
    print("=" * 78)
    print(f"    {'size':>9} {'fade':>10} {'t':>7} {'MDE':>8} "
          f"{'touchdiff':>11} {'fillable':>10} {'closes':>8} {'sweeps':>10}")
    for nb, _l, _h in N_BUCKETS:
        r = clustered(R["fade"].get((nb,), {}))
        f = clustered(R["fillable"].get((nb,), {}))
        td = clustered(R["touchdiff"].get((nb,), {}))
        if r is None:
            continue
        print(f"    {nb:>9} {r['mean']:>9.3f}c {r['t']:>7.1f} "
              f"{r['mde']:>7.3f}c "
              f"{(td['mean'] if td else float('nan')):>10.3f}c "
              f"{(f['mean'] if f else float('nan')):>10.3f} "
              f"{r['k']:>8,} {r['obs']:>10,}")

    print("\n" + "=" * 78)
    print("(d2) WHAT BUYING n CONTRACTS COSTS, tau 3-30, on the near-certain")
    print("     side, off the DISPLAYED book, by the price at the touch")
    print("=" * 78)
    bands = [f"{lo:.1f}-{hi:.1f}c" for lo, hi in PRICE_BANDS] + ["ALL"]
    bands = bands + ["FIRST:" + b for b in bands]
    for band in bands:
        rows = []
        for want in list(GRID_SIZES) + ["all", "ev_gated"]:
            r = clustered(R["cost"].get((band, want), {}))
            if r is None:
                continue
            rows.append((want, r,
                         clustered(R["avail"].get((band, want), {})),
                         clustered(R["vwap"].get((band, want), {})),
                         clustered(R["profit"].get((band, want), {})),
                         clustered(R["got"].get((band, want), {}))))
        if not rows:
            continue
        dp = clustered(R["depth"].get((band,), {}))
        tz = clustered(R["touchsz"].get((band,), {}))
        tag = ("FIRST BUYABLE SECOND ONLY, touch in " + band[6:]
               if band.startswith("FIRST:") else "touch in " + band)
        raw = band[6:] if band.startswith("FIRST:") else band
        warn = ("   *** EV NOT TRUSTWORTHY: the 0.90% flip rate is not "
                "calibrated here ***" if raw.startswith("90.0") else "")
        print(f"\n  {tag}"
              + (f"   ladder {dp['mean']:,.0f} contracts, touch level "
                 f"{tz['mean']:,.0f}, {dp['k']:,} closes" if dp and tz else "")
              + warn)
        print(f"    {'n':>9} {'over touch':>12} {'vwap':>9} "
              f"{'fillable':>10} {'filled':>10} {'EV bought':>12} "
              f"{'per ctr':>9} {'closes':>8} {'moments':>9}")
        for want, r, a, v, p, g in rows:
            per = ((p["mean"] / g["mean"]) if (p and g and g["mean"] > 0)
                   else float("nan"))
            print(f"    {str(want):>9} {r['mean']:>11.3f}c "
                  f"{(v['mean'] if v else float('nan')):>8.2f}c "
                  f"{(a['mean'] if a else float('nan')):>10.3f} "
                  f"{(g['mean'] if g else float('nan')):>10.1f} "
                  f"{(p['mean'] if p else float('nan')):>11.2f}c "
                  f"{per:>8.3f}c "
                  f"{r['k']:>8,} {r['obs']:>9,}")

    print("\n" + "=" * 78)
    print("(d3) THE CORRECTED ANSWER -- what scaling actually buys")
    print("     naive multiple assumes the price does not move; realised is")
    print("     what the displayed ladder actually pays.  'eaten' is the share")
    print("     of the naive gain that market impact takes back.")
    print("=" * 78)
    base_n = GRID_SIZES[0]
    for band in bands:
        b0 = clustered(R["profit"].get((band, base_n), {}))
        g0 = clustered(R["got"].get((band, base_n), {}))
        if b0 is None or g0 is None or g0["mean"] <= 0:
            continue
        head = False
        for want in list(GRID_SIZES[1:]) + ["all", "ev_gated"]:
            p = clustered(R["profit"].get((band, want), {}))
            g = clustered(R["got"].get((band, want), {}))
            if p is None or g is None or g["mean"] <= 0:
                continue
            if not head:
                tag = ("FIRST BUYABLE SECOND ONLY, touch in " + band[6:]
                       if band.startswith("FIRST:") else "touch in " + band)
                print(f"\n  {tag}   base = {base_n} contracts, "
                      f"{b0['mean']:.2f}c of EV per close over {b0['k']:,} "
                      f"closes")
                print(f"    {'n':>9} {'contracts':>11} {'naive x':>9} "
                      f"{'realised x':>12} {'eaten':>8} {'EV/close':>11}")
                head = True
            naive = g["mean"] / g0["mean"]
            real = p["mean"] / b0["mean"]
            eaten = (1.0 - real / naive) if naive > 0 else float("nan")
            print(f"    {str(want):>9} {g['mean']:>11.1f} {naive:>8.2f}x "
                  f"{real:>11.2f}x {100*eaten:>7.1f}% {p['mean']:>10.2f}c")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--hours", type=int, default=240,
                    help="hours of trade+ticker tape for (a),(b),(c)")
    ap.add_argument("--hours-book", type=int, default=0,
                    help="hours of orderbook_delta replay for (d); 0 = skip")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1":
        if not selftest(verbose=not a.quiet):
            raise SystemExit("self-test failed -- refusing to touch real data")

    t0 = time.time()
    res, closes = load_settled()
    print(f"\n  fulltape knows {len(res):,} settled crypto markets")
    cc = check_close_rule(closes, 3)
    if cc:
        print(f"  close_of() agrees with fulltape on {cc[0]:,} prints, "
              f"disagrees on {cc[1]:,}, ticker unknown to fulltape {cc[2]:,}")
        if cc[0] + cc[1] and cc[1] > 0.001 * (cc[0] + cc[1]):
            print("  *** close_of() DISAGREES too often -- clustering is "
                  "suspect, read (a) and (b) with that in mind ***")

    print(f"\n  scanning {a.hours}h of trade + ticker ...", flush=True)
    C, meta, sizes, label = scan(a.hours, verbose=not a.quiet, settled=res)
    R = rmeta = None
    if a.hours_book:
        print(f"\n  replaying {a.hours_book}h of order book ...", flush=True)
        R, rmeta = replay_books(a.hours_book, verbose=not a.quiet)
    report(C, meta, sizes, label, R, rmeta)
    print(f"\n  {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
