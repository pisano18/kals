# pin_rules2.ps1 -- 2026-11-01. Operator: "Push it live, skip the slash approve." Puts pin on a NEW build,
# C:\kals-live-0925q = C:\kals-live-0925p (code_sha 24eec22bbaa7) + results\patch_rules2.py (code_sha 0f49ba3ae221),
# with two new flags: --ws-later-fall-c 10 --hedge-jump-max 8.
#   v-wsfall10: a LATER buy (this side of this 15-minute market already held) with the index across the strike from
#     our side and our side's mid DOWN >= 10c over the last 5 s is refused (ws_later_fall); the rest of that side is
#     skipped for the close (ws_later_skip). 11-01 replay: only HYPE 11-01 9:15 ET (+$37.73), 0 winners skipped.
#   v-jumpcap8: the --hedge-jump 6 trigger fires only for jumps under 8 sd; a capped jump is logged as jump_capped
#     with the hedge it would have sent; the 0.40 belief line is unchanged. Live 10-24..11-01: 8 fires at 8+ sd, 0
#     flips, +$33.04 saved; replay 09-12..10-20: 19 more, 0 flips, +$35.43.
# STEPS (anything wrong before step 6 restores both launchers and stops; the running pin is never touched before 6):
#   1. refuse unless 0925p is still 24eec22bbaa7, 0925q does not exist yet, both launchers (C:\kals-live-0925n's, the
#      hand launcher, and C:\kals-repo's, which watch_bot.ps1 uses) still point at 0925p / 24eec22bbaa7, and the repo's
#      VERSIONS.md already carries the v-wsfall10 entry (it comes with the commit)
#   2. copy 0925p -> 0925q, patch 0925q\research\pinrun.py, refuse unless its sha is exactly 0f49ba3ae221
#   3. edit BOTH launchers: $code -> 0925q, $codeSha -> 0f49ba3ae221, the two flags after the band99 line (backups
#      kept, parse-checked); the build's own copy of the launcher and of VERSIONS.md too (its self-test reads them)
#   4. -Check (both launchers), the two argv must match
#   5. the FULL new argv + --selftest on the new build at BelowNormal priority: must print SELF-TEST PASSED
#   6. restart pin through C:\kals-live-0925n\restart_bot.ps1 by WMI (it waits until pin holds no open bet)
# REVERT: copy the two .before-rules2-* backups over the launchers and rerun restart_bot while flat (0925p untouched).
# Log: results\pin_rules2.out; the restart's own output: results\pin_rules2_restart.out
$log = 'C:\kals-repo\results\pin_rules2.out'
function Say($m) { $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m; Write-Output $l; Add-Content -Path $log -Value $l }
$py = 'C:\Python314\python.exe'
$old = 'C:\kals-live-0925p'
$new = 'C:\kals-live-0925q'
$oldSha = '24eec22bbaa7'
$newSha = '0f49ba3ae221'
$launchers = @('C:\kals-live-0925n\restart_bot.ps1', 'C:\kals-repo\restart_bot.ps1')
function Sha12($p) { (Get-FileHash -Algorithm SHA256 -Path $p).Hash.ToLower().Substring(0, 12) }
Say "start"
# ---- 1. preconditions
if ((Sha12 "$old\research\pinrun.py") -ne $oldSha) { Say "REFUSED: $old\research\pinrun.py is not $oldSha; nothing changed"; exit 1 }
if (Test-Path $new) { Say "REFUSED: $new already exists; nothing changed"; exit 1 }
$vrepo = [IO.File]::ReadAllText('C:\kals-repo\results\VERSIONS.md')
if ($vrepo -notmatch 'v-wsfall10') { Say "REFUSED: C:\kals-repo\results\VERSIONS.md has no v-wsfall10 entry (pull the commit first); nothing changed"; exit 1 }
$band = '    "--band99-ceiling", "0.99", "--band99-frac", "0.10",'
$edits = @(
  @('$code = "C:\kals-live-0925p"', '$code = "C:\kals-live-0925q"'),
  @('$codeSha = "24eec22bbaa7"', '$codeSha = "0f49ba3ae221"'),
  @($band,
    ($band + "`r`n" + '    # v-wsfall10 + v-jumpcap8 2026-11-01 (operator: "Push it live, skip the slash approve."): refuse a LATER buy across the line when our side''s mid fell 10c+ in 5 s (rest of that side skipped for the close); the jump hedge fires only under 8 sd (jump_capped logged). Monitor: research\pinrules_watch.py. Revert: delete this line pair and $code/$codeSha back to C:\kals-live-0925p / 24eec22bbaa7' + "`r`n" + '    "--ws-later-fall-c", "10", "--hedge-jump-max", "8",'))
)
foreach ($f in $launchers) {
  $t = [IO.File]::ReadAllText($f)
  if ($t -match 'ws-later-fall') { Say "REFUSED: $f already mentions ws-later-fall; nothing changed"; exit 1 }
  foreach ($e in $edits) {
    $n = ([regex]::Matches($t, [regex]::Escape($e[0]))).Count
    if ($n -ne 1) { Say ("REFUSED: {0}: expected once, found {1}: {2}; nothing changed" -f $f, $n, $e[0]); exit 1 }
  }
}
Say "preconditions ok: $old is $oldSha, both launchers point at it, VERSIONS.md has the entry"
# ---- 2. the new build
Copy-Item -Recurse $old $new
Get-ChildItem -Recurse -Directory -Filter '__pycache__' $new | Remove-Item -Recurse -Force
$pout = & $py -u 'C:\kals-repo\results\patch_rules2.py' "$new\research\pinrun.py" 2>&1 | Out-String
Say ("patch: " + $pout.Trim())
$got = Sha12 "$new\research\pinrun.py"
if ($got -ne $newSha) { Say "REFUSED: the patched build is $got, expected $newSha; $new left for inspection, launchers untouched"; exit 1 }
Say "new build ok: $new\research\pinrun.py code_sha $got"
Copy-Item 'C:\kals-repo\results\VERSIONS.md' "$new\results\VERSIONS.md" -Force
# ---- 3. the launchers
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$baks = @{}
function RestoreAll { foreach ($k in $baks.Keys) { Copy-Item $baks[$k] $k -Force }; Say "both launchers restored from their backups" }
foreach ($f in $launchers) {
  $t = [IO.File]::ReadAllText($f)
  $bytes = [IO.File]::ReadAllBytes($f)
  $bom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
  $bak = $f + ".before-rules2-" + $stamp
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
# ---- 4. the two launchers' pin argv must match, and both -Check clean
function ArgvOf($f) { @([IO.File]::ReadAllLines($f) | Where-Object { $_ -match '^\s*"--' } | ForEach-Object { $_.Trim().TrimEnd(',') }) }
$dif = @(Compare-Object (ArgvOf $launchers[0]) (ArgvOf $launchers[1]))
if ($dif.Count) { foreach ($d in $dif) { Say ("ARGV DIFFERS ({0}): {1}" -f $(if ($d.SideIndicator -eq '<=') { 'hand launcher only' } else { 'keep-alive only' }), $d.InputObject) }; RestoreAll; exit 1 }
Say ("the two launchers' pin argv match ({0} lines)" -f (ArgvOf $launchers[0]).Count)
$chk2 = & powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\kals-repo\restart_bot.ps1' -Check 2>&1 | Out-String
Add-Content -Path $log -Value $chk2
if ($chk2 -notmatch "code_sha $newSha" -or $chk2 -notmatch '--ws-later-fall-c 10' -or $chk2 -notmatch '--hedge-jump-max 8' -or $chk2 -notmatch '--bank-brake 3\.00' -or $chk2 -notmatch '--band99-ceiling 0\.99') { Say "the keep-alive launcher's -Check did not show the new build, both new flags, band99 and --bank-brake 3.00"; RestoreAll; exit 1 }
Say "keep-alive launcher -Check ok"
$chk = & powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\kals-live-0925n\restart_bot.ps1' -Check 2>&1 | Out-String
Add-Content -Path $log -Value $chk
$line = ($chk -split "`n" | Where-Object { $_ -match 'kals-live-0925q\\research\\pinrun\.py' -and $_ -match '--ws-later-fall-c 10' -and $_ -match '--hedge-jump-max 8' } | Select-Object -First 1)
if (-not $line -or $chk -notmatch "code_sha $newSha") { Say "-Check did not show the new build with both flags"; RestoreAll; exit 1 }
Say "hand launcher -Check ok"
# ---- 5. the full-argv self-test on the new build, before anything stops
$argv = ($line.Trim() -split '\s+')
$i = [array]::IndexOf($argv, ($argv | Where-Object { $_ -like '*pinrun.py' } | Select-Object -First 1))
$targs = @('-u', "$new\research\pinrun.py") + $argv[($i + 1)..($argv.Length - 1)] + @('--selftest')
Say ("self-test: " + ($targs -join ' '))
New-Item -ItemType Directory -Force "$new\selftest" | Out-Null
$p = Start-Process -FilePath $py -ArgumentList $targs -RedirectStandardOutput "$new\selftest\rules2_selftest.out" -RedirectStandardError "$new\selftest\rules2_selftest.err" -NoNewWindow -PassThru
$null = $p.Handle   # PowerShell 5: without this ExitCode is empty after WaitForExit
try { $p.PriorityClass = "BelowNormal" } catch {}
$p.WaitForExit()
$so = Get-Content "$new\selftest\rules2_selftest.out" -Raw
$nok = ([regex]::Matches($so, '(?m)^  ok   ')).Count
if ($p.ExitCode -ne 0 -or $so -notmatch 'SELF-TEST PASSED') { Say ("self-test FAILED (exit {0}, {1} ok); see $new\selftest\rules2_selftest.out" -f $p.ExitCode, $nok); RestoreAll; exit 1 }
Say ("self-test PASSED ({0} ok) with the full new argv" -f $nok)
# ---- 6. the restart (restart_bot waits for pin to be flat)
$cmd = 'cmd /c "powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-live-0925n\restart_bot.ps1 > C:\kals-repo\results\pin_rules2_restart.out 2>&1"'
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = 'C:\kals-live-0925n' }
Say ("restart launched, wrapper pid {0} (return {1}); watch C:\kals-repo\results\pin_rules2_restart.out" -f $r.ProcessId, $r.ReturnValue)
