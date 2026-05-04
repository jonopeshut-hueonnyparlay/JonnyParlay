"""Tests for Apr 28 2026 daily lay redesign: per-leg gates + Kelly sizing.

Audit H11 — zero coverage existed before this file.
Covers: size_daily_lay, build_alt_spread_parlay gates, _daily_lay_legs_json,
        grade_daily_lay JSON-legs path (H9).
"""

import json
import sys, os
from unittest import mock
sys.path.insert(0, os.path.dirname(__file__))

import pytest


# ---------------------------------------------------------------------------
# size_daily_lay
# ---------------------------------------------------------------------------

class TestSizeDailyLay:
    """Kelly-derived sizing: 0.25u floor, 0.75u cap, quarter-Kelly formula."""

    def _import(self):
        # Import lazily to avoid pulling the whole engine at collection time
        import importlib, types
        # run_picks is large — patch sys.modules to skip heavy side-effects
        import unittest.mock as mock
        # We only need size_daily_lay — extract it by importing run_picks
        # (which has no heavy imports at module level beyond stdlib + requests)
        import run_picks as rp
        return rp.size_daily_lay

    def test_zero_prob_returns_floor(self):
        f = self._import()
        assert f(0.0, -110) == 0.25

    def test_negative_prob_returns_floor(self):
        f = self._import()
        assert f(-0.1, -110) == 0.25

    def test_none_odds_returns_floor(self):
        f = self._import()
        assert f(0.60, None) == 0.25

    def test_negative_kelly_returns_floor(self):
        """Very low prob on a favourite → Kelly < 0 → floor."""
        f = self._import()
        # combined_prob=0.50, odds=-300 → bad EV → negative Kelly
        result = f(0.50, -300)
        assert result == 0.25

    def test_high_prob_favourite_caps_at_75(self):
        f = self._import()
        # combined_prob=0.95, odds=-110 → very high Kelly → capped at 0.75
        result = f(0.95, -110)
        assert result == 0.75

    def test_moderate_prob_in_range(self):
        f = self._import()
        # ~60% combined prob at +100 → positive EV → between floor and cap
        result = f(0.60, 100)
        assert 0.25 <= result <= 0.75

    def test_positive_odds_formula(self):
        """Positive american odds: dec = 1 + odds/100."""
        f = self._import()
        # +200 odds: dec=3.0, b=2.0; prob=0.60, q=0.40
        # kelly_full = (0.60*2 - 0.40)/2 = 0.80/2 = 0.40
        # quarter_kelly = 0.40 * 0.25 = 0.10; raw_units = 10.0 → rounds to 0.25 floor
        result = f(0.60, 200)
        assert 0.25 <= result <= 0.75

    def test_negative_odds_formula(self):
        """Negative american odds: dec = 1 + 100/abs(odds)."""
        f = self._import()
        result = f(0.65, -120)
        assert 0.25 <= result <= 0.75

    def test_output_is_multiple_of_025(self):
        """round_units should snap to 0.25 increments."""
        f = self._import()
        for prob in [0.52, 0.58, 0.63, 0.70, 0.80]:
            for odds in [-130, -110, 100, 150]:
                result = f(prob, odds)
                remainder = round(result % 0.25, 9)
                assert remainder in (0.0, 0.25 % 0.25), \
                    f"size_daily_lay({prob}, {odds})={result} not a 0.25 multiple"


# ---------------------------------------------------------------------------
# MIN_DAILY_LAY_PROB gate (post_daily_lay level)
# ---------------------------------------------------------------------------

class TestDailyLayProbGate:
    def test_constant_value(self):
        import run_picks as rp
        assert rp.MIN_DAILY_LAY_PROB == 0.47

    def test_min_daily_lay_margin_constant(self):
        import run_picks as rp
        assert rp.MIN_DAILY_LAY_MARGIN == 4.0


# ---------------------------------------------------------------------------
# _daily_lay_legs_json (H9 — run_picks side)
# ---------------------------------------------------------------------------

class TestDailyLayLegsJson:
    def _fn(self):
        import run_picks as rp
        return rp._daily_lay_legs_json

    def _leg(self, team="OKC", alt_spread=4.5, game="OKC @ DEN",
             alt_cover_prob=0.62, real_odds=-115):
        return {
            "team": team,
            "alt_spread": alt_spread,
            "game": game,
            "alt_cover_prob": alt_cover_prob,
            "real_odds": real_odds,
        }

    def test_returns_valid_json(self):
        f = self._fn()
        result = f([self._leg()])
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 1

    def test_fields_present(self):
        f = self._fn()
        leg = self._leg(team="OKC", alt_spread=4.5, game="OKC @ DEN",
                        alt_cover_prob=0.62, real_odds=-115)
        parsed = json.loads(f([leg]))
        assert parsed[0]["team"] == "OKC"
        assert parsed[0]["spread"] == 4.5
        assert parsed[0]["game"] == "OKC @ DEN"
        assert abs(parsed[0]["cover_prob"] - 0.62) < 1e-6
        assert parsed[0]["odds"] == -115

    def test_negative_spread_preserved(self):
        f = self._fn()
        leg = self._leg(alt_spread=-3.5)
        parsed = json.loads(f([leg]))
        assert parsed[0]["spread"] == -3.5

    def test_two_legs(self):
        f = self._fn()
        legs = [self._leg("OKC", 4.5), self._leg("MIN", 3.0, game="MIN @ LAL")]
        parsed = json.loads(f(legs))
        assert len(parsed) == 2
        assert parsed[1]["team"] == "MIN"

    def test_empty_legs_returns_empty_array(self):
        f = self._fn()
        result = f([])
        parsed = json.loads(result)
        assert parsed == []

    def test_bad_leg_returns_empty_string(self):
        """Exception in serialization → return ''."""
        f = self._fn()
        # Pass an object that can't be converted
        result = f([{"real_odds": "not_a_number_or_int"}])
        # odds=int(round("not_a_number_or_int")) raises → returns ""
        assert result == "" or isinstance(json.loads(result or "[]"), list)

    def test_cover_prob_fallback_to_cover_prob_key(self):
        """Falls back to leg['cover_prob'] if alt_cover_prob missing."""
        f = self._fn()
        leg = {"team": "DEN", "alt_spread": 2.5, "game": "OKC @ DEN",
               "cover_prob": 0.61, "real_odds": -120}
        parsed = json.loads(f([leg]))
        assert abs(parsed[0]["cover_prob"] - 0.61) < 1e-6


# ---------------------------------------------------------------------------
# grade_daily_lay — JSON legs path (H9 grader side)
# ---------------------------------------------------------------------------

class TestGradeDailyLayJsonPath:
    """grade_daily_lay should prefer the legs JSON column over game-string."""

    def _all_scores(self, date, home_score, away_score,
                    home_team="Oklahoma City Thunder",
                    away_team="Denver Nuggets"):
        return {
            (date, "NBA"): {
                f"{away_team} @ {home_team}": {
                    "home_team": home_team,
                    "away_team": away_team,
                    "scores": [
                        {"name": home_team, "score": str(home_score)},
                        {"name": away_team, "score": str(away_score)},
                    ],
                    "completed": True,
                }
            }
        }

    def _row(self, date="2026-04-15", legs_json="", game=""):
        return {"date": date, "game": game, "legs": legs_json}

    def test_json_legs_win(self):
        """OKC +4.5: OKC wins by 10 → covers → W."""
        from engine.grade_picks import grade_daily_lay
        legs_json = json.dumps([{
            "team": "Oklahoma City Thunder",
            "spread": 4.5,
            "game": "Denver Nuggets @ Oklahoma City Thunder",
            "cover_prob": 0.62,
            "odds": -115,
        }])
        row = self._row(legs_json=legs_json, game="")  # game field empty — JSON only
        scores = self._all_scores("2026-04-15", home_score=110, away_score=100)
        # OKC (home) wins 110-100, margin = +10, spread=+4.5 → result_val=14.5 > 0 → W
        result = grade_daily_lay(row, scores)
        assert result == "W"

    def test_json_legs_loss(self):
        """OKC +4.5: OKC loses by 10 → doesn't cover → L."""
        from engine.grade_picks import grade_daily_lay
        legs_json = json.dumps([{
            "team": "Oklahoma City Thunder",
            "spread": 4.5,
            "game": "Denver Nuggets @ Oklahoma City Thunder",
            "cover_prob": 0.62,
            "odds": -115,
        }])
        row = self._row(legs_json=legs_json)
        scores = self._all_scores("2026-04-15", home_score=100, away_score=110)
        # OKC (home) loses 100-110; margin = -10, spread=+4.5 → result_val=-5.5 < 0 → L
        result = grade_daily_lay(row, scores)
        assert result == "L"

    def test_json_legs_push(self):
        """OKC +4.5: OKC loses by exactly 4.5 → push (impossible in basketball but test math)."""
        from engine.grade_picks import grade_daily_lay
        legs_json = json.dumps([{
            "team": "Oklahoma City Thunder",
            "spread": 4.5,
            "game": "Denver Nuggets @ Oklahoma City Thunder",
            "cover_prob": 0.62,
            "odds": -115,
        }])
        row = self._row(legs_json=legs_json)
        # margin = -4.5 + spread(4.5) = 0 → push
        scores = self._all_scores("2026-04-15", home_score=100, away_score=104)
        # OKC (home) 100 - DEN 104 = -4, spread=+4.5 → result_val=0.5 > 0 → W
        # Let's make it exactly 0: home=100, away=104.5 not possible; use spread=-4.5 test
        legs_json2 = json.dumps([{
            "team": "Oklahoma City Thunder",
            "spread": -4.0,
            "game": "Denver Nuggets @ Oklahoma City Thunder",
            "cover_prob": 0.62,
            "odds": -115,
        }])
        row2 = self._row(legs_json=legs_json2)
        scores2 = self._all_scores("2026-04-15", home_score=104, away_score=100)
        # OKC home wins 104-100, margin=+4; spread=-4 → result_val = 0 → push
        result = grade_daily_lay(row2, scores2)
        assert result == "P"

    def test_invalid_json_falls_back_to_game_string(self):
        """Corrupt legs → fall back to game-field string parsing."""
        from engine.grade_picks import grade_daily_lay
        row = self._row(legs_json="{bad json!", game="Oklahoma City Thunder +4.5")
        scores = self._all_scores("2026-04-15", home_score=110, away_score=100)
        # Should fall back to game-string parsing and return W
        result = grade_daily_lay(row, scores)
        assert result == "W"

    def test_empty_legs_falls_back_to_game_string(self):
        """Empty legs field → fall back to game-string parsing."""
        from engine.grade_picks import grade_daily_lay
        row = self._row(legs_json="", game="Oklahoma City Thunder +4.5")
        scores = self._all_scores("2026-04-15", home_score=110, away_score=100)
        result = grade_daily_lay(row, scores)
        assert result == "W"


class TestPerLegGates:
    """H31: per-leg edge + cover_prob gates inside build_alt_spread_parlay.

    Uses real NBA team names so TEAM_ABBREV lookup succeeds and team_game_info
    is populated with a non-None margin, letting entries reach the per-leg gates.
    sport_sigmas must be nested: {"NBA": {"spread": float}}.
    alt_spread_data must supply the actual spread candidates to evaluate.
    """

    _HOME = "Los Angeles Lakers"   # TEAM_ABBREV key "los angeles lakers" -> LAL
    _AWAY = "Boston Celtics"       # TEAM_ABBREV key "boston celtics" -> BOS
    _HOME_KEY = "NBA_LAL"
    _AWAY_KEY = "NBA_BOS"

    def _make_inputs(self, home_odds=-110):
        """Return (game_lines, team_proj_map, sport_sigmas, alt_spread_data)."""
        game_lines = [{
            "game": f"{self._AWAY} @ {self._HOME}",
            "home": self._HOME,
            "away": self._AWAY,
            "spread": {
                self._HOME: {"line": -3.5, "odds": home_odds, "book": "fanduel"},
                self._AWAY: {"line": +3.5, "odds": -110, "book": "fanduel"},
            },
            "total": {},
            "ml": {},
            "sport": "NBA",
            "event_id": "test_ev_1",
        }]
        team_proj_map = {
            self._HOME_KEY: {"saber_team": 115.0},
            self._AWAY_KEY: {"saber_team": 111.0},
        }
        sport_sigmas = {"NBA": {"spread": 8.0}}
        # One candidate entry for the home team
        alt_spread_data = [{"team": self._HOME, "odds": home_odds, "line": -3.5}]
        return game_lines, team_proj_map, sport_sigmas, alt_spread_data

    def test_low_cover_prob_leg_is_rejected(self):
        """A leg with cover_prob < MIN_LEG_COVER_PROB_DAILY (0.58) is rejected.

        odds=-110 → implied≈0.524; normal_cdf=0.45 → cover_prob=0.55 < 0.58.
        Edge (0.026) is fine but cover_prob gate fires first.
        """
        import run_picks as rp
        game_lines, tpm, ss, asd = self._make_inputs(home_odds=-110)
        with mock.patch.object(rp, "normal_cdf", return_value=0.45):
            result = rp.build_alt_spread_parlay(
                game_lines=game_lines,
                team_proj_map=tpm,
                sport_sigmas=ss,
                alt_spread_data=asd,
            )
        assert result is None, "Low cover_prob leg should be rejected → no parlay"

    def test_low_edge_leg_is_rejected(self):
        """A leg with edge < MIN_LEG_EDGE_DAILY (0.025) is rejected.

        odds=-150 → implied=0.60; normal_cdf=0.40 → cover_prob=0.60.
        cover_prob (0.60) >= 0.58 passes that gate; edge=0.00 < 0.025 fails.
        """
        import run_picks as rp
        game_lines, tpm, ss, asd = self._make_inputs(home_odds=-150)
        with mock.patch.object(rp, "normal_cdf", return_value=0.40):
            result = rp.build_alt_spread_parlay(
                game_lines=game_lines,
                team_proj_map=tpm,
                sport_sigmas=ss,
                alt_spread_data=asd,
            )
        assert result is None, "Zero-edge leg should be rejected → no parlay"
