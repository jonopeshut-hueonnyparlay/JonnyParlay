# JonnyParlay Full System Audit Prompt

Use this prompt to commission a complete line-by-line audit of the entire codebase.
Paste into a fresh Cowork session with the JonnyParlay folder mounted.

---

## PROMPT

You are auditing the JonnyParlay sports betting engine — a production Python system that runs daily, posts picks to Discord, logs results, and tracks CLV. Real money is on the line. Be thorough and unsparing.

**Audit every line of every file listed below. Flag anything that is broken, fragile, inconsistent, or silently wrong.**

### Files to audit (in order):

1. `engine/run_picks.py` — main engine (~4650 lines)
2. `engine/grade_picks.py` — grading + Discord recap
3. `engine/capture_clv.py` — CLV capture daemon
4. `engine/clv_report.py` — CLV analysis CLI
5. `engine/results_graphic.py` — PNG results card generator
6. `engine/analyze_picks.py` — backtest analysis dashboard
7. `engine/weekly_recap.py` — weekly P&L recap
8. `engine/morning_preview.py` — daily card announcement

### For each file, check:

**Correctness**
- Logic errors, off-by-one errors, wrong comparisons
- Math errors in edge/probability/CLV calculations
- Gates/rules that can be bypassed or fire incorrectly
- Any function that silently returns wrong results

**Data integrity**
- CSV read/write consistency — column counts, header mismatches, field ordering
- Pick_log paths — all must use `~/Documents/JonnyParlay/data/pick_log.csv` (with `data/` subdir)
- Dedup logic — any case where the same pick could be double-logged or double-posted
- Grading logic — any case where a win grades as loss or vice versa

**Robustness**
- Unhandled exceptions that would crash silently
- API failures with no fallback
- File not found cases that return wrong defaults instead of erroring
- Race conditions between daemon writes and engine reads to pick_log.csv

**Consistency across files**
- BOOK_DISPLAY dicts — are all 18 CO_LEGAL_BOOKS present in every file that has one?
- HEADER columns — do all write sites (primary log, bonus log, manual log, daily_lay log) write the same 27 columns in the same order?
- `is_home` field — logged correctly for SPREAD/ML/F5 picks? Read correctly at grade time?
- Book key normalization — are regional suffixes (e.g. `hardrockbet_fl`) handled consistently everywhere?
- Timezone handling — all Discord timestamps and date comparisons in correct timezone?

**Discord posting**
- Any webhook that could double-post on reruns
- Guard files / `_card_already_posted_today` — any edge case that bypasses the guard
- Any embed field that could overflow Discord's 1024-char field limit or 6000-char embed limit

**CLV daemon specifically**
- Capture window logic — is T-5 to T+1 min correct for all sports?
- Game matching (`game_str_matches`) — any case where the wrong event gets matched?
- Line matching (`best_price`) — could it grab the wrong side (over vs under, home vs away)?
- Write logic — could a CLV write corrupt an existing row?

**Performance / API usage**
- Any unnecessary API calls in hot loops
- Cache usage — is the 15-min odds cache in run_picks.py being used correctly?

### Output format:

For each issue found:
```
FILE: engine/xxx.py
LINE: ~NNN
SEVERITY: CRITICAL | HIGH | MEDIUM | LOW
ISSUE: [what is wrong]
IMPACT: [what breaks or goes wrong in production]
FIX: [exact code change needed]
```

Severity definitions:
- **CRITICAL**: picks miscalculated, wrong results graded, money miscounted, data corrupted
- **HIGH**: silent failures, wrong output, pick_log corruption risk
- **MEDIUM**: edge cases that could cause wrong behavior under specific conditions
- **LOW**: code smell, inconsistency, minor inefficiency

At the end, provide:
1. A prioritized fix list (CRITICAL first)
2. Any cross-file inconsistencies not covered above
3. Anything that looks intentional but is worth questioning

Do not summarize what the code does correctly. Only report problems.
