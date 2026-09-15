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
# WHAT IT DOES. Every CHECK_EVERY seconds: is a `pinrun --live` process alive?
# If not, it appends a line to results/watch_bot.log saying when it went and
# what the error file held, then runs restart_bot.ps1 -- the ONE script allowed
# to start the bot, so every guard in it still applies (it refuses if the bot
# holds a position, proves the old one is gone by pid, and aborts rather than
# starting a second).
#
# WHAT IT DELIBERATELY DOES NOT DO.
#   - It never kills anything. It only starts what is missing.
#   - It never starts a bot itself; restart_bot.ps1 does, with its own rails.
#   - It STOPS RESTARTING after MAX_RESTARTS in one hour. A bot that dies
#     immediately and repeatedly is broken, and a watchdog that keeps
#     relaunching it into a loss is worse than one that stops and shouts.
#
#     powershell -ExecutionPolicy Bypass -File C:\kals-repo\watch_bot.ps1
#
param(
    [int]$CheckEvery = 60,
    [int]$MaxRestarts = 4,
    [switch]$Once
)

$repo = "C:\kals-repo"
$log = "$repo\results\watch_bot.log"
$errFile = "$repo\results\pinrun-live.err"
$restarts = New-Object System.Collections.ArrayList

function Say($msg) {
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"), $msg
    Write-Output $line
    Add-Content -Path $log -Value $line -Encoding utf8
}

function LiveBotPid {
    $p = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
         Where-Object { $_.CommandLine -like '*research*pinrun*' -and
                        $_.CommandLine -like '*--live*' }
    if ($p) { return @($p)[0].ProcessId }
    return $null
}

Say "watch_bot starting: checking every $CheckEvery s, at most $MaxRestarts restarts an hour"

while ($true) {
    $botPid = LiveBotPid
    if ($botPid) {
        if ($Once) { Say "live bot alive, pid $botPid"; break }
    } else {
        # how it died, if the error file caught anything
        $tail = ""
        if (Test-Path $errFile) {
            $lines = Get-Content $errFile -Tail 6 -ErrorAction SilentlyContinue
            if ($lines) { $tail = ($lines -join " | ") }
        }
        Say "LIVE BOT IS DOWN. last stderr: $tail"

        # rate limit: only count restarts inside the last hour
        $cutoff = (Get-Date).AddHours(-1)
        $recent = @($restarts | Where-Object { $_ -gt $cutoff })
        $restarts.Clear() | Out-Null
        foreach ($r in $recent) { $restarts.Add($r) | Out-Null }

        if ($restarts.Count -ge $MaxRestarts) {
            Say ("REFUSING TO RESTART: {0} restarts already this hour. The bot " -f $restarts.Count +
                 "is not crashing by accident. Fix it, then start it by hand with restart_bot.ps1.")
            if ($Once) { break }
            Start-Sleep -Seconds $CheckEvery
            continue
        }

        $restarts.Add((Get-Date)) | Out-Null
        Say ("restarting (attempt {0} of {1} this hour)" -f $restarts.Count, $MaxRestarts)
        & powershell -ExecutionPolicy Bypass -File "$repo\restart_bot.ps1" 2>&1 |
            ForEach-Object { Say ("  restart_bot: " + $_) }
        Start-Sleep -Seconds 20
        $now = LiveBotPid
        if ($now) { Say "back up, pid $now" } else { Say "STILL DOWN after restart_bot.ps1" }
    }
    if ($Once) { break }
    Start-Sleep -Seconds $CheckEvery
}
