# RESULTS_replay_rebuild -- the backtest rebuilt so that it takes our own trades

`research/pinsim.py`, rebuilt and measured 2026-09-12T14:48:49Z. The diagnosis this answers is `results/RESULTS_replay.md`.

**The operator's instruction:** *"remake the way that you backtest... Don't stop until you can backtest our last trade and get the same results. I want to see more losses because we actually have losses... It should replicate exactly what would happen if it was live."*

Every number below is measured against **210 real fills** read out of `results/pinrun-live-*.jsonl` -- orders the bot actually got filled on -- over 162 closes and 205 markets. **9 of them lost money.** No simulated fill and no tape-derived loss rate appears anywhere in this file. (CLAUDE.md, amendment 2026-09-10, rule 5: a loss rate about US comes from live fills only.)

## THE HEADLINE: the old backtest reproduced our WINS five times better than our LOSSES, and that asymmetry is now gone

At the millisecond we actually decided, with the book merged in the exchange's own order, pinsim's book holds the exact price our model logged on:

| | old book, once a second | new book, at the decision ms |
|---|---|---|
| the 201 fills that WON | 69/201 (34.3%) | 152/201 (75.6%) |
| the 9 fills that LOST | 0/9 (0.0%) | 6/9 (66.7%) |
| would `decide` have bought it -- WON | 111/201 (55.2%) | 133/201 (66.2%) |
| would `decide` have bought it -- LOST | 1/9 (11.1%) | 6/9 (66.7%) |

**That is the whole answer to "the backtest never shows our losses".** It was not a blind book and not a broken model: it was a once-a-second sample of a book that changes ~100 times a second, and the offers that hurt us are exactly the ones that do not survive a second. Where the offer was visible at all it was on the book for a median of 1,383 ms of a 3,000 ms window (`RESULTS_replay.md`). A sampler that looks once per second therefore misses adversely-selected fills preferentially -- and adversely-selected fills are the losing ones. With the rebuild the two populations are reproduced at the same rate, which is what a faithful replay must do. **`n` on the losing side is 9 fills; treat the loss column as a direction, not a rate.**

## What changed in pinsim.py

| | before | after | the self-test that holds it |
|---|---|---|---|
| **the book** | every `orderbook_snapshot` in the hour applied BEFORE any delta, stamped ts 0 (the reader looked for `ts_ms`, which is on 0% of snapshot records) | both channels merged into ONE stream in the exchange's own `seq` order (`EventStream`), each snapshot at its real position and its real `_rx_ms` | a snapshot planted mid-stream WIPES the level that preceded it and keeps the delta that followed it; the old order leaves that level standing |
| **snapshot clock** | 0 | `_rx_ms`, clamped down to the `ts_ms` of the delta it precedes so the merge's clock cannot run backwards | the snapshot event's ts is `+50 ms`, not 0; a receipt at `+900` is clamped to `+100` |
| **when it decides** | once a second, at the first event of the second | after EVERY book event on a tracked market in `[TAU_MIN, TAU_MAX]`, plus the once-a-second sweep so a quiet market is still re-checked (`Walk`) | an offer alive for 400 ms inside one second IS bought, at S+300 ms; the same tape sampled once a second misses it entirely |
| **the index** | fed to the second boundary | fed to the event's millisecond, and the clock it measures its own age against is fractional, as live's `time.time()` is (`feed_upto_ms`) | an event at S+440 ms sees the print stamped S and NOT the one stamped S+1 |
| **the gate** | today's constants, always | `--gate-from <pinrun-live-*.jsonl>` replays the gate that run was STARTED with | a planted `start` record moves `pinrun.PIN` to 0.98 and puts it back |

`pinsim.decide` itself is untouched: it still calls `pinrun.fair`, `net_edge`, `expected_value`, `billed_fee` and reads `pinrun`'s own constants, and `TapeIndex.partial`/`sigma` are still pinrun's own methods (the self-test asserts identity). **Nothing about the decision moved. What moved is the book it reads, the instant it reads it, and the gate it is judged by.**

## ACCEPTANCE -- (1) does pinsim's book hold the offer we hit

The live `signal` record logs the exact price the bot saw on our side. That is the ground truth for a book rebuild.

| pinsim's book, read at | == the price the live model logged |
|---|---|
| **snapshots-first, the first event of second S -- WHAT PINSIM DID (BEFORE)** | 69/210 (32.9%) |
| seq order, the first event of second S | 79/210 (37.6%) |
| seq order, the end of second S-1 (pinreplay's "start of second S") | 79/210 (37.6%) |
| **seq order, the DECISION MILLISECOND -- WHAT PINSIM DOES NOW (AFTER)** | 158/210 (75.2%) |

This is the same measurement `results/RESULTS_replay.md` makes with its OWN, independently written reconstruction, and the two agree: snapshots-first 68/207 and seq-at-the-decision-millisecond 156/207 there, 69/210 and 158/210 here on 210 fills. Two implementations of the merge, written separately, land on the same number. On one full hour (20260912T02, KXSOL15M-26SEP112300-00, 47,545 events) the two event streams are **identical tuple for tuple**.

## ACCEPTANCE -- (2) would pinsim have bought THIS fill

`pinsim.decide` is CALLED here, never reimplemented. Size is the size of the order we actually sent. Only two things vary: WHICH BOOK and WHICH GATE.

| book | read at | gate | would have bought | top refusals |
|---|---|---|---|---|
| **snapshots-first** | first event of S | today | **112/210 (53.3%)** | `undecided` 42, `too_shallow` 34, `over_ceiling` 21, `no_offer` 1 |
| **seq order** | **decision ms** | today | **139/210 (66.2%)** | `undecided` 42, `too_shallow` 17, `over_ceiling` 12 |
| snapshots-first | first event of S | the one that was LIVE | **143/210 (68.1%)** | `too_shallow` 42, `over_ceiling` 21, `undecided` 2, `no_edge` 1, `no_offer` 1 |
| **seq order** | **decision ms** | **the one that was LIVE** | **180/210 (85.7%)** | `too_shallow` 17, `over_ceiling` 11, `undecided` 2 |

The same four cells in `RESULTS_replay.md`, measured by the other harness, are 112/207, 137/207, 147/207 and 178/207.

## ACCEPTANCE -- (3) would pinsim have bought this MARKET

(2) asks a narrow question: at the exact millisecond we decided, does the backtest agree? (3) asks the operator's question: run the backtest over the market's whole `[TAU_MIN, TAU_MAX]` window, as `run()` does, and does it take the trade at all? `run()` takes the FIRST moment that passes and then marks the market decided, so several fills on one market can be reproduced at most once.

| sampling | book | gate | market bought | at the price we paid | traded after the profile's rules |
|---|---|---|---|---|---|
| **once a second** | **snapshots-first** | today | **171/210 (81.4%)** | 55/210 (26.2%) | 159 |
| **every event** | **seq order** | today | **182/210 (86.7%)** | 62/210 (29.5%) | 170 |
| once a second | snapshots-first | the one that was LIVE | **183/210 (87.1%)** | 64/210 (30.5%) | 172 |
| **every event** | **seq order** | **the one that was LIVE** | **190/210 (90.5%)** | 73/210 (34.8%) | 179 |


## The losing fills, and the winning fills as a control

### THE LOSING FILLS -- n = 9

| pinsim's book, read at | == the price the live model logged |
|---|---|
| **snapshots-first, the first event of second S -- WHAT PINSIM DID (BEFORE)** | 0/9 (0.0%) |
| seq order, the first event of second S | 1/9 (11.1%) |
| seq order, the end of second S-1 (pinreplay's "start of second S") | 1/9 (11.1%) |
| **seq order, the DECISION MILLISECOND -- WHAT PINSIM DOES NOW (AFTER)** | 6/9 (66.7%) |

| book | read at | gate | would have bought | top refusals |
|---|---|---|---|---|
| **snapshots-first** | first event of S | today | **1/9 (11.1%)** | `undecided` 3, `too_shallow` 2, `over_ceiling` 2, `no_offer` 1 |
| **seq order** | **decision ms** | today | **6/9 (66.7%)** | `undecided` 3 |
| snapshots-first | first event of S | the one that was LIVE | **3/9 (33.3%)** | `too_shallow` 3, `over_ceiling` 2, `no_offer` 1 |
| **seq order** | **decision ms** | **the one that was LIVE** | **9/9 (100.0%)** |  |

| sampling | book | gate | market bought | at the price we paid | traded after the profile's rules |
|---|---|---|---|---|---|
| **once a second** | **snapshots-first** | today | **9/9 (100.0%)** | 1/9 (11.1%) | 8 |
| **every event** | **seq order** | today | **9/9 (100.0%)** | 1/9 (11.1%) | 9 |
| once a second | snapshots-first | the one that was LIVE | **9/9 (100.0%)** | 1/9 (11.1%) | 8 |
| **every event** | **seq order** | **the one that was LIVE** | **9/9 (100.0%)** | 2/9 (22.2%) | 9 |

### THE WINNING FILLS (control) -- n = 201

| pinsim's book, read at | == the price the live model logged |
|---|---|
| **snapshots-first, the first event of second S -- WHAT PINSIM DID (BEFORE)** | 69/201 (34.3%) |
| seq order, the first event of second S | 78/201 (38.8%) |
| seq order, the end of second S-1 (pinreplay's "start of second S") | 78/201 (38.8%) |
| **seq order, the DECISION MILLISECOND -- WHAT PINSIM DOES NOW (AFTER)** | 152/201 (75.6%) |

| book | read at | gate | would have bought | top refusals |
|---|---|---|---|---|
| **snapshots-first** | first event of S | today | **111/201 (55.2%)** | `undecided` 39, `too_shallow` 32, `over_ceiling` 19 |
| **seq order** | **decision ms** | today | **133/201 (66.2%)** | `undecided` 39, `too_shallow` 17, `over_ceiling` 12 |
| snapshots-first | first event of S | the one that was LIVE | **140/201 (69.7%)** | `too_shallow` 39, `over_ceiling` 19, `undecided` 2, `no_edge` 1 |
| **seq order** | **decision ms** | **the one that was LIVE** | **171/201 (85.1%)** | `too_shallow` 17, `over_ceiling` 11, `undecided` 2 |

| sampling | book | gate | market bought | at the price we paid | traded after the profile's rules |
|---|---|---|---|---|---|
| **once a second** | **snapshots-first** | today | **162/201 (80.6%)** | 54/201 (26.9%) | 151 |
| **every event** | **seq order** | today | **173/201 (86.1%)** | 61/201 (30.3%) | 161 |
| once a second | snapshots-first | the one that was LIVE | **174/201 (86.6%)** | 63/201 (31.3%) | 164 |
| **every event** | **seq order** | **the one that was LIVE** | **181/201 (90.0%)** | 71/201 (35.3%) | 170 |

## The nine losses, one by one

### KXNEAR15M-26SEP082045-45  no @ 0.9620 x20  P&L -1929.12c

Fill second 2026-09-09T00:44:38Z, close 00:45:00Z, gate that was live PIN 0.98 / ceiling 0.988 (`pinrun-live-20260909T000027Z.jsonl`). The live model logged the offer at **0.962**. 39,326 book events on this market in the hour.

| | |
|---|---|
| our-side ask, snapshots-first @ the first event of S (BEFORE) | `0.909` |
| our-side ask, seq @ the first event of S | `0.909` |
| **our-side ask, seq @ the decision ms (AFTER)** | `0.962` |
| WALK, once a second + snapshots-first, gate today (BEFORE) | **bought no @ 0.9730 x20 at tau 18, S+4000 ms**, fair 0.00373, rules `trade` |
| **WALK, every event + seq, gate today** | **bought no @ 0.9730 x20 at tau 18, S+4000 ms**, fair 0.00373, rules `trade` |
| **WALK, every event + seq, the gate that was LIVE** | **bought no @ 0.9090 x20 at tau 22, S+0 ms**, fair 0.01826, rules `trade` |
| decide @ the first event of S, snapshots-first, gate today (BEFORE) | `undecided` |
| decide @ the decision ms, seq, gate today | `undecided` |
| **decide @ the decision ms, seq, the gate that was LIVE** | **bought @ 0.962** |

### KXNEAR15M-26SEP082045-45  no @ 0.9560 x20  P&L -1917.89c

Fill second 2026-09-09T00:44:39Z, close 00:45:00Z, gate that was live PIN 0.98 / ceiling 0.988 (`pinrun-live-20260909T000027Z.jsonl`). The live model logged the offer at **0.956**. 39,326 book events on this market in the hour.

| | |
|---|---|
| our-side ask, snapshots-first @ the first event of S (BEFORE) | `0.962` |
| our-side ask, seq @ the first event of S | `0.962` |
| **our-side ask, seq @ the decision ms (AFTER)** | `0.956` |
| WALK, once a second + snapshots-first, gate today (BEFORE) | **bought no @ 0.9730 x20 at tau 18, S+3000 ms**, fair 0.00373, rules `trade` |
| **WALK, every event + seq, gate today** | **bought no @ 0.9730 x20 at tau 18, S+3000 ms**, fair 0.00373, rules `trade` |
| **WALK, every event + seq, the gate that was LIVE** | **bought no @ 0.9090 x20 at tau 22, S-1000 ms**, fair 0.01826, rules `trade` |
| decide @ the first event of S, snapshots-first, gate today (BEFORE) | `undecided` |
| decide @ the decision ms, seq, gate today | `undecided` |
| **decide @ the decision ms, seq, the gate that was LIVE** | **bought @ 0.956** |

### KXNEAR15M-26SEP082045-45  no @ 0.7300 x19  P&L -1413.22c

Fill second 2026-09-09T00:44:43Z, close 00:45:00Z, gate that was live PIN 0.98 / ceiling 0.988 (`pinrun-live-20260909T000027Z.jsonl`). The live model logged the offer at **0.73**. 39,326 book events on this market in the hour.

| | |
|---|---|
| our-side ask, snapshots-first @ the first event of S (BEFORE) | `0.975` |
| our-side ask, seq @ the first event of S | `0.975` |
| **our-side ask, seq @ the decision ms (AFTER)** | `0.73` |
| WALK, once a second + snapshots-first, gate today (BEFORE) | **bought no @ 0.9730 x19 at tau 18, S-1000 ms**, fair 0.00373, rules `trade` |
| **WALK, every event + seq, gate today** | **bought no @ 0.9730 x19 at tau 18, S-1000 ms**, fair 0.00373, rules `trade` |
| **WALK, every event + seq, the gate that was LIVE** | **bought no @ 0.9090 x19 at tau 22, S-5000 ms**, fair 0.01826, rules `trade` |
| decide @ the first event of S, snapshots-first, gate today (BEFORE) | `too_shallow` |
| decide @ the decision ms, seq, gate today | **bought @ 0.73** |
| **decide @ the decision ms, seq, the gate that was LIVE** | **bought @ 0.73** |

### KXXRP15M-26SEP100100-00  yes @ 0.8200 x20  P&L -1660.67c

Fill second 2026-09-10T04:59:39Z, close 05:00:00Z, gate that was live PIN 0.98 / ceiling 0.98 (`pinrun-live-20260909T214302Z.jsonl`). The live model logged the offer at **0.957** and we paid 0.8200 (an IOC sweep's VWAP, which is not a level price). 85,343 book events on this market in the hour.

| | |
|---|---|
| our-side ask, snapshots-first @ the first event of S (BEFORE) | `None` |
| our-side ask, seq @ the first event of S | `None` |
| **our-side ask, seq @ the decision ms (AFTER)** | `0.74` |
| WALK, once a second + snapshots-first, gate today (BEFORE) | **bought no @ 0.8400 x15 at tau 14, S+7000 ms**, fair 0.00137, rules `trade` |
| **WALK, every event + seq, gate today** | **bought yes @ 0.9570 x20 at tau 21, S+108 ms**, fair 1.00000, rules `trade` |
| **WALK, every event + seq, the gate that was LIVE** | **bought yes @ 0.9570 x20 at tau 21, S+108 ms**, fair 1.00000, rules `trade` |
| decide @ the first event of S, snapshots-first, gate today (BEFORE) | `no_offer` |
| decide @ the decision ms, seq, gate today | **bought @ 0.74** |
| **decide @ the decision ms, seq, the gate that was LIVE** | **bought @ 0.74** |

### KXBNB15M-26SEP100130-30  yes @ 0.9400 x18.64  P&L -1759.52c

Fill second 2026-09-10T05:29:34Z, close 05:30:00Z, gate that was live PIN 0.98 / ceiling 0.98 (`pinrun-live-20260909T214302Z.jsonl`). The live model logged the offer at **0.94**. 33,027 book events on this market in the hour.

| | |
|---|---|
| our-side ask, snapshots-first @ the first event of S (BEFORE) | `0.941` |
| our-side ask, seq @ the first event of S | `0.94` |
| **our-side ask, seq @ the decision ms (AFTER)** | `0.94` |
| WALK, once a second + snapshots-first, gate today (BEFORE) | **bought no @ 0.9280 x18.64 at tau 6, S+20000 ms**, fair 0.00488, rules `trade` |
| **WALK, every event + seq, gate today** | **bought no @ 0.9280 x18.64 at tau 6, S+20000 ms**, fair 0.00488, rules `trade` |
| **WALK, every event + seq, the gate that was LIVE** | **bought yes @ 0.9400 x18.64 at tau 26, S+137 ms**, fair 0.98507, rules `trade` |
| decide @ the first event of S, snapshots-first, gate today (BEFORE) | `undecided` |
| decide @ the decision ms, seq, gate today | `undecided` |
| **decide @ the decision ms, seq, the gate that was LIVE** | **bought @ 0.94** |

### KXDOGE15M-26SEP101815-15  no @ 0.0998 x20  P&L -212.18c

Fill second 2026-09-10T22:14:49Z, close 22:15:00Z, gate that was live PIN 0.995 / ceiling 0.98 (`pinrun-live-20260910T083328Z.jsonl`). The live model logged the offer at **0.53** and we paid 0.0998 (an IOC sweep's VWAP, which is not a level price). 64,543 book events on this market in the hour.

| | |
|---|---|
| our-side ask, snapshots-first @ the first event of S (BEFORE) | `0.99` |
| our-side ask, seq @ the first event of S | `0.99` |
| **our-side ask, seq @ the decision ms (AFTER)** | `0.13` |
| WALK, once a second + snapshots-first, gate today (BEFORE) | **bought no @ 0.9740 x20 at tau 17, S-5999 ms**, fair 0.00447, rules `trade` |
| **WALK, every event + seq, gate today** | **bought no @ 0.9740 x20 at tau 17, S-5999 ms**, fair 0.00447, rules `trade` |
| **WALK, every event + seq, the gate that was LIVE** | **bought no @ 0.9740 x20 at tau 17, S-5999 ms**, fair 0.00447, rules `trade` |
| decide @ the first event of S, snapshots-first, gate today (BEFORE) | `over_ceiling` |
| decide @ the decision ms, seq, gate today | **bought @ 0.13** |
| **decide @ the decision ms, seq, the gate that was LIVE** | **bought @ 0.13** |

### KXSOL15M-26SEP110830-30  no @ 0.5910 x20  P&L -1215.85c

Fill second 2026-09-11T12:29:30Z, close 12:30:00Z, gate that was live PIN 0.995 / ceiling 0.98 (`pinrun-live-20260911T001200Z.jsonl`). The live model logged the offer at **0.7** and we paid 0.5910 (an IOC sweep's VWAP, which is not a level price). 64,271 book events on this market in the hour.

| | |
|---|---|
| our-side ask, snapshots-first @ the first event of S (BEFORE) | `0.995` |
| our-side ask, seq @ the first event of S | `0.995` |
| **our-side ask, seq @ the decision ms (AFTER)** | `0.51` |
| WALK, once a second + snapshots-first, gate today (BEFORE) | **bought yes @ 0.9200 x20 at tau 27, S+3000 ms**, fair 0.99944, rules `refuse` ['dump'] |
| **WALK, every event + seq, gate today** | **bought no @ 0.9800 x17 at tau 30, S+228 ms**, fair 0.00492, rules `trade` |
| **WALK, every event + seq, the gate that was LIVE** | **bought no @ 0.9800 x17 at tau 30, S+228 ms**, fair 0.00492, rules `trade` |
| decide @ the first event of S, snapshots-first, gate today (BEFORE) | `over_ceiling` |
| decide @ the decision ms, seq, gate today | **bought @ 0.51** |
| **decide @ the decision ms, seq, the gate that was LIVE** | **bought @ 0.51** |

### KXSOL15M-26SEP112300-00  no @ 0.9790 x20  P&L -1960.88c

Fill second 2026-09-12T02:59:31Z, close 03:00:00Z, gate that was live PIN 0.995 / ceiling 0.98 (`pinrun-live-20260912T022339Z.jsonl`). The live model logged the offer at **0.979**. 47,545 book events on this market in the hour.

| | |
|---|---|
| our-side ask, snapshots-first @ the first event of S (BEFORE) | `0.973` |
| our-side ask, seq @ the first event of S | `0.973` |
| **our-side ask, seq @ the decision ms (AFTER)** | `0.979` |
| WALK, once a second + snapshots-first, gate today (BEFORE) | **bought no @ 0.9790 x20 at tau 28, S+1000 ms**, fair 0.00016, rules `trade` |
| **WALK, every event + seq, gate today** | **bought no @ 0.9700 x12 at tau 30, S-862 ms**, fair 0.00059, rules `trade` |
| **WALK, every event + seq, the gate that was LIVE** | **bought no @ 0.9700 x12 at tau 30, S-862 ms**, fair 0.00059, rules `trade` |
| decide @ the first event of S, snapshots-first, gate today (BEFORE) | `too_shallow` |
| decide @ the decision ms, seq, gate today | **bought @ 0.979** |
| **decide @ the decision ms, seq, the gate that was LIVE** | **bought @ 0.979** |

### KXSOL15M-26SEP120400-00  yes @ 0.9400 x20  P&L -1887.90c

Fill second 2026-09-12T07:59:41Z, close 08:00:00Z, gate that was live PIN 0.995 / ceiling 0.98 (`pinrun-live-20260912T033347Z.jsonl`). The live model logged the offer at **0.94**. 58,915 book events on this market in the hour.

| | |
|---|---|
| our-side ask, snapshots-first @ the first event of S (BEFORE) | `0.938` |
| our-side ask, seq @ the first event of S | `0.938` |
| **our-side ask, seq @ the decision ms (AFTER)** | `0.94` |
| WALK, once a second + snapshots-first, gate today (BEFORE) | **bought yes @ 0.9380 x20 at tau 19, S+0 ms**, fair 0.99764, rules `trade` |
| **WALK, every event + seq, gate today** | **bought yes @ 0.9380 x20 at tau 19, S+0 ms**, fair 0.99764, rules `trade` |
| **WALK, every event + seq, the gate that was LIVE** | **bought yes @ 0.9380 x20 at tau 19, S+0 ms**, fair 0.99764, rules `trade` |
| decide @ the first event of S, snapshots-first, gate today (BEFORE) | **bought @ 0.938** |
| decide @ the decision ms, seq, gate today | **bought @ 0.94** |
| **decide @ the decision ms, seq, the gate that was LIVE** | **bought @ 0.94** |

## The operator's literal test: `pinsim.py --gate-from` on the exact windows of the nine losses

`pinreplay.py` builds its own book, so its table (e) cannot move when pinsim's book changes. So the backtest itself is run, through its own CLI, one book hour at a time, under the gate that was live for that fill. A bought loser prints as a `LOSS <ticker>` line in `report()`, so that line is the evidence -- and its absence is recorded too.

| book hour | gate from | the market we lost on | the `LOSS` line the backtest printed for it | other losses the same hour printed | s |
|---|---|---|---|---|---|
| `20260909T00` | `pinrun-live-20260909T000027Z.jsonl` | `KXNEAR15M-26SEP082045-45` | `LOSS KXNEAR15M-26SEP082045-45       no  90.9c tau 22 $-18.30` | -- | 51 |
| `20260910T04` | `pinrun-live-20260909T214302Z.jsonl` | `KXXRP15M-26SEP100100-00` | `LOSS KXXRP15M-26SEP100100-00       yes  95.7c tau 21 $-19.20` | -- | 59 |
| `20260910T05` | `pinrun-live-20260909T214302Z.jsonl` | `KXBNB15M-26SEP100130-30` | `LOSS KXBNB15M-26SEP100130-30       yes  94.0c tau 26 $-17.60` | -- | 56 |
| `20260910T22` | `pinrun-live-20260910T083328Z.jsonl` | `KXDOGE15M-26SEP101815-15` | `LOSS KXDOGE15M-26SEP101815-15       no  97.4c tau 17 $-19.52` | -- | 57 |
| `20260911T12` | `pinrun-live-20260911T001200Z.jsonl` | `KXSOL15M-26SEP110830-30` | `LOSS KXSOL15M-26SEP110830-30        no  98.0c tau 30 $-16.68` | `LOSS KXXRP15M-26SEP110830-30        no  97.7c tau 30 $-19.57`<br>`LOSS KXBNB15M-26SEP110830-30        no  97.6c tau 30 $-19.55`<br>`LOSS KXDOGE15M-26SEP110830-30       no  98.0c tau 28 $-19.63`<br>`LOSS KXHYPE15M-26SEP110830-30       no  98.0c tau 28 $-19.63` | 41 |
| `20260912T02` | `pinrun-live-20260912T022339Z.jsonl` | `KXSOL15M-26SEP112300-00` | `LOSS KXSOL15M-26SEP112300-00        no  97.0c tau 30 $-11.66` | `LOSS KXBTC15M-26SEP112300-00        no  97.0c tau 12 $-19.44` | 61 |
| `20260912T07` | `pinrun-live-20260912T033347Z.jsonl` | `KXSOL15M-26SEP120400-00` | **no settled market in this hour** -- 0 decision moments | -- | 17 |

**Six of the seven hours print our own loss, and the seventh has no settled market to score** (`fulltape/markets.json` stops at 2026-09-12T04:45Z; see divergence 9). Every one of these runs was executed twice and the `LOSS` lines and P&L lines are identical both times.

The hour `20260911T12` is worth reading on its own. Our loss there was one market; the backtest, under the gate that was live, bought **five** markets into the same 12:30 close and lost all five, `$-95.06` on one quarter hour. All twelve crypto series settle on the same quarter hour at rho ~ 0.8 (CLAUDE.md), so that is the correlated-close risk showing up as a number for the first time -- and it is another consequence of not enforcing `MAX_PER_CLOSE`, which live does (divergence 2).

`research/pinsim.py --hours 1 --end 20260909T00 --gate-from results/pinrun-live-20260909T000027Z.jsonl`

```
GATE AS OF pinrun-live-20260909T000027Z.jsonl (2026-09-09T00:00:27Z): PIN=0.98, PRICE_CEILING=0.988, EDGE_FLOOR=0.003, EV_FLOOR=0.003, SIZE=20.0, TAU_MIN=3, TAU_MAX=30, MIN_LEVEL=1.0, MAX_BOOK_AGE_MS=2000, MAX_INDEX_AGE_S=2, SIGMA_STRESS=1.0, SIGMA_WIN=300, IMPROVE_BY=0.005, MAX_PER_CLOSE=3, EV_IMPLIED_CEILING=0.988
TRADED, all                            4 fills     3 closes     3W   1L   25.00% [0.63, 80.59]  $   -16.95   95.92c
37,119 decision moments evaluated; seq monotone throughout; 1,034 events whose ts_ms precedes the second before them -- the TAPE's own clock inversions, not the merge's (12.7% of deltas carry a ts_ms already seen in seq order, measured on 20260909T00: 595,337 of 4,692,864). The simulated clock is held, never rewound
LOSS KXNEAR15M-26SEP082045-45       no  90.9c tau 22 $-18.30
```

`research/pinsim.py --hours 1 --end 20260910T04 --gate-from results/pinrun-live-20260909T214302Z.jsonl`

```
GATE AS OF pinrun-live-20260909T214302Z.jsonl (2026-09-09T21:43:02Z): PIN=0.98, PRICE_CEILING=0.98, EDGE_FLOOR=0.003, EV_FLOOR=0.003, SIZE=20.0, TAU_MIN=3, TAU_MAX=30, MIN_LEVEL=1.0, MAX_BOOK_AGE_MS=2000, MAX_INDEX_AGE_S=2, SIGMA_STRESS=1.0, SIGMA_WIN=300, IMPROVE_BY=0.005, MAX_PER_CLOSE=2, EV_IMPLIED_CEILING=0.988
TRADED, all                            2 fills     2 closes     1W   1L   50.00% [1.26, 98.74]  $   -18.13   95.00c
52,171 decision moments evaluated; seq monotone throughout; 634 events whose ts_ms precedes the second before them -- the TAPE's own clock inversions, not the merge's (12.7% of deltas carry a ts_ms already seen in seq order, measured on 20260909T00: 595,337 of 4,692,864). The simulated clock is held, never rewound
LOSS KXXRP15M-26SEP100100-00       yes  95.7c tau 21 $-19.20
```

`research/pinsim.py --hours 1 --end 20260910T05 --gate-from results/pinrun-live-20260909T214302Z.jsonl`

```
GATE AS OF pinrun-live-20260909T214302Z.jsonl (2026-09-09T21:43:02Z): PIN=0.98, PRICE_CEILING=0.98, EDGE_FLOOR=0.003, EV_FLOOR=0.003, SIZE=20.0, TAU_MIN=3, TAU_MAX=30, MIN_LEVEL=1.0, MAX_BOOK_AGE_MS=2000, MAX_INDEX_AGE_S=2, SIGMA_STRESS=1.0, SIGMA_WIN=300, IMPROVE_BY=0.005, MAX_PER_CLOSE=2, EV_IMPLIED_CEILING=0.988
TRADED, all                            7 fills     3 closes     6W   1L   14.29% [0.36, 57.87]  $   -13.34   95.17c
39,837 decision moments evaluated; seq monotone throughout; 1,060 events whose ts_ms precedes the second before them -- the TAPE's own clock inversions, not the merge's (12.7% of deltas carry a ts_ms already seen in seq order, measured on 20260909T00: 595,337 of 4,692,864). The simulated clock is held, never rewound
LOSS KXBNB15M-26SEP100130-30       yes  94.0c tau 26 $-17.60
```

`research/pinsim.py --hours 1 --end 20260910T22 --gate-from results/pinrun-live-20260910T083328Z.jsonl`

```
GATE AS OF pinrun-live-20260910T083328Z.jsonl (2026-09-10T08:33:28Z): PIN=0.995, PRICE_CEILING=0.98, EDGE_FLOOR=0.003, EV_FLOOR=0.003, SIZE=20.0, TAU_MIN=3, TAU_MAX=30, MIN_LEVEL=1.0, MAX_BOOK_AGE_MS=2000, MAX_INDEX_AGE_S=2, SIGMA_STRESS=1.0, SIGMA_WIN=300, IMPROVE_BY=0.005, MAX_PER_CLOSE=2, EV_IMPLIED_CEILING=0.988
TRADED, all                            4 fills     3 closes     3W   1L   25.00% [0.63, 80.59]  $   -18.27   97.67c
43,934 decision moments evaluated; seq monotone throughout; 919 events whose ts_ms precedes the second before them -- the TAPE's own clock inversions, not the merge's (12.7% of deltas carry a ts_ms already seen in seq order, measured on 20260909T00: 595,337 of 4,692,864). The simulated clock is held, never rewound
LOSS KXDOGE15M-26SEP101815-15       no  97.4c tau 17 $-19.52
```

`research/pinsim.py --hours 1 --end 20260911T12 --gate-from results/pinrun-live-20260911T001200Z.jsonl`

```
GATE AS OF pinrun-live-20260911T001200Z.jsonl (2026-09-11T00:12:00Z): PIN=0.995, PRICE_CEILING=0.98, EDGE_FLOOR=0.003, EV_FLOOR=0.003, SIZE=20.0, TAU_MIN=3, TAU_MAX=30, MIN_LEVEL=1.0, MAX_BOOK_AGE_MS=2000, MAX_INDEX_AGE_S=2, SIGMA_STRESS=1.0, SIGMA_WIN=300, IMPROVE_BY=0.005, MAX_PER_CLOSE=2, EV_IMPLIED_CEILING=0.988
TRADED, all                            5 fills     1 closes     0W   5L  100.00% [47.82, 100.00]  $   -95.06   97.86c
18,019 decision moments evaluated; 1 backward `seq` steps in the tape
LOSS KXSOL15M-26SEP110830-30        no  98.0c tau 30 $-16.68
LOSS KXXRP15M-26SEP110830-30        no  97.7c tau 30 $-19.57
LOSS KXBNB15M-26SEP110830-30        no  97.6c tau 30 $-19.55
LOSS KXDOGE15M-26SEP110830-30       no  98.0c tau 28 $-19.63
LOSS KXHYPE15M-26SEP110830-30       no  98.0c tau 28 $-19.63
```

`research/pinsim.py --hours 1 --end 20260912T02 --gate-from results/pinrun-live-20260912T022339Z.jsonl`

```
GATE AS OF pinrun-live-20260912T022339Z.jsonl (2026-09-12T02:23:39Z): PIN=0.995, PRICE_CEILING=0.98, EDGE_FLOOR=0.003, EV_FLOOR=0.003, SIZE=20.0, TAU_MIN=3, TAU_MAX=30, MIN_FILL_FRAC=0.5, MIN_LEVEL=1.0, MAX_BOOK_AGE_MS=2000, MAX_INDEX_AGE_S=2, SIGMA_STRESS=1.0, SIGMA_WIN=300, IMPROVE_BY=0.005, DUMP_DISCOUNT=0.15, DUMP_ENABLED=True, MAX_PER_CLOSE=2, EV_IMPLIED_CEILING=0.988
TRADED, all                            8 fills     3 closes     6W   2L   25.00% [3.19, 65.09]  $   -23.55   93.27c
43,483 decision moments evaluated; seq monotone throughout
LOSS KXSOL15M-26SEP112300-00        no  97.0c tau 30 $-11.66
LOSS KXBTC15M-26SEP112300-00        no  97.0c tau 12 $-19.44
```

`research/pinsim.py --hours 1 --end 20260912T07 --gate-from results/pinrun-live-20260912T033347Z.jsonl`

```
GATE AS OF pinrun-live-20260912T033347Z.jsonl (2026-09-12T03:33:47Z): PIN=0.995, PRICE_CEILING=0.98, EDGE_FLOOR=0.003, EV_FLOOR=0.003, SIZE=20.0, TAU_MIN=3, TAU_MAX=30, MIN_FILL_FRAC=0.5, MIN_LEVEL=1.0, MAX_BOOK_AGE_MS=2000, MAX_INDEX_AGE_S=2, SIGMA_STRESS=1.0, SIGMA_WIN=300, IMPROVE_BY=0.005, DUMP_DISCOUNT=0.15, DUMP_ENABLED=True, MAX_PER_CLOSE=2, MAX_PER_MARKET=1, EV_IMPLIED_CEILING=0.988
0 decision moments evaluated; 1 backward `seq` steps in the tape
```

## The 72-hour hedge holdout, rebuilt

`--end 20260910T04 --hours 72 --hedge 0.70,0.80,0.90 --size 20`, the same window, the same profile (`sha 7f3072d03e80`) and the same size as the run in git at `e9e9b8d`. The positions JSON is still written before the report (log line 111, before the table). Zero deltas failed to parse. 3,056,611 decision moments were evaluated where the old run evaluated one per second per market.

| | BEFORE (e9e9b8d) | AFTER |
|---|---|---|
| fills | 162 | **195** |
| closes | 101 | **117** |
| losses | 4 | **6** |
| loss rate | 2.47% [0.68, 6.20] | **3.08% [1.14, 6.58]** |
| P&L (upper bound, every offer assumed ours) | $+31.52 | **$+10.45** |
| at the 70% live fill rate | $+22.06 | **$+7.31** |
| mean price paid | 96.16c | **96.29c** |
| fit (first 70% of closes) | $+16.63, 3 losses | **$+11.00, 4 losses** |
| HOLDOUT (last 30%) | $+14.90, 1 loss | **$-0.55, 2 losses** |
| refused by the profile's `dump` rule | 12 fills | 8 fills |

**The rebuilt backtest is worse, and that is the point.** It takes 33 more trades, pays 0.13c more per contract for them (it buys at the first millisecond the gate passes, not at the next second boundary, and the first crossing is usually the dearest), takes two more losses, and its own out-of-sample third goes from +$14.90 to -$0.55. **Two of our real losing markets fall inside this window -- `KXNEAR15M-26SEP082045-45` and `KXXRP15M-26SEP100100-00`. The old backtest reproduced one of them; this one reproduces both**, and the XRP line (`yes 95.7c tau 21 $-19.20`) is the trade we actually made, at the price our live model logged.

Two cautions on this table. The last-30% holdout is 36 closes and 2 losses: its interval [0.39, 11.17] contains the fit's 3.01%, so "the holdout went negative" is one or two trades' worth of noise, not a verdict. And neither column enforces `MAX_PER_CLOSE`, so both are position-count optimistic in the same direction (divergence 2 below) -- which is why they are comparable to each other and not to a live P&L.

**Do not compare the two `why other ... did not fire` lines.** The old one counts MARKET-SECONDS (`no_offer` 64,803) because a refused market was re-counted every second; the new one counts MARKETS, once per market per reason (`no_offer` 2,276), because event-driven evaluation visits a market thousands of times before it decides and a per-visit tally would have read `too_shallow 77,000` and meant nothing. CLAUDE.md: `n` is markets or closes, never trades.

The `moments` line in the log below carries an earlier, WRONG wording of the clock-inversion counter ("snapshot receipts out of clock order"): the counter is the one described in divergence 6 and the wording was corrected in `pinsim.py` after this run had started. The number, 52,816 over 72 hours, is the count of events whose `ts_ms` precedes the second before them.

### BEFORE (git e9e9b8d: snapshots-first book, once a second)

```
  AMENDMENT 15 HOLDOUT -- 162 simulated positions, 4 lost (2.47%), unhedged P&L $+31.52
  every figure is a CEILING: delta-only book, and the replay always wins the race for the ask
   threshold  alarms  false   fa-cost $  caught  of   filled   rec c/ct   net dP&L $   hedged P&L $
        0.70       4      0        0.00       4   4        4       43.2        33.32          64.84   false-alarm rate 0.00% [0.00, 2.25]
        0.80       4      0        0.00       4   4        4       55.5        43.08          74.60   false-alarm rate 0.00% [0.00, 2.25]
        0.90       5      1        0.77       4   4        5       68.2        44.88          76.40   false-alarm rate 0.62% [0.02, 3.39]
  'caught' = alarm fired on an eventual loser; 'filled' = an ask existed under $1 within HEDGE_MAX_TRIES seconds; 'rec' = cents of the loss recovered per hedged contract
  thr 0.70: alarm fired on losers at tau [18, 16, 11, 9]
  thr 0.80: alarm fired on losers at tau [19, 16, 11, 9]
  thr 0.90: alarm fired on losers at tau [19, 16, 13, 13]
  ====================================================================================================

  ====================================================================================================
  PROFILE default (sha 7f3072d03e80), size 20, 72 book hours -- UPPER BOUND: every offer assumed ours; live we fill ~70%
  ====================================================================================================
  TRADED, all                          162 fills   101 closes   158W   4L    2.47% [0.68, 6.20]  $   +31.52   96.16c
    fit (first 70% of closes)          110 fills    71 closes   107W   3L    2.73% [0.57, 7.76]  $   +16.63   96.10c
    HOLDOUT (last 30%)                  52 fills    30 closes    51W   1L    1.92% [0.05, 10.26]  $   +14.90   96.28c
  at the 70% live fill rate: $+22.06
  REFUSED by rules (would-be)           12 fills    11 closes    11W   1L    8.33% [0.21, 38.48]  $   +32.43   76.58c

  PER RULE -- what it fired on, and what would have happened
  dump [refuse] all                     12 fills    11 closes    11W   1L    8.33% [0.21, 38.48]  $   +32.43   76.58c
      fit                                7 fills     7 closes     7W   0L    0.00% [0.00, 40.96]  $   +36.79   72.29c
      HOLDOUT                            5 fills     4 closes     4W   1L   20.00% [0.51, 71.64]  $    -4.36   82.60c

  why other moments did not fire: {'no_offer': 64803, 'too_shallow': 908, 'over_ceiling': 4578, 'undecided': 3415, 'stale_book': 348}
    LOSS KXDOGE15M-26SEP071000-00       no  98.0c tau 16 $-19.63
    LOSS KXHYPE15M-26SEP071645-45      yes  95.4c tau 23 $-19.14
    LOSS KXXRP15M-26SEP071730-30       yes  95.5c tau 18 $-19.16
    LOSS KXNEAR15M-26SEP082045-45       no  97.3c tau 18 $-19.50
EXIT 0
```

### AFTER (seq-ordered book, a decision at every event)

```
  AMENDMENT 15 HOLDOUT -- 195 simulated positions, 6 lost (3.08%), unhedged P&L $+10.45
  every figure is a CEILING: delta-only book, and the replay always wins the race for the ask
   threshold  alarms  false   fa-cost $  caught  of   filled   rec c/ct   net dP&L $   hedged P&L $
        0.70       8      2       19.66       6   6        8       41.7        28.48          38.93   false-alarm rate 1.03% [0.12, 3.66]
        0.80       9      3       22.21       6   6        9       49.8        35.69          46.14   false-alarm rate 1.54% [0.32, 4.43]
        0.90      12      6       34.93       6   6       12       58.3        25.54          35.99   false-alarm rate 3.08% [1.14, 6.58]
  'caught' = alarm fired on an eventual loser; 'filled' = an ask existed under $1 within HEDGE_MAX_TRIES seconds; 'rec' = cents of the loss recovered per hedged contract
  thr 0.70: alarm fired on losers at tau [29, 19, 18, 16, 11, 9]
  thr 0.80: alarm fired on losers at tau [29, 19, 19, 16, 11, 9]
  thr 0.90: alarm fired on losers at tau [29, 19, 19, 16, 13, 13]
  ====================================================================================================

  ====================================================================================================
  PROFILE default (sha 7f3072d03e80), size 20, 72 book hours -- UPPER BOUND: every offer assumed ours; live we fill ~70%
  ====================================================================================================
  TRADED, all                          195 fills   117 closes   189W   6L    3.08% [1.14, 6.58]  $   +10.45   96.29c
    fit (first 70% of closes)          133 fills    81 closes   129W   4L    3.01% [0.83, 7.52]  $   +11.00   96.23c
    HOLDOUT (last 30%)                  62 fills    36 closes    60W   2L    3.23% [0.39, 11.17]  $    -0.55   96.41c
  at the 70% live fill rate: $+7.31
  REFUSED by rules (would-be)            8 fills     8 closes     8W   0L    0.00% [0.00, 36.94]  $   +38.07   74.88c

  PER RULE -- what it fired on, and what would have happened
  dump [refuse] all                      8 fills     8 closes     8W   0L    0.00% [0.00, 36.94]  $   +38.07   74.88c
      fit                                5 fills     5 closes     5W   0L    0.00% [0.00, 52.18]  $   +28.08   70.40c
      HOLDOUT                            3 fills     3 closes     3W   0L    0.00% [0.00, 70.76]  $    +9.99   82.33c

  why other markets never fired (MARKETS, counted once per market per reason): {'no_offer': 2276, 'too_shallow': 539, 'over_ceiling': 680, 'undecided': 247, 'stale_book': 21}
    LOSS KXHYPE15M-26SEP061945-45      yes  97.9c tau 30 $-18.63
    LOSS KXDOGE15M-26SEP071000-00       no  98.0c tau 16 $-19.63
    LOSS KXHYPE15M-26SEP071645-45      yes  95.4c tau 23 $-19.14
    LOSS KXXRP15M-26SEP071730-30       yes  95.5c tau 18 $-19.16
    LOSS KXNEAR15M-26SEP082045-45       no  97.3c tau 18 $-19.50
    LOSS KXXRP15M-26SEP100100-00       yes  95.7c tau 21 $-19.20
```

## What still diverges, and why

Ranked by how much it could flatter the backtest.

1. **The replay always wins the race, and live fills 70% of what it sends.** Every number here assumes the offer was ours. It is an UPPER BOUND, `report()` says so on its own header line, and no rebuild of the book can fix it -- the tape does not record who else was reaching for the same level. It is also why the walk in (3) often buys EARLIER and CHEAPER than we did: it takes the first millisecond the gate passes, where live took the first one its ~20 Hz loop noticed and then had to win.
2. **`MAX_PER_CLOSE` and `MAX_ATTEMPTS_PER_CLOSE` are not enforced.** Live caps positions at 2 per close (3 under the older gate); the replay caps one per MARKET (the `decided` set) and will take three markets in one close. That was true before the rebuild too, so the before/after holdout comparison is not affected by it -- but a dollars figure from this file is not a dollars figure live could have earned. Fixing it changes P&L and is a separate decision, not a replay repair.
3. **The index is fed by the second STAMPED on a print, not by when the print arrived.** A tick stamped S is treated as available at S+0 ms; live it lands ~80 ms into the second. `RESULTS_replay.md` measures the cost of exactly this: feeding by stamp reproduces the live `fair` on 172/207 fills, feeding by arrival (`_rx_ms`) on 180/207. So the rule costs 8 fills in 207 and is the next thing to fix. It was left alone here because it moves `fair` itself, and moving the book and the model in one change would make neither measurable.
4. **One decision per market, so a market we took three fills on can be reproduced once.** Three of the nine losses are three fills on `KXNEAR15M-26SEP082045-45`, taken before AMENDMENT 13 capped fills per market at 1. The market-level tables say 7 losing MARKETS for that reason.
5. **A snapshot has no exchange timestamp at all.** It is PLACED by `seq` -- which is exact -- but TIMED by the collector's `_rx_ms`, clamped down to the `ts_ms` of the delta it precedes. That affects `book_age_ms` on the ~159 snapshot events an hour, against 2.6M deltas, and nothing else.
6. **The tape's own clock is not monotone.** In 20260909T00, 595,337 of 4,692,864 deltas carry a `ts_ms` earlier than one already seen in `seq` order, and 1,034 of those cross a second boundary. `Walk` holds the simulated clock rather than rewinding it, and counts every such event on its output line. This is the measurement behind *merging on the clock is wrong*: the clock disagrees with the exchange's own order 12.7% of the time.
7. **A collector reconnect restarts `seq`, and the merge does not segment on it -- this is the first thing to fix next.** Measured on 20260911T12: at message 925,953 of 4,504,521 the sequence drops from 13,803,396 to 3, and that hour's 181 snapshots then span seq 1 to 12,911,772 -- two numbering epochs in one sorted list. A snapshot sent by the RESUBSCRIBE carries a low seq, sorts to the front, and is applied near the start of the hour instead of at the reconnect. Harmless for a market that opened after the reconnect (its book is empty until its own deltas arrive); for a market that existed before it, it is the old bug again, for that one market. `EventStream.seq_back` counts the resets and `run()` prints the total, so an affected hour is visible rather than silent: **2 of the 7 hours holding a losing fill have exactly one reset**, and in both the losing close came after it. The fix is one line -- place a pending snapshot when EITHER the delta's `seq` has passed it OR its `_rx_ms` has -- and it was not taken here because it would have invalidated a 72-hour holdout already running.
8. **`pinreplay.py`'s flag `PINSIM_BOOK_DIFFERS_FROM_SEQ_ORDER` is now misnamed.** It compares seq order against a `snapfirst` reconstruction labelled *what pinsim.run() does*. After this change pinsim.run() does seq order, so that flag now measures the OLD pinsim. pinreplay is owned by another agent and was not touched.
9. **Settlement, not the backtest, blocks the very last trade.** `KXSOL15M-26SEP120400-00` (close 2026-09-12T08:00Z, our newest loss) is not in `fulltape/markets.json`, whose newest settlement is 2026-09-12T04:45Z, so `pinsim.run()` cannot score that market at all: `load_markets()` keeps only rows that have a `result`. The DECISION is reproduced -- the walk buys `yes @ 0.9400` at tau 19, which is the trade we made -- but the P&L cannot be until the settlement pull is refreshed. Refreshing it writes outside the repo, which this agent does not do unasked.

## Reproducing this

```
python research/pinsim.py --selftest
python research/pinsim.py --hours 1 --end 20260912T03 --size 20
python research/pinsim.py --hours 1 --end 20260909T00 --gate-from results/pinrun-live-20260909T000027Z.jsonl
python research/pinsim.py --end 20260910T04 --hours 72 --hedge 0.70,0.80,0.90 --size 20
python research/pinsim.py --hours 1 --end 20260912T03 --size 20 --per-second        # the OLD sampling, for scoring only
```

