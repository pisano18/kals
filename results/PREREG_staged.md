# PRE-REGISTRATION -- AMENDMENT 46, STAGED EARLY ENTRY (tau 45, half a bet, top up at 30)
## Written 2026-09-17 ~14:0xZ, before the staged paper arm's first fill

**Rule:** a bar is never moved after seeing a result without saying so loudly.

**AMENDED 2026-09-17 ~15:1xZ -- THIS WENT LIVE BEFORE STAGE 1's BAR WAS MET,
ON THE OPERATOR'S EXPLICIT INSTRUCTION, AND THAT IS RECORDED HERE RATHER THAN
QUIETLY.** His words: *"As long as you have the 45 second is built as safely
as you described, deploy now"*, and *"Bump it down to 1/3 the current size
instead of half."* Stage 1 below asked for 30 paper closes and 20 early
markets; the staged arm had run about 20 minutes. What was in hand instead:
the flat tau-45 arm's 27 bets / 27 won over 9.2 h (3x the control's bets,
+0.03c on shared markets) and `pinbefore`'s index measurement (0.058% model
error at 31-45 s vs 0.021% at 21-30 s). **Stage 2's live bar is unchanged and
now governs.** The paper arms keep running as the comparison they were built
to be.

## The operator's instruction, 2026-09-17

*"implement tau 45 in a safe way. Maybe not buying full coins and topping up
what's available once we hit the normal purchase point? Perhaps that normal
purchase point will need to be a hedge sometimes? I'm not sure, do what's
smart and safe and track it heavily so we know how it performs."*

## The rule as built (`staged_take()` in `pinrun.py`)

- With 31-45 s left, a market that passes EVERY existing gate may be bought
  for at most **EARLY_FRAC x SIZE**: the EARLY leg. One per market; a second
  early look is refused (`early_once`).
  **DEPLOYED LIVE 2026-09-17 at EARLY_FRAC = 0.333** (the operator: "Bump it
  down to 1/3 the current size instead of half"). The paper arm that was
  started before the deploy runs at 0.5; when comparing, the live legs are a
  third and the arm's are a half.
- With <= 30 s left, a market holding an early leg may be **TOPPED UP to SIZE**
  if the same gate still passes at that moment's price (AMENDMENT 29 already
  exempts an unfinished position from the re-buy band). Never past SIZE.
- If belief has collapsed by then, the top-up fails the confidence gate and
  the hedge pass (AMENDMENT 15, every open position, every second) buys the
  other side at belief < 0.60. That is the "needs to be a hedge sometimes".
- Markets with no early leg are bought exactly as today.
- Every `signal` and `order` record carries `leg` (full / early / topup) and
  `early_held`, and refusals `early_once` / `staged_none` are recorded, so the
  three populations can be scored separately.

## What is known

- Index alone (`pinbefore`, 14,261 closes): model wrong 0.058% of moments at
  31-45 s vs 0.021% at 21-30 s at the live bar. Model error is ~1/200th of
  the live loss rate; the unknown is adverse selection at 31-45 s.
- The flat tau-45 paper arm, first 9.2 h, read at the operator's instruction:
  27 bets / 17 closes, 0 lost; 19 NEW bets (only exist because of 31-45 s) on
  11 closes, 0 lost; on 8 shared markets it paid +0.03c vs the control. Zero
  of 27 is p~0.28 at a 4.7% loss rate -- not evidence of safety yet.
- Half a bet early + top-up caps the early exposure at half of today's
  per-market worst case, and the top-up is a bet we would make today anyway.

## STAGE 1 -- paper. Arm: live flags + `--early-tau 45 --early-frac 0.5`.

Compared with the control (pid 411820) and the flat tau-45 arm (pid 478072).

**Minimum before reading:** 30 settled closes in the staged arm, and 20
markets with an EARLY leg.

**Kill:** early legs lose 3 of their first 30 markets, or the early
population is net negative at 30 markets, or top-ups pay more than 1.0c above
the early leg on average (the "top-up" is then buying into a move against us).

**Proceed to live:** early population <= 1 loss in 30 and net positive; the
staged arm's bet count at least 1.5x the control's on the same closes.

## STAGE 2 -- the LIVE bar, decided now

Deploy = `EARLY_LIVE_OK = True` in a commit citing this file, `--early-tau 45
--early-frac 0.5` in `restart_bot.ps1`, a `v-staged` entry in VERSIONS.md with
the revert, `versioncheck` clean.

Scored over the first **40 live closes with an early leg**:

1. **Loss rate on closes with an early leg <= 6.0%** (all-time live 4.66%).
   At 3 losses in the first 40, or 2 in the first 15, revert immediately.
2. **Early legs that were later topped up: the top-up price within 1.0c of
   the early price on average.** Wider means the early leg is being sold to
   us ahead of a move.
3. **Early legs NOT topped up (gate failed at <= 30 s): their loss rate is
   reported separately.** If it exceeds 15% at 20 such legs, EARLY_FRAC drops
   to 0.25 or the window to 40 s -- a stated change, not a silent one.
4. **Net positive on those 40 closes.**

## Kill criterion for the idea itself

At 40 live early closes, if the extra bets are under +25% of today's count or
the money per close is below the control's, the window closes back to 30 and
this file records it.

## What is NOT being proposed

No change to PIN, the ceiling, the edge floor, the hedge trigger, SIZE, the
close budget, or `TAU_MAX` itself (the frozen rule stays 30 for FULL bets).
Not 46-60 s. Not combined with one-coin depth in the same arm.
