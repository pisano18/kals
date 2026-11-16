# altfeed_install.ps1 -- SERVER ONLY. Registers the scheduled task KalsAltFeed: research\altfeed_rec.py, the zero-money
# recorder of the exchange prices behind ZECUSD_RTI, BNBUSD_RTI, NEARUSD_RTI and HYPEUSD_RTI (the four coins Kalshi
# relays only once a second). v-altfeed 2026-11-16, the operator 11-15: "wouldn't the fastest possible feed on all bots
# be best? ... also test that and remember to bring it back up once there's data to read". Read: READS_DUE altfeed-read.
#
# The task starts at boot and every 10 minutes; IgnoreNew means a running recorder is never doubled, so a crash or a
# reboot costs at most 10 minutes of tape. The recorder runs below normal priority, writes C:\kals-altfeed\<venue>\
# <YYYYMMDDTHH>_<start>.jsonl.gz plus status.json, and stops itself at its --until date (2027-01-15), over 10 GB, or under 10 GB
# free disk. It sends no orders and makes no Kalshi call of any kind (public exchange websockets only).
#
# Runs the recorder's self-test first and registers NOTHING if it fails. Safe to run again (-Force replaces the task).
# Its own output goes to results\altfeed_install.out.
#
# STOP: create C:\kals-repo\results\altfeed.stop (the recorder exits within 5 s and every later start exits at once).
# REVERT: Unregister-ScheduledTask -TaskName KalsAltFeed -Confirm:$false ; then the stop file, or end its python.
$py = "C:\Python314\python.exe"
$repo = "C:\kals-repo"
$script = Join-Path $repo "research\altfeed_rec.py"
$outDir = "C:\kals-altfeed"
$until = "2027-01-15T00:00Z"
$out = Join-Path $repo "results\altfeed_install.out"
function Say($m) { $line = "{0} {1}" -f (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"), $m; $line; Add-Content -Path $out -Value $line -Encoding utf8 }

Say "altfeed install: self-test first"
$st = & $py -I -u $script --self-test | Out-String
$code = $LASTEXITCODE
Add-Content -Path $out -Value $st -Encoding utf8
if ($code -ne 0) { Say "self-test FAILED (exit $code): the task was NOT registered"; exit 1 }
Say "self-test passed"

$argLine = "-I -u $script --out $outDir --until $until --max-gb 10 --min-free-gb 10"
$a = New-ScheduledTaskAction -Execute $py -WorkingDirectory $repo -Argument $argLine
$t1 = New-ScheduledTaskTrigger -AtStartup
$t2 = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) -RepetitionInterval (New-TimeSpan -Minutes 10)
$p = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -Priority 7
try {
    Register-ScheduledTask -TaskName "KalsAltFeed" -Action $a -Trigger $t1, $t2 -Principal $p -Settings $s -Force -ErrorAction Stop | Out-Null
} catch {
    Say "registering the task FAILED: $($_.Exception.Message)"; exit 1
}
if (-not (Get-ScheduledTask -TaskName "KalsAltFeed" -ErrorAction SilentlyContinue)) { Say "registering the task FAILED: the task is not there afterwards"; exit 1 }
Say "registered KalsAltFeed as SYSTEM: $py $argLine"
Start-ScheduledTask -TaskName "KalsAltFeed"
Start-Sleep -Seconds 90
$t = Get-ScheduledTask -TaskName "KalsAltFeed"; $i = Get-ScheduledTaskInfo -TaskName "KalsAltFeed"
Say ("task: {0}, {1}, runs as {2}, triggers {3}, last run {4}, last result {5}, next {6}" -f $t.TaskName, $t.State, $t.Principal.UserId, $t.Triggers.Count, $i.LastRunTime, $i.LastTaskResult, $i.NextRunTime)
$sf = Join-Path $outDir "status.json"
if (Test-Path $sf) {
    $j = Get-Content $sf -Raw | ConvertFrom-Json
    Say ("status: pid {0}, priority {1}, {2} bytes, stopping {3}" -f $j.pid, $j.priority, $j.out_bytes, $j.stopping)
    foreach ($v in $j.rows.PSObject.Properties) {
        foreach ($c in $v.Value.PSObject.Properties) { Say ("rows {0} {1}: book {2}, trade {3}" -f $v.Name, $c.Name, $c.Value.book, $c.Value.trade) }
    }
    foreach ($v in $j.venues.PSObject.Properties) { if ($v.Value.errors -gt 0) { Say ("venue {0}: {1} errors, last {2}" -f $v.Name, $v.Value.errors, $v.Value.last_error) } }
} else { Say "no status.json yet (the first one is written 60 s after start)" }
exit 0
