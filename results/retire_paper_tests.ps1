param([string]$Target = "C:\kals-repo\boot_all.ps1", [switch]$NoStop)
# Retires the PAPER tests boot_all keeps alive whose questions are answered (2026-10-26, operator: "check if anything
# isn't needed anymore, or if you're collecting or doing something with the same data multiple times"). Audit basis:
# READS_DUE.json, HANDOFF.md, IDEA_LEDGER.md and a grep of the repo for each log's name.
#   - the three forecaster-variant side-by-side runs (fc_variants_paper.py: main, quiet, crash-guard): every read
#     closed by 10-06 (fcvar-paper, quiet2x-paper = FAIL, fcvar-crash-paper = validated, live since 09-30); none of
#     them runs the live variant (race1_98_r28_oneside), and the live forecaster's own in-process paper
#     (results\forecaster-live.jsonl, 'fill' rows with feat_*) logs the same per-fill features for the live rule.
#     Nothing but fc_compare.py (no open read) reads fcvar-paper*.jsonl.
#   - bettor_paper.py (clean-room forecaster/bettor/contrarian paper): read 10-05, all three tiny or negative; nothing
#     reads results\cleanroom-bettor.jsonl (190 MB and growing).
#   - the coin-race paper arms 3 and 4 (pinracearm.py without --live): not running now (their 3-day timer ended
#     10-25), but boot_all restarts both whenever the LIVE coin race is down at a tick; no read since September.
#   - cdc_record.py (Crypto.com recorder): idea D21 dead, nothing reads C:\kals\cdc_data (HANDOFF: "his folder, his
#     call"), and it has watched 0 contracts since 10-25.
# KEPT: the live bots, run_all (Kalshi + exchange recorders), the phone link, the ledger refresher, the ladder paper
# (ladder_shadow.py reads it; operator 10-22), rain paper (READS_DUE rain-paper 11-02).
# What this does:
#   1. boot_all.ps1 (backup first; parse-checked; the file's own line ending and BOM kept; every anchor must match
#      exactly once or NOTHING changes):
#      - the four $cleanroom entries get a stop file (`stop = ""` -> `stop = "$res\<name>.stop"`, dated comment), the
#        off switch boot_all and the phone's /features already understand, and this script writes those files;
#      - the race-arm launch and the cdc_record launch become `$false -and ...` (dated comment).
#   2. stops ONLY those python processes: Name python.exe, the script name AND a distinguishing argument in the
#      command line, never a command line with --live. Nothing else is touched.
# To bring one back: delete its results\<name>.stop, or remove the `$false -and`, or restore the backup.
# Needs administrator rights (boot_all started them elevated). retire_paper_tests.cmd asks for them.
$ErrorActionPreference = "Stop"
$freeBefore = [int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1KB)
$t = [IO.File]::ReadAllText($Target)
$sfx = ' -- results\retire_paper_tests.ps1'
$edits = @(
    @{ n = "forecaster variants paper (main)"; stopfile = "fcvar-paper.stop"
       old = '@{ n = "forecaster variants paper"; like = "*fc_variants_paper.py*"; unlike = @("*fcvar-paper-quiet*", "*fcvar-paper-crash*"); stop = "";'
       new = '@{ n = "forecaster variants paper"; like = "*fc_variants_paper.py*"; unlike = @("*fcvar-paper-quiet*", "*fcvar-paper-crash*"); stop = "$res\fcvar-paper.stop";   # 2026-10-26 RETIRED: read 10-06, no open read, no live variant in it' + $sfx },
    @{ n = "forecaster variants paper (quiet run)"; stopfile = "fcvar-paper-quiet.stop"
       old = '@{ n = "forecaster variants paper (quiet run)"; like = "*fc_variants_paper.py*fcvar-paper-quiet*"; unlike = ""; stop = "";'
       new = '@{ n = "forecaster variants paper (quiet run)"; like = "*fc_variants_paper.py*fcvar-paper-quiet*"; unlike = ""; stop = "$res\fcvar-paper-quiet.stop";   # 2026-10-26 RETIRED: quiet2x FAILED its 10-02 read' + $sfx },
    @{ n = "forecaster variants paper (crash-guard run)"; stopfile = "fcvar-paper-crash.stop"
       old = '@{ n = "forecaster variants paper (crash-guard run)"; like = "*fc_variants_paper.py*fcvar-paper-crash*"; unlike = ""; stop = "";'
       new = '@{ n = "forecaster variants paper (crash-guard run)"; like = "*fc_variants_paper.py*fcvar-paper-crash*"; unlike = ""; stop = "$res\fcvar-paper-crash.stop";   # 2026-10-26 RETIRED: validated 10-06, the guard is live' + $sfx },
    @{ n = "bettor_paper (paper)"; stopfile = "cleanroom-bettor.stop"
       old = '@{ n = "bettor_paper (paper)"; like = "*cleanroom*bettor_paper.py*"; unlike = ""; stop = "";'
       new = '@{ n = "bettor_paper (paper)"; like = "*cleanroom*bettor_paper.py*"; unlike = ""; stop = "$res\cleanroom-bettor.stop";   # 2026-10-26 RETIRED: read 10-05, nothing reads its log' + $sfx },
    @{ n = "coin-race paper arms 3 and 4"; stopfile = $null
       old = 'if ($race.Count -eq 0) {'
       new = 'if ($false -and $race.Count -eq 0) {   # 2026-10-26 RETIRED: coin-race paper arms 3/4 (no read since September; they came back whenever the live race was down)' + $sfx },
    @{ n = "Crypto.com recorder (cdc_record.py)"; stopfile = $null
       old = '} elseif (Test-Path "$kals\cdc_record.py") {'
       new = '} elseif ($false -and (Test-Path "$kals\cdc_record.py")) {   # 2026-10-26 RETIRED: Crypto.com recorder (idea D21 dead; nothing reads cdc_data)' + $sfx }
)
$new = $t
$todo = 0
foreach ($e in $edits) {
    if ($new.Contains($e.new)) { Write-Output "boot_all: $($e.n) -- already retired"; continue }
    $hits = [regex]::Matches($new, [regex]::Escape($e.old)).Count
    if ($hits -ne 1) { Write-Output "REFUSED: the line for '$($e.n)' was found $hits times (want 1); nothing changed"; exit 1 }
    $new = $new.Replace($e.old, $e.new)
    $todo++
}
if ($todo -eq 0) {
    Write-Output "boot_all: already retired -- not edited"
} else {
    $errs = $null
    [void][System.Management.Automation.Language.Parser]::ParseInput($new, [ref]$null, [ref]$errs)
    if ($errs.Count) { Write-Output "REFUSED: the edited file would not parse ($($errs[0].Message)); nothing changed"; exit 1 }
    $bak = if ($Target -eq "C:\kals-repo\boot_all.ps1") { "C:\kals-repo\results\boot_all.before-retire-tests.ps1" } else { "$Target.before-retire-tests" }
    Copy-Item $Target $bak -Force
    $bom = [IO.File]::ReadAllBytes($Target)
    $hasBom = $bom.Length -ge 3 -and $bom[0] -eq 0xEF -and $bom[1] -eq 0xBB -and $bom[2] -eq 0xBF
    [IO.File]::WriteAllText($Target, $new, (New-Object Text.UTF8Encoding $hasBom))
    Write-Output ("boot_all: {0} launch(es) retired ({1} -> {2} chars; backup {3})" -f $todo, $t.Length, $new.Length, $bak)
}
# the stop files the four $cleanroom entries now point at (next to the copy when testing on one)
$stopDir = if ($Target -eq "C:\kals-repo\boot_all.ps1") { "C:\kals-repo\results" } else { Split-Path -Parent $Target }
foreach ($e in $edits) {
    if (-not $e.stopfile) { continue }
    $sf = Join-Path $stopDir $e.stopfile
    if (Test-Path $sf) { Write-Output "  stop file exists: $sf"; continue }
    [IO.File]::WriteAllText($sf, "2026-10-26 RETIRED by results\retire_paper_tests.ps1: $($e.n). Delete this file to let boot_all start it again.`n", (New-Object Text.UTF8Encoding $false))
    Write-Output "  wrote stop file: $sf"
}
if ($NoStop) { Write-Output "-NoStop: no process stopped"; exit 0 }
# every rule: python.exe, ALL of `all` in the command line, NONE of `none`; --live is refused for every rule
$rules = @(
    @{ n = "forecaster variants paper (main)";            all = @('*fc_variants_paper.py*');                      none = @('*--log*') },
    @{ n = "forecaster variants paper (quiet run)";       all = @('*fc_variants_paper.py*', '*fcvar-paper-quiet.jsonl*'); none = @() },
    @{ n = "forecaster variants paper (crash-guard run)"; all = @('*fc_variants_paper.py*', '*fcvar-paper-crash.jsonl*'); none = @() },
    @{ n = "bettor_paper (paper)";                         all = @('*cleanroom*bettor_paper.py*', '*--minutes*');  none = @() },
    @{ n = "coin-race paper arm 3";                        all = @('*pinracearm.py*', '*--one-per-race-band*');    none = @() },
    @{ n = "coin-race paper arm 4";                        all = @('*pinracearm.py*', '*--model fair*', '*--min-edge 0.02*'); none = @() },
    @{ n = "Crypto.com recorder";                          all = @('*cdc_record.py*', '*--hot*');                  none = @() }
)
$procs = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'")
$blind = @($procs | Where-Object { -not $_.CommandLine }).Count
if ($blind) { Write-Output "WARNING: $blind python process(es) hide their command line (not elevated?) -- they cannot be matched and are left alone" }
$live = @($procs | Where-Object { $_.CommandLine -like '*--live*' }).Count
Write-Output "live processes (--live): $live, never touched"
$n = 0
foreach ($r in $rules) {
    $hits = @($procs | Where-Object { $cl = $_.CommandLine; $cl -and $cl -notlike '*--live*' -and
              -not @($r.all | Where-Object { $cl -notlike $_ }).Count -and -not @($r.none | Where-Object { $cl -like $_ }).Count })
    if (-not $hits.Count) { Write-Output "  $($r.n): not running"; continue }
    foreach ($p in $hits) {
        $mb = try { [int]((Get-Process -Id $p.ProcessId).PrivateMemorySize64 / 1MB) } catch { 0 }
        try { Stop-Process -Id $p.ProcessId -Force; $n++; Write-Output "  stopped $($r.n) (pid $($p.ProcessId), $mb MB private)" } catch { Write-Output "  could not stop $($r.n) (pid $($p.ProcessId)): $($_.Exception.Message)" }
    }
}
Start-Sleep -Seconds 3
$freeAfter = [int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1KB)
Write-Output ("stopped {0} process(es); free memory: {1} MB before, {2} MB after" -f $n, $freeBefore, $freeAfter)
