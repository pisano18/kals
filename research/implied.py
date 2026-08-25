#!/usr/bin/env python3
# VERSION: 2026-08-25-i1
"""
implied.py -- stop asking "is the market wrong". Ask what the market believes.

    python research/implied.py --selftest
    python research/implied.py --data ./kalshi_data --out ./fulltape

THE REFRAME

Every other test here compares a price to an OUTCOME, which means waiting for
settlements and spending statistical power on a single Bernoulli bit per window.
But the price already contains the market's own volatility assumption, and it can
simply be read out:

    P = Phi( (mu - K) / sd )      =>      sd = (mu - K) / Phi^-1(P)

with mu the settlement mean implied by the index and K the strike, both known.
Divide by the model's variance factor and you have the market's IMPLIED SIGMA at
that instant.

No outcomes. No waiting. Every quote in the recording is one observation, so
seven hours of data gives tens of thousands of them instead of a few hundred
settlements.

WHAT THE SHAPE OF THAT SURFACE REVEALS -- none of which needs anyone to be wrong

  LEVEL: implied vs realised sigma is the variance risk premium. If implied sits
  persistently above realised, sellers of these contracts are being PAID to carry
  variance risk -- exactly like the equity VRP. That is a risk premium, not an
  error, which is why it would persist. Being paid it is a real strategy.

  TERM STRUCTURE: under the confirmed settlement rule, implied sigma should be
  FLAT across time-to-close. Any tilt means the market is using a different
  variance formula than the one derived in settlement_math.py. And note the
  specific shape to look for: if the market used `tau + 20` where the truth is
  `tau - 39.5` -- the exact error found in RUNBOOK -- implied sigma would sag
  toward expiry in a predictable way. This test would catch that.

  SMILE: implied sigma flat across moneyness means the market prices a Gaussian.
  A smile means it prices fat tails, and the CURVATURE says how fat. That
  settles PLAN sec.10.3 from prices alone, without needing a single settlement,
  and tells us whether the market has already priced what we would be trying to
  exploit.

  SKEW: a tilt between the yes side and the no side is directional pricing --
  or inventory. A maker long the complex shades quotes to shed it. That is not
  an error either; it is a chance to be paid for absorbing it.

  BY SERIES / BY HOUR: where the maker's attention is thin.

A read-out of beliefs is more neutral than a hunt for mistakes, and it points at
the risk-premium and segmentation edges rather than only at arithmetic slips.
"""

import argparse
import math
import os
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from statistics import NormalDist, mean, median, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from settlewin import cond_mean as sw_cond_mean   # noqa: E402
from engine import var_factor, N_AVG                      # noqa: E402

ND = NormalDist()

# Prices too close to the boundary invert unstably: Phi^-1 explodes and one tick
# of quantization becomes an enormous change in sigma. Stay where the inversion
# is well conditioned.
P_LO, P_HI = 0.06, 0.94


def implied_sigma(price, mu, strike, tau):
    """The sigma the market must be using to quote `price`. None where the
    inversion is ill-conditioned."""
    if not (P_LO <= price <= P_HI):
        return None
    z = ND.inv_cdf(price)
    if abs(z) < 1e-9:
        return None                      # at 50c the price carries no sigma info
    vf = var_factor(tau, [1.0])
    if vf <= 0:
        return None
    sd = (mu - strike) / z
    if sd <= 0:
        return None
    return sd / math.sqrt(vf)


def collect(index, quotes, markets, series_to_index, ttc_max=900):
    """One row per (market, second) with a usable inversion."""
    rows = []
    for tk, q in quotes.items():
        m = markets.get(tk)
        if not m:
            continue
        iid = series_to_index.get(m.get("series") or tk.split("-")[0])
        ticks = index.get(iid)
        if not ticks:
            continue
        close_s = int(round(m["close"]))
        strike = m.get("strike")
        if not strike:
            continue
        lo_run = close_s - N_AVG + 1
        for (t, bid, ask, bs, as_) in q:
            tau = close_s - t
            if not (1 <= tau <= ttc_max) or t not in ticks:
                continue
            spot = ticks[t]
            mu = sw_cond_mean(ticks, close_s, t, spot)
            if mu is None:
                continue
            mid = (bid + ask) / 2.0
            iv = implied_sigma(mid, mu, strike, tau)
            if iv is None:
                continue
            rows.append({"series": m.get("series") or tk.split("-")[0],
                         "tau": tau, "price": mid, "iv": iv, "close": close_s,
                         "spread": ask - bid,
                         "z": (mu - strike) / max(math.sqrt(
                             var_factor(tau, [1.0])) * iv, 1e-12)})
    return rows


def realised_sigma(index):
    out = {}
    for iid, ticks in index.items():
        secs = sorted(ticks)
        d = [ticks[b] - ticks[a] for a, b in zip(secs, secs[1:]) if b - a == 1]
        if len(d) < 200:
            continue
        m = mean(d)
        out[iid] = math.sqrt(sum((x - m) ** 2 for x in d) / len(d))
    return out


def _clustered(vals_by_cluster):
    obs = [mean(v) for v in vals_by_cluster.values()]
    if len(obs) < 5:
        return None
    m, sd = mean(obs), pstdev(obs)
    se = sd / math.sqrt(len(obs)) if sd > 0 else float("inf")
    return {"mean": m, "n": len(obs), "se": se, "t": m / se if se > 0 else 0.0}


def profile(rows, key, buckets, label, norm=None):
    """Median implied sigma by bucket, clustered on close-time."""
    print(f"\n  {label}")
    print(f"  {'bucket':>14}{'obs':>9}{'clusters':>10}{'implied sigma':>15}"
          f"{'vs realised':>13}")
    out = []
    for lo, hi, name in buckets:
        sel = [r for r in rows if lo <= r[key] < hi]
        if len(sel) < 200:
            continue
        by = defaultdict(list)
        for r in sel:
            by[r["close"]].append(r["iv"])
        c = _clustered(by)
        if not c:
            continue
        ratio = (c["mean"] / norm) if norm else float("nan")
        print(f"  {name:>14}{len(sel):>9,}{c['n']:>10}{c['mean']:>15.4f}"
              + (f"{ratio:>12.2f}x" if norm else f"{'--':>13}"))
        out.append((name, c["mean"], ratio, c["n"]))
    return out


def report(rows, real_sigma_by_series):
    if not rows:
        print("  no invertible quotes.")
        return
    norm = median([real_sigma_by_series.get(r["series"], float("nan"))
                   for r in rows if r["series"] in real_sigma_by_series]) \
        if real_sigma_by_series else None
    if norm and not math.isfinite(norm):
        norm = None

    print("=" * 78)
    print("WHAT THE MARKET BELIEVES")
    print("=" * 78)
    ivs = sorted(r["iv"] for r in rows)
    print(f"  {len(rows):,} invertible quotes across "
          f"{len({r['close'] for r in rows}):,} close-time clusters")
    print(f"  implied sigma: p10 {ivs[len(ivs)//10]:.4f}  "
          f"median {ivs[len(ivs)//2]:.4f}  "
          f"p90 {ivs[9*len(ivs)//10]:.4f}   ($/sqrt(s))")
    if norm:
        print(f"  realised sigma (median across series): {norm:.4f}")
        print(f"  VARIANCE RISK PREMIUM: implied / realised = "
              f"{ivs[len(ivs)//2]/norm:.3f}x")
        print("  Above 1 means sellers are PAID to carry variance risk -- a")
        print("  risk premium, not a mistake, and therefore durable. Being on")
        print("  the paid side of it is a strategy in its own right.")

    profile(rows, "tau",
            [(1, 30, "0-30s"), (30, 60, "30-60s"), (60, 120, "60-120s"),
             (120, 300, "120-300s"), (300, 600, "300-600s"),
             (600, 901, "600-900s")],
            "TERM STRUCTURE -- should be FLAT if the market uses our variance "
            "formula", norm)
    print("  A tilt means the market's variance formula differs from")
    print("  settlement_math.py's. Sagging toward expiry is the specific")
    print("  signature of using `tau + 20` where the truth is `tau - 39.5`.")

    profile(rows, "price",
            [(0.06, 0.15, "6-15c"), (0.15, 0.30, "15-30c"),
             (0.30, 0.45, "30-45c"), (0.45, 0.55, "45-55c"),
             (0.55, 0.70, "55-70c"), (0.70, 0.85, "70-85c"),
             (0.85, 0.95, "85-94c")],
            "SMILE -- flat means the market prices a Gaussian", norm)
    print("  A U-shape means fat tails are ALREADY PRICED, which would mean")
    print("  PLAN sec.10.3's tail trade is not available. Asymmetry between the")
    print("  two wings is directional pricing or maker inventory.")

    by_series = defaultdict(list)
    for r in rows:
        by_series[r["series"]].append(r)
    print("\n  BY SERIES -- where is the maker's attention thin?")
    print(f"  {'series':>14}{'obs':>9}{'implied sigma':>15}"
          f"{'realised':>11}{'ratio':>9}{'med spread':>12}")
    for s, sel in sorted(by_series.items(), key=lambda kv: -len(kv[1])):
        if len(sel) < 300:
            continue
        iv = median([r["iv"] for r in sel])
        rs = real_sigma_by_series.get(s)
        sp = median([r["spread"] for r in sel])
        print(f"  {s:>14}{len(sel):>9,}{iv:>15.4f}"
              + (f"{rs:>11.4f}{iv/rs:>9.2f}" if rs else f"{'--':>11}{'--':>9}")
              + f"{100*sp:>11.2f}c")
    print("  A series whose implied/realised ratio is far from the others is")
    print("  priced by a different assumption than its peers -- the natural")
    print("  place for the thin-series question in PLAN sec.9 to resolve.")

    by_hour = defaultdict(list)
    for r in rows:
        by_hour[(datetime.fromtimestamp(r["close"], timezone.utc).hour // 4)
                * 4].append(r["iv"])
    if len(by_hour) > 2:
        print("\n  BY HOUR (UTC) -- implied sigma relative to the daily median")
        base = median([r["iv"] for r in rows])
        parts = [f"{h:02d}h {median(v)/base:.2f}x"
                 for h, v in sorted(by_hour.items()) if len(v) > 200]
        print("  " + "   ".join(parts))


# ===========================================================================
def selftest():
    print("=" * 78)
    print("SELF-TEST -- can it read back a volatility surface it was given?")
    print("=" * 78)
    fails = []
    sigma = 6.0
    s2i = {"KXBTC15M": "BRTI"}

    def build(quote_fn, n_win=200, seed=7):
        rnd = random.Random(seed)
        t0 = 1_760_000_000
        total = 60 + n_win * 900 + 200
        S, ticks = 80_000.0, {}
        for k in range(total):
            S += rnd.gauss(0, sigma)
            ticks[t0 + k] = S
        markets, quotes = {}, {}
        for w in range(n_win):
            open_s = t0 + 60 + w * 900
            close_s = open_s + 900
            if close_s not in ticks:
                break
            strike = sum(ticks[s] for s in range(open_s - 59, open_s + 1)) / 60.0
            tk = f"KXBTC15M-T{w:04d}"
            markets[tk] = {"ticker": tk, "series": "KXBTC15M",
                           "strike": strike, "close": float(close_s),
                           "result": 0.0}
            qs = []
            for s in range(open_s, close_s, 3):
                tau = close_s - s
                lo_run = close_s - N_AVG + 1
                hi = min(s, close_s)
                if hi >= lo_run:
                    lk = [ticks[x] for x in range(lo_run, hi + 1) if x in ticks]
                    mu = (sum(lk) + (N_AVG - len(lk)) * ticks[s]) / N_AVG
                else:
                    mu = ticks[s]
                sd = math.sqrt(var_factor(tau, [1.0]))
                p = quote_fn(mu, strike, sd, tau)
                if p is None:
                    continue
                p = min(max(p, 0.01), 0.99)
                qs.append((s, p - 0.005, p + 0.005, 500, 500))
            quotes[tk] = qs
        return {"BRTI": ticks}, quotes, markets

    print("\n1. market quotes a FLAT sigma of exactly 6.0")
    idx, q, mk = build(lambda mu, k, sd, tau:
                       1 - ND.cdf((k - mu) / (sd * sigma)))
    rows = collect(idx, q, mk, s2i)
    got = median([r["iv"] for r in rows])
    print(f"   recovered median implied sigma = {got:.4f}  (true 6.0000)")
    if abs(got - sigma) > 0.05:
        fails.append(f"flat surface recovered as {got:.4f}, expected 6.0")
    res = profile(rows, "tau", [(1, 60, "0-60s"), (60, 300, "60-300s"),
                                (300, 901, "300-900s")], "term structure",
                  sigma)
    if res and max(abs(r[2] - 1) for r in res) > 0.05:
        fails.append("flat input produced a tilted term structure")

    print("\n2. market quotes a SMILE (+30% sigma in both wings)")

    def smile(mu, k, sd, tau):
        p0 = 1 - ND.cdf((k - mu) / (sd * sigma))
        bump = 1.0 + 0.30 * min(abs(p0 - 0.5) / 0.44, 1.0)
        return 1 - ND.cdf((k - mu) / (sd * sigma * bump))
    idx, q, mk = build(smile)
    rows = collect(idx, q, mk, s2i)
    res = profile(rows, "price",
                  [(0.06, 0.20, "6-20c"), (0.40, 0.60, "40-60c"),
                   (0.80, 0.95, "80-94c")], "smile", sigma)
    if len(res) == 3:
        wings = (res[0][2] + res[2][2]) / 2.0
        belly = res[1][2]
        print(f"   wings {wings:.2f}x vs belly {belly:.2f}x")
        if wings - belly < 0.12:
            fails.append(f"failed to see a planted smile "
                         f"(wings {wings:.2f} vs belly {belly:.2f})")

    print("\n3. market uses the WRONG variance formula (tau+20, the RUNBOOK error)")

    def wrongvar(mu, k, sd, tau):
        bad = math.sqrt(tau + 20) if tau >= 60 else sd
        return 1 - ND.cdf((k - mu) / (bad * sigma))
    idx, q, mk = build(wrongvar)
    rows = collect(idx, q, mk, s2i)
    res = profile(rows, "tau", [(60, 120, "60-120s"), (300, 600, "300-600s"),
                                (600, 901, "600-900s")], "term structure",
                  sigma)
    if len(res) >= 2:
        tilt = res[0][2] / res[-1][2]
        print(f"   near/far implied ratio = {tilt:.2f}x "
              f"(a flat, correct market gives 1.00x)")
        if abs(tilt - 1.0) < 0.15:
            fails.append("failed to detect a wrong variance formula")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- recovers a flat surface exactly, sees a planted")
    print("smile, and detects a market using the wrong variance formula.")
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
        raise SystemExit("self-test failed")

    from replay import load_index, load_quotes, load_markets, SERIES_TO_INDEX
    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    index = load_index(a.data)
    if not index:
        print("  no cfbenchmarks_value -- cannot invert without the index.")
        return
    quotes = load_quotes(a.data)
    if not quotes:
        try:
            from book import rebuild
            quotes, _ = rebuild(a.data)
        except Exception:
            quotes = {}
    markets = load_markets(a.out)
    rs_by_index = realised_sigma(index)
    i2s = {v: k for k, v in SERIES_TO_INDEX.items()}
    rs = {i2s[k]: v for k, v in rs_by_index.items() if k in i2s}
    rows = collect(index, quotes, markets, SERIES_TO_INDEX)
    report(rows, rs)
    print("\n  NOTE: this needs no settlements at all, so it runs on however")
    print("  many hours are recorded. It is the cheapest large-sample view of")
    print("  the market's model available.")


if __name__ == "__main__":
    main()
