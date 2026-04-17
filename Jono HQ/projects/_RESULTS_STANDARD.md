# Results / Postmortem Standard

One convention for every project that produces dated outcomes (NBA DFS, MLB DFS, Golf DFS, KairosEdge, picksbyjonny picks). Removes the "if I've created it" ambiguity from the project prompts.

## Where results go

```
projects/<project-name>/results/YYYY-MM-DD/
    slate.md          ← what was bet, what the inputs were, what the model said
    outcome.md        ← what actually happened, units +/-, player-by-player notes
    postmortem.md     ← (optional) only if there's a learning worth saving
```

## Naming
- Folder name is the **slate date** in `YYYY-MM-DD` format, NOT the date the postmortem was written
- One folder per slate, even if you didn't bet (write `outcome.md` saying "no bets, slate skipped because X")

## Project mapping

| Project | Path | What goes in `slate.md` |
|---|---|---|
| NBA DFS | `projects/nba-dfs/results/{DATE}/` | Pool size, exposure recs, SE core lock, contest entries |
| MLB DFS | `projects/mlb-dfs/results/{DATE}/` | Stack cores, SP picks, weather notes, contest entries |
| Golf DFS | `projects/golf-dfs/results/{TOURNAMENT-START-DATE}/` | VTO scores, exclusions, pool size per contest |
| KairosEdge | `projects/kairos-edge/results/{DATE}/` | Trades attempted, deficit/time/base-rate at entry, book used |
| picksbyjonny | (use bet tracker xlsx, not this folder system) | n/a — picks live in CardPicks/GameLines |

## Template — `slate.md`
```markdown
# {SPORT} Slate — {DATE}

## Inputs
- Source files: ...
- Confirmed lineups checked at: ...
- Weather (MLB/golf): ...

## Strategy
- Modes entered: SE / 3MAX / 20MAX / 150MAX
- Stack mode (NBA): legacy / leverage / off
- Core locks: ...
- Notable exposure decisions: ...

## Contest entries
- {Contest name}: {entries} @ ${buy-in}
```

## Template — `outcome.md`
```markdown
# {SPORT} Outcome — {DATE}

## Headline
- Cash / no cash
- Units +/-
- Best lineup score / placement

## Player notes
- Hits: ...
- Misses: ...
- Surprises (over projection by 5+): ...

## Pipeline check
- Did the upload settings produce what was expected?
- Was any cap/core/min binding in a way that hurt?
- Is there a fix to flag in the next slate?
```

## Template — `postmortem.md` (optional)
Only write this if there's something to learn. Don't write postmortems for normal variance.

```markdown
# Postmortem — {DATE}

## What happened
## Why it happened
## What changes (if any)
## Should this become a hard rule or memory?
```

## Hard rules
1. **Don't write postmortems for variance.** Use `variance-edge-separator` skill first to confirm the outcome was outside expected.
2. **Slate.md is written BEFORE the games.** Outcome.md is written after.
3. **If a postmortem produces a new rule, save it to auto-memory** (`feedback_*.md`) so it survives across sessions.
