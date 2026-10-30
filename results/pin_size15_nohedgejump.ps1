# pin_size15_nohedgejump.ps1 -- 2026-10-30. For the OPERATOR to run ON THE SERVER (the classifier blocks the assistant
# from editing the live launcher). Two edits to C:\kals-live-0925n\restart_bot.ps1:
#  1. comment out  "--hedge-jump", "6",   (hedgejump6 read: 7 of 8 hedges insured winners, 0 of 3 real losses caught;
#     about +$2-4/day)
#  2. "--bank-brake", "4.00"  ->  "2.70"   (v-size15, operator 10-30: "You decide on pin size. Do the math and figure out
#     what makes the most after accounting for losses realistically." Scratchpad pinsize\sizes.py on 22 recorded days with
#     real results, book depth and the 77%/60% fill rate: 1.5x = +$2.98/day mean, beats 1x in 83% of 4,000 resamples;
#     2x = +$4.96 but a 90% range of -$6 to +$15 and one ETH-size loss = 94% of the run abort. Worst market -$119 -> -$178,
#     worst day -$68 -> -$92. Re-read 11-10: extra contracts under 0c each -> back to 4.00; over +0.5c each -> 2.00.)
# Keeps a backup, BOM and line endings, parse-checks the file, then restarts pin through restart_bot.ps1 started by WMI
# (an SSH session would kill the new pin when it closes). restart_bot itself waits until pin is flat.
# Output: C:\kals-repo\results\pin_size15.out
$log = 'C:\kals-repo\results\pin_size15.out'
function Say($m) { $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m; Write-Output $l; Add-Content -Path $log -Value $l }
$f = 'C:\kals-live-0925n\restart_bot.ps1'
$t = [IO.File]::ReadAllText($f)
$nl = "`n"; if ($t -match "`r`n") { $nl = "`r`n" }
$edits = @(
  @('    "--hedge-jump", "6",',
    '    # "--hedge-jump", "6",   # 2026-10-30 REMOVED (hedgejump6 read: 7 of 8 hedges insured winners, 0 of 3 real losses caught)'),
  @('    "--bank-brake", "4.00",',
    ('    # v-size15 2026-10-30 (operator: "You decide on pin size"): 4.00 -> 2.70 = 1.5x bet; pinsize read +$3/day, 83% of resamples; re-read 11-10' + $nl + '    "--bank-brake", "2.70",'))
)
foreach ($e in $edits) {
  $n = ([regex]::Matches($t, [regex]::Escape($e[0]))).Count
  if ($n -ne 1) { Say ("NOT CHANGED: expected once, found {0}: {1}" -f $n, $e[0]); exit 1 }
}
$bytes = [IO.File]::ReadAllBytes($f)
$bom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
$bak = $f + ".before-size15-" + (Get-Date -Format "yyyyMMdd-HHmmss")
Copy-Item $f $bak
foreach ($e in $edits) { $t = $t.Replace($e[0], $e[1]) }
[IO.File]::WriteAllText($f, $t, (New-Object System.Text.UTF8Encoding($bom)))
$errs = $null
[void][System.Management.Automation.Language.Parser]::ParseFile($f, [ref]$null, [ref]$errs)
if ($errs.Count) { Copy-Item $bak $f -Force; Say ("PARSE ERRORS: {0}; backup restored, nothing restarted" -f $errs.Count); exit 1 }
Say "CHANGED restart_bot.ps1: --hedge-jump 6 commented out, --bank-brake 2.70; parses OK (backup $bak)"
$chk = & powershell -NoProfile -ExecutionPolicy Bypass -File $f -Check 2>&1 | Out-String
Add-Content -Path $log -Value $chk
if ($chk -notmatch '2\.70') { Copy-Item $bak $f -Force; Say "-Check did not show --bank-brake 2.70; backup restored, nothing restarted"; exit 1 }
Say "restart_bot -Check ran (output above in this log); starting restart_bot by WMI (it waits for pin to be flat)"
$cmd = 'cmd /c "powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-live-0925n\restart_bot.ps1 > C:\kals-repo\results\pin_size15_restart.out 2>&1"'
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = 'C:\kals-live-0925n' }
Say ("restart launched, wrapper pid {0} (return {1}); watch C:\kals-repo\results\pin_size15_restart.out" -f $r.ProcessId, $r.ReturnValue)
