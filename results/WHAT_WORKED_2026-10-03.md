# WHAT_WORKED_2026-10-03 -- measured verdicts on the changes of 09-27 .. 10-03

Operator 2026-10-03: "Remember what stuff from the past few days actually did work, save it." Only measured
results (our own fills + Kalshi money, never the replay). "Too few to tell" is a verdict, not a pass.

## Worked -- keep

| change | live since | measured | source |
|---|---|---|---|
| 98c back on the 30-second bet (v-reopen98) | 09-28 14:36Z | 56 buys at 97.9-98c in 45 markets, 0 lost | reopen98-guard read 10-03 |
| Penny ladder, top rung, subaccount 1 | 09-29 / size 5 09-30 | 09-27..10-03: 58 markets, 0 lost, +$6.59, +2.07% on money bet (~+9% of its ~$70 pot); paper top rung matched live to the penny (+$1.01 vs +$1.10 on 10-02) | Kalshi sub1 settlements; PAPERS 10-02 |
| Ladder 404-limbo fix + 2-bids-a-market cap (v-ladder-limbo/caps) | 10-03 07:47Z | fix: the rails were blind 0.4-2.8 s after a filled bid's cancel 404'd; cap costs ~$0.20/day, halves the most on one market (28% -> 14% of pot) | live fills 09-30..10-03; WHY in VERSIONS |
| Forecaster crash guard (v-crash-guard) | 09-30 | KEEP at its read | READS_DUE crash-guard |
| Forecaster skip first 2 s (v-fc-r28) | 10-03 06:12Z | on its own live record: 6 losing fills ($23.10) avoided vs 9 winners ($3.58) given up = +$19.52; paper's first 26 closes -$14 vs base (too small) | live log 10-02 |
| Forecaster overall (subaccount 2) | 09-29 | 09-27..10-03: 59 markets, 10 lost, +$5.08, +1.96% on money bet (~+8% of ~$60) | Kalshi sub2 settlements |
| Coin race at 20 a leg, not 40 | back to 20 on 10-03 06:16Z | at 40 it filled 39 of 100 asked, $3.49/day vs $4.34/day at 20, and doubled a full loss (~$37) | RACE_WHY_2026-10-02 |
| Bank-move check (v-bankmove) | 10-03 08:15Z | first real test 10-03 10:00Z: race stake out (-$18.13) and back (+$20) both logged 'unexplained', mark untouched; the old code would have called them a withdrawal and a deposit | live log |

## Did NOT work -- reverted or reverting

| change | measured | action |
|---|---|---|
| 45-second bet allowed at 90-95c (v-floor90, 09-28) | 11 markets, 10 won (+$25.32), 1 lost (NEAR 10-03 -$86.95) = -$61.63; its own pre-registered stop says back to 95c | v-floor95 prepared, awaiting the main-bot restart |
| Coin race at 40 a leg (v-race40, 09-30) | see above | reverted 10-03 |

## Neither -- too few losers to tell (results/WHY_FLAT_2026-10-03.md)

| change | gave up (winners) | saved (losers) |
|---|---|---|
| 45-second bet capped at 97.8c (v-ceiling978, 09-27) | <= $47 in 7 days (88 markets) | 1 loser, $29 |
| Seller check (v-toxic-live, 09-27) | <= $79 (55 markets) | 3 losers, $58 |

## The main bot's week, for the record

Kalshi, by ET close day: 09-13..19 +$198.84; 09-20..26 +$373.82 (the 09-25 build); 09-27..10-03 -$1.44
(9 losing markets both of the last two weeks; losses $246 -> $368; crypto markets bought 351 -> 180).
45% of this week's losses (-$164.71) were bought on 09-27 before the 9/27 rules went live; the other five
(-$192) passed every rule: buys under 20 s, a 14-minute-old dumped offer, a last-30-s jump, false-alarm insurance.
