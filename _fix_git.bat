@echo off
cd /d C:\Users\jono4\Documents\JonnyParlay
del /f /q .git\index.lock 2>nul
del /f /q .git\index2.lock 2>nul
del /f /q .git\objects\maintenance.lock 2>nul
echo Lock files cleared.
git add engine\nba_projector.py engine\evaluate_projector.py engine\projections_db.py
git commit -m "feat(projector): Brief P3 Sec.5 — STL Bayesian shrinkage + opp TOV factor (BLK stays per-min)"
echo Done.
pause
