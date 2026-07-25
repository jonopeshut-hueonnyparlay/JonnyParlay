"""One-shot diagnostic / analysis tools for the JonnyParlay engine.

Production code lives in engine/. Files in this directory are CLI scripts
invoked manually for calibration, audit, and ad-hoc diagnostics. None of
them are imported by production code (verified by grep at move time —
audit P4, 2026-05-06).

H8 (2026-07-25): _check_dvp.py, analyze_playoff_scalars.py,
diag_blowout_buckets.py, diag_h6_backtest.py, and diag_h6_pool.py moved to
EdgeModel/engine/tools/ -- they only ever queried EdgeModel's own DB via
projections_db/nba_projector, reached via a bare sys.path.insert() into
JonnyParlay's own engine/ with no EDGEMODEL_ROOT guard, so they bare-crashed
with ModuleNotFoundError whenever EdgeModel wasn't checked out as a sibling.

Run from the repo root, e.g.:
    python engine/tools/diag_h1_constraint_chain.py
"""
