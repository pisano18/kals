# RESULTS_calib -- is the model's uncertainty the right width?

*`research/pincalib.py`, 2026-09-13T09:34Z. 109122 z-scores over 1672 closes, 2026-08-25T04:15Z .. 2026-09-13T09:30Z (19.2 days). NO BACKTEST, NO ORDER BOOK, NO P&L -- the 1-per-second settlement index and nothing else.*

`z = (settle - mu) / sd` where `mu` is the model's own forecast and `sd` its own claimed uncertainty. **If the model is right, z is standard normal.** Nothing here is a loss rate of ours and nothing here may be quoted as one (rule 5); this is a statement about the index and the model.

## 1. The whole tape

| | value | a correct model |
|---|---|---|
| mean z | -0.014 | 0 |
| **sd of z** | **1.151** | **1** |
| kurtosis | 132.39 | 3 |

**sd(z) = 1.151 means the model's own uncertainty is 15% too NARROW.** It is not that the forecast is biased -- mean z is -0.014 -- it is that the model does not know how wrong it can be.

## 2. What it promises at each confidence, against what happens

*Corrected 2026-09-13: these were computed on `abs(z)`, the two-sided tail, against a one-sided promise, and so were roughly 2x too large. We lose only when the settle comes in BELOW the forecast. The numbers below are the signed lower tail and are the right ones.*

| the model says it is this sure | z | promised failure | realised | off by | n |
|---|---|---|---|---|---|
| 0.9900 | 2.33 | 1.0000% | 2.0995% | 2.1x | 109122 |
| 0.9950 | 2.58 | 0.5000% | 1.6734% | 3.3x | 109122 |
| 0.9985 | 2.97 | 0.1500% | 1.2069% | 8.0x | 109122 |
| 0.9990 | 3.09 | 0.1000% | 1.0942% | 10.9x | 109122 |
| 0.9999 | 3.72 | 0.0100% | 0.6965% | 69.6x | 109122 |

## 3. Did it change? First 70% of closes against the last 30%

| | closes | sd of z | kurtosis | realised failure at 99.85% |
|---|---|---|---|---|
| early | 1170 | 1.114 | 150.55 | 1.2225% |
| late | 502 | 1.230 | 101.46 | 1.1711% |

## 4. By day

| day | closes | sd of z | kurtosis | worst z |
|---|---|---|---|---|
| 2026-08-25 | 77 | 1.102 | 9.36 | 7.7 |
| 2026-08-26 | 23 | 0.834 | 11.06 | 7.7 |
| 2026-08-27 | 95 | 0.965 | 15.08 | 12.3 |
| 2026-08-28 | 95 | 0.995 | 22.23 | 13.1 |
| 2026-08-29 | 96 | 1.205 | 21.68 | 15.7 |
| 2026-08-30 | 95 | 1.363 | 19.56 | 16.6 |
| 2026-08-31 | 96 | 0.945 | 13.66 | 8.3 |
| 2026-09-01 | 95 | 1.091 | 31.52 | 18.6 |
| 2026-09-02 | 63 | 1.006 | 8.82 | 7.9 |
| 2026-09-03 | 70 | 0.937 | 9.71 | 9.5 |
| 2026-09-04 | 96 | 1.042 | 21.22 | 12.4 |
| 2026-09-05 | 96 | 1.579 | 399.17 | 61.1 |
| 2026-09-06 | 96 | 1.011 | 26.49 | 15.1 |
| 2026-09-07 | 96 | 1.073 | 37.38 | 18.2 |
| 2026-09-08 | 96 | 0.934 | 12.90 | 7.9 |
| 2026-09-09 | 63 | 0.995 | 13.82 | 10.6 |
| 2026-09-10 | 95 | 1.428 | 93.70 | 34.5 |
| 2026-09-11 | 95 | 1.250 | 158.91 | 35.9 |
| 2026-09-12 | 95 | 1.229 | 90.88 | 28.1 |
| 2026-09-13 | 39 | 1.491 | 85.46 | 25.8 |

## 5. HOW FAR OUT THE MODEL ACTUALLY HAS TO BE -- the deployable table

Read this as: to be as sure as the model claims it is, the settlement has to sit this many of the model's own sds away from the strike. The Gaussian column is what it assumes; the empirical column is what the index has actually delivered over 1672 closes.

| the model says | Gaussian z | ACTUAL z needed | early | late | understated by |
|---|---|---|---|---|---|
| 0.9900 sure | 2.33 | **3.21** | 3.21 | 3.18 | 1.38x |
| 0.9950 sure | 2.58 | **4.33** | 4.36 | 4.25 | 1.68x |
| 0.9985 sure | 2.97 | **6.83** | 6.89 | 6.57 | 2.30x |
| 0.9990 sure | 3.09 | **7.59** | 7.86 | 7.30 | 2.46x |
| 0.9999 sure | 3.72 | **15.15** | 15.15 | 13.75 | 4.07x |

**No Student-t fits this.** The lower tail beyond the Gaussian 99.85 point is fatter than a t with df=3.5 predicts even after that t is scaled to unit variance, and df=10 is not close. The honest replacement for `Phi()` is THIS TABLE, measured, not a closed form -- and `results/calib_table.json` is that table, emitted by `--emit-table`.

**CAVEAT ON THE FAR ROWS.** The z-scores are clustered: 109122 of them sit on only 1672 closes, six taus share each market and twelve coins share each close. The 99% and 99.5% rows rest on thousands of independent closes and are solid; the 99.99% row rests on a handful of events and its z is an order-of-magnitude statement, not a number to gate on.

## 6. By seconds left

| tau | n | sd of z | kurtosis |
|---|---|---|---|
| 5 s | 18187 | 1.217 | 397.42 |
| 10 s | 18187 | 1.052 | 37.65 |
| 15 s | 18187 | 1.133 | 62.78 |
| 20 s | 18187 | 1.139 | 51.36 |
| 25 s | 18187 | 1.141 | 66.07 |
| 30 s | 18187 | 1.214 | 80.22 |

