# START_COINRACE_LIVE.ps1 -- the Coin Race penny test, real money.
#
# SCOPE, which the program itself enforces and its self-test proves:
#   1 contract per order, 10 orders maximum, ever
#   $10.00 cumulative stake cap  (worst case is 10 x 0.95 = $9.50)
#   never pays above 95c, where break-even at tau 15-20 is 97.28c
#   only buys 15-20 seconds before a race closes
#   only when first place leads second by >= 0.005% of return
#
# It stops itself for good once any cap is reached. To stop it early:
#   Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
#     Where-Object {$_.CommandLine -like '*pinracetest*'} |
#     ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object {$_.CommandLine -like '*pinracetest*'} |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force
                   Write-Host "stopped previous tester pid $($_.ProcessId)" }
Start-Sleep -Seconds 2

Start-Process -FilePath "C:\Python314\python.exe" `
  -ArgumentList '-u','C:\kals-repo\research\pinracetest.py','--live','--minutes','420' `
  -WorkingDirectory 'C:\kals-repo' `
  -RedirectStandardOutput "C:\kals-repo\results\pinracetest-live.log" `
  -RedirectStandardError  "C:\kals-repo\results\pinracetest-live.log.err" `
  -WindowStyle Hidden
Start-Sleep -Seconds 30

$r = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
     Where-Object {$_.CommandLine -like '*pinracetest*'} | Select-Object ProcessId
if ($r) { Write-Host "LIVE PENNY TEST RUNNING pid $($r.ProcessId)" }
else    { Write-Host "FAILED TO START -- reason below"
          Get-Content C:\kals-repo\results\pinracetest-live.log.err -Tail 20 }
Get-Content C:\kals-repo\results\pinracetest-live.log -Tail 8
