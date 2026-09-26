---
name: validate-before-you-kill
description: "restart_bot.ps1 stops the money bot before starting the new one, so anything that can make the START fail must be checked while the old bot still runs; a bare comma on its own line in a PowerShell array took the bot down."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4b086199-b082-458d-9cf9-786f0eb4321e
  modified: 2026-09-19T04:16:28.737Z
---

`restart_bot.ps1`'s one dangerous act is stopping a live money process
before starting another. On 2026-09-19 a bare `,` on its own line between
two flags -- PowerShell's unary array operator -- nested the argument list,
so the script killed the bot and then `Start-Process` refused with "Cannot
convert 'System.Object[]' to the type 'System.String'". `watch_bot.ps1`
calls the same script, so every retry failed identically. Joe had been told
the new bot was live; it was not running at all.

**Why:** a check that runs after the kill converts "nothing happened" into
"nothing is running". The launcher now builds `$botArgs` at the top and
validates it (flat, all strings, non-trivial length) before the kill.

**How to apply:** after ANY edit to `restart_bot.ps1`, before telling Joe
to restart -- (1) parse it with
`[System.Management.Automation.Language.Parser]::ParseFile`, (2) evaluate
the `$botArgs` block and assert every element is a string, (3) run the flag
list through the startup path in paper. Never put a comma on its own line
in a PowerShell array; it goes on the value. See
[[do-the-restart-yourself]] and
[[run-the-startup-path-with-the-new-flag-before-restarting-live]].
