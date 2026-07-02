"""Name-collision-safe prop matching (2026-07-02): same name_key, different players."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "engine"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from evaluators import match_props_to_projections  # noqa: E402


def _players():
    return [
        {"name_key": "muncy_max", "name": "Max Muncy", "team": "LAD", "PTS": 0, "HRR": 2.1},
        {"name_key": "muncy_max", "name": "Max Muncy", "team": "ATH", "PTS": 0, "HRR": 1.4},
        {"name_key": "witt_bob", "name": "Bobby Witt Jr.", "team": "KC", "HRR": 2.6},
    ]


def test_collision_resolved_by_game():
    props = [{"player_key": "muncy_max", "stat": "HRR", "line": 1.5, "over_odds": 100,
              "under_odds": -120, "game": "Washington Nationals @ Los Angeles Dodgers"}]
    m = match_props_to_projections(props, _players())
    assert len(m) == 1
    assert m[0]["proj_player"]["team"] == "LAD"     # the Dodgers Muncy, not the ATH one
    assert m[0]["proj"] == 2.1


def test_same_event_twins_skipped():
    # both Muncys in ONE game: the book's line names no team -> never guess
    props = [{"player_key": "muncy_max", "stat": "HRR", "line": 1.5, "over_odds": 100,
              "under_odds": -120, "game": "Los Angeles Dodgers @ Athletics"}]
    assert match_props_to_projections(props, _players()) == []


def test_single_candidate_fast_path_unchanged():
    props = [{"player_key": "witt_bob", "stat": "HRR", "line": 1.5, "over_odds": -110,
              "under_odds": -110, "game": "Tampa Bay Rays @ Kansas City Royals"}]
    m = match_props_to_projections(props, _players())
    assert len(m) == 1 and m[0]["proj"] == 2.6
