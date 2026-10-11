# start_racereward.ps1 -- LIVE coin-race reward TEST (operator 2026-10-10 "Yes to coin race test", 2026-10-11 "Create subaccount 4").
# research/sweep/racereward_live.py (code_sha c73979198066; reviewed twice: results/MONEY_SWEEP_2026-10-10.md item 1) in subaccount 4
# (pool 2, funded $55 from main 2026-10-11): 1c YES bids, 1,000 contracts, on dead coin-race legs, exit at close-60 s, day budget -$30,
# 20 races. Stop it with results\racereward-live.stop (cancels everything and exits).
$p = Start-Process -FilePath "C:\Python314\python.exe" -ArgumentList @("-u", "research\sweep\racereward_live.py", "--subaccount", "4", "--live", "--races", "20", "--minutes", "720") `
    -WorkingDirectory "C:\kals-repo" -WindowStyle Hidden `
    -RedirectStandardOutput "C:\kals-repo\results\racereward-live.out" -RedirectStandardError "C:\kals-repo\results\racereward-live.err" -PassThru
"started LIVE racereward pid $($p.Id) at $((Get-Date).ToUniversalTime().ToString('u'))"
