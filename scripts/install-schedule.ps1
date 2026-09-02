# Registers the nightly job (pull, poll, push, backup) and the Sunday job
# (pull, digest, push) in Windows Task Scheduler. setup.cmd runs this; it can
# also be run by hand from the repo root:
#     .\scripts\install-schedule.ps1 -BackupDir "D:\jobhunt-backups" -NightlyAt 04:00
#
# Re-running replaces the tasks. A workstation is asleep or switched off at
# half two most nights, so the tasks are registered with StartWhenAvailable,
# which runs a missed job at the next opportunity instead of skipping the day,
# and WakeToRun, which wakes the machine when the power settings allow it.
# Together they mean a machine that is on at any point in the day still gets
# its poll. Both run at Windows priority 9, the lowest the scheduler offers,
# so an overnight render or a game always wins the CPU. The work is a few
# minutes of waiting on HTTP anyway.
#
# The backup directory is remembered in data\local\backup-dir.txt so the
# nightly job can read it; without one, backups go to jobhunt-backups in the
# user profile, which is better than nothing but is still the same disk.

param([string]$BackupDir = "", [string]$NightlyAt = "04:00", [string]$WeeklyAt = "07:00")

$root = (Get-Location).Path
$log = Join-Path $root "data\local\scheduler.log"
New-Item -ItemType Directory -Force -Path (Join-Path $root "data\local") | Out-Null

if ($BackupDir -eq "") { $BackupDir = Join-Path $env:USERPROFILE "jobhunt-backups" }
Set-Content -Path (Join-Path $root "data\local\backup-dir.txt") -Value $BackupDir -NoNewline

function Register-Job($name, $script, $trigger, $fallback) {
    $arg = "/c `"`"$root\$script`" >> `"$log`" 2>&1`""
    try {
        $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $arg -WorkingDirectory $root
        $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun `
            -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2) -Priority 9
        Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
        return $true
    } catch {
        # Older Windows without the ScheduledTasks module. schtasks always
        # works but cannot catch up a missed run, so say so rather than
        # letting it look the same.
        schtasks /Create /F /TN $name /TR "cmd $arg" @fallback | Out-Null
        return $false
    }
}

$full = $true
$full = (Register-Job "jobhunt nightly" "scripts\nightly.cmd" (New-ScheduledTaskTrigger -Daily -At $NightlyAt) @("/SC", "DAILY", "/ST", $NightlyAt)) -and $full
$full = (Register-Job "jobhunt weekly" "scripts\weekly.cmd" (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At $WeeklyAt) @("/SC", "WEEKLY", "/D", "SUN", "/ST", $WeeklyAt)) -and $full

foreach ($old in @("jobhunt poll", "jobhunt digest", "jobhunt backup")) {
    schtasks /Delete /F /TN $old 2>$null | Out-Null
}

Write-Host "Registered: 'jobhunt nightly' at $NightlyAt (pull, poll, push, backup to $BackupDir)"
Write-Host "            'jobhunt weekly' Sundays at $WeeklyAt (pull, digest, push)"
Write-Host "Both run at the lowest scheduler priority, so a render or a game keeps the CPU."
if ($full) {
    Write-Host "Both catch up if the machine was off or asleep, and will wake it if Windows power settings allow."
} else {
    Write-Host "NOTE: registered the simple way, so a run missed while the machine was off is skipped rather than caught up."
}
Write-Host "Log: $log"
Write-Host "Remove with: schtasks /Delete /F /TN 'jobhunt nightly' (and 'jobhunt weekly')"
