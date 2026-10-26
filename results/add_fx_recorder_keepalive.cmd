@echo off
rem Double-click: asks Windows for administrator rights, then adds the FX / commodity recorder to boot_all's keep-alive list (see add_fx_recorder_keepalive.ps1).
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-NoExit','-File','C:\kals-repo\results\add_fx_recorder_keepalive.ps1'"
