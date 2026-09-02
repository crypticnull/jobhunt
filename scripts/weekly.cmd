@echo off
rem The Sunday task: the digest, after a pull so the ruleset is current, then
rem push it so it can be read from anywhere.
cd /d "%~dp0.."
echo ==== %date% %time% weekly
git -c rebase.autoStash=true pull --rebase --quiet origin main
python -m scraper digest
git add data/digests data/last-run.json
git diff --cached --quiet || (git commit --quiet -m "digest: this week" && (git push --quiet origin HEAD:main || (git -c rebase.autoStash=true pull --rebase --quiet origin main && git push --quiet origin HEAD:main)))
