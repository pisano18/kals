# PREREG_hedge_margin -- "insurance only when the price is clearly through the line" -- written 2026-09-27 ~07:5xZ, BEFORE any further alarm is read

## The finding that motivates it (our own fills; every number in-sample)

Of the 22 markets the live bot has ever hedged (09-12..09-27), 9 were false
alarms (our side won anyway) costing $263, and 13 were real saves worth $234:
insurance is about break-even. All three week-2 false alarms were photo
finishes: the settle ended within a hair of the strike (XRP 09-19 23:45 ET
-$67, BNB 09-26 10:30 -$58, ETH 09-27 02:30 -$46; 88-104 contracts each), and
at the alarm the projected settle was NOT yet clearly through the line.
Candidate ruler A: skip the hedge when the projected settle is less than
2 rounding steps past the strike against us (2 cents on BTC/ETH/BNB; a stale
or unreadable index counts as "hedge"). Replayed on the 22 markets it removes
all 3 week-2 false alarms (+$172) and gives up 1 real save (BNB 09-19 12:30,
-$21): +$151, all of it in week 2, $0 in week 1 (it never fires in a quiet
week). Candidate ruler B: skip when the projected margin against us is under
half the model's own uncertainty width (0.5 sd of the remaining-prints mean).
On the index feed (ALL 15-minute markets, not our fills -- what the index did,
labelled as such) hair-over crashes came back 47 in 100 against 23 in 100 for
deeper ones (chance about 7 in 100 that this is luck); ruler B separated them
better there (about 1 in 100).

Why this is not deployed: three events on three nights, thresholds chosen after
seeing them; with 22 hedged markets the record can only tell a $372 difference
from luck. The 0.40 panic rule ("nothing may block a hedge") stands until this
bar is met -- this file changes nothing in the bot.

## What is measured (no code, no risk)

The live bot already writes, for every alarm, the belief, seconds left, the
projected margin (signal spot/strike/sigma; the index file has the prints) and
the outcome. Each hair-over alarm the bot hedges is one reading under BOTH
rulers at once: did our side come back (the hedge was a false alarm) or not.

## The bar (decided now)

Read after the NEXT 5 alarms whose projected margin against us is under
2 rounding steps (ruler A) -- expected about 17 days at the recent rate -- and
in any case not before 2026-10-10:

- **ADOPT ruler A (skip the hedge under 2 steps)** if, over ALL hair-over alarms
  on record (the 4 before this file plus the new 5 or more), our side came back
  in at least 6 of 9, AND the dollars that skipping would have saved exceed
  the real saves it would have given up by at least $60.
- **ADOPT ruler B instead** if B's split of the same alarms is cleaner (fewer
  real saves skipped for the same false alarms avoided) by at least one event.
- **KILL both** if our side came back in fewer than 4 of the 9, or if a single
  skipped hedge would have cost more than $120 at the size then running.
- **Break-even reference:** skipping a hair-over hedge pays only if such
  crashes come back more than 31 times in 100 (hedge at ~69c on ~90
  contracts: +$46-67 when right, about -$60 when wrong at today's size).

Whatever adopts goes in as a flag (`--hedge-min-margin-steps` or
`--hedge-min-margin-sd`), entry of the HEDGE path only, with a VERSIONS entry,
the startup path run in paper with the live argv, and this file's read quoted.

Related: results/WHY_NO_MONEY_2026-09-27.md (P3), results/RULESET_2026-09-27.md,
results/HEDGE_FLIP_2026-09-25.md (0.40 beats earlier/later/half), the
photo-finish study (scratchpad pf/measure/PHOTOFINISH.md; 4 of 20 hedges under
1 step, 3 false; power 0.33).
