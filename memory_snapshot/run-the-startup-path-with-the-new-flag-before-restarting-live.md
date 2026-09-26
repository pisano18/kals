---
name: run-the-startup-path-with-the-new-flag-before-restarting-live
description: A new flag on an old constant took the live bot down for six minutes because pinrun self-tests at startup WITH the flag applied and old checks assert the running value - --selftest alone does not catch it
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4b086199-b082-458d-9cf9-786f0eb4321e
  modified: 2026-09-18T17:11:34.195Z
---

2026-09-18, ~13:04-13:10 ET. I added `--price-ceiling`, ran
`python research/pinrun.py --selftest` (green), ran `versioncheck` (green),
restarted live with `--price-ceiling 0.99` -- and the bot did not come back.
`pinrun` runs its own self-test at STARTUP with the flag already applied, and
four older checks assert the 98c ceiling against the RUNNING `PRICE_CEILING`
(`worst_close_cost`, `ladder_under`, two A45 room checks). They failed, the
process wrote "self-test failed -- nothing ran", and real money sat idle until
Joe said "Also the bot is down."

**Why `--selftest` did not catch it:** it runs with the defaults. The startup
self-test runs with the flags. They are different worlds whenever a flag moves
a constant that any older check hard-codes.

**How to apply -- before ANY live restart that carries a new or changed flag:**
1. Run the startup path in paper with the same flags and a tiny horizon, e.g.
   `python research/pinrun.py <all the live flags minus --live> --minutes 0.2`
   with `KALS_SELFTESTED` unset, and confirm `SELF-TEST PASSED` in its output.
   That is the only test that runs the checks against the flag.
2. Grep the self-test for the constant the flag moves (`PRICE_CEILING`,
   `BANK_BRAKE`, ...). Every hit that compares against the running value, not
   `_DEFAULT_*`, is a check that will fail under the flag.
3. `restart_bot.ps1` says "FAILED: pinrun did not come back" -- treat that
   line as an alarm, not a log line, and revert the flag first, investigate
   second. The revert is one edit; the investigation can wait.

Same family as the memory about asserting declared defaults; this is the
first time it has stopped real money. See
[[check-the-log-dates-against-the-deploy-first]] for the day's other trap.
