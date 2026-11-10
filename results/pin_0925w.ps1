# pin_0925w.ps1 -- 2026-11-10. Operator 11-09: "the bot needs to be as utterly fast as it can possibly be"; 11-10: "Why
# would being faster need to be a shadow? ... I'm not understanding why we purposefully aren't as fast as possible".
# WHAT IT DOES: puts pin on a NEW build, C:\kals-live-0925w = C:\kals-live-0925v (pinrun d51b131b55cf, pintake b3c7bb48abb5,
#   ordercli 467782077a23) + results\patch_0925w.py (pinrun 05a01fbb5ed2; pintake and ordercli unchanged), and adds ONE argv
#   line to BOTH live launchers, right after "--hedge-jump-shadow", "6",:
#       "--index-5hz", "<Mode>",          (-Mode shadow or -Mode hedge; required)
#   with a v-hedge5 comment above it; $code / $codeSha move to the new build. Every other flag stays.
#   v-hedge5 (patch_0925w.py): Kalshi streams the settlement index 5x a second (cfbenchmarks_value_5hz) for BTC, ETH, SOL,
#   XRP and DOGE; pin read it once a second. In BOTH modes pin subscribes to it, takes each whole-second print from it when
#   it lands first (~40 ms sooner, identical values; the 1 Hz print still overwrites), keeps the sub-second prints out of
#   settlement, and computes the hedge's belief on the newest 5 Hz print too (hedge_quote belief5; hedge_alarm belief_1hz /
#   belief5 / fast_ms / by_5hz).
#     shadow: nothing is sent on the 5 Hz belief; ONE hedge5_shadow record per position says what the belief hedge would
#       have bought the first second the 5 Hz belief was under 0.40 while the 1 Hz one was not.
#     hedge: the belief hedge fires on the LOWER of the two beliefs (it can only add a trigger), so on those five coins it
#       hedges up to ~0.8 s sooner (offline: the same flip hedged at t 5.55 s instead of 6.95 s); every 5 Hz-led hedge is
#       tagged by_5hz=true so its saves and its false alarms are priced from day one.
#   BNB, ZEC, NEAR and HYPE have no 5 Hz feed and behave exactly as today.
# HOW TO RUN (on the server, after `git pull --no-rebase`):
#     powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-repo\results\pin_0925w.ps1 -Mode shadow   (or -Mode hedge)
#   It RE-LAUNCHES ITSELF DETACHED (WMI) and this window only follows its log; -Foreground runs it in this window.
# STEPS (anything wrong before step 5 changes no live launcher; the running pin is never touched before step 6):
#   1. refuse unless 0925v is d51b131b55cf / b3c7bb48abb5 / 467782077a23 with all nine modules, 0925w does not exist yet,
#      patch_0925w.py is there, VERSIONS.md carries the v-hedge5 entry, both launchers point at 0925v / d51b131b55cf, carry
#      "--hedge-jump-shadow", "6", exactly once on a line of its own, and carry no --index-5hz argv, no v-hedge5 text and no
#      kals-live-0925w.
#   2. copy 0925v -> 0925w (no __pycache__, selftest or jumpshadow folders), patch it, refuse unless pinrun is exactly
#      05a01fbb5ed2 and pintake / ordercli are unchanged.
#   3. write BOTH edited launchers as COPIES (C:\kals-live-0925w\deploy5\): $code, $codeSha and the one new argv line, every
#      other byte as it was; parse-check, the two argv must match, they differ from the live argv by exactly the one added
#      pair, -Check of the hand copy must show the new build, code_sha 05a01fbb5ed2, --index-5hz <Mode> and every live flag.
#   4. the FULL new argv + --selftest on 0925w at BelowNormal priority, at most 10 minutes: SELF-TEST PASSED, 0 FAIL and
#      EXACTLY 1615 ok lines (the live 1604 + the 11 v-hedge5 checks; measured 11-10 on a byte copy of the build), the 11
#      v-hedge5, 120 v-0925v and 6 v-cheapwin among them.
#   5. back up both live launchers (.before-0925w-<stamp>, hash-checked), write the checked copies over them (hash-checked),
#      -Check both; any failure restores both and stops.
#   6. wait until pin is FLAT and the clock is clear (>= 20 s after a quarter-hour close, >= 150 s before the next; 25 + 15
#      minutes at most), restart through C:\kals-live-0925n\restart_bot.ps1 by WMI (3 tries if pin bought again).
#   7. WATCH 6 minutes: the start record must carry code_sha 05a01fbb5ed2, index_5hz <Mode>, hedge_jump_shadow 6 and hedge_jump
#      null; the feeds record must show the index up (> 10 ticks, BRTI among the feeds); a universe refresh must answer with
#      markets; the process must be alive. Anything wrong: both launchers back (hash-checked) and pin restarted exactly as in
#      step 6 on 0925v, CONFIRMED from pin's own records. Whether the 5 Hz feed itself arrived (index5_up / index5_silent) is
#      reported; a silent feed is NOT rolled back (pin then behaves exactly as 0925v).
#   8. after a restart: both live launchers to results\live_launcher_snapshot\ (SHA256SUMS.txt in LF); nothing is committed.
# EXIT: 0 = restarted on 0925w and healthy; 1 = refused, launchers unchanged; 2 = launchers edited, not restarted (pin's next
#   restart starts 0925w); 3 = rolled back to 0925v, CONFIRMED; 4 = 0925w runs but was not healthy at the end of the watch,
#   or the 5 Hz feed was silent: not reverted, see the log; 5 = a person must look (a restore or the rollback could not be
#   confirmed); 6 = (follower) the worker did not finish in 120 minutes.
# REVERT: copy the two .before-0925w-* backups over the launchers and rerun restart_bot while flat (0925v untouched). Or
#   switch modes without a rebuild: the one argv line "--index-5hz", "<Mode>", to "off" / "shadow" / "hedge".
# Log: results\pin_0925w.out; the worker's console: results\pin_0925w_worker.out; each restart's own output:
#   results\pin_0925w_restart-<tag>-<HHmmss>.out
param([switch]$Child, [switch]$Foreground, [string]$RunId = '', [string]$Mode = '')
$log = 'C:\kals-repo\results\pin_0925w.out'
$routPre = 'C:\kals-repo\results\pin_0925w_restart-'
$wout = 'C:\kals-repo\results\pin_0925w_worker.out'
function Say($m) { $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m; [Console]::Out.WriteLine($l); Add-Content -Path $log -Value $l }
if ($Mode -ne 'shadow' -and $Mode -ne 'hedge') { Write-Output "REFUSED: give -Mode shadow or -Mode hedge (got '$Mode'); nothing was run"; exit 1 }

# ---- 0. the follower: start the worker detached, follow its log, exit with its code
if (-not $Child -and -not $Foreground) {
  $rid = (Get-Date -Format 'yyyyMMddHHmmss') + '-' + $PID
  $me = $MyInvocation.MyCommand.Path
  $cmd = 'cmd /c "powershell -NoProfile -ExecutionPolicy Bypass -File ' + $me + ' -Child -RunId ' + $rid + ' -Mode ' + $Mode + ' > ' + $wout + ' 2>&1"'
  $start0 = 0
  if (Test-Path $log) { $start0 = (Get-Item $log).Length }
  $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = 'C:\kals-repo' }
  if ($r.ReturnValue -ne 0) { Write-Output "WMI refused to start the worker (return $($r.ReturnValue)); nothing was run"; exit 1 }
  Write-Output ("worker started detached, pid {0}, run {1}; following {2} (closing this window does not stop it)" -f $r.ProcessId, $rid, $log)
  $deadline = (Get-Date).AddMinutes(120)   # step 5 and a rollback may each wait 25 + 15 minutes
  $pos = $start0
  while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 5
    if (-not (Test-Path $log)) { continue }
    $len = (Get-Item $log).Length
    if ($len -le $pos) { continue }
    $fs = [IO.File]::Open($log, 'Open', 'Read', 'ReadWrite')
    try {
      [void]$fs.Seek($pos, 'Begin')
      $sr = New-Object IO.StreamReader($fs)
      $chunk = $sr.ReadToEnd()
    } finally { $fs.Close() }
    $pos = $len
    Write-Output $chunk.TrimEnd()
    $mm = [regex]::Match($chunk, ('RUN ' + [regex]::Escape($rid) + ' EXIT (\d)'))
    if ($mm.Success) { exit ([int]$mm.Groups[1].Value) }
  }
  Write-Output "the worker has not finished within 120 minutes; it may still be running (pid $($r.ProcessId)) -- read $log"
  exit 6
}
if (-not $RunId) { $RunId = 'fg-' + (Get-Date -Format 'yyyyMMddHHmmss') }
function Done($code, $m) { if ($m) { Say $m }; Say ("RUN {0} EXIT {1}" -f $RunId, $code); exit $code }

$py = 'C:\Python314\python.exe'
$old = 'C:\kals-live-0925v'
$build = 'C:\kals-live-0925w'
$oldSha = 'd51b131b55cf'
$codeSha = '05a01fbb5ed2'
$pintakeSha = 'b3c7bb48abb5'
$ordercliSha = '467782077a23'
$nOkPinned = 1615  # the live 1604 + the 11 v-hedge5 checks, measured 11-10 in all three modes. PowerShell names are
                      # case-insensitive, so the count read from the run is $nOkSeen, never $nok
$nH5 = 11
$nV = 120
$nCheapwin = 6
$modules = @('pinrun.py', 'pintake.py', 'ordercli.py', 'kauth.py', 'livebook.py', 'engine.py', 'pinxfer.py', 'downtime.py', 'pinflat.py')
$launchers = @('C:\kals-live-0925n\restart_bot.ps1', 'C:\kals-repo\restart_bot.ps1')
$copies = @("$build\deploy5\restart_bot_hand.ps1", "$build\deploy5\restart_bot_repo.ps1")
$anchor = '    "--hedge-jump-shadow", "6",'
$newLine = '    "--index-5hz", "' + $Mode + '",'
function Sha12($p) { try { (Get-FileHash -Algorithm SHA256 -Path $p -ErrorAction Stop).Hash.ToLower().Substring(0, 12) } catch { $null } }
function Sha64($p) { try { (Get-FileHash -Algorithm SHA256 -Path $p -ErrorAction Stop).Hash.ToLower() } catch { $null } }
function Native($exe, [string[]]$argv) { $ErrorActionPreference = 'Continue'; $o = & $exe @argv 2>&1 | Out-String; return @($o, $LASTEXITCODE) }
# the start record, read the way pinrun writes it: 'new' = code_sha 05a01fbb5ed2 with index_5hz <Mode>, the jump hedge in shadow
# (hedge_jump null, hedge_jump_shadow 6); 'old' = code_sha d51b131b55cf (no index_5hz field) with the same jump fields
function RunMode($d) {
  $sha = $null; $hj = $null; $hs = $null; $m5 = $null
  try { $sha = [string]$d.code_sha } catch {}
  try { $hj = $d.hedge_jump } catch {}
  try { $hs = $d.hedge_jump_shadow } catch {}
  try { $m5 = $d.index_5hz } catch {}
  $jumpOk = ($null -eq $hj -and $null -ne $hs -and ([double]$hs -eq 6.0))
  if ($sha -eq $codeSha -and $jumpOk -and ([string]$m5 -eq $Mode)) { return 'new' }
  if ($sha -eq $oldSha -and $jumpOk -and $null -eq $m5) { return 'old' }
  return ('code_sha=' + $sha + ' index_5hz=' + $(if ($null -eq $m5) { 'null' } else { [string]$m5 }) + ' hedge_jump=' + $(if ($null -eq $hj) { 'null' } else { [string]$hj }) + ' hedge_jump_shadow=' + $(if ($null -eq $hs) { 'null' } else { [string]$hs }))
}
$baks = @{}
$orig = @{}
$script:edited = $false
function RestoreAll {
  $bad = 0
  foreach ($k in $baks.Keys) {
    try { Copy-Item $baks[$k] $k -Force -ErrorAction Stop } catch { Say ("RESTORE COPY FAILED for {0}: {1}" -f $k, $_.Exception.Message) }
    if ((Sha64 $k) -ne $orig[$k]) { Say "RESTORE FAILED: $k is not its pre-edit bytes (backup $($baks[$k]))"; $bad++ }
  }
  if ($bad) { return $false }
  Say "both launchers restored from their backups (sha256 checked against the pre-edit files)"
  return $true
}
Say "start (run $RunId, mode $Mode)"
$ErrorActionPreference = 'Stop'
try {
  # ---- 1. preconditions
  if ((Sha12 "$old\research\pinrun.py") -ne $oldSha) { Done 1 "REFUSED: $old\research\pinrun.py is not $oldSha; nothing changed" }
  if ((Sha12 "$old\research\pintake.py") -ne $pintakeSha) { Done 1 "REFUSED: $old\research\pintake.py is not $pintakeSha; nothing changed" }
  if ((Sha12 "$old\research\ordercli.py") -ne $ordercliSha) { Done 1 "REFUSED: $old\research\ordercli.py is not $ordercliSha; nothing changed" }
  foreach ($m in $modules) { if (-not (Test-Path "$old\research\$m")) { Done 1 "REFUSED: $old\research\$m is missing; nothing changed" } }
  if (Test-Path $build) { Done 1 "REFUSED: $build already exists (look before deleting it); nothing changed" }
  if (-not (Test-Path 'C:\kals-repo\results\patch_0925w.py')) { Done 1 "REFUSED: C:\kals-repo\results\patch_0925w.py is missing (pull the commit first); nothing changed" }
  $vrepo = [IO.File]::ReadAllText('C:\kals-repo\results\VERSIONS.md')
  if ($vrepo -notmatch 'v-hedge5') { Done 1 "REFUSED: C:\kals-repo\results\VERSIONS.md has no v-hedge5 entry (pull the commit first); nothing changed" }
  try { $gs = Native 'git' @('-C', 'C:\kals-repo', 'status', '--porcelain', '--', 'restart_bot.ps1') } catch { $gs = @(('git not available: ' + $_.Exception.Message), -1) }
  Say ("git status of the keep-alive launcher (expected ' M restart_bot.ps1'): [" + $gs[0].Trim() + "]")
  $texts = @{}
  foreach ($f in $launchers) {
    $t = [IO.File]::ReadAllText($f)
    if ($t -match [regex]::Escape('"--index-5hz"')) { Done 1 "REFUSED: $f already carries the --index-5hz argv; nothing changed" }
    foreach ($w in @('v-hedge5', 'kals-live-0925w')) { if ($t -match [regex]::Escape($w)) { Done 1 "REFUSED: $f already mentions $w; nothing changed" } }
    foreach ($pair in @(
        @('$code = "C:\kals-live-0925v"', 'does not point at C:\kals-live-0925v'),
        @(('$codeSha = "' + $oldSha + '"'), "does not pin pinrun $oldSha"),
        @(('$pintakeSha = "' + $pintakeSha + '"'), "does not pin pintake $pintakeSha"))) {
      $n = ([regex]::Matches($t, [regex]::Escape($pair[0]))).Count
      if ($n -ne 1) { Done 1 ("REFUSED: {0} {1} (found {2}); nothing changed" -f $f, $pair[1], $n) }
    }
    $n = ([regex]::Matches($t, [regex]::Escape($anchor))).Count
    if ($n -ne 1) { Done 1 ("REFUSED: {0}: the anchor line {1} must appear exactly once, found {2}; nothing changed" -f $f, $anchor.Trim(), $n) }
    if ($t -notmatch ('(?m)^' + [regex]::Escape($anchor) + '\s*$')) { Done 1 "REFUSED: ${f}: the anchor line carries more than the flag pair; nothing changed" }
    $texts[$f] = $t
    $orig[$f] = Sha64 $f
  }
  Say "preconditions ok: $old is $oldSha / $pintakeSha / $ordercliSha; $build does not exist; both launchers point at 0925v and carry the jump-shadow line once; VERSIONS.md has the v-hedge5 entry"
  # ---- 2. the new build
  Copy-Item -Recurse $old $build
  foreach ($junk in @('selftest', 'jumpshadow', 'hedge60', 'deploy5')) { if (Test-Path "$build\$junk") { Remove-Item -Recurse -Force "$build\$junk" } }
  Get-ChildItem -Recurse -Directory -Filter '__pycache__' $build | Remove-Item -Recurse -Force
  $pr = Native $py @('-u', 'C:\kals-repo\results\patch_0925w.py', $build)
  Say ("patch: " + $pr[0].Trim())
  if ($pr[1] -ne 0) { Done 1 "REFUSED: patch_0925w.py failed (exit $($pr[1])); $build left for inspection, launchers untouched" }
  $got = Sha12 "$build\research\pinrun.py"
  if ($got -ne $codeSha) { Done 1 "REFUSED: the patched pinrun.py is $got, expected $codeSha; $build left for inspection, launchers untouched" }
  if ((Sha12 "$build\research\pintake.py") -ne $pintakeSha) { Done 1 "REFUSED: pintake.py changed; $build left for inspection, launchers untouched" }
  if ((Sha12 "$build\research\ordercli.py") -ne $ordercliSha) { Done 1 "REFUSED: ordercli.py changed; $build left for inspection, launchers untouched" }
  Copy-Item 'C:\kals-repo\results\VERSIONS.md' "$build\results\VERSIONS.md" -Force
  Say "new build ok: $build\research\pinrun.py code_sha $got; pintake.py and ordercli.py unchanged"
  # ---- 3. the edited launchers, as COPIES first
  if ($Mode -eq 'hedge') {
    $modeWhy = 'the belief hedge fires on the LOWER of the 1 Hz and 5 Hz beliefs (it can only add a trigger; up to ~0.8 s sooner on those five coins); every 5 Hz-led hedge is tagged by_5hz on its hedge_alarm so its saves and false alarms are priced. BNB ZEC NEAR HYPE are unchanged.'
  } else {
    $modeWhy = 'nothing is sent on the 5 Hz belief; ONE hedge5_shadow record per position says what the belief hedge would have bought the first second the 5 Hz belief was under 0.40 while the 1 Hz one was not. Switch to hedge when the read says the saves beat the false alarms.'
  }
  $why = @(
    ('    # v-hedge5 2026-11-10 (operator 11-09: "the bot needs to be as utterly fast as it can possibly be"; 11-10: "Why would being faster need to be a shadow?"): C:\kals-live-0925w = 0925v + results\patch_0925w.py (pinrun ' + $codeSha + '; pintake and ordercli unchanged). The settlement index is streamed 5x a second for BTC ETH SOL XRP DOGE; pin read it once a second. Now it reads both: each whole-second print from whichever channel lands first (~40 ms sooner, identical values), sub-second prints never in settlement, and the hedge belief on the newest 5 Hz print too.'),
    ('    #   --index-5hz ' + $Mode + ': ' + $modeWhy),
    '    #   Revert: this comment block and the line under it out, $code/$codeSha back to C:\kals-live-0925v / d51b131b55cf (backups *.before-0925w-*), rerun restart_bot while flat. Or change the mode only: "off" / "shadow" / "hedge".'
  )
  $edits = @(
    @('$code = "C:\kals-live-0925v"', ('$code = "' + $build + '"')),
    @(('$codeSha = "' + $oldSha + '"'), ('$codeSha = "' + $codeSha + '"'))
  )
  for ($i = 0; $i -lt 2; $i++) {
    $f = $launchers[$i]
    $t = $texts[$f]
    $bytes = [IO.File]::ReadAllBytes($f)
    $bom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
    $ai = $t.IndexOf($anchor)
    $nl = "`n"
    if ($t.Substring($ai + $anchor.Length, [Math]::Min(2, $t.Length - $ai - $anchor.Length)).StartsWith("`r`n")) { $nl = "`r`n" }
    foreach ($e in $edits) { $t = $t.Replace($e[0], $e[1]) }
    $t = $t.Replace($anchor, ($anchor + $nl + ($why -join $nl) + $nl + $newLine))
    New-Item -ItemType Directory -Force (Split-Path $copies[$i] -Parent) | Out-Null
    [IO.File]::WriteAllText($copies[$i], $t, (New-Object System.Text.UTF8Encoding($bom)))
    $errs = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($copies[$i], [ref]$null, [ref]$errs)
    if ($errs.Count) { Done 1 ("REFUSED: the edited copy of {0} has {1} parse errors ({2}); live launchers untouched" -f $f, $errs.Count, $copies[$i]) }
    $tc = [IO.File]::ReadAllText($copies[$i])
    if (([regex]::Matches($tc, [regex]::Escape($newLine))).Count -ne 1 -or ([regex]::Matches($tc, [regex]::Escape($anchor))).Count -ne 1 -or $tc -notmatch [regex]::Escape('$codeSha = "' + $codeSha + '"') -or $tc -notmatch [regex]::Escape('$code = "' + $build + '"')) { Done 1 "REFUSED: the edited copy of $f is not as intended (new line once, anchor kept once, code and sha moved); live launchers untouched" }
  }
  function ArgvOf($f) { @([IO.File]::ReadAllLines($f) | Where-Object { $_ -match '^\s*"--' } | ForEach-Object { $_.Trim().TrimEnd(',') }) }
  $dif = @(Compare-Object (ArgvOf $copies[0]) (ArgvOf $copies[1]))
  if ($dif.Count) { foreach ($d in $dif) { Say ("ARGV DIFFERS: {0} {1}" -f $d.SideIndicator, $d.InputObject) }; Done 1 "REFUSED: the two edited launchers' pin argv differ; live launchers untouched" }
  $dOld = @(Compare-Object (ArgvOf $launchers[0]) (ArgvOf $copies[0]))
  $dOldTxt = ($dOld | ForEach-Object { $_.SideIndicator + ' ' + $_.InputObject }) -join ' ; '
  if ($dOld.Count -ne 1 -or $dOldTxt -ne ('=> "--index-5hz", "' + $Mode + '"')) { Done 1 ("REFUSED: the argv change is not exactly the one added line (live vs copy: " + $dOldTxt + "); live launchers untouched") }
  Say ("edited copies parse, their pin argv match ({0} lines) and differ from the live argv by exactly: {1}" -f (ArgvOf $copies[0]).Count, $dOldTxt)
  Copy-Item $copies[0] "$build\restart_bot.ps1" -Force    # the build's own self-test reads its launcher
  $must = @("code_sha $codeSha", "pintake\.py sha256\[:12\] $pintakeSha", "ordercli\.py sha256\[:12\] $ordercliSha",
    ('--index-5hz ' + $Mode + '(\s|$)'), '--hedge-jump-shadow 6\s', '--hedge-jump-max 8', '--jump-hedge-min-ask 0\.05',
    '--cheap-window 6 10 0\.98', '--hedge-tick round', '--boost-rail off', '--max-positions 5',
    '--hedge-odds-mult 1\.25', '--hedge-odds-min-tau 11', '--ws-later-fall-c 10', '--hedge-belief 0\.40',
    '--bank-brake 4\.5\s', '--extra-coin 0\s', '--late-extra 0\s', '--late-extra-tau 15',
    '--band99-ceiling 0\.99', '--band-mult 0\.955 0\.981 1\.5', '--late-mult 1\.5',
    '--minutes 4320', '--loss-cap-frac 0\.187')
  $bare = '(^|\s)--hedge-jump\s+[0-9]'
  function Missing($txt) { @($must | Where-Object { $txt -notmatch $_ }) }
  $chk = (Native 'powershell' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $copies[0], '-Check'))[0]
  Add-Content -Path $log -Value $chk
  $line = ($chk -split "`n" | Where-Object { $_ -match 'kals-live-0925w\\research\\pinrun\.py' -and $_ -match ('--index-5hz ' + $Mode + '(\s|$)') -and $_ -match '--hedge-jump-shadow 6\s' -and $_ -notmatch $bare } | Select-Object -First 1)
  $miss = Missing $chk
  if (-not $line -or $miss.Count -or $chk -match 'ABORTING' -or $chk -match $bare) { Done 1 ("REFUSED: -Check of the edited hand launcher did not show $build with --index-5hz $Mode and every live flag; missing: " + ($miss -join ' | ') + "; live launchers untouched") }
  Say "edited hand launcher -Check ok ($build, code_sha $codeSha, --index-5hz $Mode, every live flag)"
  # ---- 4. the full-argv self-test on the new build, before any live launcher is touched
  $argv = ($line.Trim() -split '\s+')
  $ix = [array]::IndexOf($argv, ($argv | Where-Object { $_ -like '*pinrun.py' } | Select-Object -First 1))
  $targs = @('-u', "$build\research\pinrun.py") + $argv[($ix + 1)..($argv.Length - 1)] + @('--selftest')
  if (($targs -join ' ') -notmatch ('--index-5hz ' + $Mode + '(\s|$)')) { Done 1 "REFUSED: the self-test argv does not carry --index-5hz $Mode; live launchers untouched" }
  Say ("self-test: " + ($targs -join ' '))
  New-Item -ItemType Directory -Force "$build\selftest" | Out-Null
  $p = Start-Process -FilePath $py -ArgumentList $targs -RedirectStandardOutput "$build\selftest\0925w_selftest.out" -RedirectStandardError "$build\selftest\0925w_selftest.err" -NoNewWindow -PassThru
  $null = $p.Handle
  try { $p.PriorityClass = "BelowNormal" } catch {}
  if (-not $p.WaitForExit(600000)) { try { $p.Kill() } catch {}; Done 1 "REFUSED: the self-test did not finish in 10 minutes (killed); live launchers untouched" }
  $so = [IO.File]::ReadAllText("$build\selftest\0925w_selftest.out")
  $nOkSeen = ([regex]::Matches($so, '(?m)^  ok   ')).Count
  $nfail = ([regex]::Matches($so, '(?m)^  FAIL ')).Count
  $nh = ([regex]::Matches($so, '(?m)^  ok   v-hedge5')).Count
  $ncw = ([regex]::Matches($so, '(?m)^  ok   v-cheapwin')).Count
  $nvv = ([regex]::Matches($so, '(?m)^  ok   v-0925v')).Count
  if ($p.ExitCode -ne 0 -or $so -notmatch 'SELF-TEST PASSED' -or $nfail -ne 0 -or $nOkSeen -ne $nOkPinned -or $nh -ne $nH5 -or $ncw -ne $nCheapwin -or $nvv -ne $nV) { Done 1 ("REFUSED: self-test not as pinned (exit {0}, {1} ok vs {2} pinned, {3} FAIL lines, {4} of {5} v-hedge5, {6} of {7} v-cheapwin, {8} of {9} v-0925v); see $build\selftest\0925w_selftest.out and .err; live launchers untouched" -f $p.ExitCode, $nOkSeen, $nOkPinned, $nfail, $nh, $nH5, $ncw, $nCheapwin, $nvv, $nV) }
  Say ("self-test PASSED ({0} ok = the pinned {1}, 0 FAIL; {2} v-hedge5, {3} v-cheapwin, {4} v-0925v) with the full --index-5hz $Mode argv on $build" -f $nOkSeen, $nOkPinned, $nh, $ncw, $nvv)
  # ---- 5. the live launchers: backed up (checked), replaced by the checked copies (checked), -Check
  $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  for ($i = 0; $i -lt 2; $i++) {
    $f = $launchers[$i]
    if ((Sha64 $f) -ne $orig[$f]) { Done 1 "REFUSED: $f changed while this script ran; nothing changed" }
    $bak = $f + ".before-0925w-" + $stamp
    Copy-Item $f $bak -ErrorAction Stop
    if ((Sha64 $bak) -ne $orig[$f]) { Done 1 "REFUSED: the backup $bak is not a byte copy of $f; nothing changed" }
    $baks[$f] = $bak
  }
  for ($i = 0; $i -lt 2; $i++) {
    $f = $launchers[$i]
    $script:edited = $true
    Copy-Item $copies[$i] $f -Force -ErrorAction Stop
    if ((Sha64 $f) -ne (Sha64 $copies[$i])) { if (-not (RestoreAll)) { Done 5 "a launcher restore FAILED" }; Done 1 "REFUSED: $f is not the checked copy after writing it; both restored" }
    Say "CHANGED $f (= the checked copy $($copies[$i]); backup $($baks[$f]))"
  }
  Say "LAUNCHERS EDITED: both now start $build (code_sha $codeSha) with --index-5hz $Mode (backups *.before-0925w-$stamp). If this log stops here, pin's next restart starts 0925w."
  foreach ($f in $launchers) {
    $c = (Native 'powershell' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $f, '-Check'))[0]
    Add-Content -Path $log -Value $c
    $miss = Missing $c
    if ($miss.Count -or $c -match 'ABORTING' -or $c -match $bare) { Say ("-Check of $f did not show the new argv with every flag; missing: " + ($miss -join ' | ')); if (-not (RestoreAll)) { Done 5 "a launcher restore FAILED" }; Done 1 "both launchers restored; pin untouched" }
  }
  Say "both live launchers -Check ok"
} catch {
  Say ("ERROR before the restart: " + $_.Exception.Message)
  if ($script:edited) { if (-not (RestoreAll)) { Done 5 "a launcher restore FAILED after an error" } }
  Done 1 "stopped; the live launchers are as they were (pin untouched)"
}
$ErrorActionPreference = 'Continue'

# ---- 8 (used after 6). the launcher snapshot in the repo: SHA256SUMS.txt in LF (test_ops reads it with sha256sum's format)
function Snapshot {
  try {
    $sd = 'C:\kals-repo\results\live_launcher_snapshot'
    New-Item -ItemType Directory -Force $sd | Out-Null
    $pairs = @(@($launchers[0], 'restart_bot_hand.ps1'), @($launchers[1], 'restart_bot_repo.ps1'))
    $sums = @()
    foreach ($pr in $pairs) {
      $dst = Join-Path $sd $pr[1]
      Copy-Item $pr[0] $dst -Force
      if ((Sha64 $dst) -ne (Sha64 $pr[0])) { throw ("the snapshot copy of " + $pr[0] + " is not byte-exact") }
      $sums += ("{0}  {1}" -f (Sha64 $dst), $pr[1])
    }
    [IO.File]::WriteAllText((Join-Path $sd 'SHA256SUMS.txt'), (($sums -join "`n") + "`n"), (New-Object System.Text.ASCIIEncoding))
    $rm = Join-Path $sd 'README.md'
    $note = 'README.md not found; nothing to refresh'
    if (Test-Path $rm) {
      $txt = [IO.File]::ReadAllText($rm)
      $rnl = "`n"
      if ($txt -match "`r`n") { $rnl = "`r`n" }
      $today = Get-Date -Format 'yyyy-MM-dd'
      $n1 = ([regex]::Matches($txt, '(?m)^# Live launcher snapshot -- \d{4}-\d{2}-\d{2}\r?$')).Count
      $n2 = ([regex]::Matches($txt, '(?m)^Both start code .*$')).Count
      if ($n1 -eq 1 -and $n2 -eq 1) {
        $txt = [regex]::Replace($txt, '(?m)^# Live launcher snapshot -- \d{4}-\d{2}-\d{2}(\r?)$', ('# Live launcher snapshot -- ' + $today + '$1'))
        $txt = [regex]::Replace($txt, '(?m)^Both start code .*?(\r?)$', ('Both start code `' + $build + '` (code sha `' + $codeSha + '`, pintake sha `' + $pintakeSha + '`) with the same flags; since ' + $today + ' pin reads the settlement index 5x a second as well (`--index-5hz ' + $Mode + '`, v-hedge5, build 0925w); the jump hedge stays in shadow (`--hedge-jump-shadow 6`).$1'))
        [IO.File]::WriteAllText($rm, $txt, (New-Object System.Text.UTF8Encoding($false)))
        $note = 'README.md date and build lines refreshed'
      } else { $note = ("README.md left as it was (its date line found {0} times, its 'Both start code' line {1} times); refresh them by hand" -f $n1, $n2) }
    }
    Say ("launcher snapshot written: $sd (restart_bot_hand.ps1, restart_bot_repo.ps1, SHA256SUMS.txt in LF; " + $note + "); commit those exact files with git add -- LIVE_PATHS.txt and .gitattributes are untouched")
  } catch {
    Say ("launcher snapshot FAILED (copy the two launchers by hand and rewrite SHA256SUMS.txt in LF): " + $_.Exception.Message)
  }
}
# A FRESH OUTPUT FILE FOR EVERY RESTART CALL (pin_0925v.ps1 round 5): the pin a restart starts INHERITS the cmd wrapper's
# handle to that file, so a second restart into the same file never ran while the old file was read as "rolled back". Each
# call writes a file of its own, and what it says is believed only when it carries a "restart_bot.ps1 starting" line stamped
# after the call began -- anything else is "restart_bot did not run".
function RestartByWmi($tag) {
  $t0 = Get-Date
  $base = $routPre + ($tag -replace '[^A-Za-z0-9]+', '-') + '-' + $t0.ToString('HHmmss')
  $out = $base + '.out'
  $k = 1
  while (Test-Path $out) { $k++; $out = $base + '-' + $k + '.out' }
  $cmd = 'cmd /c "powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-live-0925n\restart_bot.ps1 > ' + $out + ' 2>&1"'
  $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = 'C:\kals-live-0925n' }
  Say ("restart launched ($tag), wrapper pid {0} (return {1}); its output: $out" -f $r.ProcessId, $r.ReturnValue)
  $res = @{ wmi = ($r.ReturnValue -eq 0); ran = $false; txt = ''; file = $out }
  if (-not $res.wmi) { return $res }
  $wp = Get-Process -Id $r.ProcessId -ErrorAction SilentlyContinue
  if ($wp) { $wp.WaitForExit(240000) | Out-Null }
  if (Test-Path $out) {
    try {
      $fs = [IO.File]::Open($out, 'Open', 'Read', 'ReadWrite')
      try { $sr = New-Object IO.StreamReader($fs); $res.txt = [string]$sr.ReadToEnd() } finally { $fs.Close() }
    } catch { Say ("could not read ${out}: " + $_.Exception.Message) }
  }
  $m = [regex]::Match($res.txt, 'restart_bot\.ps1 starting (\S+)')
  if ($m.Success) {
    $st = $null
    try { $st = [DateTime]::Parse($m.Groups[1].Value) } catch { $st = $null }
    if ($st -and $st -ge $t0.AddSeconds(-2)) { $res.ran = $true }
  }
  if (-not $res.ran) { Say ("restart ($tag) did NOT run: $out holds no 'restart_bot.ps1 starting' line from this call; nothing in it is believed") }
  return $res
}
# WHEN A RESTART MAY HAPPEN (pin_0925v.ps1 round 5). Flat is not enough: restart_bot checks flat once and stops pin a few
# seconds later, and the new pin runs its startup self-test before it trades, so a restart in a close's last minutes can
# meet that close's buys or miss them. A restart (step 5 and the rollback alike) waits until pin is FLAT and the next
# quarter-hour close (ET :00 :15 :30 :45 -- every 15-minute and hourly market closes on that grid, the same seconds in UTC)
# is at least $beforeClose s away and the last one at least $afterClose s behind. Flat keeps its 25 minutes; the clock
# alone may take up to 15 more.
$beforeClose = 150
$afterClose = 20
function UtcNow { [DateTime]::UtcNow }
function QuarterPos { $u = UtcNow; return (($u.Minute % 15) * 60.0 + $u.Second + $u.Millisecond / 1000.0) }
function ClockWait {
  $q = QuarterPos
  if ($q -lt $afterClose) { return ($afterClose - $q) }
  if ((900.0 - $q) -lt $beforeClose) { return (900.0 - $q + $afterClose) }
  return 0.0
}
function WaitReady($label, $flatBy, $clockBy) {
  $saidWait = $false
  $saidClock = $false
  while ($true) {
    $fo = Native $py @('C:\kals-repo\research\pinflat.py')
    if ($fo[1] -ne 0) {
      if ((Get-Date) -gt $flatBy) { return @{ ok = $false; why = ("pin was not flat within 25 minutes (last answer: " + $fo[0].Trim() + ")") } }
      if (-not $saidWait) { Say ("{0}: pin holds a bet, waiting for flat (pinflat exit {1}): {2}" -f $label, $fo[1], $fo[0].Trim()); $saidWait = $true }
      Start-Sleep -Seconds 15
      continue
    }
    $w = ClockWait
    $q = QuarterPos
    if ($w -le 0) { Say ("{0}: pin is flat ({1}) and the clock is clear: {2:N0} s after a quarter-hour close, {3:N0} s before the next" -f $label, $fo[0].Trim(), $q, (900.0 - $q)); return @{ ok = $true } }
    if ((Get-Date).AddSeconds($w) -gt $clockBy) { return @{ ok = $false; why = ("pin is flat but no clear moment comes within the 25 + 15 minutes ({0:N0} s before a close)" -f (900.0 - $q)) } }
    if (-not $saidClock) { Say ("{0}: pin is flat but the clock is not clear ({1:N0} s after a quarter-hour close, {2:N0} s before the next; a restart needs >= {3} s after and >= {4} s before): waiting {5:N0} s, re-checking flat as it goes" -f $label, $q, (900.0 - $q), $afterClose, $beforeClose, $w); $saidClock = $true }
    Start-Sleep -Seconds ([int][Math]::Ceiling([Math]::Min(15.0, $w)))
  }
}
# A ROLLBACK COUNTS ONLY WHEN IT IS SEEN: the next pin log (created after the rollback restart began) starts code_sha
# d51b131b55cf with no index_5hz field and the jump hedge still in shadow, results\pinrun-live.pid was written after the
# restart began and its pid is alive, and the 0925w pin is gone. Polled for up to $confirmS s.
$confirmS = 300
function ConfirmOld($since, $vPid) {
  $deadline = (Get-Date).AddSeconds($confirmS)
  $pidf = 'C:\kals-repo\results\pinrun-live.pid'
  $why = 'no pin log was created after the rollback restart began'
  while ($true) {
    $f = Get-ChildItem 'C:\kals-repo\results\pinrun-live-*.jsonl' -ErrorAction SilentlyContinue | Where-Object { $_.CreationTime -ge $since } | Sort-Object CreationTime | Select-Object -First 1
    if ($f) {
      $runSeen = $null    # not named mode: PowerShell names are case-insensitive and RunMode reads the -Mode parameter
      try {
        $fs = [IO.File]::Open($f.FullName, 'Open', 'Read', 'ReadWrite')
        try { $sr = New-Object IO.StreamReader($fs); $lines = $sr.ReadToEnd() -split "`n" } finally { $fs.Close() }
        foreach ($ln in $lines) { if ($ln -match '"kind": "start"') { try { $d = $ln | ConvertFrom-Json; $runSeen = RunMode $d } catch { $runSeen = '?' }; break } }
      } catch { $runSeen = $null }
      $ppid = $null
      $pidNew = $false
      if (Test-Path $pidf) { try { $ppid = [int](([IO.File]::ReadAllText($pidf)).Trim()); $pidNew = ((Get-Item $pidf).LastWriteTime -ge $since) } catch { $ppid = $null } }
      $alive = [bool]($ppid -and (Get-Process -Id $ppid -ErrorAction SilentlyContinue))
      $vGone = (-not $vPid) -or (-not (Get-Process -Id $vPid -ErrorAction SilentlyContinue))
      if (-not $runSeen) { $why = "the next pin log $($f.Name) has no start record" }
      elseif ($runSeen -ne 'old') { $why = "the next pin log $($f.Name) does not start 0925v as before ($runSeen)" }
      elseif (-not $pidNew) { $why = "results\pinrun-live.pid was not written after the rollback restart began" }
      elseif (-not $alive) { $why = "the pin in results\pinrun-live.pid (pid $ppid) is not running" }
      elseif ($vPid -and ($ppid -eq [int]$vPid)) { $why = "results\pinrun-live.pid still names the 0925w pin (pid $ppid)" }
      elseif (-not $vGone) { $why = "the 0925w pin (pid $vPid) is still running" }
      else {
        return @{ ok = $true; what = ("the next pin log {0} starts code_sha {1} (0925v, no 5 Hz flag, jump hedge in shadow); results\pinrun-live.pid (written {2:HH:mm:ss}) names pid {3}, alive" -f $f.Name, $oldSha, (Get-Item $pidf).LastWriteTime, $ppid) }
      }
    }
    if ((Get-Date) -gt $deadline) { return @{ ok = $false; why = $why } }
    Start-Sleep -Seconds 10
  }
}
function Rollback($why, $vPid) {
  Say ("ROLLING BACK to 0925v (the launcher backups): " + $why)
  if (-not (RestoreAll)) { Done 5 "a launcher restore FAILED during the rollback; pin may be down -- a person must look" }
  $flatBy = (Get-Date).AddMinutes(25)
  $clockBy = $flatBy.AddMinutes(15)
  for ($rt = 1; $rt -le 3; $rt++) {
    $w = WaitReady "rollback try $rt" $flatBy $clockBy
    if (-not $w.ok) { Done 5 ("ROLLBACK NOT CONFIRMED: the launchers point at 0925v again, but " + $w.why + "; this script did not restart pin -- a person must look (pin's next restart starts 0925v)") }
    $since = (Get-Date).AddSeconds(-5)
    $rs = RestartByWmi "rollback try $rt"
    if (-not $rs.wmi) { Done 5 "ROLLBACK NOT CONFIRMED: WMI refused to start the rollback's restart wrapper; the launchers point at 0925v again but pin was not restarted -- a person must look" }
    if (-not $rs.ran) { Done 5 ("ROLLBACK NOT CONFIRMED: restart_bot did not run (" + $rs.file + " holds no 'restart_bot.ps1 starting' line from this call); the launchers point at 0925v again -- a person must look") }
    if ($rs.txt -match 'REFUSING: the bot is holding a position') { Say ("rollback: restart_bot refused (try {0} of 3): pin holds a bet; waiting for flat and a clear clock again" -f $rt); continue }
    $tail = @(($rs.txt -split "`r?`n") | Where-Object { $_.Trim() } | Select-Object -Last 4)
    Say ("rollback: restart_bot ran (" + $rs.file + "; last lines: " + ($tail -join ' | ') + "); confirming from the next pin log, up to $confirmS s")
    $c = ConfirmOld $since $vPid
    if ($c.ok) { Done 3 ("ROLLED BACK, CONFIRMED: pin runs 0925v again -- " + $c.what) }
    Done 5 ("ROLLBACK NOT CONFIRMED after $confirmS s: restart_bot ran, but " + $c.why + "; the launchers point at 0925v again -- a person must look")
  }
  Done 5 "ROLLBACK NOT CONFIRMED after 3 tries: restart_bot refused each time because pin held a bet; the launchers point at 0925v again (pin's next restart starts it) -- a person must look"
}
# ---- 7 (used after 6). watch the new pin
function WatchNew($newPid, $since) {
  Say "watching the new pin (pid $newPid) for 6 minutes"
  $deadline = (Get-Date).AddMinutes(6)
  $f = $null
  while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 20
    if (-not (Get-Process -Id $newPid -ErrorAction SilentlyContinue)) { break }
    $f = Get-ChildItem 'C:\kals-repo\results\pinrun-live-*.jsonl' | Where-Object { $_.CreationTime -ge $since } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  }
  $alive = [bool](Get-Process -Id $newPid -ErrorAction SilentlyContinue)
  if (-not $f) { $f = Get-ChildItem 'C:\kals-repo\results\pinrun-live-*.jsonl' | Where-Object { $_.CreationTime -ge $since } | Sort-Object LastWriteTime -Descending | Select-Object -First 1 }
  $start = $false; $startSeen = 'none'; $rows = 0; $open = @{}; $kinds = @{}; $feedsOk = $false; $feedsSeen = 'none'; $up5 = 'none'
  if ($f) {
    $fs = [IO.File]::Open($f.FullName, 'Open', 'Read', 'ReadWrite')
    try { $sr = New-Object IO.StreamReader($fs); $lines = $sr.ReadToEnd() -split "`n" } finally { $fs.Close() }
    foreach ($ln in $lines) {
      if ($ln -notmatch '"kind": "(start|feeds|universe|index5_up|index5_silent|hedge5_shadow|entries_blocked|entries_resumed|hedge_broken|clock_skew|log_write_fail|dayloss_write_fail|expiry_drain|startup_bank|unbooked|universe_empty|api_shape)"') { continue }
      try { $d = $ln | ConvertFrom-Json } catch { continue }
      $k = [string]$d.kind
      $kinds[$k] = 1 + [int]$kinds[$k]
      if ($k -eq 'start') {
        $runSeen = RunMode $d
        $startSeen = ('code_sha ' + [string]$d.code_sha + ', ' + $runSeen)
        if ($runSeen -eq 'new') { $start = $true }
      }
      if ($k -eq 'feeds') {
        $feedsSeen = ('ticks ' + [string]$d.ticks + ', feeds ' + (@($d.feeds) -join ' '))
        if ([int]$d.ticks -gt 10 -and (@($d.feeds) -contains 'BRTI')) { $feedsOk = $true }
      }
      if ($k -eq 'index5_up') { $up5 = ('UP: ' + [string]$d.fast_ticks + ' fast prints, ' + [string]$d.fast_first + ' whole-second prints first off the 5 Hz channel') }
      if ($k -eq 'index5_silent') { $up5 = ('SILENT after ' + [string]$d.after_s + ' s') }
      if ($k -eq 'universe' -and [int]$d.rows -gt 0) { $rows++ }
      if ($d.reason -and ([string]$d.blocks).StartsWith('new entries')) { $open[[string]$d.reason] = $k }
      if ($k -eq 'entries_resumed' -and $d.reason) { $open.Remove([string]$d.reason) }
    }
  }
  $seen = ($kinds.Keys | Sort-Object | ForEach-Object { "$_ x$($kinds[$_])" }) -join ', '
  Say ("watch: log {0}; start record: {1}; start ok (code_sha {2}, index_5hz {3}, jump hedge in shadow): {4}; index: {5} (ok: {6}); 5 Hz feed: {7}; universe refreshes with markets: {8}; alive: {9}; still blocked: [{10}]; records seen: {11}" -f $(if ($f) { $f.Name } else { 'none' }), $startSeen, $codeSha, $Mode, $start, $feedsSeen, $feedsOk, $up5, $rows, $alive, (($open.Keys | Sort-Object) -join ', '), $seen)
  if (-not $alive -or -not $start -or -not $feedsOk) { Rollback ("the new pin " + $(if (-not $alive) { "is not running" } elseif (-not $start) { "never wrote a start record with code_sha $codeSha, index_5hz $Mode and the jump hedge in shadow (seen: $startSeen)" } else { "started but its index feed did not come up (feeds record: $feedsSeen)" })) $newPid }
  Snapshot
  if ($rows -lt 1 -or $open.Count) { Done 4 ("0925w IS RUNNING BUT NOT HEALTHY after 6 minutes: " + $(if ($rows -lt 1) { "no universe refresh answered with markets; " } else { "" }) + $(if ($open.Count) { "new entries still blocked by: " + (($open.Keys | Sort-Object) -join ', ') + "; " } else { "" }) + "NOT reverted; revert by hand if it is wrong: copy the .before-0925w-* backups back and rerun restart_bot while flat") }
  if ($up5 -notlike 'UP*') { Done 4 ("0925w RUNS and is healthy, but the 5 Hz feed is not confirmed ($up5): pin then behaves exactly as 0925v (every 5 Hz read is skipped). NOT reverted; read index_stats in the next end record, or the conn_stats, to see why") }
  Done 0 ("DONE: pin restarted on $build (code_sha $codeSha) with --index-5hz $Mode, pid $newPid, healthy after the 6-minute watch; start record: $startSeen; 5 Hz feed $up5")
}
# ---- 6. wait for flat AND a clear clock, then the restart through the hand launcher
$flatBy = (Get-Date).AddMinutes(25)
$note2 = "; NOTE: until pin has restarted on 0925w AND results\live_launcher_snapshot is refreshed, kalshi_watch's launcher check alarms every 30 min (the live launchers now differ from the committed snapshot: that alarm is this edit, not a fault)"
$clockBy = $flatBy.AddMinutes(15)
for ($try = 1; $try -le 3; $try++) {
  $w = WaitReady "restart try $try" $flatBy $clockBy
  if (-not $w.ok) { Done 2 ("NOT RESTARTED: " + $w.why + ". The launchers ARE edited, so pin's next restart (watch_bot, or its own 72-hour end ~12:46 ET 11-11) starts 0925w" + $note2) }
  $since = (Get-Date).AddSeconds(-5)
  $rs = RestartByWmi "try $try"
  if (-not $rs.wmi) { Done 2 ("WMI refused to start the restart wrapper; nothing restarted (the launchers ARE edited)" + $note2) }
  if (-not $rs.ran) { Done 2 ("NOT RESTARTED: restart_bot did not run (" + $rs.file + " holds no 'restart_bot.ps1 starting' line from this call), so pin was not touched; the launchers ARE edited, so pin's next restart starts 0925w" + $note2) }
  $txt = $rs.txt
  if ($txt -match 'pinrun running: pid (\d+)') { WatchNew ([int]$matches[1]) $since }
  if ($txt -match 'REFUSING: the bot is holding a position') { Say "restart_bot refused: pin bought again between the flat check and the restart; waiting for flat and a clear clock again"; continue }
  if ($txt -match 'FAILED: pinrun did not come back') { Rollback "restart_bot stopped pin but the new pin did not come back" $null }
  $tail = @(($txt -split "`r?`n") | Where-Object { $_.Trim() } | Select-Object -Last 6)
  Done 2 ("restart_bot did not report a running pin; its last lines: " + ($tail -join ' | ') + "; if pin is down, watch_bot restarts it (with the 0925w argv) within minutes" + $note2)
}
Done 2 ("NOT RESTARTED after 3 tries: pin kept holding a bet at the restart moment; the launchers ARE edited (next restart starts 0925w)" + $note2)
