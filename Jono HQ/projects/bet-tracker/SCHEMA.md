# Bet Tracker — Schema

Documents the column structure of both tracker spreadsheets so Claude doesn't have to re-inspect them on every session.

**Last verified:** 2026-04-07

---

## ⚠️ Critical gap

**Neither tracker has a CLV column or a closing-odds column.** The Sports Betting Core prompt (`prompts/05_Sports_Betting_Core.md`) hard rule #1 is "CLV is the truth" — but the data needed to measure CLV is not being captured. Without entry book + closing odds, the `clv-dashboard` skill has nothing to compute against. **This is the single highest-leverage fix in the tracker.**

Recommended new columns (both files, on the main log sheets):
- `Book` — which sportsbook the bet was placed at
- `Closing Odds` — the line at game time (or at suspension)
- `CLV` — calculated as American-odds delta or no-vig win-prob delta

Add these in the existing rightmost position (column H+) so historical formulas keep working.

---

## File 1: `picksbyjonny_CardPicks_Updated.xlsx`

Props and curated daily card. Title: "Model Picks Only · Jan 1 – Mar 30, 2026". Currently 387 rows in the main log.

### Sheet: `Pick Log` (387 rows × 7 cols) — primary log
Header row is row 4 (rows 1–3 are titles/blank).

| Col | Header | Type | Notes |
|---|---|---|---|
| A | Date | date | |
| B | Pick | text | Player + line + over/under |
| C | Sport | text | NBA, NCAAB, NFL, NHL, etc. |
| D | Odds | int (American) | |
| E | Units | float | 1u baseline, sizing notes elsewhere |
| F | Result | text | W / L / P (push) |
| G | P&L | float | units gained/lost |

### Sheet: `Daily Summary` (80 rows × 7 cols)
Row 3 headers: `Date | Picks | W | L | P&L | Cumulative | Win Rate`

### Sheet: `By Category` (10 rows × 7 cols)
Row 3 headers: `Category | Picks | W | L | P&L | Win Rate | ROI`
Categories observed: Assists, etc. (stat categories).

### Sheet: `By Sport` (7 rows × 7 cols)
Row 3 headers: `Sport | Picks | W | L | P&L | Win Rate | ROI`
First row of data: NBA — 275 picks, 150-125, +5.03u, 54.5%, 1.4% ROI.

### Sheet: `By Direction` (19 rows × 7 cols)
Overs vs Unders breakdown. Row 3 headers: `Direction | Picks | W | L | P&L | Win Rate | ROI`

### Sheet: `Monthly` (8 rows × 8 cols)
Row 3 headers: `Month | Picks | W | L | P&L | Win Rate | ROI | Avg Units/Pick`
January: 125 picks, 73-52, +18.76u, 58.4%, 9.3% ROI.

### Sheet: `By Odds Range` (9 rows × 7 cols)
Row 3 headers: `Odds Range | Picks | W | L | P&L | Win Rate | ROI`
First range: Plus Money (+100 & up) — 66 picks, 35-31, +11.25u.

### Sheet: `Streaks & Rolling` (12 rows × 6 cols)
Row 3 headers: `Metric | Value`
First metric: Current Streak (last verified: 2L).

### Sheet: `Player Leaderboard` (28 rows × 6 cols)
Row 3 headers: `Player | Bets | W | L | P&L | Win Rate`
Top: R. Sheppard — 6 bets, 4-2, +3.23u.

### Sheet: `Key Metrics` (27 rows × 2 cols)
Row 4 headers: `Metric | Value`. One-page summary stats.

---

## File 2: `picksbyjonny_GameLines.xlsx`

Game lines and parlays. Title: "Straight MLs, Spreads, Totals · Jan 1 – Mar 30, 2026".

### Sheet: `Game Lines` (84 rows × 7 cols) — primary log
Row 4 headers: `Date | Pick | Sport | Odds | Units | Result | P&L`. Same structure as Card Picks Pick Log.

### Sheet: `GL Parlays` (37 rows × 7 cols)
Row 4 headers: same. Spread/ML parlays + ladder challenges.

### Sheet: `Long Shots` (55 rows × 7 cols)
Row 4 headers: same. Prop parlays, NFL parlays, PrizePicks slips.

### Sheet: `By Category` (8 rows × 7 cols)
Row 4 headers: `Category | Picks | W | L | P&L | Win Rate | ROI`
Splits Game Lines vs GL Parlays vs Long Shots.

### Sheet: `By Sport` (9 rows × 7 cols)
Same shape. Categories: NBA, NCAAB, NFL, MIX.

### Sheet: `By Bet Type` (18 rows × 7 cols)
MLs, Spreads, Totals, Parlays, etc.

### Sheet: `Monthly` (9 rows × 7 cols)
Jan / Feb / Mar split.

### Sheet: `By Odds Range` (10 rows × 7 cols)
Plus money through heavy juice.

### Sheet: `Daily Summary` (66 rows × 7 cols)
Row 3 headers: `Date | Picks | W | L | P&L | Cumulative | Win Rate`

### Sheet: `Streaks & Rolling` (12 rows × 6 cols)
First metric: Current Streak (last verified: 4W).

### Sheet: `Key Metrics` (21 rows × 2 cols)
Title: "Non-Model Key Metrics".

---

## Editing rules (from prompt 07)

1. **Tracker is read-mostly.** Prefer adding columns/rows over restructuring sheets.
2. **Any new column** → check downstream graphics/skills before committing.
3. **Header row is row 4** (Pick Log) or row 3 (Daily Summary) — don't assume row 1.
4. **Card Picks = "Model Picks Only".** Game Lines = "Non-Model".  These two trackers are intentionally separated by methodology.

## Downstream consumers

Skills and projects that read these files:
- `clv-dashboard` (would consume CLV column once it exists)
- `performance-report-generator` (daily/weekly recaps)
- `results-graphic-script` (text content for IG performance cards)
- `variance-edge-separator` (cold-stretch detection)
- `bet-slip-builder` (re-formatting historical picks)
- `projects/sports-betting/state.md` (sizing mode + CLV trend) — currently stubbed because data isn't captured

## Card Picks vs Game Lines — why two files
- **Card Picks** = "Model Picks Only" — props sourced from the v7-style projection process, sold as the daily curated card to Discord
- **Game Lines** = "Non-Model" — straight MLs, spreads, totals, plus parlays and long shots

Different methodologies → different ROI profiles → keeping them separate stops cross-contamination. Confirmed by the title row of each Key Metrics sheet.
