# admin_1018.ps1 -- run ONCE from an ELEVATED PowerShell (right-click PowerShell -> Run as administrator):
#     & C:\kals-repo\results\admin_1018.ps1
# Operator 10-18: "Push recorder fix" + make the new Telegram layout live. Neither touches a money bot.
#  1. Installs the recorder fix (kalshi_collector v4 -> v5: one market-lookup loop per connection; ends the 429 storm),
#     keeping a backup of v4.
#  2. Waits until hh:59:50 UTC (so the new recorder opens the next hour's files cleanly), then stops the ONE running
#     recorder and the ONE running phone link (pinphone). run_all.ps1 restarts the recorder within ~5 min and
#     boot_all.ps1 restarts pinphone within ~10 min, on the new files. Tape gap: ~5-6 minutes.
# Revert recorder: copy C:\kals\kalshi_collector.py.bak-20261018-v4 over C:\kals\kalshi_collector.py, then stop it the same way.
$ErrorActionPreference = 'Stop'
$patch = 'C:\kals-repo\.sweep\q-2026-10-18b\ratelimit\patches\collector\kalshi_collector.py'
$live = 'C:\kals\kalshi_collector.py'
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Not elevated. Right-click PowerShell -> Run as administrator, then run this again."; exit 1 }

# 1. install the recorder file (once)
if (-not (Select-String -Path $live -Pattern '2026-10-18-v5' -Quiet)) {
    Copy-Item $live "$live.bak-20261018-v4" -Force
    Copy-Item $patch $live -Force
    Copy-Item $patch 'C:\kals-repo\kalshi_collector.py' -Force
}
if (-not (Select-String -Path $live -Pattern '2026-10-18-v5' -Quiet)) { Write-Host "Recorder file is not v5 -- stopping here."; exit 1 }
Write-Host "Recorder file is v5 (backup: $live.bak-20261018-v4)."

# 2. find exactly one recorder and one phone link
$col = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*kalshi_collector.py*' })
$tel = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*pinphone.py*' })
Write-Host ("recorders found: {0}; phone links found: {1}" -f $col.Count, $tel.Count)
if ($col.Count -ne 1) { Write-Host "Expected exactly ONE recorder -- not stopping anything. (Ask Claude.)"; exit 1 }

# wait for hh:59:50 UTC
while ($true) { $u = (Get-Date).ToUniversalTime(); if ($u.Minute -eq 59 -and $u.Second -ge 50) { break }; Write-Host -NoNewline "`rwaiting for hh:59:50 UTC (now $($u.ToString('HH:mm:ss')))"; Start-Sleep 1 }
Write-Host ""
Stop-Process -Id $col[0].ProcessId -Force; Write-Host "stopped recorder pid $($col[0].ProcessId)"
if ($tel.Count -eq 1) { Stop-Process -Id $tel[0].ProcessId -Force; Write-Host "stopped phone link pid $($tel[0].ProcessId)" }
Write-Host "Done. The recorder restarts within ~5 min (run_all.ps1) and the phone link within ~10 min (boot_all.ps1). Do NOT start them by hand."
