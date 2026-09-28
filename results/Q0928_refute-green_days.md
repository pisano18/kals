# Refuter check of "why 09-09..09-18 was green" (Q0928_green_days.md) -- 2026-09-28

**Verdict: the finding survives.** The pattern held when I rebuilt it from the Kalshi ledger and the live logs, including the restored 09-25 log. We did not lose more often after 09-18. We lost MORE PER LOSS. Most of the extra loss came from three things: two double bets on BTC, the 45-second leg at full size (09-17..09-22), and the six changes on 09-19. The small differences I found do not change any conclusion (listed at the end).

Sources: `results/kalshi_ledger.json` (our own settled markets only; crypto coins + hourly BTC; coin race, oil, gold, gas and copper left out), and every `results/pinrun-live-*.jsonl` (entries = kind=order with a fill; hedges come from kind=hedge and none of them appear as entries). ET day rolls at 04:00Z. Nothing is valued from trades we did not make.

## 1. Daily money: re-derived, matches to the cent

Each day's total from the ledger matches the finding's table exactly (09-09 +$48.74 ... 09-18 +$91.85; 09-19 -$223.46; 09-27 -$109.21). Every ET day 09-09..09-18 was green. 09-10 (+$0.23) and 09-11 (+$1.25) were only just green.

## 2. How often we lost vs how much a loss cost

Here a market counts as "lost" when its total, with any insurance included, was below zero. The finding counted "the bet's side lost" instead. Both ways give the same answer.

| period | markets | markets that lost money (per 100) | net | avg money-losing market | avg winning market | $ per $100 spent |
|---|---|---|---|---|---|---|
| 09-09..09-18 | 543 | 18 (3.3) | +$637.29 | -$12.05 | +$1.63 | +2.95 |
| 09-19..09-27 | 461 | 13 (2.8) | +$32.76 | -$62.38 | +$1.88 | +0.12 |

## 3. Markets checked by hand (ledger vs log)

| market (ET) | what we bought (log) | insurance (log) | ledger arithmetic | net |
|---|---|---|---|---|
| BTC 09-27 12:00 AM | YES 99 @ 97.89c + 99 @ 97.0c, two separate decisions 0.4 s apart | NO 99 @ 67c + 99 @ 68c | 198 paid out - $192.94 - $133.65 - $3.39 fees | -$131.98 |
| BTC 09-23 8:30 PM | YES 88 @ 87.0c + 88 @ 86.13c, 0.3 s apart | NO 176 at 79.5-87c | 176 - $152.36 - $151.13 - $2.92 | -$130.41 |
| BTC 09-19 4:00 PM | NO 110 @ 98c, 45 s before close | none. The log shows `pause` "loss bound ... past $-200" in the same second as the buy, lasting until settlement | 0 - $107.80 - $0.15 | -$107.95 |
| BTC 09-19 2:00 AM | NO 70 @ 94.4c, 35 s before close | none. The log ends 5 s later, and commit c5fdf7f says the crash "killed the live bot". The early leg's edge cap went from 3c to 10c at 1:08 AM ET | 0 - $66.08 - $0.26 | -$66.34 |
| BNB 09-19 1:45 AM | YES 76 @ 75c | `hedge_wait_price`: ask 21c, threshold 0.60. Then it chased at 51c, 70c and 76c and got 1 contract | ledger | -$57.76 |
| BTC 09-14 1:30 AM (the good period) | NO 60 @ 97.2c | YES 60 @ 58c at 21% confidence | 60 - $34.80 - $58.32 - $1.14 | -$34.26 |

## 4. The finding's other numbers, re-computed

| claim | the finding | mine |
|---|---|---|
| 09-19: markets first bought on the 45-second leg | 50 markets, -$172.84 | 50, -$172.84 |
| 09-19: markets first bought at 30 s or less | 23 markets, -$50.63 | 23, -$50.63 |
| 45-second leg at a third of a bet | 208 markets, +$168 | 208, +$168.31, and 0 markets lost money |
| 45-second leg at full size (09-17..09-22) | 164 markets, -$92 | 164, -$92.15, and 7 markets lost money |
| chance that luck alone makes 5 of 164 vs 1 of 208 | about 6 in 100 | 6.2 in 100, one-sided |
| first buy under 93c | 09-09..09-18: 75 markets, +$238. 09-19..09-27: 31 markets, -$107 | 74, +$238.06. 30, -$104.29 |
| the good period's real losses (09-13..09-18) | 3 markets, each insured, each cost $28-34 | confirmed: BTC 09-14 -$34.26, HYPE 09-14 -$29.90, BTC 09-17 -$27.87. DOGE and NEAR on 09-16 won the bet and lost on insurance only |

## 5. Does the one-full-bet rule really stop the double bets?

Since it went live (09-27 4:11 AM ET), 21 markets have been bought. None took a second full bet. Two markets show two orders in the same second. Each was one bet split across two prices: XRP 60.88 + 20 contracts = 80.88, under one bet of about 88; HYPE 2 + 4 contracts. The rule sits in the entry path (`rebuy_ok`, research/pinrun.py line 2943). The insurance path is separate, so the rule cannot block insurance.

## 6. Differences I found (none changes a conclusion)

- **"Almost no market held more than one bet (3 of 543)" in the good period.** The finding's own table says 2 markets, and I count 5 markets with two full-leg orders (all on 09-17 and 09-18, all won). After 09-18 I count 35 such markets, 4 of which lost money (-$266). The "9 stacked, 2 lost" figure in the finding uses a stricter size cutoff.
- **"8 losses fell on 09-10..09-12 when every bet was a fixed 20 contracts."** On 09-12 the automatic sizing reached 66 contracts, but every losing market that day held 20 contracts or fewer, so the point stands.
- **"$91.50 a day then vs $82 now" is not a like-for-like comparison.** The good-period days include loss days (09-14). The later days are only the days with no loss.
- **The full vs third comparison of the 45-second leg is also a comparison of different days and bet sizes.** Full size ran 09-17..09-22. A third ran mostly from 09-22 on. A full bet also loses three times as many dollars on the same miss. The 6-in-100 figure does not pass once the finding's roughly 9 comparisons are taken into account. It supports "don't go back to full size". It does not prove full size is worse.
- **What this sample can detect.** 22-31 losing markets in total cannot detect a change in how often we lose smaller than about 2 in 100. The loss-size difference is carried by about 6 markets.

Read-only. Nothing under C:\kals was touched. Afterwards both recorders were alive (collector 42 MB, feeds 26 MB), with 64 GB free disk. Scripts: scratchpad `q0928/refute-green_days/` (led.py and check.py are self-tested).
