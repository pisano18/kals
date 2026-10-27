# laptop_idle.ps1 -- 2026-10-27, operator: "The laptop shouldn't be doing anything though. I thought we fully migrated
# everything to the server." Every live bot and the phone link run on the Ohio server since 10-27 00:20 ET. This stops
# the laptop's leftover RESEARCH processes that the old KalsBoot task started with administrator rights (so only an
# elevated shell can stop them):
#   run_all.ps1            the recorders' watchdog (would restart the two recorders below within 5 minutes)
#   kalshi_collector.py    the coin-market tape (C:\kals\kalshi_data); no open read needs it
#   crypto_feeds.py        the exchange price tape (C:\kals\feed_data); no open read needs it
#   cdc_record.py          the Crypto.com recorder, retired 10-26 (nothing reads cdc_data) but never stopped
#   locked_average_ladder_re_paper.py   a second copy of the ladder paper test; the server runs the real one (pid 4600)
# Nothing here places orders. Never touches a command line containing --live. KalsBoot stays DISABLED, so nothing
# restarts them. To bring the recorders back: run C:\kals\run_all.ps1 from an elevated PowerShell.
$ErrorActionPreference = "Continue"
$patterns = @("*run_all.ps1*", "*kalshi_collector.py*", "*crypto_feeds.py*", "*cdc_record.py*", "*locked_average_ladder_re_paper.py*")
$hits = @()
foreach ($p in Get-CimInstance Win32_Process) {
    if (($p.Name -ne "python.exe") -and ($p.Name -ne "powershell.exe")) { continue }
    $c = [string]$p.CommandLine
    if (-not $c -or $c -like "*--live*") { continue }
    foreach ($pat in $patterns) { if ($c -like $pat) { $hits += $p; break } }
}
# the watchdog first, so it cannot restart the recorders
$hits = @($hits | Sort-Object { if ($_.Name -eq "powershell.exe") { 0 } else { 1 } })
if ($hits.Count -eq 0) { Write-Host "Nothing to stop: none of the leftover research processes is running." }
foreach ($p in $hits) {
    $c = [string]$p.CommandLine
    try {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
        Write-Host ("stopped {0} {1}  {2}" -f $p.ProcessId, $p.Name, $c.Substring(0, [Math]::Min(110, $c.Length)))
    } catch {
        Write-Host ("COULD NOT stop {0}: {1}" -f $p.ProcessId, $_.Exception.Message)
    }
}
Start-Sleep -Seconds 3
$left = @()
foreach ($p in Get-CimInstance Win32_Process -Filter "Name='python.exe'") { $left += ("{0}  {1}" -f $p.ProcessId, ([string]$p.CommandLine).Substring(0, [Math]::Min(120, ([string]$p.CommandLine).Length))) }
Write-Host ""
Write-Host "Python processes still running on this laptop:"
if ($left.Count -eq 0) { Write-Host "  none" } else { $left | ForEach-Object { Write-Host "  $_" } }
Write-Host ""
Write-Host "Done. The bots are on the server; this laptop can be switched off any time."
