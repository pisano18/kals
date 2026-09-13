# RESULTS_flood -- can we see a jump coming?

*`research/pinflood.py`, 2026-09-13T10:09Z. 18178 coin-closes over 1671 closes, 2026-08-25T04:30Z .. 2026-09-13T10:00Z (19.2 days). Index feed only -- no order book, no replay, no fills, no P&L. Every predictor is computed at close-60s, the instant the settlement window opens, so the bot would have it with at least 30 seconds to spare.*

A **flood** is a close where the model missed by more than 3.0 of its own standard deviations. A Gaussian calls that a 1-in-741 event; here it happens on **373 of 18178 coin-closes (2.05%)** and touches **198 of 1671 closes (11.8%)**.

## 0. Power, before any estimate

Resampling by CLOSE (twelve coins share one, hard rule 4), the smallest top-vs-bottom-quintile lift this design can call at alpha=0.05 with 80% power is **2.50x**. Anything under that is NO POWER, not NO EFFECT.

## 1. Every predictor, ranked within coin

A lift BELOW 1 is not a weak signal, it is a signal pointing the other way: 0.25x means the BOTTOM fifth floods four times as often as the top. Strength is therefore `max(lift, 1/lift)`, and the first version of this table ranked on the raw lift and so buried its own strongest result at the bottom of the list.

| predictor | bottom fifth floods | top fifth floods | lift | 95% by-close interval | strength | beats MDE? |
|---|---|---|---|---|---|---|
| `rv_short` | 4.28% | 1.05% | **0.25x** | [0.15, 0.39] | 4.05x | **yes** |
| `rv_long` | 3.46% | 1.35% | **0.39x** | [0.24, 0.64] | 2.55x | **yes** |
| `rv_ratio` | 3.43% | 1.02% | **0.30x** | [0.17, 0.50] | 3.34x | **yes** |
| `kurt_long` | 1.62% | 2.97% | **1.83x** | [1.14, 3.05] | 1.83x | no |
| `jumps_long` | 1.67% | 2.23% | **1.33x** | [0.86, 2.00] | 1.33x | no |
| `max_move` | 1.62% | 2.89% | **1.78x** | [1.14, 2.85] | 1.78x | no |
| `prev_z` | 2.11% | 1.82% | **0.86x** | [0.55, 1.36] | 1.16x | no |
| `prev_worst_any` | 2.83% | 2.61% | **0.93x** | [0.55, 1.67] | 1.08x | no |
| `btc_kurt` | 1.54% | 3.47% | **2.25x** | [1.25, 4.39] | 2.25x | no |
| `btc_jumps` | 1.54% | 2.20% | **1.43x** | [0.75, 2.84] | 1.43x | no |
| `btc_rv` | 2.94% | 1.54% | **0.53x** | [0.28, 0.97] | 1.90x | no |
| `btc_max_move` | 1.32% | 3.14% | **2.37x** | [1.21, 4.36] | 2.37x | no |
| `hour` | 1.92% | 2.17% | **1.13x** | [0.58, 2.38] | 1.13x | no |

Strongest: **`rv_short`** -- lift 0.25x [0.15, 0.39], strength 4.05x, against an MDE of 2.50x.

## 2. The strongest predictor, quintile by quintile

| fifth of `rv_short` | coin-closes | floods | flood rate | median value |
|---|---|---|---|---|
| 1 (low to high) | 3644 | 156 | 4.28% | 3.614e-05 |
| 2 (low to high) | 3634 | 79 | 2.17% | 5.301e-05 |
| 3 (low to high) | 3633 | 57 | 1.57% | 6.75e-05 |
| 4 (low to high) | 3634 | 43 | 1.18% | 8.476e-05 |
| 5 (low to high) | 3633 | 38 | 1.05% | 0.0001287 |

## 3. Holdout -- fitted on the first 70% of closes, checked on the last 30%

| predictor | lift, first 70% | lift, last 30% | holds? |
|---|---|---|---|
| `rv_short` | 0.28x | 0.14x | yes |
| `rv_ratio` | 0.33x | 0.20x | yes |
| `rv_long` | 0.41x | 0.29x | yes |
| `btc_max_move` | 2.08x | 2.96x | yes |
| `btc_kurt` | 2.08x | 4.84x | yes |
| `btc_rv` | 0.60x | 0.41x | yes |

## 4. What standing aside would cost

Skipping the **BOTTOM fifth of `rv_short`** -- the dangerous end:

- **20.0% of coin-closes** skipped.
- They carry **156 of 373 floods**, 41.8% of them.
- Flood rate on what is left: **1.49%**, against 2.05% today -- a 27% reduction.

**Nothing here is deployed, and nothing here is a loss rate of ours.** A flood is a property of the index, not of our fills; whether skipping floods saves US money depends on whether we would have traded those closes at all, which this file does not know.

