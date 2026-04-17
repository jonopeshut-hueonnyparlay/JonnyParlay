#!/usr/bin/env python3
"""
capture_clv.py — Closing Line Value capture daemon.

Runs continuously throughout the day. For each game with logged picks,
fetches the best available odds ~5 minutes before game start and writes
closing_odds + clv to pick_log.csv (and shadow logs).

Usage:
    python capture_clv.py [--date YYYY-MM-DD]

Capture window: T-5 to T+1 min relative to game commence_time.
Poll interval: 2 minutes.

CLV formula: clv = implied_prob(closing_odds) - implied_prob(your_odds)
  Positive = you beat the close (good). Negative = line moved in your favor
  before you bet but away by close (bad).

Supported stats:
  Game lines   — SPREAD, TOTAL, ML_FAV, ML_DOG (h2h/spreads/totals markets)
  F5           — F5_SPREAD, F5_TOTAL, F5_ML (same markets, first5_innings game)
  Player props — PTS, REB, AST, 3PM, SOG, K, OUTS, HA, HITS, TB, HRR, YARDS

Skipped stats: NRFI, YRFI, TEAM_TOTAL (no standard API market).
"""

from __future__ import annotations  # allows X | Y union hints on Python 3.9

import argparse
import csv
import math
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# Optional file lock to prevent race with run_picks.py appends.
try:
    from filelock import FileLock, Timeout as _FileLockTimeout
    _HAS_FILELOCK = True
except ImportError:
    _HAS_FILELOCK = False

# ── Constants (mirrors run_picks.py) ──────────────────────────────────────────

ODDS_API_KEY = "adb07e9742307895c8d7f14264f52aee"
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

SPORT_KEYS = {
    "NBA": "basketball_nba",
    "NHL": "icehockey_nhl",
    "NFL": "americanfootball_nfl",
    "MLB": "baseball_mlb",
    "NCAAB": "basketball_ncaab",
    "NCAAF": "americanfootball_ncaaf",
}

CO_LEGAL_BOOKS = {
    "draftkings", "fanduel", "betmgm", "williamhill_us", "betrivers",
    "bet365", "fanatics", "hardrockbet", "ballybet", "betparx",
    "espnbet", "pointsbetus", "twinspires", "circasports", "superbook",
    "tipico", "wynnbet", "betway",
}

BOOK_DISPLAY = {
    "draftkings": "DraftKings", "fanduel": "FanDuel", "betmgm": "BetMGM",
    "williamhill_us": "Caesars", "betrivers": "BetRivers", "bet365": "bet365",
    "fanatics": "Fanatics", "hardrockbet": "Hard Rock", "ballybet": "Bally",
    "betparx": "betPARX", "espnbet": "theScore Bet", "pointsbetus": "PointsBet",
    "twinspires": "TwinSpires", "circasports": "Circa", "superbook": "SuperBook",
    "tipico": "Tipico", "wynnbet": "WynnBET", "betway": "Betway",
}

# Maps our stat label → Odds API market key (for props)
STAT_TO_MARKET = {
    "PTS": "player_points",
    "REB": "player_rebounds",
    "AST": "player_assists",
    "3PM": "player_threes",
    "SOG": "player_shots_on_goal",
    "K":   "pitcher_strikeouts",
    "OUTS": "pitcher_outs",
    "HA":  "pitcher_hits_allowed",
    "HITS": "batter_hits",
    "TB":  "batter_total_bases",
    "HRR": "batter_hits_runs_rbis",
    "YARDS": "player_reception_yards",  # NFL — best available
}

# Game-line stats → which market to query
GAME_LINE_MARKET = {
    "SPREAD": "spreads",
    "ML_FAV": "h2h",
    "ML_DOG": "h2h",
    "TOTAL":  "totals",
    "F5_SPREAD": "spreads",
    "F5_ML":     "h2h",
    "F5_TOTAL":  "totals",
}

# Stats we skip (no standard market coverage)
SKIP_STATS = {"NRFI", "YRFI", "TEAM_TOTAL", "GOLF_WIN"}

# Capture window: T-5 min to T+1 min
CAPTURE_BEFORE_SECS = 5 * 60
CAPTURE_AFTER_SECS  = 1 * 60
POLL_INTERVAL_SECS  = 120  # 2 minutes


# ── Paths ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR  = Path(__file__).resolve().parent
ROOT_DIR    = SCRIPT_DIR.parent
DATA_DIR    = ROOT_DIR / "data"
PICK_LOG    = DATA_DIR / "pick_log.csv"
SHADOW_LOGS = {
    "MLB": DATA_DIR / "pick_log_mlb.csv",
}


# ── Odds API helpers ───────────────────────────────────────────────────────────

def implied_prob(american_odds: int | float) -> float:
    """Convert American odds to implied probability (raw, with vig)."""
    o = float(american_odds)
    if o < 0:
        return abs(o) / (abs(o) + 100)
    else:
        return 100 / (o + 100)


def best_price(outcomes: list[dict], direction: str, line: float | None = None) -> tuple[float | None, str]:
    """Find best American odds across CO_LEGAL_BOOKS for a given direction/line.
    Returns (best_odds, book_key) or (None, '').
    direction: 'over', 'under', 'home', 'away', or a team name fragment.
    line: for spreads/totals, must match within 0.25.
    """
    best_odds = None
    best_book = ""
    for outcome in outcomes:
        book = outcome.get("book", "")
        book_base = book.split("_")[0] if "_" in book else book
        if book not in CO_LEGAL_BOOKS and book_base not in CO_LEGAL_BOOKS:
            continue
        o_name = outcome.get("name", "").lower()
        o_price = outcome.get("price")
        o_point = outcome.get("point")
        if o_price is None:
            continue

        # Match direction
        dir_lower = direction.lower()
        name_match = (
            dir_lower in o_name
            or o_name in dir_lower
            or (dir_lower == "over" and "over" in o_name)
            or (dir_lower == "under" and "under" in o_name)
        )
        if not name_match:
            continue

        # Match line (spreads/totals): must be within 0.25
        if line is not None and o_point is not None:
            if abs(float(o_point) - float(line)) > 0.25:
                continue

        # Keep best (highest) odds
        if best_odds is None or o_price > best_odds:
            best_odds = o_price
            best_book = book

    return best_odds, best_book


def fetch_game_odds(event_id: str, sport_key: str, markets: list[str]) -> dict:
    """Fetch odds for a specific event. Returns bookmaker outcome data by market."""
    url = f"{ODDS_API_BASE}/sports/{sport_key}/events/{event_id}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": ",".join(markets),
        "oddsFormat": "american",
        "bookmakers": ",".join(CO_LEGAL_BOOKS),
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"    ⚠ fetch_game_odds error ({event_id}): {e}")
        return {}


def fetch_events(sport_key: str) -> list[dict]:
    """Fetch event metadata (IDs + commence_times) for a sport.
    Uses the cheap /events endpoint — no odds, minimal quota cost.
    Full odds are only fetched per-event at capture time via fetch_game_odds().
    """
    url = f"{ODDS_API_BASE}/sports/{sport_key}/events"
    params = {"apiKey": ODDS_API_KEY}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"    ⚠ fetch_events error ({sport_key}): {e}")
        return []


def flatten_outcomes(event_data: dict) -> dict[str, list[dict]]:
    """Flatten bookmaker → market → outcomes into {market: [{name, price, point, book}]}."""
    result: dict[str, list] = {}
    for bm in event_data.get("bookmakers", []):
        book = bm.get("key", "")
        for market in bm.get("markets", []):
            mkey = market.get("key", "")
            if mkey not in result:
                result[mkey] = []
            for oc in market.get("outcomes", []):
                result[mkey].append({
                    "name":  oc.get("description") or oc.get("name", ""),
                    "price": oc.get("price"),
                    "point": oc.get("point"),
                    "book":  book,
                })
    return result


# ── Pick log helpers ───────────────────────────────────────────────────────────

def load_picks(log_path: Path, run_date: str) -> list[dict]:
    """Load today's picks from a pick_log CSV. Returns all rows for the date."""
    if not log_path.exists():
        return []
    with open(log_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [r for r in reader if r.get("date", "") == run_date]


def picks_needing_clv(picks: list[dict]) -> list[dict]:
    """Filter to picks that haven't had closing odds captured yet and aren't graded."""
    return [
        p for p in picks
        if not p.get("closing_odds", "").strip()
        and p.get("stat", "") not in SKIP_STATS
    ]


def _do_write_closing_odds(log_path: Path, updates: dict[tuple, dict]) -> int:
    """Inner impl — assumes caller holds the file lock (if any)."""
    if not log_path.exists() or not updates:
        return 0

    with open(log_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    # Ensure columns exist
    if "closing_odds" not in fieldnames:
        fieldnames.append("closing_odds")
    if "clv" not in fieldnames:
        fieldnames.append("clv")

    updated = 0
    for row in rows:
        key = (
            row.get("player", "").strip().lower(),
            row.get("stat", "").strip(),
            str(row.get("line", "")).strip(),
            row.get("direction", "").strip().lower(),
        )
        if key in updates and not row.get("closing_odds", "").strip():
            row["closing_odds"] = str(updates[key]["closing_odds"])
            row["clv"] = f"{updates[key]['clv']:.4f}" if updates[key]["clv"] is not None else ""
            updated += 1

    # Atomic replace: write to tmp then os.replace — prevents partial writes
    # if the daemon is killed mid-write.
    tmp_path = log_path.with_suffix(log_path.suffix + ".tmp")
    with open(tmp_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    import os as _os
    _os.replace(tmp_path, log_path)

    return updated


def write_closing_odds(log_path: Path, updates: dict[tuple, dict]) -> int:
    """Write closing_odds and clv back to pick_log.
    updates: {(player, stat, line, direction): {closing_odds, clv}}
    Returns count of rows updated.

    Uses a file lock (when filelock is installed) to prevent racing against
    run_picks.py appends. Without the lock, concurrent appends from
    run_picks.py can be clobbered by this read-then-rewrite.
    """
    if not log_path.exists() or not updates:
        return 0

    if _HAS_FILELOCK:
        lock_path = str(log_path) + ".lock"
        try:
            with FileLock(lock_path, timeout=30):
                return _do_write_closing_odds(log_path, updates)
        except _FileLockTimeout:
            print(f"    ⚠ Could not acquire lock on {log_path.name} after 30s — skipping write")
            return 0
    else:
        # Fallback: no lock — warn once per process and do the write anyway.
        if not getattr(write_closing_odds, "_warned", False):
            print("    ⚠ filelock not installed — race with run_picks.py possible. "
                  "Run: pip install filelock --break-system-packages")
            write_closing_odds._warned = True
        return _do_write_closing_odds(log_path, updates)


# ── Game matching ──────────────────────────────────────────────────────────────

def game_str_matches(pick_game: str, event_home: str, event_away: str) -> bool:
    """Check if a pick's game string matches an API event.
    pick_game format: 'Away Team @ Home Team' or abbreviation form.
    """
    g = pick_game.lower()
    h = event_home.lower()
    a = event_away.lower()

    # Direct substring match on full team names
    h_words = [w for w in h.split() if len(w) > 3]
    a_words = [w for w in a.split() if len(w) > 3]

    home_match = any(w in g for w in h_words)
    away_match = any(w in g for w in a_words)
    return home_match and away_match


def find_event(pick_game: str, events: list[dict]) -> dict | None:
    """Find the best-matching API event for a pick's game string."""
    for ev in events:
        if game_str_matches(pick_game, ev.get("home_team", ""), ev.get("away_team", "")):
            return ev
    return None


# ── CLV capture logic ──────────────────────────────────────────────────────────

def get_closing_odds_for_pick(pick: dict, outcomes_by_market: dict,
                              home_team: str = "", away_team: str = "") -> tuple[float | None, str]:
    """Find best closing odds for a pick from the flattened outcomes dict.
    Returns (best_odds, book_key).
    home_team/away_team: event team names, used to fix F5_SPREAD fallback.
    """
    stat = pick.get("stat", "")
    direction = pick.get("direction", "").lower()
    line = pick.get("line")
    player = pick.get("player", "").strip()

    try:
        line = float(line) if line not in ("", None) else None
    except (ValueError, TypeError):
        line = None

    # ── Game lines ────────────────────────────────────────────────────────────
    if stat in GAME_LINE_MARKET:
        market_key = GAME_LINE_MARKET[stat]
        outcomes = outcomes_by_market.get(market_key, [])

        if stat in ("ML_FAV", "ML_DOG", "F5_ML"):
            # player field = "NYY ML" or "F5 ML New York Yankees"
            # Extract team from player field — last meaningful word(s)
            team_frag = player.replace("F5 ML", "").replace(" ML", "").strip().lower()
            # Try to match outcome name
            best = None
            best_book = ""
            for oc in outcomes:
                book = oc.get("book", "")
                book_base = book.split("_")[0] if "_" in book else book
                if book not in CO_LEGAL_BOOKS and book_base not in CO_LEGAL_BOOKS:
                    continue
                oc_name = oc.get("name", "").lower()
                # Team fragment must match: any word from team_frag in oc_name
                team_words = [w for w in team_frag.split() if len(w) > 2]
                if team_words and any(w in oc_name for w in team_words):
                    price = oc.get("price")
                    if price is not None and (best is None or price > best):
                        best = price
                        best_book = book
            return best, best_book

        elif stat in ("SPREAD", "F5_SPREAD"):
            # player field = "NYY -1.5" or "F5 New York Yankees"
            # is_home in pick tells us home vs away → match team name
            is_home = str(pick.get("is_home", "")).strip().lower() in ("true", "1", "yes")
            # We need to match by team in the outcome name
            # The player field has the team abbrev/name + line
            # Use is_home to pick the right side
            # Outcomes for spreads have team name + point
            best = None
            best_book = ""
            for oc in outcomes:
                book = oc.get("book", "")
                book_base = book.split("_")[0] if "_" in book else book
                if book not in CO_LEGAL_BOOKS and book_base not in CO_LEGAL_BOOKS:
                    continue
                price = oc.get("price")
                point = oc.get("point")
                if price is None or point is None:
                    continue
                # Must match line within 0.25
                if line is not None and abs(float(point) - line) > 0.25:
                    continue
                # Match home/away by sign of point (home favored → home has negative point)
                # This is imperfect — we'll use is_home as a tiebreaker
                # Better: match team name from player field
                oc_name = oc.get("name", "").lower()
                player_words = [w for w in player.replace("F5", "").split() if len(w) > 2 and not w.lstrip("-").replace(".","").isdigit()]
                if player_words and any(w.lower() in oc_name for w in player_words):
                    if best is None or price > best:
                        best = price
                        best_book = book
            # Fallback: use is_home + event team names when player-field name matching failed.
            # Without team context we'd grab the wrong side — use home_team/away_team if provided.
            if best is None and line is not None:
                target_team = (home_team if is_home else away_team).lower()
                target_words = [w for w in target_team.split() if len(w) > 2] if target_team else []
                for oc in outcomes:
                    book = oc.get("book", "")
                    book_base = book.split("_")[0] if "_" in book else book
                    if book not in CO_LEGAL_BOOKS and book_base not in CO_LEGAL_BOOKS:
                        continue
                    price = oc.get("price")
                    point = oc.get("point")
                    if price is None or point is None:
                        continue
                    if abs(float(point) - line) > 0.25:
                        continue
                    oc_name = oc.get("name", "").lower()
                    # Match by team name when available; otherwise accept any line match
                    if target_words and not any(w in oc_name for w in target_words):
                        continue
                    if best is None or price > best:
                        best = price
                        best_book = book
            return best, best_book

        elif stat in ("TOTAL", "F5_TOTAL"):
            outcomes = outcomes_by_market.get(market_key, [])
            best, book = best_price(outcomes, direction, line)
            return best, book

    # ── Player props ──────────────────────────────────────────────────────────
    market_key = STAT_TO_MARKET.get(stat)
    if not market_key:
        return None, ""

    outcomes = outcomes_by_market.get(market_key, [])
    # player field = "LeBron James" or "Shohei Ohtani"
    # outcome name = full player name
    player_lower = player.lower()
    player_words = [w for w in player_lower.split() if len(w) > 2]

    best = None
    best_book = ""
    for oc in outcomes:
        book = oc.get("book", "")
        book_base = book.split("_")[0] if "_" in book else book
        if book not in CO_LEGAL_BOOKS and book_base not in CO_LEGAL_BOOKS:
            continue
        price = oc.get("price")
        point = oc.get("point")
        oc_name = oc.get("name", "").lower()
        oc_desc = oc.get("description", oc_name).lower() if "description" in oc else oc_name

        if not player_words or not any(w in oc_desc for w in player_words):
            continue
        if line is not None and point is not None and abs(float(point) - line) > 0.25:
            continue
        # Match direction (Over/Under)
        dir_in_name = direction in oc_name or direction in oc_desc
        if not dir_in_name:
            continue
        if best is None or price > best:
            best = price
            best_book = book

    return best, best_book


def calc_clv(your_odds: float, closing_odds: float) -> float:
    """CLV = closing_implied - your_implied. Positive = beat the close."""
    return implied_prob(closing_odds) - implied_prob(your_odds)


# ── Main daemon ────────────────────────────────────────────────────────────────

def run(run_date: str):
    """Main poll loop."""
    print(f"\n{'─'*60}")
    print(f"  CLV Daemon — {run_date}")
    print(f"  Capturing T-{CAPTURE_BEFORE_SECS//60}min before each game")
    print(f"  Polling every {POLL_INTERVAL_SECS//60} min")
    print(f"{'─'*60}\n")

    # Track which games we've already captured to avoid double-writes
    captured_games: set[str] = set()
    # Track fetch attempts per game — only give up after MAX_FETCH_ATTEMPTS transient failures
    capture_attempts: dict[str, int] = {}
    MAX_FETCH_ATTEMPTS = 3
    # Age at which a captured price is considered stale (game started too long ago)
    STALE_AFTER_SECS = 600

    # All log files to update
    log_paths = [PICK_LOG] + list(SHADOW_LOGS.values())

    while True:
        now = datetime.now(timezone.utc)
        all_picks: list[tuple[Path, dict]] = []

        # Load today's un-captured picks across all logs
        for log_path in log_paths:
            picks = load_picks(log_path, run_date)
            open_picks = picks_needing_clv(picks)
            for p in open_picks:
                all_picks.append((log_path, p))

        if not all_picks:
            # Check if any picks exist today at all (may not have run picks yet)
            any_logged = any(
                len(load_picks(lp, run_date)) > 0
                for lp in log_paths if lp.exists()
            )
            if any_logged:
                # All logged picks already have CLV — done
                print(f"  [{now.strftime('%H:%M')} UTC] All picks captured — done for today.")
                break
            else:
                # run_picks.py hasn't run yet — keep waiting
                print(f"  [{now.strftime('%H:%M')} UTC] No picks logged yet — waiting for run_picks.py...")
                time.sleep(POLL_INTERVAL_SECS)
                continue

        # Group by sport
        picks_by_sport: dict[str, list[tuple[Path, dict]]] = {}
        for (log_path, p) in all_picks:
            sport = p.get("sport", "")
            picks_by_sport.setdefault(sport, []).append((log_path, p))

        # For each sport, fetch events and check capture window
        for sport, sport_picks in picks_by_sport.items():
            sport_key = SPORT_KEYS.get(sport)
            if not sport_key:
                continue

            events = fetch_events(sport_key)
            if not events:
                continue

            # Group picks by game
            picks_by_game: dict[str, list[tuple[Path, dict]]] = {}
            for (log_path, p) in sport_picks:
                game = p.get("game", "")
                picks_by_game.setdefault(game, []).append((log_path, p))

            for game_str, game_picks in picks_by_game.items():
                if game_str in captured_games:
                    continue

                event = find_event(game_str, events)
                if not event:
                    continue

                # Parse commence_time
                ct_str = event.get("commence_time", "")
                try:
                    ct = datetime.fromisoformat(ct_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    continue

                secs_to_start = (ct - now).total_seconds()

                # In capture window?
                if not (-CAPTURE_AFTER_SECS <= secs_to_start <= CAPTURE_BEFORE_SECS):
                    mins = int(secs_to_start / 60)
                    if mins > 0:
                        print(f"  [{now.strftime('%H:%M')}] {game_str[:45]}: T-{mins}min — waiting")
                    continue

                print(f"\n  🎯 CAPTURING: {game_str} (T{int(secs_to_start/60):+d}min)")

                # Determine which markets we need
                stats_needed = {p.get("stat", "") for (_, p) in game_picks}
                markets_needed = set()
                for s in stats_needed:
                    if s in GAME_LINE_MARKET:
                        markets_needed.add(GAME_LINE_MARKET[s])
                    elif s in STAT_TO_MARKET:
                        markets_needed.add(STAT_TO_MARKET[s])

                if not markets_needed:
                    captured_games.add(game_str)
                    continue

                # Fetch odds for this event
                event_id = event.get("id", "")
                event_data = fetch_game_odds(event_id, sport_key, list(markets_needed))
                if not event_data:
                    attempts = capture_attempts.get(game_str, 0) + 1
                    capture_attempts[game_str] = attempts
                    if attempts >= MAX_FETCH_ATTEMPTS or secs_to_start < -STALE_AFTER_SECS:
                        print(f"    ⚠ No odds data for {event_id} (attempt {attempts}/{MAX_FETCH_ATTEMPTS}) — giving up")
                        captured_games.add(game_str)
                    else:
                        print(f"    ⚠ No odds data for {event_id} (attempt {attempts}/{MAX_FETCH_ATTEMPTS}) — will retry")
                    continue

                outcomes_by_market = flatten_outcomes(event_data)

                # Group game_picks by log_path
                updates_by_log: dict[Path, dict] = {}
                ev_home = event.get("home_team", "")
                ev_away = event.get("away_team", "")
                for (log_path, pick) in game_picks:
                    closing_odds, closing_book = get_closing_odds_for_pick(
                        pick, outcomes_by_market, home_team=ev_home, away_team=ev_away
                    )
                    if closing_odds is None:
                        print(f"    — {pick.get('player')} {pick.get('stat')}: no closing odds found")
                        continue

                    your_odds = pick.get("odds")
                    try:
                        your_odds = float(your_odds)
                    except (ValueError, TypeError):
                        your_odds = None

                    clv = calc_clv(your_odds, closing_odds) if your_odds is not None else None
                    clv_str = f"{clv:+.1%}" if clv is not None else "n/a"

                    key = (
                        pick.get("player", "").strip().lower(),
                        pick.get("stat", "").strip(),
                        str(pick.get("line", "")).strip(),
                        pick.get("direction", "").strip().lower(),
                    )

                    if log_path not in updates_by_log:
                        updates_by_log[log_path] = {}
                    updates_by_log[log_path][key] = {
                        "closing_odds": closing_odds,
                        "clv": clv,
                    }

                    print(f"    ✓ {pick.get('player')[:30]} {pick.get('stat')} {pick.get('direction')}: "
                          f"got {your_odds:+.0f}, close {closing_odds:+.0f} "
                          f"({BOOK_DISPLAY.get(closing_book, closing_book)}) → CLV {clv_str}")

                # Write to CSVs
                for log_path, updates in updates_by_log.items():
                    n = write_closing_odds(log_path, updates)
                    print(f"    📝 Wrote {n} updates → {log_path.name}")

                # Only mark captured if all picks for this game got closing odds,
                # OR the game is already stale (>10 min past start). Partial captures
                # remain open so we retry missing picks on the next poll.
                total_picks_for_game = len(game_picks)
                captured_picks_for_game = sum(len(u) for u in updates_by_log.values())
                if captured_picks_for_game >= total_picks_for_game or secs_to_start < -STALE_AFTER_SECS:
                    captured_games.add(game_str)
                else:
                    attempts = capture_attempts.get(game_str, 0) + 1
                    capture_attempts[game_str] = attempts
                    if attempts >= MAX_FETCH_ATTEMPTS:
                        print(f"    ⚠ Only got {captured_picks_for_game}/{total_picks_for_game} closing odds after {attempts} attempts — giving up")
                        captured_games.add(game_str)
                    else:
                        print(f"    ⏳ Got {captured_picks_for_game}/{total_picks_for_game} closing odds (attempt {attempts}/{MAX_FETCH_ATTEMPTS}) — will retry")

        # Check if all picks are done
        remaining = sum(
            len(picks_needing_clv(load_picks(lp, run_date)))
            for lp in log_paths
            if lp.exists()
        )
        if remaining == 0:
            print(f"\n  ✅ All picks captured for {run_date}. Daemon exiting.")
            break

        print(f"\n  [{now.strftime('%H:%M')} UTC] {remaining} pick(s) pending capture. "
              f"Next check in {POLL_INTERVAL_SECS//60}min...\n")
        time.sleep(POLL_INTERVAL_SECS)


def main():
    parser = argparse.ArgumentParser(description="CLV closing odds capture daemon")
    parser.add_argument("--date", default=None, help="Date to capture (YYYY-MM-DD, default: today)")
    args = parser.parse_args()

    if args.date:
        run_date = args.date
    else:
        # Use local date (Mountain Time assumed, good enough for same-day runs)
        run_date = datetime.now().strftime("%Y-%m-%d")

    try:
        run(run_date)
    except KeyboardInterrupt:
        print("\n\n  Daemon stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
