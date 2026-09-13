# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Read-only quantitative research into whether a tradeable edge exists in Kalshi's
15-minute crypto binary markets: 12 up/down series (`KXBTC15M` and siblings)
plus 2 Coin Race relative-performance series. No money has been deployed. Every
number in this repo was produced by a script that refuses to touch real data
until its self-test passes.

`PROJECT_HISTORY.md` holds the killed approaches, the known measurement
artefacts, the two unreconciled thesis versions and the kill-criteria change
log -- read it before resurrecting an idea or quoting a confidence number.
It was split out of this file on 2026-09-13 purely to cut per-turn context
cost; nothing in it was edited.

Read `RUNBOOK.md` (hard rules, confirmed contract facts) and `HANDOFF.md`
(newest section first — the running log of what is measured, alive, and dead)
before changing anything. `BIASES.md` is the checklist.

## How to report to the operator — STANDING, every message

Set 2026-09-06 by the operator. These are not optional and they outlive any
single session.

**REVISED 2026-09-13 by the operator, replacing the three-part format below.**
His words: *"I need more efficient wording and shorter replies. Don't leave out
info but I'm tired of reading a book just to get to the reason something didn't
work. Reason, supporting evidence, whatever else I may need to know to come up
with a plan or new idea."*

**Every response: reason first, then the evidence for it, then only what he
needs to act on.** No preamble, no restating the question, no summary of what
was just done unless it changed. The `Like you're five:` and `What I need from
you:` sections are WITHDRAWN -- they duplicated the answer and buried it. If
there is nothing he needs to decide, say nothing about it.

Numbers still carry units. A loss is still quoted next to the return that
bought it. Failures are still reported as failures, never estimated.

**ALL TIMES TO THE OPERATOR ARE EASTERN. STANDING, set 2026-09-12, no
exceptions and no expiry.** His words: *"Use est only please for ever."*
Write them as `ET` -- the zone is EDT (UTC-4) from March to November and EST
(UTC-5) the rest of the year, so a literal "EST" in July would be an hour
wrong. Convert; never hand him a UTC timestamp and never append the UTC one
in brackets.

This is presentation only. **Everything INSIDE the repo stays UTC** -- log
filenames, `t` fields, close identifiers, market tickers, commit messages,
`results/*.md`. The tape, the exchange and the settlement index are all UTC,
and a local timestamp written into data is a bug waiting for the November
clock change. Convert at the moment of speaking, not before.

*The superseded format, kept so the change is visible:*
> Three parts -- the answer in plain language; a `Like you're five:` section;
> a `What I need from you:` section. Set 2026-09-06, withdrawn 2026-09-13.

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

## Resource protocol — the collector outranks every job here

Set 2026-09-06 after a job was OOM-killed. The tape is unreproducible; an
analysis result is not. So:

- **Before starting concurrent work, measure free RAM and cap concurrency so
  the total fits with headroom.** `load_quotes` holds ~2-3 GB. Two of them at
  once is what caused the kill. Prefer the cached cells under the session work
  directory over reloading.
- **After EVERY job, verify `kalshi_collector.py` and `crypto_feeds.py` are
  still alive, and say so in the report.** Both normally sit at 13-25 MB, so
  they are never the memory hog — but silence about them is not evidence.
- **Report free disk in every status. The guard is 6 GB, and the reason is
  that 5 GB is a HARD COLLECTION STOP, not a slowdown.** `run_all.ps1` line 41
  is `if ($free -lt 5) { Write-Host "LOW DISK - stopping" ; break }` — the
  watchdog *exits its loop*, so both recorders stop being restarted and the
  tape ends. A guard set below that number could never fire in time to prevent
  anything; the earlier 4 GB figure was worse than useless.
  **Below 6 GB free: stop all analysis, write state, and say so loudly.**
  On 2026-09-05 free disk reached **7.0 GB** — 2 GB from the collection stop —
  and was reported as merely "tight".
- **Never kill `python.exe` broadly.** Filter on `*research*`:

  ```powershell
  Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object {$_.CommandLine -like '*research*'} |
    Select-Object ProcessId, CommandLine
  ```

  `kalshi_collector.py` and `crypto_feeds.py` carry no `research` in their
  command lines, so that filter spares them.

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

- `pin` — **ALIVE, small, and going to forward test.** Out of sample
  **+2.54c per contract, t=+5.0**. It is a TAKER and the book is thin: median
  resting size 69 contracts, and 50 fails to fill 42.3% of the time. At a
  fillable cap of 50 the bootstrap 95% interval on $/day is **[+19, +48]
  one-per-close** — small, and **confidently positive**. The honest sentence
  is "pin makes ~$33/day and we are confident it is positive."
  **PRIMARY OPEN RISK, above everything else: the backtest cannot test whether
  we win the race for a stale quote.** In the backtest we always get the
  quote; in reality we are racing everyone else for it, and real fills will be
  worse by an unknown amount. Two further caveats travel with every pin
  number: the sample is **9 days**, so the worst close in it is not the real
  downside; and the money is concentrated (top 10 of 336 closes = 45%), which
  is real but is a screen most fat-tailed strategies fail. Note 78.3% of
  closes are individually profitable, which is not a lottery shape.
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

---

# AMENDMENT 2026-09-06 — hard rule 1 has been NARROWED BY THE OPERATOR

**This is a change to a hard rule, dated and stated loudly, per the standing
requirement that a bar is never moved quietly.**

Hard rule 1 above, and operating rule 1, both read *"never place, amend, or
cancel an order — read-only only."* The operator has replaced that, in their
own words:

> "My rule is narrower than you think: DON'T SPEND OR RISK MONEY. Everything
> else is open. Authenticated calls, non-GET methods, WebSocket channels you
> haven't subscribed to, account configuration."

and

> "no live orders and no real money without my explicit sign-off, per
> instance. That's it. That is the entire list."

**The operative rule is therefore:**

1. **No order that risks real money without per-instance operator sign-off.**
   Sign-off is per ORDER, not per session, not standing.
2. Demo orders are permitted — the demo key is proven demo-only (200 with a
   $10 balance on demo, 401 `NOT_FOUND` on production and on
   production-elections, checked 2026-09-06).
3. Non-GET methods, authenticated calls and account configuration are open.
4. `kalshi_data/`, `feed_data/` and the running collector remain untouchable.
   That rule did not change.

**The old text is left in place above rather than edited out**, so that anyone
reading later sees what the rule was before and when it moved. `research/`
enforcement did not weaken: `ordercli.py` is still the only file that can send
a non-GET, still forces `post_only`, still requires `--live` plus a sign-off
token bound to the exact order and environment, and still defaults to demo.

**Separately: hard rule 3 ("never claim a result you did not measure") is
NOT amended and never will be.**

---

# AMENDMENT 2026-09-10 — WHICH BACKTEST, AND WHAT IT IS ALLOWED TO CLAIM

Set by the operator after two days in which every threshold was tuned on a
replay that had never reproduced a real loss (the `yes_dollars_fp` snapshot bug,
fixed 2026-09-10).

1. **`research/pinsim.py` is the only backtest.** It calls `pinrun`'s own
   `fair`, `net_edge`, `expected_value`, `billed_fee` and constants through
   `pinrun`'s own `IndexWS`, with one override (`spot()`, the wall-clock read).
   Anything that reimplements the decision is analysis, not a backtest, and must
   not be called one.
2. **It is certified only for DECISION reproduction** — 13 of 14 live signals
   reproduced to five decimals on 2026-09-10. **It is not certified for loss
   rates.** It cannot model whether an offer is ours (live fill rate 70%), and the
   loss class that is hurting us — adverse fills at extreme confidence — is the
   population it cannot see.
3. **Every loss-rate claim comes from live fills** until pinsim reproduces live
   loss outcomes. Quote them as (gate version, n fills, n closes, window).
5. **NEVER QUOTE A LOSS RATE FROM THE TAPE. NOT ONCE, NOT WITH CAVEATS.**
   Measured 2026-09-11 at the live gate: the tape says 0.11% (1 of 891
   markets, CI [0.00, 0.61]); live says 3.4% (2 of 59, CI [0.4, 11.7]). The
   intervals DO NOT OVERLAP -- a 31x gap. The cause is structural and
   permanent: the tape's population is "an offer was sitting there", ours is
   "someone actively sold it to us", and only the second is adversely
   selected. The 82c XRP fill we actually took does not exist anywhere in the
   replayed book.
   The tape is valid for: what the index did, what the model computed, what
   the market did. It is INVALID for: how often WE lose, and what a rule
   would have cost US. Those come from live fills only. The operator caught
   this rule being broken three times in one day; if a number is about our
   losses and its source is pindata/pinsim, it does not get shown.
4. **No threshold is deployed from a replay without a holdout split AND a
   pre-registered live bar written before the number is seen.**
