@echo off
:: ============================================================
::  JonnyParlay - Daily Shadow Projection Run
::  Runs generate_projections.py --shadow --research
::  Generates picks for today's NBA games, logs to pick_log_custom.csv
::  No Discord posts (shadow mode). Schedule: daily ~9:30 AM local time
:: ============================================================

set ROOT=C:\Users\jono4\Documents\JonnyParlay
set LOG=%ROOT%\data\shadow_run.log

cd /d "%ROOT%"
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

:: Preemptive log rotation — keeps shadow_run.log bounded.
set PYTHONPATH=%ROOT%\engine
python -c "from log_setup import preemptive_rotate; preemptive_rotate(r'%LOG%')"
set PYTHONPATH=

echo [%date% %time%] Shadow run starting >> "%LOG%"

python -u engine\generate_projections.py --shadow --research >> "%LOG%" 2>&1

echo [%date% %time%] Shadow run exited (code %ERRORLEVEL%) >> "%LOG%"
