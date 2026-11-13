# pin_oddsmult15.ps1 -- 2026-11-13. Operator 11-13: "I'm giving you max power. Use the rest of my credits to do whatever
# you like. Improvements are obviously best."
# WHAT IT DOES (v-oddsmult15): pin's hedge EXTRA goes 1.25x -> 1.5x. ARGV ONLY, and pin is NEVER restarted by this script.
#   In BOTH live launchers the one line
#       "--hedge-odds-mult", "1.25", "--hedge-odds-min-tau", "11",
#   becomes
#       "--hedge-odds-mult", "1.5", "--hedge-odds-min-tau", "11",
#   with ONE v-oddsmult15 comment line above it (it takes the anchor line's own line end; every other byte stays). The
#   build is unchanged: C:\kals-live-0925w (pinrun 05a01fbb5ed2, pintake b3c7bb48abb5, ordercli 467782077a23); nothing
#   is copied or patched. The running pin keeps 1.25 until its next start: its --minutes 4320 run (started 11-10 12:35Z)
#   ends about 11-13 12:35Z (07:35 ET) and watch_bot.ps1 restarts it through C:\kals-repo\restart_bot.ps1, which then
#   passes 1.5. /approve pinrestart (while flat) starts it sooner.
#   v-oddsmult (11-02): when the 0.40 belief line fires with 11+ s left, pin ALSO buys (M - 1) x the position of the
#   hedge side as a second order right after the covering hedge (kind hedge_extra). At 1.5 that is 0.5x the position
#   instead of 0.25x; pinrun bounds M to [1.0, 2.0] and the extra still counts against the stake cap and the loss abort.
# WHY: the pre-registered 11-03 staging read for v-oddsmult (step 1.25x -> 1.5x when the extra's fill CAPTURE passes at
#   12 fires: >= 90% of the contracts it asks filled at <= 3c over the fire ask, nothing skipped) fell due at the 12th
#   fire on 11-09 and was never taken. On 18 fires at 1.25: 262.88 of 262.88 contracts filled, 0 skipped or refused,
#   16 won 2 lost, +$46.99 over 10.74 days (two independent verifiers agreed). Expected about +$1.5-2.5/day more at 1.5.
#   Next step 1.5 -> 2.0 on the same two-part bar over the next 12 fires (READS_DUE oddsmult-2x-staging, due 12-01).
# HOW TO RUN (on the server, RIGHT AFTER `git pull --ff-only` brings this script, VERSIONS.md's v-oddsmult15 entry and
#   the new results\live_launcher_snapshot\ -- from that pull until this has run, kalshi_watch's 30-minute launcher check
#   alarms, because the committed snapshot already says 1.5; that alarm is this deploy, not a fault):
#     powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-repo\results\pin_oddsmult15.ps1
#   It takes about a minute (most of it the self-test) and runs in the foreground: a dropped SSH session before step 4
#   changes nothing; step 4 itself is two file copies.
# STEPS (nothing before step 4 touches a live launcher; pin itself is never touched):
#   1. refuse unless: VERSIONS.md carries v-oddsmult15; the repo's SHA256SUMS.txt names exactly this script's NEW hash for
#      both snapshots; each live launcher's sha256 is EXACTLY its OLD hash (the bytes confirmed on the server 11-13
#      07:47Z = the 11-10 snapshot, which pins $code, $codeSha and every flag); the anchor line is there once, on a line
#      of its own, and no v-oddsmult15 text; C:\kals-live-0925w is pinrun 05a01fbb5ed2 / pintake b3c7bb48abb5 / ordercli
#      467782077a23; no restart_bot.ps1 is running right now (a restart reads the launcher: run this again in a minute).
#      A launcher that is ALREADY the NEW bytes (a run that stopped between its two writes) is left as it is and only the
#      other one is edited; both already NEW = "NOTHING TO DO", exit 0. Any third state is refused.
#   2. write both edited launchers as COPIES (C:\kals-live-0925w\oddsmult15\): each copy's sha256 must be the NEW hash of
#      SHA256SUMS.txt (byte-exact = the committed snapshot); parse-check; the two copies' argv lines match; each differs
#      from its live launcher's argv lines by exactly the 1.25 -> 1.5 pair; the -Check line of EACH copy must be the
#      -Check line of a live launcher with only "--hedge-odds-mult 1.25" -> "--hedge-odds-mult 1.5", and show code_sha
#      05a01fbb5ed2 with pintake and ordercli as above.
#   3. the FULL new argv (from that -Check) + --selftest on C:\kals-live-0925w at BelowNormal priority, at most 10
#      minutes: SELF-TEST PASSED, 0 FAIL and EXACTLY 1615 ok lines (the 0925w deploy's count on this server 11-10 with the
#      1.25 argv; the same 1615 measured 11-13 on a byte copy of the build with this 1.5 argv and with 1.25). pin runs this
#      same self-test at its next start and refuses to trade on a FAIL, so it is run here first.
#   4. back up both live launchers (.before-oddsmult15-<stamp>, hash-checked), write the checked copies over them -- the
#      hand launcher first, the keep-alive one (watch_bot's) last -- each hash-checked = NEW, then -Check both live
#      launchers (the same expected line as step 2); any failure restores both (hash-checked = OLD) and stops.
#   5. report: the live launchers now equal the committed snapshot (kalshi_watch quiet again), pin's pid and run end, and
#      how to confirm 1.5 is live: the next pinrun-live-*.jsonl start record carries hedge_odds_mult 1.5 (research\
#      pinrules_watch.py rule C and the phone's /fixes C read the mult from each hedge_extra record / that start record).
# EXIT: 0 = both live launchers carry 1.5 and -Check clean, or already did (pin not restarted; 1.5 from its next start);
#   1 = refused or restored, the live launchers are as they were (verified); 5 = a person must look: a launcher could not
#   be restored to its exact pre-edit bytes (the log names it and its backup).
# REVERT: powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-repo\results\pin_oddsmult15.ps1 -Revert
#   (refuses unless both live launchers are exactly the NEW bytes; takes the comment line out and "1.5" back to "1.25";
#   refuses-and-restores unless each is then exactly its OLD hash; backups *.before-oddsmult15-revert-*). pin takes 1.25
#   at its next start (/approve pinrestart sooner). Then commit the 11-10 snapshot back (results\live_launcher_snapshot\
#   restart_bot_hand.ps1, restart_bot_repo.ps1 and SHA256SUMS.txt from the commit before v-oddsmult15), or kalshi_watch
#   alarms every 30 minutes. Or by hand: the line pair back to "--hedge-odds-mult", "1.25", ... in both launchers.
# Log: results\pin_oddsmult15.out; the self-test's own output: C:\kals-live-0925w\selftest\oddsmult15_selftest.out / .err
param([switch]$Revert)
$log = 'C:\kals-repo\results\pin_oddsmult15.out'
# Say writes to the console handle, NOT the output stream (a function's output stream is its return value)
function Say($m) { $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m; [Console]::Out.WriteLine($l); Add-Content -Path $log -Value $l }
function Done($code, $m) { if ($m) { Say $m }; Say ("EXIT {0}" -f $code); exit $code }

$py = 'C:\Python314\python.exe'
$build = 'C:\kals-live-0925w'
$codeSha = '05a01fbb5ed2'
$pintakeSha = 'b3c7bb48abb5'
$ordercliSha = '467782077a23'
$nOkPinned = 1615
$versions = 'C:\kals-repo\results\VERSIONS.md'
$sums = 'C:\kals-repo\results\live_launcher_snapshot\SHA256SUMS.txt'
$pidFile = 'C:\kals-repo\results\pinrun-live.pid'
$pinLogs = 'C:\kals-repo\results\pinrun-live-*.jsonl'
$work = "$build\oddsmult15"
# each live launcher, the snapshot it is a byte copy of, and its sha256 before (OLD) and after (NEW) this edit
$hand = @{ path = 'C:\kals-live-0925n\restart_bot.ps1'; snap = 'restart_bot_hand.ps1'; what = 'the hand launcher';
  old = 'b480f67db02077a04c06d9ef7e1e031c3741ecd45963e2697bae156f88f1c016';
  new = '27ee9d11c3b4701d2bb2cfd3d8028fe598ceda454115efeae49567bf4bb53c2b' }
$keep = @{ path = 'C:\kals-repo\restart_bot.ps1'; snap = 'restart_bot_repo.ps1'; what = 'the keep-alive launcher (watch_bot.ps1 restarts pin through it)';
  old = '16ee4275dec98d721a07dee0a4ce657e27cff32631c886bf3b5b8ca6851edb53';
  new = '8e42496cb426c2d38f06d6283e84dd9f4a35d73c57e7a56ae4fce151a49dd19d' }
$launchers = @($hand, $keep)          # written in this order: the keep-alive launcher last
$anchor = '    "--hedge-odds-mult", "1.25", "--hedge-odds-min-tau", "11",'
$newFlag = '    "--hedge-odds-mult", "1.5", "--hedge-odds-min-tau", "11",'
$comment = '    # v-oddsmult15 2026-11-13 (operator 11-13: "Improvements are obviously best."): 1.25 -> 1.5, the 11-03 pre-registered next step (bar: at 12 fires the extra fills >= 90% of what it asks at <= 3c over the fire ask, nothing skipped). At 1.25: 18 fires, 262.88 of 262.88 contracts filled, 0 skipped or refused, 16 won 2 lost, +$46.99 in 10.74 days. Next: 2.0 on the same bar (READS_DUE oddsmult-2x-staging). Revert: results\pin_oddsmult15.ps1 -Revert (this line out, "1.5" back to "1.25").'
$oldPair = '--hedge-odds-mult 1.25 --hedge-odds-min-tau 11 '
$newPair = '--hedge-odds-mult 1.5 --hedge-odds-min-tau 11 '

function Sha64($p) { try { (Get-FileHash -Algorithm SHA256 -Path $p -ErrorAction Stop).Hash.ToLower() } catch { $null } }
function Sha12($p) { $h = Sha64 $p; if ($h) { $h.Substring(0, 12) } else { $null } }
# a native command's stderr must never become a terminating error (PowerShell 5.1 + Stop)
function Native($exe, [string[]]$argv) { $ErrorActionPreference = 'Continue'; $o = & $exe @argv 2>&1 | Out-String; return @($o, $LASTEXITCODE) }
function HasBom($p) { $b = [IO.File]::ReadAllBytes($p); return ($b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF) }
function WriteText($p, $t, $bom) { [IO.File]::WriteAllText($p, $t, (New-Object System.Text.UTF8Encoding($bom))) }
function Count($t, $s) { ([regex]::Matches($t, [regex]::Escape($s))).Count }
# the forward edit on the raw text: the anchor (once, a line of its own) -> the comment + the anchor's own line end + the
# new flag line. Returns $null when the text is not exactly the expected shape.
function Forward($t) {
  if ((Count $t $anchor) -ne 1 -or $t -match 'v-oddsmult15' -or (Count $t $newFlag) -ne 0) { return $null }
  $i = $t.IndexOf($anchor)
  if ($i -gt 0 -and $t[$i - 1] -ne "`n") { return $null }
  $j = $i + $anchor.Length
  $nl = $null
  if ($t.Length -ge $j + 2 -and $t.Substring($j, 2) -eq "`r`n") { $nl = "`r`n" } elseif ($t.Length -ge $j + 1 -and $t[$j] -eq "`n") { $nl = "`n" }
  if (-not $nl) { return $null }
  return $t.Replace($anchor, $comment + $nl + $newFlag)
}
# the reverse edit: the comment + its line end + the new flag line (once) -> the anchor
function Backward($t) {
  foreach ($nl in @("`r`n", "`n")) {
    $blk = $comment + $nl + $newFlag
    if ((Count $t $blk) -eq 1 -and (Count $t $comment) -eq 1 -and (Count $t $anchor) -eq 0) { return $t.Replace($blk, $anchor) }
  }
  return $null
}
function ArgvOf($f) { @([IO.File]::ReadAllLines($f) | Where-Object { $_ -match '^\s*"--' } | ForEach-Object { $_.Trim().TrimEnd(',') }) }
# the -Check line: "  <python> -u <build>\research\pinrun.py <flags>"
$pinrunRx = [regex]::Escape("$build\research\pinrun.py")
function CheckOf($f) {
  $c = (Native 'powershell' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $f, '-Check'))[0]
  Add-Content -Path $log -Value $c
  $line = @($c -split "`r?`n" | Where-Object { $_ -match $pinrunRx -and $_ -match '\s--live\s' })
  $ok = ($c -match "code_sha $codeSha") -and ($c -match ('pintake\.py sha256\[:12\] ' + $pintakeSha)) -and
        ($c -match ('ordercli\.py sha256\[:12\] ' + $ordercliSha)) -and ($c -match 'CHECK ONLY') -and ($c -notmatch 'ABORTING') -and ($line.Count -eq 1)
  return @{ ok = $ok; line = $(if ($line.Count -eq 1) { $line[0].Trim() + ' ' } else { '' }); text = $c }
}
function RestartRunning {
  @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -and $_.CommandLine -match 'restart_bot\.ps1' -and $_.CommandLine -notmatch '\s-Check' -and $_.ProcessId -ne $PID })
}
$baks = @{}
$script:edited = $false
# put every launcher this run wrote back to its pre-edit bytes, checked by sha256
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
    return ("pin pid {0} (alive: {1}) started {2} on code_sha {3} with hedge_odds_mult {4}; its --minutes {5} run ends about {6:yyyy-MM-dd HH:mm}Z, then watch_bot restarts it through C:\kals-repo\restart_bot.ps1" -f $ppid, $alive, $d.t, $d.code_sha, $d.hedge_odds_mult, $d.minutes, $end)
  } catch { return ("pin state not read: " + $_.Exception.Message) }
}

Say ("start" + $(if ($Revert) { ' (-Revert)' } else { '' }))
$ErrorActionPreference = 'Stop'
$from = @{}; $to = @{}
foreach ($L in $launchers) { if ($Revert) { $from[$L.path] = $L.new; $to[$L.path] = $L.old } else { $from[$L.path] = $L.old; $to[$L.path] = $L.new } }
try {
  # ---- 1. preconditions
  foreach ($m in @(@('pinrun.py', $codeSha), @('pintake.py', $pintakeSha), @('ordercli.py', $ordercliSha))) {
    $got = Sha12 "$build\research\$($m[0])"
    if ($got -ne $m[1]) { Done 1 ("REFUSED: $build\research\$($m[0]) is {0}, expected {1} (not the live build); nothing changed" -f $(if ($got) { $got } else { 'missing' }), $m[1]) }
  }
  if (-not $Revert) {
    $vtxt = [IO.File]::ReadAllText($versions)
    if ($vtxt -notmatch 'v-oddsmult15') { Done 1 "REFUSED: $versions has no v-oddsmult15 entry (git pull --ff-only first); nothing changed" }
    $raw = [IO.File]::ReadAllText($sums)
    if ($raw.Contains("`r")) { Done 1 "REFUSED: $sums has CR line ends (it must be LF, sha256sum format); nothing changed" }
    foreach ($L in $launchers) {
      $rows = @($raw -split "`n" | Where-Object { $_ -match ('^([0-9a-f]{64})  ' + [regex]::Escape($L.snap) + '$') })
      if ($rows.Count -ne 1) { Done 1 ("REFUSED: $sums names {0} {1} times (expected once); nothing changed" -f $L.snap, $rows.Count) }
      $h = $rows[0].Substring(0, 64)
      if ($h -ne $L.new) { Done 1 ("REFUSED: $sums gives {0} as {1}, not this script's NEW {2} (pull the v-oddsmult15 commit; do not edit the hashes); nothing changed" -f $L.snap, $h.Substring(0, 12), $L.new.Substring(0, 12)) }
    }
  }
  # each launcher is either still at the start bytes (to do) or already at the target bytes (a run that stopped half way
  # between the two writes: left as it is); anything else is refused
  $todo = @(); $already = @(); $edited = @{}
  foreach ($L in $launchers) {
    $h = Sha64 $L.path
    if ($h -eq $to[$L.path]) { $already += $L; continue }
    if ($h -ne $from[$L.path]) { Done 1 ("REFUSED: {0} ({1}) has sha256 {2}, expected exactly {3}: it changed since this script was written -- look before anything is edited; nothing changed" -f $L.path, $L.what, $(if ($h) { $h } else { 'missing' }), $from[$L.path]) }
    $t = [IO.File]::ReadAllText($L.path)
    $n = $(if ($Revert) { Backward $t } else { Forward $t })
    if ($null -eq $n) { Done 1 ("REFUSED: {0}: the flag line is not in the expected shape (once, on a line of its own); nothing changed" -f $L.path) }
    $edited[$L.path] = $n
    $todo += $L
  }
  $target = $(if ($Revert) { 'pre-v-oddsmult15 (11-10)' } else { 'v-oddsmult15' })
  foreach ($L in $already) { Say ("{0} is ALREADY the {1} bytes ({2}): left as it is" -f $L.path, $target, $to[$L.path].Substring(0, 12)) }
  if (-not $todo.Count) { Done 0 ("NOTHING TO DO: both live launchers are already the {0} bytes" -f $target) }
  $busy = @(RestartRunning)   # @(): one process would otherwise unroll to a bare object whose .Count is $null on 5.1
  if ($busy.Count -gt 0) { Done 1 ("REFUSED: a restart_bot.ps1 is running right now (pid {0}): it reads the launcher; run this again in a minute or two; nothing changed" -f (($busy | ForEach-Object { $_.ProcessId }) -join ', ')) }
  try { $gs = Native 'git' @('-C', 'C:\kals-repo', 'status', '--porcelain', '--', 'restart_bot.ps1') } catch { $gs = @(('git not available: ' + $_.Exception.Message), -1) }
  Say ("git status of the keep-alive launcher (expected ' M restart_bot.ps1': its live edits are uncommitted): [" + ([string]$gs[0]).Trim() + "]")
  Say ("preconditions ok: $build is $codeSha / $pintakeSha / $ordercliSha; to edit: {0}" -f (($todo | ForEach-Object { $_.path }) -join ', '))
  Say (PinState)

  # ---- 2. the edited launchers as COPIES first ($copies: the file each launcher will be -- a checked copy, or the live
  # file itself when it is already there)
  $dir = $(if ($Revert) { "$work\revert" } else { $work })
  New-Item -ItemType Directory -Force $dir | Out-Null
  $copies = @{}
  foreach ($L in $already) { $copies[$L.path] = $L.path }
  foreach ($L in $todo) {
    $cp = Join-Path $dir $L.snap
    WriteText $cp ($edited[$L.path]) (HasBom $L.path)
    if ((Sha64 $cp) -ne $to[$L.path]) { Done 1 ("REFUSED: the edited copy {0} has sha256 {1}, not the expected {2} (the committed snapshot); live launchers untouched" -f $cp, (Sha64 $cp), $to[$L.path]) }
    $errs = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($cp, [ref]$null, [ref]$errs)
    if ($errs.Count) { Done 1 ("REFUSED: the edited copy {0} has {1} parse errors; live launchers untouched" -f $cp, $errs.Count) }
    $copies[$L.path] = $cp
  }
  $dif = @(Compare-Object (ArgvOf ($copies[$hand.path])) (ArgvOf ($copies[$keep.path])))
  if ($dif.Count) { foreach ($d in $dif) { Say ("ARGV DIFFERS: {0} {1}" -f $d.SideIndicator, $d.InputObject) }; Done 1 "REFUSED: the two edited launchers' argv lines differ; live launchers untouched" }
  $wantOld = $(if ($Revert) { $newFlag } else { $anchor }).Trim().TrimEnd(',')
  $wantNew = $(if ($Revert) { $anchor } else { $newFlag }).Trim().TrimEnd(',')
  foreach ($L in $todo) {
    $dd = @(Compare-Object (ArgvOf $L.path) (ArgvOf ($copies[$L.path])))
    $ddTxt = ($dd | ForEach-Object { $_.SideIndicator + ' ' + $_.InputObject }) -join ' ; '
    if ($dd.Count -ne 2 -or $ddTxt -notmatch [regex]::Escape('<= ' + $wantOld) -or $ddTxt -notmatch [regex]::Escape('=> ' + $wantNew)) { Done 1 ("REFUSED: {0}: the argv change is not exactly the one line pair (live vs copy: {1}); live launchers untouched" -f $L.path, $ddTxt) }
  }
  Say ("edited copies in $dir are the expected bytes, parse, both launchers' argv lines match, and each edit is exactly: <= {0} ; => {1}" -f $wantOld, $wantNew)
  # the expected -Check line = a still-to-do live launcher's own -Check line with only the pair changed; every launcher's
  # file-to-be must print exactly it
  $pOld = $(if ($Revert) { $newPair } else { $oldPair })
  $pNew = $(if ($Revert) { $oldPair } else { $newPair })
  $cLive = CheckOf ($todo[0].path)
  if (-not $cLive.ok -or (Count $cLive.line $pOld) -ne 1 -or (Count $cLive.line $pNew) -ne 0) { Done 1 ("REFUSED: -Check of the live {0} did not show the live build with '{1}' once (the baseline line; see the log); nothing changed" -f $todo[0].path, $pOld.Trim()) }
  $expLine = $cLive.line.Replace($pOld, $pNew)
  $cNew = $null
  foreach ($L in $launchers) {
    $cc = CheckOf ($copies[$L.path])
    if (-not $cc.ok -or $cc.line -ne $expLine) { Done 1 ("REFUSED: -Check of {0} is not the live -Check line with only '{1}' -> '{2}' (see the log); live launchers untouched" -f $copies[$L.path], $pOld.Trim(), $pNew.Trim()) }
    if (-not $cNew) { $cNew = $cc }
  }
  Say ("-Check of both edited launchers ok: the live argv with only '{0}' -> '{1}'" -f $pOld.Trim(), $pNew.Trim())

  # ---- 3. the full new argv self-test (forward only: the revert goes back to the bytes pin has run on since 11-10)
  if (-not $Revert) {
    $argv = ($cNew.line.Trim() -split '\s+')
    $ix = [array]::IndexOf($argv, ($argv | Where-Object { $_ -like '*pinrun.py' } | Select-Object -First 1))
    $targs = @('-u', "$build\research\pinrun.py") + $argv[($ix + 1)..($argv.Length - 1)] + @('--selftest')
    if (($targs -join ' ') -notmatch [regex]::Escape($newPair.Trim()) -or ($targs -join ' ') -match '--hedge-odds-mult 1\.25') { Done 1 "REFUSED: the self-test argv does not carry --hedge-odds-mult 1.5; live launchers untouched" }
    Say ("self-test: " + ($targs -join ' '))
    New-Item -ItemType Directory -Force "$build\selftest" | Out-Null
    $so0 = "$build\selftest\oddsmult15_selftest.out"
    $p = Start-Process -FilePath $py -ArgumentList $targs -RedirectStandardOutput $so0 -RedirectStandardError "$build\selftest\oddsmult15_selftest.err" -NoNewWindow -PassThru
    $null = $p.Handle   # PowerShell 5: without this ExitCode is empty after WaitForExit
    try { $p.PriorityClass = "BelowNormal" } catch {}
    if (-not $p.WaitForExit(600000)) { try { $p.Kill() } catch {}; Done 1 "REFUSED: the self-test did not finish in 10 minutes (killed); live launchers untouched" }
    $so = [IO.File]::ReadAllText($so0)
    $nOkSeen = ([regex]::Matches($so, '(?m)^  ok   ')).Count
    $nFail = ([regex]::Matches($so, '(?m)^  FAIL ')).Count
    if ($p.ExitCode -ne 0 -or $so -notmatch 'SELF-TEST PASSED' -or $nFail -ne 0 -or $nOkSeen -ne $nOkPinned) { Done 1 ("REFUSED: self-test not as pinned (exit {0}, {1} ok vs {2} pinned, {3} FAIL lines); see $so0 and .err; live launchers untouched" -f $p.ExitCode, $nOkSeen, $nOkPinned, $nFail) }
    Say ("self-test PASSED ({0} ok = the pinned {1}, 0 FAIL) with the full 1.5 argv on $build" -f $nOkSeen, $nOkPinned)
  }

  # ---- 4. the live launchers: backed up (checked), replaced by the checked copies (checked), -Check
  $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  $tag = $(if ($Revert) { '.before-oddsmult15-revert-' } else { '.before-oddsmult15-' })
  foreach ($L in $todo) {
    if ((Sha64 $L.path) -ne $from[$L.path]) { Done 1 ("REFUSED: {0} changed while this script ran; nothing changed" -f $L.path) }
    $bak = $L.path + $tag + $stamp
    Copy-Item $L.path $bak -ErrorAction Stop
    if ((Sha64 $bak) -ne $from[$L.path]) { Done 1 ("REFUSED: the backup {0} is not a byte copy of {1}; nothing changed" -f $bak, $L.path) }
    $baks[$L.path] = $bak
  }
  $busy = @(RestartRunning)   # @(): one process would otherwise unroll to a bare object whose .Count is $null on 5.1
  if ($busy.Count -gt 0) { Done 1 ("REFUSED: a restart_bot.ps1 started meanwhile (pid {0}); nothing changed -- run this again in a minute or two" -f (($busy | ForEach-Object { $_.ProcessId }) -join ', ')) }
  foreach ($L in $todo) {
    $script:edited = $true
    Copy-Item ($copies[$L.path]) $L.path -Force -ErrorAction Stop
    if ((Sha64 $L.path) -ne $to[$L.path]) { if (-not (RestoreAll $from)) { Done 5 "a launcher restore FAILED" }; Done 1 ("{0} was not the checked copy after writing it; restored" -f $L.path) }
    Say ("CHANGED {0} ({1}) = {2} (sha256 {3}; backup {4})" -f $L.path, $L.what, $copies[$L.path], $to[$L.path].Substring(0, 12), $baks[$L.path])
  }
  foreach ($L in $launchers) {
    $c = CheckOf $L.path
    if (-not $c.ok -or $c.line -ne $expLine) { Say ("-Check of {0} after the write is not the expected line (see the log)" -f $L.path); if (-not (RestoreAll $from)) { Done 5 "a launcher restore FAILED" }; Done 1 "the launchers this run wrote are restored; pin untouched" }
  }
  Say "both live launchers -Check ok"
} catch {
  Say ("ERROR: " + $_.Exception.Message)
  if ($script:edited) { if (-not (RestoreAll $from)) { Done 5 "a launcher restore FAILED after an error" } }
  Done 1 "stopped; the live launchers are as they were (pin untouched)"
}
$ErrorActionPreference = 'Continue'

# ---- 5. report
$snapNote = ''
try {
  $raw = [IO.File]::ReadAllText($sums)
  $agree = @($launchers | Where-Object { $raw -match ('(?m)^' + (Sha64 $_.path) + '  ' + [regex]::Escape($_.snap) + '$') }).Count
  $snapNote = $(if ($agree -eq 2) { 'both live launchers = the committed snapshot (kalshi_watch''s launcher check is quiet again)' } else { "the committed snapshot no longer matches $(2 - $agree) live launcher(s): kalshi_watch alarms every 30 min until results\live_launcher_snapshot\ is committed to match" })
} catch { $snapNote = 'snapshot not compared: ' + $_.Exception.Message }
Say $snapNote
Say (PinState)
if ($Revert) { Done 0 "REVERTED: both live launchers pass --hedge-odds-mult 1.25 again (the 11-10 bytes). pin was NOT restarted: it takes 1.25 at its next start (/approve pinrestart sooner). Commit the 11-10 snapshot back (see REVERT in this script's header)." }
Done 0 "DONE: both live launchers pass --hedge-odds-mult 1.5 (v-oddsmult15). pin was NOT restarted: the running pin keeps 1.25 until its next start (its --minutes run end -> watch_bot, or /approve pinrestart while flat); confirm then that the newest pinrun-live-*.jsonl start record carries hedge_odds_mult 1.5."
