# Moving the stack to the Raspberry Pi 5 -- checklist

Written 2026-09-15, the day a Windows Update restart took everything down for
1h43m and nothing came back on its own. Inventory measured on the PC that day.
Nothing here has been done yet.

## 0. Blockers -- decide before starting

| | |
|---|---|
| **Hard drive** | The tape is **52 GB** (`kalshi_data`) + **11 GB** (`feed_data`) = 63 GB, growing ~4 GB/day. An SD card cannot hold it. Without the drive, the Pi can run the BOT but not the collector. |
| **Kalshi account** | Trading is BLOCKED (409 `TRADING_BLOCKED`) since 2026-09-15. The bot can be installed and paper-tested on the Pi, but not verified live until Kalshi lifts it. |
| **Pi RAM** | Live bot 65 MB, each paper arm ~65 MB, collector 13-25 MB: the whole live stack is well under 1 GB. The heavy ANALYSIS loaders (idxload, load_quotes: 2-3 GB each) stay on the PC. |

## 1. What moves, and what replaces the Windows scripts

On Linux, `systemd` with `Restart=always` IS the watchdog, and `WantedBy=multi-user.target`
IS start-on-boot -- both things that failed on 2026-09-15 come free.

| today on Windows | on the Pi |
|---|---|
| `run_all.ps1` (collector + feeds, restart loop, 5 GB disk stop) | two systemd services + a disk-check timer that keeps the 5 GB stop |
| `restart_bot.ps1` (refuses if a position is open, never two bots) | a pre-start script that keeps the position-open check and the one-bot check |
| `watch_bot.ps1` (restart, max 4/hour) | `Restart=always`, `StartLimitBurst=4`, `StartLimitIntervalSec=3600` |
| `start_arms.ps1` (6 paper arms + race arm) | one templated service per arm, same flags |
| `watch_hourly.ps1` | optional; hourly had no edge |

## 2. Software

- Pi OS Bookworm ships **Python 3.11**; the PC runs 3.14. All live-stack files
  (`pinrun, pintake, ordercli, livebook, engine, kauth, pinracearm, pinracemodel,
  idxload, pinhourly, kalshi_collector, crypto_feeds`) **parse as 3.11** (checked
  2026-09-15). Parsing is not running: every self-test must pass ON THE PI.
- Third-party packages, and only these: `cryptography` (signing), `websockets`
  (PC has 17.0.1), `requests` (collector). Use a venv.
- `crypto_feeds.py` imports `feeds.load_tob` from a `research/` folder next to
  it -- copy `research/feeds.py` alongside, or the import quietly fails.

## 3. Windows-only things that must change

| where | what | action |
|---|---|---|
| `research/kauth.py` | key file path | **done**: set `KALSHI_KEY_FILE` |
| `research/pintake.py:128-129` | `PROD_KEY_FILE`, `DEMO_KEY_FILE` = `C:\kals\*.pem` | needs the same env override -- a LIVE code change, so a VERSIONS entry |
| `research/pinrun.py:~103`, `livebook.py:93,949`, `pinracearm.py:390` | `sys.path` insert of the Windows TEMP folder | harmless on Linux (path doesn't exist; `research/kauth.py` loads) -- remove on the next versioned change |
| `research/idxload.py:33` | cache dir under Windows TEMP | analysis only; point at the drive |
| `research/pinrun.py:~975` | `ctypes.windll` process check | already guarded by `os.name == "nt"`; POSIX branch exists |
| many `research/*.py` analysis files | `DATA = r"C:\kals\kalshi_data"` | analysis only; leave on the PC |

## 4. Secrets

- Copy `kalshi.pem` and `kalshi-demo.pem` by hand over the LAN (`scp`), `chmod 600`,
  owned by the service user. **Never into git.** `KEY_ID` is already in git in
  several files and is not the secret.

## 5. Clock -- this strategy lives or dies on it

- Orders are signed with a millisecond timestamp and the bot buys in the last 30
  seconds. The Pi 5 has a real-time clock but **no battery by default**, so it
  boots with the wrong time until the network syncs it.
- Bot services must start `After=time-sync.target` with `systemd-timesyncd`
  (or chrony) enabled, and refuse to start while unsynchronised.

## 6. Cutover order -- never two bots on one account

1. On the Pi: install, copy keys, run every self-test, `versioncheck.py`.
2. Run the Pi bot as a PAPER arm beside the PC's paper mirror for several closes;
   decisions should match second for second.
3. Collector: run the Pi's alongside the PC's for a while (read-only, safe), then
   stop the PC's.
4. **Bot: stop the PC watchdog, then the PC bot, confirm zero `pinrun --live` on
   the PC, THEN start the Pi's.** Never the other way round.
5. Only after Kalshi has lifted the trading block.

## 7. Updating the Pi later

Over the network, no cables: `git pull` on the Pi, run the self-tests, restart the
service. The same VERSIONS.md rule applies to every live change.
