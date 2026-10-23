# restart_ladder_fit.ps1 -- v-ladder-fit on the live ladder (subaccount 1), 2026-10-23. Operator: "Figure out the most profitable
# safest way to run ladder and that's what we'll do" + ran the boot_all edit themselves. Same procedure as results\restart_ladder_cplus.ps1:
# validate (self-test with the new argv, old pid alive, no stop file, boot_all line), quiet window (minute 1-11 of the quarter-hour),
# stop file -> old ladder cancels and exits -> delete the stop file -> start the new one -> confirm its start record.
param([switch]$DryRun)
$ErrorActionPreference = "Stop"
$repo = "C:\kals-repo"; $res = "$repo\results"; $py = "C:\Python314\python.exe"
function Say($m) { $l = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"), $m; Write-Output $l; Add-Content -Path "$res\restart_ladder_fit.log" -Value $l -Encoding utf8 }

$lad = @("-u","research\cleanroom\ladder_live.py","--subaccount","1","--live","--auto-size","--market-cap-x","2","--levels","0,1",
         "--coins","KXNEAR15M,KXZEC15M,KXDOGE15M,KXHYPE15M,KXXRP15M","--fit","--big-coins-above","3000","--minutes","10080")
$bootLine = 'a = @("-u", "research\cleanroom\ladder_live.py", "--subaccount", "1", "--live", "--auto-size", "--market-cap-x", "2", "--levels", "0,1", "--coins", "KXNEAR15M,KXZEC15M,KXDOGE15M,KXHYPE15M,KXXRP15M", "--fit", "--big-coins-above", "3000", "--minutes", "10080");'

Say "validating (DryRun=$DryRun)"
Push-Location $repo
$out = & $py @($lad + @("--selftest")) | Out-String
Pop-Location
if ($LASTEXITCODE -ne 0 -or $out -notmatch "ladder_live self-test PASSED" -or $out -notmatch "fit \(big coins above .3000\) -> .643.47 bids 46" -or $out -notmatch "all fit\)") { Say "SELF-TEST FAILED with the new argv: $out"; exit 1 }
Say "self-test ok with the new argv (fit: 46 bids at `$643, every rung of every coin fits; 9 coins above `$3,000)"
if (Test-Path "$res\ladder-live.stop") { Say "stop file present, refusing"; exit 1 }
$last = Get-Content "$res\ladder-live-orders.jsonl" -Tail 20000 | Where-Object { $_ -match '"ev": ?"start"' } | Select-Object -Last 1
if (-not ($last -match '"pid": ?(\d+)')) { Say "no start record found -- refusing"; exit 1 }
$oldPid = [int]$Matches[1]
if (-not (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) { Say "old ladder pid $oldPid is not running -- refusing (check by hand)"; exit 1 }
$boot = Get-Content "$repo\boot_all.ps1" -Raw
if (-not $boot.Contains($bootLine)) { Say "boot_all.ps1 does not carry the new ladder argv -- refusing"; exit 1 }
Say "ok: old ladder pid $oldPid; boot_all carries the new argv"
if ($DryRun) { Say "DRY RUN: nothing changed"; exit 0 }

while ($true) { $u = (Get-Date).ToUniversalTime(); $s = ($u.Minute % 15) * 60 + $u.Second; if ($s -ge 60 -and $s -le 660) { break }; Start-Sleep 5 }
Say "quiet window (minute $((Get-Date).ToUniversalTime().Minute % 15) of the quarter-hour)"
New-Item -ItemType File -Path "$res\ladder-live.stop" -Force | Out-Null
Say "stop file written; waiting for pid $oldPid to cancel its bids and exit"
for ($i = 0; $i -lt 90 -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue); $i++) { Start-Sleep 1 }
if (Get-Process -Id $oldPid -ErrorAction SilentlyContinue) { Say "old ladder did not exit in 90 s -- stop file kept; check by hand"; exit 1 }
Say "old ladder exited after ~$i s"
Remove-Item "$res\ladder-live.stop" -Force
$p = Start-Process -FilePath $py -ArgumentList $lad -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput "$res\ladder-live-stdout.log" -RedirectStandardError "$res\ladder-live-stderr.log" -PassThru
Say "started ladder $($p.Id): $($lad -join ' ')"
$rec = $null
for ($i = 0; $i -lt 60 -and -not $rec; $i++) {
    Start-Sleep 1
    $rec = Get-Content "$res\ladder-live-orders.jsonl" -Tail 400 | Where-Object { $_ -match '"ev": ?"start"' -and $_ -match ('"pid": ?' + $p.Id + '[,}]') } | Select-Object -Last 1
}
if ($rec) { Say "start record: $rec" } else { Say "NO start record for pid $($p.Id) within 60 s -- check ladder-live-stderr.log" }
Start-Sleep 5
$starts = @(Get-Content "$res\ladder-live-orders.jsonl" -Tail 400 | Where-Object { $_ -match '"ev": ?"start"' -and $_ -match '"t": ?"([^"]+)"' -and ([datetime]$Matches[1]).ToUniversalTime() -gt (Get-Date).ToUniversalTime().AddMinutes(-3) })
Say "ladder start records in the last 3 min: $($starts.Count) (must be 1; 2 = boot_all raced us -> write results\ladder-live.stop and rerun)"
