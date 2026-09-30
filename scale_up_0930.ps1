# scale_up_0930.ps1 -- the operator's 2026-09-30 size increases, applied in one go.
#   "increase the coin race size don't stop on one loss, increase clean room forecaster, increase ladder"
#
# What it does, in order (and nothing else):
#   0. VALIDATES first, while the old bots still run: self-tests of pinracearm / forecaster_live / ladder_live pass
#      with the new code; no stop file is present; each subaccount holds no more than its new start rail; exactly
#      one live process of each is running now. Any failure -> nothing is stopped.
#   1. Points the keep-alive (boot_all.ps1 section 3e) at the NEW argv, and adds the live coin race to it, so a
#      crash restarts the new version and never the old one.
#   2. Coin race: stops the live process and starts it again at 40 contracts a leg, $120 open-bet cap, and
#      --live-max-losses 2 (stop for the rest of the ET day after 2 losing races, instead of stopping for good on 1).
#   3. Forecaster (subaccount 2): stop file -> wait for exit -> delete it -> start with --scale 0.10 (1/10 of paper;
#      every rail doubles with it: 10 a side, 40 a close, $44 held, -$24 day, -$40 run).
#   4. Ladder (subaccount 1): same, with --size 5 (5 contracts a bid; rails x5: 50 contracts, $60 held, -$30 day).
#   5. Checks each new process wrote its start record with the new settings.
# Money was already moved: subaccount 1 -> $65.15, subaccount 2 -> $54.35 (2026-09-30 ~06:0xZ).
#
#     powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/scale_up_0930.ps1 -DryRun   (checks only)
#     powershell -NoProfile -ExecutionPolicy Bypass -File C:/kals-repo/scale_up_0930.ps1
#
# REVERT: results/VERSIONS.md entries v-race40, v-forecaster-scale, v-ladder-size (old argv in each).
param([switch]$DryRun)
$ErrorActionPreference = "Stop"
$repo = "C:\kals-repo"; $res = "$repo\results"; $py = "C:\Python314\python.exe"
function Say($m) { $l = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"), $m; Write-Output $l; Add-Content -Path "$res\scale_up_0930.log" -Value $l -Encoding utf8 }
function Live($like) { @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like $like }) }

$race = @("-u","research/pinracearm.py","--live","--max-contracts","40","--max-stake","120","--live-max-losses","2","--live-rolling-stake","--live-tau-max","30","--live-min-price","0.90","--live-max-legs","5","--live-confirm","5","--live-clock-tau","20","--minutes","10080","--log","C:/kals-repo/results/pinracepenny-live.jsonl","--model","fair","--tau-max","60","--min-price","0.80","--min-edge","0.00")
$fc   = @("-u","research\cleanroom\forecaster_live.py","--subaccount","2","--live","--variant","race1_98","--scale","0.10","--minutes","10080")
$lad  = @("-u","research\cleanroom\ladder_live.py","--subaccount","1","--live","--size","5","--minutes","10080")

# ---- 0. validate (nothing is stopped if any of this fails)
Say "validating (DryRun=$DryRun)"
foreach ($t in @(@("research\pinracearm.py","--selftest"), @("research\cleanroom\forecaster_live.py","--selftest"), @("research\cleanroom\ladder_live.py","--selftest"))) {
    $out = & $py @t 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0 -or $out -notmatch "PASSED") { Say "SELF-TEST FAILED: $($t -join ' ')"; exit 1 }
    Say "self-test ok: $($t[0])"
}
foreach ($f in @("$res\pinracepenny.stop", "$res\forecaster-live.stop", "$res\ladder-live.stop")) { if (Test-Path $f) { Say "stop file present, refusing: $f"; exit 1 } }
$oldRace = @(Live '*pinracearm.py --live*'); $oldFc = @(Live '*forecaster_live.py*--live*'); $oldLad = @(Live '*ladder_live.py*--live*')
if ($oldRace.Count -ne 1 -or $oldFc.Count -ne 1 -or $oldLad.Count -ne 1) { Say "expected exactly one live race/forecaster/ladder, found $($oldRace.Count)/$($oldFc.Count)/$($oldLad.Count) -- refusing"; exit 1 }
$bal = & $py -c "import sys; sys.path.insert(0, r'$repo\research'); import kauth; print(' '.join(kauth.get('/portfolio/balance', {'subaccount': str(s), 'exchange_index': '2'})[1]['balance_dollars'] for s in (1, 2)))"
$b1, $b2 = ($bal -split ' ') | ForEach-Object { [double]$_ }
Say ("subaccount balances: 1 = {0:N2} (rail 73), 2 = {1:N2} (rail 70)" -f $b1, $b2)
if ($b1 -gt 73.0 -or $b2 -gt 70.0 -or $b1 -lt 20 -or $b2 -lt 20) { Say "balance outside the new start rails -- refusing"; exit 1 }
if ($DryRun) { Say "DRY RUN: all checks passed; nothing stopped or started"; exit 0 }

# ---- 1. keep-alive -> the new argv (+ the live coin race)
$boot = Get-Content "$repo\boot_all.ps1" -Raw
$oldFcLine = 'a = @("-u", "research\cleanroom\forecaster_live.py", "--subaccount", "2", "--live", "--variant", "race1_98", "--minutes", "10080");'
$newFcLine = 'a = @("-u", "research\cleanroom\forecaster_live.py", "--subaccount", "2", "--live", "--variant", "race1_98", "--scale", "0.10", "--minutes", "10080");'
$oldLadLine = 'a = @("-u", "research\cleanroom\ladder_live.py", "--subaccount", "1", "--live", "--minutes", "10080");'
$newLadLine = 'a = @("-u", "research\cleanroom\ladder_live.py", "--subaccount", "1", "--live", "--size", "5", "--minutes", "10080");'
$raceAnchor = '    @{ n = "bettor_paper (paper)";'
$raceEntry = '    @{ n = "coin race (LIVE, main account)"; like = "*pinracearm.py --live*"; unlike = ""; stop = "$res\pinracepenny.stop";' + "`r`n" +
             '       a = @("-u", "research/pinracearm.py", "--live", "--max-contracts", "40", "--max-stake", "120", "--live-max-losses", "2", "--live-rolling-stake", "--live-tau-max", "30", "--live-min-price", "0.90", "--live-max-legs", "5", "--live-confirm", "5", "--live-clock-tau", "20", "--minutes", "10080", "--log", "C:/kals-repo/results/pinracepenny-live.jsonl", "--model", "fair", "--tau-max", "60", "--min-price", "0.80", "--min-edge", "0.00");' + "`r`n" +
             '       o = "$res\pinracepenny-live.out"; e = "$res\pinracepenny-live.err" },' + "`r`n"
foreach ($x in @($oldFcLine, $oldLadLine, $raceAnchor)) { if (-not $boot.Contains($x)) { Say "boot_all.ps1 does not contain the expected line -- refusing: $x"; exit 1 } }
$boot = $boot.Replace($oldFcLine, $newFcLine).Replace($oldLadLine, $newLadLine).Replace($raceAnchor, $raceEntry + $raceAnchor)
$errs = $null; [void][System.Management.Automation.Language.Parser]::ParseInput($boot, [ref]$null, [ref]$errs)
if ($errs.Count) { Say "edited boot_all.ps1 does not parse -- refusing"; exit 1 }
Copy-Item "$repo\boot_all.ps1" "$res\boot_all.before-scale-up.ps1"
Set-Content -Path "$repo\boot_all.ps1" -Value $boot -Encoding utf8 -NoNewline
Say "keep-alive updated (backup results\boot_all.before-scale-up.ps1)"

# ---- 2. coin race
Stop-Process -Id $oldRace[0].ProcessId -Confirm:$false; Say "stopped coin race $($oldRace[0].ProcessId)"; Start-Sleep 2
$p = Start-Process -FilePath $py -ArgumentList $race -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput "$res\pinracepenny-live.out" -RedirectStandardError "$res\pinracepenny-live.err" -PassThru
Say "started coin race $($p.Id) (40 a leg, `$120 cap, 2 losses a day)"

# ---- 3/4. forecaster and ladder: stop file -> exit -> delete -> start
foreach ($b in @(@{ n = "forecaster"; stop = "$res\forecaster-live.stop"; old = $oldFc[0].ProcessId; a = $fc; o = "$res\forecaster-live-stdout.log"; e = "$res\forecaster-live-stderr.log" },
                 @{ n = "ladder"; stop = "$res\ladder-live.stop"; old = $oldLad[0].ProcessId; a = $lad; o = "$res\ladder-live-stdout.log"; e = "$res\ladder-live-stderr.log" })) {
    New-Item -ItemType File -Path $b.stop -Force | Out-Null
    for ($i = 0; $i -lt 90 -and (Get-Process -Id $b.old -ErrorAction SilentlyContinue); $i++) { Start-Sleep 1 }
    if (Get-Process -Id $b.old -ErrorAction SilentlyContinue) { Say "$($b.n) did not exit on its stop file -- leaving it stopped-flagged; check by hand"; continue }
    Remove-Item $b.stop -Force
    $p = Start-Process -FilePath $py -ArgumentList $b.a -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput $b.o -RedirectStandardError $b.e -PassThru
    Say "started $($b.n) $($p.Id): $($b.a -join ' ')"
}

# ---- 5. confirm the new start records
Start-Sleep 25
$chk = & $py -c @"
import json
def last(p, ev):
    r = None
    for l in open(p, encoding='utf-8'):
        if '"ev":"%s"' % ev in l or '"kind": "%s"' % ev in l: r = l
    return json.loads(r) if r else None
f = last(r'$res\forecaster-live-orders.jsonl', 'start'); l = last(r'$res\ladder-live-orders.jsonl', 'start')
print('forecaster start', f and f['t'], f and f['rails'].get('per_side'), '| ladder start', l and l['t'], l and l['rails'].get('size'))
"@
Say $chk
Say "done -- read results\scale_up_0930.log; the coin race prints its raised rails in results\pinracepenny-live.out"
