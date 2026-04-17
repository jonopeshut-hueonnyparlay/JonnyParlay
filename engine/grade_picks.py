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

import csv, json, os, sys, time, argparse, calendar, logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo
try:
    import requests
except ImportError:
    print("  pip install requests --break-system-packages")
    sys.exit(1)

# ── Config ──────────────────────────────────────────────────
PICK_LOG_PATH      = os.path.expanduser("~/Documents/JonnyParlay/data/pick_log.csv")
PICK_LOG_MLB_PATH  = os.path.expanduser("~/Documents/JonnyParlay/data/pick_log_mlb.csv")
DISCORD_GUARD_FILE = os.path.expanduser("~/Documents/JonnyParlay/data/discord_posted.json")
LOG_FILE_PATH      = os.path.expanduser("~/Documents/JonnyParlay/data/jonnyparlay.log")

# All log paths — main log first, then shadow sport logs
ALL_LOG_PATHS = [PICK_LOG_PATH, PICK_LOG_MLB_PATH]
# Shadow sports: grade silently, no Discord post
SHADOW_SPORTS = {"MLB"}

BRAND_LOGO = "https://cdn.discordapp.com/attachments/1115840612915228727/1225636209221566625/JonnyParlaylogoRedBlack.png"

# ── File logger setup (file only — console output stays as print()) ───────────
_log_dir = Path(LOG_FILE_PATH).parent
_log_dir.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger("jonnyparlay")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _fh = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(_fh)
logger.propagate = False  # Don't bubble up to root logger (avoids duplicate prints)

# ── Discord Webhooks ─────────────────────────────────────────
DISCORD_RECAP_WEBHOOK   = "https://discord.com/api/webhooks/1493388658638848344/1RixaqCAX9kYdjrfDPt9bLKrr3Xn1LQmNvzWHAutT62k09dSsdhvOYBb18JhkS49mwU0"
DISCORD_MONTHLY_WEBHOOK = "https://discord.com/api/webhooks/1493398458357383420/YOxYOEjexatDSvAoGnNA-76dP1cX57jKj7frfvwR-4nosBjmXhCZkUKJ5efJ6dDoXkXr"
DISCORD_ANNOUNCE_WEBHOOK = "https://discord.com/api/webhooks/1493399935515889768/GV9M__Wd2ZC037gJ_3zFhjWKGDE_srWzhzQYWIAvmUpAscgRO1p-XjgkS0zVLgK_4s_x"  # → #announcements
ODDS_API_KEY = "adb07e9742307895c8d7f14264f52aee"
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


_BOOK_DISPLAY = {
    # CO_LEGAL_BOOKS — must match keys used by run_picks.py exactly
    "espnbet":        "theScore Bet",
    "hardrockbet":    "Hard Rock Bet",
    "draftkings":     "DraftKings",
    "fanduel":        "FanDuel",
    "williamhill_us": "Caesars",
    "betmgm":         "BetMGM",
    "betrivers":      "BetRivers",
    "ballybet":       "Bally Bet",
    "betparx":        "BetParx",
    "pointsbetus":    "PointsBet",
    "bet365":         "bet365",
    "fanatics":       "Fanatics",
    "twinspires":     "TwinSpires",
    "circasports":    "Circa",
    "superbook":      "SuperBook",
    "tipico":         "Tipico",
    "wynnbet":        "WynnBET",
    "betway":         "Betway",
    # Sharp / offshore / other books used in CLV comparison
    "unibet_us":      "Unibet",
    "lowvig":         "LowVig",
    "novig":          "Novig",
    "betonlineag":    "BetOnline",
    "mybookieag":     "MyBookie",
    "pinnacle":       "Pinnacle",
    "fliff":          "Fliff",
}


def display_book(key: str) -> str:
    """Map internal API book key to display name. Handles region suffixes (e.g. hardrockbet_fl)."""
    key_lower = key.lower()
    if key_lower in _BOOK_DISPLAY:
        return _BOOK_DISPLAY[key_lower]
    base = key_lower.rsplit("_", 1)[0] if "_" in key_lower else key_lower
    return _BOOK_DISPLAY.get(base, key.title())


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
    # The scores endpoint returns completed games
    params = {
        "apiKey": ODDS_API_KEY,
        "daysFrom": 3,  # look back 3 days
    }
    try:
        r = requests.get(f"{ODDS_BASE}/sports/{sk}/scores", params=params, timeout=15)
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
                         params={"dates": espn_date}, timeout=15)
        r.raise_for_status()
        events = r.json().get("events", [])
        player_stats = {}

        for event in events:
            event_id = event.get("id")
            try:
                box = requests.get(f"{ESPN_NBA_BASE}/summary",
                                   params={"event": event_id}, timeout=15)
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


def fetch_nhl_boxscores(date_str):
    """Fetch NHL player stats from NHL API."""
    try:
        r = requests.get(f"{NHL_STATS_BASE}/score/{date_str}", timeout=15)
        r.raise_for_status()
        data = r.json()
        player_stats = {}

        for game in data.get("games", []):
            game_id = game.get("id")
            try:
                box = requests.get(f"{NHL_STATS_BASE}/gamecenter/{game_id}/boxscore", timeout=15)
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
                        params={"sportId": 1, "date": date_str}, timeout=15)
        r.raise_for_status()
        data = r.json()
        player_stats = {}

        for date_entry in data.get("dates", []):
            for game in date_entry.get("games", []):
                game_pk = game.get("gamePk")
                try:
                    box = requests.get(f"{MLB_STATS_BASE}/game/{game_pk}/boxscore", timeout=15)
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
                         params={"sportId": 1, "date": date_str}, timeout=15)
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
                    ls = requests.get(f"{MLB_STATS_BASE}/game/{game_pk}/linescore", timeout=15)
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


def grade_daily_lay(row, all_scores):
    """Grade the daily lay parlay (always NBA). All legs must cover for W."""
    game_desc = row.get("game", "")
    date_str  = row.get("date", "")
    nba_scores = all_scores.get((date_str, "NBA"), {})
    if not nba_scores:
        return None

    legs_raw = [l.strip() for l in game_desc.split("/") if l.strip()]
    if not legs_raw:
        return None

    for leg in legs_raw:
        parts = leg.strip().split()
        if len(parts) < 2:
            return None
        abbrev = parts[0].upper()
        try:
            spread = float(parts[1])
        except ValueError:
            return None

        team_frag = NBA_ABBREV.get(abbrev, abbrev).lower()
        matched = None
        for key, gdata in nba_scores.items():
            if team_frag in key.lower():
                matched = gdata
                break
        if not matched:
            return None

        home_score, away_score = parse_score_from_api(matched)
        if home_score is None or away_score is None:
            return None

        home_team = matched.get("home_team", "").lower()
        is_away = team_frag not in home_team
        margin = (away_score - home_score) if is_away else (home_score - away_score)
        result_val = margin + spread
        if result_val < 0:
            return "L"
        if result_val == 0:
            return "P"
        # leg covered — continue

    return "W"


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
    Uses is_home field (logged since fix) when available; falls back to string
    matching for legacy rows that pre-date the fix.
    """
    is_home_field = pick.get("is_home", "")
    if is_home_field is not None and str(is_home_field).strip() != "":
        return str(is_home_field).strip().lower() in ("true", "1", "yes")
    # Fallback for old rows: string-match pick identifiers against away_team full name
    pick_team = pick.get("team", "").strip()
    player_field = pick.get("player", "").strip()
    is_away = False
    for identifier in [pick_team, player_field]:
        if identifier and any(t.lower() in away_team.lower() for t in identifier.split() if len(t) > 2):
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
    line = float(pick["line"])

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
            margin = (f5_home - f5_away) if pick_is_home else (f5_away - f5_home)
            result_val = margin + line
            if result_val > 0: return "W"
            elif result_val < 0: return "L"
            else: return "P"

        else:  # F5_ML
            pick_is_home = _resolve_pick_is_home(pick, away_team)
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
    line = float(pick["line"])
    direction = pick["direction"]

    # Gate: only grade if we can confirm the game is finished
    if scores_by_game is not None:
        if not _game_is_complete(pick, scores_by_game):
            return None  # Game not finished — don't grade yet

    # Try exact match first, then partial
    actual = None
    if player in player_stats:
        actual = player_stats[player].get(stat)
    else:
        # Fuzzy: try last name match
        last_name = player.split()[-1].lower() if player else ""
        for name, stats in player_stats.items():
            if last_name and last_name in name.lower():
                actual = stats.get(stat)
                break

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
    """
    if not url:
        return False
    if not _confirm_post(label):
        print(f"  [Confirm] ⏭️  Skipped: {label}")
        return False
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 429:
                retry_after = float(r.json().get("retry_after", backoff))
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
    """Compute units won/lost for a single pick."""
    try:
        size = float(size)
        odds = int(float(str(odds_str).replace("+", "")))
    except (ValueError, TypeError):
        return 0.0
    if result == "W":
        return round(size * (100 / abs(odds)), 4) if odds < 0 else round(size * (odds / 100), 4)
    elif result == "L":
        return round(-size, 4)
    return 0.0  # Push


def daily_stats(picks):
    """Return (W, L, P, total_pl, roi) for a list of graded picks."""
    w  = sum(1 for p in picks if p.get("result") == "W")
    l  = sum(1 for p in picks if p.get("result") == "L")
    pu = sum(1 for p in picks if p.get("result") == "P")
    pl = sum(compute_pl(p.get("size", 0), p.get("odds", "-110"), p.get("result", "")) for p in picks)
    risked = sum(float(p.get("size", 0)) for p in picks if p.get("result") != "P")
    roi = (pl / risked * 100) if risked > 0 else 0.0
    return w, l, pu, round(pl, 2), round(roi, 1)


COUNTED_RUN_TYPES = {"primary", "bonus", "manual", "daily_lay", "", None}

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


def get_week_picks(all_rows, ref_date_str):
    """Return all graded picks in the calendar week (Mon–Sun) of ref_date, up to ref_date."""
    ref = datetime.strptime(ref_date_str, "%Y-%m-%d")
    monday = ref - timedelta(days=ref.weekday())
    mon_str = monday.strftime("%Y-%m-%d")
    return [r for r in all_rows
            if r.get("result") in ("W", "L", "P")
            and r.get("run_type", "primary") in COUNTED_RUN_TYPES
            and mon_str <= r["date"] <= ref_date_str]


def get_month_picks(all_rows, year, month, up_to_date=None):
    """Return all graded picks in the given year/month, optionally capped at up_to_date."""
    prefix = f"{year}-{month:02d}-"
    return [r for r in all_rows
            if r.get("result") in ("W", "L", "P")
            and r.get("run_type", "primary") in COUNTED_RUN_TYPES
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
    """Build the daily recap Discord embed."""
    now_str = datetime.now(ZoneInfo("America/New_York")).strftime("%I:%M %p ET")

    # Day stats
    w, l, pu, pl, roi = daily_stats(day_picks)
    pl_str  = f"+{pl:.2f}u" if pl >= 0 else f"{pl:.2f}u"
    roi_str = f"+{roi:.1f}%" if roi >= 0 else f"{roi:.1f}%"
    record  = f"**{w}-{l}{'-%dP' % pu if pu else ''} · {pl_str} · ROI {roi_str}**"

    # Streak
    grouped = get_graded_primary(all_rows)
    streak, _, _, _ = compute_streak(grouped)
    streak_line = f"\n🔥 **{streak} profitable days running**" if streak >= 2 else ""

    # Pick lines
    pick_lines = [_recap_pick_line(p) for p in day_picks]

    # Week stats
    week_picks = get_week_picks(all_rows, date_str)
    ww, wl, wp, wpl, _ = daily_stats(week_picks)
    wpl_str = f"+{wpl:.1f}u" if wpl >= 0 else f"{wpl:.1f}u"

    # Month stats (only show when 5+ graded picks in the month, capped at recap date)
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    month_picks = get_month_picks(all_rows, dt.year, dt.month, up_to_date=date_str)
    mw, ml, mp, mpl, _ = daily_stats(month_picks)
    mpl_str = f"+{mpl:.1f}u" if mpl >= 0 else f"{mpl:.1f}u"
    month_line = f"**{dt.strftime('%B')}:** {mw}-{ml} · {mpl_str}\n" if len(month_picks) >= 5 else ""

    color = 0x2ECC71 if pl >= 0 else 0xFF4444

    desc = (
        f"{record}{streak_line}\n\n"
        + "\n".join(pick_lines)
        + f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        + f"**This week:** {ww}-{wl} · {wpl_str}\n"
        + month_line
    ).rstrip()

    content = "" if suppress_ping else "@everyone"

    return {
        "username": "PicksByJonny",
        "content": content,
        "embeds": [{
            "title": f"📊 {fmt_date(date_str)} Results",
            "description": desc,
            "color": color,
            "thumbnail": {"url": BRAND_LOGO},
            "footer": {"text": f"edge > everything · full transparency · {now_str}"}
        }]
    }


def build_monthly_embed(year, month, all_rows):
    """Build the monthly summary embed for a completed month."""
    month_name = calendar.month_name[month]
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
    desc += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━\nedge > everything"

    color = 0xFFD700 if pl >= 0 else 0xFF4444

    return {
        "username": "PicksByJonny",
        "content": "@everyone",
        "embeds": [{
            "title": f"📅 {month_name} {year} — Final",
            "description": desc,
            "color": color,
            "footer": {"text": f"picksbyjonny · {calendar.month_name[(month % 12) + 1]} starts now"}
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
            "footer": {"text": "edge > everything"},
        }]
    }


def _load_guard():
    """Load the discord_posted guard file. Returns a dict of {event_key: True}."""
    try:
        with open(DISCORD_GUARD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_guard(guard):
    """Save the discord_posted guard file."""
    os.makedirs(os.path.dirname(DISCORD_GUARD_FILE), exist_ok=True)
    with open(DISCORD_GUARD_FILE, "w", encoding="utf-8") as f:
        json.dump(guard, f, indent=2)


def _already_posted(guard, event_key):
    """Return True if this event has already been posted to Discord."""
    return guard.get(event_key, False)


def _mark_posted(guard, event_key):
    """Mark an event as posted and save the guard file."""
    guard[event_key] = True
    _save_guard(guard)


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
            if not suppress_ping:
                _mark_posted(guard, recap_key)

    # ── Results graphic PNG ───────────────────────────────────
    try:
        from results_graphic import post_results_graphic
        post_results_graphic(date_str, day_picks, suppress_ping=suppress_ping)
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
            if _already_posted(guard, monthly_key):
                print(f"  [Discord] ⏭️  Monthly summary already posted for {calendar.month_name[prev_month]} {prev_year} — skipping")
            else:
                monthly_payload = build_monthly_embed(prev_year, prev_month, all_rows)
                if monthly_payload and _webhook_post(DISCORD_MONTHLY_WEBHOOK, monthly_payload,
                                                     label=f"monthly summary {calendar.month_name[prev_month]} {prev_year}"):
                    print(f"  [Discord] ✅ Monthly summary posted for {calendar.month_name[prev_month]} {prev_year}")
                    _mark_posted(guard, monthly_key)


# ============================================================
#  END DISCORD AUTOMATION
# ============================================================

def _grade_one_log(log_path_str, args, is_shadow=False):
    """Grade a single pick log file. Returns True if any picks were graded.

    is_shadow: if True, grades silently with no Discord post.
    """
    log_path = Path(log_path_str)
    if not log_path.exists():
        if not is_shadow:
            print(f"  No pick log found at {log_path}")
        return False

    # ── Read all rows ──────────────────────────────────────────
    with open(log_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    if not rows:
        if not is_shadow:
            print("  Pick log is empty")
        return False

    label = f"[{log_path.name}]"

    # ── Repost mode: skip grading, just re-fire Discord embed ──
    if getattr(args, "repost", False) and not is_shadow:
        date_str = args.date
        if not date_str:
            print(f"  {label} --repost requires --date YYYY-MM-DD")
            return False
        day_picks = [r for r in rows
                     if r.get("date") == date_str and r.get("result") in ("W", "L", "P")]
        if not day_picks:
            print(f"  {label} No graded picks found for {date_str}")
            return False
        print(f"  {label} Reposting recap for {date_str} ({len(day_picks)} picks)…")
        post_grading_results(date_str, day_picks, rows,
                             suppress_ping=args.test, force=True)
        return True

    # ── Find ungraded picks ────────────────────────────────────
    ungraded = []
    for i, row in enumerate(rows):
        if (row.get("result") or "").strip() == "":
            if args.date and row.get("date") != args.date:
                continue
            ungraded.append((i, row))

    if not ungraded:
        if not is_shadow:
            print(f"  {label} All picks already graded!")
        return False

    if not is_shadow:
        print(f"\n  {label} Found {len(ungraded)} ungraded picks")

    # ── Fetch scores/stats for each date/sport ─────────────────
    dates_sports: dict[str, set] = {}
    for idx, row in ungraded:
        d = row["date"]
        s = row.get("sport", "")
        dates_sports.setdefault(d, set()).add(s)
        # Daily lay is always NBA — ensure we fetch NBA scores for its date
        if row.get("run_type", "").lower() == "daily_lay":
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
            scores_map = {f"{g.get('away_team','')} @ {g.get('home_team','')}": g for g in scores}
            all_scores[(date_str, sport)] = scores_map
            if not is_shadow:
                print(f"    {len(scores)} completed games found")

            pstats: dict = {}
            if sport == "NBA":
                pstats = fetch_nba_boxscore(date_str)
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

        if row.get("run_type", "").lower() == "daily_lay":
            result = grade_daily_lay(row, all_scores)
        elif stat in GAME_LINE_STATS:
            ls = all_linescores.get((date_str, sport)) if sport == "MLB" else None
            result = grade_game_line(row, all_scores.get((date_str, sport), {}), linescores=ls)
        else:
            result = grade_prop(row, all_player_stats.get((date_str, sport), {}),
                                scores_by_game=all_scores.get((date_str, sport), {}))

        if result:
            rows[idx]["result"] = result
            graded_count += 1
            if not is_shadow:
                if result == "W":   emoji = "✅"
                elif result == "L": emoji = "❌"
                elif result == "P": emoji = "➖"
                else:               emoji = "🚫"  # VOID
                print(f"  {emoji} {row.get('player','')} {row.get('direction','')} {row.get('line','')} {stat} → {result}")

    if not is_shadow:
        print(f"\n  {label} Graded {graded_count}/{len(ungraded)} picks")

    # ── Write back ─────────────────────────────────────────────
    if not args.dry_run and graded_count > 0:
        with open(log_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        if not is_shadow:
            print(f"  ✅ Updated {log_path}")
    elif args.dry_run and not is_shadow:
        print("  (dry run — no changes written)")

    # ── Discord posting (skip for shadow sports) ───────────────
    if not is_shadow and not args.dry_run and graded_count > 0:
        # Collect ALL graded picks for each date (not just newly-graded ones)
        # This fixes the straggler bug: one late pick shouldn't give a partial recap
        # Only trigger recap for dates that have at least one W/L/P (not just VOIDs)
        dates_graded = {row["date"] for _, row in ungraded
                        if rows[_].get("result") in ("W", "L", "P")}
        for date_str in sorted(dates_graded):
            day_picks = [r for r in rows
                         if r.get("date") == date_str and r.get("result") in ("W", "L", "P")]
            post_grading_results(date_str, day_picks, rows, suppress_ping=args.test)

    return graded_count > 0


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
    args = parser.parse_args()

    if args.repost and not args.date:
        print("  ❌ --repost requires --date YYYY-MM-DD")
        sys.exit(1)

    global _CONFIRM_MODE
    _CONFIRM_MODE = args.confirm

    # ── Grade main log (posts to Discord) ─────────────────────
    _grade_one_log(PICK_LOG_PATH, args, is_shadow=False)

    # ── Grade shadow logs silently (no Discord post) ───────────
    if not args.repost:
        for shadow_path in ALL_LOG_PATHS[1:]:
            _grade_one_log(shadow_path, args, is_shadow=True)


if __name__ == "__main__":
    main()
