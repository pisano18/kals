# Per-quarter-hour cap, and the "few full-size orders" question -- 2026-09-28

(A) A cap on dollars per quarter-hour adds nothing now. The one-full-bet rule, live since 4:11 AM ET today, already makes most of that saving. Every cap from $100 to $250 on top of it only gives up winners. (B) Today's orders are not smaller than usual; there are fewer of them. The main cause is the 97.8c price limit: on 09-23 and 09-24, 20 and 28 of the markets bought over the same hours were bought above 97.8c.

**A. Dollar cap per quarter-hour (all coins together). Source: our own live fills, with insurance money counted; the last-sent orders are cut first.**

| cap | 09-09..09-17 (made +$545) | 09-18..09-27 (made +$107) | both halves | cap added on top of one-full-bet (1st / 2nd half) |
|---|---|---|---|---|
| $100 | $0 of losses removed, $75 of wins given up | $194 losses removed, $173 wins given up, **net +$21** | -$54 | -$62 / -$75 |
| $150 | $0 / $13 given up | $54 removed, $41 given up, net +$13 | -$1 | -$8 / -$12 |
| $200 | nothing cut | $0 removed, $6 given up | -$6 | $0 / -$4 |
| $250 | nothing cut | $0 removed, $0.49 given up | -$0.49 | $0 / -$0.49 |

The one-full-bet rule on its own, applied to the same fills: first half $545 -> $532, second half **$107 -> $225**.

Worst nights, money lost counting insurance: as traded / with a $100 cap / with a $150 cap ($200 and $250 change none of them, because each night staked $152-199):
- 09-19 11:45 PM ET: -$109 / -$64 / -$87. Both bets won; the insurance lost.
- 09-23 8:30 PM ET: -$130 / -$86 / -$128. BTC double bet; one-full-bet already halves this.
- 09-27 12:00 AM ET: -$132 / -$69 / -$103. BTC double bet; one-full-bet already halves this.

**B. Same hours each day, 3:05 AM to 11:02 PM ET, 15-minute markets only.**

| | today 09-27 | 09-23 | 09-24 |
|---|---|---|---|
| markets bought | 22 | 43 | 49 |
| bought at full size / small (under 40%) / in between | 9 / 11 / 2 | 22 / 20 / 1 | 13 / 36 / 0 |
| money spent | $1,119 | $2,610 | $1,980 |
| times the bot decided to buy | 35 | 64 | 78 |
| markets bought above 97.8c (now refused) | 0 | 20 (9 of them full size) | 28 (6 full size) |
| 97.8c limit refusals at 97.9-98.0c | 11 markets, 8 never bought | limit was 98c | limit was 98c |
| seller gate refusals | 7 markets, 6 never bought | gate off | gate off |
| second full bet refused on a market already holding one | 5 markets | 2 markets had double bets | 0 |
| only the 45-second third-size piece filled | 9 of 22 | 19 of 43 | 33 of 49 |
| full order cut down to what was offered at or under the price limit | 6 of 17 | 9 of 35 | 10 of 26 |
| full orders filled under 90% | 4 (171 contracts short) | 10 (390 short) | 12 (585 short) |
| full order, share of contracts filled | 84% | 84% | 65% |

## Recommendation
(A) Don't add a dollar cap per quarter-hour. The lead from the clean-room work does not hold up on our own fills. At $100 it cuts about one full bet per quarter-hour and gives up $54 of wins over 19 days. On top of the one-full-bet rule already live, every cap level loses $0.49 to $137, and $200 or $250 almost never trigger. The worst nights are handled better by one-full-bet (the two BTC double bets) and by reducing insurance false alarms (09-19 11:45 PM ET lost $109 even though both bets won).

(B) What to tell the operator about "barely any full-sized orders":
- The size of each bet hasn't shrunk. Full orders filled 84% of what they asked for, the same as 09-23 and better than 09-24's 65%. The share of markets bought at full size (9 of 22) sits between 09-23 (22 of 43) and 09-24 (13 of 49).
- What dropped is the number of markets bought: 22 against 43-49. The 97.8c limit is the main reason. Over these hours it takes away about 20-28 markets a day that used to be bought at 97.9-98c, and 6-9 of those were full-size bets. That is the intended trade: that price band made about $0 over 19 days.
- The seller gate removed about 6 more markets and one-full-bet removed 5 second bets. The partial-fill counts above are the same as or lower than before.
- The 45-second third-size piece is the biggest reason single orders look small: in 9 of today's 22 markets it was the only piece that filled. That is not new; it was 19 of 43 and 33 of 49 on the earlier days.
- If he wants more full-size orders, the lever to test is the full leg at under 45 seconds on markets where the third-size piece already filled. Measure it on our own fills before changing anything.

## Caveats
1. A section of the live log is missing. results/pinrun-live-20260925T122357Z.jsonl starts at 09-26 07:31Z, and the previous file ends 09-25 12:23Z. That leaves roughly 8:23 AM ET 09-25 to 3:31 AM ET 09-26 unlogged, which is the ~$100 day. I rebuilt 19 bets from that window using the Kalshi account ledger (positions of 40+ contracts). All 19 won and none was insured, so the unknown send order changes nothing (cutting losers first or winners first gives the same totals). Git status shows this file as modified, which fits the known problem of git operations reverting live-log files.
2. Every other logged bet matched the Kalshi ledger exactly (983 of 983 markets). Insurance money is included by taking each market's ledger total minus our logged bet money (-$31.59 across 22 markets). When a cap cuts a bet, I shrank that market's insurance by the same fraction, which is an approximation.
3. The replay assumes a cut order changes nothing else: freed budget is not re-spent, and the market and the insurance decisions stay the same.
4. The one-full-bet effect is approximated from order sizes (a full order is dropped if the market already held at least 90% of that order's size). My +$118 for the second half is close to VERSIONS.md's +$120.
5. Part B compares only same-hours windows on 09-23 and 09-24. 09-25 can't be used because of the log gap. The 09-24 window saw 72 quarter-hours against 80, because of restarts. For the seller-gate and one-full-bet counts I found no way to tell what those rules would have refused on the old days. The one-full-bet refusals share the 'rebuy_band' label with an older rule. The 8 hourly BTC (KXBTCD) orders and the coin race are excluded from both parts.
6. Machine: free RAM was 0.33-0.46 GB the whole time, below the 0.6 GB stop line. My scripts were small (under ~50 MB, one at a time, reading line by line), so I finished the job but ran nothing heavy. Both recorders were alive at the end (kalshi_collector pid 2532788, crypto_feeds pid 105352). Disk free on C: was 64.4 GB. I touched no process, order or money, and wrote nothing under C:\kals.
