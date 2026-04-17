# NBA DFS Pipeline — Context Prompt

Paste this at the start of any conversation about NBA DFS work.

---

## Who I am
I'm Jono (jonopeshut@gmail.com). I run the picksbyjonny brand and play daily fantasy sports on DraftKings. This prompt is for my **NBA DFS pipeline**.

## The pipeline
- **Location:** `nba dfs analysis/` (OneDrive-synced folder on my machine)
- **Main script:** `scripts/pipeline_nba.py` (~1,390 lines, v7)
- **Helpers:** `scripts/cull_lineups.py`, `scripts/slice_lineups.py`, `scripts/run_tonight.py`, `scripts/slate_validator.py`
- **Tests:** `tests/test_pipeline_nba.py` (17 regression tests, all passing)
- **Docs:** `docs/CHEATSHEET.md`, `docs/NBA_STACK_REFERENCE.md`, `docs/SaberSim_Complete_Settings_Guide.md`, `docs/TROUBLESHOOTING.md`, `RUNBOOK.md`
- **Inputs:** `inputs/today/NBA_{DATE}_input.csv` and `inputs/today/NBA_DKSalaries_{DATE}.csv`
- **Outputs:** 7 files per run (Pool_SE.csv, Pool_20MAX.csv, SS_Upload_SE.csv, SS_Upload_20MAX.csv, SE_Core_Lock.txt, Stacking_Guide.txt, SaberSim_Settings.txt)

## How I play
- **DraftKings NBA Classic** only
- **Modes I run:** SE (single-entry), 3MAX, 20MAX, 150MAX
- **Workflow:** pipeline generates a player pool + exposure caps + core locks → I upload to SaberSim → SaberSim's Sim Mode builds the lineups → I post to DK
- **I DO NOT hand-pick lineups.** SaberSim does the building. My job is to feed it the right pool, caps, and cores.
- **Always Sim Mode.** Never Optimizer, for any GPP mode including SE.

## Recent shipped work (committed 2026-04-07)
Seven research-validated fixes in one commit (`e304018`):

| Fix | What | Where |
|---|---|---|
| **#1** | Hard per-player exposure caps (3MAX 67%, 20MAX 70%, 150MAX 55%, SE 40% manual) | `exposure_rec()` + SaberSim Settings.txt |
| **#2** | `scripts/cull_lineups.py` — drops bottom 25% by projection | helper script |
| **#3** | Module-level `NBA_SLOTS` + `core_fits_roster()` + regression tests | pipeline_nba.py + tests/ |
| **#4** | `scripts/slice_lineups.py` — build-once-slice across contests | helper script |
| **#5** | Wide MinExposure windows in upload CSV (Max − 35, floor 0) to prevent SaberSim deadlocks | `_pool_to_upload()` writer |
| **#6** | SE Core Lock tags builds as CEILING/CONTRARIAN, BALANCED, FLOOR/SAFE with contest assignment guidance | SE core lock writer |
| **#7** | `DFS_STACK_MODE` A/B feature flag (`legacy` / `leverage` / `off`) via `stack_bonus()` helper | top of pipeline_nba.py + combo loop |

**Git:** repo lives at `/sessions/zen-adoring-cori/nba_git/.git` (sandbox-side — OneDrive corrupts .git in the mounted folder). Backup zip at `nba_git_backup_2026-04-07.zip` in folder root.

## Hard rules (do NOT violate)
1. **Never propose total lineup ownership sum caps.** Per-player caps OK, total sum caps forbidden.
2. **Always Sim Mode for every GPP mode including SE.** Never recommend Optimizer.
3. **SaberSim builds the lineups.** Frame every fix as "change the upload settings / caps / core lock" — never as "hand-pick players" or "play more of X."
4. **Stacking logic changes must be A/B tested before committing.** Even when research says the change is obviously better. Use the `DFS_STACK_MODE` flag to A/B over multiple slates before flipping the default.
5. **NBA correlation is NEGATIVE for same-team players**, positive for bring-backs. Don't force same-team stacks.

## How to run it
```bash
# Basic (defaults to DFS_DATE from the config)
python scripts/pipeline_nba.py

# With A/B stack flag
DFS_STACK_MODE=legacy python scripts/pipeline_nba.py   # current default
DFS_STACK_MODE=leverage python scripts/pipeline_nba.py # bring-back only
DFS_STACK_MODE=off python scripts/pipeline_nba.py      # no stack bonus

# Specific date / output dir
DFS_DATE=2026-04-06 DFS_OUTPUT_DIR=/path/to/output python scripts/pipeline_nba.py

# Tests
python tests/test_pipeline_nba.py
```

## Post-build workflow
1. Upload `SS_Upload_20MAX.csv` to SaberSim
2. Apply settings from `SaberSim_Settings.txt` (toolbar values + hard caps section)
3. For SE: lock the SE core manually using `SE_Core_Lock.txt` (assign builds to contests per the role tags)
4. Let SaberSim's Sim Mode build
5. If oversupplied: `python scripts/cull_lineups.py --in export.csv --target 20`
6. If slicing across contests: `python scripts/slice_lineups.py --in master.csv --slice "DimeTime:20" "AndOne:20"`

## Open threads / known unknowns
- **Is STACK_MODE flag actually doing anything on live slates?** On 4/06 the top SE core combos had zero same-game pairs, so legacy and leverage produced identical output. Need 5+ slate A/B before deciding if leverage is distinguishable.
- **Is Fix #5 MinExposure actually pulling drift players back?** On 4/06 Embiid was recommended 49% but SaberSim only built him at 27% (no Min floor was set for that slate). Fix #5 should pin future slates' Min at ~14% for him. Needs verification on next live slate.
- **4/06 slate results** should land at `Jono HQ/projects/nba-dfs/results/2026-04-06/` per `projects/_RESULTS_STANDARD.md`. Biggest takeaway from the day: Castle +21 over projection at 61% exposure, Embiid boomed +12 but under-played.

## What I want from you
- Be terse, no trailing summaries
- Frame every exposure gap as "the upload settings should do X" — never "Jono should play Y more"
- When in doubt about stacking, default to legacy and A/B the change
- Always save big decisions to memory so I don't repeat myself
- If you're about to recommend something that touches file paths or function names, verify they still exist first

---
*Last updated: 2026-04-07 | Pipeline v7 | Commit e304018*
