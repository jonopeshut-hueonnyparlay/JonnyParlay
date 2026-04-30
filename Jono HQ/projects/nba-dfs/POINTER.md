# NBA DFS — Pointer

*Last updated: 2026-04-21*

## Where the pipeline actually lives

**Canonical runnable script on this machine:**

```
C:\Users\jono4\Documents\DFS\DFS_Pipelines\pipeline_nba.py
```

That is the file that runs. Input CSVs (SaberSim export, DK Salaries) drop into the same folder. Output CSVs drop into the same folder.

## Single source of truth for system behavior

```
C:\Users\jono4\Documents\DFS\NBA\NBA_DFS_SYSTEM.md
```

Everything about kill layers, composite scoring, game environment tags, exposure caps, SE core lock, SaberSim settings philosophy, hard rules — read that file. It matches the v7 code on disk.

## Sandbox-only build (NOT on local disk)

A 2026-04-07 sandbox commit (`e304018` in `/sessions/zen-adoring-cori/nba_git/.git`) added:

- `DFS_STACK_MODE` A/B flag (`legacy` / `leverage` / `off`)
- `scripts/cull_lineups.py` — drop bottom 25% by projection
- `scripts/slice_lineups.py` — build-once-slice across contests
- `scripts/run_tonight.py`, `scripts/slate_validator.py`
- `tests/test_pipeline_nba.py` — 17 regression tests
- `docs/CHEATSHEET.md`, `docs/NBA_STACK_REFERENCE.md`, `docs/SaberSim_Complete_Settings_Guide.md`, `docs/TROUBLESHOOTING.md`
- `RUNBOOK.md`
- Module-level `NBA_SLOTS` + `core_fits_roster()` helper
- Wide MinExposure windows with ~14% floor for high-recommendation players

**None of that is on local disk.** If any doc references `nba dfs analysis/` or `Documents/Claude/Projects/...` — those paths don't exist here. The sandbox git repo exists at `/sessions/zen-adoring-cori/nba_git/.git` because OneDrive corrupts `.git` files inside mounted folders; moving the working tree would break the linkage.

Backup of sandbox state: `nba_git_backup_2026-04-07.zip` (sandbox-side).

## Project prompt

```
Jono HQ/prompts/01_NBA_DFS_Pipeline.md
```

## Results / postmortems

Not yet standardized. Prompt references `projects/nba-dfs/results/{DATE}/` but nothing is landing there. TODO.

## Archived stale docs

Superseded by `NBA_DFS_SYSTEM.md` and moved to `C:\Users\jono4\Documents\DFS\NBA\_archive_stale_docs_2026-04-21\`:

- `jono_nba_dfs_rule_system.md` (2026-01-22 — Carlson Rule / Bad Value Rule, not in v7)
- `jono_nba_dfs_complete_system.md` (2026-01-23 — adjusted-projection math, not in v7)
- `NBA_Pipeline_Prompt.md` (2026-04-02)
- `NBA_Pipeline_Prompt_v2.md` (2026-04-02 — adjusted-projection formulas, not in v7)
