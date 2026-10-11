# restart_race_1011.ps1 -- v-race-snowball on the live coin race (main account), 2026-10-11.
# Operator 2026-10-11: "I don't want to cap any growth ... Every account should be automatically increasing bets with their bank."
# New argv = the old one + --contracts-per-bank 0.019048 --stake-per-bank 0.038095 (20 and $40 at a $1,050 bank, growing with it).
# research/pinracearm.py sha 19355ccf6853 (built + reviewed GO 10-11: results/research_2026-10 / scratchpad snowball race_*).
# Validates first (self-test with the new argv, exactly one live race bot, no stop file, boot_all carries the NEW line), then:
# stop file -> old race bot exits -> wait out boot_all -> delete stop file -> start the new one -> confirm one live race bot.
# REVERT: put the old line back in boot_all.ps1 (results/VERSIONS.md v-race-snowball) and run this script's steps with the old argv.
param([switch]$DryRun)
$ErrorActionPreference = "Stop"
$repo = "C:\kals-repo"; $res = "$repo\results"; $py = "C:\Python314\python.exe"
function Say($m) { $l = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"), $m; Write-Output $l; Add-Content -Path "$res\restart_race_1011.log" -Value $l -Encoding utf8 }
function Live($like) { @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like $like }) }
function BootAlive() { @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object { $_.CommandLine -like '*boot_all.ps1*' }).Count -gt 0 }

$race = @("-u", "research/pinracearm.py", "--live", "--max-contracts", "20", "--max-stake", "40", "--live-max-losses", "2", "--live-rolling-stake", "--live-tau-max", "30", "--live-min-price", "0.90", "--live-max-legs", "5", "--live-confirm", "5", "--live-clock-tau", "20", "--minutes", "10080", "--log", "C:/kals-repo/results/pinracepenny-live.jsonl", "--model", "fair", "--tau-max", "60", "--min-price", "0.80", "--min-edge", "0.00", "--contracts-per-bank", "0.019048", "--stake-per-bank", "0.038095")
$bootLine = 'a = @("-u", "research/pinracearm.py", "--live", "--max-contracts", "20", "--max-stake", "40", "--live-max-losses", "2", "--live-rolling-stake", "--live-tau-max", "30", "--live-min-price", "0.90", "--live-max-legs", "5", "--live-confirm", "5", "--live-clock-tau", "20", "--minutes", "10080", "--log", "C:/kals-repo/results/pinracepenny-live.jsonl", "--model", "fair", "--tau-max", "60", "--min-price", "0.80", "--min-edge", "0.00", "--contracts-per-bank", "0.019048", "--stake-per-bank", "0.038095");'

Say "validating (DryRun=$DryRun)"
$out = & $py @("-u", "research/pinracearm.py", "--selftest") | Out-String
if ($LASTEXITCODE -ne 0) { Say "SELF-TEST FAILED"; exit 1 }
Say "self-test ok"
if (Test-Path "$res\pinracepenny.stop") { Say "stop file present, refusing"; exit 1 }
$old = @(Live '*pinracearm.py --live*')
if ($old.Count -ne 1) { Say "expected exactly one live race bot, found $($old.Count) -- refusing"; exit 1 }
$boot = Get-Content "$repo\boot_all.ps1" -Raw
if (-not $boot.Contains($bootLine)) { Say "boot_all.ps1 does not carry the NEW race argv -- refusing"; exit 1 }
Say "ok: old race bot pid $($old[0].ProcessId); boot_all carries the new argv"
if ($DryRun) { Say "DRY RUN: nothing changed"; exit 0 }

New-Item -ItemType File -Path "$res\pinracepenny.stop" -Force | Out-Null
Say "stop file written; waiting for pid $($old[0].ProcessId) to exit"
for ($i = 0; $i -lt 900 -and (Get-Process -Id $old[0].ProcessId -ErrorAction SilentlyContinue); $i++) { Start-Sleep 1 }
if (Get-Process -Id $old[0].ProcessId -ErrorAction SilentlyContinue) { Say "old race bot did not exit in 15 min -- stop file kept; check by hand"; exit 1 }
Say "old race bot exited after ~$i s"
for ($i = 0; $i -lt 60 -and (BootAlive); $i++) { Start-Sleep 1 }
if (BootAlive) { Say "boot_all still running after 60 s -- stop file kept; check by hand"; exit 1 }
Remove-Item "$res\pinracepenny.stop" -Force
$p = Start-Process -FilePath $py -ArgumentList $race -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput "$res\pinracepenny-live.out" -RedirectStandardError "$res\pinracepenny-live.err" -PassThru
Say "started race bot $($p.Id): $($race -join ' ')"
Start-Sleep 20
$now = @(Live '*pinracearm.py --live*')
Say "live race bots now: $($now.Count) ($(($now | ForEach-Object { $_.ProcessId }) -join ', '))"
