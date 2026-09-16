@echo off
REM open_deck.cmd -- rebuild the flight deck from the bot's own logs, then show it.
REM Double-click, or use the "Pin Deck" shortcut on the Desktop.
REM
REM It reads logs and writes one HTML file. It never touches the live bot,
REM the collector, or the account.
title Pin Deck
cd /d C:\kals-repo
echo Rebuilding the deck from the latest logs...
C:\Python314\python.exe research\pindeck.py
if errorlevel 1 (
  echo.
  echo The rebuild FAILED -- opening the last good copy instead.
  echo.
  pause
)
start "" "C:\kals-repo\results\pindeck.html"
exit /b 0
