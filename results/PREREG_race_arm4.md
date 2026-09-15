# PRE-REGISTRATION -- Coin Race paper arm, ARM4 (fair value). Written 2026-09-15 ~22:40Z, before any arm4 bet.

## The model
`research/pinracefair.py`: each coin's final return = locked + spot-imputed
projection + a random part whose covariance is the five-coin covariance of
1-second returns (3600 s ruler, 300 s fallback while the arm warms up) times the
variance-collapse factor `r(r+1)(2r+1)/6/3600` (+ `tau - 60` before the window).
P(win) by simulation. kappa 1.0 and the 3600 s ruler were chosen on the EARLIER
half of 795 races; nothing below was used to choose them.

## Evidence before this arm (all out of sample for the model)
- **Forecast, 398 unseen races:** photo finishes (top two within 2bp) at tau <= 30,
  log loss 0.063 vs the gap table's 0.164, Brier 0.019 vs 0.052. Clear leads:
  both near-perfect, no difference.
- **Trade tape, same unseen races, tau 2-30, price >= 90c, fair edge >= 2c:**
  37 bets / 33 races, **0 lost**, +5.25c a contract. With the forecast 1 s stale:
  34 bets, 0 lost, +4.89c; 2 s stale: 31 bets, 0 lost, +5.03c. TAPE -- what the
  market did, not our loss rate. 0 of 37 bounds the loss rate at ~8% (rule of
  three), and break-even at ~94c is ~6%, so this is NOT yet proof.
- **Forward, today's arm2 paper bets (after the truth file):** fair value would
  have taken none of the 66 it could price; those lost $1,682 on paper.
- Below 90c the model alone still loses often on the tape (34 of 70), so the
  price floor is part of the rule, not an afterthought.

## The rule, fixed now
`research/pinracearm.py --model fair --tau-max 30 --min-price 0.90 --min-edge 0.02`
(one bet per leg, side and time band; both sides of every leg considered)

## The bar -- decided before the data
Counted in BETS, reported with RACES.
- **KILL** if 3 bets lose before 40 bets.
- **KILL** at 40 bets if paper P&L is zero or negative.
- **PASS** at 40 bets with positive paper P&L and at most 2 losses -> propose a live
  penny test (1 contract a bet, operator sign-off per the standing rule).
- **KILL** if 21 days pass without reaching a pass.

## What a pass is worth
Tape frequency ~6-7 qualifying bets a day. At +5c a contract and the live bot's
77 contracts that is roughly **$20-25 a day IF the fills exist at that size** --
book depth at 90c+ on race legs is unmeasured and may be far thinner than 77.

## Not claimed
Paper fills are assumed. Adverse selection on the fills we would really get is
untested; on the up/down markets it was 26x.
