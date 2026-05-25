# Audit 2026-05-25 — Track K: Operational Safety

Auditor: Claude Sonnet 4.6 (automated)
Scope: engine/run_picks.py, engine/capture_clv.py, engine/grade_picks.py, start_clv_daemon.bat, .gitignore

---

## K1. Concurrent Run Safety

### filelock coverage — COMPLETE AND CORRECT

All write paths use `_pick_log_lock(log_path)` (a contextmanager wrapping FileLock):
- `log_picks()` (~line 3964) ✓
- `_log_bonus_pick()` (~line 5110) ✓
- `log_daily_lay_pick()` (~line 4671) ✓
- `log_longshot_pick()` (~line 4853) ✓
- `_units_bet_today()` (~line 4958) — read also locked ✓
- `_get_recent_losses()` (~line 1134) ✓
- `sgp_builder._log_sgp()` (~line 1011) — imports _pick_log_lock from run_picks ✓
- `capture_clv.write_closing_odds()` (~line 641) — separate FileLock, atomic os.replace ✓

`filelock` is a hard import (no silent fallback — `ImportError` raised on missing package). **No file corruption risk from concurrent writes.**

### Process-level lock
`run_picks.lock` acquired with `timeout=0` at startup (~line 5748). A second simultaneous `run_picks.py` process exits immediately. **No concurrent runs possible.**

### Discord guard atomicity
`discord_guard.py` uses `FileLock(LOCK_FILE, timeout=30)` on every `load_guard`, `save_guard`, `claim_post`, `mark_posted`, `release_post`. Fallback on `_FileLockTimeout` logs a warning and continues — known duplicate-post risk on lock timeout, documented in code.

### K-1 (LOW) — process lock not explicitly released on crash

```
TRACK: K
FILE: engine/run_picks.py
LINE: ~5748
SEVERITY: LOW
N: N/A
ISSUE: run_picks.lock is never explicitly released — relies on Python GC/process exit.
On non-graceful crash (SIGKILL), the lock file persists. filelock handles stale locks
via PID detection on the next run (Windows-compatible).
IMPACT: Minimal. filelock stale-detection handles this correctly.
FIX: None required.
```

---

## K2. Stale Odds / Cache Safety

### K-2 (MEDIUM) — Cache TTL is 15 minutes (CLAUDE.md says 11 minutes — MISMATCH)

```
TRACK: K
FILE: engine/run_picks.py
LINE: ~1686
SEVERITY: MEDIUM
N: N/A
ISSUE: Cache TTL in code = 15 minutes. CLAUDE.md says "11-minute Odds API cache."
Documentation mismatch. A 15-minute stale line can move 5–10 cents on a fast-moving prop
(~3–4pp implied probability). For a 3% edge pick, this can flip it from +EV to -EV before
the user bets. No staleness check at bet-finalization time — once picks are evaluated and
posted to Discord, odds are not re-fetched.
IMPACT: Post-cache line movements are not detected. Risk is proportional to market speed.
FIX: Update CLAUDE.md: "15-minute Odds API cache." Consider adding staleness warning when
cache age > 10 minutes. On --late-run, consider tightening TTL to 5 minutes.
```

### K-3 (MEDIUM) — Cache open() calls missing encoding="utf-8"

```
TRACK: K
FILE: engine/run_picks.py
LINE: ~1695 (read), ~1711 (write)
SEVERITY: MEDIUM
N: N/A
ISSUE: open(cache_file, "r") and open(cache_file, "w") lack encoding="utf-8". On Windows
with non-UTF-8 system locale, player names with non-ASCII characters (accented letters
like é, ü) could be mangled in the JSON cache. A UnicodeDecodeError fallback triggers
a re-fetch (benign), but a partial mangle that still parses could produce garbled player
names → missed prop matches with no error.
Also affects the dry-run output file open(dp, "w") at ~line 5917.
IMPACT: Low on Jono's machine (PYTHONIOENCODING=utf-8 in .bat file). Defensive fix for
robustness.
FIX: Add encoding="utf-8" to both cache open() calls (~1695, ~1711) and dry-run write (~5917).
3 one-line changes.
```

### --no-cache coverage

`--no-cache` passes `no_cache=True` to `fetch_all()` which skips `_load_cache()` for ALL sports. Full coverage — not props-only. ✓

---

## K3. Security

### .env gitignored — CONFIRMED ✓
`.gitignore` line 51: `.env` pattern. Verified via `git check-ignore -v .env`.

### No API keys in logs or pick_log — CONFIRMED ✓
`secrets_config.py:summary()` redacts all values (first 8 + last 4 chars). No debug prints of raw credentials found in any engine file.

### No hardcoded credentials — CONFIRMED ✓
All secrets load from environment/.env via `secrets_config.py`. No hardcoded API keys or webhook URLs in engine files.

### Exception handlers — CONFIRMED SAFE ✓
`OddsFetcher._get()` appends `ODDS_API_KEY` to request params but only logs HTTP status code on error — never the URL with key.

---

## K4. Invalid / Extreme Inputs

### K-4 (LOW) — No guard on extreme odds values (abs(odds) > 10000)

```
TRACK: K
FILE: engine/run_picks.py
LINE: ~1945, ~2015, ~2073, ~2103, ~2173, ~2287 (odds extraction sites)
SEVERITY: LOW
N: N/A
ISSUE: odds==0 is guarded at all extraction sites. is_decimal_leak(odds) catches decimal
format leakage. But abs(odds) > 10000 is not explicitly capped. implied_prob(99999) = 0.001
(well-behaved), but such a value would produce near-zero edge and be filtered before the card.
IMPACT: Functional impact is benign — extreme odds pass through but are filtered by edge gates.
FIX: Low priority. Could add: `if abs(odds) > 5000: continue` as a sanity guard.
```

### K-5 (LOW) — NaN projections silently dropped (no warning)

```
TRACK: K
FILE: engine/run_picks.py
LINE: ~2203, ~2225
SEVERITY: LOW
N: N/A
ISSUE: float("nan" or 0) = float("nan") = nan (not 0.0). The `if proj_val > 0:` guard at
~2203 correctly rejects NaN (Python: nan > 0 is False), so NaN projections are silently
dropped before evaluation. No warning is logged.
IMPACT: Silent drop of NaN projections. Only occurs with malformed SaberSim CSV.
FIX: Optional: add `if math.isnan(proj_val): logger.warning(f"NaN proj for {player}")`.
```

### K-6 (LOW) — CSV column misalignment passes silently

```
TRACK: K
FILE: engine/run_picks.py
LINE: ~1558–1634
SEVERITY: LOW
N: N/A
ISSUE: csv.DictReader maps misaligned values to wrong fields silently — no column-count
validation. A row where PTS appears in the AST column passes float() successfully and
produces a wrong projection with no error.
IMPACT: Very low — SaberSim CSVs are machine-generated and column-stable.
FIX: Validate required headers at load time: assert set(REQUIRED_COLS).issubset(reader.fieldnames).
```

### No extreme win_prob guards — LOW RISK
Platt clamps logit input to [-30, 30] ensuring output in (0,1). Confidence scalar pulls extremes toward 0.5. Minimum edge gates further filter. No guard strictly needed but a clamp would be defensive. ✓

---

## K5. Windows-Specific Issues

### File paths — ALL use pathlib.Path ✓
No hardcoded backslashes found. All path resolution goes through `paths.py` using `Path` objects.

### start_clv_daemon.bat — ASCII-only CONFIRMED ✓
Full review: no non-ASCII characters. All text is standard 7-bit ASCII. `PYTHONIOENCODING=utf-8` set before any Python invocation.

### K-3 (MEDIUM) — see above — cache file encoding
Three `open()` calls without `encoding="utf-8"`: cache read (~1695), cache write (~1711), dry-run write (~5917).

---

## K6. Error Recovery

### Mid-run crash recovery — CORRECT
Pick dedup key (date+player+stat+line+direction) on re-run correctly skips already-logged picks and appends only remaining ones. Forward-recoverable state. ✓

### K-7 (LOW) — Append path has no atomic crash protection

```
TRACK: K
FILE: engine/run_picks.py
LINE: ~4029
SEVERITY: LOW
N: N/A
ISSUE: The non-header-rewrite append path uses open(log_path, "a") inside the lock.
A crash mid-writerow() could leave a partial CSV line which csv.DictReader would skip
or misparse on next read. The header-rewrite path uses atomic tmp → os.replace, protecting
against truncation during schema migration. The append path does not have this protection.
IMPACT: Very low probability — crash must occur at the exact moment of a CSV write.
FIX: Acceptable risk. Document as known limitation of append mode.
```

### Re-run guard — CORRECT ✓
`_card_already_posted_today()` + Discord guard file prevents duplicate posts on same-day re-run. Two-layer protection.

### grade_picks with no picks — CORRECT ✓
`post_grading_results()` returns immediately if `not day_picks`. `process_log()` returns `(False, set())` if `not ungraded`. Clean silent exit.

---

## Summary

| ID | Severity | Finding |
|----|----------|---------|
| K-2 | MEDIUM | Cache TTL 15min (CLAUDE.md says 11min); no post-evaluation freshness check |
| K-3 | MEDIUM | Three open() calls without encoding="utf-8" (cache read, cache write, dry-run write) |
| K-1 | LOW | Process lock not explicitly released on crash (stale detection handles it) |
| K-4 | LOW | No explicit guard on extreme odds values (>10000) |
| K-5 | LOW | NaN projections silently dropped without warning |
| K-6 | LOW | CSV column misalignment passes float() silently |
| K-7 | LOW | Append path has no atomic crash protection (header-rewrite path is atomic) |

**No CRITICAL findings.**

**Security posture is clean:** .env gitignored, no hardcoded secrets, API keys/webhooks load from env only, secrets_config.py redacts before printing, exception handlers never expose credentials.

**Actionable immediate fix (3 lines of code):** Add `encoding="utf-8"` to cache read (~1695), cache write (~1711), and dry-run write (~5917).
