# PRE-REGISTRATION -- AMENDMENT 20, the volatility ruler
## Written 2026-09-13 ~07:15 ET, BEFORE any live run with `--sigma-ruler`

**Nothing is deployed.** `SIGMA_RULER` is `"live"` and a self-test asserts it.

## Where this came from

The operator, 2026-09-13: *"tracking volume, volatility, or anything else you
can think of and seeing how that correlates to lumpiness and large price
swings."* `research/pinflood.py` did that over 18,178 coin-closes on 1,671
closes, index feed only.

**The strongest predictor is the opposite of intuition.** A "flood" is a close
where the model missed by more than 3 of its own standard deviations:

| fifth of `rv_short` (how choppy the last 5 min were) | flood rate |
|---|---|
| calmest | **4.28%** |
| 2nd | 2.17% |
| 3rd | 1.57% |
| 4th | 1.18% |
| choppiest | **1.05%** |

Monotone across all five, **4.05x**, 95% by-close interval [0.15, 0.39] on the
lift, against a pre-stated MDE of 2.50x. Holds out of sample: 0.28x on the
first 70% of closes, 0.14x on the last 30%.

Every other predictor tested -- lumpiness of the last hour, count of 4-sigma
moves, biggest move, BTC's lumpiness, BTC's biggest move, the previous close's
miss, the worst miss across all coins last close, hour of day -- **failed the
MDE.** BTC's biggest move was the best of them at 2.37x [1.21, 4.36] and still
did not clear 2.50x. That is NO POWER, not NO EFFECT, and the operator's BTC
intuition is neither confirmed nor refuted here.

## The mechanism, and the test that separates it from a correlation

Calm markets are not dangerous. `z = miss / sd`, and `sd` comes from sigma
measured over the last **300 seconds**. Volatility reverts, so a quiet 300
seconds understates the next minute: **the model's ruler is too short**, and
every miss measured against it looks enormous.

If that is the mechanism, lengthening the ruler must collapse the gradient:

| ruler | flood rate | calm fifth | choppy fifth | gradient |
|---|---|---|---|---|
| 300s (live) | 2.05% | 4.28% | 1.05% | 4.09x |
| 900s | 1.79% | 3.07% | 1.40% | 2.19x |
| 1800s | 1.77% | 2.72% | 1.73% | 1.57x |
| 3600s | 1.73% | 2.41% | 2.09% | **1.15x** |
| **max(300s, 3600s)** | **1.24%** | 2.31% | 0.83% | 2.79x |

It collapses. And `--selftest` plants both worlds: one where volatility
reverts (a long ruler must win) and one where it is constant (the two rulers
must agree). The first version of that fixture made the regime PERSIST, where a
short ruler is genuinely better, and the check failed -- correctly, on the
fixture rather than the estimator.

## Why this is not the SIGMA_STRESS dead end in disguise

Multiplying sigma by a constant was measured the same day and made things
worse (k=1.25 keeps 44% of candidates at 3.09% bad against 2.90% at k=1.0).

**Kurtosis is scale-free. Multiplying every sd by a constant cannot change it.**
It falls from **132 to 47**. So the distribution's SHAPE improves, which a
uniformly wider ruler could never produce. That is the whole argument, and it
is why this is a different animal from a blanket haircut.

## What it costs, measured on the index population

Decisions rebuilt from the index alone -- no order book, no replay -- using
`strike(N+1) == settle(N)`: 108,414 decisions, gate = stated confidence >=
0.995.

| ruler | trades vs live | loss rate on gated decisions |
|---|---|---|
| 1800s | −0.5% | **−28.2%** |
| 3600s | −0.7% | **−30.1%** |
| max(300,1800) | −0.8% | **−38.3%** |
| **max(300,3600)** | **−1.0%** | **−42.3%** |

## WHAT THIS DOES NOT SHOW, stated before the bar

1. **It is not our loss rate and cannot be** (rule 5). This population is "any
   moment on the index"; ours is "someone actively sold it to us". They differ
   by 31x. A ruler that helps the first may do nothing for the second.
2. **The trade-count cost is understated.** Only the PIN gate was tested. A
   wider sigma also lowers fair value, which shrinks the edge and the EV, and
   both have floors. The real cut could be materially larger than 1%.
3. `max()` is a choice, not a fit, but 3600 was chosen after seeing the table.
   1800 is the better-CALIBRATED single window (sd(z) 1.013 against 1.153
   live) and 3600 is the better performer. That is a fitted parameter and it
   is admitted as one.

## THE LIVE BAR -- decided before the first fill under a new ruler

Run `--sigma-ruler max3600`, nothing else changed. Scored at **60 fills or 14
days, whichever comes first**:

1. **Market-loss rate strictly below 4.13%**, the live all-history baseline,
   on at least 60 fills. Point estimate below; not "trending toward".
2. **Trade count >= 70% of the concurrent rate.** The index population says
   the cost is 1%; if live says worse than 30% the model's edge was living in
   the short ruler and that is a finding, not a tuning problem.
3. **$/day must not fall.** Fewer blow-ups is only worth having if the money
   survives.

**If 1 fails, revert.** If 1 holds and 2 fails, the honest conclusion is that
the edge came from an over-confident ruler, and that reopens the strategy
rather than patching it.

## Kill criterion

If after 60 fills the loss rate is indistinguishable from baseline, the ruler
is not the mechanism for OUR fills whatever it does to the index, and this line
closes.

## Not proposed

No change to PIN, PRICE_CEILING, EDGE_FLOOR, EV_FLOOR, MEASURED_FLIP, the
sweep, the hedge, BANK_BRAKE or size. One flag, one number: how far back the
volatility estimate looks.
