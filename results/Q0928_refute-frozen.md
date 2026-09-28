# Q0928 refute-frozen: checking "is the 09-20 version better?"

Written 2026-09-28 about 2:10 AM ET by a read-only checking agent. It checks `results/Q0928_frozen.md`. Times are ET. Paper numbers are paper money; live numbers come from Kalshi's ledger (written 11:46 PM ET 09-27).

## Verdict: the answer holds. One real-money number is overstated by about half.

**"No, the 09-20 version is not better with real money" survives.** I re-counted every headline number from the raw logs and the ledger, and they match. The weak spot is the main real-money reason given for not bringing back the 90c early floor ("it lost $110 at full size"). One of its three losers, HYPE 09-19 11:45 PM (-$43.92), was a bet that WON. The money was lost on insurance bought at confidence 44-50 in 100. The 09-20 version's insurance rule buys nothing at that confidence, so under the 09-20 rules that market makes about +$5.70. Re-scored that way, the 90c floor at full size is about **-$60, not -$110** (my arithmetic, not measured). It is still negative. But it rests on 2 real losing bets out of 18 markets, which is too few to call the floor either good or bad.

## Re-counted (my scripts, same sources)

| claim | report | my count | match |
|---|---|---|---|
| frozen paper since 09-25 2:30 AM | +$248.08, 172 markets, 3 lost | +$248.08, 172, 3 | yes |
| frozen vs twin, shared closes | +$239.01 vs +$132.34, gap +$106.66, 260 closes | same money, 261 closes | yes (close count differs by 1) |
| gap by ET day | -0.05 / +93.28 / +10.06 / +3.37 | same | yes |
| gap without its top 3 markets | about +$50 | +$50.07 | yes |
| frozen paper vs live real | +$242.40 (169 markets) vs +$25.19 (127) | same | yes (272 closes, not 273) |
| twin paper vs live real | +$130.03 vs +$19.32 | same | yes |
| 90c floor, markets only frozen bought | 12 markets, +$60.15 | 13 frozen buys at 90-94.9c, +$67.28; minus ETH 09-26 7:30 PM (twin also bought there) = +$60.15 | yes |
| late add frozen lacks | -$25.22 on 9 markets | -$25.22 on 9 | yes |
| early-full arm vs twin | +$3.85, 85 closes | +$3.85, 86 closes | yes |
| early-off arm vs twin | -$16.42 | -$16.42 | yes |
| real 90-94.9c early buys | 18 markets, 3 net losers, -$98.88; full size -$110.17 | same | yes |

## Hand checks (ledger: payout on the winning side minus both costs minus fee)

| market (ET close) | live: what happened | ledger net | frozen paper | twin paper |
|---|---|---|---|---|
| BTC 09-27 12:00 AM | 2 full bets: 99 YES at 97.9c + 99 YES at 97.0c (30 s left); insured all 198 with NO at 67-68c; result NO | $198 - $192.94 - $133.65 - $3.39 = **-$131.98** | 27 + 72 = 99 contracts, all insured at 67c: **-$65.50** | 99 contracts: **-$63.96** |
| ETH 09-27 2:30 AM | 88 YES at 83.5c; insured all 88 at 51c; result YES (the bet won) | $88 - $73.46 - $44.88 - $2.39 = **-$32.73** | 88 at 89c, insured 44 at 60c: **-$18.11** | 33 at 86c, insured all 33: **-$12.28** |
| BNB 09-26 10:30 AM | 98 NO at 59.5c; insured all 98 at 58c; result NO (the bet won) | $98 - $58.34 - $56.62 - $3.33 = **-$20.29** | refused (crash guard saw 75c) | 98 at 89c, insured at 51c: **-$41.12** |
| BTC 09-19 2:00 AM | early NO, 70 at 94.4c, no insurance; result YES | **-$66.34**, a real losing bet | -- | -- |
| NEAR 09-21 12:45 PM | early YES, 81 at 91.1c; half insured at 70c, rest at 90.5c; result NO | **-$59.09**, a real losing bet | -- | -- |
| HYPE 09-19 11:45 PM | early NO, 104 at 94.1c; insured all 104 at 46c (confidence 44-50 in 100); result NO (the bet WON) | **-$43.92**: the insurance lost, not the bet | the 09-20 rule buys no insurance at 44-50 in 100, so about +$5.70 | -- |

BNB really was luck. In the same second, both paper bots refused a 94.1c offer at the spike gate. Then the twin's book showed 89c and it bought, while frozen's showed 75c and its crash guard refused. Their gate settings are the same.

## Corrections to Q0928_frozen.md

1. **The 90c floor's real record, scored under the 09-20 insurance rules, is about -$60 at full size (not -$110), and about -$49 over all 18 markets (not -$99).** Of the 18 markets, 2 bets lost (BTC 09-19, NEAR 09-21) and 16 won, at about $4.70 each. At these prices the floor breaks even if about 7 bets in 100 lose. We saw 2 in 18 (11 in 100), and with 18 markets the true rate could be anywhere from about 1 to 35 in 100. So real money does not show that the floor loses money. It also does not show that it makes money.
2. The report's warning that "09-19 was the day of the insurance bugs" fits HYPE, where the insurance was the whole loss. It does not fit BTC 09-19 2:00 AM, which bought no insurance at all.
3. "Live made no bets since 09-27 11:45 PM ET": the last live pinrun market closed at 11:15 PM ET. 11:45 PM is the ledger's last coin-race settlement. There were no live pinrun fills after that, so the point stands.
4. The recommendation changes nothing live: it only proposes a paper arm, so it cannot block insurance. In the 09-20 version, emergency insurance skips the 60c price cap (every emergency insurance buy in the frozen log lists `hedge_price` among the rules it skipped). The only insurance frozen missed was 09-25 6:00 PM ("index_stale", blind, not blocked), and that hit both bots.

## What this cannot tell you

2.7 days, and each bot lost 3 markets. A single loss of $40-130 is bigger than the whole settings gap. Paper fills are offers that were sitting on the book, so paper cannot show the losing fills that sellers choose to give us. No paper loss count here is our loss rate.

Scripts: scratchpad `q0928/refute-frozen/` (check.py, floor.py, early_real.py, arms.py, late.py; check.py and floor.py self-test with planted answers and empty inputs). Recorders alive (kalshi_collector pid 2532788, crypto_feeds pid 105352). Free disk 63.7 GB.
