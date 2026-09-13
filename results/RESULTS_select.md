# RESULTS_select -- calibration or selection

*`research/pinselect.py`, 2026-09-13T03:47Z. 46,153 model-certain observations on 8,015 markets over 894 closes, on the exogenous grid tau = 5, 10, 15, 20, 25, 30 s, 2026-09-02T09:15Z .. 2026-09-12T18:00Z (10.4 days). Gate as read from `pinrun`: PIN=0.995, PRICE_CEILING=0.98, tau [3,30], SIGMA_STRESS=1.0.*

## VERDICT: SELECTION

**The model's called side wins 99.95% [99.87, 99.99] of the time over ALL 46,153 certain observations, and 99.19% [98.42, 99.65] over the 992 where a takeable ask actually existed. The gap against the markets nobody offered us is -0.78 pp [-1.64, -0.12] (by-close block bootstrap), against an MDE of 0.20 pp. Standardised onto the tradeable arm's own (stated confidence x tau) mix, so the comparison is about WHO SOLD and not about WHEN the offer arrived, the gap is -0.49 pp [-1.25, +0.22].** **And the overconfidence is CONCENTRATED, which is what settles it.** On the 45,161 certain observations nobody offered us -- 97.9% of the population, where no seller is involved at all -- the model promises to lose 0.0012% and loses 0.0288%, missing by **0.028 pp**. On the 992 it did offer, it promises 0.0815% and loses 0.8065%, missing by **0.725 pp -- 26x more**. A Gaussian tail that is simply too thin misses by the same amount in both arms, because it knows nothing about who is quoting. This does not. Live the model promises 0.394% and loses 4.13%, a miss of 3.74 pp: the untradeable population is 130x too well behaved to explain that, and the tradeable population is the only place on this tape where the miss is even the right order of magnitude.

**This is a comparison of TWO TAPE POPULATIONS against each other, and it is only that.** Both arms are drawn from the same replayed book by the same estimator over the same hours, so whatever the replay gets wrong about a population it gets wrong in both arms. **Neither number is our loss rate**, and neither may ever be quoted as one (CLAUDE.md 2026-09-10 rule 5). Our loss rate is 4.13% (10 of 242) and comes from live fills, which is the only place it may come from. **No strategy P&L is computed in this file at all.**

---

## 0. The power, before the estimate

Twelve series settle on the same quarter hour, so a market count is not an observation count. The intraclass correlation of the win indicator across coins sharing a close is measured at **rho = 0.099**, giving a design effect of **6.04x**: 46,153 observations on 8,015 markets over 894 closes are worth **7644 independent observations** -- the deflation absorbs both the coins that share a close and the six grid seconds that share a market. Every Clopper-Pearson interval below is drawn on the deflated counts.

At a base accuracy of 99.95%, the smallest accuracy difference this design can call at alpha=0.05 two-sided with 80% power is **0.20 percentage points** (992 effective tradeable vs 8689 effective untradeable). A gap smaller than that is NO POWER, not NO EFFECT.

## 1. What the model is certain about, and what is on offer

The tape was scanned over every second in tau [3,30], giving 215,985 model-certain market-seconds read at 8,926,476 book events. Everything below is taken from the exogenous grid tau = 5, 10, 15, 20, 25, 30 s, which is 46,153 observations on 8,015 distinct markets over 894 closes:

| at a grid second, on the model's side | observations | share |
|---|---|---|
| no ask at any price | 38,435 | 83.3% |
| -- of those, an ask stood on the LOSING side | 38,433 | 100.0% |
| an ask at or below the ceiling (TRADEABLE) | 992 | 2.1% |
| an ask, but above the ceiling (DEAR -- section 4's control) | 6,726 | 14.6% |

`results/RESULTS_count.md` measured 84.2% with no ask on the winning side over its own window and its own sampling; this window and this grid give 83.3%. Of the observations with no ask on the model's side, 100.0% carried one on the LOSING side -- somebody is quoting; they will not quote the side the model wants.

## 2. THE DECISIVE COMPARISON -- did the model's called side win?

| population | obs | closes | lost | accuracy | 95% CP (cluster-deflated) | |
|---|---|---|---|---|---|---|
| (a) ALL model-certain observations | 46,153 | 894 | 21 | 99.95% | [99.87, 99.99] | the whole population |
| (b) tradeable -- a takeable ask existed | 992 | 388 | 8 | 99.19% | [98.42, 99.65] | what we can actually buy |
| (a minus b) untradeable | 45,161 | 892 | 13 | 99.97% | [99.92, 100.00] | the complement of (b) |
| -- of which: offered, but above the ceiling | 6,726 | 774 | 9 | 99.87% | [99.64, 99.99] | section 4's control |
| -- of which: never offered at all | 38,435 | 892 | 4 | 99.99% | [99.93, 100.00] |  |

**Gap (b) minus untradeable: -0.78 pp, 95% by-close bootstrap [-1.64, -0.12], 0.65% of 894-close resamples at or above zero.** Gap (b) minus (a): -0.76 pp [-1.60, -0.12] -- necessarily smaller, because (b) sits inside (a)'s own denominator.

### 2a. The same comparison at each grid second separately

No pooling, no pick: at each tau every certain market contributes one observation and the two arms are read off the same second.

| tau | certain obs | tradeable | trad. acc | untrad. acc | gap |
|---|---|---|---|---|---|
| 5 s | 8,013 | 89 | 100.00% (0 lost) | 100.00% (0 lost) | +0.00 pp |
| 10 s | 7,926 | 136 | 100.00% (0 lost) | 100.00% (0 lost) | +0.00 pp |
| 15 s | 7,797 | 158 | 100.00% (0 lost) | 99.96% (3 lost) | +0.04 pp |
| 20 s | 7,645 | 188 | 98.94% (2 lost) | 99.97% (2 lost) | -1.04 pp |
| 25 s | 7,477 | 185 | 99.46% (1 lost) | 99.96% (3 lost) | -0.50 pp |
| 30 s | 7,295 | 236 | 97.88% (5 lost) | 99.93% (5 lost) | -2.05 pp |

**What the two arms actually are, stated plainly.** An ask on the model's side at or below the ceiling means somebody will sell the model's winner for under 98c: the MARKET DISAGREES with the model. No ask on that side at any price under $1 means nobody will sell it at all: the MARKET AGREES. So this comparison asks whether the market's disagreement carries information the model does not already have -- and section 2b asks it again holding the model's own stated confidence fixed, which is what turns it from a statement about prices into a statement about the counterparty.

In loss terms the same sentence reads: the model's side fails on **0.03%** of the certain markets nobody sold to us and **0.81%** of the ones somebody did -- a ratio of **28.0x**. Both are tape populations. Neither is ours.

### 2b. The same gap, holding the model's own stated confidence and tau fixed

A takeable offer does not arrive at a uniformly random moment. If offers cluster where the model is merely certain rather than overwhelmingly certain, or at a particular tau, a gap appears with no seller in it -- the occupation-time selection CLAUDE.md warns about under 'Writing new analysis'. So the untradeable arm is re-weighted by direct standardisation onto the tradeable arm's own (stated confidence x tau) mix, over the strata where both arms have markets. `--selftest` plants a world where tradeability and the outcome are BOTH driven by the stratum and nothing else, and requires this estimator to return zero there while the crude gap still fires.

| | tradeable | untradeable | gap | 95% by-close bootstrap |
|---|---|---|---|---|
| crude | 99.19% | 99.97% | -0.78 pp | [-1.64, -0.12] |
| standardised on (conf x tau) | 99.19% | 99.68% | -0.49 pp | [-1.25, +0.22] |

992 of the 992 tradeable markets sit in a stratum that also holds an untradeable market and so can be compared at all. **The adjusted interval covers zero.** Roughly a third of the crude gap is the moment rather than the seller: takeable offers do cluster where the model's stated confidence is at the low end of certain. What remains points the same way and cannot be separated from zero HERE -- the standardised weights fall on strata where the untradeable arm has a handful of observations, so this estimator is the weakest instrument in the file. **Section 2d asks the same question with a stable statistic and answers it**, so read 2d before concluding anything from this row.

The two arms' mixes, so the size of the confound is visible:

| stratum (stated confidence, tau) | tradeable | untradeable | tradeable lost | untradeable lost |
|---|---|---|---|---|
| 0.995-0.999, 3-15 s | 62 | 31 | 0 | 0 |
| 0.995-0.999, 16-30 s | 200 | 163 | 3 | 1 |
| 0.999-0.9999, 3-15 s | 75 | 41 | 0 | 1 |
| 0.999-0.9999, 16-30 s | 145 | 278 | 3 | 0 |
| >=0.9999, 3-15 s | 246 | 23,281 | 0 | 2 |
| >=0.9999, 16-30 s | 264 | 21,367 | 2 | 9 |

### 2d. Explanation A, tested directly: is the model overconfident EVERYWHERE?

The model does not merely say 'certain', it states a number, so the claim can be scored where it is made. `stated` is the mean of (1 - confidence) over the observations in the row -- the loss rate the MODEL predicts for them. `realised` is what happened. Their ratio is the factor by which the model is overconfident THERE. Explanation A -- a Gaussian tail that is too thin -- is the claim that this factor is large in every row.

**Read the `misses by` column, not the ratio.** In the last band the model's stated loss rate rounds to zero, so the ratio divides by nothing and reports hundreds for a miss of three hundredths of a percentage point. The absolute miss is what any fix has to close.

| stated confidence | arm | obs | closes | model says it loses | it actually loses | misses by | (ratio) |
|---|---|---|---|---|---|---|---|
| 0.995-0.999 | tradeable | 262 | 198 | 0.2688% | 1.1450% | **0.876 pp** | 4x |
| 0.995-0.999 | untradeable | 194 | 160 | 0.2196% | 0.5155% | **0.296 pp** | 2x |
| 0.999-0.9999 | tradeable | 220 | 187 | 0.0448% | 1.3636% | **1.319 pp** | 30x |
| 0.999-0.9999 | untradeable | 319 | 239 | 0.0370% | 0.3135% | **0.276 pp** | 8x |
| >= 0.9999 | tradeable | 510 | 229 | 0.0011% | 0.3922% | **0.391 pp** | 358x |
| >= 0.9999 | untradeable | 44,648 | 892 | 0.0000% | 0.0246% | **0.025 pp** | 794x |

**The cleanest single cut is the last band**, where the model claims at most one failure in ten thousand and the two arms are therefore making the SAME claim. There the tradeable arm fails 0.392% of the time (2 of 510 over 229 closes) against 0.0246% (11 of 44,648) -- **15.9x worse on the same stated claim**. The gap is -0.368 pp [-0.970, +0.009] with 12.3% of by-close resamples at or above zero, against an MDE of 0.200 pp: the DIRECTION is unambiguous and the interval brushes zero, because 2 failures cannot carry a tighter one.

### 2c. The per-market rollup, and the one mechanism it exposes

The grid above is the answer. This section is a DIFFERENT reading of the same cells, kept because it found the mechanism: roll each market up to one record, calling it tradeable if a takeable ask existed at ANY second in the band and reading the offer off the moment it was cheapest. **That pick is not symmetric between the arms** -- the cheapest ask is the instant of maximum model-market disagreement, where the model is most likely wrong, while an untradeable market is read at the end of the band, where it is most likely right -- so its gap is an upper bound and the verdict is NOT taken from it.

On that reading: 835 tradeable markets at 98.20% against 7,240 untradeable at 100.00%, 15 failures in the whole 8,075-market certain population.

**And every one of those 15 failures is a market on which the model was certain of BOTH sides at different seconds inside the same 27-second band.** There are 20 such markets in 8,075; 15 of them failed, and 20 of them were tradeable. Not one market on which the model held a single consistent call failed, in either arm.

That is the mechanism in one sentence, and it decides between the two stories. A model whose Gaussian tail is merely too thin would fail occasionally on calls it never retracted -- a 99.9% call would come in at 99% and the failures would be spread thinly over the whole certain population. That is not what the tape shows. The failures are ALL retractions: the index moved far enough to reverse a stated near-certainty, and every time that happened somebody was already offering the side the model still liked, at a discount no honest quote explains.

## 3. Characterising the seller

Every row is the TRADEABLE population only -- grid observations where an ask stood on the model's side at or below the ceiling -- split on what could be seen about that offer AT THAT SECOND, before the outcome. The question is not which slice is most accurate -- it is whether ANY slice reaches the untradeable benchmark of **99.97%**, because a slice that does is a seller who is plausibly not informed. `covers` marks a slice whose interval contains that benchmark.

### 3a. by ask SIZE resting at the touch -- small = someone offloading, large = a maker quoting

| slice | obs | closes | lost | accuracy | 95% CP | covers 99.97%? |
|---|---|---|---|---|---|---|
| <10 | 173 | 134 | 2 | 98.84% | [95.89, 99.86] | no |
| 10-25 | 135 | 92 | 1 | 99.26% | [88.43, 100.00] | yes |
| 25-50 | 103 | 81 | 0 | 100.00% | [96.48, 100.00] | yes |
| 50-100 | 171 | 132 | 1 | 99.42% | [96.78, 99.99] | yes |
| 100-250 | 213 | 144 | 4 | 98.12% | [94.86, 99.44] | no |
| >=250 | 197 | 133 | 0 | 100.00% | [98.14, 100.00] | yes |

### 3b. by how long the level had RESTED before the touch

A level that has sat there for tens of seconds is a standing quote; one that appeared milliseconds earlier is a decision.

| slice | obs | closes | lost | accuracy | 95% CP | covers 99.97%? |
|---|---|---|---|---|---|---|
| <0.25 s | 519 | 291 | 8 | 98.46% | [96.99, 99.33] | no |
| 0.25-1 s | 101 | 87 | 0 | 100.00% | [96.41, 100.00] | yes |
| 1-5 s | 55 | 46 | 0 | 100.00% | [93.51, 100.00] | yes |
| 5-30 s | 15 | 14 | 0 | 100.00% | [78.20, 100.00] | yes (n<30) |
| >=30 s | 302 | 155 | 0 | 100.00% | [98.79, 100.00] | yes |

### 3c. by DISCOUNT -- how far the ask sat below the model's fair

`pinrun.DUMP_DISCOUNT` already refuses anything cheaper than 15c below fair; the >=15c row is what that guard is buying.

| slice | obs | closes | lost | accuracy | 95% CP | covers 99.97%? |
|---|---|---|---|---|---|---|
| 1.5-3c | 451 | 285 | 1 | 99.78% | [98.14, 100.00] | yes |
| 3-7.5c | 338 | 204 | 1 | 99.70% | [98.36, 99.99] | yes |
| 7.5-15c | 99 | 67 | 0 | 100.00% | [96.34, 100.00] | yes |
| >=15c | 104 | 24 | 6 | 94.23% | [47.35, 99.68] | no |

### 3d. by TIME OF DAY

| slice | obs | closes | lost | accuracy | 95% CP | covers 99.97%? |
|---|---|---|---|---|---|---|
| 00-05 UTC | 234 | 94 | 3 | 98.72% | [96.30, 99.73] | no |
| 06-11 UTC | 335 | 100 | 0 | 100.00% | [98.90, 100.00] | yes |
| 12-17 UTC | 196 | 93 | 3 | 98.47% | [95.59, 99.68] | no |
| 18-23 UTC | 227 | 101 | 2 | 99.12% | [96.45, 100.00] | yes |

### 3e. by COIN

| slice | obs | closes | lost | accuracy | 95% CP | covers 99.97%? |
|---|---|---|---|---|---|---|
| KXBNB15M | 116 | 73 | 1 | 99.14% | [95.29, 99.98] | yes |
| KXBTC15M | 171 | 100 | 0 | 100.00% | [97.87, 100.00] | yes |
| KXDOGE15M | 140 | 86 | 0 | 100.00% | [97.40, 100.00] | yes |
| KXETH15M | 107 | 73 | 0 | 100.00% | [96.61, 100.00] | yes |
| KXHYPE15M | 74 | 53 | 2 | 97.30% | [89.48, 99.63] | no |
| KXNEAR15M | 83 | 61 | 0 | 100.00% | [95.65, 100.00] | yes |
| KXSOL15M | 92 | 62 | 3 | 96.74% | [90.77, 99.32] | no |
| KXXRP15M | 144 | 86 | 2 | 98.61% | [94.06, 99.80] | no |
| KXZEC15M | 65 | 39 | 0 | 100.00% | [94.48, 100.00] | yes |

### 3f. by TAU at the touch

| slice | obs | closes | lost | accuracy | 95% CP | covers 99.97%? |
|---|---|---|---|---|---|---|
| 3-8 s | 89 | 69 | 0 | 100.00% | [95.94, 100.00] | yes |
| 9-15 s | 294 | 179 | 0 | 100.00% | [98.75, 100.00] | yes |
| 16-22 s | 188 | 152 | 2 | 98.94% | [96.21, 99.87] | no |
| 23-30 s | 421 | 239 | 6 | 98.57% | [96.28, 99.60] | no |

### 3g. THE QUESTION THAT MATTERS: is there a seller who is plausibly NOT informed?

Yes, and it is the one the shape predicts. **A level that had been resting on the book for 30 seconds or more when we read it is indistinguishable from the untradeable population: 0 failures in 302 observations over 155 closes, 100.00% [98.79, 100.00], covering the 99.97% benchmark.** A level that appeared within the last quarter-second carries 8 of the 8 failures in the whole tradeable arm: 98.46% [96.99, 99.33] on 519 observations.

The same split shows up twice more and in the same direction. An ask of 250+ contracts -- the size a maker quotes, not the size somebody offloads -- runs 100.00% [98.14, 100.00] on 197 observations. And an ask 15c or more below the model's fair runs 94.23% [47.35, 99.68] on 104 -- that is the population `pinrun.DUMP_DISCOUNT` already refuses, and on this tape it holds 6 of the tradeable arm's 8 failures.

**Read this as a description of the seller, not as a rule.** These slices were chosen after seeing the tape, the failure counts in them are single digits, and `rest`, `size` and `discount` are correlated with each other -- a level that has sat for 30 seconds is not deeply discounted, because if it were it would have been taken. Nothing here is a threshold, and turning any of it into one needs a holdout split and a pre-registered live bar written before the number is seen (CLAUDE.md, AMENDMENT 2026-09-10 item 4). What it IS is the mechanism: the informed seller on this tape is a NEW level, priced far below the model, and the standing quote is not him.

## 4. The control -- an ask existed, but we refuse it as too dear

If the mere EXISTENCE of a seller were the bad news, the dear markets would look like the tradeable ones. If it is the CHEAPNESS that carries the information, they would look like the untradeable ones. Measured: dear **99.87%** [99.64, 99.99] on 6,726 observations, against tradeable 99.19% and never-offered 99.99%.

## 5. The holdout -- first 70% of closes against the last 30%

| half | closes | tradeable acc | untradeable acc | gap | 95% bootstrap |
|---|---|---|---|---|---|
| train (first 70%) | 626 | 99.72% (711) | 100.00% (31,634) | -0.28 pp | [-0.78, +0.00] |
| HOLDOUT (last 30%) | 268 | 97.86% (281) | 99.90% (13,527) | -2.04 pp | [-4.73, +0.01] |

**Both halves point the same way**, so the gap is not an artefact of one stretch of tape.

**But say the rest of it.** Neither half on its own excludes zero -- splitting a population whose failures number 21 in 46,153 leaves each half with too few to carry an interval. What the holdout can say is that the sign did not flip and that the effect is, if anything, larger in the more recent third (-2.04 pp against -0.28 pp). What it cannot do is confirm the size. The pooled gap in section 2 is the estimate; this table is the stability check, and it passes the only test it has the power to run.

---

## What this cannot say

- It cannot say whether the offer would have been OURS. Live we win about 70% of the races we enter. That limit applies equally to both arms of the comparison, which is why the DIFFERENCE survives it and an absolute rate would not.
- It cannot see the offers that were never printed to the book we rebuilt, and `results/RESULTS_tapegaps.md` measured 3.28% of trading-window seconds inside a collector-side silent run. Both arms lose the same seconds.
- It computes no P&L, prices no rule, and proposes no threshold. A threshold would need a pre-registered live bar written before the number was seen (CLAUDE.md, AMENDMENT 2026-09-10 item 4).

