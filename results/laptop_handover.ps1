param([switch]$DryRun)
# Hands the live bots over from this laptop to the Ohio server (2026-10-27, operator: "get the bot running so i can
# start turning my laptop off"). NEVER two live bots on one account: this stops every live bot HERE and keeps the
# laptop from ever restarting them; only after it reports ALL STOPPED does the server start its copies.
#   1. stop files for the 5 live bots (forecaster, ladder, FX taker exit on their own when they see theirs; the pin
#      bot's watchdog and the coin race refuse to start while theirs exist)
#   2. the KalsBoot scheduled task is DISABLED (nothing restarts at the next 10-minute tick or after a reboot)
#   3. C:\kals\telegram.json is renamed, so nothing on this laptop can start the phone link again
#   4. waits for a quiet moment: 4 to 11 minutes past a quarter-hour (no close near) AND pinflat says FLAT
#   5. stops what is left: the pin bot, its watchdog, the coin race, the phone link, the ledger refresher, and any
#      live bot that did not exit by itself. Paper tests and recorders are left alone (they die when the laptop is off).
#   6. checks that no live process is left and writes results\laptop_handover.log
# To undo (bring the bots back to the laptop): delete the 5 stop files, rename telegram.json back, Enable-ScheduledTask
# KalsBoot -- and only after the server's copies are stopped. Needs administrator rights: laptop_handover.cmd asks.
$res = "C:\kals-repo\results"
$py = "C:\Python314\python.exe"
Set-Location "C:\kals-repo"
try { Start-Transcript -Path "$res\laptop_handover.log" -Append | Out-Null } catch { }
function Say($m) { Write-Output ("{0}  {1}" -f (Get-Date -Format "HH:mm:ss"), $m) }
Say ("=== laptop handover{0}" -f $(if ($DryRun) { " (DRY RUN: nothing is changed)" } else { "" }))
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin -and -not $DryRun) {
    Say "NOT RUN: no administrator rights. Double-click results\laptop_handover.cmd and say Yes."
    try { Stop-Transcript | Out-Null } catch { }; exit 1
}
$live = @(
    @{ n = "forecaster";  stop = "forecaster-live.stop"; like = "*forecaster_live.py*--live*" },
    @{ n = "ladder";      stop = "ladder-live.stop";     like = "*ladder_live.py*--live*" },
    @{ n = "FX taker";    stop = "fxtake-live.stop";     like = "*fxtake_live.py*--live*" },
    @{ n = "coin race";   stop = "pinracepenny.stop";    like = "*pinracearm.py*--live*" },
    @{ n = "pin bot";     stop = "pinrun-live.stop";     like = "*pinrun.py*" }
)
$others = @(
    @{ n = "phone link";        like = "*pinphone.py*" },
    @{ n = "ledger refresher";  like = "*pinledgerd.py*" }
)
# 1. stop files
foreach ($b in $live) {
    $f = Join-Path $res $b.stop
    if (Test-Path $f) { Say "stop file already there: $($b.stop)"; continue }
    if (-not $DryRun) { [IO.File]::WriteAllText($f, "2026-10-27 MOVED TO THE OHIO SERVER by results\laptop_handover.ps1. Do not delete while the server runs this bot.`n") }
    Say "wrote stop file: $($b.stop)"
}
# 2. no more restarts on this laptop
$t = Get-ScheduledTask -TaskName "KalsBoot" -ErrorAction SilentlyContinue
if ($t) { if (-not $DryRun) { Disable-ScheduledTask -TaskName "KalsBoot" | Out-Null }; Say "KalsBoot task disabled (was $($t.State))" } else { Say "no KalsBoot task found" }
# 3. the phone link's token
if (Test-Path "C:\kals\telegram.json") {
    if (-not $DryRun) { Rename-Item "C:\kals\telegram.json" "telegram.json.moved-to-server" -Force }
    Say "renamed C:\kals\telegram.json -> telegram.json.moved-to-server"
} else { Say "C:\kals\telegram.json already moved" }
# 4. a quiet moment: 4..11 minutes past a quarter-hour, and the pin bot flat
$deadline = (Get-Date).AddMinutes(25)
while ($true) {
    $m = (Get-Date).Minute % 15
    $flat = (& $py "$PSScriptRoot\..\research\pinflat.py" 2>&1 | Select-Object -Last 1)
    $isFlat = ($LASTEXITCODE -eq 0) -and ("$flat" -like "FLAT*")
    if ($m -ge 4 -and $m -le 11 -and $isFlat) { Say "quiet moment: $m min past the quarter-hour, $flat"; break }
    if ((Get-Date) -gt $deadline) { Say "NO quiet moment within 25 minutes (last: minute $m, $flat) -- run this again; the stop files stay"; try { Stop-Transcript | Out-Null } catch { }; exit 1 }
    Say "waiting for a quiet moment (now $m min past the quarter-hour; pin: $flat)"
    if ($DryRun) { Say "DRY RUN: not waiting"; break }
    Start-Sleep -Seconds 20
}
# 5. stop what is left (the forecaster, ladder and FX taker normally exited on their own by now)
$procs = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'")
$blind = @($procs | Where-Object { -not $_.CommandLine }).Count
if ($blind) {
    Say "WARNING: $blind python process(es) hide their command line (not elevated?)"
    if (-not $DryRun) { Say "NOT DONE: cannot tell which process is which -- run laptop_handover.cmd and say Yes"; try { Stop-Transcript | Out-Null } catch { }; exit 1 }
}
foreach ($b in ($live + $others)) {
    $hits = @($procs | Where-Object { $_.CommandLine -and $_.CommandLine -like $b.like })
    if (-not $hits.Count) { Say "$($b.n): not running"; continue }
    foreach ($p in $hits) {
        if ($DryRun) { Say "DRY RUN: would stop $($b.n) (pid $($p.ProcessId))"; continue }
        try { Stop-Process -Id $p.ProcessId -Force; Say "stopped $($b.n) (pid $($p.ProcessId))" } catch { Say "could not stop $($b.n) (pid $($p.ProcessId)): $($_.Exception.Message)" }
    }
}
$wb = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object { $_.CommandLine -like "*watch_bot.ps1*" }
foreach ($p in $wb) { if ($DryRun) { Say "DRY RUN: would stop the pin bot's watchdog (pid $($p.ProcessId))" } else { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue; Say "stopped the pin bot's watchdog (pid $($p.ProcessId))" } }
# 6. check
Start-Sleep -Seconds 3
$left = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $cl = $_.CommandLine; $cl -and
          (@($live + $others) | Where-Object { $cl -like $_.like }).Count })
if ($left.Count -and -not $DryRun) {
    Say ("NOT DONE: still running: " + (($left | ForEach-Object { "pid $($_.ProcessId)" }) -join ", ") + " -- run this again")
    try { Stop-Transcript | Out-Null } catch { }; exit 1
}
Say "ALL STOPPED on the laptop. Tell Claude 'handover done' -- the server starts its copies next."
try { Stop-Transcript | Out-Null } catch { }
