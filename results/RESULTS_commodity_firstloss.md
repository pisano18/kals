# The first commodity losses, and the defect that doubled them

**2026-09-17 ~20:2xZ.** The live commodity test was stopped by hand after two
losses inside one minute. **Both were the same market.** This is a write-up of
what happened and what was wrong, because the loss was not variance -- or not
only variance.

## What happened

`KXWTI15M-26SEP171615-15` settled YES. We held:

| when | side | price | contracts | window | outcome |
|---|---|---|---|---|---|
| 180 s left | NO | 0.9400 | 31 | wti-far (121-180 s) | LOST -$29.26 |
| 60 s left | NO | 0.9850 | 30 | wti-near (2-60 s) | LOST -$29.58 |
| 23 s left | YES | 0.9160 | 1 | wti-mid (16-45 s) | won |

**One adverse event became two losses.** The day finished -$53.06 on 28
settled trades, 26 of which won.

## The defect

`cmdlive` allowed **one bet per market per WINDOW**. That was wrong, and the
reasoning behind it was wrong in a way worth writing down:

**The windows are not independent opportunities. They are different moments to
look at the SAME binary outcome.** A second bet on the same side does not
diversify anything -- it doubles the stake on one event. And a bet on the
opposite side, which also happened here, locks in a guaranteed loss on one leg,
because the two cannot both win.

The intended exposure was $30 per trade. The actual exposure on that market was
**$58.84 on one side plus $0.92 on the other**. Across the day, 7 of 22 markets
carried more than one bet and **$67.72 of extra stake** went on beyond what the
sizing intended.

The crypto bot has a `both_sides` gate for precisely this. `cmdlive` had
nothing, because it was written when the size was one contract and the
consequence was pennies.

## The fix

One position per MARKET. The first window that FILLS claims the ticker
(`held[tk] = want`), and every later window on that ticker is refused before it
even prices, whichever side it wants. Claimed on the fill, not the attempt, so
a refused order cannot lock a market out. Self-tested on all three properties.

## What this does and does not say about the strategy

**It does not condemn the windows.** 26 of 28 settled trades won. The far
window that took the first losing leg is the one with 379 tape markets and 2
losses behind it; one loss is inside that.

**It does say the sizing was effectively double what was authorised** on a
third of the markets, and that the first real test of the brakes found a defect
rather than a bad market.

**The honest scoreboard after the scale-up:** 28 settled, 26 won, 2 lost, net
**-$53.06**. At one contract the same day would have been about -$1.75. The
loss is a consequence of size, and size is exactly what was just changed.

## Pending decision

Whether to resume, and at what size, is the operator's call. The defect is
fixed; the evidence base is unchanged (20 clean fills before today, now 26 wins
and 2 losses); and the statistical position is still that ~60 clean fills are
needed before the loss-rate ceiling drops under break-even.

## ADDENDUM: a third loss, found only because the operator asked

**The operator, 2026-09-17: "The gold lost 10? Didn't lose again?" He was right
and my answer was wrong.**

Killing the live process left FOUR positions open on the exchange. Killing a
process does not close positions -- they settle regardless -- and because the
bot was gone, nothing wrote a `settled` record for them. Our P&L reporting
reads those records, so it was blind to every one of them:

| market | side | price | n | outcome |
|---|---|---|---|---|
| KXWTI15M-26SEP171545-45 | yes | 0.9000 | 33 | won +$3.30 |
| KXGOLD15M-26SEP171545-45 | yes | 0.9500 | 31 | won +$1.55 |
| KXWTI15M-26SEP171700-00 | no | 0.9840 | 10 | won +$0.16 |
| **KXGOLD15M-26SEP171700-00** | **no** | **0.9790** | **10** | **LOST -$9.79** |

**Corrected commodity total for 2026-09-17: 32 settled, 29 won, 3 lost, net
-$57.84** (not the -$53.06 reported while those four were in flight).

The gold loss was in the `gold-far` window (91-180 s at 95-99c), the cell with
379 tape markets and 2 losses behind it. One live loss there is inside that
rate; it is not evidence the window is wrong. What it IS evidence of:

**LESSON: stopping the process is not stopping the exposure, and our reporting
cannot see what the process did not settle.** Any future "turn it off" needs to
either wait for open positions to settle before reporting a total, or read the
exchange directly for tickers with a fill and no settlement. The check is two
lines against `/markets/<ticker>`; it should be part of the stop path, not
something a person has to notice.
