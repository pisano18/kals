# boot_phone_hung.ps1 -- 2026-11-08 (v-tg-hung, the 11-07 phone audit). The /approve item 'phonehung'.
# Adds the HUNG-PHONE KEEP-ALIVE to the server's LIVE boot_all.ps1, editing it IN PLACE, once.
#
# WHAT IT ADDS. boot_all's 3b restarted the phone only when its process was GONE; a phone stuck inside its loop
# (running, answering nothing, sending no alerts) counted as up forever. After this edit boot_all reads the
# heartbeat the phone writes (results\pinphone.heartbeat: the time, then "pid N"); one older than 5 minutes gets that
# pid killed and a fresh phone started -- at most one kill an hour, never while a python process hides its command
# line, never a phone that started under 5 minutes ago, and never a second phone beside one the kill did not end.
# Every time is read in UTC. (PhoneHungVerdict, PhoneCands, PhoneKeepAlive and a -PhoneTest self-test: 21 checks.)
#
# WHY A SCRIPT AND NOT A COMMITTED boot_all.ps1. The live boot_all.ps1 carries edits git never had: the ladder's
# argv (one rung; on the server also the 82% rail of ladder_argv_commit82.ps1), the FX taker and FX recorder
# keep-alives, the retired paper arms and cdc recorder switched off, the forecaster and race argv. A boot_all.ps1
# committed from git's copy would stop every pull ("local changes would be overwritten") and, forced through, undo
# all of them (the "reset wiped boot_all edits" incident). So this script changes exactly three places, each found by
# text that must occur exactly ONCE, and keeps every other byte, the BOM and the file's own line ends:
#   1. the param line gets [switch]$PhoneTest;
#   2. the three functions and the -PhoneTest block go in just before "function PidFileAlive($path) {";
#   3. section 3b's "if (RunningPy '*pinphone.py*') { # fine" becomes the keep-alive.
#
# STEPS. Refuse (nothing changed) unless each of the three old texts is found once and the names 3b uses are set
# before it; a boot_all.ps1 that already has PhoneKeepAlive is left alone (exit 0). The edited text is built in a temp
# file first: it must parse with 0 errors, and its three functions and -PhoneTest block, LIFTED out of the parsed file
# (boot_all itself is never run here), must end "boot_all phone self-test: OK". Only then: the backup
# (results\boot_all.before-phonehung.ps1, byte for byte), the write, and a read-back that must equal what was built
# (else the backup goes back). It starts and stops NO bot and no phone: KalsBoot's next pass (every 10 min) runs the
# new 3b. Undo by hand: copy results\boot_all.before-phonehung.ps1 back over C:\kals-repo\boot_all.ps1.
#
# ORDER. The phone's /update does NOT need this first: research\phone\tests\test_boot_phone.py (in the /update gate)
# patches a TEMP copy of the live boot_all.ps1 with this script while the live one has no keep-alive yet, so the gate
# also proves these three anchors are found in the server's own file. Recommended: /update, its hello, then
# /approve phonehung (the phone then already writes the heartbeat with its pid).
# -Target / -Log / -Backup are for that test (it points all three at a temp folder); /approve runs this with no
# arguments. Under KALS_TESTING=1 it refuses to touch anything in C:\kals-repo.
# Log: results\boot_phone_hung.out
param([string]$Target = 'C:\kals-repo\boot_all.ps1',
      [string]$Log = 'C:\kals-repo\results\boot_phone_hung.out',
      [string]$Backup = 'C:\kals-repo\results\boot_all.before-phonehung.ps1')
if ($env:KALS_TESTING -eq '1') {
    foreach ($p in @($Target, $Log, $Backup)) {
        if ($p -like 'C:\kals-repo\*') { Write-Output "REFUSED under KALS_TESTING=1: $p is in the live repo"; exit 2 }
    }
}
function Say($m) {
    $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m
    Write-Output $l
    Add-Content -Path $Log -Value $l -Encoding utf8
}
$logDir = Split-Path -Parent $Log
if ($logDir -and -not (Test-Path -LiteralPath $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
Say "start: $Target"

$old1 = 'param([switch]$Install, [switch]$NoArms, [switch]$DeafTest, [switch]$DeafDryRun)'
$new1 = 'param([switch]$Install, [switch]$NoArms, [switch]$DeafTest, [switch]$DeafDryRun, [switch]$PhoneTest)'
$anchor2 = 'function PidFileAlive($path) {'
$block2 = @'
# --- THE PHONE LINK ALIVE BUT HUNG (v-tg-hung, 2026-11-07, the phone audit).
#
# 3b below restarted the phone only when its process was GONE. A phone stuck
# inside its loop -- the process there, answering nothing, sending no alerts --
# counted as running forever. The phone's poll loop rewrites
# results\pinphone.heartbeat (the time, then "pid N") before every long poll
# and before every tick, so a heartbeat older than $maxAgeS (5 min; a normal
# pass is under a minute, a network outage still beats every ~40 s) means the
# loop is stuck. The pid killed is the heartbeat's own, and only when a
# visible python.exe whose command line names pinphone.py has that pid (or,
# for a heartbeat naming no pid, the ONE such process); never a process that
# started less than $maxAgeS ago (it has not written its first beat yet), and
# never a --selftest / --preview / --smoke run (they name pinphone.py too).
# Every time here is UTC: local-time arithmetic reads a beat from a minute ago
# as an hour old just after a daylight-saving change, and kills a working
# phone (the stuck-recorder check above uses UTC for the same reason).
# $cands: @( @{ pid = N; started = [datetime] UTC or $null } ) (PhoneCands).
function PhoneHungVerdict($hbPath, $cands, [datetime]$nowUtc, [double]$maxAgeS = 300) {
    $cands = @($cands)
    if ($cands.Count -eq 0) { return @{ hung = $false; pid = $null; why = "no phone process" } }
    $hbAge = [double]::PositiveInfinity
    $hbPid = $null
    if (Test-Path $hbPath) {
        $hbAge = ($nowUtc - (Get-Item $hbPath).LastWriteTimeUtc).TotalSeconds
        $txt = Get-Content $hbPath -Raw -ErrorAction SilentlyContinue
        if ($txt -and $txt -match 'pid (\d+)') { $hbPid = [int]$matches[1] }
    }
    if ($hbAge -le $maxAgeS) { return @{ hung = $false; pid = $null; why = ("heartbeat {0:N0} s old" -f $hbAge) } }
    $pick = $null
    if ($hbPid) { $pick = @($cands | Where-Object { $_.pid -eq $hbPid }) | Select-Object -First 1 }
    if (-not $pick) {
        if ($cands.Count -ne 1) {
            return @{ hung = $false; pid = $null; why = ("heartbeat stale but {0} phone process(es) and none is its pid {1} -- not killing blind" -f $cands.Count, $hbPid) }
        }
        $pick = $cands[0]
    }
    if (-not $pick.started) { return @{ hung = $false; pid = $pick.pid; why = "heartbeat stale but the process start time is unknown -- not killing" } }
    $ranS = ($nowUtc - $pick.started).TotalSeconds
    if ($ranS -le $maxAgeS) {
        return @{ hung = $false; pid = $pick.pid; why = ("heartbeat stale but pid {0} started {1:N0} s ago -- still starting" -f $pick.pid, $ranS) }
    }
    $ageWords = if ([double]::IsInfinity($hbAge)) { "missing" } else { "{0:N0} s old" -f $hbAge }
    return @{ hung = $true; pid = $pick.pid; why = ("heartbeat {0} while pid {1} has run {2:N0} s -- alive but stuck" -f $ageWords, $pick.pid, $ranS) }
}

# The phone processes PhoneHungVerdict judges: a python.exe whose command line
# names pinphone.py, never a --selftest / --preview / --smoke run; each one's
# start time in UTC ($null when Windows does not give it).
function PhoneCands($procs) {
    return @(@($procs) | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*pinphone.py*' -and
                                        $_.CommandLine -notlike '*--selftest*' -and $_.CommandLine -notlike '*--preview*' -and
                                        $_.CommandLine -notlike '*--smoke*' } |
             ForEach-Object { @{ pid = [int]$_.ProcessId
                                 started = $(if ($_.CreationDate) { ([datetime]$_.CreationDate).ToUniversalTime() } else { $null }) } })
}

# What 3b does about a HUNG verdict. At most ONE kill per $guardMin (60 min,
# the stuck-recorder rule: a heartbeat that cannot be written for a long time
# must not get a working phone killed, and its "phone up" text sent, every 10
# minutes); never while a python process is blind; and the kill is CHECKED: a
# phone still running after it is left alone and no second one is started
# beside it (two phones polling one bot token answer every control twice).
# $kill / $alive: script blocks taking the pid (3b passes Stop-Process and
# Get-Process; the self-test plants its own). Returns @{ say = line or $null;
# killed = it is gone, start a fresh one; keep = the hung one stays, start
# nothing }.
function PhoneKeepAlive($pv, [int]$blind, $lastPath, [datetime]$nowUtc, $kill, $alive, [double]$guardMin = 60) {
    if (-not $pv.hung) { return @{ say = $null; killed = $false; keep = $false } }
    if ($blind -gt 0) {
        return @{ say = "phone link HUNG ($($pv.why)) but $blind python process(es) hide their command line -- not killing"; killed = $false; keep = $true }
    }
    if (Test-Path $lastPath) {
        $ago = ($nowUtc - (Get-Item $lastPath).LastWriteTimeUtc).TotalMinutes
        if ($ago -ge 0 -and $ago -lt $guardMin) {
            return @{ say = ("phone link HUNG ({0}); killed one {1:N0} min ago -- waiting out the hour" -f $pv.why, $ago); killed = $false; keep = $true }
        }
    }
    Set-Content -Path $lastPath -Value $nowUtc.ToString("o")
    & $kill $pv.pid
    if (& $alive $pv.pid) {
        return @{ say = "phone link HUNG: $($pv.why). Killed pid $($pv.pid) but it is STILL RUNNING -- not starting a second phone beside it"; killed = $false; keep = $true }
    }
    return @{ say = "phone link HUNG: $($pv.why). Killed pid $($pv.pid); starting a fresh one."; killed = $true; keep = $false }
}

if ($PhoneTest) {
    # Plants each case in a temp folder and fails loudly on any miss (the -DeafTest pattern; starts and kills nothing:
    # PhoneKeepAlive gets planted kill / alive blocks). research\phone\tests\test_boot_phone.py runs this block, lifted
    # out of the parsed file with the three functions, in every pinphone --selftest.
    $fail = 0
    function PT($cond, $msg) { if ($cond) { Write-Output "  ok   $msg" } else { Write-Output "  FAIL $msg"; $script:fail++ } }
    $t = Join-Path $env:TEMP ("phonetest_" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $t | Out-Null
    $hb = "$t\pinphone.heartbeat"
    $now = [datetime]::UtcNow
    $old = $now.AddHours(-1)
    Set-Content -Path $hb -Value "2026-11-07T17:00:00Z pid 4242"
    (Get-Item $hb).LastWriteTimeUtc = $now.AddSeconds(-10)
    $v = PhoneHungVerdict $hb @(@{ pid = 4242; started = $old }) $now
    PT (-not $v.hung) "a heartbeat written 10 s ago is a working phone, every time read in UTC (got $($v.why))"
    (Get-Item $hb).LastWriteTimeUtc = $now.AddMinutes(-10)
    $v = PhoneHungVerdict $hb @(@{ pid = 4242; started = $old }) $now
    PT ($v.hung -and $v.pid -eq 4242) "heartbeat 10 min old, its pid has run 1 h -> HUNG, kill pid 4242 (got $($v.why))"
    $v = PhoneHungVerdict $hb @(@{ pid = 5151; started = $old }, @{ pid = 4242; started = $old }) $now
    PT ($v.hung -and $v.pid -eq 4242) "two phone processes: the heartbeat's own pid is the one killed (got pid $($v.pid))"
    $v = PhoneHungVerdict $hb @(@{ pid = 4242; started = $now.AddSeconds(-60) }) $now
    PT (-not $v.hung) "NULL: the process started 60 s ago has not beaten yet -> not killed (got $($v.why))"
    $v = PhoneHungVerdict $hb @(@{ pid = 5151; started = $old }, @{ pid = 6161; started = $old }) $now
    PT (-not $v.hung) "NULL: stale, two processes and neither is the heartbeat's pid -> not killing blind (got $($v.why))"
    $v = PhoneHungVerdict $hb @(@{ pid = 4242; started = $null }) $now
    PT (-not $v.hung) "NULL: a start time that cannot be read -> not killed"
    $v = PhoneHungVerdict $hb @() $now
    PT (-not $v.hung) "NULL: no phone process -> nothing to kill (3b starts one)"
    Set-Content -Path $hb -Value "2026-11-07T12:00:00"
    (Get-Item $hb).LastWriteTimeUtc = $now.AddMinutes(-10)
    $v = PhoneHungVerdict $hb @(@{ pid = 7171; started = $old }) $now
    PT ($v.hung -and $v.pid -eq 7171) "an old-format heartbeat (no pid) and ONE phone process -> that one (got pid $($v.pid))"
    (Get-Item $hb).LastWriteTimeUtc = $now.AddSeconds(-290)
    $v = PhoneHungVerdict $hb @(@{ pid = 7171; started = $old }) $now
    PT (-not $v.hung) "NULL: 4 min 50 s is under the 5-min bar -> not killed"
    (Get-Item $hb).LastWriteTimeUtc = $now.AddSeconds(-310)
    $v = PhoneHungVerdict $hb @(@{ pid = 7171; started = $old }) $now
    PT ($v.hung) "5 min 10 s is over the 5-min bar -> HUNG"
    Remove-Item $hb
    $v = PhoneHungVerdict $hb @(@{ pid = 7171; started = $old }) $now
    PT ($v.hung -and $v.pid -eq 7171) "no heartbeat file at all from a phone that has run 1 h -> HUNG (got $($v.why))"

    # PhoneCands: which processes are judged (start times turned to UTC)
    $localStart = (Get-Date).AddHours(-2)
    $fake = @(
        [pscustomobject]@{ Name = 'python.exe'; ProcessId = 11; CommandLine = 'C:\Python314\python.exe -u C:\kals-repo\research\pinphone.py'; CreationDate = $localStart },
        [pscustomobject]@{ Name = 'python.exe'; ProcessId = 12; CommandLine = 'C:\Python314\python.exe -u C:\kals-repo\research\pinphone.py --selftest'; CreationDate = $localStart },
        [pscustomobject]@{ Name = 'python.exe'; ProcessId = 13; CommandLine = 'python research\pinphone.py --preview'; CreationDate = $localStart },
        [pscustomobject]@{ Name = 'python.exe'; ProcessId = 14; CommandLine = 'python research\pinphone.py --smoke'; CreationDate = $localStart },
        [pscustomobject]@{ Name = 'powershell.exe'; ProcessId = 15; CommandLine = 'powershell -c "Get-Process | ? pinphone.py"'; CreationDate = $localStart },
        [pscustomobject]@{ Name = 'python.exe'; ProcessId = 16; CommandLine = 'C:\Python314\python.exe -u C:\kals-repo\research\pinrun.py --live'; CreationDate = $localStart },
        [pscustomobject]@{ Name = 'python.exe'; ProcessId = 17; CommandLine = 'C:\Python314\python.exe -u C:\kals-repo\research\pinphone.py'; CreationDate = $null })
    $c = @(PhoneCands $fake)
    PT ($c.Count -eq 2 -and $c[0].pid -eq 11 -and $c[1].pid -eq 17) "PhoneCands: the running phones only -- never a --selftest / --preview / --smoke run, a PowerShell naming pinphone.py, or another bot (got $(@($c | ForEach-Object { $_.pid }) -join ','))"
    PT ($c.Count -ge 1 -and $c[0].started.Kind -eq 'Utc' -and [math]::Abs(($c[0].started - $localStart.ToUniversalTime()).TotalSeconds) -lt 1) "PhoneCands: the start time is turned to UTC"
    PT ($c.Count -ge 2 -and $null -eq $c[1].started) "PhoneCands: a start time Windows does not give stays unknown (never killed on it)"
    PT (@(PhoneCands @()).Count -eq 0) "NULL: no process -> no phone"

    # PhoneKeepAlive: the kill, its once-an-hour guard, the blind rule, and the check that it really ended
    $script:kills = @()
    $script:still = $false
    $kill = { param($p) $script:kills += $p }
    $alive = { param($p) return $script:still }
    $last = "$t\phone_hung_kill.last"
    $hungV = @{ hung = $true; pid = 4242; why = "planted" }
    $r = PhoneKeepAlive @{ hung = $false; pid = $null; why = "fine" } 0 $last $now $kill $alive
    PT ((-not $r.killed) -and (-not $r.keep) -and $null -eq $r.say -and $script:kills.Count -eq 0) "NULL: a working phone -> nothing killed, nothing said"
    $r = PhoneKeepAlive $hungV 2 $last $now $kill $alive
    PT ((-not $r.killed) -and $r.keep -and $script:kills.Count -eq 0 -and $r.say -like '*hide their command line*') "HUNG but 2 python processes are blind -> not killed, nothing started beside it"
    $r = PhoneKeepAlive $hungV 0 $last $now $kill $alive
    PT ($r.killed -and (-not $r.keep) -and $script:kills.Count -eq 1 -and $script:kills[0] -eq 4242 -and (Test-Path $last)) "HUNG -> pid 4242 killed once, the guard file written, a fresh phone to start (got $($r.say))"
    $r = PhoneKeepAlive $hungV 0 $last $now.AddMinutes(10) $kill $alive
    PT ((-not $r.killed) -and $r.keep -and $script:kills.Count -eq 1 -and $r.say -like '*waiting out the hour*') "HUNG again 10 min later -> NOT killed (one kill an hour), nothing started (got $($r.say))"
    (Get-Item $last).LastWriteTimeUtc = $now.AddMinutes(-61)
    $r = PhoneKeepAlive $hungV 0 $last $now $kill $alive
    PT ($r.killed -and $script:kills.Count -eq 2) "HUNG 61 min after the last kill -> killed again"
    (Get-Item $last).LastWriteTimeUtc = $now.AddMinutes(-61)
    $script:still = $true
    $r = PhoneKeepAlive $hungV 0 $last $now $kill $alive
    PT ((-not $r.killed) -and $r.keep -and $script:kills.Count -eq 3 -and $r.say -like '*STILL RUNNING*') "a kill that did not end it -> no second phone started beside it (got $($r.say))"
    Remove-Item -Recurse -Force $t
    if ($fail -gt 0) { Write-Output "boot_all phone self-test: FAILED ($fail)"; exit 1 }
    Write-Output "boot_all phone self-test: OK"
    exit 0
}
'@
$old3 = @'
# token file; polls Telegram, opens no port, answers one paired chat.
if (Test-Path "$kals\telegram.json") {
    if (RunningPy '*pinphone.py*') {
        # fine
    } elseif ($blind -gt 0) {
'@
$new3 = @'
# token file; polls Telegram, opens no port, answers one paired chat.
# v-tg-hung (2026-11-07): ALIVE IS NOT ANSWERING. A phone whose heartbeat is
# older than 5 min (PhoneHungVerdict above) is killed by its pid first, then
# started fresh below -- at most once an hour, never while a python process
# hides its command line (a fresh one could not be started then either), and
# only when the kill really ended it (PhoneKeepAlive).
if (Test-Path "$kals\telegram.json") {
    $phoneCands = @(PhoneCands $procs)
    $pv = PhoneHungVerdict "$res\pinphone.heartbeat" $phoneCands ([datetime]::UtcNow)
    $ka = PhoneKeepAlive $pv $blind "$res\phone_hung_kill.last" ([datetime]::UtcNow) `
              { param($p) Stop-Process -Id $p -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 2 } `
              { param($p) [bool](Get-Process -Id $p -ErrorAction SilentlyContinue) }
    if ($ka.say) { Say $ka.say }
    # after a kill, $procs still lists the killed phone: only ANOTHER phone process counts as running then
    $phoneUp = if ($ka.killed) { @($phoneCands | Where-Object { $_.pid -ne $pv.pid }).Count -gt 0 } else { RunningPy '*pinphone.py*' }
    if ($ka.keep -or $phoneUp) {
        # fine (or the hung one stays: never a second phone beside it)
    } elseif ($blind -gt 0) {
'@

if (-not (Test-Path -LiteralPath $Target)) { Say "REFUSED: $Target is not there; nothing changed"; exit 1 }
$bytes = [IO.File]::ReadAllBytes($Target)
$bom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
$off = 0
if ($bom) { $off = 3 }
$utf8 = New-Object System.Text.UTF8Encoding($false, $true)
try { $text = $utf8.GetString($bytes, $off, $bytes.Length - $off) } catch {
    Say "REFUSED: $Target is not UTF-8 text; nothing changed"; exit 1
}
$ord = [StringComparison]::Ordinal
if ($text.Contains('function PhoneKeepAlive(')) {
    Say "boot_all.ps1 already has the hung-phone keep-alive (PhoneKeepAlive): nothing changed"
    exit 0
}
# the file's own line ends: every one CRLF, or every one LF (the laptop's live copy is LF, git's checkout CRLF)
$nCrlf = ([regex]::Matches($text, "`r`n")).Count
$nLf = ([regex]::Matches($text, "`n")).Count
if ($nLf -gt 0 -and $nCrlf -eq $nLf) { $nl = "`r`n"; $style = 'CRLF' }
elseif ($nLf -gt 0 -and $nCrlf -eq 0) { $nl = "`n"; $style = 'LF' }
else { Say "REFUSED: $Target mixes line ends ($nCrlf CRLF of $nLf); nothing changed"; exit 1 }
function N([string]$s) { return (($s -replace "`r`n", "`n") -replace "`n", $nl) }
$o1 = N $old1
$n1 = N $new1
$a2 = $nl + $anchor2
$b2 = $nl + (N $block2) + $nl + $nl + $anchor2
$o3 = N $old3
$n3 = N $new3
$miss = @()
foreach ($pair in @(@('the param line', $o1), @('"function PidFileAlive($path) {" at a line start', $a2), @('section 3b''s phone lines', $o3))) {
    $n = ([regex]::Matches($text, [regex]::Escape($pair[1]))).Count
    if ($n -ne 1) { $miss += ("{0} found {1} times, want 1" -f $pair[0], $n) }
}
if ($miss.Count -gt 0) { Say ("REFUSED: " + ($miss -join '; ') + ". Nothing changed."); exit 1 }
$i1 = $text.IndexOf($o1, $ord)
$i2 = $text.IndexOf($a2, $ord)
$i3 = $text.IndexOf($o3, $ord)
foreach ($need in @('function Say(', '$procs = @(', '$blind = @(', 'function RunningPy(')) {
    $i = $text.IndexOf($need, $ord)
    if ($i -lt 0 -or $i -gt $i3) { Say "REFUSED: '$need' is not set before section 3b (the keep-alive uses it). Nothing changed."; exit 1 }
}
if (-not ($i1 -lt $i2 -and $i2 -lt $i3)) {
    Say "REFUSED: the param line, PidFileAlive and section 3b are not in that order. Nothing changed."; exit 1
}
$new = $text.Replace($o1, $n1).Replace($a2, $b2).Replace($o3, $n3)
$grow = ($n1.Length - $o1.Length) + ($b2.Length - $a2.Length) + ($n3.Length - $o3.Length)
if ($new.Length -ne $text.Length + $grow) { Say "REFUSED: the edit did not land as three single changes. Nothing changed."; exit 1 }
$body = $utf8.GetBytes($new)
if ($bom) {
    $outBytes = New-Object byte[] ($body.Length + 3)
    $outBytes[0] = 0xEF; $outBytes[1] = 0xBB; $outBytes[2] = 0xBF
    [Array]::Copy($body, 0, $outBytes, 3, $body.Length)
} else { $outBytes = $body }

# ---- the edited text, checked BEFORE the live file is touched: it parses, and its lifted self-test passes
$work = Join-Path $env:TEMP ("boot_phone_hung_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $work | Out-Null
$cand = Join-Path $work 'boot_all.ps1'
[IO.File]::WriteAllBytes($cand, $outBytes)
$tokens = $null; $errs = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($cand, [ref]$tokens, [ref]$errs)
if ($errs.Count -gt 0) {
    Say ("REFUSED: the edited boot_all.ps1 would not parse ({0} errors; first: {1} at line {2}). Nothing changed." -f $errs.Count, $errs[0].Message, $errs[0].Extent.StartLineNumber)
    Remove-Item -Recurse -Force $work; exit 1
}
$parts = @()
foreach ($name in @('PhoneHungVerdict', 'PhoneCands', 'PhoneKeepAlive')) {
    $fn = @($ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name }, $true))
    if ($fn.Count -ne 1) { Say "REFUSED: function $name found $($fn.Count) times in the edited file, want 1. Nothing changed."; Remove-Item -Recurse -Force $work; exit 1 }
    $parts += $fn[0].Extent.Text
}
$blk = @($ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.IfStatementAst] -and $n.Clauses[0].Item1.Extent.Text -eq '$PhoneTest' }, $true))
if ($blk.Count -ne 1) { Say "REFUSED: the -PhoneTest block found $($blk.Count) times in the edited file, want 1. Nothing changed."; Remove-Item -Recurse -Force $work; exit 1 }
$parts += (". " + $blk[0].Clauses[0].Item2.Extent.Text)
$lifted = Join-Path $work 'lifted.ps1'
Set-Content -Path $lifted -Value ($parts -join "`r`n`r`n") -Encoding UTF8
$st = (& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $lifted 2>&1 | Out-String)
$stCode = $LASTEXITCODE
$nOk = ([regex]::Matches($st, '(?m)^\s*ok ')).Count
Remove-Item -Recurse -Force $work
if ($stCode -ne 0 -or $st -notmatch 'boot_all phone self-test: OK' -or $st -match 'FAIL') {
    Say ("REFUSED: the keep-alive's self-test did not pass on the edited file (exit {0}). Nothing changed. Its output:`r`n{1}" -f $stCode, $st.Trim())
    exit 1
}
Say ("the edited file parses and the keep-alive self-test passes ({0} ok, lifted out of the parsed file)" -f $nOk)

# ---- the live file: backup, write, read back
try {
    [IO.File]::WriteAllBytes($Backup, $bytes)
} catch {
    Say ("REFUSED: could not write the backup {0}: {1}. Nothing changed." -f $Backup, $_.Exception.Message); exit 1
}
$bk = [IO.File]::ReadAllBytes($Backup)
if ([Convert]::ToBase64String($bk) -ne [Convert]::ToBase64String($bytes)) { Say "REFUSED: the backup does not read back the same. Nothing changed."; exit 1 }
try {
    [IO.File]::WriteAllBytes($Target, $outBytes)
} catch {
    Say ("FAILED to write {0}: {1}. Putting the backup back." -f $Target, $_.Exception.Message)
    [IO.File]::WriteAllBytes($Target, $bytes); exit 1
}
$back = [IO.File]::ReadAllBytes($Target)
if ([Convert]::ToBase64String($back) -ne [Convert]::ToBase64String($outBytes)) {
    Say "FAILED: $Target does not read back what was written. Putting the backup back."
    [IO.File]::WriteAllBytes($Target, $bytes); exit 1
}
$sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Target).Hash.ToLower()
Say ("PATCHED {0}: 3 places changed, its {1} line ends and BOM ({2}) kept, {3} -> {4} bytes, sha256 {5}; backup {6}" -f $Target, $style, $bom, $bytes.Length, $outBytes.Length, $sha.Substring(0, 12), $Backup)
$hb = Join-Path (Split-Path -Parent $Target) 'results\pinphone.heartbeat'
if (Test-Path -LiteralPath $hb) {
    $hbTxt = Get-Content -LiteralPath $hb -Raw -ErrorAction SilentlyContinue
    if ($hbTxt -and $hbTxt -match 'pid (\d+)') { Say ("the phone's heartbeat names pid {0}: the phone is on the code that beats before every poll and tick" -f $matches[1]) }
    else { Say "NOTE: the phone's heartbeat names no pid yet: it is still on its old code (/update loads the code that beats before every tick)" }
}
Say "done: KalsBoot's next pass (within 10 min) runs the new 3b; nothing was started or stopped"
exit 0
