#!/usr/bin/env python3
# VERSION: 2026-09-08-vc1
"""volcheck.py -- VALIDATE THE VOLATILITY ESTIMATOR ALONE, ON ITS OWN TERMS.

    python research/volcheck.py --selftest
    python research/volcheck.py --hours 336 --stride 7

WHAT IS BEING TESTED, AND WHY IT COMES FIRST

Everything this project prices rests on one number. Settlement is the mean of
60 one-second CF Benchmarks prints over [close-60, close-1].  With r prints
unpublished and locked sum L,

    mu            = (L + r*spot)/60
    required_move = (60/r) * (K_eff - mu)
    m(t,r)        = mean(v[t+1..t+r]) - v[t]        <- what must beat it
    p_flip        = P(m crosses required_move)

The shipped model turns that into a probability with a GAUSSIAN whose scale is

    sd_pred = sigma_300(t) * sqrt(var_factor(r,[1.0])) * (60/r)

where sigma_300 is the SD of one-second index differences over a trailing
300 s.  That 300 s is arbitrary.  It has never been validated as an estimator.
This file validates it -- and nothing downstream of it.

THE SCALING IS EXACT ALGEBRA, NOT A MODEL.  With iid increments d_i,
m(t,r) = (1/r) * sum_{i=1..r} (r-i+1) d_i, so

    Var(m) = sigma^2 * r(r+1)(2r+1) / (6 r^2)

and sigma^2 * var_factor(r,[1.0]) * (60/r)^2 is the same number, because
var_factor(r,[1.0]) = r(r+1)(2r+1)/21600 for r <= 60.  selftest() checks that
identity against engine.var_factor to 1e-12 and against Monte Carlo to 1%.
So EVERY error in sd_pred is one of exactly two things:

    (1) sigma_300 is the wrong scale      -- BIAS or NOISE in the estimator
    (2) increments are not iid gaussian   -- TAILS

They need different fixes and this file refuses to conflate them.  Bias is
read off the pooled realised/predicted ratio; noise is read off the SPREAD of
that ratio across blocks; tails are read off the exceedance counts of the
standardised move at 2/3/4/6 sigma against 4.6% / 0.27% / 0.0063% / 2e-9.

THE ESTIMATOR HORSE-RACE.  All backward-looking, all on identical cells:
trailing SD at 30/60/120/300/900 s; EWMA of squared increments at half-lives
15/60/300 s; a bipower estimator sqrt((pi/2)*mean(|d_i||d_{i-1}|)) which one
jump cannot inflate for a whole window; and an r-MATCHED estimator that takes
the RMS of past realised m(s,r) directly, never scaling a one-second sigma at
all.  Scored by RMSE against realised |m| (normalised per (index,r) by
mean|m|, or BTC's price scale would swamp DOGE's) and by the log-loss of the
p_flip each implies.

NO LOOKAHEAD.  Every estimator at second t reads only seconds <= t.  The
r-matched one reads only windows that ENDED at or before t (s + r <= t).  The
one in-sample quantity is the per-(index,r) move scale used to place the
synthetic log-loss threshold, which is identical for every estimator and so
cannot favour one; the real-tape leg of the study uses the genuine
required_move and the genuine settled outcome instead, and needs no such
choice.

SELF-TEST.  Four worlds with a known answer -- constant-sigma gaussian, a 5x
regime switch, a t(3) fat-tailed world, and a world with one 50-sigma jump --
plus the requirement that the constant world yields NO tail excess and NO
bias.  An estimator that cannot tell a fat tail from a gaussian, or that finds
a fat tail in a gaussian, fails here before it touches the tape.
"""
import argparse
import array
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
from engine import var_factor, N_AVG                        # noqa: E402

IDXDIR = r"C:\kals\kalshi_data\cfbenchmarks_value"
ROWS = os.path.join(os.path.dirname(HERE), "results", "pindata", "rows.jsonl")

SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI",
    "KXBNB15M": "BNBUSD_RTI", "KXZEC15M": "ZECUSD_RTI",
    "KXHYPE15M": "HYPEUSD_RTI", "KXNEAR15M": "NEARUSD_RTI",
}
WANT_IDX = sorted(set(SERIES_TO_INDEX.values()))

# r = tau - 1.  pin trades tau <= 20, i.e. r <= 19; the rest map the whole
# window so the failure can be seen to grow or shrink with horizon.
R_SET = (2, 3, 5, 9, 14, 19, 29, 44, 59)
SQ2 = math.sqrt(2.0)


def phi(x):
    """Standard normal CDF via erfc -- exact in the far tail where
    NormalDist().cdf() is fine too but this keeps the underflow explicit."""
    return 0.5 * math.erfc(-x / SQ2)


def sd_scale(r):
    """sqrt(var_factor(r,[1.0])) * (60/r) -- the model's move-sd multiplier."""
    return math.sqrt(var_factor(r, [1.0])) * (60.0 / r)


def sd_scale_closed(r):
    """The same thing in closed form: sqrt(r(r+1)(2r+1)/6)/r."""
    return math.sqrt(r * (r + 1) * (2 * r + 1) / 6.0) / r


# ===========================================================================
# the series, and every backward-looking estimator built on it as O(1) lookups
# ===========================================================================
class Idx:
    """One index as a dense per-second array plus prefix sums.

    Gaps are real (the tape drops seconds), so nothing is forward-filled.
    Every window carries its own present-count and a window that is not
    fully covered is simply not sampled.  That is the guard, and main()
    prints how much it discards so a guard that ate everything cannot look
    like a thin tape.
    """

    def __init__(self, name, base, vals, pres):
        self.name = name
        self.base = base
        self.v = vals                       # array('d'), NaN where absent
        self.pres = pres                    # bytearray 0/1
        self.n = len(vals)
        self.built = False

    def build(self, ewma_hl=(15, 60, 300)):
        n, v, pres = self.n, self.v, self.pres
        SV = array.array("d", [0.0]) * 0
        SV = array.array("d", bytes(8 * (n + 1)))
        CP = array.array("l", bytes(array.array("l").itemsize * (n + 1)))
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
        self.SV, self.CP = SV, CP

        SD2 = array.array("d", bytes(8 * n))
        CD = array.array("l", bytes(array.array("l").itemsize * n))
        SBP = array.array("d", bytes(8 * n))
        CBP = array.array("l", bytes(array.array("l").itemsize * n))
        ew = [array.array("d", bytes(8 * n)) for _ in ewma_hl]
        lam = [0.5 ** (1.0 / h) for h in ewma_hl]
        cur = [0.0] * len(ewma_hl)
        seen = [0] * len(ewma_hl)
        s2 = 0.0
        cd = 0
        sbp = 0.0
        cbp = 0
        prev_ad = None                      # |d| of the previous VALID diff
        prev_j = None
        for j in range(1, n):
            ok = pres[j] and pres[j - 1]
            if ok:
                d = v[j] - v[j - 1]
                ad = -d if d < 0 else d
                s2 += d * d
                cd += 1
                if prev_ad is not None and prev_j == j - 1:
                    sbp += ad * prev_ad
                    cbp += 1
                prev_ad, prev_j = ad, j
                dd = d * d
                for k in range(len(ewma_hl)):
                    if seen[k]:
                        cur[k] = lam[k] * cur[k] + (1.0 - lam[k]) * dd
                    else:
                        cur[k] = dd
                        seen[k] = 1
            SD2[j] = s2
            CD[j] = cd
            SBP[j] = sbp
            CBP[j] = cbp
            for k in range(len(ewma_hl)):
                ew[k][j] = cur[k]
        self.SD2, self.CD, self.SBP, self.CBP = SD2, CD, SBP, CBP
        self.ew, self.ewma_hl = ew, tuple(ewma_hl)
        self.built = True

    # -- estimators, all reading only indices <= i -------------------------
    def sd_win(self, i, w, minc=15):
        """Trailing SD of one-second diffs over the last w seconds.
        Window convention matches research/pindata.py idx_feats exactly:
        diffs at j in [max(1, i-w), i], i.e. w+1 of them when unclipped."""
        lo = i - w
        if lo < 1:
            lo = 1
        c = self.CD[i] - self.CD[lo - 1]
        if c < minc:
            return None
        return math.sqrt((self.SD2[i] - self.SD2[lo - 1]) / c)

    def sd_ewma(self, i, k):
        x = self.ew[k][i]
        return math.sqrt(x) if x > 0 else None

    def sd_bipower(self, i, w, minc=15):
        """sqrt((pi/2) * mean(|d_j| |d_{j-1}|)).  A single jump enters only two
        products instead of squaring itself into the whole window."""
        lo = i - w
        if lo < 2:
            lo = 2
        c = self.CBP[i] - self.CBP[lo - 1]
        if c < minc:
            return None
        return math.sqrt((math.pi / 2.0) * (self.SBP[i] - self.SBP[lo - 1]) / c)

    # -- the thing being predicted -----------------------------------------
    def move(self, t, r):
        """m(t,r) = mean(v[t+1..t+r]) - v[t].  None unless every second in
        [t, t+r] is present."""
        if t < 0 or t + r >= self.n:
            return None
        if self.CP[t + r + 1] - self.CP[t] != r + 1:
            return None
        return (self.SV[t + r + 1] - self.SV[t + 1]) / r - self.v[t]


def build_rmatch(idx, r):
    """Prefix sums of realised m(s,r)^2, so the r-MATCHED estimator can read
    the SD of the r-second average move straight out of history instead of
    scaling a one-second sigma.  Indexed by the window's START second s; the
    caller must only ever ask for s with s + r <= t."""
    n = idx.n
    SM2 = array.array("d", bytes(8 * (n + 1)))
    CM = array.array("l", bytes(array.array("l").itemsize * (n + 1)))
    mv = idx.move
    s2 = 0.0
    c = 0
    for s in range(n):
        SM2[s] = s2
        CM[s] = c
        m = mv(s, r)
        if m is not None:
            s2 += m * m
            c += 1
    SM2[n] = s2
    CM[n] = c
    return SM2, CM


def rmatch_sd(SM2, CM, t, r, W, minc=60):
    """RMS of past m(s,r) over the W seconds of windows that CLOSED by t."""
    hi = t - r                              # last start whose window ended <= t
    if hi < 0:
        return None
    lo = hi - W
    if lo < 0:
        lo = 0
    c = CM[hi + 1] - CM[lo]
    if c < minc:
        return None
    x = (SM2[hi + 1] - SM2[lo]) / c
    return math.sqrt(x) if x > 0 else None


# ===========================================================================
# loading -- newest hour file is a live truncated gzip; catch it and move on
# ===========================================================================
def load_index(hours, datadir=IDXDIR, want=None, verbose=True):
    files = sorted(glob.glob(os.path.join(datadir, "2026*.jsonl.gz")))
    if hours:
        files = files[-hours:]
    want = set(want or WANT_IDX)
    raw = defaultdict(dict)
    bad = 0
    for f in files:
        try:
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    try:
                        d = json.loads(line)
                        m = d["msg"]
                        iid = m["index_id"]
                        if iid not in want:
                            continue
                        dd = json.loads(m["data"])
                        raw[iid][int(dd["time"]) // 1000] = float(dd["value"])
                    except Exception:
                        continue
        except (EOFError, zlib.error, OSError) as e:
            bad += 1
            if verbose:
                print(f"    truncated/unreadable (expected for the live hour): "
                      f"{os.path.basename(f)} {type(e).__name__}")
    out = {}
    for iid, d in raw.items():
        if not d:
            continue
        lo, hi = min(d), max(d)
        n = hi - lo + 1
        vals = array.array("d", [float("nan")]) * n
        pres = bytearray(n)
        for s, v in d.items():
            vals[s - lo] = v
            pres[s - lo] = 1
        out[iid] = Idx(iid, lo, vals, pres)
    if verbose:
        print(f"  files={len(files)} unreadable={bad}")
        for iid in sorted(out):
            ix = out[iid]
            cov = sum(ix.pres) / ix.n
            print(f"    {iid:<12} span={ix.n:>9,}s  present={sum(ix.pres):>9,}"
                  f"  coverage={cov:6.3%}")
    return out, files


def synth(name, diffs, base=0):
    """Build an Idx from a list of one-second increments -- for the selftest."""
    vals = array.array("d", [0.0]) * (len(diffs) + 1)
    v = 1000.0
    vals[0] = v
    for i, d in enumerate(diffs):
        v += d
        vals[i + 1] = v
    ix = Idx(name, base, vals, bytearray(b"\x01" * len(vals)))
    ix.build()
    return ix


# ===========================================================================
# the estimator panel
# ===========================================================================
# (name, kind, param) -- kind: "win" trailing SD, "ew" EWMA, "bp" bipower,
# "rm" r-matched direct.  Everything but "rm" produces a ONE-SECOND sigma that
# is then multiplied by sd_scale(r); "rm" produces the move sd directly.
ESTS = (
    ("sd30",   "win", 30),
    ("sd60",   "win", 60),
    ("sd120",  "win", 120),
    ("sd300",  "win", 300),          # <-- THE SHIPPED ONE
    ("sd900",  "win", 900),
    ("ew15",   "ew", 0),
    ("ew60",   "ew", 1),
    ("ew300",  "ew", 2),
    ("bp300",  "bp", 300),
    ("rmatch", "rm", 1800),
)
SHIPPED = 3                                  # index of sd300 in ESTS
K_ABS = math.sqrt(2.0 / math.pi)             # E|X| / sd for a gaussian
TAILS = (2.0, 3.0, 4.0, 6.0)
GAUSS_TAIL = tuple(2.0 * phi(-x) for x in TAILS)
PCLAMP = 1e-6
LL_C = 2.3263478740408408                    # one-sided 1% gaussian point


def blank():
    # n, sum z2, t2, t3, t4, t6, sum|m|, sse_abs, sum m^2, sum sd^2,
    # sum min(z^2,9) -- the WINSORISED second moment.  sd(z) is itself
    # driven by the tail it is meant to be describing; clipping at 3 sigma
    # gives the scale of the BODY, which is what tells a mis-scaled sigma
    # apart from a correctly-scaled sigma with a fat tail.
    return [0, 0.0, 0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0]


def _sd_at(t, r, ei, sc, CD, SD2, CBP, SBP, ew, CM, SM2):
    """One estimator's predicted sd of m(t,r), or None. Backward-looking."""
    nm, kind, par = ESTS[ei]
    if kind == "win":
        lo = t - par
        if lo < 1:
            lo = 1
        c = CD[t] - CD[lo - 1]
        if c < 15:
            return None
        return math.sqrt((SD2[t] - SD2[lo - 1]) / c) * sc
    if kind == "ew":
        x = ew[par][t]
        if x <= 0:
            return None
        return math.sqrt(x) * sc
    if kind == "bp":
        lo = t - par
        if lo < 2:
            lo = 2
        c = CBP[t] - CBP[lo - 1]
        if c < 15:
            return None
        x = (SBP[t] - SBP[lo - 1]) / c
        if x <= 0:
            return None
        return math.sqrt(1.5707963267948966 * x) * sc
    hi = t - r
    if hi < 0:
        return None
    lo2 = hi - par
    if lo2 < 0:
        lo2 = 0
    c = CM[hi + 1] - CM[lo2]
    if c < 60:
        return None
    x = (SM2[hi + 1] - SM2[lo2]) / c
    if x <= 0:
        return None
    return math.sqrt(x)


def scan_index(ix, rs, stride, ll_every, acc, S, cond, blocks, llacc,
               warm=1900, ll_c=LL_C):
    """Walk one index once per r.

    acc[(est,r)]     dense z-stats, tail counts, |m| RMSE parts
    S[(coin,r)]      the realised move scale, used to place the log-loss bar
    cond[key]        conditional slices for the SHIPPED estimator
    blocks[(est,r)]  per-hour realised/predicted ratios, non-overlapping
    llacc[(est,r)]   log-loss at the 1% one-sided operating point
    """
    n = ix.n
    SV, CP, SD2, CD, SBP, CBP, ew, v = (ix.SV, ix.CP, ix.SD2, ix.CD,
                                        ix.SBP, ix.CBP, ix.ew, ix.v)
    base = ix.base
    sqrt = math.sqrt
    log = math.log
    ne = len(ESTS)
    for r in rs:
        SM2, CM = build_rmatch(ix, r)
        sc = sd_scale(r)
        start = max(warm, 1900)
        keys = [(nm, r) for nm, _, _ in ESTS]
        for k in keys:
            if k not in acc:
                acc[k] = blank()
        A = [acc[k] for k in keys]
        sm2 = 0.0
        cnt = 0
        # ---- loop A: dense ------------------------------------------------
        for t in range(start, n - r, stride):
            if CP[t + r + 1] - CP[t] != r + 1:
                continue
            m = (SV[t + r + 1] - SV[t + 1]) / r - v[t]
            am = -m if m < 0 else m
            sm2 += m * m
            cnt += 1
            for ei in range(ne):
                sd = _sd_at(t, r, ei, sc, CD, SD2, CBP, SBP, ew, CM, SM2)
                if not sd or sd <= 0:
                    continue
                a = A[ei]
                z = m / sd
                az = -z if z < 0 else z
                a[0] += 1
                a[1] += z * z
                if az > 2.0:
                    a[2] += 1
                    if az > 3.0:
                        a[3] += 1
                        if az > 4.0:
                            a[4] += 1
                            if az > 6.0:
                                a[5] += 1
                a[6] += am
                d = am - K_ABS * sd
                a[7] += d * d
                a[8] += m * m
                a[9] += sd * sd
                a[10] += 9.0 if az > 3.0 else z * z
                if ei == SHIPPED or ei == 9:
                    hk = ("hist" if ei == SHIPPED else "histR", r)
                    hh_ = cond.get(hk)
                    if hh_ is None:
                        hh_ = cond[hk] = [0] * HB_N
                    bi_ = int(az / HB_W)
                    hh_[bi_ if bi_ < HB_N else HB_N - 1] += 1
        S[(ix.name, r)] = (sqrt(sm2 / cnt) if cnt else None, cnt)

        # ---- conditional slices, SHIPPED estimator only --------------------
        spar = ESTS[SHIPPED][2]
        for t in range(start, n - r, stride):
            if CP[t + r + 1] - CP[t] != r + 1:
                continue
            lo = t - spar
            if lo < 1:
                lo = 1
            c = CD[t] - CD[lo - 1]
            if c < 15:
                continue
            s300 = sqrt((SD2[t] - SD2[lo - 1]) / c)
            if s300 <= 0:
                continue
            lo30 = t - 30
            if lo30 < 1:
                lo30 = 1
            c30 = CD[t] - CD[lo30 - 1]
            s30 = sqrt((SD2[t] - SD2[lo30 - 1]) / c30) if c30 >= 15 else None
            m = (SV[t + r + 1] - SV[t + 1]) / r - v[t]
            z = m / (s300 * sc)
            az = -z if z < 0 else z
            sec = base + t
            hh = (sec // 3600) % 24
            jump = 1 if (s30 is not None and s30 > 2.0 * s300) else 0
            vv = (s30 / s300) if s30 else 1.0
            vb = 0 if vv < 0.75 else (1 if vv < 1.25 else 2)
            for key in (("hour", hh), ("coin", ix.name),
                        ("jump", jump), ("vv", vb), ("r", r)):
                b = cond.get(key)
                if b is None:
                    b = cond[key] = [0, 0.0, 0, 0, 0, 0]
                b[0] += 1
                b[1] += z * z
                if az > 2.0:
                    b[2] += 1
                    if az > 3.0:
                        b[3] += 1
                        if az > 4.0:
                            b[4] += 1
                            if az > 6.0:
                                b[5] += 1

        # ---- loop B: sparse, log-loss at the 1% operating point ------------
        Sr = S[(ix.name, r)][0]
        if Sr and Sr > 0:
            req = ll_c * Sr
            bstride = stride * ll_every
            for t in range(start, n - r, bstride):
                if CP[t + r + 1] - CP[t] != r + 1:
                    continue
                m = (SV[t + r + 1] - SV[t + 1]) / r - v[t]
                yu = 1 if m > req else 0
                yd = 1 if m < -req else 0
                for ei in range(ne):
                    sd = _sd_at(t, r, ei, sc, CD, SD2, CBP, SBP, ew, CM, SM2)
                    if not sd or sd <= 0:
                        continue
                    p = phi(-req / sd)
                    if p < PCLAMP:
                        p = PCLAMP
                    elif p > 1.0 - PCLAMP:
                        p = 1.0 - PCLAMP
                    lp, lq = log(p), log(1.0 - p)
                    e = llacc.get((ESTS[ei][0], r))
                    if e is None:
                        e = llacc[(ESTS[ei][0], r)] = [0, 0.0, 0, 0.0]
                    e[0] += 2
                    e[1] += -(lp if yu else lq) - (lp if yd else lq)
                    e[2] += yu + yd
                    e[3] += 2.0 * p

        # ---- loop C: per-hour realised/predicted ratio, NON-OVERLAPPING ----
        bst = max(stride, r + 1)
        for ei in (SHIPPED, 6, 9):           # sd300, ew60, rmatch
            nm = ESTS[ei][0]
            cur_h = None
            rm2 = pm2 = 0.0
            k = 0
            for t in range(start, n - r, bst):
                h = (base + t) // 3600
                if cur_h is None:
                    cur_h = h
                if h != cur_h:
                    if k >= 20 and pm2 > 0:
                        blocks.setdefault((nm, r), []).append(
                            sqrt(rm2 / k) / sqrt(pm2 / k))
                    cur_h, rm2, pm2, k = h, 0.0, 0.0, 0
                if CP[t + r + 1] - CP[t] != r + 1:
                    continue
                sd = _sd_at(t, r, ei, sc, CD, SD2, CBP, SBP, ew, CM, SM2)
                if not sd or sd <= 0:
                    continue
                m = (SV[t + r + 1] - SV[t + 1]) / r - v[t]
                rm2 += m * m
                pm2 += sd * sd
                k += 1
            if k >= 20 and pm2 > 0:
                blocks.setdefault((nm, r), []).append(
                    sqrt(rm2 / k) / sqrt(pm2 / k))
        del SM2, CM


# ===========================================================================
def pct(xs, q):
    if not xs:
        return float("nan")
    s = sorted(xs)
    i = q * (len(s) - 1)
    lo = int(i)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


# ===========================================================================
# SELF-TEST -- four worlds whose volatility is known by construction
# ===========================================================================
def _z_stats(ix, r, w, sigma_true=None, est=("win", 300), lo=None, hi=None):
    """Pooled sd of m/sd_pred and tail counts over a stretch, done the long
    way (no prefix shortcuts) so the fast path has something to disagree
    with."""
    sc = sd_scale(r)
    lo = lo if lo is not None else 1900
    hi = hi if hi is not None else ix.n - r - 1
    n = 0
    s2 = 0.0
    t = [0, 0, 0, 0]
    for i in range(lo, hi):
        m = ix.move(i, r)
        if m is None:
            continue
        if est[0] == "win":
            s = ix.sd_win(i, est[1])
        elif est[0] == "bp":
            s = ix.sd_bipower(i, est[1])
        else:
            s = ix.sd_ewma(i, est[1])
        if not s:
            continue
        z = m / (s * sc)
        n += 1
        s2 += z * z
        a = abs(z)
        for k, thr in enumerate(TAILS):
            if a > thr:
                t[k] += 1
    return n, (math.sqrt(s2 / n) if n else None), t


def selftest():
    print("SELF-TEST -- volcheck")
    fails = []

    def ck(cond, msg):
        print(("  PASS  " if cond else "  FAIL  ") + msg)
        if not cond:
            fails.append(msg)

    # -- 0. the scaling identity is algebra, and must be exact --------------
    worst = max(abs(sd_scale(r) - sd_scale_closed(r)) / sd_scale_closed(r)
                for r in range(1, 61))
    ck(worst < 1e-12,
       f"sd_scale == sqrt(r(r+1)(2r+1)/6)/r for r=1..60 (max rel err {worst:.2e})")

    # -- 1. move() is the right quantity ------------------------------------
    ix = Idx("T", 0, array.array("d", [10.0, 11.0, 12.0, 13.0, 14.0]),
             bytearray(b"\x01" * 5))
    ix.build()
    ck(abs(ix.move(0, 4) - 2.5) < 1e-12,
       f"m(0,4) on 10,11,12,13,14 is mean(11..14)-10 = 2.5 "
       f"({ix.move(0, 4)})")
    v = array.array("d", [10.0, 11.0, float("nan"), 13.0, 14.0])
    p = bytearray([1, 1, 0, 1, 1])
    ix2 = Idx("T2", 0, v, p)
    ix2.build()
    ck(ix2.move(0, 4) is None,
       "a window containing a missing second is dropped, not filled")

    rnd = random.Random(20260908)

    # -- 2. CONSTANT-SIGMA GAUSSIAN: sigma recovered, z ~ N(0,1) ------------
    SIG = 1.0
    N = 300000
    w1 = synth("W1", [rnd.gauss(0.0, SIG) for _ in range(N)])
    acc, S, cond, blocks, ll = {}, {}, {}, {}, {}
    scan_index(w1, (5, 19), stride=3, ll_every=10, acc=acc, S=S, cond=cond,
               blocks=blocks, llacc=ll)
    a = acc[("sd300", 19)]
    zsd = math.sqrt(a[1] / a[0])
    ck(0.985 < zsd < 1.015,
       f"constant world, r=19: sd of m/sd_pred is 1.000 ({zsd:.4f})")
    # pooled realised/predicted -- the bias read
    bias = math.sqrt(a[8] / a[9])
    ck(0.985 < bias < 1.015,
       f"constant world: pooled realised/predicted sd is 1.000 ({bias:.4f})")
    # the closed-form scale is right: realised sd of m vs sigma*sd_scale(r)
    for r in (5, 19):
        aa = acc[("sd300", r)]
        realised = math.sqrt(aa[8] / aa[0])
        want = SIG * sd_scale(r)
        ck(abs(realised / want - 1.0) < 0.02,
           f"constant world r={r}: realised sd(m)={realised:.4f} vs "
           f"closed form {want:.4f} (rel {realised/want-1:+.3%})")
    # NOTHING SPURIOUS: gaussian tails must come back gaussian
    for k, thr in enumerate(TAILS[:3]):
        got = a[2 + k] / a[0]
        exp = GAUSS_TAIL[k]
        rat = got / exp if exp else float("inf")
        band = (0.75, 1.35) if k < 2 else (0.3, 3.0)
        ck(band[0] < rat < band[1],
           f"constant world: |z|>{thr:.0f} realised {got:.3%} vs gaussian "
           f"{exp:.3%}, ratio {rat:.2f} -- no spurious fat tail")
    br = blocks[("sd300", 19)]
    med = pct(br, 0.5)
    ck(len(br) >= 20 and 0.93 < med < 1.07,
       f"constant world: median per-hour realised/predicted {med:.3f} on "
       f"{len(br)} blocks -- unbiased")
    # the r-matched estimator must also land on 1 in a stationary world
    ar = acc[("rmatch", 19)]
    zr = math.sqrt(ar[1] / ar[0])
    ck(0.96 < zr < 1.05,
       f"constant world: r-matched estimator gives z sd {zr:.4f}")
    del w1, acc, S, cond, blocks, ll

    # -- 3. REGIME SWITCH: the 300 s window MUST be caught out --------------
    M = 60000
    ds = [rnd.gauss(0.0, 1.0) for _ in range(M)] + \
         [rnd.gauss(0.0, 5.0) for _ in range(M)]
    w2 = synth("W2", ds)
    r = 19
    sc = sd_scale(r)
    for tag, est in (("sd300", ("win", 300)), ("ew15", ("ewma", 0))):
        n2, sd2, _ = _z_stats(w2, r, None, est=est, lo=M + 5, hi=M + 205)
        if tag == "sd300":
            sd_slow = sd2
        else:
            sd_fast = sd2
    ck(sd_slow > 1.25,
       f"regime switch: 300s SD under-predicts for 200s after a 5x jump in "
       f"vol -- z sd {sd_slow:.2f} (>1.25 required)")
    ck(sd_fast < sd_slow,
       f"regime switch: a 15s-halflife EWMA tracks it better "
       f"(z sd {sd_fast:.2f} vs {sd_slow:.2f})")
    n3, sd3, _ = _z_stats(w2, r, None, est=("win", 300),
                          lo=2000, hi=M - r - 2)
    ck(0.93 < sd3 < 1.07,
       f"regime switch: BEFORE the switch the same estimator is unbiased "
       f"(z sd {sd3:.3f}) -- so the failure above is the regime, not a bug")
    del w2, ds

    # -- 4. FAT TAILS: scale right, tails wrong, and it must SEE that -------
    def t3():
        z = rnd.gauss(0.0, 1.0)
        w = sum(rnd.gauss(0.0, 1.0) ** 2 for _ in range(3))
        return (z / math.sqrt(w / 3.0)) / math.sqrt(3.0)   # unit variance
    N4 = 400000
    w3 = synth("W3", [t3() for _ in range(N4)])
    n4, sd4, t4 = _z_stats(w3, 5, None, est=("win", 300))
    ck(0.85 < sd4 < 1.25,
       f"t(3) world: the SCALE is still about right (z sd {sd4:.3f}) -- a "
       f"fat tail is not a scale error")
    rat3 = (t4[1] / n4) / GAUSS_TAIL[1]
    rat4 = (t4[2] / n4) / GAUSS_TAIL[2]
    ck(rat3 > 1.5,
       f"t(3) world: |z|>3 is {t4[1]/n4:.3%} vs gaussian {GAUSS_TAIL[1]:.3%} "
       f"-- ratio {rat3:.1f}x, the tail is DETECTED")
    ck(rat4 > 3.0,
       f"t(3) world: |z|>4 is {t4[2]/n4:.4%} vs gaussian {GAUSS_TAIL[2]:.4%} "
       f"-- ratio {rat4:.1f}x")
    del w3

    # -- 5. ONE JUMP: trailing SD is poisoned, bipower is not ---------------
    N5 = 20000
    ds5 = [rnd.gauss(0.0, 1.0) for _ in range(N5)]
    JT = 10000
    ds5[JT] += 50.0
    w4 = synth("W4", ds5)
    at = JT + 60                       # 60s later: the jump is inside 300s
    s_win = w4.sd_win(at, 300)
    s_bp = w4.sd_bipower(at, 300)
    ck(s_win > 2.0,
       f"jump world: trailing 300s SD is inflated to {s_win:.2f} by a single "
       f"50-sigma print (true sigma 1.0)")
    ck(s_bp < 1.5,
       f"jump world: bipower over the same window reads {s_bp:.2f} -- one "
       f"jump cannot inflate it")
    s_win_far = w4.sd_win(JT - 60, 300)
    ck(0.85 < s_win_far < 1.15,
       f"jump world: the same trailing SD 60s BEFORE the jump reads "
       f"{s_win_far:.3f} -- so the inflation is the jump, not a bug")
    del w4, ds5

    print(f"\n{'FAILED: ' + str(len(fails)) if fails else 'ALL PASS'}")
    for f in fails:
        print("   - " + f)
    return 1 if fails else 0


# ===========================================================================
HB_W = 0.01
HB_N = 4001          # |z| in [0,40) at 0.01, last bin is the overflow


def hist_tail(h, x):
    """One-sided empirical P(z > x) from a |z| histogram, assuming symmetry.
    Never returns 0: a tail that has not been observed is reported at the
    resolution limit, not as impossible."""
    tot = sum(h)
    if tot <= 0:
        return None
    i = int(x / HB_W)
    if i >= HB_N - 1:
        c = h[HB_N - 1]
    else:
        c = sum(h[i + 1:])
    return max(c, 0.5) / (2.0 * tot)


def load_rows(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--hours", type=int, default=0)
    ap.add_argument("--stride", type=int, default=7)
    ap.add_argument("--ll-every", type=int, default=10)
    ap.add_argument("--data", default=IDXDIR)
    ap.add_argument("--rows", default=ROWS)
    ap.add_argument("--rs", default=",".join(str(x) for x in R_SET))
    ap.add_argument("--margin", type=float, default=0.02)
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_SELFTESTED") != "1":
        if selftest():
            print("SELF-TEST FAILED -- refusing to touch real data")
            return 1
        print()

    rs = tuple(int(x) for x in a.rs.split(","))
    t0 = time.time()
    print("=" * 78)
    print("VOLCHECK -- is sigma_300 a good estimator of the move it is asked "
          "to price?")
    print("=" * 78)
    print(f"\nLOADING  {a.data}")
    idxs, files = load_index(a.hours, a.data)
    if not idxs:
        print("loaded nothing")
        return 0
    print(f"  load {time.time()-t0:.0f}s")

    acc, S, cond, blocks, llacc = {}, {}, {}, {}, {}
    for nm in sorted(idxs):
        ix = idxs[nm]
        tb = time.time()
        ix.build()
        scan_index(ix, rs, a.stride, a.ll_every, acc, S, cond, blocks, llacc)
        # free the heavy prefix arrays; the raw series stays for the rows leg
        for at in ("SV", "CP", "SD2", "CD", "SBP", "CBP", "ew"):
            if hasattr(ix, at):
                delattr(ix, at)
        ix.built = False
        print(f"  scanned {nm:<12} {time.time()-tb:6.0f}s")

    n_pool = sum(acc[(nm, r)][0] for r in rs for nm, _, _ in ESTS
                 if nm == "sd300")
    print(f"\nGRID: stride {a.stride}s, r in {rs}, {len(idxs)} indices, "
          f"{n_pool:,} (index, second, r) cells for the shipped estimator")

    # ---- 1. THE CENTRAL MEASUREMENT --------------------------------------
    print("\n" + "=" * 78)
    print("1. THE SHIPPED ESTIMATOR: distribution of  m(t,r) / sd_pred")
    print("   sd_pred = sigma_300 * sqrt(var_factor(r,[1.0])) * (60/r)")
    print("=" * 78)
    print(f"{'r':>4} {'tau':>4} {'n':>11} {'sd(z)':>7} {'|z|>2':>9} {'|z|>3':>9}"
          f" {'|z|>4':>10} {'|z|>6':>11}")
    print(f"{'':>4} {'':>4} {'':>11} {'want 1':>7} {'4.550%':>9} {'0.270%':>9}"
          f" {'0.0063%':>10} {'2.0e-07%':>11}")
    tot = [0, 0.0, 0, 0, 0, 0]
    for r in rs:
        x = acc[("sd300", r)]
        if not x[0]:
            continue
        for i in range(6):
            tot[i] += x[i]
        print(f"{r:>4} {r+1:>4} {x[0]:>11,} {math.sqrt(x[1]/x[0]):>7.3f}"
              f" {x[2]/x[0]:>8.3%} {x[3]/x[0]:>8.3%}"
              f" {x[4]/x[0]:>9.4%} {x[5]/x[0]:>10.3e}")
    print("-" * 78)
    print(f"{'ALL':>9} {tot[0]:>11,} {math.sqrt(tot[1]/tot[0]):>7.3f}"
          f" {tot[2]/tot[0]:>8.3%} {tot[3]/tot[0]:>8.3%}"
          f" {tot[4]/tot[0]:>9.4%} {tot[5]/tot[0]:>10.3e}")
    print("\nTAIL RATIO -- realised frequency divided by what a gaussian claims")
    for k, thr in enumerate(TAILS):
        got = tot[2 + k] / tot[0]
        exp = GAUSS_TAIL[k]
        print(f"  |z| > {thr:.0f}: realised {got:.6%}  gaussian {exp:.6%}"
              f"   RATIO {got/exp:>10.1f}x")

    # ---- 2. BIAS OR NOISE -------------------------------------------------
    print("\n" + "=" * 78)
    print("2. IS SIGMA BIASED OR JUST NOISY?  per-hour realised/predicted sd,")
    print("   non-overlapping windows inside each hour block")
    print("=" * 78)
    print(f"{'est':>8} {'r':>4} {'blocks':>7} {'p05':>6} {'p25':>6} {'MED':>6}"
          f" {'p75':>6} {'p95':>6} {'p99':>6} {'pooled':>7}")
    for nm in ("sd300", "ew60", "rmatch"):
        for r in rs:
            b = blocks.get((nm, r))
            if not b or len(b) < 20:
                continue
            x = acc[(nm, r)]
            pooled = math.sqrt(x[8] / x[9]) if x[9] else float("nan")
            print(f"{nm:>8} {r:>4} {len(b):>7} {pct(b,.05):>6.3f}"
                  f" {pct(b,.25):>6.3f} {pct(b,.50):>6.3f} {pct(b,.75):>6.3f}"
                  f" {pct(b,.95):>6.3f} {pct(b,.99):>6.3f} {pooled:>7.3f}")

    # ---- 3. THE ESTIMATOR RACE -------------------------------------------
    print("\n" + "=" * 78)
    print("3. ESTIMATOR RACE -- same cells, all backward-looking")
    print("   RMSE is against realised |m|, prediction sqrt(2/pi)*sd_pred,")
    print("   normalised by mean|m| so BTC does not swamp DOGE.")
    print("   log-loss is of p_flip at a required move of "
          f"{LL_C:.3f} x the (index,r) move scale (~1% base rate each side).")
    print("=" * 78)
    print(f"{'estimator':>10} {'n':>12} {'sd(z)':>7} {'pooled':>7} {'nRMSE':>7}"
          f" {'logloss':>8} {'base':>7} {'pred':>7} {'|z|>3':>8} {'|z|>4':>9}")
    race = []
    for nm, _, _ in ESTS:
        n = s2 = t3 = t4 = 0
        z2 = sse = sa = mm = ss = 0.0
        for r in rs:
            x = acc.get((nm, r))
            if not x:
                continue
            n += x[0]
            z2 += x[1]
            t3 += x[3]
            t4 += x[4]
            sa += x[6]
            sse += x[7]
            mm += x[8]
            ss += x[9]
        if not n:
            continue
        mean_abs = sa / n
        nrmse = math.sqrt(sse / n) / mean_abs
        e = [0, 0.0, 0, 0.0]
        for r in rs:
            y = llacc.get((nm, r))
            if y:
                for i in range(4):
                    e[i] += y[i]
        ll = e[1] / e[0] if e[0] else float("nan")
        base = e[2] / e[0] if e[0] else float("nan")
        predr = e[3] / e[0] if e[0] else float("nan")
        race.append((nm, n, math.sqrt(z2 / n), math.sqrt(mm / ss), nrmse, ll,
                     base, predr, t3 / n, t4 / n))
    for row in race:
        mark = "  <-- SHIPPED" if row[0] == "sd300" else ""
        print(f"{row[0]:>10} {row[1]:>12,} {row[2]:>7.3f} {row[3]:>7.3f}"
              f" {row[4]:>7.4f} {row[5]:>8.5f} {row[6]:>7.4%} {row[7]:>7.4%}"
              f" {row[8]:>8.4%} {row[9]:>9.5%}{mark}")
    best_rmse = min(race, key=lambda x: x[4])[0]
    best_ll = min(race, key=lambda x: x[5])[0]
    print(f"\n  best nRMSE: {best_rmse}     best log-loss: {best_ll}")

    # ---- 4. CONDITIONALS --------------------------------------------------
    print("\n" + "=" * 78)
    print("4. CONDITIONAL -- does the shipped estimator fail somewhere "
          "in particular?")
    print("=" * 78)
    for grp, lab in (("coin", "index"), ("hour", "UTC hour"),
                     ("jump", "s30 > 2*s300 (a jump just happened)"),
                     ("vv", "vol-of-vol bucket s30/s300 (<0.75, 0.75-1.25, >)")):
        print(f"\n  by {lab}")
        ks = sorted([k for k in cond if k[0] == grp], key=lambda k: str(k[1]))
        for k in ks:
            b = cond[k]
            if b[0] < 1000:
                continue
            print(f"    {str(k[1]):>12} n={b[0]:>10,}  sd(z)={math.sqrt(b[1]/b[0]):>6.3f}"
                  f"  |z|>3 {b[3]/b[0]:>7.4%} ({b[3]/b[0]/GAUSS_TAIL[1]:>6.1f}x)"
                  f"  |z|>4 {b[4]/b[0]:>8.5%} ({b[4]/b[0]/GAUSS_TAIL[2]:>7.1f}x)")

    # ---- 5. THE REAL TAPE, REAL STRIKES, REAL OUTCOMES --------------------
    rows = load_rows(a.rows)
    print("\n" + "=" * 78)
    print(f"5. THE TRADED POPULATION -- {len(rows):,} rows from {a.rows}")
    print("   real required_move, real settled flip, no synthetic threshold")
    print("=" * 78)
    if rows:
        by_idx = defaultdict(list)
        for row in rows:
            iid = SERIES_TO_INDEX.get(row["sr"])
            if iid in idxs:
                by_idx[iid].append(row)
        ok_sig = bad_sig = 0
        worst_sig = 0.0
        ok_flip = bad_flip = nomatch = 0
        dat = []
        # ONE index at a time: nine sets of prefix arrays at once is ~900 MB
        # and the collector outranks this job.
        for iid in sorted(by_idx):
            ix = idxs[iid]
            ix.build()
            for row in by_idx[iid]:
                t = int(row["sec"]) - ix.base
                r = int(row["r"])
                if t < 1900 or t + r >= ix.n:
                    continue
                s300 = ix.sd_win(t, 300)
                if not s300:
                    continue
                if row.get("sig"):
                    rel = abs(s300 - row["sig"]) / row["sig"]
                    worst_sig = max(worst_sig, rel)
                    if rel < 1e-9:
                        ok_sig += 1
                    else:
                        bad_sig += 1
                m = ix.move(t, r)
                if m is None:
                    nomatch += 1
                    continue
                req = float(row["req"])
                flip_calc = (m >= req) if req > 0 else (m <= req)
                if flip_calc == bool(row["flip"]):
                    ok_flip += 1
                else:
                    bad_flip += 1
                sc = sd_scale(r)
                sds = []
                for ei in range(len(ESTS)):
                    if ESTS[ei][1] == "rm":
                        sds.append(None)     # needs per-r history; see note
                    else:
                        sds.append(_sd_at(t, r, ei, sc, ix.CD, ix.SD2,
                                          ix.CBP, ix.SBP, ix.ew, None, None))
                dat.append((iid, t, r, req, m, bool(row["flip"]), s300,
                            row.get("s30"), row.get("s120"),
                            float(row["price"]), int(row["tau"]), tuple(sds)))
            for at in ("SV", "CP", "SD2", "CD", "SBP", "CBP", "ew"):
                if hasattr(ix, at):
                    delattr(ix, at)
            ix.built = False
        print(f"\n  RECONSTRUCTION CHECK (this pipeline vs the built dataset)")
        print(f"    sigma_300 identical to the row's 'sig': {ok_sig:,} of "
              f"{ok_sig+bad_sig:,}   worst relative diff {worst_sig:.2e}")
        print(f"    settled flip reproduced from m vs required_move: "
              f"{ok_flip:,} of {ok_flip+bad_flip:,} "
              f"({ok_flip/max(1,ok_flip+bad_flip):.4%}); "
              f"{nomatch:,} rows dropped for a gap in the index")

        # calibration of the shipped gaussian against realised flips
        print("\n  CALIBRATION of p_flip = Phi(-|required_move| / sd_pred)")
        print(f"  {'p_model bucket':>18} {'n':>7} {'mean p_model':>13}"
              f" {'realised':>10} {'ratio':>8} {'cents':>7}")
        cuts = [0, 1e-6, 1e-5, 1e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 1.01]
        buckets = [[0, 0.0, 0] for _ in cuts]
        rowsp = []
        for (iid, t, r, req, m, fl, s300, s30, s120, price, tau, sds) in dat:
            sd = s300 * sd_scale(r)
            p = phi(-abs(req) / sd) if sd > 0 else 0.5
            rowsp.append((p, fl, abs(req) / sd if sd > 0 else 0.0, r, sd,
                          price, tau, m, req, iid, t, sds))
            for i in range(len(cuts) - 1):
                if cuts[i] <= p < cuts[i + 1]:
                    buckets[i][0] += 1
                    buckets[i][1] += p
                    buckets[i][2] += 1 if fl else 0
                    break
        for i in range(len(cuts) - 1):
            b = buckets[i]
            if not b[0]:
                continue
            mp = b[1] / b[0]
            rr = b[2] / b[0]
            rat = (rr / mp) if mp > 0 else float("inf")
            print(f"  {cuts[i]:>8.0e}-{cuts[i+1]:<8.0e} {b[0]:>7,}"
                  f" {mp:>13.5%} {rr:>10.4%} {rat:>8.1f} {100*(rr-mp):>7.2f}")
        nn = len(rowsp)
        tp = sum(p for p, *_ in rowsp)
        tf = sum(1 for _, fl, *_ in rowsp if fl)
        print(f"\n    TOTAL: model expects {tp:.1f} flips in {nn:,} rows "
              f"({tp/nn:.4%}); realised {tf} ({tf/nn:.4%}); "
              f"ratio {tf/tp if tp else float('nan'):.1f}x")

        # ---- 5b. ESTIMATOR RACE ON THE REAL SETTLED OUTCOMES -------------
        hists = {r: cond.get(("hist", r)) for r in rs}
        print("\n  ESTIMATOR RACE ON REAL OUTCOMES -- p_flip = "
              "Phi(-|required_move| / sd_pred),")
        print("  scored against the settled flip.  'emp/sd300' keeps "
              "sigma_300 as the scale but")
        print("  replaces the gaussian with the measured |z| exceedance "
              "curve at the same z.")
        print("  'base rate' is no model at all -- the constant that any "
              "model has to beat.")
        print(f"  {'model':>10} {'n':>7} {'logloss':>9} {'Brier':>10}"
              f" {'E[flips]':>9} {'realised':>9}")
        base_rate = tf / nn if nn else 0.0
        for ei, (nm, kd, _) in enumerate(ESTS):
            if kd == "rm":
                continue
            n2 = 0
            ll = br = ep = 0.0
            hit = 0
            for d in dat:
                sd = d[11][ei]
                if not sd or sd <= 0:
                    continue
                pp = phi(-abs(d[3]) / sd)
                pp = min(max(pp, PCLAMP), 1.0 - PCLAMP)
                n2 += 1
                ep += pp
                fl = d[5]
                hit += 1 if fl else 0
                ll += -(math.log(pp) if fl else math.log(1.0 - pp))
                br += (pp - (1.0 if fl else 0.0)) ** 2
            if n2:
                print(f"  {nm:>10} {n2:>7,} {ll/n2:>9.5f} {br/n2:>10.7f}"
                      f" {ep:>9.1f} {hit:>9}")
        n2 = 0
        ll = br = ep = 0.0
        hit = 0
        for d in dat:
            sd = d[11][SHIPPED]
            if not sd or sd <= 0:
                continue
            r = d[2]
            h = hists.get(r) or hists.get(min(rs, key=lambda q: abs(q - r)))
            if not h:
                continue
            pp = hist_tail(h, abs(d[3]) / sd)
            if pp is None:
                continue
            pp = min(max(pp, PCLAMP), 1.0 - PCLAMP)
            n2 += 1
            ep += pp
            fl = d[5]
            hit += 1 if fl else 0
            ll += -(math.log(pp) if fl else math.log(1.0 - pp))
            br += (pp - (1.0 if fl else 0.0)) ** 2
        if n2:
            print(f"  {'emp/sd300':>10} {n2:>7,} {ll/n2:>9.5f} {br/n2:>10.7f}"
                  f" {ep:>9.1f} {hit:>9}")
        pc = max(base_rate, PCLAMP)
        llc = -(base_rate * math.log(pc) + (1 - base_rate) * math.log(1 - pc))
        print(f"  {'base rate':>10} {nn:>7,} {llc:>9.5f} "
              f"{base_rate*(1-base_rate):>10.7f} {base_rate*nn:>9.1f} {tf:>9}")

        # ---- 6. MONEY ---------------------------------------------------
        print("\n" + "=" * 78)
        print("6. MONEY -- threshold price is 1 - p_flip - margin, so a "
              "probability error")
        print("   of dp moves the threshold by 100*dp CENTS, one for one.")
        print("=" * 78)
        # (a) sigma scale error alone, using the measured pooled ratio
        kbias = math.sqrt(tot[1] / tot[0])       # pooled sd of z on the grid
        for kk, lab in ((kbias, f"measured pooled z sd {kbias:.3f}"),
                        (1.25, "the 25% sigma_stress the engine already applies"),
                        (2.0, "sigma doubled")):
            d = []
            for (p, fl, x, r, sd, price, tau, m, req, iid, t, sds) in rowsp:
                p2 = phi(-x / kk)
                d.append(abs(p2 - p) * 100.0)
            d.sort()
            print(f"\n  (a) SCALE ONLY -- sigma multiplied by {kk:.3f} "
                  f"({lab}):")
            print(f"      |delta threshold| cents: mean {sum(d)/len(d):.3f}"
                  f"  median {pct(d,.5):.3f}  p90 {pct(d,.9):.3f}"
                  f"  p99 {pct(d,.99):.3f}  max {d[-1]:.3f}")
        # (b) shape error: gaussian vs the empirical tail measured above
        d2 = []
        used = 0
        for (p, fl, x, r, sd, price, tau, m, req, iid, t, sds) in rowsp:
            h = hists.get(r) or hists.get(min(rs, key=lambda q: abs(q - r)))
            if not h:
                continue
            pe = hist_tail(h, x)
            if pe is None:
                continue
            d2.append(abs(pe - p) * 100.0)
            used += 1
        if d2:
            d2.sort()
            print(f"\n  (b) SHAPE -- gaussian p_flip vs the EMPIRICAL "
                  f"exceedance at the same z ({used:,} rows):")
            print(f"      |delta threshold| cents: mean {sum(d2)/len(d2):.3f}"
                  f"  median {pct(d2,.5):.3f}  p90 {pct(d2,.9):.3f}"
                  f"  p99 {pct(d2,.99):.3f}  max {d2[-1]:.3f}")
        # (c) total: model p vs realised rate in the bucket it landed in
        d3 = []
        for i in range(len(cuts) - 1):
            b = buckets[i]
            if b[0] < 30:
                continue
            mp = b[1] / b[0]
            rr = b[2] / b[0]
            d3.append((b[0], abs(rr - mp) * 100.0))
        if d3:
            tw = sum(w for w, _ in d3)
            print(f"\n  (c) TOTAL as calibrated -- weighted mean |realised - "
                  f"model| across buckets with n>=30: "
                  f"{sum(w*c for w, c in d3)/tw:.3f} cents")
        for at in ("SV", "CP", "SD2", "CD", "SBP", "CBP", "ew"):
            for nm in idxs:
                if hasattr(idxs[nm], at):
                    delattr(idxs[nm], at)
    print(f"\ntotal {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
