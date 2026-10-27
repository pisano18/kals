@echo off
rem Double-click after work: asks Windows for administrator rights ONCE, then runs all three jobs in order (see do_after_work.ps1): free ntopng's leaked memory, retire the finished paper tests, keep the FX recorder running.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-NoExit','-File','C:\kals-repo\results\do_after_work.ps1'"
