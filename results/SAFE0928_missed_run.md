# Missed trades -- 09-27 1:08 AM ET to 09-28 10:21 AM ET

Written by `python research/missed.py` (read-only). Our money is from Kalshi's ledger. A refused market's win/loss is the MARKET's result (everyone's offers, not the ones sold to us): the $ column is the MOST a gate could have cost us, and its loser count is the FEWEST losses it saved us. Never read it as how often we lose.

Logs read: 5 live file(s); 2615 refusal records; 44 of our buys (insurance excluded); results looked up online this run: 0; markets still without a result: 0.

Our real money in the window (Kalshi ledger, by settle time): 15-minute coins 37 markets, 1 lost, +$36.79; other (race etc.) 8 markets, 0 lost, +$3.98.

Seller gate share (its OFF line: more than 25 in 100 of early entries): on the 45-second leg it refused 5 of 20 markets that leg wanted (25 in 100); counting every buy with more than 20 s left, 9 of 34 (26 in 100).

## Per gate

| gate | markets refused (closes) | we bought anyway (our result: won / lost) | never bought: would have won / lost / not settled | contracts we'd have taken, typical price | most it could have cost us (wins) | losses it saved at least | net | one loss like these would cost | flag |
|---|---|---|---|---|---|---|---|---|---|
| price ceiling (no buys over 97.8c) | 236 (97) | 24 (14 held already, 10 later; 24 / 0) | 212 / 0 / 0 | 6204 at 99.0c | +$55.26 | +$0.00 | +$55.26 | -$28.99 | FLAG: mostly winners |
|   of which 97.9-98.0c (the 09-27 v-ceiling978 change) | 18 (18) | 4 (3 held already, 1 later; 4 / 0) | 14 / 0 / 0 | 543 at 98.0c | +$10.22 | +$0.00 | +$10.22 | -$37.97 | FLAG: mostly winners |
| seller gate (fresh offer while takers sell our side) | 10 (10) | 1 (1 held already, 0 later; 1 / 0) | 8 / 1 / 0 | 254 at 97.4c | +$5.98 | -$0.93 | +$5.05 | -$27.37 |  |
| second full bet (one-full-bet / cheaper-offer band) | 8 (8) | 8 (8 held already, 0 later; 8 / 0) | 0 / 0 / 0 | no price logged | - | - | - | - |  |
| 45-second leg floor (under 95c) | 4 (4) | 0 (0 held already, 0 later; 0 / 0) | 4 / 0 / 0 | 118 at 94.6c | +$9.12 | +$0.00 | +$9.12 | -$27.05 | FLAG: mostly winners |
| edge floor (model edge under 0.3c) | 552 (125) | 26 (21 held already, 5 later; 26 / 0) | 526 / 0 / 0 | 18899 at 99.9c | +$36.94 | +$0.00 | +$36.94 | -$35.86 | FLAG: mostly winners |
| confidence (model not sure enough) | 198 (89) | 28 (0 held already, 28 later; 28 / 0) | 159 / 11 / 0 | no price logged | - | - | - | - |  |
| depth (too few contracts offered) | 165 (87) | 13 (11 held already, 2 later; 13 / 0) | 152 / 0 / 0 | 8945 at 99.9c | +$31.26 | +$0.00 | +$31.26 | -$58.64 | FLAG: mostly winners |
| spike (confidence jumped in one second) | 8 (8) | 2 (0 held already, 2 later; 2 / 0) | 6 / 0 / 0 | 331 at 98.8c | +$3.64 | +$0.00 | +$3.64 | -$54.16 | FLAG: mostly winners |
| no_offer | 1262 (133) | 26 (25 held already, 1 later; 26 / 0) | 1235 / 1 / 0 | no price logged | - | - | - | - | nothing offered |
| book_stale | 94 (36) | 2 (2 held already, 0 later; 2 / 0) | 0 / 0 / 0 (+92 no side) | no price logged | - | - | - | - |  |
| early_once | 15 (14) | 15 (15 held already, 0 later; 15 / 0) | 0 / 0 / 0 | no price logged | - | - | - | - |  |
| market_attempts | 13 (13) | 1 (1 held already, 0 later; 1 / 0) | 0 / 0 / 0 (+12 no side) | no price logged | - | - | - | - |  |
| jump_against | 12 (11) | 2 (1 held already, 1 later; 2 / 0) | 10 / 0 / 0 | 363 at 99.5c | +$2.07 | +$0.00 | +$2.07 | -$35.99 | FLAG: mostly winners |
| against_thin | 10 (9) | 2 (2 held already, 0 later; 2 / 0) | 8 / 0 / 0 | 365 at 99.2c | +$3.00 | +$0.00 | +$3.00 | -$45.26 | FLAG: mostly winners |
| index_stale | 9 (1) | 0 (0 held already, 0 later; 0 / 0) | 0 / 0 / 0 (+9 no side) | no price logged | - | - | - | - |  |
| max_per_market | 7 (7) | 7 (7 held already, 0 later; 7 / 0) | 0 / 0 / 0 | no price logged | - | - | - | - |  |
| late_boost | 4 (4) | 2 (2 held already, 0 later; 2 / 0) | 2 / 0 / 0 | no price logged | - | - | - | - |  |
| dump_guard | 3 (3) | 1 (0 held already, 1 later; 1 / 0) | 1 / 1 / 0 | 31 at 83.0c | +$5.43 | -$0.84 | +$4.59 | -$12.83 |  |
| staged_none | 2 (2) | 2 (1 held already, 1 later; 2 / 0) | 0 / 0 / 0 | no price logged | - | - | - | - |  |
| close_budget | 2 (1) | 2 (2 held already, 0 later; 2 / 0) | 0 / 0 / 0 | no price logged | - | - | - | - |  |
| edge_cap | 1 (1) | 0 (0 held already, 0 later; 0 / 0) | 1 / 0 / 0 | 1 at 87.0c | +$0.12 | +$0.00 | +$0.12 | -$0.87 |  |

## What each gate's sample can show

- price ceiling (no buys over 97.8c): 0 losers in 212: only a loser rate of about 1 in 100 or more would likely have shown; the most it cost is about 1.9 loss(es) of a typical size here (-$28.99 each).
-   of which 97.9-98.0c (the 09-27 v-ceiling978 change): 0 losers in 14: only a loser rate of about 21 in 100 or more would likely have shown; the most it cost is about 0.3 loss(es) of a typical size here (-$37.97 each).
- seller gate (fresh offer while takers sell our side): 1 loser(s) in 9; the most it cost is about 0.2 loss(es) of a typical size here (-$27.37 each).
  - would have LOST: 09-27 6:59 PM ET KXBTCD-26SEP2719-T84199.99, YES at 92.0c, 24 s left, 1 contracts = -$0.93
- second full bet (one-full-bet / cheaper-offer band): every refused market was bought anyway (ours: 8 won, 0 lost); on 8 market(s) we already held, the refused EXTRA bet would have made at most +$23.49.
- 45-second leg floor (under 95c): 0 losers in 4: only a loser rate of about 75 in 100 or more would likely have shown; the most it cost is about 0.3 loss(es) of a typical size here (-$27.05 each).
- edge floor (model edge under 0.3c): 0 losers in 526: only a loser rate of about 1 in 100 or more would likely have shown; the most it cost is about 1.0 loss(es) of a typical size here (-$35.86 each).
- confidence (model not sure enough): 11 loser(s) in 170.
  - would have LOST: 09-27 2:29 AM ET KXDOGE15M-26SEP270230-30, YES at no price, 45 s left
  - would have LOST: 09-27 3:29 AM ET KXNEAR15M-26SEP270330-30, YES at no price, 45 s left
  - would have LOST: 09-27 4:29 AM ET KXHYPE15M-26SEP270430-30, YES at no price, 45 s left
  - would have LOST: 09-27 6:44 AM ET KXNEAR15M-26SEP270645-45, YES at no price, 45 s left
  - would have LOST: 09-27 6:59 AM ET KXBTC15M-26SEP270700-00, NO at no price, 45 s left
  - would have LOST: 09-27 12:59 PM ET KXSOL15M-26SEP271300-00, NO at no price, 45 s left
  - would have LOST: 09-27 6:59 PM ET KXBTCD-26SEP2719-T84199.99, YES at no price, 45 s left
  - would have LOST: 09-27 7:29 PM ET KXNEAR15M-26SEP271930-30, NO at no price, 45 s left
  - would have LOST: 09-28 12:59 AM ET KXDOGE15M-26SEP280100-00, YES at no price, 45 s left
  - would have LOST: 09-28 5:14 AM ET KXXRP15M-26SEP280515-15, NO at no price, 45 s left
  - would have LOST: 09-28 5:29 AM ET KXXRP15M-26SEP280530-30, NO at no price, 45 s left
- depth (too few contracts offered): 0 losers in 152: only a loser rate of about 2 in 100 or more would likely have shown; the most it cost is about 0.5 loss(es) of a typical size here (-$58.64 each).
- spike (confidence jumped in one second): 0 losers in 6: only a loser rate of about 50 in 100 or more would likely have shown; the most it cost is about 0.1 loss(es) of a typical size here (-$54.16 each).
- book_stale: no settled market to judge.
- early_once: every refused market was bought anyway (ours: 15 won, 0 lost).
- market_attempts: no settled market to judge.
- jump_against: 0 losers in 10: only a loser rate of about 30 in 100 or more would likely have shown; the most it cost is about 0.1 loss(es) of a typical size here (-$35.99 each).
- against_thin: 0 losers in 8: only a loser rate of about 38 in 100 or more would likely have shown; the most it cost is about 0.1 loss(es) of a typical size here (-$45.26 each).
- index_stale: no settled market to judge.
- max_per_market: every refused market was bought anyway (ours: 7 won, 0 lost).
- late_boost: 0 losers in 2: only a loser rate of about 100 in 100 or more would likely have shown.
- dump_guard: 1 loser(s) in 2; the most it cost is about 0.4 loss(es) of a typical size here (-$12.83 each).
  - would have LOST: 09-27 6:59 PM ET KXBTCD-26SEP2719-T84199.99, YES at 83.0c, 24 s left, 1 contracts = -$0.84
- staged_none: every refused market was bought anyway (ours: 2 won, 0 lost); on 2 market(s) we already held, the refused EXTRA bet would have made at most +$0.00.
- close_budget: every refused market was bought anyway (ours: 2 won, 0 lost).
- edge_cap: 0 losers in 1: only a loser rate of about 100 in 100 or more would likely have shown; the most it cost is about 0.1 loss(es) of a typical size here (-$0.87 each).

## Live losses in the window (Kalshi ledger)

- KXETH15M-26SEP270230-30: -$32.73, market settled YES. Our bet WON; the loss is the insurance we bought. Gates that refused this market in the window: confidence x1, dump_guard x1, edge_floor x1, price_ceiling x1.
  - our buy: 09-27 2:29 AM ET YES 88 @ 83.5c, 17 s left, sellers 79 in 100 of our side in 3 s, offer 92 ms old

## Orders we SENT that bought nothing

- 15-minute: 10 order(s), status 201, filled nothing
- KXBTCD hourly: 3 order(s), status 400, invalid_price

| ET | market | side | offer seen | contracts asked | why nothing | market result | most it could have made |
|---|---|---|---|---|---|---|---|
| 09-27 1:59 AM ET | KXXRP15M-26SEP270200-00 | YES | 97.8c | 15 | filled nothing | YES | +$0.31 |
| 09-27 2:59 AM ET | KXETH15M-26SEP270300-00 | NO | 98.0c | 86 | filled nothing | NO | +$1.60 |
| 09-27 4:29 AM ET | KXHYPE15M-26SEP270430-30 | NO | 97.8c | 88 | filled nothing | NO | +$1.80 |
| 09-27 8:44 AM ET | KXNEAR15M-26SEP270845-45 | NO | 97.5c | 29 | filled nothing | NO | +$0.68 |
| 09-27 12:29 PM ET | KXHYPE15M-26SEP271230-30 | NO | 97.6c | 8 | filled nothing | NO | +$0.19 |
| 09-27 2:59 PM ET | KXBNB15M-26SEP271500-00 | NO | 97.6c | 30 | filled nothing | NO | +$0.66 |
| 09-27 4:44 PM ET | KXXRP15M-26SEP271645-45 | YES | 97.6c | 7 | filled nothing | YES | +$0.16 |
| 09-27 9:59 PM ET | KXBTCD-26SEP2722-T83699.99 | YES | 97.0c | 1 | invalid_price | YES | +$0.03 |
| 09-27 10:59 PM ET | KXBTCD-26SEP2723-T83399.99 | NO | 91.0c | 1 | invalid_price | NO | +$0.08 |
| 09-27 10:59 PM ET | KXBTCD-26SEP2723-T83399.99 | NO | 93.0c | 1 | invalid_price | NO | +$0.07 |
| 09-28 12:59 AM ET | KXDOGE15M-26SEP280100-00 | NO | 97.1c | 1 | filled nothing | NO | +$0.03 |
| 09-28 5:14 AM ET | KXXRP15M-26SEP280515-15 | YES | 97.5c | 10 | filled nothing | YES | +$0.23 |
| 09-28 9:14 AM ET | KXNEAR15M-26SEP280915-15 | YES | 96.7c | 21 | filled nothing | YES | +$0.65 |

Total, if every one had filled at the offer seen: +$6.49 (upper bound).
