@echo off
:: ============================================================
::  JonnyParlay — CLV Capture Daemon
::  Runs capture_clv.py for today's picks.
::  Self-terminates once all picks are captured.
::  Schedule via Task Scheduler: daily at 12:00 PM ET
:: ============================================================

set ROOT=C:\Users\jono4\Documents\JonnyParlay
set LOG=%ROOT%\data\clv_daemon.log

echo [%date% %time%] CLV daemon starting >> "%LOG%"

cd /d "%ROOT%"
set PYTHONIOENCODING=utf-8
chcp 65001 > nul
python engine\capture_clv.py >> "%LOG%" 2>&1

echo [%date% %time%] CLV daemon exited >> "%LOG%"
