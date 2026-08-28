#!/usr/bin/env python3
# VERSION: 2026-08-25-l1
"""
leadlag.py -- does the contract FOLLOW the index? The #1 candidate edge.

    python research/leadlag.py --selftest
    python research/leadlag.py --data ./kalshi_data --out ./fulltape

WHY THIS ONE FIRST

PLAN_V3 sec.3 ranks stale quotes above everything else, because it is a
plumbing artefact rather than a pricing opinion: if the book lags the index you
already know where the contract is going, with no forecast of anything. And
because settlement is a 60-SECOND AVERAGE, exploiting it does not require
winning a latency race -- only a better read on a slow-moving mean. Measured
latency to this machine is 37ms median against a colocated firm's ~1-5ms, which
is nothing against a 60-second average.

THE RIGHT REGRESSOR -- and it is not the index

The naive test cross-correlates contract price changes against INDEX changes.
That is wrong, because the contract's sensitivity to the index is not constant:

    d(fair)/d(spot) = phi(z)/sd * (r_live / 60)

It depends on moneyness, on time to close, and -- inside the last minute -- on
how many settlement ticks are still live. A $50 index move with 10 seconds left
moves fair settlement by $8.33, not $50. So a raw cross-correlation mixes a
real lag together with a varying transmission coefficient and cannot separate
them.

Instead: convert each index tick into the FAIR VALUE it implies, using the
verified model, and regress the book's move on the fair value's move.

    d_mid(t)  =  beta_k * d_fair(t - k)  +  noise

    beta peaks at k = 0   -> the book tracks the index in real time. Dead end.
    beta peaks at k > 0   -> the book FOLLOWS. Mechanical edge, no forecasting.
    sum of beta over k    -> how much of a move the book EVER incorporates.
                             Less than 1 means it permanently under-reacts,
                             which is a different and also tradeable defect.

CUMULATIVE RESPONSE IS THE MONEY STATISTIC
If the book has incorporated only 60% of a fair-value move after one second and
100% after five, then for roughly five seconds there is 40% of that move sitting
in front of you. That is what the last table prints.

CLUSTERING
On close-time, never on ticker: the 12 series close simultaneously and are ~0.8
correlated, so ticker-level clustering would inflate t by roughly 10x.
"""

import argparse
import math
import os
import random
import sys
from collections import defaultdict
from statistics import NormalDist, mean, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tdist import p_two_sided, crit                       # noqa: E402
from engine import var_factor, N_AVG                     # noqa: E402
from replay import (load_index, load_quotes, load_markets,  # noqa: E402
                    SERIES_TO_INDEX, series_of)

ND = NormalDist()
LAGS = list(range(-4, 11))          # negative = book LEADS the index


# ===========================================================================
def fair_series(ticks, strike, close_s, lo_s, hi_s, gamma0, rho=(1.0,)):
    """fair value implied by the index at each second in [lo_s, hi_s]."""
    out = {}
    run_lo = close_s - N_AVG + 1
    locked_sum, locked_n = 0.0, 0
    for s in range(lo_s, hi_s + 1):
        v = ticks.get(s)
        if v is None:
            continue
        if run_lo <= s <= close_s:
            locked_sum += v
            locked_n += 1
        r = N_AVG - locked_n
        mu = (locked_sum + r * v) / N_AVG
        vf = var_factor(close_s - s, list(rho))
        if vf <= 0:
            continue
        sd = math.sqrt(vf * gamma0)
        if sd <= 0:
            continue
        out[s] = 1.0 - ND.cdf((strike - mu) / sd)
    return out


def mids(quotes_for_ticker):
    out = {}
    for (t, bid, ask, bs, as_) in quotes_for_ticker:
        out[t] = (bid + ask) / 2.0
    return out


def regress_lags(pairs_by_lag):
    """OLS slope through the origin per lag, clustered on close-time.

    Through the origin because both series are changes: a nonzero intercept
    would be a drift in the contract price unrelated to the index, which is not
    what is being asked."""
    out = {}
    for k, rows in sorted(pairs_by_lag.items()):
        if len(rows) < 200:
            continue
        num = sum(x * y for x, y, _ in rows)
        den = sum(x * x for x, _, _ in rows)
        if den <= 0:
            continue
        beta = num / den
        # cluster on close-time: one contribution per cluster
        by = defaultdict(lambda: [0.0, 0.0])
        for x, y, c in rows:
            by[c][0] += x * y
            by[c][1] += x * x
        cl = [n / d for n, d in by.values() if d > 0]
        if len(cl) < 10:
            continue
        m, sd = mean(cl), pstdev(cl)
        se = sd / math.sqrt(len(cl)) if sd > 0 else float("inf")
        out[k] = {"beta": beta, "clusters": len(cl), "n": len(rows),
                  "t": m / se if se > 0 else 0.0}
    return out


def build_pairs(index, quotes, markets, max_markets=None, gamma_by_index=None):
    pairs = defaultdict(list)
    used = 0
    for tk, q in quotes.items():
        m = markets.get(tk)
        if not m:
            continue
        iid = SERIES_TO_INDEX.get(m.get("series") or series_of(tk))
        ticks = index.get(iid)
        if not ticks:
            continue
        close_s = int(round(m["close"]))
        mm = mids(q)
        if len(mm) < 60:
            continue
        lo_s, hi_s = min(mm), max(mm)
        g0 = (gamma_by_index or {}).get(iid)
        if not g0:
            continue
        fv = fair_series(ticks, m["strike"], close_s,
                         lo_s - max(LAGS) - 2, hi_s, g0)
        if len(fv) < 60:
            continue
        dmid = {t: mm[t] - mm[t - 1] for t in mm if (t - 1) in mm}
        dfv = {t: fv[t] - fv[t - 1] for t in fv if (t - 1) in fv}
        for k in LAGS:
            for t, dy in dmid.items():
                dx = dfv.get(t - k)
                if dx is None or dx == 0.0:
                    continue
                pairs[k].append((dx, dy, close_s))
        used += 1
        if max_markets and used >= max_markets:
            break
    return pairs, used


def gamma0_from_index(ticks, sample=200_000):
    secs = sorted(ticks)
    d = [ticks[b] - ticks[a] for a, b in zip(secs, secs[1:]) if b - a == 1]
    d = d[:sample]
    if len(d) < 100:
        return None
    m = mean(d)
    return sum((x - m) ** 2 for x in d) / len(d)


def report(res, label):
    if not res:
        print(f"  {label}: not enough data")
        return None
    # The standard error is built from the close-time clusters, so this is a
    # t on (clusters - 1) degrees of freedom. With a few dozen clusters -- and
    # clusters arrive at four an hour, so a day of recording is 96 -- the gap
    # from the normal is not negligible at the thresholds used here.
    print(f"  {'lag':>6}{'beta':>10}{'t':>8}{'df':>5}{'p (t)':>10}"
          f"{'clusters':>10}{'obs':>10}")
    best = max(res, key=lambda k: res[k]["beta"])
    for k in sorted(res):
        r = res[k]
        df = max(r["clusters"] - 1, 1)
        mark = "  <== peak" if k == best else ""
        print(f"  {k:>+6}{r['beta']:>10.3f}{r['t']:>8.1f}{df:>5}"
              f"{p_two_sided(r['t'], df):>10.4f}"
              f"{r['clusters']:>10}{r['n']:>10,}{mark}")
    tot = sum(r["beta"] for r in res.values())
    bdf = max(res[best]["clusters"] - 1, 1)
    print(f"\n  peak at lag {best:+d}s   sum of beta over all lags = {tot:.3f}")
    print(f"  |t| for p<0.05 on t({bdf}) is {crit(0.05, bdf):.2f}; and see")
    print(f"  power.py -- one go.py run emits several hundred statistics, so")
    print(f"  the threshold that matters is a long way above that.")
    if best > 0:
        print("  -> THE BOOK FOLLOWS THE INDEX. That is a mechanical edge:")
        print("     the fair value has already moved and the quote has not.")
    elif best == 0:
        print("  -> the book tracks the index within a second. No timing edge.")
    else:
        print("  -> the book LEADS the index, which would mean the quote knows")
        print("     something the index has not printed yet. Suspect the")
        print("     timestamps before believing it.")
    if tot < 0.85:
        print(f"  -> and it only ever incorporates {100*tot:.0f}% of a move --")
        print("     a permanent under-reaction, separately tradeable.")
    return {"peak": best, "sum_beta": tot}


def value_of_lead(sigma_1s, zs=(0.0, 0.67, 1.28)):
    """What is ONE SECOND of lead on the index worth, in cents?

    A one-second index move of sigma_1s shifts the settlement mean by
    (r_live/60)*sigma_1s, and a shift in the mean moves fair value by
    phi(z)/sd. So:

        value = phi(z) * (r_live/60) * sigma_1s / sd(tau)

    This is why the lag profile above matters so much near expiry: sd(tau)
    collapses as tau^1.5 inside the averaging window while r_live/60 only falls
    linearly, so the value of being early RISES as the close approaches. It is
    also why the engine refuses to trade inside 15 seconds -- that is where the
    edge is largest and where a home connection is least likely to win the
    race for it.
    """
    print("\n" + "=" * 78)
    print("WHAT ONE SECOND OF LEAD IS WORTH")
    print("=" * 78)
    print(f"  index sd = {sigma_1s:.4f} per second. Multiply by the measured")
    print("  lag above to get the size of the standing mispricing.\n")
    print(f"  {'ttc':>6}{'r_live':>8}{'sd(tau)':>10}" +
          "".join(f"{f'z={z:.2f}':>11}" for z in zs))
    for tau in (600, 300, 180, 120, 90, 60, 45, 30, 20, 15):
        r_live = min(tau, N_AVG)
        sd = math.sqrt(var_factor(tau, [1.0])) * sigma_1s
        if sd <= 0:
            continue
        row = f"  {tau:>6}{r_live:>8}{sd:>10.2f}"
        for z in zs:
            phi = math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)
            row += f"{100 * phi * (r_live / 60.0) * sigma_1s / sd:>10.2f}c"
        print(row)
    print("\n  z=0 is a coin-flip contract, z=1.28 is a 90c favourite.")
    print("  Compare against the cost bar: ~2.25pp at 50c, ~0.38pp at 95c.")


def cumulative(res):
    print(f"\n  CUMULATIVE RESPONSE -- how much of a fair-value move the book")
    print(f"  has incorporated by k seconds. The shortfall is what is sitting")
    print(f"  in front of you for that long.\n")
    print(f"  {'by k=':>8}{'incorporated':>15}{'left on the table':>20}")
    run = 0.0
    for k in sorted(x for x in res if x >= 0):
        run += res[k]["beta"]
        print(f"  {k:>8}{100*run:>14.1f}%{100*max(0.0, 1 - run):>19.1f}%")


# ===========================================================================
def selftest():
    import tempfile, shutil
    from replay import make_fake_collector
    print("=" * 78)
    print("SELF-TEST -- can it recover a lag it was given?")
    print("=" * 78)
    print("  make_fake_collector quotes a maker whose view of spot is delayed")
    print("  by a known number of seconds. The peak beta must land on it.\n")
    fails = []
    for want in (0, 3, 8):
        tmp = tempfile.mkdtemp()
        try:
            mk = make_fake_collector(tmp, n_markets=60, seed=5, lag=want)
            idx = load_index(tmp, verbose=False)
            qs = load_quotes(tmp, verbose=False)
            g = {k: gamma0_from_index(v) for k, v in idx.items()}
            pairs, used = build_pairs(idx, qs, mk, gamma_by_index=g)
            res = regress_lags(pairs)
            if not res:
                fails.append(f"no regression output at injected lag {want}")
                continue
            print(f"  injected lag {want}s   ({used} markets)")
            got = report(res, f"lag={want}")
            if got and got["peak"] != want:
                fails.append(f"injected lag {want}s, recovered "
                             f"{got['peak']}s")
            print()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print("=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- the peak lands on the injected lag every time,")
    print("including zero.")
    return True


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

    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    index = load_index(a.data)
    if not index:
        print("\n  No cfbenchmarks_value data -- this test is impossible "
              "without it.")
        return
    quotes = load_quotes(a.data)
    markets = load_markets(a.out)
    g = {k: gamma0_from_index(v) for k, v in index.items()}
    for k, v in sorted(g.items()):
        if v:
            print(f"    {k:>13}: sd per second {math.sqrt(v):.4f}")
    pairs, used = build_pairs(index, quotes, markets, gamma_by_index=g)
    print(f"\n  {used:,} markets contributed")
    if not pairs:
        print("  Nothing to regress. Need markets with BOTH recorded quotes and")
        print("  a settled strike -- check that fulltape/markets.json is fresh.")
        return
    print("\n" + "=" * 78)
    print("LAG PROFILE  d_mid(t) = beta_k * d_fair(t-k)")
    print("=" * 78)
    res = regress_lags(pairs)
    got = report(res, "real")
    if res:
        cumulative(res)
    # BRTI's gamma, labelled as BRTI. max() over per-index variances in each
    # index's OWN price units always returned BRTI's (~10^12 above DOGE's),
    # and it was then printed unlabelled as "index sd" with an instruction to
    # multiply -- wrong by up to six orders of magnitude for eleven of the
    # twelve series. The cents table itself was safe (sigma cancels); only
    # this header lied.
    if g.get("BRTI"):
        print("\n  (per-second sd below is BRTI/BTC only; other series scale"
              " differently)")
        value_of_lead(math.sqrt(g["BRTI"]))
    print("\n  Caveats: mid is quantized to the tick grid, which adds noise to")
    print("  the dependent variable but does not bias the slope. A peak at a")
    print("  negative lag almost certainly means a clock problem, not")
    print("  prescience -- RUNBOOK notes the collector stamps three different")
    print("  clocks (CF `time`, Kalshi `received_at`, local `_rx_ms`).")


if __name__ == "__main__":
    main()
