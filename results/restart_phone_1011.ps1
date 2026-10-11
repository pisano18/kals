# restart_phone_1011.ps1 -- restart the operator's Telegram phone bot (research/pinphone.py) so it picks up the new /funds
# command (operator 2026-10-11: "Add a way in telegram to see the bankroll or fund sizes of all sub accounts"; built + reviewed GO).
# Stops ONLY the python process whose command line is pinphone.py, then starts it exactly as boot_all.ps1 section 3b does.
$repo = "C:\kals-repo"; $res = "$repo\results"; $py = "C:\Python314\python.exe"
$old = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*research\pinphone.py*' })
if ($old.Count -ne 1) { "expected exactly one phone bot, found $($old.Count) -- refusing"; exit 1 }
Stop-Process -Id $old[0].ProcessId -Force
Start-Sleep 3
$p = Start-Process -FilePath $py -ArgumentList @("-u", "$repo\research\pinphone.py") -WorkingDirectory $repo -WindowStyle Hidden `
    -RedirectStandardOutput "$res\pinphone.out" -RedirectStandardError "$res\pinphone.err" -PassThru
"phone bot restarted: old pid $($old[0].ProcessId) -> new pid $($p.Id)"
