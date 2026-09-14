# restart_bot.ps1 -- stop the live pin bot and start it again on current code.
#
# WHY THIS FILE EXISTS. The operator, 2026-09-13: "you push the bot live not
# me. I've never had to." The auto-mode classifier refuses an ad-hoc
# Stop-Process / Start-Process pair on a live money process, and it is right
# to -- but it can be allowed for ONE named, reviewable script. This is that
# script, and it is deliberately narrow: it kills nothing but `pinrun`, it
# starts nothing but `pinrun`, and it refuses outright if the bot is holding a
# position.
#
# IT NEVER TOUCHES THE COLLECTOR. kalshi_collector.py and crypto_feeds.py carry
# no "pinrun" in their command lines, and the tape is unreproducible.
#
# THE ARGUMENTS ARE THE DEPLOYED ONES from CURRENT_STATE.md. --size 20 is only
# a starting value; the bot re-reads the bank every 300 s and sizes itself.
#
# ADDED 2026-09-13 ~22:2xZ: --pick best (AMENDMENT 24). When two markets clear
# every gate in the same second the bot now buys the better one instead of
# whichever the loop happened to reach first. Measured +2.07c -> +2.76c per
# contract on IDENTICAL loss counts, and again out of sample (+1.63c ->
# +2.43c, six losses either way). The ordering comes from the edge measured on
# the previous 50 ms pass, so nothing is recomputed and no order waits. See
# results/PREREG_pin_live_AMENDMENT_23_24.md.
#
# ADDED 2026-09-14 BY OPERATOR DECISION: --max-per-market 2 (A23 + A29) and
# --min-fill-frac 0.10 (A28). Both were paper-only and both refusals are now
# lifted, in pinrun.py, with the reasoning written next to them.
#
# THE MEASUREMENT THAT DECIDED IT: over 234 live closes the bot spent only 58%
# of the contract budget it was ALREADY allowed, and the MEDIAN close spent
# exactly 50% -- one fill, never the second. The unspent half needs a second
# market to qualify and only 6.3% of scan seconds have one. So the cap was
# never the binding constraint; the inability to use it was.
#
# THE WORST CLOSE DOES NOT MOVE. It is MAX_PER_CLOSE x SIZE x ceiling either
# way. What changes is how often the budget is actually spent.
#
# --min-fill-frac 0.10 lowers the depth floor from half of SIZE to a tenth, so
# a thin book is taken rather than skipped. MIN_LEVEL (1 contract) is still the
# backstop. A smaller fill is the same bet at the same gate on fewer contracts.
#
# REVERTED 2026-09-13 ~18:1xZ: --sigma-ruler and --pin are GONE. The ruler cut
# live signals by 63% (4.21/hour -> 1.55/hour, measured on the day) against a
# benefit measured only on the index population, which rule 5 says may not
# transfer to us. Certain cost, unproven benefit. The sweep (AMENDMENT 18)
# stays -- it is separately evidenced and needs no flag.

$ErrorActionPreference = "Stop"
$repo = "C:\kals-repo"
$py = "C:\Python314\python.exe"

# --- 0. LEAVE A TRANSCRIPT. On 2026-09-13 the operator ran this and the bot
# did not change; nothing on disk said why, so the next session had to guess
# between "it refused because a position was open", "the execution policy
# blocked the script" and "it was run from the wrong directory". A restart that
# fails silently is worse than one that fails loudly.
$transcript = "$repo\results\restart_bot.last.log"
try { Stop-Transcript | Out-Null } catch {}
Start-Transcript -Path $transcript -Force | Out-Null
Write-Host "restart_bot.ps1 starting $(Get-Date -Format o)"

# --- 1. REFUSE IF NOT FLAT. Restarting mid-position abandons a live bet: the
# new process does not know about it, so it never settles it, never hedges it
# and never counts it against the loss brake.
$log = Get-ChildItem "$repo\results\pinrun-live-*.jsonl" |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($log) {
    $filled = 0
    $settled = 0
    foreach ($line in Get-Content $log.FullName) {
        if ($line -match '"kind":\s*"order"' -and $line -notmatch '"filled":\s*0(\.0+)?[,}]') { $filled++ }
        if ($line -match '"kind":\s*"settled"') { $settled++ }
    }
    Write-Host "newest log: $($log.Name) -- $filled filled orders, $settled settled"
    if ($settled -lt $filled) {
        Write-Host "REFUSING: the bot is holding a position ($filled filled, $settled settled)."
        Write-Host "Wait for the close to settle, then run this again."
        try { Stop-Transcript | Out-Null } catch {}
        exit 1
    }
}

# --- 2. STOP ONLY pinrun.
# ONLY THE LIVE ONE. On 2026-09-13 this matched '*pinrun*' and killed the
# WHAT-IF tracker too -- a paper pinrun the operator had asked to keep running.
# The live bot is the one carrying --live; nothing else may be stopped here.
#
# 2026-09-14: AND THE PID FILE IS THE PRIMARY SOURCE, NOT CommandLine.
# When the operator ran this himself, Win32_Process returned CommandLine EMPTY
# for the running bot -- Windows hides it from a caller that cannot open the
# process -- so this loop matched nothing, printed nothing, and the script went
# on to start a SECOND live bot. Two bots then traded the same account for 24
# minutes, each sizing off the same bank, each counting only its own fills
# against the loss abort, stake cap, position cap and losing-trade brake. Every
# rail was silently doubled.
$pidfile = "$repo\results\pinrun-live.pid"
$targets = @()
if (Test-Path $pidfile) {
    $wanted = (Get-Content $pidfile -Raw).Trim()
    if ($wanted -match '^\d+$') {
        $proc = Get-Process -Id ([int]$wanted) -ErrorAction SilentlyContinue
        if ($proc) { $targets += [int]$wanted }
    }
}
# belt and braces: the CommandLine sweep as well, in case the pid file is
# missing (a bot started before this amendment leaves none).
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*pinrun*' -and $_.CommandLine -like '*--live*' } |
    ForEach-Object { if ($targets -notcontains $_.ProcessId) { $targets += $_.ProcessId } }

if ($targets.Count -eq 0) {
    Write-Host "no live pinrun found to stop (pid file: $(Test-Path $pidfile))"
} else {
    foreach ($id in $targets) {
        Write-Host "stopping live pinrun pid $id"
        Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 3

# --- 2b. PROVE IT IS GONE BEFORE STARTING ANYTHING.
# THIS IS THE RULE THAT MATTERS: a kill that failed must ABORT the restart,
# never fall through into a second start. Checked by PID, which needs no
# permission to read, rather than by CommandLine, which is what failed.
$stillAlive = @()
foreach ($id in $targets) {
    if (Get-Process -Id $id -ErrorAction SilentlyContinue) { $stillAlive += $id }
}
if ($stillAlive.Count -gt 0) {
    Write-Host "ABORTING: could not stop live pinrun pid(s) $($stillAlive -join ', ')."
    Write-Host "Starting a second one would put TWO bots on the same account."
    Write-Host "Stop it by hand, then run this again:"
    foreach ($id in $stillAlive) { Write-Host "    Stop-Process -Id $id -Force" }
    try { Stop-Transcript | Out-Null } catch {}
    exit 1
}

# --- 3. START IT AGAIN.
Start-Process -FilePath $py -ArgumentList @(
    "-u", "$repo\research\pinrun.py",
    "--live", "--size", "20", "--minutes", "4320",
    "--loss-abort", "-60.00", "--max-positions", "3", "--max-losses", "3",
    "--improve-scope", "market", "--pick", "best",
    "--max-per-market", "2", "--improve-max", "0.010",
    "--min-fill-frac", "0.10"
) -WorkingDirectory $repo -WindowStyle Hidden
Start-Sleep -Seconds 15

# --- 4. PROVE IT CAME BACK, and prove the collector survived.
$new = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*pinrun*' -and $_.CommandLine -like '*--live*' }
if (-not $new) {
    Write-Host "FAILED: pinrun did not come back. Check results\pinrun-live-*.jsonl"
    try { Stop-Transcript | Out-Null } catch {}
    exit 1
}
Write-Host "pinrun running: pid $($new.ProcessId)"
# THE COLLECTOR CHECK IS BY FILE, NOT BY PROCESS LIST. The 2026-09-14 run
# reported "collector processes alive: 0" and raised a false alarm, for the
# same reason the kill failed: CommandLine came back empty. Both collectors
# were in fact running and had been since Sep 9. What actually proves a
# recorder is alive is that it is still WRITING, so that is what is checked.
# THE TWO RECORDERS WRITE DIFFERENTLY AND MUST BE CHECKED DIFFERENTLY.
# kalshi_collector flushes continuously, so its newest file is always seconds
# old. crypto_feeds gzips a whole hour in memory and writes it at the
# ROTATION: every one of its files has a LastWriteTime of exactly the top of
# the following hour, and the file for the hour in progress sits at 0 bytes
# until that hour ends. A naive "newest file is fresh" test therefore fails on
# a perfectly healthy feed recorder for 59 minutes out of every 60. Verified
# against six consecutive hours on 2026-09-14, each 280-690 KB, each written
# on the hour.
$fresh = 0

$newest = Get-ChildItem "C:\kals\kalshi_data" -Recurse -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($newest) {
    $age = [int]((Get-Date) - $newest.LastWriteTime).TotalSeconds
    Write-Host "kalshi_data  -- newest write $age s ago ($($newest.Name))"
    if ($age -lt 900) { $fresh++ }
} else {
    Write-Host "kalshi_data  -- NO FILES FOUND"
}

# For the feeds, the proof of life is that the PREVIOUS hour landed with
# content in it, plus a file open for the hour in progress.
$prevName = (Get-Date).ToUniversalTime().AddHours(-1).ToString("yyyyMMddTHH") + ".jsonl.gz"
$curName  = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHH") + ".jsonl.gz"
$prev = Get-ChildItem "C:\kals\feed_data" -Recurse -File -Filter $prevName -ErrorAction SilentlyContinue
$cur  = Get-ChildItem "C:\kals\feed_data" -Recurse -File -Filter $curName  -ErrorAction SilentlyContinue
$prevBytes = ($prev | Measure-Object -Property Length -Sum).Sum
Write-Host "feed_data    -- last full hour $prevName = $prevBytes bytes across $($prev.Count) feeds; $($cur.Count) open for $curName"
if ($prevBytes -gt 0 -and $cur.Count -gt 0) { $fresh++ }

if ($fresh -lt 2) {
    Write-Host "WARNING: a recorder may have stopped. The tape is NOT"
    Write-Host "reproducible -- check run_all.ps1 before anything else."
} else {
    Write-Host "both recorders are writing"
}
Write-Host "flags now live: $($new.CommandLine)"
Write-Host "restart_bot.ps1 done $(Get-Date -Format o)"
try { Stop-Transcript | Out-Null } catch {}
