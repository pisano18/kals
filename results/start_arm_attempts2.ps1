# start_arm_attempts2.ps1 -- PAPER arm-attempts2 (2026-10-17): the 10-10 arm-attempts died at the 10-14 shutdown with 2 of
# its 7 ET days (READS_DUE arm-attempts, read 10-17: 3 extra markets, 0 lost, +$9.70 paper so far). Relaunched on TODAY's
# live build (C:\kals-live-0925j, code_sha d8c3c7dcb888) with today's exact live argv (results/restart_bot.last.log
# "flags now live:"), minus --live, with the twins' no-brake pair (--max-losses 1000, --loss-abort -100000) so the paper
# 2-loss brake cannot stop it, --minutes 10080, plus ONE flag: --attempts-on-send (count a per-market attempt only when an
# order is SENT, so refusals that never send cannot lock a market out for the rest of the close). Compared against LIVE on
# the same closes. No money: refuses if --live appears.
$exe = "C:\Python314\python.exe"
$argv = @("-u", "C:\kals-live-0925j\research\pinrun.py",
  "--size", "20", "--minutes", "10080", "--loss-abort", "-100000", "--max-positions", "3", "--max-losses", "1000",
  "--improve-scope", "market", "--pick", "best", "--max-per-market", "2", "--improve-max", "0.010",
  "--max-full-bets", "1.0", "--coin-size-frac", "KXHYPE15M:0.15", "--no-drawdown-halt",
  "--min-fill-frac", "0", "--sweep-depth", "--depth-ladder", "--jump-gate", "--hedge-belief", "0.40",
  "--early-tau", "45", "--early-frac", "0.333", "--early-min-price", "0.90",
  "--rebuy-late-tau", "15", "--rebuy-late-frac", "0.5", "--series", "KXBTCD", "--series-size-frac", "0.12",
  "--early-max-edge", "10.0", "--no-hedge-prop", "--keep-conn", "on", "--keep-warm", "on", "--hedge-slip", "0.10",
  "--late-tau", "10", "--late-mult", "1.5", "--late-pin", "0.9975", "--late-jump", "2.0",
  "--extra-coin", "1", "--late-extra", "1", "--late-extra-tau", "15", "--bank-brake", "4.00", "--loss-cap-frac", "0.187",
  "--attempts-on-send")
if ($argv -contains "--live") { "REFUSING: --live in a paper arm's argv"; exit 1 }
$p = Start-Process -FilePath $exe -ArgumentList $argv -WorkingDirectory "C:\kals-repo" -WindowStyle Hidden `
    -RedirectStandardOutput "C:\kals-repo\results\arm-attempts2.out" -RedirectStandardError "C:\kals-repo\results\arm-attempts2.err" -PassThru
"started PAPER arm-attempts2 pid $($p.Id) at $((Get-Date).ToUniversalTime().ToString('u'))"
