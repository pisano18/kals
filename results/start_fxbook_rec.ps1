# start_fxbook_rec.ps1 -- READ-ONLY FX 15-minute book recorder for the fxreward PAPER test
# (spec .sweep/hunt-2026-10-15/spec-20261015-R1-C2-03/SPEC.md; built 2026-10-17, research/sweep/fxbook_rec.py).
# Kalshi WebSocket (signed handshake only, market data only) for KXEURUSD15M KXGBPUSD15M KXUSDJPY15M KXAUDUSD15M
# KXUSDCAD15M + Kraken public WebSocket books/trades + paced public REST GETs (>= 2 s apart, 429 -> 10 s back-off;
# market discovery every 300 s, not the spec's 60 s, to spare the per-IP limit the live bots share -- see the .py).
# No order verb exists in the file (its self-test scans for one). Writes results\fxbook\<channel>\<YYYYMMDDTHH>.jsonl.gz
# and results\fxbook-rec.jsonl. Rails: stop file, OS lock, free disk < 15 GB -> stop, results\fxbook > 3 GB -> stop,
# RSS > 150 MB -> stop.
# BEFORE THE FIRST START (not done by the builder): add /results/fxbook/ and the fxbook-rec/fxreward-paper log+lock
# lines to .gitignore, and the READS_DUE entry fxreward-paper-1024, in the same commit; spec risk 4: watch the
# collector / pin / ladder / forecaster logs for new ws_error in the first 30 minutes (a 6th socket on the shared key).
# Stop it: New-Item -ItemType File C:\kals-repo\results\fxbook-rec.stop   (closes its files, exits within ~1 s)
$exe = "C:\Python314\python.exe"
$argv = @("-u", "research\sweep\fxbook_rec.py")
if ($argv -contains "--live") { "REFUSING: --live in a read-only recorder's argv"; exit 1 }
if (Test-Path "C:\kals-repo\results\fxbook-rec.stop") { "REFUSING: results\fxbook-rec.stop exists -- delete it first"; exit 1 }
$p = Start-Process -FilePath $exe -ArgumentList $argv -WorkingDirectory "C:\kals-repo" -WindowStyle Hidden `
    -RedirectStandardOutput "C:\kals-repo\results\fxbook-rec.out" -RedirectStandardError "C:\kals-repo\results\fxbook-rec.err" -PassThru
"started READ-ONLY fxbook_rec pid $($p.Id) at $((Get-Date).ToUniversalTime().ToString('u'))"
