# A_inventory -- every recorder / watchdog / measurement-tool failure this project has had

**STATUS: COMPLETE.** Read-only. Nothing started, stopped, killed or edited
outside this file and my scratchpad. Started 2026-09-23 ~04:0xZ (00:0x ET).
Resources at start: disk **21.7 GB** free, RAM **1.02 GB** free of 15.8,
collectors 105304 / 105352 alive, live bot 2230760 alive.

Sources measured directly, not quoted: `C:\kals\logs\collector.out.log` (20,019
lines, 2026-09-15 20:25Z to now), `feeds.out.log`, every hour file under
`kalshi_data\{cfbenchmarks_value,orderbook_delta,trade,ticker,orderbook_snapshot}`
and `feed_data\{index_replica,coinbase,kraken,bitstamp,gemini}` (666-669 files
each; byte sizes AND record/second counts through `research/gzsalvage.py`),
`results/{watch_bot.log,boot_all.log,pindesk.log}`, the live `start`/`end`
records, the Windows task table.

---

## 0. THE HEADLINE -- three things are broken RIGHT NOW

### N1. `boot_all.ps1` has been unable to see or supervise anything since 2026-09-22 02:20 ET (21+ hours), and its log says "all up; nothing to do" every 10 minutes.

**Root cause, measured, not guessed: an elevation mismatch.**

- The Windows task `KalsBoot` runs with `RunLevel : Limited` (read from the task
  table tonight) -- i.e. NOT elevated.
- A Claude session's shell IS elevated (`IsInRole(Administrator)` = True checked
  tonight). Every process such a session starts -- all 25 paper arms,
  `pinphone.py`, the live bot via `restart_bot.ps1`, the race arms -- therefore
  runs at **high integrity**.
- A limited-token caller cannot read `Win32_Process.CommandLine` of a
  high-integrity process; it comes back null. `boot_all.ps1:180` counts exactly
  that as `$blind`.
- Queried from the elevated session tonight: 42 python processes, **0** with a
  null command line. `boot_all` at the same moment: **31 blind**. Same machine,
  same second, different token.

**What that disables, by line number:**

| line | what it refuses while `$blind > 0` |
|---|---|
| 193-194 | **starting `run_all.ps1`, the collectors' watchdog**: "REFUSING to start collectors (a duplicate collector corrupts the tape). Check by hand." If `run_all.ps1` dies now, the tape stops and nothing restarts it. |
| 216-217 | **killing a STUCK recorder** -- last night's new fix, already disabled |
| 264-265 | starting `cdc_record.py` |
| 278-279 | starting `pinphone.py` |
| 295-296 | starting the paper arms |

So the whole boot/recovery layer is a no-op, and the only line the operator sees
is `all up; nothing to do`. It went blind at **09-22 02:20 ET with 6 blind, then
27 at 02:30 ET** -- the minutes the paper fleet was rebuilt from an elevated
session (`sync_arms.ps1`, 06:21Z). 130 refusals logged since.

Evidence: `results/boot_all.log` from line 759; `boot_all.ps1:180`;
`Get-ScheduledTask KalsBoot`.Principal.RunLevel = Limited.

### N2. Gemini has recorded 1 of its 8 symbols for the entire life of the log, and nothing has ever said so.

`feeds.out.log` prints `[stat] HH:MM top-of-book live: {...}` every 5 minutes.
Over **all 2,107 windows** (09-15 20:30Z to 09-23 04:00Z, 7.3 days):

| exchange | symbols live, every single window |
|---|---|
| coinbase | 8 of 8 |
| bitstamp | 8 of 8 |
| kraken | 8 of 8 |
| **gemini** | **1 of 8, in 2,107 of 2,107 windows** |

Not a dip -- a constant. `feed_data/gemini` is 144 hours "short" against its own
median, but the median IS the broken level, so a size check can never find this.
`index_replica` rows carry `n_ex: 3` (coinbase, bitstamp, kraken) for ETH:
**every constituent mid we compute is a 3-exchange mid and the fourth exchange
has been missing for at least 7.3 days, probably since 08-25.** No alert, no log
line, no stage that fails.

### N3. The Kalshi recorder takes ~36 minutes after a reconnect to record a full book, and the closes inside that window lose whole markets.

Tonight, from the tape itself (`orderbook_delta` hours 02Z and 03Z, records per
minute, DOGE separated):

| minute (Z) | all-market deltas | DOGE deltas |
|---|---|---|
| 02:31 | 6,542 | 667 |
| 02:32 .. 02:44 | 2,172 - 15,189 (~7% of normal) | **0 every minute** |
| 02:45 (the close) | 4 | **0** |
| 02:46 | 30,627 | 3,460 |
| 03:02 onward | 80,000 - 130,000 (normal) | 5,000 - 13,000 |

**The DOGE 22:45 ET close -- the one that lost money -- has ZERO order-book
records for its last 13 minutes, including all of tau <= 45 s.** Its Kalshi
index, by contrast, is intact: 843 of 900 seconds in the window and **60 of 60
seconds of the settlement window**. The reconnect at 02:21-02:26Z resubscribes
market by market (`[sub] +N markets`, 14-16 at a time), so markets nearest their
close are not prioritised and arrive last or not at all.

---

## 1. Tonight, corrected -- it was 2 h 21 min, not 45 min, and the tape is NOT gone

Measured second by second from `cfbenchmarks_value` (Kalshi's index) and
`feed_data/index_replica` (ours); seconds present per 15-minute close window:

| close (Z / ET) | Kalshi index, of 900 s | its last 60 s | our replica |
|---|---|---|---|
| 23:45Z / 19:45 | 753 | **0 of 60** | 900, 60 of 60 |
| 00:00Z / 20:00 | 665 | 60 | 900 |
| 00:15Z / 20:15 | 65 | **0 of 60** | 900, 60 of 60 |
| 00:30Z-02:15Z / 20:30-22:15 ET (**8 closes**) | **0** | **0** | **900 each, 60 of 60 each** |
| 02:30Z / 22:30 | 274 | 60 | 900 |
| 02:45Z / 22:45 (DOGE) | 843 | 60 | 900 |

- Kalshi index silence **00:05Z to 02:26Z = 2 h 21 min**; the 01Z hour file was
  never created at all. The brief's "45+ min" understates it ~3x.
- **8 closes lost their index completely; 2 more lost their settlement window.**
  At 12 series that is ~120 markets with no Kalshi index on disk.
- **`feed_data/index_replica` held 3,600 of 3,600 seconds in every hour of the
  outage, 01Z included.** The second recorder never missed a second. Nothing in
  the repo reads it as a fallback and no report has said the outage was
  survivable.

---

## 2. Tape completeness since collection began

Collection starts **2026-08-25 04Z** (there is no earlier file, so "since
08-24" cannot be answered -- nothing was recorded then). Span to 2026-09-23 03Z
= **696 hours**.

`cfbenchmarks_value`, the channel everything depends on, counted as distinct
seconds in which any index printed, read through gzsalvage so a broken file
counts what it really holds:

| | |
|---|---|
| index seconds on disk | **2,318,260 of 2,505,600 = 92.52%** |
| total silence | **52.0 hours** |
| hour files missing entirely | **30** |
| hour files plain `gzip` cannot read | **22** (gzsalvage fully recovers 6; **16 are dead or near-dead**) |
| days at 100% | 08-31, 09-05, 09-10, 09-11, 09-12, 09-13, 09-19, 09-20, 09-21 |

Every stretch that lost 10 minutes or more of index:

| when (Z) | index lost | what it was |
|---|---|---|
| Tue 08-25 22Z to Wed 08-26 23Z | **18 h 37 min** | 18 consecutive hour files missing on every channel -- a full collection stop |
| Wed 09-02 20Z to Thu 09-03 06Z | **8 h 45 min** | files present at ~2x normal size and **unreadable**; orderbook/trade/ticker for the same hours are normal size, so only this channel was doubled |
| Wed 09-09 13Z to 21Z | **8 h 13 min** | 8 hour files missing on every channel -- full stop |
| Tue 09-01 22Z to 09-02 05Z | **5 h 38 min** | same unreadable-doubled-file signature |
| Tue 09-22 00Z to 05Z | **4 h 49 min** | the Kalshi connection outage in CURRENT_STATE |
| Tue 09-22 23Z to 09-23 03Z | **2 h 36 min** | tonight |
| Tue 09-15 13Z to 15Z | **1 h 42 min** | the Windows Update reboot |
| 23 smaller stretches | **64.5 min total** | ordinary reconnects |

**A weekly, predictable, market-data-only outage nobody has ever named.** The
market channels (`orderbook_delta`, `trade`, `ticker`, `orderbook_snapshot`) sit
at ~0% for 07Z and are MISSING for 08Z on **08-27, 09-03, 09-10 and 09-17 --
four Thursdays, exactly 7 days apart -- while `cfbenchmarks_value` is
untouched.** That is a weekly maintenance window at Thursday 03:00-05:00 ET.
8 tape hours per channel lost so far and ~8 closes a week with no book.
**The next one is Thursday 09-24 07Z.** Nothing in the repo knows about it, so
those hours read as gaps and those closes read as a thin market.

**Disk, re-measured tonight from the files themselves:** the tape wrote a mean
of **3.93 GB a day** over the last five full UTC days (09-17 3.83, 09-18 4.75,
09-19 2.98, 09-20 3.08, 09-21 4.87, 09-22 3.99). Free space **21.3 GB**. At that
rate the 6 GB hard collection stop is **3.9 days away (~09-26/27)** -- sooner
than the ~09-28 in the 09-22 map, and free space fell 0.32 GB in the 35 minutes
of this job, so something other than the tape is writing too.

---

## 3. The inventory -- every recorder / watchdog / tracker failure, in date order

"Guard today?" answers: would the checks that exist as of 2026-09-23 catch this
one if it happened again tonight.

### 3a. Collection and the tape

| # | when (UTC) | what broke | how long | cost | root cause | patched at the time | guard today? |
|---|---|---|---|---|---|---|---|
| C1 | 08-25 04Z | collection starts; first two hours short | 25 min | 25 min of index | unknown -- the collector log for that era no longer exists (see C16) | nothing | no |
| C2 | 08-25 22Z -> 08-26 23Z | every channel, no files at all | **18 h 37 min** | 18 tape hours x 5 channels, ~74 closes; the largest hole on record | **not recorded anywhere.** No log survived | nothing | partly: boot_all would now restart run_all -- except while blind (N1) |
| C3 | 08-26 (first full analysis run) | **68,976,084 of 68,976,084 orderbook deltas unparsed (2.0 GB); 7 stages loaded zero quotes; all exited 0** | one run + every conclusion from it | a whole run's analysis re-done | Kalshi emits `yes_bid_dollars`/`price_dollars`/`delta_fp` as suffixed strings; loaders asked for `yes_bid`/`price`/`delta` | `8af76b4`; loaders now discover field paths from `doctor.py`'s `schema.json`; `EMPTY_MARKERS` in `go.py` labels a stage EMPTY | **yes** |
| C4 | 08-28 17:26 | 14 of 16 stages died on `import gzip` | a whole run | one run | `research/compression.py` shadowed a stdlib package that exists on 3.14 and not on the 3.11 dev box | renamed; `shadow.py` PREFLIGHT | **yes** |
| C5 | 09-01 22Z -> 09-02 05Z | `cfbenchmarks_value` hour files present at **~2x normal size and unreadable** -- 1 to 2 records each even through gzsalvage | **5 h 38 min** | 5.6 h of index; nobody has ever known it was missing | **two writers on one gzip** (same signature as C7); orderbook/trade/ticker for the same hours are normal size, so only the index channel was doubled. The first gzip member is corrupt from byte ~0, so the duplicate-`seq` check that would prove it cannot be run | **nothing -- never reported** | no |
| C6 | 09-02 20Z -> 09-03 06Z | same as C5 | **8 h 45 min** | 8.75 h of index, ~35 closes | same | **nothing -- never reported** | no |
| C7 | 09-06 14:51-15:05Z | 150 s gap on trade/ticker, then `feed_data` **double-written**: the 15:00Z hour is 97-99% lost on coinbase, kraken, bitstamp, gemini and index_replica | 150 s + 1 h of constituent feeds | one hour of exchange books | a watchdog restart orphaned a `crypto_feeds.py`, which wrote alongside its replacement; the restart was needed because `C:\kals\run_all.ps1` carried a `--series` list the repo copy does not | `research/deploycheck.py` (diffs repo vs `C:\kals`, wired into every PREFLIGHT); disk guard 4 -> 6 GB; the orphan killed, not the supervised process | **partly**: deploycheck catches the drift; **nothing prevents two writers on one file** |
| C8 | 08-27, 09-03, 09-10, 09-17, each 07Z-08Z | market channels ~0% then MISSING; the index untouched | 2 h x 4 occurrences | 8 tape hours per channel; ~8 closes a week with no book | **a weekly maintenance window, Thursday 03:00-05:00 ET, exactly 7 days apart** | nothing -- never identified | no. **Next: Thursday 09-24 07Z** |
| C9 | 09-09 13Z-21Z | every channel missing | **8 h 13 min** | 8 tape hours x 5 channels, ~33 closes | not recorded | nothing | partly (as C2) |
| C10 | measured 09-12 by `tapegaps.py` | trade channel silent **6.42%** of covered seconds; of 705 silent runs >= 10 s, **655 are a forward `seq` jump (messages DROPPED) and 42 a `seq` reset**; on **551 of 705 the book goes silent with the trades while the 1 Hz index keeps ticking on the same socket** | continuous | every book reconstructed from the tape is silently wrong after each gap; 97 HOLE hours must be excluded from any count | **a market-data subscription failing, not a dead connection** | a 3-part collector fix was written up and **only part 2 shipped** (flush/close the gzip on SIGTERM, `kalshi_collector.py:372-400`). Part 1 (resubscribe on a `seq` gap) and part 3 (log every resubscribe) were never applied | **no.** Measured tonight over 7.3 days: **2,267 SEQ_GAPS** (one every ~4.6 min) and **38 five-minute windows (3.2 h) where the index arrived and the book recorded ZERO deltas** |
| C11 | 09-15 13Z-15Z | Windows Update reboot took everything down | 1 h 43 min | 1 h 42 min of index, ~7 closes, plus the bot | active hours 15:00-09:00 ET permit a reboot 09:00-15:00 ET while the operator is at work | nothing on the Windows side | no. `KalsBoot` is "Interactive only" and auto-logon is off, so after a reboot nothing starts until he logs in |
| C12 | 09-15 | the Kalshi API key was revoked (401 `NOT_FOUND`) and the account was trading-blocked (VPN logins from work) | hours | trading time | exchange-side | operator + Kalshi | n/a -- not ours to guard |
| C13 | 09-22 00:05Z-05:38Z | Kalshi connection refused; the collector **alive and deaf** on handshake timeouts; the bot refused every market on `book_stale` at 2,024 ms against its 2,000 ms limit | **4 h 49 min** | 4.8 h of index, ~19 closes, and the bot idle while the app said TRADING | Kalshi-side; **our fault is that nothing noticed** | app/phone BLIND banner (`pindesk.blind_of`), recorder rows made freshness-based, `boot_all` stuck-recorder check, coin-race v-race90 | **detection yes, recovery no.** And the stuck-recorder kill is itself disabled by N1 |
| C14 | 09-23 00:05Z-02:26Z (tonight) | same, then a 36-minute degraded resubscribe | **2 h 21 min deaf + 36 min degraded** | **8 closes with no index at all, 2 more with no settlement window**; the DOGE 22:45 ET close has zero book records for its last 13 minutes | Kalshi-side refusal; our resubscribe is market-by-market and not ordered by time-to-close | nothing new tonight | detection fired 14 times (19 min after the silence began); **the tape was recoverable from `index_replica` and nothing said so** |
| C15 | since 09-15 20:30Z, every one of 2,107 windows | **gemini records 1 of 8 symbols** | >= 7.3 days, probably since 08-25 | every `index_replica` mid is a 3-exchange mid | 7 of 8 per-symbol websockets never connect | nothing -- never noticed | **no** (N2) |
| C16 | structural, always | **`run_all.ps1` (the tape's watchdog) has no log at all** -- `logs\run_all.console.log` does not exist -- and every recorder restart **truncates** `collector.out.log`, because `Start-Process -RedirectStandardOutput` overwrites | since 08-25 | **no record exists of any recorder restart, and no diagnosis of C1/C2/C5/C6/C9 is possible** | a fixed log filename + overwrite redirect; `Write-Host` in a hidden process with no redirect | nothing | no |
| C17 | structural, always | `run_all.ps1`'s only health test is `HasExited` (46 lines, no self-test). A deaf-but-alive recorder is never restarted, and it also runs `Get-ChildItem -Recurse` over a 68 GB tree every 5 minutes just to print two numbers | since 08-25 | C13 and C14 both ran their full length with the watchdog "healthy" | "running" treated as "working" | nothing | no |
| C18 | 09-16 12:02 ET onward | `cdc_record.py` (the third recorder) is alive and writing (159 hour files, current to 04Z tonight) but its visible log `logs\cdc_record.out.log` froze 6 days ago; `boot_all` redirects it to `cdc_record.out`, **a different filename**, which does not exist | 6 days | none to data; total loss of visibility | two names for one log | nothing | no |

### 3b. Watchdogs, launchers and the desktop/phone trackers

| # | when | what broke | how long | cost | root cause | patched | guard today? |
|---|---|---|---|---|---|---|---|
| W1 | 09-06 (twice in one day) | "two watchdogs are running" reported twice; both times the second process was **the query's own command line** | -- | wrong alarms acted on | a process filter that matches itself | filters must exclude `$PID` / match the launcher's exact form | partly -- the same class bit the source-text self-tests 4x later |
| W2 | 09-13 | the operator ran `restart_bot.ps1`, the bot did not change, and nothing on disk said why | a session's guessing | -- | no record of what the launcher did | `Start-Transcript` to `results\restart_bot.last.log` | **the transcript itself fails**: `Transcription cannot be started` on 09-17, 09-18 (x2), 09-19, 09-22 01:30 ET and again tonight 20:33 ET -- **6 times, including both of the last two restarts** |
| W3 | 09-17 11:2xZ | `watch_bot.ps1` restarted the bot then **hung inside a pipe for four hours**, while `boot_all` said "all up; nothing to do" every ten minutes because the process existed | **4 h** | 4 h of trading | liveness by process existence | heartbeat file + kill-if-stale (`boot_all.ps1:238-250`, 300 s) | **yes** for watch_bot -- and the same class is live again in N1 |
| W4 | 09-17 | `boot_all` reported "all up" with the phone link dead, because a PowerShell whose command text merely mentioned `pinphone.py` matched | -- | phone alerts lost | matching on any process | `RunningPy` matches `python.exe` only | yes |
| W5 | 09-19 00:02Z | a bare `,` on its own line in `restart_bot.ps1` wrapped the flag list in a nested array. The script **killed the live bot first**, then `Start-Process` refused; every `watch_bot` retry failed identically and the bot stayed down while the operator had been told it was live | ~1 h | trading time + a wrong belief about what was live | kill-before-validate | argv is built and validated **before** anything is stopped ("62 flat strings") | yes |
| W6 | 09-20 03:45-04:41Z | the 20% drawdown brake halted terminally; `watch_bot` restarted every 15 min and the new run re-halted on its first bank read -- **4 times** until a human edited `pinrun-hwm.json` | **56 min, 3 closes** | 3 closes | a terminal brake plus an automatic restarter = a loop; and the diagnosis it was fixed on was wrong (the fake transfers had LOWERED the mark) | mark reset by hand | **no.** The brake trips again at a bank of $767.12 |
| W7 | continuous | `classify_bank_move` invents transfers: **18 of 19 `external` records are another bot's money** (14 the oil bot, 4 the coin-race penny test), 1 is the real $370.44 deposit | since the oil bot started | corrupted the drawdown mark; the fabricated "$58.37 withdrawal" was that minute's two oil settlements to the cent | `pinrun.realised` counts pinrun only, so every other bot's money looks like the operator moving cash | nothing | no |
| W8 | 09-22 (found) | **17 of 24 paper arms were dead** on an inherited `--max-losses 2`; none had been re-synced after three hedge changes; two had become exact copies of live | days | every arm comparison in that window | a paper arm is never restarted after a halt; live is | `sync_arms.ps1`: `--max-losses` never inherited; `arm-live-frozen` pinned | yes, when it is run |
| W9 | before 09-20 | every arm ran a flag list **frozen at launch**; `arm-pin0.97` differed from live in **16 settings**; and no arm could hedge at all before A71 | ~2 weeks | **every confidence, sigma and hedge conclusion before 09-20 is void** | arms launched once, live changed 52 times | `sync_arms.ps1` reads live's own command line | yes, when it is run |
| W10 | ongoing | `risk_abort()` calls `day_loss()` with no `a.live` check, so **24 paper arms read the LIVE day-loss file**; a -$200 live day halts the whole fleet on the day the comparison matters most | latent | the measurement fleet | a shared file with no owner check | not yet | no |
| W11 | ongoing | `boot_all.ps1` launches a **hard-coded set of 16 pre-sync arms** (`--hedge-price 0.60`, `--bank-brake 4.08`) whenever no paper arm is running, e.g. after a reboot | latent | would silently repopulate the fleet with the void configurations | a frozen list instead of `sync_arms.ps1` | not yet | no |
| W12 | 09-19 | `pindesk`'s own self-test had been **raising** since the Refresh button went in; the lab was scoring arms on markets they never traded (A51 read **+201% while $58 behind**, on a flag it had never once used) | days | every lab head-to-head in that window | scoring on the arm's own markets, not shared ones | `h2h` on shared markets; the self-test fixed | yes |
| W13 | 09-22 | `pinphone --selftest` had been failing on the operator's **real** deposits (fixture expected $500, `pinxfer` said $584.46) | days | the phone link's self-test | a fixture that reads live data | fixture pins the deposits | yes |
| W14 | now | the desktop app **cannot Pause or Stop the `--paper-live` race arm**: its filter rejects any command line containing `--live`, and `--paper-live` contains it | now | the operator's only control surface does not cover one running bot | a substring test | not fixed | no |
| W15 | now | **`boot_all` is blind and refuses everything** (N1) | 21 h and counting | the entire boot/recovery layer, including the collectors' watchdog | elevation mismatch | -- | **no** |

### 3c. Measurement tools

| # | tool | what was wrong | what it cost | root cause | state |
|---|---|---|---|---|---|
| M1 | `pinsim` / `pindata` | the `yes_dollars_fp` snapshot bug -- **every threshold for two days was tuned on a replay that had never reproduced a real loss** | two days of tuning | a unit/field bug in the snapshot path | fixed 09-10; the standing rule is now that a replay result is a HYPOTHESIS |
| M2 | `pinsim` | **OOM-killed** after 4 of 72 hours at 3.3 GB resident with 2.0 GB free | one 72-hour holdout run | `_HOUR_CACHE` (12 x ~800 MB) kept hours a one-pass run never revisits | evicts per hour; fixed |
| M3 | `kalshi_fulltape.py --markets 1200` | **OOM-killed** at market 600 with 3.5 M trade records resident; and it DUMPS only what it fetched, so a small re-run would have overwritten the settlement history | the settlement refresh | loading the trade tape to get settlements | replaced by `pinsettle.py` (merge, a few MB) |
| M4 | `pinpickoff.py --rebuild` | **memory-killed twice** at ~1.6 GB free with 22 python processes; the arm/grid rebuild was killed again at 50 of 130 hours; `pingrid` had to aggregate in place after two more | the pickoff tracker's data **still stops at 09-12**, immediately before the drop the operator was asking about | batch rebuilds on a box that is ~85% committed | "foreground for walks, from now on"; the rebuild has still not been done |
| M5 | `hedgetune.py` (shipped v-hedge25) | priced insurance on **the collector's receive time**. Receive lag in the alarm windows: median 0.04-0.29 s but **max 1.9-6.5 s in 14 of 16 alarms**. DOGE 09-18 priced insurance at **2.2c when we paid 74c**; ETH 09-12 5.5c vs 26-27c. Over 698 hedged contracts the tool was **$26.25 too cheap**; re-keyed on the exchange's own `ts_ms` it is **$2.34** off. It also carried a **452-second-old quote** for a market whose ticker feed had been dead 7.5 minutes, with no staleness check, and it hedged before it entered, top level only | the hedge trigger was moved 0.60 -> 0.25 on it. Re-measured: 0.25 beats 0.60 by **$8-46, not $97**, and `PREREG_hedge`'s "not below 0.30" was bypassed | the wrong one of two clocks | diagnosed 09-22; the tool has not been re-run |
| M6 | `racebook.py` (the coin-race tape study) | times ticker lines by `_rx_ms`; the exchange's own `ts_ms` is present and unused. Collector receive lag on CRYPTOLEAD ticker: median 0.4-0.5 s, p90 1.5-2.3 s; at tau 30-60, **5-11% of lines lag over 2 s and 1-4% over 5 s** -- and bursts are exactly when pickoffs happen | **the bias favours the strategy and its size is unmeasured.** The "lag 2 honest" control is really lag ~1.5, and 0 or less on the lines that matter | same clock class as M5 | known, not fixed. `replay.py` prefers message `ts`, so the pin replay is clean; other tape tools unchecked |
| M7 | the collector itself, as a timing source | `_rx_ms - ts_ms` on `orderbook_delta`: median 28-38 ms but **p90 2.7-4.7 s in every hour checked**, and 1.9-4.4 s in the second before 4 of 8 collapse fills. `pinsim` times deltas by `ts_ms` (fine) but **snapshots by `_rx_ms`** | anything timed by receive time is seconds wrong exactly when prices move | the recorder's backlog during bursts | known, not fixed |
| M8 | the refusal log | refusals are **de-duplicated per (close, market, gate)**, so the log records that a gate fired, never how many moments it blocked | **the most valuable open question -- why the <=30 s window's volume fell 65% -- cannot be answered from the data we have.** It needs a log field, not more analysis. Also `MAX_ATTEMPTS_PER_MARKET` counts at the signal point, so three refusals in 150 ms lock a market out of a whole close (13 post-fix lockouts, 11 with a standing offer at >= 99.5%) | de-duplication chosen for log size | `close_summary.gates` is undeduped and now the workaround; v-instr1 added records for two invisible cases |
| M9 | the bot's own logs, and `pinday` | they **miss every market held when a run died**. 09-19 the logs say -$161.14, Kalshi says **-$223.46**. Lifetime the logs **overstate profit by $72.34** | **v-nocap kept and enlarged the 45 s leg on "+$110.67" when Kalshi said -$68.78** | a log written by a process that died | `pinday.py` now takes money from Kalshi's ledger and prints every market the logs missed |
| M10 | summing `realised` | `realised` is a session running total in dollars that resets on restart; `pnl_c` is this bet in cents | reported **$1,183 on an account that had made $13.87 -- 85x** | two fields, one plausible name | rule written down; `pnl_c` only |
| M11 | baselines | "the cheap pool HALVED" was measured against **the four busiest days ever** (corrected twice; against a normal day cheap offers were +7%). "$50-60/day of missed deals" was an arithmetic bound on a flat-supply premise that is **false**: the real pile is **$3-10/day gross and $3-5/day grabbable**. "2026-09-13 was a Saturday" in three documents -- it was a **Sunday** | changes proposed, and nearly made, on a baseline that was a peak | comparing to a trailing extreme instead of a named window | `pinsupply.py`/`pincheap.py` per day and per week; the standing rule is to report the MEDIAN of every earlier day |
| M12 | self-tests | **a source-text self-test finds its own copy of the string** (bit 4 times in one session, one silently for days); **a self-test that asserts a RUNNING value refuses to start the bot** (6 times, including a 6-minute live outage from `--price-ceiling`); and **no self-test ever executes `trade_loop`** -- every loop-level protection (A69, A71, A74) is a text search | a live outage, repeated false green | tests that read code instead of running it | `rindex`/anchored lines; assert `_DEFAULT_*`; the loop test is in the K1 build |
| M13 | version discipline | **eight live changes went out 09-11..09-13 with no VERSIONS entry and nothing checked** | the reconstruction is thin and some of it is unrecoverable | no automated check | `versioncheck.py` fails if `restart_bot.ps1` passes a flag VERSIONS.md does not mention. **It covers the money bot's flags only** -- see K11 |

---

## 4. The recurring CLASSES

These are the ones that have each produced three or more separate incidents
above. The operator's question is answered by K1, K2, K3 and K4: nothing has
been fixed at this level, only at the level of individual symptoms.

**K1. "Alive" is treated as "working."** Every check asks whether a process
exists, never whether the specific thing it produces is arriving at the rate it
should. C13 (collector deaf 4 h 49 min), C14 (2 h 21 min), C17 (`HasExited` is
the only test), W3 (the watchdog hung 4 h while "all up"), C15 (gemini at 1 of
8 for a week), W12 (pindesk's own self-test raising), N1 (boot_all "all up" for
21 h while blind). **Seven incidents.** Each was patched by adding one more
specific check to one specific consumer.

**K2. A partial failure reads as total health.** One channel of five, one
exchange of four, one market of twelve, one symbol of eight. Every monitor is
per-PROCESS or per-DIRECTORY, never per-STREAM. C8 (market channels dead, index
fine -- four times), C10 (551 of 705 gaps are exactly this shape), C14 (DOGE got
zero deltas while the feed was "back"), C15, M5's dead ticker feed.

**K3. No named baseline, so the degraded level becomes the norm.** gemini's
median IS 1 of 8. The tape's per-hour median INCLUDES the broken hours. "The
pool halved" was against the busiest days on file. M11, C15, and the size-based
gap scan that missed C5/C6 entirely (those files are ABOVE the median size).

**K4. The record of a failure is destroyed by the failure.** C16 (`collector.out.log`
truncated on every restart; `run_all` has no log at all), W2 (`Start-Transcript`
fails exactly when `restart_bot` fails), M9 (the bot's log misses what it was
holding when it died), C5/C6/C7 (the restart that ended the run corrupted the
gzip it was writing), C18 (a log under a name nothing writes). **This is why
C1, C2, C9 have "cause not recorded" against 35 hours of lost tape.**

**K5. Two clocks, and the wrong one gets used.** M5 ($26.25), M6 (an unmeasured
bias in favour of a strategy), M7 (pinsim snapshots). Also the "9,999 min silent"
sentinel in tonight's DEAF alert, which is not a number the operator can read.

**K6. A guard that cannot act, or acts on the wrong thing.** N1 (blind, so it
refuses), C13/C14's DEAF check (alerts only), pintake's halt (blocks hedges),
W10 (paper arms read live's day-loss file), W6 (a terminal brake plus an
automatic restarter is a loop), W5 (killed before validating).

**K7. The fix was written up, agreed, and not applied.** C10's collector
resubscribe (1 of 3 parts shipped, 11 days ago, and it caused tonight's DOGE
book loss). The "collector alive but deaf" check was proposed 09-21, built
09-22, and disabled by N1 within hours. M4's rebuild is still not done.

**K8. Two writers on one file.** C5, C6, C7. `boot_all`'s own comment names the
fear ("a duplicate collector corrupts the tape") and its response is to refuse
to start anything -- which is how N1 became a total outage of the boot layer.

**K9. A measurement tool self-tests its logic and never its input.** C3 is the
extreme: 68,976,084 of 68,976,084 records unparsed, 7 stages loading zero, every
one exiting 0 and every self-test green. The self-test gate plants an answer in a
synthetic world; nothing checks that the real input arrived at the expected rate.

**K10. Rebuilds are batch jobs on a box that is 85% committed.** M2, M3, M4 --
at least five OOM kills of measurement tools, and the collector survived each
only because the OS picked the bigger process.

**K11. The infrastructure layer has no version log and no owner.** All **38**
entries in `results/VERSIONS.md` are money-bot behaviour. **Not one** covers
`run_all.ps1`, `boot_all.ps1`, `watch_bot.ps1`, `kalshi_collector.py`,
`crypto_feeds.py`, `pindesk.py` or `pinphone.py`. There is no dated record and
no revert command for any infra change, and `versioncheck.py` does not look at
them. `run_all.ps1` -- the process the whole project depends on -- has no
self-test at all.

---

## 5. ONE design, not eleven patches

The shape of every failure above is the same: **a consumer decides, on its own,
whether a producer it does not understand is healthy, by looking at something
that is not the data.** The design is to invert that.

**1. Every producer declares its own health, per STREAM.** A stream is
(producer, channel) for the Kalshi recorder and (producer, exchange, symbol) for
the feeds recorder -- so `gemini/DOGE` is a stream and C15 becomes visible.
Every 30 s each producer writes ONE small json to `results/health/<producer>.json`:
per stream, records in the last 60 s, **the rate it expects**, the last record's
**exchange** time and receive time, and the seq gaps since the last write.
Nothing has to parse a log to guess. This is the only new thing the recorders
have to do, and it is where C10's resubscribe counter and C15's per-symbol
connection state also land.

**2. One supervisor, and it needs no privilege.** It reads only those json files
plus pid files and file mtimes, and **never `Win32_Process.CommandLine`**. A pid
file plus `Get-Process -Id` works across integrity levels, so the whole N1 class
disappears -- and it stops boot_all's "refuse while blind" from ever being able
to disable the tape's own watchdog.

**3. Three states per stream, and the ACTION for each is written down before the
check ships.** OK / DEGRADED (below expected, above zero) / DEAD (zero). DEAD +
the producer's own log shows retries -> alert, do not restart, **and switch the
fallback on**. DEAD + no retry -> restart. DEGRADED -> alert with the number and
the baseline it is being compared against. This is the same rule
`CURRENT_STATE.md` already applies to gates: write down what it BLOCKS, and prove
in a self-test that it cannot block a hedge.

**4. Baselines come from a named good window checked into the repo, never from
the trailing median.** That is what kills K3, and it is the only way a stream
stuck at 1 of 8 for a month can ever be flagged.

**5. Nothing truncates a log, ever.** Producers write `logs/<name>-YYYYMMDD.log`
and append; the supervisor never redirects to a fixed filename; `restart_bot`
appends to a dated file instead of `Start-Transcript`. K4 is the class that has
cost the most, because it is the one that makes every other class
undiagnosable.

**6. The fallback is declared, automatic and marked.** `index_replica` held
**3,600 of 3,600 seconds in every hour Kalshi's index was missing tonight**.
`replay.load_index` should read it when the Kalshi hour is absent or short, tag
those rows, and every stage should print how many of its seconds came from the
fallback. That single change turns tonight's "the tape is gone" into "the tape
is second-hand for 8 closes, and here is how many".

**7. The 09-12 collector fix ships, with close-priority resubscribe.** On a
`seq` gap or reset, resubscribe those channels without dropping the socket;
after any reconnect, resubscribe markets **nearest their close first**; log every
resubscribe with a count. That is the one change that would have kept the DOGE
22:45 ET book.

**8. Every stream check gets a NULL in its self-test.** Fail if the check fires
on a healthy 60 s window, and fail if it misses a stream pinned at 1 of 8. And
one self-test that actually RUNS the supervisor against a fake `results/health`
tree, because K9 says a check that is only read is not a check.

**9. `results/VERSIONS_INFRA.md`, same rules, and `versioncheck.py` extended to
fail if any of the seven infra files changed without an entry.** Plus a
`results/KNOWN_OUTAGES.md` naming the Thursday 07-08Z window, so those hours are
excluded by name instead of read as a fault.

**10. Disk is still the only hard deadline: 21.3 GB free, 3.93 GB/day, 3.9
days.** No design above matters if `run_all.ps1` hits `$free -lt 5` and breaks
its loop -- and right now, with `boot_all` blind, nothing would restart it.

---

## 6. Job end -- resources and processes

Disk **21.34 GB** free (down from 21.66 GB at the start of this job). RAM
**1.22 GB** free of 15.8. `kalshi_collector.py` pid 105304 (57 MB) and
`crypto_feeds.py` pid 105352 (55 MB) **both alive**; live bot pid 2230760
(87 MB) alive; `cdc_record.py` pid 345648 alive and writing. Nothing was
started, stopped, killed or signalled. Files written: this one, and scripts
under the scratchpad `infra/inventory/`.

