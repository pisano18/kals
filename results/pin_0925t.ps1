# pin_0925t.ps1 -- 2026-11-04. Operator: "Whatever changes you proposed in your last message just push them yourself."
# Puts pin on a NEW build, C:\kals-live-0925t = C:\kals-live-0925r (pinrun code_sha ca156bf45704, pintake 9150d6b65968)
# + results\patch_0925t.py (pinrun 9e04c0252ac9, pintake b3c7bb48abb5; ordercli unchanged 467782077a23), with three
# new flags switched on and one existing flag moved:
#   --hedge-tick round (v-hedgetick): the hedge limit (ask + --hedge-slip 0.10) is snapped DOWN to the market's own
#     price grid (15-minute series: 0.1c under 10c and from 90c, 1c between; KXBTCD: whole cents). The bug: a 1.5c
#     hedge ask became an off-grid 11.5c limit; Kalshi rejected 202 of 202 such sends (order_id null) and pin re-sent
#     it every second 30-42 times; 19 of 19 on-grid sends were accepted. Only jump-trigger hedges were hit.
#   --jump-hedge-min-ask 0.05 (v-cheapjump): a JUMP-triggered hedge (belief still over the 0.40 line, no panic)
#     whose hedge side asks under 5c sends nothing that second, keeps its tries, logs hedge_cheap_skip. Jump-only
#     fires by ask: under 5c 36 fires, 0 saves, -$230 at size 322; 5-10c 18 fires, 3 saves, +$583.
#   --boost-rail off (v-boostrail, lane R2's choice): the A53 band / A55 late boost is never switched off for the
#     run by a losing leg. Every trip since 10-21 (ZEC 10-24, KXBTCD 10-31, HYPE 10-31) was a 5-7c jump-hedge leg on
#     a market whose BOOSTED side won; the boost was off 110 of 328 hours. Every losing leg of a boosted market is
#     logged as boost_rail_kept so the tracker can price what the rail would have done.
#   --max-positions 3 -> 5 (v-maxpos5): a 1.5x boosted position plus its covering hedge already reaches the 3.0x
#     SIZE line that paused every new entry (ETH 10-27). Logged open_cap_relaxed when an entry proceeds past 3x.
#   Always on in the build (no flag): the odds-line extra fires on belief under 0.40 whatever the alarm label (never
#     a stale-index alarm); pintake judges the extra with the stake cap and the loss abort (extra=True,
#     extra_stake_capped); hedge and hedge_extra records carry the ask ladder and the grid fields; --hedge-odds-mult
#     accepts [1.0, 2.0].
#   In the build but OFF (--late-bypass-fix off, the default, not in the argv): the late-1.5x bypass fix. As built it
#     trims every late add on a refused-boost market to 0; those adds were 23 of 23 winners (+$88.58 at size 322)
#     against one loss it would have saved (BNB 10-19, -$133.52 at 322): a break-even safety filter, so it stays off.
#   Tracked by research\pinrules_watch.py and the phone's /fixes command.
# STEPS (anything wrong before step 6 restores both launchers and stops; the running pin is never touched before 6):
#   1. refuse unless 0925r is still ca156bf45704 / 9150d6b65968 / 467782077a23, 0925t does not exist yet, both
#      launchers (C:\kals-live-0925n's, the hand launcher, and C:\kals-repo's, which watch_bot.ps1 uses) still point
#      at 0925r / ca156bf45704 / 9150d6b65968 and carry none of the new flags, and the repo's VERSIONS.md already
#      carries the v-0925t entry (it comes with the commit)
#   2. copy 0925r -> 0925t, patch 0925t (the patch takes the BUILD DIRECTORY and edits research\pinrun.py AND
#      research\pintake.py), refuse unless pinrun is exactly 9e04c0252ac9, pintake b3c7bb48abb5, ordercli 467782077a23
#   3. edit BOTH launchers: $code -> 0925t, $codeSha -> 9e04c0252ac9, $pintakeSha -> b3c7bb48abb5, "--max-positions"
#      "3" -> "5" (with its comment), the three flags after the v-oddsmult line (backups kept, parse-checked); the
#      build's own copy of the launcher and of VERSIONS.md too (its self-test reads them)
#   4. -Check (both launchers), the two argv must match and show every new flag and the unchanged ones
#   5. the FULL new argv + --selftest on the new build at BelowNormal priority: must print SELF-TEST PASSED
#   6. restart pin through C:\kals-live-0925n\restart_bot.ps1 by WMI (it waits until pin holds no open bet)
# REVERT: copy the two .before-0925t-* backups over the launchers and rerun restart_bot while flat (0925r untouched).
# Log: results\pin_0925t.out; the restart's own output: results\pin_0925t_restart.out
$log = 'C:\kals-repo\results\pin_0925t.out'
function Say($m) { $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m; Write-Output $l; Add-Content -Path $log -Value $l }
$py = 'C:\Python314\python.exe'
$old = 'C:\kals-live-0925r'
$new = 'C:\kals-live-0925t'
$oldSha = 'ca156bf45704'
$newSha = '9e04c0252ac9'
$oldPintakeSha = '9150d6b65968'
$newPintakeSha = 'b3c7bb48abb5'
$ordercliSha = '467782077a23'
$launchers = @('C:\kals-live-0925n\restart_bot.ps1', 'C:\kals-repo\restart_bot.ps1')
function Sha12($p) { (Get-FileHash -Algorithm SHA256 -Path $p).Hash.ToLower().Substring(0, 12) }
Say "start"
# ---- 1. preconditions
if ((Sha12 "$old\research\pinrun.py") -ne $oldSha) { Say "REFUSED: $old\research\pinrun.py is not $oldSha; nothing changed"; exit 1 }
if ((Sha12 "$old\research\pintake.py") -ne $oldPintakeSha) { Say "REFUSED: $old\research\pintake.py is not $oldPintakeSha; nothing changed"; exit 1 }
if ((Sha12 "$old\research\ordercli.py") -ne $ordercliSha) { Say "REFUSED: $old\research\ordercli.py is not $ordercliSha; nothing changed"; exit 1 }
if (Test-Path $new) { Say "REFUSED: $new already exists; nothing changed"; exit 1 }
if (-not (Test-Path 'C:\kals-repo\results\patch_0925t.py')) { Say "REFUSED: C:\kals-repo\results\patch_0925t.py is missing (pull the commit first); nothing changed"; exit 1 }
$vrepo = [IO.File]::ReadAllText('C:\kals-repo\results\VERSIONS.md')
if ($vrepo -notmatch 'v-0925t') { Say "REFUSED: C:\kals-repo\results\VERSIONS.md has no v-0925t entry (pull the commit first); nothing changed"; exit 1 }
$quote = 'Whatever changes you proposed in your last message just push them yourself'
$prevPos = '    "--loss-abort", "-60.00", "--max-positions", "3", "--max-losses", "0",'
$prevOdds = '    "--hedge-odds-mult", "1.25", "--hedge-odds-min-tau", "11",'
$posBlock = @(
  ('    # v-maxpos5 2026-11-04 (operator: "' + $quote + '"): --max-positions 3 -> 5. A 1.5x boosted position plus its covering hedge already reaches the 3.0x SIZE line that paused every new entry (ETH 10-27); the cap is a.max_positions x SIZE in risk_abort, over 6 refused. An entry that proceeds past 3x SIZE open is logged as open_cap_relaxed. Revert: "5" back to "3".'),
  '    "--loss-abort", "-60.00", "--max-positions", "5", "--max-losses", "0",'
) -join "`r`n"
$oddsBlock = @(
  $prevOdds,
  ('    # v-0925t 2026-11-04 (operator: "' + $quote + '"): one new build, C:\kals-live-0925t = 0925r + results\patch_0925t.py (pinrun 9e04c0252ac9, pintake b3c7bb48abb5, ordercli unchanged). Three new flags, each = 0925r behaviour when omitted:'),
  '    #   --hedge-tick round: the hedge limit (ask + --hedge-slip) is snapped DOWN to the market''s own price grid (15-minute series 0.1c under 10c and from 90c, KXBTCD whole cents); 202 of 202 off-grid hedge sends 10-31..11-04 were rejected by Kalshi and re-sent every second for nothing.',
  '    #   --jump-hedge-min-ask 0.05: a JUMP-triggered hedge (belief still over the 0.40 line, no panic) sends nothing while the hedge side asks under 5c (36 such fires, 0 saves, -$230 at size 322); the belief line, a panic and a dearer ask hedge as before. Logged as hedge_cheap_skip.',
  '    #   --boost-rail off: the band/late boost is no longer switched off for the run by a losing leg (all 3 trips since 10-21 were 5-7c jump-hedge legs on markets whose boosted side WON; the boost was off 110 of 328 h); every losing leg of a boosted market is logged as boost_rail_kept so the tracker prices what the rail would have done.',
  '    #   Always on in this build: the odds-line extra fires on belief under 0.40 whatever the alarm label (never a stale-index alarm); pintake judges the extra with the stake cap and the loss abort (extra=True, extra_stake_capped); hedge records carry the ask ladder and the grid fields; --max-positions 3 -> 5 above. In the build but OFF: the late-1.5x bypass fix (--late-bypass-fix, default off; as built it would trim 23 winning late adds to save one loss). Tracked by research\pinrules_watch.py and the phone''s /fixes.',
  '    #   Revert: delete this comment block and the flag line under it, "--max-positions" back to "3" above, $code/$codeSha/$pintakeSha back to C:\kals-live-0925r / ca156bf45704 / 9150d6b65968 (backups *.before-0925t-*), rerun restart_bot while flat.',
  '    "--hedge-tick", "round", "--jump-hedge-min-ask", "0.05", "--boost-rail", "off",'
) -join "`r`n"
$edits = @(
  @('$code = "C:\kals-live-0925r"', '$code = "C:\kals-live-0925t"'),
  @('$codeSha = "ca156bf45704"', '$codeSha = "9e04c0252ac9"'),
  @('$pintakeSha = "9150d6b65968"', '$pintakeSha = "b3c7bb48abb5"'),
  @($prevPos, $posBlock),
  @($prevOdds, $oddsBlock)
)
foreach ($f in $launchers) {
  $t = [IO.File]::ReadAllText($f)
  foreach ($w in @('hedge-tick', 'jump-hedge-min-ask', 'boost-rail', 'v-maxpos5', 'kals-live-0925t')) {
    if ($t -match [regex]::Escape($w)) { Say "REFUSED: $f already mentions $w; nothing changed"; exit 1 }
  }
  foreach ($e in $edits) {
    $n = ([regex]::Matches($t, [regex]::Escape($e[0]))).Count
    if ($n -ne 1) { Say ("REFUSED: {0}: expected once, found {1}: {2}; nothing changed" -f $f, $n, $e[0]); exit 1 }
  }
}
Say "preconditions ok: $old is $oldSha / $oldPintakeSha / $ordercliSha, both launchers point at it, VERSIONS.md has the entry"
# ---- 2. the new build
Copy-Item -Recurse $old $new
Get-ChildItem -Recurse -Directory -Filter '__pycache__' $new | Remove-Item -Recurse -Force
$pout = & $py -u 'C:\kals-repo\results\patch_0925t.py' $new 2>&1 | Out-String
Say ("patch: " + $pout.Trim())
$got = Sha12 "$new\research\pinrun.py"
if ($got -ne $newSha) { Say "REFUSED: the patched pinrun.py is $got, expected $newSha; $new left for inspection, launchers untouched"; exit 1 }
$gotT = Sha12 "$new\research\pintake.py"
if ($gotT -ne $newPintakeSha) { Say "REFUSED: the patched pintake.py is $gotT, expected $newPintakeSha; $new left for inspection, launchers untouched"; exit 1 }
$gotO = Sha12 "$new\research\ordercli.py"
if ($gotO -ne $ordercliSha) { Say "REFUSED: ordercli.py is $gotO, expected $ordercliSha unchanged; $new left for inspection, launchers untouched"; exit 1 }
Say "new build ok: $new\research\pinrun.py code_sha $got, pintake.py $gotT, ordercli.py $gotO"
Copy-Item 'C:\kals-repo\results\VERSIONS.md' "$new\results\VERSIONS.md" -Force
# ---- 3. the launchers
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$baks = @{}
function RestoreAll { foreach ($k in $baks.Keys) { Copy-Item $baks[$k] $k -Force }; Say "both launchers restored from their backups" }
foreach ($f in $launchers) {
  $t = [IO.File]::ReadAllText($f)
  $bytes = [IO.File]::ReadAllBytes($f)
  $bom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
  $bak = $f + ".before-0925t-" + $stamp
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
$must = @("code_sha $newSha", "pintake\.py sha256\[:12\] $newPintakeSha", "ordercli\.py sha256\[:12\] $ordercliSha",
  '--hedge-tick round', '--jump-hedge-min-ask 0\.05', '--boost-rail off', '--max-positions 5',
  '--hedge-odds-mult 1\.25', '--hedge-odds-min-tau 11', '--ws-later-fall-c 10', '--hedge-jump-max 8',
  '--bank-brake 3\.00', '--band99-ceiling 0\.99', '--band-mult 0\.955 0\.981 1\.5', '--late-mult 1\.5')
function Missing($txt) { @($must | Where-Object { $txt -notmatch $_ }) }
$chk2 = & powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\kals-repo\restart_bot.ps1' -Check 2>&1 | Out-String
Add-Content -Path $log -Value $chk2
$miss = Missing $chk2
if ($miss.Count -or $chk2 -match '--max-positions 3' -or $chk2 -match 'ABORTING') { Say ("the keep-alive launcher's -Check did not show the new build and every flag; missing: " + ($miss -join ' | ')); RestoreAll; exit 1 }
Say "keep-alive launcher -Check ok"
$chk = & powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\kals-live-0925n\restart_bot.ps1' -Check 2>&1 | Out-String
Add-Content -Path $log -Value $chk
$line = ($chk -split "`n" | Where-Object { $_ -match 'kals-live-0925t\\research\\pinrun\.py' -and $_ -match '--hedge-tick round' -and $_ -match '--jump-hedge-min-ask 0\.05' -and $_ -match '--boost-rail off' -and $_ -match '--max-positions 5' } | Select-Object -First 1)
$miss = Missing $chk
if (-not $line -or $miss.Count -or $chk -match '--max-positions 3' -or $chk -match 'ABORTING') { Say ("the hand launcher's -Check did not show the new build with every flag; missing: " + ($miss -join ' | ')); RestoreAll; exit 1 }
Say "hand launcher -Check ok"
# ---- 5. the full-argv self-test on the new build, before anything stops
$argv = ($line.Trim() -split '\s+')
$i = [array]::IndexOf($argv, ($argv | Where-Object { $_ -like '*pinrun.py' } | Select-Object -First 1))
$targs = @('-u', "$new\research\pinrun.py") + $argv[($i + 1)..($argv.Length - 1)] + @('--selftest')
Say ("self-test: " + ($targs -join ' '))
New-Item -ItemType Directory -Force "$new\selftest" | Out-Null
$p = Start-Process -FilePath $py -ArgumentList $targs -RedirectStandardOutput "$new\selftest\0925t_selftest.out" -RedirectStandardError "$new\selftest\0925t_selftest.err" -NoNewWindow -PassThru
$null = $p.Handle   # PowerShell 5: without this ExitCode is empty after WaitForExit
try { $p.PriorityClass = "BelowNormal" } catch {}
$p.WaitForExit()
$so = Get-Content "$new\selftest\0925t_selftest.out" -Raw
$nok = ([regex]::Matches($so, '(?m)^  ok   ')).Count
$nfail = ([regex]::Matches($so, '(?m)^  FAIL ')).Count
if ($p.ExitCode -ne 0 -or $so -notmatch 'SELF-TEST PASSED' -or $nfail -ne 0) { Say ("self-test FAILED (exit {0}, {1} ok, {2} FAIL lines); see $new\selftest\0925t_selftest.out" -f $p.ExitCode, $nok, $nfail); RestoreAll; exit 1 }
Say ("self-test PASSED ({0} ok, 0 FAIL) with the full new argv" -f $nok)
# ---- 6. the restart (restart_bot waits for pin to be flat)
$cmd = 'cmd /c "powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-live-0925n\restart_bot.ps1 > C:\kals-repo\results\pin_0925t_restart.out 2>&1"'
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = 'C:\kals-live-0925n' }
Say ("restart launched, wrapper pid {0} (return {1}); watch C:\kals-repo\results\pin_0925t_restart.out" -f $r.ProcessId, $r.ReturnValue)
