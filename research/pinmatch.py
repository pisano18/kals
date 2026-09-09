#!/usr/bin/env python3
# VERSION: 2026-09-08-pm1
"""pinmatch.py -- ANALOGUE SEARCH.  Find the historical moments whose INDEX
SHAPE most resembles the one we lost on, and ask what those moments did next.

    python research/pinmatch.py --selftest
    python research/pinmatch.py --hours 341 --stride 5

THE QUESTION (the operator's, verbatim)

    "What if you went to historic windows that did the exact same thing and you
    look for any possible variable or data point that was lining up the same as
    the one we just lost on? ... Then see if any filtering for that data
    occuring it usually is always followed by a flip or large movement."

WHY THIS IS NOT THE STUDY THAT ALREADY FAILED

The six-agent forensic study tested candidate features ONE AT A TIME across the
whole population of Kalshi closes, stratified by the model's own z, and found
nothing (permutation p = 0.14 .. 0.99).  It could not have found what is asked
here, for three reasons:

  1. It measured MARGINAL effects.  A CONJUNCTION can be lethal while no single
     component moves the average.  This file matches the whole vector at once.
  2. Its MDE was ~5pp on a 6.5% base rate.  A configuration that is RARE and
     NEARLY ALWAYS FATAL is invisible to a test of the mean.  A k-nearest-
     neighbour rate is not a mean over the population; it is a rate inside a
     tiny ball, and it can be 10x the base rate while shifting the population
     mean by 0.01pp.
  3. It had 132 Kalshi closes, 67 loss-carrying.  "What does the INDEX do next"
     needs no Kalshi outcome at all, and the index tape holds ~13 MILLION
     one-second cells.  That is the whole point of this file.

WHAT IS MEASURED

For every (index, second) on an exogenous fixed grid -- NOT on trade arrivals,
NOT on Kalshi closes -- we pretend a settlement window closes `tau` seconds
later, place a SYNTHETIC threshold at the same scale-free distance the real
trade faced, and record (a) the 7-feature scale-free fingerprint of the last
300 s and (b) what actually happened over the remaining r seconds: did the
60-print settlement mean end up on the far side of the threshold, and how big
was the largest one-second move.

Then: the k nearest analogues of the event's fingerprint, their flip rate, and
that rate against the unconditional base rate at the same tau and the same
scale-free distance.

THE FINGERPRINT, AND WHY EACH PIECE IS SCALE-FREE

Scale-free means: invariant when the index is multiplied by a constant, so a
$110,000 BTC cell and a $2.34 NEAR cell can sit in the same space.

  F1  range_300 / sigma_300      ratio of two price-differences -> dimensionless
  F2  sigma_10  / sigma_300      ratio of two SDs               -> dimensionless
  F3  sigma_30  / sigma_300      ratio of two SDs               -> dimensionless
  F4  max_1s_move_10s / sigma_300  ratio of two price-differences
  F5  flat_300  (share of the last 301 one-second diffs that are exactly 0)
  F6  flat_10   (same over the last 11)
  F7  range_60 / range_300       ratio of two ranges

TWO FEATURES NAMED IN THE BRIEF ARE DROPPED, AND HERE IS WHY.

  * distance / sigma_300 is CONSTANT BY CONSTRUCTION.  It is the knob used to
    place the synthetic threshold (placed at exactly the event's value), so it
    has zero variance across cells and contributes exactly zero to any
    distance.  Keeping it would be decoration.
  * distance / range_300 is then PERFECTLY COLLINEAR with F1:
        dist/range_300 = (dist/sigma_300) / (range_300/sigma_300) = c / F1.
    Including both would silently double the weight on F1.  F1 carries it.
  * tau is likewise fixed by construction (the whole scan runs at the event's
    tau), so it constrains the population rather than the metric.

  F5 and F6 are dimensionless but NOT coin-invariant: the flat share is a
  rounding artefact of each index's decimal grid (NEAR quotes 4 dp and sits at
  ~39% flat; BRTI at 2 dp on a $110k price is near 0%).  So EVERY feature is
  standardised WITHIN ITS OWN INDEX by median and IQR before distances are
  taken.  The event's fingerprint is expressed in NEAR's units and matched
  against each other coin in that coin's units, which is exactly the transfer
  semantics wanted: "as unusual for its own coin as this was for NEAR".

THE UNIT OF n, STATED ONCE

  * CELLS are (index, second) pairs.  Two cells one second apart share 59 of
    their 60 settlement prints.  They are not two observations.
  * INDEPENDENT WINDOWS are the reporting unit for everything on the index
    tape: analogues greedily thinned so that no two share an index and lie
    within 60 s of each other -- i.e. non-overlapping settlement windows.
  * TIME BLOCKS are the conservative unit: no two analogues within 60 s of each
    other AT ALL, across every index, because the coins are ~0.8 correlated and
    11 simultaneous analogues are worth ~1.2 observations, not 11.
  * CLOSES is the unit for the cost section, which is scored on Kalshi trades
    from results/pindata/rows.jsonl.

Every rate is reported with its unit named.

CONTROLS, ALL REQUIRED, NONE OPTIONAL

  SHUFFLE   flip labels permuted within index strata; the neighbour set is held
            fixed and its flip count re-drawn.  The effect must vanish.
  PLACEBO   random target fingerprints drawn from real cells, kept only where
            the k-th-neighbour radius matches the real one, so rarity is
            matched.  They must find nothing.
  OOS       scales fitted on the earlier half of the tape, neighbours drawn
            only from the later half, compared to the later half's own base
            rate.  An in-sample-only effect is an overfit to one bad night.
  ABLATION  each of the 7 features dropped in turn.  If the effect needs all 7,
            the rule is unusably rare and this file says so.

SELF-TEST.  Two synthetic worlds built from the same feature-generating
process.  In the PLANTED world, cells carrying a specific fingerprint (flat,
then a spike inside the last 10 s, hence elevated short-horizon sigma) are
followed by a jump that crosses the threshold most of the time; everywhere else
the flip rate is the base rate.  In the NULL world the identical jumps are
injected at RANDOM cells, independent of the fingerprint.  The estimator must
recover the planted lift AND must return nothing in the null world.  main()
refuses real data unless both pass (KALS_SELFTESTED=1 skips, as elsewhere).
"""
import argparse
import array
import calendar
import glob
import gzip
import heapq
import json
import math
import os
import random
import sys
import time
import zlib
from collections import defaultdict, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor                                # noqa: E402

IDXDIR = r"C:\kals\kalshi_data\cfbenchmarks_value"
ROWS = os.path.join(os.path.dirname(HERE), "results", "pindata", "rows.jsonl")

SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI",
    "KXBNB15M": "BNBUSD_RTI", "KXZEC15M": "ZECUSD_RTI",
    "KXHYPE15M": "HYPEUSD_RTI", "KXNEAR15M": "NEARUSD_RTI",
}

# ---------------------------------------------------------------------------
# THE EVENT.  Every field is re-measured from the raw tape by this file's own
# event_fingerprint(); the brief's numbers are printed beside the
# re-measurement so any discrepancy is visible rather than assumed away.
# ---------------------------------------------------------------------------
EVENT = {
    "ticker": "KXNEAR15M-26SEP082045-45",
    "index": "NEARUSD_RTI",
    "close": 1788914700,
    "K_eff": 2.34915,
    "tau": 22,
    "brief": {
        "spot": 2.34830, "dist": 0.00085, "sigma_300": 0.00027719,
        "sigma_10": 0.000581, "sigma_30": 0.000363, "max1s_10": 0.00170,
        "range_300": 0.01060, "range_60": 0.00410,
        "flat_300": 0.51, "flat_10": 0.40, "p_lose": 0.0181,
    },
}

FEATS = ("range300/sig300", "sig10/sig300", "sig30/sig300",
         "max1s10/sig300", "flat300", "flat10", "range60/range300")
NF = len(FEATS)
SEP = "-" * 78


# ===========================================================================
# small statistics
# ===========================================================================
def phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def phi_inv(p):
    """Acklam's inverse normal -- accurate to ~1e-9, plenty for reporting."""
    if p <= 0.0:
        return float("-inf")
    if p >= 1.0:
        return float("inf")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        x = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q
             + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    elif p > ph:
        q = math.sqrt(-2 * math.log(1 - p))
        x = -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q
              + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    else:
        q = p - 0.5
        r = q * q
        x = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r
             + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r
                             + b[4]) * r + 1)
    # one Halley refinement
    e = phi(x) - p
    u = e * math.sqrt(2 * math.pi) * math.exp(x * x / 2)
    return x - u / (1 + x * u / 2)


def wilson(k, n, z=1.96):
    """Wilson score interval -- correct at tiny counts where normal is not."""
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def mde_prop(p0, n, alpha=0.05, power=0.80):
    """Smallest true rate p1 > p0 detectable at n INDEPENDENT observations,
    two-sided alpha, given power.  Bisection on the unequal-variance normal
    form, which is the honest one here because p1 may be far from p0."""
    if n is None or n <= 0:
        return float("nan")
    za = -phi_inv(alpha / 2.0)
    zb = -phi_inv(1.0 - power)

    def need(p1):
        return (za * math.sqrt(p0 * (1 - p0)) + zb * math.sqrt(p1 * (1 - p1))
                ) / math.sqrt(n)

    lo, hi = p0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if mid - p0 >= need(mid):
            hi = mid
        else:
            lo = mid
    return hi


def quantile(xs, q):
    if not xs:
        return float("nan")
    s = sorted(xs)
    i = q * (len(s) - 1)
    lo = int(math.floor(i))
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


# ===========================================================================
# the index tape
# ===========================================================================
class Idx:
    """One index's one-second tape plus every prefix/sliding array the
    fingerprint needs.  Window convention follows research/pindata.py exactly:
    a horizon w means the w+1 diffs at j in [i-w, i], and the w+1 values at
    s in [i-w, i]."""

    def __init__(self, name, base, vals, pres):
        self.name = name
        self.base = base
        self.v = vals
        self.pres = pres
        self.n = len(vals)

    def build(self):
        n, v, pres = self.n, self.v, self.pres
        il = array.array("l").itemsize
        SV = array.array("d", bytes(8 * (n + 1)))
        CP = array.array("l", bytes(il * (n + 1)))
        s = 0.0
        c = 0
        for i in range(n):
            SV[i] = s
            CP[i] = c
            if pres[i]:
                s += v[i]
                c += 1
        SV[n] = s
        CP[n] = c
        SD2 = array.array("d", bytes(8 * n))
        CD = array.array("l", bytes(il * n))
        SZ = array.array("l", bytes(il * n))
        s2 = 0.0
        cd = 0
        cz = 0
        for j in range(1, n):
            if pres[j] and pres[j - 1]:
                d = v[j] - v[j - 1]
                s2 += d * d
                cd += 1
                if d == 0.0:
                    cz += 1
            SD2[j] = s2
            CD[j] = cd
            SZ[j] = cz
        self.SV, self.CP, self.SD2, self.CD, self.SZ = SV, CP, SD2, CD, SZ
        self.R300 = self._range(301)
        self.R60 = self._range(61)
        self.MX10 = self._maxdiff(11)

    def _range(self, width):
        """Sliding max-min over `width` seconds.  Absent seconds are not
        pushed; any cell whose window is not fully present is discarded by
        raw_feats(), so a partially-filled deque never reaches a result."""
        n, v, pres = self.n, self.v, self.pres
        out = array.array("d", bytes(8 * n))
        dmax, dmin = deque(), deque()
        for i in range(n):
            lo = i - width + 1
            if pres[i]:
                x = v[i]
                while dmax and dmax[-1][1] <= x:
                    dmax.pop()
                dmax.append((i, x))
                while dmin and dmin[-1][1] >= x:
                    dmin.pop()
                dmin.append((i, x))
            while dmax and dmax[0][0] < lo:
                dmax.popleft()
            while dmin and dmin[0][0] < lo:
                dmin.popleft()
            out[i] = (dmax[0][1] - dmin[0][1]) if dmax else 0.0
        return out

    def _maxdiff(self, width):
        n, v, pres = self.n, self.v, self.pres
        out = array.array("d", bytes(8 * n))
        dq = deque()
        for j in range(n):
            lo = j - width + 1
            if j >= 1 and pres[j] and pres[j - 1]:
                a = v[j] - v[j - 1]
                if a < 0:
                    a = -a
                while dq and dq[-1][1] <= a:
                    dq.pop()
                dq.append((j, a))
            while dq and dq[0][0] < lo:
                dq.popleft()
            out[j] = dq[0][1] if dq else 0.0
        return out

    def sigma(self, i, w):
        lo = i - w
        if lo < 1:
            return None
        c = self.CD[i] - self.CD[lo - 1]
        if c != w + 1:
            return None
        return math.sqrt((self.SD2[i] - self.SD2[lo - 1]) / c)

    def flat(self, i, w):
        lo = i - w
        if lo < 1:
            return None
        c = self.CD[i] - self.CD[lo - 1]
        if c != w + 1:
            return None
        return (self.SZ[i] - self.SZ[lo - 1]) / c

    def full(self, a, b):
        if a < 0 or b >= self.n or b < a:
            return False
        return self.CP[b + 1] - self.CP[a] == (b - a + 1)

    def mean(self, a, b):
        return (self.SV[b + 1] - self.SV[a]) / (b - a + 1)

    def drop_arrays(self):
        self.SV = self.CP = self.SD2 = self.CD = self.SZ = None
        self.R300 = self.R60 = self.MX10 = None
        self.v = self.pres = None


def _file_epoch(path):
    """20260825T04.jsonl.gz -> epoch seconds of that hour's start (UTC)."""
    b = os.path.basename(path)
    return calendar.timegm((int(b[0:4]), int(b[4:6]), int(b[6:8]),
                            int(b[9:11]), 0, 0, 0, 0, 0))


def load_index(hours, datadir=IDXDIR, want=None, verbose=True):
    """Parse cfbenchmarks_value.

    NOTE: this channel carries NO ts_ms.  The timestamp lives inside msg.data,
    which is a JSON STRING containing {"time": ms, "value": "..."}.  Reading
    msg.ts_ms here matches zero rows and silently yields an empty tape.

    MEMORY.  The obvious implementation accumulates dict[index][second] and
    converts at the end; on the full tape that is ~11 million dict entries and
    peaks near a gigabyte, which on this box competes with the collector and
    the live trader.  The collector outranks this job, so instead the span is
    read off the FILE NAMES first and flat arrays are allocated up front --
    about 11 MB per index instead of ~130 MB."""
    files = sorted(glob.glob(os.path.join(datadir, "2026*.jsonl.gz")))
    if hours:
        files = files[-hours:]
    if not files:
        return {}, files
    lo = _file_epoch(files[0]) - 120
    hi = _file_epoch(files[-1]) + 3600 + 120
    n = hi - lo + 1
    out = {}
    bad = 0
    t0 = time.time()
    for fi, f in enumerate(files):
        try:
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    try:
                        m = json.loads(line)["msg"]
                        iid = m["index_id"]
                        if want and iid not in want:
                            continue
                        dd = json.loads(m["data"])
                        sec = int(dd["time"]) // 1000
                        k = sec - lo
                        if k < 0 or k >= n:
                            continue
                        ix = out.get(iid)
                        if ix is None:
                            ix = out[iid] = Idx(
                                iid, lo, array.array("d", bytes(8 * n)),
                                bytearray(n))
                        ix.v[k] = float(dd["value"])
                        ix.pres[k] = 1
                    except Exception:
                        continue
        except (EOFError, zlib.error, OSError) as e:
            bad += 1
            if verbose:
                print(f"    truncated/unreadable (expected for the live "
                      f"hour): {os.path.basename(f)} {type(e).__name__}")
        if verbose and (fi + 1) % 100 == 0:
            print(f"    parsed {fi + 1}/{len(files)} files "
                  f"{time.time() - t0:.0f}s", flush=True)
    if verbose:
        print(f"  files={len(files)} unreadable={bad} "
              f"parse={time.time() - t0:.0f}s  span={lo}..{hi} ({n:,}s)")
        for iid in sorted(out):
            ix = out[iid]
            print(f"    {iid:<14} span={ix.n:>9,}s  present={sum(ix.pres):>9,}"
                  f"  coverage={sum(ix.pres) / ix.n:7.3%}")
    return out, files


# ===========================================================================
# the fingerprint
# ===========================================================================
def raw_feats(ix, i):
    """The 7 scale-free features at absolute array position i, or
    (None, reason).  Backward-looking only: reads v[i-300 .. i]."""
    if i < 301 or i >= ix.n:
        return None, "edge"
    s300 = ix.sigma(i, 300)
    if s300 is None or not ix.full(i - 300, i):
        return None, "gap300"
    if s300 <= 0.0:
        return None, "sigma0"
    r300 = ix.R300[i]
    if r300 <= 0.0:
        return None, "range0"
    s10 = ix.sigma(i, 10)
    s30 = ix.sigma(i, 30)
    f300 = ix.flat(i, 300)
    f10 = ix.flat(i, 10)
    if s10 is None or s30 is None or f300 is None or f10 is None:
        return None, "gap300"
    return (r300 / s300, s10 / s300, s30 / s300, ix.MX10[i] / s300,
            f300, f10, ix.R60[i] / r300), None


def event_fingerprint(ix):
    """Re-measure the event on the real tape.  Returns (raw, reason, extra)."""
    t = EVENT["close"] - EVENT["tau"]
    i = t - ix.base
    fr, why = raw_feats(ix, i)
    if fr is None:
        return None, why, None
    spot = ix.v[i]
    K = EVENT["K_eff"]
    dist = K - spot
    s300 = ix.sigma(i, 300)
    c = EVENT["close"]
    r = c - 1 - t
    ci = c - ix.base                      # ARRAY index of the close second
    if not ix.full(ci - 60, ci - 1):
        return None, "settlewindow_gap", None
    L = ix.SV[i + 1] - ix.SV[ci - 60]
    mu = (L + r * spot) / 60.0
    req = (60.0 / r) * (K - mu)
    sd_pred = s300 * math.sqrt(var_factor(r, [1.0])) * (60.0 / r)
    z = req / sd_pred if sd_pred > 0 else float("inf")
    settle = ix.mean(ci - 60, ci - 1)
    fut = [abs(ix.v[j] - ix.v[j - 1]) for j in range(i + 1, i + r + 1)]
    extra = {
        "spot": spot, "dist": dist, "sigma_300": s300, "r": r,
        "locked_sum": L, "mu": mu, "required_move": req, "sd_pred": sd_pred,
        "z": z, "p_lose_model": 1 - phi(z), "settle": settle,
        "dist_over_sig": dist / s300, "dist_over_range": dist / ix.R300[i],
        "sigma_10": ix.sigma(i, 10), "sigma_30": ix.sigma(i, 30),
        "max1s_10": ix.MX10[i], "range_300": ix.R300[i], "range_60": ix.R60[i],
        "flat_300": ix.flat(i, 300), "flat_10": ix.flat(i, 10),
        "flipped": settle >= K,
        "max1s_future": max(fut) if fut else float("nan"),
        "max1s_future_z": (max(fut) / s300) if fut else float("nan"),
    }
    return fr, None, extra


# ===========================================================================
# the scan -- one flat table of cells
# ===========================================================================
class Table:
    """Flat column store.  One row per scanned cell."""

    def __init__(self):
        self.F = array.array("f")        # NF floats per row (raw, then z)
        self.t = array.array("l")        # absolute second of the cell
        self.ix = bytearray()            # index ordinal
        self.flipA = bytearray()
        self.flipB = bytearray()
        self.flipC = bytearray()
        self.flipD = bytearray()
        self.jumpz = array.array("f")
        self.aligned = bytearray()
        self.n = 0
        self.names = []


def scan(indices, tau, dist_over_sig, z_model, stride, verbose=True,
         align_period=900):
    """Walk every index on a fixed exogenous grid.  Per cell, place TWO
    synthetic thresholds -- variant A at the event's dist/sigma_300, variant B
    at the event's model z -- and record whether the realised 60-print
    settlement mean landed on the far side of each.

    Cells that fall on a REAL 15-minute close boundary (t + tau divisible by
    900) are always included whatever the stride, and tagged, so the
    close-aligned robustness check is available for free."""
    T = Table()
    drop = defaultdict(int)
    r = tau - 1
    if r < 1:
        raise ValueError("tau must be >= 2")
    vf = math.sqrt(var_factor(r, [1.0]))
    for ordinal, name in enumerate(sorted(indices)):
        ix = indices[name]
        T.names.append(name)
        ix.build()
        base, n = ix.base, ix.n
        got = 0
        lo_i, hi_i = 301, n - r - 1
        i = lo_i
        while i < hi_i:
            t = base + i
            aligned = 1 if ((t + tau) % align_period == 0) else 0
            if (i - lo_i) % stride != 0 and not aligned:
                i += 1
                continue
            fr, why = raw_feats(ix, i)
            if fr is None:
                drop[why] += 1
                i += 1
                continue
            ci = i + tau                      # synthetic close, array index
            if not ix.full(ci - 60, ci - 1):
                drop["gapfuture"] += 1
                i += 1
                continue
            spot = ix.v[i]
            s300 = ix.sigma(i, 300)
            settle = ix.mean(ci - 60, ci - 1)
            KA = spot + dist_over_sig * s300
            L = ix.SV[i + 1] - ix.SV[ci - 60]
            mu = (L + r * spot) / 60.0
            KB = mu + z_model * s300 * vf
            # PLACEMENT C -- the defensive one-line fix a trader would
            # actually reach for: price with the MORE CAUTIOUS of the 30 s and
            # 300 s volatilities instead of sigma_300 alone.  If the
            # fingerprint's lift survives C, a better sigma is not the answer;
            # if it vanishes, the whole finding reduces to "sigma_300 was
            # stale" and no conjunction gate is needed.
            s30c = ix.sigma(i, 30)
            sC = s300 if (s30c is None or s30c < s300) else s30c
            KC = mu + z_model * sC * vf
            # PLACEMENT D -- the SIGN CONTROL.  A is "did it cross UPWARD
            # through a threshold 3.07 sigma above spot".  That is a SIGNED
            # outcome, and this repo's rules require a sign control for one.
            # D mirrors it downward.  Every fingerprint feature is a
            # magnitude and cannot know direction, so if the effect is real
            # D must look like A; if D is flat, A was reading drift.
            KD = spot - dist_over_sig * s300
            mx = 0.0
            for j in range(i + 1, i + r + 1):
                a = ix.v[j] - ix.v[j - 1]
                if a < 0:
                    a = -a
                if a > mx:
                    mx = a
            T.F.extend(fr)
            T.t.append(t)
            T.ix.append(ordinal)
            T.flipA.append(1 if settle >= KA else 0)
            T.flipB.append(1 if settle >= KB else 0)
            T.flipC.append(1 if settle >= KC else 0)
            T.flipD.append(1 if settle <= KD else 0)
            T.jumpz.append(mx / s300)
            T.aligned.append(aligned)
            T.n += 1
            got += 1
            i += 1
        if verbose:
            print(f"    {name:<14} cells={got:>9,}", flush=True)
        ix.drop_arrays()
    return T, dict(drop)


def standardise(T, fit_mask=None):
    """Per-index median/IQR on every feature, applied in place.  fit_mask
    restricts WHICH rows the scales are fitted on (used out-of-sample)."""
    F, n = T.F, T.n
    scales = {}
    for ordinal in range(len(T.names)):
        rows = [i for i in range(n) if T.ix[i] == ordinal
                and (fit_mask is None or fit_mask[i])]
        if len(rows) < 200:
            scales[ordinal] = [(0.0, 1.0)] * NF
            continue
        step = max(1, len(rows) // 200000)
        sub = rows[::step]
        per = []
        for f in range(NF):
            xs = sorted(F[i * NF + f] for i in sub)
            m = quantile(xs, 0.5)
            iqr = quantile(xs, 0.75) - quantile(xs, 0.25)
            if not (iqr > 0):
                sd = math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))
                iqr = sd if sd > 0 else 1.0
            per.append((m, iqr))
        scales[ordinal] = per
    for i in range(n):
        per = scales[T.ix[i]]
        o = i * NF
        for f in range(NF):
            m, s = per[f]
            F[o + f] = (F[o + f] - m) / s
    return scales


def z_target(raw, scales, ordinal):
    per = scales[ordinal]
    return [(raw[f] - per[f][0]) / per[f][1] for f in range(NF)]


# ===========================================================================
# nearest neighbours
# ===========================================================================
def knn(T, target, k, drop_feat=None, row_mask=None):
    """The k nearest rows under standardised Euclidean distance, ascending.
    drop_feat removes one feature from the metric (ablation); row_mask
    restricts the candidate pool (out-of-sample)."""
    F, n = T.F, T.n
    feats = [f for f in range(NF) if f != drop_feat]
    tv = [target[f] for f in feats]
    nf = len(feats)
    worst = float("inf")
    heap = []
    push, pushpop = heapq.heappush, heapq.heappushpop
    for i in range(n):
        if row_mask is not None and not row_mask[i]:
            continue
        o = i * NF
        d2 = 0.0
        for q in range(nf):
            e = F[o + feats[q]] - tv[q]
            d2 += e * e
            if d2 >= worst:
                break
        else:
            if len(heap) < k:
                push(heap, (-d2, i))
                if len(heap) == k:
                    worst = -heap[0][0]
            else:
                pushpop(heap, (-d2, i))
                worst = -heap[0][0]
    return sorted((-a, b) for a, b in heap)


def thin(T, hits, gap=60, cross_index=False):
    """Greedy thinning in distance order so no two kept analogues have
    overlapping settlement windows.  cross_index=False -> INDEPENDENT WINDOWS
    (within-index).  True -> TIME BLOCKS (all indices), the conservative unit,
    because the coins are ~0.8 correlated."""
    kept = []
    buckets = defaultdict(list)          # (key, t//gap) -> [t, ...]
    for d2, i in hits:
        key = 0 if cross_index else T.ix[i]
        t = T.t[i]
        b = t // gap
        clash = False
        for bb in (b - 1, b, b + 1):
            for u in buckets.get((key, bb), ()):
                if abs(t - u) < gap:
                    clash = True
                    break
            if clash:
                break
        if clash:
            continue
        buckets[(key, b)].append(t)
        kept.append((d2, i))
    return kept


def _col(T, which):
    return {"A": T.flipA, "B": T.flipB, "C": T.flipC,
            "D": T.flipD}[which]


def rate(T, rows, which="A"):
    fl = _col(T, which)
    k = sum(fl[i] for _d, i in rows)
    return k, len(rows), (k / len(rows) if rows else float("nan"))


_BASE_CACHE = {}
_STRAT_CACHE = {}


def _strata(T, which, row_mask):
    """Per-index (N, K) over the candidate pool, in ONE pass, cached.  The
    shuffle control needs these; recomputing them inside every call scanned
    the whole table dozens of times."""
    ck = (id(T), which, id(row_mask))
    hit = _STRAT_CACHE.get(ck)
    if hit is not None:
        return hit
    fl = _col(T, which)
    N = defaultdict(int)
    K = defaultdict(int)
    for i in range(T.n):
        if row_mask is not None and not row_mask[i]:
            continue
        o = T.ix[i]
        N[o] += 1
        K[o] += fl[i]
    out = {o: (N[o], K[o]) for o in N}
    _STRAT_CACHE[ck] = out
    return out


def base_rate(T, which="A", row_mask=None):
    ck = (id(T), which, id(row_mask))
    hit = _BASE_CACHE.get(ck)
    if hit is not None:
        return hit
    fl = _col(T, which)
    if row_mask is None:
        k = sum(fl)
        res = (k, T.n, (k / T.n if T.n else float("nan")))
    else:
        k = n = 0
        for i in range(T.n):
            if row_mask[i]:
                n += 1
                k += fl[i]
        res = (k, n, (k / n if n else float("nan")))
    _BASE_CACHE[ck] = res
    return res


def analogue_test(T, target, k, which="A", gap=60, cross_index=False,
                  drop_feat=None, row_mask=None, shuffle_reps=2000, seed=7,
                  pool=None):
    """The whole measurement for one target fingerprint."""
    if pool is None:
        pool = max(k * 400, 20000)
    hits = knn(T, target, pool, drop_feat=drop_feat, row_mask=row_mask)
    kept = thin(T, hits, gap=gap, cross_index=cross_index)[:k]
    blank = {"n": 0, "flips": 0, "rate": float("nan"), "radius": float("nan"),
             "base": float("nan"), "base_n": 0, "ratio": float("nan"),
             "lo": float("nan"), "hi": float("nan"),
             "p_shuffle": float("nan"), "rows": []}
    if not kept:
        return blank
    kf, kn, kr = rate(T, kept, which)
    bk, bn, br = base_rate(T, which, row_mask)
    lo, hi = wilson(kf, kn)
    if shuffle_reps <= 0:
        return {"n": kn, "flips": kf, "rate": kr,
                "radius": math.sqrt(kept[-1][0]), "base": br, "base_n": bn,
                "ratio": (kr / br) if br > 0 else float("inf"),
                "lo": lo, "hi": hi, "p_shuffle": float("nan"), "rows": kept}
    rnd = random.Random(seed)
    fl = _col(T, which)
    comp = defaultdict(int)
    for _d, i in kept:
        comp[T.ix[i]] += 1
    strat = _strata(T, which, row_mask)
    ge = 0
    for _ in range(shuffle_reps):
        tot = 0
        for ordinal, cnt in comp.items():
            N, K = strat.get(ordinal, (1, 0))
            remN, remK = N, K
            for _i in range(cnt):
                if remN <= 0:
                    break
                if rnd.random() < remK / remN:
                    tot += 1
                    remK -= 1
                remN -= 1
        if tot >= kf:
            ge += 1
    return {"n": kn, "flips": kf, "rate": kr, "radius": math.sqrt(kept[-1][0]),
            "base": br, "base_n": bn,
            "ratio": (kr / br) if br > 0 else float("inf"),
            "lo": lo, "hi": hi, "p_shuffle": (ge + 1) / (shuffle_reps + 1),
            "rows": kept}


# ===========================================================================
# SELF-TEST
# ===========================================================================
def _synth_world(seed, plant, n_idx=4, n_sec=42000, tau=22):
    """Synthetic indices whose fingerprints VARY, then either plant the
    relationship (plant=True) or scatter the same jumps at RANDOM positions
    far from the fingerprint (False).

    BUILT FROM INCREMENTS, NOT BY OVERWRITING LEVELS.  The first version of
    this world overwrote v[t-300..t] with a constant, which left v[t] and
    v[t+1] discontinuous and so injected a guaranteed jump immediately after
    EVERY fingerprint -- in both worlds.  The null world then showed a lift of
    2.46x and the self-test correctly failed.  Working in increment space
    makes the tape continuous by construction.

    THE PLANTED SHAPE copies the event: a 300 s stretch that is almost
    perfectly flat carrying ONE spike inside the last 10 s.  The spike is
    sized so that sigma_300 is EXACTLY PRESERVED (sum of squared increments
    over the window is unchanged), which matters: if the shape also changed
    sigma_300 it would move the synthetic threshold, and the null world would
    show a lift for a purely mechanical reason rather than because the
    estimator invented one.  Preserving sigma_300 makes "outcomes are
    independent of the fingerprint" true in the null world by construction.
    """
    rnd = random.Random(seed)
    out = {}
    truth = defaultdict(list)
    for a in range(n_idx):
        sig = 10.0 ** (-(2 + a))
        d = [0.0] * n_sec
        regime, flatp = 1.0, 0.3
        for i in range(1, n_sec):
            if i % 400 == 0:
                regime = math.exp(rnd.gauss(0, 0.5))
                flatp = rnd.uniform(0.05, 0.75)
            d[i] = 0.0 if rnd.random() < flatp else rnd.gauss(0, sig * regime)
        cand = list(range(1000, n_sec - tau - 200, 499))
        rnd.shuffle(cand)
        anchors = sorted(cand[:max(8, len(cand) // 2)])
        for t in anchors:
            S = sum(d[j] * d[j] for j in range(t - 300, t + 1))
            if S <= 0:
                S = (sig * 1e-3) ** 2
            for j in range(t - 300, t + 1):
                d[j] = 0.0
            s = math.sqrt(S / 2.0)          # keeps sum d^2 -- sigma_300 fixed
            d[t - 5] = s
            d[t - 4] = -s
            truth[a].append(t)
        if plant:
            jat = anchors
        else:
            pool = [q for q in range(1000, n_sec - tau - 200)
                    if all(abs(q - x) > 400 for x in anchors)]
            rnd.shuffle(pool)
            jat = sorted(pool[:len(anchors)])
        for t in jat:
            if rnd.random() < 0.85 and t + 8 < n_sec:
                sd_loc = math.sqrt(
                    sum(d[j] * d[j] for j in range(max(1, t - 300), t + 1))
                    / 301.0)
                d[t + 8] += (1 if rnd.random() < 0.5 else -1) * 25.0 * sd_loc
        v = array.array("d", bytes(8 * n_sec))
        x = 100.0 + a
        for i in range(n_sec):
            x += d[i]
            v[i] = x
        out[f"IDX{a}"] = Idx(f"IDX{a}", 1_700_000_000, v, bytearray(
            b"\x01" * n_sec))
    return out, truth


def selftest(verbose=True, quick=False):
    ok = True

    def ck(cond, msg):
        nonlocal ok
        if not cond:
            ok = False
            print(f"  FAIL {msg}")
        elif verbose:
            print(f"  ok   {msg}")

    ck(abs(phi(0) - 0.5) < 1e-12, "phi(0) = 0.5")
    ck(abs(phi_inv(0.975) - 1.959964) < 1e-6, "phi_inv(0.975) = 1.959964")
    ck(abs(phi(phi_inv(0.0181)) - 0.0181) < 1e-10, "phi/phi_inv round-trip")
    lo, hi = wilson(0, 100)
    ck(lo == 0.0 and 0.02 < hi < 0.05, f"wilson(0,100) = [{lo:.3f},{hi:.3f}]")
    m2 = mde_prop(0.02, 200)
    ck(0.03 < m2 < 0.15, f"MDE(p0=2%, n=200) = {m2:.3%}")
    ck(mde_prop(0.02, 2000) < m2, "MDE falls with n")

    v = array.array("d", [float(i % 5) for i in range(50)])
    ix = Idx("T", 0, v, bytearray(b"\x01" * 50))
    ix.build()
    ck(abs(ix.R300[49] - 4.0) < 1e-12, "sliding range 0..4 = 4")
    ck(abs(ix.R60[49] - 4.0) < 1e-12, "sliding range60 = 4")
    ck(abs(ix.MX10[49] - 4.0) < 1e-12, "sliding max|diff| = 4 (the 4->0 step)")
    man = math.sqrt(sum((v[j] - v[j - 1]) ** 2 for j in range(30, 41)) / 11)
    ck(abs(ix.sigma(40, 10) - man) < 1e-12,
       "sigma(i,w) matches the manual w+1 diff form")
    ck(abs(ix.flat(40, 10)) < 1e-12, "flat = 0 on a never-flat series")
    ck(abs(ix.mean(0, 4) - 2.0) < 1e-12, "mean(0,4) of 0,1,2,3,4 = 2")

    Tt = Table()
    Tt.names = ["A"]
    for i in range(10):
        Tt.F.extend([0.0] * NF)
        Tt.t.append(1000 + i)
        Tt.ix.append(0)
        Tt.flipA.append(0)
        Tt.flipB.append(0)
        Tt.flipC.append(0)
        Tt.flipD.append(0)
        Tt.jumpz.append(0.0)
        Tt.aligned.append(0)
        Tt.n += 1
    kept = thin(Tt, [(0.0, i) for i in range(10)], gap=60)
    ck(len(kept) == 1, f"10 cells 1 s apart thin to 1 (got {len(kept)})")

    tau = 22
    nsec = 24000 if quick else 42000
    reps = 500 if quick else 2000
    kk = 40 if quick else 60
    # The TARGET fingerprint is measured on an INDEPENDENT realisation
    # (different seed), so it is never one of the cells being searched.
    wt, tt = _synth_world(23, True, n_sec=nsec, tau=tau)
    ixa = wt["IDX0"]
    ixa.build()
    anchor = tt[0][3]                    # truth[] holds ARRAY POSITIONS
    raw, why = raw_feats(ixa, anchor)
    ck(raw is not None, f"planted fingerprint measurable ({why})")
    if raw is None:
        return False
    ck(abs(raw[0] - math.sqrt(301 / 2.0)) < 0.05,
       f"planted range300/sigma300 = {raw[0]:.2f} (theory "
       f"{math.sqrt(301 / 2.0):.2f})")
    ck(abs(raw[1] - math.sqrt(301 / 11.0)) < 0.05,
       f"planted sigma10/sigma300 = {raw[1]:.2f} (theory "
       f"{math.sqrt(301 / 11.0):.2f})")
    ck(raw[4] > 0.98, f"planted flat300 = {raw[4]:.3f} (>0.98)")
    del wt, ixa

    res = {}
    for plant in (True, False):
        world, _tr = _synth_world(11, plant, n_sec=nsec, tau=tau)
        T, _drop = scan(world, tau, 3.0716, 2.0, stride=1, verbose=False)
        if T.n < 5000:
            ck(False, f"synthetic scan produced {T.n} cells (want >5000)")
            return False
        scales = standardise(T)
        tgt = z_target(raw, scales, T.names.index("IDX0"))
        r = analogue_test(T, tgt, kk, which="A", gap=60, shuffle_reps=reps,
                          seed=3, pool=20000)
        res["plant" if plant else "null"] = r
        if verbose:
            print(f"    world={'PLANTED' if plant else 'NULL':<8} "
                  f"cells={T.n:,} n={r['n']} rate={r['rate']:.1%} "
                  f"base={r['base']:.2%} ratio={r['ratio']:.2f} "
                  f"p={r['p_shuffle']:.4f} radius={r['radius']:.3f}")
    p, z = res["plant"], res["null"]
    ck(p["n"] >= kk // 2,
       f"planted world found {p['n']} independent windows")
    ck(p["ratio"] > 3.0, f"planted lift recovered: ratio={p['ratio']:.2f} (>3)")
    ck(p["p_shuffle"] < 0.01, f"planted shuffle p={p['p_shuffle']:.4f} (<0.01)")
    ck(z["ratio"] < 1.8,
       f"NULL world (outcomes independent of the fingerprint) finds no lift: "
       f"ratio={z['ratio']:.2f} (<1.8)")
    ck(z["p_shuffle"] > 0.02,
       f"null world shuffle p={z['p_shuffle']:.4f} (>0.02)")
    ck(p["rate"] > 4 * z["rate"] if z["rate"] > 0 else p["rate"] > 0.1,
       f"planted rate {p['rate']:.1%} clearly separated from null "
       f"{z['rate']:.1%}")

    print(f"  SELFTEST {'PASS' if ok else 'FAIL'}")
    return ok


# ===========================================================================
# PLACEBO control -- random targets at matched rarity
# ===========================================================================
def placebo_run(T, k, real_radius, n_targets, which="A", gap=60, seed=99,
                pool=None):
    """Draw random REAL cells as target fingerprints, run the identical
    search, and keep only those whose k-th-neighbour radius is within a factor
    of two of the real one -- so the placebo is matched on RARITY, not merely
    on being random.  A placebo that finds a lift means the machinery
    manufactures lifts and the real result is worthless."""
    rnd = random.Random(seed)
    outs = []
    tried = 0
    while len(outs) < n_targets and tried < n_targets * 6:
        tried += 1
        j = rnd.randrange(T.n)
        tgt = [T.F[j * NF + f] for f in range(NF)]
        r = analogue_test(T, tgt, k, which=which, gap=gap, shuffle_reps=0,
                          seed=seed + tried, pool=pool)
        if r["n"] < k // 2:
            continue
        rad = r["radius"]
        if real_radius > 0 and not (0.5 * real_radius <= rad
                                    <= 2.0 * real_radius):
            continue
        outs.append(r)
    return outs, tried


# ===========================================================================
# COST -- what a gate built on this fingerprint would have refused
# ===========================================================================
def billed_fee(p, n=1):
    return math.ceil(0.07 * p * (1 - p) * n * 10000) / 10000


def load_rows(path=ROWS):
    out = []
    if not os.path.exists(path):
        return out
    with open(path) as fh:
        for line in fh:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def cost_table(rows, radii, tau_lo=None, tau_hi=None):
    """rows already carry 'dist' (fingerprint distance), 'flip', 'price'.
    For each radius, count what a REFUSE-IF-INSIDE gate would have thrown
    away.  Unit: one row = one genuinely available (market, second) trade;
    closes are counted separately because that is the inference unit."""
    out = []
    sel = [r for r in rows
           if (tau_lo is None or r["tau"] >= tau_lo)
           and (tau_hi is None or r["tau"] <= tau_hi)]
    tot = len(sel)
    tot_flip = sum(1 for r in sel if r["flip"])
    for R in radii:
        ref = [r for r in sel if r["dist"] <= R]
        rf = sum(1 for r in ref if r["flip"])
        rw = len(ref) - rf
        win_c = sum(100.0 * (1.0 - r["price"] - billed_fee(r["price"]))
                    for r in ref if not r["flip"])
        loss_c = sum(100.0 * (r["price"] + billed_fee(r["price"]))
                     for r in ref if r["flip"])
        out.append({
            "radius": R, "refused": len(ref), "refused_wins": rw,
            "refused_losses": rf,
            "closes": len({(r["tk"], r["close"]) for r in ref}),
            "wins_per_loss": (rw / rf) if rf else float("inf"),
            "profit_destroyed_c": win_c, "loss_avoided_c": loss_c,
            "net_c": loss_c - win_c,
            "share": (len(ref) / tot) if tot else float("nan"),
        })
    return out, tot, tot_flip


# ===========================================================================
def row_pmodel(d):
    """The model's own p(lose) for one pindata row, rebuilt exactly as the
    shipped model does it: p = Phi(-|required_move| / sd_pred) with
    sd_pred = sigma_300 * sqrt(var_factor(r,[1.0])) * (60/r)."""
    r = d.get("r", 0)
    if not r or r < 1:
        return None
    sd = d["sig"] * math.sqrt(var_factor(r, [1.0])) * (60.0 / r)
    if not (sd > 0):
        return None
    return phi(-abs(d["req"]) / sd)


def cost_section(a, scales, tgt, names, radii):
    """What a REFUSE-IF-INSIDE-RADIUS gate would have thrown away, on the
    Kalshi trades we could genuinely have taken.

    THREE POPULATIONS, and only the third decides anything:
      ALL          every available row, tau 2-60
      tau 3-30     the live window, but every row in it
      LIVE RULE    tau 3-30 AND the model's own p(lose) <= 2% -- what pin
                   actually buys.  The brief's "tau 3-30 contains ZERO flips"
                   is true of THIS population and not of the raw tau band,
                   which carries 213 flips in 6,207 rows.
    """
    rows = load_rows(a.rows)
    print(f"  results/pindata/rows.jsonl: {len(rows):,} rows "
          f"(one row = one genuinely available trade)")
    if not rows:
        print("  rows.jsonl absent -- the cost section CANNOT be computed and "
              "no number is reported for it.")
        return
    print("  re-loading the tape to attach the fingerprint to each row.  "
          "F1-F7 are tau-free, so the gate transfers to every tau.")
    need = defaultdict(list)
    for j, r in enumerate(rows):
        iid = SERIES_TO_INDEX.get(r["sr"])
        if iid:
            need[iid].append(j)
    idx2, _f = load_index(a.hours, datadir=a.data, want=set(need),
                          verbose=False)
    attached = missing = 0
    for iid, js in need.items():
        ix = idx2.get(iid)
        if ix is None or iid not in names:
            missing += len(js)
            continue
        ix.build()
        ordn = names.index(iid)
        for j in js:
            rr = rows[j]
            fr, _w = raw_feats(ix, rr["sec"] - ix.base)
            if fr is None:
                missing += 1
                continue
            z = z_target(fr, scales, ordn)
            rr["dist"] = math.sqrt(sum((z[f] - tgt[f]) ** 2 for f in range(NF)))
            attached += 1
        ix.drop_arrays()
    idx2.clear()
    print(f"  fingerprint attached to {attached:,} rows; {missing:,} could "
          f"not be scored (index gap or tape edge)")
    good = [r for r in rows if "dist" in r]
    for r in good:
        r["pmod"] = row_pmodel(r)

    pops = [
        ("ALL rows, tau 2-60", lambda r: True),
        ("tau 3-30, every row", lambda r: 3 <= r["tau"] <= 30),
        ("LIVE RULE: tau 3-30 AND model p(lose) <= 2%  <-- what pin buys",
         lambda r: 3 <= r["tau"] <= 30 and r["pmod"] is not None
         and r["pmod"] <= 0.02),
        ("tau 31-60 AND model p(lose) <= 2%  (where losses DO exist)",
         lambda r: 31 <= r["tau"] <= 60 and r["pmod"] is not None
         and r["pmod"] <= 0.02),
    ]
    for lbl, f in pops:
        sub = [r for r in good if f(r)]
        if not sub:
            print(f"\n  {lbl}: NO ROWS -- nothing reported.")
            continue
        tot = len(sub)
        totf = sum(1 for r in sub if r["flip"])
        allcl = {(r["tk"], r["close"]) for r in sub}
        ncl = len(allcl)
        # UNITS.  totf counts ROWS; ncl counts CLOSES.  Putting one over the
        # other is meaningless and it crashed this function once.  The
        # per-close rate needs closes that carry AT LEAST ONE flip.
        flcl = len({(r["tk"], r["close"]) for r in sub if r["flip"]})
        lo_, hi_ = wilson(flcl, ncl)
        print(f"\n  {lbl}")
        print(f"    population: {tot:,} rows over {ncl:,} CLOSES.  "
              f"{totf:,} losing ROWS ({totf / tot:.3%}); "
              f"{flcl:,} losing CLOSES ({flcl / ncl:.3%}).  Wilson 95% on "
              f"the per-CLOSE loss rate: [{lo_:.2%}, {hi_:.2%}]")
        if totf == 0:
            print(f"    THERE ARE NO LOSSES IN THIS POPULATION AT ALL, so no "
                  f"gate can be credited with avoiding one.  Every gate here "
                  f"refuses only winners.  wins/loss is not 22-44, it is "
                  f"INFINITE, and the study has NO POWER to price the "
                  f"benefit side.")
        tab, _t, _tf = cost_table(sub, radii)
        print(f"    {'radius':>7} {'refused':>8} {'share':>7} {'winsRef':>8} "
              f"{'lossAvoid':>10} {'wins/loss':>10} {'profitDestr':>13} "
              f"{'lossAvoided':>13} {'net':>10}")
        for row in tab:
            wl = ("INF" if row["wins_per_loss"] == float("inf")
                  else f"{row['wins_per_loss']:.1f}")
            print(f"    {row['radius']:>7.3f} {row['refused']:>8,} "
                  f"{row['share']:>6.2%} {row['refused_wins']:>8,} "
                  f"{row['refused_losses']:>10,} {wl:>10} "
                  f"{row['profit_destroyed_c']:>12.1f}c "
                  f"{row['loss_avoided_c']:>12.1f}c {row['net_c']:>9.1f}c")
    print("\n  The prior study killed every proposed gate at 22-44 winning "
          "trades refused per loss avoided (research/RESULTS_pinsignal.md).")
    print("  NOTE: rows.jsonl was built 2026-09-08 08:23, BEFORE the "
          "2026-09-09 00:45Z close, so the event itself is NOT in it.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--hours", type=int, default=0, help="0 = all")
    ap.add_argument("--stride", type=int, default=5)
    ap.add_argument("--placebos", type=int, default=40)
    ap.add_argument("--data", default=IDXDIR)
    ap.add_argument("--rows", default=ROWS)
    ap.add_argument("--cost-only", action="store_true",
                    help="skip the analogue study; fit scales on a coarse "
                         "grid and print only the cost tables")
    ap.add_argument("--cost-radii", default="",
                    help="comma-separated gate radii for --cost-only")
    a = ap.parse_args()

    if a.selftest:
        return 0 if selftest(quick=a.quick) else 1
    if os.environ.get("KALS_SELFTESTED") != "1":
        print("SELF-TEST (main refuses real data until this passes)")
        if not selftest(quick=a.quick):
            print("SELF-TEST FAILED -- refusing to touch real data")
            return 1
        print()

    T0 = time.time()
    print("=" * 78)
    print("PINMATCH -- historical analogues of the shape we lost on")
    print("=" * 78)
    print(f"event : {EVENT['ticker']}  close={EVENT['close']} "
          f"index={EVENT['index']} K_eff={EVENT['K_eff']} tau={EVENT['tau']}")

    want = set(SERIES_TO_INDEX.values())
    print("\nLOADING INDEX TAPE  (cfbenchmarks_value; the timestamp is "
          "msg.data.time -- there is NO ts_ms on this channel)")
    indices, files = load_index(a.hours, datadir=a.data, want=want)
    if not indices:
        print("NO INDEX DATA PARSED -- stopping.")
        return 1

    ev_ix = indices.get(EVENT["index"])
    if ev_ix is None:
        print(f"event index {EVENT['index']} absent from tape -- stopping")
        return 1
    ev_ix.build()
    raw, why, extra = event_fingerprint(ev_ix)
    if raw is None:
        print(f"EVENT FINGERPRINT NOT MEASURABLE ({why}) -- stopping")
        return 1

    print("\n" + SEP)
    print("1. THE EVENT, RE-MEASURED FROM THE RAW TAPE")
    print(SEP)
    b = EVENT["brief"]
    pairs = [("spot", extra["spot"], b["spot"]),
             ("dist to K_eff", extra["dist"], b["dist"]),
             ("sigma_300", extra["sigma_300"], b["sigma_300"]),
             ("sigma_10", extra["sigma_10"], b["sigma_10"]),
             ("sigma_30", extra["sigma_30"], b["sigma_30"]),
             ("max 1s move, 10s", extra["max1s_10"], b["max1s_10"]),
             ("range_300", extra["range_300"], b["range_300"]),
             ("range_60", extra["range_60"], b["range_60"]),
             ("flat_300", extra["flat_300"], b["flat_300"]),
             ("flat_10", extra["flat_10"], b["flat_10"]),
             ("model p(lose)", extra["p_lose_model"], b["p_lose"])]
    print(f"  {'quantity':<20}{'re-measured':>14}{'brief':>14}   delta")
    for nm, mine, theirs in pairs:
        d = "" if theirs == 0 else f"{(mine - theirs) / abs(theirs):+.1%}"
        print(f"  {nm:<20}{mine:>14.8g}{theirs:>14.8g}   {d}")
    won = "YES won, WE LOST" if extra["flipped"] else "NO won"
    print(f"  settlement mean {extra['settle']:.6f} vs K_eff "
          f"{EVENT['K_eff']} -> {won}")
    print(f"  r (future prints) = {extra['r']}, locked = {60 - extra['r']}")
    print(f"  required_move = {extra['required_move']:.6f}   sd_pred = "
          f"{extra['sd_pred']:.6f}   z = {extra['z']:.4f}")
    print(f"  LARGEST 1s MOVE IN THE REMAINING {extra['r']}s = "
          f"{extra['max1s_future']:.5f} = {extra['max1s_future_z']:.2f} "
          f"x sigma_300")
    print("\n  THE FINGERPRINT (raw, scale-free):")
    for f in range(NF):
        print(f"    F{f + 1} {FEATS[f]:<20} {raw[f]:>12.4f}")

    dos = extra["dist_over_sig"]
    zmod = extra["z"]
    print(f"\n  threshold placement A: dist/sigma_300 = {dos:.4f}  "
          f"(the brief's rule)")
    print(f"  threshold placement B: model z = {zmod:.4f}, p(lose) = "
          f"{extra['p_lose_model']:.3%}  (holds the MODEL'S OWN view "
          f"constant -- the tighter conditioning)")

    print("\n" + SEP)
    print(f"2. SCANNING THE WHOLE TAPE at tau={EVENT['tau']}, stride="
          f"{a.stride}s (exogenous grid; real 15-min closes always included)")
    print(SEP)
    stride = max(a.stride, 60) if a.cost_only else a.stride
    T, drop = scan(indices, EVENT["tau"], dos, zmod, stride)
    indices.clear()
    print(f"  cells scanned            {T.n:,}")
    if T.n < 1000:
        print("  FEWER THAN 1000 CELLS -- stopping rather than reporting a "
              "rate from nothing.")
        return 1
    print("  guard rejections (a guard that ate everything must not be able "
          "to look like a thin tape):")
    tot_cand = T.n + sum(drop.values())
    for kk, vv in sorted(drop.items(), key=lambda x: -x[1]):
        print(f"    {kk:<12} {vv:>12,}   {vv / tot_cand:.2%} of candidates")
    print(f"    KEPT         {T.n:>12,}   {T.n / tot_cand:.2%} of candidates")
    print(f"  of which fall on a REAL 15-minute close: {sum(T.aligned):,}")
    span_lo, span_hi = min(T.t), max(T.t)
    print(f"  tape span {span_lo} .. {span_hi} "
          f"({(span_hi - span_lo) / 86400:.1f} days)")
    print(f"  ceiling on INDEPENDENT WINDOWS in this tape ~ "
          f"{(span_hi - span_lo) // 60 * len(T.names):,} "
          f"(span/60 x {len(T.names)} indices)")

    scales = standardise(T)
    ev_ord = T.names.index(EVENT["index"])
    tgt = z_target(raw, scales, ev_ord)
    if a.cost_only:
        print("\n  COST-ONLY MODE.  Scales fitted on a coarse grid "
              f"(stride {stride}s); the median/IQR of 7 stationary features "
              "is stable at this density, and the event z printed below can "
              "be compared against the full run's to confirm that.")
        print("   " + "  ".join(f"{FEATS[f].split('/')[0]}={tgt[f]:+.3f}"
                                for f in range(NF)))
        rr = [float(x) for x in a.cost_radii.split(",") if x.strip()]
        if not rr:
            rr = [0.5, 0.75, 1.0, 1.5, 2.0, 3.0]
        print("\n" + SEP)
        print("8. THE COST -- what a gate on this fingerprint would refuse")
        print(SEP)
        cost_section(a, scales, tgt, T.names, sorted(rr))
        print(f"\ndone in {time.time() - T0:.0f}s")
        return 0
    print("\n  the event's fingerprint in NEAR's own robust units (z):")
    print("   " + "  ".join(f"{FEATS[f].split('/')[0]}={tgt[f]:+.2f}"
                            for f in range(NF)))
    print(f"  |z| = {math.sqrt(sum(x * x for x in tgt)):.2f}  -- how far the "
          f"event sits from a typical NEAR second")

    ka, na, ra = base_rate(T, "A")
    kb, nb, rb = base_rate(T, "B")
    kc, nc, rc = base_rate(T, "C")
    kd, nd, rd = base_rate(T, "D")
    print(f"\n  BASE RATE, placement A (dist/sigma matched): {ka:,}/{na:,} = "
          f"{ra:.4%} of cells cross")
    print(f"  BASE RATE, placement B (model-z matched):    {kb:,}/{nb:,} = "
          f"{rb:.4%} of cells cross")
    print(f"  BASE RATE, placement C (cautious sigma):      {kc:,}/{nc:,} = "
          f"{rc:.4%} of cells cross  -- lower because a bigger sigma pushes "
          f"the threshold further away, which is the point of C")
    print(f"  BASE RATE, placement D (sign control, downward): {kd:,}/{nd:,} "
          f"= {rd:.4%} of cells cross")

    print("\n" + SEP)
    print("3. MDE FIRST, THEN THE ESTIMATE")
    print(SEP)
    print("  n is INDEPENDENT WINDOWS (non-overlapping 60 s settlement "
          "windows within a coin), never cells.")
    for k in (50, 200, 1000):
        for wh, br in (("A", ra), ("B", rb), ("C", rc), ("D", rd)):
            m = mde_prop(br, k)
            print(f"  k={k:>4} placement {wh}: base {br:.4%}, MDE at 80% "
                  f"power / alpha 0.05 = {m:.3%} "
                  f"({(m / br if br > 0 else float('nan')):.1f}x base)")

    print("\n" + SEP)
    print("4. THE k NEAREST ANALOGUES, AND WHAT THEY DID NEXT")
    print(SEP)
    results = {}
    shuf = 0 if a.quick else 3000
    LBL = {"A": "dist/sigma_300 matched (the brief's rule)",
           "B": "model-z matched -- holds the MODEL'S OWN view constant",
           "C": "model-z matched but priced with sigma_C = max(sigma_30, "
                "sigma_300) -- the defensive one-line fix",
           "D": "SIGN CONTROL -- A mirrored, crossing DOWNWARD"}
    for wh in ("A", "B", "C", "D"):
        lbl = LBL[wh]
        print(f"\n  PLACEMENT {wh} ({lbl})")
        print(f"  {'k':>6} {'n_ind':>6} {'flips':>6} {'rate':>8} "
              f"{'95% CI':>17} {'base':>8} {'ratio':>7} {'radius':>7} "
              f"{'p_shuf':>7}")
        for k in (50, 200, 1000):
            r = analogue_test(T, tgt, k, which=wh, gap=60, shuffle_reps=shuf,
                              pool=max(k * 60, 30000))
            results[(wh, k)] = r
            ci = f"[{r['lo']:.2%},{r['hi']:.2%}]"
            print(f"  {k:>6} {r['n']:>6} {r['flips']:>6} {r['rate']:>7.2%} "
                  f"{ci:>17} {r['base']:>7.3%} {r['ratio']:>7.2f} "
                  f"{r['radius']:>7.3f} {r['p_shuffle']:>7.4f}")
        rc = analogue_test(T, tgt, 200, which=wh, gap=60, cross_index=True,
                           shuffle_reps=shuf, pool=30000)
        results[(wh, "cross")] = rc
        ci = f"[{rc['lo']:.2%},{rc['hi']:.2%}]"
        print("  conservative TIME-BLOCK unit (no two analogues within 60 s "
              "of each other on ANY coin):")
        print(f"  {200:>6} {rc['n']:>6} {rc['flips']:>6} {rc['rate']:>7.2%} "
              f"{ci:>17} {rc['base']:>7.3%} {rc['ratio']:>7.2f} "
              f"{rc['radius']:>7.3f} {rc['p_shuffle']:>7.4f}")

    full = results[("A", 200)]

    print("\n  ARE THE ANALOGUES SPREAD OUT IN TIME?  200 analogues drawn"
          " from three volatile hours are not 200 observations, however far"
          " apart they are within those hours.")
    for kk in (50, 200, 1000):
        rr = results.get(("A", kk))
        if not rr or not rr["rows"]:
            continue
        ts = sorted(T.t[i] for _d, i in rr["rows"])
        days = len({t // 86400 for t in ts})
        hours = len({t // 3600 for t in ts})
        span_d = (ts[-1] - ts[0]) / 86400.0
        big = defaultdict(int)
        for t in ts:
            big[t // 3600] += 1
        top = sorted(big.values(), reverse=True)
        print(f"    k={kk:>4}: {days} distinct DAYS, {hours} distinct HOURS,"
              f" span {span_d:.1f}d of the {(max(T.t) - min(T.t)) / 86400:.1f}d"
              f" tape; busiest hour holds {top[0]} of {len(ts)},"
              f" top 3 hours hold {sum(top[:3])}")
        fl_by_day = defaultdict(lambda: [0, 0])
        for _d, i in rr["rows"]:
            c = fl_by_day[T.t[i] // 86400]
            c[0] += 1
            c[1] += T.flipA[i]
        pos = sum(1 for v in fl_by_day.values() if v[1] > 0)
        print(f"            flips occur on {pos} of those {days} days"
              f" -- concentration check")

    print("\n  WHERE THE NEIGHBOURS COME FROM.  Composition is the main"
          " confound: if the ball lands on one coin, that coin's own base"
          " rate could explain the lift.  The SHUFFLE control is stratified"
          " by coin precisely for this.")
    comp = defaultdict(lambda: [0, 0])
    for _d, i in full["rows"]:
        c = comp[T.names[T.ix[i]]]
        c[0] += 1
        c[1] += T.flipA[i]
    coin_base = {}
    for o in range(len(T.names)):
        coin_base[o] = [0, 0]
    for i in range(T.n):
        cb = coin_base[T.ix[i]]
        cb[0] += 1
        cb[1] += T.flipA[i]
    print(f"    {'coin':<14} {'analogues':>10} {'flips':>6} {'rate':>8} "
          f"{'that coin base':>15}")
    for nm in sorted(comp, key=lambda x: -comp[x][0]):
        cnt, fk = comp[nm]
        bn_, bk_ = coin_base[T.names.index(nm)]
        print(f"    {nm:<14} {cnt:>10} {fk:>6} {fk / cnt:>7.1%} "
              f"{(bk_ / bn_ if bn_ else float('nan')):>14.3%}")

    print("\n  THE MATCH IS IN z-SPACE (each feature standardised inside its"
          " own coin).  z of the 10 nearest, against the event's z:")
    print("   " + " ".join(f"{n.split('/')[0][:7]:>8}" for n in FEATS)
          + f" {'coin':>13} {'dist':>6} {'flip':>5}")
    for d2, i in full["rows"][:10]:
        print("   " + " ".join(f"{T.F[i * NF + f]:>+8.2f}" for f in range(NF))
              + f" {T.names[T.ix[i]][:13]:>13} {math.sqrt(d2):>6.3f} "
                f"{T.flipA[i]:>5}")
    print("   " + " ".join(f"{tgt[f]:>+8.2f}" for f in range(NF))
          + f" {'<< EVENT':>13} {0.0:>6.3f} {1:>5}")

    print("\n  RAW FEATURE VALUES of the 10 nearest analogues -- are they "
          "really the same shape?")
    print("   " + " ".join(f"{n.split('/')[0][:7]:>8}" for n in FEATS)
          + f" {'coin':>13} {'flip':>5} {'jumpz':>7}")
    for d2, i in full["rows"][:10]:
        vals = [T.F[i * NF + f] * scales[T.ix[i]][f][1] + scales[T.ix[i]][f][0]
                for f in range(NF)]
        print("   " + " ".join(f"{v:>8.3f}" for v in vals)
              + f" {T.names[T.ix[i]][:13]:>13} {T.flipA[i]:>5} "
                f"{T.jumpz[i]:>7.2f}")
    print("   " + " ".join(f"{v:>8.3f}" for v in raw)
          + f" {'<< EVENT':>13} {1:>5} {extra['max1s_future_z']:>7.2f}")

    print("\n" + SEP)
    print("5. THE OPERATOR'S SECOND FORMULATION -- 'or large movement'")
    print(SEP)
    print("  Largest ONE-SECOND move in the remaining r seconds, in units of "
          "sigma_300 measured at entry.")
    step = max(1, T.n // 300000)
    allj = [T.jumpz[i] for i in range(0, T.n, step)]
    ez = extra["max1s_future_z"]
    for k in (50, 200, 1000):
        rr = results.get(("A", k))
        if not rr or not rr["rows"]:
            continue
        js = [T.jumpz[i] for _d, i in rr["rows"]]
        pge = sum(1 for x in js if x >= ez) / len(js)
        print(f"  k={k:>4} n={len(js):>4}  median {quantile(js, .5):>5.2f}  "
              f"p90 {quantile(js, .9):>5.2f}  p99 {quantile(js, .99):>6.2f}  "
              f"max {max(js):>6.2f}   P(jump >= {ez:.2f} sigma) = {pge:.2%}")
    pge = sum(1 for x in allj if x >= ez) / len(allj)
    print(f"  UNCOND n={len(allj):>6}  median {quantile(allj, .5):>5.2f}  "
          f"p90 {quantile(allj, .9):>5.2f}  p99 {quantile(allj, .99):>6.2f}  "
          f"max {max(allj):>6.2f}   P(jump >= {ez:.2f} sigma) = {pge:.2%}")
    print(f"  THE EVENT ITSELF: {ez:.2f} sigma")

    print("\n" + SEP)
    print("6. ABLATION -- which feature is the effect actually made of?")
    print(SEP)
    print("  Dropping a feature can only WIDEN the ball along that axis, so a")
    print("  FALL in the ratio means that feature was doing real selection")
    print("  work, and a RISE means it was adding noise.  The radius shrinks")
    print("  mechanically whenever a dimension is removed, so read the ratio,")
    print("  not the radius.")
    for wh in ("A", "B", "C"):
        base_r = results[(wh, 200)]
        print(f"\n  PLACEMENT {wh}")
        print(f"  {'dropped feature':<24} {'n':>5} {'rate':>8} {'ratio':>7} "
              f"{'radius':>7} {'p_shuf':>7}")
        print(f"  {'-- none (full 7) --':<24} {base_r['n']:>5} "
              f"{base_r['rate']:>7.2%} {base_r['ratio']:>7.2f} "
              f"{base_r['radius']:>7.3f} {base_r['p_shuffle']:>7.4f}")
        for f in range(NF):
            r = analogue_test(T, tgt, 200, which=wh, gap=60, drop_feat=f,
                              shuffle_reps=(0 if a.quick else 2000),
                              pool=30000)
            print(f"  {FEATS[f]:<24} {r['n']:>5} {r['rate']:>7.2%} "
                  f"{r['ratio']:>7.2f} {r['radius']:>7.3f} "
                  f"{r['p_shuffle']:>7.4f}")

    print("\n" + SEP)
    print("7. CONTROLS")
    print(SEP)
    print("  (a) SHUFFLE -- flip labels permuted within index strata, the "
          "neighbour set held fixed.")
    print("      p_shuf in every table above IS that control.")
    print(f"      full fingerprint, k=200: placement A p = "
          f"{full['p_shuffle']:.4f}, placement B p = "
          f"{results[('B', 200)]['p_shuffle']:.4f}")

    print(f"\n  (b) PLACEBO -- up to {a.placebos} random real cells used as "
          f"target fingerprints, kept only where the k-th-neighbour radius "
          f"is within 2x of the real one (RARITY MATCHED).")
    pl, tried = placebo_run(T, 200, full["radius"], a.placebos, which="A",
                            seed=99, pool=30000)
    if pl:
        prs = [p["rate"] for p in pl]
        above = sum(1 for x in prs if x >= full["rate"])
        print(f"      kept {len(pl)} of {tried} draws.  placebo flip rates: "
              f"median {quantile(prs, .5):.2%}, p90 {quantile(prs, .9):.2%}, "
              f"max {max(prs):.2%}")
        print(f"      placebos at or above the real fingerprint's "
              f"{full['rate']:.2%}: {above}/{len(pl)}  ->  empirical p = "
              f"{(above + 1) / (len(pl) + 1):.3f}")
        print(f"      placebo radii median "
              f"{quantile([p['radius'] for p in pl], .5):.3f} vs real "
              f"{full['radius']:.3f}")
    else:
        print("      NO PLACEBO PASSED THE RARITY MATCH -- saying so rather "
              "than quoting a number.")

    print("\n  (c) OUT OF SAMPLE -- scales fitted on the EARLY half, "
          "neighbours drawn only from the LATE half.")
    mid = (span_lo + span_hi) // 2
    early = bytearray(1 if T.t[i] <= mid else 0 for i in range(T.n))
    late = bytearray(1 - x for x in early)
    print(f"      split at {mid}: early cells {sum(early):,}, late cells "
          f"{sum(late):,}")
    F_backup = array.array("f", T.F)
    sc_early = standardise(T, fit_mask=early)
    tgt_e = z_target(raw, sc_early, ev_ord)
    for wh in ("A", "B", "C"):
        r_oos = analogue_test(T, tgt_e, 200, which=wh, gap=60, row_mask=late,
                              shuffle_reps=shuf, pool=30000)
        _, bn2, br2 = base_rate(T, wh, late)
        print(f"      placement {wh}: n={r_oos['n']} flips={r_oos['flips']} "
              f"rate={r_oos['rate']:.2%} [{r_oos['lo']:.2%},{r_oos['hi']:.2%}]"
              f" vs LATE-half base {br2:.4%} (ratio {r_oos['ratio']:.2f}), "
              f"p_shuf={r_oos['p_shuffle']:.4f}, "
              f"MDE={mde_prop(br2, r_oos['n']):.2%}")
    T.F = F_backup

    print("\n  (d) REAL-CLOSE-ALIGNED SUBSET -- cells where t+tau is an "
          "actual 15-minute boundary, so the synthetic close is a real one.")
    almask = bytearray(T.aligned)
    if sum(almask) > 2000:
        r_al = analogue_test(T, tgt, 200, which="A", gap=60, row_mask=almask,
                             shuffle_reps=(0 if a.quick else 2000), pool=30000)
        _, an2, ar2 = base_rate(T, "A", almask)
        print(f"      aligned cells {sum(almask):,}: n={r_al['n']} "
              f"rate={r_al['rate']:.2%} vs aligned base {ar2:.4%} "
              f"(ratio {r_al['ratio']:.2f}), p_shuf={r_al['p_shuffle']:.4f}, "
              f"MDE={mde_prop(ar2, r_al['n']):.2%}")
    else:
        print(f"      only {sum(almask):,} aligned cells -- NOT ENOUGH, no "
              f"number reported.")

    print("\n" + SEP)
    print("8. THE COST -- what a gate on this fingerprint would have refused")
    print(SEP)
    radii = sorted({round(x, 3) for x in
                    [results[("A", 50)]["radius"], full["radius"],
                     results[("A", 1000)]["radius"], 1.0, 1.5, 2.0, 3.0]
                    if x == x})
    cost_section(a, scales, tgt, T.names, radii)

    print("\n" + SEP)
    print(f"done in {time.time() - T0:.0f}s")
    print(SEP)
    return 0


if __name__ == "__main__":
    sys.exit(main())
