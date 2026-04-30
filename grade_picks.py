#!/usr/bin/env python3
"""
grade_picks.py — Auto-grade pick_log.csv results
Fetches final scores (The Odds API) and player stats (public APIs)
to fill in the 'result' column with W/L/P (Push).

Usage:
    python grade_picks.py                  # Grade all ungraded picks
    python grade_picks.py --date 2026-04-03  # Grade specific date only
    python grade_picks.py --dry-run        # Show what would be graded without writing
"""

import csv, json, os, sys, time, argparse, logging, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict

# filelock is a hard dependency (audit C-1). A missing lock re-opens the race
# conditions Section 2 (fsync) and Section 3 (Discord guard) closed.
try:
    from filelock import FileLock, Timeout as FileLockTimeout
except ImportError as e:
    raise ImportError(
        "filelock is required for pick_log/Discord-guard safety. "
        "Install it: pip install filelock --break-system-packages"
    ) from e

# Canonical locked-reader helper lives in pick_log_io.py and is used by every
# other reader of pick_log (analyze_picks, clv_report, weekly_recap,
# morning_preview, results_graphic). Grade_picks.py keeps a local wrapper
# (_read_rows_locked below) with the same semantics so fall-through warnings
# route through the grader's file logger. Audit H-8 / M-series, closed Apr 20 2026.
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo
try:
    import requests
except ImportError:
    print("  pip install requests --break-system-packages")
    sys.exit(1)

# Canonical player-name folding (audit H-3). Before this import, grade_picks
# used a local _norm that did NOT strip accents, so "Dončić" (API) never
# matched "Doncic" (ledger). That pick stayed ungraded forever.
from name_utils import fold_name as _fold_name  # noqa: E402

# Shared HTTP helpers (audit M-4 + M-16). Canonical UA on every outbound
# request + robust Retry-After parsing for 429s.
from http_utils import JONNYPARLAY_UA, default_headers, retry_after_secs  # noqa: E402

# ── Config ──────────────────────────────────────────────────
# Audit M-26 (closed Apr 21 2026): all path constants now resolve via
# engine/paths.py. A $JONNYPARLAY_ROOT env var overrides the historical
# ~/Documents/JonnyParlay hardcode — that's the clean Cowork escape hatch
# and replaces the symlink workaround documented in CLAUDE.md. On Windows
# with no env var set, paths.py falls back to ~/Documents/JonnyParlay, so
# existing deployments see zero behavioral change.
#
# Values are coerced to str() so downstream str+"." concatenation in the
# discord_posted.json tempfile path still works — several callers build
# the tempfile prefix off os.path.basename(DISCORD_GUARD_FILE) + ".".
from paths import (  # noqa: E402
    PICK_LOG_PATH as _PICK_LOG_PATH_P,
    PICK_LOG_MANUAL_PATH as _PICK_LOG_MANUAL_PATH_P,
    PICK_LOG_MLB_PATH as _PICK_LOG_MLB_PATH_P,
    DISCORD_GUARD_FILE as _DISCORD_GUARD_FILE_P,
    LOG_FILE_PATH as _LOG_FILE_PATH_P,
)
PICK_LOG_PATH        = str(_PICK_LOG_PATH_P)
PICK_LOG_MANUAL_PATH = str(_PICK_LOG_MANUAL_PATH_P)
PICK_LOG_MLB_PATH    = str(_PICK_LOG_MLB_PATH_P)
DISCORD_GUARD_FILE   = str(_DISCORD_GUARD_FILE_P)
LOG_FILE_PATH        = str(_LOG_FILE_PATH_P)

# All log paths — main log first, then manual, then shadow sport logs.
# Manual picks are graded alongside primary/bonus so recap totals are accurate,
# but live in their own file to keep model-generated data clean.
ALL_LOG_PATHS = [PICK_LOG_PATH, PICK_LOG_MANUAL_PATH, PICK_LOG_MLB_PATH]
# Shadow sports: grade silently, no Discord post
SHADOW_SPORTS = {"MLB"}

BRAND_LOGO = "https://cdn.discordapp.com/attachments/1115840612915228727/1225636209221566625/JonnyParlaylogoRedBlack.png"

# ── File logger setup (file only — console output stays as print()) ───────────
# Rotation is wired through engine/log_setup.attach_rotating_handler so
# jonnyparlay.log can't grow unbounded. Audit M-25 closed Apr 20 2026 — swapping
# a plain FileHandler for a RotatingFileHandler keeps the on-disk path identical
# but caps total history at ROTATION_MAX_BYTES × (ROTATION_BACKUP_COUNT + 1).
# Since run_picks.py ALSO attaches to the "jonnyparlay" logger, the helper is
# idempotent — whichever module imports first wins, the second call is a no-op.
from log_setup import attach_rotating_handler  # noqa: E402
logger = logging.getLogger("jonnyparlay")
logger.setLevel(logging.INFO)
attach_rotating_handler(logger, LOG_FILE_PATH)
logger.propagate = False  # Don't bubble up to root logger (avoids duplicate prints)

# ── Secrets (Odds API key + Discord webhooks) ────────────────
# Loaded from environment or .env file — see secrets_config.py.
# Covers audit findings C-5 (hardcoded API key) + C-6 (hardcoded webhooks).
from secrets_config import (
    ODDS_API_KEY,
    DISCORD_RECAP_WEBHOOK,       # → #daily-recap
    DISCORD_MONTHLY_WEBHOOK,     # → #monthly-tracker
    DISCORD_ANNOUNCE_WEBHOOK,    # → #announcements
)

ODDS_BASE = "https://api.the-odds-api.com/v4"
SPORT_KEYS = {
    "NBA": "basketball_nba", "NHL": "icehockey_nhl",
    "NFL": "americanfootball_nfl", "MLB": "baseball_mlb",
    "NCAAB": "basketball_ncaab", "NCAAF": "americanfootball_ncaaf",
}

# Player stat APIs (free, public)
NBA_STATS_BASE = "https://stats.nba.com/stats"
NHL_STATS_BASE = "https://api-web.nhle.com/v1"
MLB_STATS_BASE = "https://statsapi.mlb.com/api/v1"

STAT_SOURCES = {
    # stat → (sport, API field to check)
    "AST": "assists", "REB": "rebounds", "PTS": "points",
    "3PM": "threePointersMade", "SOG": "shots",
    "K": "strikeOuts", "OUTS": "outs", "HA": "hits",
    "HITS": "hits", "TB": "totalBases",
    "HRR": "hits_runs_rbis",
}

# Game-line stat types (graded from scores, not player stats)
GAME_LINE_STATS = {"TOTAL", "SPREAD", "TEAM_TOTAL", "ML_FAV", "ML_DOG",
                   "F5_TOTAL", "F5_SPREAD", "F5_ML", "NRFI", "YRFI",
                   "GOLF_WIN"}

# Terminal grader states (audit M-23, closed Apr 20 2026).
#
# Once a row's `result` column holds any of these values it is considered
# permanently graded — the grader must never re-fetch boxscores for it,
# re-grade it, or overwrite the value on a later run. Treat this as the
# single source of truth for "is this pick done?".
#
#   W     — won
#   L     — lost
#   P     — push (stake refunded, excluded from ROI denominator)
#   VOID  — canceled / DNP (stake refunded, excluded from ROI denominator)
#
# Refunded outcomes (P + VOID) must be excluded from risked/ROI math — see
# weekly_recap._REFUNDED_RESULTS (audit H-5) and results_graphic.daily_stats
# (audit M-23). Downstream readers should compare case-insensitively and
# .strip() first to tolerate whitespace from manual edits.
TERMINAL_RESULTS = frozenset({"W", "L", "P", "VOID"})


def _is_terminal_result(raw: object) -> bool:
    """Case-insensitive, whitespace-tolerant membership test for TERMINAL_RESULTS.

    Centralizes the "has this row been graded?" question so every call site
    uses the same rule. Empty strings, None, and unknown values all return
    False, which means the row is still eligible for grading.
    """
    if raw is None:
        return False
    return str(raw).strip().upper() in TERMINAL_RESULTS


# Sportsbook display contract — canonical definition in book_names.py (audit H-13).
# Kept _BOOK_DISPLAY as an alias for backwards-compat with any call site that
# references it directly.
from book_names import BOOK_DISPLAY as _BOOK_DISPLAY, display_book  # noqa: E402

# Locale-independent English month names (audit M-22). ``calendar.month_name``
# returns localized strings on non-en-US Windows installs — picksbyjonny is
# an English brand and monthly summary posts must stay English regardless
# of the host's LC_ALL / system locale.
from month_names import MONTH_NAMES  # noqa: E402

# Centralized brand tagline (audit L-7).
from brand import BRAND_TAGLINE  # noqa: E402

# Shared atomic-JSON writer (architectural note #2) — replaces the inline
# tmp+fsync+replace fallback in _save_guard.
from io_utils import atomic_write_json  # noqa: E402

# Schema sidecar writer (audit arch note #5). Every writer path must refresh
# the sidecar after a successful write so readers can fail-fast on forward-
# incompatible schema drift without sniffing the CSV header.
from pick_log_schema import write_schema_sidecar as _write_schema_sidecar  # noqa: E402


def fmt_date(date_str: str) -> str:
    """'2026-04-13' → 'April 13'"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%B %d").replace(" 0", " ")
    except Exception:
        return date_str


def fetch_scores(sport, date_str):
    """Fetch completed game scores from The Odds API for a given date."""
    sk = SPORT_KEYS.get(sport)
    if not sk:
        return []
    # The scores endpoint returns completed games.
    # daysFrom must cover the target date — compute dynamically so historical
    # grading runs (e.g. --date 2026-04-19 run a week later) actually find data.
    # API max is 40 on paid plans; cap there. Minimum 3 so same-day runs still work.
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        delta = (datetime.utcnow().date() - target_date).days + 1
        days_from = max(3, min(delta, 40))
    except Exception:
        days_from = 3
    params = {
        "apiKey": ODDS_API_KEY,
        "daysFrom": days_from,
    }
    try:
        # Audit M-16: canonical UA on every outbound API call.
        r = requests.get(f"{ODDS_BASE}/sports/{sk}/scores", params=params,
                         headers=default_headers(), timeout=15)
        if r.status_code == 422:
            # Plan limit exceeded — daysFrom too large for this subscription.
            # Return None (not []) so callers can skip the game-complete gate
            # and grade purely from player-stat APIs (ESPN/NHL) which have no
            # recency cap. Returning [] would block all prop grading.
            print(f"  ℹ Scores API unavailable for {date_str} (plan limit) — grading from stat APIs only")
            return None
        r.raise_for_status()
        scores = r.json()
        # Filter to completed games on the target date
        # IMPORTANT: commence_time is UTC — late ET games (9-10pm ET) fall on
        # the next UTC calendar day. Convert to ET before comparing.
        et = ZoneInfo("America/New_York")
        completed = []
        for game in scores:
            if not game.get("completed"):
                continue
            ct = game.get("commence_time", "")
            try:
                # Parse UTC timestamp and convert to ET date
                game_dt_utc = datetime.strptime(ct, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                game_date_et = game_dt_utc.astimezone(et).strftime("%Y-%m-%d")
                if game_date_et == date_str:
                    completed.append(game)
            except Exception:
                # Fallback: raw string check
                if date_str in ct:
                    completed.append(game)
        return completed
    except Exception as e:
        print(f"  ⚠ Error fetching {sport} scores: {e}")
        return []


ESPN_NBA_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"

def fetch_nba_boxscore(date_str):
    """Fetch NBA player stats using ESPN's public API (no auth required)."""
    espn_date = date_str.replace("-", "")
    try:
        r = requests.get(f"{ESPN_NBA_BASE}/scoreboard",
                         params={"dates": espn_date},
                         headers=default_headers(), timeout=15)
        r.raise_for_status()
        events = r.json().get("events", [])
        player_stats = {}

        for event in events:
            event_id = event.get("id")
            try:
                box = requests.get(f"{ESPN_NBA_BASE}/summary",
                                   params={"event": event_id},
                                   headers=default_headers(), timeout=15)
                box.raise_for_status()
                box_data = box.json()

                for team_block in box_data.get("boxscore", {}).get("players", []):
                    for stat_block in team_block.get("statistics", []):
                        labels = stat_block.get("labels", [])
                        for athlete in stat_block.get("athletes", []):
                            name = athlete.get("athlete", {}).get("displayName", "").strip()
                            vals  = athlete.get("stats", [])
                            if not name or not vals:
                                continue
                            d = dict(zip(labels, vals))
                            entry = {}
                            for our_key, espn_key in [("PTS","PTS"),("REB","REB"),("AST","AST")]:
                                try: entry[our_key] = int(d[espn_key])
                                except: pass
                            # 3PT is "made-att" string e.g. "3-7"
                            if "3PT" in d:
                                try: entry["3PM"] = int(str(d["3PT"]).split("-")[0])
                                except: pass
                            if entry:
                                player_stats[name.lower()] = entry
                time.sleep(0.2)
            except Exception as e:
                continue

        return player_stats
    except Exception as e:
        print(f"  ⚠ NBA (ESPN) stats fetch failed: {e}")
        return {}


def fetch_espn_game_scores(date_str):
    """Fetch NBA final game scores from ESPN — no recency limit.

    Returns a dict matching the Odds API scores_map format:
        {"Away Team @ Home Team": {home_team, away_team, scores: [{name, score}]}}

    Used as fallback when The Odds API /scores returns 422 (plan limit exceeded
    for daysFrom), so daily lay and game-line grading still works on historical dates.
    """
    espn_date = date_str.replace("-", "")
    try:
        r = requests.get(f"{ESPN_NBA_BASE}/scoreboard",
                         params={"dates": espn_date},
                         headers=default_headers(), timeout=15)
        r.raise_for_status()
        events = r.json().get("events", [])
        scores_map = {}
        for event in events:
            for comp in event.get("competitions", []):
                # Only include completed games
                status = comp.get("status", {})
                if not status.get("type", {}).get("completed", False):
                    continue
                competitors = comp.get("competitors", [])
                home = next((c for c in competitors if c.get("homeAway") == "home"), None)
                away = next((c for c in competitors if c.get("homeAway") == "away"), None)
                if not home or not away:
                    continue
                home_name = home.get("team", {}).get("displayName", "")
                away_name = away.get("team", {}).get("displayName", "")
                home_score = home.get("score", "0")
                away_score = away.get("score", "0")
                if not home_name or not away_name:
                    continue
                game_key = f"{away_name} @ {home_name}"
                scores_map[game_key] = {
                    "home_team": home_name,
                    "away_team": away_name,
                    "scores": [
                        {"name": away_name, "score": away_score},
                        {"name": home_name, "score": home_score},
                    ],
                    "completed": True,
                }
        return scores_map
    except Exception as e:
        print(f"  ⚠ ESPN game scores fetch failed: {e}")
        return {}



def fetch_nhl_boxscores(date_str):
    """Fetch NHL player stats from NHL API."""
    try:
        r = requests.get(f"{NHL_STATS_BASE}/score/{date_str}",
                         headers=default_headers(), timeout=15)
        r.raise_for_status()
        data = r.json()
        player_stats = {}

        for game in data.get("games", []):
            game_id = game.get("id")
            try:
                box = requests.get(f"{NHL_STATS_BASE}/gamecenter/{game_id}/boxscore",
                                   headers=default_headers(), timeout=15)
                box.raise_for_status()
                box_data = box.json()


                # NHL API nests player stats under playerByGameStats
                pgs = box_data.get("playerByGameStats", {})
                for side in ["homeTeam", "awayTeam"]:
                    team_data = pgs.get(side, {})
                    for player in team_data.get("forwards", []) + team_data.get("defense", []):
                        raw_name = player.get("name", "")
                        if isinstance(raw_name, dict):
                            raw_name = raw_name.get("default", "")
                        name = str(raw_name).strip()
                        if name:
                            player_stats[name.lower()] = {
                                "SOG": player.get("sog", 0),
                                "AST": player.get("assists", 0),
                            }
                time.sleep(0.3)
            except Exception as e:
                print(f"  ⚠ NHL boxscore fetch failed for game {game_id}: {e}")
                continue

        return player_stats
    except Exception as e:
        print(f"  ⚠ NHL stats fetch failed: {e}")
        return {}


def fetch_mlb_boxscores(date_str):
    """Fetch MLB player stats from MLB Stats API."""
    try:
        r = requests.get(f"{MLB_STATS_BASE}/schedule",
                        params={"sportId": 1, "date": date_str},
                        headers=default_headers(), timeout=15)
        r.raise_for_status()
        data = r.json()
        player_stats = {}

        for date_entry in data.get("dates", []):
            for game in date_entry.get("games", []):
                game_pk = game.get("gamePk")
                try:
                    box = requests.get(f"{MLB_STATS_BASE}/game/{game_pk}/boxscore",
                                       headers=default_headers(), timeout=15)
                    box.raise_for_status()
                    box_data = box.json()

                    for side in ["home", "away"]:
                        team = box_data.get("teams", {}).get(side, {})
                        players = team.get("players", {})
                        for pid, pdata in players.items():
                            name = pdata.get("person", {}).get("fullName", "").strip()
                            if not name:
                                continue
                            batting = pdata.get("stats", {}).get("batting", {})
                            pitching = pdata.get("stats", {}).get("pitching", {})

                            entry = {}
                            if batting:
                                h = batting.get("hits", 0)
                                doubles = batting.get("doubles", 0)
                                triples = batting.get("triples", 0)
                                hr = batting.get("homeRuns", 0)
                                singles = max(0, h - doubles - triples - hr)
                                entry["HITS"] = h
                                entry["TB"] = singles + 2*doubles + 3*triples + 4*hr
                                entry["HRR"] = h + batting.get("runs", 0) + batting.get("rbi", 0)

                            if pitching:
                                # Parse IP string "6.1" → 6*3 + 1 = 19 outs
                                ip_str = str(pitching.get("inningsPitched", "0"))
                                if "." in ip_str:
                                    ip_parts = ip_str.split(".")
                                    outs = int(ip_parts[0]) * 3 + int(ip_parts[1])
                                else:
                                    outs = int(ip_str) * 3
                                entry["K"] = pitching.get("strikeOuts", 0)
                                entry["OUTS"] = outs
                                entry["HA"] = pitching.get("hits", 0)
                                entry["ER"] = pitching.get("earnedRuns", 0)
                                entry["IP"] = pitching.get("inningsPitched", "0")

                            if entry:
                                player_stats[name.lower()] = entry
                    time.sleep(0.3)
                except Exception:
                    continue

        return player_stats
    except Exception as e:
        print(f"  ⚠ MLB stats fetch failed: {e}")
        return {}


def fetch_mlb_linescores(date_str):
    """Fetch MLB inning-by-inning run data for F5/NRFI grading.

    Returns dict: lowercase 'Away @ Home' → list of inning dicts.
    Each inning: {'num': N, 'away': {'runs': R}, 'home': {'runs': R}}
    Only includes completed/in-progress games.
    """
    try:
        r = requests.get(f"{MLB_STATS_BASE}/schedule",
                         params={"sportId": 1, "date": date_str},
                         headers=default_headers(), timeout=15)
        r.raise_for_status()
        data = r.json()
        linescores = {}

        for date_entry in data.get("dates", []):
            for game in date_entry.get("games", []):
                status = game.get("status", {}).get("abstractGameState", "")
                if status not in ("Final", "Live"):
                    continue
                game_pk = game.get("gamePk")
                home = game.get("teams", {}).get("home", {}).get("team", {}).get("name", "")
                away = game.get("teams", {}).get("away", {}).get("team", {}).get("name", "")
                if not game_pk or not home or not away:
                    continue
                try:
                    ls = requests.get(f"{MLB_STATS_BASE}/game/{game_pk}/linescore",
                                      headers=default_headers(), timeout=15)
                    ls.raise_for_status()
                    innings = ls.json().get("innings", [])
                    game_key = f"{away} @ {home}".lower()
                    linescores[game_key] = innings
                    time.sleep(0.2)
                except Exception:
                    continue

        return linescores
    except Exception as e:
        print(f"  ⚠ MLB linescore fetch failed: {e}")
        return {}


def parse_score_from_api(game_data):
    """Extract final score from The Odds API scores response."""
    scores = game_data.get("scores", [])
    if not scores or len(scores) < 2:
        return None, None
    home_team = game_data.get("home_team", "")
    away_team = game_data.get("away_team", "")
    home_score = None
    away_score = None
    for s in scores:
        try:
            val = int(float(str(s.get("score", 0)).strip()))
        except (ValueError, TypeError):
            val = None
        if s.get("name") == home_team:
            home_score = val
        elif s.get("name") == away_team:
            away_score = val
    return home_score, away_score


NBA_ABBREV = {
    "ATL": "Atlanta",    "BOS": "Boston",      "BKN": "Brooklyn",    "CHA": "Charlotte",
    "CHI": "Chicago",    "CLE": "Cleveland",   "DAL": "Dallas",      "DEN": "Denver",
    "DET": "Detroit",    "GSW": "Golden State","HOU": "Houston",     "IND": "Indiana",
    "LAC": "Clippers",   "LAL": "Lakers",      "MEM": "Memphis",     "MIA": "Miami",
    "MIL": "Milwaukee",  "MIN": "Minnesota",   "NOP": "New Orleans", "NYK": "New York",
    "OKC": "Oklahoma",   "ORL": "Orlando",     "PHI": "Philadelphia","PHX": "Phoenix",
    "POR": "Portland",   "SAC": "Sacramento",  "SAS": "San Antonio", "TOR": "Toronto",
    "UTA": "Utah",       "WAS": "Washington",
}


# ── Ambiguous 2-letter team codes ─────────────────────────────────────────────
# Audit H-4: a raw "LA" in the ledger's team field matches both Lakers and
# Clippers on substring — whichever NBA game was seen first in the scores
# dict "wins" the match. Same with "NY" (Knicks vs Nets), "SF" (49ers vs
# Giants), "SD" (old Padres).
#
# We refuse to best-guess these. A caller that sees an ambiguous code treats
# the pick as ungraded (returns None) and logs a loud warning so Jono can
# fix the ledger entry. The authoritative 3-letter forms (LAL, LAC, NYK,
# BKN, etc.) are unambiguous and keep working.
#
# Values are the list of full 3-letter codes the ambiguous short form might
# have meant — used purely for the warning text so the message tells Jono
# which specific teams he might have intended.
AMBIGUOUS_TEAM_CODES: dict[str, list[str]] = {
    "LA":  ["LAL", "LAC"],   # Lakers vs Clippers
    "NY":  ["NYK", "BKN"],   # Knicks vs Nets (treating BKN as "New York area")
    "SF":  [],                # 49ers vs Giants (NFL + MLB cross-sport)
    "SD":  [],                # Old Padres SD — formally dead but still appears
}


def is_ambiguous_team_code(code: str | None) -> bool:
    """True when a raw team code is known to collide across two teams.

    Case-insensitive. Blank / None → False (nothing to disambiguate).
    """
    if not code:
        return False
    return str(code).strip().upper() in AMBIGUOUS_TEAM_CODES


def describe_team_ambiguity(code: str | None) -> str:
    """Human-readable warning text for an ambiguous 2-letter code.

    Used in grader log messages so Jono can see which specific codes he
    should have used. Example::

        >>> describe_team_ambiguity("LA")
        "'LA' is ambiguous between LAL / LAC — use a 3-letter code."
    """
    if not code:
        return ""
    k = str(code).strip().upper()
    candidates = AMBIGUOUS_TEAM_CODES.get(k, [])
    if candidates:
        return f"'{k}' is ambiguous between {' / '.join(candidates)} — use a 3-letter code."
    return f"'{k}' is a known ambiguous 2-letter team code — use a 3-letter code."


def grade_daily_lay(row, all_scores):
    """Grade the daily lay parlay (always NBA). All legs must cover for W.

    Push handling: pushing legs drop out of the parlay and the remainder is
    regraded. If every leg pushes, the parlay is a push. Any losing leg = L.

    Invariants (tested in test_grade_daily_lay.py, covers audit C-10):
        * Any leg with result_val < 0 → function returns "L" IMMEDIATELY
          inside the loop. Subsequent legs are not evaluated.
        * Therefore the "return 'W'" fall-through at the bottom is only
          reachable when zero legs lost — it's safe as a default because
          an all-loss parlay cannot reach that line.
        * "return 'P'" fall-through is only reachable when every leg pushed.
        * Unparseable/unmatched leg → return None (pick stays ungraded).
    """
    import json as _json_dl
    game_desc = row.get("game", "")
    date_str  = row.get("date", "")
    nba_scores = all_scores.get((date_str, "NBA"), {})
    if not nba_scores:
        return None

    # H9: try legs JSON first (populated by _log_daily_lay since Apr 29 2026);
    # fall back to game-string parsing for the 9 legacy rows that pre-date this fix.
    parsed_legs = []   # list of (team_str, spread_float)
    _legs_json = row.get("legs", "")
    _used_json = False
    if _legs_json and isinstance(_legs_json, str):
        try:
            _jlegs = _json_dl.loads(_legs_json)
            if isinstance(_jlegs, list) and _jlegs:
                for _jl in _jlegs:
                    _t = str(_jl.get("team", "")).strip()
                    _s = float(_jl.get("spread", 0))
                    if not _t:
                        raise ValueError("empty team")
                    parsed_legs.append((_t, _s))
                _used_json = True
        except Exception:
            parsed_legs = []

    if not _used_json:
        # Legacy: parse "TEAM +spread / TEAM +spread" from the game field
        legs_raw = [l.strip() for l in game_desc.split("/") if l.strip()]
        if not legs_raw:
            return None
        for leg in legs_raw:
            parts = leg.strip().split()
            if len(parts) < 2:
                return None
            spread = None
            team_tokens = []
            for tok in parts:
                try:
                    f = float(tok.lstrip("+"))
                    spread = f
                    if tok.startswith("-"):
                        spread = -abs(spread)
                except ValueError:
                    team_tokens.append(tok)
            if spread is None or not team_tokens:
                return None
            parsed_legs.append((" ".join(team_tokens).strip(), spread))

    if not parsed_legs:
        return None

    pushed = 0
    won    = 0
    for team_str, spread in parsed_legs:
        team_upper = team_str.upper()
        team_tokens = team_str.split()  # derived for meaningful-token matching below

        # H-4: refuse to best-guess ambiguous 2-letter codes ("LA", "NY").
        # Substring-matching "LA" against "Los Angeles Lakers @ Los Angeles
        # Clippers" would match both halves of the game. A daily lay leg with
        # an ambiguous team is unresolvable — drop the whole parlay as
        # ungraded and warn so Jono can fix the source row.
        if is_ambiguous_team_code(team_upper):
            logger.warning(
                f"[grade_daily_lay] {describe_team_ambiguity(team_upper)} "
                f"(leg={team_str!r}, game={game_desc!r}) — parlay stays ungraded."
            )
            return None

        # Accept both abbreviations ("OKC") and full names ("Oklahoma City Thunder")
        team_frag = NBA_ABBREV.get(team_upper, team_str).lower()

        matched = None
        for key, gdata in nba_scores.items():
            key_lower = key.lower()
            if team_frag in key_lower or team_str.lower() in key_lower:
                matched = gdata
                break
            # Token-wise match: any meaningful (len>=4) token present in key
            meaningful = [t.lower() for t in team_tokens if len(t) >= 4]
            if meaningful and any(m in key_lower for m in meaningful):
                matched = gdata
                break
        if not matched:
            return None

        home_score, away_score = parse_score_from_api(matched)
        if home_score is None or away_score is None:
            return None

        home_team = matched.get("home_team", "").lower()
        # Team is home if its fragment (or any meaningful token) appears in home_team
        meaningful = [t.lower() for t in team_tokens if len(t) >= 4]
        is_home = team_frag in home_team or any(m in home_team for m in meaningful)
        is_away = not is_home
        margin = (away_score - home_score) if is_away else (home_score - away_score)
        result_val = margin + spread
        if result_val < 0:
            return "L"            # any leg lost → parlay lost
        if result_val == 0:
            pushed += 1           # leg pushes, drop from parlay
            continue
        won += 1                  # leg covered

    if won == 0 and pushed == len(parsed_legs):
        return "P"               # every leg pushed
    return "W"                    # remaining legs all covered


def grade_parlay_legs(row, all_player_stats, all_scores):
    """Grade a longshot or SGP row by grading each prop leg independently.

    Parlay outcome:
      W = every leg wins
      L = any leg loses
      P = no losses, at least one push (push leg drops; remainder settles)
      None = any leg is ungradeable (pick stays ungraded, retry next run)

    Legs are stored as JSON in the ``legs`` column, written by _legs_json()
    or _log_sgp(). Each leg dict must have:
        player, direction, line, stat, sport, game
    """
    import json as _json
    legs_raw = row.get("legs", "")
    if not legs_raw:
        return None
    try:
        legs = _json.loads(legs_raw)
    except (_json.JSONDecodeError, TypeError):
        logger.warning(
            f"[grade_parlay_legs] Bad legs JSON for row "
            f"player={row.get('player','?')!r} date={row.get('date','?')!r}"
        )
        return None
    if not legs:
        return None

    date_str = row.get("date", "")
    results = []
    for leg in legs:
        sport = leg.get("sport", row.get("sport", "NBA"))
        fake_pick = {
            "player":    leg.get("player", ""),
            "direction": leg.get("direction", ""),
            "line":      leg.get("line", ""),
            "stat":      leg.get("stat", ""),
            "game":      leg.get("game", row.get("game", "")),
            "team":      leg.get("team", ""),
            "date":      date_str,
            "sport":     sport,
        }
        pstats = all_player_stats.get((date_str, sport), {})
        scores = all_scores.get((date_str, sport), {})
        leg_result = grade_prop(fake_pick, pstats, scores_by_game=scores)
        if leg_result is None:
            return None   # leg not yet gradeable — wait for next run
        results.append(leg_result)

    if "L" in results:
        return "L"
    # M5: push legs drop from parlay; re-evaluate remaining legs
    # e.g. 3-leg parlay [W, P, W] → 2-leg effective parlay → W
    #      3-leg parlay [P, P, P] → all dropped → P (stake returned)
    remaining = [r for r in results if r != "P"]
    if not remaining:
        return "P"   # every leg pushed — full push, stake back
    if "L" in remaining:
        return "L"   # shouldn't be reachable but defensive
    return "W"       # all non-pushed legs won


def _find_linescore_innings(game_str, linescores):
    """Find inning list for a game string by fuzzy team-name matching."""
    if not linescores:
        return None
    game_lower = game_str.lower()
    # Direct substring match
    for key, innings in linescores.items():
        if game_lower in key or key in game_lower:
            return innings
    # Partial team name match — split on ' @ '
    parts = [p.strip() for p in game_lower.split("@") if p.strip()]
    for key, innings in linescores.items():
        key_parts = [p.strip() for p in key.split("@") if p.strip()]
        # Match if any meaningful word from pick game appears in linescore key
        for pp in parts:
            words = [w for w in pp.split() if len(w) > 3]
            for w in words:
                if any(w in kp for kp in key_parts):
                    return innings
    return None


def _resolve_pick_is_home(pick, away_team):
    """BUG G1/G2/G3 fix: determine if pick is on home team.

    Returns:
        True  — pick is on the home side.
        False — pick is on the away side.
        None  — can't reliably determine (ambiguous team code on a legacy row
                with no is_home field). Caller should treat the pick as
                ungraded rather than best-guess.

    Uses ``is_home`` field (logged since fix) when available; falls back to
    string matching for legacy rows that pre-date the fix.

    Audit H-4: fallback path refuses to guess for ambiguous 2-letter codes
    (LA / NY / SF / SD). Previously, "LA" in the team field would substring-
    match Lakers, Clippers, Los Angeles Angels, etc. — whichever was
    iterated first. Now we log a warning and return None so the caller can
    skip grading.
    """
    is_home_field = pick.get("is_home", "")
    if is_home_field is not None and str(is_home_field).strip() != "":
        return str(is_home_field).strip().lower() in ("true", "1", "yes")
    # Fallback for old rows: string-match pick identifiers against away_team full name
    pick_team = pick.get("team", "").strip()
    player_field = pick.get("player", "").strip()
    away_lower = (away_team or "").lower()
    if not away_lower:
        return True  # no away team info; assume home (caller's usual default)

    # H-4 guard: ambiguous 2-letter team codes can't be resolved by substring
    # match. Bail out loudly instead of silently grading against the wrong
    # side. Only triggers on the legacy-fallback path — modern rows have
    # is_home populated and hit the short-circuit above.
    if is_ambiguous_team_code(pick_team):
        logger.warning(
            f"[_resolve_pick_is_home] {describe_team_ambiguity(pick_team)} "
            f"No is_home field on pick (game={pick.get('game','?')!r}, "
            f"player={player_field!r}) — refusing to best-guess. Pick stays ungraded."
        )
        return None

    is_away = False
    for identifier in [pick_team, player_field]:
        if not identifier:
            continue
        # Whole-identifier substring check (handles 2-char abbrevs like "LA", "NY")
        if identifier.lower() in away_lower or away_lower in identifier.lower():
            is_away = True
            break
        # Token-level check for multi-word identifiers
        tokens = [t for t in identifier.split() if len(t) >= 2]
        if any(t.lower() in away_lower for t in tokens):
            is_away = True
            break
    return not is_away


def grade_game_line(pick, scores_by_game, linescores=None):
    """Grade a game-line pick (spread, total, ML, F5, NRFI) using scores.

    linescores: optional dict from fetch_mlb_linescores() for F5/NRFI grading.
    """
    stat = pick["stat"]
    game = pick["game"]
    direction = pick["direction"]
    try:
        line = float(pick["line"])
    except (ValueError, TypeError, KeyError):
        logger.warning(f"[grade_game_line] Bad line value for {pick.get('game','?')} {stat}: {pick.get('line','')!r} — skipping")
        return None

    # Find matching game in scores
    matched = None
    for key, gdata in scores_by_game.items():
        if game.lower() in key.lower() or key.lower() in game.lower():
            matched = gdata
            break

    if not matched:
        # Try partial team name matching
        teams = game.replace(" @ ", "|").split("|")
        for key, gdata in scores_by_game.items():
            for t in teams:
                if t.strip().lower() in key.lower():
                    matched = gdata
                    break
            if matched:
                break

    if not matched:
        return None

    home_score, away_score = parse_score_from_api(matched)
    if home_score is None or away_score is None:
        return None

    total = home_score + away_score
    home_team = matched.get("home_team", "")
    away_team = matched.get("away_team", "")

    if stat == "TOTAL":
        actual = total
        if direction == "over":
            if actual > line: return "W"
            elif actual < line: return "L"
            else: return "P"
        else:
            if actual < line: return "W"
            elif actual > line: return "L"
            else: return "P"

    elif stat == "SPREAD":
        pick_is_home = _resolve_pick_is_home(pick, away_team)
        if pick_is_home is None:
            return None  # H-4: ambiguous team code, ungradable
        if pick_is_home:
            margin = home_score - away_score
        else:
            margin = away_score - home_score
        result_val = margin + line  # line is already signed (e.g. -3.5)
        if result_val > 0: return "W"
        elif result_val < 0: return "L"
        else: return "P"

    elif stat in ("ML_FAV", "ML_DOG"):
        pick_is_home = _resolve_pick_is_home(pick, away_team)
        if pick_is_home is None:
            return None  # H-4: ambiguous team code, ungradable
        if pick_is_home:
            return "W" if home_score > away_score else ("L" if away_score > home_score else "P")
        else:
            return "W" if away_score > home_score else ("L" if home_score > away_score else "P")

    elif stat in ("NRFI", "YRFI"):
        innings = _find_linescore_innings(game, linescores or {})
        if not innings:
            return None
        # Need at least inning 1 complete — check both teams scored their half
        inning1 = next((i for i in innings if i.get("num") == 1), None)
        if not inning1:
            return None
        away_r1 = inning1.get("away", {}).get("runs", None)
        home_r1 = inning1.get("home", {}).get("runs", None)
        if away_r1 is None or home_r1 is None:
            return None  # Inning not fully complete yet
        first_inning_runs = away_r1 + home_r1
        if stat == "NRFI":
            return "W" if first_inning_runs == 0 else "L"
        else:  # YRFI
            return "W" if first_inning_runs > 0 else "L"

    elif stat == "TEAM_TOTAL":
        # Use _resolve_pick_is_home() — reads is_home field (logged since BUG G fix),
        # falls back to team-abbrev string matching for legacy rows.
        # Previous substring match on player field was broken: 3-char abbreviations
        # were filtered by len(w) > 3, so it always graded against home score.
        pick_is_home = _resolve_pick_is_home(pick, away_team)
        if pick_is_home is None:
            return None  # H-4: ambiguous team code, ungradable
        team_score = home_score if pick_is_home else away_score
        if direction == "over":
            if team_score > line: return "W"
            elif team_score < line: return "L"
            else: return "P"
        else:
            if team_score < line: return "W"
            elif team_score > line: return "L"
            else: return "P"

    elif stat in ("F5_TOTAL", "F5_SPREAD", "F5_ML"):
        innings = _find_linescore_innings(game, linescores or {})
        if not innings:
            return None
        # Need 5 complete innings minimum
        complete = [i for i in innings if i.get("num", 0) <= 5
                    and i.get("away", {}).get("runs") is not None
                    and i.get("home", {}).get("runs") is not None]
        if len(complete) < 5:
            return None  # Game not yet 5 innings complete

        f5_away = sum(i["away"]["runs"] for i in complete)
        f5_home = sum(i["home"]["runs"] for i in complete)
        f5_total = f5_away + f5_home

        if stat == "F5_TOTAL":
            if direction == "over":
                if f5_total > line: return "W"
                elif f5_total < line: return "L"
                else: return "P"
            else:
                if f5_total < line: return "W"
                elif f5_total > line: return "L"
                else: return "P"

        elif stat == "F5_SPREAD":
            pick_is_home = _resolve_pick_is_home(pick, away_team)
            if pick_is_home is None:
                return None  # H-4: ambiguous team code, ungradable
            margin = (f5_home - f5_away) if pick_is_home else (f5_away - f5_home)
            result_val = margin + line
            if result_val > 0: return "W"
            elif result_val < 0: return "L"
            else: return "P"

        else:  # F5_ML
            pick_is_home = _resolve_pick_is_home(pick, away_team)
            if pick_is_home is None:
                return None  # H-4: ambiguous team code, ungradable
            if pick_is_home:
                return "W" if f5_home > f5_away else ("L" if f5_away > f5_home else "P")
            else:
                return "W" if f5_away > f5_home else ("L" if f5_home > f5_away else "P")

    elif stat == "GOLF_WIN":
        # Golf outrights must be graded manually after tournament completes
        # (tournaments span 4 days, no real-time grading via scores API)
        return None

    return None


def _game_is_complete(pick, scores_by_game):
    """Check if a player's game appears in the completed scores dict.

    scores_by_game keys are 'Away @ Home' strings from The Odds API,
    which only includes completed games. Match by game field or team name.
    Returns True only if we can positively confirm the game is finished.
    """
    if not scores_by_game:
        return False
    game  = pick.get("game", "").strip().lower()
    team  = pick.get("team", "").strip().lower()

    for key in scores_by_game:
        key_lower = key.lower()
        # Direct game string match
        if game and (game in key_lower or key_lower in game):
            return True
        # Team name / abbreviation word match (skip very short tokens)
        if team:
            words = [w for w in team.split() if len(w) > 2]
            if words and any(w in key_lower for w in words):
                return True
    return False


def grade_prop(pick, player_stats, scores_by_game=None):
    """Grade a player prop using actual stat lines.

    scores_by_game: completed-games dict from fetch_scores (Odds API).
                    If provided, picks whose game is not yet complete
                    return None instead of a premature grade/VOID.

    Returns W/L/P on hit, VOID if game finished but player not in boxscore
    (DNP/scratch), or None if game not yet complete / data unavailable.
    """
    player = pick["player"].lower()
    stat = pick["stat"]
    try:
        line = float(pick["line"])
    except (ValueError, TypeError, KeyError):
        logger.warning(f"[grade_prop] Bad line value for {pick.get('player','?')} {stat}: {pick.get('line','')!r} — skipping")
        return None
    direction = pick["direction"]

    # Gate: only grade if we can confirm the game is finished
    if scores_by_game is not None:
        if not _game_is_complete(pick, scores_by_game):
            return None  # Game not finished — don't grade yet

    # Try exact match first, then partial
    actual = None
    # Shared canonical folding (audit H-3) — accent-stripping, lowercasing,
    # punctuation removal live in name_utils.fold_name so the grader and
    # run_picks agree on name identity. Using the local helper keeps call
    # sites short while the contract is defined in one place.
    def _norm(s):
        return _fold_name(s)

    player_norm = _norm(player)
    # Exact match on normalized keys
    for name, stats in player_stats.items():
        if _norm(name) == player_norm:
            actual = stats.get(stat)
            break

    if actual is None:
        # Fuzzy: last name match, suffix-aware
        _SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
        tokens = [t for t in player_norm.split() if t and t not in _SUFFIXES]
        last_name = tokens[-1] if tokens else ""
        first_name = tokens[0] if tokens else ""
        # Prefer matches with BOTH first + last name to avoid collisions
        best_candidate = None
        for name, stats in player_stats.items():
            name_norm = _norm(name)
            name_tokens = set(name_norm.split())
            if last_name and last_name in name_tokens:
                if first_name and first_name in name_tokens:
                    # Strong match — first + last name both present
                    actual = stats.get(stat)
                    best_candidate = None
                    break
                elif best_candidate is None:
                    # Weak fallback — last name only
                    best_candidate = stats.get(stat)
        if actual is None and best_candidate is not None:
            actual = best_candidate

    if actual is None:
        # Game is confirmed complete but player not in any boxscore → DNP/scratch
        if scores_by_game is not None and _game_is_complete(pick, scores_by_game):
            return "VOID"
        return None

    actual = float(actual)

    if direction == "over":
        if actual > line: return "W"
        elif actual < line: return "L"
        else: return "P"
    else:  # under
        if actual < line: return "W"
        elif actual > line: return "L"
        else: return "P"


# ============================================================
#  DISCORD AUTOMATION
# ============================================================

# Set to True via --confirm flag — gates every Discord post behind a y/n prompt
_CONFIRM_MODE = False


def _confirm_post(label):
    """Prompt user before posting to Discord. Returns True to proceed, False to skip.
    Always returns True when _CONFIRM_MODE is off."""
    if not _CONFIRM_MODE:
        return True
    try:
        ans = input(f"\n  [Confirm] Post '{label}' to Discord? [y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n  [Confirm] Skipping (no input).")
        return False
    return ans in ("y", "yes")


def _webhook_post(url, payload, retries=3, backoff=2.0, label="Discord post"):
    """POST a JSON payload to a Discord webhook. Retries on failure with exponential backoff.
    If _CONFIRM_MODE is True, prompts for y/n confirmation before sending.

    Audit M-4 / M-16: routes through http_utils.retry_after_secs (which
    prefers the ``Retry-After`` header and tolerates empty / non-JSON 429
    bodies) and carries the canonical JonnyParlay User-Agent.
    """
    if not url:
        return False
    if not _confirm_post(label):
        print(f"  [Confirm] ⏭️  Skipped: {label}")
        return False
    headers = default_headers()
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=10)
            if r.status_code == 429:
                retry_after = retry_after_secs(r, default=backoff)
                logger.warning(f"[Discord] Rate limited — waiting {retry_after:.1f}s (attempt {attempt}/{retries})")
                time.sleep(retry_after)
                continue
            if r.status_code in (200, 204):
                return True
            r.raise_for_status()
        except Exception as e:
            if attempt < retries:
                wait = backoff ** attempt
                logger.warning(f"[Discord] Post failed (attempt {attempt}/{retries}): {e} — retrying in {wait:.1f}s")
                time.sleep(wait)
            else:
                logger.error(f"[Discord] Post failed after {retries} attempts: {e}")
    return False


def compute_pl(size, odds_str, result):
    """Compute units won/lost for a single pick.

    Returns 0.0 for pushes/unknown results, negative for losses, positive for wins.
    If size or odds can't be parsed, logs a warning and returns 0.0 (treated as
    unscorable — caller should check for this via the warning log rather than
    silently trusting a zero).
    """
    try:
        size = float(size)
        odds = int(float(str(odds_str).replace("+", "")))
    except (ValueError, TypeError):
        logger.warning(f"[compute_pl] Unparseable size/odds: size={size!r} odds={odds_str!r} result={result!r} — returning 0.0")
        return 0.0
    if odds == 0:
        logger.warning(f"[compute_pl] Zero odds for result={result!r} size={size} — returning 0.0")
        return 0.0
    if result == "W":
        return round(size * (100 / abs(odds)), 4) if odds < 0 else round(size * (odds / 100), 4)
    elif result == "L":
        return round(-size, 4)
    return 0.0  # Push / VOID / blank


def _safe_float(v, default=0.0):
    """Coerce v to float, returning default on blank/None/non-numeric input."""
    try:
        if v in (None, ""):
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def daily_stats(picks):
    """Return (W, L, P, total_pl, roi) for a list of graded picks."""
    w  = sum(1 for p in picks if p.get("result") == "W")
    l  = sum(1 for p in picks if p.get("result") == "L")
    pu = sum(1 for p in picks if p.get("result") == "P")
    pl = sum(compute_pl(p.get("size", 0), p.get("odds", "-110"), p.get("result", "")) for p in picks)
    risked = sum(_safe_float(p.get("size")) for p in picks if p.get("result") not in ("P", "VOID"))
    roi = (pl / risked * 100) if risked > 0 else 0.0
    return w, l, pu, round(pl, 2), round(roi, 1)


COUNTED_RUN_TYPES = {"primary", "bonus", "manual", "daily_lay", "longshot", "sgp", "gameline", "", None}
PROP_RUN_TYPES    = {"primary", "bonus"}          # model props — used for W-L record / week / month
PARLAY_RUN_TYPES  = {"daily_lay", "sgp", "longshot"}  # parlays — shown separately in recap

def get_graded_primary(all_rows):
    """Return graded picks (primary + bonus + manual) grouped by date."""
    grouped = defaultdict(list)
    for row in all_rows:
        if row.get("result") in ("W", "L", "P") and row.get("run_type", "primary") in COUNTED_RUN_TYPES:
            grouped[row["date"]].append(row)
    return grouped


def compute_streak(grouped_by_date):
    """Return (streak_days, streak_pl, streak_w, streak_l) for consecutive profitable days."""
    sorted_dates = sorted(grouped_by_date.keys(), reverse=True)
    streak = 0
    total_pl = 0.0
    total_w  = 0
    total_l  = 0
    for d in sorted_dates:
        w, l, _, pl, _ = daily_stats(grouped_by_date[d])
        if pl > 0:
            streak   += 1
            total_pl += pl
            total_w  += w
            total_l  += l
        else:
            break
    return streak, round(total_pl, 2), total_w, total_l


def compute_pick_streak(all_rows):
    """Return (count, direction) for the current consecutive W/L pick streak.
    Counts model picks only (primary + bonus + daily_lay), excludes shadow sports and manual.
    Sorted by date then run_time so intra-day ordering is preserved.
    Returns (0, '') if no graded picks exist.
    """
    MODEL_RUN_TYPES = {"primary", "bonus", "daily_lay", "longshot", "sgp"}
    picks = [
        r for r in all_rows
        if r.get("result") in ("W", "L")
        and r.get("run_type", "") in MODEL_RUN_TYPES
        and r.get("sport", "") not in SHADOW_SPORTS
    ]
    picks.sort(key=lambda r: (r.get("date", ""), r.get("run_time", "")))
    if not picks:
        return 0, ""
    streak_dir = picks[-1]["result"]
    count = 0
    for p in reversed(picks):
        if p["result"] == streak_dir:
            count += 1
        else:
            break
    return count, streak_dir


def get_week_picks(all_rows, ref_date_str):
    """Return graded model prop picks (primary + bonus) in the calendar week (Mon–Sun) of
    ref_date, up to ref_date.  Parlays and shadow sports excluded so W-L record is props only."""
    ref = datetime.strptime(ref_date_str, "%Y-%m-%d")
    monday = ref - timedelta(days=ref.weekday())
    mon_str = monday.strftime("%Y-%m-%d")
    return [r for r in all_rows
            if r.get("result") in ("W", "L", "P")
            and r.get("run_type", "primary") in PROP_RUN_TYPES
            and r.get("sport", "") not in SHADOW_SPORTS
            and mon_str <= r["date"] <= ref_date_str]


def get_month_picks(all_rows, year, month, up_to_date=None):
    """Return graded model prop picks (primary + bonus) in the given year/month, optionally
    capped at up_to_date.  Parlays and shadow sports excluded so W-L record is props only."""
    prefix = f"{year}-{month:02d}-"
    return [r for r in all_rows
            if r.get("result") in ("W", "L", "P")
            and r.get("run_type", "primary") in PROP_RUN_TYPES
            and r.get("sport", "") not in SHADOW_SPORTS
            and r["date"].startswith(prefix)
            and (up_to_date is None or r["date"] <= up_to_date)]


def _fmt_odds(odds):
    """Format American odds with explicit + sign for positives."""
    try:
        o = int(float(odds))
        return f"+{o}" if o > 0 else str(o)
    except (ValueError, TypeError):
        return str(odds)


def _book_tag(book_str):
    """Return ' (Book)' or '' if book is blank."""
    b = display_book(book_str or "")
    return f" ({b})" if b else ""


def _recap_pick_line(p) -> str:
    """Format a single pick for the recap embed."""
    res     = p.get("result", "")
    emoji   = "✅" if res == "W" else ("❌" if res == "L" else "➖")
    stat    = p.get("stat", "")
    pick_pl = compute_pl(p.get("size", 0), p.get("odds", "-110"), res)
    pl_tag  = f"+{pick_pl:.2f}u" if pick_pl >= 0 else f"{pick_pl:.2f}u"
    odds_   = _fmt_odds(p.get("odds", ""))
    book    = _book_tag(p.get("book", ""))

    # Parlay / Daily Lay
    if stat in ("PARLAY", "DAILY_LAY") or p.get("run_type") == "daily_lay":
        game = p.get("game", p.get("player", ""))
        return f"{emoji} {game}{book} · {pl_tag}"

    if stat in GAME_LINE_STATS:
        team  = p.get("player", p.get("team", ""))
        line_ = p.get("line", "")
        dir_  = p.get("direction", "").upper()
        if stat == "SPREAD":
            label = f"{team} {odds_}{book}"
        elif stat in ("ML_FAV", "ML_DOG"):
            label = f"{team} ML {odds_}{book}"
        elif stat == "TOTAL":
            label = f"Total {dir_} {line_} {odds_}{book}"
        elif stat == "TEAM_TOTAL":
            team_abbr = p.get("team", "")
            label = f"{team_abbr} Team Total {dir_} {line_} {odds_}{book}"
        else:
            label = f"{team} {stat} {dir_} {line_} {odds_}{book}"
        return f"{emoji} {label} · {pl_tag}"
    else:
        # Prop: last name only
        last  = p.get("player", "").split()[-1].upper()
        dir_  = p.get("direction", "").upper()
        line_ = p.get("line", "")
        return f"{emoji} {last} {dir_} {line_} {stat}{book} · {pl_tag}"


def build_recap_embed(date_str, day_picks, all_rows, suppress_ping=False):
    """Build the daily recap Discord embed.

    Three fully-separate records shown in header and footer:
      • Props    — primary + bonus, tier != KILLSHOT
      • KILLSHOT — primary/bonus with tier == KILLSHOT (only when present)
      • Parlays  — daily_lay + sgp + longshot (only when present)
    Week / month footer breaks down all three categories.
    """
    now_str = datetime.now(ZoneInfo("America/New_York")).strftime("%I:%M %p ET")

    _rt   = lambda p: p.get("run_type", "primary")
    _tier = lambda p: p.get("tier", "")

    # ── Day splits ────────────────────────────────────────────────────────────
    reg_props    = [p for p in day_picks if _rt(p) in PROP_RUN_TYPES and _tier(p) != "KILLSHOT"]
    ks_picks     = [p for p in day_picks if _rt(p) in PROP_RUN_TYPES and _tier(p) == "KILLSHOT"]
    parlay_picks = [p for p in day_picks if _rt(p) in PARLAY_RUN_TYPES]

    # Props record (non-KILLSHOT primary/bonus)
    w, l, pu, pl, roi = daily_stats(reg_props)
    pl_str  = f"+{pl:.2f}u" if pl >= 0 else f"{pl:.2f}u"
    roi_str = f"+{roi:.1f}%" if roi >= 0 else f"{roi:.1f}%"
    record  = f"**Props: {w}-{l}{'-%dP' % pu if pu else ''} · {pl_str} · ROI {roi_str}**"

    # KILLSHOT record (if any today)
    if ks_picks:
        ks_w, ks_l, ks_pu, ks_pl, _ = daily_stats(ks_picks)
        ks_pl_str = f"+{ks_pl:.2f}u" if ks_pl >= 0 else f"{ks_pl:.2f}u"
        ks_record_line = f"\n**⚡ KILLSHOT: {ks_w}-{ks_l} · {ks_pl_str}**"
    else:
        ks_record_line = ""

    # Parlay record (if any today)
    if parlay_picks:
        p_w, p_l, p_pu, p_pl, _ = daily_stats(parlay_picks)
        p_pl_str = f"+{p_pl:.2f}u" if p_pl >= 0 else f"{p_pl:.2f}u"
        parlay_record_line = f"\n**Parlays: {p_w}-{p_l} · {p_pl_str}**"
    else:
        parlay_record_line = ""

    # ── Streaks ───────────────────────────────────────────────────────────────
    grouped = get_graded_primary(all_rows)
    streak, _, _, _ = compute_streak(grouped)
    streak_line = f"\n🔥 **{streak} profitable days running**" if streak >= 2 else ""

    pick_streak_n, pick_streak_dir = compute_pick_streak(all_rows)
    if pick_streak_dir == "W" and pick_streak_n >= 3:
        pick_streak_line = f"\n📈 **{pick_streak_n} pick W streak**"
    elif pick_streak_dir == "L" and pick_streak_n >= 3:
        pick_streak_line = f"\n🧊 **{pick_streak_n}L run — model correction incoming**"
    else:
        pick_streak_line = ""

    # ── Pick list ─────────────────────────────────────────────────────────────
    pick_lines = [_recap_pick_line(p) for p in reg_props]

    if ks_picks:
        pick_lines.append("\n**⚡ KILLSHOT**")
        for p in ks_picks:
            pick_lines.append(_recap_pick_line(p))

    daily_lays = [p for p in parlay_picks if _rt(p) == "daily_lay"]
    if daily_lays:
        pick_lines.append("\n**📋 Daily Lay**")
        for p in daily_lays:
            pick_lines.append(_recap_pick_line(p))

    longshot_picks = [p for p in parlay_picks if _rt(p) == "longshot"]
    if longshot_picks:
        pick_lines.append("\n**🎯 Longshot**")
        for p in longshot_picks:
            pick_lines.append(_recap_pick_line(p))

    sgp_picks = [p for p in parlay_picks if _rt(p) == "sgp"]
    if sgp_picks:
        pick_lines.append("\n**🎲 Same-Game Parlay**")
        for p in sgp_picks:
            pick_lines.append(_recap_pick_line(p))

    # ── Week breakdown (props / KILLSHOT / parlays separately) ───────────────
    ref = datetime.strptime(date_str, "%Y-%m-%d")
    mon_str = (ref - timedelta(days=ref.weekday())).strftime("%Y-%m-%d")

    all_week = [r for r in all_rows
                if r.get("result") in ("W", "L", "P")
                and r.get("sport", "") not in SHADOW_SPORTS
                and r.get("run_type", "primary") in COUNTED_RUN_TYPES
                and mon_str <= r["date"] <= date_str]

    wk_reg = [p for p in all_week if _rt(p) in PROP_RUN_TYPES and _tier(p) != "KILLSHOT"]
    wk_ks  = [p for p in all_week if _rt(p) in PROP_RUN_TYPES and _tier(p) == "KILLSHOT"]
    wk_par = [p for p in all_week if _rt(p) in PARLAY_RUN_TYPES]

    ww, wl, _, wpl, _ = daily_stats(wk_reg)
    wpl_str = f"+{wpl:.1f}u" if wpl >= 0 else f"{wpl:.1f}u"
    week_str = f"Props {ww}-{wl} · {wpl_str}"
    if wk_ks:
        ks_ww, ks_wl, _, ks_wpl, _ = daily_stats(wk_ks)
        week_str += f" · ⚡ {ks_ww}-{ks_wl} · {('+' if ks_wpl >= 0 else '')}{ks_wpl:.1f}u"
    if wk_par:
        pw, p_l_, _, ppl, _ = daily_stats(wk_par)
        week_str += f" · Parlays {pw}-{p_l_} · {('+' if ppl >= 0 else '')}{ppl:.1f}u"

    # ── Month breakdown ───────────────────────────────────────────────────────
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    all_month = [r for r in all_rows
                 if r.get("result") in ("W", "L", "P")
                 and r.get("sport", "") not in SHADOW_SPORTS
                 and r.get("run_type", "primary") in COUNTED_RUN_TYPES
                 and r["date"].startswith(f"{dt.year}-{dt.month:02d}-")
                 and r["date"] <= date_str]

    month_line = ""
    if len(all_month) >= 5:
        mo_reg = [p for p in all_month if _rt(p) in PROP_RUN_TYPES and _tier(p) != "KILLSHOT"]
        mo_ks  = [p for p in all_month if _rt(p) in PROP_RUN_TYPES and _tier(p) == "KILLSHOT"]
        mo_par = [p for p in all_month if _rt(p) in PARLAY_RUN_TYPES]

        mw, ml, _, mpl, _ = daily_stats(mo_reg)
        mo_str = f"Props {mw}-{ml} · {('+' if mpl >= 0 else '')}{mpl:.1f}u"
        if mo_ks:
            ks_mw, ks_ml, _, ks_mpl, _ = daily_stats(mo_ks)
            mo_str += f" · ⚡ {ks_mw}-{ks_ml} · {('+' if ks_mpl >= 0 else '')}{ks_mpl:.1f}u"
        if mo_par:
            pmw, pml, _, pmpl, _ = daily_stats(mo_par)
            mo_str += f" · Parlays {pmw}-{pml} · {('+' if pmpl >= 0 else '')}{pmpl:.1f}u"
        month_line = f"**{dt.strftime('%B')}:** {mo_str}\n"

    color = 0x2ECC71 if pl >= 0 else 0xFF4444

    desc = (
        f"{record}{ks_record_line}{parlay_record_line}{streak_line}{pick_streak_line}\n\n"
        + "\n".join(pick_lines)
        + f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        + f"**This week:** {week_str}\n"
        + month_line
    ).rstrip()

    content = ""  # Daily recap posts silently — no @everyone ping

    return {
        "username": "PicksByJonny",
        "content": content,
        "embeds": [{
            "title": f"📊 {fmt_date(date_str)} Results",
            "description": desc,
            "color": color,
            "thumbnail": {"url": BRAND_LOGO},
            "footer": {"text": f"{BRAND_TAGLINE} · full transparency · {now_str}"}
        }]
    }


def build_monthly_embed(year, month, all_rows):
    """Build the monthly summary embed for a completed month."""
    month_name = MONTH_NAMES[month]
    picks = get_month_picks(all_rows, year, month)
    if not picks:
        return None

    w, l, pu, pl, roi = daily_stats(picks)
    pl_str  = f"+{pl:.2f}u" if pl >= 0 else f"{pl:.2f}u"
    roi_str = f"+{roi:.1f}%" if roi >= 0 else f"{roi:.1f}%"

    # Tier breakdown
    tier_stats = defaultdict(lambda: [0, 0, 0.0])  # tier → [w, l, pl]
    for p in picks:
        t   = p.get("tier", "T?")
        res = p.get("result", "")
        pick_pl = compute_pl(p.get("size", 0), p.get("odds", "-110"), res)
        if res == "W": tier_stats[t][0] += 1
        elif res == "L": tier_stats[t][1] += 1
        tier_stats[t][2] += pick_pl

    tier_lines = []
    for t in sorted(tier_stats.keys()):
        tw, tl, tpl = tier_stats[t]
        tpl_str = f"+{tpl:.1f}u" if tpl >= 0 else f"{tpl:.1f}u"
        tier_lines.append(f"{t}: {tw}-{tl} · {tpl_str}")

    # Best and worst pick
    pick_pls = [(p, compute_pl(p.get("size", 0), p.get("odds", "-110"), p.get("result", ""))) for p in picks]
    best  = max(pick_pls, key=lambda x: x[1], default=None)
    worst = min(pick_pls, key=lambda x: x[1], default=None)

    def pick_label(p, ppl):
        last = p.get("player", "").split()[-1].upper()
        dir_ = p.get("direction", "").upper()
        stat = p.get("stat", "")
        line = p.get("line", "")
        ppl_str = f"+{ppl:.2f}u" if ppl >= 0 else f"{ppl:.2f}u"
        return f"{last} {dir_} {line} {stat} · {ppl_str}"

    desc = (
        f"**{w}-{l}{'-%dP' % pu if pu else ''} · {pl_str} · ROI {roi_str}**\n\n"
        + "\n".join(tier_lines)
    )
    if best:
        desc += f"\n\n**Best pick:** {pick_label(*best)}"
    if worst and worst != best:
        desc += f"\n**Worst pick:** {pick_label(*worst)}"
    desc += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━\n{BRAND_TAGLINE}"

    color = 0xFFD700 if pl >= 0 else 0xFF4444

    return {
        "username": "PicksByJonny",
        "content": "@everyone",
        "embeds": [{
            "title": f"📅 {month_name} {year} — Final",
            "description": desc,
            "color": color,
            "footer": {"text": f"picksbyjonny · {MONTH_NAMES[(month % 12) + 1]} starts now"}
        }]
    }


def build_streak_embed(streak, streak_pl=0.0, streak_w=0, streak_l=0):
    """Build the streak announcement embed with P/L stats and milestone copy."""
    pl_str  = f"{streak_pl:+.2f}u"
    rec_str = f"{streak_w}W · {streak_l}L"

    if streak >= 7:
        title = "🔥 WEEK-LONG STREAK"
        headline = f"**{streak} days straight in the green.**\nThis is what the edge looks like."
    elif streak >= 5:
        title = "🔥 5-DAY STREAK"
        headline = f"**{streak} consecutive profitable days.**\nThe model doesn't miss."
    elif streak >= 3:
        title = "🔥 STREAK ALERT"
        headline = f"**{streak} profitable days in a row.**\nMomentum is real."
    else:
        title = "🔥 STREAK ALERT"
        headline = f"**{streak} consecutive profitable days.**\nLet's keep it going."

    desc = (
        f"{headline}\n\n"
        f"📈 **Streak P/L:** {pl_str}\n"
        f"📊 **Record:** {rec_str}\n\n"
        f"Full breakdown in **#daily-recap**."
    )

    return {
        "username": "PicksByJonny",
        "content": "@everyone",
        "embeds": [{
            "title": title,
            "description": desc,
            "color": 0xFF8C00,
            "thumbnail": {"url": BRAND_LOGO},
            "footer": {"text": BRAND_TAGLINE},
        }]
    }


def _read_rows_locked(log_path, lock_timeout=30):
    """Grader-flavoured wrapper: shares the same lock/read semantics as
    pick_log_io.read_rows_locked but routes the fall-through warning
    through the grader's file logger. The canonical helper lives in
    pick_log_io.py (audit H-8 / M-series)."""
    log_path_s = str(log_path)
    lock_path = log_path_s + ".lock"

    def _do_read():
        with open(log_path_s, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fieldnames = reader.fieldnames or []
        return rows, fieldnames

    try:
        with FileLock(lock_path, timeout=lock_timeout):
            return _do_read()
    except FileLockTimeout:
        logger.error(
            f"[grade_picks] Could not acquire read lock on {lock_path} within "
            f"{lock_timeout}s — reading anyway (RISK OF STALE/PARTIAL DATA)"
        )
        return _do_read()


def _atomic_write_rows(log_path, fieldnames, rows, lock_timeout=30):
    """Atomically rewrite a pick_log CSV using a lockfile + tmp+rename.

    Matches the pattern in capture_clv.py so grade_picks and the CLV daemon
    can never clobber each other's writes. Falls back to a best-effort direct
    write with a loud warning if filelock isn't installed.
    """
    log_path = str(log_path)
    lock_path = log_path + ".lock"

    def _do_write():
        fd, tmp_path = tempfile.mkstemp(
            prefix=os.path.basename(log_path) + ".",
            suffix=".tmp",
            dir=os.path.dirname(log_path) or ".",
        )
        try:
            with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, log_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    try:
        with FileLock(lock_path, timeout=lock_timeout):
            _do_write()
    except FileLockTimeout:
        logger.error(f"[grade_picks] Could not acquire lock on {lock_path} within {lock_timeout}s — writing anyway (RISK OF CLOBBER)")
        _do_write()

    # Arch note #5: refresh the schema sidecar on every successful write so
    # readers can fail-fast on forward-incompatible drift. Sidecar failure
    # must never block grading — log and carry on.
    try:
        _write_schema_sidecar(log_path)
    except Exception as _sidecar_err:
        logger.warning(f"[grade_picks] schema sidecar write failed for {log_path}: {_sidecar_err}")


_GUARD_TTL_DAYS = 90

try:
    from discord_guard import (
        load_guard as _shared_load_guard,
        save_guard as _shared_save_guard,
        mark_posted as _shared_mark_posted,
        claim_post as _shared_claim_post,
        prune_guard as _shared_prune_guard,
    )
    _HAS_SHARED_GUARD = True
except ImportError:
    _HAS_SHARED_GUARD = False


def _prune_guard(guard):
    """Drop guard keys older than _GUARD_TTL_DAYS.

    Keys embed a YYYY-MM-DD date (e.g. 'recap:2026-04-14', 'killshot:2026-04-15:...').
    Any key that parses a date and exceeds the TTL is dropped. Keys without a
    parseable date are preserved.
    """
    # Use ET (naive) to match the ET convention used everywhere else in grade_picks.
    cutoff = datetime.now(ZoneInfo("America/New_York")).replace(tzinfo=None) - timedelta(days=_GUARD_TTL_DAYS)
    pruned = {}
    for key, val in guard.items():
        parts = key.split(":")
        keep = True
        for p in parts:
            if len(p) == 10 and p[4] == "-" and p[7] == "-":
                try:
                    dt = datetime.strptime(p, "%Y-%m-%d")
                    if dt < cutoff:
                        keep = False
                    break  # first date token is authoritative
                except ValueError:
                    continue
        if keep:
            pruned[key] = val
    return pruned


def _load_guard():
    """Load the discord_posted guard file. Returns a dict of {event_key: True}."""
    # Delegate to shared cross-process-safe helper if available
    if _HAS_SHARED_GUARD:
        return _shared_load_guard()
    try:
        with open(DISCORD_GUARD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_guard(guard):
    """Save the discord_posted guard file atomically (tmp+rename).

    Also prunes entries older than _GUARD_TTL_DAYS so the file doesn't grow
    unboundedly. Falls back to a best-effort direct write if the atomic
    rename fails (rare, e.g. cross-device).
    """
    # Delegate to shared cross-process-safe helper if available
    if _HAS_SHARED_GUARD:
        _shared_save_guard(guard)
        return
    try:
        atomic_write_json(DISCORD_GUARD_FILE, _prune_guard(guard))
    except Exception as e:
        logger.warning(f"[grade_picks] Atomic guard write failed ({e}) — falling back to direct write")
        with open(DISCORD_GUARD_FILE, "w", encoding="utf-8") as f:
            json.dump(guard, f, indent=2)
            f.flush()
            os.fsync(f.fileno())


def _already_posted(guard, event_key):
    """Return True if this event has already been posted to Discord."""
    return guard.get(event_key, False)


def _mark_posted(guard, event_key):
    """Mark an event as posted via atomic discord_guard.mark_posted.
    Also updates the local guard dict so subsequent _already_posted checks
    in the same run see the new state without another disk read.
    Fixes audit C3 (TOCTOU) + H3 (suppress_ping guard omission).
    """
    if _HAS_SHARED_GUARD:
        _shared_mark_posted(event_key)
    else:
        _save_guard(guard)  # fallback: save the locally-mutated dict
    guard[event_key] = True  # keep local view consistent


def post_grading_results(date_str, day_picks, all_rows, suppress_ping=False, force=False):
    """Post recap, streak announcement, and monthly summary if applicable.

    Uses a JSON guard file to prevent duplicate posts if grade_picks.py
    is run multiple times on the same day.
    suppress_ping: if True, omit @everyone (--test mode)
    force: if True, skip guard check and always post (--repost mode)
    """
    if not day_picks:
        return

    guard = _load_guard()

    # ── Daily recap ───────────────────────────────────────────
    recap_key = f"recap:{date_str}"
    if not force and _already_posted(guard, recap_key):
        print(f"  [Discord] ⏭️  Daily recap already posted for {date_str} — skipping")
    else:
        recap_payload = build_recap_embed(date_str, day_picks, all_rows, suppress_ping=suppress_ping)
        if _webhook_post(DISCORD_RECAP_WEBHOOK, recap_payload, label=f"daily recap {date_str}"):
            print(f"  [Discord] ✅ Daily recap posted for {date_str}")
            _mark_posted(guard, recap_key)

    # ── Results graphic PNG ───────────────────────────────────
    graphic_key = f"graphic:{date_str}"
    if not force and _already_posted(guard, graphic_key):
        print(f"  [Discord] ⏭️  Results graphic already posted for {date_str} — skipping")
    else:
        try:
            from results_graphic import post_results_graphic
            if post_results_graphic(date_str, day_picks, suppress_ping=suppress_ping):
                _mark_posted(guard, graphic_key)
        except ImportError:
            pass   # results_graphic.py not present or pillow not installed — non-fatal
        except Exception as _rg_err:
            print(f"  ⚠ Results graphic failed: {_rg_err}")

    # ── Streak announcement (skip in test mode) ───────────────
    if not suppress_ping:
        grouped = get_graded_primary(all_rows)
        streak, streak_pl, streak_w, streak_l = compute_streak(grouped)
        if streak >= 2 and DISCORD_ANNOUNCE_WEBHOOK:
            streak_key = f"streak:{date_str}"
            if not force and _already_posted(guard, streak_key):
                print(f"  [Discord] ⏭️  Streak announcement already posted for {date_str} — skipping")
            else:
                streak_payload = build_streak_embed(streak, streak_pl, streak_w, streak_l)
                if _webhook_post(DISCORD_ANNOUNCE_WEBHOOK, streak_payload, label=f"streak announcement ({streak} days)"):
                    print(f"  [Discord] ✅ Streak announcement posted ({streak} days)")
                    _mark_posted(guard, streak_key)

    # ── Monthly summary (fires only on the 1st of a new month) ───
    if not suppress_ping:
        today = datetime.now(ZoneInfo("America/New_York"))
        if today.day == 1:
            # Summarize the previous month
            prev_month = today.month - 1 if today.month > 1 else 12
            prev_year  = today.year if today.month > 1 else today.year - 1
            monthly_key = f"monthly:{prev_year}-{prev_month:02d}"
            if not force and _already_posted(guard, monthly_key):
                print(f"  [Discord] ⏭️  Monthly summary already posted for {MONTH_NAMES[prev_month]} {prev_year} — skipping")
            else:
                monthly_payload = build_monthly_embed(prev_year, prev_month, all_rows)
                if monthly_payload and _webhook_post(DISCORD_MONTHLY_WEBHOOK, monthly_payload,
                                                     label=f"monthly summary {MONTH_NAMES[prev_month]} {prev_year}"):
                    print(f"  [Discord] ✅ Monthly summary posted for {MONTH_NAMES[prev_month]} {prev_year}")
                    _mark_posted(guard, monthly_key)


# ============================================================
#  END DISCORD AUTOMATION
# ============================================================

def _load_log_rows(path_str):
    """Read a CSV log into list of dicts. Returns [] on missing/empty.

    Uses the pick_log FileLock so concurrent CLV-daemon writes can't serve
    a partial file (audit C-9).
    """
    p = Path(path_str)
    if not p.exists():
        return []
    try:
        rows, _ = _read_rows_locked(p)
        return rows
    except Exception as e:
        print(f"  ⚠ Could not read {p.name}: {e}")
        return []


def _grade_one_log(log_path_str, args, is_shadow=False,
                   recap_merge_logs=None, extra_dates=None):
    """Grade a single pick log file.

    is_shadow: if True, grades silently with no Discord post.
    recap_merge_logs: list of extra log paths to include in Discord recap aggregation
                      (e.g. pick_log_manual.csv rows merged into main log's recap).
    extra_dates: additional dates (set) that should trigger recap posting,
                 typically dates newly graded in a merge log.

    Returns tuple (graded_any: bool, dates_graded: set[str]).
    """
    extra_dates = set(extra_dates or [])
    recap_merge_logs = list(recap_merge_logs or [])

    log_path = Path(log_path_str)
    if not log_path.exists():
        if not is_shadow:
            print(f"  No pick log found at {log_path}")
        # Still allow recap from extra_dates if merge logs have graded rows
        if not is_shadow and extra_dates and not args.dry_run:
            _post_merged_recaps(extra_dates, [], recap_merge_logs, args)
        return (False, set())

    # ── Read all rows (audit C-9: locked read, matches writer) ──
    rows, fieldnames = _read_rows_locked(log_path)

    if not rows:
        if not is_shadow:
            print("  Pick log is empty")
        if not is_shadow and extra_dates and not args.dry_run:
            _post_merged_recaps(extra_dates, [], recap_merge_logs, args)
        return (False, set())

    label = f"[{log_path.name}]"

    # ── Repost mode: skip grading, just re-fire Discord embed ──
    if getattr(args, "repost", False) and not is_shadow:
        date_str = args.date
        if not date_str:
            print(f"  {label} --repost requires --date YYYY-MM-DD")
            return (False, set())
        # Repost: model picks only — no manual merge, no shadow sports
        day_picks = [r for r in rows
                     if r.get("date") == date_str
                     and r.get("result") in ("W", "L", "P")
                     and r.get("sport", "") not in SHADOW_SPORTS]
        if not day_picks:
            print(f"  {label} No graded picks found for {date_str}")
            return (False, set())
        print(f"  {label} Reposting recap for {date_str} ({len(day_picks)} picks)…")
        post_grading_results(date_str, day_picks, rows,
                             suppress_ping=args.test, force=True)
        return (True, {date_str})

    # ── Find ungraded picks ────────────────────────────────────
    # Audit M-23: use the inverse of TERMINAL_RESULTS as the allow-list.
    # A blank `result` ("" / None / whitespace) is ungraded; any of W/L/P/VOID
    # is terminal and must never be re-fetched or re-graded. Earlier code
    # used `result == ""` which coincidentally handled VOID correctly but
    # made the invariant implicit — a future maintainer adding a new
    # placeholder (e.g. "PENDING") would silently re-grade it.
    ungraded = []
    for i, row in enumerate(rows):
        if not _is_terminal_result(row.get("result")):
            if args.date and row.get("date") != args.date:
                continue
            ungraded.append((i, row))

    if not ungraded:
        if not is_shadow:
            print(f"  {label} All picks already graded!")
        # Still fire recap if merge logs had new grades for dates here
        if not is_shadow and extra_dates and not args.dry_run:
            _post_merged_recaps(extra_dates, rows, recap_merge_logs, args)
        return (False, set())

    if not is_shadow:
        print(f"\n  {label} Found {len(ungraded)} ungraded picks")

    # ── Fetch scores/stats for each date/sport ─────────────────
    dates_sports: dict[str, set] = {}
    for idx, row in ungraded:
        d = row["date"]
        s = row.get("sport", "")
        dates_sports.setdefault(d, set()).add(s)
        # Daily lay / longshot / SGP are always NBA — ensure NBA scores fetched
        if row.get("run_type", "").lower() in ("daily_lay", "longshot", "sgp"):
            dates_sports.setdefault(d, set()).add("NBA")

    all_scores: dict = {}        # (date, sport) → {game_key: game_data}
    all_player_stats: dict = {}  # (date, sport) → {player_name: stats}
    all_linescores: dict = {}    # (date, "MLB") → {game_key: innings_list}

    for date_str, sports in dates_sports.items():
        for sport in sorted(sports):
            if not sport:  # skip blank sport (e.g. daily_lay rows)
                continue
            if not is_shadow:
                print(f"\n  {label} Fetching {sport} data for {date_str}…")

            scores = fetch_scores(sport, date_str)
            # None = plan limit (422) — store None so grading loop skips the
            # game-complete gate and grades purely from stat APIs.
            # []   = valid API response with no completed games.
            if scores is None:
                scores_map = None
                count_str = "unavailable (plan limit)"
            else:
                scores_map = {f"{g.get('away_team','')} @ {g.get('home_team','')}": g for g in scores}
                count_str = f"{len(scores)} completed games"
            all_scores[(date_str, sport)] = scores_map
            if not is_shadow:
                print(f"    {count_str} found")

            pstats: dict = {}
            if sport == "NBA":
                pstats = fetch_nba_boxscore(date_str)
                # If Odds API scores unavailable (plan limit), fall back to ESPN
                # game scores so daily lay / game-line grading still works.
                if scores_map is None:
                    espn_scores = fetch_espn_game_scores(date_str)
                    if espn_scores:
                        all_scores[(date_str, sport)] = espn_scores
                        if not is_shadow:
                            print(f"    ESPN fallback: {len(espn_scores)} game scores loaded")
            elif sport == "NHL":
                pstats = fetch_nhl_boxscores(date_str)
            elif sport == "MLB":
                pstats = fetch_mlb_boxscores(date_str)
                # Also fetch inning-by-inning data for F5/NRFI grading
                ls_map = fetch_mlb_linescores(date_str)
                all_linescores[(date_str, "MLB")] = ls_map
                if not is_shadow:
                    print(f"    {len(ls_map)} MLB linescores fetched")
            all_player_stats[(date_str, sport)] = pstats
            if not is_shadow:
                print(f"    {len(pstats)} player stat lines found")

            time.sleep(0.5)

    # ── Grade each ungraded pick ───────────────────────────────
    graded_count = 0
    for idx, row in ungraded:
        date_str = row["date"]
        sport    = row.get("sport", "")
        stat     = row.get("stat", "")

        # all_scores values may be None when the Odds API returned 422 (plan
        # limit). Normalise to {} so callers don't crash on .items() etc.
        # grade_prop receives None explicitly so it skips the game-complete gate.
        _raw_scores = all_scores.get((date_str, sport))
        _scores_dict = _raw_scores if isinstance(_raw_scores, dict) else {}

        if row.get("run_type", "").lower() in ("longshot", "sgp"):
            result = grade_parlay_legs(row, all_player_stats, all_scores)
        elif row.get("run_type", "").lower() == "daily_lay":
            result = grade_daily_lay(row, all_scores)
        elif stat in GAME_LINE_STATS:
            ls = all_linescores.get((date_str, sport)) if sport == "MLB" else None
            result = grade_game_line(row, _scores_dict, linescores=ls)
        else:
            result = grade_prop(row, all_player_stats.get((date_str, sport), {}),
                                scores_by_game=_raw_scores)

        if result:
            # Defensive idempotency guard (audit M-23). The ungraded filter
            # above should already keep terminal rows out of this loop, but
            # if a future code path bypasses the filter we refuse to clobber
            # an existing W/L/P/VOID silently. Log the collision and skip.
            existing = rows[idx].get("result")
            if _is_terminal_result(existing):
                if not is_shadow:
                    print(
                        f"  \u26a0 M-23 skip: row {idx} already terminal "
                        f"({str(existing).strip().upper()}) \u2014 refusing to overwrite "
                        f"with fresh grade {result!r}. "
                        f"player={row.get('player','')!r} stat={stat!r} date={date_str}"
                    )
                continue
            rows[idx]["result"] = result
            graded_count += 1
            if not is_shadow:
                if result == "W":   emoji = "\u2705"
                elif result == "L": emoji = "\u274c"
                elif result == "P": emoji = "\u2796"
                else:               emoji = "\U0001f6ab"  # VOID
                print(f"  {emoji} {row.get('player','')} {row.get('direction','')} {row.get('line','')} {stat} \u2192 {result}")

    if not is_shadow:
        print(f"\n  {label} Graded {graded_count}/{len(ungraded)} picks")

    # \u2500\u2500 Write back \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    if not args.dry_run and graded_count > 0:
        _atomic_write_rows(log_path, fieldnames, rows)
        if not is_shadow:
            print(f"  \u2705 Updated {log_path}")
    elif args.dry_run and not is_shadow:
        print("  (dry run \u2014 no changes written)")

    # \u2500\u2500 Dates with new grades in this log \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    dates_from_this = {row["date"] for idx, row in ungraded
                       if rows[idx].get("result") in ("W", "L", "P")}

    # \u2500\u2500 Discord posting (skip for shadow sports) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    if not is_shadow and not args.dry_run:
        dates_for_recap = dates_from_this | extra_dates
        if dates_for_recap:
            _post_merged_recaps(dates_for_recap, rows, recap_merge_logs, args)

    return (graded_count > 0, dates_from_this)


def _post_merged_recaps(dates_for_recap, main_rows, recap_merge_logs, args):
    """Post Discord daily recaps for given dates.

    Only model-generated picks reach Discord (primary / bonus / daily_lay from
    the main log). Manual picks live in pick_log_manual.csv for personal
    tracking but are intentionally excluded from the recap. Shadow-sport picks
    that landed in pick_log.csv (e.g. a manually-overridden MLB bonus) are
    also excluded so they don't appear on the card.
    """
    # Note: recap_merge_logs is intentionally ignored here \u2014 manual picks
    # are not shown in Discord recaps. The parameter is kept for API compat.
    for date_str in sorted(dates_for_recap):
        day_picks = [r for r in main_rows
                     if r.get("date") == date_str
                     and r.get("result") in ("W", "L", "P")
                     and r.get("sport", "") not in SHADOW_SPORTS]
        if day_picks:
            post_grading_results(date_str, day_picks, main_rows,
                                 suppress_ping=args.test)


def main():
    parser = argparse.ArgumentParser(
        description="Grade pick_log.csv results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python grade_picks.py                        # Grade all ungraded picks
  python grade_picks.py --date 2026-04-13      # Grade specific date only
  python grade_picks.py --dry-run              # Preview without writing
  python grade_picks.py --test                 # Grade + post without @everyone ping
  python grade_picks.py --repost --date 2026-04-13           # Re-fire recap embed
  python grade_picks.py --repost --date 2026-04-13 --test    # Repost without ping
        """
    )
    parser.add_argument("--date",    default=None,  help="Grade / repost only this date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Preview grading without writing")
    parser.add_argument("--test",    action="store_true", help="Suppress @everyone ping (safe preview)")
    parser.add_argument("--repost",  action="store_true", help="Re-fire Discord recap for --date (skip grading)")
    parser.add_argument("--confirm", action="store_true", help="Prompt y/n before every Discord post")
    parser.add_argument("--pick-log-path", default=None,
                        help="Override main pick log path (default: ~/Documents/JonnyParlay/data/pick_log.csv). "
                             "Shadow logs are skipped when overridden.")
    args = parser.parse_args()

    if args.repost and not args.date:
        print("  ❌ --repost requires --date YYYY-MM-DD")
        import sys; sys.exit(1)

    global _CONFIRM_MODE
    _CONFIRM_MODE = args.confirm

    # ── Grade manual log silently FIRST (no Discord post of its own) ──
    # Manual picks live in their own file but are aggregated into the main
    # Discord daily recap so W/L totals and P&L are accurate.
    main_log_path = args.pick_log_path or PICK_LOG_PATH
    use_default_paths = not args.pick_log_path

    manual_dates: set[str] = set()
    if use_default_paths and not args.repost:
        _, manual_dates = _grade_one_log(PICK_LOG_MANUAL_PATH, args, is_shadow=True)

    # ── Grade main log (posts to Discord, includes manual rows in recap) ──
    merge_logs = [PICK_LOG_MANUAL_PATH] if use_default_paths else []
    _grade_one_log(main_log_path, args, is_shadow=False,
            