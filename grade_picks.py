"""Root shim — delegates to engine/grade_picks.py (L16).
Source of truth: engine/grade_picks.py — edit that file, not this one."""
import os as _os, sys as _sys, runpy as _runpy
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "engine"))
_runpy.run_module("grade_picks", run_name="__main__", alter_sys=True)
