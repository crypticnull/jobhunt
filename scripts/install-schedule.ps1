# Registers the nightly job (pull, poll, push, backup) and the Sunday job
# (pull, digest, push) in Windows Task Scheduler. setup.cmd runs this; it can
# also be run by hand from the repo root:
#     .\scripts\install-schedule.ps1 -BackupDir "D:\jobhunt-backups" -NightlyAt 04:00
#
# Registration goes through schtasks with a task XML file rather than
# Register-ScheduledTask, which returned Access denied on Matt's machine:
# replacing an existing task through that cmdlet wants elevation, while
# schtasks writing the current user's own task does not. The XML carries every
# setting the cmdlet would have:
#
#   StartWhenAvailable  a run missed while the machine was off or asleep
#                       happens at the next opportunity instead of being lost
#   LogonTrigger        ten minutes after any sign-in, because a task with no
#                       stored password only runs for a logged-on user
#   WakeToRun           wakes the machine where the power settings allow it
#   Priority 9          the lowest the scheduler offers, so an overnight render
#                       or a game always wins the CPU
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

function Esc($s) { $s.Replace("&", "&amp;").Replace("<", "&lt;").Replace(">", "&gt;").Replace('"', "&quot;") }

function Task-Xml($script, $triggerXml) {
    $taskArgs = Esc("/c `"`"$root\$script`" >> `"$log`" 2>&1`"")
    $desc = Esc($script)
    $wd = Esc($root)
    @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>jobhunt: $desc</Description></RegistrationInfo>
  <Triggers>
$triggerXml
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <Enabled>true</Enabled>
    <StartWhenAvailable>true</StartWhenAvailable>
    <WakeToRun>true</WakeToRun>
    <Priority>9</Priority>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>cmd.exe</Command>
      <Arguments>$taskArgs</Arguments>
      <WorkingDirectory>$wd</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@
}

function Register-Job($name, $script, $triggerXml, $fallback) {
    $xml = Join-Path $env:TEMP "jobhunt-task.xml"
    # schtasks reads the file as UTF-16, which is what the header declares.
    Set-Content -Path $xml -Value (Task-Xml $script $triggerXml) -Encoding Unicode
    schtasks /Create /F /TN $name /XML $xml 2>&1 | Out-Null
    $ok = ($LASTEXITCODE -eq 0)
    Remove-Item $xml -ErrorAction SilentlyContinue
    if ($ok) { return $true }
    # Fall back to the plain form. It cannot carry the settings above, but it
    # does at least put the job on the clock.
    schtasks /Create /F /TN $name /TR "cmd /c `"`"$root\$script`" >> `"$log`" 2>&1`"" @fallback 2>&1 | Out-Null
    return $false
}

# The date only sets the first occurrence; the schedule below repeats it.
$start = (Get-Date $NightlyAt).ToString("yyyy-MM-ddTHH:mm:ss")
$weekStart = (Get-Date $WeeklyAt).ToString("yyyy-MM-ddTHH:mm:ss")

$nightlyTriggers = @"
    <CalendarTrigger>
      <StartBoundary>$start</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
    </CalendarTrigger>
    <LogonTrigger><Enabled>true</Enabled><Delay>PT10M</Delay></LogonTrigger>
"@

$weeklyTriggers = @"
    <CalendarTrigger>
      <StartBoundary>$weekStart</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByWeek><DaysOfWeek><Sunday /></DaysOfWeek><WeeksInterval>1</WeeksInterval></ScheduleByWeek>
    </CalendarTrigger>
"@

$full = $true
$full = (Register-Job "jobhunt nightly" "scripts\nightly.cmd" $nightlyTriggers @("/SC", "DAILY", "/ST", $NightlyAt)) -and $full
$full = (Register-Job "jobhunt weekly" "scripts\weekly.cmd" $weeklyTriggers @("/SC", "WEEKLY", "/D", "SUN", "/ST", $WeeklyAt)) -and $full

foreach ($old in @("jobhunt poll", "jobhunt digest", "jobhunt backup")) {
    schtasks /Delete /F /TN $old 2>$null | Out-Null
}

Write-Host "Registered: 'jobhunt nightly' at $NightlyAt (pull, poll, push, backup to $BackupDir)"
Write-Host "            'jobhunt weekly' Sundays at $WeeklyAt (pull, digest, push)"
if ($full) {
    Write-Host "Both run at the lowest priority and catch up a run the machine slept through. The nightly one also runs ten minutes after any sign-in."
} else {
    Write-Host "NOTE: the full settings would not register, so these are on the clock only. A run missed while the machine was off is skipped rather than caught up."
}
Write-Host "Check them with: schtasks /Query /TN ""jobhunt nightly"" /V /FO LIST"
Write-Host "Log: $log"
Write-Host "Remove with: schtasks /Delete /F /TN ""jobhunt nightly"" (and ""jobhunt weekly"")"
