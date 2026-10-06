# relaunch_twin_1006.ps1 -- when the PAPER arm-live-twin (pid 4228512, 7-day --minutes ends ~2026-10-06 18:59Z) exits,
# start a fresh copy with the identical command line, so the revert comparisons (revert-0925b, revert-0914) and the
# toxic/norebuy arms keep their newer-rules baseline. PAPER ONLY: refuses if the command line contains --live.
$old = 4228512
$cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$old").CommandLine
if (-not $cmd) { "twin $old not running; nothing to copy"; exit 1 }
if ($cmd -match '--live') { "REFUSING: command line contains --live"; exit 1 }
$exe = "C:\Python314\python.exe"
$args1 = $cmd.Substring($cmd.IndexOf('-u '))
Set-Content -Path "C:\kals-repo\results\relaunch_twin_1006.cmd.txt" -Value $args1 -Encoding utf8
while (Get-Process -Id $old -ErrorAction SilentlyContinue) { Start-Sleep 20 }
Start-Sleep 5
$p = Start-Process -FilePath $exe -ArgumentList $args1 -WorkingDirectory "C:\kals-repo" -WindowStyle Hidden `
    -RedirectStandardOutput "C:\kals-repo\results\arm-live-twin-2.out" -RedirectStandardError "C:\kals-repo\results\arm-live-twin-2.err" -PassThru
"relaunched paper twin as pid $($p.Id) at $((Get-Date).ToUniversalTime().ToString('u'))"
