@echo off
rem Start the site locally, from anywhere, with no cd.
rem
rem     X:\_CLAUDE\26_09_01_Job_Hunt\jobhunt\dev.cmd
rem
rem It installs on the first run and on any run where package-lock.json is
rem newer than node_modules, then serves with --host so a phone on the same
rem network can open it too. "Works on a phone" is a stated non-negotiable and
rem a laptop is a bad place to check it.
setlocal
cd /d "%~dp0site"
where npm >nul 2>&1 || (
    echo npm is not on the PATH. Install Node 22 and reopen the shell.
    exit /b 1
)
if not exist node_modules (
    echo First run, installing.
    call npm install || exit /b 1
) else (
    rem A pulled lockfile means the dependencies moved under the tree on disk.
    for %%f in (package-lock.json) do set LOCK=%%~tf
    for %%f in (node_modules) do set MODS=%%~tf
    if "%LOCK%" gtr "%MODS%" (
        echo Lockfile is newer than node_modules, installing.
        call npm install || exit /b 1
    )
)
echo.
echo   the site         http://localhost:4321/
echo   wireframe        http://localhost:4321/?wire
echo   slot inventory   http://localhost:4321/wire
echo   motion lab       http://localhost:4321/wire/motion
echo   design system    http://localhost:4321/system
echo.
echo   Edits are live. Ctrl-C stops it.
echo.
call npm run dev -- --host
endlocal
