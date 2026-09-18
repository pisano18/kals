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
#
# 2026-09-17: THE CHECK IS research\pinflat.py, NOT A COUNT. The count
# ("filled orders > settled records") deadlocked when the bot DIED holding a
# bet: the settled record it would have written never arrives, so the count
# never balances and this script refused forever -- with the watchdog calling
# it every minute. pinflat knows whether the bot is alive (pid file) and reads
# each open fill's close time from its ticker: alive + open fill = wait; dead +
# market still ahead = wait (a new bot could buy that close twice); dead +
# market closed = flat, it settled on the exchange without us.
$flatOut = & $py "$repo\research\pinflat.py" 2>&1
$flatCode = $LASTEXITCODE
foreach ($l in $flatOut) { Write-Host "pinflat: $l" }
if ($flatCode -eq 1) {
    Write-Host "REFUSING: the bot is holding a position (see pinflat above)."
    Write-Host "Wait for the close to settle, then run this again."
    try { Stop-Transcript | Out-Null } catch {}
    exit 1
}
if ($flatCode -ne 0) {
    # the helper itself failed: fall back to the old count, which errs on
    # the side of refusing.
    Write-Host "pinflat could not answer (exit $flatCode) -- falling back to the count"
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
            try { Stop-Transcript | Out-Null } catch {}
            exit 1
        }
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
# CAPTURE STDERR. Until 2026-09-15 this started the bot with no redirect at
# all, so when trade_loop raised the traceback went to a hidden window and
# vanished. The bot died at 04:29:30Z on a TypeError in a logging line and
# nobody knew for sixteen minutes -- the only evidence was an `end` record
# with an empty state. Two files, appended, never rotated by this script.
$errLog = "$repo\results\pinrun-live.err"
$outLog = "$repo\results\pinrun-live.out"
Start-Process -FilePath $py -RedirectStandardError $errLog -RedirectStandardOutput $outLog -ArgumentList @(
    "-u", "$repo\research\pinrun.py",
    "--live", "--size", "20", "--minutes", "4320",
    "--loss-abort", "-60.00", "--max-positions", "3", "--max-losses", "2",
    "--improve-scope", "market", "--pick", "best",
    "--max-per-market", "2", "--improve-max", "0.010",
    "--min-fill-frac", "0", "--sweep-depth", "--depth-ladder", "--jump-gate",
    "--hedge-belief", "0.60",
    # AMENDMENT 46 REOPENED 2026-09-18 ~02:2xZ, at a THIRD and with a PRICE
    # FLOOR. The operator: "Can you re open 45 seconds with a cap at 90c, or
    # whatever number you like?"
    #
    # Why it is back: the pickoff tracker says the cheap offers are taken a
    # median of 41 s before the close while our window starts at 30 s, so the
    # 31-45 s band is where the trades we are missing actually live. Closing it
    # entirely gives up the only lever that addresses the real problem.
    #
    # Why a THIRD and not a full bet: its full-size life was 31 markets, 29
    # settled, 29 won, +$35.81, and then ONE fill took $27.87 back --
    # KXBTC15M-26SEP172115-15, ask seen 97.8c, FILLED AT 53.0c because the book
    # collapsed inside our 160 ms round trip. A limit is a MAXIMUM, so no price
    # rule can prevent that fill; only size bounds it. At a third it costs ~$9.
    #
    # Why the 90c floor (AMENDMENT 49): out at 31-45 s less of the settlement
    # average is locked, so `fair` leans harder on the sigma estimate. A cheap
    # ask there is the market disagreeing with us exactly where our model is
    # weakest. Inside 30 s the full leg is untouched.
    # A THIRD -> FULL, 2026-09-18 ~17:0xZ, on the operator's word: "If you're
    # ready, then yes increase to 45." The third was a precaution from a
    # mechanism story; the live record does not support it. 31-45 s on real
    # money: 57 markets, 1 model miss (hedged to +$4.36), +$64.79. The main
    # window: 475 markets, 11 misses. Same miss rate. And post-fix, 26 of 34
    # early legs got NO top-up because by 30 s nothing was left to buy -- at a
    # third that forgoes two thirds of the position on three markets in four.
    # Post-fix early legs at a third: 31 markets, 31 won, +$33.59.
    "--early-tau", "45", "--early-frac", "1.0", "--early-min-price", "0.90",
    # AMENDMENT 50, 2026-09-18. The operator asked what to do with the
    # 45-second leg in the meantime: "It's earning good it'd be a shame to
    # shut it off, but also a shame to lose money... It might mean smaller
    # gains but that's better than none."
    #
    # This is a REFUSAL, not a new way to buy, so its worst case is fewer
    # trades. Out at 31-45 s, our model being far ABOVE the market price is a
    # warning rather than a bargain, and the sign flips at 30 seconds:
    #
    #   31-45 s   under 3c  177 bets  3 lost  +0.06 $/bet
    #             3-6c       62 bets  5 lost  -0.57 $/bet
    #             6c+        11 bets  3 lost  -3.01 $/bet
    #   <=30 s    6c+       263 bets  1 lost  +1.44 $/bet   (live: +3.08)
    #
    # Because at 45 s only a quarter of the settlement average is locked, so
    # our confidence rests on a volatility estimate; at 15 s three quarters is
    # already recorded and the market is simply wrong. Refusals log as
    # `early_wide`. INSIDE 30 s NOTHING CHANGES -- a wide edge there is the
    # single most profitable thing the bot does.
    "--early-max-edge", "3.0",
    # THE RISK SETTING, 2026-09-18, operator: "Sure divide by 8." One bet goes
    # from bank/5.88 to bank/8 -- at a $613 bank that is 104 contracts down to
    # 76, about $75 a bet. The worst a single close can cost falls from 33% of
    # the bank to 25%; the earning rate falls about a quarter. He was shown
    # both halves and chose it.
    "--bank-brake", "4.08"
    # AMENDMENT 46, deployed 2026-09-17 ("As long as you have the 45 second is
    # built as safely as you described, deploy now"), first at half, then at a
    # THIRD, and from ~19:5xZ the same day at a FULL bet on his instruction:
    # "Bump 45 seconds up to normal price as well."
    #
    # So 31-45 s now buys a FULL bet, and the top-up leg becomes a no-op
    # (staged_take returns size - early_held = 0). One early leg per market is
    # still enforced by the "early_once" refusal, so this cannot double up.
    # In effect TAU_MAX is 45 for the first bet, which is exactly what the flat
    # tau-45 paper arm has been testing: 33 settled closes, 0 losses, +230% more
    # closes than its control.
    #
    # WHAT IT GIVES UP: at a third we got a foot in the door early and completed
    # at 30 s when the information was better. At full we commit at the earlier,
    # worse-information moment and cannot improve the price afterwards.
    # WHAT SUPPORTS IT: on the tape BY MARKETS, buyers of 95-98c at 31-45 s lost
    # 2.8% (606 markets) against 3.9% at 16-30 s (389) -- the earlier window is
    # not the worse one. Model error at 31-45 s is 0.058% of moments, ~1/200th
    # of our live loss rate, so the risk here is adverse selection, not
    # arithmetic, and only live fills can measure it.
    # Bar and revert UNCHANGED: results/PREREG_staged.md stage 2 -- revert at 3
    # losses on early-leg closes in the first 40, or 2 in the first 15.
    # REVERTED TO PAPER 2026-09-18 ~01:5xZ on the operator's instruction:
    # "Revert 45 seconds to just a paper". It ran live for ~12 hours at a third
    # and then a full bet. Record: 31 markets carried an early leg, 29 settled,
    # 29 won, +$35.81 -- but the two still open include KXBTC15M-26SEP172115-15,
    # where we saw an ask of 97.8c, filled at 53.0c because the book collapsed
    # inside our 160 ms round trip, and the hedge locked -$27.87. At the old
    # third-size that loss would have been about -$9. So the honest net is
    # roughly +$8 on 31 markets, and the one bad fill cost more than the other
    # thirty made.
    # The flags now live on a PAPER arm only (results/arm-early45.out).
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

# BOTH recorders gzip a whole hour in memory and write it at the ROTATION.
# An in-progress file therefore sits at 0 bytes for up to 59 minutes, and a
# "newest write was N seconds ago" test alarms on a perfectly healthy recorder
# for most of every hour. The first version of this check applied that test to
# kalshi_data and duly cried wolf at 23:21 on 2026-09-14 with both collectors
# alive and burning CPU since Sep 9.
#
# The real proof of life: the PREVIOUS hour landed with bytes in it, and a
# file is open for the hour in progress.
$prevName = (Get-Date).ToUniversalTime().AddHours(-1).ToString("yyyyMMddTHH") + ".jsonl.gz"
$curName  = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHH") + ".jsonl.gz"
foreach ($d in @("C:\kals\kalshi_data", "C:\kals\feed_data")) {
    $prev = Get-ChildItem $d -Recurse -File -Filter $prevName -ErrorAction SilentlyContinue
    $cur  = Get-ChildItem $d -Recurse -File -Filter $curName  -ErrorAction SilentlyContinue
    $prevBytes = ($prev | Measure-Object -Property Length -Sum).Sum
    $name = Split-Path $d -Leaf
    Write-Host "$name -- last full hour $prevBytes bytes across $($prev.Count) channels; $($cur.Count) open now"
    if ($prevBytes -gt 0 -and $cur.Count -gt 0) { $fresh++ }
}

if ($fresh -lt 2) {
    Write-Host "WARNING: a recorder may have stopped. The tape is NOT"
    Write-Host "reproducible -- check run_all.ps1 before anything else."
} else {
    Write-Host "both recorders are writing"
}
Write-Host "flags now live: $($new.CommandLine)"
Write-Host "restart_bot.ps1 done $(Get-Date -Format o)"
try { Stop-Transcript | Out-Null } catch {}
