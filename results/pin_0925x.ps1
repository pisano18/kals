# pin_0925x.ps1 -- 2026-11-14. Build 0925x: the 11-13 code review's four fixes + v-0925x band99late (--band99-max-tau 30).
# WHAT IT DOES: puts BOTH live launchers on a NEW build, C:\kals-live-0925x = C:\kals-live-0925w (pinrun 05a01fbb5ed2,
#   pintake b3c7bb48abb5, ordercli 467782077a23) + results\patch_0925x.py (pinrun 3a19b0019e9c) + results\
#   patch_0925x_ordercli.py (ordercli f40c43061ea3); pintake and the six other modules unchanged. In BOTH launchers
#   $code, $codeSha AND $ordercliSha move to the new build (each launcher checks ordercli's hash before it stops anything,
#   so the ordercli pin must move with the patch), and ONE argv line is added right after the band99 line
#       "--band99-ceiling", "0.99", "--band99-frac", "0.10",
#       "--band99-max-tau", "30",          (with a two-line v-0925x comment between them)
#   Every other byte stays. PIN IS NEVER RESTARTED BY THIS SCRIPT: the running pin (0925w) keeps trading as it is; its
#   --minutes 4320 run ends about 2026-11-16 12:36Z (07:36 ET) and watch_bot.ps1 restarts it through the keep-alive
#   launcher C:\kals-repo\restart_bot.ps1, which then starts 0925x. To start it sooner, restart while pin is FLAT (see
#   RESTART BY HAND below).
#   v-0925x (patch_0925x.py; its docstring has the detail): always on -- clock (book_shape_wrap knows Kalshi's "clock"
#   key), prebank (no DAY stop before the first bank read sets the real one), drain (a halt that cleared ends its
#   drain), connect (a connect-phase hedge failure is never-sent and is resent next second; ordercli marks it). NEW FLAG
#   band99late, --band99-max-tau 30: a band99 leg (a tenth of the coin's bet at up to 99c in a market pin holds nothing
#   in) is placed only with 30 s or less to the close. WHY (11-14, three independent reads of the live band, 1,036 band
#   markets 10-31..11-14): band legs at 31-45 s held ALL 12 band losses and, being the market's early leg, took pin's
#   own early slot (pin's early leg then refused early_once) -- all-in about -$7/day (P<0 ~0.85); band legs at <= 30 s
#   lost 0 of 396 markets, all-in about +$6/day (P<0 ~0.04). A band leg that is too early is refused band99_early and
#   written ONCE a market as band99_shadow (what it would have bought: side, ask and size, tau, n, limit, ladder, fair,
#   EV...); it spends no early leg, no fill, no attempt, so pin's own early leg can still buy that market.
# HOW TO RUN (on the server, RIGHT AFTER `git pull --ff-only` brings this script, patch_0925x.py, patch_0925x_ordercli.py,
#   VERSIONS.md's v-0925x entry and the new results\live_launcher_snapshot\ -- from that pull until this has run,
#   kalshi_watch's 30-minute launcher check alarms, because the committed snapshot already names 0925x; that alarm is
#   this deploy, not a fault):
#     powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-repo\results\pin_0925x.ps1
#   It runs in the foreground, about 2-6 minutes (most of it the self-test). A dropped SSH session before step 4 changes
#   no launcher; step 4 itself is two file copies, and a rerun finishes a half-done one (see step 1). Run it as an ssh
#   command of its own: the restart guard refuses while ANY process's command line names restart_bot.ps1 (not -Check),
#   so a chained command that also names a launcher makes it refuse ("nothing changed").
# STEPS (nothing before step 4 touches a live launcher; pin itself is never touched):
#   1. refuse, "nothing changed", unless: C:\kals-live-0925w is exactly pinrun 05a01fbb5ed2 / pintake b3c7bb48abb5 /
#      ordercli 467782077a23 and the six other modules at their pinned hashes; both patch files are there; VERSIONS.md
#      carries the v-0925x entry; the repo's SHA256SUMS.txt names exactly this script's NEW hash for both snapshots (the
#      snapshot committed with this script); each live launcher's sha256 is EXACTLY its OLD hash = the snapshot committed
#      before this one (HEAD 8bfb98c 11-14: hand 27ee9d11c3b4, repo 8e42496cb426 -- the v-oddsmult15 bytes, which pin
#      $code, $codeSha, $ordercliSha and every flag); in each, the four edited lines appear once (the band99 line on a
#      line of its own) and there is no --band99-max-tau / v-0925x / kals-live-0925x text; no restart_bot.ps1 is
#      running right now (a restart reads the launcher: run this again in a minute). A launcher that is ALREADY the NEW
#      bytes (a run that stopped between its two writes) is left as it is and only the other one is edited; both already
#      NEW = "NOTHING TO DO" (the build and both -Checks are verified), exit 0. Any third state is refused.
#   2. the build: copy 0925w -> 0925x (no __pycache__, selftest, deploy or work folders), run both patches, refuse
#      unless pinrun is 3a19b0019e9c, ordercli f40c43061ea3 and pintake + the six others unchanged. A 0925x that ALREADY
#      exists is used only if every one of its nine modules is exactly the pinned build (a rerun); anything else there
#      is refused (look before deleting it). The build gets VERSIONS.md (results\) for its self-test.
#   3. both edited launchers as COPIES (C:\kals-live-0925x\deploy0925x\): each copy's sha256 must be the NEW hash
#      (byte-exact = the committed snapshot); parse-check; the two copies' argv lines match; each differs from its live
#      launcher's argv lines by exactly the one added "--band99-max-tau", "30" line; the -Check line of EACH copy must be
#      the -Check line of a live launcher with only the build path (0925w -> 0925x) and "--band99-frac 0.10 " ->
#      "--band99-frac 0.10 --band99-max-tau 30 " changed, and show code_sha 3a19b0019e9c, ordercli f40c43061ea3, pintake
#      b3c7bb48abb5. Then the FULL new argv (from that -Check) + --selftest on 0925x at BelowNormal priority, at most 10
#      minutes: SELF-TEST PASSED, 0 FAIL and EXACTLY 1632 ok lines (the 0925x patch's 1624 + 8 band99late checks,
#      measured 11-14 on a byte copy of the build with this argv), 17 v-0925x, 11 v-hedge5, 120 v-0925v and 6 v-cheapwin
#      among them. pin runs this same self-test at its next start and refuses to trade on a FAIL, so it is run here first.
#   4. back up both live launchers (.before-0925x-<stamp>, hash-checked = OLD), write the checked copies over them -- the
#      hand launcher first, the keep-alive one (watch_bot's) last -- each hash-checked = NEW, then -Check both live
#      launchers (the same expected line as step 3); any failure restores both (hash-checked = OLD) and stops.
#   5. report: the live launchers now equal the committed snapshot (kalshi_watch quiet again), pin's pid and run end.
#      NO restart.
# EXIT: 0 = both live launchers start 0925x with --band99-max-tau 30 and -Check clean, or already did (pin not
#   restarted; 0925x from its next start); 1 = refused or restored, the live launchers are as they were (verified);
#   5 = a person must look (a launcher could not be restored to its exact pre-edit bytes, or both launchers are the NEW
#   bytes but their -Check fails: pin's next restart would abort -- the log names it).
# CONFIRM 0925x IS LIVE (after pin's next start): the newest results\pinrun-live-*.jsonl start record carries code_sha
#   3a19b0019e9c and band99_max_tau 30; band99_shadow records appear for band offers with more than 30 s left; no
#   order with band99 true has tau_at_send over 30. READ: READS_DUE band99-late-read (due 2026-11-30).
# RESTART BY HAND (only if 0925x should start before the natural restart): while pin is FLAT and not within ~150 s of a
#   quarter-hour close, the operator's phone /approve pinrestart; or on the server, from SSH only via WMI:
#     Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = 'cmd /c "powershell
#       -NoProfile -ExecutionPolicy Bypass -File C:\kals-live-0925n\restart_bot.ps1 > C:\kals-repo\results\
#       pin_0925x_restart.out 2>&1"'; CurrentDirectory = 'C:\kals-live-0925n' }
#   restart_bot refuses by itself while pin holds a bet (pinflat) and checks the build's hashes before it stops anything.
# REVERT: powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-repo\results\pin_0925x.ps1 -Revert
#   (refuses unless each live launcher is exactly the NEW bytes or already OLD; copies its newest .before-0925x-*
#   backup whose sha256 is OLD back over it, hand first, keep-alive last; refuses-and-restores unless each is then
#   exactly OLD and -Check shows 0925w (code_sha 05a01fbb5ed2, ordercli 467782077a23) without --band99-max-tau). pin
#   takes 0925w at its next start (it is never restarted here). C:\kals-live-0925x is left (harmless). Then commit the
#   previous snapshot back (results\live_launcher_snapshot\restart_bot_hand.ps1, restart_bot_repo.ps1, SHA256SUMS.txt
#   and README.md from the commit before v-0925x), or kalshi_watch alarms every 30 minutes. To drop only the new flag
#   and keep the four fixes: take the "--band99-max-tau", "30", line (and its two comment lines) out of both launchers
#   by hand and refresh the snapshot. If pin already runs 0925x, a revert takes effect at its next restart.
# Log: results\pin_0925x.out; the self-test's own output: C:\kals-live-0925x\selftest\0925x_selftest.out / .err
param([switch]$Revert)
$log = 'C:\kals-repo\results\pin_0925x.out'
# Say writes to the console handle, NOT the output stream (a function's output stream is its return value)
function Say($m) { $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m; [Console]::Out.WriteLine($l); Add-Content -Path $log -Value $l }
function Done($code, $m) { if ($m) { Say $m }; Say ("EXIT {0}" -f $code); exit $code }

$py = 'C:\Python314\python.exe'
$old = 'C:\kals-live-0925w'
$build = 'C:\kals-live-0925x'
$oldSha = '05a01fbb5ed2'
$codeSha = '3a19b0019e9c'
$pintakeSha = 'b3c7bb48abb5'
$ordercliOld = '467782077a23'
$ordercliSha = 'f40c43061ea3'
# the six modules neither patch touches: 0925w's bytes (= the live copies read 11-13), unchanged in 0925x
$same = [ordered]@{ 'kauth.py' = 'efa79fa98e62'; 'livebook.py' = '64e520bdd46c'; 'engine.py' = '6877a74a7441';
  'pinxfer.py' = 'e8589ee03cf4'; 'downtime.py' = '2da80f11dacb'; 'pinflat.py' = 'c2483aa10647' }
$nOkPinned = 1632    # PowerShell names are case-insensitive, so the count read from the run is $nOkSeen, never $nok
$nX = 17           # the four fixes' 9 + band99late's 8
$nH5 = 11
$nV = 120
$nCheapwin = 6
$versions = 'C:\kals-repo\results\VERSIONS.md'
$sums = 'C:\kals-repo\results\live_launcher_snapshot\SHA256SUMS.txt'
$patchPin = 'C:\kals-repo\results\patch_0925x.py'
$patchOc = 'C:\kals-repo\results\patch_0925x_ordercli.py'
$pidFile = 'C:\kals-repo\results\pinrun-live.pid'
$pinLogs = 'C:\kals-repo\results\pinrun-live-*.jsonl'
$work = "$build\deploy0925x"
# each live launcher, the snapshot it is a byte copy of, and its sha256 before (OLD) and after (NEW) this edit
$hand = @{ path = 'C:\kals-live-0925n\restart_bot.ps1'; snap = 'restart_bot_hand.ps1'; what = 'the hand launcher';
  old = '27ee9d11c3b4701d2bb2cfd3d8028fe598ceda454115efeae49567bf4bb53c2b';
  new = '394d82b4af542589f6a2091e7c9b873b97185d6e2ab6e25531f10fbf1fb56c51' }
$keep = @{ path = 'C:\kals-repo\restart_bot.ps1'; snap = 'restart_bot_repo.ps1'; what = 'the keep-alive launcher (watch_bot.ps1 restarts pin through it)';
  old = '8e42496cb426c2d38f06d6283e84dd9f4a35d73c57e7a56ae4fce151a49dd19d';
  new = '1aef96571579dbd12bf53eb8ab526e7fa222b3b9c561db5bb33c7e97a81d75fb' }
$launchers = @($hand, $keep)          # written in this order: the keep-alive launcher last
# THE EDITS. The snapshot committed with this script (the NEW hashes above) was made 11-14 by applying exactly these
# definitions -- $anchor, $newFlag, $why, $editPairs, Count and Forward, read from this file's own syntax tree, never
# retyped -- to the 11-14 snapshot (the OLD hashes): change one byte of them and step 3 refuses.
$anchor = '    "--band99-ceiling", "0.99", "--band99-frac", "0.10",'
$newFlag = '    "--band99-max-tau", "30",'
$why = @(
  '    # v-0925x 2026-11-14: C:\kals-live-0925x = 0925w + results\patch_0925x.py + patch_0925x_ordercli.py (pinrun 3a19b0019e9c, ordercli f40c43061ea3; pintake unchanged): the 11-13 review fixes always on (clock, prebank, drain, connect) and ONE new flag, the line under this block: --band99-max-tau 30 (band99late) places a band leg (the line above) only with 30 s or less to the close. 11-14 reads of the live band: legs at 31-45 s held all 12 band losses and took pin''s early slot (about -$7/day all-in); legs at 30 s or less lost 0 of 396 markets (about +$6/day). A band leg that is too early is refused band99_early and written once a market as band99_shadow; it spends no early leg, fill or attempt, so pin''s own early leg can still buy. Read: READS_DUE band99-late-read (11-30).',
  '    #   Revert: results\pin_0925x.ps1 -Revert (the .before-0925x-* backups: this block and the line under it out, $code/$codeSha/$ordercliSha back to C:\kals-live-0925w / 05a01fbb5ed2 / 467782077a23), pin takes it at its next start. Or drop only the line under this block (and this block): the band as before, the four fixes kept.'
)
$editPairs = @(
  @('$code = "C:\kals-live-0925w"', '$code = "C:\kals-live-0925x"'),
  @('$codeSha = "05a01fbb5ed2"', '$codeSha = "3a19b0019e9c"'),
  @('$ordercliSha = "467782077a23"', '$ordercliSha = "f40c43061ea3"')
)
$oldPath = 'C:\kals-live-0925w\research\pinrun.py'
$newPath = 'C:\kals-live-0925x\research\pinrun.py'
$oldPair = '--band99-frac 0.10 '
$newPair = '--band99-frac 0.10 --band99-max-tau 30 '

function Sha64($p) { try { (Get-FileHash -Algorithm SHA256 -Path $p -ErrorAction Stop).Hash.ToLower() } catch { $null } }
function Sha12($p) { $h = Sha64 $p; if ($h) { $h.Substring(0, 12) } else { $null } }
# a native command's stderr must never become a terminating error (PowerShell 5.1 + Stop)
function Native($exe, [string[]]$argv) { $ErrorActionPreference = 'Continue'; $o = & $exe @argv 2>&1 | Out-String; return @($o, $LASTEXITCODE) }
function HasBom($p) { $b = [IO.File]::ReadAllBytes($p); return ($b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF) }
function WriteText($p, $t, $bom) { [IO.File]::WriteAllText($p, $t, (New-Object System.Text.UTF8Encoding($bom))) }
function Count($t, $s) { ([regex]::Matches($t, [regex]::Escape($s))).Count }
# the forward edit on the raw text: the three pins moved, and the band99 line (once, a line of its own) -> itself + its own
# line end + the comment block + the new flag line. Returns $null when the text is not exactly the expected shape.
function Forward($t) {
  if ((Count $t $anchor) -ne 1 -or (Count $t $newFlag) -ne 0 -or (Count $t '"--band99-max-tau"') -ne 0) { return $null }
  if ($t -match 'v-0925x' -or $t -match 'kals-live-0925x') { return $null }
  foreach ($e in $editPairs) { if ((Count $t $e[0]) -ne 1 -or (Count $t $e[1]) -ne 0) { return $null } }
  $i = $t.IndexOf($anchor)
  if ($i -gt 0 -and $t[$i - 1] -ne "`n") { return $null }
  $j = $i + $anchor.Length
  $nl = $null
  if ($t.Length -ge $j + 2 -and $t.Substring($j, 2) -eq "`r`n") { $nl = "`r`n" } elseif ($t.Length -ge $j + 1 -and $t[$j] -eq "`n") { $nl = "`n" }
  if (-not $nl) { return $null }
  foreach ($e in $editPairs) { $t = $t.Replace($e[0], $e[1]) }
  return $t.Replace($anchor, ($anchor + $nl + ($why -join $nl) + $nl + $newFlag))
}
function ArgvOf($f) { @([IO.File]::ReadAllLines($f) | Where-Object { $_ -match '^\s*"--' } | ForEach-Object { $_.Trim().TrimEnd(',') }) }
# the -Check line: "  <python> -u <build>\research\pinrun.py <flags>", and the hashes the launcher printed
function CheckOf($f, $sha, $oc) {
  $c = (Native 'powershell' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $f, '-Check'))[0]
  Add-Content -Path $log -Value $c
  $line = @($c -split "`r?`n" | Where-Object { $_ -match 'kals-live-0925[wx]\\research\\pinrun\.py' -and $_ -match '\s--live\s' })
  $ok = ($c -match "code_sha $sha") -and ($c -match ('pintake\.py sha256\[:12\] ' + $pintakeSha)) -and
        ($c -match ('ordercli\.py sha256\[:12\] ' + $oc)) -and ($c -match 'CHECK ONLY') -and ($c -notmatch 'ABORTING') -and ($line.Count -eq 1)
  return @{ ok = $ok; line = $(if ($line.Count -eq 1) { $line[0].Trim() + ' ' } else { '' }); text = $c }
}
function RestartRunning {
  @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -and $_.CommandLine -match 'restart_bot\.ps1' -and $_.CommandLine -notmatch '\s-Check' -and $_.ProcessId -ne $PID })
}
# every module of a build at the hashes it must have ($pr / $oc: pinrun's and ordercli's); returns the first mismatch or $null
function BuildBad($dir, $pr, $oc) {
  foreach ($m in @(@('pinrun.py', $pr), @('ordercli.py', $oc), @('pintake.py', $pintakeSha))) {
    $g = Sha12 "$dir\research\$($m[0])"
    if ($g -ne $m[1]) { return ("$dir\research\$($m[0]) is {0}, expected {1}" -f $(if ($g) { $g } else { 'missing' }), $m[1]) }
  }
  foreach ($k in $same.Keys) {
    $g = Sha12 "$dir\research\$k"
    if ($g -ne $same[$k]) { return ("$dir\research\$k is {0}, expected {1}" -f $(if ($g) { $g } else { 'missing' }), $same[$k]) }
  }
  return $null
}
$baks = @{}
$script:edited = $false
# put every launcher this run wrote back to the bytes it had before ($want: path -> sha256), checked by sha256
function RestoreAll($want) {
  $bad = 0
  foreach ($L in $launchers) {
    if (-not $baks.ContainsKey($L.path)) { continue }
    if ((Sha64 $L.path) -eq $want[$L.path]) { continue }
    try { Copy-Item $baks[$L.path] $L.path -Force -ErrorAction Stop } catch { Say ("RESTORE COPY FAILED for {0}: {1}" -f $L.path, $_.Exception.Message) }
    if ((Sha64 $L.path) -ne $want[$L.path]) { Say ("RESTORE FAILED: {0} is not its pre-edit bytes (backup {1})" -f $L.path, $baks[$L.path]); $bad++ }
  }
  if ($bad) { return $false }
  Say "the launchers this run wrote are restored from their backups (sha256 checked against the pre-edit files)"
  return $true
}
function PinState {
  try {
    $ppid = ([IO.File]::ReadAllText($pidFile)).Trim()
    $alive = [bool](Get-Process -Id ([int]$ppid) -ErrorAction SilentlyContinue)
    $f = Get-ChildItem $pinLogs -ErrorAction Stop | Sort-Object CreationTime -Descending | Select-Object -First 1
    $fs = [IO.File]::Open($f.FullName, 'Open', 'Read', 'ReadWrite')
    try {
      $sr = New-Object IO.StreamReader($fs)
      $d = $null
      for ($k = 0; $k -lt 200; $k++) { $ln = $sr.ReadLine(); if ($null -eq $ln) { break }; if ($ln -match '"kind": "start"') { $d = $ln | ConvertFrom-Json; break } }
    } finally { $fs.Close() }
    if (-not $d) { return "pin pid $ppid (alive: $alive); no start record found in $($f.Name)" }
    $end = ([DateTime]::Parse([string]$d.t)).ToUniversalTime().AddMinutes([double]$d.minutes)
    $b9 = $null
    try { $b9 = $d.band99_max_tau } catch {}
    return ("pin pid {0} (alive: {1}) started {2} on code_sha {3} (band99_max_tau {4}); its --minutes {5} run ends about {6:yyyy-MM-dd HH:mm}Z, then watch_bot restarts it through C:\kals-repo\restart_bot.ps1" -f $ppid, $alive, $d.t, $d.code_sha, $(if ($null -eq $b9) { 'none' } else { [string]$b9 }), $d.minutes, $end)
  } catch { return ("pin state not read: " + $_.Exception.Message) }
}

Say ("start" + $(if ($Revert) { ' (-Revert)' } else { '' }))
$ErrorActionPreference = 'Stop'

# ================================================================== -Revert: both launchers back to their pre-0925x bytes
if ($Revert) {
  $from = @{}; $to = @{}
  foreach ($L in $launchers) { $from[$L.path] = $L.new; $to[$L.path] = $L.old }
  try {
    $todo = @(); $already = @(); $src = @{}
    foreach ($L in $launchers) {
      $h = Sha64 $L.path
      if ($h -eq $L.old) { $already += $L; continue }
      if ($h -ne $L.new) { Done 1 ("REFUSED: {0} ({1}) has sha256 {2}, neither this script's NEW {3} nor OLD {4}: it changed since -- look before anything is edited; nothing changed" -f $L.path, $L.what, $(if ($h) { $h } else { 'missing' }), $L.new.Substring(0, 12), $L.old.Substring(0, 12)) }
      $bk = @(Get-ChildItem -Path ($L.path + '.before-0925x-*') -ErrorAction SilentlyContinue | Where-Object { $_.Name -notmatch 'revert' -and (Sha64 $_.FullName) -eq $L.old } | Sort-Object LastWriteTime -Descending)
      if (-not $bk.Count) { Done 1 ("REFUSED: no {0}.before-0925x-* backup has the OLD bytes {1}; revert by hand (see REVERT in this script's header); nothing changed" -f $L.path, $L.old.Substring(0, 12)) }
      $src[$L.path] = $bk[0].FullName
      $todo += $L
    }
    foreach ($L in $already) { Say ("{0} is ALREADY the pre-0925x bytes ({1}): left as it is" -f $L.path, $L.old.Substring(0, 12)) }
    if (-not $todo.Count) { Done 0 "NOTHING TO DO: both live launchers are already the pre-0925x bytes" }
    $busy = @(RestartRunning)
    if ($busy.Count -gt 0) { Done 1 ("REFUSED: a restart_bot.ps1 is running right now (pid {0}): it reads the launcher; run this again in a minute or two; nothing changed" -f (($busy | ForEach-Object { $_.ProcessId }) -join ', ')) }
    if (BuildBad $old $oldSha $ordercliOld) { Done 1 ("REFUSED: the revert target is not intact: " + (BuildBad $old $oldSha $ordercliOld) + "; nothing changed") }
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    foreach ($L in $todo) {
      $bak = $L.path + '.before-0925x-revert-' + $stamp
      Copy-Item $L.path $bak -ErrorAction Stop
      if ((Sha64 $bak) -ne $L.new) { Done 1 ("REFUSED: the backup {0} is not a byte copy of {1}; nothing changed" -f $bak, $L.path) }
      $baks[$L.path] = $bak
    }
    foreach ($L in $todo) {
      $script:edited = $true
      Copy-Item ($src[$L.path]) $L.path -Force -ErrorAction Stop
      if ((Sha64 $L.path) -ne $L.old) { if (-not (RestoreAll $from)) { Done 5 "a launcher restore FAILED" }; Done 1 ("{0} was not the OLD bytes after copying {1} over it; restored" -f $L.path, $src[$L.path]) }
      Say ("REVERTED {0} ({1}) = {2} (sha256 {3}; the 0925x bytes kept as {4})" -f $L.path, $L.what, $src[$L.path], $L.old.Substring(0, 12), $baks[$L.path])
    }
    foreach ($L in $launchers) {
      $c = CheckOf $L.path $oldSha $ordercliOld
      if (-not $c.ok -or $c.line -notmatch [regex]::Escape($oldPath) -or $c.line -match '--band99-max-tau') { Say ("-Check of {0} after the revert does not show 0925w without --band99-max-tau (see the log)" -f $L.path); if (-not (RestoreAll $from)) { Done 5 "a launcher restore FAILED" }; Done 1 "the launchers this run wrote are back to the 0925x bytes; pin untouched" }
    }
  } catch {
    Say ("ERROR: " + $_.Exception.Message)
    if ($script:edited) { if (-not (RestoreAll $from)) { Done 5 "a launcher restore FAILED after an error" } }
    Done 1 "stopped; the live launchers are as they were (pin untouched)"
  }
  $ErrorActionPreference = 'Continue'
  Say (PinState)
  Done 0 "REVERTED: both live launchers start C:\kals-live-0925w (code_sha 05a01fbb5ed2, ordercli 467782077a23) without --band99-max-tau again. pin was NOT restarted: it takes 0925w at its next start. Commit the previous launcher snapshot back (see REVERT in this script's header), or kalshi_watch alarms every 30 min."
}

# ================================================================== forward
$from = @{}; $to = @{}
foreach ($L in $launchers) { $from[$L.path] = $L.old; $to[$L.path] = $L.new }
try {
  # ---- 1. preconditions
  $bad = BuildBad $old $oldSha $ordercliOld
  if ($bad) { Done 1 ("REFUSED: $old is not the live 0925w build: " + $bad + "; nothing changed") }
  foreach ($p in @($patchPin, $patchOc)) { if (-not (Test-Path $p)) { Done 1 "REFUSED: $p is missing (git pull --ff-only first); nothing changed" } }
  $vtxt = [IO.File]::ReadAllText($versions)
  if ($vtxt -notmatch '# v-0925x ' -or $vtxt -notmatch 'band99late') { Done 1 "REFUSED: $versions has no v-0925x entry (git pull --ff-only first); nothing changed" }
  $raw = [IO.File]::ReadAllText($sums)
  if ($raw.Contains("`r")) { Done 1 "REFUSED: $sums has CR line ends (it must be LF, sha256sum format); nothing changed" }
  foreach ($L in $launchers) {
    $rows = @($raw -split "`n" | Where-Object { $_ -match ('^([0-9a-f]{64})  ' + [regex]::Escape($L.snap) + '$') })
    if ($rows.Count -ne 1) { Done 1 ("REFUSED: $sums names {0} {1} times (expected once); nothing changed" -f $L.snap, $rows.Count) }
    $h = $rows[0].Substring(0, 64)
    if ($h -ne $L.new) { Done 1 ("REFUSED: $sums gives {0} as {1}, not this script's NEW {2} (pull the v-0925x commit; do not edit the hashes); nothing changed" -f $L.snap, $h.Substring(0, 12), $L.new.Substring(0, 12)) }
  }
  # each launcher is either still at the start bytes (to do) or already at the target bytes (a run that stopped half way
  # between the two writes: left as it is); anything else is refused
  $todo = @(); $already = @(); $edited = @{}
  foreach ($L in $launchers) {
    $h = Sha64 $L.path
    if ($h -eq $L.new) { $already += $L; continue }
    if ($h -ne $L.old) { Done 1 ("REFUSED: {0} ({1}) has sha256 {2}, expected exactly {3} (the committed 11-14 snapshot): it changed since this script was written -- look before anything is edited; nothing changed" -f $L.path, $L.what, $(if ($h) { $h } else { 'missing' }), $L.old) }
    $t = [IO.File]::ReadAllText($L.path)
    $n = Forward $t
    if ($null -eq $n) { Done 1 ("REFUSED: {0}: the edited lines are not in the expected shape (each once, the band99 line on a line of its own, no 0925x text); nothing changed" -f $L.path) }
    $edited[$L.path] = $n
    $todo += $L
  }
  foreach ($L in $already) { Say ("{0} is ALREADY the 0925x bytes ({1}): left as it is" -f $L.path, $L.new.Substring(0, 12)) }
  if (-not $todo.Count) {
    $bad = BuildBad $build $codeSha $ordercliSha
    if ($bad) { Done 5 ("BOTH live launchers start 0925x but the build is not the pinned one: " + $bad + " -- pin's next restart would ABORT; a person must look") }
    foreach ($L in $launchers) {
      $c = CheckOf $L.path $codeSha $ordercliSha
      if (-not $c.ok -or $c.line -notmatch [regex]::Escape($newPath) -or (Count $c.line $newPair) -ne 1) { Done 5 ("BOTH live launchers are the 0925x bytes but -Check of {0} is not clean (see the log) -- pin's next restart would ABORT; a person must look" -f $L.path) }
    }
    Say (PinState)
    Done 0 "NOTHING TO DO: both live launchers are already the 0925x bytes, the build is intact and both -Check clean"
  }
  $busy = @(RestartRunning)   # @(): one process would otherwise unroll to a bare object whose .Count is $null on 5.1
  if ($busy.Count -gt 0) { Done 1 ("REFUSED: a restart_bot.ps1 is running right now (pid {0}): it reads the launcher; run this again in a minute or two; nothing changed" -f (($busy | ForEach-Object { $_.ProcessId }) -join ', ')) }
  try { $gs = Native 'git' @('-C', 'C:\kals-repo', 'status', '--porcelain', '--', 'restart_bot.ps1') } catch { $gs = @(('git not available: ' + $_.Exception.Message), -1) }
  Say ("git status of the keep-alive launcher (expected ' M restart_bot.ps1': its live edits are uncommitted): [" + ([string]$gs[0]).Trim() + "]")
  Say ("preconditions ok: $old is $oldSha / $pintakeSha / $ordercliOld (+ the six others); VERSIONS.md has v-0925x; the committed snapshot names the NEW bytes; to edit: {0}" -f (($todo | ForEach-Object { $_.path }) -join ', '))
  Say (PinState)

  # ---- 2. the new build (or a rerun's, if it is exactly the pinned one)
  if (Test-Path $build) {
    $bad = BuildBad $build $codeSha $ordercliSha
    if ($bad) { Done 1 ("REFUSED: $build already exists and is not the pinned build (" + $bad + "): look before deleting it; nothing changed") }
    Say "$build already exists and is exactly the pinned build (a rerun): used as it is"
  } else {
    Copy-Item -Recurse $old $build
    foreach ($junk in @('selftest', 'jumpshadow', 'hedge60', 'deploy5', 'oddsmult15', 'deploy0925x')) { if (Test-Path "$build\$junk") { Remove-Item -Recurse -Force "$build\$junk" } }
    Get-ChildItem -Recurse -Directory -Filter '__pycache__' $build | Remove-Item -Recurse -Force
    $pr = Native $py @('-u', $patchOc, $build)
    Say ("patch (ordercli): " + $pr[0].Trim())
    if ($pr[1] -ne 0) { Done 1 "REFUSED: patch_0925x_ordercli.py failed (exit $($pr[1])); $build left for inspection, launchers untouched" }
    $pr = Native $py @('-u', $patchPin, $build)
    Say ("patch (pinrun): " + $pr[0].Trim())
    if ($pr[1] -ne 0) { Done 1 "REFUSED: patch_0925x.py failed (exit $($pr[1])); $build left for inspection, launchers untouched" }
    $bad = BuildBad $build $codeSha $ordercliSha
    if ($bad) { Done 1 ("REFUSED: the patched build is not the pinned one: " + $bad + "; $build left for inspection, launchers untouched") }
  }
  New-Item -ItemType Directory -Force "$build\results" | Out-Null
  Copy-Item $versions "$build\results\VERSIONS.md" -Force
  Say "new build ok: $build pinrun $codeSha, ordercli $ordercliSha, pintake $pintakeSha and the six others unchanged"

  # ---- 3. the edited launchers as COPIES first ($copies: the file each launcher will be -- a checked copy, or the live
  # file itself when it is already there), their -Check, then the full new argv self-test
  New-Item -ItemType Directory -Force $work | Out-Null
  $copies = @{}
  foreach ($L in $already) { $copies[$L.path] = $L.path }
  foreach ($L in $todo) {
    $cp = Join-Path $work $L.snap
    WriteText $cp ($edited[$L.path]) (HasBom $L.path)
    if ((Sha64 $cp) -ne $L.new) { Done 1 ("REFUSED: the edited copy {0} has sha256 {1}, not the expected {2} (the committed snapshot); live launchers untouched" -f $cp, (Sha64 $cp), $L.new) }
    $errs = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($cp, [ref]$null, [ref]$errs)
    if ($errs.Count) { Done 1 ("REFUSED: the edited copy {0} has {1} parse errors; live launchers untouched" -f $cp, $errs.Count) }
    $copies[$L.path] = $cp
  }
  $dif = @(Compare-Object (ArgvOf ($copies[$hand.path])) (ArgvOf ($copies[$keep.path])))
  if ($dif.Count) { foreach ($d in $dif) { Say ("ARGV DIFFERS: {0} {1}" -f $d.SideIndicator, $d.InputObject) }; Done 1 "REFUSED: the two edited launchers' argv lines differ; live launchers untouched" }
  $wantNew = $newFlag.Trim().TrimEnd(',')
  foreach ($L in $todo) {
    $dd = @(Compare-Object (ArgvOf $L.path) (ArgvOf ($copies[$L.path])))
    $ddTxt = ($dd | ForEach-Object { $_.SideIndicator + ' ' + $_.InputObject }) -join ' ; '
    if ($dd.Count -ne 1 -or $ddTxt -ne ('=> ' + $wantNew)) { Done 1 ("REFUSED: {0}: the argv change is not exactly the one added line (live vs copy: {1}); live launchers untouched" -f $L.path, $ddTxt) }
  }
  Say ("edited copies in $work are the expected bytes, parse, both launchers' argv lines match, and each edit adds exactly: " + $wantNew)
  # the expected -Check line = a still-to-do live launcher's own -Check line with only the build path and the band pair
  # changed; every launcher's file-to-be must print exactly it
  $cLive = CheckOf ($todo[0].path) $oldSha $ordercliOld
  if (-not $cLive.ok -or (Count $cLive.line $oldPath) -ne 1 -or (Count $cLive.line $oldPair) -ne 1 -or (Count $cLive.line '--band99-max-tau') -ne 0) { Done 1 ("REFUSED: -Check of the live {0} did not show 0925w with '{1}' once and no --band99-max-tau (the baseline line; see the log); nothing changed" -f $todo[0].path, $oldPair.Trim()) }
  $expLine = $cLive.line.Replace($oldPath, $newPath).Replace($oldPair, $newPair)
  $cNew = $null
  foreach ($L in $launchers) {
    $cc = CheckOf ($copies[$L.path]) $codeSha $ordercliSha
    if (-not $cc.ok -or $cc.line -ne $expLine) { Done 1 ("REFUSED: -Check of {0} is not the live -Check line with only the build path and '{1}' -> '{2}' (see the log); live launchers untouched" -f $copies[$L.path], $oldPair.Trim(), $newPair.Trim()) }
    if (-not $cNew) { $cNew = $cc }
  }
  Say ("-Check of both edited launchers ok: the live argv with only {0} -> {1} and '{2}' -> '{3}'; code_sha {4}, ordercli {5}, pintake {6}" -f $oldPath, $newPath, $oldPair.Trim(), $newPair.Trim(), $codeSha, $ordercliSha, $pintakeSha)
  Copy-Item ($copies[$hand.path]) "$build\restart_bot.ps1" -Force    # the build's own self-test reads its launcher
  $argv = ($cNew.line.Trim() -split '\s+')
  $ix = [array]::IndexOf($argv, ($argv | Where-Object { $_ -like '*pinrun.py' } | Select-Object -First 1))
  $targs = @('-u', "$build\research\pinrun.py") + $argv[($ix + 1)..($argv.Length - 1)] + @('--selftest')
  if (($targs -join ' ') -notmatch '--band99-ceiling 0\.99 --band99-frac 0\.10 --band99-max-tau 30 ') { Done 1 "REFUSED: the self-test argv does not carry --band99-max-tau 30 beside the band; live launchers untouched" }
  Say ("self-test: " + ($targs -join ' '))
  New-Item -ItemType Directory -Force "$build\selftest" | Out-Null
  $so0 = "$build\selftest\0925x_selftest.out"
  $p = Start-Process -FilePath $py -ArgumentList $targs -RedirectStandardOutput $so0 -RedirectStandardError "$build\selftest\0925x_selftest.err" -NoNewWindow -PassThru
  $null = $p.Handle   # PowerShell 5: without this ExitCode is empty after WaitForExit
  try { $p.PriorityClass = "BelowNormal" } catch {}
  if (-not $p.WaitForExit(600000)) { try { $p.Kill() } catch {}; Done 1 "REFUSED: the self-test did not finish in 10 minutes (killed); live launchers untouched" }
  $so = [IO.File]::ReadAllText($so0)
  $nOkSeen = ([regex]::Matches($so, '(?m)^  ok   ')).Count
  $nFail = ([regex]::Matches($so, '(?m)^  FAIL ')).Count
  $nx9 = ([regex]::Matches($so, '(?m)^  ok   v-0925x')).Count
  $nh = ([regex]::Matches($so, '(?m)^  ok   v-hedge5')).Count
  $nvv = ([regex]::Matches($so, '(?m)^  ok   v-0925v')).Count
  $ncw = ([regex]::Matches($so, '(?m)^  ok   v-cheapwin')).Count
  if ($p.ExitCode -ne 0 -or $so -notmatch 'SELF-TEST PASSED' -or $nFail -ne 0 -or $nOkSeen -ne $nOkPinned -or $nx9 -ne $nX -or $nh -ne $nH5 -or $nvv -ne $nV -or $ncw -ne $nCheapwin) { Done 1 ("REFUSED: self-test not as pinned (exit {0}, {1} ok vs {2} pinned, {3} FAIL lines, {4} of {5} v-0925x, {6} of {7} v-hedge5, {8} of {9} v-0925v, {10} of {11} v-cheapwin); see $so0 and .err; live launchers untouched" -f $p.ExitCode, $nOkSeen, $nOkPinned, $nFail, $nx9, $nX, $nh, $nH5, $nvv, $nV, $ncw, $nCheapwin) }
  Say ("self-test PASSED ({0} ok = the pinned {1}, 0 FAIL; {2} v-0925x, {3} v-hedge5, {4} v-0925v, {5} v-cheapwin) with the full --band99-max-tau 30 argv on $build" -f $nOkSeen, $nOkPinned, $nx9, $nh, $nvv, $ncw)

  # ---- 4. the live launchers: backed up (checked), replaced by the checked copies (checked), -Check
  $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  foreach ($L in $todo) {
    if ((Sha64 $L.path) -ne $L.old) { Done 1 ("REFUSED: {0} changed while this script ran; nothing changed" -f $L.path) }
    $bak = $L.path + '.before-0925x-' + $stamp
    Copy-Item $L.path $bak -ErrorAction Stop
    if ((Sha64 $bak) -ne $L.old) { Done 1 ("REFUSED: the backup {0} is not a byte copy of {1}; nothing changed" -f $bak, $L.path) }
    $baks[$L.path] = $bak
  }
  $busy = @(RestartRunning)
  if ($busy.Count -gt 0) { Done 1 ("REFUSED: a restart_bot.ps1 started meanwhile (pid {0}); nothing changed -- run this again in a minute or two" -f (($busy | ForEach-Object { $_.ProcessId }) -join ', ')) }
  foreach ($L in $todo) {
    $script:edited = $true
    Copy-Item ($copies[$L.path]) $L.path -Force -ErrorAction Stop
    if ((Sha64 $L.path) -ne $L.new) { if (-not (RestoreAll $from)) { Done 5 "a launcher restore FAILED" }; Done 1 ("{0} was not the checked copy after writing it; restored" -f $L.path) }
    Say ("CHANGED {0} ({1}) = {2} (sha256 {3}; backup {4})" -f $L.path, $L.what, $copies[$L.path], $L.new.Substring(0, 12), $baks[$L.path])
  }
  foreach ($L in $launchers) {
    $c = CheckOf $L.path $codeSha $ordercliSha
    if (-not $c.ok -or $c.line -ne $expLine) { Say ("-Check of {0} after the write is not the expected line (see the log)" -f $L.path); if (-not (RestoreAll $from)) { Done 5 "a launcher restore FAILED" }; Done 1 "the launchers this run wrote are restored; pin untouched" }
  }
  Say "both live launchers -Check ok"
} catch {
  Say ("ERROR: " + $_.Exception.Message)
  if ($script:edited) { if (-not (RestoreAll $from)) { Done 5 "a launcher restore FAILED after an error" } }
  Done 1 "stopped; the live launchers are as they were (pin untouched)"
}
$ErrorActionPreference = 'Continue'

# ---- 5. report (no restart)
$snapNote = ''
try {
  $raw = [IO.File]::ReadAllText($sums)
  $agree = @($launchers | Where-Object { $raw -match ('(?m)^' + (Sha64 $_.path) + '  ' + [regex]::Escape($_.snap) + '$') }).Count
  $snapNote = $(if ($agree -eq 2) { 'both live launchers = the committed snapshot (kalshi_watch''s launcher check is quiet again)' } else { "the committed snapshot no longer matches $(2 - $agree) live launcher(s): kalshi_watch alarms every 30 min until results\live_launcher_snapshot\ is committed to match" })
} catch { $snapNote = 'snapshot not compared: ' + $_.Exception.Message }
Say $snapNote
Say (PinState)
Done 0 "DONE: both live launchers start $build (code_sha $codeSha, ordercli $ordercliSha) with --band99-max-tau 30 (v-0925x). pin was NOT restarted: the running 0925w pin keeps trading as it is until its next start (its --minutes run end -> watch_bot, or a restart while flat: RESTART BY HAND in this script's header); confirm then that the newest pinrun-live-*.jsonl start record carries code_sha $codeSha and band99_max_tau 30."
