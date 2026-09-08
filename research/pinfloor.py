#!/usr/bin/env python3
# VERSION: 2026-09-08-pf1
"""pinfloor.py -- a VARIABLE price ceiling, from the EMPIRICAL index tail.

    python research/pinfloor.py --selftest
    python research/pinfloor.py --hours 240            # measure + score
    python research/pinfloor.py --hours 240 --stride 2 # cheaper

THE PROBLEM THIS SOLVES

pinrun.expected_value() uses a CONSTANT flip rate, MEASURED_FLIP = 0.0090.
Because f is constant, the live test "EV >= EV_FLOOR" is algebraically a FIXED
price ceiling:

    EV = (1-f)(1-p) - f*p - fee(p) = (1-p) - f - fee(p)
    EV >= e   <->   p <= 1 - f - e - fee(p)          (98.71c at f=0.90%, e=0.3c)

Nothing about the market's state enters. The operator has asked repeatedly for
a floor that MOVES with conditions.

WHY THE OBVIOUS VERSION FAILS, AND IS NOT BUILT HERE

The model's own gaussian p_flip is anti-correlated with reward: measured on
593 eligible trades over 70 closes, rows with p_flip < 1e-10 average 97.51c and
are worth 1.41c/contract, rows with p_flip > 1e-3 average 94.39c and are worth
4.35c. Sizing or gating on THAT number makes things worse (results/IDEAS_LOG.md
item 26). So the gaussian tail is not used as a probability anywhere below.

WHAT IS BUILT INSTEAD

The same z, with the gaussian REPLACED by the measured exceedance of the index
tape itself. For index i, horizon r, at second t:

    m(t,r)   = mean(v[t+1..t+r]) - v[t]        the move that must beat req
    sd(t,r)  = sigma_300(t) * sqrt(var_factor(r,[1.0])) * (60/r)
    Z(t,r)   = m(t,r) / sd(t,r)
    z_row    = |required_move| / sd            (row's own, from pindata)

    f_hat    = P(|Z| > z) / 2                  ONE-SIDED, pooled by symmetry

That is a per-trade, per-coin, condition-dependent flip probability containing
NO Kalshi outcomes -- which matters, because the eligible tau 3-30 sample has
ZERO flips and no flip model can be fitted to it.

Windows match research/pindata.py idx_feats EXACTLY (sigma_300 is the RMS of
one-second diffs at j in [max(1,i-300), i], not demeaned), and the Idx class,
its prefix sums and its sd_win convention are volcheck's, imported, not
re-implemented.

SYMMETRY. The flip condition is one-sided and signed: with req = (60/r)(K-mu),
the favoured side is YES iff req <= 0, and it flips iff m < req; the favoured
side is NO iff req > 0, and it flips iff m >= req. Both are "the move went |z|
standard deviations the wrong way", so the two tails are pooled and halved.
The pooled/unpooled asymmetry is printed as a diagnostic, and a large one
would invalidate the pooling.

SMOOTHING, SHRINKAGE AND THE FLOOR -- the three things that stop this
estimator talking us into a stupid price:

  * The tail is a HISTOGRAM in log|z| plus a Pareto extrapolation above the
    last bin with enough counts. Rows reach z = 28; nothing is ever measured
    that far out, so a curve that just returned 0 there would set the ceiling
    to 1 - 0 - 0.003 = 99.7c. The Pareto index is fitted by log-log regression
    over the bins holding between MIN_TAIL_CT and 2% of the mass, and clamped
    to [1.2, 8.0].
  * SHRINKAGE is hierarchical: (index, r-bucket, flat-bucket) shrinks to
    (index, r-bucket) shrinks to (r-bucket pooled over indices) shrinks to
    everything. The weight is n_eff/(n_eff+K) where n_eff is the EXPECTED
    NUMBER OF EXCEEDANCES the cell has at that z, so a cell with one lucky
    outlier is pulled almost entirely back to its parent.
  * THE FLOOR. f_hat is never below FLOOR_F = 0.0090, the aggregate rate
    measured on trades we actually take. This is not decoration: the index
    tape cannot see adverse selection (a near-certainty is only offered
    cheaply when the seller may know something), so the tape's own tail is a
    LOWER bound on our flip risk. With the floor in place the variable ceiling
    can only ever be TIGHTER than today's constant, never looser -- it cannot
    talk us into paying 99.5c.

THE OUTPUT

    ceiling(row) = the largest p with (1-p) - f_hat - fee(p) >= EV_FLOOR

which is 98.71c wherever f_hat is floored and falls as f_hat rises.

NOTHING UNDER C:\\kals IS WRITTEN. The index tape is opened read-only.
"""
import argparse
import array
import bisect
import calendar
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
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from engine import var_factor                                   # noqa: E402,F401
import volcheck                                                 # noqa: E402
from volcheck import Idx, sd_scale, phi                         # noqa: E402
import pinsize                                                  # noqa: E402

IDXDIR = r"C:\kals\kalshi_data\cfbenchmarks_value"
ROWS = os.path.join(os.path.dirname(HERE), "results", "pindata", "rows.jsonl")
OUTDIR = os.path.join(os.path.dirname(HERE), "results")

SERIES_TO_INDEX = dict(volcheck.SERIES_TO_INDEX)
WANT_IDX = sorted(set(SERIES_TO_INDEX.values()))

# ---- the LIVE rule, read off the running process 2026-09-08 ---------------
#   pinrun.py --live --size 5 --minutes 720 --loss-abort -21.00
#   TAU_MIN 3, TAU_MAX 30, PIN 0.98, EDGE_FLOOR 0.003, EV_FLOOR 0.003,
#   MEASURED_FLIP 0.0090, PRICE_CEILING 0.988, MAX_PER_CLOSE 2,
#   IMPROVE_BY 0.005, MIN_LEVEL 1.0
TAU_MIN, TAU_MAX = 3, 30
PIN = 0.98
EDGE_FLOOR = 0.003
EV_FLOOR = 0.003
MEASURED_FLIP = 0.0090
FLIP_CP = 0.0231            # exact one-sided 95% Clopper-Pearson, 3 in 333
PRICE_CEILING = 0.988
MAX_PER_CLOSE = 2
IMPROVE_BY = 0.005
MIN_LEVEL = 1.0

FLOOR_F = 0.0090            # f_hat can never go below this
CAP_F = 0.50                # nor above this

# ---- the histogram of log10|Z| -------------------------------------------
L0, L1, BPD = -1.3, 3.7, 60.0          # z from 0.05 to ~5012, 60 bins/decade
NBIN = int(round((L1 - L0) * BPD))     # 300
MIN_TAIL_CT = 25                       # bins with fewer counts are not fitted
MAX_TAIL_FRAC = 0.02                   # nor bins holding more than 2% of mass
ALPHA_LO, ALPHA_HI = 1.2, 8.0
SHRINK_K = 10.0                        # exceedances needed to trust a cell

# r buckets. r = tau - 1, so pin's tau 3-30 is r 2-29.
R_BUCKETS = ((2, 2), (3, 4), (5, 7), (8, 11), (12, 16), (17, 22),
             (23, 30), (31, 45), (46, 59))
R_SCAN = (2, 4, 6, 9, 14, 19, 26, 38, 52)      # one representative per bucket
FLAT_EDGES = (0.05, 0.35)                      # 3 flatness buckets


def bucket_r(r):
    r = int(r)
    for i, (lo, hi) in enumerate(R_BUCKETS):
        if lo <= r <= hi:
            return i
    return 0 if r < 2 else len(R_BUCKETS) - 1


def bucket_flat(x):
    if x is None:
        return -1
    return bisect.bisect_right(FLAT_EDGES, float(x))


def billed_fee(p, n=1):
    return math.ceil(0.07 * float(p) * (1.0 - float(p)) * float(n) * 1e4) / 1e4


def ev_at(p, f, n=1):
    """Expected dollars for n contracts at price p and flip rate f.
    (1-f)(1-p) - f*p == (1-p) - f exactly, so this is n*((1-p)-f) - fee."""
    return n * ((1.0 - float(p)) - float(f)) - billed_fee(p, n)


def ceiling_for(f, ev_floor=EV_FLOOR):
    """Largest price p with (1-p) - f - fee(p) >= ev_floor.

    fee(p) is small and the whole expression is monotone decreasing in p, so a
    short bisection lands far inside one tick. 0.0 means no price works."""
    lo, hi = 0.0, 1.0
    if ev_at(0.0, f) < ev_floor:
        return 0.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if ev_at(mid, f) >= ev_floor:
            lo = mid
        else:
            hi = mid
    return lo


# ===========================================================================
# CELLS -- a histogram of log10|Z| with a fitted Pareto tail
# ===========================================================================
class Cell(object):
    __slots__ = ("h", "n", "npos", "nneg", "_tail", "_alpha", "_u", "_eu")

    def __init__(self):
        self.h = [0] * NBIN
        self.n = 0            # every standardised sample, including |z|<0.05
        self.npos = 0
        self.nneg = 0
        self._tail = None
        self._alpha = 3.0
        self._u = None
        self._eu = 0.0

    def add(self, z):
        self.n += 1
        if z >= 0:
            self.npos += 1
        else:
            self.nneg += 1
        az = -z if z < 0 else z
        if az <= 0.0:
            return
        b = int((math.log10(az) - L0) * BPD)
        if b < 0:
            return
        if b >= NBIN:
            b = NBIN - 1
        self.h[b] += 1

    def merge(self, o):
        self.n += o.n
        self.npos += o.npos
        self.nneg += o.nneg
        h, oh = self.h, o.h
        for i in range(NBIN):
            h[i] += oh[i]
        self._tail = None

    # -- fitting ----------------------------------------------------------
    def fit(self):
        """tail[i] = # samples with log10|z| >= L0 + i/BPD, plus the Pareto
        index of the far tail by log-log regression on the bin edges."""
        t = [0] * (NBIN + 1)
        s = 0
        for i in range(NBIN - 1, -1, -1):
            s += self.h[i]
            t[i] = s
        t[NBIN] = 0
        self._tail = t
        n = self.n
        self._alpha = 3.0
        self._u = None
        self._eu = 0.0
        if n < 200:
            return self
        hi_ct = max(MIN_TAIL_CT, MAX_TAIL_FRAC * n)
        xs, ys = [], []
        for i in range(NBIN):
            c = t[i]
            if c < MIN_TAIL_CT:
                break
            if c <= hi_ct:
                xs.append((L0 + i / BPD) * math.log(10.0))
                ys.append(math.log(c / float(n)))
        # anchor: the deepest bin edge still holding MIN_TAIL_CT samples
        anchor = None
        for i in range(NBIN - 1, -1, -1):
            if t[i] >= MIN_TAIL_CT:
                anchor = i
                break
        if anchor is not None:
            self._u = 10.0 ** (L0 + anchor / BPD)
            self._eu = t[anchor] / float(n)
        if len(xs) >= 6:
            mx = sum(xs) / len(xs)
            my = sum(ys) / len(ys)
            sxx = sum((x - mx) ** 2 for x in xs)
            sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
            if sxx > 0:
                self._alpha = min(ALPHA_HI, max(ALPHA_LO, -sxy / sxx))
        return self

    # -- reading ----------------------------------------------------------
    def exceed2(self, z):
        """TWO-SIDED P(|Z| > z). Never exactly 0: the Pareto tail continues."""
        if self._tail is None:
            self.fit()
        n = self.n
        if n <= 0:
            return None
        z = float(z)
        if z != z or z == float("inf"):
            z = 1e9
        if z <= 0.0:
            return 1.0
        if self._u is not None and z >= self._u:
            return max(1e-12, self._eu * (z / self._u) ** (-self._alpha))
        x = (math.log10(z) - L0) * BPD
        if x <= 0:
            return min(1.0, self._tail[0] / float(n)) if self._tail[0] else 1.0
        i = int(x)
        if i >= NBIN:
            return 1e-12
        c0, c1 = self._tail[i], self._tail[i + 1]
        if c0 <= 0:
            return 1e-12
        f0 = c0 / float(n)
        if c1 <= 0:
            if self._u is not None:
                return max(1e-12, self._eu * (z / self._u) ** (-self._alpha))
            return max(1e-12, f0 * 0.5)
        f1 = c1 / float(n)
        w = x - i
        return math.exp((1.0 - w) * math.log(f0) + w * math.log(f1))


# ===========================================================================
# THE ESTIMATOR
# ===========================================================================
class Floor(object):
    """Hierarchical empirical exceedance -> f_hat -> price ceiling.

    Levels, most specific first:
        (iid, rb, fb)  ->  (iid, rb)  ->  (rb,)  ->  ()
    """

    def __init__(self, floor_f=FLOOR_F, shrink_k=SHRINK_K):
        self.cells = {}
        self.floor_f = float(floor_f)
        self.shrink_k = float(shrink_k)
        self.skipped = defaultdict(int)

    def cell(self, key):
        c = self.cells.get(key)
        if c is None:
            c = self.cells[key] = Cell()
        return c

    def build(self):
        """Roll the leaf cells up into every parent level, then fit."""
        parents = {}
        for key, c in list(self.cells.items()):
            if len(key) != 3:
                continue
            iid, rb, _fb = key
            for pk in ((iid, rb), (rb,), ()):
                p = parents.get(pk)
                if p is None:
                    p = parents[pk] = Cell()
                p.merge(c)
        for k, v in parents.items():
            self.cells[k] = v
        for c in self.cells.values():
            c.fit()
        return self

    # -- the curve, before the floor --------------------------------------
    def exceed_raw(self, iid, r, z, flat=None):
        """ONE-SIDED empirical exceedance, shrunk through the hierarchy."""
        rb = bucket_r(r)
        fb = bucket_flat(flat)
        chain = []
        if fb >= 0:
            chain.append((iid, rb, fb))
        chain += [(iid, rb), (rb,), ()]
        est = None
        for key in reversed(chain):          # coarsest first
            c = self.cells.get(key)
            if c is None or c.n <= 0:
                continue
            e = c.exceed2(z)
            if e is None:
                continue
            if est is None:
                est = e
                continue
            n_eff = c.n * e                  # expected exceedances backing it
            w = n_eff / (n_eff + self.shrink_k)
            est = math.exp(w * math.log(max(e, 1e-12)) +
                           (1.0 - w) * math.log(max(est, 1e-12)))
        if est is None:
            return None
        return 0.5 * est                     # two-sided -> one-sided

    def f_hat(self, index_id, r, z, features=None):
        """THE DELIVERABLE. Probability the favoured side flips.

        index_id  CF Benchmarks id, e.g. 'BRTI'
        r         unpublished prints remaining (= tau - 1)
        z         |required_move| / sd_pred, the row's own standardised barrier
        features  optional dict; 'flat' = fraction of the trailing 300 one-
                  second diffs that were EXACTLY zero (the step-function
                  mechanism). Absent -> the (index, r) level is used.

        Never below FLOOR_F, never above CAP_F.
        """
        flat = None
        if features:
            flat = features.get("flat")
        e = self.exceed_raw(index_id, r, z, flat)
        if e is None:
            return self.floor_f
        return min(CAP_F, max(self.floor_f, e))

    def ceiling(self, index_id, r, z, features=None, ev_floor=EV_FLOOR):
        return ceiling_for(self.f_hat(index_id, r, z, features), ev_floor)


# ===========================================================================
# LOADING -- lean: no giant dict, straight into volcheck's Idx
# ===========================================================================
def hour_base(fname):
    return calendar.timegm(time.strptime(os.path.basename(fname)[:11],
                                         "%Y%m%dT%H"))


def load_index_lean(hours, datadir=IDXDIR, want=None, verbose=True):
    """Build volcheck.Idx objects without materialising a per-second dict.

    volcheck.load_index holds raw[iid][sec] for every second of every index
    before densifying -- ~10M dict entries at 330 hours, roughly a gigabyte.
    The collector outranks this job, so the seconds go straight into the dense
    array. The Idx class, its prefix sums and its sd_win window convention are
    volcheck's, unchanged.
    """
    files = sorted(glob.glob(os.path.join(datadir, "2026*.jsonl.gz")))
    if hours:
        files = files[-hours:]
    if not files:
        return {}, files
    want = sorted(set(want or WANT_IDX))
    base = hour_base(files[0])
    n = (len(files) + 1) * 3600
    vals = {i: array.array("d", [float("nan")]) * n for i in want}
    pres = {i: bytearray(n) for i in want}
    bad = 0
    kept = 0
    for f in files:
        try:
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    try:
                        d = json.loads(line)
                        m = d["msg"]
                        iid = m["index_id"]
                        if iid not in pres:
                            continue
                        dd = json.loads(m["data"])
                        s = int(dd["time"]) // 1000 - base
                        if 0 <= s < n:
                            vals[iid][s] = float(dd["value"])
                            pres[iid][s] = 1
                            kept += 1
                    except Exception:                       # noqa: BLE001
                        continue
        except (EOFError, zlib.error, OSError) as e:
            bad += 1
            if verbose:
                print(f"    truncated (expected for the live hour): "
                      f"{os.path.basename(f)} {type(e).__name__}")
    out = {}
    for iid in want:
        p = pres[iid]
        if 1 not in p:
            continue
        lo = p.index(1)
        hi = n - 1 - p[::-1].index(1)
        out[iid] = Idx(iid, base + lo, vals[iid][lo:hi + 1],
                       bytearray(p[lo:hi + 1]))
        vals[iid] = None
        pres[iid] = None
    if verbose:
        print(f"  files={len(files)} unreadable={bad} prints={kept:,}")
        for iid in sorted(out):
            ix = out[iid]
            print(f"    {iid:<12} span={ix.n:>9,}s  present={sum(ix.pres):>9,}"
                  f"  coverage={sum(ix.pres)/ix.n:7.3%}")
    return out, files


def zero_diff_prefix(ix):
    """CZ[j] = # of one-second diffs at or before j that were EXACTLY zero.
    The step-function mechanism (SOL 70.5% of consecutive prints equal, BRTI
    0.6%), as a running count so it is O(1) to read in a window."""
    n = ix.n
    CZ = array.array("l", bytes(array.array("l").itemsize * n))
    v, pres = ix.v, ix.pres
    c = 0
    for j in range(1, n):
        if pres[j] and pres[j - 1] and v[j] == v[j - 1]:
            c += 1
        CZ[j] = c
    return CZ


# ===========================================================================
# THE SCAN
# ===========================================================================
def scan_index(ix, fl, rs=R_SCAN, stride=1, sigwin=300, warm=400, CZ=None):
    """Walk one index once per representative r and fill the cells."""
    if not ix.built:
        ix.build(ewma_hl=())
    SV, CP, SD2, CD = ix.SV, ix.CP, ix.SD2, ix.CD
    v = ix.v
    n = ix.n
    iid = ix.name
    lg10 = math.log10
    sq = math.sqrt
    skipped = fl.skipped
    for r in rs:
        rb = bucket_r(r)
        sc = sd_scale(r)
        t0 = max(warm, sigwin + 2)
        t1 = n - r - 2
        if t1 <= t0:
            continue
        cache = {}
        for t in range(t0, t1, stride):
            lo = t - sigwin
            if lo < 1:
                lo = 1
            c = CD[t] - CD[lo - 1]
            if c < 15:
                skipped["thin_sigma_window"] += 1
                continue
            s2 = SD2[t] - SD2[lo - 1]
            if s2 <= 0.0:
                skipped["sigma_exactly_zero"] += 1
                continue
            if CP[t + r + 1] - CP[t] != r + 1:
                skipped["gap_in_future_window"] += 1
                continue
            sd = sq(s2 / c) * sc
            z = ((SV[t + r + 1] - SV[t + 1]) / r - v[t]) / sd
            if CZ is None:
                fb = -1
            else:
                fb = bucket_flat((CZ[t] - CZ[lo - 1]) / float(c))
            key = (iid, rb, fb)
            cl = cache.get(key)
            if cl is None:
                cl = cache[key] = fl.cell(key)
            # inline of Cell.add -- this is the innermost loop of the job
            cl.n += 1
            if z >= 0:
                cl.npos += 1
                az = z
            else:
                cl.nneg += 1
                az = -z
            if az > 0.0:
                b = int((lg10(az) - L0) * BPD)
                if b >= 0:
                    if b >= NBIN:
                        b = NBIN - 1
                    cl.h[b] += 1
    return fl


# ===========================================================================
# SELF-TEST
# ===========================================================================
def _synth_idx(name, diffs):
    vals = array.array("d", [0.0]) * (len(diffs) + 1)
    x = 1000.0
    vals[0] = x
    for i, d in enumerate(diffs):
        x += d
        vals[i + 1] = x
    ix = Idx(name, 0, vals, bytearray(b"\x01" * len(vals)))
    ix.build(ewma_hl=())
    return ix


def _fat_draw(rng):
    """N(0,1) with prob 0.99; a Pareto(2.5) jump of random sign with prob 0.01.
    A PLANTED power-law tail: one jump dominates m(t,r)."""
    if rng.random() < 0.01:
        u = rng.random() or 1e-12
        j = u ** (-1.0 / 2.5)
        return j if rng.random() < 0.5 else -j
    return rng.gauss(0.0, 1.0)


def _truth_mc(gen, r, zs, ndraw, rng):
    """INDEPENDENT Monte Carlo of the true one-sided exceedance of
    m(t,r)/sd_true, sd_true built from the same generator's own variance.
    Nothing here touches the estimator."""
    s2 = 0.0
    k = 200000
    for _ in range(k):
        d = gen(rng)
        s2 += d * d
    sigma = math.sqrt(s2 / k)
    sd = sigma * sd_scale(r)
    hit = [0] * len(zs)
    for _ in range(ndraw):
        s = 0.0
        for i in range(1, r + 1):
            s += (r - i + 1) * gen(rng)
        az = abs((s / r) / sd)
        for j, zz in enumerate(zs):
            if az > zz:
                hit[j] += 1
    return [h / (2.0 * ndraw) for h in hit], sigma


def selftest(fast=True):
    print("SELF-TEST -- pinfloor")
    fails = []

    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            fails.append(msg)

    # ---- the arithmetic the whole thing rests on -------------------------
    ck(abs(ev_at(0.95, 0.009) -
           ((1 - 0.95) - 0.009 - billed_fee(0.95))) < 1e-15,
       "EV identity (1-f)(1-p) - f*p == (1-p) - f")
    c_const = ceiling_for(MEASURED_FLIP)
    ck(0.9865 <= c_const <= 0.9875,
       f"the CONSTANT flip rate collapses to today's fixed ceiling "
       f"({100 * c_const:.2f}c; live quotes it as 98.8c)")
    ck(ceiling_for(0.03) < c_const and ceiling_for(0.10) < ceiling_for(0.03),
       f"a higher f_hat gives a TIGHTER ceiling "
       f"({100 * ceiling_for(0.03):.2f}c at 3%, "
       f"{100 * ceiling_for(0.10):.2f}c at 10%)")
    ck(abs(ev_at(ceiling_for(0.02), 0.02) - EV_FLOOR) < 2e-4,
       "the ceiling sits exactly where EV meets the floor")

    ck(bucket_r(2) == 0 and bucket_r(29) == 6 and bucket_r(59) == 8,
       "r buckets map r = 2, 29, 59 to 0, 6, 8")
    ck(bucket_flat(0.0) == 0 and bucket_flat(0.2) == 1 and
       bucket_flat(0.7) == 2 and bucket_flat(None) == -1,
       "flat buckets, and None means 'feature not supplied'")

    # ---- CELL: an analytic curve is PLANTED and must come back -----------
    rng = random.Random(11)
    c = Cell()
    NP = 400000
    for _ in range(NP):
        u = rng.random() or 1e-12
        zz = u ** (-1.0 / 3.0)                 # P(|Z| > z) = z^-3 exactly
        c.add(zz if rng.random() < 0.5 else -zz)
    c.fit()
    ck(abs(c._alpha - 3.0) < 0.35,
       f"the Pareto index of a planted z^-3 tail is recovered "
       f"(alpha {c._alpha:.3f}, planted 3.000)")
    for zz in (1.5, 3.0, 6.0):
        got, tru = c.exceed2(zz), zz ** -3.0
        ck(0.6 < got / tru < 1.7,
           f"planted exceedance at z={zz}: {got:.3e} vs true {tru:.3e} "
           f"(ratio {got / tru:.2f})")
    got, tru = c.exceed2(60.0), 60.0 ** -3.0
    ck(0.2 < got / tru < 5.0,
       f"the extrapolation holds at z=60 -- 1 in {1 / tru:,.0f}, far past "
       f"anything in {NP:,} samples ({got:.2e} vs {tru:.2e})")
    ck(c.exceed2(1e6) > 0.0,
       "the curve is never exactly zero, so the ceiling can never reach 99.7c")
    prev = 1.0
    for zz in (1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0):
        e = c.exceed2(zz)
        ck(e <= prev + 1e-15, f"monotone non-increasing at z={zz}")
        prev = e

    # ---- A WORLD WITH NOTHING PLANTED: iid gaussian ----------------------
    N = 200000 if fast else 600000
    rng = random.Random(7)
    ixg = _synth_idx("GAUSS", [rng.gauss(0.0, 1.0) for _ in range(N)])
    flg = Floor()
    scan_index(ixg, flg, rs=(4, 9, 19), stride=1)
    flg.build()
    for zz in (2.0, 2.5, 3.0):
        got = flg.exceed_raw("GAUSS", 9, zz)
        tru = 1.0 - phi(zz)
        ck(0.45 < got / tru < 2.2,
           f"clean gaussian world, z={zz}: measured one-sided {got:.3e} vs "
           f"gaussian {tru:.3e} (ratio {got / tru:.2f}) -- NOTHING PLANTED, "
           f"nothing found")
    g4 = flg.exceed_raw("GAUSS", 9, 4.0)
    ck(g4 / (1.0 - phi(4.0)) < 15.0,
       f"and no manufactured fat tail at z=4 (ratio "
       f"{g4 / (1.0 - phi(4.0)):.1f}x, which is sigma-estimation noise, not a "
       f"planted tail; the planted world below must beat this)")
    # BEYOND THE DATA THE EXTRAPOLATION IS PARETO, AND A GAUSSIAN IS NOT.
    # This is a real and deliberate property, tested rather than hidden: past
    # the anchor the curve is a power law, so in a clean gaussian world it
    # OVERSTATES the far tail. Overstating raises f_hat, which TIGHTENS the
    # ceiling -- the safe direction. It must never understate.
    for zz in (5.0, 6.0, 8.0):
        ck(flg.exceed_raw("GAUSS", 9, zz) >= 1.0 - phi(zz),
           f"clean world at z={zz}: extrapolation "
           f"{flg.exceed_raw('GAUSS', 9, zz):.2e} is CONSERVATIVE against the "
           f"gaussian truth {1.0 - phi(zz):.2e} "
           f"({flg.exceed_raw('GAUSS', 9, zz) / (1.0 - phi(zz)):,.0f}x) -- "
           f"never below it")
    ck(abs(flg.f_hat("GAUSS", 9, 6.0) - FLOOR_F) < 1e-12,
       "in a clean world the FLOOR binds at z=6, so f_hat never returns 0")
    ck(flg.f_hat("GAUSS", 9, 2.0) > FLOOR_F,
       "but at z=2 the MEASUREMENT is in charge, not the floor")

    # ---- A WORLD WITH A KNOWN FAT TAIL PLANTED ---------------------------
    rng = random.Random(19)
    ixf = _synth_idx("FAT", [_fat_draw(rng) for _ in range(N)])
    flf = Floor()
    scan_index(ixf, flf, rs=(9,), stride=1)
    flf.build()
    zs = (3.0, 4.0, 6.0)
    tru_l, _sig = _truth_mc(_fat_draw, 9, zs, 120000 if fast else 400000,
                            random.Random(23))
    for zz, tt in zip(zs, tru_l):
        got = flf.exceed_raw("FAT", 9, zz)
        ck(tt > 0 and 0.35 < got / tt < 3.0,
           f"PLANTED fat tail at z={zz}: recovered {got:.3e} against "
           f"independent-MC truth {tt:.3e} (ratio {got / tt:.2f})")
    r4 = flf.exceed_raw("FAT", 9, 4.0) / flg.exceed_raw("GAUSS", 9, 4.0)
    r6 = flf.exceed_raw("FAT", 9, 6.0) / flg.exceed_raw("GAUSS", 9, 6.0)
    ck(r4 > 3.0 and r6 > 8.0,
       f"the planted world's tail is {r4:.1f}x the clean world's at z=4 and "
       f"{r6:.1f}x at z=6 -- the estimator DISCRIMINATES. It fails here if it "
       f"saw the same thing in both, which is the whole point of running the "
       f"clean world at all")

    # ---- SHRINKAGE: a thin cell cannot run away --------------------------
    fl = Floor()
    par = fl.cell(("X", 3, 0))
    for _ in range(200000):                       # a solid parent
        u = rng.random() or 1e-12
        zz = u ** (-1.0 / 3.0)
        par.add(zz if rng.random() < 0.5 else -zz)
    kid = fl.cell(("X", 3, 1))
    for _ in range(49):
        kid.add(0.3)
    kid.add(40.0)                                 # one lucky monster
    fl.build()
    ZT = 20.0
    solid = fl.exceed_raw("X", 9, ZT)             # r 9 -> bucket 3
    thin = fl.exceed_raw("X", 9, ZT, flat=0.2)    # flat 0.2 -> bucket 1
    raw_kid = 0.5 * fl.cells[("X", 3, 1)].exceed2(ZT)
    ck(raw_kid > 50.0 * solid,
       f"one lucky monster in a 50-sample cell would say {raw_kid:.3e} at "
       f"z={ZT:.0f} against the parent's {solid:.3e} -- {raw_kid / solid:,.0f}x, "
       f"and that is the failure mode being guarded")
    ck(thin < 3.0 * solid,
       f"shrunk, it says {thin:.3e}, pulled back to the parent "
       f"({thin / solid:.2f}x)")
    ck(ceiling_for(min(CAP_F, max(FLOOR_F, thin))) >=
       ceiling_for(min(CAP_F, max(FLOOR_F, raw_kid))),
       "so the thin cell cannot tighten the ceiling on one observation")

    # ---- THE FLOOR, and what it buys -------------------------------------
    ck(fl.f_hat("NOSUCHINDEX", 9, 12.0) == FLOOR_F,
       "an unknown index falls back to the floor, never to zero")
    ck(fl.ceiling("NOSUCHINDEX", 9, 12.0) <= c_const + 1e-12,
       "so the variable ceiling can never be LOOSER than today's constant")
    for zz in (2.0, 3.0, 5.0, 30.0):
        ck(FLOOR_F <= flg.f_hat("GAUSS", 9, zz) <= CAP_F,
           f"f_hat stays inside [{FLOOR_F}, {CAP_F}] at z={zz}")
    zprev, cprev = 2.0, flg.ceiling("GAUSS", 9, 2.0)
    for zz in (2.5, 3.0, 4.0, 8.0):
        cnow = flg.ceiling("GAUSS", 9, zz)
        ck(cnow >= cprev - 1e-12,
           f"ceiling is non-decreasing in z ({100 * cprev:.2f}c at z={zprev} "
           f"-> {100 * cnow:.2f}c at z={zz})")
        zprev, cprev = zz, cnow

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


# ===========================================================================
# SCORING against the constant, under the exact live rule
# ===========================================================================
def z_of(row):
    sd = float(row["sig"]) * sd_scale(int(row["r"]))
    if sd <= 0.0:
        return float("inf")
    return abs(float(row["req"])) / sd


def load_rows(path=ROWS):
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:                           # noqa: BLE001
                    pass
    return out


def gate(rows, fl=None, tau_max=TAU_MAX, ev_floor=EV_FLOOR, verbose=True,
         flats=None, label="", hard_ceiling=PRICE_CEILING):
    """Rows the LIVE rule would fire on. fl=None -> today's constant rule.

    Test order is pinrun's: tau, the model pin gate, dust, net edge, the hard
    price ceiling, then EV. The ONLY thing that differs between the two arms
    is the flip rate fed to the EV test."""
    kept = []
    cut = defaultdict(int)
    for d in rows:
        if not (TAU_MIN <= d["tau"] <= tau_max):
            cut["tau"] += 1
            continue
        z = z_of(d)
        pf_model = phi(-z)
        if pf_model > 1.0 - PIN:
            cut["pin_gate"] += 1
            continue
        if float(d["size"]) < MIN_LEVEL:
            cut["dust"] += 1
            continue
        p = float(d["price"])
        if (1.0 - pf_model) - p - billed_fee(p, 1) < EDGE_FLOOR:
            cut["edge_floor"] += 1
            continue
        if p > hard_ceiling:
            cut["hard_ceiling"] += 1
            continue
        if fl is None:
            f = MEASURED_FLIP
        else:
            feats = None
            if flats is not None:
                fv = flats.get((SERIES_TO_INDEX[d["sr"]], int(d["sec"])))
                if fv is not None:
                    feats = {"flat": fv}
            f = fl.f_hat(SERIES_TO_INDEX[d["sr"]], int(d["r"]), z, feats)
        d = dict(d, _z=z, _f=f, _ceil=ceiling_for(f, ev_floor))
        if ev_at(p, f) < ev_floor:
            cut["ev_gate"] += 1
            continue
        kept.append(d)
    kept.sort(key=lambda d: (d["close"], d["sec"], d["tk"]))
    closes = {}
    for d in kept:
        closes.setdefault(d["close"], []).append(d)
    if verbose:
        print(f"    {label}dropped: " +
              ", ".join(f"{k}={v}" for k, v in sorted(cut.items())))
    return closes, kept


def fire(closes, cap=MAX_PER_CLOSE):
    """pinrun's MAX_PER_CLOSE / IMPROVE_BY scale-in, one contract per take."""
    buys = []
    for cs in sorted(closes):
        best = None
        got = 0
        for row in closes[cs]:
            if got >= cap:
                break
            p = float(row["price"])
            if best is not None and p >= best - IMPROVE_BY:
                continue
            buys.append(row)
            best = p if best is None else min(best, p)
            got += 1
    return buys


def summarise(buys, tag, fh=None):
    """fh(row) -> the f_hat for that row. BOTH arms are valued at f_hat, not
    just the arm that used it -- otherwise the 'E[profit] at f_hat' column
    would silently be an at-0.90% column for the constant arm and the two
    would not be comparable."""
    n = len(buys)
    if not n:
        return {"tag": tag, "buys": 0, "closes": 0, "ceils": []}
    by_close = defaultdict(list)
    for b in buys:
        by_close[b["close"]].append(b)
    nc = len(by_close)
    prices = [float(b["price"]) for b in buys]
    fhv = [(fh(b) if fh is not None else b["_f"]) for b in buys]
    ev_c = sum(ev_at(b["price"], MEASURED_FLIP) for b in buys)
    ev_h = sum(ev_at(b["price"], f) for b, f in zip(buys, fhv))
    ev_cp = sum(ev_at(b["price"], FLIP_CP) for b in buys)
    real = (sum((1.0 - b["price"]) if not b["flip"] else -float(b["price"])
                for b in buys)
            - sum(billed_fee(b["price"], 1) for b in buys))
    be = pinsize.breakeven_flip(
        [pinsize.Buy(b["close"], b["tk"], float(b["price"]), 1,
                     bool(b["flip"]), int(b["tau"])) for b in buys])
    return {
        "tag": tag, "buys": n, "closes": nc,
        "flips": sum(1 for b in buys if b["flip"]),
        "mean_price": sum(prices) / n,
        "max_price": max(prices),
        "mean_fhat": sum(fhv) / n,
        "ev_const_per_close": 100.0 * ev_c / nc,
        "ev_fhat_per_close": 100.0 * ev_h / nc,
        "ev_cp_per_close": 100.0 * ev_cp / nc,
        "ev_const_total": 100.0 * ev_c,
        "ev_fhat_total": 100.0 * ev_h,
        "real_per_close": 100.0 * real / nc,
        "real_per_contract": 100.0 * real / n,
        "real_total": 100.0 * real,
        "breakeven": be,
        "headroom": be / FLIP_CP,
        "ceils": sorted(b["_ceil"] for b in buys),
    }


def pctl(xs, q):
    if not xs:
        return float("nan")
    i = int(round(q / 100.0 * (len(xs) - 1)))
    return xs[max(0, min(len(xs) - 1, i))]


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--slow-selftest", action="store_true")
    ap.add_argument("--hours", type=int, default=240)
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--rows", default=ROWS)
    ap.add_argument("--data", default=IDXDIR)
    ap.add_argument("--flat", action="store_true",
                    help="add the flat-stretch feature as a third level")
    ap.add_argument("--split", action="store_true",
                    help="estimate on the FIRST half of the tape, score the "
                         "rows that fall in the second half")
    ap.add_argument("--out", default=os.path.join(OUTDIR, "pinfloor.txt"))
    a = ap.parse_args()
    if a.selftest or a.slow_selftest:
        raise SystemExit(0 if selftest(fast=not a.slow_selftest) else 1)
    if not selftest(fast=True):
        raise SystemExit("self-test failed -- nothing ran")

    lines = []

    def P(s=""):
        print(s, flush=True)
        lines.append(s)

    P("")
    P("=" * 78)
    P("pinfloor -- EMPIRICAL flip probability and the VARIABLE price ceiling")
    P("=" * 78)
    P(f"  tape   {a.data}  last {a.hours} hours, stride {a.stride}")
    P(f"  rows   {a.rows}")
    P(f"  rule   tau {TAU_MIN}-{TAU_MAX}s, pin {PIN}, edge >= "
      f"{100 * EDGE_FLOOR:.1f}c, EV >= {100 * EV_FLOOR:.1f}c, "
      f"<= {MAX_PER_CLOSE} buys/close")
    P(f"  floor  f_hat >= {100 * FLOOR_F:.2f}%  ->  ceiling never above "
      f"{100 * ceiling_for(FLOOR_F):.2f}c (today's constant)")
    P("")

    t0 = time.time()
    idx, files = load_index_lean(a.hours, a.data)
    P(f"  loaded {len(idx)} indices in {time.time() - t0:.0f}s")
    if not idx:
        P("  loaded nothing -- stopping")
        return

    split_at = None
    if a.split:
        lo = min(ix.base for ix in idx.values())
        hi = max(ix.base + ix.n for ix in idx.values())
        split_at = lo + (hi - lo) // 2
        P(f"  SPLIT: estimating on seconds < {split_at} "
          f"({time.strftime('%Y-%m-%d %H:%MZ', time.gmtime(split_at))}), "
          f"scoring rows at or after it")

    fl = Floor()
    flats = {} if a.flat else None
    for iid in sorted(idx):
        ix = idx[iid]
        t1 = time.time()
        if split_at is not None:
            cut = split_at - ix.base
            if cut < 1000:
                continue
            ix = Idx(iid, ix.base, ix.v[:cut], ix.pres[:cut])
        ix.build(ewma_hl=())
        CZ = zero_diff_prefix(ix) if a.flat else None
        scan_index(ix, fl, rs=R_SCAN, stride=a.stride, CZ=CZ)
        if a.flat and CZ is not None:
            base, n = ix.base, ix.n
            CD = ix.CD
            for t in range(302, n):
                lo2 = t - 300
                cc = CD[t] - CD[lo2 - 1]
                if cc >= 15:
                    flats[(iid, base + t)] = (CZ[t] - CZ[lo2 - 1]) / float(cc)
        n_here = sum(c.n for k, c in fl.cells.items()
                     if len(k) == 3 and k[0] == iid)
        P(f"    {iid:<12} {n_here:>12,} standardised moves  "
          f"{time.time() - t1:.0f}s")
        idx[iid] = Idx(iid, idx[iid].base, idx[iid].v, idx[iid].pres)
    fl.build()
    tot = sum(c.n for k, c in fl.cells.items() if len(k) == 3)
    P(f"  {tot:,} standardised moves in {len(fl.cells)} cells "
      f"({time.time() - t0:.0f}s)")
    P("  GUARD NULL -- what the scan threw away, on a healthy tape:")
    den = float(tot + sum(fl.skipped.values())) or 1.0
    for k, v in sorted(fl.skipped.items()):
        P(f"    {k:<26} {v:>12,}  ({100.0 * v / den:.3f}% of attempts)")
    if not fl.skipped:
        P("    nothing")
    P("")

    # ---- the measured curve itself ---------------------------------------
    rb = bucket_r(9)
    P("  MEASURED ONE-SIDED EXCEEDANCE vs the GAUSSIAN the model uses")
    P(f"  (pooled over all indices, r bucket {R_BUCKETS[rb]} = tau "
      f"{R_BUCKETS[rb][0] + 1}-{R_BUCKETS[rb][1] + 1})")
    pool = fl.cells.get((rb,))
    P(f"    {'z':>6}{'gaussian':>13}{'measured':>13}{'ratio':>11}")
    for zz in (2.0, 2.5, 3.0, 4.0, 6.0, 10.0, 20.0, 28.0):
        g = 1.0 - phi(zz)
        e = 0.5 * pool.exceed2(zz)
        rt = ("%.1fx" % (e / g)) if g > 1e-300 else "huge"
        P(f"    {zz:>6.1f}{g:>13.3e}{e:>13.3e}{rt:>11}")
    P("")
    P(f"  BY INDEX at z=3 (one-sided), r bucket {R_BUCKETS[rb]}.")
    P("  'anchor' is the z beyond which the curve is EXTRAPOLATED, not")
    P("  measured; 'alpha' is the fitted Pareto index used out there.")
    P("  'pos/neg' is the sign asymmetry -- the pooling assumes it is ~1.")
    P(f"    {'index':<14}{'n':>13}{'P(Z>3)':>12}{'anchor':>9}{'alpha':>8}"
      f"{'pos/neg':>10}")
    for iid in sorted(idx):
        c = fl.cells.get((iid, rb))
        if c is None:
            continue
        asym = (c.npos / float(c.nneg)) if c.nneg else float("nan")
        P(f"    {iid:<14}{c.n:>13,}{0.5 * c.exceed2(3.0):>12.3e}"
          f"{(c._u or 0.0):>9.2f}{c._alpha:>8.2f}{asym:>10.3f}")
    if pool is not None:
        P(f"    {'POOLED':<14}{pool.n:>13,}{0.5 * pool.exceed2(3.0):>12.3e}"
          f"{(pool._u or 0.0):>9.2f}{pool._alpha:>8.2f}"
          f"{(pool.npos / float(pool.nneg) if pool.nneg else 0):>10.3f}")
    P("")

    # ---- calibration against ACTUAL flips, on the full row set ------------
    rows = load_rows(a.rows)
    if split_at is not None:
        rows = [r for r in rows if int(r["sec"]) >= split_at]
    nfl = sum(1 for r in rows if r["flip"])
    P(f"  rows: {len(rows):,} from pindata, {nfl:,} flips (all tau, all "
      f"prices;")
    P(f"        the eligible tau {TAU_MIN}-{TAU_MAX} sample has ZERO, which "
      f"is why this")
    P(f"        estimator is fitted to the INDEX TAPE and not to outcomes)")
    P("")
    P("  CALIBRATION -- the backward-looking companion. f_hat is scored")
    P("  against flips that ACTUALLY happened, on the whole row set. An")
    P("  estimator that cannot find flips where they exist cannot be")
    P("  trusted where they do not.")
    buckets = [(0.0, 0.0091), (0.0091, 0.02), (0.02, 0.05), (0.05, 0.10),
               (0.10, 0.25), (0.25, 1.01)]
    tab = {b: [0, 0, 0.0, 0.0] for b in buckets}
    for d in rows:
        z = z_of(d)
        f = fl.f_hat(SERIES_TO_INDEX[d["sr"]], int(d["r"]), z)
        g = phi(-z)
        for b in buckets:
            if b[0] <= f < b[1]:
                tab[b][0] += 1
                tab[b][1] += int(bool(d["flip"]))
                tab[b][2] += f
                tab[b][3] += g
                break
    P(f"    {'f_hat band':>16}{'n':>9}{'flips':>8}{'realised':>11}"
      f"{'f_hat':>10}{'gaussian':>12}")
    for b in buckets:
        n, k, sf, sg = tab[b]
        if not n:
            continue
        P(f"    {100 * b[0]:>7.2f}-{100 * b[1]:<8.2f}{n:>9,}{k:>8,}"
          f"{100.0 * k / n:>10.2f}%{100.0 * sf / n:>9.2f}%"
          f"{100.0 * sg / n:>11.4f}%")
    P("")
    P("  AND IN THE NEIGHBOURHOOD WE ACTUALLY TRADE: tau 3-30, price > 85c,")
    P("  past the pin gate. The eligible set inside this has zero flips, so")
    P("  this is the closest population where the question can be asked at")
    P("  all. Rows are split at the MEDIAN f_hat, and clustered by close.")
    near = []
    for d in rows:
        if not (TAU_MIN <= d["tau"] <= TAU_MAX):
            continue
        z = z_of(d)
        if phi(-z) > 1.0 - PIN:
            continue
        if float(d["price"]) <= 0.85 or float(d["size"]) < MIN_LEVEL:
            continue
        near.append((fl.f_hat(SERIES_TO_INDEX[d["sr"]], int(d["r"]), z), d))
    if len(near) >= 60:
        near.sort(key=lambda x: x[0])
        h = len(near) // 2
        for nm, part in (("low  f_hat half", near[:h]),
                         ("high f_hat half", near[h:])):
            cl = defaultdict(lambda: [0, 0])
            for f, d in part:
                cl[d["close"]][0] += 1
                cl[d["close"]][1] += int(bool(d["flip"]))
            nk = sum(v[1] for v in cl.values())
            P(f"    {nm}: {len(part):>5,} rows over {len(cl):>3} closes, "
              f"mean f_hat {100 * sum(f for f, _ in part) / len(part):5.2f}%, "
              f"realised flips {nk:>4} = "
              f"{100.0 * nk / len(part):5.2f}%, "
              f"closes with a flip "
              f"{sum(1 for v in cl.values() if v[1]):>3}/{len(cl)}")
    else:
        P(f"    only {len(near)} rows in that neighbourhood -- not asked")
    P("")

    # ---- THE COMPARISON --------------------------------------------------
    P("=" * 78)
    P("  THE COMPARISON -- constant 0.90% vs variable f_hat, same live rule")
    P("=" * 78)
    cc, _ = gate(rows, None, label="constant  ")
    ch, _ = gate(rows, fl, flats=flats, label="f_hat     ")
    bc = fire(cc)
    bh = fire(ch)

    def fh_of(row):
        feats = None
        if flats is not None:
            fv = flats.get((SERIES_TO_INDEX[row["sr"]], int(row["sec"])))
            if fv is not None:
                feats = {"flat": fv}
        return fl.f_hat(SERIES_TO_INDEX[row["sr"]], int(row["r"]),
                        z_of(row), feats)

    sc_ = summarise(bc, "constant", fh_of)
    sh = summarise(bh, "f_hat", fh_of)
    P("")
    P(f"    {'':<28}{'CONSTANT':>14}{'f_hat':>14}")
    spec = [
        ("closes fired", "closes", "{:,.0f}", 1.0),
        ("buys", "buys", "{:,.0f}", 1.0),
        ("flips realised", "flips", "{:,.0f}", 1.0),
        ("mean price paid (c)", "mean_price", "{:.2f}", 100.0),
        ("max price paid (c)", "max_price", "{:.2f}", 100.0),
        ("mean f_hat applied (%)", "mean_fhat", "{:.3f}", 100.0),
        ("E[profit]/close @0.90% (c)", "ev_const_per_close", "{:+.3f}", 1.0),
        ("E[profit]/close @f_hat (c)", "ev_fhat_per_close", "{:+.3f}", 1.0),
        ("E[profit]/close @2.31% (c)", "ev_cp_per_close", "{:+.3f}", 1.0),
        ("E[profit] TOTAL @f_hat (c)", "ev_fhat_total", "{:+.1f}", 1.0),
        ("realised/close (c)", "real_per_close", "{:+.3f}", 1.0),
        ("realised/contract (c)", "real_per_contract", "{:+.3f}", 1.0),
        ("realised TOTAL (c)", "real_total", "{:+.1f}", 1.0),
        ("blended break-even flip (%)", "breakeven", "{:.3f}", 100.0),
        ("headroom vs 2.31% bound", "headroom", "{:.2f}", 1.0),
    ]
    for name, key, fmt, mul in spec:
        va = sc_.get(key, 0) * mul
        vb = sh.get(key, 0) * mul
        P(f"    {name:<28}{fmt.format(va):>14}{fmt.format(vb):>14}")
    P("")
    P("  ('E[profit] @f_hat' values BOTH books at the per-row f_hat, so the")
    P("   two columns are comparable. 'realised' is what the sample actually")
    P("   did, and there are ZERO flips in it, so realised always favours")
    P("   taking more trades and cannot decide this on its own.)")
    P("")

    # ---- PAIRED, CLUSTERED ON CLOSE -------------------------------------
    P("  PAIRED BY CLOSE (n is closes, the unit the rule fires on). Each")
    P("  close contributes one number: f_hat arm minus constant arm.")
    dc = defaultdict(float)
    for b in bc:
        dc[b["close"]] -= ev_at(b["price"], fh_of(b))
    for b in bh:
        dc[b["close"]] += ev_at(b["price"], fh_of(b))
    dr = defaultdict(float)
    for b in bc:
        dr[b["close"]] -= ((1.0 - b["price"]) if not b["flip"]
                           else -float(b["price"])) - billed_fee(b["price"], 1)
    for b in bh:
        dr[b["close"]] += ((1.0 - b["price"]) if not b["flip"]
                           else -float(b["price"])) - billed_fee(b["price"], 1)
    for nm, dd in (("E[profit] at f_hat", dc), ("realised (0 flips)", dr)):
        v = [100.0 * x for x in dd.values()]
        nn = len(v)
        mu = sum(v) / nn if nn else 0.0
        sd = (math.sqrt(sum((x - mu) ** 2 for x in v) / (nn - 1))
              if nn > 1 else 0.0)
        se = sd / math.sqrt(nn) if nn else 0.0
        t = mu / se if se > 0 else 0.0
        P(f"    {nm:<22} mean {mu:+7.3f}c/close  sd {sd:6.3f}  "
          f"n {nn:>4} closes  t {t:+6.2f}")
    P("")

    # ---- HOW MUCH DOES THE CEILING ACTUALLY MOVE? ------------------------
    P("  HOW MUCH THE CEILING ACTUALLY MOVES. Scored across every trade the")
    P("  CONSTANT rule admits, so both arms see the same population.")
    ceil_all = []
    per_coin = defaultdict(list)
    fhat_all = []
    for b in bc:
        f = fh_of(b)
        cx = ceiling_for(f)
        ceil_all.append(cx)
        fhat_all.append(f)
        per_coin[b["sr"]].append(cx)
    ceil_all.sort()
    fhat_all.sort()
    cfix = ceiling_for(MEASURED_FLIP)
    if ceil_all:
        P(f"    constant ceiling            {100 * cfix:.2f}c  "
          f"on every trade, always")
        P(f"    variable ceiling   p10 {100 * pctl(ceil_all, 10):.2f}c   "
          f"p50 {100 * pctl(ceil_all, 50):.2f}c   "
          f"p90 {100 * pctl(ceil_all, 90):.2f}c")
        P(f"                       min {100 * ceil_all[0]:.2f}c   "
          f"max {100 * ceil_all[-1]:.2f}c   "
          f"p10-p90 SPAN {100 * (pctl(ceil_all, 90) - pctl(ceil_all, 10)):.2f}c")
        P(f"    f_hat              p10 {100 * pctl(fhat_all, 10):.3f}%   "
          f"p50 {100 * pctl(fhat_all, 50):.3f}%   "
          f"p90 {100 * pctl(fhat_all, 90):.3f}%")
        atfloor = sum(1 for x in ceil_all if abs(x - cfix) < 1e-9)
        P(f"    at the floor (ceiling unchanged): {atfloor} of "
          f"{len(ceil_all)} = {100.0 * atfloor / len(ceil_all):.1f}%")
        P("")
        P(f"    {'coin':<12}{'n':>6}{'p10':>9}{'p50':>9}{'p90':>9}"
          f"{'at floor':>11}{'refused':>9}")
        refused = defaultdict(int)
        adm = defaultdict(int)
        for b in bc:
            adm[b["sr"]] += 1
            if ev_at(b["price"], fh_of(b)) < EV_FLOOR:
                refused[b["sr"]] += 1
        for sr in sorted(per_coin):
            v = sorted(per_coin[sr])
            atf = sum(1 for x in v if abs(x - cfix) < 1e-9) / len(v)
            P(f"    {sr:<12}{len(v):>6}{100 * pctl(v, 10):>8.2f}c"
              f"{100 * pctl(v, 50):>8.2f}c{100 * pctl(v, 90):>8.2f}c"
              f"{100 * atf:>10.1f}%"
              f"{100.0 * refused[sr] / adm[sr]:>8.1f}%")
    P("")

    # ---- what the f_hat arm refused, and what it was worth ---------------
    keep = {(b["tk"], b["sec"]) for b in bh}
    dropped = [b for b in bc if (b["tk"], b["sec"]) not in keep]
    P("  WHAT THE VARIABLE FLOOR REFUSED (trades the constant rule took):")
    if dropped:
        rp = (sum((1.0 - b["price"]) if not b["flip"] else -float(b["price"])
                  for b in dropped)
              - sum(billed_fee(b["price"], 1) for b in dropped))
        P(f"    {len(dropped)} of {len(bc)} buys "
          f"({100.0 * len(dropped) / len(bc):.1f}%), mean price "
          f"{100 * sum(b['price'] for b in dropped) / len(dropped):.2f}c, "
          f"{sum(1 for b in dropped if b['flip'])} flips")
        P(f"    they REALISED {100 * rp:+.1f}c in total "
          f"({100 * rp / len(dropped):+.3f}c per contract)")
        P(f"    worth {100 * sum(ev_at(b['price'], MEASURED_FLIP) for b in dropped):+.1f}c"
          f" in expectation at the CONSTANT 0.90%, and "
          f"{100 * sum(ev_at(b['price'], fh_of(b)) for b in dropped):+.1f}c at "
          f"their own f_hat")
        P("    (0 flips in the whole eligible sample, so 'realised' here is a")
        P("     sample with no adverse event in it, not a verdict.)")
    else:
        P("    nothing -- the variable floor refused no trade the constant "
          "rule took")
    P("")
    P("  ARTEFACT CHECK 1 -- adverse selection. The index tape has no Kalshi")
    P("  outcomes in it, so f_hat cannot see that a near-certainty is only")
    P("  offered cheaply when the seller may know something. If the tape's")
    P("  own tail were the whole story, mean f_hat over the trades we take")
    P("  would already reach the 0.90% measured on trades actually taken.")
    if bc:
        mf = sum(fh_of(b) for b in bc) / len(bc)
        P(f"    mean f_hat over the {len(bc)} trades the constant rule takes: "
          f"{100 * mf:.3f}%")
        P(f"    measured rate on trades actually taken:                 "
          f"{100 * MEASURED_FLIP:.3f}%   (3 in 333)")
        P(f"    exact one-sided 95% bound on that:                      "
          f"{100 * FLIP_CP:.3f}%")
        P(f"    -> the tape's tail is {'ABOVE' if mf > MEASURED_FLIP else 'BELOW'}"
          f" the traded rate, so the FLOOR is "
          f"{'not' if mf > MEASURED_FLIP else ''} doing the work here")
        # Is f_hat consistent with the zero flips we actually saw?
        pz_h = 1.0
        pz_c = 1.0
        for b in bc:
            pz_h *= (1.0 - fh_of(b))
            pz_c *= (1.0 - MEASURED_FLIP)
        eh = sum(fh_of(b) for b in bc)
        P(f"    over those {len(bc)} buys f_hat expects {eh:.2f} flips and the "
          f"constant expects {len(bc) * MEASURED_FLIP:.2f}; we saw 0.")
        P(f"    P(0 flips) = {100 * pz_h:.1f}% under f_hat, "
          f"{100 * pz_c:.1f}% under the constant -- so f_hat is on the")
        P("    PESSIMISTIC side of what this sample did, though not rejected "
          "by it")
        P("    (and closes are correlated at rho~0.8, which raises both).")
    P("")

    # ---- ARTEFACT CHECK 2: is the CONDITIONING doing anything? -----------
    P("  ARTEFACT CHECK 2 -- MATCHED TIGHTNESS. The variable floor refuses")
    P("  trades; so does any tighter flat ceiling. If a flat ceiling that")
    P("  refuses the SAME NUMBER of buys does just as well, then the")
    P("  condition-dependence is cosmetic and only the tightness matters.")
    target = sh.get("buys", 0)
    best = None
    for cand in sorted({round(float(r["price"]), 4) for r in rows
                        if 0.85 < float(r["price"]) <= PRICE_CEILING}):
        cf, _ = gate(rows, None, verbose=False, hard_ceiling=cand)
        bf = fire(cf)
        d = abs(len(bf) - target)
        if best is None or d < best[0]:
            best = (d, cand, bf)
    if best is not None:
        _, cand, bf = best
        sf = summarise(bf, "flat", fh_of)
        P(f"    matched flat ceiling: {100 * cand:.2f}c  "
          f"(closest achievable to {target} buys)")
        P(f"    {'':<28}{'f_hat':>14}{'flat-matched':>14}")
        for name, key, fmt, mul in spec:
            P(f"    {name:<28}"
              f"{fmt.format(sh.get(key, 0) * mul):>14}"
              f"{fmt.format(sf.get(key, 0) * mul):>14}")
        dd = defaultdict(float)
        for b in bf:
            dd[b["close"]] -= ev_at(b["price"], fh_of(b))
        for b in bh:
            dd[b["close"]] += ev_at(b["price"], fh_of(b))
        vv = [100.0 * x for x in dd.values()]
        nn = len(vv)
        mu = sum(vv) / nn if nn else 0.0
        sd = (math.sqrt(sum((x - mu) ** 2 for x in vv) / (nn - 1))
              if nn > 1 else 0.0)
        tt = (mu / (sd / math.sqrt(nn))) if sd > 0 else 0.0
        P(f"    PAIRED f_hat MINUS flat-matched, at f_hat: "
          f"{mu:+.3f}c/close  n {nn} closes  t {tt:+.2f}")
    P("")

    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"  wrote {a.out}")


if __name__ == "__main__":
    main()
