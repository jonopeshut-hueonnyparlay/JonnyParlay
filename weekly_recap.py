"""Root shim — delegates to engine/weekly_recap.py (L16).
Source of truth: engine/weekly_recap.py — edit that file, not this one."""
import os as _os, sys as _sys, runpy as _runpy
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "engine"))
_runpy.run_module("weekly_recap", run_name="__main__", alter_sys=True)
