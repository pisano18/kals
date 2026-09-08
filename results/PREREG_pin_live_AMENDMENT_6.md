# AMENDMENT 6 — more bets, without more risk per bet

**Written 2026-09-08 BEFORE deployment, per the standing rule that a bar is
never moved after seeing a result without saying so loudly.**

The operator's instruction: *"Being able to place more bets would be the most
beneficial thing... if you test something and it's good, push it."*

Two changes. **Neither raises the maximum exposure of a close.** That is the
constraint I held myself to, because the account cannot fund more.

---

## Change 1 — a scale-in slot is consumed by a FILL, not by an attempt

**The bug.** `fired[close_s]` was written when the SIGNAL fired, *before* the
order was sent. So an order that filled **zero** contracts still burned one of
`MAX_PER_CLOSE` and still raised the improve bar by `IMPROVE_BY`.

**This is not hypothetical.** 5 of our first 19 live orders filled nothing, and
**depth was not the cause** — the misses had 562, 107, 93, 10 and 5 contracts
on offer against the 1 to 10 we asked for. They were lost races. They will keep
happening.

**Measured** on 1,196 eligible moments over 83 closes, at the observed 26% miss
rate, expected P&L at the 0.90% flip rate:

| | closes won | buys | contracts | expected |
|---|---|---|---|---|
| a no-fill BURNS a slot (today) | 67 | 87 | 870 | $40.29 |
| **a no-fill keeps the slot** | **80** | **119** | **1,190** | **$53.72** |

**+32 buys, +33.3% expected profit.**

**Maximum exposure is UNCHANGED.** The cap always meant two *fills*; the bug
made it two *attempts*. An unfilled order creates no exposure and must not
consume an exposure budget. This is a correctness fix, not a loosening.

---

## Change 2 — take a PARTIAL rather than skip the moment, down to half

**The bug.** `if size < max(MIN_LEVEL, SIZE): continue` threw away any moment
offering fewer contracts than we wanted. At size 10 a 9-contract offer was
refused outright, even though an immediate-or-cancel order fills 9 happily.

**Measured**, same population, expected P&L:

| threshold | buys | expected | vs today |
|---|---|---|---|
| take only a full size (today) | 124 | $59.75 | — |
| **≥ 50% of size** | **125** | **$60.53** | **+1.3%** |
| ≥ 25% of size | 128 | $60.11 | +0.6% |
| ≥ 5% of size | 129 | $58.37 | **−2.3%** |

At size 25 the same sweep gives **+5.4% at the 50% threshold**.

**Taking ANY scrap is worse than taking none**, and that is the interesting
part: a tiny early fill burns a scale-in slot and raises the improve bar, so it
trades a big cheap buy later for a small dear one now. **Half is the measured
optimum at both sizes tested.** `MIN_FILL_FRAC = 0.50`.

**Exposure can only fall.** We buy `min(SIZE, offered)`, never more.

---

## What was measured and REJECTED

**Raising `MAX_PER_CLOSE` from 2 to 3** measured **+26.7%** expected profit —
larger than either change above. **It is not deployed because it cannot be
funded.** Worst close would be $30 against a $38.83 balance, and the loss-abort
rail would require a brake at −$45 or looser, which exceeds the account. It
becomes the best available change the moment the account is funded.

---

## Revert

`MIN_FILL_FRAC = 1.0` restores the old dust gate. Moving `_book_slot()` back
above the order restores the old slot behaviour.

## Revert triggers

- **Any fill above 98.8¢** — the ceiling is not binding, check `MEASURED_FLIP`.
- **Live flip rate above 2.31%** (the exact one-sided 95% bound on 3 in 333) —
  every threshold in this system is derived from 0.90% and would need
  re-deriving.
- **Average price paid across a close exceeding the first fill's price** over
  50+ closes — the scale-in mechanism has reversed.
- **Partial fills below half size appearing in the log** — `MIN_FILL_FRAC` is
  not binding.

## Sample this rests on

83 closes, **zero flips**. Every number above is an EXPECTED value at an
imported 0.90% flip rate, not a realised one. Realised P&L in a zero-flip
sample is a monotone function of contracts bought and would rank nothing.
