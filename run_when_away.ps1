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

function Say($m) {
    $line = "$(Get-Date -f 'HH:mm:ss')  $m"
    Write-Host $line
    Add-Content -Path $log -Value $line
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
& python research\shadow.py . 2>&1 |
    ForEach-Object { "$_" } |
    Tee-Object -Append -FilePath $log |
    ForEach-Object { Write-Host "    | $_" }
if ($LASTEXITCODE -ne 0) {
    Say "*** PREFLIGHT FAILED. Nothing was run. Send the lines above back."
    exit 1
}

# ---- 2. run the stages -------------------------------------------------
# `book` is deliberately absent: preflight measures it at ~30 GB of RAM and
# this machine has ~16 GB, so it swaps the box to death rather than failing
# cleanly. Everything here reads the ticker/trade channels, which are small.
$stages = @("surface", "reconcile", "implied", "term", "endgame", "calib", "voltiming", "maker",
            "chain", "leadlag", "cross", "openwindow", "feeds", "pathstats",
            "proxy", "book")

Say "$($stages.Count) stages. maker is first and takes ~16 min; the rest are"
Say "1-3 min each. Expect 30-60 min total."

foreach ($s in $stages) {
    Say "--- $s ($([array]::IndexOf($stages,$s)+1) of $($stages.Count)) ---"
    $rep = "$Repo\results\RESULTS_$s.md"
    $t0 = Get-Date
    # STREAM it. The first version collected the child's output into a
    # variable and wrote it out only when the stage finished, so the screen
    # showed "--- maker ---" and then nothing for sixteen minutes. A run you
    # cannot tell from a hang is a run you will kill.
    & python research\go.py --only $s --data $Data --out $Out `
        --feeds $Feeds --report $rep 2>&1 |
        ForEach-Object { "$_" } |
        Tee-Object -Append -FilePath $log |
        ForEach-Object { Write-Host "    | $_" }
    $dt = [int]((Get-Date) - $t0).TotalSeconds
    if (Test-Path $rep) {
        Say "$s -> $(([math]::Round((Get-Item $rep).Length/1KB,1))) KB in ${dt}s"
    } else {
        Say "$s produced NO report in ${dt}s -- see the log"
    }
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
