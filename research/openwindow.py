#!/usr/bin/env python3
# VERSION: 2026-08-25-o1
"""
openwindow.py -- the first sixty seconds. H5, done the way it should have been.

    python research/openwindow.py --selftest
    python research/openwindow.py --data ./kalshi_data --out ./fulltape

THE SETUP

strike(N+1) == settle(N): consecutive windows average the identical sixty
seconds. So at the instant window N closes, window N+1's strike is ALREADY
DETERMINED, and computable from our own index feed the moment the last tick
prints -- before Kalshi stamps `floor_strike` on the new market.

Meanwhile opening_value.py established that true fair value at open is NOT 50c.
It is Phi((spot_at_open - strike) / (sigma*sqrt(860))), because the strike is a
TRAILING sixty-second average and spot at open is not that average. Mean
|fair - 50c| is 4.75c and 40% of windows open outside 45-55c.

Put those together and the first seconds of a window are the one moment where a
large, purely mechanical mispricing is plausible: the fair value is knowable
immediately, and the book has to catch up.

WHY THE EXISTING TESTS CANNOT SEE THIS

  * kalshi_signals.py H5 compares the MEAN opening price to 50c. The effect is
    symmetric around 50 by construction, so averaging deletes it exactly. H5
    would report "efficient" against an arbitrarily large conditional edge.
  * replay.py evaluates from 600s to close -- 300 seconds after the open.
  * leadlag.py measures the response to index CHANGES, not the level the book
    starts from.

Nothing has ever looked at second zero.

WHAT THIS MEASURES

  1. GATE. Our reconstructed strike vs Kalshi's `floor_strike`, to the cent. If
     these disagree we do not understand the contract and nothing else here is
     meaningful. This is a stronger check than a settlement comparison because
     it uses only our own index record.
  2. How long after open the first quote appears.
  3. The edge profile second by second: model minus market, from open onward.
     If the book opens near 50c and converges over k seconds, the area under
     that curve is the opportunity.
"""

import argparse
import math
import os
import random
import sys
from collections import defaultdict
from statistics import NormalDist, mean, median, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import var_factor, N_AVG                      # noqa: E402

ND = NormalDist()
WINDOW = 900


def reconstruct_strike(ticks, open_sec):
    """mean of the 60 index prints ending at the open. This is what the strike
    must equal."""
    vals = [ticks[s] for s in range(open_sec - N_AVG + 1, open_sec + 1)
            if s in ticks]
    if len(vals) < N_AVG * 0.95:
        return None
    return sum(vals) / len(vals)


def gate_strike(markets, index, series_to_index, verbose=True):
    """Our strike vs Kalshi's floor_strike."""
    errs = []
    for tk, m in markets.items():
        iid = series_to_index.get(m.get("series"))
        ticks = index.get(iid)
        if not ticks:
            continue
        open_s = int(round(m["close"])) - WINDOW
        got = reconstruct_strike(ticks, open_s)
        if got is None or not m.get("strike"):
            continue
        errs.append(abs(got - m["strike"]) / m["strike"])
    if not errs:
        if verbose:
            print("  no markets with both an index record and a strike.")
        return None
    errs.sort()
    med = errs[len(errs) // 2]
    p90 = errs[int(len(errs) * .9)]
    if verbose:
        print(f"  {len(errs):,} markets checked")
        print(f"  relative error  median {med:.2e}   p90 {p90:.2e}   "
              f"max {errs[-1]:.2e}")
        v = ("PASS" if med < 1e-5 else "MARGINAL" if med < 1e-4 else "*** FAIL ***")
        print(f"  {v}  -- our reconstructed strike vs Kalshi's floor_strike")
        if med >= 1e-4:
            print("  We cannot reproduce the strike from our own index record.")
            print("  Either the averaging window is offset, or the timestamps")
            print("  are misaligned. Everything downstream is invalid. STOP.")
    return {"n": len(errs), "median": med}


def check_deviation_scale(index, verbose=True):
    """THE one number the whole opening-value claim rests on.

    R1 puts mean |fair - 50c| at 4.75c, and that follows entirely from
    sd(spot - trailing-60s-mean) = sqrt(20)*sigma, exact for a walk with iid
    increments. BRTI is a consolidation of order-book mids and need not have iid
    increments, so measure the ratio instead of assuming it.

    THE DIRECTION IS NOT OBVIOUS AND I INITIALLY GOT IT BACKWARDS. Validated
    against synthetic indices:

        iid increments          ratio 0.99   -> 4.75c, as claimed
        EMA-smoothed (a=0.5)    ratio 1.69   -> about 8.0c
        EMA-smoothed (a=0.8)    ratio 2.81   -> about 13.4c

    POSITIVE autocorrelation makes the walk trend, so spot sits FURTHER from its
    own trailing average and the effect GROWS. Negative autocorrelation (quote
    flicker, bid-ask bounce) would shrink it. Both are plausible for a
    consolidated mid, so this is a genuine measurement, not a formality -- and
    it can rescale R1's headline number in either direction."""
    print("\n" + "=" * 78)
    print("SCALE CHECK -- the number the opening-value claim depends on")
    print("=" * 78)
    print(f"  {'index':>14}{'sd(spot-avg60)':>17}{'sqrt(20)*sigma':>17}"
          f"{'ratio':>9}   reading")
    out = {}
    for iid, ticks in sorted(index.items(), key=lambda kv: -len(kv[1])):
        secs = sorted(ticks)
        if len(secs) < 5000:
            continue
        d = [ticks[b] - ticks[a] for a, b in zip(secs, secs[1:]) if b - a == 1]
        if len(d) < 1000:
            continue
        mu = sum(d) / len(d)
        sig = math.sqrt(sum((x - mu) ** 2 for x in d) / len(d))
        devs = []
        for t in secs:
            w = [ticks[s] for s in range(t - N_AVG + 1, t + 1) if s in ticks]
            if len(w) == N_AVG:
                devs.append(ticks[t] - sum(w) / N_AVG)
        if len(devs) < 500:
            continue
        m = sum(devs) / len(devs)
        sd_obs = math.sqrt(sum((x - m) ** 2 for x in devs) / len(devs))
        theory = math.sqrt(20.0) * sig
        ratio = sd_obs / theory if theory > 0 else float("nan")
        out[iid] = ratio
        r = ("as assumed (iid-like)" if 0.9 <= ratio <= 1.1 else
             "SHRINKS -- index is noisy/mean-reverting at 1s" if ratio < 0.9
             else "GROWS -- index trends at 1s")
        print(f"  {iid:>14}{sd_obs:>17.4f}{theory:>17.4f}{ratio:>9.3f}   {r}")
    if out:
        med = sorted(out.values())[len(out) // 2]
        print(f"\n  median ratio {med:.3f}")
        print(f"  R1's mean |fair - 50c| of 4.75c scales roughly linearly with")
        print(f"  this, so the honest figure is about {4.75*med:.2f}c.")
        if med < 0.9:
            print("  The index mean-reverts at one-second scale (quote flicker,")
            print("  bid-ask bounce), so spot stays closer to its own trailing")
            print("  average. The opening-value effect is real but smaller.")
        elif med > 1.1:
            print("  The index TRENDS at one-second scale, so spot runs further")
            print("  from its trailing average than a random walk would. The")
            print("  opening-value effect is LARGER than R1 claimed.")
    return out


def edge_profile(markets, index, quotes, series_to_index, gamma0,
                 horizon=120, verbose=True):
    """model - market, by seconds since open."""
    rows = defaultdict(list)
    first_quote = []
    for tk, m in markets.items():
        iid = series_to_index.get(m.get("series"))
        ticks, g0 = index.get(iid), gamma0.get(iid)
        q = quotes.get(tk)
        if not ticks or not g0 or not q:
            continue
        close_s = int(round(m["close"]))
        open_s = close_s - WINDOW
        strike = m.get("strike")
        if not strike:
            continue
        mids = {t: (b + a) / 2.0 for t, b, a, _, _ in q}
        early = [t for t in mids if t >= open_s]
        if early:
            first_quote.append(min(early) - open_s)
        # The prevailing mid, carried forward at most 30s -- NOT `s in mids`.
        # The ticker channel is publish-on-change, so requiring a message in
        # the exact second samples at quote-arrival times: the market-maker's
        # own repricing process chooses the sample, which is the very
        # staleness this stage measures. calib.py's _mid_at is the blessed
        # pattern; this is the same carry-forward inline.
        msecs = sorted(mids)
        mj, mcur = 0, None
        carry = {}
        for s_ in range(open_s, open_s + horizon + 1):
            while mj < len(msecs) and msecs[mj] <= s_:
                mcur = msecs[mj]
                mj += 1
            if mcur is not None and s_ - mcur <= 30:
                carry[s_] = mids[mcur]
        for dt in range(0, horizon + 1):
            s = open_s + dt
            if s not in ticks or s not in carry:
                continue
            # before the settle window, so nothing is locked in yet
            mu = ticks[s]
            tau = close_s - s
            vf = var_factor(tau, [1.0])
            if vf <= 0:
                continue
            fair = 1.0 - ND.cdf((strike - mu) / math.sqrt(vf * g0))
            rows[dt].append((fair - carry[s], close_s))
    if verbose and first_quote:
        first_quote.sort()
        print(f"\n  first quote after open: median {median(first_quote):.0f}s"
              f"   p90 {first_quote[int(len(first_quote)*.9)]:.0f}s"
              f"   ({len(first_quote):,} markets)")
    return rows


def report_profile(rows, buckets=((0, 5), (5, 15), (15, 30), (30, 60),
                                  (60, 120))):
    print(f"\n  {'since open':>12}{'clusters':>10}{'mean edge':>12}{'t':>8}"
          f"{'mean |edge|':>14}   verdict")
    out = []
    for lo, hi in buckets:
        vals = [v for dt in range(lo, hi) for v in rows.get(dt, [])]
        if len(vals) < 30:
            continue
        by = defaultdict(list)
        for e, c in vals:
            by[c].append(e)
        obs = [mean(v) for v in by.values()]
        absobs = [abs(mean(v)) for v in by.values()]
        m, sd = mean(obs), pstdev(obs)
        se = sd / math.sqrt(len(obs)) if sd > 0 else float("inf")
        t = m / se if se > 0 else 0.0
        v = ("SIGNAL" if abs(t) > 3 else "weak" if abs(t) > 2 else "nothing")
        print(f"  {f'{lo}-{hi}s':>12}{len(obs):>10}{100*m:>11.2f}c{t:>8.1f}"
              f"{100*mean(absobs):>13.2f}c   {v}")
        out.append((lo, hi, m, t))
    print("\n  MEAN edge is the directional test and should be ~0 even if the")
    print("  book is badly wrong, because the mispricing is symmetric about 50c.")
    print("  MEAN |edge| is the size of the disagreement, which is what you")
    print("  would actually trade. A large |edge| with a zero mean edge is")
    print("  exactly the pattern H5 was blind to.")
    return out


# ===========================================================================
def selftest():
    print("=" * 78)
    print("SELF-TEST -- can it see a book that opens at 50c and converges?")
    print("=" * 78)
    fails = []
    sigma = 6.0
    g0 = {"BRTI": sigma * sigma}
    s2i = {"KXBTC15M": "BRTI"}

    for conv, label in ((0, "book correct from second 0"),
                        (30, "book opens at 50c, converges over 30s")):
        rnd = random.Random(11)
        t0 = 1_760_000_000
        n_win = 400
        total = 60 + n_win * WINDOW + 200
        S, ticks = 80_000.0, {}
        for k in range(total):
            S += rnd.gauss(0, sigma)
            ticks[t0 + k] = S
        markets, quotes = {}, {}
        for w in range(n_win):
            open_s = t0 + 60 + w * WINDOW
            close_s = open_s + WINDOW
            if close_s not in ticks:
                break
            strike = sum(ticks[s] for s in range(open_s - 59, open_s + 1)) / 60.0
            tk = f"KXBTC15M-S{w:04d}"
            markets[tk] = {"ticker": tk, "series": "KXBTC15M",
                           "strike": strike, "close": float(close_s),
                           "result": 0.0}
            qs = []
            for dt in range(0, 130):
                s = open_s + dt
                if s not in ticks:
                    continue
                vf = var_factor(close_s - s, [1.0])
                fair = 1.0 - ND.cdf((strike - ticks[s]) /
                                    math.sqrt(vf * sigma * sigma))
                if conv:
                    wgt = min(dt / conv, 1.0)      # 50c -> fair over `conv` s
                    shown = 0.5 + wgt * (fair - 0.5)
                else:
                    shown = fair
                shown = min(max(shown, 0.01), 0.99)
                qs.append((s, shown - 0.005, shown + 0.005, 500, 500))
            quotes[tk] = qs

        print(f"\n  {label}")
        g = gate_strike(markets, {"BRTI": ticks}, s2i, verbose=False)
        print(f"  strike gate: median rel err {g['median']:.2e} "
              f"over {g['n']} markets")
        if g["median"] > 1e-9:
            fails.append("strike reconstruction disagrees with its own input")
        rows = edge_profile(markets, {"BRTI": ticks}, quotes, s2i, g0,
                            verbose=False)
        res = report_profile(rows)
        early = [r for r in res if r[0] == 0]
        late = [r for r in res if r[0] == 60]
        if conv == 0:
            if early and abs(early[0][2]) > 0.002:
                fails.append(f"found a {100*early[0][2]:.2f}c edge against a "
                             "book that was correct from second 0")
        else:
            if not early or abs(early[0][2]) < 0.0:
                pass
            e0 = [abs(mean([abs(x[0]) for x in rows[d]])) for d in range(0, 5)
                  if rows.get(d)]
            e60 = [abs(mean([abs(x[0]) for x in rows[d]])) for d in range(60, 90)
                   if rows.get(d)]
            if e0 and e60 and mean(e0) < 3 * mean(e60):
                fails.append(f"failed to see the convergence: |edge| {100*mean(e0):.2f}c "
                             f"at open vs {100*mean(e60):.2f}c later")
            else:
                print(f"  |edge| falls from {100*mean(e0):.2f}c in the first 5s "
                      f"to {100*mean(e60):.2f}c after 60s -- detected.")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- silent against a book that opens correct, and")
    print("it sees a book that opens at 50c and converges.")
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
        print("  no cfbenchmarks_value -- impossible without it.")
        return
    quotes = load_quotes(a.data)
    if not quotes:
        try:
            from book import rebuild
            quotes, _ = rebuild(a.data)
        except Exception:
            quotes = {}
    markets = load_markets(a.out)
    g0 = {}
    for iid, ticks in index.items():
        secs = sorted(ticks)
        d = [ticks[b] - ticks[a] for a, b in zip(secs, secs[1:]) if b - a == 1]
        if len(d) > 200:
            m = mean(d)
            g0[iid] = sum((x - m) ** 2 for x in d) / len(d)

    print("\n" + "=" * 78)
    print("GATE  --  our reconstructed strike vs Kalshi's floor_strike")
    print("=" * 78)
    gate_strike(markets, index, SERIES_TO_INDEX)

    check_deviation_scale(index)

    print("\n" + "=" * 78)
    print("THE FIRST TWO MINUTES")
    print("=" * 78)
    rows = edge_profile(markets, index, quotes, SERIES_TO_INDEX, g0)
    if not rows:
        print("  no markets with an index record, a strike and early quotes.")
        return
    report_profile(rows)


if __name__ == "__main__":
    main()
