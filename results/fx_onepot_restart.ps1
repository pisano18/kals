# fx_onepot_restart.ps1 -- 2026-10-30 (v-fx-onepot, operator: "just base each bot's bet off of the size of the full
# subaccount"). Restarts the FX taker so it runs the pulled one-bank code: its size from BOTH pots together ($20 of bank a
# contract: ~$207 = 10, today's size), the caps scaled with it, and both pools from subaccount 5 by itself once subaccount
# 4 is empty in pool 0 and 5 holds pool-0 cash. It also carries the 30 s window (v-fx-back30), so it replaces fx30.
# boot_all passes '--subaccount 5 --fx-subaccount 4' and nothing else, so no boot_all edit.
# Launch detached (WMI). Steps: refuse unless the one-bank code is pulled and its self-test passes -> wait for minutes
# 1-11 of the quarter hour (the bot only buys in the last 30 s before a close and is flat once the close has settled) ->
# write results\fxtake-live.stop (no new orders, exits when flat) -> once exited: delete the stop file, run KalsBoot ->
# boot_all starts it again on the new code -> check the start record (layout, size, bank).
# If it has not exited after 150 s the stop file is removed and the old bot left running. Log: results\fx_onepot_restart.out
$repo = 'C:\kals-repo'; $res = "$repo\results"; $log = "$res\fx_onepot_restart.out"; $stop = "$res\fxtake-live.stop"
$py = 'C:\Python314\python.exe'; $fx = "$repo\research\cleanroom\fxtake_live.py"
function Say($m) { ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $m) | Out-File $log -Append -Encoding utf8 }
function FxPids { @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*fxtake_live.py*--live*" } | ForEach-Object { $_.ProcessId }) }
Say "start; HEAD $(git -C $repo rev-parse --short HEAD)"
$src = Get-Content $fx -Raw
if ($src -notmatch '(?m)^BANK_PER_CONTRACT\s*=\s*20\.0' -or $src -notmatch '(?m)^def choose_layout\(') { Say "fxtake_live.py does not have the one-bank code (BANK_PER_CONTRACT = 20.0, choose_layout) -- pull first; doing nothing"; exit 1 }
if ($src -notmatch '(?m)^ENTRY_FROM\s*=\s*30\.0') { Say "fxtake_live.py does not have ENTRY_FROM = 30.0 -- pull first; doing nothing"; exit 1 }
if (Test-Path $stop) { Say "a stop file already exists -- doing nothing"; exit 1 }
$st = & $py $fx --selftest | Select-Object -Last 1
if ("$st" -notmatch 'SELFTEST PASSED') { Say "fxtake_live.py --selftest did not pass ($st) -- the old bot keeps running; doing nothing"; exit 1 }
Say "self-test passed; waiting for minutes 1-11 of a quarter hour"
while ($true) { $m = (Get-Date).Minute % 15; if ($m -ge 1 -and $m -le 11) { break }; Start-Sleep -Seconds 5 }
Say ("running fx pids: " + ((FxPids) -join ","))
Set-Content -Path $stop -Value "fx_onepot_restart.ps1 restart for the one-bank FX taker (v-fx-onepot); it removes this file itself" -Encoding utf8
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
if ($st) {
    $r = $null; try { $r = $st | ConvertFrom-Json } catch {}
    if ($r -and $r.layout) { Say ("one-bank start: layout {0} ({1}); size {2} from a `${3} bank; caps held `${4} / day {5} / line {6}" -f $r.layout, $r.layout_why, $r.size, $r.bank, $r.max_held, $r.day_stop, $r.stop_line) }
    else { Say "the start record has no 'layout': the OLD code started -- check the pull" }
    Say ("start record: " + $st.Substring(0, [Math]::Min(400, $st.Length)))
} else { Say "start record NOT FOUND" }
Say "done"
