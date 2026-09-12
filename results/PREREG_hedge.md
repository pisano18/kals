# PRE-REGISTRATION -- AMENDMENT 15, the belief-collapse hedge
## Written 2026-09-12 08:1xZ, BEFORE the code exists and BEFORE any live hedge

**Rule:** a bar is never moved after seeing a result without saying so
loudly. This file states the bar first.

## What is being deployed

For every open position, once per second, recompute the model's belief that
our side wins (the same `fair()` the entry uses). If belief falls below
`HEDGE_BELIEF`, buy the OPPOSITE side for the contracts we hold, at the best
ask, through the existing `pintake.take()` path. The pair then pays exactly
$1/contract at settlement whatever the result; the loss is locked at
(entry cost + hedge cost - 1.00) instead of the full entry cost.

`HEDGE_BELIEF` will be chosen by a pinsim sweep over {0.70, 0.80, 0.90} on
DAYS NOT USED in any analysis above (the 48h ending 2026-09-12 05:00Z is
used; the holdout is everything before it that the tape holds). The choice is
made on the holdout and then frozen here before the first live hedge.

## Evidence it rests on (in-sample, stated as such)

- Live: 4 dissected losses. 3 gave >= 14 seconds of warning at a 70% alarm;
  the fourth (SOL 08:00) gave 1 second at 70% and ~2 seconds at 90%.
- Tape 48h, 1,653 entries: 1,630/1,642 winners never below 99% belief;
  11/11 losers below 20%. 70% alarm: 2 false alarms, 11/11 caught.
- Exit prices in the alarm second on the 11 tape losers: mean ~49c
  recoverable of 96c. Treated as a CEILING (we sell into a collapse).

## THE LIVE BAR -- pass/fail, decided before the first hedge fires

Scored over the first **30 live hedge events** (a hedge event = the alarm
fired on a position we hold, whether or not the hedge order filled):

1. **False-alarm rate <= 3%** of positions held. Tape says 0.12%; the bar is
   25x looser to allow for the live/tape gap this project has measured
   everywhere else.
2. **Mean recovery >= 25c per hedged contract** on hedges that fired on
   eventual losers (i.e. the hedge leg's cost <= 75c on average). Tape
   ceiling is 49c; the bar is half of it.
3. **Hedge fill rate >= 60%.** An alarm that cannot be acted on is not a
   hedge. The race is the oldest open risk here and this measures it.
4. **No hedge ever increases a loss** beyond the unhedged amount. Enforced in
   code as a hard refusal, and counted.

   **CORRECTED 2026-09-12 08:4xZ, BEFORE ANY LIVE HEDGE, and this is a bar
   move so it is dated and explained.** The first wording said "the pair must
   cost under $1.00". That is WRONG and the self-test caught it: holding 20
   NO at 96c and buying 20 YES at 35c pays 131c for a $1 payout -- a 31c loss
   that BEATS the 96c loss from holding. The pair being over a dollar is the
   normal, helpful case. The correct boundary: locked loss = entry + ask - 1,
   unhedged loss = entry, so a hedge helps exactly when **the hedge leg's ask
   is below $1.00**, whatever the entry was. `hedge_ask_ok()` enforces that;
   a $1.00 leg is refused because it locks exactly the unhedged loss and the
   fee makes it worse. The old rule would have refused nearly every real
   hedge and made this whole amendment inert.

   Separately recorded on every hedge, NOT as a gate: `edge_c` =
   (1 - belief) - ask, the cents by which the hedge leg is cheaper than the
   model's own fair value for that side. Positive = the market lags the
   collapse and the hedge is +EV on its own; negative = we are paying EV for
   variance reduction. The n=30 review reads its mean.

**Any one failing at n=30 = the hedge is disabled and the reason logged.**
All four passing = it stays on and the next review is at n=100.

## What would make this an artefact

- The tape loss population differs from ours (0.67% vs ~2-5%). The belief
  PATH is index-driven and should transfer; the PRICE we can sell at may not.
  Bar 2 catches that.
- Winners that dip below the threshold and recover: cost us the hedge. Bar 1.
- Latency: our round trip is ~100ms; a one-second collapse leaves no time.
  Those are counted as fired-but-unrecovered and hurt bar 2 honestly.

## BAR MOVE 2026-09-12 09:0xZ -- deployed BEFORE the pinsim holdout, at the operator's call

The section above said the threshold would be chosen from a pinsim holdout
before the first live hedge. The holdout was OOM-killed twice (see HANDOFF)
and its third run was ~90 minutes from done when the operator wrote: "I'm not
sure if your backtest actually [works]... I'm tempted to just tell you to push
the change... Continue hunting once this is pushed." That is the owner's
decision, and pinsim is certified for DECISION reproduction only, so his
doubt is on the record as fair.

**What ships:** HEDGE_BELIEF = 0.90, the coded default, chosen because it
fires one second earlier than 0.70 on the fast collapses (SOL 08:00: 84% at
tau 16, 0.05% at tau 15) at a tape false-alarm cost of 4/1,642 vs 2/1,642.

**What does NOT move:** the live bar at n=30 above, all four rules, and the
"any one failing disables it" clause. The holdout will still be read when it
finishes and may change the threshold; that change, if made, is a separate
dated entry.

## PILOT 2026-09-12 09:1xZ -- one-contract hedges first, at the operator's explicit sign-off

Operator: "If you want to buy one share of a losing coin to attempt the hedge
at a tiny scale you can do that." Also, in the same message: "I don't want to
lose money," and the division of labour -- Fable for thinking, planning and
new ideas; Opus for grunt work.

**What changes:** `HEDGE_PILOT_CONTRACTS = 1`. When belief collapses on a
live position, the hedge buys ONE contract of the opposite side and is then
done for that position; the other contracts ride unhedged exactly as before
this amendment. Cost of a pilot event: under $1. Purpose: prove the live
mechanics -- does the order fill, at what price against the ask we saw, do
both legs settle and book correctly, does the A8 guard stay quiet -- before
a $19 position depends on them.

**What it costs:** during the pilot a collapse still loses ~$18 instead of
~$9. That is the price of not discovering a mechanics bug on a full-size
event, and the operator chose it.

**Exit from the pilot:** after THREE hedge events with (a) a fill, (b) fill
price within one tick of the ask recorded in the alarm, (c) both legs
settled with the locked loss matching `locked_loss_c` to the cent, the pilot
is lifted to full size. That lift is a dated entry here. The n=30 live bar
above counts pilot events as events; recovery per hedged contract is
measured on the hedged contract.

## REVERSAL 2026-09-12 09:3xZ -- the one-contract pilot was MY MISREADING; full size restored

The pilot above ran live for roughly 30 minutes (pid 850344, 09:19Z to
~09:35Z). No hedge event occurred in that window. The operator's correction,
verbatim: "Wait no don't hedge a real 20 contract buy with just 1 as a test,
do all 20. For the test I meant buy 1 of a losing coin, then test the hedge
with 1."

He is right and I read him wrong. Capping the hedge on REAL positions at one
contract left real money under-hedged for the sake of a test. What he meant
is a self-contained planted test: deliberately buy ONE contract of the side
that is about to lose, on a market already decided, and let the hedge fire
on that one. Cost: a few cents (the losing side of a decided market is ~3c;
the hedge leg ~97c; the pair pays $1). It exercises fill, price-vs-ask, both
legs settling and the A8 guard, with nothing else at stake.

**What changes:** `HEDGE_PILOT_CONTRACTS = None` (full-size hedges on real
positions, as A15 was designed). A `--hedge-plant` mode is being added for the
planted test; it runs once, at the operator's per-instance sign-off already
given in that message, and is off by default.

**The exit criteria written for the pilot now apply to the planted test
instead:** fill, price within one tick of the alarm's recorded ask, both legs
settled with the locked loss matching `locked_loss_c` to the cent.

## If this bar moves again, the move is dated and explained here.
