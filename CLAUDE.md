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

## How to report to the operator — STANDING, every message

Set 2026-09-06 by the operator. These are not optional and they outlive any
single session.

**Every response is formatted in three parts, in this order:**

1. **The answer first, in plain language.** Numbers carry units.
2. **A section headed `Like you're five:`** — what was just done and what is
   happening next, written for someone who knows nothing about trading or
   code. No jargon. Any term like *null*, *markout*, *t-stat* or *fair band*
   is defined in the same sentence it appears in.
3. **A section headed `What I need from you:`** — the explicit next action, or
   `nothing, I'm continuing` when there isn't one.

**Never end a message without parts 2 and 3.**

**Posture:**

- Say what was measured and what was not. If a script fails, report the
  failure. Never estimate what the output would have been.
- Reconcile arithmetic by hand before believing a good number. Every large
  edge this project has produced has been a measurement bug.
- When a result looks good, state what would have to be true for it to be an
  artefact, then go and check that thing.
- Report half a comparison as half a comparison. A loss is quoted next to the
  return that bought it.
- Do not ask permission for read-only measurement — run it and report. Ask
  before anything that writes outside `results/` or the repo, and never touch
  `kalshi_data`, `feed_data`, or the collector.

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


---

# Project history (appended 2026-09-06)

The sections below were supplied by the operator. Where the repo or the tape
could check a claim, it was checked; where they disagree, **both readings are
recorded and neither is picked**. Resolve the flagged items before relying on
either version.

## Operating rules

1. Never place, modify, or cancel a live Kalshi order. Read-only only.
2. Never move real money.
3. Do not resurrect a killed approach without evidence that specifically
   overturns the stated reason it was killed.
4. Do not touch the running collector in `C:\kals` — collecting since
   2026-08-25, and the data is not reproducible.

## Killed approaches

- **Dutch-book basket arbitrage** — killed structurally. The fee function peaks
  at `p = 0.50`, which prices out balanced baskets. Monte Carlo showed passive
  legging needs implausible fill rates.
- **Exhaustive-basket arbitrage** — killed empirically. A 16-hour run priced
  467,907 ladders and found no usable locks. Two false-positive classes: (a)
  categorical markets, where Kalshi's `mutually_exclusive` flag means
  *at most one wins*, not *exactly one wins*; (b) far-dated ladders, where
  sub-$1 totals are the time value of money rather than mispricing. Genuine
  numeric ladders ran ~13c too expensive at the median, best +7c at depth 0-1.
  The dead-bracket effect is real but insufficient.
- **15-minute scalping in low-volume markets** — superseded by the
  research-first plan.
- **Crypto delta-neutral basis trades** — yields below hurdle, and
  auto-deleveraging events destroyed correctly-hedged positions in late 2025.

*Repo note, not a contradiction:* `research/strikes.py` independently found
that the 15-minute crypto series carry **one strike per window**
(`strike(N+1) == settle(N)`), so ladder/basket arbitrage is **undefined** for
this product rather than merely unprofitable. The kills above concern
categorical and numeric-ladder markets elsewhere on Kalshi. The same scanner
applies unchanged to the Coin Race legs, which must sum to 100c.

## Confirmed mechanics

- Settlement = 60s BRTI average. Strike = opening 60s TWAP.
  `Var(settle - strike) = 880 * sigma^2`.
  *Verified:* `research/settlement_math.py` checks 880 against the
  continuous-time approximation. The strike identity is the same fact as
  `strike(N+1) == settle(N)` — abutting windows make the opening TWAP of one
  the closing TWAP of the last.
- Fees quadratic: `0.07 * P * (1-P)`, multiplier 1.
  *Verified:* `engine.fee_per_contract`.
- Tick grid `tapered_deci_cent`: 0.1c below 10c and above 90c, 1c between.
  *Verified:* `engine.tick_at`.
- WebSocket `cfbenchmarks_value` requires the param `index_ids`
  (`BRTI`, `ETHUSD_RTI`, ...). *Verified:* `kalshi_collector.py`.
- `/historical/*` is stale to ~2026-06-24 and ignores `series_ticker` on
  trades; use `/markets?status=settled` and `/markets/trades`.
  **Not verifiable from this repo** — no stored response proves the staleness
  date, and checking it needs a live API call.

## Known artefacts — do not repeat

1. **Truncation.** An earlier result claimed 26 mispriced cells with 21c
   edges. That was `limit=200` returning only each market's LAST 200 prints.
   Any analysis paging the trades endpoint must confirm full coverage first.
2. **Sweep-level reporting.** Kalshi reports a single sweep as multiple prints
   at different price levels. **SETTLED 2026-09-06 on `ts_ms`** over 12,000,000
   trades (`research/informed.py`, `sweep_shape()`):

   | multi-price (ticker, instant) groups | `ts_ms` | whole second | control |
   |---|---|---|---|
   | groups | 6,330,052 | 1,225,485 | 1,661,130 |
   | trades per group | **1.90** | **9.79** | 6.11 |
   | multi-price share | 10.7% | 57.2% | 76.9% |
   | single-sided AND monotone | **96.6%** | 28.3% | **12.9%** |
   | consecutive exchange `seq` | 99.8% | 23.2% | 32.8% |

   **The answer is PER LEVEL, and it rests on the shape, not the count.** At
   the true instant, multi-price groups are one-sided monotone ladders walking
   the taker's own direction over consecutive `seq` — a book being walked. The
   control (groups of trades ADJACENT in time but never simultaneous, drawn to
   the same size distribution) scores 12.9%, so the test is reading sweep
   structure and not merely that a busy book trends.

   **The earlier 59.0% / median-8-legs figure was wrong and must not be
   quoted.** It grouped by `msg.ts`, which is exactly `floor(ts_ms/1000)`, so
   "same instant" meant "same second". Its own arithmetic gave it away:
   4,000,001 trades in 401,591 groups is **9.96 prints per "instant" on one
   ticker**, where the true instant gives 1.90. Grouped by second, only 28.3%
   of multi-price groups have sweep shape at all. `ts_ms` is on 100% of trade
   messages, `created_time` on 0%, and `edge.load_trades` still reads `ts` —
   it was not changed, because that timestamp is what every other stage is
   calibrated against (see the reference-quote staleness item in `HANDOFF.md`).

   Consequence: the touch leg of a sweep is its own print at its own price and
   is already inside `at-touch`, so **the at-touch maker P&L stands as
   measured and the -0.42c branch is closed.** A per-print statistic can still
   weight one taker decision several times (median 4 legs, max 342).

   **Scope matters here, and getting it backwards destroys a valid result —
   see the contradiction flagged below.**

## Thesis state — TWO VERSIONS ON RECORD, NOT RECONCILED

**Version A (operator, and `RUNBOOK.md` lines 45 and 128):** full-tape
calibration on 2.1M trades across 450 markets shows the market is efficient.
71 price/time cells, mean `t = -0.008`, sd 0.775, only 3 cells at `|t| >= 2`
against 3.2 expected by chance; the single `t = 4.1` cell flips sign in
adjacent time buckets. Confidence in a tradeable edge: **~3-5%**.

**Version B (this repo's 2026-09-06 run outputs):** the sample is now
**38,519,252 trades over 14,485 markets with quotes and 10,796 with
settlements** — roughly 18x the trades and 24x the markets of Version A. On
that tape two results sit outside their own market-is-right nulls, out of
sample:

- `pin.py`, tau <= 20s, edge floor 0.5c: realised **+2.54c, t = +5.0** on 335
  closes against an MDE of 1.54c, with sigma recalibrated only on earlier
  closes. Its `t` has risen on every successive tape: 3.0, 3.7, 4.5, 4.9, 5.0.
- `informed.py`, fills at the touch: maker **+0.48c, t = +6.4** on 17,139,809
  fills over 1,071 closes, random-sign control clean at `t = -0.9`.

**These cannot both be current.** Version A's numbers are real but were
measured on a sample ~5% the size of today's, and the two live results
post-date it. Do not quote 3-5% as the standing confidence without saying
which sample it refers to, and do not quote the new results as settled either
— see `HANDOFF.md` (newest section first) for their caveats, chiefly that
`pin`'s tail is thin (1 flip in 262, headroom 1.9x) and the maker result's
**capacity is unmeasured**.

## Contradictions flagged, not resolved

1. **Cause of the 26-cell artefact.** The operator attributes it to
   truncation (`limit=200`). `RUNBOOK.md` line 20 attributes it to the wrong
   clustering unit — trade-count statistics wrong by ~14x. Both are real bugs
   and both were present; which produced that specific number is unresolved.
   Fixing only one is not sufficient.
2. **Deduplicating sweeps.** The operator's rule is "deduplicate sweeps into
   single economic trades before computing anything." That is right for
   **taker-decision** statistics, and wrong for **maker-fill** statistics.
   Per-level reporting is precisely why the at-touch maker measurement is
   valid: a quote resting at the touch is filled by the touch **leg**, which
   is its own print at its own price. Collapsing a sweep to one VWAP print
   would hide that leg in the deeper buckets and turn a measured +0.48c into
   roughly -0.42c — the exact question `sweep_shape()` was built to settle.
   Note also that this project already controls the "one event counted many
   times" problem for *inference* by clustering on close time and reporting
   `n` as markets or closes, which is a stronger fix than deduplication.
   **Apply per scope; do not apply globally.**
3. **Short-cadence equity markets.** The operator states none exist, so the
   half-fee lever is unavailable at frequency. `HANDOFF.md` line 1488 states
   the opposite from the authoritative `frequency` field: the true
   `fifteen_min` universe is 16 series — 14 crypto plus **`KXINX15M`
   (S&P 500) and `KXNDQ15M` (Nasdaq 100)**. `IDEAS.md` B3 lists their fee
   schedule as an open, cheap, high-value check. If the repo is right the
   lever may exist; if the operator is right B3 should be struck. One API call
   settles it.
4. **"Model vs book mid is the last test."** That test has been run.
   `endgame.py` and `pin.py` both score model fair value against the book, and
   the result is **not flat** — see Version B. Either this open question
   predates those stages and is already closed, or it means something narrower
   than `pin` measures. Clarify before applying the stated kill.

## Kill criteria

To be filled in by the operator. Do not populate these from inference.

- **Threshold:** _______
- **Minimum sample:** _______
- **Result that ends the project:** _______

Until these are set, no run may be described as decisive, and no stage may
report a result as project-ending.


---

# Session handoff — reading this from a CLI on the operator's machine

Everything above was written from a **remote container with no data**. That
session could only write code and self-tests, then hand the operator a command
to run. If you are reading this from a CLI on the box that holds `C:\kals`,
that loop is gone: **you can run the stages yourself.** Read this section
before doing so.

## Where things are

| | |
|---|---|
| repo | `C:\kals-repo` |
| tape (do not touch) | `C:\kals\kalshi_data` |
| constituent feeds (do not touch) | `C:\kals\feed_data` |
| settlements | `C:\kals\fulltape` |
| deployed collector | `C:\kals\kalshi_collector.py` — a **copy**, not the repo file |
| branch | `claude/file-uploads-70rtjl` |

The stage defaults in `go.py` are `./kalshi_data` etc., which are **wrong on
this machine**. Either use the runner, which passes the real paths, or pass
them explicitly:

```powershell
python research\pin.py --data C:\kals\kalshi_data --out C:\kals\fulltape
```

## Running work

Prefer the runner — it handles paths, per-stage reports, the PID lock, the
settlement refresh, and the commit/push:

```powershell
cd C:\kals-repo
.\run_when_away.ps1 -Only pin              # one or more stages
.\run_when_away.ps1                        # all 23, ~2h35m
```

Rough budgets, measured: `informed` ~13 min (7200s cap), `pin` ~2.5 min,
`strikes` ~75s, `flow` ~100 min on a cold cache and seconds after,
`maker` ~25 min, `oos` and `flow` get 14400s, everything else 3600s.

Two things that will bite:

- **The lock.** `results/.run.lock` holds a PID; a second run refuses to start
  and names the PID to stop. `run_when_away.ps1` now releases it in a
  `finally`, with a six-hour age backstop for a hard-killed shell.

  An earlier version of this line said the lock is never deleted and must not
  be cleared by hand. **That was written on a wrong assumption and is
  withdrawn.** The script stores `$PID`, which is the PowerShell process
  *running the script* — launched from a prompt that is the operator's own
  interactive shell, which outlives the run by days. So the liveness check
  could never see the lock go stale and the runner refused to start forever.
  Found and cleared 2026-09-06 (the lock held pid 558468, a live prompt).

  **Before clearing one by hand, check that no run is actually live:**

  ```powershell
  Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object {$_.CommandLine -like '*research*'} |
    Select-Object ProcessId, CommandLine
  ```

  Nothing returned means no analysis is running and the lock is safe to
  delete. Something returned means wait.
- **The collector must keep running.** If you ever need to stop analysis
  processes, filter on `research`, never on `python.exe` alone:

  ```powershell
  Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object {$_.CommandLine -like '*research*'} |
    ForEach-Object { Stop-Process -Id $_.ProcessId }
  ```

  `kalshi_collector.py` and `crypto_feeds.py` have no `research` in their
  command lines, so that filter spares them. The watchdog (`run_all.ps1`)
  only checks liveness every **300 seconds**, so anything killed costs up to
  five minutes of unrecoverable tape.

## The working loop that produced everything above

1. Write the stage **and its self-test together**. The self-test is the
   deliverable; plant an answer, and fail if the estimator misses it *or*
   finds something in a world with nothing planted.
2. Run `--selftest` until green, then `markers.py` and `shadow.py`.
3. Run against real data.
4. **Read the output adversarially before believing it.** Most of what this
   project has learned came from a number that could not be true — a maker
   capturing a negative half-spread, a binary whose win and loss did not sum
   to 100c, a "gap" whose median size was 1. Reconcile the arithmetic by hand
   when something looks good.
5. Commit with the reasoning, not just the change.

## State as of 2026-09-06

**Two results are alive** (both detailed in `HANDOFF.md`, newest first):

- `pin` — buy the endgame's stale quotes at `tau <= 20s`. Out of sample
  **+2.54c, t = +5.0** at edge floor 0.5c. Low floors only; 1.0c and 2.0c have
  headroom at or below 1.0x and are not safely positive.
- `informed` — market-making at the touch. **+0.48c per fill, t = +6.4** on
  17.1M fills, takers there carrying zero information (t = 0.2). Sweeps print
  per level (59% of same-instant groups, median 8 legs), so the touch leg of a
  sweep is already counted.

**Immediate next actions, in order:**

1. **Run `pin` once.** The all-coins portfolio table (`run_portfolio`,
   `evaluate_markets`, `_walk_markets`) was pushed *after* the last run and
   **has never executed against real data**. It reports P&L per close summed
   over every coin, coins per close, and the worst single close. Twelve series
   settle on the same quarter hour at rho ~ 0.8, so this is leverage, not
   diversification — read the worst-close column first.
2. **Build the queue-position simulator.** `+0.48c` is per fill; how many fills
   a resting quote actually receives is unmeasured, and it is the only thing
   between the maker result and a number in dollars. The rebuilt book in
   `flow.py` is now replay-correct (seq-ordered, stale fills quarantined) and
   is the input.
3. **Fix `KXCRYPTOCOMP15M`.** It is in `CRYPTO_15M` but nothing arrives;
   the ticker is wrong or the series does not exist under that name. One API
   call. `KXCRYPTOLEAD15M` **is** recording (since 2026-09-04) and needs days
   of tape before it is testable. Verify with:

   ```powershell
   python research\newseries.py --data C:\kals\kalshi_data
   ```

4. **Settle contradiction 3** (short-cadence equity series) with one API call —
   it decides whether `IDEAS.md` B3 lives or is struck.

**Do not** re-run `flow` unless the book itself is in question; it costs ~100
minutes on a cold cache and neither live result depends on re-mining it.

## What this project has never done

No order has ever been placed. No money has been deployed. Nothing above
changes that, and the kill criteria are still blank.
