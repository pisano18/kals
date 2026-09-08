#!/usr/bin/env python3
# VERSION: 2026-09-08-rm1
"""remain.py -- STOP SUBSTITUTING ONE NOISY TICK FOR THE FUTURE.

THE QUESTION

Settlement is the mean of the 60 one-second index prints over
[close-60, close-1].  With tau seconds to close, the prints for seconds
[close-60 .. close-tau] are already on disk and r = tau-1 of them are not.
The shipped model replaces EVERY unprinted print with the current spot tick.

That single tick is noisy.  When it is a transient the model extrapolates the
transient across all r remaining prints and can be confidently wrong.  That is
the documented cause of the only loss in the 2026-09-07 replay
(KXETH15M-26SEP071745-45: ETHUSD_RTI dipped to 2492.60 at tau 5-6, model fair
0.005, index back to 2493.08 by tau=3, settle 2492.8158 -> YES).

WHAT THIS MEASURES

The estimation problem on its own, before any P&L.  For every index, every
quarter-hour close and every tau in [3,20]:

    target    = mean(actual remaining prints)      -- known after the fact
    estimate  = f(prints at or before close-tau)   -- known at decision time

and then bias and RMSE of (target - estimate) per estimator, broken down by r
and by how far spot sits from its own trailing mean.  Everything is expressed
in units of the index's own trailing sigma so the 11 coins can be pooled.

THE ESTIMATORS

  (a) spot            the shipped model: xhat = P0
  (b) mean_k          xhat = mean of the last k prints, k in {2,3,5,10}
  (c) shrink          xhat = lam*P0 + (1-lam)*mean_k, lam fitted WALK-FORWARD
  (c') shrink_ksel    same, with k also chosen walk-forward
  (c'')mean_ksel      plain mean_k with k chosen walk-forward, k=1 means spot
  (d) ar1             explicit mean reversion: AR(1) on 1-second index
                      increments, phi fitted WALK-FORWARD per index

NO PEEKING -- HOW IT IS ENFORCED

Closes are processed in strict chronological order.  Every fitted quantity is
carried as a RUNNING SUFFICIENT STATISTIC that is updated only AFTER a close
has been scored.  So the lam, k and phi used to price close C are functions of
closes strictly earlier than C and of nothing else.  There is no global fit
anywhere in the scoring path.  sigma and every trailing mean use ticks at or
before close-tau only.

Two deliberate leaks are scored alongside, to prove the harness would SHOW a
leak rather than hide one:

  LEAK_oracle   xhat = the true remaining mean.  Must score ~0 error.
  LEAK_lamfull  the same shrinkage, but with lam fitted on the WHOLE sample
                including the close being scored.  If walk-forward were
                secretly peeking, these two would agree; the gap between them
                is the size of the lookahead this study avoids.

SELF-TEST: three planted worlds.
  1. pure random walk -- spot IS optimal, so shrinkage must not beat it and
     the fitted lam must come out near 1.
  2. transient world -- price = slow walk + iid measurement noise, so the
     trailing mean IS optimal and shrinkage MUST beat spot; a harness that
     cannot see this cannot be trusted on real data.
  3. leak detector -- the oracle estimator must score ~0, and the walk-forward
     machinery must NOT be able to reproduce it.
"""
import argparse
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
from array import array
from collections import defaultdict
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor, N_AVG                        # noqa: E402

ND = NormalDist()
IDXDIR = r"C:\kals\kalshi_data\cfbenchmarks_value"
FULLTAPE = r"C:\kals\fulltape\markets.json"
CACHE = os.path.join(os.environ.get("TEMP", "/tmp"), "remain_cache")

IDX_IDS = ["BRTI", "ETHUSD_RTI", "SOLUSD_RTI", "XRPUSD_RTI", "DOGEUSD_RTI",
           "BNBUSD_RTI", "BCHUSD_RTI", "ZECUSD_RTI", "HYPEUSD_RTI",
           "NEARUSD_RTI", "ADAUSD_RTI"]

SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI",
    "KXBNB15M": "BNBUSD_RTI", "KXBCH15M": "BCHUSD_RTI",
    "KXZEC15M": "ZECUSD_RTI", "KXHYPE15M": "HYPEUSD_RTI",
    "KXNEAR15M": "NEARUSD_RTI", "KXADA15M": "ADAUSD_RTI",
}

SIGMA_WIN = 300          # trailing seconds for the sigma estimate
KS = (2, 3, 5, 10)       # trailing-mean lengths offered to the estimators
KSEL = (1,) + KS         # 1 == spot, so k-selection can choose the baseline
KFIX = 5                 # the k used by the plain `shrink` estimator
MIN_FIT = 300            # cells of earlier data before a fitted param is used
NAN = float("nan")


# ===========================================================================
# tick cache -- one array('d') per index, NaN = missing second
# ===========================================================================
def hour_of(path):
    return calendar.timegm(time.strptime(os.path.basename(path)[:11],
                                         "%Y%m%dT%H"))


def build_cache(verbose=True):
    os.makedirs(CACHE, exist_ok=True)
    files = sorted(glob.glob(os.path.join(IDXDIR, "2026*.jsonl.gz")))
    if len(files) < 2:
        raise SystemExit("no index hour files")
    files = files[:-1]                       # newest hour is a live gzip
    t0, t1 = hour_of(files[0]), hour_of(files[-1]) + 3599
    n = t1 - t0 + 1
    ticks = {i: array("d", [NAN]) * n for i in IDX_IDS}
    avg60 = {i: {} for i in IDX_IDS}         # exchange's own 60s window mean
    bad, nlines = [], 0
    for fi, f in enumerate(files):
        try:
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    a = line.find('"index_id":"')
                    if a < 0:
                        continue
                    b = line.find('"', a + 12)
                    iid = line[a + 12:b]
                    arr = ticks.get(iid)
                    if arr is None:
                        continue
                    c = line.find('\\"time\\":', b)
                    if c < 0:
                        continue
                    d = line.find(',', c)
                    sec = int(line[c + 9:d]) // 1000
                    e = line.find('\\"value\\":\\"', d)
                    if e < 0:
                        continue
                    g = line.find('\\', e + 11)
                    v = float(line[e + 12:g])
                    k = sec - t0
                    if 0 <= k < n:
                        arr[k] = v
                        nlines += 1
                    if sec % 900 == 0:
                        h = line.find('"avg_60s_data":{"value":"', g)
                        if h >= 0:
                            j = line.find('"', h + 25)
                            try:
                                avg60[iid][sec] = float(line[h + 25:j])
                            except ValueError:
                                pass
        except (EOFError, zlib.error, OSError) as ex:
            bad.append((os.path.basename(f), type(ex).__name__))
        if verbose and fi % 40 == 0:
            print("    %d/%d %s" % (fi + 1, len(files), os.path.basename(f)),
                  flush=True)
    meta = dict(t0=t0, t1=t1, n=n, files=len(files), ticks=nlines,
                bad=[list(x) for x in bad])
    with open(os.path.join(CACHE, "meta.json"), "w") as fh:
        json.dump(meta, fh)
    for i in IDX_IDS:
        with open(os.path.join(CACHE, i + ".f64"), "wb") as fh:
            ticks[i].tofile(fh)
        with open(os.path.join(CACHE, i + ".avg60.json"), "w") as fh:
            json.dump(avg60[i], fh)
    if verbose:
        print("  cache built: %d ticks, %d files, %d damaged"
              % (nlines, len(files), len(bad)))
    return meta


def load_cache():
    meta = json.load(open(os.path.join(CACHE, "meta.json")))
    ticks, avg60 = {}, {}
    for i in IDX_IDS:
        a = array("d")
        with open(os.path.join(CACHE, i + ".f64"), "rb") as fh:
            a.fromfile(fh, meta["n"])
        ticks[i] = a
        p = os.path.join(CACHE, i + ".avg60.json")
        avg60[i] = {int(k): v for k, v in json.load(open(p)).items()}
    return meta, ticks, avg60


# ===========================================================================
# the estimation cell -- everything below is a function of ticks <= now only
# ===========================================================================
def cell(arr, base, close_s, tau):
    """Everything knowable at close_s - tau, plus the target.

    r = tau-1 prints remain, at seconds [close-tau+1 .. close-1].
    Returns None unless the whole window is clean.
    """
    now = close_s - tau
    r = tau - 1
    if r < 1:
        return None
    i_now = now - base
    i_close = close_s - base
    if i_now - SIGMA_WIN - 1 < 0 or i_close > len(arr):
        return None
    p0 = arr[i_now]
    if p0 != p0:
        return None
    tot = 0.0
    for s in range(i_now + 1, i_close):
        v = arr[s]
        if v != v:
            return None
        tot += v
    target = tot / r
    lo = i_close - N_AVG
    locked, got = 0.0, 0
    for s in range(lo, i_now + 1):
        v = arr[s]
        if v == v:
            locked += v
            got += 1
    want = i_now + 1 - lo
    if want <= 0 or got < want * 0.95:
        return None
    locked *= want / got
    diffs = []
    prev = arr[i_now - SIGMA_WIN]
    for s in range(i_now - SIGMA_WIN + 1, i_now + 1):
        v = arr[s]
        if v == v and prev == prev:
            diffs.append(v - prev)
        prev = v
    if len(diffs) < 60:
        return None
    m = sum(diffs) / len(diffs)
    sigma = math.sqrt(sum((x - m) ** 2 for x in diffs) / (len(diffs) - 1))
    if sigma <= 0:
        return None
    mk = {}
    for k in KS:
        t, c = 0.0, 0
        for s in range(i_now - k + 1, i_now + 1):
            v = arr[s]
            if v == v:
                t += v
                c += 1
        if c < k:
            return None
        mk[k] = t / k
    pm1 = arr[i_now - 1]
    dlast = (p0 - pm1) if pm1 == pm1 else 0.0
    return dict(now=now, r=r, tau=tau, p0=p0, target=target, locked=locked,
                want=want, sigma=sigma, mk=mk, dlast=dlast,
                lasttick=arr[i_close - 1])


def ar1_mean(p0, dlast, phi, r):
    """Mean of the r remaining prints under AR(1) increments.

    E[X_{t+h}] = X_t + d_t * (phi + ... + phi^h), so the mean over h = 1..r is
    X_t + d_t * (1/r) * sum_h sum_{j<=h} phi^j.
    """
    if phi == 0.0:
        return p0
    tot, run, ph = 0.0, 0.0, 1.0
    for _ in range(r):
        ph *= phi
        run += ph
        tot += run
    return p0 + dlast * tot / r


# ===========================================================================
# walk-forward parameter state: running sums, updated only AFTER scoring
# ===========================================================================
class Fitter:
    """Per-r shrinkage lam and per-(r,k) running SSE, plus per-index AR(1) phi.

    Read order is enforced by the caller: estimates() for a close is computed
    BEFORE absorb_*() is given that close's data.
    """

    def __init__(self):
        self.suy = defaultdict(float)        # (r,k) -> sum u*y, sigma units
        self.suu = defaultdict(float)        # (r,k) -> sum u*u
        self.nfit = defaultdict(int)
        self.sse_mean = defaultdict(float)   # (r,k) -> SSE of plain mean_k
        self.sse_shr = defaultdict(float)    # (r,k) -> SSE of shrunk_k
        self.ac_num = defaultdict(float)     # iid -> sum d_t d_{t-1}
        self.ac_den = defaultdict(float)
        self.ac_n = defaultdict(int)
        self.fallbacks = 0
        self.used = 0

    def lam(self, r, k):
        key = (r, k)
        if self.nfit[key] < MIN_FIT or self.suu[key] <= 0:
            return None
        return self.suy[key] / self.suu[key]

    def best_k_mean(self, r):
        if self.nfit[(r, KFIX)] < MIN_FIT:
            return None
        return min((self.sse_mean[(r, k)], k) for k in KSEL)[1]

    def best_k_shrink(self, r):
        if self.nfit[(r, KFIX)] < MIN_FIT:
            return None
        return min((self.sse_shr[(r, k)], k) for k in KS)[1]

    def phi(self, iid):
        if self.ac_n[iid] < 20000 or self.ac_den[iid] <= 0:
            return None
        return self.ac_num[iid] / self.ac_den[iid]

    def absorb_cell(self, c):
        sg = c["sigma"]
        for k in KS:
            u = (c["p0"] - c["mk"][k]) / sg
            y = (c["target"] - c["mk"][k]) / sg
            key = (c["r"], k)
            lm = self.lam(c["r"], k)         # BEFORE this cell is folded in
            if lm is not None:
                e = y - lm * u
                self.sse_shr[key] += e * e
            self.suy[key] += u * y
            self.suu[key] += u * u
            self.nfit[key] += 1
            self.sse_mean[key] += y * y
        e1 = (c["target"] - c["p0"]) / sg
        self.sse_mean[(c["r"], 1)] += e1 * e1

    def absorb_acf(self, iid, arr, base, close_s):
        """1-second increment autocorrelation from the 360 s before a close."""
        lo = close_s - base - 360
        hi = close_s - base
        if lo < 1:
            return
        d_prev = None
        for s in range(lo, hi):
            a, b = arr[s - 1], arr[s]
            if a != a or b != b:
                d_prev = None
                continue
            d = b - a
            if d_prev is not None:
                self.ac_num[iid] += d * d_prev
                self.ac_den[iid] += d_prev * d_prev
                self.ac_n[iid] += 1
            d_prev = d


def estimates(c, fit, iid, lam_full=None):
    """Every estimator's xhat for one cell."""
    p0, mk, r = c["p0"], c["mk"], c["r"]
    out = {"spot": p0}
    for k in KS:
        out["mean%d" % k] = mk[k]
    lm = fit.lam(r, KFIX)
    if lm is None:
        fit.fallbacks += 1
        out["shrink"] = p0
    else:
        fit.used += 1
        out["shrink"] = mk[KFIX] + lm * (p0 - mk[KFIX])
    kb = fit.best_k_shrink(r)
    l2 = fit.lam(r, kb) if kb is not None else None
    out["shrink_ksel"] = p0 if l2 is None else mk[kb] + l2 * (p0 - mk[kb])
    km = fit.best_k_mean(r)
    out["mean_ksel"] = p0 if km in (None, 1) else mk[km]
    ph = fit.phi(iid)
    out["ar1"] = p0 if ph is None else ar1_mean(p0, c["dlast"], ph, r)
    # --- deliberate leaks, scored to prove the harness can see one ----------
    # A PARTIAL leak matters more than the oracle: it shows the harness has a
    # gradient, so a small accidental peek would also show up rather than
    # hiding inside the noise.  lasttick uses exactly ONE second of the
    # future -- the print at close-1 -- and nothing else.
    out["LEAK_lasttick"] = c["lasttick"]
    out["LEAK_oracle"] = c["target"]
    if lam_full is not None:
        lf = lam_full.get((r, KFIX))
        out["LEAK_lamfull"] = (p0 if lf is None
                               else mk[KFIX] + lf * (p0 - mk[KFIX]))
    else:
        out["LEAK_lamfull"] = p0
    return out


EST_ORDER = (["spot"] + ["mean%d" % k for k in KS]
             + ["shrink", "shrink_ksel", "mean_ksel", "ar1",
                "LEAK_lamfull", "LEAK_lasttick", "LEAK_oracle"])


# ===========================================================================
class Acc:
    """bias / RMSE accumulator in sigma units."""

    def __init__(self):
        self.n = 0
        self.s = 0.0
        self.s2 = 0.0

    def add(self, e):
        self.n += 1
        self.s += e
        self.s2 += e * e

    @property
    def bias(self):
        return self.s / self.n if self.n else float("nan")

    @property
    def rmse(self):
        return math.sqrt(self.s2 / self.n) if self.n else float("nan")


def tstat(xs):
    n = len(xs)
    if n < 3:
        return float("nan")
    m = sum(xs) / n
    v = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m / math.sqrt(v / n) if v > 0 else float("nan")


# ===========================================================================
def selftest():
    print("SELF-TEST -- remain")
    fails = []

    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            fails.append(msg)

    # -- ar1_mean arithmetic, checked by hand ------------------------------
    # phi = -0.5, r = 2, d = 1: E[X+1] = P0 + d*(-0.5) = P0 - 0.5
    #                           E[X+2] = P0 + d*(-0.5+0.25) = P0 - 0.25
    #                           mean    = P0 - 0.375
    got = ar1_mean(100.0, 1.0, -0.5, 2)
    ck(abs(got - 99.625) < 1e-12,
       "ar1_mean matches hand arithmetic (%.6f vs 99.625)" % got)
    ck(abs(ar1_mean(100.0, 3.0, 0.0, 5) - 100.0) < 1e-12,
       "ar1_mean with phi=0 is exactly spot")

    # -- cell() reads the right window -------------------------------------
    base = 0
    arr = array("d", [NAN]) * 1000
    C = 900
    for s in range(1000):
        # jitter only BEFORE the settlement window so sigma > 0 while the
        # locked prints, the trailing means and the target stay exact
        arr[s] = 10.0 + (0.001 * ((s * 37) % 7) if s < C - N_AVG else 0.0)
    for s in range(C - 4, C):
        arr[s] = 20.0                    # last 4 prints of the window differ
    c = cell(arr, base, C, 5)            # now = 895, r = 4, remaining 896..899
    ck(c is not None, "cell() returns a cell on a clean window")
    if c:
        ck(c["r"] == 4 and c["now"] == 895,
           "cell() r=%d now=%d (want 4, 895)" % (c["r"], c["now"]))
        ck(abs(c["target"] - 20.0) < 1e-12,
           "target is the mean of the REMAINING prints (%.4f, want 20)"
           % c["target"])
        ck(abs(c["p0"] - 10.0) < 1e-12,
           "spot is the tick at close-tau, not later (%.4f, want 10)"
           % c["p0"])
        # locked = 56 prints at 10 plus the one at 895 -> all 10.0
        ck(abs(c["locked"] - 560.0) < 1e-9,
           "locked sum covers [close-60, now] (%.2f, want 560)" % c["locked"])
    ck(cell(arr, base, C, 1) is None, "tau=1 (r=0) is rejected")
    arr[C - 2] = NAN
    ck(cell(arr, base, C, 5) is None,
       "a missing remaining print drops the cell rather than guessing it")

    # -- WORLD 1: pure random walk. spot IS optimal. -----------------------
    def run_world(mk_series, trials=900, seed=1):
        rng = random.Random(seed)
        fit = Fitter()
        acc = defaultdict(Acc)
        lam_seen = []
        for t in range(trials):
            a = mk_series(rng)
            C = 900
            for tau in (5, 10, 20):
                c = cell(a, 0, C, tau)
                if c is None:
                    continue
                es = estimates(c, fit, "X")
                for name, x in es.items():
                    acc[name].add((c["target"] - x) / c["sigma"])
                if fit.lam(c["r"], KFIX) is not None and c["r"] == 9:
                    lam_seen.append(fit.lam(c["r"], KFIX))
                fit.absorb_cell(c)
        return acc, fit, lam_seen

    def walk(rng):
        a = array("d", [NAN]) * 1000
        v = 100.0
        for s in range(1000):
            v += rng.gauss(0, 1.0)
            a[s] = v
        return a

    def noisy(rng):
        """slow true price + iid measurement noise -> spot is a bad estimate,
        the trailing mean is a good one."""
        a = array("d", [NAN]) * 1000
        v = 100.0
        for s in range(1000):
            v += rng.gauss(0, 0.10)
            a[s] = v + rng.gauss(0, 1.0)
        return a

    accW, fitW, lamW = run_world(walk, seed=11)
    print("  world 1 (random walk)   n=%d  spot RMSE %.4f  shrink RMSE %.4f  "
          "mean5 RMSE %.4f" % (accW["spot"].n, accW["spot"].rmse,
                               accW["shrink"].rmse, accW["mean5"].rmse))
    if lamW:
        print("      fitted lam (r=9) ended at %.3f (want ~1)" % lamW[-1])
    ck(accW["spot"].n > 1000, "world 1 produced cells (%d)" % accW["spot"].n)
    ck(accW["shrink"].rmse <= accW["spot"].rmse * 1.05,
       "on a random walk shrinkage does not damage spot "
       "(%.4f vs %.4f)" % (accW["shrink"].rmse, accW["spot"].rmse))
    ck(accW["mean5"].rmse > accW["spot"].rmse,
       "on a random walk the plain trailing mean IS worse than spot "
       "(%.4f vs %.4f) -- the test can tell the two worlds apart"
       % (accW["mean5"].rmse, accW["spot"].rmse))
    ck(bool(lamW) and lamW[-1] > 0.85,
       "walk-forward lam converges to ~1 on a random walk (%.3f)"
       % (lamW[-1] if lamW else float("nan")))

    accN, fitN, lamN = run_world(noisy, seed=12)
    print("  world 2 (noisy transient) n=%d  spot RMSE %.4f  shrink RMSE %.4f  "
          "mean5 RMSE %.4f" % (accN["spot"].n, accN["spot"].rmse,
                               accN["shrink"].rmse, accN["mean5"].rmse))
    if lamN:
        print("      fitted lam (r=9) ended at %.3f (want well below 1)"
              % lamN[-1])
    ck(accN["shrink"].rmse < accN["spot"].rmse * 0.95,
       "in a transient world shrinkage BEATS spot (%.4f vs %.4f) -- an "
       "estimator that cannot win here cannot be trusted to win on real data"
       % (accN["shrink"].rmse, accN["spot"].rmse))
    ck(bool(lamN) and lamN[-1] < 0.7,
       "walk-forward lam shrinks hard in a transient world (%.3f)"
       % (lamN[-1] if lamN else float("nan")))

    # -- WORLD 3: the leak detector ----------------------------------------
    ck(accN["LEAK_oracle"].rmse < 1e-12,
       "the oracle leak scores ~0 RMSE (%.2e) -- so a leak in this harness "
       "shows up as an implausibly good score, not as silence"
       % accN["LEAK_oracle"].rmse)
    ck(accN["shrink"].rmse > 0.05,
       "the walk-forward estimator does NOT reproduce the oracle (%.4f) -- "
       "it is not peeking" % accN["shrink"].rmse)

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


# ===========================================================================
def zbucket(z):
    a = abs(z)
    if a < 0.5:
        return 0
    if a < 1.0:
        return 1
    if a < 2.0:
        return 2
    return 3


ZLAB = ["|z| < 0.5", "0.5 - 1.0", "1.0 - 2.0", "|z| >= 2.0"]


def load_round_digits(verbose=True):
    """round_digits per series, read from custom_strike on a live market.

    Imported AFTER the repo is already on sys.path so kals-work cannot shadow
    a repo module.
    """
    out = {}
    try:
        sys.path.append(r"C:\Users\Joe\AppData\Local\Temp\kals-work")
        from kauth import get
    except Exception as e:
        print("  round_digits: kauth unavailable (%s)" % e)
        return out
    for s in SERIES_TO_INDEX:
        try:
            st, b = get("/markets", {"series_ticker": s, "status": "open",
                                     "limit": "1"})
            ms = (b or {}).get("markets") or []
            if not ms:
                continue
            d = (ms[0].get("custom_strike") or {}).get("round_digits")
            if d is not None:
                out[s] = int(d)
        except Exception:
            pass
    if verbose:
        print("  round_digits READ from the exchange: "
              + ", ".join("%s=%d" % kv for kv in sorted(out.items())))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--build-cache", action="store_true")
    ap.add_argument("--taus", default="3,4,5,6,8,10,12,15,20")
    ap.add_argument("--no-api", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not os.environ.get("KALS_SELFTESTED"):
        if not selftest():
            raise SystemExit("self-test failed")
    print()
    if a.build_cache or not os.path.exists(os.path.join(CACHE, "meta.json")):
        print("  building tick cache from %s" % IDXDIR)
        build_cache()
    meta, ticks, avg60 = load_cache()
    base, n = meta["t0"], meta["n"]
    print("  index cache: %s .. %s, %d hour files, %d ticks, %d damaged"
          % (time.strftime("%Y-%m-%dT%HZ", time.gmtime(meta["t0"])),
             time.strftime("%Y-%m-%dT%HZ", time.gmtime(meta["t1"])),
             meta["files"], meta["ticks"], len(meta["bad"])))
    for nm, ty in meta["bad"][:6]:
        print("      damaged: %s (%s)" % (nm, ty))
    taus = [int(x) for x in a.taus.split(",")]
    closes = [c for c in range(base + (900 - base % 900) % 900, base + n, 900)]
    print("  %d quarter-hour closes, taus %s" % (len(closes), taus))

    # ------------------------------------------------------------------
    # PASS 1 (LEAK ONLY): lam fitted on the WHOLE sample.  This exists only
    # so the report can show what a lookahead fit would have scored.
    # ------------------------------------------------------------------
    full = defaultdict(lambda: [0.0, 0.0])
    cells_by_close = {}
    t_start = time.time()
    for ci, C in enumerate(closes):
        got = []
        for iid in IDX_IDS:
            arr = ticks[iid]
            for tau in taus:
                c = cell(arr, base, C, tau)
                if c is not None:
                    got.append((iid, c))
        if got:
            cells_by_close[C] = got
            for iid, c in got:
                u = (c["p0"] - c["mk"][KFIX]) / c["sigma"]
                y = (c["target"] - c["mk"][KFIX]) / c["sigma"]
                key = (c["r"], KFIX)
                full[key][0] += u * y
                full[key][1] += u * u
    lam_full = {k: (v[0] / v[1]) for k, v in full.items() if v[1] > 0}
    ncell = sum(len(v) for v in cells_by_close.values())
    print("  %d clean cells over %d closes  (%.0f s to build)"
          % (ncell, len(cells_by_close), time.time() - t_start))

    # ------------------------------------------------------------------
    # PASS 2: WALK FORWARD.  score, then absorb.  Never the other way.
    # ------------------------------------------------------------------
    fit = Fitter()
    tot = defaultdict(Acc)
    by_r = defaultdict(lambda: defaultdict(Acc))
    by_z = defaultdict(lambda: defaultdict(Acc))
    by_rz = defaultdict(lambda: defaultdict(Acc))
    per_close_sq = defaultdict(lambda: defaultdict(list))
    lam_trace = []
    kpick = defaultdict(lambda: defaultdict(int))
    for C in sorted(cells_by_close):
        rows = cells_by_close[C]
        for iid, c in rows:
            es = estimates(c, fit, iid, lam_full)
            sg = c["sigma"]
            z = (c["p0"] - c["mk"][KFIX]) / sg
            zb = zbucket(z)
            for name in EST_ORDER:
                e = (c["target"] - es[name]) / sg
                tot[name].add(e)
                by_r[name][c["r"]].add(e)
                by_z[name][zb].add(e)
                by_rz[name][(c["r"], zb)].add(e)
                per_close_sq[name][C].append(e * e)
            kb = fit.best_k_shrink(c["r"])
            km = fit.best_k_mean(c["r"])
            kpick["shrink_ksel"][kb] += 1
            kpick["mean_ksel"][km] += 1
        lm = fit.lam(9, KFIX)
        if lm is not None:
            lam_trace.append((C, lm))
        for iid, c in rows:
            fit.absorb_cell(c)
        for iid in IDX_IDS:
            fit.absorb_acf(iid, ticks[iid], base, C)

    print("\n  WALK-FORWARD FIT STATE AT THE END OF THE SAMPLE")
    print("    cells priced with a fitted lam: %d;  with the lam=1 fallback "
          "(not enough earlier data): %d" % (fit.used, fit.fallbacks))
    print("    %-6s %8s %8s %8s %8s %10s" % ("r", "lam k=2", "lam k=3",
                                             "lam k=5", "lam k=10", "n fitted"))
    for r in sorted(set(t - 1 for t in taus)):
        vals = []
        for k in KS:
            lm = fit.lam(r, k)
            vals.append("%8.3f" % lm if lm is not None else "      --")
        print("    %-6d %s %10d" % (r, " ".join(vals), fit.nfit[(r, KFIX)]))
    print("    AR(1) phi of 1-second increments, per index (fitted on all "
          "closes before the last one):")
    for iid in IDX_IDS:
        ph = fit.phi(iid)
        if ph is not None:
            print("      %-14s phi = %+.4f   (n = %d increments)"
                  % (iid, ph, fit.ac_n[iid]))

    print("\n  ESTIMATOR ERROR, ALL CELLS POOLED  (units: index sigma)")
    print("    error = mean(actual remaining prints) - estimate")
    print("    %-14s %10s %11s %10s %9s" % ("estimator", "n", "bias", "RMSE",
                                            "vs spot"))
    base_rmse = tot["spot"].rmse
    for name in EST_ORDER:
        A = tot[name]
        d = 100.0 * (A.rmse - base_rmse) / base_rmse
        print("    %-14s %10d %+11.5f %10.5f %+8.2f%%"
              % (name, A.n, A.bias, A.rmse, d))

    print("\n  PAIRED vs spot, CLUSTERED ON CLOSE  (mean squared error per")
    print("  close, differenced against spot, t across closes)")
    print("    %-14s %8s %12s %9s" % ("estimator", "closes", "dMSE", "t"))
    cl = sorted(per_close_sq["spot"])
    for name in EST_ORDER:
        if name == "spot":
            continue
        ds = []
        for C in cl:
            a1 = per_close_sq["spot"][C]
            a2 = per_close_sq[name][C]
            if len(a1) != len(a2) or not a1:
                continue
            ds.append(sum(a2) / len(a2) - sum(a1) / len(a1))
        print("    %-14s %8d %+12.6f %+9.2f"
              % (name, len(ds), sum(ds) / len(ds) if ds else float("nan"),
                 tstat(ds)))

    print("\n  RMSE BY r  (r = tau-1 = prints still unpublished)")
    hdr = "    %-4s %8s" % ("r", "n")
    for name in EST_ORDER:
        if name.startswith("LEAK"):
            continue
        hdr += " %10s" % name[:10]
    hdr += " %10s" % "rw pred"
    print(hdr)
    for r in sorted(by_r["spot"]):
        line = "    %-4d %8d" % (r, by_r["spot"][r].n)
        for name in EST_ORDER:
            if name.startswith("LEAK"):
                continue
            line += " %10.4f" % by_r[name][r].rmse
        pred = math.sqrt((r + 1) * (2 * r + 1) / (6.0 * r))
        line += " %10.4f" % pred
        print(line)
    print("    'rw pred' is the RMSE a pure random walk implies for spot:")
    print("    sqrt((r+1)(2r+1)/6r).  spot matching it means the walk model")
    print("    is right; spot ABOVE it means the tick carries extra noise.")

    print("\n  THE KEY QUESTION -- RMSE BY HOW FAR SPOT IS FROM ITS OWN")
    print("  TRAILING 5-SECOND MEAN, z = (spot - mean5)/sigma")
    hdr = "    %-12s %9s" % ("z bucket", "n")
    for name in ("spot", "mean3", "mean5", "shrink", "shrink_ksel", "ar1"):
        hdr += " %11s" % name
    print(hdr + " %11s" % "shrink gain")
    for zb in range(4):
        A = by_z["spot"][zb]
        if not A.n:
            continue
        line = "    %-12s %9d" % (ZLAB[zb], A.n)
        for name in ("spot", "mean3", "mean5", "shrink", "shrink_ksel", "ar1"):
            line += " %11.4f" % by_z[name][zb].rmse
        g = 100.0 * (by_z["shrink"][zb].rmse - A.rmse) / A.rmse
        print(line + " %10.2f%%" % g)

    print("\n  BIAS BY z BUCKET  (is spot systematically extrapolating?)")
    print("    %-12s %9s %11s %11s %11s"
          % ("z bucket", "n", "spot bias", "mean5 bias", "shrink bias"))
    for zb in range(4):
        A = by_z["spot"][zb]
        if not A.n:
            continue
        print("    %-12s %9d %+11.5f %+11.5f %+11.5f"
              % (ZLAB[zb], A.n, A.bias, by_z["mean5"][zb].bias,
                 by_z["shrink"][zb].bias))

    print("\n  JOINT r x z: RMSE change vs spot, in %.  Negative = the")
    print("  estimator beats spot in that cell.  If smoothing helped when")
    print("  spot is a transient, the right-hand column would go negative.")
    for nm in ("mean3", "mean5", "shrink", "ar1"):
        print("    %s" % nm)
        line = "      %-5s" % "r"
        for zb in range(4):
            line += " %13s" % ZLAB[zb]
        print(line + " %9s" % "n(|z|>=2)")
        for r in sorted(by_r["spot"]):
            line = "      %-5d" % r
            for zb in range(4):
                A = by_rz["spot"][(r, zb)]
                B = by_rz[nm][(r, zb)]
                if A.n < 30:
                    line += " %13s" % "--"
                else:
                    line += " %+12.2f%%" % (100.0 * (B.rmse - A.rmse) / A.rmse)
            print(line + " %9d" % by_rz["spot"][(r, 3)].n)

    print("\n  k CHOSEN WALK-FORWARD (how often each length won)")
    for nm in ("mean_ksel", "shrink_ksel"):
        print("    %-12s %s" % (nm, ", ".join(
            "k=%s:%d" % (k, v) for k, v in sorted(
                kpick[nm].items(), key=lambda x: (x[0] is None, x[0])))))

    print("\n  LEAK CHECK -- what a peeking harness would have reported")
    print("    LEAK_oracle  RMSE %.6f  (must be ~0; it is the true answer)"
          % tot["LEAK_oracle"].rmse)
    print("    LEAK_lamfull RMSE %.6f  vs walk-forward shrink %.6f"
          % (tot["LEAK_lamfull"].rmse, tot["shrink"].rmse))
    print("    walk-forward lam(r=9,k=5) drifted %s"
          % (", ".join("%.3f" % v for _, v in lam_trace[::max(1, len(lam_trace)//6)])
             if lam_trace else "n/a"))
    print("    full-sample lam(r=9,k=5) = %.3f"
          % lam_full.get((9, KFIX), float("nan")))
    return dict(meta=meta, tot=tot, by_r=by_r, by_z=by_z, fit=fit,
                cells_by_close=cells_by_close, ticks=ticks, base=base,
                avg60=avg60, lam_full=lam_full, taus=taus)


if __name__ == "__main__":
    main()
