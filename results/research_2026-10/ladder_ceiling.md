REPORT.md was not written: this harness doesn't allow subagents to write report .md files. The full report follows. Script outputs are in `C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\b2dbb5c1-92b0-452a-b1e9-86b7402d3a34\scratchpad\final\ladder_upside\ceiling\` (`live_out.txt`, `calib_out.txt`, `q2_out.txt`, plus their JSONs). Fresh Kalshi pulls (GET only, subaccount 1, taken 10-10 about 02:10Z) are in `sub1_settlements_now.json` and `sub1_fills_now.json`.

# TASK B: the ladder's real capital ceiling

## Bottom line
- **Size is what limits the ladder, not sellers.** When a seller hits our 5-contract bid, they almost always take all 5 and keep selling below 98c.
- In the markets where our ladder got filled, the tape shows this much sold below 98c (capped at 200 per market):
  - median 124 contracts per market;
  - 66% of those markets had 50 or more;
  - 37% had 200 or more.
- Our own median fill was 5.
- More size gets more contracts from the same seller events. It does not add more events.
- Calibrated against live fills, the ladder as it is (auto-size, all 9 coins, at most 2 bids per market):

| pot | size per bid | $/day (low–high) | middle |
|---|---|---|---|
| $350 | 25 | $4.2–6.5 | about $5.3 (1.5% of pot a day) |
| $700 | 50 | $8.1–11.8 | about $9.9 (1.4%) |
| $1,400 | 100 | $15.3–20.0 | about $17.6 (1.3%) |

- Today it makes about $1.3/day on $80, which is 1.6% of the pot a day.
- **Nothing has run live above 5 contracts a bid.**
- Supply is falling: about 12–13% per 5 days on the tape and about 22% live.

## Live evidence (Kalshi subaccount 1, 09-28 to 10-09 about 17:15 ET)
- **Overall:** 131 filled markets, 0 lost, +$14.87 on $723.01 bet (+2.06%).
  - 738 contracts, all filled as maker; fees $0.0002 in total.
  - Every Kalshi fill matches an order in the bot's log, so the reconciliation is exact.
- **(1) Filled contracts vs bid size.**
  - 10-03 onward (size 5, at most 2 bids per market), 79 filled markets: 63 filled exactly one bid, 5 part of a bid, 10 hit the 2-bid cap, and 1 went over the cap (the known capfix bug).
  - 86 of 91 filled bids (94.5%) filled completely.
  - 09-30 to 10-03 (no cap): 56 of 56 filled bids filled completely.
  - The second bid usually goes unfilled because the seller's sweep is one event, over within about a second. Whatever size is resting at that moment is what we get.
- **(2) Queue ahead of us at 98c** (median 58 contracts; 3 in 4 bids had 232 or fewer ahead, 9 in 10 had 656 or fewer):

  | contracts ahead | bids | share filled |
  |---|---|---|
  | 0 | 1,558 | 6.6% |
  | 1–50 | 3,116 | 1.3% |
  | 50–200 | 2,534 | 0.59% |
  | 200–1,000 | 2,058 | 0.24% |
  | over 1,000 | 700 | 0.14% |

  - 112 of the 131 filled markets came from a bid with nobody ahead of it.
  - The share of our bids that were first in line fell from 20–22% (09-30, 10-01) to 12–15% (10-03 to 10-09).
  - When we were first in line, the fill rate fell from 10–13% to about 5%.
  - Size doesn't change our queue place. A 98.1c price would jump the 98.0c queue; the tape says that is worth about +7% at 50 contracts.
- **(3) The rule rested a bid but nothing filled** in 9,005 of 9,136 markets (98.6%).
  - Unfilled bids rested a median 24.7 s; 9,661 of 9,802 were cancelled at the close.
  - In 0 of those 9,005 markets did a seller sell below our price after we placed, so no seller ever traded past us.
  - Fill rate by coin: NEAR 4.1%, ZEC 2.6%, XRP 1.8%, BTC 0.5%, ETH 0.4%. NEAR, ZEC and XRP made 72% of the money.
  - Fills come a median 6.6 s before the close and 1.6 s after our first bid in that market. Sellers arrive the moment a market is decided, so speed matters.
- **(4) Money by ET day (size 5):**

  | ET day | 10-01 | 10-02 | 10-03 | 10-04 | 10-05 | 10-06 | 10-07 | 10-08 | 10-09 (partial) |
  |---|---|---|---|---|---|---|---|---|---|
  | $ | 2.52 | 1.10 | 1.18 | 1.60 | 1.60 | 1.24 | 1.31 | 1.22 | 0.90 |

  - The first 4 days averaged $1.60/day (80 contracts a day); the last 5 averaged $1.25/day (62 contracts a day).
  - Filled markets run about 11.6 a day.

## Reconciling with the design study (tape = supply evidence, never our loss rate)
I reused the verifier's independent fill model and data extracts. They count only volume sold strictly below our price, with no refill, and end 10-08 09:30Z.
- **Calibration on the same live-bid markets, size-5 period:**
  - Live 571 contracts in 97 markets.
  - Model at 0.3 s order timing: 442 contracts at size 5 (live is 1.29x) and 864 at size 10 (live is 0.66x).
  - Model at 1.0 s timing: live is 1.65x at size 5 and 0.85x at size 10.
  - Filled markets match well: 87 filled in both, 10 live only, 3 model only.
  - The live bot, with refills up to 2 bids, catches about two-thirds of what one resting 10-lot would.
- **Model $/day, all 9 coins at 98c:**

  | contracts per market | 25 | 50 | 100 | 200 |
  |---|---|---|---|---|
  | all 10 full days, 0.3 s | $5.67 | $10.52 | $19.07 | $32.17 |
  | last 5 full days (10-03 to 10-07), 0.3 s | $5.21 | $9.77 | $17.84 | $30.28 |
  | last 5 full days, 1.0 s | $4.19 | $8.11 | $15.25 | $26.54 |

  - The design study's numbers on the same tape (25 → $5.56, 50 → $10.29) reproduce within about 2%.
  - The design's $12.5–17/day needs coin weighting (most money on NEAR/ZEC/XRP, about +$4.8/day at the same capital per the verifier), the 98.1c/97.1c prices, and the older, richer days. It also needs a pot of about $700, because of the rule that at most 70% of the pot can be bid or held at once.
- **How the range is built:** low = the 1.0 s model at one bid of size S; high = 0.66 × the 0.3 s model at 2S. At size 5 this gives $0.87–1.44, and live actually made $1.39 over 10-03 to 10-07.

## Per pot: income, cost of one loss, live markets needed

| pot (new money) | $/day low–mid–high | one losing market (full 2 bids / 1 bid) | worst single close (70% rail) | break-even losses per 100 filled markets | clean filled markets needed (95%, 0 losses) |
|---|---|---|---|---|---|
| today $80, size 5 | about $1.3 (live) | $9.80 / $4.90 | $56 | 1.13 | about 264 |
| $350 (+$270), size 25 | 4.2 – 5.3 – 6.5 | $49 (about 9 days of income) / $24.50 | $245 | 0.94 | about 320 |
| $700 (+$620), size 50 | 8.1 – 9.9 – 11.8 | $98 (about 10 days) / $49 | $490 | 0.87 | about 340 |
| $1,400 (+$1,320), size 100 | 15.3 – 17.6 – 20.0 | $196 (about 11 days) / $98 | $980 | 0.78 | about 385 |

- **Today:** 0 losses in 131 filled markets. With 95% confidence the true rate is under 2.26 per 100, which is still above every break-even line above. The live record alone cannot yet show the ladder beats break-even, even at today's size.
- **Why it's believed safe today:** the price-index check found the rule wrong in 1 market out of 24,553, and a bid there would not have filled. That is evidence about the rule, not a loss rate from our fills.
- **Filled markets at any size count toward the loss evidence.** The set of filled markets doesn't change with size; only contracts per market do. A loss is priced as filling the full 2 bids.
- **Stage reads (the bar already written for the maker stage):**
  - each step needs at least 60 filled markets AND at least 7 ET days;
  - live contracts at least 70% of the tape model on the same closes and size;
  - 0 losses;
  - at least +1% of the pot a day: $3.50 at $350, $7 at $700, $14 at $1,400.
- **Stage timing:** 7 days per step is the binding limit, about 3 weeks for all three steps. That ends near 131 + 21 × 11.6 ≈ 375 clean filled markets, roughly what the $1,400 step needs.
- All three steps pass the money bar at the middle estimate. At $1,400 the low case is only 9% above it.

## What cannot be known yet
1. Whether sellers keep selling into a 25–100 contract bid at 98c. The tape shows what they sold against other people's bids. Only live size steps can measure this.
2. Whether competing bids at 98c and above keep growing.
3. The true loss rate, and whether losses come in clusters (several coins wrong at one close).
4. Whether supply keeps falling. At the recent pace, the estimates above could be 30–50% lower by the time the $1,400 step is read.

## Check-ins
- Every process stayed under about 60 MB. I streamed the 156 MB ladder log line by line and never touched `orderbook_delta`.
- Both recorders are alive: kalshi_collector (pid 2532788) and crypto_feeds (pid 105352).
- 16.4 GB free disk, 1.08 GB free RAM.