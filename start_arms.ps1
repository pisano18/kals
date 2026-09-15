# start_arms.ps1 -- start the paper arms that answer an open question, plus the
# Coin Race paper arm. READ-ONLY: none of these can send an order (pinrun
# without --live is paper; --take-dumps refuses a live run; pinracearm has no
# order path at all). Written 2026-09-15 after a Windows Update restart killed
# every process and restoring them meant digging commands out of a transcript.
# Run AFTER run_all.ps1 (collectors) and restart_bot.ps1 (live bot).
#
#     powershell -ExecutionPolicy Bypass -File C:\kals-repo\start_arms.ps1
#
$py = "C:\Python314\python.exe"
$r  = "C:\kals-repo\results"

# 1. --pick first, the control for A24. Launched 2026-09-14T00:30Z.
$a24 = @("-u","C:\kals-repo\research\pinrun.py","--size","20","--minutes","4320",
         "--loss-abort","-60.00","--max-positions","3","--max-losses","3",
         "--improve-scope","market","--pick","first")
Start-Process -FilePath $py -ArgumentList $a24 -WorkingDirectory "C:\kals-repo" `
  -RedirectStandardOutput "$r\pinrun-a24-control-2.log" `
  -RedirectStandardError  "$r\pinrun-a24-control-2.log.err" -WindowStyle Hidden
Start-Sleep -Seconds 3

# 2..6 share the live flag set, launched 2026-09-15T01:28Z..12:53Z.
$live = @("-u","C:\kals-repo\research\pinrun.py","--size","20","--minutes","4320",
          "--loss-abort","-60.00","--max-positions","3","--max-losses","2",
          "--improve-scope","market","--pick","best","--max-per-market","2",
          "--improve-max","0.010","--min-fill-frac","0","--sweep-depth","--depth-ladder")

$arms = @(
  @{ n = "arm-mirror";   x = @("--jump-gate") },                   # identical to live
  @{ n = "arm-nogate";   x = @() },                                # live minus A40
  @{ n = "arm-widen-2";  x = @("--jump-widen") },                  # A41 without A40
  @{ n = "arm-both-2";   x = @("--jump-gate","--jump-widen") },    # A40 + A41
  @{ n = "arm-dumps-2";  x = @("--jump-gate","--take-dumps") }     # dump guard off
)
foreach ($a in $arms) {
  # stdout goes to a file too: a process whose stdout is the console of a
  # launcher that has since exited can die on its first print
  Start-Process -FilePath $py -ArgumentList ($live + $a.x) -WorkingDirectory "C:\kals-repo" `
    -RedirectStandardOutput "$r\$($a.n).out" `
    -RedirectStandardError "$r\$($a.n).err" -WindowStyle Hidden
  Start-Sleep -Seconds 3
}

# the Coin Race paper arm, on the fixed model
Start-Process -FilePath $py -ArgumentList @("-u","research\pinracearm.py","--minutes","720") `
  -WorkingDirectory "C:\kals-repo" `
  -RedirectStandardOutput "$r\pinracearm-live.log" `
  -RedirectStandardError  "$r\pinracearm-live.err" -WindowStyle Hidden

Start-Sleep -Seconds 40
$all = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { ($_.CommandLine -like '*pinrun*' -and $_.CommandLine -notlike '*--live*') -or $_.CommandLine -like '*pinracearm*' }
"paper processes alive: " + @($all).Count
foreach ($p in $all) {
  $tag = "mirror"
  if ($p.CommandLine -like '*pinracearm*') { $tag = "RACE" }
  elseif ($p.CommandLine -like '*--pick first*') { $tag = "pick-first" }
  elseif ($p.CommandLine -like '*take-dumps*') { $tag = "take-dumps" }
  elseif ($p.CommandLine -like '*jump-widen*' -and $p.CommandLine -like '*jump-gate*') { $tag = "gate+widen" }
  elseif ($p.CommandLine -like '*jump-widen*') { $tag = "widen" }
  elseif ($p.CommandLine -notlike '*jump-gate*') { $tag = "no-gate" }
  "  {0,-8} {1}" -f $p.ProcessId, $tag
}
foreach ($f in @("arm-mirror","arm-nogate","arm-widen-2","arm-both-2","arm-dumps-2")) {
  "  {0,-12} stderr {1} bytes" -f $f, (Get-Item "$r\$f.err" -ErrorAction SilentlyContinue).Length
}
"  a24 stderr " + (Get-Item "$r\pinrun-a24-control-2.log.err" -ErrorAction SilentlyContinue).Length + " bytes"
"  race stderr " + (Get-Item "$r\pinracearm-live.err" -ErrorAction SilentlyContinue).Length + " bytes"
