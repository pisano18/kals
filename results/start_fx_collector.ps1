# start_fx_collector.ps1 -- start the READ-ONLY 15-MINUTE FX / commodity recorder, hidden, for 7 days.
#
#   powershell -ExecutionPolicy Bypass -File C:\kals-repo\results\start_fx_collector.ps1
#
# Runs C:\kals-repo\research\hourly_collector.py --fifteen-min --minutes 10080 (7 days) with stdout/stderr
# in results\fx-collector.out / .err. It records to C:\kals\kalshi_data_fx (never the v4 root, never the
# hourly root). This is a SECOND instance of the same recorder: it REFUSES to start when ITS OWN pid file
# (results\fx-collector.pid, written by the recorder itself) names a live process, or when any python.exe
# already runs hourly_collector.py WITH --fifteen-min. It never reads, writes or checks the hourly
# instance's pid file (results\hourly-collector.pid) and never stops or restarts anything.
# Exit codes: 0 started, 2 refused (already running), 1 the process died within 10 s (its .err tail is printed).
$ErrorActionPreference = "Stop"
$repo = "C:\kals-repo"
$res = "$repo\results"
$py = "C:\Python314\python.exe"
$script = "$repo\research\hourly_collector.py"
$pidfile = "$res\fx-collector.pid"
$out = "$res\fx-collector.out"
$err = "$res\fx-collector.err"
$tape = "C:\kals\kalshi_data_fx"

function Say($msg) { Write-Output ("{0}  {1}" -f (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"), $msg) }

if (-not (Test-Path $py)) { Say "python not found at $py"; exit 1 }
if (-not (Test-Path $script)) { Say "recorder not found at $script"; exit 1 }

# 1. OUR pid file, written by the recorder: {"pid": N, "started": ..., "argv": [...]}
if (Test-Path $pidfile) {
    $oldPid = 0
    try { $oldPid = [int]((Get-Content $pidfile -Raw | ConvertFrom-Json).pid) } catch { $oldPid = 0 }
    if ($oldPid -gt 0) {
        $alive = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
        if ($alive) {
            Say "REFUSED: fx collector (hourly_collector.py --fifteen-min) already running (pid $oldPid per $pidfile, started $((Get-Item $pidfile).LastWriteTime))"
            exit 2
        }
        Say "stale pid file (pid $oldPid is not alive) -- the recorder will take it over"
    } else {
        Say "unreadable pid file $pidfile -- the recorder will take it over"
    }
}

# 2. a python.exe whose command line names the script WITH --fifteen-min (the hourly instance runs the same
#    script without the flag and is left alone; empty command lines are processes this shell cannot inspect;
#    they are reported, and the pid file above remains the deciding check).
$procs = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'")
$running = @($procs | Where-Object { $_.CommandLine -like '*hourly_collector.py*' -and $_.CommandLine -like '*--fifteen-min*' -and $_.CommandLine -notlike '*--selftest*' -and $_.CommandLine -notlike '*--version-check*' })
if ($running.Count -gt 0) {
    Say "REFUSED: hourly_collector.py --fifteen-min already running: pid(s) $(($running | ForEach-Object { $_.ProcessId }) -join ',')"
    exit 2
}
$hourly = @($procs | Where-Object { $_.CommandLine -like '*hourly_collector.py*' -and $_.CommandLine -notlike '*--fifteen-min*' -and $_.CommandLine -notlike '*--selftest*' }).Count
if ($hourly -gt 0) { Say "note: the hourly instance is running ($hourly process); it is a separate instance and is left alone" }
$blind = @($procs | Where-Object { -not $_.CommandLine }).Count
if ($blind -gt 0) { Say "note: $blind python process(es) hide their command line; relying on the pid file" }

# 3. keep the previous run's logs (ours only)
foreach ($f in @($out, $err)) {
    if (Test-Path $f) { Move-Item $f "$f.prev" -Force }
}
if (-not (Test-Path $tape)) { New-Item -ItemType Directory -Force $tape | Out-Null }

# 4. start hidden. The recorder sets its own BELOW_NORMAL priority, writes OUR pid file, guards the disk
#    (< 8 GB free -> exits with code 2) and stops by itself after 10080 minutes.
$pyArgs = @("-u", $script, "--fifteen-min", "--minutes", "10080", "--out", $tape, "--pidfile", $pidfile)
Say "starting: $py $($pyArgs -join ' ')"
$p = Start-Process -FilePath $py -ArgumentList $pyArgs -WorkingDirectory $repo -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $out -RedirectStandardError $err
Start-Sleep -Seconds 10
$live = Get-Process -Id $p.Id -ErrorAction SilentlyContinue
if ($live) {
    Say "started pid $($p.Id); log $out"
    if (Test-Path $out) { Get-Content $out -Tail 5 }
    exit 0
} else {
    Say "FAILED: pid $($p.Id) exited within 10 s. stderr tail:"
    if (Test-Path $err) { Get-Content $err -Tail 20 }
    if (Test-Path $out) { Get-Content $out -Tail 10 }
    exit 1
}
