# 04 hedge -- the hedge's value, re-derived from scratch

Investigator 04, 2026-09-22. STATUS: COMPLETE (all five questions answered;
sections 1-4 final).

**Ranked by dollars (detail below):**

| # | finding | dollars | source |
|---|---|---|---|
| F5 | the two biggest losses of the hedging era had NO hedge (bugs; HANDOFF says fixed) | **-$174.28** | ledger |
| F2 | the entire lifetime hedge verdict is one close, 09-19 23:45 ET | **-$116.87** swing | ledger |
| F6.3 | fills that come back >= 3c under the ask we saw: 7 of 23 lost (30% vs 1.7%) | **-$113.18** net | ledger + order logs |
| F3 | v-hedge25's tool overstated 0.25-vs-0.60 by ~$55-75 (four faults) | +$96.90 claimed -> ~+$22-42 | tape vs our fills |
| F1 | lifetime value of hedging, 17 hedges / 16 closes | **-$9.35** (+$149.26 saves, -$158.60 false alarms) | ledger |
| F4 | HYPE and NEAR 09-21 walked: market led our model by 1-3 s; trigger level did not matter for HYPE | +$22.70, +$15.15 saved | logs + tape |
| F7 | a market-price trigger is NOT better than the belief trigger | refuted | tape (hypothesis) |
| F8 | v-hedge25 went under PREREG_hedge's written floor (0.30) without meeting or citing its bar; corrected, the bar fails | process | prereg + replay |

Sources: `results/pinrun-live-*.jsonl` (hedge_alarm / hedge / hedge_panic /
hedge_prop / hedge_wait_price / order), `results/kalshi_ledger.json` (Kalshi's
own per-market settlement: it carries YES and NO cost SEPARATELY, so the main
leg and the hedge leg can be split without trusting our logs), `results/VERSIONS.md`,
`research/hedgetune.py` and its cached table `flow_cache/hedgetune_table.json`.
Scripts: scratchpad `map/04/main.py` (join), `alarms.json` (per-alarm rows).

Method: main leg = the side named in `hedge_alarm.want`; hedge leg = the other
side. Main-leg fee = sum of `fee_total` on that market's `order` records;
hedge fee = ledger `fee_cost` minus that (checked against 0.07*n*p*(1-p):
matches to the cent on every row). UNHEDGED = main payout - main cost - main
fee. HEDGE VALUE = ledger net - unhedged = hedge payout - hedge cost - hedge fee.

## 1. Findings, ranked by dollars

### F1. Lifetime, the hedge has made -$9.35 -- it is a coin toss that has cost a little, and one alarm flips its sign

- **Claim.** 17 real hedges (16 closes), 10 real saves **+$149.26**, 7 false
  alarms **-$158.60**, net **-$9.35**. Premium paid $497.48 (incl. fees),
  payouts received $488.13. Across the same 17 markets: unhedged -$434.87,
  hedged -$444.22. Against the ~$387 the bot has made lifetime, the hedge is
  roughly zero -- neither the problem nor the fix.
- **Mechanism.** A hedge is the other side of the same binary. On a real save it
  returns `n*(1-price)`; on a false alarm it burns `n*price`. Real collapses
  are already priced by the time our belief alarms, so saves bought insurance
  at **68c** on average and returned **30.6c/contract**; false alarms bought it
  at **34c** and burned **35.2c/contract**. Break-even is therefore 53.5% of
  hedged contracts being on real losses; the actual share is 488 of 939 =
  **52.0%**. Net: a hair under zero.
- **Per version** (live fills, ledger money):

| version (live window, UTC) | saves | $ | false alarms | $ | net |
|---|---|---|---|---|---|
| belief<0.90, 09-12 | 0 | 0 | 2 | -8.50 | **-8.50** |
| belief<0.80, 09-12 18Z..09-16 14Z | 3 | +55.45 | 3 | -33.23 | **+22.22** |
| belief<0.60, no price gate, 09-16..09-18 23Z | 3 | +35.12 | 0 | 0 | **+35.12** |
| belief<0.60 + `--hedge-price 0.60`, 09-18 23Z..09-20 06Z | 2 | +20.83 | 2 | -116.87 | **-96.04** |
| A76 proportional, 09-20 06Z..09-21 17Z | 1 | +15.15 | 0 | 0 | **+15.15** |
| v-hedgefull / v-hedgelastweek, 09-21 17Z..20Z | no alarm | | | | 0 |
| v-hedge25 (belief<0.25), 09-21 20:12Z.. | 1 | +22.70 | 0 | 0 | **+22.70** |

  Plus one alarm with nothing bought: NEAR 09-19 17:14 ET (the 60c price gate
  refused a 40c hedge; the bet WON +$1.64, so the gate saved ~$29). Two
  1-contract test plants on 09-12 excluded.
- **Every alarm** (ET; money in dollars):

| market | ET | ver | belief at alarm | main n @ avg | hedge n @ avg | result | unhedged | hedged | hedge value | class |
|---|---|---|---|---|---|---|---|---|---|---|
| BTC 11:00 | 09-12 10:59 | 0.90 | 0.89 | 20 @ 90.0c | 20 @ 14.0c | won | +1.87 | -1.09 | -2.97 | false |
| ETH 11:15 | 09-12 11:14 | 0.90 | 0.66 | 20 @ 98.0c | 20 @ 26.3c | won | +0.37 | -5.16 | -5.53 | false |
| ZEC 20:00 | 09-12 19:59 | 0.80 | 0.53 | 11 @ 96.2c | 11 @ 80.9c | lost | -10.61 | -8.63 | +1.98 | save |
| BNB 12:30 | 09-13 12:29 | 0.80 | 0.64 | 32 @ 92.3c | 32 @ 10.0c | won | +2.31 | -1.10 | -3.40 | false |
| BTC 05:30 | 09-14 05:29 | 0.80 | 0.21 | 60 @ 97.2c | 60 @ 58.0c | lost | -58.43 | -34.26 | +24.18 | save |
| HYPE 16:00 | 09-14 15:59 | 0.80 | 0.56 | 62 @ 95.2c | 62 @ 51.0c | lost | -59.20 | -29.90 | +29.29 | save |
| NEAR 04:30 | 09-16 04:29 | 0.80 | 0.77 | 84 @ 91.4c | 84 @ 18.0c | won | +6.78 | -9.22 | -16.00 | false |
| DOGE 09:00 | 09-16 08:59 | 0.80 | 0.49 | 87 @ 97.9c | 87 @ 15.0c | won | +1.69 | -12.14 | -13.83 | false |
| BNB 12:30 | 09-16 12:29 | 0.60 | 0.53 | 1 @ 97.7c | 1 @ 47.0c | lost | -0.98 | -0.47 | +0.51 | save |
| BTC 21:15 | 09-17 21:14 | 0.60 | 0.21 | 99 @ **53.0c** | 99 @ 72.0c | lost | -54.19 | -27.87 | +26.32 | save |
| DOGE 00:15 | 09-18 00:14 | 0.60 | 0.24 | 33.6 @ **11.0c** | 33.6 @ 74.0c | lost | -3.93 | +4.36 | +8.29 | save |
| BNB 01:45 | 09-19 01:44 | 0.60+gate | 0.23 | 76 @ **75.0c** | **1** @ 76.0c | lost | -57.99 | -57.76 | +0.23 | save (1 of 76) |
| BNB 12:30 | 09-19 12:29 | 0.60+gate | 0.15 | 84.5 @ 97.3c | 84.5 @ 74.3c | lost | -82.36 | -61.75 | +20.61 | save |
| HYPE 23:45 | 09-19 23:44 | 0.60+gate | 0.44 | 104 @ 94.1c | 104 @ 46.0c | won | +5.74 | -43.92 | -49.66 | false |
| XRP 23:45 | 09-19 23:44 | 0.60+gate | 0.27 | 104 @ 97.7c | 104 @ 63.0c | won | +2.27 | -64.95 | -67.22 | false |
| NEAR 12:45 | 09-21 12:44 | A76 | 0.57 (bought at 0.39, 0.12) | 81 @ 91.1c | 81 @ 80.2c | lost | -74.24 | -59.09 | +15.15 | save |
| HYPE 18:15 | 09-21 18:14 | 0.25 | 0.23 | 55 @ 98.0c | 55 @ 57.0c | lost | -53.97 | -31.27 | +22.70 | save |

- **n.** 17 hedged markets, **16 closes** (HYPE and XRP 09-19 23:45 ET are one
  close, together -$116.87). Below the 30-close floor. No version has more
  than 6.
- **Confidence.** High on the dollars (every number is Kalshi's own ledger,
  split by side). Low on any conclusion about the SIGN: see F2.
- **Artefact check.** (a) Fee split: hedge fee recomputed as 0.07*n*p*(1-p)
  agrees on every row. (b) Order records never share an order_id with a hedge
  record, so no hedge fill is counted as a main-leg fee. (c) Matches the
  earlier 8 saves +$111 / 7 false -$159 exactly for the alarms up to 09-20; the
  two new saves since (NEAR 09-21, HYPE 09-21) add +$37.85.

### F2. The whole lifetime verdict rests on ONE close: 09-19 23:45 ET

- **Claim.** Drop the single close 09-19 23:45 ET (HYPE + XRP false alarms,
  -$116.87 together) and lifetime hedging reads **+$107.53**; keep it and it
  reads **-$9.35**. Drop XRP alone: +$57.87. Drop any ONE of the top six
  saves (HYPE 09-14 +29.29, BTC 09-17 +26.32, BTC 09-14 +24.18, HYPE 09-21
  +22.70, BNB 09-19 12:30 +20.61, NEAR 09-21 +15.15) and it goes to -$24..-$39.
  So the sign moves with one market either way.
- **Per era:** 0.90/0.80 era (8 hedges) **+$13.72**; 0.60-and-later era (9
  hedges) **-$23.07**, of which -$116.87 is the one close.
- **On the 10 hedged lost bets** hedging cut the loss from -$455.90 to
  -$306.64 (-81c to -54c per main-leg contract): it recovers **a third**, as
  the earlier sessions said.
- **Confidence.** The arithmetic is exact; the conclusion is "unknown sign,
  |value| about $10 lifetime, one close from either answer". Nothing here is
  significant (16 closes, floor is 30).
- **Artefact check.** Clustering by close done (the two 09-19 23:45 hedges are
  one observation). BNB 09-19 12:30 had two lots in one market -- counted once.

### F3. v-hedge25's tool (`hedgetune.py`) has four measurement faults; corrected, 0.25 still beats 0.60 but by ~$22-42 not $97, and that edge rests on the same single close

The tool was audited against our 22 real hedge fills (785 contracts) and the
cached table `flow_cache/hedgetune_table.json` (built 09-21 20:10Z, 16 alarms).
REPLAY-DERIVED: every number in this finding except the real fills is from the
tape + index, so it is a hypothesis.

**What is right.** The confidence rebuild is good: on 11 of the 12 alarms where
it can be checked, the rebuilt belief crosses the live threshold in **the same
second** the live bot alarmed, within 0.05 of the logged belief; the 12th (NEAR
09-16) sits on the boundary (rebuilt 0.804 vs live 0.766 against a 0.80 line).

**Fault 1 -- prices keyed on the collector's RECEIVE time, and the ticker feed
arrives 2-6 s late exactly during collapses.** Receive lag in the alarm windows:
median 0.04-0.29 s, **max 1.9-6.5 s in 14 of 16 alarms**. At DOGE 09-18 00:14
ET the tool priced insurance at **2.2c** (the pre-crash quote, received 3.6 s
late) when we really paid **74c**; at ETH 09-12 11:14 ET, **5.5c** vs **26-27c**
paid. At the seconds we actually hedged (21 fills, 698 contracts, excluding
DOGE 09-16): tool **49.1c** average vs our real **52.9c** -> the tool was
**$26.25 too cheap**. Re-keyed on the exchange's own timestamp (`msg.ts_ms`) the
tape gives **53.2c** vs 52.9c paid -- **$2.34 off over 698 contracts**. So the
tape is a good price source IF keyed on exchange time; the shipped tool was not.

**Fault 2 -- one market had no ticker feed for 7.5 minutes** (DOGE 09-16 09:00
ET: last ticker message 12:52:16Z, alarm 12:59:48Z). The tool carried a
452-second-old 92.6c quote; the real insurance cost 15-17c. No staleness check.

**Fault 3 -- it hedges before we own anything.** The path starts 12 s before the
alarm, not at our entry. At the 0.60 trigger it "hedged" BTC 09-12 11:00 at
tau 36 (we bought at tau 30) and BNB 09-13 12:30 at tau 16 (we bought at tau 5),
charging **-$35.33** of false-alarm cost that could never have happened. This
alone produced most of "0.60 was worse than never hedging" (-$45.65 -> -$10.32
once removed).

**Fault 4 -- execution: top-of-book only, one shot.** It caps the hedge at the
size on the best level. At 0.25 it hedged **3 of 76** contracts on BNB 09-19
01:45 and **7 of 84.5** on BNB 09-19 12:30, and 37 of 104 on the XRP false
alarm. The live bot hedges the WHOLE position, retrying each second (30 tries).
Also: position size and unhedged money come from our own settled rows (ETH
09-12 read as 6 contracts, really 20), and BTC 09-17 21:15 (+$26.32, a real
save) is missing because it has no settled row.

**The dial, corrected step by step** (hedge value vs never hedging, 16 alarms;
bracket = worst leave-one-out):

| | <0.60 | <0.40 | <0.25 | <0.20 |
|---|---|---|---|---|
| as shipped | -45.65 (-79.30) | +2.82 (-38.69) | **+51.25 (+23.50)** | +69.84 (+42.09) |
| + no hedge before entry | -10.32 | +26.01 | +51.25 | +69.84 |
| + exchange-time prices | -18.63 | -0.23 | +42.94 | +61.53 |
| + ledger sizes and money | -25.12 | -6.79 | +36.39 (+8.64) | +61.66 |
| live-like execution (whole position, retry each second) | **+2.84** | **+46.87 (+9.12)** | **+44.79 (+17.04)** | **+101.14 (+73.39)** |

(DOGE 09-16, the dead-feed market, still inflates the 0.60 column by ~$20 in
the last row.)

- **What survives:** 0.25 beats 0.60 in every version of the model. **What
  does not:** (a) "0.60 was worse than never hedging" -- under live-like
  execution 0.60 is about break-even; (b) "0.25 is the best-supported
  trigger" -- 0.40 ties it and 0.20 reads best in every row; (c) the size:
  0.25-minus-0.60 is +$96.90 as shipped, **+$41.95** corrected (walk model),
  ~+$22 with DOGE 09-16 at its real price.
- **What it rests on:** drop-TWO on 0.25 vs never = **-$6.90** (drop BTC 09-14
  and BNB 09-19 01:45). 0.25 minus 0.60, drop HYPE 09-19 23:45 and DOGE 09-16 =
  **-$31.80**. The 0.25-vs-0.20 choice rests on one number: XRP 09-19's belief
  bottomed at **0.209**.
- **Reproduction test** (sim at the trigger that was live for each alarm, vs
  the ledger): 12 checkable alarms, real -$24.09, sim (live-like) -$29.19. Row by
  row it is within $0.66 on 7 of 12; XRP 09-19 is $8.12 worse in the sim than
  live (tape 71c, we paid 63c); misses NEAR 09-16 (live belief 0.766, rebuilt
  0.804 at the boundary -> sim never fires, real -$16.00), DOGE 09-16 (dead
  feed), and in the two fastest collapses (BTC 09-14, HYPE 09-14) the bot paid
  **6-7c more** than the tape's top-of-book in the same second ($3.6 and $4.4
  per alarm) -- latency/slippage the tape cannot show.

### F4. The two 09-21 alarms, second by second: in both the market collapsed 1-3 s before our model; for HYPE the trigger level did not matter, for NEAR it was worth ~$38

Belief rebuilt from the index (within 0.05 of the live log at every logged
second); hedge price from exchange-time ticker; trades from the trade tape.

**HYPE 18:15 ET (KXHYPE15M-26SEP211815-15), first alarm under v-hedge25, net
-$31.27 vs -$53.97 unhedged (+$22.70 saved).**

| ET | tau | index | our belief | NO (insurance) price | what traded |
|---|---|---|---|---|---|
| 18:14:17 | 43 | 93.3974 (strike 93.3374) | 0.999 | 3.4c | **we buy 55 YES @ 98c** (filled at the ask) |
| 18:14:23 | 37 | 93.3678 | 0.996 | 7.7c | YES dumped 90-94c |
| 18:14:24 | 36 | 93.3521 | 0.982 | 10c | YES 72-92c |
| 18:14:25 | 35 | 93.3337 | 0.926 | 71c | YES 23-37c |
| 18:14:26 | 34 | 93.2778 | **0.216** (log 0.230) | 59c | **alarm, 55 NO @ 57c** (limit 58c, swept) |
| 18:14:28-33 | 32-27 | ~93.28 | 0.19-0.11 | 73-93c | |
| 18:14:50 | 10 | 93.28 | 0.000 | 99c | settles NO |

Belief fell 0.93 -> 0.22 in ONE second, so **0.60, 0.40 and 0.25 would all have
fired at 18:14:26 at the same price** -- v-hedge25 made no difference here.
A 0.20 trigger fires 2 s later at ~73c (+$14 instead of +$22.70). The market
was selling YES at 72-94c at 18:14:23-24 while our model read 0.98-0.996.

**NEAR 12:45 ET (KXNEAR15M-26SEP211245-45), A76 proportional, net -$59.09 vs
-$74.24 unhedged (+$15.15 saved).**

| ET | tau | our belief | NO price (depth) | event |
|---|---|---|---|---|
| 12:44:16 | 44 | 0.996 | 13c -> | **we buy 81 YES**, saw 95.5c, **filled avg 91.1c** -- YES was trading 62-71c in the same second |
| 12:44:17 | 43 | 0.853 | 39c (45) | |
| 12:44:18 | 42 | **0.575** (log 0.569) | 39c (44) | alarm; A76 buys **nothing** (>0.40) |
| 12:44:19-28 | 41-32 | 0.38-0.58 | 46-71c | belief wanders |
| 12:44:29 | 31 | 0.379 (log 0.392) | 74c | A76 half: **40.5 @ 70c** |
| 12:44:31-32 | 29-28 | 0.10-0.08 (log 0.123) | 90-92c | A76 rest: **40.5 @ 90.5c** |

Same position under the other rules (tape prices, hypothesis): 0.60 full at
12:44:18 ~+$45 (44 offered at 39c, rest at 46-47c); v-hedge25 (0.25) fires at
12:44:31 at ~90c, **~+$7** -- worse than what A76 actually got. Our fill itself
(4.4c under the ask we saw) was the first warning, 2 s before the belief alarm.

- **Mechanism, both cases.** The index prints once a second and lags the
  constituent exchanges; traders dump the contract 1-3 s before the index
  shows it. Any trigger on our own belief buys insurance AFTER the market has
  repriced -- which is why real saves pay 57-90c and recover only a third.

### F5. The hedge's biggest dollar failure was NOT RUNNING: the two largest losses of the hedging era had no hedge at all (bugs), -$174.28

- Since hedging went live (09-12 08:45Z): **12 lost markets, -$630.16
  unhedged**; the hedge brought them to -$480.93 (**recovered $149.23, 24%**).
  Two of the 12 never got a hedge attempt: BTC 09-19 02:00 ET **-$66.34** (trade
  loop crashed on `round(None)` while holding) and BTC 09-19 16:00 ET
  **-$107.95** (`--loss-cap` pause branch `continue`d past the hedge pass).
  Source: ledger + HANDOFF.md lines 478-480. Those two are 28% of all losses
  in the era -- more than the hedge's entire lifetime net in either direction.
  At the one-third recovery the hedge achieves, they would have been ~-$58
  less. HANDOFF records both as fixed; I did not re-audit the fix.

### F6. Alternatives to a hedge, measured on live fills only

1. **Exit by selling the position: identical to the hedge, not better.** On
   Kalshi a NO ask at p is a resting YES bid at 1-p -- one book. Checked on DOGE
   09-18: our NO hedge filled at 74c when the exchange-time YES bid was 26c.
   Same price, same depth, same fee formula (0.07*p*(1-p) is symmetric). The
   only difference is cash returned now vs at settlement minutes later.
2. **Not entering where alarms are likely.** No pre-entry feature on live data
   separates them with usable n. Since 09-12 08:45Z (565 markets): entries at
   tau >= 31 s (the 45-second leg) alarm at the same rate (7 of 196, 3.6% vs 11
   of 369, 3.0%) but LOSE twice as often (6 of 196 = 3.1% vs 6 of 369 = 1.6%);
   ledger **-$71.47** on the early entries vs **+$550.60** on the rest -- but
   -$107.95 of that is the unhedged pause-bug loss above; without it the early
   leg is **+$36.48**. Hedges on early entries: 6, **-$44.41**; on late: 11,
   **+$35.07**. Edge at entry >= 10c and price < 90c show 10% loss rates but
   both groups are still profitable (+$58, +$67). None of this clears 30
   closes of losses; hand to whoever owns the 45-second leg.
3. **A fill that comes back BELOW the ask we saw is the strongest live warning
   in the data.** Lifetime, 23 markets (22 closes) filled >= 3c under the ask
   seen: **7 lost (30%)** vs 12 of 724 (1.7%) otherwise -- 18x. Money:
   +$108.05 on the 16 winners, -$221.23 on the 7 losers, net **-$113.18**.
   Mechanism: between our book read and our order's arrival (80-330 ms) the
   book collapsed and sellers filled us below the ask -- we were the exit
   liquidity (NEAR 09-21: saw 95.5c, got 91.1c while YES traded 62-71c; BTC
   09-17: saw 97.8c, got **53c**; DOGE 09-18: saw 97.6c, got **11c**; BNB 09-19:
   saw 85c, got 75c). It cannot block the entry (it is only known after the
   fill), and all four such losers since 09-12 alarmed within 1-2 s anyway, so
   as a hedge trigger it buys ~1 s of warning. **What an immediate hedge would
   cost on the 11 winners could not be measured from live data** (no insurance
   price is logged at the fill second).
4. **"Hedge only if the market agrees" (insurance >= 40c at the alarm second,
   decided once, no waiting) does NOT hold out of sample.** Before the old
   `--hedge-price` gate shipped (11 alarms to 09-18): 11 of 11 classified right.
   After (7 alarms, 09-19..09-21): **3 of 7** -- BNB 09-19 01:45 real at 21c,
   NEAR 09-21 real at 39c, NEAR 09-19 17:15 false at 40c, XRP 09-19 false at
   63c. The live gate also failed on 09-19 23:45 for a mechanical reason: it
   re-checked every second (HYPE 37c -> 46c one second later -> hedged, -$49.66)
   and XRP's insurance was already 63c (-$67.22).
5. **Proportional (A76):** its one live alarm (NEAR 09-21) got +$15.15 where
   full-at-alarm would have got ~+$45 (tape, hypothesis). Already removed.

### F7. A market-led trigger ("hedge when insurance costs >= 30-40c") is NOT better than the current belief trigger

REPLAY-DERIVED: insurance price second by second for all 565 live positions
since 09-12 08:45Z from the ticker tape keyed on exchange time (207 hour files;
3 damaged, kept what parsed), quotes older than 3 s ignored, whole position
bought with per-second retries. Outcomes from the ledger.

| rule (whole position, bug losses excluded) | winners hit (closes) | on winners | on losers | NET vs never |
|---|---|---|---|---|
| insurance >= 20c | 23 (22) | -444.03 | +324.26 | -119.77 (incl. bug losses) |
| insurance >= 30c | 11 (10) | -225.80 | +256.33 | **+30.53** |
| insurance >= 40c | 6 (5) | -196.91 | +242.28 | **+45.37** (drop-one-close +28.06) |
| our side <= entry-20c | 14 (13) | -294.25 | +292.49 | -1.77 (incl. bug losses) |
| **belief < 0.25 (current), same tape + execution** | 2 (2) | | | **+101.41** |
| belief < 0.60, same | | | | +59.46 (~+79 without the dead-feed quote) |
| live, what really happened | | | | -9.35 |

- The market trigger fires on every one of the 12 losers but leads the belief
  alarm by a median of only **1 s** (range -1..+3 at 30c), and in that second
  the price is not reliably lower (HYPE 09-21: market trigger at 71c, belief
  alarm 1 s later at 57c). It also hits winners the belief never alarmed on --
  3 at 40c, 7 at 30c (BNB 09-16 21:15 -$39, NEAR 09-18 14:15 -$24, BNB 09-18
  04:45 -$15).
- Its apparent +$40-55 edge over what LIVE did comes from live execution
  failures since removed (A76 waiting on NEAR 09-21, the price gate on BNB 09-19
  01:45, 5 tries), not from better identification. Best of 9 rules tried --
  multiple looks, so even that is an upper bound.
- Artefact checks: same execution model and prices for both triggers;
  BTC 09-17 at its live alarm second prices at +$35.01 in the tape vs +$26.32
  live (the bot's first two tries at 63c and 66c did not fill -- the tape
  quote was not all real), so the tape flatters every rule a little.

### F8. v-hedge25 crossed a pre-registered floor without saying so, and the pre-registered bar is not met

- `results/PREREG_hedge.md` (09-14): **"Not below 0.30."** and a bar for moving
  the trigger off 0.80: (1) >= 10 hedge events settled after 2026-09-14, (2)
  0.30 ahead of 0.80 **on those events alone**, (3) **no single event more
  than half the difference**. The v-hedge25 commit (e7306e1) and its VERSIONS
  entry mention neither; they introduced a new test (drop-one) after seeing the
  result, on the same 16 alarms the dial was tuned on. (The earlier 0.80 ->
  0.60 move, v-hedge60, was on the operator's explicit instruction.)
- Checked on the 10 post-09-14 alarms in the table, corrected model (F3):
  **0.30 minus 0.80 = -$1.15** (condition 2 fails); **0.25 minus 0.80 =
  +$27.18 but NEAR 09-21 alone is -$38.10 = 140% of it** (condition 3 fails).
  Under the as-shipped top-of-book model both are negative (-$89.59, -$23.07).
  REPLAY-DERIVED.
- Money at stake is small either way (tens of dollars over 16 alarms), but the
  rule this breaks -- a bar is never moved after seeing a result without saying
  so -- is the project's defence against fitting to one close.

### Reconciliation with the other investigators' figures

- **Lifetime hedge value -$9.35 (this file) vs ~-$11 (elsewhere).** Rebuilt a
  second way from the bot's own settled rows: -$35.57 over 17 hedge rows, but
  BTC 09-17 21:15 (+$26.32 on the ledger) has NO settled row (restart while
  holding) -> -$9.25, within $0.10 of the ledger split. I could not reproduce
  -$11; the ledger split is the authority.
- **09-19 23:45 ET false alarms -$116.87** -- confirmed exactly (HYPE -$49.66,
  XRP -$67.22).
- **"Alarm fired ~2 s after a fill well below the ask seen" on HYPE 09-19 and
  NEAR 09-21** -- confirmed: HYPE 09-19 saw 97.5c, filled 94.1c (3.4c under) at
  03:44:27Z, alarm 03:44:29Z; NEAR 09-21 saw 95.5c, filled 91.1c (4.4c under)
  at 16:44:16Z, alarm 16:44:18Z. Note HYPE 09-19 was a FALSE alarm (the bet
  won): the adverse-fill warning is 7 lost of 23, not a clean separator (F6.3).

## 2. Refuted or not supported

- **"The 0.60 trigger was the worst of every option, including not hedging at
  all" (VERSIONS v-hedge25).** Not supported. -$35.33 of that row is hedges
  bought before we held the position (F3 fault 3), ~$20 is a 7.5-minute-stale
  quote (fault 2). Under live-like execution 0.60 is about break-even vs never
  (+$2.84 on 16 alarms).
- **"<60% (what we ran)" row.** Mislabelled: 8 of those 16 alarms ran at a 0.90
  or 0.80 trigger, 5 under the 60c price gate, one under A76. What we really
  got on those 16: **-$383.43** vs -$325.06 never hedging (-$58.37).
- **"0.25 is the most coverage the evidence supports" / "catches all 8 real
  losses".** As shipped it "caught" BNB 09-19 01:45 with 3 of 76 contracts and
  BNB 09-19 12:30 with 7 of 84.5 (top-of-book cap), so those two biggest losses
  were barely in its loss column. Corrected, 0.40 ties 0.25 and 0.20 reads
  best; 0.25 is a judgement call, not the data's answer.
- **"Nothing observable at the alarm second separates false from real" --
  partly contested.** The insurance price did separate them 11/11 before
  09-18, but only 3/7 after (F6.4). So the earlier statement stands in effect:
  nothing that has held OUT of sample.
- **"A hedge recovers about a third" -- CONFIRMED** (F2: -81c -> -54c a
  contract on the 10 hedged losses; 24% of all losses since 09-12 including
  the two unhedged ones).
- **"Unwinding does not work" -- consistent.** Selling = hedging on one book
  (F6.1); no alternative execution route exists that is cheaper.

## 3. Could not measure, and why

- **What an immediate hedge on an adverse fill would cost on the winners**
  (F6.3): the bot logs no insurance price at the fill second; only the tape
  has it, and the tape is not a source for our fills.
- **Whether v-hedge25 is better than 0.60 on LIVE money:** one alarm so far
  (HYPE 09-21, +$22.70), and belief fell through both triggers in the same
  second, so it cannot discriminate. Needs ~30 alarm closes.
- **hedgetune's 0.20 and below on BTC 09-17 21:15 and HYPE 09-21 18:15**: both
  missing from its table; at >= 0.25 they fire at the live alarm second (+$49.02
  to every trigger equally), below that unknown without a rebuild.
- **The DOGE 09-16 09:00 insurance path**: the ticker feed was silent for 7.5
  minutes; the real price exists only in the orderbook channel, not rebuilt
  (memory budget).
- **The fixes for the two unhedged 09-19 losses** (F5) were not re-audited.

## 4. Solutions worth testing

1. **Fix hedgetune before any further dial decision** (no live change):
   key prices on `msg.ts_ms`, refuse quotes older than ~2 s, start each path
   at our entry fill, hedge the whole position with per-second retries, take
   size and money from `kalshi_ledger.json`, and add the self-test this audit
   implies -- **reproduce the ledger's hedge value on the alarms where we
   really hedged, at the trigger that was live** (once corrected it is within
   $0.66 on 7 of 12). Blocks nothing.
2. **Reinstate PREREG_hedge's bar for v-hedge25** (VERSIONS gives it none,
   F8): count only alarms settling after 2026-09-21 20:12Z, compute hedge value
   per alarm from the ledger (YES/NO costs split, method in section 1), and
   keep 0.25 only if after >= 10 such alarms it is ahead of never hedging with
   no single close carrying more than half the result. Blocks nothing.
3. **Log, every second while a position is held, the insurance ask and size
   the bot sees** (from the book it already holds; no new reads, no gate). It is
   the missing LIVE series: today every question above about "what would the
   hedge have cost at second X" can only be answered from the tape, which F3
   shows is 2-6 s late in collapses and which the operator's rule excludes for
   our fills. It would also price F6.3 (an immediate hedge on a fill that comes
   back >= 3c under the ask seen) on our own data. Blocks nothing.
4. **Keep the belief trigger; do not switch to a market-price trigger** (F7:
   +$45 at best vs +$101 for belief < 0.25 in the same replay).
5. **Do NOT re-add a price gate on the strength of the 11/11 in-sample fit**
   (F6.4: 3/7 since). It would block hedges -- the class of change that cost
   09-19.
6. **If a trigger is moved again, 0.20 reads best in every corrected row**
   (+$101 vs +$45 at 0.25, walk model) -- but the difference is XRP 09-19's
   belief bottoming at 0.209 and ETH 09-12 at 0.23: two alarms. Not enough to
   move on; worth a paper arm (`arm-hedge20`) under the synced fleet, compared
   only on closes after 2026-09-22 06:21Z.

---
Resources at finish (2026-09-22): both collectors alive (kalshi_collector pid 105304, crypto_feeds pid 105352), RAM 1.56 GB free, disk 33.0 GB free. No process touched; only this file and the scratchpad written. Tape read by streaming single hour files (ticker, trade, cfbenchmarks_value); largest job 207 ticker hours in 52 s.
