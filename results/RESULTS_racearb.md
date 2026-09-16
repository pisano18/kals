# The Coin Race basket — real, tiny, and capital-hungry. PARKED, not killed.

`research/pinarb.py`, 2026-09-16. Source: the `ticker` channel, 1,344,636 Coin
Race updates over 240 hours, 930 races. Tape — valid for what the market
offered, and that is all this claims.

## The idea
A race has five legs and exactly one pays $1.

* buy all five YES → paid $1 whoever wins. Free money if they sum under $1.
* buy all five NO → paid $4, since four legs lose. Free money if the five
  bids sum over $1.

**No forecast in it.** It does not care whether our index model is right, which
is what makes it worth a look next to everything else here.

## Why the earlier look could not settle it
`RESULTS_coinrace` saw "the five legs summed 87c once in 26 events" from TRADE
PRINTS, which happen seconds apart. A sum built from prices at different moments
is not a basket anyone could have bought. This uses top-of-book updates and only
counts a moment when **all five legs were fresh together**.

## What is actually there

| filter | moments | races | total if filled at the size on offer |
|---|---|---|---|
| any freshness, any size | 155 long / 108 short | ~90 | meaningless — mostly stale |
| **all five fresh within 1 s, ≥1 whole contract** | **84** | 930 | **$52.01** |
| the same, ≥10 contracts on the thinnest leg | 28 | 930 | $46.81 |

**About $5 a day**, and 25 of the 28 worthwhile ones are the NO basket.

## Why it is parked rather than built

1. **Capital.** A NO basket costs ~$4 a unit to earn ~8c. A 100-unit basket ties
   up ~$400 — nearly the whole bank today — to make $8. The pin earns more on
   the same dollars.
2. **All five or nothing.** Our single-leg fill rate is ~90%, so five legs land
   together about 59% of the time. A partial fill is an unhedged position in a
   race we have no view on.
3. **It is rare.** 28 usable moments in ten days.

## When to revisit
When the bank is large enough that idle capital exists, or if the count per day
rises. `pinarb.py --hours N` re-runs it in a couple of minutes; the scan is
cheap because it reads the 988 MB ticker channel, not the 47 GB book channel.
