"""KILLSHOT tier — selection, gating, sizing, and fail-fast invariants (Plan 6 §13, v3).

Extracted from run_picks.py (extract-and-re-export refactor, Step 15) and re-imported
there so existing call sites and `from run_picks import ...` keep resolving. The KILLSHOT
Discord embed + poster stay in run_picks (they move to discord_post.py in Step 16, since
they depend on _webhook_post). Imports only {stdlib, thresholds, market_config,
calibrated, quant.odds, pick_log_lock, pick_log_writers, paths} — never run_picks or the
other extracted modules.

`_assert_killshot_invariants()` is invoked at module scope below, so it still fails fast
at import (now: at import of killshot.py).
"""
import csv
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

from thresholds import (
    KILLSHOT_SIZE_BASE, KILLSHOT_SIZE_BUMP, KILLSHOT_BUMP_WIN_PROB, KILLSHOT_BUMP_EDGE,
    KILLSHOT_ODDS_MIN, KILLSHOT_ODDS_MAX, KILLSHOT_WP_MARGIN,
    KILLSHOT_SCORE_FLOOR, KILLSHOT_STAT_ALLOW, KILLSHOT_MANUAL_FLOOR, KILLSHOT_WEEKLY_CAP,
)
from market_config import SUSPENDED_STATS
from calibrated import STAT_FAMILY_TIER
from quant.odds import implied_prob
from pick_log_lock import _pick_log_lock
from pick_log_writers import log_blocked_pick
from paths import PICK_LOG_PATH as _PICK_LOG_PATH_P

PICK_LOG_PATH = str(_PICK_LOG_PATH_P)

logger = logging.getLogger(__name__)


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
    """Count KILLSHOT picks logged in the rolling 7 days (including today).

    Fail SAFE, not just in the except block: an absent pick_log is exactly
    the "can't reliably determine" case the except block below already
    refuses to treat as 0 (R-FS23-03) -- returning 0 here would allow the
    engine to post the full weekly KILLSHOT cap on top of already-posted
    shots the log can't currently prove don't exist.
    """
    log_path = Path(PICK_LOG_PATH)
    if not log_path.exists():
        logger.warning(
            "[KILLSHOT] _killshots_this_week: pick_log not found at %s — "
            "assuming cap full to prevent over-posting", log_path
        )
        return KILLSHOT_WEEKLY_CAP
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
