# start_arm_attempts.ps1 -- PAPER arm-attempts (2026-10-10, money sweep item 6, results/MONEY_SWEEP_2026-10-10.md):
# the LIVE build (C:\kals-live-0925e, code_sha 5075b1783acf) with today's exact live argv, minus --live, with the
# twins' no-brake pair (--max-losses 1000, --loss-abort -100000) so it cannot stop on the 2-loss brake, plus ONE flag:
# --attempts-on-send (count a per-market attempt only when an order is SENT, so refusals that never send cannot lock
# a market out for the rest of the close). Compared against LIVE on the same closes. No money: refuses if --live appears.
$exe = "C:\Python314\python.exe"
$argv = @("-u", "C:\kals-live-0925e\research\pinrun.py",
  "--size", "20", "--minutes", "10080", "--loss-abort", "-100000", "--max-positions", "3", "--max-losses", "1000",
  "--improve-scope", "market", "--pick", "best", "--max-per-market", "2", "--improve-max", "0.010",
  "--max-full-bets", "1.0", "--skip-coin", "KXHYPE15M", "--no-drawdown-halt",
  "--min-fill-frac", "0", "--sweep-depth", "--depth-ladder", "--jump-gate", "--hedge-belief", "0.40",
  "--early-tau", "45", "--early-frac", "0.333", "--early-min-price", "0.90",
  "--rebuy-late-tau", "15", "--rebuy-late-frac", "0.5", "--series", "KXBTCD", "--series-size", "1",
  "--early-max-edge", "10.0", "--no-hedge-prop", "--hedge-slip", "0.10",
  "--late-tau", "10", "--late-mult", "1.5", "--late-pin", "0.9975", "--late-jump", "2.0",
  "--extra-coin", "1", "--late-extra", "1", "--late-extra-tau", "15", "--bank-brake", "4.00", "--loss-cap", "200",
  "--attempts-on-send")
if ($argv -contains "--live") { "REFUSING: --live in a paper arm's argv"; exit 1 }
$p = Start-Process -FilePath $exe -ArgumentList $argv -WorkingDirectory "C:\kals-repo" -WindowStyle Hidden `
    -RedirectStandardOutput "C:\kals-repo\results\arm-attempts.out" -RedirectStandardError "C:\kals-repo\results\arm-attempts.err" -PassThru
"started PAPER arm-attempts pid $($p.Id) at $((Get-Date).ToUniversalTime().ToString('u'))"
