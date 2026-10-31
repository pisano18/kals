# ladder82.ps1 -- 2026-10-31 (operator: "Yes do the 82%"). One ladder restart that carries two changes:
#   1. --commit-frac 0.82 (results\ladder_argv_commit82.ps1 edits boot_all's ladder line once; LS26): the money rail
#      goes 70% -> 82% of the pot, so each 98c bid is ~138 contracts instead of 118 at the $830 pot.
#   2. v-ladder-replace (ladder_live.py): a bid the paper engine MOVES (97.9c -> 98c) waits for the old bid's cancel
#      instead of being refused for good; before this the market was left with no bid. The rails are never exceeded.
# Steps: refuse unless the server has pulled the v-ladder-replace code and the ladder self-test passes; edit boot_all;
# then results\ladder_restart.ps1 (waits for minutes 2-9 of a quarter hour, stop file, KalsBoot starts it again).
# Log: results\ladder82.out (this script) and results\ladder_restart.out (the restart).
$repo = "C:\kals-repo"
$log = "$repo\results\ladder82.out"
function Say($m) { ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $m) | Out-File $log -Append -Encoding utf8 }
Set-Location $repo
Say "start"
$code = Get-Content "$repo\research\cleanroom\ladder_live.py" -Raw
if ($code -notlike "*v-ladder-replace*") { Say "REFUSED: the server has not pulled the v-ladder-replace code (git pull first)"; exit 1 }
$st = & C:\Python314\python.exe -u research\cleanroom\ladder_live.py --selftest 2>&1 | Out-String
Say ("ladder self-test: " + ($st.Trim() -split "`n" | Select-Object -Last 1))
if ($LASTEXITCODE -ne 0 -or $st -notmatch "PASSED") { Say "REFUSED: the ladder self-test did not pass; nothing changed"; exit 1 }
$argv = (Select-String -Path "$repo\boot_all.ps1" -Pattern 'ladder_live.py", "--subaccount"').Line
if ($argv -like "*--commit-frac*") {
    Say "boot_all already has --commit-frac; not editing it again"
} else {
    $out = & powershell -NoProfile -ExecutionPolicy Bypass -File "$repo\results\ladder_argv_commit82.ps1" 2>&1 | Out-String
    Say ("argv edit: " + $out.Trim())
    $argv = (Select-String -Path "$repo\boot_all.ps1" -Pattern 'ladder_live.py", "--subaccount"').Line
    if ($argv -notlike '*"--commit-frac", "0.82"*' -or $out -notmatch "parses OK") { Say "REFUSED: the boot_all edit did not take; the ladder was not restarted"; exit 1 }
}
Say "restarting the ladder (results\ladder_restart.out has the steps)"
& powershell -NoProfile -ExecutionPolicy Bypass -File "$repo\results\ladder_restart.ps1"
Say ("restart script exit code {0}" -f $LASTEXITCODE)
$tail = Get-Content "$repo\results\ladder_restart.out" -Tail 4
foreach ($l in $tail) { Say ("  " + $l) }
Say "done"
