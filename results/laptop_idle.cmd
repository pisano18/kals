@echo off
rem Double-click: asks Windows for administrator rights, then stops the laptop's leftover research processes (see laptop_idle.ps1).
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-NoExit','-File','C:\kals-repo\results\laptop_idle.ps1'"
