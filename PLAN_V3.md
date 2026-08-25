# Kalshi 15-Minute Crypto — Plan v3

`VERSION: 2026-08-25-v3` · supersedes `PLAN.md` (v2.1)

v2 was a **pattern-mining** project: eight hypotheses swept across dozens of
buckets, looking for anything that predicted. v3 is a **model-vs-market**
project. That change is the whole document; everything else follows from it.

---

## 1. Why the reframe

Settlement is a deterministic function of a public, once-per-second index.
Fair value is therefore *computed*, not forecast:

```
E[settle | now]  = (sum of settle ticks already printed + r · spot) / 60
Var[settle | now] = (1/3600) · Σⱼ Σₖ wⱼ wₖ γ(|j−k|)
fair              = Φ( (E[settle] − strike) / sd )
```

Everything on the right is public. There is exactly **one free parameter: the
index's own variance.** So the hypothesis space is not "anything in the tape" —
it is the short list of places the market's version of that arithmetic can
differ from ours. Few sharp tests instead of many vague ones, which is also the
only durable answer to this project's history of manufactured edges.

---

## 2. Corrections to v2 — all verified, all consequential

| v2 claim | status |
|---|---|
| `Var(settle − strike) = 880σ²` | ✅ correct (exact discrete value 880.0056) |
| `Var = σ²(τ+20)` before the window | ❌ should be **`σ²(τ−39.50)`**, τ = seconds to close. Overstates vol 32% at 120s, 48% at 90s |
| `σ²r³/10800` inside the window | ❌ continuous approximation. Exact is **`σ²·r(r+1)(2r+1)/21600`**. Understates vol 7.5% at r=10, 73% at r=1 |
| "every window opens at exactly 50¢ by construction" | ❌ that is the *unconditional* mean |
| tail crossover at 96.7¢ is a real replicated finding | ❌ artefact of the statistic |

**The opening-value error matters most.** Strike is the *trailing* 60-second
average; spot at open is not that average. Their difference has sd √20·σ ≈ $26
against a settlement sd of ~$176, so the conditional fair value at open averages
**4.75¢ away from 50**, with 40% of windows opening outside 45–55¢. There *is* a
directional view at open, it needs no forecasting, and no prior test could have
detected whether the book captures it — H5 compares the *mean* opening price to
50¢, which averages the effect to zero by construction.

**The 96.7¢ crossover is not a finding.** Fourteen unrelated fat-tailed
processes (Student-t ν=3–20, GARCH across a range of persistence, normal
mixtures) all cross at 96.3–99.3¢ regardless of kurtosis (1.0 to 168). It is
close to a fixed point of standardizing *any* fat-tailed distribution.
"Replicated at 96.6¢ and 96.7¢" establishes only that returns have excess
kurtosis. Do not build a threshold strategy on it.

**Settlement is 60 discrete prices, not an integral** — confirmed from the app's
own rules text. Every continuous-time formula is an approximation, worst exactly
where v2 said to trade.

---

## 3. Where an edge can live, ranked — and why the ranking changed

Split the candidates by *which parameter they live in*. This is the single most
useful idea in v3.

**μ-based edges — robust.** Disagreements about the *mean* of the settlement
distribution. Our σ and the market's appear on both sides and largely cancel, so
an error in σ neither creates nor destroys the edge.

1. **Stale quotes / lead-lag.** Does the book follow the index? A plumbing
   artefact, not a pricing opinion. Replay: **+7.85¢/contract** against a maker
   lagging spot by 20s. Because settlement is a 60-second *average*, this needs
   no colocation — only a better read on a slow-moving mean. This is
   `crypto_feeds.py`'s original thesis and it is the best idea in the v2 work.
2. **The locked-in partial average.** Inside the last minute part of settlement
   is already determined and Kalshi publishes the running average itself
   (`avg_60s_data`). Pure arithmetic. Replay: **+4.83¢** against a maker that
   ignores the averaging.
3. **Delta damping.** `d(fair)/d(spot) = φ(z)/sd · (r_live/60)`. A $50 spot move
   with 10s left moves fair settlement by $8.33, not $50 — anything reacting 1:1
   overreacts 6×. Testable as a regression with a *known correct coefficient*,
   far sharper than H6, which looks at contract jumps with no index reference
   and cannot separate overreaction from a real move.

**σ-based edges — self-limiting.** To profit from the book's σ being wrong you
must know σ better than the book does, and our own σ̂ carries 2–4% error at best.

4. **Vol timing.** Real, but bounded by our own estimation error. v2's successor
   analysis ranked this first; §4 explains why that was wrong.
5. **Tail shape.** Only after the conditional/unconditional question is settled.

---

## 4. The constraint that sets the floor

`d(fair)/d(log σ) = −z·φ(z)`, maximised at **0.242** where z=1. So a relative
error ε in σ moves fair value by up to `0.242·ε`. For an EWMA of squared
increments, the relative standard error is `1/√(2·n_eff)`.

| σ window | rel. SE | phantom edge |
|---|---|---|
| 33 s | 12.3% | **2.98¢** |
| 333 s | 3.9% | 0.94¢ |
| 1,250 s | 2.0% | 0.48¢ |
| 5,000 s | 1.0% | 0.24¢ |

Measured, not hypothesised: a 33-second σ̂ made the engine trade 18–28% of
windows against a *provably fair* book and lose 3.7¢/contract. **It traded
exactly when its own noise favoured it.**

Two consequences. A short σ window is noisy and a long one is stale (σ genuinely
moves), so σ̂ error is irreducible — that is the floor under any σ-based edge.
And every candidate trade must survive a σ stress test, which is now built into
the engine at `max(25%, 3× the estimator's own SE)`.

---

## 5. Measurement discipline — the actual lesson

Five bugs of one family in two days, each producing a fake edge, none catchable
by inspection:

1. chain-gate verdict keyed on a median that corruption could not move
2. tail test inventing a crossover from clean Gaussian noise
3. a model "beating" a fair book purely from tick quantization (t = 10.6)
4. occupation-time bias in the calibration estimator (mean t = −1.03 on a fair book)
5. cents-vs-dollars inferred per observation — a 0.5¢ quote read as 50¢, worth
   75¢/contract against a fair maker

**Every one was caught by asking a statistic what it returns when the answer is
already known.** That check now precedes every number, and every tool refuses to
touch real data until its self-test passes.

Two specifics worth carrying forward:

- **Clustering fixes standard errors, not point estimates.** RUNBOOK hard-rule 3
  treats clustering as *the* fix for the earlier fake-edge episode. It is
  necessary and not sufficient — the occupation-time bias survives it.
- **Sample on an exogenous schedule.** Evaluating at fixed times-to-close
  removes the selection that pooling every print introduces.

---

## 6. Route to money

1. **`python research/go.py`** — self-tests, then chain gate, vol
   discriminator, null calibrator, replay. One report. *(No collector needed
   for the first two stages.)*
2. **Resolve the null for the existing 450-market result** (`placebo`). Until
   then "the market is efficient" is not established; −0.008 was compared to
   zero, and the estimator's null is not zero.
3. **Measure the μ-based edges** on collector data (`edge`, `replay`). Lead-lag
   first.
4. **If an edge survives its own null:** run the engine live in log-only mode
   for a week. It already produces decisions; nothing wires them to an exchange.
5. **Only then** connect execution, at minimum size, with the risk layer active.

**Kill it if:** no μ-based edge clears its outcome-redraw null on ≥1,000
close-time clusters; or the edge exists only inside 15s to close (latency race,
unwinnable from home); or it survives only at one σ.

---

## 7. Sizing, when it comes to that

Kelly stake fraction for a binary bought at q with true probability p is
`(p−q)/(1−q)`. Full Kelly at 95¢ on a 1¢ edge stakes **20% of bankroll** — that
is PLAN v2 §6's steamroller, stated exactly.

Defaults in `engine.py`: quarter-Kelly, on an edge **halved** relative to the
entry threshold (a modelled edge is not a measured one), capped at 2% per market
and 6% total. The total cap matters more than it looks: the 12 series close
simultaneously and are ~0.8 correlated → **1.22 effective independent units**
(v2 §5). Sizing each independently and summing understates risk roughly 10×.

Plus: no trading inside 15s to close, book-staleness guard, and a drawdown kill
switch.

---

## 8. Open

- Is `cfbenchmarks_value` actually flowing? A `{"type":"subscribed"}` reply is
  not success — only a data frame is. Everything in §3 depends on it.
- Maker fee: secondary sources say 25% of taker (0.0175 vs 0.07). Unconfirmed
  from primary source. Does not revive the maker path — v2 §4's objection was
  queue depth (~3,767 at the touch), not fee.
- Is BRTI a random walk at one-second scale? If increments are autocorrelated, a
  plain σ²·k model is wrong by a fixed factor. `edge.py` estimates γ and
  propagates it rather than assuming.
- Cross-sectional design: 12 correlated series are weak for time-series tests
  (1.22 effective units) but *strong* as mutual controls — "is NEAR mispriced
  relative to BTC?" differences out the common move. Not yet built.
- Are the thin series (ZEC, HYPE, NEAR, TON) more loosely quoted than BTC?
