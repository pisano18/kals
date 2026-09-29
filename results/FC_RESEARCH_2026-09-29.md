# Forecaster loss research, 2026-09-29 -- workflow wf_3deb4ed1-525 (7 lenses, 7 adversarial verifiers, 1 synthesis)

REPLAY ONLY (displayed-offer population). Operator 2026-09-29: "do heavy research ... don't be afraid to do anything no matter how outlandish". Per-lens scripts and logs: <scratchpad>/clean/research/<lens>/ and <lens>_verify/ (scratch, not committed). Dataset bug found by the verifiers (fc_dataset.jsonl dropped 340 of 934 realistic fills -- realistic fills in seconds where the decision-instant rule had hit its cap) is FIXED in research/cleanroom/fc_features.py; rebuilt dataset fc_dataset_v2.jsonl (3,785 rows) reproduces the replay's realistic money to the cent (TRAIN +$2,934.76, TEST +$886.76). The synthesis below already used corrected data.

# Synthesis: can anything separate the forecaster's losing buys from its winners? (REPLAY only)

**Answer: no. Nothing survived verification.** Seven lenses tried about 7,060 configurations: meta-labelling 1,260, pooling ~500, microstructure 46 families (~180 thresholds), denoise 97, cross-asset 147, risk/sizing 446 and outlandish 4,561. None of them saves as much losing money as it cuts winning money on the untouched TEST days while also pointing the same way on held-out TRAIN days. Two methods were marked "promising" by their authors. Both failed adversarial verification:
- the risk-budget reallocation, which only "passed" by betting more;
- the narrowed race rule, which the full engine replay reverses on one population and which is chance-level on TRAIN.

Every number below comes from the replay, which is the population of offers that were on display. It is a source of hypotheses and never our loss rate (CLAUDE.md amendment 2026-09-10 rule 5).

Terms: TRAIN = 08-25..09-17 (24 days); TEST = 09-18..09-26 (9 days, read once). "Realistic" = fills that pass the 1-second rule (the size is still displayed 1 s later). "Decision-instant" = the larger check that assumes every offer seen was filled.

---

## 0. The corrected baseline (every lens that used fc_dataset's survived rows had it wrong)

I recomputed this myself from `fcvar3/base_fills.jsonl` with `research/synth_check.py`:

| population | split | net | money on losing rows | losing rows / markets | money in net-negative markets |
|---|---|---|---|---|---|
| realistic | TRAIN | +$2,934.76 | -$551.91 | 19 / 16 | -$499.38 (14 markets) |
| realistic | TEST | +$886.76 | -$199.29 | 5 / 4 | -$198.01 (4 markets) |
| decision-instant | TRAIN | +$6,599.49 | -$6,614.78 | 152 / 103 | -$5,389.82 |
| decision-instant | TEST | +$2,785.16 | -$1,409.98 | 37 / 24 | -$1,138.79 |

- **The brief's -$499 / -$198 is the same money counted a different way.** It nets each market (5 TRAIN markets held both sides). The other figure counts losing rows. Both are correct.
- **`fc_dataset.jsonl` is missing 340 of the 934 realistic fills.** These are fills at seconds after the decision-instant engine had already hit its cap (337 of the 340). The missing rows hold +$926.78 of TRAIN net and **4 of the 16 TRAIN losing markets (-$273.27, 49% of TRAIN realistic losses)**, plus 1 TEST losing market (KXDOGE15M-26SEP181600-00, -$12.52). All five verifiers confirmed this independently. Use `base_fills` (fill == 'real'), or one of the rebuilt union files: `microstructure/msdata.jsonl`, `pooling/pool_dataset.jsonl` or `outlandish/decisions.jsonl` (3,785 rows each).
- **`fc_dataset`'s `x_intensity` is biased.** It is computed on trades already cut at close minus 45 s.
- **Two structural facts limit every test:**
  1. **TEST is thin.** Realistic TEST has only 4 losing markets, and two of them (KXNEAR15M-26SEP250300-00 -$85.21 and KXBNB15M-26SEP221230-30 -$76.32) are 81% of the $199 lost. All 4 were fresh offers, meaning the price had changed in the last second (feat_age 0.2).
  2. **Decision-instant losses are a weak stand-in for realistic ones.** 98 of the 103 TRAIN decision-instant losing markets are ones where the forecaster later flipped and won on the other side. Only 5 of the 16 realistic losing markets are like that.

## 1. Methods that survived verification

**None.** No method from any lens holds.

Closest lead, **NOT a survivor**. It is included only because it is the one idea with a positive full-engine result against the live rule on both realistic splits:

**Narrowed race rule (`race_trend0`). This is a weak hypothesis, chosen after TEST was read.**
- **Rule.** It replaces the live race05_98 skip. Skip a buy of side S at ask q only when all three hold:
  1. feat_toward5 < -0.5;
  2. p_side < 0.98;
  3. p_trend - q - 0.07·q·(1-q) < 0.
- **How p_trend is computed.** It is the forecaster's own p, recomputed with the spot carried forward along its recent trend:
  - b = the least-squares slope of the index prints stamped rel-9..rel (price per second);
  - v_trend = v_rel + b·(-rel)/2;
  - proj = (sum of window prints stamped close-60..close+rel + r·v_trend)/60;
  - sd = v_trend·s·sqrt(s_coef(rel))/60, where s = Tables.f_sig(coin, r, local_sigma_120s);
  - p = f_calibrate(1 - Phi((thr - proj)/sd), r); use 1-p for NO.
- **Live inputs.** Index prints plus the forecaster's own tables. It is live-computable, and the verifier built it inside VEngine (11,537 evaluations).
- **Full-engine replay against the live race05_98 rule** (`outlandish_verify/v_engine_sum_log.txt`):

| population | split | net change | losses saved | wins cut | TEST losing markets behind it |
|---|---|---|---|---|---|
| realistic | TRAIN | +$57.30 | -$5.95 (one more small loss) | -$63.25 (wins added) | n/a |
| realistic | TEST | +$39.57 | $0 | -$39.57 (3 winning markets given back) | **0** |
| decision-instant | TRAIN | **-$95.70** | n/a | n/a | 9 losing markets made worse by $455.58 |
| decision-instant | TEST | +$192.68 | n/a | n/a | 0 losing markets changed |

- **Why it is not a survivor:**
  1. On TRAIN, the race rows it gives back lose as often as the rows it keeps blocking: 11.5% vs 11.9% of rows. A random subset of race rows of the same size beats it 8-11% of the time.
  2. It was picked from 13 combinations after the TEST read, and the race thresholds themselves were chosen on all 33 days, TEST included.
  3. Simply loosening the race threshold recovers 93-95% of its TRAIN gain, and similar variants (race2, race1_98) already failed on TEST.
- **Scale.** At live size (about 1/20 of paper, and not exact, because small orders fill differently) +$57 over 24 days is roughly +$3.

Also examined and **not** a survivor: the fresh-offer cut. It caps a buy at 25 paper contracts when the offer is under 0.5 s old and p < 0.95, and it is the loss-cutting half of risk/sizing's reallocation. The pattern behind it is real in the replay: 12 of 14 realistic losing markets after the race rule were fresh offers. But acting on it at equal size costs more than it saves:

| population | split | net change | losses saved | wins cut |
|---|---|---|---|---|
| realistic | TRAIN | -$319.27 | $186.98 (3 BTC markets) | $506.25 |
| realistic | TEST | -$113.98 | $57.24 (one market, BNB 09-22) | $171.22 |
| decision-instant | TEST | -$372.82 | $465.73 | n/a |

## 2. What combines, and the order to test (one thing at a time)

Nothing survived, so there is no combination to build. Several ideas turned out to duplicate what is already running:
- **Duplicates the live race rule:** denoise's best Kalman config (1 of 84); about half of pooling's "price fell in 10 s" vetoes (14 of 29 TRAIN losers); both TEST savings of tox_book / tox_flow / mid-2s (the same NEAR 09-25 market the race rule already skips).
- **Duplicates the 1-second fill rule:** cross-market Kalshi signals (0 of 8 and 0 of 14 flagged losers survive 1 s); ask-crash and "vanished offers" in general. Offers that vanish within 1 s lose 1.29x what the model expects (90% range 1.06-1.55). Offers that survive lose 0.82x (0.46-1.22). The 1-s rule is already the toxic-offer filter.
- **Not additive:** `race_trend0` replaces race05_98. The fresh-offer cut would stack on top of the race rule, but it fails on its own.

Recommended order:
1. **Now, with no trading change:** let the live race05_98 rule reach its pre-registered forward bar (READS_DUE `forecaster-live` / `fcvar-paper`). Add a per-decision and per-fill feature snapshot to the live forecaster's log, if it is not already there. This is a code change to a live bot, so it needs a VERSIONS entry and whatever sign-off the main session requires.
2. **Paper only, one arm:** `race_trend0` beside race05_98, with the bar written before any result. Suggested bar: the buys it gives back must net at or above $0 after at least 100 given-back buys; stop early if their losses exceed their profits. The expected dollars are small, so this is low priority.
3. **Only after at least 30 live losing markets:** re-test the fresh-offer cut, ask-crash, tox_book and market-quote fusion on live fills, which is the only valid loss population.
4. **Separate read-only research:** a constituent-exchange leading signal (see section 4).

## 3. Tried and ruled out (replay; TEST realistic net unless stated)

- **Meta-label logistic, ~80 features.** It ranks losers better (TEST score 0.85 vs the model's 0.80, where 0.5 is a coin flip). But the flagged buys still lose less often than their price's break-even (11.7% vs 15.6%), so skipping them loses money: -$73; decision-instant -$91.
- **Near-miss (ordinal) meta-model:** -$82; decision-instant -$242. The TRAIN gain came from one fold, and a shuffle null matched it.
- **Boosted trees:** -$127. They found no interaction the linear model missed.
- **Sizing by probability** (Kelly, parameter-uncertainty Kelly, the AFML 2Φ(z)-1 map, edge-proportional, vol targeting, meta-model shrink): every configuration was negative once the race rule is applied. The model is near-certain on most buys, so shrinking cuts wins everywhere.
- **Pooling the model with the market price** (log pool, extremized, Bates-Granger, Bayesian averaging): these removed only winners. Bates-Granger -$127; log pool -$2 with 0 of 19 TRAIN losers removed.
- **Trade only when model and market agree:** -$567. It throws away the profit source.
- **Veto when our side's ask, bid or mid fell 7-8c in 10 s:** -$15 to -$44, 0 of 4 losing markets caught. These are one test, not three.
- **Rising-ask veto (the operator's idea):** removed only winners on TRAIN.
- **Classic toxic-flow measures** (order-flow imbalance, VPIN, Kyle's lambda, Hawkes intensity, big prints, microprice, depth imbalance): cross-validation chose "no veto" in every fold.
- **Toxicity models** (logistic, trees, money-weighted, fresh-only): -$100 to -$115.
- **tox_book / tox_flow / mid-2s indices:** each TEST gain is the single NEAR 09-25 loss, which the race rule already skips. All are negative on held-out TRAIN, and tox_book flips to -$42.55 with a 4% cut.
- **Ask crash (ask fell at least 8.5c in 10 s):** -$66. The TRAIN gain is one $88 loss.
- **Denoising the spot** (Kalman level, Haar wavelets, median-of-3, EMA): forecasts get worse and money -$42 to -$141. The newest print is real information: a move over 4 sigma continues 28-59% of the time and reverses only 4-9%. **This rules out "degaussing".**
- **Jump-robust and alternative volatility** (bipower, MedRV, EWMA, Student-t tails, vol-regime scaling): small forecast gains at most; -$59 to -$258.
- **Momentum / drift / Kalman velocity corrections:** slopes are tiny; -$99. The one positive config (1 of 84) duplicates the race rule.
- **Fusing the model with the market quote:** the biggest forecast gain (TEST log-loss -5%). But it cuts 3-17x more winning money than losing money on TRAIN at every margin.
- **BTC / market lead-lag drift:** real (t 10-43) but tiny at settlement scale. TRAIN -$144 realistic, -$611 decision-instant; TEST -$2.
- **Cross-market Kalshi signals:** the losers they flag are stale offers the 1-s rule never fills.
- **Per-close exposure caps, same-direction caps, loss-clustering vetoes:** realistic losing markets never share a close (at most 1 per close), so these caps only cut wins.
- **Drawdown de-leveraging, day stop, circuit breakers:** losses do not cluster in time; all negative.
- **"Model got burned recently" pause (surp_16 > 5):** it rests on one $88 loss in one episode (09-11/12) and never fires in TEST.
- **Per-coin, hour, weekday and minute reliability:** empirical-Bayes finds between-group spread of about 0.
- **Macro-release time slots:** 0 realistic losers in those slots; TRAIN -$176.
- **Insurance (also buy the other side):** algebraically this is buying less plus a certain loss. It costs $174-$872 more than simply buying less for the same protection.
- **Scale in on confirmation:** cuts 32-59% of losses but nets -$46 to -$82. The TEST saving is the same single BNB market.
- **Risk-budget reallocation (cap 200 on stale offers, 25 on fresh):** it passes only because it bets more. Against its own up-size-only control, the loss-cutting part fails in all four cells (TEST realistic -$114 for $57 saved, one market). It would also need a live size step.
- **Analogue / nearest-neighbour matching** (index paths, past decisions): worse than the model on TEST, and its "over-confident" flag reversed.
- **Anomaly detection** (Mahalanobis, isolation forest): losing decisions are not unusual states.
- **Conformal abstention:** it is only a threshold on a weak classifier: -$76.
- **Order-flow entropy, round numbers, strike-crossing timing, fractal and entropy measures, streaks, calendar, Benford, crowding:** no information. Round numbers -$444.
- **Local-only-sigma edge** (outlandish's single pre-registered candidate): passed TRAIN cross-validation and the null, then caught 0 of 5 TEST realistic losing rows: -$43.
- **Trend-carried fair value alone:** roughly halves losses, but TRAIN -$221 (7.5% of net) and TEST -$11.
- **"Volatility input lags" and "over-confident at p ≥ 0.98" by-products:** neither reproduced on TEST.

## 4. What would be needed to learn more

1. **Live fills with a feature snapshot at every decision and fill.** The replay cannot see whether an offer was sold to us, and our loss rate comes only from live fills (the 09-11 measurement found a 31x gap between tape and live). Log at least:
   - offer age;
   - toward5 and p_trend;
   - our side's ask, bid and mid 3 s and 10 s earlier;
   - last trade price and age;
   - the "no trade since close-45 s" flag;
   - depth within 3 ticks;
   - taker flow over 2-10 s;
   - the other coins' index moves;
   - the market mid (for fusion).
   
   Re-test only after at least 30 live losing markets.
2. **More losing markets in the replay.** Realistic losing markets arrive at about 0.67 a day (TRAIN, 16 in 24 days) to 0.44 a day (TEST, 4 in 9). Reaching 30 new ones needs roughly 45-70 more recorded days. Until then, any effect smaller than one ~$80 loss cannot be measured on realistic TEST.
3. **A signal the digest does not have: constituent exchange prices (`feed_data`).** The CF index is built from them each second. The Kalshi book already leads the index by about 1 s (lead correlation +0.125 vs lag +0.01; not independently recomputed, and possibly CF stamping delay). This is the one mechanism no lens could test. Read `feed_data` read-only and never modify it.
4. **Judge every candidate inside the engine (fc_variants), not by removing rows.** Per-side and per-close caps bind on 57-71% of fills, and the bot re-decides a second after a skip. `race_trend0` went from +$326 to -$96 on TRAIN decision-instant once it was run in the engine.
5. **Untested and low priority:** using the market quote to add buys, since fusion was only tried as a veto; and a forecaster sigma change re-run through fc_replay, since changing p changes which buys exist.

## 5. Things the operator may be missing

- **The live race05_98 rule's own replay record** (full engine vs base, the "1/3 less loss for a little profit" trade, live since 2026-09-29 04:21Z):

| population | split | net change | losing-market money saved | losing markets |
|---|---|---|---|---|
| realistic | TRAIN | -$16.45 | $147.80 of $499.38 (30%) | 14 → 10 |
| realistic | TEST | -$14.95 | $101.06 of $198.01 (51%) | 4 → 3 |
| decision-instant | TRAIN | +$107.15 | n/a | n/a |
| decision-instant | TEST | **-$285.59** | only $45.35 | n/a |

  Its thresholds were chosen with TEST days in view. Its forward bar is the real test.
- **The one loss nothing catches.** KXBNB15M-26SEP221230-30 (-$76.32: fresh offer, index not racing, p 0.926) is rated low-risk by every model in every lens.
- **"Quiet" buys are the best money.** Buys with no trade since close minus 45 s:
  - TRAIN: 157 buys, 0 losses, +$934;
  - TEST: 79 buys, 0 losses, +$532, which is 60% of TEST realistic profit.
  
  Never veto them. Sizing them up would be a size step, and it is untested against the model's own p.
- **Realistic replay losses look like plain bad luck at the model's own odds:** 19 actual vs 23.3 expected on TRAIN (90% range of the ratio 0.46-1.22). That is why every filter cuts winners in proportion.

Housekeeping: my only script is `research/synth_check.py` (read-only). Both recorders were alive after it ran (crypto_feeds pid 105352, kalshi_collector pid 2532788). Free disk 57.2 GB, free RAM 2.0 GB. Nothing under C:\kals-repo or C:\kals was touched. `outlandish/pool.jsonl` (296 MB) can be deleted.
