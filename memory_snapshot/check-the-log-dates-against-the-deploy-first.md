---
name: check-the-log-dates-against-the-deploy-first
description: "Before reading code to explain a pattern in the logs, check whether the records predate the last fix - an hour was spent explaining behaviour that no longer existed"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4b086199-b082-458d-9cf9-786f0eb4321e
  modified: 2026-09-18T16:20:48.125Z
---

2026-09-18. The both-sides guard appeared to block every top-up: 149 live
markets, and on 129 of them the original side went on to win, so the block was
plainly wrong. I read every line between the fair computation and the gate,
instrumented the gate, restarted the live bot on it, and could not produce a
flip from any input -- because the code I was reading was correct. The 149
records were written BEFORE `v-a8fix` (09-17 ~21:0xZ). Post-fix live runs show
two blocks, both genuine reversals, and three real top-up orders.

Four paper arms started on 09-15/16 were still running the pre-fix code they
loaded at start, producing hundreds of bogus blocks that looked like a live
reproduction. Restarted on current code.

**Why it went wrong:** I anchored on "the code cannot do this" and kept reading
harder, when the first question should have been "when were these records
written, and what has changed since". The operator's nudge -- *"look at exactly
how the code and the bot actually works instead of assuming"* -- was right, but
the assumption I was making was about the DATA's vintage, not the code.

**How to apply:** when a log pattern contradicts the source, the first check is
a timestamp histogram of the pattern against `results/VERSIONS.md` deploy times
and the start records of the runs it came from. A paper arm runs whatever
source it loaded at launch; an arm older than the last relevant commit is
evidence about an old bot. See [[baseline-error-is-our-recurring-bug]] and
[[compare-against-the-real-alternative]] -- same family: a correct reading of
the wrong reference.

**What the post-fix data actually says, which is the finding that matters:**
26 of 34 early legs on live were never topped up because by 30 s there was
nothing left to buy (`no_offer`), not because anything blocked them. At a
third size that forgoes two thirds of the intended position on three markets
in four -- the strongest argument for running the 45-second leg at full size.
