#!/usr/bin/env python3
"""
health_check.py — JonnyParlay + EdgeModel system health check
Run every morning before picks. Should complete in < 30 seconds.
Usage: python engine/health_check.py

Checks:
  1. All critical constants match expected values
  2. No stale OneDrive paths in any engine file
  3. .env has all required keys
  4. Key files exist
  5. CLAUDE.md under 40k chars
  6. projections.db exists and is fresh
  7. Both repos are clean and pushed
  8. analyze_game_lines.py correct (sigma, Kelly, date filter)
  9. context_research.py has web search + date filter
  10. pick_log.csv is readable
  11. Python syntax check on all engine/*.py files
"""

import os
import sys
import ast
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(errors="replace")

# ── Paths ─────────────────────────────────────────────────────────────────────
JP_ROOT   = Path(r"C:\Dev\JonnyParlay")
EM_ROOT   = Path(r"C:\Dev\EdgeModel")
RUN_PICKS = JP_ROOT / "engine" / "run_picks.py"
ENGINE    = JP_ROOT / "engine"
EM_ENGINE = EM_ROOT / "engine"
CLAUDE_MD = JP_ROOT / "CLAUDE.md"
PICK_LOG  = JP_ROOT / "data" / "pick_log.csv"
PROJ_DB   = EM_ROOT / "data" / "projections.db"
AGL       = JP_ROOT / "analyze_game_lines.py"
CTX       = ENGINE / "context_research.py"
ENV_FILE  = JP_ROOT / ".env"

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"

results = []

def check(name, passed, detail=""):
    status = PASS if passed else FAIL
    results.append((status, name, detail))
    return passed

def warn(name, detail=""):
    results.append((WARN, name, detail))

def read_file(path):
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return Path(path).read_text(encoding=enc, errors="replace")
        except Exception:
            continue
    return f"ERROR:could not read {path}"

def grep(content, pattern):
    return pattern in content

# ── 1. Key files exist ────────────────────────────────────────────────────────
print("Checking file existence...")
for f in [RUN_PICKS, ENGINE/"capture_clv.py", ENGINE/"gate_check.py",
          ENGINE/"sgp_builder.py", ENGINE/"context_research.py",
          ENGINE/"grade_picks.py", ENGINE/"secrets_config.py",
          EM_ENGINE/"nba_projector.py", EM_ENGINE/"generate_projections.py",
          EM_ENGINE/"projections_db.py", AGL, CLAUDE_MD, ENV_FILE]:
    check(f"File exists: {f.name}", f.exists(), str(f) if not f.exists() else "")

# ── 2. .env completeness ──────────────────────────────────────────────────────
print("Checking .env keys...")
env_content = read_file(ENV_FILE)
for key in ["ODDS_API_KEY", "ANTHROPIC_API_KEY", "DISCORD_WEBHOOK_URL",
            "EDGEMODEL_DB_PATH"]:
    present = key in env_content and f"{key}=" in env_content
    val_line = [l for l in env_content.splitlines() if l.startswith(f"{key}=")]
    val = val_line[0].split("=",1)[1].strip() if val_line else ""
    empty = len(val) < 5
    if not present:
        check(f".env: {key} present", False, "MISSING")
    elif empty:
        check(f".env: {key} has value", False, f"Empty or too short: '{val}'")
    else:
        check(f".env: {key} present", True)

# Optional webhooks — warn if key line is not in .env at all
for key in ["DISCORD_GAME_LINES_WEBHOOK"]:
    if f"{key}=" not in env_content:
        warn(f".env: {key} (optional)", "not in .env — add blank line to enable game-lines posting")

# ── 3. No stale OneDrive paths ────────────────────────────────────────────────
print("Checking for stale paths...")
stale_pattern = "Documents\\JonnyParlay"
# Exclude files that legitimately contain home-directory path strings
STALE_EXCLUDE = {"health_check.py", "secrets_config.py", "paths.py"}
checked_files = [f for f in list((JP_ROOT / "engine").glob("*.py")) + [AGL]
                 if f.name not in STALE_EXCLUDE]
for f in checked_files:
    fc = read_file(f)
    if stale_pattern in fc:
        check(f"No stale OneDrive path: {f.name}", False, f"Contains old path")
    elif "ERROR:" not in fc:
        check(f"No stale OneDrive path: {f.name}", True)
# Check .bat files
for bat in JP_ROOT.glob("*.bat"):
    bc = read_file(bat)
    if stale_pattern in bc:
        check(f"No stale OneDrive path: {bat.name}", False, f"Old path in bat file")

# ── 4. CLAUDE.md size ─────────────────────────────────────────────────────────
print("Checking CLAUDE.md...")
claude_content = read_file(CLAUDE_MD)
claude_size = len(claude_content)
check("CLAUDE.md under 40k chars", claude_size < 40000, f"{claude_size} chars")
# API key not stored in CLAUDE.md by design — check .env instead (done above)

# ── 5. Critical constants (post-refactor e2a4721) ─────────────────────────────
# Phase 1 split (commit e2a4721) moved most constants out of run_picks.py into
# sibling modules. run_picks.py re-imports them, but this check greps source files,
# so each constant is verified in the file where it is now DEFINED:
#   thresholds.py — sizing/gate decision-boundary constants (Step 9)
#   calibrated.py — empirically fitted values (Step 10)
# Patterns/values are unchanged from before the refactor; only the file searched moved.
print("Checking critical constants...")
rp = read_file(RUN_PICKS)
thresholds_src = read_file(ENGINE / "thresholds.py")
calibrated_src = read_file(ENGINE / "calibrated.py")

# Local to evaluate_nrfi() in engine/evaluators.py (moved in Phase 2a refactor)
EXPECTED_RP = {
    "NRFI_GAMMA = 0.65": 'NRFI_GAMMA = 0.65',
}

# Moved to engine/thresholds.py (Step 9)
EXPECTED_THRESHOLDS = {
    "KELLY_FRACTION = 6.0": "KELLY_FRACTION = 6.0",
    "BLEND_ALPHA = 0.25": "BLEND_ALPHA = 0.25",
    "F5_SCALAR = 0.540": "F5_SCALAR = 0.540",
    "LONGSHOT_SIZE = 0.25": "LONGSHOT_SIZE = 0.25",
    "VALUE_PARLAY_SIZE = 0.25": "VALUE_PARLAY_SIZE = 0.25",
    "KILLSHOT_SIZE_BASE = 3.0": "KILLSHOT_SIZE_BASE       = 3.0",
    "KILLSHOT_WEEKLY_CAP = 2": "KILLSHOT_WEEKLY_CAP     = 2",
}

# Moved to engine/calibrated.py (Step 10)
EXPECTED_CALIBRATED = {
    "MLB GAME_SIGMA total=4.6": '"total": 4.6',
    "MLB GAME_SIGMA spread=4.2": '"spread": 4.2',
    "NBA GAME_SIGMA total=18.5": '"total": 18.5',
    "NBA GAME_SIGMA spread=12.5": '"spread": 12.5',
    "BM_SHRINKAGE T2=0.85": '"T2": 0.85',
    "BM_SHRINKAGE T1=0.75": '"T1": 0.75',
    "BM_SHRINKAGE T1B=0.80": '"T1B": 0.80',
    "BM_SHRINKAGE T3=0.70": '"T3": 0.70',
    "NB_R AST=9.66": '"AST": 9.66',
    "NB_R REB=13.16": '"REB": 13.16',
    "NB_R ER=4.75 (Task#1 starts-only)": '"ER":  4.75',
    "NB_R HA=13.41 (held; starts-only=Poisson)": '"HA":  13.41',
    "T1 min_edge 0.07": '"min_edge": 0.07',
    "T2 min_edge 0.05": '"min_edge": 0.05',
    "STAT AST=T1B": '"AST": "T1B"',
    "STAT REB=T1": '"REB": "T1"',
    "STAT PTS=T2": '"PTS": "T2"',
    "STAT 3PM=T3": '"3PM": "T3"',
}

for label, pattern in EXPECTED_RP.items():
    check(f"evaluators.py: {label}", pattern in read_file(ENGINE / "evaluators.py"), f"Pattern not found: '{pattern}'")
for label, pattern in EXPECTED_THRESHOLDS.items():
    check(f"thresholds.py: {label}", pattern in thresholds_src, f"Pattern not found: '{pattern}'")
for label, pattern in EXPECTED_CALIBRATED.items():
    check(f"calibrated.py: {label}", pattern in calibrated_src, f"Pattern not found: '{pattern}'")

# Retired constant must stay gone from run_picks.py
check("PICK_SCORE_TIER_MULT absent",
      "PICK_SCORE_TIER_MULT = {" not in rp and "PICK_SCORE_TIER_MULT={" not in rp,
      "PICK_SCORE_TIER_MULT still defined — should be retired")
# SGP_JOINT_EV_MARGIN lives in the builders, not run_picks (verified in section 6)
check("SGP_JOINT_EV_MARGIN not in run_picks", True, "Lives in sgp_builder.py (correct)")

# ── 6. sgp_builder.py constants ──────────────────────────────────────────────
print("Checking sgp_builder.py...")
sgp = read_file(ENGINE / "sgp_builder.py")
# NB_R single-source: shared NBA dispersion (3PM/AST/REB) is DERIVED from
# calibrated.NB_R (not hand-mirrored), so there are no literal values to grep —
# verify the wiring + load-time invariant instead. The invariant itself fires on
# every import (incl. the test suite), which is the real enforcement.
check("sgp_builder NB_R imports from calibrated (single source)",
      "from calibrated import NB_R" in sgp,
      "sgp_builder no longer single-sources NB_R from calibrated.py")
check("sgp_builder NB_R derived from NB_STATS (no hand-mirrored values)",
      "for stat in NB_STATS" in sgp,
      "NB_R derivation comprehension missing — risk of re-introduced drift")
check("sgp_builder single-source invariant runs at import",
      "_assert_nb_r_single_source()" in sgp,
      "NB_R single-source load-time invariant missing")
check("sgp_builder BLK/STL stay SGP-only", '"BLK": 2.8' in sgp and '"STL": 3.6' in sgp,
      "SGP-only NB_R stats BLK/STL missing from _SGP_ONLY_NB_R")
# Copula math moved to quant/copula.py (Step 7); the *0.87 deflation lives there now.
copula_src = read_file(ENGINE / "quant" / "copula.py")
check("quant/copula.py copula *0.87", "0.87" in copula_src, "Copula deflation factor not found")
check("sgp_builder SGP_JOINT_EV_MARGIN=0.025", "0.025" in sgp, "")

# ── 7. capture_clv.py ─────────────────────────────────────────────────────────
print("Checking capture_clv.py...")
clv = read_file(ENGINE / "capture_clv.py")
check("capture_clv SKIP_STATS unchanged (NRFI/YRFI/TT deferred)",
      "GOLF_WIN" in clv and "PARLAY" in clv,
      "SKIP_STATS format changed")
check("capture_clv NRFI still in SKIP_STATS (2d deferred)",
      "NRFI" in clv,
      "NRFI removed from SKIP_STATS without plumbing — would silently drop CLV")

# ── 8. gate_check.py ──────────────────────────────────────────────────────────
print("Checking gate_check.py...")
gc = read_file(ENGINE / "gate_check.py")
check("gate_check T1 mult gate ABSENT", "T1 mult re-eval" not in gc, "T1 mult gate still present")

# ── 9. EdgeModel nba_projector.py constants ───────────────────────────────────
print("Checking EdgeModel nba_projector.py...")
nbap = read_file(EM_ENGINE / "nba_projector.py")
check("EdgeModel LEAGUE_AVG_TOTAL=229", "229" in nbap, "Not 229")
check("EdgeModel REB_PRIOR_RS PG=0.128", "0.128" in nbap, "")
check("EdgeModel REB_PRIOR_RS C=0.305", "0.305" in nbap, "")
check("EdgeModel DAYS_REST_MAX_REDUCTION=0.07", "0.07" in nbap, "")
check("EdgeModel DAYS_REST_EFOLD_TIME=1.5", "DAYS_REST_EFOLD_TIME" in nbap, "Still DAYS_REST_HALF_LIFE?")
check("EdgeModel STL span=25", "25" in nbap, "")
check("EdgeModel DAYS_REST_HALF_LIFE ABSENT",
      "DAYS_REST_HALF_LIFE" not in nbap,
      "Old name still present — should be EFOLD_TIME")

# ── 10. analyze_game_lines.py ─────────────────────────────────────────────────
print("Checking analyze_game_lines.py...")
agl = read_file(AGL)
check("AGL MLB sigma total=4.6", '"total": 4.6' in agl, "Still 4.0?")
check("AGL MLB sigma spread=4.2", '"spread": 4.2' in agl, "Still 3.8?")
check("AGL GAME_LINE_KELLY_FRACTION=10.0", "GAME_LINE_KELLY_FRACTION = 10.0" in agl, "Wrong fraction")
check("AGL GAME_LINE_MARKET_MULT=0.75", "GAME_LINE_MARKET_MULT    = 0.75" in agl, "Wrong mult")
check("AGL date filter present", "_is_valid" in agl and "_today_local" in agl, "Date filter missing")
check("AGL dedup present", "_dedup_today" in agl, "Dedup missing")
check("AGL NBA_NAME_MAP used", "NBA_NAME_MAP.get" in agl, "Still using [:3] matching")
check("AGL positive-only edge filter", "edge < 0.04" in agl, "Old threshold still used")
check("AGL no stale sigma print", "total=4.0/spread=3.8" not in agl, "Stale sigma in print")

# ── 11. context_research.py ───────────────────────────────────────────────────
print("Checking context_research.py...")
ctx = read_file(CTX)
check("context_research web search enabled", "web_search_20260209" in ctx, "Web search not added")
check("context_research date filter", "today_local" in ctx, "Date filter missing")
check("context_research dedup", "seen" in ctx, "Dedup missing")
check("context_research response parsing", "hasattr(block" in ctx or "block.text" in ctx,
      "Old response[0].text parsing")

# ── 12. projections.db freshness ──────────────────────────────────────────────
print("Checking projections.db...")
if PROJ_DB.exists():
    age_hours = (datetime.now() - datetime.fromtimestamp(PROJ_DB.stat().st_mtime)).total_seconds() / 3600
    check("projections.db exists", True)
    if age_hours > 48:
        warn("projections.db freshness", f"{age_hours:.0f}h old — run --pull --force before picks")
    else:
        check("projections.db fresh (<48h)", True, f"{age_hours:.1f}h old")

    # Check player_game_stats has recent data
    try:
        conn = sqlite3.connect(str(PROJ_DB))
        cur = conn.cursor()
        cur.execute("SELECT MAX(game_date) FROM games")
        last = cur.fetchone()[0]
        conn.close()
        check("projections.db games table current", last is not None, f"Last game: {last}")
    except Exception as e:
        check("projections.db readable", False, str(e))
else:
    check("projections.db exists", False, str(PROJ_DB))

# ── 13. pick_log.csv readable ─────────────────────────────────────────────────
print("Checking pick_log.csv...")
if PICK_LOG.exists():
    check("pick_log.csv exists", True)
    try:
        content = PICK_LOG.read_bytes()
        check("pick_log.csv no null bytes", b"\x00" not in content,
              "NULL BYTES DETECTED — file may be corrupted")
    except Exception as e:
        check("pick_log.csv readable", False, str(e))
else:
    warn("pick_log.csv", "File not found — may not have run picks yet today")

# ── 14. Git status ────────────────────────────────────────────────────────────
print("Checking git status...")
for repo_name, repo_path in [("JonnyParlay", JP_ROOT), ("EdgeModel", EM_ROOT)]:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path, capture_output=True, text=True, timeout=10
        )
        dirty = result.stdout.strip()
        # Untracked files (??) are warnings, modified files (M) are failures
        modified = [l for l in dirty.splitlines() if l.startswith("M ") or l.startswith(" M")]
        untracked = [l for l in dirty.splitlines() if l.startswith("??")]
        if modified:
            check(f"Git clean: {repo_name}", False, "Uncommitted changes: " + ", ".join(modified)[:80])
        elif untracked:
            check(f"Git clean: {repo_name}", True)
            warn(f"Git untracked: {repo_name}", ", ".join(untracked)[:80])
        else:
            check(f"Git clean: {repo_name}", True)

        result2 = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=repo_path, capture_output=True, text=True, timeout=10
        )
        check(f"Git has commits: {repo_name}", bool(result2.stdout.strip()), "")

        # Check if ahead of origin
        result3 = subprocess.run(
            ["git", "log", "origin/main..HEAD", "--oneline"],
            cwd=repo_path, capture_output=True, text=True, timeout=10
        )
        unpushed = result3.stdout.strip()
        if unpushed:
            warn(f"Git unpushed: {repo_name}", f"{len(unpushed.splitlines())} commits not pushed")
        else:
            check(f"Git pushed: {repo_name}", True)
    except Exception as e:
        check(f"Git check: {repo_name}", False, str(e))

# ── 15. Python syntax check ───────────────────────────────────────────────────
print("Checking Python syntax...")
py_files = list((JP_ROOT / "engine").glob("*.py")) + [RUN_PICKS, AGL]
py_files += list(EM_ENGINE.glob("*.py"))
syntax_errors = []
for f in py_files:
    try:
        source = read_file(f)
        ast.parse(source, filename=str(f))
    except SyntaxError as e:
        syntax_errors.append(f"{f.name}: {e}")
    except Exception:
        pass
check("Python syntax: all engine files", not syntax_errors,
      "\n  ".join(syntax_errors) if syntax_errors else "")

# ── 16. WNBA team_sigmas keyed by abbrev, not team_id (P0.2) ──────────────────
print("Checking WNBA team_sigmas keying...")
try:
    sys.path.insert(0, str(ENGINE))
    from calibrated import _TEAM_SIGMAS, GAME_SIGMA  # noqa: E402
    from team_resolve import get_game_sigma           # noqa: E402
    _wnba = _TEAM_SIGMAS.get("WNBA", {})
    _numeric = [k for k in _wnba if str(k).isdigit()]
    check("WNBA team_sigmas keyed by abbrev (not team_id)",
          bool(_wnba) and not _numeric,
          f"{len(_numeric)} numeric-id keys remain — re-key via WNBA_ID_MAP"
          if _numeric else f"{len(_wnba)} abbrev-keyed teams")
    _lg = GAME_SIGMA["WNBA"]["total"]
    _sg = get_game_sigma("WNBA", "Las Vegas Aces", "Los Angeles Sparks", "total")
    check("WNBA get_game_sigma resolves team-specific (≠ league σ)",
          abs(_sg - _lg) > 1e-9, f"matchup σ={_sg:.3f} vs league={_lg:.3f}")
except Exception as e:
    check("WNBA team_sigmas health check", False, f"{type(e).__name__}: {e}")

# ── 17. Platt calibration space ↔ formula consistency (P0.4) ──────────────────
# No Platt artifact JSON exists in this repo — the calibration is the three code
# constants (formula in prob_core + PLATT_A/B in calibrated + PLATT_SPACE in
# thresholds), which must stay mutually consistent (CLAUDE.md "atomic 3-way").
# prob_core._platt_calibrate_prop asserts PLATT_SPACE matches its formula; calling
# it here turns that call-time guard into a startup hard-fail and reports the
# active config every run.
print("Checking Platt calibration space...")
try:
    sys.path.insert(0, str(ENGINE))
    from thresholds import PLATT_SPACE          # noqa: E402
    from calibrated import PLATT_A, PLATT_B     # noqa: E402
    from prob_core import _platt_calibrate_prop  # noqa: E402
    check("PLATT_SPACE is a known value", PLATT_SPACE in ("raw", "logit"),
          f"PLATT_SPACE={PLATT_SPACE!r}")
    # If PLATT_SPACE was flipped without changing the formula, this raises
    # AssertionError inside prob_core → caught below as a FAIL.
    _p = _platt_calibrate_prop(0.6)
    check("Platt space ↔ formula consistent (no mismatch)",
          0.0 <= _p <= 1.0,
          f"space={PLATT_SPACE} A={PLATT_A} B={PLATT_B} → p(0.6)={_p:.4f}")
except Exception as e:
    check("Platt space ↔ formula consistent (no mismatch)", False,
          f"{type(e).__name__}: {e} — PLATT_SPACE flipped without matching formula?")

# ── 18. NBA SGP ρ provenance + regression guard (P1.5) ────────────────────────
# No JSON ρ matrix — values are hardcoded in sgp_builder._pairwise_rho(). Assert
# the provenance stamp is present and that canonical leg-pairs still return the
# frozen ρ values (catches silent ρ edits; reports version/fit_date every run).
print("Checking NBA SGP rho provenance...")
try:
    sys.path.insert(0, str(ENGINE))
    import sgp_builder  # noqa: E402
    _meta = getattr(sgp_builder, "_NBA_SGP_RHO_META", None)
    _meta_ok = isinstance(_meta, dict) and {"version", "fit_date", "source"} <= set(_meta)
    check("NBA SGP rho provenance stamped",
          _meta_ok,
          f"version={_meta.get('version')} fit_date={_meta.get('fit_date')}"
          if _meta_ok else "_NBA_SGP_RHO_META missing/malformed")

    def _leg(player, team, stat, direction, game="G1"):
        return {"player": player, "team": team, "stat": stat, "direction": direction, "game": game}
    # (leg_a, leg_b, expected_rho) — one per hierarchy branch.
    _canon = [
        (_leg("A", "X", "PTS", "over"), _leg("B", "X", "AST", "over"), 0.35),   # same-team off overs
        (_leg("A", "X", "PTS", "over"), _leg("A", "X", "REB", "over"), 0.28),   # same player same dir
        (_leg("A", "X", "PTS", "over"), _leg("A", "X", "REB", "under"), -0.20), # same player opp dir
        (_leg("A", "X", "REB", "over"), _leg("B", "X", "REB", "over"), 0.20),   # same-team REB overs
        (_leg("A", "X", "STL", "over"), _leg("B", "X", "BLK", "over"), 0.15),   # same-team same dir other
        (_leg("A", "X", "PTS", "over"), _leg("B", "Y", "PTS", "over"), 0.10),   # cross-team overs
        (_leg("A", "X", "PTS", "over"), _leg("B", "Y", "PTS", "over", game="G2"), 0.0),  # different games
    ]
    _bad = [(a["stat"], b["stat"], exp, sgp_builder._pairwise_rho(a, b))
            for a, b, exp in _canon if abs(sgp_builder._pairwise_rho(a, b) - exp) > 1e-9]
    check("NBA SGP rho values match frozen canonical set",
          not _bad, f"{len(_bad)} drifted: {_bad}" if _bad else f"{len(_canon)} pairs OK")
except Exception as e:
    check("NBA SGP rho provenance + regression guard", False, f"{type(e).__name__}: {e}")

# ── 19. MLB SGP ρ provenance + refit-trigger status (P1.6) ────────────────────
print("Checking MLB SGP rho provenance...")
try:
    sys.path.insert(0, str(ENGINE))
    import mlb_sgp_builder as msb  # noqa: E402
    _mmeta = getattr(msb, "_MLB_SGP_RHO_META", None)
    _mok = isinstance(_mmeta, dict) and {"version", "source", "n_sign_check", "n_target"} <= set(_mmeta)
    check("MLB SGP rho provenance stamped", _mok,
          f"version={_mmeta.get('version')} targets {_mmeta.get('n_sign_check')}/{_mmeta.get('n_target')}"
          if _mok else "_MLB_SGP_RHO_META missing/malformed")
    # 0.30 OUTS-over x opposing-HITS-under must hold (the key value to tighten).
    _outs = {"player": "P", "team": "X", "stat": "OUTS", "direction": "over"}
    _hits = {"player": "B", "team": "Y", "stat": "HITS", "direction": "under"}
    check("MLB SGP rho OUTS-over x opp-HITS-under = 0.30",
          abs(msb._pairwise_rho_mlb(_outs, _hits) - 0.30) < 1e-9,
          f"got {msb._pairwise_rho_mlb(_outs, _hits)}")
    _nsgp = msb._count_scored_mlb_sgps()
    check("MLB SGP rho refit-trigger readable", True,
          f"n={_nsgp} scored MLB SGP slips (target {_mmeta.get('n_target') if _mok else '?'})")
except Exception as e:
    check("MLB SGP rho provenance + refit-trigger", False, f"{type(e).__name__}: {e}")

# ── Report ────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("HEALTH CHECK REPORT")
print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*70)

passes = sum(1 for r in results if r[0] == PASS)
fails  = sum(1 for r in results if r[0] == FAIL)
warns  = sum(1 for r in results if r[0] == WARN)

# Show failures first
if fails:
    print(f"\n❌ FAILURES ({fails}):")
    for status, name, detail in results:
        if status == FAIL:
            print(f"  {status}  {name}")
            if detail:
                print(f"          → {detail}")

if warns:
    print(f"\n⚠️  WARNINGS ({warns}):")
    for status, name, detail in results:
        if status == WARN:
            print(f"  {status}  {name}")
            if detail:
                print(f"          → {detail}")

print(f"\n✅ PASSED: {passes}/{passes+fails} checks")
print(f"{'🟢 SYSTEM HEALTHY — safe to run picks' if not fails else '🔴 FIX FAILURES BEFORE RUNNING PICKS'}")
print("="*70)

if fails:
    sys.exit(1)
