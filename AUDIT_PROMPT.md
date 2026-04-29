# JonnyParlay — Full System Audit Prompt

**Paste this into a new Claude conversation to start a comprehensive line-by-line audit.**

---

## Your task

Perform a full line-by-line audit of the JonnyParlay sports betting engine. This is a live production system that posts real picks to a Discord community, logs bets, captures closing line value, and grades results automatically. It has undergone many recent changes and Jono wants confidence that every system is correct, consistent, and robust.

**You are not writing new features.** You are hunting bugs, inconsistencies, dead code, silent failures, API assumption drift, concurrency issues, and anywhere reality doesn't match intent.

---

## Project context

- **Repo root:** `/sessions/<session>/mnt/JonnyParlay/` (Cowork mount) · Windows path: `C:\Users\jono4\Documents\JonnyParlay\`
- **Source of truth:** `engine/` directory. Root-level copies are synced from there (`cp engine/X.py X.py`).
- **Memory:** `CLAUDE.md` — read this FIRST. It has the schema, tier rules, file map, glossary, and current operational state.
- **Daily flow:**
  1. `run_picks.py nba.csv` — generates picks, posts Discord card, logs to `data/pick_log.csv`
  2. CLV daemon (`capture_clv.py`) — runs on Windows Task Scheduler daily at 10am, captures closing odds 2-3 min before gametime
  3. `grade_picks.py` — grades the log after games finish, posts recap + results graphic
  4. `weekly_recap.py` — Sunday weekly P&L
  5. `morning_preview.py` — daily card teaser

## Files to audit (priority order)

### Core engine (highest priority, largest surface area)
1. **`engine/run_picks.py`** — ~4700 lines. The whole pick generation pipeline. VAKE sizing, tier assignment, Discord posting, pick logging, context scanner, correlation caps, directional balance, etc.
2. **`engine/grade_picks.py`** — ~1600 lines. Grading logic for props, game lines, daily lay parlays, MLB F5/NRFI, Discord recap posting, monthly summaries.
3. **`engine/capture_clv.py`** — ~843 lines. CLV daemon. Polls Odds API every 2 min, matches picks to closing odds, writes back `closing_odds` + `clv`. Has single-instance guard + ghost-game checkpoint integrity.

### Support scripts
4. `engine/clv_report.py`
5. `engine/results_graphic.py`
6. `engine/analyze_picks.py`
7. `engine/weekly_recap.py`
8. `engine/morning_preview.py`
9. `post_nrfi_bonus.py`
10. `test_context.py`

### Operational glue
11. `start_clv_daemon.bat` — Windows batch launcher
12. `setup_clv_task.ps1` — Task Scheduler registration

### Data schema
13. `data/pick_log.csv` — header + row format. Schema is in CLAUDE.md. **Verify every writer produces 27 fields matching the header.** We recently caught a truncated row from a concurrent-write race.

---

## Audit categories — check every file against all of these

### 1. Name / string matching
We found **two** recent bugs where fuzzy name matching grabbed the wrong record:
- Player props: `"Wendell Carter Jr"` → fuzzy last-name match on `"jr"` grabbed a different "Jr." in the box score. Fixed by punctuation normalization + suffix-aware token logic.
- Daily lay legs: `"Oklahoma City Thunder -6.5"` → split on whitespace, took `parts[1]` as spread which is actually `"City"`. Fixed by extracting spread from last numeric token.

**Look for:** any `.split()[0]`, `.split()[-1]`, or `in key.lower()` substring match that could false-positive. Especially:
- 2-letter team abbrevs (`SD`, `LA`, `SF`, `TB`, `KC`, `NY`) embedded in other words
- Suffix-sensitive player names (Jr., Sr., II, III, IV, V)
- Punctuation differences between source and pick log (periods, apostrophes, accented chars)
- Multi-word team names in any parser

### 2. API payload assumptions
We found one bug where `flatten_outcomes` collapsed both `name` and `description` into a single field, breaking player prop direction matching.

**Look for:** any place that reads Odds API `outcomes`, ESPN box scores, NBA stats, NHL API, MLB stats API. Verify it handles:
- Player props: `name="Over"/"Under"`, `description="<player>"`
- Game lines: `name="<team>"` or `name="Over"/"Under"`, no `description`
- Spread/ML with 2-letter abbrev teams
- Tie scores, OT games, suspended/postponed games
- Empty/null fields (especially `point`, `price`)

### 3. Concurrency / race conditions
Three writers can touch `pick_log.csv`:
- `run_picks.py` — appends primary picks, bonus picks, daily lay rows
- `capture_clv.py` — daemon rewrites entire file every 2 min during capture window
- `grade_picks.py` — rewrites entire file when filling in results

We added a shared `FileLock` at `pick_log.csv.lock` for all three. **Verify every single open() on pick_log is wrapped in the lock** (both reads and writes, since a read during a daemon rewrite can get a truncated file).

Same check for:
- `pick_log_manual.csv`
- `pick_log_mlb.csv` (shadow MLB log)
- `discord_posted.json` (posting guard)
- `clv_checkpoint.json` (daemon checkpoint)

### 4. Sizing consistency
The bonus drop had a sizing bug where it retained `size_picks_base` output (1.25u cap) instead of VAKE-adjusted size. We added `size_bonus_pick()`.

**Look for:** every path where `pick["size"]` is set. Verify:
- Primary picks → `size_picks_vake`
- Bonus picks → `size_bonus_pick` (new this session)
- Daily lay → hardcoded 0.50u
- KILLSHOT → `_killshot_size` (based on pick_score: 90-100=3u, 100-110=4u, 110+=5u, weekly cap 3)
- Manual picks → user-entered
- Every size is in `[0.25, 5.0]` range
- Every pick logged to `pick_log.csv` has a non-empty `size` field

### 5. Logged row completeness
Every row written to `pick_log.csv` MUST have all 27 schema fields (even if blank). We found one row with only 17 fields (concurrent-write truncation).

**Run:** `grep -v "^date" data/pick_log.csv | awk -F',' '{ n = NF; if (n != 27) print n" fields: "$0 }'` to find any truncated rows.

### 6. Silent failures
**Look for:** every `except Exception`, `except:`, `pass`, `return None` path. Verify:
- Errors are logged (not swallowed)
- Fallbacks are sensible (don't silently produce zero/empty data)
- Critical failures stop the pipeline (don't post a card with 0 picks)

### 7. Config drift / hardcoded paths
CLAUDE.md lists:
- Windows path: `C:\Users\jono4\Documents\JonnyParlay\`
- Cowork mount: `/sessions/.../mnt/JonnyParlay/`
- Odds API key: `adb07e9742307895c8d7f14264f52aee`
- `espnbet` API key → displayed as `theScore Bet`
- 18 CO_LEGAL_BOOKS

**Verify:** no stale paths (e.g., `mbp/` is retired), consistent book name normalization, API key not leaked to logs, book display names consistent across engine/grader/reporter.

### 8. Tier / run_type / stat value consistency
CLAUDE.md schema says:
- `run_type`: `primary | bonus | manual | daily_lay`
- `tier`: `T1 | T1B | T2 | T3 | KILLSHOT | DAILY_LAY`
- `stat`: `SOG | PTS | REB | AST | 3PM | SPREAD | ML_FAV | ML_DOG | TOTAL | TEAM_TOTAL | F5_ML | F5_SPREAD | F5_TOTAL | PARLAY`

**Look for:** any tier/stat/run_type assignment that uses a different string. Case mismatches. Missing values.

### 9. Shadow-sport isolation
MLB is in `SHADOW_SPORTS` — picks go to `pick_log_mlb.csv`, NOT posted to Discord, NOT captured by CLV daemon (unless `ENABLE_SHADOW_CLV=True`).

**Verify:**
- No MLB picks leak into Discord recap, weekly recap, results graphic
- No MLB picks leak into the main `pick_log.csv`
- CLV daemon truly skips shadow logs by default
- Analyzer includes shadow only with `--shadow` flag

### 10. Discord posting guards
`discord_posted.json` prevents double-posting. Keys like `daily_lay:2026-04-19`, `card_announcement:2026-04-19`, etc.

**Verify:**
- Every Discord post path checks the guard before posting
- Guard is updated BEFORE the post, not after (fail-safe)
- `--repost` flag bypasses the guard correctly
- Guard keys are unique and correctly formatted

### 11. Context sanity system (disabled by default)
`--context` flag enables a Haiku-based pre-game scanner. The code is in `run_picks.py` but disabled on normal runs.

**Verify:**
- Disabled-by-default doesn't leak context fields to the pick log
- When enabled, it cuts `conflicts` picks and annotates `supports`
- Error in the Anthropic API call doesn't block pick generation

### 12. Dead code / obsolete paths
Recent refactors may have left unreachable branches. Look for:
- Functions called from nowhere
- Config constants never read
- Obsolete file paths (e.g., `mbp/`)
- Feature flags that are always True/False

---

## PICK LOG AUDIT (dedicated section — critical)

The CSV files in `data/` are the source of truth for every dollar wagered. They're read by grading, CLV capture, weekly recap, analyzer, dashboard, results graphic, and monthly summaries. A corrupted row poisons all of them.

Audit all three log files:
- `data/pick_log.csv` — main (primary + bonus + daily_lay)
- `data/pick_log_manual.csv` — manual picks
- `data/pick_log_mlb.csv` — shadow MLB

Plus the backup: `data/pick_log.backup-pre-manual-split.csv` (verify it's actually pre-split and not actively written to).

### A. Schema integrity — run on every row

**Field count:** every non-header row must have exactly 27 comma-separated fields. Run:
```bash
awk -F',' 'NR>1 && NF!=27 { print NR": "NF" fields | "$0 }' data/pick_log.csv
```
(Any output = bug. We found one on 2026-04-19 due to a concurrent-write race, since patched with filelock.)

**Header match:** the first line must exactly equal:
```
date,run_time,run_type,sport,player,team,stat,line,direction,proj,win_prob,edge,odds,book,tier,pick_score,size,game,mode,result,closing_odds,clv,card_slot,is_home,context_verdict,context_reason,context_score
```

**Field-level type checks (per-row):**
| Field | Rule |
|-------|------|
| `date` | YYYY-MM-DD |
| `run_time` | HH:MM (24h) or blank for legacy rows |
| `run_type` | one of: `primary`, `bonus`, `manual`, `daily_lay` |
| `sport` | `NBA`, `NHL`, `NFL`, `MLB`, `NCAAB`, `NCAAF`, `TENNIS`, `GOLF`, or blank (daily_lay only) |
| `stat` | one of the documented stat codes (SOG, PTS, REB, AST, 3PM, SPREAD, ML_FAV, ML_DOG, TOTAL, TEAM_TOTAL, F5_ML, F5_SPREAD, F5_TOTAL, PARLAY, plus NRFI/YRFI/TDS/GOALS/HA/HITS/K/OUTS/TB/HRR for shadow or specialty) |
| `line` | float or blank (PARLAY/ML rows) |
| `direction` | `over`, `under`, `cover`, or blank |
| `proj` | float or blank |
| `win_prob` | float 0.0–1.0 or blank |
| `edge` | float (can be negative) or blank |
| `odds` | integer (American odds) or blank — sanity range: -10000 to +10000 |
| `book` | one of the 18 CO_LEGAL_BOOKS display names |
| `tier` | `T1`, `T1B`, `T2`, `T3`, `KILLSHOT`, `DAILY_LAY` |
| `pick_score` | float or blank (blank for bonus/daily_lay) |
| `size` | float 0.25–5.0 |
| `game` | non-empty string (for game context) |
| `mode` | string or blank |
| `result` | `W`, `L`, `P`, `VOID`, or blank (ungraded) |
| `closing_odds` | int or blank |
| `clv` | float or blank |
| `card_slot` | 1-5 or blank |
| `is_home` | `True`, `False`, or blank |
| `context_verdict` | `supports`, `neutral`, `conflicts`, `skipped`, or blank |
| `context_reason` | string or blank |
| `context_score` | int or blank |

Flag every row that violates any of these.

### B. Duplicate detection

Two rows are duplicates if `(date, player, stat, line, direction)` match. **No two rows should be dupes unless one is a legitimate multi-run log** (e.g., morning primary + afternoon bonus of the same leg). Flag all duplicates and classify:
- Intended multi-run (different `run_type`) → OK
- Exact same `run_type` → BUG

### C. Orphans / ghosts

- Rows with game dates older than 14 days and `result=""` → grader missed them
- Rows with `closing_odds` filled but `clv` empty (or vice versa) → inconsistent CLV write
- Rows with `result` set but `closing_odds`/`clv` empty when game is ≥ 2h past tipoff → CLV daemon missed them
- Rows with `tier=DAILY_LAY` but `run_type != daily_lay` (or vice versa) → misrouting
- Rows with `card_slot` filled but `run_type != primary` → shouldn't happen
- Rows with `card_slot` empty but `run_type == primary` → primary picks must have a slot 1-5

### D. CLV coverage rate

Count: for rows with `date >= 2026-04-14` (when logging started) and `run_type in (primary, bonus, daily_lay)` and game is confirmed complete:
- What % have `closing_odds` populated?
- What % have `clv` populated?
- Break down by sport — if NBA is 90% but NHL is 30%, there's a sport-specific matcher bug.
- Break down by `stat` — if SPREAD is 95% but 3PM is 40%, there's a prop-type matcher bug.

Report the coverage matrix.

### E. Grade coverage rate

For rows with game dates ≥ 3 days ago:
- % graded (result is W/L/P/VOID)
- % ungraded
- List every ungraded row with date older than 3 days — these are grading failures.

### F. Size-sanity sweep

For every row:
- `size == 0` or `size == ""` → BUG (unposted pick shouldn't be logged, and every posted pick has a size)
- `size > 5.0` → BUG (KILLSHOT ceiling is 5u)
- `size < 0.25` → BUG (below minimum floor)
- `tier == T3 and size > 0.75` and `run_type == primary` → possible sizing bug (T3 primary should cap ~0.50u)
- `tier == KILLSHOT and size not in (3, 4, 5)` → BUG (KILLSHOT sizing is discrete)

### G. Book name consistency

Every row's `book` field must match one of the 18 CO_LEGAL_BOOKS **display names** (not API keys). Specifically:
- If you see `espnbet` anywhere in the `book` column → BUG (should be displayed as "theScore Bet")
- If you see raw API keys like `williamhill_us`, `hardrockbet`, `fliff` → BUG (should be the display name)
- Typos, trailing spaces, inconsistent casing → flag

### H. Cross-log integrity

- Any row in `pick_log.csv` with `sport == MLB`? → BUG (should be in `pick_log_mlb.csv`, since MLB is still shadow)
- Any row in `pick_log_manual.csv` with `run_type != manual`? → BUG
- Any row in `pick_log_mlb.csv` with `sport != MLB`? → BUG
- Any row appearing in both `pick_log.csv` and `pick_log_manual.csv`? → BUG (double-log)

### I. Timeline / monotonicity

- `date` should be monotonically increasing (roughly — within a date, run_time can vary).
- No rows with `date` in the future (except for T+1 picks posted the night before, allowable within 12h).
- No rows with `date` before 2026-04-14 (main log) or before the manual split backup date (manual log).

### J. Discord-Discord consistency

Cross-check the `discord_posted.json` guard keys against the log:
- Every `daily_lay:YYYY-MM-DD` guard should have a matching `daily_lay` row in the log for that date.
- Every `killshot:*` guard should have a KILLSHOT row.
- Orphan guards (posted to Discord but not logged) → BUG
- Orphan log rows (logged but no Discord guard) → means it wasn't actually posted, flag for investigation.

### K. Backup files

- `pick_log.backup-pre-manual-split.csv` — verify it's not being written to, verify its last-modified date is older than the manual split was made, verify it's not a duplicate of the current main log.
- Any `.tmp` files left over in `data/` → indicates a crashed atomic-replace write, BUG.

---

**Output a separate `PICK_LOG_AUDIT.md` file at `/sessions/<session>/mnt/JonnyParlay/PICK_LOG_AUDIT.md` with:**
- Summary counts (total rows per log, graded %, CLV coverage %)
- A table of every row-level violation (severity, row number, field, issue)
- Every duplicate pair
- Every orphan
- Every size/book/tier anomaly
- Timeline anomalies
- Cross-log leakage
- Recommended cleanups (which rows to fix, which to delete, which to re-grade)

---

## Known-good reference patterns

Use these as "gold standard" shapes when you find anything that looks different:

**pick_log.csv row (27 fields):**
```
date, run_time, run_type, sport, player, team, stat, line, direction,
proj, win_prob, edge, odds, book, tier, pick_score, size, game, mode,
result, closing_odds, clv, card_slot, is_home, context_verdict,
context_reason, context_score
```

**File lock pattern (from `capture_clv.py` / `grade_picks.py`):**
```python
if _HAS_FILELOCK:
    with FileLock(str(log_path) + ".lock", timeout=30):
        # read-check-write all inside the lock
        ...
```

**Atomic rewrite pattern:**
```python
tmp_path = log_path.with_suffix(log_path.suffix + ".tmp")
with open(tmp_path, "w", ...) as f:
    ...
os.replace(tmp_path, log_path)
```

---

## Expected output

For each file, produce:

1. **Summary** — one paragraph: what the file does, overall health, rough line count.
2. **Issues found** — structured list:
   - **Severity:** CRITICAL (silent data corruption / wrong picks / money-affecting) / HIGH (breaks a feature) / MEDIUM (edge case / future-breaking) / LOW (cosmetic / style)
   - **Location:** `filename:line_number`
   - **What it does now:** 1-2 sentences
   - **Why it's wrong:** 1-2 sentences
   - **Suggested fix:** code snippet or description
3. **Cross-file inconsistencies** — if a function in one file expects something a caller in another doesn't provide.
4. **Dead code found**
5. **Open questions** — anything you can't verify without running it live or seeing production data.

**Do NOT fix anything.** Just report. Jono will triage and decide which fixes to ship.

---

## EXHAUSTIVENESS — nothing gets skipped

This audit must be **line-by-line, function-by-function, file-by-file**. Every line of code has to be touched. If you're tempted to summarize a section as "looks standard" — stop and read it anyway.

In addition to the categories above, check these:

### 13. Every import and dependency
- Every `import X` — is X actually used in the file? Unused imports flagged.
- Every external package (`filelock`, `anthropic`, `pandas`, `requests`, etc.) — pinned version? Installed on Windows? Fallback if missing?
- Relative imports between engine files — any circular imports? Any import-time side effects?
- `sys.path` manipulations — correct?

### 14. Every function signature
- Docstring matches actual behavior?
- Arguments documented?
- Return type consistent across all code paths?
- Any function that sometimes returns `None`, sometimes `""`, sometimes `0` — flag as inconsistent.
- Any function over 100 lines — flag as refactor candidate.

### 15. Every external API call
- Odds API: every `GET /v4/sports/...` endpoint — correct params, key, region, markets?
- ESPN NBA / NHL / MLB stats APIs — correct endpoints, auth, user-agent?
- Anthropic API (context system) — correct model, timeout, retry?
- Every Discord webhook — correct URL, payload, rate limit handling?
- Every API call must have: timeout, error handling, retry policy (where appropriate), and rate-limit awareness.
- Every API response parse — handles `None` fields, missing keys, empty lists, malformed JSON.

### 16. Every env var and secret
- Every `os.environ.get(...)` — has a sensible fallback? Logged if missing?
- Every hardcoded API key or webhook URL — is it supposed to be hardcoded? (Odds API key is; webhooks are per-channel.)
- Any secret printed to logs or Discord embeds? → CRITICAL.
- Any `.env` file referenced that isn't in the repo? → document required env setup.

### 17. Every constant — is the value still correct?
CLAUDE.md documents values like:
- `MIN_DAILY_LAY_PROB = 0.33`
- `MIN_DAILY_LAY_MARGIN = 4.0`
- Bonus: min score 65, min win prob 0.65, max 5/day
- KILLSHOT: score ≥ 90, weekly cap 3
- Premium: 5 picks (do NOT change)
- Capture window: T-30 to T+3 min

**Verify every one of these constants in the code matches CLAUDE.md.** If CLAUDE.md and code disagree, one is wrong — flag which.

### 18. Every print / log / Discord message
- Any PII (real player home addresses, contact info, etc.) in logs? Shouldn't be.
- Any API keys or webhook URLs in logs?
- Any message that's confusing or outdated (e.g., references features that were removed)?
- Every `print(f"...")` — properly formatted, no broken f-strings?
- Unicode handling: any emoji or non-ASCII chars that might break on Windows cp1252?

### 19. Every boundary condition
For every numeric input, test mentally:
- Zero
- Negative
- Empty string / None
- NaN / infinity
- Very large (e.g., 999999)
- Float vs int mismatch
- String with only whitespace

For every list/dict:
- Empty
- Single element
- Duplicates
- Missing expected keys

### 20. Every timezone handling
The engine runs in America/New_York time (see `ZoneInfo` usage).
- Every `datetime.now()` without a timezone → BUG (should be `datetime.now(ZoneInfo("America/New_York"))`)
- Every date comparison crosses midnight correctly?
- Every `strftime` uses consistent format?
- CLV daemon capture window — T-30 uses game start time in what TZ? Correct relative to book's cutoff?

### 21. Every Windows-specific concern
- Path separators — use `Path` or `os.path.join`, never hardcoded `/` or `\\`
- `python -u` and `PYTHONUNBUFFERED=1` in every daemon launcher (required for S4U logon)
- Task Scheduler: S4U logon flag, WakeToRun, correct working directory
- Batch files: `chcp 65001` for UTF-8, proper quoting
- `.lock` file cleanup on crash
- File encoding: every `open()` should specify `encoding="utf-8"`

### 22. Every test / debug artifact
- `test_context.py` — still working? Referenced anywhere?
- Any `if __name__ == "__main__": test_xxx()` blocks — do they run?
- Any commented-out code that should be deleted?
- Any `TODO`, `FIXME`, `XXX`, `HACK` comments — list them all.
- Any `print("debug: ...")` left in production code?

### 23. Documentation drift (CLAUDE.md vs reality)
- Every file listed in CLAUDE.md's "Key Files" table exists and has the documented purpose?
- Every term in the glossary matches its definition in code?
- Every workflow described ("Daily Routine", "CLV Daemon") matches the actual code?
- Every path in CLAUDE.md exists on both Windows and Cowork mount?
- `CLAUDE.md` last-updated — any section stale?

### 24. Git state
- `.gitignore` — does it cover all secrets, logs, lock files, tmp files?
- Any committed file that shouldn't be (API keys, webhook URLs, personal data)?
- Any recent commits with "WIP", "test", "hack" messages that need followup?
- Any local-only changes in `engine/` that aren't in root (or vice versa)?

### 25. Line count reconciliation
CLAUDE.md says `run_picks.py` is ~4700 lines. Actual count?
Any file ballooning over 1000 lines without clear module structure → refactor candidate, flag.

### 26. Error messages to the user
When something goes wrong, does the user know:
- What failed
- Where (file + approximate location)
- What to do about it

Silent swallowing of errors anywhere → CRITICAL.

### 27. Every Discord embed
- Field limits (25 fields, 1024 chars per field value, 2000 chars total for `description`)
- Character escaping (especially user-typed player names with special chars)
- Color / thumbnail / footer consistency with brand (picksbyjonny aesthetic)
- Mobile rendering (long field names can wrap badly)
- `@everyone` ping only where explicitly allowed (KILLSHOT, daily lay)
- Every embed posted also persists to the log with the correct row

### 28. Data persistence everywhere
- Every mutation to state (pick log, discord_posted.json, clv_checkpoint.json) — durable on crash?
- Every checkpoint write — atomic (tmp + rename)?
- Every counter / guard — survives process restart?
- Every cache — has a TTL? Cleared on run?

### 29. Every command-line flag
For each script, list every `argparse` flag and verify:
- It's documented in `--help`
- It's documented in CLAUDE.md if it's a user-facing flag
- It does what the name suggests (no surprising behaviors)
- Combinations don't conflict (e.g., `--repost --dry-run` should be coherent)

### 30. Scheduled task / daemon health
- CLV daemon: S4U logon, WakeToRun, filelock, ghost-game checkpoint integrity
- Grade_picks: any scheduled trigger? Currently manual, correct?
- Morning preview, weekly recap: when do they fire, how?
- Every script that runs unattended — does it have proper error recovery, no interactive prompts?

### 31. Math / statistics correctness (money-affecting)
- American-to-decimal odds conversion — boundary cases `-100`, `+100`, `0`, `±∞`
- Decimal-to-implied-prob — correct formula? (`1/decimal`)
- Implied prob subtraction for CLV — sign convention right? (`closing_ip − opening_ip` = positive when beat the close)
- Kelly criterion / VAKE base sizing — formula correct? Capped correctly?
- Win-prob floor / edge floor — applied in the right order?
- Pick Score formula — inputs, weights, normalization. Any division-by-zero? Any log/sqrt of negative?
- Parlay odds multiplication — correct combination of American odds across legs?
- Break-even win rate — implied from odds correctly?

### 32. Correlation / exposure / portfolio rules
- Max picks per game (G7 rule: max 2)
- Max pitcher props per pitcher (G11: 0)
- Max batter correlated props per batter (G11b: 0)
- Same-stat same-direction cap (R10)
- No U2.5 AST / U2.5 REB / REB Overs (R4, R11)
- No line ≤ 1.5 on AST/REB/SOG/K/HA/HITS (G8)
- Max odds ≤ -150 (G7)
- Daily unit cap (12u) and check (1.00u minimum)
- **Verify every one of these rules is enforced in code, and that the code matches the picks file footer** (the "OUTPUT VERIFICATION CHECKLIST" section shows which rules were enforced)

### 33. Card composition rules
- Premium = exactly 5 picks (hard rule per CLAUDE.md)
- Directional balance: max 1 overs / 1 unders on Premium (R9)
- Safest 5 — how selected?
- Tier distribution — any constraints?
- Sport distribution — does the card ever end up mono-sport by accident?
- Fallback when fewer than 5 qualify — warn loudly? Degrade gracefully?

### 34. Odds / line dedup
- Same player + stat + direction across multiple books — which book wins?
- Same player + stat + direction + multiple lines — which line is picked?
- Is there a "best available" logic and is it correctly finding the line with highest +EV?

### 35. CSV parsing edge cases
- Commas in player names (D'Angelo Russell, R.J. Barrett) — quoted correctly in output?
- Quotes in strings — escaped correctly?
- Embedded newlines in game strings — handled?
- BOM markers at file start — `utf-8-sig` needed anywhere?
- Mixed line endings (CRLF on Windows vs LF) — consistent?
- Empty trailing line at end of file — doesn't break parser?

### 36. Discord webhook resilience
- Rate-limit response (HTTP 429) — does code back off and retry?
- 5xx errors — retry with exponential backoff?
- Webhook URL invalidated — logged clearly so Jono can rotate?
- Payload too large (>2000 chars description, >25 embed fields) — truncated or rejected?
- Queue of pending posts if Discord is down — does anything queue, or do they silently fail?

### 37. Odds API quota & caching
- How many API calls per run?
- Are responses cached per-day to avoid redundant calls?
- What's the monthly quota, what's current usage?
- On quota-exceeded response — graceful degradation?
- Are prop-specific calls (separate endpoint per market) de-duped?

### 38. Memory / resource leaks
- CLV daemon runs for hours — any unbounded growth? (dict grows with each game, does it get pruned?)
- Any open file handles not closed? (Should all use `with` blocks.)
- Any list/dict append without eviction?

### 39. Log file rotation
- `jonnyparlay.log` — size-capped? Rotated? Ever pruned?
- `clv_daemon.log` — same questions
- After 6 months, will the logs be unmanageable?

### 40. Backtest / analysis correctness (`analyze_picks.py`)
- ROI calculation — American odds handled correctly?
- Variance / Sharpe — proper formula?
- Filtering — date range, sport, tier, stat — all work independently and in combination?
- Shadow log inclusion via `--shadow` flag — correct?
- Date parsing — doesn't include today's ungraded picks?
- Divisor for win rate — excludes VOIDs? (Should.)

### 41. Results graphic (`results_graphic.py`)
- PNG generation — fonts load correctly on Windows?
- Layout — correct when 0 picks, 1 pick, 10 picks?
- Branding (picksbyjonny luxury aesthetic) — colors, spacing, typography match brand?
- File size — acceptable for Discord upload?
- Failure mode — if graphic generation fails, does recap still post?

### 42. Performance
- `run_picks.py` end-to-end runtime — reasonable?
- Parallel where possible — ThreadPoolExecutor usage correct (no shared-state races)?
- Any O(n²) loops that could be O(n)?
- Any repeated API calls that could be batched?

### 43. Historical / re-run safety
- Re-running `run_picks.py` for a past date — does it work? Does it duplicate?
- Re-running grader for a past date — idempotent?
- Re-posting to Discord — guard prevents dupes?
- Backfilling CLV for past picks — supported?

### 44. Model calibration loop
- Anywhere that compares proj to actual?
- Any calibration that adjusts projections based on historical accuracy?
- If yes — is it correct?
- If no — should there be one?

### 45. SaberSim CSV input assumptions
- Required columns documented somewhere?
- What if SaberSim changes their column names — does code fail loudly or silently use wrong data?
- Encoding (UTF-8 / Latin-1 / Excel-flavored)?
- Missing rows / blank rows — handled?

### 46. Path / home-directory handling
- `~/Documents/JonnyParlay/` relies on `$HOME` being set correctly
- Running under Task Scheduler S4U logon — is $HOME set?
- Running under different user accounts — path breaks?
- Any `os.getcwd()` usage that assumes working directory?

### 47. Unicode / accented player names
- Nikola Jokić, Luka Dončić, Alperen Şengün — stored correctly in log?
- Matched correctly between SaberSim (may strip accents) and Odds API (may keep accents)?
- Discord renders them correctly?
- Results graphic fonts support extended Latin?

### 48. Exit codes
- Every script exits `0` on success, non-zero on failure?
- Batch files check exit codes and log them?
- Task Scheduler can detect failed runs?

### 49. Defensive programming
- Every dict access — uses `.get()` with default, or is `KeyError` acceptable?
- Every list index — bounded, or does `IndexError` crash the daemon?
- Every type conversion — `try/except ValueError` where input is untrusted?
- Every API response — checks status code before parsing JSON?

### 50. Thread safety
- `ThreadPoolExecutor` used in `run_picks.py`, `capture_clv.py` (at minimum) — any shared mutable state accessed without a lock?
- Any module-level dict / list that multiple threads mutate?
- Any counter increment that's not atomic?

### 51. Schema migration logic
- `run_picks.py` line 2980ish: "If header has changed (new columns added), rewrite the file with updated header"
- Does it handle column removal? Reordering? Renaming?
- Does it preserve existing rows' data correctly through migration?
- Is the migration atomic (locked)?

### 52. Book closing-time awareness
- Different books close markets at different times pre-game
- CLV daemon capture window is T-30 to T+3 — does it need to be book-specific?
- Is there a sport-specific adjustment (e.g., NHL vs NBA close differently)?

### 53. Tournament / playoff special cases
- NBA playoffs / NHL playoffs / NFL playoffs — any code that treats these differently?
- Overtime rules — SPREAD lines include OT? Player props include OT?
- Game-7 scenarios (rare, high-leverage) — handled?

### 54. Env vars & $HOME on Task Scheduler S4U logon
- S4U sessions have different env than interactive sessions
- `$HOME`, `%USERPROFILE%`, `%TEMP%` — all set correctly under S4U?
- `ANTHROPIC_API_KEY` if context system enabled — loaded from where?
- `PYTHONIOENCODING=utf-8` and `PYTHONUNBUFFERED=1` set?

### 55. Every `TODO` / `FIXME` / `XXX` / `HACK` / `WIP` comment
Grep all source for these and list every one. Each is either:
- Done → delete the comment
- Still pending → promote to issue

### 56. Every `pass` statement
Every `pass` statement in the codebase: is it intentional? In an `except: pass` block, is swallowing the error justified?

### 57. Every `# type: ignore`, `# noqa`, or silenced warning
Why was it silenced? Is it still justified?

### 58. Every magic number
Any numeric literal that isn't obvious (0, 1, 2, 100) → should be a named constant with a comment explaining what it represents.

### 59. Every regex
Every `re.compile` / `re.match` / `re.search` / `re.sub`:
- Does it handle edge cases in input?
- Is it anchored correctly (`^` / `$`)?
- Is it using `re.escape` for user-supplied fragments?
- Is it tested against the actual data it matches?

### 60. Every f-string
- No broken `{}` syntax?
- No unescaped `{` / `}` where literal braces intended?
- Consistent formatting precision (`.2f`, `.4f`, etc.)?
- No accidental silent failures from missing attributes?

---

## NEW SECTIONS — added Apr 24 2026 (post-session additions)

The following features were added or heavily modified in the session that preceded this audit. These must be audited with extra scrutiny.

### 61. New pick types — SGP, Longshot, Gameline

Three new `run_type` values are now supported:
- `sgp` — Same-Game Parlay (built by `engine/sgp_builder.py`)
- `longshot` — Longshot parlay (multi-leg, high payout, low stake)
- `gameline` — Game line manual picks (SPREAD, ML, TOTAL etc. logged via `--log-manual`)

**Verify everywhere `run_type` is consumed:**
- `grade_picks.py` — `COUNTED_RUN_TYPES`, `MODEL_RUN_TYPES`, grading dispatch (`grade_parlay_legs()` for sgp/longshot)
- `capture_clv.py` — does it skip sgp/longshot rows correctly? (They have no individual closing line to capture.)
- `analyze_picks.py` — includes sgp/longshot in P&L? Filters work?
- `weekly_recap.py` — P&L correct across all run_types?
- `clv_report.py` — sgp/longshot excluded from CLV metrics (no individual closing line)?
- `discord_posted.json` guard — sgp/longshot have their own guard keys?
- Any `run_type == "primary"` or `in ("primary", "bonus", "daily_lay")` hardcoded check — is it missing the new types?

### 62. pick_log.csv schema v3 — `legs` column (28 fields)

Schema bumped from v2 (27 cols) to v3 (28 cols). New column: `legs` — JSON array of parlay leg detail for sgp/longshot rows.

**Verify:**
- `engine/pick_log_schema.py` — `SCHEMA_VERSION = 3`, `CANONICAL_HEADER` has exactly 28 fields, `_V3_COLUMNS = frozenset(["legs"])`, assertions for both v2 and v3 columns present.
- Every writer that appends to `pick_log.csv` (run_picks.py, sgp_builder.py, grade_picks.py) writes all 28 fields.
- Non-parlay rows (primary, bonus, daily_lay, gameline, manual) write `legs = ""` (blank), not missing.
- `grade_picks.py` — `grade_parlay_legs()` correctly parses `legs` JSON and dispatches per-leg grading.
- Schema field-count check: run `awk -F',' 'NR>1 && NF!=28 { print NR": "NF" fields | "$0 }' data/pick_log.csv` — any output = bug.
- Header must now be exactly: `date,run_time,run_type,sport,player,team,stat,line,direction,proj,win_prob,edge,odds,book,tier,pick_score,size,game,mode,result,closing_odds,clv,card_slot,is_home,context_verdict,context_reason,context_score,legs`
- Migration: both `pick_log.csv` and `pick_log_manual.csv` were migrated from v2→v3. Verify no rows lost, no field shifted.
- Root-level `pick_log_schema.py` is synced with `engine/pick_log_schema.py`.

### 63. SGP builder — `engine/sgp_builder.py`

New file (~769 lines). Standalone module, also callable from `run_picks.py` via `run_sgp_builder()`.

**Audit checklist:**
- `run_sgp_builder(csv_paths, dry_run, confirm, test, cached_odds, save)` — all six params present in signature? (`save=True` was a late fix — verify it didn't get dropped.)
- `post_sgp(legs, parlay_odds, game, suppress_ping, today_str, save)` — `save` param used correctly to gate `_log_sgp()`?
- `_log_sgp(legs, parlay_odds, game, today_str, book)` — writes exactly 28 fields, book field populated, legs JSON valid.
- `build_sgp_embed()` — shows `📍 Bet on: **{book}**` line, shows per-leg odds, correct formatting.
- `_sgp_book(legs)` — modal book logic, prefers DK/FanDuel on ties.
- Constants: `MIN_LEGS=6`, `MAX_LEGS=6`, `MIN_PARLAY_ODDS=400`, `MAX_PARLAY_ODDS=700`, `MAX_LEG_ODDS=-150`, sweet spot +500 in `_score_sgp`.
- `build_candidate_legs()` — `if odds > MAX_LEG_ODDS: continue` filter present? `if odds < -300: continue` still there?
- `_generate_thesis()` — direction-aware (overs vs unders)? No "stat-stuffing" on under-heavy stacks?
- `_is_negatively_correlated()` — all 4 rules (R0–R3) correct?
- Correlation tags — `team_off_`, `team_reb_`, `team_def_vs_` scoped to team correctly?
- `_parlay_american()` — decimal conversion correct for both positive and negative leg odds?
- `today_str` passed to both `post_sgp()` call sites in `run_sgp_builder()`?
- Root `sgp_builder.py` synced with `engine/sgp_builder.py`?
- CLi `__main__` block — correct argparse, no `save` param in CLI (save=True by default from CLI)?

### 64. `run_picks.py` — SGP/Longshot/Gameline integration

**Verify these specific new integration points in `run_picks.py`:**
- `run_sgp_builder()` call passes `save=_sgp_save` (not hardcoded True/False).
- `_sgp_dry` computed as `args.dry_run or args.no_discord` — correct gate?
- `_sgp_save` computed as `not args.no_save` — correct gate?
- `post_longshot()` called with `save=_save` — consistent with other save gates?
- `--log-manual` gameline classification: stat in `_gameline_stats` → `run_type="gameline"`, else `"manual"`.
- `_gameline_stats` set covers: `{"SPREAD", "ML_FAV", "ML_DOG", "TOTAL", "TEAM_TOTAL", "F5_SPREAD", "F5_ML", "F5_TOTAL", "NRFI", "YRFI", "GOLF_WIN"}` (verify exact set).
- New tiers `SGP` and `LONGSHOT` — do any tier-gated checks (`if tier == "T1"` etc.) accidentally block them?
- `COUNTED_RUN_TYPES` in run_picks.py (if it exists there) — includes all 7 types?

### 65. `grade_picks.py` — new grading paths

**Verify:**
- `grade_parlay_legs(row, all_player_stats, all_scores)` — added after `grade_daily_lay()`, dispatched before daily_lay check in the grading loop.
- `sgp` and `longshot` rows → `grade_parlay_legs()`.
- `grade_parlay_legs()` logic: `"L" in results → "L"`, `"P" in results → "P"`, else `"W"` — correct parlay grading (one loss = loss, no graded leg = None/skip).
- NBA data fetched for `daily_lay`, `longshot`, `sgp` sport lookups.
- `COUNTED_RUN_TYPES = {"primary","bonus","manual","daily_lay","longshot","sgp","gameline","",None}` — all present?
- `MODEL_RUN_TYPES = {"primary","bonus","daily_lay","longshot","sgp"}` — gameline/manual correctly excluded?
- `build_recap_embed()` — has separate sections/headers for longshot and SGP picks?
- Does the grader skip `legs=""` rows for non-parlay picks without erroring?
- Monthly summary — includes sgp/longshot in P&L totals?

### 66. `secrets_config.py` — new webhook vars

Two new webhook env vars added:
- `DISCORD_LONGSHOT_WEBHOOK`
- `DISCORD_SGP_WEBHOOK`

**Verify:**
- Both exported from `engine/secrets_config.py`.
- Root `secrets_config.py` synced (this caused an ImportError on first real run after adding — verify fix is in place).
- `.env.example` has both documented with placeholder values.
- Both used with `or DISCORD_BONUS_WEBHOOK` fallback in their respective post functions.
- Neither leaked to logs or Discord embeds.

### 67. KILLSHOT v2 rule changes (Apr 21 2026)

KILLSHOT gate was updated. Verify code matches exactly:
- `tier == "T1"` strict (not T1B, T2, etc.)
- `pick_score >= 90`
- `win_prob >= 0.65`
- `odds in [-200, +110]` (inclusive)
- `stat in {"PTS", "REB", "AST", "SOG", "3PM"}`
- Sizing: 3u default, 4u iff `win_prob >= 0.70 AND edge >= 0.06` (no 5u — v1 allowed 5u, v2 removed it)
- Weekly cap: **2** (was 3 in v1 — verify cap in code matches 2)
- Manual override `--killshot NAME` bypasses gate, requires `score >= 75`, still counts toward cap
- Posts to `#killshot` channel with `@everyone`

### 68. File sync audit — engine/ vs root

The following files must be identical between `engine/` and root:
- `run_picks.py` ↔ `engine/run_picks.py`
- `grade_picks.py` ↔ `engine/grade_picks.py`
- `sgp_builder.py` ↔ `engine/sgp_builder.py`
- `pick_log_schema.py` ↔ `engine/pick_log_schema.py`
- `secrets_config.py` ↔ `engine/secrets_config.py`
- `results_graphic.py` ↔ `engine/results_graphic.py`

Run `diff engine/X.py X.py` for each — any diff = bug (the session had multiple instances of root not being synced after edits).

### 69. pick_log data integrity — v3 post-migration

The logs were migrated from v2 (27 cols) to v3 (28 cols) mid-session. Verify:
- All rows in `pick_log.csv` have exactly 28 fields.
- All rows in `pick_log_manual.csv` have exactly 28 fields.
- Migrated rows have `legs=""` (blank, not "legs", not missing).
- No row has `legs` containing malformed JSON (for sgp/longshot rows added after migration).
- Sidecar files (`pick_log.csv.schema`, `pick_log_manual.csv.schema`) reflect `SCHEMA_VERSION=3`.

---

## Final instruction: leave no stone unturned

If you find yourself skipping a file, function, or branch because it "looks fine" — read it character-by-character instead. This is a line-by-line audit, not a spot-check.

For files over 1000 lines, consider delegating to a subagent with a targeted prompt so they can focus. You (the main agent) must still synthesize their findings into the final report.

If you're unsure whether something is a bug or intended behavior, **flag it as an OPEN QUESTION** rather than silently approving it.

**The goal:** after this audit, Jono should be able to read the report and know exactly what needs to change, in priority order, with enough detail to act on it.

---

## Start here

1. Read `CLAUDE.md` in full — it's the north star.
2. Run `wc -l engine/*.py` to size up the surface area.
3. Start with `run_picks.py` since it's the largest and highest-blast-radius.
4. Then `grade_picks.py`.
5. Then `capture_clv.py`.
6. Then `engine/sgp_builder.py` (new this session — high priority).
7. Then `engine/pick_log_schema.py`.
8. Then `engine/secrets_config.py`.
9. Then the support scripts.
10. Run all file-sync diffs (section 68).
11. Run all pick_log integrity checks (sections 5, 62, 69).
12. Finish with a top-level "cross-file issues" section.

Use parallel subagents where it helps — Explore / general-purpose agents can each take one file and report back. But YOU should synthesize the final report.

Ship the audit report as a markdown file at `/sessions/<session>/mnt/JonnyParlay/AUDIT_REPORT.md`.

---

*Updated Apr 24 2026 — added sections 61–69 covering SGP builder, longshot parlay, gameline run_type, pick_log v3 schema migration, KILLSHOT v2 rules, new webhook secrets, and file sync audit. Original audit closed Apr 21 2026 with 78/78 items resolved.*
