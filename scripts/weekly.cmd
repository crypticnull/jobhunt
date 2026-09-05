@echo off
rem The Sunday task: the digest, after a pull so the ruleset is current, then
rem push it so it can be read from anywhere. It waits for a running nightly
rem first, up to ninety minutes, because both tasks commit in this one tree
rem and the second to arrive would otherwise fail on the index lock.
cd /d "%~dp0.."
set "PY=python"
if exist "data\local\python.txt" set /p PY=<"data\local\python.txt"
set "STATUS=data\local\nightly-status.log"
set /a TRIES=0
:wait
if not exist "data\local\nightly.lock" goto :go
set /a TRIES+=1
if %TRIES% geq 90 goto :go
timeout /t 60 /nobreak >nul
goto :wait
:go
echo ==== %date% %time% weekly
git rebase --abort >nul 2>&1
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD') do set "BRANCH=%%b"
if not "%BRANCH%"=="main" echo %date% %time% weekly not on main but on %BRANCH% >> "%STATUS%"
git -c rebase.autoStash=true pull --rebase --quiet origin main || echo %date% %time% weekly pull failed >> "%STATUS%"
%PY% -m scraper digest || echo %date% %time% digest failed >> "%STATUS%"
git add data/digests
git diff --cached --quiet && goto :end
git commit --quiet -m "digest: this week"
git push --quiet origin HEAD:main && goto :end
git -c rebase.autoStash=true pull --rebase --quiet origin main && git push --quiet origin HEAD:main || echo %date% %time% digest push failed >> "%STATUS%"
:end
