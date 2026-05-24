# Sharp Money Signals Research
*Completed: 2026-05-23*

## Verdict Summary

| Signal | Build? | Why |
|--------|--------|-----|
| Multi-book sharp line comparison | **YES — Tier 1** | Free (existing Odds API), works for props, real signal |
| Opening-vs-current line movement | **YES — Tier 2** | Free (Odds API historical endpoint), works for props |
| DK public sentiment fade | **Skip** | Game lines only, not props; very weak signal |
| Steam moves | **No** | Latency incompatible with batch pipeline; props data n/a |
| Reverse line movement (RLM) | **No** | Empirically weak (one study: 46.3% win rate); props data n/a |
| Bet % / Money % subscriptions | **No** | Props coverage gap; no machine-readable API at any price |
| Pinnacle API direct | **Closed** | API closed July 23 2025; SharpAPI proxy costs $399/mo |
| Unabated / OddsJam API | **Closed** | $500–$3,000/mo enterprise pricing |

---

## Key Finding: Props vs. Game Lines Gap

The most-discussed sharp signals in the literature (steam, RLM, bet %) apply almost
entirely to **game lines** — spreads, ML, totals. Player props have almost no bet
percentage or handle data publicly available, at any price. This is structurally
important: our engine is ~85% props-focused. The entire paid-subscription market
for sharp money data is largely irrelevant for us.

The good news: **props markets are less efficient** precisely because there's less
sharp money infrastructure focused on them. A projection-model-first approach has
a larger structural edge in props than in game lines.

---

## Signal 1: Multi-Book Sharp Line Comparison (Build — Tier 1)

**Concept:** The consensus line across the sharpest available books is the market's
best estimate of true probability. When our pick engine is getting a meaningfully
better number than that consensus, we're getting +EV vs. the sharp market.

**Why it works:** Soft books (DK, FanDuel) lag sharp books (bet365, Caesars, Circa)
by 5–20 minutes on game lines and longer on props. That gap is exploitable.
Multi-book line delta is the cleanest operationalization of this.

**Implementation:**
- Already pulling multi-book odds via The Odds API
- At pick time, identify the sharpest available book's line for each prop
- Compute: `sharp_line_delta = our_line - sharp_consensus_line`
- Positive delta (we're getting a better number) → additive +N to pick_score
- Use bet365 / Caesars as sharp proxy for NBA props (DK and FD are the soft books)
- Store `sharp_line_delta` per pick for later CLV-style analysis

**Expected lift:** 1–3 pick_score points additive. Real signal — getting a better
number than the sharp consensus is definitionally +EV.

**Cost:** $0 (existing Odds API subscription).

**Note on Pinnacle:** Pinnacle API closed July 23 2025. Not in The Odds API standard
offering. Use bet365/Caesars as sharp proxy instead.

---

## Signal 2: Opening-vs-Current Line Movement Direction (Build — Tier 2)

**Concept:** If a prop line has moved in the direction of our pick since game open,
that's weak confirmation (market moved our way). If it moved against our pick,
that's a caution flag (sharps may have pushed it away from our position).

**Implementation:**
- The Odds API historical endpoint has snapshots at 5–10 min intervals since Sep 2022
- Query earliest available snapshot for each game as "opening line"
- Compare to current line at pick time
- Classify: toward_our_pick / away_from_our_pick / flat
- Away-from-pick (≥0.5 unit movement): −3 to −5 pick_score
- Toward-pick (≥0.5 unit movement): +1 to +2 pick_score (asymmetric — flag the negative harder)

**Cost:** Historical API queries consume credits. Monitor usage — at 10–20 props/day
this should be manageable.

**Caveat:** "Opening line" is approximated as earliest snapshot (may be hours after
true market open for NBA, day-of for MLB). Not tick-by-tick precision.

---

## Signals Not Worth Building

### Steam Moves
Steam moves (simultaneous coordinated sharp wagers across books) are exploitable
only within minutes of trigger. Our batch-job pick engine + human-in-the-loop
Discord posting model introduces too much latency. The line has already moved
before we could act on it. Monitoring services cost $60–$300/mo and don't cover
props anyway.

### Reverse Line Movement (RLM)
Only published academic study (2008 MLB): 518-600 record, 46.3% win rate — negative
ROI. Easily confounded with book-driven line balancing. Theoretically sound but
empirically weak. Props coverage: zero.

### Action Network PRO / SportsInsights
$60–$300/month. Consumer UIs, no API. Even if we scraped them, the data is game
lines only. Not automatable into the pipeline at a reasonable cost.

---

## CLV (Already Built — Keep As-Is)

CLV (capture_clv.py) is empirically the strongest signal in sports betting.
Buchdahl's 20k-bet study: 3.4% actual profit vs. 4.0% CLV-predicted EV (within noise).
Reaches statistical significance ~50x faster than win/loss records.

However: CLV is **post-close only** — it cannot improve a single real-time pick.
It validates the model retrospectively. H3 gate (300 over_p_raw rows) will enable
CLV-informed Platt recalibration. Continue accumulating. No action needed now.

---

## Implementation Priority

1. **Sharp line comparison** — add to existing multi-book odds pull in run_picks.py.
   Identify sharp proxy books, compute delta, add to pick_score. Low effort.

2. **Opening line movement** — requires historical API call per game. Medium effort.
   Cache the opening snapshot to avoid repeated credit usage.

3. Both signals are additive modifiers to pick_score, not gates. They should never
   override the projection-based foundation — only confirm or flag.

---

## Data Source Reference

| Source | Cost | Props? | API? | Notes |
|--------|------|--------|------|-------|
| The Odds API (existing) | $0 extra | Yes | Yes | Multi-book lines + history |
| Action Network PRO | $60/mo | No | No | Consumer UI only |
| SportsInsights | $99–$299/mo | No | No | Consumer UI only |
| OddsJam consumer | $199/mo | Partially | No | Scraping only |
| SharpAPI (Pinnacle proxy) | $399/mo | Partially | Yes | Overkill for our volume |
| Unabated API | $3,000/mo | Yes | Yes | Enterprise only |
| DK Public Splits | $0 | No | No (scrape) | Square book only, game lines |
