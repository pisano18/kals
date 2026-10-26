@echo off
rem Double-click: asks Windows for administrator rights, then restarts the ntopng service to free the ~3 GB of kernel memory it leaks (see restart_ntopng.ps1). The bots keep running.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-NoExit','-File','C:\kals-repo\results\restart_ntopng.ps1'"
