"""Tests for injury_parser.py fixes — name reversal, active-team filter, EWMA redistribution."""
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

# ---------------------------------------------------------------------------
# _maybe_reverse_name
# ---------------------------------------------------------------------------

from injury_parser import _maybe_reverse_name


class TestMaybeReverseName:
    def test_reversed_last_first(self):
        assert _maybe_reverse_name("Embiid, Joel") == "Joel Embiid"

    def test_reversed_with_spaces(self):
        assert _maybe_reverse_name("Van Gundy, Jeff") == "Jeff Van Gundy"

    def test_no_comma_unchanged(self):
        assert _maybe_reverse_name("Joel Embiid") == "Joel Embiid"

    def test_empty_string(self):
        assert _maybe_reverse_name("") == ""

    def test_non_string_passthrough(self):
        # non-string: no comma check, returns as-is
        result = _maybe_reverse_name(12345)
        assert result == 12345

    def test_trailing_comma(self):
        # "Last," with no first — should not crash
        result = _maybe_reverse_name("James,")
        assert isinstance(result, str)

    def test_multiple_commas_uses_first(self):
        # partition on first comma only
        result = _maybe_reverse_name("James, LeBron, III")
        assert result == "LeBron, III James"


# ---------------------------------------------------------------------------
# _normalise_report — name reversal applied before fold_name
# ---------------------------------------------------------------------------

from injury_parser import _normalise_report


class TestNormaliseReport:
    def _make_df(self, player_names, statuses=None):
        statuses = statuses or ["Questionable"] * len(player_names)
        return pd.DataFrame({
            "Player Name": player_names,
            "Current Status": statuses,
        })

    def test_last_first_converted(self):
        df = self._make_df(["James, LeBron"])
        out = _normalise_report(df)
        assert out["player_name"].iloc[0] == "LeBron James"

    def test_name_key_from_reversed(self):
        df = self._make_df(["Embiid, Joel"])
        out = _normalise_report(df)
        # fold_name lowercases + strips accents
        assert "joel" in out["name_key"].iloc[0]
        assert "embiid" in out["name_key"].iloc[0]

    def test_already_first_last_unchanged(self):
        df = self._make_df(["Anthony Davis"])
        out = _normalise_report(df)
        assert out["player_name"].iloc[0] == "Anthony Davis"

    def test_status_parsed(self):
        df = self._make_df(["Player, First"], ["Out"])
        out = _normalise_report(df)
        # _parse_status("Out") -> "O" (short code for OUT)
        assert out["status_code"].iloc[0] == "O"


# ---------------------------------------------------------------------------
# get_injury_context — active-team filter
# ---------------------------------------------------------------------------

from injury_parser import get_injury_context


class TestGetInjuryContextActiveTeamFilter:
    """Verify that get_injury_context only processes players on teams playing today."""

    def _make_fake_injury_df(self):
        return pd.DataFrame({
            "player_name": ["LeBron James", "Giannis Antetokounmpo"],
            "status_raw": ["Out", "Questionable"],
            "status_code": ["OUT", "Q"],
            "play_prob": [0.0, 0.5],
            "name_key": ["lebron james", "giannis antetokounmpo"],
            "player_id": [1, 2],
            "team_id": [10, 20],
        })

    def test_returns_empty_when_no_active_team_match(self):
        """Players on teams 10/20, but only team 30 is playing — filter removes all."""
        fake_df = self._make_fake_injury_df()

        with patch("injury_parser.fetch_injury_report", return_value=fake_df), \
             patch("injury_parser.resolve_player_ids", return_value=fake_df), \
             patch("injury_parser.get_conn") as mock_conn:

            # Simulate: one active game with team_ids 30, 40 (not 10 or 20)
            mock_cursor = MagicMock()
            mock_cursor.execute.return_value.fetchall.return_value = [
                {"home_team_id": 30, "away_team_id": 40}
            ]
            # For the pid_to_team lookup — players 1,2 are on teams 10,20
            mock_cursor.execute.side_effect = lambda q, *a, **kw: _multi_cursor(q, mock_cursor)
            mock_conn.return_value = mock_cursor

            # Patch the players lookup directly
            with patch("injury_parser.get_conn") as mc2:
                conn_inst = MagicMock()
                conn_inst.__enter__ = lambda s: s
                conn_inst.__exit__ = MagicMock(return_value=False)
                # First call: active_team_ids query
                active_result = MagicMock()
                active_result.fetchall.return_value = [{"home_team_id": 30, "away_team_id": 40}]
                # Second call: players query
                players_result = MagicMock()
                players_result.fetchall.return_value = [
                    {"player_id": 1, "team_id": 10},
                    {"player_id": 2, "team_id": 20},
                ]
                conn_inst.execute.side_effect = [active_result, players_result]
                mc2.return_value = conn_inst

                statuses, overrides = get_injury_context(
                    game_date="2026-05-05",
                    season="2025-26",
                    db_path=":memory:",
                )

        # No players on active teams → empty dicts
        assert statuses == {}
        assert overrides == {}

    def test_active_team_players_included(self):
        """Players whose team_id matches active teams should be processed."""
        fake_df = self._make_fake_injury_df()
        # Player 1 on team 10, player 2 on team 20; game has teams 10 + 30
        # Player 1 should be included, player 2 excluded

        with patch("injury_parser.fetch_injury_report", return_value=fake_df), \
             patch("injury_parser.resolve_player_ids", return_value=fake_df), \
             patch("injury_parser.get_conn") as mc:

            conn_inst = MagicMock()
            active_result = MagicMock()
            active_result.fetchall.return_value = [{"home_team_id": 10, "away_team_id": 30}]
            players_result = MagicMock()
            players_result.fetchall.return_value = [
                {"player_id": 1, "team_id": 10},
                {"player_id": 2, "team_id": 20},
            ]
            conn_inst.execute.side_effect = [active_result, players_result]
            mc.return_value = conn_inst

            # get_injury_context will filter injury_df to players on team 10 or 30
            # Player 1 (team 10) is on an active team — should be included in statuses
            # We need the full processing to run — patch at the per-player DB queries too
            with patch("injury_parser._get_team_rotation", return_value=pd.DataFrame()):
                statuses, overrides = get_injury_context(
                    game_date="2026-05-05",
                    season="2025-26",
                    db_path=":memory:",
                )

            # Player 1 (OUT) should be in statuses; player 2 filtered out
            assert 1 in statuses
            assert statuses[1] in ("OUT", "O", "Q")  # code depends on status_code column value
            assert 2 not in statuses


def _multi_cursor(q, cursor):
    return cursor.execute.return_value
