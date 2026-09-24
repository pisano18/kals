# PREREG_fresh -- "no fresh offers with more than 20 s left" -- written 2026-09-24 ~08:1xZ, BEFORE the paper arm ran

## The signal, measured on OUR OWN FILLS (not the tape)

`level_age_ms` -- how long the price level we hit had been resting when we hit
it -- has been written on every signal record since 2026-09-13 (livebook
`level_age_ms`, exact when we saw the level appear, a lower bound when it
predates our watch). First fills with it on record: 587 (17 losers). Of the
markets that SURVIVE tonight's live rules (spike gate, 10c cap above 20 s,
95c early floor), entered with MORE than 20 s left: 385 markets, 7 losers.

| level age at the fill (>20 s left, survivors) | markets | losers | lost $ | net $ |
|---|---|---|---|---|
| under 200 ms | 159 | 5 | -275.14 | -25.19 |
| 200-500 ms | 28 | 1 | -0.47 | +37.03 |
| 0.5-2 s | 34 | 0 | 0 | +53.79 |
| 2-10 s | 9 | 1 | -29.90 | -16.79 |
| over 10 s (resting before we looked) | 155 | 0 | 0 | +233.25 |

Six of the seven remaining early losers -- BTC 09-19 16:00 -$107.95, XRP
09-19 -$64.95, BNB 09-19 12:30 -$61.75, HYPE 09-21 -$31.27, NEAR 09-16
-$9.22, BNB 09-16 -$0.47 -- hit a level that had existed for 19-229 ms. The
seventh hit a 6.5 s level. Loss rate 6 of 187 (3.2 in 100) for fresh levels
against 1 of 198 (0.5 in 100) for resting ones. Inside 20 s the age does not
matter (fresh 2 of 68, resting 2 of 73, both positive) -- the average is
mostly locked there.

**Mechanism:** a level posted a few hundred milliseconds before we lift it
is someone reacting to the same index print we are -- and 94% of fresh
90-98c posts are pulled within 500 ms on the tape, so the ones we get filled
on are the ones the poster WANTED to sell. A level that was resting before
the print is a stale quote; we are first. The same population shows up in
results/cf_2026-09-24/toxicity.md (taker selling of our side in the 3 s
before our order marks 68% of losers vs 33% of winners, only at 21-45 s).

**Money, honestly:** refusing every fresh (<500 ms) level at >20 s gives up
+$287.45 of winners to avoid -$275.60 of losses on this record: net -$11.84
over 11 days, i.e. about zero. Four of the six losers are 2026-09-19, the
day hedges were blocked by bugs since fixed; with working hedges those four
would be roughly half, and the refused group would be about +$130 -- a
real cost of ~$12/day for the loss reduction. By period the refused group
was +$75 (09-13..15), -$117 (09-16..19), +$53 (09-20..24). This is a
lose-less rule with an expected cost between $0 and $12 a day, NOT a make-
more rule. It is therefore NOT deployed live on this measurement.

## What runs: the paper arm `arm-fresh500`

Flag `--fresh-min-age-ms 500 --fresh-tau-min 20` (both default off): with
more than 20 s left, refuse an entry whose level age is exact and under
500 ms, as gate `fresh_level` (entry only, below the hedge pass, records the
age). The arm is live's argv plus that flag, so on the SAME closes live =
arm + the fresh entries, and the refused set's REAL outcomes are live's own
fills.

## The bar (decided now, before any arm number is read)

Read after >= 7 days beside live, with `results/cf_2026-09-24/armh2h2.py`
on the same closes both were up for:

- **DEPLOY** if live's fresh (<500 ms, >20 s) fills over the window are net
  NEGATIVE or within +$25 of zero AND contain >= 2 losers, i.e. the rule
  costs nothing and removes losses -- and the arm shows no loser that live
  did not also have.
- **KILL** if live's fresh fills over the window are net >= +$100 with <= 1
  loser (the signal stopped separating, or the loss size is now bounded by
  the hedge and the fresh winners pay for it).
- Otherwise extend 7 more days; never move the 500 ms / 20 s numbers on the
  same data that chose them.

## What it may never do

Block or delay a hedge (it sits in the entry scan). Touch entries inside 20 s.
