<#
  run_when_away.ps1 -- run the analysis and PUBLISH the results to GitHub.

  Why: Claude runs in a sandbox in Anthropic's cloud and cannot reach this PC.
  It CAN read this repository on GitHub. So this script does the two things
  that close the loop: it runs the stages, and it commits the results where
  Claude can read them. You can then be at work, or asleep, and the work
  continues.

      powershell -ExecutionPolicy Bypass -File C:\kals-repo\run_when_away.ps1

  Safe to run while the recorder is going. It never writes to kalshi_data or
  feed_data, never places an order, and skips the one stage that needs 30 GB
  of RAM on a 16 GB machine.
#>
param(
    [string]$Repo  = "C:\kals-repo",
    [string]$Data  = "C:\kals\kalshi_data",
    [string]$Feeds = "C:\kals\feed_data",
    [string]$Out   = "C:\kals\fulltape",
    [string]$Branch = "claude/file-uploads-70rtjl",
    [switch]$NoPush
)

$ErrorActionPreference = "Continue"
Set-Location $Repo
$stamp = Get-Date -Format "yyyyMMdd-HHmm"
$log   = "$Repo\results\run-$stamp.log"
New-Item -ItemType Directory -Force -Path "$Repo\results" | Out-Null

# -Encoding utf8 EVERYWHERE, including on the stage output below.
# Say used Add-Content (ASCII by default in Windows PowerShell 5.1) while the
# stage output used Tee-Object (UTF-16LE, and 5.1's Tee has no -Encoding), so
# the published log was a byte-level splice of the two. `file` called it
# "data", grep refused it as binary, and the script's own instruction --
# "Send the lines above back" -- pointed at an artifact that cannot be read
# as text. results/run-20260828-1948.log is exactly that on disk.
function Say($m) {
    $line = "$(Get-Date -f 'HH:mm:ss')  $m"
    Write-Host $line
    Add-Content -Path $log -Value $line -Encoding utf8
}

# Tee-Object in Windows PowerShell 5.1 has no -Encoding, so this replaces it.
function LogLines($lines) {
    $lines | ForEach-Object {
        Write-Host "    | $_"
        Add-Content -Path $log -Value "$_" -Encoding utf8
    }
}

# PowerShell turns anything a native program writes to stderr into a red
# ErrorRecord, even when the program succeeded. git writes ordinary progress
# there ("From https://github.com/..."), so a clean pull printed a wall of
# red and a NativeCommandError. Stringify each line before it reaches the
# pipeline and it is just text again.
function Git-Quiet {
    $out = & git @args 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE
    if ($out) { Add-Content -Path $log -Value $out }
    # On failure the reason belongs on screen. It used to go only to the log,
    # so "git pull FAILED" was all anyone ever saw of it.
    if ($code -ne 0 -and $out) {
        $out | ForEach-Object { Write-Host "    | $_" }
    }
    return $code
}

Say "=== run_when_away $stamp ==="

# ---- 1. take Claude's latest fixes -------------------------------------
# --rebase so a local results commit never turns into a merge bubble.
# --autostash because the previous run leaves results/*.md modified, and a
# rebase refuses to start on a dirty tree. That is the likeliest reason a pull
# has ever failed here.
Say "git pull"
$rc = Git-Quiet pull --rebase --autostash origin $Branch
if ($rc -ne 0) {
    Say "  rebase pull failed; aborting any partial rebase and retrying as a merge"
    Git-Quiet rebase --abort | Out-Null
    $rc = Git-Quiet pull --no-rebase --autostash origin $Branch
}
$head   = (git rev-parse --short HEAD 2>$null)
$remote = (git rev-parse --short "origin/$Branch" 2>$null)
Say "now at $head (origin/$Branch is $remote)"

# A run on code that is not what Claude pushed produces results nobody can
# attribute, and the 19:48 run was exactly that: the pull failed, the script
# said so in one line, and then ran sixteen stages on whatever was on disk.
# Silence about provenance is how an evening gets spent twice.
# -not $head -or -not $remote FIRST. If git itself is broken -- absent from
# PATH under a service account, or "dubious ownership" when the scheduled task
# runs as a different user than the repo owner -- BOTH rev-parses exit 128 with
# empty stdout, both variables bind to $null, and $null -ne $null is $false. The
# guard would fall through in exactly the case where provenance is unknowable,
# which is the case it exists for. Found by audit, not by running it.
if ((-not $head) -or (-not $remote) -or ($head -ne $remote)) {
    if ((-not $head) -or (-not $remote)) {
        Say "*** git could not report HEAD or origin/$Branch at all."
        Say "*** (git missing from PATH, or dubious-ownership under a"
        Say "***  different account than the one that owns C:\kals-repo)"
    }
    Say "*** This checkout does NOT match origin/$Branch."
    Say "*** Refusing to run: results from unknown code are worse than none."
    Say "*** Fix with:   git stash -u ; git pull --rebase origin $Branch"
    exit 1
}

# ---- 1b. preflight, ONCE ------------------------------------------------
# go.py runs this too, per stage. Doing it here as well is not redundancy for
# its own sake: without it a preflight failure prints sixteen identical walls
# of text, one per stage, and the run still takes long enough to look real.
Say "preflight: stdlib shadowing"
$pre = & python research\shadow.py . 2>&1 | ForEach-Object { "$_" }
$preRc = $LASTEXITCODE
LogLines $pre
if ($preRc -ne 0) {
    Say "*** PREFLIGHT FAILED. Nothing was run. Send the lines above back."
    exit 1
}

# ---- 1c. REFRESH THE OUTCOMES ------------------------------------------
# run_all.ps1 records quotes and index continuously, but the SETTLEMENTS come
# from kalshi_fulltape.py, which was a manual step nobody re-ran. Three
# consecutive analysis runs therefore read the same 3,600 settled markets
# while the quoted-market count grew 3,638 -> 4,797 -> 6,127. Every
# settlement-dependent stage -- calib, endgame, patterntrade, cross,
# openwindow -- was frozen on a fixed sample, and the project's own standard
# ("confirm it on data the finding has never seen") was impossible to meet.
#
# --markets-only skips the per-market trade tapes, which are the 10-15 minutes
# and which only placebo and pathstats read. This is a couple of minutes.
Say "refreshing settled outcomes (markets.json)"
# --markets 1200 per series, not 4000. The recording spans ~164 hours and a
# 15-minute series settles 4 markets an hour, so ~660 per series covers every
# market we have quotes for; 1200 is generous. 4000 meant 22 pages per series
# across twelve series, and that request rate is what triggered the rate
# limiting that returned zero markets for five of them.
$ft = & python kalshi_fulltape.py --data $Data --out $Out --markets 1200 `
        --markets-only 2>&1 | ForEach-Object { "$_" }
$ftRc = $LASTEXITCODE
LogLines $ft
if ($ftRc -ne 0) {
    Say "*** settlement refresh FAILED (exit $ftRc). Stages will run on the"
    Say "*** outcomes already on disk, which may be stale. Say so in the"
    Say "*** report you send back."
}
# The refresh refuses to write a materially smaller file than the one already
# there, so a rate-limited fetch leaves the good outcomes in place. Surface
# that here too, because a stale-but-good file is a very different thing to
# read a report against than a fresh one.
if ($ft -match "REFUSING TO WRITE") {
    Say "*** the refresh came back short and REFUSED to overwrite. The"
    Say "*** outcomes on disk are the previous, larger set. Results below"
    Say "*** are on THAT sample, not a fresh one."
}

# ---- 2. run the stages -------------------------------------------------
# `flow` runs FIRST and it is new. It is the only stage that reads
# orderbook_delta -- 395 million messages, about twenty times the rest of the
# tape put together, and until now completely unread. It STREAMS rather than
# rebuilding, so it needs a few hundred MB rather than the ~30 GB a rebuild
# wants, and it caches one file per day: the first run is roughly an hour and
# every run after it is seconds. First in the list so that a short window
# still gets it.
#
# `book` stays last: its main path reads the small `ticker` channel, not the
# rebuild, so it is cheap -- but it is also the least interesting thing here
# now that flow reads the real book.
$stages = @("flow",
            "surface", "reconcile", "implied", "term", "endgame", "patterntrade", "calfit", "oos",
            "calib", "voltiming", "maker",
            "chain", "leadlag", "cross", "openwindow", "feeds", "pathstats",
            "proxy", "book")

Say "$($stages.Count) stages. flow reads the whole order book once -- about an hour the first time, seconds after that. oos walks the tape"
Say "forward and refits as it goes -- it may take hours on its own. maker is ~16 min; the rest are 1-3 min each."

$failed = @()
foreach ($s in $stages) {
    Say "--- $s ($([array]::IndexOf($stages,$s)+1) of $($stages.Count)) ---"
    $rep = "$Repo\results\RESULTS_$s.md"

    # DELETE THE OLD REPORT FIRST. Success used to be inferred from
    # Test-Path alone, and last night's file passes that test. On the 19:48
    # run every stage died in preflight, go.py wrote a 1.5 KB "no stage ran"
    # stub, and the loop logged sixteen success-shaped lines --
    # "surface -> 1.5 KB in 1s" -- then committed and pushed them as results.
    if (Test-Path $rep) { Remove-Item $rep -Force }

    $t0 = Get-Date
    # STREAM it. The first version collected the child's output into a
    # variable and wrote it out only when the stage finished, so the screen
    # showed "--- maker ---" and then nothing for sixteen minutes. A run you
    # cannot tell from a hang is a run you will kill. ForEach-Object streams
    # and writes one encoding; Tee-Object in 5.1 cannot be told an encoding.
    & python research\go.py --only $s --data $Data --out $Out `
        --feeds $Feeds --report $rep 2>&1 |
        ForEach-Object {
            $line = "$_"
            Write-Host "    | $line"
            Add-Content -Path $log -Value $line -Encoding utf8
        }
    $rc = $LASTEXITCODE
    $dt = [int]((Get-Date) - $t0).TotalSeconds

    if ($rc -ne 0) {
        $failed += $s
        Say "*** $s FAILED (exit $rc) in ${dt}s"
    } elseif (-not (Test-Path $rep)) {
        $failed += $s
        Say "*** $s produced NO report in ${dt}s -- see the log"
    } else {
        Say "$s -> $(([math]::Round((Get-Item $rep).Length/1KB,1))) KB in ${dt}s"
    }
}

if ($failed.Count -gt 0) {
    Say ""
    Say "*** $($failed.Count) of $($stages.Count) stages FAILED: $($failed -join ', ')"
    Say "*** Results below are partial. Do not read a missing stage as a null."
}

# ---- 3. publish --------------------------------------------------------
# A result Claude cannot read is a result that does not exist. Committing
# them is the whole point of the script.
if ($NoPush) { Say "-NoPush given; stopping before publish."; exit 0 }

Say "publishing"
Git-Quiet add results | Out-Null
$dirty = git status --porcelain results
if (-not $dirty) {
    Say "nothing changed; not committing."
    exit 0
}
Git-Quiet -c user.name="kals-runner" -c user.email="runner@localhost" `
    commit -q -m "results: automated run $stamp at $head" | Out-Null

# Claude may have pushed while this ran. Rebase onto whatever is there and
# retry rather than failing and leaving the results stranded on this machine.
for ($i = 1; $i -le 4; $i++) {
    Git-Quiet pull --rebase origin $Branch | Out-Null
    if ((Git-Quiet push origin "HEAD:$Branch") -eq 0) {
        Say "pushed on attempt $i"; break
    }
    $wait = [math]::Pow(2, $i)
    Say "push failed; retrying in ${wait}s"
    Start-Sleep -Seconds $wait
}

Say "=== done ==="
