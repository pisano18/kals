# CURRENT_STATE.md -- read this FIRST

**As of 2026-09-25 ~07:0xZ.** If that is more than a day old, re-check the live
numbers before quoting them. All times here are UTC; say them to the operator
in ET.

**Read in this order:** this file -> the top section of `HANDOFF.md` (every
running process with pid, end date and read date) -> `OPEN_WORK.md` (the
operator's topic index; he names a topic by its "Say:" handle) ->
`results/IDEA_LEDGER.md` (every money idea ever checked -- read before
proposing one) -> `results/VERSIONS.md` (what is live, with revert commands).
Older HANDOFF sections: `HANDOFF_ARCHIVE_2026-09.md`. This file's earlier
text (the 09-21/09-22 blocks): `DOCS_ARCHIVE_2026-09.md`.

## Live money

- **15-minute crypto bot** `research/pinrun.py --live`, version **v-safety2**
  since 09:36:44Z 09-25, pid 2934836, code_sha 28f5e66b2169. Its argv is
  `restart_bot.ps1` -- the ONLY script that may start it. What it does now,
  newest change first (each has a VERSIONS entry):
  - asks Kalshi what it holds at startup and after any lost order reply, and
    books/hedges a fill it did not see; re-sends a lost hedge that did not
    fill; "0.00" orders count as zero (v-safety2; record kind `ktruth`).
    HELD for the operator: tighter pintake caps (fix 4) and the scale-in
    double buy (A23 compares against the sweep-inflated average paid);
  - never sends a 0-contract order (v-zerotake; watch the log for
    `late_add_full` / `zero_take` -- each is a halt that did not happen);
  - trades the hourly BTC ladder at 1 contract (`--series KXBTCD
    --series-size 1`, v-btcd1); code for six more hourly ladders and for 99c
    far rungs is on disk with every flag OFF (v-ladder7, v-farrung);
  - logs taker selling from Kalshi's trade feed; the `toxic_fresh` gate is OFF
    (v-tradefeed; paper arm `arm-toxic` runs it ON);
  - late same-market add at <=15 s (`--rebuy-late-tau 15 --rebuy-late-frac
    0.5`), hedge limit slip 0.10 (v-lateadd-live, v-lateadd-fix);
  - 10c edge cap only with more than 20 s left; 45 s leg at a third of size
    with a 95c floor (`--early-frac 0.333 --early-min-price 0.95`)
    (v-cap20, v-early-third);
  - spike gate; hedge the WHOLE position when belief falls to 0.40
    (`--hedge-belief 0.40 --no-hedge-prop`; A76 proportional hedging fired
    once and was removed) (v-nospike, v-hedgefull);
  - `--bank-brake 4.00` (auto-size 88 at a $1,043 bank), `--loss-cap 200`
    per ET day surviving restarts, 20% drawdown halt that HOLDS until START on
    the app re-bases it (v-hwm-reset).
  - `--minutes 4320`: exits ~09-28 06:25Z and `watch_bot.ps1` restarts it.
- **Coin race penny test** `research/pinracearm.py --live`, pid 2707284, 5
  contracts a leg (v-race5), ends ~10-01 15:16Z -- relaunch BY HAND with the
  v-race5 argv from VERSIONS.md. A tie counts as a loss for its stop rail
  (v-race-tie1).
- **Money (Kalshi's ledger, the only source to quote):** lifetime +$437.82
  over 1,101 markets at 09-25 05:49Z; ET 09-25 +$13.46 at 05:49Z. Deposits
  $584.46 net of fees in 7 deposits, **zero withdrawals ever**
  (`results/kalshi_transfers.json`, fetched 09-24 07:06Z; `research/pinxfer.py`
  is the authority). Day totals: `python research/pinday.py`.

## What else runs

- Control: `watch_bot.ps1` (pid 2839244) restarts the bot; the **Pin Bot**
  desktop app (`research/pindesk.py`, Start/Pause/Stop; `results/pinrun-live.stop`
  present = he stood it down); the phone bot (`research/pinphone.py`: /stats,
  /bars, /race). `boot_all.ps1` (task KalsBoot) starts everything at LOGON
  only -- after a reboot nothing restarts until the operator signs in.
  **Windows Update may no longer reboot while he is signed in** (set 09-25
  ~08:55Z with his OK: HKLM Policies WindowsUpdate AU
  NoAutoRebootWithLoggedOnUsers = 1; active hours 06-23). Revert:
  `reg delete "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v NoAutoRebootWithLoggedOnUsers /f`
  (from Git Bash set `MSYS_NO_PATHCONV=1` first).
- Recorders: `kalshi_collector.py` + `crypto_feeds.py` under
  `C:\kals\run_all.ps1`. Never touch them or `C:\kals\kalshi_data` /
  `feed_data`.
- Paper arms, watchers (wxwatch, quakewatch, rungwatch), the Polymarket US
  recorder and the money-idea sweep: table at the top of `HANDOFF.md`.
  Arm-vs-live comparisons are valid only from 2026-09-22 06:21Z; every arm
  number from before 2026-09-20 is void.

## Disk -- the deadline that stops everything

**~17 GB free at 08:5xZ 09-25** after the session purged the pip cache
(5.8 GB), npm cache (0.7 GB) and five merged workflow worktrees (1.9 GB).
**MEASURED rate: the recorders write ~5.0 GB/day** (kalshi_data ~198 MB a
normal hour; disk-triage agent 09-25), plus Claude's own
`Temp\claude\bash-edit-diff` while agents run (~0.4 GB/h). The operator is
deleting a game ~11:00Z 09-25 and gets a drive ~23:00Z 09-25. Still
reclaimable with his OK: restore points 9.7 GB (`vssadmin delete shadows`),
hiberfil 6.8 GB (`powercfg /h off`). `run_all.ps1` STOPS both recorders for good
at **5 GB** (its line 41); our guard is **6 GB**: below it, stop all analysis
and say so loudly. The tape cannot be recreated. **The 2 TB external drive is
NOT bought yet** (OPEN_WORK C1). The daily rate is NOT settled -- docs quote
~1, ~3 and ~4 GB/day, and the free space also moves with workflow worktrees
(`.claude/worktrees` was 1.9 GB at 07:0xZ) -- measure before quoting a date.

## Decided -- do not re-open without new data

- Far rungs of the hourly ladder at 99c: dead (no safe-side supply,
  `results/FAR_RUNG_2026-09-25.md`).
- Market making on 15-min crypto: dead (`results/MAKER_SIM_2026-09-24.md` s9).
- Exchange-feed "moved against us" gate: dead on our fills
  (`results/FEED_LEAD_2026-09-24.md`).
- The 09-24 per-second rebuild list (half size then top-up, every other hedge
  trigger, 90c floor at 21-30 s, confidence tightening, 2.0x late boost, ...):
  top of `HANDOFF.md`, 09-24 section, "Measured and NOT changed".
- Everything in `results/IDEA_LEDGER.md` marked dead, and the kills in
  `results/SECOND_INCOME_SCAN_2026-09-25.md`.
- Polymarket US offers the operator ONLY BTC 15-min and 1-hour; funded ~$60,
  eligible. Recorder decides whether it is worth anything (OPEN_WORK A11).
- A tape or replay number is never OUR loss rate (CLAUDE.md amendment
  2026-09-10).

## Open

1. Money-idea sweep `wf_a10c880e-f3b`: its writer did not know the ledger --
   merge `results/IDEA_SWEEP_2026-09-25.md` rows into `results/IDEA_LEDGER.md`
   by hand; add survivors to OPEN_WORK with a "Say:" handle.
2. `results/rungwatch.stop`: create after the 09-25 ~23:00Z close.
3. Polymarket recorder read ~09-28 06:11Z (OPEN_WORK A11).
4. Arm bars ~10-01/02 (`python research/bars.py`; fresh500, toxic, btcd,
   edge2c, lateadd-off, hourly-all). `bars.py` counts KXBTCD only.
5. Known bugs, not fixed: same-second double sends can build 2-2.7x SIZE
   (`--one-coin-max` exists, not in the argv, unmeasured);
   `classify_bank_move` still infers transfers from balance moves (make it
   consult `pinxfer`); the seven-coin ladder adds ~1.4 s to each universe
   refresh (a hedge blackout if ever taken live).
6. Operator: buy the drive; enable Windows automatic sign-in; AWS Lightsail
   Ohio after a good weekend (`results/VM_PLAN_2026-09-24.md`); two doc
   contradictions only he can settle (CLAUDE.md, "Open questions for the
   operator").

## The operator -- context that changes decisions

- On 09-19 he put in $370 of two weeks' spending money. **This is money he
  needs**: at the margin, favour lower variance over expected value.
- **Do restarts yourself** (`restart_bot.ps1` through the Bash tool; the
  PowerShell tool is refused for it). Ask before moving a risk limit he set
  (`--loss-cap`), and before a new strategy family or size step goes live.
- He is usually right when he pushes back, and hates blind agreement: re-derive,
  then argue with evidence either way.
- His ideas are suggestions to measure; ship only what measures positive
  (memory `measure-then-ship-only-positive`).

## Traps that have already cost real time

- A self-test asserting a RUNNING value refuses to start the bot under a new
  flag: assert `_DEFAULT_*`, and run the startup path in paper with the live
  flags before any live restart.
- A source-text self-test finds its own copy of the string (anchor on the whole
  line, or `rindex`), and cannot see a block-nesting change: every gate needs a
  driven world that refuses. Code inserted between `sig["take_n"] = take_n` and
  the early-leg gates re-parents them (bitten twice on 09-24).
- Nothing may ever gate a hedge. Before shipping a gate, write down what it
  BLOCKS.
- Money: never quote a bank delta without subtracting deposits; never sum
  `realised` (running total, resets on restart; per-market is `pnl_c`); a
  hedged market writes TWO settled rows; the bot's own logs miss markets held
  when a run died -- use the ledger.
- `sync_arms.ps1 -Only` disables the stale sweep (without that it retires every
  arm outside the narrowed plan).
- A `-like '*x.py*'` process query matches the querying shell: filter
  `Name='python.exe'`. Never kill `python.exe` broadly.
- The Bash tool's heredoc halves backslashes: write scripts with Write.
- Never `git pull --rebase` / stash / `reset --hard` while bots run
  (tracked live-state files revert); fetch + merge only.
- The harness kills its own background shells when free RAM nears 1 GB; keep
  the arm fleet under ~15 and detach anything that must survive.
- Check weekdays with a calendar (2026-09-13 was a Sunday).
- Thursday ~07Z Kalshi maintenance: the phone says BLIND ~03:05 ET; expected.
