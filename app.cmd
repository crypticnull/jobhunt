@echo off
rem The job hunt as one window, from anywhere, with no cd.
rem
rem     X:\_CLAUDE\26_09_01_Job_Hunt\jobhunt\app.cmd
rem
rem Pin it to the taskbar and this is the only thing you ever run. It starts
rem the console itself and the site the first time you click Site, and a second
rem launch focuses the window that is already open rather than starting another.
rem
rem The first run installs Electron, which is a few hundred megabytes and takes
rem a minute. Every run after that is instant.
setlocal
cd /d "%~dp0desktop"
where npm >nul 2>&1 || (
    echo npm is not on the PATH. Install Node 22 and reopen the shell.
    exit /b 1
)
if not exist node_modules (
    echo First run, installing Electron. This takes a minute and only happens once.
    call npm install || exit /b 1
)
call npm start
endlocal
