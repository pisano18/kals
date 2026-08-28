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

Say "=== run_when_away $stamp ==="

# ---- 1. take Claude's latest fixes -------------------------------------
# --rebase so a local results commit never turns into a merge bubble.
Say "git pull"
git pull --rebase origin $Branch 2>&1 | Tee-Object -Append -FilePath $log
$head = (git rev-parse --short HEAD)
Say "now at $head"

# ---- 2. run the stages -------------------------------------------------
# `book` is deliberately absent: preflight measures it at ~30 GB of RAM and
# this machine has ~16 GB, so it swaps the box to death rather than failing
# cleanly. Everything here reads the ticker/trade channels, which are small.
$stages = @("maker", "calib", "voltiming", "chain", "leadlag", "cross",
            "openwindow", "implied", "feeds", "pathstats", "proxy")

foreach ($s in $stages) {
    Say "--- $s ---"
    $rep = "$Repo\results\RESULTS_$s.md"
    $t0 = Get-Date
    & python research\go.py --only $s --data $Data --out $Out --feeds $Feeds `
        --report $rep 2>&1 | Tee-Object -Append -FilePath $log | Out-Null
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
git add results 2>&1 | Out-Null
$dirty = git status --porcelain results
if (-not $dirty) {
    Say "nothing changed; not committing."
    exit 0
}
git -c user.name="kals-runner" -c user.email="runner@localhost" `
    commit -q -m "results: automated run $stamp at $head" 2>&1 |
    Tee-Object -Append -FilePath $log

# Claude may have pushed while this ran. Rebase onto whatever is there and
# retry rather than failing and leaving the results stranded on this machine.
for ($i = 1; $i -le 4; $i++) {
    git pull --rebase origin $Branch 2>&1 | Out-Null
    git push origin "HEAD:$Branch" 2>&1 | Tee-Object -Append -FilePath $log
    if ($LASTEXITCODE -eq 0) { Say "pushed on attempt $i"; break }
    $wait = [math]::Pow(2, $i)
    Say "push failed; retrying in ${wait}s"
    Start-Sleep -Seconds $wait
}

Say "=== done ==="
