# pin_jumpshadow.ps1 -- 2026-11-08. Operator 11-08: "Keep working on jump hedge. It's a big problem currently"; his standing
# rule: a rule stays only if it is tested and shown to make more money.
# WHAT IT DOES: the JUMP HEDGE goes to SHADOW. Same build (C:\kals-live-0925v, pinrun code_sha d51b131b55cf, pintake
#   b3c7bb48abb5, ordercli 467782077a23 -- nothing is copied or patched), ARGV ONLY: in BOTH live launchers the one line
#       "--hedge-jump", "6",
#   becomes
#       "--hedge-jump-shadow", "6",
#   with a v-jumpshadow comment above it saying why. "--hedge-jump-max", "8", and "--jump-hedge-min-ask", "0.05", stay as
#   they are (the shadow records whether the cap and the 5c floor would have skipped each alarm). Then pin is restarted
#   when flat. With --hedge-jump-shadow set and --hedge-jump NOT set, pinrun computes the jump alarm every second exactly as
#   the jump hedge computed it and writes ONE jump_shadow record per outcome (ticker, side, the contracts it would buy, the
#   other side's ask and size, belief, jump_sd, tau, capped / cheap_skip / would_send); it SENDS NOTHING. The 0.40 belief
#   hedge and its 1.25x extra are untouched. pinrun refuses both flags together at startup.
# WHY (the 11-08 study, jh1108: events\REPORT.md, replay\RESULTS.md, decide\DECISION.md): live 10-23 21:45 ET..11-08 09:31 ET
#   (15.5 days) the jump hedge fired on 60 jump-only alarms (50 markets); 57 were false alarms whose insurance cost $327.90
#   at today's 376 contracts on bets that WON; the 3 real flips added only $32.69 over what the 0.40 belief line alone would
#   have done (it would have caught all 3 a few seconds later); net -$295.21, about -$19 a day, and -$32 a day over
#   11-01..11-08. Every premium-cutting variant (37 replayed on both samples) lost money pooled, rested on one or two
#   events, or bought the cover later and dearer on every real flip it met. Nothing in the rule is changed; it is switched
#   from spending to recording so the 12-07 read can price what it WOULD have done against the belief line at real asks.
# HOW TO RUN (on the server, after `git pull --no-rebase` -- never a rebase, stash, reset or checkout of restart_bot.ps1):
#     powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-repo\results\pin_jumpshadow.ps1
#   By default the script RE-LAUNCHES ITSELF DETACHED (WMI, like the restart) and this window only follows its log, so a
#   dropped SSH session cannot stop it half way; the follower exits with the worker's own exit code. -Foreground runs it in
#   this window instead.
# STEPS (anything wrong before step 4 changes no live launcher; the running pin is never touched before step 5):
#   1. refuse unless: C:\kals-live-0925v\research\pinrun.py is d51b131b55cf, pintake b3c7bb48abb5, ordercli 467782077a23,
#      and all nine modules the build and its self-test load are there; both launchers (C:\kals-live-0925n's, the hand
#      launcher, and C:\kals-repo's, which watch_bot.ps1 uses) point at C:\kals-live-0925v / d51b131b55cf, carry
#      "--hedge-jump", "6", exactly once each, carry NO "--hedge-jump-shadow" argv and no v-jumpshadow text, and still carry
#      "--hedge-jump-max", "8", and "--jump-hedge-min-ask", "0.05", once each; C:\kals-repo\results\VERSIONS.md carries a
#      v-jumpshadow entry. The keep-alive launcher's git status is logged.
#   2. write BOTH edited launchers as COPIES (C:\kals-live-0925v\jumpshadow\restart_bot_hand.ps1 / restart_bot_repo.ps1):
#      the one argv line replaced, the v-jumpshadow comment above it, every other byte as it was (the hand launcher mixes
#      CRLF and LF line ends and the inserted lines take the anchor line's own); parse-check both, the two argv must match,
#      -Check the hand copy: it must show --hedge-jump-shadow 6, --hedge-jump-max 8, --jump-hedge-min-ask 0.05, every
#      other live flag, and NO bare --hedge-jump <n>.
#   3. the FULL new argv (from that -Check) + --selftest on C:\kals-live-0925v at BelowNormal priority, at most 10 minutes:
#      SELF-TEST PASSED, 0 FAIL, and EXACTLY the pinned count: 1604 ok lines (the 120 v-0925v and the 6 v-cheapwin among
#      them) -- measured 11-08 on a byte copy of the live build with this exact shadow argv under plain python and under
#      python -I with tzdata refused (the server's form), and the same 1604 with today's live argv. Only now is a live
#      launcher touched.
#   4. back up both live launchers (.before-jumpshadow-<stamp>, hash-checked), write the checked copies over them
#      (hash-checked), -Check both live launchers; any failure restores both (hash-checked) and stops.
#   5. wait until research\pinflat.py says FLAT and the clock is clear -- at least 20 s after a quarter-hour close and at
#      least 150 s before the next -- at most 25 minutes for flat, up to 15 more for the clock alone; then restart pin
#      through C:\kals-live-0925n\restart_bot.ps1 by WMI, its output in a file of its own
#      (results\pin_jumpshadow_restart-<tag>-<HHmmss>.out, believed only with a "restart_bot.ps1 starting" line stamped
#      after the call began); if it refuses because pin bought again, wait for flat and the clock again (3 tries). If no
#      such moment comes, the launchers stay edited and pin's next restart (watch_bot, or its own end ~05:17 ET 11-10)
#      starts the shadow; the log says so.
#   6. WATCH the new pin for 6 minutes: its start record must carry code_sha d51b131b55cf AND hedge_jump null (the field is
#      pinrun's HEDGE_JUMP_SIGMA, None with the flag off) AND hedge_jump_shadow 6; a universe refresh must answer with
#      markets; the process must still be alive; no new-entry block may still be open at the end. If the new pin died,
#      never started, or started with the wrong flags, both launchers are put back (hash-checked) and pin is restarted
#      EXACTLY as in step 5 (flat, the clock, 3 tries, a fresh output file); the rollback counts only when CONFIRMED from
#      pin's own records -- the next pin log's start record carries code_sha d51b131b55cf with hedge_jump 6 and
#      hedge_jump_shadow null, results\pinrun-live.pid was written after the restart and its pid is alive, the shadow pin
#      is gone -- never from the pid restart_bot reports.
#   7. after a restart (healthy or not): both live launchers are copied to C:\kals-repo\results\live_launcher_snapshot\
#      with SHA256SUMS.txt in LF (`<sha256>  <name>` lines, what sha256sum -c and research\botdata\tests\test_ops.py read;
#      pin_0925v.ps1 wrote it CRLF and failed that test) and README.md's date and build lines refreshed; nothing is
#      committed by this script.
# EXIT: 0 = restarted with the jump hedge in shadow and healthy after the watch; 1 = refused, live launchers unchanged
#   (verified); 2 = launchers edited but not restarted (the next restart starts the shadow); 3 = the new pin died, never
#   started or started with the wrong flags: the launchers were put back and pin restarted with --hedge-jump 6, CONFIRMED
#   from its start record and pid file; 4 = the shadow pin is running but was not healthy at the end of the watch (blocked /
#   no markets): NOT reverted, the reasons are in the log; 5 = a person must look: a launcher could not be restored to its
#   exact pre-edit bytes, or the rollback's restart could not be CONFIRMED (it did not run, pin never went flat, or no
#   matching start record with a live pid followed) -- the log says which; 6 = (follower only) the worker did not finish
#   within 120 minutes; it may still be running, read the log.
# REVERT: copy the two .before-jumpshadow-* backups over the launchers and rerun restart_bot while flat (same build; the jump
#   hedge is back at 6 sd). Or by hand: the line pair back to "--hedge-jump", "6", in both launchers.
# Log: results\pin_jumpshadow.out; the worker's console: results\pin_jumpshadow_worker.out; each restart's own output, one
#   file per call: results\pin_jumpshadow_restart-<tag>-<HHmmss>.out
param([switch]$Child, [switch]$Foreground, [string]$RunId = '')
$log = 'C:\kals-repo\results\pin_jumpshadow.out'
$routPre = 'C:\kals-repo\results\pin_jumpshadow_restart-'   # + <tag>-<HHmmss>.out, one file per restart call
$wout = 'C:\kals-repo\results\pin_jumpshadow_worker.out'
# Say writes to the console handle, NOT the output stream: a function's output stream is its return value, and a Say
# inside RestoreAll / RestartByWmi would otherwise turn their $true / $false / text into an array
function Say($m) { $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m; [Console]::Out.WriteLine($l); Add-Content -Path $log -Value $l }

# ---- 0. the follower: start the worker detached, follow its log, exit with its code
if (-not $Child -and -not $Foreground) {
  $rid = (Get-Date -Format 'yyyyMMddHHmmss') + '-' + $PID
  $me = $MyInvocation.MyCommand.Path
  $cmd = 'cmd /c "powershell -NoProfile -ExecutionPolicy Bypass -File ' + $me + ' -Child -RunId ' + $rid + ' > ' + $wout + ' 2>&1"'
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
$build = 'C:\kals-live-0925v'
$codeSha = 'd51b131b55cf'
$pintakeSha = 'b3c7bb48abb5'
$ordercliSha = '467782077a23'
$nOkPinned = 1604    # the pinned self-test count with the shadow argv (see step 3 above). PowerShell names are
                     # case-insensitive, so the count read from the run is $nOkSeen, never $nok (which would BE this)
$nV = 120
$nCheapwin = 6
$shadowSd = '6'
$modules = @('pinrun.py', 'pintake.py', 'ordercli.py', 'kauth.py', 'livebook.py', 'engine.py', 'pinxfer.py', 'downtime.py', 'pinflat.py')
$launchers = @('C:\kals-live-0925n\restart_bot.ps1', 'C:\kals-repo\restart_bot.ps1')
$copies = @("$build\jumpshadow\restart_bot_hand.ps1", "$build\jumpshadow\restart_bot_repo.ps1")
$anchor = '    "--hedge-jump", "6",'
$shadowLine = '    "--hedge-jump-shadow", "' + $shadowSd + '",'
function Sha12($p) { try { (Get-FileHash -Algorithm SHA256 -Path $p -ErrorAction Stop).Hash.ToLower().Substring(0, 12) } catch { $null } }
function Sha64($p) { try { (Get-FileHash -Algorithm SHA256 -Path $p -ErrorAction Stop).Hash.ToLower() } catch { $null } }
# a native command's stderr must never become a terminating error (PowerShell 5.1 + Stop)
function Native($exe, [string[]]$argv) { $ErrorActionPreference = 'Continue'; $o = & $exe @argv 2>&1 | Out-String; return @($o, $LASTEXITCODE) }
# the start record's two jump fields, read the way pinrun writes them: hedge_jump = HEDGE_JUMP_SIGMA (null with --hedge-jump
# off), hedge_jump_shadow = HEDGE_JUMP_SHADOW (null with --hedge-jump-shadow off). Returns 'shadow', 'jump', or what it saw.
function JumpMode($d) {
  $hj = $null; $hs = $null
  try { $hj = $d.hedge_jump } catch { $hj = $null }
  try { $hs = $d.hedge_jump_shadow } catch { $hs = $null }
  if ($null -eq $hj -and $null -ne $hs -and ([double]$hs -eq [double]$shadowSd)) { return 'shadow' }
  if ($null -ne $hj -and ([double]$hj -eq 6.0) -and $null -eq $hs) { return 'jump' }
  return ('hedge_jump=' + $(if ($null -eq $hj) { 'null' } else { [string]$hj }) + ' hedge_jump_shadow=' + $(if ($null -eq $hs) { 'null' } else { [string]$hs }))
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
Say "start (run $RunId)"
$ErrorActionPreference = 'Stop'
try {
  # ---- 1. preconditions: the build is the live one, both launchers are exactly as the 0925v deploy left them, the entry is in
  if ((Sha12 "$build\research\pinrun.py") -ne $codeSha) { Done 1 "REFUSED: $build\research\pinrun.py is not $codeSha (missing, or not the live build); nothing changed" }
  if ((Sha12 "$build\research\pintake.py") -ne $pintakeSha) { Done 1 "REFUSED: $build\research\pintake.py is not $pintakeSha; nothing changed" }
  if ((Sha12 "$build\research\ordercli.py") -ne $ordercliSha) { Done 1 "REFUSED: $build\research\ordercli.py is not $ordercliSha; nothing changed" }
  foreach ($m in $modules) { if (-not (Test-Path "$build\research\$m")) { Done 1 "REFUSED: $build\research\$m is missing (the build and its self-test load it); nothing changed" } }
  $vrepo = [IO.File]::ReadAllText('C:\kals-repo\results\VERSIONS.md')
  if ($vrepo -notmatch 'v-jumpshadow') { Done 1 "REFUSED: C:\kals-repo\results\VERSIONS.md has no v-jumpshadow entry (pull the commit first); nothing changed" }
  try { $gs = Native 'git' @('-C', 'C:\kals-repo', 'status', '--porcelain', '--', 'restart_bot.ps1') } catch { $gs = @(('git not available: ' + $_.Exception.Message), -1) }
  Say ("git status of the keep-alive launcher (expected ' M restart_bot.ps1': its live edits are uncommitted): [" + $gs[0].Trim() + "]")
  $texts = @{}
  foreach ($f in $launchers) {
    $t = [IO.File]::ReadAllText($f)
    # the argv form of the shadow flag (a quoted token); the v-0925v comment block mentions the flag by name, which is fine
    if ($t -match [regex]::Escape('"--hedge-jump-shadow"')) { Done 1 "REFUSED: $f already carries `"--hedge-jump-shadow`" in its argv (the shadow is already deployed, or half deployed -- look); nothing changed" }
    if ($t -match 'v-jumpshadow') { Done 1 "REFUSED: $f already mentions v-jumpshadow; nothing changed" }
    foreach ($pair in @(
        @('$code = "C:\kals-live-0925v"', 'does not point at C:\kals-live-0925v'),
        @(('$codeSha = "' + $codeSha + '"'), "does not pin pinrun $codeSha"),
        @(('$pintakeSha = "' + $pintakeSha + '"'), "does not pin pintake $pintakeSha"),
        @('"--hedge-jump-max", "8",', 'does not carry "--hedge-jump-max", "8", exactly once (it shares the v-wsfall10 + v-jumpcap8 line)'),
        @('"--jump-hedge-min-ask", "0.05",', 'does not carry "--jump-hedge-min-ask", "0.05", exactly once (it shares the v-0925t line)'))) {
      $n = ([regex]::Matches($t, [regex]::Escape($pair[0]))).Count
      if ($n -ne 1) { Done 1 ("REFUSED: {0} {1} (found {2}); nothing changed" -f $f, $pair[1], $n) }
    }
    $n = ([regex]::Matches($t, [regex]::Escape($anchor))).Count
    if ($n -ne 1) { Done 1 ("REFUSED: {0}: the anchor line {1} must appear exactly once, found {2}; nothing changed" -f $f, $anchor.Trim(), $n) }
    # the anchor must be an argv line of its own (nothing else on it)
    if ($t -notmatch ('(?m)^' + [regex]::Escape($anchor) + '\s*$')) { Done 1 "REFUSED: ${f}: the anchor line carries more than the flag pair; nothing changed" }
    $texts[$f] = $t
    $orig[$f] = Sha64 $f
  }
  Say "preconditions ok: $build is $codeSha / $pintakeSha / $ordercliSha with all nine modules; both launchers point at it, carry --hedge-jump 6 once and no shadow argv; VERSIONS.md has the v-jumpshadow entry"
  # ---- 2. the edited launchers, as COPIES first
  $why = @(
    '    # v-jumpshadow 2026-11-08 (operator 11-08: "Keep working on jump hedge. It''s a big problem currently"; his rule: a rule stays only if it is tested and shown to make more money): the JUMP HEDGE goes to SHADOW -- same build, this one line changed. Live 10-23..11-08 (15.5 days) it fired on 60 jump-only alarms: 57 false alarms paid $327.90 of insurance at today''s 376 contracts on bets that won, the 3 real flips added only $32.69 over what the 0.40 belief line alone would have done; net -$295.21 (about -$19/day; -$32/day over 11-01..11-08). 37 premium-cutting variants replayed on both samples: every one lost money pooled, rested on 1-2 events, or bought the cover later and dearer on real flips (jh1108 REPORT / RESULTS / DECISION).',
    '    #   --hedge-jump-shadow 6: the alarm is computed every second exactly as the jump hedge computed it and ONE jump_shadow record per outcome says what it would have bought (side, contracts, ask and size, belief, sd, tau, capped / cheap_skip / would_send); NOTHING is sent, no try is spent. --hedge-jump-max 8 and --jump-hedge-min-ask 0.05 below stay (the shadow records whether the cap and the 5c floor would have skipped each alarm). The 0.40 belief hedge, its 1.25x extra and every other flag are untouched; pinrun refuses --hedge-jump together with this flag. Reads (results\READS_DUE.json): 11-15 sanity (records being written, 0 orders sent by the shadow); 12-07 jumphedge-shadow-read: RE-ENABLE "--hedge-jump", "6", only if the shadow''s would-have-been net vs the belief line is >= +$5/day over >= 30 days with both halves positive.',
    '    #   Revert: this line pair back to "--hedge-jump", "6", (backups *.before-jumpshadow-*), rerun restart_bot while flat (same build, nothing else moves).'
  )
  for ($i = 0; $i -lt 2; $i++) {
    $f = $launchers[$i]
    $t = $texts[$f]
    $bytes = [IO.File]::ReadAllBytes($f)
    $bom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
    # the inserted lines take the anchor line's OWN line end (the hand launcher mixes CRLF and LF; every other byte stays)
    $ai = $t.IndexOf($anchor)
    $nl = "`n"
    if ($t.Substring($ai + $anchor.Length, [Math]::Min(2, $t.Length - $ai - $anchor.Length)).StartsWith("`r`n")) { $nl = "`r`n" }
    $t = $t.Replace($anchor, (($why -join $nl) + $nl + $shadowLine))
    New-Item -ItemType Directory -Force (Split-Path $copies[$i] -Parent) | Out-Null
    [IO.File]::WriteAllText($copies[$i], $t, (New-Object System.Text.UTF8Encoding($bom)))
    $errs = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($copies[$i], [ref]$null, [ref]$errs)
    if ($errs.Count) { Done 1 ("REFUSED: the edited copy of {0} has {1} parse errors ({2}); live launchers untouched" -f $f, $errs.Count, $copies[$i]) }
    $tc = [IO.File]::ReadAllText($copies[$i])
    if (([regex]::Matches($tc, [regex]::Escape($shadowLine))).Count -ne 1 -or $tc -match [regex]::Escape($anchor)) { Done 1 "REFUSED: the edited copy of $f does not carry the shadow line exactly once with the old line gone; live launchers untouched" }
  }
  function ArgvOf($f) { @([IO.File]::ReadAllLines($f) | Where-Object { $_ -match '^\s*"--' } | ForEach-Object { $_.Trim().TrimEnd(',') }) }
  $dif = @(Compare-Object (ArgvOf $copies[0]) (ArgvOf $copies[1]))
  if ($dif.Count) { foreach ($d in $dif) { Say ("ARGV DIFFERS: {0} {1}" -f $d.SideIndicator, $d.InputObject) }; Done 1 "REFUSED: the two edited launchers' pin argv differ; live launchers untouched" }
  $dOld = @(Compare-Object (ArgvOf $launchers[0]) (ArgvOf $copies[0]))
  $dOldTxt = ($dOld | ForEach-Object { $_.SideIndicator + ' ' + $_.InputObject }) -join ' ; '
  if ($dOld.Count -ne 2 -or $dOldTxt -notmatch [regex]::Escape('<= "--hedge-jump", "6"') -or $dOldTxt -notmatch [regex]::Escape('=> "--hedge-jump-shadow", "' + $shadowSd + '"')) { Done 1 ("REFUSED: the argv change is not exactly the one line pair (live vs copy: " + $dOldTxt + "); live launchers untouched") }
  Say ("edited copies parse, their pin argv match ({0} lines) and differ from the live argv by exactly: {1}" -f (ArgvOf $copies[0]).Count, $dOldTxt)
  $must = @("code_sha $codeSha", "pintake\.py sha256\[:12\] $pintakeSha", "ordercli\.py sha256\[:12\] $ordercliSha",
    ('--hedge-jump-shadow ' + $shadowSd + '\s'), '--hedge-jump-max 8', '--jump-hedge-min-ask 0\.05',
    '--cheap-window 6 10 0\.98', '--hedge-tick round', '--boost-rail off', '--max-positions 5',
    '--hedge-odds-mult 1\.25', '--hedge-odds-min-tau 11', '--ws-later-fall-c 10', '--hedge-belief 0\.40',
    '--bank-brake 4\.5\s', '--extra-coin 0\s', '--late-extra 0\s', '--late-extra-tau 15',
    '--band99-ceiling 0\.99', '--band-mult 0\.955 0\.981 1\.5', '--late-mult 1\.5',
    '--minutes 4320', '--loss-cap-frac 0\.187')
  $bare = '(^|\s)--hedge-jump\s+[0-9]'   # the jump hedge switched ON: must not appear anywhere in a -Check
  function Missing($txt) { @($must | Where-Object { $txt -notmatch $_ }) }
  $chk = (Native 'powershell' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $copies[0], '-Check'))[0]
  Add-Content -Path $log -Value $chk
  $line = ($chk -split "`n" | Where-Object { $_ -match 'kals-live-0925v\\research\\pinrun\.py' -and $_ -match ('--hedge-jump-shadow ' + $shadowSd + '\s') -and $_ -match '--hedge-jump-max 8' -and $_ -match '--jump-hedge-min-ask 0\.05' -and $_ -notmatch $bare } | Select-Object -First 1)
  $miss = Missing $chk
  if (-not $line -or $miss.Count -or $chk -match 'ABORTING' -or $chk -match $bare) { Done 1 ("REFUSED: -Check of the edited hand launcher did not show the live build with --hedge-jump-shadow $shadowSd, --hedge-jump-max 8, --jump-hedge-min-ask 0.05, every other flag and no bare --hedge-jump; missing: " + ($miss -join ' | ') + $(if ($chk -match $bare) { '; a bare --hedge-jump <n> is still there' } else { '' }) + "; live launchers untouched") }
  Say "edited hand launcher -Check ok (shadow on, jump hedge off, cap 8 and min ask 0.05 kept)"
  # ---- 3. the full-argv self-test on the live build, before any live launcher is touched
  $argv = ($line.Trim() -split '\s+')
  $ix = [array]::IndexOf($argv, ($argv | Where-Object { $_ -like '*pinrun.py' } | Select-Object -First 1))
  $targs = @('-u', "$build\research\pinrun.py") + $argv[($ix + 1)..($argv.Length - 1)] + @('--selftest')
  if (($targs -join ' ') -match $bare -or ($targs -join ' ') -notmatch ('--hedge-jump-shadow ' + $shadowSd + '\s')) { Done 1 "REFUSED: the self-test argv is not the shadow argv; live launchers untouched" }
  Say ("self-test: " + ($targs -join ' '))
  New-Item -ItemType Directory -Force "$build\selftest" | Out-Null
  $p = Start-Process -FilePath $py -ArgumentList $targs -RedirectStandardOutput "$build\selftest\jumpshadow_selftest.out" -RedirectStandardError "$build\selftest\jumpshadow_selftest.err" -NoNewWindow -PassThru
  $null = $p.Handle   # PowerShell 5: without this ExitCode is empty after WaitForExit
  try { $p.PriorityClass = "BelowNormal" } catch {}
  if (-not $p.WaitForExit(600000)) { try { $p.Kill() } catch {}; Done 1 "REFUSED: the self-test did not finish in 10 minutes (killed); live launchers untouched" }
  $so = [IO.File]::ReadAllText("$build\selftest\jumpshadow_selftest.out")
  $nOkSeen = ([regex]::Matches($so, '(?m)^  ok   ')).Count
  $nfail = ([regex]::Matches($so, '(?m)^  FAIL ')).Count
  $ncw = ([regex]::Matches($so, '(?m)^  ok   v-cheapwin')).Count
  $nvv = ([regex]::Matches($so, '(?m)^  ok   v-0925v')).Count
  if ($p.ExitCode -ne 0 -or $so -notmatch 'SELF-TEST PASSED' -or $nfail -ne 0 -or $nOkSeen -ne $nOkPinned -or $ncw -ne $nCheapwin -or $nvv -ne $nV) { Done 1 ("REFUSED: self-test not as pinned (exit {0}, {1} ok vs {2} pinned, {3} FAIL lines, {4} of {5} v-cheapwin ok, {6} of {7} v-0925v ok); see $build\selftest\jumpshadow_selftest.out and .err; live launchers untouched" -f $p.ExitCode, $nOkSeen, $nOkPinned, $nfail, $ncw, $nCheapwin, $nvv, $nV) }
  Say ("self-test PASSED ({0} ok = the pinned {1}, 0 FAIL, the {2} v-cheapwin and {3} v-0925v checks ok) with the full shadow argv on $build" -f $nOkSeen, $nOkPinned, $ncw, $nvv)
  # ---- 4. the live launchers: backed up (checked), replaced by the checked copies (checked), -Check
  $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  for ($i = 0; $i -lt 2; $i++) {
    $f = $launchers[$i]
    if ((Sha64 $f) -ne $orig[$f]) { if ($script:edited) { if (-not (RestoreAll)) { Done 5 "a launcher restore FAILED" } }; Done 1 "REFUSED: $f changed while this script ran; nothing (more) changed" }
    $bak = $f + ".before-jumpshadow-" + $stamp
    Copy-Item $f $bak -ErrorAction Stop
    if ((Sha64 $bak) -ne $orig[$f]) { if ($script:edited) { if (-not (RestoreAll)) { Done 5 "a launcher restore FAILED" } }; Done 1 "REFUSED: the backup $bak is not a byte copy of $f" }
    $baks[$f] = $bak
  }
  for ($i = 0; $i -lt 2; $i++) {
    $f = $launchers[$i]
    $script:edited = $true
    Copy-Item $copies[$i] $f -Force -ErrorAction Stop
    if ((Sha64 $f) -ne (Sha64 $copies[$i])) { if (-not (RestoreAll)) { Done 5 "a launcher restore FAILED" }; Done 1 "REFUSED: $f is not the checked copy after writing it; both restored" }
    Say "CHANGED $f (= the checked copy $($copies[$i]); backup $($baks[$f]))"
  }
  Say "LAUNCHERS EDITED: both now pass --hedge-jump-shadow $shadowSd instead of --hedge-jump 6 (backups *.before-jumpshadow-$stamp). If this log stops here, pin's next restart starts the shadow."
  foreach ($f in $launchers) {
    $c = (Native 'powershell' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $f, '-Check'))[0]
    Add-Content -Path $log -Value $c
    $miss = Missing $c
    if ($miss.Count -or $c -match 'ABORTING' -or $c -match $bare) { Say ("-Check of $f did not show the shadow argv with every flag; missing: " + ($miss -join ' | ') + $(if ($c -match $bare) { '; a bare --hedge-jump <n> is there' } else { '' })); if (-not (RestoreAll)) { Done 5 "a launcher restore FAILED" }; Done 1 "both launchers restored; pin untouched" }
  }
  Say "both live launchers -Check ok"
} catch {
  Say ("ERROR before the restart: " + $_.Exception.Message)
  if ($script:edited) { if (-not (RestoreAll)) { Done 5 "a launcher restore FAILED after an error" } }
  Done 1 "stopped; the live launchers are as they were (pin untouched)"
}
$ErrorActionPreference = 'Continue'

# ---- 7 (used after 5). the launcher snapshot in the repo: SHA256SUMS.txt in LF (test_ops reads it with sha256sum's format)
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
        $txt = [regex]::Replace($txt, '(?m)^Both start code .*?(\r?)$', ('Both start code `' + $build + '` (code sha `' + $codeSha + '`, pintake sha `' + $pintakeSha + '`) with the same flags; since ' + $today + ' the jump hedge runs as a SHADOW (`--hedge-jump-shadow ' + $shadowSd + '`, v-jumpshadow: it records what it would have bought and sends nothing).$1'))
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
# A ROLLBACK COUNTS ONLY WHEN IT IS SEEN. restart_bot's "pinrun running: pid N" says a python process was there 15 s after it
# started one, not what it runs. The rollback is confirmed from pin's own records: the next pin log (created after this
# restart began) carries a start record with code_sha d51b131b55cf AND hedge_jump 6 AND hedge_jump_shadow null (the jump
# hedge is back on), results\pinrun-live.pid was written after the restart began and the pid in it is alive, and the shadow
# pin is gone. Polled for up to $confirmS s (the new pin writes its start record after its startup self-test).
$confirmS = 300
function ConfirmOld($since, $vPid) {
  $deadline = (Get-Date).AddSeconds($confirmS)
  $pidf = 'C:\kals-repo\results\pinrun-live.pid'
  $why = 'no pin log was created after the rollback restart began'
  while ($true) {
    $f = Get-ChildItem 'C:\kals-repo\results\pinrun-live-*.jsonl' -ErrorAction SilentlyContinue | Where-Object { $_.CreationTime -ge $since } | Sort-Object CreationTime | Select-Object -First 1
    if ($f) {
      $sha = $null; $mode = $null
      try {
        $fs = [IO.File]::Open($f.FullName, 'Open', 'Read', 'ReadWrite')
        try { $sr = New-Object IO.StreamReader($fs); $lines = $sr.ReadToEnd() -split "`n" } finally { $fs.Close() }
        foreach ($ln in $lines) { if ($ln -match '"kind": "start"') { try { $d = $ln | ConvertFrom-Json; $sha = [string]$d.code_sha; $mode = JumpMode $d } catch { $sha = '?'; $mode = '?' }; break } }
      } catch { $sha = $null }
      $ppid = $null
      $pidNew = $false
      if (Test-Path $pidf) { try { $ppid = [int](([IO.File]::ReadAllText($pidf)).Trim()); $pidNew = ((Get-Item $pidf).LastWriteTime -ge $since) } catch { $ppid = $null } }
      $alive = [bool]($ppid -and (Get-Process -Id $ppid -ErrorAction SilentlyContinue))
      $vGone = (-not $vPid) -or (-not (Get-Process -Id $vPid -ErrorAction SilentlyContinue))
      if (-not $sha) { $why = "the next pin log $($f.Name) has no start record" }
      elseif ($sha -ne $codeSha) { $why = "the next pin log $($f.Name) starts code_sha $sha, not $codeSha" }
      elseif ($mode -ne 'jump') { $why = "the next pin log $($f.Name) starts $codeSha but not with the jump hedge back on ($mode)" }
      elseif (-not $pidNew) { $why = "results\pinrun-live.pid was not written after the rollback restart began" }
      elseif (-not $alive) { $why = "the pin in results\pinrun-live.pid (pid $ppid) is not running" }
      elseif ($vPid -and ($ppid -eq [int]$vPid)) { $why = "results\pinrun-live.pid still names the shadow pin (pid $ppid)" }
      elseif (-not $vGone) { $why = "the shadow pin (pid $vPid) is still running" }
      else {
        $gone = ''
        if ($vPid) { $gone = ", and the shadow pin (pid $vPid) is gone" }
        return @{ ok = $true; what = ("the next pin log {0} starts code_sha {1} with hedge_jump 6 and hedge_jump_shadow null; results\pinrun-live.pid (written {2:HH:mm:ss}) names pid {3}, alive{4}" -f $f.Name, $sha, (Get-Item $pidf).LastWriteTime, $ppid, $gone) }
      }
    }
    if ((Get-Date) -gt $deadline) { return @{ ok = $false; why = $why } }
    Start-Sleep -Seconds 10
  }
}
function Rollback($why, $vPid) {
  Say ("ROLLING BACK to --hedge-jump 6 (the launcher backups): " + $why)
  if (-not (RestoreAll)) { Done 5 "a launcher restore FAILED during the rollback; pin may be down -- a person must look" }
  # restarted EXACTLY as step 5 restarts (flat and a clear clock, its own 25 + 15 minutes, 3 tries when restart_bot refuses
  # because pin holds a bet, a fresh output file) and CONFIRMED from pin's own records (ConfirmOld), never from the pid
  # restart_bot reports: whatever cannot be confirmed is exit 5, never "rolled back"
  $flatBy = (Get-Date).AddMinutes(25)
  $clockBy = $flatBy.AddMinutes(15)
  for ($rt = 1; $rt -le 3; $rt++) {
    $w = WaitReady "rollback try $rt" $flatBy $clockBy
    if (-not $w.ok) { Done 5 ("ROLLBACK NOT CONFIRMED: the launchers carry --hedge-jump 6 again, but " + $w.why + "; this script did not restart pin, which may still run the shadow -- a person must look (pin's next restart brings the jump hedge back)") }
    $since = (Get-Date).AddSeconds(-5)
    $rs = RestartByWmi "rollback try $rt"
    if (-not $rs.wmi) { Done 5 "ROLLBACK NOT CONFIRMED: WMI refused to start the rollback's restart wrapper; the launchers carry --hedge-jump 6 again but pin was not restarted -- a person must look" }
    if (-not $rs.ran) { Done 5 ("ROLLBACK NOT CONFIRMED: restart_bot did not run (" + $rs.file + " holds no 'restart_bot.ps1 starting' line from this call); the launchers carry --hedge-jump 6 again but pin was not restarted and may still run the shadow -- a person must look") }
    if ($rs.txt -match 'REFUSING: the bot is holding a position') { Say ("rollback: restart_bot refused (try {0} of 3): pin holds a bet; waiting for flat and a clear clock again" -f $rt); continue }
    $tail = @(($rs.txt -split "`r?`n") | Where-Object { $_.Trim() } | Select-Object -Last 4)
    Say ("rollback: restart_bot ran (" + $rs.file + "; last lines: " + ($tail -join ' | ') + "); confirming from the next pin log, up to $confirmS s")
    $c = ConfirmOld $since $vPid
    if ($c.ok) { Done 3 ("ROLLED BACK, CONFIRMED: pin runs the jump hedge (--hedge-jump 6) again on $build -- " + $c.what) }
    Done 5 ("ROLLBACK NOT CONFIRMED after $confirmS s: restart_bot ran, but " + $c.why + "; the launchers carry --hedge-jump 6 again -- a person must look")
  }
  Done 5 "ROLLBACK NOT CONFIRMED after 3 tries: restart_bot refused each time because pin held a bet; the launchers carry --hedge-jump 6 again (pin's next restart brings the jump hedge back) -- a person must look"
}
# ---- 6 (used after 5). watch the new pin
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
  $start = $false; $startSeen = 'none'; $rows = 0; $open = @{}; $kinds = @{}
  if ($f) {
    $fs = [IO.File]::Open($f.FullName, 'Open', 'Read', 'ReadWrite')
    try { $sr = New-Object IO.StreamReader($fs); $lines = $sr.ReadToEnd() -split "`n" } finally { $fs.Close() }
    foreach ($ln in $lines) {
      if ($ln -notmatch '"kind": "(start|universe|jump_shadow|entries_blocked|entries_resumed|hedge_broken|clock_skew|log_write_fail|dayloss_write_fail|expiry_drain|startup_bank|unbooked|universe_empty|api_shape)"') { continue }
      try { $d = $ln | ConvertFrom-Json } catch { continue }
      $k = [string]$d.kind
      $kinds[$k] = 1 + [int]$kinds[$k]
      if ($k -eq 'start') {
        $mode = JumpMode $d
        $startSeen = ('code_sha ' + [string]$d.code_sha + ', ' + $mode)
        if ([string]$d.code_sha -eq $codeSha -and $mode -eq 'shadow') { $start = $true }
      }
      if ($k -eq 'universe' -and [int]$d.rows -gt 0) { $rows++ }
      if ($d.reason -and ([string]$d.blocks).StartsWith('new entries')) { $open[[string]$d.reason] = $k }
      if ($k -eq 'entries_resumed' -and $d.reason) { $open.Remove([string]$d.reason) }
    }
  }
  $seen = ($kinds.Keys | Sort-Object | ForEach-Object { "$_ x$($kinds[$_])" }) -join ', '
  Say ("watch: log {0}; start record seen: {1}; start ok (code_sha {2}, hedge_jump null, hedge_jump_shadow {3}): {4}; universe refreshes with markets: {5}; alive: {6}; still blocked: [{7}]; records seen: {8}" -f $(if ($f) { $f.Name } else { 'none' }), $startSeen, $codeSha, $shadowSd, $start, $rows, $alive, (($open.Keys | Sort-Object) -join ', '), $seen)
  if (-not $alive -or -not $start) { Rollback ("the new pin " + $(if (-not $alive) { "is not running" } else { "never wrote a start record with code_sha $codeSha, hedge_jump null and hedge_jump_shadow $shadowSd (seen: $startSeen)" })) $newPid }
  Snapshot
  if ($rows -lt 1 -or $open.Count) { Done 4 ("THE SHADOW PIN IS RUNNING BUT NOT HEALTHY after 6 minutes: " + $(if ($rows -lt 1) { "no universe refresh answered with markets; " } else { "" }) + $(if ($open.Count) { "new entries still blocked by: " + (($open.Keys | Sort-Object) -join ', ') + " -- it hedges and books as normal but buys nothing while that lasts; " } else { "" }) + "NOT reverted (a block may be right); revert by hand if it is wrong: copy the .before-jumpshadow-* backups back and rerun restart_bot while flat") }
  Done 0 ("DONE: pin restarted on $build (code_sha $codeSha) with the jump hedge in SHADOW (--hedge-jump-shadow $shadowSd; --hedge-jump off; --hedge-jump-max 8 and --jump-hedge-min-ask 0.05 kept for the record), pid $newPid, healthy after the 6-minute watch; start record: $startSeen")
}
# ---- 5. wait for flat AND a clear clock, then the restart through the hand launcher (restart_bot refuses while pin holds a
# bet); one 25-minute flat budget for all three tries, up to 15 more for the clock alone
$flatBy = (Get-Date).AddMinutes(25)
$note2 = "; NOTE: until pin has restarted on the shadow argv AND results\live_launcher_snapshot is refreshed, kalshi_watch's launcher check alarms every 30 min (the live launchers now differ from the committed snapshot: that alarm is this edit, not a fault)"
$clockBy = $flatBy.AddMinutes(15)
for ($try = 1; $try -le 3; $try++) {
  $w = WaitReady "restart try $try" $flatBy $clockBy
  if (-not $w.ok) { Done 2 ("NOT RESTARTED: " + $w.why + ". The launchers ARE edited, so pin's next restart (watch_bot, or its own end ~05:17 ET 11-10) starts the shadow; /approve pinrestart restarts it sooner" + $note2) }
  $since = (Get-Date).AddSeconds(-5)
  $rs = RestartByWmi "try $try"
  if (-not $rs.wmi) { Done 2 ("WMI refused to start the restart wrapper; nothing restarted (the launchers ARE edited)" + $note2) }
  if (-not $rs.ran) { Done 2 ("NOT RESTARTED: restart_bot did not run (" + $rs.file + " holds no 'restart_bot.ps1 starting' line from this call), so pin was not touched; the launchers ARE edited, so pin's next restart starts the shadow" + $note2) }
  $txt = $rs.txt
  if ($txt -match 'pinrun running: pid (\d+)') { WatchNew ([int]$matches[1]) $since }
  if ($txt -match 'REFUSING: the bot is holding a position') { Say "restart_bot refused: pin bought again between the flat check and the restart; waiting for flat and a clear clock again"; continue }
  if ($txt -match 'FAILED: pinrun did not come back') { Rollback "restart_bot stopped pin but the new pin did not come back" $null }
  $tail = @(($txt -split "`r?`n") | Where-Object { $_.Trim() } | Select-Object -Last 6)
  Done 2 ("restart_bot did not report a running pin; its last lines: " + ($tail -join ' | ') + "; if pin is down, watch_bot restarts it (with the shadow argv) within minutes" + $note2)
}
Done 2 ("NOT RESTARTED after 3 tries: pin kept holding a bet at the restart moment; the launchers ARE edited (next restart starts the shadow)" + $note2)
