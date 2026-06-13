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

# ── Context research verdicts (display-only; written by engine/context_research.py) ─
_CTX_VERDICTS: dict = {}
_ctx_path = Path(__file__).parent.parent / "data" / "context_verdicts.json"
if _ctx_path.exists():
    try:
        for _v in json.loads(_ctx_path.read_text(encoding="utf-8")):
            _CTX_VERDICTS[_v["game"]] = _v
    except Exception:
        pass

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

def _longshot_pos_corr_pair(a, b):
    """True iff (a, b) is the positively-correlated pair: pitcher OUTS under +
    opposing team's TEAM_TOTAL over in the same game (Plan 9 §9B, ρ ≈ +0.30-0.40 —
    pitcher exits early → opposing offense scoring; mirror of the X1 negative pair).
    Opposing-team check mirrors filter_cross_type_correlations (team_abbrev fields).
    """
    g = a.get("game", "")
    if not g or g != b.get("game", ""):
        return False
    for outs_pick, tt_pick in ((a, b), (b, a)):
        if (outs_pick.get("stat") == "OUTS" and outs_pick.get("direction") == "under"
                and tt_pick.get("stat") == "TEAM_TOTAL" and tt_pick.get("direction") == "over"):
            t_outs = outs_pick.get("team_abbrev", "")
            t_tt = tt_pick.get("team_abbrev", "")
            if t_outs and t_tt and t_outs != t_tt:
                return True
    return False


def _longshot_effective_wp(p, selected):
    """Effective win prob of candidate p for longshot RANKING, conditional on
    already-selected legs (Plan 9 §9B). If p forms a positively-correlated pair
    with a selected leg q, independence understates the joint prob — rank p by
    P(p | q) = joint / P(q), where (Bernoulli-φ identity):

        joint = p·q + ρ·sqrt(p(1−p)·q(1−q))

    Equals the raw win_prob when no boosted pair exists. Ranking-only: the
    displayed/logged combined_prob stays the independence product (conservative
    for the boosted pair).
    """
    wp = p["win_prob"]
    best = wp
    for q_pick in selected:
        if _longshot_pos_corr_pair(p, q_pick):
            q = q_pick["win_prob"]
            if q <= 0.0:
                continue
            joint = wp * q + LONGSHOT_PAIR_RHO * math.sqrt(
                max(0.0, wp * (1.0 - wp) * q * (1.0 - q)))
            best = max(best, min(0.99, joint / q))
    return best


def build_safest6_parlay(qualified):
    """Build a longshot parlay from the 6 safest picks by win probability.

    This is a HIT-FREQUENCY PRODUCT (Plan 9 §9G decision, 2026-06-06):
    selecting by win_prob maximizes how often the card has at least one
    parlay winner (engagement/subscriber value — a hit every ~2-3 weeks at
    daily cadence), not EV. An EV-factor ranking (1 + edge/implied) would be
    theoretically superior (~+77% vs ~+19% slip EV in the worked example) but
    is a product direction change requiring subscriber expectation management.
    Current design is intentional and documented as hit-frequency.

    Per-game cap of 2: prevents same-game correlation from dominating the
    combined probability estimate (which assumes independence across legs).
    If the top 6 by WP would pull 3+ from one game, the 3rd+ are skipped
    and replaced by the next-best picks from other games.

    Independence assumption is valid for cross-game legs: positive cross-game
    correlation (shared pace/scoring environment) would make true joint prob
    >= naive product, so independence is conservative, not aggressive.
    """
    # Hit-frequency product: rank by win_prob, not EV-factor.
    # Plan 9 §9B: iterative greedy — each round selects the pool max by
    # EFFECTIVE wp (conditional on already-selected positively-correlated
    # partners via _longshot_effective_wp). With no boosted pairs this is
    # sequence-identical to the old single-pass wp-desc sort (max() resolves
    # ties to the lowest index in the wp-desc pool).
    pool = sorted(qualified, key=lambda p: p["win_prob"], reverse=True)
    game_counts: dict = {}
    player_counts: dict = {}
    safest = []
    while pool and len(safest) < 6:
        p = max(pool, key=lambda c: _longshot_effective_wp(c, safest))
        pool.remove(p)
        g = p.get("game", "")
        player = p.get("player", "")
        if game_counts.get(g, 0) >= LONGSHOT_MAX_PER_GAME:
            continue
        # Max 1 leg per player — same player's stats are correlated, not independent
        if player and player_counts.get(player, 0) >= 1:
            continue
        game_counts[g] = game_counts.get(g, 0) + 1
        if player:
            player_counts[player] = player_counts.get(player, 0) + 1
        safest.append(p)
    if len(safest) < 6:
        return None
    # Displayed/logged combined_prob stays the independence product — conservative
    # for a boosted pair (true joint prob >= product under positive ρ).
    combined_prob = 1.0
    combined_dec  = 1.0
    book_counts: dict = {}
    for p in safest:
        combined_prob *= p["win_prob"]
        o = p.get("odds", -110)
        if o > 0:
            combined_dec *= 1.0 + o / 100.0
        else:
            combined_dec *= 1.0 + 100.0 / abs(o)
        bk = _norm_book(p.get("book", ""))
        if bk:
            book_counts[bk] = book_counts.get(bk, 0) + 1
    # Actual payout from book leg prices (not model fair value)
    if combined_dec >= 2.0:
        parlay_odds = int(round((combined_dec - 1.0) * 100.0))
    else:
        parlay_odds = int(round(-100.0 / (combined_dec - 1.0)))
    # Modal book across legs — best guess for where to parlay
    best_book = max(book_counts, key=book_counts.get) if book_counts else ""
    return {"legs": safest, "combined_prob": combined_prob, "parlay_odds": parlay_odds, "book": best_book}


def build_value_parlay(qualified):
    """5-leg fallback parlay — fires only when 6-leg longshot cannot be built.
    Same per-game (LONGSHOT_MAX_PER_GAME) and per-player (1) caps as longshot.
    Returns None if fewer than 5 legs pass all caps.

    Plan 10 §S: per-leg +EV admissibility gate (adj_edge > 0). Compounding ~14% vig on
    individually −EV legs is presumptively −EV, so we return None rather than ship a parlay
    built from non-positive-edge legs.
    """
    ranked = sorted(qualified, key=lambda p: p["win_prob"], reverse=True)
    game_counts: dict = {}
    player_counts: dict = {}
    safest = []
    for p in ranked:
        g = p.get("game", "")
        player = p.get("player", "")
        if p.get("adj_edge", 0) <= 0:
            continue  # Plan 10 §S: exclude non-positive-edge legs
        if game_counts.get(g, 0) >= LONGSHOT_MAX_PER_GAME:
            continue
        if player and player_counts.get(player, 0) >= 1:
            continue
        game_counts[g] = game_counts.get(g, 0) + 1
        if player:
            player_counts[player] = player_counts.get(player, 0) + 1
        safest.append(p)
        if len(safest) == 5:
            break
    if len(safest) < 5:
        return None
    combined_prob = 1.0
    combined_dec  = 1.0
    book_counts: dict = {}
    for p in safest:
        combined_prob *= p["win_prob"]
        o = p.get("odds", -110)
        if o > 0:
            combined_dec *= 1.0 + o / 100.0
        else:
            combined_dec *= 1.0 + 100.0 / abs(o)
        bk = _norm_book(p.get("book", ""))
        if bk:
            book_counts[bk] = book_counts.get(bk, 0) + 1
    if combined_dec >= 2.0:
        parlay_odds = int(round((combined_dec - 1.0) * 100.0))
    else:
        parlay_odds = int(round(-100.0 / (combined_dec - 1.0)))
    best_book = max(book_counts, key=book_counts.get) if book_counts else ""
    return {"legs": safest, "combined_prob": combined_prob, "parlay_odds": parlay_odds, "book": best_book}


def build_alt_spread_parlay(game_lines, team_proj_map, sport_sigmas, alt_spread_data=None, debug=False):
    """
    Build alt spread parlay (NBA ONLY).
    Selects legs by edge (model cover prob vs implied prob from odds).
    Tries 3 legs → 2 → 1 per book, one leg per game.
    Only posts if combined parlay odds >= -130.
    """
    if alt_spread_data is None:
        alt_spread_data = []

    def dbg(msg):
        if debug:
            print(f"  [daily-lay-debug] {msg}")

    MIN_COMBINED_ODDS_VAL = -130  # combined parlay must be -130 or longer
    MAX_COMBINED_ODDS_VAL = 100   # combined parlay must not exceed +100

    def american_to_decimal(odds):
        if odds > 0:
            return 1.0 + odds / 100.0
        return 1.0 + 100.0 / abs(odds)

    def decimal_to_american(dec):
        if dec >= 2.0:
            return (dec - 1.0) * 100.0
        return -100.0 / (dec - 1.0)

    # Step 1: Build per-team projection info from NBA game lines
    team_game_info = {}
    nba_games = []
    for gl in game_lines:
        if gl.get("sport", "").upper() != "NBA":
            continue
        home = gl["home"]
        away = gl["away"]
        sigma = sport_sigmas.get("NBA", {}).get("spread", 12.0)
        sport_prefix = "NBA_"

        home_proj = away_proj = None
        for full_name, abbr in TEAM_ABBREV.items():
            sport_key = sport_prefix + abbr
            if full_name in home.lower() and sport_key in team_proj_map:
                hp = team_proj_map[sport_key].get("saber_team", 0)
                if hp > 0:
                    home_proj = hp
            if full_name in away.lower() and sport_key in team_proj_map:
                ap = team_proj_map[sport_key].get("saber_team", 0)
                if ap > 0:
                    away_proj = ap

        spread_data = gl.get("spread", {})
        home_std = spread_data.get(home, {}).get("line")
        away_std = spread_data.get(away, {}).get("line")

        if home_proj is not None and away_proj is not None:
            margin = home_proj - away_proj
            dbg(f"GAME {gl['game']}: home={home_proj:.1f} away={away_proj:.1f} margin={margin:+.1f}")
            team_game_info[home] = {"margin": margin,  "sigma": sigma, "game": gl["game"], "sport": "NBA", "std_spread": home_std}
            team_game_info[away] = {"margin": -margin, "sigma": sigma, "game": gl["game"], "sport": "NBA", "std_spread": away_std}
        else:
            dbg(f"SKIP proj {gl['game']}: home_proj={home_proj} away_proj={away_proj}")
            team_game_info[home] = {"margin": None, "sigma": sigma, "game": gl["game"], "sport": "NBA", "std_spread": home_std}
            team_game_info[away] = {"margin": None, "sigma": sigma, "game": gl["game"], "sport": "NBA", "std_spread": away_std}

        nba_games.append(gl["game"])

    if not nba_games:
        dbg("No NBA games found")
        return None

    # Step 2: Score every alt spread entry by edge + quality filters
    scored = []
    for entry in alt_spread_data:
        team = entry["team"]
        if team not in team_game_info:
            continue
        info = team_game_info[team]
        if info["margin"] is None:
            continue

        odds = entry["odds"]
        line = entry["line"]
        margin = info["margin"]
        sigma = info["sigma"]

        implied = abs(odds) / (abs(odds) + 100.0) if odds < 0 else 100.0 / (odds + 100.0)
        cover_prob = 1.0 - normal_cdf(-line, margin, sigma)
        # Raw vigged implied (not no-vig) — alt-spread lines are one-sided, making no-vig
        # impossible. Conservative: vigged implied is harder to beat at 0.025 threshold.
        edge = cover_prob - implied

        # Per-leg quality gates: screen out noise before composite scoring
        if edge < MIN_LEG_EDGE_DAILY:
            dbg(f"  {team} {line:+.1f} @ {odds}: SKIP edge {edge:.3f} < {MIN_LEG_EDGE_DAILY}")
            continue
        if cover_prob < MIN_LEG_COVER_PROB_DAILY:
            dbg(f"  {team} {line:+.1f} @ {odds}: SKIP cover_prob {cover_prob:.3f} < {MIN_LEG_COVER_PROB_DAILY}")
            continue

        # Composite leg score: edge weighted 60%, excess cover prob weighted 40%.
        # The 0.58 floor clips the baseline — only rewarding probability meaningfully
        # above the minimum, not raw implied probability (which penalises tight lines).
        # Odds quality bonus: legs in -145 to -100 range get a 5% boost (market is
        # less certain = better value signal than -200+ juice).
        prob_excess = max(0.0, cover_prob - MIN_LEG_COVER_PROB_DAILY)
        odds_quality = 1.05 if -145 <= odds <= -100 else 1.00
        leg_score = (edge * 0.60 + prob_excess * 0.40) * odds_quality

        dbg(f"  {team} {line:+.1f} @ {odds} [{entry['book']}]: cover={cover_prob:.3f} implied={implied:.3f} edge={edge:+.3f} leg_score={leg_score:.4f}")

        scored.append({
            "team": team,
            "game": info["game"],
            "sport": info["sport"],
            "std_spread": info["std_spread"],
            "margin": margin,
            "sigma": sigma,
            "line": line,
            "odds": odds,
            "book": entry["book"],
            "cover_prob": cover_prob,
            "edge": edge,
            "leg_score": leg_score,
        })

    if not scored:
        dbg("No scored entries — no alt spread data passed per-leg quality gates")
        return None

    # Step 3: Per book, pick best leg-score line per game, then try 3→2 legs (min 2)
    book_game_best = defaultdict(dict)
    for s in scored:
        bk, gm = s["book"], s["game"]
        if gm not in book_game_best[bk] or s["leg_score"] > book_game_best[bk][gm]["leg_score"]:
            book_game_best[bk][gm] = s

    best_result = None
    best_score = float("-inf")

    for book, game_bests in book_game_best.items():
        # Sort by composite leg_score (edge × 0.60 + prob_excess × 0.40 × odds_quality)
        entries = sorted(game_bests.values(), key=lambda x: x["leg_score"], reverse=True)
        dbg(f"Book {book}: {len(entries)} game(s)")
        for e in entries:
            dbg(f"  {e['game']} → {e['team']} {e['line']:+.1f} @ {e['odds']} edge={e['edge']:+.3f} leg_score={e['leg_score']:.4f}")

        # Min 2 legs — a single alt spread leg is a straight bet, not a parlay product
        for num_legs in [3, 2]:
            if len(entries) < num_legs:
                continue
            leg_entries = entries[:num_legs]
            combined_dec = 1.0
            for e in leg_entries:
                combined_dec *= american_to_decimal(e["odds"])
            parlay_odds = decimal_to_american(combined_dec)

            dbg(f"  {book} {num_legs}-leg combined: {parlay_odds:.0f}")

            if parlay_odds < MIN_COMBINED_ODDS_VAL:
                dbg(f"  {book} {num_legs}-leg: {parlay_odds:.0f} < {MIN_COMBINED_ODDS_VAL} — too juicy, skip")
                continue
            if parlay_odds > MAX_COMBINED_ODDS_VAL:
                dbg(f"  {book} {num_legs}-leg: {parlay_odds:.0f} > {MAX_COMBINED_ODDS_VAL} — too long, skip")
                continue

            total_leg_score = sum(e["leg_score"] for e in leg_entries)
            if total_leg_score > best_score:
                best_score = total_leg_score
                best_result = (book, leg_entries, parlay_odds, num_legs)
            break  # found valid leg count for this book

    if not best_result:
        dbg("No valid parlay found — all books either too juicy, no edge, or under 2 legs")
        return None

    best_book, best_entries, best_parlay_odds, num_legs = best_result

    legs = []
    for e in best_entries:
        bought_pts = (e["line"] - e["std_spread"]) if e["std_spread"] is not None else 0.0
        legs.append({
            "team": e["team"],
            "team_abbrev": get_team_abbrev(e["game"], ""),
            "game": e["game"],
            "margin": e["margin"],
            "std_spread": e["std_spread"],
            "alt_spread": e["line"],
            "bought_pts": bought_pts,
            "alt_cover_prob": e["cover_prob"],
            "real_odds": e["odds"],
            "real_book": display_book(best_book),
            "book_key": best_book,
            "sport": e["sport"],
            "decimal_odds": american_to_decimal(e["odds"]),
        })

    combined_prob = 1.0
    for leg in legs:
        combined_prob *= leg["alt_cover_prob"]

    return {
        "legs": legs,
        "num_legs": num_legs,
        "combined_prob": combined_prob,
        "parlay_odds": best_parlay_odds,
        "book": display_book(best_book),
        "has_real_odds": True,
    }


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


_DISCORD_GUARD_TTL_DAYS = 90


try:
    from discord_guard import (
        load_guard as _shared_load_guard,
        save_guard as _shared_save_guard,
        prune_guard as _shared_prune_guard,
        claim_post as _shared_claim_post,
        release_post as _shared_release_post,
        mark_posted as _shared_mark_posted,
    )
    _HAS_SHARED_GUARD = True
except ImportError:
    _HAS_SHARED_GUARD = False


def _prune_discord_guard(guard):
    """Drop guard keys older than _DISCORD_GUARD_TTL_DAYS (based on embedded YYYY-MM-DD token)."""
    from datetime import datetime, timedelta
    # Pin cutoff to ET (pick-log date convention). Strip tzinfo so the compare
    # against naive strptime dates stays valid (audit H-1).
    cutoff = datetime.now(ZoneInfo("America/New_York")).replace(tzinfo=None) - timedelta(days=_DISCORD_GUARD_TTL_DAYS)
    pruned = {}
    for key, val in guard.items():
        keep = True
        for p in key.split(":"):
            if len(p) == 10 and p[4] == "-" and p[7] == "-":
                try:
                    dt = datetime.strptime(p, "%Y-%m-%d")
                    if dt < cutoff:
                        keep = False
                    break
                except ValueError:
                    continue
        if keep:
            pruned[key] = val
    return pruned


def _load_discord_guard():
    """Load the Discord post de-dup registry from disk. Returns {} on miss."""
    # Delegate to shared cross-process-safe helper if available
    if _HAS_SHARED_GUARD:
        return _shared_load_guard()
    try:
        with open(DISCORD_GUARD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_discord_guard(guard):
    """Persist the Discord post de-dup registry atomically with TTL pruning."""
    # Delegate to shared cross-process-safe helper if available
    if _HAS_SHARED_GUARD:
        _shared_save_guard(guard)
        return
    try:
        atomic_write_json(DISCORD_GUARD_FILE, _prune_discord_guard(guard))
    except Exception as e:
        logger.warning(f"[Discord] Guard write failed: {e}")
        # Best-effort fallback — prune stale entries before writing
        try:
            guard = _prune_discord_guard(guard)
            with open(DISCORD_GUARD_FILE, "w", encoding="utf-8") as f:
                json.dump(guard, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            pass


def _discord_already_posted(key):
    """Return True if this guard key has already been posted (read-only check).
    Use _discord_claim_post for the atomic test-and-set before posting.
    """
    return bool(_load_discord_guard().get(key))


def _discord_mark_posted(key):
    """Record a successful Discord post (legacy RMW wrapper).
    Prefer _discord_claim_post for new call sites.
    """
    if _HAS_SHARED_GUARD:
        _shared_mark_posted(key)
        return
    g = _load_discord_guard()
    g[key] = True
    _save_discord_guard(g)


def _discord_claim_post(key):
    """Atomic test-and-set: claim a guard key before posting.
    Returns True if THIS run just claimed key (caller should post).
    Returns False if already claimed (caller should skip).
    Fixes audit C3 (TOCTOU) + H3 (suppress_ping guard omission).
    """
    if _HAS_SHARED_GUARD:
        return _shared_claim_post(key)
    # Fallback: best-effort non-atomic claim (no discord_guard module)
    if _load_discord_guard().get(key):
        return False
    _discord_mark_posted(key)
    return True


def _discord_release_post(key):
    """Un-claim a guard key after a failed webhook post so the next run
    can retry. No-op if the key is not set. Do NOT call after success.
    """
    if _HAS_SHARED_GUARD:
        _shared_release_post(key)
        return
    g = _load_discord_guard()
    if key in g:
        del g[key]
        _save_discord_guard(g)


def _notify_post_failure(label, guard_key=None, err=None):
    """Release the guard claim (if any) and fire the fallback webhook alert.
    Swallows all errors — a broken notifier must never mask the real failure.
    Fixes audit H5 / F6.4 / F6.7.
    """
    if guard_key:
        _discord_release_post(guard_key)
    try:
        from webhook_fallback import notify_fallback
        notify_fallback(label, err=err)
    except Exception as _e:
        logger.warning(f"[fallback-notifier] raised (suppressed): {_e}")


def _webhook_post(url, payload, retries=3, backoff=2.0, label="Discord post"):
    """POST a JSON payload to a Discord webhook URL. Retries on failure with exponential backoff.
    If _CONFIRM_MODE is True, prompts for y/n confirmation before sending.

    Audit M-4 / M-16 (closed Apr 20 2026): retry_after parsed via
    http_utils.retry_after_secs so a non-JSON / empty 429 body can't
    crash the poster, and the Retry-After header is preferred over the
    (Discord-specific) JSON body. Canonical UA from default_headers()
    stamps every outbound webhook post.
    """
    if not url:
        logger.warning("[Discord] Webhook URL not configured — skipping post.")
        return False
    if not _confirm_post(label):
        print(f"  [Confirm] ⏭️  Skipped: {label}")
        return False
    import requests as _req
    from http_utils import default_headers as _dh, retry_after_secs as _ras
    headers = _dh()
    for attempt in range(1, retries + 1):
        try:
            # H5/H22: split timeout (connect=5s, read=10s); ReadTimeout is NOT
            # retried because the POST body has already been sent — a retry risks
            # a duplicate Discord post.
            r = _req.post(url, json=payload, headers=headers, timeout=(5, 10))
            if r.status_code == 429:
                retry_after = _ras(r, default=backoff)
                logger.warning(f"[Discord] Rate limited — waiting {retry_after:.1f}s (attempt {attempt}/{retries})")
                time.sleep(retry_after)
                continue
            r.raise_for_status()
            return True
        except _req.exceptions.ReadTimeout as e:
            # H5: never retry ReadTimeout — POST body was already delivered.
            logger.error(f"[Discord] ReadTimeout (body already sent, NOT retrying): {e}")
            return False
        except Exception as e:
            if attempt < retries:
                wait = backoff ** attempt
                logger.warning(f"[Discord] Post failed (attempt {attempt}/{retries}): {e} — retrying in {wait:.1f}s")
                time.sleep(wait)
            else:
                logger.error(f"[Discord] Post failed after {retries} attempts: {e}")
    return False


def build_premium_embed(premium, mode, today, suppress_ping=False, sport=None):
    """Build the Discord embed payload for the premium card (#premium-portfolio)."""
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    mode_emoji = {"Default": "⚖️", "Aggressive": "🔥", "Conservative": "🛡️"}
    picks = premium[:5]
    total_u = sum(p.get("size", 0) for p in picks)

    now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%I:%M %p ET")
    mode_str = f"{mode_emoji.get(mode, '⚖️')} {mode}"
    sport_label = f" · {sport}" if sport else ""

    lines = [f"**{len(picks)} picks | {total_u:.2f}u | {mode_str}**\n"]
    for i, p in enumerate(picks):
        e = emojis[i] if i < len(emojis) else "•"
        stat = p.get("stat", "")
        direction = p["direction"].upper()
        line_val = p["line"]
        odds_str = fmt_odds(p["odds"])
        book_str = display_book(p["book"])
        size = p.get("size", 0)
        game = p.get("game", "")
        edge_str = f"+{p['adj_edge']*100:.1f}%"
        score_str = f"{p.get('pick_score', 0):.1f}"
        tier = p.get("tier", "")

        # Game-line stats use full player field; props use last name only
        _SUFFIXES = {"jr.", "sr.", "ii", "iii", "iv"}
        if stat == "TEAM_TOTAL":
            pick_label = f"{p['player']} {direction} {line_val}"
        elif stat in ("ML_FAV", "ML_DOG"):
            pick_label = p["player"]  # already "TEAM ML", e.g. "MON ML"
        elif stat in ("SPREAD", "TOTAL", "F5_TOTAL", "F5_SPREAD", "F5_ML"):
            pick_label = f"{p['player']} {direction} {line_val}"
        elif stat in ("NRFI", "YRFI"):
            matchup = p.get("team_abbrev") or p.get("game", "")
            pick_label = f"{matchup} {stat}" if matchup else stat
        elif stat == "GOLF_WIN":
            pick_label = f"{p['player']} {direction}"
        elif stat == "PARLAY":
            pick_label = (p.get("player") or "Parlay").strip()
        else:
            parts = (p.get("player") or "").split() or [""]
            last = parts[-1]
            if last.lower() in _SUFFIXES and len(parts) >= 2:
                last = parts[-2]
            pick_label = f"{last} {direction} {line_val} {stat}"

        inj_flag    = " 🔄" if p.get("injury_trigger") else ""
        _ctx = _CTX_VERDICTS.get(game, {})
        _ctx_tag = "  [CTX+]" if _ctx.get("verdict") == "confirms" else ("  [CTX-]" if _ctx.get("verdict") == "fades" else "")
        lines.append(f"{e} **{pick_label}**{_ctx_tag} | {odds_str} | {book_str} | **{size:.2f}u**{inj_flag}")
        lines.append(f"╰ {game} | Edge {edge_str} | Score {score_str}")

    lines.append(f"\n━━━━━━━━━━━━━━━━")
    lines.append(f"**Total:** {total_u:.2f}u")

    return {
        "username": "PicksByJonny",
        "content": "" if suppress_ping else "@everyone",
        "embeds": [{
            "title": f"🔒 Premium Portfolio{sport_label} — {today}",
            "description": "\n".join(lines),
            "color": 0xFFD700,  # Gold
            "thumbnail": {"url": BRAND_LOGO},
            "footer": {"text": f"{BRAND_TAGLINE} · {now_et}"},
        }]
    }


def build_potd_embed(potd, today, sport=None):
    """Build the standalone POTD embed (posted after premium card, same channel)."""
    stat = potd.get("stat", "")
    direction = potd["direction"].upper()
    line_val = potd["line"]
    game = potd.get("game", "")
    odds_str = fmt_odds(potd["odds"])
    book_str = display_book(potd["book"])
    size = potd.get("size", 0)
    edge_str = f"+{potd['adj_edge']*100:.1f}%"
    score_str = f"{potd.get('pick_score', 0):.1f}"
    tier = potd.get("tier", "")
    proj = potd.get("proj", 0)
    now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%I:%M %p ET")

    _SUFFIXES = {"jr.", "sr.", "ii", "iii", "iv"}
    if stat == "TEAM_TOTAL":
        pick_label = f"{potd['player']} {direction} {line_val}"
    elif stat in ("ML_FAV", "ML_DOG"):
        pick_label = potd["player"]
    elif stat in ("SPREAD", "TOTAL", "F5_TOTAL", "F5_SPREAD", "F5_ML"):
        pick_label = f"{potd['player']} {direction} {line_val}"
    elif stat in ("NRFI", "YRFI"):
        matchup = potd.get("team_abbrev") or potd.get("game", "")
        pick_label = f"{matchup} {stat}" if matchup else stat
    elif stat == "GOLF_WIN":
        pick_label = f"{potd['player']} {direction}"
    elif stat == "PARLAY":
        pick_label = (potd.get("player") or "Parlay").strip()
    else:
        parts = (potd.get("player") or "").split() or [""]
        last = parts[-1]
        if last.lower() in _SUFFIXES and len(parts) >= 2:
            last = parts[-2]
        pick_label = f"{last} {direction} {line_val} {stat}"

    _ctx = _CTX_VERDICTS.get(game, {})
    _ctx_tag = " [CTX+]" if _ctx.get("verdict") == "confirms" else (" [CTX-]" if _ctx.get("verdict") == "fades" else "")
    description = (
        f"━━━━━━━━━━━━━━━━\n"
        f"**{pick_label}**{_ctx_tag}\n"
        f"{potd['player']} | {game}\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"{odds_str} @ {book_str} | **{size:.2f}u**\n\n"
        f"Edge: **{edge_str}** | Score: **{score_str}**\n"
        f"Proj: {proj:.1f} {stat.lower()}"
    )

    sport_suffix = f" · {sport}" if sport else ""
    return {
        "username": "PicksByJonny",
        "embeds": [{
            "title": f"⭐ Pick of the Day{sport_suffix} — {today}",
            "description": description,
            "color": 0xFF4500,  # OrangeRed
            "thumbnail": {"url": BRAND_LOGO},
            "footer": {"text": f"{BRAND_TAGLINE} · {now_et}"},
        }]
    }


def post_to_discord(premium, mode, today, suppress_ping=False, force=False, sport=None):
    """Post the premium card + standalone POTD embed to #premium-portfolio.

    Uses discord_posted.json guard keys to prevent double-posts on re-run.
    sport: sorted sport key e.g. "MLB", "NBA", "NBA+NHL" — enables separate
    MLB + NBA cards on the same day. Guard key: premium_card:{sport}:{date}.
    force=True (--force-card) releases the guard keys before claiming so the
    card re-posts even if it was already sent today.
    """
    if not premium:
        print("  [Discord] No premium picks — skipping premium post.")
        return

    _sport_label = sport or "MULTI"

    # Premium card
    premium_key = f"premium_card:{_sport_label}:{today}"
    if force:
        _discord_release_post(premium_key)
    if not _discord_claim_post(premium_key):
        print(f"  [Discord] ⏭️  Premium card already posted for {_sport_label} {today} — skipping")
    else:
        payload = build_premium_embed(premium, mode, today, suppress_ping=suppress_ping, sport=sport)
        if _webhook_post(DISCORD_WEBHOOK_URL, payload, label="premium card"):
            print(f"  [Discord] ✅ Premium card posted ({len(premium[:5])} picks) [{_sport_label}]")
        else:
            _notify_post_failure("premium_card", guard_key=premium_key)

    # POTD — separate embed, same channel, same webhook.
    # premium[0] is guaranteed non-KILLSHOT (KILLSHOTs are excluded from premium).
    potd_key = f"potd:{_sport_label}:{today}"
    if force:
        _discord_release_post(potd_key)
    if not _discord_claim_post(potd_key):
        print(f"  [Discord] ⏭️  POTD already posted for {_sport_label} {today} — skipping")
    else:
        potd = premium[0]
        potd_payload = build_potd_embed(potd, today, sport=sport)
        if _webhook_post(DISCORD_WEBHOOK_URL, potd_payload, label=f"POTD: {potd['player']} {potd['stat']}"):
            print(f"  [Discord] ✅ POTD posted: {potd['player']} {potd['stat']}")
        else:
            _discord_release_post(potd_key)


# size_daily_lay lives in sizing.py (re-imported above with the other sizing fns).


def post_daily_lay(alt_spread_parlay, today, suppress_ping=False, save=True):
    """Post the alt spread parlay to #daily-lay channel."""
    if not DISCORD_ALT_PARLAY_WEBHOOK or not alt_spread_parlay:
        print("  [Discord] No alt spread parlay — skipping #daily-lay post.")
        return
    legs = alt_spread_parlay.get("legs", [])
    if not legs:
        return

    combined_prob = alt_spread_parlay.get("combined_prob", 0)
    # M26: also compute book-implied combined prob for transparency (gate uses model prob)
    book_implied_combined = 1.0
    for _leg in legs:
        _leg_odds = _leg.get("real_odds")
        if _leg_odds is not None:
            book_implied_combined *= implied_prob(_leg_odds)
    if combined_prob < MIN_DAILY_LAY_PROB:
        print(f"  [Discord] Daily Lay combined prob {combined_prob*100:.1f}% < {MIN_DAILY_LAY_PROB*100:.0f}% threshold — skipping weak parlay.")
        return

    guard_key = f"daily_lay:{today}"
    if not _discord_claim_post(guard_key):
        print(f"  [Discord] ⏭️  Daily Lay already posted for {today} — skipping")
        return

    now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%I:%M %p ET")
    book = alt_spread_parlay.get("book", "N/A")
    parlay_odds_raw = alt_spread_parlay.get("parlay_odds", 0)
    parlay_odds = fmt_odds(parlay_odds_raw)
    n_legs = len(legs)
    DAILY_LAY_SIZE = size_daily_lay(combined_prob, parlay_odds_raw)
    print(f"  [daily-lay-sizing] Kelly sizing: combined_prob={combined_prob:.3f} (book-implied={book_implied_combined:.3f}) odds={parlay_odds} → {DAILY_LAY_SIZE:.2f}u")

    leg_lines = [f"{n_legs}-leg alt spread parlay @ {book}\n"]
    for i, leg in enumerate(legs, 1):
        team = leg.get("team", "")
        spread = leg.get("alt_spread", 0)
        sign = "+" if spread > 0 else ""
        leg_odds = fmt_odds(leg.get("real_odds", 0)) if leg.get("real_odds") else "N/A"
        cover_pct = f"{leg.get('alt_cover_prob', 0)*100:.0f}%"
        game = leg.get("game", "")
        leg_lines.append(f"**Leg {i}** | {team} {sign}{spread:.1f} (alt) | {leg_odds} | {cover_pct} cover")
        leg_lines.append(f"╰ {game}")

    leg_lines.append(f"\n━━━━━━━━━━━━━━━━")
    leg_lines.append(f"**{parlay_odds}** combined | **{DAILY_LAY_SIZE:.2f}u**")

    payload = {
        "username": "PicksByJonny",
        "content": "" if suppress_ping else "@everyone",
        "embeds": [{
            "title": f"🎲 Daily Lay — {today}",
            "description": "\n".join(leg_lines),
            "color": 0x9B59B6,
            "footer": {"text": f"{BRAND_TAGLINE} · {now_et}"}
        }]
    }
    if _webhook_post(DISCORD_ALT_PARLAY_WEBHOOK, payload, label=f"daily lay ({n_legs} legs @ {parlay_odds})"):
        print(f"  [Discord] ✅ Daily Lay posted to #daily-lay ({n_legs} legs @ {parlay_odds})")
        _log_daily_lay(alt_spread_parlay, today, save=save)
    else:
        _notify_post_failure("daily_lay", guard_key=guard_key)








def post_longshot(safest6_parlay, today, suppress_ping=False, save=True):
    """Post the longshot 6-leg parlay to #longshot (or #bonus-drops fallback)."""
    if not safest6_parlay:
        print("  [Discord] No longshot parlay — skipping.")
        return
    legs = safest6_parlay.get("legs", [])
    if len(legs) < 6:
        return

    webhook = DISCORD_LONGSHOT_WEBHOOK or DISCORD_BONUS_WEBHOOK
    if not webhook:
        print("  [Discord] DISCORD_LONGSHOT_WEBHOOK not configured — skipping longshot post.")
        return

    guard_key = f"longshot:{today}"
    if not _discord_claim_post(guard_key):
        print(f"  [Discord] ⏭️  Longshot already posted for {today} — skipping")
        return

    now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%I:%M %p ET")
    combined_prob = safest6_parlay.get("combined_prob", 0)
    parlay_odds   = fmt_odds(safest6_parlay.get("parlay_odds", 0))
    book_display  = display_book(safest6_parlay.get("book", "")) or "N/A"

    _GL_STAT_CODES = {
        "ML_FAV", "ML_DOG", "SPREAD", "TOTAL", "TEAM_TOTAL",
        "F5_ML", "F5_SPREAD", "F5_TOTAL", "NRFI", "YRFI",
    }
    leg_lines = [f"6-leg longshot — safest model picks\n"]
    for i, leg in enumerate(legs, 1):
        dir_word  = "Over" if str(leg.get("direction", "")).lower() == "over" else "Under"
        wp_pct    = f"{leg.get('win_prob', 0)*100:.0f}%"
        stat      = leg.get("stat", "")
        # Game-line picks: player description already contains the market name;
        # appending the raw stat code (e.g. TEAM_TOTAL, F5_TOTAL) is redundant.
        stat_suffix = "" if stat in _GL_STAT_CODES else f" {stat}"
        leg_lines.append(
            f"**Leg {i}** | {leg.get('player','')} {dir_word} {leg.get('line','')}"
            f"{stat_suffix} | {wp_pct}"
        )
    leg_lines.append(f"\n━━━━━━━━━━━━━━━━")
    leg_lines.append(f"**{parlay_odds}** combined | **{LONGSHOT_SIZE:.2f}u** | {combined_prob*100:.1f}% model prob | 📍 {book_display}")

    payload = {
        "username": "PicksByJonny",
        "content": "" if suppress_ping else "@everyone",
        "embeds": [{
            "title": f"🎯 Longshot — {today}",
            "description": "\n".join(leg_lines),
            "color": 0xE74C3C,
            "footer": {"text": f"{BRAND_TAGLINE} · {now_et}"}
        }]
    }
    if _webhook_post(webhook, payload, label=f"longshot (6-leg @ {parlay_odds})"):
        print(f"  [Discord] ✅ Longshot posted ({parlay_odds})")
        if save:
            _log_longshot(safest6_parlay, today)
    else:
        _discord_release_post(guard_key)




def post_value_parlay(value_parlay, today, suppress_ping=False, save=True):
    """Post the 5-leg value parlay to #bonus-drops (fires only when longshot cannot build)."""
    if not value_parlay:
        return
    legs = value_parlay.get("legs", [])
    if len(legs) < 5:
        return

    webhook = DISCORD_BONUS_WEBHOOK
    if not webhook:
        print("  [Discord] DISCORD_BONUS_WEBHOOK not configured — skipping value parlay post.")
        return

    guard_key = f"value_parlay:{today}"
    if not _discord_claim_post(guard_key):
        print(f"  [Discord] ⏭️  Value parlay already posted for {today} — skipping")
        return

    now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%I:%M %p ET")
    combined_prob = value_parlay.get("combined_prob", 0)
    parlay_odds   = fmt_odds(value_parlay.get("parlay_odds", 0))
    book_display  = display_book(value_parlay.get("book", "")) or "N/A"

    _GL_STAT_CODES = {
        "ML_FAV", "ML_DOG", "SPREAD", "TOTAL", "TEAM_TOTAL",
        "F5_ML", "F5_SPREAD", "F5_TOTAL", "NRFI", "YRFI",
    }
    leg_lines = [f"5-leg value parlay — safest model picks\n"]
    for i, leg in enumerate(legs, 1):
        dir_word  = "Over" if str(leg.get("direction", "")).lower() == "over" else "Under"
        wp_pct    = f"{leg.get('win_prob', 0)*100:.0f}%"
        stat      = leg.get("stat", "")
        stat_suffix = "" if stat in _GL_STAT_CODES else f" {stat}"
        leg_lines.append(
            f"**Leg {i}** | {leg.get('player','')} {dir_word} {leg.get('line','')}"
            f"{stat_suffix} | {wp_pct}"
        )
    leg_lines.append(f"\n━━━━━━━━━━━━━━━━")
    leg_lines.append(f"**{parlay_odds}** combined | **{VALUE_PARLAY_SIZE:.2f}u** | {combined_prob*100:.1f}% model prob | 📍 {book_display}")

    payload = {
        "username": "PicksByJonny",
        "content": "" if suppress_ping else "@everyone",
        "embeds": [{
            "title": f"💎 Value Parlay — {today}",
            "description": "\n".join(leg_lines),
            "color": 0x2ECC71,
            "footer": {"text": f"{BRAND_TAGLINE} · {now_et}"}
        }]
    }
    if _webhook_post(webhook, payload, label=f"value parlay (5-leg @ {parlay_odds})"):
        print(f"  [Discord] ✅ Value parlay posted ({parlay_odds})")
        if save:
            _log_value_parlay(value_parlay, today)
    else:
        _discord_release_post(guard_key)




def _card_guard_should_block_logging(card_was_up: bool, no_discord: bool, force_card: bool) -> bool:
    """Return True iff the premium-card guard should suppress log_picks.

    The card guard exists for *Discord* dedup — preventing a duplicate
    premium-card post when the day's card has already shipped.  Two flags
    bypass it because they decouple logging from the Discord post:

    * ``--no-discord`` (shadow / research / dry-run): no Discord post will
      ever happen, so the guard has no purpose.  Without this bypass the
      shadow scheduled task silently logs zero rows whenever the live
      SaberSim card has already fired earlier in the day — the original
      symptom that motivated audit item A4 (2026-05-06).
    * ``--force-card``: explicit operator override (existing behavior;
      kept here for clarity and so the helper covers both paths).
    """
    if not card_was_up:
        return False
    if no_discord or force_card:
        return False
    return True


def _card_already_posted_today(today_str, sport_key=None):
    """Return True if a premium card for this sport has already been posted today.

    sport_key: sorted sport string e.g. "MLB", "NBA", "NBA+NHL". If None, checks
    all sport keys (backward compat). Per-sport keys allow running MLB + NBA
    separately on the same day without the second run being blocked.

    H14: previous implementation scanned pick_log.csv for 'primary' run_type
    rows, which conflates card posting with KILLSHOT pick logging — a run that
    only qualified KILLSHOT picks would log them as run_type='primary' and
    incorrectly suppress the card on the next run.

    Now uses the discord guard key as the source of truth. Falls back to
    pick_log scan (checking card_slot is set) when the guard cannot be read.
    """
    try:
        guard = _load_discord_guard()
        if sport_key:
            # Check sport-keyed guard (new format) first, then legacy global key
            if guard.get(f"premium_card:{sport_key}:{today_str}"):
                return True
        else:
            # Backward compat: check any sport key for today
            prefix = f"premium_card:"
            for k, v in guard.items():
                if k.endswith(f":{today_str}") and k.startswith(prefix) and v:
                    return True
        # Guard says not posted — also check pick_log as a safety net.
        # Require card_slot to be non-blank: only the card posting path sets
        # card_slot; KILLSHOT-only runs leave it blank (H14 fix).
        log_path = Path(PICK_LOG_PATH)
        if not log_path.exists():
            return False
        with _pick_log_lock(log_path):
            with open(log_path, "r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        return any(
            r.get("date") == today_str
            and r.get("run_type") in {"primary", "", None}
            and r.get("card_slot", "").strip() not in ("", "0")
            and (not sport_key or r.get("sport", "") in sport_key.split("+"))
            for r in rows
        )
    except Exception as e:
        logger.warning("_is_card_posted: unexpected error — returning False: %s", e)
        return False


def _units_bet_today(today_str):
    """Sum units already bet today across all run_types (for cross-run 12u cap).

    Reads pick_log.csv and sums the size column for today's rows. Manual picks
    are excluded (they're tracked separately and don't count against daily cap).
    Returns 0.0 on any error so the cap falls back to session-only behaviour.
    """
    try:
        log_path = Path(PICK_LOG_PATH)
        if not log_path.exists():
            return 0.0
        with _pick_log_lock(log_path):
            with open(log_path, "r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        total = sum(
            float(r.get("size", 0) or 0)
            for r in rows
            if r.get("date") == today_str
            and r.get("run_type", "").lower() != "manual"
        )
        return round(total, 4)
    except Exception as e:
        logger.warning("_units_bet_today: unexpected error — returning 0.0: %s", e)
        return 0.0


def post_extras_to_discord(qualified, run_id=None, save=True):
    """Post a single bonus drop to #bonus-drops.

    Selection rules (Option A from handoff):
      - "New" = pick not already in pick_log.csv under run_type='bonus' OR 'primary' for today
      - Single highest Pick Score new pick only
      - Hard cap: 5 bonus posts per calendar day (checked via pick_log.csv)

    run_id: optional identifier for this run (defaults to current timestamp string).
    """
    if not DISCORD_BONUS_WEBHOOK:
        print("  [Discord] DISCORD_BONUS_WEBHOOK not configured — skipping bonus post.")
        return

    today_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    # ET for run_id so timestamp stays consistent with today_str (audit H-1).
    run_id = run_id or datetime.now(ZoneInfo("America/New_York")).strftime("%H%M%S")

    # --- Check daily cap ---
    log_path = Path(PICK_LOG_PATH)
    bonus_today_count = 0
    already_posted_keys = set()  # (player_lower, stat, line, direction)

    if log_path.exists() and log_path.stat().st_size > 0:
        # Shared lock — don't race a mid-flush CLV/grader write (audit H-8).
        with _pick_log_lock(log_path):
            with open(log_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("date", "") != today_str:
                        continue
                    # Count bonus posts
                    if row.get("run_type", "").lower() == "bonus":
                        bonus_today_count += 1
                    # Only block re-posting if: was on the premium card OR already a bonus drop
                    # Qualified picks that didn't make the card ARE eligible for bonus
                    is_card_pick = row.get("card_slot", "").strip() not in ("", None)
                    is_bonus = row.get("run_type", "").lower() == "bonus"
                    if is_card_pick or is_bonus:
                        already_posted_keys.add((
                            row.get("player", "").strip().lower(),
                            row.get("stat", "").strip(),
                            str(row.get("line", "")).strip(),
                            row.get("direction", "").strip().lower(),
                        ))

    if bonus_today_count >= BONUS_DAILY_CAP:
        print(f"  [Discord] Bonus cap reached ({BONUS_DAILY_CAP}/day) — skipping bonus post.")
        return

    # --- Find single highest-score new pick ---
    eligible = []
    for p in qualified:
        key = (
            p.get("player", "").strip().lower(),
            p.get("stat", "").strip(),
            str(p.get("line", "")).strip(),
            p.get("direction", "").strip().lower(),
        )
        if (key not in already_posted_keys
                and p.get("pick_score") is not None
                and p.get("pick_score", 0) >= MIN_BONUS_SCORE
                and p.get("win_prob", 0) >= MIN_BONUS_WIN_PROB
                and p.get("tier") != "KILLSHOT"):
            eligible.append(p)

    if not eligible:
        print("  [Discord] No new picks available for bonus drop.")
        return

    best = max(eligible, key=lambda p: p.get("pick_score", 0))

    # --- Re-size the bonus pick with VAKE variance + tier multipliers ---
    # The pick entered here with base sizing (from size_picks_base), which caps
    # at 1.25u for any edge ≥ 9% regardless of tier. A standalone bonus drop
    # should track Premium tier economics (T3 ≈ 0.50u, T2 ≈ 1.00u), so recompute.
    # This overwrites the pick's `size` field, which _log_bonus_pick then reads.
    _prev_size = best.get("size")
    resized = size_bonus_pick(best)
    if resized is None:
        # Audit H-9: VAKE math rolled below the tier floor — refuse to ship
        # a dust bet. size_bonus_pick already logged the reason. We don't
        # try the next-best pick here: the bonus selector already filtered
        # on MIN_BONUS_SCORE and MIN_BONUS_WIN_PROB, so the top eligible
        # pick failing sizing is a real signal that today's bonus slate is
        # too weak. Skip for the day rather than drilling down into the
        # scraps.
        logger.warning("Bonus drop skipped — top eligible pick failed H-9 sizing gate.")
        return
    best["size"] = resized
    if _prev_size is not None and _prev_size != best["size"]:
        print(f"  [Discord] Bonus sizing: {best['tier']} {best['stat']} "
              f"{_prev_size:.2f}u → {best['size']:.2f}u (VAKE)")

    # M6: check 12u session cap AFTER sizing (uses the actual resized value, not base size)
    _units_so_far = _units_bet_today(today_str)
    _bonus_est = best.get("size", 1.25)
    if _units_so_far + _bonus_est > 12.0:
        print(f"  [Discord] Bonus drop skipped — session cap: {_units_so_far:.2f}u logged + {_bonus_est:.2f}u bonus would exceed 12u.")
        return

    # --- Build embed ---
    dir_word = "Over" if best["direction"] == "over" else "Under"
    team = best.get("team_abbrev", "")
    lines = [
        f"**{best['player']} ({team}) {dir_word} {best['line']} {best['stat']}**",
        f"{fmt_odds(best['odds'])} @ {display_book(best['book'])} — **{best.get('size',0):.2f}u**",
        "",
        f"Win: **{fmt_pct(best['win_prob'])}** | Edge: **{fmt_pct(best['adj_edge'])}** | Score: **{best.get('pick_score',0):.1f}**",
        f"Proj: {best['proj']:.1f} | {best['game']}",
    ]
    payload = {
        "username": "PicksByJonny",
        "embeds": [{
            "title": "💎 Bonus Drop",
            "description": "\n".join(lines),
            "color": 0x00BFFF,  # Deep sky blue
            "footer": {"text": BRAND_TAGLINE},
        }]
    }

    if _webhook_post(DISCORD_BONUS_WEBHOOK, payload, label=f"bonus drop: {best['player']} {best['stat']}"):
        print(f"  [Discord] ✅ Bonus drop posted: {best['player']} {best['stat']} (Score: {best.get('pick_score',0):.1f})")
        # Log this bonus pick to pick_log.csv with run_type='bonus'.
        # Discord post already succeeded — any log failure must NOT crash the run
        # or we end up with a ghost post and no ledger entry for grade_picks/CLV.
        try:
            _log_bonus_pick(best, run_id, today_str, save=save)
        except Exception as _log_err:
            logger.error(f"Bonus drop posted but logging failed: {_log_err}")
            logger.warning(f"Backfill manually: {best['player']} {best['stat']} {best['direction']} {best['line']} @ {best['odds']} ({best['book']})")




# ============================================================
#  KILLSHOT TIER
# ============================================================

def _killshot_size(pick):
    """Return KILLSHOT unit size per v2 rules.
    3u default. Bumps to 4u iff win_prob >= KILLSHOT_BUMP_WIN_PROB AND edge >= KILLSHOT_BUMP_EDGE.
    Replaces VAKE entirely for KILLSHOT picks.

    Reads `adj_edge` (canonical internal key used throughout run_picks.py)
    with fallback to `edge` — the CSV column name and the key used by tests
    and by rows reconstructed from pick_log.csv.
    """
    try:
        wp   = float(pick.get("win_prob", 0))
        edge = float(pick.get("adj_edge", pick.get("edge", 0)))
    except (TypeError, ValueError):
        return KILLSHOT_SIZE_BASE
    if wp >= KILLSHOT_BUMP_WIN_PROB and edge >= KILLSHOT_BUMP_EDGE:
        return KILLSHOT_SIZE_BUMP
    return KILLSHOT_SIZE_BASE


def _killshot_odds_wp_ok(pick):
    """v3 shared odds-range + odds-dependent wp floor (Plan 6 §13).

    wp >= implied_prob(odds) + KILLSHOT_WP_MARGIN — replaces the static 0.65
    floor, which left a latent −EV window (wp=0.65 at −200 is −2.5%/unit).
    Self-adjusting under any future parameter changes, including the H3 Platt
    refit. Applied to BOTH the auto path and the manual --killshot path (the
    v2 manual path checked score only).

    Returns (True, "", "") on pass, (False, reason, code) on fail —
    code is a short machine tag for blocked-pick logging (ODDS / WP).
    """
    try:
        odds = int(float(pick.get("odds", 0)))  # H6: float() first handles "-115.5" strings
    except (TypeError, ValueError):
        return False, "odds unparseable", "ODDS"
    if odds < KILLSHOT_ODDS_MIN or odds > KILLSHOT_ODDS_MAX:
        return False, f"odds={odds:+d} outside [{KILLSHOT_ODDS_MIN},{KILLSHOT_ODDS_MAX}]", "ODDS"
    try:
        wp = float(pick.get("win_prob", 0))
    except (TypeError, ValueError):
        return False, "win_prob unparseable", "WP"
    wp_floor = implied_prob(odds) + KILLSHOT_WP_MARGIN
    if wp < wp_floor:
        return False, f"win_prob={wp:.3f} < breakeven+margin {wp_floor:.3f} at {odds:+d}", "WP"
    return True, "", ""


def _passes_killshot_v2_gate(pick):
    """v3 auto-qualify gate (name kept for test/API stability). ALL must pass:
    score floor, odds range, odds-dependent wp floor, stat allowlist.
    Tier requirement dropped in v3 — T1 WR (46.6%) < T2 (60.3%); selection on
    floors is strictly better, and tier already enters via BM shrinkage (Plan 9 §9F).
    Returns (True, "") on pass, (False, reason) on fail.
    Manual promotes bypass score/stat but NOT the odds/wp checks.
    """
    # WNBA excluded from KILLSHOT until CLV history matures (pre-registered at
    # go-live 2026-06-09 — TIER_FINDINGS.md / WNBA_RESEARCH_FINDINGS.md; was
    # implicitly excluded by the SHADOW_SPORTS split pre-go-live).
    if pick.get("sport") == "WNBA":
        return False, "WNBA excluded from KILLSHOT (insufficient CLV history)"
    try:
        score = float(pick.get("pick_score", 0))
    except (TypeError, ValueError):
        return False, "pick_score unparseable"
    if score < KILLSHOT_SCORE_FLOOR:
        return False, f"score={score:.1f} < {KILLSHOT_SCORE_FLOOR}"
    ok, reason, _code = _killshot_odds_wp_ok(pick)
    if not ok:
        return False, reason
    stat = pick.get("stat", "")
    if stat not in KILLSHOT_STAT_ALLOW:
        return False, f"stat={stat!r} not in allowlist"
    return True, ""


def _assert_killshot_invariants():
    """Fail fast at module load if KILLSHOT_STAT_ALLOW contains a dead entry
    (Plan 6 §13: the v2 PTS-tier and SOG-suspension dead entries went unnoticed
    for 5+ weeks — 0 KILLSHOTs fired).

    Every allowlisted stat must be (a) not suspended and (b) in some active
    tier's stat universe (i.e. capable of producing a qualified pick at all).
    """
    suspended = KILLSHOT_STAT_ALLOW & set(SUSPENDED_STATS)
    assert not suspended, (
        f"KILLSHOT_STAT_ALLOW contains suspended stat(s) {sorted(suspended)} — "
        f"dead entries can never fire. Remove them from the allowlist (or lift "
        f"the suspension in SUSPENDED_STATS) before starting the engine."
    )
    orphans = KILLSHOT_STAT_ALLOW - set(STAT_FAMILY_TIER)
    assert not orphans, (
        f"KILLSHOT_STAT_ALLOW contains stat(s) {sorted(orphans)} not routed to any "
        f"tier in STAT_FAMILY_TIER — they can never reach the qualified pool."
    )


_assert_killshot_invariants()   # fail fast at module load (Plan 6 §13, 8b)


def _killshots_this_week(today_str):
    """Count KILLSHOT picks logged in the rolling 7 days (including today)."""
    log_path = Path(PICK_LOG_PATH)
    if not log_path.exists():
        return 0
    cutoff = (datetime.strptime(today_str, "%Y-%m-%d") - timedelta(days=6)).strftime("%Y-%m-%d")
    try:
        # Shared lock — don't race a mid-flush CLV/grader write (audit H-8).
        with _pick_log_lock(log_path):
            with open(log_path, "r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        return sum(
            1 for r in rows
            if r.get("tier") == "KILLSHOT"
            and cutoff <= r.get("date", "") <= today_str
        )
    except Exception as e:
        # Fail SAFE: on any read/parse error, assume the cap is full.
        # Returning 0 here would allow the engine to post the full weekly
        # KILLSHOT cap on top of already-posted shots (audit H4 / F2.7).
        logger.error(
            f"[KILLSHOT] _killshots_this_week failed — assuming cap full to "
            f"prevent over-posting: {type(e).__name__}: {e}"
        )
        return KILLSHOT_WEEKLY_CAP


def select_killshots(qualified, today_str, manual_players=None):
    """Identify KILLSHOT picks from the qualified pool (v3 rules — Plan 6 §13).

    Auto-qualify (all must pass; no tier requirement in v3):
      - pick_score >= KILLSHOT_SCORE_FLOOR (65)
      - odds in [KILLSHOT_ODDS_MIN, KILLSHOT_ODDS_MAX] ([-200, +110])
      - win_prob >= implied_prob(odds) + KILLSHOT_WP_MARGIN (0.03) — odds-dependent
      - stat in KILLSHOT_STAT_ALLOW ({PTS, AST}; SOG removed while suspended)

    Manual promote (--killshot NAME): bypasses score/stat selection, still requires
      pick_score >= KILLSHOT_MANUAL_FLOOR (75) AND the odds range + odds-dependent
      wp floor (v3 — the v2 manual path was a −EV bypass), counts toward weekly cap.

    Weekly cap: max KILLSHOT_WEEKLY_CAP (2) per rolling 7 days.

    8d: disqualification counts printed per run; near-misses (score floor met,
    another check failed) appended to pick_log_blocked.csv as KILLSHOT_{code}.

    Returns picks with tier='KILLSHOT' and sizing applied.
    """
    manual_players = manual_players or set()
    # CLI passes last names ("Pastrnak,McDavid") but pick rows store full names.
    # Normalise manual_players to lowercase tokens for case-insensitive substring match.
    manual_tokens = {m.strip().lower() for m in manual_players if m.strip()}
    already_posted = _killshots_this_week(today_str)
    remaining_cap  = max(0, KILLSHOT_WEEKLY_CAP - already_posted)

    if remaining_cap == 0:
        print(f"  [KILLSHOT] Weekly cap reached ({already_posted}/{KILLSHOT_WEEKLY_CAP}) — no KILLSHOTs today")
        return []

    def _player_matches(full_name: str) -> bool:
        if not manual_tokens:
            return False
        parts = {w.lower() for w in full_name.split() if w}
        full_lower = full_name.lower()
        # M3: match on exact full name OR per-word token only (no substring — "son" must not match "Johnson")
        return any(tok == full_lower or tok in parts for tok in manual_tokens)

    candidates = []
    disqual_counts = defaultdict(int)   # 8d: per-run disqualification tally
    for p in qualified:
        try:
            score = float(p.get("pick_score", 0))
        except (TypeError, ValueError):
            score = 0.0
        player = p.get("player", "")
        # Manual promote (v3): bypasses score-floor/stat selection but MUST still
        # pass the odds range + odds-dependent wp floor — the v2 manual path
        # checked score only, leaving a −EV bypass (Plan 6 §13).
        if _player_matches(player) and score >= KILLSHOT_MANUAL_FLOOR:
            m_ok, m_reason, _m_code = _killshot_odds_wp_ok(p)
            if m_ok:
                candidates.append(p)
            else:
                print(f"  [KILLSHOT] Manual promote REJECTED: {player} — {m_reason}")
            continue
        # Auto-qualify: must pass full v3 gate
        ok, _reason = _passes_killshot_v2_gate(p)
        if ok:
            candidates.append(p)
            continue
        # 8d: tally disqualifications; log near-misses (score floor met but
        # another check failed) to pick_log_blocked.csv so gate health is
        # visible in audits — v2's dead gate was console-only for 5+ weeks.
        code = "SCORE"
        if score >= KILLSHOT_SCORE_FLOOR:
            _ok2, _r2, code = _killshot_odds_wp_ok(p)
            if _ok2:
                code = "STAT"   # only remaining check that can have failed
            log_blocked_pick({**p, "gate_result": f"KILLSHOT_{code}"})
        disqual_counts[code] += 1

    if disqual_counts:
        _summary = ", ".join(f"{k}={v}" for k, v in sorted(disqual_counts.items()))
        print(f"  [KILLSHOT] {sum(disqual_counts.values())} disqualified ({_summary}); near-misses logged to blocked log")

    # Sort by score desc, apply cap
    candidates.sort(key=lambda x: x.get("pick_score", 0), reverse=True)
    killshots = candidates[:remaining_cap]

    # Apply KILLSHOT tier + sizing
    for p in killshots:
        p["tier"] = "KILLSHOT"
        p["size"] = _killshot_size(p)

    if killshots:
        print(f"  [KILLSHOT] {len(killshots)} pick(s) qualified (weekly total: {already_posted + len(killshots)}/{KILLSHOT_WEEKLY_CAP})")

    return killshots


def build_killshot_embed(pick, today, suppress_ping=False):
    """Build a KILLSHOT embed for #killshot channel."""
    dir_word = "Over" if pick.get("direction") == "over" else "Under"
    team     = pick.get("team_abbrev", "")
    score    = pick.get("pick_score", 0)
    content  = "" if suppress_ping else "@everyone"

    _ctx = _CTX_VERDICTS.get(pick.get("game", ""), {})
    _ctx_tag = "  [CTX+]" if _ctx.get("verdict") == "confirms" else ("  [CTX-]" if _ctx.get("verdict") == "fades" else "")
    desc = "\n".join([
        f"**{pick['player']} ({team}) {dir_word} {pick['line']} {pick['stat']}**{_ctx_tag}",
        f"{fmt_odds(pick['odds'])} @ {display_book(pick['book'])} — **{pick.get('size', 0):.2f}u**",
        "",
        f"Win: **{fmt_pct(pick['win_prob'])}** | Edge: **{fmt_pct(pick['adj_edge'])}** | Score: **{score:.1f}**",
        f"Proj: {pick['proj']:.1f} | {pick['game']}",
    ])

    return {
        "username": "PicksByJonny",
        "content": content,
        "embeds": [{
            "title":       "⚡ KILLSHOT",
            "description": desc,
            "color":       0xFF0000,
            "thumbnail":   {"url": BRAND_LOGO},
            "footer":      {"text": f"{today} · {BRAND_TAGLINE} · high conviction only"},
        }]
    }


def post_killshots_to_discord(killshots, today, today_str, suppress_ping=False):
    """Post each KILLSHOT pick to #killshot channel.

    Uses per-pick guard keys (killshot:{date}:{player}:{stat}) so a rerun of
    run_picks.py doesn't re-fire pings for already-posted KILLSHOTS. Guard
    is only marked on real (non-test) successful posts.
    """
    if not killshots:
        return
    if not DISCORD_KILLSHOT_WEBHOOK:
        print("  [Discord] DISCORD_KILLSHOT_WEBHOOK not configured — skipping KILLSHOT posts.")
        return
    for pick in killshots:
        ks_key = f"killshot:{today_str}:{pick.get('player','').strip().lower()}:{pick.get('stat','')}:{pick.get('direction','')}:{pick.get('line','')}"
        if not _discord_claim_post(ks_key):
            print(f"  [Discord] ⏭️  KILLSHOT already posted: {pick['player']} {pick['stat']} — skipping")
            continue
        payload = build_killshot_embed(pick, today, suppress_ping=suppress_ping)
        if _webhook_post(DISCORD_KILLSHOT_WEBHOOK, payload, label=f"KILLSHOT: {pick['player']} {pick['stat']}"):
            print(f"  [Discord] 🎯 KILLSHOT posted: {pick['player']} {pick['stat']} ({pick.get('size', 0):.2f}u · Score {pick.get('pick_score', 0):.1f})")
        else:
            _notify_post_failure(
                f"killshot:{pick.get('player','')}:{pick.get('stat','')}",
                guard_key=ks_key,
            )
            print(f"  [Discord] ⚠ KILLSHOT post failed: {pick['player']} {pick['stat']}")


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

def main():
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

    args = parser.parse_args()

    # --no-cap safety guard: must be paired with --no-discord to prevent
    # accidentally logging every qualified pick to the live pick_log during a
    # real Discord run. This flag is only meaningful in shadow / research mode.
    if getattr(args, "no_cap", False) and not args.no_discord:
        print("  ERROR: --no-cap requires --no-discord (safety guard — use shadow/research mode only).")
        sys.exit(1)

    # M12: prevent emoji → UnicodeEncodeError crashes on Windows cmd.exe (cp1252)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # M8: prevent concurrent runs (double-post guard at the process level)
    _run_lock_path = str(_data_path("run_picks.lock"))
    _run_lock = FileLock(_run_lock_path, timeout=0)
    try:
        _run_lock.acquire()
    except _FileLockTimeout:
        print("ERROR: another run_picks.py is already running. Aborting to prevent double-post.")
        sys.exit(1)

    global _CONFIRM_MODE
    _CONFIRM_MODE = args.confirm

    print("""
    ╔═══════════════════════════════════════════╗
    ║  JonnyParlay MBP Runner v2.0              ║
    ║  Master Betting Prompt v9.4               ║
    ║  Pure Python — Zero AI, Deterministic     ║
    ╚═══════════════════════════════════════════╝
    """)

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

    fetcher = OddsFetcher()
    odds_data = fetcher.fetch_all(sports,
                                   fetch_alt_spreads=True,
                                   game_lines_only=args.alt_parlay,
                                   no_cache=args.no_cache,
                                   force=args.force)

    if args.dry_run:
        out_path = Path(OUTPUT_FOLDER)
        out_path.mkdir(parents=True, exist_ok=True)
        # ET date for dry-run filename (audit H-1).
        dp = out_path / f"odds_dry_{datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d')}.json"
        with open(dp, "w", encoding="utf-8") as f:
            json.dump(odds_data, f, indent=2, default=str)
        print(f"\n  Dry run saved: {dp}")
        return

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
                confirm=_CONFIRM_MODE,
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
                confirm=_CONFIRM_MODE,
                test=getattr(args, 'test', False),
                save=not args.no_save,
                debug=getattr(args, 'sgp_debug', False),
            )
        except Exception as e:
            print(f'  [MLB SGP] Error: {e} — skipping.')

    print("\n  Done. Let's eat.\n")


if __name__ == "__main__":
    main()
