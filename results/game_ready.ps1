# game_ready.ps1 -- 2026-10-27, operator: "im about to play an online game so make sure my computer is ready for that
# last night the internet situation wasnt working at all". Runs elevated (game_ready.cmd asks once). It:
#   1. stops the laptop's leftover research processes (laptop_idle.ps1: run_all watchdog, kalshi_collector,
#      crypto_feeds, cdc_record, the duplicate ladder paper; never anything with --live; the bots are on the server)
#   2. STOPS the ntopng network-monitor service for this session (it leaks kernel memory: 560,833 handles and a 1.2 GB
#      nonpaged pool tonight, and it captures every packet on the Wi-Fi adapter). Its start type is NOT changed, so it
#      comes back at the next reboot; to start it sooner: Start-Service ntopng (elevated).
#   3. prints free memory, UDP ports in use and a ping test.
# Last night's failure (System log, 10-26 22:35:08, Tcpip 4266): Windows ran out of UDP ports, which games and DNS
# both need. Nothing holds more than 11 UDP ports tonight; the watch in the Claude session alerts if it climbs again.
$ErrorActionPreference = "Continue"
function Mem {
    $os = Get-CimInstance Win32_OperatingSystem
    $np = (Get-Counter '\Memory\Pool Nonpaged Bytes').CounterSamples[0].CookedValue
    "free RAM {0:N1} GB, kernel nonpaged pool {1:N0} MB" -f ($os.FreePhysicalMemory / 1MB), ($np / 1MB)
}
Write-Host ("BEFORE: " + (Mem))
Write-Host ""
Write-Host "1. Leftover research processes:"
& "C:\kals-repo\results\laptop_idle.ps1"
Write-Host ""
Write-Host "2. ntopng network monitor:"
try {
    $p = Get-Process ntopng -ErrorAction SilentlyContinue
    if ($p) { Write-Host ("   handles before: {0}" -f $p.HandleCount) }
    Stop-Service ntopng -Force -ErrorAction Stop
    Write-Host ("   stopped (service now {0}; it starts again at the next reboot)" -f (Get-Service ntopng).Status)
} catch { Write-Host ("   COULD NOT stop ntopng: " + $_.Exception.Message) }
Start-Sleep -Seconds 5
Write-Host ""
Write-Host ("AFTER:  " + (Mem))
Write-Host ("UDP ports in use: {0} of 16,384" -f @(Get-NetUDPEndpoint -ErrorAction SilentlyContinue).Count)
foreach ($h in @("192.168.1.1", "1.1.1.1")) {
    $r = Test-Connection -ComputerName $h -Count 10 -ErrorAction SilentlyContinue
    $t = @($r | ForEach-Object { $_.ResponseTime })
    if ($t.Count) { Write-Host ("ping {0}: {1}/10 replies, avg {2:N0} ms, max {3} ms" -f $h, $t.Count, ($t | Measure-Object -Average).Average, ($t | Measure-Object -Maximum).Maximum) }
    else { Write-Host ("ping {0}: NO replies" -f $h) }
}
Write-Host ""
Write-Host "Ready. You can close this window."
