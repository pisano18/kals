# oddsmult_test.ps1 -- dress rehearsal of the patch on a scratch copy of the live build (nothing live is touched):
# copy 0925q -> results\oddsmult_test, patch, hash, run the FULL live argv + --selftest at BelowNormal priority.
$ErrorActionPreference = 'Stop'
$py = 'C:\Python314\python.exe'
$src = 'C:\kals-live-0925q'
$dst = 'C:\kals-repo\results\oddsmult_test'
if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
Copy-Item -Recurse $src $dst
Get-ChildItem -Recurse -Directory -Filter '__pycache__' $dst | Remove-Item -Recurse -Force
& $py -u 'C:\kals-repo\results\patch_oddsmult.py' "$dst\research\pinrun.py"
Write-Output ("sha " + (Get-FileHash -Algorithm SHA256 "$dst\research\pinrun.py").Hash.ToLower().Substring(0, 12))
$targs = @('-u', "$dst\research\pinrun.py",
  '--live', '--size', '20', '--minutes', '4320',
  '--loss-abort', '-60.00', '--max-positions', '3', '--max-losses', '0',
  '--improve-scope', 'market', '--pick', 'best',
  '--max-per-market', '2', '--improve-max', '0.010',
  '--max-full-bets', '1.0',
  '--band-mult', '0.955', '0.981', '1.5',
  '--hedge-jump', '6',
  '--wrongside-rise-c', '1.0',
  '--band99-ceiling', '0.99', '--band99-frac', '0.10',
  '--ws-later-fall-c', '10', '--hedge-jump-max', '8',
  '--hedge-odds-mult', '1.25', '--hedge-odds-min-tau', '11',
  '--coin-size-frac', 'KXHYPE15M:0.15',
  '--no-drawdown-halt',
  '--min-fill-frac', '0', '--sweep-depth', '--depth-ladder', '--jump-gate',
  '--hedge-belief', '0.40',
  '--early-tau', '45', '--early-frac', '0.333', '--early-min-price', '0.90',
  '--rebuy-late-tau', '15', '--rebuy-late-frac', '0.5',
  '--series', 'KXBTCD', '--series-size-frac', '0.12',
  '--early-max-edge', '10.0',
  '--no-hedge-prop',
  '--keep-conn', 'on', '--keep-warm', 'on',
  '--hedge-slip', '0.10',
  '--late-tau', '10', '--late-mult', '1.5',
  '--late-pin', '0.9975',
  '--late-jump', '2.0',
  '--extra-coin', '1',
  '--late-extra', '1',
  '--late-extra-tau', '15',
  '--bank-brake', '3.00',
  '--loss-cap-frac', '0.187',
  '--selftest')
$t0 = Get-Date
$p = Start-Process -FilePath $py -ArgumentList $targs -RedirectStandardOutput "$dst\selftest.out" -RedirectStandardError "$dst\selftest.err" -NoNewWindow -PassThru
$null = $p.Handle
try { $p.PriorityClass = 'BelowNormal' } catch {}
$p.WaitForExit()
Write-Output ("exit " + $p.ExitCode + " after " + [int]((Get-Date) - $t0).TotalSeconds + " s")
$so = Get-Content "$dst\selftest.out" -Raw
Write-Output ("ok lines " + ([regex]::Matches($so, '(?m)^  ok   ')).Count + "; FAIL lines " + ([regex]::Matches($so, '(?m)^  FAIL ')).Count)
Select-String -Path "$dst\selftest.out" -Pattern 'SELF-TEST|FAIL|v-oddsmult' | ForEach-Object { $_.Line.Substring(0, [Math]::Min(230, $_.Line.Length)) } | Select-Object -Last 40
Write-Output '--- stderr tail'
Get-Content "$dst\selftest.err" -Tail 15
