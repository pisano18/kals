# start_fxreward_v5.ps1 -- V5 engine calibration for the fxreward paper (a bounded BATCH job, not a service):
# the penny ladder's Kalshi-confirmed orders (results\ladder-live-orders.jsonl: placed / cancelled / live_fill) replayed
# through fxreward_paper's own queue engine on C:\kals\kalshi_data, READ-ONLY, one hour file at a time, streamed in
# bounded memory (v2, 2026-10-17: 60.6 s and 59 MB peak working set on 20261013T21; ~415 hours -> ~7 h). Hours that
# ended < 15 min before the start are left out (the collector is still writing them). Writes v5_start (code sha,
# argv, scope, hours), one v5_hour row per hour, and validation_v5 at the end to results\fxreward-paper.jsonl.
# Pass = engine contracts 0.67-1.5x live AND 60 s markout within 1c/contract of live (fifo_prorata). The bar uses ONLY
# a complete run with no --from/--to/--max-hours cut, written by the SAME code (sha) as the paper run: re-run after
# any code change. The resource protocol applies: ONE heavy job at a time -- do not start it while another tape job
# runs. Stop it: New-Item -ItemType File C:\kals-repo\results\fxreward-v5.stop (checked every 65,536 tape lines and
# between hours; a stopped run writes complete=false, which never counts).
$exe = "C:\Python314\python.exe"
$argv = @("-u", "research\sweep\fxreward_paper.py", "--v5", "--lock", "C:\kals-repo\results\fxreward-v5.lock",
  "--stop", "C:\kals-repo\results\fxreward-v5.stop")
if ($argv -contains "--live") { "REFUSING: --live in a calibration job's argv"; exit 1 }
if (Test-Path "C:\kals-repo\results\fxreward-v5.stop") { "REFUSING: results\fxreward-v5.stop exists -- delete it first"; exit 1 }
$p = Start-Process -FilePath $exe -ArgumentList $argv -WorkingDirectory "C:\kals-repo" -WindowStyle Hidden `
    -RedirectStandardOutput "C:\kals-repo\results\fxreward-v5.out" -RedirectStandardError "C:\kals-repo\results\fxreward-v5.err" -PassThru
"started V5 calibration pid $($p.Id) at $((Get-Date).ToUniversalTime().ToString('u'))"
