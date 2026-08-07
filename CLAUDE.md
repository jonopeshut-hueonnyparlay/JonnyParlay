# Memory

## Current State — scalars & data-gates
Dated, frequently-updated content (calibrated constant values, open data-gate status, refit
history) lives in `docs/CURRENT_STATE.md` — **update that file, not this one**, when a
constant refits or a gate opens/closes. This file holds static structure: architecture, file
map, schema, conventions. Split out 2026-08-03 to keep this file's structural content stable
while the scalars/gates section churns with every calibration cycle (same reasoning EdgeModel
uses for its own gates pointer).

## Closed Audits
`docs/archive/audits/AUDIT_HISTORY.md` — all pre-2026-06 audits closed (archived).

---

## Me
Jono (jonopeshut@gmail.com). Sports bettor, DFS player, Discord community operator. Runs picks as a trading business — analytical, sharp, luxury brand.

## Brand
**picksbyjonny** · Tagline: *edge > everything* · Aesthetic: luxury · sharp · analytical  
Discord bot display name: **PicksByJonny**

## Projects

| Name | What |
|------|------|
| **JonnyParlay** | Python betting engine — run_picks.py + grade_picks.py. Runs on Windows at `C:\Dev\JonnyParlay` |
| **Discord Overhaul** | Full server rebuild — **done**. Phase 1 design + Phase 2 manual build both shipped. |
| **KILLSHOT** | Premium tier (**v3**, Plan 6 §13). Full gate spec in **Terms** table below. Posts to #killshot with @everyone; near-misses logged to pick_log_blocked.csv as `KILLSHOT_{ODDS\|WP\|STAT}`; module-load invariant (`_assert_killshot_invariants`) asserts allowlist stats unsuspended + tier-eligible. |
| **KairosEdge** | Halftime trade system — buying trailing team YES in full-game winner market. Tracked separately. |
| **EdgeModel** (Custom Projection Engine) | **Separate repo at `C:\Dev\EdgeModel`** (no longer JonnyParlay code). Replaces SaberSim — produces `projections.db`, consumed by run_picks via `EDGEMODEL_DB_PATH`. **Run daily FROM EdgeModel:** `python engine\generate_projections.py [--run-picks]` (chains into JonnyParlay picks); `--late-run` re-fetches injuries without DB persist; `--shadow` → pick_log_custom.csv, no Discord. **Go-live gate:** ~100 shadow CLV rows (frozen — NBA offseason). **Key features:** EWMA + Bayesian projection, role-tier minute scalars (RS+PO), confirmed-starter lineups (`lineup_fetcher.py`), injury redistribution, 240-min + Vegas team-total constraints, blowout sigmoid, `[HIGH-VAR]` 3PT flag. Has its own CLAUDE.md; **no test suite** — validate producer changes by running the calibration. |

## Key Files

| File | Purpose |
|------|---------|
| `engine/run_picks.py` | Main betting engine orchestrator (**~1646 lines**; refactored 2026-06-12 from 6982 — constants + logic in 30+ focused modules, see **Engine Module Map**). `main()` decomposed into named stage helpers. **Runs `health_check.py` first as a pre-run gate** (`_run_health_gate`, aborts on blocking config-integrity FAIL; bypass `--skip-health-check`). **Source of truth — edit engine/ only; root entry points are shims.** Flags: `--force-card`, `--no-cache`. **Game lines decoupled 2026-06-13 (f69095b)** — run_picks no longer cards/logs/posts game lines (TEAM_TOTAL/SPREAD/TOTAL/ML/F5); `analyze_game_lines.py` is sole source. `evaluate_game_lines` still runs internally for prop-correlation filtering only; NRFI/YRFI shadow-log to pick_log_shadow_stats.csv; Daily Lay unchanged. |
| `engine/health_check.py` | Pre-run system-integrity gate (~20 checks: constants match, no stale paths, `.env` keys, key files, `projections.db` freshness, **both repos clean/pushed**, PLATT_SPACE↔formula, SGP ρ provenance, reliability-curve drift §20). Auto-runs inside run_picks; standalone `python engine/health_check.py`. <30s. Blocking fails only (CLAUDE.md-size + git-clean are warn). |
| `engine/grade_picks.py` | Auto-grades pick_log.csv + pick_log_game_lines.csv; posts Discord recaps (game lines to `DISCORD_GAME_LINES_WEBHOOK`). Monthly summary auto-fires on 1st of month. |
| `engine/capture_clv.py` | CLV daemon — polls every 2 min, captures closing odds T-45 to T+3; CLV written only within T-10 of tip. Scheduled via Task Scheduler at 10am daily. S4U logon. `MAX_DAEMON_UPTIME_SECS=18h` guard prevents no-picks day from blocking next-day start. Also watches `pick_log_custom.csv` when `ENABLE_CUSTOM_CLV=True`. |
| `engine/clv_report.py` | CLI report: `python clv_report.py [--days N] [--sport X] [--tier Y] [--stat X] [--shadow]` |
| `engine/analyze_picks.py` | Backtest analysis dashboard. Usage: `python analyze_picks.py [--sport X] [--since YYYY-MM-DD] [--stat X] [--shadow] [--export]` |
| `engine/weekly_recap.py` | Weekly P&L recap posted to #announcements every Sunday. |
| **EdgeModel repo** (`C:\Dev\EdgeModel`) | Projection engine — `nba_projector.py`, `projections_db.py`, `injury_parser.py`, `csv_writer.py`, `lineup_fetcher.py`, `backtest_projections.py`, and the `mlb/nhl/wnba_stats_fetcher.py` historical loaders all live HERE now (moved out of JonnyParlay). Produces `projections.db` (status: MLB 8,095 games/69k pitcher/169k batter; NHL 3,936 games/142k skater/15k goalie; WNBA loaded). Run from EdgeModel: `python engine\generate_projections.py`. See EdgeModel's own CLAUDE.md. |
| `engine/calibrate_distributions.py` | (Still JonnyParlay) Within-player distribution calibration; reads the EdgeModel DB via `EDGEMODEL_DB_PATH`. Outputs NB r, Normal CV, Poisson confirmation per stat. Run: `python engine/calibrate_distributions.py [--sport NBA\|MLB_P\|MLB_B\|NHL_SK\|NHL_G] [--save] [--mode team-sigmas\|wnba-sigma]`. |
| `data/pick_log.csv` | Model-generated ledger (primary / bonus / daily_lay / sgp / longshot). Starts Apr 14 2026. **29-column** header (schema_version=4, last col is `over_p_raw`). No longer receives game-line/TEAM_TOTAL rows from run_picks (decoupled 2026-06-13). |
| `data/pick_log_manual.csv` | Manual picks only (--log-manual). Same 29-column schema. Graded alongside main log but never posted to Discord. Excluded from CLV daemon. |
| `data/pick_log_mlb.csv` | Historical MLB shadow log (pre-go-live, Apr 12–May 19). MLB now posts to main `pick_log.csv`. |
| `data/pick_log_wnba.csv` | Historical WNBA shadow log (pre-go-live, through Jun 8 2026). WNBA now posts to main `pick_log.csv`. Still graded by grade_picks.py and CLV-watched (`ENABLE_WNBA_CLV`) until legacy rows close. |
| `data/pick_log_calibration.csv` | **Calibration shadow log** (added 2026-06-14). Captures ALL evaluated prop picks with valid `over_p_raw` — qualified **and** gate-failed — for unbiased Platt calibration (10–50× more signal/day than pick_log.csv). Written by run_picks (`run_type=calibration`, guarded by `--no-save`), never posted, graded silently daily via grade_picks.py shadow loop. Gate: **Calibration Platt** (0/100) in `gate_check.py`. NB: requires the `log_picks` `run_type`-param fix (was hard-coded `"primary"`). |
| `data/pick_log_blocked.csv` | Gate failure audit log. Structural gate failures (props + game lines) logged by log_blocked_pick() on each run. Excludes suspension gates. Created on first run. |
| `data/pick_log_game_lines.csv` | Game-line bet log. Written by `analyze_game_lines.py` confirm-to-log flow. Not yet wired to capture_clv.py. |
| `analyze_game_lines.py` | Standalone game-line edge analyzer. Confirm-to-log flow: after ranked table, prompts user to select rows; writes to `data/pick_log_game_lines.csv` (29-col schema, run_type=game_line, card_slot=GL). Discord posting via `_post_game_lines_discord()` — console preview when `DISCORD_GAME_LINES_WEBHOOK` blank, live POST when set. Not yet wired to capture_clv.py. `PICK_LOG_GAME_LINES_PATH` added to `engine/paths.py`. |
| `sgp_builder.py` | Root shim → `engine/sgp_builder.py`. NBA SGP builder. Allowed books: FanDuel, BetMGM, DraftKings, theScore (espnbet), Caesars (williamhill_us), Fanatics, Hard Rock (hardrockbet). Logs as `run_type=sgp`. |
| `engine/mlb_sgp_builder.py` | MLB SGP builder (added 2026-05-29). 3-4 legs, +200–+450. Stats: OUTS (pitchers); HITS (batters). **t-copula (ν=6)** with MLB-calibrated ρ table. Fires automatically when MLB CSV is present. Logs to pick_log.csv: `sport=MLB, tier=SGP`. ρ table: OUTS-over + opposing HITS-under = 0.30; all other cross-type pairs = 0.02. Kill R2_MLB: OUTS-under + HITS-under same game → killed. `MIN_LEG_WIN_PROB_OUTS=0.62` (lower than global 0.65 — tuned to old OUTS σ; SIGMA['OUTS']=0.27 now). SP scratch guard: drops leg if confirmed SP changes before build. Cohesion: pitcher_dom/batter_hot tags via _correlation_cohesion_mlb() (weight=0.25). |
| `start_clv_daemon.bat` | Launcher for CLV daemon. **Must contain ASCII only** — non-ASCII chars cause cmd.exe to crash with exit code 255. |
| `setup_clv_task.ps1` | Registers CLV daemon scheduled task. S4U logon + WakeToRun. `ExecutionTimeLimit=22h`. Re-run as admin to reset. |
| `post_nrfi_bonus.py` | One-shot webhook poster for manual bonus drops. Uses Mozilla UA to bypass Cloudflare 1010. Restored 2026-05-27. |
| `engine/gate_check.py` | Single-shot CLI reporting all open gate counts. Run: `python engine/gate_check.py`. Added 2026-06-03. |
| `engine/context_research_v2.py` | **Active daily context layer** — zero-Anthropic-cost, free-public-API drop-in replacing the paid v1. Same `data/context_verdicts.json` schema + 15-factor weighted aggregation (line move, ERA/FIP, bullpen, weather, umpire, pythag, form, home/away, rest, travel, division, motivation, injury; rlm/public_sharp stale-neutral until `ACTION_NETWORK_PRO_KEY` set). **Run AFTER run_picks, BEFORE analyze_game_lines:** `python engine/context_research_v2.py --sport ALL`. Display-only until Plan 11 gate. |
| `engine/context_research.py` | Legacy paid-Opus v1 (still present; superseded by v2). 5 parallel group calls/game. Manual fallback: `context_prep.py` (prompt→clipboard) + `save_context.py` (paste Claude.ai JSON back). |
| `engine/gate_digest.py` · `engine/clv_weekly_export.py` · `engine/tools/calibration_dashboard.py` | Reporting: weekly gate-counter Discord digest (`DISCORD_GATES_WEBHOOK`, blank→console); weekly per-pick CLV ledger CSV; rolling per-stat reliability dashboard. |
| `replay/run_replay.py` | Determinism trust-anchor — re-runs run_picks against frozen `replay/snapshots/` (freezegun) for byte-identical output. **Any code change must keep replay byte-identical** or it moved pricing. `--capture` to re-baseline. Snapshot: 06-15 MLB+WNBA (no NBA — capture when in season). |
| `README.md` · `config/thresholds.toml` | Repo map / data-flow / entry points. `thresholds.toml` (gitignored; `.example` committed): opt-in TOML overrides of whitelisted scalar thresholds only (frozen/calibrated constants excluded — enforced in code). |
| `docs/research/STATISTICAL_FOUNDATIONS.md` | **Statistical foundations audit (Plan 6).** Every distribution/constant validated vs literature; 21 sections LOCKED/PERIODIC_RECAL/DATA_GATED/NEEDS_CHANGE with citations. **Check before changing any distribution/statistical constant.** All 11 NEEDS_CHANGE resolved. |
| `docs/research/EDGEMODEL_FOUNDATIONS.md` | **EdgeModel projection + context audit (Plans 7–8).** EWMA spans, minute scalars, Vegas constraint, scalars/deflators, DK_STD, 3PM arch, blend alphas (7); home/away, blowout sigmoid, days-rest, REB priors, role tiers, cold-start, injury redist, status probs (8). **Check before changing any EdgeModel projection/context constant.** July-refit NEEDS_CHANGE incl. STL/BLK span, AST Vegas-anchoring, spot=1.6124, `_REB_RATE_PRIOR` ~2× deflation. Locks: blend alphas, PAD_3P=242, OT cap, Vegas prior. |
| `docs/research/MARKET_FOUNDATIONS.md` | **Market-facing foundations audit (Plan 9).** NRFI/YRFI, anti-correlation filters (X1, ρ bands), CLV methodology, SLOW_BOOKS, parlay construction, tier system, hard rules (R4/R7/R9/R10/R12), caps. All 12 NEEDS_CHANGE resolved. **Check before changing any market-facing constant/gate/card rule.** Plan 10: ~70 items A–GG audited; backlog + corrected STAT_FAMILY_TIER implemented. |

## Engine Module Map (post-2026-06-12 refactor)
*Test suite: ~1451 collected as of 2026-06-20 (run `pytest --collect-only -q -m "not network" --basetemp=C:/Dev/JonnyParlay/.pytest_tmp` for live count — treat any doc figure as a hint, verify before setting targets).*
`run_picks.py` is now a thin orchestrator; constants and logic live in focused modules under `engine/`:
- **`engine/quant/`** — pure math: `distributions.py`, `odds.py`, `derived.py`, `copula.py` (probit/cholesky/copula_joint_prob/copula_joint_approx).
- **`calibrated.py`** — fitted values: `SIGMA`, `SIGMA_WNBA`, `NB_R`, `NB_R_WNBA`, `COMBO_RHO_WNBA`, `GAME_SIGMA`, `F5_SIGMA`, `MLB_TEAM_RUN_R`, `MLB_PARK_FACTORS`, `KELLY_MARKET_MULT`, `PLATT_A`/`PLATT_B`, `STAT_FAMILY_TIER`, `BM_SHRINKAGE_WEIGHT`, `_load_team_sigmas()`.
- **`thresholds.py`** — structural decision-boundary constants: `KELLY_FRACTION`, `PLATT_SPACE`, KILLSHOT + gate thresholds, WNBA gate constants.
- **`market_config.py`** — runtime/market wiring: `SPORT_KEYS`, `SUSPENDED_STATS`.
- **`gates.py`** — `check_prop_gates`, `check_game_gates`. **`rules.py`** — `apply_hard_rules`, R12, caps.
- **`sizing_core.py`** — `kelly_units`, `apply_bm_shrinkage`. **`sizing.py`** — `size_picks_base`, `size_bonus_pick`, `size_picks_vake`.
- **`prob_core.py`** — `calc_prop_prob`, `pick_score`, `_platt_calibrate_prop`. **`evaluators.py`** — `evaluate_props`, `evaluate_game_lines`, `evaluate_f5_lines`, `evaluate_nrfi` (`NRFI_GAMMA` lives here).
- **`correlation.py`** — `deduplicate`, `filter_game_line_correlations`, `filter_cross_type_correlations`.
- **`odds_io.py`** — `OddsFetcher`, CSV parsing, extractors. **`team_resolve.py`** — `get_game_sigma`/`get_game_sigma_team`/`get_mlb_team_run_r`, `resolve_team_abbrev`. **`wnba_gate.py`** — WNBA early-season gate logic. **`name_norm.py`** — `normalize_name`. **`pick_log_lock.py`** — `_pick_log_lock` primitive.
- **`parlays.py`** — pure parlay builders (`build_safest6_parlay` et al.). **`killshot.py`** — KILLSHOT selection/gating (`_assert_killshot_invariants` fires at import). **`discord_post.py`** — Discord I/O, embeds, posters, `set_confirm_mode`/`get_confirm_mode`, `_CTX_VERDICTS`. **`output_format.py`** — `fmt_*`, `format_output`.
- **`pick_log_writers.py`** — WRITERS (`log_picks`, `log_blocked_pick`). **`pick_log_io.py`** — pre-existing locked READERS (unchanged — **distinct from** pick_log_writers.py).
- **SGP contract (keep intact):** `sgp_builder.py` still imports `PICK_LOG_PATH`, `_pick_log_lock`, `_normalize_odds`, `_normalize_size`, `_write_schema_sidecar`, `_webhook_post` from `run_picks` — these remain re-exported. `_pairwise_rho` stayed in `sgp_builder.py` (NBA domain logic).

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
| KILLSHOT | Highest-conviction tier. v3 gate (Plan 6 §13): score≥65, odds ∈ [-200,+110], wp ≥ implied_prob(odds)+0.03, stat ∈ {PTS,AST} (no tier req; SOG removed while suspended), WNBA excluded. Sizing: 3u default, 4u iff wp≥0.70 AND edge≥0.06. Weekly cap 2. Manual `--killshot NAME` bypasses selection but must pass odds+wp+score≥75, counts to cap. @everyone ping. |
| Premium | Top 3 picks per sport from the model each day |
| Bonus Drop | Single highest-scoring NEW pick per run (max 5/day) |
| Daily Lay | Alt spread parlay — 3-leg (min 2), model-identified mispriced lines. **Max combined odds: +100**. Per-leg gates: `edge≥0.025`, `cover_prob≥0.58`. `MIN_DAILY_LAY_PROB=0.50`. Kelly-derived sizing: 0.25–0.75u via `size_daily_lay()`. Redesigned Apr 28 2026. |
| SGP | Same-Game Parlay — **3-4 leg**, **+200–450**. NBA + MLB builders. **t-copula (ν=6)** joint prob (`copula_joint_prob`, `quant/copula.py`). BetMGM preferred, allowed books only. Sizing: 0.25u / 0.50u premium (EV margin ≥0.10 AND cohesion ≥0.55 AND avg_edge ≥0.035). `--sgp-only` forces SGP post. |
| Longshot | 6-leg parlay of safest picks. Logged as `run_type=longshot`. Per-game cap: max 2 legs (`LONGSHOT_MAX_PER_GAME=2`). Per-player cap: max 1 leg (added 2026-05-29 — same player's stats are correlated). Added Apr 28 2026. |
| Value Parlay | 5-leg fallback parlay — fires when longshot cannot build a 6-leg slip. Same safest-picks pool, same per-game (max 2) and per-player (max 1) caps. Posts to #bonus-drops. Logged as `run_type=value_parlay`, `tier=LONGSHOT`. Fixed size: `VALUE_PARLAY_SIZE=0.25u`. Added 2026-06-03. |
| CLV | Closing Line Value — primary edge indicator. Positive = beat the close. Raw vigged closing implied minus raw vigged open implied (not vig-free — consistent with industry standard). |
| CO-legal books | 12 CO-approved books (P0.1). API key "espnbet" = display "theScore Bet" |
| cold_start sub-types | Players below `MIN_GAMES_FOR_TIER=10` classified at projection time (cap applied after role scalar; `project_player()` in EdgeModel nba_projector.py): **taxi** (0 career games, cap 12); **returner** (≥180d out, cap min(avg,22)); **extended_absence** (60–179d, cap min(avg×0.70,25)); **new_acquisition** (<60d, cap min(avg,28)). |

## Books / APIs
- **Odds API key + Discord webhooks:** loaded from `.env` via `engine/secrets_config.py`
  - Windows path: `C:\Dev\JonnyParlay\.env` (also searches project root + `engine/.env`)
  - Template: `.env.example` (committed). Real `.env` is gitignored.
  - Debug inventory: `python engine/secrets_config.py` prints a redacted summary.
  - `DISCORD_GAME_LINES_WEBHOOK` added to `secrets_config.py` + `.env` — blank by default; set to go live (no code change needed).
- `espnbet` in Odds API → display as **theScore Bet** everywhere
- CO_LEGAL_BOOKS in `engine/book_names.py` (pruned 18→12, P0.1)

## Python Dependencies
- Install: `pip install -r requirements.txt --break-system-packages`
- **Hard deps (required to import):** `filelock` (cross-process locks), `requests`
- **Soft deps (feature-gated):** `openpyxl` (xlsx recap)

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
- **Daily total cap: 12u** (12.0 literal in `apply_caps()`, `rules.py` — `G12` in code is the pitcher-prop same-game direction gate, unrelated) — hard ceiling across all run_types per session.
- **Sport unit caps:** NBA=8.0u | MLB=8.0u | NHL=5.0u | NFL=5.0u | WNBA=4.0u max per pick (`SPORT_UNIT_CAP` dict).
- **VALUE_PARLAY_SIZE=0.25u** — fixed size for value_parlay (5-leg fallback parlay; fires when longshot cannot build).
- **NHL SOG stat cap:** max 6 picks per run (`STAT_CAP = {"SOG": 6, ...}`; default cap = 2 for other stats).

## Negative Correlation Filter System
Two functions in `engine/correlation.py` run before `build_safest6_parlay()` (`parlays.py`) to prevent anti-correlated legs from combining in the longshot pool:

**`filter_game_line_correlations()`** — GL vs GL pairs. Rules 1-5:
- R1: Team ML/SPREAD + opponent TEAM_TOTAL over → kill
- R2: F5_ML both teams same game → kill
- R3: TOTAL over + TOTAL under same game → kill
- R4: TOTAL + TEAM_TOTAL same direction → kill
- R5: NRFI + YRFI same game (ρ=−1.0) → kill *(added 2026-05-29)*

**`filter_cross_type_correlations()`** — Prop vs GL pairs *(added 2026-05-29)*:
- X1 (HARD): Pitcher HA/ER UNDER + opposing TEAM_TOTAL OVER same game (ρ≈−0.65–0.75 — fewer hits/ER = fewer runs)

**SGP hard kills** (in sgp_builder.py and mlb_sgp_builder.py) are separate — they operate within a single SGP slip, not the main card/longshot pool. MLB-specific kills:
- R2_MLB: OUTS-under + HITS-under same game → kill (pitcher struggles = more hits; negative correlation).

## MLB Status
**LIVE as of 2026-05-20.** Posts to Discord, logs to `pick_log.csv`, CLV auto-captured. Historical shadow log: `data/pick_log_mlb.csv` (pre-go-live).

## WNBA Status
**LIVE as of 2026-06-09.** Posts to Discord, logs to `pick_log.csv`. `SHADOW_SPORTS` empty (defined in `market_config.py`; mirrored in grade_picks.py). CLV daemon watches main log + legacy `pick_log_wnba.csv` until legacy rows close (then `ENABLE_WNBA_CLV=False`). In force: `SPORT_UNIT_CAP`=4.0u, G_WNBA_EDGE (EV≥0.0955), G_WNBA_OPEN, early-season sigma dampener (2027). **Excluded from KILLSHOT** (sport check in `_passes_killshot_v2_gate`, `killshot.py`) until CLV history matures. REB pinned to 0.25u floor (mult 0.10 both dirs, revisit n≥50); REB over remains R4-shadow-routed.

## Running grade_picks.py in Cowork
Set `JONNYPARLAY_ROOT` to the repo root → all modules resolve paths (`export JONNYPARLAY_ROOT=/.../JonnyParlay; python engine/grade_picks.py --date YYYY-MM-DD [--repost] [--dry-run]`). Windows leaves it unset — `paths.py` falls back to `~/Documents/JonnyParlay`.

## ⚠ Cowork Write Caution
If the engine runs on Windows and writes to pick_log.csv, do NOT use the Write tool to rewrite pick_log.csv — it will clobber engine-written rows. Use Edit/append only.

## Daily Routine
1. **Projections (from EdgeModel):** `cd C:\Dev\EdgeModel` → `python engine\generate_projections.py --run-picks` (builds projections.db, then chains into JonnyParlay picks). `--late-run` for late injury updates. *(Or run picks directly from JonnyParlay: `python engine\run_picks.py [csv]` — auto-discovers the CSV; runs health_check first.)*
2. **Context (after picks, before game lines):** `python engine\context_research_v2.py --sport ALL`
3. **Game lines (separate):** `python analyze_game_lines.py` (ranked table → confirm-to-log). Set `DISCORD_GAME_LINES_WEBHOOK` to post live; otherwise console preview only. Not yet CLV-wired.
4. **Done** — CLV daemon captures automatically; `grade_picks.py` grades after games.
- Quick checks: `python engine\health_check.py` (pre-run integrity), `python engine\gate_check.py` (data-gate status).

## CLV Daemon
- Scheduled: Windows Task Scheduler, daily 10am, runs `start_clv_daemon.bat`
- Logon: **S4U** (fires without active desktop session). WakeToRun enabled. `ExecutionTimeLimit=22h`.
- `MAX_DAEMON_UPTIME_SECS=18h` — exits if no picks logged after 18h (prevents blocking next-day start on zero-pick days).
- Manual trigger: `schtasks /run /tn "JonnyParlay CLV Daemon"` or foreground `python -u engine\capture_clv.py`
