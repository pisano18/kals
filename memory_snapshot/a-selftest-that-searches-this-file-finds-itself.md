---
name: a-selftest-that-searches-this-file-finds-itself
description: "Source-text self-tests that use index() on a literal match their OWN copy of that literal first; use rindex or anchor after an offset. Bit four times in one session, one silently for days."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4b086199-b082-458d-9cf9-786f0eb4321e
  modified: 2026-09-19T20:56:31.661Z
---

A self-test that reads its own file and does `src.index("<literal>")` finds
**the literal inside the test itself**, not the code it means to check. Four
times in the 2026-09-19 session:

- `index("HEDGE(paper)")` matched the test's own string, so an A63 check
  failed on its own text.
- `index('_gate("close_budget"')` reported the crashing fields still present
  when the real gate was clean -- nearly a false "not fixed" in a handover.
- `pindesk`'s `index("        threading.Thread(target=worker")` matched a
  more deeply indented line 1300 lines EARLIER, producing an empty slice --
  so `selftest()` raised `ValueError` and **none of the Refresh-button checks
  had ever run**, for days.
- the `def apply():` slice, same shape.

**Why:** the failure is silent or misdirected. A raising self-test looks like
a broken test, not a broken product, so nobody reads the output.

**How to apply:** use `rindex`, or find the start anchor first and search
AFTER that offset (`s.index(needle, start)`), and write in the comment why.
Add a check that the slice is non-empty -- `ck(len(slice) > 200, ...)` --
because an empty slice makes every check below it raise instead of fail. Same
family as [[a-gate-must-never-block-a-hedge]]: a test that cannot fail
correctly is worse than no test.
