# pin_0925v.ps1 -- 2026-11-07, rounds 3, 4 and 5 11-08. Operator: "Anything that could cause the 1k+ loss needs to be addressed
# immediately. I'm
# serious. And the answer isn't betting less" -- and "Everything else that's possible to fix needs addressing as well as
# possible".
# Puts pin on a NEW build, C:\kals-live-0925v = C:\kals-live-0925t (pinrun code_sha 9e04c0252ac9, pintake b3c7bb48abb5,
# ordercli 467782077a23) + results\patch_0925u.py (pinrun e0ba3543e7be, the cheap-window trial, never deployed on its
# own) + results\patch_0925v.py (pinrun d51b131b55cf; pintake and ordercli unchanged). STRAIGHT FROM LIVE 0925t: this script
# replaces pin_0925u.ps1 (do not run both; if 0925u was installed it refuses).
#   0925u's one flag is switched on, as pin_0925u.ps1 would have: --cheap-window 6 10 0.98 (v-cheapwin, with its shadow).
#   0925v's fail-safe fixes are always on: when the bot cannot see, book, hedge or account for what it holds it BLOCKS NEW
#   ENTRIES (never a hedge, a cancel or an exit) and writes a record of a new kind. Round 3 (11-08) adds, always on: the
#   day cap / run abort see a market's NET, never one leg (D2); a jump give-up no longer marks a position hedged (D4);
#   hedge sends no longer spend the close's entry budget (D5); --max-positions counts unhedged contracts (D6); the paused
#   loop re-checks hedges every 0.05 s (P7). One new flag, --hedge-jump-shadow, ships OFF and is NOT passed here.
#   Round 4 (11-08, the reviews of round 3), always on: every leg of a market books from one read in one pass (the 15 s
#   split was reconcile's own GET throttle), and while pintake's per-leg loss rail would refuse every buy the bot blocks
#   new entries instead of halting on 2 refusals (leg_dip); the close's hedge cap on a jump-only second no longer marks a
#   position hedged; hedge_broken needs failures on 2 different markets (one market's reject loop blocks no other); the
#   jump shadow reads every second until it would send and writes below the hedge pass; the startup self-test leaves no
#   TEMP folder behind.
#   Round 5 (11-08, the three reviews of round 4), in pinrun: the startup self-test's TEMP check judges what its retrying
#   sweep could not remove (one folder a virus scanner held for a moment failed it: pin refused to start, and inside this
#   script's watch that read as a dead pin); the rest of pinrun's round 5 is new self-test checks. In THIS script: every
#   restart has an output file of its own (the pin a restart starts inherits a handle to that file, so a second restart
#   into the same file never ran while the old file was read as "rolled back"); a rollback restarts exactly like step 6
#   and counts only when CONFIRMED from the next pin log, else exit 5; a restart waits for flat AND a clear clock (>= 20 s
#   after a quarter-hour close, >= 150 s before the next).
#   CALL B, in the argv this script writes: --extra-coin 1 -> 0, --late-extra 1 -> 0, --bank-brake 3.00 -> 4.5 -- the 3rd
#   bet leaves every close (budget 3 x SIZE -> 2 x SIZE, the worst close $1,153 -> $768 at SIZE 392) while SIZE and the
#   largest single order stay exactly as they are (the brake divides the bank by 8.82 either way); a 2nd boosted coin in
#   the same close is capped at 0.5 x SIZE (196 at SIZE 392, was 588) -- that is the 3rd bet's room. Evidence, the record
#   kinds and the revert: results\VERSIONS.md, the v-0925v entry.
# HOW TO RUN (on the server, after `git pull --no-rebase` -- never a rebase, stash, reset or checkout of restart_bot.ps1:
#   the keep-alive launcher's 0925t edits are uncommitted there):
#     powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-repo\results\pin_0925v.ps1
#   By default the script RE-LAUNCHES ITSELF DETACHED (WMI, like the restart) and this window only follows its log, so a
#   dropped SSH session cannot stop it half way; the follower exits with the worker's own exit code. -Foreground runs it
#   in this window instead. -Rebuild first renames a C:\kals-live-0925v left by an earlier refused run (only when no
#   launcher points at it).
# STEPS (anything wrong before step 5 changes no live launcher; the running pin is never touched before step 6):
#   1. refuse unless: 0925t is still 9e04c0252ac9 / b3c7bb48abb5 / 467782077a23 and holds all nine modules the build and
#      its self-test load; 0925v and 0925u do not exist; both launchers (C:\kals-live-0925n's, the hand launcher, and
#      C:\kals-repo's, which watch_bot.ps1 uses) still point at 0925t / 9e04c0252ac9 / b3c7bb48abb5, carry no
#      --cheap-window and still carry --extra-coin 1, --late-extra 1 and --bank-brake 3.00 once each;
#      both patches are in the repo AND are the reviewed files (sha); VERSIONS.md carries the v-0925v
#      entry with the new sha. The keep-alive launcher's git status is logged.
#   2. copy 0925t -> 0925v, apply patch_0925u.py (refuse unless pinrun is then exactly e0ba3543e7be), THEN patch_0925v.py
#      (refuse unless pinrun is exactly d51b131b55cf); pintake / ordercli must be unchanged
#   3. write BOTH edited launchers as COPIES inside the new build ($code -> 0925v, $codeSha -> d51b131b55cf, after the
#      v-0925t flag line the v-0925u comment block + "--cheap-window", "6", "10", "0.98" + the v-0925v comment block;
#      call B: "--extra-coin", "0", "--late-extra", "0", "--bank-brake", "4.5", each with its v-0925v comment line);
#      parse-check both, the two argv must match, -Check the hand copy (it must show all three new values)
#   4. the FULL new argv (from that -Check) + --selftest on the new build at BelowNormal priority, at most 10 minutes:
#      SELF-TEST PASSED, 0 FAIL, the 6 v-cheapwin and the 120 v-0925v checks ok. Only now is a live launcher touched.
#   5. back up both live launchers (.before-0925v-<stamp>, hash-checked), write the checked copies over them (hash-checked),
#      -Check both live launchers; any failure restores both (hash-checked) and stops
#   6. wait until research\pinflat.py says FLAT and the clock is clear -- at least 20 s after a quarter-hour close and at
#      least 150 s before the next (round 5) -- at most 25 minutes for flat, up to 15 more for the clock alone; then
#      restart pin through C:\kals-live-0925n\restart_bot.ps1 by WMI, its output in a file of its own
#      (results\pin_0925v_restart-<tag>-<HHmmss>.out, believed only with a "restart_bot.ps1 starting" line stamped after
#      the call began); if it refuses because pin bought again, wait for flat and the clock again (3 tries).
#      If no such moment comes, the launchers stay edited and pin's next restart (watch_bot, or its own end ~05:17 ET
#      11-10) starts the new build; the log says so.
#   7. WATCH the new pin for 6 minutes: its start record must carry code_sha d51b131b55cf, a universe refresh must answer
#      with markets, the process must still be alive, and no new-entry block may still be open at the end. If the new pin
#      died or never started, both launchers are put back to 0925t (hash-checked) and pin is restarted EXACTLY as in
#      step 6 (flat, the clock, 3 tries, a fresh output file); the rollback counts only when it is CONFIRMED from pin's
#      own records -- the next pin log's start record carries code_sha 9e04c0252ac9, results\pinrun-live.pid was written
#      after the restart and its pid is alive, the 0925v pin is gone -- never from the pid restart_bot reports.
#   8. after a restart (healthy or not): both live launchers are copied to C:\kals-repo\results\live_launcher_snapshot\
#      with SHA256SUMS.txt (plain `<sha256>  <name>` lines, checkable with sha256sum -c) and README.txt; nothing is
#      committed by this script.
# EXIT: 0 = restarted on 0925v and healthy after the watch; 1 = refused, live launchers unchanged (verified); 2 = launchers
#   edited but not restarted (the next restart starts 0925v); 3 = 0925v died or never started after the restart: the
#   launchers were put back to 0925t and pin was restarted on 0925t, CONFIRMED from its start record and pid file (round
#   5: never from the pid restart_bot reports); 4 = 0925v is running but was not healthy at the end of the watch
#   (blocked / no markets): NOT reverted, the reasons are in the log; 5 = a person must look: a launcher could not be
#   restored to its exact pre-edit bytes, or the rollback's restart could not be CONFIRMED (it did not run, pin never
#   went flat, or no 0925t start record with a live pid followed) -- the log says which; 6 = (follower only) the worker
#   did not finish within 120 minutes; it may still be running, read the log.
# REVERT: copy the two .before-0925v-* backups over the launchers and rerun restart_bot while flat (0925t untouched);
#   that also takes call B back (--extra-coin 1 --late-extra 1 --bank-brake 3.00).
# Log: results\pin_0925v.out; the worker's console: results\pin_0925v_worker.out; each restart's own output, one file
#   per call (round 5): results\pin_0925v_restart-<tag>-<HHmmss>.out
param([switch]$Child, [switch]$Foreground, [switch]$Rebuild, [string]$RunId = '')
$log = 'C:\kals-repo\results\pin_0925v.out'
$routPre = 'C:\kals-repo\results\pin_0925v_restart-'   # round 5: + <tag>-<HHmmss>.out, one file per restart call
$wout = 'C:\kals-repo\results\pin_0925v_worker.out'
# Say writes to the console handle, NOT the output stream: a function's output stream is its return value, and a Say
# inside RestoreAll / RestartByWmi would otherwise turn their $true / $false / text into an array
function Say($m) { $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m; [Console]::Out.WriteLine($l); Add-Content -Path $log -Value $l }

# ---- 0. the follower: start the worker detached, follow its log, exit with its code
if (-not $Child -and -not $Foreground) {
  $rid = (Get-Date -Format 'yyyyMMddHHmmss') + '-' + $PID
  $extra = ''
  if ($Rebuild) { $extra = ' -Rebuild' }
  $me = $MyInvocation.MyCommand.Path
  $cmd = 'cmd /c "powershell -NoProfile -ExecutionPolicy Bypass -File ' + $me + ' -Child -RunId ' + $rid + $extra + ' > ' + $wout + ' 2>&1"'
  $start0 = 0
  if (Test-Path $log) { $start0 = (Get-Item $log).Length }
  $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = 'C:\kals-repo' }
  if ($r.ReturnValue -ne 0) { Write-Output "WMI refused to start the worker (return $($r.ReturnValue)); nothing was run"; exit 1 }
  Write-Output ("worker started detached, pid {0}, run {1}; following {2} (closing this window does not stop it)" -f $r.ProcessId, $rid, $log)
  $deadline = (Get-Date).AddMinutes(120)   # round 5: was 80; step 6 and a rollback may each wait 25 + 15 minutes
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
$old = 'C:\kals-live-0925t'
$new = 'C:\kals-live-0925v'
$skipped = 'C:\kals-live-0925u'
$oldSha = '9e04c0252ac9'
$midSha = 'e0ba3543e7be'
$newSha = 'd51b131b55cf'
$pintakeSha = 'b3c7bb48abb5'
$ordercliSha = '467782077a23'
$patchU = 'C:\kals-repo\results\patch_0925u.py'
$patchV = 'C:\kals-repo\results\patch_0925v.py'
$patchUSha = 'abb9775a073e'   # sha256[:12] of the patch's text with CRs removed (LF form)
$patchVSha = 'e50514e7f55b'
$nCheapwin = 6
$nV = 120
$modules = @('pinrun.py', 'pintake.py', 'ordercli.py', 'kauth.py', 'livebook.py', 'engine.py', 'pinxfer.py', 'downtime.py', 'pinflat.py')
$launchers = @('C:\kals-live-0925n\restart_bot.ps1', 'C:\kals-repo\restart_bot.ps1')
$copies = @("$new\restart_bot.ps1", "$new\restart_bot_keepalive.ps1")
function Sha12($p) { try { (Get-FileHash -Algorithm SHA256 -Path $p -ErrorAction Stop).Hash.ToLower().Substring(0, 12) } catch { $null } }
function Sha64($p) { try { (Get-FileHash -Algorithm SHA256 -Path $p -ErrorAction Stop).Hash.ToLower() } catch { $null } }
# a patch script's sha over its text with every CR removed: the same whether git checked it out LF or CRLF
function ShaLF($p) { try { $t = [IO.File]::ReadAllText($p).Replace("`r", ''); $h = [Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($t)); (-join ($h | ForEach-Object { $_.ToString('x2') })).Substring(0, 12) } catch { $null } }
# a native command's stderr must never become a terminating error (PowerShell 5.1 + Stop)
function Native($exe, [string[]]$argv) { $ErrorActionPreference = 'Continue'; $o = & $exe @argv 2>&1 | Out-String; return @($o, $LASTEXITCODE) }
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
  # ---- 1. preconditions
  if ($Rebuild -and (Test-Path $new)) {
    foreach ($f in $launchers) { if ([IO.File]::ReadAllText($f) -match [regex]::Escape('kals-live-0925v')) { Done 1 "REFUSED: -Rebuild, but $f points at $new; nothing changed" } }
    $gone = $new + '.refused-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
    Move-Item $new $gone
    Say "-Rebuild: the leftover $new was renamed to $gone (no launcher pointed at it)"
  }
  if ((Sha12 "$old\research\pinrun.py") -ne $oldSha) { Done 1 "REFUSED: $old\research\pinrun.py is not $oldSha; nothing changed" }
  if ((Sha12 "$old\research\pintake.py") -ne $pintakeSha) { Done 1 "REFUSED: $old\research\pintake.py is not $pintakeSha; nothing changed" }
  if ((Sha12 "$old\research\ordercli.py") -ne $ordercliSha) { Done 1 "REFUSED: $old\research\ordercli.py is not $ordercliSha; nothing changed" }
  foreach ($m in $modules) { if (-not (Test-Path "$old\research\$m")) { Done 1 "REFUSED: $old\research\$m is missing (the new build and its self-test load it); nothing changed" } }
  if (Test-Path $new) { Done 1 "REFUSED: $new already exists (a refused run left it? rerun with -Rebuild); nothing changed" }
  if (Test-Path $skipped) { Done 1 "REFUSED: $skipped exists (pin_0925u.ps1 ran?) -- this script goes from 0925t straight to 0925v; nothing changed" }
  if ((ShaLF $patchU) -ne $patchUSha) { Done 1 "REFUSED: $patchU is missing or not the reviewed file ($patchUSha); pull the commit first; nothing changed" }
  if ((ShaLF $patchV) -ne $patchVSha) { Done 1 "REFUSED: $patchV is missing or not the reviewed file ($patchVSha); pull the commit first; nothing changed" }
  $vrepo = [IO.File]::ReadAllText('C:\kals-repo\results\VERSIONS.md')
  if ($vrepo -notmatch 'v-0925v' -or $vrepo -notmatch $newSha) { Done 1 "REFUSED: C:\kals-repo\results\VERSIONS.md has no v-0925v entry naming $newSha (pull the commit first); nothing changed" }
  try { $gs = Native 'git' @('-C', 'C:\kals-repo', 'status', '--porcelain', '--', 'restart_bot.ps1') } catch { $gs = @(('git not available: ' + $_.Exception.Message), -1) }
  Say ("git status of the keep-alive launcher (expected ' M restart_bot.ps1': its 0925t edits are uncommitted): [" + $gs[0].Trim() + "]")
  $quoteU = "Sure. Make sure to log and track the difference it makes and what it would've been without the rule"
  $quoteV = "Anything that could cause the 1k+ loss needs to be addressed immediately"
  $prevFlags = '    "--hedge-tick", "round", "--jump-hedge-min-ask", "0.05", "--boost-rail", "off",'
  $vBlock = @(
    $prevFlags,
    ('    # v-0925u 2026-11-07 (operator: "' + $quoteU.Replace('"', "'") + '"): built as C:\kals-live-0925u = 0925t + results\patch_0925u.py, never deployed alone -- it rides in 0925v below. One flag, = 0925t when omitted:'),
    '    #   --cheap-window 6 10 0.98: a FIRST buy (nothing held) under 98c in a market closing 06:00-10:00 ET is refused and the market skipped for the close; markets closing 06-10 ET were the only losing stretch of the day from 10-01 (-$273.18 vs +$1,767.17 the rest of the day), first buys under 98c there lost (287 markets -$73.31) and 98c+ made money (+$72.64); September went the other way, so it is a TRIAL WITH A SHADOW.',
    '    #   Every skip is shadowed in the log (refused gate cheap_window + cheap_window_settled: the size it would have asked, the belief hedge it would have bought, the result) and priced on the phone as /fixes change K, "without the rule" beside it; pinrules_watch alerts on any $10+ skip. Read 11-21: keep if K net >= $0.',
    '    #   Revert (this flag only): delete this comment block and the flag line under it, rerun restart_bot while flat (the 0925v build runs = 0925t + the fail-safe fixes with it off).',
    '    "--cheap-window", "6", "10", "0.98",',
    ('    # v-0925v 2026-11-07/08 (operator: "' + $quoteV + '"): C:\kals-live-0925v = 0925t + patch_0925u.py + patch_0925v.py (pinrun ' + $newSha + '; pintake and ordercli unchanged). The fail-safe fixes are always on; one new flag, --hedge-jump-shadow, ships OFF and is not passed here. Call B (the 3rd bet out, SIZE kept) is on the --extra-coin / --late-extra / --bank-brake lines below.'),
    '    #   Round 3 (11-08), always on: the day cap and the run abort see a market''s NET, never one leg (a hedged market''s legs book ~15 s apart: 11-02 ZEC -$281.63 then +$253.07); a jump give-up no longer marks the position hedged (the belief hedge keeps its tries); hedge sends no longer spend the close''s 24-send entry budget; --max-positions counts unhedged contracts; the paused loop re-checks hedges every 0.05 s.',
    '    #   Round 4 (11-08), always on: every leg of a market books from ONE read in ONE pass (the 15 s split was the GET throttle''s), and while pintake''s per-leg loss rail would refuse every buy new entries are blocked (leg_dip) instead of 2 refusals halting the run; the close''s hedge cap on a jump-only second no longer marks a position hedged; hedge_broken needs failures on 2 markets; the jump shadow (off) reads every second until it would send; the startup self-test leaves no TEMP folder.',
    '    #   When pin cannot see, book, hedge or account for what it holds it BLOCKS NEW ENTRIES (never a hedge, a cancel or an exit) and writes a record: unbooked (a market not booked 15 min after its close is parked and read on; its worst case counts against the run / day stop), settle_changed, hedge_fail / hedge_broken (3 failed hedge sends in a row, on 2 markets), universe_empty (/events fallback), expiry_drain / expiry_exit (no exit holding a bet), startup_bank, clock_skew, log_write_fail, dayloss_write_fail, entries_blocked / entries_resumed, api_shape.',
    '    #   Revert: $code/$codeSha back to C:\kals-live-0925t / 9e04c0252ac9 and delete the two comment blocks and the --cheap-window line above (backups *.before-0925v-*), rerun restart_bot while flat (0925t untouched).'
  ) -join "`r`n"
  # CALL B (operator 11-07: "...And the answer isn't betting less"): the 3rd bet comes out of every close and the brake
  # moves so SIZE does not -- floor(bank / (brake x bets x 98c)) is floor(bank / 8.82) both ways, the same number to the
  # bit; the largest single order (1.5 x SIZE), the per-market cap, the stake cap and the day stop are identical
  # (b_sizing_proof.py, and the self-test's v-0925v B check); the close budget falls from 3 x SIZE to 2 x SIZE.
  $bQuote = "Anything that could cause the 1k+ loss needs to be addressed immediately ... And the answer isn't betting less"
  $bCoin = @(
    '    # v-0925v call B 2026-11-08: 1 -> 0, a new coin no longer gets a 3rd bet in a close (the brake below keeps SIZE; revert: back to 1)',
    '    "--extra-coin", "0",'
  ) -join "`r`n"
  $bLate = @(
    '    # v-0925v call B 2026-11-08: 1 -> 0, the last seconds no longer add a 3rd bet either (revert: back to 1)',
    '    "--late-extra", "0",'
  ) -join "`r`n"
  $bBrake = @(
    ('    # v-0925v call B 2026-11-08 (operator 11-07: "' + $bQuote.Replace('"', "'") + '"): 3.00 -> 4.5 with --extra-coin 1 -> 0 and --late-extra 1 -> 0 above. A close may now hold 2 x SIZE of main bets, not 3 x (the worst close $1,153 -> $768 at SIZE 392, two band-boosted coins no longer both fill), and SIZE does not move: it is floor(bank / (brake x bets x 98c)) = floor(bank / 8.82) both ways (3.00 x 3 = 4.5 x 2). The largest single order (1.5 x SIZE), the per-market cap, the stake cap and the day stop are identical; a 2nd boosted coin in the same close is now capped at 0.5 x SIZE (196 at SIZE 392, was 588) -- the 3rd bet''s room. Cost: the 3rd bet''s own trades, $1.26-$4.28/day at today''s size (29 closes since 09-19, 0 lost); keep unless they run above $5/day over 30 days (the scan''s bar). Revert: 4.5 -> 3.00 and both lines above back to 1.'),
    '    "--bank-brake", "4.5",'
  ) -join "`r`n"
  $edits = @(
    @('$code = "C:\kals-live-0925t"', '$code = "C:\kals-live-0925v"'),
    @('$codeSha = "9e04c0252ac9"', ('$codeSha = "' + $newSha + '"')),
    @($prevFlags, $vBlock),
    @('    "--extra-coin", "1",', $bCoin),
    @('    "--late-extra", "1",', $bLate),
    @('    "--bank-brake", "3.00",', $bBrake)
  )
  $texts = @{}
  foreach ($f in $launchers) {
    $t = [IO.File]::ReadAllText($f)
    foreach ($w in @('cheap-window', 'v-0925u', 'v-0925v', 'kals-live-0925u', 'kals-live-0925v')) {
      if ($t -match [regex]::Escape($w)) { Done 1 "REFUSED: $f already mentions $w; nothing changed" }
    }
    if ($t -notmatch [regex]::Escape(('$pintakeSha = "' + $pintakeSha + '"'))) { Done 1 "REFUSED: $f does not pin pintake $pintakeSha; nothing changed" }
    foreach ($e in $edits) {
      $n = ([regex]::Matches($t, [regex]::Escape($e[0]))).Count
      if ($n -ne 1) { Done 1 ("REFUSED: {0}: expected once, found {1}: {2}; nothing changed" -f $f, $n, $e[0]) }
    }
    $texts[$f] = $t
    $orig[$f] = Sha64 $f
  }
  Say "preconditions ok: $old is $oldSha / $pintakeSha / $ordercliSha with all nine modules, both launchers point at it, both reviewed patches and the VERSIONS.md entry are in the repo"
  # ---- 2. the new build: 0925t + 0925u + 0925v
  Copy-Item -Recurse $old $new
  Get-ChildItem -Recurse -Directory -Filter '__pycache__' $new | Remove-Item -Recurse -Force
  $po = Native $py @('-u', $patchU, $new)
  Say ("patch 0925u (exit {0}): {1}" -f $po[1], $po[0].Trim())
  $got = Sha12 "$new\research\pinrun.py"
  if ($got -ne $midSha) { Done 1 "REFUSED: after patch_0925u.py pinrun.py is $got, expected $midSha; $new left for inspection (-Rebuild clears it), launchers untouched" }
  $po = Native $py @('-u', $patchV, $new)
  Say ("patch 0925v (exit {0}): {1}" -f $po[1], $po[0].Trim())
  $got = Sha12 "$new\research\pinrun.py"
  if ($got -ne $newSha) { Done 1 "REFUSED: after patch_0925v.py pinrun.py is $got, expected $newSha; $new left for inspection (-Rebuild clears it), launchers untouched" }
  $gotT = Sha12 "$new\research\pintake.py"
  if ($gotT -ne $pintakeSha) { Done 1 "REFUSED: pintake.py is $gotT, expected $pintakeSha unchanged; $new left for inspection, launchers untouched" }
  $gotO = Sha12 "$new\research\ordercli.py"
  if ($gotO -ne $ordercliSha) { Done 1 "REFUSED: ordercli.py is $gotO, expected $ordercliSha unchanged; $new left for inspection, launchers untouched" }
  Say "new build ok: $new\research\pinrun.py code_sha $got ($oldSha -> $midSha -> $newSha), pintake.py $gotT, ordercli.py $gotO"
  Copy-Item 'C:\kals-repo\results\VERSIONS.md' "$new\results\VERSIONS.md" -Force
  # ---- 3. the edited launchers, as COPIES in the new build first
  for ($i = 0; $i -lt 2; $i++) {
    $f = $launchers[$i]
    $t = $texts[$f]
    $bytes = [IO.File]::ReadAllBytes($f)
    $bom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
    foreach ($e in $edits) { $t = $t.Replace($e[0], $e[1]) }
    [IO.File]::WriteAllText($copies[$i], $t, (New-Object System.Text.UTF8Encoding($bom)))
    $errs = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($copies[$i], [ref]$null, [ref]$errs)
    if ($errs.Count) { Done 1 ("REFUSED: the edited copy of {0} has {1} parse errors ({2}); live launchers untouched" -f $f, $errs.Count, $copies[$i]) }
  }
  function ArgvOf($f) { @([IO.File]::ReadAllLines($f) | Where-Object { $_ -match '^\s*"--' } | ForEach-Object { $_.Trim().TrimEnd(',') }) }
  $dif = @(Compare-Object (ArgvOf $copies[0]) (ArgvOf $copies[1]))
  if ($dif.Count) { foreach ($d in $dif) { Say ("ARGV DIFFERS: {0} {1}" -f $d.SideIndicator, $d.InputObject) }; Done 1 "REFUSED: the two edited launchers' pin argv differ; live launchers untouched" }
  Say ("edited copies parse and their pin argv match ({0} lines)" -f (ArgvOf $copies[0]).Count)
  $must = @("code_sha $newSha", "pintake\.py sha256\[:12\] $pintakeSha", "ordercli\.py sha256\[:12\] $ordercliSha",
    '--cheap-window 6 10 0\.98',
    '--hedge-tick round', '--jump-hedge-min-ask 0\.05', '--boost-rail off', '--max-positions 5',
    '--hedge-odds-mult 1\.25', '--hedge-odds-min-tau 11', '--ws-later-fall-c 10', '--hedge-jump-max 8',
    '--bank-brake 4\.5\s', '--extra-coin 0\s', '--late-extra 0\s', '--late-extra-tau 15',
    '--band99-ceiling 0\.99', '--band-mult 0\.955 0\.981 1\.5', '--late-mult 1\.5',
    '--minutes 4320', '--loss-cap-frac 0\.187')
  function Missing($txt) { @($must | Where-Object { $txt -notmatch $_ }) }
  $chk = (Native 'powershell' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $copies[0], '-Check'))[0]
  Add-Content -Path $log -Value $chk
  $line = ($chk -split "`n" | Where-Object { $_ -match 'kals-live-0925v\\research\\pinrun\.py' -and $_ -match '--cheap-window 6 10 0\.98' -and $_ -match '--hedge-tick round' -and $_ -match '--bank-brake 4\.5\s' -and $_ -match '--extra-coin 0\s' -and $_ -match '--late-extra 0\s' -and $_ -notmatch '--hedge-jump-shadow' } | Select-Object -First 1)
  $miss = Missing $chk
  if (-not $line -or $miss.Count -or $chk -match 'ABORTING') { Done 1 ("REFUSED: -Check of the edited hand launcher did not show the new build with every flag; missing: " + ($miss -join ' | ') + "; live launchers untouched") }
  Say "edited hand launcher -Check ok"
  # ---- 4. the full-argv self-test on the new build, before any live launcher is touched
  $argv = ($line.Trim() -split '\s+')
  $ix = [array]::IndexOf($argv, ($argv | Where-Object { $_ -like '*pinrun.py' } | Select-Object -First 1))
  $targs = @('-u', "$new\research\pinrun.py") + $argv[($ix + 1)..($argv.Length - 1)] + @('--selftest')
  Say ("self-test: " + ($targs -join ' '))
  New-Item -ItemType Directory -Force "$new\selftest" | Out-Null
  $p = Start-Process -FilePath $py -ArgumentList $targs -RedirectStandardOutput "$new\selftest\0925v_selftest.out" -RedirectStandardError "$new\selftest\0925v_selftest.err" -NoNewWindow -PassThru
  $null = $p.Handle   # PowerShell 5: without this ExitCode is empty after WaitForExit
  try { $p.PriorityClass = "BelowNormal" } catch {}
  if (-not $p.WaitForExit(600000)) { try { $p.Kill() } catch {}; Done 1 "REFUSED: the self-test did not finish in 10 minutes (killed); live launchers untouched" }
  $so = [IO.File]::ReadAllText("$new\selftest\0925v_selftest.out")
  $nok = ([regex]::Matches($so, '(?m)^  ok   ')).Count
  $nfail = ([regex]::Matches($so, '(?m)^  FAIL ')).Count
  $ncw = ([regex]::Matches($so, '(?m)^  ok   v-cheapwin')).Count
  $nvv = ([regex]::Matches($so, '(?m)^  ok   v-0925v')).Count
  if ($p.ExitCode -ne 0 -or $so -notmatch 'SELF-TEST PASSED' -or $nfail -ne 0 -or $ncw -ne $nCheapwin -or $nvv -ne $nV) { Done 1 ("REFUSED: self-test FAILED (exit {0}, {1} ok, {2} FAIL lines, {3} of {4} v-cheapwin ok, {5} of {6} v-0925v ok); see $new\selftest\0925v_selftest.out; live launchers untouched" -f $p.ExitCode, $nok, $nfail, $ncw, $nCheapwin, $nvv, $nV) }
  Say ("self-test PASSED ({0} ok, 0 FAIL, the {1} v-cheapwin and {2} v-0925v checks ok) with the full new argv" -f $nok, $ncw, $nvv)
  # ---- 5. the live launchers: backed up (checked), replaced by the checked copies (checked), -Check
  $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  for ($i = 0; $i -lt 2; $i++) {
    $f = $launchers[$i]
    if ((Sha64 $f) -ne $orig[$f]) { if ($script:edited) { if (-not (RestoreAll)) { Done 5 "a launcher restore FAILED" } }; Done 1 "REFUSED: $f changed while this script ran; nothing (more) changed" }
    $bak = $f + ".before-0925v-" + $stamp
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
  Say "LAUNCHERS EDITED: both point at $new / $newSha now (backups *.before-0925v-$stamp). If this log stops here, pin's next restart starts 0925v."
  foreach ($f in $launchers) {
    $c = (Native 'powershell' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $f, '-Check'))[0]
    Add-Content -Path $log -Value $c
    $miss = Missing $c
    if ($miss.Count -or $c -match 'ABORTING') { Say ("-Check of $f did not show the new build and every flag; missing: " + ($miss -join ' | ')); if (-not (RestoreAll)) { Done 5 "a launcher restore FAILED" }; Done 1 "both launchers restored; pin untouched" }
  }
  Say "both live launchers -Check ok"
} catch {
  Say ("ERROR before the restart: " + $_.Exception.Message)
  if ($script:edited) { if (-not (RestoreAll)) { Done 5 "a launcher restore FAILED after an error" } }
  Done 1 "stopped; the live launchers are as they were (pin untouched)"
}
$ErrorActionPreference = 'Continue'

# ---- 8 (used after 6). the launcher snapshot in the repo
function Snapshot {
  try {
    $sd = 'C:\kals-repo\results\live_launcher_snapshot'
    New-Item -ItemType Directory -Force $sd | Out-Null
    $pairs = @(@($launchers[0], 'restart_bot_hand.ps1'), @($launchers[1], 'restart_bot_repo.ps1'))
    $sums = @()
    $readme = @("The live launchers as pin_0925v.ps1 left them, " + (Get-Date -Format o) + "; pin restarted on $new (pinrun code_sha $newSha).")
    foreach ($pr in $pairs) {
      $dst = Join-Path $sd $pr[1]
      Copy-Item $pr[0] $dst -Force
      $sums += ("{0}  {1}" -f (Sha64 $dst), $pr[1])
      $readme += ("{0} is a byte copy of {1}" -f $pr[1], $pr[0])
    }
    Set-Content -Path (Join-Path $sd 'SHA256SUMS.txt') -Value $sums -Encoding ASCII
    Set-Content -Path (Join-Path $sd 'README.txt') -Value $readme -Encoding ASCII
    Say ("launcher snapshot written: $sd (restart_bot_hand.ps1, restart_bot_repo.ps1, SHA256SUMS.txt, README.txt); commit those exact files with git add")
  } catch {
    Say ("launcher snapshot FAILED (copy the two launchers by hand): " + $_.Exception.Message)
  }
}
# v-0925v round 5 (11-08, the deploy review of round 4): A FRESH OUTPUT FILE FOR EVERY RESTART CALL. Every call used to
# write results\pin_0925v_restart.out, and the pin a restart starts INHERITS the cmd wrapper's handle to that file
# (restart_bot's Start-Process hands its console handles on), so the rollback's own `> pin_0925v_restart.out` could not
# open it: cmd failed, restart_bot never ran, this script read the OLD file, found its "pinrun running" line and logged
# "rolled back: pin restarted on 0925t" while 0925v kept running (rev4_deploy\ps_rehearsal, scenario silentredir). Now
# each call writes a file of its own, and what it says is believed only when it carries a "restart_bot.ps1 starting"
# line stamped after the call began -- anything else is "restart_bot did not run".
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
# v-0925v round 5 (11-08): WHEN A RESTART MAY HAPPEN. Flat is not enough: restart_bot checks flat once and stops pin a few
# seconds later, and the new pin runs its startup self-test before it trades, so a restart in a close's last minutes can
# meet that close's buys or miss them. A restart (step 6 and the rollback alike) waits until pin is FLAT and the next
# quarter-hour close (ET :00 :15 :30 :45 -- every 15-minute and hourly market closes on that grid, the same seconds in
# UTC) is at least $beforeClose s away and the last one at least $afterClose s behind. The 20 s is belt and braces: while
# pin is alive pinflat already says HOLDING until every leg it holds has its settled record, so a held market's booking
# is never cut by the flat check alone (and a dead pin has nothing to book); the 20 s keeps the close's own settlement
# reads out of the restart's way. Flat keeps its 25 minutes; the clock alone may take up to 15 more.
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
# v-0925v round 5 (11-08): A ROLLBACK COUNTS ONLY WHEN IT IS SEEN. restart_bot's "pinrun running: pid N" says a python
# process was there 15 s after it started one, not which build it runs -- and in the deploy review's silentredir case
# the line read was the PREVIOUS restart's. So the rollback is confirmed from pin's own records: the next pin log
# (created after this restart began) carries a start record with code_sha 9e04c0252ac9, results\pinrun-live.pid was
# written after the restart began and the pid in it is alive, and the 0925v pin is gone. Polled for up to $confirmS s
# (the new pin writes its start record after its startup self-test).
$confirmS = 300
function ConfirmOld($since, $vPid) {
  $deadline = (Get-Date).AddSeconds($confirmS)
  $pidf = 'C:\kals-repo\results\pinrun-live.pid'
  $why = 'no pin log was created after the rollback restart began'
  while ($true) {
    $f = Get-ChildItem 'C:\kals-repo\results\pinrun-live-*.jsonl' -ErrorAction SilentlyContinue | Where-Object { $_.CreationTime -ge $since } | Sort-Object CreationTime | Select-Object -First 1
    if ($f) {
      $sha = $null
      try {
        $fs = [IO.File]::Open($f.FullName, 'Open', 'Read', 'ReadWrite')
        try { $sr = New-Object IO.StreamReader($fs); $lines = $sr.ReadToEnd() -split "`n" } finally { $fs.Close() }
        foreach ($ln in $lines) { if ($ln -match '"kind": "start"') { try { $sha = [string]($ln | ConvertFrom-Json).code_sha } catch { $sha = '?' }; break } }
      } catch { $sha = $null }
      $ppid = $null
      $pidNew = $false
      if (Test-Path $pidf) { try { $ppid = [int](([IO.File]::ReadAllText($pidf)).Trim()); $pidNew = ((Get-Item $pidf).LastWriteTime -ge $since) } catch { $ppid = $null } }
      $alive = [bool]($ppid -and (Get-Process -Id $ppid -ErrorAction SilentlyContinue))
      $vGone = (-not $vPid) -or (-not (Get-Process -Id $vPid -ErrorAction SilentlyContinue))
      if (-not $sha) { $why = "the next pin log $($f.Name) has no start record" }
      elseif ($sha -ne $oldSha) { $why = "the next pin log $($f.Name) starts code_sha $sha, not $oldSha" }
      elseif (-not $pidNew) { $why = "results\pinrun-live.pid was not written after the rollback restart began" }
      elseif (-not $alive) { $why = "the pin in results\pinrun-live.pid (pid $ppid) is not running" }
      elseif ($vPid -and ($ppid -eq [int]$vPid)) { $why = "results\pinrun-live.pid still names the 0925v pin (pid $ppid)" }
      elseif (-not $vGone) { $why = "the 0925v pin (pid $vPid) is still running" }
      else {
        $gone = ''
        if ($vPid) { $gone = ", and the 0925v pin (pid $vPid) is gone" }
        return @{ ok = $true; what = ("the next pin log {0} starts code_sha {1}; results\pinrun-live.pid (written {2:HH:mm:ss}) names pid {3}, alive{4}" -f $f.Name, $sha, (Get-Item $pidf).LastWriteTime, $ppid, $gone) }
      }
    }
    if ((Get-Date) -gt $deadline) { return @{ ok = $false; why = $why } }
    Start-Sleep -Seconds 10
  }
}
function Rollback($why, $vPid) {
  Say ("ROLLING BACK to 0925t: " + $why)
  if (-not (RestoreAll)) { Done 5 "a launcher restore FAILED during the rollback; pin may be down -- a person must look" }
  # round 5: restarted EXACTLY as step 6 restarts (flat and a clear clock, its own 25 + 15 minutes, 3 tries when
  # restart_bot refuses because pin holds a bet, a fresh output file) and CONFIRMED from pin's own records (ConfirmOld),
  # never from the pid restart_bot reports: whatever cannot be confirmed is exit 5, never "rolled back"
  $flatBy = (Get-Date).AddMinutes(25)
  $clockBy = $flatBy.AddMinutes(15)
  for ($rt = 1; $rt -le 3; $rt++) {
    $w = WaitReady "rollback try $rt" $flatBy $clockBy
    if (-not $w.ok) { Done 5 ("ROLLBACK NOT CONFIRMED: the launchers are 0925t again, but " + $w.why + "; this script did not restart pin, which may still be 0925v -- a person must look (pin's next restart starts 0925t)") }
    $since = (Get-Date).AddSeconds(-5)
    $rs = RestartByWmi "rollback try $rt"
    if (-not $rs.wmi) { Done 5 "ROLLBACK NOT CONFIRMED: WMI refused to start the rollback's restart wrapper; the launchers are 0925t again but pin was not restarted -- a person must look" }
    if (-not $rs.ran) { Done 5 ("ROLLBACK NOT CONFIRMED: restart_bot did not run (" + $rs.file + " holds no 'restart_bot.ps1 starting' line from this call); the launchers are 0925t again but pin was not restarted and may still be 0925v -- a person must look") }
    if ($rs.txt -match 'REFUSING: the bot is holding a position') { Say ("rollback: restart_bot refused (try {0} of 3): pin holds a bet; waiting for flat and a clear clock again" -f $rt); continue }
    $tail = @(($rs.txt -split "`r?`n") | Where-Object { $_.Trim() } | Select-Object -Last 4)
    Say ("rollback: restart_bot ran (" + $rs.file + "; last lines: " + ($tail -join ' | ') + "); confirming from the next pin log, up to $confirmS s")
    $c = ConfirmOld $since $vPid
    if ($c.ok) { Done 3 ("ROLLED BACK, CONFIRMED: pin runs 0925t again -- " + $c.what) }
    Done 5 ("ROLLBACK NOT CONFIRMED after $confirmS s: restart_bot ran, but " + $c.why + "; the launchers are 0925t again -- a person must look")
  }
  Done 5 "ROLLBACK NOT CONFIRMED after 3 tries: restart_bot refused each time because pin held a bet; the launchers are 0925t again (pin's next restart starts 0925t) -- a person must look"
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
  $start = $false; $rows = 0; $open = @{}; $kinds = @{}
  if ($f) {
    $fs = [IO.File]::Open($f.FullName, 'Open', 'Read', 'ReadWrite')
    try { $sr = New-Object IO.StreamReader($fs); $lines = $sr.ReadToEnd() -split "`n" } finally { $fs.Close() }
    foreach ($ln in $lines) {
      if ($ln -notmatch '"kind": "(start|universe|entries_blocked|entries_resumed|hedge_broken|clock_skew|log_write_fail|dayloss_write_fail|expiry_drain|startup_bank|unbooked|universe_empty|api_shape)"') { continue }
      try { $d = $ln | ConvertFrom-Json } catch { continue }
      $k = [string]$d.kind
      $kinds[$k] = 1 + [int]$kinds[$k]
      if ($k -eq 'start' -and [string]$d.code_sha -eq $newSha) { $start = $true }
      if ($k -eq 'universe' -and [int]$d.rows -gt 0) { $rows++ }
      if ($d.reason -and ([string]$d.blocks).StartsWith('new entries')) { $open[[string]$d.reason] = $k }
      if ($k -eq 'entries_resumed' -and $d.reason) { $open.Remove([string]$d.reason) }
    }
  }
  $seen = ($kinds.Keys | Sort-Object | ForEach-Object { "$_ x$($kinds[$_])" }) -join ', '
  Say ("watch: log {0}; start record with code_sha {1}: {2}; universe refreshes with markets: {3}; alive: {4}; still blocked: [{5}]; records seen: {6}" -f $(if ($f) { $f.Name } else { 'none' }), $newSha, $start, $rows, $alive, (($open.Keys | Sort-Object) -join ', '), $seen)
  if (-not $alive -or -not $start) { Rollback ("the new pin " + $(if (-not $alive) { "is not running" } else { "never wrote a start record with code_sha $newSha" })) $newPid }
  Snapshot
  if ($rows -lt 1 -or $open.Count) { Done 4 ("0925v IS RUNNING BUT NOT HEALTHY after 6 minutes: " + $(if ($rows -lt 1) { "no universe refresh answered with markets; " } else { "" }) + $(if ($open.Count) { "new entries still blocked by: " + (($open.Keys | Sort-Object) -join ', ') + " -- it hedges and books as normal but buys nothing while that lasts; " } else { "" }) + "NOT reverted (a block may be right); revert by hand if it is wrong: copy the .before-0925v-* backups back and rerun restart_bot while flat") }
  Done 0 ("DONE: pin restarted on 0925v (code_sha $newSha, --cheap-window 6 10 0.98, call B --extra-coin 0 --late-extra 0 --bank-brake 4.5, the v-0925v fail-safes), pid $newPid, healthy after the 6-minute watch")
}
# ---- 6. wait for flat AND a clear clock (round 5), then the restart through the hand launcher (restart_bot refuses
# while pin holds a bet); one 25-minute flat budget for all three tries, up to 15 more for the clock alone
$flatBy = (Get-Date).AddMinutes(25)
$clockBy = $flatBy.AddMinutes(15)
for ($try = 1; $try -le 3; $try++) {
  $w = WaitReady "restart try $try" $flatBy $clockBy
  if (-not $w.ok) { Done 2 ("NOT RESTARTED: " + $w.why + ". The launchers ARE edited, so pin's next restart (watch_bot, or its own end ~05:17 ET 11-10) starts 0925v; /approve pinrestart restarts it sooner") }
  $since = (Get-Date).AddSeconds(-5)
  $rs = RestartByWmi "try $try"
  if (-not $rs.wmi) { Done 2 "WMI refused to start the restart wrapper; nothing restarted (the launchers ARE edited)" }
  if (-not $rs.ran) { Done 2 ("NOT RESTARTED: restart_bot did not run (" + $rs.file + " holds no 'restart_bot.ps1 starting' line from this call), so pin was not touched; the launchers ARE edited, so pin's next restart starts 0925v") }
  $txt = $rs.txt
  if ($txt -match 'pinrun running: pid (\d+)') { WatchNew ([int]$matches[1]) $since }
  if ($txt -match 'REFUSING: the bot is holding a position') { Say "restart_bot refused: pin bought again between the flat check and the restart; waiting for flat and a clear clock again"; continue }
  if ($txt -match 'FAILED: pinrun did not come back') { Rollback "restart_bot stopped 0925t but the new pin did not come back" $null }
  $tail = @(($txt -split "`r?`n") | Where-Object { $_.Trim() } | Select-Object -Last 6)
  Done 2 ("restart_bot did not report a running pin; its last lines: " + ($tail -join ' | ') + "; if pin is down, watch_bot restarts it (on 0925v) within minutes")
}
Done 2 "NOT RESTARTED after 3 tries: pin kept holding a bet at the restart moment; the launchers ARE edited (next restart starts 0925v)"
