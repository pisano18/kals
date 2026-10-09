> **SUPERSEDED 2026-10-09 by results/FINAL_SYNTHESIS_2026-10-09.md** (blind design competition). Its two refusals (seller check, 5c cap) did NOT survive verification; only the insurance self-trade fix and the 5 Hz paper arm carry over. Do not use results/restart_bot.seen.ps1.

# The version that should run -- derived from everything, 2026-10-08 (written 10:1xZ)

Operator's order (10-08 ~09:2xZ): *"take EVERYTHING and consider EVERYTHING to derive what version needs
to be done to work ... create a version that wins as much money as possible once you calculate the
profits from losses ... know your limitations and how trustworthy your predictions and verifications are."*

Sources, in the project's order of trust: (1) our own live fills -- Kalshi's ledger joined to every live
log since 09-08 (`scratchpad/final/live_markets.jsonl`, 1,362 markets; built and reconciled to pinday to
the cent); (2) the raw index / trade / constituent feeds around every loss (`loss_anatomy.md`); (3) the
paper arms on shared closes (`paper_gates.md`); (4) nothing here rests on the replay. Outside the data:
Kalshi's docs and changelog, CF Benchmarks' methodology (`external_research.md`), two live checks of the
exchange's WebSocket run today. Every doc in the repo was digested (`docs_digest.md`). All numbers are
markets, never trades; every loss rate is from live fills. Times in this file are UTC.

## 1. Verdict in plain words

The bot has an edge and it is being eaten by one thing: **it buys offers that the market has already
seen through.** Lifetime it made +$701.78 on $66,379 bet (1.06 cents per dollar), 45 losing markets in
1,362 (3.3 in 100). The wins average $2 a market; a loss averages $45 and can be $130. At that shape the
bot can afford about 3 losses in 100 markets, so it sits at break-even: +$22.6/day lifetime, +$8.4/day
over the last 14 days, -$33 since the 10-04 revert.

The losing fills are identifiable AT DECISION TIME, on our own fills, by two things the model does not
look at: (a) the offer appeared less than half a second ago while takers were selling our side (an
informed seller dumping into us); (b) the price is more than 5c below what the model says it is worth
with 20-45 s left ("too good to be true" -- the market disagrees with the model, and the market is right
because it is reading the index 5 times a second while we read it once). A third thing -- a loss that is
a winning bet killed by insurance that was not needed -- is real but its fix has a pre-registered bar that
is not met yet; the insurance rule stays as it is.

**The version = the bot that runs now + the two refusals above + a self-trade fix for the insurance
order, then a 5-prints-a-second index feed proved in paper first.** The money estimate, in-sample on our
own fills since 09-24: the two refusals would have turned +$14.0/day into +$30.5/day (8 of the 15
losses refused, 23 markets in 100 skipped). The honest out-of-sample expectation is lower -- call it
+$10 to +$20 a day on the main pot (revised down 10-09: half the in-sample gain, and fewer offers -- 10-08 had 16 markets) -- because the thresholds were chosen after seeing those 15 losses.
The seller refusal has independent support (three paper windows); the price refusal has only our fills.

Side pots, measured: the ladder is the only strategy with zero losses and a measured way to grow
(+2.06 cents per dollar bet, 0 lost in 113 markets, supply allows about 5x now); the forecaster earns
the most per dollar but cannot grow past ~5x; the coin race cannot grow at all; the weather seller is
not yet positive.

## 2. What was measured (the evidence)

### 2a. The money record, by what the bot was doing (live fills, Kalshi money)

| window | markets | net | bet | per $ | lost | /day |
|---|---|---|---|---|---|---|
| all-time 09-08..10-08 | 1,362 | +$701.78 | $66,379 | +1.06% | 45 (3.3/100, CI 2.4-4.4) | +$22.6 |
| last 14 ET days | 462 | +$117.22 | $24,447 | +0.48% | 15 (3.2/100, CI 1.8-5.3) | +$8.4 |
| since the 10-04 revert | 192 | -$33.47 | $8,613 | -0.39% | 7 | -$8 |
| newer rules live 09-27..10-04 | 260 | +$157.33 | | +1.42% | 14 (5.4/100) | +$23 |

A 30-day bootstrap by close (potmath.py) of the LAST 14 DAYS' version: mean +$15, median +$44, 5th
percentile -$740, a losing month 46 times in 100. Of the all-time record: mean +$738, losing month 9 in
100. The current version is a coin flip; the earlier one was not.

### 2b. What separates our losing fills from our winning ones (own fills; n = markets)

| decision-time fact | markets | lost | net |
|---|---|---|---|
| offer level < 500 ms old (all rows with the field) | 622 | 25 (4.0/100) | +$58 |
| offer level >= 500 ms old | 478 | 7 (1.5/100) | +$596 |
| takers sold our side > 55% of the last 3 s (since 09-24) | 154 | 8 (5.2/100) | -$237 |
| takers sold our side <= 55% | 310 | 7 (2.3/100) | +$358 |
| model-minus-price > 4c with > 20 s left | 160 | 16 (10.0/100) | -$230 |
| model-minus-price 2.5-4c, > 20 s | 219 | 5 (2.3/100) | +$207 |
| model-minus-price 7-15c with < 20 s left | 49 | 3 (6.1/100) | +$258 (wide late edges PAY) |
| filled >= 3c UNDER the ask the bot saw (book collapsed) | 35 | 10 (28.6/100) | -$123 |
| first fill with <= 10 s left | 133 | 2 (1.5/100) | +$408 |
| first fill 21-30 s left | 454 | 18 (4.0/100) | -$67 (1st half +$172, 2nd half -$239) |
| price 93-95c (all-time) | 108 | 8 (7.4/100) | -$29 |
| price >= 98c (all-time) | 264 | 3 (1.3/100) | +$85 |
| Saturday | 253 | 13 (5.1/100) | -$167 all-time, but +$19 since 09-24: not stable |
| BTC | 256 | 10 (3.9/100) | -$44 all-time, +$57 since 09-24: not stable |

The model's own confidence is identical for losers and winners (0.9975 vs 0.9973): the model is not
wrong, the fills are adversely selected. Hours of day and weekdays were looked at and do not hold across
halves; no rule is proposed on them.

### 2c. Rules replayed on our own fills since 09-24 (525 markets, +$210.64 = +$14.0/day, 15 lost)

"$ saved" = money the refused markets actually made, sign flipped; "halves" = the saving in the first
and second half of the days (a rule that only works in one half is suspect).

| rule | refuses | losses caught | $ saved | halves | net after |
|---|---|---|---|---|---|
| seller check: level < 500 ms AND sold share >= 0.5, > 20 s (the twin's `--toxic-fresh`) | 97 (18%) | 6 of 15 | +$201 | +$90 / +$111 | +$412 |
| price refusal: model-minus-price > 5c, > 20 s (`MAX_EDGE_C` 10 -> 5) | 40 (8%) | 5 | +$168 | -$19 / +$187 | +$379 |
| both | 122 (23%) | 8 | +$247 | +$84 / +$163 | **+$458 = +$30.5/day** |
| both + no first leg at 21-30 s | 197 | 8 | +$156 | | worse: the window's losers are already caught |
| seller check at every tau (not only > 20 s) | 105 | 6 | +$189 | | same losses, 24 more refusals; paper says inside 20 s costs $18-21 and catches nothing |
| Saturday off / BTC off | | | -$19 / -$57 | | cost money since 09-24; dropped |

Which loss each rule flags (the 15 since 09-24): the seller check catches BTC 09-27 00:00 ET (-$131.98),
ZEC 10-07 (-$83.26), HYPE 10-04 (-$49.02), BNB 10-06 08:00 (-$16.16), BTC 10-06 (-$16.59), BTC 10-03
(-$13.01); the price refusal adds NEAR 10-03 (-$86.95, 5.5c under the model, no selling) and XRP 09-30
(-$42.60, swept 88->95c, 11c under). Neither catches HYPE 10-05 (-$73.88: 88% sellers but a 3-s-old
level; HYPE is skipped now), SOL 10-02 (-$41.11 at 19 s), ETH 09-27 (-$32.73 at 17 s, 83.5c), NEAR 10-06
(-$21.93, insurance), BNB 09-26 (-$20.29, book collapsed at 5 s), BNB 09-28 (-$8.26, 4.6c), BTC 10-04
(-$6.08).

### 2d. The same gates on the paper arms (independent population; paper cannot see adverse fills)

- Seller check, twin -> LIVE, 09-29..10-08, 823 shared closes: the twin refused 118 markets; live bought
  50 of them: 46 won +$49.44, 4 lost -$165.03 (ZEC, HYPE 10-04, BTC 10-06, BNB 10-06) = **saved $115.59**.
  arm-toxic -> LIVE 09-25..27: 18 won +$21.28, 1 lost -$131.98 = saved $110.70. While LIVE itself had the
  check (09-27..10-04): the twin bought 6 of its refusals, all won, +$6.49 = cost $6.49.
- Seller check INSIDE 20 s (arms toxic15 / toxic0, 10-03..10-08): cost $18.64 / $20.58, caught nothing;
  their pre-registered bar is NOT met. The check stays at > 20 s.
- 97.8c cap on the 45-s leg: ~180 refused markets, no loser among them, cost ~$1-5/day: stays at 98c.
  0.95 vs 0.90 early floor: about $0. One-full-bet cap: cost $17 in 6 days on paper, 0 saved on paper --
  kept on its LIVE evidence (11 second full bets ever, 2 lost, both same-second BTC). Jump/spike gates ~$0.
- Insurance: 0.40 beats 0.20 and none on paper; on our fills the hedge leg is +$143 lifetime (21 real
  +$448.57, 13 false alarms -$305.54). Keep 0.40. The "skip insurance when the price is only a hair
  through the line" ruler (`results/PREREG_hedge_margin.md`, +$151 in-sample on 3 events) reads after the
  next 5 hair-over alarms, not before 10-10; nothing changes until then.
- Arm vs arm, 400 shared closes 10-03..10-08: twin +$128 (3 lost), 0925b +$179 (5 lost), 0914 -$16,
  LIVE -$31 (7 lost) -- same code as 0925b, $210 behind it: the gap is the fills paper never sees.

### 2e. Two facts from outside our data, verified on the exchange today

1. **Kalshi streams the settlement index 5 times a second** (`cfbenchmarks_value_5hz`, changelog
   2026-09-03; CF methodology v17, 200 ms calc since 2026-05-18) for BTC, ETH, SOL, XRP and DOGE; ZEC, BNB,
   HYPE, NEAR stay at 1/s. Measured 10-08 10:0xZ over 20 s: 5.00 prints/s on the five, the top-of-second
   prints IDENTICAL to the 1 Hz channel's (180 of 180 equal, none missing), and the 5 Hz frames arrive
   40 ms sooner (median receipt lag 58 ms vs 98 ms; the 1 Hz frame carries the 60-s average payload).
   Our bot reads once a second (`IndexWS`, `cfbenchmarks_value`). A seller watching the 5 Hz feed sees a
   move up to 800 ms before we do -- the "too good" offers of 2b are what that looks like from our side.
   The settlement series is unchanged (the 60 :000 prints), so a bot on the 5 Hz feed keeps the same
   locked sum and gets a fresher spot. Not measurable from our recordings (we never recorded 5 Hz).
2. **Self-trade prevention is per order and applies across subaccounts**, and the book is unified (a
   YES bid at 98c IS a NO ask at 2c). `pintake.STP` is `taker_at_cross`: an insurance IOC from the main
   account that would cross the ladder's resting bid in subaccount 1 is CANCELLED, not filled. Checked on
   all 14 insurance orders since 09-28: the ladder's bids came 4-29 s AFTER each one, so it has not
   happened; the race exists by design (a late insurance order would hit it). Fix: insurance orders carry
   `maker` (the ladder's stale bid is cancelled instead, which is what the ladder wants at that moment).
   Also from outside: the index is an order-book mid, uncrossed, a martingale by construction; ZEC and
   BNB have only two constituent exchanges (Coinbase, Kraken), HYPE three -- the thinnest indices are our
   worst adverse-fill coins; Kalshi's volume incentive ($0.005/contract on 3-97c trades) ends 10-13
   (no credits found in our transfers); a CFTC rule on event contracts went to OMB 09-28 (text
   unpublished); nothing announced that delists or changes the 15-minute series.

### 2f. The raw feeds around every loss (kalshi_data / feed_data around our own fills)

Every live loser since 09-08 (42 markets, -$1,539) against 120 winners matched on time-left and price,
rebuilt from the raw index, trade tape, order book and constituent exchange books (the agent's report
was cut off by a usage limit after writing `scratchpad/final/loss_anatomy.md`; its tables are complete,
its settlement cross-check matched the ledger on 162 of 162 markets; 6 tape hours missing 09-23/24).
- What the losses were: 25 index jumps (-$1,040) -- 14 began within 1 s of our send (we bought into
  the start of the move), 11 began later (nothing visible when we bought); 12 insurance false alarms
  (-$236: the bet won, the insurance lost); 3 photo finishes (-$126); 1 stale feed; 1 unmeasured.
- Signals at the send that separate losers from the matched winners (37 looks; the multiple-looks bar
  is p < 0.0014): the index already moving against us over the last 3 s (>= 2 sd: 8 of 41 losers vs 2
  of 117 winners, p 0.0003); a constituent exchange book moving against us in the last 3 s (13 of 21 vs
  12 of 73, p 0.0001; recorded for BTC/ETH/SOL/XRP/DOGE only); the 09-27 seller check (13 of 29 vs 13
  of 83, p 0.0022). Bot confidence, offer age alone, size offered, trade counts: no separation.
- So the losses are mostly the index moving in the second we buy, and the people selling to us see it
  first -- on the exchange books and on the 5-per-second index we do not read.
- **Checked on EVERY filled market (1,331 with index windows, `idxmove.py`), not a matched sample:**
  the 3-s move ending at the newest print the bot actually HAD at the send does NOT separate losers
  (09-22..10-08, 580 markets with ms send times: >= 2 sd refuses 14, catches 1 of 16 losers, first half
  negative). The same move ending at the print OF the send second does (>= 2 sd: 20 refused, 4 of 16
  losers, +$95, both halves) -- but for ETH 09-27, BNB 09-26 and BTC 10-04 that print (a 4.5-6.9 sd
  move against us) reached us 20-40 ms AFTER our order went out. That is look-ahead on the 1/sec feed
  and the reason for the 5/sec arm. No index-side gate on the 1/sec feed goes into v-seen (this
  matches the project's record: every index-side gate lost money on our fills). Also checked and
  dead: the bot's own print age at the send (1.0-1.2 s old: 172 markets, 2.3/100 lost, +$122).

### 2h. The 10-08 ET day (after this file was first written)

+$20.64 on 16 markets, 0 lost (+3.4% on $613 bet). Low supply, not a brake: 757 refusals were "no offer
at all". The paper copies on the same closes: twin +$26.24 (17 markets), 09-25 copy +$31.10 (23).

### 2g. Side pots (Kalshi subaccount settlements, reconciled to each balance)

| pot | window | markets | net | per $ bet | lost | of pot | can it grow |
|---|---|---|---|---|---|---|---|
| ladder (sub 1, post-only 98c bids) | 09-29..10-08 | 113 | +$12.94 | +2.06% | 0 | +19.9% in 9 d | supply-limited: 5x -> ~2.8x the contracts (~$4/day on ~$350); 20x -> ~14x ($14-20/day on ~$1,400); one losing close at 20x = -$98 |
| forecaster (sub 2, IOC, crash guard) | 09-29..10-08 | 74 | +$27.94 | +8.0% | 11 | +54.8% in 10 d | adverse-selection-limited: fills flat to 11/side, depth median 45; since r28 (10-03) 15 mk, 1 lost, +25% -- small n |
| coin race (main, 20 a leg) | 09-21..10-08 | 169 races | +$23.32 | +2.06% | 5 (2 ties) | | NO: contracts got fell 94 -> 31 per 100 as size rose 1 -> 40; -$4.23 since the $40 cap |
| weather dip-seller (sub 3) | 10-04..10-08 | 13 | -$0.27 | -1.8% | 5 | -0.5% | not until positive (bar needs 60 fills, has 13) |

## 3. The version -- `v-seen` ("refuse what the market has already seen")

**Live, main pot, build `C:\kals-live-0925e` = today's `0925d` + two small code patches:**
1. `--toxic-fresh` ON (defaults: level age < 500 ms AND sold share >= 0.5, only with > 20 s left).
   Already in the build (self-test passed with it on 10-07, `results/restart_bot.toxic.ps1`).
2. Price refusal 10c -> 5c with > 20 s left: new flag `--max-edge-c 5.0` (today a constant,
   `MAX_EDGE_C = 10.0`, applied through `edge_cap_block` only above `EDGE_CAP_TAU = 20`), and
   `--early-max-edge 10.0 -> 5.0` for the 45-s leg. Inside 20 s nothing changes (wide late edges pay).
3. Insurance orders carry `self_trade_prevention_type = maker` (`pintake.take(..., hedge=True)`).
Everything else exactly as now: one full bet per coin, HYPE skipped, 98c ceiling, 0.90 early floor,
insurance at 0.40, -$200 run / -$200 day / 2-loss pause, size bank/11.76 (`--bank-brake 4.00`).

**Built and verified 2026-10-09 05:0x-05:1xZ (nothing deployed):** `C:\kals-live-0925e`,
code_sha 5075b1783acf. `pintake.py --selftest` PASS (new check: the entry goes out
`taker_at_cross`, the insurance `maker`); `pinrun.py --selftest` PASS (new check on the 5c cap); the
startup path in PAPER with the exact live argv PASS -- after one fix: an old check asserted the RUNNING
10c cap and refused to start under `--max-edge-c 5.0` (the 09-18 `--price-ceiling` outage pattern;
now asserted against the declared default); the start record carries `toxic_fresh true, max_edge_c 5.0,
edge_cap_tau 20, early_max_edge 5.0`. `results/restart_bot.seen.ps1 -Check` PASS (73 flat strings,
code_sha matches). Revert file `results/restart_bot.before-seen.ps1` = today's launcher.

**Paper (no money):**
- `arm-5hz` STARTED 2026-10-09 05:23:01Z, pid 1685096 (`results/start_arm5hz.ps1`): the twin's exact
  argv + `--index-5hz` on a copy of the twin's code (`C:\kals-arms\arm-5hz`, code_sha 61c71ec1672f):
  also reads the 5-per-second index; the newest sub-second print sets the projection price;
  settlement prints unchanged (self-test: a sub-second print never enters the settlement series).
  Bar pre-registered in READS_DUE `arm-5hz` (10-14): fewer losing markets than the twin and money
  within $40 -> propose a live port.
- `arm-late15` (full leg only inside 15 s, a supply measurement): NOT started -- RAM is short (1.3-3 GB
  free) and it measures supply, not losses; next if wanted.

**Side pots:** ladder to 5x (needs about +$285 in subaccount 1; bar: <= 1 losing market in the first
150 filled at 5x, then consider 20x); forecaster to 2x (+$50 in subaccount 2; bar: >= +4% per dollar bet
over 60 markets with <= 8 losers); coin race stays at 20 a leg; weather seller stays at $50.

## 4. What it should be worth, and how sure

- Main pot: in-sample +$30.5/day on the since-09-24 fills vs +$14.0/day without the two refusals.
  Expect +$10..20/day out of sample (revised down 10-09). The seller refusal: three independent paper windows (+$116, +$111,
  -$6) plus both halves of our fills -- the most trustworthy number in this file. The price refusal: our
  fills only, savings concentrated in the second half -- half-trusted. Together they skip 23 markets in
  100 and give up about $14/day of wins to avoid about $28/day of losses.
- What it cannot do: a loss still costs $50-85 (5-8% of the pot); 7 of the 15 recent losses would still
  have happened; a day of -$80 remains normal. It does not change the hedge false alarms (3 of the last
  week's 9 losses) -- that waits for its bar.
- The edge is decaying: the 21-30 s window went from +$172 to -$239 between the two halves of the
  record, offers at our confidence halved on 09-22, and the market now has a 5 Hz feed we do not read.
  This version buys time; the ladder (maker side) is the direction if the taker edge dies.
- Not done, and why: no size change (the size is the operator's risk limit; after the bar); no ceiling
  above 98c (>= 98c fills lose 1.3/100 vs a 1.4/100 break-even at 98.5c: a wash); no coin or weekday
  rule (not stable across halves); no cut of the 21-30 s window (the gates catch its losers; cutting it
  on top loses $90); no change inside 20 s (paper bar failed); no hedge change (bar pending).

## 5. Pre-registered bar for `v-seen` (written before deploy; the read is in READS_DUE)

Read 2026-10-15 12:00Z (7 ET days) and again at 300 markets, from Kalshi's ledger:
- **KEEP** if net >= +$10/day AND losing markets <= 2.5 per 100 (lifetime 3.3).
- **REVIEW** if net is between $0 and +$10/day, or the two refusals together skip more than 35 markets
  in 100 (supply has shifted under the gate).
- **REVERT** (to 0925d, `results/restart_bot.before-seen.ps1`) if net <= $0 over the 7 days, or two
  losing markets in one ET day that neither gate flagged and that the twin also bought (the gates are
  not the lever).
- Report alongside: the refused markets (gate name) and what they did, from the twin on shared closes;
  copy noise is $18-40 over a few days, so a twin lead under $40 means nothing.
What would falsify the thesis: the twin (same gates, paper) keeps winning while live loses on markets
the gates passed -- then the loss is in the FILL (size, sweep), not the offer, and the next lever is
"buy only the first price after a dump" (F28) and no sweep headroom at > 20 s.

## 6. Housekeeping found on the way (not money, but the deadline)

Free disk 23.0 GB at 10:05Z (recorders ~5 GB/day; guard 6 GB). Reclaimable: my tool's temp cache
`%LOCALAPPDATA%\Temp\claude\bash-edit-diff` 8.6 GB (Claude's own; safe to clear), Windows restore points
6.8 GB (max 17.6 GB; operator's call, `vssadmin delete shadows`), the swap file is 14.2 GB and grows with
memory pressure (commit 24 GB of 30). RAM free 1.7-2.8 GB; ntopng restarted 10-07 23:13Z.
