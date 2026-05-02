# Memory

## Audit 2026-05-01 — Status
Full audit doc: `docs/audits/AUDIT_2026-05-01.md`. **0 CRIT / 2 HIGH / 4 MED / 9 LOW / 54 CLEAN.**

**Closed May 1 2026:** H1, H2, M1, M2, M3, M4, L1–L9. P9 Platt constants fitted (PLATT_A=1.4988, PLATT_B=-0.8102, 76 props, 6% Brier). 832 tests pass. **Audit fully closed.**

## Audit 2026-04-28 — Status
Full audit doc: `docs/audits/AUDIT_2026-04-28.md`. **52 findings: 3 CRIT / 11 HIGH / 14 MED / 20 LOW / 4 CLEAN.**

**All CRIT + HIGH items closed (Apr 28–29 2026).** Branch: `audit-2026-04-28-fixes` merged to main.

**MED — all closed:** M1 (mlb schema), M2 (csv_writer TZ), M3 (KILLSHOT substring), M5 (push-leg drop), M6 (empty CSV abort), M8 (run lock), M9 (paths.py sweep), M12 (stdout utf-8).

**LOW — all closed Apr 30 2026:** L1 (tests/ dir), L2 (docs/audits/), L3 (marketing/ untracked), L5 (fuse artifacts — auto-clear), L6 (backtest logs — never tracked), L7 (pre-commit hook — `.git/hooks/pre-commit` guards shims), L9 (REB dropped from KILLSHOT_STAT_ALLOW), L10 (is_decimal_leak — already invoked), L11 (SIGMA fallthrough warning), L12 (unit cap docs), L13 ($PSScriptRoot in setup_clv_task.ps1), L14 (legs column docs), L15 (MBP terminology note), L16 (root shims — eliminate copy-sync drift), L17 (NHL sizing docs), L18 (conftest.py), L19 (streak docs), L20 (discord corruption test). **Audit fully closed.**

## Me
Jono (jonopeshut@gmail.com). Sports bettor, DFS player, Discord community operator. Runs picks as a trading business — analytical, sharp, luxury brand.

## Brand
**picksbyjonny** · Tagline: *edge > everything* · Aesthetic: luxury · sharp · analytical  
Discord bot display name: **PicksByJonny**

## Projects

| Name | What |
|------|------|
| **JonnyParlay** | Python betting engine — run_picks.py + grade_picks.py. Runs on Windows at `C:\Users\jono4\Documents\JonnyParlay\` |
| **Discord Overhaul** | Full server rebuild — **done**. Phase 1 design + Phase 2 manual build both shipped. |
| **KILLSHOT** | Premium tier (v2, Apr 21 2026). Auto-qualifies only when ALL pass: `tier=T1` strict, `pick_score≥90`, `win_prob≥0.65`, `odds ∈ [-200, +110]`, `stat ∈ {PTS,AST,SOG,3PM}`. Sizing: 3u default, 4u iff `win_prob≥0.70 AND edge≥0.06` (no 5u). Weekly cap: **2**. Manual override (`--killshot NAME`) bypasses gate but still counts toward cap + requires `score≥75`. Posts to #killshot with @everyone. |
| **KairosEdge** | Halftime trade system — buying trailing team YES in full-game winner market. Tracked separately from props. |
| **Custom Projection Engine** | In-flight replacement for SaberSim as the CSV input to `run_picks.py`. **Code lives in this repo** (engine/nba_projector.py + projections_db.py + injury_parser.py + csv_writer.py + backtest_*.py = ~159 KB; data/projections.db = 14.8 MB SQLite). Committed to git (C1 closed Apr 28). Zero production-path imports — verified isolated. Output CSV must match SaberSim schema exactly. SaberSim stays live until custom CLV ≥ SaberSim CLV over 100+ picks (no comparison harness wired yet). Full spec: `memory/projects/custom-projection-engine.md`. |

## Key Files

| File | Purpose |
|------|---------|
| `engine/run_picks.py` | Main betting engine (large — ~5k+ lines and growing). **Source of truth — edit engine/ only. Root entry points are shims (L16, Apr 30 2026) — no sync step needed.** |
| `engine/grade_picks.py` | Auto-grades pick_log.csv results, posts Discord recap + results graphic. Monthly summary auto-fires on 1st of month. |
| `engine/capture_clv.py` | CLV daemon — polls every 2 min, captures closing odds in T-30 to T+3 window per game. Writes `closing_odds` + `clv` to pick_log. Scheduled via Windows Task Scheduler at 10am daily. Single-instance guard via filelock. Ghost-game checkpoint integrity check on startup. |
| `engine/clv_report.py` | CLI report: `python clv_report.py [--days N] [--sport X] [--tier Y] [--shadow]` |
| `engine/results_graphic.py` | Generates PNG results card posted to Discord after recap. |
| `engine/analyze_picks.py` | Backtest analysis dashboard. Usage: `python analyze_picks.py [--sport X] [--since YYYY-MM-DD] [--stat X] [--shadow] [--export]` |
| `engine/weekly_recap.py` | Weekly P&L recap posted to #announcements every Sunday. |
| `engine/morning_preview.py` | Posts daily card teaser to #announcements after run_picks.py runs. |
| `data/pick_log.csv` | Model-generated ledger (primary / bonus / daily_lay / sgp / longshot). Starts Apr 14 2026. **28-column** header (schema_version=3, last col is `legs` JSON for parlays). |
| `data/pick_log_manual.csv` | Manual picks only (--log-manual). Same 28-column schema. Graded alongside main log but never posted to Discord recap. Excluded from CLV daemon. |
| `data/pick_log_mlb.csv` | Shadow log for MLB (still in SHADOW_SPORTS). Include in analyze with --shadow flag. |
| `sgp_builder.py` | Root shim → `engine/sgp_builder.py`. Same-Game Parlay builder. Runs after every pick run. Allowed books: FanDuel, BetMGM, DraftKings, theScore (espnbet), Caesars (williamhill_us), Fanatics, Hard Rock (hardrockbet). Logs as `run_type=sgp`. |
| `start_clv_daemon.bat` | Launcher for CLV daemon — called by Task Scheduler. Requires `PYTHONUNBUFFERED=1` + `python -u` (S4U logon). **Must contain ASCII only** — non-ASCII chars (em-dash, box-drawing, ×) cause cmd.exe to crash with exit code 255. |
| `setup_clv_task.ps1` | One-shot PowerShell script that registers the CLV daemon scheduled task. S4U logon + WakeToRun. Re-run as admin to reset. |
| `post_nrfi_bonus.py` | One-shot webhook poster for manual bonus drops. Uses Mozilla UA to bypass Cloudflare 1010. Template for future manual webhooks. |
| `tests/test_context.py` | Manual test harness for context system — run on Windows to test `--context` flag behaviour. |

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
| KILLSHOT | Highest-conviction tier. v2 gate (Apr 21 2026): tier=T1 strict, score≥90, win_prob≥0.65, odds ∈ [-200,+110], stat ∈ {PTS,AST,SOG,3PM} (REB dropped L9). Sizing: 3u default, 4u iff wp≥0.70 AND edge≥0.06. Weekly cap: 2. @everyone ping. |
| Premium | Top 5 picks from the model each day |
| Bonus Drop | Single highest-scoring NEW pick per run (max 5/day) |
| Daily Lay | Alt spread parlay — 3-leg (min 2), model-identified mispriced lines. **Max combined odds: +100**. Per-leg gates: `edge≥0.025`, `cover_prob≥0.58`. `MIN_DAILY_LAY_PROB=0.47`. Kelly-derived sizing: 0.25–0.75u via `size_daily_lay()`. Redesigned Apr 28 2026. |
| SGP | Same-Game Parlay — **3-4 leg** (redesigned Apr 28 2026), NBA only, **+200–450 range**. Composite pool_score sort, Gaussian odds scoring, BetMGM first. Dynamic sizing: 0.25u default / 0.50u premium (avg_wp≥0.70 AND cohesion≥0.55 AND avg_edge≥0.035). Allowed books only (see sgp_builder.py). `--sgp-only` flag forces SGP post only. |
| Longshot | 6-leg parlay of safest picks. Logged as `run_type=longshot`. Per-game cap: max 2 legs per game (`LONGSHOT_MAX_PER_GAME=2`). Added Apr 28 2026. |
| CLV | Closing Line Value — primary edge indicator. Positive = beat the close. |
| CO-legal books | 18 CO-approved books. API key "espnbet" = display "theScore Bet" |

## Books / APIs
- **Odds API key + Discord webhooks:** loaded from `.env` via `engine/secrets_config.py`
  - Windows path: `C:\Users\jono4\Documents\JonnyParlay\.env` (also searches project root + `engine/.env`)
  - Template: `.env.example` (committed). Real `.env` is gitignored.
  - Debug inventory: `python engine/secrets_config.py` prints a redacted summary.
- `espnbet` in Odds API → display as **theScore Bet** everywhere
- CO_LEGAL_BOOKS: 18 books defined in run_picks.py

## Python Dependencies
- Install: `pip install -r requirements.txt --break-system-packages`
- **Hard deps (required to import):** `filelock` (cross-process locks), `requests`
- **Soft deps (feature-gated):** `openpyxl` (xlsx recap), `Pillow` (results_graphic PNG), `anthropic` (--context mode)
- Audit C-1 closed Apr 19 2026 — `filelock` is hard-required everywhere. If it's missing, the engine fails fast at import with a clear install hint.

## Audit Status
- **Closed Apr 21 2026 — 78/78 items declared resolved.** Section 40 (schema-version fail-fast via sidecar) + Section 41 (print → logging via `engine/engine_logger.py`) were the final two items. Regression suite: 756 passed, 2 skipped.
- **Apr 28 2026 — Parlay sharpness overhaul:** SGP redesigned 6→3-4 legs (+200–450), daily lay per-leg gates + Kelly sizing, longshot per-game cap of 2. All committed. engine/sgp_builder.py synced (H1 closed).
- **Audit 2026-04-28 — 52 findings, ALL items closed Apr 28–30 2026.** CRIT+HIGH closed Apr 28–29; all MED + all LOW closed Apr 29–30. See `docs/audits/AUDIT_2026-04-28.md`.

## pick_log.csv Schema (current — schema_version 3, 28 columns)
`date, run_time, run_type, sport, player, team, stat, line, direction, proj, win_prob, edge, odds, book, tier, pick_score, size, game, mode, result, closing_odds, clv, card_slot, is_home, context_verdict, context_reason, context_score, legs`

- `run_type`: primary | bonus | manual | daily_lay | sgp | longshot
- `tier`: T1 | T1B | T2 | T3 | KILLSHOT | DAILY_LAY | SGP | LONGSHOT | MANUAL
- `stat`: SOG | PTS | REB | AST | 3PM | SPREAD | ML_FAV | ML_DOG | TOTAL | TEAM_TOTAL | F5_ML | F5_SPREAD | F5_TOTAL | PARLAY
- `is_home`: True/False for SPREAD/ML/F5/TEAM_TOTAL picks; blank for props (canonical: `normalize_is_home`)
- `clv`: closing_implied_prob − your_implied_prob (positive = beat the close); filled by capture_clv.py
- `context_verdict`: supports | neutral | conflicts | skipped | disabled — blank on normal runs (context disabled by default)
- `legs`: JSON array for parlay rows. **SGP populates ✓** | longshot populates ✓ | **daily_lay populates ✓** (H9 closed Apr 28 — `_daily_lay_legs_json()` added; grader reads JSON-first with game-string fallback for 9 legacy rows). primary/bonus/manual leave it blank. pick_log_mlb.csv 282 short rows normalized to 28 cols (M1 closed Apr 29).

## Sizing Caps (L12/L17)
- **Daily total cap: 12u** (`G12` check in run_picks.py) — hard ceiling across all run_types per session.
- **Sport unit caps:** NBA = 8.0u max per pick | NHL = 5.0u max per pick (`SPORT_UNIT_CAP` dict).
- **NHL SOG stat cap:** max 6 picks per run (`STAT_CAP = {"SOG": 6, ...}`; default cap = 2 for other stats).

## Context Sanity System

**Status: DISABLED by default.** Enable with `--context` flag.

SaberSim projections already incorporate injury adjustments. Context layer stays in code for future use.

```
python run_picks.py nba.csv --context
```
Requires `anthropic` package + `ANTHROPIC_API_KEY` env var on Windows.

- `run_pregame_scan()` — one Haiku + web_search call per sport (concurrent)
- `run_context_check()` — one call per pick (up to 8 concurrent), checks for OUT/scratched flags
- `conflicts` → pick cut | `supports` → pass + annotation | `neutral` → pass

## MLB Status
Still in **SHADOW_SPORTS** — picks go to `pick_log_mlb.csv`, not posted to Discord. Sizing bug fixed (Apr 19 2026) — shadow picks now get VAKE base sizing. Go-live = Jono's call.

## Running grade_picks.py in Cowork
M9 closed Apr 29 2026 — all engine modules now use `paths.py`. Set `JONNYPARLAY_ROOT` to the repo root and every module resolves paths correctly:
```
export JONNYPARLAY_ROOT=/sessions/.../mnt/JonnyParlay
python engine/grade_picks.py --date YYYY-MM-DD [--repost] [--dry-run]
```
Windows deployments leave the env var unset — `paths.py` falls back to `~/Documents/JonnyParlay` so existing behavior is unchanged.

Migrated: `clv_report`, `csv_writer`, `grade_picks`, `projections_db`, `discord_guard`, `morning_preview`, `weekly_recap`, `analyze_picks`, `results_graphic`, `run_picks`. Remaining hardcoders: `capture_clv` (CLV daemon — low priority, runs on Windows only).

## ⚠ Cowork Write Caution
If the engine runs on Windows and writes to pick_log.csv, do NOT use the Write tool to rewrite pick_log.csv — it will clobber engine-written rows. Use Edit/append only.

## Daily Routine
1. Download SaberSim CSV
2. `python run_picks.py nba.csv` (or nhl.csv etc) — posts card, logs picks
3. Done — CLV daemon captures automatically, grade_picks.py grades after games

## CLV Daemon
- Scheduled: Windows Task Scheduler, daily 10am, runs `start_clv_daemon.bat`
- Logon: **S4U** (fires without active desktop session). WakeToRun enabled.
- Manual trigger: `schtasks /run /tn "JonnyParlay CLV Daemon"` or foreground `python -u engine\capture_clv.py`
- Log: `data\clv_daemon.log`
- Capture window: **T-30 to T+3** min per game
- Shadow logs: skipped by default (`ENABLE_SHADOW_CLV = False`). Flip to `True` when MLB goes live.
- Single-instance guard: filelock at `data/clv_daemon.lock` (override via `JONNYPARLAY_DAEMON_LOCK` env var for tests). Ghost-game checkpoint eviction on startup.
- Graceful shutdown (audit H-10, closed Apr 20 2026): SIGTERM / SIGINT / SIGBREAK all trigger a clean exit at the next poll boundary — final checkpoint saved, daemon lock released. Second signal hard-exits.
- `start_clv_daemon.bat` must keep `PYTHONUNBUFFERED=1` + `python -u` — required for S4U logon.
- `start_clv_daemon.bat` must be ASCII-only — fixed Apr 28 2026 (non-ASCII chars were causing exit code 255 crash before Python started).
- `data/discord_posted.json` can get truncated/corrupted on Windows mount. **C2 FIXED Apr 28:** `_load_unlocked` in `engine/discord_guard.py` now attempts regex rebuild from raw bytes on `JSONDecodeError` before falling back to `{}`. Partial corruption is recovered automatically; total corruption (no extractable keys) logs a warning and resets safely.

## Preferences
- Responses: terse, direct. No unnecessary summaries.
- Code: edit `engine/run_picks.py` (source of truth). **No sync step needed** — root entry points are 5-line shims (L16, Apr 30 2026) that delegate to engine/ via `runpy.run_module`. Cowork mount = `/sessions/.../mnt/JonnyParlay/`. Windows path = `C:\Users\jono4\Documents\JonnyParlay\`. **Cowork bash sync is unreliable** — use `git push` for all changes; bash `cp` can truncate files if the stream closes mid-write. "MBP" terminology (Master Betting Prompt) lives in run_picks.py header/docstrings + `Master_Betting_Prompt_v9_4.md`; mbp/ folder is RETIRED but the term is preserved in code.
- Manual picks are excluded from pick streaks. `compute_pick_streak()` uses `MODEL_RUN_TYPES = {"primary","bonus","daily_lay","longshot","sgp"}` — manual picks never count toward streak.
- Premium tier stays at 5 picks — do not change.
- Discord recap shows model picks only. Manual picks never appear in Discord. Shadow sports (MLB) excluded from all Discord output.
- **Tracking: props only (Apr 30 2026).** `COUNTED_RUN_TYPES = {"primary","bonus"}` in both grade_picks.py and weekly_recap.py. Parlays still post to Discord for entertainment but results are never tracked. Manual log (`pick_log_manual.csv`) no longer loaded by grader or weekly recap.
- Recap embed W-L structure (Apr 30 2026): bare record + win% at top (e.g. `2-4 (33%)`), pick list split **Premium** / **Bonus** / **⚡ KILLSHOT** sections. Footer: `⚡ KILLSHOT W-L` tracked separately. No tier breakdown in public embeds (internal diagnostic → analyze_picks.py). Constants: `PROP_RUN_TYPES = {"primary","bonus"}`, `PARLAY_RUN_TYPES = {"daily_lay","sgp","longshot"}` (kept for grading only).
