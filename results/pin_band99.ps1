# pin_band99.ps1 -- 2026-10-31. For the OPERATOR (phone /approve pinband99; operator: "I like the test you came up
# with, do that."). Puts pin on a NEW build, C:\kals-live-0925p = C:\kals-live-0925n (code_sha e51a465d8b5c) +
# results\patch_band99.py (code_sha 24eec22bbaa7), with two new flags: --band99-ceiling 0.99 --band99-frac 0.10.
# THE TEST: an offer over pin's 98c ceiling and at or under 99c, in a market pin holds NOTHING in, is bought at a
# tenth of the coin's bet (~28 contracts at 281); every other gate still applies except the expected-value floor (at
# 99c it refuses everything); one band buy a market. Also logs drop_seen (the top own-side ask of the last 60 s) on
# every signal and order: no trading change.
# STEPS (anything wrong before step 5 restores both launchers and stops; the running pin is never touched before 5):
#   1. refuse unless 0925n is still e51a465d8b5c, 0925p does not exist yet, and both launchers (C:\kals-live-0925n's,
#      which restarts by hand, and C:\kals-repo's, which watch_bot.ps1 uses) still point at 0925n / e51a465d8b5c
#   2. copy 0925n -> 0925p, patch 0925p\research\pinrun.py, refuse unless its sha is exactly 24eec22bbaa7
#   3. edit BOTH launchers: $code -> 0925p, $codeSha -> 24eec22bbaa7, the two flags after --wrongside-rise-c
#      (backups kept, parse-checked); the build's own copy of the launcher too (its self-test reads it)
#   4. -Check, then the FULL new argv + --selftest on the new build at BelowNormal priority: must print SELF-TEST PASSED
#   5. a VERSIONS.md entry (repo + build copies), then restart pin through C:\kals-live-0925n\restart_bot.ps1 by WMI (it waits until pin holds no open bet)
# REVERT: copy the two .before-band99-* backups over the launchers and rerun restart_bot while flat (0925n is untouched).
# Log: results\pin_band99.out; the restart's own output: results\pin_band99_restart.out
$log = 'C:\kals-repo\results\pin_band99.out'
function Say($m) { $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m; Write-Output $l; Add-Content -Path $log -Value $l }
$py = 'C:\Python314\python.exe'
$old = 'C:\kals-live-0925n'
$new = 'C:\kals-live-0925p'
$oldSha = 'e51a465d8b5c'
$newSha = '24eec22bbaa7'
$launchers = @('C:\kals-live-0925n\restart_bot.ps1', 'C:\kals-repo\restart_bot.ps1')
function Sha12($p) { (Get-FileHash -Algorithm SHA256 -Path $p).Hash.ToLower().Substring(0, 12) }
Say "start"
# ---- 1. preconditions
if ((Sha12 "$old\research\pinrun.py") -ne $oldSha) { Say "REFUSED: $old\research\pinrun.py is not $oldSha; nothing changed"; exit 1 }
if (Test-Path $new) { Say "REFUSED: $new already exists; nothing changed"; exit 1 }
$edits = @(
  @('$code = "C:\kals-live-0925n"', '$code = "C:\kals-live-0925p"'),
  @('$codeSha = "e51a465d8b5c"', '$codeSha = "24eec22bbaa7"'),
  @('    "--wrongside-rise-c", "1.0",',
    ('    "--wrongside-rise-c", "1.0",' + "`r`n" + '    # v-band99 2026-10-31 (operator: "I like the test you came up with, do that."): offers over 98c and at or under 99c, only in a market with nothing held, at a tenth of the bet; off again if band orders lose more than $60 or winners fill under 50% after 3 days. Revert: delete this line pair and $code/$codeSha back to C:\kals-live-0925n / e51a465d8b5c' + "`r`n" + '    "--band99-ceiling", "0.99", "--band99-frac", "0.10",'))
)
foreach ($f in $launchers) {
  $t = [IO.File]::ReadAllText($f)
  if ($t -match 'band99') { Say "REFUSED: $f already mentions band99; nothing changed"; exit 1 }
  foreach ($e in $edits) {
    $n = ([regex]::Matches($t, [regex]::Escape($e[0]))).Count
    if ($n -ne 1) { Say ("REFUSED: {0}: expected once, found {1}: {2}; nothing changed" -f $f, $n, $e[0]); exit 1 }
  }
}
Say "preconditions ok: $old is $oldSha, both launchers point at it"
# ---- 2. the new build
Copy-Item -Recurse $old $new
Get-ChildItem -Recurse -Directory -Filter '__pycache__' $new | Remove-Item -Recurse -Force
$pout = & $py -u 'C:\kals-repo\results\patch_band99.py' "$new\research\pinrun.py" 2>&1 | Out-String
Say ("patch: " + $pout.Trim())
$got = Sha12 "$new\research\pinrun.py"
if ($got -ne $newSha) { Say "REFUSED: the patched build is $got, expected $newSha; $new left for inspection, launchers untouched"; exit 1 }
Say "new build ok: $new\research\pinrun.py code_sha $got"
# ---- 4. the launchers
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$baks = @{}
function RestoreAll { foreach ($k in $baks.Keys) { Copy-Item $baks[$k] $k -Force }; Say "both launchers restored from their backups" }
foreach ($f in $launchers) {
  $t = [IO.File]::ReadAllText($f)
  $bytes = [IO.File]::ReadAllBytes($f)
  $bom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
  $bak = $f + ".before-band99-" + $stamp
  Copy-Item $f $bak
  $baks[$f] = $bak
  foreach ($e in $edits) { $t = $t.Replace($e[0], $e[1]) }
  [IO.File]::WriteAllText($f, $t, (New-Object System.Text.UTF8Encoding($bom)))
  $errs = $null
  [void][System.Management.Automation.Language.Parser]::ParseFile($f, [ref]$null, [ref]$errs)
  if ($errs.Count) { Say ("PARSE ERRORS in {0}: {1}" -f $f, $errs.Count); RestoreAll; exit 1 }
  Say "CHANGED $f (parses OK; backup $bak)"
}
Copy-Item 'C:\kals-live-0925n\restart_bot.ps1' "$new\restart_bot.ps1" -Force
# ---- 5. check + the full-argv self-test on the new build, before anything stops
$chk = & powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\kals-live-0925n\restart_bot.ps1' -Check 2>&1 | Out-String
Add-Content -Path $log -Value $chk
$line = ($chk -split "`n" | Where-Object { $_ -match 'kals-live-0925p\\research\\pinrun\.py' -and $_ -match '--band99-ceiling 0\.99' } | Select-Object -First 1)
if (-not $line -or $chk -notmatch "code_sha $newSha") { Say "-Check did not show the new build with the band flags"; RestoreAll; exit 1 }
$argv = ($line.Trim() -split '\s+')
$i = [array]::IndexOf($argv, ($argv | Where-Object { $_ -like '*pinrun.py' } | Select-Object -First 1))
$targs = @('-u', "$new\research\pinrun.py") + $argv[($i + 1)..($argv.Length - 1)] + @('--selftest')
Say ("self-test: " + ($targs -join ' '))
$p = Start-Process -FilePath $py -ArgumentList $targs -RedirectStandardOutput "$new\selftest\band99_selftest.out" -RedirectStandardError "$new\selftest\band99_selftest.err" -NoNewWindow -PassThru
$null = $p.Handle   # PowerShell 5: without this ExitCode is empty after WaitForExit
try { $p.PriorityClass = "BelowNormal" } catch {}
$p.WaitForExit()
$so = Get-Content "$new\selftest\band99_selftest.out" -Raw
$nok = ([regex]::Matches($so, '(?m)^  ok   ')).Count
if ($p.ExitCode -ne 0 -or $so -notmatch 'SELF-TEST PASSED') { Say ("self-test FAILED (exit {0}, {1} ok); see $new\selftest\band99_selftest.out" -f $p.ExitCode, $nok); RestoreAll; exit 1 }
Say ("self-test PASSED ({0} ok) with the full new argv" -f $nok)
# ---- 5b. the version entry (only once everything passed)
$entry = '# v-band99 -- INSTALLED ' + (Get-Date -Format 'yyyy-MM-dd HH:mm') + ' ET by results/pin_band99.ps1 (phone /approve pinband99); LIVE at this restart (C:\kals-live-0925p, pinrun code_sha 24eec22bbaa7 = 0925n e51a465d8b5c + results/patch_band99.py; ordercli/pintake unchanged). Operator 10-31: "I like the test you came up with, do that." NEW FLAGS --band99-ceiling 0.99 --band99-frac 0.10 (default off): an offer over the 98c ceiling and at or under 99c, in a 15-minute market pin holds NOTHING in (no side, no fill, no open position, any leg), is bought at floor(10% of the coin''s bet) (~28 at size 281), one band buy a market; every other gate applies except the expected-value floor (at 99c its 0.9% flip rate refuses everything); the order''s limit never passes 99c; refusals band99_held / band99_over. Every signal and order now carries drop_seen (top own-side ask of the last 60 s and its tau) and band99. Evidence (ceil99 study, 09-14..10-31, size 281): never-held markets 2,967, 3 lost, +$3,679 if every order filled; markets bought anyway later 317, 17 lost, -$1,566 (excluded by the held rule). One loss ~-$28, one win ~+$0.26, ~78 eligible markets a day. Scale only if >= 60% of winning band orders fill. STOP: off again if band orders lose more than $60 in total, or if after 3 days winners fill under 50%. REVERT: the .before-band99 backups of both launchers, rerun while flat.'
foreach ($vf in @('C:\kals-repo\results\VERSIONS.md', "$new\results\VERSIONS.md")) {
  $vt = [IO.File]::ReadAllText($vf)
  [IO.File]::WriteAllText($vf, $entry + "`r`n" + $vt, (New-Object System.Text.UTF8Encoding($false)))
}
Say "VERSIONS.md entry written (repo + build)"
# ---- 6. the restart (restart_bot waits for pin to be flat)
$cmd = 'cmd /c "powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-live-0925n\restart_bot.ps1 > C:\kals-repo\results\pin_band99_restart.out 2>&1"'
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = 'C:\kals-live-0925n' }
Say ("restart launched, wrapper pid {0} (return {1}); watch C:\kals-repo\results\pin_band99_restart.out" -f $r.ProcessId, $r.ReturnValue)
