---
name: paper-log-money-fields
description: "In pinrun logs `settled.realised` is a RUNNING day total, not the market's money; per-market money is `pnl_c`/100. Arm names are not in the logs; group paper logs by their start-record diff vs live."
metadata: 
  node_type: memory
  type: project
  originSessionId: 47b37ac1-655c-4d72-a81b-a48e9625d5bd
  modified: 2026-09-24T03:05:52.691Z
---

Found 2026-09-24 while building the arm head-to-head: summing
`settled.realised` gave +$5,150 for four days that Kalshi books at ~+$110.
`realised` accumulates through the day; the market's own money is
`pnl_c / 100` (cents, whole market, after fee). Paper-arm start records
carry no arm name and `results/arm-<name>.out` names only the CURRENT
run's log (a re-sync wipes the history), so identify a paper log by the
keys where its start record differs from live's start record of the same
moment (`results/cf_2026-09-24/armh2h2.py` does this).

**Why:** a wrong money field made every arm look +$3,000; the fix took an
hour.

**How to apply:** use `armh2h2.py` for arm-vs-live on the SAME markets over
closes both were up for; treat arm money as paper fills (100% at the ask),
and remember arm-vs-live is only valid from the 2026-09-20 sync. See
[[arm-data-was-measuring-nothing]], [[an-arm-must-have-exercised-its-flag]].
