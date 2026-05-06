#!/usr/bin/env python3
"""Regression tests for audit M-7 — results_graphic font configurability.

Before this fix, _load_fonts() hardcoded a handful of Windows/Mac/Linux
paths and silently fell back to Pillow's tiny bitmap default when none
resolved. Fresh Windows installs and containerized runs would post
unreadable PNGs to Discord with no diagnostic.

These tests lock in:
  - JONNYPARLAY_FONTS env var (file OR directory) takes highest priority
  - Repo-local fonts/ directory is consulted before system fallbacks
  - System fallbacks work when env + fonts/ are empty
  - Pillow's bitmap default is used ONLY when nothing else resolves,
    and the fallback emits a loud one-time stderr warning
  - get_font_report() surfaces which path was chosen per slot
"""

from __future__ import annotations

import importlib
import io
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "engine"))

# Skip the whole file if Pillow isn't installed — results_graphic is a soft dep.
pytest.importorskip("PIL")


@pytest.fixture
def fresh_rg(monkeypatch):
    """Reload results_graphic with a clean env + repo-fonts stub.

    Every test gets its own module so the module-level _FONT_REPORT and
    _FALLBACK_WARNED state don't leak between cases.
    """
    # Scrub the env var so tests are deterministic.
    monkeypatch.delenv("JONNYPARLAY_FONTS", raising=False)
    import results_graphic as rg
    importlib.reload(rg)
    # Isolate from the real repo fonts/ dir (if anyone drops one in later,
    # these tests should still describe the CONTRACT, not the current state).
    rg._repo_font_dir_paths = lambda: []
    rg._FALLBACK_WARNED = False
    rg._FONT_REPORT.clear()
    return rg


def _find_any_system_truetype() -> str | None:
    """Return some truetype we can use as a canonical 'this file exists' probe."""
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/arial.ttf",
    ):
        if Path(p).exists():
            return p
    return None


# ─────────────────────────────────────────────────────────────────
# Env-var + dir expansion
# ─────────────────────────────────────────────────────────────────

def test_expand_env_paths_empty(fresh_rg):
    assert fresh_rg._expand_env_paths(None) == []
    assert fresh_rg._expand_env_paths("") == []
    assert fresh_rg._expand_env_paths("   ") == []


def test_expand_env_paths_single_file(fresh_rg, tmp_path):
    f = tmp_path / "brand.ttf"
    f.write_bytes(b"not-a-real-font")   # existence is all expand cares about
    paths = fresh_rg._expand_env_paths(str(f))
    assert paths == [str(f)]


def test_expand_env_paths_directory_returns_sorted_truetype_files(fresh_rg, tmp_path):
    (tmp_path / "z.ttf").write_bytes(b"")
    (tmp_path / "a.otf").write_bytes(b"")
    (tmp_path / "b.ttc").write_bytes(b"")
    (tmp_path / "ignored.txt").write_bytes(b"")
    paths = fresh_rg._expand_env_paths(str(tmp_path))
    # Sorted alphabetically — caller controls priority by naming.
    assert paths == [
        str(tmp_path / "a.otf"),
        str(tmp_path / "b.ttc"),
        str(tmp_path / "z.ttf"),
    ]
    # Non-font files dropped.
    assert not any("ignored.txt" in p for p in paths)


def test_expand_env_paths_splits_on_pathsep(fresh_rg, tmp_path):
    a = tmp_path / "a.ttf"; a.write_bytes(b"")
    b = tmp_path / "b.ttf"; b.write_bytes(b"")
    combined = f"{a}{os.pathsep}{b}"
    assert fresh_rg._expand_env_paths(combined) == [str(a), str(b)]


# ─────────────────────────────────────────────────────────────────
# Search chain priority
# ─────────────────────────────────────────────────────────────────

def test_env_var_wins_over_system_fallbacks(fresh_rg, monkeypatch):
    ttf = _find_any_system_truetype()
    if ttf is None:
        pytest.skip("no system truetype available on this host")
    monkeypatch.setenv("JONNYPARLAY_FONTS", ttf)
    chain = fresh_rg._build_search_chain("bold")
    # Env var entry must appear before any system-fallback entry.
    # Compare via Path to handle OS separator differences (/ vs \\ on Windows).
    assert Path(chain[0]) == Path(ttf)


def test_repo_fonts_dir_wins_over_system(fresh_rg, tmp_path, monkeypatch):
    # Pretend the repo has a fonts/ dir with a brand font.
    repo_font = tmp_path / "brand-bold.ttf"
    repo_font.write_bytes(b"")
    monkeypatch.setattr(fresh_rg, "_repo_font_dir_paths", lambda: [str(repo_font)])
    chain = fresh_rg._build_search_chain("bold")
    # No env var set; repo font still precedes system fallbacks.
    env_idx  = -1  # no env entry expected
    repo_idx = chain.index(str(repo_font))
    sys_candidates = [p for p in chain if p.startswith(("C:/", "/usr/", "/System/"))]
    if sys_candidates:
        sys_idx = chain.index(sys_candidates[0])
        assert repo_idx < sys_idx


def test_system_fallbacks_used_when_env_and_repo_empty(fresh_rg, monkeypatch):
    # Env + repo both empty → first entry is a system fallback constant.
    chain = fresh_rg._build_search_chain("bold")
    assert chain[0] in fresh_rg._SYSTEM_BOLD_FALLBACKS


# ─────────────────────────────────────────────────────────────────
# Full _load_fonts behavior + get_font_report
# ─────────────────────────────────────────────────────────────────

def test_load_fonts_reports_path_for_each_slot(fresh_rg):
    fresh_rg._load_fonts()
    report = fresh_rg.get_font_report()
    expected_slots = {"title", "stats", "tier_badge", "pick_text",
                      "pick_bold", "pl_text", "footer"}
    assert set(report.keys()) == expected_slots
    for slot, info in report.items():
        assert "path" in info and "family" in info and "size" in info
        assert info["family"] in ("bold", "regular")


def test_load_fonts_with_real_system_font_records_path(fresh_rg):
    ttf = _find_any_system_truetype()
    if ttf is None:
        pytest.skip("no system truetype available on this host")
    fresh_rg._load_fonts()
    report = fresh_rg.get_font_report()
    # At least some slots should have resolved a real path (not None).
    chosen_paths = {info["path"] for info in report.values()}
    assert any(p is not None for p in chosen_paths)


def test_load_fonts_emits_warning_and_path_none_on_full_fallback(fresh_rg, monkeypatch):
    # Simulate a host with no truetype fonts anywhere.
    monkeypatch.setattr(fresh_rg, "_SYSTEM_BOLD_FALLBACKS", ())
    monkeypatch.setattr(fresh_rg, "_SYSTEM_REG_FALLBACKS", ())
    monkeypatch.delenv("JONNYPARLAY_FONTS", raising=False)
    monkeypatch.setattr(fresh_rg, "_repo_font_dir_paths", lambda: [])

    # Capture stderr
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)

    fresh_rg._load_fonts()

    report = fresh_rg.get_font_report()
    # Every slot must fall back — path is None, which is the diagnostic signal.
    assert all(info["path"] is None for info in report.values())

    warning = buf.getvalue()
    assert "No truetype font found" in warning
    assert "JONNYPARLAY_FONTS" in warning
    # Must mention the repo-level escape hatch.
    assert "fonts/" in warning


def test_fallback_warning_fires_only_once_per_process(fresh_rg, monkeypatch):
    """Loud warning is good; a 1000-line stderr spam in grade_picks is not."""
    monkeypatch.setattr(fresh_rg, "_SYSTEM_BOLD_FALLBACKS", ())
    monkeypatch.setattr(fresh_rg, "_SYSTEM_REG_FALLBACKS", ())
    monkeypatch.delenv("JONNYPARLAY_FONTS", raising=False)
    monkeypatch.setattr(fresh_rg, "_repo_font_dir_paths", lambda: [])

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)

    fresh_rg._load_fonts()
    fresh_rg._load_fonts()
    fresh_rg._load_fonts()

    warnings = buf.getvalue().count("No truetype font found")
    assert warnings == 1, f"expected 1 warning, got {warnings}"


def test_get_font_report_is_a_safe_copy(fresh_rg):
    """Mutating the returned report must NOT corrupt internal state."""
    fresh_rg._load_fonts()
    r1 = fresh_rg.get_font_report()
    r1["title"]["path"] = "/mutated"
    r1.clear()
    r2 = fresh_rg.get_font_report()
    assert "title" in r2
    assert r2["title"]["path"] != "/mutated"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
