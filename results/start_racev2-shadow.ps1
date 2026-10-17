# start_racev2-shadow.ps1 -- PAPER racev2-shadow (built 2026-10-17; spec .sweep\hunt-2026-10-15\spec-20261015-R1-C2-02
# section 2, bar 4.1): research\sweep\racev2_shadow.py --follow replays the Coin Race 1c reward filler v2 rule on each
# CLOSED hour of our own tape (read-only, one hour file at a time) with public unauthenticated GETs only (~4 an hour).
# No orders, no API key, no money: refuses if --live appears. Its self-test runs first and it refuses on a failure.
# --since is used only when no cursor exists (results\racev2-shadow.state.json); 20261017T03 is the hour before ET day
# 2026-10-17, the first full ET day after the spec was written, so the 4.1 gate reads ET days 10-17, 10-18, 10-19.
# A restart resumes from the cursor and skips every race already in results\racev2-shadow.jsonl.
# Stop: New-Item C:\kals-repo\results\racev2-shadow.stop   (it exits between hours; delete the file before restarting)
# Read: python research\sweep\racev2_shadow.py --report --days 3
$exe = "C:\Python314\python.exe"
$argv = @("-u", "C:\kals-repo\research\sweep\racev2_shadow.py", "--follow", "--hours", "336", "--since", "20261017T03")
if ($argv -contains "--live") { "REFUSING: --live in a paper process's argv"; exit 1 }
if (Test-Path "C:\kals-repo\results\racev2-shadow.stop") { "REFUSING: results\racev2-shadow.stop exists; delete it to start"; exit 1 }
$p = Start-Process -FilePath $exe -ArgumentList $argv -WorkingDirectory "C:\kals-repo" -WindowStyle Hidden `
    -RedirectStandardOutput "C:\kals-repo\results\racev2-shadow.out" -RedirectStandardError "C:\kals-repo\results\racev2-shadow.err" -PassThru
try { $p.PriorityClass = 'BelowNormal' } catch { }   # this new process only: the live bots keep the CPU first
"started PAPER racev2-shadow pid $($p.Id) at $((Get-Date).ToUniversalTime().ToString('u'))"
