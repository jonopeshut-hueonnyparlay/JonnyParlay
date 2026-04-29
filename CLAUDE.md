# Memory

## ⚠ Audit 2026-04-28 — Outstanding Issues
Full audit doc: `AUDIT_2026-04-28.md` at repo root. **52 findings: 3 CRIT / 11 HIGH / 14 MED / 20 LOW / 4 CLEAN.**

**CRIT (must fix this week):**
- **C1** ~159 KB of CPE code (nba_projector, projections_db, injury_parser, backtest_*, csv_writer) + Apr 28 parlay overhaul + this CLAUDE.md draft are **uncommitted to git**. Single SSD failure = total work loss. Verify `git remote -v` exists, then commit + push.
- **C2** `engine/discord_guard.py:_load_unlocked` returns `{}` on `JSONDecodeError` — every guard key resets, full daily run reposts to Discord with @everyone. The "regex rebuild from raw bytes" fix this CLAUDE.md claims (line 143) **does not exist in the codebase**.
- **C3** TOCTOU race — `run_picks.py` + `grade_picks.py` + `weekly_recap.py` use `_discord_already_posted()` then `_discord_mark_posted()` (two separate lock acquisitions). The atomic `claim_post()` primitive exists in `discord_guard.py` and is used correctly in `morning_preview.py` — just not propagated.

**HIGH highlights:**
- **H1** `engine/sgp_builder.py` has the OLD 6-leg design; root has the Apr 28 redesign. Production loads root so it works, but engine→root sync rule is violated. Run `cp sgp_builder.py engine/sgp_builder.py`.
- **H2** Root `secrets_config.py` is **truncated** mid-function (ends with `    f`). Run `cp engine/secrets_config.py secrets_config.py`.
- **H3** Discord guards never marked when `suppress_ping=True` — empirically confirmed: 9 daily_lay rows in pick_log, 0 daily_lay keys in `discord_posted.json`. Re-runs would double-post.
- **H4** `_killshots_this_week` swallows all exceptions and returns 0 — corrupt pick_log → engine posts full weekly cap on top of existing KILLSHOTs.
- **H5/H6** `webhook_fallback.notify_fallback` has zero call sites (audit H-7 close was fictitious) AND `DISCORD_FALLBACK_WEBHOOK` is missing from `.env`. Failed Discord posts are silent in production.
- **H7** S-41 print→logging migration is **partial** (132 print() in run_picks.py, ~10 are warning/error paths that should be logger).
- **H8** `compute_pl` includes VOIDed picks in ROI risked denominator — math drift over time.
- **H9** `grade_daily_lay` parses `game` field as legs string (fragile) because `_log_daily_lay` doesn't populate the canonical `legs` JSON column like SGP/longshot do.
- **H11** Apr 28 SGP/Daily Lay/Longshot redesigns have **zero test coverage** (KILLSHOT v2 has tests; this work doesn't).

**Recommended order of operations:**
1. Day 1 (~60 min): C1 (commit + push) → H2 (fix root secrets_config) → H1 (sync sgp_builder)
2. Day 2 (3-4 hr): C2 (regex rebuild) + C3 (claim_post sweep) + tests
3. Day 3-4: H3-H11 + CLAUDE.md refresh (ironic — but several inline statements below are inaccurate; see audit doc)
4. Sprint backlog: M1-M14 + L items

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
| **KILLSHOT** | Premium tier (v2, Apr 21 2026). Auto-qualifies only when ALL pass: `tier=T1` strict, `pick_score≥90`, `win_prob≥0.65`, `odds ∈ [-200, +110]`, `stat ∈ {PTS,REB,AST,SOG,3PM}`. Sizing: 3u default, 4u iff `win_prob≥0.70 AND edge≥0.06` (no 5u). Weekly cap: **2**. Manual override (`--killshot NAME`) bypasses gate but still counts toward cap + requires `score≥75`. Posts to #killshot with @everyone. |
| **KairosEdge** | Halftime trade system — buying trailing team YES in full-game winner market. Tracked separately from props. |
| **Custom Projection Engine** | In-flight replacement for SaberSim as the CSV input to `run_picks.py`. **Code lives in this repo** (engine/nba_projector.py + projections_db.py + injury_parser.py + csv_writer.py + backtest_*.py = ~159 KB; data/projections.db = 14.8 MB SQLite). All currently uncommitted to git (audit C1). Zero production-path imports — verified isolated. Output CSV must match SaberSim schema exactly. SaberSim stays live until custom CLV ≥ SaberSim CLV over 100+ picks (no comparison harness wired yet — audit F9.5). Full spec: `memory/projects/custom-projection-engine.md`. |

## Key Files

| File | Purpose |
|------|---------|
| `engine/run_picks.py` | Main betting engine (large — ~5k+ lines and growing). Source of truth — always sync to root after edits. |
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
| `sgp_builder.py` | Same-Game Parlay builder. Runs after every pick run. Allowed books: FanDuel, BetMGM, DraftKings, theScore (espnbet), Caesars (williamhill_us), Fanatics, Hard Rock (hardrockbet). Logs as `run_type=sgp`. |
| `start_clv_daemon.bat` | Launcher for CLV daemon — called by Task Scheduler. Requires `PYTHONUNBUFFERED=1` + `python -u` (S4U logon). **Must contain ASCII only** — non-ASCII chars (em-dash, box-drawing, ×) cause cmd.exe to crash with exit code 255. |
| `setup_clv_task.ps1` | One-shot PowerShell script that registers the CLV daemon scheduled task. S4U logon + WakeToRun. Re-run as admin to reset. |
| `post_nrfi_bonus.py` | One-shot webhook poster for manual bonus drops. Uses Mozilla UA to bypass Cloudflare 1010. Template for future manual webhooks. |
| `test_context.py` | Manual test harness for context system — run on Windows to test `--context` flag behaviour. |

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
| KILLSHOT | Highest-conviction tier. v2 gate (Apr 21 2026): tier=T1 strict, score≥90, win_prob≥0.65, odds ∈ [-200,+110], stat ∈ {PTS,REB,AST,SOG,3PM}. Sizing: 3u default, 4u iff wp≥0.70 AND edge≥0.06. Weekly cap: 2. @everyone ping. |
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
- **Closed Apr 21 2026 — 78/78 items declared resolved.** Section 40 (schema-version fail-fast via sidecar) + Section 41 (print → logging via `engine/engine_logger.py`) were the final two items. Regression suite: 756 passed, 2 skipped (count not re-verified in Apr 28 audit).
- **Apr 28 2026 — Parlay sharpness overhaul:** SGP redesigned 6→3-4 legs (+200–450), daily lay per-leg gates + Kelly sizing, longshot per-game cap of 2. **Lives in root copies; engine/sgp_builder.py is STALE with the OLD design (audit H1). Not committed to git.**
- **Audit 2026-04-28 (this run) — 52 new findings, 3 CRIT.** S-41 actually only ~92% closed (132 print() in run_picks.py, ~10 are warnings/errors that should be logger). M-26 paths.py adoption only ~13% (most modules still hardcode `~/Documents/JonnyParlay/`). H-7 webhook_fallback module exists but is never invoked. See `AUDIT_2026-04-28.md` for full punch list.

## pick_log.csv Schema (current — schema_version 3, 28 columns)
`date, run_time, run_type, sport, player, team, stat, line, direction, proj, win_prob, edge, odds, book, tier, pick_score, size, game, mode, result, closing_odds, clv, card_slot, is_home, context_verdict, context_reason, context_score, legs`

- `run_type`: primary | bonus | manual | daily_lay | sgp | longshot
- `tier`: T1 | T1B | T2 | T3 | KILLSHOT | DAILY_LAY | SGP | LONGSHOT | MANUAL
- `stat`: SOG | PTS | REB | AST | 3PM | SPREAD | ML_FAV | ML_DOG | TOTAL | TEAM_TOTAL | F5_ML | F5_SPREAD | F5_TOTAL | PARLAY
- `is_home`: True/False for SPREAD/ML/F5/TEAM_TOTAL picks; blank for props (canonical: `normalize_is_home`)
- `clv`: closing_implied_prob − your_implied_prob (positive = beat the close); filled by capture_clv.py
- `context_verdict`: supports | neutral | conflicts | skipped | disabled — blank on normal runs (context disabled by default)
- `legs`: JSON array for parlay rows. **SGP populates ✓** | longshot populates ✓ (no rows yet) | **daily_lay does NOT populate** — puts string descriptor in `game` field instead (audit F2.6/F4.5 — pending fix). primary/bonus/manual leave it blank. NOTE: pick_log_mlb.csv has 282 rows (Apr 27-28) missing the trailing `legs` comma because positional writerow writes 27 fields and shadow CLV is off so the rewrite-normalization sweep never runs (audit F3.5).

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
Preferred (audit M-26, **only ~13% adopted** — `clv_report`, `csv_writer`, `grade_picks`, `projections_db` import paths.py; `run_picks`, `capture_clv`, `analyze_picks`, `morning_preview`, `discord_guard`, `results_graphic`, etc. still hardcode `~/Documents/JonnyParlay/`): set `JONNYPARLAY_ROOT` to the repo root. Modules that import `engine/paths.py` honor this env var.
```
export JONNYPARLAY_ROOT=/sessions/.../mnt/JonnyParlay
python engine/grade_picks.py --date YYYY-MM-DD [--repost] [--dry-run]
```
Windows deployments leave the env var unset — `paths.py` falls back to `~/Documents/JonnyParlay` so existing behavior is unchanged.

Legacy fallback (still works for scripts that haven't been migrated): symlink `~/Documents/JonnyParlay/data` → project data dir.

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
- `data/discord_posted.json` can get truncated/corrupted on Windows mount. **CLAIMED FIX APR 28 NOT IMPLEMENTED (audit C2):** `_load_unlocked` in `engine/discord_guard.py:99-104` silently returns `{}` on `JSONDecodeError`. Every guard key resets, full daily run reposts to Discord with @everyone. The "regex scan of raw bytes" rebuild path documented here doesn't exist anywhere in the codebase. Manual recovery today: stop engine, restore from backup, restart.

## Preferences
- Responses: terse, direct. No unnecessary summaries.
- Code: edit `engine/run_picks.py` (source of truth). Always sync to root after edits (`cp engine/run_picks.py run_picks.py`). Same for grade_picks.py, results_graphic.py. **Sync rule is currently broken in BOTH directions** (audit H1+H2): root `secrets_config.py` is truncated, engine `sgp_builder.py` is stale. Production loads root copies — verify via import resolution before editing. Cowork mount = `/sessions/.../mnt/JonnyParlay/`. Windows path = `C:\Users\jono4\Documents\JonnyParlay\`. mbp/ folder is RETIRED (but "MBP" terminology lives in run_picks.py:5037 print + R12 docstring + Master_Betting_Prompt_v9_4.md doc).
- Premium tier stays at 5 picks — do not change.
- Discord recap shows model picks only (primary/bonus/daily_lay from main log). Manual picks never appear in Discord. Shadow sports (MLB) excluded from all Discord output.
- Recap embed W-L structure (Apr 28 2026): **Props** (primary+bonus, excl. KILLSHOT) · **⚡ KILLSHOT** (separate) · **Parlays** (daily_lay+sgp+longshot). Week/month footer shows all three independently. Constants: `PROP_RUN_TYPES = {"primary","bonus"}`, `PARLAY_RUN_TYPES = {"daily_lay","sgp","longshot"}` in grade_picks.py.
