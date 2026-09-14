# restart_bot.ps1 -- stop the live pin bot and start it again on current code.
#
# WHY THIS FILE EXISTS. The operator, 2026-09-13: "you push the bot live not
# me. I've never had to." The auto-mode classifier refuses an ad-hoc
# Stop-Process / Start-Process pair on a live money process, and it is right
# to -- but it can be allowed for ONE named, reviewable script. This is that
# script, and it is deliberately narrow: it kills nothing but `pinrun`, it
# starts nothing but `pinrun`, and it refuses outright if the bot is holding a
# position.
#
# IT NEVER TOUCHES THE COLLECTOR. kalshi_collector.py and crypto_feeds.py carry
# no "pinrun" in their command lines, and the tape is unreproducible.
#
# THE ARGUMENTS ARE THE DEPLOYED ONES from CURRENT_STATE.md. --size 20 is only
# a starting value; the bot re-reads the bank every 300 s and sizes itself.
#
# ADDED 2026-09-13 ~22:2xZ: --pick best (AMENDMENT 24). When two markets clear
# every gate in the same second the bot now buys the better one instead of
# whichever the loop happened to reach first. Measured +2.07c -> +2.76c per
# contract on IDENTICAL loss counts, and again out of sample (+1.63c ->
# +2.43c, six losses either way). The ordering comes from the edge measured on
# the previous 50 ms pass, so nothing is recomputed and no order waits. See
# results/PREREG_pin_live_AMENDMENT_23_24.md.
#
# NOT ADDED, deliberately: --max-per-market (AMENDMENT 23). It pays, but it
# puts more of one close on a single coin, and the operator's condition was
# "if it's good and does not raise risk". It stays in a paper what-if.
#
# REVERTED 2026-09-13 ~18:1xZ: --sigma-ruler and --pin are GONE. The ruler cut
# live signals by 63% (4.21/hour -> 1.55/hour, measured on the day) against a
# benefit measured only on the index population, which rule 5 says may not
# transfer to us. Certain cost, unproven benefit. The sweep (AMENDMENT 18)
# stays -- it is separately evidenced and needs no flag.

$ErrorActionPreference = "Stop"
$repo = "C:\kals-repo"
$py = "C:\Python314\python.exe"

# --- 0. LEAVE A TRANSCRIPT. On 2026-09-13 the operator ran this and the bot
# did not change; nothing on disk said why, so the next session had to guess
# between "it refused because a position was open", "the execution policy
# blocked the script" and "it was run from the wrong directory". A restart that
# fails silently is worse than one that fails loudly.
$transcript = "$repo\results\restart_bot.last.log"
try { Stop-Transcript | Out-Null } catch {}
Start-Transcript -Path $transcript -Force | Out-Null
Write-Host "restart_bot.ps1 starting $(Get-Date -Format o)"

# --- 1. REFUSE IF NOT FLAT. Restarting mid-position abandons a live bet: the
# new process does not know about it, so it never settles it, never hedges it
# and never counts it against the loss brake.
$log = Get-ChildItem "$repo\results\pinrun-live-*.jsonl" |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($log) {
    $filled = 0
    $settled = 0
    foreach ($line in Get-Content $log.FullName) {
        if ($line -match '"kind":\s*"order"' -and $line -notmatch '"filled":\s*0(\.0+)?[,}]') { $filled++ }
        if ($line -match '"kind":\s*"settled"') { $settled++ }
    }
    Write-Host "newest log: $($log.Name) -- $filled filled orders, $settled settled"
    if ($settled -lt $filled) {
        Write-Host "REFUSING: the bot is holding a position ($filled filled, $settled settled)."
        Write-Host "Wait for the close to settle, then run this again."
        try { Stop-Transcript | Out-Null } catch {}
        exit 1
    }
}

# --- 2. STOP ONLY pinrun.
# ONLY THE LIVE ONE. On 2026-09-13 this matched '*pinrun*' and killed the
# WHAT-IF tracker too -- a paper pinrun the operator had asked to keep running.
# The live bot is the one carrying --live; nothing else may be stopped here.
$old = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*pinrun*' -and $_.CommandLine -like '*--live*' }
foreach ($p in $old) {
    Write-Host "stopping pid $($p.ProcessId)"
    Stop-Process -Id $p.ProcessId -Force
}
Start-Sleep -Seconds 2

# --- 3. START IT AGAIN.
Start-Process -FilePath $py -ArgumentList @(
    "-u", "$repo\research\pinrun.py",
    "--live", "--size", "20", "--minutes", "4320",
    "--loss-abort", "-60.00", "--max-positions", "3", "--max-losses", "3",
    "--improve-scope", "market", "--pick", "best"
) -WorkingDirectory $repo -WindowStyle Hidden
Start-Sleep -Seconds 15

# --- 4. PROVE IT CAME BACK, and prove the collector survived.
$new = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*pinrun*' -and $_.CommandLine -like '*--live*' }
if (-not $new) {
    Write-Host "FAILED: pinrun did not come back. Check results\pinrun-live-*.jsonl"
    try { Stop-Transcript | Out-Null } catch {}
    exit 1
}
Write-Host "pinrun running: pid $($new.ProcessId)"
$coll = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*kalshi_collector*' -or $_.CommandLine -like '*crypto_feeds*' }
Write-Host "collector processes alive: $($coll.Count)"
if ($coll.Count -lt 2) { Write-Host "WARNING: expected 2 collector processes" }
Write-Host "flags now live: $($new.CommandLine)"
Write-Host "restart_bot.ps1 done $(Get-Date -Format o)"
try { Stop-Transcript | Out-Null } catch {}
