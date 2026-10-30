# pin_drop_hedgejump.ps1 -- 2026-10-30 (hedgejump6 read, scratchpad hedgejump6read\VERDICT.md). For the OPERATOR to run
# on the server (the classifier blocks the assistant from editing the live launcher).
# What the read found (pin live 10-24 01:45Z .. 10-30 06:42Z, 6.2 days): the jump rule fired 13 times on its own; 8 hedges
# executed: 7 insured positions that went on to WIN (cost $23.96), 1 caught a real loss early (+$11.47); 5 fired in the
# last 1-6 s and never filled. It missed all 3 real losses (ZEC -$56.63, XRP -$31.35, ETH -$118.91: slides, not jumps; the
# 0.40 belief line caught them). Side effect: its first false hedge (ZEC 10-24) was booked as a boosted loss and switched
# the 1.5x band boost OFF for 2.9 days (about -$24). Net: about -$2 to -$4 a day. Verdict: drop the flag.
# This script comments out ONE line in C:\kals-live-0925n\restart_bot.ps1:
#     "--hedge-jump", "6",
# keeps a backup, keeps BOM and line endings, and parse-checks the file. It does NOT restart anything. Then, while pin
# is flat (minutes 1-9 of a quarter hour), run:  powershell -ExecutionPolicy Bypass -File C:\kals-live-0925n\restart_bot.ps1 -Check
# (prints the new argument list and exits) and then the same without -Check (it waits for flat, stops pin, starts it).
$f = 'C:\kals-live-0925n\restart_bot.ps1'
$old = '    "--hedge-jump", "6",'
$new = '    # "--hedge-jump", "6",   # 2026-10-30 REMOVED (hedgejump6 read: 7 of 8 hedges insured winners, 0 of 3 real losses caught, boost switched off 2.9 days)'
$t = [IO.File]::ReadAllText($f)
$n = ([regex]::Matches($t, [regex]::Escape($old))).Count
if ($n -ne 1) { Write-Output ("NOT CHANGED: expected the old line once, found {0}" -f $n); exit 1 }
$bytes = [IO.File]::ReadAllBytes($f)
$bom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
Copy-Item $f ($f + ".before-nohedgejump-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
$enc = New-Object System.Text.UTF8Encoding($bom)
[IO.File]::WriteAllText($f, $t.Replace($old, $new), $enc)
Write-Output "CHANGED restart_bot.ps1: --hedge-jump 6 commented out"
powershell -NoProfile -Command "[void][System.Management.Automation.Language.Parser]::ParseFile('$f', [ref]`$null, [ref]`$e); if (`$e.Count) { 'PARSE ERRORS: ' + `$e.Count; exit 1 } else { 'restart_bot.ps1 parses OK' }"
Write-Output "Next, while pin is flat: powershell -ExecutionPolicy Bypass -File $f -Check   then the same without -Check"
