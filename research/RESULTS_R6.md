# RESULTS R6 — removing the guesswork, and two new tests

`2026-08-25` · sandbox, no market data. Everything below is simulation or
analysis of the collector log.

## The overnight log

Read from the hourly jumps in `run_all.ps1` output:

| | per hour | per day |
|---|---|---|
| `kalshi_data` | 57.6 MB | 1.38 GB |
| `feed_data` | 133 MB | 3.19 GB |
| **total** | **191 MB** | **4.57 GB** |

Two things follow.

**The staircase is not a stall.** `kalshi` reads 65.0 MB from 01:07 to 01:57
then jumps to 124.1 at 02:02. That is Windows not refreshing the directory-entry
size until the hourly `.gz` handle closes — Python's `flush()` pushes to the OS
but does not update the size metadata. Data was being written throughout.

**The growth estimate in `kalshi_collector.py` is 20× low.** Its docstring says
"40-80 MB/day gzipped, ~2 GB/month"; the measured figure is ~41 GB/month for
`kalshi_data` alone. At 49.4 GB free and a watchdog that halts below 5 GB, that
is **~9.7 days** of runway. Also: zero `RESTART` lines in 7 hours — both
processes stayed up.

---

## 1. The loaders no longer guess at field names

This was the largest practical risk to the whole pipeline. Every downstream
loader hard-coded field names I had guessed at — `yes_bid` or `bid` or
`best_bid`, cents or dollars, `ts` or `created_time`. A wrong guess does not
crash; it silently returns nothing, or something subtly wrong.

`doctor.py` reads the real collector output, walks every leaf path (descending
into nested JSON *strings*, which is how `cfbenchmarks` payloads arrive),
resolves concepts to the paths that actually exist, decides the price unit once
from the whole sample, and writes `schema.json`. `replay.py` reads that file, or
discovers the fields from the data itself when it is absent.

**Proven, not assumed:** the same synthetic data emitted under three different
naming conventions —

| naming | markets | quotes | trades | P&L/contract |
|---|---|---|---|---|
| `market_ticker`/`yes_bid`, cents | 120 | 101,411 | 118 | 10.98¢ |
| `ticker`/`bid`, dollars | 120 | 101,411 | 118 | 10.98¢ |
| `market`/`best_bid`, ISO timestamps | 120 | 101,411 | 118 | 10.98¢ |

Bit-identical.

`doctor` also answers the question everything depends on — is
`cfbenchmarks_value` delivering, per index, at what rate — plus sequence gaps,
the clock chain, and disk runway.

## 2. The real order book, and a number worth re-checking

`book.py` rebuilds the book from `orderbook_snapshot` + `orderbook_delta`. Two
things a ticker-only view gets wrong:

- **The yes-ask comes from the best NO bid.** A no-bid at *p* is a yes-offer at
  *1−p*. Reading only "yes" data sees half the market and does not error.
- **A sequence gap invalidates the book** until the next snapshot, rather than
  silently corrupting every level after it.

Self-test replays 400 deltas against a book built by hand: 0 mismatches, gap
detected, no states emitted after an unrepaired gap.

It also re-measures the queue depth PLAN §4 used to kill the maker strategy.
That "best bid 0.40 with **3,767 contracts** resting" came from a REST call that
RUNBOOK separately records as mis-parsed — levels ascending, truncated from the
bottom, top-of-book hidden. A number read off an endpoint that was
simultaneously misread should not be allowed to close off a strategy without
re-measurement from the websocket.

## 3. Cross-sectional: the correlation is an asset, not a liability

PLAN §5 is right that 12 series at ρ=0.8 give **1.22 effective independent
units** — for an *absolute* question. For a *relative* one it inverts, because
demeaning the close-time cluster deletes the common crypto move, which is
exactly the term that made the series redundant.

`cross.py`, measured on synthetic data with ρ=0.8:

- power gain from demeaning: **2.2× in t, 4.8× in variance**
- a 0.2¢ relative mispricing: found **74%** of the time, versus **10%** absolute
- a 0.5¢ relative mispricing: **100%** versus 94%

**A trap found while building it.** With a *mean* centre, one genuinely
mispriced series drags the reference for every other: a +1¢ bias in one of
twelve moves the mean by 0.083¢, so the eleven innocent series all read −0.08¢.
Measured: **four false MISPRICED flags from one real effect.** A median centre
cut it to two. Neither is enough — a relative test cannot on its own distinguish
"S07 is +1¢" from "the other eleven are −0.08¢". The fix is to identify outliers
and exclude them from the reference, then recompute. After that: S07 flagged at
t=26.8 recovering +1.04¢ against a planted +1.0¢, and **zero** innocent series
flagged.

This is the natural test for PLAN §9's open question — are ZEC/HYPE/NEAR/TON
more loosely quoted than BTC? A maker running twelve books with one model is
most likely wrong on the assets it cares least about.

## 4. The first sixty seconds — the test nothing could do

`strike(N+1) == settle(N)`, so a window's strike is fully determined the instant
the previous window closes, computable from our own index feed before Kalshi
stamps `floor_strike`. And R1 established fair value at open is not 50¢ but
`Φ((spot−strike)/σ√860)` — 4.75¢ away on average, 40% of windows outside 45–55¢.

So if the book opens near 50¢ and converges, the entire disagreement is
available at the most liquid moment of the window. **Nothing had looked at
second zero**: H5 measures the *mean* opening edge, `replay` starts 300s after
the open, and `leadlag` measures the response to index *changes*, not the level
the book starts from.

`openwindow.py` demonstrates the blindness. Against a simulated book that opens
at 50¢ and converges over 30 seconds:

| statistic | first 5 seconds |
|---|---|
| mean edge (what H5 measures) | −0.30¢, t = −1.1 → **"nothing"** |
| mean \|edge\| (what you would trade) | **4.23¢** |

Against a book that opens correct, both read 0.00¢. The effect is symmetric
about 50¢, so averaging deletes it exactly — which is why H5 would report
"efficient" against an arbitrarily large conditional mispricing.

It also gates our strike reconstruction against `floor_strike` to the cent,
using only our own index record.

---

## State

`python research/go.py` — **12 self-tests**, then 9 stages. Every tool refuses
real data until its self-test passes.

| | |
|---|---|
| `settlement_math` | the model, MC-verified, now stdlib-only |
| `doctor` | what is on disk; writes `schema.json` |
| `book` | order book from deltas; queue depth |
| `chain` | `strike(N+1)==settle(N)` gate; σ; vol clustering; tails |
| `volmodel` | fat tails vs vol clustering |
| `placebo` | the calibration estimator's null |
| `engine` | decisions, Kelly, σ stress, risk limits |
| `replay` | engine over recorded data, with a P&L null |
| `leadlag` | does the book follow the index |
| `cross` | relative mispricing across the 12 series |
| `openwindow` | the first 60 seconds |

Still no order-placement code anywhere, and no flag that enables one.
