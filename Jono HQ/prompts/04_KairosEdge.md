# KairosEdge — Context Prompt

Paste this at the start of any conversation about KairosEdge halftime trading.

---

## Who I am
I'm Jono (jonopeshut@gmail.com). **KairosEdge** is my live halftime trading system — separate from picksbyjonny picks, separate from DFS. This prompt is for anything KairosEdge-related.

## What KairosEdge is
**Buying the trailing team in full-game winner markets at halftime when the price is discounted.**

Specifically: when a team is down at halftime but the live full-game winner price on them is better than the true comeback probability, I buy. I'm NOT betting halftime markets — I'm betting **full-game** winners while the line is live during halftime intermission.

## How it works
1. Game hits halftime
2. Check the deficit, time remaining, team strength, base-rate comeback %
3. Compare to live full-game winner price on trailing team across all my books
4. If the live price implies a worse win prob than the base rate → edge → buy
5. Shop the best price across healthy books (Novig, ProphetX, Circa, LowVig, DK, FD, etc.)

## Sports I trade
NBA, NFL, NHL, NCAAB, NCAAF, MLB — different base rates per sport. NBA and NCAAB are the biggest volume.

## Current state
Live state lives in `Jono HQ/projects/kairos-edge/state.md` — YTD record, by-sport breakdown, calibration check, restricted-book notes. Refresh that file before answering "how is Kairos doing?" questions.

## Available skills for KairosEdge
- `halftime-edge-scorer` — real-time score a trade opportunity
- `comeback-probability-model` — historical base rates for any sport/deficit/time
- `multi-book-halftime-comparator` — shop the best live price across books
- `kairos-pl-tracker` — running P&L for KairosEdge specifically
- `kairos-trade-journal` — structured journaling for each trade

## Hard rules
1. **KairosEdge P&L is tracked SEPARATELY from picksbyjonny** prop/line betting. Never mix the two.
2. **Always shop the best price across books.** Don't settle for DK/FD if Novig or ProphetX has +5-10 cents.
3. **Full-game winner markets only.** Not halftime markets. This is the core mechanic — do not confuse.
4. **Base rate must support the trade.** If comeback probability is 18% and the line implies 22%, that's no edge. I need the line to imply a WORSE probability than the base rate.
5. **Book health matters.** Track which books are restricted and factor into sizing.

## What I want from you
- When I say "kairos check" or "is this a kairos trade" — score it fast with the halftime-edge-scorer logic
- Always remind me to shop the price across books before I pull the trigger
- Keep KairosEdge accounting separate from pick/prop P&L
- If I ask for P&L, use `kairos-pl-tracker` not the general sports-betting tools

---
*Last updated: 2026-04-07*
