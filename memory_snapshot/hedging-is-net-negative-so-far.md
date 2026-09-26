---
name: hedging-is-net-negative-so-far
description: "Hedging is about break-even lifetime (-$9.35 on the ledger, 09-22); it recovers only a third of a loss; nothing at the alarm second predicts a false alarm; live = hedge ALL at belief 0.40 (A76 proportional removed)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 350e3ea1-7f0f-4b66-8f90-c31872b59750
  modified: 2026-09-25T07:10:20.664Z
---

**Lifetime, Kalshi's ledger (CURRENT_STATE correction, 2026-09-22): -$9.35** --
10 real saves +$149.26, 7 false alarms -$158.60. (An earlier note said
+$111 / -$159, or -$47; those are superseded.)

**Live rule now:** hedge the WHOLE position when belief falls to 0.40
(`--hedge-belief 0.40 --no-hedge-prop`, v-nospike 2026-09-24), limit slip 0.10
(v-lateadd-live). History: 0.60 -> 0.25 (v-hedge25, 09-21) -> 0.40 (0.25 fired
5 s late on the 09-23 BTC loss). **A76 proportional hedging fired ONCE (NEAR
09-21, +$15.15) and was REMOVED** (v-hedgefull, 09-21). The 09-24 per-second
rebuild over 820 positions found 0.40 all-at-once the best of every trigger,
proportional, drop-from-peak and seconds-left-aware variant tried -- no change.
`arm-nohedge` and the hedge arm family were retired 2026-09-24.

It works when needed -- a hedged loss costs **57c a contract against a naked
86c** -- but that is only **about a third** recovered, because a hedge returns
`1 - price paid` and by the time belief collapses enough to fire, the market
has repriced to 46-80c.

**All 18 alarms raised up to 09-21 were rebuilt from the raw index. NOTHING
observable at the alarm second separates a false alarm from a real collapse**
-- not crossing depth, market-wide vs idiosyncratic, belief level or seconds
left. The information arrives 1-10 s later, and by then insurance is at 99c
(trade tape: 58c -> 99c in 5 s). A confirmation delay is +$37 overall but
**-$79 excluding one close**. So a hedge cannot be made rarer without making it
useless.

**Unwinding does not work, and the arithmetic is settled.** Both sides held
is a fixed outcome: 104 NO at 94c + 104 YES at 46c costs $145.60 and pays
exactly $104. Selling back when confidence returns recovers ~2c on the 46c,
because the hedge became worthless precisely *because* the bet recovered.
**The money is lost at the moment of purchase.** See
[[a-gate-must-never-block-a-hedge]].
