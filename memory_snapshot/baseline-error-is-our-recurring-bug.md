---
name: baseline-error-is-our-recurring-bug
description: "Before reporting any trend, check what the comparison window is anchored to - twice now a real number has been read against a peak and called a collapse"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4b086199-b082-458d-9cf9-786f0eb4321e
  modified: 2026-09-18T06:13:17.357Z
---

Twice in this project a correct number produced a wrong conclusion because of
what it was compared AGAINST, not because the number was wrong.

1. **2026-09-18, "the cheap-offer pool halved."** Real arithmetic, measured
   against 09-09..09-12 -- the four highest days in a 24-day record. Against a
   normal (median) earlier day the same days were UP 7%. See
   [[supply-exists-we-arrive-late]].
2. **The commodity series joined the tape on 09-14** and added 10-15k bargains
   a day. Comparing a 14-series day against a 9-series day measured the
   denominator, not the market.

**Why:** a peak is the most tempting anchor because it is the most recent
vivid thing, and a changed population is invisible unless you go looking for
it. Joe's reaction to the first one was *"Are you 100% certain opportunities
have halved... Are you 100% certain you can't be missing anything"* -- and the
honest answer was no. He was right to push. See
[[operator-pushback-is-usually-right]].

**How to apply:** before reporting any trend, say out loud what the baseline
is and whether the population changed inside the window. Report the MEDIAN of
every earlier observation alongside any window comparison -- four outliers
cannot move a median but they drag a mean. `research/pinsupply.py`'s
`baseline()` enforces exactly this and its self-test plants the error; copy
that shape for any future trend claim. And prefer a second, independent source
over a second look at the same one: Kalshi's REST market history goes back 67
days, 2.5x our own tape, and settled the question on its own.
