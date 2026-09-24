# sync_arms.ps1 -- every paper arm = THE LIVE BOT + its own one change.
#
# WHY THIS EXISTS. The operator, 2026-09-20: *"The paper bots should be taking
# other settings as they change as long as it's not what we're testing. Maybe
# that changes the way you run the paper bots but if we change stress to .5
# right now all bots should change otherwise their data isn't meaningful."*
#
# He is right, and the gap was far worse than it sounded. Measured that day,
# `arm-pin0.97` differed from the live bot in SIXTEEN settings:
#
#   --early-tau 45  --early-frac 1.0  --early-min-price 0.90
#   --early-max-edge 10.0  --hedge-price 0.60  --hedge-slip 0.03
#   --late-tau 10  --late-mult 1.5  --late-pin 0.9975  --late-jump 2.0
#   --extra-coin 1  --late-extra 1  --late-extra-tau 15
#   --bank-brake 4.00  --loss-cap 200      (and no 45-second leg at all)
#
# So "the confidence arm" was not measuring confidence. It was measuring a
# bot from five days ago that also happened to have a different --pin. Every
# head-to-head built on it is uninterpretable, including the one this session
# reported.
#
# HOW IT WORKS. The arms are no longer launched from a hard-coded flag list
# that rots the moment live changes. This script READS THE LIVE BOT'S OWN
# COMMAND LINE, strips --live (and anything the arm is testing), and hands
# each arm that base plus its single override. Change live, re-run this, and
# every arm moves with it.
#
# SAFETY, in the order it matters:
#   - It NEVER passes --live. Asserted per arm, and the whole run aborts if
#     the base it read still contains it after stripping.
#   - It validates EVERY arm's argv before stopping ANY process, because a
#     start that fails after a stop leaves nothing running (restart_bot.ps1's
#     lesson, learned the hard way on 2026-09-19).
#   - It never touches the live bot, the collectors, or the frozen pinvin_*
#     snapshots -- those are old code ON PURPOSE and syncing them would
#     destroy the only thing they are for.
#
#     powershell -ExecutionPolicy Bypass -File C:\kals-repo\sync_arms.ps1 -WhatIf
#     powershell -ExecutionPolicy Bypass -File C:\kals-repo\sync_arms.ps1
param([switch]$WhatIf, [string]$Only = "", [int]$GapMs = 2500)

$ErrorActionPreference = "Stop"
$py   = "C:\Python314\python.exe"
$repo = "C:\kals-repo"
$res  = "$repo\results"

# ---- 1. the live bot's own settings, read from the running process --------
# 2026-09-22: match pinrun.py EXACTLY. This used to take the first python
# process with '--live' in it -- and since 09-21 the coin race penny test
# (pinracearm.py --live) is one too. Which one came first depended on the
# process table's order: a -WhatIf on 09-22 11:4xZ built all 24 arms from the
# PENNY TEST's flags, which would have launched 24 dead pinruns.
$liveHits = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
              Where-Object { $_.CommandLine -like '*research\pinrun.py*' -and
                             $_.CommandLine -like '* --live*' })
if ($liveHits.Count -eq 0) { throw "the live bot (pinrun.py --live) is not running -- nothing to sync arms TO" }
if ($liveHits.Count -gt 1) { throw "REFUSING: $($liveHits.Count) pinrun.py --live processes -- which one is live? pids $(($liveHits | ForEach-Object { $_.ProcessId }) -join ', ')" }
$liveCl = $liveHits[0].CommandLine
foreach ($must in @('--hedge-belief', '--loss-cap', '--bank-brake')) {
    if ($liveCl -notlike "*$must*") { throw "REFUSING: the 'live' command line has no $must -- is it really pinrun? $liveCl" }
}

# argv, minus the exe and -u. Quoted tokens kept whole.
$argv = @()
foreach ($m in [regex]::Matches($liveCl, '(?:"([^"]*)"|(\S+))')) {
    if ($m.Groups[1].Success) { $argv += $m.Groups[1].Value } else { $argv += $m.Groups[2].Value }
}
$argv = @($argv | Select-Object -Skip 1 | Where-Object { $_ -ne "-u" })

# Split into [flag, values...] groups so a flag can be replaced with its value.
$groups = @(); $cur = $null
foreach ($t in $argv) {
    if ($t -like "--*") { if ($cur) { $groups += ,$cur }; $cur = @($t) }
    elseif ($cur)       { $cur += $t }
}
if ($cur) { $groups += ,$cur }

function BaseWithout([string[]]$drop) {
    # the live flag list minus --live, minus --size/--minutes (arms set their
    # own), minus every flag this arm overrides.
    $out = @()
    foreach ($g in $groups) {
        $f = $g[0]
        if ($f -eq "--live") { continue }
        if ($f -in @("--size", "--minutes", "--arm-name")) { continue }
        # 2026-09-22: --max-losses is NOT inherited. Live halts after 2
        # losing trades and watch_bot restarts it ~15 min later; a paper arm
        # has no watchdog, so the same brake ended it FOR GOOD. By 09-22 it
        # had stopped 17 of 24 arms -- every bold one the operator asked to
        # watch -- after exactly the two losses the comparison needs to see.
        if ($f -eq "--max-losses") { continue }
        if ($drop -contains $f) { continue }
        $out += $g
    }
    return ,$out
}

# ---- 2. THE ARMS: name -> the ONE thing it changes -----------------------
# `drop` lists the live flags this arm replaces; `add` is what it uses
# instead. Everything else comes from live, automatically, for ever.
$arms = @(
  # --- confidence: the question with the most money on it ---
  @{ n="arm-pin0.985";      drop=@();                    add=@("--pin","0.985") },
  @{ n="arm-pin0.99";       drop=@();                    add=@("--pin","0.99") },
  # --- how humble the volatility model is ---
  # --- the hedge, which is where the money has been going ---
  # 2026-09-22: live itself went to --no-hedge-prop (v-hedgefull) and dropped
  # --hedge-price (v-hedgelastweek) on 09-21, which turned arm-hedgeprop-off
  # and arm-hedge-noprice into exact copies of live measuring nothing. Each
  # now tests the setting live LEFT, and hedge60 tests v-hedge25 itself.
  # --- the 45-second leg ---
  @{ n="arm-early-off";     drop=@("--early-tau","--early-frac","--early-min-price",
                                   "--early-max-edge"); add=@() },
  # 2026-09-22 v-early-third: live runs the leg at a third; the operator asked
  # to "measure which would have been the best idea in hindsight" -- full size
  # here, off in arm-early-off, live is the third.
  @{ n="arm-early-full";    drop=@("--early-frac");      add=@("--early-frac","1.0") },
  @{ n="arm-early-cap975";  drop=@();                    add=@("--early-max-price","0.975") },
  # --- sizing ---
  @{ n="arm-brake3";        drop=@("--bank-brake");      add=@("--bank-brake","3.00") },
  # 2026-09-22 (missed-deals D_plan R1): count a per-market attempt only when
  # an ORDER IS SENT. MAX_ATTEMPTS_PER_MARKET=3 is counted at the SIGNAL point
  # today, so three refusals inside 150 ms lock a market out of the whole
  # close (13 post-fix lockouts in 12 closes, 11 still had a standing offer at
  # >= 99.5%). Live is unflagged; this is the only bot with it on.
  @{ n="arm-attempt-send";  drop=@();                    add=@("--attempts-on-send") },
  # 2026-09-23 (signature D_plan R1): size up when the model's own confidence
  # in the side we buy was under 0.50 at a reading 5 s+ earlier in the same
  # close. 66 markets, 62 closes, 0 money-losers, +$2.95/mkt against +$0.70
  # book-wide; money stable on every leave-one-day-out, significance marginal
  # -- hence paper. --doubt-mult is REFUSED with --live, and sync strips
  # --live, so these two are the only bots running it.
  @{ n="arm-doubt15";       drop=@();                    add=@("--doubt-mult","1.5") },
  @{ n="arm-doubt125";      drop=@();                    add=@("--doubt-mult","1.25") },
  # v-lateadd (2026-09-24): a FULL position may add 0.5 x SIZE inside the last
  # 15 s when the ask is at or above what we paid. Measured +$95/16 d with one
  # losing add on the per-second rebuild (results/cf_2026-09-24/); PAPER FIRST.
  # 2026-09-24 04:4xZ: the seven sigma_stress arms were RETIRED: confidence tightening
  # at 21-45 s was refuted with numbers tonight, the loosening ones add the loss class,
  # and RAM commit stood at 23.4 of 27.8 GB with 34 arms (a full commit charge can
  # fail an allocation in the MONEY bot). Rows kept in git history.
  # 2026-09-24 04:35Z: ten more arms RETIRED for memory (commit 22.5 of 27.8 GB, 40 python
  # processes; the harness killed a shell for low memory) -- the hedge family (settled
  # by the 820-position replay: 0.40 all-at-once is best), pin 0.97/0.975/0.98 (the bar
  # is not moving; 0.985/0.99 stay), band15 (-$63 h2h), early60, brake6. Rows in git.
  # 2026-09-24 09:2xZ: arm-friday (a 09-19 flag set; arm-afternoon and arm-live-frozen are
  # the controls now) and arm-hedge-slip0 (the slip question is settled: live runs 0.10)
  # retired -- a second low-memory shell kill; keep the fleet under ~15.
  @{ n="arm-lateadd-off";   drop=@("--rebuy-late-tau","--rebuy-late-frac"); add=@() },
  # 2026-09-24 04:2xZ: entries with under 2c of edge after fee were 314 of the 763
  # markets that survive tonight's rules, 9 of their 19 losers, net +$15 --
  # break-even trades. A 2c floor on the engine: same money (+$5..+$26 / 16 d),
  # half the loss dollars, 40% fewer entries, but MIXED by week (+$39 / -$34).
  # (A 97.5c ceiling was tried first and is worse: -$114..-$143; not the same thing.)
  @{ n="arm-edge2c";        drop=@();                    add=@("--edge-floor","2.0") },
  # 2026-09-24 08:xxZ (IDEAS item 2): the hourly BTC strike ladder, paper only
  # (--series is refused with --live). Bar: 7 days, >= 30 fired closes, 0 paper
  # losses at <= 30 s, >= 660 captured contracts, offers on >= 15 cheap closes.
  @{ n="arm-btcd";          drop=@();                    add=@("--series","KXBTCD") },
  # 2026-09-24 08:xxZ (results/PREREG_fresh.md): with more than 20 s left, refuse a
  # level posted under 500 ms ago. Live = this arm + the fresh entries, so the
  # refused set's real outcomes are live's own fills. Bar: 7 days, then armh2h2.
  @{ n="arm-fresh500";      drop=@();                    add=@("--fresh-min-age-ms","500","--fresh-tau-min","20") }
)
if ($Only) { $arms = @($arms | Where-Object { $_.n -like "*$Only*" }) }

# ---- 2b. FROZEN BASELINES: NOT synced, on purpose -----------------------
# The operator, 2026-09-20: *"Can there be two versions of the ones that are
# doing good? If they're working they're working, why break them"* and
# *"reverting to something like Friday that did good in the week"*.
#
# He is right that syncing everything throws away the one thing a long-lived
# arm is good for: a STABLE reference. So the board now holds both kinds.
#
#   SYNCED   = live + one change. Answers "is this flag better?" Must move
#              with live or the comparison means nothing.
#   FROZEN   = a whole configuration, pinned for ever. Answers "was the bot
#              better on <date>?" Must NOT move, for the same reason.
#
# pinvin_0912*/0913* are already frozen this way, as separate script files.
# These are frozen by flag list instead, which is enough for a config that
# today's code can still express.
#
# FRIDAY (2026-09-18) is the first, at the operator's request: +$64.57 on the
# account and ZERO losing crypto closes, the best loss record of the week.
# Its exact settings are read off that day's own `start` record, not from
# memory: early_max_edge 3.0, band-mult 1.5, bank_brake 4.08, late boost OFF,
# and none of --hedge-slip / --extra-coin / --late-extra / --loss-cap, which
# did not exist yet. --no-hedge-prop restores its all-or-nothing hedge.
#
# It runs on TODAY'S code, so it keeps the crash fixes (A69/A71/A74) that are
# not flags. That is deliberate: this tests Friday's TRADING RULES, not
# Friday's bugs.
$frozen = @(
  # and the live rules of the 2026-09-20 sync, PINNED. This used to be x=@()
  # -- "seed from live once, then leave it alone" -- but "once" meant "every
  # time it is not running", so an arm halted by a brake came back as TODAY'S
  # live bot and silently stopped being frozen. The list is restart_bot.ps1
  # at 6ff3cce (live at the 09-20 sync), minus --live/--size/--minutes and
  # the --max-losses brake above: hedge at 0.60 with the 0.60 price gate and
  # A76 proportional hedging on (the code default then and now).
  @{ n="arm-live-frozen"; x=@(
      "--loss-abort","-60.00","--max-positions","3",
      "--improve-scope","market","--pick","best","--max-per-market","2",
      "--improve-max","0.010","--min-fill-frac","0","--sweep-depth",
      "--depth-ladder","--jump-gate","--hedge-belief","0.60",
      "--early-tau","45","--early-frac","1.0","--early-min-price","0.90",
      "--early-max-edge","10.0","--hedge-price","0.60","--hedge-slip","0.03",
      "--late-tau","10","--late-mult","1.5","--late-pin","0.9975",
      "--late-jump","2.0","--extra-coin","1","--late-extra","1",
      "--late-extra-tau","15","--bank-brake","4.00","--loss-cap","200") }
)

# ---- 3. BUILD AND VALIDATE EVERYTHING BEFORE STOPPING ANYTHING ----------
$plan = @()
foreach ($a in $arms) {
    $full = @("-u", "$repo\research\pinrun.py", "--size", "20", "--minutes", "4320") +
            (BaseWithout $a.drop | ForEach-Object { $_ }) + $a.add + @("--arm-name", $a.n)
    $flat = @($full | ForEach-Object { $_ })
    foreach ($t in $flat) {
        if ($t -isnot [string]) { throw "REFUSING: non-string token in $($a.n)" }
        if ($t -eq "--live")    { throw "REFUSING: --live survived stripping for $($a.n)" }
    }
    if ($flat -contains "--max-losses") { throw "REFUSING: --max-losses survived stripping for $($a.n)" }
    $baseLine = ((BaseWithout @()) | ForEach-Object { $_ }) -join ' '
    $armLine  = (@((BaseWithout $a.drop | ForEach-Object { $_ }) + $a.add) | ForEach-Object { $_ }) -join ' '
    if ($armLine -eq $baseLine -or ($a.add.Count -and ($baseLine -like "*$($a.add -join ' ')*") -and ($a.drop.Count -eq 0))) {
        "  WARNING: $($a.n) is IDENTICAL to live -- live adopted what it tests; it measures nothing until it is flipped"
    }
    if ($flat.Count -lt 8) { throw "REFUSING: $($a.n) built only $($flat.Count) args" }
    $plan += [pscustomobject]@{ Name = $a.n; Argv = $flat }
}
# the frozen ones: a whole config, NOT rebuilt from live. arm-live-frozen is
# the exception -- it is seeded from live ONCE and then left alone, which is
# what "frozen as of today" means.
foreach ($fz in $frozen) {
    $body = if ($fz.x.Count) { $fz.x } else { (BaseWithout @() | ForEach-Object { $_ }) }
    $full = @("-u", "$repo\research\pinrun.py", "--size", "20", "--minutes", "4320") +
            $body + @("--arm-name", $fz.n)
    $flat = @($full | ForEach-Object { $_ })
    foreach ($t in $flat) {
        if ($t -isnot [string]) { throw "REFUSING: non-string token in $($fz.n)" }
        if ($t -eq "--live")    { throw "REFUSING: --live in frozen arm $($fz.n)" }
    }
    if ($flat -contains "--max-losses") { throw "REFUSING: --max-losses in $($fz.n) -- a paper arm has no watchdog, the brake ends it for good" }
    # A FROZEN ARM IS NEVER RESTARTED BY THIS SCRIPT once it is up. Restarting
    # it would re-seed arm-live-frozen from a changed live bot and silently
    # turn the baseline into a moving target -- the exact rot this file
    # exists to stop.
    $already = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
                 Where-Object { $_.CommandLine -like "*--arm-name $($fz.n)*" })
    if ($already.Count) { "  frozen $($fz.n) already running (left alone)"; continue }
    $plan += [pscustomobject]@{ Name = $fz.n; Argv = $flat }
}
"built $($plan.Count) arm command lines from the LIVE bot's own settings"
"live base: $(($groups | ForEach-Object { $_[0] }) -join ' ')"

if ($WhatIf) {
    foreach ($p in $plan) { "  {0,-20} {1}" -f $p.Name, (($p.Argv | Select-Object -Skip 2) -join ' ') }
    "WhatIf: nothing stopped, nothing started"
    return
}

# ---- 4. RETIRE EVERY STALE ARM FIRST ------------------------------------
# An arm not in the plan above is running a flag list from whenever it was
# launched, which is exactly the rot this script exists to end. Leaving it
# alongside a synced arm would put two answers to the same question on the
# board, and the board cannot tell which is which.
#
# pinvin_* is deliberately excluded: those are frozen snapshots and old code
# is their entire purpose. The live bot is excluded twice over.
$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'"
$keep = @($plan | ForEach-Object { $_.Name })
$stale = @($procs | Where-Object {
    $_.CommandLine -like '*pinrun.py*' -and
    $_.CommandLine -notlike '*--live*' -and
    $_.CommandLine -notlike '*pinvin_*' -and
    -not ($keep | Where-Object { $_.CommandLine -like "*--arm-name $_*" })
})
# the -like above cannot see $_ from the outer pipe; do it explicitly
$stale = @()
foreach ($p in $procs) {
    $cl = $p.CommandLine
    if (-not $cl) { continue }
    if ($cl -notlike '*pinrun.py*') { continue }
    if ($cl -like '*--live*' -or $cl -like '*pinvin_*') { continue }
    # a FROZEN arm is never stale -- not moving is its job
    if ($cl -like '*--arm-name arm-friday*' -or $cl -like '*--arm-name arm-live-frozen*') { continue }
    $isKeeper = $false
    foreach ($k in $keep) { if ($cl -like "*--arm-name $k*") { $isKeeper = $true; break } }
    if (-not $isKeeper) { $stale += $p }
}
# -Only NARROWS THE PLAN, SO IT MUST DISABLE THE SWEEP. Run with -Only and
# the plan holds one arm; every other arm then looks "not in the plan" and the
# sweep retires the whole fleet. That is exactly what happened on the first
# run of this script -- 21 synced arms killed by a filter meant to start one.
# A partial run may never decide what is stale.
if ($Only -and $stale.Count) {
    "-Only is set, so the stale sweep is SKIPPED ($($stale.Count) arm(s) left alone)"
    $stale = @()
}
if ($stale.Count) {
    "retiring $($stale.Count) stale arm(s) running pre-sync flag lists:"
    foreach ($s in $stale) {
        $nm = if ($s.CommandLine -match '--arm-name (\S+)') { $matches[1] } else { "unnamed pid $($s.ProcessId)" }
        "   stop $nm"
        Stop-Process -Id $s.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}

$started = 0
foreach ($p in $plan) {
    $old = @($procs | Where-Object {
        $_.CommandLine -like "*--arm-name $($p.Name)*" -and $_.CommandLine -notlike '*--live*' })
    foreach ($o in $old) {
        Stop-Process -Id $o.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 300
    Start-Process -FilePath $py -ArgumentList $p.Argv -WorkingDirectory $repo -WindowStyle Hidden `
        -RedirectStandardOutput "$res\$($p.Name).out" -RedirectStandardError "$res\$($p.Name).err"
    "  synced $($p.Name)$(if ($old.Count) { " (replaced pid $($old[0].ProcessId))" })"
    $started++
    Start-Sleep -Milliseconds $GapMs
}
"$started arms now running LIVE'S settings plus their own one change"
"{0:N2} GB free RAM" -f ((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB)
