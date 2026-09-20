# restart_stale_arms.ps1 -- relaunch paper arms that are running PRE-A71 code.
#
# WHY. A71 (2026-09-19 ~21:4xZ) fixed the fact that a paper arm could not
# hedge at all: `hedge_meta` was written at two live-only sites, so a paper
# position never had a strike, its belief was never computed and its hedge
# alarm never fired. Arms started BEFORE that commit are still running the
# old code in memory -- they cannot hedge, and the live bot can.
#
# THAT BREAKS THE COMPARISON IN A SPECIFIC, EXPENSIVE WAY. `arm-pin0.99` was
# started 09-19 08:21 ET and its siblings 0.97-0.985 were relaunched
# 09-20 03:42, so the "confidence" family differs in TWO things at once --
# the confidence bar AND whether the arm can insure a losing bet. The same
# split hit the sigma family (1.25/1.50/2.00 old, 0.40/0.60/0.80 new). Any
# head-to-head across that line measures the hedge, not the flag.
#
# WHAT IT DOES NOT TOUCH.
#   - `--live`. Checked twice, and the script aborts outright if it sees it.
#   - `pinvin_*.py`. Those are FROZEN SNAPSHOTS of the 09-12/09-13 bot, kept
#     deliberately on old code: restarting them onto today's pinrun would
#     destroy the only thing they are for.
#   - anything already started after the cutoff.
#
# HISTORY IS KEPT. `pinlab.join_logs` stitches an arm's logs across restarts,
# so a relaunched arm keeps every settled market it has already recorded.
#
#     powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_stale_arms.ps1 -WhatIf
#     powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_stale_arms.ps1
param([switch]$WhatIf, [datetime]$Cutoff = "2026-09-19T22:00:00Z", [int]$GapMs = 2500)

$ErrorActionPreference = "Stop"
$py   = "C:\Python314\python.exe"
$repo = "C:\kals-repo"
$res  = "$repo\results"

$all = Get-CimInstance Win32_Process -Filter "Name='python.exe'"

# EVERY CHECK BEFORE ANY KILL. restart_bot.ps1's lesson: a Stop/Start pair
# must validate the whole plan first, because a start that fails after the
# stop leaves nothing running.
$stale = @()
foreach ($p in $all) {
    $cl = $p.CommandLine
    if (-not $cl) { continue }
    if ($cl -notlike '*pinrun.py*') { continue }        # excludes pinvin_*, cmdarm, pinracearm
    if ($cl -like '*--live*')       { continue }
    if ($p.CreationDate.ToUniversalTime() -ge $Cutoff.ToUniversalTime()) { continue }
    $argv = @()
    # Split the command line into argv, dropping the exe and any -u.
    $m = [regex]::Matches($cl, '(?:"([^"]*)"|(\S+))')
    # NOT `$argv += (if ...)`: Windows PowerShell 5.1 has no inline if
    # expression and reads `if` as a command name.
    foreach ($x in $m) {
        if ($x.Groups[1].Success) { $argv += $x.Groups[1].Value }
        else                      { $argv += $x.Groups[2].Value }
    }
    $argv = @($argv | Select-Object -Skip 1 | Where-Object { $_ -ne "-u" })
    if ($argv.Count -lt 3) { throw "REFUSING: pid $($p.ProcessId) parsed to $($argv.Count) args" }
    foreach ($a in $argv) { if ($a -like "*--live*") { throw "REFUSING: --live in argv for pid $($p.ProcessId)" } }
    # NAME IT BY WHAT MAKES IT DIFFERENT. The first flag on every one of
    # these command lines is --size, so a naive "first flag" rule called six
    # separate arms "size" and they would all have written to one redirect.
    # These are the flags the whole fleet shares; the arm is whatever is left.
    $common = @("size","minutes","loss-abort","max-positions","max-losses",
                "improve-scope","pick","max-per-market","improve-max",
                "min-fill-frac","sweep-depth","depth-ladder","jump-gate",
                "hedge-belief","bank-brake","hedge-price","band-mult",
                "early-tau","early-frac","early-min-price","late-tau",
                "late-mult","late-pin","late-jump")
    $name = $null
    if ($cl -match '--arm-name\s+(\S+)')          { $name = $matches[1] }
    elseif ($cl -match '--pin\s+(\S+)')           { $name = "pin$($matches[1])" }
    elseif ($cl -match '--sigma-stress\s+(\S+)')  { $name = "sigma$($matches[1])" }
    else {
        foreach ($f in [regex]::Matches($cl, '--([\w-]+)')) {
            $flag = $f.Groups[1].Value
            if ($common -notcontains $flag) { $name = $flag; break }
        }
    }
    if (-not $name) { $name = "arm$($p.ProcessId)" }
    $stale += [pscustomobject]@{ Pid = $p.ProcessId; Argv = $argv; Name = $name
                                 Started = $p.CreationDate.ToString("MM-dd HH:mm") }
}

if ($stale.Count -eq 0) { "no stale arms -- every paper arm is on post-A71 code"; return }

"found $($stale.Count) arm(s) started before $($Cutoff.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')):"
foreach ($s in $stale) { "  pid $($s.Pid)  started $($s.Started)  $($s.Name)   ($($s.Argv.Count) args)" }
$vin = @($all | Where-Object { $_.CommandLine -like '*pinvin_*' }).Count
"leaving $vin frozen pinvin_* snapshot(s) alone -- old code is what they are for"
if ($WhatIf) { "WhatIf: nothing stopped, nothing started"; return }

$ok = 0
foreach ($s in $stale) {
    try {
        Stop-Process -Id $s.Pid -Force -ErrorAction Stop
        Start-Sleep -Milliseconds 400
        Start-Process -FilePath $py -ArgumentList (@("-u") + $s.Argv) `
            -WorkingDirectory $repo -WindowStyle Hidden `
            -RedirectStandardOutput "$res\restale-$($s.Name)-$($s.Pid).out" `
            -RedirectStandardError  "$res\restale-$($s.Name)-$($s.Pid).err"
        "  restarted $($s.Name)"
        $ok++
    } catch {
        "  FAILED on $($s.Name): $($_.Exception.Message)"
    }
    Start-Sleep -Milliseconds $GapMs
}
"$ok of $($stale.Count) restarted onto current code"
"{0:N2} GB free RAM" -f ((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB)
