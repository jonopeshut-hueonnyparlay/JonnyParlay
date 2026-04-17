# Project Context — Bet Tracker

Load this when we're working on logging picks, updating the tracker spreadsheets, computing ROI/CLV, or building tracker-related views.

---

## What this project is
The source-of-truth log for every pick I post under picksbyjonny. Two spreadsheets, one per market type:
- **`picksbyjonny_CardPicks_Updated.xlsx`** — props and "card picks" (the daily curated card I sell to Discord)
- **`picksbyjonny_GameLines.xlsx`** — game-line picks (spreads, totals, MLs)

## Where the files live
`Jono HQ/projects/bet-tracker/`

## Why two files
Card picks and game lines have different sizing rules, different CLV behavior, and feed different downstream content (results graphics, Discord posts). Keeping them separate keeps the math clean and stops me from cross-contaminating ROI when I report results.

## Hard rules
1. **CLV is truth.** Every logged pick should have entry odds, closing odds, and CLV calculated. Long-term edge = CLV. Short-term W/L is variance.
2. **Line-shop before logging.** The odds in the tracker are the best odds I could get across my books, not the first book I checked.
3. **Separate KairosEdge.** Halftime trades go in the Kairos P&L tracker, NOT here. Do not mix.
4. **Units are 1u baseline.** Sizing notes (1.5u, 2u, etc.) live in the row's notes column.
5. **Tracker is read-mostly.** When making changes, prefer adding columns/rows over restructuring sheets — formulas downstream will break.

## When working on this project
- If I want to "log a pick," ask which file (cards vs game lines) and confirm the columns before writing.
- If I want a results recap, pull from these two files first; don't recompute from memory.
- If I want a CLV report, that's the `clv-dashboard` skill — point to these files as the data source.
- Any new column or formula change → tell me what downstream graphics/skills depend on it before committing.

## Open to-dos / known gaps
- (none documented yet — populate as we work)

---
*Last updated: 2026-04-07*
