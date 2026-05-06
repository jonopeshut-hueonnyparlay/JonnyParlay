# Runbook — late-day injury status changes

Closes audit item M1 (2026-05-06).

## Symptom

A player's injury status changes between the morning projection run and
tip-off.  Two flavors:

1. **Down-grade** (active → questionable / out / GTD).  The morning run
   classified them healthy, projected full minutes, and may have triggered
   redistribution bumps to teammates that no longer apply.
2. **Up-grade** (questionable → confirmed active).  The morning run may have
   excluded them entirely (status O / D), so teammates absorbed minutes that
   are now coming back.

The late NBA injury report fires several times during the day; the morning
projection run captures whichever snapshot existed at the time it ran.

## Why this matters

`injury_minutes_redistrib_bumps` is computed during projection generation
and persisted to the `projections` table.  Picks are emitted off the
persisted projections.  If the upstream injury status changed after that
write, the bumps are stale:

- A teammate's `proj_min` and `proj_pts` may reflect an OUT player who is
  actually playing.
- A taxi cold-start player who got promoted to "starter" via the bump path
  may now project too high (or vice versa).

The picks pipeline does not re-read the injury report; it trusts the
persisted projections.  So projections must be regenerated.

## Detection

- Compare the late NBA injury report (PDF or `nbainjuries` package output)
  against `injury_statuses` logged at the top of
  `engine/generate_projections.py` for today's run.  Any added scratches or
  newly-confirmed actives are operative.
- Spot-check teammates of the changed player in the most recent SaberSim
  CSV (output of `generate_projections.py`).  A starter projected at 8 min
  or a bench player projected at 32 min usually means a stale bump.
- `data/jonnyparlay.log` will contain the bump magnitudes from the morning
  run — useful for confirming which teammates were affected.

## Mitigation — `--late-run`

`engine/generate_projections.py --late-run` is the T-90 min second-pass.
It re-fetches injuries, re-runs `redistribute_minutes`, regenerates
projections, and overwrites the SaberSim CSV.  Pace and Odds API totals
are not re-called — the morning's cached pace / spreads / totals are reused
to stay within API quota.

```
# Live re-post (writes to pick_log.csv, posts updated card to Discord)
python engine\generate_projections.py --late-run --run-picks

# Shadow re-fire (writes to pick_log_custom.csv, no Discord)
python engine\generate_projections.py --late-run --shadow

# Bulk research re-log (all qualified picks, shadow log)
python engine\generate_projections.py --late-run --research
```

`--late-run` always regenerates projections from scratch, so any stale
bumps are wiped.  This is the canonical fix for the down-grade race
condition.

## Caveats

- Vegas totals / spreads / pace are not refreshed under `--late-run`.  If
  lines moved materially since morning (rare same-day, common day-of-rest
  shift), run `generate_projections.py` without `--late-run` for a full
  refresh — accepts the Odds API quota cost but ensures everything is
  current.
- `pick_log.csv` dedup at `engine/run_picks.py:3220-3235` keys on
  `(date, player, stat, line, direction)` — so re-running `--late-run
  --run-picks` will not double-log picks that already shipped.  Updated
  odds / size / proj overwrite the existing row.
- Shadow log dedup is bypassed (audit A2 fix, 2026-05-06): a `--late-run
  --shadow` re-fire appends fresh rows even if the morning run already
  populated the day.  This is intentional — shadow data is sampled, not
  ledger-canonical.
- KILLSHOT cap (`weekly cap = 2`) is enforced across re-runs via the
  Discord guard.  A re-run will not double-post a KILLSHOT that already
  fired.

## When to skip the runbook

If the changed player is on the GTD / Q boundary and ends up playing,
projections were correct as-is (binary in/out design — see
`memory/feedback_play_prob_binary.md`).  No action needed.

## Related

- Audit item M1 — `docs/audits/AUDIT_2026-05-06_projection_deep_dive.md` §M1
- `--late-run` flag definition — `engine/generate_projections.py:566-572`
- `redistribute_minutes` — `engine/nba_projector.py`
- Injury parser fallback to previous-day report — commit `fcf47e2`
