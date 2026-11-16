# pin_hedge5live.ps1 -- 2026-11-16. v-hedge5live: pin's 5 Hz belief SENDS the hedge (--index-5hz shadow -> hedge).
# Operator 11-10: "Why would being faster need to be a shadow? If it's faster it can react quicker with more info";
# 11-16: "We don't need to wait all the way til 12-15 for everything".
# hedge5-read run early (11-16, 5.6 days of shadow since 11-10 07:35 ET; scratchpad reads_now\reads_hedge5.py): 5
#   positions where the 5 Hz belief crossed 0.40 before the 1 Hz one (272-355 ms ahead), all would_send; 0 false
#   alarms; 2 flips saved +$5.78 (ETH 11-15 11:45 AM 80c vs the real 90.4c, BTC hourly 11-15 10 PM 51c vs 55c); 3
#   won-bet markets where both feeds crossed would have paid $45.76 less (ETH 11-14 11:15 PM: 15c at tau 4 instead of
#   20-26c a second later). +$51.54 total, +$9.20/day; with the measured 1.77c live slip ~+$36.7. ETH 11-14 carries 86%.
# WHAT "hedge" DOES (v-hedge5, build 0925w and later): BTC ETH SOL XRP DOGE (and BTCD) also read the settlement index
#   5x a second; the belief hedge fires the first time EITHER the 5 Hz or the 1 Hz belief is under the line (0.40),
#   hedge_alarm by_5hz true when the 5 Hz one was first. ZEC BNB NEAR HYPE have no 5 Hz index: unchanged.
# ARGV ONLY: same build C:\kals-live-0925x (pinrun 3a19b0019e9c, pintake b3c7bb48abb5, ordercli f40c43061ea3); in
#   BOTH live launchers ONE argv line changes, with one v-hedge5live comment line above it:
#     "--index-5hz", "shadow",   ->   "--index-5hz", "hedge",
#   Everything else stays (v-railany's --boost-rail any, v-undo1114's flags, --hedge-odds-mult 1.5 ...).
# Derived from results\pin_railany.ps1 (itself pin_undo1114.ps1, rehearsed 11-14): the same preconditions, checked
#   copies, -Check, full-argv --selftest (1632 ok / 0 FAIL pinned; a different count REFUSES before any live write),
#   backups, hash-checked writes and restores.
# HOW TO RUN (on the server right after `git pull --ff-only`), as an ssh command of its own:
#     powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-repo\results\pin_hedge5live.ps1
#   PIN IS NEVER RESTARTED BY THIS SCRIPT. Then restart pin while FLAT (from SSH only via WMI):
#     Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = 'cmd /c "powershell
#       -NoProfile -ExecutionPolicy Bypass -File C:\kals-live-0925n\restart_bot.ps1 > C:\kals-repo\results\
#       pin_hedge5live_restart.out 2>&1"'; CurrentDirectory = 'C:\kals-live-0925n' }
#   A restart starts a new run, so the boost rail (v-railany) re-arms: the 1.5x boost is on again until the next boosted
#   loss.
# CONFIRM: the newest results\pinrun-live-*.jsonl start record carries index_5hz hedge (boost_rail any unchanged).
# TRACKING vs SHADOW: every hedge_alarm with by_5hz true is priced against the first pintraj second with the 1 Hz belief
#   under 0.40 at that row's hedge-side ask (flip: the saving; won with no 1 Hz crossing: the premium = a false alarm).
# REVERT: powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-repo\results\pin_hedge5live.ps1 -Revert, then
#   commit the v-railany launcher snapshot back.
# EXIT: 0 = both live launchers carry --index-5hz hedge and -Check clean (or already did); 1 = refused or restored;
#   5 = a person must look.
# Log: results\pin_hedge5live.out; self-test output: C:\kals-live-0925x\selftest\hedge5live_selftest.out / .err
param([switch]$Revert)
$log = 'C:\kals-repo\results\pin_hedge5live.out'
# Say writes to the console handle, NOT the output stream (a function's output stream is its return value)
function Say($m) { $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m; [Console]::Out.WriteLine($l); Add-Content -Path $log -Value $l }
function Done($code, $m) { if ($m) { Say $m }; Say ("EXIT {0}" -f $code); exit $code }

$py = 'C:\Python314\python.exe'
$build = 'C:\kals-live-0925x'
$codeSha = '3a19b0019e9c'
$pintakeSha = 'b3c7bb48abb5'
$ordercliSha = 'f40c43061ea3'
# the six modules the 0925x build did not patch (pin_0925x.ps1's pins)
$same = [ordered]@{ 'kauth.py' = 'efa79fa98e62'; 'livebook.py' = '64e520bdd46c'; 'engine.py' = '6877a74a7441';
  'pinxfer.py' = 'e8589ee03cf4'; 'downtime.py' = '2da80f11dacb'; 'pinflat.py' = 'c2483aa10647' }
$nOkPinned = 1632    # PowerShell names are case-insensitive, so the count read from the run is $nOkSeen, never $nok
$nX = 17
$nH5 = 11
$nV = 120
$nCheapwin = 6
$versions = 'C:\kals-repo\results\VERSIONS.md'
$sums = 'C:\kals-repo\results\live_launcher_snapshot\SHA256SUMS.txt'
$pidFile = 'C:\kals-repo\results\pinrun-live.pid'
$pinLogs = 'C:\kals-repo\results\pinrun-live-*.jsonl'
$work = "$build\hedge5live"
# each live launcher, the snapshot it is a byte copy of, and its sha256 before (OLD) and after (NEW) this edit
$hand = @{ path = 'C:\kals-live-0925n\restart_bot.ps1'; snap = 'restart_bot_hand.ps1'; what = 'the hand launcher';
  old = '1fd7261d871cb30c8617d91c9bf973af36a5320665524d359a27a03d6ba355e9';
  new = '7569550a9dd1a415bfe928a8a1732a957aab6b1c0b7beaeab3174e9d2ee224a1' }
$keep = @{ path = 'C:\kals-repo\restart_bot.ps1'; snap = 'restart_bot_repo.ps1'; what = 'the keep-alive launcher (watch_bot.ps1 restarts pin through it)';
  old = 'aacaa1f0741f2834cf6813711d1671ff26d32f10cb34e3e3ed0b141dc9b5ced9';
  new = 'c029a6df5589a503cc8972cf35ec695da3cad92ec0a733bb2c1e55774963232d' }
$launchers = @($hand, $keep)          # written in this order: the keep-alive launcher last
# THE EDITS: @(the old line, the v-hedge5live comment line put above the new line, the new line or $null = the old line
# is replaced by the comment line alone). Each line is matched as a WHOLE line, exactly once. The snapshot committed
# with this script (the NEW hashes above) was made 11-14 by applying exactly these definitions -- $edits, EolAt,
# LineHits and Forward, read from this file's own syntax tree, never retyped -- to the 11-14 snapshot (the OLD hashes):
# change one byte of them and step 2 refuses.
$edits = @(,@(
  '    "--index-5hz", "shadow",',
  '    # v-hedge5live 2026-11-16 (operator 11-16: "We don''t need to wait all the way til 12-15 for everything"; 11-10: "Why would being faster need to be a shadow?"): the 5 Hz belief now SENDS the hedge, --index-5hz shadow -> hedge (same build, flag choice off/shadow/hedge). hedge5-read run early 11-16 (5.6 days of shadow): 5 positions where the 5 Hz belief crossed 0.40 first (272-355 ms ahead), 0 false alarms; 2 flips saved +$5.78 (ETH 11:45 AM 80c vs 90.4c, BTC hourly 10 PM 51c vs 55c); 3 won-bet markets where both crossed would have paid $45.76 less (ETH 11-14: 15c at tau 4 instead of 20-26c a second later); +$51.54 total, +$9.20/day (86% from ETH 11-14). Tracking vs shadow: hedge_alarm by_5hz true records, priced against the first 1 Hz crossing in pintraj (the read''s HOW). Revert: results\pin_hedge5live.ps1 -Revert, or "hedge" back to "shadow" in the line under this one.',
  '    "--index-5hz", "hedge",'))
# the -Check line's flag changes, in order (old -> new; a leading and a trailing space keep each token whole)
$checkPairs = @(,@(' --index-5hz shadow ', ' --index-5hz hedge '))
# what the new -Check line must carry (and the old one must not), and what must be gone from it
$mustNew = @(' --index-5hz hedge ', ' --boost-rail any ', ' --wrongside-rise-c 0 ', ' --extra-coin 1 ', ' --late-extra 1 ',
  ' --bank-brake 3.00 ', ' --hedge-odds-mult 1.5 ', ' --band99-max-tau 30 ', ' --hedge-jump-shadow 6 ', ' --hedge-belief 0.40 ')
$mustGone = @(' --index-5hz shadow ', ' --boost-rail off ', '--cheap-window', '--hedge-jump-max')

function Sha64($p) { try { (Get-FileHash -Algorithm SHA256 -Path $p -ErrorAction Stop).Hash.ToLower() } catch { $null } }
function Sha12($p) { $h = Sha64 $p; if ($h) { $h.Substring(0, 12) } else { $null } }
# a native command's stderr must never become a terminating error (PowerShell 5.1 + Stop)
function Native($exe, [string[]]$argv) { $ErrorActionPreference = 'Continue'; $o = & $exe @argv 2>&1 | Out-String; return @($o, $LASTEXITCODE) }
function HasBom($p) { $b = [IO.File]::ReadAllBytes($p); return ($b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF) }
function WriteText($p, $t, $bom) { [IO.File]::WriteAllText($p, $t, (New-Object System.Text.UTF8Encoding($bom))) }
function Count($t, $s) { ([regex]::Matches($t, [regex]::Escape($s))).Count }
# the line end that starts at index $j of $t ("`r`n" or "`n"), or $null
function EolAt($t, $j) {
  if ($t.Length -ge $j + 2 -and $t.Substring($j, 2) -ceq "`r`n") { return "`r`n" }
  if ($t.Length -ge $j + 1 -and $t.Substring($j, 1) -ceq "`n") { return "`n" }
  return $null
}
# every index where $line stands as a WHOLE line of $t (after a line feed or at the start, before a line end)
function LineHits($t, $line) {
  $rx = '(?<=\n|^)' + [regex]::Escape($line) + '(?=\r?\n)'
  @([regex]::Matches($t, $rx) | ForEach-Object { $_.Index })
}
# the forward edit on the raw text: each old line (once, a whole line) -> its comment + the old line's own line end +
# its new line (or the comment alone). Returns $null when the text is not exactly the expected shape.
function Forward($t) {
  if ($t -match 'v-hedge5live') { return $null }
  foreach ($e in $edits) {
    if (@(LineHits $t $e[0]).Count -ne 1) { return $null }
    if (@(LineHits $t $e[1]).Count -ne 0) { return $null }
    if ($null -ne $e[2] -and @(LineHits $t $e[2]).Count -ne 0) { return $null }
  }
  foreach ($e in $edits) {
    $hits = @(LineHits $t $e[0])
    if ($hits.Count -ne 1) { return $null }
    $i = $hits[0]
    $j = $i + $e[0].Length
    $nl = EolAt $t $j
    if (-not $nl) { return $null }
    $rep = $(if ($null -eq $e[2]) { $e[1] } else { $e[1] + $nl + $e[2] })
    $t = $t.Substring(0, $i) + $rep + $t.Substring($j)
  }
  return $t
}
# the reverse edit: each comment line (once, a whole line) and the new line under it (same line end) -> the old line;
# a comment that stands alone (the removed line) -> the old line
function Backward($t) {
  foreach ($e in $edits) {
    if (@(LineHits $t $e[0]).Count -ne 0) { return $null }
    if (@(LineHits $t $e[1]).Count -ne 1) { return $null }
  }
  foreach ($e in $edits) {
    $hits = @(LineHits $t $e[1])
    if ($hits.Count -ne 1) { return $null }
    $i = $hits[0]
    $j = $i + $e[1].Length
    $nl = EolAt $t $j
    if (-not $nl) { return $null }
    if ($null -eq $e[2]) { $t = $t.Substring(0, $i) + $e[0] + $t.Substring($j); continue }
    $k = $j + $nl.Length
    if ($t.Length -lt $k + $e[2].Length -or $t.Substring($k, $e[2].Length) -cne $e[2]) { return $null }
    $m = $k + $e[2].Length
    if ((EolAt $t $m) -cne $nl) { return $null }
    $t = $t.Substring(0, $i) + $e[0] + $t.Substring($m)
  }
  return $t
}
function ArgvOf($f) { @([IO.File]::ReadAllLines($f) | Where-Object { $_ -match '^\s*"--' } | ForEach-Object { $_.Trim().TrimEnd(',') }) }
# the argv-line change each edited launcher must show against its live file: these out (<=), these in (=>)
$argvOut = @($edits | ForEach-Object { $_[0].Trim().TrimEnd(',') })
$argvIn = @($edits | Where-Object { $null -ne $_[2] } | ForEach-Object { $_[2].Trim().TrimEnd(',') })
# the -Check line: "  <python> -u <build>\research\pinrun.py <flags>", and the hashes the launcher printed
$pinrunRx = [regex]::Escape("$build\research\pinrun.py")
function CheckOf($f) {
  $c = (Native 'powershell' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $f, '-Check'))[0]
  Add-Content -Path $log -Value $c
  $line = @($c -split "`r?`n" | Where-Object { $_ -match $pinrunRx -and $_ -match '\s--live\s' })
  $ok = ($c -match "code_sha $codeSha") -and ($c -match ('pintake\.py sha256\[:12\] ' + $pintakeSha)) -and
        ($c -match ('ordercli\.py sha256\[:12\] ' + $ordercliSha)) -and ($c -match 'CHECK ONLY') -and ($c -notmatch 'ABORTING') -and ($line.Count -eq 1)
  return @{ ok = $ok; line = $(if ($line.Count -eq 1) { $line[0].Trim() + ' ' } else { '' }); text = $c }
}
# a -Check line carries v-hedge5live (every $mustNew once, no $mustGone)
function LineIsNew($l) {
  foreach ($s in $mustNew) { if ((Count $l $s) -ne 1) { return $false } }
  foreach ($s in $mustGone) { if ((Count $l $s) -ne 0) { return $false } }
  return $true
}
# a -Check line carries the pre-hedge5live flag (--index-5hz shadow once, never hedge)
function LineIsOld($l) {
  foreach ($p in $checkPairs) { if ((Count $l $p[0]) -ne 1) { return $false } }
  foreach ($s in @(' --index-5hz hedge ')) { if ((Count $l $s) -ne 0) { return $false } }
  return $true
}
function RestartRunning {
  @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -and $_.CommandLine -match 'restart_bot\.ps1' -and $_.CommandLine -notmatch '\s-Check' -and $_.ProcessId -ne $PID })
}
# every module of the build at the hashes it must have; returns the first mismatch or $null
function BuildBad {
  foreach ($m in @(@('pinrun.py', $codeSha), @('ordercli.py', $ordercliSha), @('pintake.py', $pintakeSha))) {
    $g = Sha12 "$build\research\$($m[0])"
    if ($g -ne $m[1]) { return ("$build\research\$($m[0]) is {0}, expected {1}" -f $(if ($g) { $g } else { 'missing' }), $m[1]) }
  }
  foreach ($k in $same.Keys) {
    $g = Sha12 "$build\research\$k"
    if ($g -ne $same[$k]) { return ("$build\research\$k is {0}, expected {1}" -f $(if ($g) { $g } else { 'missing' }), $same[$k]) }
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
    $fl = @()
    foreach ($n in @('index_5hz', 'boost_rail', 'extra_coin', 'late_extra', 'bank_brake', 'hedge_odds_mult', 'band99_max_tau', 'hedge_jump_shadow')) {
      $v = $null
      try { $v = $d.$n } catch {}
      $fl += ('{0} {1}' -f $n, $(if ($null -eq $v) { 'null' } else { (@($v) -join ',') }))
    }
    return ("pin pid {0} (alive: {1}) started {2} on code_sha {3} ({4}); its --minutes {5} run ends about {6:yyyy-MM-dd HH:mm}Z, then watch_bot restarts it through C:\kals-repo\restart_bot.ps1" -f $ppid, $alive, $d.t, $d.code_sha, ($fl -join ', '), $d.minutes, $end)
  } catch { return ("pin state not read: " + $_.Exception.Message) }
}

Say ("start" + $(if ($Revert) { ' (-Revert)' } else { '' }))
$ErrorActionPreference = 'Stop'

# ================================================================== -Revert: both launchers back to their pre-hedge5live (v-railany) bytes
if ($Revert) {
  $from = @{}; $to = @{}
  foreach ($L in $launchers) { $from[$L.path] = $L.new; $to[$L.path] = $L.old }
  try {
    $bad = BuildBad
    if ($bad) { Done 1 ("REFUSED: $build is not the 0925x build the launchers start: " + $bad + "; nothing changed") }
    $todo = @(); $already = @(); $newText = @{}
    foreach ($L in $launchers) {
      $h = Sha64 $L.path
      if ($h -eq $L.old) { $already += $L; continue }
      if ($h -ne $L.new) { Done 1 ("REFUSED: {0} ({1}) has sha256 {2}, neither this script's NEW {3} nor OLD {4}: it changed since -- look before anything is edited; nothing changed" -f $L.path, $L.what, $(if ($h) { $h } else { 'missing' }), $L.new.Substring(0, 12), $L.old.Substring(0, 12)) }
      $n = Backward ([IO.File]::ReadAllText($L.path))
      if ($null -eq $n) { Done 1 ("REFUSED: {0}: the v-hedge5live line is not in the expected shape; revert by hand (see REVERT in this script's header); nothing changed" -f $L.path) }
      $newText[$L.path] = $n
      $todo += $L
    }
    foreach ($L in $already) { Say ("{0} is ALREADY the pre-hedge5live (v-railany) bytes ({1}): left as it is" -f $L.path, $L.old.Substring(0, 12)) }
    if (-not $todo.Count) { Done 0 "NOTHING TO DO: both live launchers are already the pre-hedge5live (v-railany) bytes" }
    $busy = @(RestartRunning)
    if ($busy.Count -gt 0) { Done 1 ("REFUSED: a restart_bot.ps1 is running right now (pid {0}): it reads the launcher; run this again in a minute or two; nothing changed" -f (($busy | ForEach-Object { $_.ProcessId }) -join ', ')) }
    $dir = "$work\revert"
    New-Item -ItemType Directory -Force $dir | Out-Null
    $copies = @{}
    foreach ($L in $todo) {
      $cp = Join-Path $dir $L.snap
      WriteText $cp ($newText[$L.path]) (HasBom $L.path)
      if ((Sha64 $cp) -ne $L.old) { Done 1 ("REFUSED: the reverted copy {0} has sha256 {1}, not the pre-hedge5live {2}; live launchers untouched" -f $cp, (Sha64 $cp), $L.old) }
      $c = CheckOf $cp
      if (-not $c.ok -or -not (LineIsOld $c.line)) { Done 1 ("REFUSED: -Check of the reverted copy {0} does not show the pre-hedge5live flag on $build (see the log); live launchers untouched" -f $cp) }
      $copies[$L.path] = $cp
    }
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    foreach ($L in $todo) {
      $bak = $L.path + '.before-hedge5live-revert-' + $stamp
      Copy-Item $L.path $bak -ErrorAction Stop
      if ((Sha64 $bak) -ne $L.new) { Done 1 ("REFUSED: the backup {0} is not a byte copy of {1}; nothing changed" -f $bak, $L.path) }
      $baks[$L.path] = $bak
    }
    $busy = @(RestartRunning)
    if ($busy.Count -gt 0) { Done 1 ("REFUSED: a restart_bot.ps1 started meanwhile (pid {0}); nothing changed -- run this again in a minute or two" -f (($busy | ForEach-Object { $_.ProcessId }) -join ', ')) }
    foreach ($L in $todo) {
      $script:edited = $true
      Copy-Item ($copies[$L.path]) $L.path -Force -ErrorAction Stop
      if ((Sha64 $L.path) -ne $L.old) { if (-not (RestoreAll $from)) { Done 5 "a launcher restore FAILED" }; Done 1 ("{0} was not the pre-hedge5live bytes after the write; restored" -f $L.path) }
      Say ("REVERTED {0} ({1}) = {2} (sha256 {3}; the v-hedge5live bytes kept as {4})" -f $L.path, $L.what, $copies[$L.path], $L.old.Substring(0, 12), $baks[$L.path])
    }
    foreach ($L in $launchers) {
      $c = CheckOf $L.path
      if (-not $c.ok -or -not (LineIsOld $c.line)) { Say ("-Check of {0} after the revert does not show the pre-hedge5live flag (see the log)" -f $L.path); if (-not (RestoreAll $from)) { Done 5 "a launcher restore FAILED" }; Done 1 "the launchers this run wrote are back to the v-hedge5live bytes; pin untouched" }
    }
  } catch {
    Say ("ERROR: " + $_.Exception.Message)
    if ($script:edited) { if (-not (RestoreAll $from)) { Done 5 "a launcher restore FAILED after an error" } }
    Done 1 "stopped; the live launchers are as they were (pin untouched)"
  }
  $ErrorActionPreference = 'Continue'
  Say (PinState)
  Done 0 "REVERTED: both live launchers pass --index-5hz shadow again (the v-railany bytes). pin was NOT restarted: it takes it at its next start. Commit the previous launcher snapshot back (see REVERT in this script's header), or kalshi_watch alarms every 30 min."
}

# ================================================================== forward
$from = @{}; $to = @{}
foreach ($L in $launchers) { $from[$L.path] = $L.old; $to[$L.path] = $L.new }
try {
  # ---- 1. preconditions
  $bad = BuildBad
  if ($bad) { Done 1 ("REFUSED: $build is not the live 0925x build: " + $bad + "; nothing changed") }
  $vtxt = [IO.File]::ReadAllText($versions)
  if ($vtxt -notmatch '# v-hedge5live ') { Done 1 "REFUSED: $versions has no v-hedge5live entry (git pull --ff-only first); nothing changed" }
  $raw = [IO.File]::ReadAllText($sums)
  if ($raw.Contains("`r")) { Done 1 "REFUSED: $sums has CR line ends (it must be LF, sha256sum format); nothing changed" }
  foreach ($L in $launchers) {
    $rows = @($raw -split "`n" | Where-Object { $_ -match ('^([0-9a-f]{64})  ' + [regex]::Escape($L.snap) + '$') })
    if ($rows.Count -ne 1) { Done 1 ("REFUSED: $sums names {0} {1} times (expected once); nothing changed" -f $L.snap, $rows.Count) }
    $h = $rows[0].Substring(0, 64)
    if ($h -ne $L.new) { Done 1 ("REFUSED: $sums gives {0} as {1}, not this script's NEW {2} (pull the v-hedge5live commit; do not edit the hashes); nothing changed" -f $L.snap, $h.Substring(0, 12), $L.new.Substring(0, 12)) }
  }
  # each launcher is either still at the start bytes (to do) or already at the target bytes (a run that stopped half way
  # between the two writes: left as it is); anything else is refused
  $todo = @(); $already = @(); $newText = @{}
  foreach ($L in $launchers) {
    $h = Sha64 $L.path
    if ($h -eq $L.new) { $already += $L; continue }
    if ($h -ne $L.old) { Done 1 ("REFUSED: {0} ({1}) has sha256 {2}, expected exactly {3} (the committed v-railany snapshot): it changed since this script was written -- look before anything is edited; nothing changed" -f $L.path, $L.what, $(if ($h) { $h } else { 'missing' }), $L.old) }
    $n = Forward ([IO.File]::ReadAllText($L.path))
    if ($null -eq $n) { Done 1 ("REFUSED: {0}: the edited line is not in the expected shape (each once, a whole line; no v-hedge5live text); nothing changed" -f $L.path) }
    $newText[$L.path] = $n
    $todo += $L
  }
  foreach ($L in $already) { Say ("{0} is ALREADY the v-hedge5live bytes ({1}): left as it is" -f $L.path, $L.new.Substring(0, 12)) }
  if (-not $todo.Count) {
    foreach ($L in $launchers) {
      $c = CheckOf $L.path
      if (-not $c.ok -or -not (LineIsNew $c.line)) { Done 5 ("BOTH live launchers are the v-hedge5live bytes but -Check of {0} is not clean (see the log) -- pin's next restart would ABORT; a person must look" -f $L.path) }
    }
    Say (PinState)
    Done 0 "NOTHING TO DO: both live launchers are already the v-hedge5live bytes, the build is intact and both -Check clean"
  }
  $busy = @(RestartRunning)   # @(): one process would otherwise unroll to a bare object whose .Count is $null on 5.1
  if ($busy.Count -gt 0) { Done 1 ("REFUSED: a restart_bot.ps1 is running right now (pid {0}): it reads the launcher; run this again in a minute or two; nothing changed" -f (($busy | ForEach-Object { $_.ProcessId }) -join ', ')) }
  try { $gs = Native 'git' @('-C', 'C:\kals-repo', 'status', '--porcelain', '--', 'restart_bot.ps1') } catch { $gs = @(('git not available: ' + $_.Exception.Message), -1) }
  Say ("git status of the keep-alive launcher (expected ' M restart_bot.ps1': its live edits are uncommitted): [" + ([string]$gs[0]).Trim() + "]")
  Say ("preconditions ok: $build is $codeSha / $pintakeSha / $ordercliSha (+ the six other modules); VERSIONS.md has v-hedge5live; the committed snapshot names the NEW bytes; to edit: {0}" -f (($todo | ForEach-Object { $_.path }) -join ', '))
  Say (PinState)

  # ---- 2. the edited launchers as COPIES first ($copies: the file each launcher will be -- a checked copy, or the live
  # file itself when it is already there), and their -Check
  New-Item -ItemType Directory -Force $work | Out-Null
  $copies = @{}
  foreach ($L in $already) { $copies[$L.path] = $L.path }
  foreach ($L in $todo) {
    $cp = Join-Path $work $L.snap
    WriteText $cp ($newText[$L.path]) (HasBom $L.path)
    if ((Sha64 $cp) -ne $L.new) { Done 1 ("REFUSED: the edited copy {0} has sha256 {1}, not the expected {2} (the committed snapshot); live launchers untouched" -f $cp, (Sha64 $cp), $L.new) }
    $errs = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($cp, [ref]$null, [ref]$errs)
    if ($errs.Count) { Done 1 ("REFUSED: the edited copy {0} has {1} parse errors; live launchers untouched" -f $cp, $errs.Count) }
    $copies[$L.path] = $cp
  }
  $dif = @(Compare-Object (ArgvOf ($copies[$hand.path])) (ArgvOf ($copies[$keep.path])))
  if ($dif.Count) { foreach ($d in $dif) { Say ("ARGV DIFFERS: {0} {1}" -f $d.SideIndicator, $d.InputObject) }; Done 1 "REFUSED: the two edited launchers' argv lines differ; live launchers untouched" }
  $wantTxt = ((@($argvOut | ForEach-Object { '<= ' + $_ }) + @($argvIn | ForEach-Object { '=> ' + $_ })) | Sort-Object) -join ' ; '
  foreach ($L in $todo) {
    $dd = @(Compare-Object (ArgvOf $L.path) (ArgvOf ($copies[$L.path])))
    $ddTxt = (@($dd | ForEach-Object { $_.SideIndicator + ' ' + $_.InputObject }) | Sort-Object) -join ' ; '
    if ($ddTxt -cne $wantTxt) { Done 1 ("REFUSED: {0}: the argv change is not exactly the one line out and the one in (live vs copy: {1}); live launchers untouched" -f $L.path, $ddTxt) }
  }
  Say ("edited copies in $work are the expected bytes, parse, both launchers' argv lines match, and each edit is exactly: " + $wantTxt)
  # the expected -Check line = a still-to-do live launcher's own -Check line with only the one flag change; every
  # launcher's file-to-be must print exactly it
  $cLive = CheckOf ($todo[0].path)
  if (-not $cLive.ok -or -not (LineIsOld $cLive.line)) { Done 1 ("REFUSED: -Check of the live {0} did not show $build with --index-5hz shadow once (the baseline line; see the log); nothing changed" -f $todo[0].path) }
  $expLine = $cLive.line
  foreach ($p in $checkPairs) { $expLine = $expLine.Replace($p[0], $p[1]) }
  if (-not (LineIsNew $expLine)) { Done 1 "REFUSED: the expected -Check line does not carry v-hedge5live (see the log); nothing changed" }
  $cNew = $null
  foreach ($L in $launchers) {
    $cc = CheckOf ($copies[$L.path])
    if (-not $cc.ok -or $cc.line -cne $expLine) { Done 1 ("REFUSED: -Check of {0} is not the live -Check line with only the one flag change (see the log); live launchers untouched" -f $copies[$L.path]) }
    if (-not $cNew) { $cNew = $cc }
  }
  Say ("-Check of both edited launchers ok: the live argv with only the one flag change; code_sha $codeSha, ordercli $ordercliSha, pintake $pintakeSha")

  # ---- 3. the full new argv self-test
  Copy-Item ($copies[$hand.path]) "$build\restart_bot.ps1" -Force    # the build's own self-test reads its launcher
  $argv = ($cNew.line.Trim() -split '\s+')
  $ix = [array]::IndexOf($argv, ($argv | Where-Object { $_ -like '*pinrun.py' } | Select-Object -First 1))
  $targs = @('-u', "$build\research\pinrun.py") + $argv[($ix + 1)..($argv.Length - 1)] + @('--selftest')
  if (-not (LineIsNew (' ' + ($targs -join ' ') + ' '))) { Done 1 "REFUSED: the self-test argv does not carry v-hedge5live; live launchers untouched" }
  Say ("self-test: " + ($targs -join ' '))
  New-Item -ItemType Directory -Force "$build\selftest" | Out-Null
  $so0 = "$build\selftest\hedge5live_selftest.out"
  $p = Start-Process -FilePath $py -ArgumentList $targs -RedirectStandardOutput $so0 -RedirectStandardError "$build\selftest\hedge5live_selftest.err" -NoNewWindow -PassThru
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
  Say ("self-test PASSED ({0} ok = the pinned {1}, 0 FAIL; {2} v-0925x, {3} v-hedge5, {4} v-0925v, {5} v-cheapwin) with the full v-hedge5live argv on $build" -f $nOkSeen, $nOkPinned, $nx9, $nh, $nvv, $ncw)

  # ---- 4. the live launchers: backed up (checked), replaced by the checked copies (checked), -Check
  $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  foreach ($L in $todo) {
    if ((Sha64 $L.path) -ne $L.old) { Done 1 ("REFUSED: {0} changed while this script ran; nothing changed" -f $L.path) }
    $bak = $L.path + '.before-hedge5live-' + $stamp
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
    $c = CheckOf $L.path
    if (-not $c.ok -or $c.line -cne $expLine) { Say ("-Check of {0} after the write is not the expected line (see the log)" -f $L.path); if (-not (RestoreAll $from)) { Done 5 "a launcher restore FAILED" }; Done 1 "the launchers this run wrote are restored; pin untouched" }
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
Done 0 "DONE: both live launchers pass --index-5hz hedge (v-hedge5live; everything else as v-railany, the same build $build). pin was NOT restarted: the running pin keeps --index-5hz shadow until its next start (restart while flat: HOW TO RUN in this script's header); confirm then that the newest pinrun-live-*.jsonl start record carries index_5hz hedge."
