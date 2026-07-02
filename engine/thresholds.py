"""Structural decision-boundary constants for run_picks.py.

Gate thresholds, win-prob/edge floors, sizing literals, caps, cutoffs, Kelly
fraction, and the KILLSHOT + WNBA early-season gate parameters. Extracted from
run_picks.py (extract-and-re-export refactor, Step 9) and re-imported there so
existing call sites and `from run_picks import ...` keep resolving. Imports only
{stdlib, paths, secrets_config} — never run_picks or the other constants modules.
"""
from datetime import date
from pathlib import Path

BONUS_DAILY_CAP = 5             # Max bonus posts per calendar day
MIN_BONUS_SCORE = 65            # Minimum pick_score to qualify for a bonus drop
MIN_BONUS_WIN_PROB = 0.65       # Minimum win probability to qualify for a bonus drop
MIN_DAILY_LAY_PROB = 0.50       # Minimum combined cover probability before posting daily lay
                                 # 0.50 guarantees EV > 0 at +100 cap: 0.50 × 2.00 = 1.00 (break-even at minimum).
                                 # Kelly is negative at 47% for any realistic odds range; the 0.25u
                                 # floor in size_daily_lay() handles under-Kelly stakes. Old 0.33
                                 # allowed zero-EV posts at the parlay level.
MIN_DAILY_LAY_MARGIN = 4.0      # Minimum projected margin (pts) for a team to qualify as a daily lay leg
MIN_LEG_EDGE_DAILY = 0.025      # Minimum per-leg edge for daily lay legs (screens out noise)
MIN_LEG_COVER_PROB_DAILY = 0.58 # Minimum per-leg cover probability for daily lay legs
LONGSHOT_SIZE = 0.25            # Unit size for longshot parlay (high variance, small stake)
VALUE_PARLAY_SIZE = 0.25        # Unit size for 5-leg value parlay fallback; tune separately after data
LONGSHOT_MAX_PER_GAME = 2       # F2.20: moved from inside build_safest6_parlay to top-level constant
LONGSHOT_PAIR_RHO = 0.35        # Plan 9 §9B: +ρ ranking boost for pitcher OUTS-under +
                                # opposing TEAM_TOTAL-over in the same game (ρ ≈ +0.30-0.40,
                                # mirror image of the X1 negative pair). Ranking-only —
                                # never blocks; displayed combined_prob stays independence.
SGP_LOG_SIZE  = 0.25            # Unit size for SGP when logged (mirrors sgp_builder.SGP_SIZE)

# ── KILLSHOT tier (v3 — Plan 6 §13 redesign 2026-06-05; see CLAUDE.md) ─────────
# v2 was internally dead (0 KILLSHOTs in 5+ weeks): PTS is T2 so PTS ∧ tier=T1 was
# unsatisfiable, SOG is suspended — only NBA AST could ever fire. v3 changes:
#   - tier requirement dropped (T1 WR=46.6% < T2=60.3%; selection on floors is
#     strictly better — tier already enters via BM shrinkage on win_prob, Plan 9 §9F)
#   - static wp floor replaced by odds-dependent: wp >= implied_prob(odds) + MARGIN
#     (closes the latent −EV window: wp=0.65 at −200 was −2.5%/unit)
#   - manual path now also enforces the odds range + wp floor (was score-only)
#   - SOG removed from allowlist while G_SOG_SUSPENDED — re-add at July refit
#   - _assert_killshot_invariants() fails fast at module load on dead entries
# Auto-qualify gate: ALL must pass
KILLSHOT_SCORE_FLOOR    = 65.0                             # Pick Score floor
KILLSHOT_WP_MARGIN      = 0.03                             # v3: wp >= implied_prob(odds) + 0.03 (breakeven + EV cushion)
KILLSHOT_ODDS_MIN       = -200                             # no razor-thin chalk (−EV window closed by the wp floor)
KILLSHOT_ODDS_MAX       =  110                             # no live dogs
KILLSHOT_STAT_ALLOW     = frozenset({"PTS", "AST"})        # v3: SOG removed while G_SOG_SUSPENDED (re-add at July refit); REB dropped (L9), 3PM dropped (CV 0.65-1.2 incompatible)
# Manual override (via --killshot NAME): bypasses score/stat selection but still
# counts toward weekly cap AND must pass the odds range + odds-dependent wp floor (v3).
KILLSHOT_MANUAL_FLOOR   = 75.0                             # Minimum score to allow manual promote
KILLSHOT_WEEKLY_CAP     = 2                                # rarer = more signal
# Sizing: replaces VAKE for KILLSHOT picks. Flat-ish — safer plays don't argue for bigger size.
KILLSHOT_SIZE_BASE       = 3.0   # default
KILLSHOT_SIZE_BUMP       = 4.0   # bump ceiling
KILLSHOT_BUMP_WIN_PROB   = 0.70  # bump requires BOTH wp and edge
KILLSHOT_BUMP_EDGE       = 0.06

POISSON_CUTOFF = 8.5  # line threshold below which Poisson applies for low-count stats (see POISSON_STATS)

# WNBA early-season gate — opening-day extreme variance is structural (SaberSim cannot
# price new-team/new-role stars; Section 1 + 6 research). Plan 6 §14 (2026-06-05):
#   - opening gate re-keyed to GAMES PLAYED (both teams >= WNBA_OPENING_GATE_GAMES);
#     WNBA_OPENING_GATE_DAYS retained only as the fallback when the games-played
#     count is unavailable (EdgeModel DB missing/stale).
#   - early-season dampener rewired from edge-multiplication to SIGMA INFLATION
#     (sigma /= factor in calc_prop_prob) so win_prob, edge, score AND Kelly size
#     all shrink coherently — the old edge-mult lowered ranking but sized at full
#     confidence. Factors are DATA_GATED: recalibrate at WNBA go-live (100 graded).
WNBA_SEASON_START = date(2026, 5, 8)    # 2026 opener Fri May 8 (WNBA.com); was 5/13 (audit 2026-06)
WNBA_OPENING_GATE_DAYS = 3              # FALLBACK day gate (games-played source unavailable)
WNBA_OPENING_GATE_GAMES = 2             # both teams need >= 2 current-season games
WNBA_EARLY_SEASON_EDGE_MULT = [         # (day_threshold, factor) — ascending; sigma /= factor
    (14, 0.80),   # days 4-14:  sigma × 1.25
    (21, 0.90),   # days 15-21: sigma × 1.11
]
# G_WNBA_EDGE is an EV-PER-UNIT floor (Plan 6 §14 option B; replaced the dead
# WNBA_EDGE_FLOOR=0.035, which was always dominated by G9=0.05). Bar = the net EV
# of NBA's G9 floor pick at standard vig: edge 0.05 at −110 → EV = 0.05 × 1.9091
# ≈ 0.0955/unit. EV computed from ACTUAL quoted odds, so the floor auto-adjusts
# to vig (at −115 it requires ~5.1% edge; wider vig → higher edge required).
# (§14's "6.2% at −115" figure measured edge against p=0.50, not the engine's
# vigged-implied edge — corrected to the engine's frame here.)
WNBA_EV_FLOOR = 0.0955

PLATT_SPACE = "raw"  # "raw"=sigmoid(A*p+B); "logit"=sigmoid(A*logit(p)+B). Change SIMULTANEOUSLY with formula+A/B at H3.

F5_SCALAR = 0.558  # F5 share of full-game total. SYNCED 2026-07-02 to EdgeModel's realized-data reconciliation (0.558; n=2560 realized F5/full team-scores = 2.509/4.496). Was 0.540 (2022-25 market calibration; before that 0.503).

# Game line projection blending: anchor SaberSim to the market line.
# Formula in prose: the blended projection equals the market line plus
# BLEND_ALPHA of the gap between the SaberSim projection and the market.
# 0.25 means we trust SaberSim for 25% of any disagreement and the
# market for the remaining 75% — this prevents massive edge calculations
# when SaberSim disagrees with Vegas by 10+ pts.
BLEND_ALPHA = 0.25

BM_SHRINKAGE_DEFAULT = 0.80

KELLY_FRACTION = 6.0  # Units converter for Kelly sizing under the 100u bankroll convention:
                      # units = f* × 6, so stake fraction = f* × 6/100 ≈ 1/16.7 Kelly —
                      # NOT "1/6 Kelly" (Plan 6 §4 relabel; the value is correct, the old
                      # label was wrong). Calibrated 2026-06-01 on 207 primary/bonus picks
                      # (mid-band median implied-F ≈ 5.9).

DEFAULT_MARKET_MULT = 0.75

MAX_PREMIUM_PICKS = 3  # per-sport cap (multi-sport days: MLB+WNBA+NHL+NBA)
MIN_PICK_SCORE    = 15  # lowered 2026-05-27 — probability calibration improved, 25 was too restrictive
MIN_OVER_SCORE    = 15  # lowered to match MIN_PICK_SCORE — over/under treated equally
MIN_WIN_PROB      = 0.50  # floor removed 2026-05-27 — probability calibration improved


# ── Optional external overrides (audit S4f-X) ─────────────────────────────────
# The documented defaults above are the source of truth. An OPTIONAL
# `config/thresholds.toml` may override the operator-tunable SCALARS below without a
# code edit (single-file config, TOML via stdlib tomllib — no new dependency, and the
# module keeps its "stdlib + paths only" import contract). Default behaviour is
# unchanged: with no config file, nothing is overridden (replay byte-identical).
#
# Calibrated/frozen constants (KELLY_FRACTION, F5_SCALAR, BM_SHRINKAGE_DEFAULT,
# PLATT_SPACE, BLEND_ALPHA, DEFAULT_MARKET_MULT, WNBA_EV_FLOOR, POISSON_CUTOFF,
# LONGSHOT_PAIR_RHO) and non-scalar structures are deliberately NOT overridable —
# they change only via a reviewed code edit (see the fix-plan anti-patterns).
_TUNABLE = frozenset({
    "BONUS_DAILY_CAP", "MIN_BONUS_SCORE", "MIN_BONUS_WIN_PROB", "MIN_DAILY_LAY_PROB",
    "MIN_DAILY_LAY_MARGIN", "MIN_LEG_EDGE_DAILY", "MIN_LEG_COVER_PROB_DAILY",
    "LONGSHOT_SIZE", "VALUE_PARLAY_SIZE", "LONGSHOT_MAX_PER_GAME", "SGP_LOG_SIZE",
    "KILLSHOT_SCORE_FLOOR", "KILLSHOT_WP_MARGIN", "KILLSHOT_ODDS_MIN", "KILLSHOT_ODDS_MAX",
    "KILLSHOT_MANUAL_FLOOR", "KILLSHOT_WEEKLY_CAP", "KILLSHOT_SIZE_BASE",
    "KILLSHOT_SIZE_BUMP", "KILLSHOT_BUMP_WIN_PROB", "KILLSHOT_BUMP_EDGE",
    "WNBA_OPENING_GATE_DAYS", "WNBA_OPENING_GATE_GAMES",
    "MAX_PREMIUM_PICKS", "MIN_PICK_SCORE", "MIN_OVER_SCORE", "MIN_WIN_PROB",
})


def _coerce_override(current, new):
    """Coerce `new` to the type of `current` (scalar only). Returns None if incompatible.

    bool is checked before int (bool is an int subclass); a float target accepts ints;
    an int target accepts a float only if it is integer-valued.
    """
    if isinstance(current, bool):
        return bool(new) if isinstance(new, bool) else None
    if isinstance(current, int):
        if isinstance(new, bool):
            return None
        if isinstance(new, int):
            return int(new)
        if isinstance(new, float) and new.is_integer():
            return int(new)
        return None
    if isinstance(current, float):
        return float(new) if (isinstance(new, (int, float)) and not isinstance(new, bool)) else None
    if isinstance(current, str):
        return str(new) if isinstance(new, str) else None
    return None


def _apply_overrides(ns: dict, overrides: dict, tunable=_TUNABLE) -> dict:
    """Override whitelisted scalar names in namespace `ns` from `overrides`.

    Only names in `tunable` that already exist in `ns` and coerce to the existing
    type are applied. Returns the {name: value} actually applied.
    """
    applied = {}
    for name, val in overrides.items():
        if name not in tunable or name not in ns:
            continue
        coerced = _coerce_override(ns[name], val)
        if coerced is None:
            continue
        ns[name] = coerced
        applied[name] = coerced
    return applied


def _load_threshold_overrides() -> dict:
    """Opt-in: apply `config/thresholds.toml` over the whitelisted scalars. Fail-soft."""
    try:
        import tomllib  # stdlib (Python 3.11+); read-only
    except ImportError:
        return {}
    try:
        from paths import PROJECT_ROOT
        cfg = Path(PROJECT_ROOT) / "config" / "thresholds.toml"
    except Exception:
        return {}
    if not cfg.exists():
        return {}
    try:
        with open(cfg, "rb") as fh:
            data = tomllib.load(fh)
    except Exception as exc:  # malformed config must never crash a run
        import sys
        print(f"[thresholds] WARNING: ignoring {cfg}: {exc}", file=sys.stderr)
        return {}
    applied = _apply_overrides(globals(), data)
    if applied:
        import sys
        print(f"[thresholds] applied {len(applied)} override(s) from config/thresholds.toml: "
              f"{', '.join(sorted(applied))}", file=sys.stderr)
    return applied


_THRESHOLD_OVERRIDES = _load_threshold_overrides()
