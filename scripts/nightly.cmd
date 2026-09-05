@echo off
rem The nightly task. Pull what was merged, take in any seed lists dropped into
rem data\seeds (already-known companies are skipped, so this is safe to re-run),
rem poll, which also grows the list from the discovery feeds, write the study
rem list, then push all three back so the repo copy is the live one and the
rem curriculum is versioned rather than logged. Then back up. Run by Task
rem Scheduler from the repo root; the log is data\local\scheduler.log.
cd /d "%~dp0.."
echo ==== %date% %time% nightly
git -c rebase.autoStash=true pull --rebase --quiet origin main
python -m scraper import data/seeds
python -m scraper poll
python -m scraper curriculum --write data/curriculum.md
git add data/companies.json data/last-run.json data/curriculum.md
git diff --cached --quiet || (git commit --quiet -m "companies: nightly discovery" && (git push --quiet origin HEAD:main || (git -c rebase.autoStash=true pull --rebase --quiet origin main && git push --quiet origin HEAD:main)))
if exist "data\local\backup-dir.txt" (
  set /p BACKUP=<"data\local\backup-dir.txt"
  python -m scraper backup --to "%BACKUP%"
)
