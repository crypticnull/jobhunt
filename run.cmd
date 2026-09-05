@echo off
rem Run any scraper command from anywhere, with no cd and no PYTHONPATH.
rem
rem     X:\_CLAUDE\26_09_01_Job_Hunt\jobhunt\run.cmd score
rem     X:\_CLAUDE\26_09_01_Job_Hunt\jobhunt\run.cmd digest --stdout
rem     X:\_CLAUDE\26_09_01_Job_Hunt\jobhunt\run.cmd curriculum
rem
rem Every path inside the package resolves from the module's own location
rem rather than the working directory, so the only thing this has to fix is
rem where python looks for `scraper` itself. %~dp0 is this file's directory,
rem which is the repo root, so the launcher works wherever it is called from
rem and keeps working if the repo moves.
cd /d "%~dp0"
python -m scraper %*
