# start_fxreward_paper.ps1 -- PAPER quoter for the FX 15-minute reward test, --follow mode
# (spec .sweep/hunt-2026-10-15/spec-20261015-R1-C2-03/SPEC.md; research/sweep/fxreward_paper.py). No money, no orders,
# no network: it only reads the recorder's results\fxbook hour files, each one 15 min after the hour ends, and writes
# results\fxbook\paper\<YYYYMMDD>.jsonl.gz (window x variant rows) and results\fxreward-paper.jsonl (summaries,
# validation). Start it after start_fxbook_rec.ps1. The bar is read with
#   python research\sweep\fxreward_paper.py --report      (due 2026-10-24T12:00Z, READS_DUE fxreward-paper-1024)
# Stop it: New-Item -ItemType File C:\kals-repo\results\fxreward-paper.stop
$exe = "C:\Python314\python.exe"
$argv = @("-u", "research\sweep\fxreward_paper.py", "--follow")
if ($argv -contains "--live") { "REFUSING: --live in a paper quoter's argv"; exit 1 }
if (Test-Path "C:\kals-repo\results\fxreward-paper.stop") { "REFUSING: results\fxreward-paper.stop exists -- delete it first"; exit 1 }
$p = Start-Process -FilePath $exe -ArgumentList $argv -WorkingDirectory "C:\kals-repo" -WindowStyle Hidden `
    -RedirectStandardOutput "C:\kals-repo\results\fxreward-paper.out" -RedirectStandardError "C:\kals-repo\results\fxreward-paper.err" -PassThru
"started PAPER fxreward_paper --follow pid $($p.Id) at $((Get-Date).ToUniversalTime().ToString('u'))"
