# kalshi_watch_install.ps1 -- SERVER ONLY. Registers the scheduled task KalsKalshiWatch: research\kalshi_watch.py, one
# scan every 30 minutes (and at startup), as SYSTEM, exactly like KalsPinRulesWatch (research\pinrules_watch.py, every
# 5 minutes). v-kwatch 2026-11-07 (the operator: "add some feedback and alarms where we have something that runs a scan
# to catch any kalshi changes").
#
# What the task does each run (research\kalshi_watch.py's docstring has the whole list): Kalshi's API changelog, 20
# SIGNED Kalshi reads with pin's key (series, one open market per series, scheduled fee changes, exchange status and
# schedule, the balance answer's shape only), the CRYPTO15M contract terms PDF, CF Benchmarks' exchanges PDF and status
# page, the new lines of pin's live log, free disk, Python package versions and the live launchers' sha256. Every change
# is a phone message, old value beside new; urgent ones ring even in quiet hours. The phone's /watch shows it all.
# No orders. No unsigned call to Kalshi's API. State: results\kalshi_watch_state.json; log: results\kalshi_watch.log.
#
# Runs its self-test first (no network, no key, no Telegram) and registers NOTHING if it fails. Safe to run again
# (-Force replaces the task). The first scan sets the baseline and sends ONE "baseline set" note to the phone.
# Its own output goes to results\kalshi_watch_install.out (so it reads the same from ssh or from the phone's /approve).
#
# OFF FROM THE PHONE: /watch off (asks, then /watch off yes) writes results\kalshi_watch.stop: every run exits at once,
# scans nothing, sends nothing. /watch on removes it.
# REVERT: Unregister-ScheduledTask -TaskName KalsKalshiWatch -Confirm:$false
#         (the state file results\kalshi_watch_state.json can stay; a later install picks the baseline up from it)
$py = "C:\Python314\python.exe"
$repo = "C:\kals-repo"
$script = Join-Path $repo "research\kalshi_watch.py"
$out = Join-Path $repo "results\kalshi_watch_install.out"
function Say($m) { $line = "{0} {1}" -f (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"), $m; $line; Add-Content -Path $out -Value $line -Encoding utf8 }

Say "kalshi_watch install: self-test first"
$st = & $py -I -u $script --self-test | Out-String
$code = $LASTEXITCODE
Add-Content -Path $out -Value $st -Encoding utf8
if ($code -ne 0) { Say "self-test FAILED (exit $code): the task was NOT registered"; exit 1 }
Say "self-test passed"

$a = New-ScheduledTaskAction -Execute "C:\Python314\python.exe" -WorkingDirectory "C:\kals-repo" `
    -Argument "-I -u C:\kals-repo\research\kalshi_watch.py"
$t1 = New-ScheduledTaskTrigger -AtStartup
$t2 = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) -RepetitionInterval (New-TimeSpan -Minutes 30)
$p = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
try {
    Register-ScheduledTask -TaskName "KalsKalshiWatch" -Action $a -Trigger $t1, $t2 -Principal $p -Settings $s -Force -ErrorAction Stop | Out-Null
} catch {
    Say "registering the task FAILED: $($_.Exception.Message)"; exit 1
}
if (-not (Get-ScheduledTask -TaskName "KalsKalshiWatch" -ErrorAction SilentlyContinue)) { Say "registering the task FAILED: the task is not there afterwards"; exit 1 }
Start-ScheduledTask -TaskName "KalsKalshiWatch"
Start-Sleep -Seconds 90
$t = Get-ScheduledTask -TaskName "KalsKalshiWatch"; $i = Get-ScheduledTaskInfo -TaskName "KalsKalshiWatch"
Say ("task: {0}, {1}, runs as {2}, triggers {3}, last run {4}, last result {5}, next {6}" -f $t.TaskName, $t.State, $t.Principal.UserId, $t.Triggers.Count, $i.LastRunTime, $i.LastTaskResult, $i.NextRunTime)
if (Test-Path (Join-Path $repo "results\kalshi_watch.log")) {
    Get-Content (Join-Path $repo "results\kalshi_watch.log") -Tail 3 | ForEach-Object { Say "log: $_" }
} else { Say "no results\kalshi_watch.log yet (the first scan takes about a minute: 20 signed reads 1 s apart)" }
exit 0
