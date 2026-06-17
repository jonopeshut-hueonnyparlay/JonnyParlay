"""P2.10 — pre-run config-integrity gate (_run_health_gate in run_picks.py).

The gate subprocess-runs health_check.py and aborts the run only on *blocking*
(integrity) failures; advisory items are warns and never block. These tests
exercise the decision logic without spawning a real subprocess.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))


class _FakeProc:
    def __init__(self, returncode, stdout=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


def test_skip_returns_without_spawning(monkeypatch):
    import run_picks

    def _boom(*a, **k):
        raise AssertionError("subprocess.run must not be called when skip=True")

    monkeypatch.setattr(subprocess, "run", _boom)
    assert run_picks._run_health_gate(True) is None  # no exception, no spawn


def test_pass_does_not_abort(monkeypatch):
    import run_picks
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeProc(0, "✅ PASSED: 146/146"))
    assert run_picks._run_health_gate(False) is None


def test_blocking_failure_aborts(monkeypatch):
    import run_picks
    out = "❌ FAILURES (1):\n  ❌ FAIL  NB_R ER=4.75\n          → drifted\n✅ PASSED: 145/146"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeProc(1, out))
    with pytest.raises(SystemExit):
        run_picks._run_health_gate(False)


def test_crash_without_fail_lines_does_not_abort(monkeypatch):
    # Non-zero exit but no FAIL lines → health_check itself errored; must not block.
    import run_picks
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: _FakeProc(1, "Traceback (most recent call last): ..."))
    assert run_picks._run_health_gate(False) is None


def test_subprocess_exception_does_not_abort(monkeypatch):
    import run_picks

    def _raise(*a, **k):
        raise OSError("python not found")

    monkeypatch.setattr(subprocess, "run", _raise)
    assert run_picks._run_health_gate(False) is None


def test_missing_health_check_file_does_not_abort(monkeypatch):
    import run_picks
    monkeypatch.setattr(run_picks.os.path, "exists", lambda p: False)
    # Should return before ever calling subprocess.run.
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not spawn")))
    assert run_picks._run_health_gate(False) is None


def test_parser_exposes_skip_flag():
    import run_picks
    args = run_picks._build_arg_parser().parse_args(["x.csv", "--skip-health-check"])
    assert args.skip_health_check is True
    args2 = run_picks._build_arg_parser().parse_args(["x.csv"])
    assert args2.skip_health_check is False


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
