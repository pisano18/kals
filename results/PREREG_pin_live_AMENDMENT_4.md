# AMENDMENT 4 — extend the trading window from 20 to 30 seconds

**Written 2026-09-08 ~15:20 UTC, BEFORE the change goes live.**

## What changes

| | before | after |
|---|---|---|
| `TAU_MAX` | **20** seconds | **30** seconds |
| everything else | unchanged | unchanged |

## The evidence — model calibration by time horizon

Measured on the order-book dataset (28,446 moments where a trade genuinely
existed), restricted to moments the model calls **under 2% risk** — the zone
the rule trades:

| tau | moments | closes | flips | realised | model claimed | ratio |
|---|---|---|---|---|---|---|
| 3–10 | 575 | 82 | **0** | 0.00% | 0.034% | clean |
| 11–20 | 1,772 | 106 | **0** | 0.00% | 0.078% | clean |
| **21–30** | **2,872** | **118** | **0** | **0.00%** | 0.086% | **clean** |
| 31–45 | 7,302 | 131 | 25 | 0.34% | 0.092% | **3.7×** |
| 46–60 | 10,047 | 132 | 126 | 1.25% | 0.115% | **10.9×** |

**The model's overconfidence is entirely a long-horizon phenomenon.** Below 30
seconds it has not been wrong once in 5,219 moments across 306 closes. From 31
seconds it degrades, and by 46 seconds it understates risk elevenfold.

This also *explains* a previously unexplained result: the `tau<=60` cell was
dead in the out-of-sample backtest (+0.17c, t=+0.5). Now we know why — beyond
30 seconds the probability model is not merely weaker, it is wrong.

## What it buys

Applying the same EV gate, qualifying moments roughly double:

| tau | moments passing the EV gate | closes |
|---|---|---|
| 3–20 (current) | 593 | ~70 |
| 21–30 (added) | 603 | 64 |

More opportunities at a horizon where the model is measurably honest, and
where the order book is deeper because fewer participants have yet done the
arithmetic.

## What would make this wrong

1. **Zero flips is not proof of zero risk.** 118 closes with no flip gives a
   95% upper bound of about **2.5% per close**, against a break-even near
   2.26% at typical prices. At the pessimistic end of that interval the zone
   is marginal. **This is the weakest link.** The mitigating fact is that the
   11–20 zone we already trade has the same statistical weakness (106 closes,
   0 flips, upper bound 2.8%) — this amendment does not accept a *new* kind of
   uncertainty, it extends an existing one.
2. The dataset covers 96 hours. A regime with larger moves could push the
   breakdown point below 30 seconds.
3. Longer tau means more prints unpublished (29 vs 19 at the extremes), so the
   arithmetic protection is weaker even where the empirical record is clean.
   The required-move multiplier falls from 3.2× at tau=20 to 2.1× at tau=30.

## Revert condition

- **Any flip on a trade taken at tau > 20** triggers an immediate review and,
  if a second occurs, reversion to `TAU_MAX = 20`.
- If the realised flip rate over the next 200 fired closes exceeds **1.0%**,
  revert.
- `TAU_MAX` is **not** to be extended beyond 30 on this evidence. The data says
  31–45 is 3.7× overconfident; that is a measured wall, not a soft edge.
