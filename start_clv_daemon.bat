@echo off
:: ============================================================
::  JonnyParlay - CLV Capture Daemon
::  Runs capture_clv.py for today's picks.
::  Self-terminates once all picks are captured.
::  Schedule via Task Scheduler: daily at 10:00 AM local time
:: ============================================================

set ROOT=C:\Users\jono4\Documents\JonnyParlay
set LOG=%ROOT%\data\clv_daemon.log

cd /d "%ROOT%"
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

:: Preemptive log rotation (audit M-24, closed Apr 20 2026)
:: The >> redirect below would hold the log file open for the entire daemon
:: lifetime, so Python cannot rename it from inside capture_clv.py on Windows.
:: Instead we rotate HERE, in a tiny separate python process, BEFORE the
:: redirect opens. Keeps clv_daemon.log bounded to ROTATION_MAX_BYTES per
:: backup x (ROTATION_BACKUP_COUNT + 1) files. Failures are non-fatal --
:: preemptive_rotate() swallows OS errors so the daemon still starts.
set PYTHONPATH=%ROOT%\engine
python -c "from log_setup import preemptive_rotate; preemptive_rotate(r'%LOG%')"
set PYTHONPATH=

echo [%date% %time%] CLV daemon starting >> "%LOG%"

python -u engine\capture_clv.py >> "%LOG%" 2>&1

echo [%date% %time%] CLV daemon exited >> "%LOG%"
