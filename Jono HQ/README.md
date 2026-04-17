# Jono HQ

This is the home base for everything I'm actively working on. One folder, one master prompt, eight projects. If I'm starting a new Claude conversation, the first thing to do is paste `00_MASTER_Jono.md` into the chat.

---

## How to use HQ in a Claude conversation

1. Open `00_MASTER_Jono.md` and paste the whole thing into a fresh Claude chat.
2. If the work is project-specific, also paste the matching prompt from `prompts/` (e.g., `01_NBA_DFS_Pipeline.md` for an NBA slate question).
3. Claude will reply with a one-liner confirming context is loaded. Then drive the conversation.

That's it. The master prompt loads who I am, my hard rules, my tools, and where every project lives. The project prompts add the specific context for whichever system we're touching.

---

## What's in HQ

### Top level
- **`00_MASTER_Jono.md`** — the master prompt. Always paste this first.
- **`README.md`** — this file. For me, not for Claude.

### `prompts/` — 8 project context files
| # | File | Project |
|---|---|---|
| 01 | `01_NBA_DFS_Pipeline.md` | NBA DFS via SaberSim |
| 02 | `02_MLB_DFS_Pipeline.md` | MLB DFS via SaberSim |
| 03 | `03_picksbyjonny_Brand.md` | IG, Twitter, TikTok, Discord content |
| 04 | `04_KairosEdge.md` | Halftime trading system |
| 05 | `05_Sports_Betting_Core.md` | Picks, props, CLV, line shopping |
| 06 | `06_Golf_DFS_Pipeline.md` | PGA DFS, VTO scoring |
| 07 | `07_Bet_Tracker.md` | CardPicks + GameLines spreadsheets |
| 08 | `08_ML_Projection_System.md` | v7 ML game-line model |

### `projects/` — working folders for each project
- **`nba-dfs/`** — `POINTER.md` only. Code lives at `Documents/Claude/Projects/nba dfs analysis/` (sandbox-side git).
- **`mlb-dfs/`** — `POINTER.md` only. Same external folder as NBA.
- **`picksbyjonny/`** — brand voice cheatsheet, content archive, results graphics, upsell library.
- **`kairos-edge/`** — trade journal, P&L tracker, base rates, current state.
- **`sports-betting/`** — sizing mode, CLV trend, line-shop log, daily startup notes.
- **`golf-dfs/`** — PGA DFS pipeline. `spec/`, `pools/`, `uploads/`, `reports/`, plus the `dfs-pipeline.skill` bundle.
- **`bet-tracker/`** — `picksbyjonny_CardPicks_Updated.xlsx` and `picksbyjonny_GameLines.xlsx`.
- **`ml-projection-system/`** — v7 engine status and gap analysis (HTML for now, convert to markdown when revisited).

### `archive/`
Anything that's been retired or replaced but shouldn't be deleted.
- `golf_dfs_pipeline_skill_backup.zip` — older snapshot of `projects/golf-dfs/dfs-pipeline.skill` (different content, kept as a rollback point)
- `golf-dfs-stale-v1/` — pre-v4 golf pool/upload/report files, superseded by `_v4` versions in `projects/golf-dfs/`

---

## What is NOT in HQ

The NBA + MLB DFS pipeline still lives at `Documents/Claude/Projects/nba dfs analysis/`. The git repo is sandbox-side and OneDrive corrupts `.git` files inside mounted folders, so moving the working tree would break linkage. The folder name is misleading — it houses both NBA and MLB pipelines, plus `scripts/`, `tests/`, `docs/`, `inputs/`, `outputs/`, `archive/`, and `RUNBOOK.md`.

When working on NBA or MLB DFS, the prompt file lives in HQ (`prompts/01_NBA_DFS_Pipeline.md`, `prompts/02_MLB_DFS_Pipeline.md`) but the actual code and data are in the original `nba dfs analysis/` folder.

---

## Migration notes (2026-04-07)

- Created Jono HQ from scratch on this date.
- Promoted the master prompt out of `Claude/Projects/nba dfs analysis/prompts/` (where it was buried 3 levels deep) to HQ root.
- Copied the 5 existing project prompts (01-05) to `prompts/`.
- Wrote 3 new prompts (06 golf, 07 bet tracker, 08 ML projection) for projects that previously had no Claude context.
- Migrated `bet tracker/`, `golf dfs analysis/`, and `machine learning projection system/` into `projects/` with cleaned-up names and (for golf) sorted into `pools/`, `uploads/`, `reports/`, `spec/`.
- Old folders at `Documents/Claude/Projects/` are still in place as a safety copy. Once everything in HQ is verified working, those can be deleted.

---
*Maintained by Jono. Last updated: 2026-04-07.*
