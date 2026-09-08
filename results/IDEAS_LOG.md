# Ideas log — every idea, what testing it got, what happened

**Purpose: nothing gets lost in fast conversation.** Every idea raised, by
either of us, with its evidence and current status. Update this whenever an
idea is raised, tested, deployed or killed.

Status key: **LIVE** · **TESTED-REJECTED** · **TESTED-PROMISING** (works but not
deployed, with the reason) · **PARTIAL** (tested but not conclusively) ·
**UNTESTED** · **DEAD** (structurally impossible)

---

## LIVE — deployed to real money

| # | idea | evidence | version |
|---|---|---|---|
| 1 | **Edge floor 0.5¢ → 0.3¢** | OOS: 389 closes / +2.76¢ / t=+5.6 / 1 flip in 359, vs 354 / +2.51¢ / t=+4.1 / 3 in 333 | v1 |
| 2 | **EV gate — price ceiling from the MEASURED flip rate** *(operator: "is it even worth doing trades above .99c")* | 5 of first 7 trades were negative-EV. Breakeven price = 1−f = 99.1¢. Profit/trade 1.41¢ → 3.42¢ | v2 |
| 3 | **Scale in as price improves** *(operator)* | 4.18¢ → 7.43¢ per close at cap 2; avg price paid FELL 95.53¢ → 94.60¢ | v3 |
| 4 | **Window 20s → 30s** | Model calibration by horizon: 0 flips in 5,219 moments under tau 30; 3.7× overconfident at 31–45; 10.9× at 46–60 | v4 |
| 5 | **Size 1 → 3 → 8** | Depth median 125 contracts at the touch; we were using ~2% | v5/v6 |

---

## MEASURED 2026-09-08 — the two biggest results of the day

### 26 | Size on CONFIDENCE — **TESTED-REJECTED, and it is backwards**

The operator's standing request was to size by how sure we are. Measured across
a panel of sizing rules on 593 eligible trades over 70 closes:

| the model's p_flip | mean price | worth per contract |
|---|---|---|
| below 1e-10 (most certain) | **97.51¢** | **1.41¢** |
| above 1e-3 (least certain) | 94.39¢ | **4.35¢** |

**Confidence and reward are INVERSELY related here.** "Buy more when confident"
is literally "buy more at 97–99¢", which is the expensive end. `CONF_PROP` is
the WORST rule in the panel (3.02¢/contract vs flat's 3.43¢) and gets
monotonically worse as its cap rises.

**What works instead is sizing on what the trade PAYS** — price or EV. That is
the same information with the model's opinion taken out of it. Best survivor:
`TIER_IMPROVE cap2` — first take is 2 contracts when the price is already below
93¢, `n = 1 + floor((0.95 − price)/0.02)`, cap unchanged. +15% per close at
identical max exposure and slightly LOWER abort probability. **Not deployed** —
it is +0.8¢/close measured on 70 closes with zero adverse events, which is a
candidate for pre-registration, not a reason to touch a working process.

### 27 | Is our volatility number any good? — **MEASURED, and it is the wrong SHAPE**

`volcheck.py`, 13.0M cells over 329 hour-files, 90.3% tape coverage. Verified
against the shipped dataset on 28,479 of 28,479 rows (worst relative difference
3.96e-10) and reproduces the settled flip on 28,479 of 28,479.

When the model says the move has standard deviation X, the realised standard
deviation is **1.18X** pooled — 1.105× at tau 3 rising monotonically to 1.262×
at tau 60. But the pooled RMS ratio is only **1.029**, so the *average level* is
nearly right and the gap is per-instance error.

**The distribution is not a gaussian of the wrong width. It is the wrong shape.**

| | realised | gaussian | ratio |
|---|---|---|---|
| median \|z\| (body) | 0.470 | 0.674 | **0.70×** — too NARROW |
| \|z\| > 2 | 7.02% | 4.55% | 1.5× |
| \|z\| > 3 | 2.52% | 0.270% | 9.3× |
| \|z\| > 4 | 1.114% | 0.0063% | **176×** |
| \|z\| > 6 | 0.329% | 2e-7% | 1.7 million× |

**Mechanism, visible in the raw tape: these indices are step functions.**
Fraction of consecutive one-second prints that are EXACTLY equal — SOL 70.5%,
NEAR 39.1%, XRP 17.7%, DOGE 17.6%, ETH 10.7%, BNB 8.4%, HYPE 3.8%, BRTI 0.6%,
ZEC 0.07%. A long flat stretch sets a tiny 300-second sigma, then one second
moves 20–25 sigma and the level persists.

**This independently explains the 0.90% flip rate.** The model implies ~0.06%;
reality is 15× worse. The tail measurement says exceedance at z>3 runs ~9×
gaussian. Two independent routes to the same order of magnitude. **The
protection is not the model — it is that we substitute the measured 0.90% for
the model's number in the EV gate.** That substitution is doing all the work.

**Also corrected here:** the flip-rate 95% upper bound. 1.80% was a Wald normal
approximation on 3 events. The exact one-sided Clopper-Pearson bound on 3 in
333 is **2.31%**, 28% higher. Every headroom figure in this repo now uses 2.31%.

### 28 | Price ceiling 98.8¢ → 96¢ — **TESTED-REJECTED after being wrongly declared live**

See `results/VERSIONS.md`. Committed to disk, never restarted, never traded.
Withdrawn because live prices (mean 97.61¢) are far dearer than the backtest
(93.86¢), so it would refuse 12 of 16 real signals rather than ~30%.

---

## TESTED-PROMISING — works, deliberately not deployed

| # | idea | result | why not deployed |
|---|---|---|---|
| 6 | **Rest at our price instead of racing** *(operator)* | +402¢ vs +292¢ = **+37%**, and no fee | **Zero losses in the sample**, so it cannot measure the one risk resting carries (being filled when wrong). Also needs post/cancel every second — the pattern that lost $24.14 on 2026-09-07. |

**Note:** my *first* test of this was rigged against it — it only filled when
the offer was already at our price, i.e. when we'd have taken it anyway.
Retested with real trade prints, it wins. Caught only because the operator
insisted dead ideas be re-checked.

---

## TESTED-REJECTED

| # | idea | why it failed |
|---|---|---|
| 7 | **Spot lead — predict the index from constituent exchanges** | No forward lead. Predicting index[t+k] from the replica beats persistence by **+0.03% on BTC**. Our replica's noise ($5.4) exceeds a one-second index move ($4.30). The 107 ms *arrival* advantage is real (100.00% of 1,111,809 seconds) but only tells us the present sooner. |
| 8 | **SCALE_ALL — buy every qualifying second** | Highest total but **worst per contract** (4.13¢, below the current rule). More size at worse prices. |
| 9 | **PATIENT — wait for a better price** | Skipping one tick **missed 7 of 70 closes entirely** and earned less per contract. Directly answers "what if it never hits the low": you lose the trade and gain nothing. |
| 10 | **Commodities (GOLD, SILVER, WTI, NATGAS…)** | Settle on a **single instantaneous print**, not a 60-second average. pin's entire mechanism is the variance collapse of an average. Does not apply. |

---

## PARTIAL — tested, not conclusive

| # | idea | state |
|---|---|---|
| 11 | **Dynamic per-trade floor** *(operator, repeatedly)* | The core open item. `pinprob.py` computes `p_flip` per trade and the ceiling falls out as `1 − p_flip − margin`. **Deployed with a CONSTANT p_flip, which collapses it to a fixed ceiling.** Volatility-accuracy study running to decide whether the per-trade number can be trusted. |
| 12 | **Buying cheaper — is it free?** | **No.** The model's own risk rises **700×** from the 99¢ band (0.001%) to the 80–90¢ band (0.739%). The discount is compensation for real risk. Confirmed on model risk; realised flips unmeasurable (zero in sample). |
| 13 | **Confidence-based sizing / Kelly** | Study running. Full Kelly says stake 82% of bankroll — only valid if the probability is *known*; ours rests on 3 flips in 333, and at the 1.80% upper bound Kelly changes violently. That instability is the argument for staying small. |

---

## UNTESTED — queued, with why each matters

| # | idea | why |
|---|---|---|
| 14 | **Sweep MULTIPLE price levels, not just the touch** *(operator, 2026-09-08)* | We measure depth only at the best offer (median 125). The book holds more at 96¢, 97¢, 98¢ — **all under our ceiling and all profitable.** Could multiply capacity several-fold. **Highest-value untested item.** |
| 15 | **Order book features** — quote age, depth, imbalance, spread | Quote age cuts both ways: an old quote suggests an absent quoter (safe); a fresh one may be someone who just repriced (dangerous). Must be measured, not assumed. |
| 16 | **Volatility estimator alternatives** | 30/60/120/300/900s, EWMA, jump-robust bipower, r-matched. The live 300s window is arbitrary and never validated. Study running. |
| 17 | **Autocorrelation in `var_factor`** | `engine.var_factor(tau, rho)` accepts a correlation sequence and **every call site passes white noise.** Nobody has ever checked whether index increments are autocorrelated. |
| 18 | **Kalshi's own `avg_60s_data`** | The index feed carries the exchange's own rolling 60-second mean. We reconstruct it ourselves instead. Using theirs would remove any drift between our locked sum and the settlement figure. |
| 19 | **Cross-asset jump warning** | Eleven coins settle at the same second. A BTC jump may be a live warning for an alt trade about to be placed. |
| 20 | **Hour-of-day effects** | All evidence came from the US afternoon; we ran overnight. Fire rate and flip rate by hour, unmeasured. |
| 21 | **Coin Race (`KXCRYPTOLEAD15M`)** | **Qualifies for pin** — both ends are 60-second averages of indices we already stream — and has **never been traded**. 5 legs per close that must sum to 100¢, a second independent constraint. |
| 22 | **Getting losses into the sample** | Everything above is limited by a dataset with **zero losses at tau 3–30**. Needs a longer span or a deliberately looser rule in backtest only. **Blocks items 6 and 13.** |
| 23 | **Capacity re-measurement under the current rule** | The old "$30/day, ceiling ~$100" figure came from a *different* rule. Not re-derived since v1–v6. |

---

## DEAD — structurally impossible

| # | idea | why |
|---|---|---|
| 24 | `KXADA15M`, `KXBCH15M`, `KXTON15M`, `KXCRYPTOCOMP15M` | Zero markets in any status. Not products. |
| 25 | Spot data for BNB, ZEC, HYPE, NEAR | **No constituent exchange books recorded at all** — `crypto_feeds.py` never subscribed. Four coins we actively trade have no spot-side visibility. Would need a collector change. |

---

## Validation controls (standing gates, run on every change)

| control | result |
|---|---|
| **Mirror** — offer it the opposite side of its own trades | Refused **70 of 70** |
| **Forced wrong side** | Lost **70 of 70**, −4.76¢/trade |
| **Placebo** — outcomes shuffled | **−48.68¢/trade** |

The placebo is the strongest evidence in the project: with outcomes randomised
the same rule bleeds badly, so the edge comes from picking the side, not from
bookkeeping.

---

## Standing caveats that apply to everything above

1. **Zero losses observed, live or in the dataset, at tau 3–30.** At the
   measured 0.90% flip rate this is the *expected* outcome, not evidence of
   safety. The first loss costs roughly ten wins.
2. **The flip rate rests on 3 flips in 333** (or 1 in 359 at the 0.3¢ floor).
   Its 95% upper bound is 1.80% — double the point estimate. Every threshold
   in the system is built on that number.
3. **`MEASURED_FLIP = 0.0090` was taken from the 0.5¢-floor cell** while we
   run the 0.3¢ floor (whose cell shows 0.28%). It lands conservatively
   between estimate and upper bound, but by accident rather than design.
