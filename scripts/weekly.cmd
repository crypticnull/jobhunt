@echo off
rem The Sunday task: the digest, after a pull so the ruleset is current.
cd /d "%~dp0.."
echo ==== %date% %time% weekly
git pull --rebase --quiet origin main
python -m scraper digest
