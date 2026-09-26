---
name: the-disk-is-the-real-deadline
description: "run_all.ps1 stops both recorders for good at 5 GB free (our guard is 6 GB); the tape cannot be recreated; the 2 TB external drive is NOT bought yet - report free disk in every status"
metadata: 
  node_type: memory
  type: project
  originSessionId: 350e3ea1-7f0f-4b66-8f90-c31872b59750
  modified: 2026-09-25T07:10:12.345Z
---

**As of 2026-09-25 07:02Z: 11.9 GB free on C:.** Readings: ~19.8 GB 09-21;
21.2 GB 09-24 ~04Z; 5.9-7.9 GB 09-24 ~22:20Z (phone DISK alerts) before space
was freed; 14.5 GB 09-25 06:10Z. The daily rate is NOT settled -- notes quote
~1, ~3.9 and ~4 GB/day, and workflow worktrees (`.claude/worktrees`, 1.9 GB on
09-25) and other jobs move free space too. Measure; never quote a stop date
from one rate.

**The line:** `C:\kals\run_all.ps1` line 41 breaks its loop at **5 GB** and
**both recorders stop for good** -- a hard collection stop, not a slowdown. Our
guard is **6 GB**: below it stop all analysis and say so loudly (CLAUDE.md).
A full disk also takes the MONEY bot down, not just the tape (09-24 audit).

`C:\kals\kalshi_data` writes ~130 MB an hour (09-21 figure). **The tape cannot
be recreated.**

**The fix is hardware, and it is not bought:** a 2 TB external HARD drive
($105 Toshiba / $119 Seagate; an SSD buys nothing for an append-only
recording -- OPEN_WORK C1). Earlier notes said "Joe is buying an SSD"; that
changed. The longer-term option is uploading the tape to cloud storage
(`results/VM_PLAN_2026-09-24.md`, ~$3-8/month). Remind him; cron reminders are
session-only and die with a `/clear`. Report free disk in every status; say it
loudly under 8 GB.
