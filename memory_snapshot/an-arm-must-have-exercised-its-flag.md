---
name: an-arm-must-have-exercised-its-flag
description: "Before quoting a paper arm's record, check it actually TRADED the same markets as live and that its flag ever FIRED; two separate bugs made arms look decisive on no data."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4b086199-b082-458d-9cf9-786f0eb4321e
  modified: 2026-09-19T08:15:58.922Z
---

Two independent traps in reading a paper arm, both found 2026-09-19:

1. **Population.** `pinlab.whatif` scaled an arm's money-per-contract onto
   live's whole volume, which credits the arm for every close it never
   entered. A51 read **+201%** while being **$58.35 behind** on the 54
   markets the two actually shared. Fixed: `whatif()` now returns `h2h`
   (both sides' money on shared markets, unscaled) and the Lab leads with
   it. **Read `h2h['diff']`, never `diff`.**
2. **The flag never fired.** The same A51 arm had taken **0 hedges in 75
   markets** -- the hedge blocker it exists to test had never once been
   reached, while live hedged 21 times. Nothing checks for this yet.

**Why:** both make an arm look decisive on no data, and both survive a big
`n`. The operator caught #1 himself ("the tracking chart isn't working?
Because a51 doesn't show a loss at that time") after I had already quoted
the bad number to him twice.

**How to apply:** before quoting any arm, state (a) how many markets it and
live BOTH settled, and (b) how many times its flag actually fired. If either
is near zero, say "no data", not a percentage. Per-contract is the only way
to compare a 20-contract arm to a 105-contract live bot -- A51 and live were
identical at 2.21c each. See [[baseline-error-is-our-recurring-bug]] and
[[compare-against-the-real-alternative]].
