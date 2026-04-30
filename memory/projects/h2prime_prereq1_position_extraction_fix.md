# H2'-PREREQ1 — Fix position=UNK extraction in player_index

## Context (read this first)

You're working on the **JonnyParlay Custom Projection Engine**, an in-flight NBA projection system replacing SaberSim ($197/mo). The project is mid-Phase-2 root-cause work. H1 (healthy-filter at min≥15) landed and hit the PTS MAE gate by 0.005 but left a sharp residual fingerprint — starter MIN undershoot, bench overshoot, <15-projected-minutes catastrophe, 35+ overshoot.

A 1,300-line deep-research deliverable returned 2026-04-23 with verdict: **Architecture A+** (per-minute × minutes outer decomposition is correct; inner rate term must be role-conditioned). The first real architectural change is **H2' — role-tier classifier (5 tiers) with role-matched rate subsampling**.

**H2' cannot ship until position data is valid.** During the Phase 1 slice diagnostic, the position bucket was `UNK` for all ~19,829 rows — `player_index.position` is not being populated. The role-tier classifier depends on position-aware priors (esp. for cold-start: "position × archetype × prior-team rate" — see research §2.5.3, §4.4). Position is also needed for:

- Per-stat position-tier Bayesian shrinkage (REB/AST/STL/BLK vary dramatically by position)
- Starter-out absorption minutes (G/F vs C → different backup absorption magnitude)
- Joint-distribution correlation matrices (5 position-tier-specific matrices)

**This prompt is the surgical fix for that bug.** Do NOT expand scope. Do NOT build the role-tier classifier in this ticket. Just get valid positions into `player_index` end-to-end and prove it with a diagnostic.

## NO BAND-AIDS directive

Every change must be:
1. A **bug fix** (the code did something demonstrably wrong), OR
2. A **causal model feature** with written mechanism, OR
3. A **scope correction** with written rationale

Forbidden: empirical constants, player-name overrides, tuned multipliers, hardcoded fallback positions ("set everyone to G"). If the data source doesn't expose position, the fix is to pull from a source that does, not to invent one.

Every code change gets a comment: `# [H2'-PREREQ1] <causal reason>`.

## Investigation checklist

Before writing any fix, do all of the following:

### 1. Locate where player_index is built and populated

Search the engine for references to `player_index`, `.position`, and the table/dataframe schema:

```
grep -rn "player_index" engine/
grep -rn "position" engine/ --include="*.py"
```

Identify:
- Source file(s) that **write** `player_index` rows (the ETL path)
- Source file(s) that **read** `player_index.position` (the consumers)
- DB schema for the table (if stored in `projections.db`) or the dataframe schema (if in-memory)

### 2. Trace where position *should* come from

The most likely upstream sources, in order of preference:

1. **`nba_api.stats.endpoints.CommonPlayerInfo`** — returns `POSITION` field (e.g., "Guard", "Forward-Guard", "Center"). Most reliable.
2. **`nba_api.stats.endpoints.CommonTeamRoster`** — also exposes `POSITION` per team-season.
3. **`nba_api.stats.endpoints.LeagueDashPlayerBioStats`** — bulk endpoint, all players one season.
4. **Basketball Reference scrape** — `PlayerSeasonFinderPage` or per-player page. Slower (3s crawl delay) but most complete historically.

Check which of these are already being called elsewhere in the codebase (e.g., in `engine/nba_api_client.py` or similar). Piggyback on existing API calls where possible.

### 3. Identify the failure mode

Exactly one of the following is true — figure out which:

- **A: No position extraction exists.** `player_index.position` is never populated anywhere; default value is `UNK` or NULL.
- **B: Position extraction exists but is broken.** The code attempts to populate it but hits an exception, wrong field name, or silent `.get('POSITION', 'UNK')` fallback.
- **C: Position is populated in one code path but consumed from another.** Writer populates correctly but downstream reader pulls from a different column / table / dataframe that doesn't have it.
- **D: Position data is stale.** Written once at season start but not refreshed after trades / changes.

Write a short diagnostic block (as a comment in the relevant file or in a markdown writeup) showing:
- Which failure mode you found
- The exact file+line where the break happens
- A 1-sentence causal explanation

## The fix

Based on which failure mode you diagnosed:

**If A or B:** Add/fix extraction. Use `CommonPlayerInfo` or `LeagueDashPlayerBioStats` (preferred: one bulk call per season is cheaper than N per-player calls). Parse the raw `POSITION` string into a canonical enum:

```python
# [H2'-PREREQ1] Canonical position enum — normalizes nba_api's
# "Guard"/"Forward-Guard"/"Guard-Forward"/"Forward"/"Forward-Center"/"Center"
# into 3 buckets required by role-tier classifier (H2') and per-position
# Bayesian shrinkage (H6'). Do not add a 6th bucket without updating
# the research report's position-tier correlation matrices in §5.9.
POSITION_CANONICAL = {
    "Guard":          "G",
    "Guard-Forward":  "G",   # primary = first-listed position
    "Forward-Guard":  "F",
    "Forward":        "F",
    "Forward-Center": "F",
    "Center-Forward": "C",
    "Center":         "C",
}
```

Note: the research recommends 5 position tiers (PG/SG/SF/PF/C) for correlation matrices. For now, map to 3 (G/F/C) — finer granularity requires depth-chart + height + wingspan, which is a separate enrichment step. The role-tier classifier needs only coarse G/F/C for H2'.

**If C:** Fix the reader path to consume from the correct source, or consolidate. Do not duplicate data.

**If D:** Add a refresh trigger on trade-deadline + weekly cron. Out of scope for this ticket if position is *mostly* correct — document the stale-data limitation and move on.

## Validation

After the fix:

1. Run the slice diagnostic:
   ```
   python engine\backtest_slice.py --start 2025-10-22 --end 2026-04-13 --min-minutes 15 --out slice_results_2026-04-23_prereq1 -v
   ```
2. Verify the position bucket breakdown in the slice report shows G/F/C (or finer) populated for ≥95% of rows. Target: `UNK` rate below 5%. If any single position bucket has <500 rows, something's still broken.
3. Spot-check: pick 20 players at random from `player_index` and verify their position against Basketball Reference. Target: ≥18/20 correct.
4. Append the diagnostic result (failure mode identified + fix applied + UNK rate post-fix + spot-check rate) to `memory/projects/custom-projection-engine-phase2-root-cause.md` under a new `### H2'-PREREQ1 RESULT` header.

## Out of scope for this ticket

- Do NOT build the role-tier classifier (that's H2')
- Do NOT change any rate computation logic
- Do NOT change the minutes baseline
- Do NOT expand to 5-bucket position (PG/SG/SF/PF/C) — coarse 3-bucket is sufficient for H2'
- Do NOT add height/wingspan/archetype — those are for v2+

## Deliverables

1. **Code change** — minimal diff, traced to the diagnosed failure mode.
2. **Diagnostic writeup** — appended to Phase 2 plan as H2'-PREREQ1 RESULT section.
3. **Slice re-run** — confirms UNK rate <5% and no regression on existing MAE / bias metrics.
4. **Spot-check** — 20-player manual verification against Basketball Reference.

## Files you'll likely touch

| File | Likely role |
|------|-------------|
| `engine/player_index.py` (or wherever it lives) | Primary edit target — position field population |
| `engine/nba_api_client.py` (or equivalent) | Source of the new `CommonPlayerInfo` / `LeagueDashPlayerBioStats` call |
| `engine/projections_db.py` | Schema update if position column type changes / new column |
| `engine/backtest_slice.py` | Sanity check that slice report shows position buckets |
| `memory/projects/custom-projection-engine-phase2-root-cause.md` | Append H2'-PREREQ1 RESULT section |

## Success criteria

- `player_index.position` populated to canonical G/F/C for ≥95% of active roster players
- Slice diagnostic re-run shows position bucket breakdown with real values (no universal UNK)
- Spot-check confirms ≥18/20 players have correct position
- No regression in PTS MAE (still ≤5.0), MIN bias (still ≈ -0.07), or starter/bench MIN bias vs post-H1 numbers
- Phase 2 plan updated with the RESULT block
- Code comments tag every change with `# [H2'-PREREQ1] <reason>`

Once this passes, H2'-PREREQ2 (garbage-time filter on rate inputs) is unblocked, followed by H2' proper (role-tier classifier + role-matched rates).
