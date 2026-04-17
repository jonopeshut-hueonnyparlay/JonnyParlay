# 2026-04-07 — NBA + MLB Postmortem

## Slate summary

**MLB** — 26 entries, $11 in fees
- Quarter Jukebox (20): avg 94.06 | high 127.85
- Strike Three $1 (5): avg 97.95 | high 128.65
- Daily Dollar SE: 108.65

**NBA** — 43 entries, $33 in fees
- Quarter Jukebox (20): avg 283.47 | high 328.25
- And-One (20): avg 279.99 | high 338.50
- High Five SE: 301.75
- Elbow Shot SE: 274.00
- Daily Dollar SE: 270.25

## What went right

Pool discipline was essentially perfect.

| Sport | Slots in-pool | Avg pts in-pool | Avg pts off-pool |
|---|---|---|---|
| MLB | 257/260 (98.8%) | 9.59 | 5.00 |
| NBA | 343/344 (99.7%) | 35.28 | 12.75 |

System picks the right players. Off-pool plays were rare and bad.

## What went wrong — the one real leak

**NBA high-conviction plays were massively under-rostered vs. their ExposureRec.**
The SS upload file only carried `MaxExposure`, so SaberSim had a ceiling with no floor. It was free to roster the system's core plays at near-zero.

| Player | Rec | Actual | Scored |
|---|---|---|---|
| John Konchar | 30% | **0%** | **50.5** |
| Julian Reese | 38% | 9% | 46.2 |
| Jaylen Brown | 50% | 19% | 53.7 |
| Jayson Tatum | 42% | 14% | 37.7 |
| Cody Williams | 38% | 5% | 30.0 |

Every one of those players outscored their ceiling projection. Not variance — systematic under-exposure of the exact guys the system was pounding.

MLB was cleaner (small gap on Donovan, Rumfield, Alvarez), no overweights, and off-pool was only 3 slots total.

## Fix applied

Built `apply_min_exposures.py` (in `Downloads/`). It reads the Pool CSV, translates `ExposureRec` into a `MinExposure` floor, and writes a patched `*_WITHMIN.csv` next to the original SS upload file.

**Tier logic**
- ExposureRec ≥ 40 → MinExp = max(rec − 5, 25)
- ExposureRec ≥ 25 → MinExp = max(rec − 10, 15)
- < 25 → no floor
- Always clamped to MaxExposure − 1

**Safety rails**
- MLB: only pitchers get floors. Hitters skipped to avoid the player-level/stack-level deadlock noted in `mlb-dfs/POINTER.md`.
- NBA: all positions.
- Never overwrites originals.

## Usage going forward

**NBA:** run the script after every pool build, upload `*_WITHMIN.csv` instead of the original.
```
python apply_min_exposures.py --date YYYY-MM-DD
```

**MLB:** skip the script. Only 3 pitcher floors per slate — hand-enter them in SaberSim:
- `Garrett Crochet 24%`, `Tarik Skubal 22%`, etc. (pull from the Pool file)
- Keeps the stack-level rules clean.

## What NOT to change

- Pool discipline is already at 99%+. Don't loosen it.
- Don't add new contrarian off-pool plays — yesterday's off-pool slots averaged 5 (MLB) and 12.75 (NBA).
- Don't layer manual rules in the SS UI. Settings doc says: "Rules: 0 — build first, rule-fix second."

## Open question for next review

Is the under-exposure pattern repeatable? One slate isn't enough. Re-run this comparison after 5–10 more slates. If it holds, the fix is load-bearing. If NBA 4/8 exposures already match rec because the MinExp floor is enforced, we'll know the script is doing its job.
