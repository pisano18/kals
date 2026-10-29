# ladder_argv_commit82.ps1 -- 2026-10-29 (IDEA_LEDGER LS26; operator: "Should we increase the ladder bet size so 3
# trades makes a 1% return off total bank?"). Edits boot_all.ps1's ladder line ONCE:
#   "--fit", "--big-coins-above", "3000"  ->  "--fit", "--commit-frac", "0.82", "--big-coins-above", "7000"
# --commit-frac 0.82: the money rail goes 70% -> 82% of the pot, so each 98c bid is 135 contracts instead of 115 at
#   an $811 pot (+$1.10-1.28 a day, $98 more at rest, 3 fills = 1.0% of the pot; same lock rule, same price).
# --big-coins-above 7000: the 4 big coins join only from a $7,000 pot (LS08/LS26: they lose money below that; the
#   old 3000 was stale). Nothing happens until the ladder restarts (results\ladder_restart.ps1).
# Refuses to touch the file unless the old text occurs exactly once; keeps the BOM and CRLF line endings.
$f = 'C:\kals-repo\boot_all.ps1'
$old = '"--fit", "--big-coins-above", "3000"'
$new = '"--fit", "--commit-frac", "0.82", "--big-coins-above", "7000"'
$t = [IO.File]::ReadAllText($f)
$n = ([regex]::Matches($t, [regex]::Escape($old))).Count
if ($n -ne 1) { Write-Output ("NOT CHANGED: expected the old text once, found {0}" -f $n); exit 1 }
$bytes = [IO.File]::ReadAllBytes($f)
$bom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
Copy-Item $f ($f + ".bak-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
$enc = New-Object System.Text.UTF8Encoding($bom)
[IO.File]::WriteAllText($f, $t.Replace($old, $new), $enc)
$line = (Select-String -Path $f -Pattern 'ladder_live.py", "--subaccount"').Line.Trim()
Write-Output "CHANGED boot_all.ps1 ladder line:"
Write-Output $line
powershell -NoProfile -Command "[void][System.Management.Automation.Language.Parser]::ParseFile('$f', [ref]`$null, [ref]`$e); if (`$e.Count) { 'PARSE ERRORS: ' + `$e.Count; exit 1 } else { 'boot_all.ps1 parses OK' }"
