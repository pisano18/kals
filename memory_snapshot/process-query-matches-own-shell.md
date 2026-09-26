---
name: process-query-matches-own-shell
description: "A Win32_Process `-like '*pindesk.py*'` (or pinphone/pinrun) query matches the bash/powershell running the query itself; filter Name='python.exe' or you kill your own shell (exit 255) and mis-count duplicates"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 47b37ac1-655c-4d72-a81b-a48e9625d5bd
  modified: 2026-09-24T06:47:14.688Z
---

2026-09-24 02:2xZ: `Get-CimInstance Win32_Process | Where-Object { $_.CommandLine
-like '*pindesk.py*' } | Stop-Process` "stopped" four processes -- the app AND
the bash/powershell ancestors of the command itself (their command lines
contain the pattern). The shell died, the command exited 255 before its
relaunch step ran, and the "five pindesk processes" that then appeared were
my own shells again. Same for `*pinphone.py*`, `*--live*` (matches the coin
race), `*research*`.

**Why:** it looks like duplicate daemons, and killing "duplicates" kills the
session's own shell.

**How to apply:** always add `-Filter "Name='python.exe' or Name='pythonw.exe'"`
(or match `pythonw.exe`+`research\pindesk.py`), print pid + CreationDate +
ParentProcessId before acting, and never `Stop-Process` from a pattern that
could match the running command. See [[validate-before-you-kill]].
