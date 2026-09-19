# start_sigma.ps1 -- AMENDMENT 57: the same bot at four different levels of
# caution. READ-ONLY (paper: pinrun without --live cannot send an order).
#
# The operator, 2026-09-18: "can you make paper arms with different sigmas.
# The whole thing not just the boost."
#
# --sigma-stress multiplies the volatility estimate EVERYWHERE the model
# runs: the fair value at entry, the highest price the sweep may pay, and
# the hedge's belief while a position is open. There is no corner of the
# decision it does not touch, which is what he asked for.
#
# Above 1.0 the bot believes the coin can move further than measured, so it
# is less sure, takes fewer trades and pays less for them. Below 1.0 it
# believes the coin is calmer than measured, so it is surer, takes more and
# pays more. A LIVE run refuses anything under 1.0 -- every live number we
# have was measured at 1.0, and a bolder model is not a safer one.
#
#     powershell -ExecutionPolicy Bypass -File C:\kals-repo\start_sigma.ps1
param([switch]$Stop)
$py = "C:\Python314\python.exe"; $r = "C:\kals-repo\results"
if ($Stop) {
  $v = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
       Where-Object { $_.CommandLine -like '*--sigma-stress*' -and $_.CommandLine -notlike '*--live*' }
  foreach ($p in $v) { Stop-Process -Id $p.ProcessId -Force -EA SilentlyContinue }
  "stopped $(@($v).Count)"; return
}
# the live baseline, so each arm differs from live in ONE number
$core = @("-u","C:\kals-repo\research\pinrun.py","--size","20","--minutes","4320",
          "--loss-abort","-60.00","--max-positions","3","--max-losses","2",
          "--improve-scope","market","--pick","best","--max-per-market","2",
          "--improve-max","0.010","--min-fill-frac","0","--sweep-depth","--depth-ladder",
          "--jump-gate","--hedge-belief","0.60","--early-tau","45","--early-frac","1.0",
          "--early-min-price","0.90","--early-max-edge","3.0","--bank-brake","4.08",
          "--hedge-price","0.60","--band-mult","0.90","0.94","1.5",
          "--late-tau","10","--late-mult","1.5","--late-pin","0.9975","--late-jump","2.0")
foreach ($s in @("0.80","1.25","1.50","2.00")) {
  Start-Process -FilePath $py -ArgumentList ($core + @("--sigma-stress", $s)) `
    -WorkingDirectory "C:\kals-repo" -WindowStyle Hidden `
    -RedirectStandardOutput "$r\arm-sig$s.out" -RedirectStandardError "$r\arm-sig$s.err"
  "started --sigma-stress $s"
  Start-Sleep -Seconds 4
}
