# RESULTS_entry -- how to know when NOT to buy

Generated 2026-09-12T13:03:36Z by `research/pinentry.py` (`--selftest` passes; `main()` refuses real data until it does).

## What was measured, and on which population

The bot's losses are a COLLAPSE of the model's own belief after entry, not a drift. The question is whether the entry second already knows. Four entry-time features were tested: offer provenance (how long the level we would hit had rested, and how big it is against that market's own recent touch), same-coin pre-entry jumpiness, the margin to the strike in sigma units, and tau/price as controls. Every one is computed from data at or before the entry second.

**Two populations, harvested in one pass, because the real one is too small to answer anything alone:**

| | A -- TRADEABLE ENTRIES | B -- MODEL-CERTAIN MOMENTS |
|---|---|---|
| what it is | the live gate would have BOUGHT: an offer existed at <= 98c, deep enough, edge and EV pass, not a >15c dump | the model first reached 99.5% belief with 3 <= tau <= 30, offer or no offer |
| decided by | `pinsim.decide` + `pinrun.DUMP_DISCOUNT` | `pinrun.fair` vs `pinrun.PIN` |
| markets | 409 | 7,328 |
| closes | 274 | 801 |
| collapses (belief < 0.90 after entry, tau >= 3) | 16 (3.91%) | 36 (0.49%) |
| the chosen side lost | 3 (0.73%) | 17 (0.23%) |

Span 2026-09-02T19:15Z to 2026-09-12T04:00Z (9 days), split at day 5: the first 5 days are in sample and the last 4 are the holdout. A feature that only works in the first half is dead.

**A is the unit the question asks about and B is the only one with power.** Provenance features need an offer to exist, so they are reported on A and on the subset of B that had an offer at the certain second. Model-side features exist on both. Nothing is concluded from B alone about what WE would pay.

**NO LOSS RATE ON THIS PAGE IS OUR LOSS RATE.** The tape's population is *an offer was resting there*; ours is *someone actively sold it to us*, and only the second is adversely selected -- the measured gap is 31x (tape 0.11%, live 3.4%). Every rate below RANKS BUCKETS AGAINST EACH OTHER and nothing more (CLAUDE.md AMENDMENT 2026-09-10 item 5).

**Not measured here:** whether we would have won the race for the offer (the replay always does); anything about exiting or hedging after entry; per-coin tails (a separate stage); and `MAX_PER_CLOSE`, which is not applied, so A counts every market the gate liked rather than the portfolio the bot would hold.

## The sample, day by day

Entry opportunity is not stationary over these 9 days, and the 5/4 split is therefore partly a regime split. That is stated here so the holdout is read for what it is.

| day (UTC) | B certain | B collapses | A tradeable | A losses | half |
|---|---|---|---|---|---|
| 09-02 | 80 | 0 | 6 | 0 | first 5 |
| 09-03 | 568 | 0 | 22 | 0 | first 5 |
| 09-04 | 836 | 2 | 66 | 0 | first 5 |
| 09-05 | 864 | 7 | 86 | 1 | first 5 |
| 09-06 | 845 | 1 | 65 | 0 | first 5 |
| 09-07 | 827 | 6 | 30 | 0 | HOLDOUT |
| 09-08 | 908 | 2 | 15 | 0 | HOLDOUT |
| 09-09 | 557 | 2 | 20 | 0 | HOLDOUT |
| 09-10 | 845 | 5 | 34 | 0 | HOLDOUT |
| 09-11 | 845 | 7 | 40 | 1 | HOLDOUT |
| 09-12 | 153 | 4 | 25 | 1 | HOLDOUT |

## Does the collapse flag track the loss?

| population | collapsed & lost | lost, no collapse | collapsed & won | neither |
|---|---|---|---|---|
| A tradeable | 3 | 0 | 13 | 393 |
| B model-certain | 17 | 0 | 19 | 7,292 |

On B, 17 of 17 losses (100.0%) were preceded by belief falling under 0.90 with 3s or more still on the clock. The collapse is 2.1x more common than the loss, so it is the outcome with power; the loss column is reported beside it as a check of direction, never as evidence on its own.

## Is the collapse flag a FEED artefact?

`IndexWS.partial()` models every settlement print that has not yet arrived with the newest spot it holds. If the index feed stalls, belief falls because the DATA went quiet, not because the market moved -- a collapse rate would then be measuring the collector. So the index age at the exact second the alarm fires is recorded. In a replay this age can only be non-zero where the RECORDED tape has a gap, which is exactly the artefact worth ruling out here; live staleness is a different question and is not measured by this file.

| moment | n | index age |
|---|---|---|
| at the certain second, every row | 7,328 | 0.0s median, 0.0s p95, 0.0s worst |
| at the collapse alarm | 36 | 0.0s median, 0.0s p95, 0.0s worst |

0 of 36 alarms (0.0%) fired with an index 3 s or more stale. **Small enough that the collapse flag is reading the market, not the feed.**

## Every loss among the TRADEABLE entries, as it looked at entry

With this few losses the list is more informative than any rate. `age` is seconds the level had rested (`*` = bounded below by a book snapshot), `rel` its size against that market's own median touch over the prior 60 s.

| close (UTC) | coin | tau | paid | margin sd | disc c | age s | fresh s | size | rel | jumps>3sd | max z | collapsed | min belief |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 09-05 11:00 | ZEC | 18 | 86.0c | 2.84 | 13.8 | 0.26 | 0.26 | 60 | 1.60 | 4 | 5.39 | yes | 0.000 |
| 09-11 12:30 | DOGE | 27 | 92.0c | 3.59 | 8.0 | 0.27 | 0.27 | 16 | 0.11 | 4 | 9.68 | yes | 0.000 |
| 09-12 03:00 | SOL | 28 | 97.9c | 3.60 | 2.1 | 0.81 | 0.17 | 283 | 3.61 | 1 | 4.66 | yes | 0.000 |

## Power, stated before the estimates

All coins settle on the same second at rho ~ 0.8, so markets are not independent facts -- CLAUDE.md's own figure is ~1.22 independent observations per close. Two MDEs are therefore given everywhere: one counting MARKETS (too optimistic) and one counting CLOSES (the conservative bound). The truth is between them.

| population | n | baseline | MDE markets | MDE closes |
|---|---|---|---|---|
| A collapse | 409 markets / 274 closes | 3.91% | 6.84% | 7.55% |
| A loss | 409 markets / 274 closes | 0.73% | 2.17% | 2.54% |
| B collapse | 7,328 markets / 801 closes | 0.49% | 0.74% | 1.31% |
| B loss | 7,328 markets / 801 closes | 0.23% | 0.40% | 0.84% |

**Say it plainly: with 3 losses among the tradeable entries in 9 days, NO single feature can be resolved on population A's loss column.** A bucket holding a tenth of A would contain 0.3 losses. Population A's collapse column has 16 events and population B's has 36; B is where the arithmetic has any chance, and B is not the population we trade.


# PRIMARY: population A, the entries the live gate would take

---

## 1a. OFFER AGE -- seconds the level we hit had been resting -- A (tradeable)

_distribution: 409 of 409 rows carry it; p5 0.02 / p25 0.36 / median 299.45 / p75 821.25 / p95 852.1_

**MDE first.** The smallest bucket holds 20 entries over 18 closes. Against a 3.91% collapse baseline that resolves 19.93% counting markets and 20.94% counting closes; on the loss column (0.73% baseline), 16.29% / 17.99%.

**ALL 9 DAYS**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 0.1s | 45 | 42 | 2 (4.44%) | [0.54, 15.15] | 0 | 0.00% | [0.00, 7.87] |
| 0.1-0.5s | 79 | 71 | 9 (11.39%) | [5.34, 20.53] | 2 | 2.53% | [0.31, 8.85] |
| 0.5-2s | 44 | 39 | 1 (2.27%) | [0.06, 12.02] | 1 | 2.27% | [0.06, 12.02] |
| 2-10s | 20 | 18 | 0 (0.00%) | [0.00, 16.84] | 0 | 0.00% | [0.00, 16.84] |
| >= 10s | 221 | 179 | 4 (1.81%) | [0.50, 4.57] | 0 | 0.00% | [0.00, 1.66] |

**FIRST 5 DAYS (in sample)**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 0.1s | 23 | 20 | 0 (0.00%) | [0.00, 14.82] | 0 | 0.00% | [0.00, 14.82] |
| 0.1-0.5s | 61 | 56 | 7 (11.48%) | [4.74, 22.22] | 1 | 1.64% | [0.04, 8.80] |
| 0.5-2s | 34 | 31 | 0 (0.00%) | [0.00, 10.28] | 0 | 0.00% | [0.00, 10.28] |
| 2-10s | 18 | 16 | 0 (0.00%) | [0.00, 18.53] | 0 | 0.00% | [0.00, 18.53] |
| >= 10s | 134 | 112 | 2 (1.49%) | [0.18, 5.29] | 0 | 0.00% | [0.00, 2.72] |

**LAST 4 DAYS (holdout)**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 0.1s | 22 | 22 | 2 (9.09%) | [1.12, 29.16] | 0 | 0.00% | [0.00, 15.44] |
| 0.1-0.5s | 18 | 15 | 2 (11.11%) | [1.38, 34.71] | 1 | 5.56% | [0.14, 27.29] |
| 0.5-2s | 10 | 8 | 1 (10.00%) | [0.25, 44.50] | 1 | 10.00% | [0.25, 44.50] |
| 2-10s | 2 | 2 | 0 (0.00%) | [0.00, 84.19] | 0 | 0.00% | [0.00, 84.19] |
| >= 10s | 87 | 67 | 2 (2.30%) | [0.28, 8.06] | 0 | 0.00% | [0.00, 4.15] |

**Worst bucket `0.1-0.5s` vs the rest, COLLAPSE rate, cluster bootstrap over CLOSES (2,000 draws):**

| sample | difference | 95% CI | verdict |
|---|---|---|---|
| all | +9.27 pp | [+3.15, +15.90] | EXCLUDES 0 |
| first 5d | +10.52 pp | [+2.84, +18.97] | EXCLUDES 0 |
| last 4d | +6.98 pp | [-2.63, +20.90] | includes 0 |

**Does not survive the split.**

---

## 1b. OFFER FRESHNESS -- seconds since the level was last INCREASED -- A (tradeable)

_distribution: 409 of 409 rows carry it; p5 0.01 / p25 0.19 / median 0.93 / p75 42.01 / p95 416.95_

**MDE first.** The smallest bucket holds 43 entries over 41 closes. Against a 3.91% collapse baseline that resolves 14.18% counting markets and 14.47% counting closes; on the loss column (0.73% baseline), 7.81% / 8.18%.

**ALL 9 DAYS**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 0.1s | 68 | 62 | 5 (7.35%) | [2.43, 16.33] | 0 | 0.00% | [0.00, 5.28] |
| 0.1-0.5s | 98 | 85 | 9 (9.18%) | [4.29, 16.72] | 3 | 3.06% | [0.64, 8.69] |
| 0.5-2s | 67 | 60 | 1 (1.49%) | [0.04, 8.04] | 0 | 0.00% | [0.00, 5.36] |
| 2-10s | 43 | 41 | 0 (0.00%) | [0.00, 8.22] | 0 | 0.00% | [0.00, 8.22] |
| >= 10s | 133 | 110 | 1 (0.75%) | [0.02, 4.12] | 0 | 0.00% | [0.00, 2.74] |

**FIRST 5 DAYS (in sample)**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 0.1s | 40 | 36 | 2 (5.00%) | [0.61, 16.92] | 0 | 0.00% | [0.00, 8.81] |
| 0.1-0.5s | 69 | 62 | 6 (8.70%) | [3.26, 17.97] | 1 | 1.45% | [0.04, 7.81] |
| 0.5-2s | 56 | 49 | 1 (1.79%) | [0.05, 9.55] | 0 | 0.00% | [0.00, 6.38] |
| 2-10s | 34 | 33 | 0 (0.00%) | [0.00, 10.28] | 0 | 0.00% | [0.00, 10.28] |
| >= 10s | 71 | 62 | 0 (0.00%) | [0.00, 5.06] | 0 | 0.00% | [0.00, 5.06] |

**LAST 4 DAYS (holdout)**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 0.1s | 28 | 26 | 3 (10.71%) | [2.27, 28.23] | 0 | 0.00% | [0.00, 12.34] |
| 0.1-0.5s | 29 | 23 | 3 (10.34%) | [2.19, 27.35] | 2 | 6.90% | [0.85, 22.77] |
| 0.5-2s | 11 | 11 | 0 (0.00%) | [0.00, 28.49] | 0 | 0.00% | [0.00, 28.49] |
| 2-10s | 9 | 8 | 0 (0.00%) | [0.00, 33.63] | 0 | 0.00% | [0.00, 33.63] |
| >= 10s | 62 | 48 | 1 (1.61%) | [0.04, 8.66] | 0 | 0.00% | [0.00, 5.78] |

**Worst bucket `0.1-0.5s` vs the rest, COLLAPSE rate, cluster bootstrap over CLOSES (2,000 draws):**

| sample | difference | 95% CI | verdict |
|---|---|---|---|
| all | +6.93 pp | [+2.11, +12.59] | EXCLUDES 0 |
| first 5d | +7.20 pp | [+0.67, +14.06] | EXCLUDES 0 |
| last 4d | +6.71 pp | [-0.93, +15.73] | includes 0 |

**Does not survive the split.**

---

## 1c. OFFER SIZE vs this market's own median touch over the prior 60s -- A (tradeable)

_distribution: 409 of 409 rows carry it; p5 0.132 / p25 0.882 / median 1 / p75 2.441 / p95 11.431_

**MDE first.** The smallest bucket holds 48 entries over 45 closes. Against a 3.91% collapse baseline that resolves 13.56% counting markets and 13.92% counting closes; on the loss column (0.73% baseline), 7.02% / 7.47%.

**ALL 9 DAYS**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 0.5x | 65 | 57 | 2 (3.08%) | [0.37, 10.68] | 1 | 1.54% | [0.04, 8.28] |
| 0.5-1x | 49 | 47 | 2 (4.08%) | [0.50, 13.98] | 0 | 0.00% | [0.00, 7.25] |
| 1-2x | 175 | 141 | 6 (3.43%) | [1.27, 7.31] | 1 | 0.57% | [0.01, 3.14] |
| 2-5x | 72 | 64 | 5 (6.94%) | [2.29, 15.47] | 1 | 1.39% | [0.04, 7.50] |
| >= 5x | 48 | 45 | 1 (2.08%) | [0.05, 11.07] | 0 | 0.00% | [0.00, 7.40] |

**FIRST 5 DAYS (in sample)**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 0.5x | 47 | 42 | 0 (0.00%) | [0.00, 7.55] | 0 | 0.00% | [0.00, 7.55] |
| 0.5-1x | 36 | 34 | 2 (5.56%) | [0.68, 18.66] | 0 | 0.00% | [0.00, 9.74] |
| 1-2x | 104 | 86 | 4 (3.85%) | [1.06, 9.56] | 1 | 0.96% | [0.02, 5.24] |
| 2-5x | 51 | 44 | 2 (3.92%) | [0.48, 13.46] | 0 | 0.00% | [0.00, 6.98] |
| >= 5x | 32 | 30 | 1 (3.12%) | [0.08, 16.22] | 0 | 0.00% | [0.00, 10.89] |

**LAST 4 DAYS (holdout)**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 0.5x | 18 | 15 | 2 (11.11%) | [1.38, 34.71] | 1 | 5.56% | [0.14, 27.29] |
| 0.5-1x | 13 | 13 | 0 (0.00%) | [0.00, 24.71] | 0 | 0.00% | [0.00, 24.71] |
| 1-2x | 71 | 55 | 2 (2.82%) | [0.34, 9.81] | 0 | 0.00% | [0.00, 5.06] |
| 2-5x | 21 | 20 | 3 (14.29%) | [3.05, 36.34] | 1 | 4.76% | [0.12, 23.82] |
| >= 5x | 16 | 15 | 0 (0.00%) | [0.00, 20.59] | 0 | 0.00% | [0.00, 20.59] |

**Worst bucket `2-5x` vs the rest, COLLAPSE rate, cluster bootstrap over CLOSES (2,000 draws):**

| sample | difference | 95% CI | verdict |
|---|---|---|---|
| all | +3.68 pp | [-1.57, +10.04] | includes 0 |
| first 5d | +0.73 pp | [-4.17, +7.34] | includes 0 |
| last 4d | +10.90 pp | [-1.69, +27.03] | includes 0 |

**Does not survive the split.**

---

## 1d. OFFER SIZE, absolute contracts at the level -- A (tradeable)

_distribution: 409 of 409 rows carry it; p5 14 / p25 38 / median 117.5 / p75 300 / p95 3066_

**MDE first.** The smallest bucket holds 45 entries over 41 closes. Against a 3.91% collapse baseline that resolves 13.92% counting markets and 14.47% counting closes; on the loss column (0.73% baseline), 7.47% / 8.18%.

**ALL 9 DAYS**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 20 | 45 | 41 | 2 (4.44%) | [0.54, 15.15] | 1 | 2.22% | [0.06, 11.77] |
| 20-100 | 149 | 125 | 6 (4.03%) | [1.49, 8.56] | 1 | 0.67% | [0.02, 3.68] |
| 100-500 | 139 | 118 | 6 (4.32%) | [1.60, 9.16] | 1 | 0.72% | [0.02, 3.94] |
| >= 500 | 76 | 72 | 2 (2.63%) | [0.32, 9.18] | 0 | 0.00% | [0.00, 4.74] |

**FIRST 5 DAYS (in sample)**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 20 | 27 | 25 | 0 (0.00%) | [0.00, 12.77] | 0 | 0.00% | [0.00, 12.77] |
| 20-100 | 99 | 84 | 4 (4.04%) | [1.11, 10.02] | 1 | 1.01% | [0.03, 5.50] |
| 100-500 | 97 | 80 | 3 (3.09%) | [0.64, 8.77] | 0 | 0.00% | [0.00, 3.73] |
| >= 500 | 47 | 46 | 2 (4.26%) | [0.52, 14.54] | 0 | 0.00% | [0.00, 7.55] |

**LAST 4 DAYS (holdout)**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 20 | 18 | 16 | 2 (11.11%) | [1.38, 34.71] | 1 | 5.56% | [0.14, 27.29] |
| 20-100 | 50 | 41 | 2 (4.00%) | [0.49, 13.71] | 0 | 0.00% | [0.00, 7.11] |
| 100-500 | 42 | 38 | 3 (7.14%) | [1.50, 19.48] | 1 | 2.38% | [0.06, 12.57] |
| >= 500 | 29 | 26 | 0 (0.00%) | [0.00, 11.94] | 0 | 0.00% | [0.00, 11.94] |

**Worst bucket `< 20` vs the rest, COLLAPSE rate, cluster bootstrap over CLOSES (2,000 draws):**

| sample | difference | 95% CI | verdict |
|---|---|---|---|
| all | +0.60 pp | [-5.18, +9.44] | includes 0 |
| first 5d | -3.70 pp | [-6.17, -1.60] | EXCLUDES 0 |
| last 4d | +6.98 pp | [-6.45, +28.18] | includes 0 |

**Does not survive the split.**

---

## 2a. PRE-ENTRY JUMPINESS -- 1s index moves > 3 sigma in the last 120s -- A (tradeable)

_distribution: 409 of 409 rows carry it; p5 0 / p25 2 / median 3 / p75 4 / p95 6_

**MDE first.** The smallest bucket holds 39 entries over 37 closes. Against a 3.91% collapse baseline that resolves 14.78% counting markets and 15.12% counting closes; on the loss column (0.73% baseline), 8.59% / 9.04%.

**ALL 9 DAYS**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| 0 | 39 | 37 | 0 (0.00%) | [0.00, 9.03] | 0 | 0.00% | [0.00, 9.03] |
| 1 | 61 | 57 | 2 (3.28%) | [0.40, 11.35] | 1 | 1.64% | [0.04, 8.80] |
| 2-3 | 177 | 145 | 4 (2.26%) | [0.62, 5.68] | 0 | 0.00% | [0.00, 2.06] |
| >= 4 | 132 | 106 | 10 (7.58%) | [3.69, 13.49] | 2 | 1.52% | [0.18, 5.37] |

**FIRST 5 DAYS (in sample)**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| 0 | 22 | 21 | 0 (0.00%) | [0.00, 15.44] | 0 | 0.00% | [0.00, 15.44] |
| 1 | 44 | 40 | 1 (2.27%) | [0.06, 12.02] | 0 | 0.00% | [0.00, 8.04] |
| 2-3 | 111 | 97 | 2 (1.80%) | [0.22, 6.36] | 0 | 0.00% | [0.00, 3.27] |
| >= 4 | 93 | 78 | 6 (6.45%) | [2.40, 13.52] | 1 | 1.08% | [0.03, 5.85] |

**LAST 4 DAYS (holdout)**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| 0 | 17 | 16 | 0 (0.00%) | [0.00, 19.51] | 0 | 0.00% | [0.00, 19.51] |
| 1 | 17 | 17 | 1 (5.88%) | [0.15, 28.69] | 1 | 5.88% | [0.15, 28.69] |
| 2-3 | 66 | 48 | 2 (3.03%) | [0.37, 10.52] | 0 | 0.00% | [0.00, 5.44] |
| >= 4 | 39 | 28 | 4 (10.26%) | [2.87, 24.22] | 1 | 2.56% | [0.06, 13.48] |

**Worst bucket `>= 4` vs the rest, COLLAPSE rate, cluster bootstrap over CLOSES (2,000 draws):**

| sample | difference | 95% CI | verdict |
|---|---|---|---|
| all | +5.41 pp | [+0.55, +11.00] | EXCLUDES 0 |
| first 5d | +4.76 pp | [-0.08, +10.53] | includes 0 |
| last 4d | +7.26 pp | [-3.23, +20.97] | includes 0 |

**Does not survive the split.**

---

## 2b. LARGEST 1s index move in the last 120s, in sigma units -- A (tradeable)

_distribution: 409 of 409 rows carry it; p5 2.65 / p25 4.21 / median 5.63 / p75 7.89 / p95 11.13_

**MDE first.** The smallest bucket holds 5 entries over 5 closes. Against a 3.91% collapse baseline that resolves 55.02% counting markets and 55.02% counting closes; on the loss column (0.73% baseline), 55.02% / 55.02%.

**ALL 9 DAYS**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 2 | 5 | 5 | 0 (0.00%) | [0.00, 52.18] | 0 | 0.00% | [0.00, 52.18] |
| 2-3 | 34 | 33 | 0 (0.00%) | [0.00, 10.28] | 0 | 0.00% | [0.00, 10.28] |
| 3-4 | 47 | 45 | 0 (0.00%) | [0.00, 7.55] | 0 | 0.00% | [0.00, 7.55] |
| 4-6 | 134 | 118 | 6 (4.48%) | [1.66, 9.49] | 2 | 1.49% | [0.18, 5.29] |
| >= 6 | 189 | 141 | 10 (5.29%) | [2.57, 9.51] | 1 | 0.53% | [0.01, 2.91] |

**FIRST 5 DAYS (in sample)**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 2 | 3 | 3 | 0 (0.00%) | [0.00, 70.76] | 0 | 0.00% | [0.00, 70.76] |
| 2-3 | 19 | 19 | 0 (0.00%) | [0.00, 17.65] | 0 | 0.00% | [0.00, 17.65] |
| 3-4 | 31 | 30 | 0 (0.00%) | [0.00, 11.22] | 0 | 0.00% | [0.00, 11.22] |
| 4-6 | 84 | 75 | 4 (4.76%) | [1.31, 11.75] | 1 | 1.19% | [0.03, 6.46] |
| >= 6 | 133 | 99 | 5 (3.76%) | [1.23, 8.56] | 0 | 0.00% | [0.00, 2.74] |

**LAST 4 DAYS (holdout)**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 2 | 2 | 2 | 0 (0.00%) | [0.00, 84.19] | 0 | 0.00% | [0.00, 84.19] |
| 2-3 | 15 | 14 | 0 (0.00%) | [0.00, 21.80] | 0 | 0.00% | [0.00, 21.80] |
| 3-4 | 16 | 15 | 0 (0.00%) | [0.00, 20.59] | 0 | 0.00% | [0.00, 20.59] |
| 4-6 | 50 | 43 | 2 (4.00%) | [0.49, 13.71] | 1 | 2.00% | [0.05, 10.65] |
| >= 6 | 56 | 42 | 5 (8.93%) | [2.96, 19.62] | 1 | 1.79% | [0.05, 9.55] |

**Worst bucket `>= 6` vs the rest, COLLAPSE rate, cluster bootstrap over CLOSES (2,000 draws):**

| sample | difference | 95% CI | verdict |
|---|---|---|---|
| all | +2.56 pp | [-1.40, +6.96] | includes 0 |
| first 5d | +0.84 pp | [-3.35, +5.27] | includes 0 |
| last 4d | +6.52 pp | [-1.42, +17.74] | includes 0 |

**Does not survive the split.**

---

## 3. MARGIN TO THE STRIKE at entry, in sigma units -- A (tradeable)

_distribution: 409 of 409 rows carry it; p5 2.607 / p25 2.772 / median 3.17 / p75 6.006 / p95 7.034_

**MDE first.** The smallest bucket holds 10 entries over 10 closes. Against a 3.91% collapse baseline that resolves 30.79% counting markets and 30.79% counting closes; on the loss column (0.73% baseline), 30.79% / 30.79%.

**ALL 9 DAYS**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| 2.58-3 | 169 | 135 | 8 (4.73%) | [2.07, 9.11] | 1 | 0.59% | [0.01, 3.25] |
| 3-4 | 96 | 82 | 6 (6.25%) | [2.33, 13.11] | 2 | 2.08% | [0.25, 7.32] |
| 4-5 | 31 | 29 | 2 (6.45%) | [0.79, 21.42] | 0 | 0.00% | [0.00, 11.22] |
| 5-6 | 10 | 10 | 0 (0.00%) | [0.00, 30.85] | 0 | 0.00% | [0.00, 30.85] |
| >= 6 | 103 | 85 | 0 (0.00%) | [0.00, 3.52] | 0 | 0.00% | [0.00, 3.52] |

**FIRST 5 DAYS (in sample)**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| 2.58-3 | 121 | 99 | 6 (4.96%) | [1.84, 10.48] | 1 | 0.83% | [0.02, 4.52] |
| 3-4 | 68 | 58 | 2 (2.94%) | [0.36, 10.22] | 0 | 0.00% | [0.00, 5.28] |
| 4-5 | 21 | 20 | 1 (4.76%) | [0.12, 23.82] | 0 | 0.00% | [0.00, 16.11] |
| 5-6 | 7 | 7 | 0 (0.00%) | [0.00, 40.96] | 0 | 0.00% | [0.00, 40.96] |
| >= 6 | 53 | 46 | 0 (0.00%) | [0.00, 6.72] | 0 | 0.00% | [0.00, 6.72] |

**LAST 4 DAYS (holdout)**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| 2.58-3 | 48 | 36 | 2 (4.17%) | [0.51, 14.25] | 0 | 0.00% | [0.00, 7.40] |
| 3-4 | 28 | 24 | 4 (14.29%) | [4.03, 32.67] | 2 | 7.14% | [0.88, 23.50] |
| 4-5 | 10 | 9 | 1 (10.00%) | [0.25, 44.50] | 0 | 0.00% | [0.00, 30.85] |
| 5-6 | 3 | 3 | 0 (0.00%) | [0.00, 70.76] | 0 | 0.00% | [0.00, 70.76] |
| >= 6 | 50 | 39 | 0 (0.00%) | [0.00, 7.11] | 0 | 0.00% | [0.00, 7.11] |

**Worst bucket `4-5` vs the rest, COLLAPSE rate, cluster bootstrap over CLOSES (2,000 draws):**

| sample | difference | 95% CI | verdict |
|---|---|---|---|
| all | +2.75 pp | [-4.12, +12.85] | includes 0 |
| first 5d | +1.55 pp | [-4.98, +12.59] | includes 0 |
| last 4d | +5.35 pp | [-6.25, +29.33] | includes 0 |

**Does not survive the split.**

---

## 4a. TAU AT ENTRY (control) -- A (tradeable)

_distribution: 409 of 409 rows carry it; p5 7 / p25 18 / median 28 / p75 30 / p95 30_

**MDE first.** The smallest bucket holds 32 entries over 31 closes. Against a 3.91% collapse baseline that resolves 16.10% counting markets and 16.32% counting closes; on the loss column (0.73% baseline), 10.40% / 10.72%.

**ALL 9 DAYS**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| 3-9s | 32 | 31 | 1 (3.12%) | [0.08, 16.22] | 0 | 0.00% | [0.00, 10.89] |
| 10-19s | 85 | 72 | 4 (4.71%) | [1.30, 11.61] | 1 | 1.18% | [0.03, 6.38] |
| 20-30s | 292 | 213 | 11 (3.77%) | [1.90, 6.64] | 2 | 0.68% | [0.08, 2.45] |

**FIRST 5 DAYS (in sample)**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| 3-9s | 23 | 22 | 1 (4.35%) | [0.11, 21.95] | 0 | 0.00% | [0.00, 14.82] |
| 10-19s | 57 | 48 | 1 (1.75%) | [0.04, 9.39] | 1 | 1.75% | [0.04, 9.39] |
| 20-30s | 190 | 139 | 7 (3.68%) | [1.49, 7.44] | 0 | 0.00% | [0.00, 1.92] |

**LAST 4 DAYS (holdout)**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| 3-9s | 9 | 9 | 0 (0.00%) | [0.00, 33.63] | 0 | 0.00% | [0.00, 33.63] |
| 10-19s | 28 | 24 | 3 (10.71%) | [2.27, 28.23] | 0 | 0.00% | [0.00, 12.34] |
| 20-30s | 102 | 74 | 4 (3.92%) | [1.08, 9.74] | 2 | 1.96% | [0.24, 6.90] |

**Worst bucket `10-19s` vs the rest, COLLAPSE rate, cluster bootstrap over CLOSES (2,000 draws):**

| sample | difference | 95% CI | verdict |
|---|---|---|---|
| all | +1.00 pp | [-4.20, +7.51] | includes 0 |
| first 5d | -2.00 pp | [-5.80, +2.58] | includes 0 |
| last 4d | +7.11 pp | [-6.41, +23.39] | includes 0 |

**Does not survive the split.**

---

## 4b. PRICE PAID (control) -- A (tradeable)

_distribution: 409 of 409 rows carry it; p5 0.87 / p25 0.92 / median 0.96 / p75 0.977 / p95 0.98_

**MDE first.** The smallest bucket holds 54 entries over 52 closes. Against a 3.91% collapse baseline that resolves 12.93% counting markets and 13.12% counting closes; on the loss column (0.73% baseline), 6.25% / 6.49%.

**ALL 9 DAYS**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 94c | 137 | 106 | 8 (5.84%) | [2.55, 11.18] | 2 | 1.46% | [0.18, 5.17] |
| 94-97c | 111 | 96 | 6 (5.41%) | [2.01, 11.39] | 0 | 0.00% | [0.00, 3.27] |
| 97-98c | 107 | 94 | 2 (1.87%) | [0.23, 6.59] | 1 | 0.93% | [0.02, 5.10] |
| >= 98c | 54 | 52 | 0 (0.00%) | [0.00, 6.60] | 0 | 0.00% | [0.00, 6.60] |

**FIRST 5 DAYS (in sample)**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 94c | 79 | 64 | 3 (3.80%) | [0.79, 10.70] | 1 | 1.27% | [0.03, 6.85] |
| 94-97c | 80 | 69 | 5 (6.25%) | [2.06, 13.99] | 0 | 0.00% | [0.00, 4.51] |
| 97-98c | 73 | 66 | 1 (1.37%) | [0.03, 7.40] | 0 | 0.00% | [0.00, 4.93] |
| >= 98c | 38 | 36 | 0 (0.00%) | [0.00, 9.25] | 0 | 0.00% | [0.00, 9.25] |

**LAST 4 DAYS (holdout)**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 94c | 58 | 42 | 5 (8.62%) | [2.86, 18.98] | 1 | 1.72% | [0.04, 9.24] |
| 94-97c | 31 | 27 | 1 (3.23%) | [0.08, 16.70] | 0 | 0.00% | [0.00, 11.22] |
| 97-98c | 34 | 28 | 1 (2.94%) | [0.07, 15.33] | 1 | 2.94% | [0.07, 15.33] |
| >= 98c | 16 | 16 | 0 (0.00%) | [0.00, 20.59] | 0 | 0.00% | [0.00, 20.59] |

**Worst bucket `< 94c` vs the rest, COLLAPSE rate, cluster bootstrap over CLOSES (2,000 draws):**

| sample | difference | 95% CI | verdict |
|---|---|---|---|
| all | +2.90 pp | [-1.71, +8.11] | includes 0 |
| first 5d | +0.66 pp | [-4.06, +6.26] | includes 0 |
| last 4d | +6.15 pp | [-1.24, +15.08] | includes 0 |

**Does not survive the split.**

---

## 4c. DISCOUNT BELOW FAIR at entry, cents (the LIVE guard cuts at 15c) -- A (tradeable)

_distribution: 409 of 409 rows carry it; p5 1.73 / p25 2.1 / median 3.77 / p75 8 / p95 13_

**MDE first.** The smallest bucket holds 3 entries over 3 closes. Against a 3.91% collapse baseline that resolves 78.72% counting markets and 78.72% counting closes; on the loss column (0.73% baseline), 78.72% / 78.72%.

**ALL 9 DAYS**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| 1-2c | 64 | 61 | 1 (1.56%) | [0.04, 8.40] | 0 | 0.00% | [0.00, 5.60] |
| 2-5c | 178 | 146 | 6 (3.37%) | [1.25, 7.19] | 1 | 0.56% | [0.01, 3.09] |
| 5-10c | 100 | 85 | 3 (3.00%) | [0.62, 8.52] | 1 | 1.00% | [0.03, 5.45] |
| 10-15c | 64 | 55 | 6 (9.38%) | [3.52, 19.30] | 1 | 1.56% | [0.04, 8.40] |
| >= 15c (guard refuses) | 3 | 3 | 0 (0.00%) | [0.00, 70.76] | 0 | 0.00% | [0.00, 70.76] |

**FIRST 5 DAYS (in sample)**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| 1-2c | 48 | 45 | 1 (2.08%) | [0.05, 11.07] | 0 | 0.00% | [0.00, 7.40] |
| 2-5c | 120 | 100 | 4 (3.33%) | [0.92, 8.31] | 0 | 0.00% | [0.00, 3.03] |
| 5-10c | 70 | 59 | 1 (1.43%) | [0.04, 7.70] | 0 | 0.00% | [0.00, 5.13] |
| 10-15c | 31 | 29 | 3 (9.68%) | [2.04, 25.75] | 1 | 3.23% | [0.08, 16.70] |
| >= 15c (guard refuses) | 1 | 1 | 0 (0.00%) | [0.00, 97.50] | 0 | 0.00% | [0.00, 97.50] |

**LAST 4 DAYS (holdout)**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| 1-2c | 16 | 16 | 0 (0.00%) | [0.00, 20.59] | 0 | 0.00% | [0.00, 20.59] |
| 2-5c | 58 | 46 | 2 (3.45%) | [0.42, 11.91] | 1 | 1.72% | [0.04, 9.24] |
| 5-10c | 30 | 26 | 2 (6.67%) | [0.82, 22.07] | 1 | 3.33% | [0.08, 17.22] |
| 10-15c | 33 | 26 | 3 (9.09%) | [1.92, 24.33] | 0 | 0.00% | [0.00, 10.58] |
| >= 15c (guard refuses) | 2 | 2 | 0 (0.00%) | [0.00, 84.19] | 0 | 0.00% | [0.00, 84.19] |

**Worst bucket `10-15c` vs the rest, COLLAPSE rate, cluster bootstrap over CLOSES (2,000 draws):**

| sample | difference | 95% CI | verdict |
|---|---|---|---|
| all | +6.48 pp | [+0.07, +14.04] | EXCLUDES 0 |
| first 5d | +7.17 pp | [-2.58, +19.33] | includes 0 |
| last 4d | +5.32 pp | [-1.04, +14.12] | includes 0 |

**Does not survive the split.**


# COMPANION: population B, every moment the model was certain

Same features, ~30x the rows, on the population the 48-hour collapse table was built from. This is the backward-looking companion a null needs to be interpretable: an estimator that finds nothing here has been shown incapable of finding anything.

---

## 1a. OFFER AGE -- seconds the level we hit had been resting -- B (model-certain)

_distribution: 5,520 of 7,328 rows carry it; p5 0.92 / p25 788.62 / median 814.83 / p75 830.59 / p95 851.04_

**MDE first.** The smallest bucket holds 67 entries over 59 closes. Against a 0.49% collapse baseline that resolves 5.06% counting markets and 5.73% counting closes; on the loss column (0.23% baseline), 5.06% / 5.73%.

**ALL 9 DAYS**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 0.1s | 67 | 59 | 2 (2.99%) | [0.36, 10.37] | 2 | 2.99% | [0.36, 10.37] |
| 0.1-0.5s | 142 | 118 | 9 (6.34%) | [2.94, 11.69] | 5 | 3.52% | [1.15, 8.03] |
| 0.5-2s | 127 | 108 | 0 (0.00%) | [0.00, 2.86] | 0 | 0.00% | [0.00, 2.86] |
| 2-10s | 104 | 96 | 2 (1.92%) | [0.23, 6.77] | 0 | 0.00% | [0.00, 3.48] |
| >= 10s | 5,080 | 798 | 20 (0.39%) | [0.24, 0.61] | 8 | 0.16% | [0.07, 0.31] |
| n/a | 1,808 | 556 | 3 (0.17%) | [0.03, 0.48] | 2 | 0.11% | [0.01, 0.40] |

**Worst bucket `0.1-0.5s` vs the rest, COLLAPSE rate, cluster bootstrap over CLOSES (2,000 draws):**

| sample | difference | 95% CI | verdict |
|---|---|---|---|
| all | +5.89 pp | [+2.10, +10.38] | EXCLUDES 0 |
| first 5d | +3.61 pp | [+0.29, +8.11] | EXCLUDES 0 |
| last 4d | +11.66 pp | [+2.00, +23.84] | EXCLUDES 0 |

**SURVIVES THE SPLIT.**

---

## 1b. OFFER FRESHNESS -- seconds since the level was last INCREASED -- B (model-certain)

_distribution: 5,520 of 7,328 rows carry it; p5 0.26 / p25 20.7 / median 274.79 / p75 646.05 / p95 807.06_

**MDE first.** The smallest bucket holds 142 entries over 123 closes. Against a 0.49% collapse baseline that resolves 2.81% counting markets and 3.03% counting closes; on the loss column (0.23% baseline), 2.41% / 2.78%.

**ALL 9 DAYS**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 0.1s | 142 | 123 | 7 (4.93%) | [2.00, 9.89] | 5 | 3.52% | [1.15, 8.03] |
| 0.1-0.5s | 244 | 184 | 5 (2.05%) | [0.67, 4.72] | 2 | 0.82% | [0.10, 2.93] |
| 0.5-2s | 338 | 232 | 3 (0.89%) | [0.18, 2.57] | 0 | 0.00% | [0.00, 1.09] |
| 2-10s | 438 | 291 | 4 (0.91%) | [0.25, 2.32] | 1 | 0.23% | [0.01, 1.27] |
| >= 10s | 4,358 | 780 | 14 (0.32%) | [0.18, 0.54] | 7 | 0.16% | [0.06, 0.33] |
| n/a | 1,808 | 556 | 3 (0.17%) | [0.03, 0.48] | 2 | 0.11% | [0.01, 0.40] |

**Worst bucket `< 0.1s` vs the rest, COLLAPSE rate, cluster bootstrap over CLOSES (2,000 draws):**

| sample | difference | 95% CI | verdict |
|---|---|---|---|
| all | +4.45 pp | [+0.96, +8.71] | EXCLUDES 0 |
| first 5d | +1.68 pp | [-0.54, +5.12] | includes 0 |
| last 4d | +10.10 pp | [+1.63, +20.88] | EXCLUDES 0 |

**Does not survive the split.**

---

## 1c. OFFER SIZE vs this market's own median touch over the prior 60s -- B (model-certain)

_distribution: 5,520 of 7,328 rows carry it; p5 0.247 / p25 1 / median 1 / p75 1 / p95 13.158_

**MDE first.** The smallest bucket holds 163 entries over 138 closes. Against a 0.49% collapse baseline that resolves 2.62% counting markets and 2.85% counting closes; on the loss column (0.23% baseline), 2.10% / 2.48%.

**ALL 9 DAYS**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 0.5x | 369 | 257 | 7 (1.90%) | [0.77, 3.87] | 4 | 1.08% | [0.30, 2.75] |
| 0.5-1x | 163 | 138 | 3 (1.84%) | [0.38, 5.28] | 0 | 0.00% | [0.00, 2.24] |
| 1-2x | 4,323 | 775 | 18 (0.42%) | [0.25, 0.66] | 8 | 0.19% | [0.08, 0.36] |
| 2-5x | 197 | 162 | 3 (1.52%) | [0.32, 4.39] | 1 | 0.51% | [0.01, 2.80] |
| >= 5x | 468 | 288 | 2 (0.43%) | [0.05, 1.54] | 2 | 0.43% | [0.05, 1.54] |
| n/a | 1,808 | 556 | 3 (0.17%) | [0.03, 0.48] | 2 | 0.11% | [0.01, 0.40] |

**Worst bucket `< 0.5x` vs the rest, COLLAPSE rate, cluster bootstrap over CLOSES (2,000 draws):**

| sample | difference | 95% CI | verdict |
|---|---|---|---|
| all | +1.39 pp | [-0.05, +3.09] | includes 0 |
| first 5d | +1.08 pp | [-0.16, +2.67] | includes 0 |
| last 4d | +2.58 pp | [-0.73, +7.60] | includes 0 |

**Does not survive the split.**

---

## 1d. OFFER SIZE, absolute contracts at the level -- B (model-certain)

_distribution: 7,328 of 7,328 rows carry it; p5 0 / p25 0.01 / median 19 / p75 102 / p95 1942.35_

**MDE first.** The smallest bucket holds 884 entries over 563 closes. Against a 0.49% collapse baseline that resolves 1.27% counting markets and 1.50% counting closes; on the loss column (0.23% baseline), 0.80% / 0.98%.

**ALL 9 DAYS**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 20 | 3,697 | 794 | 15 (0.41%) | [0.23, 0.67] | 8 | 0.22% | [0.09, 0.43] |
| 20-100 | 1,769 | 688 | 14 (0.79%) | [0.43, 1.32] | 7 | 0.40% | [0.16, 0.81] |
| 100-500 | 978 | 572 | 4 (0.41%) | [0.11, 1.04] | 1 | 0.10% | [0.00, 0.57] |
| >= 500 | 884 | 563 | 3 (0.34%) | [0.07, 0.99] | 1 | 0.11% | [0.00, 0.63] |

**Worst bucket `20-100` vs the rest, COLLAPSE rate, cluster bootstrap over CLOSES (2,000 draws):**

| sample | difference | 95% CI | verdict |
|---|---|---|---|
| all | +0.40 pp | [-0.03, +0.88] | includes 0 |
| first 5d | +0.40 pp | [-0.16, +1.13] | includes 0 |
| last 4d | +0.33 pp | [-0.23, +0.97] | includes 0 |

**Does not survive the split.**

---

## 2a. PRE-ENTRY JUMPINESS -- 1s index moves > 3 sigma in the last 120s -- B (model-certain)

_distribution: 7,328 of 7,328 rows carry it; p5 0 / p25 1 / median 2 / p75 3 / p95 5_

**MDE first.** The smallest bucket holds 1,043 entries over 455 closes. Against a 0.49% collapse baseline that resolves 1.20% counting markets and 1.63% counting closes; on the loss column (0.23% baseline), 0.75% / 1.08%.

**ALL 9 DAYS**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| 0 | 1,043 | 455 | 2 (0.19%) | [0.02, 0.69] | 0 | 0.00% | [0.00, 0.35] |
| 1 | 1,601 | 664 | 5 (0.31%) | [0.10, 0.73] | 4 | 0.25% | [0.07, 0.64] |
| 2-3 | 3,065 | 775 | 19 (0.62%) | [0.37, 0.97] | 10 | 0.33% | [0.16, 0.60] |
| >= 4 | 1,619 | 608 | 10 (0.62%) | [0.30, 1.13] | 3 | 0.19% | [0.04, 0.54] |

**Worst bucket `2-3` vs the rest, COLLAPSE rate, cluster bootstrap over CLOSES (2,000 draws):**

| sample | difference | 95% CI | verdict |
|---|---|---|---|
| all | +0.22 pp | [-0.11, +0.58] | includes 0 |
| first 5d | -0.08 pp | [-0.45, +0.30] | includes 0 |
| last 4d | +0.54 pp | [+0.00, +1.17] | EXCLUDES 0 |

**Does not survive the split.**

---

## 2b. LARGEST 1s index move in the last 120s, in sigma units -- B (model-certain)

_distribution: 7,328 of 7,328 rows carry it; p5 2.33 / p25 3.59 / median 4.81 / p75 6.7 / p95 10.61_

**MDE first.** The smallest bucket holds 169 entries over 127 closes. Against a 0.49% collapse baseline that resolves 2.57% counting markets and 2.98% counting closes; on the loss column (0.23% baseline), 2.03% / 2.69%.

**ALL 9 DAYS**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 2 | 169 | 127 | 0 (0.00%) | [0.00, 2.16] | 0 | 0.00% | [0.00, 2.16] |
| 2-3 | 865 | 424 | 2 (0.23%) | [0.03, 0.83] | 0 | 0.00% | [0.00, 0.43] |
| 3-4 | 1,460 | 615 | 4 (0.27%) | [0.07, 0.70] | 2 | 0.14% | [0.02, 0.49] |
| 4-6 | 2,475 | 741 | 17 (0.69%) | [0.40, 1.10] | 11 | 0.44% | [0.22, 0.79] |
| >= 6 | 2,359 | 692 | 13 (0.55%) | [0.29, 0.94] | 4 | 0.17% | [0.05, 0.43] |

**Worst bucket `4-6` vs the rest, COLLAPSE rate, cluster bootstrap over CLOSES (2,000 draws):**

| sample | difference | 95% CI | verdict |
|---|---|---|---|
| all | +0.30 pp | [-0.08, +0.72] | includes 0 |
| first 5d | +0.15 pp | [-0.25, +0.59] | includes 0 |
| last 4d | +0.46 pp | [-0.11, +1.17] | includes 0 |

**Does not survive the split.**

---

## 3. MARGIN TO THE STRIKE at entry, in sigma units -- B (model-certain)

_distribution: 7,328 of 7,328 rows carry it; p5 2.751 / p25 7.034 / median 7.034 / p75 7.034 / p95 7.034_

**MDE first.** The smallest bucket holds 262 entries over 217 closes. Against a 0.49% collapse baseline that resolves 2.08% counting markets and 2.27% counting closes; on the loss column (0.23% baseline), 1.43% / 1.59%.

**ALL 9 DAYS**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| 2.58-3 | 606 | 383 | 23 (3.80%) | [2.42, 5.64] | 8 | 1.32% | [0.57, 2.58] |
| 3-4 | 383 | 297 | 8 (2.09%) | [0.91, 4.07] | 5 | 1.31% | [0.43, 3.02] |
| 4-5 | 262 | 220 | 0 (0.00%) | [0.00, 1.40] | 0 | 0.00% | [0.00, 1.40] |
| 5-6 | 262 | 217 | 0 (0.00%) | [0.00, 1.40] | 0 | 0.00% | [0.00, 1.40] |
| >= 6 | 5,815 | 800 | 5 (0.09%) | [0.03, 0.20] | 4 | 0.07% | [0.02, 0.18] |

**Worst bucket `2.58-3` vs the rest, COLLAPSE rate, cluster bootstrap over CLOSES (2,000 draws):**

| sample | difference | 95% CI | verdict |
|---|---|---|---|
| all | +3.60 pp | [+2.09, +5.29] | EXCLUDES 0 |
| first 5d | +2.83 pp | [+0.99, +4.90] | EXCLUDES 0 |
| last 4d | +4.37 pp | [+2.04, +7.12] | EXCLUDES 0 |

**SURVIVES THE SPLIT.**

---

## 4a. TAU AT ENTRY (control) -- B (model-certain)

_distribution: 7,328 of 7,328 rows carry it; p5 17 / p25 30 / median 30 / p75 30 / p95 30_

**MDE first.** The smallest bucket holds 206 entries over 87 closes. Against a 0.49% collapse baseline that resolves 2.33% counting markets and 3.91% counting closes; on the loss column (0.23% baseline), 1.66% / 3.91%.

**ALL 9 DAYS**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| 3-9s | 206 | 87 | 3 (1.46%) | [0.30, 4.20] | 0 | 0.00% | [0.00, 1.77] |
| 10-19s | 229 | 185 | 6 (2.62%) | [0.97, 5.62] | 5 | 2.18% | [0.71, 5.02] |
| 20-30s | 6,893 | 801 | 27 (0.39%) | [0.26, 0.57] | 12 | 0.17% | [0.09, 0.30] |

**Worst bucket `10-19s` vs the rest, COLLAPSE rate, cluster bootstrap over CLOSES (2,000 draws):**

| sample | difference | 95% CI | verdict |
|---|---|---|---|
| all | +2.20 pp | [+0.40, +4.52] | EXCLUDES 0 |
| first 5d | +1.43 pp | [-0.37, +3.94] | includes 0 |
| last 4d | +2.94 pp | [-0.01, +6.63] | includes 0 |

**Does not survive the split.**

---

## 4b. PRICE PAID (control) -- B (model-certain)

_distribution: 5,520 of 7,328 rows carry it; p5 0.37 / p25 0.51 / median 0.61 / p75 0.87 / p95 0.999_

**MDE first.** The smallest bucket holds 94 entries over 85 closes. Against a 0.49% collapse baseline that resolves 3.62% counting markets and 4.00% counting closes; on the loss column (0.23% baseline), 3.62% / 4.00%.

**ALL 9 DAYS**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 94c | 4,255 | 765 | 20 (0.47%) | [0.29, 0.73] | 9 | 0.21% | [0.10, 0.40] |
| 94-97c | 128 | 111 | 6 (4.69%) | [1.74, 9.92] | 1 | 0.78% | [0.02, 4.28] |
| 97-98c | 94 | 85 | 2 (2.13%) | [0.26, 7.48] | 1 | 1.06% | [0.03, 5.79] |
| >= 98c | 1,043 | 417 | 5 (0.48%) | [0.16, 1.12] | 4 | 0.38% | [0.10, 0.98] |
| n/a | 1,808 | 556 | 3 (0.17%) | [0.03, 0.48] | 2 | 0.11% | [0.01, 0.40] |

**Worst bucket `94-97c` vs the rest, COLLAPSE rate, cluster bootstrap over CLOSES (2,000 draws):**

| sample | difference | 95% CI | verdict |
|---|---|---|---|
| all | +4.19 pp | [+1.03, +8.05] | EXCLUDES 0 |
| first 5d | +4.10 pp | [+0.56, +9.04] | EXCLUDES 0 |
| last 4d | +4.62 pp | [-0.72, +12.77] | includes 0 |

**Does not survive the split.**

---

## 4c. DISCOUNT BELOW FAIR at entry, cents (the LIVE guard cuts at 15c) -- B (model-certain)

_distribution: 5,520 of 7,328 rows carry it; p5 0.1 / p25 12.98 / median 38.82 / p75 49 / p95 63_

**MDE first.** The smallest bucket holds 71 entries over 61 closes. Against a 0.49% collapse baseline that resolves 4.78% counting markets and 5.55% counting closes; on the loss column (0.23% baseline), 4.78% / 5.55%.

**ALL 9 DAYS**

| bucket | entries | closes | collapse | 95% CP | losses | loss rate | 95% CP |
|---|---|---|---|---|---|---|---|
| < 1c | 906 | 399 | 5 (0.55%) | [0.18, 1.28] | 4 | 0.44% | [0.12, 1.13] |
| 1-2c | 151 | 122 | 1 (0.66%) | [0.02, 3.63] | 0 | 0.00% | [0.00, 2.41] |
| 2-5c | 171 | 145 | 4 (2.34%) | [0.64, 5.88] | 2 | 1.17% | [0.14, 4.16] |
| 5-10c | 111 | 92 | 4 (3.60%) | [0.99, 8.97] | 1 | 0.90% | [0.02, 4.92] |
| 10-15c | 71 | 61 | 1 (1.41%) | [0.04, 7.60] | 0 | 0.00% | [0.00, 5.06] |
| >= 15c (guard refuses) | 4,110 | 756 | 18 (0.44%) | [0.26, 0.69] | 8 | 0.19% | [0.08, 0.38] |
| n/a | 1,808 | 556 | 3 (0.17%) | [0.03, 0.48] | 2 | 0.11% | [0.01, 0.40] |

**Worst bucket `5-10c` vs the rest, COLLAPSE rate, cluster bootstrap over CLOSES (2,000 draws):**

| sample | difference | 95% CI | verdict |
|---|---|---|---|
| all | +3.07 pp | [+0.19, +6.76] | EXCLUDES 0 |
| first 5d | +3.46 pp | [-0.39, +8.14] | includes 0 |
| last 4d | +2.36 pp | [-0.94, +9.06] | includes 0 |

**Does not survive the split.**


---

## The per-close arithmetic

Money is only defined where we would actually have traded, so this is population A. Refusing a bucket changes two things -- the losses avoided and the wins given up -- and this project has twice been fooled by a per-contract table that reversed per close ("be more patient for a bigger discount", 2026-09-11; "stop paying above 94c", 2026-09-12). P&L is scaled linearly to size 20 and is a CEILING: the replay always wins the race.

| feature / bucket refused | entries | closes | losses in it | $/close now | $/close if refused | change |
|---|---|---|---|---|---|---|
| 1a. OFFER AGE `0.1-0.5s` | 79 | 274 | 2 | $1.321 | $1.221 | -0.100 |
| 3. MARGIN TO THE STRIKE at entry, in sigma units `2.58-3` | 169 | 274 | 1 | $1.321 | $0.880 | -0.441 |

---

## Verdict

**Nothing survives on the population that matters.** On the 409 entries the live gate would have taken over 9 days there are 3 losses and 16 post-entry collapses, and no entry-time feature separates them in both halves of the tape. That is a null with a stated MDE, not a discovery of absence: the smallest effect population A could have resolved on its loss column is roughly 2.2% against a 0.73% base, so anything short of a feature that triples the loss rate was never findable here.

On the 30x-larger model-certain population, 2 feature(s) do survive the split: `1a. OFFER AGE` bucket `0.1-0.5s`, `3. MARGIN TO THE STRIKE at entry, in sigma units` bucket `2.58-3`. That population is NOT what we trade -- it includes every moment nobody was offering -- so it cannot license a live rule on its own. It is the right place to look next, and the honest reading is that the effect is real in the model's behaviour and unproven at the prices we can actually get.


### What would have to be true for anything above to be an artefact

1. **The collapse flag could be the feed, not the market.** Checked above at the alarm second.
2. **The book could be wrong.** The replay is delta-driven with snapshots applied at their real `_rx_ms`; `pinsim.load_hour` stamps every snapshot 0, which this file does not use. A level seeded by a snapshot has an age that is only a lower bound and is flagged.
3. **Clustering could manufacture the separation.** Every headline interval is a cluster bootstrap over CLOSES; the self-test contains a world where 240 markets carry 20 facts and per-market intervals separate while the clustered one does not.
4. **The split could be luck.** Nothing is called a survivor unless the interval excludes zero in BOTH halves, holdout included.

