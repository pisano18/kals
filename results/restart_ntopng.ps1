# Restarts the ntopng network-monitor service to free the kernel memory it leaks (2026-10-26, operator: "free up
# memory"). Measured 10-26 05:15 local: ntopng held 1,150,612 handles (825,659 to dead threads, 324,317 mutexes) --
# the next-biggest process held 11,625 -- pinning ~2.9 GB of nonpaged pool (tag Thre, 832,028 thread objects for
# 4,532 live threads) and probably ~0.7 GB of paged pool (Toke/SeAt). It grows ~0.2-0.26 GB a day since the 10-15
# boot. Restarting the SERVICE frees it at once; the bots, the phone and every other service keep running; only
# ntopng's in-memory traffic history is lost. Needs administrator rights (restart_ntopng.cmd asks for them).
$ErrorActionPreference = "Stop"
function Pools {
    $c = Get-Counter '\Memory\Pool Nonpaged Bytes', '\Memory\Pool Paged Bytes', '\Memory\Available MBytes'
    $v = $c.CounterSamples | ForEach-Object { $_.CookedValue }
    return "nonpaged pool {0:N0} MB, paged pool {1:N0} MB, available {2:N0} MB" -f ($v[0] / 1MB), ($v[1] / 1MB), $v[2]
}
$p = Get-Process ntopng -ErrorAction SilentlyContinue
Write-Output ("before: {0}; ntopng handles {1}" -f (Pools), $(if ($p) { $p.HandleCount } else { "not running" }))
Restart-Service ntopng -Force
Start-Sleep -Seconds 10
$p = Get-Process ntopng -ErrorAction SilentlyContinue
Write-Output ("after:  {0}; ntopng handles {1}; service {2}" -f (Pools), $(if ($p) { $p.HandleCount } else { "not running" }),
    (Get-Service ntopng).Status)
