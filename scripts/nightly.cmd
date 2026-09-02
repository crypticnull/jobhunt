@echo off
rem The nightly task. Pull what was merged, poll (which grows the list from
rem the discovery feeds), push the list back so the repo copy is the live one,
rem then back up. Run by Task Scheduler from the repo root; the log is
rem data\local\scheduler.log.
cd /d "%~dp0.."
echo ==== %date% %time% nightly
git pull --rebase --quiet origin main
python -m scraper poll
git add data/companies.json
git diff --cached --quiet || (git commit --quiet -m "companies: nightly discovery" && git push --quiet origin HEAD:main)
if exist "data\local\backup-dir.txt" (
  set /p BACKUP=<"data\local\backup-dir.txt"
  python -m scraper backup --to "%BACKUP%"
)
