# STREAKS -- do the chances come in bunches?

`research/pinstreak.py`, 635 closes, 304 of them bought on (47.9%).

## Do they clump?

| | |
|---|---|
| hours on record | 166 |
| busiest hour | 4 buys |
| hours with none | 19 (11%) |
| clumping, ours | **0.64** |
| clumping, a coin-flip world at our rate | 0.52 |
| p against a coin-flip world | 0.010 |

**They clump, mildly.** Our hours vary more than a coin flip at the same rate would: 0.64 against 0.52, p 0.010. The comparison is with that simulated world, not the textbook 1.0 -- with only four closes in an hour a random world already sits near 0.52.

## Does a dry spell predict another?

| situation | chance the next close buys | moments |
|---|---|---|
| right after a buy | 51% | 303 |
| after 1 dry closes (15m) | 45% | 331 |
| after 2 dry closes (30m) | 40% | 181 |
| after 4 dry closes (1h) | 32% | 65 |
| after 8 dry closes (2h) | 25% | 20 |
| the plain average | 48% | 635 |

## How long is a normal dry spell?

| dry spell | closes | in hours |
|---|---|---|
| typical (half are shorter) | 0 | 0.0 h |
| 9 in 10 are shorter | 3 | 0.8 h |
| 19 in 20 are shorter | 4 | 1.0 h |
| 99 in 100 are shorter | 9 | 2.2 h |
| the longest we have seen | 15 | 3.8 h |

So a silence past **1.0 hours** is longer than 19 in 20 normal ones -- past that, check the bot before blaming the market.

**Right now:** 0.0 hours since the last buy (0 closes). 303 of the 303 dry spells on record were at least this long (100%).

## Buys per day

| day (ET) | buys |
|---|---|
| 2026-09-08 | 27 |
| 2026-09-09 | 29 |
| 2026-09-10 | 41 |
| 2026-09-11 | 36 |
| 2026-09-12 | 69 |
| 2026-09-13 | 34 |
| 2026-09-14 | 46 |
| 2026-09-15 | 22 |
