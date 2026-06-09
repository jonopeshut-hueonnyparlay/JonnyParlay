#!/usr/bin/env python3
"""context_research.py — Per-game Opus research layer (5 parallel groups).

Researches each game in 5 independent factor groups (odds/lines, weather,
pitching, team/standings, roster/schedule), run in parallel across a single
thread pool. Per-factor verdicts are weighted (rlm/injury/line_move 3x;
era_fip/bullpen/public_sharp/motivation 2x; rest 1x) and aggregated into a
single verdict written to data/context_verdicts.json. run_picks.py reads
this file and adds [CTX+]/[CTX-] display tags at output time. Display-only
in v1 — never blocks picks or affects sizing. Gate: 50+ context-graded
picks before any behavioral use.

Each factor also carries data_quality (fresh/stale/failed) and a
neutral_reason so future behavioral logic can distinguish true neutrals
from data failures. Stale or failed data never drives a verdict — those
factors are overridden to neutral.

Results are cached per (game, local date): a re-run skips games already
researched today unless --refresh is passed. Writes merge into the existing
file (entries from other sports researched today are preserved; entries
from prior days are pruned).

Usage:
  python engine/context_research.py --sport NBA            # Odds API game list
  python engine/context_research.py --sport ALL            # all active sports, merged
  python engine/context_research.py --sport MLB --odds-only
  python engine/context_research.py nba.csv                # SaberSim CSV game list
  python engine/context_research.py --sport NBA --refresh  # bypass daily cache
"""

import argparse
import csv
import json
import logging
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
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
    import anthropic
except ImportError:
    sys.exit("anthropic package not installed. Run: pip install anthropic")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

_OUT_PATH = data_path("context_verdicts.json")

_MODEL = "claude-opus-4-8"
_WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search"}
# Worst case is 5 groups x 6 outdoor MLB games = 30 calls; sized so a full
# slate runs in a single concurrent wave (<2 min target with web search).
_MAX_WORKERS = 30

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
# closed): weather is hardcoded neutral, no research call is made.
_DOMED_HOME_TEAMS = frozenset({
    "Tampa Bay Rays",        # Tropicana Field
    "Toronto Blue Jays",     # Rogers Centre
    "Houston Astros",        # Minute Maid Park
    "Arizona Diamondbacks",  # Chase Field
    "Miami Marlins",         # loanDepot park
    "Seattle Mariners",      # T-Mobile Park
    "Texas Rangers",         # Globe Life Field
})

# ── Research groups ────────────────────────────────────────────────────────────

_GROUP1_BODY = """\
Research the betting market for this game ONLY (line movement, betting splits).

Run these web searches:
- "{away} vs {home} betting percentages splits {date}"
- "{away} vs {home} line movement since open {date}"
- site:actionnetwork.com "{away} {home}"
Preferred sources: Action Network, ESPN BET, Pregame.com, DonBest.

Evaluate these factors:
- rlm: Reverse line movement — <30% of public bets on a side but the line moved \
toward that side (sharp action). "confirms" if present.
- line_move: Significant line move since open. Threshold: a move of 1.5+ points \
is significant.
- public_sharp: Public-money fade signal — heavy public money on one side with \
reverse line movement.
"""

_GROUP2_BODY = """\
Research the weather for this outdoor MLB game ONLY.

Run this web search (use the home team's city — home team: {home}):
- "[home city] weather forecast {date} [game time] wind"
Preferred sources: weather.gov, Weather Underground.

Evaluate this factor:
- weather: Wind >=10mph blowing OUT = "confirms" (more runs). Wind >=10mph \
blowing IN = "fades" (fewer runs). Precipitation = "fades". Otherwise "neutral".
"""

_GROUP3_BODY = """\
Research starting pitchers, bullpens, and the home plate umpire for this MLB \
game ONLY.

First identify both starting pitchers and the home plate umpire, then run \
these web searches:
- "[pitcher name] ERA FIP 2026 site:fangraphs.com" (for each starter)
- "{away} bullpen usage last 3 days 2026"
- "{home} bullpen usage last 3 days 2026"
- "home plate umpire {away} {home} {date}"
- "[umpire name] runs per game tendency"
Preferred sources: FanGraphs (ERA/FIP), Baseball Reference (bullpen IP, \
umpire stats), UmpireAudit.com.

Evaluate these factors:
- era_fip: Starter ERA minus FIP gap >=1.0 = regression candidate (fades that \
pitcher's side).
- bullpen: High-leverage bullpen IP >=8 in the last 3 days = fatigue signal \
(fades that team).
- umpire: Home plate umpire runs/game vs league average >=0.4 = "confirms" the \
over (run-suppressing umpire by the same margin = "fades").
"""

_GROUP4_BODY = """\
Research team performance and standings context for this game ONLY.

Run these web searches (for BOTH teams where applicable):
- "{away} pythagorean record 2026 actual vs expected wins"
- "{home} pythagorean record 2026 actual vs expected wins"
- "{away} last 7 games results 2026"
- "{home} last 7 games results 2026"
- "{away} home away splits 2026"
- "{home} home away splits 2026"
- "{away} {home} playoff standings elimination {date} 2026"
Preferred sources: FanGraphs (pythag), ESPN, Baseball Reference, NBA.com, \
NHL.com, WNBA.com.

Evaluate these factors:
- pythag: Pythagorean expected wins vs actual wins differing by >=4 wins = \
significant over/underperformance.
- form: Last-7-games win% vs season win% differing by >=15 percentage points.
- division: Divisional familiarity advantage (repeated matchups within division).
- motivation: Elimination game, must-win pressure, or tanking incentive.
- home_away: Notable home/away split relevant to this matchup.
"""

_GROUP5_BODY = """\
Research injuries, rest, and travel for this game ONLY.

Run these web searches:
- "{away} injury report {date} 2026"
- "{home} injury report {date} 2026"
- "{away} {home} schedule {date} back to back"
- "{away} last game location {date}"
Preferred sources: ESPN injury pages, Rotoworld, RotoBaller, official team \
injury reports.

Evaluate these factors:
- injury: A key rotation player (top-8 rotation / starting lineup) out and not \
yet priced into the market.
- rest: One team on a back-to-back while the opponent has 2+ days rest.
- travel: Westward shift of 3+ timezones (e.g. West Coast to East Coast the \
previous night) = disadvantage.

RECENCY RULE: injury information must be from today. If the most recent injury \
report you can find is 2 or more days old, set data_quality to "stale" for the \
injury factor and its verdict to "neutral".
"""

_GROUPS = {
    1: {"name": "odds_lines", "factors": ["rlm", "line_move", "public_sharp"], "body": _GROUP1_BODY},
    2: {"name": "weather",    "factors": ["weather"],                          "body": _GROUP2_BODY},
    3: {"name": "pitching",   "factors": ["era_fip", "bullpen", "umpire"],     "body": _GROUP3_BODY},
    4: {"name": "team",       "factors": ["pythag", "form", "division", "motivation", "home_away"], "body": _GROUP4_BODY},
    5: {"name": "roster",     "factors": ["injury", "rest", "travel"],         "body": _GROUP5_BODY},
}

# Summary composition order: odds and roster signals lead.
_GROUP_SUMMARY_PRIORITY = [1, 5, 3, 4, 2]

_PROMPT_HEADER = """\
You are a sharp sports betting analyst evaluating whether market context \
supports ("confirms") or undermines ("fades") the current pricing of this game.

Game: {game} | Sport: {sport} | Date: {date}

"""

_PROMPT_RULES = """\

Data-quality rules (set per factor):
- "fresh": the data you found is from today or yesterday.
- "stale": a source was found but its most recent data is 2+ days old. Still \
report what you found, but mark data_quality "stale".
- If you cannot find relevant data for a factor, set its verdict to "neutral" \
and data_quality to "fresh".

Respond ONLY with a JSON object in this exact format (no markdown fences, \
no prose before or after):
"""


def _json_skeleton(group_id: int) -> str:
    """JSON response contract for one group's prompt."""
    lines = ["{", '  "factors": {']
    factors = _GROUPS[group_id]["factors"]
    for i, f in enumerate(factors):
        comma = "," if i < len(factors) - 1 else ""
        lines.append(
            f'    "{f}": {{"verdict": "confirms|fades|neutral", '
            f'"data_quality": "fresh|stale", '
            f'"evidence": "one short sentence citing the number you found"}}{comma}'
        )
    lines.append("  },")
    lines.append('  "summary": "One sentence: the strongest signal in this group, or \'no signal\'."')
    lines.append("}")
    return "\n".join(lines)


def _split_game(game: str) -> tuple:
    """Split 'AWAY @ HOME' into (away, home). Defensive on malformed keys."""
    parts = [p.strip() for p in game.split("@")]
    away = parts[0] if parts else game
    home = parts[-1] if len(parts) > 1 else game
    return away, home


def _build_group_prompt(group_id: int, game: str, sport: str, date_str: str) -> str:
    away, home = _split_game(game)
    body = _GROUPS[group_id]["body"].format(
        game=game, sport=sport, date=date_str, away=away, home=home,
    )
    header = _PROMPT_HEADER.format(game=game, sport=sport, date=date_str)
    return header + body + _PROMPT_RULES + _json_skeleton(group_id)


# ── Core logic ─────────────────────────────────────────────────────────────────

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


def _fast_path_result(group_id: int, game: str, sport: str) -> dict | None:
    """Group results that need no API call; None means research is required."""
    if group_id == 2 and _is_indoor(game, sport):
        return _hardcoded_group_result(2, "hardcoded_neutral")
    if group_id == 3 and sport.upper() != "MLB":
        return _hardcoded_group_result(3, "not_applicable")
    return None


def _parse_group_response(text: str, group_id: int) -> dict:
    """Extract and validate one group's JSON response.

    Raises ValueError when no JSON object is present (caller converts to a
    failed group). Per-factor validation is defensive: invalid verdict →
    neutral, invalid/missing data_quality or missing factor → failed.
    """
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("no JSON object in response")
    data = json.loads(m.group())
    raw_factors = data.get("factors", {})
    if not isinstance(raw_factors, dict):
        raw_factors = {}

    factors = {}
    for f in _GROUPS[group_id]["factors"]:
        entry = raw_factors.get(f)
        if not isinstance(entry, dict):
            factors[f] = {
                "verdict": "neutral", "data_quality": "failed",
                "neutral_reason": "source_failed", "evidence": "",
            }
            continue
        verdict = str(entry.get("verdict", "neutral")).strip().lower()
        if verdict not in _VALID_VALUES:
            verdict = "neutral"
        quality = str(entry.get("data_quality", "failed")).strip().lower()
        if quality not in _DATA_QUALITY_VALUES:
            quality = "failed"
        factors[f] = {
            "verdict": verdict,
            "data_quality": quality,
            "neutral_reason": None,
            "evidence": str(entry.get("evidence", "")).strip()[:120],
        }
    summary = str(data.get("summary", "")).strip()
    return {"factors": factors, "summary": summary}


def _research_group(client, game: str, sport: str, date_str: str, group_id: int) -> dict:
    """One API call for one group. Never raises — failures degrade to a
    failed group result so one group cannot kill the game or its siblings."""
    try:
        prompt = _build_group_prompt(group_id, game, sport, date_str)
        response = client.messages.create(
            model=_MODEL,
            max_tokens=4096,
            tools=[_WEB_SEARCH_TOOL],
            messages=[{"role": "user", "content": prompt}],
        )
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text
        return _parse_group_response(text.strip(), group_id)
    except Exception as e:  # noqa: BLE001 — containment is the contract here
        logger.warning(
            f"Group {group_id} ({_GROUPS[group_id]['name']}) failed for {game}: {e}"
        )
        return _failed_group_result(group_id)


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


def research_game(game: str, sport: str, date_str: str, client) -> dict:
    """Research one game across all 5 groups (sequential convenience path —
    main() parallelizes group calls across a shared pool instead).

    Always returns a verdict dict: failed groups degrade to neutral factors
    with data_quality='failed' rather than dropping the game.
    """
    group_results = {}
    for gid in sorted(_GROUPS):
        fast = _fast_path_result(gid, game, sport)
        group_results[gid] = fast if fast is not None else _research_group(
            client, game, sport, date_str, gid
        )
    return _assemble_game_verdict(game, sport, date_str, group_results)


# ── Daily cache / merge ────────────────────────────────────────────────────────

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
    by this run (other sports / earlier runs), prune prior-day entries
    (run_picks keys by game string only — stale same-matchup entries from
    yesterday would collide)."""
    new_keys = {e["game"] for e in new_entries}
    kept = [
        e for e in existing
        if isinstance(e, dict) and e.get("date") == today and e.get("game") not in new_keys
    ]
    merged = kept + new_entries
    atomic_write_json(path, merged)
    return merged


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
    parser.add_argument("--sport", default="NBA",
                        help="Sport: NBA, MLB, NHL, WNBA, or ALL (default: NBA)")
    parser.add_argument("--odds-only", action="store_true", help="Use Odds API for game list (ignores CSV)")
    parser.add_argument("--dry-run", action="store_true", help="Print games without calling API")
    parser.add_argument("--refresh", action="store_true",
                        help="Re-research games even if already cached for today")
    args = parser.parse_args()

    sport = args.sport.upper()
    if sport == "ALL" and args.csv and not args.odds_only:
        sys.exit("--sport ALL uses the Odds API for every sport; a CSV game list cannot be combined with it.")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key and not args.dry_run:
        sys.exit("ANTHROPIC_API_KEY not set. Add it to .env and re-run.")

    odds_key = os.environ.get("ODDS_API_KEY", "")

    # Build game list
    if sport == "ALL":
        if not odds_key:
            sys.exit("ODDS_API_KEY not set. Add it to .env.")
        games = []
        for s in _ALL_SPORTS:
            games.extend(_fetch_games_from_odds_api(s, odds_key))
    elif args.odds_only or not args.csv:
        if not odds_key:
            sys.exit("ODDS_API_KEY not set. Add it to .env.")
        games = _fetch_games_from_odds_api(sport, odds_key)
    else:
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

    print(f"Researching {len(to_research)} game(s) via Claude Opus (5 parallel groups/game)...")
    client = anthropic.Anthropic(api_key=api_key)

    # Pre-compute fast paths (indoor weather, non-MLB pitching) — they never
    # consume a pool slot. Everything else fans out over one flat pool of
    # (game x group) tasks; per-group containment means a failure surfaces
    # as a failed group, never an exception.
    group_results_by_game = {g["game"]: {} for g in to_research}
    api_tasks = []
    for g in to_research:
        for gid in _GROUPS:
            fast = _fast_path_result(gid, g["game"], g["sport"])
            if fast is not None:
                group_results_by_game[g["game"]][gid] = fast
            else:
                api_tasks.append((g, gid))

    if api_tasks:
        with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(api_tasks))) as ex:
            futures = {
                ex.submit(_research_group, client, g["game"], g["sport"], today, gid): (g, gid)
                for g, gid in api_tasks
            }
            done = 0
            for fut in as_completed(futures):
                g, gid = futures[fut]
                try:
                    result = fut.result()
                except Exception:  # _research_group never raises, but be safe
                    result = _failed_group_result(gid)
                group_results_by_game[g["game"]][gid] = result
                done += 1
                print(f"  [{done}/{len(api_tasks)}] {g['game']} — {_GROUPS[gid]['name']} done", flush=True)

    new_entries = []
    for g in to_research:
        entry = _assemble_game_verdict(g["game"], g["sport"], today, group_results_by_game[g["game"]])
        new_entries.append(entry)
        print(
            f"  {entry['game']}: {entry['verdict']} ({entry['confidence']:.0%}) "
            f"[wc={entry['weighted_confirms']} wf={entry['weighted_fades']}]"
        )

    merged = _write_merged(new_entries, existing, _OUT_PATH, today)
    print(f"\nWrote {len(new_entries)} new verdict(s) ({len(merged)} total for today) to {_OUT_PATH}")


if __name__ == "__main__":
    main()
