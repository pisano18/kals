# What the safe bot turned down -- first missed-trades report (09-28)

Window: 09-27 1:08 AM ET (first safe-build run) to 09-28 10:18 AM ET, 1.4 days.
Tool: `python research/missed.py` (new; daily from now on; `--all` for this window).
Full per-gate output: `results/SAFE0928_missed_run.md`.

## The answer

**Nothing the safe bot turned down is proof it is leaving safe money behind.** Over 1.4
days its safety rules turned away 579 markets we never bought. Using each market's final
result, 578 would have won and 1 would have lost (a 1-contract hourly BTC bet, -$0.93). The
most those buys could have made is **+$101, about $73 a day**. For comparison, we really made
**+$36.79** on the 15-minute coins (37 markets, 1 lost) plus +$3.98 on the coin race.

Why that +$101 is not money waiting for us:
- It is almost all offers at 99c and up. At 99c a win pays about 1c a contract, while a loss
  costs about 99c. So these buys only pay if they lose fewer than about 1 time in 100.
- Our real fills at 97c and up lost about 3 contracts in 100 (WHY_NO_MONEY 09-27). The
  market result counts everyone's offers. Ours are the ones someone chose to sell us, and
  those lose far more often (0.11% on paper against 3.4% live on 09-11). So the "would have
  won" counts overstate what we would have kept.
- Each rule's upper-bound cost equals one or two of our typical losses (table). One bad fill
  cancels it.

**Found while doing this: the ceiling change broke the live hourly BTC test.** Since 09-27
3:05 AM ET, all 3 hourly BTC orders were rejected by Kalshi as "invalid price". Before the
change, 9 of 10 filled. The bot now sends a 97.8c limit, and hourly markets seem to trade only
in whole cents. I have not confirmed the cause with Kalshi. The money lost is tiny ($0.18 at
most), but the hourly live test has measured nothing for about 31 hours.

## Per rule (1.4 days, distinct markets; "most it cost" = wins at the price refused, losses at full cost)

| rule | markets refused | bought anyway (all won) | never bought: would have won / lost | typical price | most it cost us | one loss like these costs |
|---|---|---|---|---|---|---|
| price ceiling (nothing over 97.8c) | 236 | 24 | 212 / 0 | 99.0c | +$55.26 | $29 |
| -- of which 97.9-98.0c (the 09-27 change) | 18 | 4 | 14 / 0 | 98.0c | +$10.22 | $38 |
| seller gate (fresh offer, sellers dumping our side) | 10 | 1 | 8 / 1 | 97.4c | +$5.05 net | $27 |
| one full bet per coin | 8 | 8 (all held already) | -- | -- | extra second bets: +$23.49 (8 of 8 won) | ~$85 |
| 45-second leg floor (under 95c) | 4 | 0 | 4 / 0 | 94.6c | +$9.12 | $27 |
| edge floor (profit under 0.3c) | 552 | 26 | 526 / 0 | 99.9c | +$36.94 | $36 |
| depth (too few offered) | 165 | 13 | 152 / 0 | 99.9c | +$31.26 | $59 |
| spike (confidence jumped in 1 s) | 8 | 2 | 6 / 0 | 98.8c | +$3.64 | $54 |
| jump against / thin against / dump guard / edge cap | 12 / 10 / 3 / 1 | 5 total | 20 / 1 | 83-99.5c | +$9.78 together | -- |
| confidence (model not sure) | 198 | 28 | no price logged; the side the model leaned to 45 s before the close lost 11 of 170 (6 in 100) | -- | -- | -- |

Rules that only limit extra size (early leg once, max per market, close budget, staged)
refused only markets we already held; we won all of those.

The tool flags a rule when it "refused mostly winners and came out ahead even after counting
losses at full cost". It flagged the ceiling, edge floor, depth, 45-second floor, spike, jump
and thin rules. **Expect those flags every day.** On these markets the favourite wins 98-99
times in 100, so the flag does not mean "turn it off". The flag worth acting on is a rule
whose upper-bound cost stays well above one of our real losses, day after day. Today only the
ceiling is near that: about 2 typical losses' worth in 1.4 days.

## The loss in the window, and which rule saw it

- **ETH 09-27 2:29 AM ET, -$32.73.** Our bet won: 88 YES at 83.5c with 17 seconds left. The
  loss was the insurance: 88 NO at 51c, bought at 10 seconds left on a false alarm. The seller
  gate would have blocked this buy (79 in 100 sellers on our side, the offer only 92 ms old),
  but it switches off with 20 seconds or less left, and this buy came at 17. The price ceiling,
  edge floor, confidence and dump guard all refused this market at other moments. Only one
  loss, so this is not evidence for moving the 20-second line.

## Orders we sent that bought nothing

- 10 orders on 15-minute coins got nothing (someone took the offer first). All 10 markets won;
  the most they could have made is +$6.31.
- 3 hourly BTC orders were rejected for "invalid price" (see above), +$0.18 at most.

## Seller gate against its 10-01 bar (POSTMORTEM_2026-09-27 section 3)

- Wins it skipped, at most: +$5.98 against the $75 line. **KEEP on this reading.** It also
  refused one market that settled against us (the 1-contract hourly one).
- Share of early buys it refuses (OFF line: more than 25 in 100): 5 of 20 on the 45-second
  leg (25 in 100); 9 of 34 counting every buy with more than 20 s left (26 in 100); 8 of 33
  without the hourly market (24 in 100). **That is right on the line.** Read it again on 10-01.

## What this sample can and cannot show

- 1.4 days. 212 ceiling markets with 0 losers only rules out a loser rate of about 1.4 in
  100 or higher. The break-even at 99c is about 1 in 100, so the tape cannot say whether
  lifting the ceiling pays. The one-bet (8 markets), 45-second floor (4) and seller gate (9)
  samples can only rule out loser rates of about 35-75 in 100.
- I could not split this into 09-09..09-17 and 09-18..09-28 halves: every one of these safety
  settings started on 09-27.
- Where more trades could come from, in order of evidence: (1) fix the hourly limit, which
  is free and brings a live test back; (2) second full bets, +$23 at most in 1.4 days, but
  Q0928_one_bet already priced one lost second bet at about 30 such wins; (3) the 97.9-98.0c
  band, +$10 at most. None of these clears the bar for adding risk yet. The daily report will
  build the sample.

## How it was measured

- Our money comes from Kalshi's ledger. I used `pinledger.pnl`, which pays the winning side
  from the contracts held. The ledger's `revenue` field reads 0 on insured markets, and a
  first draft that used it booked the ETH loss as -$120.73. The log's own settled records
  give +$36.80 against the ledger's +$36.79. Log buys and ledger markets match: 37 and 37.
- A refused market's result is the market's own result, found in our ledger, in a cache
  (`results/missed_results_cache.json`, new) or through Kalshi's public market lookup: 26
  calls, no key, no order endpoint. All 1,259 needed markets were found; none was missing.
- Price and size come from each rule's FIRST refusal in the market that logged a price.
  Size is the smaller of what was offered and our bet (a third on the 45-second leg, 1
  contract on hourly BTC). Taker fees are included.
- Self-test: planted refusals, buys, insurance, duplicates, an out-of-window record, an
  insured ledger row and an empty world. It checks the exact dollars and fails on any miss;
  it passed. The shadow check is clean.
- Recorders: kalshi_collector (pid 2532788, 44 MB) and crypto_feeds (pid 105352, 26 MB)
  alive after the run. Free disk 62 GB; free memory 1.2 GB. No orders sent, no process
  touched, nothing written under C:\kals.
- READS_DUE: added `missed-daily`, due 09-29 8:00 AM ET.
