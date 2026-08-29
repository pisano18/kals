#!/usr/bin/env python3
"""term.py -- the VOLATILITY TERM STRUCTURE, and what it says about the
market's variance model.

    python research/term.py --selftest
    python research/term.py --data ./kalshi_data --out ./fulltape

WHY THIS IS DIFFERENT FROM EVERY OTHER VOL MEASUREMENT HERE

Every implied-vol result this project has produced is a LEVEL: implied sigma
divided by a realised sigma we estimated ourselves. The live candidate --
implied/settle = 0.895, with four series' CIs excluding 1 -- is a level. Levels
are fragile in exactly one way, and it is the way that matters: any bias in our
realised-sigma estimator lands entirely in the answer. voltiming.py's estimator
was 16.5% high until it was fixed. reconcile.py exists because three of our own
sigma estimates disagreed with each other.

This file measures a SHAPE instead, and the shape needs no realised sigma at
all.

Var(settle - strike) with tau seconds left is exact and known:

    sd(tau)/sigma = sqrt(var_factor(tau))

Invert every quote in one market through that exact formula and you get an
implied sigma per second-to-close. If the market is using the same variance
formula we are, those numbers are FLAT in tau -- whatever sigma the market
believes, and whether or not it is right. A tilt means the market's variance
formula differs from the exact one, and that is a statement about arithmetic,
not about volatility.

Better still, it is a WITHIN-MARKET comparison. Two quotes on the same contract,
same underlying, same close, ten minutes apart. Nothing about our estimator,
our data, or our calendar can put a slope between them.

THE FINGERPRINT

Three variance models leave three unmistakable signatures. Written as the ratio
our exact inversion would return to the sigma the market actually believes:

     tau     exact   sqrt(tau)   sqrt(tau-39.5)
     900     1.000       1.023            1.000
     400     1.000       1.053            1.000
     120     1.000       1.221            1.000
      60     1.000       1.711            1.000
      30     1.000       3.380            0.000
      10     1.000       9.670            0.000

So a book on naive sqrt(tau) shows implied sigma EXPLODING into the close, and
one on sqrt(tau - 39.5) shows it COLLAPSING below about 40 seconds. Neither is
subtle, and neither can be produced by an error in anything we measure.

WHY IT IS WORTH KNOWING

endgame.py prices the consequence. Against a book quoting sqrt(tau) the exact
model earns +7.9c inside 60 seconds and +12.1c inside 15, with the claimed edge
matching the realised P&L to inside a standard error. So this file identifies
which model the market is on, and endgame.py says what that is worth. If the
answer is "flat", the market has the same arithmetic we do and there is nothing
here -- which is worth knowing for the price of one measurement.

TWO TRAPS, BOTH PINNED IN THE SELF-TEST

1. THE INVERSION IS UNDEFINED AT 50c and ill-conditioned near it. Filtering on
   |z| is the obvious fix and it is a trap, because the usual z is computed
   with the ROW'S OWN implied sigma: at a given distance from the strike, a
   high-sigma quote has a low |z| and gets cut. That is selection on the very
   quantity being measured, and because sqrt(var_factor(tau)) shrinks into the
   close it selects DIFFERENTLY at each tau -- manufacturing a term structure
   out of a flat one. This file filters on a z computed with a per-market
   REFERENCE sigma instead, so the cut falls on how far the path went, which is
   independent of the pricing error. The self-test plants a flat structure and
   fails if either filter reports a tilt.

2. ONE MARKET IS ONE OBSERVATION. Every quote inside a window is the same
   contract; SEs cluster on close time, and the regression is demeaned within
   market so the level -- the fragile part -- is differenced away before
   anything is fitted.

WHAT IT CANNOT DO, MEASURED RATHER THAN CLAIMED

A genuine view -- the market believing volatility RISES into the close -- tilts
the same way a sqrt(tau) error does, so no single beta separates them. Measured
on a fixture where the book holds a 40%-into-the-close view and uses the exact
formula, sqrt(tau) still reads beta = 0.185 (t = 12.6). The PAIR separates them
cleanly and that is how the table should be read:

                            beta on sqrt(tau)    beta on free power law
    a sqrt(tau) book                    0.998                    -0.580
    a 40% rising-vol view               0.119                    -0.157

Every figure here is printed by the self-test below, and is quoted rather than
remembered: an earlier version of this table carried numbers no run produced,
they were copied into HANDOFF, and they were still there when the result those
numbers described turned out to be an artefact.

A large beta on sqrt(tau) with a power-law beta near -0.58 is an arithmetic
error. A small one with a power-law beta near -0.18 is somebody's opinion about
volatility, which is not the same thing and is not obviously tradeable.

NOTHING HERE PLACES AN ORDER.
"""

import argparse
import math
import os
import random
import sys
from collections import defaultdict
from statistics import NormalDist, median, mean

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import var_factor                                  # noqa: E402
from implied import collect, _build                            # noqa: E402
from tdist import p_two_sided                                  # noqa: E402

ND = NormalDist()

# Buckets are tight where var_factor moves fastest and wide where it does not.
TAU_BUCKETS = [(1, 10), (10, 20), (20, 40), (40, 60), (60, 90), (90, 150),
               (150, 250), (250, 400), (400, 600), (600, 900)]

MIN_CELL = 3          # quotes before a (market, tau-bucket) cell counts
MIN_CLUSTERS = 20     # close times before a fit is reported.
                      # Was 8, where the measured size of a nominal 5% test
                      # is 13.4%. At 20 it is 8.7% and the t correction below
                      # closes most of the rest.
Z_LO, Z_HI = 0.5, 2.0


# Measured in the self-test below: symmetric mid noise on a FLAT book, whose
# true beta is exactly zero, produces |beta| of 0.000 / 0.041 / 0.123 at mid
# noise of 0c / 2c / 5c. Very nearly linear, so the floor is quoted as
# 2.46 * (noise in probability units), with half the observed spread used as
# the noise proxy. Crude, and it is the difference between a result and a
# number, so it is printed beside every fit.
NOISE_SLOPE = 2.46


def noise_floor(spread):
    """|beta| this file cannot distinguish from quote noise, given a spread."""
    return NOISE_SLOPE * (spread / 2.0)


def t_crit(df, p=0.975):
    """Two-sided 97.5% t critical value. 1.96 is the df=inf limit and it is
    materially wrong where this file actually operates: 2.365 at df=8."""
    if df < 1:
        return float("inf")
    lo, hi = 1.0, 100.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if p_two_sided(mid, df) > 2 * (1 - p):
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def vf(tau):
    return var_factor(int(tau), [1.0])


# A LOOSE backstop, no longer a bias control. implied.collect() inverts every
# carried-forward quote at the second it was ISSUED, so staleness no longer
# tilts the tau profile at all -- measured below on a flat book at 3s, 10s and
# 20s quote spacing, where beta comes back 0.0000 with this filter on or off.
#
# It used to be 0.02 and it used to be the whole defence, and it did not work.
# The rule was only ever exercised on a fixture emitting a quote every 3
# seconds, so every row it ever saw had age in {0,1,2}. On the same exact-model
# book with quotes 20s apart -- which is what a publish-on-change channel
# actually looks like when the book is quiet -- it returned beta = -0.487 on
# sqrt(tau) at t = -7.7 and +0.119 on the free power law at t = +7.7, against a
# true beta of exactly zero. The real tape's first reported figure, +0.111 at
# t = 8.4, is indistinguishable from that artefact.
STALE_TOL = 0.50


def fresh(tau, age):
    """A backstop against absurdly old quotes. NOT the staleness fix.

    The fix is in implied.collect(): a carried-forward quote is inverted at the
    tau it was issued at, which removes the bias exactly rather than bounding
    it. This only drops quotes so old that the market they describe has moved
    on entirely.

    What follows is why bounding it did not work, kept because the reasoning
    looked sound and was wrong.

    A carried-forward quote was priced when tau was tau+age, so inverting it
    through sqrt(var_factor(tau)) returns sd(tau+age)/sd(tau) times the sigma
    the quoter actually used. Far from the close that ratio is 1.00 and the
    staleness is harmless. Into the close it is not: sd/sigma falls from 0.893
    at tau=20 to 0.327 at tau=10, so a two-second-old quote at tau=15 inverts
    ~23% high and a thirty-second-old one at tau=10 inverts ~7x high.

    That is a rising-into-the-close bias, which is exactly the shape of the
    sqrt(tau) signature this file exists to detect. Measured on a fixture
    whose truth is exactly flat, allowing 2s of staleness gives beta = +0.062
    at t = 6.0 against a true beta of 0. With this rule it is 0.000.

    So the rule is not a tolerance on age, it is a tolerance on the thing age
    actually damages.
    """
    if age <= 0:
        return True
    v0, v1 = vf(tau), vf(tau + age)
    if v0 <= 0:
        return False
    return math.sqrt(v1 / v0) - 1.0 <= STALE_TOL


# --- the three candidate variance models, as log-ratio profiles ------------
def g_flat(tau):
    return 0.0


def g_naive(tau):
    """log of what an exact inversion returns when the book used sqrt(tau)."""
    v = vf(tau)
    return 0.5 * math.log(tau / v) if v > 0 else 0.0


def g_linear(tau):
    """...and when it used sqrt(tau - 39.5), which dies below ~40s."""
    v = vf(tau)
    x = max(tau - 39.5, 0.0)
    if v <= 0 or x <= 0:
        return -8.0            # a floor: the model says "essentially zero"
    return 0.5 * math.log(x / v)


def g_logtau(tau):
    """A free power law in tau. Not a variance model -- the catch-all that
    says 'something is tilted' without naming it."""
    return 0.5 * math.log(max(tau, 1))


MODELS = [("sqrt(tau)  naive", g_naive),
          ("sqrt(tau-39.5)", g_linear),
          ("free power law", g_logtau)]


# ===========================================================================
def staleness_table(rows):
    """What the freshness rule removes, per tau band. Printed before any
    result, because a band that keeps 2% of its quotes is not measured."""
    out = []
    for lo, hi in TAU_BUCKETS:
        sel = [r for r in rows if lo <= r["tau"] < hi]
        if not sel:
            continue
        ok = [r for r in sel if fresh(r["tau"], r.get("age", 0))]
        ages = sorted(r.get("age", 0) for r in sel)
        out.append({"band": (lo, hi), "n": len(sel), "kept": len(ok),
                    "med_age": ages[len(ages) // 2]})
    return out


def cells(rows, z_lo=Z_LO, z_hi=Z_HI, own_z=False):
    """Rows -> one median-iv cell per (close, series, tau-bucket).

    `own_z=True` reproduces the trap described in the header: filtering on a z
    built from each row's own implied sigma. It exists so the self-test can
    measure what that costs rather than assert it in a comment.
    """
    by_mkt = defaultdict(list)
    for r in rows:
        by_mkt[(r["close"], r["series"])].append(r)

    out = []
    for key, sel in by_mkt.items():
        # Reference sigma for this market: the median |iv| over the mid part
        # of the window, where the inversion is best conditioned. It is a
        # per-market CONSTANT, so it cannot put a slope inside the market.
        mid = [abs(r["iv"]) for r in sel if 150 <= r["tau"] <= 800]
        ref = median(mid) if len(mid) >= 10 else None
        if not ref or ref <= 0:
            continue
        keep = []
        for r in sel:
            if not fresh(r["tau"], r.get("age", 0)):
                continue
            if own_z:
                z = abs(r["z"])
            else:
                # z with the reference sigma: |mu-K| / (ref * sqrt(vf)), which
                # is |z_own| * |iv| / ref -- selection on how far the path
                # went, not on the price.
                z = abs(r["z"]) * abs(r["iv"]) / ref
            if z_lo <= z <= z_hi:
                keep.append(r)
        buck = defaultdict(list)
        for r in keep:
            for lo, hi in TAU_BUCKETS:
                if lo <= r["tau"] < hi:
                    buck[(lo, hi)].append(r)
                    break
        for b, v in buck.items():
            med = median([x["iv"] for x in v])
            if med <= 0:
                continue                       # signed noise; cannot take a log
            out.append({"close": key[0], "series": key[1], "mkt": key,
                        "band": b, "n": len(v),
                        "tau": mean(x["tau"] for x in v),
                        "y": math.log(med)})
    return [c for c in out if c["n"] >= MIN_CELL]


def demeaned(cs, g):
    """Within-market demeaning of both sides. The market's own level -- the
    part that carries every realised-sigma worry -- is differenced out here
    and never reaches the fit."""
    by = defaultdict(list)
    for c in cs:
        by[c["mkt"]].append(c)
    pts = []
    for mkt, v in by.items():
        if len(v) < 2:
            continue                          # one cell carries no shape
        my = mean(c["y"] for c in v)
        gx = [g(c["tau"]) for c in v]
        mx = mean(gx)
        for c, x in zip(v, gx):
            pts.append((c["close"], x - mx, c["y"] - my))
    return pts


def fit(pts):
    """Slope through the origin, with a close-time cluster-robust (CR0) SE.

    beta = 1 means the data has exactly that model's shape; beta = 0 means it
    has none of it. Both ends are informative, which is why the CI is what
    gets reported rather than a p-value against zero alone.
    """
    if len(pts) < 10:
        return None
    sxx = sum(x * x for _, x, _ in pts)
    if sxx <= 0:
        return None
    sxy = sum(x * y for _, x, y in pts)
    b = sxy / sxx
    g2 = defaultdict(float)
    for c, x, y in pts:
        g2[c] += x * (y - b * x)
    ncl = len(g2)
    if ncl < MIN_CLUSTERS:
        return None
    # CR0 with a finite-cluster correction and a t critical value, not 1.96.
    # Monte Carlo of this exact estimator at a true beta of zero: with 8
    # clusters the true sd(beta) is 0.211 while the uncorrected se averages
    # 0.180, so a nominal 5% test fired 13.4% of the time. At 20 clusters,
    # 8.7%; at 60, 6.2%. The sandwich itself is right -- at 256 clusters it is
    # 5.9% -- and the whole defect is the small-G floor, which is exactly the
    # regime main()'s per-series tables run in.
    se = math.sqrt(sum(v * v for v in g2.values())) / sxx
    se *= math.sqrt(ncl / (ncl - 1.0)) if ncl > 1 else 1.0
    crit = t_crit(ncl - 1)
    return {"beta": b, "se": se, "n": len(pts), "clusters": ncl,
            "t": (b / se) if se > 0 else 0.0, "crit": crit,
            "lo": b - crit * se, "hi": b + crit * se}


def shape(cs):
    """The non-parametric profile: mean within-market-demeaned log iv per tau
    band, with a close-clustered SE. This is the picture; the fits above are
    summaries of it."""
    by = defaultdict(list)
    for c in cs:
        by[c["mkt"]].append(c)
    rows = defaultdict(list)
    for mkt, v in by.items():
        if len(v) < 2:
            continue
        my = mean(c["y"] for c in v)
        for c in v:
            rows[c["band"]].append((c["close"], c["y"] - my))
    out = []
    for b in TAU_BUCKETS:
        v = rows.get(b)
        if not v:
            continue
        cl = defaultdict(list)
        for c, y in v:
            cl[c].append(y)
        vals = [mean(x) for x in cl.values()]
        if len(vals) < MIN_CLUSTERS:
            continue
        m = mean(vals)
        var = sum((x - m) ** 2 for x in vals) / (len(vals) * (len(vals) - 1))
        out.append({"band": b, "n": len(v), "clusters": len(vals),
                    "mean": m, "se": math.sqrt(var)})
    return out


def report(rows, label=""):
    cs = cells(rows)
    if len(cs) < 20:
        print(f"  {label}: {len(cs)} usable cells -- not enough to fit.")
        return None
    nm = len({c["mkt"] for c in cs})
    print(f"\n  {label}{len(cs):,} cells over {nm:,} markets, "
          f"{len({c['close'] for c in cs})} close times")

    st = staleness_table(rows)
    if st:
        print(f"\n  {'tau band':>12}{'quotes':>10}{'median age':>12}"
              f"{'fresh enough':>14}{'kept':>8}")
        for s in st:
            lo, hi = s["band"]
            print(f"  {f'{lo}-{hi}s':>12}{s['n']:>10,}{s['med_age']:>11}s"
                  f"{s['kept']:>14,}"
                  f"{100.0*s['kept']/s['n']:>7.0f}%")
        print("  Age is now DIAGNOSTIC, not a correction: implied.collect()")
        print("  inverts each carried quote at the tau it was issued at, so a")
        print("  stale quote is attributed to the moment its author priced it")
        print("  and contributes no tilt. Read this table for how live the")
        print("  book is, not for how much bias was removed.")

    sh = shape(cs)
    print(f"\n  {'tau band':>12}{'cells':>8}{'closes':>8}"
          f"{'log iv vs own market':>22}{'ratio':>9}"
          f"{'  naive says':>13}{'  linear says':>14}")
    # The model columns must be demeaned EXACTLY as the data column is:
    # within market, then averaged over the same cells. Subtracting a global
    # mean instead is a different centering whenever markets do not all carry
    # the same set of tau bands -- which they never do, because the close-in
    # bands are sparser. Measured on the planted sqrt(tau) book, where the fit
    # correctly returns beta=0.998 (the market IS exactly on the model), the
    # global-mean version printed 'naive says 2.932x' at 20-40s against data
    # of 2.259x, and 0.881x against 0.923x at 600-900s: a 30% disagreement
    # invented by the centering, in a table the header calls "the picture".
    # Demeaned consistently, the model says 2.282x and 0.921x -- under 1%.
    model_band = {}
    for name, g in (("naive", g_naive), ("linear", g_linear)):
        pts = demeaned(cs, g)                 # (close, x_demeaned, y) per cell
        acc = defaultdict(list)
        by = defaultdict(list)
        for c in cs:
            by[c["mkt"]].append(c)
        for mkt, v in by.items():
            if len(v) < 2:
                continue
            gx = [g(c["tau"]) for c in v]
            mx = mean(gx)
            for c, x in zip(v, gx):
                acc[c["band"]].append(x - mx)
        model_band[name] = {b: mean(vals) for b, vals in acc.items() if vals}
    for s in sh:
        lo, hi = s["band"]
        mn = model_band["naive"].get(s["band"])
        ml = model_band["linear"].get(s["band"])
        print(f"  {f'{lo}-{hi}s':>12}{s['n']:>8}{s['clusters']:>8}"
              f"{s['mean']:>+15.3f} +-{1.96*s['se']:<5.3f}"
              f"{math.exp(s['mean']):>8.3f}x"
              f"{(math.exp(mn) if mn is not None else float('nan')):>12.3f}x"
              f"{(math.exp(ml) if ml is not None else float('nan')):>13.3f}x")

    spreads = sorted(r["spread"] for r in rows if r.get("spread") is not None)
    sp = spreads[len(spreads) // 2] if spreads else 0.0
    fl = noise_floor(sp)
    print(f"\n  median spread {100*sp:.2f}c -> NOISE FLOOR |beta| = {fl:.3f}.")
    print("  A fit inside that is not a finding however large its t, because")
    print("  the t is against zero and zero is not the right null for a book")
    print("  that is quoted in ticks. See THE NOISE FLOOR in the self-test.")
    print(f"\n  {'variance model':>20}{'beta':>9}{'95% CI':>20}{'t':>8}"
          f"{'cells':>8}{'closes':>8}   reading")
    fits = {}
    for name, g in MODELS:
        f = fit(demeaned(cs, g))
        fits[name] = f
        if not f:
            print(f"  {name:>20}   not enough clusters")
            continue
        f["floor"] = fl
        if abs(f["beta"]) <= fl:
            rd = "INSIDE the noise floor -- not a finding"
        elif f["lo"] > 0.5:
            rd = "the market is ON this model"
        elif f["hi"] < 0.5 and f["lo"] > -0.5 and abs(f["t"]) < 2:
            rd = "no trace of it"
        elif f["t"] > 2:
            rd = "partial -- some of this shape"
        elif f["t"] < -2:
            rd = "the OPPOSITE tilt"
        else:
            rd = "indistinguishable from flat"
        cistr = "[%.3f, %.3f]" % (f["lo"], f["hi"])
        print(f"  {name:>20}{f['beta']:>9.3f}{cistr:>20}"
              f"{f['t']:>8.2f}{f['n']:>8}{f['clusters']:>8}   {rd}")
    return fits


# ===========================================================================
def _quote(model, noise=0.0):
    """A quote function for implied._build that prices with a chosen variance
    model. `sd` arrives as sqrt(var_factor(tau)) -- the exact one.

    `noise` adds SYMMETRIC error to the mid before the tick rounding _build
    applies. It is not decoration: it is the only way to see this file's
    resolution limit, and the limit turns out to be the same order as the
    effects it is looking for.
    """
    rng = random.Random(20260829)

    def q(mu, strike, sd, tau, sig):
        if model == "exact":
            s = sig * sd
        elif model == "naive":
            s = sig * math.sqrt(tau)
        elif model == "linear":
            s = sig * math.sqrt(max(tau - 39.5, 1e-9))
        elif model == "termup":
            # a GENUINE term structure: the market believes vol rises into the
            # close by 40% from open to close. Not a formula error -- a view.
            s = sig * sd * (1.0 + 0.4 * (1.0 - tau / 900.0))
        else:
            raise ValueError(model)
        if s <= 0:
            return None
        p = ND.cdf((mu - strike) / s)
        return p + rng.gauss(0, noise) if noise else p
    return q


def selftest():
    print("=" * 78)
    print("SELF-TEST -- against known answers")
    print("=" * 78)
    fails = []

    # ---- 1. the fingerprint table must be the closed form -----------------
    print("\n  The fingerprint. What an EXACT inversion returns, as a multiple")
    print("  of the sigma the market actually believes:")
    print(f"\n  {'tau':>8}{'exact':>10}{'sqrt(tau)':>12}{'sqrt(t-39.5)':>15}")
    for tau, want_n in ((900, 1.023), (400, 1.053), (120, 1.221),
                        (60, 1.711), (30, 3.380), (10, 9.670)):
        rn = math.exp(g_naive(tau))
        rl = math.exp(g_linear(tau))
        print(f"  {tau:>8}{1.000:>10.3f}{rn:>12.3f}{rl:>15.3f}")
        if abs(rn - want_n) > 2e-3:
            fails.append(f"naive ratio at tau={tau} is {rn:.4f}, not {want_n}")
    for tau in (30, 10):
        if math.exp(g_linear(tau)) > 1e-3:
            fails.append(f"sqrt(tau-39.5) does not collapse at tau={tau}")
    for tau in (900, 400, 120):
        if abs(math.exp(g_linear(tau)) - 1.0) > 2e-3:
            fails.append(f"sqrt(tau-39.5) is not exact at tau={tau}")

    S2I = {"KXBTC15M": "BRTI"}

    def rows_for(model, n_win=260, seed=7):
        idx, q, mk = _build(_quote(model), n_win=n_win, seed=seed)
        return collect(idx, q, mk, S2I)

    # ---- 2. a flat book must read FLAT ------------------------------------
    print("\n" + "-" * 78)
    print("  A book on the EXACT model. Every beta must be ~0: there is no")
    print("  term structure to find, and finding one would mean this file")
    print("  manufactures the thing it exists to detect.")
    fits = report(rows_for("exact"), "exact book: ")
    if not fits:
        fails.append("the exact-model world produced no fit at all")
    else:
        for name, f in fits.items():
            if f and abs(f["t"]) > 3:
                fails.append(f"exact book: {name} came back beta="
                             f"{f['beta']:.3f} at t={f['t']:.1f} -- a term "
                             "structure invented out of a flat one")

    # ---- 2b. QUOTE SPACING. The cell that would have caught the bug. -----
    # implied._build emits a quote every 3 seconds, so every row every other
    # fixture here has ever seen had age in {0,1,2}. A publish-on-change
    # channel on a quiet book looks nothing like that. Re-run the SAME
    # exact-model book at 10s and 20s spacing, where the true beta is still
    # exactly zero.
    print("\n" + "-" * 78)
    print("  QUOTE SPACING. Same exact-model book, quotes further apart. The")
    print("  true beta is zero at every spacing. This is the regime the old")
    print("  2%-staleness rule was never tested in, and it returned")
    print("  beta = -0.487 (t = -7.7) on sqrt(tau) at 20s spacing.")
    print(f"\n  {'spacing':>9}{'cells':>8}{'beta sqrt(tau)':>24}"
          f"{'beta power law':>24}")
    for step in (3, 10, 20):
        idx_, q_, mk_ = _build(_quote("exact"), n_win=260, seed=7, step=step)
        cs_ = cells(collect(idx_, q_, mk_, S2I))
        fn_ = fit(demeaned(cs_, g_naive))
        fp_ = fit(demeaned(cs_, g_logtau))
        def _f(x):
            return f"{x['beta']:+.4f} (t={x['t']:+6.2f})" if x else "no fit"
        print(f"  {step:>8}s{len(cs_):>8}{_f(fn_):>24}{_f(fp_):>24}")
        for nm, ft in (("sqrt(tau)", fn_), ("free power law", fp_)):
            if ft and abs(ft["beta"]) > 0.05:
                fails.append(f"at {step}s quote spacing a FLAT book returned "
                             f"beta={ft['beta']:+.3f} (t={ft['t']:+.1f}) on "
                             f"{nm} -- a term structure invented out of the "
                             "gap between quotes")

    # ---- 2c. THE NOISE FLOOR. What this file cannot resolve. -------------
    # Quote noise alone tilts a FLAT book. Same exact-model world, same
    # everything, with symmetric noise added to the mid before the 1c tick
    # rounding. The true beta is zero in every row.
    #
    # Raising Z_LO does not help -- it makes it worse -- so this is NOT the
    # small-|z| convexity it looks like, and no mechanism here is claimed. It
    # is measured and reported as a floor, because a bound you can state is
    # worth more than a correction built on a mechanism you have not proved.
    print("\n" + "-" * 78)
    print("  THE NOISE FLOOR. Symmetric mid noise on a FLAT book, where the")
    print("  true beta is exactly zero. This is what quote noise alone buys,")
    print("  and no result of this file smaller than it means anything.")
    print(f"\n  {'mid noise':>11}{'cells':>8}{'beta sqrt(tau)':>24}"
          f"{'beta power law':>24}")
    floor = 0.0
    for nz in (0.0, 0.02, 0.05):
        idx_, q_, mk_ = _build(_quote("exact", noise=nz), n_win=260, seed=7,
                               step=5)
        cs_ = cells(collect(idx_, q_, mk_, S2I))
        fn_ = fit(demeaned(cs_, g_naive))
        fp_ = fit(demeaned(cs_, g_logtau))
        def _f(x):
            return f"{x['beta']:+.4f} (t={x['t']:+6.2f})" if x else "no fit"
        print(f"  {nz:>11.2f}{len(cs_):>8}{_f(fn_):>24}{_f(fp_):>24}")
        for ft in (fn_, fp_):
            if ft:
                floor = max(floor, abs(ft["beta"]))
        if nz == 0.0:
            for nm, ft in (("sqrt(tau)", fn_), ("power law", fp_)):
                if ft and abs(ft["beta"]) > 0.02:
                    fails.append(f"a flat book with NO quote noise returned "
                                 f"beta={ft['beta']:+.3f} on {nm}")
    print(f"\n  NOISE FLOOR |beta| = {floor:.3f}. term.py cannot distinguish a")
    print("  real tilt smaller than this from the quote noise that produces")
    print("  it, whatever the t-statistic says -- the t is against zero, and")
    print("  zero is not the right null when the book is noisy.")
    globals()["NOISE_FLOOR"] = floor

    # ---- 3. the trap, measured rather than asserted ------------------------
    print("\n" + "-" * 78)
    print("  THE FILTER TRAP. Same flat book, same rows. The only difference")
    print("  is whether the |z| cut uses each row's OWN implied sigma (which")
    print("  is selection on the measured quantity) or a per-market reference")
    print("  sigma (which is selection on the path).")
    flat_rows = rows_for("exact")
    print(f"\n  {'|z| filter built from':>26}{'beta on free power law':>26}"
          f"{'t':>8}")
    trap = {}
    for own, lbl in ((False, "a per-market reference"), (True, "the row's own iv")):
        cs = cells(flat_rows, own_z=own)
        f = fit(demeaned(cs, g_logtau))
        trap[own] = f
        if f:
            print(f"  {lbl:>26}{f['beta']:>26.3f}{f['t']:>8.2f}")
        else:
            print(f"  {lbl:>26}{'no fit':>26}")
    if trap[False] and abs(trap[False]["t"]) > 3:
        fails.append("the reference-sigma filter itself produced a tilt on a "
                     "flat book")
    if trap[True] and trap[False] and \
            abs(trap[True]["beta"]) <= abs(trap[False]["beta"]):
        print("\n  NOTE: on this fixture the own-iv filter did not bite harder")
        print("  than the reference filter. The reference filter is still the")
        print("  correct one -- it is the only one whose selection provably")
        print("  cannot depend on the price -- but this cell is not currently")
        print("  pinning the difference, so do not cite it as evidence.")

    # ---- 4. each planted model must be identified -------------------------
    for model, expect, others in (
            ("naive", "sqrt(tau)  naive", ("sqrt(tau-39.5)",)),
            ("linear", "sqrt(tau-39.5)", ("sqrt(tau)  naive",))):
        print("\n" + "-" * 78)
        print(f"  A book on {model}. beta on its OWN model must be ~1.")
        fits = report(rows_for(model), f"{model} book: ")
        if not fits or not fits.get(expect):
            fails.append(f"the {model} world produced no fit for {expect}")
            continue
        f = fits[expect]
        if not (0.7 <= f["beta"] <= 1.3):
            fails.append(f"{model} book: beta on {expect} is {f['beta']:.3f}, "
                         "not ~1 -- the planted model was not recovered")
        if f["t"] < 3:
            fails.append(f"{model} book: {expect} only reached t={f['t']:.1f}")

    # ---- 5. a genuine term structure is NOT a formula error ---------------
    print("\n" + "-" * 78)
    print("  A book with a real VIEW -- it thinks vol rises 40% into the")
    print("  close -- and the exact variance formula. The free power law must")
    print("  see the tilt; the two formula models must not claim it, because")
    print("  telling a view apart from an arithmetic error is the whole point.")
    fits = report(rows_for("termup"), "term-structure book: ")
    if not fits:
        fails.append("the term-structure world produced no fit")
    else:
        fp = fits.get("free power law")
        if not fp or fp["t"] > -3:
            fails.append("a book pricing 40% more vol into the close did not "
                         "show a negative power-law tilt")
        fn = fits.get("sqrt(tau)  naive")
        if fn and fn["beta"] > 0.5:
            fails.append(f"a genuine term structure was read as sqrt(tau) "
                         f"with beta={fn['beta']:.2f} -- this file cannot "
                         "tell a view from a formula error")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- flat on a flat book, recovers a planted")
    print("sqrt(tau) and sqrt(tau-39.5) at beta ~ 1, and separates a genuine")
    print("term-structure view from a variance-formula error.")
    return True


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--out", default="./fulltape")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed; refusing to touch real data")

    from replay import (load_index, load_quotes, load_markets,
                        SERIES_TO_INDEX)
    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    index = load_index(a.data)
    if not index:
        print("  no cfbenchmarks_value -- cannot invert without the index.")
        return
    quotes = load_quotes(a.data)
    if not quotes:
        print("  no quotes on disk. Run doctor.py.")
        return
    markets = load_markets(a.out)
    if not markets:
        print(f"  *** NO MARKETS at {os.path.abspath(a.out)} -- fix --out.")
        return
    rows = collect(index, quotes, markets, SERIES_TO_INDEX)
    print(f"\n  {len(rows):,} invertible quote-seconds")
    if not rows:
        return
    report(rows, "all series: ")

    by = defaultdict(list)
    for r in rows:
        by[r["series"]].append(r)
    for s in sorted(by):
        if len(by[s]) < 2000:
            continue
        print("\n" + "-" * 78)
        report(by[s], f"{s}: ")

    print("\n  This needs no settlements and no realised sigma, so it runs on")
    print("  however many hours are recorded, and no error in our own")
    print("  volatility estimate can move it. A beta near 1 on sqrt(tau) is")
    print("  the one result here that endgame.py has already priced.")


if __name__ == "__main__":
    main()
