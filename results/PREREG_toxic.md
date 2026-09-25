# PREREG_toxic -- "a FRESH offer while others are SELLING our side" -- written 2026-09-24 ~17:4xZ, BEFORE any arm ran

## The finding (our own fills, 09-13..09-24, first entries with MORE than 20 s left, 392 markets with both reads)

Two signals were each measured alone this morning and each looked like a
wash on money:

- FRESH: the offer we hit had been on the book under 500 ms (results/PREREG_fresh.md).
- SELLING: in the 3 s before our order, takers net-SOLD our side (sell share of
  taker volume > 0.5; results/cf_2026-09-24/toxicity.md).

Crossed, they are not the same population. The loss lives in the AND:

| cell (>20 s left) | markets | losers | lost $ | net $ | losses per 100 |
|---|---|---|---|---|---|
| neither | 146 | 1 | -29.90 | +203.96 | 0.7 |
| selling only (resting offer) | 51 | 0 | 0 | +109.00 | 0.0 |
| fresh only (no sellers) | 108 | 3 | -68.78 | +125.69 | 2.8 |
| **fresh AND selling** | **87** | **8** | **-461.81** | **-285.15** | **9.2** |

Eight of the twelve early losers sit in the AND cell, which is 22% of the
entries and the only cell that loses money. Mechanism: a level posted a few
hundred ms ago WHILE the tape shows takers dumping our side is an informed
seller joining a move; a resting offer with sellers around it was placed
before the move and is stale (0 of 51); a fresh offer with no selling is near
the base rate (3 of 108).

**Money if the AND cell had been refused:** gives up +$176.66 of winners to
avoid -$461.81 of losses = **+$285.15 over ~11 days**. Compare: fresh alone
+$159 (refuses 195 markets), selling alone +$176 (refuses 138), EITHER +$50
(refuses 246). The AND refuses the fewest markets and removes the most loss.
Honest discount: 6 of the 8 AND losers are 2026-09-19, the day hedges were
blocked by bugs since fixed; with working hedges those losses would be about
half, and the cell would be roughly -$75 net -- refusing it then is worth
about +$7/day, still with 8 of 12 losers removed.

**Why this is not a data-mined cell:** both thresholds were pre-specified
separately before this cross (500 ms in PREREG_fresh.md; sell share > 0.5 in
toxicity.md's own bar). This file pre-registers the conjunction.

## What gets built (in this order)

1. The live bot subscribes to Kalshi's `trade` channel for the markets it
   watches (the recorder already does), keeps a 3-second rolling count of
   taker buy/sell volume on each side per market, and writes `sell_share_3s`
   on EVERY signal and order record. No behaviour change on live.
2. A gate `toxic_fresh`: refuse an entry with more than 20 s left when the
   level age is exact and under 500 ms AND sell_share_3s > 0.5. Flag
   `--toxic-fresh` (default off). Entry only, below the hedge pass.
3. A paper arm `arm-toxic` = live's argv plus the flag. Live = arm + the
   refused set, so the refused set's real outcomes are live's own fills.

## The bar (decided now)

Read after >= 7 days of the live bot logging `sell_share_3s` (armh2h2 on the
same closes; the AND cell of live's own fills):

- **DEPLOY** the gate live if the AND cell of live's fills over the window is
  net NEGATIVE or within +$25 of zero AND holds >= 2 losers, AND its loss
  rate is >= 3x the rest of the early entries'.
- **KILL** if the AND cell is net >= +$75 with <= 1 loser, or its loss rate
  is under 2x the rest.
- Otherwise EXTEND 7 days. The 500 ms and 0.5 thresholds do not move on the
  data that chose them.

## What it may never do

Block or delay a hedge. Touch entries inside 20 s. Refuse on a lower-bound
(non-exact) age. Trade on a stale trade feed: if the feed is older than 5 s
for a market, sell_share_3s is None and the gate stands down (logged).
