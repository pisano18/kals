#!/usr/bin/env python3
# VERSION: 2026-08-25-x1
"""
cross.py -- turn the 12-series correlation from a liability into an asset.

    python research/cross.py --selftest
    python research/cross.py --data ./kalshi_data --out ./fulltape

THE ARGUMENT

PLAN.md sec.5 correctly notes that the 12 crypto series close simultaneously and
are ~0.8 correlated, so twelve series give **1.22 effective independent units**,
not twelve. That is why a week of data resolves so little: almost all of the
apparent sample is one number repeated.

But that reasoning applies to an ABSOLUTE question -- "is the market mispriced?"
It inverts for a RELATIVE one -- "is NEAR mispriced relative to BTC?" -- because
subtracting the cluster mean removes the common crypto move, which is precisely
the term that made the twelve series redundant. The thing that destroys power in
one design supplies it in the other.

Write the per-series edge as

    edge_i = common + idio_i

With rho = 0.8, Var(common) = 4 * Var(idio). The absolute test carries the
common term and is dominated by it. Demeaning within a close-time cluster
deletes it, leaving only idio -- roughly a 5x variance reduction, plus (S-1)
usable residuals per cluster instead of one. The self-test measures the realized
gain rather than trusting this arithmetic.

WHAT IT CAN AND CANNOT SEE

  CAN: one series priced differently from its peers. That is the natural shape
       of the open question in PLAN sec.9 -- are the thin series (ZEC, HYPE,
       NEAR, TON) more loosely quoted than BTC? A single maker running twelve
       books with one model and per-asset parameters is most likely to be wrong
       on the assets it cares least about.

  CANNOT: a mispricing common to every series. Demeaning removes it by
       construction. So this does not replace the absolute test in replay.py --
       it answers a different question with far more power, and the two are
       complementary.
"""

import argparse
import math
import os
import random
import sys
from collections import defaultdict
from statistics import NormalDist, mean, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from settlewin import cond_mean as sw_cond_mean   # noqa: E402

ND = NormalDist()


# ===========================================================================
def series_of(ticker):
    return ticker.split("-")[0] if ticker else None


def timeseries_test(obs, label="absolute"):
    """obs: {series: {cluster: edge}}. Per-series mean edge, clustered on
    close-time. This is the design that suffers from the common factor."""
    out = {}
    for s, byc in obs.items():
        vals = list(byc.values())
        if len(vals) < 20:
            continue
        m = mean(vals)
        se = _mbb_se(byc) or float("inf")
        out[s] = {"mean": m, "n": len(vals), "se": se,
                  "t": m / se if se > 0 else 0.0}
    return out


def _mbb_se(byc, B=200, seed=20260828):
    """Moving-block-bootstrap SE of the mean over close-ordered clusters.

    The iid 1/sqrt(n) SE assumes independent clusters; consecutive crypto
    closes are neither independent (a maker's parameter error persists) nor
    homoskedastic (vol clusters). On this project's data a nominal-95% iid
    interval covered 69%. Same recipe as chain.py's block bootstrap.

    Prefix sums make each drawn block one subtraction, because the self-test
    calls this inside a 3-edge x 400-replication power harness: the naive
    list-slicing version turned a 90-second self-test into a timeout.
    """
    vals = [v for _c, v in sorted(byc.items())]
    n = len(vals)
    if n < 20:
        return None
    b = max(2, int(round(n ** (1.0 / 3.0))))
    starts = n - b + 1
    k = max(1, -(-n // b))
    cum = [0.0]
    for v in vals:
        cum.append(cum[-1] + v)
    bsum = [cum[i + b] - cum[i] for i in range(starts)]
    rng = random.Random(seed)
    pick = rng.randrange
    inv = 1.0 / (k * b)
    ms = []
    for _ in range(B):
        t = 0.0
        for _ in range(k):
            t += bsum[pick(starts)]
        ms.append(t * inv)
    return pstdev(ms)


def _median(xs):
    v = sorted(xs)
    n = len(v)
    if not n:
        return 0.0
    return v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2])


def _fit(by_cluster, exclude, min_series, centre):
    """One pass: centre each cluster on the series NOT in `exclude`."""
    resid = defaultdict(dict)
    for c, per in by_cluster.items():
        ref = [e for s, e in per.items() if s not in exclude]
        if len(ref) < min_series:
            continue
        mu = _median(ref) if centre == "median" else mean(ref)
        for s, e in per.items():
            resid[s][c] = e - mu
    out = {}
    for s, byc in resid.items():
        vals = list(byc.values())
        if len(vals) < 20:
            continue
        m = mean(vals)
        se = _mbb_se(byc) or float("inf")
        out[s] = {"mean": m, "n": len(vals), "se": se,
                  "t": m / se if se > 0 else 0.0}
    return out


def crosssection_test(obs, min_series=4, centre="median", max_rounds=3):
    """Same data, common factor removed, with outliers excluded from the
    reference they are being measured against.

    A relative test cannot on its own distinguish "S07 is +1c" from "the other
    eleven are -0.08c" -- with S series a single planted effect displaces every
    other by effect/(S-1) in the opposite direction. Measured: one +1c series
    produced FOUR false MISPRICED flags on a mean centre and TWO on a median.

    So identify the outliers, drop them from the centre, and recompute. After
    that the innocent series are measured against a benchmark the guilty one
    never touched. Convergence is capped at max_rounds and the excluded set is
    reported, because silently discarding data is its own failure mode."""
    by_cluster = defaultdict(dict)
    for s, byc in obs.items():
        for c, e in byc.items():
            by_cluster[c][s] = e
    n_series = len(obs)
    thresh = ND.inv_cdf(1 - 0.025 / max(n_series, 1))
    exclude = set()
    out = _fit(by_cluster, exclude, min_series, centre)
    for _ in range(max_rounds):
        flagged = {s for s, r in out.items() if abs(r["t"]) > thresh}
        if flagged == exclude or len(flagged) >= n_series - min_series:
            break
        exclude = flagged
        out = _fit(by_cluster, exclude, min_series, centre)
    return out, len(by_cluster), sorted(exclude)


def show(ts, xs, n_clusters, n_series, excluded=()):
    print(f"  {'series':>12}{'clusters':>10}"
          f"{'absolute edge':>15}{'t':>7}"
          f"{'relative edge':>16}{'t':>7}   verdict")
    thresh = ND.inv_cdf(1 - 0.025 / max(n_series, 1))
    gains = []
    for s in sorted(set(ts) | set(xs)):
        a, b = ts.get(s), xs.get(s)
        if not a or not b:
            continue
        if a["se"] > 0 and b["se"] > 0:
            gains.append(a["se"] / b["se"])
        v = ("MISPRICED vs peers" if abs(b["t"]) > thresh
             else "watch" if abs(b["t"]) > 2 else "in line")
        print(f"  {s:>12}{b['n']:>10}{100*a['mean']:>14.2f}c{a['t']:>7.1f}"
              f"{100*b['mean']:>15.2f}c{b['t']:>7.1f}   {v}")
    if gains:
        g = mean(gains)
        print(f"\n  measured power gain from demeaning: {g:.2f}x in t "
              f"({g*g:.1f}x in variance)")
    print(f"  Bonferroni |t| threshold for {n_series} series: {thresh:.2f}")
    if excluded:
        print(f"  excluded from the reference (measured against their peers "
              f"only): {list(excluded)}")
    print("  'relative' is edge minus the cross-sectional mean of that close")
    print("  time, so a mispricing common to ALL series is invisible here by")
    print("  construction -- that is what replay.py's absolute test is for.")


# ===========================================================================
def synth(n_clusters=600, n_series=12, rho=0.8, base_sd=0.02,
          bias=None, seed=1):
    """edge_i = common + idio_i, with the requested correlation, plus an
    optional per-series bias planted in one name."""
    rnd = random.Random(seed)
    names = [f"S{i:02d}" for i in range(n_series)]
    # rho = Var(common) / (Var(common) + Var(idio))
    v_common = rho * base_sd ** 2
    v_idio = (1 - rho) * base_sd ** 2
    obs = defaultdict(dict)
    for c in range(n_clusters):
        common = rnd.gauss(0.0, math.sqrt(v_common))
        for s in names:
            e = common + rnd.gauss(0.0, math.sqrt(v_idio))
            if bias and s == bias[0]:
                e += bias[1]
            obs[s][c] = e
    return dict(obs)


def selftest():
    print("=" * 78)
    print("SELF-TEST -- does demeaning actually buy the power it promises?")
    print("=" * 78)
    fails = []

    print("\n1. NULL: no series mispriced. Neither test may fire.")
    obs = synth(seed=3)
    ts = timeseries_test(obs)
    xs, nc, excl = crosssection_test(obs)
    show(ts, xs, nc, 12, excl)
    thresh = ND.inv_cdf(1 - 0.025 / 12)
    n_fire = sum(1 for s in xs if abs(xs[s]["t"]) > thresh)
    if n_fire:
        fails.append(f"cross-section flagged {n_fire} series under the null")

    print("\n2. ONE SERIES mispriced by 1.0c against its peers.")
    obs = synth(bias=("S07", 0.010), seed=3)
    ts = timeseries_test(obs)
    xs, nc, excl = crosssection_test(obs)
    show(ts, xs, nc, 12, excl)
    if abs(xs.get("S07", {}).get("t", 0)) < thresh:
        fails.append("cross-section MISSED a planted 1.0c relative mispricing")
    if abs(ts.get("S07", {}).get("t", 0)) > abs(xs["S07"]["t"]):
        fails.append("the absolute test beat the cross-sectional one")
    contaminated = [s for s in xs
                    if s != "S07" and abs(xs[s]["t"]) > thresh]
    print(f"\n  innocent series wrongly flagged: {len(contaminated)} "
          f"{contaminated if contaminated else ''}")
    if contaminated:
        fails.append(f"one planted effect contaminated {len(contaminated)} "
                     "innocent series -- the centre is not robust")

    print("\n3. POWER at 400 replications, by planted edge size.")
    print(f"  {'planted':>10}{'clusters':>10}{'absolute finds it':>20}"
          f"{'relative finds it':>20}")
    for edge in (0.002, 0.005, 0.010):
        for ncl in (300,):
            hit_a = hit_x = 0
            R = 400
            for r in range(R):
                o = synth(n_clusters=ncl, bias=("S07", edge), seed=5000 + r)
                a = timeseries_test(o).get("S07")
                x, _, _ = crosssection_test(o)
                x = x.get("S07")
                if a and abs(a["t"]) > thresh:
                    hit_a += 1
                if x and abs(x["t"]) > thresh:
                    hit_x += 1
            print(f"  {100*edge:>9.1f}c{ncl:>10}{100*hit_a/R:>19.0f}%"
                  f"{100*hit_x/R:>19.0f}%")
    print("\n  A 0.5c relative mispricing is invisible to the absolute test and")
    print("  routine for the cross-sectional one. That is the whole point: the")
    print("  correlation that costs power in one design supplies it in the")
    print("  other.")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- silent under the null, finds a planted relative")
    print("mispricing, and the measured power gain matches the argument.")
    return True


# ===========================================================================
def build_obs(data_dir, out_dir, ttc_points=(600, 300, 120, 60, 30)):
    """Real data: model-minus-market at fixed times to close, per series,
    keyed by close-time cluster."""
    from replay import load_index, load_quotes, load_markets, SERIES_TO_INDEX
    from engine import var_factor, N_AVG
    index = load_index(data_dir)
    if not index:
        print("  no cfbenchmarks_value -- cannot compute a model. Run doctor.py")
        return {}
    quotes = load_quotes(data_dir)
    if not quotes:
        try:
            from book import rebuild
            quotes, _ = rebuild(data_dir)
        except Exception:
            quotes = {}
    markets = load_markets(out_dir)
    # CAUSAL variance: prefix sums of squared one-second increments, so each
    # market is priced with only the ticks a trader at its cut had. The old
    # code computed one full-sample g0 per index and used it for every
    # market, handing the model a realised quantity -- a vol episode anywhere
    # in the sample re-priced markets that closed before it happened.
    gpre = {}
    for iid, ticks in index.items():
        secs = sorted(ticks)
        ts_, cum, cnt = [], [0.0], [0]
        for a, b in zip(secs, secs[1:]):
            if b - a == 1:
                ts_.append(b)
                cum.append(cum[-1] + (ticks[b] - ticks[a]) ** 2)
                cnt.append(cnt[-1] + 1)
        gpre[iid] = (ts_, cum, cnt)

    def g0_at(iid, cut):
        pre = gpre.get(iid)
        if not pre:
            return None
        ts_, cum, cnt = pre
        import bisect
        i = bisect.bisect_right(ts_, cut)
        if cnt[i] < 200:
            return None
        return cum[i] / cnt[i]

    obs = defaultdict(dict)
    for tk, q in quotes.items():
        m = markets.get(tk)
        if not m:
            continue
        ser = m.get("series") or series_of(tk)
        iid = SERIES_TO_INDEX.get(ser)
        ticks = index.get(iid)
        if not ticks:
            continue
        close_s = int(round(m["close"]))
        qq = {t: (b + a) / 2.0 for t, b, a, _, _ in q}
        for ttc in ttc_points:
            cut = close_s - ttc
            prev = None
            for t in sorted(qq):
                if t <= cut:
                    prev = qq[t]
                else:
                    break
            if prev is None or cut not in ticks:
                continue
            mu = sw_cond_mean(ticks, close_s, cut, ticks[cut])
            if mu is None:
                continue          # too many missing ticks to trust the window
            vf = var_factor(ttc, [1.0])
            if vf <= 0:
                continue
            gv = g0_at(iid, cut)
            if not gv or gv <= 0:
                continue
            fair = 1.0 - ND.cdf((m["strike"] - mu) / math.sqrt(vf * gv))
            obs[ser].setdefault(close_s, []).append(fair - prev)
    # ONE observation per (series, close). The five ttc reads of a market are
    # five reads of the same mispricing settling on the same outcome -- the
    # docstring always said "keyed by close-time cluster" while the key was
    # (close_s, ttc), quintupling n and inflating every t by ~sqrt(5).
    return {ser: {c: mean(v) for c, v in byc.items()}
            for ser, byc in obs.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--out", default="./fulltape")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed")

    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    obs = build_obs(a.data, a.out)
    if not obs:
        print("  nothing to compare.")
        return
    print(f"  {len(obs)} series, "
          f"{sum(len(v) for v in obs.values()):,} series-observations")
    ts = timeseries_test(obs)
    xs, nc, excl = crosssection_test(obs)
    if not xs:
        print("  too few clusters with enough simultaneous series.")
        return
    print("\n" + "=" * 78)
    print("ABSOLUTE vs RELATIVE MISPRICING")
    print("=" * 78)
    show(ts, xs, nc, len(obs), excl)
    print("\n  A series flagged MISPRICED vs peers is the most tradeable shape")
    print("  available here: hedge it against the rest of the complex and the")
    print("  common crypto move -- the thing you cannot forecast -- cancels.")


if __name__ == "__main__":
    main()
