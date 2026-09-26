---
name: measure-then-ship-only-positive
description: "Joe (2026-09-24) - any rule can change but never change for the sake of changing; the only test is a bigger end-of-day profit, measured; his own ideas are suggestions to be measured, not orders"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 47b37ac1-655c-4d72-a81b-a48e9625d5bd
  modified: 2026-09-24T03:05:42.376Z
---

Joe, 2026-09-24, after the BTC -$130 loss: "Any rule can be changed if you
think another way is better. It's not law." Then: "don't change things for
the sake of changing. Use your ultimate logic testing and judgement to
simply make the biggest profit after revenue minus liabilities." And: his
ideas (e.g. half size before 20 s, top up after) "are simply suggestions
with nothing to back it up, that's your job."

**Why:** he wants the profit number bigger and trusts measurement over
opinion, including his own; a change that measured negative (his ladder,
-$41) was left off and he accepted that.

**How to apply:** price every candidate on the per-second rebuild
(`results/cf_2026-09-24/cf_build.py` + `cf_sim.py`: belief from the index
tape with pinrun's maths, ask from the ticker tape, money from Kalshi's
ledger), compare rule sets on ONE engine, split by week, print a 70%-fill
column, ship only what is positive in both weeks, and record what was
measured and NOT changed in HANDOFF so it is not re-proposed. A refusal is
per SECOND, not per market -- the bot re-looks and re-enters -- so never
count a gate's give-up as whole markets. See CLAUDE.md (LENGTH rule),
[[operator-pushback-is-usually-right]].
