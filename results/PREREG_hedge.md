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
4. **No hedge ever increases a loss** beyond the unhedged amount, i.e. the
   hedge leg's price is always < (1 - entry cost) + entry cost = it never
   pays above the ask that makes the pair cost > $1.00 + fee. Enforced in
   code as a hard refusal, and counted.

**Any one failing at n=30 = the hedge is disabled and the reason logged.**
All four passing = it stays on and the next review is at n=100.

## What would make this an artefact

- The tape loss population differs from ours (0.67% vs ~2-5%). The belief
  PATH is index-driven and should transfer; the PRICE we can sell at may not.
  Bar 2 catches that.
- Winners that dip below the threshold and recover: cost us the hedge. Bar 1.
- Latency: our round trip is ~100ms; a one-second collapse leaves no time.
  Those are counted as fired-but-unrecovered and hurt bar 2 honestly.

## Not amended. If this bar moves, the move is dated and explained here.
