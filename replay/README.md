# Replay harness (P-1)

Deterministic, no-network replay of the `run_picks` pipeline against frozen
snapshots. This is the safety net for the audit fix pass — every code change is
diffed against a golden so nothing reprices silently.

## Why
`run_picks` reads live odds, the wall clock, and confirmed-starter APIs, and its
output (pick rows, the card) embeds timestamps. To compare "before vs after" a
fix you must remove all of that nondeterminism. This harness does:

- **Clock** frozen with `freezegun` (cache filename, tip-time filter, pick timestamps).
- **Odds** injected by monkeypatching `OddsFetcher._load_cache` to return the
  snapshot JSON. A cache hit short-circuits `fetch_all` — no network, and the
  snapshot's `events` are already tip-filtered.
- **MLB starters** stubbed to `{}` (no statsapi). *Limitation:* MLB SP-confirmation
  is disabled in replay — consistent run-to-run, but not identical to the original
  live run.
- **Writes** suppressed via `--no-save --no-discord` (run is effectively read-only).

## Scope
Replays `run_picks` against **frozen CSV + odds snapshots only** — it does NOT
re-run the EdgeModel projection engine (separate repo `C:\Dev\EdgeModel`). The
projection CSV is taken as a frozen input.

Snapshots retained: **2026-06-15 (MLB + WNBA)** — the only day whose raw odds JSON
survived. Earlier `pick_log` history exists but its odds snapshots weren't kept,
so it can't be replayed. Coverage grows forward as new snapshots are added.

## Usage
```bash
python replay/run_replay.py --list       # show discovered snapshot jobs
python replay/run_replay.py --capture    # write goldens from CURRENT code
python replay/run_replay.py              # check current code vs goldens (unified diff)
```
Exit code: `0` = all byte-identical, `1` = diffs or worker failure, `2` = no goldens.

## Validation gate
`--capture` then a plain run must report **0 diffs** (byte-identical) — that proves
the harness is deterministic. Do this against the `pre-audit-fixes-2026-06` tag
before any Phase 0 commit. After a real fix, a plain run shows the repricing diff.

## Per-task workflow during the fix pass
1. Before the change: `--capture` (golden = current behavior), commit goldens.
2. Make the fix.
3. `python replay/run_replay.py` → review the diff (expected vs surprising).
4. If the change is meant to reprice, re-`--capture` to move the golden forward.

## Adding a snapshot (capture-forward)
Create `replay/snapshots/<YYYY-MM-DD>/` with:
- `<SPORT>.csv` — the SaberSim projection CSV used that day.
- `odds_<SPORT>.json` — the matching `data/picks/cache/odds_<SPORT>_<date>.json`.
- `meta.json` — `{ "as_of": "<UTC instant on that day>", ... }` (see 2026-06-15).
Then `--capture` to add its golden.
