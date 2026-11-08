# pin_0925u.ps1 -- 2026-11-07. Operator: "Sure. Make sure to log and track the difference it makes and what it would've
# been without the rule" (the rule: no first buy under 98c in markets closing 6 to 10 AM ET).
# Puts pin on a NEW build, C:\kals-live-0925u = C:\kals-live-0925t (pinrun code_sha 9e04c0252ac9, pintake b3c7bb48abb5,
# ordercli 467782077a23) + results\patch_0925u.py (pinrun e0ba3543e7be; pintake and ordercli unchanged), with one new flag
# switched on:
#   --cheap-window 6 10 0.98 (v-cheapwin): a FIRST buy (nothing held on the market) whose ask is under 98c, in a market
#     closing 06:00 <= Eastern hour < 10:00, is refused and the market is skipped for the close. Every refusal is
#     shadowed in pin's own log (the size it would have asked, the belief hedge it would have bought, the result:
#     cheap_window_settled) and priced on the phone's /fixes as change K, with "without the rule" beside it.
#   Evidence, the read (11-21) and the revert: results\VERSIONS.md, the v-0925u entry.
# STEPS (anything wrong before step 6 restores both launchers and stops; the running pin is never touched before 6):
#   1. refuse unless 0925t is still 9e04c0252ac9 / b3c7bb48abb5 / 467782077a23, 0925u does not exist yet, both launchers
#      (C:\kals-live-0925n's, the hand launcher, and C:\kals-repo's, which watch_bot.ps1 uses) still point at 0925t /
#      9e04c0252ac9 / b3c7bb48abb5 and carry no --cheap-window, and the repo's VERSIONS.md carries the v-0925u entry
#   2. copy 0925t -> 0925u, patch 0925u (research\pinrun.py only), refuse unless pinrun is exactly e0ba3543e7be and
#      pintake / ordercli are unchanged
#   3. edit BOTH launchers: $code -> 0925u, $codeSha -> e0ba3543e7be, the flag after the v-0925t flag line (backups kept,
#      parse-checked); the build's own copy of the launcher and of VERSIONS.md too
#   4. -Check (both launchers): the two argv must match and show the new flag and the unchanged ones
#   5. the FULL new argv + --selftest on the new build at BelowNormal priority: must print SELF-TEST PASSED, 0 FAIL
#   6. wait until research\pinflat.py says FLAT (at most 25 minutes), then restart pin through
#      C:\kals-live-0925n\restart_bot.ps1 by WMI; if it refuses because pin bought again, wait for flat again (3 tries).
#      If no flat moment comes, the launchers stay edited and pin's next restart (watch_bot, or its own 72 h end at
#      ~05:17 ET 11-10) starts the new build; the log says so.
# REVERT: copy the two .before-0925u-* backups over the launchers and rerun restart_bot while flat (0925t untouched).
# Log: results\pin_0925u.out; the restart's own output: results\pin_0925u_restart.out
$log = 'C:\kals-repo\results\pin_0925u.out'
$rout = 'C:\kals-repo\results\pin_0925u_restart.out'
function Say($m) { $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m; Write-Output $l; Add-Content -Path $log -Value $l }
# SUPERSEDED 2026-11-07 by results\pin_0925v.ps1, which goes from live 0925t straight to 0925v = this build's
# cheap-window flag PLUS the fail-safe fixes. Run alone, this script would install 0925u and make pin_0925v.ps1
# refuse for good (it refuses once C:\kals-live-0925u exists), stranding the fixes. Kept for the record; it refuses.
Say "REFUSED: superseded by C:\kals-repo\results\pin_0925v.ps1 (0925t -> 0925v: --cheap-window 6 10 0.98 plus the v-0925v fail-safe fixes); nothing changed"; exit 1
$py = 'C:\Python314\python.exe'
$old = 'C:\kals-live-0925t'
$new = 'C:\kals-live-0925u'
$oldSha = '9e04c0252ac9'
$newSha = 'e0ba3543e7be'
$pintakeSha = 'b3c7bb48abb5'
$ordercliSha = '467782077a23'
$launchers = @('C:\kals-live-0925n\restart_bot.ps1', 'C:\kals-repo\restart_bot.ps1')
function Sha12($p) { (Get-FileHash -Algorithm SHA256 -Path $p).Hash.ToLower().Substring(0, 12) }
Say "start"
# ---- 1. preconditions
if ((Sha12 "$old\research\pinrun.py") -ne $oldSha) { Say "REFUSED: $old\research\pinrun.py is not $oldSha; nothing changed"; exit 1 }
if ((Sha12 "$old\research\pintake.py") -ne $pintakeSha) { Say "REFUSED: $old\research\pintake.py is not $pintakeSha; nothing changed"; exit 1 }
if ((Sha12 "$old\research\ordercli.py") -ne $ordercliSha) { Say "REFUSED: $old\research\ordercli.py is not $ordercliSha; nothing changed"; exit 1 }
if (Test-Path $new) { Say "REFUSED: $new already exists; nothing changed"; exit 1 }
if (-not (Test-Path 'C:\kals-repo\results\patch_0925u.py')) { Say "REFUSED: C:\kals-repo\results\patch_0925u.py is missing (pull the commit first); nothing changed"; exit 1 }
$vrepo = [IO.File]::ReadAllText('C:\kals-repo\results\VERSIONS.md')
if ($vrepo -notmatch 'v-0925u') { Say "REFUSED: C:\kals-repo\results\VERSIONS.md has no v-0925u entry (pull the commit first); nothing changed"; exit 1 }
$quote = "Sure. Make sure to log and track the difference it makes and what it would've been without the rule"
$prevFlags = '    "--hedge-tick", "round", "--jump-hedge-min-ask", "0.05", "--boost-rail", "off",'
$cwBlock = @(
  $prevFlags,
  ('    # v-0925u 2026-11-07 (operator: "' + $quote.Replace('"', "'") + '"): one new build, C:\kals-live-0925u = 0925t + results\patch_0925u.py (pinrun e0ba3543e7be; pintake and ordercli unchanged). One new flag, = 0925t when omitted:'),
  '    #   --cheap-window 6 10 0.98: a FIRST buy (nothing held) under 98c in a market closing 06:00-10:00 ET is refused and the market skipped for the close; markets closing 06-10 ET were the only losing stretch of the day from 10-01 (-$273.18 vs +$1,767.17 the rest of the day), first buys under 98c there lost (287 markets -$73.31) and 98c+ made money (+$72.64); September went the other way, so it is a TRIAL WITH A SHADOW.',
  '    #   Every skip is shadowed in the log (refused gate cheap_window + cheap_window_settled: the size it would have asked, the belief hedge it would have bought, the result) and priced on the phone as /fixes change K, "without the rule" beside it; pinrules_watch alerts on any $10+ skip. Read 11-21: keep if K net >= $0.',
  '    #   Revert: delete this comment block and the flag line under it, $code/$codeSha back to C:\kals-live-0925t / 9e04c0252ac9 (backups *.before-0925u-*), rerun restart_bot while flat.',
  '    "--cheap-window", "6", "10", "0.98",'
) -join "`r`n"
$edits = @(
  @('$code = "C:\kals-live-0925t"', '$code = "C:\kals-live-0925u"'),
  @('$codeSha = "9e04c0252ac9"', '$codeSha = "e0ba3543e7be"'),
  @($prevFlags, $cwBlock)
)
foreach ($f in $launchers) {
  $t = [IO.File]::ReadAllText($f)
  foreach ($w in @('cheap-window', 'v-0925u', 'kals-live-0925u')) {
    if ($t -match [regex]::Escape($w)) { Say "REFUSED: $f already mentions $w; nothing changed"; exit 1 }
  }
  if ($t -notmatch [regex]::Escape(('$pintakeSha = "' + $pintakeSha + '"'))) { Say "REFUSED: $f does not pin pintake $pintakeSha; nothing changed"; exit 1 }
  foreach ($e in $edits) {
    $n = ([regex]::Matches($t, [regex]::Escape($e[0]))).Count
    if ($n -ne 1) { Say ("REFUSED: {0}: expected once, found {1}: {2}; nothing changed" -f $f, $n, $e[0]); exit 1 }
  }
}
Say "preconditions ok: $old is $oldSha / $pintakeSha / $ordercliSha, both launchers point at it, VERSIONS.md has the entry"
# ---- 2. the new build
Copy-Item -Recurse $old $new
Get-ChildItem -Recurse -Directory -Filter '__pycache__' $new | Remove-Item -Recurse -Force
$pout = & $py -u 'C:\kals-repo\results\patch_0925u.py' $new 2>&1 | Out-String
Say ("patch: " + $pout.Trim())
$got = Sha12 "$new\research\pinrun.py"
if ($got -ne $newSha) { Say "REFUSED: the patched pinrun.py is $got, expected $newSha; $new left for inspection, launchers untouched"; exit 1 }
$gotT = Sha12 "$new\research\pintake.py"
if ($gotT -ne $pintakeSha) { Say "REFUSED: pintake.py is $gotT, expected $pintakeSha unchanged; $new left for inspection, launchers untouched"; exit 1 }
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
  $bak = $f + ".before-0925u-" + $stamp
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
$must = @("code_sha $newSha", "pintake\.py sha256\[:12\] $pintakeSha", "ordercli\.py sha256\[:12\] $ordercliSha",
  '--cheap-window 6 10 0\.98',
  '--hedge-tick round', '--jump-hedge-min-ask 0\.05', '--boost-rail off', '--max-positions 5',
  '--hedge-odds-mult 1\.25', '--hedge-odds-min-tau 11', '--ws-later-fall-c 10', '--hedge-jump-max 8',
  '--bank-brake 3\.00', '--band99-ceiling 0\.99', '--band-mult 0\.955 0\.981 1\.5', '--late-mult 1\.5')
function Missing($txt) { @($must | Where-Object { $txt -notmatch $_ }) }
$chk2 = & powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\kals-repo\restart_bot.ps1' -Check 2>&1 | Out-String
Add-Content -Path $log -Value $chk2
$miss = Missing $chk2
if ($miss.Count -or $chk2 -match 'ABORTING') { Say ("the keep-alive launcher's -Check did not show the new build and every flag; missing: " + ($miss -join ' | ')); RestoreAll; exit 1 }
Say "keep-alive launcher -Check ok"
$chk = & powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\kals-live-0925n\restart_bot.ps1' -Check 2>&1 | Out-String
Add-Content -Path $log -Value $chk
$line = ($chk -split "`n" | Where-Object { $_ -match 'kals-live-0925u\\research\\pinrun\.py' -and $_ -match '--cheap-window 6 10 0\.98' -and $_ -match '--hedge-tick round' } | Select-Object -First 1)
$miss = Missing $chk
if (-not $line -or $miss.Count -or $chk -match 'ABORTING') { Say ("the hand launcher's -Check did not show the new build with every flag; missing: " + ($miss -join ' | ')); RestoreAll; exit 1 }
Say "hand launcher -Check ok"
# ---- 5. the full-argv self-test on the new build, before anything stops
$argv = ($line.Trim() -split '\s+')
$i = [array]::IndexOf($argv, ($argv | Where-Object { $_ -like '*pinrun.py' } | Select-Object -First 1))
$targs = @('-u', "$new\research\pinrun.py") + $argv[($i + 1)..($argv.Length - 1)] + @('--selftest')
Say ("self-test: " + ($targs -join ' '))
New-Item -ItemType Directory -Force "$new\selftest" | Out-Null
$p = Start-Process -FilePath $py -ArgumentList $targs -RedirectStandardOutput "$new\selftest\0925u_selftest.out" -RedirectStandardError "$new\selftest\0925u_selftest.err" -NoNewWindow -PassThru
$null = $p.Handle   # PowerShell 5: without this ExitCode is empty after WaitForExit
try { $p.PriorityClass = "BelowNormal" } catch {}
$p.WaitForExit()
$so = Get-Content "$new\selftest\0925u_selftest.out" -Raw
$nok = ([regex]::Matches($so, '(?m)^  ok   ')).Count
$nfail = ([regex]::Matches($so, '(?m)^  FAIL ')).Count
$ncw = ([regex]::Matches($so, '(?m)^  ok   v-cheapwin')).Count
if ($p.ExitCode -ne 0 -or $so -notmatch 'SELF-TEST PASSED' -or $nfail -ne 0 -or $ncw -ne 6) { Say ("self-test FAILED (exit {0}, {1} ok, {2} FAIL lines, {3} of 6 v-cheapwin ok); see $new\selftest\0925u_selftest.out" -f $p.ExitCode, $nok, $nfail, $ncw); RestoreAll; exit 1 }
Say ("self-test PASSED ({0} ok, 0 FAIL, the 6 v-cheapwin checks ok) with the full new argv" -f $nok)
# ---- 6. wait for flat, then the restart through the hand launcher (restart_bot refuses while pin holds a bet)
$deadline = (Get-Date).AddMinutes(25)
$saidWait = $false
for ($try = 1; $try -le 3; $try++) {
  while ($true) {
    $fo = & $py 'C:\kals-repo\research\pinflat.py' 2>&1 | Out-String
    $fc = $LASTEXITCODE
    if ($fc -eq 0) { Say ("pin is flat: " + $fo.Trim()); break }
    if ((Get-Date) -gt $deadline) { Say ("NOT RESTARTED: pin was not flat within 25 minutes (last answer: " + $fo.Trim() + "). The launchers ARE edited, so pin's next restart (watch_bot, or its own end ~05:17 ET 11-10) starts 0925u; /approve pinrestart restarts it sooner"); exit 2 }
    if (-not $saidWait) { Say ("pin holds a bet, waiting for flat (pinflat exit $fc): " + $fo.Trim()); $saidWait = $true }
    Start-Sleep -Seconds 15
  }
  $saidWait = $false
  $cmd = 'cmd /c "powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-live-0925n\restart_bot.ps1 > C:\kals-repo\results\pin_0925u_restart.out 2>&1"'
  $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = 'C:\kals-live-0925n' }
  Say ("restart launched (try $try), wrapper pid {0} (return {1}); its output: $rout" -f $r.ProcessId, $r.ReturnValue)
  if ($r.ReturnValue -ne 0) { Say "WMI refused to start the restart wrapper; nothing restarted (the launchers ARE edited)"; exit 2 }
  $wp = Get-Process -Id $r.ProcessId -ErrorAction SilentlyContinue
  if ($wp) { $wp.WaitForExit(240000) | Out-Null }
  $txt = ''
  if (Test-Path $rout) { $txt = [string](Get-Content $rout -Raw -ErrorAction SilentlyContinue) }
  if ($txt -match 'pinrun running: pid (\d+)') { Say ("DONE: pin restarted on 0925u (code_sha $newSha, --cheap-window 6 10 0.98), new pid " + $matches[1]); exit 0 }
  if ($txt -match 'REFUSING: the bot is holding a position') { Say "restart_bot refused: pin bought again between the flat check and the restart; waiting for flat again"; continue }
  $tail = @(($txt -split "`r?`n") | Where-Object { $_.Trim() } | Select-Object -Last 6)
  Say ("restart_bot did not report a running pin; its last lines: " + ($tail -join ' | ') + "; if pin is down, watch_bot restarts it (on 0925u) within minutes")
  exit 2
}
Say "NOT RESTARTED after 3 tries: pin kept holding a bet at the restart moment; the launchers ARE edited (next restart starts 0925u)"
exit 2
