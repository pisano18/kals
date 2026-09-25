# CLAUDE.md

Guidance for Claude Code in this repo. This file is loaded on EVERY turn, so it
is kept tight; its full wording before 2026-09-25 is preserved verbatim in
`DOCS_ARCHIVE_2026-09.md`. No rule was dropped in that tightening.

## Where to read what

| need | read |
|---|---|
| **what is live NOW, decided, open, gotchas -- FIRST, and after every /clear** | `CURRENT_STATE.md` |
| every running process, arm, watcher and read date; the running log, newest first | top of `HANDOFF.md`; older: `HANDOFF_ARCHIVE_2026-09.md` |
| the operator's topic index ("Say: ..." handles) | `OPEN_WORK.md` |
| every live change, its evidence, copy-paste revert | `results/VERSIONS.md` |
| every money idea ever checked -- read before proposing one | `results/IDEA_LEDGER.md` (re-run the hunt: `research/sweep/README.md`) |
| the mental model: why the edge exists, the two contract families, the population trap, measured vs believed, bug classes -- read before changing the strategy; each section says what would falsify it | `THEORY.md` |
| killed approaches, measurement artefacts, the two unreconciled thesis versions, kill-criteria log -- read before resurrecting an idea or quoting a confidence number | `PROJECT_HISTORY.md` (split out of this file 2026-09-13, unedited; also holds this file's superseded 2026-09-06 status block) |
| hard rules, confirmed contract facts -- read, with the top of `HANDOFF.md`, before changing anything | `RUNBOOK.md` |
| the bias checklist | `BIASES.md` |
| what a scheduled/unattended session may and may not do | `GUARDIAN.md` |
| money numbers | `python research/pinday.py`, `results/kalshi_ledger.json`; deposits: `research/pinxfer.py` |

## What this is

Quantitative research into, and live trading of, an edge in Kalshi's 15-minute
crypto binaries: 12 up/down series (`KXBTC15M` and siblings) plus 2 Coin Race
relative-performance series. Every number here was produced by a script that
refuses to touch real data until its self-test passes.

**REAL MONEY IS DEPLOYED.** `research/pinrun.py --live` has traded the
operator's account since 2026-09-08. (This file once said "no money has been
deployed"; true when written, false since 2026-09-08.)

## Reporting to the operator -- STANDING, every message

The operator's rules, dated, in his words where quoted. They outlive any session.

**Format (2026-09-13, replacing the 2026-09-06 format).** *"I need more
efficient wording and shorter replies. Don't leave out info but I'm tired of
reading a book just to get to the reason something didn't work. Reason,
supporting evidence, whatever else I may need to know to come up with a plan or
new idea."* So: **reason first, then its evidence, then only what he needs to
act on.** No preamble, no restating the question, no recap of what was just done
unless it changed. Numbers carry units; a loss is quoted next to the return that
bought it; failures are reported as failures, never estimated.
*The superseded format, kept so the change is visible: three parts -- the answer
in plain language; a `Like you're five:` section; a `What I need from you:`
section. Set 2026-09-06, withdrawn 2026-09-13: the two sections duplicated the
answer and buried it.*

**Plain language, the WHOLE reply (2026-09-13; outranks the format rule).**
*"I need you to take what's important for me to know and consider and explain
it very simple. Like I'm five."* He is not a quant; jargon made the reports
useless. Not a plain-language SECTION after a technical one -- that was the
killed 09-06 format. These are not suggestions:
- No term he has not used himself unless defined in the same sentence in
  ordinary words. Never `tau`, `rho`, `MDE`, `Clopper-Pearson`, `bootstrap`,
  `adverse selection`, `standardised`, `IOC`, `p90` in a reply (fine in the
  repo, commits and code comments).
- Every number carries what it MEANS in dollars, days or times-out-of-a-hundred
  ("2.86%" alone is not a report; "loses about 3 times out of 100" is).
  Percentages become counts where a count is clearer.
- Say what it means for his money BEFORE how it was measured.
- Reason first, failures as failures, ET and hard rule 3 are unchanged: simple
  never means vague, and never rounds a bad number in a kind direction.

**ET only (2026-09-12, no exceptions, no expiry).** *"Use est only please for
ever."* Write `ET` -- EDT (UTC-4) March to November, EST (UTC-5) otherwise, so a
literal "EST" in July is an hour wrong. Convert; never give a UTC time, never
append UTC in brackets. Presentation only: **everything INSIDE the repo stays
UTC** (log filenames, `t` fields, close ids, tickers, commit messages,
`results/*.md`) -- the tape, exchange and settlement index are UTC, and a local
time written into data breaks at the November clock change. Convert at the
moment of speaking.

**Anything he must do or decide goes LAST (2026-09-13).** *"If you have
something I need to do or answer always put it in a dedicated section at the
end."* Head it `## What I need from you`, NOTHING else in it, one line per
decision or action, each answerable without scrolling back (restate the choice
inside the item). If there is nothing, omit the section; never pad it, never
invent a question. This does NOT bring back the 09-06 format.

**Length (2026-09-13; HARDENED 2026-09-18 because replies got long again).**
09-13: *"Only include what's needed for me to know and consider. If I don't need
to know it don't waste text on it. Just don't leave out anything important."*
09-18: *"I really need you to permanently be more concise your messages are
extremely long and eat tokens, can be exhausting to read multiple of, and make
me miss important things... That definitely doesn't mean think less or do less
detail, or miss extra stuff you think I should know, or not ask me questions,
just shorter overall replies."* The cut is in the WRITING, never the work: same
depth, same unprompted findings, same questions when a decision is his.
- **Say a thing ONCE.** He counted five admissions of one mistake in one reply:
  *"you said it was ur mistake 5 times there, just once is fine."* Same for a
  caveat, correction or warning -- repetition buries the next point.
- No paragraph re-explaining a table already on screen; no closing summary;
  lead with the answer to what he asked, not what was interesting to find.
- Cut every number he does not need to act on; keep every one he does.

**Priority order (2026-09-13, above all other work).** *"Anything that makes
more money, or makes us lose less, or identify things better is immediately a
top priority above absolutely all other things and we should constantly be
looking for anything that meets those criteria, with #1 being lose less or
identify better. Thats what this fucking lives and dies on."* So **lose less /
identify better > make more > everything else.** Tidying, refactoring, docs and
infrastructure only in service of those three, or when something is broken.
"Constantly looking" is standing: read-only measurement is run and reported,
never proposed. (See "Open questions" below: on 2026-09-17 he put max money
first.)

**The backtest is not evidence (2026-09-18).** *"Stop trusting that stupid
backtest it's never been accurate about anything."* Goes further than the
2026-09-10 amendment (which only certified `pinsim` for decision reproduction):
- A finding that rests on the replay is a HYPOTHESIS, whatever its n.
- Prefer, in order: (1) the raw index feed, (2) the trade tape, (3) our own live
  fills, (4) the replay. `research/pincalib.py` is the worked example: it answers
  from the index alone and its self-test fails if a replay import appears in its
  working code.
- When the replay is genuinely the only source, say so in the first sentence of
  the report, not a footnote.

**Every live change gets a version entry AT DEPLOY (2026-09-13).** *"Can we
start naming update versions so it's easier to revert when something goes
bad?"* The log is `results/VERSIONS.md`; it had LAPSED (eight live changes
09-11..13 with no entry, unnoticed because nothing checked). An entry is
`v-<short name>` with the UTC deploy time, git SHA, one sentence on what the bot
now does differently, the evidence (or its honest absence) and **the exact revert
command, copy-pasteable**. Write it WHEN deploying -- a later entry is a
reconstruction, and the 09-11..13 back-fill shows how thin those are.
**`python research/versioncheck.py` in any session that touches the live bot**:
it fails if `restart_bot.ps1` passes a flag VERSIONS.md does not mention, or
mentions with a different value.

**Posture.**
- Say what was measured and what was not. If a script fails, report the
  failure; never estimate what the output would have been.
- Reconcile arithmetic by hand before believing a good number -- every large
  edge this project produced was a measurement bug. When a result looks good,
  state what would make it an artefact, then check that thing.
- Report half a comparison as half a comparison; a loss is quoted next to the
  return that bought it.
- Do not ask permission for read-only measurement -- run it and report. Ask
  before anything that writes outside `results/` or the repo; never touch
  `kalshi_data`, `feed_data` or the collector.

## Resource protocol -- the collector outranks every job here (2026-09-06)

Set after a job was OOM-killed. The tape is unreproducible; an analysis is not.
- **Before concurrent work, measure free RAM and cap concurrency so the total
  fits with headroom.** `load_quotes` holds ~2-3 GB; two at once caused the kill.
  Prefer the cached cells under the session work directory to reloading.
- **After EVERY job, verify `kalshi_collector.py` and `crypto_feeds.py` are still
  alive, and say so in the report.** Both sit at 13-25 MB, so they are never the
  memory hog -- but silence about them is not evidence.
- **Report free disk in every status. The guard is 6 GB because 5 GB is a HARD
  COLLECTION STOP, not a slowdown.** `run_all.ps1` line 41,
  `if ($free -lt 5) { Write-Host "LOW DISK - stopping" ; break }`, exits the
  watchdog loop, so neither recorder is restarted and the tape ends. A guard below
  that could never fire in time (the earlier 4 GB figure was worse than useless).
  **Below 6 GB free: stop all analysis, write state, and say so loudly.** On
  2026-09-05 free disk reached 7.0 GB -- 2 GB from the stop -- and was reported
  as merely "tight".
- **Never kill `python.exe` broadly.** Filter on `*research*` (the recorders'
  command lines contain no `research`) AND on `Name='python.exe'` (a `-like`
  query also matches the querying shell itself):

  ```powershell
  Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object {$_.CommandLine -like '*research*'} |
    Select-Object ProcessId, CommandLine
  # to stop them: ... | ForEach-Object { Stop-Process -Id $_.ProcessId }
  ```

  The watchdog (`run_all.ps1`) checks liveness only every **300 s**, so anything
  killed costs up to five minutes of unrecoverable tape.

## Hard rules

1. **No order that risks real money without per-instance operator sign-off.**
   NARROWED 2026-09-06 -- read the amendment below before acting on this rule;
   `pinrun --live` runs under that sign-off. The original text, kept so the
   change is visible: *"Never place, amend, or cancel an order. No `POST
   /portfolio/orders`. `kalshi.pem` exists only so the WebSocket can authenticate
   for market data."*
2. **Never modify anything under `kalshi_data/` or `feed_data/`.** A collector is
   actively writing there.
3. **Never claim a result you did not measure.** If a script fails, report the
   failure. Do not estimate what the output would have been. (Not amended and
   never will be.)
4. **Cluster by close time; report `n` as markets or closes, never trades.**
   Hundreds of trades share one settlement outcome. All twelve crypto series
   settle on the same quarter hour, and at rho ~ 0.8 they are worth ~1.22
   independent observations per close, not 12.
5. **Never infer a price's unit from its magnitude.** The tick is tapered --
   0.1c below 10c and above 90c, 1c between -- so a half-cent quote is written
   `0.5` and any `x > 1` test reads it as fifty cents. Decide the unit once, from
   the whole sample.

### AMENDMENT 2026-09-06 -- hard rule 1 NARROWED BY THE OPERATOR

Stated loudly, per the standing requirement that a bar is never moved quietly.
Hard rule 1 and operating rule 1 both read *"never place, amend, or cancel an
order -- read-only only."* The operator replaced that, in his words:

> "My rule is narrower than you think: DON'T SPEND OR RISK MONEY. Everything
> else is open. Authenticated calls, non-GET methods, WebSocket channels you
> haven't subscribed to, account configuration."

> "no live orders and no real money without my explicit sign-off, per
> instance. That's it. That is the entire list."

The operative rule is therefore:
1. **No order that risks real money without per-instance operator sign-off.**
   Sign-off is per ORDER, not per session, not standing.
2. Demo orders are permitted -- the demo key is proven demo-only (200 with a $10
   balance on demo, 401 `NOT_FOUND` on production and production-elections,
   checked 2026-09-06).
3. Non-GET methods, authenticated calls and account configuration are open.
4. `kalshi_data/`, `feed_data/` and the running collector remain untouchable.

`research/` enforcement did not weaken: `ordercli.py` is still the only file
that can send a non-GET, still forces `post_only`, still requires `--live` plus
a sign-off token bound to the exact order and environment, and still defaults
to demo. (See "Open questions": memory records a broader 2026-09-07 permission.)

### AMENDMENT 2026-09-10 -- WHICH BACKTEST, AND WHAT IT IS ALLOWED TO CLAIM

Set by the operator after two days of thresholds tuned on a replay that had
never reproduced a real loss (the `yes_dollars_fp` snapshot bug, fixed
2026-09-10).
1. **`research/pinsim.py` is the only backtest.** It calls `pinrun`'s own `fair`,
   `net_edge`, `expected_value`, `billed_fee` and constants through `pinrun`'s own
   `IndexWS`, with one override (`spot()`, the wall-clock read). Anything that
   reimplements the decision is analysis, not a backtest, and must not be called
   one.
2. **Certified only for DECISION reproduction** -- 13 of 14 live signals to five
   decimals on 2026-09-10. **Not for loss rates.** It cannot model whether an
   offer is ours (live fill rate 70%), and the loss class hurting us -- adverse
   fills at extreme confidence -- is the population it cannot see.
3. **Every loss-rate claim comes from live fills** until pinsim reproduces live
   loss outcomes. Quote them as (gate version, n fills, n closes, window).
4. **No threshold is deployed from a replay without a holdout split AND a
   pre-registered live bar written before the number is seen.**
5. **NEVER QUOTE A LOSS RATE FROM THE TAPE. NOT ONCE, NOT WITH CAVEATS.**
   Measured 2026-09-11 at the live gate: the tape says 0.11% (1 of 891 markets,
   CI [0.00, 0.61]); live says 3.4% (2 of 59, CI [0.4, 11.7]). The intervals DO
   NOT OVERLAP -- a 31x gap. The cause is structural and permanent: the tape's
   population is "an offer was sitting there", ours is "someone actively sold it
   to us", and only the second is adversely selected. The 82c XRP fill we
   actually took does not exist anywhere in the replayed book. The tape is valid
   for what the index did, what the model computed, what the market did; INVALID
   for how often WE lose and what a rule would have cost US -- those come from
   live fills only. The operator caught this rule broken three times in one day;
   if a number is about our losses and its source is pindata/pinsim, it is not
   shown.

## Open questions for the operator (contradictions between his recorded words)

Found 2026-09-25 by the docs housekeeping; neither is settled by the docs. Until
he answers, follow the text above and put the question to him.
1. **Priority order.** 2026-09-13 (above): lose less / identify better first. On
   2026-09-17 (`HANDOFF_2026-09-17.md`): *"my first priority is make max money.
   Lose less happens to follow closely."*, and a memory note said that amended
   this file. The 2026-09-24/25 session recorded "lose less first" among his
   standing asks. Which leads?
2. **Money permission.** The 2026-09-06 amendment says sign-off per ORDER. Memory
   `money-permission-scope.md` records that on 2026-09-07 he granted blanket
   permission to spend on Kalshi (limits, his words: "Don't purchase margin in
   the way of like a loan. Be upfront if you need more money in the account" and
   "don't deposit my money, and don't put me in debt with loans or margin").
   Practice since 2026-09-08: the live bot sends orders with no per-order
   sign-off, and each NEW strategy family or size step is put to him first
   (far-rung live test 2026-09-25, coin-race size 2026-09-24).

## Commands

Everything runs from the repo root with plain `python` (stdlib only -- no
requirements file, no test framework, no linter config).

```bash
python research/go.py                      # every stage, writes RESULTS.md
python research/go.py --only pin           # one stage
python research/go.py --quick              # fewer null draws
python research/<stage>.py --selftest      # one file's self-test
```

**On the operator's box the `go.py` stage defaults (`./kalshi_data` etc.) are
WRONG.** Use the runner, or pass the paths:
`python research\pin.py --data C:\kals\kalshi_data --out C:\kals\fulltape`.

`run_when_away.ps1` is the unattended driver: pulls, refreshes settlements, runs
stages one at a time via `go.py --only`, commits `results/` back.
`.\run_when_away.ps1` (all 23, ~2h35m) or `.\run_when_away.ps1 -Only pin,informed`.
Measured budgets: `informed` ~13 min (7200 s cap), `pin` ~2.5 min, `strikes`
~75 s, `flow` ~100 min cold and seconds after, `maker` ~25 min; `oos` and `flow`
get 14400 s, everything else 3600 s.

**The lock.** `results/.run.lock` holds a PID; a second run refuses to start and
names it, because concurrent runs interleave the same report files and git tree.
The runner releases it in a `finally`, with a six-hour age backstop for a
hard-killed shell. (An earlier line said the lock must never be cleared by hand
-- WITHDRAWN: it stored `$PID`, the operator's own interactive prompt, which
outlives a run by days, so the lock never went stale. Found and cleared
2026-09-06; it held pid 558468.) Before deleting one by hand, run the
`*research*` process query above: nothing returned means no run is live and
the lock is safe to delete; something returned means wait.

## The self-test gate -- do not remove it

Every analysis file has a `--selftest` that builds a world where the answer is
known and fails if the estimator misses it *or* finds something in a world with
nothing planted. `main()` runs its own self-test before touching real data
unless `KALS_SELFTESTED=1` (which `go.py` sets after running the suite once).
This is not ceremony: every large edge here has been a measurement bug, and they
are not catchable by inspection. When adding an estimator, the self-test is the
deliverable; the estimator is the easy part.

`go.py` runs a `PREFLIGHT` before every stage, even under `--only`:
- `shadow.py` -- a module here shadowing a stdlib name breaks stages on Python
  versions the dev box lacks (`research/compression.py` once killed 14 of 16
  stages on 3.14 while passing on 3.11).
- `markers.py` -- a stage that prints "loaded nothing" must then stop.
  `EMPTY_MARKERS` in `go.py` labels such stages EMPTY so a null is never read as
  a result; prose that trips those patterns mislabels a good run.

**The working loop that produced everything here:** (1) write the stage AND its
self-test together -- plant an answer, fail on a miss or on a find in an empty
world; (2) `--selftest` until green, then `markers.py` and `shadow.py`; (3) run
on real data; (4) read the output adversarially -- most of what this project
learned came from a number that could not be true (a maker capturing a negative
half-spread, a binary whose win and loss did not sum to 100c, a "gap" whose
median size was 1); reconcile by hand when something looks good; (5) commit
with the reasoning, not just the change.

## Architecture

**Collection (always running, do not disturb).** `run_all.ps1` is a watchdog
around `kalshi_collector.py` (Kalshi WebSocket -> `kalshi_data/<channel>/*.jsonl.gz`,
one file per channel per hour) and `crypto_feeds.py` (constituent exchange
books -> `feed_data/`). Channels: `cfbenchmarks_value` (1/sec settlement index --
the one everything depends on), `ticker`, `trade`, `orderbook_snapshot`,
`orderbook_delta`. Series live in `CRYPTO_15M` in `kalshi_collector.py`; adding
one there and copying the file to `C:\kals` is the whole deployment, because the
watchdog runs the collector from there, not from the repo.
`research/newseries.py` verifies a series is actually arriving -- `discover()`
skips an unknown ticker with no error and no log line, which is how the Coin
Race branch was silently lost once. Known live gaps: `KXADA15M`, `KXBCH15M`,
`KXTON15M` and `KXCRYPTOCOMP15M` return zero settled markets.

**Settlement pull.** `kalshi_fulltape.py` writes `fulltape/markets.json`
(strike/close/result per ticker) and `tapes.json`. Outcomes come from `result`;
`settle` is the index *level*, and confusing the two once booked a YES win for
every market. Use `endgame.outcome_of()`.

**Analysis (`research/`).** Each file is a standalone stage: a docstring saying
what it measures and why, a `--selftest`, and a `main()` that loads real data.
`go.py` holds the ordered `STAGES` list plus per-stage input guards and time
budgets. Shared infrastructure:
- `replay.py` -- `load_quotes`, `load_index`, `load_markets`, `SERIES_TO_INDEX`.
  Loaders discover field paths from the data (via `doctor.py`'s `schema.json`)
  rather than assuming names: Kalshi renamed fields once and 68,976,084 of
  68,976,084 deltas went unparsed while every stage exited 0.
- `engine.py` -- `var_factor`, `N_AVG`, `fee_per_contract`, `tick_at`.
- `settlewin.py` -- `partial()`, the locked/remaining split of the settlement
  window.
- `endgame.py` -- `scan`, `evaluate`, `summarise`, `redraw_null`, `outcome_of`.
  `pin.py` is a filter built entirely on these.
- `tdist.py`, `gzsalvage.py`, `power.py` -- t critical values, salvaging
  truncated gzip, MDE arithmetic.

**Reports.** `go.py` writes `RESULTS.md` (gitignored, local only). The committed
artefacts are `results/RESULTS_<stage>.md`, one per stage, written by
`run_when_away.ps1 --only` and pushed. Results are read back from git, so a stage
whose publish step fails has produced nothing readable -- the runner says so
loudly and prints the two commands that recover it.

## Settlement model (established, do not re-derive)

Settlement is the mean of 60 discrete 1-second CF Benchmarks prints, and
`strike(N+1) == settle(N)` exactly -- one strike per window, which is why
cross-strike arbitrage is undefined here rather than absent.

With `tau` seconds left, `60 - tau` of those prints are already recorded, so
`Var(settle - strike) = 880 sigma^2` and `sd/sigma` collapses far faster than
`sqrt(tau)` -- 9.7x too large at `tau = 10`. Fair value is
`Phi(((locked_sum + r*spot)/60 - K)/sd)`, and its sensitivity to sigma is exactly
zero at 50c. That collapse is the mechanism the surviving strategy (`pin.py`)
rests on.

Makers pay no fee; takers pay `0.07*p*(1-p)`.

## Writing new analysis

- State the MDE before the estimate. "No effect" and "no power" are different
  results; the report must not conflate them.
- Sample on an exogenous grid (fixed times to close), not on trade arrivals.
  Occupation-time selection biases the point estimate and survives clustering.
- Any forward-looking test needs a backward-looking companion that must be large.
  A null from an estimator never shown capable of finding anything is
  uninterpretable.
- Any signed markout needs a random-sign control. Volatility is symmetric,
  direction is not; an absolute-move version once fired at t = +11 on a tape with
  provably zero adverse selection.
- A guard that discards data needs its own null: print how much it throws away on
  a healthy feed. A guard that discarded everything once looked exactly like a
  thin tape.
- Floor cluster counts (30) before claiming significance, and print the
  multiple-looks threshold when a table shows many cells.

## This machine, and git

Early sessions ran in a remote container with no data and could only hand the
operator commands. A CLI on the box holding `C:\kals` runs the stages itself.

| | |
|---|---|
| repo | `C:\kals-repo` |
| tape (do not touch) | `C:\kals\kalshi_data` |
| constituent feeds (do not touch) | `C:\kals\feed_data` |
| settlements | `C:\kals\fulltape` |
| deployed collector | `C:\kals\kalshi_collector.py` -- a **copy**, not the repo file |
| branch | `claude/file-uploads-70rtjl` (work here) |

`results/` is committed; `kalshi_data/`, `feed_data/`, `fulltape/`, `flow_cache/`,
`RESULTS.md`, `schema.json` and the other generated JSON are gitignored.
