# PRE-REGISTRATION -- Coin Race paper arm, ARM3. Written 2026-09-15 ~21:40Z, before any arm3 bet.

## Why arm3 exists
arm2 lost on paper: **73 bets, 44 won, -$1,560** at 250 contracts a bet, over 12
races on 2026-09-15. No wiring bug -- every bet was the right coin and side. The
losses were photo finishes (every late-window loss had a lead under 1.4bp, priced
65-78c by the market and ~89c by the table) and cheap bets placed while the race
was still open. Operator: "Well the goal is to make money so."

## The rule, fixed now
`research/pinracearm.py --tau-max 30 --min-gap-bp 4 --min-price 0.90 --one-per-race-band`

- only the last 30 seconds (RESULTS_coinrace: market efficient before tau 30)
- only a lead or deficit of at least 4bp (no 4bp+ lead overturned at tau <= 25 in
  795 races; the tape's 93c+ NO winners in pinraceno all had gaps past 4bp)
- never cheaper than 90c (the discount cliff)
- at most one bet per race per time band

**Honest caveat:** the 4bp and 90c lines were chosen after seeing arm2 lose. They
also rest on older evidence (the gap table, pinraceno, RESULTS_coinrace), but this
is NOT a clean out-of-sample rule. That is why the bar below is strict.

## The bar -- decided before the data
Counted in BETS, reported with the number of distinct RACES.

- **KILL** the race idea if, at any point before 30 bets, **3 bets have lost**.
  At a ~95c average price, break-even is ~5 losses in 100; 3 in the first 30 is
  ~10 in 100.
- **KILL** at 30 bets if paper P&L is **zero or negative**.
- **CONTINUE** (to a live penny test, which needs its own operator sign-off) only
  if at 30 bets: paper P&L positive AND at most 2 losses.
- **KILL** if 14 days pass with fewer than 30 bets and paper P&L is not positive.

## What even a pass would be worth
The tape showed roughly 1-2 such chances a day (pinraceno: 11 legs at 93c+ in 240
hours). At the live bot's current 77 contracts and ~3-5c a contract that is about
**$2-8 a day** -- small next to the main bot. A pass makes it a side income, not a
second engine.

## Not claimed
Paper fills are assumed. Winning the fill, and adverse selection on the fills we
do get, are untested by any paper arm.
