---
name: money-sweep-playbook
description: "\"run the money sweep\" means research/sweep/README.md (multi-agent Workflow over every Kalshi/Polymarket market family); every idea ever checked lives in results/IDEA_LEDGER.md -- read it before proposing any money idea."
metadata:
  node_type: memory
  type: reference
  originSessionId: 47b37ac1-655c-4d72-a81b-a48e9625d5bd
  modified: 2026-09-25T06:31:25.938Z
---

The operator asked on 2026-09-25 for a reusable, re-runnable version of the
multi-agent "find any way to make money" sweep. It lives in the repo:

- `research/sweep/README.md` -- the playbook (steps, args, cost).
- `research/sweep/money_idea_sweep.js` -- the Workflow script; `args.date` is
  required, `focus` / `bank` / `extra` / `maxCheck` / `limit` optional.
- `research/sweep/sweep_catalogue.py` -- builds `.sweep/catalogue/` (skips the
  millions of parlay markets via `mve_filter=exclude`).
- `results/IDEA_LEDGER.md` -- every idea ever checked, status and reason, plus
  HOT AREAS and UNRESOLVED. Each run reads it first and updates it last.

**Why:** the operator wants to say "do it again" later without re-explaining,
and each run should skip dead ideas and push unresolved ones to a verdict.

**How to apply:** before proposing ANY new money idea in any session, check
the ledger; if it is dead there, only raise it with a new angle stated. After
any money research, add its row. Related: [[measure-then-ship-only-positive]],
[[next-session-first-jobs]].
