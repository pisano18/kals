# GUARDIAN.md -- the fixed runbook for when nobody technical is around

Written 2026-09-24, 9:55 PM ET. For a scheduled Claude Code session on the
laptop, or the operator on his phone. Plain language. Short lines. Every
number here is already in the code or in `results/VERSIONS.md`, and says
where.

**The one rule above all others: the guardian keeps things running the way
they already are. It never makes them different.** If a decision is not in
the table below, the answer is: do nothing, message the operator, wait.

---

## 0. What the guardian may and may not do

MAY, on its own:
- Run `boot_all.ps1` (starts anything missing; never starts the money bot
  directly -- it starts the watchdog, which does).
- Run `restart_bot.ps1` (the ONLY launcher of the money bot; it refuses
  while a bet is held and never starts two bots).
- PAUSE the bot: the app's own pause path, which writes the stand-down
  flag `results\pinrun-live.stop`, waits for open bets to settle, then
  stops the bot. Nothing restarts it until the flag is deleted.
- Message the operator (Telegram, or the templates in section 3).
- Read anything. Write the weekly review (section 4). Commit `results/`
  files it wrote (never `git pull --rebase`; a failed rebase once reverted
  the live pid file and 40 logs).

NEVER, whatever the reason:
- Change any flag, size, or price in `restart_bot.ps1`, `sync_arms.ps1`,
  or `boot_all.ps1`. Not `--bank-brake`, not `--series-size`, not
  `--loss-cap`. Not even back to an older value.
- Edit any `.py` or `.ps1` file.
- Re-base the drawdown mark: never write `results\pinrun-hwm.reset`, never
  edit `results\pinrun-hwm.json`, never call the app's START or the phone's
  `/start` after a DRAWDOWN halt (both re-base the mark: `pindesk.do_start`
  -> `arm_hwm_reset`, VERSIONS v-hwm-reset).
- Place, amend, or cancel an order. No `ordercli.py`, no `cmdlive.py`, no
  `pinracearm.py --live`, no `--live` anything except through
  `restart_bot.ps1`.
- Touch `C:\kals\kalshi_data` or `C:\kals\feed_data`, or stop
  `kalshi_collector.py` / `crypto_feeds.py`. The tape cannot be recreated.
- Kill `python.exe` broadly. Filter on `*research*` or a pid file.
- Delete anything under `results\`, or edit `pinrun-dayloss.json`
  (it is the $200-a-day cap's memory; 09-19 lost $223 through 13 fresh
  runs before it existed).
- Turn the oil bot back on (`boot_all.ps1` holds it behind `$false`).

---

## 1. The daily check, in this order

Run from a PowerShell prompt in `C:\kals-repo`. Expected values are next to
each. Phone equivalents in brackets. Do the whole list before deciding
anything; one bad line is usually explained by a later one.

**1. The money bot is alive and its log is fresh.**
```
python research\pinflat.py
Get-ChildItem results\pinrun-live-*.jsonl | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | ForEach-Object { "{0}  written {1:N0} s ago" -f $_.Name, ((Get-Date) - $_.LastWriteTime).TotalSeconds }
"watchdog heartbeat {0:N0} s ago" -f ((Get-Date) - (Get-Item results\watch_bot.heartbeat).LastWriteTime).TotalSeconds
```
Expect: `FLAT -- every fill has settled (pid N, ...)` or a list of open
bets; log written under 25 min ago (the watchdog restarts a bot silent 25
min, `watch_bot.ps1 -StaleMin 25`); heartbeat under 120 s (the app calls
the watchdog NOT RUNNING past 120 s, `pindesk.py _status_of`).
[Phone: `/status` -- first line TRADING, "Watchdog ok".]

**2. The recorders are writing.**
```
Get-ChildItem C:\kals\kalshi_data\cfbenchmarks_value | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | ForEach-Object { "Kalshi index file {0}, written {1:N0} s ago" -f $_.Name, ((Get-Date) - $_.LastWriteTime).TotalSeconds }
Get-ChildItem C:\kals\feed_data -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | ForEach-Object { "exchange feed written {0:N0} s ago" -f ((Get-Date) - $_.LastWriteTime).TotalSeconds }
```
Expect: both under 300 s. Five minutes silent is "deaf" (`pindesk.py
REC_FRESH_S = 300`); `boot_all.ps1` kills a recorder silent 15 min and
`run_all.ps1` starts a fresh one within 5 min.
[Phone: `/status` -- "Recorders both writing".]

**3. The settlement index is fresh.** The first command in step 2 IS the
index (the 1-per-second settlement feed everything depends on). If that
file is fresh but the bot reads BLIND (step 1's phone line, or the app),
the bot's own connection is the problem, not Kalshi's -- see the table.

**4. Bank against the halt line.**
```
Get-Content results\pinrun-hwm.json
Get-Content results\pinrun-live-size.json
Get-Content results\pinrun-dayloss.json
```
Halt line = 0.80 x the `hwm` number (`MAX_DRAWDOWN = 0.20`, pinrun.py
line 2257). Headroom = `bank` minus the line. Today: mark $1,037.33, line
$829.86, bank $1,012.04, headroom $182. `pinrun-dayloss.json` is today's
ET realised money; the bot stops the day at -$200 (`--loss-cap 200`).
[Phone: `/stats` -- "bank and halt headroom".]

**5. Yesterday's money, from Kalshi's books, not our logs.**
```
python research\pinledger.py --days 3
```
Expect a table by ET day: markets, made, losses. Cross-check with
`python research\pinday.py --days 2` (its "NOT IN LOGS" lines are markets
our logs missed; the money column is Kalshi's and is the one to quote).
[Phone: `/yesterday`, or wait for the automatic YESTERDAY message at
8 AM ET.]

**6. Disk.**
```
"{0:N1} GB free" -f ((Get-PSDrive C).Free / 1GB)
```
Lines: **8 GB** = warn every day (this runbook); **6 GB** = stop all
analysis (CLAUDE.md); **5 GB** = `run_all.ps1` line 41 stops both
recorders for good. Today 16.4 GB, falling ~4 GB a day.

**7. Memory.**
```
"{0:N1} GB RAM free" -f ((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB)
```
Under 3 GB free the harness has had its own shells killed three times
(HANDOFF 09-24 09:2xZ). Under 3 GB: start nothing new, message.
Today 2.2 GB free.

**8. The phone bot and the ledger refresher are alive.**
```
"phone heartbeat {0:N0} s ago" -f ((Get-Date) - (Get-Item results\pinphone.heartbeat).LastWriteTime).TotalSeconds
"ledger refresher {0:N0} s ago" -f ((Get-Date) - (Get-Item results\pinledgerd.heartbeat).LastWriteTime).TotalSeconds
```
Expect both under 5 min (the phone bot polls every ~25 s, the refresher
every 60 s). If either is old, `boot_all.ps1` restarts it (section 2).
Do NOT count processes by command line containing `pinphone.py` -- the
query matches its own shell (HANDOFF 09-24).

**9. The coin race penny bot (real money, 5 contracts a leg).**
```
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*pinracearm.py*--live*' } | Select-Object ProcessId
Select-String -Path results\pinracepenny-live.jsonl -Pattern '"live_halt"' | Select-Object -Last 1
```
Expect one pid and no `live_halt` line. A `live_halt` line means its
stop-on-first-loss rail fired (`pinracearm.py loss_halt`). Nothing
restarts it -- `boot_all.ps1` starts only the paper race arms.

**10. Versions match.**
```
python research\versioncheck.py
```
Expect `versioncheck: clean`. Anything else is a hard-stop condition
(section 5).

Then send the DAILY message (section 3), every day, even when all is well.

---

## 2. The decision table

"Restart" always means: `powershell -ExecutionPolicy Bypass -File
C:\kals-repo\boot_all.ps1` first (it brings back the watchdog, recorders,
phone, refresher), then -- only if the bot is still down 5 minutes later
and its last halt is NOT a DRAWDOWN halt -- `powershell -ExecutionPolicy
Bypass -File C:\kals-repo\restart_bot.ps1`.

"PAUSE" always means, from `C:\kals-repo`:
```
python -c "import sys; sys.path.insert(0, r'C:\kals-repo\research'); import pindesk; pindesk.do_pause(print, print)"
```
(the app's own PAUSE: writes `results\pinrun-live.stop`, waits for open
bets to settle, stops the bot; the watchdog holds while the flag exists).
[Phone: `/pause`.] Resuming is the operator's: he deletes the flag or
sends `/start`.

| state | how you know | on its own, the guardian may | never |
|---|---|---|---|
| **bot dead** (crash, or `end` record) | step 1: pinflat says not running; app DOWN | Wait 15 min: `watch_bot.ps1` restarts it in 30 s, 4 tries per 15 min, then every 3 min forever. Still down after 15 min: restart (above). Message BOT DOWN. | Do not touch a bot that is PAUSING (open bets, flag set). |
| **bot BLIND** (alive, cannot reach Kalshi: 5 failed checks in 10 min, none good -- `pindesk.py BLIND_MIN_BAD 5 / BLIND_WIN_S 600`) | app/phone says BLIND; STATE CHANGED alert | Check step 2. If the Kalshi recorder is ALSO silent: it is the connection -- wait, message after 30 min, do not restart (it will not help). If the recorder is writing: restart once. Message BLIND. | Never more than one restart an hour for BLIND. |
| **recorder SILENT** (5 min, `REC_FRESH_S 300`) | RECORDER SILENT alert; step 2 | Run `boot_all.ps1` (after 15 min it kills a stuck recorder; `run_all.ps1` starts a fresh one within 5 min). Message if still silent after 30 min. Silent over 6 h: section 5. | Never stop or start a recorder by hand. Never touch the tape folders. |
| **DRAWDOWN halt** (bank 20% under its high mark) | app "HALTED: 20% drawdown"; watchdog log "NOT restarting" | Nothing. Message DRAWDOWN. The watchdog holds it until the operator presses START (app or `/start`), which re-bases the mark (VERSIONS v-hwm-reset). | Never write `pinrun-hwm.reset`, never edit `pinrun-hwm.json`, never `/start`. Two in one week: section 5. |
| **day-cap halt** ("DAY loss cap: $-200 lost today") | halt record in the newest log; `pinrun-dayloss.json` at or under -200 | Nothing. Read the code, not memory -- this halt has never fired live: its words do not match the watchdog's money-brake pattern (`watch_bot.ps1 IsMoneyBrake`), so the watchdog restarts it at once, the bot halts again on its first loop (`risk_abort`, A79), and that repeats -- 4 times in 15 min, then every 3 min -- until midnight ET. The app shows NOT RUNNING, not SAFETY BRAKE, and the phone will flip DOWN/TRADING. That is the cap working. Message DAY CAP once. | Never edit `pinrun-dayloss.json`. Never PAUSE it to stop the flipping. |
| **loss COUNT brake** (2 losing bets in one run, `--max-losses 2`) | halt record "loss COUNT brake" | Nothing. The watchdog restarts it after 15 min (`-BrakeCooldownMin 15`) with a fresh count. Message only if it fires 3 times in a day. | |
| **three losing markets in one ET day** (Kalshi's ledger, step 5) | `pinledger.py`: losses >= 3 today | PAUSE at the next flat moment. Message THREE LOSSES. Wait for the operator's word. (The operator's own rule was "1/5 of bank or 3 losses, whichever first", pinrun.py A30.) | Never resume on your own. |
| **disk under 8 GB** | step 6 | Message DISK every day. Under 6 GB: message every check and PAUSE the bot at the next flat moment -- at ~4 GB a day the disk is a day from full, and a bot that dies with the disk full holds bets it cannot hedge. | Never delete tape. Never delete anything under `results\`. |
| **an hourly-BTC loss** (a KXBTCD market with a loss on the ledger) | step 5 / LOSS alert naming KXBTCD | At 1 contract a loss is about -$1: message HOURLY LOSS, nothing else. More than 2 contracts on any KXBTCD row (the `--series-size 1 / --max-per-market 2` cap failed, VERSIONS v-btcd1): section 5. | Never change `--series-size`. |
| **coin-race stop rail fired** (`live_halt` in `pinracepenny-live.jsonl`) | step 9 | Message COIN RACE STOPPED. Leave it stopped. | Never relaunch it: real money, per-instance sign-off (CLAUDE.md hard rule 1). |
| **Windows rebooted** | uptime short; everything down; `boot_all.log` has a fresh "starting" burst | If logged in: run `boot_all.ps1`; it brings back recorders, watchdog (which restarts the bot unless the stop flag exists), phone, refresher, paper arms. Message REBOOT with what came back. Not restarted by anyone: `arm-afternoon`, `wxwatch`, `quakewatch` (read-only, leave them), and the coin race penny bot (real money, leave it). | Never re-create the penny bot. Never clear a stop flag the operator set. |
| **phone bot dead** | step 8 | `boot_all.ps1`. | |
| **KalsBoot not running** (`Get-ScheduledTask KalsBoot` not Running) | | `boot_all.ps1` by hand, then message: nothing auto-starts until it is fixed. | Never re-register the task with different settings. |

---

## 3. Message templates

All times ET. Money from Kalshi's ledger. Send the daily one every day;
the others when the state changes, once, not repeatedly.

**DAILY**
```
OK <day> <time> ET.
Bot: TRADING (pid <n>), last wrote <s> s ago. Watchdog ok.
Recorders: both writing. Index file <s> s old.
Bank $<b>, size <n>. Halt line $<l> (headroom $<b-l>). Today so far $<d>.
Yesterday: $<y>, <n> markets, <k> losses.
Disk <g> GB free (recorders stop at 5). RAM <r> GB free.
Phone bot ok. Ledger refresher ok. Coin race bot alive. Versions clean.
Nothing needed from you.
```

**BOT DOWN**
```
BOT DOWN since <time> ET (<why, from the last halt/end record, in plain words>).
Watchdog tried <n> restarts. I ran boot_all / restart_bot at <time>: <back up pid N | still down>.
No open bets were left behind (pinflat: FLAT).   [or: <n> open bets, closing <time>]
You: nothing, unless it is still down at the next daily message.
```

**BLIND**
```
BOT BLIND since <time> ET: alive but cannot reach Kalshi.
Kalshi recorder is <also silent -> it is the connection | writing -> it is the bot; restarted once at <time>>.
You: nothing yet. If this lasts 2 hours the internet or Kalshi is down; check the laptop's Wi-Fi if you can.
```

**DRAWDOWN -- needs you**
```
HALTED: bank $<b> is 20% under its high of $<h>. The bot is stopped and will stay stopped.
Today $<d>, yesterday $<y>. Losses this week: <list, market and dollars>.
I will NOT restart it. Only you can: /start re-bases the mark to today's bank and resumes.
Before you do: is this a real loss or a withdrawal? (A withdrawal looks identical to the bot.)
```

**DAY CAP**
```
The bot lost $200 today (<n> markets: <list>) and stopped for the day at <time> ET.
Until midnight ET the watchdog will restart it every few minutes and it will stop again each time -- expect DOWN/TRADING messages; that is the cap holding. Nothing needed.
```

**THREE LOSSES -- paused**
```
Three losing markets today (<list with dollars>). I PAUSED the bot at <time> ET after its open bets settled.
It stays paused until you say. Reply /start to resume, or tell me to wait.
```

**DISK**
```
DISK: <g> GB free, falling ~4 GB a day. The recorders stop themselves at 5 GB (about <d> days).
[Under 6 GB:] I paused the bot at <time> ET; the tape is about to stop and the bot cannot log safely.
You: plug in the drive / free space. I cannot delete anything.
```

**HOURLY LOSS**
```
Hourly BTC lost $<x> on <market> (<n> contracts). Cap is 1 contract, so this is the expected size. Nothing needed.
```

**COIN RACE STOPPED**
```
The coin race bot stopped itself after a losing race (<race>, $<x>) at <time> ET. It stays stopped; I will not restart it.
```

**REBOOT**
```
The laptop restarted at <time> ET. boot_all brought back: <list>. Not back (by rule): coin race bot, arm-afternoon, wxwatch, quakewatch.
Bot: <TRADING pid n | down, watchdog retrying>.
```

**HARD STOP -- I stopped the bot**
```
I PAUSED the bot at <time> ET and will not restart it. Reason: <one of section 5, with the number>.
Open bets: none / <list>. Bank $<b>.
It stays stopped until you reply. Nothing else was changed.
```

---

## 4. The weekly review

Every Sunday by 10 AM ET (or the first daily check after). Read-only
except the file it writes. From `C:\kals-repo`:

```
python research\pinledger.py --days 8          > results\GUARDIAN_WEEKLY_<YYYY-MM-DD>.txt
python research\pinday.py --days 8             >> the same file
python research\barcheck.py --brief            >> the same file   (the pre-registered bars; writes results\FREEZE_status.md)
python results\cf_2026-09-24\armh2h2.py 2026-09-22T06:21:00Z   >> the same file   (paper arms vs live; valid only from that date, CURRENT_STATE)
python research\pinxfer.py --no-refresh        >> the same file   (deposits -- a bank change is not profit)
python research\versioncheck.py                >> the same file
python research\deploycheck.py                 >> the same file   (the recorder copies in C:\kals match the repo)
```
Plus the phone's `/stats` text, pasted in. Then write
`results\GUARDIAN_WEEKLY_<YYYY-MM-DD>.md`: ten lines, plain words -- money
this week and each day, losses (market, dollars, one line why from the
LOSS alert story), halts, restarts, disk, and whether any hard-stop
condition came within one event of firing. Commit that file only:
```
git add results\GUARDIAN_WEEKLY_<date>.md results\GUARDIAN_WEEKLY_<date>.txt
git commit -m "guardian: weekly review <date>"
git push          (if it is refused, leave it; never pull --rebase)
```
Send the ten lines to the operator. Do not act on any bar result -- the
bars are for him.

---

## 5. Hard stop: PAUSE the bot and wait for the operator

Any one of these: PAUSE (section 2), send HARD STOP, never restart on your
own. Each number is the existing rail; the guardian adds no new ones.

1. **Two DRAWDOWN halts in seven days.** The first is held by the watchdog
   and the operator re-based it; a second means 20% was lost twice
   (`MAX_DRAWDOWN 0.20`; watch_bot.ps1 `HaltVerdict`; v-hwm-reset).
2. **A loss over $150 on one market** on Kalshi's ledger. The largest loss
   in the bot's history is -$130.41 (VERSIONS v-nospike); $150 is outside
   everything the rules were built on.
3. **A recorder silent more than 6 hours** with `boot_all.ps1` running
   (its 15-minute deaf-kill and `run_all.ps1`'s 5-minute restart have had
   24 chances). The 09-23 recorder was deaf 6 h; a machine that has not
   healed itself in 6 h is not one to leave trading money unattended.
4. **`versioncheck.py` is not clean** -- `restart_bot.ps1` carries a flag
   VERSIONS.md does not, or with a different value. Someone or something
   changed the launcher without a version entry (CLAUDE.md standing rule).
5. **A KXBTCD settlement with more than 2 contracts.** The hourly cap is 1
   a market, 2 at most (`--series-size 1`, `--max-per-market 2`, v-btcd1).
   More means the cap failed.
6. **A crash loop:** the bot crashed (an `end` record with no halt, or a
   traceback in `results\pinrun-live.err`) more than 4 times in 15 minutes
   (the watchdog's own quick-restart limit, `-QuickRestarts 4
   -QuickWindowMin 15`) and is still crashing an hour later. A bot that
   dies every few minutes can be holding a bet it cannot hedge. A day-cap
   halt looks the same from the outside but is NOT this: its halt record
   says `DAY loss cap`, and it ends at midnight ET.

There is no RAM number in the code to stop on; the daily check's "under
3 GB free: start nothing, message" is the whole rule.

---

## 6. The operator's own checklist before leaving

Do these in this order. The first two are the ones that have already cost
days.

1. **The disk.** 16.4 GB free on 09-24 at 9:55 PM ET, falling ~4 GB a day;
   the recorders stop for good at 5 GB (`run_all.ps1` line 41), about
   **09-28**. Plug in the 2 TB drive and have the recording moved
   (OPEN_WORK C1) BEFORE anything else. Nothing on this page helps if the
   tape stops.
2. **KalsBoot must run without a login.** Measured 09-24: the Windows task
   runs `LogonType: Interactive` -- after any reboot, nothing starts until
   you sign in (CURRENT_STATE 09-22 open item). Set it to "run whether
   user is logged on or not", or turn on automatic sign-in. Then test it:
   reboot, wait 12 minutes, check `/status` from your phone.
3. **Windows Update.** The 09-15 update reboot cost 7.57 hours of trading
   (`boot_all.ps1` header). Pause updates for as long as Settings allows
   (Windows Home: up to 5 weeks) and put the resume date in your calendar;
   set active hours to the whole day so it never restarts on its own.
4. **Power and sleep.** Plugged in; sleep never; hibernate never; lid close
   = do nothing; Wi-Fi reconnect automatically. The 09-22 outage was 4 h
   47 min of lost tape from a dropped connection.
5. **Funding floor.** The bot needs the bank above its 20% halt line
   ($829.86 today against a $1,037.33 mark). Do not withdraw while away:
   a withdrawal looks exactly like a trading loss and halts the bot
   (pinrun.py A30). Decide now, from the scaling plan
   (`results/SCALING_PLAN_2026-09-24.md`), whether the bank stays at
   ~$1,000 (size 86) or goes to $1,500 (size 127); after that the
   guardian may not touch size.
6. **Kalshi access.** The signing key `C:\kals\kalshi.pem` (dated 09-15)
   and `C:\kals\keyname.txt` are what the bot uses; the repo records no
   expiry date for them. Check in Kalshi's account settings whether the
   API key or your identity verification has a date, and write both here:
   key expires ______ ; KYC/ID review ______ . Make sure you can pass
   Kalshi's two-factor prompt from wherever you will be (a phone number
   that works there, or an authenticator app). If the key dies, the bot
   cannot trade and cannot hedge.
7. **Telegram.** `C:\kals\telegram.json` (token + pairing, dated 09-17).
   Send `/status` and `/stats` before you go and confirm both answer;
   `/unmute` if you ever muted. Know the four commands you may need:
   `/status`, `/pause`, `/start` (this one re-bases the drawdown mark
   after a halt -- read the DRAWDOWN message first), `/stop yes`.
8. **A way to reach the laptop** (Remote Desktop, or Tailscale as the VM
   plan suggests). Without it the guardian and you can only do what the
   phone commands do. If you would rather not leave the laptop in charge
   for months, the cloud move is in `results/VM_PLAN_2026-09-24.md`
   ($124 a month; it removes the Wi-Fi, power, reboot and disk risks in
   one step). Decide before leaving; the guardian will not move anything.
9. **The manual processes.** `arm-afternoon`, `wxwatch`, `quakewatch`
   (read-only) and the coin race penny bot (real money, 5 contracts a
   leg) are not restarted after a reboot. Decide now whether the coin
   race bot should stay down after its first reboot (the guardian's rule)
   or be added to `boot_all.ps1` by a session while you are still here.
10. **Open tests with read dates you will miss:** the fresh-offer test
    (~10-01), hourly BTC (~30 fired closes), the earthquake watch (~10-08).
    Nobody acts on them until you are back; the guardian never changes a
    flag. That is intended.
11. **Leave the branch clean:** `git status` shows only `results\` files;
    `python research\versioncheck.py` says clean; `python
    research\deploycheck.py` says the `C:\kals` copies match.
