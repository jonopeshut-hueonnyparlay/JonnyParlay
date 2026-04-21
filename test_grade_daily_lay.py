"""test_grade_daily_lay.py — regression test for grade_picks.grade_daily_lay.

Covers audit finding C-10 (daily-lay all-loss handling). The audit claimed
that when every leg loses, the aggregator falls through to "W". This test
pins the correct behaviour — any losing leg returns "L" immediately.

Run:
    cd engine && python -m pytest ../test_grade_daily_lay.py -v
    # or: cd engine && python ../test_grade_daily_lay.py   (no pytest dependency)

These are pure-function tests — no network, no Discord, no filesystem.
"""

import sys
from pathlib import Path

# Import grade_daily_lay from the engine module
ENGINE_DIR = Path(__file__).resolve().parent / "engine"
sys.path.insert(0, str(ENGINE_DIR))

from grade_picks import grade_daily_lay  # noqa: E402


def _game(home, home_score, away, away_score):
    """Build one entry for the all_scores dict in the shape grade_daily_lay reads."""
    return {
        "home_team": home,
        "away_team": away,
        "scores": [
            {"name": home, "score": str(home_score)},
            {"name": away, "score": str(away_score)},
        ],
    }


def _all_scores(date_str, games):
    return {(date_str, "NBA"): games}


DATE = "2026-04-19"


def test_all_three_legs_lose_returns_L():
    """C-10 regression: every leg fails to cover → parlay is L, not W."""
    # OKC -6.5 (win by 1 only), SAS -1.5 (win by 1 only), DET +2.5 (lose by 10)
    scores = _all_scores(DATE, {
        "Memphis @ Oklahoma City Thunder":
            _game("Oklahoma City Thunder", 100, "Memphis", 99),
        "Phoenix @ San Antonio Spurs":
            _game("San Antonio Spurs", 105, "Phoenix", 104),
        "Detroit Pistons @ Brooklyn":
            _game("Brooklyn", 110, "Detroit Pistons", 100),
    })
    row = {
        "date": DATE,
        "game": "Oklahoma City Thunder -6.5 / San Antonio Spurs -1.5 / Detroit Pistons +2.5",
        "run_type": "daily_lay",
    }
    assert grade_daily_lay(row, scores) == "L"


def test_all_three_legs_win_returns_W():
    """All legs cover → parlay wins."""
    scores = _all_scores(DATE, {
        "Memphis @ Oklahoma City Thunder":
            _game("Oklahoma City Thunder", 120, "Memphis", 100),  # OKC wins by 20, covers -6.5
        "Phoenix @ San Antonio Spurs":
            _game("San Antonio Spurs", 110, "Phoenix", 100),       # SAS wins by 10, covers -1.5
        "Detroit Pistons @ Brooklyn":
            _game("Brooklyn", 100, "Detroit Pistons", 99),         # DET loses by 1, +2.5 covers
    })
    row = {
        "date": DATE,
        "game": "Oklahoma City Thunder -6.5 / San Antonio Spurs -1.5 / Detroit Pistons +2.5",
        "run_type": "daily_lay",
    }
    assert grade_daily_lay(row, scores) == "W"


def test_one_loss_in_middle_returns_L():
    """A single losing leg (second of three) → parlay lost."""
    scores = _all_scores(DATE, {
        "Memphis @ Oklahoma City Thunder":
            _game("Oklahoma City Thunder", 120, "Memphis", 100),   # OKC covers -6.5
        "Phoenix @ San Antonio Spurs":
            _game("San Antonio Spurs", 100, "Phoenix", 100),       # SAS ties — -1.5 LOSS
        "Detroit Pistons @ Brooklyn":
            _game("Brooklyn", 100, "Detroit Pistons", 99),         # DET covers +2.5
    })
    row = {
        "date": DATE,
        "game": "Oklahoma City Thunder -6.5 / San Antonio Spurs -1.5 / Detroit Pistons +2.5",
        "run_type": "daily_lay",
    }
    assert grade_daily_lay(row, scores) == "L"


def test_all_legs_push_returns_P():
    """Every leg lands exactly on the spread → whole parlay pushes."""
    # Use integer spreads so exact-margin pushes are possible
    scores = _all_scores(DATE, {
        "Memphis @ Oklahoma City Thunder":
            _game("Oklahoma City Thunder", 106, "Memphis", 100),   # OKC wins by 6, -6 = push
    })
    row = {"date": DATE, "game": "Oklahoma City Thunder -6", "run_type": "daily_lay"}
    assert grade_daily_lay(row, scores) == "P"


def test_partial_push_remaining_legs_cover_returns_W():
    """Push drops leg; remainder all cover → parlay wins on the remainder."""
    scores = _all_scores(DATE, {
        "Memphis @ Oklahoma City Thunder":
            _game("Oklahoma City Thunder", 106, "Memphis", 100),   # OKC -6 push
        "Phoenix @ San Antonio Spurs":
            _game("San Antonio Spurs", 110, "Phoenix", 100),       # SAS -1.5 cover
    })
    row = {"date": DATE,
           "game": "Oklahoma City Thunder -6 / San Antonio Spurs -1.5",
           "run_type": "daily_lay"}
    assert grade_daily_lay(row, scores) == "W"


def test_unparseable_leg_returns_None():
    """Broken game string → stays ungraded, not silently treated as W/L."""
    scores = _all_scores(DATE, {})
    row = {"date": DATE, "game": "this is not a parlay", "run_type": "daily_lay"}
    assert grade_daily_lay(row, scores) is None


def test_missing_nba_scores_returns_None():
    """No NBA scores fetched for the date → ungraded."""
    row = {"date": DATE,
           "game": "Oklahoma City Thunder -6.5",
           "run_type": "daily_lay"}
    assert grade_daily_lay(row, {}) is None


# ──────────────────────────────────────────────────────────────────────────
# Fallback runner: executes tests without requiring pytest.
# Keeps the file useful in environments where pytest isn't installed.
# ──────────────────────────────────────────────────────────────────────────

def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed, failed = 0, []
    for t in tests:
        try:
            t()
            print(f"  ✅ {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {t.__name__} — {e}")
            failed.append(t.__name__)
        except Exception as e:
            print(f"  🚫 {t.__name__} — {type(e).__name__}: {e}")
            failed.append(t.__name__)
    print(f"\n  {passed}/{len(tests)} passed")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(_run_all())
