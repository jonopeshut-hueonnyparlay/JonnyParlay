"""SaberSim CSV parsing + Odds API fetching/extraction.

Extracted from run_picks.py (extract-and-re-export refactor, Step 11) and
re-imported there so existing call sites and `from run_picks import ...` keep
resolving. Imports only {stdlib, requests, secrets_config, paths, http_utils,
name_utils, book_names, market_config, quant.odds} — never run_picks or the
other extracted modules.
"""
import sys
import csv
import json
import os
import re
import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from secrets_config import ODDS_API_KEY
from paths import data_path as _data_path
from http_utils import default_headers
from name_utils import name_key
from book_names import CO_LEGAL_BOOKS
from market_config import (
    ODDS_BASE, ODDS_REGIONS, API_SLEEP, SPORT_KEYS,
    SPORT_ALT_MARKET, PROP_MARKETS, MARKET_TO_STAT, MARKET_TO_STAT_OVERRIDE,
)
from quant.odds import is_decimal_leak

logger = logging.getLogger("jonnyparlay")

OUTPUT_FOLDER = str(_data_path("picks"))

# ADR-005 / 1B (revised per architecture review): required-column contract for
# parse_csv(). Each stat's alternate set is transcribed EXACTLY from that stat's
# own clean.get(...) fallback chain below -- not a generic case-insensitive
# guess, since the chains are inconsistent (MLB fields are exact-case only;
# NBA/NHL fields tolerate some but not all case variants). If none of a stat's
# alternates appear in the file's raw header, parse_csv() would silently price
# every player at 0 for that stat with no fallback -- this is deliberately
# narrower than "every column the parser reads": dk_std is excluded because its
# absence already has a documented, intentional fallback (see the dk_std
# comment below, "falls back to SIGMA['PTS']").
# R16: fraction of rows failing to parse above which the aggregate drop-rate
# check fires. High enough to tolerate normal per-file noise (a player or two
# with a bad value), low enough to catch a systemic problem before it silently
# halves a slate.
_ROW_DROP_WARN_THRESHOLD = 0.20

_REQUIRED_STAT_COLUMNS = {
    "NBA":  {"PTS": {"PTS", "pts"}, "REB": {"RB", "rb", "REB"},
             "AST": {"AST", "ast"}, "3PM": {"3PT", "3pt", "3PM"}},
    "WNBA": {"PTS": {"PTS", "pts"}, "REB": {"RB", "rb", "REB"},
             "AST": {"AST", "ast"}, "3PM": {"3PT", "3pt", "3PM"}},
    "MLB":  {"1B": {"1B"}, "2B": {"2B"}, "3B": {"3B"}, "HR": {"HR"}, "R": {"R"},
             "RBI": {"RBI"}, "H": {"H"}, "K": {"K"}, "BB": {"BB"}, "IP": {"IP"},
             "ER": {"ER"}, "PA": {"PA"}},
    "NHL":  {"SOG": {"SOG", "sog"}, "AST": {"A", "a", "AST"}, "G": {"G", "g"},
             "SV": {"SV", "sv"}, "GA": {"GA", "ga"}},
}


def _confirm_sport_detection(raw_headers: set, sport: str, path: Path) -> None:
    """R16: sport misdetection is not a degraded input -- it's potentially the
    wrong semantic interpretation of every column in the file (e.g. NHL goals
    parsed as NBA points). Unlike a single missing stat column, there is no
    defensible partial-continuation value, so this fails loudly unconditionally
    -- never gated by ODDS_IO_STRICT_CSV_VALIDATION. If none of the detected
    sport's own identifying stat columns are present at all, detection cannot
    be trusted and this file must not be priced under a guessed sport."""
    required = _REQUIRED_STAT_COLUMNS.get(sport)
    if not required:
        return
    expected = set().union(*required.values())
    if expected & raw_headers:
        return  # at least one identifying column present -- detection confirmed
    logger.error(
        "odds_io.parse_csv: sport detection failure -- detected sport=%s for %s, "
        "but none of the expected identifying columns %s are present in the "
        "header %s. Refusing to price this file under a possibly-wrong sport.",
        sport, path, sorted(expected), sorted(raw_headers))
    print(f"  [!] {path.name}: detected sport={sport} but no identifying column "
          f"found (expected one of {sorted(expected)} in header {sorted(raw_headers)}) "
          f"-- aborting. This file may be misclassified.")
    sys.exit(1)


def _check_required_columns(raw_headers: set, sport: str, path: Path) -> None:
    """Warn (default) or abort (ODDS_IO_STRICT_CSV_VALIDATION=1) when a
    structurally required stat column is entirely absent from the CSV header."""
    required = _REQUIRED_STAT_COLUMNS.get(sport)
    if not required:
        return
    missing = [stat for stat, alts in required.items() if not (alts & raw_headers)]
    if not missing:
        return
    msg = (f"  [!] {path.name}: missing required {sport} column(s) {missing} -- "
           f"affected players will silently price at 0 for these stats.")
    if os.environ.get("ODDS_IO_STRICT_CSV_VALIDATION", "").lower() in ("1", "true", "yes"):
        print(msg + " Aborting (ODDS_IO_STRICT_CSV_VALIDATION is set).")
        sys.exit(1)
    print(msg)
    logger.warning("odds_io.parse_csv: missing required %s column(s) %s in %s",
                   sport, missing, path.name)


def parse_csv(filepath):
    """Parse SaberSim CSV. Returns list of player dicts and detected sport."""
    path = Path(filepath)
    if not path.exists():
        # Auto-find in Downloads by sport keyword (e.g. "mlb.csv" -> search for *mlb* in Downloads)
        sport_key = path.stem.lower()
        downloads_dirs = [
            Path.home() / "Downloads" / "projections",
            Path.home() / "Downloads",
        ]
        now = time.time()
        for d in downloads_dirs:
            if not d.exists():
                continue
            matches = sorted(
                [f for f in d.glob("*.csv") if re.search(r'(?<![a-z])' + re.escape(sport_key) + r'(?![a-z])', f.name.lower()) and (now - f.stat().st_mtime) < 43200],
                key=lambda f: f.stat().st_mtime, reverse=True
            )
            if matches:
                path = matches[0]
                print(f"  [auto] Found {path.name}")
                break
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        # M6: error + abort instead of silently defaulting to NBA
        name = Path(filepath).name
        print(f"  [!] Empty CSV: {filepath} — aborting. Check that {name} is a valid SaberSim export.")
        sys.exit(1)

    headers = {h.strip().lower() for h in rows[0].keys()}

    # Detect sport — filename wins over headers (WNBA has identical headers to NBA)
    fname = path.name.lower()
    if "wnba" in fname:
        sport = "WNBA"
    elif "sog" in headers or any("shot" in h for h in headers):
        sport = "NHL"
    elif "ip" in headers and ("er" in headers or "k" in headers or "qs" in headers):
        sport = "MLB"
    elif "rb" in headers or "ast" in headers or "3pt" in headers:
        sport = "NBA"
    elif "mlb" in fname:
        sport = "MLB"
    elif "nhl" in fname:
        sport = "NHL"
    else:
        sport = "NBA"

    raw_headers = {h.strip() for h in rows[0].keys()}
    _confirm_sport_detection(raw_headers, sport, path)
    _check_required_columns(raw_headers, sport, path)

    players = []
    for row in rows:
        # Clean keys
        clean = {k.strip(): v.strip() for k, v in row.items()}

        try:
            # R10: Parse Status column — "Confirmed" means SaberSim has confirmed this starter
            raw_status = clean.get("Status", clean.get("status", "")).strip().lower()
            p = {
                "name": clean.get("Name", clean.get("name", "")),
                "team": clean.get("Team", clean.get("team", "")),
                "opp":  clean.get("Opp", clean.get("opp", "")),
                "pos":  clean.get("Pos", clean.get("pos", "")),
                "saber_total": float(clean.get("Saber Total", clean.get("saber total", 0)) or 0),
                "saber_team":  float(clean.get("Saber Team", clean.get("saber team", 0)) or 0),
                "status": raw_status,  # "confirmed" for confirmed starters, "" otherwise
            }

            if sport in ("NBA", "WNBA"):
                p["AST"] = float(clean.get("AST", clean.get("ast", 0)) or 0)
                p["REB"] = float(clean.get("RB", clean.get("rb", clean.get("REB", 0))) or 0)
                p["PTS"] = float(clean.get("PTS", clean.get("pts", 0)) or 0)
                p["3PM"] = float(clean.get("3PT", clean.get("3pt", clean.get("3PM", 0))) or 0)
                # H3: custom projection engine writes dk_std (empirical σ including high-var floor).
                # SaberSim CSVs also carry this column. 0.0 = absent → falls back to SIGMA["PTS"].
                p["dk_std"] = float(clean.get("dk_std", clean.get("DK_STD", 0)) or 0)
                # Custom engine extras — absent/blank in SaberSim CSVs (gates no-op when None/False).
                _cv_raw = clean.get("pts_cv", "")
                p["pts_cv"] = float(_cv_raw) if _cv_raw else None
                p["cold_start_subtype"] = clean.get("cold_start_subtype") or None
                p["injury_trigger"] = clean.get("injury_trigger", "").lower() in ("true", "1", "yes")
            elif sport == "NHL":
                if p["pos"].upper() == "G":
                    # Goalie — parse saves/GA and include; skip all skater stats
                    sv = float(clean.get("SV", clean.get("sv", 0)) or 0)
                    ga = float(clean.get("GA", clean.get("ga", 0)) or 0)
                    if sv > 0 or ga > 0:
                        p["SV"] = sv
                        p["GA"] = ga
                        p["name_key"] = name_key(p["name"])
                        players.append(p)
                    continue
                # Skater
                p["SOG"] = float(clean.get("SOG", clean.get("sog", 0)) or 0)
                p["AST"] = float(clean.get("A", clean.get("a", clean.get("AST", 0))) or 0)
                p["GOALS"]  = float(clean.get("G",   clean.get("g",   0)) or 0)
                p["NHLPTS"] = p["GOALS"] + p["AST"]   # G+A points — Poisson, var/mu=0.983
                p["NHLBLK"] = float(clean.get("BLK", clean.get("blk", 0)) or 0)
            elif sport == "MLB":
                is_pitcher = p["pos"].upper() == "P"
                # Raw stats from SaberSim
                singles = float(clean.get("1B", 0) or 0)
                doubles = float(clean.get("2B", 0) or 0)
                triples = float(clean.get("3B", 0) or 0)
                hr = float(clean.get("HR", 0) or 0)
                r = float(clean.get("R", 0) or 0)
                rbi = float(clean.get("RBI", 0) or 0)
                h = float(clean.get("H", 0) or 0)
                k = float(clean.get("K", 0) or 0)
                bb = float(clean.get("BB", 0) or 0)
                ip = float(clean.get("IP", 0) or 0)
                er = float(clean.get("ER", 0) or 0)
                pa = float(clean.get("PA", 0) or 0)

                p["is_pitcher"] = is_pitcher
                if is_pitcher:
                    p["K"] = k
                    p["OUTS"] = ip * 3  # Convert IP to outs recorded
                    p["HA"] = h         # Hits allowed
                    p["ER"] = er        # Earned runs — internal use only (game-line projection math)
                    p["IP"] = ip
                    p["BB"] = bb
                    p["PC"] = float(clean.get("Pitches", clean.get("P", clean.get("PC", 0))) or 0)
                    p["HR"] = hr        # R4: HR allowed — required for FIP calculation
                else:
                    p["HITS"] = h
                    p["TB"] = singles + 2 * doubles + 3 * triples + 4 * hr  # Total bases
                    p["TB_1B"] = singles   # Components preserved for discrete distribution model
                    p["TB_2B"] = doubles
                    p["TB_3B"] = triples
                    p["TB_HR"] = hr
                    p["HRR"]  = h + r + rbi  # Hits + Runs + RBIs
                    p["RUNS"] = r            # Batter runs scored (batter_runs_scored market)
                    p["R"]    = r            # Keep internal alias
                    p["RBI"]  = rbi
                    p["HR"]   = hr
                    p["PA"]   = pa

            p["name_key"] = name_key(p["name"])
            players.append(p)
        except (ValueError, KeyError) as e:
            # R16: raised from debug to warning -- a per-row skip is tolerated
            # (unchanged), but was previously invisible under default logging.
            logger.warning(f"Skipped malformed row: {e}")
            continue

    # R16: aggregate drop-rate check. A single bad row is normal, tolerated
    # noise (unchanged above); a large fraction failing indicates a systemic
    # problem (e.g. a subtly drifted export) that per-row tolerance alone
    # would hide. Gated the same way as _check_required_columns -- warn by
    # default, abort under ODDS_IO_STRICT_CSV_VALIDATION.
    _rows_attempted = len(rows)
    _dropped = _rows_attempted - len(players)
    if _rows_attempted and (_dropped / _rows_attempted) > _ROW_DROP_WARN_THRESHOLD:
        _msg = (f"  [!] {path.name}: {_dropped}/{_rows_attempted} rows failed to parse "
                f"({_dropped / _rows_attempted:.0%}) -- possible malformed or drifted export.")
        if os.environ.get("ODDS_IO_STRICT_CSV_VALIDATION", "").lower() in ("1", "true", "yes"):
            print(_msg + " Aborting (ODDS_IO_STRICT_CSV_VALIDATION is set).")
            sys.exit(1)
        print(_msg)
        logger.warning("odds_io.parse_csv: high row-drop-rate %.0f%% (%d/%d) in %s",
                       _dropped / _rows_attempted * 100, _dropped, _rows_attempted, path.name)

    # Deduplicate by name_key (handles Showdown CSVs where each player appears twice)
    seen = {}
    deduped = []
    for p in players:
        nk = p["name_key"]
        if nk not in seen:
            seen[nk] = True
            deduped.append(p)
    is_showdown = "showdown" in path.name.lower()
    if is_showdown and len(players) != len(deduped):
        print(f"  Loaded {path.name}: {len(deduped)} players (Showdown deduped from {len(players)}), sport: {sport}")
    else:
        print(f"  Loaded {path.name}: {len(deduped)} players, sport: {sport}")
    return deduped, sport, path

class OddsFetcher:
    def __init__(self):
        self.remaining = None

    def _get(self, url, params):
        params["apiKey"] = ODDS_API_KEY
        # Audit M-16: canonical UA on every outbound Odds API call.
        headers = default_headers()
        for attempt in range(3):
            try:
                r = requests.get(url, params=params, headers=headers, timeout=15)
                self.remaining = r.headers.get("x-requests-remaining")
                if r.status_code == 200:
                    return r.json()
                elif r.status_code == 422:
                    return []
                elif r.status_code == 401:
                    logger.error("Invalid Odds API key.")
                    sys.exit(1)
                else:
                    print(f"  [!] API {r.status_code}")
                    time.sleep(2 ** attempt)
            except Exception as e:
                print(f"  [!] {e}")
                time.sleep(2 ** attempt)
        return []

    def _load_cache(self, sport):
        """Load cached odds data if fresh enough (< 15 min old)."""
        cache_dir = Path(OUTPUT_FOLDER) / "cache"
        # Use ET for day boundary (matches pick_log date convention) so the
        # cache file name doesn't drift across timezones (audit H-1).
        cache_file = cache_dir / f"odds_{sport}_{datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d')}.json"
        if cache_file.exists():
            age_min = (time.time() - cache_file.stat().st_mtime) / 60
            if age_min < 15:
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    print(f"  ♻️  Using cached {sport} odds ({age_min:.0f} min old)")
                    return data
                except json.JSONDecodeError as _e:
                    # H10: only swallow corrupt JSON; let real I/O errors propagate
                    logger.warning("H10: Corrupt odds cache, will re-fetch: %s", _e)  # C9: was log.warning (NameError)
        return None

    def _save_cache(self, sport, data):
        """Save odds data to cache."""
        cache_dir = Path(OUTPUT_FOLDER) / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        # ET day boundary — must match _load_cache (audit H-1).
        cache_file = cache_dir / f"odds_{sport}_{datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d')}.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, default=str)
        except Exception as e:
            logger.warning("Cache save failed: %s", e)

    def fetch_all(self, sports, fetch_alt_spreads=False, game_lines_only=False, no_cache=False, force=False):
        """Fetch all odds. Batches markets per event. Caches for 15 min."""
        all_data = {}

        for sport in sports:
            sk = SPORT_KEYS.get(sport)
            if not sk:
                continue

            print(f"\n  {'='*40}")
            print(f"  Fetching {sport} odds...")

            # Check cache first
            if not no_cache:
                cached = self._load_cache(sport)
                if cached:
                    all_data[sport] = cached
                    continue

            data = {"events": [], "game_lines": [], "props": {}}
            api_calls = 0

            # Events
            events = self._get(f"{ODDS_BASE}/sports/{sk}/events", {})
            api_calls += 1
            now = datetime.now(timezone.utc)
            # FIX L1: Dynamic timezone — handles MST/MDT automatically
            CO_TZ = ZoneInfo("America/Denver")
            local_now = now.astimezone(CO_TZ)
            local_date = local_now.strftime("%Y-%m-%d")
            # End of today = next midnight local → in UTC
            local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            end_of_today_utc = local_midnight.astimezone(timezone.utc)

            def parse_commence(ct):
                """Parse API commence_time string to UTC datetime."""
                try:
                    ct = ct.replace("Z", "+00:00")
                    return datetime.fromisoformat(ct)
                except Exception:
                    return None

            upcoming = []
            for e in (events or []):
                ct = parse_commence(e.get("commence_time", ""))
                # --force: skip the now < ct check so already-started games are included (test only)
                in_window = ct and ct < end_of_today_utc and (force or now < ct)
                if in_window:
                    upcoming.append(e)
            data["events"] = upcoming
            total_events = len(events or [])
            print(f"  {len(upcoming)} today's games (filtered from {total_events} total)")
            print(f"  Local date: {local_date} {local_now.strftime('%Z')} | Now UTC: {now.strftime('%H:%M')} | Cutoff UTC: {end_of_today_utc.strftime('%Y-%m-%d %H:%M')}")
            if upcoming:
                for ue in upcoming[:5]:
                    ct_str = ue.get("commence_time", "?")
                    ct_dt = parse_commence(ct_str)
                    local_ct = ct_dt.astimezone(CO_TZ).strftime("%I:%M %p %Z") if ct_dt else "?"
                    print(f"    {ue.get('away_team','?')} @ {ue.get('home_team','?')} — {local_ct}")

            if not upcoming:
                all_data[sport] = data
                continue

            # Game lines (bulk — 1 call for all games)
            print(f"\n  Pulling game lines...")
            gl = self._get(f"{ODDS_BASE}/sports/{sk}/odds",
                          {"regions": ODDS_REGIONS, "markets": "spreads,totals,h2h",
                           "oddsFormat": "american"})
            data["game_lines"] = gl or []
            api_calls += 1
            time.sleep(API_SLEEP)

            # Per-event markets — BATCHED into as few calls as possible
            for ev in upcoming:
                eid = ev["id"]
                matchup = f"{ev.get('away_team','?')} @ {ev.get('home_team','?')}"
                print(f"\n  {matchup}")

                # Alt lines (spreads/puck_line/run_line) — sport-specific market name
                alt_market = SPORT_ALT_MARKET.get(sport)
                if fetch_alt_spreads and alt_market:
                    print(f"    {alt_market}...")
                    alts = self._get(f"{ODDS_BASE}/sports/{sk}/events/{eid}/odds",
                                    {"regions": ODDS_REGIONS, "markets": alt_market,
                                     "oddsFormat": "american"})
                    if alts:
                        data["props"][f"{eid}_{alt_market}"] = alts
                    api_calls += 1
                    time.sleep(API_SLEEP)

                # Skip props + team totals in game_lines_only mode
                if game_lines_only:
                    continue

                # BATCH all prop markets + team_totals (+ F5 for MLB) into ONE call
                batch_markets = ["team_totals"] + PROP_MARKETS.get(sport, [])
                if sport == "MLB":
                    batch_markets.extend(["h2h_1st_5_innings", "spreads_1st_5_innings",
                                          "totals_1st_5_innings", "totals_1st_1_innings"])
                markets_str = ",".join(batch_markets)
                print(f"    batched: {len(batch_markets)} markets in 1 call")

                resp = self._get(f"{ODDS_BASE}/sports/{sk}/events/{eid}/odds",
                                {"regions": ODDS_REGIONS, "markets": markets_str,
                                 "oddsFormat": "american"})
                api_calls += 1

                if resp:
                    # Parse the batched response into separate keyed entries
                    # The API returns all markets in one response — we need to split them
                    # into the format the rest of the code expects
                    if isinstance(resp, dict):
                        bms = resp.get("bookmakers", [])
                    elif isinstance(resp, list) and resp:
                        bms = resp[0].get("bookmakers", []) if isinstance(resp[0], dict) else []
                    else:
                        bms = []

                    # Group markets from the response
                    market_data = {}  # market_key → list of bookmaker entries with only that market
                    for bm in bms:
                        book_key = bm.get("key", "")
                        for market in bm.get("markets", []):
                            mk = market.get("key", "")
                            if mk not in market_data:
                                market_data[mk] = []
                            # Build a bookmaker entry with just this one market
                            market_data[mk].append({
                                "key": book_key,
                                "title": bm.get("title", ""),
                                "markets": [market],
                            })

                    # Store each market under the expected key format
                    for mk, bm_entries in market_data.items():
                        if mk == "team_totals":
                            store_key = f"{eid}_team_totals"
                        elif mk in ("h2h_1st_5_innings", "spreads_1st_5_innings", "totals_1st_5_innings"):
                            store_key = f"{eid}_f5_innings"
                        elif mk == "totals_1st_1_innings":
                            store_key = f"{eid}_nrfi"
                        else:
                            store_key = f"{eid}_{mk}"

                        # Build response object matching what individual calls return
                        if store_key in data["props"]:
                            # Merge bookmakers into existing entry (for F5 which has 3 markets)
                            existing = data["props"][store_key]
                            if isinstance(existing, dict):
                                existing.setdefault("bookmakers", [])
                                # Merge: add new markets to existing bookmaker entries
                                existing_books = {b["key"]: b for b in existing["bookmakers"]}
                                for bm_entry in bm_entries:
                                    bk = bm_entry["key"]
                                    if bk in existing_books:
                                        existing_books[bk]["markets"].extend(bm_entry["markets"])
                                    else:
                                        existing["bookmakers"].append(bm_entry)
                        else:
                            data["props"][store_key] = {"bookmakers": bm_entries}

                time.sleep(API_SLEEP)

            all_data[sport] = data

            # Save to cache
            self._save_cache(sport, data)

            print(f"\n  {sport}: {api_calls} API calls total")
            if self.remaining:
                print(f"  API requests remaining: {self.remaining}")

        return all_data

def extract_player_props(odds_data, sport):
    """
    Parse API odds data into a list of prop opportunities.
    Returns list of dicts: {player, player_key, stat, line, over_odds, under_odds, game, book_over, book_under}
    """
    props = []
    events = odds_data.get("events", [])
    event_map = {e["id"]: e for e in events}

    for key, response in odds_data.get("props", {}).items():
        parts = key.split("_", 1)
        eid = parts[0]
        market_key = parts[1] if len(parts) > 1 else ""

        if market_key == "team_totals":
            continue  # handled separately

        # Sport-aware override first (e.g. player_points: NBA→PTS, NHL→NHLPTS)
        stat = MARKET_TO_STAT_OVERRIDE.get(sport, {}).get(market_key) or MARKET_TO_STAT.get(market_key, "")
        if not stat:
            continue

        ev = event_map.get(eid, {})
        game = f"{ev.get('away_team','?')} @ {ev.get('home_team','?')}"

        # response is the event odds object or list
        if isinstance(response, dict):
            bookmakers = response.get("bookmakers", [])
        elif isinstance(response, list) and len(response) > 0:
            bookmakers = response[0].get("bookmakers", []) if isinstance(response[0], dict) else []
        else:
            continue

        # Collect best odds per (player, line, direction)
        best = {}  # key: (player, line) -> {over_odds, under_odds, book_over, book_under}

        for bm in bookmakers:
            book = bm.get("key", "")
            # Strip region suffix (e.g. hardrockbet_az → hardrockbet) for CO_LEGAL_BOOKS check
            book_base = book.rsplit("_", 1)[0] if "_" in book else book
            if book_base not in CO_LEGAL_BOOKS and book not in CO_LEGAL_BOOKS:
                continue  # Skip books not available in Colorado
            for market in bm.get("markets", []):
                if market.get("key", "") != market_key:
                    continue
                for outcome in market.get("outcomes", []):
                    player = outcome.get("description", "")
                    line = outcome.get("point")
                    odds = outcome.get("price", 0)
                    name = outcome.get("name", "")  # "Over" or "Under"

                    if not player or line is None or odds == 0:
                        continue
                    if is_decimal_leak(odds):
                        continue

                    pk = (player, line)
                    if pk not in best:
                        best[pk] = {"over_odds": None, "under_odds": None,
                                    "book_over": "", "book_under": ""}

                    if name == "Over":
                        if best[pk]["over_odds"] is None or odds > best[pk]["over_odds"]:
                            best[pk]["over_odds"] = odds
                            best[pk]["book_over"] = book
                    elif name == "Under":
                        if best[pk]["under_odds"] is None or odds > best[pk]["under_odds"]:
                            best[pk]["under_odds"] = odds
                            best[pk]["book_under"] = book

        for (player, line), info in best.items():
            props.append({
                "player": player,
                "player_key": name_key(player),
                "stat": stat,
                "line": float(line),
                "over_odds": info["over_odds"],
                "under_odds": info["under_odds"],
                "book_over": info["book_over"],
                "book_under": info["book_under"],
                "game": game,
                "sport": sport,
                "event_id": eid,
            })

    return props

def extract_game_lines(odds_data, sport):
    """Parse game lines from API response. Only includes upcoming (not started) games."""
    lines = []
    events = odds_data.get("events", [])
    event_map = {e["id"]: e for e in events}
    # Set of upcoming event IDs (already filtered by commence_time in fetch_all)
    upcoming_ids = {e["id"] for e in events}

    for game_data in odds_data.get("game_lines", []):
        # Skip games that have already started (not in upcoming events)
        eid = game_data.get("id", "")
        if eid and upcoming_ids and eid not in upcoming_ids:
            continue
        eid = game_data.get("id", "")
        home = game_data.get("home_team", "")
        away = game_data.get("away_team", "")
        game = f"{away} @ {home}"

        best_spread = {}    # {team: {line, odds, book}}
        best_total = {}     # {direction: {line, odds, book}}
        best_ml = {}        # {team: {odds, book}}

        for bm in game_data.get("bookmakers", []):
            book = bm.get("key", "")
            book_base = book.rsplit("_", 1)[0] if "_" in book else book
            if book_base not in CO_LEGAL_BOOKS and book not in CO_LEGAL_BOOKS:
                continue  # Skip books not available in Colorado
            for market in bm.get("markets", []):
                mk = market.get("key", "")
                for outcome in market.get("outcomes", []):
                    name = outcome.get("name", "")
                    odds = outcome.get("price", 0)
                    point = outcome.get("point")

                    if odds == 0 or is_decimal_leak(odds):
                        continue

                    if mk == "spreads" and point is not None:
                        if name not in best_spread or odds > best_spread[name]["odds"]:
                            best_spread[name] = {"line": point, "odds": odds, "book": book}
                    elif mk == "totals":
                        if name not in best_total or odds > best_total[name]["odds"]:
                            best_total[name] = {"line": point, "odds": odds, "book": book}
                    elif mk == "h2h":
                        if name not in best_ml or odds > best_ml[name]["odds"]:
                            best_ml[name] = {"odds": odds, "book": book}

        lines.append({
            "game": game, "home": home, "away": away,
            "spread": best_spread, "total": best_total, "ml": best_ml,
            "sport": sport, "event_id": eid,
        })

    return lines

def extract_team_totals(odds_data, sport):
    """Parse team totals from API response."""
    results = []
    events = odds_data.get("events", [])
    event_map = {e["id"]: e for e in events}

    for key, response in odds_data.get("props", {}).items():
        if "team_totals" not in key:
            continue

        eid = key.split("_")[0]
        ev = event_map.get(eid, {})
        game = f"{ev.get('away_team','?')} @ {ev.get('home_team','?')}"

        if isinstance(response, dict):
            bookmakers = response.get("bookmakers", [])
        elif isinstance(response, list) and response:
            bookmakers = response[0].get("bookmakers", []) if isinstance(response[0], dict) else []
        else:
            continue

        # (team, point) -> {over_odds, under_odds, book_over, book_under, book_set}
        by_line = {}
        book_counts = {}  # (team, point) -> set of books offering BOTH sides

        for bm in bookmakers:
            book = bm.get("key", "")
            book_base = book.rsplit("_", 1)[0] if "_" in book else book
            if book_base not in CO_LEGAL_BOOKS and book not in CO_LEGAL_BOOKS:
                continue
            for market in bm.get("markets", []):
                for outcome in market.get("outcomes", []):
                    team = outcome.get("description", outcome.get("name", ""))
                    name = outcome.get("name", "")
                    odds = outcome.get("price", 0)
                    point = outcome.get("point")

                    if not team or odds == 0 or point is None or is_decimal_leak(odds):
                        continue
                    if team in ("Over", "Under"):
                        continue  # description absent — name fallback gives direction, not team

                    direction = "over" if name == "Over" else "under"
                    pk = (team, point)
                    if pk not in by_line:
                        by_line[pk] = {}
                    entry = by_line[pk]

                    odds_key = f"{direction}_odds"
                    book_key = f"book_{direction}"
                    # Keep best odds per direction at this exact point
                    if odds_key not in entry or odds > entry[odds_key]:
                        entry[odds_key] = odds
                        entry[book_key] = book

        # Count how many books offer BOTH sides at each (team, point)
        # Re-scan bookmakers to count matched lines per book
        for bm in bookmakers:
            book = bm.get("key", "")
            book_base = book.rsplit("_", 1)[0] if "_" in book else book
            if book_base not in CO_LEGAL_BOOKS and book not in CO_LEGAL_BOOKS:
                continue
            book_sides = {}  # (team, point) -> set of directions this book offers
            for market in bm.get("markets", []):
                for outcome in market.get("outcomes", []):
                    team = outcome.get("description", outcome.get("name", ""))
                    name = outcome.get("name", "")
                    odds = outcome.get("price", 0)
                    point = outcome.get("point")
                    if not team or odds == 0 or point is None or is_decimal_leak(odds):
                        continue
                    direction = "over" if name == "Over" else "under"
                    pk = (team, point)
                    book_sides.setdefault(pk, set()).add(direction)
            for pk, sides in book_sides.items():
                if "over" in sides and "under" in sides:
                    book_counts.setdefault(pk, set()).add(book)

        # For each team, pick the point offered by the most books (= main line)
        # Require both over and under to exist at that point
        teams_seen = set(team for (team, _) in by_line)
        for team in teams_seen:
            candidates = []
            for (t, point), entry in by_line.items():
                if t != team:
                    continue
                if "over_odds" not in entry or "under_odds" not in entry:
                    continue
                n_books = len(book_counts.get((team, point), set()))
                candidates.append((n_books, point, entry))

            if not candidates:
                continue

            # Most books = main line; break ties by picking most-negative under odds
            candidates.sort(key=lambda x: (-x[0], x[2].get("under_odds", 0)))
            _, point, entry = candidates[0]

            results.append({
                "team": team, "game": game, "sport": sport,
                "line": point,
                "over_odds": entry["over_odds"], "under_odds": entry["under_odds"],
                "book_over": entry.get("book_over", ""), "book_under": entry.get("book_under", ""),
                "home_team": ev.get("home_team", ""),
            })

    return results

def extract_alt_spreads(odds_data, sport):
    """Parse alternate spreads from API response.
    Returns list of dicts: [{"team", "line", "odds", "book"}, ...]
    Keeps ALL book prices so parlay builder can group by book.
    """
    alt_lines = []
    events = odds_data.get("events", [])

    for key, response in odds_data.get("props", {}).items():
        if not any(m in key for m in ("alternate_spreads", "alternate_puck_line", "alternate_run_line")):
            continue

        if isinstance(response, dict):
            bookmakers = response.get("bookmakers", [])
        elif isinstance(response, list) and response:
            bookmakers = response[0].get("bookmakers", []) if isinstance(response[0], dict) else []
        else:
            continue

        for bm in bookmakers:
            book = bm.get("key", "")
            book_base = book.rsplit("_", 1)[0] if "_" in book else book
            if book_base not in CO_LEGAL_BOOKS and book not in CO_LEGAL_BOOKS:
                continue
            for market in bm.get("markets", []):
                for outcome in market.get("outcomes", []):
                    team = outcome.get("name", "")
                    odds = outcome.get("price", 0)
                    point = outcome.get("point")

                    if not team or odds == 0 or point is None or is_decimal_leak(odds):
                        continue

                    alt_lines.append({
                        "team": team, "line": point,
                        "odds": odds, "book": book,
                    })

    return alt_lines

def extract_f5_lines(odds_data, sport):
    """Extract First 5 innings lines from MLB API response."""
    if sport != "MLB":
        return []
    f5_lines = []
    events = odds_data.get("events", [])
    event_map = {e["id"]: e for e in events}

    for key, response in odds_data.get("props", {}).items():
        if "f5_innings" not in key:
            continue
        parts = key.split("_", 1)
        eid = parts[0]
        ev = event_map.get(eid, {})
        game = f"{ev.get('away_team','?')} @ {ev.get('home_team','?')}"
        home = ev.get("home_team", "")
        away = ev.get("away_team", "")

        if isinstance(response, dict):
            bookmakers = response.get("bookmakers", [])
        elif isinstance(response, list) and len(response) > 0:
            bookmakers = response[0].get("bookmakers", []) if isinstance(response[0], dict) else []
        else:
            continue

        f5_data = {"game": game, "home": home, "away": away, "sport": sport, "event_id": eid}

        # Parse each F5 market type
        for bm in bookmakers:
            book = bm.get("key", "")
            book_base = book.rsplit("_", 1)[0] if "_" in book else book
            if book_base not in CO_LEGAL_BOOKS and book not in CO_LEGAL_BOOKS:
                continue
            for market in bm.get("markets", []):
                mk = market.get("key", "")
                for outcome in market.get("outcomes", []):
                    name = outcome.get("name", "")
                    odds = outcome.get("price", 0)
                    point = outcome.get("point")
                    if odds == 0 or is_decimal_leak(odds):
                        continue

                    if mk == "totals_1st_5_innings":
                        if name == "Over" and point is not None:
                            f5_data.setdefault("total", {})
                            if "Over" not in f5_data["total"] or odds > f5_data["total"]["Over"].get("odds", -9999):
                                f5_data["total"]["Over"] = {"odds": odds, "line": point, "book": book}
                        elif name == "Under" and point is not None:
                            f5_data.setdefault("total", {})
                            if "Under" not in f5_data["total"] or odds > f5_data["total"]["Under"].get("odds", -9999):
                                f5_data["total"]["Under"] = {"odds": odds, "line": point, "book": book}
                    elif mk == "h2h_1st_5_innings":
                        f5_data.setdefault("ml", {})
                        if name not in f5_data["ml"] or odds > f5_data["ml"].get(name, {}).get("odds", -9999):
                            f5_data["ml"][name] = {"odds": odds, "book": book, "team": name}
                    elif mk == "spreads_1st_5_innings":
                        if point is not None:
                            f5_data.setdefault("spread", {})
                            if name not in f5_data["spread"] or odds > f5_data["spread"].get(name, {}).get("odds", -9999):
                                f5_data["spread"][name] = {"odds": odds, "line": point, "book": book, "team": name}

        if any(k in f5_data for k in ("total", "ml", "spread")):
            f5_lines.append(f5_data)

    return f5_lines
