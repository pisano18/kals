# fx_restart.ps1 -- 2026-10-27, v-fx-stopline deploy (operator: "do whatever needs to be done with fx. do whatever is
# best"). Restarts the FX taker so it runs the new code (it stands itself down if its money since 10-26 falls below
# -$10). Launch it detached (WMI) so a dropped SSH session cannot leave it half done. Steps:
#   1. wait for minutes 2-9 of a quarter hour (FX only buys in the last 30-15 s before a close)
#   2. write results\fxtake-live.stop -> the bot places no new orders and exits once nothing is held
#   3. once it has exited: delete the stop file and run KalsBoot -> boot_all starts it again on the new code
# If the bot has not exited after 150 s it removes the stop file and leaves the old bot running. If a stop file already
# exists it does nothing at all. Log: results\fx_restart.out
$log = "C:\kals-repo\results\fx_restart.out"
$stop = "C:\kals-repo\results\fxtake-live.stop"
function Say($m) { ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $m) | Out-File $log -Append -Encoding utf8 }
function FxPids { @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*fxtake_live.py*--live*" } | ForEach-Object { $_.ProcessId }) }
Say "start; waiting for minutes 2-9 of a quarter hour"
while ($true) { $m = (Get-Date).Minute % 15; if ($m -ge 2 -and $m -le 9) { break }; Start-Sleep -Seconds 5 }
if (Test-Path $stop) { Say "a stop file already exists -- doing nothing"; exit 1 }
Say ("running fxtake pids: " + ((FxPids) -join ","))
Set-Content -Path $stop -Value "fx_restart.ps1 restart for v-fx-stopline; it removes this file itself" -Encoding utf8
Say "stop file written; waiting for the bot to exit"
$t0 = Get-Date
while ((FxPids).Count -gt 0 -and ((Get-Date) - $t0).TotalSeconds -lt 150) { Start-Sleep -Seconds 2 }
if ((FxPids).Count -gt 0) { Remove-Item $stop -Force; Say "did NOT exit in 150 s -- stop file removed, old bot left running"; exit 1 }
Say ("old bot exited after {0:N0} s" -f ((Get-Date) - $t0).TotalSeconds)
Remove-Item $stop -Force
Say "stop file removed; running KalsBoot"
schtasks /run /tn KalsBoot | Out-Null
$t0 = Get-Date
while ((FxPids).Count -eq 0 -and ((Get-Date) - $t0).TotalSeconds -lt 180) { Start-Sleep -Seconds 3 }
Say ("new fxtake pids: " + ((FxPids) -join ","))
Start-Sleep -Seconds 20
$st = Get-Content C:\kals-repo\results\fxtake-live-orders.jsonl -Tail 300 | Where-Object { $_ -match '"kind": "start"' } | Select-Object -Last 1
if ($st) { $o = $st | ConvertFrom-Json; Say ("start record: t {0} stop_line {1} line_pnl {2}" -f $o.t, $o.stop_line, $o.line_pnl) } else { Say "start record NOT FOUND" }
Say "done"
