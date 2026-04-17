# Sports Betting Core

Working folder for the picks/props/game-lines side of picksbyjonny. Project prompt: `Jono HQ/prompts/05_Sports_Betting_Core.md`.

This is **separate** from KairosEdge accounting and **separate** from DFS. The bet tracker spreadsheets in `projects/bet-tracker/` are the source of truth for logged picks — this folder holds operational state, sizing mode, CLV trend, line-shop logs.

## Structure
- `state.md` — current sizing mode, CLV trend, cold-stretch flag, account health snapshot
- `line-shop-log.md` — daily snapshots of where each bet was placed and why
- `daily/` — TODAY.md style daily startup notes (one file per day, archived weekly)

## Related folders
- `projects/bet-tracker/` — the actual logged picks (CardPicks + GameLines xlsx)
- `projects/kairos-edge/` — halftime trades, separate P&L
- `projects/ml-projection-system/` — v7 model that feeds game-line picks here
