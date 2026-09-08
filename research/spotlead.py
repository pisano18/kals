#!/usr/bin/env python3
# VERSION: 2026-09-08-sl1
"""
spotlead.py -- does the CONSTITUENT spot market tell us what the settlement
index will print BEFORE Kalshi publishes it?

    python research/spotlead.py --selftest
    python research/spotlead.py --feeds C:\\kals\\feed_data \\
                               --data  C:\\kals\\kalshi_data \\
                               --out   C:\\kals\\fulltape

WHY THIS IS THE HIGHEST-VALUE UNTESTED QUESTION

Settlement is the mean of 60 one-second CF Benchmarks prints over
[close-60, close-1].  With `r` of those prints not yet published, the current
model treats them as a FORECAST: it assumes every unseen print equals the
current spot and puts a gaussian on a trailing-300s sigma around that.  If the
constituent books tell us where the index is going, those r prints stop being
a forecast and become partly a CALCULATION -- p_flip falls, the price we can
safely pay rises, and we can trade earlier where the book is deeper.

CF computes BRTI from the ORDER BOOKS of Coinbase, Kraken, Bitstamp and
Gemini.  crypto_feeds.py has been recording exactly those books since
2026-08-25, and emits `index_replica` once per second AT THE TOP OF SECOND --
a size-weighted consolidated mid, a first-order approximation of BRTI, not the
real methodology.  This file asks three questions in order, and the first one
can kill the other two.

1. TIMING.  Both the index print and the replica record carry a LOCAL receipt
   stamp written by `time.time()` on this one machine -- `_rx_ms` in
   kalshi_collector.py:326, `_rx` in crypto_feeds.py's index_replica().  Same
   clock, two processes, so the difference is a real arrival gap and not a
   clock skew.  If the replica does not arrive FIRST, the idea is dead for
   real-time use however good the statistics look.

2. PREDICTIVE POWER, against persistence.  The index is a near-random-walk, so
   index[t] is a strong forecast of index[t+k].  Beating it at ANY horizon is
   the finding.

   LEVEL versus CHANGE matters here.  The replica is a DIFFERENT estimator of
   the same price and carries a persistent offset (venue mix, size weighting),
   so its raw level is not a forecast of the index level.  It is rebased with
   a strictly causal trailing mean of the basis:

       e[t]    = replica[t] - index[t]
       ebar[t] = mean of e over [t-W, t-1]        (W = 300s, causal)

   and the four predictors of index[t+k] are

       P0  persistence   index[t]                  <- what the model does today
       P1  rebased level replica[t] - ebar[t]      <- beta = 1
       P2  fitted OOS    index[t] + b_k*(replica[t]-ebar[t]-index[t])
                         b_k fitted on the FIRST 60% of the tape by time and
                         applied to the last 40%.  P2 nests P0 at b_k = 0, so
                         P2 can only beat P0 if the basis genuinely carries
                         information.
       P3  DIAGNOSTIC, NOT TRADEABLE: index[t] + (replica[t+k] - replica[t]).
                         Uses the FUTURE replica.  It is the upper bound on
                         what a perfect real-time reading of these books could
                         buy, and it is reported only to bound the answer.

3. THE DECISIVE TEST.  For real settled markets, with r of the 60 settlement
   prints still unpublished, estimate their mean.  The model's estimate is
   "all r equal current spot" = index[t] with t = close-1-r.  The alternative
   is the rebased replica.  Errors are divided by the index's own causal
   trailing sigma so coins pool.  If that error falls, p_flip falls and the
   strategy changes character.  If it does not, it does not.

HONEST CAVEATS, STATED BEFORE THE NUMBERS
  * The replica is a size-weighted consolidated mid.  CF's real methodology is
    an exponentially weighted price-volume curve with order-size capping over
    full depth.  Right shape, different function.
  * Only top-of-book is recorded for most venues.
  * A negative arrival gap would be a plumbing fact, not prescience; a
    negative-lag predictive win would be a bug.  Both are reported, not hidden.
"""

import argparse
import glob
import gzip
import json
import math
import os
import random
import statistics
import sys
import time
import zlib
from array import array
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gzsalvage import iter_lines as salvage_lines          # noqa: E402

NAN = float("nan")


def new_arr(n):
    """A dense per-second float64 array prefilled with NaN.

    A Python list of n floats costs ~32 bytes an element once filled; at 1.2M
    seconds x 14 series that is over half a gigabyte, and the collector
    outranks this job.  array('d') is 8 bytes an element."""
    return array("d", [NAN]) * n

# Kalshi index id -> the asset key crypto_feeds.py writes into index_replica
REPLICA_ASSET = {
    "BRTI": "BTC",
    "ETHUSD_RTI": "ETH",
    "SOLUSD_RTI": "SOL",
    "XRPUSD_RTI": "XRP",
    "DOGEUSD_RTI": "DOGE",
    "BCHUSD_RTI": "BCH",
    "ADAUSD_RTI": "ADA",
}
INDEX_TO_SERIES = {
    "BRTI": "KXBTC15M", "ETHUSD_RTI": "KXETH15M", "SOLUSD_RTI": "KXSOL15M",
    "XRPUSD_RTI": "KXXRP15M", "DOGEUSD_RTI": "KXDOGE15M",
    "BNBUSD_RTI": "KXBNB15M", "BCHUSD_RTI": "KXBCH15M",
    "ZECUSD_RTI": "KXZEC15M", "HYPEUSD_RTI": "KXHYPE15M",
    "NEARUSD_RTI": "KXNEAR15M", "ADAUSD_RTI": "KXADA15M",
    "TONUSD_RTI": "KXTON15M",
}
ORDER = ["BRTI", "ETHUSD_RTI", "SOLUSD_RTI", "XRPUSD_RTI", "DOGEUSD_RTI",
         "BCHUSD_RTI", "ADAUSD_RTI"]

OFFSET_W = 300          # causal window for the replica/index basis mean
SIGMA_W = 300           # causal window for the index's own per-second sigma
MIN_OFFSET_PTS = 60     # refuse to rebase on fewer than this many basis obs
HORIZONS = list(range(1, 21))
R_VALUES = list(range(2, 20))
TRAIN_FRAC = 0.60


# ==========================================================================
# small numeric helpers -- each one is exercised by the self-test
# ==========================================================================
def pctiles(xs, ps=(0, 1, 5, 25, 50, 75, 95, 99, 100)):
    """Percentiles by nearest-rank on a sorted copy.  Returns a dict."""
    if not xs:
        return {}
    s = sorted(xs)
    n = len(s)
    out = {}
    for p in ps:
        i = int(round((p / 100.0) * (n - 1)))
        out[p] = s[max(0, min(n - 1, i))]
    return out


def hist_pctiles(counter, ps=(0, 1, 5, 25, 50, 75, 95, 99, 100)):
    """Percentiles from a {value: count} histogram, nearest-rank.

    The timing tests have millions of observations; keeping them as integer
    milliseconds in a Counter costs a few thousand keys instead of a few
    hundred megabytes."""
    if not counter:
        return {}
    total = sum(counter.values())
    keys = sorted(counter)
    out = {}
    targets = sorted((p, int(round((p / 100.0) * (total - 1)))) for p in ps)
    run = 0
    ti = 0
    for k in keys:
        run += counter[k]
        while ti < len(targets) and targets[ti][1] < run:
            out[targets[ti][0]] = k
            ti += 1
        if ti >= len(targets):
            break
    while ti < len(targets):
        out[targets[ti][0]] = keys[-1]
        ti += 1
    return out


def hist_total(counter):
    return sum(counter.values())


def hist_frac_gt(counter, x):
    t = hist_total(counter)
    if not t:
        return NAN
    return 100.0 * sum(c for k, c in counter.items() if k > x) / t


def causal_offset(index, replica, lo, hi, w=OFFSET_W, min_pts=MIN_OFFSET_PTS):
    """ebar[t] = mean of (replica - index) over [t-w, t-1], STRICTLY causal.

    Returns a list aligned with index/replica.  NaN where fewer than
    `min_pts` basis observations are available in the window."""
    n = len(index)
    ebar = new_arr(n)
    ssum = 0.0
    cnt = 0
    ring = []
    head = 0
    for t in range(lo, hi):
        # t's estimate uses only [t-w, t-1], so publish BEFORE adding t
        if cnt >= min_pts:
            ebar[t] = ssum / cnt
        a, b = index[t], replica[t]
        if a == a and b == b:
            ring.append((t, b - a))
            ssum += b - a
            cnt += 1
        while head < len(ring) and ring[head][0] <= t - w:
            ssum -= ring[head][1]
            cnt -= 1
            head += 1
        if head > 4096:
            del ring[:head]
            head = 0
    return ebar


def causal_mean(index, lo, hi, w=OFFSET_W, min_pts=MIN_OFFSET_PTS):
    """Trailing mean of the index itself over [t-w, t-1], strictly causal.

    This exists because of a trap.  The rebased replica is
    replica[t] - ebar[t], and ebar is a 300s mean of (replica - index), so

        replica[t] - ebar[t] - index[t-1]
            = (replica[t] - mean300(replica)) + (mean300(index) - index[t-1])

    The SECOND term is made of index history alone.  If the published index
    mean-reverts towards its own 300s average, that term predicts index[t] with
    no constituent data involved, and the whole result would be an artefact of
    the rebasing.  So mean300(index) - index[t-1] goes into the CONTROL, and
    the replica is only ever credited with what it adds on top."""
    n = len(index)
    out = new_arr(n)
    ssum = 0.0
    cnt = 0
    ring = []
    head = 0
    for t in range(lo, hi):
        if cnt >= min_pts:
            out[t] = ssum / cnt
        v = index[t]
        if v == v:
            ring.append((t, v))
            ssum += v
            cnt += 1
        while head < len(ring) and ring[head][0] <= t - w:
            ssum -= ring[head][1]
            cnt -= 1
            head += 1
        if head > 4096:
            del ring[:head]
            head = 0
    return out


def causal_sigma(index, lo, hi, w=SIGMA_W, min_pts=60):
    """sd of one-second index changes over the trailing w seconds, causal."""
    n = len(index)
    sig = new_arr(n)
    s1 = s2 = 0.0
    cnt = 0
    ring = []
    head = 0
    for t in range(lo, hi):
        if cnt >= min_pts:
            m = s1 / cnt
            v = s2 / cnt - m * m
            sig[t] = math.sqrt(v) if v > 0 else NAN
        a = index[t]
        b = index[t - 1] if t > 0 else NAN
        if a == a and b == b:
            d = a - b
            ring.append((t, d))
            s1 += d
            s2 += d * d
            cnt += 1
        while head < len(ring) and ring[head][0] <= t - w:
            d = ring[head][1]
            s1 -= d
            s2 -= d * d
            cnt -= 1
            head += 1
        if head > 4096:
            del ring[:head]
            head = 0
    return sig


def ols(xs, ys):
    """Slope and intercept of y on x.  Returns (b, a, n)."""
    n = len(xs)
    if n < 3:
        return NAN, NAN, n
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) * (x - mx) for x in xs)
    if sxx <= 0:
        return NAN, NAN, n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx
    return b, my - b * mx, n


def ols2(x1, x2, ys):
    """y = a + b1*x1 + b2*x2 by normal equations.  Returns (b1, b2, a, n)."""
    n = len(ys)
    if n < 10:
        return NAN, NAN, NAN, n
    m1 = sum(x1) / n
    m2 = sum(x2) / n
    my = sum(ys) / n
    s11 = s22 = s12 = s1y = s2y = 0.0
    for u, v, y in zip(x1, x2, ys):
        du, dv, dy = u - m1, v - m2, y - my
        s11 += du * du
        s22 += dv * dv
        s12 += du * dv
        s1y += du * dy
        s2y += dv * dy
    det = s11 * s22 - s12 * s12
    if det == 0 or s11 <= 0 or s22 <= 0:
        b, a, _ = ols(x1, ys)
        return b, 0.0, a, n
    b1 = (s22 * s1y - s12 * s2y) / det
    b2 = (s11 * s2y - s12 * s1y) / det
    return b1, b2, my - b1 * m1 - b2 * m2, n


class Normal:
    """Streaming least squares with an intercept, for a handful of regressors.

    It accumulates X'X and X'y as rows arrive, so a fit over a million seconds
    costs one small matrix rather than a million stored rows.  That is not
    tidiness: the collector outranks this job, and the list-of-rows version of
    the same fit peaked several hundred megabytes."""

    def __init__(self, k):
        self.k = k
        self.m = k + 1
        self.A = [[0.0] * (self.m + 1) for _ in range(self.m)]
        self.n = 0
        self.sy = 0.0

    def add(self, row, y):
        v = (1.0,) + tuple(row)
        m = self.m
        for i in range(m):
            vi = v[i]
            Ai = self.A[i]
            for j in range(m):
                Ai[j] += vi * v[j]
            Ai[m] += vi * y
        self.n += 1
        self.sy += y

    def solve(self):
        """[intercept, b1, ...] by Gaussian elimination with partial pivoting.

        Too few rows, or a singular system, falls back to the intercept alone
        -- which makes the fitted predictor collapse to the baseline rather
        than to something arbitrary."""
        m, k = self.m, self.k
        if self.n < 10 * m:
            return [0.0] * m
        A = [row[:] for row in self.A]
        for c in range(m):
            piv = max(range(c, m), key=lambda r: abs(A[r][c]))
            if abs(A[piv][c]) < 1e-12:
                return [self.sy / self.n] + [0.0] * k
            A[c], A[piv] = A[piv], A[c]
            pv = A[c][c]
            for j in range(c, m + 1):
                A[c][j] /= pv
            for r in range(m):
                if r == c:
                    continue
                f = A[r][c]
                if f:
                    for j in range(c, m + 1):
                        A[r][j] -= f * A[c][j]
        return [A[i][m] for i in range(m)]


def olsk(X, ys):
    """Least squares with an intercept over a list of rows.  Returns
    [intercept, b1, b2, ...].  Thin wrapper on Normal, kept because the
    self-test plants coefficients and reads them back this way."""
    if not ys:
        return [0.0]
    nrm = Normal(len(X[0]))
    for row, y in zip(X, ys):
        nrm.add(row, y)
    return nrm.solve()


def _fit1(n, sx, sy, sxx, sxy):
    """[a, b] minimising (a + b*x - y)^2 from cross-moments alone."""
    if n < 20:
        return [0.0, 0.0]
    den = n * sxx - sx * sx
    if den <= 0:
        return [sy / n, 0.0]
    b = (n * sxy - sx * sy) / den
    return [(sy - b * sx) / n, b]


def _fit2(n, sx, sd, sy, sxx, sdd, sxd, sxy, sdy):
    """[a, b1, b2] for y ~ a + b1*x + b2*d, from cross-moments alone."""
    if n < 30:
        return [0.0, 0.0, 0.0]
    cxx = sxx - sx * sx / n
    cdd = sdd - sd * sd / n
    cxd = sxd - sx * sd / n
    cxy = sxy - sx * sy / n
    cdy = sdy - sd * sy / n
    det = cxx * cdd - cxd * cxd
    if det == 0 or cxx <= 0 or cdd <= 0:
        c = _fit1(n, sx, sy, sxx, sxy)
        return [c[0], c[1], 0.0]
    b1 = (cdd * cxy - cxd * cdy) / det
    b2 = (cxx * cdy - cxd * cxy) / det
    return [(sy - b1 * sx - b2 * sd) / n, b1, b2]


def _sse1(c, n, sx, sy, sxx, sxy, syy):
    """Sum of (a + b*x - y)^2 over a set summarised by its moments."""
    a, b = c[0], c[1]
    return (n * a * a + b * b * sxx + syy
            + 2 * a * b * sx - 2 * a * sy - 2 * b * sxy)


def _sse2(c, n, sx, sd, sy, sxx, sdd, sxd, sxy, sdy, syy):
    """Sum of (a + b1*x + b2*d - y)^2 from moments."""
    a, b1, b2 = c[0], c[1], c[2]
    return (n * a * a + b1 * b1 * sxx + b2 * b2 * sdd + syy
            + 2 * a * b1 * sx + 2 * a * b2 * sd + 2 * b1 * b2 * sxd
            - 2 * a * sy - 2 * b1 * sxy - 2 * b2 * sdy)


def apply_ols(coef, row):
    v = coef[0]
    for c, x in zip(coef[1:], row):
        v += c * x
    return v


def rmse(errs):
    if not errs:
        return NAN
    return math.sqrt(sum(e * e for e in errs) / len(errs))


# ==========================================================================
# 1. TIMING
# ==========================================================================
def arrival_gaps(index_rx_ms, replica_rx_ms):
    """ms by which the replica for second s beat the index print for second s.

    index_rx_ms / replica_rx_ms are {sec: local receipt in ms}.  Positive means
    the replica was in hand first.  Both stamps come from time.time() on this
    one machine (kalshi_collector.py:326 and crypto_feeds.py index_replica),
    so the difference is arrival, not clock skew."""
    out = []
    for s, irx in index_rx_ms.items():
        rrx = replica_rx_ms.get(s)
        if rrx is None:
            continue
        out.append(irx - rrx)
    return out


# ==========================================================================
# 2. PREDICTIVE POWER
# ==========================================================================
def horizon_table(index, replica, ebar, lo, hi, horizons=HORIZONS,
                  train_frac=TRAIN_FRAC):
    """RMSE of P0/P1/P2/P3 for each k.  P2's beta is fitted on the first
    `train_frac` of the span BY TIME and scored on the rest; P0 and P1 are
    scored on that same test slice so the comparison is like for like."""
    split = lo + int((hi - lo) * train_frac)
    # usable t: everything the tradeable predictors need at decision time
    base = []
    for t in range(lo + 1, hi):
        a = index[t]
        b = replica[t]
        e = ebar[t]
        c = replica[t - 1]
        if a == a and b == b and e == e and c == c:
            base.append(t)
    out = {}
    for k in horizons:
        # ONE pass over the span.  Training rows go into scalar cross-moments;
        # test rows go into their OWN cross-moments, because for a linear
        # predictor the test sum of squared errors is an exact function of
        # those moments:
        #     SSE(a,b) = n*a^2 + b^2*Sxx + Syy + 2ab*Sx - 2a*Sy - 2b*Sxy
        # So the fitted predictors can be scored AFTER the pass without
        # storing a single row, and without a second sweep.  The earlier
        # matrix-accumulator version was correct and far too slow: 20 horizons
        # x 2 sweeps x 1.1M seconds.
        tn = txx = tdd = txd = txy = tdy = tx = td = ty = 0.0
        vn = vxx = vdd = vxd = vxy = vdy = vx = vd = vy = vyy = 0.0
        s0 = s1 = s3 = s03 = 0.0
        n3 = 0
        for t in base:
            u = t + k
            if u >= hi:
                continue
            fut = index[u]
            if fut != fut:
                continue
            ix = index[t]
            reb = replica[t] - ebar[t]
            x = reb - ix                      # the rebased basis
            d = replica[t] - replica[t - 1]   # the replica's own last move
            y = fut - ix                      # what we are trying to predict
            if t < split:
                tn += 1
                tx += x
                td += d
                ty += y
                txx += x * x
                tdd += d * d
                txd += x * d
                txy += x * y
                tdy += d * y
                continue
            vn += 1
            vx += x
            vd += d
            vy += y
            vxx += x * x
            vdd += d * d
            vxd += x * d
            vxy += x * y
            vdy += d * y
            vyy += y * y
            s0 += y * y                       # P0: predict zero change
            e = x - y
            s1 += e * e                       # P1: the rebased level itself
            rfu = replica[u]
            if rfu == rfu:
                e = (rfu - replica[t]) - y
                s3 += e * e
                s03 += y * y     # P0 on P3's own rows, so the two are
                n3 += 1          # compared on exactly the same seconds
        n_test = int(vn)
        if not n_test:
            out[k] = {"n_train": int(tn), "n_test": 0}
            continue
        c2 = _fit1(tn, tx, ty, txx, txy)
        c4 = _fit2(tn, tx, td, ty, txx, tdd, txd, txy, tdy)
        s2 = _sse1(c2, vn, vx, vy, vxx, vxy, vyy)
        s4 = _sse2(c4, vn, vx, vd, vy, vxx, vdd, vxd, vxy, vdy, vyy)
        out[k] = {
            "n_train": int(tn), "n_test": n_test, "n_all": int(tn) + n_test,
            "beta": c2[1], "alpha": c2[0], "beta_basis": c4[1],
            "beta_drep": c4[2],
            "rmse_p0": math.sqrt(s0 / n_test), "rmse_p1": math.sqrt(s1 / n_test),
            "rmse_p2": math.sqrt(max(s2, 0.0) / n_test),
            "rmse_p3": math.sqrt(s3 / n3) if n3 else NAN, "n_p3": n3,
            "rmse_p0_p3sub": math.sqrt(s03 / n3) if n3 else NAN,
            "rmse_p4": math.sqrt(max(s4, 0.0) / n_test),
        }
    return out


def nowcast_table(index, replica, ebar, lo, hi, train_frac=TRAIN_FRAC,
                  imean=None):
    """The sharpest form of the arrival-gap question.

    At wall clock T+5ms we hold replica[T].  Anyone reading the published feed
    holds only index[T-1] until T+~95ms.  So compare three estimators of
    index[T] itself:

        N0  index[t-1]                     the published feed, stale by 1s
        N1  replica[t] - ebar[t]           the rebased replica, in hand first
        N2  index[t-1] + b*(N1 - index[t-1])   best linear blend, fitted on the
                                           first `train_frac` of the span

    N2 beating N0 is NOT yet a finding about the spot feed.  If the published
    index has autocorrelated increments -- because it is itself a smoothed or
    lagged estimator -- then its OWN history predicts index[t] from index[t-1]
    and no constituent data is needed.  So the table also carries

        N3  index[t-1] + c1*d1 + c2*d2 + c3*m1   index-only CONTROL, where
                                           d1 = index[t-1]-index[t-2],
                                           d2 = index[t-2]-index[t-3] and
                                           m1 = mean300(index)-index[t-1],
                                           which is the half of the rebasing
                                           that is made of index history alone
        N4  N3 plus the replica basis      everything at once

    The number that credits the SPOT DATA is N4 against N3, not N2 against N0.
    Every coefficient is fitted on the first `train_frac` of the span by time
    and scored on the rest."""
    split = lo + int((hi - lo) * train_frac)
    # A None imean would make m1 identically zero, which makes the normal
    # equations singular and sends solve() to its intercept-only fallback --
    # silently discarding the REPLICA term as well.  Compute it instead.
    if imean is None:
        imean = causal_mean(index, lo, hi)

    def rows(a, b):
        """(basis, d1, d2, m1, prev, cur) for every second in [a, b) that has
        everything the three fits need."""
        for t in range(max(a, lo + 3), b):
            cur = index[t]
            prev = index[t - 1]
            p2 = index[t - 2]
            p3 = index[t - 3]
            rp = replica[t]
            eb = ebar[t]
            im = imean[t]
            if not (cur == cur and prev == prev and p2 == p2 and p3 == p3
                    and rp == rp and eb == eb and im == im):
                continue
            yield (rp - eb - prev, prev - p2, p2 - p3, im - prev, prev, cur)

    n2 = Normal(1)
    n3 = Normal(3)
    n4 = Normal(4)
    for bs, d1, d2, m1, prev, cur in rows(lo, split):
        y = cur - prev
        n2.add((bs,), y)
        n3.add((d1, d2, m1), y)
        n4.add((bs, d1, d2, m1), y)
    if n2.n < 100:
        return {"n_train": n2.n, "n_test": 0}
    c2, c3, c4 = n2.solve(), n3.solve(), n4.solve()
    s0 = s1 = s2 = s3 = s4 = 0.0
    cnt = 0
    for bs, d1, d2, m1, prev, cur in rows(split, hi):
        cnt += 1
        d = prev - cur
        s0 += d * d
        d = (bs + prev) - cur                      # the rebased replica level
        s1 += d * d
        d = prev + c2[0] + c2[1] * bs - cur
        s2 += d * d
        d = prev + c3[0] + c3[1] * d1 + c3[2] * d2 + c3[3] * m1 - cur
        s3 += d * d
        d = (prev + c4[0] + c4[1] * bs + c4[2] * d1 + c4[3] * d2
             + c4[4] * m1 - cur)
        s4 += d * d
    if not cnt:
        return {"n_train": n2.n, "n_test": 0}
    return {"n_train": n2.n, "n_test": cnt, "beta": c2[1],
            "coef2": c2, "coef3": c3, "coef4": c4,
            "rmse_n0": math.sqrt(s0 / cnt), "rmse_n1": math.sqrt(s1 / cnt),
            "rmse_n2": math.sqrt(s2 / cnt), "rmse_n3": math.sqrt(s3 / cnt),
            "rmse_n4": math.sqrt(s4 / cnt)}


# ==========================================================================
# 3. THE DECISIVE TEST -- the r unpublished settlement prints
# ==========================================================================
def settle_table(index, replica, ebar, sigma, closes, lo, hi,
                 rs=R_VALUES, train_frac=TRAIN_FRAC, rep_lead=0, imean=None):
    """For each r: RMSE of (true mean of the r unpublished prints - estimate),
    in units of the index's own causal trailing sigma.

    Settlement averages the prints at seconds [close-60, close-1].  With r
    unpublished, the last published second is t = close-1-r and the unknown is
    mean(index[close-r .. close-1]).

        model    : every unseen print equals index[t]  -> est = index[t]
        replica  : rebased replica level               -> est = replica[..]-ebar
        control  : index[t] + c1*d1 + c2*d2 + c3*m1, built from index history
                   ALONE -- its own momentum plus mean300(index)-index[t],
                   which is the half of the rebasing that contains no
                   constituent data.  A win for the replica has to be a win
                   over this.
        fitted   : the control plus b*basis, everything at once

    `rep_lead` is the point of the whole exercise.  With rep_lead=0 the replica
    is read at the same second t as the last published index print -- a
    like-for-like comparison that ignores the arrival gap.  With rep_lead=1 the
    replica is read at t+1, which is what we ACTUALLY hold in real time: at
    wall clock (t+1)+5ms the replica for second t+1 exists while index[t+1] is
    still ~90ms away, so index[t] is the freshest published print.  rep_lead=1
    is the honest real-time construction and it is the one that decides this.

    Coefficients are fitted on the first `train_frac` of CLOSES by time and
    scored on the rest."""
    if imean is None:                  # see the note in nowcast_table
        imean = causal_mean(index, lo, hi)
    closes = sorted(closes)
    if not closes:
        return {}
    split_t = (closes[int(len(closes) * train_frac)] if len(closes) > 4
               else closes[-1])
    out = {}
    for r in rs:
        trX, trY = [], []
        rows = []
        for c in closes:
            t = c - 1 - r
            tr = t + rep_lead
            # tr can sit before lo for the stale placebo; a negative index
            # would wrap round the array and silently read the far end of the
            # tape, which is exactly the kind of bug this file exists to avoid
            if t < lo + 3 or c > hi or tr >= hi or tr < lo:
                continue
            ix = index[t]
            d1 = ix - index[t - 1] if index[t - 1] == index[t - 1] else NAN
            d2 = (index[t - 1] - index[t - 2]
                  if index[t - 2] == index[t - 2] else NAN)
            m1 = imean[t] - ix
            rp = replica[tr]
            eb = ebar[tr]
            sg = sigma[t]
            if not (ix == ix and rp == rp and eb == eb and sg == sg and sg > 0
                    and d1 == d1 and d2 == d2 and m1 == m1):
                continue
            tot = 0.0
            ok = True
            for s in range(c - r, c):
                v = index[s]
                if v != v:
                    ok = False
                    break
                tot += v
            if not ok:
                continue
            true = tot / r
            row = (((rp - eb) - ix) / sg, d1 / sg, d2 / sg, m1 / sg)
            y = (true - ix) / sg
            if c < split_t:
                trX.append(row)
                trY.append(y)
            else:
                rows.append((row, y))
        if len(trY) < 30 or not rows:
            out[r] = {"n_train": len(trY), "n_test": 0}
            continue
        cR = olsk([[q[0]] for q in trX], trY)              # replica only
        cC = olsk([[q[1], q[2], q[3]] for q in trX], trY)  # index history only
        cF = olsk([list(q) for q in trX], trY)             # both
        e_model = [y for (_, y) in rows]                   # est = index[t]
        e_rep = [(q[0] - y) for (q, y) in rows]            # est = rebased level
        e_fitR = [(apply_ols(cR, (q[0],)) - y) for (q, y) in rows]
        e_ctrl = [(apply_ols(cC, (q[1], q[2], q[3])) - y) for (q, y) in rows]
        e_fit = [(apply_ols(cF, q) - y) for (q, y) in rows]
        # RMSE on ~400 closes is dominated by its worst few: this tape's
        # index moves reach tens of sigma, so a single event entering the
        # window at one r can double an RMSE with nothing wrong.  The median
        # absolute error is carried alongside so that a jump in the RMSE
        # column can be told apart from a jump in the underlying error.
        amed = sorted(abs(x) for x in e_model)
        fmed = sorted(abs(x) for x in e_fit)
        # Significance at the CLUSTER unit this repo insists on: one
        # observation per CLOSE, paired, on squared error.  A positive t means
        # the fitted estimate beat the control on the same closes.
        dif = [(c * c - f * f) for c, f in zip(e_ctrl, e_fit)]
        dm = sum(dif) / len(dif)
        dv = sum((x - dm) ** 2 for x in dif) / max(len(dif) - 1, 1)
        tstat = dm / math.sqrt(dv / len(dif)) if dv > 0 else 0.0
        difm = [(a * a - f * f) for a, f in zip(e_model, e_fit)]
        dmm = sum(difm) / len(difm)
        dvm = sum((x - dmm) ** 2 for x in difm) / max(len(difm) - 1, 1)
        tstatm = dmm / math.sqrt(dvm / len(difm)) if dvm > 0 else 0.0
        out[r] = {
            "n_train": len(trY), "n_test": len(rows), "beta": cF[1],
            "beta_rep_only": cR[1], "coef": cF,
            "rmse_model": rmse(e_model), "rmse_replica": rmse(e_rep),
            "rmse_reponly": rmse(e_fitR), "rmse_control": rmse(e_ctrl),
            "rmse_fitted": rmse(e_fit),
            "mae_model": amed[len(amed) // 2], "mae_fitted": fmed[len(fmed) // 2],
            "max_model": amed[-1], "t_vs_ctrl": tstat, "t_vs_model": tstatm,
        }
    return out


# ==========================================================================
# LOADING
# ==========================================================================
def hour_stems(*dirs):
    stems = set()
    for d in dirs:
        for fp in glob.glob(os.path.join(d, "*.jsonl.gz")):
            stems.add(os.path.basename(fp).split(".")[0])
    return sorted(stems)


def stem_epoch(stem):
    """"20260908T10" -> epoch seconds of that UTC hour."""
    import calendar
    y, mo, d = int(stem[0:4]), int(stem[4:6]), int(stem[6:8])
    h = int(stem[9:11])
    return calendar.timegm((y, mo, d, h, 0, 0, 0, 0, 0))


def read_hour(path):
    try:
        for line in salvage_lines(path):
            try:
                yield json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
    except (OSError, EOFError, zlib.error, gzip.BadGzipFile):
        return


def load(feeds_dir, data_dir, hours=None, verbose=True):
    """Stream one hour at a time.  Returns per-second arrays keyed by index."""
    rep_dir = os.path.join(feeds_dir, "index_replica")
    idx_dir = os.path.join(data_dir, "cfbenchmarks_value")
    stems = hour_stems(rep_dir, idx_dir)
    if hours:
        stems = stems[-hours:]
    if not stems:
        print("  no cfbenchmarks_value and no index_replica hours on disk. "
              "nothing to analyse.")
        return None
    t0 = stem_epoch(stems[0])
    t1 = stem_epoch(stems[-1]) + 3600
    n = t1 - t0 + 2
    if verbose:
        print(f"  {len(stems)} hour files, {stems[0]} .. {stems[-1]}, "
              f"{n:,} seconds of span")

    index = {iid: new_arr(n) for iid in REPLICA_ASSET}
    replica = {iid: new_arr(n) for iid in REPLICA_ASSET}
    # millions of observations each -> integer-millisecond histograms, not lists
    gaps = defaultdict(Counter)
    cf_lat = Counter()   # index print time -> our receipt, ms
    rep_lat = Counter()  # replica top-of-second -> its own stamp, ms
    nex = defaultdict(Counter)
    idx_secs = defaultdict(int)
    rep_secs = defaultdict(int)
    other_idx = defaultdict(int)

    for stem in stems:
        rrx = {}          # asset -> {sec: rx_ms}
        for m in read_hour(os.path.join(rep_dir, stem + ".jsonl.gz")):
            sec = m.get("sec")
            rx = m.get("_rx")
            if sec is None or rx is None:
                continue
            sec = int(sec)
            i = sec - t0
            if not (0 <= i < n):
                continue
            rep_lat[int(round((float(rx) - sec) * 1000.0))] += 1
            for iid, asset in REPLICA_ASSET.items():
                d = m.get(asset)
                if not isinstance(d, dict):
                    continue
                v = d.get("wmid")
                if v is None:
                    continue
                try:
                    replica[iid][i] = float(v)
                except (TypeError, ValueError):
                    continue
                rep_secs[iid] += 1
                nex[iid][int(d.get("n_ex", 0))] += 1
                rrx.setdefault(asset, {})[sec] = float(rx) * 1000.0

        for m in read_hour(os.path.join(idx_dir, stem + ".jsonl.gz")):
            msg = m.get("msg") or {}
            iid = msg.get("index_id")
            if iid is None:
                continue
            if iid not in REPLICA_ASSET:
                other_idx[iid] += 1
                continue
            raw = msg.get("data")
            try:
                d = json.loads(raw) if isinstance(raw, str) else (raw or {})
                tms = int(d["time"])
                val = float(d["value"])
            except (TypeError, ValueError, KeyError):
                continue
            sec = tms // 1000
            i = sec - t0
            if not (0 <= i < n):
                continue
            index[iid][i] = val
            idx_secs[iid] += 1
            rx_ms = m.get("_rx_ms")
            if rx_ms is None:
                continue
            cf_lat[int(round(float(rx_ms) - tms))] += 1
            r = rrx.get(REPLICA_ASSET[iid], {}).get(sec)
            if r is not None:
                gaps[iid][int(round(float(rx_ms) - r))] += 1

    return {
        "t0": t0, "n": n, "index": index, "replica": replica, "gaps": gaps,
        "cf_lat": cf_lat, "rep_lat": rep_lat, "nex": nex,
        "idx_secs": idx_secs, "rep_secs": rep_secs, "other_idx": other_idx,
        "stems": stems,
    }


def load_closes(out_dir):
    p = os.path.join(out_dir, "markets.json")
    try:
        with open(p, encoding="utf-8") as f:
            mk = json.load(f)
    except (OSError, ValueError):
        return {}
    ser_to_idx = {v: k for k, v in INDEX_TO_SERIES.items()}
    out = defaultdict(set)
    for series, rows in mk.items():
        iid = ser_to_idx.get(series)
        if iid is None:
            continue
        for r in rows:
            c = r.get("close")
            if c:
                out[iid].add(int(c))
    return {k: sorted(v) for k, v in out.items()}


# ==========================================================================
# SELF-TEST
# ==========================================================================
def _world(n, lead, idx_noise, rep_noise, seed, rep_independent=False):
    """A latent price p.  index[t] = p[t-lead] (+noise); the replica reads the
    latent price with no lag, so it LEADS the index by `lead` seconds, and it
    carries a fixed +1000 offset plus its own noise."""
    rnd = random.Random(seed)
    p = [0.0] * (n + 64)
    for t in range(1, len(p)):
        p[t] = p[t - 1] + rnd.gauss(0, 5.0)
    q = [0.0] * (n + 64)
    for t in range(1, len(q)):
        q[t] = q[t - 1] + rnd.gauss(0, 5.0)
    index = [NAN] * n
    replica = [NAN] * n
    for t in range(64, n):
        index[t] = p[t - lead] + (rnd.gauss(0, idx_noise) if idx_noise else 0.0)
        src = q[t] if rep_independent else p[t]
        replica[t] = src + 1000.0 + (rnd.gauss(0, rep_noise) if rep_noise
                                     else 0.0)
    return index, replica


def selftest():
    print("=" * 78)
    print("SELF-TEST -- plant a lead, then plant nothing")
    print("=" * 78)
    fails = []

    # ---- 1. timing ------------------------------------------------------
    irx = {s: s * 1000 + 80 for s in range(1000, 3000)}
    rrx = {s: s * 1000 + 5 for s in range(1000, 3000)}
    pc = pctiles(arrival_gaps(irx, rrx))
    print(f"\n  [timing] planted a 75ms replica lead -> median {pc[50]:.1f} ms, "
          f"min {pc[0]:.1f}, max {pc[100]:.1f}")
    if abs(pc[50] - 75.0) > 1e-6:
        fails.append(f"arrival_gaps median {pc[50]} != 75")
    g2 = arrival_gaps({s: s * 1000 for s in range(1000, 3000)},
                      {s: s * 1000 + 40 for s in range(1000, 3000)})
    if abs(pctiles(g2)[50] + 40.0) > 1e-6:
        fails.append("arrival_gaps did not report a NEGATIVE gap as negative")
    else:
        print("  [timing] and a planted 40ms replica LAG reports as -40.0 ms")

    # the real run reads its percentiles off a histogram, so test that too
    rnd = random.Random(3)
    sample = [int(rnd.gauss(70, 30)) for _ in range(20000)]
    h = Counter(sample)
    pl, ph = pctiles(sample), hist_pctiles(h)
    bad = [p for p in pl if pl[p] != ph[p]]
    if bad:
        fails.append(f"hist_pctiles disagrees with pctiles at {bad}")
    else:
        print(f"  [timing] hist_pctiles == pctiles on 20,000 draws "
              f"(median {ph[50]}, p1 {ph[1]}, p99 {ph[99]})")
    fg = hist_frac_gt(h, 0)
    fl = 100.0 * sum(1 for x in sample if x > 0) / len(sample)
    if abs(fg - fl) > 1e-9:
        fails.append("hist_frac_gt disagrees with the direct count")

    # ---- 2. the rebasing is causal --------------------------------------
    idx = [float(t) for t in range(1000)]
    rep = [float(t) + 7.0 for t in range(1000)]
    eb = causal_offset(idx, rep, 0, 1000, w=100, min_pts=10)
    if any(e == e and abs(e - 7.0) > 1e-9 for e in eb):
        fails.append("causal_offset did not recover a constant +7 basis")
    if eb[5] == eb[5]:
        fails.append("causal_offset published a value before min_pts")
    rep2 = [float(t) + (7.0 if t < 500 else 107.0) for t in range(1000)]
    eb2 = causal_offset(idx, rep2, 0, 1000, w=100, min_pts=10)
    if abs(eb2[500] - 7.0) > 1e-9:
        fails.append(f"causal_offset leaked the future: ebar[500]={eb2[500]}")
    else:
        print("  [causal] at the second the basis jumps by +100, ebar still "
              "reads the OLD basis -- no look-ahead")

    # ---- 2b. the two-regressor fit recovers planted coefficients --------
    rnd2 = random.Random(5)
    x1 = [rnd2.gauss(0, 1) for _ in range(4000)]
    x2 = [rnd2.gauss(0, 1) for _ in range(4000)]
    yy = [2.0 * u + 3.0 * v + 1.5 + rnd2.gauss(0, 0.01)
          for u, v in zip(x1, x2)]
    b1, b2, aa, _ = ols2(x1, x2, yy)
    print(f"  [ols2] planted y = 1.5 + 2*x1 + 3*x2 -> recovered "
          f"a={aa:.3f} b1={b1:.3f} b2={b2:.3f}")
    if abs(b1 - 2) > 0.01 or abs(b2 - 3) > 0.01 or abs(aa - 1.5) > 0.01:
        fails.append("ols2 did not recover its planted coefficients")

    # the horizon table scores its fitted predictors from cross-moments
    # instead of stored rows.  That is an algebraic identity, so it must agree
    # with the direct sum to floating-point noise -- and if it ever does not,
    # every fitted RMSE in this file is wrong.
    n = float(len(yy))
    sx = sum(x1)
    sd = sum(x2)
    sy = sum(yy)
    sxx = sum(u * u for u in x1)
    sdd = sum(v * v for v in x2)
    sxd = sum(u * v for u, v in zip(x1, x2))
    sxy = sum(u * y for u, y in zip(x1, yy))
    sdy = sum(v * y for v, y in zip(x2, yy))
    syy = sum(y * y for y in yy)
    c1 = _fit1(n, sx, sy, sxx, sxy)
    c2f = _fit2(n, sx, sd, sy, sxx, sdd, sxd, sxy, sdy)
    if abs(c2f[1] - 2) > 0.01 or abs(c2f[2] - 3) > 0.01:
        fails.append("_fit2 did not recover the planted coefficients")
    direct1 = sum((c1[0] + c1[1] * u - y) ** 2 for u, y in zip(x1, yy))
    direct2 = sum((c2f[0] + c2f[1] * u + c2f[2] * v - y) ** 2
                  for u, v, y in zip(x1, x2, yy))
    m1 = _sse1(c1, n, sx, sy, sxx, sxy, syy)
    m2 = _sse2(c2f, n, sx, sd, sy, sxx, sdd, sxd, sxy, sdy, syy)
    r1 = abs(m1 - direct1) / max(direct1, 1e-12)
    r2 = abs(m2 - direct2) / max(direct2, 1e-12)
    print(f"  [moments] SSE from cross-moments vs the direct sum: "
          f"1 regressor rel.err {r1:.2e}, 2 regressors {r2:.2e}")
    if r1 > 1e-6 or r2 > 1e-6:
        fails.append(f"moment SSE disagrees with the direct sum "
                     f"({r1:.2e}, {r2:.2e}) -- every fitted RMSE is suspect")

    # ---- 3. planted lead of 2 seconds -----------------------------------
    N = 30000
    index, replica = _world(N, lead=2, idx_noise=0.0, rep_noise=0.5, seed=7)
    eb = causal_offset(index, replica, 0, N)
    tab = horizon_table(index, replica, eb, 64, N, horizons=[1, 2, 3, 5, 10])
    print("\n  [predictive] planted: the replica LEADS the index by 2s")
    print("     k   rmse P0(persist)   rmse P2(fitted)    improve%   beta")
    for k in (1, 2, 3, 5, 10):
        d = tab[k]
        imp = 100.0 * (d["rmse_p0"] - d["rmse_p2"]) / d["rmse_p0"]
        print(f"    {k:2d}   {d['rmse_p0']:14.3f}   {d['rmse_p2']:14.3f}   "
              f"{imp:8.2f}   {d['beta']:6.3f}")
        if k <= 2 and imp < 20.0:
            fails.append(f"planted lead missed at k={k}: improvement {imp:.1f}%")

    # ---- 3b. the nowcast test, on a replica that is simply CLEANER ------
    ni, nr = _world(N, lead=0, idx_noise=0.0, rep_noise=0.5, seed=23)
    neb = causal_offset(ni, nr, 0, N)
    nw = nowcast_table(ni, nr, neb, 64, N, imean=causal_mean(ni, 0, N))
    imp = 100.0 * (nw["rmse_n0"] - nw["rmse_n1"]) / nw["rmse_n0"]
    print("\n  [nowcast] planted: the replica reads THIS second with sd 0.5 "
          "while the\n            index moves sd 5.0 a second -> "
          f"N0 {nw['rmse_n0']:.3f}, N1 {nw['rmse_n1']:.3f}, "
          f"improve {imp:.1f}%")
    if imp < 50.0:
        fails.append(f"nowcast missed a clean planted replica: {imp:.1f}%")

    # ---- 4. the settlement estimator, same planted world ----------------
    closes = list(range(1200, N - 100, 120))
    sg = causal_sigma(index, 0, N)
    st = settle_table(index, replica, eb, sg, closes, 64, N, rs=[2, 5, 10, 19])
    print("\n  [settlement] planted world, error in sigma units")
    print("      r     n   model   replica   fitted   improve%")
    for r in (2, 5, 10, 19):
        d = st[r]
        imp = 100.0 * (d["rmse_model"] - d["rmse_fitted"]) / d["rmse_model"]
        print(f"    {r:3d} {d['n_test']:5d}  {d['rmse_model']:6.3f}  "
              f"{d['rmse_replica']:7.3f}  {d['rmse_fitted']:6.3f}  {imp:8.2f}")
        if r <= 5 and imp < 10.0:
            fails.append(f"planted settlement lead missed at r={r}: {imp:.1f}%")
    st1 = settle_table(index, replica, eb, sg, closes, 64, N, rs=[2, 5],
                       rep_lead=1)
    stp = settle_table(index, replica, eb, sg, closes, 64, N, rs=[2, 5],
                       rep_lead=-60)
    for r in (2, 5):
        d = st1[r]
        imp = 100.0 * (d["rmse_model"] - d["rmse_fitted"]) / d["rmse_model"]
        dp = stp[r]
        impp = (100.0 * (dp["rmse_control"] - dp["rmse_fitted"])
                / dp["rmse_control"]) if dp["n_test"] else 0.0
        print(f"    rep_lead=1 r={r}: n {d['n_test']}, improve {imp:6.2f}%"
              f"   |  PLACEBO rep_lead=-60: n {dp['n_test']}, "
              f"fit-ctrl {impp:+6.2f}%")
        if imp < 10.0:
            fails.append(f"rep_lead=1 missed the planted lead at r={r}: "
                         f"{imp:.1f}%")
        if impp > 5.0:
            fails.append(f"the stale placebo found {impp:.1f}% at r={r} in a "
                         f"world where a minute-old replica knows nothing")

    # ---- 5. NOTHING planted: the index IS the latent price ---------------
    index, replica = _world(N, lead=0, idx_noise=0.0, rep_noise=5.0, seed=11)
    eb = causal_offset(index, replica, 0, N)
    tab = horizon_table(index, replica, eb, 64, N, horizons=[1, 2, 5, 10])
    print("\n  [null A] index IS the latent price; replica is a noisy copy "
          "with an offset")
    print("     k   improve% (P2 fitted)     beta")
    worst = 0.0
    for k in (1, 2, 5, 10):
        d = tab[k]
        imp = 100.0 * (d["rmse_p0"] - d["rmse_p2"]) / d["rmse_p0"]
        worst = max(worst, imp)
        print(f"    {k:2d}   {imp:18.3f}   {d['beta']:6.3f}")
    if worst > 1.0:
        fails.append(f"null A: claimed {worst:.2f}% improvement from nothing")

    # ---- 6. NOTHING planted, harder: an UNRELATED walk -------------------
    index, replica = _world(N, lead=0, idx_noise=0.0, rep_noise=0.5, seed=13,
                            rep_independent=True)
    eb = causal_offset(index, replica, 0, N)
    tab = horizon_table(index, replica, eb, 64, N, horizons=[1, 2, 5])
    sg = causal_sigma(index, 0, N)
    st = settle_table(index, replica, eb, sg, closes, 64, N, rs=[2, 10])
    nw = nowcast_table(index, replica, eb, 64, N,
                       imean=causal_mean(index, 0, N))
    nimp = 100.0 * (nw["rmse_n0"] - nw["rmse_n2"]) / nw["rmse_n0"]
    print("\n  [null B] replica tracks an UNRELATED random walk")
    print(f"    nowcast N2 improve% {nimp:8.3f}   beta {nw['beta']:7.4f}")
    if nimp > 1.0:
        fails.append(f"null B: nowcast claimed {nimp:.2f}% from noise")
    worstb = 0.0
    for k in (1, 2, 5):
        d = tab[k]
        imp = 100.0 * (d["rmse_p0"] - d["rmse_p2"]) / d["rmse_p0"]
        worstb = max(worstb, imp)
        print(f"    k={k:2d}  improve% {imp:8.3f}   beta {d['beta']:7.4f}")
    st1 = settle_table(index, replica, eb, sg, closes, 64, N, rs=[2, 10],
                       rep_lead=1)
    for r in (2, 10):
        d = st[r]
        imp = 100.0 * (d["rmse_model"] - d["rmse_fitted"]) / d["rmse_model"]
        worstb = max(worstb, imp)
        d1 = st1[r]
        imp1 = 100.0 * (d1["rmse_model"] - d1["rmse_fitted"]) / d1["rmse_model"]
        worstb = max(worstb, imp1)
        print(f"    r={r:2d}  improve% {imp:8.3f}   beta {d['beta']:7.4f}"
              f"   (rep_lead=1: {imp1:7.3f}%)")
    # the horizon rows have ~400,000 test points and sit within 0.01%; the
    # settlement rows have only 96 test closes here, so their noise floor is a
    # couple of percent.  The real run has thousands of closes per coin.
    if worstb > 3.0:
        fails.append(f"null B: claimed {worstb:.2f}% improvement from noise")

    # ---- 7. P1 (beta=1) must LOSE when the replica is noisy and no lead --
    index, replica = _world(N, lead=0, idx_noise=0.0, rep_noise=5.0, seed=17)
    eb = causal_offset(index, replica, 0, N)
    d = horizon_table(index, replica, eb, 64, N, horizons=[1])[1]
    print(f"\n  [null C] beta=1 rebased replica with no lead: "
          f"P0 {d['rmse_p0']:.3f} vs P1 {d['rmse_p1']:.3f}")
    if d["rmse_p1"] <= d["rmse_p0"]:
        fails.append("P1 beat persistence in a world with no lead")

    # ---- 8. NULL D -- the trap the nowcast test could fall into ----------
    # A published index that is SMOOTHED has autocorrelated increments, so
    # index[t-1] alone underrates what its own history implies.  Here the
    # index is exactly that and the replica is unrelated noise: the
    # index-only control N3 must find a large effect (or the control has no
    # power and the whole comparison is uninterpretable), and the replica
    # must add nothing on top of it.
    rnd = random.Random(29)
    idxd = [NAN] * N
    repd = [NAN] * N
    idxd[0], idxd[1] = 0.0, 0.0
    w = 0.0
    for t in range(2, N):
        step = 0.6 * (idxd[t - 1] - idxd[t - 2]) + rnd.gauss(0, 4.0)
        idxd[t] = idxd[t - 1] + step
        w += rnd.gauss(0, 5.0)
        repd[t] = w + 1000.0
    ebd = causal_offset(idxd, repd, 0, N)
    nd = nowcast_table(idxd, repd, ebd, 64, N, imean=causal_mean(idxd, 0, N))
    r0 = nd["rmse_n0"]
    i2 = 100.0 * (r0 - nd["rmse_n2"]) / r0
    i3 = 100.0 * (r0 - nd["rmse_n3"]) / r0
    marg = 100.0 * (nd["rmse_n3"] - nd["rmse_n4"]) / nd["rmse_n3"]
    print("\n  [null D] the index's OWN increments are autocorrelated "
          "(phi=0.6) and\n           the replica is an unrelated walk")
    print(f"    N2 (replica only) improve% {i2:8.3f}")
    print(f"    N3 (index-only control)    {i3:8.3f}   <- must be LARGE or "
          f"the control has no power")
    print(f"    N4 vs N3 (replica's margin){marg:8.3f}   <- must be ~0")
    if i3 < 10.0:
        fails.append(f"null D: the index-only control found only {i3:.2f}% in "
                     f"a world built to be predictable from its own past -- "
                     f"the control is not capable and proves nothing")
    if marg > 1.0:
        fails.append(f"null D: the replica claimed {marg:.2f}% over the "
                     f"control while being unrelated noise")

    # ---- 9. NULL E -- the trap the REBASING itself could spring ---------
    # replica[t]-ebar[t]-index[t-1] contains (mean300(index) - index[t-1]).
    # If the published index mean-reverts towards its own 300s average, that
    # term forecasts index[t] using no constituent data at all, and the
    # nowcast result would be an artefact of how the replica is rebased.
    # Here the index does exactly that and the replica is an unrelated walk.
    rnd = random.Random(31)
    M = 40000
    ix = [NAN] * M
    rp = [NAN] * M
    ix[0] = 0.0
    w = 0.0
    run = 0.0
    for t in range(1, M):
        lo_i = max(0, t - 300)
        mu = sum(ix[lo_i:t]) / (t - lo_i)
        # a STRONG pull, so the control has real power to find; a weak one
        # would pass the null for the wrong reason
        ix[t] = ix[t - 1] + 0.8 * (mu - ix[t - 1]) + rnd.gauss(0, 1.0)
        w += rnd.gauss(0, 5.0)
        rp[t] = w + 1000.0
    ix[0] = NAN
    ebe = causal_offset(ix, rp, 0, M)
    ne = nowcast_table(ix, rp, ebe, 64, M, imean=causal_mean(ix, 0, M))
    r0 = ne["rmse_n0"]
    e2 = 100.0 * (r0 - ne["rmse_n2"]) / r0
    e3 = 100.0 * (r0 - ne["rmse_n3"]) / r0
    emarg = 100.0 * (ne["rmse_n3"] - ne["rmse_n4"]) / ne["rmse_n3"]
    print("\n  [null E] the index MEAN-REVERTS to its own 300s average and "
          "the\n           replica is unrelated -- the rebasing trap")
    print(f"    N2 (rebased replica alone)  {e2:8.3f}   <- the trap: pure "
          f"index information\n                                            "
          f"leaking through the rebasing")
    print(f"    N3 (index-only control)     {e3:8.3f}   <- must be LARGE")
    print(f"    N4 vs N3 (replica's margin) {emarg:8.3f}   <- must be ~0")
    if e3 < 5.0:
        fails.append(f"null E: the index-only control found only {e3:.2f}% "
                     f"where the index reverts to its own mean -- the control "
                     f"cannot see the trap it exists to catch")
    if emarg > 1.0:
        fails.append(f"null E: the replica claimed {emarg:.2f}% over the "
                     f"control while being unrelated noise -- the rebasing is "
                     f"leaking index information into the replica term")

    print()
    if fails:
        print("SELF-TEST FAILED")
        for f in fails:
            print("  *", f)
        return 1
    print("SELF-TEST PASSED -- the estimator recovers a planted 2s lead in "
          "both the\nhorizon table and the settlement table, and finds nothing "
          "in three worlds\nwith nothing planted.")
    return 0


# ==========================================================================
# VARIANTS -- is a negative an artefact of the replica FORMULA?
# ==========================================================================
VENUES = ["coinbase", "kraken", "bitstamp", "gemini"]


def load_variants(feeds_dir, data_dir, iid="BRTI", hours=None, verbose=True):
    """Same tape, but keep every reading the replica record carries for ONE
    index: wmid, median_mid, and each venue's own mid.

    crypto_feeds.py weights each venue by min(bid_size, ask_size), which is a
    crude proxy for depth, and it keeps a venue for 10 seconds after its last
    update.  If the consolidated number is noisy for those reasons, a negative
    result would be about the FORMULA and not about the constituent books.
    This measures the alternatives on the same seconds."""
    asset = REPLICA_ASSET[iid]
    rep_dir = os.path.join(feeds_dir, "index_replica")
    idx_dir = os.path.join(data_dir, "cfbenchmarks_value")
    stems = hour_stems(rep_dir, idx_dir)
    if hours:
        stems = stems[-hours:]
    if not stems:
        return None
    t0 = stem_epoch(stems[0])
    n = stem_epoch(stems[-1]) + 3600 - t0 + 2
    names = ["wmid", "median_mid"] + VENUES + ["med3_no_gemini"]
    var = {k: new_arr(n) for k in names}
    index = new_arr(n)
    present = Counter()
    for stem in stems:
        for m in read_hour(os.path.join(rep_dir, stem + ".jsonl.gz")):
            sec, d = m.get("sec"), m.get(asset)
            if sec is None or not isinstance(d, dict):
                continue
            i = int(sec) - t0
            if not (0 <= i < n):
                continue
            if d.get("wmid") is not None:
                var["wmid"][i] = float(d["wmid"])
            if d.get("median_mid") is not None:
                var["median_mid"][i] = float(d["median_mid"])
            pe = d.get("per_ex") or {}
            mids = {}
            for ex, bk in pe.items():
                try:
                    mids[ex] = (float(bk["b"]) + float(bk["a"])) / 2.0
                except (TypeError, ValueError, KeyError):
                    continue
            for ex in VENUES:
                if ex in mids:
                    var[ex][i] = mids[ex]
                    present[ex] += 1
            three = sorted(mids[e] for e in ("coinbase", "kraken", "bitstamp")
                           if e in mids)
            if len(three) == 3:
                var["med3_no_gemini"][i] = three[1]
        for m in read_hour(os.path.join(idx_dir, stem + ".jsonl.gz")):
            msg = m.get("msg") or {}
            if msg.get("index_id") != iid:
                continue
            raw = msg.get("data")
            try:
                dd = json.loads(raw) if isinstance(raw, str) else (raw or {})
                i = int(dd["time"]) // 1000 - t0
                v = float(dd["value"])
            except (TypeError, ValueError, KeyError):
                continue
            if 0 <= i < n:
                index[i] = v
    if verbose:
        print("  venue seconds present: " + ", ".join(
            f"{k}={present[k]:,}" for k in VENUES))
    return {"t0": t0, "n": n, "index": index, "var": var, "names": names}


def run_variants(V, closes=None):
    """Nowcast each candidate reading of the constituent books, and if any of
    them beats the stale published print, run the settlement test on it too."""
    n, index = V["n"], V["index"]
    im = causal_mean(index, 1, n)
    print("  nowcast of index[t] from index[t-1] (N0) and each reading.")
    print("  N3 is the INDEX-ONLY momentum control; the column that credits")
    print("  the constituent books is N4 vs N3, not N2 vs N0.")
    print(f"  {'reading':<17}{'n_test':>9}{'RMSE N0':>11}{'RMSE N1':>11}"
          f"{'N1 imp%':>9}{'N2 imp%':>9}{'N3 imp%':>9}{'N4 imp%':>9}"
          f"{'N4 vs N3':>10}{'b_repl':>8}")
    best = None
    for name in V["names"]:
        rep = V["var"][name]
        eb = causal_offset(index, rep, 1, n)
        d = nowcast_table(index, rep, eb, 1, n, imean=im)
        if not d["n_test"]:
            print(f"  {name:<17}   no overlapping seconds")
            continue
        r0 = d["rmse_n0"]
        i1 = 100.0 * (r0 - d["rmse_n1"]) / r0
        i2 = 100.0 * (r0 - d["rmse_n2"]) / r0
        i3 = 100.0 * (r0 - d["rmse_n3"]) / r0
        i4 = 100.0 * (r0 - d["rmse_n4"]) / r0
        marg = 100.0 * (d["rmse_n3"] - d["rmse_n4"]) / d["rmse_n3"]
        print(f"  {name:<17}{d['n_test']:>9,}{r0:>11.5g}{d['rmse_n1']:>11.5g}"
              f"{i1:>9.2f}{i2:>9.2f}{i3:>9.2f}{i4:>9.2f}{marg:>10.2f}"
              f"{d['coef4'][1]:>8.3f}")
        if best is None or marg > best[1]:
            best = (name, marg, eb)
    if best and closes:
        name, marg, eb = best
        print(f"\n  best reading by MARGINAL value over the index-only "
              f"control: {name} ({marg:+.2f}%)")
        sg = causal_sigma(index, 1, n)
        cls = [c - V["t0"] for c in closes if V["t0"] + 100 < c < V["t0"] + n]
        for lead in (0, 1):
            st = settle_table(index, V["var"][name], eb, sg, cls, 1, n,
                              rep_lead=lead, imean=im)
            print(f"  settlement test on {name}, rep_lead={lead}, "
                  f"{len(cls):,} closes")
            print(f"    {'r':>3}{'n_test':>8}{'RMSE model':>12}"
                  f"{'RMSE repl':>11}{'RMSE ctrl':>11}{'RMSE fit':>11}"
                  f"{'repl imp%':>11}{'ctrl imp%':>11}{'fit imp%':>10}"
                  f"{'fit-ctrl%':>11}{'b_repl':>8}{'MAEmodel':>9}"
                  f"{'MAEimp%':>9}{'maxerr':>9}")
            for r in R_VALUES:
                d = st.get(r)
                if not d or not d["n_test"]:
                    continue
                m = d["rmse_model"]
                ir = 100.0 * (m - d["rmse_reponly"]) / m
                ic = 100.0 * (m - d["rmse_control"]) / m
                iff = 100.0 * (m - d["rmse_fitted"]) / m
                mg = (100.0 * (d["rmse_control"] - d["rmse_fitted"])
                      / d["rmse_control"])
                print(f"    {r:>3}{d['n_test']:>8,}{m:>12.4f}"
                      f"{d['rmse_replica']:>11.4f}{d['rmse_control']:>11.4f}"
                      f"{d['rmse_fitted']:>11.4f}{ir:>11.2f}{ic:>11.2f}"
                      f"{iff:>10.2f}{mg:>11.2f}{d['beta']:>8.3f}"
                      f"{d['mae_model']:>9.3f}"
                      f"{(100.0*(d['mae_model']-d['mae_fitted'])/d['mae_model'] if d['mae_model'] > 0 else NAN):>9.2f}"
                      f"{d['max_model']:>9.1f}")


# ==========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feeds", default="./feed_data")
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--out", default="./fulltape")
    ap.add_argument("--hours", type=int, default=0)
    ap.add_argument("--skip-predict", action="store_true",
                    help="skip the k=1..20 horizon tables (section 2), which "
                         "are the only expensive part, and go straight to the "
                         "nowcast and the settlement test")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--variants", default="",
                    help="index id (e.g. BRTI) -- test every reading the "
                         "replica record carries, not just wmid")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_SELFTESTED") != "1":
        if selftest() != 0:
            print("\nself-test failed -- refusing to touch real data")
            return 1
    print()
    print("#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    t_start = time.time()
    if a.variants:
        iid = a.variants
        print()
        print("=" * 78)
        print(f"4. VARIANTS -- is the answer about the DATA or about the "
              f"FORMULA?  ({iid})")
        print("=" * 78)
        V = load_variants(a.feeds, a.data, iid=iid, hours=a.hours or None)
        if V is None:
            print("  no hours on disk for the variant test.")
            return 0
        run_variants(V, load_closes(a.out).get(iid))
        print(f"\n  total wall time {time.time() - t_start:.0f}s")
        return 0
    D = load(a.feeds, a.data, hours=a.hours or None)
    if D is None:
        return 0
    t0, n = D["t0"], D["n"]
    print(f"  loaded in {time.time() - t_start:.0f}s")
    print("  index ids with a replica: " + ", ".join(
        f"{k}={v:,}s" for k, v in sorted(D["idx_secs"].items())))
    if D["other_idx"]:
        print("  index ids with NO replica (no constituent books recorded): "
              + ", ".join(sorted(D["other_idx"])))
    print("  replica seconds: " + ", ".join(
        f"{k}={v:,}" for k, v in sorted(D["rep_secs"].items())))
    print("  median exchanges per second in the replica: " + ", ".join(
        f"{k}={hist_pctiles(v, (50,))[50]:.0f}"
        for k, v in sorted(D["nex"].items()) if v))

    # ---------------- 1. TIMING ------------------------------------------
    print()
    print("=" * 78)
    print("1. TIMING -- does the replica ARRIVE before the index print?")
    print("=" * 78)
    print("  Both stamps are local time.time() on THIS machine: _rx_ms in")
    print("  kalshi_collector.py:326, _rx in crypto_feeds.py index_replica().")
    print("  Same clock, two processes -- so this is arrival, not skew.")
    print()
    if D["cf_lat"]:
        pc = hist_pctiles(D["cf_lat"])
        print(f"  CF print stamp -> our receipt (ms), "
              f"n={hist_total(D['cf_lat']):,}")
        print(f"    p1 {pc[1]:.0f}  p25 {pc[25]:.0f}  MEDIAN {pc[50]:.0f}  "
              f"p75 {pc[75]:.0f}  p95 {pc[95]:.0f}  p99 {pc[99]:.0f}")
    if D["rep_lat"]:
        pc = hist_pctiles(D["rep_lat"])
        print(f"  replica top-of-second -> its own stamp (ms), "
              f"n={hist_total(D['rep_lat']):,}")
        print(f"    p1 {pc[1]:.1f}  p25 {pc[25]:.1f}  MEDIAN {pc[50]:.1f}  "
              f"p75 {pc[75]:.1f}  p95 {pc[95]:.1f}  p99 {pc[99]:.1f}")
    print()
    print("  GAP for the SAME second = index receipt - replica stamp, ms")
    print("  (positive = the replica was in hand first)")
    print(f"  {'index':<14}{'n':>10}{'p1':>8}{'p5':>8}{'p25':>8}{'MEDIAN':>9}"
          f"{'p75':>8}{'p95':>8}{'p99':>8}{'%replica first':>16}")
    for iid in ORDER:
        g = D["gaps"].get(iid)
        if not g:
            continue
        pc = hist_pctiles(g)
        first = hist_frac_gt(g, 0)
        print(f"  {iid:<14}{hist_total(g):>10,}{pc[1]:>8.0f}{pc[5]:>8.0f}"
              f"{pc[25]:>8.0f}{pc[50]:>9.0f}{pc[75]:>8.0f}{pc[95]:>8.0f}"
              f"{pc[99]:>8.0f}{first:>15.2f}%")

    # ---------------- 2. PREDICTIVE --------------------------------------
    print()
    print("=" * 78)
    print("2. PREDICTIVE POWER -- replica[t] rebased vs persistence")
    print("=" * 78)
    print("  P0 persistence  index[t]                    (what the model does)")
    print(f"  P1 rebased      replica[t] - ebar[t]        (ebar = causal "
          f"{OFFSET_W}s mean of replica-index)")
    print("  P2 fitted OOS   index[t] + b_k*(rebased - index[t]), b_k fitted")
    print(f"                  on the first {TRAIN_FRAC:.0%} of the span BY "
          f"TIME, scored on the rest")
    print("  P3 DIAGNOSTIC   index[t] + (replica[t+k] - replica[t]) -- uses the")
    print("                  FUTURE replica, NOT TRADEABLE, an upper bound only")
    print("  P4 fitted OOS   as P2 but with the replica's own last move")
    print("                  (replica[t]-replica[t-1]) as a second regressor")
    ebars, nowcasts, imeans = {}, {}, {}
    for iid in ORDER:
        idx = D["index"][iid]
        rep = D["replica"][iid]
        if D["idx_secs"].get(iid, 0) < 10000 or D["rep_secs"].get(iid, 0) < 10000:
            print(f"\n  {iid}: too little overlapping data "
                  f"(index {D['idx_secs'].get(iid, 0):,}s, "
                  f"replica {D['rep_secs'].get(iid, 0):,}s) -- skipped")
            continue
        eb = causal_offset(idx, rep, 1, n)
        ebars[iid] = eb
        im = causal_mean(idx, 1, n)
        imeans[iid] = im
        now = nowcast_table(idx, rep, eb, 1, n, imean=im)
        nowcasts[iid] = now
        if a.skip_predict:
            print(f"\n  {iid}: horizon table skipped (--skip-predict)")
            continue
        tab = horizon_table(idx, rep, eb, 1, n)
        both = sum(1 for t in range(n)
                   if idx[t] == idx[t] and rep[t] == rep[t])
        print(f"\n  {iid}  ({INDEX_TO_SERIES.get(iid)}, "
              f"{hist_pctiles(D['nex'][iid], (50,))[50]:.0f} exchanges median, "
              f"{both:,} seconds with both)")
        print(f"    {'k':>3}{'n_test':>10}{'RMSE P0':>13}{'RMSE P1':>13}"
              f"{'RMSE P2':>13}{'P1 imp%':>9}{'P2 imp%':>9}{'P4 imp%':>9}"
              f"{'b_basis':>9}{'P3 imp%(na)':>12}")
        for k in HORIZONS:
            d = tab[k]
            if not d["n_test"]:
                continue
            i1 = 100.0 * (d["rmse_p0"] - d["rmse_p1"]) / d["rmse_p0"]
            i2 = 100.0 * (d["rmse_p0"] - d["rmse_p2"]) / d["rmse_p0"]
            i4 = 100.0 * (d["rmse_p0"] - d["rmse_p4"]) / d["rmse_p0"]
            i3 = (100.0 * (d["rmse_p0_p3sub"] - d["rmse_p3"])
                  / d["rmse_p0_p3sub"]
                  if d["rmse_p3"] == d["rmse_p3"] else NAN)
            print(f"    {k:>3}{d['n_test']:>10,}{d['rmse_p0']:>13.6g}"
                  f"{d['rmse_p1']:>13.6g}{d['rmse_p2']:>13.6g}"
                  f"{i1:>9.2f}{i2:>9.2f}{i4:>9.2f}{d['beta']:>9.3f}"
                  f"{i3:>12.2f}")

    # ---------------- 2b. NOWCAST ----------------------------------------
    print()
    print("=" * 78)
    print("2b. NOWCAST -- is the 92ms arrival lead worth a WHOLE SECOND?")
    print("=" * 78)
    print("  At wall clock T+5ms we hold replica[T].  A reader of the published")
    print("  feed holds only index[T-1] until T+~95ms.  So the question is not")
    print("  whether the replica predicts the future -- it is whether it reads")
    print("  the CURRENT second better than the last published print does.")
    print("    N0  index[t-1]                     the feed, stale by one second")
    print("    N1  replica[t] - ebar[t]           the rebased replica")
    print("    N2  index[t-1] + b*(N1 - index[t-1])   fitted OOS")
    print("    N3  index[t-1] + c1*d1 + c2*d2 + c3*m1   INDEX-ONLY control,")
    print("                                       m1 = mean300(index)-index[t-1],")
    print("                                       the half of the rebasing that")
    print("                                       is index history alone")
    print("    N4  N3 plus the replica basis      everything at once")
    print("  all scored against index[t] itself.  N2 over N0 is not yet a")
    print("  finding: if the published index is itself smoothed, its own past")
    print("  predicts it.  THE COLUMN THAT CREDITS THE SPOT DATA IS N4 vs N3.")
    print(f"  {'index':<13}{'n_test':>9}{'RMSE N0':>11}{'RMSE N1':>11}"
          f"{'N1 imp%':>9}{'N2 imp%':>9}{'N3 imp%':>9}{'N4 imp%':>9}"
          f"{'N4 vs N3':>10}{'b_repl':>8}")
    for iid in ORDER:
        d = nowcasts.get(iid)
        if not d or not d["n_test"]:
            continue
        r0 = d["rmse_n0"]
        i1 = 100.0 * (r0 - d["rmse_n1"]) / r0
        i2 = 100.0 * (r0 - d["rmse_n2"]) / r0
        i3 = 100.0 * (r0 - d["rmse_n3"]) / r0
        i4 = 100.0 * (r0 - d["rmse_n4"]) / r0
        marg = 100.0 * (d["rmse_n3"] - d["rmse_n4"]) / d["rmse_n3"]
        print(f"  {iid:<13}{d['n_test']:>9,}{r0:>11.5g}{d['rmse_n1']:>11.5g}"
              f"{i1:>9.2f}{i2:>9.2f}{i3:>9.2f}{i4:>9.2f}{marg:>10.2f}"
              f"{d['coef4'][1]:>8.3f}")

    # ---------------- 3. THE DECISIVE TEST -------------------------------
    print()
    print("=" * 78)
    print("3. THE DECISIVE TEST -- the r UNPUBLISHED settlement prints")
    print("=" * 78)
    closes = load_closes(a.out)
    if not closes:
        print("  fulltape/markets.json holds no settled markets for these "
              "indices, so the settlement test is skipped.")
        return 0
    print("  Settlement = mean of index prints at seconds [close-60, close-1].")
    print("  With r unpublished, decision second t = close-1-r and the unknown")
    print("  is mean(index[close-r .. close-1]).  Errors divided by the index's")
    print(f"  own causal {SIGMA_W}s per-second sigma so coins pool.")
    for iid in ORDER:
        cl = closes.get(iid)
        if not cl or iid not in ebars:
            reason = "no settled markets" if not cl else "no usable tape"
            print(f"\n  {iid} ({INDEX_TO_SERIES.get(iid)}): {reason} -- skipped")
            continue
        idx = D["index"][iid]
        rep = D["replica"][iid]
        sg = causal_sigma(idx, 1, n)
        cls = [c - t0 for c in cl if t0 + 100 < c < t0 + n]
        print(f"\n  {iid}  ({INDEX_TO_SERIES.get(iid)}, "
              f"{len(cls):,} closes inside the tape)")
        for lead in (0, 1, -60):
            st = settle_table(idx, rep, ebars[iid], sg, cls, 1, n,
                              rep_lead=lead, imean=imeans[iid])
            tag = {0: "replica read at t, the same second as the last "
                      "published print -- no arrival advantage used",
                   1: "replica read at t+1 -- the REAL-TIME position, one "
                      "second of spot the published feed has not printed yet",
                   -60: "PLACEBO: replica read at t-60, a full minute stale. "
                        "Whatever this row finds, the fitting procedure "
                        "manufactures."}[lead]
            print(f"    rep_lead={lead}: {tag}")
            print(f"    {'r':>3}{'n_test':>8}{'RMSE model':>12}"
                  f"{'RMSE repl':>11}{'RMSE ctrl':>11}{'RMSE fit':>11}"
                  f"{'repl imp%':>11}{'ctrl imp%':>11}{'fit imp%':>10}"
                  f"{'fit-ctrl%':>11}{'b_repl':>8}{'t vs ctrl':>10}"
                  f"{'MAEimp%':>9}{'maxerr':>9}")
            for r in R_VALUES:
                d = st.get(r)
                if not d or not d["n_test"]:
                    continue
                m = d["rmse_model"]
                ir = 100.0 * (m - d["rmse_reponly"]) / m
                ic = 100.0 * (m - d["rmse_control"]) / m
                iff = 100.0 * (m - d["rmse_fitted"]) / m
                marg = (100.0 * (d["rmse_control"] - d["rmse_fitted"])
                        / d["rmse_control"])
                # the median absolute error is legitimately ZERO on the
                # coarsely quantised coins -- more than half of DOGE's closes
                # see the index not move at all over a few seconds -- so this
                # division is guarded rather than assumed safe
                mm = (100.0 * (d["mae_model"] - d["mae_fitted"]) / d["mae_model"]
                      if d["mae_model"] > 0 else NAN)
                print(f"    {r:>3}{d['n_test']:>8,}{m:>12.4f}"
                      f"{d['rmse_replica']:>11.4f}{d['rmse_control']:>11.4f}"
                      f"{d['rmse_fitted']:>11.4f}{ir:>11.2f}{ic:>11.2f}"
                      f"{iff:>10.2f}{marg:>11.2f}{d['beta']:>8.3f}"
                      f"{d['t_vs_ctrl']:>10.2f}{mm:>9.2f}"
                      f"{d['max_model']:>9.1f}")
    print()
    print(f"  total wall time {time.time() - t_start:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
