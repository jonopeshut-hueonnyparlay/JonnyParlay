# ============================================================
#  JonnyParlay — Daily Shadow Projection Task Scheduler Setup
#  Run once as Administrator to register the scheduled task.
#  Usage: Right-click this file → "Run with PowerShell"
#
#  What it does: schedules a daily run of generate_projections.py
#  --shadow --research. Picks are logged to pick_log_custom.csv
#  with no Discord posts; CLV daemon (separate task) captures
#  closing odds automatically.
# ============================================================

$taskName  = "JonnyParlay Shadow Run"
$batFile   = "$PSScriptRoot\start_shadow_run.bat"
$startDir  = $PSScriptRoot
$startTime = "09:30"   # 9:30 AM local — well before tip-off; injury reports usually live by 9 AM ET

# Remove existing task if present (clean reinstall)
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction `
    -Execute    "cmd.exe" `
    -Argument   "/c `"$batFile`"" `
    -WorkingDirectory $startDir

$trigger = New-ScheduledTaskTrigger `
    -Daily `
    -At $startTime

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances    IgnoreNew `
    -ExecutionTimeLimit   (New-TimeSpan -Minutes 30) `
    -StartWhenAvailable   `
    -WakeToRun            `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries

$principal = New-ScheduledTaskPrincipal `
    -UserId    $env:USERNAME `
    -LogonType S4U `
    -RunLevel  Highest

Register-ScheduledTask `
    -TaskName  $taskName `
    -Action    $action `
    -Trigger   $trigger `
    -Settings  $settings `
    -Principal $principal `
    -Force | Out-Null

Write-Host ""
Write-Host "Task registered: '$taskName'" -ForegroundColor Green
Write-Host "  Runs daily at $startTime (local time), logs to: $startDir\data\shadow_run.log"
Write-Host ""
Write-Host "To run manually now:  Start-ScheduledTask -TaskName '$taskName'" -ForegroundColor Cyan
Write-Host "To unregister:        Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false" -ForegroundColor Cyan
Write-Host ""
