# 01 money-vs-changes -- FINAL (2026-09-22)

Question: did the bot make steady money, then did tweaks meant to grow it turn it into a loser? Which exact changes?

Sources: Kalshi's ledger (`results/kalshi_ledger.json` via `pinledger.pnl`) for money per market; the 124 live logs (`results/pinrun-live-*.jsonl`) for legs, prices, seconds-to-close and bet size; each run's `start` record for the settings it actually ran. **No replay, no tape, no paper arms** are used anywhere below. Scripts and intermediate JSON are in the scratchpad `map/01/` (build.py, table.py, legs.py, groups.py, windows.py, cf.py, sig.py, imp.py). Times: UTC in tables (data), ET in prose.

## 0. Reconciliation (done before any analysis)

- Ledger crypto 15M: 755 markets. 747 have pinrun orders. The other 8 are $0.00 penny/plant tests plus the August manual trades (-$20). For all 747, the contracts logged as filled == the ledger's contract counts (0 mismatches), and for every unhedged market the P&L rebuilt from our fills == the ledger P&L to the cent. No hedged market mixed leg types, so every split by leg below is exact.
- **The bot's own day totals (`pinday`) are wrong on two days, because the bot died while holding positions and never wrote `settled` rows:** 09-19 was **-$223.46** (ledger), not -$161.14 (missing BTC 02:00 ET -$66.34 and ETH +$4.06). 09-17 was **+$99.87**, not +$115.68 (missing the 21:15 ET close: BTC -$27.87 and ZEC +$12.09). 09-08, 09-11 and 09-12 differ by less than $4.
- Crypto bot total, 09-08 to 09-22 02:30 ET: **+$484.98 on 547 closes / 747 markets.** The account's ~$387 also includes commodities (-$101.6) and the August manual trades.

## 1. Findings, ranked by dollars

### Headline

**The belief is half right.** The money did turn, but it turned in one place, on 09-19 starting 00:03 ET. It did not wear down gradually. In dollars, wins did not shrink; per contract they shrank ~27%. Losses did not get significantly more frequent. **What changed is that each losing close got 4x bigger, and that is the whole swing.** Most of that growth traces to one family of changes, the 45-second early leg. On top of it sit three hedge-blocking bugs shipped on 09-18 and 09-19.

| period (UTC) | closes | net | $/close | losing closes | avg winning close | avg losing close | contracts/close | net c/contract | win c/contract | avg price |
|---|---|---|---|---|---|---|---|---|---|---|
| A 09-08..09-13 02Z (size <=20) | 196 | +$37.36 | +0.19 | 10 (5.1%) | +$0.99 | -$14.62 | 22 | +0.87 | 4.73 | 94.3c |
| **B 09-13 02Z..09-17 13Z "steady"** | 151 | **+$388.95** | **+2.58** | 5 (3.3%) | +$3.25 | **-$17.20** | 78 | **+3.29** | 4.14 | 95.6c |
| C 09-17 13Z..09-19 04Z (45 s leg phased in) | 74 | +$170.40 | +2.30 | 1 (1.4%) | +$2.55 | -$15.79 | 91 | +2.54 | 3.00 | 95.8c |
| **D 09-19 04Z..09-22 06Z** | 126 | **-$111.74** | **-0.89** | 7 (5.6%) | +$3.17 | **-$69.85** | 105 | **-0.84** | 3.04 | 96.6c |
| (D2 = D from 09-20 00:00 ET, after the 09-19 bug fixes) | 72 | +$111.73 | +1.55 | 2 | | -$45.18 | 90 | +1.73 | 3.20 | 96.5c |

- **Did losses get more frequent?** B had 5 of 151 closes losing and D had 7 of 126. A Fisher exact test gives p = 0.39. **Not shown at this n.**
- **Did wins shrink?** Per winning close, no: $3.25 in B and $3.17 in D. Per contract, yes: 4.14c fell to 3.04c. Prices paid rose from 95.6c to 96.6c.
- **Did losses get bigger?** **Yes, 4.1x:** -$17.20 per losing close became -$69.85. That is 1.34x more contracts per close multiplied by ~2.7x more lost per contract. Losing markets in B lost 27c per contract, because both real losses were hedged. In D they lost 72c per contract, because three hedges were blocked by bugs and two hedges were false alarms.
- **Arithmetic for D:** 119 winning closes x $3.17 = +$377, and 7 losing closes x -$69.85 = -$489. Two what-ifs:
  - With B-sized losses (-$17.20 each), D would be about +$257.
  - With B's loss frequency but D's loss size, D would be about +$84.
  - **So loss size explains more of the swing than loss frequency does.**
- **Bets did NOT get bigger relative to the bank.** One bet was bank/5.88 until 09-18 06:51Z. It became bank/8 then, bank/8.85 from 09-19 04:03Z (brake 3.00 plus the extra coin), and bank/11.8 from 09-20 05:46Z. Median dollars at risk per close were $71.50 in B (16.6% of the bank) and $101.40 in D (11.0% of the bank). In units of one bet, contracts per close were flat: 1.21 in B, 1.02 in C, 1.24 in D. The dollar size grew because the bank grew: $262 on 09-13, then $927 after the $370.44 deposit at 03:08 ET on 09-19.

Per ET day (ledger):

| ET day | closes | net | winning closes x avg | losing closes x avg | contracts/close | net c/ct | win c/ct | avg price | bet size | worst close |
|---|---|---|---|---|---|---|---|---|---|---|
| 09-13 | 34 | +114.78 | 34 x 3.38 | 0 | 65 | 5.23 | 5.36 | 94.2c | 47 | +0.25 |
| 09-14 | 46 | +81.10 | 44 x 3.30 | 2 x -32.08 | 72 | 2.44 | 4.54 | 95.2c | 58 | -34.26 |
| 09-15 | 25 | +76.32 | 25 x 3.05 | 0 | 97 | 3.14 | 3.14 | 96.6c | 74 | +1.29 |
| 09-16 | 34 | +85.11 | 31 x 3.45 | 3 x -7.28 | 89 | 2.83 | 3.77 | 95.9c | 85 | -12.14 |
| 09-17 | 38 | +99.87 | 37 x 3.13 | 1 x -15.79 | 97 | 2.70 | 3.56 | 95.0c | 97 | -15.79 |
| 09-18 | 43 | +91.85 | 43 x 2.14 | 0 | 86 | 2.49 | 2.49 | 96.6c | 79 | +0.10 |
| **09-19** | 54 | **-223.46** | 49 x 3.57 | **5 x -79.72** | 126 | -3.30 | 2.88 | 96.6c | 106 | -108.86 |
| 09-20 | 34 | +109.63 | 34 x 3.22 | 0 | 97 | 3.33 | 3.33 | 96.4c | 74 | +0.10 |
| 09-21 | 36 | -2.97 | 34 x 2.57 | 2 x -45.18 | 84 | -0.10 | 3.05 | 96.6c | 78 | -59.09 |

(09-08..09-12: 201 closes, +$47.69, bet size 10-20, 10 losing closes. "Win c/ct" falls from ~4.5-5.4c before 09-15 to 2.5-3.6c after.)

### F1. The 45-second early leg holds 64% of the contracts since 09-17 and is net NEGATIVE. It is the leg where 7 of the 9 losing markets happened. Direct cost: -$65. With displacement counted (see below), the cost is larger.

- **Claim:** the early leg went live with v-staged (09-17 13:05Z) and moved to full size with v-early-full (19:41Z) and v-early-full2 (09-18 16:33Z). Its edge cap rose from 3c to 10c with v-cheap (09-19 05:08Z). Since then:
  - **Legs bought at 31-45 s:** 202 markets, 149 closes, 12,793 contracts, **-$65.41 (-0.51c per contract).**
  - **Legs bought at <=30 s, same 200 closes:** 110 legs, 7,157 contracts, **+$124.08 (+1.73c per contract).**
- **Mechanism:**
  1. **The 31-45 s window is where the book is expensive.** Winning early legs paid 97.0-97.3c. Winning <=30 s legs paid 96.2-96.3c. So a winning early contract earns 2.6-2.9c against 3.5-4.2c.
  2. **A thin margin cannot absorb the ordinary loss rate.** At ~97c a lost contract costs ~97c, so unhedged the early leg breaks even only below a ~2.8% loss rate by contracts. It lost 3.2% of its contracts in C and 3.65% in D. That is about the same rate as the <=30 s legs (3.5% in D). The loss rate is ordinary; the margin is too thin for it.
  3. **It displaced the profitable window instead of adding to it.** Total contracts per close in bet units stayed at ~1.2 (B 1.21, D 1.24). But <=30 s buying fell from 1.21 bets (78 contracts) per close in B to 0.39-0.45 bets (35-36 contracts) in C and D. The early leg spends the budget first.
- **Evidence (ledger + live fills):**

| since 09-17 13:05Z | legs | closes | contracts | net | c/contract | losing markets (of which our side lost) |
|---|---|---|---|---|---|---|
| early, before v-cheap (to 09-19 05:08Z) | 84 | 60 | 4,204 | +$80.35 | +1.91 | 1 (2; DOGE's hedge turned one into +$4.36) |
| early, after v-cheap | 118 | 89 | 8,588 | **-$145.76** | -1.70 | 6 (4; the other 2 are the 23:45 false alarms) |
| early, 09-20 00:00 ET..now (after the bug fixes) | 69 | 54 | 4,392 | +$30.29 | +0.69 | 2 (2) |
| <=30 s, 09-20 00:00 ET..now | 41 | 30 | 2,063 | **+$81.44** | **+3.95** | 0 (0) |
| (B, all <=30 s, reference) | 204 | 151 | 11,817 | +$388.95 | +3.29 | 6 (3) |

- **Early legs by price paid (since 09-17):**
  - 96.5-97.5c: +$68.63 (40 closes, 0 losses)
  - 97.5-99c: **-$61.35** (103 closes, 3 losses)
  - under 96.5c: **-$72.70** (34 closes, 4 losses)
  - This slicing was chosen after seeing the data, so treat it as a hypothesis.
- **Counterfactual, live fills only:** drop the early legs and the hedges attached to them.

| ET day | actual | without early legs |
|---|---|---|
| 09-17 | +$99.87 | +$79.85 |
| 09-18 | +$91.85 | +$32.96 |
| **09-19** | **-$223.46** | **-$48.85** |
| **09-20** | +$109.63 | +$35.43 |
| **09-21** | **-$2.97** | **+$44.14** |

  - Net, that is +$65.41 better. **That figure is a FLOOR on the leg's cost, not an estimate of it.** Without the early leg, the <=30 s window would have had budget for many of those 202 markets, and in B it filled ~1.2 bets per close there.
  - How much it would have bought, and at what price, needs the book (a replay/tape hypothesis), so it is not claimed.
  - v-nocap measured that we fill 82% of our ask at 11-30 s, so the replacement would not be 100%.
- **Confidence:** medium-high on the margin gap, which rests on ~290 winning legs. Medium on net sign: 149 closes clears the 30-close floor, but it holds only 7 losing markets.
- **Artefact check:** leg labels agree with seconds-to-close on all 773 legs (early == tau 31-45, 202/202). Hedge P&L is exact per market. **Not checked:** whether the early losses cluster in one volatility regime (09-19). The signal `sigma` field is not comparable across coins, and the index was not streamed.

### F2. The decisions that kept and enlarged the early leg were read off the bot's own log, which is missing the early leg's two worst-bookkept losses. Kalshi's books disagree with it by $179.

- **v-nocap (09-20 ~09:48Z)** removed the 97.5c early ceiling. It said: "45s early 136 markets, +$110.67, loss rate 1.5%... the 45-second leg is not the risky leg." I reproduced its 136 markets exactly from the logs.
- **The ledger for the same leg at the same moment is 140 markets, -$68.78, with 4 side-lost (2.9%).** The gap has two causes:
  1. **Four markets have no `settled` row because the process died holding them.** Two of them are early-leg losses: BTC 09-17 21:15 ET (-$27.87) and BTC 09-19 02:00 ET (-$66.34).
  2. **Entry P&L was counted without the early legs' hedges,** which cost -$82.78 (mostly the 09-19 23:45 false alarms).
- **v-early-full2 (09-18 16:33Z, a third -> full size)** cited "31-45 s: 57 markets, 1 miss, +$64.79" from the same log view. That view already lacked the -$27.87 BTC 09-17 21:15 early loss.
- **Mechanism:** `pinday`/`settled` records are written by a live process. A crash or kill mid-close leaves no record, so the log systematically drops losses that coincide with process death. Two of the three process deaths while holding happened on early legs.
- **Dollar impact:** the early leg has cost at least $65 since the decision to keep it (F1). The decision rested on a +$110.67 that was really -$68.78.

### F3. Three bugs shipped between 09-18 22:46Z and 09-19 07:38Z blocked the hedge, or crashed the process, on otherwise ordinary losses: -$232.05 on 3 markets (all fixed per HANDOFF 09-21).

| close (ET) | ledger | leg | what made the loss possible | what made it naked |
|---|---|---|---|---|
| 09-19 01:45 BNB | -$57.76 | <=30 s at 24 s, 76 at 75.0c (ask seen 85c, model 99.9%) | the 15c dump guard passed an 85c ask by 0.1c | `--hedge-price 0.60` (v-bands, 22:46Z) refused insurance at a 21c ask |
| 09-19 02:00 BTC | -$66.34 | **early at 35 s**, 70 at 94.4c, edge 5.0c | needed both `--early-tau 45` AND `--early-max-edge 10` (v-cheap, 51 minutes earlier; the old 3c cap would have refused a 5.0c edge) | process crashed (`round(None)` in the close_budget gate's log line); no hedge loop ran |
| 09-19 16:00 BTC | **-$107.95** | **early at 45 s**, 110 at 98.0c | needed `--early-tau 45` at full size. The 110 contracts came from bank/8.85 after the deposit, with the brake kept at 3.00 at 07:38Z | the `--loss-cap 200` pause skipped the hedge pass (v-cap200) |

- What working hedges would have recovered is **not measurable** for any of the three:
  - BTC 02:00: the bot was dead, so no belief was ever computed.
  - The other two: the depth behind the ask was not logged.
- For scale: the lifetime typical hedged loss is ~57c per contract against ~86c naked, which would put the three at roughly -$150. That is a hypothesis, not a measurement.

### F4. Two false-alarm hedges on early legs cost -$116.87 on 09-19 at 23:45 ET.

- XRP and HYPE, both early legs (bought at 41 s and 33 s), 104 contracts each. **Both bets won** (+$7.99 together). The hedge fired at belief 0.27 and 0.50 and cost -$67.21 and -$49.66.
- Settings at the time: trigger 0.60 (v-hedge60), `--hedge-slip 0.03` (v-hedgefill, 22:50Z, 55 minutes earlier).
- **Lifetime hedge-leg P&L, straight from the ledger: -$11.21 over 17 hedged markets** (B +$20.18, C +$34.24, D -$58.91). Hedging has roughly broken even overall, and in D it cost money.
- Hedged markets since 09-17: 6 of 202 early markets (3.0%) against 2 of 89 <=30 s markets (2.2%). With counts this small, the early leg is not measurably more alarm-prone. Its losses are larger because that is where the contracts are.

### F5. Every loss over $25, tied to the setting that made it possible

| close (ET) | ledger | leg / price | only possible because of |
|---|---|---|---|
| 09-08 20:45 NEAR | -$52.60 | 3 legs, 3rd at 73.0c | max-per-close 3, pin 0.98 (v13 era) |
| 09-14 05:30 BTC | -$34.26 | <=30 s at 13 s, 60 at 97.2c | ordinary loss; the hedge at 0.80 recovered +$24.18 |
| 09-14 16:00 HYPE | -$29.90 | <=30 s at 30 s, 62 at 95.2c | ordinary loss; the hedge recovered +$29.29 |
| 09-17 21:15 BTC | -$27.87 | early at 38 s, signal at 97.8c but FILLED at 53.0c, 99 contracts | `--early-tau 45` at full size (v-early-full, 3.5 hours earlier); the early leg had no price floor yet (the 90c floor came 6 hours later) |
| 09-19 01:45 BNB | -$57.76 | <=30 s at 24 s, 76 at 75.0c | dump-guard margin; hedge blocked by `--hedge-price 0.60` |
| 09-19 02:00 BTC | -$66.34 | early at 35 s, 70 at 94.4c | `--early-tau 45` plus `--early-max-edge 10`; crash |
| 09-19 12:30 BNB | -$61.75 | <=30 s at 23 s, 84.5 at 97.3c (signal 91.5c, only 23 contracts on the touch) | ladder sizing (sweep_depth 23 -> 114) plus bidding up to the 98c limit. The band boost fired (order for 171) but did NOT change the fill: 84.5 filled, fewer than the unboosted 114. Hedge +$20.60 |
| 09-19 16:00 BTC | -$107.95 | early at 45 s, 110 at 98.0c | `--early-tau 45`; the loss-cap pause skipped the hedge |
| 09-19 23:45 XRP | -$64.95 | early at 41 s; the bet won, the hedge lost | false alarm on an early leg |
| 09-19 23:45 HYPE | -$43.92 | early at 33 s; the bet won, the hedge lost | false alarm on an early leg |
| 09-21 12:45 NEAR | -$59.09 | early at 44 s, 81 at 91.1c (edge 3.8c) | `--early-tau 45` plus the edge cap at 10 (v-cheap) |
| 09-21 18:15 HYPE | -$31.27 | early at 43 s, 55 at 98.0c | `--early-tau 45`; hedge recovered +$22.70 |

**Since 09-17 13:05Z there have been 9 losing markets, -$520.90 gross. 7 of them are early legs (-$401.39). The other 2 are <=30 s buys at an abnormal price (75c; 97.3c against a 91.5c signal).**

### F6 (identify better, hypothesis). A fill more than 5c BETTER than the price we saw is a 40% loss marker.

- IOC buys filled at the price seen, or worse: 14 of 721 legs lost the main side (1.9%), +$563.19.
- Filled more than 5c BETTER than the signal's ask: **6 of 15 legs lost (40%), across 14 closes.** Their entries made -$67.33: the 9 winners +$79.65, the 6 losers -$146.98.
- Filled 2-5c better: 1 of 13 legs lost, but that one was NEAR -$59.09.
- Examples: BTC 09-17 (signal 97.8c, filled 53c), DOGE 09-18 (97.6c -> 11c), BNB 09-19 01:45 (85c -> 75c).
- **Mechanism:** the ask collapsed in the ~100 ms between look and fill, so someone sold hard into the book. The market knew before the index did.
- **n = 14 closes is below the 30-close floor.** Signal-to-order pairing is strict (same file, within 2 s, exact exec price).

## 2. Refuted or not supported

- **"The tweaks made the bets bigger, so the tail got fatter": not supported as a tweak effect.** Bet size relative to the bank went DOWN at every brake change. Dollar size grew with profits and the $370.44 deposit.
  - The one sizing decision that mattered: after the deposit, brake 4.08 was reverted to 3.00 at 07:38Z on 09-19 ("keep bet size"). That put the afternoon and evening at 104-114 contracts instead of ~77.
  - Scaled proportionally, the 09-19 07:38Z to 09-20 05:46Z window would have been -$76.89 instead of -$104.57, a $27.68 difference. This is approximate, because fills are limited by the book.
- **Extra coin (`--extra-coin 1`, v-thirdcoin) and late budget (`--late-extra`):** the budget beyond 2x the bet was used 4 times (169 contracts, **+$5.55**). Not a cause.
- **Late boost (1.5x inside 10 s):** fired 3 times, all 3 won. Boosted portion ~+$5.00.
- **Band boost (1.5x at 90-94c, removed 09-20):** fired 3 times. Boosted portion +$5.27. The -$61.75 BNB it fired on would have filled the same 84.5 unboosted.
- **Top-ups and re-buys:** top-up legs +$6.41 (6 legs). Second-and-later legs on a market: -$7.69 lifetime, mostly 09-08.
- **Losses getting more frequent:** 3.3% -> 5.6% of closes, p = 0.39. Not shown.
- **"Edge broke" in the sense of the <=30 s strategy failing: not supported.** <=30 s legs since 09-20 made +3.95c per contract with 0 losses in 30 closes. B was +3.29c. The thinner average margin comes from where the contracts moved (the 31-45 s window), not from the old window decaying.

## 3. Could not measure, and why

- **What the <=30 s window would have bought on the 202 early-leg markets without the early leg.** This needs the book at 0-30 s, i.e. tape or replay, which is a hypothesis by the operator's rule.
- **What working hedges would have recovered** on BTC 02:00 (the bot was dead, so no belief exists), and on BTC 16:00 and BNB 01:45 (the depth behind the ask was not logged).
- **What the A50 bug cost** (v-bank8 applied the 3c early edge cap to <=30 s legs too, 09-18 07:59Z to ~22:46Z). 7 logged refusals at 3.2-7.6c edge. These are refused offers, not fills, so they are not scored.
- **Most single versions.** After 09-17 only two version windows have 30 or more closes: 09-19 07:38Z to 09-20 05:46Z (51 closes, -$104.57) and 09-20 05:46Z to 09-21 17:03Z (52 closes, +$72.44). Every other window has 2-14 closes. Per-window table (market assigned to the window of its first leg):

| window (start UTC) | closes | markets | losing closes | net | c/ct | avg price | early share |
|---|---|---|---|---|---|---|---|
| hedge 0.60 (09-16 13:57) | 24 | 29 | 0 | +76.66 | 3.71 | 96.0c | 0% |
| v-staged, early at 1/3 (09-17 13:05) | 14 | 19 | 0 | +24.73 | 2.92 | 96.9c | 43% |
| v-early-full (09-17 19:41) | 13 | 23 | 1 | +26.73 | 1.55 | 93.9c | 79% |
| early off (09-18 01:48) | 2 | 3 | 0 | +10.62 | 4.17 | 95.5c | 0% |
| v-early49, 1/3 + 90c floor (09-18 03:02) | 12 | 17 | 0 | +39.88 | 4.15 | 92.9c | 42% |
| v-bank8 (09-18 06:51) | 12 | 20 | 0 | +14.94 | 2.35 | 97.5c | 55% |
| v-early-full2 (09-18 16:33) | 11 | 17 | 0 | +29.04 | 2.53 | 97.3c | 73% |
| v-bands (09-18 22:46) | 10 | 16 | 0 | +24.47 | 2.13 | 97.7c | 71% |
| brake 3 / extra coin / late 1.5x / v-cheap / panic (09-19 04:03) | 7 | 9 | 2 | -104.44 | -15.59 | 93.4c | 55% |
| loss cap + deposit + taper + hedge-slip (09-19 07:38) | 51 | 70 | 3 | -104.57 | -1.58 | 97.0c | 65% |
| v-proportion, brake 4 (09-20 05:46) | 52 | 76 | 1 | +72.44 | 1.61 | 96.7c | 70% |
| v-hedgefull / v-hedgelastweek (09-21 17:03) | 6 | 10 | 0 | +35.22 | 4.41 | 95.3c | 58% |
| v-hedge25 (09-21 20:12) | 10 | 11 | 1 | -10.38 | -1.59 | 96.4c | 57% |

## 4. Solutions worth testing

1. **Turn the 45 s leg off, or back to a third, as a live test with a bar written first.**
   - Baseline: D2 (72 closes, +$1.55 per close; early legs +0.69c per contract, <=30 s legs +3.95c).
   - Bar: the next 30 or more live closes without the early leg, judged on $/close and on <=30 s contracts per close. The operator has said he wants to keep the 45 s leg ("keep the 45 normal"), so this is his decision.
   - `arm-early-off` is synced from 09-22 06:21Z and gives a paper read in parallel.
   - **What it blocks:** every buy at 31-45 s (~0.8 bets per close; 69 of the last 110 legs, +$30.29 since 09-20). It cannot block a hedge.
   - **Risk:** the <=30 s window may not absorb the budget (82% fill ratio at 11-30 s per v-nocap), so there are fewer dollars on quiet days.
2. **If the early leg stays, bring back its 3c edge cap (`--early-max-edge 3.0`, scoped to the early leg only, which the A50 fix already does).**
   - **What it blocks:** early legs whose edge is above 3c. Since v-cheap that is 26 legs, -$34.59, including NEAR -$59.09 and BTC 02:00 -$66.34.
   - n = 24 closes, below the floor, so it is a hypothesis. Validate as a synced arm, then live.
   - It cannot block a hedge or a <=30 s leg.
3. **Make the ledger join the only source for leg- and version-level decisions** (the join in scratchpad `map/01/table.py`: ledger rows x logged orders, hedge P&L = ledger minus entry P&L).
   - Two live decisions (v-early-full2, v-nocap) rested on a log view that drops every market held when the process died, and that splits hedge cost away from the leg that caused it.
   - Blocks nothing; it is measurement.
4. **Log-only first: a "fill far better than seen" alarm (F6)** -- record every fill more than 5c below the signal ask, plus the opposite side's ask at that moment. Score it after 30 events.
   - If it holds, use it as a hedge TRIGGER, never as an entry gate: it only adds insurance and cannot block a hedge.
   - Cost to watch: on the 9 winners it would have bought insurance that expired worthless, against their +$79.65.

---
Resources at finish: both collectors alive (kalshi_collector pid 105304, crypto_feeds pid 105352), free RAM ~2.2 GB, free disk 34 GB. No process started, stopped or signalled; nothing written outside this file and the scratchpad.
