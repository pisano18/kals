# pin_undo1114.ps1 -- 2026-11-14. v-undo1114: UNDO four pin rules the 11-14 retrospective found made LESS money than
# never changing (an analyst and a skeptic per change, each from pin's raw live logs, losses, hedges and fees in;
# scratchpad maxpower\retro_synthesis\RETRO.md). The operator 11-14: "do what makes money"; his standing rule: no
# break-even safety filters. ARGV ONLY: the build does not move (C:\kals-live-0925x, pinrun 3a19b0019e9c, pintake
# b3c7bb48abb5, ordercli f40c43061ea3), nothing is copied or patched, and PIN IS NEVER RESTARTED BY THIS SCRIPT.
# WHAT IT DOES: in BOTH live launchers, six argv lines (each exactly once, a line of its own), each with ONE v-undo1114
#   comment line put above it (the comment takes the edited line's own line end, so the hand launcher's mixed CRLF / LF
#   stays as it is):
#     "--wrongside-rise-c", "1.0",                         -> "--wrongside-rise-c", "0",      WS off (pinrun: 0 = off)
#     "--ws-later-fall-c", "10", "--hedge-jump-max", "8",  -> "--ws-later-fall-c", "10",      B's 8 sd jump cap out
#     "--cheap-window", "6", "10", "0.98",                 -> (the comment line only)         K off (no flag = off)
#     "--extra-coin", "0",                                 -> "--extra-coin", "1",            \
#     "--late-extra", "0",                                 -> "--late-extra", "1",             > M: call B undone
#     "--bank-brake", "4.5",                               -> "--bank-brake", "3.00",         /  (the pre-11-08 values)
#   Every other byte stays: --hedge-odds-mult 1.5, --band99-max-tau 30, --hedge-jump-shadow 6 (the jump hedge itself
#   stays SHADOW), --ws-later-fall-c 10 and every other flag are untouched.
#   WS  --wrongside-rise-c (v-wrongside, LS20, live since 10-27): a FIRST buy in a 15-minute market with the index across
#       the strike from our side needed our side's mid UP >= 1c over the last 5 s, else the market was skipped for the
#       close. Retro: -$35.14 (skeptic) to -$56.45 (analyst) against never having it; all 16 markets it skipped WON.
#   B   --hedge-jump-max 8 (v-jumpcap8, 11-01): the jump hedge fired only for jumps under 8 sd. -$25.12 while the jump
#       hedge was live (11-01..11-08); $0/day now (the jump hedge is in shadow; its jump_shadow records keep each
#       alarm's jump_sd, so the cap stays computable).
#   K   --cheap-window 6 10 0.98 (v-cheapwin, 11-08): a FIRST buy under 98c in a market closing 06:00-10:00 ET was
#       refused and the market skipped for the close. -$27.98 to -$42.73 in 6.16 days; its pre-registered 11-21 bar
#       (keep if K net >= $0) fails today.
#   M   call B (11-08): --extra-coin 0 --late-extra 0 --bank-brake 4.5 in place of 1 / 1 / 3.00. --extra-coin 1: a coin
#       not yet held in a close may spend one more SIZE of budget; --late-extra 1: inside --late-extra-tau (15 s) any
#       market may (the two SHARE one extra bet, never two); --bank-brake 3.00 keeps SIZE = floor(bank / (brake x
#       (2 + 1) x 0.98)) = floor(bank / 8.82), what 4.5 x 2 x 0.98 gave (pinrun's own size_for_bank: identical at every
#       whole-dollar bank $100-$20,000). The close budget goes back from 2 x SIZE to 3 x SIZE (a new coin, or the last
#       15 s); the loss abort, the loss cap, the stake cap and the take cap do not move. -$57.62 in 6.16 days
#       (-$9.35/day; all 3 buys it held back won); expected +$4-6/day back. The worst close grows from 2 to 3 bets
#       ($876 -> $1,314 at today's SIZE 447, bank $3,948).
# HOW TO RUN (on the server, RIGHT AFTER `git pull --ff-only` brings this script, VERSIONS.md's v-undo1114 entry and the
#   new results\live_launcher_snapshot\ -- from that pull until this has run, kalshi_watch's 30-minute launcher check
#   alarms, because the committed snapshot already has the undo; that alarm is this deploy, not a fault):
#     powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-repo\results\pin_undo1114.ps1
#   Run it as an ssh command of its own (the restart guard refuses while ANY process's command line names
#   restart_bot.ps1 without -Check). It runs in the foreground, about 1-3 minutes (most of it the self-test). A dropped
#   SSH session before step 4 changes no launcher; step 4 itself is two file copies, and a rerun finishes a half-done one.
# STEPS (nothing before step 4 touches a live launcher; pin itself is never touched):
#   1. refuse, "nothing changed", unless: C:\kals-live-0925x is exactly pinrun 3a19b0019e9c / pintake b3c7bb48abb5 /
#      ordercli f40c43061ea3 and the six other modules at their pinned hashes; VERSIONS.md carries the v-undo1114 entry;
#      the repo's SHA256SUMS.txt (LF) names exactly this script's NEW hash for both snapshots; each live launcher's
#      sha256 is EXACTLY its OLD hash = the snapshot committed before this one (f089ee1, 11-14: hand
#      394d82b4af54, repo 1aef96571579 -- the v-0925x bytes pin has run on since 11-14 13:11 ET); in each, every edited
#      line is there once, on a line of its own, and none of the new lines or v-undo1114 text is; no restart_bot.ps1 is
#      running right now. A launcher that is ALREADY the NEW bytes (a run that stopped between its two writes) is left as
#      it is and only the other one is edited; both already NEW = "NOTHING TO DO" (build and both -Checks verified),
#      exit 0. Any third state is refused.
#   2. both edited launchers as COPIES (C:\kals-live-0925x\undo1114\): each copy's sha256 must be the NEW hash
#      (byte-exact = the committed snapshot); parse-check; the two copies' argv lines match; each differs from its live
#      launcher's argv lines by exactly the six old lines out and the five new lines in; the -Check line of EACH copy
#      must be a live launcher's -Check line with exactly the six flag changes (" --wrongside-rise-c 1.0 " -> " 0 ",
#      " --hedge-jump-max 8" out, " --cheap-window 6 10 0.98" out, --extra-coin / --late-extra 0 -> 1, --bank-brake
#      4.5 -> 3.00) and nothing else, and show code_sha 3a19b0019e9c, pintake b3c7bb48abb5, ordercli f40c43061ea3.
#   3. the FULL new argv (from that -Check) + --selftest on C:\kals-live-0925x at BelowNormal priority, at most 10
#      minutes: SELF-TEST PASSED, 0 FAIL and EXACTLY 1632 ok lines (17 v-0925x, 11 v-hedge5, 120 v-0925v, 6 v-cheapwin
#      among them) -- the 0925x deploy's count, measured 11-14 on a byte copy of the build with this new argv and with
#      the live one (1632 both). pin runs this same self-test at its next start and refuses to trade on a FAIL, so it is
#      run here first. (The build's own restart_bot.ps1, which that self-test reads, is set to the new hand copy first,
#      as pin_0925x.ps1 did.)
#   4. back up both live launchers (.before-undo1114-<stamp>, hash-checked = OLD), write the checked copies over them --
#      the hand launcher first, the keep-alive one (watch_bot's) last -- each hash-checked = NEW, then -Check both live
#      launchers (the same expected line as step 2); any failure restores both (hash-checked = OLD) and stops.
#   5. report: the live launchers now equal the committed snapshot (kalshi_watch quiet again), pin's pid, run end and
#      the running flags. NO restart.
# EXIT: 0 = both live launchers carry the undo and -Check clean, or already did (pin not restarted; the undo is live
#   from its next start); 1 = refused or restored, the live launchers are as they were (verified); 5 = a person must
#   look (a launcher could not be restored to its exact pre-edit bytes, or both are the NEW bytes but a -Check fails:
#   pin's next restart would abort -- the log names it).
# LIVE FROM pin's next start: its --minutes 4320 run (started 2026-11-14 18:11:41Z) ends about 2026-11-17 18:11Z
#   (13:11 ET) and watch_bot restarts it through C:\kals-repo\restart_bot.ps1. Sooner = more money (M alone is worth
#   ~$4-6/day): a restart while pin is FLAT -- the operator's phone /approve pinrestart, or on the server, from SSH only
#   via WMI:
#     Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = 'cmd /c "powershell
#       -NoProfile -ExecutionPolicy Bypass -File C:\kals-live-0925n\restart_bot.ps1 > C:\kals-repo\results\
#       pin_undo1114_restart.out 2>&1"'; CurrentDirectory = 'C:\kals-live-0925n' }
#   restart_bot refuses by itself while pin holds a bet (pinflat) and checks the build's hashes before it stops anything.
# CONFIRM (after that start): the newest results\pinrun-live-*.jsonl start record carries extra_coin 1.0, late_extra
#   1.0, bank_brake 3.0, cheap_window null, wrongside_rise_c 0.0, hedge_jump_max null, and still hedge_odds_mult 1.5,
#   band99_max_tau 30, hedge_jump_shadow 6.0, ws_later_fall_c 10.0; the autosize SIZE is the same as before at the same
#   bank; no refused record with gate wrong_side or cheap_window appears.
# TRACKING vs KEEPING EACH RULE (READS_DUE undo-M-read, undo-K-read, undo-WS-read, all due 12-05), from records pin
#   writes with the rules off: K = first buys (no earlier fill in that market this close) under 98c in markets closing
#   06:00-10:00 ET (the ticker's own ET label, or t + tau), hourly ladder included; WS = first buys in a 15-minute
#   market whose signal has spot_wrong true and mid_rise_c under 1.0 (the mids are kept while --ws-later-fall-c > 0:
#   keep A on, or WS can no longer be priced); M = per close, the contracts filled past 2 x SIZE (15-minute and hourly
#   fills together, SIZE from the autosize records; each signal's budget_left cross-checks it). Each such market's
#   whole money (all legs and hedges) at its result is what the rule would have changed.
# REVERT (all four together): powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-repo\results\pin_undo1114.ps1
#   -Revert  (refuses unless each live launcher is exactly the NEW bytes or already OLD; takes the six comment lines out
#   and the old lines back; refuses-and-restores unless each is then exactly its OLD hash and -Check shows the old
#   values; backups *.before-undo1114-revert-*). pin takes it at its next start. Then commit the previous launcher
#   snapshot back (results\live_launcher_snapshot\restart_bot_hand.ps1, restart_bot_repo.ps1, SHA256SUMS.txt and
#   README.md from the commit before v-undo1114), or kalshi_watch alarms every 30 minutes. One rule only: put its line(s)
#   back by hand in both launchers (each comment line says how) and refresh the snapshot.
# Log: results\pin_undo1114.out; the self-test's own output: C:\kals-live-0925x\selftest\undo1114_selftest.out / .err
param([switch]$Revert)
$log = 'C:\kals-repo\results\pin_undo1114.out'
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
$work = "$build\undo1114"
# each live launcher, the snapshot it is a byte copy of, and its sha256 before (OLD) and after (NEW) this edit
$hand = @{ path = 'C:\kals-live-0925n\restart_bot.ps1'; snap = 'restart_bot_hand.ps1'; what = 'the hand launcher';
  old = '394d82b4af542589f6a2091e7c9b873b97185d6e2ab6e25531f10fbf1fb56c51';
  new = 'b0624d6a011b5c2f96cf85996d2b3f0ef27b4147e5434edee0bda32070bff15c' }
$keep = @{ path = 'C:\kals-repo\restart_bot.ps1'; snap = 'restart_bot_repo.ps1'; what = 'the keep-alive launcher (watch_bot.ps1 restarts pin through it)';
  old = '1aef96571579dbd12bf53eb8ab526e7fa222b3b9c561db5bb33c7e97a81d75fb';
  new = '3310cc3d60556f7d8ffea43ae79aaf75da918198ce4e3c38bbdef330d460d5ed' }
$launchers = @($hand, $keep)          # written in this order: the keep-alive launcher last
# THE EDITS: @(the old line, the v-undo1114 comment line put above the new line, the new line or $null = the old line
# is replaced by the comment line alone). Each line is matched as a WHOLE line, exactly once. The snapshot committed
# with this script (the NEW hashes above) was made 11-14 by applying exactly these definitions -- $edits, EolAt,
# LineHits and Forward, read from this file's own syntax tree, never retyped -- to the 11-14 snapshot (the OLD hashes):
# change one byte of them and step 2 refuses.
$edits = @(
  @('    "--wrongside-rise-c", "1.0",',
    '    # v-undo1114 2026-11-14 (operator 11-14: "do what makes money"; his standing rule: no break-even safety filters): the wrong-side first-buy skip (v-wrongside, LS20) is OFF, 1.0 -> 0 (pinrun: 0 = off). The 11-14 retro (an analyst and a skeptic, each from the raw logs): -$35.14 to -$56.45 against never having it, 10-27..11-14; all 16 markets it skipped WON; 0 of 46 wrong-side first buys lost since it went live. Tracking vs keeping it: every first buy signal still carries spot_wrong and mid_rise_c (pin keeps the 5 s mids while --ws-later-fall-c is on), READS_DUE undo-WS-read (12-05). Revert: results\pin_undo1114.ps1 -Revert (all four undos), or this line out and "0" back to "1.0".',
    '    "--wrongside-rise-c", "0",'),
  @('    "--ws-later-fall-c", "10", "--hedge-jump-max", "8",',
    '    # v-undo1114 2026-11-14: --hedge-jump-max 8 is OUT of the line under this one (the 8 sd cap on the jump hedge, v-jumpcap8: -$25.12 against never having it while the jump hedge was live, 11-01..11-08; $0/day now). The jump hedge itself stays SHADOW (--hedge-jump-shadow 6 above); each jump_shadow record keeps its jump_sd, so what the cap would have done stays computable. --ws-later-fall-c 10 (v-wsfall10, $0: never fired) stays; it also keeps the mids the wrong-side tracking reads. Revert: this line out and the line under it back to --ws-later-fall-c 10 --hedge-jump-max 8.',
    '    "--ws-later-fall-c", "10",'),
  @('    "--cheap-window", "6", "10", "0.98",',
    '    # v-undo1114 2026-11-14: the cheap morning skip (K, v-cheapwin) is OFF -- its flag line (--cheap-window 6 10 0.98) is out of the list, and pinrun without the flag = off. The 11-14 retro: -$27.98 to -$42.73 in 6.16 days against never having it (ahead in only 28-33% of resamples); its pre-registered 11-21 bar (keep if K net >= $0) fails today; under the no break-even safety filters rule it goes. Tracking vs keeping it: every first buy signal / order carries the ticker (its ET close), tau and price; READS_DUE undo-K-read (12-05). Revert: this comment line back to the flag line, or results\pin_undo1114.ps1 -Revert.',
    $null),
  @('    "--extra-coin", "0",',
    '    # v-undo1114 2026-11-14: call B undone, 0 -> 1 (with --late-extra 1 and --bank-brake 3.00 below = the values live 10-30..11-08; the same SIZE): a coin not yet held in a close may again take a 3rd bet. The 11-14 retro: call B cost -$57.62 in 6.16 days (-$9.35/day; all 3 buys it held back won), expected +$4-6/day back; the worst close goes back from 2 to 3 bets ($876 -> $1,314 at SIZE 447). READS_DUE undo-M-read (12-05).',
    '    "--extra-coin", "1",'),
  @('    "--late-extra", "0",',
    '    # v-undo1114 2026-11-14: call B undone, 0 -> 1: inside --late-extra-tau (15 s) a close may again spend a 3rd bet (one extra bet shared with --extra-coin above, never two).',
    '    "--late-extra", "1",'),
  @('    "--bank-brake", "4.5",',
    '    # v-undo1114 2026-11-14: call B undone, 4.5 -> 3.00 with --extra-coin 1 and --late-extra 1 above: SIZE = floor(bank / (brake x (2 + 1) x 0.98)) = floor(bank / 8.82), exactly what 4.5 x 2 x 0.98 gave (pinrun size_for_bank, every whole-dollar bank $100-$20,000); the close budget goes back from 2 x SIZE to 3 x SIZE for a new coin or the last 15 s; the loss abort, loss cap and stake cap do not move. Revert: results\pin_undo1114.ps1 -Revert, or 3.00 -> 4.5 and both lines above back to 0.',
    '    "--bank-brake", "3.00",')
)
# the -Check line's flag changes, in order (old -> new; a leading and a trailing space keep each token whole)
$checkPairs = @(
  @(' --wrongside-rise-c 1.0 ', ' --wrongside-rise-c 0 '),
  @(' --ws-later-fall-c 10 --hedge-jump-max 8 ', ' --ws-later-fall-c 10 '),
  @(' --cheap-window 6 10 0.98 ', ' '),
  @(' --extra-coin 0 ', ' --extra-coin 1 '),
  @(' --late-extra 0 ', ' --late-extra 1 '),
  @(' --bank-brake 4.5 ', ' --bank-brake 3.00 ')
)
# what the new -Check line must carry (and the old one must not), and what must be gone from it
$mustNew = @(' --wrongside-rise-c 0 ', ' --ws-later-fall-c 10 --hedge-odds-mult 1.5 ', ' --extra-coin 1 ', ' --late-extra 1 ',
  ' --bank-brake 3.00 ', ' --hedge-odds-mult 1.5 ', ' --band99-max-tau 30 ', ' --hedge-jump-shadow 6 ')
$mustGone = @('--cheap-window', '--hedge-jump-max', ' --wrongside-rise-c 1.0 ', ' --extra-coin 0 ', ' --late-extra 0 ', ' --bank-brake 4.5 ')

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
  if ($t -match 'v-undo1114') { return $null }
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
# a -Check line carries the undo (every $mustNew once, no $mustGone)
function LineIsNew($l) {
  foreach ($s in $mustNew) { if ((Count $l $s) -ne 1) { return $false } }
  foreach ($s in $mustGone) { if ((Count $l $s) -ne 0) { return $false } }
  return $true
}
# a -Check line carries the pre-undo flags (every old pair side once, none of the new-only values)
function LineIsOld($l) {
  foreach ($p in $checkPairs) { if ((Count $l $p[0]) -ne 1) { return $false } }
  foreach ($s in @(' --wrongside-rise-c 0 ', ' --extra-coin 1 ', ' --late-extra 1 ', ' --bank-brake 3.00 ')) { if ((Count $l $s) -ne 0) { return $false } }
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
    foreach ($n in @('extra_coin', 'late_extra', 'bank_brake', 'cheap_window', 'wrongside_rise_c', 'hedge_jump_max', 'hedge_odds_mult', 'band99_max_tau')) {
      $v = $null
      try { $v = $d.$n } catch {}
      $fl += ('{0} {1}' -f $n, $(if ($null -eq $v) { 'null' } else { (@($v) -join ',') }))
    }
    return ("pin pid {0} (alive: {1}) started {2} on code_sha {3} ({4}); its --minutes {5} run ends about {6:yyyy-MM-dd HH:mm}Z, then watch_bot restarts it through C:\kals-repo\restart_bot.ps1" -f $ppid, $alive, $d.t, $d.code_sha, ($fl -join ', '), $d.minutes, $end)
  } catch { return ("pin state not read: " + $_.Exception.Message) }
}

Say ("start" + $(if ($Revert) { ' (-Revert)' } else { '' }))
$ErrorActionPreference = 'Stop'

# ================================================================== -Revert: both launchers back to their pre-undo bytes
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
      if ($null -eq $n) { Done 1 ("REFUSED: {0}: the v-undo1114 lines are not in the expected shape; revert by hand (see REVERT in this script's header); nothing changed" -f $L.path) }
      $newText[$L.path] = $n
      $todo += $L
    }
    foreach ($L in $already) { Say ("{0} is ALREADY the pre-undo bytes ({1}): left as it is" -f $L.path, $L.old.Substring(0, 12)) }
    if (-not $todo.Count) { Done 0 "NOTHING TO DO: both live launchers are already the pre-undo bytes" }
    $busy = @(RestartRunning)
    if ($busy.Count -gt 0) { Done 1 ("REFUSED: a restart_bot.ps1 is running right now (pid {0}): it reads the launcher; run this again in a minute or two; nothing changed" -f (($busy | ForEach-Object { $_.ProcessId }) -join ', ')) }
    $dir = "$work\revert"
    New-Item -ItemType Directory -Force $dir | Out-Null
    $copies = @{}
    foreach ($L in $todo) {
      $cp = Join-Path $dir $L.snap
      WriteText $cp ($newText[$L.path]) (HasBom $L.path)
      if ((Sha64 $cp) -ne $L.old) { Done 1 ("REFUSED: the reverted copy {0} has sha256 {1}, not the pre-undo {2}; live launchers untouched" -f $cp, (Sha64 $cp), $L.old) }
      $c = CheckOf $cp
      if (-not $c.ok -or -not (LineIsOld $c.line)) { Done 1 ("REFUSED: -Check of the reverted copy {0} does not show the pre-undo flags on $build (see the log); live launchers untouched" -f $cp) }
      $copies[$L.path] = $cp
    }
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    foreach ($L in $todo) {
      $bak = $L.path + '.before-undo1114-revert-' + $stamp
      Copy-Item $L.path $bak -ErrorAction Stop
      if ((Sha64 $bak) -ne $L.new) { Done 1 ("REFUSED: the backup {0} is not a byte copy of {1}; nothing changed" -f $bak, $L.path) }
      $baks[$L.path] = $bak
    }
    $busy = @(RestartRunning)
    if ($busy.Count -gt 0) { Done 1 ("REFUSED: a restart_bot.ps1 started meanwhile (pid {0}); nothing changed -- run this again in a minute or two" -f (($busy | ForEach-Object { $_.ProcessId }) -join ', ')) }
    foreach ($L in $todo) {
      $script:edited = $true
      Copy-Item ($copies[$L.path]) $L.path -Force -ErrorAction Stop
      if ((Sha64 $L.path) -ne $L.old) { if (-not (RestoreAll $from)) { Done 5 "a launcher restore FAILED" }; Done 1 ("{0} was not the pre-undo bytes after the write; restored" -f $L.path) }
      Say ("REVERTED {0} ({1}) = {2} (sha256 {3}; the undo bytes kept as {4})" -f $L.path, $L.what, $copies[$L.path], $L.old.Substring(0, 12), $baks[$L.path])
    }
    foreach ($L in $launchers) {
      $c = CheckOf $L.path
      if (-not $c.ok -or -not (LineIsOld $c.line)) { Say ("-Check of {0} after the revert does not show the pre-undo flags (see the log)" -f $L.path); if (-not (RestoreAll $from)) { Done 5 "a launcher restore FAILED" }; Done 1 "the launchers this run wrote are back to the undo bytes; pin untouched" }
    }
  } catch {
    Say ("ERROR: " + $_.Exception.Message)
    if ($script:edited) { if (-not (RestoreAll $from)) { Done 5 "a launcher restore FAILED after an error" } }
    Done 1 "stopped; the live launchers are as they were (pin untouched)"
  }
  $ErrorActionPreference = 'Continue'
  Say (PinState)
  Done 0 "REVERTED: both live launchers pass the pre-undo flags again (--wrongside-rise-c 1.0, --hedge-jump-max 8, --cheap-window 6 10 0.98, --extra-coin 0 --late-extra 0 --bank-brake 4.5). pin was NOT restarted: it takes them at its next start. Commit the previous launcher snapshot back (see REVERT in this script's header), or kalshi_watch alarms every 30 min."
}

# ================================================================== forward
$from = @{}; $to = @{}
foreach ($L in $launchers) { $from[$L.path] = $L.old; $to[$L.path] = $L.new }
try {
  # ---- 1. preconditions
  $bad = BuildBad
  if ($bad) { Done 1 ("REFUSED: $build is not the live 0925x build: " + $bad + "; nothing changed") }
  $vtxt = [IO.File]::ReadAllText($versions)
  if ($vtxt -notmatch '# v-undo1114 ') { Done 1 "REFUSED: $versions has no v-undo1114 entry (git pull --ff-only first); nothing changed" }
  $raw = [IO.File]::ReadAllText($sums)
  if ($raw.Contains("`r")) { Done 1 "REFUSED: $sums has CR line ends (it must be LF, sha256sum format); nothing changed" }
  foreach ($L in $launchers) {
    $rows = @($raw -split "`n" | Where-Object { $_ -match ('^([0-9a-f]{64})  ' + [regex]::Escape($L.snap) + '$') })
    if ($rows.Count -ne 1) { Done 1 ("REFUSED: $sums names {0} {1} times (expected once); nothing changed" -f $L.snap, $rows.Count) }
    $h = $rows[0].Substring(0, 64)
    if ($h -ne $L.new) { Done 1 ("REFUSED: $sums gives {0} as {1}, not this script's NEW {2} (pull the v-undo1114 commit; do not edit the hashes); nothing changed" -f $L.snap, $h.Substring(0, 12), $L.new.Substring(0, 12)) }
  }
  # each launcher is either still at the start bytes (to do) or already at the target bytes (a run that stopped half way
  # between the two writes: left as it is); anything else is refused
  $todo = @(); $already = @(); $newText = @{}
  foreach ($L in $launchers) {
    $h = Sha64 $L.path
    if ($h -eq $L.new) { $already += $L; continue }
    if ($h -ne $L.old) { Done 1 ("REFUSED: {0} ({1}) has sha256 {2}, expected exactly {3} (the committed 11-14 snapshot): it changed since this script was written -- look before anything is edited; nothing changed" -f $L.path, $L.what, $(if ($h) { $h } else { 'missing' }), $L.old) }
    $n = Forward ([IO.File]::ReadAllText($L.path))
    if ($null -eq $n) { Done 1 ("REFUSED: {0}: the six edited lines are not in the expected shape (each once, a whole line; no v-undo1114 text); nothing changed" -f $L.path) }
    $newText[$L.path] = $n
    $todo += $L
  }
  foreach ($L in $already) { Say ("{0} is ALREADY the v-undo1114 bytes ({1}): left as it is" -f $L.path, $L.new.Substring(0, 12)) }
  if (-not $todo.Count) {
    foreach ($L in $launchers) {
      $c = CheckOf $L.path
      if (-not $c.ok -or -not (LineIsNew $c.line)) { Done 5 ("BOTH live launchers are the v-undo1114 bytes but -Check of {0} is not clean (see the log) -- pin's next restart would ABORT; a person must look" -f $L.path) }
    }
    Say (PinState)
    Done 0 "NOTHING TO DO: both live launchers are already the v-undo1114 bytes, the build is intact and both -Check clean"
  }
  $busy = @(RestartRunning)   # @(): one process would otherwise unroll to a bare object whose .Count is $null on 5.1
  if ($busy.Count -gt 0) { Done 1 ("REFUSED: a restart_bot.ps1 is running right now (pid {0}): it reads the launcher; run this again in a minute or two; nothing changed" -f (($busy | ForEach-Object { $_.ProcessId }) -join ', ')) }
  try { $gs = Native 'git' @('-C', 'C:\kals-repo', 'status', '--porcelain', '--', 'restart_bot.ps1') } catch { $gs = @(('git not available: ' + $_.Exception.Message), -1) }
  Say ("git status of the keep-alive launcher (expected ' M restart_bot.ps1': its live edits are uncommitted): [" + ([string]$gs[0]).Trim() + "]")
  Say ("preconditions ok: $build is $codeSha / $pintakeSha / $ordercliSha (+ the six others); VERSIONS.md has v-undo1114; the committed snapshot names the NEW bytes; to edit: {0}" -f (($todo | ForEach-Object { $_.path }) -join ', '))
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
    if ($ddTxt -cne $wantTxt) { Done 1 ("REFUSED: {0}: the argv change is not exactly the six lines out and five in (live vs copy: {1}); live launchers untouched" -f $L.path, $ddTxt) }
  }
  Say ("edited copies in $work are the expected bytes, parse, both launchers' argv lines match, and each edit is exactly: " + $wantTxt)
  # the expected -Check line = a still-to-do live launcher's own -Check line with only the six flag changes; every
  # launcher's file-to-be must print exactly it
  $cLive = CheckOf ($todo[0].path)
  if (-not $cLive.ok -or -not (LineIsOld $cLive.line)) { Done 1 ("REFUSED: -Check of the live {0} did not show $build with each pre-undo flag once (the baseline line; see the log); nothing changed" -f $todo[0].path) }
  $expLine = $cLive.line
  foreach ($p in $checkPairs) { $expLine = $expLine.Replace($p[0], $p[1]) }
  if (-not (LineIsNew $expLine)) { Done 1 "REFUSED: the expected -Check line does not carry the undo (see the log); nothing changed" }
  $cNew = $null
  foreach ($L in $launchers) {
    $cc = CheckOf ($copies[$L.path])
    if (-not $cc.ok -or $cc.line -cne $expLine) { Done 1 ("REFUSED: -Check of {0} is not the live -Check line with only the six flag changes (see the log); live launchers untouched" -f $copies[$L.path]) }
    if (-not $cNew) { $cNew = $cc }
  }
  Say ("-Check of both edited launchers ok: the live argv with only the six flag changes; code_sha $codeSha, ordercli $ordercliSha, pintake $pintakeSha")

  # ---- 3. the full new argv self-test
  Copy-Item ($copies[$hand.path]) "$build\restart_bot.ps1" -Force    # the build's own self-test reads its launcher
  $argv = ($cNew.line.Trim() -split '\s+')
  $ix = [array]::IndexOf($argv, ($argv | Where-Object { $_ -like '*pinrun.py' } | Select-Object -First 1))
  $targs = @('-u', "$build\research\pinrun.py") + $argv[($ix + 1)..($argv.Length - 1)] + @('--selftest')
  if (-not (LineIsNew (' ' + ($targs -join ' ') + ' '))) { Done 1 "REFUSED: the self-test argv does not carry the undo; live launchers untouched" }
  Say ("self-test: " + ($targs -join ' '))
  New-Item -ItemType Directory -Force "$build\selftest" | Out-Null
  $so0 = "$build\selftest\undo1114_selftest.out"
  $p = Start-Process -FilePath $py -ArgumentList $targs -RedirectStandardOutput $so0 -RedirectStandardError "$build\selftest\undo1114_selftest.err" -NoNewWindow -PassThru
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
  Say ("self-test PASSED ({0} ok = the pinned {1}, 0 FAIL; {2} v-0925x, {3} v-hedge5, {4} v-0925v, {5} v-cheapwin) with the full v-undo1114 argv on $build" -f $nOkSeen, $nOkPinned, $nx9, $nh, $nvv, $ncw)

  # ---- 4. the live launchers: backed up (checked), replaced by the checked copies (checked), -Check
  $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  foreach ($L in $todo) {
    if ((Sha64 $L.path) -ne $L.old) { Done 1 ("REFUSED: {0} changed while this script ran; nothing changed" -f $L.path) }
    $bak = $L.path + '.before-undo1114-' + $stamp
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
Done 0 "DONE: both live launchers pass the v-undo1114 argv (--wrongside-rise-c 0, no --hedge-jump-max, no --cheap-window, --extra-coin 1 --late-extra 1 --bank-brake 3.00; the same build $build). pin was NOT restarted: the running pin keeps its flags until its next start (its --minutes run end -> watch_bot, or a restart while flat: LIVE FROM in this script's header); confirm then that the newest pinrun-live-*.jsonl start record carries extra_coin 1.0, late_extra 1.0, bank_brake 3.0, cheap_window null, wrongside_rise_c 0.0, hedge_jump_max null."
