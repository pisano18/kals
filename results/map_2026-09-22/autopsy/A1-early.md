# Autopsy A1-early -- three early losing closes (DONE 2026-09-22)

Investigator A1-early, 2026-09-22. Kalshi ledger nets per close. Times ET (EDT = UTC-4).

| close (ET) | close (UTC) | net | legs | status |
|---|---|---|---|---|
| 08-15 01:30 | 2026-08-15T05:30Z | -$19.00 | KXBTC15M | DONE: manual, not the bot |
| 08-22 21:15 | 2026-08-23T01:15Z | -$10.51 | KXBTC15M | DONE: manual, not the bot |
| 09-08 20:45 | 2026-09-09T00:45Z | -$52.60 | KXNEAR15M | DONE: late jump + thin confidence (fills 1-2), stale-index adverse fill (fill 3) |

## 08-15 01:30 ET -- KXBTC15M-26AUG150130-30, -$19.00 -- MANUAL, NOT THE BOT

- Ledger: 38.97 YES, cost $18.3159 (= 0.4700 exact), fee $0.6796, market_result NO. pinledger.pnl = -$18.9955.
- No live log contains it: the first `pinrun-live-*.jsonl` is 2026-09-08T06:20Z and the repo's
  first commit is 2026-08-25. `results/overnight/ACCOUNT_FORENSICS.md` sec 1.2/2 reconstructs it
  from Kalshi's order API: a `type: market` taker buy typed as a DOLLAR amount ($19.00 incl. fee),
  entered 01:19 ET (~11 min before close, t+~385s into the window), held to settlement; the third
  trade of a 45-minute Saturday-night session that re-funded the card three times.
- Index tape: none (cfbenchmarks_value starts 2026-08-25T04Z), so strike/window not reconstructable here.
- Cause: manual_or_not_bot. A coin-flip-priced (47c) mid-window market order with no model. Not
  avoidable by any bot rule; avoidable only by not trading manually. Rule cost on bot winners: n/a.

## 08-22 21:15 ET -- KXBTC15M-26AUG222115-15, -$10.51 -- MANUAL, NOT THE BOT

- Ledger: 12.37 NO, cost $10.3908 (= 0.8400 exact), fee $0.1164, market_result YES. pnl = -$10.5072.
  Kalshi settled it 14h20m late (2026-08-23T15:35Z).
- No live log (pre-bot, pre-repo). ACCOUNT_FORENSICS: `type: market` taker buy of NO at 84c at
  21:06 ET (~9 min before close), held. The public trade tape shows NO marked 0.999 with 38 s
  left and 0.05 thirty-six seconds later: BTC crossed the $77,305.87 strike in the last half-minute.
- Index tape: none for this date. Cause: manual_or_not_bot (the underlying event was a genuine
  late move through the strike, but no bot logic was involved). Rule cost: n/a.

## 09-08 20:45 ET -- KXNEAR15M-26SEP082045-45, -$52.60 -- THE BOT'S FIRST LIVE LOSS

Ledger: 59 NO, cost $52.23, fee $0.3723, market_result YES; pnl -$52.6023.

Live run `results/pinrun-live-20260909T000027Z.jsonl`. Start record: size 20, max_per_close 3,
pin 0.98, tau 3-30, price_ceiling 0.988, edge_floor 0.003, ev_floor 0.003 (measured_flip 0.009),
improve_by 0.005, loss_abort -$90, max_positions 4, sigma_stress 1.0, sigma_win 300.
code_sha 45383f2320bf = sha256 of `research/pinrun.py` at git 7df4582 (verified by hashing
`git show 7df4582:research/pinrun.py`). VERSIONS.md name: **v14** (22:47Z settings), code one
commit later (latency instrumentation; no separate VERSIONS entry).

Leg type: normal window leg (the only kind that existed; no early-45s leg, no late boost,
no hedge in this code). Three scale-in fills on one market, all NO:

| t (UTC) | ET | tau | model P(YES) | NO ask seen | filled | exec | note |
|---|---|---|---|---|---|---|---|
| 00:44:38 | 20:44:38 | 22 | 0.01826 | 0.930 | 0 | - | IOC canceled (offer gone) |
| 00:44:38 | 20:44:38 | 22 | 0.01826 | 0.958 | 0 | - | IOC canceled |
| 00:44:38 | 20:44:38 | 22 | 0.01826 | 0.962 | 20 | 0.962 | fill 1 |
| 00:44:39 | 20:44:39 | 21 | 0.01235 | 0.956 | 20 | 0.956 | fill 2 (scale-in, >=0.5c cheaper) |
| 00:44:43 | 20:44:43 | 17 | 0.00373 | 0.530 | 0 | - | IOC canceled; index_age 1.04 s |
| 00:44:43 | 20:44:43 | 17 | 0.00173 | 0.730 | 19 | 0.730 | fill 3; market said YES ~27-47c |

strike 2.3492, spot 2.3483-2.3484 at every signal (9 ticks = 3.8 bp below), sigma 0.000275-0.000278/s.
Settled YES; the three `settled` rows sum to -$52.61 (-1929.12c -1917.89c -1413.22c), matching Kalshi.
Loss-count brake (3 losing trades) halted the run at 00:45:50Z.


### The index (tape `cfbenchmarks_value/20260909T00`, NEARUSD_RTI, 60/60 window prints present, no duplicates)

- Settlement = mean of 00:44:00..00:44:59Z = **2.349367**, rounds to 2.3494 >= strike 2.3492 -> YES
  (Kalshi's own `avg_60s_data` at 00:45:00 reads 2.34936667 -- exact match). Won by 0.00017 (0.7 bp).
- Path: 2.3471 at 00:44:00, up to 2.3496 by 00:44:30 (market ~50/50), then **-0.0017 in one second at
  00:44:31** (tau 29) to 2.3478, flat 2.3483-2.3487 for 13 prints, then **+0.0021 at 00:44:44 (tau 16)**
  and **+0.0014 at 00:44:46 (tau 14)** to 2.3518, held ~2.3506-2.3515 to the close.
- Recomputed with pinrun's own formula (engine.var_factor, 300-s sigma, eff strike 2.34915) from the tape:
  fair = 0.01826 / 0.01235 / 0.00173 -- **identical to the bot's logged fair**. The bot's inputs were correct.
- Fill 1 (tau 22): 39 prints locked, running mean 2.348751 (1.9 bp under K), spot 2.3483 (3.8 bp, 9 ticks
  under), z = -2.09. The remaining 21 prints had to average 0.0016 above spot = 5.7x the 1-s sigma.
  They averaged 2.350510 (0.0022 above spot).
- Fat tails, measured in the same 300 s the model used: 3 one-second moves >= 4 sigma (-0.0015, +0.0012,
  -0.0017); a Gaussian expects 0.02. The killing move was 7.6 sigma.
- Index-only calibration (`results/calib_table.json`, pincalib, 1672 closes, all coins, NOT our loss rate):
  at z 2.09 the settle misses by that much 2.64% of the time (model says 1.83%); at z 2.92, 1.25% (model 0.17%).

### The market (tape `ticker` + `trade`, same hour)

- Our three fills are visible in the trade tape: 00:44:38.522 yes 0.038 x20, 00:44:39.383 yes 0.044 x20,
  00:44:43.274 yes 0.27 x19 (all taker NO).
- Fills 1-2: the market AGREED with us. Someone else sold 727 YES at 4.1c in the same second; YES then traded
  2.1-2.7c at tau 20-18 (market ~2-3% YES, i.e. slightly MORE sure than the model). No sign of an informed
  counterparty. Price paid 96.2/95.6c vs model 98.2/98.8% and index-history ~97.4/97.8%: still +EV by ~1-2c.
- Fill 3: at 00:44:43.004-.007 a buyer took ~740 YES from 9c to 44c -- **270 ms before our fill and ~1 s
  before the index printed the +0.0021 jump** (the 00:44:43 print was flat 2.3484; the jump published in
  the 00:44:44 print). The model, reading the last print, said 99.83% NO; the market said ~60-75% NO.
  **The market was right.** We sold YES at 27c into an informed buyer: stale-index adverse selection.
  The scale-in rule of that version (buy again if >= 0.5c cheaper, no upper bound) read a 23c collapse as
  "a better price".

### Cause

Primary **genuine_late_move** (fills 1-2, $38.47 = 73%): a 7.6-sigma one-second jump at tau 16 on a
market whose confidence (98.2%) sat right on the then-gate of 98%, 9 ticks from the strike.
Contributing: **model_overconfident** (Gaussian tails; z 2.09 is ~2.6% not 1.8% on index history),
**adverse_fill** (fill 3, $14.13: bought 0.8 s before the index showed a move the market already priced),
**sizing_amplified** (3 stacked fills, 59 contracts, $52 on a ~$154 bank, one market; averaging down).

### Rule cost on LIVE fills (773 entry fills, 547 closes, 751 won $1,265.93, 22 lost -$769.74, entry leg only)

| rule | blocks here | winners it also blocks | losers it blocks | net | status |
|---|---|---|---|---|---|
| confidence >= 99.5% (pin 0.995) | fills 1+2, $38.47 | 39 fills, $33.36, 35 closes | 3 fills, -$56.06, 2 closes | +$22.71 | LIVE since 2026-09-10 08:33Z |
| confidence >= 98.5% | fill 1, $19.29 | 19 fills, $11.19 | 1 fill (this) | +$8.10 | superseded by 0.995 |
| dump guard: ask seen > 15c below model | fill 3, $14.13 | 5 fills, $32.61 | 3 fills, -$28.41 | -$4.20 | LIVE (first start record carrying dump_enabled=true: 2026-09-12 02:23Z) |
| scale-in no more than 1c cheaper | fill 3, $14.13 | 3 fills, $5.36 | 1 fill (this) | +$8.77 | LIVE in the 09-22 start record (max_per_market 2, improve_max 0.01) |
| one fill per market | fills 2+3, $33.31 | 23 fills, $33.32 | 3 fills, -$34.98, 2 closes | +$1.65 | - |
| no buys above tau 20 | fills 1+2 | **532 fills, $816.10** | 18 fills, -$676.17 | **-$139.93** | NOT a fix |
| spot within 5 bp of strike | all 3 | **578 fills, $943.15** | 19 fills | **-$318.23** | NOT a fix |
| skip NEAR | all 3, $52.60 | 56 fills, $77.45 | 4 fills, 2 closes | +$49.40 | n = 2 losing closes; not evidence |

Every rule that would have caught this loss either is already live (pin 0.995, dump guard, 1c scale-in
band -- together they block all three fills) or rests on this one close. Nothing at the fill-1 second
separated it from the 39 winners at the same confidence.

**Side finding (related mechanism, current code):** the dump guard tests the ask SEEN, but the order goes
out with a sweep limit up to 98c, so it can fill far below the checked price. Fills that passed the guard
yet executed > 15c below the model: 5 won $40.38, 4 lost -$132.71 (4 closes) on live fills. A fill price
far under the ask seen is the same signal as fill 3 here (market knows, index has not printed).

## Verifier

Adversarial verifier, 2026-09-22. Own scripts and outputs under scratchpad `map/verify-A1-early/`
(`ledger3.py`, `vfills.py`, `vrules.py`, `idx.py`, `mkt.py`, `fair.py`, `cfnow.py`, `*.out`). DONE.

### 08-15 01:30 ET (KXBTC15M-26AUG150130-30) -- CONFIRMED, manual

- Ledger re-read: 38.97 YES, cost $18.3159 (0.4700 exact), fee $0.6796, result NO, pnl -$18.9955. Buy at
  05:19:05Z per ACCOUNT_FORENSICS 1.2 = 01:19 ET, 10m55s before the close. It predates the bot: first
  live log 2026-09-08T06:20Z, first repo commit 2026-08-25 06:17Z, no index tape before 2026-08-25T04Z.
- Small error in the write-up above: "t+~385s into the window" is wrong for this trade. 05:19:05Z is
  **t+245 s** into the 05:15Z window. t+385 s was the 08-22 trade. The cause is unaffected.

### 08-22 21:15 ET (KXBTC15M-26AUG222115-15) -- CONFIRMED, manual; the late-move detail is second-hand

- Ledger: 12.37 NO, cost $10.3908 (0.8400 exact), fee $0.1164, result YES, pnl -$10.5072; settled
  2026-08-23T15:35:37Z, 14h20m after the close. Buy 01:06:24Z = 21:06 ET, 8m36s before the close.
- "BTC crossed the $77,305.87 strike in the last half-minute" cannot be checked here: no index tape,
  and the ticker is not in `fulltape/markets.json`. It rests only on ACCOUNT_FORENSICS' trade-tape marks
  (best mark 0.999 at +478 s, worst 0.05 at +514 s). The manual attribution does not depend on it.

### 09-08 20:45 ET (KXNEAR15M-26SEP082045-45) -- DISPUTED: the cause is right, "no new rule needed" is not

Reproduced independently, all matching the autopsy:
- Ledger 59 NO, cost $52.23, fee $0.3723, result YES, pnl -$52.6023. Settled rows -1929.12c -1917.89c
  -1413.22c; `halt` "loss COUNT brake: 3 losing trades" at 00:45:50Z.
- Code: start record code_sha 45383f2320bf = sha256 of `git show 7df4582:research/pinrun.py`. That file
  has no hedge code, tau_max 30 (no early leg), and the rebuy test `price >= prev["best"] - IMPROVE_BY`
  refuses, i.e. at least 0.5c cheaper, no upper bound. Leg attribution (normal leg, two scale-ins) is right.
- Index (NEARUSD_RTI, 60/60 prints): settle mean 2.34936667 = Kalshi `avg_60s_data` exactly; strike
  2.349245 -> 2.3492. Moves -0.0017 at 00:44:31, +0.0021 at 00:44:44 (7.6 sd), +0.0014 at 00:44:46.
- Fair recomputed from the tape (300 s sd of 1-s moves, 7df4582 var_factor): 0.01826 / 0.01235 / 0.00373
  / 0.00173, identical to the logged signals. calib_table.json interpolated: z 2.091 -> 2.63%, z 2.923 ->
  1.25% (autopsy 2.64% / 1.25%).
- Market: 727 YES sold at 4.1c at 00:44:38.166; YES 2.1-2.7c at tau 20-18; ~748 YES bought 9c->44c at
  00:44:43.004-.007; our fill 3 at 00:44:43.274.

Where I disagree:

1. **Today's rules would still have bought this market and lost.** At 00:44:42.300 (tau 18) the book
   showed NO at 97.5c (7 at the top level). The model on the 00:44:42 print, which had arrived 0.23 s
   earlier, said NO 99.627%. Using the 2026-09-22T05:30Z start record, that quote passes every gate I
   could rebuild: pin 0.995, price_ceiling 0.98, EV (+1.4c), edge (+2.0c), dump (2.1c discount), jump
   gate (largest up-move in the last 3 prints 1.1 sd), depth floor 1.0, and index/book age. The "against"
   gate does not apply because spot was below the strike, on our side. The current `_sig_over` and
   `fair()` are the same formula, so the number is the same. v14 skipped this quote only because it
   already held 40 at 95.6c, and 97.5c was not 0.5c cheaper. Without fills 1-2 (pin 0.995 blocks them),
   this becomes today's first entry, one second before the jump, at today's much larger size. Only the
   hedge (belief 0.25) limits the damage: the model's NO belief is 40.6% / 45.8% on the 00:44:44/45 prints
   and 1.0% on the 00:44:46 print (`hedgechk.py`), and YES was trading 77-86c in that second.
   So "all three fills are blocked, no new rule is needed" is true of the three fills and false of the
   close. Not checked: whether max_positions or the close budget had room, because other coins in that
   close were not rebuilt. This is an eligibility statement from the tape, not a loss rate.
2. **"Index age at fill 3 was 1.04 s" is wrong.** 1.04 s is on the CANCELED 53c order, sent at
   00:44:43.043 before the 00:44:43 print arrived at .079. Fill 3's signal logs `index_age_s` **0.19**:
   the bot had the newest print. So the feed was not stale. The market moved about 1 s before the
   published index printed the move. The adverse_fill label stands; "stale index" overstates it.
3. **The side finding's "exec-price guard, +$92.33 if blocked" cannot be a pre-trade gate.** A buy
   limit fills at the best ask at or under the limit. A fill far below the ask we saw cannot be refused
   by any limit we send. The only possible response comes after the fill, for example an immediate hedge,
   and its value is that hedge's value, not +$92.33. The counts reproduce: 5 winners $40.38, 4 losers
   -$132.71, 4 closes.
4. **The 1c scale-in band was counted on the wrong prices.** Live `rebuy_ok` compares the ask seen with
   what we paid, and it exempts top-ups of an unfinished position. The autopsy compared exec price with
   exec price. Counted on the ask seen: it blocks 2 winners ($3.64, 2 closes) and 1 loser (-$14.13), net
   +$10.50, against the autopsy's 3 winners $5.36, net +$8.77. Small, and the direction is the same.

Rule-cost recount on live entry fills (own table, `vfills.py`): 775 fills, 549 closes, 753 won
$1,268.15, 22 lost -$769.74 (19 closes). The autopsy's 773 / 751 / $1,265.93 differ only by 2 winning
fills since its run. pin 0.995 (39 W $33.36 / 3 L -$56.06 / net +$22.71), pin 0.985 (+$8.10), dump on ask
(net -$4.20), one-fill-per-market (+$1.65) and skip NEAR (+$49.40) all reproduce to the cent. tau>20
(-$141.55) and 5 bp (-$318.83) move by the one extra fill each. Not verified: "~$154 bank"; there is no
bank field in that run's log.
