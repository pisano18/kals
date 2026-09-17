# PRE-REGISTRATION -- AMENDMENT 47: THE MARKET MUST AGREE BEFORE WE PAY FOR INSURANCE
## Written 2026-09-17 ~16:3xZ, before the `--hedge-price 0.50` paper arm has hedged once

**Rule:** the bar is written before the number is seen. **Disclosure, because
it matters:** the IDEA came from looking at our seven past live hedges. Those
seven are the motivation, not the evidence, and they are not counted toward
the bar below. The bar is scored on hedges the arm makes FROM NOW.

## What changes

`--hedge-price P` (shipped OFF; `HEDGE_PRICE = None`). With it set, a hedge
fires only when **both** are true:

1. the model's belief in our side has fallen below `--hedge-belief` (0.60), and
2. **our side's own market price is below P** (0.50).

We buy the opposite side at its ask, so our side is trading at about
`1 - ask`; the test is `1 - ask < P`. A position that fails only (2) is **not
retired** -- the loop keeps checking, and if the price does fall through 50c
later in the same close, the hedge fires then. Waiting, not refusing.

## Why, and what makes it more than a curve fit

`research/pingrid.py`'s wobble screen, **1,717 crypto markets** over 5 days.
Take every market whose favourite was at 90c+ with a minute left, and bucket
it by the LOWEST price that favourite traded at inside the last 30 seconds:

| favourite fell to | markets | favourite LOST |
|---|---|---|
| stayed 90c+ | 1,511 | 0 |
| 80-90c | 17 | 0 |
| 70-80c | 16 | 0 |
| 50-70c | 15 | 0 |
| **under 50c** | **158** | **120 (76%)** |

**48 of 48 dips that stopped above 50c recovered.** A crossing below 50c was a
real flip three times in four. The 50c line is the TABLE's own boundary, not a
threshold fitted to our hedges -- which matters, because the second-best fit
to our own seven hedges was 55c and would have been a curve fit.

Our model's belief does not know this. It re-prices from the index alone and
panics at moves the market shrugs off.

## The motivating seven (NOT evidence -- disclosed, then set aside)

Of 14 live hedges, 7 fired at a belief under today's 0.60 gate (the rest fired
under the older 0.80 and 0.90 gates and could not happen now):

| our side's price | belief | outcome | $ |
|---|---|---|---|
| 5c | 0.020 | needed | +0.05 |
| 19c, 19c | 0.525 | needed | +0.19, +1.79 |
| 42c | 0.214 | needed | +24.18 |
| 49c | 0.559 | needed | +29.30 |
| **85c** | 0.485 | **wasted** | **-13.83** |
| 53c | 0.533 | needed | +0.51 |

A 50c price filter skips the 85c one (+$13.83) and the 53c one (-$0.51), for
+$13.32 over five days. **n = 7. That is an anecdote with arithmetic on it.**

## THE BAR, fixed now

Arm: the live flags plus `--hedge-belief 0.60 --hedge-price 0.50`.
Control: the existing `--hedge-belief 0.60` arm, same flags otherwise.

**Minimum before anything is read: 12 hedge ALARMS in the arm** (an alarm is
belief crossing 0.60, whether or not the price test then let it through), and
30 settled closes in each arm. Alarms are the population; hedges are the
subset the filter passes, so scoring on hedges alone would hide exactly what
the change does.

**KILL (A47 is closed, the flag stays off):**

1. Of the alarms the filter SKIPPED, **3 or more would have been needed
   hedges** (our side went on to lose). The filter is then throwing away
   insurance we wanted.
2. The arm's net dollars over those closes are worse than the control's.

**PROCEED to a live test (not a deployment):**

1. At most 1 skipped alarm turns out to have been a needed hedge, AND
2. the arm skipped at least 4 alarms that were wasted hedges in the control, AND
3. the arm's net dollars beat the control's over the shared closes.

Anything between: run to 25 alarms and re-read at the same bars. **No
threshold is moved to make it pass**, and 0.50 is not re-tuned after seeing
results -- if 0.50 fails, A47 fails.

## What is recorded

`hedge_wait_price` (ticker, the opposite ask, our implied price, the
threshold, belief, tau) once per position, plus the existing `hedge_alarm`,
`hedge`, and `settled` records. The skipped population is therefore
reconstructable: every alarm that did not become a hedge has a reason on file.

## Revert

The flag is off in `restart_bot.ps1` and in the live bot. Nothing to revert
unless it is deployed; if it ever is, removing `--hedge-price 0.50` from
`restart_bot.ps1` and restarting is the whole revert.
