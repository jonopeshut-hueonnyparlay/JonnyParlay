"""Smoke tests for runtime/market wiring in market_config.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

import pytest

from market_config import (
    SPORT_KEYS,
    PROP_MARKETS,
    MARKET_TO_STAT,
    TEAM_ABBREV,
    WNBA_TEAM_ABBREV,
    SHADOW_SPORTS,
    SUSPENDED_STATS,
    SLOW_BOOKS,
)


def test_sport_keys_is_dict_with_core_sports():
    assert isinstance(SPORT_KEYS, dict)
    for sport in ("NBA", "MLB", "NHL", "WNBA"):
        assert sport in SPORT_KEYS


def test_sport_keys_values_non_empty_strings():
    for sport, key in SPORT_KEYS.items():
        assert isinstance(key, str) and key, f"SPORT_KEYS[{sport}]"


def test_prop_markets_non_empty_dict():
    assert isinstance(PROP_MARKETS, dict) and PROP_MARKETS


def test_market_to_stat_non_empty_dict():
    assert isinstance(MARKET_TO_STAT, dict) and MARKET_TO_STAT


def test_team_abbrev_non_empty_dict():
    assert isinstance(TEAM_ABBREV, dict) and TEAM_ABBREV


def test_wnba_team_abbrev_non_empty_dict():
    assert isinstance(WNBA_TEAM_ABBREV, dict) and WNBA_TEAM_ABBREV


def test_shadow_sports_empty_set():
    # All sports live (NBA/MLB/NHL/WNBA) — locked at WNBA go-live 2026-06-09.
    assert isinstance(SHADOW_SPORTS, set)
    assert SHADOW_SPORTS == set()
    assert "WNBA" not in SHADOW_SPORTS


def test_suspended_stats_is_dict():
    # Single source of truth: stat -> gate code (SOG/HA/RA suspended).
    assert isinstance(SUSPENDED_STATS, dict)


def test_slow_books_non_empty():
    assert isinstance(SLOW_BOOKS, (set, frozenset, list)) and len(SLOW_BOOKS) > 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
