# scale_sub_1002.ps1 -- v-sub-autosize: both side-account bots size from their OWN account, like the main bot.
#   Operator 2026-10-02: "Set no limits on the sub accounts. I don't think you understand the goal, I want each
#   account running just like the main pin. High total making 2-10% per day of its total."
#
# What it does, in order (and nothing else):
#   0. VALIDATES first, while the old bots still run: forecaster_live / ladder_live self-tests pass with the new
#      code; no stop file; exactly one live forecaster and one live ladder; the main bot (pinrun --live) and the
#      coin race (pinracearm --live) are running and are NOT touched (their pids are checked again at the end);
#      boot_all.ps1 holds the exact argv lines this script replaces; each subaccount's pot (cash + the cost of what
#      it holds, read by the bots' own reader) is >= $10 -- there is NO upper rail any more. Any failure -> nothing
#      is stopped.
#   1. Points the keep-alive (boot_all.ps1 section 3e) at the NEW argv so a crash restarts the new version and
#      never the old one (backup results\boot_all.before-autosize.ps1; the edited file must parse).
#   2. Forecaster (subaccount 2): stop file -> wait for exit (<= 90 s) -> wait while boot_all.ps1 is mid-run (its
#      stale process snapshot could start a duplicate) -> delete the stop file -> start with --auto-scale in
#      place of --scale 0.10 (--variant race1_98 --crash-gap 0.10 kept): scale = pot / 630, re-read every 60 s,
#      applied only when flat; day stop -20% / run stop -33% / 70% committed of the pot.
#   3. Ladder (subaccount 1): same, with --auto-size in place of --size 5: size = floor(pot / 14), re-read every
#      60 s, applied only when nothing is held and no bid rests; day stop -20% / 70% committed of the pot.
#   4. After 25 s, checks each NEW process wrote a live start record with its flag and the size its pot implies.
#
#     powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/scale_sub_1002.ps1 -DryRun   (checks only)
#     powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/scale_sub_1002.ps1
#
# REVERT: results/VERSIONS.md entry v-sub-autosize (the old argv lines, copy-pasteable).
param([switch]$DryRun)
$ErrorActionPreference = "Stop"
$repo = "C:\kals-repo"; $res = "$repo\results"; $py = "C:\Python314\python.exe"
function Say($m) { $l = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"), $m; Write-Output $l; Add-Content -Path "$res\scale_sub_1002.log" -Value $l -Encoding utf8 }
function Live($like) { @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like $like }) }
# the keep-alive (KalsBoot runs boot_all.ps1 every 10 min, the desktop app on open) snapshots the process list ONCE at
# its start: a run that began before our new bot exists and reaches section 3e after the stop file is gone would start
# a second copy. So never remove a stop file while boot_all.ps1 is mid-run (it takes ~1 s). Verifier 2026-10-02.
function BootAlive() { @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object { $_.CommandLine -like '*boot_all.ps1*' }).Count -gt 0 }

$fc  = @("-u","research\cleanroom\forecaster_live.py","--subaccount","2","--live","--variant","race1_98","--auto-scale","--crash-gap","0.10","--minutes","10080")
$lad = @("-u","research\cleanroom\ladder_live.py","--subaccount","1","--live","--auto-size","--minutes","10080")

# the keep-alive lines (boot_all.ps1 section 3e): the OLD argv, and the NEW one that replaces it
$oldFcLine = 'a = @("-u", "research\cleanroom\forecaster_live.py", "--subaccount", "2", "--live", "--variant", "race1_98", "--scale", "0.10", "--crash-gap", "0.10", "--minutes", "10080");'
$newFcLine = 'a = @("-u", "research\cleanroom\forecaster_live.py", "--subaccount", "2", "--live", "--variant", "race1_98", "--auto-scale", "--crash-gap", "0.10", "--minutes", "10080");'
$oldLadLine = 'a = @("-u", "research\cleanroom\ladder_live.py", "--subaccount", "1", "--live", "--size", "5", "--minutes", "10080");'
$newLadLine = 'a = @("-u", "research\cleanroom\ladder_live.py", "--subaccount", "1", "--live", "--auto-size", "--minutes", "10080");'

# ---- 0. validate (nothing is stopped if any of this fails)
Say "validating (DryRun=$DryRun)"
foreach ($t in @(@("research\cleanroom\forecaster_live.py","--selftest"), @("research\cleanroom\ladder_live.py","--selftest"))) {
    $out = & $py @t | Out-String
    if ($LASTEXITCODE -ne 0 -or $out -notmatch "PASSED") { Say "SELF-TEST FAILED: $($t -join ' ')"; exit 1 }
    Say "self-test ok: $($t[0])"
}
foreach ($f in @("$res\forecaster-live.stop", "$res\ladder-live.stop")) { if (Test-Path $f) { Say "stop file present, refusing: $f"; exit 1 } }
$oldFc = @(Live '*forecaster_live.py*--live*'); $oldLad = @(Live '*ladder_live.py*--live*')
$main = @(Live '*pinrun.py --live*'); $race = @(Live '*pinracearm.py --live*')
if ($oldFc.Count -ne 1 -or $oldLad.Count -ne 1) { Say "expected exactly one live forecaster and one live ladder, found $($oldFc.Count)/$($oldLad.Count) -- refusing"; exit 1 }
if ($main.Count -ne 1 -or $race.Count -ne 1) { Say "expected exactly one live main bot and one live coin race, found $($main.Count)/$($race.Count) -- refusing"; exit 1 }
Say "untouched: main bot pid $($main[0].ProcessId), coin race pid $($race[0].ProcessId); to replace: forecaster pid $($oldFc[0].ProcessId), ladder pid $($oldLad[0].ProcessId)"
$boot = Get-Content "$repo\boot_all.ps1" -Raw
foreach ($x in @($oldFcLine, $oldLadLine)) { if (-not $boot.Contains($x)) { Say "boot_all.ps1 does not contain the expected line -- refusing: $x"; exit 1 } }
Say "boot_all.ps1 holds both old argv lines"
# the pots, read by the bots' own reader (cash + the cost of what each holds; cents and dollars must agree)
$pots = & $py -c "import sys; sys.path.insert(0, r'$repo\research'); sys.path.insert(0, r'$repo\research\cleanroom'); import ordercli, forecaster_live as F, ladder_live as L; pk = ordercli.load_key(F.KEY_FILE); s = lambda m, p, b, q: ordercli.send(ordercli.PROD, pk, F.KEY_ID, m, p, body=b, query=q); p1 = L.read_pot(s, 1); p2 = F.read_pot(s, 2); print(p1, p2, L.size_for_pot(p1) if p1 is not None else None, F.scale_for_pot(p2) if p2 is not None else None)"
$p1, $p2, $n1, $k2 = (($pots | Out-String).Trim() -split ' ')
if ($p1 -eq 'None' -or $p2 -eq 'None') { Say "a pot is unreadable ($pots) -- refusing"; exit 1 }
if ([double]$p1 -lt 10 -or [double]$p2 -lt 10) { Say "a pot is under the `$10 floor ($pots) -- refusing"; exit 1 }
Say ("pots: subaccount 1 (ladder) = `${0:N2} -> {1} a bid; subaccount 2 (forecaster) = `${2:N2} -> scale {3}; no upper rail (the operator's order)" -f [double]$p1, $n1, [double]$p2, $k2)
if ($DryRun) { Say "DRY RUN: all checks passed; nothing stopped or started"; exit 0 }

# ---- 1. keep-alive -> the new argv
$boot = $boot.Replace($oldFcLine, $newFcLine).Replace($oldLadLine, $newLadLine)
$errs = $null; [void][System.Management.Automation.Language.Parser]::ParseInput($boot, [ref]$null, [ref]$errs)
if ($errs.Count) { Say "edited boot_all.ps1 does not parse -- refusing"; exit 1 }
Copy-Item "$repo\boot_all.ps1" "$res\boot_all.before-autosize.ps1"
Set-Content -Path "$repo\boot_all.ps1" -Value $boot -Encoding utf8 -NoNewline
Say "keep-alive updated (backup results\boot_all.before-autosize.ps1)"

# ---- 2/3. forecaster and ladder: stop file -> exit -> delete -> start
$newPid = @{}
foreach ($b in @(@{ n = "forecaster"; stop = "$res\forecaster-live.stop"; old = $oldFc[0].ProcessId; a = $fc; o = "$res\forecaster-live-stdout.log"; e = "$res\forecaster-live-stderr.log" },
                 @{ n = "ladder"; stop = "$res\ladder-live.stop"; old = $oldLad[0].ProcessId; a = $lad; o = "$res\ladder-live-stdout.log"; e = "$res\ladder-live-stderr.log" })) {
    New-Item -ItemType File -Path $b.stop -Force | Out-Null
    for ($i = 0; $i -lt 90 -and (Get-Process -Id $b.old -ErrorAction SilentlyContinue); $i++) { Start-Sleep 1 }
    if (Get-Process -Id $b.old -ErrorAction SilentlyContinue) { Say "$($b.n) did not exit on its stop file in 90 s -- leaving it stopped-flagged (stop file kept); check by hand"; continue }
    for ($i = 0; $i -lt 60 -and (BootAlive); $i++) { Start-Sleep 1 }
    if (BootAlive) { Say "boot_all.ps1 still running after 60 s -- starting $($b.n) anyway; check for a duplicate afterwards" }
    Remove-Item $b.stop -Force
    $p = Start-Process -FilePath $py -ArgumentList $b.a -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput $b.o -RedirectStandardError $b.e -PassThru
    $newPid[$b.n] = $p.Id
    Say "started $($b.n) $($p.Id): $($b.a -join ' ')"
}

# ---- 4. confirm the NEW processes' start records (flag on, size derived from the pot)
Start-Sleep 25
$fcPid = if ($newPid.ContainsKey("forecaster")) { $newPid["forecaster"] } else { -1 }
$ladPid = if ($newPid.ContainsKey("ladder")) { $newPid["ladder"] } else { -1 }
$chk = & $py -c @"
import json, math
def last(p, ev):
    r = None
    for l in open(p, encoding='utf-8'):
        if '"ev":"%s"' % ev in l: r = l
    return json.loads(r) if r else None
f = last(r'$res\forecaster-live-orders.jsonl', 'start'); l = last(r'$res\ladder-live-orders.jsonl', 'start')
ok = True
if not (f and f.get('live') and f.get('auto_scale') and f.get('pid') == $fcPid):
    ok = False; print('FORECASTER: no live --auto-scale start record from pid ${fcPid}:', f)
else:
    want = min(1.0, max(0.02, round(f['pot'] / 630.0, 4)))
    print('forecaster start', f['t'], 'pid', f['pid'], 'pot %.2f scale %s (want %s) per_side %s per_close %s commit %s day %s run %s start_cap %s' % (f['pot'], f['rails']['scale'], want, f['rails']['per_side'], f['rails']['per_close'], f['rails']['max_commit'], f['rails']['day_stop'], f['rails']['run_stop'], f['rails'].get('start_cap')))
    if abs(float(f['rails']['scale']) - want) > 1e-9: ok = False; print('FORECASTER: scale is not pot/630')
if not (l and l.get('live') and l.get('auto_size') and l.get('pid') == $ladPid):
    ok = False; print('LADDER: no live --auto-size start record from pid ${ladPid}:', l)
else:
    want = max(1, min(100, int(math.floor(l['pot'] / 14.0 + 1e-9))))
    print('ladder start', l['t'], 'pid', l['pid'], 'pot %.2f size %s (want %s) contracts %s commit %s day %s start_cap %s' % (l['pot'], l['rails']['size'], want, l['rails']['max_contracts'], l['rails']['max_commit'], l['rails']['day_stop'], l['rails'].get('start_cap')))
    if l['rails']['size'] != want: ok = False; print('LADDER: size is not floor(pot/14)')
print('CONFIRMED' if ok else 'NOT CONFIRMED -- check results/*-live-stderr.log and the order logs by hand')
"@
Say (($chk | Out-String).Trim())
$main2 = @(Live '*pinrun.py --live*'); $race2 = @(Live '*pinracearm.py --live*')
if ($main2.Count -eq 1 -and $main2[0].ProcessId -eq $main[0].ProcessId -and $race2.Count -eq 1 -and $race2[0].ProcessId -eq $race[0].ProcessId) {
    Say "main bot and coin race untouched (pids $($main[0].ProcessId), $($race[0].ProcessId))"
} else {
    Say "WARNING: the main bot / coin race pid changed during the switch (was $($main[0].ProcessId) / $($race[0].ProcessId)) -- this script did not touch them; look"
}
Say "done -- read results\scale_sub_1002.log; VERSIONS.md v-sub-autosize is now LIVE (mark it), READS_DUE sub-autosize due 2026-10-04 12:00Z"
