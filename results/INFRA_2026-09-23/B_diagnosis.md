# B -- Why the recorders and trackers keep breaking: the classes, diagnosed in code

Investigator `diagnose`, 2026-09-23 ~04:1x-04:5xZ (2026-09-23 00:1x-00:5x ET).
**Read-only. Nothing started, stopped, killed, signalled or edited outside this
file.** Companion to `A_inventory.md` (the incident list); this file is the
causes, the mechanisms, and the residue.

**End-of-job resource check (CLAUDE.md requires it):** both collectors ALIVE and
writing -- `kalshi_data/cfbenchmarks_value` newest write 0.8 s old,
`orderbook_delta` 0.1 s, `trade` 0.1 s; `feed_data` all five channels < 2 s;
`cdc_data` writing. Free disk **25.23 GB (1e9) / 23.50 GiB** -- ABOVE the 6 GB
guard, and ~2-4 GB higher than A_inventory's 21.34 GB measured 40 min earlier,
so something was deleted or a temp file freed; the daily burn (3.93 GB/day) is
unchanged and the deadline moves by at most a day. All heartbeats fresh:
`watch_bot` 2 s, `pinphone` 7 s, `pinledgerd` 52 s (910 settlements).

Code read directly: `run_all.ps1` (repo and the deployed `C:\kals` copy --
byte-identical, as are `kalshi_collector.py` and `crypto_feeds.py`),
`boot_all.ps1`, `watch_bot.ps1`, `restart_bot.ps1`, `research/pindesk.py`
(`recorder_ok`, `blind_of`, `health`), `research/pinphone.py` (`alerts_tick`),
`research/pinledgerd.py`, `research/replay.py` (`load_index`),
`research/versioncheck.py`. Logs read: `results/boot_all.log`,
`results/watch_bot.log`, `results/restart_bot.last.log`,
`C:\kals\logs\*`. Tape measured by streaming single hour files only (no
`load_quotes`, python peak well under 400 MB). **Nothing here rests on the
replay.**

---

## 0. NINE THINGS FOUND IN THE CODE TONIGHT THAT CHANGE THE DESIGN

These are new or they correct A_inventory. They are listed first because three
of them make the "one design" wrong as written.

### N1. The tape watchdog's privilege-free health signal HAS NEVER EXISTED. `C:\kals\logs\run_all.pid` is not on disk.

`boot_all.ps1:191` decides run_all.ps1 is alive with
`(PidFileAlive "$kals\logs\run_all.pid") -or (Running '*run_all.ps1*')`.
`run_all.ps1:16` writes that pid file -- but that line was added in commit
`1bf5b1c` on **2026-09-17**, and the running instance was started at the
**09-15** boot. `os.path.exists` says the file is **absent**. So the branch that
boot_all's own header calls the most trusted ("needs no permission to read")
is dead, and the tape's watchdog is currently held up **entirely by the
command-line match** -- the exact mechanism the elevation bug destroys.

`grep -c "REFUSING to start collectors" results/boot_all.log` = **0**. That is
not evidence the guard works; it is evidence the command-line read on that one
`powershell.exe` still succeeds. **The day it does not, boot_all will conclude
run_all is down, see `$blind > 0`, refuse to start it, and write one line to a
log nothing reads.** That is the total-tape-loss path, and it is one process
away, today.

### N2. `run_all.ps1` genuinely has no log, and the proof is that boot_all did not start the running instance.

`C:\kals\logs\run_all.console.log` -- the redirect `boot_all.ps1:200` supplies
-- **does not exist**. Neither does `C:\kals\logs\cdc_record.out` (boot_all's
redirect for the Crypto.com recorder). Every producer running right now was
started by hand, so none of boot_all's redirects exist and every `Write-Host`
`run_all.ps1` has emitted since 09-15 -- every `RESTART collector` line, every
disk line -- went to a closed handle. **There is no record of any recorder
restart, ever.** That is why 35 hours of lost tape have "cause not recorded"
against them, and it will still be true of the next one.

### N3. boot_all.ps1 cannot start the ledger refresher: a literal CRLF is inside the quoted path.

Bytes at `boot_all.ps1:360`:

```
Start-Process -FilePath $py -ArgumentList @("-u", "$repo\r\nesearch\pinledgerd.py") `
```

A PowerShell double-quoted string spans lines, so the argument is
`C:\kals-repo` + CRLF + `esearch\pinledgerd.py`. `pinledgerd.py` is the only
thing keeping `results/kalshi_ledger.json` -- every money number the app and the
phone show -- current. boot_all can never start it; the Start-Process error goes
to the scheduled task's discarded stderr; and `$started++` runs anyway, so the
log would say "started N process(es)". It is alive now only because a human
started it.

### N4. Nothing anywhere has a health check for the ledger refresher.

`grep pinledgerd research/pindesk.py research/pinphone.py` = **nothing**.
`health()` has rows for the bot, the watchdog, the phone, both recorders,
cdc, paper arms, race arms, disk, RAM -- and none for `pinledgerd`. It writes
`results/pinledgerd.heartbeat` and **no code reads it.** Its own docstring says
it exists because "a number that is merely STALE still reads as current"; the
same sentence is now true one level up, about itself.

### N5. Gemini is not a broken connection. Only one symbol was ever coded.

`crypto_feeds.py:216` is a single hard-coded URL
`wss://api.gemini.com/v1/marketdata/BTCUSD?...` and `:231` only ever calls
`upd("gemini", "BTC", ...)`. coinbase/kraken/bitstamp each subscribe to 8
symbols in one send. Measured on `20260923T03`: coinbase 8 distinct symbols,
kraken 8, bitstamp 8, gemini 1 (BTCUSD). **No guard could have caught this** --
there is nothing failing. It is a missing feature that has been read as a
degraded feed.

### N6. `index_replica`'s `n_ex` is 1 to 4, not 3, and DOGE is one of the worst -- which matters because the design proposes it as the fallback.

A_inventory says "every index_replica row we compute is a 3-exchange mid
(n_ex: 3)". Measured, 3,001 rows of `20260923T03`:

| asset | n_ex 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| BTC | 0 | 0 | 30 | 2,970 |
| DOGE | 24 | 676 | 2,300 | 0 |
| ADA | 147 | 1,471 | 1,382 | 0 |
| BCH | 96 | 1,792 | 1,112 | 0 |
| ETH | 0 | 410 | 2,590 | 0 |

`index_replica` drops any exchange whose top-of-book is older than 10 s
(`crypto_feeds.py:251`) **silently**, and writes the row anyway if one asset
survived (`:266 if len(out) > 2`). Across tonight's outage hours:

| hour | replica distinct seconds | DOGE n_ex=1 | =2 | =3 | absent | Kalshi index lines |
|---|---|---|---|---|---|---|
| 20260923T00 | 3,600 / 3,600 | 803 | 1,627 | 1,014 | 156 | 737 |
| 20260923T01 | 3,600 / 3,600 | 538 | 1,577 | 1,434 | 51 | **NO FILE** |
| 20260923T02 | 3,600 / 3,600 | 173 | 1,544 | 1,883 | 0 | 21,769 |
| 20260923T03 | 3,600 / 3,600 | 34 | 770 | 2,796 | 0 | 39,589 |

So the fallback is **complete in second count** (3,600/3,600 in the hour Kalshi
has no file at all) and **variable in quality**: in that hour DOGE was a
one-exchange mid for 538 seconds and absent for 51. The design's item 6 is
right that the fallback exists; it is **wrong to treat it as one thing**. Every
fallback row must carry `n_ex` and the venue list, and every stage must print
the distribution, not a count.

### N7. `replay.load_index` cannot report a missing day, by construction.

`research/replay.py:125-158` reads `cfbenchmarks_value` only -- no fallback --
and its coverage line is
`cov = 100 * len(v) / max(span*3600, 1)` where `span = (max(v) - min(v))`.
**The denominator is the span of what loaded.** Lose the first day entirely and
the span shrinks with it; coverage stays ~100%. The `<-- GAPPY` marker is a
`print` under `if verbose`, read by no stage and fatal to nothing. This is K3
written into the loader every analysis depends on.

### N8. Zero of the 2026-09-12 three-part collector fix shipped, not one.

`git log -1 -- kalshi_collector.py` = `ceb5bda`, **2026-09-06**. The
SIGTERM/gzip-close block (`main()`, lines 372-400) that A_inventory credits as
"part 2 shipped" is present in that 09-06 commit -- it **predates** the 09-12
write-up. The collector has not been touched in 17 days. Part 1
(resubscribe on a seq gap) and part 3 (log every resubscribe) were never
applied, and part 1 is what lost tonight's DOGE order book.

### N9. `restart_bot.ps1` DIES at line 59 when Start-Transcript fails -- it does not merely fail to record.

This is the one that matters most for the money; it has its own section (§3).
`$ErrorActionPreference = "Stop"` is set at line 48; `Start-Transcript -Path
$transcript -Force` is line 59. All 6 failures in `watch_bot.log` are followed
by **zero** `restart_bot:` stdout lines -- no "argument list ok", no "pinflat",
no "stopping live pinrun". The script never validated, never killed, never
started. **6 of 27 watchdog restarts (22%) did nothing at all.**

---

## 1. THE CLASSES, ONE AT A TIME

Each: (1) the guard that should have caught it and exactly why it could not;
(2) the single mechanism that ends the class; (3) what is left after tonight.

---

### K1 -- "ALIVE" IS TREATED AS "WORKING"

**1. The guard, and why it could not.** There are four, and each fails on a
different flavour of the same mistake:

| guard | signal it reads | why it cannot see function |
|---|---|---|
| `run_all.ps1:31` | `-not $jobs[$n] -or $jobs[$n].HasExited` | process existence, full stop. A collector deaf for 4 h 47 min never exits, so this never fires. |
| `boot_all.ps1:181-186` `Running`/`RunningPy` | `Win32_Process.CommandLine -like` | a string in the process table. Returns `$null` for a process the caller cannot open -- **and a limited-token caller cannot open a high-integrity one** (KalsBoot is `RunLevel Limited`, `boot_all.ps1:58`). |
| `boot_all.ps1:238-250` watch_bot | heartbeat file age > 300 s -> kill | this one is CORRECT, and it is the template. It reads a thing the process produces, not the process. |
| `watch_bot.ps1:186` bot staleness | newest write to `pinrun-live-*.jsonl` or `.out` older than 25 min | also correct in shape, but it is `alive vs silent`, not `alive vs useful`: the 09-21/22 outage wrote a log line every few seconds, all of them failures. `blind_of` was added later to cover exactly that. |

The pattern: **liveness is cheap and function is specific, so every check took
the cheap one.** Where function was checked, it was bolted onto one consumer
after one incident -- `blind_of` for the bot, `recorder_ok` freshness for the
recorders, the heartbeat for watch_bot -- and nothing generalised.

The current instance is the sharpest: boot_all has logged **"all up; nothing to
do" 874 times**, including 130 consecutive times over 21 h while refusing to do
anything, because `$started -eq 0` (line 420) means "I started nothing" and it
is printed as "everything is fine". A refusal increments no counter and changes
no message.

**2. The single mechanism.** Invert the direction: **every producer writes its
own health, per stream, and the supervisor only reads files.** Concretely,
`results/health/<producer>.json` every 30 s, containing per stream: records in
the last 60 s, the rate the producer EXPECTS, the last record's exchange time
AND receive time, seq gaps since the last write. Then no consumer ever asks the
OS about a process it does not understand, and the supervisor needs no
privilege: pid files + `Get-Process -Id` + file mtimes, never
`Win32_Process.CommandLine`. That single change removes the elevation class
outright and makes "alive" unquotable -- there is no field for it.

**3. What is left after tonight.**
- *Needs a human, named:* clearing the blind condition without a reboot (the 31
  high-integrity python processes were started from elevated sessions and only
  their termination or a reboot clears it); KalsBoot "run whether logged on" or
  auto-logon (his Windows password).
- *Still only process existence:* `run_all.ps1`'s own two children (`HasExited`);
  `pinledgerd` (a `RunningPy` match in boot_all and nothing else); every paper
  arm (`pindesk` counts a log written in the last 900 s -- which is liveness of
  a file, and nothing alerts); `cdc_record` (file mtimes only).
- *No alert:* boot_all refusing to act; a dead paper arm; a stale ledger.
- *No record of having failed:* `run_all.ps1` (N2).
- *Survivable-but-invisible:* the whole recovery layer being off for 21 h, while
  the app and the phone are green because they check different things.

---

### K2 -- A PARTIAL FAILURE READS AS TOTAL HEALTH

**1. The guard, and why it could not.** This is the class where **last night's
new fix is itself an instance of the bug.**

`DeafVerdict` (`boot_all.ps1:89-121`) loops over the channel directories and
takes the **newest** mtime of any of them:

```
foreach ($d in Get-ChildItem -Path $tapeRoot -Directory) {
    foreach ($f in @($cur, $prev)) { ... if ($m -gt $newest) { $newest = $m } }
}
if ($tapeMin -lt $silentMin) { return @{ state = "ok" ... } }
```

`kalshi_data` has 12 channel directories. **If `ticker` is writing, the verdict
is "ok" even if `cfbenchmarks_value` -- the settlement index, the one channel
everything depends on -- is dead.** `pindesk.recorder_ok:1006-1029` does exactly
the same thing (`newest = max(newest, m)` across directories), and
`pinphone.alerts_tick:476-478` alerts off `h["kalshi_ok"]`, which is that same
per-directory boolean. `restart_bot.ps1`'s own recorder check is bytes-per-hour
and channel count; the transcript from 20:33 ET reads
`last full hour 29611319 bytes across 10 channels; 3 open now` and then
**"both recorders are writing"** -- 3 of 10 channels open, reported as healthy.

So: one channel of five (or twelve), one exchange of four, one symbol of eight,
one coin of twelve. Every monitor in the stack is per-PROCESS or
per-DIRECTORY. **Not one is per-STREAM.** Evidence that this is not theoretical:
the Thursday 07-08Z maintenance killed the book four times while the index was
fine and was never identified as anything; 551 of 705 measured tape gaps have
that exact shape; tonight DOGE got zero `orderbook_delta` for its last 13
minutes while the feed was nominally back.

**2. The single mechanism.** **Define the stream as the unit of health, and name
every stream in a checked-in manifest with its expected rate.** For Kalshi that
is `(producer, channel)`; for the exchange feeds `(producer, exchange, symbol)`,
so `gemini/DOGE` is a stream that is DEAD rather than an absence nobody can
name. A stream that is not in the manifest is itself an alert. Nothing may
aggregate streams with `max()` before deciding.

**3. What is left after tonight.**
- *Needs a human:* nothing -- this one is entirely ours.
- *Still only per-directory:* `boot_all.DeafVerdict`, `pindesk.recorder_ok`,
  `pinphone`'s recorder alert, `restart_bot`'s pre-flight. **All four.**
- *No alert:* any single channel dying; any single exchange dying; any single
  symbol; `n_ex` falling.
- *No record of having failed:* the Thursday window (four occurrences, no
  calendar entry, next one **Thursday 2026-09-24 07Z**).
- *Survivable-but-invisible:* gemini at 1 of 8 for the entire history, so every
  non-BTC "consolidated" mid we have ever computed is a 3-venue mid at best and
  a 1-venue mid for hundreds of seconds an hour (N6) -- and no tool records
  which.

---

### K3 -- NO NAMED BASELINE, SO THE DEGRADED LEVEL BECOMES THE NORM

**1. The guard, and why it could not.** Every size or rate check in the stack
compares against the data's own trailing statistics, so a fault that has been
running long enough is definitionally normal:

- `replay.load_index` divides by the span of what it loaded (N7) -- a missing
  day cannot lower coverage below 100%.
- `feed_data/gemini` is 144 hours "short" against its own median, but the median
  IS the one-symbol level.
- A size-based gap scan cannot see the 2026-09-01/02 and 09-02/03 double-write:
  those 13 hour files are 3.0-3.1 MB against a 1.55 MB normal, i.e. **ABOVE**
  the median, and unreadable from byte ~0.
- The same habit outside the recorders produced the three baseline errors: "the
  cheap pool halved" against the four busiest days on file; "$50-60/day of
  missed deals" on a flat-supply premise; "09-13 was a Saturday".

**2. The single mechanism.** **A baseline is a checked-in artefact, not a
computed one.** One file in the repo naming a good window per stream
(`cfbenchmarks_value` = 3,600 records/hour; `gemini` = 8 symbols;
`orderbook_delta` = N/hour at the 09-19..21 level) with the date the window was
chosen and who chose it. Every check compares to that number, prints both
numbers, and a change to the file is a version entry. Corollary, and it is the
part that bites: **a completeness measurement must divide by the REQUESTED
window, never by the returned data.**

**3. What is left after tonight.**
- *Needs a human:* choosing the good windows (one sitting; the nine 100% index
  days -- 08-31, 09-05, 09-10..13, 09-19..21 -- are the obvious candidates).
- *No alert:* every rate in the system.
- *No record:* the 14 h 23 min of corrupt index has never appeared in any
  report, HANDOFF entry or results file.
- *Survivable-but-invisible:* **every "n closes" number in the project is
  quoted against an unknown denominator** -- 7.48% of the settlement index does
  not exist and no stage says so. 22 hour files sit on disk at full size and are
  unreadable by anything; 16 of them are dead. 97 HOLE hours must be excluded
  from any trade-channel count and nothing excludes them.

---

### K4 -- THE RECORD OF A FAILURE IS DESTROYED BY THE FAILURE

**1. The guard, and why it could not.** There is no guard; there are four
mechanisms that actively destroy evidence, and three of them were built as
logging.

| destroyer | code | what is lost |
|---|---|---|
| no log at all | `run_all.ps1` uses `Write-Host` inside a `-WindowStyle Hidden` process; `logs\run_all.console.log` **does not exist** (N2) | every recorder restart in the tape's history |
| fixed filename + overwrite redirect | `run_all.ps1:19-22` `-RedirectStandardOutput "$Dir\logs\$name.out.log"` | each recorder restart truncates `collector.out.log`; the current file is 1.32 MB and begins at the last restart |
| fixed filename + `-Force` | `restart_bot.ps1:57-59` writes one `restart_bot.last.log`, overwritten every run | at most ONE restart's record exists at a time; the 6 failures cannot be confirmed from disk at all |
| two names for one log | `boot_all.ps1:269` redirects cdc to `logs\cdc_record.out`; the program's visible log is `logs\cdc_record.out.log` | `cdc_record.out` is **absent**, `cdc_record.out.log` is **6.5 days stale** while the recorder writes data every second |

And the one that turns a logging bug into a money bug: the transcript is not
just overwritten, **its failure aborts the script** (N9, §3).

The `Start-Transcript` failure cause is now measured. `restart_bot.last.log`
from 2026-09-22 20:33 ET is COMPLETE and its header reads
`Host Application: ... -File C:/kals-repo/restart_bot.ps1` -- **forward
slashes**. `watch_bot.ps1:144` passes `"$repo\restart_bot.ps1"` -- backslashes.
So two `restart_bot.ps1` instances ran 18 s apart, and the surviving record is
the OTHER one's. `-Force` does not make a transcript exclusive; a second
Start-Transcript against a path a live PowerShell already holds fails
`CannotStartTranscription`. **The record fails precisely when two restarts
overlap, and two restarts overlap precisely when the bot went down and both the
watchdog and the operator/app reacted.** The record is destroyed by the event it
was built to explain -- not by coincidence, by construction.

**2. The single mechanism.** **Nothing truncates, nothing overwrites, nothing
shares a name.** Dated append-only files per producer per run
(`logs/<producer>-YYYYMMDDTHHMMSSZ.log`), and a logging call that fails must
never be able to stop the work. For `restart_bot.ps1` that means replacing
`Start-Transcript` with `Add-Content` to a dated file -- and, in the meantime,
the one-line change that matters: **the Start-Transcript call must be inside
`try { } catch { }`** so a failed record cannot abort a restart.

**3. What is left after tonight.**
- *Needs a human:* nothing.
- *No record of having failed:* `run_all.ps1` entirely; every recorder restart;
  every collector resubscribe (part 3 of the 09-12 fix, never applied);
  `cdc_record`'s last 6.5 days; 5 of the 6 aborted restarts; boot_all's 130
  refusals are recorded but in a log nothing reads and nothing alerts on.
- *Survivable-but-invisible:* the bot's own logs miss whatever it held when a
  run died ($72.34 of overstated lifetime profit, and `v-nocap` was decided on
  it). `pinday` now reads the ledger, but the **day-loss cap is still seeded
  from the logs**, so a crash-orphaned loss still does not count against it.

---

### K5 -- TWO CLOCKS, AND THE WRONG ONE GETS USED

**1. The guard, and why it could not.** There is no guard and there never could
be one as the data is shaped: `kalshi_collector.handle:326` stamps
`m["_rx_ms"] = int(time.time()*1000)` on **every** message, so every record
carries a receive time whether or not it carries an exchange time. A tool that
reaches for a timestamp finds `_rx_ms` first and it is never missing. The
exchange's own `ts_ms` is present and optional.

Measured consequences: `hedgetune.py` priced insurance on `_rx_ms` and was
$26.25 too cheap over 698 contracts ($2.34 off when re-keyed on `ts_ms`) -- and
the live hedge trigger was moved 0.60 -> 0.25 on that number, past
`PREREG_hedge`'s "not below 0.30" bar. `racebook.py` times ticker lines by
`_rx_ms`, and collector receive lag on CRYPTOLEAD ticker is median 0.4-0.5 s,
p90 1.5-2.3 s, with 5-11% of lines past 2 s at tau 30-60 -- bursts, i.e.
exactly when a pickoff happens. `pinsim` times deltas by `ts_ms` (right) and
snapshots by `_rx_ms` (wrong). `replay.py` prefers the message time, which is
why the pin replay is clean and nobody looked further.

The recorder is itself the worst offender: `_rx_ms - ts_ms` on
`orderbook_delta` has a median of 28-38 ms and a **p90 of 2.7-4.7 s in every
hour checked**, and was 1.9-4.4 s in the second before 4 of 8 collapse fills.

The same class produces the unreadable alert: `DeafVerdict:102` sets
`$tapeMin = 9999` when no hour file exists, and the phone printed **"tape
silent 9,999 min"** at 22:20 ET tonight -- a sentinel in a field the operator
reads as a number, fired in the worst case (no file at all).

**2. The single mechanism.** **Name the clock in the field name and make the
wrong one impossible to reach by accident.** Every record carries `t_exch_ms`
and `t_rx_ms`; a loader exposes `t` = exchange time and requires an explicit
`clock="rx"` to get the other; every tool prints which clock it used in its
header, and a self-test asserts the two differ in a planted world. Same rule for
alerts: a sentinel is `null` and renders as "no file this hour", never 9,999.

**3. What is left after tonight.**
- *Needs a human:* deciding whether `v-hedge25` (0.25) stands, given the tool
  that justified it was $26.25 wrong and its pre-registered bar was bypassed;
  and whether the coin-race z3 arm may ever graduate to real money while its
  edge estimate is biased in its own favour by an unmeasured amount.
- *Uncorrected:* `pinsim` snapshots; every tape tool except `replay.py` and
  `pinfeed`; `hedgetune` has not been re-run since the diagnosis.
- *No alert / no record:* nothing measures the collector's receive lag
  continuously, though it is the single field that would make every downstream
  estimate auditable.
- *Survivable-but-invisible:* the bias always favours the strategy, so it shows
  up as an edge, never as a fault.

---

### K6 -- A GUARD THAT CANNOT ACT, OR ACTS ON THE WRONG THING

**1. The guard, and why it could not.** Every case here is a guard whose
ACTION was never written down beside its CHECK:

- `boot_all.ps1:193-194, 216-217, 264-265, 278-279, 295-296`: five refusals
  keyed on `$blind -gt 0`. The whole recovery layer's action is "do nothing and
  log", and 130 refusals in 21 h prove it. **The safety check disabled the
  safety system.**
- `boot_all.ps1:214`: `DEAF but retrying ... Not killing it` -- correct, and its
  only action is a log line. Detection with no recovery and no fallback.
- `run_all.ps1:44`: `if ($free -lt 5) { Write-Host "LOW DISK - stopping"; break }`
  -- the watchdog **exits its loop**, so both recorders stop being restarted.
  Identical in the repo and the deployed copy; CLAUDE.md's 6 GB guard exists
  only as prose in a report.
- `pinrun` drawdown brake: terminal, and `watch_bot` restarts unconditionally
  after a 15-min cooldown, so it re-halts on its first bank read. Four times on
  09-20 until a human edited `pinrun-hwm.json`. It trips again at a bank of
  $767.12.
- `risk_abort()` calls `day_loss()` with no `a.live` check: 24 paper arms read
  the live bot's day-loss file, so a -$200 live day halts the measurement fleet
  on the day the comparison matters. (Fixed in `v-safety1`'s scope per
  CURRENT_STATE; the coupling in `boot_all`'s hard-coded 16-arm pre-sync list is
  not.)
- `restart_bot.ps1` used to kill before validating (fixed). It now validates
  first -- and then dies at line 59 before either (N9).

**2. The single mechanism.** **Three states per stream, and the ACTION for each
is written and self-tested before the check ships.** `OK` /
`DEGRADED` (below expected, above zero) / `DEAD` (zero). `DEAD` + retries in the
producer's own log -> alert, do NOT restart, and **turn the declared fallback
ON**. `DEAD` with no retry -> restart. `DEGRADED` -> alert carrying the number
and the checked-in baseline. And the rule that ends the 21-hour case: **a guard
may refuse to ACT, never refuse to REPORT** -- a refusal is an alert with the
same weight as the fault it is refusing to fix, and it may never be summarised
as "nothing to do".

**3. What is left after tonight.**
- *Needs a human, named:* the drawdown brake -- should it see all bots, and
  should a terminal halt auto-clear or cut size instead (the 09-20 loop is
  armed); the 5 GB hard stop in `run_all.ps1` (a code change to an untouchable
  file, so it needs his word); and the elevated-process cleanup that clears the
  blind condition.
- *Still detection-only:* the DEAF check; `blind_of`; the recorder-SILENT
  alert; boot_all's every refusal.
- *No alert:* disk, anywhere. `run_all` prints it to a log that does not exist;
  `pindesk` shows a number on a tab; nothing pages.
- *Survivable-but-invisible:* boot_all's hard-coded 16 pre-sync arms
  (`--hedge-price 0.60`, `--bank-brake 4.08`) repopulate the fleet with the
  configurations CURRENT_STATE says never to trust, whenever no paper arm is
  running -- silently, and the lab would score them.

---

### K7 -- THE FIX WAS WRITTEN UP, AGREED, AND NOT APPLIED

**1. The guard, and why it could not.** `research/versioncheck.py` is the only
automated discipline, and `grep` shows its entire scope is one constant:
`LAUNCHER = os.path.join(REPO, "restart_bot.ps1")`. It compares the money bot's
**flags** against `VERSIONS.md`. It cannot see a proposal that was never
deployed, and it cannot see any of the seven infrastructure files at all.

Measured: the collector has not changed in 17 days (N8), so zero of the 09-12
three-part fix shipped -- part 1 (resubscribe on seq gap) is what lost tonight's
DOGE book eleven days later. `pinpickoff --rebuild` has been outstanding since
09-17 and its data still stops at 09-12, immediately before the drop the
operator was asking about. The "collector alive but deaf" check was proposed
09-21, built 09-22, and disabled by the elevation bug within hours.

**2. The single mechanism.** **An agreed fix is a dated open item with an owner
in one checked-in file, and the checker that reads that file fails a run while
an item is open past its date.** Same shape as `versioncheck.py`, pointed at
proposals instead of flags -- which is the only reason the flag discipline
survived and this one did not.

**3. What is left after tonight.**
- *Needs a human:* the pickoff rebuild (foreground, needs a RAM window).
- *Open and unshipped:* collector resubscribe-on-seq-gap; resubscribe ordered by
  time-to-close; resubscribe logging; the `KNOWN_OUTAGES` calendar; the
  `pinledgerd` path (N3); `pindesk`'s `--live` substring test (below).
- *No record:* there is no file that lists an agreed-but-unapplied fix, so the
  count above is what I found by reading, not by looking it up.

---

### K8 -- TWO WRITERS ON ONE FILE

**1. The guard, and why it could not.** The write path was hardened and the
detection path was not. `kalshi_collector.py:372-400` installs SIGTERM handlers
on Windows so `Writer.close()` runs and the gzip gets its trailer -- that stops
MORE corruption being written. Nothing prevents two processes opening the same
hour file, and nothing detects that it happened: the resulting files are 2x
normal size, i.e. above any median (K3), and unreadable from byte ~0, so even
`gzsalvage.py` recovers 1-2 records.

boot_all's response to the FEAR of a duplicate is `$blind -gt 0` -> refuse
everything (its own comment: "a duplicate collector corrupts the tape"). That is
how a two-writer safety check became a 21-hour outage of the boot layer -- **the
guard for K8 caused the current instance of K6.**

**2. The single mechanism.** **A single-writer lease per output, taken by the
producer.** The recorder opens `<out>/.writer.lock`, writes its pid and
refreshes it; a second instance that finds a live lease exits with a message.
Then no supervisor ever has to reason about duplicates, and the refusal that
disabled the boot layer can be deleted. The same lease is what
`restart_bot.ps1` needs (two instances ran 18 s apart tonight with no lock, no
mutex -- `grep -n "lock\|Mutex" restart_bot.ps1` finds none in its logic).

**3. What is left after tonight.**
- *Needs a human:* nothing.
- *No alert / no record:* nothing detects a double-write, before or after. The
  09-01/02 and 09-02/03 corruptions have never been reported anywhere.
- *Survivable-but-invisible:* 16 hour files sit on disk at full size and are
  dead. Any stage that read those hours saw nothing and exited 0.

---

### K9 -- A MEASUREMENT TOOL SELF-TESTS ITS LOGIC AND NEVER ITS INPUT

**1. The guard, and why it could not.** The self-test gate is the best thing in
this repo and it is aimed one inch to the left of the problem. A `--selftest`
plants an answer in a synthetic world; it proves the estimator. It says nothing
about whether the real input arrived. The extreme case: 68,976,084 of
68,976,084 deltas unparsed, 7 stages loading zero quotes, every self-test
green, every stage exit 0.

That class was fixed *at the level of the class* -- schema discovery plus
`EMPTY_MARKERS` -- and it is the only one in this list that was. But the same
shape survives in three places:

- **No self-test executes `trade_loop`.** Every loop-level protection (A69, A71,
  A74) is an `index`/`rindex` source search. Three in-loop crashes of newly
  shipped code in 14 days, all at `:29:30`/`:59:30` -- tau = 30 s, the first
  second the entry path runs its rare branches -- one while holding, -$66.34.
- **A source-text self-test finds its own copy of the string** it searches for.
  Four times in one session, once silently for days.
- **A self-test asserting a RUNNING value refuses to start the bot** -- six
  times, including a 6-minute live outage when `--price-ceiling` was added,
  because `pinrun` self-tests at startup with flags applied.
- `crypto_feeds.selftest()` proves the Bitstamp depth trim preserves the touch.
  It is a good test. It has nothing to say about gemini being 1 of 8, because
  arrival is not its subject.

**2. The single mechanism.** **Every stream check gets a NULL in its self-test,
and one self-test RUNS the supervisor against a fake health tree.** Which is to
say: the deliverable is a test that drives the thing, not one that reads it. For
the loop specifically, a fake book + fake index + fake `take`, one open
position, a gate monkeypatched to raise -> the loop must survive N iterations
and the hedge pass must have written a hedge. For the health layer, a planted
tree with one DEAD stream, one DEGRADED, and a NULL tree with nothing wrong.

**3. What is left after tonight.**
- *Needs a human:* nothing; the loop-executing test is in the K1 build and not
  yet shipped.
- *No self-test at all:* `run_all.ps1` -- 46 lines the entire project depends on.
  `boot_all.ps1` has `-DeafTest` (7 cases, verified 7/7 tonight) and nothing
  else; the blind-refusal logic that has been off for 21 h has no test and no
  NULL.
- *Survivable-but-invisible:* an estimator that never saw its input is
  indistinguishable from one that saw a healthy input, and `load_index` cannot
  tell you which (N7).

---

### K10 -- REBUILDS ARE BATCH JOBS ON A BOX THAT IS ~85% COMMITTED

**1. The guard, and why it could not.** There is none. CLAUDE.md's resource
protocol is **disk only**; the RAM rule is prose in a brief ("keep every python
process under ~500 MB") with nothing enforcing it. At least five OOM kills:
`kalshi_fulltape --markets 1200` at market 600; `pinsim` after 4 of 72 hours at
3.3 GB; `pinpickoff --rebuild` twice at ~1.6 GB free with 22 python processes;
the arm/grid rebuild at 50 of 130 hours. **The collectors survived each only
because the OS chose the bigger process** -- which is luck, and the tape is the
one thing that cannot be recreated.

**2. The single mechanism.** **A pre-flight RAM budget that refuses to start,
and a producer that cannot be the victim.** One helper every analysis entry
point calls: measure free RAM, refuse above a declared ceiling, and set the
recorders' process priority/working-set so the OS never picks them. Streaming,
not loading, is the other half -- `pinsettle.py` replacing `kalshi_fulltape`
(a few MB merge instead of the whole trade tape) is the worked example.

**3. What is left after tonight.**
- *Needs a human:* `pinpickoff --rebuild` in a quiet window. **Its data still
  stops at 09-12**, immediately before the drop that started this whole
  investigation.
- *No guard:* RAM, anywhere in code.
- *No record:* an OOM kill leaves no trace in our logs; it is found by the
  missing output.

---

### K11 -- THE INFRASTRUCTURE LAYER HAS NO VERSION LOG AND NO OWNER

**1. The guard, and why it could not.** `versioncheck.py` reads exactly one file
(K7). `VERSIONS.md` has ~64 entries and **one** of them is infrastructure:
`v-selfheal` (2026-09-17 04:22Z), which shipped `watch_bot.ps1` + `boot_all.ps1`
+ `pindesk`. Its revert block is

```
git checkout 879f5b4 -- watch_bot.ps1 restart_bot.ps1
```

-- **`boot_all.ps1` is not in it.** The file that is broken right now has no
revert line anywhere in the log. And tonight's three infra fixes have no entry at
all: `grep -i "blind_of\|deaf\|stuck-recorder\|RECORDER SILENT" results/VERSIONS.md`
returns **nothing**.

The deeper reason is ownership. The recorders are untouchable by hard rule 2,
which protects the data and, as written, also protects their bugs: gemini's one
symbol has been there since 08-25, and the collector's last change was 09-06.

**2. The single mechanism.** **`results/VERSIONS_INFRA.md` with the same rules,
and `versioncheck.py` extended to read all seven infra files** -- `run_all.ps1`,
`boot_all.ps1`, `watch_bot.ps1`, `restart_bot.ps1`, `kalshi_collector.py`,
`crypto_feeds.py`, `pindesk.py`/`pinphone.py` -- failing a run when a deployed
file's hash differs from the one the newest entry names. That also subsumes
`deploycheck.py`'s repo-vs-`C:\kals` drift check (both collector copies are
byte-identical right now, verified).

**3. What is left after tonight.**
- *Needs a human:* an explicit narrowing of hard rule 2 to "never modify the
  DATA; the recorder PROGRAM may be changed under a version entry" -- otherwise
  gemini and the seq-gap resubscribe cannot be fixed at all.
- *No record:* every infrastructure change since 09-17.
- *No revert path:* all seven files.

---

## 2. THE ONE THAT WORRIES ME MOST FOR THE MONEY

**Not the elevation bug, and not the disk. It is that a failed `Start-Transcript`
kills `restart_bot.ps1` before it starts the money bot -- and the watchdog then
reports success.**

Mechanism, in code:

- `restart_bot.ps1:48` `$ErrorActionPreference = "Stop"`.
- `restart_bot.ps1:58-59` `try { Stop-Transcript } catch {}` then
  `Start-Transcript -Path $transcript -Force | Out-Null` -- **not** inside a
  `try`.
- One fixed path, `results\restart_bot.last.log`. `-Force` overwrites; it does
  not acquire. A second Start-Transcript against a path a live PowerShell still
  holds fails `CannotStartTranscription`, which under `Stop` is terminating.
- `watch_bot.ps1:153-158` logs the child's stdout and stderr, then `:159-161`
  sleeps 15 s, reads `LiveBotPid`, and says **"back up, pid N"** if anything is
  there -- it never checks that its own child did the starting.

Evidence, all six occurrences in `results/watch_bot.log`, and in every one of
them there is **not a single `restart_bot:` stdout line** (compare 09-20 00:16,
which has three):

| when (ET) | watch_bot's next line |
|---|---|
| 09-17 15:41:57 | back up, pid 532412 (~15 s) |
| 09-18 13:04:23 | **STILL DOWN after restart_bot.ps1 -- will retry**; back only at 13:05:40 |
| 09-18 15:07:28 | **STILL DOWN after restart_bot.ps1 -- will retry**; back only at 15:08:47 |
| 09-19 01:08:13 | back up, pid 1107380 (~16 s) |
| 09-22 01:30:23 | back up, pid 1985112 (~15 s) |
| 09-22 20:33:22 | back up, pid 2230760 (~15 s) |

**6 of 27 watchdog restarts (22%) did nothing at all.** Four were rescued
because something else was restarting at the same second -- which is also what
caused the collision. Two (09-18) left the bot down until the next cycle. And
the surviving 20:33 transcript proves the rescuer was a different caller (its
header says `-File C:/kals-repo/restart_bot.ps1`, forward slashes; watch_bot
passes backslashes), i.e. **two `restart_bot.ps1` instances ran 18 s apart on
the live money bot with no lock and no mutex.**

**Failure scenario, concrete.** The bot crashes in the entry scan at
`:59:30` -- tau = 30 s, which is where all three in-loop crashes have landed.
`watch_bot` notices within 30 s and calls `restart_bot.ps1`. The transcript path
is held by a PowerShell that is still open -- the desktop app's own Start, a
Claude session's shell, or the previous restart's hung child -- so
`Start-Transcript` fails and the script dies at line 59. Because nobody else is
restarting this time, `LiveBotPid` returns nothing, `watch_bot` logs "STILL
DOWN", and retries: 4 quick attempts inside 15 min, then **one every 3 minutes
forever, each dying at line 59.** The desktop app shows the bot stopped, the
phone sends one STATE CHANGED, and nothing else ever fires. If the holder is a
long-lived shell, this is unbounded. Overnight at the post-fix rate
(+$1.52/close, 4 closes an hour) an 8-hour hole is **~$49 of foregone edge**,
and the tail case is the operator waking to a bot that has been down since the
crash. Worse variant: the crash happened **while holding**, `pinflat` would
have refused the restart anyway -- but nothing hedges that close, and the
measured cost of one unhedged collapse on this size is **-$66 to -$108**.

Why it is worse than the elevation bug: the elevation bug costs data and a
recovery layer, and the tape is currently being written. This one costs the
money bot's only automatic recovery, silently, with a log line that says the
opposite, and it has already fired six times.

**The fix is one line of scope** -- wrap `Start-Transcript` in
`try { } catch { }` so a failed record cannot abort a restart -- plus two more:
`watch_bot` must verify its own child produced the new pid (compare the pid
before and after, and require the child to have written a line), and the
transcript must become a dated append-only file with a single-writer lease. None
of the three can block a hedge: they run only when the bot is already down.

---

## 3. THE CLASSES RANKED BY EXPECTED COST

Cost is dollars where a dollar is measured, and irreplaceable data where it is
not. Ranked on expected cost over the next 30 days, i.e. probability x size.

| # | class | what it costs if it fires again | the ONE mechanism that ends it |
|---|---|---|---|
| 1 | **Disk (K6's worst instance)** | the whole 68 GB tape, unreproducible. `run_all.ps1:44` EXITS its loop at 5 GB free; 23.5 GiB now at 3.93 GB/day = ~4 days; and with boot_all blind nothing would restart it | **An archiving producer with its own health stream and a 10 GB alert**, plus the 5 GB `break` becoming a size-shedding pause, not an exit. Certain unless acted on -- rank 1 on probability, not severity |
| 2 | **K1 alive-vs-working (current instance: boot_all blind 21 h, and `run_all.pid` has never existed)** | the entire boot/recovery layer, including last night's stuck-recorder kill; if `run_all.ps1` dies, the tape ends with one unread log line | **Producers declare health per stream to `results/health/*.json`; the supervisor reads pid files + `Get-Process -Id` + mtimes and NEVER `Win32_Process.CommandLine`** |
| 3 | **K4 the record destroyed by the failure (money instance: the aborted restart)** | the money bot's only automatic recovery: 6 of 27 restarts did nothing; 2 left it down; tail is a whole night (~$49 foregone) or an unhedged held close (-$66 to -$108) | **Nothing truncates or overwrites; dated append-only logs; and a logging call can never abort the work (`try`/`catch` round `Start-Transcript`)** |
| 4 | **K2 partial failure reads as total health** | the settlement index can die alone while every monitor says WRITING -- `DeafVerdict`, `recorder_ok`, the phone alert and `restart_bot`'s pre-flight all take `max(mtime)` across channels. Tonight's DOGE close has no book for its last 13 min | **The stream is the unit of health: a checked-in manifest of `(producer, channel)` and `(producer, exchange, symbol)` with expected rates; no `max()` before a verdict** |
| 5 | **K5 two clocks** | a live hedge threshold already set on a $26.25 error past its own pre-registered bar; the coin-race edge biased in its own favour by an unmeasured amount, with a real-money test pending on it | **Name the clock in the field (`t_exch_ms` / `t_rx_ms`); the default loader returns exchange time and receive time needs an explicit opt-in; every tool prints which it used** |
| 6 | **K6 a guard that cannot act** | -$66.34 realised and 3 crashes; the drawdown brake re-arms at a bank of $767.12 and will loop against watch_bot again; 130 refusals logged as "nothing to do" | **Three states per stream with the ACTION written and self-tested before the check ships; and a guard may refuse to act but never to report** |
| 7 | **K9 self-test the logic, never the input** | the next in-loop crash at tau = 30 s while holding; every loop-level protection is still a text search | **Every stream check gets a NULL, and one self-test RUNS the supervisor against a planted health tree -- tests that drive, not read** |
| 8 | **K7 agreed and not applied** | it already cost tonight's DOGE order book, 11 days after the fix was written; the pickoff tracker is still 11 days stale | **Open items are dated, owned and in one checked-in file that a checker fails a run on** -- the `versioncheck.py` shape, pointed at proposals |
| 9 | **K3 no named baseline** | proposals built on a peak, and a completeness number that cannot fall: `load_index` divides by the span of what it loaded | **The baseline is a checked-in artefact with a date and a chooser, and a completeness measure divides by the REQUESTED window** |
| 10 | **K8 two writers on one file** | 14 h 23 min of settlement index already destroyed and never reported; its guard (`$blind` refusal) caused #2 | **A single-writer lease per output, taken by the producer -- which lets the refusal that disabled the boot layer be deleted** |
| 11 | **K10 no RAM guard** | the next measurement OOM; the collectors have survived five only because the OS chose the bigger process | **A pre-flight RAM budget every entry point calls, plus the recorders protected from ever being the victim** |
| 12 | **K11 no infra version log** | no dated record and no revert command for the seven files the machine runs on; `boot_all.ps1` is broken right now and has no revert line | **`VERSIONS_INFRA.md` and `versioncheck.py` extended to hash all seven deployed files** |

**The synthesis.** All twelve are one sentence: *a consumer decides, on its own,
whether a producer it does not understand is healthy, by looking at something
that is not the data.* Items 2, 4 and 6 of the table are that sentence inverted,
and they are the load-bearing part of the design. Items 1, 3 and 12 are the
ones that would make the next failure diagnosable and the next tape survivable.
Everything else follows.

Two cheap things outside the design that are worth doing in the same pass
because they are one line each: `boot_all.ps1:360`'s broken `pinledgerd` path
(N3), and `pindesk.py:1551`'s `if "--live" in cl` substring test, which puts the
`--paper-live` coin-race arm outside the operator's only control surface.
