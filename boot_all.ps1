# boot_all.ps1 -- bring the whole machine back after a reboot, and keep it up.
#
# WHY. Nothing started anything after a restart. run_all.ps1 (collectors),
# watch_bot.ps1 (live bot), the Crypto.com recorder and every paper arm were
# all launched by hand from a shell, so a Windows Update at 3 AM meant the
# tape stopped, the bot stopped, and everything stayed stopped until someone
# logged in and ran four scripts from memory. On 2026-09-15 that cost 7.57
# hours of trading.
#
# This script is IDEMPOTENT: it starts only what is missing and touches
# nothing that is running. The scheduled task "KalsBoot" runs it at logon and
# every 10 minutes after (Register with: powershell -File boot_all.ps1 -Install).
# The desktop app also runs it when it opens.
#
# HOW "RUNNING" IS DECIDED, in order of trust:
#   1. a pid file written by the process itself (run_all.pid, watch_bot.pid,
#      pinrun-live.pid) whose pid is alive -- needs no permission to read;
#   2. a command-line match -- which Windows returns EMPTY for a process the
#      caller cannot open (the 2026-09-14 double-bot incident). So if ANY
#      python.exe shows an empty command line, this script REFUSES to start
#      collectors or arms rather than risk a duplicate, and says so.
#
# THE LIVE BOT IS NEVER STARTED HERE. watch_bot.ps1 -> restart_bot.ps1 is the
# only path, with all its rails. This script only makes sure the watchdog
# exists.
#
#     powershell -ExecutionPolicy Bypass -File C:\kals-repo\boot_all.ps1
#     powershell -ExecutionPolicy Bypass -File C:\kals-repo\boot_all.ps1 -Install
#
param([switch]$Install, [switch]$NoArms, [switch]$DeafTest, [switch]$DeafDryRun)

$repo = "C:\kals-repo"
$res = "$repo\results"
$kals = "C:\kals"
$py = "C:\Python314\python.exe"
$log = "$res\boot_all.log"

function Say($msg) {
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"), $msg
    Write-Output $line
    Add-Content -Path $log -Value $line -Encoding utf8
}

if ($Install) {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File $repo\boot_all.ps1"
    $user = "$env:USERDOMAIN\$env:USERNAME"
    $t1 = New-ScheduledTaskTrigger -AtLogOn -User $user
    $t1.Delay = "PT1M"
    # every 10 minutes, indefinitely: a daily trigger whose repetition runs the
    # whole day. ([TimeSpan]::MaxValue as the duration is rejected by the
    # scheduler: "value incorrectly formatted or out of range".)
    $t2 = New-ScheduledTaskTrigger -Daily -At "00:00"
    $rep = (New-ScheduledTaskTrigger -Once -At "00:00" -RepetitionInterval (New-TimeSpan -Minutes 10) -RepetitionDuration (New-TimeSpan -Hours 24)).Repetition
    $t2.Repetition = $rep
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
        -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    try {
        Register-ScheduledTask -TaskName "KalsBoot" -Action $action -Trigger @($t1, $t2) -Settings $settings -Principal $principal -Force -ErrorAction Stop | Out-Null
    } catch {
        Say "FAILED to install scheduled task KalsBoot: $($_.Exception.Message)"
        exit 1
    }
    $info = Get-ScheduledTaskInfo -TaskName "KalsBoot"
    Say "installed scheduled task KalsBoot: at logon (+1 min) and every 10 min all day, as $user; next run $($info.NextRunTime)"
    exit 0
}

# --- A RECORDER ALIVE BUT DEAF. Operator sign-off 2026-09-22: "Yes also do
# build that check."
#
# run_all.ps1 restarts a recorder only when its process EXITS. On 2026-09-21
# from 20:50 to 01:38 ET the Kalshi collector stayed alive and wrote nothing,
# and nothing noticed for 4 h 47 min. That tape is gone for good.
#
# Two kinds of deaf, and only one is ours to fix:
#   RETRYING  its own log shows reconnect attempts in the last ~15 min. It is
#             already doing exactly what a restart would do. 09-21 was this:
#             37 failed handshakes, and it reconnected by itself within a
#             minute of the live bot doing the same -- the CONNECTION was
#             down, not the program. Killing it would only cost the buffered
#             hour. Alert (the phone does, on the tape going silent); no kill.
#   STUCK     tape silent 15+ min AND either its log has stopped too (hung),
#             or its log runs but shows no reconnect attempt (connected and
#             deaf -- nothing inside it will ever retry). Kill it; run_all.ps1
#             starts a fresh one within 5 minutes.
# At most one kill per recorder per hour, so a long outage cannot churn it.
function DeafVerdict($tapeRoot, $logPath, [datetime]$nowUtc, [double]$silentMin = 15) {
    $cur  = $nowUtc.ToString("yyyyMMdd'T'HH") + ".jsonl.gz"
    $prev = $nowUtc.AddHours(-1).ToString("yyyyMMdd'T'HH") + ".jsonl.gz"
    $newest = $null
    foreach ($d in @(Get-ChildItem -Path $tapeRoot -Directory -ErrorAction SilentlyContinue)) {
        foreach ($f in @($cur, $prev)) {
            $p = Join-Path $d.FullName $f
            if (Test-Path $p) {
                $m = (Get-Item $p).LastWriteTimeUtc
                if ((-not $newest) -or ($m -gt $newest)) { $newest = $m }
            }
        }
    }
    $tapeMin = if ($newest) { ($nowUtc - $newest).TotalMinutes } else { 9999 }
    if ($tapeMin -lt $silentMin) { return @{ state = "ok"; tape_min = $tapeMin; why = "" } }
    if (-not (Test-Path $logPath)) {
        return @{ state = "stuck"; tape_min = $tapeMin; why = ("tape silent {0:N0} min and no log at {1}" -f $tapeMin, $logPath) }
    }
    $logMin = ($nowUtc - (Get-Item $logPath).LastWriteTimeUtc).TotalMinutes
    if ($logMin -ge $silentMin) {
        return @{ state = "stuck"; tape_min = $tapeMin; why = ("tape silent {0:N0} min and its own log silent {1:N0} min -- hung" -f $tapeMin, $logMin) }
    }
    # the log has no dates; its [stat] line comes every 5 min, so the third
    # from last marks ~15 min ago. Any reconnect line after it = retrying.
    $tail = @(Get-Content $logPath -Tail 150 -ErrorAction SilentlyContinue)
    $stats = @(for ($i = 0; $i -lt $tail.Count; $i++) { if ($tail[$i] -match '^\[stat\]') { $i } })
    $from = if ($stats.Count -ge 3) { $stats[$stats.Count - 3] } else { 0 }
    $recon = @($tail[$from..($tail.Count - 1)] | Where-Object { $_ -match 'retry|connected|handshake' })
    if ($recon.Count -gt 0) {
        return @{ state = "retrying"; tape_min = $tapeMin; why = ("tape silent {0:N0} min, {1} reconnect line(s) in its log -- the connection is down, not the program" -f $tapeMin, $recon.Count) }
    }
    return @{ state = "stuck"; tape_min = $tapeMin; why = ("tape silent {0:N0} min, its log runs but shows no reconnect attempt -- connected and deaf" -f $tapeMin) }
}

if ($DeafTest) {
    # Plants each case in a temp folder and fails loudly on any miss.
    $fail = 0
    function DT($cond, $msg) { if ($cond) { Write-Output "  ok   $msg" } else { Write-Output "  FAIL $msg"; $script:fail++ } }
    $t = Join-Path $env:TEMP ("deaftest_" + [guid]::NewGuid().ToString("N"))
    $now = [datetime]::SpecifyKind([datetime]"2026-09-22T03:10:00", "Utc")
    New-Item -ItemType Directory -Force -Path "$t\tape\cfbenchmarks_value" | Out-Null
    $fp = "$t\tape\cfbenchmarks_value\20260922T03.jsonl.gz"
    Set-Content -Path $fp -Value "x"
    $lg = "$t\collector.out.log"
    # 1. healthy
    (Get-Item $fp).LastWriteTimeUtc = $now.AddSeconds(-5)
    Set-Content -Path $lg -Value @("[stat] 03:00 tracking=301 {'trade': 5}", "[stat] 03:05 tracking=301 {'trade': 5}", "[stat] 03:10 tracking=301 {'trade': 5}")
    (Get-Item $lg).LastWriteTimeUtc = $now.AddSeconds(-30)
    DT ((DeafVerdict "$t\tape" $lg $now).state -eq "ok") "a tape written 5 s ago is ok"
    # 2. THE 09-21 NIGHT, lines verbatim from C:\kals\logs\collector.out.log
    (Get-Item $fp).LastWriteTimeUtc = $now.AddMinutes(-40)
    Set-Content -Path $lg -Value @("[stat] 02:52 tracking=301 {}", "[ws] TimeoutError: timed out during opening handshake -- retry in 60s", "[stat] 02:57 tracking=301 {}", "[stat] 03:02 tracking=301 {}", "[ws] TimeoutError: timed out during opening handshake -- retry in 60s", "[stat] 03:07 tracking=301 {}")
    (Get-Item $lg).LastWriteTimeUtc = $now.AddSeconds(-60)
    $v = DeafVerdict "$t\tape" $lg $now
    DT ($v.state -eq "retrying") "THE 09-21 NIGHT: silent 40 min but retrying every minute -> retrying, NOT killed (got $($v.state))"
    # 3. connected and deaf: stats say nothing arrives, no reconnect attempt
    Set-Content -Path $lg -Value @("[ws] connected", "[stat] 02:52 tracking=301 {}", "[stat] 02:57 tracking=301 {}", "[stat] 03:02 tracking=301 {}", "[stat] 03:07 tracking=301 {}")
    (Get-Item $lg).LastWriteTimeUtc = $now.AddSeconds(-60)
    $v = DeafVerdict "$t\tape" $lg $now
    DT ($v.state -eq "stuck") "connected-and-deaf (an old '[ws] connected', then 15 min of empty stats) -> stuck (got $($v.state))"
    # 4. hung: tape and log both silent
    (Get-Item $lg).LastWriteTimeUtc = $now.AddMinutes(-30)
    DT ((DeafVerdict "$t\tape" $lg $now).state -eq "stuck") "tape AND log silent 30 min -> stuck (hung)"
    # 5. NULL: silent under the bar
    (Get-Item $fp).LastWriteTimeUtc = $now.AddMinutes(-10)
    DT ((DeafVerdict "$t\tape" $lg $now).state -eq "ok") "NULL: 10 min silent is under the 15-min bar -> ok"
    # 6. the top of the hour: last hour's file is fresh, this hour's not yet made
    Remove-Item $fp
    $pp = "$t\tape\cfbenchmarks_value\20260922T02.jsonl.gz"
    Set-Content -Path $pp -Value "x"
    (Get-Item $pp).LastWriteTimeUtc = $now.AddSeconds(-20)
    DT ((DeafVerdict "$t\tape" $lg $now).state -eq "ok") "NULL: the previous hour's file written 20 s ago counts (top of the hour)"
    # 7. exchange-feed reconnect wording, verbatim from feeds.out.log
    (Get-Item $pp).LastWriteTimeUtc = $now.AddMinutes(-40)
    Set-Content -Path $lg -Value @("[stat] 02:55 top-of-book live: {}", "[kraken] ConnectionClosedError: no close frame received or sent -- retry 60s", "[stat] 03:00 top-of-book live: {}", "[stat] 03:05 top-of-book live: {}")
    (Get-Item $lg).LastWriteTimeUtc = $now.AddSeconds(-60)
    DT ((DeafVerdict "$t\tape" $lg $now).state -eq "retrying") "the exchange recorder's '-- retry 60s' reads as retrying"
    Remove-Item -Recurse -Force $t
    if ($fail -gt 0) { Write-Output "boot_all deaf self-test: FAILED ($fail)"; exit 1 }
    Write-Output "boot_all deaf self-test: OK"
    exit 0
}

function PidFileAlive($path) {
    if (-not (Test-Path $path)) { return $false }
    $w = (Get-Content $path -Raw -ErrorAction SilentlyContinue)
    if (-not $w -or $w.Trim() -notmatch '^\d+$') { return $false }
    return [bool](Get-Process -Id ([int]$w.Trim()) -ErrorAction SilentlyContinue)
}

$procs = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -in 'python.exe', 'powershell.exe', 'pwsh.exe' })
$blind = @($procs | Where-Object { $_.Name -eq 'python.exe' -and -not $_.CommandLine }).Count
function Running($like) { return [bool]($procs | Where-Object { $_.CommandLine -like $like -and $_.ProcessId -ne $PID }) }
# python scripts are matched on python.exe ONLY: a PowerShell whose command
# text merely mentions 'pinphone.py' (an operator typing a check, or this very
# script's caller) must not count as the program running. That false match
# reported 'all up' with the phone link dead on 2026-09-17.
function RunningPy($like) { return [bool]($procs | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like $like }) }

$started = 0

# --- 1. the collectors' watchdog (run_all.ps1). The tape outranks everything.
if ((PidFileAlive "$kals\logs\run_all.pid") -or (Running '*run_all.ps1*')) {
    # fine
} elseif ($blind -gt 0) {
    Say "run_all.ps1 not visible, but $blind python process(es) hide their command line -- REFUSING to start collectors (a duplicate collector corrupts the tape). Check by hand."
} elseif ((RunningPy '*kalshi_collector.py*') -or (RunningPy '*crypto_feeds.py*')) {
    Say "a collector is running without run_all.ps1 -- leaving it alone"
} else {
    Say "run_all.ps1 is NOT running -- starting the collectors' watchdog"
    Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "$kals\run_all.ps1") `
        -WorkingDirectory $kals -WindowStyle Hidden -RedirectStandardOutput "$kals\logs\run_all.console.log" -RedirectStandardError "$kals\logs\run_all.console.err"
    $started++
}

# --- 1b. a recorder ALIVE BUT DEAF (see DeafVerdict above). Only while
# run_all.ps1 is up to start the replacement, and never when any python
# process hides its command line -- a kill must name exactly one process.
$runAllUp = (PidFileAlive "$kals\logs\run_all.pid") -or (Running '*run_all.ps1*')
foreach ($r in @(
    @{ name = "Kalshi recorder"; like = '*kalshi_collector.py*'; tape = "$kals\kalshi_data"; log = "$kals\logs\collector.out.log"; last = "$res\deaf_kill_collector.last" },
    @{ name = "Exchange recorder"; like = '*crypto_feeds.py*'; tape = "$kals\feed_data"; log = "$kals\logs\feeds.out.log"; last = "$res\deaf_kill_feeds.last" }
)) {
    $v = DeafVerdict $r.tape $r.log ([datetime]::UtcNow)
    if ($v.state -eq "ok") { continue }
    if ($v.state -eq "retrying") { Say "$($r.name) DEAF but retrying: $($v.why). Not killing it."; continue }
    $hits = @($procs | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like $r.like })
    if ($hits.Count -ne 1) { Say "$($r.name) STUCK ($($v.why)) but $($hits.Count) matching process(es) -- not killing blind"; continue }
    if ($blind -gt 0) { Say "$($r.name) STUCK ($($v.why)) but $blind python process(es) hide their command line -- not killing"; continue }
    if (-not $runAllUp) { Say "$($r.name) STUCK ($($v.why)) but run_all.ps1 is not up to restart it -- not killing"; continue }
    if (Test-Path $r.last) {
        $ago = ((Get-Date) - (Get-Item $r.last).LastWriteTime).TotalMinutes
        if ($ago -lt 60) { Say ("$($r.name) STUCK ($($v.why)); killed one {0:N0} min ago -- waiting out the hour" -f $ago); continue }
    }
    if ($DeafDryRun) { Say "DRY RUN: would kill $($r.name) pid $($hits[0].ProcessId): $($v.why)"; continue }
    Say "$($r.name) STUCK: $($v.why). Killing pid $($hits[0].ProcessId); run_all.ps1 starts a fresh one within 5 min."
    Stop-Process -Id $hits[0].ProcessId -Force -ErrorAction SilentlyContinue
    Set-Content -Path $r.last -Value (Get-Date -Format o)
}
if ($DeafDryRun) { exit 0 }

# --- 2. the live bot's watchdog. It starts the bot itself, through restart_bot.ps1.
#
# 2026-09-17: "RUNNING" IS NOT "WORKING". The watchdog hung inside a pipe after
# a restart and sat alive-but-blind for four hours, while this check said "all
# up; nothing to do" every ten minutes because the process existed. A watchdog
# that is not writing its heartbeat is dead to us, whatever the process table
# says, so it is killed and replaced. The threshold is generous: a restart
# attempt legitimately takes ~40 s, during which no heartbeat is written.
$wdStale = $false
$hb = "$res\watch_bot.heartbeat"
if (Test-Path $hb) {
    $age = ((Get-Date) - (Get-Item $hb).LastWriteTime).TotalSeconds
    if ($age -gt 300) {
        $wdStale = $true
        Say ("watch_bot heartbeat is {0:N0} s old -- it is alive but not watching. Killing it." -f $age)
        if (Test-Path "$res\watch_bot.pid") {
            $wp = (Get-Content "$res\watch_bot.pid" -Raw).Trim()
            if ($wp -match '^\d+$') { Stop-Process -Id ([int]$wp) -Force -ErrorAction SilentlyContinue }
        }
        Start-Sleep -Seconds 2
    }
}
if ((-not $wdStale) -and ((PidFileAlive "$res\watch_bot.pid") -or (Running '*watch_bot.ps1*'))) {
    # fine
} else {
    Say "watch_bot.ps1 is NOT running -- starting it (it will bring the live bot up unless results\pinrun-live.stop exists)"
    Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "$repo\watch_bot.ps1") `
        -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput "$res\watch_bot.console.log" -RedirectStandardError "$res\watch_bot.console.err"
    $started++
}

# --- 3. the Crypto.com recorder (public data, no key, no orders).
if (RunningPy '*cdc_record.py*') {
    # fine
} elseif ($blind -gt 0) {
    Say "cdc_record.py not visible and $blind python process(es) are blind -- not starting it"
} elseif (Test-Path "$kals\cdc_record.py") {
    Say "cdc_record.py is NOT running -- starting it"
    Start-Process -FilePath $py -ArgumentList @("-u", "$kals\cdc_record.py", "--seconds", "2", "--hot", "150", "--warm", "30", "--workers", "10") `
        -WorkingDirectory $kals -WindowStyle Hidden -RedirectStandardOutput "$kals\logs\cdc_record.out" -RedirectStandardError "$kals\logs\cdc_record.err"
    $started++
}

# --- 3b. the phone link (Telegram). Only when the operator has written the
# token file; polls Telegram, opens no port, answers one paired chat.
if (Test-Path "$kals\telegram.json") {
    if (RunningPy '*pinphone.py*') {
        # fine
    } elseif ($blind -gt 0) {
        Say "pinphone.py not visible and $blind python process(es) are blind -- not starting it"
    } else {
        Say "pinphone.py is NOT running -- starting the phone link"
        Start-Process -FilePath $py -ArgumentList @("-u", "$repo\research\pinphone.py") -WorkingDirectory $repo -WindowStyle Hidden `
            -RedirectStandardOutput "$res\pinphone.out" -RedirectStandardError "$res\pinphone.err"
        $started++
    }
}

# --- 4. the paper arms. READ-ONLY, none can send an order (pinrun without
# --live is paper; pinracearm has no order path). Started only when NONE are
# running, i.e. after a reboot -- never topped up one by one, because the
# comparison arms must share a window.
if (-not $NoArms) {
    $paper = @($procs | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*pinrun.py*' -and $_.CommandLine -notlike '*--live*' })
    $race = @($procs | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*pinracearm.py*' })
    if ($blind -gt 0 -and ($paper.Count -eq 0 -or $race.Count -eq 0)) {
        Say "paper arms not all visible and $blind python process(es) are blind -- not starting arms"
    } else {
        $live = @("-u", "$repo\research\pinrun.py", "--size", "20", "--minutes", "4320",
                  "--loss-abort", "-60.00", "--max-losses", "2", "--improve-scope", "market",
                  "--pick", "best", "--max-per-market", "2", "--improve-max", "0.010",
                  "--min-fill-frac", "0", "--sweep-depth", "--depth-ladder", "--jump-gate")
        if ($paper.Count -eq 0) {
            Say "no paper arms running -- starting the current experiment set"
            # 2026-09-18: the AMENDMENT 53 band arms replace the 09-15 set,
            # whose questions are answered (tau45/staged shipped as v-early-*,
            # onecoin/hedge70/dumps/loose/early60 dead or superseded). The
            # flag lists are the ones in start_bands.ps1; keep the two in step.
            # NO early-leg settings in $band: every arm below sets its own,
            # and a duplicated --early-tau makes argparse take the LAST one,
            # which silently turned a 60 s arm into a 45 s one.
            $band = @("--bank-brake", "4.08", "--hedge-price", "0.60",
                      "--max-positions", "3", "--hedge-belief", "0.60")
            $m15 = @("--band-mult", "0.90", "0.94", "1.5")
            $arms = @(
                @{ n = "arm-b-control";     x = $band + @("--early-tau", "45", "--early-frac", "1.0", "--early-min-price", "0.90", "--early-max-edge", "3.0", "--early-min-price", "0.90", "--early-max-edge", "3.0") + $m15 },
                @{ n = "arm-b-early-open";  x = $band + @("--early-tau", "45", "--early-frac", "1.0", "--early-min-price", "0.80", "--early-min-price", "0.80") + $m15 },
                @{ n = "arm-b-early-nocap"; x = $band + @("--early-tau", "45", "--early-frac", "1.0", "--early-min-price", "0.90", "--early-min-price", "0.90") + $m15 },
                @{ n = "arm-b-skip9496";    x = $band + @("--early-tau", "45", "--early-frac", "1.0", "--early-min-price", "0.90", "--early-max-edge", "3.0", "--early-min-price", "0.90", "--early-max-edge", "3.0", "--skip-band", "0.94", "0.96") + $m15 },
                @{ n = "arm-b-skip975";     x = $band + @("--early-tau", "45", "--early-frac", "1.0", "--early-min-price", "0.90", "--early-max-edge", "3.0", "--early-min-price", "0.90", "--early-max-edge", "3.0", "--skip-band", "0.94", "0.975") + $m15 },
                @{ n = "arm-b-mult2";       x = $band + @("--early-tau", "45", "--early-frac", "1.0", "--early-min-price", "0.90", "--early-max-edge", "3.0", "--early-min-price", "0.90", "--early-max-edge", "3.0", "--band-mult", "0.90", "0.94", "2.0") },
                @{ n = "arm-b-harder";      x = $band + @("--early-tau", "45", "--early-frac", "1.0", "--early-min-price", "0.90", "--early-max-edge", "3.0", "--early-min-price", "0.90", "--early-max-edge", "3.0", "--skip-band", "0.94", "0.975", "--band-mult", "0.80", "0.90", "2.0", "--band-mult", "0.90", "0.94", "2.0") },
                @{ n = "arm-b-all";         x = $band + @("--early-tau", "45", "--early-frac", "1.0", "--early-min-price", "0.80", "--early-min-price", "0.80", "--skip-band", "0.94", "0.975", "--band-mult", "0.80", "0.90", "2.0", "--band-mult", "0.90", "0.94", "2.0") },
                # the confidence arms (Lab: "Lower confidence to X"), relaunched
                # 2026-09-18 ~22:49Z after dying at ~16:36Z with no `end`
                # record. No early leg, no bands: the 09-15 base plus --pin.
                @{ n = "arm-pin0.97";       x = @("--max-positions", "3", "--hedge-belief", "0.60", "--pin", "0.97") },
                @{ n = "arm-pin0.975";      x = @("--max-positions", "3", "--hedge-belief", "0.60", "--pin", "0.975") },
                @{ n = "arm-pin0.98";       x = @("--max-positions", "3", "--hedge-belief", "0.60", "--pin", "0.98") },
                @{ n = "arm-pin0.985";      x = @("--max-positions", "3", "--hedge-belief", "0.60", "--pin", "0.985") },
                @{ n = "arm-pin0.99";       x = @("--max-positions", "3", "--hedge-belief", "0.60", "--pin", "0.99") },
                # the 60-second ladder (start_early60.ps1; keep the two in step)
                @{ n = "arm-e60-third";     x = $band + @("--early-tau", "60", "--early-frac", "0.333", "--early-min-price", "0.90", "--early-max-edge", "3.0") + $m15 },
                @{ n = "arm-e60-full";      x = $band + @("--early-tau", "60", "--early-frac", "1.0", "--early-min-price", "0.90", "--early-max-edge", "3.0") + $m15 },
                @{ n = "arm-e60-open";      x = $band + @("--early-tau", "60", "--early-frac", "0.333", "--early-min-price", "0.80") + $m15 }
            )
            foreach ($a in $arms) {
                # --arm-name PUTS THE NAME IN THE COMMAND LINE. Until
                # 2026-09-19 an arm here was known only by the redirect
                # filename below, and Windows does not report a redirect in a
                # process's command line -- so eleven of these arms could not
                # be told apart from one another and the desktop app refused
                # to pause or stop any of them (correctly: they share flags,
                # so a heuristic would have killed the wrong one). The flag is
                # a label; pinrun reads it for nothing and refuses it outright
                # on a --live command line.
                Start-Process -FilePath $py -ArgumentList ($live + $a.x + @("--arm-name", $a.n)) `
                    -WorkingDirectory $repo -WindowStyle Hidden `
                    -RedirectStandardOutput "$res\$($a.n).out" -RedirectStandardError "$res\$($a.n).err"
                Start-Sleep -Seconds 3
                $started++
            }
        }
        # THE LEDGER REFRESHER. results/kalshi_ledger.json is what the desktop
        # app and the phone bot now read for money, and nothing was keeping it
        # current -- a ledger frozen at whenever someone last ran the command by
        # hand still reads as today's number. It trades nothing; it fetches
        # settlements and writes a file.
        if (-not (RunningPy '*pinledgerd.py*')) {
            Say "pinledgerd.py is NOT running -- starting the Kalshi ledger refresher"
            Start-Process -FilePath $py -ArgumentList @("-u", "$repo
esearch\pinledgerd.py") `
                -WorkingDirectory $repo -WindowStyle Hidden `
                -RedirectStandardOutput "$res\pinledgerd.out" -RedirectStandardError "$res\pinledgerd.err"
            $started++
        }
        # the commodities paper arm (gold / silver / WTI). Paper only: its own
        # self-test asserts it cannot order. results/RESULTS_commodities.md.
        if (-not (RunningPy '*cmdarm.py*')) {
            Say "cmdarm.py is NOT running -- starting the commodities paper arm"
            Start-Process -FilePath $py -ArgumentList @("-u", "$repo\research\cmdarm.py", "--minutes", "4320") `
                -WorkingDirectory $repo -WindowStyle Hidden `
                -RedirectStandardOutput "$res\arm-cmd.out" -RedirectStandardError "$res\arm-cmd.err"
            Start-Sleep -Seconds 3
            $started++
        }
        # LIVE OIL -- REAL MONEY. Added 2026-09-18 on the operator's word
        # ("Boot script"). Trades KXWTI15M only, 16-30 s at 93-99c, $20 a bet,
        # stops itself at $25 down or 4 losses in a day. The sign-off phrase is
        # cmdlive's fixed per-instance token; the operator's actual sign-off
        # for this window and size is recorded in results/VERSIONS.md
        # (v-oilsweet). NOTE the embedded quotes: Start-Process splits an
        # ArgumentList element on spaces, and the first two relaunches on
        # 2026-09-18 failed exactly that way, leaving oil down for four minutes.
        # LIVE OIL IS OFF, 2026-09-18 ~13:3xZ. Operator: "Oil is sucking bad.
        # Ruined gains 2 days in a row now. Turn it off, figure out a strategy
        # for it, then paper trade it." It hit its own $25 brake twice in two
        # days. The 2-30 s paper arm and cmdarm keep measuring it for free.
        # To bring it back, delete this $false.
        if ($false -and -not (RunningPy '*cmdlive.py*')) {
            Say "cmdlive.py is NOT running -- starting LIVE oil (real money, \$20 a bet)"
            Start-Process -FilePath $py -ArgumentList @("-u", "$repo\research\cmdlive.py", "--live", "--signoff", '"commodity penny test"', "--size", "20", "--minutes", "1440") `
                -WorkingDirectory $repo -WindowStyle Hidden `
                -RedirectStandardOutput "$res\cmdlive.out" -RedirectStandardError "$res\cmdlive.err"
            Start-Sleep -Seconds 3
            $started++
        }
        # the 2-30 s oil PAPER arm the operator asked for alongside the live
        # 16-30 s rule. Its own process, because an overlapping band inside
        # cmdarm is refused by the one-per-market rule and never measured.
        if (-not (RunningPy '*cmdarm-wide230*')) {
            Say "2-30 s oil paper arm is NOT running -- starting it"
            Start-Process -FilePath $py -ArgumentList @("-u", "$repo\research\cmdarm.py", "--minutes", "4320", "--series", "KXWTI15M", "--only-window", "2:30:0.93:0.99", "--out", "$res\cmdarm-wide230.jsonl") `
                -WorkingDirectory $repo -WindowStyle Hidden `
                -RedirectStandardOutput "$res\arm-wide230.out" -RedirectStandardError "$res\arm-wide230.err"
            Start-Sleep -Seconds 3
            $started++
        }
        if ($race.Count -eq 0) {
            Say "no Coin Race arms running -- starting arm3 and arm4"
            Start-Process -FilePath $py -ArgumentList @("-u", "research\pinracearm.py", "--minutes", "4320", "--tau-max", "30", "--min-gap-bp", "4", "--min-price", "0.90", "--one-per-race-band") `
                -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput "$res\pinracearm-live.log" -RedirectStandardError "$res\pinracearm-live.err"
            Start-Sleep -Seconds 3
            Start-Process -FilePath $py -ArgumentList @("-u", "research\pinracearm.py", "--minutes", "4320", "--model", "fair", "--tau-max", "30", "--min-price", "0.90", "--min-edge", "0.02") `
                -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput "$res\pinracearm4-live.log" -RedirectStandardError "$res\pinracearm4-live.err"
            $started += 2
        }
    }
}

if ($started -eq 0) { Say "all up; nothing to do" } else { Say "started $started process(es)" }
