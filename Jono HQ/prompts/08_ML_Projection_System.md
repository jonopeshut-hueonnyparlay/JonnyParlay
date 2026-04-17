# Project Context — v7 ML Projection System (NBA + NCAAB Game Lines)

Load this when we're working on the v7 engine — game-line projections, model training, feature engineering, gap analysis, or anything in the `v7_daily.py` workflow.

---

## What this project is
A machine learning engine that predicts game margins and totals for NBA and NCAAB. Outputs feed picksbyjonny game-line picks (project 05 — Sports Betting Core). It is **not** a DFS tool — DFS uses SaberSim, this is for spreads/totals/MLs.

## Current state
**Last verified:** 2026-03-28 — these numbers are 10+ days stale, refresh before quoting them in any pick or stakeholder context.

- **NBA:** 56.2% win rate (18-14), +2.00u, 21 features, 17,709 training games
- **NCAAB:** 52.9% win rate (18-16), +0.83u, 13 features, 18,854 training games
- Models are XGBoost + Neural net stacker, with a market-shrinkage layer that accounts for low R² (0.14 NBA, 0.10 NCAAB)

## Where the files live
- **Project folder:** `Jono HQ/projects/ml-projection-system/`
- **Status reports (markdown, with .html originals kept as backup):**
  - `v7_master_status_2026-03-28.md` — full status: done items, pending commands, remaining TODOs
  - `v7_master_action_list.md` — prioritized action list, deduplicated across roadmaps
  - `v7_gap_analysis.md` — architecture gaps, root causes, fix proposals
  - Originals at `v7_*.html` — same content, kept until the markdown versions are confirmed clean
- **Code:** lives outside this folder (the actual `v7_daily.py`, `ncaab/features.py`, etc. — confirm path before editing)

## Known critical gaps (as of last status)
1. **NBA favorite compression** — model under-predicts margin at spreads >12 (79% compression at 18+). Current bandaid is `SPREAD_CAP=15`. Real fix needs a separate blowout model or quantile regression.
2. **NCAAB Barttorvik features are season-level snapshots** — stale by March, miss teams peaking/declining into the tournament. Fix is daily timestamped scrapes.
3. **NCAAB injury feature scraper exists but is not wired into the model** — ~30 min fix in `ncaab/features.py`.
4. **Model R² is honest but low** (0.14/0.10) — caps the realistic per-game edge at 2-3%, so this is a volume game, not a conviction game.

## Pending commands to run (from status report)
- `python v7_daily.py train nba` — retrain with 27-feature structure (after ref backfill)
- `python v7_daily.py ref-backfill` — ~5h overnight job to populate `ref_assignments` from NBA Stats API
- `python v7_daily.py ref-tendencies` then `train nba` — after backfill completes
- `python validation/feature_audit.py` — confirm np.bool_ serialization fix
- `python v7_daily.py train-stacker` — once 50+ shadow predictions are accumulated

## Hard rules (project-specific)
1. **R² is what it is.** Don't propose fixes that try to inflate R² without acknowledging the market-shrinkage layer is the right call given the data.
2. **Volume over conviction.** Edge is small per game; the model needs to play a lot of games, not size up on individual picks.
3. **Shadow log before going live.** New features/models run in shadow mode for 50+ predictions before they affect real picks.
4. **NCAAB ≠ NBA.** Don't assume a fix that works for NBA transfers — different feature sets, different training sizes, different market efficiencies.
5. **This feeds picksbyjonny game lines.** When the model says "edge here," that becomes a Sports Betting Core pick (project 05). It does not become a DFS decision.

## When working on this project
- If I ask "what should I work on next," start with the action list HTML and rank by Critical → Next Sprint → When Ready.
- If I want to ship a fix, confirm whether it's coded but unrun (just needs a command) vs needs new code.
- Status reports are HTML right now — fine for now, but if we revisit them more than twice, convert to markdown.

## Open to-dos
- ~~Convert HTML status reports to markdown~~ ✓ done 2026-04-07 (mechanical conversion, stat-box header has minor artifacts, all content preserved)
- Document where the actual `v7_daily.py` code lives
- Connect this project's outputs to the bet-tracker so v7 picks auto-populate the game-lines sheet (see `projects/bet-tracker/SCHEMA.md` for the target columns — and note that CLV columns don't exist there yet, which is the bigger blocker)

---
*Last updated: 2026-04-07*
