# RESULTS_exit -- can we SELL the winner before it settles?

Generated 2026-09-13T04:34Z by `research/pinexit.py`.

**Window:** 216 book hours, 2026-09-03T10Z -> 2026-09-12T17Z, 426 traded closes out of 837 closes in the window, **549 positions** (12 of them eventually lost).
Companion population (model called it near-certain, conf >= 0.97, offer or not): **7,548 markets**, 30 of which the model's own side eventually lost.

**CEILINGS.** A bid reconstructed from the opposite side's ask is what we could sell into ONLY IF WE WIN THE RACE FOR IT -- live we fill ~70% of the attempts we make, and every exit-fill number below assumes we win every race. A sale is a TAKER trade, so `pinrun.billed_fee` is charged on the exit leg at the exit price; there is no maker-fee-free version of this without resting an ask, which is a different question and is not tested here. Per CLAUDE.md (2026-09-10 amendment, rule 5) **no loss rate on this page is OUR live loss rate** -- this is the replay's population, not ours.

## 1. THE DECISIVE TABLE -- does the bid survive on the LOSERS?

**MDE, stated before the estimate.** 537 winners and **12 losers**. Against a winner rate of 92.0%, the smallest drop in the losers' rate detectable at 80% power / 5% two-sided is **41.7 percentage points**. Anything smaller than that is NO POWER, not NO EFFECT, and this page must not be read as ruling it out.

`have` = a bid existed on our side with size > 0 at that tau; `med` and `p10` are that bid in cents; `size` is the contracts resting at it. Positions opened later than a given tau are simply absent from that row (`n` says how many were open).

### POSITIONS the gate opened

| tau | group | n pos | closes | have a bid | 95% CI | med bid | p10 bid | med size | med belief |
|---|---|---|---|---|---|---|---|---|---|
| 15 | WON | 430 | 346 | 100.0% | [99.1, 100.0] | 99.2c | 94.0c | 82 | 100.00% |
| 15 | LOST | 12 | 11 | 75.0% | [42.8, 94.5] | 23.0c | 7.2c | 60 | 3.18% |
| 10 | WON | 487 | 388 | 100.0% | [99.2, 100.0] | 99.4c | 94.8c | 173 | 100.00% |
| 10 | LOST | 12 | 11 | 75.0% | [42.8, 94.5] | 5.9c | 1.9c | 64 | 0.00% |
| 8 | WON | 502 | 398 | 100.0% | [99.3, 100.0] | 99.5c | 95.0c | 191 | 100.00% |
| 8 | LOST | 12 | 11 | 66.7% | [34.9, 90.1] | 2.6c | 0.3c | 113 | 0.00% |
| 5 | WON | 522 | 409 | 100.0% | [99.3, 100.0] | 99.8c | 96.9c | 347 | 100.00% |
| 5 | LOST | 12 | 11 | 58.3% | [27.7, 84.8] | 1.0c | 0.3c | 130 | 0.00% |
| 3 | WON | 536 | 419 | 100.0% | [99.3, 100.0] | 99.9c | 97.5c | 1350 | 100.00% |
| 3 | LOST | 12 | 11 | 50.0% | [21.1, 78.9] | 0.5c | 0.2c | 90 | 0.00% |

### COMPANION: every model-certain market

| tau | group | n pos | closes | have a bid | 95% CI | med bid | p10 bid | med size | med belief |
|---|---|---|---|---|---|---|---|---|---|
| 15 | WON | 7,364 | 836 | 100.0% | [99.9, 100.0] | 99.9c | 99.5c | 3619 | 100.00% |
| 15 | LOST | 26 | 20 | 80.8% | [60.6, 93.4] | 11.0c | 5.0c | 100 | 2.05% |
| 10 | WON | 7,429 | 836 | 100.0% | [100.0, 100.0] | 99.9c | 99.6c | 4905 | 100.00% |
| 10 | LOST | 29 | 23 | 82.8% | [64.2, 94.2] | 5.5c | 1.7c | 68 | 0.00% |
| 8 | WON | 7,435 | 834 | 100.0% | [100.0, 100.0] | 99.9c | 99.7c | 5410 | 100.00% |
| 8 | LOST | 29 | 23 | 75.9% | [56.5, 89.7] | 3.1c | 0.1c | 113 | 0.00% |
| 5 | WON | 7,489 | 836 | 100.0% | [100.0, 100.0] | 99.9c | 99.8c | 7347 | 100.00% |
| 5 | LOST | 30 | 24 | 60.0% | [40.6, 77.3] | 2.6c | 0.3c | 123 | 0.00% |
| 3 | WON | 7,464 | 833 | 100.0% | [100.0, 100.0] | 99.9c | 99.9c | 8197 | 100.00% |
| 3 | LOST | 30 | 24 | 53.3% | [34.3, 71.7] | 2.3c | 0.2c | 80 | 0.00% |

## 2. ADVERSE-SELECTION CONTROL -- exit fill rate, losers vs winners

The test `results/RESULTS_maker.md` ran on the resting bid, in its own units. There a bid filled on **100% of eventual losers and 29% of winners** and the idea died. Here the question is the mirror image: an exit that fills on the winners and not the losers is worse than holding.

| exit tau | floor | winners exit | 95% CI | losers exit | 95% CI | MDE (pp) |
|---|---|---|---|---|---|---|
| 15 | 0.985 | 500/537 = 93.1% | [90.6, 95.1] | 2/12 = 16.7% | [2.1, 48.4] | 34.3 |
| 15 | 0.990 | 497/537 = 92.6% | [90.0, 94.6] | 2/12 = 16.7% | [2.1, 48.4] | 42.2 |
| 15 | 0.995 | 458/537 = 85.3% | [82.0, 88.2] | 1/12 = 8.3% | [0.2, 38.5] | 43.1 |
| 10 | 0.985 | 497/537 = 92.6% | [90.0, 94.6] | 0/12 = 0.0% | [0.0, 26.5] | 42.2 |
| 10 | 0.990 | 494/537 = 92.0% | [89.4, 94.1] | 0/12 = 0.0% | [0.0, 26.5] | 41.7 |
| 10 | 0.995 | 456/537 = 84.9% | [81.6, 87.8] | 0/12 = 0.0% | [0.0, 26.5] | 42.7 |
| 8 | 0.985 | 497/537 = 92.6% | [90.0, 94.6] | 0/12 = 0.0% | [0.0, 26.5] | 42.2 |
| 8 | 0.990 | 493/537 = 91.8% | [89.2, 94.0] | 0/12 = 0.0% | [0.0, 26.5] | 41.5 |
| 8 | 0.995 | 450/537 = 83.8% | [80.4, 86.8] | 0/12 = 0.0% | [0.0, 26.5] | 41.6 |
| 5 | 0.985 | 494/537 = 92.0% | [89.4, 94.1] | 0/12 = 0.0% | [0.0, 26.5] | 41.7 |
| 5 | 0.990 | 489/537 = 91.1% | [88.3, 93.3] | 0/12 = 0.0% | [0.0, 26.5] | 40.7 |
| 5 | 0.995 | 429/537 = 79.9% | [76.2, 83.2] | 0/12 = 0.0% | [0.0, 26.5] | 45.5 |
| 3 | 0.985 | 479/537 = 89.2% | [86.3, 91.7] | 0/12 = 0.0% | [0.0, 26.5] | 38.9 |
| 3 | 0.990 | 472/537 = 87.9% | [84.8, 90.5] | 0/12 = 0.0% | [0.0, 26.5] | 45.7 |
| 3 | 0.995 | 401/537 = 74.7% | [70.8, 78.3] | 0/12 = 0.0% | [0.0, 26.5] | 47.7 |

### 2b. The same control on the COMPANION population

The positions the gate opens are few and their losers are fewer, so the table above can only ever refute a very large asymmetry. This is the backward-looking companion CLAUDE.md requires: every market the model called near-certain inside the entry window, whether or not an offer existed for us to buy. Same book, same side, same question, and **an order of magnitude more losers** -- which is the point, because losers are what the decisive table is short of. It cannot be priced (those markets have no entry price), so it reports the FILL RATE only, from the same `cap` summary the position table is cross-checked against in the self-test. The two strata are reported separately and never pooled: the first is the live gate exactly, the second is the 0.97-0.995 band, which is where the flips live.

| exit tau | floor | winners exit | 95% CI | losers exit | 95% CI | MDE (pp) |
|---|---|---|---|---|---|---|
**reached the LIVE gate (conf >= 0.995)** -- 7,534 markets, 836 closes, 18 of which the model's side eventually LOST.

| exit tau | floor | winners exit | 95% CI | losers exit | 95% CI | MDE (pp) |
|---|---|---|---|---|---|---|
| 15 | 0.985 | 7,430/7,516 = 98.9% | [98.6, 99.1] | 3/18 = 16.7% | [3.6, 41.4] | 21.2 |
| 15 | 0.990 | 7,420/7,516 = 98.7% | [98.4, 99.0] | 3/18 = 16.7% | [3.6, 41.4] | 21.0 |
| 15 | 0.995 | 7,335/7,516 = 97.6% | [97.2, 97.9] | 2/18 = 11.1% | [1.4, 34.7] | 19.9 |
| 10 | 0.985 | 7,420/7,516 = 98.7% | [98.4, 99.0] | 0/18 = 0.0% | [0.0, 18.5] | 21.0 |
| 10 | 0.990 | 7,408/7,516 = 98.6% | [98.3, 98.8] | 0/18 = 0.0% | [0.0, 18.5] | 20.9 |
| 10 | 0.995 | 7,319/7,516 = 97.4% | [97.0, 97.7] | 0/18 = 0.0% | [0.0, 18.5] | 19.7 |
| 8 | 0.985 | 7,409/7,516 = 98.6% | [98.3, 98.8] | 0/18 = 0.0% | [0.0, 18.5] | 20.9 |
| 8 | 0.990 | 7,396/7,516 = 98.4% | [98.1, 98.7] | 0/18 = 0.0% | [0.0, 18.5] | 20.7 |
| 8 | 0.995 | 7,296/7,516 = 97.1% | [96.7, 97.4] | 0/18 = 0.0% | [0.0, 18.5] | 19.4 |
| 5 | 0.985 | 7,390/7,516 = 98.3% | [98.0, 98.6] | 0/18 = 0.0% | [0.0, 18.5] | 20.6 |
| 5 | 0.990 | 7,379/7,516 = 98.2% | [97.8, 98.5] | 0/18 = 0.0% | [0.0, 18.5] | 20.5 |
| 5 | 0.995 | 7,257/7,516 = 96.6% | [96.1, 97.0] | 0/18 = 0.0% | [0.0, 18.5] | 25.1 |
| 3 | 0.985 | 7,309/7,516 = 97.2% | [96.9, 97.6] | 0/18 = 0.0% | [0.0, 18.5] | 19.5 |
| 3 | 0.990 | 7,295/7,516 = 97.1% | [96.7, 97.4] | 0/18 = 0.0% | [0.0, 18.5] | 19.4 |
| 3 | 0.995 | 7,163/7,516 = 95.3% | [94.8, 95.8] | 0/18 = 0.0% | [0.0, 18.5] | 23.8 |

**near-certain only (0.97 <= conf < 0.995)** -- 14 markets, 14 closes, 12 of which the model's side eventually LOST.

| exit tau | floor | winners exit | 95% CI | losers exit | 95% CI | MDE (pp) |
|---|---|---|---|---|---|---|
| 15 | 0.985 | 0/2 = 0.0% | [0.0, 84.2] | 0/12 = 0.0% | [0.0, 26.5] | -- |
| 15 | 0.990 | 0/2 = 0.0% | [0.0, 84.2] | 0/12 = 0.0% | [0.0, 26.5] | -- |
| 15 | 0.995 | 0/2 = 0.0% | [0.0, 84.2] | 0/12 = 0.0% | [0.0, 26.5] | -- |
| 10 | 0.985 | 0/2 = 0.0% | [0.0, 84.2] | 0/12 = 0.0% | [0.0, 26.5] | -- |
| 10 | 0.990 | 0/2 = 0.0% | [0.0, 84.2] | 0/12 = 0.0% | [0.0, 26.5] | -- |
| 10 | 0.995 | 0/2 = 0.0% | [0.0, 84.2] | 0/12 = 0.0% | [0.0, 26.5] | -- |
| 8 | 0.985 | 0/2 = 0.0% | [0.0, 84.2] | 0/12 = 0.0% | [0.0, 26.5] | -- |
| 8 | 0.990 | 0/2 = 0.0% | [0.0, 84.2] | 0/12 = 0.0% | [0.0, 26.5] | -- |
| 8 | 0.995 | 0/2 = 0.0% | [0.0, 84.2] | 0/12 = 0.0% | [0.0, 26.5] | -- |
| 5 | 0.985 | 0/2 = 0.0% | [0.0, 84.2] | 0/12 = 0.0% | [0.0, 26.5] | -- |
| 5 | 0.990 | 0/2 = 0.0% | [0.0, 84.2] | 0/12 = 0.0% | [0.0, 26.5] | -- |
| 5 | 0.995 | 0/2 = 0.0% | [0.0, 84.2] | 0/12 = 0.0% | [0.0, 26.5] | -- |
| 3 | 0.985 | 0/2 = 0.0% | [0.0, 84.2] | 0/12 = 0.0% | [0.0, 26.5] | -- |
| 3 | 0.990 | 0/2 = 0.0% | [0.0, 84.2] | 0/12 = 0.0% | [0.0, 26.5] | -- |
| 3 | 0.995 | 0/2 = 0.0% | [0.0, 84.2] | 0/12 = 0.0% | [0.0, 26.5] | -- |

## 3. PRICE THE RULE -- per close, size 20

Denominator is **every close in the window (837)**, so a close we trade nothing on counts as zero. `hold` is the same population held to settlement, which is what `pin` does today. Positions that fail to exit keep their original outcome.

| exit tau | floor | full exits | partial | hold $ | exit $ | delta $ | hold $/close | exit $/close | med exit bid |
|---|---|---|---|---|---|---|---|---|---|
| 15 | 0.985 | 353/549 = 64.3% | 149 | +191.63 | +159.68 | **-31.95** | +0.2289 | +0.1908 | 99.1c |
| 15 | 0.990 | 334/549 = 60.8% | 165 | +191.63 | +153.16 | **-38.47** | +0.2289 | +0.1830 | 99.2c |
| 15 | 0.995 | 352/549 = 64.1% | 107 | +191.63 | +167.25 | **-24.38** | +0.2289 | +0.1998 | 99.6c |
| 10 | 0.985 | 385/549 = 70.1% | 112 | +191.63 | +140.69 | **-50.94** | +0.2289 | +0.1681 | 99.4c |
| 10 | 0.990 | 376/549 = 68.5% | 118 | +191.63 | +148.69 | **-42.94** | +0.2289 | +0.1776 | 99.5c |
| 10 | 0.995 | 366/549 = 66.7% | 90 | +191.63 | +169.71 | **-21.92** | +0.2289 | +0.2028 | 99.8c |
| 8 | 0.985 | 390/549 = 71.0% | 107 | +191.63 | +144.37 | **-47.26** | +0.2289 | +0.1725 | 99.5c |
| 8 | 0.990 | 384/549 = 69.9% | 109 | +191.63 | +150.33 | **-41.30** | +0.2289 | +0.1796 | 99.5c |
| 8 | 0.995 | 362/549 = 65.9% | 88 | +191.63 | +170.77 | **-20.86** | +0.2289 | +0.2040 | 99.8c |
| 5 | 0.985 | 430/549 = 78.3% | 64 | +191.63 | +153.89 | **-37.74** | +0.2289 | +0.1839 | 99.7c |
| 5 | 0.990 | 427/549 = 77.8% | 62 | +191.63 | +157.20 | **-34.43** | +0.2289 | +0.1878 | 99.8c |
| 5 | 0.995 | 384/549 = 69.9% | 45 | +191.63 | +173.75 | **-17.88** | +0.2289 | +0.2076 | 99.9c |
| 3 | 0.985 | 427/549 = 77.8% | 52 | +191.63 | +161.48 | **-30.15** | +0.2289 | +0.1929 | 99.9c |
| 3 | 0.990 | 417/549 = 76.0% | 55 | +191.63 | +164.56 | **-27.06** | +0.2289 | +0.1966 | 99.9c |
| 3 | 0.995 | 369/549 = 67.2% | 32 | +191.63 | +177.09 | **-14.54** | +0.2289 | +0.2116 | 99.9c |

## 4. THE BREAK-EVEN LOSS RATE -- pricing this without a tape loss rate

Section 3's dollar columns are a function of how often the REPLAY's positions lost, and CLAUDE.md's 2026-09-10 rule 5 forbids reading that as how often WE lose (0.11% on the tape against 3.4% live, intervals that do not overlap). Read alone they would therefore flatter HOLDING for exactly the forbidden reason. So the loss rate is taken out of the comparison. Per contract, buying at `px` and selling at `b` with both legs taker, exiting a winner costs `(1-b) + fee` and exiting a loser gains `b - fee`; those sum to 1. The rule beats holding above

    p* = e_w*c_w / (e_w*c_w + e_l*g_l)

**Compare p-star against the LIVE loss rate, which comes from live fills only.** `optimistic` assumes the losers exit as often and as dear as the winners; `measured` uses the losers actually observed.

| exit tau | floor | e_w | e_l | med net exit (win) | p* optimistic | med net exit (lose) | p* measured |
|---|---|---|---|---|---|---|---|
| 15 | 0.985 | 65.4% (351/537) | 16.7% (2/12) | 99.14c | **0.86%** | 98.66c | **3.29%** |
| 15 | 0.990 | 62.0% (333/537) | 8.3% (1/12) | 99.25c | **0.75%** | 98.93c | **5.33%** |
| 15 | 0.995 | 65.5% (352/537) | 0.0% (0/12) | 99.57c | **0.43%** | -- | **100.00%** |
| 10 | 0.985 | 71.7% (385/537) | 0.0% (0/12) | 99.47c | **0.53%** | -- | **100.00%** |
| 10 | 0.990 | 70.0% (376/537) | 0.0% (0/12) | 99.57c | **0.43%** | -- | **100.00%** |
| 10 | 0.995 | 68.2% (366/537) | 0.0% (0/12) | 99.79c | **0.21%** | -- | **100.00%** |
| 8 | 0.985 | 72.6% (390/537) | 0.0% (0/12) | 99.57c | **0.43%** | -- | **100.00%** |
| 8 | 0.990 | 71.5% (384/537) | 0.0% (0/12) | 99.57c | **0.43%** | -- | **100.00%** |
| 8 | 0.995 | 67.4% (362/537) | 0.0% (0/12) | 99.79c | **0.21%** | -- | **100.00%** |
| 5 | 0.985 | 80.1% (430/537) | 0.0% (0/12) | 99.79c | **0.21%** | -- | **100.00%** |
| 5 | 0.990 | 79.5% (427/537) | 0.0% (0/12) | 99.79c | **0.21%** | -- | **100.00%** |
| 5 | 0.995 | 71.5% (384/537) | 0.0% (0/12) | 99.89c | **0.11%** | -- | **100.00%** |
| 3 | 0.985 | 79.5% (427/537) | 0.0% (0/12) | 99.89c | **0.11%** | -- | **100.00%** |
| 3 | 0.990 | 77.7% (417/537) | 0.0% (0/12) | 99.89c | **0.11%** | -- | **100.00%** |
| 3 | 0.995 | 68.7% (369/537) | 0.0% (0/12) | 99.89c | **0.11%** | -- | **100.00%** |

## 5. WHAT WOULD HAVE TO BE TRUE FOR THIS TO BE AN ARTEFACT

**(a) A STALE BOOK.** If the collector went quiet, the replayed book keeps showing the last bid it saw. A position going wrong is exactly when the real book would reprice, so a stale book manufactures surviving bids on losers -- the artefact that would fake this result. `results/RESULTS_tapegaps.md` measures 3.28% of seconds inside this tau band falling in a silent run of >= 10 s. So every headline is re-run with live's own freshness rail, `MAX_BOOK_AGE_MS = 2000`, applied to the exit moment as live applies it to the entry moment.

| exit tau | floor | full exits (no age gate) | full exits (age gate) | delta $ (no gate) | delta $ (age gate) |
|---|---|---|---|---|---|
| 15 | 0.985 | 353/549 | 353/549 | -31.95 | -31.95 |
| 15 | 0.990 | 334/549 | 334/549 | -38.47 | -38.47 |
| 15 | 0.995 | 352/549 | 352/549 | -24.38 | -24.38 |
| 10 | 0.985 | 385/549 | 385/549 | -50.94 | -50.94 |
| 10 | 0.990 | 376/549 | 376/549 | -42.94 | -42.94 |
| 10 | 0.995 | 366/549 | 366/549 | -21.92 | -21.92 |
| 8 | 0.985 | 390/549 | 390/549 | -47.26 | -47.26 |
| 8 | 0.990 | 384/549 | 384/549 | -41.30 | -41.30 |
| 8 | 0.995 | 362/549 | 362/549 | -20.86 | -20.86 |
| 5 | 0.985 | 430/549 | 430/549 | -37.74 | -37.74 |
| 5 | 0.990 | 427/549 | 427/549 | -34.43 | -34.43 |
| 5 | 0.995 | 384/549 | 384/549 | -17.88 | -17.88 |
| 3 | 0.985 | 427/549 | 427/549 | -30.15 | -30.15 |
| 3 | 0.990 | 417/549 | 417/549 | -27.06 | -27.06 |
| 3 | 0.995 | 369/549 | 369/549 | -14.54 | -14.54 |

Book age across every observation in the watch window: median 0 ms, p90 0 ms, p99 92 ms.

**(b) THE MODEL STILL BELIEVED AT THE EXIT.** If a losing position exits at 99c only because the model had not yet noticed it was losing, the bid is real but the rule is not selling a doomed position -- it is selling a position that looks fine, which is the same thing the winners are. The model's belief at the exit moment, at exit tau 10 / floor 0.99:

- winners that exited: median belief 100.000% (494 exits)
- losers that exited: median belief -- (0 exits)

**(c) THE BID IS OUR OWN RACE TO WIN.** Everything above assumes we reach the resting bid first. Live we win ~70% of the races we enter on the BUY side; there is no reason the sell side is easier, and a collapsing book is precisely where the race is hardest. Multiply every fill rate by roughly that factor before believing any dollar figure.

## 6. FIT / HOLDOUT -- first 70% of closes vs last 30%

Split at close 1789006500 (2026-09-10T02:15Z). Nothing here is a survivor unless the holdout agrees.

| slice | positions | closes | exit tau | floor | full exits | hold $ | exit $ | delta $ |
|---|---|---|---|---|---|---|---|---|
| fit (first 70%) | 386 | 298 | 15 | 0.985 | 247 = 64.0% | +176.00 | +129.90 | -46.10 |
| fit (first 70%) | 386 | 298 | 15 | 0.990 | 233 = 60.4% | +176.00 | +139.71 | -36.28 |
| fit (first 70%) | 386 | 298 | 15 | 0.995 | 241 = 62.4% | +176.00 | +156.99 | -19.01 |
| fit (first 70%) | 386 | 298 | 10 | 0.985 | 268 = 69.4% | +176.00 | +139.76 | -36.23 |
| fit (first 70%) | 386 | 298 | 10 | 0.990 | 261 = 67.6% | +176.00 | +145.56 | -30.44 |
| fit (first 70%) | 386 | 298 | 10 | 0.995 | 256 = 66.3% | +176.00 | +160.95 | -15.05 |
| fit (first 70%) | 386 | 298 | 8 | 0.985 | 277 = 71.8% | +176.00 | +141.57 | -34.43 |
| fit (first 70%) | 386 | 298 | 8 | 0.990 | 272 = 70.5% | +176.00 | +146.12 | -29.88 |
| fit (first 70%) | 386 | 298 | 8 | 0.995 | 250 = 64.8% | +176.00 | +161.93 | -14.07 |
| fit (first 70%) | 386 | 298 | 5 | 0.985 | 299 = 77.5% | +176.00 | +147.91 | -28.08 |
| fit (first 70%) | 386 | 298 | 5 | 0.990 | 296 = 76.7% | +176.00 | +150.62 | -25.38 |
| fit (first 70%) | 386 | 298 | 5 | 0.995 | 257 = 66.6% | +176.00 | +163.93 | -12.07 |
| fit (first 70%) | 386 | 298 | 3 | 0.985 | 292 = 75.6% | +176.00 | +154.62 | -21.37 |
| fit (first 70%) | 386 | 298 | 3 | 0.990 | 285 = 73.8% | +176.00 | +156.79 | -19.20 |
| fit (first 70%) | 386 | 298 | 3 | 0.995 | 252 = 65.3% | +176.00 | +165.78 | -10.22 |
| HOLDOUT (last 30%) | 163 | 128 | 15 | 0.985 | 106 = 65.0% | +15.63 | +29.78 | +14.15 |
| HOLDOUT (last 30%) | 163 | 128 | 15 | 0.990 | 101 = 62.0% | +15.63 | +13.45 | -2.18 |
| HOLDOUT (last 30%) | 163 | 128 | 15 | 0.995 | 111 = 68.1% | +15.63 | +10.26 | -5.37 |
| HOLDOUT (last 30%) | 163 | 128 | 10 | 0.985 | 117 = 71.8% | +15.63 | +0.93 | -14.70 |
| HOLDOUT (last 30%) | 163 | 128 | 10 | 0.990 | 115 = 70.6% | +15.63 | +3.13 | -12.51 |
| HOLDOUT (last 30%) | 163 | 128 | 10 | 0.995 | 110 = 67.5% | +15.63 | +8.77 | -6.87 |
| HOLDOUT (last 30%) | 163 | 128 | 8 | 0.985 | 113 = 69.3% | +15.63 | +2.81 | -12.83 |
| HOLDOUT (last 30%) | 163 | 128 | 8 | 0.990 | 112 = 68.7% | +15.63 | +4.21 | -11.42 |
| HOLDOUT (last 30%) | 163 | 128 | 8 | 0.995 | 112 = 68.7% | +15.63 | +8.84 | -6.80 |
| HOLDOUT (last 30%) | 163 | 128 | 5 | 0.985 | 131 = 80.4% | +15.63 | +5.98 | -9.65 |
| HOLDOUT (last 30%) | 163 | 128 | 5 | 0.990 | 131 = 80.4% | +15.63 | +6.59 | -9.04 |
| HOLDOUT (last 30%) | 163 | 128 | 5 | 0.995 | 127 = 77.9% | +15.63 | +9.82 | -5.81 |
| HOLDOUT (last 30%) | 163 | 128 | 3 | 0.985 | 135 = 82.8% | +15.63 | +6.86 | -8.78 |
| HOLDOUT (last 30%) | 163 | 128 | 3 | 0.990 | 132 = 81.0% | +15.63 | +7.77 | -7.86 |
| HOLDOUT (last 30%) | 163 | 128 | 3 | 0.995 | 117 = 71.8% | +15.63 | +11.31 | -4.32 |

