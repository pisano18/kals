# 09 market-and-competition -- COMPLETE (2026-09-22, ~09:20Z)

Question: separate what WE changed from what the MARKET changed.

**Answer: the market did not get worse than normal. It stopped being unusually
kind, and our margin had thinned.**
- The whole market's rate of upsets (a >=90c buy that loses) on 09-19..22 is its
  normal rate. The four days before, 09-15..18, were the calmest stretch in the
  sample, for everyone.
- The bot's "consistent money" on 09-15..18 came from almost nothing going wrong:
  1 losing market out of 199 bought at >=90c, against 7 of 337 the week before
  (about a 1-in-12 streak of luck).
- Meanwhile WE thinned the margin. What a winning contract pays went from 3.76c
  (09-08..14) to 3.05c (09-15..18) to 2.93c (09-19..22), because we paid more per
  contract. The market's prices did not move.
- WE also doubled the contracts per market, 27 to 63 to 74. When upsets returned to
  normal on 09-19, the thin margin and the big size together turned the bot negative.
- Supply did not shrink, competitors did not start earlier, and no new large player
  showed up. 09-19 volatility was normal; 09-21 was high, but its late strike
  crossings were normal.

Method (fixed before looking at 09-18+):
- Tape = every taker buy on the 9 live crypto series (BTC ETH SOL XRP DOGE BNB ZEC
  HYPE NEAR; ADA/BCH/TON list no markets) inside the last 90 s, 2026-09-01 00Z ..
  09-22 06Z, streamed one UTC hour at a time (`scan.py`, ~60 MB RAM).
- Outcome = Kalshi's result (ledger, then the tape's `determined` event). 215 markets
  use the index settlement instead. It agrees with Kalshi 16,935 of 16,948 times,
  and my strike (previous settle) matches Kalshi's floor_strike to a median 6e-7.
- Market loss rate = per market-side: "a taker bought this side at this price
  inside 45 s; did that side lose?" n = closes; intervals = bootstrap over closes
  (95%). Contract-weighted versions are in `agg2.log`, but >=1000-lot orders carry
  70% of contracts there, so the per-market-side numbers are the ones to trust.
- Ex-us = tape minus our main-leg fills (from the live logs). Join check: 97.7% of
  our >=90c contracts show on the tape within +-2 s.
- The tape is used ONLY for what the market did. Our loss rates come from our live
  fills and Kalshi's ledger (`results/kalshi_ledger.json` via `pinledger`).
- Price unit fixed once on the whole extract: max taker price 999 milli-dollars.
- Scripts and outputs: scratchpad `map/09/` (`scan.py`, `agg2.py`..`agg5.py`,
  `agg_idx.py`, `agg_book.py`, `ourper.py`, `be.py`, `losers.py`, `*.log`).

## 1. Findings, ranked by dollars

### F1. The margin thinned while the market was calm; normal upsets then made it negative
- **Claim.** The bot is paying more per contract than it did in its first week, so a
  win pays less. On 09-15..18 that was hidden because almost nothing lost, for us
  and for the market. From 09-19 upsets returned to the market's normal rate, and
  at the thinner margin and bigger size that is a loss.
- **Evidence -- ours (live fills + Kalshi results, main leg >=90c, before hedges):**

  | | 09-08..14 | 09-15..18 | 09-19..22 |
  |---|---|---|---|
  | markets / lost | 337 / 7 | 199 / **1** | 174 / 5 |
  | contracts per market (all prices) | 27 | 63 | 74 |
  | avg price paid | 95.97c | 96.73c | 96.86c |
  | a winning contract pays (= break-even loss share) | **3.76c** | **3.05c** | **2.93c** |
  | share of contracts that lost | 2.58% | 0.01% | **3.10%** |
  | ledger, all our markets | +$243.57 (7 days) | +$353 (4 days) | -$109.51 (3.3 days) |

  At 09-08..14's loss share (2.58%) and today's margin (2.93c), the bot nets about
  +0.35c a contract, roughly $0.26 a market before hedges. At that week's margin
  (3.76c) it would net about +1.2c. The 09-15..18 run (1 losing market in 199, where about 4 were
  expected at the earlier 7-in-337 rate) has about an 8% chance of happening by luck.
  B vs 09-15..18 loss counts: 6/178 vs 3/203 over all our markets, one-sided p = 0.19.
- **Evidence -- the market (tape, per market-side, inside 45 s):**

  | | 09-01..07 | 09-08..14 | **09-15..18** | 09-19..22 | median day 09-01..18 |
  |---|---|---|---|---|---|
  | 90-97.9c lost | 8.45% [6.9, 10.0] | 6.64% [5.3, 8.1] | **4.80% [3.1, 6.5]** | 6.15% [4.1, 8.3] | 6.88% |
  | 98c+ lost | 0.67% [0.4, 1.1] | 0.71% [0.3, 1.2] | **0.38% [0.1, 0.7]** | 0.69% [0.3, 1.1] | 0.45% |
  | closes (90-97.9c / 98c+) | 423 / 595 | 448 / 577 | 238 / 357 | 195 / 272 | 18 days |

  09-19..22 sits at the normal level. 09-15..18 was the calmest stretch in the
  sample (about 30-45% fewer upsets than usual); the intervals overlap, so that part
  is suggestive, not proven.
- **Price: ours rose, the market's did not (tape, last 45 s).** The market's average
  price in the 90-97.9c band was 94.5-95.5c every day 09-01..22. The share of
  90-99.9c contracts traded at 98c+ was 80-90% every day. Ours at 98c+: 9-14% of
  contracts on 09-09..16, then 17-27% on 09-17..21.
- **Mechanism.** A contract bought at p pays (1 - p - fee) if it wins and costs
  (p + fee) if it loses, so the loss share that breaks even is exactly the win
  margin. Moving from 96.0c to 96.9c cut the loss share we can survive from 3.8% to
  2.9%. Size does not change that ratio, but it multiplies every dollar: one loss at
  74 contracts x 97c is about $72 before hedging.
- **Confidence:** high on the margin arithmetic and on the market's price mix; high
  that the market was not worse than normal on 09-19..22; medium that 09-15..18 was
  unusually calm.
- **Artefact check:** hedges are excluded from the before-hedge columns; the ledger
  row includes them. Why our price rose from 09-15 is a settings question, which
  investigators 01/05 map to versions. The market's own price mix rules out "the
  offers got dearer".

### F2. The 31-45 s leg lost money on the same days the late leg made money (-$57.38 vs +$139.59 since 09-17)
- **Claim.** Since the early leg started (09-17), markets we bought first at 31-45 s
  lost money, while markets we bought at <=30 s on the same days made money. Four
  of our six losses since 09-19 were early-leg buys, and in each one the index
  crossed the strike 2-10 s after we bought.
- **Evidence (live fills + ledger, 9 crypto series, 09-17..22 ET):**

  | first buy | markets | lost | ledger $ | $ per market | contracts per market | avg price |
  |---|---|---|---|---|---|---|
  | 31-45 s, 09-17..18 | 83 | 2 | +$83.50 | +$1.01 | 50 | 95.49c |
  | 31-45 s, 09-19..22 | 120 | 4 | **-$140.88** | -$1.17 | 73 | 96.91c |
  | <=30 s, 09-17..18 | 40 | 0 | +$108.22 | +$2.71 | 77 | 96.22c |
  | <=30 s, 09-19..22 | 58 | 2 | +$31.37 | +$0.54 | 78 | 95.94c |

  The early leg is 56-76% of our markets on every day since 09-17 (0% before).
  Its fills were not cheaper: 97.51c on 09-17/18 and 96.91c after, against 96.37c
  for 11-30 s fills before 09-17. Our 11-30 s fills fell from ~37 a day (09-08..16)
  to ~17 a day (09-19..22), while the tape's late supply did not fall (F3).
- **Our losing markets since 09-19 (ET):** BTC 02:00 09-19, 94.4c at 35 s, -$66.34;
  BTC 16:00 09-19, 98.0c at 45 s, 110 contracts, **-$107.95**; NEAR 12:45 09-21,
  91.1c at 44 s, -$59.09; HYPE 18:15 09-21, 98.0c at 43 s, -$31.27. These four are
  the early leg, -$264.65 together; the last strike crossings came at 43, 42, 35 and
  28 s out. The other two: BNB 01:45 09-19, 75c at 24 s, -$57.76, and BNB 12:30 09-19,
  97.3c at 23 s, -$61.75. In NEAR 09-21 other takers bought only 51 contracts
  at >=90c on our side in the whole last 45 s, against our 81.
- **The window itself is not worse for the market.** At a given price, the market
  loses about as often at 31-50 s as at 11-30 s; only the last 10 s is clearly safer:

  | price, 09-01..18 | 0-10 s | 11-20 s | 21-30 s | 31-40 s | 41-50 s |
  |---|---|---|---|---|---|
  | 90-96.4c | 3.0% | 7.4% | 7.4% | 7.6% | 7.5% |
  | 96.5-97.9c | 1.3% | 2.5% | 2.3% | 3.3% | 2.4% |
  | 98c+ | 0.20% | 0.42% | 0.39% | 0.41% | 0.47% |

  (262-1562 closes per cell; the 09-19..22 cells are in `agg3.log` and are no worse.)
  So the early leg's losses are OURS: which markets our model picks at 45 s, what
  we pay there, and the full-size bets sitting there. They are not something the
  whole market suffers in that window. On 98c early buys we lost 2 of 25 markets
  on 09-19..22 against 0 of 21 before (p = 0.29). The market loses 0.4-0.6% there.
- **Confidence:** high on the dollars and the mix; low that the early-vs-late gap is
  more than luck plus size (6/203 vs 2/98 lost markets). Whether the early leg takes
  markets the late leg would have bought better is not measured.

### F3. Supply did not shrink and competitors did not move earlier (tape)
- 90-97.9c contracts traded per close inside 60 s, by weekday (three weeks, oldest
  first): Mon 16.2k / 16.3k / 18.4k; Tue 15.8k / 17.2k / 21.4k; Wed 16.2k / 19.3k /
  14.1k; Thu 16.0k / 26.6k / 19.8k; Fri 19.6k / 20.8k / 23.5k; **Sat 26.8k / 30.8k /
  20.5k**; Sun 17.0k / 16.4k / 16.9k. Weekdays are flat. Saturday 09-19 was the
  thinnest of the three Saturdays, but still inside the weekday range.
- Median seconds-before-close of 90-97.9c trades: 09-19 40.0 s, 09-20 38.9 s,
  09-21 39.2 s, against 33-47 s on every earlier day. No move earlier. This was the
  premise of the early leg (v-staged, 09-17), and the tape does not support it.
- Our share of 90-97.9c contracts inside 45 s: 0.02-0.09% (09-08..11), 0.07-0.35%
  (09-12..18), 0.45% (09-19), 0.22-0.23% (09-20/21). That is too small to move the
  market or to be crowded out of it. `RESULTS_pickoff.md` says 3-10%, but it counts
  prints and calls itself an upper bound.

### F4. Volatility: 09-19 normal, 09-21 high, late strike crossings normal (index only)
- Realised 1-s index volatility against each coin's 22-day median: 09-19 0.91x,
  09-20 0.96x, **09-21 1.36x, the highest day in the sample** (09-11 1.30x, 09-16 1.26x).
- Markets whose index crossed the strike inside the last 30 s: 09-19 6.5%, 09-21
  6.8%, against 4.4-8.6% on other days.
- Leader >=90% sure at 30 s (index model) and still lost: 09-19 3 of 825 (1.7
  expected), 09-21 2 of 721 (1.2 expected); at 45 s, 5 of 791 and 3 of 691. The bad
  market day in the sample was **09-11** (13 of 836 at 30 s), and our fills that day
  came out at +0.15c a contract.

### F5. No new big participant; order sizes drifted up before our losses (tape)
- Taker orders of >=1000 contracts: 13-19 per close on 09-18..21, against 10-21 on
  09-01..17 (weekends highest). They carry 70-76% of all >=90c contracts every day.
- Median taker order 15-16 contracts (09-12..14), then 20-25 (09-15..21); p90 ~300
  then ~450-485 from 09-16. This started before 09-19 and does not line up with
  our losses.
- Spread on the leading side at 30 s: 0.1c every day. Median ask size there was
  488 on 09-18, then 327 / 259 / 134 on 09-19/20/21 (83-286 earlier).
- Markets with the leader offered at 90-97.9c at 30 s: 3.2-4.4% on 09-17..21 against
  4.0-5.7% on earlier weekdays. Slightly lower, and partly us: since 09-17 we take
  those offers before 30 s.

## 2. Refuted or not supported
- "The market got worse after 09-18": no. Per-market loss rate, per-contract
  taker profit, supply, timing, order sizes, spreads and crossing counts are all at
  normal levels on 09-19..22. The only thing out of line is that 09-15..18 was
  unusually good.
- "Competitors moved earlier and took the cheap offers" (the reason given for the
  early leg): the timing of cheap trades is flat, supply is flat, and our early
  fills were not cheaper.
- "09-19 was a violent day": 0.91x normal volatility, normal crossing count.
- **A tape signal at decision time that flags our losers.** Tested on the 15 s
  before our first send: our side's share of taker contracts (<50% / 50-90% / >=90%),
  whether the other side was bought at >=10c, no trades at all. Split early/late,
  that is 12 cells with 19 losses in total, and nothing separates them.
  Example: late buys with our side <50% had 0 of 171 lost; early buys with our side
  <50% had 4 of 55. Opposite directions, which is what noise looks like.
- **A 98c ceiling on the early leg, on loss-rate grounds.** The market loses only
  0.4-0.6% of 98c+ market-sides at 31-50 s, under the 1.9% break-even. Our own
  2 of 25 is too few to call. The size of a 98c bet is the problem, not the price alone.

## 3. Could not measure, and why
- 2026-09-22 01:00-04:59Z: no trade/ticker tape (the Kalshi connection outage).
- Early September: collector restarts inside an hour break gzip members, and those
  lines are lost (read with `gzsalvage`). 09-02 has 16k trades with no result.
- Whether the early leg displaced a later, cheaper buy in the same market: the bot
  does not log the late signal it would have sent.
- Who the counterparties are: the Kalshi tape has no participant IDs. Order size
  is the only proxy.

## 4. Solutions worth testing
1. **Win the margin back before anything else.** At the normal upset rate the bot
   needs about 3.8c a winning contract (what it had on 09-08..14); it now gets 2.9c.
   Find which settings raised our average price from 96.0c to 96.9c (the market's
   did not move) and test undoing them one at a time in a synced paper arm (valid
   from 2026-09-22 06:21Z). Promote on LIVE fills only. The bar: win margin per
   contract above the contract loss share, over at least 150 markets that include
   normal-upset days, not a 09-15..18-style calm stretch. **Blocks:** entries above a
   price. It must be written so it cannot touch hedge orders.
2. **Size the early leg by what it has earned.** Since 09-17 it is -$0.28 a market
   against +$1.42 for the late leg on the same days. Test `--early-frac 0.333` (the
   v-early49 setting) and compare early-leg dollars per market on LIVE fills over at
   least 100 early markets. **Blocks:** contracts on 31-45 s entries only, never hedges.
3. **A daily market-health line, so the next bad day is labelled in minutes.** From
   the tape: per-market-side loss rate at 90-97.9c and 98c+ inside 45 s, next to the
   median of every earlier day (the baseline rule); cheap supply per close; share
   of markets with a late strike crossing; volatility ratio. The code exists in
   scratchpad `map/09/` (`scan.py`, `agg5.py`, `agg_idx.py`). The tape is valid here
   because this measures the market, not us. **Blocks:** nothing (read-only).
4. **The market's own edge is in the last 10 s.** 90-96.4c buyers there lose 3.0% of
   market-sides against 7.4% at 11-50 s. We had 59 such markets before 09-19 (0 lost,
   +5.7c a contract at 90-96c) and only 10 since. Worth a synced paper arm that
   favours 0-10 s entries, validated on live fills only after it matches live.
   **Blocks:** entries at 11-45 s in that arm, never hedges.
