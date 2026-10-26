param([string]$Target = "C:\kals-repo\boot_all.ps1")
# Adds the FX taker (fxtake_live.py, subaccounts 5 + 4) to boot_all's keep-alive list, right after the ladder.
# boot_all then restarts it after a reboot or crash unless results\fxtake-live.stop exists. Backup first; refuses
# if the ladder line is not found exactly once or the FX entry is already there; checks the result still parses.
$ErrorActionPreference = "Stop"
$t = [IO.File]::ReadAllText($Target)
if ($t.Contains("fxtake_live.py")) { Write-Output "already there: nothing changed"; exit 0 }
$k = '       o = "$res\ladder-live-stdout.log"; e = "$res\ladder-live-stderr.log" },'
$hits = [regex]::Matches($t, [regex]::Escape($k)).Count
if ($hits -ne 1) { Write-Output "REFUSED: the ladder line was found $hits times (want 1); nothing changed"; exit 1 }
$nl = if ($t.Contains("`r`n")) { "`r`n" } else { "`n" }      # the file's own line ending
$add = $nl +
  '    @{ n = "fxtake_live (LIVE, subaccounts 5 + 4)"; like = "*fxtake_live.py*--live*"; unlike = ""; stop = "$res\fxtake-live.stop";' + $nl +
  '       a = @("-u", "research\cleanroom\fxtake_live.py", "--subaccount", "5", "--fx-subaccount", "4", "--live", "--minutes", "10080");' + $nl +
  '       o = "$res\fxtake-live-stdout.log"; e = "$res\fxtake-live-stderr.log" },'
$new = $t.Replace($k, $k + $add)
$errs = $null
[void][System.Management.Automation.Language.Parser]::ParseInput($new, [ref]$null, [ref]$errs)
if ($errs.Count) { Write-Output "REFUSED: the edited file would not parse ($($errs[0].Message)); nothing changed"; exit 1 }
$bak = Join-Path (Split-Path $Target) "results\boot_all.before-fx.ps1"
if ($Target -ne "C:\kals-repo\boot_all.ps1") { $bak = "$Target.before-fx" }
Copy-Item $Target $bak -Force
[IO.File]::WriteAllText($Target, $new, (New-Object Text.UTF8Encoding $true))
Write-Output ("DONE: FX taker added to the keep-alive list (file {0} -> {1} bytes; backup {2})" -f $t.Length, $new.Length, $bak)
