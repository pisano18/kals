param([string]$Target = "C:\kals-repo\boot_all.ps1", [switch]$NoStop)
# Retires the September pin-bot PAPER arms (2026-10-26, operator: "free up memory ... check if anything isn't needed
# anymore"). The 16 pinrun.py paper copies (arm-b-*, arm-pin0.97..0.99, arm-e60-*) test settings from 09-18 on the old
# baseline, nothing has read their logs since September, and together they hold ~1.6 GB of RAM, ~1.6 CPU cores and 16
# copies of the same Kalshi websocket feed. boot_all relaunches all 16 whenever none run, so this does two things:
#   1. boot_all.ps1: the paper-arm launch becomes `if ($false -and $paper.Count -eq 0)` (backup first; parse-checked;
#      the file's own line ending and BOM kept; the coin-race arms and everything else are untouched);
#   2. stops every python pinrun.py process that is NOT --live and carries --arm-name. The live pin bot (--live) is never
#      touched.
# Needs administrator rights (boot_all started the arms elevated). retire_paper_arms.cmd asks for them.
$ErrorActionPreference = "Stop"
$freeBefore = [int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1KB)
$t = [IO.File]::ReadAllText($Target)
$k = 'if ($paper.Count -eq 0) {'
if ($t.Contains('if ($false -and $paper.Count -eq 0) {')) {
    Write-Output "boot_all: already retired -- not edited"
} else {
    $hits = [regex]::Matches($t, [regex]::Escape($k)).Count
    if ($hits -ne 1) { Write-Output "REFUSED: the paper-arm line was found $hits times (want 1); nothing changed"; exit 1 }
    $new = $t.Replace($k, 'if ($false -and $paper.Count -eq 0) {   # 2026-10-26 RETIRED: the September pin paper arms (stale; ~1.6 GB, ~1.6 cores, 16 duplicate feeds) -- results\retire_paper_arms.ps1')
    $errs = $null
    [void][System.Management.Automation.Language.Parser]::ParseInput($new, [ref]$null, [ref]$errs)
    if ($errs.Count) { Write-Output "REFUSED: the edited file would not parse ($($errs[0].Message)); nothing changed"; exit 1 }
    $bak = if ($Target -eq "C:\kals-repo\boot_all.ps1") { "C:\kals-repo\results\boot_all.before-retire-arms.ps1" } else { "$Target.before-retire-arms" }
    Copy-Item $Target $bak -Force
    $bom = [IO.File]::ReadAllBytes($Target)
    $hasBom = $bom.Length -ge 3 -and $bom[0] -eq 0xEF -and $bom[1] -eq 0xBB -and $bom[2] -eq 0xBF
    [IO.File]::WriteAllText($Target, $new, (New-Object Text.UTF8Encoding $hasBom))
    Write-Output ("boot_all: paper-arm launch retired ({0} -> {1} chars; backup {2})" -f $t.Length, $new.Length, $bak)
}
if ($NoStop) { Write-Output "-NoStop: no process stopped"; exit 0 }
$arms = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
    $_.CommandLine -like '*pinrun.py*' -and $_.CommandLine -notlike '*--live*' -and $_.CommandLine -like '*--arm-name*' })
$live = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*pinrun.py*' -and $_.CommandLine -like '*--live*' })
Write-Output ("found {0} pin paper arm(s); the live pin bot: {1} process(es), left alone" -f $arms.Count, $live.Count)
foreach ($p in $arms) {
    $name = if ($p.CommandLine -match '--arm-name\s+(\S+)') { $Matches[1] } else { '?' }
    try { Stop-Process -Id $p.ProcessId -Force; Write-Output "  stopped $name (pid $($p.ProcessId))" } catch { Write-Output "  could not stop $name (pid $($p.ProcessId)): $($_.Exception.Message)" }
}
Start-Sleep -Seconds 3
$freeAfter = [int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1KB)
Write-Output ("free memory: {0} MB before, {1} MB after" -f $freeBefore, $freeAfter)
