# RESULTS R5 — σ uncertainty sets a floor on any detectable edge

`2026-08-25` · sandbox, no market data. Replay against synthetic books.

## What was built

`engine.py` — the decision logic for a live bot. Pure and deterministic: no
network, no files, no order code. It is fed index ticks and book updates and
returns `Decision` objects. The transport lives elsewhere, so every rule that
risks money can be replayed offline against a scenario with a known answer.

Its variance function was cross-checked against `settlement_math.py` for
τ=1..900 — zero mismatches. That is now three independent implementations of
the same quantity agreeing (`settlement_math`, `edge`, `engine`).

## The finding

The first self-test **failed**: against a maker quoting the *true* model, the
engine traded 18–28% of windows and **lost 3.7¢ per contract**. It was
selecting on its own volatility-estimation error — trading exactly when its
noisy σ̂ happened to favour it.

The size of that effect is the important part:

```
d(fair)/d(log σ) = −z·φ(z),  maximised at z=1 where it equals 0.242
```

So a relative error of `ε` in σ moves fair value by up to `0.242·ε`. And for an
EWMA of squared increments with decay λ, the relative standard error is
`1/√(2·n_eff)` with `n_eff = 1/(1−λ)`.

| EWMA window | rel. SE of σ̂ | phantom edge |
|---|---|---|
| 33 s (λ=0.97) | 12.3% | **2.98¢** |
| 100 s | 7.1% | 1.72¢ |
| 333 s | 3.9% | 0.94¢ |
| 1,250 s | 2.0% | 0.48¢ |
| 5,000 s | 1.0% | 0.24¢ |

**A σ̂ estimated over 33 seconds manufactures ~3¢ of apparent edge — larger than
most of the edges this project is hunting.** Measured, not hypothesised: it
produced 71 trades and a 3.7¢/contract loss against a provably fair book.

## The strategic consequence — this reorders the roadmap

There is an irreducible tension. A short σ window is noisy; a long one is stale,
and R2/R3 established that σ genuinely moves (vol clustering). Either way σ̂
carries error, and that error sets a floor under any edge that *depends on σ*.

So separate the candidate edges by which parameter they live in:

**μ-based edges — robust.** Stale quotes, the locked-in partial average,
delta damping. These are disagreements about the *mean* of the settlement
distribution. Our σ and the market's σ appear on both sides and largely cancel,
so a σ error does not create or destroy the edge.

**σ-based edges — self-limiting.** Vol timing, tail/threshold trades. To profit
from the book's σ being wrong you must know σ *better than the book does*. Our
own σ̂ error is ~2–4% at best, which caps how confidently that can ever be
asserted.

R2 ranked vol-timing as the most promising hypothesis because it is durable and
needs no directional view. **That ranking was wrong, and this reverses it.**
Priority order is now:

1. **Stale quotes / lead-lag** (μ) — largest and most robust. Replay: +7.85¢
   per contract against a maker lagging spot by 20s.
2. **Locked-in average / delta damping** (μ) — mechanical, deterministic.
   Replay: +4.83¢ against a maker that ignores the averaging.
3. **Vol timing** (σ) — real but bounded by our own estimation error.

This also matches `crypto_feeds.py`'s original thesis, which R1 flagged as the
best untested idea in the existing work.

## Defences now in the engine

- **Self-calibrating σ stress.** Every candidate must clear its threshold when
  σ is moved against it by `max(25%, 3 × the estimator's own relative SE)`. A
  trade that exists at only one σ is a model artefact, not a trade.
- **σ over ~30 minutes** (λ=0.9995, 1,800-tick warmup).
- **Correlation-aware exposure.** The 12 series are ~0.8 correlated → 1.22
  effective independent units (PLAN §5). Sizing each independently and summing
  would understate risk ~10×; total simultaneous stake is capped accordingly.
- **Quarter-Kelly off a haircut edge.** `f* = (p−q)/(1−q)`; full Kelly at 95¢ on
  a 1¢ edge stakes 20% of bankroll, which is PLAN §6's steamroller. The edge
  used for *sizing* is halved relative to the edge used for *entry*, because a
  modelled edge is not a measured one.
- **No trading inside 15s to close** (PLAN kill criterion 3 — latency race).
- **Drawdown kill switch**, book-staleness guard, per-market and total caps.

## Validation

`python research/engine.py --selftest` — 400 markets per row:

| simulated maker | trades | avg edge | P&L/contract |
|---|---|---|---|
| fair (null) | 1 / 400 | — | — |
| fair, 2nd seed | **0 / 400** | — | — |
| σ 40% too low | 396 | 7.03¢ | **+10.71¢** |
| σ 60% too high | 398 | 5.40¢ | +1.98¢ |
| quote 20s stale | 394 | 5.59¢ | **+7.85¢** |
| ignores averaging | 85 | 5.23¢ | +4.83¢ |

Risk controls: 0 violations of the time-to-close window; σ stress gate cuts a
marginal maker from 64 trades to 0 when tightened; drawdown kill fires at 25.9%
> 10%; Kelly fractions match `(p−q)/(1−q)·0.25` exactly at 50/90/95/98¢.

## Still true

No order-placement code exists in this repo, and no flag enables one. These are
decisions written to a log. Wiring them to an exchange is a separate, deliberate
act that should happen only after a measured edge on real data.
