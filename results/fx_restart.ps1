# fx_restart.ps1 -- 2026-10-30 (v-fx-from45, operator: "Sure widen fx if the profit loss rate increases").
# Restarts the FX taker so it runs the pulled code (ENTRY_FROM 45 s; boot_all passes no --from, so no boot_all edit).
# Launch detached (WMI). Steps: wait for minutes 1-11 of the quarter hour (the bot only buys in the last 45 s before a
# close and is flat once the close has settled) -> write results\fxtake-live.stop (no new orders, exits when flat) ->
# once exited: delete the stop file, run KalsBoot -> boot_all starts it again on the new code -> check the start record.
# If it has not exited after 150 s the stop file is removed and the old bot left running. Log: results\fx_restart.out
$repo = 'C:\kals-repo'; $res = "$repo\results"; $log = "$res\fx_restart.out"; $stop = "$res\fxtake-live.stop"
function Say($m) { ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $m) | Out-File $log -Append -Encoding utf8 }
function FxPids { @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*fxtake_live.py*--live*" } | ForEach-Object { $_.ProcessId }) }
Say "start; HEAD $(git -C $repo rev-parse --short HEAD)"
$src = Get-Content "$repo\research\cleanroom\fxtake_live.py" -Raw
if ($src -notmatch '(?m)^ENTRY_FROM\s*=\s*45\.0') { Say "fxtake_live.py does not have ENTRY_FROM = 45.0 -- pull first; doing nothing"; exit 1 }
if (Test-Path $stop) { Say "a stop file already exists -- doing nothing"; exit 1 }
Say "waiting for minutes 1-11 of a quarter hour"
while ($true) { $m = (Get-Date).Minute % 15; if ($m -ge 1 -and $m -le 11) { break }; Start-Sleep -Seconds 5 }
Say ("running fx pids: " + ((FxPids) -join ","))
Set-Content -Path $stop -Value "fx_restart.ps1 restart for ENTRY_FROM 45; it removes this file itself" -Encoding utf8
Say "stop file written; waiting for the bot to exit flat"
$t0 = Get-Date
while ((FxPids).Count -gt 0 -and ((Get-Date) - $t0).TotalSeconds -lt 150) { Start-Sleep -Seconds 2 }
if ((FxPids).Count -gt 0) { Remove-Item $stop -Force; Say "did NOT exit in 150 s -- stop file removed, old bot left running"; exit 1 }
Say ("old bot exited after {0:N0} s" -f ((Get-Date) - $t0).TotalSeconds)
Remove-Item $stop -Force
Say "stop file removed; running KalsBoot"
schtasks /run /tn KalsBoot | Out-Null
$t0 = Get-Date
while ((FxPids).Count -eq 0 -and ((Get-Date) - $t0).TotalSeconds -lt 180) { Start-Sleep -Seconds 3 }
Say ("new fx pids: " + ((FxPids) -join ","))
Start-Sleep -Seconds 20
$st = Get-Content "$res\fxtake-live-orders.jsonl" -Tail 300 | Where-Object { $_ -match '"kind": ?"start"' } | Select-Object -Last 1
if ($st) { Say ("start record: " + $st.Substring(0, [Math]::Min(400, $st.Length))) } else { Say "start record NOT FOUND" }
Say "done"
