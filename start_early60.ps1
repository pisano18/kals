# start_early60.ps1 -- can we buy EARLIER than 45 seconds, in increments?
#
# The operator, 2026-09-18: "Do we have an arm for testing buying early in
# increments up to 60 seconds?" We did not -- `arm-early60` was in the old
# boot list and ended on 09-17, and the band-arm rewrite dropped it. This
# brings the question back as three arms on the CURRENT live baseline.
#
# WHY 60 SECONDS IS THE WALL. Settlement is the mean of sixty one-second
# prints. At 60 s out NONE of them is recorded, so the locked-average
# collapse the whole strategy rests on has not begun; at 45 s a quarter is
# locked, at 30 s a half. Beyond 60 s there is no edge to find, only the
# market's own opinion. So this is the last rung of the ladder, not a step
# on a longer one.
#
# WHAT "IN INCREMENTS" MEANS HERE. `--early-frac 0.333` buys a THIRD when it
# first qualifies (46-60 s), and the top-up leg completes the position to a
# full bet once inside 30 s, when three times as much of the settlement
# average is on disk. Two bites at two different levels of certainty, which
# is what a staged entry is for. `--early-frac 1.0` commits the whole bet at
# the earlier, worse-information moment and is here as its control.
#
# READ-ONLY: pinrun without --live is paper and cannot send an order.
#
#     powershell -ExecutionPolicy Bypass -File C:\kals-repo\start_early60.ps1
#
param([switch]$Stop)
$py = "C:\Python314\python.exe"
$r  = "C:\kals-repo\results"

if ($Stop) {
  $v = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
       Where-Object { $_.CommandLine -like '*--early-tau 60*' -and $_.CommandLine -notlike '*--live*' }
  foreach ($p in $v) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
  "stopped $(@($v).Count)"
  return
}

# the live baseline (v-bands), minus the early-leg settings each arm sets
$core = @("-u", "C:\kals-repo\research\pinrun.py", "--size", "20", "--minutes", "4320",
          "--loss-abort", "-60.00", "--max-positions", "3", "--max-losses", "2",
          "--improve-scope", "market", "--pick", "best", "--max-per-market", "2",
          "--improve-max", "0.010", "--min-fill-frac", "0", "--sweep-depth", "--depth-ladder",
          "--jump-gate", "--hedge-belief", "0.60", "--bank-brake", "4.08",
          "--hedge-price", "0.60", "--band-mult", "0.90", "0.94", "1.5")

$arms = @(
  # a THIRD at 46-60 s, topped up to a full bet inside 30 s -- the increments
  @{ n = "arm-e60-third"; x = @("--early-tau", "60", "--early-frac", "0.333",
                                "--early-min-price", "0.90", "--early-max-edge", "3.0") },
  # the whole bet at 46-60 s: the control for the increments
  @{ n = "arm-e60-full";  x = @("--early-tau", "60", "--early-frac", "1.0",
                                "--early-min-price", "0.90", "--early-max-edge", "3.0") },
  # increments AND the bands that earn: no 3c edge cap, floor at 80c
  @{ n = "arm-e60-open";  x = @("--early-tau", "60", "--early-frac", "0.333",
                                "--early-min-price", "0.80") },
  # A54: the SAME arm as arm-e60-third, plus one thing -- when a bet opened
  # at 46-60 s flips inside 30 s, buy DOUBLE the position on the side the
  # later look prefers instead of an equal hedge. arm-e60-third is its
  # control; the two differ only in --flip-mult, so the pair measures the
  # flip and nothing else. The operator: "have one that does that and one
  # that doesnt."
  @{ n = "arm-e60-flip2"; x = @("--early-tau", "60", "--early-frac", "0.333",
                                "--early-min-price", "0.90", "--early-max-edge", "3.0",
                                "--flip-mult", "2.0") }
)

foreach ($a in $arms) {
  # --arm-name puts $a.n in the COMMAND LINE, so the desktop app can prove
  # which of these near-identical arms a process is before stopping it.
  Start-Process -FilePath $py -ArgumentList ($core + $a.x + @("--arm-name", $a.n)) -WorkingDirectory "C:\kals-repo" `
    -RedirectStandardOutput "$r\$($a.n).out" -RedirectStandardError "$r\$($a.n).err" -WindowStyle Hidden
  "started $($a.n)"
  Start-Sleep -Seconds 4
}
