# 10 -- Loss autopsy synthesis: every losing close, its cause, and the rule that would have stopped it

Synthesizer over 7 autopsy groups (A1..D1), each checked by an independent verifier.
Where the verifier disputed the autopsy, the verifier's version is used and marked **(V)**.
All times ET (EDT = UTC-4). Data stays UTC.

**Sources.** Money: Kalshi's ledger (`results/kalshi_ledger.json` through `research/pinledger.pnl`, 847 rows, last settlement 2026-09-22 08:00Z).
Fills: my own table built from the 124 `results/pinrun-live-*.jsonl` files (`order` rows with filled > 0, joined to the preceding `signal` row and to the ledger):
**775 entry fills, 749 markets, 549 closes, 09-08 07:59Z .. 09-22. 753 winning fills +$1,268.15; 22 losing fills -$769.74 over 19 closes.**
This matches the verifiers' tables exactly (A1 verifier: 775 / 549 / +$1,268.15 / -$769.74).
The hedge table I built from the ledger matches the C2 verifier exactly: 17 hedged markets, 16 closes; 10 saves +$149.24; 7 false alarms -$158.59; **net -$9.35 lifetime.**
Scripts: scratchpad `map/10/` (fills.py, era.py, pat.py, rules.py, hedge.py, nocap.py).
Tape facts (what the index and the market did) come from the autopsies and verifiers. None of them is a loss rate.
Every loss rate and every rule cost below comes from live fills.

---

## 1. Every losing close

Money is the close net from the ledger. The losing market's own figure is in brackets when a sibling market in the same close won.

| Close (ET) | $ net | Coin | Leg | Version (code) | Primary cause | Verifier | Conf |
|---|---|---|---|---|---|---|---|
| 08-15 01:30 | -19.00 | BTC | manual market order, 39 ct at 47c | none; before the bot and the repo | manual_or_not_bot | confirmed | high |
| 08-22 21:15 | -10.51 | BTC | manual, 12 ct at 84c | none | manual_or_not_bot | confirmed | high |
| 09-08 20:45 | -52.60 | NEAR | normal, 3 stacked fills, 59 ct | v14 (7df4582), pin 0.98 | genuine_late_move | **disputed on the fix**, cause agreed | high |
| 09-10 01:00 | -12.83 (XRP -16.61) | XRP | normal, 20 ct | eab677e, no VERSIONS entry | adverse_fill | confirmed; mechanism corrected | high |
| 09-10 01:30 | -16.89 (BNB -17.60) | BNB | normal; 2nd fill of the close via cross-market scale-in | eab677e | model_overconfident | **disputed mechanism**, cause kept | high |
| 09-10 18:15 | -2.12 | DOGE | normal, 20 ct | v-pin995 (d581522) | adverse_fill | confirmed | high |
| 09-11 08:30 | -12.16 | SOL | normal, 20 ct | v-a10b (435994a) | model_overconfident | confirmed | high |
| 09-11 23:00 | -17.17 (SOL -19.61) | SOL | normal, 20 ct | v-a12a (5e8db5f) | genuine_late_move | confirmed | high |
| 09-12 04:00 | -17.95 (SOL -18.88) | SOL | normal, 20 ct | A13+A14 (02c9ec5), no entry | model_overconfident | confirmed | high |
| 09-12 11:00 | -1.09 | BTC | normal; hedge at belief 0.90 | be72eda, no entry | hedge_failure (false alarm; the bet won) | confirmed | high |
| 09-12 11:15 | -5.16 | ETH | normal; hedge at belief 0.90 | be72eda | hedge_failure (false alarm; the bet won) | confirmed | medium |
| 09-12 20:00 | -8.20 (ZEC -8.63) | ZEC | normal, 11 ct | v-a15 (9205ae4) | adverse_fill | confirmed | medium |
| 09-14 05:30 | -34.26 | BTC | normal, 60 ct | v-ladder (d0c3d60) | model_overconfident | confirmed | high |
| 09-14 16:00 | -29.90 | HYPE | normal; sweep 52 -> 62 ct | v-nofloor | genuine_late_move | **disputed** (the hedge counterfactual) | high |
| 09-16 04:30 | -9.22 | NEAR | normal; sweep 9 -> 84 ct | v-withdraw, hedge 0.80 | hedge_failure (false alarm; the bet won) | confirmed | high |
| 09-16 09:00 | -12.14 | DOGE | normal, 87 ct | v-withdraw, hedge 0.80 | hedge_failure (false alarm; the bet won) | **disputed** (rule dollars) | medium |
| 09-16 12:30 | -0.47 | BNB | normal, 1 ct | v-hedge60 | genuine_late_move | confirmed | high |
| 09-17 21:15 | -15.79 (BTC -27.87) | BTC | **EARLY**, 99 ct | v-early-full | **genuine_late_move (V)**; the autopsy said adverse_fill | **DISPUTED CAUSE** | medium |
| 09-19 01:45 | -57.76 | BNB | normal ('full'), 76 ct | v-latebudget (7ab67e0) | adverse_fill, plus the hedge-price gate | **disputed** (rescue dollars) | high |
| 09-19 02:00 | -62.28 (BTC -66.34) | BTC | **EARLY**, 70 ct | v-latebudget | model_overconfident, plus a crash with no hedge | confirmed | medium |
| 09-19 12:30 | -61.75 | BNB | normal; sweep 23 -> 114 ct | v-mirror (277be1f) | sizing_amplified | confirmed | high |
| 09-19 16:00 | -107.95 | BTC | **EARLY**, 110 ct at 98c | v-taper + v-cap200 (dea19ed) | genuine_late_move, plus a pause that skipped the hedge | confirmed; one sub-claim refuted | high |
| 09-19 23:45 | -108.86 (XRP -64.95, HYPE -43.92) | XRP + HYPE | **EARLY**, 104 ct each; **both bets won** | A74 v-hedgefill (8dd7fe6) | hedge_failure (two false alarms) | confirmed | high |
| 09-21 12:45 | -59.09 | NEAR | **EARLY**, 81 ct | v-nocap + v-proportion (6ff3cce) | adverse_fill | **disputed** (the proposed gate fails) | high |
| 09-21 18:15 | -31.27 | HYPE | **EARLY**, 55 ct at 98c | v-hedge25 (e7306e1) | genuine_late_move | confirmed | high |

**Not autopsied, all under $1.10 or outside the pin bot:**
- 09-13 12:30 BNB -1.10: a hedge false alarm inside a close that netted positive.
- 09-06 21:45, 09-06 22:00, 09-07 01:15, 09-08 03:15 and 09-15 16:30: $0.00-0.02 each, manual or coin race.
- Coin race 09-21 09:30 (-0.86) and 16:15 (XRP race -0.87).
- A manual daily-BTC bet `KXBTCD-26AUG1501` (-$19.00, 08-15). It is not a 15-minute market and was missing from the close list.
- The commodity bot: 8 losing markets, -$122.09 lost, -$108.06 net, 09-10..09-18. It is a different bot and is out of scope.

**Pin bot totals, ledger:** 749 markets, **+$1,249.64 won, -$762.44 lost over 25 losing markets, net +$487.20.**

---

## 2. By cause and by era

The eras are by close date: **A** is before 09-12, **B** is 09-12..09-18, **C** is 09-19 onward. Dollars are the losing MARKETS' ledger P&L, pin bot only (the 25 losing markets, -$762.44).

| Primary cause | A: n / $ | B: n / $ | C: n / $ | Total n / $ |
|---|---|---|---|---|
| genuine_late_move | 2 / -72.21 | 3 / -58.24 | 2 / -139.22 | 7 / -269.67 |
| model_overconfident | 2 / -29.76 | 2 / -53.14 | 1 / -66.34 | 5 / -149.24 |
| adverse_fill | 2 / -18.73 | 1 / -8.63 | 2 / -116.85 | 5 / -144.21 |
| hedge_failure (every one a false alarm on a WINNING bet) | 0 / 0 | 5 / -28.71 | 2 / -108.87 | 7 / -137.58 |
| sizing_amplified | 0 | 0 | 1 / -61.75 | 1 / -61.75 |
| **losing markets** | **6 / -120.70** | **11 / -148.72** | **8 / -493.03** | **25 / -762.44** |
| markets traded (ledger) | 164 | 407 | 178 | 749 |
| won on the other markets | +130.31 | +735.81 | +383.52 | +1,249.64 |
| **era net** | **+9.62** | **+587.09** | **-109.51** | **+487.20** |

The same eras measured on live fills (my table):

| | A | B | C |
|---|---|---|---|
| markets whose ENTRY lost, per 100 traded | 3.7 | 1.7 | 3.4 |
| markets losing on the LEDGER (with hedge false alarms), per 100 | 3.7 | 2.7 | 4.5 |
| contracts per market | 16.8 | 49.3 | **75.0** |
| average price paid | 93.60c | 95.62c | **96.59c** |
| margin, i.e. what a winning contract pays | 6.40c | 4.38c | **3.41c** |
| share of contracts that lost | 5.72% | 1.43% | **3.57%** |
| average $ per losing fill | -15.09 | -29.46 | **-63.26** |
| average $ per winning fill | +0.81 | +1.82 | +2.14 |

**Which cause classes grew after the changes meant to grow the bot:**

- **The loss FREQUENCY did not grow. The loss SIZE and the margin did.** A losing fill cost 4.2x more in C than in A: contracts per market went 16.8 -> 75. A winning fill earned only 2.6x more, because the margin fell 6.40c -> 3.41c.
  - In C the contract loss share (3.57%) is above the margin (3.41c), so era C lost money.
  - B's low loss rate was a calm market. The 09-market report measured the market's own upset rate at 4.8% in B against a 6.2-6.9% median. So the losses that came back in C are ordinary; they only look new against B.
- **New in C:**
  - **sizing_amplified**, from the sweep ladder: 09-19 12:30, about $45 of $62 per the verifier.
  - Three **contributing** classes, all from changes shipped 09-19 and all fixed since:
    - the process crash (09-19 02:00, ~$29-31);
    - the loss-cap pause that skipped the hedge (09-19 16:00, $16-25, upper bound);
    - the hedge-price gate (09-19 01:45, $0-54, verifier range).
- **Grew most in dollars:**
  - **hedge_failure**: $0 in A, -$28.71 in B (5 markets, average $5.74), -$108.87 in C (2 markets, average $54.44). Full-size hedges bought at the top of a spike turned two winning early bets (+$8.01 on the bets) into -$108.87.
  - **adverse_fill**: -$9.12 per market across A and B (3 markets), -$58.43 per market in C (2 markets).
- **The early (31-45 s) leg** carries 5 of the 8 losing markets in C, -$373.52 of the -$493.03 (76%), on 63% of C's fills. Its loss RATE is not higher: 6 losing fills in 203 (2.96%) against 3 in 111 (2.70%) for the other legs since 09-17 13Z. Its MARGIN is lower: in C the early leg paid 96.91c with 3.09c margin against a 3.61% contract loss share, i.e. below break-even; the other legs paid 95.98c, with 4.02c margin against 3.49%.

---

## 3. What the losers have in common that the winners do not (checked on live fills)

Unit: entry fills, 775 in total (22 losers), with markets and closes given. I tested about 35 cuts, so any single cut that isolates 3-6 losers can be chance. A hypergeometric p is given where a feature separates.

**Things the losers do NOT have in common (refuted on live fills):**

- **The model's stated confidence.** Loss rate by z bucket:
  - 0-2.576: 3 / 42 (7.1%)
  - 2.576-2.75: 6 / 268 (2.2%)
  - 2.75-3.0: 6 / 193 (3.1%)
  - 3.0-3.5: 4 / 135 (3.0%)
  - 3.5+: 3 / 137 (2.2%)

  The model claims losses fall from about 0.5% to under 0.02% across these buckets; live, they sit at about 2-3% throughout. Inside the gate, stated confidence carries no information about which fill loses. This is the "model_overconfident" label in all 25 closes, **common to winners and losers alike**, and it is why the strategy loses about 3 bets in 100 however sure the model says it is.
- **Size.** Fills of 60+ contracts lose 8 / 299 (2.68%) against 2.94% for the rest. Size multiplies the dollars, not the frequency.
- **Sweep-grown fills** (size more than 1.5x the touch): 4 / 208 (1.92%) against 3.17%.
- **Distance to strike.** Under 3 bp: 15 / 431 (3.48%) against 2.03%. Blocking those fills costs $88.08 net: 416 winners +$656.46 against 15 losers -$568.39.
- **The market disagreeing with the model** (market risk 20x the model's or more): 10 / 334 (2.99%) against 2.72%.

**Things that DO separate:**

1. **Price-through: the fill came in below the ask the bot saw.** Filling at 2c or more below the ask seen: **7 of 28 fills lose (25%) against 15 of 747 (2.0%)**, p = 4e-6; at 10c or more below, 6 of 9 lose. It is the signature of the book collapsing between the decision and the order's arrival, and it appears in 09-10 01:00, 09-10 18:15, 09-17 21:15, 09-19 01:45 and 09-21 12:45. **It is known only after the fill**, so no entry rule can use it. Only an instant hedge can, and the D1 autopsy's top-of-book estimate of such a hedge on those 28 fills recovers about +$8 (tape, optimistic). The 28 flagged markets net -$102.69 on the ledger.
2. **The offer was fresh (level age < 250 ms), on the early leg.** Early fills on levels resting < 250 ms: **6 of 86 lose; on levels >= 250 ms: 0 of 116.** Every early losing fill had a level age of 15-89 ms. p = 0.005 for one look.
   - The 250 ms threshold was set on 09-13 in `RESULTS_select.md`, before the early leg existed. `pinrun.py` has logged the field since then as a pre-registered forward record ("LOGGED, NEVER GATED ON").
   - Across ALL legs, the pre-registered test gives 10 of 231 fills < 250 ms losing (4.33%) against 2 of 281 (0.71%), p = 0.007. On the non-early legs, though, it does not pay: 141 winners +$356.28 against 4 losers -$141.77.
   - Mechanism: a level that appeared in the last quarter-second at a price the bot likes exists because someone just repriced on information the 1/s index has not printed yet. That is the same ~1 s market-leads-index pattern the verifiers measured in 7 of the losses.
   - At 31-45 s there is time for that information to arrive. In the last 30 s, cheap fresh offers are mostly our best winners.
3. **The market led the index by about 0.3-1.1 s** in 09-10 01:00, 09-10 18:15, 09-12 20:00, 09-14 05:30, 09-19 01:45, 09-19 12:30 and 09-21 12:45 (tape, per the autopsies and verifiers). **Nothing the bot can see before the send separates this from winners.** A2 verifier: a tell restricted to trades the bot could have seen gives 17 winners +$79.78 against 2 losers -$30.74. D1 verifier: the trade-tape proxy flags 0 losers once its window ends at the send.
4. **Hedge alarms on winning bets.** 7 of the 17 hedged markets were false alarms: -$158.59 against +$149.24 saved on 10, so hedging is net -$9.35 lifetime. The 09-19 23:45 close alone is 73% of the false-alarm cost.

---

## 4. Prevention rules, ranked by net dollars

**How to read it.**
- Rule costs come from live entry fills: saved = minus the losing fills' entry P&L; blocked = the winning fills' entry P&L.
- "Ledger" = Kalshi's net for markets where every fill is blocked, so it includes the hedges.
- Rules marked (V) or (A) are the verifier's or the autopsy's measured numbers, not mine.
- **Rows 1-6 hit the same 6 early-leg losing closes. They overlap and are NOT additive.**

**Not live (candidates, all post-hoc, all under the 30-close floor):**

| # | Rule (cause class) | Winners blocked | Losses avoided | Net entry | Net ledger | Losing closes |
|---|---|---|---|---|---|---|
| 1 | Early leg: refuse a level resting < 250 ms (adverse_fill / late move on the early leg) | 80 fills, +$139.18 | 6 fills, -$360.62 | **+$221.44** | **+$268.72** (83 mkts) | 6 |
| 2 | Early leg: refuse when spot is < 3 bp from the strike on our side | 42, +$73.94 | 3, -$228.47 | +$154.53 | +$181.69 (41) | 3 (all BTC) |
| 3 | A78: early ceiling 97.5c on the decision price. Live 09-20 04:44-05:48 ET, then removed | 99, +$117.19 | 4, -$220.04 | +$102.85 | +$115.57 (100) | 4 |
| 4 | Early leg: ask >= 98c | 44, +$45.76 | 2, -$161.91 | +$116.16 | +$94.76 (44) | 2 |
| 5 | Early leg off entirely | 197, +$341.95 | 6, -$360.62 | +$18.67 | +$69.84 (197) | 6 |
| 6 | Early leg with confidence < 99.7% | 82, +$143.42 | 3, -$194.78 | +$51.35 | +$15.31 (80) | 3 |
| 7 | Sweep limit at ask + 3c instead of a flat 98c (sizing_amplified) | 10, +$40.22 (V) | -$61.75 (V) | +$21.54 (V) | -- | 1 |
| 8 | Instant hedge when a fill lands >= 2c under the ask seen (adverse_fill) | blocks no entry | upper bound $221 of entry loss | about +$8 (A, tape) | -- | 7 |

Row 5 ignores what the later legs would have bought in place of the early leg, which is unmeasured. At early_frac 0.333, every early-leg dollar scales by one third, so the ledger's -$69.84 becomes about -$23. That is smaller, but still not positive.

**Already live (measured value):**

| Rule | Class | Value | Blocks |
|---|---|---|---|
| Jump gate (v-jump) | model_overconfident | +$66.32 entry on pre-gate fills (4 winners +$4.27, 2 losers -$70.59) (V); refusals since: 81 won / 1 lost, about +$5 (V, tape-resolved) | 83 refusals |
| Crash fix c5fdf7f | bug | about $29-31 on 09-19 02:00 (book estimate) | nothing |
| No filter may block a hedge (A62 / v-hedgelastweek) | hedge side effect | $0-54 on 09-19 01:45; two ~100 ms races decide it (V) | nothing |
| A69: a pause never skips the hedge | gate side effect | $16-25 on 09-19 16:00 (upper bound) | nothing |
| v-hedge25 (trigger 0.25) | hedge_failure | tape rebuild over the 7 hedges between 0.25 and 0.60: +$60.69 net (V). It still hedges XRP 09-19 (-$44.40 instead of -$67.22) and costs about $17 on 09-14 16:00 (V) | later hedges |
| v-pin995 | model_overconfident | +$22.71 entry (39 winners +$33.36, 3 losers -$56.06, 2 closes) | 42 fills |
| v-a10c dump guard (15c) | adverse_fill | -$4.20 entry (5 winners +$32.61, 3 losers -$28.41), a wash; refusals since forwent about +$20 (V) | 28 refusals |

**Not fixes (cost more than they save on live fills):**

| Rule | Net on live fills | Source |
|---|---|---|
| Spot < 3 bp from the strike, any leg | -$88.08 | mine |
| Spot < 5 bp, any leg | -$320.68 | mine |
| Market risk >= 20x the model's | -$311.72 | mine |
| z 2.576-2.75 | -$169.36 | mine |
| z 2.75-3.0 | -$189.58 | mine |
| Sweep-grown fills | -$307.22 | mine |
| Fills of 60+ contracts | -$252.33 | mine |
| Level < 250 ms on the non-early legs | -$214.52 | mine |
| Dump guard at 10c | -$105.14 | mine |
| Size capped at the touch | -$248 to -$281 | (V) |
| Locked average on the wrong side | -$125.75 | (V) |
| Confidence < 99.8% | -$311.47 | (V) |
| --jump-widen | -$77.49 | (V) |
| A measured-tail pin on all legs (blocks 696 of 749 markets) | -$437.93 | (V) |

**The unavoidable cost of the strategy.** The bot sells about 2-4c of insurance for 96-98c. Live, it loses 22 of 775 fills (2.8%), and nothing visible before the send predicts which ones, except possibly fresh levels on the early leg. The **genuine_late_move** losses, -$269.67 over 7 markets, are that cost:
- 09-11 23:00 SOL
- 09-14 16:00 HYPE
- 09-16 12:30 BNB
- 09-17 21:15 BTC
- 09-21 18:15 HYPE
- 09-08 20:45 NEAR fills 1-2 (today's gates would still buy it at 97.5c, per the verifier)
- the core of 09-19 16:00 BTC (about -$80-90 even with A69)

In each, the entry was worth taking at the measured odds and the index jumped after the fill. **Their frequency is the price of the strategy; their SIZE is a choice:** 20 contracts in A, 55-110 in C. What is avoidable:
- about $137.58 of hedge false alarms;
- about $45-110 of bugs and gates on 09-19, all fixed;
- the sizing-amplified $45 on 09-19 12:30;
- probably the fresh-level early fills (row 1).

---

## 5. Where the autopsy and the verifier disagreed, and it matters

1. **09-08 20:45 NEAR (-$52.60).** The autopsy said all three fills are blocked by rules live today, so no new rule is needed. **The verifier found a 97.5c NO quote at tau 18 (model 99.63%) that passes every live gate**, one second before the jump. The largest pre-growth loss is NOT prevented by today's gates.
2. **09-17 21:15 BTC.**
   - **The cause changes from adverse_fill to genuine_late_move.** The 53c fill REDUCED the loss: at the 97.8c seen it would have been about -$70 even with the hedge, against the actual -$27.87.
   - **The autopsy's early-leg dollars were sign-inverted.** Blocking the leg SAVES $59 on the ledger; the autopsy said it loses $59. My independent count: early-only markets net **-$69.84 over 197 markets**, so blocking saves $69.84.
3. **The v-nocap evidence does not reproduce** (my check; the same finding as 07_evidence-audit F1). v-nocap removed the 97.5c early ceiling on "136 markets, +$110.67, 2 losing". On Kalshi's ledger, the early-only markets settled before its commit (09-20 09:48Z) are **135 markets, -$79.91, 5 losing markets (-$311.03)**. The missing losses are BTC 09-19 02:00, BTC 09-19 16:00 and the XRP/HYPE 09-19 23:45 false alarms. Since the removal, the early leg is +$10.06 on 62 markets, with 2 losing markets (-$90.36): the two 09-21 losses. The main window since then: +$69.44 on 29 markets, 0 losing.
4. **09-19 01:45 BNB, the rescue dollars.** The autopsy said an ungated hedge makes the close about $0. The verifier: the deployed hedge could only take the top level, so the result depends on two ~100 ms races, somewhere from -$4.17 to -$57.76. **"Never gate a hedge" is worth $0-54 here, not $57.**
5. **09-14 16:00 HYPE.** The autopsy said the 0.25 trigger would not fire, which would make the close -$59.20. The verifier: it fires at tau 17 at 79c, for about -$46.9. v-hedge25 costs about $17 here.
   - The same verifier corrected the 0.25-0.60 band arithmetic: a lower trigger waits rather than never hedging. It gives up $25.58 of saves (not $46.95) and avoids $86.30 of false-alarm cost (not $130.69), a **net of +$60.69 (tape rebuild)**.
6. **09-19 16:00 BTC.** The autopsy said `--honest` would not block it. **The verifier says it would**: measured confidence 99.04% is under the 99.5% pin. As a global rule, though, a measured-tail pin blocks 696 of 749 markets (-$437.93), so it is not a fix.
7. **09-19 23:45 XRP/HYPE.** The autopsy said today's settings would still lose $60-78. The verifier's estimate is about -$35 (range -$35 to -$70, tape). Lifetime hedging is **-$9.35**, not -$35.62; the autopsy missed the BTC 09-17 save (+$26.32), which has no settled row. I reproduced -$9.35.
8. **09-21 12:45 NEAR.**
   - **The autopsy's proposed bid-collapse gate (a 5c drop in 1 s) fails on this very loss.** The bot's own book showed a 2-3c drop. The proxy's power came from trades printed after the decision; with the window ending 150 ms before the send, it catches 0 losers.
   - The verifier's alternative (early leg, level < 250 ms) is row 1 above, and I reproduced it.
9. **A78 scoring (09-21 18:15 HYPE).** The autopsy scored the 97.5c early ceiling on the FILL price and called it a wash (+$1.23). The gate reads the DECISION price. Scored that way it is **+$102.85 entry / +$115.57 ledger** (mine; the verifier gets +$45.55 using the losing markets' nets and entry for winners).
10. **09-10 01:30 BNB.** The autopsy's "spike-born signal, market at ~70c" mechanism is not supported: the market traded 94c on both sides of our fill, and spike-born fills lose 2 of 56 (3.6%) against 13 of 446 (2.9%) for other fills. The cause stays model_overconfident (thin margin, then a genuine move).

Smaller corrections that change no conclusion:
- 09-12 20:00: the offer was 81 ms old, not ~300 ms.
- 09-11 08:30: the settle was 13 model sd from the forecast, not ~20.
- 09-14 05:30: the bank was $354.89, not $325.83.
- 09-16 04:30: the alarm was at :42, not :40, and sweep-depth grew the bet 9 -> 84.
- 09-19 12:30: the vanished offers were three (98% of the ladder), not two (95%).

---

## Could not measure

- **What the later legs would have bought if the early leg were blocked or cut.** The bot does not log the later signal it would have sent, so rows 1-6 assume the capital simply sits idle.
- **The hedge price an instant post-fill hedge would get.** It needs the order book at each of the 28 price-through seconds (~230 MB per delta hour); only the D1 top-of-book estimate (about +$8) exists.
- **Every rule rests on 1-7 losing closes**, below the 30-close floor. With about 35 cuts tried here, the multiple-looks threshold for p is about 0.0014. Only price-through (p = 4e-6, but post-fill) clears it. The early level-age rule (p = 0.005) clears it only if its pre-registered 250 ms threshold counts as one look.
- **Rows 1-6 are post-hoc.** No paper arm has run them in a window where arms matched live.
- **August closes and the tape.** 08-15 and 08-22 have no index tape (it starts 08-25). Tape hours 20260915T13, T20 and 20260922T06 are corrupt, and 01-05Z on 09-22 is missing (outage).

Resources: read-only throughout. Free RAM was 1.88 GB at the start. Python stayed under 100 MB (no tape reads by this job).
