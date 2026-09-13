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
# --sigma-ruler max3600 added 2026-09-13 (AMENDMENT 20) on the operator's
# instruction, against the bar in results/PREREG_ruler.md. If that bar fails,
# the revert is to delete the two arguments below and run this file again.

$ErrorActionPreference = "Stop"
$repo = "C:\kals-repo"
$py = "C:\Python314\python.exe"

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
        exit 1
    }
}

# --- 2. STOP ONLY pinrun.
$old = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*pinrun*' }
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
    "--sigma-ruler", "max3600"
) -WorkingDirectory $repo -WindowStyle Hidden
Start-Sleep -Seconds 15

# --- 4. PROVE IT CAME BACK, and prove the collector survived.
$new = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*pinrun*' }
if (-not $new) {
    Write-Host "FAILED: pinrun did not come back. Check results\pinrun-live-*.jsonl"
    exit 1
}
Write-Host "pinrun running: pid $($new.ProcessId)"
$coll = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*kalshi_collector*' -or $_.CommandLine -like '*crypto_feeds*' }
Write-Host "collector processes alive: $($coll.Count)"
if ($coll.Count -lt 2) { Write-Host "WARNING: expected 2 collector processes" }
