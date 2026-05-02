"""Section 38 — atomic_write_json consolidation (architectural note #2).

Five modules used to each carry their own tmp+fsync+replace dance:

    engine/discord_guard.py   (_save_unlocked)
    engine/capture_clv.py     (save_checkpoint)
    engine/grade_picks.py     (_save_guard)
    engine/morning_preview.py (_save_guard)
    engine/weekly_recap.py    (_save_guard)
    engine/run_picks.py       (_save_discord_guard)

All now delegate to ``engine/io_utils.atomic_write_json``. These tests
enforce:

* The helper exists, has the right signature, and round-trips JSON data.
* Atomicity: a crash between the tmp write and the replace leaves the
  target either untouched (original content) or complete — never empty
  or truncated.
* Tmp-file cleanup: a failure during write does not leak a ``*.tmp`` file.
* Every migrated caller actually imports from ``io_utils`` and has dropped
  the inline mkstemp/tempfile dance from its save path.
* Root mirrors stay byte-identical to ``engine/`` for every migrated file.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = REPO_ROOT / "engine"

# Make ``engine/`` importable the same way the launchers do.
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))


# ── io_utils.atomic_write_json: behaviour ──────────────────────────────────

def test_io_utils_module_exists():
    assert (ENGINE_DIR / "io_utils.py").is_file(), (
        "engine/io_utils.py must exist — arch note #2"
    )


def test_atomic_write_json_exported():
    import io_utils
    assert hasattr(io_utils, "atomic_write_json")
    assert "atomic_write_json" in io_utils.__all__


def test_atomic_write_json_round_trips(tmp_path):
    from io_utils import atomic_write_json
    p = tmp_path / "x.json"
    data = {"a": 1, "b": [2, 3], "c": {"d": None}}
    atomic_write_json(p, data)
    assert json.loads(p.read_text(encoding="utf-8")) == data


def test_atomic_write_json_creates_parent_dir(tmp_path):
    from io_utils import atomic_write_json
    p = tmp_path / "deep" / "nested" / "x.json"
    atomic_write_json(p, {"ok": True})
    assert p.is_file()


def test_atomic_write_json_leaves_no_tmp_on_success(tmp_path):
    from io_utils import atomic_write_json
    p = tmp_path / "x.json"
    atomic_write_json(p, {"ok": True})
    leftovers = [f for f in os.listdir(tmp_path) if f.endswith(".tmp")]
    assert leftovers == [], f"tmp files leaked: {leftovers}"


def test_atomic_write_json_cleans_tmp_on_failure(tmp_path, monkeypatch):
    """If json.dump raises, the tmp file must be removed and the exception
    re-raised — no silent swallow, no orphaned tmp."""
    import io_utils
    from io_utils import atomic_write_json
    p = tmp_path / "x.json"

    def _boom(*a, **kw):  # noqa: ANN001
        raise TypeError("nope")

    monkeypatch.setattr(io_utils.json, "dump", _boom)
    with pytest.raises(TypeError):
        atomic_write_json(p, {"ok": True})
    # No tmp file left behind in the target directory.
    leftovers = [f for f in os.listdir(tmp_path) if f.endswith(".tmp")]
    assert leftovers == [], f"tmp files leaked on failure: {leftovers}"
    # Target itself must not have been created.
    assert not p.exists()


def test_atomic_write_json_original_survives_failed_write(tmp_path, monkeypatch):
    """If the tmp write fails, the existing target file must be untouched —
    this is the whole point of the tmp+replace dance."""
    import io_utils
    from io_utils import atomic_write_json

    p = tmp_path / "x.json"
    original = {"version": 1}
    p.write_text(json.dumps(original), encoding="utf-8")

    def _boom(*a, **kw):  # noqa: ANN001
        raise TypeError("nope")

    monkeypatch.setattr(io_utils.json, "dump", _boom)
    with pytest.raises(TypeError):
        atomic_write_json(p, {"version": 2})
    # Original content preserved.
    assert json.loads(p.read_text(encoding="utf-8")) == original


def test_atomic_write_json_overwrites_existing(tmp_path):
    from io_utils import atomic_write_json
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"old": True}), encoding="utf-8")
    atomic_write_json(p, {"new": True})
    assert json.loads(p.read_text(encoding="utf-8")) == {"new": True}


def test_atomic_write_json_accepts_pathlib_and_str(tmp_path):
    from io_utils import atomic_write_json
    p1 = tmp_path / "p1.json"
    p2 = tmp_path / "p2.json"
    atomic_write_json(p1, {"k": 1})
    atomic_write_json(str(p2), {"k": 2})
    assert json.loads(p1.read_text(encoding="utf-8")) == {"k": 1}
    assert json.loads(p2.read_text(encoding="utf-8")) == {"k": 2}


# ── Consumer migration: every save path routes through io_utils ──────────────

_CONSUMERS_WITH_SAVE_FN = [
    # (filename, save-function name that must NOT contain the inline dance)
    ("discord_guard.py",   "_save_unlocked"),
    ("capture_clv.py",     "save_checkpoint"),
    ("grade_picks.py",     "_save_guard"),
    ("morning_preview.py", "_save_guard"),
    ("weekly_recap.py",    "_save_guard"),
    ("run_picks.py",       "_save_discord_guard"),
]


@pytest.mark.parametrize("fname, _fn", _CONSUMERS_WITH_SAVE_FN,
                         ids=[f for f, _ in _CONSUMERS_WITH_SAVE_FN])
def test_consumer_imports_atomic_write_json(fname, _fn):
    src = (ENGINE_DIR / fname).read_text(encoding="utf-8")
    assert re.search(r"from\s+io_utils\s+import\s+[^\n]*atomic_write_json", src), (
        f"{fname} must `from io_utils import atomic_write_json` — arch note #2"
    )


def _extract_function_body(src: str, fn_name: str) -> str:
    """Return the source of the first def matching ``fn_name`` (name + body).
    Falls back to full src on parse hiccups — test will just be stricter."""
    import ast
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == fn_name:
            lines = src.splitlines()
            start = node.lineno - 1
            end = node.end_lineno  # inclusive
            return "\n".join(lines[start:end])
    return ""


# The primary success path of each save fn must delegate to
# atomic_write_json — the inline mkstemp/tempfile dance must be gone
# (fallback-only code can still reference raw json/open for best-effort
# writes, but only in the `except` branch after the helper fails).
_MIGRATED_SAVE_FNS = [
    ("discord_guard.py",   "_save_unlocked"),
    ("capture_clv.py",     "save_checkpoint"),
    ("grade_picks.py",     "_save_guard"),
    ("morning_preview.py", "_save_guard"),
    ("weekly_recap.py",    "_save_guard"),
    ("run_picks.py",       "_save_discord_guard"),
]


@pytest.mark.parametrize("fname, fn", _MIGRATED_SAVE_FNS,
                         ids=[f"{f}::{fn}" for f, fn in _MIGRATED_SAVE_FNS])
def test_save_fn_delegates_to_atomic_write_json(fname, fn):
    src = (ENGINE_DIR / fname).read_text(encoding="utf-8")
    body = _extract_function_body(src, fn)
    assert body, f"couldn't find def {fn} in {fname}"
    assert "atomic_write_json(" in body, (
        f"{fname}::{fn} must call atomic_write_json(...) — arch note #2"
    )


@pytest.mark.parametrize("fname, fn", _MIGRATED_SAVE_FNS,
                         ids=[f"{f}::{fn}" for f, fn in _MIGRATED_SAVE_FNS])
def test_save_fn_has_no_inline_mkstemp_dance(fname, fn):
    """The inline ``tempfile.mkstemp(...)`` + ``os.fdopen`` shape must be
    gone from the primary write path. Other files (atomic CSV writes in
    grade_picks._atomic_write_rows, for example) can still use mkstemp —
    the test is scoped per-function."""
    src = (ENGINE_DIR / fname).read_text(encoding="utf-8")
    body = _extract_function_body(src, fn)
    assert body, f"couldn't find def {fn} in {fname}"
    assert "tempfile.mkstemp" not in body, (
        f"{fname}::{fn} still contains tempfile.mkstemp — delegate to "
        f"atomic_write_json instead (arch note #2)"
    )


# ── End-to-end smoke: helpers actually wire up in a real module ──────────────

def test_discord_guard_save_uses_helper(tmp_path, monkeypatch):
    """Re-point GUARD_FILE at a tmp path and verify the save path uses the
    helper end-to-end (produces a valid JSON file, no leftover .tmp)."""
    import discord_guard
    guard_path = tmp_path / "discord_posted.json"
    lock_path = str(guard_path) + ".lock"
    monkeypatch.setattr(discord_guard, "GUARD_FILE", guard_path)
    monkeypatch.setattr(discord_guard, "LOCK_FILE", lock_path)
    discord_guard.save_guard({"post:2026-04-21:test": "hit"})
    assert guard_path.is_file()
    data = json.loads(guard_path.read_text(encoding="utf-8"))
    assert data == {"post:2026-04-21:test": "hit"}
    assert not list(tmp_path.glob("*.tmp"))


def test_save_checkpoint_uses_helper(tmp_path, monkeypatch):
    import capture_clv
    target = tmp_path / "clv_checkpoint.json"
    monkeypatch.setattr(capture_clv, "CHECKPOINT_PATH", target)
    capture_clv.save_checkpoint("2026-04-21", {"game-a", "game-b"})
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["date"] == "2026-04-21"
    assert sorted(data["captured_games"]) == ["game-a", "game-b"]
    assert not list(tmp_path.glob("*.tmp"))


# ── Root-mirror sync contract ────────────────────────────────────────────────

# L16 (Apr 30 2026): root files are runpy shims — intentionally differ from engine/.
# test_tail_guard.py guards shim validity. Byte-identical sync removed (H1/H2, May 1 2026).
