# Section 6: Injury Market Impact — Book Repricing Lag Research

**Research date:** 2026-05-21  
**Queries run:** 28 across 5 batches  
**Key academic anchor:** Humphreys 2015 (ScienceDirect) — NBA opening lines have significant errors in injury games; closing lines are approximately fair. All edge is in the announcement→close window.

---

## Table 1: Book Adjustment by Position/Stat

| SPORT | INJURED | AFFECTED MARKET | LINE MOVE | DIRECTION | CONFIDENCE | SOURCE |
|-------|---------|-----------------|-----------|-----------|------------|--------|
| NBA | Star PG (OUT) | Backup PG AST | +1.5–3.0 AST | **Under-adjusted** — backup's line set on 15-min avg; now playing 30–35 min | Medium | rithmm.com; oddsindex.com |
| NBA | Star PG (OUT) | Game TOTAL | −2 to −4 pts | Accurate; may over-adjust if backup is solid | Medium | hoopheadspod.com; bettoredge.com |
| NBA | Star PG (OUT) | Other players PTS (non-backup) | Minimal move | **Under-adjusted** — usage spreads; books only update obvious replacement | Low-Medium | bettoredge.com; rithmm.com |
| NBA | Star C (OUT) | Backup C REB | +1.0–2.5 REB | **Under-adjusted** — rim rebounds concentrate; books track star C, miss backup C | Medium | bettoredge.com; unabated.com |
| NBA | Star C (OUT) | Team TOTAL | −1 to −3 pts | Accurate — rim protection loss may offset scoring loss; net near-zero | Medium | oddsindex.com; bettoredge.com |
| NBA | Star SF (OUT) | Other SF PTS | +0.5–1.5 pts | **Under-adjusted** — SF usage spreads 2–3 players; second-order beneficiaries missed | Low | bettoredge.com |
| NBA | Star SF (OUT) | Game TOTAL | −1 to −3 pts | Accurate to slightly over-adjusted for elite wing (25+ ppg) | Medium | hoopheadspod.com |
| NBA | Defensive stopper (OUT) | Opponent star PTS | "Line should be 2–3 pts higher" — books lag ~half game | **Under-adjusted** — morning shootaround timing is critical | Medium | oddsindex.com (explicit) |
| NHL | Top-6 F (OUT) | Other F SOG | +0.5–1.5 SOG — Nylander example: 2.7→4.1/game, books kept at 2.5–3.0 | **Under-adjusted** — most concrete data point in the research | Medium | tonyspicks.com |
| NHL | Top-6 F (OUT) | PP time for others | +1–2 min PP time [unverified estimate] | **Under-adjusted** — PP metrics spike before books adjust | Medium | tonyspicks.com |
| NHL | Top-6 F (OUT) | TOTAL | −0.25 to −0.50 goals | Accurately adjusted; smaller effect than goalie swap | Low-Medium | mybookie.ag [magnitude unverified] |
| NHL | #1 D (OUT) | Other D SOG | +0.3–0.8 SOG [unverified estimate] | **Under-adjusted** — D SOG is thin market; books rarely update #2 D lines | Low | sportbotai.com [no empirical source] |
| NHL | Backup goalie starts | TOTAL | +0.34 goals average; extreme up to +1.3 goals (4.9→6.2 documented) | **Over-adjusted in high-profile cases** — public bombs the over; sharp play is to fade | High | sportbotai.com; mybookie.ag |
| MLB | Cleanup hitter (OUT) | Team TOTAL | −0.3 to −0.8 runs [unverified estimate] | Accurate to slightly over-adjusted for elite bats | Low | oddsindex.com [magnitude unverified] |
| MLB | Cleanup hitter (OUT) | Other batters TB/HITS | Minimal adjustment | **Under-adjusted** — lineup protection analysis rarely priced | Low | No empirical source found |
| MLB | SP scratch | Replacement K props | Props VOIDED; new line posted for replacement — no direct adjustment window | N/A — original bet voids | High (on void mechanics) | actionnetwork.com |
| MLB | SP scratch | Team TOTAL | +1.5–2.0 runs (ace→bullpen game); +0.5–1.0 for rotation-spot replacement | Accurate for ace scratch; may over-adjust for serviceable #3–4 arm | High | yardbarker.com |
| NFL | RB1 (OUT) | RB2 RUSH_YARDS | +4–8 rush yard line bump; books use RB2's season avg, often stale | **Under-adjusted** — RB2 carries jump 10→18–22 touches; line set on small sample | Medium | VSiN; actionnetwork.com |
| NFL | RB1 (OUT) | Game TOTAL | −0.5 to −1.5 pts | Accurate — game flow changes, net impact modest | Low-Medium | packernet.com |
| NFL | WR1 (OUT) | WR2 REC_YARDS | +10–20 receiving yard bump; elite tier moves spread 2.0 pts | **Under-adjusted on #3 WR** — target cascade to 3 receivers; books update WR2 only | Medium | VSiN; SharpFootball |
| NFL | QB injury (OUT) | Game TOTAL | −3 to −7 pts total (elite→journeyman); up to −10 extreme cases | Accurate to slightly over-adjusted — public overvalues QB; spread moves 5–7 pts | High | walterfootball.com; packernet.com |
| NFL | QB injury (OUT) | RB RUSH_YARDS | +5–10 rush yard bump (run-heavy backup offense) | **Under-adjusted** — books slow to model backup QB run-reliance | Low-Medium | VSiN [no dedicated empirical source] |

---

## Table 2: Exploitation Window by Sport/Stat

All CLV percentages marked [estimated] — derived from known spread-value formula (1 spread pt ≈ 2–3% EV) applied to prop line moves. Not directly sourced from a CLV study.

| SPORT | STAT | SLOW BOOK LAG | CLV at 5 min | CLV at 15 min | CLV at 30 min | Half-life | SOURCE |
|-------|------|--------------|-------------|--------------|--------------|-----------|--------|
| NBA | AST | 15–40 min (Fanatics/Hard Rock/BetRivers) | +3–6% [estimated] | +2–4% [estimated] | +1–2% (mostly closed) | ~10–15 min | rithmm.com; oddsindex.com; Humphreys 2015 |
| NBA | PTS | 15–40 min slow books | +2–5% [estimated] | +1–3% [estimated] | Near-zero at sharp books | ~8–12 min | bettoredge.com; oddsindex.com |
| NBA | REB | 15–40 min slow books | +2–4% [estimated] | +1–2% [estimated] | Near-zero | ~10–15 min | unabated.com [no specific study] |
| NHL | SOG | 15–30 min after confirmation (goalie: 60–90 min before puck drop at sharp books) | +2–5% [estimated] | +1–3% [estimated] | +1–2% | ~20–30 min (thinner market, adjusts slower) | mybookie.ag; sportbotai.com |
| MLB | K (vs replacement SP) | Props voided; replacement K is a fresh market. Sharp books post quickly; slow books lag 30–60 min | N/A (void) | New market posted ~30–60 min before game | N/A | ~30–60 min on thin replacement market | actionnetwork.com |

**Critical note:** The Humphreys 2015 study (ScienceDirect) is the only academic anchor. It confirms opening lines err materially in injury games; closing lines are fair. This validates the exploitation window framework but provides no CLV magnitude data. Your own `pick_log_custom.csv` CLV rows are the only path to calibrated numbers.

---

## Section 6B: Systematic Patterns

### Most consistent UNDER-adjustment (exploit these)

**1. NBA — Backup AST after star PG out** (strongest/most documented)
Books set the backup's line on their 20-min average; backup now plays 35 min. AST is highly usage-dependent and redistributes almost entirely to the primary backup. oddsindex explicitly documents "half-game lag" when this breaks during morning shootaround. This is the most exploitable single scenario across all sports.

**2. NBA — Defensive stopper out → opposing star PTS**
oddsindex playoff article explicitly states books lag "half a game" on this. Books update the injured player's market; opponent star PTS props sit stale. The line "should be 2–3 pts higher."

**3. NHL — SOG for other forwards after Top-6 F exits**
Nylander example is the most concrete data point in the research: SOG jumped 2.7→4.1/game, books maintained lines at 2.5–3.0. Power play time reallocation is the mechanism — books don't update SOG props when PP minutes shift.

**4. NFL — RB2 rush yards after RB1 out**
VSiN confirms books update spread/total but are slower on individual RB2 prop lines. RB2 carries jump from ~10 to 18–22 — a near-doubling that isn't reflected in a +4–8 yard bump.

**5. NFL — WR3 receiving yards after WR1 out**
Books update WR2; the cascading target shift to WR3 is consistently missed.

### Most consistent OVER-adjustment (fade these)

**1. NHL — Game total when backup goalie announced**
SportBotAI empirical finding: average lift is only +0.34 goals, but public bombs extreme cases to +1.3 goals (4.9→6.2). The sharp play is fading the over when the public overreacts to a backup goalie narrative.

**2. NBA — Game total when elite scorer ruled out**
bettoredge.com: books "over-adjust for big names to manage public perception." Teams with solid benches outperform the lowered total in early games after a star injury. The market over-prices star absence at the game-level.

**3. NFL — QB injury spread (extreme cases)**
Line moves 5–7 pts correctly on average; moves of 7+ pts may overshoot when the backup is a competent veteran.

### "Forgotten player" patterns

- **Second and third beneficiaries** are the most consistently mispriced. When Embiid sits, Maxey gets attention — but role PF/C players see additional touches nobody prices.
- **MLB lineup protection:** When cleanup hitter sits, #5 and #6 hitters see lineup protection improvements that are almost never priced into their TB/hits props.
- **NFL receiving corps:** Books update WR2 only; WR3 and TE target-share spillover goes unpriced.

### Exploitability ranking by sport

| Rank | Sport | Reason |
|------|-------|--------|
| 1 | **NBA** | Most liquid prop market + fastest news cycle + Humphreys 2015 academic validation of opening-line errors |
| 2 | **NHL** | SOG/PP markets less liquid → longer stale window; Nylander data point is concrete |
| 3 | **NFL** | Weekly news cycle = less time pressure; RB2/WR3 cascading patterns documented |
| 4 | **MLB** | SP scratch voids K prop (no edge on original bet); replacement pitcher is a new market; cleanup hitter impact on others not documented |

---

## Section 6C: CLV Magnitude by Injury Type

| Injury type | Window | CLV magnitude | Notes |
|-------------|--------|---------------|-------|
| Confirmed OUT (announced before props post, 11am–1pm NBA) | None for beneficiary — books post already adjusted | Minimal unless secondary beneficiary | NBA's 11am–1pm injury report + 10am–noon prop posting means timing matters enormously |
| Confirmed OUT (late scratch, <2h to tip) | **Best window** — 15–40 min on slow books | +3–8% implied prob [estimated] vs closing line at sharp books | Humphreys: opening lines err materially; this is where the edge lives |
| GTD → confirms active (game-day morning) | Negative for beneficiary who bet early | Negative CLV on beneficiary bet | Risk: if you took the over on backup at inflated line and player confirms in → line drops |
| GTD → confirms out (warmups) | **Best possible window** — shortest correction time for slow books | +5–10% [estimated] | Maximum lag; warmup scratch gives slow books the least time |
| Q listed (unresolved before game) | Moderate window if Q resolves OUT at last moment | +2–5% [estimated] on resolution | Most books pull Q'd player's own props; void risk on injury player's line; beneficiary line may sit stale |

**CLV half-life:** Based on NBA timing research (DK/FD/BetMGM adjust in 10–30 sec, slow books 15–40 min), the half-life of slow-book advantage is approximately **10–15 minutes** for NBA props, **20–30 minutes** for NHL SOG. At 30 minutes post-announcement, the edge at slow books is likely <2%.

---

## Table 3: Pick Score Bonus Specification

**Current system:** `INJURY_TRIGGER_BONUS = 7` (flat, applies to all redistribution-bump picks).  
**Calibration context:** 1pp win_prob = +4 score pts; 1pp edge = +2 score pts. A 3pp win_prob uplift ≈ +12 score pts.

| Scenario | Current bonus | Research-supported bonus | Confidence | Rationale / Source |
|----------|--------------|--------------------------|------------|--------------------|
| Confirmed OUT (late scratch) → replacement AST | +7 | **+10–12** | Medium | Strongest under-adjustment pattern; "2–3 pt line should be higher" → ~3pp win_prob uplift → +12 pts. oddsindex.com; rithmm.com |
| Confirmed OUT (late scratch) → replacement PTS | +7 | **+8–10** | Medium | Second-strongest; secondary beneficiaries less reliable than backup PG AST. bettoredge.com |
| Confirmed OUT (late scratch) → replacement REB | +7 | **+7–9** | Medium | REB concentrates on backup C; market under-adjusts but REB is noisier. unabated.com |
| GTD → confirms active (fear allayed, beneficiary bet already placed) | 0 | **−3 to −5** (negative penalty) | Low | No empirical source for exact magnitude; directional penalty recommended |
| Defensive stopper OUT → opposing star PTS | +7 (if trigger fires) | **+8–10** | Medium | "Half-game lag" explicitly documented; 2–3 pt line miss. oddsindex.com |
| NHL Top-6 F → other F SOG | +7 (if trigger fires) | **+8–10** | Medium | Nylander: SOG 2.7→4.1, books at 2.5–3.0. Power play reallocation is the signal. tonyspicks.com |
| MLB SP scratch → replacement K | N/A (void) | **+5–7 for replacement K line** if a fresh market opens at a weak projection | Low | Void mechanics mean you're betting a new market; books post initial replacement K lines quickly. actionnetwork.com |

**Recommendation:** Replace the single flat `INJURY_TRIGGER_BONUS = 7` with a dict keyed by `(sport, stat, scenario_type)`. The AST/backup-PG scenario earns the highest bonus (+10–12); GTD-confirms-active should carry a negative adjustment.

---

## Table 4: Implementation Phases

### Phase 1 — No custom engine required (implement now)

- Differentiate `INJURY_TRIGGER_BONUS` by stat: AST → +10, PTS → +8, REB → +7. Change single constant to a dict in `run_picks.py`.
- Add `stopper_injury_trigger` flag for opposing star PTS picks (requires manual identification from morning injury report). Apply +8 bonus.
- Add `INJURY_OPPORTUNITY` label to pick output when `injury_trigger=True`.
- Use `--force-card` to override card guard when a late scratch breaks.

### Phase 2 — After custom engine go-live

- `injury_parser.py` already tags redistribution beneficiaries. Extend to output `injury_trigger_type` field: `{backup_ast, backup_pts, backup_reb, opponent_star, nhl_sog, stopper_out}`.
- Auto-apply differentiated bonuses by `injury_trigger_type` without manual tagging.
- `--late-run` already re-fetches injuries. Extend to auto-detect Q/GTD resolution, re-price beneficiary picks, and flag if a material line change occurred.
- Log `injury_trigger_type` to `pick_log.csv` for downstream CLV segmentation.

### Phase 3 — Data accumulation required

- Once ~100 CLV rows exist with `injury_trigger=True`: segment mean CLV on injury-triggered vs baseline picks. If material difference confirmed, increase bonuses to calibrate.
- If stat-specific CLV differs (AST vs PTS vs REB), apply stat-specific constants confirmed by data rather than research estimates.
- H3 Platt refit unlocks (~300 `over_p_raw` rows) — check whether injury-triggered picks have systematically different calibration requiring a separate Platt curve.
- Opposing-team beneficiary props (defensive stopper out → opponent star): only model explicitly after custom engine go-live (projection engine currently captures matchup factors; opponent AST/REB impact not modeled — Phase 2/3 work).

---

## Key Data Gaps

**What is well-sourced:**
- NBA game total drops 2–4 pts when a top-5 player is out (multiple consistent sources)
- NHL backup goalie lifts totals by +0.34 goals average; extreme cases up to +1.3 goals (SportBotAI empirical)
- MLB ace scratch lifts total 1.5–2.0 runs for bullpen game (yardbarker/thelines confirmed)
- NFL QB injury moves spread 5–7 pts; elite WR/TE worth ≤2.0 spread pts (VSiN/SharpFootball)
- Humphreys 2015: NBA opening lines err materially in injury games; closing lines are fair
- Defensive stopper out → opposing star PTS "half-game lag" explicitly stated (oddsindex.com)
- Nylander SOG 2.7→4.1/game vs books at 2.5–3.0 — most concrete single under-adjustment data point (tonyspicks.com)

**What is NOT empirically sourced (directional only):**
- Specific CLV percentages at 5/15/30 min post-announcement — **no study found**
- Exact magnitude of backup AST line under-adjustment
- REB redistribution line move size for backup C
- MLB cleanup hitter injury impact on other batters TB/HITS
- NFL RB1 out → game total magnitude (qualitative only)
- GTD-confirms-active CLV penalty magnitude

**The most important gap:** Your own `pick_log_custom.csv` CLV data, once 100 injury-triggered rows accumulate, is the only path to properly calibrated bonuses for this specific model. The academic literature confirms the *existence* of edge; it does not provide the magnitudes needed for precision calibration.

---

## Sources

- [Are Injuries in NBA Good for Player Props? — rithmm.com](https://www.rithmm.com/post/are-injuries-in-nba-good-for-player-props/)
- [Top 5 Ways Player Injuries Affect NBA Betting Lines — bettoredge.com](https://www.bettoredge.com/post/top-5-ways-player-injuries-affect-nba-betting-lines)
- [The Role of Injuries in NBA Betting — hoopheadspod.com](https://hoopheadspod.com/the-role-of-injuries-in-nba-betting-how-line-movements-reflect-player-absences/)
- [NBA Playoff Bets: Injuries, Props & Key Edges — oddsindex.com](https://oddsindex.com/sports/nba/nba-playoff-injuries-flip-bets-props-unders-rule)
- [How Injuries Affect Betting Lines — oddsindex.com](https://oddsindex.com/guides/injury-impact-betting-guide)
- [How Injuries Affect Betting Lines — yardbarker.com](https://www.yardbarker.com/general_sports/articles/how_injuries_affect_betting_lines_a_guide_to_market_movement/s1_17354_43584377)
- [Fine Tune Your NBA Prop Betting Strategy — unabated.com](https://unabated.com/articles/fine-tune-your-nba-prop-betting-strategy-using-unabated-nba)
- [Player absence and betting lines in the NBA — Humphreys 2015 (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S1544612315000227)
- [NHL Goalie Confirmations & Line Movement — mybookie.ag](https://www.mybookie.ag/sports-betting-guide/goalie-confirmations-and-line-movement/)
- [NHL Backup Goalie Betting — sportbotai.com](https://www.sportbotai.com/blog/nhl-backup-goalie-betting-ai-predictions-value)
- [NHL Anytime Goal Scorer Props: Reading Power Play Time — tonyspicks.com](https://www.tonyspicks.com/2026/05/15/nhl-anytime-goal-scorer-props-reading-power-play-time-as-the-edge/)
- [Using NFL Injuries to Determine Betting Line Movement — VSiN](https://vsin.com/nfl/using-nfl-injuries-to-determine-betting-line-movement/)
- [How Injury News Moves NFL Betting Markets — packernet.com](https://www.packernet.com/blog/2026/03/10/how-nfl-injury-reports-impact-betting-lines-and-market-movement/)
- [Quarterback Injuries and NFL Betting Lines — walterfootball.com](https://walterfootball.com/quarterbackinjuriesimpact.php)
- [MLB Betting Rules for Scratched Pitchers — actionnetwork.com](https://www.actionnetwork.com/mlb/mlb-betting-rules-for-scratched-pitchers-action-vs-listed)
- [Closing Line Value — VSiN](https://vsin.com/how-to-bet/the-importance-of-closing-line-value/)
- [How to Find Value in NBA Player Props — pinnacle.com](https://www.pinnacle.com/betting-resources/en/educational/how-to-find-value-in-nba-player-props)
- [Live Betting Latency — tonyspicks.com](https://www.tonyspicks.com/2026/05/12/live-betting-latency-which-sportsbooks-update-fastest-during-play/)
