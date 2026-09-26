---
name: next-session-first-jobs
description: "RAISE IN FIRST REPLY -- 2026-09-26: read the top of HANDOFF.md 'PICK UP HERE'; operator approved: combine the Kalshi cash pools, run the reward test, the Polymarket wire test; permission rule P0 first"
metadata:
  node_type: memory
  type: project
  originSessionId: 47b37ac1-655c-4d72-a81b-a48e9625d5bd
  modified: 2026-09-26T07:21:53.059Z
---

The 09-24..26 session ended 2026-09-26 ~07:30Z and its context is gone. **Read
the top section of `C:\kals-repo\HANDOFF.md` ("PICK UP HERE") before anything
else** -- it holds the operator's last message and jobs P0-P7 in order.

Short version:
- **P0:** real-money orders from the Bash tool are blocked by Claude Code's
  auto-mode classifier. The operator was given a one-liner (in HANDOFF) that
  adds `Bash(python research/polyorder.py:*)` and `Bash(python research/ordercli.py:*)`
  to `.claude/settings.local.json`. Check it is there; run those tools with the
  command STARTING with `python research/...` (no `cd &&`, no env prefix).
  Never edit the permission file yourself.
- **P1 combine the cash (approved)**, **P2 run the reward test (approved)**,
  **P3 Polymarket wire test (approved: "do what you want on polymarket")**.
- **P4** Polymarket paper read ~09-28; **P5** bars ~10-01/02; coin race: not yet
  ready to size up.
- Live: v-scalein-caps on v-safety2 (pid 2951024 at the end of the session).

See [[operator-context-virginia]], [[money-sweep-playbook]],
[[bash-heredoc-halves-backslashes]], [[handoff-is-the-only-continuity]].
