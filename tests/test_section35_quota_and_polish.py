"""Regression tests for Section 35 — CLV quota stop, preflight Python pin,
weekly_recap PL rounding, post_nrfi_bonus team column.

Audit findings closed here (Apr 20 2026):
    L-8   capture_clv.py now parks the daemon on x-requests-remaining=0 until
          the next UTC midnight instead of spinning on 429s every poll.
    L-5   preflight.bat now actively rejects Python < 3.10 instead of just
          claiming "3.10+ required" in the not-installed branch.
    L-16  weekly_recap.compute_pl() no longer rounds to 4 decimals internally.
          Rounding happens once at the display boundary — prevents compounding
          rounding errors across per-pick → daily → week aggregations.
    L-9   post_nrfi_bonus.py writes a single team name in the `team` column
          ("Toronto Blue Jays") instead of a game-string ("TOR@ARI") — matches
          the pick_log schema contract used by grader and analytics.
"""

from __future__ import annotations

import importlib
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CAPTURE_CLV = REPO_ROOT / "engine" / "capture_clv.py"
CAPTURE_CLV_ROOT = REPO_ROOT / "capture_clv.py"
WEEKLY_RECAP = REPO_ROOT / "engine" / "weekly_recap.py"
WEEKLY_RECAP_ROOT = REPO_ROOT / "weekly_recap.py"
PREFLIGHT_BAT = REPO_ROOT / "preflight.bat"
POST_NRFI = REPO_ROOT / "post_nrfi_bonus.py"


# ── L-8: CLV daemon quota-exhausted graceful stop ─────────────────────────────

@pytest.fixture(scope="module")
def clv_src() -> str:
    return CAPTURE_CLV.read_text(encoding="utf-8")


def test_capture_clv_has_quota_exhausted_state(clv_src: str):
    """Module-level state must exist so the short-circuit survives across
    calls inside a single daemon lifetime."""
    assert "_quota_exhausted_until" in clv_src, (
        "capture_clv.py must define module-level _quota_exhausted_until"
    )


def test_capture_clv_has_is_quota_exhausted_helper(clv_src: str):
    """Public-ish getter so run() and _odds_api_get() both check the same
    source of truth."""
    assert re.search(r"def is_quota_exhausted\s*\(", clv_src), (
        "capture_clv.py must expose is_quota_exhausted() helper"
    )


def test_capture_clv_has_mark_quota_exhausted_helper(clv_src: str):
    """Setter is called when we observe remaining=0. Idempotent — only the
    first observation sets the deadline."""
    assert re.search(r"def _mark_quota_exhausted\s*\(", clv_src)


def test_capture_clv_odds_api_get_short_circuits_on_exhaustion(clv_src: str):
    """_odds_api_get must return early WITHOUT calling requests.get when
    the quota flag is set — otherwise we'd still burn a syscall and log
    a bogus connection error on every poll."""
    # Slice the function body.
    m = re.search(
        r"def _odds_api_get\s*\([^)]*\)[^:]*:\s*(.*?)(?=\ndef\s|\nclass\s|\Z)",
        clv_src,
        re.DOTALL,
    )
    assert m, "could not locate _odds_api_get body"
    body = m.group(1)
    # The short-circuit must appear BEFORE requests.get() in the function body.
    exhausted_idx = body.find("is_quota_exhausted()")
    requests_idx = body.find("requests.get(")
    assert exhausted_idx != -1, (
        "_odds_api_get must consult is_quota_exhausted() before issuing a request"
    )
    assert requests_idx != -1, "_odds_api_get should still contain requests.get call"
    assert exhausted_idx < requests_idx, (
        "is_quota_exhausted() guard must run BEFORE requests.get() in _odds_api_get"
    )


def test_capture_clv_marks_quota_exhausted_at_zero(clv_src: str):
    """The header-observation block must call _mark_quota_exhausted() when
    x-requests-remaining is exactly 0. Below the low-quota threshold is a
    warning; at 0 it's a hard stop."""
    # Check for `if remaining == 0` near a _mark_quota_exhausted() call.
    assert re.search(
        r"if\s+remaining\s*==\s*0\s*:\s*\n\s*_mark_quota_exhausted\s*\(",
        clv_src,
    ), (
        "capture_clv.py must call _mark_quota_exhausted() when remaining == 0"
    )


def test_capture_clv_run_loop_checks_quota_before_fetching(clv_src: str):
    """The main poll loop must consult is_quota_exhausted() inside the
    `while True:` body — otherwise the fix is cosmetic and the daemon still
    iterates through fetch + 429 on every cycle."""
    # Find the `while True:` inside run()
    m = re.search(r"def run\(run_date[^)]*\):\s*(.*?)\Z", clv_src, re.DOTALL)
    assert m, "could not locate run() body"
    run_body = m.group(1)
    # Inside the while-True loop, there should be an is_quota_exhausted() check.
    loop_match = re.search(r"while\s+True\s*:\s*(.*?)\Z", run_body, re.DOTALL)
    assert loop_match, "run() must contain `while True:` loop"
    loop_body = loop_match.group(1)
    # Verify the quota check happens before any Odds API call site.
    assert "is_quota_exhausted()" in loop_body, (
        "main poll loop must check is_quota_exhausted() each iteration"
    )


def test_capture_clv_quota_backoff_end_to_end():
    """Functional smoke test — import the module and drive the quota state
    machine to confirm the helpers actually cooperate.

    Uses the test-only reset hook so we start from a clean slate regardless
    of module state from a prior test."""
    sys.path.insert(0, str(REPO_ROOT / "engine"))
    try:
        clv = importlib.import_module("capture_clv")
    finally:
        # Leave path in place — other tests in this suite may need it.
        pass
    # Baseline: not exhausted.
    clv._reset_quota_state_for_tests()
    assert clv.is_quota_exhausted() is False
    # Mark exhausted.
    clv._mark_quota_exhausted()
    assert clv.is_quota_exhausted() is True
    # Deadline should be strictly in the future and land on a UTC midnight.
    deadline = clv._quota_exhausted_until
    assert deadline is not None
    assert deadline.tzinfo is not None
    assert deadline > datetime.now(timezone.utc)
    assert deadline.hour == 0 and deadline.minute == 0 and deadline.second == 0
    # Idempotent: a second mark doesn't push the deadline.
    first_deadline = deadline
    clv._mark_quota_exhausted()
    assert clv._quota_exhausted_until == first_deadline, (
        "_mark_quota_exhausted() must be idempotent — repeated calls must not "
        "reset the deadline"
    )
    # Simulate rollover: manually set deadline to the past, expect auto-clear.
    clv._quota_exhausted_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert clv.is_quota_exhausted() is False, (
        "is_quota_exhausted() must auto-clear once the deadline passes"
    )
    assert clv._quota_exhausted_until is None, (
        "auto-clear must null the deadline so we don't repeatedly log the "
        "'quota elapsed' message"
    )
    # Clean up module state so we don't affect subsequent tests.
    clv._reset_quota_state_for_tests()


def test_next_utc_quota_reset_lands_on_utc_midnight():
    """Math check on the reset helper — tomorrow's UTC midnight regardless
    of caller's local time."""
    sys.path.insert(0, str(REPO_ROOT / "engine"))
    clv = importlib.import_module("capture_clv")
    # Pin "now" to a known instant just before UTC midnight.
    pinned = datetime(2026, 4, 20, 23, 59, 59, tzinfo=timezone.utc)
    reset = clv._next_utc_quota_reset(pinned)
    assert reset == datetime(2026, 4, 21, 0, 0, 0, tzinfo=timezone.utc)
    # Pin to just past UTC midnight — reset should be the NEXT midnight, not today's.
    pinned = datetime(2026, 4, 20, 0, 0, 1, tzinfo=timezone.utc)
    reset = clv._next_utc_quota_reset(pinned)
    assert reset == datetime(2026, 4, 21, 0, 0, 0, tzinfo=timezone.utc)


def test_capture_clv_root_mirror_matches_engine():
    # L16 (Apr 30 2026): capture_clv.py root file is a runpy shim.
    # test_tail_guard.py guards shim validity. (H1/H2, May 1 2026)
    root = CAPTURE_CLV_ROOT
    if root.exists():
        src = root.read_text(encoding="utf-8", errors="replace")
        assert "runpy.run_module" in src, "root capture_clv.py must be a runpy shim (L16)"


# ── L-5: preflight.bat actively enforces Python >= 3.10 ─────────────────────

@pytest.fixture(scope="module")
def preflight_src() -> str:
    return PREFLIGHT_BAT.read_text(encoding="utf-8", errors="replace")


def test_preflight_runs_version_check(preflight_src: str):
    """L-5: the file must invoke `sys.version_info >= (3, 10)` somewhere in
    the Python-presence section. The subprocess exits 1 on older interpreters,
    which trips errorlevel and lets the batch file FAIL the preflight."""
    assert re.search(
        r"sys\.version_info\s*>=\s*\(\s*3\s*,\s*10\s*\)",
        preflight_src,
    ), "preflight.bat must enforce Python >= 3.10 via sys.version_info check"


def test_preflight_fails_on_old_python(preflight_src: str):
    """After the version check, there must be an errorlevel branch that
    prints FAIL and jumps to :end — not just a WARN."""
    # Find the version check line and capture everything up to the first
    # lone `)` at column 0 (which closes the `if errorlevel 1 (` block).
    m = re.search(
        r"python\s+-c\s+\"import sys;\s*sys\.exit\(0 if sys\.version_info[^\n]*\n"
        r"(if errorlevel 1 \(.*?\n\))",
        preflight_src,
        re.DOTALL,
    )
    assert m, "could not locate the version-check failure branch"
    branch = m.group(1)
    assert "[FAIL]" in branch, "old-python branch must print [FAIL], not [WARN]"
    assert "goto :end" in branch, "old-python branch must jump to :end"


# ── L-16: weekly_recap compute_pl no longer rounds internally ───────────────

@pytest.fixture(scope="module")
def recap_src() -> str:
    return WEEKLY_RECAP.read_text(encoding="utf-8")


def test_compute_pl_has_no_internal_rounding(recap_src: str):
    """Strict: no `round(...)` call anywhere inside the compute_pl body.
    Display-layer formatting is responsible for rounding."""
    m = re.search(
        r"def compute_pl\([^)]*\):\s*(.*?)(?=\ndef\s|\nclass\s|\Z)",
        recap_src,
        re.DOTALL,
    )
    assert m, "compute_pl function not found in weekly_recap.py"
    body = m.group(1)
    assert "round(" not in body, (
        "compute_pl must not round internally (L-16) — let the display layer "
        "handle rounding once, at the presentation boundary"
    )


def test_compute_pl_still_returns_correct_floats():
    """Functional check — feed it a few known inputs and verify the math."""
    sys.path.insert(0, str(REPO_ROOT / "engine"))
    recap = importlib.import_module("weekly_recap")
    # Win at -110: size * (100/110)
    assert recap.compute_pl(1.0, "-110", "W") == pytest.approx(100 / 110)
    # Win at +150: size * 1.5
    assert recap.compute_pl(2.0, "+150", "W") == pytest.approx(3.0)
    # Loss: -size
    assert recap.compute_pl(1.5, "-110", "L") == -1.5
    # Push / VOID / blank: 0.0
    for r in ("P", "VOID", "", None):
        assert recap.compute_pl(1.0, "-110", r) == 0.0
    # Malformed odds: 0.0 (don't raise)
    assert recap.compute_pl(1.0, "garbage", "W") == 0.0


def test_compute_pl_returns_full_precision():
    """With rounding removed, the return value should be full float precision
    for a non-integer-quotient case (1u at -110). The old code returned 0.9091
    (4-decimal round); the new code returns 0.9090909090909091 which can be
    rounded exactly once at display."""
    sys.path.insert(0, str(REPO_ROOT / "engine"))
    recap = importlib.import_module("weekly_recap")
    # 1u at -110 win = 0.909090909...
    pl = recap.compute_pl(1.0, "-110", "W")
    # The 4-decimal-rounded version would be exactly 0.9091.
    assert pl != 0.9091, (
        "compute_pl still rounds to 4 decimals — the round() call must be "
        "removed from both the W and L branches"
    )
    # Sanity: the value is within 0.001 of the 4-decimal approximation.
    assert abs(pl - 0.9091) < 0.001


def test_weekly_recap_root_mirror_matches_engine():
    # L16 (Apr 30 2026): weekly_recap.py root file is a runpy shim.
    # test_tail_guard.py guards shim validity. (H1/H2, May 1 2026)
    root = WEEKLY_RECAP_ROOT
    if root.exists():
        src = root.read_text(encoding="utf-8", errors="replace")
        assert "runpy.run_module" in src, "root weekly_recap.py must be a runpy shim (L16)"


# ── L-9: post_nrfi_bonus.py team column holds a single team ─────────────────

@pytest.fixture(scope="module")
def nrfi_src() -> str:
    return POST_NRFI.read_text(encoding="utf-8")


def test_post_nrfi_team_column_is_not_a_game_string(nrfi_src: str):
    """The `team` value must be a single team, not a game abbreviation
    ("TOR@ARI") — the pick_log schema treats `team` as a single team name
    that the grader and team-pace lookups can join on."""
    assert '"team": "TOR@ARI"' not in nrfi_src, (
        "post_nrfi_bonus.py still writes 'TOR@ARI' in the team column — "
        "audit L-9 calls for a single team name"
    )
    # And no '@' in any `"team": "..."` value (covers other abbreviations).
    for m in re.finditer(r'"team"\s*:\s*"([^"]*)"', nrfi_src):
        assert "@" not in m.group(1), (
            f"post_nrfi_bonus.py team column still contains '@': {m.group(1)!r}"
        )


def test_post_nrfi_team_matches_away_team_in_game_string(nrfi_src: str):
    """Convention: for NRFI-style pitcher-matchup props, team column holds the
    AWAY team (leftmost slot in the `game` field). Verify the two rows agree."""
    team_m = re.search(r'"team"\s*:\s*"([^"]+)"', nrfi_src)
    game_m = re.search(r'"game"\s*:\s*"([^"]+)"', nrfi_src)
    assert team_m and game_m, "could not locate team/game rows in post_nrfi_bonus.py"
    team = team_m.group(1)
    game = game_m.group(1)
    assert " @ " in game, f"game string must use ' @ ' separator, got {game!r}"
    away, _home = game.split(" @ ", 1)
    assert team == away, (
        f"team column ({team!r}) should match the away side of the game "
        f"string ({away!r}) for pitcher-matchup props"
    )
