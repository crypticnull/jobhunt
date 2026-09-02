@echo off
rem Installs or repairs just the two scheduled tasks. Seconds, no polling.
rem An optional argument moves the nightly run:  schedule.cmd 03:00
cd /d "%~dp0"
if "%~1"=="" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\install-schedule.ps1"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\install-schedule.ps1" -NightlyAt "%~1"
)
echo.
schtasks /Query /TN "jobhunt nightly" /FO LIST 2>nul | findstr /C:"Next Run Time" /C:"Status"
pause
