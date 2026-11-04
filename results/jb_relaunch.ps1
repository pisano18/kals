# jb_relaunch.ps1 -- 2026-11-04. For the OPERATOR (phone /approve jbrelaunch). Starts the jump band LIVE arm again with the
# SAME command as results\jb_deploy.ps1 -Stage live (10-30 stage 1): 5 contracts a buy, subaccount 3 (the $50 crypto
# pool-2 pot), --minutes 20160 (14 days), stop line -$25 in the code, log results\jumpband-live.jsonl. Meant for AFTER the
# running arm ends itself (its 14 days are up about 11-13 03:13 ET; neither arm is in boot_all), never alongside it.
# REFUSES if: a live or dry-run jump band process is running (never two live bots on one account); results\jumpband-live.stop
# exists (the bot's stop line or a human stood it down; delete the file by hand first if the relaunch is really wanted); or
# the bot's own offline self-test fails on the server's code. The paper arm (jumpband_live.py without --live) does not block it.
# Then it launches through WMI exactly as jb_deploy.ps1 does (detached from this script and from the phone), waits 25 s and
# reads back the bot's first lines. Log: results\jb_relaunch.out (read back by the phone when this ends).
$repo = 'C:\kals-repo'; $res = "$repo\results"; $log = "$res\jb_relaunch.out"
function Say($m) { $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m; Write-Output $l; Add-Content -Path $log -Value $l }
function JbPids($pat) { @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like $pat } | ForEach-Object { $_.ProcessId }) }
Set-Location $repo
Say "start; HEAD $(git rev-parse --short HEAD)"
# ---- 1. refusals
$dry = @(JbPids '*jumpband_live.py*--live*--dry-run*')
if ($dry.Count -gt 0) { Say ("REFUSED: a jump band dry-run is still running (pid " + ($dry -join ',') + "); nothing launched"); exit 1 }
$live = @(JbPids '*jumpband_live.py*--live*')
if ($live.Count -gt 0) { Say ("REFUSED: a live jump band bot is ALREADY running (pid " + ($live -join ',') + "); never two live bots on one account; nothing launched"); exit 1 }
if (Test-Path "$res\jumpband-live.stop") { Say "REFUSED: $res\jumpband-live.stop exists (the bot's stop line or a human stood it down); delete it by hand first if the relaunch is really wanted; nothing launched"; exit 1 }
$paper = @(JbPids '*jumpband_live.py*')
if ($paper.Count -gt 0) { Say ("note: the paper arm is running (pid " + ($paper -join ',') + "); it does not block a live relaunch") }
# ---- 2. the bot's own self-test on the server's code, before anything starts
$st = & C:\Python314\python.exe research\cleanroom\jumpband_live.py --selftest 2>&1 | Select-Object -Last 2
Say ("selftest exit {0}: {1}" -f $LASTEXITCODE, ($st -join ' | '))
if ($LASTEXITCODE -ne 0) { Say "REFUSED: the self-test failed; nothing launched"; exit 1 }
# ---- 3. the launch, exactly jb_deploy.ps1 -Stage live
$cmd = 'cmd /c "C:\Python314\python.exe -u research\cleanroom\jumpband_live.py --live --subaccount 3 --max-contracts 5 --minutes 20160 > results\jumpband-live-stdout.log 2>&1"'
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine = $cmd; CurrentDirectory = $repo }
Say ("LIVE launched: return {0} pid {1}" -f $r.ReturnValue, $r.ProcessId)
if ($r.ReturnValue -ne 0) { Say "WMI refused to start it; nothing is running"; exit 1 }
Start-Sleep -Seconds 25
Say ("live pids now: " + ((JbPids '*jumpband_live.py*--live*') -join ','))
if (Test-Path "$res\jumpband-live.jsonl") { Get-Content "$res\jumpband-live.jsonl" -Tail 3 | ForEach-Object { Say ("log: " + $_.Substring(0, [Math]::Min(300, $_.Length))) } }
if (Test-Path "$res\jumpband-live-stdout.log") { Get-Content "$res\jumpband-live-stdout.log" -Tail 5 | ForEach-Object { Say ("out: " + $_) } }
exit 0
