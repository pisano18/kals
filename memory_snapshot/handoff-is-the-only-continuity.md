---
name: handoff-is-the-only-continuity
description: "Joe works the kals project across desktop, phone and CLI and expects sessions to carry over; they do not, so the repo docs must be updated as the work happens."
metadata:
  node_type: memory
  type: project
  modified: 2026-09-25T07:09:56.170Z
  originSessionId: 47b37ac1-655c-4d72-a81b-a48e9625d5bd
---

Joe runs this project from the Claude desktop app, phone, and the CLI, and
asked on 2026-09-06 whether the CLI session was literally the same one he had
been talking to (it was not -- no prior conversation was in context). He
clears context regularly to save tokens (2026-09-17, 2026-09-25, ...).

**Why:** he reasons about the work as one continuous conversation, so anything
established in a session but not written to the repo is simply lost, and he
will not know it is missing.

**Where continuity lives (as of 2026-09-25):** `C:\kals-repo\CLAUDE.md` (loaded
every turn; its top table says where to read what) -> `CURRENT_STATE.md` (read
first) -> the top section of `HANDOFF.md` (newest first; sections before
2026-09-23 are in `HANDOFF_ARCHIVE_2026-09.md`) -> `OPEN_WORK.md` (his topic
index) -> `results/VERSIONS.md` and `results/IDEA_LEDGER.md`. The dated
`HANDOFF_2026-09-14.md` / `HANDOFF_2026-09-17.md` files are historical.

**How to apply:** write findings into HANDOFF.md as part of doing the work,
not as a closing chore -- newest entry at the top. State what changed, what it
does NOT change, and what is still undecided. Keep CURRENT_STATE.md and
OPEN_WORK.md true in the same commit. Do not assume he remembers a number from
an earlier session, and do not assume a number he cites is one this repo
actually produced; check it against the results logs. (This note once said
"there is no CLAUDE.md in this repo" -- false; it has one.) See
[[open-work-is-the-topic-index]], [[next-session-first-jobs]].
