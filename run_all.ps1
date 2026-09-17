# run_all.ps1 -- watchdog. Keeps both recorders alive across crashes.
# The collector reconnects its WebSocket, but if the PYTHON PROCESS dies
# (unhandled exception, OOM, Windows update) everything stops silently and
# you lose the rest of the 48 hours. This restarts them.
#
#   powershell -ExecutionPolicy Bypass -File run_all.ps1
#
$ErrorActionPreference = "Continue"
$Dir    = "C:\kals"
$KeyId  = "5163259c-ecb0-4966-9053-0d2776cf061e"
$KeyFile= "kalshi.pem"
Set-Location $Dir
New-Item -ItemType Directory -Force -Path "$Dir\logs" | Out-Null
# 2026-09-17: our own pid, so boot_all.ps1 can see this watchdog is alive
# without reading a command line (which Windows may return empty).
$PID | Set-Content "$Dir\logs\run_all.pid" -Encoding ascii

function Start-Job2($name, $args2) {
    Start-Process -FilePath "python" -ArgumentList $args2 `
        -RedirectStandardOutput "$Dir\logs\$name.out.log" `
        -RedirectStandardError  "$Dir\logs\$name.err.log" `
        -NoNewWindow -PassThru
}

$jobs = @{}
while ($true) {
    foreach ($j in @(
        @{n="collector"; a="kalshi_collector.py --key-id $KeyId --key-file $KeyFile --out ./kalshi_data"},
        @{n="feeds";     a="crypto_feeds.py --out ./feed_data"}
    )) {
        if (-not $jobs[$j.n] -or $jobs[$j.n].HasExited) {
            if ($jobs[$j.n]) { Write-Host "$(Get-Date -f HH:mm) RESTART $($j.n)" }
            $jobs[$j.n] = Start-Job2 $j.n $j.a
            Write-Host "$(Get-Date -f HH:mm) started $($j.n) pid=$($jobs[$j.n].Id)"
        }
    }
    # disk + freshness check every 5 min
    $free = [math]::Round((Get-PSDrive C).Free/1GB,1)
    $kb = (Get-ChildItem "$Dir\kalshi_data" -Recurse -File -EA SilentlyContinue |
           Measure-Object Length -Sum).Sum/1MB
    $fb = (Get-ChildItem "$Dir\feed_data"   -Recurse -File -EA SilentlyContinue |
           Measure-Object Length -Sum).Sum/1MB
    Write-Host ("$(Get-Date -f HH:mm) disk {0}GB free | kalshi {1:N1}MB | feeds {2:N1}MB" -f $free,$kb,$fb)
    if ($free -lt 5) { Write-Host "LOW DISK - stopping" ; break }
    Start-Sleep -Seconds 300
}
