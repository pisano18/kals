# log_rotate_install.ps1 -- 2026-11-07. SERVER ONLY. Registers the scheduled task KalsLogRotate: research\log_rotate.py
# --apply once a day at 09:40 UTC (04:40 AM ET while the clocks are on EST, 05:40 AM ET on EDT), as SYSTEM like
# KalsBoot and KalsPinRulesWatch. Each run gzips the FINISHED pin logs log_rotate.py's POLICY names (pintraj-live-* and
# pinrun-paper-* after 48 h, pinrun-live-* after 60 days; never a bot's newest log, never a file held open or tracked by
# git) into results\archive\, checks each .gz reads back to the same sha256 before the plain file goes, and logs to
# results\log_rotate.log (status and the weeks-of-disk-left projection: results\log_rotate_status.json).
# WHY: 26.3 GB free on 11-07, ~1.46 GB a week, nothing rotated: the disk fills around March 2027.
# STEPS: 1) log_rotate.py --self-test must pass (else nothing is installed); 2) git is found (this shell's PATH, the
# MACHINE Path SYSTEM uses, then Program Files) and its path is written INTO the task (--git), so SYSTEM never depends
# on its own PATH; none found = every run moves nothing (it refuses to guess what git tracks) -- said loudly, and the
# phone alerts "git unreadable" after the first run; 3) a dry run is printed (what the first run will move; nothing
# changes); 4) the task is registered (replacing any older one), first run at the NEXT 09:40 UTC (never at once by
# surprise; -RunNow starts one now); 5) results\log_rotate_installed.json is written (the phone's "installed but never
# ran" alarm reads it) and results\pinphone.update asks the phone to reload, so the phone reads the archive BEFORE the
# first run moves anything (11-07 review: an old phone would drop archived paper logs from /brief until reloaded).
#   powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-repo\results\log_rotate_install.ps1
#   ... -DryRunOnly     steps 1-3 only, nothing registered, nothing written but this script's log
#   ... -RunNow         also start the first run now (the backlog: ~2 GB of old trajectory and paper logs); give the
#                       phone its ~10 min reload first if the archived logs must never drop out of /brief meanwhile
#   ... -Uninstall      remove the task and the marker (archives already written stay; nothing is put back)
#   ... -NoPhoneReload  do not write results\pinphone.update (the phone was already reloaded on this code; a reload
#                       takes the phone offline for up to ~10 min: its self-tests, then boot_all's next start)
# Log: results\log_rotate_install.out
param([switch]$DryRunOnly, [switch]$RunNow, [switch]$Uninstall, [switch]$NoPhoneReload)
$repo = 'C:\kals-repo'
$py = 'C:\Python314\python.exe'
$script = "$repo\research\log_rotate.py"
$log = "$repo\results\log_rotate_install.out"
$marker = "$repo\results\log_rotate_installed.json"
$phoneFlag = "$repo\results\pinphone.update"
$task = 'KalsLogRotate'
function Say($m) { $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m; Write-Output $l; Add-Content -Path $log -Value $l }
Say "start"
if ($Uninstall) {
  if (Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $task -Confirm:$false
    Say "removed the scheduled task $task (the archive in results\archive\ is kept)"
  } else { Say "no scheduled task $task to remove" }
  if (Test-Path $marker) { Remove-Item -LiteralPath $marker -Force; Say "removed $marker (the phone stops watching the rotation)" }
  exit 0
}
if (-not (Test-Path $script)) { Say "REFUSED: $script is not there (merge the commit first); nothing installed"; exit 1 }
# ---- 1. the self-test
$so = (& $py -I -u $script --self-test 2>&1 | Out-String)
$code = $LASTEXITCODE
$nfail = ([regex]::Matches($so, '(?m)^  FAIL ')).Count
if ($code -ne 0 -or $so -notmatch 'log_rotate self-test: OK' -or $nfail -ne 0) {
  Say ("REFUSED: log_rotate self-test failed (exit $code, $nfail FAIL lines); nothing installed. Its output:`r`n" + $so.Trim())
  exit 1
}
Say ("self-test passed ({0} ok lines)" -f ([regex]::Matches($so, '(?m)^  ok   ')).Count)
# ---- 2. git: this shell's PATH, then the MACHINE Path (SYSTEM's), then the usual install folders
$git = $null
$cmd = Get-Command git.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if ($cmd) { $git = $cmd.Source }
if (-not $git) {
  $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
  $gitDir = @($machinePath -split ';' | Where-Object { $_ -and (Test-Path (Join-Path $_ 'git.exe')) }) | Select-Object -First 1
  if ($gitDir) { $git = Join-Path $gitDir 'git.exe' }
}
if (-not $git) {
  $git = @('C:\Program Files\Git\cmd\git.exe', 'C:\Program Files\Git\bin\git.exe', 'C:\Program Files (x86)\Git\cmd\git.exe') |
    Where-Object { Test-Path $_ } | Select-Object -First 1
}
if ($git) { Say "git for the task: $git (written into the task, so SYSTEM's own PATH does not matter)" }
else { Say "WARNING: no git.exe found (PATH, machine Path, Program Files), so every run will move NOTHING (it refuses to guess what git tracks); the phone will say 'git unreadable' after the first run. Install Git for Windows, then run this again." }
$gitArg = @()
if ($git) { $gitArg = @('--git', $git) }
# ---- 3. the dry run (nothing changes), with the same git the task will use
$dry = (& $py -I -u $script --dry-run @gitArg 2>&1 | Out-String)
$lines = @(($dry -split "`r?`n") | Where-Object { $_.Trim() })
$moves = @($lines | Where-Object { $_ -like 'would move *' })
foreach ($l in ($lines | Where-Object { $_ -notlike 'would move *' })) { Say ("dry run: " + $l) }
Say ("dry run: {0} file(s) would move; the first 5: {1}" -f $moves.Count, (($moves | Select-Object -First 5) -join ' | '))
if ($DryRunOnly) { Say "DRY RUN ONLY: nothing registered"; exit 0 }
# ---- 4. the task: daily at 09:40 UTC, in the server's own clock; the first run is the NEXT 09:40 UTC
$utc = [datetime]::SpecifyKind([datetime]::UtcNow.Date.AddHours(9).AddMinutes(40), [DateTimeKind]::Utc)
if ($utc -le [datetime]::UtcNow) { $utc = $utc.AddDays(1) }
$at = $utc.ToLocalTime()
$argLine = "-I -u $script --apply"
if ($git) { $argLine += " --git `"$git`"" }
$a = New-ScheduledTaskAction -Execute $py -WorkingDirectory $repo -Argument $argLine
$t = New-ScheduledTaskTrigger -Daily -At $at
$p = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2) -Priority 7
try {
  Register-ScheduledTask -TaskName $task -Action $a -Trigger $t -Principal $p -Settings $s -Force -ErrorAction Stop | Out-Null
} catch { Say ("FAILED to register $task" + ": " + $_.Exception.Message); exit 1 }
$i = Get-ScheduledTaskInfo -TaskName $task
Say ("installed $task as SYSTEM: daily at {0} server time (09:40 UTC), first run {1}; action: {2} {3}" -f $at.ToString('HH:mm'), $i.NextRunTime, $py, $argLine)
# ---- 5. the phone: the marker its alarm reads, and a reload so it reads the archive before anything moves
$mk = @{ installed_t = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds(); task = $task; git = $git; at_utc = '09:40' } | ConvertTo-Json -Compress
[IO.File]::WriteAllText($marker, $mk)
Say "wrote $marker (the phone alerts if no run finishes within 36 h)"
if ($NoPhoneReload) { Say "-NoPhoneReload: the phone was not asked to reload (it must already run this code, or archived logs drop out of /brief until it does)" }
else {
  [IO.File]::WriteAllText($phoneFlag, "log_rotate_install.ps1: read the archive before the first rotation`r`n")
  Say "asked the phone to reload ($phoneFlag): it runs its self-tests and comes back on the new code within ~10 min"
}
if ($RunNow) {
  Start-ScheduledTask -TaskName $task
  Say "started the first run now; it writes results\log_rotate.log as it goes"
}
exit 0
