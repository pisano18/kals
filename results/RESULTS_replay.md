# RESULTS_replay -- does the tape replay reproduce our own trades?

`research/pinreplay.py`, run 2026-09-12T13:03:56Z.

**n = 195 live fills over 150 closes over 190 markets**, every one a real order the bot actually got filled on, read from `results/pinrun-live-*.jsonl`. **9 of them lost money.** No simulated fill, no assumed rule, no tape-derived loss rate appears anywhere in this file -- the losses are our own.

Zero deltas failed to parse.

Tape integrity: 0 hour-channels needed member-by-member gzip salvage (a collector restart inside the hour; the standard reader recovers ZERO lines from those and would have shown an empty book). 0 hour-channels are missing entirely.

## What each check means

| | question |
|---|---|
| (a) | does the replayed index reproduce the `fair` the live model logged, to 1e-4? Three feeds are tried: ticks stamped `<= S` (pinsim's rule), `<= S-1`, and ticks fed by ARRIVAL up to the reconstructed decision millisecond. |
| (b) | is there an ask at or better than the price we paid, in the rebuilt book, on our side -- at the second boundary (what the backtest sees) and at every delta instant inside the second (what the bot saw)? |
| (c) | is our own fill on the trade tape as a print with `taker_side` = our side, our price to one tick and our size to 20%? |
| (d) | does `fulltape/markets.json` agree with the outcome the live bot booked? |
| (e) | would `pinsim.decide` -- the existing backtest's decision function, called here, not reimplemented -- have bought it, and if not, what reason string does it return? |

### ALL FILLS -- n = 195 fills over 150 closes

| flag | fills | % | closes |
|---|---|---|---|
| FAIR_DIVERGE | 4 | 2.1% | 3 |
| FAIR_NEEDS_ONE_SEC_LAG | 28 | 14.4% | 28 |
| PRICE_DIVERGE_AT_W | 44 | 22.6% | 41 |
| OFFER_MISSING | 30 | 15.4% | 30 |
| OFFER_ONLY_SUBSECOND | 30 | 15.4% | 30 |
| PINSIM_BOOK_DIFFERS_FROM_SEQ_ORDER | 32 | 16.4% | 31 |
| TS_ORDER_BOOK_DIFFERS_FROM_SEQ_ORDER | 109 | 55.9% | 94 |
| OUR_FILL_NOT_ON_TAPE | 14 | 7.2% | 13 |
| NO_TAPE_SETTLEMENT | 21 | 10.8% | 15 |
| NO_LIVE_SETTLEMENT | 9 | 4.6% | 5 |
| REFUSED_BY_PINRUN_DUMP_GUARD_TODAY | 10 | 5.1% | 9 |
| REFUSED_BY_BACKTEST_PROFILE_RULE | 9 | 4.6% | 8 |
| FULL_BACKTEST_WOULD_NOT_BUY | 93 | 47.7% | 78 |
| INDEX_SETTLE_WINDOW_INCOMPLETE | 2 | 1.0% | 1 |
| BACKTEST_WOULD_NOT_BUY | 91 | 46.7% | 77 |

**Why `pinsim.decide` would not have bought (91 of 195)** -- at the second boundary, today's gate, our own order size:

| reason | fills | % |
|---|---|---|
| `undecided` | 42 | 21.5% |
| `too_shallow` | 29 | 14.9% |
| `over_ceiling` | 19 | 9.7% |
| `no_offer` | 1 | 0.5% |

### THE LOSING FILLS ONLY -- n = 9 fills over 7 closes

| flag | fills | % | closes |
|---|---|---|---|
| PRICE_DIVERGE_AT_W | 3 | 33.3% | 3 |
| OFFER_MISSING | 2 | 22.2% | 2 |
| OFFER_ONLY_SUBSECOND | 2 | 22.2% | 2 |
| PINSIM_BOOK_DIFFERS_FROM_SEQ_ORDER | 1 | 11.1% | 1 |
| TS_ORDER_BOOK_DIFFERS_FROM_SEQ_ORDER | 5 | 55.6% | 3 |
| NO_TAPE_SETTLEMENT | 1 | 11.1% | 1 |
| REFUSED_BY_PINRUN_DUMP_GUARD_TODAY | 4 | 44.4% | 4 |
| REFUSED_BY_BACKTEST_PROFILE_RULE | 4 | 44.4% | 4 |
| FULL_BACKTEST_WOULD_NOT_BUY | 8 | 88.9% | 6 |
| BACKTEST_WOULD_NOT_BUY | 8 | 88.9% | 6 |

**Why `pinsim.decide` would not have bought (8 of 9)** -- at the second boundary, today's gate, our own order size:

| reason | fills | % |
|---|---|---|
| `undecided` | 3 | 33.3% |
| `too_shallow` | 2 | 22.2% |
| `over_ceiling` | 2 | 22.2% |
| `no_offer` | 1 | 11.1% |

### THE WINNING FILLS ONLY (the control) -- n = 186 fills over 147 closes

| flag | fills | % | closes |
|---|---|---|---|
| FAIR_DIVERGE | 4 | 2.2% | 3 |
| FAIR_NEEDS_ONE_SEC_LAG | 28 | 15.1% | 28 |
| PRICE_DIVERGE_AT_W | 41 | 22.0% | 39 |
| OFFER_MISSING | 28 | 15.1% | 28 |
| OFFER_ONLY_SUBSECOND | 28 | 15.1% | 28 |
| PINSIM_BOOK_DIFFERS_FROM_SEQ_ORDER | 31 | 16.7% | 30 |
| TS_ORDER_BOOK_DIFFERS_FROM_SEQ_ORDER | 104 | 55.9% | 91 |
| OUR_FILL_NOT_ON_TAPE | 14 | 7.5% | 13 |
| NO_TAPE_SETTLEMENT | 20 | 10.8% | 15 |
| NO_LIVE_SETTLEMENT | 9 | 4.8% | 5 |
| REFUSED_BY_PINRUN_DUMP_GUARD_TODAY | 6 | 3.2% | 6 |
| REFUSED_BY_BACKTEST_PROFILE_RULE | 5 | 2.7% | 5 |
| FULL_BACKTEST_WOULD_NOT_BUY | 85 | 45.7% | 73 |
| INDEX_SETTLE_WINDOW_INCOMPLETE | 2 | 1.1% | 1 |
| BACKTEST_WOULD_NOT_BUY | 83 | 44.6% | 71 |

**Why `pinsim.decide` would not have bought (83 of 186)** -- at the second boundary, today's gate, our own order size:

| reason | fills | % |
|---|---|---|
| `undecided` | 39 | 21.0% |
| `too_shallow` | 27 | 14.5% |
| `over_ceiling` | 17 | 9.1% |

## (a) which index feed reproduces the live `fair`

| feed | fills within 1e-4 | median |d| | max |d| |
|---|---|---|---|
| ticks stamped <= S  (**what pinsim does**) | 163/195 (83.6%) | 3.05e-06 | 8.26e-02 |
| ticks stamped <= S-1 | 59/195 (30.3%) | 3.79e-03 | 4.70e-01 |
| ticks by ARRIVAL <= decision ms  (**faithful**) | 170/195 (87.2%) | 2.80e-06 | 1.64e-01 |

## (b) where the offer we hit actually was

| the offer we paid was visible... | fills | % |
|---|---|---|
| at the START of second S (pinsim's own view) | 148 | 75.9% |
| at the END of second S | 68 | 34.9% |
| at the reconstructed DECISION instant | 154 | 79.0% |
| at SOME millisecond in [S-1, S+2) | 195 | 100.0% |
| at NO millisecond at all -- invisible to any book replay | 0 | 0.0% |

### which book reconstruction reproduces the offer the live model logged

The live `signal` record logs the exact `price` the bot saw on our side. That is the ground truth for a book rebuild, so it is scored directly. `seq order` merges snapshots and deltas on the exchange's own sequence number; `timestamp order` merges them on the clock (deltas' `ts_ms`, snapshots' receipt time); `snapshots-first` is what `pinsim.run()` does -- every snapshot in the hour applied before any delta.

| reconstruction, evaluated at | == live logged price | median |d| (cents) |
|---|---|---|
| **seq order, the decision millisecond** | 151/195 (77.4%) | 0.00c |
| seq order, start of second S | 76/195 (39.0%) | 0.20c |
| seq order, end of second S | 36/195 (18.5%) | 0.60c |
| timestamp order, start of second S | 35/195 (17.9%) | 30.00c |
| snapshots-first (pinsim), start of second S | 66/195 (33.8%) | 0.30c |

Where the offer was visible at all, it was on the book for a median of **1383 ms** of the 3,000 ms window (p10 372, p90 2757, max 3000).

## (e) would the backtest have bought it? four ways

`pinsim.decide` is CALLED here, not reimplemented. Two things are varied: WHEN the book is read (the second boundary, which is what `pinsim.run()` does, versus the millisecond the live bot actually decided) and WHICH GATE it runs under (the constants in `pinrun` today, versus the ones the `start` record of that fill's own run logged). Nothing else moves.

| book read at | gate | rules | would have bought | top refusal reasons |
|---|---|---|---|---|
| second boundary | today | decide only | **104/195** (53.3%) | `undecided` 42, `too_shallow` 29, `over_ceiling` 19, `no_offer` 1 |
| **decision millisecond** | today | decide only | **128/195** (65.6%) | `undecided` 42, `too_shallow` 13, `over_ceiling` 12 |
| second boundary | **the one that was LIVE** | decide only | **139/195** (71.3%) | `too_shallow` 34, `over_ceiling` 19, `undecided` 2, `no_offer` 1 |
| **decision millisecond** | **the one that was LIVE** | decide only | **169/195** (86.7%) | `too_shallow` 13, `over_ceiling` 11, `undecided` 2 |
| second boundary | today | decide + profile rules | **102/195** (52.3%) | `undecided` 42, `too_shallow` 29, `over_ceiling` 19, `rule:dump` 2 |
| **decision millisecond** | today | decide + profile rules | **121/195** (62.1%) | `undecided` 42, `too_shallow` 13, `over_ceiling` 12, `rule:dump` 7 |
| **decision millisecond** | **the one that was LIVE** | decide + profile rules | **160/195** (82.1%) | `too_shallow` 13, `over_ceiling` 11, `rule:dump` 9, `undecided` 2 |

The gate was not one thing over this window. `PIN` by fill: 0.98 x85, 0.995 x110. A fill taken under `PIN` 0.98 is refused `undecided` by today's 0.995 -- which is a gate change, not a replay defect, and the two must not be confused.

### the two dump guards, which are NOT the same rule

`pinrun` (live) refuses any offer whose discount to fair exceeds 15c at ANY confidence. The `default` profile that `pinsim.run()` applies refuses `conf >= 0.999 AND discount_c > 5`. A trade can pass one and fail the other, so both are counted, on the fair the live model logged and the price we actually paid.

| | all fills | losing fills |
|---|---|---|
| refused by pinrun's live 15c guard as it stands TODAY | 10 | 4 |
| refused by the guard that was live for that fill | 0 | 0 |
| refused by the backtest profile's `dump` rule | 9 | 4 |
| **refused by NEITHER** | 185 | 5 |

Discount to fair across all fills: median 2.95c, p90 8.49c, max 90.02c.
 On the LOSING fills: 1.97c, 2.07c, 3.17c, 4.51c, 5.76c, 18.00c, 26.83c, 40.41c, 90.02c.

## (d) the settlement, three ways

Settlement is the mean of the sixty 1-second index prints in [close-60, close-1], so it is recoverable from the index tape without `fulltape/markets.json`. All three sources are compared.

| | fills |
|---|---|
| live `settled` record present | 186 |
| `markets.json` has a result | 174 |
| index tape has all 60 settlement prints | 193 |
| **index-tape outcome == the outcome we booked live** | 184 |
| index-tape outcome DISAGREES with live | 0 |
| `markets.json` DISAGREES with the index tape | 0 |

## Per-loss detail -- all 9 losing fills, verbatim

These are the trades the operator says the backtest does not show. Each is reported in full, (a) to (e).

#### KXNEAR15M-26SEP082045-45  want NO @ 0.9620  x20  P&L -1929.12c

fill second `2026-09-09T00:44:38Z` (S=1788914678), close 2026-09-09T00:45:00Z from markets.json, tau 22s (live logged tau 22, tau_at_send 22), latency 102.6 ms, decision instant S+440 ms (exact).

| | value |
|---|---|
| **(a) fair, live** | `0.01826` |
| (a) fair, replay ticks<=S (what pinsim uses) | `0.01826`  (|d| 0.000002) |
| (a) fair, replay ticks<=S-1 | `0.02542`  (|d| 0.007158) |
| (a) fair, replay ticks by ARRIVAL<=decision instant | `0.01826`  (|d| 0.000002) |
| (a) closest feed | **sec**, |d| 0.000002 within 1e-4 |
| (a) sigma live / replay | `0.00027759` replay vs live `0.00027800` |
| strike live / tape | 2.3492 / 2.3492 |
| **(b) offer we paid** | 0.9620 (model saw 0.9620) |
| (b) our-side ask at START of S (pinsim's view) | 0.9090 x 25.0 |
| (b) our-side ask at END of S | 0.9620 x 40.0 |
| (b) our-side ask at the DECISION INSTANT | 0.9620 x 60.0 |
| (b) offer <= what we paid, at a second boundary? | **YES** |
| (b) offer existed at some ms in [S-1, S+2)? | **YES**, for 2304 ms of 3000 (145 book states checked; best ask seen 0.9080) |
| (b) offer window (the scan covers S-1000 to S+2000) | S-1000 ms to S+1477 ms |
| (b) book age at instant: replay / live-logged | 7 ms / 90 ms |
| (b) deltas / snapshots (levelled) on this market this hour | 39,323 / 3 (1) |
| **(c) our fill as a print** | FOUND |
| (c) print | taker no @ 0.9620 x 20.00, +82 ms from the decision instant |
| (c) prints on this market in [S-1, S+2) | 26 |
| **(d) settlement, from the INDEX TAPE** | mean of 60 prints = 2.349367 vs effective strike 2.349150 -> `yes` |
| (d) settlement | tape `yes` vs live `yes` -> agree |
| **(e) pinsim.decide, second boundary, today's gate** | **undecided** |
| (e) pinsim.decide at the decision instant | undecided |
| (e) pinsim.decide, second boundary, the gate that was LIVE (PIN 0.9800, ceiling 0.9880) | bought |
| (e) pinsim.decide at the decision instant, the LIVE gate | **bought** |
| **(e) discount to fair we paid** | 1.97c -> pinrun's live 15c guard TODAY: allow; the guard live at the time (-): not logged |
| (e) the backtest profile's rules | trade |
| **(e) FULL backtest verdict (decide + rules), decision ms, today's gate** | **undecided** |
| (e) all size/gate variants at the boundary | now/attempt/s0=undecided, now/gate_size/s0=undecided, now/live_size/s0=undecided, then/attempt/s0=bought, then/gate_size/s0=bought, then/live_size/s0=too_shallow |
| flags | TS_ORDER_BOOK_DIFFERS_FROM_SEQ_ORDER, BACKTEST_WOULD_NOT_BUY, WHYNOT:undecided, FULL_BACKTEST_WOULD_NOT_BUY |

#### KXNEAR15M-26SEP082045-45  want NO @ 0.9560  x20  P&L -1917.89c

fill second `2026-09-09T00:44:39Z` (S=1788914679), close 2026-09-09T00:45:00Z from markets.json, tau 21s (live logged tau 21, tau_at_send 21), latency 78.4 ms, decision instant S+330 ms (exact).

| | value |
|---|---|
| **(a) fair, live** | `0.01235` |
| (a) fair, replay ticks<=S (what pinsim uses) | `0.01235`  (|d| 0.000004) |
| (a) fair, replay ticks<=S-1 | `0.01826`  (|d| 0.005912) |
| (a) fair, replay ticks by ARRIVAL<=decision instant | `0.01235`  (|d| 0.000004) |
| (a) closest feed | **sec**, |d| 0.000004 within 1e-4 |
| (a) sigma live / replay | `0.00027759` replay vs live `0.00027800` |
| strike live / tape | 2.3492 / 2.3492 |
| **(b) offer we paid** | 0.9560 (model saw 0.9560) |
| (b) our-side ask at START of S (pinsim's view) | 0.9620 x 40.0 |
| (b) our-side ask at END of S | 0.9760 x 6.0 |
| (b) our-side ask at the DECISION INSTANT | 0.9560 x 60.0 |
| (b) offer <= what we paid, at a second boundary? | **NO -- OFFER MISSING** |
| (b) offer existed at some ms in [S-1, S+2)? | **YES**, for 381 ms of 3000 (143 book states checked; best ask seen 0.9090) |
| (b) offer window (the scan covers S-1000 to S+2000) | S-1000 ms to S+477 ms |
| (b) book age at instant: replay / live-logged | 52 ms / 21 ms |
| (b) deltas / snapshots (levelled) on this market this hour | 39,323 / 3 (1) |
| **(c) our fill as a print** | FOUND |
| (c) print | taker no @ 0.9560 x 20.00, +53 ms from the decision instant |
| (c) prints on this market in [S-1, S+2) | 21 |
| **(d) settlement, from the INDEX TAPE** | mean of 60 prints = 2.349367 vs effective strike 2.349150 -> `yes` |
| (d) settlement | tape `yes` vs live `yes` -> agree |
| **(e) pinsim.decide, second boundary, today's gate** | **undecided** |
| (e) pinsim.decide at the decision instant | undecided |
| (e) pinsim.decide, second boundary, the gate that was LIVE (PIN 0.9800, ceiling 0.9880) | bought |
| (e) pinsim.decide at the decision instant, the LIVE gate | **bought** |
| **(e) discount to fair we paid** | 3.17c -> pinrun's live 15c guard TODAY: allow; the guard live at the time (-): not logged |
| (e) the backtest profile's rules | trade |
| **(e) FULL backtest verdict (decide + rules), decision ms, today's gate** | **undecided** |
| (e) all size/gate variants at the boundary | now/attempt/s0=undecided, now/gate_size/s0=undecided, now/live_size/s0=undecided, then/attempt/s0=bought, then/gate_size/s0=bought, then/live_size/s0=bought |
| flags | OFFER_MISSING, OFFER_ONLY_SUBSECOND, TS_ORDER_BOOK_DIFFERS_FROM_SEQ_ORDER, BACKTEST_WOULD_NOT_BUY, WHYNOT:undecided, FULL_BACKTEST_WOULD_NOT_BUY |

#### KXNEAR15M-26SEP082045-45  want NO @ 0.7300  x19  P&L -1413.22c

fill second `2026-09-09T00:44:43Z` (S=1788914683), close 2026-09-09T00:45:00Z from markets.json, tau 17s (live logged tau 17, tau_at_send 17), latency 103.0 ms, decision instant S+190 ms (exact).

| | value |
|---|---|
| **(a) fair, live** | `0.00173` |
| (a) fair, replay ticks<=S (what pinsim uses) | `0.00173`  (|d| 0.000003) |
| (a) fair, replay ticks<=S-1 | `0.00373`  (|d| 0.002000) |
| (a) fair, replay ticks by ARRIVAL<=decision instant | `0.00173`  (|d| 0.000003) |
| (a) closest feed | **sec**, |d| 0.000003 within 1e-4 |
| (a) sigma live / replay | `0.00027508` replay vs live `0.00027500` |
| strike live / tape | 2.3492 / 2.3492 |
| **(b) offer we paid** | 0.7300 (model saw 0.7300) |
| (b) our-side ask at START of S (pinsim's view) | 0.9750 x 3.0 |
| (b) our-side ask at END of S | 0.6500 x 60.0 |
| (b) our-side ask at the DECISION INSTANT | 0.7300 x 24.0 |
| (b) offer <= what we paid, at a second boundary? | **YES** |
| (b) offer existed at some ms in [S-1, S+2)? | **YES**, for 1816 ms of 3000 (341 book states checked; best ask seen 0.4200) |
| (b) offer window (the scan covers S-1000 to S+2000) | S+11 ms to S+2000 ms |
| (b) book age at instant: replay / live-logged | 9 ms / 13 ms |
| (b) deltas / snapshots (levelled) on this market this hour | 39,323 / 3 (1) |
| **(c) our fill as a print** | FOUND |
| (c) print | taker no @ 0.7300 x 19.00, +84 ms from the decision instant |
| (c) prints on this market in [S-1, S+2) | 44 |
| **(d) settlement, from the INDEX TAPE** | mean of 60 prints = 2.349367 vs effective strike 2.349150 -> `yes` |
| (d) settlement | tape `yes` vs live `yes` -> agree |
| **(e) pinsim.decide, second boundary, today's gate** | **too_shallow** |
| (e) pinsim.decide at the decision instant | bought |
| (e) pinsim.decide, second boundary, the gate that was LIVE (PIN 0.9800, ceiling 0.9880) | too_shallow |
| (e) pinsim.decide at the decision instant, the LIVE gate | **bought** |
| **(e) discount to fair we paid** | 26.83c -> pinrun's live 15c guard TODAY: **REFUSE**; the guard live at the time (-): not logged |
| (e) the backtest profile's rules | refuse (dump) |
| **(e) FULL backtest verdict (decide + rules), decision ms, today's gate** | **rule:dump** |
| (e) all size/gate variants at the boundary | now/attempt/s0=too_shallow, now/gate_size/s0=too_shallow, now/live_size/s0=too_shallow, then/attempt/s0=too_shallow, then/gate_size/s0=too_shallow, then/live_size/s0=too_shallow |
| flags | TS_ORDER_BOOK_DIFFERS_FROM_SEQ_ORDER, REFUSED_BY_PINRUN_DUMP_GUARD_TODAY, REFUSED_BY_BACKTEST_PROFILE_RULE, BACKTEST_WOULD_NOT_BUY, WHYNOT:too_shallow, FULL_BACKTEST_WOULD_NOT_BUY |

#### KXXRP15M-26SEP100100-00  want YES @ 0.8200  x20  P&L -1660.67c

fill second `2026-09-10T04:59:39Z` (S=1789016379), close 2026-09-10T05:00:00Z from markets.json, tau 21s (live logged tau 21, tau_at_send 21), latency 84.0 ms, decision instant S+180 ms (exact).

| | value |
|---|---|
| **(a) fair, live** | `1.00000` |
| (a) fair, replay ticks<=S (what pinsim uses) | `1.00000`  (|d| 0.000000) |
| (a) fair, replay ticks<=S-1 | `1.00000`  (|d| 0.000000) |
| (a) fair, replay ticks by ARRIVAL<=decision instant | `1.00000`  (|d| 0.000000) |
| (a) closest feed | **sec**, |d| 0.000000 within 1e-4 |
| (a) sigma live / replay | `0.00007859` replay vs live `0.00007900` |
| strike live / tape | 1.3900 / 1.3900 |
| **(b) offer we paid** | 0.8200 (model saw 0.9570) |
| (b) our-side ask at START of S (pinsim's view) | - x 0.0 |
| (b) our-side ask at END of S | 0.5500 x 7.0 |
| (b) our-side ask at the DECISION INSTANT | 0.7400 x 200.0 |
| (b) offer <= what we paid, at a second boundary? | **YES** |
| (b) offer existed at some ms in [S-1, S+2)? | **YES**, for 1700 ms of 3000 (943 book states checked; best ask seen 0.4300) |
| (b) offer window (the scan covers S-1000 to S+2000) | S+170 ms to S+2000 ms |
| (b) book age at instant: replay / live-logged | 1 ms / 2 ms |
| (b) deltas / snapshots (levelled) on this market this hour | 85,342 / 1 (1) |
| **(c) our fill as a print** | FOUND |
| (c) print | taker yes @ 0.8200 x 20.00, +19 ms from the decision instant |
| (c) prints on this market in [S-1, S+2) | 152 |
| **(d) settlement, from the INDEX TAPE** | mean of 60 prints = 1.389796 vs effective strike 1.389950 -> `no` |
| (d) settlement | tape `no` vs live `no` -> agree |
| **(e) pinsim.decide, second boundary, today's gate** | **no_offer** |
| (e) pinsim.decide at the decision instant | bought |
| (e) pinsim.decide, second boundary, the gate that was LIVE (PIN 0.9800, ceiling 0.9800) | no_offer |
| (e) pinsim.decide at the decision instant, the LIVE gate | **bought** |
| **(e) discount to fair we paid** | 18.00c -> pinrun's live 15c guard TODAY: **REFUSE**; the guard live at the time (-): not logged |
| (e) the backtest profile's rules | refuse (dump) |
| **(e) FULL backtest verdict (decide + rules), decision ms, today's gate** | **rule:dump** |
| (e) all size/gate variants at the boundary | now/attempt/s0=no_offer, now/gate_size/s0=no_offer, now/live_size/s0=no_offer, then/attempt/s0=no_offer, then/gate_size/s0=no_offer, then/live_size/s0=no_offer |
| flags | PRICE_DIVERGE_AT_W, REFUSED_BY_PINRUN_DUMP_GUARD_TODAY, REFUSED_BY_BACKTEST_PROFILE_RULE, BACKTEST_WOULD_NOT_BUY, WHYNOT:no_offer, FULL_BACKTEST_WOULD_NOT_BUY |

#### KXBNB15M-26SEP100130-30  want YES @ 0.9400  x18.64  P&L -1759.52c

fill second `2026-09-10T05:29:34Z` (S=1789018174), close 2026-09-10T05:30:00Z from markets.json, tau 26s (live logged tau 26, tau_at_send 26), latency 97.9 ms, decision instant S+220 ms (exact).

| | value |
|---|---|
| **(a) fair, live** | `0.98507` |
| (a) fair, replay ticks<=S (what pinsim uses) | `0.98507`  (|d| 0.000002) |
| (a) fair, replay ticks<=S-1 | `0.92164`  (|d| 0.063433) |
| (a) fair, replay ticks by ARRIVAL<=decision instant | `0.98507`  (|d| 0.000002) |
| (a) closest feed | **sec**, |d| 0.000002 within 1e-4 |
| (a) sigma live / replay | `0.03533889` replay vs live `0.03533900` |
| strike live / tape | 722.5600 / 722.5600 |
| **(b) offer we paid** | 0.9400 (model saw 0.9400) |
| (b) our-side ask at START of S (pinsim's view) | 0.9400 x 0.6 |
| (b) our-side ask at END of S | 0.5000 x 5.0 |
| (b) our-side ask at the DECISION INSTANT | 0.9400 x 18.6 |
| (b) offer <= what we paid, at a second boundary? | **YES** |
| (b) offer existed at some ms in [S-1, S+2)? | **YES**, for 2684 ms of 3000 (381 book states checked; best ask seen 0.4800) |
| (b) offer window (the scan covers S-1000 to S+2000) | S-1000 ms to S+2000 ms |
| (b) book age at instant: replay / live-logged | 0 ms / 2 ms |
| (b) deltas / snapshots (levelled) on this market this hour | 33,024 / 3 (1) |
| **(c) our fill as a print** | FOUND |
| (c) print | taker yes @ 0.9400 x 18.00, +24 ms from the decision instant |
| (c) prints on this market in [S-1, S+2) | 89 |
| **(d) settlement, from the INDEX TAPE** | mean of 60 prints = 722.539683 vs effective strike 722.555000 -> `no` |
| (d) settlement | tape `no` vs live `no` -> agree |
| **(e) pinsim.decide, second boundary, today's gate** | **undecided** |
| (e) pinsim.decide at the decision instant | undecided |
| (e) pinsim.decide, second boundary, the gate that was LIVE (PIN 0.9800, ceiling 0.9800) | too_shallow |
| (e) pinsim.decide at the decision instant, the LIVE gate | **bought** |
| **(e) discount to fair we paid** | 4.51c -> pinrun's live 15c guard TODAY: allow; the guard live at the time (-): not logged |
| (e) the backtest profile's rules | trade |
| **(e) FULL backtest verdict (decide + rules), decision ms, today's gate** | **undecided** |
| (e) all size/gate variants at the boundary | now/attempt/s0=undecided, now/gate_size/s0=undecided, now/live_size/s0=undecided, then/attempt/s0=too_shallow, then/gate_size/s0=too_shallow, then/live_size/s0=too_shallow |
| flags | PINSIM_BOOK_DIFFERS_FROM_SEQ_ORDER, BACKTEST_WOULD_NOT_BUY, WHYNOT:undecided, FULL_BACKTEST_WOULD_NOT_BUY |

#### KXDOGE15M-26SEP101815-15  want NO @ 0.0998  x20  P&L -212.18c

fill second `2026-09-10T22:14:49Z` (S=1789078489), close 2026-09-10T22:15:00Z from markets.json, tau 11s (live logged tau 11, tau_at_send 11), latency 116.4 ms, decision instant S+430 ms (exact).

| | value |
|---|---|
| **(a) fair, live** | `0.00000` |
| (a) fair, replay ticks<=S (what pinsim uses) | `0.00000`  (|d| 0.000000) |
| (a) fair, replay ticks<=S-1 | `0.00000`  (|d| 0.000004) |
| (a) fair, replay ticks by ARRIVAL<=decision instant | `0.00000`  (|d| 0.000000) |
| (a) closest feed | **sec**, |d| 0.000000 within 1e-4 |
| (a) sigma live / replay | `0.00000456` replay vs live `0.00000500` |
| strike live / tape | 0.0840 / 0.0840 |
| **(b) offer we paid** | 0.0998 (model saw 0.5300) |
| (b) our-side ask at START of S (pinsim's view) | 0.9900 x 56.0 |
| (b) our-side ask at END of S | 0.0680 x 68.0 |
| (b) our-side ask at the DECISION INSTANT | 0.1300 x 145.0 |
| (b) offer <= what we paid, at a second boundary? | **YES** |
| (b) offer existed at some ms in [S-1, S+2)? | **YES**, for 1128 ms of 3000 (222 book states checked; best ask seen 0.0310) |
| (b) offer window (the scan covers S-1000 to S+2000) | S+489 ms to S+2000 ms |
| (b) book age at instant: replay / live-logged | 5 ms / 3 ms |
| (b) deltas / snapshots (levelled) on this market this hour | 64,540 / 3 (1) |
| **(c) our fill as a print** | FOUND |
| (c) print | taker no @ 0.1100 x 17.00, +104 ms from the decision instant |
| (c) prints on this market in [S-1, S+2) | 94 |
| **(d) settlement, from the INDEX TAPE** | mean of 60 prints = 0.084036 vs effective strike 0.084023 -> `yes` |
| (d) settlement | tape `yes` vs live `yes` -> agree |
| **(e) pinsim.decide, second boundary, today's gate** | **over_ceiling** |
| (e) pinsim.decide at the decision instant | bought |
| (e) pinsim.decide, second boundary, the gate that was LIVE (PIN 0.9950, ceiling 0.9800) | over_ceiling |
| (e) pinsim.decide at the decision instant, the LIVE gate | **bought** |
| **(e) discount to fair we paid** | 90.02c -> pinrun's live 15c guard TODAY: **REFUSE**; the guard live at the time (-): not logged |
| (e) the backtest profile's rules | refuse (dump) |
| **(e) FULL backtest verdict (decide + rules), decision ms, today's gate** | **rule:dump** |
| (e) all size/gate variants at the boundary | now/attempt/s0=over_ceiling, now/gate_size/s0=over_ceiling, now/live_size/s0=too_shallow, then/attempt/s0=over_ceiling, then/gate_size/s0=over_ceiling, then/live_size/s0=too_shallow |
| flags | PRICE_DIVERGE_AT_W, TS_ORDER_BOOK_DIFFERS_FROM_SEQ_ORDER, REFUSED_BY_PINRUN_DUMP_GUARD_TODAY, REFUSED_BY_BACKTEST_PROFILE_RULE, BACKTEST_WOULD_NOT_BUY, WHYNOT:over_ceiling, FULL_BACKTEST_WOULD_NOT_BUY |

#### KXSOL15M-26SEP110830-30  want NO @ 0.5910  x20  P&L -1215.85c

fill second `2026-09-11T12:29:30Z` (S=1789129770), close 2026-09-11T12:30:00Z from markets.json, tau 30s (live logged tau 30, tau_at_send 30), latency 96.1 ms, decision instant S+280 ms (exact).

| | value |
|---|---|
| **(a) fair, live** | `0.00492` |
| (a) fair, replay ticks<=S (what pinsim uses) | `0.00492`  (|d| 0.000004) |
| (a) fair, replay ticks<=S-1 | `0.00002`  (|d| 0.004900) |
| (a) fair, replay ticks by ARRIVAL<=decision instant | `0.00492`  (|d| 0.000004) |
| (a) closest feed | **sec**, |d| 0.000004 within 1e-4 |
| (a) sigma live / replay | `0.01037327` replay vs live `0.01037300` |
| strike live / tape | 99.3065 / 99.3065 |
| **(b) offer we paid** | 0.5910 (model saw 0.7000) |
| (b) our-side ask at START of S (pinsim's view) | 0.9950 x 130.0 |
| (b) our-side ask at END of S | 0.7900 x 200.0 |
| (b) our-side ask at the DECISION INSTANT | 0.5100 x 200.0 |
| (b) offer <= what we paid, at a second boundary? | **NO -- OFFER MISSING** |
| (b) offer existed at some ms in [S-1, S+2)? | **YES**, for 818 ms of 3000 (641 book states checked; best ask seen 0.1800) |
| (b) offer window (the scan covers S-1000 to S+2000) | S+274 ms to S+2000 ms |
| (b) book age at instant: replay / live-logged | 1 ms / 5 ms |
| (b) deltas / snapshots (levelled) on this market this hour | 64,268 / 3 (1) |
| **(c) our fill as a print** | FOUND |
| (c) print | taker no @ 0.5900 x 18.00, +87 ms from the decision instant |
| (c) prints on this market in [S-1, S+2) | 170 |
| **(d) settlement, from the INDEX TAPE** | mean of 60 prints = 99.473833 vs effective strike 99.306450 -> `yes` |
| (d) settlement | tape `yes` vs live `yes` -> agree |
| **(e) pinsim.decide, second boundary, today's gate** | **over_ceiling** |
| (e) pinsim.decide at the decision instant | bought |
| (e) pinsim.decide, second boundary, the gate that was LIVE (PIN 0.9950, ceiling 0.9800) | over_ceiling |
| (e) pinsim.decide at the decision instant, the LIVE gate | **bought** |
| **(e) discount to fair we paid** | 40.41c -> pinrun's live 15c guard TODAY: **REFUSE**; the guard live at the time (-): not logged |
| (e) the backtest profile's rules | refuse (dump) |
| **(e) FULL backtest verdict (decide + rules), decision ms, today's gate** | **rule:dump** |
| (e) all size/gate variants at the boundary | now/attempt/s0=over_ceiling, now/gate_size/s0=over_ceiling, now/live_size/s0=over_ceiling, then/attempt/s0=over_ceiling, then/gate_size/s0=over_ceiling, then/live_size/s0=over_ceiling |
| flags | OFFER_MISSING, OFFER_ONLY_SUBSECOND, PRICE_DIVERGE_AT_W, TS_ORDER_BOOK_DIFFERS_FROM_SEQ_ORDER, REFUSED_BY_PINRUN_DUMP_GUARD_TODAY, REFUSED_BY_BACKTEST_PROFILE_RULE, BACKTEST_WOULD_NOT_BUY, WHYNOT:over_ceiling, FULL_BACKTEST_WOULD_NOT_BUY |

#### KXSOL15M-26SEP112300-00  want NO @ 0.9790  x20  P&L -1960.88c

fill second `2026-09-12T02:59:31Z` (S=1789181971), close 2026-09-12T03:00:00Z from markets.json, tau 29s (live logged tau 29, tau_at_send 29), latency 90.2 ms, decision instant S+250 ms (exact).

| | value |
|---|---|
| **(a) fair, live** | `0.00032` |
| (a) fair, replay ticks<=S (what pinsim uses) | `0.00032`  (|d| 0.000002) |
| (a) fair, replay ticks<=S-1 | `0.00059`  (|d| 0.000270) |
| (a) fair, replay ticks by ARRIVAL<=decision instant | `0.00032`  (|d| 0.000002) |
| (a) closest feed | **sec**, |d| 0.000002 within 1e-4 |
| (a) sigma live / replay | `0.00428968` replay vs live `0.00429000` |
| strike live / tape | 101.6945 / 101.6945 |
| **(b) offer we paid** | 0.9790 (model saw 0.9790) |
| (b) our-side ask at START of S (pinsim's view) | 0.9730 x 0.9 |
| (b) our-side ask at END of S | 0.9790 x 283.0 |
| (b) our-side ask at the DECISION INSTANT | 0.9790 x 207.0 |
| (b) offer <= what we paid, at a second boundary? | **YES** |
| (b) offer existed at some ms in [S-1, S+2)? | **YES**, for 2994 ms of 3000 (297 book states checked; best ask seen 0.9670) |
| (b) offer window (the scan covers S-1000 to S+2000) | S-1000 ms to S+2000 ms |
| (b) book age at instant: replay / live-logged | 15 ms / 26 ms |
| (b) deltas / snapshots (levelled) on this market this hour | 47,544 / 1 (1) |
| **(c) our fill as a print** | FOUND |
| (c) print | taker no @ 0.9780 x 16.00, -62 ms from the decision instant |
| (c) prints on this market in [S-1, S+2) | 57 |
| **(d) settlement, from the INDEX TAPE** | mean of 60 prints = 101.713667 vs effective strike 101.694450 -> `yes` |
| (d) settlement | tape `yes` vs live `yes` -> agree |
| **(e) pinsim.decide, second boundary, today's gate** | **too_shallow** |
| (e) pinsim.decide at the decision instant | bought |
| (e) pinsim.decide, second boundary, the gate that was LIVE (PIN 0.9950, ceiling 0.9800) | too_shallow |
| (e) pinsim.decide at the decision instant, the LIVE gate | **bought** |
| **(e) discount to fair we paid** | 2.07c -> pinrun's live 15c guard TODAY: allow; the guard live at the time (0.1500): allow |
| (e) the backtest profile's rules | trade |
| **(e) FULL backtest verdict (decide + rules), decision ms, today's gate** | **bought** |
| (e) all size/gate variants at the boundary | now/attempt/s0=too_shallow, now/gate_size/s0=too_shallow, now/live_size/s0=too_shallow, then/attempt/s0=too_shallow, then/gate_size/s0=too_shallow, then/live_size/s0=too_shallow |
| flags | BACKTEST_WOULD_NOT_BUY, WHYNOT:too_shallow, FULL_BACKTEST_WOULD_NOT_BUY |

#### KXSOL15M-26SEP120400-00  want YES @ 0.9400  x20  P&L -1887.90c

fill second `2026-09-12T07:59:41Z` (S=1789199981), close 2026-09-12T08:00:00Z from ticker-suffix-ET, tau 19s (live logged tau 19, tau_at_send 19), latency 85.1 ms, decision instant S+70 ms (exact).

| | value |
|---|---|
| **(a) fair, live** | `0.99764` |
| (a) fair, replay ticks<=S (what pinsim uses) | `0.99764`  (|d| 0.000002) |
| (a) fair, replay ticks<=S-1 | `0.94057`  (|d| 0.057074) |
| (a) fair, replay ticks by ARRIVAL<=decision instant | `0.99764`  (|d| 0.000002) |
| (a) closest feed | **sec**, |d| 0.000002 within 1e-4 |
| (a) sigma live / replay | `0.00356843` replay vs live `0.00356800` |
| strike live / tape | 101.6700 / 101.6700 |
| **(b) offer we paid** | 0.9400 (model saw 0.9400) |
| (b) our-side ask at START of S (pinsim's view) | 0.9380 x 25.0 |
| (b) our-side ask at END of S | 0.8800 x 25.0 |
| (b) our-side ask at the DECISION INSTANT | 0.9400 x 180.0 |
| (b) offer <= what we paid, at a second boundary? | **YES** |
| (b) offer existed at some ms in [S-1, S+2)? | **YES**, for 2959 ms of 3000 (606 book states checked; best ask seen 0.7700) |
| (b) offer window (the scan covers S-1000 to S+2000) | S-1000 ms to S+1985 ms |
| (b) book age at instant: replay / live-logged | 2 ms / 3 ms |
| (b) deltas / snapshots (levelled) on this market this hour | 58,914 / 1 (1) |
| **(c) our fill as a print** | FOUND |
| (c) print | taker yes @ 0.9400 x 20.00, -9 ms from the decision instant |
| (c) prints on this market in [S-1, S+2) | 118 |
| **(d) settlement, from the INDEX TAPE** | mean of 60 prints = 101.663500 vs effective strike 101.669950 -> `no` |
| (d) settlement | tape `-` vs live `no` -> no tape settlement yet |
| **(e) pinsim.decide, second boundary, today's gate** | **bought** |
| (e) pinsim.decide at the decision instant | bought |
| (e) pinsim.decide, second boundary, the gate that was LIVE (PIN 0.9950, ceiling 0.9800) | bought |
| (e) pinsim.decide at the decision instant, the LIVE gate | **bought** |
| **(e) discount to fair we paid** | 5.76c -> pinrun's live 15c guard TODAY: allow; the guard live at the time (0.1500): allow |
| (e) the backtest profile's rules | trade |
| **(e) FULL backtest verdict (decide + rules), decision ms, today's gate** | **bought** |
| (e) all size/gate variants at the boundary | now/attempt/s0=bought, now/gate_size/s0=bought, now/live_size/s0=too_shallow, then/attempt/s0=bought, then/gate_size/s0=bought, then/live_size/s0=too_shallow |
| flags | NO_TAPE_SETTLEMENT |

## DIAGNOSIS

**The model is not the problem and neither is the tape.** The replayed index reproduces the `fair` the live bot logged on **191 of 195** fills to within 1e-4; our own fill is on the trade tape as a print with the right taker side, price and size on **181 of 195**; and the settlement recomputed from the sixty index prints agrees with the outcome we booked on **184 of 195**. The offer we hit exists in the rebuilt book at some millisecond on **195 of 195** fills -- it is NOT invisible. What breaks is WHEN the book is read and WHICH RULE reads it. Reconstructed on the exchange's `seq` and evaluated at the millisecond the live bot decided, the book shows exactly the price we paid on **151 of 195**; evaluated at the second boundary, which is what `pinsim.run()` does, it shows it on **76 of 195** and holds an offer at or better than we paid on 165 against 154 at the decision instant. Then the rule layer: the existing backtest, run at the second boundary under today's constants, would have bought **102 of 195** of our own fills -- the dominant refusal is `undecided` on 42 of them, then `too_shallow` on 29. Move only the sampling to the decision millisecond and it buys **121**; put back the gate that was actually live for each fill and it buys **160 of 195**. **On the 9 fills that LOST money the same backtest buys 1**, refusing the rest as `undecided` x3, `too_shallow` x2, `over_ceiling` x2, `no_offer` x1. That is the answer to why the backtest does not show our losses: not a blind book and not a broken model, but a once-a-second sample of a book that changes ~102 times a second, judged by a gate that has since been tightened past the trades it is being asked to reproduce.
