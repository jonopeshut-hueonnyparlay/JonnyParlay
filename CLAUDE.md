# Memory

## Me
Jono (jonopeshut@gmail.com). Sports bettor, DFS player, Discord community operator. Runs picks as a trading business — analytical, sharp, luxury brand.

## Brand
**picksbyjonny** · Tagline: *edge > everything* · Aesthetic: luxury · sharp · analytical  
Discord bot display name: **PicksByJonny**

## Projects

| Name | What |
|------|------|
| **JonnyParlay** | Python betting engine — run_picks.py + grade_picks.py. Runs on Windows at `C:\Users\jono4\Documents\JonnyParlay\` |
| **Discord Overhaul** | Full server rebuild. Phase 1 = design (locked). Phase 2 = manual Discord build (in progress). |
| **KILLSHOT** | New premium tier scaffold. Trigger criteria + sizing math deferred — revisit next pass. |
| **KairosEdge** | Halftime trade system — buying trailing team YES in full-game winner market. Tracked separately from props. |

## Key Files

| File | Purpose |
|------|---------|
| `engine/run_picks.py` | Main betting engine (~4650 lines). Source of truth — always sync to root after edits. |
| `engine/grade_picks.py` | Auto-grades pick_log.csv results, posts Discord recap + results graphic. |
| `engine/capture_clv.py` | CLV daemon — polls every 2 min, captures closing odds at T-5 min per game. Writes `closing_odds` + `clv` to pick_log. Scheduled via Windows Task Scheduler at 10am daily. |
| `engine/clv_report.py` | CLI report: `python clv_report.py [--days N] [--sport X] [--tier Y] [--shadow]` |
| `engine/results_graphic.py` | Generates PNG results card posted to Discord after recap. |
| `engine/analyze_picks.py` | Backtest analysis dashboard — ROI, win rate, calibration by tier/stat/edge bucket. |
| `engine/weekly_recap.py` | Weekly P&L recap posted to #announcements every Sunday. |
| `engine/morning_preview.py` | Posts daily card teaser to #announcements after run_picks.py runs. |
| `data/pick_log.csv` | Master results ledger. Starts Apr 14 2026. 27-column header (auto-migrates on next run). |
| `test_context.py` | Manual test harness for context system — run on Windows to test `--context` flag behaviour. |
| `data/pick_log_mlb.csv` | Shadow log for MLB (still in SHADOW_SPORTS). Use `--shadow` flag in clv_report to include. |
| `start_clv_daemon.bat` | Launcher for CLV daemon — called by Task Scheduler. Sets UTF-8 encoding. |
| `discord-overhaul-master-plan.md` | Full design spec. All decisions locked. |
| `discord-build-reference.md` | Step-by-step manual build checklist (Phase 2). |

## Discord Structure (Target)
```
WELCOME: #welcome, #start-here, #announcements
PICKS: #premium-portfolio, #bonus-drops, #daily-lay, #killshot 🔒
RESULTS: #daily-recap, #monthly-tracker, #winning-slips
COMMUNITY: #general, #questions, #community-picks, #testimonials, 🔊gaming
RESOURCES: #glossary, #sports-news, #affiliates
MODS: (hidden)
ARCHIVE: (collapsed)
```

## Terms

| Term | Meaning |
|------|---------|
| VAKE | Bankroll sizing system (proprietary) |
| Pick Score | Model ranking score for each pick |
| POTD | Pick of the Day — standalone embed, posted after premium card |
| KILLSHOT | Highest-conviction tier. Scaffold live, criteria TBD. @everyone ping. |
| Premium | Top 5 picks from the model each day |
| Bonus Drop | Single highest-scoring NEW pick per run (max 5/day) |
| Daily Lay | Alt spread parlay — 3-leg, model-identified mispriced lines |
| CLV | Closing Line Value — primary edge indicator |
| CO-legal books | 18 CO-approved books. API key "espnbet" = display "theScore Bet" |

## Books / APIs
- **Odds API key:** `adb07e9742307895c8d7f14264f52aee`
- `espnbet` in Odds API → display as **theScore Bet** everywhere
- CO_LEGAL_BOOKS: 18 books defined in run_picks.py

## pick_log.csv Schema (current)
`date, run_time, run_type, sport, player, team, stat, line, direction, proj, win_prob, edge, odds, book, tier, pick_score, size, game, mode, result, closing_odds, clv, card_slot, is_home, context_verdict, context_reason, context_score`

- `run_type`: primary | bonus | manual | daily_lay
- `tier`: T1 | T1B | T2 | T3 | KILLSHOT | DAILY_LAY
- `stat`: SOG | PTS | REB | AST | 3PM | SPREAD | ML_FAV | ML_DOG | TOTAL | TEAM_TOTAL | F5_ML | F5_SPREAD | F5_TOTAL | PARLAY
- `is_home`: True/False for SPREAD/ML/F5 picks (BUG G1/G2/G3 fix); blank for props
- `clv`: closing_implied_prob − your_implied_prob (positive = beat the close); filled by capture_clv.py
- `context_verdict`: supports | neutral | conflicts | skipped — blank on normal runs (context disabled by default)
- `context_reason`: short explanation when context is enabled
- `context_score`: 0-3 (unused while context disabled)

## Context Sanity System (Session 3 — Apr 17 2026)

**Status: DISABLED by default.** All the code is in place but skipped on normal runs. Enable with `--context` flag.

### Why disabled
SaberSim projections (the engine's input) already incorporate injury adjustments and confirmed starters. The LLM context check was redundant for most signals and unreliable for others (inconsistent JSON, web search returning thin results). Decision: pure math run is cleaner. Context layer stays in code for future use.

### To enable
```
python run_picks.py nba.csv --context
```
Requires `anthropic` package + `ANTHROPIC_API_KEY` env var on Windows.

### How it works (when enabled)
1. **`run_pregame_scan(sports, today_str)`** — one Haiku + web_search call per sport, concurrent. Returns injury/lineup bulletin per sport.
2. **`run_context_check(pick, today_str, pregame_notes="")`** — one call per pick (up to 8 concurrent), no web search. Checks for obvious red flags (player OUT/scratched) using pregame bulletin. Returns `(verdict, reason, score)` 3-tuple.
3. **`apply_context_sanity(...)`** — orchestrates both. `conflicts` cuts the pick; `supports` and `neutral` pass.

### Verdicts
- `conflicts` → pick cut (player OUT/DOUBTFUL/scratched)
- `supports` → pass + `↳ ✅ reason` shown on Discord card under the pick
- `neutral` → pass, no annotation

### Settings
```
CONTEXT_API_MODEL    = "claude-haiku-4-5-20251001"
CONTEXT_MAX_WORKERS  = 8
```

## Bugs Fixed

### Session 1
- **BUG G1/G2/G3**: SPREAD/ML/F5 away-team picks grading as home. Fixed via `is_home` field logged at pick time, `_resolve_pick_is_home()` used at grade time.
- **Recap book display**: Props now show book in recap embed. TEAM_TOTAL display fixed in both embed (`grade_picks.py`) and graphic (`results_graphic.py`) — uses team abbrev instead of full player field + stat.
- **Recap odds format**: Positive odds now show `+` sign.
- **Recap weekly/monthly totals**: All run_types counted (bonus, manual, daily_lay, primary).
- **Recap week cap**: `get_week_picks` capped at `ref_date_str` to avoid including future dates when reposting.

### Session 2 (full audit — Apr 16 2026)
- **`--log-manual` CSV corruption** (`run_picks.py`): Header/data row was 22 columns, missing `clv` and `is_home`. Now 24 columns matching HEADER.
- **PICK_LOG_PATH wrong path** (`results_graphic.py`): Was `~/Documents/JonnyParlay/pick_log.csv` — missing `data/` subdir. Standalone graphic silently read nothing. Fixed.
- **Python 3.9 crash** (`capture_clv.py`): `int | float` union syntax requires 3.10+. Added `from __future__ import annotations` — now works on 3.9+.
- **TEAM_TOTAL always graded home score** (`grade_picks.py`): Substring match on `player` field filtered 3-char abbreviations (`len(w) > 3`), so `is_away` was always False. Replaced with `_resolve_pick_is_home()` which reads the `is_home` field correctly.
- **`_card_already_posted_today` false positive** (`run_picks.py`): `r.get("run_type", "")` defaulted to `""` which matched the allow-list, blocking card posting for rows with blank run_type. Fixed to `r.get("run_type") in ("primary", None)`.
- **R9 swap stale counters** (`run_picks.py`): Directional balance swap didn't roll back `old_pick`'s contributions to `game_count`, `stat_dir_count`, `pitcher_game_dir_count`, or `used` before evaluating `can_add()` on the replacement. Rewrote to: remove old_pick's counters → find best_over → commit or restore.
- **`_BOOK_DISPLAY` missing 8 CO_LEGAL_BOOKS keys** (`grade_picks.py`): Added `bet365`, `fanatics`, `betparx`, `pointsbetus`, `twinspires`, `circasports`, `tipico`, `wynnbet`. Fixed `pointsbet_us` → `pointsbetus` key mismatch.
- **Recap footer wrong timezone** (`grade_picks.py`): `datetime.now()` used local (MT) time but labelled "ET". Fixed to `datetime.now(ZoneInfo("America/New_York"))`.

### Session 3 (context system build — Apr 17 2026)
- **`_CONTEXT_PROMPTS` generic prompts replaced**: now `_build_context_prompt()` with stat-specific logic per NBA/NHL/MLB stat type.
- **`run_context_check` returned 2-tuple**: updated to 3-tuple `(verdict, reason, score)`. All callers updated.
- **`pick_log.csv` missing context columns**: added `context_verdict`, `context_reason`, `context_score` to HEADER + all write sites (primary, bonus, manual). Header auto-migration on next run.
- **`test_context.py` unpacking crash**: was `verdict, reason = run_context_check(...)` — fixed to unpack 3-tuple, show pregame scan output + score stars.
- **F5_SPREAD/F5_ML grading on full-game scores** (`grade_picks.py`): removed from SPREAD/ML branches so they fall through to F5 branch correctly.

### Session 4 (system audit + CLV setup — Apr 17 2026)
- **`grade_picks.py` display_book regional suffix bug**: `hardrockbet_fl` displayed as "Hardrockbet_Fl" in recaps. Fixed: strip suffix before dict lookup.
- **Book key stored raw in pick_log** (`run_picks.py`): Added `_norm_book()` helper — strips region suffix at log time so pick_log always has clean base keys (e.g. `hardrockbet` not `hardrockbet_fl`).
- **Auto-R12 from pick_log** (`run_picks.py`): Added `auto_r12_from_log()` — reads last 5 days of primary/bonus losses and auto-builds cooldown list every run. No more manual `--cooldown` flag. Manual overrides still work. Console shows `R12 Cooldown: auto: Melton, Eichel` etc.
- **`analyze_picks.py` wrong path**: Was `~/Documents/JonnyParlay/pick_log.csv` — missing `data/` subdir. Fixed to `data/pick_log.csv`. Would have silently read nothing.
- **`weekly_recap.py` wrong path**: Same fix.
- **CLV daemon deployed**: Scheduled via Windows Task Scheduler — daily at 10am, runs `start_clv_daemon.bat`. Daemon waits if picks not logged yet (won't exit on empty). Self-terminates when all picks captured.
- **`capture_clv.py` premature exit**: Was exiting immediately if no picks found (even if picks not logged yet). Fixed: only exits if picks exist AND all have CLV. Otherwise keeps waiting.
- **`capture_clv.py` API quota waste**: `fetch_events()` was hitting `/sports/{sport}/odds` (expensive, full odds) every 2-min poll. Fixed to use cheap `/sports/{sport}/events` endpoint (metadata only). Full odds fetched once per game at capture time only.

### Session 5 (full audit + Discord guards — Apr 17 2026)
Audit covered 8 files (run_picks, grade_picks, capture_clv, clv_report, results_graphic, analyze_picks, weekly_recap, morning_preview). All fixes applied across 6 batches.

**Silent data loss (Batch 1):**
- **`morning_preview.py` wrong paths**: `PICK_LOG_PATH` and `DISCORD_GUARD_FILE` missing `/data/` subdir — fixed.
- **`weekly_recap.py` guard path**: Same missing `/data/` subdir — fixed.
- **`capture_clv.py` write race condition**: Daemon uses read-modify-rewrite on pick_log.csv while run_picks.py appends. Added optional `filelock` import + atomic `tmp + os.replace()` write. Graceful fallback with warning if filelock not installed (`pip install filelock --break-system-packages` recommended).
- **`capture_clv.py` premature `captured_games.add()`**: Fetch failures and partial captures were marking a game "done" after one attempt, losing retries. Added `capture_attempts` counter (max 3 retries) + stale-game check (>10 min past start). Partial captures remain open so next poll retries missing picks.

**Correctness / dedup (Batch 2):**
- **KILLSHOT manual promote broken**: `--killshot "Pastrnak,McDavid"` used exact full-name match so last-name tokens never matched "David Pastrnak". Now does case-insensitive token + substring match on player full name.
- **`_card_already_posted_today` blank run_type bypass** (`run_picks.py`): Filter was `in ("primary", None)` — blank-string rows bypassed the guard. Changed to `{"primary", "", None}` (treats blank as primary).
- **`post_daily_lay` / `post_card_announcement` no dedup** (`run_picks.py`): Re-running run_picks.py would fire these webhooks again. Added `DISCORD_GUARD_FILE` (shared with morning_preview/weekly_recap) + `_discord_already_posted/mark_posted` helpers. Guard keys: `daily_lay:{date}`, `card_announcement:{date}`.

**Consistency (Batch 3):**
- **`weekly_recap.py` `_BOOK_DISPLAY` missing 6 books**: Added bet365, betparx, twinspires, circasports, tipico, wynnbet to match grade_picks.py. Added regional-suffix strip in `display_book()`.
- **`weekly_recap.py` wrong timezone**: `datetime.now()` labelled "ET" but used local (MT) time. Fixed to `datetime.now(ZoneInfo("America/New_York"))`.
- **`weekly_recap.py` BRAND_LOGO placeholder URL**: `/1234567890/jpj_logo.png` was a sample. Replaced with the live logo URL used everywhere else.
- **`weekly_recap.py` filter missed bonus/manual/daily_lay**: `filter_week` and `month_picks` only counted primary — contradicted CLAUDE.md note. Added `COUNTED_RUN_TYPES = {"primary", "bonus", "manual", "daily_lay", "", None}` to match grade_picks.

**Filter cleanup (Batch 4):**
- **`morning_preview.py` `get_today_picks` blank bypass**: Same `("primary", None)` pattern as `_card_already_posted_today`. Changed to `{"primary", "", None}`.

**Medium priority (Batch 5):**
- **`results_graphic.py` no 5xx retry**: Post loop retried 429 only; any 5xx or transport exception was a hard fail. Now retries transient 5xx + `RequestException` with exponential backoff (max 3 attempts); 4xx still fails fast.
- **`analyze_picks.py` retired MBP header**: Report banner said "MBP v9.4 Pick Performance" — mbp/ folder is retired per CLAUDE.md. Changed to "Pick Log Performance Report".

**Low priority (Batch 6):**
- **`morning_preview.py` wrong timezone for default date**: `datetime.now()` used local (MT) time for the "today" default. Fixed to ET via `ZoneInfo("America/New_York")` — matches run_picks.py / grade_picks.py.

## MLB Status
MLB is still in **SHADOW_SPORTS** — picks go to `pick_log_mlb.csv`, not posted to Discord. Go-live = Jono's call.

## Running grade_picks.py in Cowork
grade_picks.py uses `~/Documents/JonnyParlay/` hardcoded. In Cowork, create symlink first:
```
mkdir -p ~/Documents/JonnyParlay
ln -sf /sessions/.../mnt/JonnyParlay/data ~/Documents/JonnyParlay/data
```
Then: `python engine/grade_picks.py --date YYYY-MM-DD [--repost] [--dry-run]`

## ⚠ Cowork Write Caution
If the engine runs on Windows and writes to pick_log.csv, do NOT use the Write tool to rewrite pick_log.csv — it will clobber engine-written rows. Use Edit/append only.

## Daily Routine
1. Download SaberSim CSV
2. `python run_picks.py nba.csv` (or nhl.csv etc) — posts card, logs picks
3. Done — CLV daemon captures automatically, grade_picks.py grades after games

## CLV Daemon
- Scheduled: Windows Task Scheduler, daily 10am, runs `start_clv_daemon.bat`
- Manual trigger: `schtasks /run /tn "JonnyParlay CLV Daemon"`
- Log: `data\clv_daemon.log`
- Behavior: waits for picks to be logged → polls every 2 min → captures at T-5 min per game → exits when all done
- API usage: cheap `/events` endpoint for polling, one real odds call per game at capture time

## Preferences
- Responses: terse, direct. No unnecessary summaries.
- Code: edit `engine/run_picks.py` (source of truth). Always sync to root after edits (`cp engine/run_picks.py run_picks.py`). Same for grade_picks.py, results_graphic.py. Cowork mount = `/sessions/.../mnt/JonnyParlay/`. Windows path = `C:\Users\jono4\Documents\JonnyParlay\`. mbp/ folder is RETIRED.
- Premium tier stays at 5 picks — do not change.
