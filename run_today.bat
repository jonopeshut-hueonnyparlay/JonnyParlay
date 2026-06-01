@echo off
if "%1"=="" (
    echo Usage: run_today [nba^|mlb^|nhl^|wnba]
    echo.
    echo Examples:
    echo   run_today nba
    echo   run_today mlb
    pause
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0go.ps1" -Sport %1
