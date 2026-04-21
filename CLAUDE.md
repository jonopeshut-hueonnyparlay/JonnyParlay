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
| **Discord Overhaul** | Full server rebuild — **done**. Phase 1 design + Phase 2 manual build both shipped. |
| **KILLSHOT** | Premium tier (v2, Apr 21 2026). Auto-qualifies only when ALL pass: `tier=T1` strict, `pick_score≥90`, `win_prob≥0.65`, `odds ∈ [-200, +110]`, `stat ∈ {PTS,REB,AST,SOG,3PM}`. Sizing: 3u default, 4u iff `win_prob≥0.70 AND edge≥0.06` (no 5u). Weekly cap: **2**. Manual override (`--killshot NAME`) bypasses gate but still counts toward cap + requires `score≥75`. Posts to #killshot with @everyone. |
| **KairosEdge** | Halftime trade system — buying trailing team YES in full-game winner market. Tracked separately from props. |

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
| `data/pick_log.csv` | Model-generated ledger (primary / bonus / daily_lay). Starts Apr 14 2026. 27-column header. |
| `data/pick_log_manual.csv` | Manual picks only (--log-manual). Same 27-column schema. Graded alongside main log but never posted to Discord recap. Excluded from CLV daemon. |
| `data/pick_log_mlb.csv` | Shadow log for MLB (still in SHADOW_SPORTS). Include in analyze with --shadow flag. |
| `start_clv_daemon.bat` | Launcher for CLV daemon — called by Task Scheduler. Requires `PYTHONUNBUFFERED=1` + `python -u` (S4U logon). |
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
| Daily Lay | Alt spread parlay — 3-leg, model-identified mispriced lines |
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
- **Closed Apr 21 2026 — 78/78 items resolved.** Section 40 (schema-version fail-fast via sidecar) + Section 41 (print → logging via `engine/engine_logger.py`) were the final two items. Full regression suite: 756 passed, 2 skipped.

## pick_log.csv Schema (current)
`date, run_time, run_type, sport, player, team, stat, line, direction, proj, win_prob, edge, odds, book, tier, pick_score, size, game, mode, result, closing_odds, clv, card_slot, is_home, context_verdict, context_reason, context_score`

- `run_type`: primary | bonus | manual | daily_lay
- `tier`: T1 | T1B | T2 | T3 | KILLSHOT | DAILY_LAY
- `stat`: SOG | PTS | REB | AST | 3PM | SPREAD | ML_FAV | ML_DOG | TOTAL | TEAM_TOTAL | F5_ML | F5_SPREAD | F5_TOTAL | PARLAY
- `is_home`: True/False for SPREAD/ML/F5 picks; blank for props
- `clv`: closing_implied_prob − your_implied_prob (positive = beat the close); filled by capture_clv.py
- `context_verdict`: supports | neutral | conflicts | skipped — blank on normal runs (context disabled by default)

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
Preferred (audit M-26, closed Apr 21 2026): set `JONNYPARLAY_ROOT` to the repo root. Every engine tool routes path resolution through `engine/paths.py`, which honors this env var.
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

## Preferences
- Responses: terse, direct. No unnecessary summaries.
- Code: edit `engine/run_picks.py` (source of truth). Always sync to root after edits (`cp engine/run_picks.py run_picks.py`). Same for grade_picks.py, results_graphic.py. Cowork mount = `/sessions/.../mnt/JonnyParlay/`. Windows path = `C:\Users\jono4\Documents\JonnyParlay\`. mbp/ folder is RETIRED.
- Premium tier stays at 5 picks — do not change.
- Discord recap shows model picks only (primary/bonus/daily_lay from main log). Manual picks never appear in Discord. Shadow sports (MLB) excluded from all Discord output.
