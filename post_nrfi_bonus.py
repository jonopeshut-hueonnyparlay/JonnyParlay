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

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

import requests

# ── Engine imports ────────────────────────────────────────────────────────────
_ENGINE_DIR = Path(__file__).parent / "engine"
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

from brand import BRAND_TAGLINE  # noqa: E402  (L-7)
from http_utils import default_headers  # noqa: E402  (H-3)
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
# and Discord posting is suppressed.  MLB live 2026-05-20, WNBA live 2026-06-09
# — no shadow sports remain.
SHADOW_LOGS: dict[str, Path] = {}

_SHADOW_SPORTS: frozenset[str] = frozenset(SHADOW_LOGS.keys())


def _log_path_for(sport: str) -> Path:
    """Route a sport to the correct pick_log CSV path.

    Live sports (all, since WNBA go-live 2026-06-09) → MAIN_LOG.
    Any future shadow sport                          → SHADOW_LOGS[sport].
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


def _build_row(
    away_team: str = _AWAY_TEAM,
    home_team: str = _HOME_TEAM,
    raw_odds: str = _RAW_ODDS,
    stat: str = _STAT,
    line: str = _LINE,
    direction: str = _DIRECTION,
    win_prob: str = _WIN_PROB,
    edge_raw: str = _EDGE_RAW,
    book: str = _BOOK,
    size_raw: str = _SIZE_RAW,
) -> dict:
    """Construct a canonical-shaped pick row, running every numeric field
    through the Section-24 normalizers (audit M-20)."""
    now = datetime.now()
    return {
        "date":             now.strftime("%Y-%m-%d"),
        "run_time":         now.strftime("%H:%M"),
        "run_type":         "bonus",
        "sport":            _SPORT,
        "player":           "NRFI",
        "team":             away_team,             # L-9: single team name (away side)
        "stat":             stat,
        "line":             line,
        "direction":        direction,
        "proj":             normalize_proj(_PROJ_RAW),
        "win_prob":         win_prob,
        "edge":             normalize_edge(edge_raw),
        "odds":             normalize_american_odds(raw_odds),
        "book":             book,
        "tier":             _TIER,
        "pick_score":       _PICK_SCORE,
        "size":             normalize_size(size_raw),
        "game":             f"{away_team} @ {home_team}",
        "mode":             "",
        "result":           "",
        "closing_odds":     "",
        "clv":              "",
        "card_slot":        "",
        "is_home":          normalize_is_home("", stat),
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
    requests.post(
        _BONUS_WEBHOOK,
        json={"content": content},
        headers=default_headers({"Content-Type": "application/json"}),
        timeout=10,
    )


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Post a one-shot NRFI/pitcher-matchup bonus pick.")
    p.add_argument("--away-team",  default=_AWAY_TEAM,  help="Away team name")
    p.add_argument("--home-team",  default=_HOME_TEAM,  help="Home team name")
    p.add_argument("--odds",       default=_RAW_ODDS,   help="American odds (e.g. +108)")
    p.add_argument("--stat",       default=_STAT,       help="Stat key (e.g. NRFI)")
    p.add_argument("--line",       default=_LINE,       help="Line (e.g. 0.5)")
    p.add_argument("--direction",  default=_DIRECTION,  help="over or under")
    p.add_argument("--win-prob",   default=_WIN_PROB,   help="Win probability (e.g. 0.684)")
    p.add_argument("--edge",       default=_EDGE_RAW,   help="Edge (e.g. 0.213)")
    p.add_argument("--book",       default=_BOOK,       help="Book key (e.g. fanduel)")
    p.add_argument("--size",       default=_SIZE_RAW,   help="Unit size (e.g. 0.50)")
    a = p.parse_args(argv)

    row = _build_row(
        away_team=a.away_team,
        home_team=a.home_team,
        raw_odds=a.odds,
        stat=a.stat,
        line=a.line,
        direction=a.direction,
        win_prob=a.win_prob,
        edge_raw=a.edge,
        book=a.book,
        size_raw=a.size,
    )
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


# exec()-based tests must call main([]) explicitly after exec().
if __name__ == "__main__":
    main()
