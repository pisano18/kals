#!/usr/bin/env python3
# VERSION: 2026-08-25-pw1
"""
power.py -- given the data that EXISTS, what could we have detected?

    python research/power.py --selftest
    python research/power.py --hours 72 --settled-days 30
    python research/power.py --hours 72 --settled-days 30 --alpha 0.01

WHY THIS EXISTS

Every other tool here asks "is there an edge?" and answers with a t-statistic.
That is only half a result. A t of 1.4 means one of two completely different
things:

    (a) there is no edge, or
    (b) there is an edge and we do not have enough data to see it.

Nothing in this repository could tell those apart, so every null result in
RESULTS.md has been unreadable. This file computes the MINIMUM DETECTABLE
EFFECT: the smallest true effect that this much data would find, at the stated
significance, four times out of five. Below that line "we found nothing" is not
evidence of anything.

It matters here more than usual because of one number. The twelve crypto series
close SIMULTANEOUSLY. A day of recording is not 1,152 independent markets; it is
96 close times, and everything inside one close time is ~0.8 correlated. The
independent unit is the CLOSE TIME, and there are four per hour. A week of
recording is 672 of them. That is a small sample, and it is small no matter how
many rows the loaders report.

HOW THE NUMBERS ARE PRODUCED

Not from a formula that could be wrong in a way nobody notices. Each estimator
is SIMULATED under its own null a few thousand times to get its true standard
error at the given n; the MDE follows from that. Then --selftest plants an
effect of exactly the computed MDE and checks the estimator actually fires at
the target rate. If the arithmetic were wrong, the planted-effect power would
not come back at 80% and the self-test fails.

MULTIPLE TESTING

go.py emits several hundred t-statistics in one run. At alpha=0.05 that is a
dozen or more "findings" expected from noise alone. The last section counts
them and prints the corrected thresholds. A result that clears 3.0 unadjusted
and not the corrected line is not a lead; it is the arithmetic working.
"""

import argparse
import math
import os
import random
import sys
from statistics import NormalDist, mean, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tdist import student_t_cdf, student_t_ppf, p_two_sided   # noqa: E402,F401

ND = NormalDist()

WINDOWS_PER_HOUR = 4          # 15-minute markets
WINDOWS_PER_DAY = 96


def fee(p):
    """Kalshi quadratic taker fee, large-order limit."""
    return 0.07 * p * (1 - p)


def crit_for(fn, alpha, **kw):
    """The critical value an estimator's t should be compared against.

    Everything here is a z EXCEPT the block-bootstrap slope, whose standard
    error is built from a handful of blocks.
    """
    if fn is est_lagbeta:
        blocks = kw.get("blocks", 20)
        return student_t_ppf(1 - alpha / 2.0, max(blocks - 1, 1))
    return ND.inv_cdf(1 - alpha / 2.0)


def eff_units(n_series, rho):
    """Effective independent count for n equicorrelated series.

    Var(mean of n) = (1 + (n-1)rho)/n * Var(one), so averaging them is worth
    n/(1+(n-1)rho) independent draws -- 1.22 for twelve series at rho=0.8.
    """
    if n_series <= 1:
        return 1.0
    return n_series / (1.0 + (n_series - 1) * rho)


# ===========================================================================
# The estimators, each as (null generator, effect injector).
#
# Every one returns a single scalar statistic computed exactly the way the
# corresponding tool computes it, so the standard error measured here is the
# standard error that tool actually has -- not an idealised one.
# ===========================================================================
def est_pnl(n_clusters, effect, rnd, price=0.95, per_cluster=3, n_series=12,
            rho=0.8):
    """replay.py / engine.py: mean net P&L per contract, clustered by close.

    `effect` is the true edge in probability terms: the contract wins with
    probability price+effect while costing price. Trades inside one close time
    share the common crypto move, which is what makes twelve series worth 1.22.
    """
    q = price
    f = fee(q)
    per = []
    a, b = math.sqrt(rho), math.sqrt(max(1 - rho, 0.0))
    for _ in range(n_clusters):
        # A Gaussian copula, not a mixture of uniforms. rho*U1 + (1-rho)*U2 is
        # trapezoidal, not uniform, so P(u < 0.95) is not 0.95 and the win rate
        # comes out wrong -- which showed up as a null that rejected 999 times
        # out of 1000 at every sample size.
        common = rnd.gauss(0, 1)
        vals = []
        for _ in range(per_cluster):
            u = ND.cdf(a * common + b * rnd.gauss(0, 1))
            win = 1.0 if u < (q + effect) else 0.0
            vals.append((1 - q) * win - q * (1 - win) - f)
        per.append(mean(vals))
    m, sd = mean(per), pstdev(per)
    se = sd / math.sqrt(len(per)) if sd > 0 else float("inf")
    # A no-edge strategy does not break even -- it loses the fee, exactly.
    # Testing mean P&L against ZERO therefore rejects with certainty at any
    # sample size, which is a true statement about fees and no statement at
    # all about edge. The null value is -f, and an edge of e in probability
    # is worth e dollars per contract, so the statistic below is in the same
    # units as the edge that produced it.
    null_mean = -f
    return m - null_mean, ((m - null_mean) / se if se > 0 else 0.0)


def est_brier(n_clusters, effect, rnd, price=0.95, per_cluster=12,
              model_noise=0.005):
    """edge.py: clustered mean of (market Brier - model Brier).

    `effect` is the MARKET's bias: it quotes truth+effect. Our model quotes
    truth plus its own estimation error, `model_noise` -- because the model has
    one free parameter, sigma, and d(fair)/d(log sigma) peaks at 0.242, so a
    2% error in sigma is worth about half a cent of price wherever it bites.

    The expectation is (market bias)^2 - (model noise)^2. That is the single
    most important line in this file: the model does not beat the market by
    being right, it beats it by being MORE right, and its own noise is a floor
    that no amount of data lowers. A market bias smaller than our sigma error
    is undetectable in principle, not just in this sample.

    Note the effect enters SQUARED, so the MDE cannot be scaled from the null
    standard error the way a linear one can -- which is why mde() below solves
    numerically instead of multiplying.
    """
    per = []
    for _ in range(n_clusters):
        vals = []
        for _ in range(per_cluster):
            truth = min(max(price + rnd.gauss(0, 0.02), 0.02), 0.98)
            q = min(max(truth + effect, 0.001), 0.999)
            m_hat = min(max(truth + rnd.gauss(0, model_noise), 0.001), 0.999)
            y = 1.0 if rnd.random() < truth else 0.0
            vals.append((q - y) ** 2 - (m_hat - y) ** 2)
        per.append(mean(vals))
    m, sd = mean(per), pstdev(per)
    se = sd / math.sqrt(len(per)) if sd > 0 else float("inf")
    # Under the null the market is unbiased and our model still carries its own
    # noise, so the expected difference is NOT zero -- it is minus that noise
    # squared, and the model genuinely loses. Testing against zero rejects on
    # the wrong side. This is what placebo.py's outcome-redraw null measures on
    # real data; here the generator knows it exactly.
    null_val = -(model_noise ** 2)
    return m - null_val, ((m - null_val) / se if se > 0 else 0.0)


def est_uprate(n_markets, effect, rnd):
    """chain.py: is the settled up-rate 0.5? effect is the deviation."""
    p = 0.5 + effect
    k = sum(1 for _ in range(n_markets) if rnd.random() < p)
    ph = k / n_markets
    se = math.sqrt(0.25 / n_markets)
    return ph - 0.5, (ph - 0.5) / se


def est_autocorr(n_pairs, effect, rnd):
    """chain.py: lag-1 autocorrelation of window returns. effect is rho."""
    n = n_pairs + 1
    x, prev = [], rnd.gauss(0, 1)
    for _ in range(n):
        v = effect * prev + math.sqrt(max(1 - effect ** 2, 0.0)) * rnd.gauss(0, 1)
        x.append(v)
        prev = v
    m = mean(x)
    den = sum((v - m) ** 2 for v in x)
    if den <= 0:
        return 0.0, 0.0
    num = sum((x[i] - m) * (x[i + 1] - m) for i in range(n - 1))
    r = num / den
    return r, r * math.sqrt(n - 1)


def est_lagbeta(n_seconds, effect, rnd, blocks=20, noise=1.0, ar=0.6,
                ar_x=0.6, iid_se=False):
    """feeds.py / leadlag.py: regression slope with a BLOCK-bootstrap SE.

    BOTH the regressor and the residual are AR(1), and both have to be.

    An earlier version made only the residual persistent and asserted the iid
    standard error would then be too small. It is not, and the self-test said
    so: with an INDEPENDENT iid regressor, E[dx_t e_t dx_s e_s] factors to
    E[dx_t dx_s] E[e_t e_s] = 0 for t != s, so the score dx*e is serially
    uncorrelated no matter what the residual does and the iid formula is
    exactly right. What breaks it is persistence in the REGRESSOR -- and index
    increments and book-imbalance both have it, which is precisely why
    feeds.py and leadlag.py block-bootstrap in the first place.

    Pass iid_se=True to see the cost of getting that wrong.
    """
    per_blk = max(n_seconds // blocks, 5)
    betas, all_num, all_den, resid = [], 0.0, 0.0, []
    e_prev = rnd.gauss(0, noise)
    x_prev = rnd.gauss(0, 1)
    sd_inn = noise * math.sqrt(max(1 - ar * ar, 1e-9))
    sd_x = math.sqrt(max(1 - ar_x * ar_x, 1e-9))
    for _ in range(blocks):
        num = den = 0.0
        for _ in range(per_blk):
            x_prev = ar_x * x_prev + rnd.gauss(0, sd_x)
            dx = x_prev
            e_prev = ar * e_prev + rnd.gauss(0, sd_inn)
            dy = effect * dx + e_prev
            num += dx * dy
            den += dx * dx
            resid.append((dx, dy))
        all_num += num
        all_den += den
        if den > 0:
            betas.append(num / den)
    if all_den <= 0 or len(betas) < 3:
        return 0.0, 0.0
    beta = all_num / all_den
    if iid_se:
        n = len(resid)
        rss = sum((dy - beta * dx) ** 2 for dx, dy in resid)
        se = math.sqrt(rss / max(n - 1, 1) / all_den)
    else:
        sd = pstdev(betas)
        se = sd / math.sqrt(len(betas)) if sd > 0 else float("inf")
    return beta, (beta / se if se > 0 else 0.0)


ESTIMATORS = [
    ("replay net P&L / contract", "close-time clusters", est_pnl, "cents",
     "the decision metric: would this have made money"),
    ("edge.py Brier advantage", "close-time clusters", est_brier, "prob",
     "model vs market, the statistical test"),
    ("chain.py up-rate deviation", "settled markets", est_uprate, "prob",
     "is the coin fair"),
    ("chain.py lag-1 autocorr", "consecutive pairs", est_autocorr, "rho",
     "does window N predict N+1"),
    ("feeds.py lead-lag beta", "seconds of overlap", est_lagbeta, "beta",
     "does the book follow the index"),
]


# ===========================================================================
def mde(fn, n, alpha=0.05, power=0.80, reps=800, seed=1, hi=None,
        return_curve=False, pw_reps=None, **kw):
    """Smallest effect this estimator finds `power` of the time at `alpha`.

    Solved, not multiplied. The obvious shortcut -- MDE = (z_a + z_p) * SE --
    makes two assumptions that are both false here.

      1. That the statistic's expectation is LINEAR in the effect. For
         edge.py's Brier difference it is quadratic: bias^2 minus model
         noise^2, with a floor no sample size reaches.
      2. That its VARIANCE does not depend on the effect. The P&L variance
         FALLS as the edge grows -- a winning bet loses less often -- and the
         Brier variance RISES. Ignoring that lands the power ten points out,
         in opposite directions for the two.

    So both curves are measured from the same three probes: the mean curve
    a*e + b*e^2 and the variance ratio g(e) = sd(e)/sd(0), then
    a*e + b*e^2 = (z_a + z_p) * sd(0) * g(e) is solved numerically. Modelling
    g separately is also what makes extrapolation to a larger n honest: sd(0)
    scales as 1/sqrt(n) and g does not scale at all, whereas folding them
    together carried a large-effect variance reduction into a regime where the
    effect is small and read 15% optimistic.

    Returns (mde, se_null, t_crit), or with return_curve a dict as well.
    """
    rnd = random.Random(seed)
    zc = crit_for(fn, alpha, **kw)
    zp = ND.inv_cdf(power)
    probe_reps = max(reps // 3, 120)

    def _bail(se_):
        curve = {"a": 1.0, "b": 0.0, "c1": 0.0, "c2": 0.0, "se0": se_,
                 "zc": zc, "cal": 1.0, "n": n}
        return ((float("inf"), se_, zc, curve) if return_curve
                else (float("inf"), se_, zc))

    def probe(e, r_reps, seed_off):
        r = random.Random(seed + seed_off)
        v = [fn(n, e, r, **kw)[0] for _ in range(r_reps)]
        return mean(v), pstdev(v)

    m0, se0 = probe(0.0, reps, 0)
    if se0 <= 0:
        return _bail(se0)
    K = (zc + zp) * se0

    h = hi if hi is not None else max(K, 1e-9)
    for _ in range(30):
        m1, s1 = probe(h, probe_reps, 977)
        m2, s2 = probe(2 * h, probe_reps, 977)
        if (m2 - m0) >= K:
            break
        h *= 2.0
        if h > 1e6:
            return _bail(se0)
    else:
        return _bail(se0)

    y1, y2 = m1 - m0, m2 - m0
    b = (y2 - 2 * y1) / (2 * h * h)
    a = (y1 - b * h * h) / h
    # Keep the quadratic term ONLY where it is doing real work. Fitting b to
    # two noisy probes on a genuinely linear estimator gives a coefficient
    # that swings from -9 to -0.3 across sample sizes, and that spurious
    # curvature is optimism, which is the dangerous direction. The Brier
    # statistic really is quadratic (a ~ 0, b ~ 1) and sails through.
    if abs(b * h * h) < 0.25 * abs(a * h):
        b = 0.0
        a = ((y1 / h) + (y2 / (2 * h))) / 2.0

    g1, g2 = s1 / se0, s2 / se0
    c2 = (g2 - 2 * g1 + 1.0) / (2 * h * h)
    c1 = (g1 - 1.0 - c2 * h * h) / h

    curve = {"a": a, "b": b, "c1": c1, "c2": c2, "se0": se0, "zc": zc,
             "cal": 1.0, "n": n}
    e = _solve_curve(curve, K)
    if e == float("inf"):
        return _bail(se0)

    # Even with both curves right, this is still normal theory and these
    # statistics are skewed. Finish by MEASURING the power at the analytic
    # answer and rescaling: p_hat implies an achieved z of inv_cdf(p_hat) + zc,
    # and for a locally linear curve the effect scales by the ratio of the
    # wanted z to the achieved one. --selftest checks the result by planting
    # it, so this cannot quietly stop working.
    pw_reps = pw_reps or max(reps, 350)
    # Stop when the measured power is within its OWN sampling error of the
    # target. A fixed 0.02 band at 200 replications is inside the noise, so
    # the loop exits on a lucky draw and the answer comes back a few points low.
    tol = max(0.02, math.sqrt(power * (1 - power) / pw_reps))
    e0 = e
    for _ in range(3):
        p_hat = measured_power(fn, n, e, alpha, reps=pw_reps,
                               seed=seed + 6100, **kw)
        if abs(p_hat - power) <= tol:
            break
        p_hat = min(max(p_hat, 1e-4), 1 - 1e-4)
        z_now = ND.inv_cdf(p_hat) + zc
        z_want = zp + zc
        if z_now <= 0.05:
            e *= 2.0
            continue
        e *= z_want / z_now
    curve["cal"] = (e / e0) if e0 > 0 else 1.0
    if return_curve:
        return e, se0, zc, curve
    return e, se0, zc


def _solve_curve(curve, K):
    """Smallest e > 0 with a*e + b*e^2 = K * (1 + c1*e + c2*e^2).

    Bisection rather than the quadratic formula: both sides are closed form,
    so this costs nothing, and it does not care how the coefficients came out.
    """
    a, b, c1, c2 = curve["a"], curve["b"], curve["c1"], curve["c2"]

    def f(e):
        return (a * e + b * e * e) - K * (1.0 + c1 * e + c2 * e * e)

    if f(0.0) >= 0:
        return 0.0
    lo, hi = 0.0, max(K, 1e-12)
    for _ in range(60):
        if f(hi) >= 0:
            break
        hi *= 2.0
        if hi > 1e9:
            return float("inf")
    else:
        return float("inf")
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if f(mid) >= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0


def mde_scaled(fn, n_target, alpha=0.05, power=0.80, reps=400, seed=1,
               n_cap=3000, n_sim_force=None, curve=None, pw_reps=None, **kw):
    """MDE at n_target, simulated at min(n_target, n_cap) and extrapolated.

    Every statistic here is a sample mean, so sd(0) falls as 1/sqrt(n) --
    checked in --selftest, where four times the data halves each linear MDE.
    The mean curve and the variance-ratio curve are properties of the
    estimator's shape, not of n, so they are measured once and reused.
    Simulating a quarter of a million seconds of feed outright would take
    hours. Returns (mde, n_simulated).
    """
    n_sim = int(n_sim_force) if n_sim_force else int(min(n_target, n_cap))
    if n_sim < 30:
        return float("inf"), n_sim
    if curve is None:
        _m, _se, _zc, curve = mde(fn, n_sim, alpha, power, reps=reps,
                                  seed=seed, return_curve=True,
                                  pw_reps=pw_reps, **kw)
    if n_sim == n_target:
        e = _solve_curve(curve, (curve["zc"] + ND.inv_cdf(power))
                         * curve["se0"])
        return (e * curve["cal"] if e != float("inf") else e), n_sim
    se_t = curve["se0"] * math.sqrt(n_sim / float(n_target))
    e = _solve_curve(curve, (curve["zc"] + ND.inv_cdf(power)) * se_t)
    return (e * curve["cal"] if e != float("inf") else e), n_sim


def measured_power(fn, n, effect, alpha=0.05, reps=2000, seed=2, **kw):
    """Fraction of runs where a planted effect actually clears the bar."""
    rnd = random.Random(seed)
    zc = crit_for(fn, alpha, **kw)
    hits = sum(1 for _ in range(reps)
               if abs(fn(n, effect, rnd, **kw)[1]) > zc)
    return hits / reps


# ===========================================================================
# how many tests does a full go.py run actually emit?
# ===========================================================================
# Hand-counted from each stage's output tables, and deliberately on the low
# side -- every bucket, lag and horizon a stage prints a t for is a chance to
# be wrong, and undercounting them makes the corrected threshold too LENIENT.
# If you add a stage or a breakdown, add it here; a stale count here is a
# quietly wrong threshold everywhere else.
TEST_COUNTS = [
    # (stage, tests per series or per run, per_series?)
    ("chain     gate + sigma + clustering + autocorr + tails + hour", 8, True),
    ("volmodel  lambda, dLL, two tail profiles", 4, True),
    ("edge      logloss/Brier/PnL at each of 3 ttc bands", 9, False),
    ("cross     one residual test per series, plus the pooled one", 2, True),
    ("replay    P&L, hit rate, and their nulls", 4, False),
    ("leadlag   one beta per lag on the tested grid", 13, False),
    ("openwindow strike gate + edge profile buckets", 6, False),
    ("implied   level, term tilt, smile, per-series", 3, True),
    ("pathstats price/velocity/roundness splits x 3 horizons", 27, False),
    ("proxy     one residual regression per candidate reference", 6, False),
    ("feeds     lag profile + imbalance horizons", 16, False),
    ("book      depth by price bucket", 9, False),
]


def testing_report(n_series, alpha):
    print("\n" + "=" * 78)
    print("MULTIPLE TESTING -- how many chances does one run get?")
    print("=" * 78)
    total = 0
    print(f"  {'stage':>62}{'tests':>8}")
    for label, k, per_series in TEST_COUNTS:
        n = k * n_series if per_series else k
        total += n
        print(f"  {label:>62}{n:>8}")
    print(f"  {'':>62}{'-'*8:>8}")
    print(f"  {'TOTAL statistics in one go.py run':>62}{total:>8}")

    exp_false = total * alpha
    bonf = alpha / total
    sidak = 1 - (1 - alpha) ** (1.0 / total)
    print(f"\n  At alpha={alpha}, {exp_false:.0f} of those are expected to fire "
          f"on pure noise.")
    print(f"  {'threshold':>28}{'alpha':>12}{'|t| needed':>14}")
    for name, a in (("unadjusted", alpha),
                    ("Bonferroni", bonf),
                    ("Sidak", sidak)):
        print(f"  {name:>28}{a:>12.2e}{ND.inv_cdf(1 - a/2):>14.2f}")
    print(f"\n  Benjamini-Hochberg is the right tool when several results are")
    print(f"  expected to be real, and it is not a fixed threshold: sort the")
    print(f"  {total} p-values ascending and keep the largest i with")
    print(f"  p_(i) <= i * {alpha} / {total}.")
    print("\n  THE PRACTICAL RULE. One |t| of 3.1 out of "
          f"{total} tests is noise.")
    print(f"  Treat |t| < {ND.inv_cdf(1 - bonf/2):.1f} as a lead to re-measure "
          "on fresh data, never as a")
    print("  finding -- and re-measuring on fresh data is stronger than any "
          "correction.")
    return total


# ===========================================================================
def selftest(quick=False):
    """quick=True halves every replication count. go.py runs it that way --
    a full pass is seven and a half minutes and this file touches no data, so
    paying that on every run would just discourage running go.py at all. The
    tolerances still hold at 3 sigma on the reduced counts."""
    q = 0.45 if quick else 1.0

    def R(n):
        return max(int(n * q), 60)

    print("=" * 78)
    print("SELF-TEST -- does a planted effect of exactly the MDE actually fire?")
    print("=" * 78)
    print("  If the MDE arithmetic were wrong, the measured power at that")
    print("  effect would not come back near the target. Every estimator is")
    print("  checked in both directions: the null must fire at alpha, and the")
    print("  planted MDE must fire at the requested power. This takes a few")
    print("  minutes -- it is thousands of simulated runs of each estimator.\n")
    fails = []
    ALPHA, POWER = 0.05, 0.80

    print("  Student-t quantiles vs published tables (the block bootstrap")
    print("  needs them; stdlib has no t distribution):")
    print(f"  {'quantile':>16}{'computed':>12}{'published':>12}")
    for (pq, df, want) in ((0.975, 1, 12.7062), (0.975, 19, 2.0930),
                           (0.995, 5, 4.0321), (0.95, 30, 1.6973),
                           (0.975, 120, 1.9799)):
        got = student_t_ppf(pq, df)
        print(f"  {'t(%d) @ %.3f' % (df, pq):>16}{got:>12.4f}{want:>12.4f}")
        if abs(got - want) > 5e-4:
            fails.append(f"t({df}) @ {pq} = {got:.4f}, published {want}")
    print()
    print(f"  {'estimator':>28}{'n':>9}{'MDE':>12}{'power@MDE':>11}"
          f"{'null rate':>11}")
    N = (lambda v: max(int(v * (0.5 if quick else 1.0)), 120))
    cases = [
        # not shrunk in quick mode: below ~300 clusters the per-cluster
        # P&L is skewed enough that a normal critical value over-rejects,
        # which the section further down measures rather than hides
        ("replay net P&L / contract", est_pnl, 300, {}, True),
        ("edge.py Brier advantage", est_brier, N(300), {"per_cluster": 4},
         False),
        ("chain.py up-rate deviation", est_uprate, N(3000), {}, True),
        ("chain.py lag-1 autocorr", est_autocorr, N(2000), {}, True),
        ("feeds.py lead-lag beta", est_lagbeta, N(4000), {}, True),
    ]
    for label, fn, n, kw, linear in cases:
        m, se, _ = mde(fn, n, ALPHA, POWER, reps=R(250), seed=11,
                       pw_reps=R(350), **kw)
        pw = measured_power(fn, n, m, ALPHA, reps=R(900), seed=99, **kw)
        nl = measured_power(fn, n, 0.0, ALPHA, reps=R(900), seed=13, **kw)
        flag = ""
        if abs(pw - POWER) > (0.09 if quick else 0.06):
            flag = " <-- power off"
            fails.append(f"{label}: planted the MDE and measured power "
                         f"{pw:.2f}, wanted {POWER:.2f}")
        if abs(nl - ALPHA) > 0.03:
            flag = " <-- size off"
            fails.append(f"{label}: null fires at {nl:.3f}, wanted {ALPHA}")
        print(f"  {label:>28}{n:>9,}{m:>12.5f}{pw:>11.2f}{nl:>11.3f}{flag}")

    print("\n  SKEW AT SMALL CLUSTER COUNTS -- replay's t is anti-conservative")
    print("  The per-cluster net P&L is a handful of binary payoffs at a price")
    print("  near 95c: mostly small wins, occasionally a 95c loss. Averaging a")
    print("  few dozen of those does not give you a normal, so comparing the")
    print("  t to 1.96 rejects a TRUE null more often than 5% -- and a day of")
    print("  recording is 96 clusters. Not a bug to fix here; a number to know")
    print("  before reading a P&L t-statistic off a short recording.")
    print(f"\n  {'clusters':>12}{'null rejection rate at alpha=0.05':>36}")
    prev = None
    for nc in (60, 150, 300, 600, 1200):
        r = measured_power(est_pnl, nc, 0.0, ALPHA, reps=R(900), seed=71)
        print(f"  {nc:>12,}{r:>36.3f}")
        if nc >= 300 and abs(r - ALPHA) > 0.03:
            fails.append(f"P&L null fires at {r:.3f} with {nc} clusters -- "
                         "the skew should have washed out by here")
        prev = r
    if prev is None or prev > 0.08:
        fails.append("the P&L null never settled toward alpha as clusters grew")

    print("\n  SQRT(n) SCALING -- four times the data must halve a LINEAR MDE")
    print(f"  {'estimator':>28}{'MDE(n)':>12}{'MDE(4n)':>12}{'ratio':>9}"
          f"{'want':>8}")
    for label, fn, n, kw, linear in cases:
        if not linear:
            continue
        a, _, _ = mde(fn, n, ALPHA, POWER, reps=R(200), seed=21,
                      pw_reps=R(350), **kw)
        b, _, _ = mde(fn, 4 * n, ALPHA, POWER, reps=R(200), seed=21,
                      pw_reps=R(350), **kw)
        ratio = b / a if a > 0 else float("nan")
        bad = ""
        if not (0.40 < ratio < 0.62):
            bad = " <--"
            fails.append(f"{label}: MDE scaled by {ratio:.2f} for 4x the data, "
                         "expected ~0.50 -- the n-model does not hold")
        print(f"  {label:>28}{a:>12.5f}{b:>12.5f}{ratio:>9.3f}{0.5:>8.2f}{bad}")

    print("\n  EXTRAPOLATION -- simulating at n_cap and scaling must match")
    print("  main() cannot simulate a quarter of a million seconds of feed, so")
    print("  it simulates n_cap and scales the standard error by sqrt(n). If")
    print("  that shortcut were wrong every number in the report would be too.")
    print(f"\n  {'estimator':>28}{'direct':>12}{'scaled':>12}{'ratio':>9}")
    print("  Both directions. Extrapolating used to read 15% optimistic at")
    print("  8x up and 23% pessimistic at 6x down, because the effect-dependent")
    print("  variance was folded into the standard error instead of modelled.")
    print("  These rows are what caught that.")
    for label, fn, n, cap, kw in (
            ("up-rate, 4x up", est_uprate, 8000, 2000, {}),
            ("lag-1 autocorr, 4x up", est_autocorr, 8000, 2000, {}),
            ("net P&L, 4x up", est_pnl, 1200, 300, {}),
            ("net P&L, 8x up", est_pnl, 2400, 300, {}),
            ("net P&L, 6x DOWN", est_pnl, 250, 1500, {}),
            ("up-rate, 8x DOWN", est_uprate, 500, 4000, {})):
        direct, _, _ = mde(fn, n, ALPHA, POWER, reps=R(200), seed=5,
                           pw_reps=R(350), **kw)
        # force the simulation size so a DOWN row really extrapolates down
        # instead of quietly simulating the target directly, which is what an
        # earlier version did -- both DOWN rows read exactly 1.000, which
        # should have been the giveaway.
        scaled, nsim = mde_scaled(fn, n, ALPHA, POWER, reps=R(200), seed=5,
                                  n_sim_force=cap, pw_reps=R(350), **kw)
        ratio = scaled / direct if direct > 0 else float("nan")
        bad = ""
        # both sides of the ratio are simulated, so the band has to widen when
        # the replication counts are cut
        band = 0.14 if quick else 0.09
        if not (1 - band < ratio < 1 + band):
            bad = " <--"
            fails.append(f"{label}: extrapolated MDE is {ratio:.2f}x the "
                         "directly simulated one")
        print(f"  {label:>28}{direct:>12.5f}{scaled:>12.5f}{ratio:>9.3f}{bad}")

    print("\n  THE MODEL-NOISE FLOOR -- the one MDE that data cannot lower")
    print("  edge.py compares OUR probability to the market's. Its expectation")
    print("  is (market bias)^2 - (our noise)^2, so no sample size lets us")
    print("  detect a bias smaller than our own error. sigma is the only free")
    print("  parameter and d(fair)/d(log sigma) peaks at 0.242, so this floor")
    print("  is set by how well sigma is known -- not by how long we record.")
    print(f"\n  {'our noise':>16}{'n=300':>12}{'n=' + f'{N(2400):,}':>12}"
          f"{'floor':>12}")
    for mn in (0.003, 0.010):
        a, _, _ = mde(est_brier, 300, ALPHA, POWER, reps=R(150), seed=41,
                      pw_reps=R(350), per_cluster=4, model_noise=mn)
        b, _, _ = mde(est_brier, N(2400), ALPHA, POWER, reps=R(150), seed=41,
                      pw_reps=R(350), per_cluster=4, model_noise=mn)
        print(f"  {mn:>16.3f}{a:>12.5f}{b:>12.5f}{mn:>12.3f}")
        if b < mn * 0.9:
            fails.append(f"MDE {b:.5f} fell below the model-noise floor "
                         f"{mn:.3f} -- impossible, the estimator is wrong")
        if b >= a:
            fails.append("16x the data did not lower the Brier MDE at all")

    print("\n  BLOCK BOOTSTRAP -- what it is actually for")
    print("  Regressor AND residual are both AR(1) at 0.6, as index increments")
    print("  and book imbalance both are. Persistence in the REGRESSOR is what")
    print("  breaks the iid standard error: with an iid regressor the score")
    print("  dx*e is serially uncorrelated whatever the residual does, and the")
    print("  iid formula is exactly right. This file asserted the opposite")
    print("  until the line below measured 0.058 and refused to pass.")
    print(f"\n  {'critical value':>34}{'null rejection rate':>22}{'want':>8}")
    rates = {}
    for name, iid, crit in (
            ("iid SE, z=1.96", True, ND.inv_cdf(0.975)),
            ("block SE, z=1.96 (what we did)", False, ND.inv_cdf(0.975)),
            ("block SE, t(19)=2.09 (correct)", False,
             student_t_ppf(0.975, 19))):
        rnd = random.Random(51)
        hits = sum(1 for _ in range(R(900))
                   if abs(est_lagbeta(4000, 0.0, rnd, iid_se=iid)[1]) > crit)
        rates[name] = hits / R(900)
        print(f"  {name:>34}{rates[name]:>22.3f}{ALPHA:>8.2f}")
    if abs(rates["block SE, t(19)=2.09 (correct)"] - ALPHA) > 0.03:
        fails.append("block-bootstrap null with the t critical value fires at "
                     f"{rates['block SE, t(19)=2.09 (correct)']:.3f}, "
                     f"wanted {ALPHA}")
    if rates["iid SE, z=1.96"] <= ALPHA * 1.5:
        fails.append(f"the iid standard error rejected at "
                     f"{rates['iid SE, z=1.96']:.3f} on AR(1) residuals -- it "
                     "should be much worse than alpha, so this test is not "
                     "testing anything")
    if rates["block SE, z=1.96 (what we did)"] <= ALPHA:
        fails.append("using z instead of t on 20 blocks did not over-reject "
                     "-- then the degrees-of-freedom point is wrong")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- every MDE fires at its target power, every")
    print("null fires at alpha, the linear estimators scale as sqrt(n), the")
    print("Brier MDE respects its model-noise floor, and the block bootstrap")
    print("earns its keep on dependent residuals.")
    return True


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=72.0,
                    help="hours of live collector recording on disk")
    ap.add_argument("--settled-days", type=float, default=30.0,
                    help="days of settled history in chain_cache.json")
    ap.add_argument("--series", type=int, default=12)
    ap.add_argument("--rho", type=float, default=0.8)
    ap.add_argument("--price", type=float, default=0.95,
                    help="the entry price the P&L row is computed at")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--power", type=float, default=0.80)
    ap.add_argument("--reps", type=int, default=400)
    ap.add_argument("--cap", type=int, default=3000,
                    help="largest n actually simulated; bigger targets are "
                         "reached by scaling the standard error as 1/sqrt(n)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--quick", action="store_true",
                    help="with --selftest: fewer replications, same checks")
    a = ap.parse_args()

    if a.selftest:
        raise SystemExit(0 if selftest(quick=a.quick) else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed; the numbers below would be wrong")

    clusters = int(a.hours * WINDOWS_PER_HOUR)
    markets = clusters * a.series
    settled = int(a.settled_days * WINDOWS_PER_DAY)
    seconds = int(a.hours * 3600)
    eff = eff_units(a.series, a.rho)

    print("\n\n" + "#" * 78)
    print("# WHAT THIS MUCH DATA COULD DETECT")
    print("#" * 78)
    print(f"\n  {a.hours:.0f} hours recorded, {a.settled_days:.0f} days of "
          f"settled history, {a.series} series at rho={a.rho}")
    print(f"  {'close-time clusters (the independent unit)':>52}"
          f"{clusters:>10,}")
    print(f"  {'markets (NOT the sample size)':>52}{markets:>10,}")
    print(f"  {'effective independent units per cluster':>52}{eff:>10.2f}")
    print(f"  {'settled markets per series':>52}{settled:>10,}")
    print(f"  {'seconds of feed overlap':>52}{seconds:>10,}")

    print("\n" + "=" * 78)
    print(f"MINIMUM DETECTABLE EFFECT  (alpha={a.alpha}, power={a.power:.0%})")
    print("=" * 78)
    print("  Below these lines, a null result means NOTHING was measurable --")
    print("  not that nothing is there. `sim n` is the size actually simulated;")
    print("  larger targets are reached by scaling the standard error as")
    print("  1/sqrt(n), which --selftest checks against a direct run.\n")
    print(f"  {'estimator':<28}{'unit':>19}{'n':>11}{'sim n':>8}"
          f"{'MDE':>11}{'corrected':>12}")

    total_tests = sum(k * a.series if per else k for _, k, per in TEST_COUNTS)
    bonf = a.alpha / total_tests

    ns = {"replay net P&L / contract": clusters,
          "edge.py Brier advantage": clusters,
          "chain.py up-rate deviation": settled,
          "chain.py lag-1 autocorr": max(settled - 1, 0),
          "feeds.py lead-lag beta": seconds}
    kws = {"replay net P&L / contract": {"price": a.price,
                                         "n_series": a.series, "rho": a.rho},
           "edge.py Brier advantage": {"price": a.price,
                                       "per_cluster": a.series}}
    for name, unit_label, fn, unit, why in ESTIMATORS:
        n = ns[name]
        if n < 30:
            print(f"  {name:<28}{unit_label:>19}{n:>11,}"
                  f"{'-- too little data --':>31}")
            continue
        kw = kws.get(name, {})
        m1, nsim = mde_scaled(fn, n, a.alpha, a.power, reps=a.reps, seed=7,
                              n_cap=a.cap, **kw)
        m2, _ = mde_scaled(fn, n, bonf, a.power, reps=a.reps, seed=7,
                           n_cap=a.cap, **kw)
        def fmt(v):
            if v == float("inf"):
                return "unreachable"
            return f"{100*v:.2f}c" if unit == "cents" else f"{v:.5f}"
        f1, f2 = fmt(m1), fmt(m2)
        print(f"  {name:<28}{unit_label:>19}{n:>11,}{nsim:>8,}{f1:>11}{f2:>12}")
        print(f"  {'':<28}{why}")

    print("\n" + "=" * 78)
    print("WHAT MORE RECORDING BUYS")
    print("=" * 78)
    print("  The P&L row is clustered by close time, and close times arrive")
    print("  at 4 an hour no matter how many series you watch. Halving the")
    print("  MDE means quadrupling the DAYS.")
    print("  One simulated curve, rescaled as 1/sqrt(n) in both directions;")
    print("  --selftest checks that against direct runs to within 10%.\n")
    print(f"  {'recording':>12}{'clusters':>11}{'P&L MDE':>11}"
          f"{'corrected':>12}")

    ncur = min(a.cap, 1200)
    kwp = dict(price=a.price, n_series=a.series, rho=a.rho)
    cur_raw = mde(est_pnl, ncur, a.alpha, a.power, reps=a.reps, seed=7,
                  return_curve=True, **kwp)[3]
    cur_cor = mde(est_pnl, ncur, bonf, a.power, reps=a.reps, seed=7,
                  return_curve=True, **kwp)[3]
    for days in (1, 3, 7, 14, 30, 90):
        cl = int(days * 24 * WINDOWS_PER_HOUR)
        p1, _ = mde_scaled(est_pnl, cl, a.alpha, a.power, n_sim_force=ncur,
                           curve=cur_raw, **kwp)
        p2, _ = mde_scaled(est_pnl, cl, bonf, a.power, n_sim_force=ncur,
                           curve=cur_cor, **kwp)

        def cell(v, w):
            # 96 clusters cannot reach the corrected threshold at any effect
            # size; say so rather than printing "infc"
            return (f"{100*v:>{w-1}.2f}c" if v != float("inf")
                    else f"{'unreachable':>{w}}")
        print(f"  {str(days) + ' day' + ('s' if days > 1 else ''):>12}"
              f"{cl:>11,}{cell(p1, 11)}{cell(p2, 12)}")
    print("\n  Read the P&L column against the edge you would actually trade.")
    print("  If the edges on the table are 1c and the MDE at your recording")
    print("  length is 2c, replay CANNOT confirm or refute them, and saying")
    print("  'the backtest found nothing' would be reporting the sample size.")
    print("  The per-second estimators -- leadlag, feeds, proxy, pathstats --")
    print("  do not have this problem: they get 3,600 observations an hour")
    print("  instead of 4, which is the whole reason PLAN_V3 ranks the")
    print("  plumbing questions above the opinion ones.")

    testing_report(a.series, a.alpha)

    print("\n" + "=" * 78)
    print("HOW TO USE THIS")
    print("=" * 78)
    print("  1. Read RESULTS.md next to this table. Any stage whose measured")
    print("     effect is smaller than its MDE has produced no information --")
    print("     positive OR negative. Do not describe it as 'no edge found'.")
    print("  2. The P&L row is the one that decides deployment. If the MDE")
    print("     there is larger than the edge you would trade on, live P&L")
    print("     cannot confirm the strategy in any reasonable time and the")
    print("     decision has to rest on pre-trade measurement instead.")
    print("     viability.py --edge X prices exactly that consequence.")
    print("  3. To halve an MDE, quadruple the clusters. Clusters accrue at")
    print(f"     {WINDOWS_PER_HOUR}/hour and nothing you do to the code changes "
          "that, which")
    print("     is why the recording matters more than the analysis.")
    print("  4. cross.py is the exception: demeaning the close-time cluster")
    print("     removes the common crypto move, which is most of the variance.")
    print("     PLAN_V3 measured 4.8x in variance, i.e. the same MDE from")
    print("     roughly a fifth of the data. That is the cheapest power on")
    print("     the table and the reason to run it first.")


if __name__ == "__main__":
    main()
