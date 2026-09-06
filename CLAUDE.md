# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Read-only quantitative research into whether a tradeable edge exists in Kalshi's
15-minute crypto binary markets: 12 up/down series (`KXBTC15M` and siblings)
plus 2 Coin Race relative-performance series. No money has been deployed. Every
number in this repo was produced by a script that refuses to touch real data
until its self-test passes.

Read `RUNBOOK.md` (hard rules, confirmed contract facts) and `HANDOFF.md`
(newest section first — the running log of what is measured, alive, and dead)
before changing anything. `BIASES.md` is the checklist.

## Hard rules

1. **Never place, amend, or cancel an order.** No `POST /portfolio/orders`.
   `kalshi.pem` exists only so the WebSocket can authenticate for market data.
2. **Never modify anything under `kalshi_data/` or `feed_data/`.** A collector
   is actively writing there.
3. **Never claim a result you did not measure.** If a script fails, report the
   failure. Do not estimate what the output would have been.
4. **Cluster by close time; report `n` as markets or closes, never trades.**
   Hundreds of trades share one settlement outcome. All twelve crypto series
   settle on the same quarter hour, and at rho ~ 0.8 they are worth ~1.22
   independent observations per close, not 12.
5. **Never infer a price's unit from its magnitude.** The tick is tapered —
   0.1c below 10c and above 90c, 1c between — so a half-cent quote is written
   `0.5` and any `x > 1` test reads it as fifty cents. Decide the unit once,
   from the whole sample.

## Commands

Everything runs from the repo root with plain `python` (stdlib only — no
requirements file, no test framework, no linter config).

```bash
python research/go.py                      # every stage, writes RESULTS.md
python research/go.py --only pin           # one stage
python research/go.py --quick              # fewer null draws
python research/<stage>.py --selftest      # one file's self-test
```

On the operator's Windows box, `run_when_away.ps1` is the unattended driver: it
pulls, refreshes settlements, runs stages one at a time via `go.py --only`, and
commits `results/` back to the branch.

```powershell
.\run_when_away.ps1                        # every stage
.\run_when_away.ps1 -Only pin,informed     # a subset
```

It holds a PID lock in `results/.run.lock` and refuses to start while another
run is live. Concurrent runs would interleave the same report files and the
same git tree.

## The self-test gate — do not remove it

Every analysis file has a `--selftest` that builds a world where the answer is
already known and fails if the estimator misses it *or* finds something in a
world with nothing planted. `main()` runs its own self-test before touching
real data unless `KALS_SELFTESTED=1` (which `go.py` sets after running the
suite once).

This is not ceremony. Every large edge this project has produced has been a
measurement bug, and they are not catchable by inspection. When adding an
estimator, the self-test is the deliverable; the estimator is the easy part.

`go.py` runs a `PREFLIGHT` before every stage, even under `--only`:

- `shadow.py` — a module here that shadows a stdlib name breaks stages on
  Python versions the dev box does not have. `research/compression.py` once
  killed 14 of 16 stages on 3.14 while passing on 3.11.
- `markers.py` — enforces that a stage which prints "loaded nothing" then
  stops. `EMPTY_MARKERS` in `go.py` labels such stages EMPTY so a null is never
  read as a result; prose that trips those patterns mislabels a good run.

## Architecture

**Collection (always running, do not disturb).** `run_all.ps1` is a watchdog
around `kalshi_collector.py` (Kalshi WebSocket → `kalshi_data/<channel>/*.jsonl.gz`,
one file per channel per hour) and `crypto_feeds.py` (constituent exchange books
→ `feed_data/`). Channels: `cfbenchmarks_value` (1/sec settlement index — the
one everything depends on), `ticker`, `trade`, `orderbook_snapshot`,
`orderbook_delta`. Series live in `CRYPTO_15M` in
`kalshi_collector.py`; adding one there and copying the file to `C:\kals` is
the whole deployment, because the watchdog runs the collector from there, not
from the repo. `research/newseries.py` verifies a series is actually arriving —
`discover()` skips an unknown ticker with no error and no log line, which is
how the Coin Race branch was silently lost once. Known live gaps: `KXADA15M`,
`KXBCH15M`, `KXTON15M` and `KXCRYPTOCOMP15M` return zero settled markets.

**Settlement pull.** `kalshi_fulltape.py` writes `fulltape/markets.json`
(strike/close/result per ticker) and `tapes.json`. Outcomes come from `result`;
`settle` is the index *level*, and confusing the two once booked a YES win for
every market. Use `endgame.outcome_of()`.

**Analysis (`research/`).** Each file is a standalone stage with a docstring
stating what it measures and why, a `--selftest`, and a `main()` that loads real
data. `go.py` holds the ordered `STAGES` list plus per-stage input guards and
time budgets. Shared infrastructure:

- `replay.py` — `load_quotes`, `load_index`, `load_markets`, `SERIES_TO_INDEX`.
  Loaders discover field paths from the data itself (via `doctor.py`'s
  `schema.json`) rather than assuming names; Kalshi renamed fields once and
  68,976,084 of 68,976,084 deltas went unparsed while every stage exited 0.
- `engine.py` — `var_factor`, `N_AVG`, `fee_per_contract`, `tick_at`.
- `settlewin.py` — `partial()`, the locked/remaining split of the settlement
  window.
- `endgame.py` — `scan`, `evaluate`, `summarise`, `redraw_null`, `outcome_of`.
  `pin.py` is a filter built entirely on these.
- `tdist.py`, `gzsalvage.py`, `power.py` — t critical values, salvaging
  truncated gzip, MDE arithmetic.

**Reports.** `go.py` writes `RESULTS.md`, which is gitignored and therefore
local only. The committed artefacts are `results/RESULTS_<stage>.md`, written
one per stage by `run_when_away.ps1 --only` and pushed to the branch. Results
are read back from git, so a stage whose publish step fails has produced
nothing readable — the runner says so loudly and prints the two commands that
recover it.

## Settlement model (established, do not re-derive)

Settlement is the mean of 60 discrete 1-second CF Benchmarks prints, and
`strike(N+1) == settle(N)` exactly — one strike per window, which is why
cross-strike arbitrage is undefined here rather than absent.

With `tau` seconds left, `60 - tau` of those prints are already recorded on
disk, so `Var(settle - strike) = 880 sigma^2` and `sd/sigma` collapses far
faster than `sqrt(tau)` — 9.7x too large at `tau = 10`. Fair value is
`Phi(((locked_sum + r*spot)/60 - K)/sd)`, and its sensitivity to sigma is
exactly zero at 50c. That collapse is the mechanism the one surviving strategy
(`pin.py`) rests on.

Makers pay no fee; takers pay `0.07*p*(1-p)`.

## Writing new analysis

- State the MDE before the estimate. "No effect" and "no power" are different
  results and the report must not conflate them.
- Sample on an exogenous grid (fixed times to close), not on trade arrivals.
  Occupation-time selection biases the point estimate and survives clustering
  untouched.
- Any forward-looking test needs a backward-looking companion that must be
  large. A null from an estimator never shown capable of finding anything is
  uninterpretable.
- Any signed markout needs a random-sign control. Volatility is symmetric and
  direction is not; an absolute-move version once fired at t = +11 on a tape
  with provably zero adverse selection.
- A guard that discards data needs its own null: print how much it throws away
  on a healthy feed. A guard that discarded everything once looked exactly like
  a thin tape.
- Floor cluster counts (30) before claiming significance, and print the
  multiple-looks threshold when a table shows many cells.

## Git

Work on `claude/file-uploads-70rtjl`. `results/` is committed; `kalshi_data/`,
`feed_data/`, `fulltape/`, `flow_cache/`, `RESULTS.md`, `schema.json` and the
other generated JSON are gitignored.
