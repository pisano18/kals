---
name: coin-race-size-and-direction
description: "Coin race size went 1 -> 5 contracts on 2026-09-24 with Joe's OK (v-race5); the next size step waits on the photo-finish arm; he wants earlier entry without added risk"
metadata: 
  node_type: memory
  type: project
  originSessionId: 47b37ac1-655c-4d72-a81b-a48e9625d5bd
  modified: 2026-09-24T15:18:12.297Z
---

**Size: 5 contracts a leg since 2026-09-24 15:16Z (v-race5).** Was 1
("size stays 1 contract until Joe says"); he said: *"If you're ready to size
coin race up and feel confident we can give it a small boost."* 5 and not
more because the break-even margin was +1.2 points on 95 legs -- not
distinguishable from zero. Safe only because v-race-tie1 (same day) reads
ties from Kalshi's own result, pays 50c to both tied coins, and counts a tie
as a LOSS for the stop-on-first-loss rail; before that a real tie was booked
as a win and the rail did not fire.

**Before any further size step:** read `arm-gap075` -- races whose top two
coins finish within 0.75 basis points are 15 in 100 of the races we enter
against 7 in 100 of all races. If they are the loss class, that filter goes
in first.

**Earlier entry** (his standing want, without added risk) is being measured
by the `z3` arm (enters more than 30 s out on a 3-sigma gap): 36 won, 1 tie,
0 lost in 37 races (as of 09-24; `python research/bars.py` for the live count). Bar: 125 races with no losses, or 250 with at most one.

See [[measure-then-ship-only-positive]], [[paper-log-money-fields]].
