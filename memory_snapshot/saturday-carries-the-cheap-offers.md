---
name: saturday-carries-the-cheap-offers
description: CORRECTED - 2026-09-13 was a SUNDAY not a Saturday; the weekend effect is real but the label was on the wrong day
metadata: 
  node_type: memory
  type: project
  originSessionId: 350e3ea1-7f0f-4b66-8f90-c31872b59750
  modified: 2026-09-20T02:19:50.995Z
---

**CORRECTED 2026-09-19. This note used to say "09-13 was a SATURDAY with ~2x
a weekday's cheap supply". 2026-09-13 was a SUNDAY.** The repo said Saturday
in `CURRENT_STATE.md` and `HANDOFF.md` too, and all of it was wrong.
`datetime.date.fromisoformat('2026-09-13').strftime('%A')` = `Sunday`. The
Saturdays are **09-12** and **09-19**.

**Check the day of week with the calendar, never from memory or from what a
repo file asserts.** One wrong weekday propagated into three documents and a
published finding.

**The WEEKEND effect survives the correction.** Share of our contracts bought
under 95c, live fills:

| day | dow | under 95c |
|---|---|---|
| 09-12 | Sat | 31.2% |
| 09-13 | Sun | **45.5%** (richest in the sample) |
| 09-18 | Fri | 6.0% |
| 09-19 | Sat | 10.2% |

So the weekend really is richer, and Sunday is the best day. What is
withdrawn is "Saturday carries twice a weekday's supply" -- that number came
off a Sunday.

**And the cheap end genuinely thinned, independent of our bet size.** The
fixed-20-contract paper arms (the size control) went from 32.3% under 95c on
09-13 to 15.2% on 09-19 -- roughly halved while holding size constant. So the
live decline is not just our bets growing 66 -> 106 contracts and walking
further up the ladder. Relates to [[baseline-error-is-our-recurring-bug]] and
[[supply-exists-we-arrive-late]].
