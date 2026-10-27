param([string]$TestDir = "")
# The operator's three after-work jobs in one (2026-10-26, operator: "Make the changes you made earlier for me to do
# after work into one command"). Runs, in this order, each in its own try so one failing never blocks the others:
#   1. restart_ntopng.ps1            -- frees the ~3 GB of kernel memory the ntopng service leaks (bots keep running)
#   2. retire_paper_tests.ps1        -- retires 5 answered paper tests in boot_all and stops only those processes
#   3. add_fx_recorder_keepalive.ps1 -- adds the FX / commodity recorder to boot_all's keep-alive list (must be done
#                                       before ~2026-10-30 08:49Z, when the running recorder stops itself)
# Steps 2 and 3 were checked on a copy of today's boot_all in both orders: same result, and a second run changes nothing.
# Everything it prints is also saved to results\do_after_work.log. Needs administrator rights: do_after_work.cmd asks.
# -TestDir <folder with a copy of boot_all.ps1>: a dry run -- skips ntopng and stopping processes, edits only the copy.
$res = "C:\kals-repo\results"
$test = [bool]$TestDir
$log = if ($test) { Join-Path $TestDir "do_after_work.log" } else { "$res\do_after_work.log" }
try { Start-Transcript -Path $log -Append | Out-Null } catch { }
Write-Output ("=== do_after_work {0}{1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $(if ($test) { " (TEST on $TestDir)" } else { "" }))
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin -and -not $test) {
    Write-Output "NOT RUN: this window has no administrator rights. Double-click results\do_after_work.cmd and say Yes."
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}
$target = if ($test) { Join-Path $TestDir "boot_all.ps1" } else { "C:\kals-repo\boot_all.ps1" }
$steps = @(
    @{ n = "1. free the memory ntopng leaked"; skip = $test
       run = { & "$res\restart_ntopng.ps1" } },
    @{ n = "2. retire the finished paper tests"; skip = $false
       run = { if ($test) { & "$res\retire_paper_tests.ps1" -Target $target -NoStop } else { & "$res\retire_paper_tests.ps1" } } },
    @{ n = "3. keep the FX recorder running"; skip = $false
       run = { & "$res\add_fx_recorder_keepalive.ps1" -Target $target } }
)
$done = @()
foreach ($s in $steps) {
    Write-Output ""
    Write-Output "--- $($s.n)"
    if ($s.skip) { Write-Output "skipped (test run)"; $done += "$($s.n): skipped (test)"; continue }
    $global:LASTEXITCODE = 0
    try {
        & $s.run
        if ($LASTEXITCODE -ne 0) { $done += "$($s.n): REFUSED (see above), nothing changed by this step" }
        else { $done += "$($s.n): OK" }
    } catch {
        Write-Output "FAILED: $($_.Exception.Message)"
        $done += "$($s.n): FAILED ($($_.Exception.Message))"
    }
}
Write-Output ""
Write-Output "=== summary"
$done | ForEach-Object { Write-Output "  $_" }
Write-Output "Saved to $log. You can close this window."
try { Stop-Transcript | Out-Null } catch { }
