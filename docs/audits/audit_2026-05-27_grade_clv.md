# Audit: grade_picks.py + capture_clv.py
**Date:** 2026-05-27  
**Auditor:** Claude Sonnet 4.6 (line-by-line read)  
**Files:** `engine/grade_picks.py` (~2255 lines), `engine/capture_clv.py` (~1452 lines)

---

## grade_picks.py — Findings

### CRITICAL

- **[CRITICAL]** `grade_picks.py:1851–1855` — **WHAT**: `_mark_posted` fallback path (no `discord_guard.py` module) calls `_save_guard(guard)` BEFORE adding `guard[event_key] = True`. **WHY WRONG**: `_save_guard` writes `_prune_guard(guard)` to disk, but `event_key` hasn't been added to `guard` yet at that point — so the new key is NOT persisted to `discord_posted.json`. On the next run, `_already_posted()` returns False and the recap fires again. This is a silent duplicate-post bug that only triggers when the `discord_guard` module is unavailable (import fallback). The shared path (`_HAS_SHARED_GUARD=True`) is unaffected. **FIX**: Move `guard[event_key] = True` above `_save_guard(guard)` in the fallback branch.

### HIGH

- **[HIGH]** `grade_picks.py:82` — **WHAT**: `ALL_LOG_PATHS = [PICK_LOG_PATH, PICK_LOG_MLB_PATH, PICK_LOG_WNBA_PATH]` is defined but never referenced anywhere in the file. **WHY WRONG**: Dead variable — creates a false impression that this list is used to enumerate logs for grading. The actual grading loop in `main()` (line 2249) independently hardcodes its own tuple. Any future addition to `ALL_LOG_PATHS` will silently have no effect. **FIX**: Remove the dead variable or wire `main()` to use it.

- **[HIGH]** `grade_picks.py:2248–2250` — **WHAT**: `pick_log_shadow_stats.csv` (the SHADOW_STATS gate log for GOALS, NHLPTS, NHLBLK, SV, GA, ER, BB, PC, RBI, RUNS, TB, HRR, NRFI/YRFI shadow picks) is never graded. Neither `PICK_LOG_SHADOW_STATS_PATH` is imported from `paths.py`, nor is it included in the shadow log loop `(PICK_LOG_MLB_PATH, PICK_LOG_WNBA_PATH, PICK_LOG_CUSTOM_PATH)`. **WHY WRONG**: Shadow-stats picks accumulate in `pick_log_shadow_stats.csv` indefinitely with blank `result` fields — the grader never fills them in. All shadow-stats W/L tracking, win-rate evaluation, and gate-reopening decisions (e.g., "G8B: re-evaluate at n=30 AST picks") rely on graded rows. Without graded results, the shadow stats system has no outcome feedback loop. **FIX**: Import `PICK_LOG_SHADOW_STATS_PATH` from paths.py and add it to the shadow grading loop.

- **[HIGH]** `grade_picks.py:383–420` — **WHAT**: `fetch_nhl_boxscores` iterates only `forwards` and `defense` lists; it never iterates the `goalies` list in `playerByGameStats`. **WHY WRONG**: If any NHL goalie prop ever reaches pick_log.csv (e.g., SV saves), `grade_prop` would find no matching player stats and grade every goalie pick as `VOID`. SV is currently a SHADOW_STAT, but if SV/GA moves out of shadow mode, goalie props would all be permanently mis-graded. **FIX**: Add a loop over `team_data.get("goalies", [])` in `fetch_nhl_boxscores`, extracting `saveShotsAgainst` → `SV` and `goalsAgainst` → `GA`.

- **[HIGH]** `grade_picks.py:1329` — **WHAT**: `COUNTED_RUN_TYPES = {"primary", "bonus"}` — `manual` is absent. **WHY WRONG**: The docstring for `get_graded_primary` (line 1334) still says "primary + bonus + manual". The CLAUDE.md says "Manual picks discontinued" and `PICK_LOG_MANUAL_PATH` is still graded silently (`is_shadow=True`). But `manual` rows in the main pick_log.csv (loaded via `main_rows`) are excluded from the Discord recap's W-L record and streak calculation even though they do appear in `day_picks` (since `day_picks` at line 2192 does not filter by run_type). This means manual rows CAN appear in the recap embed body but are excluded from the W/L header counts — creating inconsistent totals. **FIX**: Either explicitly exclude `manual` run_type from `day_picks` in `_post_merged_recaps`, or add `"manual"` to `COUNTED_RUN_TYPES` and `PROP_RUN_TYPES`. Align docstring with actual behavior.

- **[HIGH]** `grade_picks.py:1714–1717` — **WHAT**: `_read_rows_locked` falls back to a lock-free read when the 30s lock timeout expires. **WHY WRONG**: The comment says "RISK OF STALE/PARTIAL DATA" — this is correct. The CLV daemon can be mid-atomic-write (reading old file content mid-replace) at the moment of fallback. This isn't a new bug, but it means a 30-second lock contention window means the grader can clobber partial data. **FIX**: Do NOT fall back — if the lock cannot be acquired in 30s, raise an exception (abort gracefully rather than proceeding with potentially corrupt data). If a fallback-read is truly needed, at minimum log at WARNING level with the specific file path so Jono can investigate.

- **[HIGH]** `grade_picks.py:1621–1627` — **WHAT**: `pick_label()` inside `build_monthly_embed` uses `p.get("player", "").split()[-1]` to get a display name. **WHY WRONG**: For game-line picks (SPREAD, ML, TOTAL, TEAM_TOTAL), the `player` field contains strings like `"BOS -3.5"`, `"NYY ML"`, `"F5 New York Yankees"` — `split()[-1]` would produce `"-3.5"`, `"ML"`, or `"Yankees"` as the "last name". The monthly best/worst picks display would show e.g. `"-3.5 OVER 7.5 SPREAD | +1.23u"` for a best/worst game-line pick — confusing and meaningless. **FIX**: Use `_recap_pick_line(p)` for the best/worst labels (already handles all stat types correctly) instead of the ad-hoc `pick_label`.

### MEDIUM

- **[MEDIUM]** `grade_picks.py:1455` — **WHAT**: `build_recap_embed` accepts `suppress_ping=False` as a parameter but never uses it. `content` is always hardcoded to `""` (line 1585). **WHY WRONG**: In `--test` mode, `suppress_ping=True` is passed but silently ignored in the recap embed. The intent is to omit pings in test mode, but the recap embed already never pings. However, if someone adds a ping to the recap in future, this parameter provides no actual protection. The monthly summary at line 1908 also passes `suppress_ping=` via `build_monthly_embed` but that function also ignores it. Confusing dead parameter. **FIX**: Document that `content=""` intentionally means no ping, or remove the `suppress_ping` parameter from `build_recap_embed`/`build_monthly_embed`.

- **[MEDIUM]** `grade_picks.py:1334` — **WHAT**: `get_graded_primary` docstring says "primary + bonus + manual" but code uses `COUNTED_RUN_TYPES = {"primary", "bonus"}`. **WHY WRONG**: Doc/code mismatch — "manual" is not included despite the docstring. Misleads anyone relying on the docstring to understand streak calculation scope.

- **[MEDIUM]** `grade_picks.py:311–313` and `grade_picks.py:483–484` and `grade_picks.py:566–567` — **WHAT**: Three `except Exception: continue` blocks in `_parse_espn_boxscore` (per-game), `fetch_mlb_boxscores` (per-game), and `fetch_mlb_linescores` (per-game). **WHY WRONG**: Silent failures — a systematic API format change, a network issue, or a new field structure would silently drop all stats for all games. No log output of any kind, so Jono cannot detect a whole day's worth of missed grading until he notices picks are stuck as blank. **FIX**: At minimum log the exception string (`logger.warning`) so it appears in `jonnyparlay.log`.

- **[MEDIUM]** `grade_picks.py:1543–1546` — **WHAT**: The week breakdown in `build_recap_embed` uses `COUNTED_RUN_TYPES = {"primary", "bonus"}` (excludes parlays from W-L), but the daily header at line 1476 includes `parlay_picks` in the daily stats. **WHY WRONG**: The daily header W/L/P/L includes parlay results, but the week/month breakdown headers exclude them. This is intentional per the comment, but it means a winning daily_lay pick appears in the day's P&L but not in the week's W-L record — creating a persistent discrepancy that could confuse followers comparing day vs. week numbers. **FIX**: Either consistently exclude parlays from ALL totals (daily + week + month) or include them everywhere. Document the intentional split clearly in the embed so followers aren't confused.

- **[MEDIUM]** `grade_picks.py:1104–1106` — **WHAT**: `_game_is_complete` checks if a game appears in `scores_by_game` using a substring match `if game in key_lower or key_lower in game`. **WHY WRONG**: A game string like "BOS" could substring-match "BOS @ LAL" when looking for a Boston Red Sox MLB game (BOS appears in both NBA/MLB contexts). If `all_scores` accidentally contains NBA scores when checking an MLB player prop, a false-positive game-complete match could cause the grader to return VOID for a player who simply wasn't in the NBA boxscore but whose MLB game hasn't finished yet. **FIX**: Also match by sport context when checking game completeness — the `(date_str, sport)` key already scopes scores by sport, but the inner substring check doesn't use the sport label.

- **[MEDIUM]** `grade_picks.py:2112` — **WHAT**: Longshot/SGP rows call `grade_parlay_legs(row, all_player_stats, all_scores, all_linescores=all_linescores)` but `all_scores` is the full `(date, sport)` → scores_map dict. Inside `grade_parlay_legs`, the `scores` variable at line 826 is obtained via `all_scores.get((date_str, sport), {})`. When `all_scores[(date_str, sport)]` is `None` (plan-limit case), this `.get(..., {})` returns `None` (not `{}`) because `None` IS the stored value — the default `{}` only applies when the key is missing entirely. Then `grade_game_line(fake_pick, scores if isinstance(scores, dict) else {}, ...)` is called — `isinstance(None, dict)` is False, so it correctly falls through to `{}`. Actually this is handled correctly. CONFIRMING NO BUG HERE.

- **[MEDIUM]** `grade_picks.py:2027–2028` — **WHAT**: For `daily_lay`, `longshot`, and `sgp` run_types, NBA scores are always added to `dates_sports` regardless of the actual legs' sports. **WHY WRONG**: A longshot parlay with all MLB legs would trigger an unnecessary NBA score fetch. Not incorrect behavior, but wastes an API call and adds latency. Low real-world impact given daily_lay/longshot are currently NBA-only. **FIX**: Only add "NBA" to dates_sports if there is at least one NBA leg in the parlay row.

- **[MEDIUM]** `grade_picks.py:1560` — **WHAT**: `all_month` in `build_recap_embed` uses `r.get("run_type", "primary") in COUNTED_RUN_TYPES`. The month breakdown therefore excludes longshot/sgp/daily_lay results from the month W-L, but the month data comes from `all_rows` (the main pick_log.csv). **WHY WRONG**: Consistent with the week breakdown, but `all_month` result is shown in the footer with no note that it excludes parlays. If Jono checks the recap footer month total against the full pick log (including daily_lay P&L), they won't match. Same intentional split issue as the week breakdown above.

- **[MEDIUM]** `grade_picks.py:313` — **WHAT**: In `_parse_espn_boxscore`, each event's boxscore fetch is wrapped in `try/except Exception: continue`. If a game's summary endpoint returns a non-JSON 200 response or has unexpected structure, the game is silently skipped with no player stats. **WHY WRONG**: If ESPN changes its summary API format, all player stats would silently return empty for affected games, causing grading to stall with picks stuck ungraded — and no log entry to investigate. **FIX**: `logger.warning(f"ESPN event {event_id} failed: {e}")`.

- **[MEDIUM]** `grade_picks.py:2104–2109` — **WHAT**: Historical date bypass logic: if `_raw_scores` is an empty dict and the pick date is before today UTC, `_raw_scores` is set to `None` to bypass the game-complete gate. **WHY WRONG**: The UTC date comparison `datetime.now(timezone.utc).date()` is correct, but picks dated "yesterday" in ET could be "today" in UTC late at night (e.g., 11pm ET = 3am UTC+4). For a pick from the previous ET day with a UTC now() that hasn't crossed midnight yet, `date_str < today_utc` would be false — the bypass wouldn't trigger. This means yesterday's picks (by ET date) during a late-night re-run could be sent through the game-complete gate with an empty scores dict and return `None` (ungraded) instead of grading from stats alone. **FIX**: Use ET date (`datetime.now(ZoneInfo("America/New_York")).date()`) for the comparison to match the pick log's date convention.

### LOW

- **[LOW]** `grade_picks.py:84` — **WHAT**: `SHADOW_SPORTS = {"WNBA"}` still includes WNBA but the grader's main `day_picks` filter in `_post_merged_recaps` (line 2190) does NOT filter by sport — so WNBA picks from pick_log.csv would appear in the recap. The `SHADOW_SPORTS` set is used in `all_week`/`all_month` (lines 1544, 1559) to exclude WNBA from weekly/monthly totals. **WHY WRONG**: WNBA picks that accidentally land in pick_log.csv (e.g., via go-live) would appear in the day's recap picks list but be excluded from the week/month totals — inconsistent counting. Minor while WNBA is shadow-only. **FIX**: Confirm whether WNBA rows ever land in pick_log.csv vs. always in pick_log_wnba.csv.

- **[LOW]** `grade_picks.py:1466` — **WHAT**: `_rt = lambda p: p.get("run_type", "primary")` — the default is `"primary"`. **WHY WRONG**: An old row with a blank `run_type` would be silently treated as `primary`. If gameline rows ever have blank run_type, they'd appear in the props W-L totals. Minor risk since run_type has been populated since early in the log. **FIX**: Default to `""` and handle explicitly, or add a note that this default is intentional.

- **[LOW]** `grade_picks.py:1539–1540` — **WHAT**: Week calculation uses `ref.weekday()` where Monday=0. `mon_str` is the Monday of the current week. **WHY WRONG**: This is correct for a Mon–Sun week. If the "week" in CLAUDE.md is intended as Mon–Sun, no bug. But if the business week is Sun–Sat, Monday-anchoring would miscount. Presumed intentional but unconfirmed.

- **[LOW]** `grade_picks.py:1617–1618` — **WHAT**: `best = max(pick_pls, key=lambda x: x[1], default=None)` / `worst = min(...)`. **WHY WRONG**: With `default=None`, a totally empty picks list would set `best=None` and `worst=None`, which are guarded by `if best:` at line 1632. However `if best:` is falsy for `0` — if the best pick has a P/L of exactly `0.0`, `if best:` evaluates to False even though `best` is a valid `(pick, 0.0)` tuple. Actually, `(pick, 0.0)` is a non-empty tuple — Python evaluates `if (pick, 0.0)` as truthy (non-empty tuple). Only `None` or empty tuple would be falsy. So no real bug here — just potentially confusing code.

- **[LOW]** `grade_picks.py:1582` — **WHAT**: Discord embed description is truncated at 4090 chars with `desc[:4090] + "\n…"`. **WHY WRONG**: The Discord embed description limit is 4096 characters, so 4090 leaves a 6-char margin. This is fine, but a very long pick list could silently cut off mid-line with just "…". No functional bug, but the truncation isn't announced to the user. **FIX**: Consider truncating at a pick boundary rather than mid-character.

- **[LOW]** `grade_picks.py:483` — **WHAT**: `fetch_mlb_boxscores` inner loop at line 483: `except Exception: continue` silently skips individual game boxscores. `fetch_mlb_linescores` at line 566 does the same. **WHY WRONG**: Already documented above under MEDIUM — combined note for completeness.

### OPEN_QUESTIONS

- **[OPEN_QUESTION]** `grade_picks.py:1898–1900` — **WHAT**: Monthly summary fires when `today.day == 1` using `datetime.now(ZoneInfo("America/New_York"))`. **QUESTION**: If grade_picks runs at midnight ET exactly on the 1st, the previous month's all_rows may not have all of the last day's grades yet (if the last day's grading runs late). Does the monthly summary include the final day of the previous month? Trace: `get_month_picks` uses `r["date"].startswith(f"{prev_year}-{prev_month:02d}-")` with no upper bound on date. So any picked row from the previous month that is graded by the time the monthly summary runs IS included. If grade_picks runs at, say, 2am ET on the 1st and all last-day picks are graded by then, this is fine. If the grader runs immediately after the last game finishes (e.g., 11pm ET on the 30th, which is the 1st at 4am UTC), the monthly summary would fire on that same run. Low risk in practice.

- **[OPEN_QUESTION]** `grade_picks.py:301–310` — **WHAT**: ESPN boxscore stat extraction for NBA: `entry["3PM"] = int(str(d["3PT"]).split("-")[0])`. **QUESTION**: ESPN's `3PT` field format is "made-attempted" (e.g., "3-7"). `split("-")[0]` gives made count = correct. But what if a player goes 0-0 (did not attempt)? ESPN may return "0-0" → `split("-")[0]` = "0" = `int("0")` = 0 = correct. Edge case with negative numbers is unlikely for made shots. Presumed correct.

- **[OPEN_QUESTION]** `grade_picks.py:2190–2192` — **WHAT**: `day_picks` in `_post_merged_recaps` includes all run_types (including `sgp`, `longshot`, `daily_lay`, `manual`). `build_recap_embed` then splits by run_type. **QUESTION**: If a manual pick in pick_log.csv (not pick_log_manual.csv) with result=W is present, it would appear in `parlay_picks` only if `run_type=daily_lay/sgp/longshot`, otherwise it falls through to `reg_props` or is not shown. Manual picks with `run_type=manual` would be in `reg_props` only if `_rt(p) in PROP_RUN_TYPES` — since PROP_RUN_TYPES={"primary","bonus"}, `manual` run_type rows would appear in neither `reg_props` nor `parlay_picks` and would be silently dropped from the embed body. They ARE counted in the daily stats header because `daily_stats(reg_props + ks_picks + parlay_picks)` passes only those three lists (manual excluded). Net result: if a manual pick exists in pick_log.csv, it silently contributes to `day_picks` count but doesn't appear in the embed and doesn't affect W-L numbers. Confusing but no double-counting.

---

## grade_picks.py — TODO/FIXME/HACK/bare-except inventory

- `grade_picks.py:312`: `except Exception: continue` (ESPN per-game boxscore loop — silent)
- `grade_picks.py:483`: `except Exception: continue` (MLB per-game boxscore loop — silent)
- `grade_picks.py:566`: `except Exception: continue` (MLB linescore per-game loop — silent)
- `grade_picks.py:1714–1717`: Lock fallback in `_read_rows_locked` — falls through to lock-free read with warning
- `grade_picks.py:1752–1756`: Lock fallback in `_atomic_write_rows` — writes anyway with warning (HIGH risk)
- No TODO/FIXME/HACK comments found in the codebase.

---

## capture_clv.py — Findings

### CRITICAL

*(None found)*

### HIGH

- **[HIGH]** `capture_clv.py:190–193` — **WHAT**: `DATA_DIR` and `PICK_LOG` are built from `Path(__file__).resolve().parent.parent / "data"` — hard-coded relative to the script location. **WHY WRONG**: This bypasses `paths.py`'s `JONNYPARLAY_ROOT` env-var override and its project-root detection heuristic. If `JONNYPARLAY_ROOT` is set (e.g., in Cowork), `grade_picks.py` and `run_picks.py` would read/write to the env-var-specified root, but `capture_clv.py` would still write to the script-relative `data/` directory — causing CLV updates to land in a different file than the one being graded. **FIX**: Import `PICK_LOG_PATH, DATA_DIR` from `paths.py` instead of rebuilding them locally. (Note: `PICK_LOG` hardcodes `pick_log.csv` anyway and doesn't honour `JONNYPARLAY_PICK_LOG` env var, but `paths.py` does — CLV is intentionally anchored to the real log, not the shadow log.)

- **[HIGH]** `capture_clv.py:565–573` — **WHAT**: `picks_needing_clv` only filters by `closing_odds` being empty (or "STALE") and `stat not in SKIP_STATS` and `result not in terminal`. It does NOT filter by `run_type`. **WHY WRONG**: If a `run_type=sgp` or `run_type=longshot` row has `stat` something other than `"PARLAY"` (which shouldn't happen but could from manual entry), the daemon would attempt CLV capture for it. Also: STALE detection — `picks_needing_clv` checks `not p.get("closing_odds", "").strip()` — so if `closing_odds = "STALE"`, it correctly returns non-empty string and is excluded. This part is fine. The run_type omission is a latent bug for unusual rows. **FIX**: Add `p.get("run_type", "") not in {"sgp", "longshot"}` to `picks_needing_clv` as defensive filtering.

- **[HIGH]** `capture_clv.py:870–874` — **WHAT**: `calc_clv` calls `implied_prob(closing_odds) - implied_prob(your_odds)` — both calls could return `None` if odds are 0/NaN/missing. **WHY WRONG**: `None - float` raises `TypeError`. But the caller at line 1337 checks: `clv = calc_clv(your_odds, closing_odds) if (your_odds is not None and your_odds != 0) else None` — this guards `your_odds`. However, `closing_odds` comes from `get_closing_odds_for_pick()` which can return odds values like 0 in theory (though unlikely from a real bookmaker). `implied_prob(0)` returns `None` (the `not o` check). So `None - float` = `TypeError` in `calc_clv`. The guard at the call site only checks `your_odds`, not `closing_odds`. **FIX**: In `calc_clv`, guard for `None` returns from `implied_prob`: `a, b = implied_prob(closing_odds), implied_prob(your_odds); return (a - b) if (a is not None and b is not None) else None`.

### MEDIUM

- **[MEDIUM]** `capture_clv.py:594–603` — **WHAT**: `_do_write_closing_odds` opens the CSV file for reading WITHOUT a lock (it's inside `write_closing_odds` which holds the lock, so this is fine). However, if `closing_odds` is a numeric float (e.g., `-110`), it gets stored as `str(-110)` = `"-110"` on line 602. **WHY WRONG**: Not a bug per se, but `closing_odds = -110` (integer) gets stored as `"-110"` while `closing_odds = -110.0` (float) gets stored as `"-110.0"`. Downstream readers using exact string comparison could be confused by the inconsistency. **FIX**: Ensure `closing_odds` is always formatted consistently, e.g., `f"{int(closing_odds)}"` for integer odds values.

- **[MEDIUM]** `capture_clv.py:1006–1017` — **WHAT**: Ghost-game integrity check loads all today's picks using `load_picks` (which uses `read_rows_locked_if_exists`). `needs_clv_games` is built from games with empty `closing_odds` AND `stat not in SKIP_STATS`. **WHY WRONG**: The result filter does NOT exclude terminal results (`W/L/P/VOID`). This means a pick that was graded (W/L) before CLV was captured would appear in `needs_clv_games` and could evict a checkpoint entry, causing an unnecessary re-fetch attempt. Comparing with `picks_needing_clv` (line 565–573), which DOES filter out terminal results — the ghost-game check is less strict. This could cause spurious checkpoint evictions. **FIX**: Add `and p.get("result", "") not in {"W", "L", "P", "VOID"}` to the `needs_clv_games` set comprehension (lines 1013–1017).

- **[MEDIUM]** `capture_clv.py:836` — **WHAT**: Player name normalisation in CLV prop matching. `player_lower = player.lower().replace("-", " ")` and `player_words = [w for w in player_lower.split() if len(w) > 2]`. **WHY WRONG**: This does NOT use the same `_fold_name` (accent-stripping) normalisation that grade_picks.py and run_picks.py use. The Odds API returns player descriptions with accented characters (e.g., "Nikola Jokić"), and the pick log may have "Nikola Jokic" (no accent). Without accent-stripping, the word `"jokić"` would not match `"jokic"`. CLV for accented-name players would always fail to find a closing line and leave `closing_odds` blank. **FIX**: Import and use `fold_name` from `name_utils` for player matching, consistent with grade_picks.py.

- **[MEDIUM]** `capture_clv.py:659–673` — **WHAT**: `game_str_matches` word-overlap fallback uses words with `len(w) >= 3`. A 3-letter city like "Los" appears in "Los Angeles Lakers" AND "Los Angeles Clippers" — both ≥ 3 chars. In a scenario where the pick game string is "Clippers @ Lal" (abbreviated) and two events exist in the same-day list for both LA teams, the fallback could match both events, returning the first one found. **WHY WRONG**: For same-city multi-team markets (LA, NY), the fallback word match could produce a false-positive match against the wrong team's game, fetching wrong closing odds and computing incorrect CLV. **FIX**: Add the ambiguous team code check (already in grade_picks.py's `AMBIGUOUS_TEAM_CODES`) to `game_str_matches`, returning False for known ambiguous fragments.

- **[MEDIUM]** `capture_clv.py:1302–1319` — **WHAT**: Write-gate logic: when `secs_to_start > CAPTURE_WRITE_BEFORE_SECS` (game more than 10 min away), the code prints odds availability info and sets `secs_to_next_window = min(secs_to_next_window, secs_to_start - CAPTURE_WRITE_BEFORE_SECS)`. **WHY WRONG**: `secs_to_start - CAPTURE_WRITE_BEFORE_SECS` is the number of seconds until the write gate opens. If this is a small positive number (e.g., 30 seconds) and `POLL_INTERVAL_SECS=120`, the sleep at the bottom of the loop would be `min(secs_to_next_window, POLL_INTERVAL_LONG_SECS)` — but the sleep logic at line 1409 uses `secs_to_next_window - POLL_INTERVAL_SECS`. If `secs_to_next_window = 30` and `POLL_INTERVAL_SECS = 120`, then `secs_to_next_window - POLL_INTERVAL_SECS = -90 < 0`, and `max(-90, POLL_INTERVAL_SECS) = 120`. So the daemon sleeps a full 2-min poll interval and misses the narrow 30-second write gate — the next poll happens 2min after the gate opened. Functionally this is fine since the game is still being polled every 2 min afterward, but there could be a ~2-min delay in CLV write for games with very narrow pre-gate windows. Not critical but suboptimal.

- **[MEDIUM]** `capture_clv.py:204–207` — **WHAT**: `_ALL_SHADOW_LOGS = {"MLB": DATA_DIR / "pick_log_mlb.csv"}` with `ENABLE_SHADOW_CLV = False` means `SHADOW_LOGS = {}`. MLB went live on 2026-05-20 — its picks now go to `pick_log.csv` (main log), which IS captured by the daemon. BUT: any old MLB picks still in `pick_log_mlb.csv` that were logged before go-live would never get CLV captured because `ENABLE_SHADOW_CLV = False`. **WHY WRONG**: This is expected/intentional (old pre-live shadow rows won't get CLV retroactively). However, it means `pick_log_mlb.csv` rows permanently have blank `closing_odds` and "STALE" will never be written — they just stay blank forever, which clv_report.py may show as "no CLV" rather than "STALE". Minor data quality issue.

- **[MEDIUM]** `capture_clv.py:448–449` — **WHAT**: `except (ValueError, TypeError): pass` when parsing the `x-requests-remaining` header. **WHY WRONG**: A `pass` here means a malformed header value (e.g., empty string or non-numeric) would silently skip the quota check. If the API changes to return a non-integer quota header, the quota exhaustion logic would silently stop working. However this is a graceful degradation (daemon continues normally) rather than a correctness bug. **FIX**: `logger.debug("Quota header malformed: %r", r.headers.get('x-requests-remaining'))` to make this visible at DEBUG level.

### LOW

- **[LOW]** `capture_clv.py:260` — **WHAT**: `import math as _math` inside `implied_prob` function body. **WHY WRONG**: `math` is already imported at module level (line 35). Importing it again inside the function is redundant — it works correctly (Python caches modules) but is confusing. **FIX**: Remove the inner import and use the module-level `math` directly.

- **[LOW]** `capture_clv.py:294–300` — **WHAT**: `best_price` direction matching: `dir_lower in o_name or o_name in dir_lower`. **WHY WRONG**: `o_name in dir_lower` matches when the outcome name is a substring of the direction string. For `direction="over"`, this is fine. But if `direction="san antonio spurs"` (a team name used as direction for a spread), `o_name in dir_lower` could match short outcome names like "san" being in "san antonio spurs". This is a theoretical false-positive risk for team-name directions. In practice, TOTAL/SPREAD outcomes have `o_name = "Over"/"Under"` so this doesn't apply, but the logic is fragile. **FIX**: Add `len(o_name) >= 3` guard or use a more explicit direction check.

- **[LOW]** `capture_clv.py:1358–1359` — **WHAT**: `BOOK_DISPLAY.get(closing_book, closing_book)` in the print statement. **WHY WRONG**: `BOOK_DISPLAY` maps `espnbet` → `"theScore Bet"`. This is correct in the print output. But the `closing_book` stored in the update dict at line 1351 is the raw `espnbet` API key, not the display name. Downstream `closing_book` is not written to pick_log.csv (only `closing_odds` and `clv` are written). So no incorrect data is persisted. Low severity — display only.

- **[LOW]** `capture_clv.py:975–976` — **WHAT**: `_daemon_start_utc = datetime.now(timezone.utc)` is used for uptime calculation but is computed AFTER the lock acquisition. If lock acquisition takes several minutes (blocked by another process), the actual wall-clock start time would be underestimated, which could cause the MIN_UPTIME guard to exit slightly later than intended. Negligible in practice.

- **[LOW]** `capture_clv.py:999` — **WHAT**: Checkpoint is loaded before the integrity check. The integrity check (lines 1000–1024) builds `all_today_picks` but does NOT include `WNBA_LOG` picks in the `needs_clv_games` set when checking against `captured_games`. Wait — checking lines 1006–1012: `_all_logs = [PICK_LOG] + list(SHADOW_LOGS.values())` + optional `CUSTOM_SHADOW_LOG` + optional `WNBA_LOG`. WNBA_LOG IS included in the ghost-game check when `ENABLE_WNBA_CLV=True`. Correct — no bug here.

- **[LOW]** `capture_clv.py:1369` — **WHAT**: `captured_picks_for_game = sum(len(u) for u in updates_by_log.values())`. **WHY WRONG**: This counts the number of keys in `updates_by_log`, which is the number of (date, player, stat, line, direction) tuples for which closing odds were found. This is compared to `total_picks_for_game = len(game_picks)`. If a single pick appears in multiple logs with the same key (shouldn't happen but could via duplicate rows), `captured_picks_for_game` would undercount. Minor edge case.

- **[LOW]** `capture_clv.py:985` — **WHAT**: `atexit` `_log_exit` function has a bare `except Exception: pass`. **WHY WRONG**: If the logger itself fails during atexit (e.g., log file removed), the exception is swallowed silently. Acceptable for an atexit handler since the process is exiting anyway — but notable.

### OPEN_QUESTIONS

- **[OPEN_QUESTION]** `capture_clv.py:565–573` — **WHAT**: `picks_needing_clv` does NOT filter out `run_type=manual` picks. Manual picks in `pick_log.csv` would attempt CLV capture just like primary picks. **QUESTION**: Is CLV capture desired for manual picks? Per CLAUDE.md: "Excluded from CLV daemon" applies to `pick_log_manual.csv` (the separate manual log), but manual picks accidentally logged to `pick_log.csv` (e.g., via `--log-manual` flag) would be captured. Probably unintentional — manual picks shouldn't have CLV.

- **[OPEN_QUESTION]** `capture_clv.py:751–757` — **WHAT**: 2-letter team abbreviation handling: `elif not target_words and team_frag and len(team_frag) == 2: if team_frag in oc_name: matched = True`. **QUESTION**: 2-letter abbreviations like "LA", "NY", "TB" can match substrings: "la" is in "dallas", "ny" is in "new york", "tb" is in "table". For example, searching for "LA" ML odds: `"la" in "dallas mavericks"` is True. This means the daemon could capture CLV for the wrong team on a ML pick when team_frag is 2 characters and target_words is empty. Is this scenario reachable in practice given modern picks always have `is_home` set?

---

## capture_clv.py — TODO/FIXME/HACK/bare-except inventory

- `capture_clv.py:432`: `except Exception as e:` in `_odds_api_get` for unexpected errors — logs and returns None (appropriate, not silent)
- `capture_clv.py:448–449`: `except (ValueError, TypeError): pass` for quota header parsing (silent, noted above)
- `capture_clv.py:985`: `except Exception: pass` in atexit `_log_exit` (acceptable for atexit)
- `capture_clv.py:1440–1446`: Top-level `except Exception:` in `main()` — catches all unhandled exceptions and logs to clv_daemon.log; intentional daemon crash handler
- No TODO/FIXME/HACK comments found.

---

## Summary

### grade_picks.py
The grader is well-structured with proper FileLock, atomic writes, timezone-aware dates, and good error handling in most places. The two most impactful bugs are:

1. **`pick_log_shadow_stats.csv` is never graded** (HIGH) — SHADOW_STATS picks have no outcome feedback. This breaks the data-gated evaluation system for GOALS/NHLBLK/SV/GA/ER/BB/PC/RBI/RUNS stats.

2. **`_mark_posted` fallback writes guard before adding the new key** (CRITICAL) — duplicate Discord posts if `discord_guard` module is unavailable.

3. **`_atomic_write_rows` falls back to a lock-free write** (HIGH) — if lock cannot be acquired after 30s, writes proceed without locking, risking clobber of CLV daemon's concurrent write.

4. **`pick_label` in `build_monthly_embed` uses `.split()[-1]`** (HIGH) — game-line picks produce nonsense labels like `"-3.5 SPREAD | +1.23u"`.

5. **NHL goalie stats not fetched** (HIGH) — SV/GA goalie grading would always return VOID.

Three silent `except Exception: continue` blocks in ESPN/MLB API parsers should be upgraded to log warnings.

### capture_clv.py
The daemon is robust with single-instance locking, graceful shutdown, retry logic, and quota management. The most important issues are:

1. **`calc_clv` can raise `TypeError` if `closing_odds` → `implied_prob` returns `None`** (HIGH) — crashes CLV write for zero or unusual closing odds values.

2. **`DATA_DIR` bypasses `JONNYPARLAY_ROOT` env var** (HIGH) — mismatch in Cowork deployments where root is overridden.

3. **Player name matching lacks accent-stripping** (MEDIUM) — accented player names (e.g., Jokić, Dončić) would never get CLV captured.

4. **Ghost-game check does not filter terminal results** (MEDIUM) — spurious checkpoint evictions for already-graded picks.

5. **`needs_clv_games` in ghost-game check doesn't exclude terminal-result rows** (MEDIUM) — same as above, detailed.

The `pick_log_shadow_stats.csv` is correctly NOT included in the CLV daemon's log paths (shadow stats picks have no standard market coverage for CLV).
