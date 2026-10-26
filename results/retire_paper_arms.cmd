@echo off
rem Double-click: asks Windows for administrator rights, then retires the September pin paper arms (see retire_paper_arms.ps1).
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-NoExit','-File','C:\kals-repo\results\retire_paper_arms.ps1'"
