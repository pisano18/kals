# watch_hourly.ps1 -- sample the hourly book through every hourly close.
#
# research/pinhourly.py --at-close waits for 70 s before the hour and samples
# through it, then exits. One close per run. This loops it so an overnight
# session collects a close an hour instead of one.
#
# READ-ONLY. pinhourly imports no order module and every request it makes is a
# GET. This script starts nothing else and kills nothing.
#
#     powershell -ExecutionPolicy Bypass -File C:\kals-repo\watch_hourly.ps1
#
param([int]$Hours = 12)
$repo = "C:\kals-repo"
$log  = "$repo\results\watch_hourly.log"
$out  = "$repo\results\hourly_book_sample.jsonl"
function Say($m) {
  $l = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"), $m
  Write-Output $l; Add-Content -Path $log -Value $l -Encoding utf8
}
Say "watch_hourly starting: $Hours closes, appending to $(Split-Path $out -Leaf)"
for ($i = 1; $i -le $Hours; $i++) {
  Say "waiting for close $i of $Hours"
  & "C:\Python314\python.exe" "$repo\research\pinhourly.py" --at-close --out $out 2>&1 |
      Select-Object -Last 3 | ForEach-Object { Say ("  " + $_) }
  if (Test-Path $out) {
    $n = (Get-Content $out -ErrorAction SilentlyContinue | Measure-Object -Line).Lines
    Say "  sample file now $n rows"
  }
}
Say "watch_hourly done"
