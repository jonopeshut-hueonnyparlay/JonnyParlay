"""One-shot diagnostic / analysis tools for the projection engine.

Production code lives in engine/. Files in this directory are CLI scripts
invoked manually for calibration, audit, and ad-hoc diagnostics. None of
them are imported by production code (verified by grep at move time —
audit P4, 2026-05-06).

Run from the repo root, e.g.:
    python engine/tools/diag_h6_pool.py
"""
