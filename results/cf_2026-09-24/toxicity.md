# Was our side being sold right before we bought it? (toxicity at entry)

Read-only measurement, 2026-09-24 03:00Z, from the recorded `trade` channel
(`C:\kals\kalshi_data\trade`) and the raw settlement-index feed
(`cfbenchmarks_value`), over the 825 markets the live bot entered
2026-09-08 .. 2026-09-24 (`rebuild_spike.jsonl`). Nothing here comes from the
replay. Scripts: scratchpad `tox_scan.py` (tape scan, 172 s), `tox_analyze.py`,
`tox_check.py`, `tox_index.py`.

## The answer

**Yes, there is a real selling signature, but only in the last 3 seconds
before our order, and it is a marker of the losers more than a predictor.**

- In the 3 s before we bought, takers had SOLD more of our side than they
  bought in **17 of 25 losers** (68%) but in only **245 of 746 winners** (33%).
  That is a 4x higher loss rate when the flag is on: 17 of 262 flagged entries
  lost (6.5%) vs 8 of 531 unflagged (1.5%). Odds this is chance: about 4 in
  10,000 (rank-sum p = 0.0004; 24 cells were looked at, so the bar was 0.002
  and this clears it).
- It is direction, not activity: the number of trades in those 3 s is the
  same for losers and winners (median 59 vs 56, p = 0.99). Only the side the
  takers were on differs.
- At 10 s the signal is weak (p = 0.04) and at 30 s it is gone (p = 0.72).
- **Money, in-sample:** the flagged third of our entries lost **$571.51** and
  won **$481.78**, net **-$89.73** over 16 days; the unflagged two-thirds made
  **+$670.97** net. Skipping every flagged entry would have added about $90
  over 16 days (about $6/day) while giving up a third of all entries.
  **Fragile:** the two biggest flagged losers (KXBTC15M-26SEP191600-00
  -$107.95 and KXBTC15M-26SEP190200-00 -$66.34) are $174.29 of that; without
  them the flagged bucket is net **+$84.56** and skipping would have COST money.
- The flag does not foresee much on its own: among WINNERS, a flagged entry
  saw the index move against us over the next 10 s 53% of the time vs 49%
  unflagged (p = 0.16). Losers get hit by an 11-sigma move in 10 s whether
  flagged or not. So the crowd's last-3-second selling is weakly informed, and
  93.5% of flagged entries still win.

**What it would justify:** not a skip rule yet -- the count is solid, the
dollars are not, and skipping 33% of entries for $6/day is a bad trade if the
two big losers were luck. What it does justify is (1) logging the last-3-s
taker flow at every live entry with no behaviour change, against a
pre-registered bar (below), and (2) testing a DELAY rather than a skip: hold a
flagged order 3-5 s and re-evaluate. Among winners the index barely moves after
a flag (so the entry would still fire); among losers it moves -8 sigma in 5 s
(median), which would collapse the fair and stop the entry. The delay cannot be
priced from the tape (the counterfactual fill is not in it).

**Implementation cost:** `pinrun.py` subscribes to `orderbook_delta` only, not
`trade` (grep: no taker_side anywhere). A rule needs a `trade` subscription
(the collector already holds one) or an aggressor inferred from which side of
the book got hit.

## Data quality and the checks that ran (two failed)

- **Unit:** `yes_price_dollars` sampled on 1,488,549 lines across every hour
  file: min 0.001, max 0.999, values above 1: none. Dollars, decided from the
  whole sample. `yes + no = 1` on all 6,126,291 kept trades.
- **Side convention:** `taker_side` is present on every trade. It pairs exactly
  with `taker_book_side` (yes<->bid 3,115,708; no<->ask 3,010,583; no other
  combination), and with price direction: when the print moved up the taker
  was on YES 73.7% of the time (1,004,296 of 1,362,791); when it moved down the
  taker was on NO 88.8% (803,002 of 904,298). So `taker_side` = the outcome the
  taker BOUGHT; a taker on NO is selling YES.
- **Our own fills as the third check:** the bot is an IOC taker, so its fill must
  print as `taker_side == want` at our price just after `t_send`. It did in
  **770 of 772** covered markets that had any print in the 2 s after `t_send`
  (median +26 ms after `t_send`, min -169 ms, max +211 ms). Clocks agree to
  0.2 s, and any leak of our fill into the pre-window would count as BUYING of
  our side, i.e. push the losers' number the wrong way. Not the artefact.
- **Named sanity market KXBTC15M-26SEP232030-30 (YES at 87c, 00:29:34Z
  2026-09-24, -$130.41): FAILED -- no tape.** Hour file `20260924T00` does
  not exist; the trade recorder was down ~19:00Z 2026-09-23 to 01:01Z
  2026-09-24 (`20260923T16,T18,T20-T23`, `20260924T00` missing; `T15,T17,T19`
  are 1-15 KB stubs). The convention was checked on the 770 fills instead.
- **Big winner KXHYPE15M-26SEP172330-30** (NO at 92c, +$16.41): our fill printed
  on our side at 0.916 in the 2 s after `t_send`; 30 s before, takers bought
  5,745 of our side / sold 7,299; 30 s after, bought 9,213 / sold 4,329.
  Reads correctly.
- **Coverage:** 328 hour files needed; 9 missing, 4 truncated (kept what was
  read: `20260909T13` 76,606 lines, `20260915T13` 89,383, `20260915T20`
  42,604, `20260923T19` 15). **793 of 825 markets covered**; 32 uncovered, of
  which **2 losers ($142.55: the -$130.41 above and KXDOGE -$12.14)**. All
  numbers below are on the 793.
- **Positive control (the estimator can see selling when it is there):** on the
  same markets 2-32 s AFTER our fill, losers show sell share 0.545 vs winners
  0.431 (p = 0.010) and our-side price trend -53.9c vs +1.9c (p < 0.0001).
  A null before entry is therefore a real null, not a blind estimator.

## Losers vs winners, 793 covered markets (582 closes)

Losers: 25 markets, 24 closes, -$752.76. Winners: 768 markets, +$1,334.00.
"Sell share" = contracts of our side sold by takers / all taker contracts in
the window; 0.5 means as much sold as bought.

| window before order | metric | losers median | winners median | losers mean | winners mean | p |
|---|---|---|---|---|---|---|
| 3 s | sell share | **0.665** | **0.350** | 0.59 | 0.37 | **0.0004** |
| 3 s | net sold - bought, contracts | **+165** | **-133** | +3,470 | -31 | **0.0003** |
| 3 s | sold our side, contracts | 699 | 293 | 5,764 | 3,645 | 0.12 |
| 3 s | bought our side, contracts | 333 | 533 | 2,294 | 3,677 | 0.31 |
| 3 s | trades in window | 59 | 55.5 | 138 | 137 | 0.99 |
| 3 s | our-side price trend | 0.0c | +1.5c | -5.1c | +3.9c | 0.009 |
| 10 s | sell share | 0.47 | 0.38 | 0.49 | 0.39 | 0.04 |
| 10 s | net sold - bought | -176 | -404 | +3,010 | +179 | 0.18 |
| 10 s | our-side price trend | +1.1c | +7.8c | +3.9c | +14.9c | 0.006 |
| 30 s | sell share | 0.41 | 0.44 | 0.44 | 0.43 | 0.72 |
| 30 s | net sold - bought | -892 | -615 | -1,606 | +1,804 | 0.63 |
| 30 s | sold, dollars | $2,156 | $2,309 | $19,776 | $20,333 | 0.97 |
| 30 s | our-side price trend | +7.3c | +26.8c | +12.3c | +31.2c | 0.002 |
| last print | last price of our side minus what we paid | -0.1c | -0.1c | -1.1c | -1.9c | 0.68 |

The 10 s / 30 s price-trend rows are NOT a selling signal: the losers' side was
already at 82c 30 s before entry (winners' 68c) and we paid less (94c vs 97c,
p = 0.0005). That is the already-known "market disagrees with the model" loss
pattern, restated; it is separate from the 3 s flow.

## Split by time left at entry

| band | markets | losers | $ lost | losers flagged (3 s sell share > 0.5) | winners flagged | p | net $ if flagged skipped |
|---|---|---|---|---|---|---|---|
| 21-45 s | 566 | 20 | -$693.94 | **14 of 20** | 176 of 546 (32%) | 0.0008 | **+$215.56** (avoid $534.03, give up $318.47) |
| <= 20 s | 227 | 5 | -$58.82 | 3 of 5 | 69 of 222 (31%) | 0.18 | **-$125.83** (avoid $37.47, give up $163.31) |

The signal lives where the money is lost (21-45 s). Under 20 s the flag
costs money; five losers is too few to say more than that.

## Would a rule have paid? (in-sample, tuned on 25 losers -- optimistic)

| rule (3 s window) | flagged | losers caught | $ loss avoided | $ wins given up | net | p |
|---|---|---|---|---|---|---|
| sell share > 0.5 (pre-registered cut) | 262 (33%) | 17 of 25 | $571.51 | $481.78 | **+$89.73** | 0.0003 |
| sell share > 0.6 | 181 (23%) | 15 of 25 | $565.25 | $327.53 | +$237.72 | 0.0001 |
| sell share > 0.75 | 90 (11%) | 9 of 25 | $295.39 | $139.95 | +$155.44 | 0.0009 |
| net sold > 500 contracts | 138 (17%) | 11 of 25 | $414.71 | $286.50 | +$128.22 | 0.0015 |
| net sold > 2,000 contracts (top decile) | 77 (10%) | 7 of 25 | $266.28 | $157.99 | +$108.29 | 0.007 |
| ANY selling of our side in 3 s | 715 (90%) | 23 of 25 | -- | -- | -$511.58 | 0.55 |

Dollars by sell-share bucket (all covered markets):

| 3 s sell share | markets | losers | $ lost | $ won | net |
|---|---|---|---|---|---|
| 0 - 0.25 | 298 | 4 | -$101.85 | +$453.45 | **+$351.60** |
| 0.25 - 0.5 | 210 | 3 | -$76.94 | +$351.99 | **+$275.05** |
| 0.5 - 0.75 | 172 | 8 | -$276.12 | +$341.83 | +$65.71 |
| 0.75 - 1.0 | 90 | 9 | -$295.39 | +$139.95 | **-$155.44** |
| no trades in 3 s | 23 | 1 | -$2.47 | +$46.78 | +$44.31 |

Loss rate climbs monotonically with the share (1.3%, 1.4%, 4.7%, 10%), which is
what a real signal looks like; but the money in the top bucket is 9 markets.

## Robustness (all on the 3 s sell share unless stated)

- Leave one loser out, worst case: p = 0.0011. No single loser carries it.
- Close level (one row per close, mean share over its markets): closes with a
  loser median 0.62 vs 0.36, p = 0.007.
- Every day that had a loser: 09-10 3/3 flagged, 09-11 1/1, 09-12 3/5, 09-13
  1/1, 09-14 1/2, 09-16 0/2, 09-18 1/1, 09-19 4/4, 09-20 2/2, 09-21 1/2, 09-23
  0/1; winners flagged 18-45% each day.
- By leg: same direction in all three (no leg p = 0.07, early p = 0.009,
  full p = 0.04).
- Normal pin entries only (paid >= 90c, 754 markets, 20 losers, -$636.24):
  losers median 0.62 vs 0.34, p = 0.02; 12 of 20 losers flagged, p = 0.009.
  Weaker: five losers entered at 10c-82c (KXDOGE 10c, KXBTC 53c, KXSOL 59c,
  KXBNB 75c, KXXRP 82c) all had share 0.69-0.96 and add to the full-sample
  strength; those were markets already collapsing when we bought.
- Not a proxy for distance to strike: flagged and unflagged entries sit the
  same distance from the strike (median +5.4 vs +5.2 sigma, p = 0.72).
- Index feed, next 10 s, in per-second sigma: all covered, flagged mean -1.53
  vs unflagged -0.22 (p = 0.015) -- driven by the losers. Winners only: -0.59
  vs -0.03 (p = 0.16). Losers: -15.1 flagged vs -12.9 unflagged (p = 0.91),
  against us in 25 of 25.

## Every covered loser

| ticker | side | paid | tau | pnl | 3 s sold / bought (contracts) | share | trades 3 s | 3 s trend | flag |
|---|---|---|---|---|---|---|---|---|---|
| KXBTC15M-26SEP191600-00 | no | 98c | 45 | -107.95 | 12,799 / 7,150 | 0.64 | 345 | +0.4c | FLAG |
| KXBTC15M-26SEP190200-00 | no | 94c | 35 | -66.34 | 37,085 / 12,245 | 0.75 | 792 | +4.0c | FLAG |
| KXXRP15M-26SEP192345-45 | no | 98c | 41 | -64.95 | 1,069 / 47 | 0.96 | 31 | -1.4c | FLAG |
| KXBNB15M-26SEP191230-30 | yes | 97c | 23 | -61.75 | 751 / 154 | 0.83 | 52 | -5.0c | FLAG |
| KXNEAR15M-26SEP211245-45 | yes | 91c | 44 | -59.09 | 229 / 273 | 0.46 | 61 | -7.8c | pass |
| KXBNB15M-26SEP190145-45 | yes | 75c | 24 | -57.76 | 481 / 219 | 0.69 | 33 | -9.9c | FLAG |
| KXNEAR15M-26SEP082045-45 | no | 96c | 22 | -52.60 | 11 / 1,110 | 0.01 | 37 | +5.2c | pass |
| KXHYPE15M-26SEP192345-45 | no | 94c | 33 | -43.92 | 96 / 35 | 0.73 | 17 | -2.9c | FLAG |
| KXBTC15M-26SEP140530-30 | no | 97c | 13 | -34.26 | 17,559 / 4,100 | 0.81 | 351 | -1.9c | FLAG |
| KXHYPE15M-26SEP211815-15 | yes | 98c | 43 | -31.27 | 169 / 94 | 0.64 | 17 | +2.7c | FLAG |
| KXHYPE15M-26SEP141600-00 | no | 95c | 30 | -29.90 | 0 / 2 | 0.00 | 1 | 0.0c | pass |
| KXBTC15M-26SEP172115-15 | yes | 53c | 38 | -27.87 | 33,720 / 11,972 | 0.74 | 506 | +1.4c | FLAG |
| KXSOL15M-26SEP112300-00 | no | 98c | 29 | -19.61 | 1,404 / 462 | 0.75 | 63 | +1.2c | FLAG |
| KXSOL15M-26SEP120400-00 | yes | 94c | 19 | -18.88 | 110 / 1,325 | 0.08 | 98 | +36.0c | pass |
| KXBNB15M-26SEP100130-30 | yes | 94c | 26 | -17.60 | 201 / 35 | 0.85 | 27 | +5.2c | FLAG |
| KXXRP15M-26SEP100100-00 | yes | 82c | 21 | -16.61 | 6,526 / 290 | 0.96 | 97 | -19.8c | FLAG |
| KXSOL15M-26SEP110830-30 | no | 59c | 30 | -12.16 | 5,264 / 364 | 0.94 | 83 | -58.8c | FLAG |
| KXNEAR15M-26SEP160430-30 | yes | 91c | 21 | -9.22 | 807 / 1,641 | 0.33 | 47 | -6.2c | pass |
| KXZEC15M-26SEP122000-00 | yes | 96c | 25 | -8.63 | 241 / 333 | 0.42 | 66 | -2.2c | pass |
| KXETH15M-26SEP121115-15 | no | 98c | 29 | -5.16 | 699 / 641 | 0.52 | 29 | +1.0c | FLAG |
| KXDOGE15M-26SEP222245-45 | no | 93c | 12 | -2.47 | 0 / 0 | n/a | 0 | -- | pass (no print for 803 s) |
| KXDOGE15M-26SEP101815-15 | no | 10c | 11 | -2.12 | 2,160 / 248 | 0.90 | 59 | -86.0c | FLAG |
| KXBNB15M-26SEP131230-30 | no | 92c | 5 | -1.10 | 332 / 319 | 0.51 | 70 | +8.0c | FLAG |
| KXBTC15M-26SEP121100-00 | no | 90c | 30 | -1.09 | 22,371 / 13,708 | 0.62 | 532 | +9.0c | FLAG |
| KXBNB15M-26SEP161230-30 | no | 98c | 30 | -0.47 | 21 / 588 | 0.03 | 32 | +1.1c | pass |

Uncovered losers (no tape): KXBTC15M-26SEP232030-30 -$130.41, and one KXDOGE
-$12.14.

## What this sample can and cannot say

- The COUNT result (losers are 4x more likely to have been flagged) is
  established at this n; it survived the multiple-looks bar, leave-one-out,
  the close-level test and the by-day split.
- The DOLLAR result is not. 25 losers, of which 2 hold 23% of the money; the
  net of a skip rule flips sign on those 2.
- Pre-registered live bar for the flag as logged (no behaviour change):
  "sell share > 0.5 in the 3 s before the order", flagged fraction ~33%,
  compare loss rate flagged vs unflagged, one-sided, 5% false-alarm, 80%
  power. At the observed 6.5% vs 1.5%: **400 more entries (~8 days at 50/day,
  ~13 losers)**. If the true lift is 4.5% vs 1.5%: 850 entries (~17 days). If
  only 3% vs 1.5%: 2,650 entries (~53 days). Do not deploy a skip before the
  bar is met; a delay rule needs its own paper arm because the tape cannot
  price it.
- A top-decile skip rule (79 flagged) could only have been told from chance
  at a 3.1x enrichment or more with this n; the observed top decile on 3 s net
  sold was 7 losers vs 2.5 expected (p = 0.007), i.e. right at that edge.

## Resources

Scan streamed 2.87 GB of gzip once (172 s); peak process RAM well under
1 GB (free RAM never below 788 MB, 2,318 MB free at the end). After the job:
`kalshi_collector.py` alive (54 MB), `crypto_feeds.py` alive (40 MB), live
`pinrun --live` alive (99 MB). Disk free 21.46 GB.

## Appendix A -- full auto-generated tables (tox_analyze.py)

### 2. Losers vs winners, covered markets only

n = 793 markets (582 distinct closes); losers 25 markets (24 closes, $-752.76); winners 768 ($1334.00). Sizes differ per market, so every bucket below carries dollars, not just counts.

#### Window: 3 s before our order

| metric | losers mean | losers median | winners mean | winners median | rank-sum p |
|---|---|---|---|---|---|
| taker SOLD our side, contracts | 5764.2 | 698.5 | 3645.3 | 293.2 | 0.12 |
| taker SOLD our side, dollars | $5326 | $676 | $3352 | $274 | 0.12 |
| taker BOUGHT our side, contracts | 2294.2 | 333.3 | 3676.8 | 533.4 | 0.31 |
| taker BOUGHT our side, dollars | $2127 | $289 | $3392 | $508 | 0.29 |
| net sold - bought, contracts | +3470.0 | +165.2 | -31.4 | -132.9 | 0.00 |
| sell share of taker volume (0..1) | 0.59 | 0.66 | 0.37 | 0.35 | 0.00 |
| trades in window | 137.8 | 59.0 | 136.7 | 55.5 | 0.99 |
| price trend of our side, cents | -5.07 | +0.00 | +3.90 | +1.50 | 0.01 |

Markets with NO trades at all in the window: losers 1 of 25, winners 22 of 768.

#### Window: 10 s before our order

| metric | losers mean | losers median | winners mean | winners median | rank-sum p |
|---|---|---|---|---|---|
| taker SOLD our side, contracts | 14071.2 | 1242.9 | 10482.4 | 1086.5 | 0.40 |
| taker SOLD our side, dollars | $12309 | $963 | $9096 | $932 | 0.39 |
| taker BOUGHT our side, contracts | 11061.2 | 1649.0 | 10303.2 | 1701.3 | 0.72 |
| taker BOUGHT our side, dollars | $9552 | $1551 | $8923 | $1539 | 0.74 |
| net sold - bought, contracts | +3010.0 | -175.8 | +179.2 | -403.8 | 0.18 |
| sell share of taker volume (0..1) | 0.49 | 0.47 | 0.39 | 0.38 | 0.04 |
| trades in window | 388.6 | 139.0 | 385.4 | 152.5 | 0.51 |
| price trend of our side, cents | +3.92 | +1.10 | +14.90 | +7.80 | 0.01 |

Markets with NO trades at all in the window: losers 1 of 25, winners 20 of 768.

#### Window: 30 s before our order

| metric | losers mean | losers median | winners mean | winners median | rank-sum p |
|---|---|---|---|---|---|
| taker SOLD our side, contracts | 24173.1 | 3186.5 | 27472.3 | 3341.9 | 0.68 |
| taker SOLD our side, dollars | $19776 | $2156 | $20333 | $2309 | 0.97 |
| taker BOUGHT our side, contracts | 25778.9 | 3975.2 | 25668.2 | 4607.4 | 0.45 |
| taker BOUGHT our side, dollars | $20878 | $3051 | $19178 | $3510 | 0.68 |
| net sold - bought, contracts | -1605.8 | -892.2 | +1804.1 | -614.8 | 0.63 |
| sell share of taker volume (0..1) | 0.44 | 0.41 | 0.43 | 0.44 | 0.72 |
| trades in window | 928.9 | 361.0 | 980.0 | 383.5 | 0.59 |
| price trend of our side, cents | +12.27 | +7.30 | +31.20 | +26.80 | 0.00 |

Markets with NO trades at all in the window: losers 1 of 25, winners 19 of 768.

#### Last print before our order

| metric | losers mean | losers median | winners mean | winners median | rank-sum p |
|---|---|---|---|---|---|
| last traded price of our side minus what we paid, cents | -1.06 | -0.10 | -1.88 | -0.12 | 0.68 |
| age of that print, seconds | 32.2 | 0.0 | 9.8 | 0.1 | 0.54 |

#### Positive control: the SAME estimator 2-32 s AFTER our fill

If the estimator cannot see selling of our side after entry on the losers (when the market is moving against us), a null before entry means nothing.

| metric | losers mean | losers median | winners mean | winners median | rank-sum p |
|---|---|---|---|---|---|
| taker SOLD our side, contracts | 45453.9 | 7591.5 | 30193.0 | 2117.1 | 0.00 |
| taker BOUGHT our side, contracts | 55560.1 | 4113.5 | 21366.7 | 3059.6 | 0.04 |
| net sold - bought, contracts | -10106.3 | +1991.0 | +8826.2 | -559.7 | 0.28 |
| sell share (0..1) | 0.52 | 0.55 | 0.42 | 0.43 | 0.01 |
| price trend of our side, cents | -42.43 | -53.90 | +2.80 | +1.90 | 0.00 |

### 3. Would a "skip when our side is being sold" rule have helped?

Rank every covered market by the sell-pressure metric; flag the top 10% (ties broken by sell dollars). Loss rate and money in the flagged bucket vs the rest. p = one-sided exact test that losers are enriched in the flagged bucket.

| metric | window | flagged n | losers in flagged | $ lost in flagged | $ won in flagged (given up if skipped) | net $ if skipped | losers in rest | $ lost in rest | p |
|---|---|---|---|---|---|---|---|---|---|
| sold contracts | 3 s | 79 | 4 | $-129.56 | $168.74 | $-39.18 | 21 | $-623.20 | 0.23 |
| sold dollars | 3 s | 79 | 4 | $-129.56 | $155.66 | $-26.10 | 21 | $-623.20 | 0.23 |
| net sold | 3 s | 79 | 7 | $-266.28 | $165.71 | $+100.57 | 18 | $-486.48 | 0.01 |
| sell share | 3 s | 79 | 7 | $-209.44 | $129.31 | $+80.13 | 18 | $-543.32 | 0.01 |
| sold contracts | 10 s | 79 | 3 | $-95.31 | $172.16 | $-76.85 | 22 | $-657.46 | 0.46 |
| sold dollars | 10 s | 79 | 3 | $-95.31 | $157.92 | $-62.61 | 22 | $-657.46 | 0.46 |
| net sold | 10 s | 79 | 4 | $-122.98 | $170.42 | $-47.44 | 21 | $-629.79 | 0.23 |
| sell share | 10 s | 79 | 5 | $-131.82 | $161.54 | $-29.71 | 20 | $-620.94 | 0.09 |
| sold contracts | 30 s | 79 | 2 | $-94.21 | $170.55 | $-76.34 | 23 | $-658.55 | 0.73 |
| sold dollars | 30 s | 79 | 3 | $-202.16 | $161.11 | $+41.06 | 22 | $-550.60 | 0.46 |
| net sold | 30 s | 79 | 2 | $-82.95 | $178.69 | $-95.75 | 23 | $-669.82 | 0.73 |
| sell share | 30 s | 79 | 2 | $-28.77 | $165.15 | $-136.38 | 23 | $-724.00 | 0.73 |

"net $ if skipped" = the losses avoided minus the wins given up; positive means the rule would have made money over these markets.

#### Simpler cut: ANY taker selling of our side in the window vs none

| window | markets with selling | losers | $ lost | $ won | net $ if skipped | markets with none | losers | $ lost | p |
|---|---|---|---|---|---|---|---|---|---|
| 3 s | 715 | 23 | $-720.39 | $1231.97 | $-511.58 | 78 | 2 | $-32.37 | 0.55 |
| 10 s | 767 | 24 | $-750.30 | $1284.52 | $-534.22 | 26 | 1 | $-2.47 | 0.80 |
| 30 s | 773 | 24 | $-750.30 | $1291.40 | $-541.10 | 20 | 1 | $-2.47 | 0.87 |

### 4. Split by time left at entry

#### <= 20 s: 227 markets, 5 losers ($-58.82), winners $493.29

| metric | window | losers mean | losers median | winners mean | winners median | rank-sum p | top-decile flagged n | losers in flagged | $ lost flagged | $ won flagged | p |
|---|---|---|---|---|---|---|---|---|---|---|---|
| sold contracts | 3 s | 4032.31 | 331.81 | 4759.71 | 395.90 | 0.97 | 22 | 1 | $-34.26 | $49.36 | 0.40 |
| net sold | 3 s | 2834.13 | 12.91 | -372.81 | -144.14 | 0.18 | 22 | 1 | $-34.26 | $49.46 | 0.40 |
| sell share | 3 s | 0.57 | 0.66 | 0.37 | 0.37 | 0.18 | 22 | 2 | $-36.38 | $50.57 | 0.08 |
| sold contracts | 10 s | 7840.57 | 1114.81 | 13668.83 | 1482.63 | 0.60 | 22 | 0 | $0.00 | $66.49 | 1.00 |
| net sold | 10 s | -624.83 | -1148.40 | 39.56 | -370.63 | 0.62 | 22 | 0 | $0.00 | $41.79 | 1.00 |
| sell share | 10 s | 0.40 | 0.41 | 0.41 | 0.42 | 0.95 | 22 | 0 | $0.00 | $44.83 | 1.00 |
| sold contracts | 30 s | 18028.91 | 5073.64 | 34145.73 | 4459.34 | 0.91 | 22 | 0 | $0.00 | $64.75 | 1.00 |
| net sold | 30 s | -3458.49 | -1784.71 | 2093.64 | -355.52 | 0.26 | 22 | 0 | $0.00 | $46.12 | 1.00 |
| sell share | 30 s | 0.45 | 0.45 | 0.46 | 0.47 | 0.77 | 22 | 0 | $0.00 | $51.03 | 1.00 |

#### 21-45 s: 566 markets, 20 losers ($-693.94), winners $840.71

| metric | window | losers mean | losers median | winners mean | winners median | rank-sum p | top-decile flagged n | losers in flagged | $ lost flagged | $ won flagged | p |
|---|---|---|---|---|---|---|---|---|---|---|---|
| sold contracts | 3 s | 6197.15 | 724.74 | 3192.23 | 241.56 | 0.06 | 56 | 3 | $-95.31 | $110.80 | 0.32 |
| net sold | 3 s | 3628.97 | 213.69 | 107.35 | -126.78 | 0.00 | 56 | 6 | $-232.02 | $108.60 | 0.01 |
| sell share | 3 s | 0.59 | 0.66 | 0.37 | 0.34 | 0.00 | 56 | 5 | $-173.06 | $80.88 | 0.04 |
| sold contracts | 10 s | 15628.92 | 1265.19 | 9186.86 | 940.04 | 0.17 | 56 | 3 | $-95.31 | $105.76 | 0.32 |
| net sold | 10 s | 3918.77 | -139.42 | 235.98 | -407.46 | 0.08 | 56 | 4 | $-122.98 | $125.93 | 0.13 |
| sell share | 10 s | 0.50 | 0.47 | 0.38 | 0.37 | 0.02 | 56 | 3 | $-72.68 | $113.54 | 0.32 |
| sold contracts | 30 s | 25709.20 | 2148.55 | 24758.88 | 2828.61 | 0.74 | 56 | 2 | $-94.21 | $107.57 | 0.61 |
| net sold | 30 s | -1142.61 | -743.03 | 1686.36 | -764.02 | 0.89 | 56 | 3 | $-110.82 | $113.67 | 0.32 |
| sell share | 30 s | 0.44 | 0.40 | 0.42 | 0.43 | 0.95 | 56 | 2 | $-28.77 | $103.33 | 0.61 |

### 5. Every covered loser, one line each (10 s window; 30 s in brackets)

| ticker | side | paid | tau s | pnl $ | sold our side c (30 s) | bought our side c (30 s) | trades (30 s) | trend 10 s c | last px vs paid c | age s | sold 2-32 s AFTER | bought AFTER |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| KXBTC15M-26SEP191600-00 | no | 98c | 45 | -107.95 | 30434 (86214) | 28692 (106144) | 1261 (3956) | +1.1 | +0.0 | 0 | 250341 | 349295 |
| KXBTC15M-26SEP190200-00 | no | 94c | 35 | -66.34 | 113450 (164036) | 74522 (153642) | 2170 (3938) | +17.3 | -0.1 | 0 | 237906 | 274593 |
| KXXRP15M-26SEP192345-45 | no | 98c | 41 | -64.95 | 1590 (3187) | 2029 (4627) | 132 (389) | -0.8 | -0.1 | 0 | 8886 | 9448 |
| KXBNB15M-26SEP191230-30 | yes | 97c | 23 | -61.75 | 990 (1544) | 1645 (2138) | 314 (727) | -4.9 | -5.8 | 0 | 6906 | 2629 |
| KXNEAR15M-26SEP211245-45 | yes | 91c | 44 | -59.09 | 338 (1129) | 311 (2021) | 73 (192) | -6.9 | -3.1 | 0 | 7270 | 3069 |
| KXBNB15M-26SEP190145-45 | yes | 75c | 24 | -57.76 | 832 (1617) | 1710 (6149) | 92 (640) | -8.0 | +8.0 | 0 | 8803 | 4113 |
| KXNEAR15M-26SEP082045-45 | no | 96c | 22 | -52.60 | 1288 (1863) | 2842 (3416) | 139 (227) | +38.1 | -0.1 | 0 | 5459 | 3468 |
| KXHYPE15M-26SEP192345-45 | no | 94c | 33 | -43.92 | 474 (668) | 135 (1174) | 71 (176) | -3.4 | +1.0 | 0 | 3284 | 5317 |
| KXBTC15M-26SEP140530-30 | no | 97c | 13 | -34.26 | 34743 (73616) | 36424 (87259) | 797 (2441) | -1.9 | +0.3 | 0 | 117988 | 97014 |
| KXHYPE15M-26SEP211815-15 | yes | 98c | 43 | -31.27 | 1243 (3205) | 638 (2280) | 57 (388) | +0.8 | +0.8 | 0 | 8402 | 5528 |
| KXHYPE15M-26SEP141600-00 | no | 95c | 30 | -29.90 | 115 (314) | 291 (511) | 16 (51) | +2.8 | -0.2 | 1 | 7592 | 3806 |
| KXBTC15M-26SEP172115-15 | yes | 53c | 38 | -27.87 | 81747 (124760) | 43183 (118142) | 1633 (3390) | +5.4 | +44.7 | 0 | 237630 | 361763 |
| KXSOL15M-26SEP112300-00 | no | 98c | 29 | -19.61 | 1573 (2434) | 1412 (3975) | 207 (349) | +5.3 | -0.6 | 0 | 17836 | 13095 |
| KXSOL15M-26SEP120400-00 | yes | 94c | 19 | -18.88 | 354 (7917) | 1781 (9702) | 140 (337) | +39.0 | +0.0 | 0 | 9985 | 5619 |
| KXBNB15M-26SEP100130-30 | yes | 94c | 26 | -17.60 | 496 (1168) | 599 (2300) | 92 (181) | +28.2 | -0.8 | 0 | 3506 | 3885 |
| KXXRP15M-26SEP100100-00 | yes | 82c | 21 | -16.61 | 7658 (11797) | 1016 (4176) | 156 (561) | -19.1 | -2.0 | 0 | 10185 | 11369 |
| KXSOL15M-26SEP110830-30 | no | 59c | 30 | -12.16 | 5514 (6140) | 574 (1452) | 96 (194) | -58.7 | -18.1 | 0 | 6303 | 3563 |
| KXNEAR15M-26SEP160430-30 | yes | 91c | 21 | -9.22 | 807 (879) | 1649 (2143) | 51 (98) | -6.0 | +2.2 | 0 | 803 | 1796 |
| KXZEC15M-26SEP122000-00 | yes | 96c | 25 | -8.63 | 525 (1034) | 1412 (1575) | 153 (203) | +38.0 | -7.2 | 1 | 4386 | 1861 |
| KXETH15M-26SEP121115-15 | no | 98c | 29 | -5.16 | 2516 (8065) | 2812 (8616) | 88 (437) | +4.7 | -0.3 | 0 | 35991 | 30386 |
| KXDOGE15M-26SEP222245-45 | no | 93c | 12 | -2.47 | 0 (0) | 0 (0) | 0 (0) | +0.0 | -45.4 | 803 | 0 | 0 |
| KXDOGE15M-26SEP101815-15 | no | 10c | 11 | -2.12 | 2991 (5074) | 1859 (4658) | 179 (413) | -82.2 | +3.0 | 0 | 601 | 2177 |
| KXBNB15M-26SEP131230-30 | no | 92c | 5 | -1.10 | 1115 (3538) | 2263 (5817) | 148 (361) | +59.0 | -2.3 | 0 | 186 | 2203 |
| KXBTC15M-26SEP121100-00 | no | 90c | 30 | -1.09 | 60564 (93093) | 67601 (110312) | 1541 (3301) | +47.0 | +0.0 | 0 | 141345 | 191839 |
| KXBNB15M-26SEP161230-30 | no | 98c | 30 | -0.47 | 425 (1040) | 1131 (2244) | 110 (273) | +3.3 | -0.6 | 0 | 4752 | 1165 |

### 6. What this sample can and cannot say (power)

- Base loss rate: 25 of 793 markets = 3.2% (about 3 in 100), but only 24 distinct closes carry the losses.
- A top-decile rule flags 79 markets. With this n, the smallest loss rate inside the flagged bucket that could be told apart from the 3.2% base (one-sided, 5% false-alarm, 80% power) is about 9.7% -- i.e. roughly 3.1x enrichment, or 8 losers in the flagged 79 against 2 expected.
- To detect a 2x enrichment (loss rate 6.3% in the flagged decile) would take about 2,900 entered markets (3.7x what we have); at the current ~50 entries/day that is ~58 days.
- To detect a 3x enrichment (loss rate 9.5% in the flagged decile) would take about 900 entered markets (1.1x what we have); at the current ~50 entries/day that is ~18 days.
- Money-weighted: 2 markets (KXBTC15M-26SEP191600-00, KXBTC15M-26SEP190200-00) carry $174.29 of the $752.76 covered loss, so any dollar figure above moves with whether those two land in a bucket.


## Appendix B -- robustness checks (tox_check.py, verbatim)

```
covered 793 losers 25

== A. exact p-values (rank-sum, two-sided) ==
w3_net_c         z=+3.58 p=0.0003  losers n=25 med=165.180  winners n=768 med=-132.920
w3_sell_share    z=+3.54 p=0.0004  losers n=24 med=0.665  winners n=746 med=0.350
w3_trend         z=-2.62 p=0.0088  losers n=25 med=0.000  winners n=768 med=0.015
w3_sell_c        z=+1.57 p=0.1161  losers n=25 med=698.510  winners n=768 med=293.185
w3_buy_c         z=-1.01 p=0.3112  losers n=25 med=333.290  winners n=768 med=533.360
w3_n             z=+0.01 p=0.9936  losers n=25 med=59.000  winners n=768 med=55.500
w10_sell_share   z=+2.07 p=0.0385  losers n=24 med=0.472  winners n=748 med=0.384
w10_net_c        z=+1.33 p=0.1821  losers n=25 med=-175.840  winners n=768 med=-403.810
w10_trend        z=-2.75 p=0.0060  losers n=25 med=0.011  winners n=768 med=0.078
w30_trend        z=-3.15 p=0.0016  losers n=25 med=0.073  winners n=768 med=0.268
post_trend       z=-4.72 p=0.0000  losers n=25 med=-0.539  winners n=768 med=0.019
post_sell_share  z=+2.59 p=0.0097  losers n=24 med=0.545  winners n=744 med=0.431
multiple looks: 24 rank-sum cells in section 2 -> Bonferroni 0.05/24 = 0.0021; 12 decile cells -> 0.0042

== B. clock check: our fill vs t_send ==
n=772 first our-side print at our price nearest t_send: min -0.169 s, p5 -0.057, median +0.026, p95 +0.093, max +0.211
negative = a print at our price on our side BEFORE t_send (could be crowd, or clock skew): 238 of 772 ; below -0.5 s: 0

== C. count-based 3 s cut: sell share > 0.5 (more of our side sold than bought) ==
all        share>0.5: flagged 262 of 793 (33%), losers 17 of 25 ($-571.51), wins given up $481.78, net if skipped $+89.73, p=0.0003
all        share>0.6: flagged 181 of 793 (23%), losers 15 of 25 ($-565.25), wins given up $327.53, net if skipped $+237.72, p=0.0001
all        share>0.75: flagged 90 of 793 (11%), losers 9 of 25 ($-295.39), wins given up $139.95, net if skipped $+155.44, p=0.0009
all        net sold > 0 c: flagged 262 of 793 (33%), losers 17 of 25 ($-571.51), wins given up $481.78, net if skipped $+89.73, p=0.0003
all        net sold > 100 c: flagged 220 of 793 (28%), losers 13 of 25 ($-490.07), wins given up $426.91, net if skipped $+63.16, p=0.0079
all        net sold > 500 c: flagged 138 of 793 (17%), losers 11 of 25 ($-414.71), wins given up $286.50, net if skipped $+128.22, p=0.0015
all        net sold > 2000 c: flagged 77 of 793 (10%), losers 7 of 25 ($-266.28), wins given up $157.99, net if skipped $+108.29, p=0.0071
tau<=20    share>0.5: flagged 72 of 227 (32%), losers 3 of 5 ($-37.47), wins given up $163.31, net if skipped $-125.83, p=0.1842
tau<=20    share>0.6: flagged 41 of 227 (18%), losers 2 of 5 ($-36.38), wins given up $93.66, net if skipped $-57.28, p=0.2223
tau<=20    share>0.75: flagged 14 of 227 (6%), losers 2 of 5 ($-36.38), wins given up $22.25, net if skipped $+14.13, p=0.0318
tau<=20    net sold > 0 c: flagged 72 of 227 (32%), losers 3 of 5 ($-37.47), wins given up $163.31, net if skipped $-125.83, p=0.1842
tau<=20    net sold > 100 c: flagged 63 of 227 (28%), losers 2 of 5 ($-36.38), wins given up $149.05, net if skipped $-112.67, p=0.4256
tau<=20    net sold > 500 c: flagged 41 of 227 (18%), losers 2 of 5 ($-36.38), wins given up $101.26, net if skipped $-64.88, p=0.2223
tau<=20    net sold > 2000 c: flagged 23 of 227 (10%), losers 1 of 5 ($-34.26), wins given up $52.06, net if skipped $-17.80, p=0.4168
tau 21-45  share>0.5: flagged 190 of 566 (34%), losers 14 of 20 ($-534.03), wins given up $318.47, net if skipped $+215.56, p=0.0008
tau 21-45  share>0.6: flagged 140 of 566 (25%), losers 13 of 20 ($-528.87), wins given up $233.87, net if skipped $+295.00, p=0.0001
tau 21-45  share>0.75: flagged 76 of 566 (13%), losers 7 of 20 ($-259.01), wins given up $117.70, net if skipped $+141.30, p=0.0108
tau 21-45  net sold > 0 c: flagged 190 of 566 (34%), losers 14 of 20 ($-534.03), wins given up $318.47, net if skipped $+215.56, p=0.0008
tau 21-45  net sold > 100 c: flagged 157 of 566 (28%), losers 11 of 20 ($-453.69), wins given up $277.85, net if skipped $+175.83, p=0.0082
tau 21-45  net sold > 500 c: flagged 97 of 566 (17%), losers 9 of 20 ($-378.33), wins given up $185.24, net if skipped $+193.09, p=0.0029
tau 21-45  net sold > 2000 c: flagged 54 of 566 (10%), losers 6 of 20 ($-232.02), wins given up $105.93, net if skipped $+126.09, p=0.0077

== D. restrict to the normal pin population: paid >= 90c ==
n 754 losers 20 $ -636.24
w3_net_c         z=+2.51 p=0.0122 losers med=59.350 winners med=-134.100
w3_sell_share    z=+2.32 p=0.0205 losers med=0.620 winners med=0.344
w3_trend         z=-1.45 p=0.1471 losers med=0.007 winners med=0.015
w10_sell_share   z=+1.15 p=0.2499 losers med=0.453 winners med=0.381
share>0.5: flagged 243 of 754, losers 12 of 20, $lost -454.99, $won given up 391.83, p=0.0089

== E. by leg ==
leg=None   n=451 losers=15 ($-229.39) sell-share-3s losers med=0.52 winners med=0.35 p=0.074
leg=early  n=228 losers=7 ($-401.39) sell-share-3s losers med=0.73 winners med=0.41 p=0.009
leg=full   n=114 losers=3 ($-121.98) sell-share-3s losers med=0.76 winners med=0.31 p=0.040

== F. close-level version (one row per close; label = any loser in the close; metric = mean 3 s sell share over its markets) ==
closes with a loser 23 med=0.620; closes without 542 med=0.361; z=+2.71 p=0.0067
net sold 3 s: closes with a loser 24 med=98.3; without 558 med=-151.7; z=+2.86 p=0.0042

== G. which losers does "3 s sell share > 0.5" catch, and which does it miss ==
KXBTC15M-26SEP191600-00      no  paid 98c tau 45 pnl  -107.95 3s: sold    12799 bought     7150 share 0.64 trades  345 trend +0.4c  -> FLAG
KXBTC15M-26SEP190200-00      no  paid 94c tau 35 pnl   -66.34 3s: sold    37085 bought    12245 share 0.75 trades  792 trend +4.0c  -> FLAG
KXXRP15M-26SEP192345-45      no  paid 98c tau 41 pnl   -64.95 3s: sold     1069 bought       47 share 0.96 trades   31 trend -1.4c  -> FLAG
KXBNB15M-26SEP191230-30      yes paid 97c tau 23 pnl   -61.75 3s: sold      751 bought      154 share 0.83 trades   52 trend -5.0c  -> FLAG
KXNEAR15M-26SEP211245-45     yes paid 91c tau 44 pnl   -59.09 3s: sold      229 bought      273 share 0.46 trades   61 trend -7.8c  -> pass
KXBNB15M-26SEP190145-45      yes paid 75c tau 24 pnl   -57.76 3s: sold      481 bought      219 share 0.69 trades   33 trend -9.9c  -> FLAG
KXNEAR15M-26SEP082045-45     no  paid 96c tau 22 pnl   -52.60 3s: sold       11 bought     1110 share 0.01 trades   37 trend +5.2c  -> pass
KXHYPE15M-26SEP192345-45     no  paid 94c tau 33 pnl   -43.92 3s: sold       96 bought       35 share 0.73 trades   17 trend -2.9c  -> FLAG
KXBTC15M-26SEP140530-30      no  paid 97c tau 13 pnl   -34.26 3s: sold    17559 bought     4100 share 0.81 trades  351 trend -1.9c  -> FLAG
KXHYPE15M-26SEP211815-15     yes paid 98c tau 43 pnl   -31.27 3s: sold      169 bought       94 share 0.64 trades   17 trend +2.7c  -> FLAG
KXHYPE15M-26SEP141600-00     no  paid 95c tau 30 pnl   -29.90 3s: sold        0 bought        2 share 0.00 trades    1 trend +0.0c  -> pass
KXBTC15M-26SEP172115-15      yes paid 53c tau 38 pnl   -27.87 3s: sold    33720 bought    11972 share 0.74 trades  506 trend +1.4c  -> FLAG
KXSOL15M-26SEP112300-00      no  paid 98c tau 29 pnl   -19.61 3s: sold     1404 bought      462 share 0.75 trades   63 trend +1.2c  -> FLAG
KXSOL15M-26SEP120400-00      yes paid 94c tau 19 pnl   -18.88 3s: sold      110 bought     1325 share 0.08 trades   98 trend +36.0c  -> pass
KXBNB15M-26SEP100130-30      yes paid 94c tau 26 pnl   -17.60 3s: sold      201 bought       35 share 0.85 trades   27 trend +5.2c  -> FLAG
KXXRP15M-26SEP100100-00      yes paid 82c tau 21 pnl   -16.61 3s: sold     6526 bought      290 share 0.96 trades   97 trend -19.8c  -> FLAG
KXSOL15M-26SEP110830-30      no  paid 59c tau 30 pnl   -12.16 3s: sold     5264 bought      364 share 0.94 trades   83 trend -58.8c  -> FLAG
KXNEAR15M-26SEP160430-30     yes paid 91c tau 21 pnl    -9.22 3s: sold      807 bought     1641 share 0.33 trades   47 trend -6.2c  -> pass
KXZEC15M-26SEP122000-00      yes paid 96c tau 25 pnl    -8.63 3s: sold      241 bought      333 share 0.42 trades   66 trend -2.2c  -> pass
KXETH15M-26SEP121115-15      no  paid 98c tau 29 pnl    -5.16 3s: sold      699 bought      641 share 0.52 trades   29 trend +1.0c  -> FLAG
KXDOGE15M-26SEP222245-45     no  paid 93c tau 12 pnl    -2.47 3s: sold        0 bought        0 share n/a trades    0 trend +0.0c  -> pass
KXDOGE15M-26SEP101815-15     no  paid 10c tau 11 pnl    -2.12 3s: sold     2160 bought      248 share 0.90 trades   59 trend -86.0c  -> FLAG
KXBNB15M-26SEP131230-30      no  paid 92c tau  5 pnl    -1.10 3s: sold      332 bought      319 share 0.51 trades   70 trend +8.0c  -> FLAG
KXBTC15M-26SEP121100-00      no  paid 90c tau 30 pnl    -1.09 3s: sold    22371 bought    13708 share 0.62 trades  532 trend +9.0c  -> FLAG
KXBNB15M-26SEP161230-30      no  paid 98c tau 30 pnl    -0.47 3s: sold       21 bought      588 share 0.03 trades   32 trend +1.1c  -> pass

== H. window-start price level (is the trend difference just a level difference?) ==
first our-side print in 3 s window: losers med 96.1c mean 93.1c; winners med 94.5c mean 91.1c; p=0.1100
first our-side print in 10 s window: losers med 93.4c mean 83.8c; winners med 88.0c mean 79.9c; p=0.0246
first our-side print in 30 s window: losers med 82.0c mean 75.1c; winners med 68.0c mean 63.2c; p=0.0118
price paid: losers med 94.1c winners med 97.4c p=0.0005

== I. leave-one-out on the 3 s sell-share rank-sum (drop each loser in turn; max p) ==
max p over leave-one-out: 0.0011, min 0.0001

== J. same 3 s sell-share, on the dollars-weighted view: sum pnl by share bucket ==
share [0,0.25): n=298 losers=4 $lost=-101.85 $won=453.45 net=+351.60
share [0.25,0.5): n=210 losers=3 $lost=-76.94 $won=351.99 net=+275.05
share [0.5,0.75): n=172 losers=8 $lost=-276.12 $won=341.83 net=+65.71
share [0.75,1.01): n=90 losers=9 $lost=-295.39 $won=139.95 net=-155.44
no trades in 3 s: n=23 losers=1 net=+44.31

== K. by day: does the 3 s signal hold across days (losers flagged / losers, winners flagged / winners) ==
09-08: n= 25 losers 0/0 flagged, winners 7/25 flagged (28%)
09-09: n= 35 losers 0/1 flagged, winners 10/34 flagged (29%)
09-10: n= 49 losers 3/3 flagged, winners 15/46 flagged (33%)
09-11: n= 37 losers 1/1 flagged, winners 9/36 flagged (25%)
09-12: n= 94 losers 3/5 flagged, winners 31/89 flagged (35%)
09-13: n= 61 losers 1/1 flagged, winners 25/60 flagged (42%)
09-14: n= 52 losers 1/2 flagged, winners 9/50 flagged (18%)
09-15: n= 40 losers 0/0 flagged, winners 9/40 flagged (22%)
09-16: n= 44 losers 0/2 flagged, winners 12/42 flagged (29%)
09-17: n= 51 losers 0/0 flagged, winners 14/51 flagged (27%)
09-18: n= 65 losers 1/1 flagged, winners 24/64 flagged (38%)
09-19: n= 71 losers 4/4 flagged, winners 30/67 flagged (45%)
09-20: n= 64 losers 2/2 flagged, winners 21/62 flagged (34%)
09-21: n= 51 losers 1/2 flagged, winners 12/49 flagged (24%)
09-22: n= 27 losers 0/0 flagged, winners 9/27 flagged (33%)
09-23: n= 26 losers 0/1 flagged, winners 8/25 flagged (32%)
09-24: n=  1 losers 0/0 flagged, winners 0/1 flagged (0%)
```

## Appendix C -- index-feed test (tox_index.py, verbatim)

```
index hour files needed 302 missing [] errors {'20260909T13': 'EOFError: Compressed file ended before the end-of-stream marker was reached', '20260915T13': 'EOFError: Compressed file ended before the end-of-stream marker was reached'}
markets with index around entry 792 of 793
ALL covered: index move toward our side over the next 10 s, in per-second-sigma units:
   flagged n=262: mean -1.53 median -0.37; moved AGAINST us in 148 of 262 (56%)
   unflagged n=530: mean -0.22 median -0.02; moved AGAINST us in 265 of 530 (50%)
   rank-sum p=0.0146
   5 s: flagged mean -1.30 med -0.11 (against 53%); unflagged mean -0.21 med +0.00 (against 49%); p=0.0369
   distance of index from strike at entry (sigma, + = our side): flagged med +5.4, unflagged med +5.2, p=0.7191
WINNERS only: index move toward our side over the next 10 s, in per-second-sigma units:
   flagged n=245: mean -0.59 median -0.20; moved AGAINST us in 131 of 245 (53%)
   unflagged n=522: mean -0.03 median +0.00; moved AGAINST us in 257 of 522 (49%)
   rank-sum p=0.1581
   5 s: flagged mean -0.52 med -0.01 (against 50%); unflagged mean -0.08 med +0.00 (against 48%); p=0.3150
   distance of index from strike at entry (sigma, + = our side): flagged med +5.5, unflagged med +5.2, p=0.8529
LOSERS only: index move toward our side over the next 10 s, in per-second-sigma units:
   flagged n=17: mean -15.05 median -11.18; moved AGAINST us in 17 of 17 (100%)
   unflagged n=8: mean -12.88 median -11.62; moved AGAINST us in 8 of 8 (100%)
   rank-sum p=0.9072
   5 s: flagged mean -12.63 med -8.00 (against 94%); unflagged mean -8.20 med -10.77 (against 88%); p=0.8157
   distance of index from strike at entry (sigma, + = our side): flagged med +4.2, unflagged med +3.4, p=1.0000

within distance-to-strike quartiles (all covered): fraction of 10 s moves against us, flagged vs unflagged
  Q1 dist med +1.5 sigma: flagged 38/72 against (53%), unflagged 70/126 (56%); losers 10
  Q2 dist med +4.2 sigma: flagged 27/56 against (48%), unflagged 64/142 (45%); losers 4
  Q3 dist med +6.4 sigma: flagged 47/70 against (67%), unflagged 58/128 (45%); losers 6
  Q4 dist med +9.3 sigma: flagged 36/64 against (56%), unflagged 73/134 (54%); losers 5
```
