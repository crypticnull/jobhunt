@echo off
rem Double-click this. It hands the work to scripts\setup.ps1, which writes
rem everything it does to setup.log, so nothing is lost when this window closes.
rem An optional argument moves the nightly run:  setup.cmd 03:00
cd /d "%~dp0"
if "%~1"=="" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\setup.ps1"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\setup.ps1" -NightlyAt "%~1"
)
echo.
echo A full record of this run is in setup.log
pause
