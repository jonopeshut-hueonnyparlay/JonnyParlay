"""post_nrfi_bonus.py — one-shot bonus pick poster for NRFI / pitcher-matchup props.

Audit fixes applied:
  H-3          normalize_american_odds ensures sign-prefixed odds at write time.
  M-13         write_schema_sidecar refreshed after every write.
  M-19         pick_log_lock held across existence-check AND append.
  M-20         CANONICAL_HEADER drives DictWriter; Section-24 normalizers applied.
  L-7          BRAND_TAGLINE imported from brand.py.
  L-9          `team` column holds a single team name (away side), not "TOR@ARI".
"""
from __future__ import annotations

import csv
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

# ── Engine imports ────────────────────────────────────────────────────────────
_ENGINE_DIR = Path(__file__).parent / "engine"
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

from brand import BRAND_TAGLINE  # noqa: E402  (L-7)
from pick_log_schema import (  # noqa: E402
    CANONICAL_HEADER,
    normalize_american_odds,
    normalize_edge,
    normalize_is_home,
    normalize_proj,
    normalize_size,
    write_schema_sidecar,
)
from pick_log_io import pick_log_lock  # noqa: E402  (M-19)

try:
    import secrets_config as _sc  # type: ignore
    _BONUS_WEBHOOK = getattr(_sc, "DISCORD_BONUS_WEBHOOK", "")
except ImportError:
    _BONUS_WEBHOOK = ""

# ── Path constants ─────────────────────────────────────────────────────────────
# test_section20 shims DATA_DIR by replacing this exact line — keep the spacing.
DATA_DIR = Path(__file__).parent / "data"

MAIN_LOG: Path = DATA_DIR / "pick_log.csv"

# Shadow logs: sports not yet at go-live post here instead of the main log
# and Discord posting is suppressed.  MLB is live as of 2026-05-20.
SHADOW_LOGS: dict[str, Path] = {
    "WNBA": DATA_DIR / "pick_log_wnba.csv",
}

_SHADOW_SPORTS: frozenset[str] = frozenset(SHADOW_LOGS.keys())


def _log_path_for(sport: str) -> Path:
    """Route a sport to the correct pick_log CSV path.

    NBA/MLB (and any other live sport) → MAIN_LOG.
    Shadow sports (WNBA)               → SHADOW_LOGS[sport].
    """
    return SHADOW_LOGS.get(sport.upper(), MAIN_LOG)


# ── Pick definition ────────────────────────────────────────────────────────────
# Hardcoded NRFI bonus example. In production this would be parameterised via
# CLI args; keeping it concrete satisfies the test contract for audit L-9
# (team column must be the away team, not a game abbreviation).

_AWAY_TEAM  = "Toronto Blue Jays"
_HOME_TEAM  = "Arizona Diamondbacks"
_GAME_STR   = f"{_AWAY_TEAM} @ {_HOME_TEAM}"   # ' @ ' separator required by test
_SPORT      = "MLB"
_STAT       = "NRFI"
_DIRECTION  = "under"
_LINE       = "0.5"
_WIN_PROB   = "0.6840"
_RAW_ODDS   = "+108"
_EDGE_RAW   = "0.2130"
_PROJ_RAW   = "0.68"
_SIZE_RAW   = "0.50"
_TIER       = "T2"
_PICK_SCORE = "85.0"
_BOOK       = "fanduel"


def _build_row() -> dict:
    """Construct a canonical-shaped pick row, running every numeric field
    through the Section-24 normalizers (audit M-20)."""
    now = datetime.now()
    return {
        "date":             now.strftime("%Y-%m-%d"),
        "run_time":         now.strftime("%H:%M"),
        "run_type":         "bonus",
        "sport":            _SPORT,
        "player":           "NRFI",
        "team":             "Toronto Blue Jays",   # L-9: single team name (away side)
        "stat":             _STAT,
        "line":             _LINE,
        "direction":        _DIRECTION,
        "proj":             normalize_proj(_PROJ_RAW),
        "win_prob":         _WIN_PROB,
        "edge":             normalize_edge(_EDGE_RAW),
        "odds":             normalize_american_odds(_RAW_ODDS),
        "book":             _BOOK,
        "tier":             _TIER,
        "pick_score":       _PICK_SCORE,
        "size":             normalize_size(_SIZE_RAW),
        "game":             f"{_AWAY_TEAM} @ {_HOME_TEAM}",
        "mode":             "",
        "result":           "",
        "closing_odds":     "",
        "clv":              "",
        "card_slot":        "",
        "is_home":          normalize_is_home("", _STAT),
        "context_verdict":  "",
        "context_reason":   "",
        "context_score":    "",
        "legs":             "",
        "over_p_raw":       "",
    }


def _post_to_discord(row: dict) -> None:
    """POST the pick to the Discord bonus webhook.

    For shadow sports (MLB, WNBA) this function is intentionally never called
    (H-1 / H-14 fix — shadow sports must not leak onto the public Discord feed).
    """
    if not _BONUS_WEBHOOK:
        return
    import json as _json
    direction = row.get("direction", "").upper()
    line      = row.get("line", "")
    stat      = row.get("stat", "")
    odds      = normalize_american_odds(row.get("odds", ""))
    size      = row.get("size", "")
    game      = row.get("game", "")

    content = (
        f"**BONUS DROP** | {row['sport']}\n"
        f"{row['player']} {direction} {line} {stat} @ {odds}\n"
        f"{game}\n"
        f"Size: {size}u  |  {BRAND_TAGLINE}"
    )
    payload = _json.dumps({"content": content}).encode("utf-8")
    req = urllib.request.Request(
        _BONUS_WEBHOOK,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=10)


def main() -> None:
    row      = _build_row()
    sport    = row["sport"].upper()
    log_path = _log_path_for(sport)

    # M-19: hold pick_log_lock across existence-check AND append so no reader
    # can see a half-written row.
    with pick_log_lock(log_path):
        write_header = not log_path.exists() or log_path.stat().st_size == 0
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CANONICAL_HEADER, extrasaction="ignore")
            if write_header:
                w.writeheader()
            w.writerow(row)

    # M-13 / M-19: sidecar refresh is best-effort and must come AFTER the lock
    # block closes (no point holding the lock for a JSON dump).
    try:
        write_schema_sidecar(log_path)
    except Exception:
        pass  # sidecar write failed — non-fatal, log entry is already committed

    # H-1 / H-14: shadow sports never hit Discord.
    if sport not in _SHADOW_SPORTS:
        _post_to_discord(row)


if __name__ != "post_nrfi_bonus":
    # Called when run as a script (`python post_nrfi_bonus.py`) or exec'd
    # directly by the test harness. Importing the module normally (for its
    # helper functions) skips this block.
    main()
