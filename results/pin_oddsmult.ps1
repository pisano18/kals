# pin_oddsmult.ps1 -- 2026-11-02. Operator: "Go. Push it yourself without me needing to do anything." Puts pin on a
# NEW build, C:\kals-live-0925r = C:\kals-live-0925q (code_sha 0f49ba3ae221) + results\patch_oddsmult.py (code_sha
# ca156bf45704), with two new flags: --hedge-odds-mult 1.25 --hedge-odds-min-tau 11.
#   v-oddsmult: when the hedge fires on the BELIEF line (pin's odds in our side under --hedge-belief 0.40; never the
#     jump trigger, never a stale-index alarm) with 11+ s left, pin ALSO buys (M - 1) x the position of the hedge side
#     as a SECOND order right after the covering hedge. The covering hedge is byte-for-byte the order it was. Logged as
#     kind hedge_extra (hedge_extra_skipped / hedge_extra_refused when not). Evidence: the hedge side at the odds line
#     won 27 of 37 (09-23..11-01); 2x = +$350..+$550 per 40 days at 299-contract bets; inside 10 s the extra lost
#     (-$136 on 8), hence the floor. 11-02 ZEC 7:30 ET: 2x would have turned -$28.56 into about +$170. Start 1.25x
#     (the tiny-test rule), then 1.5x, 2x. Monitor: research\pinrules_watch.py (rule C).
# STEPS (anything wrong before step 6 restores both launchers and stops; the running pin is never touched before 6):
#   1. refuse unless 0925q is still 0f49ba3ae221, 0925r does not exist yet, both launchers (C:\kals-live-0925n's, the
#      hand launcher, and C:\kals-repo's, which watch_bot.ps1 uses) still point at 0925q / 0f49ba3ae221, and the repo's
#      VERSIONS.md already carries the v-oddsmult entry (it comes with the commit)
#   2. copy 0925q -> 0925r, patch 0925r\research\pinrun.py, refuse unless its sha is exactly ca156bf45704
#   3. edit BOTH launchers: $code -> 0925r, $codeSha -> ca156bf45704, the two flags after the v-wsfall10 line (backups
#      kept, parse-checked); the build's own copy of the launcher and of VERSIONS.md too (its self-test reads them)
#   4. -Check (both launchers), the two argv must match
#   5. the FULL new argv + --selftest on the new build at BelowNormal priority: must print SELF-TEST PASSED
#   6. restart pin through C:\kals-live-0925n\restart_bot.ps1 by WMI (it waits until pin holds no open bet)
# REVERT: copy the two .before-oddsmult-* backups over the launchers and rerun restart_bot while flat (0925q untouched).
# Log: results\pin_oddsmult.out; the restart's own output: results\pin_oddsmult_restart.out
$log = 'C:\kals-repo\results\pin_oddsmult.out'
function Say($m) { $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m; Write-Output $l; Add-Content -Path $log -Value $l }
$py = 'C:\Python314\python.exe'
$old = 'C:\kals-live-0925q'
$new = 'C:\kals-live-0925r'
$oldSha = '0f49ba3ae221'
$newSha = 'ca156bf45704'
$launchers = @('C:\kals-live-0925n\restart_bot.ps1', 'C:\kals-repo\restart_bot.ps1')
function Sha12($p) { (Get-FileHash -Algorithm SHA256 -Path $p).Hash.ToLower().Substring(0, 12) }
Say "start"
# ---- 1. preconditions
if ((Sha12 "$old\research\pinrun.py") -ne $oldSha) { Say "REFUSED: $old\research\pinrun.py is not $oldSha; nothing changed"; exit 1 }
if (Test-Path $new) { Say "REFUSED: $new already exists; nothing changed"; exit 1 }
$vrepo = [IO.File]::ReadAllText('C:\kals-repo\results\VERSIONS.md')
if ($vrepo -notmatch 'v-oddsmult') { Say "REFUSED: C:\kals-repo\results\VERSIONS.md has no v-oddsmult entry (pull the commit first); nothing changed"; exit 1 }
$prev = '    "--ws-later-fall-c", "10", "--hedge-jump-max", "8",'
$edits = @(
  @('$code = "C:\kals-live-0925q"', '$code = "C:\kals-live-0925r"'),
  @('$codeSha = "0f49ba3ae221"', '$codeSha = "ca156bf45704"'),
  @($prev,
    ($prev + "`r`n" + '    # v-oddsmult 2026-11-02 (operator: "Go. Push it yourself without me needing to do anything."): when the 0.40 belief line fires with 11+ s left, ALSO buy (M - 1) x the position of the hedge side as a second order right after the covering hedge (never on the jump trigger). 1.25 first (the tiny-test rule), then 1.5, 2. Logged as hedge_extra; scored by research\pinrules_watch.py (rule C). Revert: delete this line pair and $code/$codeSha back to C:\kals-live-0925q / 0f49ba3ae221' + "`r`n" + '    "--hedge-odds-mult", "1.25", "--hedge-odds-min-tau", "11",'))
)
foreach ($f in $launchers) {
  $t = [IO.File]::ReadAllText($f)
  if ($t -match 'hedge-odds-mult') { Say "REFUSED: $f already mentions hedge-odds-mult; nothing changed"; exit 1 }
  foreach ($e in $edits) {
    $n = ([regex]::Matches($t, [regex]::Escape($e[0]))).Count
    if ($n -ne 1) { Say ("REFUSED: {0}: expected once, found {1}: {2}; nothing changed" -f $f, $n, $e[0]); exit 1 }
  }
}
Say "preconditions ok: $old is $oldSha, both launchers point at it, VERSIONS.md has the entry"
# ---- 2. the new build
Copy-Item -Recurse $old $new
Get-ChildItem -Recurse -Directory -Filter '__pycache__' $new | Remove-Item -Recurse -Force
$pout = & $py -u 'C:\kals-repo\results\patch_oddsmult.py' "$new\research\pinrun.py" 2>&1 | Out-String
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
  $bak = $f + ".before-oddsmult-" + $stamp
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
if ($chk2 -notmatch "code_sha $newSha" -or $chk2 -notmatch '--hedge-odds-mult 1\.25' -or $chk2 -notmatch '--hedge-odds-min-tau 11' -or $chk2 -notmatch '--ws-later-fall-c 10' -or $chk2 -notmatch '--hedge-jump-max 8' -or $chk2 -notmatch '--bank-brake 3\.00' -or $chk2 -notmatch '--band99-ceiling 0\.99') { Say "the keep-alive launcher's -Check did not show the new build, both new flags, the 11-01 flags, band99 and --bank-brake 3.00"; RestoreAll; exit 1 }
Say "keep-alive launcher -Check ok"
$chk = & powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\kals-live-0925n\restart_bot.ps1' -Check 2>&1 | Out-String
Add-Content -Path $log -Value $chk
$line = ($chk -split "`n" | Where-Object { $_ -match 'kals-live-0925r\\research\\pinrun\.py' -and $_ -match '--hedge-odds-mult 1\.25' -and $_ -match '--hedge-odds-min-tau 11' } | Select-Object -First 1)
if (-not $line -or $chk -notmatch "code_sha $newSha") { Say "-Check did not show the new build with both flags"; RestoreAll; exit 1 }
Say "hand launcher -Check ok"
# ---- 5. the full-argv self-test on the new build, before anything stops
$argv = ($line.Trim() -split '\s+')
$i = [array]::IndexOf($argv, ($argv | Where-Object { $_ -like '*pinrun.py' } | Select-Object -First 1))
$targs = @('-u', "$new\research\pinrun.py") + $argv[($i + 1)..($argv.Length - 1)] + @('--selftest')
Say ("self-test: " + ($targs -join ' '))
New-Item -ItemType Directory -Force "$new\selftest" | Out-Null
$p = Start-Process -FilePath $py -ArgumentList $targs -RedirectStandardOutput "$new\selftest\oddsmult_selftest.out" -RedirectStandardError "$new\selftest\oddsmult_selftest.err" -NoNewWindow -PassThru
$null = $p.Handle   # PowerShell 5: without this ExitCode is empty after WaitForExit
try { $p.PriorityClass = "BelowNormal" } catch {}
$p.WaitForExit()
$so = Get-Content "$new\selftest\oddsmult_selftest.out" -Raw
$nok = ([regex]::Matches($so, '(?m)^  ok   ')).Count
if ($p.ExitCode -ne 0 -or $so -notmatch 'SELF-TEST PASSED') { Say ("self-test FAILED (exit {0}, {1} ok); see $new\selftest\oddsmult_selftest.out" -f $p.ExitCode, $nok); RestoreAll; exit 1 }
Say ("self-test PASSED ({0} ok) with the full new argv" -f $nok)
# ---- 6. the restart (restart_bot waits for pin to be flat)
$cmd = 'cmd /c "powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-live-0925n\restart_bot.ps1 > C:\kals-repo\results\pin_oddsmult_restart.out 2>&1"'
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = 'C:\kals-live-0925n' }
Say ("restart launched, wrapper pid {0} (return {1}); watch C:\kals-repo\results\pin_oddsmult_restart.out" -f $r.ProcessId, $r.ReturnValue)
