# Project Context — Golf DFS Pipeline (PGA)

Load this when we're working on PGA DFS, the VTO scoring system, the exclusion pipeline, or any golf-related SaberSim build.

---

## What this project is
A weekly PGA DFS pipeline targeting DraftKings tournaments. Builds a "VTO" (Value Through Outcomes) score for every golfer in the field, then generates ladder pools (3MAX, 20MAX, 150MAX, SE) sized for different contest types. SaberSim consumes the upload CSVs to build the actual lineups.

## Where the code and files live
- **Project folder:** `Jono HQ/projects/golf-dfs/`
- **Spec:** `spec/DFS_Exclusion_Pipeline_System_Spec.md` — the exclusion pipeline design doc, read this before suggesting any structural changes
- **Pools:** `pools/VTO_2026_Pool_*.csv` — filtered player pools by contest type (3MAX, 20MAX, 150MAX, SE)
- **SaberSim uploads:** `uploads/VTO_2026_SS_Upload_*.csv` — the files that get uploaded to SaberSim, one per contest type
- **Reports:** `reports/VTO_2026_Full_Field_*.csv`, `Top30_*.csv` — scored field reports and top-30 cuts
- **Skill bundle:** `dfs-pipeline.skill` — packaged skill version of the pipeline

## File naming convention
- `_v2`, `_v4` suffixes are versioned outputs. Treat the highest version as canonical unless I say otherwise.
- `Pool_*` = filtered player pool (input to upload)
- `SS_Upload_*` = the SaberSim-formatted upload (caps + cores baked in)
- `Full_Field_*` = scored full field, used as the source for everything else

## Hard rules (golf-specific, on top of the master prompt rules)
1. **SaberSim builds the lineups, never hand-pick.** Same rule as NBA/MLB. All fixes are upload settings, caps, or cores.
2. **Sim Mode for every GPP, including SE.** No Optimizer.
3. **No total ownership sum cap.** Per-player caps only.
4. **Pool size matches contest type.** 3MAX = small/cash-leaning, 20MAX = mid GPP, 150MAX = large GPP, SE = single entry.
5. **Exclusion pipeline is the core IP.** Don't bypass it to "just include" a player. If the exclusion logic is wrong, fix the rule, not the output.

## When working on this project
- If I'm debugging a missing player, start with the exclusion pipeline spec — usually the player got filtered for a reason.
- If I want to ship lineups to SaberSim, the answer is which `SS_Upload_*.csv` to use, not "build me lineups."
- If I'm comparing v2 to v4, the diff is usually in the scoring weights or exclusion rules.

## Open to-dos / known gaps
- (none documented yet — populate as we work)

---
*Last updated: 2026-04-07*
