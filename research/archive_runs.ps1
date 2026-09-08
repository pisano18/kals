# archive_runs.ps1 -- keep the live-run evidence durable.
#
# The operator wants reports a week and a month from now, so the per-close
# records the live trader writes must survive without anyone remembering to
# save them. This commits and pushes results/ every 20 minutes, forever, and
# does nothing at all when nothing changed (so history stays readable).
#
# It only ever touches results/. It never runs a strategy, never places an
# order, and never touches C:\kals.
#
# Start detached:
#   powershell -NoProfile -WindowStyle Hidden -File C:\kals-repo\research\archive_runs.ps1

$repo = "C:\kals-repo"
$log  = "C:\kals-repo\results\archive_runs.log"
Set-Location $repo

function Say($m) {
  $line = "{0}  {1}" -f (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"), $m
  Add-Content -Path $log -Value $line -Encoding utf8
}

Say "archiver started"

while ($true) {
  try {
    # only the evidence, never code -- a code commit is a human decision
    git add results/pinrun-live-*.jsonl results/pinrun-paper-*.jsonl `
            results/pinsmoke-*.jsonl results/*.log results/OVERNIGHT.md `
            results/MORNING.md 2>$null

    $staged = git diff --cached --name-only 2>$null
    if ($staged) {
      $n = ($staged | Measure-Object).Count
      $stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd HH:mm")
      git commit -q -m "archive: live run evidence $stamp UTC ($n files)

Automatic. Preserves the per-close records the live trader writes so that a
report a week or a month from now has the full history rather than whatever
happened to be committed by hand.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Jm2VPm9As6VQk1YUzuRs8p" 2>$null
      git push -q origin claude/file-uploads-70rtjl 2>$null
      Say ("committed {0} file(s)" -f $n)
    }
  } catch {
    Say ("ERROR " + $_.Exception.Message)
  }
  Start-Sleep -Seconds 1200
}
