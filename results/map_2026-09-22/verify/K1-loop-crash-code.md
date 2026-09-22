# Verify K1-loop-crash (lens: CODE) -- IN PROGRESS

Verifier K1-loop-crash-code, 2026-09-22. Read-only. Scratch code:
`scratchpad/map/verify/K1-loop-crash-code/`.

Claim (06_code-and-infra.md F3): no self-test runs pinrun's trading loop; the
entry scan (~1,170 lines from ~9491) has no outer try, so any exception there ends
the process while holding; a fill is registered for hedging only after a logging
call full of round() args -- if that raises, the fill goes unhedged and uncounted.
All 3 in-loop crashes ~30 s before a close.

Code under test: research/pinrun.py sha256 6f6b1df38af6 (== live code_sha per 06).

## Status
- in progress
