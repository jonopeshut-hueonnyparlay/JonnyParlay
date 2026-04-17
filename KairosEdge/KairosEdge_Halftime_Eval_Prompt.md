# KairosEdge Halftime Evaluation — Output Format

When I send you halftime screenshots from ESX, always produce the following output in this exact order. No exceptions.

---

## What I Will Send You:

1. **Both ESX indicator screenshots** (Home tab + Away tab with all 5 indicators visible)
2. **Score screenshot** (with time/quarter confirmation)
3. **Contract prices** (both team YES prices)
4. **Pregame spread** (e.g., "CHA -13.5")

---

## What You Output — Every Time:

### Section 1: Score + Spread Header

```
## [AWAY] [score], [HOME] [score] | [FAV] -[spread]
```

### Section 2: Indicator Readout

```
**Indicators ([Team A] tab / [Team B] tab):**
- HRS: [Team A] **[+/-X.X]** / [Team B] **[+/-X.X]** → [plain English: who's hot/cold]
- PA: **[X.X]** ([which team's structural edge])
- ES: **[X.X]** / **[X.X]** | CC: **[X.X]** / **[X.X]** | 3PA Rate: **[X.X]** / **[X.X]**
```

### Section 3: Market Edge Calculation

Show the full corrected Brownian formula with actual numbers:

```
deficit = [X] | spread = [+/-X.X] ([trailing team] is the dog/fav) | τ = 0.5 | σ = 12.5
z = (-[deficit] + ([spread] × 0.5)) / (12.5 × √0.5)
z = [numerator] / 8.84 = [z-score]
Fair Value = normalCDF([z]) ≈ [X]¢
```

**Important formula notes:**
- `deficit` = points the trailing team is down (always positive)
- `spread` = from the trailing team's perspective (negative if they're the dog, positive if they're the favorite)
- `τ = 0.5` at halftime (remaining seconds / 2880)
- `σ = 12.5` (NBA scoring standard deviation)
- Use `√0.5 = 0.707`, so denominator = `12.5 × 0.707 = 8.84`

### Section 4: Fair Value vs Market vs Edge

```
**[Trailing team] fair value: ~[X]¢ | Market: [X]¢ | Edge: [+/-X]pp**
```

### Section 5: BUY or PASS Verdict

**BUY criteria (ALL must be met):**
- Edge ≥ 8pp (fair value minus market price, after accounting for FLB)
- Entry price in 30–45¢ sweet spot
- HRS shows leading team shooting above baseline (regression signal present)
- PA near neutral or favoring trailing team (structural competitiveness)
- Not trailing by 19+ (hard filter auto-reject)

**If PASS:** Explain specifically which criteria failed and why. Reference the indicators directly. Explain the story the indicators are telling — is this an anti-regression setup? Is the price already too generous? Is the structural picture too lopsided?

**If BUY:** Include entry price recommendation (maker limit), sizing (half-Kelly), take profit target, stop loss, and forced exit at 4:00 remaining Q4.

### Section 6: Q3/Q4 Game Flow Prediction

```
**Q3 (first 6 minutes):** [What happens when shooting regresses — who benefits, how does the deficit change]

**Q3 (back half):** [How PA and structural factors interact with normalized shooting — where does the lead settle]

**Q4:** [How the game closes out — final margin prediction]

**Contract path:** [Trailing team contract price trajectory through Q3 and Q4 — where it spikes, where it bleeds, where it dies]
```

### Section 7: Updated Summary Table

Running table of ALL games evaluated that night:

```
## UPDATED SUMMARY: [X]/[Y] — [X] BUY, [Y-X] PASS

| Game | Trailing Team | Fair Value | Market | Edge | Verdict |
|------|--------------|-----------|--------|------|---------|
| [AWAY/HOME] | [team] | [X]¢ | [X]¢ | [+/-X]pp | [BUY/PASS — reason] |
```

### Section 8: Full Predictions List

Running list of winner predictions + margin for ALL games that night:

```
1. **[AWAY/HOME] → [Winner]** by [X-Y]
2. **[AWAY/HOME] → [Winner]** by [X-Y]
...
```

---

## Additional Rules:

- **Always check the other side.** If the trailing team is overpriced, briefly note whether the leading team has edge (fair value = 100 - trailing team fair value). Only call it out if the leading team's edge ≥ 8pp AND the setup makes sense (e.g., cold-shooting favorite with structural dominance).
- **Anti-regression setups:** When the LEADING team is shooting cold and has structural dominance (positive PA), flag this explicitly — regression helps them, not the trailing team. These are the most dangerous traps.
- **Hard filters:** Auto-reject trailing by 19+. Flag paint differential ≥ 12 or turnovers ≥ 7 as structural mismatches.
- **Price sweet spot:** KairosEdge operates at 30–45¢. Contracts outside this range have worse risk/reward characteristics even if edge exists.
- **Be direct.** No hedging, no "it depends." Give the BUY or PASS and own it.
