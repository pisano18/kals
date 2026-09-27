# LEAD 1 -- rounding-decided markets (read-only, 2026-09-27)

Script: `rounding.py` (self-test 16/16 PASS incl. planted flip, planted 70% YES rate, empty world, far-from-strike world).
Data: clean-room digest (markets.jsonl exact decimal means, index/, trades/), `results/kalshi_ledger.json`, `results/pinrun-live-*.jsonl`.
Check: rounded exact mean vs Kalshi's result = 0 mismatches on all 25,803 up/down markets with a full window
(DOGE strike = previous market's settlement value, which also clears the digest's one exception).

## Answer first
- Our live bot has compared against the ROUNDED threshold since its first live day (`pinrun.eff_strike`, commit c661d34, 2026-09-08).
  The clean room's "false belief" was its own simulators', not ours.
- 24 flips in the whole tape (08-25..09-27), not 18 (18 are the clean room's train window). About 1 in 1,075 markets, ~0.75 a day.
- Since live (09-08) there were 13; we held 5, all on the YES (rounding) side, all won: +$31.60 (ledger).
- Of the 56 markets whose final average landed within half a rounding unit of the strike, we held 13 -- every one YES, every one won, +$45.69. We never held the losing side of a rounding-decided market.
- A "bet the rounding side" rule is not a new edge: at 10-30 s out the projection is too noisy for half a unit to matter; by 1-2 s it is knowable but the price is already 97-98c. n = 22-29 markets per cell -> too few to act on.

## (a) The 24 flips (raw mean < strike, rounded mean = strike -> YES)

| close ET | coin | raw 60-s mean | rounded | strike | result | raw vs strike (half-units) | we held |
|---|---|---|---|---|---|---|---|
| 08-25 12:30 | BNB | 698.1462167 | 698.15 | 698.15 | YES | -0.76 | pre-live |
| 08-26 00:00 | BNB | 696.1351 | 696.14 | 696.14 | YES | -0.98 | pre-live |
| 08-28 21:00 | XRP | 1.3832837 | 1.3833 | 1.3833 | YES | -0.33 | pre-live |
| 08-28 21:45 | XRP | 1.3824555 | 1.3825 | 1.3825 | YES | -0.89 | pre-live |
| 08-30 04:30 | BNB | 693.4983167 | 693.50 | 693.50 | YES | -0.34 | pre-live |
| 08-30 06:00 | NEAR | 1.8776967 | 1.8777 | 1.8777 | YES | -0.07 | pre-live |
| 08-31 01:45 | XRP | 1.3648593 | 1.3649 | 1.3649 | YES | -0.81 | pre-live |
| 08-31 22:30 | NEAR | 1.9279917 | 1.9280 | 1.9280 | YES | -0.17 | pre-live |
| 09-05 01:00 | XRP | 1.398494 | 1.3985 | 1.3985 | YES | -0.12 | pre-live |
| 09-07 14:00 | XRP | 1.3979877 | 1.3980 | 1.3980 | YES | -0.25 | pre-live |
| 09-07 17:45 | ETH | 2492.8158333 | 2492.82 | 2492.82 | YES | -0.83 | pre-live |
| 09-08 10:30 | BNB | 749.95985 | 749.96 | 749.96 | YES | -0.03 | no (watched, no signal) |
| 09-08 22:15 | XRP | 1.4168548 | 1.4169 | 1.4169 | YES | -0.90 | no |
| 09-09 04:15 | XRP | 1.4409952 | 1.4410 | 1.4410 | YES | -0.10 | YES 20 @ 91.5c, 11 s out, +$1.59 |
| 09-09 22:30 | BNB | 721.3252667 | 721.33 | 721.33 | YES | -0.95 | YES 20 @ 64c, 7 s out, +$6.88 |
| 09-10 00:15 | XRP | 1.3902573 | 1.3903 | 1.3903 | YES | -0.85 | YES 20 @ 80c, 4 s out, +$3.78 |
| 09-11 22:15 | XRP | 1.360885 | 1.3609 | 1.3609 | YES | -0.30 | no |
| 09-14 11:15 | BNB | 721.7668 | 721.77 | 721.77 | YES | -0.64 | no (model said 38% at 30 s) |
| 09-20 02:15 | XRP | 1.3819517 | 1.3820 | 1.3820 | YES | -0.97 | no (model said 40% at 45 s) |
| 09-20 03:30 | XRP | 1.3834865 | 1.3835 | 1.3835 | YES | -0.27 | no (model 99.8% at 8 s; price 97.9-98.4c refused) |
| 09-24 15:15 | ETH | 2690.3975 | 2690.40 | 2690.40 | YES | -0.50 | YES 83 @ 97.1c, 27 s out, +$2.24 |
| 09-24 17:00 | XRP | 1.5305748 | 1.5306 | 1.5306 | YES | -0.50 | YES 124.5 @ 85.4c, 3 s out, +$17.11 |
| 09-25 15:45 | BNB | 775.1286667 | 775.13 | 775.13 | YES | -0.27 | no |
| 09-26 10:30 | NEAR | 4.8374917 | 4.8375 | 4.8375 | YES | -0.17 | no (model 28% at 45 s) |

(Close times are ET, EDT = UTC-4, matching the ticker names.)
Coins: XRP 12, BNB 7, NEAR 3, ETH 2; zero BTC/SOL/DOGE/HYPE/ZEC -- half a unit is largest relative to price for XRP/NEAR/BNB.
None of the 24 sat exactly ON a half-unit tie, so our float arithmetic in `eff_strike` never mattered here.

## (c) Was the rounding side knowable, and what did the tape print? (all 24; YES rate by projection band)

Band = where the "index stays where it is" projection sat: Z = within half a unit BELOW the strike (rounds up -> YES);
BELOW = 1-3 half-units under; AT = at/above within half a unit. Tape price = what a YES buyer paid in the next 3 s. n = markets (one per close).

| seconds left | Z: YES / n | BELOW: YES / n | AT: YES / n | Z median YES price |
|---|---|---|---|---|
| 30 | 16/22 (73%) | 29/50 (58%) | 18/26 (69%) | 60c |
| 20 | 19/28 (68%) | 13/33 (39%) | 24/31 (77%) | 61c |
| 10 | 18/29 (62%) | 11/40 (28%) | 30/31 (97%) | 66c |
| 5 | 23/27 (85%) | 1/34 (3%) | 33/33 (100%) | 87c |
| 2 | 23/25 (92%) | 0/38 | 34/34 | 97c |
| 1 | 24/24 (100%) | 0/38 | 32/32 | 98c |

Read: at 30 s the band says nothing (Z no better than BELOW); from ~5 s the rounding side is mostly settled, and the market
already prices it (87c at 5 s, 97-98c at 1-2 s). Of the 24 flips, the projection sat in Z at 30 s in 5 (Z or AT: 9), at 20 s in 8 (14), at 10 s in 13 (19), at 5 s in 18 (22), at 2 s in 23 (24), at 1 s in 24.
Tape in the last 30 s of the flips: YES traded anywhere from 2c to 99.9c; volume-weighted 51-97c. Money that sat on the NO side
in the last 10 s of the 18 train flips: $64,000 (of it $42,000 in one ETH market, 09-07); this is stake that went to zero,
not a "gift" figure -- whoever bought YES from them paid 51-99c for it.

## (d) Rule "projection in Z -> buy YES", TAPE POPULATION (not our loss rate; no fill modelling)

MDE first: ~25 markets per cell -> a YES rate is only distinguishable from 50% if it is ~27 points away, and money per contract
only if it is ~19c (sd ~0.35, 80% power). Every money figure below is inside that.

| seconds left | n markets (closes) | YES rate | median price | tape c/contract after fee | at 100 contracts, 32 days | halves 09-09..17 / 09-18..27 (c/contract, n) |
|---|---|---|---|---|---|---|
| 10 | 29 (29) | 62% | 66c | -5.4c | -$156 | -12.8c (10) / +2.3c (6) |
| 5 | 27 (26) | 85% | 87c | +4.9c | +$128 | +7.6c (5) / +7.2c (6) |
| 2 | 25 (25) | 92% | 97c | +1.3c | +$30 | +2.6c (6) / +0.1c (7) |
| 1 | 24 (24) | 100% | 98c | +3.3c | +$76 | +2.4c (6) / +1.8c (6) |

Markets per day in Z at 5 s: 27 over ~32 tape days = under 1 a day (0.8), across all nine coins.
The 5 s row's +$128 is 27 markets at 100 contracts assuming every printed price was ours -- the population trap applies in full.

## Verdict
Too few to act on: 24 flips in 32 days, ~1 rule market a day, and every money cell is within its MDE. The one piece of it
that is real -- compare against strike minus half a unit -- the live bot already does and was paid for 5 times (+$31.60).
No live change proposed. $0 check still worth doing (from the clean room): an exact-decimal tie in `eff_strike` -- 0 of 24
flips sat on a tie, so it has cost nothing to date.
