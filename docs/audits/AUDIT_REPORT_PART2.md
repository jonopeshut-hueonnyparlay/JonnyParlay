# JonnyParlay Audit Report — Part 2

**Focus Files:** `engine/capture_clv.py`, `engine/sgp_builder.py`, `engine/pick_log_schema.py`, `engine/secrets_config.py`

**Date:** 2026-04-24  
**Scope:** Line-by-line audit of new SGP system, CLV daemon integrity, schema v3 migration, and webhook config.

---

## Executive Summary

**Critical Issues Found: 5**  
**High-Priority Issues: 4**  
**Medium Issues: 6**  
**File Sync Status:** `secrets_config.py` OUT OF SYNC (root version incomplete); others in sync.

The SGP builder has several **money-affecting bugs** that will either prevent SGPs from being logged/posted or cause runtime crashes. The CLV daemon and schema are sound. The out-of-sync secrets_config.py will cause an ImportError if the new webhook variables aren't available.

---

## File Sync Status

| File | Engine | Root | Status |
|------|--------|------|--------|
| `sgp_builder.py` | 769 L | 769 L | ✅ IN SYNC |
| `pick_log_schema.py` | 510 L | 510 L | ✅ IN SYNC |
| `capture_clv.py` | 1179 L | 1179 L | ✅ IN SYNC |
| `secrets_config.py` | 161 L | 154 L | ❌ OUT OF SYNC |

Root-level `secrets_config.py` is missing the final 7 lines (`summary()` function body + `if __name__`). This causes the module to be incomplete, potentially breaking any code that imports it.

---

## 1. engine/sgp_builder.py (769 lines)

### Summary
SGP builder is a new module (~769 lines) that constructs 6-leg same-game parlays with prop correlations, posts them to Discord, and logs to pick_log.csv. It has clear structure but **multiple critical bugs in control flow and parameter passing**.

### Critical Issues

#### **CRITICAL-1: Undefined variable `today_str` in `run_sgp_builder()` — Line 750**
**Severity:** CRITICAL (runtime crash)  
**Location:** `sgp_builder.py:750`  
**What it does now:**
```python
ok = post_sgp(legs, parlay_odds, game, suppress_ping=test,
              today_str=today_str, save=save)
```

**Why it's wrong:**  
The variable `today_str` is never defined anywhere in `run_sgp_builder()`. This code path is executed when the user is in `confirm` mode and declines to post an SGP. The code attempts to call `post_sgp()` with `today_str=today_str`, but `today_str` doesn't exist in scope. This will raise `NameError: name 'today_str' is not defined` at runtime.

**Suggested fix:**  
Compute `today_str` at the start of `run_sgp_builder()`:
```python
from datetime import datetime
from zoneinfo import ZoneInfo

def run_sgp_builder(csv_paths, dry_run=False, confirm=False, test=False,
                    cached_odds=None, save=True):
    today_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    # ... rest of function
```

---

#### **CRITICAL-2: Unreachable else block with logic error in `run_sgp_builder()` — Lines 740–754**
**Severity:** CRITICAL (silent loss of SGPs)  
**Location:** `sgp_builder.py:740–754`  
**What it does now:**
```python
if dry_run:
    reason = "--dry-run" if not save else "--no-discord"
    print(f"  [SGP] {reason}: skipping Discord post.")
elif confirm:
    ans = input(f"  [SGP] Post this SGP to #bonus-drops? (y/n): ").strip().lower()
    if ans == "y":
        ok = post_sgp(legs, parlay_odds, game, suppress_ping=test)
        print(f"  [SGP] {'Posted' if ok else 'FAILED'}: {game}")
    else:
        print(f"  [SGP] Skipped: {game}")
        ok = post_sgp(legs, parlay_odds, game, suppress_ping=test,
                      today_str=today_str, save=save)
        print(f"  [SGP] {'Posted' if ok else 'FAILED'}: {game}")
print(f"\n  [SGP] No valid SGPs built for tonight's slate.")
```

**Why it's wrong:**  
1. When user declines to post (`ans != "y"`), the code **still calls `post_sgp()`** with logging enabled. This is backwards logic — if the user said "no", it shouldn't post.
2. The "No valid SGPs" message is **printed unconditionally** inside the `for event in events:` loop, so it prints after every single game, even when SGPs were successfully posted.
3. The first `post_sgp()` call (line 745, when user says yes) does **not pass `today_str`** or `save`, so it defaults to `today_str=None` and `save=True`. This may not log the SGP at all because of the None check in `post_sgp()`.

**Suggested fix:**
```python
if dry_run:
    reason = "--dry-run" if not save else "--no-discord"
    print(f"  [SGP] {reason}: skipping Discord post.")
elif confirm:
    ans = input(f"  [SGP] Post this SGP to #bonus-drops? (y/n): ").strip().lower()
    if ans == "y":
        ok = post_sgp(legs, parlay_odds, game, suppress_ping=test, 
                      today_str=today_str, save=save)
        print(f"  [SGP] {'Posted' if ok else 'FAILED'}: {game}")
    else:
        print(f"  [SGP] Skipped: {game}")
else:  # Normal mode: post without prompting
    ok = post_sgp(legs, parlay_odds, game, suppress_ping=test, 
                  today_str=today_str, save=save)
    print(f"  [SGP] {'Posted' if ok else 'FAILED'}: {game}")
```

And move the "No valid SGPs" message **outside the loop**:
```python
if not results:
    print(f"\n  [SGP] No valid SGPs built for tonight's slate.")
return results
```

---

#### **CRITICAL-3: `post_sgp()` gates logging on `today_str is not None`, but callers don't always pass it — Lines 628–650**
**Severity:** CRITICAL (SGPs not logged)  
**Location:** `sgp_builder.py:628–650`, called from lines 745–750  
**What it does now:**
```python
def post_sgp(legs, parlay_odds, game, suppress_ping=False, today_str=None, save=True):
    # ... post to Discord ...
    if ok and save and today_str:  # <-- GATES on today_str being truthy
        _log_sgp(legs, parlay_odds, game, today_str, book=book)
    return ok
```

When called from line 745 (user confirms post):
```python
ok = post_sgp(legs, parlay_odds, game, suppress_ping=test)  # <-- NO today_str passed!
```

**Why it's wrong:**  
If `today_str` is not passed, it defaults to `None`, so the `if ok and save and today_str:` check fails and `_log_sgp()` is never called. The SGP posts to Discord but never gets logged to pick_log.csv. This breaks grading, CLV capture, and analytics.

**Suggested fix:**  
Pass `today_str` to all `post_sgp()` calls (see CRITICAL-2 fix above), or compute it inside `post_sgp()`:
```python
if today_str is None:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    today_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
```

---

#### **CRITICAL-4: Root `secrets_config.py` is INCOMPLETE — Missing final 7 lines**

**Severity:** CRITICAL (import failure)  
**Location:** `/sessions/festive-busy-cori/mnt/JonnyParlay/secrets_config.py` (root-level file)  
**What it does now:**  
The root file ends abruptly:
```python
def summary() -> str:
    """Return a redacted inventory — useful for debugging missing secrets."""
    def _redact(s: str) -> str:
        if not s:
            return "<not set>"
        return s[:8] + "..." + s[-4:] if len(s) > 16 else "<set>"
    lines = [f"  .env loaded from: {DOTENV_PATH or '<none>'}"]
    lines.append(f"  ODDS_API_KEY:        {_redact(ODDS_API_KEY)}")
    f
```

It cuts off mid-line at `f` (incomplete f-string).

**Why it's wrong:**  
The file is syntactically invalid Python. Any code that imports from `secrets_config.py` will fail with a `SyntaxError`. This breaks:
- `sgp_builder.py` (imports `DISCORD_BONUS_WEBHOOK` at line 23)
- `run_picks.py` (likely imports ODDS_API_KEY and webhook URLs)
- `grade_picks.py` (likely imports webhook URLs)
- `capture_clv.py` (imports `ODDS_API_KEY` at line 77)

**Engine version has:**
```python
def summary() -> str:
    """Return a redacted inventory — useful for debugging missing secrets."""
    def _redact(s: str) -> str:
        if not s:
            return "<not set>"
        return s[:8] + "..." + s[-4:] if len(s) > 16 else "<set>"
    lines = [f"  .env loaded from: {DOTENV_PATH or '<none>'}"]
    lines.append(f"  ODDS_API_KEY:        {_redact(ODDS_API_KEY)}")
    for short, (env_key, url) in _WEBHOOK_REGISTRY.items():
        lines.append(f"  {env_key:28s} {_redact(url)}")
    return "\n".join(lines)


if __name__ == "__main__":
    print("JonnyParlay secrets inventory:\n")
    print(summary())
```

**Suggested fix:**  
Sync root from engine immediately:
```bash
cp engine/secrets_config.py secrets_config.py
```

---

### High-Priority Issues

#### **HIGH-1: `run_sgp_builder()` CLI doesn't pass `save` parameter — Lines 761–769**
**Severity:** HIGH (CLI feature broken)  
**Location:** `sgp_builder.py:761–769`  
**What it does now:**
```python
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JonnyParlay SGP Builder")
    parser.add_argument("csvs", nargs="+", help="SaberSim NBA CSV file(s)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    run_sgp_builder(
        args.csvs,
        dry_run=args.dry_run,
        confirm=args.confirm,
        test=args.test,
    )
```

**Why it's wrong:**  
The CLI call doesn't pass `save=True` (or handle `--no-save`). According to the audit spec (section 63), `save=True` is the **default from CLI** — it should not be exposed as a flag. The code is correct in not accepting it, but it should explicitly pass `save=True` to ensure SGPs are logged.

**Suggested fix:**
```python
run_sgp_builder(
    args.csvs,
    dry_run=args.dry_run,
    confirm=args.confirm,
    test=args.test,
    save=True,  # Always save from CLI
)
```

---

#### **HIGH-2: `_check_parlay_correlations()` is called but never defined — Line 432**
**Severity:** HIGH (runtime NameError)  
**Location:** `sgp_builder.py:432`  
**What it does now:**
```python
if not _check_parlay_correlations(legs):
    continue
```

**Why it's wrong:**  
`_check_parlay_correlations()` is called in `build_sgp()` but is never defined anywhere in the file. This will raise `NameError: name '_check_parlay_correlations' is not defined` at runtime.

Looking through the file, I see:
- `_is_negatively_correlated()` — checks if two legs conflict
- `_correlation_tags()` — returns team-scoped tags
- `_correlation_cohesion()` — measures linkage

But no `_check_parlay_correlations()`. This function should either be implemented or the call should use existing functions.

**Suggested fix:**  
Implement the function (or replace the call with equivalent logic):
```python
def _check_parlay_correlations(legs):
    """Return True if all legs are compatible (no negative correlations)."""
    for a, b in combinations(legs, 2):
        if _is_negatively_correlated(a, b):
            return False
    return True
```

---

#### **HIGH-3: `build_candidate_legs()` filter logic has two contradictory conditions — Lines 363–365**
**Severity:** HIGH (incorrect leg filtering)  
**Location:** `sgp_builder.py:363–365`  
**What it does now:**
```python
if odds > MAX_LEG_ODDS:   # reject anything not juiced enough (e.g. +100, -110 etc.)
    continue
if odds < -300:
    continue
```

**Why it's wrong:**  
- `MAX_LEG_ODDS = -150` (line 34)
- The acceptable range is `[-299, -150]` (strictly: odds in range where odds <= -150 AND odds > -300)
- The comment says "legs must be heavily juiced alt lines (~-150 to -300)" which describes the intended range
- But the second filter `if odds < -300` excludes legs at -300, -350, etc. (correct)
- This creates an acceptable range of `[-299, -150]` — odds must be negative and juiced

This logic is **correct but poorly documented**. The comment is misleading because it says "alt lines" but the range includes moneyline favorites (anything -150 or lower is heavily favored).

**Suggested fix:**  
Clarify the comment:
```python
# Accept legs in the range [-299, -150] (heavily juiced alt lines)
# Reject loose lines (+100, -110) and extreme locks (< -300)
if odds > MAX_LEG_ODDS or odds < -300:
    continue
```

---

#### **HIGH-4: `_log_sgp()` assumes imports will succeed but doesn't validate schema — Lines 529–550**
**Severity:** HIGH (silent failure on import error)  
**Location:** `sgp_builder.py:529–550`  
**What it does now:**
```python
def _log_sgp(legs, parlay_odds, game, today_str, book=""):
    """Append an SGP to pick_log.csv as run_type='sgp'."""
    import csv, json, os
    from pathlib import Path
    try:
        from pick_log_schema import CANONICAL_HEADER
        from run_picks import PICK_LOG_PATH, _pick_log_lock, _normalize_odds, _normalize_size, _write_schema_sidecar
    except ImportError as e:
        print(f"  [SGP] pick_log import failed — not logging: {e}")
        return
```

**Why it's wrong:**  
The function imports from `run_picks.py` (which is 5000+ lines and may have its own import errors). If the import fails silently, the SGP posts to Discord but never gets logged. The error message is vague. If `pick_log_schema`, `run_picks`, or any of their dependencies are broken, users won't know until they check the logs.

**Suggested fix:**  
Log the error more prominently:
```python
except ImportError as e:
    logger.error(f"_log_sgp import failed (SGP will NOT be logged): {e}")
    print(f"  [SGP] ⚠⚠⚠ Import error — SGP NOT LOGGED: {e}")
    return
```

Or ensure the import happens at module load time so failures are immediate.

---

### Medium-Priority Issues

#### **MEDIUM-1: `_generate_thesis()` assumes at least one leg — Line 451**
**Severity:** MEDIUM (potential crash on empty list)  
**Location:** `sgp_builder.py:451–476`  
**What it does now:**
```python
def _generate_thesis(legs):
    teams = [l["team"] for l in legs]
    team_counts = Counter(teams)
    dominant_team, dom_count = team_counts.most_common(1)[0]  # <-- IndexError if teams is empty
```

**Why it's wrong:**  
If `legs` is empty, `team_counts.most_common(1)` returns an empty list, and `[0]` raises `IndexError`. By design, SGPs always have 6 legs, so this shouldn't happen. But defensive programming would guard it.

**Suggested fix:**
```python
if not teams:
    return "Incomplete SGP"
dominant_team, dom_count = team_counts.most_common(1)[0]
```

---

#### **MEDIUM-2: `_sgp_book()` doesn't validate that `legs` is non-empty — Line 481**
**Severity:** MEDIUM (potential crash)  
**Location:** `sgp_builder.py:481–489`  
**What it does now:**
```python
def _sgp_book(legs):
    """Pick the single best book to place the SGP at (most common across legs)."""
    preferred = ["draftkings", "fanduel", "betmgm", "caesars", "pointsbetsus"]
    counts = Counter(leg["book"] for leg in legs)
    modal_book, modal_count = counts.most_common(1)[0]  # <-- IndexError if legs empty
```

**Why it's wrong:**  
If `legs` is empty, `counts.most_common(1)` returns `[]`, and `[0]` raises `IndexError`. By design, this shouldn't happen, but defensive coding would help.

**Suggested fix:**
```python
if not legs:
    return "draftkings"  # fallback
```

---

#### **MEDIUM-3: `fetch_event_props_from_cache()` uses `startswith(event_id)` on cache keys — Lines 286–300**
**Severity:** MEDIUM (potential false matches)  
**Location:** `sgp_builder.py:286–300`  
**What it does now:**
```python
for cache_key, cache_val in cached_data.get("props", {}).items():
    if not cache_key.startswith(event_id):
        continue
```

**Why it's wrong:**  
If two event IDs have a common prefix (e.g., "game123" vs "game1234"), using `startswith()` will cause false matches. This is a subtle bug if event IDs can be prefixes of each other.

**Suggested fix:**
```python
if not cache_key.startswith(event_id + ":"):
    continue
```

Or use a more explicit key format like `f"{event_id}:{market}"`.

---

#### **MEDIUM-4: Logic error in `confirm` mode — "No valid SGPs" prints on every iteration**
**Severity:** MEDIUM (bad UX)  
**Location:** `sgp_builder.py:751`  
**What it does now:**
```python
for event in events:
    # ... build SGP ...
    # ... ask user ...
print(f"\n  [SGP] No valid SGPs built for tonight's slate.")  # <-- Inside loop!
return results
```

**Why it's wrong:**  
The message is printed after the `if/elif/else` block but still inside the `for event in events:` loop. So if there are 10 games, the message prints 10 times. It should only print once after all games are processed.

**Suggested fix:**  
Move outside the loop (see CRITICAL-2 fix above).

---

#### **MEDIUM-5: Circular import risk with `run_picks.py`**
**Severity:** MEDIUM (fragile architecture)  
**Location:** `sgp_builder.py:538–540`  
**What it does now:**
```python
from run_picks import PICK_LOG_PATH, _pick_log_lock, _normalize_odds, _normalize_size, _write_schema_sidecar
```

**Why it's wrong:**  
`run_picks.py` likely imports from `sgp_builder.py` to call `run_sgp_builder()`. This creates a **circular import**. The lazy import inside `_log_sgp()` mitigates it (import only on demand), but it's fragile.

**Suggested fix:**  
Move shared constants/helpers to a new `engine/log_utils.py` module:
- `_normalize_odds()`
- `_normalize_size()`
- `PICK_LOG_PATH`
- `_write_schema_sidecar()`

Then both `run_picks.py` and `sgp_builder.py` can import from `log_utils` without circular dependency.

---

#### **MEDIUM-6: `build_candidate_legs()` doesn't warn when player not found — Line 349**
**Severity:** MEDIUM (silent data loss)  
**Location:** `sgp_builder.py:349–351`  
**What it does now:**
```python
name_key = _normalize_name(player)
proj_data = projections.get(name_key)
if not proj_data or stat not in proj_data["proj"]:
    continue
```

**Why it's wrong:**  
If a player is in the Odds API but not in the SaberSim CSV (name mismatch after normalization), they silently drop out of candidate pool. There's no warning to the user, so they won't know why an expected player isn't in the SGP. This is expected behavior for a mismatch, but a counter or debug output would help.

**Suggested fix:**  
Add a debug log (not a print, since this runs many times):
```python
if not proj_data:
    # player in odds but not in projections — skip silently
    continue
```

---

### Audit Spec Section 63 Checklist — Results:

| Item | Status | Notes |
|------|--------|-------|
| `run_sgp_builder` signature has `save=True` | ✅ PASS | Line 697 |
| `post_sgp` uses `save` correctly to gate `_log_sgp()` | ⚠️ FAIL | Incomplete: doesn't pass `today_str` to first call (line 745) |
| `_log_sgp` writes exactly 28 fields | ✅ PASS | Lines 572–598 construct a 28-field row dict |
| `MIN_LEGS=6, MAX_LEGS=6` | ✅ PASS | Lines 31–32 |
| `MIN_PARLAY_ODDS=400, MAX_PARLAY_ODDS=700` | ✅ PASS | Lines 33–34 |
| `MAX_LEG_ODDS=-150` | ✅ PASS | Line 35 |
| `build_candidate_legs` has both filters | ✅ PASS | Lines 363–365 (though comment misleading) |
| `today_str` passed to both `post_sgp()` call sites | ❌ FAIL | Line 745 doesn't pass it; line 750 tries to use undefined var |
| `_generate_thesis()` is direction-aware | ✅ PASS | Lines 451–476 check over/under direction |
| Root `sgp_builder.py` synced with `engine/` | ✅ PASS | Diff confirms identical |

---

## 2. engine/capture_clv.py (1179 lines)

### Summary
CLV daemon is well-architected. Single-instance guard, ghost-game checkpoint integrity, filelock on all CSV reads/writes, graceful shutdown, and atomic JSON writes. **No critical bugs found.** 

### Notable Positives
- ✅ FileLock used on all `pick_log.csv` access
- ✅ Checkpoint integrity check on startup (ghost-game eviction)
- ✅ Shadow log skipping via `ENABLE_SHADOW_CLV` flag (default False)
- ✅ Atomic JSON checkpoint writes via `atomic_write_json()`
- ✅ Signal handlers for graceful shutdown
- ✅ Daemon lock acquired before signal handlers installed

### Issues Found: None (Sound design, no blocking issues)

---

## 3. engine/pick_log_schema.py (510 lines)

### Summary
Schema module is well-designed. Defines `CANONICAL_HEADER` (28 columns), `SCHEMA_VERSION=3`, migration helpers, and validation. **No bugs found.**

### Audit Spec Section 62 Checklist — Results:

| Item | Status |
|------|--------|
| `SCHEMA_VERSION = 3` | ✅ PASS |
| `CANONICAL_HEADER` has exactly 28 fields | ✅ PASS |
| `_V3_COLUMNS = frozenset(["legs"])` | ✅ PASS |
| Assertions for both v2 and v3 columns present | ✅ PASS |
| Root synced with engine version | ✅ PASS |

---

## 4. engine/secrets_config.py (161 lines engine, 154 lines root)

### Summary
Secrets module exports API keys and webhook URLs. **Root version is incomplete and will cause ImportError.**

### Critical Issues

#### **CRITICAL-4: Root `secrets_config.py` missing final 7 lines — Incomplete file**

**Severity:** CRITICAL (blocks all imports)  
**Status:** OUT OF SYNC  
**Action:** Sync immediately

---

## Summary of All Findings

| Severity | Count | Files |
|----------|-------|-------|
| **CRITICAL** | 5 | sgp_builder (4), secrets_config (1) |
| **HIGH** | 4 | sgp_builder (4) |
| **MEDIUM** | 6 | sgp_builder (6) |
| **LOW** | 0 | — |

### Blocking Issues (Must Fix Before Production):
1. **Sync root `secrets_config.py`** — currently incomplete (missing 7 lines)
2. **Fix `today_str` undefined in `run_sgp_builder()`** — Line 750 crash
3. **Fix logic in `confirm` mode** — Line 745 doesn't pass params, line 751 message duplicates
4. **Implement `_check_parlay_correlations()`** — Line 432 NameError
5. **Fix `post_sgp()` logging gate** — today_str not passed or validated

### Recommended Action Plan:
1. Sync secrets_config.py immediately (`cp engine/secrets_config.py secrets_config.py`)
2. Fix CRITICAL-1, CRITICAL-2, CRITICAL-3 in sgp_builder.py
3. Implement `_check_parlay_correlations()` function
4. Add defensive checks for empty lists in `_generate_thesis()` and `_sgp_book()`
5. Document webhook env vars in `.env.example`
6. Consider refactoring to extract shared logging functions to `log_utils.py`

---

**Audit completed:** 2026-04-24  
**Files audited:** 4 (capture_clv, sgp_builder, pick_log_schema, secrets_config)  
**Status:** Ready for triage
