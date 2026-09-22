# C9-hedgetune -- adversarial verification (lens: REPRODUCE)

Status: COMPLETE, 2026-09-22. Verifier C9-hedgetune-reproduce.
My own code only: scratchpad `map/verify2/C9-hedgetune-reproduce/` (`split.py`, `table_asis.py`,
`tape_ticker.py`, `lag.py`, `belief_check.py`, `sim.py`, `check04walk.py`, `robust.py`,
`override.py`, `tstat.py`). No investigator script run or imported.

## Verdict: CONFIRMED, with three corrections

Every part of the claim reproduces. Three of the numbers that back it are wrong or rest on a fragile
choice, but the conclusions hold:
1. 04's upper figure, **$42**, comes from a pricing model with a bug: every second it re-bought the
   same 3 contracts from a quote that was 7.5 minutes old (DOGE 09-16, at 92.6c). That is the
   staleness fault (#2) that 04 itself found. Fixed, the number is **$8 to $46** depending on two
   judgement calls. The best-sourced estimate is **+$45.51**, so the top of 04's range was right,
   but for the wrong reason.
2. "Flips on dropping two alarms": in fact it flips when **one close** is dropped, 09-19 23:45 ET,
   which holds two alarms (HYPE and XRP). That is true in every version of the model.
3. "Move-bar bypassed": the bar said not to move off 0.80. The operator overrode it on 09-16
   (v-hedge60), not v-hedge25. What v-hedge25 did bypass, without a word, is the written
   **floor**: "Not below 0.30" (PREREG_hedge) and "the floor is 0.30, never lower" (VERSIONS).

## Headline numbers reproduced

### 1. Lifetime hedging on the ledger: -$9.35. REPRODUCED EXACTLY
Own join (`split.py`): `kalshi_ledger.json` has 21 markets where both sides were held. Removed:
BTC 09-07 (0.02 contracts, before hedging existed), SOL 09-12 06:00 (the 1-contract planted
test) and two WTI markets (commodity bot). That leaves **17 hedged markets on 16 closes**, the same
set as the `hedge_alarm` list.
Method: main side = `hedge_alarm.want`; hedge value = ledger net minus (main payout - main cost
- main fee).

Three independent ways to split the fee:
- (A) main fee taken from the entry `order.fee_total`: **-$9.35** (10 saves +$149.26, 7 false
  alarms -$158.60).
- (B) ledger only, fee split in proportion to 0.07*n*p*(1-p) at each leg's average price: -$9.32.
- (C) hedge fee taken from the hedge fill records: -$9.30.

Premium incl. fee $497.48, payouts $488.13. Across those 17 markets: unhedged -$434.87, hedged
-$444.22. Dropping close 09-19 23:45 ET gives +$107.53. Every row matches 04's table to the cent,
and the ledger's hedge-leg counts and costs equal the hedge fill records on all 17.

### 2. The tool as shipped: REPRODUCED EXACTLY from `flow_cache/hedgetune_table.json`
My own reimplementation (`table_asis.py`), 16 alarms, sum of "never hedge" = -$324.40:

| trigger | 0.60 | 0.40 | 0.30 | 0.25 | 0.20 |
|---|---|---|---|---|---|
| total | -370.05 | -321.58 | -339.66 | -273.15 | -254.56 |

These equal VERSIONS v-hedge25. 0.25 minus 0.60 = **+$96.90** (this is the "~$97").
(Not in any report: on the same as-shipped table, 0.80 reads +$67.79 against never hedging,
better than the shipped 0.25 at +$51.25. The tool's trigger list starts at 0.60, so 0.80 was
never shown.)

### 3. The four faults: ALL CONFIRMED, from the code and from the raw tape
- **Receive time.** `build()` keys prices on `_rx_ms // 1000` (the recorder's clock). Every ticker
  message also carries the exchange's own `ts_ms`. In the window from 12 s before the alarm to the
  close, receive lag is median **0.05-0.36 s**, but the maximum is **1.93-6.47 s in 14 of 16
  alarms**. So "2-6 s late" describes the worst seconds, not the typical one, and the worst
  seconds are the collapses.
  - At the seconds we really hedged (21 fills, 698.13 contracts, DOGE 09-16 excluded) we paid
    **52.85c**, the tool priced **49.09c** (**$26.25 too cheap**), and exchange-time top of book
    was **53.19c** ($2.34 off).
  - DOGE 09-18: tool 2.2c vs 74c paid. ETH 09-12: tool 5.5c vs 26-27c.
  - All of this is identical to 04.
- **No staleness guard.** DOGE 09-16: the last ticker message was at 12:52:16Z, 452 s before the
  alarm, quoting 92.6c. There was no message from then to the close. The code carries `q` forward
  with no age check. At the same second the live bot saw an ask of 17c for 399 contracts and paid
  15c.
- **Hedges before entry.** The path starts at the alarm minus 12 s (`LOOKBACK`) with no reference
  to our fill:
  - At 0.60, BTC 09-12 "hedged" at alarm -12 s (tau 36); our entry fill was at alarm -6 s (tau 30).
  - BNB 09-13 "hedged" at tau 16; our fill was at tau 5.
  - Starting each path at our fill moves 0.60 from -$45.65 to **-$10.32** (+$35.33), exactly as 04
    found.
- **Top of book, one shot.** `n = min(n, depth)` at one second. At 0.25 it hedged 3 of 76
  (BNB 09-19 01:45), 6.97 of 84.5 (BNB 09-19 12:30) and 37 of 104 (XRP 09-19).
- **Sizes taken from settled rows.** ETH 09-12 is n=6 (the ledger says 20); ZEC 09-12 is n=10 (the
  ledger says 11; 04 did not list this one). BTC 09-17 21:15 and HYPE 09-21 are missing from the
  table.

### 4. The corrected dial: my own model
Model: the tool's belief path (checked below), exchange-time top of book, stale quotes over 3 s
refused, the path starts at our entry fill, sizes and unhedged money from the ledger, and the
whole position bought by walking the top of book each second for up to 30 tries.

**Check against the ledger.** Run at each alarm's own live trigger, on the 11 alarms where live
execution is comparable (the others ran a price gate, the proportional hedge, or had a dead
feed): sim **-$12.25 vs ledger -$10.26**. 8 of the 11 rows are within $0.70. The sim flatters BTC
09-14 by $3.58 and HYPE 09-14 by $4.36, and is $8.12 harsher than live on XRP 09-19.

**Belief rebuild.** It first crosses the live threshold in the same second as the live alarm on
14 of 16 alarms. The two misses are both boundary cases:
- NEAR 09-16: 0.804 rebuilt vs 0.766 logged, against 0.80.
- NEAR 09-19 17:15: 0.601 rebuilt vs **0.585** logged, against 0.60. 04 did not report this one,
  and it matters (below).

Step by step, value against never hedging (my code; the first four rows equal 04's rows to the
cent):

| step | <0.80 | <0.60 | <0.40 | <0.30 | <0.25 | <0.20 | 0.25 minus 0.60 |
|---|---|---|---|---|---|---|---|
| as shipped | +67.79 | -45.65 | +2.82 | -15.26 | +51.25 | +69.84 | +96.90 |
| + start at entry | +95.56 | -10.32 | +26.01 | -15.26 | +51.25 | +69.84 | +61.57 |
| + exchange-time prices | +85.57 | -18.63 | -0.23 | -23.57 | +42.94 | +61.53 | +61.57 |
| + 3 s stale guard + ledger sizes | +84.30 | -22.32 | -6.79 | -30.13 | +36.39 | +61.66 | +58.71 |
| walk whole position (DOGE 09-16 unhedgeable) | +73.37 | +36.52 | +46.97 | +16.55 | +44.92 | +101.25 | **+8.40** |
| walk, DOGE 09-16 at its live-paid 15c | +59.54 | +22.69 | +46.97 | +16.55 | +44.92 | +101.25 | **+22.23** |
| walk, live-logged belief at alarm second, DOGE unhedgeable | +56.67 | +13.23 | +46.97 | +16.55 | +44.92 | +107.61 | **+31.68** |
| **walk, live belief + DOGE live price (best-sourced)** | +42.84 | **-0.59** | +46.97 | +16.55 | +44.92 | +107.61 | **+45.51** |
| 04's walk (re-buys the same stale 3-lot each second) | | +2.84 (mine +3.01) | +46.87 | | +44.79 | +101.14 | +41.95 |

- **Where 04's walk goes wrong (checked, `check04walk.py`).** A walk that does not track depth it
  has already taken from an unchanged quote buys 3 contracts at 92.6c on DOGE 09-16 in each of 12
  seconds, 36 contracts on a winner. That is -$33.51, against -$13.83 at the real 15c. It gives
  +$3.01 at 0.60, which matches 04's +2.84 (the gap is fee rounding). 04's F8 numbers carry the
  same -$19.68 at 0.80: 0.30 minus 0.80 comes out -$1.15 in 04 and -$20.95 in mine; 0.25 minus
  0.80 comes out +$27.18 in 04 and +$7.41 in mine.
- **Both ends of "$22-42" hang on two judgement calls:**
  - DOGE 09-16's dead feed. Is the market hedgeable at 0.60, and at what price?
  - NEAR 09-19 17:15. Live belief 0.585 says 0.60 would have hedged 72 contracts of a winner at
    about 30-37c (-$23); the rebuilt 0.601 says it would not.

  Using live data wherever it exists, as the operator's source order requires, gives **+$45.51**.
- **0.40 ties 0.25: CONFIRMED.** +$46.97 vs +$44.92 (+$2.05) in every walk variant. Its worst
  drop-one close is -$28.44 (NEAR 09-21), which makes it a coin toss.
- **0.20 reads best in every variant** (+$101 to +$108). Its lead over 0.25 (+$56 to +$63) mostly
  depends on XRP 09-19's belief bottoming at 0.209.
- **Flip test, by close (15 closes; HYPE and XRP 09-19 23:45 are one close):**
  - 0.25 minus 0.60: dropping close 09-19 23:45 alone turns it to **-$46.43 / -$60.25 / -$36.97 /
    -$23.14** in the four walk variants.
  - 0.25 vs never: survives every drop-one (worst +$17.17), flips on drop-two (**-$6.80**, BTC
    09-14 + BNB 09-19 01:45; 04 had -$6.90).
- **Significance.** 0.25 minus 0.60, per close: mean +$1.48 to +$3.03, **t = 0.26-0.52**, with only
  6-7 of 15 closes non-zero. 0.40 minus 0.25: t = 0.05. All of this is below the 30-close floor.
  None of it is a result; it only shows how big the effect could be.

### 5. The PREREG_hedge bar: CONFIRMED that it was not met, and that the floor was crossed without comment
- PREREG_hedge (09-14) says **"Not below 0.30."** VERSIONS (withdrawn-0.10 entry) says "the floor
  is 0.30, never lower". The e7306e1 commit message and the v-hedge25 VERSIONS entry cite neither.
  They add a new criterion ("loosest trigger whose every drop-one is positive") after the result
  was seen.
- The move-bar ("do not move off 0.80 until...") had already been overridden on the operator's
  explicit instruction at v-hedge60 (09-16, which itself says "0.60 was chosen after seeing
  them"). So the move-bar breach is v-hedge60's, not v-hedge25's.
- Scored anyway on the 10 table alarms after 09-14:
  - Condition 2: 0.30 minus 0.80 = **-$4.26** (best-sourced) to -$34.78. It **fails** in every
    variant.
  - Condition 3: 0.25 minus 0.80 = +$24.11 to -$6.41, and NEAR 09-21 alone (-$38.09) is **158% to
    594%** of it. It **fails**.
  - Condition 1 (>= 10 events settled after 09-14) was met: 11 alarm markets.

## Cuts tried / multiple-looks bar
- Ledger: 3 fee splits, and 16 drop-one-close cuts.
- Dial: 17 model variants x 6 triggers = **102 cells**.
- Robustness: 5 difference series x (15 drop-one + 105 drop-two) = 600 cuts per variant, on 4 walk
  variants.
- Bonferroni bar for about 100 dial cells at 0.05: |t| > 3.5. The largest t measured is 0.52.
  Nothing here is a significant difference between triggers. The dollar figures are descriptive
  sums over 15 closes, below the 30-close floor.

## Where my numbers differ from the reports, and which is right
| number | report | mine | which is right |
|---|---|---|---|
| lifetime hedge value | 04: -$9.35; "elsewhere" ~-$11 | -$9.35 (fee splits: -9.30..-9.35) | 04 |
| 0.25 minus 0.60, as shipped | VERSIONS: +$96.90 | +$96.90 | same (and the tool is wrong, see faults) |
| 0.60 vs never, walk | 04: +$2.84 | +$13 to +$37; -$0.59 best-sourced | mine. 04's walk re-bought a 452-s-old 3-lot 12 times |
| 0.25 minus 0.60, corrected | 04: +$41.95 walk / ~+$22 with DOGE real | +$8.40 / +$22.23 / +$31.68 / +$45.51 | range $8-46; 04's $42 was right by accident |
| PREREG 0.30 minus 0.80 | 04: -$1.15 | -$4.26 best-sourced, -$20.95 table belief | mine (same stale re-buy in 04); conclusion unchanged |
| PREREG 0.25 minus 0.80 | 04: +$27.18, NEAR 140% | +$24.11 (158%) / +$7.41 (514%) | mine; conclusion unchanged |
| receive-lag median | 04: 0.04-0.29 s | 0.05-0.36 s | trivial (window choice); maxima identical |
| real hedge fills in the table | 04: "22 fills, 785 contracts" | 22 fills, 785.13 | same |
| "flips on dropping two alarms" | claim | flips on dropping ONE close (two alarms) | mine is the stricter reading |

## Could not measure
- DOGE 09-16's insurance price after the alarm second. The ticker feed was dead and I did not
  rebuild it from `orderbook_delta` (memory budget). Only 0.60 and 0.80 fire on it (its belief was
  0.484 for one second, then back above 0.82), so lower triggers are unaffected.
- Whether the live bot, at a pure 0.60 trigger with no price gate, would have paid the tape's
  30-37c on NEAR 09-19 or the 40c ask it logged. I used the tape walk.

Resources: RAM 1.6 GB free at the finish; both recorders alive (kalshi_collector pid 105304, crypto_feeds pid
105352); disk C: 30.5 GB free. Tape read: 20 ticker hour files, streamed, only the alarm markets
kept. No process touched.
