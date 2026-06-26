# AUDIT 2026-06 — JP-5 Grading (JonnyParlay)

Files audited (3 read): grade_picks.py, grade_picks.py, post_nrfi_bonus.py

**Findings (final, excl. refuted): C=0 H=0 M=4 I=6** | constants extracted: 13 | not-done: 5

## Findings

| ID | File:line | Sev | Status | Cat | Known | Title |
|----|-----------|-----|--------|-----|-------|-------|
| JP5-02 | grade_picks.py:1941 | M | confirmed | code |  | Lost-update race: grade_picks reads all rows under lock, releases lock during (slow) network grading, then rewrites the WHOLE file |
| JP5-04 | grade_picks.py:1360 | M | confirmed | code |  | grade_prop weak fuzzy fallback grades on last-name-only when no first+last match — can settle on the wrong same-surname player |
| JP5-06 | grade_picks.py:987 | M | confirmed | code |  | _resolve_pick_is_home legacy fallback accepts len>=2 token substring match — common letter pairs false-positive on the wrong side  |
| JP5-07 | grade_picks.py:1493 | M | confirmed | code |  | compute_pl / daily_stats match result with exact =="W"/"L"/"P" (no strip/upper), contradicting the module's own TERMINAL_RESULTS c |
| JP5-01 | grade_picks.py:1125 | I | refuted | code |  | grade_game_line TOTAL/TEAM_TOTAL/F5_TOTAL compare direction with raw =="over" (no lower/strip) — capitalized/whitespace direction  |
| JP5-03 | grade_picks.py:1644 | I | refuted | code |  | _recap_pick_line crashes (IndexError) on a prop row with blank player — aborts the run after results are written, skipping shadow  |
| JP5-08 | grade_picks.py:1175 | I | confirmed | completeness |  | NRFI/YRFI can only return W or L — a postponed/rained-out game (inning 1 never completes) stays ungraded forever, no VOID path |
| JP5-09 | grade_picks.py:1264 | I | unverified | completeness |  | GOLF_WIN intentionally returns None (manual grading) — acceptable stub, documented |
| JP5-10 | grade_picks.py:1476 | I | unverified | code |  | compute_pl American-odds payout math is correct |
| JP5-11 | grade_picks.py:490 | I | unverified | code |  | MLB derived-stat math (TB, HRR, IP->outs) is correct |
| JP5-12 | grade_picks.py:694 | I | unverified | code |  | grade_daily_lay push/loss/win fall-through invariants hold |
| JP5-05 | post_nrfi_bonus.py:73 | I | confirmed | statistical |  | post_nrfi_bonus posts a hardcoded NRFI pick with fabricated win_prob/edge/proj when run with no args — not derived from any model |

## C/H/M detail

### [M] JP5-02 — Lost-update race: grade_picks reads all rows under lock, releases lock during (slow) network grading, then rewrites the WHOLE file — clobbering CLV columns the CLV daemon wrote in the gap
`C:/Dev/JonnyParlay/engine/grade_picks.py:1941-2014` · code · status=confirmed

**Evidence:** _read_rows_locked (1941) acquires the lock, reads every row, releases. Grading then performs many network calls (seconds-to-minutes). _atomic_write_rows (1966) re-acquires the lock and writes the FULL `rows` list (including the now-stale closing_odds/clv columns it read earlier). The comment at 1967-1971 claims grade_picks and the CLV daemon 'can never clobber each other's writes' — but holding the lock only during the discrete read and the discrete write prevents torn I/O, NOT a read-modify-write lost update. Any capture_clv update to closing_odds/clv landing between the read and the write is overwritten back to the old value.

**Recommendation:** Either hold the lock across read->grade->write (long hold, simplest), or re-read each row's non-result columns under the write lock and merge (only overwrite the `result` cell). Do not rewrite columns grade_picks did not author.

**Verifier (confirmed):** The code does exactly what the finding claims. In grade_picks.py, _read_rows_locked (lines 1941/2211/2488) acquires the file lock, reads ALL rows, and releases; grading then performs many slow network calls (fetch_scores/fetch_*_boxscore with time.sleep(0.5) per date-sport — seconds to minutes); then _atomic_write_rows (1966/2431/2581) re-acquires the lock and writes the FULL in-memory `rows` list. grade_picks only authors the `result` cell (rows[idx][\"result\"]=result, line 2415) but rewrites 

### [M] JP5-04 — grade_prop weak fuzzy fallback grades on last-name-only when no first+last match — can settle on the wrong same-surname player
`C:/Dev/JonnyParlay/engine/grade_picks.py:1360-1381` · code · status=confirmed

**Evidence:** After exact-fold fails, the fuzzy block prefers first+last (line 1372) but falls back to `best_candidate = stats.get(stat)` on last-name-only match (1377-1381). On a slate with two players sharing a surname (e.g. two 'Williams'/'Johnson') and the strong-match name absent from the boxscore, the weak fallback returns the OTHER player's stat line and grades W/L against the wrong human.

**Recommendation:** When only a last-name match exists and >1 boxscore player shares that surname, return None (ungraded) instead of best-guessing; or require team agreement before accepting a last-name-only candidate.

**Verifier (confirmed):** Code matches the finding. In grade_picks.py:1360-1381, after exact-fold match fails, the fuzzy block prefers first+last (line 1372, breaks) but otherwise sets best_candidate on the FIRST last-name-only match (elif best_candidate is None, 1377-1379) and accepts it (1380-1381). There is no count of how many players share that surname and no team-agreement check. Reachability confirmed and broader than stated: grade_prop is fed all_player_stats[(date,sport)] (line 2360 / 2397), which is the ENTIRE 

### [M] JP5-06 — _resolve_pick_is_home legacy fallback accepts len>=2 token substring match — common letter pairs false-positive on the wrong side for non-ambiguous short codes
`C:/Dev/JonnyParlay/engine/grade_picks.py:987-991` · code · status=confirmed

**Evidence:** Lines 987-989: `tokens = [t for t in identifier.split() if len(t) >= 2]; if any(t.lower() in away_lower for t in tokens): is_away = True`. Whole-identifier check at 983 also uses naked substring. Ambiguous codes (LA/NY/SF/SD) bail earlier (970), but other 2-3 char codes (e.g. 'SA','AL') can substring-hit unrelated full names ('Sacramento','Kansas','Dallas'...), flipping home/away for legacy rows lacking the is_home field. Affects SPREAD/ML/TEAM_TOTAL/F5 settlement direction.

**Recommendation:** On the legacy path resolve the code through _GL_NAME_TO_ABBR and compare full abbreviation equality rather than naked substring; return None if it can't be resolved unambiguously.

**Verifier (confirmed):** Code confirmed at C:/Dev/JonnyParlay/engine/grade_picks.py:978-991. The legacy fallback in _resolve_pick_is_home sets is_away via naked substring (`identifier.lower() in away_lower`, line 983, and the token check at 987-989). The H-4 guard at line 970 only covers AMBIGUOUS_TEAM_CODES = {LA, NY, SF, SD} (lines 658-663); it does NOT cover ordinary 3-letter abbreviations.

The finding's SPECIFIC examples ('SA','AL') are wrong — those are not real abbreviations in the system (market_config.TEAM_ABBR

### [M] JP5-07 — compute_pl / daily_stats match result with exact =="W"/"L"/"P" (no strip/upper), contradicting the module's own TERMINAL_RESULTS case-insensitive contract
`C:/Dev/JonnyParlay/engine/grade_picks.py:1493-1518` · code · status=confirmed

**Evidence:** TERMINAL_RESULTS doc (147-157) says downstream readers should `.strip().upper()`; _is_terminal_result does so. But compute_pl (1493 `if result == "W"`) and daily_stats (1512-1516 `p.get("result")=="W"` etc.) compare raw. A manually-edited lowercase 'w' or ' W ' row is counted as a non-win/non-loss (P&L 0, excluded from record) — silent miscount of the public W-L/ROI.

**Recommendation:** Normalize result via str(result).strip().upper() in compute_pl and daily_stats counters, matching _is_terminal_result.

**Verifier (confirmed):** Code matches the finding exactly. compute_pl (grade_picks.py:1493,1495) and daily_stats (1512-1514) compare result with raw equality (=="W"/"L"/"P"), no strip/upper. The module's own TERMINAL_RESULTS contract (156-157) instructs downstream readers to compare case-insensitively and strip, and _is_terminal_result (170) does so via str(raw).strip().upper(). The CSV read path _read_rows_locked (1951) uses plain DictReader with no normalization, so raw cell values flow straight into the counters. Gra


## Confirmed-correct / coverage notes

- compute_pl (1476-1497): American-odds payout math is correct for both signs; zero/unparseable odds guarded and return 0.0 with a warning, not a silent crash.
- MLB derived stats (490-512): singles/TB/HRR and IP-string->outs conversion (e.g. '6.1'->19) all match standard MLB definitions.
- grade_daily_lay (694-815): documented push/loss/win fall-through invariants verified — any losing leg returns 'L' immediately, all-push returns 'P', and the trailing 'W' is reachable only when no leg lost. Ambiguous 2-letter codes correctly drop the whole parlay to ungraded.
- TERMINAL_RESULTS / _is_terminal_result (158-170) and the M-23 idempotency guards (2405-2414, 2565-2568) correctly prevent re-grading/overwriting terminal W/L/P/VOID rows.
- _atomic_write_rows (1966-2014) uses lockfile + tmp + fsync + os.replace, so individual writes are atomic and torn reads are prevented (the residual concern is the cross-process read-modify-write window, JP5-02, not torn I/O).
- _save_guard (2070-2086) correctly refuses to fall back to a non-atomic open() write on atomic-write failure, preventing a truncated guard file from causing duplicate Discord posts.
- _webhook_post (1427-1473) correctly does NOT retry on ReadTimeout (avoids duplicate Discord posts) while retrying connect/other errors, and parses Retry-After for 429s.
- fetch_scores (206-260) correctly distinguishes 422 plan-limit (returns None -> grade from stat APIs) from an empty completed-games list (returns []), and converts UTC commence_time to ET before date-matching late games.
- grade_parlay_legs (818-888) routes game-line legs to grade_game_line and prop legs to grade_prop, and correctly drops P/VOID legs before re-evaluating (fixes the prior all-W-on-VOID-game-line bug).
- grade_prop (1320-1403) gates on game-complete before grading, returns VOID for DNP only when the game is confirmed finished, and normalizes direction (lower/strip) — the normalization grade_game_line is missing (JP5-01).
- Root grade_picks.py is a thin runpy shim delegating to engine/grade_picks.py — no logic.

## Not-Done / incomplete (this module)

| Kind | File | Detail |
|------|------|--------|
| stub | grade_picks.py | grade_game_line GOLF_WIN branch (1264-1267) always returns None — golf outrights graded manually only. |
| partial-feature | post_nrfi_bonus.py | Module is a hardcoded one-shot NRFI poster with placeholder win_prob/edge/proj/size defaults (73-86); docstring says production would parameterize via CLI args. |
| dead-code | grade_picks.py | _key_sport_matches (1311-1317) is a documented no-op that always returns True; exists only as a future extension point for mixed-sport score dicts. |
| flag-gated | grade_picks.py | SHADOW_SPORTS = set() (87) and SHADOW_LOGS = {} (post_nrfi_bonus 54) — all sports live; shadow-log grading paths (main 2654-2657) retained for legacy CSVs but e |
| deferred | grade_picks.py | NRFI/YRFI has no VOID/postponement terminal path (1175-1192) unlike F5; suspended-game NRFI rows remain ungraded indefinitely. |
