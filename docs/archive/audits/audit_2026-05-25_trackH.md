# Audit 2026-05-25 — Track H: Grading, CLV & Output Layer

Auditor: Claude Sonnet 4.6 (automated)
Scope: engine/grade_picks.py, engine/capture_clv.py, engine/results_graphic.py, engine/weekly_recap.py, engine/clv_report.py, engine/analyze_picks.py

---

## H1. Grading Correctness

### Over/under direction — CORRECT (strict inequalities)
`grade_prop()` (~lines 1198–1205):
```python
if direction_norm == "over":
    if actual > line: return "W"   # strict >
    elif actual < line: return "L"
    else: return "P"               # exact = push
elif direction_norm == "under":
    if actual < line: return "W"   # strict <
    elif actual > line: return "L"
    else: return "P"
```
Matches DK rules: exact line = push/refund. Correct.

### VOID handling — CORRECT
`grade_prop()` (~lines 1188–1193): VOID returned when game is complete but player absent from boxscore. Double-layer protection: upstream `_is_terminal_result` filter on ungraded list, plus defensive check at write site.

### Double-write guard — CORRECT
`_is_terminal_result(existing)` at write site prevents overwriting settled picks.

### Parlay/SGP settlement — CORRECT
Any losing leg → L. Push/VOID legs drop out. All remaining must be W for overall W. Correct.

---

### H-1 (LOW) — OT grading relies entirely on external API completed flag

```
TRACK: H
FILE: engine/grade_picks.py
LINE: ~239, ~353
SEVERITY: LOW
N: N/A
ISSUE: The grader won't find the game in the completed list until the API marks it complete
(completed=True). This is correct by design — _game_is_complete() returns False during OT
so grade_prop() returns None and retries. BUT if the ESPN boxscore returns player stats
before Odds API marks the game complete (e.g., mid-overtime timeout), premature grading
could occur.
IMPACT: Very low probability — Odds API marks completed quickly after buzzer.
FIX: No code change required. A unit test pinning this behavior would lock it in.
```

---

## H2. CLV Capture

### Capture window — MISMATCH with CLAUDE.md

```
TRACK: H
FILE: engine/capture_clv.py
LINE: ~157–159
SEVERITY: MEDIUM
N: N/A
ISSUE: CLAUDE.md says "T-30 to T+3" capture window. Actual code constants:
  CAPTURE_BEFORE_SECS    = 45 * 60   # polling starts at T-45
  CAPTURE_AFTER_SECS     = 3 * 60    # post-tip cutoff T+3
  CAPTURE_WRITE_BEFORE_SECS = 10 * 60  # writes within T-10 only
So polling starts at T-45 (not T-30), and writes are gated to within T-10.
IMPACT: Documentation mismatch could mislead CLV analysis (e.g., "why did CLV capture
at T-32?" would seem wrong per CLAUDE.md but is correct per code).
FIX: Update CLAUDE.md: "T-45 to T+3 polling; CLV written only within T-10 of tip."
```

### CLV formula — vigged, not vig-free

```
TRACK: H
FILE: engine/capture_clv.py + engine/clv_report.py
LINE: ~870–874 (capture_clv), ~55–63 (clv_report)
SEVERITY: LOW
N: N/A
ISSUE: CLV is computed as:
    return implied_prob(closing_odds) - implied_prob(your_odds)
Both sides use raw VIGGED implied probability. CLAUDE.md says "vig-free both sides."
The code comment acknowledges this explicitly: "Both sides use raw vigged implied.
Standard industry practice." CLV magnitude is slightly understated (compressed by ~0.5–1pp
vs vig-free CLV for asymmetric markets), but direction is preserved. Sign is correct:
positive CLV = you beat the close.
clv_report.py reads stored CLV directly — consistent with capture_clv.
IMPACT: CLV magnitude is not directly comparable to no-vig edge (edge is no-vig, CLV is
vigged). CLAUDE.md is factually wrong.
FIX: Update CLAUDE.md: "raw vigged closing implied minus raw vigged open implied
(consistent with industry standard, not vig-free)."
```

### Game matching — partial risk from short city fragments

```
TRACK: H
FILE: engine/capture_clv.py
LINE: ~650–673
SEVERITY: MEDIUM
N: N/A
ISSUE: Fallback game matching uses word-level overlap with any word ≥ 3 chars from home
and away team names. Short 3-char city fragments (San, New, Los) could match wrong events.
Within a single sport this is unlikely but not impossible.
IMPACT: Wrong CLV written for a pick if a game-matching fallback fires on a short fragment.
FIX: Require words ≥ 5 chars in fallback, or require both full team name substrings.
```

### CLV filelock — CORRECT
`write_closing_odds()` acquires `FileLock(lock_path, timeout=30)` before every write. Inner write uses atomic `os.replace()`. Correct.

### MAX_DAEMON_UPTIME late-game scenario

```
TRACK: H
FILE: engine/capture_clv.py
LINE: ~185
SEVERITY: LOW
N: N/A
ISSUE: Daemon starts at 10am, exits after 18h (4am). If run_picks fires at 3am for a
late-night West Coast game, the prior day's daemon has already exited. Next day's daemon
starts at 10am and finds those picks already graded — they get STALE. Very rare in practice.
IMPACT: Occasional STALE CLV on very late runs. Known limitation. No fix warranted.
```

### Spread side matching — fallback has blind spot

```
TRACK: H
FILE: engine/capture_clv.py
LINE: ~759–818
SEVERITY: MEDIUM
N: N/A
ISSUE: Primary match is by player-field word overlap (words > 2 chars). Short 2-letter
team abbreviations (SD, KC, TB, NY) fail word match and fall to is_home fallback.
If is_home is blank (legacy rows), fallback returns None → no CLV written (STALE).
Modern rows with is_home populated are fine.
IMPACT: Short-abbrev spread picks on legacy rows get STALE CLV. Acceptable behavior
(better than wrong CLV), but worth documenting.
FIX: No code change needed. Document accepted limitation.
```

---

## H3. Discord Posting

### Discord guard coverage — nearly complete

All primary posting paths check the guard (`_discord_claim_post` or `_already_posted`):
- Premium card ✓
- POTD ✓
- Bonus ✓
- Longshot ✓
- KILLSHOT ✓
- Recap (grade_picks) ✓
- Weekly (weekly_recap) ✓

### H-2 (MEDIUM) — No Discord embed length guard (4096 char limit)

```
TRACK: H
FILE: engine/grade_picks.py + engine/weekly_recap.py
LINE: ~1575–1594 (grade_picks), ~492–506 (weekly_recap)
SEVERITY: MEDIUM
N: N/A
ISSUE: Discord embed description limit is 4096 chars. The recap desc is assembled as a
multi-line string with no length check or truncation. On a heavy-pick day (15+ picks +
parlays), description could approach or exceed 4096 chars. Discord silently rejects
embeds exceeding this limit (returns 400 Bad Request) — recap fails to post with no
automatic fallback or retry.
Weekly embed has same issue. CLV block alone can be 6–8 lines; 7-day breakdown + best/worst
+ month total could accumulate.
IMPACT: Silent Discord failure on heavy-pick days.
FIX: Add `desc = desc[:4090] + "…"` before embed construction, or split into multiple
embeds for days with many picks. At minimum log embed length at debug level.
```

### H-3 (MEDIUM) — weekly_recap 429 handling doesn't use shared retry utility

```
TRACK: H
FILE: engine/weekly_recap.py
LINE: ~606–612
SEVERITY: MEDIUM
N: N/A
ISSUE: grade_picks._webhook_post() uses shared http_utils.retry_after_secs which checks
both the JSON body and the Retry-After HTTP header. weekly_recap._webhook_post_with_file()
uses inline retry logic that only reads json().get("retry_after") and doesn't check the
HTTP header. On Discord 429 with non-standard body, weekly_recap waits 2s instead of
the correct backoff.
IMPACT: On heavy rate-limiting, weekly recap may fail where grade_picks would survive.
FIX: Replace inline retry_after in weekly_recap with `from http_utils import retry_after_secs`.
```

### results_graphic.py — no Discord guard

```
TRACK: H
FILE: engine/results_graphic.py
LINE: ~610–614
SEVERITY: LOW
N: N/A
ISSUE: Standalone results_graphic.py CLI posts to Discord with no guard key. Running it
twice on the same day posts the graphic twice. However, grade_picks.py does NOT call it
automatically — it's manual CLI only.
IMPACT: Duplicate graphic post on manual reruns.
FIX: Add a guard key graphic:{date} or accept as manual-only limitation.
```

---

## H4. CLV Report / Analyze Picks

### H-4 (MEDIUM) — analyze_picks.calc_metrics includes VOID in risked units

```
TRACK: H
FILE: engine/analyze_picks.py
LINE: ~110
SEVERITY: MEDIUM
N: N/A
ISSUE: calc_metrics in analyze_picks.py:
    risked = sum(p["size_num"] for p in picks if p["result"] != "P")
VOID picks (result="VOID", DNP) are NOT excluded from risked — they inflate risked
units and drag ROI lower than reality (stake is refunded by the book for VOID picks).

Contrast with grade_picks.daily_stats and weekly_recap.daily_stats which both correctly
exclude ("P", "VOID") from risked:
    risked = sum(... for p in picks if p["result"] not in ("P", "VOID"))

This is an inconsistency between the analysis tool and production metrics.
IMPACT: analyze_picks.py reports slightly overstated risked units and understated ROI
when VOID picks are present. Could mask real edge if multiple VOIDs occur in a window.
FIX: Change line ~110 in analyze_picks.py:
    risked = sum(p["size_num"] for p in picks if p["result"] not in ("P", "VOID"))
```

### H-5 (MEDIUM) — VOID picks excluded from daily Discord recap

```
TRACK: H
FILE: engine/grade_picks.py
LINE: ~1979–1981
SEVERITY: MEDIUM
N: N/A
ISSUE: day_picks filter in _post_merged_recaps:
    day_picks = [r for r in main_rows
                 if r.get("date") == date_str
                 and r.get("result") in ("W", "L", "P")]
VOID picks are excluded. A premium pick that was DNP (VOID) disappears from the Discord
recap — subscribers see 5 picks on the card but only 4 in the recap.
IMPACT: Transparency gap. Subscribers tracking the card may notice the discrepancy.
FIX: Include VOID picks in day_picks with a distinct display label (e.g., "🚫 VOID — DNP").
Update _recap_pick_line() to handle result="VOID".
```

### CLV formula consistency — CORRECT within system
Both capture_clv and clv_report use the same raw vigged implied probability. CLV stored in pick_log.csv and CLV displayed in clv_report.py are consistent with each other. No inconsistency.

### Date filtering in clv_report — minor
`--days 30` uses inclusive comparison: picks on the cutoff date are included. This is 31 calendar days inclusive, not exactly 30. Intentional and expected behavior.

### Weekly vs daily VOID inclusion — minor inconsistency

```
TRACK: H
FILE: engine/grade_picks.py vs engine/weekly_recap.py
LINE: ~1337 (grade_picks) vs ~244–247 (weekly_recap)
SEVERITY: LOW
N: N/A
ISSUE: weekly_recap.filter_week() includes VOID in week's picks (result in "W","L","P","VOID").
grade_picks.get_graded_primary() excludes VOID (result in "W","L","P" only).
VOID picks appear in weekly embed but not in daily recap pick count.
IMPACT: Daily recap under-counts bets placed by number of VOIDs. No financial error.
FIX: Consistency choice — document or add VOID to daily recap pick list.
```
