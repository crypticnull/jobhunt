@echo off
rem Double-click once. Pulls the latest, registers the nightly and weekly
rem tasks, seeds the company list from assets\companies.txt if there is one,
rem and runs the first poll so there is something to look at tomorrow.
cd /d "%~dp0"
echo.
echo == jobhunt setup ==
git pull --rebase origin main
if errorlevel 1 (
  echo git pull failed. Is this folder the clone of the jobhunt repo?
  pause
  exit /b 1
)
git config core.hooksPath .githooks
if not exist "data\local" mkdir "data\local"
if not exist "data\local\scoring.local.json" echo WARNING: data\local\scoring.local.json is missing, posted salaries will be flagged, not scored.
if exist "assets\companies.txt" (
  echo.
  echo Seeding the company list from assets\companies.txt ...
  python -m scraper import "assets\companies.txt"
)
echo.
echo Registering the scheduled tasks ...
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\install-schedule.ps1"
echo.
echo First poll, this can take a few minutes ...
python -m scraper poll
echo.
echo Pushing the company list so the repo copy is the live one ...
git add data/companies.json
git diff --cached --quiet || (git commit --quiet -m "companies: first poll" && git push --quiet origin HEAD:main)
echo.
echo Done. The digest lands in data\local\digests every Sunday morning.
echo Nothing else to run. The nightly task pulls updates and pushes the list on its own.
pause
