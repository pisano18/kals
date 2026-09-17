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
param([switch]$Install, [switch]$NoArms)

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
            $arms = @(
                @{ n = "arm-control";  x = @("--max-positions", "3", "--hedge-belief", "0.60") },
                @{ n = "arm-loose";    x = @("--max-positions", "5", "--hedge-belief", "0.60", "--take-dumps") },
                @{ n = "arm-tau45";    x = @("--max-positions", "3", "--hedge-belief", "0.60", "--tau-max", "45") },
                @{ n = "arm-hedge70";  x = @("--max-positions", "3", "--hedge-belief", "0.70") },
                @{ n = "arm-mirror";   x = @("--max-positions", "3", "--hedge-belief", "0.80") },
                @{ n = "arm-dumps";    x = @("--max-positions", "3", "--hedge-belief", "0.80", "--take-dumps") },
                @{ n = "arm-onecoin";  x = @("--max-positions", "3", "--hedge-belief", "0.60", "--one-coin-depth", "--one-coin-max", "2.0") },
                @{ n = "arm-staged";   x = @("--max-positions", "3", "--hedge-belief", "0.60", "--early-tau", "45", "--early-frac", "0.5") },
                # 46-60 s: the grid's frontier (RESULTS_grid.md). Does our gate rescue it?
                @{ n = "arm-early60";  x = @("--max-positions", "3", "--hedge-belief", "0.60", "--early-tau", "60", "--early-frac", "0.333") }
            )
            foreach ($a in $arms) {
                Start-Process -FilePath $py -ArgumentList ($live + $a.x) -WorkingDirectory $repo -WindowStyle Hidden `
                    -RedirectStandardOutput "$res\$($a.n).out" -RedirectStandardError "$res\$($a.n).err"
                Start-Sleep -Seconds 3
                $started++
            }
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
