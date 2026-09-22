# C8-market-calm -- ALTERNATIVE-EXPLANATION verifier -- VERDICT: WEAKENED (complete)

**Short version.** The market half holds: my own tape read reproduces 09_market's numbers and 09-15..18
stays the calmest stretch after controlling for weekday, hour and coin. The "our luck" half is
overstated by a selection artefact: counted by the price the bot DECIDED at, 09-15..18 had 3 losing
markets where 4.8 were expected (P = 0.29), not 1 where 4 were expected (~8%). The "what changed is
margin and size" half is true arithmetic against 09-08..14 (same share of contracts lost, 0.87c less
margin, worth ~$109 over 09-19..22), but it is not the only explanation that fits: 09-19..22's
-$109.45 is two 09-19 closes (a since-fixed bug and a double false-alarm hedge under a since-changed
rule), either of which alone is the whole loss; the same thin margin made +1.47c a contract on
09-20..22; and the wide margin lost -0.77c a contract on 09-08..11.

Claim under test (09_market.md): the market did not get worse; takers' upset rate at 90c+
in the last 45 s is normal now; 09-15..18 was an unusually calm stretch for everyone
(1 losing market where ~4 were expected, ~8% by luck); what changed is our margin (we buy
more at 98c+) and our size (27 -> 74 contracts a market).

Sources: Kalshi ledger (`results/kalshi_ledger.json` via `pinledger.load_cache/pnl/money`,
847 rows, last settlement 2026-09-22 08:00Z) for money and results; `pinrun-live-*.jsonl`
(124 files) for which side we bought, the price the bot SAW when it decided (`ask_seen`,
or the preceding `signal` price in old logs), leg and seconds-to-close. Own code:
scratchpad `map/verify2/C8-market-calm-alternative/` (`build.py`, `repro.py`, `cut2.py`, ...).
Periods are ET days: A 09-08..14, B 09-15..18, C 09-19..22. 9 crypto series only.

## Cut 1 -- reproduction of the claim's table (ledger + logs): REPRODUCED within one market

| | A 09-08..14 | B 09-15..18 | C 09-19..22 |
|---|---|---|---|
| markets, main leg FILLED at >=90c / main leg lost | 338 / 6 (claim 337 / 7) | 200 / 1 (claim 199 / 1) | 175 / 5 (claim 174 / 5) |
| contracts per market | 26.9 | 62.9 | 74.6 |
| avg fill >=90c | 95.97c | 96.75c | 96.87c |
| win margin net of fee | 3.77c | 3.04c | 2.92c |
| ledger $ (all our markets) | +243.55 | +353.15 | -109.45 |
| main leg before hedges $ | +200.53 | +348.45 | -50.60 |
| hedge legs $ | +43.03 | +4.70 | **-58.86** |

With my A count (6 of 338) the claim's own cut gives B expected 3.55, P(<=1) = 0.13, not 0.08.

## Cut 2 -- THE "1 LOSING MARKET" IS A SELECTION ARTEFACT (conditioning on fill price)

The claim buckets markets by the price we were FILLED at. When an index crosses the strike
between our decision and our fill, the book collapses and our buy fills far below what the bot
saw. Those markets are exactly the upsets, and the fill-price cut throws them out.
B's two real losses:
- BTC 09-17 21:15 ET: bot saw 97.8c at 38 s, 99 contracts FILLED AT 53c, lost (hedged, ledger -$27.87).
- DOGE 09-18 00:15 ET: bot saw 97.6c at 32 s, 34 contracts FILLED AT 11c, lost (hedged, ledger +$4.36).
The one loss the claim does count (BNB 09-16 12:30) is a ONE-contract market (-$0.47).

By the price the bot decided at (>=90c):

| | markets | main leg lost | B expected at A's rate | P(B this low by luck) |
|---|---|---|---|---|
| A | 338 | 8 | | |
| B | 202 | 3 | 4.78 | **0.29** |
| C | 174 | 5 | | |
| B, >=5 contracts only | 189 | 2 | 4.85 | 0.14 |

So for OUR fills, 09-15..18 was not a 1-in-12 streak; by decision price it is roughly 1 in 3.5
(1 in 7 if the 1-contract market is dropped).

Why B's losses were so cheap: its two real losses were filled INTO the collapse (53c and 11c
fills on 97.8c / 97.6c decisions) and hedged within 2 s, so B lost $59.10 on main legs
(44c per losing contract) against C's $442.84 (96c per losing contract). B's good result is as
much "the few upsets happened in a cheap way" as "few upsets".

## Cut 3 -- per contract, decision price >= 90c (ledger + logs)

| | markets / lost | ctr/mkt | win margin | share of contracts lost | cost per lost ctr | main leg c/ctr | ledger c/ctr | ledger $ |
|---|---|---|---|---|---|---|---|---|
| A 09-08..14 | 338 / 8 | 26 | 3.75c | 3.05% | 93.7c | +0.78c | +1.27c | +112.50 |
| B 09-15..18 | 202 / 3 | 63 | 3.14c | 1.06% | 44.2c | +2.64c | +2.68c | +338.91 |
| C 09-19..22 | 174 / 5 | 74 | 2.88c | 3.11% | 96.1c | -0.19c | -0.65c | -83.60 |
| C, 09-19 only | 71 / 3 | 93 | 2.80c | 4.01% | 97.0c | -1.21c | -2.68c | -176.29 |
| C, 09-20..22 | 103 / 2 | 61 | 2.97c | 2.16% | 94.3c | +0.87c | +1.47c | +92.69 |

Loss-count differences are all noise (one-sided Fisher): C 5/174 vs B 3/202 p = 0.28; C vs A p = 0.47;
A vs B p = 0.36; 09-19 alone 3/71 vs B p = 0.18.

**This SUPPORTS the margin half of the claim against A**: A and C lost the same share of contracts
(3.05% vs 3.11%); the ~1c/contract gap between them is almost exactly the 0.87c margin gap.
C at A's margin: +$108.90 on 12,496 winning contracts, turning C's >=90c ledger from -$83.60 to
+$25.30. The margin change A->C is -0.87c = -0.61c from buying at higher prices (90-95c share of
contracts 26.6% -> 11.2%; 97c+ 47.8% -> 65.7%) and -0.26c from paying more inside the same band.
"We buy more at 98c+" is only part of it -- the biggest move is out of 90-95c into 97-98c.

**It does NOT hold against B**, the period the operator remembers as "consistent money": B->C
margin moved only 0.26c (worth ~$32 over C) and size 63 -> 74. The B->C swing
(+$353 -> -$109 ledger) is loss dollars and hedges, not margin.

## Cut 4 -- a few big closes (leave one out), ledger $ by close

| period | total | drop worst close | drop 2nd worst | drop both |
|---|---|---|---|---|
| A | +243.55 | +296.15 | +277.81 | |
| B | +353.15 | +368.94 | +365.29 | |
| C | -109.45 | **-0.59** (09-19 23:45 HYPE+XRP) | **-1.50** (09-19 16:00 BTC) | **+107.36** |

A and B keep their sign; C's loss is two closes, both on 09-19, each alone ~all of it.
- 09-19 23:45 ET: HYPE and XRP main legs WON (+$8.01), both fully hedged on a false alarm,
  hedge legs -$116.87, ledger -$108.86. The claim's "losing market" count never sees this (main leg won).
- 09-19 16:00 ET: BTC 110 contracts at 98c, no hedge attempted (loss-cap pause skipped the hedge pass,
  a bug fixed that day), -$107.95.

## Cut 5 -- the since-fixed 09-19 bugs (memory a-gate-must-never-block-a-hedge + logs)

Three of C's six main-leg losses had their hedge blocked by code shipped 09-18/19 and fixed 09-19:
BNB 01:45 (-$57.76, --hedge-price refused a 21c hedge; decision 85c, filled 75c), BTC 02:00 (-$66.34,
loop crash), BTC 16:00 (-$107.95, loss-cap pause). Together -$232.05. C without them: +$122.60.
Fair counterfactual (hedged at the project's measured 57c vs 86c naked): C = -$31.21, i.e. the bugs
cost ~$78 of C's -$109.

## Cut 6 -- hedges

| | hedged mkts | false alarms: n, hedge $ | real saves: n, hedge $ |
|---|---|---|---|
| A | 7 | 4, -$11.96 | 3, +$55.45 |
| B | 5 | 2, -$29.82 | 3, +$35.12 |
| C | 6 | 2, **-$116.87** | 4, +$58.69 |

Hedge legs net: A +$43.03, B +$4.70, C -$58.86 -- over half of C's ledger loss is hedge legs,
which the claim's main-leg, >=90c framing leaves out.

## Cut 7 -- size, the deposit, and 09-19

`autosize` in the live logs: bank $555.95 -> $927.62 at 2026-09-19 07:13Z (the $370.44 deposit;
pinxfer), size 63 -> 105-114 contracts for the rest of 09-19. 09-19 averaged 93 contracts a market.
The two worst C closes were 110 and 2x104 contracts. Size cannot flip a sign (C at B's size: -$92.29),
but the 09-19 size was the operator's deposit, not a drift.

## Cut 8 -- time of day, coin, leg (ours)
- ET hour blocks, C: 00-06 2/43 lost -$37; 06-12 0/56 +$113; 12-18 3/39 -$138; 18-24 1/41 -$48.
  B: 1/63, 0/36, 1/51, 1/54, all positive. A: 5/109, 1/80, 1/63, 4/119, all positive. No block
  stands out across periods; n too small (<=5 losses per cell).
- Coin: the same nine coins every day 09-08..21; C's losses BNB 2/23, BTC 2/24, HYPE 1/19, NEAR 1/15.
  Nothing new traded, no coin concentration beyond noise.
- Leg: C early (first buy >30 s) 4/120 lost, -$140.88, -0.69c/ctr main; C late 2/59, +$31.42, +0.24c/ctr.
  B early 2/83 +$83.50; B late 1/121 +$269.65. Same loss rate per market early vs late in C (3.3% vs 3.4%).
- Our 98c+ decision band: A 0/55, B 0/46, **C 2/42** (both early leg, 43-45 s; one is the 110-lot bug).
  The market's 98c+ rate is 0.4-0.7% (09_market), so ~0.2 expected: C's 98c losses are not
  "normal upsets at a thin margin", they are excess at the price where the margin argument says
  losses should be rarest (n = 2, so this too is weak).

Cuts so far: 8 groups, ~40 cells. Multiple-looks bar: with ~40 cells, nominal p < 0.05/40 = 0.00125
for any single cell to count; nothing here reaches it, and no cell has 30 closes of losses.

## Cut 9 -- a fixed loss schedule (is the thinner margin by itself a loss of edge?)

Our pooled (A+B+C) per-market loss rate by decision band: 90-95c 4/118 (3.4%), 95-97c 5/172
(2.9%), 97-98c 5/281 (1.8%), 98c+ 2/143 (1.4%). Applying one schedule to each period's own
price mix and all-in cost: expected main leg A +1.40c/ctr, B +1.47c, C +0.77c. So at OUR pooled
rates the move to dearer prices costs ~0.6c a contract (supports the claim's mechanism); at the
09_market band rates for the whole market it costs nothing (A -0.25c, B +0.20c, C -0.24c). Our
band rates rest on 2-5 losses each, so this cut cannot settle it either way.

## Cut 10 -- the 09-19 23:45 double false alarm under today's hedge rule

HYPE: alarm at belief 0.44 (threshold 0.60), hedged all 104 at 46c, -$49.65 hedge leg. XRP: panic
at belief 0.27, hedged all 104 at 63c, -$67.22. Under A76 as deployed now (all at <=20% belief, half
at <=40%, none above) HYPE would not have hedged and XRP would have hedged half: roughly $80 of the
$117 would not have been spent (arithmetic on the logged beliefs, not a replay). This rule has
changed since, so part of C's loss is also a since-changed setting.

## Cut 11 -- same weekdays, our fills (decision >= 90c, ledger)

| days | margin era | markets / lost | ledger $ | ledger c/ctr |
|---|---|---|---|---|
| Tue-Fri 09-08..11 | wide (A) | 153 / 4 | **-$19.51** | **-0.77c** |
| Sat-Mon 09-12..14 | wide (A) | 185 / 4 | +$132.01 | +2.08c |
| Tue-Fri 09-15..18 | thin (B) | 202 / 3 | +$338.91 | +2.68c |
| Sat-Mon 09-19..21 | thin (C) | 170 / 5 | -$89.08 | -0.70c |

At the WIDE margin the bot already had a losing four-day stretch (09-08..11, -0.77c a contract,
at 11-19 contracts a market so only -$19.51). Four-day windows swing between -0.8c and +2.7c a
contract whatever the margin; the margin change (0.87c) is about half of that swing. A 3-4 day
window cannot show that the margin is what turned the bot negative.

## Cuts 12-16 -- the tape (what the MARKET did; never our loss rate)

Own scanner `tape.py`/`tape2.py` (zcat|grep one UTC hour at a time, ~30 MB RAM), outcomes from
market_lifecycle_v2 `determined` events (17,064) plus `C:\kals\fulltape\markets.json` (6,990 more);
7,406 overlap, **0 disagree**. Unit: `yes_price_dollars`/`no_price_dollars`, dollars, decided once.
Definition as the claim: a market-side counts if a taker bought that side in the band inside the
last 45 s; did it lose. n = closes, 95% intervals by resampling closes.
Gaps: zcat read nothing for 09-09 14-20Z, 09-10 07-08Z, 09-15 14Z and 20Z, 09-17 07-08Z (broken gzip
members, not salvaged) and 09-22 01-04Z (outage). 7 market-sides on 09-09 had no result.

**12. Reproduction (per market-side):**

| | 09-01..07 | A 09-08..14 | B 09-15..18 | C 09-19..22 |
|---|---|---|---|---|
| 90-97.9c lost | 8.07% [6.6, 9.5] | 6.64% [5.3, 8.2] | 4.82% [3.0, 6.7] | 6.01% [4.0, 8.2] |
| 98c+ lost | 0.65% [0.3, 1.1] | 0.71% [0.4, 1.2] | 0.39% [0.1, 0.7] | 0.67% [0.3, 1.1] |
| closes (90-97.9 / 98+) | 438 / 616 | 448 / 577 | 237 / 354 | 201 / 281 |

Claim: 8.45 / 6.64 / 4.80 / 6.15 and 0.67 / 0.71 / 0.38 / 0.69. Reproduced.

**13. Per day (90-97.9c):** B = 09-15 7.8%, **09-16 2.3%, 09-17 3.0%**, 09-18 5.3%. The calm is two
days. Other single calm days: 09-10 3.8%, 09-12 3.5%.

**14. Rolling 4-day windows (18, overlapping):** B is rank 2 of 18 at 90-97.9c (lowest is 09-16..19,
4.44%) and rank 1 at 98c+.

**15. Standardised to the pooled ET-hour-block x coin mix:** B 4.56% (raw 4.82%), C 5.67% (raw 6.28%),
A 6.67%, 09-01..07 8.00%; 98c+: B 0.38%, C 0.71%, A 0.71%. Hour and coin mix do not explain the calm.

**16. Same weekdays:** Tue-Fri 09-01..04 8.74%, 09-08..11 6.82%, **B 4.82%**; Sat-Mon 09-05..07 7.31%,
09-12..14 6.46%, **C 6.28%**. 98c+: Tue-Fri 0.83 / 1.05 / **0.39%**; Sat-Mon 0.46 / 0.40 / **0.70%**.
B is the calmest Tue-Fri; C is ordinary for Sat-Mon at 90-97.9c and at the top of the Sat-Mon range at 98c+.

So the tape supports "09-15..18 was calm for everyone" (suggestive, intervals overlap, as 09_market says)
and "09-19..22 is normal". The "normal" level itself drifts: 8.1% -> 6.6% -> 4.8% -> 6.0%.

**Our calm is what the market's calm predicts.** B's market rate was 0.73x A's (90-97.9c) and 0.55x
(98c+). Our A rate (8/338 by decision price) scaled by that gives ~3.3 expected losing markets in B;
we had 3. Nothing extra to explain.

**Ours vs the market, same band and days:** 90-97.9c, ours per market / market per market-side:
A 2.83% / 6.64% (0.43x), B 1.92% / 4.82% (0.40x), C 2.27% / 6.01% (0.38x) -- our selection relative to
the market did not degrade. 98c+: A 0/55, B 0/46, **C 2/42** against the market's 0.67% (0.28
expected, P(>=2) = 0.03 nominal): the only cell where we lost more than the market, and it is the
band where the margin argument says losses matter least. Does not survive the multiple-looks bar.

## Multiple looks

16 cuts, about 150 cells (periods x bands x legs x hour blocks x coins x days x windows). Bonferroni
bar: p < 0.05/150 = 0.0003. Nothing reaches it. The smallest nominal p is C's 98c+ 2/42 (0.03).
No cell has 30 losing closes; every loss-count comparison here rests on 2-8 losses.

## What the evidence supports instead

1. Market: the whole market's upset rate at 90c+ in the last 45 s was lowest on 09-15..18 and is at its
   ordinary level on 09-19..22 (my own tape read, weekday/hour/coin controlled). CONFIRMED.
2. Us on 09-15..18: 3 losing markets of 202 by the price we decided at (4.8 expected, P = 0.29), exactly
   what the market's calm predicts. What made that stretch pay was as much that two of its three losses
   filled INTO the collapse (53c and 11c) and were hedged at once -- $59 of main-leg losses at 44c a
   losing contract, against 94-96c in the other periods. The claim's "1 loss, ~8% luck" is an artefact
   of bucketing by fill price. WEAKENED.
3. Margin: against 09-08..14 the margin fell 0.87c (0.61c from buying at dearer prices, mostly out of
   90-95c into 97-98c; 0.26c from paying more at the same decision price), at an identical share of
   contracts lost (3.05% vs 3.11%); worth ~$109 over 09-19..22 at ~12,500 winning contracts. REAL.
   Against 09-15..18 it fell only 0.26c (~$32). Size multiplies whatever sign there is; 09-19's
   93-contract average was the $370.44 deposit, not drift.
4. The 09-19..22 loss (-$109.45) has at least three explanations of the same size, each alone enough:
   margin vs A (~$109); the 09-19 bugs that blocked three hedges (~$78 at the measured 57c-vs-86c hedge
   saving, $232 upper bound); the 09-19 23:45 double false-alarm hedge (-$117 of hedge legs on two
   winning markets, ~$80 of it avoidable under today's A76 rule). Drop either of the two worst closes
   and C is flat (-$0.59 / -$1.50). The post-fix days 09-20..22 made +1.47c a contract at the thin
   margin, and the wide-margin days 09-08..11 lost -0.77c. So "what changed is our margin and size" is
   one sufficient cause among several, not a demonstrated one.

Resources: python stayed under ~40 MB; free RAM 1.49-1.86 GB throughout; `kalshi_collector.py`
(pid 105304) and `crypto_feeds.py` (pid 105352) alive at the end. No process touched.
