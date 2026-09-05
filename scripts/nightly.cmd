@echo off
rem The nightly task. Pull what was merged, take in any seed lists dropped into
rem data\seeds (already-known companies are skipped and a name with no board
rem becomes a hand-check record once, rather than being re-probed every night),
rem poll, which also grows the list from the discovery feeds, write the study
rem list, then push all three back so the repo copy is the live one and the
rem curriculum is versioned rather than logged. Then back up. Run by Task
rem Scheduler from the repo root; the log is data\local\scheduler.log and any
rem step that fails writes one line to data\local\nightly-status.log, which
rem the Sunday digest prints, so a job that stops says so in the repo.
cd /d "%~dp0.."
set "PY=python"
if exist "data\local\python.txt" set /p PY=<"data\local\python.txt"
set "STATUS=data\local\nightly-status.log"
if not exist "data\local" mkdir "data\local"
echo %date% %time% > "data\local\nightly.lock"
echo ==== %date% %time% nightly
rem A rebase that conflicted last night would otherwise stall every run after it.
git rebase --abort >nul 2>&1
git merge --abort >nul 2>&1
set "GITOK=1"
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD') do set "BRANCH=%%b"
if not "%BRANCH%"=="main" set "GITOK="
if not defined GITOK echo %date% %time% not on main but on %BRANCH%, git steps skipped >> "%STATUS%"
if defined GITOK git -c rebase.autoStash=true pull --rebase --quiet origin main || echo %date% %time% pull failed >> "%STATUS%"
%PY% -m scraper import data/seeds --manual || echo %date% %time% import failed >> "%STATUS%"
%PY% -m scraper poll || echo %date% %time% poll failed >> "%STATUS%"
%PY% -m scraper curriculum --write data/curriculum.md || echo %date% %time% curriculum failed >> "%STATUS%"
if not defined GITOK goto :backup
git add data/companies.json data/last-run.json data/curriculum.md
git diff --cached --quiet && goto :backup
git commit --quiet -m "nightly: discovery and curriculum" || echo %date% %time% commit failed >> "%STATUS%"
git push --quiet origin HEAD:main && goto :backup
git -c rebase.autoStash=true pull --rebase --quiet origin main && git push --quiet origin HEAD:main || echo %date% %time% push failed >> "%STATUS%"
:backup
rem Unbracketed on purpose: inside an if block %BACKUP% expands before set /p
rem runs, which is how fourteen copies of postings.db landed in the repo root.
set "BACKUP="
if exist "data\local\backup-dir.txt" set /p BACKUP=<"data\local\backup-dir.txt"
if defined BACKUP %PY% -m scraper backup --to "%BACKUP%" || echo %date% %time% backup failed >> "%STATUS%"
del "data\local\nightly.lock" >nul 2>&1
