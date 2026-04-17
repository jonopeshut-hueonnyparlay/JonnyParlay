# NBA DFS — Pointer

The NBA DFS pipeline does **not** live in Jono HQ. The working tree is at:

```
Documents/Claude/Projects/nba dfs analysis/
```

Why it's external: the git repo is sandbox-side at `/sessions/zen-adoring-cori/nba_git/.git` because OneDrive corrupts `.git` files inside mounted folders. Moving the working tree would break the git linkage.

## What's in that folder
- `scripts/pipeline_nba.py` — main script (v7, ~1,390 lines)
- `scripts/pipeline_mlb.py` — MLB pipeline lives in the same folder (project 02)
- `scripts/cull_lineups.py`, `slice_lineups.py`, `run_tonight.py`, `slate_validator.py` — helpers
- `tests/test_pipeline_nba.py` — 17 regression tests
- `docs/` — CHEATSHEET.md, NBA_STACK_REFERENCE.md, SaberSim_Complete_Settings_Guide.md, TROUBLESHOOTING.md
- `inputs/today/` — daily input CSVs
- `outputs/` — daily output CSVs
- `RUNBOOK.md` — operating runbook
- `nba_git_backup_2026-04-07.zip` — last full backup

## Where the context lives
Project prompt: `Jono HQ/prompts/01_NBA_DFS_Pipeline.md`

## Where results / postmortems should land
TODO: standardize. Currently `results/{DATE}/` is referenced inside the prompt as "if I've created it" — no canonical home yet.
