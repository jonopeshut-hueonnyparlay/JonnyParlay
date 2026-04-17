# MLB DFS Pipeline — Context Prompt

Paste this at the start of any conversation about MLB DFS work.

---

## Who I am
I'm Jono (jonopeshut@gmail.com). I run the picksbyjonny brand and play daily fantasy sports on DraftKings. This prompt is for my **MLB DFS pipeline**.

## The pipeline
- **Location:** `nba dfs analysis/` (same folder as NBA — the folder name is historical, it houses both sports now)
- **Main script:** `scripts/pipeline_mlb.py` (v2.1)
- **Shared helpers:** `scripts/cull_lineups.py`, `scripts/slice_lineups.py`, `scripts/run_tonight.py`
- **Inputs:** `inputs/today/MLB_{DATE}_input.csv` (SaberSim export) + DK salaries CSV
- **Outputs:** Pool + SS_Upload CSVs per mode + SE_Core_Lock.txt + SaberSim_Settings.txt + Stacking_Guide.txt

## How I play
- **DraftKings MLB Classic GPP only** (no Showdown, no cash games for now)
- **Modes I run:** SE, 3MAX, 20MAX, 150MAX
- **Workflow:** pipeline generates pool + caps + stack cores → upload to SaberSim → Sim Mode builds lineups
- **Same as NBA:** I do NOT hand-pick. SaberSim's Sim Mode does the building.

## MLB-specific differences from NBA
- **MLB correlation is POSITIVE for same-team (stacking), strongly negative for opposing pitcher**
- **Stack cores are the whole ballgame** — the pipeline leans on 4-5 man team stacks with secondary 2-3 man stacks
- **Pitcher selection is binary** — you either bet on the SP or you don't. Bad SP = whole lineup sinks.
- **Lineup locks** matter — confirmed lineups are gold, projected lineups are risky. Always check RotoWire / MLB starting lineups before locks.
- **Weather is a real factor** (wind, temp, humidity) — affects HR rate and totals. Use the `weather-impact-analyzer` skill when relevant.
- **Umpire assignments** affect K/BB rates — niche but real.

## Hard rules (do NOT violate)
1. **Never propose total lineup ownership sum caps.** Per-player caps OK.
2. **Always Sim Mode** for every GPP mode.
3. **SaberSim builds the lineups.** Don't frame fixes as "play more of X" — frame as upload settings.
4. **Do NOT layer player-level Min Exposures on top of stack-level Min Exposures.** I learned this the hard way on MLB — it deadlocks SaberSim. Pool-level min/max caps on individual players are fine; stack + player min together = broken.
5. **Stacking logic changes must be A/B tested** before committing, even when research disagrees.

## Recent state
- Pipeline v2.1 built and running
- DK Classic GPP only
- Running through SaberSim (via RunPureSports.com subscription, not sabersim.com directly)

## v2.1 changelog (TODO — fill in)
The MLB pipeline shipped to v2.1 but the diff vs v2.0 is not documented here yet. Before the next material change, populate this block the same way the NBA prompt documents commit `e304018`:

| Fix | What | Where |
|---|---|---|
| TODO | TODO | TODO |

## Open threads
- MLB is in-season right now (April 2026) — I'm running slates regularly
- Need to evaluate if the Fix #5 wide-window MinExposure approach from NBA should be ported to MLB upload writer
- Results tracking / CLV over the MLB season — should I be logging per-slate results somewhere structured?

## What I want from you
- Terse. No trailing summaries.
- Check RotoWire / MLB.com for confirmed lineups before recommending pitcher or hitter plays
- Weather matters — don't forget to check it for outdoor games
- Frame all fixes as upload settings, never manual lineup edits
- Save non-obvious MLB-specific decisions to memory

---
*Last updated: 2026-04-07 | Pipeline v2.1*
