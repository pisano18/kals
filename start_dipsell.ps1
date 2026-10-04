# start_dipsell.ps1 -- start the weather dip-seller live micro test (SJN1) in subaccount 3 (pool 0, funded $50 on 2026-10-04).
# Operator sign-off: "Yes run the test" / "Yes move weather" (2026-10-03/04). Stop it with results\dipsell-live.stop.
$p = Start-Process -FilePath "C:\Python314\python.exe" -ArgumentList @("-u","research\sweep\dipsell_live.py","--subaccount","3","--live","--minutes","21600") -WorkingDirectory "C:\kals-repo" -WindowStyle Hidden -RedirectStandardOutput "C:\kals-repo\results\dipsell-live-stdout.log" -RedirectStandardError "C:\kals-repo\results\dipsell-live-stderr.log" -PassThru
"started weather dip-seller pid $($p.Id); log results\dipsell-live-orders.jsonl"
