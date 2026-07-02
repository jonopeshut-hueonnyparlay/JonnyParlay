#!/usr/bin/env python3
"""context_research_v2.py — Per-game contextual research via FREE public APIs.

A drop-in, zero-Anthropic-cost replacement for context_research.py. It writes
the SAME data/context_verdicts.json schema (read by run_picks.py and
analyze_game_lines.py), using the SAME 15-factor weighted aggregation, valid
values, cache/merge logic, and output format as the original — but every factor
is computed from a free data source instead of a paid Opus web-search call.

Active factor sources (all free):
  line_move   — Odds API opening snapshot vs current total
  era_fip     — MLB Stats API season pitching stats (FIP vs ERA regression)
  bullpen     — MLB Stats API boxscores (reliever IP, last 3 days)
  weather     — wttr.in (wind/precip/heat at the home park)
  umpire      — MLB Stats API officials + umpscorecards cache
  pythag      — standings RS/RA (MLB) or PF/PA (NBA/WNBA)
  form        — standings last-10 vs season win%
  home_away   — standings home/road splits
  rest        — schedule back-to-back detection
  travel      — eastward timezone shift (circadian disadvantage)
  division    — divisional/conference familiarity
  motivation  — playoff/wildcard race (Aug 1+)
  injury      — MLB IL endpoint / ESPN summary injuries

Stale-neutral until a key is added (weight 5/25, no code change to activate):
  rlm, public_sharp — require ACTION_NETWORK_PRO_KEY in .env

Aggregation, _apply_quality_override, cache/merge and the JSON schema are copied
verbatim from context_research.py so downstream consumers are unchanged.

Usage:
  python engine/context_research_v2.py --sport MLB
  python engine/context_research_v2.py --sport ALL
  python engine/context_research_v2.py --refresh
  python engine/context_research_v2.py --dry-run
  python engine/context_research_v2.py nba.csv --sport NBA

Daily workflow: run AFTER run_picks.py, BEFORE analyze_game_lines.py.
"""

import argparse
import csv
import json
import logging
import math
import os
import re
import sys
from datetime import date as _date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# ── Path setup — works whether called from project root or engine/ ─────────────
_ENGINE_DIR = Path(__file__).resolve().parent
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

import secrets_config  # noqa: F401 — side-effect: loads .env into os.environ
from io_utils import atomic_write_json
from paths import data_path

try:
    import requests
except ImportError:  # pragma: no cover
    sys.exit("requests package not installed. Run: pip install requests")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Constants (copied verbatim from context_research.py) ─────────────────────────

_OUT_PATH = data_path("context_verdicts.json")

_LOCAL_TZ = ZoneInfo("America/Denver")
_ALL_SPORTS = ["NBA", "MLB", "NHL", "WNBA"]

_SPORT_KEYS = {
    "NBA":  "basketball_nba",
    "MLB":  "baseball_mlb",
    "NHL":  "icehockey_nhl",
    "WNBA": "basketball_wnba",
    "NFL":  "americanfootball_nfl",
}

_FACTORS = [
    "rlm", "weather", "travel", "umpire", "era_fip", "bullpen",
    "pythag", "injury", "rest", "home_away", "form",
    "division", "motivation", "line_move", "public_sharp",
]
_VALID_VALUES = {"confirms", "fades", "neutral"}
_DATA_QUALITY_VALUES = {"fresh", "stale", "failed"}
_NEUTRAL_REASONS = {
    "researched_neutral", "hardcoded_neutral", "stale_data",
    "source_failed", "not_applicable",
}

_WEIGHTS = {
    "rlm": 3, "injury": 3, "line_move": 3,
    "era_fip": 2, "bullpen": 2, "public_sharp": 2, "motivation": 2,
    "weather": 1, "travel": 1, "umpire": 1, "pythag": 1, "rest": 1,
    "home_away": 1, "form": 1, "division": 1,
}
_MAX_POSSIBLE = sum(_WEIGHTS.values())  # 25
_VERDICT_THRESHOLD = 4

# MLB teams whose home park is domed or has a retractable roof (assumed
# closed): weather is hardcoded neutral, no fetch is made.
_DOMED_HOME_TEAMS = frozenset({
    "Tampa Bay Rays",        # Tropicana Field
    "Toronto Blue Jays",     # Rogers Centre
    "Houston Astros",        # Minute Maid Park
    "Arizona Diamondbacks",  # Chase Field
    "Miami Marlins",         # loanDepot park
    "Seattle Mariners",      # T-Mobile Park
    "Texas Rangers",         # Globe Life Field
})

# Minimal group→factor map so the verbatim group helpers below stay valid.
# v2 produces verdicts via _assemble_game_verdict_v2 (flat factors), but these
# helpers are copied unchanged from context_research.py per the build contract.
_GROUPS = {
    1: {"name": "odds_lines", "factors": ["rlm", "line_move", "public_sharp"]},
    2: {"name": "weather",    "factors": ["weather"]},
    3: {"name": "pitching",   "factors": ["era_fip", "bullpen", "umpire"]},
    4: {"name": "team",       "factors": ["pythag", "form", "division", "motivation", "home_away"]},
    5: {"name": "roster",     "factors": ["injury", "rest", "travel"]},
}
_GROUP_SUMMARY_PRIORITY = [1, 5, 3, 4, 2]

# ── MLB team maps ────────────────────────────────────────────────────────────────
# Full team name → MLB Stats API team id (ids are stable; 30 teams).
_MLB_NAME_TO_ID = {
    "Los Angeles Angels": 108, "Arizona Diamondbacks": 109,
    "Baltimore Orioles": 110, "Boston Red Sox": 111,
    "Chicago Cubs": 112, "Cincinnati Reds": 113,
    "Cleveland Guardians": 114, "Colorado Rockies": 115,
    "Detroit Tigers": 116, "Houston Astros": 117,
    "Kansas City Royals": 118, "Los Angeles Dodgers": 119,
    "Washington Nationals": 120, "New York Mets": 121,
    "Oakland Athletics": 133, "Athletics": 133,
    "Pittsburgh Pirates": 134, "San Diego Padres": 135,
    "Seattle Mariners": 136, "San Francisco Giants": 137,
    "St. Louis Cardinals": 138, "Tampa Bay Rays": 139,
    "Texas Rangers": 140, "Toronto Blue Jays": 141,
    "Minnesota Twins": 142, "Philadelphia Phillies": 143,
    "Atlanta Braves": 144, "Chicago White Sox": 145,
    "Miami Marlins": 146, "New York Yankees": 147,
    "Milwaukee Brewers": 158,
}

# wttr.in city string per MLB home park (full team name → city query).
_STADIUM_CITIES = {
    "Atlanta Braves": "Atlanta", "Arizona Diamondbacks": "Phoenix",
    "Baltimore Orioles": "Baltimore", "Boston Red Sox": "Boston",
    "Chicago Cubs": "Chicago", "Chicago White Sox": "Chicago",
    "Cincinnati Reds": "Cincinnati", "Cleveland Guardians": "Cleveland",
    "Colorado Rockies": "Denver", "Detroit Tigers": "Detroit",
    "Houston Astros": "Houston", "Kansas City Royals": "Kansas+City",
    "Los Angeles Angels": "Anaheim", "Los Angeles Dodgers": "Los+Angeles",
    "Miami Marlins": "Miami", "Milwaukee Brewers": "Milwaukee",
    "Minnesota Twins": "Minneapolis", "New York Mets": "New+York",
    "New York Yankees": "New+York", "Oakland Athletics": "West+Sacramento",
    "Athletics": "West+Sacramento", "Philadelphia Phillies": "Philadelphia",
    "Pittsburgh Pirates": "Pittsburgh", "San Diego Padres": "San+Diego",
    "San Francisco Giants": "San+Francisco", "Seattle Mariners": "Seattle",
    "St. Louis Cardinals": "St+Louis", "Tampa Bay Rays": "Tampa",
    "Texas Rangers": "Fort+Worth", "Toronto Blue Jays": "Toronto",
    "Washington Nationals": "Washington",
}

# Wind directions (16-point) blowing OUT / IN at most parks (home-plate-south
# orientation): OUT toward center field, IN toward home plate.
_PARK_WIND_OUT = {"N", "NNE", "NE", "NNW", "NW"}
_PARK_WIND_IN = {"S", "SSE", "SE", "SSW", "SW"}

# Team timezone offset from ET (0=ET, -1=CT, -2=MT, -3=PT). Used by _factor_travel.
# AZ/Phoenix assigned by their effective summer offset where the sport is active.
_TEAM_TZ_OFFSET = {
    # MLB
    "Baltimore Orioles": 0, "Boston Red Sox": 0, "New York Yankees": 0,
    "New York Mets": 0, "Tampa Bay Rays": 0, "Toronto Blue Jays": 0,
    "Atlanta Braves": 0, "Miami Marlins": 0, "Philadelphia Phillies": 0,
    "Washington Nationals": 0, "Cleveland Guardians": 0, "Cincinnati Reds": 0,
    "Detroit Tigers": 0, "Pittsburgh Pirates": 0,
    "Chicago White Sox": -1, "Chicago Cubs": -1, "Kansas City Royals": -1,
    "Minnesota Twins": -1, "Milwaukee Brewers": -1, "St. Louis Cardinals": -1,
    "Houston Astros": -1, "Texas Rangers": -1,
    "Colorado Rockies": -2, "Arizona Diamondbacks": -3,
    "Los Angeles Dodgers": -3, "Los Angeles Angels": -3,
    "San Francisco Giants": -3, "San Diego Padres": -3,
    "Seattle Mariners": -3, "Oakland Athletics": -3, "Athletics": -3,
    # NBA
    "Boston Celtics": 0, "Brooklyn Nets": 0, "New York Knicks": 0,
    "Philadelphia 76ers": 0, "Toronto Raptors": 0, "Atlanta Hawks": 0,
    "Charlotte Hornets": 0, "Miami Heat": 0, "Orlando Magic": 0,
    "Washington Wizards": 0, "Cleveland Cavaliers": 0, "Detroit Pistons": 0,
    "Indiana Pacers": 0, "Chicago Bulls": -1, "Milwaukee Bucks": -1,
    "Minnesota Timberwolves": -1, "Oklahoma City Thunder": -1,
    "New Orleans Pelicans": -1, "Memphis Grizzlies": -1, "Houston Rockets": -1,
    "Dallas Mavericks": -1, "San Antonio Spurs": -1, "Denver Nuggets": -2,
    "Utah Jazz": -2, "Phoenix Suns": -2, "Golden State Warriors": -3,
    "Los Angeles Clippers": -3, "LA Clippers": -3, "Los Angeles Lakers": -3,
    "Sacramento Kings": -3, "Portland Trail Blazers": -3,
    # WNBA
    "Atlanta Dream": 0, "Connecticut Sun": 0, "Indiana Fever": 0,
    "New York Liberty": 0, "Washington Mystics": 0, "Chicago Sky": -1,
    "Dallas Wings": -1, "Minnesota Lynx": -1, "Golden State Valkyries": -3,
    "Las Vegas Aces": -3, "Los Angeles Sparks": -3, "Phoenix Mercury": -3,
    "Seattle Storm": -3, "Toronto Tempo": 0, "Portland Fire": -3,
}

# Team → division (MLB) / division (NBA) / conference (WNBA). Same group → "confirms".
_TEAM_DIVISION = {
    # MLB
    "Baltimore Orioles": "AL East", "Boston Red Sox": "AL East",
    "New York Yankees": "AL East", "Tampa Bay Rays": "AL East",
    "Toronto Blue Jays": "AL East",
    "Chicago White Sox": "AL Central", "Cleveland Guardians": "AL Central",
    "Detroit Tigers": "AL Central", "Kansas City Royals": "AL Central",
    "Minnesota Twins": "AL Central",
    "Houston Astros": "AL West", "Los Angeles Angels": "AL West",
    "Oakland Athletics": "AL West", "Athletics": "AL West",
    "Seattle Mariners": "AL West", "Texas Rangers": "AL West",
    "Atlanta Braves": "NL East", "Miami Marlins": "NL East",
    "New York Mets": "NL East", "Philadelphia Phillies": "NL East",
    "Washington Nationals": "NL East",
    "Chicago Cubs": "NL Central", "Cincinnati Reds": "NL Central",
    "Milwaukee Brewers": "NL Central", "Pittsburgh Pirates": "NL Central",
    "St. Louis Cardinals": "NL Central",
    "Arizona Diamondbacks": "NL West", "Colorado Rockies": "NL West",
    "Los Angeles Dodgers": "NL West", "San Diego Padres": "NL West",
    "San Francisco Giants": "NL West",
    # NBA
    "Boston Celtics": "Atlantic", "Brooklyn Nets": "Atlantic",
    "New York Knicks": "Atlantic", "Philadelphia 76ers": "Atlantic",
    "Toronto Raptors": "Atlantic",
    "Chicago Bulls": "Central", "Cleveland Cavaliers": "Central",
    "Detroit Pistons": "Central", "Indiana Pacers": "Central",
    "Milwaukee Bucks": "Central",
    "Atlanta Hawks": "Southeast", "Charlotte Hornets": "Southeast",
    "Miami Heat": "Southeast", "Orlando Magic": "Southeast",
    "Washington Wizards": "Southeast",
    "Denver Nuggets": "Northwest", "Minnesota Timberwolves": "Northwest",
    "Oklahoma City Thunder": "Northwest", "Portland Trail Blazers": "Northwest",
    "Utah Jazz": "Northwest",
    "Golden State Warriors": "Pacific", "Los Angeles Clippers": "Pacific",
    "LA Clippers": "Pacific", "Los Angeles Lakers": "Pacific",
    "Phoenix Suns": "Pacific", "Sacramento Kings": "Pacific",
    "Dallas Mavericks": "Southwest", "Houston Rockets": "Southwest",
    "Memphis Grizzlies": "Southwest", "New Orleans Pelicans": "Southwest",
    "San Antonio Spurs": "Southwest",
    # WNBA (conference)
    "Atlanta Dream": "WNBA-East", "Chicago Sky": "WNBA-East",
    "Connecticut Sun": "WNBA-East", "Indiana Fever": "WNBA-East",
    "New York Liberty": "WNBA-East", "Washington Mystics": "WNBA-East",
    "Dallas Wings": "WNBA-West", "Golden State Valkyries": "WNBA-West",
    "Las Vegas Aces": "WNBA-West", "Los Angeles Sparks": "WNBA-West",
    "Minnesota Lynx": "WNBA-West", "Phoenix Mercury": "WNBA-West",
    "Seattle Storm": "WNBA-West", "Toronto Tempo": "WNBA-East",
    "Portland Fire": "WNBA-West",
}

# ESPN / nba_api abbreviate team names where Odds API spells them out; these
# two-way-substring-miss against the full names. Canonicalize to the Odds-API
# full name before any name match or standings keying. The "LA " prefix rule
# generalizes Los Angeles teams (Clippers/Lakers/Sparks); the explicit map
# covers any non-LA quirks discovered later.
_TEAM_NAME_ALIASES = {
    "LA Clippers": "Los Angeles Clippers",
    "LA Lakers": "Los Angeles Lakers",
    "LA Sparks": "Los Angeles Sparks",
}


def _canon_team(name: str) -> str:
    """Map an ESPN/nba_api team name to its Odds-API full-name form."""
    n = (name or "").strip()
    if n in _TEAM_NAME_ALIASES:
        return _TEAM_NAME_ALIASES[n]
    if n.startswith("LA "):  # ESPN/nba_api use "LA" for "Los Angeles"
        return "Los Angeles " + n[3:]
    return n

# wttr.in / umpire cache HTTP UA (avoid bot blocks).
_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

_SEASON = "2026"
_MLB_LEAGUE_AVG_RPG = 9.0  # both teams combined, league avg
_UMP_CACHE_PATH = data_path("umpire_stats_cache.json")

# Module-level caches (one run): populated lazily, never re-fetched.
_MLB_SCHEDULE_CACHE: dict = {}
_STANDINGS_CACHE: dict = {}
_TEAM_SCHED_CACHE: dict = {}
_BOXSCORE_CACHE: dict = {}
_MLB_INJURIES_CACHE: dict = {}
_ESPN_SCOREBOARD_CACHE: dict = {}
_ESPN_SCHED_CACHE: dict = {}


# ── VERBATIM from context_research.py — aggregation, override, cache/merge ───────

def _split_game(game: str) -> tuple:
    """Split 'AWAY @ HOME' into (away, home). Defensive on malformed keys."""
    parts = [p.strip() for p in game.split("@")]
    away = parts[0] if parts else game
    home = parts[-1] if len(parts) > 1 else game
    return away, home


def _today_local() -> str:
    """Single source of 'today' — Denver local (matches game-day boundaries)."""
    return datetime.now(_LOCAL_TZ).strftime("%Y-%m-%d")


def _is_indoor(game: str, sport: str) -> bool:
    """True when weather cannot matter: indoor sports, or domed MLB home park."""
    if sport.upper() != "MLB":
        return True
    _, home = _split_game(game)
    return home in _DOMED_HOME_TEAMS


def _make_group_result(group_id: int, verdict: str, data_quality: str,
                       neutral_reason: str, summary: str = "") -> dict:
    """Uniform group result with every factor set to the same values."""
    return {
        "factors": {
            f: {
                "verdict": verdict,
                "data_quality": data_quality,
                "neutral_reason": neutral_reason,
                "evidence": "",
            }
            for f in _GROUPS[group_id]["factors"]
        },
        "summary": summary,
    }


def _hardcoded_group_result(group_id: int, reason: str) -> dict:
    return _make_group_result(group_id, "neutral", "fresh", reason)


def _failed_group_result(group_id: int) -> dict:
    return _make_group_result(group_id, "neutral", "failed", "source_failed")


def _apply_quality_override(factor_result: dict) -> dict:
    """Stale/failed data never drives a verdict — override to neutral and
    record why. Fresh neutrals get 'researched_neutral' unless a fast path
    already set a reason; non-neutral verdicts carry no neutral_reason."""
    out = dict(factor_result)
    quality = out.get("data_quality", "failed")
    if quality in ("stale", "failed"):
        out["verdict"] = "neutral"
        out["neutral_reason"] = "stale_data" if quality == "stale" else "source_failed"
    elif out.get("verdict") == "neutral":
        out["neutral_reason"] = out.get("neutral_reason") or "researched_neutral"
    else:
        out["neutral_reason"] = None
    return out


def aggregate_verdict(factors: dict) -> tuple:
    """Weighted aggregation of per-factor signals.

    Returns (verdict, confidence, weighted_confirms, weighted_fades).
    """
    wc = sum(_WEIGHTS.get(k, 1) for k, v in factors.items() if v == "confirms")
    wf = sum(_WEIGHTS.get(k, 1) for k, v in factors.items() if v == "fades")
    if wc - wf >= _VERDICT_THRESHOLD:
        verdict = "confirms"
    elif wf - wc >= _VERDICT_THRESHOLD:
        verdict = "fades"
    else:
        verdict = "neutral"
    confidence = round(max(wc, wf) / _MAX_POSSIBLE, 2) if factors else 0.0
    return verdict, confidence, wc, wf


def _compose_summary(group_results: dict) -> str:
    """Join the summaries of groups that produced a (post-override) signal,
    odds/roster first. No extra API call."""
    parts = []
    fallback = ""
    for gid in _GROUP_SUMMARY_PRIORITY:
        gres = group_results.get(gid)
        if not gres:
            continue
        summary = (gres.get("summary") or "").strip()
        if summary and not fallback:
            fallback = summary
        has_signal = any(
            fr.get("verdict") != "neutral" for fr in gres.get("factors", {}).values()
        )
        if has_signal and summary:
            parts.append(summary)
    joined = "; ".join(parts).strip()[:300]
    return joined or fallback[:300] or "No significant contextual signals."


def _assemble_game_verdict(game: str, sport: str, date_str: str,
                           group_results: dict) -> dict:
    """Flatten 5 group results into one schema-compatible verdict entry."""
    overridden = {}
    for gid in _GROUPS:
        gres = group_results.get(gid) or _failed_group_result(gid)
        overridden[gid] = {
            "factors": {
                f: _apply_quality_override(fr)
                for f, fr in gres.get("factors", {}).items()
            },
            "summary": gres.get("summary", ""),
        }

    factors, data_quality, neutral_reason = {}, {}, {}
    for gid, gres in overridden.items():
        for f, fr in gres["factors"].items():
            factors[f] = fr["verdict"]
            data_quality[f] = fr["data_quality"]
            neutral_reason[f] = fr["neutral_reason"]

    verdict, confidence, wc, wf = aggregate_verdict(factors)
    return {
        "game": game,
        "date": date_str,
        "sport": sport,
        "verdict": verdict,
        "confidence": confidence,
        "factors": factors,
        "summary": _compose_summary(overridden),
        "researched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "data_quality": data_quality,
        "neutral_reason": neutral_reason,
        "weighted_confirms": wc,
        "weighted_fades": wf,
    }


def _load_existing_verdicts(path: Path) -> list:
    """Load the current verdicts file; missing/corrupt → empty list."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError, ValueError):
        return []


def _split_cache(existing: list, today: str) -> dict:
    """Today's entries keyed by game string — the daily cache."""
    return {
        e["game"]: e
        for e in existing
        if isinstance(e, dict) and e.get("date") == today and e.get("game")
    }


def _partition_games(games: list, cache: dict, refresh: bool) -> tuple:
    """Split the slate into (to_research, cached_entries)."""
    to_research, cached = [], []
    for g in games:
        entry = None if refresh else cache.get(g["game"])
        if entry is not None:
            cached.append(entry)
        else:
            to_research.append(g)
    return to_research, cached


def _write_merged(new_entries: list, existing: list, path: Path, today: str) -> list:
    """Merge new entries into the file: keep today's entries not superseded
    by this run (other sports / earlier runs), prune prior-day entries."""
    new_keys = {e["game"] for e in new_entries}
    kept = [
        e for e in existing
        if isinstance(e, dict) and e.get("date") == today and e.get("game") not in new_keys
    ]
    merged = kept + new_entries
    atomic_write_json(path, merged)
    return merged


def _fetch_games_from_odds_api(sport: str, api_key: str) -> list:
    """Pull today's games from The Odds API. Returns list of game-key strings."""
    sport_key = _SPORT_KEYS.get(sport.upper())
    if not sport_key:
        logger.error(f"Unknown sport: {sport}. Valid: {list(_SPORT_KEYS)}")
        return []
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": "h2h",
        "oddsFormat": "american",
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        now_local = datetime.now(_LOCAL_TZ)
        today_local = now_local.date()

        games = []
        seen = set()
        for g in resp.json():
            away = g.get("away_team", "")
            home = g.get("home_team", "")
            commence_time = g.get("commence_time", "")
            if not (away and home):
                continue
            try:
                ct = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
                ct_local = ct.astimezone(_LOCAL_TZ)
            except Exception:
                ct_local = now_local

            game_key = f"{away} @ {home}"
            is_today = ct_local.date() == today_local
            not_started = ct_local > now_local
            if is_today and not_started and game_key not in seen:
                seen.add(game_key)
                games.append({"game": game_key, "sport": sport.upper()})

        logger.info(f"Fetched {len(games)} {sport} games from Odds API (today, not yet started)")
        return games
    except Exception as e:
        logger.error(f"Odds API fetch failed: {e}")
        return []


def _parse_games_from_csv(csv_path: str, sport: str) -> list:
    """Extract unique game matchups from a SaberSim CSV."""
    games_seen = set()
    results = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            col = next(
                (c for c in (reader.fieldnames or []) if c.strip().lower() in ("game", "matchup")),
                None,
            )
            if not col:
                logger.warning(f"No 'Game'/'Matchup' column in {csv_path}; use --odds-only instead")
                return []
            for row in reader:
                raw = (row.get(col) or "").strip()
                raw = re.sub(r"\s+\d{1,2}:\d{2}[AP]M.*", "", raw, flags=re.IGNORECASE).strip()
                raw = re.sub(r"\s*@\s*", " @ ", raw)
                if "@" not in raw or raw in games_seen:
                    continue
                games_seen.add(raw)
                results.append({"game": raw, "sport": sport.upper()})
    except OSError as e:
        logger.error(f"Cannot read CSV {csv_path}: {e}")
    logger.info(f"Found {len(results)} games from CSV {csv_path}")
    return results


# ── Factor dict builders (v2 canonical shape) ────────────────────────────────────

def _factor(verdict: str, data_quality: str, evidence: str = "",
            neutral_reason=None) -> dict:
    """Build a canonical factor dict. _apply_quality_override fills neutral_reason
    for stale/failed/fresh-neutral; we pass a starting hint for fast paths."""
    return {
        "verdict": verdict,
        "data_quality": data_quality,
        "neutral_reason": neutral_reason,
        "evidence": (evidence or "")[:120],
    }


def _na_factor() -> dict:
    """Factor not applicable for this sport/venue (e.g. pitching for non-MLB)."""
    return {"verdict": "neutral", "data_quality": "fresh",
            "neutral_reason": "not_applicable", "evidence": ""}


def _hardcoded_factor() -> dict:
    """Factor hardcoded neutral (e.g. domed-stadium weather)."""
    return {"verdict": "neutral", "data_quality": "fresh",
            "neutral_reason": "hardcoded_neutral", "evidence": ""}


def _failed_factor() -> dict:
    """Factor source failed — override forces neutral, records source_failed."""
    return {"verdict": "neutral", "data_quality": "failed",
            "neutral_reason": None, "evidence": ""}


# ── v2 assemble (flat factors) ───────────────────────────────────────────────────

def _assemble_game_verdict_v2(game, sport, date_str, factors_raw):
    """factors_raw: {factor_name: raw factor dict} (pre-override).
    Produces output identical in schema to _assemble_game_verdict()."""
    overridden = {f: _apply_quality_override(fr) for f, fr in factors_raw.items()}

    factors = {f: v["verdict"] for f, v in overridden.items()}
    data_quality = {f: v["data_quality"] for f, v in overridden.items()}
    neutral_reason = {f: v["neutral_reason"] for f, v in overridden.items()}

    verdict, confidence, wc, wf = aggregate_verdict(factors)

    # Summary: highest-weight non-neutral factor evidence, joined (top 3).
    non_neutral = [
        (overridden[f].get("evidence", ""), _WEIGHTS.get(f, 1))
        for f in _FACTORS
        if overridden.get(f, {}).get("verdict", "neutral") != "neutral"
        and overridden.get(f, {}).get("evidence", "").strip()
    ]
    non_neutral.sort(key=lambda x: x[1], reverse=True)
    summary_parts = [ev for ev, _ in non_neutral[:3]]
    summary = "; ".join(summary_parts).strip()[:300]
    if not summary:
        summary = "No significant contextual signals."

    return {
        "game": game,
        "date": date_str,
        "sport": sport,
        "verdict": verdict,
        "confidence": confidence,
        "factors": factors,
        "summary": summary,
        "researched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "data_quality": data_quality,
        "neutral_reason": neutral_reason,
        "weighted_confirms": wc,
        "weighted_fades": wf,
    }


# ── Low-level HTTP helper ─────────────────────────────────────────────────────────

def _get_json(url: str, params: dict | None = None, timeout: int = 12):
    """GET → parsed JSON, or None on any failure. Never raises."""
    try:
        resp = requests.get(url, params=params, headers=_HTTP_HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:  # noqa: BLE001
        logger.debug(f"GET failed {url}: {e}")
        return None


def _innings_to_float(ip) -> float:
    """Convert MLB innings-pitched string ('6.1','6.2') to outs-based float."""
    try:
        s = str(ip)
        if "." in s:
            whole, frac = s.split(".")
            return int(whole) + (int(frac) / 3.0)
        return float(s)
    except (ValueError, TypeError):
        return 0.0


# ── Odds-line snapshot / current totals ──────────────────────────────────────────

def _fetch_odds_json(sport_key: str, odds_key: str, markets: str) -> list:
    """Raw Odds API odds array for a sport. [] on failure."""
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
    data = _get_json(url, params={
        "apiKey": odds_key, "regions": "us",
        "markets": markets, "oddsFormat": "american",
    }, timeout=15)
    return data if isinstance(data, list) else []


def _extract_total(g: dict):
    """Median 'over' point across books for one game, or None."""
    points = []
    for bm in g.get("bookmakers", []):
        for m in bm.get("markets", []):
            if m.get("key") != "totals":
                continue
            for o in m.get("outcomes", []):
                if o.get("name", "").lower() == "over" and o.get("point") is not None:
                    points.append(float(o["point"]))
    if not points:
        return None
    points.sort()
    return points[len(points) // 2]


def _extract_ml(g: dict):
    """Median home/away moneyline across books → (home_ml, away_ml) or (None, None)."""
    home, away = g.get("home_team", ""), g.get("away_team", "")
    hp, ap = [], []
    for bm in g.get("bookmakers", []):
        for m in bm.get("markets", []):
            if m.get("key") != "h2h":
                continue
            for o in m.get("outcomes", []):
                if o.get("name") == home and o.get("price") is not None:
                    hp.append(int(o["price"]))
                elif o.get("name") == away and o.get("price") is not None:
                    ap.append(int(o["price"]))

    def _med(xs):
        if not xs:
            return None
        xs.sort()
        return xs[len(xs) // 2]
    return _med(hp), _med(ap)


def _prune_opening_files():
    """Delete context_opening_lines_*.json older than 3 days."""
    today = _date.fromisoformat(_today_local())
    try:
        for p in data_path("").glob("context_opening_lines_*.json"):
            m = re.search(r"(\d{4}-\d{2}-\d{2})", p.name)
            if not m:
                continue
            try:
                fdate = _date.fromisoformat(m.group(1))
            except ValueError:
                continue
            if (today - fdate).days > 3:
                p.unlink(missing_ok=True)
                logger.info(f"Pruned old opening-lines file {p.name}")
    except Exception as e:  # noqa: BLE001
        logger.debug(f"prune failed: {e}")


def _snapshot_opening_lines(sport_key: str, odds_key: str) -> dict:
    """Capture today's opening total/ML per game (once). Merges into the dated
    file so the FIRST observation of the day is preserved across sports/runs."""
    today = _today_local()
    path = data_path(f"context_opening_lines_{today}.json")
    snap = {}
    if path.exists():
        try:
            snap = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            snap = {}

    if not odds_key:
        return snap

    games = _fetch_odds_json(sport_key, odds_key, "h2h,totals")
    changed = False
    for g in games:
        away, home = g.get("away_team", ""), g.get("home_team", "")
        if not (away and home):
            continue
        key = f"{away} @ {home}"
        if key in snap:
            continue
        total = _extract_total(g)
        home_ml, away_ml = _extract_ml(g)
        snap[key] = {"total": total, "home_ml": home_ml, "away_ml": away_ml}
        changed = True

    if changed:
        atomic_write_json(path, snap)
    return snap


def _fetch_current_totals(sport_key: str, odds_key: str) -> dict:
    """{game: current median total} for today's slate."""
    if not odds_key:
        return {}
    out = {}
    for g in _fetch_odds_json(sport_key, odds_key, "totals"):
        away, home = g.get("away_team", ""), g.get("home_team", "")
        if away and home:
            out[f"{away} @ {home}"] = _extract_total(g)
    return out


# ── MLB schedule / standings / injuries fetchers ─────────────────────────────────

def _fetch_mlb_schedule_today(date_str: str) -> dict:
    """Today's MLB schedule with probable pitchers + officials. Cached per run."""
    if _MLB_SCHEDULE_CACHE.get(date_str) is not None:
        return _MLB_SCHEDULE_CACHE[date_str]
    url = "https://statsapi.mlb.com/api/v1/schedule"
    data = _get_json(url, params={
        "sportId": 1, "date": date_str,
        "hydrate": "probablePitcher,officials,team",
    }, timeout=12) or {}
    _MLB_SCHEDULE_CACHE[date_str] = data
    return data


def _iter_mlb_games(schedule: dict):
    for dblock in (schedule or {}).get("dates", []):
        for game in dblock.get("games", []):
            yield game


def _mlb_game_for(game_key: str, schedule: dict):
    """Find the schedule game whose home/away names match the 'AWAY @ HOME' key."""
    away, home = _split_game(game_key)
    for g in _iter_mlb_games(schedule):
        t = g.get("teams", {})
        gh = t.get("home", {}).get("team", {}).get("name", "")
        ga = t.get("away", {}).get("team", {}).get("name", "")
        if gh == home and ga == away:
            return g
    return None


def _fetch_standings(sport: str) -> dict:
    """{team_full_name: {wins, losses, rs, ra, last10_w, last10_l,
    home_w, home_l, away_w, away_l, pf, pa, wc_gb}}. Cached per sport."""
    sport = sport.upper()
    if sport in _STANDINGS_CACHE:
        return _STANDINGS_CACHE[sport]

    out: dict = {}
    try:
        if sport == "MLB":
            out = _standings_mlb()
        elif sport == "NBA":
            out = _standings_nba()
        elif sport == "WNBA":
            out = _standings_wnba()
        # NHL / others: no standings source wired → {} (factors degrade to stale)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"{sport} standings fetch failed: {e}")
        out = {}
    _STANDINGS_CACHE[sport] = out
    return out


def _standings_mlb() -> dict:
    data = _get_json(
        "https://statsapi.mlb.com/api/v1/standings",
        params={"leagueId": "103,104", "season": _SEASON,
                "standingsTypes": "regularSeason"}, timeout=12,
    )
    # The standings team object carries the short club name ("Yankees"), not the
    # Odds-API full name ("New York Yankees"). Key by team id → all full-name
    # aliases from _MLB_NAME_TO_ID so _standings_lookup(full_name) hits.
    id_to_names: dict = {}
    for nm, tid in _MLB_NAME_TO_ID.items():
        id_to_names.setdefault(tid, []).append(nm)

    out = {}
    for rec in (data or {}).get("records", []):
        for tr in rec.get("teamRecords", []):
            tid = tr.get("team", {}).get("id")
            names = id_to_names.get(tid) or [tr.get("team", {}).get("name", "")]
            entry = {
                "wins": tr.get("wins"), "losses": tr.get("losses"),
                "rs": tr.get("runsScored"), "ra": tr.get("runsAllowed"),
                "wc_gb": tr.get("wildCardGamesBack"),
                "last10_w": None, "last10_l": None,
                "home_w": None, "home_l": None,
                "away_w": None, "away_l": None,
            }
            for sr in tr.get("records", {}).get("splitRecords", []):
                typ = sr.get("type")
                if typ == "lastTen":
                    entry["last10_w"], entry["last10_l"] = sr.get("wins"), sr.get("losses")
                elif typ == "home":
                    entry["home_w"], entry["home_l"] = sr.get("wins"), sr.get("losses")
                elif typ == "away":
                    entry["away_w"], entry["away_l"] = sr.get("wins"), sr.get("losses")
            for nm in names:
                if nm:
                    out[nm] = entry
    return out


def _standings_nba() -> dict:
    try:
        from nba_api.stats.endpoints import leaguestandings
    except ImportError:
        logger.warning("nba_api not installed — NBA standings unavailable")
        return {}
    # Current NBA season spanning 2026 calendar = 2025-26.
    df = leaguestandings.LeagueStandings(season="2025-26").get_data_frames()[0]
    out = {}

    def _wl(s):
        try:
            w, l = str(s).split("-")
            return int(w), int(l)
        except (ValueError, AttributeError):
            return None, None

    for _, row in df.iterrows():
        name = _canon_team(f"{row.get('TeamCity', '')} {row.get('TeamName', '')}".strip())
        if not name:
            continue
        h_w, h_l = _wl(row.get("HOME"))
        a_w, a_l = _wl(row.get("ROAD"))
        l_w, l_l = _wl(row.get("L10"))
        out[name] = {
            "wins": row.get("WINS"), "losses": row.get("LOSSES"),
            "rs": None, "ra": None,
            "pf": row.get("PointsPG"), "pa": row.get("OppPointsPG"),
            "last10_w": l_w, "last10_l": l_l,
            "home_w": h_w, "home_l": h_l, "away_w": a_w, "away_l": a_l,
            "wc_gb": None,
        }
    return out


def _standings_wnba() -> dict:
    """Best-effort ESPN WNBA standings. {} on any parse failure."""
    data = _get_json(
        "https://site.api.espn.com/apis/v2/sports/basketball/wnba/standings",
        params={"season": _SEASON}, timeout=12,
    )
    if not data:
        return {}
    out = {}

    def _walk(node):
        if isinstance(node, dict):
            entries = node.get("standings", {}).get("entries")
            if isinstance(entries, list):
                for e in entries:
                    _parse_entry(e)
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for v in node:
                _walk(v)

    def _parse_entry(e):
        team = e.get("team", {})
        name = _canon_team(team.get("displayName") or team.get("name") or "")
        if not name:
            return
        stats = {s.get("name") or s.get("type"): s.get("value") for s in e.get("stats", [])}
        out[name] = {
            "wins": stats.get("wins"), "losses": stats.get("losses"),
            "rs": None, "ra": None,
            "pf": stats.get("avgPointsFor") or stats.get("pointsFor"),
            "pa": stats.get("avgPointsAgainst") or stats.get("pointsAgainst"),
            "last10_w": None, "last10_l": None,
            "home_w": None, "home_l": None, "away_w": None, "away_l": None,
            "wc_gb": None,
        }

    try:
        _walk(data)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"WNBA standings parse failed: {e}")
        return {}
    return out


def _standings_lookup(standings: dict, team_name: str):
    """Exact then case-insensitive lookup."""
    if not standings:
        return None
    if team_name in standings:
        return standings[team_name]
    low = team_name.lower()
    for k, v in standings.items():
        if k.lower() == low:
            return v
    return None


def _fetch_mlb_injuries() -> dict:
    """{team_id: [(player_name, status, recent_bool)]} from MLB IL endpoint."""
    if _MLB_INJURIES_CACHE:
        return _MLB_INJURIES_CACHE
    data = _get_json("https://statsapi.mlb.com/api/v1/injuries",
                     params={"sportId": 1}, timeout=12)
    out: dict = {}
    today = _date.fromisoformat(_today_local())
    for inj in (data or {}).get("roster", []) if isinstance(data, dict) else []:
        team_id = inj.get("team", {}).get("id") or inj.get("teamId")
        name = inj.get("person", {}).get("fullName") or inj.get("fullName", "")
        status = (inj.get("status") or inj.get("injuryStatus") or "").lower()
        recent = False
        for dk in ("date", "injuryDate", "updateDate"):
            ds = inj.get(dk)
            if ds:
                try:
                    d = datetime.fromisoformat(str(ds).replace("Z", "+00:00")).date()
                    if (today - d).days <= 3:
                        recent = True
                except (ValueError, TypeError):
                    pass
        if team_id and name:
            out.setdefault(team_id, []).append((name, status, recent))
    _MLB_INJURIES_CACHE.update(out)
    return out


# ── MLB team schedule / boxscore helpers (bullpen, rest, travel) ──────────────────

def _mlb_team_schedule(team_id: int, start: str, end: str) -> list:
    """Completed games for a team in [start, end], newest first.
    Each: {date, gamePk, is_home, home_id, away_id}."""
    ck = (team_id, start, end)
    if ck in _TEAM_SCHED_CACHE:
        return _TEAM_SCHED_CACHE[ck]
    data = _get_json("https://statsapi.mlb.com/api/v1/schedule", params={
        "sportId": 1, "teamId": team_id, "startDate": start, "endDate": end,
    }, timeout=12)
    games = []
    for g in _iter_mlb_games(data or {}):
        state = g.get("status", {}).get("abstractGameState", "")
        if state != "Final":
            continue
        t = g.get("teams", {})
        home_id = t.get("home", {}).get("team", {}).get("id")
        away_id = t.get("away", {}).get("team", {}).get("id")
        # officialDate is MLB's local calendar date for the game -- prefer it over
        # converting the UTC first pitch to machine-local time (a third dating
        # convention that shifts late games for anyone not in US-Central).
        od = g.get("officialDate")
        gd = g.get("gameDate", "")
        try:
            ldate = (_date.fromisoformat(od) if od else
                     datetime.fromisoformat(gd.replace("Z", "+00:00")).astimezone(_LOCAL_TZ).date())
        except Exception:
            continue
        games.append({
            "date": ldate, "gamePk": g.get("gamePk"),
            "is_home": home_id == team_id, "home_id": home_id, "away_id": away_id,
        })
    games.sort(key=lambda x: x["date"], reverse=True)
    _TEAM_SCHED_CACHE[ck] = games
    return games


def _mlb_boxscore(game_pk) -> dict:
    if game_pk in _BOXSCORE_CACHE:
        return _BOXSCORE_CACHE[game_pk]
    data = _get_json(f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore", timeout=12) or {}
    _BOXSCORE_CACHE[game_pk] = data
    return data


def _reliever_ip_last3(team_id: int) -> float | None:
    """Sum of reliever IP for a team over the last 3 days. None on failure."""
    today = _date.fromisoformat(_today_local())
    start = (today - timedelta(days=3)).isoformat()
    end = (today - timedelta(days=1)).isoformat()
    sched = _mlb_team_schedule(team_id, start, end)
    if not sched:
        return 0.0
    total_ip = 0.0
    seen_any = False
    for gm in sched:
        box = _mlb_boxscore(gm["gamePk"])
        side = "home" if gm["is_home"] else "away"
        tdata = box.get("teams", {}).get(side, {})
        pitchers = tdata.get("pitchers", [])
        players = tdata.get("players", {})
        if not pitchers:
            continue
        seen_any = True
        for pid in pitchers[1:]:  # skip starter (first in order)
            pstats = players.get(f"ID{pid}", {}).get("stats", {}).get("pitching", {})
            total_ip += _innings_to_float(pstats.get("inningsPitched", 0))
    return total_ip if seen_any else 0.0


# ── ESPN injuries (NBA / WNBA) ───────────────────────────────────────────────────

def _espn_path(sport: str) -> str | None:
    return {"NBA": "nba", "WNBA": "wnba"}.get(sport.upper())


def _espn_scoreboard(sport: str) -> dict:
    """Today's ESPN scoreboard for the sport, cached per run. {} if unsupported."""
    path = _espn_path(sport)
    if not path:
        return {}
    if path not in _ESPN_SCOREBOARD_CACHE:
        _ESPN_SCOREBOARD_CACHE[path] = _get_json(
            f"https://site.api.espn.com/apis/site/v2/sports/basketball/{path}/scoreboard",
            timeout=12) or {}
    return _ESPN_SCOREBOARD_CACHE[path]


def _name_match(a: str, b: str) -> bool:
    """Loose two-way substring match, after canonicalizing short-name variants
    (e.g. ESPN "LA Clippers" → "Los Angeles Clippers")."""
    a, b = _canon_team(a).lower(), _canon_team(b).lower()
    return bool(a) and bool(b) and (a in b or b in a)


def _espn_event_id(sport: str, home_name: str, away_name: str):
    sb = _espn_scoreboard(sport)
    if not sb:
        return None
    for ev in sb.get("events", []):
        comp = (ev.get("competitions") or [{}])[0]
        names = [c.get("team", {}).get("displayName", "") for c in comp.get("competitors", [])]
        if any(_name_match(home_name, n) for n in names) and \
           any(_name_match(away_name, n) for n in names):
            return ev.get("id")
    return None


def _espn_team_id(sport: str, team_name: str):
    """Numeric ESPN team id for a team playing today, from the cached scoreboard."""
    sb = _espn_scoreboard(sport)
    if not sb:
        return None
    for ev in sb.get("events", []):
        comp = (ev.get("competitions") or [{}])[0]
        for c in comp.get("competitors", []):
            team = c.get("team", {})
            if _name_match(team_name, team.get("displayName", "")):
                tid = team.get("id")
                return int(tid) if tid is not None else None
    return None


def _espn_team_recent_games(sport: str, team_id) -> list:
    """Completed games for an ESPN team, newest-first, before today.
    Each: {date, is_home, home_name, away_name}. [] on any failure."""
    path = _espn_path(sport)
    if not path or team_id is None:
        return []
    ck = (path, team_id)
    if ck in _ESPN_SCHED_CACHE:
        return _ESPN_SCHED_CACHE[ck]

    data = _get_json(
        f"https://site.api.espn.com/apis/site/v2/sports/basketball/{path}/teams/{team_id}/schedule",
        timeout=12) or {}
    today = _date.fromisoformat(_today_local())
    games = []
    for ev in data.get("events", []):
        comp = (ev.get("competitions") or [{}])[0]
        status = comp.get("status") or ev.get("status") or {}
        if not status.get("type", {}).get("completed"):
            continue
        try:
            ldate = datetime.fromisoformat(
                comp.get("date", ev.get("date", "")).replace("Z", "+00:00")
            ).astimezone(_LOCAL_TZ).date()
        except Exception:
            continue
        if ldate >= today:
            continue
        home_name = away_name = ""
        is_home = None
        for c in comp.get("competitors", []):
            nm = c.get("team", {}).get("displayName", "")
            ha = c.get("homeAway")
            if ha == "home":
                home_name = nm
            elif ha == "away":
                away_name = nm
            if _name_match_id(c, team_id):
                is_home = (ha == "home")
        games.append({"date": ldate, "is_home": is_home,
                      "home_name": home_name, "away_name": away_name})
    games.sort(key=lambda x: x["date"], reverse=True)
    _ESPN_SCHED_CACHE[ck] = games
    return games


def _name_match_id(competitor: dict, team_id) -> bool:
    tid = competitor.get("team", {}).get("id") or competitor.get("id")
    try:
        return tid is not None and int(tid) == int(team_id)
    except (ValueError, TypeError):
        return False


def _espn_injuries(sport: str, event_id) -> dict:
    """{team_displayName: [(athlete, status)]} from ESPN summary."""
    path = _espn_path(sport)
    if not path or not event_id:
        return {}
    data = _get_json(
        f"https://site.web.api.espn.com/apis/site/v2/sports/basketball/{path}/summary",
        params={"event": event_id}, timeout=12) or {}
    out = {}
    for blk in data.get("injuries", []):
        tname = blk.get("team", {}).get("displayName", "")
        rows = []
        for it in blk.get("injuries", []):
            ath = it.get("athlete", {}).get("displayName", "")
            status = (it.get("status") or it.get("type", {}).get("name", "") or "").lower()
            rows.append((ath, status))
        if tname:
            out[tname] = rows
    return out


# ── FACTOR IMPLEMENTATIONS ───────────────────────────────────────────────────────

def _factor_line_move(game: str, opening_snapshot: dict, current_odds: dict) -> dict:
    """Compare opening total to current total. >=1.0 move significant (MLB scale)."""
    try:
        opening = (opening_snapshot or {}).get(game, {}).get("total")
        current = (current_odds or {}).get(game)
        if opening is None or current is None:
            return _factor("neutral", "stale",
                           "No opening/current total snapshot available")
        delta = current - opening
        if abs(delta) < 0.5:
            return _factor("neutral", "fresh",
                           f"Total flat ({opening}→{current})", "researched_neutral")
        if delta >= 1.0:
            return _factor("confirms", "fresh",
                           f"Total moved {opening}->{current} (rising — sharp over action)")
        if delta <= -1.0:
            return _factor("fades", "fresh",
                           f"Total moved {opening}->{current} (falling — sharp under action)")
        # 0.5 <= |delta| < 1.0 → minor move, neutral
        return _factor("neutral", "fresh",
                       f"Minor total move {opening}->{current}", "researched_neutral")
    except Exception:  # noqa: BLE001
        return _failed_factor()


def _factor_injury(game: str, sport: str, mlb_schedule: dict) -> dict:
    """Key player OUT and not yet priced in. Home out → fades; away out → confirms."""
    try:
        away, home = _split_game(game)
        sport = sport.upper()
        if sport == "MLB":
            inj = _fetch_mlb_injuries()
            if not inj:
                return _factor("neutral", "stale", "MLB injury endpoint unavailable")
            home_id, away_id = _MLB_NAME_TO_ID.get(home), _MLB_NAME_TO_ID.get(away)
            # Only count *recent* IL additions — the full IL list is always
            # populated and is already priced in.
            home_recent = [n for (n, s, r) in inj.get(home_id, []) if r]
            away_recent = [n for (n, s, r) in inj.get(away_id, []) if r]
            if home_recent and not away_recent:
                return _factor("fades", "stale",
                               f"{home_recent[0]} newly IL — home weakened")
            if away_recent and not home_recent:
                return _factor("confirms", "stale",
                               f"{away_recent[0]} newly IL — home advantage amplified")
            return _factor("neutral", "fresh", "No recent IL additions",
                           "researched_neutral")

        if sport in ("NBA", "WNBA"):
            eid = _espn_event_id(sport, home, away)
            if not eid:
                return _factor("neutral", "stale", "ESPN event not found")
            inj = _espn_injuries(sport, eid)
            if not inj:
                return _factor("neutral", "fresh", "No injuries reported",
                               "researched_neutral")

            def _outs(team_name):
                for tname, rows in inj.items():
                    if team_name.lower() in tname.lower() or tname.lower() in team_name.lower():
                        return [a for (a, s) in rows if "out" in s]
                return []
            home_out, away_out = _outs(home), _outs(away)
            if home_out and not away_out:
                return _factor("fades", "fresh",
                               f"{home_out[0]} (Out) — key home player missing")
            if away_out and not home_out:
                return _factor("confirms", "fresh",
                               f"{away_out[0]} (Out) — home advantage amplified")
            return _factor("neutral", "fresh", "No decisive injury edge",
                           "researched_neutral")

        return _na_factor()
    except Exception:  # noqa: BLE001
        return _failed_factor()


def _factor_rlm() -> dict:
    """Reverse line movement — needs Action Network public %. Stale until keyed."""
    if os.environ.get("ACTION_NETWORK_PRO_KEY"):
        # Hook point: fetch public %, compute RLM. Not implemented (no key in env).
        pass
    return {"verdict": "neutral", "data_quality": "stale",
            "neutral_reason": "stale_data",
            "evidence": "Public betting % unavailable (ACTION_NETWORK_PRO_KEY not set)"}


def _factor_public_sharp() -> dict:
    """Public-money fade — needs Action Network public %. Stale until keyed."""
    return {"verdict": "neutral", "data_quality": "stale",
            "neutral_reason": "stale_data",
            "evidence": "Public betting % unavailable (ACTION_NETWORK_PRO_KEY not set)"}


def _pitcher_season_stats(pid):
    """{era, ip, bb, so, hr} for a pitcher's 2026 season, or None."""
    data = _get_json(f"https://statsapi.mlb.com/api/v1/people/{pid}/stats",
                     params={"stats": "season", "group": "pitching",
                             "season": _SEASON}, timeout=12)
    try:
        splits = data["stats"][0]["splits"]
        if not splits:
            return None
        s = splits[0]["stat"]
        return {
            "era": float(s.get("era", 0) or 0),
            "ip": _innings_to_float(s.get("inningsPitched", 0)),
            "bb": float(s.get("baseOnBalls", 0) or 0),
            "so": float(s.get("strikeOuts", 0) or 0),
            "hr": float(s.get("homeRuns", 0) or 0),
        }
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _factor_era_fip(game: str, sport: str, mlb_schedule: dict) -> dict:
    """ERA-FIP regression: lucky pitcher (FIP>ERA) → more runs coming → confirms."""
    try:
        if sport.upper() != "MLB":
            return _na_factor()
        g = _mlb_game_for(game, mlb_schedule)
        if not g:
            return _factor("neutral", "stale", "Game not in MLB schedule")
        t = g.get("teams", {})
        home_pid = t.get("home", {}).get("probablePitcher", {}).get("id")
        away_pid = t.get("away", {}).get("probablePitcher", {}).get("id")
        if not home_pid or not away_pid:
            return _factor("neutral", "stale", "Probable pitcher(s) unconfirmed")

        def _signal(pid):
            st = _pitcher_season_stats(pid)
            if not st or st["ip"] <= 0:
                return None, None, None
            fip = (13 * st["hr"] + 3 * st["bb"] - 2 * st["so"]) / st["ip"] + 3.10
            gap = fip - st["era"]
            if gap >= 1.0:
                return "confirms", fip, st["era"]   # lucky → regression → more runs
            if gap <= -1.0:
                return "fades", fip, st["era"]       # unlucky → improvement → fewer runs
            return "neutral", fip, st["era"]

        hp_sig, hp_fip, hp_era = _signal(home_pid)
        ap_sig, ap_fip, ap_era = _signal(away_pid)
        if hp_sig is None or ap_sig is None:
            return _failed_factor()

        confirms = sum(1 for s in (hp_sig, ap_sig) if s == "confirms")
        fades = sum(1 for s in (hp_sig, ap_sig) if s == "fades")
        if confirms and not fades:
            verdict = "confirms"
        elif fades and not confirms:
            verdict = "fades"
        else:
            verdict = "neutral"

        ev = (f"Pitchers FIP/ERA — home {hp_fip:.1f}/{hp_era:.1f}, "
              f"away {ap_fip:.1f}/{ap_era:.1f}")
        return _factor(verdict, "fresh", ev,
                       "researched_neutral" if verdict == "neutral" else None)
    except Exception:  # noqa: BLE001
        return _failed_factor()


def _factor_bullpen(game: str, sport: str) -> dict:
    """Tired bullpen (>=8 reliever IP / last 3 days) → more runs allowed → confirms."""
    try:
        if sport.upper() != "MLB":
            return _na_factor()
        away, home = _split_game(game)
        home_id, away_id = _MLB_NAME_TO_ID.get(home), _MLB_NAME_TO_ID.get(away)
        if not home_id or not away_id:
            return _factor("neutral", "stale", "Team id unmapped for bullpen")
        h_ip = _reliever_ip_last3(home_id)
        a_ip = _reliever_ip_last3(away_id)
        if h_ip is None or a_ip is None:
            return _failed_factor()
        ev = f"Home bullpen: {h_ip:.1f} IP last 3 days | Away: {a_ip:.1f} IP"
        if h_ip >= 8 or a_ip >= 8:
            return _factor("confirms", "fresh", ev)
        return _factor("neutral", "fresh", ev, "researched_neutral")
    except Exception:  # noqa: BLE001
        return _failed_factor()


def _factor_motivation(game: str, sport: str, standings: dict) -> dict:
    """Elimination / wildcard race pressure. Pre-Aug 1 → not applicable."""
    try:
        month = int(_today_local()[5:7])
        if month < 8:
            return _factor("neutral", "fresh",
                           "Regular season, no elimination pressure", "not_applicable")
        away, home = _split_game(game)
        if not standings:
            return _factor("neutral", "stale", "Standings unavailable for motivation")
        h = _standings_lookup(standings, home)
        a = _standings_lookup(standings, away)

        def _in_race(rec):
            gb = rec.get("wc_gb") if rec else None
            if gb in (None, "-", "+"):
                return False
            try:
                return abs(float(str(gb).replace("+", ""))) <= 3.0
            except (ValueError, TypeError):
                return False
        if _in_race(h) or _in_race(a):
            return _factor("confirms", "fresh", "Team(s) within 3 GB of wildcard cutoff")
        return _factor("neutral", "fresh", "No elimination pressure", "researched_neutral")
    except Exception:  # noqa: BLE001
        return _failed_factor()


def _factor_weather(game: str, sport: str) -> dict:
    """Outdoor MLB only: wind out → confirms, wind in/precip → fades, heat → mild confirms."""
    try:
        if sport.upper() != "MLB":
            return _na_factor()
        if _is_indoor(game, sport):
            return _hardcoded_factor()
        _, home = _split_game(game)
        city = _STADIUM_CITIES.get(home)
        if not city:
            return _factor("neutral", "stale", "No stadium city mapping")
        data = _get_json(f"https://wttr.in/{city}", params={"format": "j1"}, timeout=8)
        if not data:
            return _failed_factor()
        cur = (data.get("current_condition") or [{}])[0]
        try:
            temp_f = int(cur.get("temp_F") or cur.get("FeelsLikeF") or 0)
        except (ValueError, TypeError):
            temp_f = 0
        try:
            wind_kmph = int(cur.get("windspeedKmph") or 0)
        except (ValueError, TypeError):
            wind_kmph = 0
        wdir = cur.get("winddir16Point", "")
        try:
            precip = float(cur.get("precipMM") or 0)
        except (ValueError, TypeError):
            precip = 0.0

        if precip >= 2.0:
            return _factor("fades", "fresh",
                           f"{temp_f}F, precip {precip}mm — rain suppresses scoring ({city})")
        if wind_kmph >= 16 and wdir in _PARK_WIND_OUT:
            return _factor("confirms", "fresh",
                           f"{temp_f}F, {wind_kmph}km/h {wdir} wind (blowing out) — {city}")
        if wind_kmph >= 16 and wdir in _PARK_WIND_IN:
            return _factor("fades", "fresh",
                           f"{temp_f}F, {wind_kmph}km/h {wdir} wind (blowing in) — {city}")
        if temp_f >= 90:
            return _factor("confirms", "fresh",
                           f"{temp_f}F heat (offense +~3%) — {city}")
        return _factor("neutral", "fresh",
                       f"{temp_f}F, {wind_kmph}km/h {wdir} — neutral ({city})",
                       "researched_neutral")
    except Exception:  # noqa: BLE001
        return _failed_factor()


def _load_ump_cache() -> dict:
    try:
        return json.loads(Path(_UMP_CACHE_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _save_ump_cache(cache: dict):
    try:
        atomic_write_json(_UMP_CACHE_PATH, cache)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"ump cache save failed: {e}")


def _fetch_ump_stats(name: str):
    """Best-effort umpire run-environment fetch. None if unavailable.
    Tries umpscorecards JSON, falls back to bs4 HTML scrape if installed."""
    api = _get_json("https://umpscorecards.com/api/umpires/", timeout=10)
    if isinstance(api, list):
        for u in api:
            if str(u.get("name", "")).lower() == name.lower():
                rpg = u.get("runs_per_game") or u.get("runsPerGame")
                if rpg is not None:
                    return {"runs_per_game": float(rpg),
                            "k_per_game": u.get("k_per_game")}
    # HTML scrape fallback (only if bs4 available — never hard-fails the run)
    try:
        from bs4 import BeautifulSoup  # noqa: F401
        # Site HTML layout is volatile; we intentionally do not guess a brittle
        # selector here. Return None so the factor degrades to stale neutral.
        return None
    except ImportError:
        return None


def _factor_umpire(game: str, sport: str, mlb_schedule: dict) -> dict:
    """Home-plate umpire run environment vs 9.0 R/G league avg (±0.4 threshold)."""
    try:
        if sport.upper() != "MLB":
            return _na_factor()
        g = _mlb_game_for(game, mlb_schedule)
        if not g:
            return _factor("neutral", "stale", "Game not in MLB schedule")
        ump = ""
        for off in g.get("officials", []):
            if off.get("officialType") == "Home Plate":
                ump = off.get("official", {}).get("fullName", "")
                break
        if not ump:
            return _factor("neutral", "stale", "Home plate umpire not announced")

        cache = _load_ump_cache()
        rec = cache.get(ump)
        today = _today_local()
        fresh = False
        if rec:
            try:
                age = (_date.fromisoformat(today) - _date.fromisoformat(rec.get("updated", "2000-01-01"))).days
                fresh = age <= 7
            except ValueError:
                fresh = False
        if not fresh:
            stats = _fetch_ump_stats(ump)
            if stats:
                rec = {"runs_per_game": stats["runs_per_game"],
                       "k_per_game": stats.get("k_per_game"), "updated": today}
                cache[ump] = rec
                _save_ump_cache(cache)
                fresh = True
        if not rec or rec.get("runs_per_game") is None:
            return _factor("neutral", "stale", f"Ump {ump} — run stats unavailable")

        rpg = float(rec["runs_per_game"])
        quality = "fresh" if fresh else "stale"
        if rpg >= _MLB_LEAGUE_AVG_RPG + 0.4:
            return _factor("confirms", quality, f"Ump {ump}: {rpg:.1f} R/G (high-scoring env)")
        if rpg <= _MLB_LEAGUE_AVG_RPG - 0.4:
            return _factor("fades", quality, f"Ump {ump}: {rpg:.1f} R/G (run-suppressing)")
        return _factor("neutral", quality, f"Ump {ump}: {rpg:.1f} R/G (avg)", "researched_neutral")
    except Exception:  # noqa: BLE001
        return _failed_factor()


def _pythag_pct(rs, ra, exp=2.0):
    try:
        rs, ra = float(rs), float(ra)
        if rs <= 0 and ra <= 0:
            return None
        return rs ** exp / (rs ** exp + ra ** exp)
    except (ValueError, TypeError, ZeroDivisionError):
        return None


def _actual_pct(rec):
    try:
        w, l = float(rec.get("wins")), float(rec.get("losses"))
        if w + l <= 0:
            return None
        return w / (w + l)
    except (ValueError, TypeError):
        return None


def _factor_pythag(game: str, sport: str, standings: dict) -> dict:
    """Net pythag-minus-actual; home due to improve → confirms (threshold 0.057)."""
    try:
        away, home = _split_game(game)
        if not standings:
            return _factor("neutral", "stale", "Standings unavailable for pythag")
        h, a = _standings_lookup(standings, home), _standings_lookup(standings, away)
        if not h or not a:
            return _factor("neutral", "stale", "Team standings not found")

        is_nba = sport.upper() in ("NBA", "WNBA")
        exp = 16.5 if is_nba else 2.0
        if is_nba:
            h_py = _pythag_pct(h.get("pf"), h.get("pa"), exp)
            a_py = _pythag_pct(a.get("pf"), a.get("pa"), exp)
        else:
            h_py = _pythag_pct(h.get("rs"), h.get("ra"), exp)
            a_py = _pythag_pct(a.get("rs"), a.get("ra"), exp)
        h_act, a_act = _actual_pct(h), _actual_pct(a)
        if None in (h_py, a_py, h_act, a_act):
            return _factor("neutral", "stale", "Incomplete RS/RA or W/L data")

        net = (h_py - h_act) - (a_py - a_act)
        ev = f"Pythag-actual: home {h_py - h_act:+.3f}, away {a_py - a_act:+.3f}"
        if net > 0.057:
            return _factor("confirms", "fresh", ev + " (home due to improve)")
        if net < -0.057:
            return _factor("fades", "fresh", ev + " (home due to regress)")
        return _factor("neutral", "fresh", ev, "researched_neutral")
    except Exception:  # noqa: BLE001
        return _failed_factor()


def _factor_form(game: str, sport: str, standings: dict) -> dict:
    """Last-10 vs season win% (±0.15). Home hot / away cold → confirms."""
    try:
        away, home = _split_game(game)
        if not standings:
            return _factor("neutral", "stale", "Standings unavailable for form")
        h, a = _standings_lookup(standings, home), _standings_lookup(standings, away)

        def _hotcold(rec):
            if not rec or rec.get("last10_w") is None:
                return None
            l10 = rec["last10_w"] / 10.0
            season = _actual_pct(rec)
            if season is None:
                return None
            d = l10 - season
            if d > 0.15:
                return "hot"
            if d < -0.15:
                return "cold"
            return "even"
        hs, as_ = _hotcold(h), _hotcold(a)
        if hs is None or as_ is None:
            return _factor("neutral", "stale", "Last-10 record unavailable")

        ev = f"Home form {hs}, away form {as_}"
        if hs == "hot" and as_ != "hot":
            return _factor("confirms", "fresh", ev + " (home hot)")
        if hs == "cold" and as_ != "cold":
            return _factor("fades", "fresh", ev + " (home cold)")
        if as_ == "hot" and hs != "hot":
            return _factor("fades", "fresh", ev + " (away hot)")
        if as_ == "cold" and hs != "cold":
            return _factor("confirms", "fresh", ev + " (away cold)")
        return _factor("neutral", "fresh", ev, "researched_neutral")
    except Exception:  # noqa: BLE001
        return _failed_factor()


def _factor_home_away(game: str, sport: str, standings: dict) -> dict:
    """Home team strong at home (>0.55) + away team weak on road (<0.45) → confirms."""
    try:
        away, home = _split_game(game)
        if not standings:
            return _factor("neutral", "stale", "Standings unavailable for home/away")
        h, a = _standings_lookup(standings, home), _standings_lookup(standings, away)

        def _pct(w, l):
            try:
                w, l = float(w), float(l)
                return w / (w + l) if (w + l) > 0 else None
            except (ValueError, TypeError):
                return None
        h_home = _pct(h.get("home_w"), h.get("home_l")) if h else None
        a_away = _pct(a.get("away_w"), a.get("away_l")) if a else None
        if h_home is None or a_away is None:
            return _factor("neutral", "stale", "Home/road split unavailable")

        ev = f"Home W% at home {h_home:.2f} | Away W% on road {a_away:.2f}"
        if h_home > 0.55 and a_away < 0.45:
            return _factor("confirms", "fresh", ev)
        if h_home < 0.45 and a_away > 0.55:
            return _factor("fades", "fresh", ev)
        return _factor("neutral", "fresh", ev, "researched_neutral")
    except Exception:  # noqa: BLE001
        return _failed_factor()


def _factor_rest(game: str, sport: str) -> dict:
    """Back-to-back vs 2+ days rest. Home rested + away B2B → confirms.

    gap = calendar days since last completed game. B2B = gap==1 (played
    yesterday); rested = gap>=2. (The prior MLB code tested gap==0 for B2B, which
    is unreachable: the schedule window ends yesterday, so the minimum gap is 1.)
    Wired for MLB (MLB Stats API) and NBA/WNBA (ESPN team schedule).
    """
    try:
        away, home = _split_game(game)
        sport = sport.upper()
        today = _date.fromisoformat(_today_local())

        if sport == "MLB":
            home_id, away_id = _MLB_NAME_TO_ID.get(home), _MLB_NAME_TO_ID.get(away)
            if not home_id or not away_id:
                return _factor("neutral", "stale", "Team id unmapped for rest")
            start = (today - timedelta(days=7)).isoformat()
            end = (today - timedelta(days=1)).isoformat()

            def _gap(tid):
                sched = _mlb_team_schedule(tid, start, end)
                return (today - sched[0]["date"]).days if sched else None
            h_gap, a_gap = _gap(home_id), _gap(away_id)

        elif sport in ("NBA", "WNBA"):
            home_id, away_id = _espn_team_id(sport, home), _espn_team_id(sport, away)
            if home_id is None or away_id is None:
                return _factor("neutral", "stale", "ESPN team id not found for rest")

            def _gap(tid):
                sched = _espn_team_recent_games(sport, tid)
                return (today - sched[0]["date"]).days if sched else None
            h_gap, a_gap = _gap(home_id), _gap(away_id)

        else:
            return _factor("neutral", "stale", "Rest source not wired for this sport")

        if h_gap is None or a_gap is None:
            return _factor("neutral", "stale", "Recent schedule unavailable")

        ev = f"Home: {h_gap}d since last | Away: {a_gap}d since last"
        if h_gap >= 2 and a_gap == 1:
            return _factor("confirms", "fresh", ev + " (home rest edge — away B2B)")
        if a_gap >= 2 and h_gap == 1:
            return _factor("fades", "fresh", ev + " (away rest edge — home B2B)")
        return _factor("neutral", "fresh", ev, "researched_neutral")
    except Exception:  # noqa: BLE001
        return _failed_factor()


def _factor_travel(game: str, sport: str) -> dict:
    """Eastward timezone shift >=2h for the away team → circadian disadvantage → fades.

    NOTE: the original prompt's '<=-2' condition contradicts its own worked
    example (PT->ET = +3 eastward = fades). We follow the worked example and the
    circadian literature: eastward (positive) shift of 2+ hours fades the away team.
    Wired for MLB (MLB Stats API) and NBA/WNBA (ESPN team schedule).
    """
    try:
        away, home = _split_game(game)
        sport = sport.upper()
        today_off = _TEAM_TZ_OFFSET.get(home)
        if today_off is None:
            return _factor("neutral", "stale", "Tonight's venue timezone unknown")
        today = _date.fromisoformat(_today_local())

        if sport == "MLB":
            away_id = _MLB_NAME_TO_ID.get(away)
            if away_id is None:
                return _factor("neutral", "stale", "Team id unmapped for travel")
            start = (today - timedelta(days=3)).isoformat()
            end = (today - timedelta(days=1)).isoformat()
            sched = _mlb_team_schedule(away_id, start, end)
            if not sched:
                return _factor("neutral", "stale", "Away team's last game not found")
            # Venue tz of away team's previous game = tz of that game's home team.
            venue_id = sched[0]["home_id"]
            venue_name = next((n for n, i in _MLB_NAME_TO_ID.items() if i == venue_id), None)

        elif sport in ("NBA", "WNBA"):
            away_id = _espn_team_id(sport, away)
            if away_id is None:
                return _factor("neutral", "stale", "ESPN team id not found for travel")
            sched = _espn_team_recent_games(sport, away_id)
            if not sched:
                return _factor("neutral", "stale", "Away team's last game not found")
            venue_name = sched[0]["home_name"]

        else:
            return _factor("neutral", "stale", "Travel source not wired for this sport")

        venue_off = _TEAM_TZ_OFFSET.get(venue_name)
        if venue_off is None:
            return _factor("neutral", "stale", "Previous venue timezone unknown")

        eastward_shift = today_off - venue_off  # +ve = moved east
        if eastward_shift >= 2:
            return _factor("fades", "fresh",
                           f"{away} traveled {-venue_off}->{-today_off}h "
                           f"({eastward_shift}h eastward — circadian disadvantage)")
        return _factor("neutral", "fresh",
                       f"{away} tz shift {eastward_shift}h (no disadvantage)",
                       "researched_neutral")
    except Exception:  # noqa: BLE001
        return _failed_factor()


def _factor_division(game: str, sport: str) -> dict:
    """Same division/conference → familiarity signal → confirms."""
    try:
        away, home = _split_game(game)
        h_div, a_div = _TEAM_DIVISION.get(home), _TEAM_DIVISION.get(away)
        if not h_div or not a_div:
            return _factor("neutral", "fresh", "Division mapping unavailable",
                           "researched_neutral")
        if h_div == a_div:
            return _factor("confirms", "fresh", f"Divisional matchup ({h_div}) — familiarity")
        return _factor("neutral", "fresh", "Non-divisional matchup", "researched_neutral")
    except Exception:  # noqa: BLE001
        return _failed_factor()


# ── Main research flow ────────────────────────────────────────────────────────────

def research_game_v2(game, sport, date_str, opening_snapshot,
                     current_odds, mlb_schedule, standings):
    """Compute all 15 factors from free APIs and assemble the verdict."""
    factors_raw = {
        "line_move":    _factor_line_move(game, opening_snapshot, current_odds),
        "injury":       _factor_injury(game, sport, mlb_schedule),
        "rlm":          _factor_rlm(),
        "era_fip":      _factor_era_fip(game, sport, mlb_schedule),
        "bullpen":      _factor_bullpen(game, sport),
        "public_sharp": _factor_public_sharp(),
        "motivation":   _factor_motivation(game, sport, standings),
        "weather":      _factor_weather(game, sport),
        "umpire":       _factor_umpire(game, sport, mlb_schedule),
        "pythag":       _factor_pythag(game, sport, standings),
        "form":         _factor_form(game, sport, standings),
        "rest":         _factor_rest(game, sport),
        "home_away":    _factor_home_away(game, sport, standings),
        "travel":       _factor_travel(game, sport),
        "division":     _factor_division(game, sport),
    }
    return _assemble_game_verdict_v2(game, sport, date_str, factors_raw)


# ── Main ──────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Per-game contextual research via free public APIs (v2)")
    parser.add_argument("csv", nargs="?", help="SaberSim CSV path (optional)")
    parser.add_argument("--sport", default="NBA",
                        help="Sport: NBA, MLB, NHL, WNBA, or ALL (default: NBA)")
    parser.add_argument("--odds-only", action="store_true",
                        help="Use Odds API for game list (ignores CSV)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print games without calling factor APIs")
    parser.add_argument("--refresh", action="store_true",
                        help="Re-research games even if already cached for today")
    args = parser.parse_args()

    sport = args.sport.upper()
    if sport == "ALL" and args.csv and not args.odds_only:
        sys.exit("--sport ALL uses the Odds API for every sport; a CSV game list cannot be combined with it.")

    odds_key = os.environ.get("ODDS_API_KEY", "")

    # Build game list
    if sport == "ALL":
        if not odds_key:
            sys.exit("ODDS_API_KEY not set. Add it to .env.")
        sports_to_run = list(_ALL_SPORTS)
        games = []
        for s in sports_to_run:
            games.extend(_fetch_games_from_odds_api(s, odds_key))
    elif args.odds_only or not args.csv:
        if not odds_key:
            sys.exit("ODDS_API_KEY not set. Add it to .env.")
        sports_to_run = [sport]
        games = _fetch_games_from_odds_api(sport, odds_key)
    else:
        sports_to_run = [sport]
        games = _parse_games_from_csv(args.csv, sport)

    if not games:
        print("No games found — nothing to research.")
        return

    today = _today_local()
    existing = _load_existing_verdicts(_OUT_PATH)
    cache = _split_cache(existing, today)
    to_research, cached_entries = _partition_games(games, cache, args.refresh)

    if cached_entries:
        print(f"{len(cached_entries)} game(s) already researched today (cache hit — use --refresh to force):")
        for e in cached_entries:
            print(f"  {e['game']}: {e.get('verdict', '?')} (cached)")

    if args.dry_run:
        print(f"Would research {len(to_research)} game(s):")
        for g in to_research:
            print(f"  {g['game']} [{g['sport']}]")
        return

    if not to_research:
        _write_merged([], existing, _OUT_PATH, today)
        print(f"\nNothing new to research. {_OUT_PATH} pruned to today's {len(cache)} entr(ies).")
        return

    # ── Startup: opening-line snapshot, current totals, schedule, standings ──
    _prune_opening_files()
    opening_snapshot, current_odds, standings_by_sport = {}, {}, {}
    sports_in_slate = {g["sport"] for g in to_research}
    for s in sports_in_slate:
        skey = _SPORT_KEYS.get(s)
        if skey and odds_key:
            opening_snapshot.update(_snapshot_opening_lines(skey, odds_key))
            current_odds.update(_fetch_current_totals(skey, odds_key))
        standings_by_sport[s] = _fetch_standings(s)
    mlb_schedule = _fetch_mlb_schedule_today(today) if "MLB" in sports_in_slate else {}

    print(f"Researching {len(to_research)} game(s) via free APIs (15 factors/game)...")
    new_entries = []
    for i, g in enumerate(to_research, 1):
        s = g["sport"]
        entry = research_game_v2(
            g["game"], s, today, opening_snapshot, current_odds,
            mlb_schedule, standings_by_sport.get(s, {}),
        )
        new_entries.append(entry)
        print(
            f"  [{i}/{len(to_research)}] {entry['game']}: {entry['verdict']} "
            f"({entry['confidence']:.0%}) [wc={entry['weighted_confirms']} "
            f"wf={entry['weighted_fades']}]", flush=True,
        )

    merged = _write_merged(new_entries, existing, _OUT_PATH, today)
    print(f"\nWrote {len(new_entries)} new verdict(s) ({len(merged)} total for today) to {_OUT_PATH}")


if __name__ == "__main__":
    main()
