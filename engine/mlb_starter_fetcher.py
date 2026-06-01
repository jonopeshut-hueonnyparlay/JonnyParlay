"""mlb_starter_fetcher.py — Fetch probable MLB starting pitchers from the MLB Stats API.

The MLB Stats API exposes probablePitcher as soon as a team announces their
starter — typically 3-6 hours before first pitch, sometimes the day before.
SaberSim only marks pitchers "confirmed" after the batting lineup is set,
which is later. This fetcher closes that gap so the pitcher-confirmation gate
in run_picks.py can act on the earlier announcement.

Usage:
    from mlb_starter_fetcher import fetch_confirmed_starters
    starters = fetch_confirmed_starters("2026-05-22")
    # {"NYY": "Gerrit Cole", "BOS": "Brayan Bello", ...}
    # Returns {} gracefully on network error or when no starters announced yet.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from name_utils import name_key
from http_utils import default_headers

log = logging.getLogger("mlb_starter_fetcher")

_MLB_SCHEDULE_URL = (
    "https://statsapi.mlb.com/api/v1/schedule"
    "?sportId=1&date={date}&hydrate=probablePitcher"
)

# Static MLB team ID → abbreviation map (IDs are stable; 30 teams).
# Source: statsapi.mlb.com/api/v1/teams?sportId=1
_TEAM_ID_TO_ABBREV: dict[int, str] = {
    108: "LAA",
    109: "ARI",
    110: "BAL",
    111: "BOS",
    112: "CHC",
    113: "CIN",
    114: "CLE",
    115: "COL",
    116: "DET",
    117: "HOU",
    118: "KC",
    119: "LAD",
    120: "WSH",
    121: "NYM",
    133: "OAK",   # Athletics (now Sacramento — SaberSim may still use OAK)
    134: "PIT",
    135: "SD",
    136: "SEA",
    137: "SF",
    138: "STL",
    139: "TB",
    140: "TEX",
    141: "TOR",
    142: "MIN",
    143: "PHI",
    144: "ATL",
    145: "CWS",
    146: "MIA",
    147: "NYY",
    158: "MIL",
}


def _norm_name(name: str) -> str:
    """Lowercase, strip accents, remove suffixes — mirrors run_picks name_key logic."""
    try:
        from name_utils import fold_name
        return fold_name(name)
    except ImportError:
        import unicodedata, re
        n = unicodedata.normalize("NFD", name)
        n = "".join(c for c in n if unicodedata.category(c) != "Mn")
        n = n.lower()
        n = re.sub(r"\b(jr\.?|sr\.?|ii|iii|iv|v)\b", "", n)
        n = re.sub(r"[^a-z ]", "", n)
        return n.strip()



def fetch_confirmed_starters(game_date: str | None = None) -> dict[str, list[str]]:
    """Return {team_abbrev: [pitcher_full_name, ...]} for today's probable starters.

    Uses the MLB Stats API probablePitcher hydration. A player listed as
    probablePitcher is treated as confirmed for the pitcher-gate in run_picks.py
    — they're announced well before SaberSim confirms the batting lineup.

    Returns {} gracefully on any error so the existing SaberSim "confirmed"
    status check in run_picks.py still works as fallback.
    """
    try:
        import requests as _req
    except ImportError:
        log.warning("requests not installed — MLB starter fetch unavailable")
        return {}

    from datetime import date as _date
    date_str = game_date or _date.today().isoformat()

    try:
        url = _MLB_SCHEDULE_URL.format(date=date_str)
        resp = _req.get(url, timeout=10, headers=default_headers())
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("MLB Stats API fetch failed: %s", exc)
        return {}

    # dict[abbrev, list[names]] — list handles doubleheaders where a team has
    # two probable starters (one per game); second game no longer overwrites first.
    result: dict[str, list[str]] = {}

    try:
        for date_block in data.get("dates", []):
            for game in date_block.get("games", []):
                teams = game.get("teams", {})
                for side in ("home", "away"):
                    team_data = teams.get(side, {})
                    team_id = team_data.get("team", {}).get("id")
                    pitcher = team_data.get("probablePitcher", {})
                    if team_id and pitcher:
                        abbrev = _TEAM_ID_TO_ABBREV.get(team_id, "")
                        name = pitcher.get("fullName", "")
                        if abbrev and name:
                            result.setdefault(abbrev, []).append(name)
                            log.info("Probable starter %s: %s", abbrev, name)
    except Exception as exc:
        log.warning("MLB Stats API parse failed: %s", exc)
        return {}

    return result


def is_confirmed(pitcher_name: str, team_abbrev: str,
                 confirmed_starters: dict[str, list[str]]) -> bool:
    """Return True if pitcher_name matches any confirmed starter for team_abbrev.

    confirmed_starters is a dict[abbrev, list[names]] — the list handles
    doubleheaders where a team has two starters on the same day.
    Uses fuzzy name_key matching so 'José Berríos' matches 'Jose Berrios'.
    """
    if not confirmed_starters:
        return False
    api_names = confirmed_starters.get(team_abbrev.upper(), [])
    if not api_names:
        return False
    pitcher_key = name_key(pitcher_name)
    return any(pitcher_key == name_key(n) for n in api_names)
