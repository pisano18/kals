---
name: desktop-app-is-the-control-surface
description: "Joe wants the bot controlled from a desktop program with Start/Pause/Stop, not scripts; Pin Bot (research/pindesk.py) exists since 2026-09-17 and the stand-down flag is how it and the watchdog agree"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4b086199-b082-458d-9cf9-786f0eb4321e
  modified: 2026-09-17T04:32:37.295Z
---

On 2026-09-17 Joe asked for the bot to relaunch itself "until it works" through a 3-5 AM maintenance window, and for "a proper tool on my desktop ... click start pause and stop. Make it that simple so anyone can do it, then do whatever you want for the rest of it."

**Why:** he is not going to run PowerShell scripts, and he expects downtime to be handled without either of us. Every earlier outage (7.57 h on 2026-09-15) was manual recovery.

**How to apply:** the control surface is the desktop shortcut **Pin Bot** (`research/pindesk.py`, tkinter). Any new operator-facing control goes there as a button, not as a command to paste. The stand-down flag `results/pinrun-live.stop` is the contract between the app and `watch_bot.ps1`: flag present = do not relaunch. If the bot is down and that file exists, he pressed Pause or Stop. `boot_all.ps1` (task KalsBoot) is the only thing that should start watchdogs; the live bot is only ever started by `restart_bot.ps1`. Remaining hole he was told about: a reboot with nobody signed in (no auto sign-in, no admin). START on the app also re-bases the 20% drawdown mark after a DRAWDOWN halt (v-hwm-reset, 2026-09-24). Related: [[handoff-is-the-only-continuity]], [[operator-pushback-is-usually-right]].
