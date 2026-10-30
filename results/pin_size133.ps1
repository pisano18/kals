# pin_size133.ps1 -- 2026-10-30 evening. For the OPERATOR (phone /approve pinsize). ONE edit to
# C:\kals-live-0925n\restart_bot.ps1: "--bank-brake", "4.00" -> "3.00" (1.33x bet, trial). The jump hedge (--hedge-jump 6)
# STAYS ON: the operator asked whether it ever prevented losses; the 10-18 / 10-20 history studies (09-12..10-20) said it
# would have cut the big fast losses (NEAR 10-03 -$86.95, ZEC 10-07 -$83.26, ZEC 10-18 -$32.68 -> about -$1.50), +$76 to
# +$189 over those weeks, while its only live week (10-24..10-30) had no jump-type loss and cost -$12.50 plus a band-boost
# side effect. With a bigger bet, insurance against the big fast losses is worth keeping.
# Stop rule for the size trial: any pin day worse than -$100, or the 11-10 read showing the extra contracts under 0c each
# -> back to 4.00. Keeps a backup, BOM and line endings, parse-checks, -Check, then restart_bot by WMI (waits for flat).
$log = 'C:\kals-repo\results\pin_size133.out'
function Say($m) { $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m; Write-Output $l; Add-Content -Path $log -Value $l }
$f = 'C:\kals-live-0925n\restart_bot.ps1'
$t = [IO.File]::ReadAllText($f)
$nl = "`n"; if ($t -match "`r`n") { $nl = "`r`n" }
$edits = @(
  ,@('    "--bank-brake", "4.00",',
    ('    # v-size15 2026-10-30 (operator: "You decide on pin size"): 4.00 -> 3.00 = 1.33x bet (trial; operator asked for caution; jump hedge kept); +$2/day, 84% of resamples; back to 4.00 on a day under -$100 or a bad 11-10 read' + $nl + '    "--bank-brake", "3.00",'))
)
foreach ($e in $edits) {
  $n = ([regex]::Matches($t, [regex]::Escape($e[0]))).Count
  if ($n -ne 1) { Say ("NOT CHANGED: expected once, found {0}: {1}" -f $n, $e[0]); exit 1 }
}
$bytes = [IO.File]::ReadAllBytes($f)
$bom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
$bak = $f + ".before-size133-" + (Get-Date -Format "yyyyMMdd-HHmmss")
Copy-Item $f $bak
foreach ($e in $edits) { $t = $t.Replace($e[0], $e[1]) }
[IO.File]::WriteAllText($f, $t, (New-Object System.Text.UTF8Encoding($bom)))
$errs = $null
[void][System.Management.Automation.Language.Parser]::ParseFile($f, [ref]$null, [ref]$errs)
if ($errs.Count) { Copy-Item $bak $f -Force; Say ("PARSE ERRORS: {0}; backup restored, nothing restarted" -f $errs.Count); exit 1 }
Say "CHANGED restart_bot.ps1: --bank-brake 3.00 (jump hedge kept); parses OK (backup $bak)"
$chk = & powershell -NoProfile -ExecutionPolicy Bypass -File $f -Check 2>&1 | Out-String
Add-Content -Path $log -Value $chk
if ($chk -notmatch '3\.00') { Copy-Item $bak $f -Force; Say "-Check did not show --bank-brake 3.00; backup restored, nothing restarted"; exit 1 }
Say "restart_bot -Check ran (output above in this log); starting restart_bot by WMI (it waits for pin to be flat)"
$cmd = 'cmd /c "powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-live-0925n\restart_bot.ps1 > C:\kals-repo\results\pin_size133_restart.out 2>&1"'
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = 'C:\kals-live-0925n' }
Say ("restart launched, wrapper pid {0} (return {1}); watch C:\kals-repo\results\pin_size133_restart.out" -f $r.ProcessId, $r.ReturnValue)
