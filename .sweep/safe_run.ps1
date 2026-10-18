# safe_run.ps1 -- run ONE heavy research command without starving the live bots.
# Waits until free RAM >= MinFreeMB and no other safe_run job is running (a lock file), and stays clear
# of the last 90 s before each 15-minute close (:00 :15 :30 :45) when the live bots are busiest.
# The job runs at Idle CPU priority. Usage (from bash):
#   powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/.sweep/safe_run.ps1 -WorkDir <dir> -Cmd "python -I script.py args" [-MinFreeMB 1500]
param([Parameter(Mandatory=$true)][string]$Cmd, [string]$WorkDir = (Get-Location).Path, [int]$MinFreeMB = 1500)
$lock = 'C:\kals-repo\.sweep\safe_run.lock'
function FreeMB { [int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1KB) }
function NearClose { $t = (Get-Date).ToUniversalTime(); $s = ($t.Minute % 15) * 60 + $t.Second; return ($s -ge (15*60 - 90)) }
while ($true) {
  $busy = $false
  if (Test-Path $lock) {
    $old = Get-Content $lock -ErrorAction SilentlyContinue
    if ($old -and (Get-Process -Id ([int]$old) -ErrorAction SilentlyContinue)) { $busy = $true } else { Remove-Item $lock -ErrorAction SilentlyContinue }
  }
  if (-not $busy -and (FreeMB) -ge $MinFreeMB -and -not (NearClose)) { break }
  Start-Sleep -Seconds 10
}
Set-Content -Path $lock -Value $PID
try {
  $p = Start-Process -FilePath 'cmd.exe' -ArgumentList @('/c', $Cmd) -WorkingDirectory $WorkDir -NoNewWindow -PassThru
  try { $p.PriorityClass = 'Idle' } catch {}
  $p.WaitForExit()
  exit $p.ExitCode
} finally { Remove-Item $lock -ErrorAction SilentlyContinue }
