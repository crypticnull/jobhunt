# Registers the nightly poll and the Sunday digest in Windows Task Scheduler.
# Run once from the repo root in PowerShell. Re-running replaces the tasks.
# Misses are tolerated: a weekly cadence does not care about one skipped night.

$root = (Get-Location).Path
$python = (Get-Command python).Source
$log = Join-Path $root "data\local\scheduler.log"

$poll = "cmd /c `"cd /d `"$root`" && `"$python`" -m scraper poll >> `"$log`" 2>&1`""
$digest = "cmd /c `"cd /d `"$root`" && `"$python`" -m scraper digest >> `"$log`" 2>&1`""

schtasks /Create /F /TN "jobhunt poll" /SC DAILY /ST 02:30 /TR $poll | Out-Null
schtasks /Create /F /TN "jobhunt digest" /SC WEEKLY /D SUN /ST 07:00 /TR $digest | Out-Null

Write-Host "Registered: 'jobhunt poll' nightly at 02:30, 'jobhunt digest' Sundays at 07:00."
Write-Host "Log: $log"
Write-Host "Remove with: schtasks /Delete /F /TN 'jobhunt poll'; schtasks /Delete /F /TN 'jobhunt digest'"
