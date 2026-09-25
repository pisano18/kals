# Money projection -- the next 60 days, from our own record

Written 2026-09-25, about 3:35 AM ET. Start: bank **$1,044.69** (Kalshi, read 3:25 AM ET), bet size 88.
Day 1 is Saturday 09-26; day 60 is Tuesday 11-24. **This is our past replayed forward, not a promise.**

## The answer

Built from the last 7 full days of real trading (09-18 to 09-24: 393 markets on 272 closes, money from Kalshi's own books), replayed 5,000 times over:

| | day 7 (Fri 10-02) | day 14 (Fri 10-09) | day 30 (Sun 10-25) | day 60 (Tue 11-24) |
|---|---:|---:|---:|---:|
| middle outcome (half do better) | $1,164 | $1,327 | $1,800 | **$2,924** |
| bad luck (1 in 10 do worse) | $804 | $789 | $840 | $1,133 |
| good luck (1 in 10 do better) | $1,640 | $2,081 | $3,149 | $5,163 |
| bet size, middle path (contracts) | 97 | 111 | 151 | 246 |

- **Money per day: about $21 a day now, about $40 a day by day 60** (average over all paths). A typical day makes $60 now, but about 1 day in 7 loses ~$200, and that one day eats most of a week.
- **Chance of ending 60 days below today's $1,045: 9 in 100.**
- **Chance the 20%-drawdown stop fires at least once: 97 in 100** (55 in 100 by day 7). Why so high: the record holds one -$223 day (09-19) in 7, and at today's size a day like that is a -$200 day, which is 20% of the bank on its own. Take that day out and the chance is 19 in 100.
- **Worst days get bigger as the bet grows.** The 1-in-20 worst day is -$208 now and -$380 by day 60: the $200 daily stop only stops the day AFTER the close that crosses it, and one close at size 246 can lose $365 (our worst close ever, -$130.41 at size 88, scaled).
- **Where more money stops helping.** The book already runs short at today's size: we get about 74 of every 100 contracts we ask for on the main bet, about 62 of 100 at size 250. Each extra contract of size earns 2.2c on a winning market from size 88 to 127 and 1.8c from 212 to 250, against 2.6c on average today, while a losing market loses the full amount at every size. The code stops raising the size at a bank of **$2,940** (250 contracts); the middle path gets there around day 60.

## The same question under other assumptions

| scenario | day 60 middle | 1 in 10 worse | 1 in 10 better | ends below $1,045 | 20% stop fires | $/day now -> day 60 |
|---|---:|---:|---:|---:|---:|---:|
| **Last 7 days (the answer above)** | $2,924 | $1,133 | $5,163 | 9 in 100 | 97 in 100 | $21 -> $40 |
| All 12 days (09-13..09-24) | $8,409 | $6,042 | $10,617 | 0 in 100 | 53 in 100 | $60 -> $139 |
| All 12 days, weekends from weekends only | $8,247 | $5,854 | $10,563 | 0 in 100 | 68 in 100 | $42 -> $138 |
| Last 7 days without the 09-19 bug day | $7,197 | $5,501 | $8,889 | 0 in 100 | 19 in 100 | $57 -> $114 |
| Last 7 days, cheap offers halve again | $1,946 | $750 | $3,562 | 19 in 100 | 99 in 100 | $12 -> $18 |
| Last 7 days + a planted disaster | $837 | $293 | $2,567 | 59 in 100 | 100 in 100 | -$2 -> $0 |

- **All 12 days is too rosy.** 09-13 to 09-15 were traded at size 50-70 when cheap offers were twice as plentiful (they fell by about half from 09-16). Replayed at size 88 those days look like $130-190 days that the market no longer offers. That is why the answer uses the last 7.
- **The planted disaster** is our worst close ever (-$130.41 at size 88) doubled -- close to the most one close can lose (3 bets x 98c x size) -- happening once in every 450 closes, as often as the real worst one did. **That alone turns the 60 days into a loss more often than not (59 in 100 end below today).** The whole profit rests on the worst close not getting twice as bad or twice as common.
- **Cheap offers halving again** keeps it positive but cuts day 60 from $2,924 to $1,946.

## Taking money out every week

Every 7th day, anything above the line is withdrawn. 'Total' = money taken out + bank on day 60.

| rule | total, middle | total, 1 in 10 worse | total, 1 in 20 worse | taken out, middle | 20% stop fires |
|---|---:|---:|---:|---:|---:|
| never withdraw | $2,924 | $1,133 | $802 | $0 | 97 in 100 |
| keep $2,500 | $3,030 | $1,133 | $802 | $499 | 98 in 100 |
| keep $1,500 | $2,780 | $1,135 | $815 | $1,269 | 99 in 100 |
| keep $1,000 | $2,177 | $1,105 | $853 | $1,228 | 100 in 100 |

- **Withdrawing does NOT make the 20% stop rarer -- it makes it slightly more common**, because the $200 daily stop is a bigger share of a smaller bank. What it does is bank the gains: keeping $1,500 takes about $1,270 home over 60 days in the middle case and gives up about $144 of middle-case growth.
- **Keeping $2,500 costs nothing** ($3,030 vs $2,924): above ~$2,500 the extra size buys dearer, thinner offers while every losing market still loses the full size.
- Any withdrawal must be followed by START on the app so the bot's high mark moves down with it (it can mistake a withdrawal for a loss).

## Day by day (the answer above: last 7 days replayed, 5,000 paths)

'Worst 1-in-20 day' = the day's loss that 1 path in 20 does worse than, at that day's size. 'Made so far' = middle bank minus $1,045. Dates are ET.

| day | date | middle bank | 1 in 10 worse | 1 in 10 better | bet size (middle) | middle day's money | worst 1-in-20 day | made so far (middle) | 20% stop fired by now |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Sat 09-26 | $1,105 | $837 | $1,178 | 88 | $60 | -$208 | $60 | 14 in 100 |
| 2 | Sun 09-27 | $1,100 | $837 | $1,289 | 93 | $0 | -$230 | $55 | 27 in 100 |
| 3 | Mon 09-28 | $1,115 | $877 | $1,366 | 93 | $0 | -$213 | $70 | 34 in 100 |
| 4 | Tue 09-29 | $1,113 | $873 | $1,438 | 94 | $51 | -$213 | $68 | 40 in 100 |
| 5 | Wed 09-30 | $1,130 | $830 | $1,496 | 94 | $55 | -$207 | $85 | 46 in 100 |
| 6 | Thu 10-01 | $1,147 | $804 | $1,565 | 96 | $52 | -$213 | $102 | 51 in 100 |
| 7 | Fri 10-02 | $1,164 | $804 | $1,640 | 97 | $45 | -$215 | $120 | 55 in 100 |
| 8 | Sat 10-03 | $1,192 | $806 | $1,696 | 99 | $48 | -$213 | $147 | 58 in 100 |
| 9 | Sun 10-04 | $1,215 | $800 | $1,764 | 101 | $53 | -$215 | $170 | 62 in 100 |
| 10 | Mon 10-05 | $1,246 | $789 | $1,817 | 103 | $53 | -$217 | $202 | 65 in 100 |
| 11 | Tue 10-06 | $1,261 | $789 | $1,875 | 105 | $54 | -$218 | $216 | 67 in 100 |
| 12 | Wed 10-07 | $1,286 | $789 | $1,956 | 107 | $57 | -$221 | $242 | 69 in 100 |
| 13 | Thu 10-08 | $1,306 | $784 | $2,004 | 109 | $53 | -$224 | $261 | 72 in 100 |
| 14 | Fri 10-09 | $1,327 | $789 | $2,081 | 111 | $49 | -$226 | $282 | 74 in 100 |
| 15 | Sat 10-10 | $1,357 | $791 | $2,141 | 112 | $59 | -$226 | $313 | 76 in 100 |
| 16 | Sun 10-11 | $1,380 | $791 | $2,204 | 115 | $55 | -$230 | $336 | 77 in 100 |
| 17 | Mon 10-12 | $1,408 | $792 | $2,285 | 117 | $55 | -$228 | $364 | 79 in 100 |
| 18 | Tue 10-13 | $1,445 | $799 | $2,328 | 119 | $56 | -$230 | $400 | 80 in 100 |
| 19 | Wed 10-14 | $1,479 | $801 | $2,419 | 122 | $55 | -$234 | $434 | 81 in 100 |
| 20 | Thu 10-15 | $1,505 | $801 | $2,468 | 125 | $59 | -$232 | $460 | 82 in 100 |
| 21 | Fri 10-16 | $1,534 | $810 | $2,536 | 127 | $56 | -$233 | $489 | 84 in 100 |
| 22 | Sat 10-17 | $1,564 | $814 | $2,618 | 130 | $57 | -$241 | $520 | 85 in 100 |
| 23 | Sun 10-18 | $1,589 | $813 | $2,689 | 133 | $56 | -$238 | $544 | 86 in 100 |
| 24 | Mon 10-19 | $1,624 | $813 | $2,743 | 135 | $56 | -$246 | $579 | 86 in 100 |
| 25 | Tue 10-20 | $1,655 | $822 | $2,819 | 138 | $56 | -$254 | $610 | 87 in 100 |
| 26 | Wed 10-21 | $1,682 | $825 | $2,882 | 140 | $58 | -$255 | $637 | 88 in 100 |
| 27 | Thu 10-22 | $1,722 | $828 | $2,950 | 142 | $57 | -$252 | $678 | 89 in 100 |
| 28 | Fri 10-23 | $1,744 | $830 | $3,027 | 146 | $56 | -$262 | $699 | 90 in 100 |
| 29 | Sat 10-24 | $1,779 | $834 | $3,095 | 148 | $56 | -$262 | $735 | 90 in 100 |
| 30 | Sun 10-25 | $1,800 | $840 | $3,149 | 151 | $62 | -$259 | $755 | 91 in 100 |
| 31 | Mon 10-26 | $1,827 | $845 | $3,228 | 153 | $58 | -$263 | $783 | 92 in 100 |
| 32 | Tue 10-27 | $1,866 | $851 | $3,321 | 155 | $61 | -$273 | $821 | 92 in 100 |
| 33 | Wed 10-28 | $1,901 | $864 | $3,381 | 158 | $61 | -$272 | $857 | 92 in 100 |
| 34 | Thu 10-29 | $1,935 | $870 | $3,429 | 161 | $62 | -$289 | $890 | 93 in 100 |
| 35 | Fri 10-30 | $1,976 | $888 | $3,520 | 164 | $68 | -$291 | $932 | 93 in 100 |
| 36 | Sat 10-31 | $2,009 | $898 | $3,567 | 168 | $71 | -$297 | $964 | 93 in 100 |
| 37 | Sun 11-01 | $2,052 | $898 | $3,638 | 170 | $62 | -$307 | $1,007 | 94 in 100 |
| 38 | Mon 11-02 | $2,098 | $900 | $3,728 | 174 | $74 | -$305 | $1,053 | 94 in 100 |
| 39 | Tue 11-03 | $2,123 | $902 | $3,811 | 178 | $71 | -$298 | $1,079 | 94 in 100 |
| 40 | Wed 11-04 | $2,165 | $911 | $3,831 | 180 | $72 | -$327 | $1,120 | 94 in 100 |
| 41 | Thu 11-05 | $2,198 | $926 | $3,910 | 184 | $73 | -$330 | $1,153 | 94 in 100 |
| 42 | Fri 11-06 | $2,232 | $934 | $3,985 | 186 | $69 | -$318 | $1,187 | 95 in 100 |
| 43 | Sat 11-07 | $2,262 | $956 | $4,052 | 189 | $72 | -$332 | $1,217 | 95 in 100 |
| 44 | Sun 11-08 | $2,310 | $963 | $4,132 | 192 | $72 | -$345 | $1,265 | 95 in 100 |
| 45 | Mon 11-09 | $2,353 | $973 | $4,221 | 196 | $71 | -$371 | $1,308 | 95 in 100 |
| 46 | Tue 11-10 | $2,377 | $983 | $4,268 | 200 | $70 | -$360 | $1,332 | 95 in 100 |
| 47 | Wed 11-11 | $2,416 | $1,003 | $4,353 | 202 | $65 | -$352 | $1,372 | 95 in 100 |
| 48 | Thu 11-12 | $2,451 | $1,011 | $4,383 | 205 | $73 | -$366 | $1,407 | 95 in 100 |
| 49 | Fri 11-13 | $2,495 | $1,011 | $4,450 | 208 | $71 | -$372 | $1,450 | 96 in 100 |
| 50 | Sat 11-14 | $2,540 | $1,022 | $4,501 | 212 | $72 | -$374 | $1,496 | 96 in 100 |
| 51 | Sun 11-15 | $2,569 | $1,033 | $4,534 | 216 | $66 | -$380 | $1,524 | 96 in 100 |
| 52 | Mon 11-16 | $2,616 | $1,047 | $4,621 | 218 | $63 | -$377 | $1,571 | 96 in 100 |
| 53 | Tue 11-17 | $2,651 | $1,053 | $4,701 | 222 | $75 | -$380 | $1,607 | 96 in 100 |
| 54 | Wed 11-18 | $2,677 | $1,062 | $4,742 | 225 | $75 | -$380 | $1,632 | 96 in 100 |
| 55 | Thu 11-19 | $2,717 | $1,076 | $4,805 | 227 | $80 | -$380 | $1,673 | 96 in 100 |
| 56 | Fri 11-20 | $2,753 | $1,075 | $4,884 | 231 | $83 | -$380 | $1,708 | 96 in 100 |
| 57 | Sat 11-21 | $2,811 | $1,095 | $4,935 | 234 | $78 | -$380 | $1,766 | 96 in 100 |
| 58 | Sun 11-22 | $2,850 | $1,114 | $5,011 | 239 | $93 | -$380 | $1,806 | 96 in 100 |
| 59 | Mon 11-23 | $2,902 | $1,135 | $5,103 | 242 | $83 | -$380 | $1,858 | 96 in 100 |
| 60 | Tue 11-24 | $2,924 | $1,133 | $5,163 | 246 | $81 | -$380 | $1,880 | 97 in 100 |

## How it was built (short)

- **Money:** Kalshi's ledger, one row per market with a hedge netted in (`results/kalshi_ledger.json`, refreshed 3:03 AM ET 09-25), 15-minute crypto only. Coin race (+$2.25 over 147 markets, ever) and hourly BTC at 1 contract (+$0.02) are left out; they do not move this chart.
- **Bet size at each market:** the live logs' own resize records. Each market's dollars were re-scaled from the size it was traded at to the size the simulated bank allows, re-sized before every close exactly as the bot does (bank / 11.76, 1 to 250).
- **Book depth and price:** the order book the live bot saw at the moment of its main bet, on 183 markets since 09-18 (logged by the bot itself, not the tape). A winning market pays 1 - price - fee on each contract, cheapest first, until the book under 98c runs out. A losing market loses the whole size: 12 of our 17 losing markets filled all of it or more.
- **Rules applied:** the -$200 daily stop (fixed dollars, never grows), the 20% drawdown stop (assumed: rest of that day and the next day off, then START re-bases it), the 250 cap. Everything inside a close -- the 45-second leg, late boost, extra coin, hedges, the two-loss pause -- is already inside each market's dollars.
- **Whole ET days are replayed**, so a bad day's losses stay together.
- **Checks:** a self-test plants worlds with a known answer (capacity: 600 closes above the book's limit add exactly 600 x the limit's profit; a no-edge world never moves; the $200 stop cuts a day at exactly -$250 in a planted case; the 20% stop pauses and resumes). Day 1 by hand: each of the 7 days replayed at $1,044.69 gives +$100.01, -$208.06, +$133.00, -$4.75, +$60.35, -$45.26, +$103.78 -> average **$19.87**; the 5,000-path simulation says $20.91 (within its own noise).

## What would make this wrong

- **7 days is a small sample**, and the rules changed several times inside it (09-19's losses came from gates since fixed; new ones can break the same way). The spread in the table is the luck of the draw, not the uncertainty of the record itself -- the real range is wider.
- **The book may thin faster than modelled.** The depth comes from one snapshot at the main bet. Our own fills fell faster as size rose (91 of 100 contracts at size 40-59, 69 of 100 at 80-99), though cheap offers were halving over the same days, so the two cannot be separated yet. If it is size, the top half of this chart is too high.
- **Nothing new is in it:** no deposits, no new markets, no hourly BTC at size, no strategy changes.

Script: `research/moneyproj.py` (self-test runs first). Per-day series for a chart: `results/projection_2026-09-25.json`.
