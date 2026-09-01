# Registers the nightly poll, the nightly backup, the Sunday digest and the
# monthly export in Windows Task Scheduler. Run once from the repo root in
# PowerShell, passing a backup directory that is not this disk:
#     .\scripts\install-schedule.ps1 -BackupDir "D:\jobhunt-backups"
# Re-running replaces the tasks. Misses are tolerated.

param([string]$BackupDir = "")

$root = (Get-Location).Path
$python = (Get-Command python).Source
$log = Join-Path $root "data\local\scheduler.log"

$poll = "cmd /c `"cd /d `"$root`" && `"$python`" -m scraper poll >> `"$log`" 2>&1`""
$digest = "cmd /c `"cd /d `"$root`" && `"$python`" -m scraper digest >> `"$log`" 2>&1`""

schtasks /Create /F /TN "jobhunt poll" /SC DAILY /ST 02:30 /TR $poll | Out-Null
schtasks /Create /F /TN "jobhunt digest" /SC WEEKLY /D SUN /ST 07:00 /TR $digest | Out-Null
Write-Host "Registered: 'jobhunt poll' nightly at 02:30, 'jobhunt digest' Sundays at 07:00."

if ($BackupDir -ne "") {
  $backup = "cmd /c `"cd /d `"$root`" && `"$python`" -m scraper backup --to `"$BackupDir`" >> `"$log`" 2>&1`""
  $export = "cmd /c `"cd /d `"$root`" && `"$python`" -m scraper export --to `"$BackupDir`" >> `"$log`" 2>&1`""
  schtasks /Create /F /TN "jobhunt backup" /SC DAILY /ST 03:00 /TR $backup | Out-Null
  schtasks /Create /F /TN "jobhunt export" /SC MONTHLY /D 1 /ST 03:15 /TR $export | Out-Null
  Write-Host "Registered: 'jobhunt backup' nightly at 03:00 and 'jobhunt export' on the 1st, both to $BackupDir."
} else {
  Write-Host "No -BackupDir given, so no backup task. Nine months of history should not live on one disk."
}
Write-Host "Log: $log"
Write-Host "Remove with: schtasks /Delete /F /TN 'jobhunt poll' (and digest, backup, export)"
