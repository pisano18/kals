#!/usr/bin/env python3
# VERSION: 2026-08-25-r1
"""
opening_value.py -- "every window opens at exactly 50c by construction" is false.

That sentence is the load-bearing claim of PLAN.md sec.2 and it is the reason
the project pivoted to the 90-99c endgame. It is wrong, and the error is not
subtle once you write it down.

    strike  = mean(S_1 .. S_60)      the 60 ticks BEFORE open
    open    = second 60
    settle  = mean(S_901 .. S_960)

At the open, E[settle | everything known] = S_60, the CURRENT index level.
The strike is the TRAILING 60-SECOND AVERAGE. Those are not the same number.

    P(Yes at open) = Phi( (S_60 - strike) / sd )

S_60 - strike is the deviation of spot from its own trailing average. For a
random walk that has mean zero but standard deviation sqrt(20)*sigma. It is
zero only in expectation -- never in any actual window.

So "50c" is the UNCONDITIONAL mean of the opening fair value. The CONDITIONAL
fair value, which is the only one you can trade, is a random variable spread
several cents either side of 50, and it is fully determined by data we already
record. No forecasting. Just spot minus a trailing average.

WHY THE EARLIER ANALYSIS COULD NOT HAVE SEEN THIS
  * kalshi_signals.py H5 tests mean(opening price) against 0.50. That averages
    the effect to zero by construction and reports "efficient".
  * The full-tape calibration compared price to outcome. A market can be
    perfectly calibrated in every price bucket and still be beatable by a model
    that conditions on more information.
  * Neither test ever saw the index. Without BRTI you cannot compute
    (S_60 - strike) at all, so this hypothesis was unreachable.

This file establishes the size of the effect by simulation, so we know what to
look for before spending a day pulling data.
"""

import math
import random
from statistics import NormalDist

from settlement_math import (CLOSE_K, N_AVG, SETTLE_IDX, STRIKE_IDX,
                             cond_var_closedform)

ND = NormalDist()
OPEN_K = 60


def main():
    rng = random.Random(11)
    n = 120_000
    sigma = 1.0

    # only the strike window, the settle window and the open are ever read, so
    # jump between them in one draw each rather than stepping all 960 seconds
    need = sorted(set(STRIKE_IDX) | set(SETTLE_IDX) | {OPEN_K})
    pos = {k: i for i, k in enumerate(need)}
    sds = [sigma * math.sqrt(g) for g in
           [need[0]] + [need[i] - need[i-1] for i in range(1, len(need))]]
    si = [pos[i] for i in STRIKE_IDX]
    ei = [pos[i] for i in SETTLE_IDX]
    strike, settle, spot_open = [], [], []
    for _ in range(n):
        path, x = [], 0.0
        for sd in sds:
            x += rng.gauss(0.0, sd)
            path.append(x)
        strike.append(sum(path[i] for i in si) / 60.0)
        settle.append(sum(path[i] for i in ei) / 60.0)
        spot_open.append(path[pos[OPEN_K]])

    print("=" * 78)
    print("A. IS FAIR VALUE AT OPEN ACTUALLY 50 CENTS?")
    print("=" * 78)
    dev = [a - b for a, b in zip(spot_open, strike)]
    def _mean(x): return sum(x) / len(x)
    def _sd(x):
        m = _mean(x)
        return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1))
    print(f"   spot_at_open - strike:  mean {_mean(dev):+.4f} sigma   "
          f"sd {_sd(dev):.4f} sigma")
    print(f"   theory: mean 0, sd sqrt(20) = {math.sqrt(20):.4f} sigma")

    sd_open = math.sqrt(cond_var_closedform(OPEN_K, sigma))
    z = [d / sd_open for d in dev]
    p_open = [ND.cdf(x) for x in z]
    print(f"\n   residual sd of settle at open = {sd_open:.3f} sigma")
    print(f"   so z at open has sd {_sd(z):.4f}  "
          f"(= sqrt(20/{cond_var_closedform(OPEN_K):.1f}))")
    print(f"\n   TRUE fair value at open, distribution over windows:")
    qs = [1, 5, 10, 25, 50, 75, 90, 95, 99]
    sp = sorted(p_open)
    vals = [sp[min(int(len(sp) * q / 100), len(sp) - 1)] for q in qs]
    print("   " + "".join(f"p{q:<4}" for q in qs))
    print("   " + "".join(f"{100*v:<5.1f}" for v in vals))
    ad = [abs(p - 0.5) for p in p_open]
    print(f"\n   mean |fair - 50c| = {100*_mean(ad):.2f} cents")
    print(f"   P(fair outside 45-55c) = "
          f"{100*sum(1 for v in ad if v > 0.05)/len(ad):.1f}%")
    print(f"   P(fair outside 40-60c) = "
          f"{100*sum(1 for v in ad if v > 0.10)/len(ad):.1f}%")

    # verify the model is actually right: does it predict outcomes?
    print("\n   CALIBRATION OF THE MODEL ITSELF (sanity, must be ~diagonal):")
    out = [1.0 if a >= b else 0.0 for a, b in zip(settle, strike)]
    print(f"   {'model says':>12}{'windows':>9}{'actually Yes':>14}")
    for lo, hi in [(0, .35), (.35, .45), (.45, .55), (.55, .65), (.65, 1)]:
        sel = [out[i] for i, p in enumerate(p_open) if lo <= p < hi]
        if len(sel) > 100:
            print(f"   {f'{100*lo:.0f}-{100*hi:.0f}c':>12}{len(sel):>9,}"
                  f"{100*_mean(sel):>13.1f}%")

    print("\n" + "=" * 78)
    print("B. IF THE BOOK OPENS AT 50c, WHAT IS THE EDGE?")
    print("=" * 78)
    print("   Buy the side the model favours, at a flat 50c, every window.")
    edge = _mean(ad)
    fee50 = math.ceil(0.07 * 0.5 * 0.5 * 100) / 100.0
    print(f"   gross edge                 {100*edge:+.2f} c/contract")
    print(f"   taker fee at 50c           {-100*fee50:+.2f} c")
    print(f"   net                        {100*edge - 100*fee50:+.2f} c")
    print("\n   That is an absurd number and it is exactly why I do not believe")
    print("   the book opens at a flat 50c. But it sets the scale: the market")
    print("   MUST be pricing spot-minus-trailing-average, or this would be")
    print("   free money in the most liquid moment of every window.")
    print("   The real experiment is how much of it the book already captures.")

    print("\n" + "=" * 78)
    print("C. THE DELTA DAMPING -- the mechanical fade, no forecasting")
    print("=" * 78)
    print("   d(fair)/d(spot) = phi(z)/sd * (r_future/60), where r_future is")
    print("   the number of settle ticks NOT yet locked in. Inside the last")
    print("   minute that factor collapses:")
    print(f"\n   {'sec to close':>13}{'ticks still live':>18}{'spot sensitivity':>19}")
    for tau in (900, 300, 120, 60, 45, 30, 20, 10, 5, 2):
        t = CLOSE_K - tau
        live = len([i for i in SETTLE_IDX if i > t])
        print(f"   {tau:>13}{live:>18}{live/60:>18.3f}x")
    print("\n   A $50 spot move with 10 seconds left changes the settlement")
    print("   average by $50 * 10/60 = $8.33, not $50. A quoter (or a retail")
    print("   flow) reacting to spot 1:1 in the last minute OVERREACTS by 6x.")
    print("   This is testable directly: regress contract-price change on index")
    print("   change, bucketed by seconds-to-close. The coefficient must fall")
    print("   like r/60. If it stays flat, the book is overreacting and the")
    print("   fade is mechanical.")
    print("\n   kalshi_signals.py H6 gropes at this by looking at CONTRACT price")
    print("   jumps with no reference to the index, which cannot distinguish")
    print("   'overreaction' from 'the index really moved'. With BRTI it is a")
    print("   clean regression with a known correct coefficient.")


if __name__ == "__main__":
    main()
