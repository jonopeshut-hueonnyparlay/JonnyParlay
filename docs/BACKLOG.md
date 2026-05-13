# JonnyParlay Backlog

Ordered by ease of implementation / lowest risk first.
Items that need research resolve to "ship" or "close" at end of session.
Passive items are blocked on data accumulation — nothing to do.

Last updated: 2026-05-13

---

## Tier 1 — Zero risk (no code changes)

| # | Item | Notes |
|---|------|-------|
| 1 | ~~**Position API refresh**~~ ✅ | Done 2026-05-12. 587 players refreshed, 0 height fallback. |
| 2 | ~~**Edge decay analysis**~~ ✅ | Done 2026-05-12. Key findings: overs bleeding (-5.28u) vs unders crushing (+20.79u); T1 calibration gap (59%→50%); FanDuel worst book (-6.50u); Slot 4 weak (-5.17u). See backlog items added to Tier 5. |
| 3 | **Sports/markets expansion planning doc** | Inventory every sport/market we want to offer, what projection source is needed, and estimated timeline. Strategic input for monetization. |
| 4 | **MMA/UFC research** | What projection sources exist? Is method-of-victory complexity worth it? Decide yes/no. |
| 5 | **College basketball research** | KenPom/BartTorvik available. Line markets only (no props). Decide yes/no. |
| 6 | **Soccer research** | FBref/Opta. Goals/assists/SOT markets. Decide yes/no. |

---

## Tier 2 — New isolated features (don't touch existing code paths)

| # | Item | Notes |
|---|------|-------|
| 7 | **Combo stats (PRA, PR, PA, RA)** | New stat type. Mean = sum of individual projections. Joint probability via correlated Normal (reuse copula infra from sgp_builder.py). Zero risk to existing prop paths. |
| 8 | **WNBA spin-up** | Season is live now. Reuses NBA engine + same `nba_api`. Mostly config + minor new plumbing. Low risk. |
| 9 | **Golf research + build** | DataGolf API has good projections. Win/top-10/top-20/matchup markets. New sport = isolated code path. |

---

## Tier 3 — Small constant / config changes

| # | Item | Notes |
|---|------|-------|
| 10 | ~~**Round-stratified playoff scalars v2**~~ ✅ CLOSED | Analysed 2026-05-12. Round effect is real but CF=82 rows, Finals=108 rows — too thin for reliable separate scalars. Revisit after 2-3 more full playoff seasons. Pooled 1.075 stays. |
| 11 | **Context system re-enable (KILLSHOT only)** | System already exists, just disabled. Re-enable for T1 tier only. Adds one Haiku API call per KILLSHOT pick to check for OUT/scratched. |

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
| 15b | **FanDuel line quality** | Low — add FanDuel min_edge premium or deprioritize in line shopping. 13 picks, -41.3% ROI vs +18.3% BetMGM. |
| 15c | **Slot 4 card position** | Low — 4th premium pick -5.17u. Investigate whether card-building is forcing a weak 4th pick. |
| 15d | **T1/AST calibration — PARTIAL FIX** | AST over ban at line ≤4.5 (G8B, 2026-05-13) resolves the main calibration drag. Monitor T1 hit rate going forward. Full Platt refit data-gated (#28). |
| 16 | **PTS distribution audit** | Low — may change `calc_prop_prob` for PTS at low lines only |
| 16 | **Schedule density (3-in-4, West Coast swings)** | Low-medium — touches `project_minutes()` in nba_projector |
| 17 | **EWMA span ramp (returning players)** | Low-medium — touches `project_minutes()` |
| 18 | **fg3a × stable_pct (3PT specialists)** | Low — touches 3PM projection only |
| 19 | **Vegas line movement signals** | Low — additive signal, doesn't replace existing scoring |
| 20 | **Referee tendency data** | Low — small additive multiplier in nba_projector |
| 21 | **Line shopping gap analysis** | Medium — may change how best line is selected in evaluate_props |
| 22 | **SGP copula deep-dive** | Medium — touches live SGP scoring in sgp_builder.py |

---

## Tier 6 — Meaningful builds (touch existing systems, needs care)

| # | Item | Notes |
|---|------|-------|
| 23 | **Opp defensive splits for STL/BLK** | New DB columns in `projections_db.py` + `get_team_def_ratio()` call in `nba_projector.py`. Prerequisite for #24. |
| 24 | **STL/BLK tier activation** | Add to TIERS config + evaluate_props gates. Needs #23 done first + SaberSim projection availability confirmed. |
| 25 | **NHL props expansion** | Add saves / assists / PPP / goals to NHL eval path. Needs SaberSim NHL projection column research first. |

---

## Tier 7 — Large new builds

| # | Item | Notes |
|---|------|-------|
| 26 | **MLB go-live** | Currently shadow. Config change + CLV daemon update. Go-live = Jono's call when data is clean. |
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
