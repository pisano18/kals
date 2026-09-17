# RESULTS -- the dump guard IS a hidden 85c price floor, but it has NOT cost $82

**2026-09-17. THIS FILE REPLACES AN EARLIER VERSION THAT WAS WRONG, and the
error is left described rather than deleted, because it is a trap in the log
format that will catch the next reader too.**

## The part that is true: it is a price floor

`research/pinrun.py`, AMENDMENT 10:

```python
_conf = f if want == "yes" else (1.0 - f)     # our belief in OUR side
_disc = (f - price) if want == "yes" else ((1.0 - f) - price)
if _disc > DUMP_DISCOUNT:        # DUMP_DISCOUNT = 0.15
    ... continue                 # refuse
```

The confidence gate upstream guarantees `_conf >= PIN = 0.995`, so the refusal
condition `_conf - price > 0.15` is exactly

    price < 0.995 - 0.15 = 0.845

**Any offer below about 84.5c is refused, by a gate whose name says nothing
about price.** Nothing in the buy path is NAMED a price floor. This is one.
That part of the original finding stands, and it is worth knowing.

## The part that was WRONG: "$82 of blocked winners"

The first version of this file said the guard had refused 17 markets, that 10
had settled, that all ten would have won, and that this was $+82.30 left on the
table. **Every step of that is a misreading of what a `dumped` record means.**

**A `dumped` record marks a MOMENT, not a market's fate.** It is written once
per (close, market), the first time the offer sits more than 15c under fair.
The bot then keeps evaluating that same market every tick. When the discount
narrows below the threshold a second later -- which is the normal case, because
a dump is usually a brief print -- **the bot buys it.**

Checked against the fills:

| of 17 flagged markets | |
|---|---|
| bought anyway, seconds later | **10** |
| never traded | 7 |

**The ten "blocked winners" were not blocked. We own them, and their wins are
already inside the run's +$422.** Counting them as forgone was double-counting
money we already have.

The seven the guard genuinely stopped are these, and **not one has a settlement
record in our logs**, so their outcome is unknown:

| market | day | side | price | discount |
|---|---|---|---|---|
| KXBNB15M-26SEP110830-30 | 09-11 | no | 0.860 | 14.0c |
| KXDOGE15M-26SEP110830-30 | 09-11 | no | 0.920 | 8.0c |
| KXHYPE15M-26SEP110830-30 | 09-11 | yes | 0.920 | 8.0c |
| KXNEAR15M-26SEP110830-30 | 09-11 | yes | 0.480 | 52.0c |
| KXBNB15M-26SEP111245-45 | 09-11 | no | 0.460 | 53.9c |
| KXXRP15M-26SEP111730-30 | 09-11 | no | 0.740 | 25.7c |
| KXXRP15M-26SEP160215-15 | 09-16 | yes | 0.450 | 54.5c |

Six of the seven are from a single day, 09-11, and two carry discounts (8.0c)
below today's threshold, so the configuration then was not the configuration
now. **The measured cost of the dump guard is therefore: unknown, and close to
zero on anything recent.**

## What the cheap end actually looks like when we DO buy it

Separately, and scored correctly this time (the side of a fill lives in
`body.side` -- `bid` is YES, `ask` is NO; there is no `want` field on an order
record, and reading one gives every fill the same wrong answer):

**Every sub-85c fill the bot has ever taken: 9 won, 4 lost, net $+25.15.**

That is a real, modest, positive result for cheap buys, on 13 live fills. It is
not evidence about the dump guard, because most of those fills predate it. It
is evidence that the cheap end is not poison.

## The two measurement lessons, for whoever reads this next

1. **A refusal record is per-MOMENT, not per-market.** Before claiming a gate
   cost anything, check whether the market was traded later anyway. This is the
   same family as counting trades where rule 4 wants closes.
2. **`want` does not exist on an order record.** Reading it returns `None`,
   every comparison fails, and every fill scores as a loss. This produced a
   confident "-$297.85, 13 of 13 lost" that was entirely an artefact -- the
   second time in one day the same field-name error inverted a conclusion (the
   first was hedges, where `side` was the right field).

## Status

**No change was deployed.** The operator had approved raising `DUMP_DISCOUNT`
from 0.15 to 0.25 on the strength of the $82 figure; that figure does not
survive checking, so the change was not made and the decision goes back to him
with the corrected numbers.

**What would settle it properly:** the guard needs an arm that records, for
every flagged market, whether the bot later bought it and what it settled at --
i.e. the counterfactual for the markets it truly blocks, not the ones it merely
delays. Until that exists, the honest answer about the dump guard's cost is
"we do not know, and it is smaller than it looked".
