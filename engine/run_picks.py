#!/usr/bin/env python3
"""
JonnyParlay MBP Runner v2.0 — Pure Python Engine
=================================================
Master Betting Prompt v9.4 (no Bravo Six)

Automates the full workflow:
  1. Reads SaberSim CSV projections
  2. Fetches live odds from The Odds API (all 23 US books + exchanges)
  3. Runs ALL math: Poisson/Normal distributions, no-vig, edge, gates, sizing
  4. Outputs the full betting card (sections A-J)

Zero external AI. Deterministic. Runs in ~30 seconds.

SETUP:
  pip install requests

USAGE:
  python run_picks.py                              # Interactive
  python run_picks.py nba.csv                      # Direct
  python run_picks.py nba.csv nhl.csv              # Multi-sport
  python run_picks.py nba.csv --mode Conservative  # Cold streak
  python run_picks.py nba.csv --dry-run            # Test odds pull only
  python run_picks.py nba.csv --cooldown "Reaves,Sheppard"  # R12 cooldown list
"""

import os, sys, csv, json, time, argparse, math, unicodedata, re, logging, tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager

# ── filelock (hard dep, shared with capture_clv.py + grade_picks.py) ──────────
# Audit C-1: filelock is a required dependency. Fallback removed — a missing
# lock silently re-enables the CLV daemon / grader race conditions Section 2
# and Section 3 were designed to close.
try:
    from filelock import FileLock, Timeout as _FileLockTimeout
except ImportError as e:
    raise ImportError(
        "filelock is required for pick_log/Discord-guard safety. "
        "Install it: pip install filelock --break-system-packages"
    ) from e

# Cross-process pick_log file lock lives in pick_log_lock.py (extract-and-re-export
# refactor, Step 1). Re-imported here so existing call sites and
# `from run_picks import ...` keep resolving. FileLock / _FileLockTimeout stay
# imported above (used directly in main()).
from pick_log_lock import _pick_log_lock  # noqa: E402

from datetime import datetime, timezone, timedelta, date
from zoneinfo import ZoneInfo
from pathlib import Path
from collections import defaultdict, OrderedDict

# ============================================================
#  CONFIG
# ============================================================

# Secrets (Odds API key + Discord webhooks) load from env / .env via
# secrets_config.py. See engine/secrets_config.py for the .env search path.
from secrets_config import (
    ODDS_API_KEY,
    EDGEMODEL_DB_PATH,
    DISCORD_WEBHOOK_URL,
    DISCORD_BONUS_WEBHOOK,
    DISCORD_ALT_PARLAY_WEBHOOK,
    DISCORD_RECAP_WEBHOOK,
    DISCORD_KILLSHOT_WEBHOOK,
    DISCORD_MONTHLY_WEBHOOK,
    DISCORD_ANNOUNCE_WEBHOOK,
    DISCORD_LONGSHOT_WEBHOOK,
    DISCORD_SGP_WEBHOOK,
)

# M9: resolved via paths.py — honours $JONNYPARLAY_ROOT
from paths import (  # noqa: E402
    PICK_LOG_PATH as _PICK_LOG_PATH_P,
    PICK_LOG_MANUAL_PATH as _PICK_LOG_MANUAL_PATH_P,
    PICK_LOG_MLB_PATH as _PICK_LOG_MLB_PATH_P,
    PICK_LOG_CALIBRATION_PATH as _PICK_LOG_CALIBRATION_PATH_P,
    PICK_LOG_SHADOW_STATS_PATH as _PICK_LOG_SHADOW_STATS_PATH_P,
    PICK_LOG_BLOCKED_PATH as _PICK_LOG_BLOCKED_PATH_P,
    DISCORD_GUARD_FILE as _DISCORD_GUARD_FILE_P,
    LOG_FILE_PATH as _LOG_FILE_PATH_P,
    project_path as _project_path,
    data_path as _data_path,
)

CSV_FOLDER    = str(_project_path("projections"))
# Additional drop locations scanned by find_csvs(). Preserves backward compatibility
# with the primary CSV_FOLDER while also picking up SaberSim exports from Downloads.
CSV_FOLDER_FALLBACKS = [
    os.path.expanduser("~/Downloads/projections"),
    os.path.expanduser("~/Downloads"),
]
OUTPUT_FOLDER = str(_data_path("picks"))
PICK_LOG_PATH = str(_PICK_LOG_PATH_P)
# Manual picks (entered via --log-manual) go to their own file so they don't
# pollute the model-generated log, don't burn CLV API calls (markets often
# missing), and don't confuse analysis of model performance.
PICK_LOG_MANUAL_PATH = str(_PICK_LOG_MANUAL_PATH_P)
LOG_FILE_PATH = str(_LOG_FILE_PATH_P)
DISCORD_GUARD_FILE = str(_DISCORD_GUARD_FILE_P)
PICK_LOG_BLOCKED_PATH = str(_PICK_LOG_BLOCKED_PATH_P)

# ── File logger setup (file only — console output stays as print()) ───────────
# Rotation is wired through engine/log_setup.attach_rotating_handler so
# jonnyparlay.log can't grow unbounded. Audit M-25 closed Apr 20 2026. The
# helper is idempotent, so if grade_picks.py is imported alongside this module
# (happens in some tests) we don't end up with duplicate handlers on the
# "jonnyparlay" logger.
from log_setup import attach_rotating_handler  # noqa: E402
logger = logging.getLogger("jonnyparlay")
logger.setLevel(logging.INFO)
attach_rotating_handler(logger, LOG_FILE_PATH)
logger.propagate = False  # Don't bubble up to root logger (avoids duplicate prints)

# Context research verdicts (display-only) load into discord_post.py (Step 16), where
# the embeds that read them now live; _CTX_VERDICTS is re-imported below with the rest
# of the Discord layer.

# Runtime/market wiring constants live in market_config.py (extract-and-re-export
# refactor, Step 8). Re-imported here so existing call sites and
# `from run_picks import ...` keep resolving.
from market_config import (  # noqa: E402
    ODDS_BASE, ODDS_REGIONS, API_SLEEP, SPORT_KEYS,
    SHADOW_SPORTS, SHADOW_STATS, SHADOW_GATE_CODES,
    _BLOCKED_LOG_SKIP_GATES, _BLOCKED_LOG_COLS, SHADOW_LOG_PATHS,
    SPORT_ALT_MARKET, PROP_MARKETS, MARKET_TO_STAT, MARKET_TO_STAT_OVERRIDE,
    WNBA_TEAM_ABBREV, SUSPENDED_STATS, SLOW_BOOKS, TEAM_ABBREV,
)

# Colorado-legal sportsbooks — line shopping filtered to these only.
# Canonical definition lives in book_names.py (audit H-13).
from book_names import CO_LEGAL_BOOKS, BOOK_DISPLAY, norm_book as _norm_book, display_book  # noqa: E402

# Canonical pick_log schema lives in pick_log_schema.py (audit H-3).
# HEADER and BONUS_HEADER below are aliases of CANONICAL_HEADER — no drift possible.
from pick_log_schema import (  # noqa: E402
    CANONICAL_HEADER,
    SCHEMA_VERSION as PICK_LOG_SCHEMA_VERSION,
    assert_manual_row_valid as _assert_manual_row_valid,
    migrate_row as _migrate_pick_row,
    normalize_american_odds as _normalize_odds,
    # M-3/M-10/M-11/M-12: write-time data-contract normalizers.
    normalize_is_home as _normalize_is_home,
    normalize_size as _normalize_size,
    normalize_proj as _normalize_proj,
    normalize_edge as _normalize_edge,
    # M-13: sidecar writer — fires once per successful pick_log write.
    write_schema_sidecar as _write_schema_sidecar,
)

# Canonical player-name folding (audit H-3). Every caller that compares
# player names must go through fold_name so "Dončić" / "Doncic" collapse
# to the same key.
from name_utils import fold_name as _fold_name, name_key  # noqa: E402

# Shared HTTP helpers (audit M-16). Canonical User-Agent on every outbound
# Odds API request.
from http_utils import default_headers  # noqa: E402

# Centralized brand constants (audit L-7) — tagline lives in brand.py.
from brand import BRAND_TAGLINE  # noqa: E402

# Shared atomic-JSON writer (architectural note #2). Replaces the bespoke
# tmp+fsync+replace dance that used to live inline at every guard-file save.
from io_utils import atomic_write_json  # noqa: E402

# Golf code removed — see archived_golf_code.py

# ============================================================
#  DISCORD WEBHOOK CONFIG
# ============================================================
# Webhook URLs are imported from secrets_config.py at the top of this file.
# To rotate, edit `.env` (gitignored) at project root or user home dir.
# Bot display name on all webhooks: PicksByJonny

# Structural decision-boundary constants live in thresholds.py (extract-and-re-export
# refactor, Step 9). Re-imported here so existing call sites and
# `from run_picks import ...` keep resolving.
from thresholds import (  # noqa: E402
    BONUS_DAILY_CAP, MIN_BONUS_SCORE, MIN_BONUS_WIN_PROB,
    MIN_DAILY_LAY_PROB, MIN_DAILY_LAY_MARGIN, MIN_LEG_EDGE_DAILY, MIN_LEG_COVER_PROB_DAILY,
    LONGSHOT_SIZE, VALUE_PARLAY_SIZE, LONGSHOT_MAX_PER_GAME, LONGSHOT_PAIR_RHO, SGP_LOG_SIZE,
    KILLSHOT_SCORE_FLOOR, KILLSHOT_WP_MARGIN, KILLSHOT_ODDS_MIN, KILLSHOT_ODDS_MAX,
    KILLSHOT_STAT_ALLOW, KILLSHOT_MANUAL_FLOOR, KILLSHOT_WEEKLY_CAP,
    KILLSHOT_SIZE_BASE, KILLSHOT_SIZE_BUMP, KILLSHOT_BUMP_WIN_PROB, KILLSHOT_BUMP_EDGE,
    POISSON_CUTOFF,
    WNBA_SEASON_START, WNBA_OPENING_GATE_DAYS, WNBA_OPENING_GATE_GAMES,
    WNBA_EARLY_SEASON_EDGE_MULT, WNBA_EV_FLOOR,
    PLATT_SPACE, F5_SCALAR, BLEND_ALPHA,
    BM_SHRINKAGE_DEFAULT, KELLY_FRACTION, DEFAULT_MARKET_MULT,
    MAX_PREMIUM_PICKS, MIN_PICK_SCORE, MIN_OVER_SCORE, MIN_WIN_PROB,
)
BRAND_LOGO = "https://cdn.discordapp.com/attachments/1115840612915228727/1225636209221566625/JonnyParlaylogoRedBlack.png"

# ============================================================
#  SIGMA & TIER CONFIG (v9.4)
# ============================================================

# Calibrated/fitted constants live in calibrated.py (extract-and-re-export refactor,
# Step 10). Re-imported here so existing call sites and `from run_picks import ...`
# keep resolving. The get_game_sigma* accessors stay below (they use resolve_team_abbrev
# + math) and read the re-imported _TEAM_SIGMAS / GAME_SIGMA. _load_team_sigmas() runs
# at calibrated.py import — _TEAM_SIGMAS / _TEAM_SIGMAS_MEANSQ arrive already populated.
from calibrated import (  # noqa: E402
    SIGMA, POISSON_STATS, NB_STATS, NB_R, NB_R_WNBA,
    COMBO_STATS, COMBO_COMPONENTS, COMBO_RHO, SIGMA_WNBA, COMBO_RHO_WNBA,
    PITCHER_STATS, BATTER_CORR_STATS, MLB_CORR_GROUPS,
    PLATT_A, PLATT_B, GAME_SIGMA,
    _TEAM_SIGMAS, _TEAM_SIGMAS_MEANSQ,
    _FIXED_SPREAD_SPORTS, F5_SIGMA, MLB_PARK_FACTORS, MLB_TEAM_RUN_R,
    STAT_FAMILY_TIER, TIERS, BM_SHRINKAGE_WEIGHT, KELLY_MARKET_MULT, VAKE_MULT,
    PICK_SCORE_MODES, COLD_START_SCORE_PENALTY,
    INJURY_TRIGGER_BONUS, INJURY_TRIGGER_BONUS_DEFAULT,
)

# WNBA early-season/opening gate constants (WNBA_SEASON_START, WNBA_OPENING_GATE_*,
# WNBA_EARLY_SEASON_EDGE_MULT, WNBA_EV_FLOOR) now live in thresholds.py (re-imported at top).
# WNBA early-season factor + opening-gate games-played helper live in wnba_gate.py
# (extract-and-re-export refactor, Step 3). Re-imported here so existing call sites
# and `from run_picks import ...` keep resolving. _WNBA_GP_CACHE is the same dict
# object (re-import binds the identity), so in-place clears via run_picks still work.
from wnba_gate import (  # noqa: E402
    _WNBA_GP_CACHE, _wnba_early_season_factor, _wnba_team_games_played,
)

# PLATT_A/PLATT_B, GAME_SIGMA, and the team-sigma loader (_TEAM_SIGMAS,
# _TEAM_SIGMAS_MEANSQ, _load_team_sigmas) now live in calibrated.py (re-imported at top;
# _load_team_sigmas runs at that import, so _TEAM_SIGMAS arrives populated).
#
# Team-name / sigma accessors live in team_resolve.py (extract-and-re-export
# refactor, Step 2). Re-imported here so existing call sites and
# `from run_picks import ...` keep resolving. They read GAME_SIGMA / _TEAM_SIGMAS /
# _TEAM_SIGMAS_MEANSQ / MLB_TEAM_RUN_R (from calibrated) and TEAM_ABBREV
# (from market_config).
from team_resolve import (  # noqa: E402
    get_game_sigma, get_game_sigma_team, get_mlb_team_run_r,
    resolve_team_abbrev, find_team_proj, get_team_abbrev,
)

# _FIXED_SPREAD_SPORTS, F5_SIGMA, MLB_PARK_FACTORS, MLB_TEAM_RUN_R now live in
# calibrated.py (re-imported at top).

# STAT_FAMILY_TIER, TIERS, BM_SHRINKAGE_WEIGHT, KELLY_MARKET_MULT, VAKE_MULT,
# PICK_SCORE_MODES, COLD_START_SCORE_PENALTY, INJURY_TRIGGER_BONUS(_DEFAULT) now live in
# calibrated.py (re-imported at top).

# Sportsbook display / normalization — imported above from book_names (audit H-13).
# Keeping CO_LEGAL_BOOKS, BOOK_DISPLAY, _norm_book, display_book callable at
# module level for backwards-compat with legacy call sites that reference them
# as run_picks.CO_LEGAL_BOOKS etc.
# SLOW_BOOKS and TEAM_ABBREV now live in market_config.py (re-imported at top).

# ============================================================
#  MATH ENGINE
# ============================================================

# Distribution PMFs/CDFs extracted to quant/distributions.py (pure, property-tested).
# Re-imported here so every call site below and `from run_picks import ...` keep working.
from quant.distributions import (  # noqa: E402
    poisson_pmf,
    poisson_cdf,
    normal_cdf,
    negbinom_pmf,
    negbinom_cdf,
)


# Derived probability calcs extracted to quant/derived.py (pure, property-tested).
from quant.derived import mlb_ml_from_nb, calc_tb_prob, calc_edge  # noqa: E402


# Odds/probability conversions extracted to quant/odds.py (pure, property-tested).
from quant.odds import implied_prob, no_vig, is_decimal_leak  # noqa: E402

# Probability/scoring core lives in prob_core.py (extract-and-re-export refactor,
# Step 5). Re-imported here so existing call sites and `from run_picks import ...`
# keep resolving. It reads PLATT_*/POISSON_*/NB_*/SIGMA*/COMBO_*/PICK_SCORE_* (from
# thresholds + calibrated), the quant.distributions PMF/CDFs, and
# _wnba_early_season_factor (from wnba_gate). (calc_tb_prob / calc_edge live in
# quant/derived.py, imported above.)
from prob_core import (  # noqa: E402
    _platt_calibrate_prop, calc_prop_prob, _combo_mu_sigma,
    calc_combo_prob, pick_score,
)

# Core sizing/Kelly/tier-routing helpers live in sizing_core.py (extract-and-re-export
# refactor, Step 4). Re-imported here so existing call sites and
# `from run_picks import ...` keep resolving. They read BM_SHRINKAGE_* / KELLY_*
# / STAT_FAMILY_TIER / TIERS (from thresholds + calibrated) and implied_prob
# (from quant.odds).
from sizing_core import (  # noqa: E402
    apply_bm_shrinkage, kelly_units, round_units,
    get_market_mult, get_tier, get_tier_min_edge,
)

# ============================================================
#  GATES
# ============================================================

# Prop / game-line gate checks live in gates.py (extract-and-re-export refactor,
# Step 9). Re-imported here so existing call sites and `from run_picks import ...`
# keep resolving. They read SUSPENDED_STATS, the WNBA threshold constants, the SIGMA/
# stat-set calibration, implied_prob, the WNBA gate helpers and _combo_mu_sigma.
from gates import check_prop_gates, check_game_gates  # noqa: E402


# ============================================================
#  RULES ENGINE (R1-R12)
# ============================================================

# Hard rules / R12 cooldown / soft-rule premium selection / daily caps live in
# rules.py (extract-and-re-export refactor, Step 8). Re-imported here so existing
# call sites and `from run_picks import ...` keep resolving. They read the threshold
# floors, PITCHER_STATS/COMBO_STATS, the file lock, log_blocked_pick and normalize_name.
from rules import (  # noqa: E402
    apply_hard_rules, auto_r12_from_log, apply_r12_cooldown,
    apply_soft_rules_premium, apply_caps,
)



# MAX_PREMIUM_PICKS, MIN_PICK_SCORE, MIN_OVER_SCORE, MIN_WIN_PROB now live in
# thresholds.py (re-imported at top).


# Note: SGP (0.25u), Longshot (0.25u), and Daily Lay (up to 0.75u) are logged
# AFTER apply_caps() runs and do not consume from the 12u hard cap tracked here.
# Effective per-session ceiling is ~13.25u. Cross-run protection (units_already_bet)
# applies to the primary/bonus pool only.

# ============================================================
#  VAKE SIZING
# ============================================================

# Stake-sizing functions live in sizing.py (extract-and-re-export refactor, Step 10,
# executed before Step 6 because format_output depends on size_daily_lay). Re-imported
# here so existing call sites and `from run_picks import ...` keep resolving. They read
# VAKE_MULT (calibrated) and kelly_units / get_market_mult / round_units (sizing_core).
from sizing import (  # noqa: E402
    size_picks_base, size_bonus_pick, size_picks_vake, size_daily_lay,
)

# ============================================================
#  CSV PARSER
# ============================================================

# Player-name normalization lives in name_norm.py (extract-and-re-export refactor,
# Step 1.5). Re-imported here so existing call sites and `from run_picks import ...`
# keep resolving.
from name_norm import normalize_name  # noqa: E402


# SaberSim CSV parsing + Odds API fetch/extract live in odds_io.py (extract-and-
# re-export refactor, Step 11). Re-imported here so existing call sites and
# `from run_picks import ...` keep resolving. odds_io owns its own `import requests`;
# run_picks keeps its requests import for the Discord webhook poster.
from odds_io import (  # noqa: E402
    parse_csv, OddsFetcher,
    extract_player_props, extract_game_lines, extract_team_totals,
    extract_alt_spreads, extract_f5_lines,
)

# ============================================================
#  ODDS FETCHER
# ============================================================

import requests


# ============================================================
#  ODDS PARSER — extract best lines from API response
# ============================================================







# ============================================================
#  PLAYER MATCHING
# ============================================================

# Prop / game-line / F5 / NRFI evaluators + prop matcher live in evaluators.py
# (extract-and-re-export refactor, Step 13). Re-imported here so existing call sites
# and `from run_picks import ...` keep resolving. evaluators wires prob_core,
# sizing_core, team_resolve, gates and the quant layer over the calibrated constants.
from evaluators import (  # noqa: E402
    match_props_to_projections, evaluate_props, evaluate_game_lines,
    evaluate_f5_lines, evaluate_nrfi,
)

# ============================================================
#  MAIN PIPELINE
# ============================================================



# Golf outright evaluation removed — see archived_golf_code.py




# ============================================================
#  DEDUPLICATION
# ============================================================

# Pick-pool dedup + negative-correlation filters live in correlation.py (extract-and-
# re-export refactor, Step 12). Re-imported here so existing call sites and
# `from run_picks import ...` keep resolving. They read MLB_CORR_GROUPS (calibrated).
from correlation import (  # noqa: E402
    deduplicate, filter_game_line_correlations, dedup_game_line_correlation,
    filter_cross_type_correlations, warn_tt_divergence,
)




# Backward-compat alias — external callers and existing tests still work.




# ── CHANGE 2: Team-total lambda divergence warning ─────────────────────────────



# ── CHANGE 3: Pre-post thesis block ───────────────────────────────────────────

_GL_STATS_THESIS = {"ML_FAV", "ML_DOG", "SPREAD", "TOTAL", "TEAM_TOTAL",
                    "F5_ML", "F5_SPREAD", "F5_TOTAL", "NRFI", "YRFI"}


def print_thesis_block(picks_pre: list, picks_post: list) -> None:
    """Print a per-game thesis block comparing pre- and post-GLC game-line picks.

    For each game that has game-line picks in either list, print:
      PRE-GLC : all qualified game-line picks for that game
      POST-GLC: game-line picks that survived the GLC filter
      Dropped : legs removed by the GLC filter

    Only fires when at least one game has multiple game-line picks pre-GLC.
    """
    def _gl(picks):
        return [p for p in picks if p.get("stat") in _GL_STATS_THESIS]

    pre_gl = _gl(picks_pre)
    post_gl = _gl(picks_post)
    post_keys = {
        (p.get("game",""), p.get("stat",""), p.get("direction",""), p.get("is_home"))
        for p in post_gl
    }

    # Group pre-GLC by game
    by_game: dict = defaultdict(list)
    for p in pre_gl:
        by_game[p.get("game", "")].append(p)

    multi_games = {g: ps for g, ps in by_game.items() if len(ps) >= 2}
    if not multi_games:
        return

    print("\n  ── Thesis Check (game-line picks per game) ──")
    for game, pre_picks in sorted(multi_games.items()):
        print(f"  {game}:")
        for p in sorted(pre_picks, key=lambda x: -(x.get("pick_score") or 0)):
            key = (p.get("game",""), p.get("stat",""), p.get("direction",""), p.get("is_home"))
            survived = key in post_keys
            marker = "  " if survived else "  [DROPPED]"
            score = p.get("pick_score") or 0
            print(
                f"    {'✓' if survived else '✗'} {p.get('player',''):<28} "
                f"{p.get('stat',''):<12} {p.get('direction',''):<6} "
                f"score={score:.1f}{marker}"
            )
    print()


# ============================================================
#  PARLAY BUILDERS
# ============================================================

# prob_to_american extracted to quant/odds.py (pure, property-tested).
from quant.odds import prob_to_american  # noqa: E402

# Parlay BUILDERS (longshot safest-6, value 5-leg fallback, alt-spread daily lay)
# live in parlays.py (extract-and-re-export refactor, Step 14). Re-imported here so
# existing call sites and `from run_picks import ...` keep resolving. The Discord
# post_* parlay functions stay below (they move to discord_post.py in Step 16).
from parlays import (  # noqa: E402
    _longshot_pos_corr_pair, _longshot_effective_wp,
    build_safest6_parlay, build_value_parlay, build_alt_spread_parlay,
)


# ============================================================
#  OUTPUT FORMATTER
# ============================================================

# Console/text card formatting (fmt_* + format_output) lives in output_format.py
# (extract-and-re-export refactor, Step 6). Re-imported here so existing call sites
# and `from run_picks import ...` keep resolving. It reads display_book (book_names),
# SLOW_BOOKS (market_config), SIGMA*/POISSON_STATS/PITCHER_STATS/BATTER_CORR_STATS
# (calibrated), LONGSHOT_SIZE/MAX_PREMIUM_PICKS (thresholds) and size_daily_lay (sizing).
from output_format import fmt_odds, fmt_dir, fmt_pct, format_output  # noqa: E402

# Pick-log CSV writers + legs-JSON helpers live in pick_log_writers.py (extract-and-
# re-export refactor, Step 7; the name pick_log_io.py was already taken by the locked
# readers module). Re-imported here so existing call sites and `from run_picks import ...`
# keep resolving. The writers read the pick_log_schema normalizers plus the file lock,
# blocked-log columns, book normaliser, longshot sizes, and size_daily_lay from sizing.
# PICK_LOG_PATH / PICK_LOG_BLOCKED_PATH stay defined above.
from pick_log_writers import (  # noqa: E402
    log_blocked_pick, log_candidates, log_picks,
    _daily_lay_legs_json, _log_daily_lay, _legs_json,
    _log_longshot, _log_value_parlay, _log_bonus_pick,
)






# ============================================================
#  DISCORD POSTING FUNCTIONS
# ============================================================

# The Discord I/O layer — webhook posting, post-dedup guard, confirm-mode, the
# context-verdict cache, every embed builder + poster, and the post-guard / session-cap
# query helpers the posters depend on — lives in discord_post.py (extract-and-re-export
# refactor, Step 16). Re-imported here so existing call sites and `from run_picks import
# ...` keep resolving (the SGP builders import _webhook_post from run_picks). main() uses
# set_confirm_mode()/get_confirm_mode() for the --confirm flag rather than rebinding a
# module global (a mutated global cannot be shared across a re-export).
from discord_post import (  # noqa: E402
    set_confirm_mode, get_confirm_mode, _confirm_post,
    _CTX_VERDICTS,
    _prune_discord_guard, _load_discord_guard, _save_discord_guard,
    _discord_already_posted, _discord_mark_posted, _discord_claim_post,
    _discord_release_post, _notify_post_failure, _webhook_post,
    build_premium_embed, build_potd_embed, post_to_discord,
    post_daily_lay, post_longshot, post_value_parlay,
    _card_guard_should_block_logging, _card_already_posted_today, _units_bet_today,
    post_extras_to_discord, build_killshot_embed, post_killshots_to_discord,
)


# ============================================================
#  KILLSHOT TIER
# ============================================================

# KILLSHOT selection / gating / sizing + the fail-fast invariant assertion live in
# killshot.py (extract-and-re-export refactor, Step 15). Re-imported here so existing
# call sites and `from run_picks import ...` keep resolving. _assert_killshot_invariants()
# now fires at import of killshot.py (still fail-fast at engine start). The KILLSHOT
# Discord embed + poster stay below (they move to discord_post.py in Step 16).
from killshot import (  # noqa: E402
    _killshot_size, _killshot_odds_wp_ok, _passes_killshot_v2_gate,
    _assert_killshot_invariants, _killshots_this_week, select_killshots,
)


# build_killshot_embed + post_killshots_to_discord live in discord_post.py (Step 16);
# re-imported above with the rest of the Discord layer.

# format_output moved to output_format.py (re-imported above with fmt_odds/fmt_dir/fmt_pct).

# ============================================================
#  MAIN
# ============================================================

def find_csvs(folder=None):
    """Scan primary CSV_FOLDER plus fallbacks (Downloads\\projections, Downloads\\).
    If `folder` is given, only that folder is scanned (preserves legacy behavior).
    De-duplicates by resolved path so the same CSV shows only once.
    """
    if folder is not None:
        scan_dirs = [Path(folder)]
    else:
        scan_dirs = [Path(CSV_FOLDER)] + [Path(p) for p in CSV_FOLDER_FALLBACKS]

    collected = []
    seen = set()
    for d in scan_dirs:
        if not d.exists():
            continue
        for c in d.glob("*.csv"):
            key = str(c.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            collected.append(c)

    collected.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    result = []
    for c in collected[:20]:
        try:
            with open(c, "r", encoding="utf-8-sig") as f:
                hdr = f.readline().lower()
            if any(k in hdr for k in ["saber", "ast", "rb", "sog", "pts", "win%", "make cut", "birdies"]):
                result.append(c)
        except OSError:
            continue
    return result

def _build_arg_parser():
    """Construct the run_picks CLI argument parser (extracted from main(), Step 17).
    Pure setup — no dependency on main() locals; returns the configured parser."""
    parser = argparse.ArgumentParser(description="JonnyParlay MBP Runner v2.0 — Pure Python")
    parser.add_argument("csvs", nargs="*", help="SaberSim CSV file(s)")
    parser.add_argument("--mode", default="Default", choices=["Default", "Conservative", "Aggressive"])
    parser.add_argument("--exclude", default="", help="Teams to exclude")
    parser.add_argument("--cooldown", default="", help="R12 cooldown players (comma-separated last names)")
    parser.add_argument("--output", default=None)
    parser.add_argument("--no-save", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Fetch odds only")
    parser.add_argument("--parlays-only", action="store_true", help="Only output Longshot + Alt Spread parlays")
    parser.add_argument("--alt-parlay", action="store_true", help="Only output Alt Spread parlay (skips props, minimal API calls)")
    parser.add_argument("--no-cache", action="store_true", help="Skip odds cache, force fresh API calls")
    parser.add_argument("--force-card", action="store_true",
                        help="Override the daily premium card guard and repost even if the card "
                             "was already posted today. Useful for fixing a malformed card. "
                             "Dedup logic still prevents double-logging picks to pick_log.csv.")  # L11
    parser.add_argument("--force", action="store_true", help="Skip game start-time filter (test with already-started games)")
    parser.add_argument("--skip-health-check", action="store_true",
                        help="Bypass the pre-run config-integrity gate (P2.10). Used by replay/tests "
                             "(which validate pricing, not environment health). Use in production only "
                             "if you understand why a blocking check is failing.")
    parser.add_argument("--no-discord", action="store_true", help="Skip all Discord posts (dry run for Discord only)")
    parser.add_argument("--no-cap", action="store_true",
                        help="Log ALL qualified picks instead of top-5 premium only. "
                             "Requires --no-discord (safety guard). Use with shadow mode for "
                             "faster CLV accumulation — does not affect Discord or live pick flow.")
    parser.add_argument("--test",       action="store_true", help="Suppress @everyone ping on all Discord posts (safe preview)")
    parser.add_argument("--repost",     action="store_true", help="Re-fire premium card + POTD from the most recent primary log entry")

    parser.add_argument("--killshot", default="", help="Manually promote picks to KILLSHOT tier (comma-separated player last names, e.g. 'Pastrnak,McDavid')")
    parser.add_argument("--log-manual", action="store_true", help="Log a manually posted pick to pick_log.csv (interactive prompt)")
    parser.add_argument("--debug-daily-lay", action="store_true", help="Verbose debug output for alt spread parlay builder")
    parser.add_argument("--repost-daily-lay", action="store_true", help="Force-post the daily lay even if card was already posted today")
    parser.add_argument("--confirm",    action="store_true", help="Prompt y/n before every Discord post")
    parser.add_argument("--max-per-game", type=int, default=2,
                        help="R7 override: max picks per game (default 2). Use on thin-slate nights e.g. --max-per-game 5")
    parser.add_argument("--no-sgp", action="store_true", help="Skip SGP builder (same-game parlay suggestions)")
    parser.add_argument("--sgp-only", action="store_true", help="Run SGP builder only — skip everything else (premium card, bonus, daily lay, longshot, killshots)")
    parser.add_argument("--sgp-debug", action="store_true", help="Verbose per-game debug output for MLB SGP builder")
    parser.add_argument("--bonus-only", action="store_true", help="Run bonus drop + SGP only; skip premium card, daily lay, longshot, killshots, preview")
    parser.add_argument("--log-candidates", action="store_true",
                        help="Log all gate-passing picks (full candidate pool) to data/pick_log_candidates.csv "
                             "with alternative formula scores. Use for backtesting formula changes.")

    return parser


def _parse_exclude_teams(args):
    """Resolve --exclude into a normalized set of team names (extracted from main(), Step 17)."""
    # Parse exclude list — accepts team names, abbreviations, or city names
    exclude_raw = [s.strip().lower() for s in args.exclude.split(",") if s.strip()]
    # Common abbreviation/name mappings
    TEAM_ALIASES = {
        "celtics": "boston celtics", "bos": "boston celtics", "boston": "boston celtics",
        "hornets": "charlotte hornets", "cha": "charlotte hornets", "charlotte": "charlotte hornets",
        "wizards": "washington wizards", "was": "washington wizards", "washington": "washington wizards",
        "raptors": "toronto raptors", "tor": "toronto raptors", "toronto": "toronto raptors",
        "blazers": "portland trail blazers", "trailblazers": "portland trail blazers", "por": "portland trail blazers", "portland": "portland trail blazers",
        "magic": "orlando magic", "orl": "orlando magic", "orlando": "orlando magic",
        "kings": "sacramento kings", "sac": "sacramento kings", "sacramento": "sacramento kings",
        "nets": "brooklyn nets", "bkn": "brooklyn nets", "brooklyn": "brooklyn nets",
        "lakers": "los angeles lakers", "lal": "los angeles lakers",
        "clippers": "la clippers", "lac": "la clippers",
        "knicks": "new york knicks", "nyk": "new york knicks",
        "warriors": "golden state warriors", "gsw": "golden state warriors",
        "nuggets": "denver nuggets", "den": "denver nuggets", "denver": "denver nuggets",
        "thunder": "oklahoma city thunder", "okc": "oklahoma city thunder",
        "rockets": "houston rockets", "hou": "houston rockets", "houston": "houston rockets",
        "pelicans": "new orleans pelicans", "nop": "new orleans pelicans",
        "suns": "phoenix suns", "phx": "phoenix suns",
        "mavs": "dallas mavericks", "dal": "dallas mavericks", "mavericks": "dallas mavericks",
        "heat": "miami heat", "mia": "miami heat",
        "bucks": "milwaukee bucks", "mil": "milwaukee bucks",
        "76ers": "philadelphia 76ers", "sixers": "philadelphia 76ers", "phi": "philadelphia 76ers",
        "hawks": "atlanta hawks", "atl": "atlanta hawks",
        "bulls": "chicago bulls", "chi": "chicago bulls",
        "cavs": "cleveland cavaliers", "cle": "cleveland cavaliers", "cavaliers": "cleveland cavaliers",
        "pistons": "detroit pistons", "det": "detroit pistons",
        "pacers": "indiana pacers", "ind": "indiana pacers",
        "grizzlies": "memphis grizzlies", "mem": "memphis grizzlies",
        "timberwolves": "minnesota timberwolves", "min": "minnesota timberwolves", "wolves": "minnesota timberwolves",
        "spurs": "san antonio spurs", "sas": "san antonio spurs",
        "jazz": "utah jazz", "uta": "utah jazz",
        # NHL
        "avalanche": "colorado avalanche", "col": "colorado avalanche", "avs": "colorado avalanche",
        "blackhawks": "chicago blackhawks",
        "devils": "new jersey devils", "njd": "new jersey devils",
        "flyers": "philadelphia flyers",
        "penguins": "pittsburgh penguins", "pit": "pittsburgh penguins", "pens": "pittsburgh penguins",
        "islanders": "new york islanders", "nyi": "new york islanders",
        "flames": "calgary flames", "cgy": "calgary flames",
        "maple leafs": "toronto maple leafs", "leafs": "toronto maple leafs",
        "ducks": "anaheim ducks", "ana": "anaheim ducks",
        "blues": "st louis blues", "stl": "st louis blues",
        "sharks": "san jose sharks", "sjs": "san jose sharks",
        "canucks": "vancouver canucks", "van": "vancouver canucks",
        "golden knights": "vegas golden knights", "vgk": "vegas golden knights", "knights": "vegas golden knights",
        "stars": "dallas stars",
    }
    exclude_teams = set()
    for ex in exclude_raw:
        if ex in TEAM_ALIASES:
            exclude_teams.add(TEAM_ALIASES[ex])
        else:
            exclude_teams.add(ex)  # keep raw for fuzzy matching

    return exclude_teams


def _resolve_cooldown(args):
    """Merge --cooldown with auto-R12 pick-log losses into one cooldown list (extracted from main(), Step 17)."""
    cooldown = [s.strip() for s in args.cooldown.split(",") if s.strip()]

    # Auto-R12: merge pick_log losses (last 5 days) into cooldown list automatically
    today_str_main = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    auto_cool = auto_r12_from_log(today_str_main, window_days=5)
    if auto_cool:
        # Merge: manual --cooldown takes precedence, auto adds any not already listed
        manual_cool_norm = {normalize_name(n) for n in cooldown}
        for p in auto_cool:
            if normalize_name(p) not in manual_cool_norm:
                cooldown.append(p)

    return cooldown


def _stage_load_csvs(args):
    """Load + parse SaberSim CSV(s) and patch MLB starters (extracted from main(), Step 17).
    Returns (all_players, sports, csv_paths_resolved). May sys.exit on no-CSV / empty selection."""
    # --- CSV ---
    csv_paths = []
    if args.csvs:
        csv_paths = [Path(c) for c in args.csvs]
    else:
        found = find_csvs()
        if not found:
            print(f"  No SaberSim CSVs in {CSV_FOLDER}")
            print("  Usage: python run_picks.py path/to/nba.csv")
            sys.exit(1)
        print(f"  Found {len(found)} CSV(s):\n")
        for i, f in enumerate(found[:10]):
            # Display mtime in ET for consistency with pick_log dates (audit H-1).
            mt = datetime.fromtimestamp(f.stat().st_mtime, tz=ZoneInfo("America/New_York")).strftime("%m/%d %H:%M")
            print(f"    [{i+1}] {f.name} ({mt})")
        choice = input(f"\n  Select (e.g. '1' or '1,2'): ").strip()
        if not choice:
            sys.exit(0)
        indices = [int(x.strip())-1 for x in choice.split(",") if x.strip().isdigit()]
        csv_paths = [found[i] for i in indices if 0 <= i < len(found)]

    all_players = {}
    csv_paths_resolved = []
    for path in csv_paths:
        players, sport, resolved_path = parse_csv(path)
        csv_paths_resolved.append(resolved_path)
        if sport not in all_players:
            all_players[sport] = []
        all_players[sport].extend(players)

    sports = list(all_players.keys())

    # MLB pitcher confirmation: patch status="confirmed" from MLB Stats API when
    # SaberSim hasn't confirmed the pitcher yet (batting lineup lag).
    if "MLB" in all_players:
        try:
            from mlb_starter_fetcher import fetch_confirmed_starters as _mlb_starters, is_confirmed as _mlb_confirmed
            _today_mlb = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
            _mlb_api_starters = _mlb_starters(_today_mlb)
            if _mlb_api_starters:
                _patched = 0
                for _p in all_players["MLB"]:
                    if _p.get("is_pitcher") and _p.get("status", "").lower() != "confirmed":
                        if _mlb_confirmed(_p["name"], _p.get("team", ""), _mlb_api_starters):
                            _p["status"] = "confirmed"
                            _patched += 1
                if _patched:
                    print(f"  [MLB Starters] Patched {_patched} pitcher(s) confirmed via MLB Stats API")
            else:
                print("  [MLB Starters] No probable starters announced yet (MLB Stats API)")
        except Exception as _e:
            print(f"  [MLB Starters] Fetch skipped: {_e}")
            _unconfirmed = sum(1 for _p in all_players.get("MLB", []) if _p.get("is_pitcher") and _p.get("status", "").lower() != "confirmed")
            if _unconfirmed:
                print(f"  [MLB Starters] WARNING: {_unconfirmed} pitcher(s) unconfirmed — K/OUTS/HA props may be suppressed")
    return all_players, sports, csv_paths_resolved


def _stage_fetch_odds(sports, args):
    """Fetch live odds for all sports via the Odds API (extracted from main(), Step 17)."""
    fetcher = OddsFetcher()
    odds_data = fetcher.fetch_all(sports,
                                   fetch_alt_spreads=True,
                                   game_lines_only=args.alt_parlay,
                                   no_cache=args.no_cache,
                                   force=args.force)

    return odds_data


def _stage_evaluate(all_players, odds_data, args, cooldown):
    """Run the MBP engine: extract + match + evaluate props / game lines / F5 / NRFI
    across all sports (extracted from main(), Step 17). Returns
    (all_prop_picks, all_game_picks, all_game_lines, all_team_proj, all_alt_spreads)."""
    # --- EVALUATION ---
    print(f"\n  {'='*40}")
    print(f"  Running MBP v9.4 engine...")
    print(f"  {'='*40}")

    all_prop_picks = []
    all_game_picks = []
    all_game_lines = []  # For alt spread parlay
    all_team_proj = {}   # For alt spread parlay
    all_alt_spreads = [] # For alt spread parlay — real book prices

    for sport, players in all_players.items():
        sd = odds_data.get(sport, {})

        # Game lines (needed for all modes)
        game_lines = extract_game_lines(sd, sport)
        all_game_lines.extend(game_lines)

        # Alt spreads (real book prices for parlay)
        if sport == "NBA":
            alt_sp = extract_alt_spreads(sd, sport)
            all_alt_spreads.extend(alt_sp)

        # Build team projection map for this sport (keyed by sport+team to avoid DAL/DET collisions)
        for p in players:
            team = p["team"].upper()
            key = f"{sport}_{team}"
            if key not in all_team_proj:
                all_team_proj[key] = {"saber_total": p["saber_total"], "saber_team": p["saber_team"], "sport": sport}

        # Skip props + game line evaluation in alt-parlay mode
        if args.alt_parlay:
            continue

        # Props
        raw_props = extract_player_props(sd, sport)
        matched = match_props_to_projections(raw_props, players)
        print(f"\n  {sport}: {len(raw_props)} prop lines found, {len(matched)} matched to projections")

        prop_picks = evaluate_props(matched, args.mode, cooldown)
        all_prop_picks.extend(prop_picks)

        # Game line evaluation
        team_tots = extract_team_totals(sd, sport)
        gl_picks = evaluate_game_lines(game_lines, team_tots, players, sport, args.mode)
        all_game_picks.extend(gl_picks)

        # MLB-specific: F5 innings + NRFI/YRFI
        if sport == "MLB":
            f5_data = extract_f5_lines(sd, sport)
            f5_picks = evaluate_f5_lines(f5_data, players, args.mode)
            all_game_picks.extend(f5_picks)
            print(f"  MLB F5: {len(f5_data)} games, {len(f5_picks)} F5 picks evaluated")

            nrfi_picks = evaluate_nrfi(game_lines, players, sd, sport, args.mode)
            all_game_picks.extend(nrfi_picks)
            print(f"  MLB NRFI: {len(nrfi_picks)} NRFI/YRFI evaluated")

    return all_prop_picks, all_game_picks, all_game_lines, all_team_proj, all_alt_spreads


def _stage_build_parlays(qualified, premium, killshots, all_players, all_game_lines, all_team_proj, all_alt_spreads, args):
    """Build safest-5 list + longshot / value / alt-spread parlays (extracted from main(), Step 17).
    Excludes premium + KILLSHOT picks from the longshot pool. Returns
    (safest5, safest6_parlay, value_parlay, alt_spread_parlay)."""
    # Safest 5
    safest5 = sorted(qualified, key=lambda p: p["win_prob"], reverse=True)[:5] if qualified else []

    # Build parlays
    # H12: Exclude premium + KILLSHOT picks from longshot pool — same pick can't appear
    # on both the premium card and the longshot (duplicate disclosure, misleading bankroll).
    _card_keys = {(p.get("player", "").lower(), p.get("stat"), p.get("direction"))
                  for p in premium + killshots}
    _longshot_pool = [p for p in qualified
                      if (p.get("player", "").lower(), p.get("stat"), p.get("direction"))
                      not in _card_keys]
    _n_excluded = len(qualified) - len(_longshot_pool)
    if _n_excluded:
        logger.debug(f"Excluded {_n_excluded} premium picks from longshot pool")
    safest6_parlay = build_safest6_parlay(_longshot_pool)
    # 5-leg fallback: only builds if 6-leg longshot cannot be assembled
    value_parlay = build_value_parlay(_longshot_pool) if safest6_parlay is None else None
    if value_parlay:
        print(f"  [Value Parlay] Built 5-leg value parlay ({fmt_odds(value_parlay['parlay_odds'])} combined).")
    sport_sigmas = {}
    for sport in all_players:
        sport_sigmas[sport] = GAME_SIGMA.get(sport, GAME_SIGMA["NBA"])
    alt_spread_parlay = build_alt_spread_parlay(all_game_lines, all_team_proj, sport_sigmas, all_alt_spreads, debug=getattr(args, "debug_daily_lay", False))

    return safest5, safest6_parlay, value_parlay, alt_spread_parlay


def _stage_post_discord(args, premium, qualified, killshots, safest6_parlay, value_parlay,
                        alt_spread_parlay, today, today_str, suppress_ping, _sport_key, _card_was_already_up):
    """Post premium card / bonus / parlays / KILLSHOT to Discord per run mode
    (extracted from main(), Step 17). Side-effect only; no return."""
    if args.no_discord:
        print("\n  [Discord] --no-discord flag set -- skipping all Discord posts.")
    else:
        card_already_up = _card_was_already_up
        _bonus_only = getattr(args, "bonus_only", False)
        _sgp_only   = getattr(args, "sgp_only", False)

        _save = not args.no_save
        _repost_daily_lay = getattr(args, "repost_daily_lay", False)
        if _sgp_only:
            print("\n  [Discord] --sgp-only: skipping all posts -- SGP builder will run below.")
        elif card_already_up or _bonus_only:
            if _bonus_only:
                print("\n  [Discord] --bonus-only: skipping premium card, daily lay, longshot, killshots, preview.")
            else:
                print(f"\n  [Discord] {_sport_key} card already posted today -- skipping premium card, POTD, daily lay.")
            print("  [Discord] Running bonus drop check only...")
            post_extras_to_discord(qualified, save=_save)
            # Still attempt KILLSHOT posts — discord guard key prevents double-posting.
            # Covers the case where updated CSVs produce a new KILLSHOT after the card
            # was already posted (e.g. better projection data downloaded mid-afternoon).
            if not _bonus_only:
                post_killshots_to_discord(killshots, today, today_str, suppress_ping=suppress_ping)
            elif killshots:
                print(f"  [Discord] --bonus-only: skipping {len(killshots)} pending KILLSHOT(s) — run without --bonus-only to post.")
            if _repost_daily_lay:
                print("  [Discord] --repost-daily-lay: force-posting daily lay...")
                post_daily_lay(alt_spread_parlay, today_str, suppress_ping=True, save=_save)
        else:
            _force = getattr(args, "force_card", False)
            post_to_discord(premium, args.mode, today_str, suppress_ping=suppress_ping, force=_force, sport=_sport_key)
            post_extras_to_discord(qualified, save=_save)

            # Daily lay and longshot post silently -- no @everyone ping
            post_daily_lay(alt_spread_parlay, today_str, suppress_ping=True, save=_save)
            post_longshot(safest6_parlay, today_str, suppress_ping=True, save=_save)
            post_value_parlay(value_parlay, today_str, suppress_ping=True, save=_save)

            # -- KILLSHOT posts -> #killshot
            post_killshots_to_discord(killshots, today, today_str, suppress_ping=suppress_ping)



def _run_health_gate(skip):
    """Pre-run config-integrity gate (P2.10).

    Subprocess-runs ``health_check.py`` and ABORTS the run if any *blocking* check
    fails (advisory items — CLAUDE.md size, git cleanliness, calibration drift —
    are ``warn()`` and never block; health_check exits non-zero only on integrity
    failures). stdout-silent on pass, so it cannot perturb the card output captured
    by replay. Bypass with ``--skip-health-check`` (replay/tests validate pricing,
    not environment health). A health_check *crash* (non-zero with no FAIL lines)
    warns but does not block — a broken checker must not halt the business.
    """
    if skip:
        return
    hc = os.path.join(os.path.dirname(os.path.abspath(__file__)), "health_check.py")
    if not os.path.exists(hc):
        return  # health_check is optional; never block a run on its absence
    try:
        import subprocess
        res = subprocess.run([sys.executable, hc], capture_output=True,
                             text=True, timeout=60)
    except Exception as e:
        print(f"  [health-check] skipped ({type(e).__name__}: {e})", file=sys.stderr)
        return
    if res.returncode == 0:
        return
    fails = [ln.strip() for ln in (res.stdout or "").splitlines() if "FAIL" in ln]
    if not fails:
        # Non-zero exit but no FAIL lines → health_check itself errored. Warn, don't block.
        print("  [health-check] non-zero exit with no FAIL lines parsed — continuing "
              "(run `python engine/health_check.py` to inspect).", file=sys.stderr)
        return
    print("  ABORT: health_check reported blocking config-integrity failures:", file=sys.stderr)
    for ln in fails[:20]:
        print(f"    {ln}", file=sys.stderr)
    print("  Fix the above, or re-run with --skip-health-check if you understand the risk.",
          file=sys.stderr)
    sys.exit(1)


def main():
    args = _build_arg_parser().parse_args()

    # --no-cap safety guard: must be paired with --no-discord to prevent
    # accidentally logging every qualified pick to the live pick_log during a
    # real Discord run. This flag is only meaningful in shadow / research mode.
    if getattr(args, "no_cap", False) and not args.no_discord:
        print("  ERROR: --no-cap requires --no-discord (safety guard — use shadow/research mode only).")
        sys.exit(1)

    # M12: prevent emoji → UnicodeEncodeError crashes on Windows cmd.exe (cp1252)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # P2.10: config-integrity gate — abort before any betting work if a blocking
    # health_check fails. stdout-silent on pass; bypassed by --skip-health-check.
    _run_health_gate(getattr(args, "skip_health_check", False))

    # M8: prevent concurrent runs (double-post guard at the process level)
    _run_lock_path = str(_data_path("run_picks.lock"))
    _run_lock = FileLock(_run_lock_path, timeout=0)
    try:
        _run_lock.acquire()
    except _FileLockTimeout:
        print("ERROR: another run_picks.py is already running. Aborting to prevent double-post.")
        sys.exit(1)

    set_confirm_mode(args.confirm)

    print("""
    ╔═══════════════════════════════════════════╗
    ║  JonnyParlay MBP Runner v2.0              ║
    ║  Master Betting Prompt v9.4               ║
    ║  Pure Python — Zero AI, Deterministic     ║
    ╚═══════════════════════════════════════════╝
    """)

    all_players, sports, csv_paths_resolved = _stage_load_csvs(args)

    cooldown = _resolve_cooldown(args)

    exclude_teams = _parse_exclude_teams(args)

    # --- ODDS ---
    print(f"\n  Sports: {', '.join(sports)} | Mode: {args.mode}")
    if exclude_teams:
        print(f"  Excluding: {', '.join(sorted(exclude_teams))}")
    if cooldown:
        manual_listed = [s.strip() for s in args.cooldown.split(",") if s.strip()]
        auto_listed = [p for p in cooldown if p not in manual_listed]
        parts = []
        if manual_listed:
            parts.append(f"manual: {', '.join(manual_listed)}")
        if auto_listed:
            parts.append(f"auto: {', '.join(auto_listed)}")
        print(f"  R12 Cooldown: {' | '.join(parts)}")

    odds_data = _stage_fetch_odds(sports, args)

    if args.dry_run:
        out_path = Path(OUTPUT_FOLDER)
        out_path.mkdir(parents=True, exist_ok=True)
        # ET date for dry-run filename (audit H-1).
        dp = out_path / f"odds_dry_{datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d')}.json"
        with open(dp, "w", encoding="utf-8") as f:
            json.dump(odds_data, f, indent=2, default=str)
        print(f"\n  Dry run saved: {dp}")
        return

    all_prop_picks, all_game_picks, all_game_lines, all_team_proj, all_alt_spreads = _stage_evaluate(all_players, odds_data, args, cooldown)

    # === ALT-PARLAY FAST PATH ===
    if args.alt_parlay:
        sport_sigmas = {}
        for sport in all_players:
            if sport not in GAME_SIGMA:
                logger.debug("GAME_SIGMA: no entry for sport=%r — falling back to NBA", sport)
            sport_sigmas[sport] = GAME_SIGMA.get(sport) or GAME_SIGMA["NBA"]
        alt_spread_parlay = build_alt_spread_parlay(all_game_lines, all_team_proj, sport_sigmas, all_alt_spreads, debug=getattr(args, "debug_daily_lay", False))

        # ET-aware date header (audit H-1).
        today = datetime.now(ZoneInfo("America/New_York")).strftime("%B %d, %Y")
        pout = []
        pout.append(f"{'='*50}")
        pout.append(f"ALT SPREAD PARLAY — {today}")
        pout.append(f"3 Legs @ ~-500 Each")
        pout.append(f"{'='*50}")
        if alt_spread_parlay and alt_spread_parlay["legs"]:
            pout.append(f"  Book: {alt_spread_parlay.get('book', 'N/A')}")
            pout.append("")
            for i, leg in enumerate(alt_spread_parlay["legs"], 1):
                sign = "+" if leg["alt_spread"] > 0 else ""
                odds_str = fmt_odds(leg["real_odds"]) if leg.get("real_odds") else "N/A"
                pout.append(f"  {i}. {leg['team']} {sign}{leg['alt_spread']:.1f} ({odds_str})")
                pout.append(f"     {leg['game']} | Margin: {leg['margin']:+.1f} | Cover: {leg['alt_cover_prob']*100:.1f}%")
            pout.append(f"  ────────────────────────────────")
            pout.append(f"  Parlay Odds: {fmt_odds(alt_spread_parlay['parlay_odds'])}")
            pout.append(f"  Model Cover Prob: {alt_spread_parlay['combined_prob']*100:.1f}%")
        else:
            pout.append("  Not enough qualifying NBA game lines for 3-leg parlay.")
        print("\n" + "\n".join(pout))
        print("\n  Done. Let's eat.\n")
        return

    # Combine
    all_picks = all_prop_picks + all_game_picks

    # Exclude teams
    if exclude_teams:
        before = len(all_picks)
        all_picks = [p for p in all_picks
                     if not any(ex in p.get("game", "").lower() for ex in exclude_teams)]
        print(f"\n  Excluded {before - len(all_picks)} picks from {len(exclude_teams)} teams")

    # Hard rules (R4, R11) — shadow_dest collects R4/R11 kills for shadow logging
    _hard_rules_shadow: list = []
    all_picks = apply_hard_rules(all_picks, shadow_dest=_hard_rules_shadow, log_blocked=not args.no_save)

    # R12 cooldown
    all_picks = apply_r12_cooldown(all_picks, cooldown)

    # Split qualified vs failed
    qualified = [p for p in all_picks if p.get("gate_result") == "PASS" and p.get("pick_score") is not None]
    failed = [p for p in all_picks if p.get("gate_result") != "PASS" or p.get("pick_score") is None]

    # Calibration shadow: log ALL evaluated prop picks with valid over_p_raw,
    # regardless of gate result — removes selection bias and gives 10-50x more
    # calibration signal/day than pick_log.csv. Never posted; graded daily by
    # grade_picks.py. Respects --no-save like every other log writer.
    if not args.no_save:
        _calibration_picks = [
            p for p in all_picks
            if p.get("pick_type") == "prop"
            and p.get("over_p_raw") not in (None, "", "0", 0)
            and 0 < float(p.get("over_p_raw") or 0) < 1
        ]
        if _calibration_picks:
            log_picks(
                _calibration_picks, args.mode,
                log_path_override=Path(str(_PICK_LOG_CALIBRATION_PATH_P)),
                run_type="calibration",
            )
            print(f"  [Calibration] {len(_calibration_picks)} pick(s) "
                  f"logged to pick_log_calibration.csv")

    # Persist structural gate failures to pick_log_blocked.csv for frequency auditing.
    # Suspension gates are excluded (see _BLOCKED_LOG_SKIP_GATES).
    if not args.no_save:
        for p in failed:
            log_blocked_pick(p)

    # Extract direction/line-specific gate kills that should shadow-log instead of just fail.
    # These picks are already in `failed` (built and sized=0 by evaluate_props/evaluate_game_lines).
    _gate_shadow_picks = [p for p in failed if p.get("gate_result") in SHADOW_GATE_CODES]

    # Deduplicate
    qualified = deduplicate(qualified)

    # CHANGE 2: Warn when engine team total diverges from market-implied (all picks, incl. failed)
    warn_tt_divergence(all_picks)

    # CHANGE 1 / FIX 5: Full GLC matrix — drop hard-conflict game-line pairs
    qualified_pre_glc = list(qualified)  # snapshot for thesis block
    qualified = filter_game_line_correlations(qualified)
    # Drop prop ↔ game-line anti-correlations (pitcher HA/ER under + opp TT over)
    qualified = filter_cross_type_correlations(qualified)

    # Game lines are produced solely by analyze_game_lines.py. evaluate_game_lines
    # still runs above so props are filtered against game-line correlations (GLC + X1),
    # but game-line PICKS are dropped from the live card here — never sized into the
    # premium card, logged to pick_log.csv, posted to Discord, or used as parlay legs.
    # Exception: shadow-only game-line stats (NRFI/YRFI ∈ SHADOW_STATS) stay in the pool
    # so they reach the SHADOW_STATS split below and keep accumulating to
    # pick_log_shadow_stats.csv (analyze_game_lines.py does not generate them).
    qualified = [p for p in qualified
                 if p.get("pick_type") != "game_line" or p.get("stat") in SHADOW_STATS]

    # CHANGE 3: Thesis block — show pre vs post GLC per game (multi-pick games only)
    print_thesis_block(qualified_pre_glc, qualified)

    print(f"\n  Qualified picks (pre-context): {len(qualified)}")
    print(f"  Failed gates: {len(failed)}")

    # ── Split shadow sports out BEFORE context layer (don't burn API calls on shadow picks) ──
    shadow_picks  = [p for p in qualified if p.get("sport") in SHADOW_SPORTS]
    # Rescue shadow-sport picks that failed only the sport-specific edge gate (e.g. G_WNBA_EDGE).
    # These passed all structural gates — the edge-floor is the only blocker, and it's intentionally
    # higher for shadow sports to compensate for wider vig / early-season uncertainty. We still want
    # them logged so the shadow sample builds toward the go-live gate.
    _SHADOW_SPORT_EDGE_GATES = {"G_WNBA_EDGE", "G_WNBA_OPEN"}
    shadow_picks += [p for p in failed
                     if p.get("sport") in SHADOW_SPORTS
                     and p.get("gate_result") in _SHADOW_SPORT_EDGE_GATES]
    qualified     = [p for p in qualified if p.get("sport") not in SHADOW_SPORTS]

    today_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

    print(f"\n  Qualified picks: {len(qualified)}")
    print(f"  Failed gates: {len(failed)}")

    # Gate failure diagnostic
    gate_counts = defaultdict(int)
    for p in failed:
        gate_counts[p.get("gate_result", "UNKNOWN")] += 1
    print(f"\n  Gate failure breakdown:")
    for gate, count in sorted(gate_counts.items(), key=lambda x: -x[1]):
        print(f"    {gate}: {count}")

    # Show top 15 picks killed by gates (best edges that got filtered)
    interesting_fails = sorted(
        [p for p in failed if p.get("adj_edge", 0) > 0.03],
        key=lambda p: p.get("adj_edge", 0), reverse=True
    )[:15]
    if interesting_fails:
        print(f"\n  Top filtered picks (edge > 3% but failed gates):")
        print(f"  {'Player':<25} {'Stat':<6} {'Line':>5} {'Dir':<6} {'WP':>6} {'Edge':>6} {'Odds':>6} {'Gate':<8} {'Game'}")
        print(f"  {'-'*125}")
        for p in interesting_fails:
            game_str = p.get("game", "")
            print(f"  {p['player']:<25} {p['stat']:<6} {p['line']:>5} {p['direction']:<6} {p['win_prob']*100:>5.1f}% {p['adj_edge']*100:>5.1f}% {p['odds']:>6} {p.get('gate_result','?'):<8} {game_str}")

    # Log shadow picks to their own CSVs (never touches main pick_log).
    # Must run BEFORE the early-return below so solo-WNBA runs still log
    # even when qualified is empty (WNBA is always stripped into shadow_picks).
    if shadow_picks:
        shadow_picks = size_picks_base(shadow_picks)
    if not args.no_save:
        for sport, path in SHADOW_LOG_PATHS.items():
            sport_shadow = [p for p in shadow_picks if p.get("sport") == sport]
            if sport_shadow:
                log_picks(sport_shadow, args.mode, log_path_override=Path(path))

    if not qualified:
        if shadow_picks:
            print("\n  [!] No live-sport qualifying picks (shadow picks logged separately).")
        else:
            print("\n  [!] No qualifying picks found. Check CSV data and odds availability.")
        return

    # Base sizing for qualifying picks (Full Card)
    qualified = size_picks_base(qualified) if qualified else []

    # Split shadow stat picks out BEFORE apply_caps so they don't consume cap budget
    # from live picks. They're logged to pick_log.csv for accuracy tracking but never
    # posted to Discord. Remove a stat from SHADOW_STATS at n>=30, WR>=55%.
    shadow_stat_picks = [p for p in qualified if p.get("stat") in SHADOW_STATS]
    qualified         = [p for p in qualified if p.get("stat") not in SHADOW_STATS]
    # Merge all shadow sources:
    #   shadow_stat_picks   — full-stat kills re-enabled (TB, HRR, NRFI, YRFI, new markets)
    #   _gate_shadow_picks  — direction/line-specific kills (G8B/C/D, K gates, TT over, etc.)
    #   _hard_rules_shadow  — R4/R11 kills (REB over, REB U≤2.5, AST U≤2.5)
    # shadow_stat_picks already sized (came through size_picks_base on qualified).
    # The others have size=0 and need sizing before logging.
    _unsized_shadow = _gate_shadow_picks + _hard_rules_shadow
    if _unsized_shadow:
        _unsized_shadow = size_picks_base(_unsized_shadow)
    all_shadow_picks = shadow_stat_picks + _unsized_shadow

    if all_shadow_picks:
        _shadow_stats_seen = ", ".join(sorted({p["stat"] for p in all_shadow_picks}))
        print(f"\n  [Shadow] {len(all_shadow_picks)} pick(s) logged to pick_log_shadow_stats.csv (not posted): {_shadow_stats_seen}")
        if not args.no_save:
            log_picks(all_shadow_picks, args.mode,
                      log_path_override=Path(str(_PICK_LOG_SHADOW_STATS_PATH_P)))

    # Candidate logging: write full pool (all gate-passing picks) to pick_log_candidates.csv
    # for formula backtesting. Runs after sizing so size is populated; before caps so pool is complete.
    if getattr(args, "log_candidates", False) and qualified:
        log_candidates(qualified, args.mode, today_str)

    # Build per-sport card guard key (enables separate MLB + NBA cards on same day)
    _sport_key = "+".join(sorted(sports))

    # Cross-run daily unit cap: read units already logged today so this run
    # can't exceed the 12u total cap even when a prior sport ran earlier.
    _units_today = _units_bet_today(today_str) if not getattr(args, "no_cap", False) else 0.0
    if _units_today > 0:
        print(f"\n  [CAP] Units already bet today: {_units_today:.2f}u — remaining 12u budget: {max(0, 12.0 - _units_today):.2f}u")

    # Apply caps.
    # A1 (audit 2026-05-06): --no-cap bypasses apply_caps entirely so
    # research mode can log all gate-passing picks for fast CLV
    # accumulation.  apply_caps would otherwise truncate the qualified
    # pool via STAT_CAP / max_per_game / SPORT_UNIT_CAP / 12u-total —
    # those caps are the right behavior for the live card but defeat the
    # docstring intent of --research --no-cap (~25-50/day vs 8-13).
    # Safety: --no-cap requires --no-discord (guard at line ~5190), so
    # this never affects live Discord flow.  The premium card at line
    # ~5529 still selects top-5 via apply_soft_rules_premium, so the
    # front-channel UX is unchanged regardless.
    if qualified and not getattr(args, "no_cap", False):
        qualified = apply_caps(qualified, {}, max_per_game=args.max_per_game, units_already_bet=_units_today)

    # ── KILLSHOT selection (runs BEFORE premium build) ───────────────────────
    # KILLSHOTs are excluded from the premium card — they get their own dedicated
    # embed in #killshot with @everyone. Premium card + POTD show the next best 5.
    manual_ks = {n.strip() for n in args.killshot.split(",") if n.strip()} if args.killshot else set()
    killshots  = select_killshots(qualified, today_str, manual_players=manual_ks)
    ks_keys    = {(p["player"], p["stat"], p["line"]) for p in killshots}

    # Build Premium 5 from non-KILLSHOT qualified picks only
    non_ks_qualified = [p for p in qualified if (p["player"], p["stat"], p["line"]) not in ks_keys]
    premium = apply_soft_rules_premium([], non_ks_qualified, max_per_game=args.max_per_game) if non_ks_qualified else []

    # Apply VAKE sizing to Premium 5 only (overwrites base sizing for these 5)
    premium = size_picks_vake(premium) if premium else []

    # H1 (audit 2026-05-09): Hard-enforce 12u daily cap across premium + KILLSHOT combined.
    # apply_caps() only saw the pre-KILLSHOT pool. KILLSHOT picks (3-4u each) are added
    # after, so we must check the combined total here and trim if needed.
    # Also includes _units_today for cross-run enforcement (e.g. MLB ran earlier today).
    _premium_u = sum(p.get("size", 0) for p in premium)
    _ks_total  = sum(p.get("size", 0) for p in killshots)
    if _premium_u + _ks_total + _units_today > 12.0:
        # Drop lowest-scoring KILLSHOT(s) until within cap
        killshots = sorted(killshots, key=lambda x: x.get("pick_score", 0), reverse=True)
        while killshots and _premium_u + sum(p.get("size", 0) for p in killshots) + _units_today > 12.0:
            dropped = killshots.pop()
            print(f"  [CAP] Dropping KILLSHOT {dropped['player']} ({dropped.get('size',0):.2f}u) — 12u daily cap")

    # 5.6: SPORT_UNIT_CAP re-check — apply_caps() ran before KILLSHOT sizing,
    # so KILLSHOT 3-4u picks can push a sport over its per-sport ceiling.
    _ks_sport_cap = {"NBA": 8.0, "WNBA": 4.0, "NHL": 5.0, "NFL": 5.0, "MLB": 8.0}
    _ks_sport_u: dict = defaultdict(float)
    for p in premium:
        _ks_sport_u[p.get("sport", "NBA")] += p.get("size", 0)
    _killshots_kept = []
    for p in killshots:
        sp = p.get("sport", "NBA")
        cap = _ks_sport_cap.get(sp, 8.0)
        if _ks_sport_u[sp] + p.get("size", 0) <= cap:
            _killshots_kept.append(p)
            _ks_sport_u[sp] += p.get("size", 0)
        else:
            print(f"  [CAP] Dropping KILLSHOT {p['player']} ({p.get('size',0):.2f}u) — {sp} sport cap ({cap:.1f}u)")
    killshots = _killshots_kept

    # Log premium picks + KILLSHOT picks on first run of the day.
    # KILLSHOT picks carry tier=KILLSHOT and no card_slot; premium picks get slots 1-5.
    # On subsequent runs (card already up), still log any new KILLSHOT picks that
    # weren't present in the earlier run — dedup in log_picks prevents duplicates.
    today_str_log = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    _card_was_already_up = _card_already_posted_today(today_str_log, sport_key=_sport_key)
    # A4 (audit 2026-05-06): the card guard suppresses log_picks for
    # the entire run when today's premium card has already shipped.
    # That's correct for live re-runs (avoids double-logging the
    # production ledger) but wrong for shadow/research runs that pass
    # --no-discord — those have no Discord post to deduplicate against
    # and were silently dropping every pick whenever SaberSim's live
    # run fired earlier in the day.  _card_guard_should_block_logging
    # bypasses the guard for --no-discord and --force-card.
    if _card_was_already_up and not _card_guard_should_block_logging(
        card_was_up=True,
        no_discord=args.no_discord,
        force_card=getattr(args, "force_card", False),
    ):
        if getattr(args, "force_card", False):
            print("  [Discord] --force-card: overriding card guard — will repost premium card with fresh picks.")
        else:
            print("  [--no-discord] Card guard bypassed: log-only run, no Discord risk.")
        _card_was_already_up = False
    if not args.no_save and not _card_was_already_up:
        if getattr(args, "no_cap", False):
            # --no-cap (shadow/research mode): log ALL qualified picks for CLV accumulation.
            # premium_picks= is still set so card_slot 1-5 columns are correct for the
            # actual top-5; extra picks log with blank card_slot (run_type=primary, no slot).
            # dedup key prevents double-logging if qualified overlaps premium.
            log_picks(qualified + killshots, args.mode, premium_picks=premium)
            print(f"  [--no-cap] Logged {len(qualified)} qualified picks (vs top-5 only in normal mode).")
        else:
            log_picks(premium + killshots, args.mode, premium_picks=premium)
    elif not args.no_save and killshots:
        # Card already posted but new KILLSHOTs may have emerged (e.g. updated CSVs).
        # Log them separately — dedup key (date+player+stat+line+direction) prevents
        # double-logging picks that were already recorded.
        log_picks(killshots, args.mode, premium_picks=[])

    safest5, safest6_parlay, value_parlay, alt_spread_parlay = _stage_build_parlays(
        qualified, premium, killshots, all_players, all_game_lines, all_team_proj, all_alt_spreads, args)

    # ET-aware date header (audit H-1).
    today = datetime.now(ZoneInfo("America/New_York")).strftime("%B %d, %Y")

    # === PARLAYS-ONLY MODE ===
    if args.parlays_only:
        pout = []
        pout.append(f"{'='*50}")
        pout.append(f"PARLAYS ONLY — {today}")
        pout.append(f"{'='*50}")
        pout.append("")

        # Longshot Parlay
        pout.append(f"{'='*50}")
        pout.append("LONGSHOT PARLAY — 6 Safest Picks by Win Probability")
        pout.append(f"{'='*50}")
        if safest6_parlay and safest6_parlay["legs"]:
            for i, leg in enumerate(safest6_parlay["legs"], 1):
                side = f"{fmt_dir(leg['direction'])} {leg['line']}" if "direction" in leg else leg.get("team", "?")
                pout.append(f"  {i}. {leg['player']} {side} ({leg['stat']}) — WP: {leg['win_prob']*100:.1f}%")
            pout.append(f"  ────────────────────────────────")
            pout.append(f"  Combined Probability: {safest6_parlay['combined_prob']*100:.2f}%")
            pout.append(f"  Fair Odds: {fmt_odds(safest6_parlay['parlay_odds'])}")
        else:
            pout.append("  Not enough qualifying picks for 6-leg parlay.")
        pout.append("")

        # Alt Spread Parlay
        _dlay_n2 = alt_spread_parlay.get("num_legs", "?") if alt_spread_parlay else "?"
        _dlay_bk2 = alt_spread_parlay.get("book", "") if alt_spread_parlay else ""
        _dlay_hdr2 = f"ALT SPREAD PARLAY — {_dlay_n2}-Leg ({_dlay_bk2})" if _dlay_bk2 else f"ALT SPREAD PARLAY — {_dlay_n2}-Leg"
        pout.append(f"{'='*50}")
        pout.append(_dlay_hdr2)
        pout.append(f"{'='*50}")
        if alt_spread_parlay and alt_spread_parlay["legs"]:
            pout.append(f"  Book: {alt_spread_parlay.get('book', 'N/A')}")
            pout.append("")
            for i, leg in enumerate(alt_spread_parlay["legs"], 1):
                sign = "+" if leg["alt_spread"] > 0 else ""
                odds_str = fmt_odds(leg["real_odds"]) if leg.get("real_odds") else "N/A"
                pout.append(f"  {i}. {leg['team']} {sign}{leg['alt_spread']:.1f} ({odds_str})")
                pout.append(f"     {leg['game']} | Margin: {leg['margin']:+.1f} | Cover: {leg['alt_cover_prob']*100:.1f}%")
            pout.append(f"  ────────────────────────────────")
            pout.append(f"  Parlay Odds: {fmt_odds(alt_spread_parlay['parlay_odds'])}")
            pout.append(f"  Model Cover Prob: {alt_spread_parlay['combined_prob']*100:.1f}%")
        else:
            pout.append("  Not enough qualifying NBA game lines for 3-leg parlay.")

        parlay_output = "\n".join(pout)
        print("\n" + parlay_output)
        print("\n  Done. Let's eat.\n")
        return

    # Format full output
    output = format_output(premium, safest5, qualified, all_picks, args.mode, today,
                           safest6_parlay=safest6_parlay, alt_spread_parlay=alt_spread_parlay,
                           max_per_game=args.max_per_game, killshots=killshots,
                           units_already_bet=_units_today)

    # Print
    print("\n" + "=" * 60)
    print(output)
    print("=" * 60)

    # Save
    if not args.no_save:
        folder = Path(OUTPUT_FOLDER)
        folder.mkdir(parents=True, exist_ok=True)
        # ET date for output filename (matches today_str + pick_log; audit H-1).
        out_path = args.output or str(folder / f"picks_{datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d')}.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"\n  Saved: {out_path}")

    # Post to Discord
    suppress_ping = args.test  # --test suppresses @everyone on all posts

    # ── Manual pick logging mode ──────────────────────────────────────────────────
    if args.log_manual:
        print("\n  Log a manually posted pick to pick_log.csv")
        print("  (Use this for picks you posted in Discord without running the model)\n")
        today_manual = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
        run_time_manual = datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M")
        player   = input("  Player name: ").strip()
        sport    = input("  Sport (NBA/NHL/MLB/NFL): ").strip().upper()
        team     = input("  Team abbreviation: ").strip().upper()
        stat     = input("  Stat (PTS/REB/AST/SOG/3PM etc): ").strip().upper()
        line     = input("  Line (e.g. 24.5): ").strip()
        direction = input("  Direction (over/under): ").strip().lower()
        odds     = input("  Odds (e.g. -115 or +105): ").strip()
        book     = _norm_book(input("  Book (e.g. draftkings): ").strip().lower())
        # Size must parse to float — downstream grade_picks/recap math calls float(size).
        while True:
            size_raw = input("  Size in units (e.g. 1.25): ").strip()
            try:
                size_f = float(size_raw)
                if size_f <= 0:
                    print("    ❌ Size must be > 0. Try again.")
                    continue
                size = f"{size_f:g}"
                break
            except ValueError:
                print(f"    ❌ '{size_raw}' is not a valid number. Try again.")
        game     = input("  Game (e.g. 'Boston Celtics @ Miami Heat'): ").strip()
        tier     = input("  Tier (T1/T1B/T2/T3/KILLSHOT or leave blank): ").strip().upper() or "MANUAL"
        # run_type is always "manual" for manual picks — stat already identifies game-line vs prop.
        # (Note: "gameline" is not a valid schema run_type; removed M4 2026-05-27)
        manual_run_type = "manual"

        # is_home prompt — required for SPREAD/ML/F5/TEAM_TOTAL so grade_picks resolves the right side.
        _home_stats = {"SPREAD", "ML_FAV", "ML_DOG", "TEAM_TOTAL",
                       "F5_SPREAD", "F5_ML", "F5_TOTAL", "NRFI", "YRFI"}
        is_home_val = ""
        if stat in _home_stats:
            ih = input("  Is picked side HOME? (y/n): ").strip().lower()
            if ih.startswith("y"):
                is_home_val = "True"
            elif ih.startswith("n"):
                is_home_val = "False"
            # anything else → blank, _resolve_pick_is_home fallback handles it
        # Normalize odds to canonical sign-prefixed form at write time
        # (PICK_LOG_AUDIT H-3). Blank -> blank (validator below will catch
        # it as a missing required field).
        odds_norm = _normalize_odds(odds)

        # Pre-flight row so we can run the required-field validator BEFORE
        # acquiring the lock / opening the file. Rejecting here means we
        # never persist a half-typed manual pick (PICK_LOG_AUDIT H-4).
        manual_row = {
            "date": today_manual,
            "sport": sport,
            "stat": stat,
            "line": line,
            "direction": direction,
            "odds": odds_norm,
            "book": book,
            "size": size,
        }
        try:
            _assert_manual_row_valid(manual_row)
        except Exception as e:
            print(f"\n  ❌ Manual pick rejected: {e}")
            print("  Nothing was written. Try again with every field filled.")
            return

        # Manual picks go to their own log — keeps model-generated pick_log.csv clean.
        log_path = Path(PICK_LOG_MANUAL_PATH)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not log_path.exists() or log_path.stat().st_size == 0
        # Shared FileLock for the manual log too, so the grader/analyzer can't
        # read mid-append and see a partial row (audit H-5 / H-8).
        with _pick_log_lock(log_path):
            with open(log_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow(CANONICAL_HEADER)
                writer.writerow([
                    today_manual, run_time_manual, manual_run_type, sport, player, team, stat, line,
                    direction, "", "", "", odds_norm, book,
                    # M-10: canonical 2-decimal size for manual rows too.
                    # M-3: canonical is_home (handles "1"/"true"/etc).
                    tier, "", _normalize_size(size), game, "Default", "", "", "", "",
                    _normalize_is_home(is_home_val, stat),
                    "", "", "",  # context_verdict, context_reason, context_score
                    "", "",     # legs, over_p_raw (col 28-29 — must match 29-col CANONICAL_HEADER)
                ])
                # Commit to disk before releasing the outer lock (audit H-5).
                f.flush()
                os.fsync(f.fileno())
        # M-13: refresh the manual log's sidecar — manual and main logs
        # share the 27-column schema but each gets its own versioned sidecar.
        try:
            _write_schema_sidecar(log_path)
        except Exception as _sidecar_err:
            logger.warning(f"M-13 sidecar write failed for {log_path}: {_sidecar_err}")
        print(f"\n  ✅ Logged: {player} {direction.upper()} {line} {stat} ({sport}) to pick_log_manual.csv")
        print("\n  Done. Let's eat.\n")
        return

    # ── Repost mode: re-fire premium card + POTD from the most recent log entry ──
    if args.repost:
        log_path = Path(PICK_LOG_PATH)
        if log_path.exists():
            # Shared reader lock — don't race a mid-flush CLV/grader write (audit H-8).
            with _pick_log_lock(log_path):
                with open(log_path, "r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    repost_rows = [r for r in reader
                                   if r.get("run_type", "") in {"primary", "", None}
                                   and r.get("tier", "") != "KILLSHOT"
                                   and r.get("date", "") == today_str]
            if repost_rows:
                # Sort by card_slot (original card order) so POTD is always slot 1
                repost_rows.sort(key=lambda r: int(r.get("card_slot") or 99))
                # Reconstruct minimal pick dicts from log
                repost_picks = []
                for r in repost_rows[:5]:  # top 5 primary picks
                    repost_picks.append({
                        "player": r.get("player", ""), "team_abbrev": r.get("team", ""),
                        "stat": r.get("stat", ""), "line": float(r.get("line", 0)),
                        "direction": r.get("direction", ""),
                        "proj": float(r.get("proj", 0)), "win_prob": float(r.get("win_prob", 0)),
                        "adj_edge": float(r.get("edge", 0)), "raw_edge": float(r.get("edge", 0)),
                        "conf": 1.0, "odds": int(float(r.get("odds", -110))),
                        "book": r.get("book", ""), "game": r.get("game", ""),
                        "sport": r.get("sport", ""), "tier": r.get("tier", ""),
                        "size": float(r.get("size", 0)),
                        "pick_score":      float(r.get("pick_score", 0)),
                        "pick_type":       "prop",
                        "context_verdict": r.get("context_verdict", ""),
                        "context_reason":  r.get("context_reason", ""),
                        "context_score":   int(float(r.get("context_score", 0) or 0)),
                    })
                if repost_picks:
                    print(f"\n  [Discord] --repost: re-firing premium card + POTD for {today_str}\u2026")
                    _repost_sports = sorted(set(p.get("sport", "") for p in repost_picks if p.get("sport")))
                    _repost_sport_key = "+".join(_repost_sports) if _repost_sports else "MULTI"
                    post_to_discord(repost_picks, args.mode, today_str, suppress_ping=suppress_ping, force=True, sport=_repost_sport_key)
                else:
                    print(f"\n  [Discord] --repost: no primary picks found for {today_str}")
            else:
                print(f"\n  [Discord] --repost: no picks logged for {today_str} yet")
        else:
            print("\n  [Discord] --repost: pick_log.csv not found")
        print("\n  Done. Let's eat.\n")
        return

    _stage_post_discord(args, premium, qualified, killshots, safest6_parlay, value_parlay,
                        alt_spread_parlay, today, today_str, suppress_ping, _sport_key, _card_was_already_up)

    # -- SGP builder (runs regardless of --no-discord) ----------------
    # NBA only, playoff fun bet. Prints to console always; posts to
    # Discord only when --no-discord and --dry-run are both off.
    # Not tracked in pick_log.
    if not getattr(args, 'no_sgp', False):
        try:
            from sgp_builder import run_sgp_builder
            _sgp_csv_strs = [str(p) for p in csv_paths_resolved]
            # --sgp-only forces a live post even if --no-discord was set
            _sgp_only = getattr(args, 'sgp_only', False)
            _sgp_dry  = (args.dry_run or args.no_discord) and not _sgp_only
            _sgp_save = not args.no_save
            print("\n  [SGP] Running SGP builder...")
            run_sgp_builder(
                _sgp_csv_strs,
                dry_run=_sgp_dry,
                confirm=get_confirm_mode(),
                test=getattr(args, 'test', False),
                save=_sgp_save,
            )
        except Exception as e:
            print(f'  [SGP] Error: {e} — skipping.')

    # MLB SGP — runs whenever an MLB CSV is present
    if not getattr(args, 'no_sgp', False):
        try:
            from mlb_sgp_builder import run_mlb_sgp_builder
            _mlb_csv_strs = [str(p) for p in csv_paths_resolved]
            _mlb_sgp_dry  = (args.dry_run or args.no_discord) and not getattr(args, 'sgp_only', False)
            print("\n  [MLB SGP] Running MLB SGP builder...")
            run_mlb_sgp_builder(
                _mlb_csv_strs,
                dry_run=_mlb_sgp_dry,
                confirm=get_confirm_mode(),
                test=getattr(args, 'test', False),
                save=not args.no_save,
                debug=getattr(args, 'sgp_debug', False),
            )
        except Exception as e:
            print(f'  [MLB SGP] Error: {e} — skipping.')

    print("\n  Done. Let's eat.\n")


if __name__ == "__main__":
    main()
