# RESULTS_levels -- expected P&L per CONTRACT SIZE, and how far it scales

`research/pinlevels.py`, profile `default` sha `7f3072d03e80`, written 2026-09-13T01:55Z. One tape pass, scored at 13 sizes.

**Window: 422 book hours, 2026-08-25T03Z to 2026-09-12T18Z, span 18.62 days (19 UTC days). 16,683 candidate rows.**

`$/day` is total P&L divided by that span, idle hours included. The span is truncated at the newest settlement on file, because a book hour after it cannot resolve and can earn nothing.

## Read the 70% column, not the ceiling -- and even it is an upper bound

Live we fill 70% of the attempts we make (50 of 72, measured). The replay wins every race it never ran, so `$/day @70%` is an upper bound, not a central estimate: it assumes the 70% we win are a random sample of the offers on the tape, when the ones we lose the race for are plausibly the better ones. The `ceiling` column assumes we win every race and should not be quoted at all.

Per CLAUDE.md (2026-09-10, rule 5): **the loss rate below is the REPLAY's, not ours.** The tape's population is "an offer was sitting there"; ours is "someone actively sold it to us", and only the second is adversely selected. Measured gap at the live gate: tape 0.11% [0.00, 0.61] against live 3.4% [0.4, 11.7] -- intervals non-overlapping, a 31x gap. Do not substitute one for the other.

## Why there is no live $/day to check this against

The live bank is +$19.77 over about 4.3 days, but that is **eight different strategies**, not one. Split by the gate each run STARTED with (supplied by the coordinating agent, 2026-09-12):

| PIN/ceiling/guard/perMkt/hedge | legs | days | $/day |
|---|---|---|---|
| `0.98/-` | 11 | 0.27 | $+0.79 |
| `0.98/0.988` | 21 | 0.40 | $-110.09 |
| `0.98/0.98` | 50 | 1.10 | $+23.49 |
| `0.995/0.98` | 72 | 1.66 | $+21.10 |
| `0.995/0.98/0.15` | 3 | 0.02 | $-777.42 |
| `0.995/0.98/0.15/1` | 21 | 0.22 | $-9.06 |
| `0.995/0.98/0.15/1/0.9` | 43 | 0.34 | $+42.15 |
| `0.995/0.98/0.15/1/0.8` | 7 | 0.09 | $+41.59 |

**The longest single-gate window is 1.66 days**, and the full current model (0.995 gate, 0.98 ceiling, 15c dump guard, one fill per market, 0.80 hedge) has existed for hours. No live window is long enough to anchor a $/day figure for any gate, and the blended $4.60/day is dragged down by the -$110/day of the 0.988-ceiling era that no longer exists. **So the backtest is the PRIMARY estimate and its own day-block bootstrap interval is the honest uncertainty** -- agreement with a blended live number would be a coincidence, not a check.

## Acceptance anchor 1 -- this scorer reproduces pinsim.run() exactly

Same 72 book hours ending `20260910T04`, same profile sha, size 20, TOUCH mode. `pinsim.run()` is the certified backtest; this file only re-scores the candidates it finds, so if the two disagree the scorer is wrong.

| field | pinsim.run() | pinlevels | 
|---|---|---|
| fills | 156 | 156 |
| closes | 117 | 117 |
| wins / losses | 150 / 6 | 150 / 6 |
| loss rate | 3.85% [1.42, 8.18] | 3.85% [1.42, 8.18] |
| P&L | $-11.01 | $-11.01 |
| mean price | 96.14c | 96.14c |
| refused by the dump rule | 9 | 9 |

**It did NOT pass first time, and both failures were real bugs in this file.** (i) The emission rule tracked DEPTH only, so a later offer that was cheaper but no deeper was never emitted and could never clear the IMPROVE_BY bar -- 153 fills against 156, with the closes matching 117 to 117 and all three misses being SECOND fills of a close. (ii) The scorer sorted rows by `(entry_ts, ticker)`, which re-orders two candidates at the same millisecond alphabetically instead of in the exchange's own order; whichever books the close's slot first sets `best` for the improve bar, so that alone cost one fill and $0.85. Sorting by `entry_ts` alone -- the sort is stable, so ties keep tape order -- matched exactly.

**And note what the anchor window itself says:** over those 72 hours the current model at size 20 LOST $11.01 on 156 fills. Three days is not a verdict, but it is the same direction as the holdout below.

## TOUCH -- what the deployed bot would do

One price, one level: the order sees the best ask and the size resting there, and `MIN_FILL_FRAC` is measured against that touch. This is the live rule, so these are the numbers for the sizes we actually trade.

| size | closes | fills | mean filled | levels swept | VWAP slippage | loss rate (fills) | 95% CP | closes lost | mean price | $/day CEILING | **$/day @70%** | peak concurrent $ | %ROC/day | hedge ON $/day |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 730 | 947 | 1.0 | 1.00 | +0.000c | 2.01% | [1.21, 3.12] | 18 of 730 | 95.91c | $+0.92 | **$+0.64** | $1.95 | 47.1% | $+0.87 |
| 2 | 730 | 947 | 2.0 | 1.00 | +0.000c | 2.01% | [1.21, 3.12] | 18 of 730 | 95.91c | $+1.81 | **$+1.26** | $3.91 | 46.2% | $+1.70 |
| 5 | 723 | 930 | 4.9 | 1.00 | +0.000c | 2.04% | [1.23, 3.17] | 18 of 723 | 95.89c | $+4.48 | **$+3.13** | $9.77 | 45.8% | $+4.23 |
| 10 | 720 | 924 | 9.7 | 1.00 | +0.000c | 2.06% | [1.24, 3.19] | 18 of 720 | 95.90c | $+8.22 | **$+5.75** | $19.54 | 42.1% | $+7.77 |
| 20 | 712 | 908 | 19.2 | 1.00 | +0.000c | 2.09% | [1.26, 3.25] | 18 of 712 | 95.89c | $+17.09 | **$+11.96** | $39.08 | 43.7% | $+15.80 |
| 35 | 708 | 898 | 32.9 | 1.00 | +0.000c | 2.12% | [1.28, 3.28] | 18 of 708 | 95.92c | $+26.97 | **$+18.88** | $68.39 | 39.4% | $+24.62 |
| 50 | 705 | 896 | 46.3 | 1.00 | +0.000c | 2.12% | [1.28, 3.29] | 18 of 705 | 95.91c | $+36.17 | **$+25.32** | $97.70 | 37.0% | $+33.33 |
| 75 | 695 | 873 | 68.8 | 1.00 | +0.000c | 2.18% | [1.31, 3.38] | 18 of 695 | 95.92c | $+49.44 | **$+34.61** | $146.40 | 33.8% | $+45.55 |
| 125 | 671 | 825 | 112.7 | 1.00 | +0.000c | 2.06% | [1.21, 3.28] | 16 of 671 | 95.98c | $+78.88 | **$+55.21** | $244.00 | 32.3% | $+73.68 |
| 250 | 600 | 725 | 212.9 | 1.00 | +0.000c | 2.35% | [1.37, 3.73] | 16 of 600 | 95.95c | $+120.76 | **$+84.53** | $487.75 | 24.8% | $+108.81 |
| 500 | 519 | 598 | 412.5 | 1.00 | +0.000c | 1.50% | [0.69, 2.84] | 9 of 519 | 96.06c | $+306.05 | **$+214.23** | $976.50 | 31.3% | $+283.48 |
| 1000 | 398 | 432 | 855.9 | 1.00 | +0.000c | 2.08% | [0.96, 3.92] | 9 of 398 | 95.86c | $+346.04 | **$+242.23** | $1924.00 | 18.0% | $+329.81 |
| 2000 | 291 | 306 | 1515.4 | 1.00 | +0.000c | 2.61% | [1.14, 5.09] | 8 of 291 | 95.47c | $+400.78 | **$+280.55** | $3848.00 | 10.4% | $+379.77 |

**SATURATION.** $/day peaks at **size 2000** ($+400.78/day ceiling, $+280.55 at the 70% fill rate), which needs **$3848.00 of peak concurrent capital**, and never falls inside the sizes tested.

| size | mean filled | $/day @70% | $/day per contract of size | peak concurrent $ | %/day on the LAST dollar added | worst close | bank needed at 1.5x brake |
|---|---|---|---|---|---|---|---|
| 1 | 1.0 | $+0.64 | $+0.6434 | $1.95 | -- | $-1.91 | $2.87 |
| 2 | 2.0 | $+1.26 | $+0.6324 | $3.91 | +31.7% | $-3.82 | $5.73 |
| 5 | 4.9 | $+3.13 | $+0.6266 | $9.77 | +31.9% | $-9.55 | $14.33 |
| 10 | 9.7 | $+5.75 | $+0.5754 | $19.54 | +26.8% | $-19.10 | $28.65 |
| 20 | 19.2 | $+11.96 | $+0.5982 | $39.08 | +31.8% | $-35.26 | $52.89 |
| 35 | 32.9 | $+18.88 | $+0.5394 | $68.39 | +23.6% | $-66.37 | $99.55 |
| 50 | 46.3 | $+25.32 | $+0.5064 | $97.70 | +22.0% | $-94.81 | $142.22 |
| 75 | 68.8 | $+34.61 | $+0.4614 | $146.40 | +19.1% | $-142.22 | $213.33 |
| 125 | 112.7 | $+55.21 | $+0.4417 | $244.00 | +21.1% | $-237.04 | $355.55 |
| 250 | 212.9 | $+84.53 | $+0.3381 | $487.75 | +12.0% | $-379.26 | $568.88 |
| 500 | 412.5 | $+214.23 | $+0.4285 | $976.50 | +26.5% | $-479.00 | $718.51 |
| 1000 | 855.9 | $+242.23 | $+0.2422 | $1924.00 | +3.0% | $-958.01 | $1437.01 |
| 2000 | 1515.4 | $+280.55 | $+0.1403 | $3848.00 | +2.0% | $-1923.50 | $2885.26 |
**The last column is the number that answers "should I add capital":** the extra $/day the step bought, divided by the extra peak capital it required. The average return on capital stays high long after the MARGINAL return has collapsed, and it is the marginal one that prices the next dollar.

## SWEEP -- how far it COULD scale

The order walks the opposite side's bids from the best price down and pays the VWAP of what it consumes, stopping at `PRICE_CEILING` on EVERY level or as soon as the running VWAP would fail pinrun's own edge/EV gates. **This is a RULE CHANGE, not a better estimate** -- today's bot measures depth at the touch and would simply refuse most of these fills.

| size | closes | fills | mean filled | levels swept | VWAP slippage | loss rate (fills) | 95% CP | closes lost | mean price | $/day CEILING | **$/day @70%** | peak concurrent $ | %ROC/day | hedge ON $/day |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 730 | 947 | 1.0 | 1.00 | +0.000c | 2.01% | [1.21, 3.12] | 18 of 730 | 95.91c | $+0.92 | **$+0.64** | $1.95 | 47.1% | $+0.86 |
| 2 | 730 | 947 | 2.0 | 1.03 | +0.010c | 2.01% | [1.21, 3.12] | 18 of 730 | 95.92c | $+1.82 | **$+1.27** | $3.91 | 46.4% | $+1.69 |
| 5 | 725 | 937 | 5.0 | 1.11 | +0.024c | 2.03% | [1.23, 3.15] | 18 of 725 | 95.90c | $+4.50 | **$+3.15** | $9.78 | 46.0% | $+4.15 |
| 10 | 721 | 926 | 9.9 | 1.20 | +0.041c | 2.05% | [1.24, 3.19] | 18 of 721 | 95.90c | $+8.75 | **$+6.13** | $19.55 | 44.8% | $+8.03 |
| 20 | 713 | 911 | 19.8 | 1.36 | +0.075c | 2.09% | [1.26, 3.24] | 18 of 713 | 95.90c | $+16.94 | **$+11.86** | $39.10 | 43.3% | $+15.36 |
| 35 | 710 | 905 | 34.6 | 1.63 | +0.118c | 2.10% | [1.27, 3.26] | 18 of 710 | 95.92c | $+28.52 | **$+19.96** | $68.42 | 41.7% | $+26.03 |
| 50 | 706 | 903 | 49.2 | 1.84 | +0.151c | 2.10% | [1.27, 3.27] | 18 of 706 | 95.94c | $+39.75 | **$+27.82** | $97.70 | 40.7% | $+36.46 |
| 75 | 699 | 889 | 73.6 | 2.15 | +0.221c | 2.14% | [1.29, 3.32] | 18 of 699 | 95.99c | $+56.64 | **$+39.65** | $146.59 | 38.6% | $+51.07 |
| 125 | 686 | 866 | 121.0 | 2.63 | +0.325c | 2.19% | [1.33, 3.40] | 18 of 686 | 96.02c | $+87.19 | **$+61.03** | $244.35 | 35.7% | $+79.07 |
| 250 | 655 | 820 | 232.4 | 3.58 | +0.531c | 2.32% | [1.40, 3.60] | 18 of 655 | 96.10c | $+133.06 | **$+93.14** | $488.72 | 27.2% | $+123.83 |
| 500 | 569 | 710 | 444.9 | 4.65 | +0.877c | 2.68% | [1.62, 4.15] | 18 of 569 | 96.09c | $+211.73 | **$+148.21** | $977.39 | 21.7% | $+173.48 |
| 1000 | 493 | 592 | 865.7 | 5.47 | +1.359c | 3.04% | [1.81, 4.76] | 17 of 493 | 95.99c | $+399.71 | **$+279.79** | $1952.39 | 20.5% | $+344.70 |
| 2000 | 399 | 459 | 1688.4 | 6.16 | +1.929c | 2.83% | [1.52, 4.79] | 12 of 399 | 95.83c | $+697.56 | **$+488.29** | $3901.72 | 17.9% | $+611.37 |

**SATURATION.** $/day peaks at **size 2000** ($+697.56/day ceiling, $+488.29 at the 70% fill rate), which needs **$3901.72 of peak concurrent capital**, and never falls inside the sizes tested.

| size | mean filled | $/day @70% | $/day per contract of size | peak concurrent $ | %/day on the LAST dollar added | worst close | bank needed at 1.5x brake |
|---|---|---|---|---|---|---|---|
| 1 | 1.0 | $+0.64 | $+0.6434 | $1.95 | -- | $-1.91 | $2.87 |
| 2 | 2.0 | $+1.27 | $+0.6353 | $3.91 | +32.0% | $-3.82 | $5.73 |
| 5 | 5.0 | $+3.15 | $+0.6295 | $9.78 | +32.0% | $-9.55 | $14.33 |
| 10 | 9.9 | $+6.13 | $+0.6126 | $19.55 | +30.5% | $-19.10 | $28.65 |
| 20 | 19.8 | $+11.86 | $+0.5930 | $39.10 | +29.3% | $-35.26 | $52.89 |
| 35 | 34.6 | $+19.96 | $+0.5704 | $68.42 | +27.6% | $-66.37 | $99.55 |
| 50 | 49.2 | $+27.82 | $+0.5564 | $97.70 | +26.8% | $-94.81 | $142.22 |
| 75 | 73.6 | $+39.65 | $+0.5286 | $146.59 | +24.2% | $-142.22 | $213.33 |
| 125 | 121.0 | $+61.03 | $+0.4883 | $244.35 | +21.9% | $-237.04 | $355.55 |
| 250 | 232.4 | $+93.14 | $+0.3726 | $488.72 | +13.1% | $-444.88 | $667.31 |
| 500 | 444.9 | $+148.21 | $+0.2964 | $977.39 | +11.3% | $-870.08 | $1305.13 |
| 1000 | 865.7 | $+279.79 | $+0.2798 | $1952.39 | +13.5% | $-1333.84 | $2000.76 |
| 2000 | 1688.4 | $+488.29 | $+0.2441 | $3901.72 | +10.7% | $-1929.78 | $2894.67 |
**The last column is the number that answers "should I add capital":** the extra $/day the step bought, divided by the extra peak capital it required. The average return on capital stays high long after the MARGINAL return has collapsed, and it is the marginal one that prices the next dollar.

## 70/30 split by close -- nothing is a claim unless the holdout agrees

Cut at close 2026-09-07T15:30Z. Both halves are divided by the SAME full-window span, so the two columns add to the whole rather than each being a rate of its own half. TOUCH mode.

| size | fit fills | fit $ | fit loss% | holdout fills | holdout $ | holdout loss% |
|---|---|---|---|---|---|---|
| 1 | 657 | $+14.71 | 1.52% | 290 | $+2.41 | 3.10% |
| 2 | 657 | $+29.48 | 1.52% | 290 | $+4.18 | 3.10% |
| 5 | 642 | $+70.81 | 1.56% | 288 | $+12.56 | 3.12% |
| 10 | 639 | $+136.07 | 1.56% | 285 | $+17.03 | 3.16% |
| 20 | 627 | $+279.83 | 1.59% | 281 | $+38.49 | 3.20% |
| 35 | 619 | $+445.64 | 1.62% | 279 | $+56.66 | 3.23% |
| 50 | 617 | $+598.37 | 1.62% | 279 | $+75.31 | 3.23% |
| 75 | 598 | $+870.67 | 1.67% | 275 | $+50.12 | 3.27% |
| 125 | 560 | $+1413.06 | 1.43% | 265 | $+56.01 | 3.40% |
| 250 | 495 | $+1911.96 | 1.82% | 230 | $+337.18 | 3.48% |
| 500 | 415 | $+3999.72 | 1.45% | 183 | $+1700.42 | 1.64% |
| 1000 | 303 | $+6971.00 | 0.99% | 129 | $-525.93 | 4.65% |
| 2000 | 198 | $+8366.76 | 1.01% | 108 | $-902.26 | 5.56% |

**THE HOLDOUT IS MUCH WEAKER THAN THE FIT, AND THAT IS THE MOST DECISION-RELEVANT LINE IN THIS FILE.** At size 20 the first 70% of closes made $+279.83 on 627 fills at a 1.59% loss rate; the last 30% made $+38.49 on 281 fills at 3.20% -- the loss rate DOUBLED. At sizes 1000 and 2000 the holdout is outright negative. The 72-hour acceptance window above, which sits inside the holdout, lost money. Two readings are open and this window cannot separate them: the market has got harder, or nine days of holdout is too few closes to tell. Nothing here should be sized as though the fit half were the expectation.


## Block bootstrap BY DAY -- 95% interval on $/day

4,000 resamples of the 19 UTC days with replacement, seed 20260912. The block is the DAY and not the fill: twelve series settle on the same second at rho ~ 0.8, so fills are not independent draws, and idle days stay in the list so they dilute as they do in life.

### TOUCH

| size | $/day ceiling | 95% interval | includes zero? | $/day @70% | 70% interval |
|---|---|---|---|---|---|
| 1 | $+0.92 | [$+0.39, $+1.39] | no | $+0.64 | [$+0.27, $+0.98] |
| 2 | $+1.81 | [$+0.73, $+2.79] | no | $+1.26 | [$+0.51, $+1.95] |
| 5 | $+4.48 | [$+1.90, $+6.82] | no | $+3.13 | [$+1.33, $+4.78] |
| 10 | $+8.22 | [$+3.11, $+12.81] | no | $+5.75 | [$+2.17, $+8.96] |
| 20 | $+17.09 | [$+6.76, $+26.36] | no | $+11.96 | [$+4.73, $+18.45] |
| 35 | $+26.97 | [$+8.72, $+43.40] | no | $+18.88 | [$+6.10, $+30.38] |
| 50 | $+36.17 | [$+11.75, $+58.45] | no | $+25.32 | [$+8.23, $+40.92] |
| 75 | $+49.44 | [$+15.00, $+81.31] | no | $+34.61 | [$+10.50, $+56.92] |
| 125 | $+78.88 | [$+27.12, $+125.09] | no | $+55.21 | [$+18.99, $+87.56] |
| 250 | $+120.76 | [$+20.67, $+204.61] | no | $+84.53 | [$+14.47, $+143.22] |
| 500 | $+306.05 | [$+183.64, $+408.46] | no | $+214.23 | [$+128.55, $+285.92] |
| 1000 | $+346.04 | [$+23.46, $+625.17] | no | $+242.23 | [$+16.42, $+437.62] |
| 2000 | $+400.78 | [$-118.59, $+834.37] | **YES** | $+280.55 | [$-83.02, $+584.06] |

### SWEEP

| size | $/day ceiling | 95% interval | includes zero? | $/day @70% | 70% interval |
|---|---|---|---|---|---|
| 1 | $+0.92 | [$+0.39, $+1.39] | no | $+0.64 | [$+0.27, $+0.98] |
| 2 | $+1.82 | [$+0.76, $+2.76] | no | $+1.27 | [$+0.53, $+1.93] |
| 5 | $+4.50 | [$+1.94, $+6.81] | no | $+3.15 | [$+1.36, $+4.76] |
| 10 | $+8.75 | [$+3.64, $+13.36] | no | $+6.13 | [$+2.55, $+9.35] |
| 20 | $+16.94 | [$+6.78, $+26.06] | no | $+11.86 | [$+4.75, $+18.24] |
| 35 | $+28.52 | [$+10.91, $+44.46] | no | $+19.96 | [$+7.64, $+31.12] |
| 50 | $+39.75 | [$+14.77, $+62.50] | no | $+27.82 | [$+10.34, $+43.75] |
| 75 | $+56.64 | [$+20.27, $+89.93] | no | $+39.65 | [$+14.19, $+62.95] |
| 125 | $+87.19 | [$+25.84, $+142.56] | no | $+61.03 | [$+18.09, $+99.79] |
| 250 | $+133.06 | [$+10.82, $+243.66] | no | $+93.14 | [$+7.58, $+170.56] |
| 500 | $+211.73 | [$+2.05, $+400.37] | no | $+148.21 | [$+1.44, $+280.26] |
| 1000 | $+399.71 | [$+18.23, $+730.37] | no | $+279.79 | [$+12.76, $+511.26] |
| 2000 | $+697.56 | [$-81.59, $+1338.06] | **YES** | $+488.29 | [$-57.11, $+936.64] |

## Drawdown, which is the operator's actual constraint

| size | worst single close | when | worst day | when | days traded | days positive | bank at 1.5x brake |
|---|---|---|---|---|---|---|---|
| 1 | $-1.91 | 2026-09-11T12:30Z | $-1.65 | 2026-08-30 | 19 | 15 | $2.87 |
| 2 | $-3.82 | 2026-09-11T12:30Z | $-3.32 | 2026-08-30 | 19 | 15 | $5.73 |
| 5 | $-9.55 | 2026-09-11T12:30Z | $-7.81 | 2026-08-30 | 19 | 15 | $14.33 |
| 10 | $-19.10 | 2026-09-11T12:30Z | $-16.19 | 2026-08-30 | 19 | 15 | $28.65 |
| 20 | $-35.26 | 2026-09-11T12:30Z | $-32.28 | 2026-08-30 | 19 | 15 | $52.89 |
| 35 | $-66.37 | 2026-09-11T12:30Z | $-59.83 | 2026-08-30 | 19 | 14 | $99.55 |
| 50 | $-94.81 | 2026-09-11T12:30Z | $-82.51 | 2026-08-30 | 19 | 14 | $142.22 |
| 75 | $-142.22 | 2026-09-11T12:30Z | $-95.61 | 2026-08-30 | 19 | 14 | $213.33 |
| 125 | $-237.04 | 2026-09-11T12:30Z | $-147.25 | 2026-09-07 | 19 | 14 | $355.55 |
| 250 | $-379.26 | 2026-09-11T12:30Z | $-463.54 | 2026-08-30 | 19 | 15 | $568.88 |
| 500 | $-479.00 | 2026-09-07T21:30Z | $-288.51 | 2026-09-07 | 19 | 16 | $718.51 |
| 1000 | $-958.01 | 2026-09-07T21:30Z | $-1366.33 | 2026-09-09 | 19 | 15 | $1437.01 |
| 2000 | $-1923.50 | 2026-09-07T14:00Z | $-2434.11 | 2026-09-07 | 19 | 16 | $2885.26 |

## What this cannot tell you

- **The race.** Every fill here assumes the offer was ours.
- **Our loss rate.** See the rule quoted above; the number in the table is the replay's.
- **A later cheaper offer on a market whose first deep candidate was already taken.** The pass emits a row when a candidate offers MORE depth than any earlier one on that market, not when it offers a lower price, so a few second-fills-of-a-close that the IMPROVE_BY bar would have allowed are missed. Conservative.
- **Whether a sweep would move the market.** The SWEEP table consumes resting bids at the prices they rest at. A real 2,000-contract order into a book this thin would be seen, and the levels behind it would move away. So the sweep column is an upper bound on an upper bound.
- **An offer whose TOUCH holds less than one contract.** pinrun's MIN_LEVEL refuses those outright, so the pass never records them and no size can fill from them -- even a sweep that would have taken the level behind. Live-faithful for TOUCH, conservative for SWEEP.
- **Anything about the tape's recording holes.** 6.42% of covered seconds are silent (`results/RESULTS_tapegaps.md`), 3.28% inside the tau band, so every COUNT here is a lower bound by roughly 3%.
