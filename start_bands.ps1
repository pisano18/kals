# start_bands.ps1 -- the AMENDMENT 53 paper arms: price bands, sizing by band,
# and the 45-second leg opened to the bands that earn. READ-ONLY: pinrun
# without --live is paper and cannot send an order.
#
# The operator, 2026-09-18: "Start up some paper trades all tinkering all
# around with the idea of buying early on the safer ranges, omitting 94-96 and
# 94-97.5, doubling down on more certain trades with better staked to return
# ratios, just going harder ... in the good ranges."
#
# EVERY ARM SHARES THE LIVE BASELINE (v-bands: hedge on the market's agreement
# at 0.60, 1.5x at 90-94c that switches itself off after one boosted loss)
# and changes ONE thing, except the last, which changes everything at once.
# `arm-b-control` IS the live flag set in paper, so its start record is the
# proof that the live startup path -- self-test WITH flags applied -- comes
# up; start it first.
#
# REVISED ~22:3xZ the same day: the 94-96c skip came OUT of the baseline and
# out of the live set (VERSIONS.md v-bands section 2 -- the "dead band" was
# three first-week losses; on the modern bot it earns 2.25%). It is now one
# arm, `arm-b-skip9496`, read against the control like every other change.
#
#     powershell -ExecutionPolicy Bypass -File C:\kals-repo\start_bands.ps1
#     powershell -ExecutionPolicy Bypass -File C:\kals-repo\start_bands.ps1 -Only control
#     powershell -ExecutionPolicy Bypass -File C:\kals-repo\start_bands.ps1 -SkipControl
#
# WHAT PAPER CAN AND CANNOT SAY HERE. A paper fill is the touch at the tape
# price; nobody sold it to us. So a band-mult arm measures how OFTEN the book
# held the wider order and what those markets settled at -- never whether a
# 2x order fills at the same price as a 1x one. An early-open arm's loss rate
# is a LOWER bound on the live one (rule 5). Paper kills an idea; only a
# graduated live step proves one.
param([string]$Only = "", [switch]$SkipControl)
$py = "C:\Python314\python.exe"
$r  = "C:\kals-repo\results"

$core = @("-u", "C:\kals-repo\research\pinrun.py", "--size", "20", "--minutes", "4320",
          "--loss-abort", "-60.00", "--max-positions", "3", "--max-losses", "2",
          "--improve-scope", "market", "--pick", "best", "--max-per-market", "2",
          "--improve-max", "0.010", "--min-fill-frac", "0", "--sweep-depth", "--depth-ladder",
          "--jump-gate", "--hedge-belief", "0.60", "--early-tau", "45", "--early-frac", "1.0",
          "--bank-brake", "4.08", "--hedge-price", "0.60")
$m15 = @("--band-mult", "0.90", "0.94", "1.5")

$arms = @(
  # the live set, in paper: the control every other arm is read against
  @{ n = "arm-b-control";     x = @("--early-min-price", "0.90", "--early-max-edge", "3.0") + $m15 },
  # the 45 s leg opened to the bands that earn: no 3c edge cap, floor at 80c
  @{ n = "arm-b-early-open";  x = @("--early-min-price", "0.80") + $m15 },
  # the 45 s leg with the edge cap off but the 90c floor kept (isolates the cap)
  @{ n = "arm-b-early-nocap"; x = @("--early-min-price", "0.90") + $m15 },
  # skip 94-96c -- withdrawn from live, tested here
  @{ n = "arm-b-skip9496";    x = @("--early-min-price", "0.90", "--early-max-edge", "3.0",
                                    "--skip-band", "0.94", "0.96") + $m15 },
  # skip 94-97.5c
  @{ n = "arm-b-skip975";     x = @("--early-min-price", "0.90", "--early-max-edge", "3.0",
                                    "--skip-band", "0.94", "0.975") + $m15 },
  # 2x at 90-94c instead of 1.5x
  @{ n = "arm-b-mult2";       x = @("--early-min-price", "0.90", "--early-max-edge", "3.0",
                                    "--band-mult", "0.90", "0.94", "2.0") },
  # go harder: 2x across 80-94c, and skip 94-97.5c
  @{ n = "arm-b-harder";      x = @("--early-min-price", "0.90", "--early-max-edge", "3.0",
                                    "--skip-band", "0.94", "0.975",
                                    "--band-mult", "0.80", "0.90", "2.0", "--band-mult", "0.90", "0.94", "2.0") },
  # everything at once: early open + harder
  @{ n = "arm-b-all";         x = @("--early-min-price", "0.80",
                                    "--skip-band", "0.94", "0.975",
                                    "--band-mult", "0.80", "0.90", "2.0", "--band-mult", "0.90", "0.94", "2.0") }
)

$started = 0
foreach ($a in $arms) {
  if ($Only -ne "" -and $a.n -ne "arm-b-$Only") { continue }
  if ($SkipControl -and $a.n -eq "arm-b-control") { continue }
  Start-Process -FilePath $py -ArgumentList ($core + $a.x) -WorkingDirectory "C:\kals-repo" `
    -RedirectStandardOutput "$r\$($a.n).out" -RedirectStandardError "$r\$($a.n).err" -WindowStyle Hidden
  "started $($a.n)"
  $started++
  Start-Sleep -Seconds 4
}
"$started arm(s) started"
