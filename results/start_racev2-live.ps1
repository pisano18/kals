# start_racev2-live.ps1 -- LIVE coin-race reward filler v2, the 20-race test (operator: "Build race v2.", 2026-10-22).
# research\sweep\racev2_live.py (sha256 7484be3d716f...; spec .sweep\hunt-2026-10-15\spec-20261015-R1-C2-02 section 3,
# bar 4.2). Subaccount 4 ONLY, pool 2, 1,100 YES at 1c on dead legs, exit 116 s (own cancel) / 115 s (server expiry),
# every 3rd race, max 20 races with an order then it exits; at most -$30 a day, -$45 over the test, $40 collateral.
# Its self-test runs first and it refuses on a failure, on a changed racereward_live.py / racev2_shadow.py, on sub-4 cash
# outside $40..$50, on open positions, or on a stop file.
# PRE-REGISTERED SAMPLE (spec 4.2): start between 21:00 and 23:00 ET so 00-04 ET falls inside and the run crosses an ET
# midnight. Fund first:  python research\ordercli.py --sub-fund 45 --sub 4   (dry run -> token -> --live --signoff <token>)
# Stop: New-Item C:\kals-repo\results\racev2-live.stop   (cancels everything and exits; delete it before a restart)
# Read: python research\sweep\racev2_live.py --subaccount 4 --report   (2 h after the last race, and 48 h after it)
$exe = "C:\Python314\python.exe"
$argv = @("-u", "C:\kals-repo\research\sweep\racev2_live.py", "--subaccount", "4", "--live", "--races", "20", "--every", "3")
if (Test-Path "C:\kals-repo\results\racev2-live.stop") { "REFUSING: results\racev2-live.stop exists; delete it to start"; exit 1 }
$p = Start-Process -FilePath $exe -ArgumentList $argv -WorkingDirectory "C:\kals-repo" -WindowStyle Hidden `
    -RedirectStandardOutput "C:\kals-repo\results\racev2-live.out" -RedirectStandardError "C:\kals-repo\results\racev2-live.err" -PassThru
"started LIVE racev2 pid $($p.Id) at $((Get-Date).ToUniversalTime().ToString('u'))"
