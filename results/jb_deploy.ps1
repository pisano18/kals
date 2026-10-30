# jb_deploy.ps1 -- 2026-10-30 (LS25 live stage 1, operator: "Run build and start jump band buyer").
# Server side. -Stage dryrun: pull, selftest, start a 3-minute --live --dry-run via WMI (keys + signed cash read + websockets,
# no orders) into its own log. -Stage live: start the real bot via WMI: 5 contracts a buy, subaccount 3 ($50, crypto pool 2),
# stop line -$25, log results\jumpband-live.jsonl. Log of this script: results\jb_deploy.out
param([ValidateSet('dryrun', 'live')][string]$Stage = 'dryrun')
$repo = 'C:\kals-repo'; $res = "$repo\results"; $log = "$res\jb_deploy.out"
function Say($m) { ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $m) | Out-File $log -Append -Encoding utf8; Write-Output $m }
function JbPids($pat) { @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like $pat } | ForEach-Object { $_.ProcessId }) }
Set-Location $repo
Say "stage $Stage; HEAD $(git rev-parse --short HEAD)"
if ($Stage -eq 'dryrun') {
    $st = & C:\Python314\python.exe research\cleanroom\jumpband_live.py --selftest 2>&1 | Select-Object -Last 2
    Say ("selftest exit {0}: {1}" -f $LASTEXITCODE, ($st -join ' | '))
    if ($LASTEXITCODE -ne 0) { Say "selftest FAILED -- stopping"; exit 1 }
    if (Test-Path "$res\jumpband-dryrun.jsonl") { Remove-Item "$res\jumpband-dryrun.jsonl" -Force }
    $cmd = 'cmd /c "C:\Python314\python.exe -u research\cleanroom\jumpband_live.py --live --dry-run --subaccount 3 --max-contracts 5 --minutes 3 --log results\jumpband-dryrun.jsonl > results\jumpband-dryrun-stdout.log 2>&1"'
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine = $cmd; CurrentDirectory = $repo }
    Say ("dry-run launched: return {0} pid {1}" -f $r.ReturnValue, $r.ProcessId)
    exit 0
}
if ($Stage -eq 'live') {
    if ((JbPids '*jumpband_live.py*--live*--dry-run*').Count -gt 0) { Say "a dry-run is still running -- stopping"; exit 1 }
    if ((JbPids '*jumpband_live.py*--live*').Count -gt 0) { Say "a live jump-band bot is ALREADY running -- stopping"; exit 1 }
    if (Test-Path "$res\jumpband-live.stop") { Say "stop file exists -- stopping"; exit 1 }
    $cmd = 'cmd /c "C:\Python314\python.exe -u research\cleanroom\jumpband_live.py --live --subaccount 3 --max-contracts 5 --minutes 20160 > results\jumpband-live-stdout.log 2>&1"'
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine = $cmd; CurrentDirectory = $repo }
    Say ("LIVE launched: return {0} pid {1}" -f $r.ReturnValue, $r.ProcessId)
    Start-Sleep -Seconds 25
    Say ("live pids now: " + ((JbPids '*jumpband_live.py*--live*') -join ','))
    if (Test-Path "$res\jumpband-live.jsonl") { Get-Content "$res\jumpband-live.jsonl" -Tail 3 | ForEach-Object { Say ("log: " + $_.Substring(0, [Math]::Min(300, $_.Length))) } }
    if (Test-Path "$res\jumpband-live-stdout.log") { Get-Content "$res\jumpband-live-stdout.log" -Tail 5 | ForEach-Object { Say ("out: " + $_) } }
    exit 0
}
