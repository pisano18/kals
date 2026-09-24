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
#   - EXCEPT THE DRAWDOWN BRAKE (v-hwm-reset, 2026-09-24). Its mark lives on
#     disk, so a restarted bot reads the same mark and halts again on its
#     first sizing tick: on 2026-09-20 this loop restarted a halted bot every
#     cooldown for two hours until a human edited results\pinrun-hwm.json.
#     A DRAWDOWN halt is now TERMINAL here: logged once, never restarted,
#     until results\pinrun-hwm.reset exists -- which START on the desktop
#     app writes in that state and nothing else writes. Then it restarts at
#     once (no cooldown: the operator has already decided) and the bot
#     re-bases its mark to the balance at startup and deletes the flag. If
#     the bot halts on DRAWDOWN again later, the flag is gone and this holds
#     again. Every other halt and crash keeps the behaviour above exactly.
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
#     powershell -ExecutionPolicy Bypass -File C:\kals-repo\watch_bot.ps1 -SelfTest
#
# -SelfTest drives ParseHalt and HaltVerdict -- the two pure functions that
# decide whether a dead bot is restarted -- on planted log lines, touches no
# file under results\, and exits 1 on any miss.
param(
    [int]$CheckEvery = 30,
    [int]$QuickRestarts = 4,
    [int]$QuickWindowMin = 15,
    [int]$SlowEveryMin = 3,
    [int]$StaleMin = 25,
    [int]$BrakeCooldownMin = 15,
    [switch]$Once,
    [switch]$SelfTest
)

$repo = "C:\kals-repo"
$res = "$repo\results"
$resetFlag = "$res\pinrun-hwm.reset"
$saidDrawdown = $false
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

function ParseHalt($lines, [datetime]$fallback) {
    # ("why", time) of the newest halt record among $lines (the tail of a
    # log, oldest first), or $null. A halt is followed by `end`, so the
    # newest halt is found by walking the tail backwards.
    if (-not $lines) { return $null }
    $arr = @($lines)
    for ($i = $arr.Count - 1; $i -ge 0; $i--) {
        $line = $arr[$i]
        if ($line -match '"kind":\s*"halt"' -and $line -match '"why":\s*"([^"]*)"') {
            $why = $matches[1]
            $t = $fallback
            if ($line -match '"t":\s*"([^"]*)"') { try { $t = [datetime]::Parse($matches[1]).ToLocalTime() } catch {} }
            return @{ why = $why; at = $t }
        }
    }
    return $null
}

function LastHalt {
    # ("why", time) of the newest halt record in the newest log, or $null
    $f = NewestLog
    if (-not $f) { return $null }
    $tail = Get-Content $f.FullName -Tail 5 -ErrorAction SilentlyContinue
    return (ParseHalt $tail $f.LastWriteTime)
}

function IsMoneyBrake($why) {
    return ($why -match 'loss COUNT brake|loss abort|DRAWDOWN brake')
}

function IsDrawdown($why) {
    return ($why -match 'DRAWDOWN brake')
}

function HaltVerdict($h, [bool]$resetPresent, [datetime]$now, [int]$cooldownMin) {
    # What to do about a DEAD bot, given its last halt ($h from LastHalt, or
    # $null for a crash with no halt record). Pure, so -SelfTest can drive it.
    #   act = "restart"  -> call restart_bot.ps1; `need` is the log line
    #   act = "wait"     -> money-brake cooldown running; `say` once
    #   act = "hold"     -> DRAWDOWN halt, no operator flag; `say` once, never restart
    if (-not $h) { return @{ act = "restart"; need = "DOWN" } }
    if (IsDrawdown $h.why) {
        if ($resetPresent) {
            return @{ act = "restart"; need = "DOWN after DRAWDOWN halt -- operator re-base flag present, restarting now (the bot re-bases its mark at startup): " + $h.why }
        }
        return @{ act = "hold"; say = ("DRAWDOWN halted the bot: {0} -- NOT restarting: a restarted bot halts again on the same mark. Waiting for the operator's START on the app (it writes results\pinrun-hwm.reset)." -f $h.why) }
    }
    if (IsMoneyBrake $h.why) {
        $age = ($now - $h.at).TotalMinutes
        if ($age -lt $cooldownMin) {
            return @{ act = "wait"; say = ("MONEY BRAKE halted the bot: {0} -- waiting {1} min before restarting" -f $h.why, $cooldownMin) }
        }
        return @{ act = "restart"; need = "DOWN after money brake (cooldown over): " + $h.why }
    }
    return @{ act = "restart"; need = "DOWN after halt: " + $h.why }
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

    # 2026-09-17 INCIDENT: this used to be
    #     & powershell -File restart_bot.ps1 2>&1 | ForEach-Object { Say ... }
    # and it HUNG FOR FOUR HOURS. The restart itself worked (the bot came back
    # as pid 544616 at 03:25), but the pipeline never closed -- a grandchild of
    # the restart script kept the write end of the pipe open, so ForEach-Object
    # waited for EOF that never came. The watchdog was alive, unhung-able and
    # blind: no heartbeat, no further checks, nothing watching the money.
    #
    # A watchdog must never block on a child. Start-Process writes to FILES,
    # so there is no pipe to keep open, and WaitForExit has a hard timeout.
    $rOut = "$res\watch_restart.out"
    $rErr = "$res\watch_restart.err"
    try {
        $proc = Start-Process -FilePath "powershell.exe" `
            -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "$repo\restart_bot.ps1") `
            -RedirectStandardOutput $rOut -RedirectStandardError $rErr -WindowStyle Hidden -PassThru
        if (-not $proc.WaitForExit(180000)) {
            Say "restart_bot.ps1 did not finish in 3 minutes -- killing it and retrying next cycle"
            try { $proc.Kill() } catch {}
        }
    } catch {
        Say ("could not run restart_bot.ps1: " + $_.Exception.Message)
    }
    foreach ($l in @(Get-Content $rOut -ErrorAction SilentlyContinue)) {
        if ($l -and $l.Trim() -and $l -notmatch 'transcript|^\*{4,}|^$') { Say ("  restart_bot: " + $l.Trim()) }
    }
    foreach ($l in @(Get-Content $rErr -ErrorAction SilentlyContinue)) {
        if ($l -and $l.Trim()) { Say ("  restart_bot ERR: " + $l.Trim()) }
    }
    Start-Sleep -Seconds 15
    $now = LiveBotPid
    if ($now) { Say "back up, pid $now" } else { Say "STILL DOWN after restart_bot.ps1 -- will retry" }
}

if ($SelfTest) {
    # Planted lines, verbatim shapes from the live logs; nothing under
    # results\ is read or written, and the pid file above is NOT claimed.
    $fail = 0
    function ST($cond, $msg) { if ($cond) { Write-Output "  ok   $msg" } else { Write-Output "  FAIL $msg"; $script:fail++ } }
    $ddLine = '{"why": "DRAWDOWN brake: bank $810.59 is 22.5% below its high of $1046.43, limit 20%. Size has been reduced to 91. STOP AND LOOK. (A WITHDRAWAL from the account looks identical to a trading loss here -- check the balance before assuming the worst.)", "drained": false, "t": "2026-09-20T04:16:38Z", "kind": "halt"}'
    $lcLine = '{"why": "loss COUNT brake: 2 losing trades this run >= 2", "drained": false, "t": "2026-09-20T04:16:38Z", "kind": "halt"}'
    $errLine = '{"why": "5 consecutive errors", "drained": false, "t": "2026-09-20T04:16:38Z", "kind": "halt"}'
    $pendLine = '{"why": "DRAWDOWN brake: bank $810.59 is 22.5% below its high of $1046.43, limit 20%.", "open_contracts": 91, "t": "2026-09-20T04:16:00Z", "kind": "halt_pending"}'
    $endLine = '{"state": {"halted": true}, "t": "2026-09-20T04:16:38Z", "kind": "end"}'
    $fb = [datetime]"2026-01-01T00:00:00"
    $h = ParseHalt @('{"kind": "autosize", "t": "2026-09-20T04:16:38Z"}', $ddLine, $endLine) $fb
    ST ($h -and (IsDrawdown $h.why) -and $h.at -eq ([datetime]::Parse("2026-09-20T04:16:38Z").ToLocalTime())) "THE 09-20 LOG SHAPE (autosize, halt, end): the halt is found past the end, with its own time"
    ST ((ParseHalt @($pendLine, $endLine) $fb) -eq $null) "NULL: a halt_pending row is not a halt"
    ST ((ParseHalt @('{"kind": "watch", "t": "x"}', $endLine) $fb) -eq $null) "NULL: a crash (end, no halt) parses as no halt"
    ST ((ParseHalt @() $fb) -eq $null -and (ParseHalt $null $fb) -eq $null) "NULL: an empty tail is no halt"
    $h2 = ParseHalt @($lcLine, $endLine, '{"kind": "start", "t": "2026-09-20T04:30:40Z"}', $ddLine) $fb
    ST ($h2 -and (IsDrawdown $h2.why)) "two halts in the tail: the NEWEST one wins"
    $now = [datetime]::Parse("2026-09-20T04:18:38Z").ToLocalTime()
    $dd = ParseHalt @($ddLine, $endLine) $fb
    $lc = ParseHalt @($lcLine, $endLine) $fb
    $er = ParseHalt @($errLine, $endLine) $fb
    $v = HaltVerdict $dd $false $now 15
    ST ($v.act -eq "hold" -and $v.say -match 'NOT restarting' -and $v.say -match 'pinrun-hwm.reset') "DRAWDOWN halt, no flag -> HOLD: never restarted, says what unlocks it (got $($v.act))"
    $v = HaltVerdict $dd $false $now.AddHours(5) 15
    ST ($v.act -eq "hold") "...and still HOLD five hours later: no cooldown ends it"
    $v = HaltVerdict $dd $true $now 15
    ST ($v.act -eq "restart" -and $v.need -match 're-base flag present') "DRAWDOWN halt WITH the operator's flag -> restart at once, no cooldown (got $($v.act))"
    $v = HaltVerdict $lc $false $now 15
    ST ($v.act -eq "wait" -and $v.say -match 'waiting 15 min') "loss COUNT brake 2 min old -> WAIT out the cooldown, as before (got $($v.act))"
    $v = HaltVerdict $lc $true $now 15
    ST ($v.act -eq "wait") "NULL: the re-base flag changes nothing for a loss COUNT brake"
    $v = HaltVerdict $lc $false $now.AddMinutes(14) 15
    ST ($v.act -eq "restart" -and $v.need -match 'cooldown over') "loss COUNT brake 16 min old -> restart, as before (got $($v.act))"
    $v = HaltVerdict $er $false $now 15
    ST ($v.act -eq "restart" -and $v.need -match 'DOWN after halt: 5 consecutive errors') "any other halt -> restart at once, as before (got $($v.act))"
    $v = HaltVerdict $null $false $now 15
    ST ($v.act -eq "restart" -and $v.need -eq "DOWN") "a crash with no halt record -> restart at once, as before (got $($v.act))"
    if ($fail -gt 0) { Write-Output "watch_bot self-test: FAILED ($fail)"; exit 1 }
    Write-Output "watch_bot self-test: OK"
    exit 0
}

Set-Content -Path "$res\watch_bot.pid" -Value $PID -Encoding ascii
Say "watch_bot starting: every $CheckEvery s; $QuickRestarts quick restarts per $QuickWindowMin min, then one every $SlowEveryMin min forever; stale after $StaleMin min; money-brake cooldown $BrakeCooldownMin min; a DRAWDOWN halt is held until results\pinrun-hwm.reset exists"

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
        $h = LastHalt
        $v = HaltVerdict $h (Test-Path $resetFlag) (Get-Date) $BrakeCooldownMin
        if ($v.act -eq "hold") {
            if (-not $saidDrawdown) { Say $v.say; $saidDrawdown = $true }
            if ($Once) { break }
            Start-Sleep -Seconds $CheckEvery
            continue
        }
        if ($saidDrawdown) { Say "re-base flag present; restarting the drawdown-halted bot"; $saidDrawdown = $false }
        if ($v.act -eq "wait") {
            if ($saidBrake -ne $h.why) {
                Say $v.say
                $saidBrake = $h.why
            }
            if ($Once) { break }
            Start-Sleep -Seconds $CheckEvery
            continue
        }
        $need = $v.need
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
