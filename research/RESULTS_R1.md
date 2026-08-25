# RESULTS R1 — settlement math, re-derived and verified

`2026-08-25` · run in a sandbox with **no market data access** (org egress policy
blocks every exchange/Kalshi host; GitHub and web *search* only). Everything
below is analytic or Monte Carlo. **No claim here is a measurement on real
market data.** Each needs confirming against the tape on `C:\kals`.

## Commands

```
python3 research/settlement_math.py
python3 research/opening_value.py
```

## What was verified, not assumed

Settlement is the mean of **60 discrete once-per-second RTI prices** — confirmed
from the Kalshi app rules text, not inferred:

> "At the last minute before expiration, 60 RTI prices are collected. The
> official and final value is the average of these prices."

Timeline, integer seconds: strike = mean(S₁…S₆₀), open at k=60, settle =
mean(S₉₀₁…S₉₆₀), close at k=960.

Every closed form below was checked three ways: exact covariance-matrix
computation, an independent closed form, and 200k-path Monte Carlo. Worst MC
disagreement 0.41%.

---

## 1. CONFIRMED — Var(settle − strike) = 880σ²

Exact discrete value **880.0056σ²**. PLAN.md and RUNBOOK.md are right. The
earlier 900σ² and 820σ² were indeed errors.

## 2. ERROR — `Var = σ²(τ + 20)` before the averaging window

RUNBOOK.md T5. Correct form is **`σ²(τ − 39.50)`** for τ = seconds to close.
Off by a constant ≈59.5σ² — derived for "time until the averaging window
starts", written as "time to close".

| τ (s to close) | exact/σ² | RUNBOOK | vol overstated |
|---|---|---|---|
| 900 | 860.50 | 920.00 | 3.4% |
| 300 | 260.50 | 320.00 | 10.8% |
| 120 | 80.50 | 140.00 | **31.9%** |
| 90 | 50.50 | 110.00 | **47.6%** |
| 61 | 21.50 | 81.00 | **94.1%** |

## 3. ERROR — `σ²r³/10800` inside the window

That is the continuous integral. With 60 *discrete* prices the exact residual
variance with r ticks left is **`σ²·r(r+1)(2r+1)/21600`**.

| r | exact/σ² | continuous | vol understated |
|---|---|---|---|
| 30 | 2.62639 | 2.50000 | 2.5% |
| 10 | 0.10694 | 0.09259 | 7.5% |
| 5 | 0.01528 | 0.01157 | 14.9% |
| 3 | 0.00389 | 0.00250 | 24.7% |
| 1 | 0.00028 | 0.00009 | 73.2% |

Too little vol pushes probabilities toward 0/1, so the continuous form
**overprices favourites**. PLAN.md §2 targets 90–99¢ favourites in the last
30–120s — the exact cell where this is largest and in the losing direction.
§10.3's fat-tail effect pushes the same way. Two independent reasons the v2
target cell is overvalued by the v2 model.

---

## 4. PREMISE ERROR — "every window opens at exactly 50¢ by construction"

PLAN.md §2. This is the claim the whole v2 pivot rests on, and it is false.

50¢ is the **unconditional** mean. The **conditional** fair value at open is

```
P(Yes) = Φ( (spot_at_open − strike) / (σ·√860) )
```

The strike is the *trailing* 60-second average; spot at open is not that
average. Their difference has mean 0 but **sd √20·σ ≈ $26** at BTC ~$78.8k,
against a settlement sd of ~$176.

Simulated distribution of true fair value at open (400k windows):

| p1 | p5 | p10 | p25 | p50 | p75 | p90 | p95 | p99 |
|---|---|---|---|---|---|---|---|---|
| 36.3¢ | 40.2¢ | 42.3¢ | 46.0¢ | 50.0¢ | 54.0¢ | 57.7¢ | 59.8¢ | 63.7¢ |

- mean |fair − 50¢| = **4.75¢**
- 40.5% of windows open outside 45–55¢
- 9.3% open outside 40–60¢

Model self-calibration is diagonal (says 34% → settles 34.0%; says 58% →
settles 58.1%), so this is the model being right, not a coding artefact.

**Why no earlier test could have found this.** `kalshi_signals.py` H5 compares
*mean* opening price to 50¢ — that averages the effect to exactly zero and
reports "efficient". The full-tape calibration compared price to outcome, which
tests marginal calibration, not conditional efficiency against a model. And
neither ever saw BRTI, so `spot − strike` was not computable.

If the book opened flat at 50¢ this would be ~4.75¢ gross, ~3.0¢ net of the
1.75¢ fee (large-order limit). **I do not believe the book does that** — this
sets the scale of what must already be priced, and makes "how much does the
book capture?" the sharpest available experiment.

## 5. The delta-damping fade

`d(fair)/d(spot) = φ(z)/sd · (r_live/60)`, where `r_live` = settle ticks not yet
locked in.

| s to close | ticks live | spot sensitivity |
|---|---|---|
| ≥60 | 60 | 1.000× |
| 30 | 30 | 0.500× |
| 10 | 10 | 0.167× |
| 5 | 5 | 0.083× |
| 2 | 2 | 0.033× |

A $50 spot move with 10s left moves fair settlement by $8.33, not $50. Anything
reacting to spot 1:1 inside the last minute overreacts by 6×. Testable as a
regression of contract-price change on index change bucketed by time-to-close,
with a **known correct coefficient** — far sharper than H6, which looks at
contract jumps with no index reference and cannot separate overreaction from a
real move.

---

## Caveat that could shrink all of this

Every number assumes BRTI increments are iid. BRTI is a martingale by CF's
construction, but it is built from *order-book mids*, which can be smoothed or
mean-reverting at 1-second scale. If so, the σ implied by `Var(settle−strike) =
880σ²` over 900s is **not** the σ that governs `spot − trailing-average` over
60s. The bot must estimate those two variances **separately and empirically**
rather than linking them through one σ. Flagged as the first thing to measure
once index data exists.
