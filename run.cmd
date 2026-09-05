@echo off
rem Run any scraper command from anywhere, with no cd and no PYTHONPATH.
rem
rem     X:\_CLAUDE\26_09_01_Job_Hunt\jobhunt\run.cmd pull
rem     X:\_CLAUDE\26_09_01_Job_Hunt\jobhunt\run.cmd score
rem     X:\_CLAUDE\26_09_01_Job_Hunt\jobhunt\run.cmd digest --stdout
rem     X:\_CLAUDE\26_09_01_Job_Hunt\jobhunt\run.cmd curriculum
rem
rem Every path inside the package resolves from the module's own location
rem rather than the working directory, so the only thing this has to fix is
rem where python looks for `scraper` itself. %~dp0 is this file's directory,
rem which is the repo root, so the launcher works wherever it is called from
rem and keeps working if the repo moves. The interpreter comes from the same
rem data\local\python.txt the scheduled tasks read, so a hand run and a
rem nightly run can never disagree about which python owns the database.
cd /d "%~dp0"
set "PY=python"
if exist "data\local\python.txt" set /p PY=<"data\local\python.txt"
if /i "%~1"=="pull" goto :pull
%PY% -m scraper %*
goto :eof

:pull
rem `pull` is not a scraper command, it is the one thing the launcher does on
rem its own. Only the nightly pulls on a schedule, so a digest run by hand at
rem noon reads whatever code was here at 04:00. If the rules moved in the
rem meantime the piles are stale and the digest lies quietly, which is worse
rem than an error. So pull, and if the pull touched the rules, rescore before
rem handing the shell back.
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD') do set "BRANCH=%%b"
if not "%BRANCH%"=="main" (
    echo On %BRANCH%, not main. Pull it yourself if that is deliberate.
    goto :eof
)
for /f "delims=" %%h in ('git rev-parse HEAD') do set "BEFORE=%%h"
git -c rebase.autoStash=true pull --rebase origin main || goto :eof
for /f "delims=" %%h in ('git rev-parse HEAD') do set "AFTER=%%h"
if "%BEFORE%"=="%AFTER%" (
    echo Already current, nothing to rescore.
    goto :eof
)
git diff --name-only %BEFORE% %AFTER% | findstr /i "data/scoring.json scraper/" >nul
if errorlevel 1 (
    echo Code moved but the rules did not, so the piles still stand.
    goto :eof
)
echo Rules moved, rescoring.
%PY% -m scraper score
