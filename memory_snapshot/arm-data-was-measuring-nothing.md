---
name: arm-data-was-measuring-nothing
description: Every paper-arm conclusion before 2026-09-20 is void - arms could not hedge (until SHA 1bd47c9) AND differed from live in up to 16 settings; arm-vs-live valid only from 2026-09-22 06:21Z
metadata: 
  node_type: memory
  type: project
  originSessionId: 350e3ea1-7f0f-4b66-8f90-c31872b59750
  modified: 2026-09-25T07:10:04.854Z
---

**Any confidence, sigma or hedge conclusion drawn from a paper arm before
2026-09-20 is WITHDRAWN.** Arm-vs-live comparisons are valid only from
2026-09-22 06:21Z (the rebuilt fleet). Two independent faults, either one fatal:

1. **No paper arm could hedge, ever -- until 2026-09-19 (A71, SHA `1bd47c9`).**
   `pinrun`'s hedge pass skips any position missing from `hedge_meta`, and
   `hedge_meta` was written at exactly two sites, both live-only. A paper
   position never had a strike, so its belief was never computed and its alarm
   never fired. Measured: the five arms on 09-19 logged 151 signals and ZERO
   `hedge_alarm` / `hedge` records; live on the same markets had 2 alarms, 8
   hedges, 2 panics. A filled hedge turns a -73c..-96c per-contract loss into
   -26.9c, so every arm-vs-live head-to-head compared a bot that eats losses
   whole against one that insures them. Invalid on LOSING closes specifically
   (winners unaffected). It is also why A62, A69 and A70 had to go straight to
   live: paper could not exercise them.
2. **Arms ran flag lists frozen at launch.** `arm-pin0.97` differed from the
   live bot in **SIXTEEN** settings -- no 45-second leg at all, no
   `--hedge-price`, no `--hedge-slip`, no late boost, no extra coin, a
   different bank brake. It was never measuring confidence.

**The fix:** `sync_arms.ps1` builds every arm from the **live bot's own
command line**, stripping only what that arm tests. Change live, re-run it,
the whole fleet moves. `-Only` disables the stale sweep (without that it
retires every arm outside the narrowed plan -- it killed all 21 once).

**Two kinds, and the distinction is load-bearing:** SYNCED arms (live + one
change) must move with live; FROZEN baselines (`arm-live-frozen`, the
`pinvin_*` snapshots, the manual `arm-afternoon`) must not, because not moving
is their job.

`pinlab.EXPERIMENTS` must be updated whenever arms are renamed -- it listed 34
dead arms and none of the 24 real ones, which made the Lab look frozen on a
single arm. (Merged 2026-09-25 from the former `paper-arms-could-not-hedge`
note.) Relates to [[an-arm-must-have-exercised-its-flag]],
[[a-gate-must-never-block-a-hedge]], [[paper-log-money-fields]].
