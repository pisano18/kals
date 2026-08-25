# RESULTS R2 — the chain, a calibrated harness, and two corrections

`2026-08-25` · sandbox, **no market data access** (org egress policy blocks all
exchange/Kalshi hosts; GitHub + web *search* only). Everything below is either
analytic, simulated, or sourced from public documentation. **Nothing here is a
measurement on real market data.**

## The observation

Window N+1 opens exactly when window N closes. So `strike(N+1)` and `settle(N)`
are averages over **the identical 60 seconds** and must be equal to the cent.

Two consequences:

1. **A settlement gate that needs no index feed.** Stronger than
   `kalshi_gate1.py`, which can only test markets that closed inside the
   recording window. This one runs on all settled history, today, from public
   records.
2. **A free dataset.** The chain `settle(1), settle(2), …` *is* a 60-second-TWAP
   time series at 15-minute spacing, per asset, as far back as Kalshi serves
   settled markets. Each window's return is exactly `settle − strike` — the
   quantity the contract pays on. We never needed to record it.

That dataset answers, with no BRTI and no collector: σ per series, vol
clustering, window-level return autocorrelation, time-of-day vol seasonality,
and per-series tails.

## How to run it

```
python research/chain.py --selftest                      # must pass first
python research/chain.py --power                         # what it can detect
python research/chain.py --series KXBTC15M --markets 5000
```

`main()` refuses to touch real data unless the self-test passes.

---

## 1. The harness is calibrated, not merely careful

Every statistic is run against synthetic data with a known answer *before* it is
allowed near real data. It must recover an injected effect **and** stay silent
on clean noise. This project's history is of measurement bugs producing fake
edges; the fix for that is calibration, not care.

Writing the self-test immediately found three bugs **in my own code**:

- The chain gate keyed its verdict on the median. Corrupting every 7th pair
  leaves the median at exactly 0, so it printed `PASS` on data it had already
  measured as only 85.7% exact. Now keyed on p90 and the exact-match fraction.
- The tail test reported a confident crossover at ~99.4¢ from ratios of
  1.00/1.02/1.03 — **pure noise**. Now requires both bracketing ratios to differ
  from 1 by >2 binomial SE. Clean Gaussian input now correctly reports `none`.
- Two "clean noise" control runs shared a seed, so the second was a copy of the
  first rather than an independent check.

The second bug matters beyond my code: **that is exactly the failure mode that
would manufacture a tail-crossover finding out of nothing.**

## 2. GARCH alone reproduces the 96.7¢ crossover

Self-test case 5, with **no fat tails injected** — only vol clustering:

| case | n | excess kurt | 80% | 90% | 96% | 98% | 99% | crossover |
|---|---|---|---|---|---|---|---|---|
| gaussian | 5,988 | −0.1 | 1.00 | 1.02 | 1.03 | 1.03 | 0.99 | none |
| garch(fat) | 5,988 | 3.4 | 0.75 | 0.86 | 1.18 | 1.67 | 2.32 | **96.7¢** |

RUNBOOK reports a real-data crossover replicated at 96.6¢ and 96.7¢ and treats
it as a fixed distributional property. Plain vol clustering produces the same
number from a process with **no unconditional fat tails at all** — the kurtosis
is entirely an artefact of mixing high- and low-vol periods.

This changes the trading implication completely:

- *Static fat tails* → a constant threshold; "don't buy favourites above 96.7¢".
- *Vol clustering* → the correct threshold **moves with recent realized vol**,
  and is forecastable.

If the book quotes a slow σ and the true σ is conditional, that is a durable
edge requiring no directional view. This is now the single most promising
hypothesis in the project. `chain.py` tests it directly.

**Caveat:** this shows GARCH is *sufficient* to produce the observed crossover,
not that it is the cause. Distinguishing them requires conditioning the tail
test on trailing realized vol — if the crossover is static it stays put, if it
is GARCH it moves. That test is the obvious next build.

## 3. The maker fee is probably already public

PLAN.md §9 / Next-action 1 says the maker fee is unanswerable without resting a
live order. Multiple secondary sources give **maker = 25% of taker**, i.e. a
`0.0175` multiplier against the taker's `0.07`:

| | multiplier | at 50¢, per contract |
|---|---|---|
| taker | 0.07 | 1.75¢ |
| maker | 0.0175 | 0.44¢ |

**Not confirmed from primary source.** Kalshi's own schedule is at
`kalshi.com/docs/kalshi-fee-schedule.pdf`, which this environment cannot fetch.
Sources also say maker pricing applies only to *some* markets, and none of them
state whether the 15-minute crypto series is among them. So the live-order test
is still worth doing — but it is confirming a number, not discovering one.

This does **not** revive the maker path. PLAN §4's objection was queue depth
(~3,767 resting at the touch, spread already at minimum tick), and a 4× cheaper
fee does not fix a ~4% fill rate on adversely-selected fills.

---

## What this does not do

`chain.py` cannot see anything that requires the index path: the opening-value
edge from R1, delta damping, lead-lag, or model-vs-market scoring. Those need
BRTI, which means either the collector's `cfbenchmarks_value` stream or a
working historical endpoint. The chain is what is available *now*, at full
sample size, while the collector accumulates.
