# Registers the nightly job (pull, poll, backup) and the Sunday job (pull,
# digest) in Windows Task Scheduler. setup.cmd runs this; it can also be run
# by hand from the repo root:
#     .\scripts\install-schedule.ps1 -BackupDir "D:\jobhunt-backups"
# Re-running replaces the tasks. Misses are tolerated. The backup directory
# is remembered in data\local\backup-dir.txt so the nightly job can read it;
# without one, backups go to jobhunt-backups in the user profile, which is
# better than nothing but is still the same disk.

param([string]$BackupDir = "")

$root = (Get-Location).Path
$log = Join-Path $root "data\local\scheduler.log"
New-Item -ItemType Directory -Force -Path (Join-Path $root "data\local") | Out-Null

if ($BackupDir -eq "") { $BackupDir = Join-Path $env:USERPROFILE "jobhunt-backups" }
Set-Content -Path (Join-Path $root "data\local\backup-dir.txt") -Value $BackupDir -NoNewline

$nightly = "cmd /c `"`"$root\scripts\nightly.cmd`" >> `"$log`" 2>&1`""
$weekly = "cmd /c `"`"$root\scripts\weekly.cmd`" >> `"$log`" 2>&1`""

schtasks /Create /F /TN "jobhunt nightly" /SC DAILY /ST 02:30 /TR $nightly | Out-Null
schtasks /Create /F /TN "jobhunt weekly" /SC WEEKLY /D SUN /ST 07:00 /TR $weekly | Out-Null
schtasks /Delete /F /TN "jobhunt poll" 2>$null | Out-Null
schtasks /Delete /F /TN "jobhunt digest" 2>$null | Out-Null
schtasks /Delete /F /TN "jobhunt backup" 2>$null | Out-Null
Write-Host "Registered: 'jobhunt nightly' at 02:30 (pull, poll, backup to $BackupDir) and 'jobhunt weekly' Sundays at 07:00 (pull, digest)."
Write-Host "Log: $log"
Write-Host "Remove with: schtasks /Delete /F /TN 'jobhunt nightly' (and 'jobhunt weekly')"
