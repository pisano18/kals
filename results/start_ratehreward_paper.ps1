# start_ratehreward_paper.ps1 -- PAPER RATEH reward-pair recorder (spec .sweep/hunt-2026-10-15/spec-20261015-R1-C2-01,
# rule V2: ghost 1c/1c pairs 6-8 bp from the ladder yield + cancel-all on the first far sweep). GET-only REST
# (<= 1 call / 3 s) + one market-data WebSocket (livebook). No money: refuses if --live appears.
# Runs 14 days (20160 min) = Mon 10-19 .. Fri 10-30 (the 6.3 EXTEND horizon) when started before Mon 06:58Z.
# Ends cleanly on C:\kals-repo\results\ratehreward-paper.stop ; log C:\kals-repo\results\ratehreward-paper.jsonl
$exe = "C:\Python314\python.exe"
$argv = @("-u", "C:\kals-repo\research\sweep\ratehreward_paper.py", "--minutes", "20160")
if ($argv -contains "--live") { "REFUSING: --live in a paper recorder's argv"; exit 1 }
if (Test-Path "C:\kals-repo\results\ratehreward-paper.stop") {
  "REFUSING: stop file present -- delete C:\kals-repo\results\ratehreward-paper.stop first"; exit 1 }
$p = Start-Process -FilePath $exe -ArgumentList $argv -WorkingDirectory "C:\kals-repo" -WindowStyle Hidden `
    -RedirectStandardOutput "C:\kals-repo\results\ratehreward-paper.out" -RedirectStandardError "C:\kals-repo\results\ratehreward-paper.err" -PassThru
"started PAPER ratehreward-paper pid $($p.Id) at $((Get-Date).ToUniversalTime().ToString('u'))"
