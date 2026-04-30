"""Section 37 audit regression — M-26 (paths), L-3 (label dedupe), L-4
(ghost code enumeration).

Bundle summary:

* M-26: ``engine/paths.py`` is the single resolver for every data-dir
  location. Honors ``$JONNYPARLAY_ROOT``; falls back to the in-repo
  ``data/`` dir; final fallback to ``~/Documents/JonnyParlay``. ``grade_picks``
  and ``clv_report`` both source their path constants from it so a
  Cowork run needs ``export JONNYPARLAY_ROOT=...`` instead of the old
  symlink dance documented in CLAUDE.md.

* L-3: ``engine/pick_labels.py`` owns the canonical short/long label
  formatters. ``weekly_recap._pick_short_label`` and the inline
  analyze_picks "%player %dir %line %stat (sport) @ %odds" formatter
  both route through it. PARLAY short-form only had to be taught to one
  file; both now get it.

* L-4: The ghost-code sweep found zero commented-out executable Python
  in ``engine/run_picks.py``. This test re-runs that scan as a contract
  so a future edit that slips commented-out code into the file fails
  loudly instead of rotting.
"""
from __future__ import annotations

import ast
import importlib
import os
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent
ENGINE = REPO_ROOT / "engine"

# Make engine/ importable for the duration of the test module.
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))


# ── M-26: paths.py ────────────────────────────────────────────────────────────

@pytest.fixture
def fresh_paths(monkeypatch):
    """Reload paths.py with a controlled env so each test starts clean.

    Yields a callable that takes an optional override value; pass None
    to clear the env var before reload.
    """
    def _reload(override=None):
        if override is None:
            monkeypatch.delenv("JONNYPARLAY_ROOT", raising=False)
        else:
            monkeypatch.setenv("JONNYPARLAY_ROOT", str(override))
        if "paths" in sys.modules:
            return importlib.reload(sys.modules["paths"])
        return importlib.import_module("paths")

    return _reload


def test_paths_module_exists():
    """engine/paths.py is the canonical path resolver."""
    assert (ENGINE / "paths.py").is_file(), (
        "engine/paths.py must exist — it is the single resolver for every data-dir "
        "location (audit M-26)."
    )


def test_paths_env_var_override_wins(fresh_paths, tmp_path):
    """$JONNYPARLAY_ROOT is the explicit override and takes precedence."""
    paths = fresh_paths(tmp_path)
    assert paths.PROJECT_ROOT == tmp_path.resolve()
    assert paths.DATA_DIR == tmp_path.resolve() / "data"
    assert paths.PICK_LOG_PATH == tmp_path.resolve() / "data" / "pick_log.csv"


def test_paths_env_var_accepts_tilde(fresh_paths, tmp_path, monkeypatch):
    """~ is expanded so users can write $JONNYPARLAY_ROOT=~/some/path."""
    fake_home = tmp_path
    monkeypatch.setenv("HOME", str(fake_home))
    # override with a tilde-prefixed relative path
    monkeypatch.setenv("JONNYPARLAY_ROOT", "~/picksroot")
    if "paths" in sys.modules:
        paths = importlib.reload(sys.modules["paths"])
    else:
        paths = importlib.import_module("paths")
    assert paths.PROJECT_ROOT == (fake_home / "picksroot").resolve()


def test_paths_repo_fallback_used_when_env_unset(fresh_paths):
    """With no env var, paths.py picks the repo root (has data/)."""
    paths = fresh_paths(None)
    # The test tree itself is a JonnyParlay repo — data/ lives at REPO_ROOT.
    assert paths.PROJECT_ROOT == REPO_ROOT.resolve()
    assert paths.DATA_DIR == (REPO_ROOT / "data").resolve()


def test_paths_engine_does_not_shadow_root(fresh_paths):
    """Resolver must pick the repo root, not engine/, even though engine/
    contains pick_log_schema.py. Before fixing the heuristic, the
    ``pick_log_schema.py`` sentinel made engine/ win, pointing every
    path at ``engine/data/...`` which doesn't exist."""
    paths = fresh_paths(None)
    assert paths.PROJECT_ROOT.name != "engine", (
        f"paths.PROJECT_ROOT should not resolve to engine/; got {paths.PROJECT_ROOT}"
    )


def test_paths_all_canonical_constants_are_path_objects(fresh_paths):
    """Callers type-hint on Path; make sure the module hasn't regressed to str."""
    paths = fresh_paths(None)
    for name in (
        "PROJECT_ROOT", "DATA_DIR", "PICK_LOG_PATH", "PICK_LOG_MANUAL_PATH",
        "PICK_LOG_MLB_PATH", "DISCORD_GUARD_FILE", "LOG_FILE_PATH",
        "CLV_DAEMON_LOG", "CLV_DAEMON_LOCK",
    ):
        v = getattr(paths, name)
        assert isinstance(v, Path), f"paths.{name} must be a Path, got {type(v).__name__}"


def test_paths_helpers_join_correctly(fresh_paths, tmp_path):
    paths = fresh_paths(tmp_path)
    assert paths.data_path("pick_log.csv") == tmp_path.resolve() / "data" / "pick_log.csv"
    assert paths.project_path("engine", "run_picks.py") == (
        tmp_path.resolve() / "engine" / "run_picks.py"
    )


# ── M-26: grade_picks and clv_report use paths.py ─────────────────────────────

def _strip_py_comments_and_docstrings(src: str) -> str:
    """Drop docstrings and '#' comments so grep-style tests don't false-
    positive on audit notes that mention the forbidden pattern."""
    # Strip full-line triple-quoted docstrings (rough but good enough here).
    src = re.sub(r'""".*?"""', '""', src, flags=re.DOTALL)
    src = re.sub(r"'''.*?'''", "''", src, flags=re.DOTALL)
    # Strip trailing comments (preserve indentation).
    src = re.sub(r"(?m)(^|\s)#.*$", r"\1", src)
    return src


@pytest.mark.parametrize("filename", ["grade_picks.py", "clv_report.py"])
def test_consumers_import_from_paths(filename):
    """grade_picks and clv_report both source path constants from paths.py."""
    src = (ENGINE / filename).read_text(encoding="utf-8")
    assert re.search(r"^from paths import", src, re.MULTILINE), (
        f"{filename} must `from paths import ...` (audit M-26)"
    )


@pytest.mark.parametrize("filename", ["grade_picks.py", "clv_report.py"])
def test_consumers_no_longer_hardcode_documents_path(filename):
    """No executable code in these files builds paths via the historical
    ``os.path.expanduser("~/Documents/JonnyParlay/...")`` hardcode. An audit
    comment mentioning it is fine; a literal in source is not."""
    src = (ENGINE / filename).read_text(encoding="utf-8")
    code = _strip_py_comments_and_docstrings(src)
    assert 'expanduser("~/Documents/JonnyParlay/' not in code, (
        f"{filename} still has a hardcoded ~/Documents/JonnyParlay path — "
        "route it through paths.py (audit M-26)."
    )


def test_grade_picks_path_constants_still_strings():
    """grade_picks relies on os.path.basename(DISCORD_GUARD_FILE) + '.'
    string concatenation in the tempfile path. Its path constants must
    remain str, even though paths.py returns Path objects."""
    gp = importlib.import_module("grade_picks")
    for name in (
        "PICK_LOG_PATH", "PICK_LOG_MANUAL_PATH", "PICK_LOG_MLB_PATH",
        "DISCORD_GUARD_FILE", "LOG_FILE_PATH",
    ):
        v = getattr(gp, name)
        assert isinstance(v, str), (
            f"grade_picks.{name} must stay a str for string-concat compatibility; "
            f"got {type(v).__name__}"
        )


def test_clv_report_shadow_logs_point_at_paths_module():
    """clv_report.SHADOW_LOGS[MLB] must match paths.PICK_LOG_MLB_PATH."""
    paths = importlib.import_module("paths")
    # Reimport under the test env to make sure we're comparing against the
    # current resolution.
    if "clv_report" in sys.modules:
        importlib.reload(sys.modules["clv_report"])
    cr = importlib.import_module("clv_report")
    assert cr.SHADOW_LOGS["MLB"] == paths.PICK_LOG_MLB_PATH


# ── L-3: pick_labels.py ───────────────────────────────────────────────────────

def test_pick_labels_module_exists():
    assert (ENGINE / "pick_labels.py").is_file(), (
        "engine/pick_labels.py must exist — it is the canonical source for "
        "the compact and detailed pick label formats (audit L-3)."
    )


def test_pick_labels_exposes_expected_api():
    pl = importlib.import_module("pick_labels")
    for name in ("GAME_LINE_STATS", "short_label", "detail_line"):
        assert hasattr(pl, name), f"pick_labels must export {name}"


def test_game_line_stats_includes_parlay():
    """PARLAY was the original forcing function for L-3 — the prop formatter
    silently mangled daily_lay aggregate rows until the short-label logic
    learned about it. Keep the regression wired."""
    from pick_labels import GAME_LINE_STATS
    assert "PARLAY" in GAME_LINE_STATS


@pytest.mark.parametrize(
    "pick,expected",
    [
        ({"stat": "SPREAD", "player": "Mavericks", "line": "-4.5"}, "Mavericks -4.5"),
        ({"stat": "ML_FAV", "player": "Mavericks"}, "Mavericks ML"),
        ({"stat": "ML_DOG", "player": "Magic"}, "Magic ML"),
        ({"stat": "TOTAL", "direction": "over", "line": "220.5"}, "Total OVER 220.5"),
        ({"stat": "PARLAY", "player": "Daily Lay 3-leg", "odds": "+540"},
         "Daily Lay 3-leg @ +540"),
        ({"stat": "PARLAY", "player": "Daily Lay 3-leg"}, "Daily Lay 3-leg"),
        ({"stat": "3PM", "player": "Stephen Curry", "direction": "over", "line": "3.5"},
         "CURRY OVER 3.5 3PM"),
        # Degenerate: missing player → label still well-formed (no leading
        # whitespace, no double spaces).
        ({"stat": "PTS", "direction": "over", "line": "22.5"}, "OVER 22.5 PTS"),
    ],
    ids=["spread", "ml_fav", "ml_dog", "total", "parlay_with_odds",
         "parlay_without_odds", "prop_3pm", "prop_no_player"],
)
def test_short_label_shapes(pick, expected):
    from pick_labels import short_label
    assert short_label(pick) == expected


def test_detail_line_includes_all_core_fields():
    from pick_labels import detail_line
    p = {
        "player": "Luka Doncic",
        "direction": "over",
        "line": "32.5",
        "stat": "PTS",
        "sport": "NBA",
        "odds": "-110",
    }
    out = detail_line(p)
    for token in ("Luka Doncic", "over", "32.5", "PTS", "(NBA)", "-110"):
        assert token in out, f"detail_line missing {token!r}: got {out!r}"


def test_detail_line_signs_positive_odds():
    """American odds must always carry an explicit sign. This mirrors the
    pick_log normalizer's contract (audit PICK_LOG_AUDIT H-3)."""
    from pick_labels import detail_line
    out = detail_line({
        "player": "x", "direction": "o", "line": "1", "stat": "PTS",
        "sport": "NBA", "odds": "108",
    })
    assert "@ +108" in out, out


def test_weekly_recap_uses_pick_labels():
    """weekly_recap.py must source its _pick_short_label from pick_labels,
    not redefine it locally."""
    src = (ENGINE / "weekly_recap.py").read_text(encoding="utf-8")
    # The import must exist.
    assert re.search(r"from pick_labels import .*short_label", src), (
        "weekly_recap.py must import short_label from pick_labels (audit L-3)"
    )
    # No local `def _pick_short_label(` allowed — that was the original
    # duplication the audit flagged.
    assert not re.search(r"^\s*def\s+_pick_short_label\s*\(", src, re.MULTILINE), (
        "weekly_recap.py still defines _pick_short_label locally — it must "
        "come from pick_labels.py."
    )


def test_analyze_picks_uses_pick_labels():
    """analyze_picks.py must import the detail formatter instead of
    inlining the '{player} {direction} {line} {stat} ({sport}) @ {odds}'
    f-string — that inline format was the other half of the L-3 drift."""
    src = (ENGINE / "analyze_picks.py").read_text(encoding="utf-8")
    assert re.search(r"from pick_labels import .*detail_line", src), (
        "analyze_picks.py must import detail_line from pick_labels (audit L-3)"
    )
    code = _strip_py_comments_and_docstrings(src)
    # The fossil inline f-string — if it shows up in executable code, L-3
    # has regressed.
    fossil = "{p['player']} {p['direction']} {p['line']} {p['stat']}"
    assert fossil not in code, (
        "analyze_picks.py still contains the inlined label f-string; route "
        "it through pick_labels.detail_line()."
    )


# ── L-4: no ghost code in run_picks.py ────────────────────────────────────────

def _commented_python_bodies(src: str):
    """Yield (lineno, body) pairs for every single-line comment whose body
    is parseable Python AND is not obviously prose."""
    prose_tokens = (
        "e.g.", "i.e.", "audit ", "todo", "fixme", "note:", "returns ",
        "return the", "return a", " or ", " and ",
    )
    for i, line in enumerate(src.splitlines(), 1):
        s = line.rstrip()
        stripped = s.lstrip()
        if not stripped.startswith("#"):
            continue
        body = stripped[1:].lstrip()
        if not body:
            continue
        # Skip pure divider lines.
        if set(body) <= set("=-─━  "):
            continue
        # Syntactic tell: must have at least one code-shaped token.
        if not any(tok in body for tok in (
            "(", "[", "return", "def ", "import ", "class ",
            "print(", "for ", "while ",
        )):
            continue
        # Exclude natural language.
        low = body.lower()
        if any(tok in low for tok in prose_tokens):
            continue
        try:
            tree = ast.parse(body)
        except (SyntaxError, IndentationError, ValueError):
            continue
        if not tree.body:
            continue
        node = tree.body[0]
        # Bare string / number / single name literals are prose.
        if isinstance(node, ast.Expr) and isinstance(node.value, (ast.Constant, ast.Name)):
            continue
        yield i, body


def test_run_picks_has_no_commented_out_code():
    """Audit L-4: the report flagged 'commented-out ghost code' with a
    TODO to enumerate. The Apr 21 2026 sweep came up clean. This test
    keeps it clean — any new commented-out executable Python checked in
    fails the suite instead of decaying silently."""
    src = (ENGINE / "run_picks.py").read_text(encoding="utf-8")
    suspects = list(_commented_python_bodies(src))
    assert not suspects, (
        "Commented-out Python detected in engine/run_picks.py (audit L-4). "
        "Remove or convert to a proper prose comment:\n"
        + "\n".join(f"  L{i}: {body[:100]}" for i, body in suspects)
    )


# ── Root mirror sync contract (same pattern as prior sections) ───────────────

@pytest.mark.parametrize(
    "filename",
    ["paths.py", "pick_labels.py", "clv_report.py", "grade_picks.py",
     "weekly_recap.py", "analyze_picks.py"],
)
def test_root_mirror_matches_engine(filename):
    """Every touched file has a byte-identical sibling at the repo root.
    The engine ships from root on Windows (historical layout) and from
    engine/ under test; a drift between the two has caused real bugs
    in prior audit sections."""
    engine_path = ENGINE / filename
    root_path = REPO_ROOT / filename
    assert engine_path.is_file(), f"{engine_path} missing"
    assert root_path.is_file(), f"{root_path} missing (sync engine/ → root)"
    assert engine_path.read_bytes() == root_path.read_bytes(), (
        f"{filename}: engine and root copies are out of sync"
    )
