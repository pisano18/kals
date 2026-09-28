# Q0928 refute: floor_math (checked 2026-09-28)

**Verdict: the finding stands. The recommendation to change no flag holds.** I re-ran the numbers the decision rests on myself. They match, apart from one full-size dollar figure and one hedge price, and neither changes the decision.

## What I re-checked, and what I got

| claim | my re-run | status |
|---|---|---|
| The 60c rule can't act with today's 0.40 trigger | `research/pinrun.py`: the hedge fires only at belief < `HEDGE_BELIEF` (0.40). The panic rule is on at belief <= `HEDGE_PANIC` (0.40, and live does not override it). The price check reads `if not _panic and not hedge_price_ok(_ask)`, and the live settings have no `--hedge-jump`. So every hedge that fires is a panic hedge, and the price rule is skipped | confirmed |
| 13 panic records since 9/19, all skip the price rule | 13 of 13 | confirmed |
| 3 records where a hedge waited on price, all under the old 0.60 trigger | BNB 9/19 1:44 AM ET (belief 0.227, other side 21c), NEAR 9/19 5:14 PM, HYPE 9/19 11:44 PM | confirmed |
| While the floor was 90c (9/18 2:51 AM to 9/23 10:22 PM ET): 16 bets at 90-95c, 2 lost, -$73.99 | 16 markets, 2 lost, -$73.84 (the gap is fees). BTC 9/19 2:00 AM -$66.34 (94.4c, 70 contracts). NEAR 9/21 12:45 PM -$74.24 on the 45-second bet (91.1c, 81 contracts) | confirmed |
| At 95-98c in the same window: 188 markets, 2 lost, +$82.99 | 188 markets, 2 lost, +$84.46 | confirmed |
| BTC 9/19 2:00 AM had no hedge because the bot's run ended 30 s before close | the run ended at 1:59:30 AM ET; the market closed at 2:00 | confirmed |
| BNB 9/19 1:45 AM -$57.76; HYPE 9/19 11:45 PM -$43.92 | -$57.76; -$43.92 (from the Kalshi ledger) | confirmed |
| 14 bets turned away at 90-95c since the 95c floor, all won, +$18.97 at a third of a bet | 14 markets, **0 lost, now checked against Kalshi's own results** (the finding had judged 13 of them by our model). +$19.05 at a third of a bet | confirmed, and stronger |
| The same 14 at full size: +$57.08, $853 at risk | +$76.82, $1,188 at risk, using the size the bot logged at the time | the dollar amount differs; the direction is the same |

## What I did not re-run
- The hedge replay (-$68 for the 0.60 trigger with the 60c rule, +$23 for the 09-20 build). This is a replay, so it is a hypothesis, not evidence. I checked one market by hand. HYPE 9/19 11:45 PM ET: live hedged at 46c when belief was 0.50, so today's 0.40 trigger would not have fired there. That fits the replay's "+$5.73 instead of -$43.92". The finding said "insured at 43c"; live actually paid 46c.

## What the sample can and can't tell
In the 90-95c band we have 30 markets and 2 losses in all: 2 of 16 that we bought, 0 of 14 that were turned away. The turned-away 14 are not our fills, so they can't show the bad fills we get when someone who knows better sells to us. 2 losses in 30 can't tell a 3-in-100 loss rate from a 12-in-100 one. Break-even at a 93c average price is about 7 losses in 100.
