# RESULTS R4 — the calibration estimator has a bias that clustering does not fix

`2026-08-25` · sandbox, no market data. Simulation only. **This is the most
consequential thing found so far, and it is about measurement, not markets.**

## The claim under test

RUNBOOK's headline:

> Full-tape calibration on 2.1M trades across 450 markets, clustered by market:
> the market is **efficient**. Mean t across 71 cells −0.008 … Cells at
> abs(t) ≥ 2: 3 (efficient market predicts 3.2)

That reads as a clean null. It rests on an unstated assumption: that the
estimator returns **zero** when the market is efficient.

## What was measured

A synthetic market where the book quotes **exactly** the true model — efficient
by construction, no edge to find — then run through
`kalshi_fulltape.py`'s `calibration()` scheme verbatim: time bucket × 0.05
price bucket, group by market, average prices within (market, cell), one
observation per market, cluster SE on markets.

| | ground truth | measured |
|---|---|---|
| mean t across cells | 0 | **−1.031** |
| sd of t | 1 | 0.852 |
| cells with \|t\| ≥ 2 | ~4 of 84 | **12 of 84** |

Pooling raw observations instead (no per-market averaging) gives mean t = −1.60,
with **every one of ten price buckets biased in the same direction**
(errors −0.004 to −0.025, χ²-ish 506 on 10 df). Taking exactly **one**
observation per market at a fixed time-to-close removes it entirely
(χ²-ish 11 on 10 df — pure noise).

## Why

**Occupation-time selection.** Each market contributes ~128 observations, and
how long a price path lingers near a level is correlated with where that path
ends up. A path that reaches 0.85 and goes on to win passes through quickly; one
that reaches 0.85 and then fails tends to oscillate there first, contributing
more observations. So the losers are over-weighted at every level.

**Clustering does not fix this.** Clustering corrects the *standard error*. This
is a bias in the *point estimate*. RUNBOOK hard-rule 3 treats clustering as the
fix for the earlier fake-edge episode; it is necessary and not sufficient.

## What this does and does not say about the headline result

It does **not** show the market is inefficient. My synthetic trades arrive on a
fixed 7-second cadence; real trades arrive endogenously, which changes the
occupation weighting by an unknown amount and possibly its sign.

It does show that **−0.008 was compared against the wrong null.** Under one
plausible sampling model the estimator reads −1.03 on a market that is
efficient by construction. Until the null is calibrated on the *actual* trade
arrival process, "mean t ≈ 0" cannot be read as "efficient" — and, read against
a −1.03 null, it would mean prices sit systematically *below* outcomes.

**The fix is cheap:** take the real trade timestamps, simulate fair prices along
random paths at exactly those times, and see what the estimator reports. That is
the null. It requires no new data — `fulltape/tapes.json` already has the
timestamps.

## The bias is big enough to hide a real defect

While debugging, the harness failed to detect a book whose σ was **40% too
low** — a 6¢ average mispricing. Reason: the occupation bias runs 1.5–4¢ in the
opposite direction and cancels it. A genuinely broken book measured as
efficient.

## Design consequences

1. **Sample on an exogenous schedule.** `edge.py` now evaluates each market at
   fixed times-to-close (600, 480, …, 10s), taking the last print at or before
   each. Sample times are chosen by us, not by where the price went.
2. **Prefer head-to-head over absolute calibration.** Comparing model and market
   on the *same* observations makes the occupation bias affect both forecasts
   identically, so it largely cancels in the difference. Measured: absolute
   calibration biased −1.03; head-to-head on the same data reads t = −1.3/+1.5
   on two independent nulls.
3. **Never trade at the print.** Allowing entry at the observed price harvested
   the market's own tick rounding: **+4.47¢ at t=3.1 against a fair book.**
   Entry now pays a tick.

## The harness, calibrated

`python research/edge.py --selftest` — 1,500 synthetic markets per case:

| simulated book | ΔlogLoss t | ΔBrier t | net P&L | verdict |
|---|---|---|---|---|
| fair (null) | −1.3 | −1.3 | — | tie |
| fair, 2nd null | +1.9 | +1.5 | — | tie |
| σ 40% too low | 6.1 | 4.9 | +2.66¢ | detected |
| quote 20s stale | 11.1 | 13.0 | +7.55¢ | detected |
| ignores averaging | 7.7 | 7.5 | +24.43¢ | detected |

Two independent nulls read tie; three planted defects detected with sensible
relative magnitudes. Index autocorrelation is recovered to ±0.005 at ρ₁ = 0,
±0.3.

**Power:** a pure σ-scale error needs ~1,200 markets (at 300 it reads t=0.8 —
underpowered, not undetected). Stale quotes and averaging errors are detectable
at 300. Log-loss has the right sign but poor power against overconfidence,
because the failure arrives as rare huge losses; Brier is the statistical test,
net P&L the decision metric.

## Method note

Four bugs of the same family in two days, each found by asking a statistic what
it returns when the answer is already known:

1. chain-gate verdict keyed on a median that corruption could not move
2. tail test inventing a crossover from clean Gaussian noise
3. model "beating" a fair book on log-loss purely from tick quantization
4. this one — occupation-time bias in the calibration estimator

None would have been caught by inspection. All were caught by calibration
against ground truth. That check should precede every number this project
reports.
