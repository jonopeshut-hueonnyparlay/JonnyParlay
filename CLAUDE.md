# Memory

## Active Scalars — `engine/nba_projector.py`
- `PLAYOFF_MINUTES_SCALAR` (~line 242): starter=1.075, sixth_man=0.960, rotation=0.924, spot=0.948, cold_start=0.400. Refit 2026-05-06 on 3925 pairs (3 seasons).
- `REGULAR_SEASON_MINUTES_SCALAR` (~line 261): starter=1.0534, sixth_man=1.0139, rotation=1.0327, spot=1.5695, cold_start=1.0034.
- `REGULAR_SEASON_STAT_SCALAR` (~line 276): pts=1.0019, ast=1.0120, reb=1.0264, fg3m=1.0231, blk=1.0608, stl=1.0017, tov=1.000.
- `LEAGUE_AVG_PACE`=100.22 (2025-26 season-to-date; 2024-25 RS=99.58). `LEAGUE_AVG_PACE_PO`=96.5.
- `_HOME_AWAY_DELTA`: pts=0.0235, reb=0.0088, ast=0.0333, fg3m=0.0452, blk=0.0439, tov=−0.0122.
- `_REB_RATE_PRIOR`: G=0.058, F=0.079, C=0.133.
- `DK_STD_FLOOR`: starter=4.0, sixth_man=4.0, rotation=3.5, spot=3.0, cold_start=3.0. `DK_STD_COEFF`=0.35.
- `HIGH_VAR_CV_THRESHOLD`=0.60, `HIGH_VAR_MIN_GAMES`=8 (3PT specialist bimodal flag, RB8 H5).
- Blowout sigmoid: k=0.15, mid=20.0, max_reduction=0.19 (refit 2026-05-06 on 24,600 rows).
- `PLATT_A`=1.4988, `PLATT_B`=−0.8102 — **frozen** until H3 gate.

## Data-gated / Open
- **H3 (Platt refit)**: gated on ~300 post-v4 `over_p_raw` rows (~13 as of 2026-05-09). Check: count non-empty `over_p_raw` in pick_log.csv.
- **Shadow CLV go-live**: need ~100 CLV rows in `pick_log_custom.csv` (0/86 as of 2026-05-09). Daemon stable post-2026-05-09 MAX_UPTIME fix.
- **Role-tier thresholds** (26/20/12/5 MPG, 0.60 starter_rate in `classify_role()`) not empirically refit — candidate for next calibration session.

## Closed Audits
Full fix-pass details: `docs/audits/AUDIT_HISTORY.md`

| Audit | Findings | Status |
|-------|----------|--------|
| 2026-05-06 projection deep-dive | 0C/5H/8M/5L | ALL CLOSED (H3 data-gated) |
| 2026-05-05 injury + deep audit | various | ALL CLOSED |
| 2026-05-04 10-agent | 14C/17H/28M/17L | ALL CLOSED |
| 2026-05-02 10-agent season | 6C/33H/16M/3L | ALL CLOSED |
| 2026-05-01 | 0C/2H/4M/9L | ALL CLOSED |
| 2026-04-28 | 3C/11H/14M/20L | ALL CLOSED |
| 2026-04-21 | 78 items | ALL CLOSED |

---

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
| **Custom Projection Engine** | Replacement for SaberSim as `run_picks.py` CSV input. **Code:** engine/nba_projector.py + projections_db.py + injury_parser.py + csv_writer.py + backtest_projections.py; data/projections.db (SQLite, ~16 MB). **Run daily:** `python engine\generate_projections.py [--run-picks]`. **Late updates:** `--late-run` re-fetches injuries + re-runs without DB persist. **Shadow mode:** `--shadow` → logs to pick_log_custom.csv, no Discord (parallel CLV validation). **Go-live gate:** ~100 shadow CLV rows (0/86 as of 2026-05-09). **Key features:** EWMA + Bayesian projection per player, role-tier minute scalars (RS + PO), confirmed-starter lineup integration (`engine/lineup_fetcher.py`, C1 2026-05-08), injury redistribution (override/bump split), 240-min lineup-protected constraint, Vegas team-total constraint, blowout sigmoid, high-var `[HIGH-VAR]` flag for bimodal 3PT scorers. Development log: `docs/audits/AUDIT_HISTORY.md`. Full spec: `memory/projects/custom-projection-engine.md`. |

## Key Files

| File | Purpose |
|------|---------|
| `engine/run_picks.py` | Main betting engine (~5k+ lines). **Source of truth — edit engine/ only. Root entry points are shims.** Flags: `--force-card` (override card guard), `--no-cache` (bypass 11-min Odds API cache — picks pipeline only). |
| `engine/grade_picks.py` | Auto-grades pick_log.csv results, posts Discord recap + results graphic. Monthly summary auto-fires on 1st of month. |
| `engine/capture_clv.py` | CLV daemon — polls every 2 min, captures closing odds T-30 to T+3. Scheduled via Task Scheduler at 10am daily. S4U logon. `MAX_DAEMON_UPTIME_SECS=18h` guard prevents no-picks day from blocking next-day start. Also watches `pick_log_custom.csv` when `ENABLE_CUSTOM_CLV=True`. |
| `engine/clv_report.py` | CLI report: `python clv_report.py [--days N] [--sport X] [--tier Y] [--stat X] [--shadow]` |
| `engine/results_graphic.py` | Generates PNG results card posted to Discord after recap. |
| `engine/analyze_picks.py` | Backtest analysis dashboard. Usage: `python analyze_picks.py [--sport X] [--since YYYY-MM-DD] [--stat X] [--shadow] [--export]` |
| `engine/weekly_recap.py` | Weekly P&L recap posted to #announcements every Sunday. |
| `engine/morning_preview.py` | Posts daily card teaser to #announcements after run_picks.py runs. |
| `data/pick_log.csv` | Model-generated ledger (primary / bonus / daily_lay / sgp / longshot). Starts Apr 14 2026. **29-column** header (schema_version=4, last col is `over_p_raw`). |
| `data/pick_log_manual.csv` | Manual picks only (--log-manual). Same 29-column schema. Graded alongside main log but never posted to Discord. Excluded from CLV daemon. |
| `data/pick_log_mlb.csv` | Shadow log for MLB (still in SHADOW_SPORTS). Include in analyze with --shadow flag. |
| `sgp_builder.py` | Root shim → `engine/sgp_builder.py`. Same-Game Parlay builder. Allowed books: FanDuel, BetMGM, DraftKings, theScore (espnbet), Caesars (williamhill_us), Fanatics, Hard Rock (hardrockbet). Logs as `run_type=sgp`. |
| `start_clv_daemon.bat` | Launcher for CLV daemon. **Must contain ASCII only** — non-ASCII chars cause cmd.exe to crash with exit code 255. |
| `setup_clv_task.ps1` | Registers CLV daemon scheduled task. S4U logon + WakeToRun. `ExecutionTimeLimit=22h`. Re-run as admin to reset. |
| `post_nrfi_bonus.py` | One-shot webhook poster for manual bonus drops. Uses Mozilla UA to bypass Cloudflare 1010. |
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
| cold_start sub-types | R7/RB8. Players below `MIN_GAMES_FOR_TIER=10` in current season are classified at projection time: **taxi** — n_career_games=0, min cap=12; **returner** — last appearance ≥180 days, min cap=min(career_avg, 22); **extended_absence** — last appearance 60-179 days, min cap=min(career_avg×0.70, 25); **new_acquisition** — last appearance <60 days, min cap=min(career_avg, 28). Cap applied after role scalar. Source: `project_player()` in nba_projector.py. |

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

## pick_log.csv Schema (current — schema_version 4, 29 columns)
`date, run_time, run_type, sport, player, team, stat, line, direction, proj, win_prob, edge, odds, book, tier, pick_score, size, game, mode, result, closing_odds, clv, card_slot, is_home, context_verdict, context_reason, context_score, legs, over_p_raw`

Authoritative source: `engine/pick_log_schema.py`. Updated to v4 by RB8 IMMEDIATE 1 (2026-05-05).

- `run_type`: primary | bonus | manual | daily_lay | sgp | longshot
- `tier`: T1 | T1B | T2 | T3 | KILLSHOT | DAILY_LAY | SGP | LONGSHOT | MANUAL
- `stat`: SOG | PTS | REB | AST | 3PM | SPREAD | ML_FAV | ML_DOG | TOTAL | TEAM_TOTAL | F5_ML | F5_SPREAD | F5_TOTAL | PARLAY
- `is_home`: True/False for SPREAD/ML/F5/TEAM_TOTAL picks; blank for props
- `clv`: closing_implied_prob − your_implied_prob (positive = beat the close); filled by capture_clv.py
- `context_verdict`: supports | neutral | conflicts | skipped | disabled — blank on normal runs
- `legs`: JSON array for parlay rows (SGP ✓, longshot ✓, daily_lay ✓). primary/bonus/manual leave blank.
- `over_p_raw`: pre-Platt over-probability for prop picks. Blank for non-props and legacy v1–v3 rows. Populating ~300+ rows unblocks H3 Platt refit.

## Sizing Caps
- **Daily total cap: 12u** (`G12` check in run_picks.py) — hard ceiling across all run_types per session.
- **Sport unit caps:** NBA = 8.0u max per pick | NHL = 5.0u max per pick (`SPORT_UNIT_CAP` dict).
- **NHL SOG stat cap:** max 6 picks per run (`STAT_CAP = {"SOG": 6, ...}`; default cap = 2 for other stats).

## Context Sanity System
**Status: DISABLED by default.** Enable with `--context` flag. Requires `anthropic` package + `ANTHROPIC_API_KEY`.
- `run_pregame_scan()` — one Haiku + web_search call per sport (concurrent)
- `run_context_check()` — one call per pick (up to 8 concurrent), checks for OUT/scratched flags
- `conflicts` → pick cut | `supports` → pass + annotation | `neutral` → pass

## MLB Status
Still in **SHADOW_SPORTS** — picks go to `pick_log_mlb.csv`, not posted to Discord. Go-live = Jono's call.

## Running grade_picks.py in Cowork
Set `JONNYPARLAY_ROOT` to the repo root and every module resolves paths correctly:
```
export JONNYPARLAY_ROOT=/sessions/.../mnt/JonnyParlay
python engine/grade_picks.py --date YYYY-MM-DD [--repost] [--dry-run]
```
Windows deployments leave env var unset — `paths.py` falls back to `~/Documents/JonnyParlay`.

## ⚠ Cowork Write Caution
If the engine runs on Windows and writes to pick_log.csv, do NOT use the Write tool to rewrite pick_log.csv — it will clobber engine-written rows. Use Edit/append only.

## Daily Routine
1. Download SaberSim CSV
2. `python run_picks.py nba.csv` (or nhl.csv etc) — posts card, logs picks
3. Done — CLV daemon captures automatically, grade_picks.py grades after games

## CLV Daemon
- Scheduled: Windows Task Scheduler, daily 10am, runs `start_clv_daemon.bat`
- Logon: **S4U** (fires without active desktop session). WakeToRun enabled. `ExecutionTimeLimit=22h`.
- `MAX_DAEMON_UPTIME_SECS=18h` — exits if no picks logged after 18h (prevents blocking next-day start on zero-pick days).
- Manual trigger: `schtasks /run /tn "JonnyParlay CLV Daemon"` or foreground `python -u engine\capture_clv.py`
