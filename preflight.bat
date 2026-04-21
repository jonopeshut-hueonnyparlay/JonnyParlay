@echo off
setlocal enabledelayedexpansion
REM ============================================================
REM  preflight.bat — JonnyParlay pre-run setup check
REM  Run this before the first run_picks.py of the day
REM ============================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo   JonnyParlay Preflight Check
echo ============================================================
echo.

REM ── 1. Python present AND >= 3.10? ─────────────────────────
REM  Audit L-5 (closed Apr 20 2026): we claim 3.10+ in the "missing" branch
REM  but never actually enforced it if an older interpreter was on PATH.
REM  run_picks.py + capture_clv.py use `from __future__ import annotations`
REM  with `X | Y` union syntax and zoneinfo — hard failures on 3.9. Check
REM  sys.version_info up front so the user gets ONE clear error instead of
REM  a cryptic ImportError deep in the engine.
python --version >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Python not found on PATH. Install Python 3.10+ first.
    goto :end
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    for /f "tokens=*" %%V in ('python --version 2^>^&1') do set PYV=%%V
    echo [FAIL] Python too old: !PYV! — JonnyParlay requires Python 3.10+.
    echo        Install from https://www.python.org/downloads/ and rerun.
    goto :end
)
for /f "tokens=*" %%V in ('python --version 2^>^&1') do set PYV=%%V
echo [ OK ] %PYV%

REM ── 2. filelock installed? ─────────────────────────────────
python -c "import filelock" >nul 2>&1
if errorlevel 1 (
    echo [WARN] filelock not installed — installing now...
    python -m pip install filelock --break-system-packages
    if errorlevel 1 (
        echo [FAIL] filelock install failed. Run manually:
        echo        pip install filelock --break-system-packages
    ) else (
        echo [ OK ] filelock installed
    )
) else (
    echo [ OK ] filelock present
)

REM ── 3. requests installed? ─────────────────────────────────
python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo [WARN] requests not installed — installing now...
    python -m pip install requests --break-system-packages
) else (
    echo [ OK ] requests present
)

REM ── 4. PIL/pillow (for results_graphic) ────────────────────
python -c "import PIL" >nul 2>&1
if errorlevel 1 (
    echo [WARN] pillow not installed — installing now...
    python -m pip install pillow --break-system-packages
) else (
    echo [ OK ] pillow present
)

REM ── 5. openpyxl (for xlsx recap export) ────────────────────
REM  Audit M-8 (closed Apr 20 2026): weekly_recap.py writes .xlsx via
REM  openpyxl. It was previously a silent feature-gated import — if it
REM  wasn't installed, the recap CLI printed a warning and skipped the
REM  xlsx attachment. Preflight now surfaces the gap up front.
python -c "import openpyxl" >nul 2>&1
if errorlevel 1 (
    echo [WARN] openpyxl not installed — installing now...
    python -m pip install openpyxl --break-system-packages
) else (
    echo [ OK ] openpyxl present
)

REM ── 6. Required files present? ─────────────────────────────
set MISSING=0
for %%F in (run_picks.py grade_picks.py capture_clv.py start_clv_daemon.bat) do (
    if not exist "%%F" (
        echo [FAIL] Missing: %%F
        set /a MISSING+=1
    ) else (
        echo [ OK ] %%F
    )
)
for %%F in (data\pick_log.csv) do (
    if not exist "%%F" (
        echo [WARN] Missing: %%F  ^(will be created on first run^)
    ) else (
        echo [ OK ] %%F
    )
)

REM ── 7. CLV daemon scheduled task? ──────────────────────────
schtasks /query /tn "JonnyParlay CLV Daemon" >nul 2>&1
if errorlevel 1 (
    echo [WARN] CLV daemon task not found. Create it with:
    echo        schtasks /create /tn "JonnyParlay CLV Daemon" /tr "%%~dp0start_clv_daemon.bat" /sc daily /st 10:00
) else (
    echo [ OK ] CLV daemon task scheduled
)

REM ── 8. Any stale lockfiles from crashed runs? ──────────────
REM  Audit L-13 (closed Apr 20 2026): we only cleaned pick_log.csv.lock
REM  before. clv_daemon.lock and discord_posted.json.lock can both survive
REM  a hard kill (Task Scheduler kill-tree, power loss) and then block the
REM  next run. Checking all three keeps the engine unblocked on boot.
for %%L in (
    data\pick_log.csv.lock
    data\clv_daemon.lock
    data\discord_posted.json.lock
) do (
    if exist "%%L" (
        echo [WARN] Found stale %%L — removing
        del /f /q "%%L" >nul 2>&1
    )
)

REM ── 9. Show today's log status ─────────────────────────────
for /f %%D in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set TODAY=%%D
echo.
echo Today: %TODAY%
python -c "import csv; rows=[r for r in csv.DictReader(open('data/pick_log.csv', encoding='utf-8')) if r.get('date')=='%TODAY%']; print(f'  Picks logged today: {len(rows)}')" 2>nul

echo.
echo ============================================================
echo   Ready. Next step:
echo     python run_picks.py nba.csv
echo     python run_picks.py nhl.csv
echo ============================================================

:end
echo.
pause
endlocal
