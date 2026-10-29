# ladder_restart.ps1 -- 2026-10-29 (LS26, operator: "Should we increase the ladder bet size so 3 trades makes a 1% return").
# Restarts the ladder so it picks up boot_all's new argv (run results\ladder_argv_commit82.ps1 FIRST: it adds
# --commit-frac 0.82 and sets --big-coins-above 7000). Launch it detached (WMI) so a dropped SSH session cannot
# leave it half done. Steps:
#   1. wait for minutes 2-9 of a quarter hour (the ladder only rests bids in the last ~30 s before a close)
#   2. write results\ladder-live.stop -> the bot places nothing new and exits
#   3. once it has exited: delete the stop file and run KalsBoot -> boot_all starts it again with the new argv
# If the bot has not exited after 150 s it removes the stop file and leaves the old bot running. If a stop file already
# exists it does nothing at all. Log: results\ladder_restart.out
$log = "C:\kals-repo\results\ladder_restart.out"
$stop = "C:\kals-repo\results\ladder-live.stop"
function Say($m) { ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $m) | Out-File $log -Append -Encoding utf8 }
function LadPids { @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*ladder_live.py*--live*" } | ForEach-Object { $_.ProcessId }) }
Say "start; waiting for minutes 2-9 of a quarter hour"
while ($true) { $m = (Get-Date).Minute % 15; if ($m -ge 2 -and $m -le 9) { break }; Start-Sleep -Seconds 5 }
if (Test-Path $stop) { Say "a stop file already exists -- doing nothing"; exit 1 }
$argv = (Select-String -Path C:\kals-repo\boot_all.ps1 -Pattern 'ladder_live.py", "--subaccount"').Line
if ($argv -notlike '*--commit-frac*') { Say "boot_all's ladder line has no --commit-frac yet -- run ladder_argv_commit82.ps1 first; doing nothing"; exit 1 }
Say ("running ladder pids: " + ((LadPids) -join ","))
Set-Content -Path $stop -Value "ladder_restart.ps1 restart for --commit-frac 0.82; it removes this file itself" -Encoding utf8
Say "stop file written; waiting for the bot to exit"
$t0 = Get-Date
while ((LadPids).Count -gt 0 -and ((Get-Date) - $t0).TotalSeconds -lt 150) { Start-Sleep -Seconds 2 }
if ((LadPids).Count -gt 0) { Remove-Item $stop -Force; Say "did NOT exit in 150 s -- stop file removed, old bot left running"; exit 1 }
Say ("old bot exited after {0:N0} s" -f ((Get-Date) - $t0).TotalSeconds)
Remove-Item $stop -Force
Say "stop file removed; running KalsBoot"
schtasks /run /tn KalsBoot | Out-Null
$t0 = Get-Date
while ((LadPids).Count -eq 0 -and ((Get-Date) - $t0).TotalSeconds -lt 180) { Start-Sleep -Seconds 3 }
Say ("new ladder pids: " + ((LadPids) -join ","))
Start-Sleep -Seconds 20
$st = Get-Content C:\kals-repo\results\ladder-live-orders.jsonl -Tail 200 | Where-Object { $_ -match '"ev": ?"start"' } | Select-Object -Last 1
if ($st) { $o = $st | ConvertFrom-Json; Say ("start record: t {0} pot {1} commit_frac {2} size {3}" -f $o.t, $o.pot, $o.auto.commit_frac, $o.auto.size) } else { Say "start record NOT FOUND" }
Say "done"
