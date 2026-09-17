# watch_bot.ps1 -- keep the live bot alive, and say loudly when it was not.
#
# WHY THIS EXISTS. On 2026-09-15 the live bot died three times in one night and
# each death was silent: `pinrun` raised, the traceback went to a hidden window,
# and the only evidence was an `end` record with an empty state. Between the
# crash and somebody noticing, the account simply stopped trading -- sixteen
# minutes the first time, twenty the second.
#
# run_all.ps1 has been watchdogging the two COLLECTORS since the beginning, for
# exactly this reason. Nothing has ever watchdogged the bot that spends money.
#
# REWRITTEN 2026-09-17 (operator: "Does the bot automatically catch itself
# being down and relaunch until it works? If not it should."). The first
# version stopped for good after 4 restarts in an hour. During an exchange
# maintenance window the bot halts on "5 consecutive errors" within minutes of
# every start, so four attempts were used up in the first ten minutes of the
# outage and the watchdog then sat silent -- possibly for the rest of the
# night. Now:
#
#   - QUICK restarts: up to $QuickRestarts inside $QuickWindowMin minutes.
#   - Then SLOW retries: one every $SlowEveryMin minutes, FOREVER, each logged.
#     An outage ends when it ends; the bot is back within $SlowEveryMin of it.
#   - A MONEY BRAKE halt (loss COUNT brake, loss abort, DRAWDOWN) waits
#     $BrakeCooldownMin minutes before the first restart, so at least one full
#     close passes and the halt is visible in the log and on the desktop app.
#     It is NOT a permanent stop: the operator's standing order is to keep
#     trading, and the brake resets per run anyway.
#   - A STALE bot -- alive but nothing written to its log for $StaleMin minutes
#     -- is treated as hung and restarted. The bot writes a close summary every
#     15 minutes and a watch record most minutes, so silence that long is not
#     a quiet market.
#   - THE OPERATOR'S STOP FLAG. If results\pinrun-live.stop exists, the desktop
#     app (research\pindesk.py) or a human has said "stand down". Nothing is
#     restarted until that file is gone. Start on the app deletes it.
#
# WHAT IT DELIBERATELY DOES NOT DO.
#   - It never starts a bot itself; restart_bot.ps1 does, with its own rails
#     (refuses while a bet is held and the bot is alive, proves the old pid is
#     gone, never starts a second live bot).
#   - It never touches the collectors.
#
# Heartbeat: results\watch_bot.heartbeat (ISO time) every check, and
# results\watch_bot.pid at start, so boot_all.ps1 and the desktop app can see
# it without reading a command line (which Windows may return empty).
#
#     powershell -ExecutionPolicy Bypass -File C:\kals-repo\watch_bot.ps1
#
param(
    [int]$CheckEvery = 30,
    [int]$QuickRestarts = 4,
    [int]$QuickWindowMin = 15,
    [int]$SlowEveryMin = 3,
    [int]$StaleMin = 25,
    [int]$BrakeCooldownMin = 15,
    [switch]$Once
)

$repo = "C:\kals-repo"
$res = "$repo\results"
$log = "$res\watch_bot.log"
$errFile = "$res\pinrun-live.err"
$stopFlag = "$res\pinrun-live.stop"
$pidFile = "$res\pinrun-live.pid"
$restarts = New-Object System.Collections.ArrayList
$lastAttempt = [datetime]::MinValue
$saidStop = $false
$saidBrake = ""

function Say($msg) {
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"), $msg
    Write-Output $line
    Add-Content -Path $log -Value $line -Encoding utf8
}

function LiveBotPid {
    # pid file first (needs no permission), command line second.
    if (Test-Path $pidFile) {
        $w = (Get-Content $pidFile -Raw -ErrorAction SilentlyContinue)
        if ($w -and $w.Trim() -match '^\d+$') {
            if (Get-Process -Id ([int]$w.Trim()) -ErrorAction SilentlyContinue) { return [int]$w.Trim() }
        }
    }
    $p = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
         Where-Object { $_.CommandLine -like '*research*pinrun*' -and
                        $_.CommandLine -like '*--live*' }
    if ($p) { return @($p)[0].ProcessId }
    return $null
}

function NewestLog {
    Get-ChildItem "$res\pinrun-live-*.jsonl" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

function LastHalt {
    # ("why", time) of the newest halt record in the newest log, or $null
    $f = NewestLog
    if (-not $f) { return $null }
    $tail = Get-Content $f.FullName -Tail 5 -ErrorAction SilentlyContinue
    foreach ($line in ($tail | Sort-Object -Descending)) {
        if ($line -match '"kind":\s*"halt"' -and $line -match '"why":\s*"([^"]*)"') {
            $why = $matches[1]
            $t = $f.LastWriteTime
            if ($line -match '"t":\s*"([^"]*)"') { try { $t = [datetime]::Parse($matches[1]).ToLocalTime() } catch {} }
            return @{ why = $why; at = $t }
        }
    }
    return $null
}

function IsMoneyBrake($why) {
    return ($why -match 'loss COUNT brake|loss abort|DRAWDOWN brake')
}

function SecondsSinceLogWrite {
    $f = NewestLog
    $o = Get-Item "$res\pinrun-live.out" -ErrorAction SilentlyContinue
    $t = [datetime]::MinValue
    if ($f -and $f.LastWriteTime -gt $t) { $t = $f.LastWriteTime }
    if ($o -and $o.LastWriteTime -gt $t) { $t = $o.LastWriteTime }
    if ($t -eq [datetime]::MinValue) { return 1e9 }
    return ((Get-Date) - $t).TotalSeconds
}

function Attempt($why) {
    $script:lastAttempt = Get-Date
    $restarts.Add((Get-Date)) | Out-Null
    Say ("restarting ({0}) -- {1}" -f $why, (& { $t = ""; if (Test-Path $errFile) { $l = Get-Content $errFile -Tail 3 -ErrorAction SilentlyContinue; if ($l) { $t = "last stderr: " + ($l -join " | ") } }; $t }))
    & powershell -ExecutionPolicy Bypass -File "$repo\restart_bot.ps1" 2>&1 |
        ForEach-Object { Say ("  restart_bot: " + $_) }
    Start-Sleep -Seconds 20
    $now = LiveBotPid
    if ($now) { Say "back up, pid $now" } else { Say "STILL DOWN after restart_bot.ps1 -- will retry" }
}

Set-Content -Path "$res\watch_bot.pid" -Value $PID -Encoding ascii
Say "watch_bot starting: every $CheckEvery s; $QuickRestarts quick restarts per $QuickWindowMin min, then one every $SlowEveryMin min forever; stale after $StaleMin min; money-brake cooldown $BrakeCooldownMin min"

while ($true) {
    Set-Content -Path "$res\watch_bot.heartbeat" -Value (Get-Date -Format o) -Encoding ascii
    $botPid = LiveBotPid

    if (Test-Path $stopFlag) {
        if (-not $saidStop) {
            $reason = (Get-Content $stopFlag -Raw -ErrorAction SilentlyContinue)
            Say "STANDING DOWN: operator stop flag present ($($reason.Trim())). Not restarting until it is removed."
            $saidStop = $true
        }
        if ($Once) { break }
        Start-Sleep -Seconds $CheckEvery
        continue
    }
    if ($saidStop) { Say "stop flag removed; watching again"; $saidStop = $false }

    $need = $null
    if ($botPid) {
        $quiet = SecondsSinceLogWrite
        if ($quiet -gt $StaleMin * 60) {
            $need = "STALE: pid $botPid alive but nothing written for $([int]($quiet/60)) min"
        } elseif ($Once) { Say "live bot alive, pid $botPid, last wrote $([int]$quiet) s ago"; break }
    } else {
        $need = "DOWN"
        $h = LastHalt
        if ($h -and (IsMoneyBrake $h.why)) {
            $age = ((Get-Date) - $h.at).TotalMinutes
            if ($age -lt $BrakeCooldownMin) {
                if ($saidBrake -ne $h.why) {
                    Say ("MONEY BRAKE halted the bot: {0} -- waiting {1} min before restarting" -f $h.why, $BrakeCooldownMin)
                    $saidBrake = $h.why
                }
                if ($Once) { break }
                Start-Sleep -Seconds $CheckEvery
                continue
            }
            $need = "DOWN after money brake (cooldown over): " + $h.why
        } elseif ($h) {
            $need = "DOWN after halt: " + $h.why
        }
    }

    if ($need) {
        if ($need -eq "DOWN" -or $need -like "DOWN*") { Say "LIVE BOT IS $need" } else { Say $need }
        # keep only restarts inside the quick window
        $cutoff = (Get-Date).AddMinutes(-$QuickWindowMin)
        $recent = @($restarts | Where-Object { $_ -gt $cutoff })
        $restarts.Clear() | Out-Null
        foreach ($r in $recent) { $restarts.Add($r) | Out-Null }

        if ($restarts.Count -ge $QuickRestarts) {
            $since = ((Get-Date) - $lastAttempt).TotalMinutes
            if ($since -ge $SlowEveryMin) {
                Say ("{0} restarts in the last {1} min -- slow retry (every {2} min until it sticks)" -f $restarts.Count, $QuickWindowMin, $SlowEveryMin)
                if ($need -like "STALE*") { Say "stale bot: stopping pid $botPid first"; Stop-Process -Id $botPid -Force -ErrorAction SilentlyContinue; Start-Sleep 3 }
                Attempt "slow"
            }
        } else {
            if ($need -like "STALE*") { Say "stale bot: stopping pid $botPid first"; Stop-Process -Id $botPid -Force -ErrorAction SilentlyContinue; Start-Sleep 3 }
            Attempt ("quick {0} of {1}" -f ($restarts.Count + 1), $QuickRestarts)
        }
    }
    if ($Once) { break }
    Start-Sleep -Seconds $CheckEvery
}
