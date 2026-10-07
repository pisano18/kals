# restart_ladder_1007.ps1 -- v-ladder-capfix on the live ladder (subaccount 1), 2026-10-07.
# Same argv as before (boot_all.ps1 already carries it; it is NOT edited). Validates first (self-test with the live argv,
# exactly one live ladder, no stop file, boot_all line present), then: stop file -> old ladder cancels its bids and exits
# -> wait out boot_all -> delete the stop file -> start the new one -> confirm one live ladder + its start record.
# REVERT: results/VERSIONS.md v-ladder-capfix.
param([switch]$DryRun)
$ErrorActionPreference = "Stop"
$repo = "C:\kals-repo"; $res = "$repo\results"; $py = "C:\Python314\python.exe"
function Say($m) { $l = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"), $m; Write-Output $l; Add-Content -Path "$res\restart_ladder_1007.log" -Value $l -Encoding utf8 }
function Live($like) { @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like $like }) }
function BootAlive() { @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object { $_.CommandLine -like '*boot_all.ps1*' }).Count -gt 0 }

$lad = @("-u","research\cleanroom\ladder_live.py","--subaccount","1","--live","--auto-size","--market-cap-x","2","--minutes","10080")
$bootLine = 'a = @("-u", "research\cleanroom\ladder_live.py", "--subaccount", "1", "--live", "--auto-size", "--market-cap-x", "2", "--minutes", "10080");'

Say "validating (DryRun=$DryRun)"
$out = & $py @($lad + @("--selftest")) | Out-String
if ($LASTEXITCODE -ne 0 -or $out -notmatch "ladder_live self-test PASSED") { Say "SELF-TEST FAILED with the live argv"; exit 1 }
Say "self-test ok with the live argv"
if (Test-Path "$res\ladder-live.stop") { Say "stop file present, refusing"; exit 1 }
$old = @(Live '*ladder_live.py*--live*')
if ($old.Count -ne 1) { Say "expected exactly one live ladder, found $($old.Count) -- refusing"; exit 1 }
$boot = Get-Content "$repo\boot_all.ps1" -Raw
if (-not $boot.Contains($bootLine)) { Say "boot_all.ps1 does not carry the same ladder argv -- refusing"; exit 1 }
Say "ok: old ladder pid $($old[0].ProcessId); boot_all carries the same argv"
if ($DryRun) { Say "DRY RUN: nothing changed"; exit 0 }

New-Item -ItemType File -Path "$res\ladder-live.stop" -Force | Out-Null
Say "stop file written; waiting for pid $($old[0].ProcessId) to cancel its bids and exit"
for ($i = 0; $i -lt 90 -and (Get-Process -Id $old[0].ProcessId -ErrorAction SilentlyContinue); $i++) { Start-Sleep 1 }
if (Get-Process -Id $old[0].ProcessId -ErrorAction SilentlyContinue) { Say "old ladder did not exit in 90 s -- stop file kept; check by hand"; exit 1 }
Say "old ladder exited after ~$i s"
for ($i = 0; $i -lt 60 -and (BootAlive); $i++) { Start-Sleep 1 }
if (BootAlive) { Say "boot_all still running after 60 s -- stop file kept; check by hand"; exit 1 }
Remove-Item "$res\ladder-live.stop" -Force
$p = Start-Process -FilePath $py -ArgumentList $lad -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput "$res\ladder-live-stdout.log" -RedirectStandardError "$res\ladder-live-stderr.log" -PassThru
Say "started ladder $($p.Id): $($lad -join ' ')"
$rec = $null
for ($i = 0; $i -lt 60 -and -not $rec; $i++) {
    Start-Sleep 1
    $rec = Get-Content "$res\ladder-live-orders.jsonl" -Tail 400 | Where-Object { $_ -match '"ev": ?"start"' -and $_ -match ('"pid": ?' + $p.Id + '[,}]') } | Select-Object -Last 1
}
if ($rec) { Say "start record: $rec" } else { Say "NO start record for pid $($p.Id) within 60 s -- check ladder-live-stderr.log" }
$now = @(Live '*ladder_live.py*--live*')
Say "live ladders now: $($now.Count) ($(($now | ForEach-Object { $_.ProcessId }) -join ', '))"
