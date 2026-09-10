# RESTART CARD — how to start the trader yourself

## Is it running?

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object {$_.CommandLine -like '*pinrun*'} | Select-Object ProcessId
```

Nothing returned = it is stopped.

## Start it

Paste this one line into PowerShell:

```powershell
Start-Process -FilePath "C:\Python314\python.exe" -ArgumentList '-u','C:\kals-repo\research\pinrun.py','--live','--size','20','--minutes','4320','--loss-abort','-60.00','--max-positions','3','--max-losses','3' -WorkingDirectory 'C:\kals-repo' -RedirectStandardOutput "C:\kals-repo\results\pinrun-manual.log" -RedirectStandardError "C:\kals-repo\results\pinrun-manual.log.err" -WindowStyle Hidden
```

Wait 20 seconds, then check it is alive with the command above. If nothing is
listed, the reason is in `C:\kals-repo\results\pinrun-manual.log.err`.

## Stop it

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object {$_.CommandLine -like '*research*pinrun*'} |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

**Never kill `python.exe` broadly.** The `*research*pinrun*` filter spares the
two data collectors, which must keep running.

## Watch it

```powershell
Get-Content (Get-ChildItem C:\kals-repo\results\pinrun-live-*.jsonl |
  Sort-Object LastWriteTime | Select-Object -Last 1).FullName -Tail 20
```

---

## SILENCE OVERNIGHT IS NORMAL

Kalshi halts **all** trading for maintenance until about **5am ET (09:00Z)**.
During it the log gets no new lines at all. Check before assuming a hang:

```powershell
python -c "import sys; sys.path.insert(0, r'C:\Users\Joe\AppData\Local\Temp\kals-work'); from kauth import get; print(get('/exchange/status', auth=False)[1]['trading_active'])"
```

`False` = maintenance, leave it alone. `True` with a silent log = look closer.

---

## IT STOPS ITSELF ON PURPOSE. Check which before restarting.

Search the newest log for `"kind": "halt"`. Four brakes can fire:

| halt says | meaning | what to do |
|---|---|---|
| `loss COUNT brake` | **3 losing CLOSES** | **Do not just restart it.** This is the one that means "re-measure before trading". |
| `loss abort` | −$60 realised | Same. Something is wrong. |
| `stake cap` | $130 committed | Restart is fine; it clears on start. |
| `errors on the ORDER path` | orders being refused | Check the `error` lines in the log first. |

**If it halted on the loss-count brake, leave it off.** That brake exists so a
human looks before more money moves.

---

## What it is running

| | |
|---|---|
| size | 20 contracts, up to 2 buys per close |
| price ceiling | **98.0¢** — never pays more |
| confidence gate | **0.995** since 2026-09-10 (was 0.98) — needs 2.58 sd, not 2.05 |
| dump guard | since 2026-09-10 23:38Z: refuses a ≥99.9% "certainty" offered more than 5¢ below fair — that is someone else's information |
| window | last 3–30 seconds before a close |
| brakes | −$60 · 3 losing closes · 2 order errors · 8 attempts/close |
| runs for | 3 days, then exits cleanly |

## Sanity checks

Money is on the **Crypto shard** (exchange_index 2). If a balance appears on
index 0 it **cannot buy anything** — that needs a transfer, and the working call
is documented in `results/OVERNIGHT.md`.

Both collectors must stay alive:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object {$_.CommandLine -like '*kalshi_collector*' -or $_.CommandLine -like '*crypto_feeds*'} |
  Select-Object ProcessId
```

Two results expected. Free disk must stay above 6 GB or data collection stops.

## Where things are written down

- `results/SKIM.md` — current state, what is settled, what is open. **Start here.**
- `results/LOSS_PLAN.md` — what happens after a loss, written before the first one.
- `results/VERSIONS.md` — every change with evidence and how to revert it.
