# pin_restart_flat.ps1 -- 2026-11-04. For the OPERATOR (phone /approve pinrestart). Restarts the live pin bot ONCE on the
# build it already runs, with nothing edited, through its own hand launcher C:\kals-live-0925n\restart_bot.ps1 (the file
# every pin deploy since 10-04 has restarted through: it checks the code file's sha, refuses while pin holds an open bet,
# stops only the live pinrun and starts it again on the same argv).
# WHY: pin's 1.5x boosts (--band-mult 0.955 0.981 1.5 and --late-mult 1.5) switch themselves OFF for the rest of a run after
# a losing boosted leg (band_boost_off / late_boost_off) and only a restart puts them back on. From the 0925t build
# (11-04) pin runs with --boost-rail off, so that rail never trips unless the launcher is changed back to any/side;
# research\pinrules_watch.py still sends the phone an urgent alert if a trip record ever appears and names this item.
# Also the plain way to restart pin while flat (a launcher edit to load, a stuck run), with nothing edited by this script.
# STEPS: 1) refuse unless a live pin is running (pid file first, then the command lines; a dead pin is watch_bot's job to
# restart) and no restart_bot wrapper is already running; 2) wait until research\pinflat.py says FLAT (pin is flat about
# 14 minutes of every 15; this gives up after 25 minutes); 3) launch restart_bot by WMI exactly as results\pin_oddsmult.ps1
# does, its own output to results\pin_restart_flat_restart.out; 4) wait for it and copy its verdict into this log; if it
# refused because pin had just bought again, back to step 2 (at most 3 tries).
# Log: results\pin_restart_flat.out (read back by the phone when this ends).
$log = 'C:\kals-repo\results\pin_restart_flat.out'
$rout = 'C:\kals-repo\results\pin_restart_flat_restart.out'
$py = 'C:\Python314\python.exe'
$launcher = 'C:\kals-live-0925n\restart_bot.ps1'
$pidfile = 'C:\kals-repo\results\pinrun-live.pid'
function Say($m) { $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m; Write-Output $l; Add-Content -Path $log -Value $l }
function LivePinPids {
  $ids = @()
  if (Test-Path $pidfile) {
    $w = (Get-Content $pidfile -Raw -ErrorAction SilentlyContinue)
    if ($w -and $w.Trim() -match '^\d+$' -and (Get-Process -Id ([int]$w.Trim()) -ErrorAction SilentlyContinue)) { $ids += [int]$w.Trim() }
  }
  Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*pinrun.py*' -and $_.CommandLine -like '*--live*' } | ForEach-Object { if ($ids -notcontains $_.ProcessId) { $ids += $_.ProcessId } }
  return $ids
}
function Wrappers { @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*restart_bot.ps1*' -and $_.ProcessId -ne $PID } | ForEach-Object { $_.ProcessId }) }
Say "start"
# ---- 1. preconditions: the launcher, a live pin, no restart already under way
if (-not (Test-Path $launcher)) { Say "REFUSED: $launcher is not there; nothing done"; exit 1 }
$pins = @(LivePinPids)
if ($pins.Count -eq 0) { Say "REFUSED: no live pin process is running (a dead pin is restarted by watch_bot by itself); nothing done"; exit 1 }
Say ("live pin pid(s): " + ($pins -join ','))
$w = @(Wrappers)
if ($w.Count -gt 0) { Say ("REFUSED: a restart_bot wrapper is already running (pid " + ($w -join ',') + "); nothing done"); exit 1 }
$sha = (Get-FileHash -Algorithm SHA256 -Path $launcher).Hash.ToLower().Substring(0, 12)
Say "launcher $launcher (sha12 $sha): the same build and argv it already runs, nothing edited"
# ---- 2..4. wait for flat, restart through the launcher, read its verdict
$deadline = (Get-Date).AddMinutes(25)
$saidWait = $false
for ($try = 1; $try -le 3; $try++) {
  while ($true) {
    $fo = & $py 'C:\kals-repo\research\pinflat.py' 2>&1 | Out-String
    $fc = $LASTEXITCODE
    if ($fc -eq 0) { Say ("pin is flat: " + $fo.Trim()); break }
    if ((Get-Date) -gt $deadline) { Say ("GAVE UP: pin was not flat within 25 minutes (last answer: " + $fo.Trim() + "); nothing restarted; approve again later"); exit 1 }
    if (-not $saidWait) { Say ("pin holds a bet, waiting for flat (pinflat exit $fc): " + $fo.Trim()); $saidWait = $true }
    Start-Sleep -Seconds 15
  }
  $saidWait = $false
  $cmd = 'cmd /c "powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-live-0925n\restart_bot.ps1 > C:\kals-repo\results\pin_restart_flat_restart.out 2>&1"'
  $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = 'C:\kals-live-0925n' }
  Say ("restart launched (try $try), wrapper pid {0} (return {1}); its output: $rout" -f $r.ProcessId, $r.ReturnValue)
  if ($r.ReturnValue -ne 0) { Say "WMI refused to start the restart wrapper; nothing restarted"; exit 1 }
  $p = Get-Process -Id $r.ProcessId -ErrorAction SilentlyContinue
  if ($p) { $p.WaitForExit(240000) | Out-Null }
  $txt = ''
  if (Test-Path $rout) { $txt = [string](Get-Content $rout -Raw -ErrorAction SilentlyContinue) }
  if ($txt -match 'pinrun running: pid (\d+)') { Say ("DONE: pin restarted on the same build and argv, new pid " + $matches[1] + " (a fresh run: boosts on, run loss budget and attempt counters reset)"); exit 0 }
  if ($txt -match 'REFUSING: the bot is holding a position') { Say "restart_bot refused: pin bought again between the flat check and the restart; waiting for flat again"; continue }
  $tail = @(($txt -split "`r?`n") | Where-Object { $_.Trim() } | Select-Object -Last 6)
  Say ("restart_bot did not report a running pin; its last lines: " + ($tail -join ' | ') + "; if pin is down, watch_bot restarts it within minutes")
  exit 1
}
Say "GAVE UP after 3 tries: pin kept holding a bet at the restart moment; nothing restarted; approve again later"
exit 1
