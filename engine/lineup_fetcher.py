"""lineup_fetcher.py — Fetch confirmed NBA starting lineups from the NBA live API.

Teams submit starting lineups ~30 min before tip-off.  Once submitted, they
appear in the nba_api live BoxScore feed with starter="1".  For morning
projection runs this returns {} (starters not yet confirmed); it populates
for --late-run calls close to tip-off.

Usage:
    from lineup_fetcher import fetch_confirmed_starters
    starters = fetch_confirmed_starters("2026-05-08")
    # {"PHI": ["Kelly Oubre Jr.", ...], "NYK": [...], ...}
    # Returns {} when no starters confirmed yet.
"""
from __future__ import annotations
import logging
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

log = logging.getLogger("lineup_fetcher")


def fetch_confirmed_starters(game_date: str | None = None) -> dict[str, list[str]]:
    """Return {team_tricode: [starter_name, ...]} for all games with confirmed lineups.

    Only includes teams with exactly 5 confirmed starters.  Returns {} gracefully
    when starters not yet submitted, nba_api unavailable, or on any error.

    game_date is accepted for interface consistency with the rest of the pipeline
    but is not used to filter — the NBA live scoreboard always returns today's games.
    """
    try:
        from nba_api.live.nba.endpoints import scoreboard as _sb_mod
        from nba_api.live.nba.endpoints import boxscore as _bs_mod
    except ImportError:
        log.warning("nba_api not installed — confirmed lineups unavailable")
        return {}

    try:
        sb_data = _sb_mod.ScoreBoard().get_dict()
        games = sb_data["scoreboard"]["games"]
    except Exception as exc:
        log.warning("ScoreBoard fetch failed: %s", exc)
        return {}

    result: dict[str, list[str]] = {}

    for game in games:
        game_id = game.get("gameId", "")
        if not game_id:
            continue
        try:
            bs_data = _bs_mod.BoxScore(game_id).get_dict()
        except Exception as exc:
            log.warning("BoxScore fetch failed for %s: %s", game_id, exc)
            continue

        game_node = bs_data.get("game", {})
        for side in ("homeTeam", "awayTeam"):
            team_node = game_node.get(side, {})
            tricode = team_node.get("teamTricode", "")
            players = team_node.get("players", [])
            starters = [
                p.get("name") or f"{p.get('firstName', '')} {p.get('familyName', '')}".strip()
                for p in players if str(p.get("starter", "0")) == "1"
            ]
            if len(starters) == 5:
                result[tricode] = starters
                log.info("Confirmed starters %s: %s", tricode, ", ".join(starters))
            elif starters:
                log.debug("Partial starters %s (%d/5) — not yet complete", tricode, len(starters))

    return result
