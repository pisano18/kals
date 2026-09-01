#!/usr/bin/env python3
"""calfit.py -- ONE number for the whole calibration curve.

    python research/calfit.py --selftest
    python research/calfit.py --data ./kalshi_data --out ./fulltape

WHY THIS EXISTS

calib.py measures the calibration curve bucket by bucket and the shape is the
most persistent thing this project has found: on the exogenous grid, outcomes
come out MORE EXTREME than prices, smoothly, across nineteen buckets.

    price   realised
      20c      16.9%
      40c      34.4%
      55c      50.1%
      80c      82.1%
      90c      94.4%

No single bucket clears |t| = 2. patterntrade.py then tried to trade it and
reported the honest problem rather than a result: one trade per market has a
per-trade standard deviation of ~46c, so at 583 close-time clusters its
minimum detectable edge is 5.7c -- larger than the 3-5c the curve implies. It
cannot see the thing it was built to test. Waiting for enough clusters means
twenty-two days of recording for a 3c edge.

The problem is not the sample. It is the instrument. Nineteen bucket tests
throw away the fact that the buckets agree with each other, and one trade per
market throws away everything except one Bernoulli draw.

THE MODEL

One parameter, fitted to every settled market at once:

    P(win) = Phi( a * Phi^-1(price) )

    a = 1   the market is calibrated
    a > 1   outcomes are MORE extreme than prices -- the market's implied
            volatility is too HIGH, and the money is in buying the favourite
    a < 1   outcomes are LESS extreme -- implied volatility too LOW, and the
            money is in buying the underdog

That is not an arbitrary curve. It is exactly a volatility misestimate: a
market quoting sigma_impl when the truth is sigma_true produces precisely this
distortion with a = sigma_impl / sigma_true. So

    a = 1 / r

where r is the ratio reconcile.py measures a completely different way, from
settlement dispersion against implied volatility. THE SAME PARAMETER, TWO
INSTRUMENTS, AND THEY CURRENTLY DISAGREE ABOUT ITS DIRECTION: calib's curve
implies a > 1, reconcile reports r around 0.5-0.75, i.e. a of 1.3-2.0 -- the
same sign, but wildly different sizes. Printing them side by side is half the
point of this file.

WHY IT HAS POWER WHERE patterntrade DOES NOT

Every market contributes to one parameter instead of to one of nineteen
buckets, and the contribution is weighted by how informative that market's
price is: the Fisher information per market is

    z^2 phi(az)^2 / [ Phi(az)(1 - Phi(az)) ]

which is zero at 50c -- an at-the-money binary carries no volatility
information at all, the same fact that runs through this whole project -- and
rises into the wings. The estimator therefore ignores the mid-book crowd for
free, without a hand-set filter, and the standard error follows.

WHAT IT STILL CANNOT DO

It assumes the ONLY distortion is a volatility misestimate. A market that is
wrong about direction, or that carries a fee-driven skew, will show up in `a`
as though it were volatility. The per-series table is the check: a common
mechanism should give a common `a`.

One market is one observation and standard errors cluster on close time,
because every series settles on the same clock and a crypto move is shared.

NOTHING HERE PLACES AN ORDER.
"""

import argparse
import math
import os
import random
import sys
from collections import defaultdict
from statistics import NormalDist, mean, median

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from voltiming import fee_cents, half_spread_c                  # noqa: E402

ND = NormalDist()
EPS = 1e-9
A_LO, A_HI = 0.20, 5.00          # bisection bracket for a
P_LO, P_HI = 0.02, 0.98          # inversions outside this are ill-conditioned


def _clip(x, lo=EPS, hi=1.0 - EPS):
    return min(max(x, lo), hi)


def outcome_of(m):
    """1.0 / 0.0 / None. `settle` is the settled index LEVEL and `result` is
    the outcome -- reading the truthiness of `settle` booked every market on
    the tape as a YES win once already (see endgame.py)."""
    r = m.get("result")
    if r is not None:
        if isinstance(r, bool):
            return 1.0 if r else 0.0
        if isinstance(r, (int, float)):
            return 1.0 if float(r) >= 0.5 else 0.0
        t = str(r).strip().lower()
        if t in ("yes", "y", "true", "1", "1.0", "win"):
            return 1.0
        if t in ("no", "n", "false", "0", "0.0", "loss"):
            return 0.0
        return None
    st, k = m.get("settle"), m.get("strike")
    if st is None or k is None:
        return None
    return 1.0 if float(st) >= float(k) else 0.0


# ===========================================================================
def score(a, z, y):
    """d(log L)/da for one market."""
    az = a * z
    P = _clip(ND.cdf(az))
    return z * ND.pdf(az) * (y - P) / (P * (1.0 - P))


def information(a, z):
    """Fisher information for one market. ZERO at z = 0: an at-the-money
    binary carries no volatility information, so the estimator down-weights
    the mid-book automatically rather than by a filter."""
    az = a * z
    P = _clip(ND.cdf(az))
    return (z * ND.pdf(az)) ** 2 / (P * (1.0 - P))


def fit(rows):
    """Maximum-likelihood `a` with a close-time cluster-robust SE.

    rows: (close, price, outcome). One row per MARKET.
    """
    obs = [(c, ND.inv_cdf(p), y) for c, p, y in rows if P_LO <= p <= P_HI]
    if len(obs) < 50:
        return None

    def total(a):
        return sum(score(a, z, y) for _, z, y in obs)

    lo, hi = A_LO, A_HI
    f_lo, f_hi = total(lo), total(hi)
    if f_lo * f_hi > 0:
        # The score does not change sign in the bracket: the data want an `a`
        # outside it, which is a statement about the data and not a fit.
        return {"a": lo if f_lo < 0 else hi, "se": float("inf"),
                "n": len(obs), "clusters": 0, "bracketed": False}
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if total(mid) * f_lo > 0:
            lo, f_lo = mid, total(mid)
        else:
            hi = mid
    a = (lo + hi) / 2.0

    H = sum(information(a, z) for _, z, _ in obs)
    by = defaultdict(float)
    for c, z, y in obs:
        by[c] += score(a, z, y)
    meat = sum(v * v for v in by.values())
    ncl = len(by)
    if H <= 0 or ncl < 2:
        return None
    # A finite-cluster correction, for the same reason term.py needed one.
    se = math.sqrt(meat * ncl / (ncl - 1.0)) / H
    return {"a": a, "se": se, "n": len(obs), "clusters": ncl,
            "t": (a - 1.0) / se if se > 0 else 0.0,
            "lo": a - 1.96 * se, "hi": a + 1.96 * se,
            "mde": 3.0 * se, "bracketed": True}


def edge_at(price, a):
    """Cents of gross edge from buying the side the model says is underpriced,
    at mid `price`, plus which side that is."""
    p = _clip(price, P_LO, P_HI)
    q = ND.cdf(a * ND.inv_cdf(p))
    return (100.0 * (q - p), "yes") if q > p else (100.0 * (p - q), "no")


def money(a, prices=(0.05, 0.10, 0.20, 0.30, 0.50, 0.70, 0.80, 0.90, 0.95)):
    print(f"\n  {'mid':>6}{'true fair':>11}{'side':>6}{'gross':>9}"
          f"{'cost':>8}{'NET':>9}")
    best = None
    for p in prices:
        g, side = edge_at(p, a)
        hs = half_spread_c(p)
        entry = p + hs / 100.0 if side == "yes" else p - hs / 100.0
        fee = fee_cents(entry if side == "yes" else 1.0 - entry)
        net = g - hs - fee
        if best is None or net > best[1]:
            best = (p, net, side)
        q = ND.cdf(a * ND.inv_cdf(_clip(p, P_LO, P_HI)))
        print(f"  {100*p:>5.0f}c{100*q:>10.2f}c{side:>6}{g:>8.2f}c"
              f"{hs + fee:>7.2f}c{net:>8.2f}c")
    if best:
        print(f"\n  Best cell: {100*best[0]:.0f}c buying {best[2].upper()}"
              f" at {best[1]:+.2f}c net.")
    print("  Cost is half the tightest quotable spread plus the taker fee --")
    print("  a FLOOR. surface.py re-costs this with the spreads actually")
    print("  resting there, and they are far wider in the wings.")
    return best


def report(rows, label=""):
    if not rows:
        print(f"  {label}no markets.")
        return None
    ys = [y for _, _, y in rows]
    rate = mean(ys)
    print(f"\n  {label}{len(rows):,} markets, YES rate {rate:.3f}")
    if not (0.05 <= rate <= 0.95):
        print("  *** REFUSING: that YES rate is a parsing failure, not a")
        print("  *** market. `settle` is the settled index LEVEL and the")
        print("  *** outcome is `result`.")
        return None
    f = fit(rows)
    if not f:
        print("  too few usable markets to fit.")
        return None
    if not f["bracketed"]:
        print(f"  the likelihood wants a outside [{A_LO}, {A_HI}] -- "
              "reporting the boundary, not a fit.")
        return f
    verdict = ("MORE extreme than prices (implied vol too HIGH)"
               if f["a"] > 1 else
               "LESS extreme than prices (implied vol too LOW)")
    print(f"  a = {f['a']:.4f}  [{f['lo']:.4f}, {f['hi']:.4f}]   "
          f"t vs 1 = {f['t']:+.2f}   {f['clusters']} clusters")
    print(f"  MDE on a: {f['mde']:.4f}  (the smallest departure from 1 this "
          f"sample could certify)")
    print(f"  implied/true sigma r = 1/a = {1.0/f['a']:.4f}")
    if abs(f["a"] - 1.0) <= f["mde"]:
        print("  INSIDE the MDE -- this sample cannot tell it from calibrated.")
    else:
        print(f"  outcomes are {verdict}")
    return f


# ===========================================================================
def _world(n_mkt, a_true, seed, rho=0.0, per_close=1):
    """Markets whose outcomes really do follow Phi(a * Phi^-1(p)).

    `rho` correlates outcomes WITHIN a close time, which is what a shared
    crypto move does. It must widen the standard error and must not move the
    point estimate; both are asserted.
    """
    rnd = random.Random(seed)
    rows = []
    n_close = max(1, n_mkt // per_close)
    for c in range(n_close):
        zc = rnd.gauss(0, 1)
        for _ in range(per_close):
            p = rnd.uniform(0.03, 0.97)
            q = ND.cdf(a_true * ND.inv_cdf(p))
            u = (math.sqrt(rho) * zc + math.sqrt(1 - rho) * rnd.gauss(0, 1)
                 if rho else rnd.gauss(0, 1))
            rows.append((c, p, 1.0 if u < ND.inv_cdf(q) else 0.0))
    return rows


def selftest():
    print("=" * 78)
    print("SELF-TEST -- against known answers")
    print("=" * 78)
    fails = []

    # ---- 1. recover a planted a -----------------------------------------
    print("\n  Plant a known distortion and read it back. a = 1 is a")
    print("  calibrated market; a > 1 means outcomes come out more extreme")
    print("  than prices.")
    print(f"\n  {'a planted':>11}{'a fitted':>11}{'95% CI':>22}"
          f"{'markets':>9}{'t vs 1':>9}")
    for a_true in (0.70, 1.00, 1.25, 1.60):
        f = fit(_world(20000, a_true, seed=int(a_true * 1000)))
        if not f:
            fails.append(f"no fit at a={a_true}")
            continue
        ci = f"[{f['lo']:.3f}, {f['hi']:.3f}]"
        print(f"  {a_true:>11.2f}{f['a']:>11.4f}{ci:>22}{f['n']:>9,}"
              f"{f['t']:>9.2f}")
        if abs(f["a"] - a_true) > 4 * f["se"]:
            fails.append(f"planted a={a_true} came back {f['a']:.4f} "
                         f"({abs(f['a']-a_true)/f['se']:.1f} SEs out)")
        if a_true == 1.00 and abs(f["t"]) > 3:
            fails.append(f"a calibrated market read t={f['t']:.2f} against 1")

    # ---- 2. clustering must widen the SE, not move the estimate ----------
    print("\n  CLUSTERING. Every series settles on the same clock, so one")
    print("  crypto move decides many markets at once. Correlated outcomes")
    print("  must WIDEN the interval and must not move the point estimate.")
    print(f"\n  {'within-close rho':>18}{'a':>10}{'se':>10}{'clusters':>10}")
    prev_se = None
    for rho in (0.0, 0.5):
        f = fit(_world(12000, 1.30, seed=7, rho=rho, per_close=20))
        if not f:
            fails.append(f"no fit at rho={rho}")
            continue
        print(f"  {rho:>18.2f}{f['a']:>10.4f}{f['se']:>10.5f}"
              f"{f['clusters']:>10}")
        if abs(f["a"] - 1.30) > 4 * f["se"]:
            fails.append(f"rho={rho} moved the estimate to {f['a']:.4f}")
        if prev_se is not None and f["se"] <= prev_se:
            fails.append("correlated outcomes did not widen the standard "
                         "error -- the cluster-robust sandwich is not working")
        prev_se = f["se"]

    # ---- 3. the power claim, measured against patterntrade ---------------
    print("\n  POWER, which is the entire reason this file exists.")
    print("  patterntrade takes one trade per market: per-trade sd ~46c, so")
    print("  583 clusters give it an MDE of 5.7c. Same markets, this")
    print("  estimator, converted to cents at the price it is worth most:")
    print(f"\n  {'markets':>9}{'clusters':>10}{'MDE on a':>11}"
          f"{'as cents at 20c':>18}")
    for n_mkt, per_close in ((5000, 9), (11000, 19)):
        f = fit(_world(n_mkt, 1.00, seed=99, rho=0.5, per_close=per_close))
        if not f:
            continue
        g_hi, _ = edge_at(0.20, 1.0 + f["mde"])
        print(f"  {f['n']:>9,}{f['clusters']:>10}{f['mde']:>11.4f}"
              f"{g_hi:>17.2f}c")
        if f["clusters"] > 500 and g_hi > 5.7:
            fails.append(f"at {f['clusters']} clusters the MDE is {g_hi:.2f}c "
                         "in money terms, no better than patterntrade's 5.7c "
                         "-- this file's whole claim is that it is better")

    # ---- 4. an at-the-money market must contribute NOTHING ---------------
    print("\n  d(fair)/d(log sigma) = -z*phi(z) is exactly zero at 50c, so an")
    print("  at-the-money binary carries no volatility information. The")
    print("  Fisher information must say the same thing without being told.")
    print(f"\n  {'price':>8}{'information':>14}")
    for p in (0.50, 0.40, 0.20, 0.10, 0.05):
        info = information(1.0, ND.inv_cdf(p))
        print(f"  {100*p:>7.0f}c{info:>14.5f}")
    if information(1.0, 0.0) > 1e-12:
        fails.append("a 50c market carries nonzero information")
    if information(1.0, ND.inv_cdf(0.16)) <= information(1.0, ND.inv_cdf(0.45)):
        fails.append("the wings do not carry more information than the "
                     "mid-book, which contradicts z*phi(z)")

    # ---- 5. a is exactly a volatility ratio -------------------------------
    # Build quotes from a TRUE model with sigma_impl and settle with
    # sigma_true; the fitted a must come back as sigma_impl/sigma_true.
    print("\n  a IS a volatility ratio, not a curve-fitting parameter. Quote")
    print("  a book at sigma_impl, settle it at sigma_true, and the fit must")
    print("  return their ratio -- which is what makes it comparable to")
    print("  reconcile.py's r = 1/a, measured a completely different way.")
    print(f"\n  {'sigma_impl/sigma_true':>22}{'a fitted':>11}{'1/a':>9}")
    rnd = random.Random(4242)
    for ratio in (0.80, 1.00, 1.30):
        rows = []
        for i in range(20000):
            z_true = rnd.gauss(0, 1)             # (mu-K)/(sigma_true*sqrt(vf))
            z_mkt = z_true / ratio               # what the market believes
            p = ND.cdf(z_mkt)
            if not (P_LO <= p <= P_HI):
                continue
            rows.append((i % 600, p, 1.0 if rnd.gauss(0, 1) < z_true else 0.0))
        f = fit(rows)
        if not f:
            fails.append(f"no fit at sigma ratio {ratio}")
            continue
        print(f"  {ratio:>22.2f}{f['a']:>11.4f}{1.0/f['a']:>9.4f}")
        if abs(f["a"] - ratio) > 4 * f["se"]:
            fails.append(f"a sigma ratio of {ratio} fitted as {f['a']:.4f} "
                         f"({abs(f['a']-ratio)/f['se']:.1f} SEs out) -- `a` is "
                         "then NOT the volatility ratio this file claims and "
                         "is not comparable to reconcile's r")

    # ---- 6. a degenerate outcome column must be refused -------------------
    print("\n  A degenerate outcome column is a parsing failure, not a")
    print("  market, and it must refuse rather than fit:")
    bad = [(i % 50, 0.3, 1.0) for i in range(500)]
    if report(bad, "all-YES fixture: ") is not None:
        fails.append("an all-YES outcome column was fitted instead of refused")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- recovers a planted distortion, is unmoved by")
    print("clustering while widening its interval, weights the wings and")
    print("ignores the money automatically, returns a as the volatility ratio")
    print("reconcile measures independently, and refuses a degenerate column.")
    return True


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--out", default="./fulltape")
    ap.add_argument("--tau", type=int, default=600,
                    help="seconds before close at which the price is read. "
                         "FIXED and exogenous: the market does not choose it.")
    ap.add_argument("--max-age", type=int, default=30)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed; refusing to touch real data")

    from replay import load_quotes, load_markets
    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    quotes = load_quotes(a.data)
    if not quotes:
        print("\n  no quotes on disk. Run doctor.py.")
        return
    markets = load_markets(a.out)
    if not markets:
        print(f"\n  *** NO SETTLED MARKETS at {os.path.abspath(a.out)}.")
        return

    rows, by_series, skipped = [], defaultdict(list), defaultdict(int)
    for tk, q in quotes.items():
        m = markets.get(tk)
        if not m:
            skipped["no settled market"] += 1
            continue
        y = outcome_of(m)
        close = m.get("close")
        if y is None or close is None:
            skipped["no usable outcome"] += 1
            continue
        want = int(round(float(close))) - a.tau
        # The prevailing quote at a FIXED second before close. Exogenous: the
        # market chooses when to quote, not when we look.
        best = None
        for rec in q:
            t = int(rec[0])
            if t <= want and (best is None or t > best[0]):
                best = (t, rec)
        if best is None or want - best[0] > a.max_age:
            skipped["no fresh quote at tau"] += 1
            continue
        bid, ask = best[1][1], best[1][2]
        if not (0.0 < bid < ask < 1.0):
            skipped["unusable quote"] += 1
            continue
        mid = (bid + ask) / 2.0
        if not (P_LO <= mid <= P_HI):
            skipped["price outside the invertible band"] += 1
            continue
        ser = m.get("series") or tk.split("-")[0]
        rows.append((int(round(float(close))), mid, y))
        by_series[ser].append((int(round(float(close))), mid, y))

    print(f"\n  one market = one observation, priced at tau = {a.tau}s")
    for k, v in sorted(skipped.items(), key=lambda x: -x[1]):
        print(f"    skipped {v:>7,}  {k}")

    f_all = report(rows, "ALL SERIES: ")
    if f_all and f_all.get("bracketed"):
        money(f_all["a"])

    print("\n" + "=" * 78)
    print("PER SERIES -- a common mechanism should give a common `a`")
    print("=" * 78)
    print(f"  {'series':>12}{'markets':>9}{'clusters':>10}{'a':>9}"
          f"{'95% CI':>20}{'r = 1/a':>10}")
    for ser in sorted(by_series):
        f = fit(by_series[ser])
        if not f or not f.get("bracketed"):
            print(f"  {ser:>12}{len(by_series[ser]):>9,}   no fit")
            continue
        ci = f"[{f['lo']:.3f}, {f['hi']:.3f}]"
        print(f"  {ser:>12}{f['n']:>9,}{f['clusters']:>10}{f['a']:>9.4f}"
              f"{ci:>20}{1.0/f['a']:>10.4f}")

    print("\n  Compare the r column against reconcile.py's ratio, which")
    print("  measures the SAME parameter from settlement dispersion and")
    print("  implied volatility rather than from outcomes. They have")
    print("  disagreed since 2026-08-28 and one of them is wrong.")


if __name__ == "__main__":
    main()
