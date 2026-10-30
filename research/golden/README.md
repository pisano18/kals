# Golden-output harness (step 0 of the phone rebuild)

Records what the Telegram phone bot (`pinphone.py`, `botstats.py`, `tgcharts.py`) says and draws for every command,
chart, alert and data view, from one frozen copy of the server's data, so a refactor can be checked byte for byte.
Nothing here is imported by production code. Design: DESIGN.md section 4, "Step 0".

## Files

| file | what |
|---|---|
| `capture.py` | runs on the server: renders every case once against the real `results\` (read-only, fenced), learns which files they touch, copies those into a fixture folder outside the repo |
| `replay.py` | renders every case of every world from a fixture with one code tree, one process per world |
| `compare.py` | expected vs actual, case by case; `--accept CASE --why "..."` writes `CHANGES.md` |
| `shadow.py` | step 9: the OLD Phone path vs a NEW `phone/commands` module, byte for byte, in every world (below) |
| `gl_child.py` | one world of a replay (started by replay.py) |
| `gl_cases.py` | the cases and their runners, the Kalshi store / recorder, the seams |
| `gl_fence.py` | file-system virtualisation and write guard, network / process guards, frozen clock, thread registry |
| `gl_worlds.py` | the eight worlds |
| `gl_common.py` | JSON codec, normalisation, file names |
| `CHANGES.md` | accepted differences (world, case, digests, why) |

## Record and compare on the same machine

PNG bytes depend on the matplotlib build (3.11.2 on the laptop and on the server today). Record the baseline and
replay the tree under test on the SAME machine with the SAME Python (`C:\Python314\python.exe`: matplotlib, numpy,
PIL). Everything below runs on the laptop; nothing in a replay can reach Kalshi, Telegram, AWS, the real `results\`
or `C:\kals` (the fence refuses it and the case FAILS).

### 1. A fixture (once; the server has the live data)

Fixtures live outside the repo, in `C:\kals-golden\fixtures\<stamp>\`. The current one is
`C:\kals-golden\fixtures\20261030T132932Z` (captured 2026-10-30 13:29Z on the server, code 5492870). To make a new
one (one read-only pass on the server, about 3.5 minutes, below-normal priority, refuses under 800 MB free):

```powershell
scp -i ~/.ssh/kals_server_ed25519 research\golden\capture.py research\golden\gl_*.py Administrator@18.216.240.218:C:/kals/golden/tools/
ssh -i ~/.ssh/kals_server_ed25519 Administrator@18.216.240.218 "C:\Python314\python.exe -u C:\kals\golden\tools\capture.py --code C:\kals-repo\research --root C:\kals\golden --extra-names C:\kals\golden\tools\extra_names.json"
scp -r -i ~/.ssh/kals_server_ed25519 Administrator@18.216.240.218:C:/kals/golden/fixtures/<stamp> C:\kals-golden\fixtures\
```

`--extra-names` (optional) is a JSON list of `results\` file names to copy as well, for files a newer code tree reads
that the server's code does not. The capture writes only under `--root`; Kalshi is asked through the phone's own
GET-only getter, each distinct request once (`kalshi.json`); botstats is served from a copy of
`botstats_cache.json` re-stamped to the capture clock; `telegram.json` is never read (the fixture gets a fake one);
`*.pem` / key / secret files are never copied. On the laptop, `--no-kalshi` captures without any Kalshi request.

### 2. Record a baseline from a git sha

```powershell
git -C C:\kals-repo worktree add --detach C:\kals-golden-base <sha>
C:\Python314\python.exe research\golden\replay.py --fixture C:\kals-golden\fixtures\20261030T132932Z --code C:\kals-golden-base\research --out C:\kals-golden\expected\<sha>
```

Another sha later: `git -C C:\kals-golden-base checkout --detach <sha>` (or `git -C C:\kals-repo worktree remove
C:\kals-golden-base` and add again). The harness itself always runs from the working tree's `research\golden`;
only `--code` changes. A worktree's own `results\` is never read (the fence maps every results path to the fixture).

### 3. Compare a working tree

```powershell
C:\Python314\python.exe research\golden\replay.py --fixture C:\kals-golden\fixtures\20261030T132932Z --code C:\kals-repo\research --out C:\kals-golden\actual\<name>
C:\Python314\python.exe research\golden\compare.py C:\kals-golden\expected\<sha> C:\kals-golden\actual\<name>
```

`compare.py` prints one line per world and writes `<actual>\compare.md` (`--report FILE` elsewhere): a table, every
FAIL case, and for each changed case the fields that differ with a unified diff; for a changed chart both PNGs and a
PIL difference image go to `compare_files\`. Exit 0 = every case byte-identical or accepted.

An intended change: `compare.py EXPECTED ACTUAL --accept "base/cmd//bots" --why "v-tg-active hides stopped bots"`
appends one line per matching changed case to `CHANGES.md` (pattern: `world/case`, fnmatch, `*` crosses `/`; no world
= every world). A later compare treats exactly that pair of digests as accepted; a further change shows again.

A whole run: about 3.5 minutes on the laptop (`--jobs 2`), 8 worlds x 90 cases. Useful options: `--world base`
(repeatable), `--only REGEX` (case ids), `--repeat N` (each case N times in one process: flakiness check),
`--keep-work`, `--jobs`. `GOLDEN_MPL_TRACE=1` writes every matplotlib drawing call's data to `mpl_trace.txt` (for
a chart diff).

## Cases (ids)

- `cmd//status` ... every command and alias of DESIGN 1.1 (`/status /s /status@kalsbot /start@ /today /yesterday
  /days /open /fills /bets /brief /summary /market /losses /hedges /stats /race /racestats /bots /pin /forecaster /fc
  /ladder /weather /wx /fx /jb /jumpband /bars /funds /bank /accounts /speed /server` + `help ? aws setup`,
  `/features /pause /start /start@kalsbot /stop`, `/stop yes`, `/stop no`, `/mute /unmute /update /help /? /HELP`,
  `hello there`, `/nosuchcommand`, empty), plus any command the tree under test adds (its `BOT_CMDS`, `CMD_KIND`, help
  text). Each: reply text, type (`Html` / `str` / `None`), the exact `split_html` / `split_text` chunks, everything
  `say()` sent (control and /update workers, joined), the chart kind, the Kalshi requests made, fence events.
  `/pause /start /stop yes` call STUBS of `pindesk.do_*`; `/update`'s two self-test runs are stubbed to pass.
- `pair/right`, `pair/right-at`, `pair/wrong`, `pair/empty` (a fake unpaired config in the world's scratch
  `C:\kals\telegram.json`), `auth/other-chat`, `auth/unpaired`.
- `chart/<kind>` for every kind in the tree's `tgcharts.CMD_KIND`: `tgcharts.build(kind, Phone._chart_ctx(...))` ->
  sha256 + size + caption (PNG in `charts\`).
- `tick/alerts-state` (bot down / back / stand-down flag), `tick/alerts-recorder` (silent, both silent, back),
  `tick/alerts-disk` (7.5 / 5.9 / 4.0 / 9.5 GB), `tick/alerts-loss` (the newest losing close is new),
  `tick/alerts-daily` (8 AM summary, then muted), `tick/update-flag` (results\pinphone.update in the scratch copy).
- `data/all_bots` (canonical JSON), `data/active_bots`, `data/owner` (every fixture ticker in its sub + synthetic
  tickers in every sub), `data/version_of` (every bot), `data/kind_of`, `data/tables` (the per-bot tables the
  registry must reproduce).

A case's `status` is `FAIL` (and says why) on: an unrecorded Kalshi request, a read outside the fixture, a write
outside the scratch copy, a network attempt, a signalled process, a thread left running, a harness error. A refused
process start (bars' watcher scripts) is listed in `fence` but is not a failure.

## Worlds

| world | what changes |
|---|---|
| `base` | the fixture as captured |
| `race-stopfile` | `pinracepenny.stop` set and a live race process in the table (running, refusing every trade) |
| `jumpband-live` | `jumpband_live.py --live` in the process table, no stop file |
| `jumpband-dry-run` | `jumpband_live.py --live --dry-run` instead (sends nothing) |
| `procs-unreadable` | every process reader returns None; no cached table in botstats' cache |
| `kalshi-down` | every Kalshi GET answers 500; botstats' cache read stamps 2 h old |
| `dst-2026-11-01` | the clock at 2026-11-01 13:30Z (8:30 AM EST, after the clocks went back); cache fresh at that clock |
| `empty-logs` | every `*.jsonl` / `*.log` / `*.out` in results emptied (mtimes kept) |

## How a replay is held still

- One process per world, `PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1`, `OPENBLAS_NUM_THREADS=1`, MPLBACKEND Agg.
- The fence is installed before `--code` is imported. `open`, `os.stat/listdir/scandir/remove/replace/...`,
  `os.path.exists/getmtime/...` go through it: `<tree>\results`, `C:\kals-repo\results`, `boot_all.ps1`, `C:\kals`
  and the research data files the capture saw read (`cleanroom\ladder_live.py`) are REDIRECTED to the world's
  scratch copy (mtimes from `manifest.json`); any other read under a repo, `C:\kals`, `C:\kals-live*` or `~\.ssh`
  is refused and fails the case. Writes go only to the scratch copy and the output folder.
- Clock: `time.time`, `localtime()`, `gmtime()`, `strftime(fmt)`, `datetime.now/utcnow/today`, `date.today` read
  the world's frozen clock; `time.sleep` returns at once. `monotonic` / `perf_counter` stay real (deadlines only).
- Seams: `pinphone.list_python_procs`, `botstats._procs_native / read_procs`, `botdata.procs.native_rows / wmi_rows /
  read_all` (so `procs.table() / cached() / refresh_once()` too; when the tree has botdata) (the recorded process table),
  `pinphone.machine_read`, `pinphone.kalshi_ping`, `pinphone._aws_http` (refused: the not-connected path),
  `pindesk.health` (recorded), `shutil.disk_usage` (recorded), `pindesk.do_start/do_pause/do_stop` (stubs), the Phone
  attributes of the same names; `kauth` is a fake module serving `kalshi.json`. A seam the tree no longer has is
  listed in `meta.json` (`missing_seams`) and `replay.py` prints it.
- Every module-level `_cache` dict / list / set of the code under test is put back to its just-imported state before
  each case, so no case depends on the one before it. The Ledger is shared (built and refreshed once per world).
- Strings are normalised: the code folder -> `<CODE>`, its repo and `C:\kals-repo` -> `<REPO>`, the scratch folder
  -> `<WORK>`, `0x...` addresses -> `0xADDR`.

## Shadow: a new command module against the old Phone path (step 9)

```powershell
C:\Python314\python.exe research\golden\shadow.py --module phone.commands.hedges [--module ...] [--case "/server help=phone.commands.server"] [--only REGEX] [--world W] [--jobs 2] [--code <research dir>] [--fixture DIR] [--out DIR]
```

For every message text of each module (each name its Command(s) declare plus their `examples`; `--case` adds a text
or a `cmd/...` case id with its module; no `--module`/`--case` = every module in `<code>\phone\commands`), in each world
(default all 8), one world process builds the world exactly as a replay does (`replay.copy_fixture`,
`gl_worlds.prepare`, `gl_child.open_world`: same fixture, frozen clock, fence, seams, guards) and runs, through
`gl_cases.run_case` (caches, health, clock and scratch files put back before each side):

- OLD: `Phone.handle(chat, text)` (the replay's cmd case);
- NEW: the router's steps (split as handle does, `ledger.refresh()` when `needs_ledger`, the paused-bot check -> the
  pair is `hidden`, not compared), then `Command.run(Ctx.from_phone(phone, text))`.

Compared: reply text, type, `split_html`/`split_text` chunks, `say()` messages, mute state, exception, chart kind
(`tgcharts.kind_of(cmd)` vs `Command.kind_of(cmd)`), Kalshi requests (set), fence events, case status. Output:
`<out>\<world>\shadow.json`, `<out>\shadow.md` (unified diffs, new-path tracebacks); default `--out` is
`C:\kals-golden\shadow\<stamp>-<pid>` (parallel agents never collide). The harness runs from its own folder and
`--code` names the tree under test, so a lane in its own worktree runs `<worktree>\research\golden\shadow.py --code
<worktree>\research`. Exit 0 only when every compared pair is identical in every world run (last line `shadow:
IDENTICAL in all 8 world(s) ...`). `--only` filters pair ids (`hedges /hedges`). One world: ~7 s + the fixture copy.
The authors' contract: `research\phone\commands\CONTRACT.md`.

## Known limits

- **Render noise.** matplotlib on this machine can draw a long path's sub-pixel edge differently from one draw to the
  next with identical data (measured: `dst-2026-11-01/chart/bot:fx`, 263 pixels, at most 6 levels; it happens even
  twice in one process). `compare.py` counts a chart whose only difference is the PNG bytes and whose pixels differ by
  at most 24 levels on at most 2,000 pixels as the same (`noise` column).
- Paper-arm logs (`pinrun-paper-*.jsonl`, 704 MB on the server) older than 7 days are 0-byte stand-ins (mtime kept):
  only /brief and /bars read them; those cases list `standins_read`. A case that reads any other stand-in lists it too.
- Big logs read only near their end are copied as that tail (`manifest.json` `mode: tail`); files the code only
  looked at (stat / listing) are copied whole up to 64 KB, else 0-byte stand-ins.
- /bars' watcher scripts (`--report` subprocesses) are refused: /bars shows "could not run" for them.
- /server's AWS section is the not-connected path (no AWS request at capture or replay).
- The 20261030T132932Z fixture's clock is the start of the trace (later captures use the end of the copy): files
  written in the ~15 s before the health read show as "-14 s ago".
