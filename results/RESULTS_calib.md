# RESULTS_calib -- is the model's uncertainty the right width?

*`research/pincalib.py`, 2026-09-13T09:07Z. 108990 z-scores over 1670 closes, 2026-08-25T04:15Z .. 2026-09-13T09:00Z (19.2 days). NO BACKTEST, NO ORDER BOOK, NO P&L -- the 1-per-second settlement index and nothing else.*

`z = (settle - mu) / sd` where `mu` is the model's own forecast and `sd` its own claimed uncertainty. **If the model is right, z is standard normal.** Nothing here is a loss rate of ours and nothing here may be quoted as one (rule 5); this is a statement about the index and the model.

## 1. The whole tape

| | value | a correct model |
|---|---|---|
| mean z | -0.013 | 0 |
| **sd of z** | **1.151** | **1** |
| kurtosis | 132.31 | 3 |

**sd(z) = 1.151 means the model's own uncertainty is 15% too NARROW.** It is not that the forecast is biased -- mean z is -0.013 -- it is that the model does not know how wrong it can be.

## 2. What it promises at each confidence, against what happens

| the model says it is this sure | z | promised failure | realised | off by | n |
|---|---|---|---|---|---|
| 0.9900 | 2.33 | 1.0000% | 3.8517% | 3.9x | 108990 |
| 0.9950 | 2.58 | 0.5000% | 3.0773% | 6.2x | 108990 |
| 0.9985 | 2.97 | 0.1500% | 2.2231% | 14.8x | 108990 |
| 0.9990 | 3.09 | 0.1000% | 2.0195% | 20.2x | 108990 |
| 0.9999 | 3.72 | 0.0100% | 1.2781% | 127.8x | 108990 |

## 3. Did it change? First 70% of closes against the last 30%

| | closes | sd of z | kurtosis | realised failure at 99.85% |
|---|---|---|---|---|
| early | 1169 | 1.115 | 150.55 | 2.2009% |
| late | 501 | 1.231 | 101.25 | 2.2742% |

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
| 2026-09-13 | 37 | 1.525 | 82.01 | 25.8 |

## 5. HOW FAR OUT THE MODEL ACTUALLY HAS TO BE -- the deployable table

Read this as: to be as sure as the model claims it is, the settlement has to sit this many of the model's own sds away from the strike. The Gaussian column is what it assumes; the empirical column is what the index has actually delivered over 1670 closes.

| the model says | Gaussian z | ACTUAL z needed | early | late | understated by |
|---|---|---|---|---|---|
| 0.9900 sure | 2.33 | **3.10** | 3.09 | 3.13 | 1.33x |
| 0.9950 sure | 2.58 | **4.17** | 4.10 | 4.40 | 1.62x |
| 0.9985 sure | 2.97 | **6.83** | 6.29 | 7.83 | 2.30x |
| 0.9990 sure | 3.09 | **7.83** | 7.30 | 9.32 | 2.54x |
| 0.9999 sure | 3.72 | **17.56** | 13.12 | 18.91 | 4.72x |

**No Student-t fits this.** At the Gaussian 99.85 per-cent point the index delivers a 2.22 per-cent tail; the fattest sensible t (df=3.5) predicts 1.43 and df=10 predicts 0.78. It is fatter than any of them, so the honest replacement for `Phi()` is THIS TABLE, measured, not a closed form.

**CAVEAT ON THE FAR ROWS.** The z-scores are clustered: 108990 of them sit on only 1670 closes, six taus share each market and twelve coins share each close. The 99% and 99.5% rows rest on thousands of independent closes and are solid; the 99.99% row rests on a handful of events and its z is an order-of-magnitude statement, not a number to gate on.

## 6. By seconds left

| tau | n | sd of z | kurtosis |
|---|---|---|---|
| 5 s | 18165 | 1.217 | 397.35 |
| 10 s | 18165 | 1.052 | 37.64 |
| 15 s | 18165 | 1.133 | 62.73 |
| 20 s | 18165 | 1.139 | 51.31 |
| 25 s | 18165 | 1.142 | 66.03 |
| 30 s | 18165 | 1.215 | 80.15 |

