@echo off
rem Double-click: asks Windows for administrator rights, then stops every live bot on this laptop and keeps it from restarting them, so the Ohio server can run them (see laptop_handover.ps1). Never two copies of a live bot.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-NoExit','-File','C:\kals-repo\results\laptop_handover.ps1'"
