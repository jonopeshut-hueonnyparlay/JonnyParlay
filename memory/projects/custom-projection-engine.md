# Project: Custom Projection Engine

## Status
**Last updated: Apr 30 2026.** All 5 engine files built and committed. DB has 79k game log rows + 587 players indexed. Steps 1–4 coded but not fully wired — three DB tables are empty and blocking a meaningful backtest.

**Blocking issues:**
- `team_defense` — 0 rows → matchup_factor not computing (TODO at nba_projector.py:522)
- `pace_factors` — 0 rows → pace_factor defaulting to 1.0
- `injury_status` — 0 rows → no injury adjustments in projections

**Next session:** populate those three tables, verify projector produces sensible output, then run the backtest (step 5).

**SaberSim stays live as the data source until custom projector is proven.** Parallel run, not a cutover.

## Goal
Replace SaberSim ($197/mo) as the CSV input for `engine/run_picks.py`. Zero changes to the existing betting engine — the projector just emits a CSV in the exact SaberSim schema that `parse_csv()` already reads.

## Go-Live Gate
100+ picks, custom CLV ≥ SaberSim-sourced CLV → cancel SaberSim.

## Files (all exist)
- `engine/projections_db.py` — SQLite schema + historical pull
- `engine/nba_projector.py` — EWMA rates, minutes, pace, matchup
- `engine/injury_parser.py` — nbainjuries integration + minutes redistribution
- `engine/csv_writer.py` — SaberSim schema output
- `engine/backtest_projections.py` — MAE + CLV comparison harness
- `data/projections.db` — 79k rows, 587 players; team_defense/pace_factors/injury_status empty

## Output Schema (must match SaberSim exactly)
`Name, Pos, Team, Opp, Status, Saber Team, Saber Total, dk_std` + sport stats
- `dk_std = proj_pts * 0.35` placeholder
- Status: Out → "O", Questionable → "Q", active → "Confirmed", unknown → ""
- Validate output by feeding to `parse_csv()` in run_picks.py before declaring done

## Core Formula
```
projected_stat = per_minute_rate × projected_minutes × matchup_factor × pace_factor
```
- per_minute_rate: EWMA span=10 (`pandas.Series.ewm(span=10).mean()`)
- projected_minutes: EWMA baseline + injury/B2B/blowout adjustments
- pace_factor: `game_implied_total / league_avg_total` (from Odds API, already in pipeline)
- matchup_factor: opp allowed rate vs. position / league avg, clipped to [0.80, 1.20]

## Build Order (strict, no skipping)
1. projections_db.py — SQLite + nba_api historical, verify clean load
2. nba_projector.py — unit test on 3 known players
3. injury_parser.py — nbainjuries + minutes redistribution
4. csv_writer.py — feed output to parse_csv() to confirm
5. backtest_projections.py — MAE + CLV comparison
6. Iterate EWMA/matchup weights until CLV ≥ SaberSim over 50+ picks
7. Parallel run 2-3 weeks
8. NHL projector
9. MLB projector
10. NFL projector (off-season, lowest urgency)

## Conventions to Reuse
- `engine/name_utils.py::fold_name()` for all cross-source name matching
- `engine/paths.py` for path resolution (honors `JONNYPARLAY_ROOT`)
- Secrets via `engine/secrets_config.py` / `.env`

## Data Sources (verify latest versions at build time — do not hardcode from brief)
- NBA: `nba_api` (V3 endpoints for 25-26 season), `nbainjuries` (official PDF parser), Basketball Reference (scrape w/ 3s+ delay, cache to `data/cache/bref_defense_{date}.json`)
- NHL: `api-web.nhle.com/v1/` (new API — old one dead), `nhl-api-py`, Natural Stat Trick CSVs
- MLB: `pybaseballstats` (not original pybaseball), `statsapi.mlb.com`. Never project PA-based batter stats until SP confirmed.

## Target MAE (NBA)
PTS ±5, AST ±2, REB ±2.5 — but CLV is the primary metric, not MAE.

## Notes for Future Sessions
- This project runs in a separate Cowork session. If asked about it here, treat as in flight in the other session — do not duplicate work or start building files in this session unless explicitly asked.
- SaberSim CSVs continue to flow daily — the existing pipeline is untouched.
