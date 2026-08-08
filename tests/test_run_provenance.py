"""Run provenance: which code produced the last live pick run?

The gap being closed is silence on the live card. pick_log.csv's model_version is empty on all
390 graded picks and all 26,985 calibration rows, and run_id is populated on 1 of 390 — so the
only real-money record in this system had no code provenance at all.

Tests are aimed at the ways this could go quiet again, not at the happy path.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "engine"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import run_provenance as rp  # noqa: E402


def test_records_and_reads_back(tmp_path):
    p = tmp_path / "prov.json"
    ver = rp.record_run("2026-08-07T14:30", "primary", path=p)
    assert ver == rp.code_version()
    rec = rp.read_last_run(p)
    assert rec["run_id"] == "2026-08-07T14:30"
    assert rec["run_type"] == "primary"
    assert rec["recorded_at"].endswith("Z")


def test_recording_overwrites_rather_than_appends(tmp_path):
    """The question is which code produced the MOST RECENT run. A growing file would need
    parsing rules the reader does not have."""
    p = tmp_path / "prov.json"
    rp.record_run("run-1", path=p)
    rp.record_run("run-2", path=p)
    assert rp.read_last_run(p)["run_id"] == "run-2"
    assert len(json.loads(p.read_text(encoding="utf-8"))) == 4


def test_drift_is_detected(tmp_path, monkeypatch):
    p = tmp_path / "prov.json"
    monkeypatch.setattr(rp, "code_version", lambda: "aaaaaaaaaaaa")
    rp.record_run("run-1", path=p)
    monkeypatch.setattr(rp, "code_version", lambda: "bbbbbbbbbbbb")
    lvl, msg = rp.drift_status(p)
    assert lvl == "STALE"
    assert "aaaaaaaaaaaa" in msg and "bbbbbbbbbbbb" in msg
    assert "not attributable" in msg


def test_no_drift_is_ok(tmp_path, monkeypatch):
    p = tmp_path / "prov.json"
    monkeypatch.setattr(rp, "code_version", lambda: "abc123abc123")
    rp.record_run("run-1", path=p)
    lvl, msg = rp.drift_status(p)
    assert lvl == "OK"
    assert "run-1" in msg


def test_missing_record_is_NOT_ok(tmp_path):
    """THE failure mode. 'No record' means 'cannot tell', not 'no drift' — defaulting an
    unread field to success is how model_version stayed empty on 390 live picks."""
    lvl, msg = rp.drift_status(tmp_path / "absent.json")
    assert lvl == "WARN"
    assert "cannot tell" in msg


def test_malformed_record_is_NOT_ok(tmp_path):
    p = tmp_path / "prov.json"
    p.write_text("{ not json", encoding="utf-8")
    assert rp.read_last_run(p) is None
    assert rp.drift_status(p)[0] == "WARN"


def test_unresolvable_version_is_NOT_ok(tmp_path, monkeypatch):
    """Two 'unknown's are equal as strings and must not therefore read as a match."""
    p = tmp_path / "prov.json"
    monkeypatch.setattr(rp, "code_version", lambda: rp.UNKNOWN)
    rp.record_run("run-1", path=p)
    assert rp.drift_status(p)[0] == "WARN"


def test_a_dirty_tree_does_not_masquerade_as_the_committed_sha(monkeypatch):
    """Picks produced from a modified checkout must be distinguishable from the clean SHA."""
    monkeypatch.setattr(rp, "_git", lambda *a: "abcdef1234567" if a[0] == "rev-parse"
                        else " M engine/foo.py")
    assert rp.code_version() == "abcdef123456.dirty"


def test_failed_status_is_not_reported_as_clean(monkeypatch):
    seq = {"rev-parse": "abcdef1234567", "status": None}
    monkeypatch.setattr(rp, "_git", lambda *a: seq[a[0]])
    assert rp.code_version() == "abcdef123456.unknowndirty"


def test_recorder_never_raises_and_never_blocks_a_live_run(monkeypatch):
    """A provenance write must never take down a pick run."""
    def boom(*a, **k):
        raise OSError("read-only filesystem")
    monkeypatch.setattr(Path, "write_text", boom)
    assert rp.record_run("run-1") is None


def test_git_failure_degrades_to_unknown(monkeypatch):
    def boom(*a, **k):
        raise OSError("git not found")
    monkeypatch.setattr(subprocess, "run", boom)
    assert rp.code_version() == rp.UNKNOWN


def test_pick_writer_records_provenance():
    """The check is worthless if nothing writes the record — pin the call site."""
    src = (_ROOT / "engine" / "pick_log_writers.py").read_text(encoding="utf-8")
    assert "record_run(run_id, run_type)" in src


def test_health_check_reports_it():
    """An unwired check never runs, which is the same as not existing."""
    src = (_ROOT / "engine" / "health_check.py").read_text(encoding="utf-8")
    assert "drift_status()" in src


def test_model_version_is_left_alone():
    """model_version is a SOURCE tag (blank = live source, 'edgemodel' = sourced from
    EdgeModel). Overloading it with a code version would corrupt the one provenance field that
    already works, so provenance is recorded alongside rather than inside it."""
    src = (_ROOT / "engine" / "pick_log_writers.py").read_text(encoding="utf-8")
    assert '"model_version": ""' in src or '"model_version":   ""' in src
    assert '"model_version": "edgemodel"' in src or 'model_version": "edgemodel' in src
