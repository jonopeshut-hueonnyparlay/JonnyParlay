@echo off
:: Run setup_clv_task.ps1 with execution policy bypass
:: Double-click this file to install the CLV daemon scheduled task.

echo Setting up CLV daemon task...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_clv_task.ps1"

echo.
pause
