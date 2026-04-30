# ============================================================
#  JonnyParlay — CLV Daemon Task Scheduler Setup
#  Run once as Administrator to register the scheduled task.
#  Usage: Right-click this file → "Run with PowerShell"
# ============================================================

$taskName   = "JonnyParlay CLV Daemon"
$batFile    = "$PSScriptRoot\start_clv_daemon.bat"   # L13: was hardcoded to jono4 home
$startDir   = $PSScriptRoot
$startTime  = "10:00"   # 10am — runs before picks are posted, waits if needed

# Remove existing task if present (clean reinstall)
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$action  = New-ScheduledTaskAction `
    -Execute    "cmd.exe" `
    -Argument   "/c `"$batFile`"" `
    -WorkingDirectory $startDir

$trigger = New-ScheduledTaskTrigger `
    -Daily `
    -At $startTime

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances    IgnoreNew `
    -ExecutionTimeLimit   (New-TimeSpan -Hours 12) `
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
Write-Host "✅ Task registered: '$taskName'" -ForegroundColor Green
Write-Host "   Runs daily at $startTime, logs to: $startDir\data\clv_daemon.log"
Write-Host ""

# Fire it right now so today's picks get captured
Write-Host "▶  Starting daemon now for today..." -ForegroundColor Cyan
Start-ScheduledTask -TaskName $taskName

Write-Host "   Done. Check data\clv_daemon.log in a few seconds to confirm."
Write-Host ""
