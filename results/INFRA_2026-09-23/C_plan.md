# C_plan -- ONE design that ends these classes, specified to implement

Written 2026-09-23 ~04:3xZ (**2026-09-23 00:3x ET**). Read-only
job. Nothing started, stopped, killed or edited outside this file. Inputs:
`A_inventory.md` (39 numbered failures, 11 classes), `B_diagnosis.md` (N1-N9 in
the code), and the code itself -- `run_all.ps1` (46 lines), `boot_all.ps1` (420),
`watch_bot.ps1` (231), `restart_bot.ps1` (677), `kalshi_collector.py` (411),
`crypto_feeds.py` (430), `research/replay.py` (829), `research/pindesk.py`,
`research/versioncheck.py`.

**End-of-job resources: disk 23.0 GiB free on C:; both recorders writing THIS
SECOND (`cfbenchmarks_value/20260923T04.jsonl.gz` mtime 04:31:29Z,
`index_replica/20260923T04.jsonl.gz` mtime 04:31:36Z, now 04:31:36Z);
`boot_all.log` still logging "31 python process(es) are blind ... all up;
nothing to do" as of 00:30:14 ET -- the 21-hour outage is live while this is
being written.**

---

## 0. THE ONE SENTENCE

Every one of the 39 failures has the same shape: **a consumer decided, on its
own, whether a producer it does not understand was healthy, by looking at
something that is not the data** -- a process table, a directory mtime, a file
size, a trailing median. The design inverts that: **every producer declares its
own health per STREAM, in numbers; one supervisor with no privilege and no kill
path turns those numbers into a verdict against a baseline checked into the
repo; exactly one actor owns each process; and every hole is written down
forever so no analysis can silently use a shorter window.**

Eleven pieces, P1-P11, in build order. For each: what it would have caught among
the 39, what it could break, the self-test that proves it, and the order.

### Two constraints that outrank every piece here

**C-A. Nothing in this design may touch or delay a hedge.** No new code runs
inside `trade_loop`. `pinrun`'s only addition is `Health.tick()` -- a dict
increment, plus a 30-second writer thread that swallows every exception. The
supervisor, the gap ledger and the archiver are separate processes and nothing
on the hedge path reads a file they write. **Self-test: make `results/health`
unwritable and assert every decision in a planted close is byte-identical, and
that a hedge is still sent.** This is `CURRENT_STATE.md`'s rule 3 applied to
infrastructure: write down what it BLOCKS, then prove it blocks nothing.

**C-B. The collector outranks everything, and no design may risk the tape to
protect itself.** Mechanically: the supervisor has NO kill path at all (its only
channel is a request file that the recorder's own parent executes on its own
child); the archiver never deletes a file it has not read back at the
destination; the disk shed always keeps `cfbenchmarks_value`; the RAM budget
names the two recorders as never-the-victim; and the one change that touches the
recorder (P7) ships only after a two-hour shadow run to a separate directory.

---

## 1. P1 -- DISK. The only hard deadline, and the cheapest 11x we will ever get

**Why first: 23.0 GiB free, 3.93 GB/day measured, ~4-5 days. `run_all.ps1` line
44-45 is `if ($free -lt 5) { Write-Host "LOW DISK - stopping" ; break }` -- the
watchdog EXITS ITS LOOP, so both recorders stop being restarted and the tape
ends. And with `boot_all` blind, nothing restarts `run_all.ps1` afterwards.**
Nothing else in this document matters if that fires.

### 1a. Measured tonight: where the 3.93 GB/day actually goes

Hour `20260923T03`, bytes on disk:

| channel | MB/hour | GB/day | share |
|---|---|---|---|
| `orderbook_delta` | 148.95 | **3.57** | **91%** |
| `trade` | 11.83 | 0.28 | 7% |
| `ticker` | 2.86 | 0.069 | 1.7% |
| `market_lifecycle_v2` | 0.29 | 0.007 | |
| `cfbenchmarks_value` | **1.59** | **0.038** | **1.0%** |
| `orderbook_snapshot` + `ok` + `event_lifecycle` + `subscribed` | 0.055 | 0.001 | |
| all of `feed_data` (bitstamp 7.5, coinbase 5.1, gemini 0.71, index_replica 0.74, kraken 0.69) | 14.70 | 0.353 | 9% |
| **total** | **180.3** | **3.93** | matches the measured 3.93 GB/day exactly |

**The thing every strategy in this project depends on -- the 1/sec settlement
index -- is 1.0% of the bytes.** That is the whole design of the shed.

### 1b. The shed: `break` becomes a narrowing, never an exit

`run_all.ps1` change, ~8 lines: at `$free -lt 8` it writes
`C:\kals\shed.json` naming the channels to drop, alerts, and **keeps looping**.
The collector reads that file at the top of every `handle()` batch (or on a
30-second poll) and stops WRITING the named channels -- it stays subscribed, so
nothing has to be renegotiated when the file is removed.

Shed ladder, from `results/streams.json` (`sheddable` rank), each step's
survival on 23 GiB:

| step | drops | GB/day after | days of tape left |
|---|---|---|---|
| 0 normal | nothing | 3.93 | 4-5 |
| 1 at < 8 GB | `orderbook_delta` | 0.36 | **~63** |
| 2 at < 6.5 GB | + `trade`, `ticker` | 0.045 | ~500 |
| 3 at < 5.5 GB | + `feed_data` except `index_replica` | 0.056 (index + replica only) | ~410 |
| floor | **`cfbenchmarks_value` and `index_replica` are NEVER sheddable** | | |

`run_all.ps1` never breaks its loop again; the `-lt 5` branch is deleted. Losing
the order book for a week is a bad week of analysis. Losing the settlement index
is the project.

### 1c. The archiver, as a producer with its own health stream

`research/pinarchive.py`, started and owned by the supervisor (P2). Every 10
minutes, for each channel directory:

1. take hour files older than `--keep-hours 48`, **never the current or previous
   hour**, at most `--max-per-pass 40`;
2. read the file end to end (gzip member scan + first and last record parsed) --
   a file that cannot be read is **never deleted**, it is recorded in the gap
   ledger as `unreadable` and left alone (that is the 16 dead hour files from
   09-01/02 and 09-02/03);
3. copy to `--dest` (the external SSD), then read the destination copy back and
   compare **byte length AND record count**;
4. only then delete the source, and append
   `{"channel":..., "hour":..., "dest":..., "bytes":..., "records":...}` to
   `results/gaps/archived.jsonl`, so `window_status()` (P4) answers
   "present, off-box, at <path>" rather than "missing";
5. write `results/health/archive.json`: GB freed this pass, GB/day trend, days
   to the shed threshold, files refused and why.

Until the SSD exists it runs `--report-only` (default) and publishes the numbers
only. **`--dest` missing is not an error and never triggers a delete.**

### 1d. Scorecard

- **Would have caught / prevented:** failure 39 (the disk deadline itself) --
  one item, and the one that would have cost the entire 68 GB tape. Also the
  second half of 8 and 9 (the two full collection stops): after a `break` on low
  disk nothing restarts `run_all.ps1`, and with `boot_all` blind that is exactly
  today's state.
- **What it could break:** an archiver bug deletes tape. Mitigated by read-back
  verification before delete, `--report-only` default, never touching the two
  newest hours, a per-pass cap, and the rule that an unreadable file is never
  deleted. A shed bug loses a channel we wanted: mitigated by the ladder being a
  checked-in file and by the shed being **write-suppression, not
  unsubscription** -- removing the file restores it within 30 s.
- **Self-test (`pinarchive.py --selftest`):** plant a tree with three hour files,
  one with a truncated gzip member, plus the current and previous hour. Assert:
  the truncated file is NOT deleted and IS recorded as `unreadable`; the two good
  files are copied byte-identical and record-count-identical and only then
  deleted; the current and previous hours are untouched; **NULL** -- with `--dest`
  absent, zero deletions and health says `BLOCKED`; and a planted dest whose copy
  is one byte short causes a refusal, not a delete.
  **Shed self-test (in `kalshi_collector.py --selftest`):** with a planted
  `shed.json` naming `orderbook_delta`, assert zero delta records are written and
  that `cfbenchmarks_value` count is unchanged; with no file, assert every
  channel writes (the NULL); assert `cfbenchmarks_value` is refused as a shed
  target even if the file names it.

---

## 2. P2 -- FUNCTION CHECKS, NOT LIVENESS: one health protocol, one supervisor

This is the piece that ends K1, and it is live right now: `boot_all` has logged
"all up; nothing to do" 130+ times over 21 hours while unable to see 31 of 42
python processes, because `Win32_Process.CommandLine` returns null to a
limited-token caller for a high-integrity process. **The fix is not a better
command-line read. It is to never read a command line again.**

### 2a. Producers declare health, per STREAM

`research/health.py`, ~200 lines, stdlib only. API:

```python
h = Health("kalshi_collector", streams=[...])   # names from research/streams.json
h.tick("cfbenchmarks_value", n=1, ts_ms=..., rx_ms=...)
h.seq_gap("orderbook_delta", expected=41, got=57)
h.retrying("socket", since=time.time())         # or h.retrying("socket", None)
h.selftest("ok")                                 # or "fail: <one line>"
h.connected("gemini/DOGEUSD", False)
```

A daemon thread writes `results/health/<producer>.json` every 30 s, atomically
(`tmp` + `os.replace`), and **every exception inside the writer is swallowed and
counted** (constraint C-A).

Shape, and the field names are the contract:

```json
{"producer":"kalshi_collector","pid":105304,
 "started":"2026-09-15T16:25:03Z","t":"2026-09-23T04:31:30Z",
 "lease_ok":true,"selftest":"ok","log":"C:\\kals\\logs\\collector-20260923.log",
 "streams":{
  "cfbenchmarks_value":{"n60":718,"last_ts":"2026-09-23T04:31:29Z",
                        "last_rx":"2026-09-23T04:31:29Z","seq_gaps_60":0,
                        "resubs_60":0,"retrying_since":null,"connected":true},
  "orderbook_delta":{"n60":84213,"...":"..."},
  "gemini/DOGEUSD":{"n60":0,"connected":false,"retrying_since":null}}}
```

**The producer reports NUMBERS and its own connection state. It never decides
OK/DEGRADED/DEAD.** The baseline lives in the repo, not in the producer, so K3
cannot come back through the back door.

A stream is `(producer, channel)` for the Kalshi recorder and
`(producer, exchange, symbol)` for the feeds -- so `gemini/DOGEUSD` is a stream,
and failure 2 (one exchange at 1 of 8 symbols for 7.3+ days, invisible to every
existing monitor) becomes a row that is DEGRADED from the first 30 seconds.

Producers to instrument: `kalshi_collector.py`, `crypto_feeds.py`,
`cdc_record.py`, `pinrun.py` (live and every paper arm, keyed by `--arm-name`),
`pinracearm.py`, `pinledgerd.py` (**nothing anywhere checks it today -- N4**),
`pindesk.py`, `pinphone.py`, `pinarchive.py`. `run_all.ps1` and `watch_bot.ps1`
write theirs in 6 lines of `ConvertTo-Json`.

### 2b. The manifest: `research/streams.json`, checked in

One row per stream. Numbers come from a **named** good window, measured once by
`research/baseline.py` (P11) and written as a dated artefact -- never a trailing
median.

```json
{"baseline":"BASELINE_2026-09-20.json",
 "window":"2026-09-20T00:00Z..2026-09-21T00:00Z","chosen_on":"2026-09-23",
 "streams":{
  "kalshi_collector/cfbenchmarks_value":
    {"expect_per_s":12.0,"degraded_below":8.0,"dead_after_s":60,
     "sheddable":false,"fallback":"crypto_feeds/index_replica","owner":"run_all"},
  "kalshi_collector/orderbook_delta":
    {"expect_per_s":1400.0,"degraded_below":280.0,"dead_after_s":60,
     "sheddable":1,"owner":"run_all"},
  "kalshi_collector/trade":
    {"expect_per_s":null,"zero_is_legal":true,"witness":"orderbook_delta",
     "degraded_seq_gaps_60":3,"owner":"run_all"},
  "crypto_feeds/gemini/DOGEUSD":
    {"expect_per_s":0.5,"degraded_below":0.05,"dead_after_s":300,"owner":"run_all"},
  "crypto_feeds/index_replica":
    {"expect_per_s":1.0,"degraded_below":0.9,"min_n_ex":3,"dead_after_s":60,
     "owner":"run_all"},
  "pinledgerd/ledger":
    {"expect_stale_s":900,"degraded_after_s":900,"dead_after_s":3600,
     "owner":"pinsuper"},
  "pinrun-live/eval":
    {"expect_per_min":1.0,"degraded_below":0.2,"dead_after_s":1500,
     "blind_rule":"pindesk.blind_of","owner":"watch_bot"}}}
```

Three rules that make the manifest do the work:

1. **A stream present in a health file but absent from the manifest is a FAILURE,
   not a default-OK.** That is how a newly added channel or symbol can never
   arrive silently (the Coin Race branch was lost exactly that way once).
2. **`trade` and `ticker` are bursty, so zero is legal.** They are judged by
   seq-gap count and by the *witness* rule from failure 7: silent while
   `orderbook_delta` is alive = DEGRADED. They can never be DEAD and can never
   trigger a kill.
3. **The supervisor refuses to start if the baseline window overlaps any
   DEAD/DEGRADED entry in the gap ledger.** A baseline measured over a broken
   window is the whole of K3, and this is the only mechanical way to stop it.

### 2c. `research/pinsuper.py` -- one supervisor, no privilege, no kill path

Loop every 30 s:

1. Read every `results/health/*.json`. **A health file older than 90 s means
   that producer is SILENT** -- its own liveness, from its own file, needing no
   permission of any kind.
2. For the five pid-file processes (`run_all.pid`, `watch_bot.pid`,
   `pinrun-live.pid`, `pinsuper.pid`, `pinarchive.pid`): pid file +
   `os.kill(pid, 0)`. **`Win32_Process.CommandLine` is never read.** Enforced by
   a self-test that greps `pinsuper.py` and `boot_all.ps1` for `CommandLine` and
   fails on a single hit.
3. Per-stream verdict against the manifest. Three states, and the ACTION for each
   is written down before the check ships:

| state | definition | action |
|---|---|---|
| **OK** | at or above `degraded_below` | nothing |
| **DEGRADED** | below `degraded_below`, above zero (or `min_n_ex` unmet, or seq gaps over the bar) | gap-ledger row; log; phone alert **with the number AND the baseline it is compared to**; **never restart** |
| **DEAD** | zero for `dead_after_s` | gap-ledger row; phone alert; **turn the declared `fallback` ON**; then: producer says `retrying_since` set -> **alert only, never restart**; no retry AND *every* stream of that producer is DEAD -> write a kill-request |

4. Write `results/health/verdict.json`: per stream the state, the observed
   number, the baseline, the action taken, and the `owner` allowed to act.
5. Append every DEGRADED/DEAD minute to the gap ledger (P4).
6. Escalate: **log always -> phone on a STATE CHANGE (never on every cycle) ->
   restart only what it owns.** No sentinel numbers in any alert ever: a missing
   value prints `unknown`, not the `9,999 min` that tonight's DEAF alert printed
   14 times.

**The single most important constraint: `pinsuper` has no code path that can
stop `kalshi_collector`, `crypto_feeds` or `pinrun --live`.** Its only kill
channel is `results/health/kill-request-<producer>.json` (reason, verdict, a
one-per-hour lease). `run_all.ps1` reads its own request file and kills **its own
child**, whose pid it already holds in `$jobs[$j.n].Id`. That is strictly better
than today: the actor knows exactly which process is its child, so boot_all's
"$hits.Count -ne 1 -- not killing blind" disappears along with the command-line
read. `watch_bot.ps1` keeps sole authority over the money bot; `pinsuper` never
requests a bot restart at all.

Self-test greps `pinsuper.py` for `Stop-Process`, `taskkill` and `os.kill` with
a signal, and fails on any.

### 2d. Who owns what -- and why two supervisors cannot fight

The 09-14 double-bot incident is the reason boot_all refuses while blind, and
that refusal is what produced tonight's 21-hour outage. Three mechanisms replace
it, and the refusal is deleted:

| process | started by | judged by | killed by |
|---|---|---|---|
| `kalshi_collector.py`, `crypto_feeds.py` | `run_all.ps1` | `pinsuper` | `run_all.ps1` (own child, on request) |
| `pinrun.py --live` | `restart_bot.ps1` | `pindesk.blind_of` + `pinsuper` | `watch_bot.ps1` only |
| `run_all.ps1`, `watch_bot.ps1`, `pinsuper.py` | `boot_all.ps1` (pid file dead) | `pinsuper` / each other's pid files | `boot_all.ps1` (stale heartbeat only) |
| paper arms, `pinledgerd`, `cdc_record`, `pinarchive` | `pinsuper` | `pinsuper` | `pinsuper` |

1. **One actor per process**, named in the manifest as `owner`. A verdict that
   names an owner other than yourself is information, not an instruction.
2. **A single-writer LEASE, taken by the producer itself.**
   `results/health/<producer>.lease` holds pid + start time, renewed every 30 s;
   a producer that cannot take a live lease **exits immediately with a log line**.
   A duplicate collector becomes impossible *at the only place it can be made
   impossible* -- inside the producer. That kills K8 (two writers on one gzip,
   which destroyed 14 h 23 min of the settlement index and an hour of
   `feed_data`) at the source, and it is what licenses deleting the `$blind`
   refusal.
3. **`pinsuper` has no kill path.** Even a supervisor with a wrong verdict cannot
   stop a recorder; it can only ask the recorder's own parent.

### 2e. `boot_all.ps1` rewritten -- 420 lines to ~80, and no privilege

Delete: `$procs = @(Get-CimInstance Win32_Process ...)`, `$blind`, `Running()`,
`RunningPy()`, all five `$blind -gt 0` refusals (lines 193-194, 216-217, 264-265,
278-279, 295-296), `DeafVerdict` and `-DeafTest` (moved into `pinsuper`, where
the producer's own `retrying_since` replaces a 150-line tail-grep heuristic), and
the **hardcoded 16-arm block** with `--hedge-price 0.60 --bank-brake 4.08` that
`CURRENT_STATE.md` says never to trust (it calls `sync_arms.ps1` instead).

Fix: **N3, the literal CRLF inside `"$repo\r\nesearch\pinledgerd.py"` at line
360** -- boot_all has never once been able to start the ledger refresher, and
`$started++` ran anyway.

Keep: start a process whose pid file is dead or whose heartbeat is stale, and
nothing else. It reads only pid files, `Get-Process -Id`, heartbeat mtimes and
`verdict.json`. **It works identically from a limited or an elevated token,
which is the whole point.**

`run_all.ps1` also gains: **its pid written EVERY loop, not only at start** --
`C:\kals\logs\run_all.pid` does not exist right now (N1) because the line that
writes it shipped 2026-09-17 and the running watchdog started at the 09-15 boot,
so the tape's watchdog is held up only by the command-line match that the
elevation bug breaks. Writing it every loop makes that self-healing forever.

### 2f. Scorecard

- **Would have caught / prevented, by number:** 1 (the elevation class ceases to
  exist -- nothing reads a command line), 2 (gemini per-symbol, DEGRADED in 30 s
  instead of invisible for 7.3 days), 3 and 4 (deaf-but-retrying detected in
  60 s, with the correct action: alert + fallback on, never a kill), 6 (the
  Thursday window becomes a named outage, not a fault), 7 (seq gaps counted in
  the health file -> DEGRADED alert), 8 and 9 (the two full stops: `run_all`'s
  own SILENT health file, and a `boot_all` that can act because the refusal is
  gone), 13 (`cdc_record` gets one stream and one log name), 14 (the class:
  liveness never decides anything again), 19 (a dead paper arm is a DEAD stream
  the supervisor owns and restarts), 21 (the hardcoded pre-sync arm list
  deleted), 22 and 23 (a producer whose own `--selftest` raises publishes
  `selftest:"fail"`, which is a stream the supervisor alerts on -- pindesk's had
  been raising for days and pinphone's for days, and nobody noticed).
  **14 of the 39, plus N4 (nothing watches `pinledgerd`) and N1.**
- **What it could break:** (a) a wrong manifest number floods the phone --
  mitigated by shipping **alert-only for the first 48 h** with every verdict
  compared by hand against reality before any action is enabled; (b) a lease bug
  makes a healthy producer exit -- mitigated by the lease being advisory on
  first ship (log "would have refused") and enforcing only after a week; (c) a
  `pinsuper` crash leaves nothing judging -- it writes its own health file and
  `boot_all` restarts it on a stale one, and its death is fail-safe because it
  cannot kill anything anyway.
- **Self-test:** see P10 -- the decisive one runs `pinsuper`'s whole decision
  function against a planted `results/health` tree with 12 scenarios, one per
  real incident, and fails if a healthy tree produces **any** action.

---

## 3. P3 -- THE RECORD MUST SURVIVE THE FAILURE (K4)

This is the class that makes every other class undiagnosable. 35 hours of lost
tape have "cause not recorded" against them, and the reason is two lines of
mechanism.

### 3a. Nothing truncates or overwrites a log, ever

- Every producer writes `logs/<name>-YYYYMMDD.log`, opened **append**.
- `run_all.ps1`'s `Start-Job2` uses
  `-RedirectStandardOutput "$Dir\logs\$name-$(Get-Date -f yyyyMMdd-HHmmss).out.log"`.
  Today it is a fixed `collector.out.log` with an overwrite redirect, so **every
  recorder restart destroys the evidence of the restart before it**; there is no
  record of any recorder restart ever having happened.
- `run_all.ps1` gets a log at all: today `logs\run_all.console.log` **does not
  exist** (N2), so every `Write-Host` it has emitted since the 09-15 boot went
  to a closed handle -- the tape's watchdog, the process CLAUDE.md says outranks
  everything, has produced no record in 8 days.
- `research/logcheck.py` greps every `.ps1` in the repo for
  `RedirectStandardOutput` with a non-dated target and fails. Wired into `go.py`
  PREFLIGHT beside `shadow.py` and `markers.py`.

### 3b. `restart_bot.ps1` -- the fix worth the most per line in this document

**N9: `$ErrorActionPreference = "Stop"` (line 48) plus an untried
`Start-Transcript` (line 59) means a failed transcript KILLS THE SCRIPT.** All 6
failures in `watch_bot.log` show **zero** `restart_bot:` stdout lines: never
validated, never killed, never started. **6 of 27 watchdog restarts (22%) did
nothing at all.** Two left the bot down to the next cycle; four were rescued by a
concurrent restart -- and that concurrency is itself the bug: the surviving
20:33 transcript header reads `-File C:/kals-repo/restart_bot.ps1` (forward
slashes) while `watch_bot` passes backslashes, so **two `restart_bot` instances
ran 18 s apart on the live money bot with no lock and no mutex.**

Three changes, all in the already-down path so none can touch a hedge:

1. Replace `Start-Transcript` with `function Rec($m) { Write-Host $m; try {
   Add-Content "$res\restart_bot-$(Get-Date -f yyyyMMdd).log" $m } catch {} }`.
   **A logging call can never abort the work it is logging.** That is the general
   rule; this is the instance.
2. A **restart lease**: `results/restart_bot.lease` (pid + ISO time, 180 s TTL),
   taken *before* the validate-then-kill block. A second instance logs "another
   restart holds the lease, exiting" and **exits without killing anything**.
3. `watch_bot.ps1` verifies **its own child produced a new pid**: record
   `pinrun-live.pid`'s content and mtime before the attempt, and after it require
   both to have changed. Today `Attempt()` only asks "does a pid exist", which a
   *concurrent* restart satisfies.

### 3c. One line elsewhere, same class

`research/pindesk.py:1551` uses `if "--live" in cl` -- a substring test, so the
`--paper-live` Coin Race arm is outside the operator's only control surface. Fix:
`if "--live" in cl.split()`, with a self-test asserting a command line containing
`--paper-live` is NOT matched.

### 3d. Scorecard

- **Would have caught:** 10 (no run_all log, collector.out.log truncated -- the
  root of "cause not recorded" on failures 8, 9, 5 and 11), 13 (two names for one
  log), 15 (the transcript failing exactly when needed, 6 times), 16 (already
  fixed, but this is its class), 24 (the `--live` substring). **5 named, and it is
  the precondition for diagnosing the other 34.**
- **Dollar case for 3b alone:** a bot crash at `:59:30` (where all 3 in-loop
  crashes landed) with the transcript path held -> `restart_bot` dies at line 59,
  `watch_bot` retries forever, each attempt dying identically. 8 overnight hours
  at +$1.52/close is **~$49 foregone**; if the crash happened while holding,
  nothing hedges and one unhedged collapse is **-$66 to -$108**.
- **What it could break:** nothing on the money path -- every line runs only when
  the bot is already down. Worst case a lease bug delays a restart by one
  `watch_bot` cycle (30 s), against the 22% of restarts that currently do
  nothing.
- **Self-test:** (a) hold the transcript/log path open with a competing writer and
  assert `restart_bot` still reaches `argument list ok: N flat strings` and still
  starts the bot; (b) plant a live lease and assert the second instance exits
  **without** a `Stop-Process`; (c) plant a stale (200 s) lease and assert it
  proceeds; (d) assert `watch_bot` reports `STILL DOWN` when the pid file did not
  change, even though a pid exists; (e) `logcheck.py` on the real repo must pass;
  (f) NULL -- a healthy restart with a writable log produces exactly the log lines
  it does today.

---

## 4. P4 -- THE GAP LEDGER: no analysis ever silently uses a shorter window

**Nothing has ever measured this.** Over 696 hours the settlement index holds
2,318,260 of 2,505,600 distinct seconds = **92.52%**; 52.0 hours of total
silence; 30 hour files missing; 22 unreadable, of which 16 are dead. Every
"n closes" number in the project is quoted against an unknown denominator.

### 4a. The file

`results/gaps/<channel>.jsonl`, append-only, one record per contiguous run:

```json
{"channel":"cfbenchmarks_value","from":"2026-09-23T00:05:00Z",
 "to":"2026-09-23T02:26:00Z","state":"dead","expected_per_s":12.0,
 "observed_per_s":0.0,"cause":"kalshi_ws_handshake_refused",
 "evidence":"113 handshake failures in collector-20260923.log",
 "source":"pinsuper","fallback":"index_replica","fallback_s":8460}
```

`state` is one of `dead` / `degraded` / `unreadable` / `archived` / `known`.
Append-only and never rewritten: a correction is a new row with
`"supersedes":"<id>"`, because a ledger that can be edited is a ledger that will
be edited to make a result look better.

### 4b. The three writers

1. **`pinsuper`, live** -- the authoritative one, because it alone knows the
   expected rate, the producer's retry state, and therefore the cause.
2. **`research/gapscan.py --backfill`** -- run ONCE now, over the 696 hours
   already on disk, plus any hour the supervisor was not running. It re-derives
   every number (nothing hand-typed from `A_inventory.md`): missing hour files,
   files that plain gzip cannot open, per-second presence from the message stamp.
   **It must divide by the REQUESTED window, and its self-test proves that.**
3. **`results/KNOWN_OUTAGES.md`** -> a small JSON of *named* windows, merged in
   with `state:"known"`: the **Thursday 07:00-08:00Z exchange maintenance**
   (08-27, 09-03, 09-10, 09-17, and the next one is **Thursday 2026-09-24 07Z**,
   tomorrow), the 16 unreadable hour files, the hours archived off-box. Those
   hours are then excluded **by name**, instead of being read as a thin market --
   which is exactly how they have been read four times.

### 4c. The API analyses call -- deliberately tiny, so it gets used

```python
from research.gapledger import window_status
st = window_status("cfbenchmarks_value", t0, t1)
st.complete    # bool
st.pct         # observed / REQUESTED seconds. NEVER / span-of-what-loaded.
st.missing_s   # int
st.causes      # {"kalshi_ws_handshake_refused": 8460, "double_write": 51780, ...}
st.fallback_s  # seconds available second-hand (P5)
st.unknown_s   # seconds no writer has an opinion about -- reported, never assumed complete
```

and one line every tape stage prints:

```
window 2026-09-15T00Z..2026-09-23T04Z  cfbenchmarks_value 92.5% complete
  (52.0 h missing: kalshi_ws 7.2 h, double_write 14.4 h, full_stop 26.8 h,
   reboot 1.7 h, small 1.1 h; 8.6 h available second-hand; 0.0 h unknown)
```

**Enforcement, or this becomes another file nobody reads:** `go.py` PREFLIGHT
gains `gaps.py`, which fails a stage that reads the tape and does not print a
completeness line -- the same mechanism as `markers.py` today. A missing ledger
entry is reported as `unknown`, loudly, and **never** as complete.

### 4d. N7's fix lands here

`replay.load_index` computes `cov = 100 * len(v) / max(span*3600, 1)` where
`span = (max(v) - min(v))/3600` -- the **denominator is the span of what
loaded**, so losing a whole day leaves coverage at 100%. And `<-- GAPPY` is a
`print`, fatal to nothing. Under this design the denominator is the requested
window from the ledger, and the status is a returned value the caller must
handle.

### 4e. Scorecard

- **Would have made permanently visible and attributable:** 3, 4 (the two Kalshi
  outages), 5 (14 h 23 min of corrupt index that a size-based scan can never see
  because the files are ABOVE the median size), 6 (the Thursday window, named
  instead of mistaken for a thin market), 7 (6.42% trade silence, 97 HOLE hours
  that must be excluded from any trade count), 8, 9 (the two full stops), 11,
  12, 38 (tape completeness, which nothing has ever measured). **10 of 39.** It
  is also the input to P5 and P11, and the mechanical answer to 33 (three
  baseline errors in five days).
- **What it could break:** a stage that legitimately reads one hour now has to
  print a line or fail PREFLIGHT -- deliberate, and `unknown` is always an
  allowed answer. A wrong cause attribution is a wrong story; mitigated by every
  row carrying its `evidence` string and `source`.
- **Self-test:** plant a synthetic channel with a **known 7-minute hole** and a
  known degraded stretch. Assert `window_status` returns exactly 420 missing
  seconds with the right cause; assert a clean window returns `complete=True`
  and zero causes (**the NULL**); assert that **deleting a whole day does NOT
  leave `pct` at 100%** (the N7 regression, pinned forever); assert a window with
  no ledger row returns `unknown_s > 0` and `complete=False`; assert an
  append-only violation (rewriting a row) is refused.

---

## 5. P5 -- THE INDEX FALLBACK, declared, automatic, and MARKED

**Tonight the tape was not lost.** `feed_data/index_replica` held **3,600 of
3,600 seconds in every hour of the 2 h 21 min Kalshi outage, including the 01Z
hour where `cfbenchmarks_value` has no file at all.** Nothing reads it as a
fallback and no report has ever said so. The DOGE 22:45 ET close -- the one that
lost money -- has an intact Kalshi index (843/900 s, 60/60 in the settlement
window); what is gone is its **order book**, which is P7's job. But the eight
closes from 20:30-22:15 ET have zero Kalshi index seconds and a complete replica.

### 5a. Recording: no new recorder, two changes to what exists

1. `crypto_feeds.index_replica` ends with `if len(out) > 2: w.write(...)` -- if
   fewer than three ASSETS are fresh, **the whole second is dropped**. Change to
   always write, and mark the second instead. A thin second recorded and labelled
   beats a second that does not exist.
2. Add per-asset `venues` (the names are already in `per_ex`) and `stale_ex`, so
   a one-exchange mid is visible on its face. **N6: `n_ex` is 1 to 4, not 3.** In
   `20260923T01` -- the hour with NO Kalshi index file -- the replica held
   3,600/3,600 seconds, but **DOGE was a one-exchange mid for 538 s and absent
   for 51 s**. The fallback exists; treating it as one uniform thing is wrong.
3. **N5: gemini is not a failing feed. Only one symbol was ever coded.**
   `crypto_feeds.py:216` is a single hardcoded
   `wss://api.gemini.com/v1/marketdata/BTCUSD?...` URL. Coinbase, Kraken and
   Bitstamp are 8 of 8 in every one of 2,107 five-minute windows; gemini is 1 of
   8 in every window. Fixing it is 8 per-symbol connections in the same `runner`
   pattern, and it raises DOGE's `n_ex` in exactly the hours that matter.
   **This needs hard rule 2 narrowed -- see P-H8.**

### 5b. Reading: one function, and the marking is a RENAME, not a caveat

`research/tape.py` (P6) exposes:

```python
rows = tape.load_index(window, allow_fallback=True)
# each row: {"t": sec, "value": float, "src": "kalshi"}
#        or {"t": sec, "replica_value": float, "src": "replica",
#            "n_ex": 2, "venues": ["coinbase","kraken"], "recon": True}
```

It reads the replica for a second **only** when the Kalshi second is absent
according to the gap ledger -- never to fill a second that exists, so the two can
never be silently blended.

**The marking has to be mechanical, because a caveat in prose is exactly what
this project keeps failing to carry through:**

- A reconstructed row's field is named **`replica_value`, not `value`.** A tool
  that wants the index and is handed a reconstruction gets a `KeyError`, not a
  wrong number. **Rename, don't caveat** -- this is the same trick that fixed
  `settle` vs `result` after a YES win was booked for every market.
- Any result computed over a window containing a `recon` row carries `recon_s`
  and `recon_pct`, and every report line is prefixed
  `RECONSTRUCTED 1800 s (50.0%), median n_ex 2` -- the count and the median
  `n_ex`, because a 4-venue reconstruction and a 1-venue one are not the same
  claim.
- A stage may not print a **settlement-level** number from a window over
  `--recon-max-pct` (default 0) without an explicit `--allow-recon`, and the
  self-test proves the flag is required.

### 5c. Calibration comes BEFORE any money decision rests on it

`research/replicacal.py`: regress replica against Kalshi second by second over
the **nine days at 100% index coverage** (08-31, 09-05, 09-10..13, 09-19..21),
per asset and per `n_ex`, and publish the sd of the difference **in the same
units as the settlement**. Then "the index was 23 bp from the strike" becomes
"23 bp, against the replica's own 6 bp sd at n_ex=3" -- and at n_ex=1 the honest
answer may be that the close cannot be adjudicated at all. Until that number
exists, a reconstructed close can say *what happened* but not *by how much*, and
the report must say so **in its first sentence**, the same way a replay claim
must.

### 5d. Scorecard

- **Would have recovered:** 3 (tonight: 8 closes, 2 h 21 min), 4 (09-22:
  4 h 49 min, ~19 closes), 5 (the 14 h 23 min of corrupt index, ~57 closes --
  the replica hours for 09-01/02 and 09-02/03 are readable), 8, 9 (the two full
  stops are NOT recoverable -- `crypto_feeds` was down too; the ledger records
  that honestly), 12 (the reboot: also both down). **Honest count: 3 windows
  fully recoverable (~21 h 33 min of index, ~76 closes), 3 windows where the
  ledger's job is to say the fallback was also absent.** Half a comparison
  reported as half.
- **What it could break:** someone treats a reconstruction as the index. Prevented
  by the rename (`replica_value`), the required `--allow-recon`, the mandatory
  `RECONSTRUCTED` prefix, and a self-test for each. Also: writing thin seconds
  grows `feed_data/index_replica` slightly (0.74 MB/hour today) -- negligible,
  and it is on the never-shed list.
- **Self-test:** build an hour where Kalshi has seconds 0-1799 and the replica has
  0-3599. Assert `load_index` returns exactly 1,800 `src:"kalshi"` + 1,800
  `src:"replica"` rows -- never 3,600 of either; assert `recon_pct == 50.0`;
  assert a stage computing a settlement without `--allow-recon` **fails**; assert
  a reconstructed row has no `value` key at all; **NULL** -- a complete Kalshi
  hour returns **zero** replica rows even though the replica file is full; and a
  planted `n_ex:1` stretch must appear in the printed median.

---

## 6. P6 -- ONE TAPE READER: streaming, exchange-timestamped, gap-aware, bounded

`research/tape.py`, ~400 lines. **102 files in `research/` open `*.jsonl.gz` or
call `read_jsonl_gz` today**, each with its own clock choice, its own memory
behaviour and its own idea of what a missing hour means.

### 6a. What it replaces, and in what order

It replaces the tape-loading half of `replay.py` (`read_jsonl_gz`,
`load_quotes`, `load_index`, `load_markets`) and the ad-hoc `gzip.open` calls
elsewhere -- **not all 102 at once**. The order is by money at risk:

1. `research/hedgetune.py` -- a **live hedge threshold** (0.60 -> 0.25) was set
   on its output, and keyed on the collector's receive time it was **$26.25 too
   cheap over 698 contracts**; re-keyed on the exchange's `ts_ms` it is $2.34
   off. It has not been re-run. First customer.
2. `research/racebook.py` -- times ticker by `_rx_ms` while timing the index by
   the CF print's own clock; a money test is pending on it.
3. `research/pinsim.py` -- times deltas by `ts_ms` (correct) but **snapshots by
   `_rx_ms`**.
4. `pindata.py`, `pinbook.py`, `tapegaps.py`, `pinpickoff.py`.
5. Everything else, opportunistically. PREFLIGHT gains a check that a file on a
   named list does not `import gzip` directly.

### 6b. The contract

```python
with tape.open("orderbook_delta", t0, t1, clock="exchange", mem_mb=300) as t:
    print(t.header())        # completeness line + clock + schema version
    for rec in t:
        if isinstance(rec, tape.Gap):
            ...              # a hole. Handle it or crash -- silence is not an option
        else:
            rec["t_ms"]      # the EXCHANGE's stamp
            rec["rx_ms"]      # ours, separate, never substituted
```

- **Exchange-timestamped by default.** `t_ms` is `msg.ts_ms`, or the `time`
  inside `cfbenchmarks_value`'s nested JSON string. `clock="receive"` must be
  passed **explicitly**, and the header prints which. A tool that does not print
  its clock fails PREFLIGHT. This closes K5, which currently sets a live money
  threshold: the collector's own `_rx_ms - ts_ms` on `orderbook_delta` has a p90
  of **2.7-4.7 s in every hour checked**, and was 1.9-4.4 s in the second before
  4 of 8 collapse fills -- worst exactly when prices move.
- **Gap-aware.** The iterator yields a `Gap(from, to, cause, channel)` sentinel at
  every hole the ledger knows about. A consumer must handle it or crash; a hole
  can never again be silently absorbed into a count.
- **Field discovery, promoted from a marker to an exception.** Paths come from
  `doctor.py`'s `schema.json`. If a requested field resolves for **fewer than 99%
  of a 1,000-record sample, `open()` RAISES.** On 2026-08-26 Kalshi's suffixed
  names (`yes_bid_dollars`, `price_dollars`, `delta_fp`) meant **68,976,084 of
  68,976,084 deltas went unparsed, 7 stages loaded zero quotes, and all of them
  exited 0.** `markers.py` labels that EMPTY after the fact; this refuses to open.
- **Memory-bounded.** Never more than one hour resident, never more than
  `mem_mb` of accumulator. A `tape.budget()` call at entry refuses to start when
  free RAM is under the manifest's floor -- the written RAM guard that does not
  exist today (CLAUDE.md's guard is disk only). **The two recorders are named in
  the manifest as never-the-victim**, and the rule is that a batch job caps
  itself rather than relying on the OS choosing the bigger process, which is the
  only reason the collectors survived five OOM kills.
- **Corrupt members salvaged and COUNTED.** A truncated gzip goes through
  `gzsalvage`; recovered and attempted counts are returned and appended to the
  ledger. The 16 dead hour files become a number in every report instead of a
  silent zero.

### 6c. Scorecard

- **Would have caught:** 5 (corrupt members counted instead of silently zero), 7
  (gaps as objects, not absences), 26 (five OOM kills; the pickoff tracker whose
  data still stops at 09-12, immediately before the drop the operator asked
  about), 27 (`hedgetune`, $26.25 over 698 contracts, and a live threshold set on
  it past its own pre-registered bar), 28 (`racebook`, biased in its own favour
  by an unmeasured amount with a money test pending), 29 (the collector as a
  timing source), 34 (68,976,084 of 68,976,084). **7 of 39, and three of them are
  live money decisions.**
- **What it could break:** the largest job here, and a bug in it is a bug in every
  analysis. Mitigated by (a) shipping it **beside** `replay.py`, not instead of
  it, and requiring a **byte-identical re-run** of three existing stages before
  any caller is switched; (b) one caller at a time, each with its old number
  recorded first; (c) the 99% field rule could refuse a legitimately sparse field
  -- so the threshold is per-field in `schema.json`, not global.
- **Self-test:** plant a tree with (a) a renamed field -> `open()` raises; (b)
  1,000 records of which 40% lack `ts_ms` -> raises rather than silently falling
  back to `rx_ms`; (c) a known 7-minute hole -> exactly one `Gap` with the right
  bounds; (d) a truncated member -> recovery count reported, no exception; (e)
  **NULL** -- a healthy hour yields no `Gap`, no warning and the same records
  `replay.read_jsonl_gz` yields today, compared element-wise; (f) stream 12 hours
  and assert peak RSS under 400 MB; (g) assert `clock="receive"` cannot be the
  default by grepping for the keyword's default value.

---

## 7. P7 -- SHIP THE 09-12 COLLECTOR FIX, with close-priority resubscribe

**K7 in one line: a three-part fix was written up and agreed on 2026-09-12; one
part shipped; the missing part 1 is what lost tonight's DOGE order book, 11 days
later.** And N8: `kalshi_collector.py`'s last commit is `ceb5bda`, **2026-09-06**
-- even the SIGTERM/gzip block that was credited as "part 2 shipped" predates the
write-up. 17 days untouched.

Measured cost of the gap: **2,267 SEQ_GAPS over 7.3 days (one every ~4.6 min)**,
and **38 five-minute windows (3.2 h) in which the index arrived and the book
recorded ZERO deltas**. The collector records a `_seq_gap` field
(`kalshi_collector.py:342`), increments a stat, and does nothing else.

### 7a. Three changes

1. **Resubscribe on a seq gap or reset**, per `sid`, without dropping the socket
   (`sub()` already exists at line 256). Log `[resub] <channel>/<ticker> seq
   <prev> -> <got>` and count it into the health file's `resubs_60`.
2. **After any reconnect, order the resubscribe list by TIME TO CLOSE, nearest
   first.** Today `refresher()` batches 14-16 markets with no ordering, so the
   market 30 seconds from settling is resubscribed after the one 14 minutes out
   -- or not at all. That is precisely why the DOGE 22:45 ET close has **zero
   `orderbook_delta` records for its last 13 minutes, including all of
   tau <= 45 s**, and why the book arrived at ~7% of normal for 22 minutes after
   the reconnect.
3. **Log every resubscribe** (part 3, never applied), and cap them:
   `--max-resub-per-min 60`, declared in the health file. A resubscribe storm is
   itself a failure, and the cap is what stops a pathological gap loop from
   becoming the thing that kills the tape.

### 7b. Scorecard

- **Would have caught:** 3 (the DOGE 22:45 ET book -- the money-losing close that
  cannot currently be autopsied), 4 (the 36-minute degraded resubscribe), 7 (the
  2,267 gaps and the 38 zero-delta windows). **3 named, and it is the highest
  value per line of anything in this document.**
- **What it could break: THE TAPE.** This is the only piece that changes a
  recorder, so it carries the heaviest gate:
  1. hard rule 2 must be narrowed first (P-H8) -- otherwise it cannot ship at
     all, which is the actual reason it has not;
  2. `--selftest` against a planted frame stream;
  3. **a 2-hour shadow run**: the patched collector writing to
     `C:\kals\kalshi_data_shadow` under a **different lease name**, compared
     record-count-per-channel-per-minute against the live one. Nothing about the
     shadow run may touch the live tape, and the disk cost (~330 MB for 2 h with
     `orderbook_delta` shed in the shadow) is checked against free space first;
  4. a `VERSIONS_INFRA.md` entry with a copy-pasteable revert to `ceb5bda`.
- **Self-test:** plant a frame stream containing a forward jump, a reset to 1, and
  a contiguous run. Assert exactly one resub for the jump, one for the reset, and
  **zero for the contiguous run (the NULL)**; assert close-priority ordering from
  a market list with known close times (nearest first, and the 30-second market
  before the 14-minute one); assert the rate cap fires at 61 and not at 60;
  assert a resub never drops or re-creates the socket.

---

## 8. P8 -- THE INFRA VERSION LOG AND THE OPEN-FIXES REGISTER (K7, K11)

All 38 entries in `results/VERSIONS.md` are money-bot behaviour. **Not one covers
`run_all.ps1`, `boot_all.ps1`, `watch_bot.ps1`, `kalshi_collector.py`,
`crypto_feeds.py`, `pindesk.py` or `pinphone.py`.** No dated record, no revert
command, and `versioncheck.py` looks only at `restart_bot.ps1`'s flags.
`boot_all.ps1` is broken right now and has no revert line; tonight's three infra
fixes have no entry.

1. **`results/VERSIONS_INFRA.md`**, same rules: `v-<name>`, UTC deploy time, git
   SHA, one sentence on what the machine now does differently, the evidence (or
   its honest absence), and **the exact revert command, copy-pasteable**. Written
   AT DEPLOY, never reconstructed. Backfill tonight's three (BLIND banner,
   stuck-recorder check, v-unidefer) and every piece here.
2. **`versioncheck.py` extended** to hash the deployed files -- `C:\kals\run_all.ps1`,
   `C:\kals\kalshi_collector.py`, `C:\kals\crypto_feeds.py`,
   `C:\kals\cdc_record.py`, `boot_all.ps1`, `watch_bot.ps1`, `restart_bot.ps1`,
   `research/pindesk.py`, `research/pinphone.py`, `research/pinsuper.py` -- against
   the hashes recorded in `VERSIONS_INFRA.md`, and fail on a mismatch. That also
   catches repo-vs-deployment drift, which `deploycheck.py` does for one file
   today (and which caused the 09-06 double-write).
3. **`results/OPEN_FIXES.md`** -- dated, owned, one line each, naming the incident
   it came from. A `barcheck.py`-style checker fails a run when an entry is older
   than 7 days with no movement. The 09-12 collector fix would have been visible
   every single day for 11 days instead of forgotten; the pickoff tracker rebuild
   has been outstanding since 09-17.

**Scorecard:** catches 37 (eight live changes with no entry) outright, and is the
reason 7 and 26 aged in place. It is also the only revert path the entire
infrastructure layer will have. Could break: nothing -- it is a checker; worst
case it fails a run until an entry is written, which is the point. Self-test:
plant a deployed file whose hash differs from the log and assert a non-zero exit;
plant a matching pair and assert zero (the NULL); plant an `OPEN_FIXES` entry 8
days old and assert a fail.

---

## 9. P9 -- A GUARD MAY REFUSE TO ACT. IT MAY NEVER REFUSE TO REPORT (K6)

The rule, enforced by a checker: **a guard that cannot act must still measure and
still alert, with the number and the baseline.**

- **`boot_all`'s blind refusal is deleted.** A safety check became a 21-hour
  outage of the entire boot layer. The lease (2d) makes the duplicate impossible
  at the producer, so the refusal has nothing left to protect.
- **The DEAF check gains an action**: turn the declared fallback on (P5). Today it
  only alerts, and it printed `9,999 min` -- which is not a number the operator
  can read. **No sentinel values in any alert; a missing value prints `unknown`.**
  Checked by a self-test that greps the alert formatters for `9999`.
- **The drawdown loop**: a terminal brake plus an automatic restarter is a loop --
  it halted the bot four times on 09-20 until a human edited
  `results/pinrun-hwm.json`, and **it re-arms at a bank of $767.12, i.e. after
  ~$151 more of losses**. The mechanical half ships now: the supervisor detects
  "same halt reason 3 times in 30 min", stops requesting anything, alerts with the
  reason, and names the file a human must clear. The policy half is his (P-H5).
- **`classify_bank_move` consults `pinxfer` before `shift_hwm` moves the mark.**
  18 of 19 "external" records are another bot's money; the fabricated "$58.37
  withdrawal" is exactly that minute's two oil settlements. Also: seed the
  high-water mark and the day-loss cap from **Kalshi's ledger minus pinxfer
  deposits**, never from `realised` (a session running total that resets on
  restart -- summing it once reported $1,183 on an account that had made $13.87).
- **Refusal records stop being de-duplicated per (close, market, gate)**, so the
  most valuable open "make more" question -- why the <=30 s window's volume fell
  65% -- becomes answerable. It needs a log field, not more analysis.
  `MAX_ATTEMPTS_PER_MARKET` is counted at the **signal** point, so three refusals
  inside 150 ms lock a market out of a whole close (13 lockouts in 12 closes, 11
  of which still had a standing offer at >= 99.5%): count it at the **send**
  point instead.

**Scorecard:** catches 1 (the refusal itself), 17 (the brake loop), 18 (invented
transfers), 30 (the de-dup and the lockout), 32 (summing `realised`, via the
seeding rule). **5 of 39.** Could break: **the lockout change touches the money
path**, so it is the one item here that needs a paper arm and a pre-registered
bar before live, and a written statement that it cannot block a hedge. Self-test:
assert no alert formatter can emit a sentinel; assert the loop detector fires on
3 identical halts in 30 min and NOT on 3 different ones (the NULL); assert
`shift_hwm` refuses to move on a bank change that `pinxfer` explains.

---

## 10. P10 -- SELF-TESTS THAT TEST THE INPUT, AND ONE THAT RUNS THE SUPERVISOR (K9)

The gate plants an answer in a synthetic world; **nothing checks that the real
input arrived at the expected rate.** That is why 68,976,084 of 68,976,084
records went unparsed with every self-test green.

1. **Every stream check gets a NULL and a PINNED-DEGRADED case.** Fail if the
   check fires on a healthy 60-second window; fail if it **misses a stream pinned
   at 1 of 8** (gemini, 7.3 days, invisible).
2. **One self-test RUNS `pinsuper`'s decision function** against a planted
   `results/health` tree, fake pid files and a fake gap ledger. Twelve scenarios,
   one per real incident: blind-token, deaf-retrying, deaf-stuck, gemini-degraded,
   disk-low, arm-dead, ledger-stale, bot-blind, double-write, corrupt-hour,
   fallback-on, known-Thursday-outage. Assert the verdict AND the action for each,
   and **assert a healthy tree produces zero actions.**
3. **A producer whose own `--selftest` raises publishes `selftest:"fail"`**, which
   is a stream the supervisor alerts on. That is failures 22 (pindesk's own
   self-test raising for days while the lab scored arms on markets they never
   traded) and 23 (pinphone's fixture failing on the operator's real deposits)
   caught automatically instead of by someone noticing.
4. **Kept unchanged:** `shadow.py` and `markers.py` in PREFLIGHT, the
   `_DEFAULT_*` rule (a self-test asserting a RUNNING value has refused to start
   the bot six times, once for 6 live minutes), and the `rindex`/anchored-line
   rule (a source-text self-test finds its own copy of the string -- 4 times in
   one session, once silently for days).
5. **The one still missing and not in this design's scope:** no self-test ever
   executes `trade_loop`. Three in-loop crashes in 14 days, all at tau = 30 s, one
   while holding (-$66.34). It belongs in the K1 build; `OPEN_FIXES.md` (P8) is
   what stops it being forgotten again.

**Scorecard:** catches 22, 23, 34, 35 (the `compression.py` stdlib shadow that
killed 14 of 16 stages), 36 (the self-test defect family). **5 of 39.** Could
break: a strict self-test refuses to start a producer -- which is exactly the
`--price-ceiling` 6-minute outage, so the rule stands: **assert `_DEFAULT_*`,
never the running global**, and a producer's self-test failure publishes a health
row rather than exiting.

---

## 11. P11 -- BASELINES AS CHECKED-IN ARTEFACTS (K3)

**Gemini's median IS 1 of 8. The tape's per-hour median INCLUDES the broken
hours. The corrupt index files are ABOVE the median size. "The pool halved" was
measured against the four busiest days on file.** A trailing median cannot detect
a stream that has been broken since before the window.

- `research/baseline.py` writes `results/BASELINE_<date>.json` from a **named**
  window; `streams.json` points at it by name and date with `chosen_by` and
  `chosen_on`.
- The supervisor **refuses to start** if the baseline window overlaps any DEAD or
  DEGRADED entry in the gap ledger. That is the mechanical death of K3.
- Every report quotes the baseline it used, **by name**, and completeness always
  divides by the REQUESTED window (N7).
- The standing rule "report the MEDIAN of every earlier day too" gets a helper so
  it is one call rather than a discipline.

**Scorecard:** catches 2 (the only way a stream stuck at 1 of 8 is ever flagged),
5 (a size check can never find an above-median corruption; a *readability* check
in the named baseline can), 33 (three baseline errors in five days, two of them
nearly changing live code). **3 of 39.** Could break: a badly chosen window
becomes the new wrong norm -- mitigated by the overlap refusal, the date in the
filename, and `chosen_by` naming who picked it. Self-test: plant a ledger with a
DEAD row inside the candidate window and assert the supervisor refuses to start;
plant a clean window and assert it starts (the NULL); assert a stream absent from
the manifest is a failure, not a default-OK.

---

## 12. THE HUMAN-ONLY ITEMS

Each: the fix, or why it must stay manual.

**P-H1. The 31 blind processes, right now.** Those processes were started from an
elevated session (`IsInRole(Administrator)=True`), and a limited-token `KalsBoot`
can never read their command lines. **The code fix (P2) removes the need entirely
-- nothing will read a command line.** Until then it is human: either a reboot or
clearing them. **Recommend shipping P2 rather than rebooting** -- a reboot costs
tape, and with `KalsBoot` interactive-only it may not come back at all until he
logs in. Separately, and this is a rule not a fix: **a session must stop starting
long-lived processes from an elevated shell.** The blindness began the minute the
arm fleet was rebuilt from an elevated session at 06:20-06:21Z on 09-22.

**P-H2. `KalsBoot` needs a logged-in session.** `LogonType=Interactive`,
`RunLevel=Limited`, `AutoAdminLogon=0`. After a reboot **nothing starts until he
logs in** -- that cost 1 h 43 min on 09-15. Fix: change the principal to `S4U`
("run whether logged on or not"), which needs **his password once** at install.
**Must stay human: it needs his credentials.** **Recommend S4U over auto-logon** --
auto-logon leaves an unlocked box with a trading account on it. One line in
`boot_all.ps1 -Install`, plus his password at the prompt.

**P-H3. Windows Update active hours are 15:00-09:00 ET**, so a reboot is
*permitted* 09:00-15:00 ET -- while he is at work. His machine's policy, so his
change: active hours to 06:00-23:00 ET, or pause updates. P-H2 makes a reboot
survivable either way, which is the more important of the two.

**P-H4. The external SSD.** Hardware; his purchase. **This is the deadline:
23.0 GiB free, 3.93 GB/day, ~4-5 days.** Until it arrives the archiver runs
report-only and **the shed (P1) is the whole protection** -- but the shed buys
~63 days at step 1 and ~500 at step 2, so it converts a hard deadline into a
degraded one. Say that plainly rather than letting the SSD look optional.

**P-H5. The drawdown mark needing a hand edit.** The brake is terminal and
`watch_bot` is automatic, so together they are a loop; a hand edit of
`results/pinrun-hwm.json` was the only exit, four halts later. The **mechanism**
is ours (P9: loop detection, the `pinxfer` consult, seeding the mark from the
ledger). The **policy is his**, three options: (a) the brake writes
`results/pinrun-live.stop` with a reason and a human clears it -- safe, costs
trading time; (b) it auto-clears after N hours; (c) it is removed because the
per-ET-day `--loss-cap 200` already does the job. **The mark itself should never
need a hand edit again**: seeded from Kalshi's ledger minus `pinxfer` deposits.

**P-H6. The desktop app cannot Pause or Stop the `--paper-live` race arm.** Code,
one line (P3c: `"--live" in cl.split()`). Human only in that it changes his
control surface, so he should be told it changed. Today it is stood down only by
`results/pinracepenny.stop`, the money test's own switch.

**P-H7. `pinpickoff --rebuild`.** Not human, but it has been OOM-killed twice at
~1.6 GB free and **its data still stops at 09-12, immediately before the drop he
was asking about.** It goes after P1 and P6 so it can stream under a RAM budget
instead of loading. It is an `OPEN_FIXES.md` entry from 09-17.

**P-H8. HARD RULE 2 MUST BE NARROWED, AND ONLY HE CAN DO IT.** Today: *"Never
modify anything under `kalshi_data/` or `feed_data/`."* The **program** is
`C:\kals\kalshi_collector.py` and `C:\kals\crypto_feeds.py`, and the rule has
been read as covering it -- which is why gemini has recorded 1 of 8 symbols for a
month and the seq-gap resubscribe is 11 days unshipped. **Proposed wording: never
modify the DATA; the recorder PROGRAM may change under a `VERSIONS_INFRA.md`
entry, a passing `--selftest`, and a shadow run to a separate directory.**
**Without this, P5's gemini fix and P7 cannot ship at all, and P7 is the single
highest-value change in this document.** This is the biggest thing on his list.

---

## 13. BUILD ORDER, AND WHY THAT ORDER

**Step 0 -- tonight, three one-liners, no design required.** Each independently
safe, each has already bitten:

1. `boot_all.ps1:360` -- the literal CRLF in `"$repo\r\nesearch\pinledgerd.py"`.
   boot_all has never been able to start the ledger refresher.
2. `restart_bot.ps1:59` -- `try`/`catch` round `Start-Transcript` (or the `Rec`
   function). **22% of watchdog restarts currently do nothing.**
3. `research/pindesk.py:1551` -- `"--live" in cl.split()`.

~20 minutes, one `VERSIONS_INFRA.md` entry. None touches the trading decision.

| order | piece | why here |
|---|---|---|
| 1 | **P1 disk** (shed first, archiver report-only) | ~4-5 days. Nothing else gets built if this fires. The shed alone is 4 days -> ~63. |
| 2 | **P2 health + supervisor + boot_all rewrite** | Ends the live 21-hour outage class and makes every later piece observable. **Alert-only for 48 h**, every verdict checked by hand, then actions enabled one owner at a time: arms -> pinledgerd -> cdc_record -> kill-requests to run_all last. |
| 3 | **P3 logs** | Cheap, and without it the next failure is undiagnosable again. Includes the restart_bot fix, which is the worst single money exposure here. |
| 4 | **P4 gap ledger + one-off backfill** | Required before any completeness or baseline claim, and it is P5's and P6's input. |
| 5 | **P5 index fallback** (read side now; the gemini fix needs P-H8) | Turns tonight's eight closes from "gone" into "second-hand, calibrated". |
| 6 | **P6 one tape reader** | Biggest job; depends on P4. First customer is `hedgetune` -- a live hedge threshold currently rests on a $26.25 error. |
| 7 | **P7 collector resubscribe** | Highest value per line, but it touches the tape, so it ships after the observability that would show it misbehaving, and only after P-H8 + a shadow run. |
| -- | **P8, P9, P10, P11** | Checkers. Each ships **with** the piece it guards, never at the end -- a checker written last is a checker written never. |

---

## 14. COVERAGE, HONESTLY COUNTED

Of the 39 inventory failures: **35 are prevented, detected, or made permanently
attributable** by one of P1-P11. Four are not:

- **20** (paper arms on flag lists frozen at launch, `arm-pin0.97` differing in
  16 settings) -- **already closed** by `sync_arms.ps1`; P2 adds detection of a
  dead arm, which was the remaining half.
- **25** (`pinsim`'s `yes_dollars_fp` snapshot bug) -- **already closed**, plus the
  standing rule that a replay finding is a hypothesis whatever its n.
- **31** (the bot's logs miss markets held when a run died: logs say -$161.14 for
  09-19, Kalshi says -$223.46; lifetime overstated by $72.34) -- **partly**;
  `pinday` reads the ledger now, and P9 adds seeding the day-loss cap from the
  ledger so a crash-orphaned loss counts. The log itself cannot be fixed; the
  ledger is the authority.
- **36**'s hardest part (no self-test ever executes `trade_loop`) -- out of scope
  here, in the K1 build, and held open by `OPEN_FIXES.md`.

Per piece: P1 = 1 (the biggest), P2 = 14, P3 = 5, P4 = 10, P5 = 3 windows fully
recoverable and 3 honestly not, P6 = 7, P7 = 3, P8 = 1 + the reason two others
aged, P9 = 5, P10 = 5, P11 = 3. Overlaps are real and deliberate: tonight's
outage is caught four different ways, which is the difference between a design
and eleven patches.

---

## 15. WHAT MAY NEVER HAPPEN -- the constraints as tests

1. **Nothing here runs inside `trade_loop`, and nothing on the hedge path reads a
   file this design writes.** Test: `results/health` unwritable -> every decision
   in a planted close byte-identical, and a hedge still sent.
2. **`pinsuper` cannot stop the collectors or the money bot.** Test: grep its
   source for `Stop-Process`, `taskkill`, `os.kill` -- any hit fails.
3. **Nothing reads `Win32_Process.CommandLine`.** Test: grep `pinsuper.py` and
   `boot_all.ps1` -- any hit fails.
4. **`cfbenchmarks_value` and `index_replica` are never shed and never archived
   from the current or previous hour.** Test: a `shed.json` naming them is
   refused.
5. **A file that cannot be read back at the destination is never deleted.** Test:
   a one-byte-short destination copy causes a refusal.
6. **A guard may refuse to act; it may never refuse to report, and never with a
   sentinel.** Test: no alert formatter can emit `9999`.
7. **A stream in a health file but not in the manifest is a failure, not a
   default-OK.** Test: an unknown stream fails the supervisor's startup.
8. **Completeness always divides by the REQUESTED window.** Test: delete a whole
   day and assert `pct` is not 100%.
