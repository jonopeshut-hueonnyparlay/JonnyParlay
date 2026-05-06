#!/usr/bin/env python3
"""H2 (Audit 2026-05-06): cold_start_min_cap must not clamp injury_minutes_override.

The override-bypass guard at nba_projector.py:1130 ensures an authoritative
announced minutes restriction (e.g. "Player X returns from injury, 18-min cap")
is preserved through the cold_start cap branch.  Without the guard, a taxi
sub-type cold_start player (cap=12) with override=18 was silently re-clamped
to 12 — violating the design contract documented at line 1151.
"""
from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent / "engine"
sys.path.insert(0, str(ENGINE))


# ---------------------------------------------------------------------------
# Source-level guard test — catches accidental removal of the override bypass.
# ---------------------------------------------------------------------------


class TestH2GuardPresentInSource:
    """Source-level regression check for the H2 fix."""

    def test_override_bypass_guard_present(self):
        """The cap-clamp condition must include `injury_minutes_override is None`."""
        import nba_projector
        src = inspect.getsource(nba_projector.project_player)
        # Locate the cold_start cap branch and confirm the guard precedes it.
        # Pattern allows whitespace / newlines between the guard and the cap check.
        pattern = re.compile(
            r"injury_minutes_override\s+is\s+None"
            r"[\s\S]{0,200}?"
            r"cold_start_min_cap\s+is\s+not\s+None",
            re.MULTILINE,
        )
        assert pattern.search(src), (
            "H2 fix missing: cold_start_min_cap branch must be guarded by "
            "`injury_minutes_override is None` so an authoritative override "
            "is not silently re-clamped."
        )


# ---------------------------------------------------------------------------
# Behavioral test — invokes project_player end-to-end with stubbed upstream
# calls.  Verifies the override survives the cap branch in the taxi (cap=12)
# scenario.
# ---------------------------------------------------------------------------


def _empty_recent_games_df() -> pd.DataFrame:
    """Mimic get_player_recent_games() empty result for a brand-new (taxi) player."""
    cols = [
        "game_id", "game_date", "season", "season_type", "team_id", "tm_min",
        "min", "pts", "reb", "ast", "fg3m", "stl", "blk", "tov",
        "fga", "fg3a", "fgm", "fg3m_made", "ftm", "fta",
        "starter_flag", "fg_pct", "fg3_pct", "ft_pct",
    ]
    return pd.DataFrame(columns=cols)


@pytest.fixture
def stub_project_player_deps(monkeypatch):
    """Stub every external dep used inside project_player.

    Builds a synthetic taxi cold_start scenario:
      - 0 prior recent games (DataFrame empty)
      - 0 career games  → cold_start_subtype = "taxi", cold_start_min_cap = 12.0
      - league-average pace / shooting / matchup factors

    With these stubs the only thing that drives proj_min is the
    injury_minutes_override path inside project_minutes() and the cap
    branch in project_player().
    """
    import nba_projector as np_mod

    monkeypatch.setattr(np_mod, "get_player_recent_games",
                        lambda *a, **k: _empty_recent_games_df())
    # < MIN_GAMES_FOR_TIER (=10) → cold_start branch
    monkeypatch.setattr(np_mod, "get_player_season_game_count",
                        lambda *a, **k: 0)
    monkeypatch.setattr(np_mod, "get_player_b2b_context",
                        lambda *a, **k: {"days_rest": 3, "is_b2b": False})
    monkeypatch.setattr(np_mod, "get_player_trade_context",
                        lambda *a, **k: None)
    # 0 career games + None avg → taxi (cap = 12.0)
    monkeypatch.setattr(np_mod, "get_player_career_avg_minutes",
                        lambda *a, **k: None)
    monkeypatch.setattr(np_mod, "get_player_career_game_count",
                        lambda *a, **k: (0, None))
    monkeypatch.setattr(np_mod, "get_player_last_appearance_days",
                        lambda *a, **k: None)
    # League-average pace + neutral matchup factors
    monkeypatch.setattr(np_mod, "get_team_pace",
                        lambda *a, **k: 100.22)
    monkeypatch.setattr(np_mod, "get_team_def_ratio",
                        lambda *a, **k: 1.0)
    monkeypatch.setattr(np_mod, "get_team_tov_rate",
                        lambda *a, **k: np_mod.LEAGUE_AVG_TOV_RATE)
    monkeypatch.setattr(np_mod, "get_team_rim_attempt_rate",
                        lambda *a, **k: np_mod.LEAGUE_AVG_RIM_ATTEMPT_RATE)
    monkeypatch.setattr(np_mod, "get_team_avg_fga",
                        lambda *a, **k: 88.0)
    monkeypatch.setattr(np_mod, "get_team_shooting_stats",
                        lambda *a, **k: {"fga_per_game": 88.0, "fg_pct": 0.47})
    # availability_weights returns empty Series for empty df — fine
    yield np_mod


class TestH2BehavioralOverrideBypass:
    """End-to-end verification: override survives taxi cold_start cap."""

    def test_taxi_with_override_keeps_override(self, stub_project_player_deps):
        """H2: override must survive the cold_start_min_cap (taxi=12).

        Override value 14 sits above the taxi sub-type cap (12) and below the
        broader cold_start role ceiling ROLE_MAX_MIN["cold_start"]=16, so the
        only cap that should activate is the one H2 fixes.  Without the H2
        fix, proj_min would be clamped to 12.0.
        """
        np_mod = stub_project_player_deps
        result = np_mod.project_player(
            player_id=999, player_name="Taxi Override", position="F",
            team_id=1, opp_team_id=2, game_id=12345,
            game_date="2026-05-06", season="2025-26",
            season_type="Regular Season",
            implied_total=110.0, spread=0.0,
            injury_status="Q",
            injury_minutes_override=14.0,
            injury_minutes_redistrib_bump=None,
            is_home=True,
        )
        assert result is not None, "project_player returned None for taxi+override"
        assert result["proj_min"] == 14.0, (
            f"H2 regression: taxi cold_start with override=14 should keep proj_min=14.0, "
            f"got {result['proj_min']} (taxi cap=12 was clamping the override)."
        )
        assert result["role_tier"] == "cold_start"

    def test_taxi_without_override_still_capped(self, stub_project_player_deps,
                                                  monkeypatch):
        """Negative control: cap MUST still apply when no override is set.

        Force project_minutes() to return a value above the taxi cap (12.0) so the
        cap branch is exercised.  Without the H2 guard, override=None already hits
        the cap.  After the H2 fix, the cap still fires in the no-override path.
        """
        np_mod = stub_project_player_deps
        monkeypatch.setattr(np_mod, "project_minutes",
                            lambda *a, **k: 25.0)
        result = np_mod.project_player(
            player_id=999, player_name="Taxi NoOverride", position="F",
            team_id=1, opp_team_id=2, game_id=12345,
            game_date="2026-05-06", season="2025-26",
            season_type="Regular Season",
            implied_total=110.0, spread=0.0,
            injury_status="",
            injury_minutes_override=None,
            injury_minutes_redistrib_bump=None,
            is_home=True,
        )
        assert result is not None
        assert result["proj_min"] == 12.0, (
            f"Negative control failed: taxi cold_start (cap=12) with no override "
            f"and project_minutes returning 25.0 should clamp to 12.0; got "
            f"{result['proj_min']}.  H2 guard may be over-applied."
        )

    def test_taxi_with_override_below_cap_unchanged(self, stub_project_player_deps):
        """Override below cap should also pass through verbatim."""
        np_mod = stub_project_player_deps
        result = np_mod.project_player(
            player_id=999, player_name="Taxi Restricted", position="F",
            team_id=1, opp_team_id=2, game_id=12345,
            game_date="2026-05-06", season="2025-26",
            season_type="Regular Season",
            implied_total=110.0, spread=0.0,
            injury_status="Q",
            injury_minutes_override=8.0,
            injury_minutes_redistrib_bump=None,
            is_home=True,
        )
        assert result is not None
        assert result["proj_min"] == 8.0, (
            f"override=8 should pass through (below cap 12); got {result['proj_min']}"
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
