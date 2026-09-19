# restart_arms.ps1 -- relaunch every PAPER arm on the current code.
#
# AMENDMENT 66 (2026-09-19). An arm reads the live bot's contract size from
# results/pinrun-live-size.json, so its dollars are comparable with live's.
# Arms started before A66 do not have that code and stay pinned at --size:
# measured 2026-09-19, ZERO autosize records across 43 arms while live ran
# 109 contracts. They have to be restarted once to pick it up.
#
# RESTARTING IS SAFE FOR CONTINUITY. pinlab.join_logs treats an arm as EVERY
# log matching its selector, joined oldest-first with the gap left in, so a
# restarted arm keeps its whole history. What it does NOT keep is the process,
# so anything unsettled at the moment of the kill is simply not recorded.
#
#     powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_arms.ps1
#     ...              -File C:\kals-repo\restart_arms.ps1 -WhatIf
#
param([switch]$WhatIf, [int]$GapMs = 1500)

$ErrorActionPreference = "Stop"
$py   = "C:\Python314\python.exe"
$repo = "C:\kals-repo"
$res  = "$repo\results"

# --- 1. FIND THEM, AND PROVE WHAT THEY ARE ---------------------------------
# A paper arm runs pinrun.py (or a pinvin_*.py copy) WITHOUT --live. The
# --live test is the whole safety of this script: the money bot must never be
# in this list, and restart_bot.ps1 is the only thing allowed to touch it.
$all = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
       Where-Object { $_.CommandLine -match 'pinrun\.py|pinvin_\w+\.py' }

$live  = @($all | Where-Object { $_.CommandLine -like '*--live*' })
$arms  = @($all | Where-Object { $_.CommandLine -notlike '*--live*' })

"found $($arms.Count) paper arm(s); $($live.Count) live bot(s) left alone"
foreach ($l in $live) { "  LIVE (untouched): pid $($l.ProcessId)" }
if ($arms.Count -eq 0) { "nothing to do"; return }

# --- 2. CAPTURE EVERY COMMAND LINE **BEFORE** KILLING ANYTHING -------------
# The 2026-09-19 lesson from restart_bot.ps1: build and validate the thing you
# are going to relaunch with BEFORE you stop what is running, or a bad parse
# leaves the arm dead with nothing to restart it.
$plan = @()
foreach ($p in $arms) {
  $cl = $p.CommandLine
  # split the command line into argv, honouring quotes
  $argv = [System.Text.RegularExpressions.Regex]::Matches($cl, '(?:"([^"]*)"|(\S+))') |
          ForEach-Object { if ($_.Groups[1].Success) { $_.Groups[1].Value } else { $_.Groups[2].Value } }
  if ($argv.Count -lt 2) { "  SKIP pid $($p.ProcessId): cannot parse its command line"; continue }
  $exe  = $argv[0]
  $rest = @($argv[1..($argv.Count - 1)])
  if (-not ($rest -join ' ') -match 'pinrun\.py|pinvin_') {
    "  SKIP pid $($p.ProcessId): parsed args do not name a bot script"; continue
  }
  if (($rest -join ' ') -like '*--live*') {
    "  REFUSING pid $($p.ProcessId): --live survived the parse"; continue
  }
  $tag = ($rest | Where-Object { $_ -like '*pinvin_*' } | Select-Object -First 1)
  if (-not $tag) { $tag = "arm" } else { $tag = [IO.Path]::GetFileNameWithoutExtension($tag) }
  $plan += [pscustomobject]@{ Pid = $p.ProcessId; Exe = $exe; Args = $rest; Tag = $tag }
}

"planned $($plan.Count) restart(s)"
if ($plan.Count -ne $arms.Count) {
  "REFUSING: $($arms.Count) arms found but only $($plan.Count) parsed. " +
  "Fix the parse before killing anything."
  return
}

if ($WhatIf) {
  foreach ($q in $plan) { "  would restart pid $($q.Pid): $($q.Args -join ' ')" }
  return
}

# --- 3. the mirror must exist, or every arm restarts and stays pinned ------
$mirror = "$res\pinrun-live-size.json"
if (-not (Test-Path $mirror)) {
  "REFUSING: $mirror does not exist, so a restarted arm has nothing to copy " +
  "and would come up pinned at --size -- exactly the bug this fixes."
  return
}
"mirror: " + ((Get-Content $mirror -Raw) -replace "`r`n", " ")

# --- 4. stop, then start, one at a time ------------------------------------
$n = 0
foreach ($q in $plan) {
  try { Stop-Process -Id $q.Pid -Force -ErrorAction Stop }
  catch { "  could not stop pid $($q.Pid): $($_.Exception.Message)"; continue }
  $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
  $o = "$res\arm-restart-$($q.Tag)-$stamp.out"
  $e = "$res\arm-restart-$($q.Tag)-$stamp.err"
  $new = Start-Process -FilePath $q.Exe -ArgumentList $q.Args -WorkingDirectory $repo `
           -WindowStyle Hidden -PassThru -RedirectStandardOutput $o -RedirectStandardError $e
  "  pid $($q.Pid) -> $($new.Id)  $($q.Tag)"
  $n++
  Start-Sleep -Milliseconds $GapMs
}
"restarted $n arm(s)"

# --- 5. say what is alive now ----------------------------------------------
Start-Sleep -Seconds 5
$after = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
           Where-Object { $_.CommandLine -match 'pinrun\.py|pinvin_\w+\.py' -and
                          $_.CommandLine -notlike '*--live*' })
"paper arms alive now: $($after.Count)"
$stillLive = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
               Where-Object { $_.CommandLine -like '*--live*' })
"live bot alive: $($stillLive.Count)"
