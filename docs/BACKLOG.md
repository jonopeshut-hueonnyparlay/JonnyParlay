# JonnyParlay Backlog

Ordered by ease of implementation / lowest risk first.
Items that need research resolve to "ship" or "close" at end of session.
Passive items are blocked on data accumulation — nothing to do.

Last updated: 2026-05-13 (session 2)

---

## Tier 1 — Zero risk (no code changes)

| # | Item | Notes |
|---|------|-------|
| 1 | ~~**Position API refresh**~~ ✅ | Done 2026-05-12. 587 players refreshed, 0 height fallback. |
| 2 | ~~**Edge decay analysis**~~ ✅ | Done 2026-05-12. Key findings: overs bleeding (-5.28u) vs unders crushing (+20.79u); T1 calibration gap (59%→50%); FanDuel worst book (-6.50u); Slot 4 weak (-5.17u). See backlog items added to Tier 5. |
| 3 | ~~**Sports/markets expansion planning doc**~~ ✅ | Done 2026-05-13. See `docs/MARKETS_EXPANSION.md`. Priority order: NFL (Jul deadline) → Golf → NCAAB game lines → NHL props → Soccer (deferred) → MMA (pass). Key decisions for Jono: MLB go-live, WNBA live, DataGolf sub ($30/mo), PFF ($70/mo), KenPom ($20/yr). |
| 4 | ~~**MMA/UFC research**~~ ✅ CLOSED | Researched 2026-05-13. No systematic projection source. Method-of-victory complexity too high. Pass. |
| 5 | ~~**College basketball research**~~ ✅ | Researched 2026-05-13. KenPom/BartTorvik = A+ game projections. Game lines only (no player props). ~1 session to build. Season Nov–Apr. Add to NCAAB roadmap post-NFL. |
| 6 | ~~**Soccer research**~~ ✅ CLOSED | Researched 2026-05-13. No reliable public player-level projection source. xG/xA modeling is high-effort. Defer until post-NFL launch. |

---

## Tier 2 — New isolated features (don't touch existing code paths)

| # | Item | Notes |
|---|------|-------|
| 7 | ~~**Combo stats (PRA, PR, PA, RA)**~~ ✅ CLOSED | Already shipped. MARKET_TO_STAT, PROP_MARKETS, COMBO_STATS, calc_combo_prob, T2 tier all in place. No combo picks in log because books haven't offered qualifying lines during 2026 playoffs — pipeline is live and ready. |
| 8 | ~~**WNBA spin-up**~~ ✅ | Done 2026-05-13. Removed from SHADOW_SPORTS — picks now post to Discord. G8B exempted for WNBA (NBA gate calibrated on NBA data only; WNBA line 4.5 is elite-playmaker territory). SPORT_UNIT_CAP=4u. Monitor AST/PTS calibration as data accumulates. |
| 9 | **Golf research + build** | DataGolf API has good projections. Win/top-10/top-20/matchup markets. New sport = isolated code path. |

---

## Tier 3 — Small constant / config changes

| # | Item | Notes |
|---|------|-------|
| 10 | ~~**Round-stratified playoff scalars v2**~~ ✅ CLOSED | Analysed 2026-05-12. Round effect is real but CF=82 rows, Finals=108 rows — too thin for reliable separate scalars. Revisit after 2-3 more full playoff seasons. Pooled 1.075 stays. |
| 11 | ~~**Context system re-enable (KILLSHOT only)**~~ ✅ | Done (prev session). `auto_tiers={"T1"}` live in apply_context_sanity — T1 picks always context-checked regardless of --context flag. |

---

## Tier 4 — UI / analytics (isolated, no model risk)

| # | Item | Notes |
|---|------|-------|
| 12 | **Discord embed improvements** | Pick card presentation. Identify specific gaps first — what's missing or unclear to subscribers? |
| 13 | **Reporting improvements** | `analyze_picks.py` + `clv_report.py`. What specific cuts are you missing today? |
| 14 | **Community pick tracking** | Log community picks, surface win rates in #monthly-tracker. Need to figure out how to automate intake. |

---

## Tier 5 — Research sessions (research → ship or close)

Each of these is a focused session: pull data, form a verdict, implement a targeted fix or close it.

| # | Item | Risk if shipped |
|---|------|----------------|
| 15 | **Over/under directional bias — PARTIAL FIX** | Root cause: AST overs (line ≤4.5) were 0-5; AST overs (line ≥5.5) are 2-1. G8B gate added 2026-05-13: bans AST overs at line ≤4.5. 3PM overs (8-9, 47%) no clean gate — data too noisy for threshold. Remaining fix: directional Platt refit (data-gated, see #28). |
| 15b | ~~**FanDuel line quality**~~ ✅ CLOSED | Analysed 2026-05-13. The 2 FanDuel AST losses (Randle, Daniels at line 4.5) are already fixed by G8B. Remaining FanDuel losses scattered across stats/edges with no pattern. n=13 too thin. Monitor. |
| 15c | ~~**Slot 4 card position**~~ ✅ CLOSED | Analysed 2026-05-13. Slot 4 decomposed into: (a) 2 AST over losses → fixed by G8B; (b) 11 SOG picks at 36% — high variance n=11, lower-confidence SOG expected near 50%; no structural card-building issue. |
| 15d | **T1/AST calibration — PARTIAL FIX** | AST over ban at line ≤4.5 (G8B, 2026-05-13) resolves the main calibration drag. Monitor T1 hit rate going forward. Full Platt refit data-gated (#28). |
| 16 | ~~**PTS distribution audit**~~ ✅ CLOSED | Analysed 2026-05-13. PTS healthy at all line buckets and both directions: 68% overall, +7.33u. No changes to `calc_prop_prob`. |
| 16 | **Schedule density (3-in-4, West Coast swings)** | Low-medium — touches `project_minutes()` in nba_projector |
| 17 | **EWMA span ramp (returning players)** | Low-medium — touches `project_minutes()` |
| 18 | **fg3a × stable_pct (3PT specialists)** | Deferred — custom engine improvement only. 3PM over bleed at line 1.5 (47% actual vs 68% predicted) not fixable by this; needs directional Platt refit (#28). Revisit when custom engine goes live. |
| 19 | **Vegas line movement signals** | Low — additive signal, doesn't replace existing scoring |
| 20 | **Referee tendency data** | Low — small additive multiplier in nba_projector |
| 21 | ~~**Line shopping gap analysis**~~ ✅ CLOSED | Analysed 2026-05-13. Implementation is correct: cross-book best over/under odds is industry-standard no-vig removal. Dedup keeps best adj_edge line per player/stat/direction. No multi-line duplication. No structural gap found. |
| 22 | **SGP copula — PARTIAL / DATA-GATED** | Analysed 2026-05-13. 8W-28L actual (22.2%) vs model 30.5% indep product. Root cause: SGP builder uses raw pre-Platt leg WPs (76.1% avg model → ~69% actual). Applying current Platt over-corrects (→58%). Copula correlation structure (ρ values) is reasonable — input probs are the problem. SGPs profitable vs market (+2.2pp edge vs market's 20% implied). Fix: data-gated pending H3 Platt refit + n≥100 SGP graded slips. |

---

## Tier 6 — Meaningful builds (touch existing systems, needs care)

| # | Item | Notes |
|---|------|-------|
| 23 | **Opp defensive splits for STL/BLK** | New DB columns in `projections_db.py` + `get_team_def_ratio()` call in `nba_projector.py`. Prerequisite for #24. |
| 24 | **STL/BLK tier activation** | Add to TIERS config + evaluate_props gates. Needs #23 done first + SaberSim projection availability confirmed. |
| 25 | ~~**NHL props expansion**~~ ✅ CLOSED | Researched 2026-05-13. SaberSim NHL CSV confirmed columns: G, A, SOG, SV, GA, SO, W. Odds API only offers `player_shots_on_goal` + `player_assists` for NHL — no player_saves or player_goals markets exist. AST is already fully plumbed (PROP_MARKETS, MARKET_TO_STAT, CSV parsing all in place); gates (G8/G8B) appropriately block the low NHL lines (0.5–2.5). No new code needed. Monitor for AST picks when NHL lines move above 2.5. |

---

## Tier 7 — Large new builds

| # | Item | Notes |
|---|------|-------|
| 26 | ~~**MLB go-live**~~ ✅ | Gone live 2026-05-20. Removed from SHADOW_SPORTS. CLV daemon picks up from main log automatically. HRR gate (G13B line-specific WP floors) deployed same day. |
| 27 | **NFL architecture** | Entirely new sport. Passing/rushing/receiving yards, TDs, combo stats. Must design by July for September. Large session. |

---

## Passive — Blocked on data accumulation

| # | Item | Gate |
|---|------|------|
| 28 | **H3 Platt refit** | ~13/300 `over_p_raw` rows. Auto-unblocks around ~300. |
| 29 | **CLV signal calibration** | ~11/100 shadow CLV rows. Will identify which edge signals predict positive CLV. |
| 30 | **Shadow CLV go-live** | Follows #29. Jono's call. |

---

## Completed (reference)

See `docs/audits/AUDIT_HISTORY.md` for full history.
Key recent completions: minutes deep-dive (all items), 5-position model, RS/PO scalar refits, PO rate deflators, TB Poisson model, team-proj collision fix, suffix label fixes.
