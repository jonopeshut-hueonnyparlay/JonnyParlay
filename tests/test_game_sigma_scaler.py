"""Tests for the Plan 6 §6 game-sigma fixes (2026-06-05).

Locks in:
  - NBA GAME_SIGMA calibration: {total: 18.5, spread: 12.5, team: 11.0, ml: 12.5}
    (residual-basis from 3,922 reconstructed games; prior 12/12/9/12 was never
    calibrated — total ~40% too narrow).
  - get_game_sigma() relative-scaler formula:
        sigma = sigma_league(market) * sqrt((sh^2 + sa^2) / (2 * mean_sq_league))
    replacing the independence sum sqrt(sh^2 + sa^2), which dropped the
    home/away covariance (rho_NBA = +0.227) and inflated NBA spread/ML sigma
    ~45% while silently overriding the per-market NHL calibration.
"""

import math

import pytest

import run_picks
from run_picks import GAME_SIGMA, get_game_sigma


# ---------------------------------------------------------------------------
# Fixtures — fake team-sigma tables injected around the module globals
# ---------------------------------------------------------------------------

LEAGUE_MEANSQ = 12.0 ** 2  # mean of score_sigma^2 across the fake league


@pytest.fixture
def fake_teams(monkeypatch):
    """Two high-var teams, two low-var, one thin-sample team."""
    data = {
        "AAA": {"score_sigma": 14.0, "n_games": 100},   # high variance
        "BBB": {"score_sigma": 14.0, "n_games": 100},   # high variance
        "CCC": {"score_sigma": 10.0, "n_games": 100},   # low variance
        "DDD": {"score_sigma": 10.0, "n_games": 100},   # low variance
        "EEE": {"score_sigma": 12.0, "n_games": 100},   # league-average
        "FFF": {"score_sigma": 12.0, "n_games": 100},   # league-average
        "GGG": {"score_sigma": 14.0, "n_games": 5},     # below n_games floor
    }
    monkeypatch.setattr(run_picks, "_TEAM_SIGMAS", {"NBA": data})
    monkeypatch.setattr(run_picks, "_TEAM_SIGMAS_MEANSQ", {"NBA": LEAGUE_MEANSQ})
    return data


# ---------------------------------------------------------------------------
# Calibrated NBA values
# ---------------------------------------------------------------------------

def test_nba_game_sigma_calibrated_values():
    assert GAME_SIGMA["NBA"] == {"total": 18.5, "spread": 12.5, "team": 11.0, "ml": 12.5}


def test_nba_total_no_longer_too_narrow():
    """Prior total=12.0 was ~40% below the empirical residual SD (19.33)."""
    assert GAME_SIGMA["NBA"]["total"] >= 18.0


# ---------------------------------------------------------------------------
# Relative-scaler formula
# ---------------------------------------------------------------------------

def test_league_average_pair_returns_league_sigma(fake_teams):
    """Two league-average teams -> scaler = 1.0 -> exactly the league sigma."""
    for market in ("total", "spread", "ml"):
        assert get_game_sigma("NBA", "EEE", "FFF", market) == pytest.approx(
            GAME_SIGMA["NBA"][market])


def test_high_variance_pair_scales_up(fake_teams):
    sigma = get_game_sigma("NBA", "AAA", "BBB", "spread")
    expected = 12.5 * math.sqrt((14.0**2 + 14.0**2) / (2 * LEAGUE_MEANSQ))
    assert sigma == pytest.approx(expected)
    assert sigma > 12.5


def test_low_variance_pair_scales_down(fake_teams):
    sigma = get_game_sigma("NBA", "CCC", "DDD", "total")
    expected = 18.5 * math.sqrt((10.0**2 + 10.0**2) / (2 * LEAGUE_MEANSQ))
    assert sigma == pytest.approx(expected)
    assert sigma < 18.5


def test_not_independence_sum(fake_teams):
    """The old formula returned sqrt(sh^2+sa^2) — ~19.8 for the high-var pair.
    The scaler form must stay anchored to the per-market league sigma instead."""
    sigma = get_game_sigma("NBA", "AAA", "BBB", "spread")
    independence = math.sqrt(14.0**2 + 14.0**2)  # 19.80
    assert sigma != pytest.approx(independence)
    assert sigma < independence


def test_per_market_calibration_preserved(fake_teams):
    """Same matchup, different markets -> different sigmas (old formula
    collapsed every market to the same independence sum)."""
    total = get_game_sigma("NBA", "AAA", "BBB", "total")
    spread = get_game_sigma("NBA", "AAA", "BBB", "spread")
    assert total != pytest.approx(spread)
    assert total / spread == pytest.approx(18.5 / 12.5)


# ---------------------------------------------------------------------------
# Fallbacks
# ---------------------------------------------------------------------------

def test_unknown_team_falls_back_to_league(fake_teams):
    assert get_game_sigma("NBA", "AAA", "ZZZ", "spread") == pytest.approx(12.5)


def test_thin_sample_team_falls_back_to_league(fake_teams):
    """n_games < 20 on either side -> league sigma (quality floor)."""
    assert get_game_sigma("NBA", "AAA", "GGG", "total") == pytest.approx(18.5)


def test_no_team_data_falls_back_to_league(monkeypatch):
    monkeypatch.setattr(run_picks, "_TEAM_SIGMAS", {})
    monkeypatch.setattr(run_picks, "_TEAM_SIGMAS_MEANSQ", {})
    assert get_game_sigma("NBA", "AAA", "BBB", "ml") == pytest.approx(12.5)


def test_zero_meansq_falls_back_to_league(monkeypatch, fake_teams):
    """Defensive: a sport whose JSON had no qualifying teams must not divide by 0."""
    monkeypatch.setattr(run_picks, "_TEAM_SIGMAS_MEANSQ", {"NBA": 0.0})
    assert get_game_sigma("NBA", "AAA", "BBB", "total") == pytest.approx(18.5)


def test_wnba_numeric_keys_fall_back_to_league():
    """team_sigmas_wnba.json is keyed by numeric team_ids — name lookups miss
    and must fall back to the calibrated WNBA league sigma."""
    assert get_game_sigma("WNBA", "Las Vegas Aces", "New York Liberty", "total") == \
        pytest.approx(GAME_SIGMA["WNBA"]["total"])


def test_team_market_unaffected(fake_teams):
    """'team' market is handled by get_game_sigma_team(); get_game_sigma returns
    league sigma for it regardless of team data."""
    assert get_game_sigma("NBA", "AAA", "BBB", "team") == pytest.approx(11.0)


# ---------------------------------------------------------------------------
# Loader mean-square computation
# ---------------------------------------------------------------------------

def test_meansq_loaded_for_real_sports():
    """_load_team_sigmas() must populate a positive mean-square for every sport
    with a JSON on disk (NBA/NHL/MLB at minimum)."""
    for sport in ("NBA", "NHL", "MLB"):
        if sport in run_picks._TEAM_SIGMAS:
            assert run_picks._TEAM_SIGMAS_MEANSQ.get(sport, 0.0) > 0.0


def test_meansq_matches_filtered_mean():
    """meansq = mean of score_sigma^2 over teams with n_games >= 20."""
    for sport, data in run_picks._TEAM_SIGMAS.items():
        sq = [t["score_sigma"] ** 2 for t in data.values()
              if isinstance(t, dict) and t.get("score_sigma") and t.get("n_games", 0) >= 20]
        if sq:
            assert run_picks._TEAM_SIGMAS_MEANSQ[sport] == pytest.approx(sum(sq) / len(sq))
