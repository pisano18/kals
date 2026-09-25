# REPO_MAP.md -- where things are (for AI sessions)

Snapshot 2026-09-25. Points at the docs; does not restate them. Repo = `C:\kals-repo`,
branch `claude/file-uploads-70rtjl`. Everything inside is UTC; speak ET to the operator.

## Read in this order

1. `CLAUDE.md` (auto-loaded) -- rules and how to report.
2. `CURRENT_STATE.md` -- what is deployed right now.
3. `HANDOFF.md` -- **top section only** (the file is ~420 KB, newest first).
4. `OPEN_WORK.md` -- topic index; the operator names topics from it.
5. `results/VERSIONS.md` -- top entry = what the live bot runs, with its revert command.
6. `results/IDEA_LEDGER.md` before proposing any money idea; `research/sweep/README.md` to run a sweep.
7. Changing strategy: `THEORY.md`, `RUNBOOK.md`, `PROJECT_HISTORY.md`, `BIASES.md`. Unattended/phone runbook: `GUARDIAN.md`.
8. Finding a file: `research/INDEX.md` (every .py: status, purpose, who uses it) and `results/INDEX.md`.

## Top level

| path | what |
|---|---|
| `research/` | all bot + analysis code, flat, one file per question. `poly/` Polymarket recorder/report, `sweep/` money-idea sweep, `_verify/` 09-08 checks |
| `results/` | outputs AND live state: live/paper logs, reports, caches, pid/heartbeat (731 MB) |
| `restart_bot.ps1` | restart the live bot (validates before it kills) |
| `watch_bot.ps1` | watchdog for the live bot and desktop app |
| `boot_all.ps1` | bring everything back after a reboot |
| `sync_arms.ps1` | paper arms = live command line + one change |
| `start_*.ps1`, `restart_arms.ps1`, `restart_stale_arms.ps1` | older arm launchers (09-15..20) |
| `run_all.ps1` | collector watchdog -- the RUNNING copy is `C:\kals\run_all.ps1` |
| `run_when_away.ps1` | analysis pipeline (`research/go.py`); commits `results/` |
| `watch_hourly.ps1`, `START_COINRACE_LIVE.ps1`, `open_deck.cmd` | idle / retired |
| `kalshi_collector.py`, `crypto_feeds.py` | collector SOURCE; running copies are in `C:\kals` |
| `kalshi_fulltape.py` | settlement pull -> `C:\kals\fulltape` |
| `kalshi_backtest/brti/gate1/signals.py` | phase-0 scripts, done |
| `tool/`, `profiles/` | 09-11 browser tool (served by `research/pintool.py`), idle |
| `flow_cache/`, `certs/`, `.sweep/`, `*.zip`, `*.json` at root | ignored caches and generated files |

Root docs not in the reading list are history: `PLAN.md`, `PLAN_V3.md`, `STATUS.md`,
`RUN_WHEN_HOME.md`, `EXPLAIN_SIMPLY.md` (08-25..27), `IDEAS.md` (09-04), `PREREG_pin.md`
(09-06 draft), `RESTART.md`, `TOOL_PLAN.md` (09-11), `FACTS.md` (09-13), `PI_MIGRATION.md`
(09-15, never done), `HANDOFF_2026-09-14/17.md`. Root `RESULTS_{calib,chain,maker,voltiming}.md`
are stale 08-28 copies -- the real ones are in `results/`. Root `REPORT.md` and `RESULTS.md`
are generated and gitignored.

Outside the repo: `C:\kals` holds the running collector copies, `kalshi_data/` and
`feed_data/` (never touch), `fulltape/` (settlements), `logs/`.

## What is running -- ask the process table, not this file

```bash
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | ForEach-Object { \"\$(\$_.ProcessId) \$(\$_.CommandLine)\" }"
```

Filter on `Name='python.exe'`: a bare `-like '*x.py*'` also matches the shell running the
query. At snapshot: `pinrun.py --live` (money), `pinracearm.py --live` (coin-race money),
10 `pinrun` paper arms (one is `pinrun_afternoon.py`), 5 `pinracearm` paper arms,
2 `cmdarm`, `pinphone`, `pindesk` (pythonw), `pinledgerd`, `wxwatch`, `quakewatch`,
`rungwatch`, and the collectors from `C:\kals`.

## Naming in results/

- `pinrun-live-<startUTC>.jsonl` -- one file per live-bot start; newest = current.
- `pinrun-paper-<startUTC>.jsonl` -- one per paper-arm start. The arm name is not inside;
  `arm-<name>.out` prints the arm's current log (`results/INDEX.md` has the table).
- `arm-<name>.out/.err` -- paper-arm stdout. `pinracearm-<arm>.jsonl`, `pinracepenny-live.jsonl`
  (coin-race live), `cmdarm-*.jsonl`, `<watcher>-<startUTC>.jsonl`.
- `RESULTS_<topic>.md` -- one per question ("automated run" ones are `go.py` stages).
  `PREREG_<topic>.md` -- the bar, written before the data. `ARM_<slug>.md` -- written and
  committed by pindesk when an arm is deleted.
- `VERSIONS.md` -- `v-<name>` entries, parsed by `research/versioncheck.py`.
- Money: per market `settled.pnl_c/100`; `settled.realised` is a running day total;
  `kalshi_ledger.json` (from Kalshi) is the authority, `kalshi_transfers.json` for deposits.

## Gotchas that cost tokens or money

- `research/pinrun.py` is 1.1 MB (~20k lines): grep, then Read with offset/limit. Never Read
  it whole. `pinrun913.py`, `pinrun_afternoon.py`, `pinvin_*.py` are frozen copies with the
  same docstring -- aim greps at `research/pinrun.py`.
- `pinracearm.py` imports `pinrun`: a pinrun edit reaches the coin-race money bot at its next
  restart too.
- Editing the repo's `kalshi_collector.py`/`crypto_feeds.py` does nothing until copied to
  `C:\kals` (`research/deploycheck.py` checks).
- Live state files are tracked in git (`pinrun-live.pid`, `pinrun-hwm.json`, ...). With bots
  running never stash/rebase/reset/checkout `results/`; take remote commits with fetch + merge.
- `run_when_away.ps1` runs `git add results`: anything in `results/` that is not ignored gets
  committed.
- `pinlab.py` still marks the `pinvin_*` arms RUNNING; they are not.
- Docstrings that are wrong: `pinracearm.py` ("nothing is ever sent" -- it has `--live`),
  `pinrun.py` ("--live sends size 1"), `research/poly/*` (call themselves `scan_poly_ws*.py`).
- `go.py` defaults to `./kalshi_data` -- wrong here. Use `run_when_away.ps1` or pass
  `--data C:\kals\kalshi_data --out C:\kals\fulltape`.
- Code saved inside `results/`: `cf_2026-09-24/armh2h2.py` (arm vs live, read `h2h`),
  `audit/*.py`, `_verify*.py`.
- The Bash tool's heredocs mangle backslashes: write scripts with the Write tool, run by path.
