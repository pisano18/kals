# ladder_rail100.ps1 -- 2026-11-13. Operator 11-13: "I'm giving you max power. Use the rest of my credits to do whatever
# you like. Improvements are obviously best."
# WHAT IT DOES (v-ladder-rail100): the penny ladder's (research\cleanroom\ladder_live.py, subaccount 1) CASH LIMIT goes
#   from 82% to 100% of its pot at the SAME bid size. ONE edit to the server's C:\kals-repo\boot_all.ps1 (its ladder_live
#   keep-alive line; boot_all.ps1 is locally modified and not in git, so `git pull` never touches it):
#       "--fit", "--commit-frac", "0.82", "--big-coins-above", "7000"
#   becomes
#       "--pot-per-contract", "5.9756", "--commit-frac", "1.0"
#   with every other flag as it was, and a one-line v-ladder-rail100 comment above that line.
#   Bid size = floor(pot / 5.9756) = the --fit size floor(0.82 x pot / (5 coins x 0.98c)) (5.9756 = 4.9 / 0.82): 215 at
#   today's $1,286 either way. The money rail becomes the whole pot, so 6 bids of 98c fit in one close instead of 5. One
#   market is still at most 2 bids (--market-cap-x 2, ~$421 at 215). --big-coins-above has to go: ladder_live refuses
#   it without --fit. With --fit it did one thing: from a $7,000 pot it added BTC ETH SOL BNB and cut the bid to fit 9
#   coins. The pot is $1,286, so dropping it changes nothing for now.
#   THIS SCRIPT NEVER STOPS OR STARTS THE LADDER. The running ladder keeps the 82% rail. KalsBoot (boot_all.ps1 every 10
#   min) starts it with the NEW argv when its --minutes 10080 run ends on its own (~04:50 ET 2026-11-14 for the run
#   started 11-07 04:50 ET) or after any other stop. Run this BEFORE then, or the change waits for the following start.
# WHY (two verifiers agreed): over the 82% rail's life the ladder refused 186 second bids for its cash limit (rail
#   max_commit); 58 of them would have filled, and every market involved won. The ladder lost 0 of 364 settled markets.
#   Worth ~+$3.9-5.2/day, ~$2.5-3/day risk-adjusted. RISK: at most ~98% of the pot rests in one close instead of 82%
#   (a close where every bid lost would cost ~$1,264 instead of ~$1,054). The worst single market stays at 2 bids.
# HOW TO RUN (on the server, after `git pull --ff-only` -- never a rebase, stash, reset or checkout):
#     powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-repo\results\ladder_rail100.ps1
#   (-Repo <dir> exists ONLY to rehearse on a scratch copy of the repo; the default is C:\kals-repo.)
# STEPS (boot_all.ps1 is not written before step 4; a failure in step 4 restores it from the backup):
#   1. refuse unless: results\VERSIONS.md has the v-ladder-rail100 entry (the commit is pulled); ladder_live.py has the
#      --pot-per-contract and --commit-frac options; boot_all.ps1 has the old argv text exactly once, ON the ladder line;
#      that line is exactly the expected one (every other flag as the self-test in step 2 runs it), a whole CRLF line,
#      directly under the ladder_live (LIVE, subaccount 1) keep-alive entry; boot_all.ps1 has no "--pot-per-contract" and
#      no v-ladder-rail100 text yet (already applied = refused, nothing changed).
#   2. the ladder's own self-test with the OLD and with the NEW sizing argv (each + --selftest, at most 5 minutes each).
#      They run without --live / --subaccount, so boot_all's keep-alive pattern (*ladder_live.py*--live*) can never take
#      them for the ladder; the program returns from --selftest before it reads either flag. Both must exit 0 with
#      "ladder_live self-test PASSED". The new run must report "pot_per_contract 5.9756 -> $643.47 bids N ...
#      commit_frac 1.0" and the old run "fit (big coins above $7000) -> $643.47 bids N" with the SAME N (same size).
#   3. build the edited text in memory: the one line replaced and the comment above it, with the line's own indent and
#      line end. Every other byte stays as it was, the BOM too (read and written as Latin-1, a byte-for-byte round trip;
#      the inserted text is ASCII). Then check it: it parses with 0 errors; line by line, exactly the old ladder line is
#      gone and exactly the comment + the new line are added; the new line's argv is exactly the expected list.
#   4. wait until no boot_all.ps1 run is in progress and KalsBoot's next run is at least 30 s away (at most 10 minutes;
#      PowerShell reads a script whole when it starts, so only that read must not meet the write). Back up boot_all.ps1
#      to results\boot_all.before-rail100-<stamp>.ps1 (sha256-checked) and write the new bytes (checked against the
#      expected bytes). Then parse-check the live file and re-check the ladder line. Any failure restores the backup
#      (sha256-checked against the pre-edit file).
#   5. report the running ladder (pid, start, old or new argv), when its run ends, the stop file and KalsBoot's state.
#      Nothing is restarted.
# EXIT: 0 = boot_all.ps1 edited and verified; 1 = refused, boot_all.ps1 unchanged; 5 = a restore failed -- a person must
#   look (the log names the backup).
# REVERT: copy results\boot_all.before-rail100-<stamp>.ps1 back over C:\kals-repo\boot_all.ps1 (or by hand: the ladder line
#   back to "--fit", "--commit-frac", "0.82", "--big-coins-above", "7000" in place of "--pot-per-contract", "5.9756",
#   "--commit-frac", "1.0", and the v-ladder-rail100 comment line deleted). If the ladder already runs the 100% rail,
#   then run results\ladder_restart.ps1: it stops the ladder in minutes 2-9 of a quarter hour, and KalsBoot starts it again
#   on the restored argv.
# Log: results\ladder_rail100.out; the self-tests' output: results\ladder_rail100_selftest_old.out / _new.out (+ .err)
param([string]$Repo = 'C:\kals-repo')
$log = "$Repo\results\ladder_rail100.out"
$f = "$Repo\boot_all.ps1"
$py = 'C:\Python314\python.exe'
function Say($m) { $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m; [Console]::Out.WriteLine($l); Add-Content -Path $log -Value $l }
function Done($code, $m) { if ($m) { Say $m }; Say ("EXIT {0}" -f $code); exit $code }
function Sha64($p) { try { (Get-FileHash -Algorithm SHA256 -Path $p -ErrorAction Stop).Hash.ToLower() } catch { $null } }
$latin1 = [Text.Encoding]::GetEncoding(28591)    # every byte <-> one char: a byte-exact round trip of the whole file

$oldArgv = '"--fit", "--commit-frac", "0.82", "--big-coins-above", "7000"'
$newArgv = '"--pot-per-contract", "5.9756", "--commit-frac", "1.0"'
$entryHead = '    @{ n = "ladder_live (LIVE, subaccount 1)"; like = "*ladder_live.py*--live*"; unlike = ""; stop = "$res\ladder-live.stop";'
$oldLine = '       a = @("-u", "research\cleanroom\ladder_live.py", "--subaccount", "1", "--live", "--auto-size", "--market-cap-x", "2", "--levels", "0", "--coins", "KXNEAR15M,KXZEC15M,KXDOGE15M,KXHYPE15M,KXXRP15M", ' + $oldArgv + ', "--minutes", "10080");'
$newLine = $oldLine.Replace($oldArgv, $newArgv)
$expectNew = @('-u', 'research\cleanroom\ladder_live.py', '--subaccount', '1', '--live', '--auto-size', '--market-cap-x', '2', '--levels', '0',
               '--coins', 'KXNEAR15M,KXZEC15M,KXDOGE15M,KXHYPE15M,KXXRP15M', '--pot-per-contract', '5.9756', '--commit-frac', '1.0', '--minutes', '10080')
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$bak = "$Repo\results\boot_all.before-rail100-$stamp.ps1"
$comment = '       # v-ladder-rail100 2026-11-13: ladder cash limit 82% -> 100% of the pot at the same bid size (--fit --commit-frac 0.82 --big-coins-above 7000 -> --pot-per-contract 5.9756 --commit-frac 1.0; floor(pot / 5.9756) = the fit size, 6 bids a close instead of 5, still 2 a market) -- results\ladder_rail100.ps1; revert: results\boot_all.before-rail100-' + $stamp + '.ps1'
# the argv tokens of one a = @(...) line
function TokensOf($line) { @([regex]::Matches($line.Substring($line.IndexOf('@(')), '"([^"]*)"') | ForEach-Object { $_.Groups[1].Value }) }
# the self-test argv from a keep-alive line: drop -u and the script, --live, --subaccount N; add --selftest
function SelftestArgs($line) {
  $t = TokensOf $line
  $out = @('-u', $t[1])
  for ($i = 2; $i -lt $t.Count; $i++) {
    if ($t[$i] -eq '--live') { continue }
    if ($t[$i] -eq '--subaccount') { $i++; continue }
    $out += $t[$i]
  }
  return ($out + @('--selftest'))
}
function RunSelftest($tag, $argv) {
  $so = "$Repo\results\ladder_rail100_selftest_$tag.out"
  $se = "$Repo\results\ladder_rail100_selftest_$tag.err"
  Say ("self-test ({0}): {1} {2}" -f $tag, $py, ($argv -join ' '))
  $p = Start-Process -FilePath $py -ArgumentList $argv -WorkingDirectory $Repo -RedirectStandardOutput $so -RedirectStandardError $se -NoNewWindow -PassThru
  $null = $p.Handle   # PowerShell 5: without this ExitCode is empty after WaitForExit
  try { $p.PriorityClass = 'BelowNormal' } catch {}
  if (-not $p.WaitForExit(300000)) { try { $p.Kill() } catch {}; return @{ ok = $false; why = "did not finish in 5 minutes (killed)"; out = '' } }
  $txt = ''
  try { $txt = [IO.File]::ReadAllText($so) } catch {}
  $err = ''
  try { $err = [IO.File]::ReadAllText($se) } catch {}
  foreach ($l in (($txt.Trim() -split "`r?`n") | Where-Object { $_.Trim() })) { Say ("  [$tag] " + $l) }
  if ($err.Trim()) { Say ("  [$tag stderr] " + (($err.Trim() -split "`r?`n") -join ' | ')) }
  return @{ ok = ($p.ExitCode -eq 0 -and $txt -match 'ladder_live self-test PASSED'); why = ("exit {0}" -f $p.ExitCode); out = $txt }
}
function LadderProcs { @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*ladder_live.py*--live*' }) }

Say ("start (repo $Repo, python $py)")
$ErrorActionPreference = 'Stop'
# ---- 1. preconditions
try {
  if (-not (Test-Path $f)) { Done 1 "REFUSED: $f is missing; nothing changed" }
  if (-not (Test-Path $py)) { Done 1 "REFUSED: $py is missing; nothing changed" }
  $vers = [IO.File]::ReadAllText("$Repo\results\VERSIONS.md")
  if ($vers -notmatch '# v-ladder-rail100 -- ') { Done 1 "REFUSED: $Repo\results\VERSIONS.md has no v-ladder-rail100 entry (git pull --ff-only first); nothing changed" }
  $code = [IO.File]::ReadAllText("$Repo\research\cleanroom\ladder_live.py")
  foreach ($opt in @('"--pot-per-contract"', '"--commit-frac"', '"--big-coins-above needs --fit"')) {
    if (-not $code.Contains($opt)) { Done 1 "REFUSED: research\cleanroom\ladder_live.py does not carry $opt (not the expected code); nothing changed" }
  }
  $orig = Sha64 $f
  $bytes = [IO.File]::ReadAllBytes($f)
  $t = $latin1.GetString($bytes)
  $bom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
  if ($t.Contains('v-ladder-rail100') -or $t.Contains('--pot-per-contract')) { Done 1 "REFUSED: boot_all.ps1 already carries v-ladder-rail100 / --pot-per-contract (already applied, or half applied -- look); nothing changed" }
  $nOld = ([regex]::Matches($t, [regex]::Escape($oldArgv))).Count
  if ($nOld -ne 1) { Done 1 ("REFUSED: boot_all.ps1 must carry the old argv text {0} exactly once, found {1}; nothing changed" -f $oldArgv, $nOld) }
  $nLine = ([regex]::Matches($t, [regex]::Escape($oldLine))).Count
  if ($nLine -ne 1) {
    $seen = (([regex]::Matches($t, '(?m)^.*ladder_live\.py", "--subaccount".*$') | ForEach-Object { $_.Value.Trim() }) -join ' || ')
    Done 1 ("REFUSED: the ladder line is not exactly the expected one (found {0} copies of it; the ladder line(s) now: {1}); nothing changed" -f $nLine, $seen)
  }
  $i0 = $t.IndexOf($oldLine)
  $before = $t.Substring(0, $i0)
  if ($i0 -gt 0 -and -not $before.EndsWith("`n")) { Done 1 "REFUSED: the ladder line does not start a line; nothing changed" }
  $after = $t.Substring($i0 + $oldLine.Length)
  if ($after.StartsWith("`r`n")) { $nl = "`r`n" } elseif ($after.StartsWith("`n")) { $nl = "`n" } else { Done 1 "REFUSED: the ladder line does not end at a line end; nothing changed" }
  $prevLine = ($before.TrimEnd([char[]]"`r`n") -split "`n")[-1].TrimEnd([char]13)
  if ($prevLine -ne $entryHead) { Done 1 ("REFUSED: the line above the ladder argv is not the ladder_live (LIVE, subaccount 1) keep-alive entry (it is: {0}); nothing changed" -f $prevLine.Trim()) }
  Say ("preconditions ok: VERSIONS.md has v-ladder-rail100; ladder_live.py has --pot-per-contract / --commit-frac; boot_all.ps1 (sha256 {0}, {1} bytes, BOM {2}, line end {3}) carries the old argv once, on the expected ladder line under the ladder_live entry" -f $orig.Substring(0, 12), $bytes.Length, $bom, $(if ($nl -eq "`r`n") { 'CRLF' } else { 'LF' }))
} catch { Done 1 ("REFUSED: error in the checks: " + $_.Exception.Message + "; nothing changed") }

# ---- 2. the ladder's self-test with the old and the new sizing argv
try {
  $rOld = RunSelftest 'old' (SelftestArgs $oldLine)
  $rNew = RunSelftest 'new' (SelftestArgs $newLine)
} catch { Done 1 ("REFUSED: the self-test could not run: " + $_.Exception.Message + "; nothing changed") }
if (-not $rOld.ok) { Done 1 ("REFUSED: the ladder self-test with the OLD argv did not pass (" + $rOld.why + "); see results\ladder_rail100_selftest_old.out/.err; nothing changed") }
if (-not $rNew.ok) { Done 1 ("REFUSED: the ladder self-test with the NEW argv did not pass (" + $rNew.why + "); see results\ladder_rail100_selftest_new.out/.err; nothing changed") }
$mOld = [regex]::Match($rOld.out, 'fit \(big coins above \$7000\) -> \$643\.47 bids (\d+), levels \[0\] .*commit_frac 0\.82 ')
$mNew = [regex]::Match($rNew.out, 'pot_per_contract 5\.9756 -> \$643\.47 bids (\d+), levels \[0\] .*commit_frac 1\.0 ')
if (-not $mOld.Success -or -not $mNew.Success) { Done 1 "REFUSED: the self-tests passed but their argv lines are not the expected sizing (old: fit, commit_frac 0.82; new: pot_per_contract 5.9756, commit_frac 1.0); nothing changed" }
if ($mOld.Groups[1].Value -ne $mNew.Groups[1].Value) { Done 1 ("REFUSED: the bid size differs at the self-test's `$643.47 pot (old {0}, new {1}); nothing changed" -f $mOld.Groups[1].Value, $mNew.Groups[1].Value) }
Say ("self-tests PASSED with both argvs; the same bid at `$643.47: {0} (old --fit 0.82) = {1} (new --pot-per-contract 5.9756)" -f $mOld.Groups[1].Value, $mNew.Groups[1].Value)

# ---- 3. the new text, built and checked in memory
try {
  $t2 = $t.Substring(0, $i0) + $comment + $nl + $newLine + $t.Substring($i0 + $oldLine.Length)
  $errs = $null
  $toks = $null
  $text2 = [Text.Encoding]::UTF8.GetString($latin1.GetBytes($t2))       # ASCII file + ASCII insert: the same characters
  if ($bom) { $text2 = $text2.TrimStart([char]0xFEFF) }
  [void][System.Management.Automation.Language.Parser]::ParseInput($text2, [ref]$toks, [ref]$errs)
  if ($errs.Count) { Done 1 ("REFUSED: the edited text has {0} parse errors (first: {1}); nothing changed" -f $errs.Count, $errs[0].Message) }
  # line by line, by position: lines 0..k-1 identical, old line k -> comment + new line, every later line identical
  $a1 = $t -split "`n"
  $a2 = $t2 -split "`n"
  $k = -1
  for ($j = 0; $j -lt $a1.Count; $j++) { if ($a1[$j].TrimEnd([char]13) -ceq $oldLine) { if ($k -ne -1) { $k = -2; break }; $k = $j } }
  $okLines = ($k -ge 1 -and $a2.Count -eq ($a1.Count + 1) -and $a2[$k].TrimEnd([char]13) -ceq $comment -and $a2[$k + 1].TrimEnd([char]13) -ceq $newLine)
  if ($okLines) { for ($j = 0; $j -lt $k; $j++) { if ($a1[$j] -cne $a2[$j]) { $okLines = $false; break } } }
  if ($okLines) { for ($j = $k + 1; $j -lt $a1.Count; $j++) { if ($a1[$j] -cne $a2[$j + 1]) { $okLines = $false; break } } }
  if (-not $okLines) { Done 1 ("REFUSED: the edited text is not exactly the one-line change (old line at index {0}, {1} -> {2} lines); nothing changed" -f $k, $a1.Count, $a2.Count) }
  $tk = TokensOf $newLine
  if (($tk -join '|') -ne ($expectNew -join '|')) { Done 1 ("REFUSED: the new ladder argv is not the expected list: " + ($tk -join ' ') + "; nothing changed") }
  $newBytes = $latin1.GetBytes($t2)
  Say ("edited text ok: parses with 0 errors, {0} -> {1} lines, only the ladder line replaced + the comment above it; new argv: {2}" -f $a1.Count, $a2.Count, ($tk -join ' '))
} catch { Done 1 ("REFUSED: error building the edited text: " + $_.Exception.Message + "; nothing changed") }

# ---- 4. wait for a quiet moment, back up, write, verify (restore on any failure)
function BootBusy { @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -like '*boot_all.ps1*' }).Count -gt 0 }
function NextBootS { try { $n = (Get-ScheduledTaskInfo -TaskName KalsBoot -ErrorAction Stop).NextRunTime; if ($n) { return ($n - (Get-Date)).TotalSeconds } } catch {}; return 9999.0 }
$quietBy = (Get-Date).AddMinutes(10)
$said = $false
try {
  while ($true) {
    $busy = BootBusy
    $nxt = NextBootS
    if (-not $busy -and ($nxt -ge 30 -or $nxt -lt -5)) { break }
    if ((Get-Date) -gt $quietBy) { Done 1 "REFUSED: no quiet moment (a boot_all.ps1 run in progress or KalsBoot due within 30 s) in 10 minutes; nothing changed" }
    if (-not $said) { Say ("waiting for a quiet moment (boot_all run in progress: {0}; KalsBoot next run in {1:N0} s)" -f $busy, $nxt); $said = $true }
    Start-Sleep -Seconds 5
  }
} catch { Done 1 ("REFUSED: error while waiting for a quiet moment: " + $_.Exception.Message + "; nothing changed") }
Say ("quiet moment: no boot_all.ps1 run in progress, KalsBoot next run in {0:N0} s" -f (NextBootS))
$written = $false
function Restore {
  try { Copy-Item $bak $f -Force -ErrorAction Stop } catch { Say ("RESTORE COPY FAILED: " + $_.Exception.Message) }
  if ((Sha64 $f) -ne $orig) { Say "RESTORE FAILED: $f is not its pre-edit bytes (backup $bak)"; return $false }
  Say "boot_all.ps1 restored from $bak (sha256 checked against the pre-edit file)"
  return $true
}
try {
  if ((Sha64 $f) -ne $orig) { Done 1 "REFUSED: boot_all.ps1 changed while this script ran; nothing changed" }
  Copy-Item $f $bak -ErrorAction Stop
  if ((Sha64 $bak) -ne $orig) { Done 1 "REFUSED: the backup $bak is not a byte copy of boot_all.ps1; boot_all.ps1 unchanged" }
  Say "backup: $bak (sha256 checked)"
  $written = $true
  [IO.File]::WriteAllBytes($f, $newBytes)
  $chk = [IO.File]::ReadAllBytes($f)
  if ($chk.Length -ne $newBytes.Length -or $latin1.GetString($chk) -ne $t2) { throw "boot_all.ps1 does not read back as the edited bytes" }
  $errs = $null
  [void][System.Management.Automation.Language.Parser]::ParseFile($f, [ref]$null, [ref]$errs)
  if ($errs.Count) { throw ("the live boot_all.ps1 has {0} parse errors (first: {1})" -f $errs.Count, $errs[0].Message) }
  $t3 = $latin1.GetString($chk)
  if (([regex]::Matches($t3, [regex]::Escape($newLine))).Count -ne 1 -or $t3.Contains($oldArgv) -or ([regex]::Matches($t3, [regex]::Escape($comment))).Count -ne 1) { throw "the live boot_all.ps1 does not carry the new ladder line + comment exactly once with the old argv gone" }
  $ln = ($t3 -split "`n" | Where-Object { $_ -match 'ladder_live\.py", "--subaccount"' }) | ForEach-Object { $_.TrimEnd("`r").Trim() }
  Say ("CHANGED boot_all.ps1 (sha256 {0} -> {1}); parses with 0 errors; the ladder line now: {2}" -f $orig.Substring(0, 12), (Sha64 $f).Substring(0, 12), ($ln -join ' || '))
} catch {
  Say ("ERROR while writing: " + $_.Exception.Message)
  if ($written) { if (-not (Restore)) { Done 5 "a person must look: boot_all.ps1 could not be restored to its pre-edit bytes (backup $bak)" } }
  Done 1 "boot_all.ps1 is as it was (restored and checked); the ladder untouched"
}
$ErrorActionPreference = 'Continue'

# ---- 5. report (nothing is restarted)
$lp = LadderProcs
$stop = "$Repo\results\ladder-live.stop"
if ($lp.Count) {
  foreach ($p in $lp) {
    $mode = 'OLD argv (--fit --commit-frac 0.82): the 82% rail until this run ends'
    if ($p.CommandLine -like '*--pot-per-contract 5.9756*') { $mode = 'NEW argv already' }
    $ends = $p.CreationDate.AddMinutes(10080)
    Say ("ladder running: pid {0}, started {1:yyyy-MM-dd HH:mm:ss}, {2}; its --minutes 10080 run ends ~{3:yyyy-MM-dd HH:mm} (server clock), then KalsBoot starts it with the NEW argv within 10 minutes" -f $p.ProcessId, $p.CreationDate, $mode, $ends)
  }
} else {
  Say "no ladder process is running: KalsBoot's next boot_all run starts it with the NEW argv (unless the stop file stands it down)"
}
Say ("stop file {0}: {1}" -f $stop, $(if (Test-Path $stop) { 'PRESENT (the ladder is stood down; boot_all will not start it)' } else { 'absent' }))
try { $ti = Get-ScheduledTaskInfo -TaskName KalsBoot -ErrorAction Stop; $tk2 = Get-ScheduledTask -TaskName KalsBoot -ErrorAction Stop; Say ("KalsBoot: {0}, last run {1}, next run {2}, last result {3}" -f $tk2.State, $ti.LastRunTime, $ti.NextRunTime, $ti.LastTaskResult) } catch { Say ("KalsBoot not readable: " + $_.Exception.Message) }
Done 0 ("DONE: boot_all.ps1's ladder line now runs --pot-per-contract 5.9756 --commit-frac 1.0 (backup $bak). The ladder was NOT stopped or started; the 100% rail goes live at its next start. REVERT: copy $bak over $f (then results\ladder_restart.ps1 if the ladder already runs the new argv).")
