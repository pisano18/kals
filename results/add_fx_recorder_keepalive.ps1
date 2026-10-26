param([string]$Target = "C:\kals-repo\boot_all.ps1")
# Adds the READ-ONLY 15-minute FX / commodity recorder (research\hourly_collector.py --fifteen-min, tape
# C:\kals\kalshi_data_fx) to boot_all's keep-alive list, right after the FX taker (2026-10-26). Why: the running
# recorder (pid 2455836, started 10-23 08:48:57Z by results\start_fx_collector.ps1) stops itself at --minutes 10080,
# about 2026-10-30 08:49Z, and nothing restarts it -- and its tape is what the FX taker's rules are judged on (the
# 10-26 replay fx_replay5.py; fx-taker-read 10-28). The new entry runs it with --minutes 0 (until stopped) and
# matches only a process with BOTH hourly_collector.py and --fifteen-min in its command line, so the running copy is
# seen and never doubled. results\fx-collector.stop stands it down. Backup first; refuses if the FX taker's line is
# not found exactly once or the entry is already there; checks the result still parses; keeps the BOM and endings.
$ErrorActionPreference = "Stop"
$t = [IO.File]::ReadAllText($Target)
if ($t.Contains("hourly_collector.py*--fifteen-min")) { Write-Output "already there: nothing changed"; exit 0 }
$k = '       o = "$res\fxtake-live-stdout.log"; e = "$res\fxtake-live-stderr.log" },'
$hits = [regex]::Matches($t, [regex]::Escape($k)).Count
if ($hits -ne 1) { Write-Output "REFUSED: the FX taker line was found $hits times (want 1); nothing changed"; exit 1 }
$nl = if ($t.Contains("`r`n")) { "`r`n" } else { "`n" }      # the file's own line ending
$add = $nl +
  '    # 2026-10-26: the READ-ONLY FX / commodity 15-minute recorder (no key, no orders) -- results\add_fx_recorder_keepalive.ps1' + $nl +
  '    @{ n = "fx recorder (READ-ONLY, 15-min FX + commodity tape)"; like = "*hourly_collector.py*--fifteen-min*"; unlike = ""; stop = "$res\fx-collector.stop";' + $nl +
  '       a = @("-u", "research\hourly_collector.py", "--fifteen-min", "--minutes", "0", "--out", "C:\kals\kalshi_data_fx", "--pidfile", "$res\fx-collector.pid");' + $nl +
  '       o = "$res\fx-collector-stdout.log"; e = "$res\fx-collector-stderr.log" },'
$new = $t.Replace($k, $k + $add)
$errs = $null
[void][System.Management.Automation.Language.Parser]::ParseInput($new, [ref]$null, [ref]$errs)
if ($errs.Count) { Write-Output "REFUSED: the edited file would not parse ($($errs[0].Message)); nothing changed"; exit 1 }
$bak = if ($Target -eq "C:\kals-repo\boot_all.ps1") { "C:\kals-repo\results\boot_all.before-fx-recorder.ps1" } else { "$Target.before-fx-recorder" }
Copy-Item $Target $bak -Force
$b = [IO.File]::ReadAllBytes($Target)
$hasBom = $b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF
[IO.File]::WriteAllText($Target, $new, (New-Object Text.UTF8Encoding $hasBom))
Write-Output ("DONE: the FX recorder is in the keep-alive list (file {0} -> {1} chars; backup {2})" -f $t.Length, $new.Length, $bak)
