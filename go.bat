@echo off
REM go.bat — wrapper for go.ps1
REM Usage:
REM   go.bat                    (interactive, full run)
REM   go.bat -SkipRun           (preflight only)
REM   go.bat -DryRun            (show what would happen)
REM   go.bat -Sports nba        (restrict to specific sport)
REM   go.bat -Sports nba,nhl    (multiple sports)

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0go.ps1" %*
set PSEXIT=%ERRORLEVEL%

echo.
echo ============================================================
if %PSEXIT% neq 0 (
    echo  go.ps1 exited with code %PSEXIT%
) else (
    echo  go.ps1 finished.
)
echo ============================================================
pause
