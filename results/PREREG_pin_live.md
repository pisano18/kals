# PRE-REGISTRATION -- pin, first live run (size 1)

Written 2026-09-07 ~20:45 ET, BEFORE any live pin order exists. The point of
this file is that the bar is set before the number is seen. If anything below
is changed after a result, the change is dated and explained here, loudly.

## The rule, frozen

Exactly the out-of-sample cell that produced +2.54c/contract, t=+5.0:

| parameter | value | source |
|---|---|---|
| universe | the 12 crypto 15-minute series in `SERIES_TO_INDEX` | pin.py |
| window | last **20 s** before close (tau <= 20) | RESULTS_pin.md, OOS cell |
| decided | model fair >= **0.98** (buy YES) or <= **0.02** (buy NO) | PIN in pin.py |
| edge floor | quote at least **0.5c** on the wrong side of fair | edge floor 0.5c, OOS cell |
| one per close per market | fire at most ONCE per market; hold to settlement | one-per-close rule |
| order type | LIMIT at the seen price, immediate-or-cancel, post_only FALSE | pintake.py rails |
| size | **1 contract** per fire | this document |
| fee model | taker 0.07 * p * (1-p) per contract (fractional cent; to be confirmed from fills) | engine.fee_per_contract |

Fair value is computed live exactly as the backtest computes it:
`mu = (locked_sum + remaining * spot) / 60`, `sd = sigma * sqrt(var_factor(tau))`,
`fair = Phi((mu - K) / sd)` (pinlive.py `fair()`, self-tested against four
hand-computed cases).

The detector may LOG wider (tau <= 60) for information. Only tau <= 20 fires.

## What a size-1 run CAN prove

1. **The taker order path works end to end** -- accepted, filled-or-cancelled
   within the second, fee charged as modelled. Binary; one fill proves it.
2. **The race is winnable in practice.** Of N signals fired, how many filled at
   the price we saw? `racecheck.py` measured from tape that 55.6% of
   mispriced quotes survive a 500 ms round trip. Prediction: fill rate
   **40-60%**. Below 20% means we are structurally too slow and pin is not
   executable from this box.
3. **The side is right.** Every fill's side should match settlement. The
   model says the flip rate is ~0.4% (1 in 262). One flip in the first 20
   fills is a 7.7% event under the model -- a flag, not a refutation. Two
   flips in the first 40 is a 1.1% event -- that is the loss abort, and it is
   evidence the model is wrong, not bad luck.
4. **The fee at size 1** is fractional (0.07 * 0.98 * 0.02 = 0.14c) and does
   not round up to a whole cent. If it rounds up, a 1-2c win becomes ~0, and
   pin only works at size >= 5.

## What a size-1 run CANNOT prove

**Profitability.** Per trade: win +~2c with p=0.996, lose ~97c with p=0.004.
Mean +1.6c, sd ~6.2c. Detecting +1.6c at t=2 needs ~60 fills -- but the mean
is entirely hostage to the flip rate, and the breakeven flip rate is
2/(97+2) = **2.0%**. To show the flip rate is below 2% at 95% confidence with
zero observed flips needs ~150 fills (rule of three). At ~37 signals/day and
~50% fills, that is **7-8 days at size 1**. Tonight cannot say pin makes
money. Tonight can only say whether it executes, fills, and settles on the
right side.

## Rails, all in code, all checked by self-tests before start

- loss abort: realised P&L this run <= **-$2.00** -> no further takes. Runs at
  the TOP of the loop, before any branch (last night's abort sat after a
  `continue` and never ran; a structural self-test now fails if that pattern
  reappears).
- per-order: count 1 (HARD_MAX 5 in a second constant nothing may exceed),
  price in (0,1), IOC/FOK only, post_only False, market close within 90 s.
- stake ledger: total dollars sent this run capped (pintake.py MAX_RUN_STAKE).
- one position per market; never re-buy a market already held.
- suppress a fire if the index feed is > 2 s stale or the book is > 2 s stale.
- capital: size 1 needs at most ~$12 concurrent (12 coins x ~$0.99) against
  a $41.04 balance. No new money is needed for size 1. Scaling to the
  backtested one-per-close cap of 50 contracts needs ~$50-100 peak
  concurrent; that is a later decision, made on tonight's numbers.

## Success / stop conditions for tonight

- SUCCESS: >= 5 signals fired at tau <= 20; fill rate reported; 100% of fills
  on the settled side; fees fractional. -> Next: run size 1 for a week to
  bound the flip rate, then scale on evidence.
- STOP AND INVESTIGATE: any fill whose side loses; fill rate < 20%; a fee that
  rounds up to a whole cent; the detector firing on a market the book shows
  was correctly priced (a detector bug).
- The loss abort is a HARD stop for the run, not a suggestion.

## Measured so far (for the record)

- 45-min paper run 22:42-23:27Z: **0 signals**, but the REST book feed was
  blind most seconds (rate-limited) -- not evidence about pin.
- 2-min diagnostic 23:29Z: every market seen was correctly priced
  (yes 0.001/0.002 on decided-NO markets) -- no stale quote in that one close.
- Two bugs found before money: a self-test that placed ticks in the wrong
  half of the window, and `close_s` off by 3600 s (time.timezone ignores DST).

## Measured AFTER this file was written (dated additions, not bar changes)

- 2026-09-07 ~20:50 ET: authenticated REST round trip from this box to
  `GET /markets/{t}/orderbook`, n=15: **min 81 ms, median 90 ms, p90 156 ms,
  max 1,091 ms**. The 40-60% fill prediction above assumed 200-500 ms; the
  measured clock is faster, so the prediction is conservative. It stands as
  written.
- Account at the time of writing: $41.04 cash, 0 positions, 0 resting orders.
