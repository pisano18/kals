# start_fc_fast.ps1 -- PAPER fc-fast (2026-10-17, results/STRATEGY_HUNT_2026-10-15.md, "Lose-less leads" A):
# research\cleanroom\fc_fast_paper.py runs, on ONE Kalshi WebSocket, the live clean-room forecaster's exact paper
# rule (control: forecaster_live --variant race1_98_r28 --crash-gap 0.10, decide 0.2 s after the print's second,
# fill only if still shown 1.0 s later) beside a FAST variant (decide when the print arrives, fill only if still
# shown 75 ms later; same prices, caps and crash guard). No money: GET-only public REST, market-data WebSocket,
# no order code; refuses if --live appears. Log results\fc-fast-paper.jsonl; stop: create results\fc-fast-paper.stop.
# Read the bar with:  python research\cleanroom\fc_fast_paper.py --read   (after >= 200 fast fills / >= 100 closes)
$exe = "C:\Python314\python.exe"
$argv = @("-u", "research\cleanroom\fc_fast_paper.py", "--minutes", "20160")
if ($argv -contains "--live") { "REFUSING: --live in a paper runner's argv"; exit 1 }
$stop = "C:\kals-repo\results\fc-fast-paper.stop"
if (Test-Path $stop) { "REFUSING: stop file present ($stop); delete it to start"; exit 1 }
$lock = "C:\kals-repo\results\fc-fast-paper.jsonl.lock"
if (Test-Path $lock) {
  $held = (Get-Content $lock -ErrorAction SilentlyContinue | Select-Object -First 1)
  if ($held -and (Get-Process -Id ([int]$held) -ErrorAction SilentlyContinue)) { "REFUSING: already running as pid $held"; exit 1 }
}
$p = Start-Process -FilePath $exe -ArgumentList $argv -WorkingDirectory "C:\kals-repo" -WindowStyle Hidden `
    -RedirectStandardOutput "C:\kals-repo\results\fc-fast-paper.out" -RedirectStandardError "C:\kals-repo\results\fc-fast-paper.err" -PassThru
"started PAPER fc-fast pid $($p.Id) at $((Get-Date).ToUniversalTime().ToString('u'))"
