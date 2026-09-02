@echo off
rem The nightly task. Pull what was merged, then poll. Run by Task Scheduler
rem from the repo root; the log is data\local\scheduler.log.
cd /d "%~dp0.."
echo ==== %date% %time% nightly
git pull --ff-only --quiet origin main
python -m scraper poll
if exist "data\local\backup-dir.txt" (
  set /p BACKUP=<"data\local\backup-dir.txt"
  python -m scraper backup --to "%BACKUP%"
)
