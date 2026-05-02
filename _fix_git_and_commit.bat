@echo off
cd /d "C:\Users\jono4\Documents\JonnyParlay"
echo Removing git lock files...
del /f /q ".git\index.lock" 2>nul
del /f /q ".git\index2.lock" 2>nul
del /f /q ".git\objects\maintenance.lock" 2>nul
echo Lock files removed.
echo.
echo Staging files...
git add engine/nba_projector.py engine/evaluate_projector.py engine/projections_db.py
echo.
echo Committing...
git commit -m "feat(projector): Brief P3 Sec.5+6 -- STL/BLK Bayesian rates + continuous days-rest model"
echo.
echo Done. Press any key to close.
pause >nul
