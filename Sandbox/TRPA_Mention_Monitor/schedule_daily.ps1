# Registers a Windows scheduled task that refreshes the TRPA Mention Monitor data every day.
#
#   .\schedule_daily.ps1                     # 6:00 a.m. daily, refresh data\ only
#   .\schedule_daily.ps1 -At 5:30am          # a different time
#   .\schedule_daily.ps1 -Publish            # also commit and push data\ (GitHub Pages)
#   .\schedule_daily.ps1 -Remove             # delete the task
#
# The task runs as the current user, only while they're logged on (no stored password).
# It also runs at the next opportunity if the computer was off or asleep at the set time.
# Logs go to logs\update_YYYY-MM-DD.log.
param(
    [string]$At = "6:00am",
    [switch]$Publish,
    [switch]$Remove,
    [string]$TaskName = "TRPA Mention Monitor daily update"
)

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed scheduled task '$TaskName'."
    return
}

$runner = Join-Path $PSScriptRoot "run_daily.bat"
$arguments = "/c `"`"$runner`"$(if ($Publish) { ' publish' })`""
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $arguments -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Refreshes data\ for the TRPA Mention Monitor (python -m trpa_monitor)." -Force | Out-Null

Write-Host "Scheduled '$TaskName' daily at $At$(if ($Publish) { ', committing and pushing data\' })."
Write-Host "Run it now with:  Start-ScheduledTask -TaskName '$TaskName'"
