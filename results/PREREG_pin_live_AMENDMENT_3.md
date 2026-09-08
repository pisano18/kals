# AMENDMENT 3 — scale in as the price improves, instead of one shot

**Written 2026-09-08 ~15:00 UTC, BEFORE the change goes live.**

## What changes

| | before | after |
|---|---|---|
| buys per close | **1**, at the first qualifying second | up to **2**, adding only when the price **improves** |
| everything else | unchanged | unchanged |

tau 3–20, model ≥98%, EV ≥0.3¢ at the measured 0.90% flip rate, size 1 per
buy, loss abort −$3.00, stake cap $5.00: **all unchanged**.

## The evidence

70 closes, 593 qualifying seconds (8.5 per close), walk-forward on the
available-trade dataset (order book replayed, so the population is trades that
genuinely existed — not every moment the model felt confident).

| strategy | closes | buys | avg price | total | ¢/contract | ¢/close |
|---|---|---|---|---|---|---|
| FIRST (live) | 70 | 70 | 95.53¢ | 292.5¢ | 4.18¢ | 4.18¢ |
| **SCALE_IMPROVE cap3** | 70 | 116 | **94.28¢** | 621.2¢ | 5.36¢ | **8.87¢** |
| BUDGET step1¢ cap3 | 70 | 101 | 93.79¢ | 587.4¢ | 5.82¢ | 8.39¢ |
| SCALE_ALL cap3 | 70 | 189 | 95.58¢ | 780.2¢ | 4.13¢ | 11.15¢ |
| PATIENT skip1 | **63** | 63 | 95.65¢ | 256.5¢ | 4.07¢ | 4.07¢ |
| BEST (needs the future) | 70 | 70 | 92.95¢ | 463.0¢ | 6.61¢ | 6.61¢ |

**Three findings:**

1. **Waiting is strictly worse.** `PATIENT skip1` missed **7 of 70 closes
   entirely** and earned less per contract. There is no case for holding out
   for a better price.
2. **Adding on improvement lowers the average price** — 95.53¢ → 94.28¢ — so
   the extra contracts are *better* than the first, not worse.
3. **It is better risk-adjusted, not merely bigger.** 1.66× the contracts for
   2.12× the profit. The mechanism: in this bet a lower price **wins more AND
   loses less**, so averaging down improves both sides. That is unusual and it
   is why this works here.

Scored on expected value rather than the (zero-loss) realised outcomes, using
the measured 0.90% flip rate: **+3.25¢/close for FIRST vs +7.37¢/close for
SCALE_IMPROVE.** The advantage does not depend on the lucky sample.

## Why cap 2 and not 3

Cap 3 earns more but takes maximum exposure per close to ~$2.83, which would
nearly trip the −$3.00 loss abort **in a single bad close**. Cap 2 caps it at
about **$1.90**. The abort must be able to fire on the second bad event, not
the first.

`SCALE_ALL` earns the most in total but has the **worst** price per contract
(4.13¢, below the current rule) because it buys indiscriminately. Rejected:
more size at worse prices is not an improvement.

## What would make this wrong

1. **There are zero losses in the sample.** Scaling multiplies losses as well
   as wins, and this data cannot show that half. The expected-value
   calculation above is what carries the case, not the realised outcomes.
   **This is the weakest link.**
2. Only 70 closes. The per-close figures are noisy.
3. If the extra fills in practice come at *worse* prices than the first (e.g.
   the book thins as we buy), the averaging-down mechanism reverses. At size 1
   against a median 200-contract book we consume 0.5%, so impact should be
   negligible — but it is assumed, not measured.

## Revert condition

- If average fill price across a close comes out **higher** than the first
  fill's price over 50+ closes, the improvement rule is not working and this
  reverts to one shot.
- If the loss abort fires on a single close, reduce cap to 1 immediately.
