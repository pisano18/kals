"""voltiming.py -- can the ONE confirmed finding be turned into money?

The finding: volatility clusters. |r| predicts the next |r|, on 5,195 settled
windows across six coins, surviving five different attacks including dropping
the wildest day. `chain.py` measures it; this file asks the only question that
matters next.

    Knowing what bread costs is not a bargain. It is a bargain only if the
    shop is charging the wrong price.

So: does Kalshi's implied volatility ALREADY respond to recent realised
volatility as much as the truth does? If it does, the finding is worth
nothing. If it under-responds, the gap is money, and this file says how much
and where on the price curve to take it.

WHERE ON THE PRICE CURVE -- and this is the part that surprised me
    Fair value is p = Phi(z), so d(fair)/d(log sigma) = -z*phi(z). That is
    ZERO at the money. A 50c contract carries NO volatility information at
    all: mispricing sigma by any amount whatsoever moves its fair value by
    nothing. Every cent of volatility edge lives away from 50c, peaking at
    |z| = 1 (p = 16c or 84c) at 0.242c per 1.0 log-unit of sigma error.

    The taker fee is 0.07*p*(1-p) -- quadratic, so it is LARGEST at 50c
    (1.75c) and vanishes into the wings. Edge and fee therefore push the same
    way, which is rare and worth exploiting.

    But the wings are choked by the 1c tick and, worse, by model error: at
    large |z| the Gaussian fair value is exactly where a fat-tailed truth
    disagrees with it most, and our own kurtosis measurement says the truth is
    very fat. So the band is bounded on both sides, and part 1 computes it.

THE ESTIMATOR (part 2)
    Two regressions on the same predictor collapse into one. With x = a
    backward-looking log-volatility forecast built only from windows that
    closed BEFORE this market opened,

        slope of  log(sigma_realised / sigma_implied)  on  x   =   d_beta

    is exactly the amount by which the market under-responds. It needs no
    separate estimate of either loading, and its standard error is one number
    rather than a difference of two correlated ones.

    Cents of edge available at the optimal strike:

        edge = 100 * 0.242 * d_beta * E|x - xbar|

    against a hurdle of the fee plus the half-spread you cross. Part 1 prints
    the hurdle; part 2 prints the edge; the comparison is the decision.

NOTHING HERE PLACES AN ORDER.
"""

import argparse
import math
import os
import random
import sys
from statistics import NormalDist, mean, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import var_factor, N_AVG                          # noqa: E402
from tdist import p_two_sided                                  # noqa: E402

ND = NormalDist()

# Kalshi's taker fee on the 15-minute crypto series. Makers pay nothing --
# fee_type is "quadratic", not "quadratic_with_maker_fees", which was checked
# across all sixteen fifteen-minute series.
FEE_K = 0.07

# The tick is TAPERED, not flat. From the API's own price_ranges on a live
# KXBTC15M market:
#
#     0.0000 - 0.1000   step 0.0010   =  0.1c
#     0.1000 - 0.9000   step 0.0100   =  1.0c
#     0.9000 - 1.0000   step 0.0010   =  0.1c
#
# Run 2 measured "a flat 1c spread" and that was right about the liquid
# mid-book and blind to the wings, because nothing quotes there. This file
# previously assumed 0.5c of half-spread EVERYWHERE, which is 10x too high in
# exactly the region every thread in this project points at. The corrected
# break-even sigma error keeps FALLING below 10c instead of turning back up:
# 2.6% at 7c and 1.9% at 2c, against the 4.8-6.4% the flat assumption gave.
TICK_RANGES = ((0.00, 0.10, 0.001), (0.10, 0.90, 0.010), (0.90, 1.00, 0.001))


def tick_cents(p):
    for lo, hi, step in TICK_RANGES:
        if lo <= p < hi:
            return 100.0 * step
    return 100.0 * TICK_RANGES[-1][2]


def half_spread_c(p):
    """Half of the tightest quotable spread at this price.

    A one-tick-wide book is the best case, and the liquid series do quote one
    tick wide. It is a floor on the cost of crossing, not a measurement of
    what is actually resting there -- ZEC quotes 7c and NEAR 8c, and neither
    is tradeable on this basis at any tick.
    """
    return tick_cents(p) / 2.0


HALF_SPREAD_C = 0.5          # kept for the 10c-90c band, where it is correct

# max of |z|*phi(z), at |z| = 1. The ceiling on any sigma-based edge, in cents
# per 1.0 log-unit of sigma error.
MAX_DFAIR_DLOGSIG = 100.0 * 1.0 * ND.pdf(1.0)


# ===========================================================================
# PART 1 -- analytic. Needs no data and cannot be wrong about the market,
# only about the arithmetic, which the self-test checks against brute force.
# ===========================================================================
def dfair_dlogsigma(p):
    """Cents of fair value per 1.0 log-unit of sigma, at price p.

    = |z| * phi(z) * 100.  Zero at 50c: an at-the-money binary is a pure
    direction bet and carries no volatility information whatever.
    """
    if not (0.0 < p < 1.0):
        return 0.0
    z = ND.inv_cdf(p)
    return abs(z) * ND.pdf(z) * 100.0


def fee_cents(p):
    """Kalshi's quadratic taker fee, in cents per contract."""
    p = min(max(p, 0.0), 1.0)
    return 100.0 * FEE_K * p * (1.0 - p)


def net_edge(p, dsig, half_spread=None):
    """Cents left after the fee and the spread, for a log-sigma error dsig."""
    hs = half_spread_c(p) if half_spread is None else half_spread
    return dfair_dlogsigma(p) * dsig - fee_cents(p) - hs


def tail_error_cents(p, ratio):
    """Cents the Gaussian fair value is wrong by, if the empirical tail at
    this price is `ratio` times the Gaussian one.

    This is not a refinement, it is the thing most likely to kill the wings.
    A ratio of 2.0 at p = 1c means the true fair value is 2c and the model
    says 1c -- a 1c error, against a sigma-timing edge there of ~0.1c. Model
    error does not average out across trades: it is the same sign every time.
    """
    if ratio is None or ratio <= 0:
        return 0.0
    return abs(ratio - 1.0) * 100.0 * min(p, 1.0 - p)


def band(dsig, half_spread=None, tails=None, lo=0.01, hi=0.50,
         step=0.0025):
    """The contiguous price range where net edge > model error, on the low
    side of 50c. Returns (p_lo, p_hi) or None."""
    best = []
    p = lo
    while p <= hi + 1e-12:
        ne = net_edge(p, dsig, half_spread)
        me = tail_error_cents(p, tails(p) if callable(tails) else tails)
        if ne > me:
            best.append(p)
        p += step
    if not best:
        return None
    return (min(best), max(best))


def analytic_report(dsigs=(0.05, 0.10, 0.20, 0.30), tails=None):
    print("=" * 78)
    print("PART 1  WHERE a volatility edge can be taken -- analytic")
    print("=" * 78)
    print("  d(fair)/d(log sigma) = -z*phi(z): ZERO at 50c, peaking at |z|=1")
    print(f"  (p = {100*ND.cdf(-1.0):.0f}c / {100*ND.cdf(1.0):.0f}c) at "
          f"{MAX_DFAIR_DLOGSIG:.3f}c per 1.0 log-unit.")
    print(f"  Taker fee = {FEE_K}*p*(1-p): largest at 50c, vanishing in the "
          f"wings.")
    print("  The tick is TAPERED (API price_ranges): 0.1c below 10c and above")
    print("  90c, 1c in between. So a taker crosses 0.05c in the wings, not")
    print("  0.5c -- and the hurdle keeps falling instead of turning back up.")
    hdr = (f"  {'price':>7}{'z':>7}{'edge/logsig':>13}{'fee':>8}{'tick':>7}"
           f"{'hurdle':>9}"
           + "".join(f"{f'net@{d:.0%}':>10}" for d in dsigs))
    print(hdr)
    for p in (0.50, 0.40, 0.30, 0.25, 0.20, 0.16, 0.12, 0.10, 0.07, 0.05,
              0.03, 0.02, 0.01):
        z = ND.inv_cdf(p)
        g = dfair_dlogsigma(p)
        f = fee_cents(p)
        row = (f"  {100*p:>6.0f}c{z:>7.2f}{g:>12.3f}c{f:>7.2f}c"
               f"{tick_cents(p):>6.1f}c{f + half_spread_c(p):>8.2f}c")
        for d in dsigs:
            row += f"{net_edge(p, d):>10.2f}"
        print(row)
    print("\n  Break-even sigma error, by price (what the market must be "
          "wrong by\n  before a single contract is worth crossing the "
          "spread for):")
    print(f"  {'price':>7}{'needed':>12}")
    for p in (0.40, 0.30, 0.20, 0.16, 0.10, 0.05, 0.02):
        g = dfair_dlogsigma(p)
        need = (fee_cents(p) + half_spread_c(p)) / g if g > 0 else float("inf")
        print(f"  {100*p:>6.0f}c{100*need:>11.1f}%")
    for d in dsigs:
        b = band(d, tails=tails)
        if b is None:
            print(f"\n  sigma error {d:.0%}: NO tradeable band.")
        else:
            print(f"\n  sigma error {d:.0%}: tradeable at "
                  f"{100*b[0]:.0f}c-{100*b[1]:.0f}c "
                  f"(and {100*(1-b[1]):.0f}c-{100*(1-b[0]):.0f}c by symmetry)")
    if tails is None:
        print("\n  MEASURED TAILS say the deep wings are worse than this table")
        print("  makes them look. chain.py on 5,190 windows per series puts")
        print("  the 99th-percentile empirical/Gaussian ratio at 1.72-2.64")
        print("  (BTC 2.64). At p = 1c that is model error of ~1.6c, carrying")
        print("  the SAME SIGN on every trade, against a sigma-timing edge")
        print("  there of ~0.06c per 1% -- so 1-3c is not a place to trade a")
        print("  Gaussian model however cheap the tick is. Pass --tail-ratio")
        print("  to fold it in.")
        print("\n  NOTE no empirical tail ratios supplied, so the wings are")
        print("  scored on fee and tick alone. That is optimistic. Pass")
        print("  --tail-ratio to fold in chain.py's measured tail table; at")
        print("  large |z| the Gaussian fair value is exactly where a")
        print("  fat-tailed truth disagrees with it most, and model error")
        print("  carries the same sign on every trade rather than averaging")
        print("  out across them.")


# ===========================================================================
# PART 2 -- the measurement
# ===========================================================================
def ewma_logvol(vals, halflife):
    """Backward-looking log-volatility forecast: EWMA of log|r|, using only
    entries STRICTLY BEFORE each position. Returns a list the same length,
    with None where there is not yet any history.

    Strictly before is the whole point. A forecast that peeks at its own
    window is not a forecast, and it would produce a beautiful result.
    """
    lam = 0.5 ** (1.0 / max(halflife, 1e-9))
    out, acc, wt = [], 0.0, 0.0
    for v in vals:
        out.append(math.log(acc / wt) if wt > 0 and acc > 0 else None)
        a = abs(v)
        if a > 0:
            acc = lam * acc + a
            wt = lam * wt + 1.0
    return out


def ols_slope(xs, ys):
    n = len(xs)
    if n < 3:
        return None, None
    mx, my = mean(xs), mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return None, None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return b, my - b * mx


def block_slope_se(xs, ys, B=800, seed=20260827, block=None):
    """Moving-block-bootstrap SE for an OLS slope.

    The iid SE is wrong here for the same reason it was wrong in chain.py:
    both the predictor and the residual are serially dependent, because
    volatility clustering is the thing being measured. Resampling contiguous
    runs keeps that dependence in every resample.
    """
    n = len(xs)
    if n < 30:
        return None, None
    b = block or max(2, int(round(n ** (1.0 / 3.0))))
    starts = n - b + 1
    if starts < 2:
        return None, b
    k = max(1, int(math.ceil(n / float(b))))
    rng = random.Random(seed)
    out = []
    for _ in range(B):
        xi, yi = [], []
        for _ in range(k):
            s = rng.randrange(starts)
            xi.extend(xs[s:s + b])
            yi.extend(ys[s:s + b])
        sl, _ic = ols_slope(xi, yi)
        if sl is not None:
            out.append(sl)
    if len(out) < 50:
        return None, b
    return pstdev(out), b


def gap_test(x, logratio, label="", B=800, seed=20260827):
    """The whole measurement, in one regression.

    x         backward-looking log-vol forecast, one per close
    logratio  log(sigma_realised / sigma_implied) for that same close

    Two DIFFERENT claims come out, and conflating them is a mistake I made
    here before the self-test caught it:

    LEVEL (the intercept).  The market prices sigma systematically high or
    low, by the same amount every window. `implied.py` already sees this
    unconditionally -- BTC 0.88, ETH 0.86 -- and it is by far the larger
    number. It is also the fragile one: ANY bias in how we estimate realised
    sigma lands entirely in this term. A 5% error in the realised estimator is
    indistinguishable from a 5% market mispricing.

    RESPONSE (the slope).  The market under-reacts to what recent volatility
    already told it. This is the claim volatility clustering actually
    supports, and it is robust to exactly the thing that breaks the level: a
    constant bias in the realised estimator cancels out of a slope.

    So the verdict keys on the SLOPE. The level is reported beside it, and
    treated as a lead rather than a finding.
    """
    pairs = [(a, b) for a, b in zip(x, logratio)
             if a is not None and b is not None
             and math.isfinite(a) and math.isfinite(b)]
    if len(pairs) < 50:
        return None
    mx = mean(a for a, _ in pairs)
    xs = [a - mx for a, _ in pairs]          # centred, so the intercept IS
    ys = [b for _, b in pairs]               # the mean mispricing
    slope, icept = ols_slope(xs, ys)
    if slope is None:
        return None
    se, blk = block_slope_se(xs, ys, B=B, seed=seed)
    mad = mean(abs(a) for a in xs)
    fitted = [icept + slope * a for a in xs]
    out = {"n": len(pairs), "slope": slope, "level": icept, "se": se,
           "block": blk, "sd_x": pstdev(xs), "mad_x": mad, "mean_x": mx,
           "label": label,
           # the response edge: what the SLOPE alone is worth
           "edge_c": MAX_DFAIR_DLOGSIG * slope * mad,
           # the level edge, and the two together
           "level_c": MAX_DFAIR_DLOGSIG * abs(icept),
           "total_c": MAX_DFAIR_DLOGSIG * mean(abs(f) for f in fitted)}

    # The linear term |z|*phi(z)*gap is a first-order approximation and it
    # OVERSTATES, by 12% on the self-test's blind market. Two corrections,
    # both real money:
    #   (a) Phi(z*exp(-g)) - Phi(z) is not linear in g once g is not small,
    #       and the mispricings we are looking for are not small; and
    #   (b) a trader acts on the FITTED gap but is paid on the REALISED one,
    #       so the residual has to be integrated over -- when it flips the
    #       sign of the true mispricing, that trade loses.
    # Taking the linear number to the hurdle would call trades that do not
    # clear it. This is the figure the verdict uses.
    # The residual distribution is discretised by QUANTILE, not by resampling
    # it. A 200-draw bootstrap pool has a mean that wanders by ~sd/sqrt(200),
    # and here that is 0.018 log-units -- worth 0.43c of edge, which is the
    # entire discrepancy this test showed before. Evenly spaced quantiles are
    # deterministic and carry the empirical mean exactly.
    res = sorted(y - f for y, f in zip(ys, fitted))
    K = min(201, len(res))
    pool = [res[min(len(res) - 1, int((i + 0.5) * len(res) / K))]
            for i in range(K)]
    z1, base = 1.0, ND.cdf(1.0)

    def _cents(f):
        side = 1.0 if f > 0 else -1.0
        return side * 100.0 * mean(
            base - ND.cdf(z1 * math.exp(-(f + e))) for e in pool)

    out["edge_exact_c"] = mean(_cents(f) for f in fitted)
    if se and se > 0:
        out["t"] = slope / se
        out["p"] = p_two_sided(abs(slope / se), max(len(pairs) - 2, 1))
        out["mde_slope"] = 3.0 * se
        out["mde_edge_c"] = MAX_DFAIR_DLOGSIG * 3.0 * se * mad
    return out


def fitted_gap(r, x):
    """The mispricing this regression predicts for a window with forecast x.

    The ONLY quantity a trader may act on. It is the fitted value, intercept
    included -- not the realised gap, which is hindsight, and not the slope
    term alone, which throws away the level.
    """
    if r is None or x is None or not math.isfinite(x):
        return None
    return r["level"] + r["slope"] * (x - r["mean_x"])


def hurdle_cents(p=0.16):
    return fee_cents(p) + half_spread_c(p)


GAP_HDR = (f"  {'label':>12}{'n':>7}{'level':>9}{'slope':>9}{'se':>8}"
           f"{'t':>7}{'resp c':>9}{'lvl c':>8}{'both':>8}{'hurdle':>9}"
           f"   verdict")


def print_gap(r):
    if not r:
        print("    not enough paired observations")
        return
    h = hurdle_cents()
    t = r.get("t")
    print(f"  {r['label']:>12}{r['n']:>7,}{r['level']:>9.3f}"
          f"{r['slope']:>9.3f}"
          f"{(r['se'] if r['se'] else float('nan')):>8.3f}"
          f"{(t if t is not None else float('nan')):>7.1f}"
          f"{r['edge_c']:>8.2f}c{r['level_c']:>7.2f}c"
          f"{r['edge_exact_c']:>7.2f}c"
          f"{h:>8.2f}c   "
          + ("EDGE" if (t is not None and t > 3 and r["edge_exact_c"] > h)
             else "response real, under hurdle"
             if (t is not None and t > 3)
             else "no response"))


# ===========================================================================
def _sim(n, seed, beta=0.6, market_loading=1.0, sig0=6.0, halflife=8.0,
         noise=0.25):
    """A market with a KNOWN under-response.

    True log-sigma follows the forecast with loading `beta`. The market quotes
    log-sigma following the SAME forecast with loading beta*market_loading, so
    market_loading = 1.0 is a market that prices vol clustering perfectly (no
    edge) and 0.0 is one that ignores it entirely.

    The planted answer is d_beta = beta * (1 - market_loading).
    """
    rng = random.Random(seed)
    rs, xs, lr = [], [], []
    hist = []
    for i in range(n):
        f = ewma_logvol(hist, halflife)[-1] if hist else None
        if f is None:
            f = math.log(sig0)
        # realised log-sigma loads `beta` on the forecast's deviation
        dev = f - math.log(sig0)
        ls_true = math.log(sig0) + beta * dev + rng.gauss(0, noise)
        ls_mkt = math.log(sig0) + beta * market_loading * dev
        sig = math.exp(ls_true)
        r = rng.gauss(0, sig)
        hist.append(r)
        xs.append(dev if i > 0 else None)
        lr.append((ls_true - ls_mkt) if i > 0 else None)
        rs.append(r)
    return xs, lr


def selftest():
    print("=" * 78)
    print("SELF-TEST -- against known answers")
    print("=" * 78)
    fails = []

    # 1. the analytic curve, against brute force
    print("\n1. d(fair)/d(log sigma) must match a numeric derivative, and must")
    print("   be EXACTLY ZERO at 50c (an at-the-money binary carries no")
    print("   volatility information -- if this is ever non-zero the whole")
    print("   band analysis is pointing at the wrong prices).")
    print(f"   {'price':>8}{'analytic':>12}{'numeric':>12}{'diff':>12}")
    worst = 0.0
    for p in (0.50, 0.30, 0.16, 0.10, 0.05):
        mu, K, tau, sig = 80000.0, None, 600, 6.0
        vf = math.sqrt(var_factor(tau, [1.0]))
        z = ND.inv_cdf(p)
        K = mu - z * sig * vf                    # strike giving exactly p
        h = 1e-5
        num = (ND.cdf((mu - K) / (sig * math.exp(h) * vf))
               - ND.cdf((mu - K) / (sig * math.exp(-h) * vf))) / (2 * h) * 100.0
        ana = -math.copysign(dfair_dlogsigma(p), z)
        worst = max(worst, abs(num - ana))
        print(f"   {100*p:>7.0f}c{ana:>12.4f}{num:>12.4f}{num - ana:>12.2e}")
    if worst > 1e-3:
        fails.append(f"analytic derivative off by {worst:.2e} cents")
    if dfair_dlogsigma(0.5) != 0.0:
        fails.append("d(fair)/d(log sigma) is non-zero at 50c")

    # 2. the forecast must not peek
    print("\n2. The forecast must use ONLY the past. A forecast that sees its")
    print("   own window produces a beautiful result and no money.")
    vals = [1.0] * 20 + [50.0] + [1.0] * 20
    f = ewma_logvol(vals, 8.0)
    if f[0] is not None:
        fails.append("the first forecast is not None -- it had no history")
    jump = 20
    if f[jump] is not None and f[jump] > math.log(2.0):
        fails.append(f"the forecast at the spike already knew about it "
                     f"({math.exp(f[jump]):.2f})")
    if not (f[jump + 1] is not None and f[jump + 1] > math.log(2.0)):
        fails.append("the forecast never reacted to the spike at all")
    print(f"   forecast at the spike: {math.exp(f[jump]):.2f}   "
          f"one window later: {math.exp(f[jump + 1]):.2f}   "
          f"(must be small then large)")

    # 3. plant a known under-response and recover it; plant none and find none
    print("\n3. A market that prices vol clustering PERFECTLY must show no")
    print("   gap. One that ignores it must show the whole of it.")
    print(GAP_HDR)
    BETA = 0.6
    for tag, ml, want in (("perfect", 1.00, 0.0),
                          ("half-blind", 0.50, BETA * 0.5),
                          ("blind", 0.00, BETA)):
        xs, lr = _sim(4000, seed=41 + int(ml * 10), beta=BETA,
                      market_loading=ml)
        r = gap_test(xs, lr, tag)
        print_gap(r)
        if not r:
            fails.append(f"{tag}: no result")
            continue
        if abs(r["slope"] - want) > 0.08:
            fails.append(f"{tag}: recovered slope {r['slope']:.3f}, planted "
                         f"{want:.3f}")
        if want == 0.0 and r.get("t") is not None and abs(r["t"]) > 3:
            fails.append(f"{tag}: invented a gap in a correctly priced "
                         f"market (t={r['t']:.1f})")
        if want > 0.3 and (r.get("t") is None or r["t"] < 3):
            fails.append(f"{tag}: missed a planted gap of {want:.2f}")

    # 4. the cents conversion must predict actual money
    print("\n4. THE ONE THAT MATTERS: the cents figure must predict realised")
    print("   P&L. A formula that says 3c and earns 0.4c is not a formula.")
    print("   Trade the planted mispricing at |z|=1 and settle every")
    print("   contract.")
    print("\n   The trader may use ONLY the forecastable part of the gap,")
    print("   slope*x -- never the realised gap. Using the realised gap is")
    print("   hindsight, and the first version of this test did exactly that:")
    print("   it paid 6.75c on a market with a real edge AND 4.07c on one")
    print("   with none, because knowing this window's volatility is worth")
    print("   money whether or not the market is mispriced.")

    def trade(xs, lr, r, seed):
        """Settle every window at |z| = 1, betting on the FITTED gap alone.

        Returns (drawn, expected). `drawn` settles each contract on an actual
        coin flip; `expected` takes its expectation over that flip only.

        Both are honest -- the strategy and the mispricing are identical in
        each. Separating them separates two different failures: `expected`
        tests whether the CENTS FORMULA is right, at a fraction of the noise,
        while `drawn` tests that nothing goes missing between a probability
        and a settled contract. Judging the formula on `drawn` alone means
        judging it through the variance of six thousand coin flips, which is
        how a 20%-wrong formula passes.
        """
        rng = random.Random(seed)
        drawn, exp = [], []
        for x, gap in zip(xs, lr):
            if x is None or gap is None:
                continue
            ghat = fitted_gap(r, x)              # the ONLY thing we may know
            if ghat is None:
                continue
            z_mkt = 1.0 if rng.random() < 0.5 else -1.0
            p_mkt = ND.cdf(z_mkt)
            p_true = ND.cdf(z_mkt * math.exp(-gap))
            yes = ghat * (-z_mkt) > 0            # sign of d(fair)/d(log sig)
            entry = p_mkt if yes else 1.0 - p_mkt
            win = p_true if yes else 1.0 - p_true
            exp.append(100.0 * (win - entry) - fee_cents(entry))
            drawn.append(100.0 * ((1.0 if rng.random() < win else 0.0) - entry)
                         - fee_cents(entry))
        return drawn, exp

    print(f"\n   {'market':>14}{'planted':>10}{'predicted':>12}"
          f"{'expected':>11}{'+/-':>7}{'settled':>10}{'+/-':>7}{'n':>7}")
    for tag, ml, seed in (("blind", 0.0, 99), ("half-blind", 0.5, 131),
                          ("perfect", 1.0, 123)):
        xs, lr = _sim(6000, seed=seed, beta=0.6, market_loading=ml)
        r = gap_test(xs, lr, tag)
        pnl, ev = trade(xs, lr, r, seed + 1)
        got, se = mean(pnl), pstdev(pnl) / math.sqrt(len(pnl))
        gev, sev = mean(ev), pstdev(ev) / math.sqrt(len(ev))
        # The trader acts on the FITTED gap -- intercept and slope together
        # -- so the prediction is total_c, not the response term alone.
        # Predicting from edge_c understated the blind case by 3x, because
        # the simulated market also carries a constant level error and the
        # trader picks that up with a constant sign.
        pred = r["edge_exact_c"] - fee_cents(ND.cdf(-1.0))
        print(f"   {tag:>14}{0.6 * (1 - ml):>10.2f}{pred:>11.2f}c"
              f"{gev:>10.2f}c{sev:>7.2f}{got:>9.2f}c{se:>7.2f}"
              f"{len(pnl):>7,}")
        if abs(r["slope"] - 0.6 * (1 - ml)) > 0.08:
            fails.append(f"{tag}: slope {r['slope']:.3f} vs planted "
                         f"{0.6 * (1 - ml):.3f}")
        if abs(gev - pred) > max(3.0 * sev, 0.15):
            fails.append(f"{tag}: the formula predicted {pred:.2f}c and the "
                         f"strategy's expectation is {gev:.2f}c +/- {sev:.2f}"
                         " -- the conversion from slope to money is wrong")
        if abs(got - gev) > 4.0 * se:
            fails.append(f"{tag}: settled P&L {got:.2f}c differs from its own "
                         f"expectation {gev:.2f}c by more than settlement "
                         "noise explains")
        if ml == 1.0 and gev > 0:
            fails.append(f"a correctly priced market pays {gev:.2f}c in "
                         "expectation -- the simulation is leaking an edge")

    # 5. and the hindsight version must pay MORE, on a market with no edge.
    #    This pins the trap rather than just avoiding it: if this ever stops
    #    being true, the forecast has started peeking.
    xs, lr = _sim(6000, seed=123, beta=0.6, market_loading=1.0)
    rng = random.Random(5)
    cheat = []
    for x, gap in zip(xs, lr):
        if x is None or gap is None:
            continue
        z_mkt = 1.0 if rng.random() < 0.5 else -1.0
        p_mkt, p_true = ND.cdf(z_mkt), ND.cdf(z_mkt * math.exp(-gap))
        yes = p_true > p_mkt
        entry = p_mkt if yes else 1.0 - p_mkt
        hit = rng.random() < (p_true if yes else 1.0 - p_true)
        cheat.append(100.0 * ((1.0 if hit else 0.0) - entry) - fee_cents(entry))
    c = mean(cheat)
    print(f"\n   the same no-edge market, traded with HINDSIGHT: {c:>6.2f}c")
    print("   That number is the size of the trap, not a strategy.")
    if c <= 0:
        fails.append("hindsight did not beat the forecast on a no-edge "
                     "market, so this test no longer pins the look-ahead trap")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- the curve matches brute force and is zero at")
    print("50c, the forecast cannot see its own window, a perfectly priced")
    print("market shows no gap, a blind one shows all of it, and the cents")
    print("figure predicts the money a simulation actually pays.")
    return True


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--feeds", default="./feed_data")
    ap.add_argument("--out", default="./fulltape",
                    help="where fulltape wrote markets.json")
    ap.add_argument("--halflife", type=float, default=8.0,
                    help="windows; 8 = two hours of 15-minute closes")
    ap.add_argument("--tau-lo", type=int, default=300)
    ap.add_argument("--tau-hi", type=int, default=900)
    ap.add_argument("--tail-ratio", type=float, default=None,
                    help="empirical/Gaussian tail ratio from chain.py, folded "
                         "into the band as model error")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed; refusing to touch real data")

    analytic_report(tails=a.tail_ratio)

    print("\n" + "=" * 78)
    print("PART 2  DOES THE MARKET ALREADY KNOW? -- measured")
    print("=" * 78)
    try:
        from replay import (load_quotes, load_markets, load_index,
                            SERIES_TO_INDEX)   # NOT engine -- it lives here
        from implied import collect
    except ImportError as e:
        print(f"  loaders unavailable ({e}); analytic half only.")
        return
    try:
        quotes = load_quotes(a.data)
        markets = load_markets(a.out)   # NOT "." -- it lives beside the tapes
        index = load_index(a.data)
    except Exception as e:
        print(f"  {type(e).__name__}: {e}")
        return
    rows = collect(index, quotes, markets, SERIES_TO_INDEX,
                   ttc_max=a.tau_hi)
    if not rows:
        print("  no invertible quotes -- nothing to measure.")
        return

    # One implied sigma per (series, close): the median over the tau window,
    # so a single stale quote cannot set the number for a whole market.
    per = {}
    for r in rows:
        if not (a.tau_lo <= r["tau"] <= a.tau_hi):
            continue
        per.setdefault((r["series"], r["close"]), []).append(r["iv"])
    if not per:
        print(f"  no quotes in tau {a.tau_lo}-{a.tau_hi}s.")
        return

    print("\n" + GAP_HDR)
    by_series = {}
    for (s, c), ivs in per.items():
        by_series.setdefault(s, []).append((c, sorted(ivs)[len(ivs) // 2]))
    for s, items in sorted(by_series.items()):
        items.sort()
        closes = [c for c, _ in items]
        ivs = [v for _, v in items]
        # realised sigma over each window, from the index itself
        iid = SERIES_TO_INDEX.get(s)
        ticks = index.get(iid) or {}
        rvs = []
        for c in closes:
            seg = [ticks[t] for t in range(c - 900, c) if t in ticks]
            if len(seg) < 300:
                rvs.append(None)
                continue
            d = [seg[i + 1] - seg[i] for i in range(len(seg) - 1)]
            rvs.append(pstdev(d) if len(d) > 30 else None)
        good = [(c, iv, rv) for c, iv, rv in zip(closes, ivs, rvs)
                if rv and rv > 0 and iv and iv > 0]
        if len(good) < 60:
            print(f"  {s:>10}{len(good):>7,}   too few paired windows")
            continue
        x = ewma_logvol([g[2] for g in good], a.halflife)
        lr = [math.log(g[2] / g[1]) for g in good]
        print_gap(gap_test(x, lr, s))

    print("\n  A positive slope means the market UNDER-responds to what recent")
    print("  volatility already told it. 'EDGE' requires both t > 3 and the")
    print("  cents figure clearing the hurdle -- a gap that is real but worth")
    print("  less than the fee is not a trade.")


if __name__ == "__main__":
    main()
