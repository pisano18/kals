#!/usr/bin/env python3
# VERSION: 2026-09-08-ac1
"""acvar.py -- IS THE WHITE-NOISE ASSUMPTION INSIDE THE VARIANCE MODEL TRUE?

THE QUESTION

engine.var_factor(tau, rho) takes an AUTOCOVARIANCE SEQUENCE. Every call site
in this project passes [1.0] -- one-second index increments are independent
white noise. Nobody has checked. If the increments are autocorrelated (positive
at short lags from staleness, negative from bid-ask bounce), then

    Var(settle) = (1/3600) sum_j sum_k w_j w_k gamma(|j-k|)

is being evaluated with the off-diagonal terms deleted, sd is wrong by a fixed
factor at every r, and so is every fair value pin has ever computed.

WHAT THIS FILE DOES

1. MEASURES gamma(h)/gamma(0) for h = 1..30 per index over the whole tape,
   from consecutive-second increments only.
2. RECOMPUTES var_factor with the measured rho and prints the sd ratio versus
   white noise for r = 1..60, calling out r = 19, 9, 4, 2.
3. RE-SCORES the pin gate (fair >= 0.98 / <= 0.02) with the corrected variance,
   WALK FORWARD: the rho used to price close C is estimated only from index
   increments strictly earlier than C - 900 (the previous close), so no part of
   the priced window, and no part of the decision instant, is in the estimator.
4. CHECKS the 880 identity empirically. Var(settle - strike) = 880 sigma^2 is a
   white-noise statement. The same quadratic form over the 959 increments that
   separate strike from settle, evaluated at the measured rho, gives the honest
   number. Both are printed next to the realised second moment.

NO-LOOKAHEAD DISCIPLINE, ENFORCED IN CODE

  * rho for close C comes from RhoBook.at(iid, C - 900), which sums per-hour
    lag blocks whose last touched price index is < the cutoff. The bound is
    asserted, not assumed (last_touched_sec()).
  * sigma for the decision at close C, tau seconds out, is the sample SD of the
    300 consecutive-second increments ending at C - tau -- prints that are
    already published at the moment of the decision.
  * two CANARIES run beside the real score. mu-oracle replaces the spot
    substitution with the realised settlement average through the same
    fair_at() code path; rho-leak estimates rho on a window centred on C, half
    of it in the future. If the harness were blind to leaked information the
    oracle would not separate from the honest model.

SELF-TEST: a white-noise world where the answer is rho = 0, var ratio = 1 and
the 880 identity holds; and an MA(1) world with a planted coefficient where the
estimator must recover it, where var_factor must move by the analytically known
amount, and where the 880 identity must BREAK by the known amount. An estimator
that cannot fail on the MA(1) world cannot be trusted on the tape.
"""
import argparse
import array
import calendar
import glob
import gzip
import math
import os
import random
import sys
import time
import zlib
from operator import mul
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import settle_weights, N_AVG                       # noqa: E402

ND = NormalDist()
IDXDIR = r"C:\kals\kalshi_data\cfbenchmarks_value"
FULLTAPE = r"C:\kals\fulltape\markets.json"

SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI",
    "KXBNB15M": "BNBUSD_RTI", "KXBCH15M": "BCHUSD_RTI",
    "KXZEC15M": "ZECUSD_RTI", "KXHYPE15M": "HYPEUSD_RTI",
    "KXNEAR15M": "NEARUSD_RTI", "KXADA15M": "ADAUSD_RTI",
}
MAXLAG = 30
PIN = 0.98
SIGMA_WIN = 300
BLOCK = 3600                      # rho is accumulated in one-hour blocks
NAN = float("nan")


# ===========================================================================
# variance
# ===========================================================================
def qform(w, rho):
    """(1/3600) sum_j sum_k w_j w_k gamma(|j-k|) / gamma0, for weights w."""
    tot = rho[0] * sum(x * x for x in w)
    n = len(w)
    for h in range(1, len(rho)):
        if h < n:
            tot += 2 * rho[h] * sum(w[i] * w[i + h] for i in range(n - h))
    return tot / (N_AVG ** 2)


def var_factor_rho(r, rho):
    """Var(settle)/gamma0 with r unpublished prints, under autocorrelation rho.

    Own implementation rather than engine.var_factor because engine clamps a
    negative quadratic form to 0.0, which would silently turn sd into zero and
    every fair value into a hard 0 or 1."""
    w = settle_weights(r)
    if not w:
        return 0.0
    return qform(w, rho)


def gap_weights():
    """The 959 one-second increments separating strike(N) from settle(N).

    strike(N) = settle(N-1) = mean of prints [C-960, C-901];
    settle(N)              = mean of prints [C-60,  C-1].
    Walking from X(C-960) to X(C-1): 59 increments inside the earlier window
    with weights 1..59, 841 gap increments at weight 60, 59 increments inside
    the later window with weights 59..1."""
    return list(range(1, 60)) + [60] * 841 + list(range(59, 0, -1))


def qform_se(w, n):
    """Standard error of qform() caused by SAMPLING ERROR IN rho alone.

    This matters far more than it looks. The 959-weight gap form has
    A_h = sum_i w_i w_{i+h} ~ 3e6 for every h, so a rho_h wrong by 0.001 moves
    the answer by 2*0.001*3e6/3600 ~ 1.7. With N increments, se(rho_h) ~
    1/sqrt(N), and the errors accumulate over MAXLAG lags. Quoting a measured
    "880" without this number would be quoting noise as a correction."""
    v = 0.0
    ln = len(w)
    for h in range(1, MAXLAG + 1):
        if h >= ln:
            break
        A = sum(w[i] * w[i + h] for i in range(ln - h))
        v += (2.0 * A / (N_AVG ** 2)) ** 2 / n
    return math.sqrt(v)


def bartlett(rho, bw):
    """Newey-West taper. Raw sample autocovariances at long lags are noisy and
    the quadratic form built from them need not be positive; the taper is the
    standard fix and it shrinks toward the white-noise answer, so it cannot
    manufacture a correction."""
    out = [rho[0]]
    for h in range(1, min(len(rho), bw + 1)):
        out.append(rho[h] * (1.0 - h / (bw + 1.0)))
    return out


# ===========================================================================
# loading
# ===========================================================================
BS = chr(92)
_TIME = BS + '"time' + BS + '":'
_VAL = BS + '"value' + BS + '":' + BS + '"'


def hour_of(path):
    return calendar.timegm(time.strptime(os.path.basename(path)[:11],
                                         "%Y%m%dT%H"))


def load_index(files, verbose=True):
    """{iid: array('d')} over one contiguous second grid, NaN where missing."""
    base = hour_of(files[0])
    end = hour_of(files[-1]) + 3600
    span = end - base
    vals, bad, n = {}, [], 0
    for f in files:
        try:
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    i = line.find('"index_id":"')
                    if i < 0:
                        continue
                    j = line.find('"', i + 12)
                    iid = line[i + 12:j]
                    k = line.find(_TIME, j)
                    if k < 0:
                        continue
                    k2 = line.find(",", k)
                    sec = int(line[k + len(_TIME):k2]) // 1000
                    v = line.find(_VAL, k2)
                    if v < 0:
                        continue
                    v2 = line.find(BS, v + len(_VAL))
                    idx = sec - base
                    if idx < 0 or idx >= span:
                        continue
                    a = vals.get(iid)
                    if a is None:
                        a = vals[iid] = array.array("d", [NAN]) * span
                    a[idx] = float(line[v + len(_VAL):v2])
                    n += 1
        except (EOFError, zlib.error, OSError) as e:
            bad.append((os.path.basename(f), type(e).__name__))
    if verbose:
        print("  %d hour files, %d indices, %s ticks"
              % (len(files), len(vals), format(n, ",")))
        if bad:
            print("  %d damaged file(s) used partially: %s"
                  % (len(bad), ", ".join("%s (%s)" % t for t in bad[:4])))
    return base, span, vals


# ===========================================================================
# per-hour lag blocks -> a walk-forward rho
# ===========================================================================
class RhoBook:
    """Autocovariance of one-second increments, accumulated in one-hour blocks
    so a trailing estimate is a sum of blocks rather than a rescan.

    Block b covers increment indices [b*BLOCK, (b+1)*BLOCK). Its lag-h sum uses
    partners at increment index i+h, so the last PRICE index any block can read
    is (b+1)*BLOCK - 1 + MAXLAG + 1. at() only ever admits blocks whose last
    readable price index is strictly below the cutoff."""

    def __init__(self, base, span, vals, maxlag=MAXLAG, verbose=False):
        self.base = base
        self.maxlag = maxlag
        self.nblk = span // BLOCK
        self.blocks = {}
        for iid, a in vals.items():
            z = array.array("d", [0.0]) * (span - 1)
            m = array.array("l", [0]) * (span - 1)
            for i in range(span - 1):
                x = a[i]
                y = a[i + 1]
                if x == x and y == y:
                    z[i] = y - x
                    m[i] = 1
            per = []
            for b in range(self.nblk):
                lo = b * BLOCK
                hi = min((b + 1) * BLOCK, span - 1)
                s = [0.0] * (maxlag + 1)
                c = [0] * (maxlag + 1)
                for h in range(maxlag + 1):
                    hi2 = min(hi, span - 1 - h)
                    if hi2 <= lo:
                        continue
                    s[h] = sum(map(mul, z[lo:hi2], z[lo + h:hi2 + h]))
                    c[h] = sum(map(mul, m[lo:hi2], m[lo + h:hi2 + h]))
                per.append((s, c, sum(z[lo:hi]), sum(m[lo:hi])))
            self.blocks[iid] = per
            del z, m
            if verbose:
                print("    rho blocks built for %s" % iid)

    def _last_readable(self, b):
        """Largest PRICE index block b can read. Never overridden -- this is
        the honest bound that last_touched_sec() reports."""
        return (b + 1) * BLOCK - 1 + self.maxlag + 1

    def _admit(self, b, cut):
        """Whether block b may be used to price something at index `cut`.
        The leak canary overrides THIS, not _last_readable, so that
        last_touched_sec() still reports the truth about what was read."""
        return self._last_readable(b) < cut

    def last_block(self, iid, cutoff_sec):
        """Index of the newest block admissible at cutoff_sec, or None.

        This is the ONLY safe cache key for a walk-forward rho. Keying on the
        hour that contains the cutoff is not: several closes share an hour, and
        whichever one fills the cache first fixes the block set for the rest.
        Iterating closes newest-first then hands an EARLIER close a rho built
        from blocks that postdate it. The audit in acrun caught exactly that,
        2,584 times, on 2026-09-08."""
        per = self.blocks.get(iid)
        if per is None:
            return None
        cut = cutoff_sec - self.base
        ok = [b for b in range(len(per)) if self._admit(b, cut)]
        return ok[-1] if ok else None

    def at(self, iid, cutoff_sec, hours):
        """rho[0..maxlag] from the `hours` most recent whole blocks that lie
        entirely earlier than cutoff_sec. (rho, n_increments)."""
        per = self.blocks.get(iid)
        if per is None:
            return None, 0
        cut = cutoff_sec - self.base
        ok = [b for b in range(len(per)) if self._admit(b, cut)]
        if not ok:
            return None, 0
        use = ok[-hours:]
        S = [0.0] * (self.maxlag + 1)
        C = [0] * (self.maxlag + 1)
        sd = 0.0
        nd = 0
        for b in use:
            s, c, sz, sm = per[b]
            for h in range(self.maxlag + 1):
                S[h] += s[h]
                C[h] += c[h]
            sd += sz
            nd += sm
        if C[0] < 2000:
            return None, 0
        mean = sd / nd if nd else 0.0
        g0 = S[0] / C[0] - mean * mean
        if g0 <= 0:
            return None, 0
        rho = [1.0]
        for h in range(1, self.maxlag + 1):
            rho.append(((S[h] / C[h] - mean * mean) / g0)
                       if C[h] > 200 else 0.0)
        return rho, C[0]

    def centred(self, iid, close_sec, hours):
        """DELIBERATE LEAK. Blocks centred on the close, half of them in the
        future. Exists only so the report can show what a leak would look
        like; never used to price anything."""
        per = self.blocks.get(iid)
        if per is None:
            return None, 0
        mid = (close_sec - self.base) // BLOCK
        lo = max(0, mid - hours // 2)
        hi = min(len(per), mid + hours // 2 + 1)
        use = list(range(lo, hi))
        if not use:
            return None, 0
        S = [0.0] * (self.maxlag + 1)
        C = [0] * (self.maxlag + 1)
        sd = 0.0
        nd = 0
        for b in use:
            s, c, sz, sm = per[b]
            for h in range(self.maxlag + 1):
                S[h] += s[h]
                C[h] += c[h]
            sd += sz
            nd += sm
        if C[0] < 2000:
            return None, 0
        mean = sd / nd if nd else 0.0
        g0 = S[0] / C[0] - mean * mean
        if g0 <= 0:
            return None, 0
        rho = [1.0]
        for h in range(1, self.maxlag + 1):
            rho.append(((S[h] / C[h] - mean * mean) / g0)
                       if C[h] > 200 else 0.0)
        return rho, C[0]

    def last_touched_sec(self, iid, cutoff_sec, hours):
        """The largest index-tape SECOND at() could have read for this call.
        The no-lookahead claim is this number being < cutoff_sec."""
        per = self.blocks.get(iid)
        if per is None:
            return None
        cut = cutoff_sec - self.base
        ok = [b for b in range(len(per)) if self._admit(b, cut)]
        if not ok:
            return None
        return self.base + max(self._last_readable(b) for b in ok)


# ===========================================================================
# the model
# ===========================================================================
def sigma_from(a, base, now_s, win=SIGMA_WIN):
    lo = now_s - win - base
    hi = now_s - base
    if lo < 0 or hi >= len(a):
        return None
    d = []
    for i in range(lo, hi):
        x = a[i]
        y = a[i + 1]
        if x == x and y == y:
            d.append(y - x)
    if len(d) < 20:
        return None
    m = sum(d) / len(d)
    return math.sqrt(sum((x - m) ** 2 for x in d) / (len(d) - 1))


def fair_at(a, base, close_s, now_s, K_eff, sigma, rho, mu_override=None):
    """Model fair value. rho is the autocovariance sequence handed to the
    variance; [1.0] reproduces the shipped white-noise model."""
    lo = close_s - N_AVG
    hi = min(now_s, close_s - 1)
    if hi < lo:
        return None
    want = hi - lo + 1
    got = []
    for s in range(lo, hi + 1):
        i = s - base
        if 0 <= i < len(a) and a[i] == a[i]:
            got.append(a[i])
    if not got or len(got) < want * 0.95:
        return None
    locked = sum(got) * (want / len(got))
    r = N_AVG - want
    si = now_s - base
    if not (0 <= si < len(a)) or a[si] != a[si]:
        return None
    spot = a[si]
    mu = (locked + r * spot) / N_AVG if mu_override is None else mu_override
    if r <= 0:
        return 1.0 if mu >= K_eff else 0.0
    vf = var_factor_rho(int(r), rho)
    if vf <= 0:
        return None
    sd = sigma * math.sqrt(vf)
    if sd <= 0:
        return 1.0 if mu >= K_eff else 0.0
    return ND.cdf((mu - K_eff) / sd)


def true_settle(a, base, close_s):
    got = []
    for s in range(close_s - N_AVG, close_s):
        i = s - base
        if 0 <= i < len(a) and a[i] == a[i]:
            got.append(a[i])
    if len(got) < N_AVG * 0.95:
        return None
    return sum(got) / len(got)


# ===========================================================================
# self-test
# ===========================================================================
def _synth_book(inc):
    """Wrap a list of one-second increments into the array shape."""
    span = len(inc) + 1
    a = array.array("d", [0.0]) * span
    v = 100.0
    for i, d in enumerate(inc):
        a[i] = v
        v += d
    a[span - 1] = v
    return a, span


def selftest():
    print("SELF-TEST -- acvar")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    rng = random.Random(11)

    # ---- WORLD 1: white noise. rho ~ 0, corrected variance == white-noise
    # variance, 880 identity holds.
    n = 120 * BLOCK
    inc = [rng.gauss(0, 1.0) for _ in range(n)]
    a, span = _synth_book(inc)
    rb = RhoBook(0, span, {"W": a}, maxlag=MAXLAG)
    rho, cnt = rb.at("W", span, 200)
    m1 = max(abs(x) for x in rho[1:])
    print("  white noise: n=%s increments, max |rho_h| = %.4f"
          % (format(cnt, ","), m1))
    ck(m1 < 0.02, "white noise gives rho ~ 0 (max |rho| %.4f < 0.02)" % m1)
    rr = math.sqrt(var_factor_rho(19, rho) / var_factor_rho(19, [1.0]))
    ck(abs(rr - 1) < 0.02, "sd ratio at r=19 is 1 under white noise (%.4f)" % rr)
    g = qform(gap_weights(), rho)
    gse = qform_se(gap_weights(), cnt)
    print("  white noise: Var(settle-strike)/gamma0 = %.1f  (se from rho "
          "sampling error alone = %.1f)" % (g, gse))
    ck(abs(g - 880.0) < 3 * gse,
       "Var(settle-strike)/gamma0 = 880 under white noise (got %.1f, "
       "3 se = %.1f)" % (g, 3 * gse))
    ck(abs(qform(gap_weights(), [1.0]) - 880.0056) < 0.01,
       "the 959-weight quadratic form reproduces 880 exactly at rho=[1]")

    # ---- WORLD 2: MA(1), d_t = e_t + th*e_{t-1}. Planted rho_1 =
    # th/(1+th^2), rho_h = 0 for h >= 2. Long-run variance is (1+th)^2 var(e),
    # so a negative th must SHRINK the settlement sd and must break 880.
    th = -0.35
    e = [rng.gauss(0, 1.0) for _ in range(n + 1)]
    inc = [e[i + 1] + th * e[i] for i in range(n)]
    a2, span2 = _synth_book(inc)
    rb2 = RhoBook(0, span2, {"M": a2}, maxlag=MAXLAG)
    rho2, cnt2 = rb2.at("M", span2, 200)
    want1 = th / (1 + th * th)
    print("  MA(1) th=%.2f: rho_1 measured %+.4f, theory %+.4f; rho_2 %+.4f"
          % (th, rho2[1], want1, rho2[2]))
    ck(abs(rho2[1] - want1) < 0.02,
       "the estimator recovers a planted rho_1 (%+.4f vs %+.4f)"
       % (rho2[1], want1))
    ck(abs(rho2[2]) < 0.02, "and finds nothing at lag 2 (%+.4f)" % rho2[2])

    exact = [1.0, want1] + [0.0] * (MAXLAG - 1)
    for r in (2, 4, 9, 19):
        got = var_factor_rho(r, rho2)
        wnt = var_factor_rho(r, exact)
        ck(abs(got / wnt - 1) < 0.05,
           "measured-rho variance matches MA(1) theory at r=%d (%.6g vs %.6g)"
           % (r, got, wnt))
    r19 = math.sqrt(var_factor_rho(19, rho2) / var_factor_rho(19, [1.0]))
    print("  MA(1): sd at r=19 is %.4fx the white-noise sd" % r19)
    ck(r19 < 0.95,
       "a negative rho_1 SHRINKS the settlement sd and the test sees it "
       "(%.4f must be well below 1)" % r19)

    g2 = qform(gap_weights(), rho2)
    print("  MA(1): Var(settle-strike)/gamma0 = %.1f, not 880" % g2)
    ck(abs(g2 - 880 * (1 + 2 * want1)) < 25,
       "the 880 identity breaks by the analytic amount under MA(1) "
       "(%.1f vs %.1f)" % (g2, 880 * (1 + 2 * want1)))

    # ---- NO-LOOKAHEAD: at() must never touch a second >= the cutoff.
    leaks = 0
    for cut in (30 * BLOCK, 70 * BLOCK, 119 * BLOCK):
        lt = rb2.last_touched_sec("M", cut, 6)
        if lt is None or lt >= cut:
            leaks += 1
    ck(leaks == 0,
       "RhoBook.at() never reads an index second at or after its cutoff")

    class Leaky(RhoBook):
        def _admit(self, b, cut):
            return True
    lk = Leaky(0, span2, {"M": a2}, maxlag=MAXLAG)
    lt = lk.last_touched_sec("M", 30 * BLOCK, 6)
    ck(lt is not None and lt >= 30 * BLOCK,
       "and the same check FIRES on a deliberately leaking subclass "
       "(touched %s, cutoff %d)" % (lt, 30 * BLOCK))

    tp = bartlett(rho2, 30)
    ck(abs(tp[1]) < abs(rho2[1]) + 1e-12,
       "the Bartlett taper shrinks toward white noise, never away from it")

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a, _ = ap.parse_known_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    raise SystemExit("acvar.py: run --selftest, or import it from acrun.py")
