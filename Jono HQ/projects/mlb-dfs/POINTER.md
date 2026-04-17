# MLB DFS — Pointer

Same folder as NBA. The MLB pipeline does **not** live in Jono HQ. The working tree is at:

```
Documents/Claude/Projects/nba dfs analysis/
```

Folder name is historical — it houses both NBA and MLB now.

## What's in that folder (MLB-specific)
- `scripts/pipeline_mlb.py` — main script (v2.1)
- Shared helpers with NBA: `cull_lineups.py`, `slice_lineups.py`, `run_tonight.py`
- `inputs/today/MLB_{DATE}_input.csv` — SaberSim export
- `inputs/today/MLB_DKSalaries_{DATE}.csv` — DK salaries

## Where the context lives
Project prompt: `Jono HQ/prompts/02_MLB_DFS_Pipeline.md`

## Hard rule reminder (MLB-specific)
Never layer player-level Min Exposures on top of stack-level Min Exposures — deadlocks SaberSim. This is also saved in auto-memory as `feedback_mlb_min_exposure_deadlock.md`.

## Where results / postmortems should land
TODO: standardize alongside NBA.
