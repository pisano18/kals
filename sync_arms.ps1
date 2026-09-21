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
$liveCl = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
           Where-Object { $_.CommandLine -like '*--live*' } |
           Select-Object -First 1).CommandLine
if (-not $liveCl) { throw "the live bot is not running -- nothing to sync arms TO" }

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
  @{ n="arm-pin0.97";       drop=@();                    add=@("--pin","0.97") },
  @{ n="arm-pin0.975";      drop=@();                    add=@("--pin","0.975") },
  @{ n="arm-pin0.98";       drop=@();                    add=@("--pin","0.98") },
  @{ n="arm-pin0.985";      drop=@();                    add=@("--pin","0.985") },
  @{ n="arm-pin0.99";       drop=@();                    add=@("--pin","0.99") },
  # --- how humble the volatility model is ---
  @{ n="arm-sigma0.20";     drop=@();                    add=@("--sigma-stress","0.20") },
  @{ n="arm-sigma0.40";     drop=@();                    add=@("--sigma-stress","0.40") },
  @{ n="arm-sigma0.60";     drop=@();                    add=@("--sigma-stress","0.60") },
  @{ n="arm-sigma0.80";     drop=@();                    add=@("--sigma-stress","0.80") },
  @{ n="arm-sigma1.25";     drop=@();                    add=@("--sigma-stress","1.25") },
  @{ n="arm-sigma1.50";     drop=@();                    add=@("--sigma-stress","1.50") },
  @{ n="arm-sigma2.00";     drop=@();                    add=@("--sigma-stress","2.00") },
  # --- the hedge, which is where the money has been going ---
  @{ n="arm-nohedge";       drop=@("--hedge-belief");    add=@("--hedge-belief","0.01") },
  @{ n="arm-hedgeprop-off"; drop=@();                    add=@("--no-hedge-prop") },
  @{ n="arm-hedge-noprice"; drop=@("--hedge-price");     add=@() },
  @{ n="arm-hedge-slip0";   drop=@("--hedge-slip");      add=@() },
  # --- the 45-second leg ---
  @{ n="arm-early-off";     drop=@("--early-tau","--early-frac","--early-min-price",
                                   "--early-max-edge"); add=@() },
  @{ n="arm-early-cap975";  drop=@();                    add=@("--early-max-price","0.975") },
  @{ n="arm-early60";       drop=@("--early-tau");       add=@("--early-tau","60") },
  # --- sizing ---
  @{ n="arm-brake3";        drop=@("--bank-brake");      add=@("--bank-brake","3.00") },
  @{ n="arm-brake6";        drop=@("--bank-brake");      add=@("--bank-brake","6.00") },
  @{ n="arm-band15";        drop=@();                    add=@("--band-mult","0.90","0.94","1.5") }
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
  @{ n="arm-friday"; x=@(
      "--loss-abort","-60.00","--max-positions","3","--max-losses","2",
      "--improve-scope","market","--pick","best","--max-per-market","2",
      "--improve-max","0.010","--min-fill-frac","0","--sweep-depth",
      "--depth-ladder","--jump-gate","--hedge-belief","0.60",
      "--early-tau","45","--early-frac","1.0","--early-min-price","0.90",
      "--early-max-edge","3.0","--hedge-price","0.60",
      "--band-mult","0.90","0.94","1.5","--bank-brake","4.08",
      "--no-hedge-prop") },
  # and today's live rules, pinned, so there is always a stable reference for
  # "what the bot was doing when this question was asked"
  @{ n="arm-live-frozen"; x=@() }
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
