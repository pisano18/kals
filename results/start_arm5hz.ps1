# start_arm5hz.ps1 -- PAPER arm-5hz (2026-10-09, results/FINAL_VERSION_2026-10-08.md 2e/3):
# arm-live-twin's exact argv (results/relaunch_twin_1006.cmd.txt) on a COPY of the twin's code
# (C:\kals-arms\arm-5hz\research, repo pinrun.py 9afb6eca6a91 + the --index-5hz patch) plus ONE
# flag, --index-5hz: also read Kalshi's 5-per-second settlement index and let the newest
# sub-second print set the price the model projects from. No money: refuses if --live appears.
$exe = "C:\Python314\python.exe"
$argv = @("-u", "C:\kals-arms\arm-5hz\research\pinrun.py",
  "--size", "20", "--minutes", "10080", "--loss-abort", "-100000", "--max-positions", "3",
  "--max-losses", "1000", "--improve-scope", "market", "--pick", "best", "--max-per-market", "2",
  "--improve-max", "0.010", "--min-fill-frac", "0", "--sweep-depth", "--depth-ladder", "--jump-gate",
  "--hedge-belief", "0.40", "--early-tau", "45", "--early-frac", "0.333", "--early-min-price", "0.90",
  "--early-max-price", "0.978", "--rebuy-late-tau", "15", "--rebuy-late-frac", "0.5",
  "--series", "KXBTCD", "--series-size", "1", "--early-max-edge", "10.0", "--no-hedge-prop",
  "--toxic-fresh", "--price-ceiling", "0.98", "--one-full-bet", "--hedge-slip", "0.10",
  "--late-tau", "10", "--late-mult", "1.5", "--late-pin", "0.9975", "--late-jump", "2.0",
  "--extra-coin", "1", "--late-extra", "1", "--late-extra-tau", "15", "--bank-brake", "4.00",
  "--loss-cap", "200",
  "--index-5hz", "--arm-name", "arm-5hz")
if ($argv -contains "--live") { "REFUSING: --live in a paper arm's argv"; exit 1 }
$p = Start-Process -FilePath $exe -ArgumentList $argv -WorkingDirectory "C:\kals-repo" -WindowStyle Hidden `
    -RedirectStandardOutput "C:\kals-repo\results\arm-5hz.out" -RedirectStandardError "C:\kals-repo\results\arm-5hz.err" -PassThru
"started PAPER arm-5hz pid $($p.Id) at $((Get-Date).ToUniversalTime().ToString('u'))"
