---
name: bash-heredoc-halves-backslashes
description: "In this harness's Bash tool a quoted heredoc still halves backslashes, so a Python script inlined that way gets `\\r` where `\\\\r` was written; write scripts with the Write tool instead."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 47b37ac1-655c-4d72-a81b-a48e9625d5bd
  modified: 2026-09-25T03:19:14.417Z
---

A Python script passed through `python - <<'EOF' ... EOF` in the Bash tool
received `"C:\kals-repo\restart_bot.ps1"` when `"C:\\kals-repo\\restart_bot.ps1"`
was written: the `\\` pairs collapsed to `\`, Python then read `\r` as a
carriage return, and a VERSIONS.md revert command shipped as
`C:\kals-repoestart_bot.ps1` (2026-09-25, two extra commits to repair).

**Why:** the quoted heredoc is supposed to be literal, but the tool's
transport halves backslashes before bash sees them.

**How to apply:** any inline script containing a Windows path or a regex
goes into a scratch `.py` file with the Write tool and is run by path. If a
heredoc must be used, write raw strings with SINGLE backslashes and check
the output bytes with `od -c` before committing. Related:
[[process-query-matches-own-shell]].
