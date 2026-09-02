@echo off
rem Double-click this. It hands the work to scripts\setup.ps1, which writes
rem everything it does to setup.log, so nothing is lost when this window closes.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\setup.ps1"
echo.
echo A full record of this run is in setup.log
pause
