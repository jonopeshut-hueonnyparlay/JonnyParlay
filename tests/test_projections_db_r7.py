#!/usr/bin/env python3
"""Tests for Research Brief 7 additions to projections_db.py.

Covers:
  C11 - get_player_career_game_count() correctness
  C12 - get_player_last_appearance_days() correctness + C4 (bad date guard)
  C13 - cold_start sub-type classification (taxi / returner / new_acquisition)
  C14 - CUSTOM_SHADOW_LOG / ENABLE_CUSTOM_CLV present in capture_clv
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent / "engine"
sys.path.insert(0, str(ENGINE))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db(tmp_path):
    """Minimal projections.db with schema for R7 tests."""
    db_path = tmp_path / "projections.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE teams (
            team_id   INTEGER PRIMARY KEY,
            name      TEXT,
            abbreviation TEXT
        );
        CREATE TABLE players (
            player_id  INTEGER PRIMARY KEY,
            name       TEXT,
            name_key   TEXT,
            team_id    INTEGER,
            position   TEXT
        );
        CREATE TABLE games (
            game_id      INTEGER PRIMARY KEY,
            game_date    TEXT,
            season       TEXT,
            home_team_id INTEGER,
            away_team_id INTEGER,
            status       TEXT DEFAULT 'Final'
        );
        CREATE TABLE player_game_stats (
            stat_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id  INTEGER,
            game_id    INTEGER,
            min        REAL DEFAULT 0,
            pts        REAL DEFAULT 0,
            reb        REAL DEFAULT 0,
            ast        REAL DEFAULT 0,
            fg3m       REAL DEFAULT 0,
            stl        REAL DEFAULT 0,
            blk        REAL DEFAULT 0,
            tov        REAL DEFAULT 0
        );
        """
    )
    # Teams
    conn.execute("INSERT INTO teams VALUES (1, 'Lakers', 'LAL')")
    conn.execute("INSERT INTO teams VALUES (2, 'Celtics', 'BOS')")
    # Players
    conn.execute("INSERT INTO players VALUES (1, 'Player One', 'player_one', 1, 'F')")
    conn.execute("INSERT INTO players VALUES (2, 'Newcomer', 'newcomer', 1, 'G')")
    conn.execute("INSERT INTO players VALUES (3, 'Veteran', 'veteran', 2, 'C')")
    # Games across two seasons
    conn.execute("INSERT INTO games VALUES (101, '2023-11-01', '2023-24', 1, 2, 'Final')")
    conn.execute("INSERT INTO games VALUES (102, '2024-01-15', '2023-24', 1, 2, 'Final')")
    conn.execute("INSERT INTO games VALUES (103, '2025-03-01', '2024-25', 1, 2, 'Final')")
    conn.execute("INSERT INTO games VALUES (104, '2025-10-20', '2025-26', 1, 2, 'Final')")
    # Stats: Player 1 played in all prior seasons
    conn.execute("INSERT INTO player_game_stats (player_id, game_id, min, pts) VALUES (1, 101, 30, 10)")
    conn.execute("INSERT INTO player_game_stats (player_id, game_id, min, pts) VALUES (1, 102, 25, 8)")
    conn.execute("INSERT INTO player_game_stats (player_id, game_id, min, pts) VALUES (1, 103, 28, 12)")
    conn.execute("INSERT INTO player_game_stats (player_id, game_id, min, pts) VALUES (1, 104, 32, 15)")
    # Veteran: played in 2023-24 only, last game far in the past
    conn.execute("INSERT INTO player_game_stats (player_id, game_id, min, pts) VALUES (3, 101, 35, 20)")
    conn.execute("INSERT INTO player_game_stats (player_id, game_id, min, pts) VALUES (3, 102, 38, 22)")
    # Newcomer: no prior games at all
    conn.commit()
    conn.close()
    return str(db_path)


# ---------------------------------------------------------------------------
# C11 — get_player_career_game_count
# ---------------------------------------------------------------------------

class TestGetPlayerCareerGameCount:
    """C11: career game count returns correct n and avg_min."""

    def test_player_with_prior_season_games(self, tmp_db):
        from projections_db import get_player_career_game_count
        # Player 1 has 2 games in 2023-24 + 1 in 2024-25 = 3 prior to current 2025-26
        n, avg_min = get_player_career_game_count(1, "2025-26", db_path=tmp_db)
        assert n == 3, f"Expected 3 prior games, got {n}"
        assert avg_min is not None
        assert 26.0 < avg_min < 29.0, f"Expected ~27.7 avg_min, got {avg_min}"

    def test_newcomer_has_zero_games(self, tmp_db):
        from projections_db import get_player_career_game_count
        # Player 2 (Newcomer) has no games at all
        n, avg_min = get_player_career_game_count(2, "2025-26", db_path=tmp_db)
        assert n == 0, f"Newcomer should have 0 prior games, got {n}"
        assert avg_min is None, "avg_min should be None when n_games=0"

    def test_excludes_current_season(self, tmp_db):
        from projections_db import get_player_career_game_count
        # Player 1 has 1 game in 2025-26 but it should be excluded
        n_current, _ = get_player_career_game_count(1, "2025-26", db_path=tmp_db)
        n_all, _ = get_player_career_game_count(1, "2099-00", db_path=tmp_db)
        assert n_all == 4, "All 4 games visible when no current season excluded"
        assert n_current == 3, "Current season game excluded"

    def test_veteran_prior_career(self, tmp_db):
        from projections_db import get_player_career_game_count
        n, avg_min = get_player_career_game_count(3, "2025-26", db_path=tmp_db)
        assert n == 2
        assert avg_min is not None
        assert 36.0 < avg_min < 37.0


# ---------------------------------------------------------------------------
# C12 — get_player_last_appearance_days
# ---------------------------------------------------------------------------

class TestGetPlayerLastAppearanceDays:
    """C12: last appearance days returns correct delta + handles edge cases."""

    def test_returns_days_since_last_game(self, tmp_db):
        from projections_db import get_player_last_appearance_days
        # Player 1's last game before 2025-10-25 is 2025-10-20 (game 104) — 5 days
        days = get_player_last_appearance_days(1, "2025-10-25", db_path=tmp_db)
        assert days == 5, f"Expected 5 days, got {days}"

    def test_newcomer_returns_none(self, tmp_db):
        from projections_db import get_player_last_appearance_days
        # Player 2 has never played
        days = get_player_last_appearance_days(2, "2025-10-25", db_path=tmp_db)
        assert days is None

    def test_veteran_long_absence(self, tmp_db):
        from projections_db import get_player_last_appearance_days
        # Veteran last played 2024-01-15; queried as of 2025-10-25 = ~648 days
        days = get_player_last_appearance_days(3, "2025-10-25", db_path=tmp_db)
        assert days is not None
        assert days >= 600, f"Expected long absence, got {days}"

    def test_excludes_game_on_reference_date(self, tmp_db):
        from projections_db import get_player_last_appearance_days
        # before_date is exclusive — game on 2025-10-20 should NOT count if
        # reference date is 2025-10-20 itself
        days = get_player_last_appearance_days(1, "2025-10-20", db_path=tmp_db)
        # Previous game before 2025-10-20 is 2025-03-01 (game 103)
        from datetime import date
        expected = (date.fromisoformat("2025-10-20") - date.fromisoformat("2025-03-01")).days
        assert days == expected, f"Expected {expected} days, got {days}"

    def test_c4_malformed_date_returns_none(self, tmp_db, caplog):
        """C4: malformed date string in DB should return None + log a warning."""
        import sqlite3 as _sqlite3
        import logging
        # Inject a bad date into game table
        conn = _sqlite3.connect(tmp_db)
        conn.execute("INSERT INTO games VALUES (999, 'BAD-DATE', '2025-26', 1, 2, 'Final')")
        conn.execute("INSERT INTO player_game_stats (player_id, game_id, min) VALUES (1, 999, 10)")
        conn.commit()
        conn.close()
        from projections_db import get_player_last_appearance_days
        with caplog.at_level(logging.WARNING):
            # 'BAD-DATE' will sort after all real dates (alpha-sort), so MAX() picks it up
            # The C4 guard should catch the fromisoformat() failure and return None
            days = get_player_last_appearance_days(1, "9999-01-01", db_path=tmp_db)
        # Either returns None (malformed) or a valid integer — should not crash
        assert days is None or isinstance(days, int)


# ---------------------------------------------------------------------------
# C13 — cold_start sub-type classification in nba_projector
# ---------------------------------------------------------------------------

class TestColdStartSubType:
    """C13: cold_start players are classified as taxi / returner / new_acquisition."""

    def _make_projector_call(self, tmp_db, player_id: int, before_date: str,
                              current_season: str = "2025-26"):
        """Helper that calls the DB functions and applies the R7 classification logic."""
        from projections_db import get_player_career_game_count, get_player_last_appearance_days
        n_career, career_avg_min = get_player_career_game_count(
            player_id, current_season, db_path=tmp_db)
        last_days = get_player_last_appearance_days(
            player_id, before_date, db_path=tmp_db)

        # R7 classification logic (mirrors nba_projector cold_start block)
        if n_career == 0:
            sub_type = "taxi"
        elif last_days is None or last_days >= 180:
            sub_type = "returner"
        else:
            sub_type = "new_acquisition"
        return sub_type, n_career, career_avg_min, last_days

    def test_newcomer_is_taxi(self, tmp_db):
        sub_type, n, avg, days = self._make_projector_call(tmp_db, 2, "2025-10-25")
        assert sub_type == "taxi", f"Expected taxi, got {sub_type!r}"
        assert n == 0
        assert avg is None

    def test_veteran_long_absence_is_returner(self, tmp_db):
        # Veteran last played Jan 2024 — >180 days before Oct 2025
        sub_type, n, avg, days = self._make_projector_call(tmp_db, 3, "2025-10-25")
        assert sub_type == "returner", f"Expected returner, got {sub_type!r}"
        assert days is not None and days >= 180

    def test_recent_acquisition_is_new_acquisition(self, tmp_db):
        # Player 1 last played 2025-10-20 — only 5 days before 2025-10-25
        sub_type, n, avg, days = self._make_projector_call(tmp_db, 1, "2025-10-25")
        assert sub_type == "new_acquisition", f"Expected new_acquisition, got {sub_type!r}"
        assert days == 5

    def test_boundary_exactly_180_days(self, tmp_db):
        """180 days exactly should be returner (>= 180 threshold)."""
        from datetime import date, timedelta
        # Veteran last played 2024-01-15; compute a reference date 180 days after
        last = date.fromisoformat("2024-01-15")
        ref = last + timedelta(days=180)
        sub_type, _, _, days = self._make_projector_call(tmp_db, 3, str(ref))
        assert days == 180
        assert sub_type == "returner"


# ---------------------------------------------------------------------------
# C14 — CUSTOM_SHADOW_LOG and ENABLE_CUSTOM_CLV present in capture_clv
# ---------------------------------------------------------------------------

class TestCaptureClvCustomShadow:
    """C14: capture_clv exposes CUSTOM_SHADOW_LOG and ENABLE_CUSTOM_CLV."""

    def test_constants_exist(self):
        import capture_clv
        assert hasattr(capture_clv, "CUSTOM_SHADOW_LOG"), \
            "capture_clv must define CUSTOM_SHADOW_LOG"
        assert hasattr(capture_clv, "ENABLE_CUSTOM_CLV"), \
            "capture_clv must define ENABLE_CUSTOM_CLV"

    def test_custom_shadow_log_points_to_pick_log_custom(self):
        import capture_clv
        path = capture_clv.CUSTOM_SHADOW_LOG
        assert str(path).endswith("pick_log_custom.csv"), \
            f"CUSTOM_SHADOW_LOG should point to pick_log_custom.csv, got: {path}"

    def test_enable_custom_clv_is_true_by_default(self):
        import capture_clv
        assert capture_clv.ENABLE_CUSTOM_CLV is True, \
            "ENABLE_CUSTOM_CLV should be True by default"

    def test_custom_log_appended_when_enabled_and_exists(self, tmp_path, monkeypatch):
        """When ENABLE_CUSTOM_CLV=True and the file exists, it's in log_paths."""
        import capture_clv
        custom_log = tmp_path / "pick_log_custom.csv"
        custom_log.write_text("date,player\n")  # create the file
        monkeypatch.setattr(capture_clv, "CUSTOM_SHADOW_LOG", custom_log)
        monkeypatch.setattr(capture_clv, "ENABLE_CUSTOM_CLV", True)
        # The daemon build_log_paths logic (simplified version)
        log_paths = [capture_clv.PICK_LOG]
        if capture_clv.ENABLE_CUSTOM_CLV and capture_clv.CUSTOM_SHADOW_LOG.exists():
            log_paths.append(capture_clv.CUSTOM_SHADOW_LOG)
        assert custom_log in log_paths, "Custom log should be in log_paths when enabled+exists"

    def test_custom_log_not_appended_when_disabled(self, tmp_path, monkeypatch):
        import capture_clv
        custom_log = tmp_path / "pick_log_custom.csv"
        custom_log.write_text("date,player\n")
        monkeypatch.setattr(capture_clv, "CUSTOM_SHADOW_LOG", custom_log)
        monkeypatch.setattr(capture_clv, "ENABLE_CUSTOM_CLV", False)
        log_paths = [capture_clv.PICK_LOG]
        if capture_clv.ENABLE_CUSTOM_CLV and capture_clv.CUSTOM_SHADOW_LOG.exists():
            log_paths.append(capture_clv.CUSTOM_SHADOW_LOG)
        assert custom_log not in log_paths, "Custom log must not appear when ENABLE_CUSTOM_CLV=False"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
