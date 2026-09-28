# Q0928 frozen -- is the 09-20 version better, or does it cause losses?

Written 2026-09-28 ~05:40Z (1:40 AM ET) by a read-only analysis agent. Times ET. Paper numbers are paper; money numbers are Kalshi's ledger.

## Answer, reason first

**It is not better in any way that would hold up with real money. Its paper lead over the live settings is about $107 in 2.7 days. About $41 of that is luck on one market. About $60 comes from the 90c early-buy floor, and when that floor ran with real money it LOST $110 on 14 markets.**

1. **Right now:** the frozen 09-20 bot shows +$248.08 on paper since 09-25 2:30 AM ET (172 markets, 3 losers). The live bot made +$25.19 of real money over the same closes (127 markets, 3 losers; live has made no bets since 09-27 11:45 PM ET). That $217 gap is mostly the flattery built into paper, not the settings. Its paper twin runs exactly the live 09-25 settings, and on the same closes the twin shows +$130.03 against live's +$19.32 real. So paper runs about $111 above real money even with identical settings.
2. **The fair comparison is paper against paper:** frozen +$239.01 against the twin's +$132.34 on 260 shared closes, so frozen leads by **+$106.66**. Both halves of the window are positive (+$79.95, then +$26.71).
3. **Where the $107 comes from:**
   - **+$41.12, luck.** On BNB 09-26 10:30 AM both bots have the same safety gates. The twin happened to see an 89c offer and bought, losing $41. The frozen bot saw 75c a moment later and its crash guard refused.
   - **+$60.15, the 90c early floor.** 12 paper buys at 90-94.9c with 45 s left, all winners at about $5 each. Paper cannot see the offers that are sold to us because the seller knows something. Our real record at the same prices, 09-17 to 09-27: 18 markets, **3 lost (-$66.34, -$43.92, -$59.09), net -$98.88**. At full size (09-17 to 09-21) it was 14 markets, 3 losers, **-$110.17**. One loser wipes out about 11 winners. That is why it moved to 95c on 09-24 (v-cap20).
   - **+$59.78, the full-size 45-second buy** on markets both bots traded (91 markets). No loss fell in those markets in this window. The arm that isolates this setting, arm-early-full (live settings plus a full-size early buy, since 09-27 4:09 AM), is only +$3.85 ahead of the twin over 85 closes.
   - **-$35.66, no late add.** Frozen lacks the last-15-seconds add, which live has had since 09-24; -$25.22 of this is on the 9 markets where the twin used it.
   - **-$6.24, insurance settings.** The 60-in-100 trigger fired 4 times and bought nothing each time: partial insurance buys 0 until confidence falls below 40 in 100. The 60c price cap never blocked anything, because both emergency buys skip it. So in practice "0.60 + 60c" = "0.40 with half-insurance".
   - **+$0.85, no hourly BTC ladder:** nothing.
   - **-$13.33, other markets** only one bot entered (timing): twin-only 15-minute markets other than BNB -$20.60, frozen-only markets that were not 90c buys +$7.27.

## Every loss since 09-25 2:30 AM ET (live and the frozen arm)

| market (ET close) | LIVE real $ | live bought | live insurance | FROZEN paper $ | frozen bought | frozen insurance | twin paper $ | why the frozen result differs |
|---|---|---|---|---|---|---|---|---|
| BNB 09-26 10:30 AM | **-20.29** | 98 NO at 59.5c, 5 s left (the book was crashing) | 98 YES at 58c (confidence 3 in 100) | **no bet** | -- | -- | -41.12 (98 at 89c, insured at 51c) | luck: same gates in both arms; frozen saw 75c and its crash guard refused |
| ETH 09-26 10:15 PM | no bet | -- | -- | **-3.83** | 20 NO at 97.9c, 35 s left | 10 at 40c (confidence 39 in 100) | -10.09 (insured all 20 at 50c) | bet WON; insurance was the cost; half-insurance cost less |
| BTC 09-27 12:00 AM | **-131.98** | 99 at 97.9c + 99 more at 97.0c, both at 30 s = 198 contracts | all 198 at 67-68c (4 in 100) | **-65.50** | 27 at 97.0c (31 s) + 72 top-up at 97.6c = 99 | all 99 at 67c (4 in 100) | -63.96 (99 contracts) | frozen held HALF as many contracts. Live's second full bet on the same market is what v-onefull removed on 09-27 4:11 AM; it is not a 09-20 setting |
| ETH 09-27 2:30 AM | **-32.73** | 88 YES at 83.5c, 17 s left | all 88 at 51c (35 in 100) | **-18.11** | 88 YES at 89.0c, 17 s | half, 44 at 60c (35 in 100) | -12.28 (33 bought, 33 insured at 49c) | bet WON; the loss was the insurance. Half-insurance lost about $15 less. My arithmetic (not measured): live with half-insurance would have been about -$10 |
| hourly BTC 09-27 7 PM | no bet | -- | -- | not traded | -- | -- | -1.39 | frozen has no hourly ladder |

Frozen's own record: 3 losing markets (the three above it bet on). It bought insurance on exactly those 3. It had one more alarm, ETH 09-27 2:45 PM, where it bought nothing (confidence 49 in 100) and the bet won.

## Totals, per ET day

(b) Frozen paper vs LIVE real money, closes where both ran (through 09-27 11:45 PM, the last ledger settlement):

| ET day | frozen markets | frozen paper $ | live markets | live real $ |
|---|---|---|---|---|
| 09-25 | 54 | +109.20 | 44 | +87.60 |
| 09-26 | 65 | +123.35 | 53 | +46.80 |
| 09-27 | 50 | +9.85 | 30 | -109.21 |
| total | 169 | +242.40 | 127 | +25.19 |

Frozen on 09-28 so far: 3 markets, +$5.68. Live: none.

(a) Frozen vs its paper twin (live-identical 09-25 settings), 260 shared closes:

| ET day | closes | frozen $ | twin $ | gap $ |
|---|---|---|---|---|
| 09-25 (from 8:30 AM) | 62 | +100.12 | +100.17 | -0.05 |
| 09-26 | 96 | +123.35 | +30.07 | +93.28 (BNB luck +41) |
| 09-27 | 96 | +9.85 | -0.21 | +10.06 |
| 09-28 | 6 | +5.68 | +2.31 | +3.37 |
| total | 260 | +239.01 | +132.34 | **+106.66** |

Yardstick, twin paper vs live real on the same closes: twin +$130.03, live +$19.32. That is the paper flattery. Most of it is 09-27, where live's double bet on BTC lost $132 and the twin lost $64.

Other arms: arm-early-off (no 45-second buy) vs twin: -$16.42 over 260 closes. arm-early-full vs twin: +$3.85 over 85 closes. Frozen vs arm-early-full: +$5.25 over the same 85 closes.

## Real-money record of the 45-second buy by price (Kalshi ledger, all live logs)

| first early price | period (ET close) | markets | lost | net $ | avg early contracts |
|---|---|---|---|---|---|
| 90-94.9c | 09-17..09-21 (full size) | 14 | 3 | -110.17 | 86 |
| 90-94.9c | 09-22..09-24 (third) | 3 | 0 | +9.35 | 27 |
| 90-94.9c | 09-25..09-28 | 1 | 0 | +1.94 | 30 |
| 95c+ | 09-17..09-21 (full size) | 184 | 3 | +59.39 | 61 |
| 95c+ | 09-22..09-24 (third) | 86 | 0 | +63.15 | 26 |
| 95c+ | 09-25..09-28 (third) | 80 | 0 | +58.72 | 25 |

The 90-94.9c losers were BTC 09-19 2:00 AM (-$66.34), HYPE 09-19 11:45 PM (-$43.92) and NEAR 09-21 12:45 PM (-$59.09). Caveat: 09-19 was the day of the insurance bugs (fixed 09-19/09-21), so two of the three may have lost more than they would today. NEAR 09-21 came after the fix. The full-size and third-size periods are different weeks, so the 95c+ rows do not separate size from the calendar.

## What this sample can and cannot say

- 2.7 days, 3 losing markets per bot. One $40-130 loser moves any total here by more than the whole settings gap. The gap without its top 3 markets is +$50.
- Paper fills come from offers that were sitting there. Our real fills come from sellers who chose to sell to us, and only those get picked off. So paper is structurally blind to the losers of the 90c early buy, the setting that makes it look best. The loss count must come from real fills (the table above), and those say the 90c floor loses money.
- The "09-20 version" is really the 09-20 flags running on the 09-25 early-morning code. It includes the spike gate and 10c cap from 09-24. It lacks the late add, the toxic-seller gate, the 97.8c ceiling and one-full-bet. Its first 3-day run (09-22 to 09-25, noted +$309 paper) cannot be checked: that log was cut on disk.
- Prior reports read before the live log was restored (09-26 3:31 AM to 09-27 11:45 PM ET) undercounted live. The TEST_AUDIT figures (+$104 vs twin; frozen +$124 vs live +$28 on 113 shared markets) were computed AFTER the repair and match this report (+$106.66; now 114 shared markets, frozen +$126.19 vs live +$30.26).

## Recommendation

- Do not switch to the 09-20 version.
- Do NOT bring back the 90c floor. It is the biggest piece of the paper lead and lost $110 of real money at full size.
- Full-size early buy: leave it at a third. Let arm-early-full run to its 10-04 read. Today it is only +$4.
- The one setting with a real-money argument is **half-insurance when confidence is 20-40 in 100.** It would have saved about $22 on ETH 09-27 2:30 AM. That is one market, and v-hedgefull (09-21) turned it off after replaying every real alarm, so it needs its own paper arm against today's live build before anything changes.

Scripts: scratchpad `q0928/frozen/` (frozen.py, analyse.py, early_live.py, extra.py; each self-tests with a planted answer and an empty world). Recorders alive (kalshi_collector pid 2532788, crypto_feeds pid 105352); free disk 63.8 GB.
