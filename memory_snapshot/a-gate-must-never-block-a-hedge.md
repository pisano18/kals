---
name: a-gate-must-never-block-a-hedge
description: "2026-09-19 lost $106.73 -- the first losing day ever -- and three of the four losses were new gates/brakes blocking a hedge or crashing the loop, not market or model errors."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4b086199-b082-458d-9cf9-786f0eb4321e
  modified: 2026-09-19T20:56:21.614Z
---

**2026-09-19: the first losing day since going live, -$106.73 against
+$64.59 the day before (that figure was taken at ~20:5xZ; the full ET day
on Kalshi's ledger was -$223.46). Three of the four big losses were caused by code
shipped in the previous 24 hours.** The operator: *"Today's losses were
caused by you including things that don't even allow it to work. You're the
only version who's lost me money."*

- `--hedge-price 0.60` refused a hedge at a **21c** ask at 22.7% belief:
  **-$57.76**.
- The `close_budget` gate logged `want`/`price`/`fair`, assigned ~100 lines
  later; `round(None)` killed the loop while holding: **-$66.34**.
- `--loss-cap 200` paused the bot one instant after a fill, and the pause
  branch's `continue` skipped the hedge pass entirely -- 45 seconds, no
  alarm, no attempt: **-$107.95**, the largest loss in the project.

**Why:** every one is a GATE OR BRAKE blocking something it was never meant
to block. Not a model error, not the market. A safety feature nobody tested
against the thing it would refuse. The third is the worst because the
self-test *enforced* it -- it asserted "risk_abort() runs before the first
`continue`", which is what pinned the brake above the hedge.

**How to apply:** before shipping any gate or brake, write down what it
BLOCKS, not what it allows, and prove in a self-test that it cannot block a
hedge. A hedge buys the other side of a position already open: it lowers that
close's worst case and cannot raise exposure, so nothing may ever gate it.
And when a new flag changes a rail, re-derive every OTHER rail that reads
that rail -- `--loss-cap` tightened the abort, which made a rare pause
routine. See [[run-the-startup-path-with-the-new-flag-before-restarting-live]]
and [[an-arm-must-have-exercised-its-flag]].
