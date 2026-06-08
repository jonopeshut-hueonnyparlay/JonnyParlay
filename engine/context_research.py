#!/usr/bin/env python3
"""context_research.py — Per-game Opus research layer.

Calls Claude Opus to evaluate 15 contextual factors per game and writes
data/context_verdicts.json. run_picks.py reads this file and adds [CTX+]/[CTX-]
display tags at output time. Display-only in v1 — never blocks picks or
affects sizing. Gate: 50+ context-graded picks before any behavioral use.

Usage:
  python engine/context_research.py --sport NBA            # Odds API game list
  python engine/context_research.py --sport MLB --odds-only
  python engine/context_research.py nba.csv               # SaberSim CSV game list
"""

import argparse
import csv
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Path setup — works whether called from project root or engine/ ─────────────
_ENGINE_DIR = Path(__file__).resolve().parent
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

import secrets_config  # noqa: F401 — side-effect: loads .env into os.environ

try:
    import anthropic
except ImportError:
    sys.exit("anthropic package not installed. Run: pip install anthropic")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

_DATA_DIR = _ENGINE_DIR.parent / "data"
_OUT_PATH = _DATA_DIR / "context_verdicts.json"

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

# ── Research prompt ────────────────────────────────────────────────────────────

_RESEARCH_PROMPT = """\
You are a sharp sports betting analyst. Research the following game and evaluate \
15 contextual factors to determine whether the current market pricing is favorable \
(confirms sharp action) or should be faded.

Game: {game}
Sport: {sport}
Date: {date}

For each factor below, return "confirms" (edge-supporting), "fades" (edge-reducing), \
or "neutral" (no meaningful signal). Use real data and reasoning. \
If information is unavailable, return "neutral".

Factors:
- rlm: Reverse line movement — <30% public bets but line moved toward that side (sharp action)
- weather: Wind ≥10mph or precipitation at outdoor/exposed MLB parks
- travel: Westward 3+ timezone shift or back-to-back game disadvantage
- umpire: Umpire tendency impacting run environment (MLB only; neutral for other sports)
- era_fip: Starting pitcher ERA-FIP gap ≥1.0 (regression candidate; MLB only)
- bullpen: High-leverage bullpen IP in last 3 days (fatigue signal)
- pythag: Team significantly over/underperforming Pythagorean win expectation
- injury: Key injury not yet priced into the market
- rest: Rest advantage — one team has extra rest vs opponent on back-to-back
- home_away: Notable home/away split vs what the model assumes
- form: Recent 7-day form significantly better or worse than season average
- division: Divisional familiarity advantage (MLB repeated matchups within division)
- motivation: Playoff pressure, elimination game, tanking incentive
- line_move: Significant line move since open (direction and magnitude)
- public_sharp: Public-money fade signal — heavy public on one side with reverse line move

Respond ONLY with a JSON object in this exact format (no markdown, no explanation):
{{
  "factors": {{
    "rlm": "neutral",
    "weather": "neutral",
    "travel": "neutral",
    "umpire": "neutral",
    "era_fip": "neutral",
    "bullpen": "neutral",
    "pythag": "neutral",
    "injury": "neutral",
    "rest": "neutral",
    "home_away": "neutral",
    "form": "neutral",
    "division": "neutral",
    "motivation": "neutral",
    "line_move": "neutral",
    "public_sharp": "neutral"
  }},
  "summary": "One sentence summary of the key contextual signal."
}}
"""

# ── Core logic ─────────────────────────────────────────────────────────────────

def aggregate_verdict(factors: dict) -> tuple:
    """Aggregate per-factor signals into a single verdict and confidence score."""
    c = sum(1 for v in factors.values() if v == "confirms")
    f = sum(1 for v in factors.values() if v == "fades")
    if c - f >= 2:
        verdict = "confirms"
    elif f - c >= 2:
        verdict = "fades"
    else:
        verdict = "neutral"
    total = len(factors)
    confidence = round(max(c, f) / total, 2) if total else 0.0
    return verdict, confidence


def _parse_factors(raw: dict) -> dict:
    """Validate and normalise a raw factor dict from the API response."""
    out = {}
    for key in _FACTORS:
        val = raw.get(key, "neutral").strip().lower()
        out[key] = val if val in _VALID_VALUES else "neutral"
    return out


def research_game(game: str, sport: str, date_str: str, client) -> dict | None:
    """Call Opus to research one game. Returns a verdict dict or None on failure."""
    prompt = _RESEARCH_PROMPT.format(game=game, sport=sport, date=date_str)
    try:
        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=4096,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text
        text = text.strip()
        # Extract JSON — tolerate markdown code fences
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            logger.warning(f"No JSON found in response for {game}")
            return None
        data = json.loads(m.group())
        factors = _parse_factors(data.get("factors", {}))
        summary = str(data.get("summary", "")).strip()[:300]
        verdict, confidence = aggregate_verdict(factors)
        return {
            "game": game,
            "date": date_str,
            "sport": sport,
            "verdict": verdict,
            "confidence": confidence,
            "factors": factors,
            "summary": summary,
            "researched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        }
    except (anthropic.APIError, anthropic.APIConnectionError, anthropic.RateLimitError) as e:
        logger.warning(f"Anthropic API error for {game}: {e}")
        return None
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.warning(f"Parse error for {game}: {e}")
        return None


# ── Game list sources ──────────────────────────────────────────────────────────

def _fetch_games_from_odds_api(sport: str, api_key: str) -> list:
    """Pull today's games from The Odds API. Returns list of game-key strings."""
    import requests  # noqa: PLC0415
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
        from datetime import datetime, timezone, timedelta
        local_tz_offset = -6  # MDT (Mountain Daylight Time, UTC-6)
        local_tz = timezone(timedelta(hours=local_tz_offset))
        now_local = datetime.now(local_tz)
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
                ct_local = ct.astimezone(local_tz)
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
    """Extract unique game matchups from a SaberSim CSV.

    SaberSim CSVs have a 'Game' or 'Matchup' column with values like
    'BOS@NYY' or 'MIL@CHC 07:10PM ET'. We normalise to 'AWAY @ HOME' format.
    Falls back to cross-referencing the Odds API to get canonical full-name keys.
    """
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
                # Strip time suffix e.g. "07:10PM ET" or "07:10PM"
                raw = re.sub(r"\s+\d{1,2}:\d{2}[AP]M.*", "", raw, flags=re.IGNORECASE).strip()
                # Normalise BOS@NYY or BOS @ NYY → "BOS @ NYY"
                raw = re.sub(r"\s*@\s*", " @ ", raw)
                if "@" not in raw or raw in games_seen:
                    continue
                games_seen.add(raw)
                results.append({"game": raw, "sport": sport.upper()})
    except OSError as e:
        logger.error(f"Cannot read CSV {csv_path}: {e}")
    logger.info(f"Found {len(results)} games from CSV {csv_path}")
    return results


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Per-game contextual research via Claude Opus")
    parser.add_argument("csv", nargs="?", help="SaberSim CSV path (optional)")
    parser.add_argument("--sport", default="NBA", help="Sport: NBA, MLB, NHL, WNBA (default: NBA)")
    parser.add_argument("--odds-only", action="store_true", help="Use Odds API for game list (ignores CSV)")
    parser.add_argument("--dry-run", action="store_true", help="Print games without calling API")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key and not args.dry_run:
        sys.exit("ANTHROPIC_API_KEY not set. Add it to .env and re-run.")

    odds_key = os.environ.get("ODDS_API_KEY", "")

    # Build game list
    if args.odds_only or not args.csv:
        if not odds_key:
            sys.exit("ODDS_API_KEY not set. Add it to .env.")
        games = _fetch_games_from_odds_api(args.sport, odds_key)
    else:
        games = _parse_games_from_csv(args.csv, args.sport)

    if not games:
        print("No games found — nothing to research.")
        return

    print(f"Researching {len(games)} {args.sport} game(s) via Claude Opus...")
    if args.dry_run:
        for g in games:
            print(f"  {g['game']}")
        return

    client = anthropic.Anthropic(api_key=api_key)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    results = []

    for i, g in enumerate(games, 1):
        game_key = g["game"]
        sport = g["sport"]
        print(f"  [{i}/{len(games)}] {game_key} ...", end=" ", flush=True)
        verdict = research_game(game_key, sport, date_str, client)
        if verdict:
            results.append(verdict)
            print(f"{verdict['verdict']} ({verdict['confidence']:.0%})")
        else:
            print("skipped")
        if i < len(games):
            time.sleep(1)

    _OUT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {len(results)} verdict(s) to {_OUT_PATH}")


if __name__ == "__main__":
    main()
