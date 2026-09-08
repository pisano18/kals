# AMENDMENT 2 — replace the edge floor with an EXPECTED VALUE test

**Written 2026-09-08 11:30 UTC, BEFORE the change goes live.** Dated and loud,
per the standing rule.

## The defect this fixes

The rule buys when `net_edge = fair − price − fee ≥ floor`. `fair` is the
**model's** probability, which at the prices we were paying implies an error
rate near **0.06%**. The **measured** error rate on trades we actually take is
**0.90%** (3 flips in 333 dear trades, out of sample) — fifteen times worse,
because of adverse selection: someone only sells a near-certainty cheaply when
they may know something.

At high prices that gap **flips the sign of the trade**.

```
EV per contract = (1−f)·(1−p) − f·p − fee
Setting EV = 0:   (1−f)(1−p) = f·p   →   p* = 1 − f = 0.991
```

**Any purchase above 99.1c loses money on average.** Five of the seven live
trades on 2026-09-08 were above it:

| market | paid | won | EV at f=0.90% |
|---|---|---|---|
| BTC | 99.2c | +0.74c | **−0.16c** |
| SOL | 97.9c | +1.95c | +1.05c |
| ZEC | 94.7c | +4.94c | +4.04c |
| BTC | 99.6c | +0.37c | **−0.53c** |
| NEAR | 99.1c | +0.83c | **−0.07c** |
| HYPE | 99.3c | +0.65c | **−0.25c** |
| BNB | 99.6c | +0.37c | **−0.53c** |

Realised +9.85c against an expected **+3.55c**. The run was **lucky, not
right** — seven wins at a 0.90% flip rate is a 93.9% likely outcome, and one
loss at 99.6c costs **10.1× the entire night's profit**.

Credit where due: the operator spotted this by asking "is it even worth doing
the trades above .99c".

## What changes

| | before | after |
|---|---|---|
| gate | `fair − price − fee ≥ 0.003` | `EV ≥ EV_FLOOR` where `EV = (1−f)(1−p) − f·p − fee` |
| f | implicit, from the model (~0.06%) | **measured, 0.90%**, a constant |
| effect | no price ceiling | implies a ceiling near **98.5c** |
| EV_FLOOR | — | **0.003** ($0.003 = 0.3c per contract) |

Everything else unchanged: tau [3,20], PIN gate 0.98/0.02, one fire per close,
size 1, resting level ≥ 1 contract, loss abort −$3.00, stake cap $5.00.

The model's `fair` is still required to clear 0.98 — that gate stays. The EV
test is an **additional** filter, and it is the binding one at high prices.

## Why f = 0.90% and not something else

- Point estimate from the corrected out-of-sample run: 3 flips in 333 dear
  trades = 0.90%.
- Its 95% upper bound is 1.80%, which would put the ceiling at 98.2c. Using
  the point estimate rather than the bound is the **less** conservative choice
  and is recorded as such.
- f is a **constant** here, not fitted per trade. Making it conditional on
  volatility, time and book state is the larger dynamic-floor project, still
  under walk-forward test. This amendment is the arithmetic correction only.

## What this costs

It would have **refused 5 of the 7 trades**, keeping 2. Expect the trade rate
to fall by roughly two thirds. That is the intended effect: those trades were
losing money in expectation, and a lower trade count at positive EV beats a
higher one at negative EV.

## What would make this wrong

1. **If f is materially lower at high prices** than the 0.90% average — i.e.
   the flip rate varies with price — then the ceiling is too strict and we are
   discarding good trades. This is measurable and is the first thing to check
   when usage allows. **This is the weakest point of the amendment.**
2. If f is materially *higher* than 0.90%, the ceiling is too loose and even
   98.5c is negative. The 95% bound of 1.80% would imply 98.2c.
3. n=3 flips is a very small sample for f. Both directions above are live
   possibilities.

## Revert / escalate condition

- If the live flip rate over the next 100 fired closes exceeds **1.8%**, drop
  f to the observed rate and re-derive the ceiling.
- If fewer than **5 trades fire in 24 hours**, the ceiling is too strict to be
  useful at this size and the opportunity set must be widened another way
  (earlier entry, more families) rather than by loosening the EV test.
