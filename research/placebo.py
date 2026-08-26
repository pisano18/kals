#!/usr/bin/env python3
# VERSION: 2026-08-25-p1
"""
placebo.py -- what does the calibration estimator return when the market IS
efficient? Answering that makes the existing 450-market result readable.

    python research/placebo.py --selftest
    python research/placebo.py --out ./fulltape --reps 400

THE PROBLEM (R4)

RUNBOOK's headline is "mean t across 71 cells = -0.008, therefore efficient."
That compares the estimator's output to ZERO. R4 showed the estimator does not
return zero on an efficient market: on a synthetic book quoting the true model
exactly, kalshi_fulltape.py's calibration() returns mean t = -1.03, because how
long a price path lingers near a level is correlated with where it ends up.

But R4's synthetic trades arrived on a fixed 7-second cadence and real ones do
not. So R4 establishes that a bias EXISTS, not its size on real data.

THE FIX -- and it needs no new data

Take the real markets, the real trades, the real timestamps, the real prices.
Change exactly one thing: the OUTCOME.

    y ~ Bernoulli(p_last)

where p_last is that market's final observed price. Under the efficient-market
null the price is a martingale with E[y | F_t] = p_t, so

    E[y | p_t] = E[ E[y | p_last] | p_t ] = E[p_last | p_t] = p_t

for EVERY t. The redrawn outcomes are exactly consistent with efficiency at
every point on every path, while every source of selection -- when trades
arrive, how long a path lingers, which markets trade at all -- is preserved
bit-for-bit, because it is the real data.

Run the estimator R times on redrawn outcomes and you get the null
distribution. Anything the estimator reports there is bias, by construction.
Then ask where the REAL outcomes fall in it. That is the p-value the project
has been missing.

WHY THIS IS BETTER THAN SIMULATING PATHS
Simulating index paths and reusing real timestamps would break the dependence
between arrival times and the price path -- which is the exact mechanism that
creates the bias. It would understate it. Redrawing only the outcome preserves
that dependence perfectly.

WHAT A RESULT MEANS
  observed inside the null band  -> no evidence of inefficiency. And, crucially,
                                    no evidence of efficiency either: report the
                                    band, since it bounds what could be hiding.
  observed outside the band      -> a real deviation, already corrected for
                                    every selection effect in the tape.
"""

import argparse
import json
import math
import os
import random
from collections import defaultdict
from datetime import datetime, timezone
from statistics import NormalDist, mean, pstdev

ND = NormalDist()


def parse_ts(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s if s < 1e12 else s / 1000.0)
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


# ===========================================================================
# the estimator under test -- kalshi_fulltape.py calibration(), verbatim
# ===========================================================================
def time_bucket(ttc):
    return ("0-60s" if ttc <= 60 else "60-180s" if ttc <= 180 else
            "180-480s" if ttc <= 480 else "480-900s")


def build_cells(paths):
    """paths: {ticker: [(ttc, price)]}. Returns cell -> {ticker: [prices]}.
    Built ONCE; only the outcome map changes between replications, which is what
    makes 400 reps cheap."""
    cells = defaultdict(lambda: defaultdict(list))
    for tk, pts in paths.items():
        for ttc, p in pts:
            key = (time_bucket(ttc), round(min(max(p, .01), .99) * 20) / 20.0)
            cells[key][tk].append(p)
    return cells


def run_estimator(cells, outcome, min_markets=40):
    """Exactly kalshi_fulltape.py's calibration(): per-market price average
    within a cell, one observation per market, binomial SE on market count."""
    ts, edges, flagged = [], [], 0
    for key in sorted(cells, key=lambda k: (k[0], k[1])):
        pm = cells[key]
        obs = [(sum(v) / len(v), outcome[tk]) for tk, v in pm.items()
               if tk in outcome]
        n = len(obs)
        if n < min_markets:
            continue
        e = mean([o - p for p, o in obs])
        real = mean([o for _, o in obs])
        ph = min(max(real, 1.0 / (n + 2)), 1 - 1.0 / (n + 2))
        se = math.sqrt(ph * (1 - ph) / n)
        t = e / se if se > 0 else 0.0
        ts.append(t)
        edges.append(e)
        if abs(t) > 3 and abs(e) > 0.02:
            flagged += 1
    if not ts:
        return None
    return {"cells": len(ts), "mean_t": mean(ts),
            "sd_t": pstdev(ts) if len(ts) > 1 else 0.0,
            "n_ge2": sum(1 for t in ts if abs(t) >= 2),
            "max_abs_t": max(abs(t) for t in ts),
            "flagged": flagged, "mean_edge": mean(edges)}


# ===========================================================================
def load_fulltape(out_dir):
    markets = json.load(open(os.path.join(out_dir, "markets.json"), encoding="utf-8"))
    tapes = json.load(open(os.path.join(out_dir, "tapes.json"), encoding="utf-8"))
    idx = {}
    for s, ms in markets.items():
        for m in ms:
            idx[m["ticker"]] = m
    paths = defaultdict(list)
    for s, ts in tapes.items():
        for t in ts:
            tk = t.get("ticker") or t.get("market_ticker")
            m = idx.get(tk)
            if not m:
                continue
            raw = t.get("yes_price_dollars")
            if raw is not None:
                p = float(raw)
            else:
                raw = t.get("yes_price")
                if raw is None:
                    continue
                p = float(raw) / 100.0        # websocket/REST price is CENTS
            tt = parse_ts(t.get("created_time") or t.get("ts"))
            if tt is None or not (0 < p < 1):
                continue
            ttc = m["close"] - tt
            if 0 <= ttc <= 900:
                paths[tk].append((ttc, p))
    for v in paths.values():
        v.sort(key=lambda x: -x[0])           # chronological
    return idx, dict(paths)


def null_distribution(cells, paths, reps, seed=0, verbose=True):
    """Redraw outcomes under the efficient-market null and re-run."""
    rnd = random.Random(seed)
    p_last = {tk: pts[-1][1] for tk, pts in paths.items() if pts}
    keys = sorted(p_last)
    acc = defaultdict(list)
    for r in range(reps):
        oc = {tk: (1.0 if rnd.random() < p_last[tk] else 0.0) for tk in keys}
        res = run_estimator(cells, oc)
        if res:
            for k, v in res.items():
                acc[k].append(v)
        if verbose and (r + 1) % max(reps // 10, 1) == 0:
            print(f"    {r+1}/{reps}", end="\r", flush=True)
    if verbose:
        print("           ", end="\r")
    return acc


def band(vals, lo=2.5, hi=97.5):
    v = sorted(vals)
    if not v:
        return (float("nan"),) * 3
    return (v[int(len(v) * lo / 100)], mean(v), v[min(int(len(v) * hi / 100),
                                                      len(v) - 1)])


def pct_of(vals, x):
    v = sorted(vals)
    return 100.0 * sum(1 for y in v if y <= x) / max(len(v), 1)


def report(observed, nulls, label):
    print(f"\n  {label}")
    print(f"  {'statistic':>14}{'observed':>11}{'null 2.5%':>12}"
          f"{'null mean':>12}{'null 97.5%':>12}{'pctile':>9}   verdict")
    rows = [("mean t", "mean_t"), ("sd of t", "sd_t"),
            ("cells |t|>=2", "n_ge2"), ("max |t|", "max_abs_t"),
            ("mean edge", "mean_edge")]
    out = {}
    for name, key in rows:
        if key not in nulls or observed is None:
            continue
        lo, mu, hi = band(nulls[key])
        ob = observed[key]
        pc = pct_of(nulls[key], ob)
        v = "inside null" if lo <= ob <= hi else "*** OUTSIDE ***"
        fmt = ".3f" if key != "n_ge2" else ".1f"
        print(f"  {name:>14}{ob:>11{fmt}}{lo:>12{fmt}}{mu:>12{fmt}}"
              f"{hi:>12{fmt}}{pc:>8.1f}%   {v}")
        out[key] = (ob, lo, mu, hi, pc)
    n_out = sum(1 for v in out.values() if not (v[1] <= v[0] <= v[3]))
    print(f"  {n_out} of {len(out)} statistics outside their 95% band "
          f"(expect {0.05*len(out):.2f} by chance). A single marginal flag is"
          f" noise;\n  a finding is several statistics agreeing, or one far "
          f"outside.")
    return out


# ===========================================================================
def synth_paths(n_markets, n_pts, inefficiency=0.0, seed=1):
    """Realistic-ish tapes: a martingale price path per market with trade
    arrivals CLUSTERED toward the close, which is what the real tape looks like
    and what drives the occupation-time selection.

    inefficiency: shifts the true outcome probability away from the final price
    by this many probability points (0 = efficient)."""
    rnd = random.Random(seed)
    paths, truth = {}, {}
    for i in range(n_markets):
        tk = f"SYN-{i:05d}"
        p = 0.5
        pts = []
        # arrivals clustered near close: more trades as ttc shrinks
        times = sorted((900 * (rnd.random() ** 2.2) for _ in range(n_pts)),
                       reverse=True)
        prev_t = 900.0
        for tt in times:
            dt = max(prev_t - tt, 0.0)
            prev_t = tt
            # martingale in probability space: step sd scales with sqrt(dt)
            # and with p(1-p) so it cannot leave [0,1]
            s = 0.055 * math.sqrt(max(dt, 1e-9) / 60.0) * max(p * (1 - p), 0.01) * 4
            p = min(max(p + rnd.gauss(0, s), 0.005), 0.995)
            pts.append((tt, round(p * 100) / 100.0))
        paths[tk] = pts
        pt = min(max(pts[-1][1] + inefficiency, 0.001), 0.999)
        truth[tk] = 1.0 if rnd.random() < pt else 0.0
    return paths, truth


def selftest():
    print("=" * 78)
    print("SELF-TEST -- does the placebo separate bias from real inefficiency?")
    print("=" * 78)
    fails = []

    print("\n1. EFFICIENT synthetic market (truth: no edge whatsoever)")
    paths, truth = synth_paths(1200, 90, inefficiency=0.0, seed=7)
    cells = build_cells(paths)
    obs = run_estimator(cells, truth)
    nulls = null_distribution(cells, paths, reps=300, seed=11)
    print(f"   NAIVE reading: mean t = {obs['mean_t']:+.3f}, "
          f"{obs['n_ge2']} cells |t|>=2 of {obs['cells']}")
    print(f"   -- compared to zero, that alone would be read as a finding "
          f"either way.")
    r1 = report(obs, nulls, "against the CALIBRATED null")
    if "mean_t" in r1:
        _, lo, mu, hi, _ = r1["mean_t"]
        if not (lo <= obs["mean_t"] <= hi):
            fails.append("placebo flagged an efficient market as inefficient")
        if abs(mu) < 0.15:
            print(f"\n   note: null mean t = {mu:+.3f} -- on THIS arrival "
                  f"process the estimator is close to unbiased.")

    print("\n\n2. INEFFICIENT synthetic market (+4pp planted at every close)")
    paths2, truth2 = synth_paths(1200, 90, inefficiency=0.04, seed=7)
    cells2 = build_cells(paths2)
    obs2 = run_estimator(cells2, truth2)
    nulls2 = null_distribution(cells2, paths2, reps=300, seed=13)
    r2 = report(obs2, nulls2, "against the CALIBRATED null")
    if "mean_t" in r2:
        _, lo, mu, hi, _ = r2["mean_t"]
        if lo <= obs2["mean_t"] <= hi:
            fails.append("placebo MISSED a planted +4pp inefficiency")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- the placebo leaves an efficient market inside")
    print("the band and pushes a planted inefficiency outside it.")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="./fulltape")
    ap.add_argument("--reps", type=int, default=400)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed; refusing to touch real data")

    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    if not os.path.exists(os.path.join(a.out, "markets.json")):
        print(f"  no markets.json in {a.out} -- nothing to do.")
        return
    idx, paths = load_fulltape(a.out)
    npts = sum(len(v) for v in paths.values())
    print(f"  {len(paths):,} markets with usable tapes, {npts:,} prints, "
          f"{npts/max(len(paths),1):.0f}/market")
    lasts = sorted(v[-1][0] for v in paths.values() if v)
    if lasts:
        print(f"  time-to-close of last print: median {lasts[len(lasts)//2]:.0f}s "
              f"p90 {lasts[int(len(lasts)*.9)]:.0f}s")
        print("  (the null draws y ~ Bernoulli(last price); a late last print")
        print("   makes that a tight null, an early one makes it conservative)")

    outcome = {tk: m["result"] for tk, m in idx.items() if tk in paths}
    cells = build_cells(paths)
    obs = run_estimator(cells, outcome)
    if not obs:
        print("  no cells met the 40-market minimum.")
        return
    print(f"\n  REPRODUCING the existing headline on real outcomes:")
    print(f"    cells={obs['cells']}  mean t={obs['mean_t']:+.3f}  "
          f"sd t={obs['sd_t']:.3f}  |t|>=2: {obs['n_ge2']}  "
          f"flagged={obs['flagged']}")
    print(f"    RUNBOOK reports: 71 cells, mean t -0.008, sd 0.775, 3 at |t|>=2")

    print(f"\n  building the null from {a.reps} redraws ...")
    nulls = null_distribution(cells, paths, reps=a.reps, seed=99)
    report(obs, nulls, "REAL OUTCOMES vs THE EFFICIENT-MARKET NULL")

    print("\n  HOW TO READ THIS")
    print("   Every selection effect in the tape -- arrival clustering,")
    print("   occupation time, which markets trade at all -- is present in both")
    print("   columns, because the null reuses the real tape and changes only")
    print("   the outcome. So the null band IS the estimator's behaviour under")
    print("   efficiency, and 'inside the band' is the only honest way to say")
    print("   'no evidence of an edge'. Comparing mean t to 0 was never valid.")
    print("\n   If observed sits inside: the band width bounds what could still")
    print("   be hiding. Report that width, not the word 'efficient'.")


if __name__ == "__main__":
    main()
