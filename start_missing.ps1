# start_missing.ps1 -- start ONLY the paper arms that are not running.
#
# WHY THIS EXISTS. 2026-09-20: 21 of the 34 arms on the Lab board had no
# process. They had died in the night's memory squeezes (the OS was killing
# helper shells; each arm is ~40 MB, and 15.8 GB of RAM holds all of them --
# the pressure was elsewhere). Nothing could bring them back one at a time:
#   - boot_all.ps1 starts the whole set only when ZERO arms are running, so
#     the comparison arms share a window;
#   - start_bands / start_early60 / start_sigma start their whole group with
#     no "already running" check, so running one duplicates the survivors;
#   - restart_arms.ps1 relaunches what IS running and cannot see what is not.
# The desktop app's Play button now restarts any arm it has seen running --
# but it had never seen these, so this is the once-off that gets them back
# under names the app can prove.
#
# THE TABLE BELOW IS A COPY. boot_all.ps1's arm table is canonical for the
# band, pin and e60 arms; start_sigma.ps1 for the sigma arms; the flip2 arm
# comes from start_early60.ps1. If those change, change this.
#
# An arm counts as RUNNING if any python.exe command line carries its
# --arm-name (the same test the desktop app makes), or -- for the sigma arms
# -- its exact --sigma-stress value.
#
#     powershell -ExecutionPolicy Bypass -File C:\kals-repo\start_missing.ps1
#     ... -WhatIf     lists what it would start and starts nothing
param([switch]$WhatIf)
$py   = "C:\Python314\python.exe"
$repo = "C:\kals-repo"
$res  = "$repo\results"

$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'"
$cls = @($procs | ForEach-Object { $_.CommandLine } | Where-Object { $_ })

function Running($needle) {
    foreach ($c in $cls) { if ($c -like "*$needle*") { return $true } }
    return $false
}

$live = @("-u", "$repo\research\pinrun.py", "--size", "20", "--minutes", "4320",
          "--loss-abort", "-60.00", "--max-losses", "2", "--improve-scope", "market",
          "--pick", "best", "--max-per-market", "2", "--improve-max", "0.010",
          "--min-fill-frac", "0", "--sweep-depth", "--depth-ladder", "--jump-gate")
$band = @("--bank-brake", "4.08", "--hedge-price", "0.60", "--max-positions", "3", "--hedge-belief", "0.60")
$m15  = @("--band-mult", "0.90", "0.94", "1.5")
# the sigma launcher's own base, which differs from $live (it carries the full
# v-bands live set so each arm differs from live in ONE number)
$sigcore = @("-u", "$repo\research\pinrun.py", "--size", "20", "--minutes", "4320",
             "--loss-abort", "-60.00", "--max-positions", "3", "--max-losses", "2",
             "--improve-scope", "market", "--pick", "best", "--max-per-market", "2",
             "--improve-max", "0.010", "--min-fill-frac", "0", "--sweep-depth", "--depth-ladder",
             "--jump-gate", "--hedge-belief", "0.60", "--early-tau", "45", "--early-frac", "1.0",
             "--early-min-price", "0.90", "--early-max-edge", "3.0", "--bank-brake", "4.08",
             "--hedge-price", "0.60", "--band-mult", "0.90", "0.94", "1.5",
             "--late-tau", "10", "--late-mult", "1.5", "--late-pin", "0.9975", "--late-jump", "2.0")

$arms = @(
    @{ n = "arm-b-control";     needle = "--arm-name arm-b-control";     a = $live + $band + @("--early-tau", "45", "--early-frac", "1.0", "--early-min-price", "0.90", "--early-max-edge", "3.0") + $m15 },
    @{ n = "arm-b-early-open";  needle = "--arm-name arm-b-early-open";  a = $live + $band + @("--early-tau", "45", "--early-frac", "1.0", "--early-min-price", "0.80") + $m15 },
    @{ n = "arm-b-early-nocap"; needle = "--arm-name arm-b-early-nocap"; a = $live + $band + @("--early-tau", "45", "--early-frac", "1.0", "--early-min-price", "0.90") + $m15 },
    @{ n = "arm-b-skip9496";    needle = "--arm-name arm-b-skip9496";    a = $live + $band + @("--early-tau", "45", "--early-frac", "1.0", "--early-min-price", "0.90", "--early-max-edge", "3.0", "--skip-band", "0.94", "0.96") + $m15 },
    @{ n = "arm-b-skip975";     needle = "--arm-name arm-b-skip975";     a = $live + $band + @("--early-tau", "45", "--early-frac", "1.0", "--early-min-price", "0.90", "--early-max-edge", "3.0", "--skip-band", "0.94", "0.975") + $m15 },
    @{ n = "arm-b-mult2";       needle = "--arm-name arm-b-mult2";       a = $live + $band + @("--early-tau", "45", "--early-frac", "1.0", "--early-min-price", "0.90", "--early-max-edge", "3.0", "--band-mult", "0.90", "0.94", "2.0") },
    @{ n = "arm-b-harder";      needle = "--arm-name arm-b-harder";      a = $live + $band + @("--early-tau", "45", "--early-frac", "1.0", "--early-min-price", "0.90", "--early-max-edge", "3.0", "--skip-band", "0.94", "0.975", "--band-mult", "0.80", "0.90", "2.0", "--band-mult", "0.90", "0.94", "2.0") },
    @{ n = "arm-b-all";         needle = "--arm-name arm-b-all";         a = $live + $band + @("--early-tau", "45", "--early-frac", "1.0", "--early-min-price", "0.80", "--skip-band", "0.94", "0.975", "--band-mult", "0.80", "0.90", "2.0", "--band-mult", "0.90", "0.94", "2.0") },
    @{ n = "arm-pin0.97";       needle = "--pin 0.97 ";                  a = $live + @("--max-positions", "3", "--hedge-belief", "0.60", "--pin", "0.97") },
    @{ n = "arm-pin0.975";      needle = "--pin 0.975";                  a = $live + @("--max-positions", "3", "--hedge-belief", "0.60", "--pin", "0.975") },
    @{ n = "arm-pin0.98";       needle = "--pin 0.98 ";                  a = $live + @("--max-positions", "3", "--hedge-belief", "0.60", "--pin", "0.98") },
    @{ n = "arm-pin0.985";      needle = "--pin 0.985";                  a = $live + @("--max-positions", "3", "--hedge-belief", "0.60", "--pin", "0.985") },
    @{ n = "arm-pin0.99";       needle = "--pin 0.99";                   a = $live + @("--max-positions", "3", "--hedge-belief", "0.60", "--pin", "0.99") },
    @{ n = "arm-e60-third";     needle = "--arm-name arm-e60-third";     a = $live + $band + @("--early-tau", "60", "--early-frac", "0.333", "--early-min-price", "0.90", "--early-max-edge", "3.0") + $m15 },
    @{ n = "arm-e60-full";      needle = "--arm-name arm-e60-full";      a = $live + $band + @("--early-tau", "60", "--early-frac", "1.0", "--early-min-price", "0.90", "--early-max-edge", "3.0") + $m15 },
    @{ n = "arm-e60-open";      needle = "--arm-name arm-e60-open";      a = $live + $band + @("--early-tau", "60", "--early-frac", "0.333", "--early-min-price", "0.80") + $m15 },
    @{ n = "arm-e60-flip2";     needle = "--arm-name arm-e60-flip2";     a = $live + $band + @("--early-tau", "60", "--early-frac", "0.333", "--early-min-price", "0.90", "--early-max-edge", "3.0", "--flip-mult", "2.0") + $m15 },
    @{ n = "arm-sigma0.40";     needle = "--sigma-stress 0.40";          a = $sigcore + @("--sigma-stress", "0.40") },
    @{ n = "arm-sigma0.60";     needle = "--sigma-stress 0.60";          a = $sigcore + @("--sigma-stress", "0.60") },
    @{ n = "arm-sigma0.80";     needle = "--sigma-stress 0.80";          a = $sigcore + @("--sigma-stress", "0.80") },
    @{ n = "arm-sigma1.25";     needle = "--sigma-stress 1.25";          a = $sigcore + @("--sigma-stress", "1.25") },
    @{ n = "arm-sigma1.50";     needle = "--sigma-stress 1.50";          a = $sigcore + @("--sigma-stress", "1.50") },
    @{ n = "arm-sigma2.00";     needle = "--sigma-stress 2.00";          a = $sigcore + @("--sigma-stress", "2.00") }
)

$started = 0; $skipped = 0
foreach ($a in $arms) {
    if (Running $a.needle) { "  running : $($a.n)"; $skipped++; continue }
    foreach ($x in $a.a) { if ($x -like "*--live*") { throw "REFUSING: --live in a paper argv for $($a.n)" } }
    if ($WhatIf) { "  WOULD START: $($a.n)"; $started++; continue }
    Start-Process -FilePath $py -ArgumentList ($a.a + @("--arm-name", $a.n)) `
        -WorkingDirectory $repo -WindowStyle Hidden `
        -RedirectStandardOutput "$res\$($a.n).out" -RedirectStandardError "$res\$($a.n).err"
    "  STARTED : $($a.n)"
    $started++
    Start-Sleep -Seconds 3
}
"$started started, $skipped already running"
$free = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 2)
"free RAM now: $free GB"
