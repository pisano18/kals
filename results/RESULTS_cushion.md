# A minimum "distance from the strike" gate would have COST us money. Killed.

**2026-09-18.** After the -$27.87 Bitcoin loss the operator asked whether
anything could warn us before buying. The cushion -- how many standard
deviations the spot sits from the strike at the moment we buy -- looked like
the answer, because the losses cluster there:

| cushion | markets | lost | loss rate |
|---|---|---|---|
| under 3 sd | 164 | 6 | 3.7% |
| 3-4 sd | 112 | 3 | 2.7% |
| 4-6 sd | 108 | 1 | 0.9% |
| over 6 sd | 174 | 3 | 1.7% |

**Six of thirteen all-time losses sat under 3 sd**, and the Bitcoin loss sat at
2.70 -- $21 above the strike on a $76,500 coin, which the model called 99.56%
safe by mapping that distance through a NORMAL curve when the index has
measured kurtosis 132 against a normal's 3.

Every word of that is true and the conclusion drawn from it was still wrong.

## Scored in DOLLARS instead of losses, on our own settled money

| floor | markets skipped | of which losers | money skipped | net vs today |
|---|---|---|---|---|
| 2.0 sd | 54 | 3 | +$5.80 | **-$5.80** |
| 2.5 sd | 96 | 4 | +$48.09 | **-$48.09** |
| 3.0 sd | 144 | 5 | +$86.85 | **-$86.85** |
| 3.5 sd | 202 | 7 | +$93.74 | **-$93.74** |
| 4.0 sd | 242 | 9 | +$105.31 | **-$105.31** |

Base: $+514.87 over 494 settled markets.

**Every floor loses money, and the more it protects the more it costs.** A
3-sigma floor would skip 144 markets to avoid 5 losers, and those 144 markets
made **+$86.85** between them. The thin-cushion trades lose more often AND are
still profitable: they earn $0.60 a market against $1.04 for the rest.

## The lesson, which is the same one this project keeps learning

**Counting losses is not counting money.** "Six of our thirteen losses were
under 3 sd" is a true sentence that points the wrong way, because the 164
markets it indicts also contain the winners that pay for them. At 96c a gate
must be judged on dollars per market, never on how many bad outcomes it
catches -- a rule that catches every loss by refusing every trade is perfect
by that measure and worthless.

This is the third time in one day the same error shape appeared: win RATE is
not profit (the race arm that won 8 of 9 legs and lost $1,682), loss COUNT is
not cost (the dump guard that "blocked 10 winners" it had actually bought),
and now loss LOCATION is not loss VALUE.

## What is worth trying instead

Not a floor -- a **size taper**. Thin-cushion markets are profitable but earn
about 58% as much per market, so the honest response is to take them SMALLER
rather than refuse them, which keeps the profit and cuts the variance. That
also fits the other finding of the night: the damage from a collapsing book is
bounded by SIZE and by nothing else.

No paper arm was started for the floor. It does not need one; the answer is
already in the settled record.
