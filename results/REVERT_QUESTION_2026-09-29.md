# Should pin revert to an older version? -- 2026-09-29 (workflow wf_ddded9de-5e0: fair paper test, real money, adversarial verifier)

Answer: KEEP the current version. Operator asked 2026-09-29 ~14:5xZ: "Should we revert pin to a previous version".
Follow-ups done: exact-live paper twin started 18:59:18Z (pid 4228512, results/pinrun-paper-20260929T185918Z.jsonl,
--max-losses 1000 --loss-abort -100000 so the comparison cannot end at a loss) -- READS_DUE 'live-twin'. Ledger bug
(subaccount rows mixed into the main ledger) fixed in research/pinledger.py (subaccount=0); the existing file still
holds the mixed rows -- its rebuild was refused by the permission check and waits for the operator.

## Recommendation (verifier)

No older version of pin makes more money than the one running now, so keep the current version. The file `RECOMMENDATION.md` was not written, because a subagent may not write report files. The full text is below.

# Should pin go back to an older version? No, keep the current one.

**Reason:** Once you count the 97.9–98c buys the live bot has been making again since Monday 10:36 AM ET, the 09-25 version comes out about even: $4 to $7 behind over 27 hours on paper. It gets that close only because of one market today, BTC 1:30 PM. The new seller check refused that buy, and every older version took it and lost. The 09-20 version is $53 behind. Income is down mostly because the market has fewer cheap offers: practice bots still running the old rules also earn about half what they did last week.

## Evidence
Practice bots against practice bots, on the same 107 quarter-hours: Monday 09-28 10:45 AM to Tuesday 09-29 2:30 PM ET, both weekdays. I counted it again from the raw logs with my own script, and every number matches the first analyst's to the cent.

| older version | ahead (+) or behind (−) today's rules, paper | counting the 97.9–98c wins live takes again | what decides it |
|---|---|---|---|
| 09-25 (the last version before the new rules) | +$7.18 | about −$4 to −$7 | BTC 1:30 PM: it lost $22.65; today's rules refused it |
| 09-25 without the last-15-second add | +$3.19 | about −$8 | the same BTC market, −$23.20 |
| 45-second bet at full size | −$8.33 | −$8.33 | BNB 8 PM cost it twice as much |
| 09-20 version (45-second bet at full size) | −$52.55 | about −$58 | BTC 1:30 PM, −$73.12 |
| 09-25 with no 45-second bet | +$23.12 | about +$11 | BNB 8 PM; over 4.3 days this version is **$9.30 behind** the 09-25 version, so the lead is one day's luck |

- **How big a gap has to be to mean anything:** two practice bots with identical settings ended $10 apart over the same day. Gaps under about $10 a day are noise.
- **BTC 1:30 PM today, checked in the live log:**
  - The model was 99.6 in 100 sure of NO. The offer was 96.1c with 36 seconds left, and it had been up for less than a tenth of a second.
  - 97 of every 100 contracts sold in the last 3 seconds were sold into our side.
  - The seller check refused it, and the market went the other way.
  - The older versions lost $23 to $27 there on a third of a bet, and $73 on a full bet.
- **The old version would have hit the two-loss stop.** The 09-25 practice bot that was restarted Sunday night (09-27, 10:47 PM ET) carries the same stop-after-2-losses brake as live. It hit that brake at 1:30 PM today, after losing BNB 8 PM and BTC 1:30 PM, and stopped. Live, on today's rules, has 1 loss this run.
- **The practice bot closest to live** is "arm-floor90", which I checked against the running command lines. Its only difference from live is that it still refuses 97.9–98c on the 30-second bet. The first analyst compared against the right bot.
- **Real money in the same hours, for context only (not a fair comparison with paper):** 29 markets, 28 won, 1 lost, +$26.44. The loss was BNB 8 PM, −$8.26: the 45-second bet lost at a 95c offer, and the insurance got most of it back.

## Why income is down: mostly the market
- **Real money:** the middle weekday from 09-14 to 09-25 made +$83. Since the change: Monday +$22.72, and Tuesday +$17.92 up to 2 PM.
- **Practice bots on unchanged old rules:** about $100 a day of wins on Thursday 09-24 and Friday 09-25, then $47 to $55 on Monday 09-28. Weekday against weekday, that is half, with no rule change.
- **The new rules' share:** at most about $12 to $18 a day of small wins, counting every refused offer as if it filled in full. Today's one refused loser was worth more than a day of that.
- **Correction to the real-money report:** its example (Saturday $81, Sunday $77, Monday $47) runs from a weekend into a weekday, and weekends carry more cheap offers. The weekday-only numbers above still show a halving, so its conclusion holds. It rests on only one or two weekdays on each side.
- **Money per winning market** fell from about $1.96 to about $1.20. Part of that may be the one-bet rule, up to $5–7 a day. It is not only the market.

## Money per day at real-money scale, and bad days
Live buys about 3 of every 4 markets its paper twin buys under identical rules, so I scaled paper by about 3/4.

| choice | per day compared with keeping | worst single loss | worst day seen |
|---|---|---|---|
| **Keep the current version** | — (real so far: $18–23 a weekday in this market) | seen: −$8.26. Possible: about −$90 to −$96 (one full bet at 98c), about −$144 with the last-15-second add | no losing day yet, but only 2.6 days |
| Go back to 09-25 | from −$5 to +$10 a day, middle about $0. About $10–12 a day more in small wins while nothing goes wrong. Each loser like BTC 1:30 PM costs about $23 (a third of a bet) up to about $90 (a full bet) | −$131.98 real (BTC, Sunday 09-27 12:00 AM: two full bets, which the one-bet rule now stops) | −$109.21 (Sunday 09-27) |
| Go back to 09-20 | worse: about −$50 over these 27 hours | −$73 on paper today. Its full-size 45-second bet caused the −$108 real loss (BTC 09-19) | — |

## Turn off just one rule? No, not yet.
- **Seller check:** keep. It already meets its own pre-set keep test, because a market it refused went against us (BTC 1:30 PM). It costs at most $2–6 a day in wins.
- **97.8c cap on the 45-second bet:** keep. It costs at most about $2.50–2.80 a day. It blocks the kind of buy behind BTC 09-19 (−$108) and HYPE 09-21 (−$54).
- **One-bet rule:** keep. It cost $0–2 in the paper test, and $5–7 a day at most by the refused-offer count. It stops a repeat of the −$132 loss.
- **90c floor on the 45-second bet:** keep. It made +$6.49 real on 3 buys, and its stop rule only fires if the total goes below $0.
- **97.9–98c on the 30-second bet again:** keep. 9 markets, 0 lost, about +$10 real.
- **Dropping the 45-second bet entirely:** no. It is ahead over these 27 hours but $9.30 behind over 4.3 days.

## What would change the answer
- **Old rules pull ahead:** the 09-25 practice bot beats today's rules by more than $10 a day for 3 or more weekdays, after removing its 97.9–98c buys, with no more refused losers. Then turn off the one rule the breakdown blames: the one-bet rule or the 97.8c cap. Never the seller check.
- **A rule costs us a loss:** a loss under today's rules that an old rule would have avoided means revisiting that rule.
- **Reads already scheduled:**
  - Daily at 8 AM ET: the 98c stop (a second loss in the first 100 such buys) and the 90c stop (total below $0).
  - Thursday 10-01: the seller check, the 97.8c cap and the one-bet rule.
- **The fair comparison is about to end:** arm-floor90 has 1 loss and stops at its next one. After that, no practice bot runs live's exact settings, so one should be started with live's exact settings.

## Found while checking
The Kalshi money file (`results/kalshi_ledger.json`, built by `research/pinledger.py` `merge()`) keeps one row per market and settlement time. When a penny bot held the same market as pin, the main bot's money gets dropped. Today that happened twice:
- BNB 2:30 AM: the file shows +$0.07; the bot's own records show +$2.83.
- ZEC 1:30 PM: the file shows +$0.50; the bot's own records show +$1.63.

That is $3.89 missing. The file also counts 6 penny-bot markets as main-account money. Both analysts found this and I confirmed the two 1-contract rows. It shifts the daily money totals and the 98c/90c stop reads by a few dollars.

The recorders are alive: kalshi_collector (43 MB) and crypto_feeds (38 MB). There is 50.4 GB of disk free. I stopped nothing, placed no orders, and wrote only in the scratchpad.

My scripts are in `C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\b2dbb5c1-92b0-452a-b1e9-86b7402d3a34\scratchpad\revert\verify\` (`arms.py`, `long.py`, `real.py`); all three self-tests passed.

## Fair paper test

No older version of pin beats today's rules by more than about one small loss on the same markets, so reverting isn't supported. The 09-20 version is $52.55 behind, all from one market that today's seller check refused.

`REPORT.md` was not written: the tool refused to write report files from a subagent. The tables are below and in `C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\b2dbb5c1-92b0-452a-b1e9-86b7402d3a34\scratchpad\revert\fairtest\tables.md`. Every market is in `fair_out.json` in the same folder. `fair.py` has a self-test (planted answer plus an empty world), and it passed before any real data was read. `run.py` and `survey.py` are there too.

**Window:** 107 quarter-hours, 09-28 10:45 AM to 09-29 2:30 PM ET, both weekdays. 15-minute coins only, and only quarter-hours both arms ran. All dollar figures are paper unless marked real.

## 1. Paper arm closest to live
No running arm matches live exactly. The start records don't store `--toxic-fresh`, `--one-full-bet` or `--max-losses`, so I read those from the running processes' command lines.

The closest is **arm-floor90**: pid 3772756, `results/pinrun-paper-20260928T052115Z.jsonl`, same code as live (0f2c2a4bfa3f). Where it differs:
- **`--price-ceiling 0.978` (live 0.98).** This is the only real rule difference: the arm still refuses 97.9–98c on the 30-second bet.
- **No `--early-max-price` (live 0.978).** No effect, because the arm's 0.978 ceiling already caps the 45-second bet at the same price.
- **`bank_divisor` 7.824 vs 7.84.** No effect: paper arms copy live's bet size.
- **`--minutes` 10080 vs 4320, and paper instead of `--live`.** No effect on the rules.

Two cautions:
- arm-floor90 has had 1 loss since it started. `--max-losses 2` stops it buying at the next one, which ends this comparison.
- Yesterday's report described arm-early-full wrongly. It actually runs `--toxic-fresh --price-ceiling 0.978 --max-losses 2` without `--one-full-bet`. So it is the 09-27 07:05Z live build with a full-size 45-second bet, not "09-25 + full-size".

## 2. Each older arm against arm-floor90, same markets

| older arm | shared | only older ($) | only floor90 ($) | older $ | floor90 $ | diff | biggest close | without it | 98c part* | vs live rules (est.) |
|---|---|---|---|---|---|---|---|---|---|---|
| 09-20 frozen | 29 | 25 (−45.04) | 1 (+0.33) | −33.82 | +18.73 | **−52.55** | 09-29 1:30 PM −72.85 | +20.30 | +5.64 | −58.19 |
| 09-25 twin | 29 | 24 (−4.11) | 1 (+0.15) | +25.91 | +18.73 | **+7.18** | 09-29 1:30 PM −21.72 | +28.90 | +11.12 | −3.94 |
| early-full | 27 | 4 (+4.95) | 3 (+1.11) | +10.39 | +18.73 | **−8.33** | 09-28 5:15 PM −12.06 | +3.72 | 0 | −8.33 |
| early-off | 16 | 12 (+18.68) | 14 (+3.69) | +41.85 | +18.73 | **+23.12** | 09-28 8:00 PM +11.31 | +11.81 | +11.63 | +11.49 |
| lateadd-off | 27 | 26 (−5.07) | 3 (+1.32) | +21.92 | +18.73 | **+3.19** | 09-29 1:30 PM −22.93 | +26.12 | +10.73 | −7.54 |

\*The 98c part is 97.9–98c buys on the 30-second bet. arm-floor90 refuses them, but live buys them again since v-reopen98 (live did buy DOGE 3:30 AM, BTC 5:00 AM, NEAR 7:15 AM and NEAR 1:00 PM). "Vs live rules" is the difference minus that part, and is an estimate.

**Split by the rule that made the difference.** Each cell is dollars, then (markets only the older arm bought / shared markets / markets only floor90 bought). A negative number means today's rule helped.

| rule | frozen | twin | early-full | early-off | lateadd-off |
|---|---|---|---|---|---|
| seller gate | −76.97 (8/3/0) | −28.89 (8/2/0) | −0.12 (0/0/1) | −7.90 (2/1/0) | −31.48 (6/2/0) |
| 45-s bet capped at 97.8c | +14.07 (10/2/0) | +5.64 (9/2/0) | – | – | +5.58 (12/1/0) |
| one-full-bet | −0.22 (0/1/0) | +1.77 (0/1/0) | – | – | – |
| 45-s floor 90c | – | −0.15 (0/0/1) | −0.15 (0/0/1) | – | −0.15 (0/0/1) |
| 45-s bet size (full vs third) | −4.07 (0/4/0) | – | +0.72 (0/8/0) | – | – |
| 45-s bet (older arm has none) | – | – | – | +9.87 (0/2/14) | – |
| 98c on 30-s bet (live allows) | +5.64 (4/3/0) | +11.12 (5/4/0) | – | +11.63 (7/4/0) | +10.73 (5/3/0) |
| cap above 98c | −0.33 (0/0/1) | – | −0.84 (0/0/1) | – | −1.17 (0/0/2) |
| other (same book seen a split second apart) | +9.36 | +17.68 | −7.94 | +9.56 | +19.67 |

Live's own refusal records at the same tickers agree with the split. It logged the seller check on BTC 3:30 AM, ETH 8:15 AM and BTC 1:30 PM, the 97.8c cap on the 45-second 97.9–98c markets, and the one-full-bet refusal after its BNB 1:00 PM bet.

## 3. Is any difference bigger than one typical loss ($25–60)?
Only frozen's, and it runs against the older version.

- **BTC 09-29 1:30 PM ET decides frozen.** The older arms bought NO at 96.1c on the 45-second bet with 36 s left. The offer was about 0.1 s old and sellers had taken 95–97% of that side in the last 3 s.
  - The seller check refused it, both live and in arm-floor90.
  - It lost: twin −$22.65, lateadd-off −$23.20, frozen −$73.12 (91 contracts, full size).
  - Without that one quarter-hour, frozen would be +$20.30 ahead: small full-size 97.9–98c winners, no losses.
- **Twin (+$7.18) and lateadd-off (+$3.19)** are within noise. Each is swung by 3 quarter-hours of about ±$10–23.
- **Early-off (09-25 build with no 45-second bet) is the only arm ahead of live rules**, by about +$11 to +$23. Half of that is one market, BNB 09-28 8:00 PM, where every bot with a 45-second bet lost and so did live (−$8.26 real). That lead is under one typical loss and rests on 1–2 quarter-hours.
- **One paper fill favours arm-floor90 by about $11.5 in every comparison.** At XRP 09-28 5:15 PM it paper-filled 91 contracts at 86c for +$11.97; live's order there filled 0. Without that fill, versus live rules:
  - twin: about +$7.6
  - lateadd-off: about +$4.0
  - early-off: about +$23.1
  - early-full: about +$3.5
  - frozen: about −$46.6
- **How big a gap has to be to mean anything:** the same 09-25 settings relaunched on 09-28 trail the twin by $10.04 over 103 quarter-hours with all 50 markets shared. Gaps under about $10 a day are noise.

**Live, for context only (not compared with paper):** 29 markets, 28 won, 1 lost (BNB 8:00 PM, −$8.26), **+$26.44 real**.

## Problem in the Kalshi ledger
`results/kalshi_ledger.json` keeps one row per market and settlement time, and the first row seen wins (`research/pinledger.py` `merge()`). Since the penny bots started trading in subaccounts 1 and 2, this goes wrong two ways:
- **Main-bot money is dropped when a penny bot held the same market.** The penny bot's 1-contract row is kept instead of the main bot's:
  - BNB 09-29 2:30 AM: ledger shows +$0.07, but the main bot filled 96 contracts for +$2.83 by its log.
  - ZEC 09-29 1:30 PM: ledger shows +$0.50, the main bot's log shows +$1.63.
  - Together that understates the main bot by $3.89.
- **Six penny-bot-only markets appear as main-account money.** Five are the forecaster's, one is the ladder's.

This affects pinday, bars and the floor90-guard read. The symptom is measured; that the two rows share one key is inferred from the code (I didn't call the API).

The collector (pid 2532788) and crypto_feeds (pid 105352) are alive, and 50.5 GB of disk is free. I stopped nothing, placed no orders, and wrote only in the scratchpad.

## Real money

REPORT.md was not written: the tool refuses report files from subagents, so the full content is below. Scripts and data are in `C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\b2dbb5c1-92b0-452a-b1e9-86b7402d3a34\scratchpad\revert\realmoney\`.

# Real money since 09-12: the rules or the market?

Times are ET. Money is the main bot's only, from Kalshi's statement (ledger written 2:03 PM ET 09-29). Paper figures are only compared with paper, or one day with another under unchanged rules.

## Answer

**Most of the drop is the market, not the 09-27 rules.** Paper bots still running the old rules also lost about half their income over the same days. At most, the new rules cost about $12-18 a day in paper winners. Today the seller check refused a market that lost, and that loss is larger than a day of what the rules turn away.

1. **Real money.**
   - Before the change, the middle weekday made **+$83.10** on 54 markets (10 weekdays, 09-14..25).
   - After: **Mon 09-28 +$22.72** on 27 markets; **Tue 09-29 +$17.92** on 14 markets up to 2 PM.
   - Weekends: the middle weekend day before made **+$46.80**. Sun 09-27 made **+$22.75** after 1:08 AM.
   - Sun 09-27 as a whole day was -$109.23, because at 12:00 AM the 09-25 build lost -$131.98 on BTC with two full bets.
2. **The market paid less under unchanged rules.** Winners' money per day on paper:
   - 09-25 rules: $81 (Sat 09-26), $77 (Sun), $47 (Mon 09-28).
   - 09-20 rules: $127, $93, $55 on the same days.
   - A third old-rules bot made $90-100 a day on 09-24..26.
   - Markets where the model was at least 99.5 in 100 sure and an offer was at 98c or less in the last 45 s: 82-83 on 09-24/25, 51 on 09-28, 30 today to 2:30 PM.
3. **Cost of the new rules, at most.** This counts every refused offer as filled at full size and scored by the market's result.
   - `missed.py`: +$28.54 on 09-27 (+$21.21 of it is second bets on markets we already held), **+$17.91 on 09-28**, +$11.61 so far on 09-29 (incomplete; 287 markets have no result offline).
   - Against the 09-25-rules paper bot on the same slots: live bought 74 in 100 of its markets under identical rules. That fell to 54 in 100 under the safe build and 47 in 100 since 09-28 10:36 AM, about 10-13 fewer markets a day.
   - On paper those extra markets were worth about +$12 a day in the safe-build window. Since 10:36 AM 09-28 they come to -$4.90 net, because one of them lost (point 5).
4. **Bank and bet barely moved.** The bank went from $1,143 to $1,083 (about 5 in 100 less) and the bet from 97 to 91 contracts. That is worth about $3 a day.
5. **Today the seller check stopped a loss: BTC 1:30 PM 09-29.**
   - The model was 99.6 in 100 sure of NO. The offer was 96.1c with 36 s left, and 97 in 100 of the last 3 s of sell volume hit our side.
   - The seller check refused it and the market settled YES.
   - On paper the 09-25-rules bot lost **-$22.65** on it and the 09-20-rules bot lost **-$73.12**.
   - Same hours today (3:15 AM-2 PM closes): live **+$11.34**, 09-25 rules on paper **-$1.41**, 09-20 rules on paper **-$46.60**.
6. **For the revert question.** Reverting to 09-25 would bring back at most about $12-18 a day of small winners. It would also bring back buys like BTC 1:30 PM (-$23 to -$73 each) and the two-full-bets loss (-$131.98). It would not bring back the missing money, because most of that loss comes from the market.

**How sure:** only 2.6 days have passed since the change, and one loss moves a day by $10-130. The market finding rests on three old-rules paper bots falling together. The rules' cost is an upper bound and cannot see losses the rules prevent, except where a paper bot actually took one (point 5).

**Found while measuring: the money ledger is now wrong on shared markets.**
- `kalshi_ledger.json` keys rows by (ticker, settled_time), and it now holds the clean-room sub-account bots' markets too. I found 10 such markets and excluded 6 of them.
- When the main bot and a sub-account bot hold the same market, only one row survives:
  - BNB 2:30 AM 09-29: the ledger kept the forecaster's 1 contract (+$0.07) and dropped the main bot's 90 (+$2.84).
  - ZEC 1:30 PM: it kept 1 contract (+$0.50) and dropped the main bot's 80.68 (+$1.63).
- So pinday/pinledger totals for 09-29 undercount the main bot by $3.90 and mix in sub-account money. I rebuilt both rows from the bot's order records here; the tool itself is not edited.

## 1. Real money per ET day (15-min coins + hourly BTC; staked = both sides' cost incl. insurance)

| ET day | | version live (deploys that day, ET) | mk | lost | money | staked | per $100 | worst market |
|---|---|---|---|---|---|---|---|---|
| 09-12 | Sat | older; v-a15 2:06 PM, v-hedgefix, v-a16, v-a17, v-brake3 | 96 | 6 | +$38.04 | $1,657 | +$2.30 | SOL 4:00 AM -$18.88 |
| 09-13 | Sun | older; 9 changes (v-a18..v-brake20) | 49 | 1 | +$114.78 | $2,071 | +$5.54 | BNB 12:30 PM -$1.10 |
| 09-14 | Mon | older; v-ladder, v-brake2, v-lossreset, v-against, v-nofloor, v-jump | 61 | 2 | +$81.10 | $3,225 | +$2.51 | BTC 5:30 AM -$34.26 |
| 09-15 | Tue | older; v-withdraw | 36 | 0 | +$76.32 | $2,350 | +$3.25 | none lost |
| 09-16 | Wed | older; v-hedge60 ~10:10 AM | 45 | 3 | +$85.11 | $2,917 | +$2.92 | DOGE 9:00 AM -$12.14 |
| 09-17 | Thu | older; v-selfheal, v-staged, v-early-full, v-a8fix, v-early49 | 55 | 1 | +$99.87 | $3,580 | +$2.79 | BTC 9:15 PM -$27.87 |
| 09-18 | Fri | older; v-bank8, v-early-full2, v-bands, v-late10, +7 more 8:20-11:10 PM | 68 | 0 | +$91.85 | $3,595 | +$2.55 | none lost |
| 09-19 | Sat | older; v-mirror, v-taper, v-hedgefill, v-settledonly; drawdown halt 11:45 PM | 73 | 6 | -$223.46 | $6,728 | -$3.32 | BTC 4:00 PM -$107.95 |
| 09-20 | Sun | older; v-proportion 1:46 AM, v-noboost, v-earlycap, v-nocap | 53 | 0 | +$109.63 | $3,176 | +$3.45 | none lost |
| 09-21 | Mon | older; v-hedgefull, v-hedgelastweek, v-hedge25 | 48 | 2 | -$2.97 | $3,000 | -$0.10 | NEAR 12:45 PM -$59.09 |
| 09-22 | Tue | older; v-early-third 7:42 AM, v-safety1, v-instr1, v-unidefer | 34 | 1 | +$53.70 | $1,630 | +$3.29 | DOGE 10:45 PM -$2.47 |
| 09-23 | Wed | older; v-traj1, v-nospike+v-cap20 ~10 PM, v-lateadd-live 11:31 PM | 54 | 1 | -$42.46 | $3,370 | -$1.26 | BTC 8:30 PM -$130.41 |
| 09-24 | Thu | older; v-lateadd-fix 12:21 AM, v-btcd1 ~1 PM | 63 | 0 | +$93.42 | $2,699 | +$3.46 | none lost |
| 09-25 | Fri | older to 8:23 AM (17 mk +$25.58), then the 09-25 build (36 mk +$81.73); v-zerotake, v-safety2, v-scalein-caps 8:23 AM | 53 | 0 | +$107.31 | $2,775 | +$3.87 | none lost |
| 09-26 | Sat | 09-25 build; v-onepool 3:38 AM (account only) | 53 | 1 | +$46.80 | $2,540 | +$1.84 | BNB 10:30 AM -$20.29 |
| 09-27 | Sun | 09-25 build to 1:08 AM (1 mk -$131.98); +seller check to 3:05 AM (6 mk -$25.16); +97.8c cap to 4:11 AM (2 mk +$7.94); safe build (21 mk +$39.97) | 30 | 2 | -$109.23 | $1,888 | -$5.79 | BTC 12:00 AM -$131.98 (two full bets); ETH 2:30 AM -$32.73 (insurance) |
| 09-28 | Mon | safe build to 10:36 AM (8 mk +$14.02); v-reopen98+v-floor90 after (19 mk +$8.70) | 27 | 1 | +$22.72 | $1,009 | +$2.25 | BNB 8:00 PM -$8.26 (insurance) |
| 09-29 | Tue | reopen98/floor90, to the 2 PM close | 14 | 0 | +$17.92 | $785 | +$2.28 | none lost |

## 2. The middle day, before vs after

Each column is its own middle value, so a row does not add up across.

| | money/day | winners' money | markets | lost | staked | per $100 |
|---|---|---|---|---|---|---|
| Before, weekdays 09-14..25 (10) | **+$83.10** | $92.63 | 54 | 1 | $2,959 | $2.85 |
| Before, weekends 09-12,13,19,20,26 (5) | **+$46.80** | $109.63 | 53 | 1 | $2,540 | $2.30 |
| Before, weekdays 09-21..25 only (5) | +$53.70 | $87.95 | 53 | 1 | $2,775 | $3.29 |
| After: Sun 09-27 from 1:08 AM | +$22.75 | $55.48 | 29 | 1 | $1,561 | $1.46 |
| After: Mon 09-28 | +$22.72 | $30.98 | 27 | 1 | $1,009 | $2.25 |
| After: Tue 09-29 to 2 PM | +$17.92 | $17.92 | 14 | 0 | $785 | $2.28 |

Money per winning market was $1.96 (weekdays before) and $1.98 (Sunday after), then $1.19 on Monday and $1.28 today. That points to fewer cheap offers, not smaller bets.

## 3. The market under unchanged rules (15-min coins; markets / winners' money)

| day | live (real) | 09-25 rules paper | 09-20 rules paper | 09-24 paper bot |
|---|---|---|---|---|
| Thu 09-24 | 63 / $93.42 | – | – | 80 / $100.32 |
| Fri 09-25 | 50 / $107.18 | 49 / $100.15 (from 8:25 AM) | 54 / $109.20 (from 2:30 AM) | 72 / $98.74 |
| Sat 09-26 | 49 / $66.83 | 64 / $80.98 | 65 / $127.18 | 72 / $90.28 |
| Sun 09-27 | 30 / $55.49 | 47 / $77.19 | 50 / $93.46 | stopped |
| Mon 09-28 | 24 / $30.87 | 48 / $47.36 | 48 / $54.75 | |
| Tue 09-29 to 2:30 PM | 13 / $17.86 | 27 / $27.05 | 27 / $31.45 | |

Same clock hours each day (closes 3:15 AM-2 PM), money including losses:

| day | live | 09-25 rules paper | 09-20 rules paper |
|---|---|---|---|
| Fri 09-25 | 15 mk +$21.90 | – | 19 mk +$33.12 |
| Sat 09-26 | 24 mk +$15.58 | 32 mk -$3.63 | 30 mk +$70.01 |
| Sun 09-27 | 16 mk +$31.80 | 21 mk +$44.35 | 23 mk +$54.59 |
| Mon 09-28 | 8 mk +$12.16 | 22 mk +$20.87 | 20 mk +$18.63 |
| Tue 09-29 | 9 mk +$11.34 | 23 mk -$1.41 | 22 mk -$46.60 |

## 4. What the new rules refused

Upper bound, from `missed.py --no-fetch`:

| day | 97.9-98c cap | seller check | 45 s bet cap at 97.8c | 2nd full bet (held mkts) | total |
|---|---|---|---|---|---|
| 09-27 from 1:08 AM | 8 mk +$5.59 | 7 mk, 1 would have lost, net +$1.74 | – | 7 mk +$21.21 | +$28.54 |
| 09-28 | 6 mk +$4.64 | 8 mk +$5.86 | 7 mk +$2.56 | 2 mk +$4.85 | +$17.91 |
| 09-29 to 2:35 PM | lifted | 3 mk +$1.76 (BTC 1:30 PM loser not yet scored) | 11 mk +$2.79 | 6 mk +$7.06 | +$11.61 so far |

Against the 09-25-rules paper bot, same slots. The last column splits the markets only the paper bot bought by live's first recorded reason: got nothing / new rule / old rule.

| window | slots | paper mk | live also | paper-only split | paper $ on those |
|---|---|---|---|---|---|
| identical rules 09-25 8:30 AM - 09-27 1:08 AM | 162 | 114 | 84 (74 in 100) | 24 / 0 / 6 | +$24.67 |
| safe build to 09-28 10:36 AM | 134 | 67 | 36 (54 in 100) | 7 / 15 / 9 | +$28.45 |
| since 09-28 10:36 AM | 105 | 53 | 25 (47 in 100) | 9 / 16 / 3 | -$4.90 (incl. BTC 1:30 PM -$22.65) |

## 5. Bank, bet size, offers

Offers means markets where the model was at least 99.5 in 100 sure and an offer was at 98c or less (or 97.8c or less) in the last 45 s.

| day | bank at start | bet size | offers ≤98c | offers ≤97.8c | orders sent / bought nothing |
|---|---|---|---|---|---|
| 09-21 Mon | $931 | 78 | 59 | 40 | 66 / 13 |
| 09-22 Tue | $916 | 80 | 51 | 35 | 65 / 25 |
| 09-23 Wed | $983 | 84 | 72 | 50 | 80 / 16 |
| 09-24 Thu | $930 | 83 | 83 | 52 | 98 / 25 |
| 09-25 Fri | $1,035 | 89 | 82 | 54 | 91 / 30 |
| 09-26 Sat | $1,143 | 97 | 72 | 52 | 82 / 21 |
| 09-27 Sun | $1,042 | 88 | 47 | 42 | 44 / 8 |
| 09-28 Mon | $1,083 | 91 | 51 | 35 | 41 / 14 |
| 09-29 Tue (14.5 h) | $1,061 | 90 | 30 | 17 | 21 / 7 |

- Offers at 98c or less: before, the middle weekday had 64 (09-14..25). Monday had 51, and today had 30 by 2:30 PM.
- The bot was up 24 hours a day after the change, so downtime explains nothing.
- The share of orders that bought nothing stayed flat: 26-33 in 100 before, 18-34 in 100 after.

## Method

- **Money per market:** pinledger.pnl (payout from `value` times contracts held, minus both sides' costs, minus fees; never `revenue`).
- **Which rows count:** only markets the main bot filled in its own logs.
  - Excluded: 255 coin-race, commodity and Tencent rows, plus 6 rows only a sub-account bot traded.
  - Kept: 2 rows from before any other bot existed (ETH 5:45 AM 09-12, BTC 4:15 PM 09-15), even though no fill for them is in the logs.
  - Rebuilt: the 2 collided rows. No main-bot fill is missing from the ledger.
- **Days and versions:** ET days come from the close time in the ticker. Versions are split at the VERSIONS.md deploy second; "~" times are approximate there.
- **Checks:** money.py's self-test passed (planted insured market, sub-account row, race and commodity rows, a split at a deploy second, an empty world). `missed.py` passed its own self-test and did not write its cache.
- **Recorders:** the collector (pid 2532788, 43 MB) and crypto_feeds (pid 105352, 38 MB) are alive. 50.5 GB of disk and 1.0 GB of memory are free.
- **Scope:** I stopped nothing, placed no orders, and wrote nothing outside the scratchpad folder.

Files are in `C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\b2dbb5c1-92b0-452a-b1e9-86b7402d3a34\scratchpad\revert\realmoney\`:
- money.py
- money.json
- scan.py
- scan.json
- paperscan.py
- paper.json
- context.py
- gapwhy.py
- samehours.py
- mdtables.py
- missed_0927.md
- missed_0928.md
- missed_0929.md
