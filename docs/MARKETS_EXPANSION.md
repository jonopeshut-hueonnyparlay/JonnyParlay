# Sports & Markets Expansion Plan

Last updated: 2026-05-13

Strategic inventory of every sport/market we want to offer, what projection source is needed,
and estimated build effort. Ordered by priority (monetization impact × build readiness).

---

## Current Live Markets

| Sport | Status | Props | Game Lines | Projection Source |
|-------|--------|-------|------------|-------------------|
| NBA | **Live** | PTS, REB, AST, 3PM + combos (PRA/PR/PA/RA) | Totals, spreads, ML, team totals, daily lay | SaberSim + custom engine (nba_projector.py) |
| NHL | **Live** | SOG | Totals, spreads, ML, F5, team totals | SaberSim (no custom engine) |
| MLB | Shadow | K, OUTS, HITS, HA, HRR, TB | F5/full totals, spreads, ML, NRFI/YRFI | SaberSim |
| WNBA | **Live** | PTS, REB, AST, 3PM + combos | Totals, spreads, ML | Reuses NBA engine (nba_api basketball_wnba) |

---

## Priority 1 — NFL (Ship by September 2026)

**Why first:** Biggest betting market in the US. Season starts September. Must architect by July or we miss 2026.

### Markets to offer
- Passing yards, passing TDs, interceptions
- Rushing yards, rushing TDs
- Receiving yards, receptions, receiving TDs
- Combo: passing+rushing yards (QB), rec+rush (RB)
- Game lines: spread, totals, ML, F5 alt lines

### Projection sources
| Source | Quality | Access | Cost |
|--------|---------|--------|------|
| **4th Down Model** (rbsdm.com) | A — EPA-based, well-calibrated | Public scrape / CSV | Free |
| **NumberFire** | B+ — widely used, DFS-focused | Scrape | Free |
| **PFF (Premium)** | A+ — best player-level projections | API/download | ~$70/mo |
| **FantasyPros consensus** | B — aggregated, lags sharp sources | Scrape | Free |
| **SaberSim NFL** (if available) | B+ — already integrated format | SaberSim account | Included |

**Recommendation:** Start with SaberSim NFL (same CSV format = minimal new code). Add 4th Down Model as validation layer. PFF if monetization revenue justifies it.

### Build scope
- New `parse_csv` branch for NFL format
- NFL `SIGMA` entries for passing/rushing/receiving yards (Normal, higher variance)
- `TIERS` config for NFL stats — yards likely T2, TDs likely T3 (binary)
- `GAME_SIGMA["NFL"]` — larger spread sigma than NBA
- No custom projection engine needed initially (use SaberSim)
- Odds API key: `americanfootball_nfl` — already in CO_LEGAL_BOOKS scope

**Estimated effort:** Large (2-3 sessions). This is backlog item #27.
**Hard deadline:** Architecture design by 2026-07-01, first live run by 2026-09-01.

---

## Priority 2 — Golf (isolated build, any time)

**Why second:** DataGolf API has best-in-class projections. Clean, isolated code path. Major tournaments drive significant betting volume. No season dependency — runs all year.

### Markets to offer
- Win (outrights)
- Top 5 / Top 10 / Top 20 / Top 40 finish
- Head-to-head matchups
- Make/miss cut

### Projection sources
| Source | Quality | Access | Cost |
|--------|---------|--------|------|
| **DataGolf** | A+ — Strokes Gained based, tournament-specific | REST API | ~$30/mo |
| **Datagolf free tier** | B — limited fields | Public | Free |

**Recommendation:** DataGolf paid tier. API returns field projections + course fit adjustments.

### Build scope
- New `evaluate_golf` function (completely isolated from existing paths)
- DataGolf API fetcher (new file `engine/golf_fetcher.py`)
- Win/top-N probability models: DataGolf publishes finish probabilities directly — may not need custom calc
- Odds API key: `golf_masters_tournament_winner` and similar tournament keys
- Card format: separate embed type (different from prop/game line layout)

**Estimated effort:** Medium (1-2 sessions). This is backlog item #9.
**Risk:** Low — completely isolated. No existing code touched.

---

## Priority 3 — College Basketball (November–March)

**Why:** KenPom/BartTorvik are the most accurate game-level projections in any sport. Strong overlap with NBA bettors in the Discord audience.

### Markets to offer
- Game totals (over/under)
- Spreads (ATS)
- Moneylines
- *No player props* — no reliable public player-level projection source for college

### Projection sources
| Source | Quality | Access | Cost |
|--------|---------|--------|------|
| **KenPom** | A+ — tempo/efficiency model, best NCAAB | Scrape or API | ~$20/yr |
| **BartTorvik** | A+ — similar to KenPom, cross-validates well | Scrape | Free |
| **Haslametrics** | A | Scrape | Free |

**Recommendation:** KenPom primary, BartTorvik cross-validation. Both project game pace and efficiency → can build team-total projections.

### Build scope
- KenPom/BartTorvik game projection fetcher
- College basketball uses same Odds API sport key: `basketball_ncaab`
- Reuse existing game-line eval pipeline (totals/spreads) — minimal new code
- Add `"NCAAB"` to `SPORT_KEYS` and `GAME_SIGMA["NCAAB"]`
- No prop pipeline needed initially

**Estimated effort:** Small-medium (1 session). Mostly config + a new projection fetcher.
**Season:** November 2026 – April 2027 (March Madness = highest volume).

---

## Priority 4 — NHL Props Expansion

**Why:** Already live with SOG. Adding saves, assists, PPP, and goals would increase NHL card volume significantly during playoffs.

### Additional markets
- Goalie saves (count stat, similar to SOG)
- Assists (count stat — same distribution as NBA AST)
- Goals (binary/count hybrid — rare per game, Poisson at low λ)
- Power play points (PPP) — dependent on PP time, hard to model

### Projection sources
| Source | Quality | Notes |
|--------|---------|-------|
| **SaberSim NHL** | B+ | Need to verify which columns are available for saves/assists/goals |

**Recommendation:** Verify SaberSim NHL CSV column availability first (this is the blocker for backlog #25). If columns exist, the eval pipeline change is small.

**Estimated effort:** Small (0.5 session) if SaberSim columns confirmed. This is backlog item #25.

---

## Priority 5 — Soccer (Research required)

**Why:** High global interest. Goals/assists/SOT markets exist on Odds API.

### Markets to offer
- Goals (binary — 0-1 per player per game, very low λ)
- Assists (rare, high variance)
- Shots on target (SOT) — most analogous to SOG

### Projection sources
| Source | Quality | Access | Cost |
|--------|---------|--------|------|
| **FBref/StatsBomb** | A — event-level data, needs modeling | Scrape | Free |
| **Opta** | A+ | Licensed data only | Expensive |
| **Understat** | B | xG/xA per player, public | Free |
| **FiveThirtyEight/ESPN** | B | Game-level only | Free |

**Status:** No reliable public player-level projection source comparable to SaberSim. Would need to build a custom projection layer using xG/xA + minutes data. High effort.

**Decision:** Research session needed. Likely **defer until custom projection engine is proven and stable**. The build complexity is high and the expected ROI is lower than NFL/Golf/NCAAB.

---

## Priority 6 — MMA / UFC

**Why:** High interest from Discord audience. Underdog + parlay culture fits our brand.

### Markets to offer
- Fight winner (ML)
- Method of victory: KO/TKO, decision, submission
- Round betting (which round fight ends)
- Over/under rounds

### Projection sources
| Source | Quality | Notes |
|--------|---------|-------|
| **MMA Decisions** | B | Historical stats, no forward projections |
| **Tapology** | B | Aggregated community predictions |
| **FightMetric** | A | Official UFC stats, historical only |
| **BestFightOdds** | B+ | Line movement data |

**Status:** No systematic player-level projection source. Method-of-victory models require fight-specific modeling (style matchups, reach, cardio, judge tendencies). High complexity, no clear projection input equivalent to SaberSim.

**Decision:** **Pass for now.** The ML fight-winner market has low edge potential (razor-thin lines on favorites). Matchup modeling is a full research project. Revisit post-NFL launch.

---

## Monetization-Aligned Roadmap

| Timeline | Work | Deliverable |
|----------|------|-------------|
| **Now** | MLB go-live (Jono's call, #26) | More content volume immediately |
| **Now** | WNBA live (already shadow, Jono's call) | Active season, low risk |
| **May–Jun** | Golf build (#9) | New sport for summer content |
| **Jul** | NFL architecture (#27) | Ready for September kickoff |
| **Sep** | NFL live | Biggest betting season of year |
| **Nov** | NCAAB game lines | March Madness prep |
| **TBD** | NHL props expansion (#25) | Adds depth to existing NHL |
| **Post-NFL** | Soccer research | Decide yes/no with full info |
| **Never?** | MMA | Pass unless projection source appears |

---

## Key Decisions Needed from Jono

1. **MLB go-live**: Shadow has been running. When is data clean enough? (Backlog #26)
2. **WNBA live**: Season is active. Want to flip it live? (Backlog #8 already shipped)
3. **DataGolf subscription**: ~$30/mo. Worth it for golf content? (Backlog #9)
4. **PFF subscription**: ~$70/mo. Worth it for NFL quality edge? (Can start free with SaberSim NFL)
5. **KenPom subscription**: ~$20/yr. Near-free for NCAAB game lines.
