---
name: never-rebase-with-live-bots
description: "Never git pull --rebase / autostash / reset --hard / stash in C:\\kals-repo while bots run -- it reverts tracked LIVE state files (pinrun-live.pid, pinrun-hwm.json) and logs"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 47b37ac1-655c-4d72-a81b-a48e9625d5bd
  modified: 2026-09-22T06:33:06.050Z
---

On 2026-09-22 a `git pull --rebase` (autoStash) failed half-way on a locked
log (`results/watch_bot.console.log`, held open by watch_bot). Its `reset
--hard` had ALREADY reverted 77 tracked files to HEAD, including
`results/pinrun-live.pid` (pointed at a dead pid, so the watchdog/app could
think the live bot was dead and start a second one), `pinrun-hwm.json` (the
bank brake's high-water mark) and ~40 paper/live jsonl logs. Recovered from
the autostash commit with a per-file script (stash + anything appended since).

**Why:** `results/` holds files the running bots both READ and WRITE, and they
are tracked. Anything that resets the working tree rewrites live state.

**How to apply:** to integrate a remote commit, use `git fetch` then
`git merge --no-edit origin/<branch>` (touches only the files that commit
changes). Never `pull --rebase`, `--autostash`, `stash`, `checkout .` or
`reset --hard` in this repo while any bot runs. Commit only named files.
Related: [[validate-before-you-kill]].
