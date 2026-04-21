#!/usr/bin/env python3
"""
capture_clv.py — Closing Line Value capture daemon.

Runs continuously throughout the day. For each game with logged picks,
fetches the best available odds close to game start and writes
closing_odds + clv to pick_log.csv (shadow logs skipped by default).

Usage:
    python capture_clv.py [--date YYYY-MM-DD]

Capture window: T-30 to T+3 min relative to game commence_time.
Poll interval: 2 minutes. ~15 pre-tip polling attempts per game.

CLV formula: clv = implied_prob(closing_odds) - implied_prob(your_odds)
  Positive = you beat the close (good). Negative = line moved in your favor
  before you bet but away by close (bad).

Supported stats:
  Game lines   — SPREAD, TOTAL, ML_FAV, ML_DOG (h2h/spreads/totals markets)
  F5           — F5_SPREAD, F5_TOTAL, F5_ML (same markets, first5_innings game)
  Player props — PTS, REB, AST, 3PM, SOG, K, OUTS, HA, HITS, TB, HRR, YARDS

Skipped stats: NRFI, YRFI, TEAM_TOTAL, GOLF_WIN, PARLAY (no standard API market).
Shadow logs: skipped by default (ENABLE_SHADOW_CLV = False). Flip when MLB goes live.
"""

from __future__ import annotations  # allows X | Y union hints on Python 3.9

import argparse
import atexit
import csv
import json
import math
import os
import signal
import sys
import time
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

import requests

# filelock is a hard dependency (audit C-1). Prevents races with run_picks.py
# appends and with the single-instance daemon lock.
try:
    from filelock import FileLock, Timeout as _FileLockTimeout
except ImportError as e:
    raise ImportError(
        "filelock is required for pick_log/daemon-instance safety. "
        "Install it: pip install filelock --break-system-packages"
    ) from e

# Canonical locked-reader helper — every pick_log reader must take the same
# FileLock as the writers (audit H-8 / M-series).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pick_log_io import read_rows_locked_if_exists  # noqa: E402

# Schema sidecar writer (audit arch note #5). Every writer path must refresh
# the sidecar after a successful write so readers can fail-fast on future
# schema drift without having to sniff the CSV header.
from pick_log_schema import write_schema_sidecar as _write_schema_sidecar  # noqa: E402

# Shared HTTP helpers (audit M-16). Canonical User-Agent on every outbound
# Odds API request so server-side logs can distinguish us from generic
# python-requests traffic.
from http_utils import default_headers  # noqa: E402

# Shared atomic-JSON writer (architectural note #2). Dedupes the tmp+fsync+
# replace dance that used to live inline at every guard-file / checkpoint
# save site.
from io_utils import atomic_write_json  # noqa: E402

# Shared structured logger (audit M-28). Warnings + errors route through
# the named logger so they land in clv_daemon.log with level + timestamp,
# while staying visible on the daemon's live terminal via the stderr
# stream handler. Intentional progress prints remain as ``print()`` —
# those are part of the daemon's interactive UX.
from engine_logger import get_logger  # noqa: E402

_LOG_PATH = str(Path(__file__).resolve().parent.parent / "data" / "clv_daemon.log")
logger = get_logger("capture_clv", log_path=_LOG_PATH)

# ── Constants (mirrors run_picks.py) ──────────────────────────────────────────

# Odds API key — loaded from environment or .env (see secrets_config.py).
# Covers audit C-5 (hardcoded API key).
from secrets_config import ODDS_API_KEY

ODDS_API_BASE = "https://api.the-odds-api.com/v4"

SPORT_KEYS = {
    "NBA": "basketball_nba",
    "NHL": "icehockey_nhl",
    "NFL": "americanfootball_nfl",
    "MLB": "baseball_mlb",
    "NCAAB": "basketball_ncaab",
    "NCAAF": "americanfootball_ncaaf",
}

# Sportsbook contracts — canonical definition in book_names.py (audit H-13).
from book_names import CO_LEGAL_BOOKS, BOOK_DISPLAY, display_book, norm_book  # noqa: E402

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
SKIP_STATS = {"NRFI", "YRFI", "TEAM_TOTAL", "GOLF_WIN", "PARLAY"}

# Capture window: T-30 min to T+3 min. Player prop markets are pulled from the
# Odds API feed at tip-off, and commence_time can shift backward by 10-20 min
# as the API reconciles scheduled vs actual start. Widening the pre-tip window
# to -30 gives the daemon multiple capture attempts before the shift lands us
# in a post-tip window where prop markets are already gone.
CAPTURE_BEFORE_SECS = 30 * 60
CAPTURE_AFTER_SECS  = 3 * 60
POLL_INTERVAL_SECS  = 120  # 2 minutes

# If the daemon is restarted after a crash, allow retry attempts until this many
# seconds past game start (was 600 = 10 min; extended to 30 min so a restart
# within half an hour of tip-off can still recover closing odds).
STALE_AFTER_SECS = 30 * 60


# ── Paths ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR     = Path(__file__).resolve().parent
ROOT_DIR       = SCRIPT_DIR.parent
DATA_DIR       = ROOT_DIR / "data"
PICK_LOG       = DATA_DIR / "pick_log.csv"
CHECKPOINT_PATH  = DATA_DIR / "clv_checkpoint.json"
# Daemon lockfile path is overridable via env var so tests can run with a
# sandboxed lockfile without colliding with a real host-side daemon.
DAEMON_LOCK_PATH = Path(os.environ.get("JONNYPARLAY_DAEMON_LOCK")
                        or (DATA_DIR / "clv_daemon.lock"))
# Shadow logs are disabled by default — sports listed here go to their
# shadow log but the CLV daemon skips them (markets often don't exist in
# Odds API for shadow sports, burns API calls). Flip `ENABLE_SHADOW_CLV`
# to True when a sport goes live if you want CLV on the ramp-up days.
ENABLE_SHADOW_CLV = False
_ALL_SHADOW_LOGS = {
    "MLB": DATA_DIR / "pick_log_mlb.csv",
}
SHADOW_LOGS = _ALL_SHADOW_LOGS if ENABLE_SHADOW_CLV else {}


# ── Checkpoint helpers ────────────────────────────────────────────────────────

def load_checkpoint(run_date: str) -> set[str]:
    """Load the set of already-captured game strings for this date.
    Survives daemon restarts so we don't re-fetch already-captured games.
    Returns empty set if file missing or date mismatch.
    """
    try:
        with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("date") != run_date:
            return set()
        return set(data.get("captured_games", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_checkpoint(run_date: str, captured_games: set[str]) -> None:
    """Atomically persist captured_games to disk.

    Uses the shared ``io_utils.atomic_write_json`` helper so the fsync /
    tmp-cleanup contract is identical to every other JSON writer in the
    engine.  Failures are logged and swallowed — losing a checkpoint
    costs us (at most) one duplicate capture attempt, which the T-30
    window semantics absorb.
    """
    try:
        atomic_write_json(
            CHECKPOINT_PATH,
            {"date": run_date, "captured_games": sorted(captured_games)},
        )
    except Exception as e:
        logger.warning("Checkpoint save failed: %s", e)


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


# ── Odds API HTTP helper with 429/5xx retry (audit C-11) ──────────────────────
#
# The old code caught every exception with a blanket `except Exception` and
# treated the poll cycle as lost. Under a 429 rate-limit response that throws
# away a whole capture window even though a single backoff + retry would have
# succeeded. This helper centralises retry behaviour:
#
#   * 429: honour `Retry-After` (in seconds) if present, otherwise exponential
#          backoff (2s → 4s → 8s, capped at MAX_BACKOFF_S).
#   * 5xx: transient — same exponential backoff.
#   * 4xx (other): permanent — fail fast, no retry.
#   * Connection / timeout: transient — same exponential backoff.
#
# Returns the decoded JSON body, or None on final failure. A dedicated
# `quota_low_warned` flag logs once when x-requests-remaining drops below the
# threshold so Jono sees it without flooding the log.

_ODDS_API_MAX_RETRIES = 3
_ODDS_API_BASE_BACKOFF_S = 2.0
_ODDS_API_MAX_BACKOFF_S = 60.0
_ODDS_API_QUOTA_WARN_THRESHOLD = 500  # log once when remaining quota drops below this
_quota_low_warned = False

# Audit L-8 (closed Apr 20 2026): when x-requests-remaining hits 0 the old
# code kept hammering the API, chewing through 429s and wasting daemon poll
# cycles. Now we record a UTC "quota exhausted until" timestamp and the
# helper short-circuits every subsequent request until the window passes.
# The Odds API daily quota resets at the UTC boundary for standard plans,
# so parking the daemon until next UTC midnight is the correct conservative
# behavior. The main loop calls is_quota_exhausted() each iteration and
# sleeps a normal POLL_INTERVAL instead of burning requests.
_quota_exhausted_until: "datetime | None" = None


def _next_utc_quota_reset(now: "datetime | None" = None) -> "datetime":
    """Return the next UTC midnight (the Odds API's assumed quota reset).

    Hoisted out as a pure function so the regression test can pin 'now' and
    verify the rollover math without patching datetime at module scope.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def is_quota_exhausted() -> bool:
    """True while we've observed quota=0 and haven't reached the reset yet.

    Side-effect: if the current time is past the recorded reset window, the
    flag is auto-cleared. That keeps the daemon self-healing — no operator
    intervention needed after the Odds API rolls over for the day.
    """
    global _quota_exhausted_until
    if _quota_exhausted_until is None:
        return False
    if datetime.now(timezone.utc) >= _quota_exhausted_until:
        _quota_exhausted_until = None
        print("    [odds-api] Quota window elapsed — resuming normal polling")
        return False
    return True


def _mark_quota_exhausted() -> None:
    """Park the daemon on quota=0 until next UTC midnight. Idempotent."""
    global _quota_exhausted_until
    if _quota_exhausted_until is not None:
        return  # already marked — don't reset the deadline
    reset_at = _next_utc_quota_reset()
    _quota_exhausted_until = reset_at
    print(
        f"    ⚠ Odds API quota exhausted (x-requests-remaining=0) — "
        f"sleeping daemon until {reset_at.strftime('%Y-%m-%d %H:%M UTC')}"
    )


def _reset_quota_state_for_tests() -> None:
    """Test-only hook — reset module state between tests. Not part of the
    daemon's runtime surface. Named so the linter flags accidental calls."""
    global _quota_exhausted_until, _quota_low_warned
    _quota_exhausted_until = None
    _quota_low_warned = False


def _odds_api_get(url: str, params: dict, label: str) -> dict | list | None:
    """GET against the Odds API with backoff + 429 handling.

    `label` is a short tag used in the log line so multiple call sites are
    distinguishable (e.g. 'fetch_events(NBA)' vs 'fetch_game_odds(<id>)').
    """
    global _quota_low_warned

    # Audit L-8: once we've seen x-requests-remaining=0, every call is
    # guaranteed to return 429 until the UTC rollover. Skip them entirely so
    # the daemon's backoff math doesn't churn through retries on every poll.
    if is_quota_exhausted():
        return None

    last_err: str | None = None
    # Audit M-16: canonical UA stamps every Odds API call so operators
    # can identify JonnyParlay traffic in CDN / server-side logs.
    headers = default_headers()
    for attempt in range(1, _ODDS_API_MAX_RETRIES + 1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=10)
        except (requests.ConnectionError, requests.Timeout) as e:
            last_err = f"{type(e).__name__}: {e}"
            sleep_s = min(_ODDS_API_BASE_BACKOFF_S * (2 ** (attempt - 1)),
                          _ODDS_API_MAX_BACKOFF_S)
            logger.warning("%s: %s — retry %d/%d in %.0fs", label, last_err, attempt, _ODDS_API_MAX_RETRIES, sleep_s)
            time.sleep(sleep_s)
            continue
        except Exception as e:
            # Truly unexpected — don't retry, surface it.
            logger.error("%s: unexpected %s: %s", label, type(e).__name__, e)
            return None

        # Observe quota header when available (one-shot warning + hard-stop at 0).
        try:
            remaining = int(r.headers.get("x-requests-remaining", "-1"))
            if 0 <= remaining < _ODDS_API_QUOTA_WARN_THRESHOLD and not _quota_low_warned:
                logger.warning("Odds API quota low: %d requests remaining", remaining)
                _quota_low_warned = True
            # L-8: at 0 we park the daemon until the UTC rollover. Don't return
            # yet — the response body for *this* call may still be valid; we
            # just want the NEXT call to short-circuit.
            if remaining == 0:
                _mark_quota_exhausted()
        except (ValueError, TypeError):
            pass  # header missing / malformed — ignore

        if r.status_code == 429:
            # Honour Retry-After if the server sent one, else exponential backoff.
            retry_after_raw = r.headers.get("Retry-After", "")
            try:
                retry_after = min(float(retry_after_raw), _ODDS_API_MAX_BACKOFF_S)
            except ValueError:
                retry_after = min(_ODDS_API_BASE_BACKOFF_S * (2 ** (attempt - 1)),
                                  _ODDS_API_MAX_BACKOFF_S)
            last_err = f"HTTP 429 (rate-limited, retry-after {retry_after:.0f}s)"
            logger.warning("%s: %s — retry %d/%d", label, last_err, attempt, _ODDS_API_MAX_RETRIES)
            if attempt < _ODDS_API_MAX_RETRIES:
                time.sleep(retry_after)
            continue

        if 500 <= r.status_code < 600:
            last_err = f"HTTP {r.status_code} (server error)"
            sleep_s = min(_ODDS_API_BASE_BACKOFF_S * (2 ** (attempt - 1)),
                          _ODDS_API_MAX_BACKOFF_S)
            logger.warning("%s: %s — retry %d/%d in %.0fs", label, last_err, attempt, _ODDS_API_MAX_RETRIES, sleep_s)
            if attempt < _ODDS_API_MAX_RETRIES:
                time.sleep(sleep_s)
            continue

        if not r.ok:
            # 4xx other than 429 — won't succeed on retry.
            logger.error("%s: HTTP %d (no retry): %s", label, r.status_code, r.text[:200])
            return None

        # 2xx — parse JSON.
        try:
            return r.json()
        except ValueError as e:
            logger.error("%s: bad JSON response: %s", label, e)
            return None

    logger.error("%s: gave up after %d retries (%s)", label, _ODDS_API_MAX_RETRIES, last_err)
    return None


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
    result = _odds_api_get(url, params, label=f"fetch_game_odds({event_id})")
    return result if isinstance(result, dict) else {}


def fetch_events(sport_key: str) -> list[dict]:
    """Fetch event metadata (IDs + commence_times) for a sport.
    Uses the cheap /events endpoint — no odds, minimal quota cost.
    Full odds are only fetched per-event at capture time via fetch_game_odds().
    """
    url = f"{ODDS_API_BASE}/sports/{sport_key}/events"
    params = {"apiKey": ODDS_API_KEY}
    result = _odds_api_get(url, params, label=f"fetch_events({sport_key})")
    return result if isinstance(result, list) else []


def flatten_outcomes(event_data: dict) -> dict[str, list[dict]]:
    """Flatten bookmaker → market → outcomes into {market: [{name, description, price, point, book}]}.

    IMPORTANT: keep `name` and `description` distinct. For player props the Odds
    API returns name='Over'/'Under' and description=<player name>. Collapsing
    them into one field breaks direction matching downstream (the direction
    check `"over" in oc_name` fails when oc_name has been rewritten to the
    player name).
    """
    result: dict[str, list] = {}
    for bm in event_data.get("bookmakers", []):
        book = bm.get("key", "")
        for market in bm.get("markets", []):
            mkey = market.get("key", "")
            if mkey not in result:
                result[mkey] = []
            for oc in market.get("outcomes", []):
                result[mkey].append({
                    "name":        oc.get("name", ""),
                    "description": oc.get("description", ""),
                    "price":       oc.get("price"),
                    "point":       oc.get("point"),
                    "book":        book,
                })
    return result


# ── Pick log helpers ───────────────────────────────────────────────────────────

def load_picks(log_path: Path, run_date: str) -> list[dict]:
    """Load today's picks from a pick_log CSV. Returns all rows for the date.

    Shared FileLock — don't race a concurrent run_picks.py append or grader
    rewrite mid-read (audit H-8 / M-series).
    """
    rows, _ = read_rows_locked_if_exists(log_path)
    return [r for r in rows if r.get("date", "") == run_date]


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
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, log_path)

    # Arch note #5: refresh the schema sidecar on every successful write so
    # readers can fail-fast on forward-incompatible schema drift. Sidecar
    # failure must never block CLV writes — log and carry on.
    try:
        _write_schema_sidecar(log_path)
    except Exception as _sidecar_err:
        logger.warning("schema sidecar write failed for %s: %s", log_path, _sidecar_err)

    return updated


def write_closing_odds(log_path: Path, updates: dict[tuple, dict]) -> int:
    """Write closing_odds and clv back to pick_log.
    updates: {(player, stat, line, direction): {closing_odds, clv}}
    Returns count of rows updated.

    Uses a file lock to prevent racing against run_picks.py appends.
    filelock is a hard dependency — no fallback (audit C-1).
    """
    if not log_path.exists() or not updates:
        return 0

    lock_path = str(log_path) + ".lock"
    try:
        with FileLock(lock_path, timeout=30):
            return _do_write_closing_odds(log_path, updates)
    except _FileLockTimeout:
        logger.warning("Could not acquire lock on %s after 30s — skipping write", log_path.name)
        return 0


# ── Game matching ──────────────────────────────────────────────────────────────

def game_str_matches(pick_game: str, event_home: str, event_away: str) -> bool:
    """Check if a pick's game string matches an API event.
    pick_game format: 'Away Team @ Home Team' or abbreviation form.

    Strategy:
      1. If both full team names appear as substrings → match.
      2. Otherwise use word-level overlap with any word ≥ 3 chars (was ≥ 4 —
         that failed on 3-letter cities like "Los" in "Los Angeles" and short
         team nicknames).
    """
    g = pick_game.lower()
    h = event_home.lower()
    a = event_away.lower()

    # Preferred: full team name substring match
    if h in g and a in g:
        return True

    # Fallback: any word ≥ 3 chars from home + any word ≥ 3 chars from away
    h_words = [w for w in h.split() if len(w) >= 3]
    a_words = [w for w in a.split() if len(w) >= 3]
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
            # player field = "SD ML" / "NYY ML" / "F5 ML New York Yankees"
            # Two-letter abbrevs (SD, LA, SF, TB, KC, NY) fail the `len > 2`
            # filter, so fall back to is_home + the event's home/away team
            # names. If `is_home` is unset (legacy rows), fall back further to
            # a substring match on the player fragment inside both teams.
            team_frag = player.replace("F5 ML", "").replace(" ML", "").strip().lower()
            team_words = [w for w in team_frag.split() if len(w) > 2]

            is_home_raw = str(pick.get("is_home", "")).strip().lower()
            is_home_known = is_home_raw in ("true", "false", "1", "0", "yes", "no")
            is_home = is_home_raw in ("true", "1", "yes")

            target_team = ""
            if is_home_known and (home_team or away_team):
                target_team = (home_team if is_home else away_team).lower()
            target_words = [w for w in target_team.split() if len(w) > 2]

            best = None
            best_book = ""
            for oc in outcomes:
                book = oc.get("book", "")
                book_base = book.split("_")[0] if "_" in book else book
                if book not in CO_LEGAL_BOOKS and book_base not in CO_LEGAL_BOOKS:
                    continue
                oc_name = oc.get("name", "").lower()
                price = oc.get("price")
                if price is None:
                    continue

                matched = False
                # 1. Preferred: match against the pick's canonical team
                #    (home_team / away_team from the resolved event).
                if target_words and any(w in oc_name for w in target_words):
                    matched = True
                # 2. Fallback: match against the player-field fragment
                #    (covers 3+ letter abbrevs like MIA/COL/BOS and full names).
                elif team_words and any(w in oc_name for w in team_words):
                    matched = True
                # 3. Last resort: 2-letter abbrev substring inside the team
                #    name (e.g. "sd" in "san diego padres"). Only use when
                #    we couldn't resolve target_team from event metadata,
                #    since short abbrevs can collide.
                elif not target_words and team_frag and len(team_frag) == 2:
                    if team_frag in oc_name:
                        matched = True

                if matched and (best is None or price > best):
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
    # Odds API player props return:
    #   name        = "Over" / "Under"
    #   description = player full name ("LeBron James")
    # Match player via `description`, direction via `name`.
    player_lower = player.lower().replace("-", " ")  # normalise hyphens → spaces
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
        oc_name = oc.get("name", "").lower()          # "over" / "under"
        oc_desc = oc.get("description", "").lower()    # player name

        # Player match against description (fall back to name if description empty —
        # shouldn't happen for props but keeps us safe if a book returns a legacy
        # payload with player name in `name`).
        target = oc_desc or oc_name
        if not player_words or not any(w in target for w in player_words):
            continue
        if line is not None and point is not None and abs(float(point) - line) > 0.25:
            continue
        # Direction match against name ("Over"/"Under")
        if direction not in oc_name:
            continue
        if price is None:
            continue
        if best is None or price > best:
            best = price
            best_book = book

    return best, best_book


def calc_clv(your_odds: float, closing_odds: float) -> float:
    """CLV = closing_implied - your_implied. Positive = beat the close."""
    return implied_prob(closing_odds) - implied_prob(your_odds)


# ── Graceful shutdown (audit H-10) ─────────────────────────────────────────────
# Signal handlers flip a flag that the poll loop checks at safe boundaries.
# This way we never exit mid-write and always release the single-instance lock
# + persist the checkpoint. Matters most for Windows Task Scheduler "End task",
# which sends a shutdown signal that would otherwise kill the daemon before it
# can release DAEMON_LOCK_PATH, blocking the next run.

_shutdown_requested = False
_shutdown_signal_name: str | None = None


def _request_shutdown(signum, _frame):
    """Signal handler — only sets a flag. Actual cleanup happens in the main
    loop at a safe boundary, so we never interrupt a half-finished write or a
    filelock acquisition mid-way."""
    global _shutdown_requested, _shutdown_signal_name
    try:
        name = signal.Signals(signum).name
    except (ValueError, AttributeError):
        name = f"signal {signum}"
    # First signal: request clean exit. Second signal: let it propagate (hard kill).
    if _shutdown_requested:
        print(f"\n  ⚠ {name} received again — forcing immediate exit.", flush=True)
        # Restore default handler so a third signal can't be swallowed
        try:
            signal.signal(signum, signal.SIG_DFL)
        except (ValueError, OSError):
            pass
        raise SystemExit(1)
    _shutdown_requested = True
    _shutdown_signal_name = name
    print(f"\n  ⚠ {name} received — will exit cleanly at next safe boundary.", flush=True)


def _install_signal_handlers():
    """Bind SIGTERM/SIGINT (+ SIGBREAK on Windows) to the shutdown flag.
    Safe to call multiple times; safe on Windows where not all signals exist."""
    for sig_name in ("SIGTERM", "SIGINT", "SIGBREAK", "SIGHUP"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, _request_shutdown)
        except (ValueError, OSError):
            # Happens when called from a non-main thread, or when the OS
            # doesn't actually support delivering that signal.
            pass


def _interruptible_sleep(total_secs: float, chunk_secs: float = 2.0) -> bool:
    """Sleep up to `total_secs` but wake early if shutdown is requested.
    Returns True if the full duration elapsed, False if interrupted.

    Cross-platform: POSIX `time.sleep` is already EINTR-interruptible, but
    Windows `time.sleep` uses WaitForSingleObject which isn't — so we chunk
    the sleep and check the flag between chunks."""
    if total_secs <= 0:
        return not _shutdown_requested
    remaining = float(total_secs)
    while remaining > 0:
        if _shutdown_requested:
            return False
        slice_ = min(chunk_secs, remaining)
        time.sleep(slice_)
        remaining -= slice_
    return not _shutdown_requested


# ── Main daemon ────────────────────────────────────────────────────────────────

def run(run_date: str):
    """Main poll loop."""
    # ── Single-instance guard ─────────────────────────────────────────────────
    # Prevent two daemons from running concurrently (ghost-daemon scenario from
    # Session 8). filelock is now a hard dependency (audit C-1), so the guard
    # always runs.
    _daemon_lock = FileLock(str(DAEMON_LOCK_PATH), timeout=0)
    try:
        _daemon_lock.acquire()
        atexit.register(_daemon_lock.release)
        print(f"  [daemon] Lock acquired — PID {os.getpid()}")
    except _FileLockTimeout:
        print(
            f"  ⚠ Another CLV daemon instance is already running "
            f"(lock held: {DAEMON_LOCK_PATH}). Exiting to prevent double-capture."
        )
        sys.exit(0)

    # Install SIGTERM/SIGINT/SIGBREAK handlers AFTER the lock is acquired so a
    # signal during startup doesn't leave a stale lockfile. atexit.register is
    # still our safety net: the handler itself just sets a flag, and atexit
    # runs at normal process exit to release the daemon lock.
    _install_signal_handlers()

    print(f"\n{'─'*60}")
    print(f"  CLV Daemon — {run_date}")
    print(f"  Capturing T-{CAPTURE_BEFORE_SECS//60}min before each game")
    print(f"  Polling every {POLL_INTERVAL_SECS//60} min")
    print(f"{'─'*60}\n")

    # Track which games we've already captured to avoid double-writes.
    # Hydrate from checkpoint so a restart doesn't re-fetch already-done games.
    captured_games: set[str] = load_checkpoint(run_date)
    if captured_games:
        # ── Ghost-game integrity check ────────────────────────────────────────
        # A poisoned checkpoint (e.g. from a ghost daemon or ENABLE_SHADOW_CLV
        # flip) can mark games as captured when their picks still need CLV.
        # Cross-check: any game in captured_games whose picks still have empty
        # closing_odds gets evicted so the daemon retries them.
        all_today_picks: list[dict] = []
        for lp in [PICK_LOG] + list(SHADOW_LOGS.values()):
            all_today_picks.extend(load_picks(lp, run_date))
        needs_clv_games: set[str] = {
            p.get("game", "") for p in all_today_picks
            if not p.get("closing_odds", "").strip()
            and p.get("stat", "") not in SKIP_STATS
        }
        ghost_games = captured_games & needs_clv_games
        if ghost_games:
            print(f"  ⚠ Ghost game(s) detected in checkpoint — evicting and retrying:")
            for g in sorted(ghost_games):
                print(f"      {g}")
            captured_games -= ghost_games
            save_checkpoint(run_date, captured_games)
        print(f"  Resuming from checkpoint: {len(captured_games)} game(s) already captured\n")
    # Track fetch attempts per game — only give up after MAX_FETCH_ATTEMPTS transient failures.
    # Audit C-8: entries are evicted when a game is retired, and the dict is
    # capped at MAX_ATTEMPTS_ENTRIES (LRU) to stop it growing unboundedly
    # across the daemon's long-running lifetime.
    capture_attempts: "OrderedDict[str, int]" = OrderedDict()
    MAX_FETCH_ATTEMPTS = 3
    MAX_ATTEMPTS_ENTRIES = 500

    def _retire_game(game_str: str) -> None:
        """Mark a game fully processed: add to captured_games, persist the
        checkpoint, and drop any attempt counter. This is the only place that
        should advance captured_games so cleanup stays paired with the state
        change (prevents the capture_attempts leak in audit C-8).
        """
        captured_games.add(game_str)
        save_checkpoint(run_date, captured_games)
        capture_attempts.pop(game_str, None)

    def _bump_attempt(game_str: str) -> int:
        """Increment and return the attempt counter for `game_str`, with LRU
        eviction when the dict exceeds MAX_ATTEMPTS_ENTRIES (defence in depth
        for audit C-8 — in normal operation _retire_game keeps the dict small).
        """
        attempts = capture_attempts.get(game_str, 0) + 1
        capture_attempts[game_str] = attempts
        # Mark this key as most-recently-used for LRU semantics.
        capture_attempts.move_to_end(game_str)
        while len(capture_attempts) > MAX_ATTEMPTS_ENTRIES:
            old_key, _ = capture_attempts.popitem(last=False)
            logger.warning("capture_attempts cap hit (%d) — evicted oldest: %s", MAX_ATTEMPTS_ENTRIES, old_key)
        return attempts

    # All log files to update
    log_paths = [PICK_LOG] + list(SHADOW_LOGS.values())

    while True:
        # Audit H-10: bail at the top of each iteration if a signal was caught
        # during the previous sleep. All CSV writes happen inside FileLock
        # context managers that complete atomically before we get here, so this
        # is the safest possible boundary.
        if _shutdown_requested:
            print(f"\n  ⏹ Shutdown requested ({_shutdown_signal_name}) — "
                  f"persisting checkpoint and releasing lock.", flush=True)
            save_checkpoint(run_date, captured_games)
            return

        # Audit L-8: if we've exhausted the Odds API daily quota, skip the
        # entire fetch path and sleep one normal poll interval. is_quota_exhausted()
        # auto-clears the flag once the UTC rollover passes, so the daemon
        # self-heals without any operator intervention.
        if is_quota_exhausted():
            if not _interruptible_sleep(POLL_INTERVAL_SECS):
                continue  # next iter picks up the shutdown flag
            continue

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
                _interruptible_sleep(POLL_INTERVAL_SECS)
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
                    _retire_game(game_str)
                    continue

                # Fetch odds for this event
                event_id = event.get("id", "")
                event_data = fetch_game_odds(event_id, sport_key, list(markets_needed))
                if not event_data:
                    attempts = _bump_attempt(game_str)
                    if attempts >= MAX_FETCH_ATTEMPTS or secs_to_start < -STALE_AFTER_SECS:
                        print(f"    ⚠ No odds data for {event_id} (attempt {attempts}/{MAX_FETCH_ATTEMPTS}) — giving up")
                        _retire_game(game_str)
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

                    your_odds_str = f"{your_odds:+.0f}" if your_odds is not None else "n/a"
                    print(f"    ✓ {pick.get('player')[:30]} {pick.get('stat')} {pick.get('direction')}: "
                          f"got {your_odds_str}, close {closing_odds:+.0f} "
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
                    _retire_game(game_str)
                else:
                    attempts = _bump_attempt(game_str)
                    # Only give up once game is past the T+3 window — not based on attempt count.
                    # Props can be unavailable pre-tip and appear closer to game time.
                    if secs_to_start < -CAPTURE_AFTER_SECS:
                        print(f"    ⚠ Only got {captured_picks_for_game}/{total_picks_for_game} closing odds — past T+{CAPTURE_AFTER_SECS//60}min, giving up")
                        _retire_game(game_str)
                    else:
                        print(f"    ⏳ Got {captured_picks_for_game}/{total_picks_for_game} closing odds (attempt {attempts}) — will retry")

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
        _interruptible_sleep(POLL_INTERVAL_SECS)


def main():
    parser = argparse.ArgumentParser(description="CLV closing odds capture daemon")
    parser.add_argument("--date", default=None, help="Date to capture (YYYY-MM-DD, default: today)")
    args = parser.parse_args()

    if args.date:
        run_date = args.date
    else:
        # Match ET convention used by run_picks.py / grade_picks.py so a
        # pre-midnight-MT run doesn't grab the wrong day's picks.
        run_date = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

    try:
        run(run_date)
    except KeyboardInterrupt:
        print("\n\n  Daemon stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
