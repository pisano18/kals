# restart_ladder_1003.ps1 -- v-ladder-limbo + v-ladder-caps (market x2) on the live ladder (subaccount 1), 2026-10-03.
# Validates first (self-test with the NEW argv, one live ladder, boot_all line present), then: keep-alive line ->
# new argv, stop file -> old ladder cancels its bids and exits -> wait out boot_all -> start the new one.
# REVERT: results/VERSIONS.md v-ladder-caps.
param([switch]$DryRun)
$ErrorActionPreference = "Stop"
$repo = "C:\kals-repo"; $res = "$repo\results"; $py = "C:\Python314\python.exe"
function Say($m) { $l = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"), $m; Write-Output $l; Add-Content -Path "$res\restart_ladder_1003.log" -Value $l -Encoding utf8 }
function Live($like) { @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like $like }) }
function BootAlive() { @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object { $_.CommandLine -like '*boot_all.ps1*' }).Count -gt 0 }

$lad = @("-u","research\cleanroom\ladder_live.py","--subaccount","1","--live","--auto-size","--market-cap-x","2","--minutes","10080")
$oldLine = 'a = @("-u", "research\cleanroom\ladder_live.py", "--subaccount", "1", "--live", "--auto-size", "--minutes", "10080");'
$newLine = 'a = @("-u", "research\cleanroom\ladder_live.py", "--subaccount", "1", "--live", "--auto-size", "--market-cap-x", "2", "--minutes", "10080");'

Say "validating (DryRun=$DryRun)"
$out = & $py @($lad + @("--selftest")) | Out-String
if ($LASTEXITCODE -ne 0 -or $out -notmatch "ladder_live self-test PASSED") { Say "SELF-TEST FAILED with the new argv"; exit 1 }
Say "self-test ok with the new argv"
if (Test-Path "$res\ladder-live.stop") { Say "stop file present, refusing"; exit 1 }
$old = @(Live '*ladder_live.py*--live*')
if ($old.Count -ne 1) { Say "expected exactly one live ladder, found $($old.Count) -- refusing"; exit 1 }
$boot = Get-Content "$repo\boot_all.ps1" -Raw
if (-not $boot.Contains($oldLine)) { Say "boot_all.ps1 does not contain the expected ladder line -- refusing"; exit 1 }
$nb = $boot.Replace($oldLine, $newLine)
$errs = $null; [void][System.Management.Automation.Language.Parser]::ParseInput($nb, [ref]$null, [ref]$errs)
if ($errs.Count) { Say "edited boot_all.ps1 does not parse -- refusing"; exit 1 }
Say "ok: old ladder pid $($old[0].ProcessId); boot_all line found; edit parses"
if ($DryRun) { Say "DRY RUN: nothing changed"; exit 0 }

Copy-Item "$repo\boot_all.ps1" "$res\boot_all.before-laddercaps.ps1"
Set-Content -Path "$repo\boot_all.ps1" -Value $nb -Encoding utf8 -NoNewline
Say "keep-alive updated (backup results\boot_all.before-laddercaps.ps1)"
New-Item -ItemType File -Path "$res\ladder-live.stop" -Force | Out-Null
for ($i = 0; $i -lt 90 -and (Get-Process -Id $old[0].ProcessId -ErrorAction SilentlyContinue); $i++) { Start-Sleep 1 }
if (Get-Process -Id $old[0].ProcessId -ErrorAction SilentlyContinue) { Say "old ladder did not exit in 90 s -- stop file kept; check by hand"; exit 1 }
for ($i = 0; $i -lt 60 -and (BootAlive); $i++) { Start-Sleep 1 }
Remove-Item "$res\ladder-live.stop" -Force
$p = Start-Process -FilePath $py -ArgumentList $lad -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput "$res\ladder-live-stdout.log" -RedirectStandardError "$res\ladder-live-stderr.log" -PassThru
Say "started ladder $($p.Id): $($lad -join ' ')"
