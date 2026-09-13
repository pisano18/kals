# FACTS.md — the raw material, one line at a time

**What this is.** Every fact we have MEASURED, stated atomically, with where it
came from. Not a summary, not a narrative, not a conclusion. An inventory.

**Why it exists.** On 2026-09-13 the operator said, in his own words:

> *"Take data points that aren't seemingly connected and pair it with a thought
> of something else seemingly unconnected, then put them together in a strange
> way to create a solution or original idea no one else could find... most will
> give nothing, but when it does work you have great ideas."*

That day's one good idea came from colliding three facts that lived in three
different files and had never been in the same sentence: **F-R05** (the tape
cannot measure our losses because its population is "an offer was sitting
there" and ours is "someone sold it to us"), **F-P03** (we lose 1 in 4 races),
and **F-I04** (the collector records who did the buying on every trade).
Nothing in any one of them is interesting. Together they were a day's work and
a deployed change.

**So the rule for this file:** facts go in ATOMIC and WITHOUT their conclusion.
"The tick above 90c is 0.1c" belongs here. "Therefore we should sweep" does
not — that is the output, and it goes in `results/`. A fact carrying its own
conclusion cannot recombine with anything, because it has already been spent.

**How it is used.** `research/collide.py` samples pairs and asks one question
of each: *is there a measurement that connects these two?* It records which
pairs have been tried so the same ground is not re-walked. Most pairs give
nothing; that is the expected yield and is not a failure of the method.

**Maintenance.** Add a fact the moment it is measured. Delete one the moment it
is falsified, and say so in the commit. Never edit a fact to fit a story.

---

## C — The contract

| id | fact | source |
|---|---|---|
| F-C01 | A new 15-minute window opens every 15 minutes, 24/7, on 12 crypto series. | `RUNBOOK.md` |
| F-C02 | Settlement is the simple average of the sixty 1-second index prints before the close. | market `rules_primary` |
| F-C03 | The strike is the same average over the sixty seconds before the OPEN. | market `rules_primary` |
| F-C04 | `strike(N+1) == settle(N)` exactly — one strike per window. | `CLAUDE.md` |
| F-C05 | The two averaging windows are 840 seconds apart, so `Var(settle - strike) = 880 sigma^2`. | `RUNBOOK.md` |
| F-C06 | With `tau` seconds left, `60 - tau` of the settlement prints are already on disk and unchangeable. | `CLAUDE.md` |
| F-C07 | Fair value's sensitivity to the volatility estimate is exactly ZERO at 50c. | `CLAUDE.md` |
| F-C08 | Mean `abs(fair - 50c)` at the open is 4.75c; 40% of windows open outside 45-55c. | `RUNBOOK.md` R1 |
| F-C09 | S&P and Nasdaq 15-minute series EXIST (`fifteen_min`, `quadratic`) and have never run a single market. | `CURRENT_STATE.md` |
| F-C10 | `KXADA15M`, `KXBCH15M`, `KXTON15M`, `KXCRYPTOCOMP15M` return zero settled markets. | `CLAUDE.md` |

## X — The exchange

| id | fact | source |
|---|---|---|
| F-X01 | The price tick is tapered: 0.1c below 10c and above 90c, 1c in between. | `engine.tick_at` |
| F-X02 | Makers pay no fee. Takers pay `0.07 * p * (1-p)`, billed per ORDER and ceilinged to $0.0001. | `CLAUDE.md`, `pinrun.billed_fee` |
| F-X03 | A crossing IOC limit fills at the RESTING order's price, not at our limit. 283/283 live fills at or below the signalled price; 76 strictly better; ZERO worse. | 2026-09-13, `RUNBOOK.md` |
| F-X04 | The order body has no "no" side: `price` is always the YES price. Buying NO at q is `side="ask", price=1-q`. | `pintake` docstring |
| F-X05 | Sweeps print per level — 59% of same-instant groups, median 8 legs. | `results/RESULTS_informed` |
| F-X06 | Our demo key returns 200 on demo and 401 `NOT_FOUND` on production — proven demo-only. | 2026-09-06 |
| F-X07 | Order round trip from this box is a median 96 ms, p90 116 ms. | 362 live orders |

## M — The model

| id | fact | source |
|---|---|---|
| F-M01 | Fair value is `Phi(((locked_sum + tau*spot)/60 - K) / sd)`. | `CLAUDE.md` |
| F-M02 | `sd/sigma` collapses far faster than `sqrt(tau)` — 9.7x too large at `tau = 10` if you use `sqrt(tau)`. | `CLAUDE.md` |
| F-M03 | The model states a confidence. Over the live-gate candidate population it claims it will be wrong 0.15% of the time. | `pinlevels` rows |
| F-M04 | It is actually wrong 2.90% of the time on that population — **19x** its own claim. | 2026-09-13 |
| F-M05 | That overconfidence went from **12.5x** in the first 70% of closes to **28.2x** in the last 30%, while its STATED confidence barely moved (0.99851 -> 0.99837). | 2026-09-13 |
| F-M06 | Multiplying the volatility estimate by 1.25 before deciding keeps 44% of trades and makes the bad rate WORSE (2.90% -> 3.09%). At 2.0x, 4.62%. Distrusting the model more does not help. | 2026-09-13 |
| F-M07 | Where nobody offered to sell, the model misses its own claim by 0.028pp. Where somebody did, by 0.725pp — **26x**. | `results/RESULTS_select.md` |
| F-M08 | Within each coin, the LOWEST measured-volatility fifth is the worst (5.19% bad, 43.7x overconfident); the middle fifth is the best (1.38%, 8.3x). | 2026-09-13 |
| F-M09 | Sigma is NOT comparable across coins — it scales with the coin's price. Bucketing on raw sigma sorts by coin. | 2026-09-13 |

## P — Our performance

| id | fact | source |
|---|---|---|
| F-P01 | Break-even is a **3.58%** close-loss rate. A win pays ~3.7c, a loss costs ~96c: one loss undoes ~27 wins. | `CURRENT_STATE.md` |
| F-P02 | Current version: 35 closes, 34W 1L. All live history: 12 losing of 248 closes (4.84%). The two straddle break-even. | `pinver` |
| F-P03 | 28.2% of live orders fill NOTHING. | 362 live orders |
| F-P04 | It is not our speed: filled and zero-filled orders have the SAME median latency, 96 ms both. | 2026-09-13 |
| F-P05 | Mean entry 95.6c; mean edge at signal +3.9c (current version), +4.60c over all history. | `pinver` |
| F-P06 | The hedge recovers about one third of a loss, and that decays with size: 34.9% at 20, 33.2% at 68, 22.3% at 250. | `CURRENT_STATE.md` |
| F-P07 | Selling a winner before settlement always loses money. By 15s out a loser's bid is already 23c, 6c at 10s. | `results/RESULTS_exit.md` |
| F-P08 | 0 of 18 closes FOLLOWING a loss lost. Mean dollars after a loss is HIGHER. | 2026-09-13 |
| F-P09 | Removing the depth floor costs 30% of the money: +15% fills, -35% mean size, -25% contracts. | `results/RESULTS_levels.md` |
| F-P10 | Market-making at the touch earns +0.48c per fill, t=+6.4, on 17.1M fills — and takers there carry ZERO information (t=0.2). Never turned into dollars because queue position is unmeasured. | `results/RESULTS_informed` |
| F-P11 | No coin is reliably safer: rank correlation between halves is +0.35 and the rule fails non-monotonically out of sample. | `results/PREREG_coinrank.md` |

## O — The other side

| id | fact | source |
|---|---|---|
| F-O01 | Someone else takes the offer we wanted within 1 second **87.9%** of the time. | `results/RESULTS_contest.md` |
| F-O02 | When they do, the first competing take lands at a median **67 ms**, and the fastest tenth at 6 ms. | same |
| F-O03 | They consume the whole level 68.6% of the time. | same |
| F-O04 | 83.3% of the time there is NO ask at any price on the side the model wants. Of those, 100% carry an ask on the LOSING side — somebody is quoting, and will not quote the side we want. | `results/RESULTS_select.md` |
| F-O05 | Whether an offer gets taken is partly CAUSED by the outcome — the gap grows 3.18 -> 88.55 pp as the window widens 250 ms -> 60 s. Any forward-looking window leaks the answer. | `results/RESULTS_contest.md` |
| F-O06 | Every bad fill in the select sample sat on a price under 0.25s old; prices resting 30s+ had 0 failures in 302. Chosen after seeing the tape; logged live, never gated on. | `results/RESULTS_select.md` |
| F-O07 | The counterparty's behaviour did NOT change between the early and late tape — contest 88.6% -> 86.8%, speed 66 -> 70 ms, depth UP. Only the model's accuracy changed. | 2026-09-13 |

## R — Rules we measured our way into

| id | fact | source |
|---|---|---|
| F-R01 | Twelve series settle on the same quarter hour at rho ~0.8 — worth ~1.22 independent observations per close, not 12. | `CLAUDE.md` |
| F-R02 | Measured on the candidate population, that rho is 0.62-0.69 and the design effect is 31-46x. | `pincontest` |
| F-R03 | Cross-strike arbitrage is UNDEFINED here, not merely absent — there is one strike per window. | `CLAUDE.md` |
| F-R04 | Every large edge this project has produced has been a measurement bug. | `CLAUDE.md` |
| F-R05 | The tape's population is "an offer was sitting there"; ours is "someone actively sold it to us". Only the second is adversely selected, and the two differ 31x. | `CLAUDE.md` rule 5 |
| F-R06 | Trying to reconstruct that second population from the trade tape FAILS — the clean backward-looking version has no power (+1.27 pp, [-1.62, +4.57], MDE 4.05). | `results/RESULTS_contest.md` |

## I — Infrastructure and data

| id | fact | source |
|---|---|---|
| F-I01 | The settlement index (`cfbenchmarks_value`) arrives once per second. | collector |
| F-I02 | Channels recorded: `cfbenchmarks_value`, `ticker`, `trade`, `orderbook_snapshot`, `orderbook_delta`. | `kalshi_collector.py` |
| F-I03 | 57.7 million trade records over 376 hours; ~5% fall in the last 60 seconds of a quarter hour. | 2026-09-13 |
| F-I04 | Every trade record carries `taker_outcome_side` — WHO crossed, on which side, to the millisecond. | trade channel |
| F-I05 | A collector restart inside a UTC hour leaves two gzip members and the standard reader recovers ZERO lines from that file, not half. | `gzsalvage.py` |
| F-I06 | Kalshi renamed fields once and 68,976,084 of 68,976,084 deltas went unparsed while every stage exited 0. | `CLAUDE.md` |
| F-I07 | `discover()` skips an unknown ticker with no error and no log line. | `CLAUDE.md` |
| F-I08 | Below 5 GB free disk the watchdog EXITS ITS LOOP and the tape ends. The guard is 6 GB. | `run_all.ps1:41` |
| F-I09 | `pinlevels_rows.jsonl` holds 16,683 candidates, of which 2,699 are ones the live bot REFUSES (dump guard). | 2026-09-13 |
| F-I10 | The watchdog only checks liveness every 300 seconds, so anything killed costs up to five minutes of unrecoverable tape. | `run_all.ps1` |

## B — Bankroll and risk

| id | fact | source |
|---|---|---|
| F-B01 | Size follows the bank automatically, re-read every 300 seconds, and only while flat. | `pinrun.autosize_tick` |
| F-B02 | `size = bank / (BANK_BRAKE * MAX_PER_CLOSE * PRICE_CEILING)`; at BANK_BRAKE 3.0 that is `bank / 5.88`. | `pinrun` |
| F-B03 | The worst one close can lose is exactly `MAX_PER_CLOSE * size * PRICE_CEILING` — a bound, not a sample maximum. | `pinbank` |
| F-B04 | Because size follows the bank, consecutive worst-case losses shrink geometrically: 33%, then 22%, then 15% of the starting bank. | `pinbank`, 2026-09-13 |
| F-B05 | The loss brake counts losing CLOSES, not losing trades. Three stops the run. | `pinrun` A8(B) |
| F-B06 | At the current close-loss rate a back-to-back pair is a 3.0% event per day, 19.5% per week, 60.6% per month. | 2026-09-13 |
| F-B07 | The drawdown model explodes above break-even: 11.6 worst-closes deep at 2.86%, 34.6 at 4.84%. More capital buys a longer bleed, not survival. | `pinbank` |
