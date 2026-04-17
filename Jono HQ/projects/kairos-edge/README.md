# KairosEdge — Halftime Trading

Working folder for the KairosEdge halftime trading system. Project prompt: `Jono HQ/prompts/04_KairosEdge.md`.

**Core mechanic:** buying the trailing team in full-game winner markets at halftime when the live price implies a worse win prob than the historical base rate.

## Structure
- `trade-journal.md` — running log of every Kairos trade (use the `kairos-trade-journal` skill)
- `pl-tracker.xlsx` — running P&L by sport / deficit bucket / discount tier (use the `kairos-pl-tracker` skill)
- `base-rates.md` — comeback base rates per sport, refreshed as the data grows (sourced from `comeback-probability-model` skill)
- `state.md` — current YTD record, biggest edges, restricted-book notes

## Hard rule
KairosEdge P&L is tracked **separately** from picksbyjonny prop/line betting. Never mix the two.

## Where to log new trades
Open `trade-journal.md`, add a row using the kairos-trade-journal skill format. Update `pl-tracker.xlsx` once the game ends.
