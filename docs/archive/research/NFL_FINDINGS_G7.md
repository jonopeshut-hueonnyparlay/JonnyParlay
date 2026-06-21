# NFL Model Findings — G7: Role Tiers, Kickers/DST, STAT_CAP, KILLSHOT, SHADOW_SPORTS

**Date:** 2026-05-21  
**Agent:** G7  
**Source sections:** Role Tiers, Kickers and D/ST, STAT_CAP and SPORT_UNIT_CAP, KILLSHOT Eligibility, SHADOW_SPORTS  
**Research base:** Web search + cross-referencing existing NBA/MLB/NHL model parameters  

---

## ROLE TIERS

### Best proxy for tier without custom projections

SaberSim DraftKings salary is the most reliable single proxy for role tier — it encodes usage, opportunity, and snap/target share simultaneously. Do not use SaberSim projected points directly because they vary by game total and opponent; salary is more stable. Target share (%) from the SaberSim CSV is the best secondary signal for WRs and TEs.

**Ordering of proxy reliability:**
1. DK salary (encodes market consensus on usage + opportunity)
2. Target share % (WR/TE) or carry share % (RB) from SaberSim CSV
3. Snap share % (less available in SaberSim CSV, use if present)
4. Projected points (weakest — game-script dependent)

---

### Tier Definitions

**RB1 — Workhorse Back**
- DK salary ≥ $6,500 OR carry share ≥ 60% (in SaberSim CSV where available)
- High confidence, lower CV (~0.45 typical)
- Full model confidence; T1/T2 eligible based on edge
- Gate: must project ≥ 45 rushing yards before pick is posted

**RB2 — Committee or Handcuff Back**
- DK salary $4,500–$6,499 OR carry share 30–59%
- Medium confidence, higher CV (~0.65–0.80)
- Cap tier routing at T2 regardless of edge score — RB2 picks cannot reach T1
- Gate: must project ≥ 25 rushing yards before posting

**RB3 — Deep committee / low usage**
- DK salary < $4,500
- Skip entirely — model likely to misfire on committee noise
- Refuse to post; below salary floor

**WR1 — Primary Receiver**
- DK salary ≥ $6,500 OR target share ≥ 22% (season-average or SaberSim projected)
- 120+ season targets is the WR1/WR2 line historically (NFL.com analysis)
- High confidence; T1/T2 eligible
- Gate: must project ≥ 50 receiving yards before posting

**WR2 — Secondary Receiver**
- DK salary $5,000–$6,499 OR target share 14–21%
- Medium confidence; cap at T2
- Gate: must project ≥ 35 receiving yards before posting

**WR3 / Slot / Low-Volume**
- DK salary $4,000–$4,999 OR target share < 14%
- Lower confidence, noisy target share (high CV ~0.85+)
- Cap at T3; rarely post unless edge is exceptional
- Gate: must project ≥ 25 receiving yards before posting

**TE1 — Primary Tight End**
- DK salary ≥ $4,500 OR projected targets ≥ 4.0/game in SaberSim
- Medium confidence (TEs have lower weekly target floor than WRs)
- T2 max — TE1 picks should not reach T1 in initial model build
- Gate: must project ≥ 30 receiving yards before posting

**TE2 — Blocking TE / Low Target Share**
- DK salary < $4,500 OR projected targets ≤ 2.0/game
- Avoid — model will systematically misfire on blocking TEs
- Skip entirely: do not post picks

**QB — Starting**
- DK salary ≥ $6,000 (any starting QB will be ≥ $6,000 on DK)
- High confidence; T1/T2 eligible for passing stats
- Backup QB: DK salary < $6,000 → skip entirely

---

### Salary Floor (Hard Skip)
- **DK salary < $4,000 → refuse to post regardless of edge**
- Below $4,000 on DK = noise players (handcuff scrubs, backup TEs, inactive risks)
- This threshold is conservative; can tighten to $4,500 after model validation

---

### Role Tier → Pick Tier Routing
| Player Tier | Max Pick Tier |
|-------------|--------------|
| RB1         | T1           |
| RB2         | T2           |
| RB3         | skip         |
| WR1         | T1           |
| WR2         | T2           |
| WR3         | T3           |
| TE1         | T2           |
| TE2         | skip         |
| QB (starter)| T1           |
| QB (backup) | skip         |

---

## KICKERS AND D/ST

### Should the model skip kicker props entirely?

**Yes — skip kicker props entirely.**

Reasons:
- Kicker field goal total props exist on DraftKings (under "D/ST Props — Kicking Pts") and BetMGM, but they are extremely low volume (1–3 picks per game max), highly weather-sensitive, and difficult to project without stadium/temperature/opponent kick coverage data.
- The Odds API does not expose a reliable `player_kicking` or `player_field_goals` market key consistently across CO-legal books — it is not in the standard documented market list (confirmed via Odds API docs).
- Even if the market key exists, vig is typically -130/-130 or wider on kicker props, making positive EV very difficult.
- SaberSim NFL CSV does include kicker salary and some projection, but the underlying model is too coarse for reliable betting.
- **Decision: Gate out kickers entirely at the position level.** If `position == "K"` in SaberSim CSV, skip.

### Are kicker/D/ST props in The Odds API?

**Confirmed: DraftKings and FanDuel offer D/ST sack and kicking props** via their sportsbook UI. However, The Odds API's documented player prop market keys do NOT include dedicated kicker or D/ST sack market keys in their standard tier. This means:
- No consistent programmatic access via `americanfootball_nfl` player prop endpoints
- If the market key does exist (e.g., `player_field_goals`), coverage is likely limited to 2–3 books
- **Gate:** Even if a market key is found, skip kicker and D/ST player props in initial build

### D/ST team-level sack props — worth modeling?

**Team sacks total: conditionally worth modeling, but defer to Phase 2.**

Key findings:
- DraftKings offers "D/ST Props — Sacks" as a team-level market (e.g., "Chiefs defense ≥ 3 sacks")
- FanDuel also offers "NFL Sacks and Interceptions" under D/ST tab
- The Odds API market key for this is NOT in the standard documented list — likely accessible via `player_pass_sacks` or a custom team prop market, but not confirmed
- **Distribution for team sacks:** Negative Binomial recommended. Team sacks per game average ~2.5–3.0 with mean ~2.6, variance much larger than Poisson would predict (overdispersed). NB_R ≈ 3.0 is a reasonable initial prior.
- **Team INT total props:** Much rarer as a betting market. Low sample + high variance → skip in Phase 1.

**Recommendation:** Skip D/ST props in Phase 1. Add team sacks as a Phase 2 market once The Odds API market key is confirmed and NB_R is calibrated on actual book lines.

---

## STAT_CAP (max picks per stat per run)

### Rationale
NFL has 1 QB per team → 2 starting QBs per game, 16 games on a full Sunday slate = max 32 QBs. WR/RB/TE: many more options but pick quality degrades quickly past top tier. Caps prevent card bloat and correlated overexposure.

### Recommended STAT_CAP for NFL

| Stat         | Cap | Rationale |
|--------------|-----|-----------|
| PASS_YARDS   | 4   | 1-2 elite QBs per game; avoid posting on weak matchups |
| RUSH_YARDS   | 5   | More RB1s across slate; cap prevents committee-back noise |
| REC_YARDS    | 8   | Most picks will come here; highest market availability |
| RECEPTIONS   | 6   | Correlated with REC_YARDS; separate cap avoids double-stacking |
| PASS_TDS     | 3   | Binary/overdispersed; strict cap to avoid overclaiming TD edges |
| RUSH_TDS     | 3   | Same — rare count stat, high variance |
| REC_TDS      | 3   | Same as above |
| INT          | 2   | Extremely rare; 2 max prevents noise picks |
| SPREAD       | 6   | Standard game line; same as other sports |
| TOTAL        | 4   | Standard; weather-sensitive |
| TEAM_TOTAL   | 4   | Correlated with spread; cap prevents double-dip |

**Total-day cap on a 16-game Sunday slate:**
The existing 12u/day cap applies. However, with 16 games the card could theoretically surface 30+ picks. Add a secondary gate: **max 20 total picks per Sunday run** (regardless of units). This prevents card dilution and keeps the brand's quality signal high.

On a single-game slate (TNF, SNF, MNF): **max 4 picks per game** to prevent correlated overexposure.

### SPORT_UNIT_CAP for NFL

**Recommendation: 4u max per single NFL pick.**

Rationale:
- NBA = 8u (daily format, many games, high sample to validate)
- NHL = 5u (daily format, fewer games per slate)
- NFL = 4u (weekly format, single-game variance is enormous, 17-game season = tiny validation window)
- Never post a full Kelly bet on NFL without 2+ seasons of calibrated data
- After shadow validation with ≥300 picks and positive CLV, can revisit 5u ceiling

**Day-of unit exposure cap:** On a 16-game Sunday slate with 20 picks at up to 4u each = theoretical 80u exposure. The existing 12u/day cap handles this, but add a **per-game cap of 2u total** (not picks — aggregate units per game). This prevents a single game blowup from burning the entire day's bankroll.

---

## KILLSHOT ELIGIBILITY (NFL)

### Which stats eligible for KILLSHOT?

| Stat       | Eligible? | Reason |
|------------|-----------|--------|
| PASS_YARDS | YES       | Continuous, normally distributed, tightest markets, most projectable |
| RUSH_YARDS | YES       | Workhorse RB1s have tight CV; best use is ≥55-yard lines |
| REC_YARDS  | YES       | WR1 with high target share; best projectable receiver stat |
| RECEPTIONS | MAYBE     | Reasonable if ≥5.5 line and WR1 with consistent target share; debut as eligible but monitor |
| PASS_TDS   | NO        | Too binary/overdispersed for KILLSHOT conviction |
| RUSH_TDS   | NO        | Too rare; variance destroys win probability signal |
| REC_TDS    | NO        | Same |
| INT        | NO        | Directionally hard to predict; almost never KILLSHOT quality |
| SPREAD     | YES       | Same as NBA — game line KILLSHOT is viable with high win_prob |
| TOTAL      | MAYBE     | Weather risk in outdoor stadiums; only eligible in dome/closed-roof games |

**Initial eligible KILLSHOT stats: PASS_YARDS, RUSH_YARDS, REC_YARDS, SPREAD**  
After 1 season of data: add RECEPTIONS if calibration holds.

---

### win_prob threshold for NFL KILLSHOT

**Recommendation: 0.70 (raise from NBA's 0.65)**

Rationale:
- Weekly format: one bad KILLSHOT per week is a larger fraction of the week's card than one bad NBA pick per day
- NFL prop lines are less efficient (wider vig, more market maker uncertainty) — but model calibration uncertainty is ALSO higher (no NFL-specific Platt scaling initially)
- Use identity calibration (A=1.0, B=0.0) until ~200 NFL picks accumulated → raw win_prob is noisier → need higher threshold as buffer
- **Floor: win_prob ≥ 0.70 for NFL KILLSHOT**

---

### Odds range for NFL KILLSHOT

**Keep [-200, +110] same as NBA initially.**

However: NFL props frequently have wider juice than NBA (-120/-110 vs NBA's tighter -115/-115). Monitor whether the [-200, +110] range captures enough volume. If KILLSHOT fires zero times in first 4 weeks because juice is always -120 or worse, widen to [-200, +120].

Do NOT widen to +150 or higher — that would make KILLSHOT lottery-adjacent, undermining the brand.

---

### Weekly cap for NFL KILLSHOT

**Recommendation: 1 KILLSHOT per week maximum (reduce from NBA's 2/week)**

Rationale:
- NBA has 5–7 game days per week → 2 KILLSHOTs across many opportunities is conservative
- NFL has 1 main slate per week → 1 KILLSHOT on that slate is the correct unit of measurement
- With 17 regular season weeks, 1/week = 17 max KILLSHOTs per season — a credible annual volume for a premium tier
- The brand value of KILLSHOT depends on rarity; 2/week on NFL would devalue it

---

## SHADOW_SPORTS

### Should NFL launch in shadow mode?

**Yes — mandatory shadow mode for NFL before going live.**

NFL is a distinct sport with no calibrated model parameters (no NFL-specific Platt scaling, no validated NB_R values, no tested role-tier thresholds). Shadow mode is essential.

---

### Shadow weeks needed before NFL goes live

**Minimum: 6 weeks (target: full first half-season = 9 weeks)**

Rationale:
- Week 1 NFL has high variance: new rosters, injury surprises, Week 1 game scripts are notoriously unpredictable
- Weeks 1–3: model settling, line access confirmation, Odds API integration testing
- Weeks 4–9: live shadow tracking with CLV capture
- By Week 9 (mid-season), you have ~9 games per stat × 5 stats × 9 weeks ≈ enough data to start seeing patterns

**Hard gate: do NOT go live before Week 6 regardless of results.**

---

### Minimum picks for calibration validation

**Minimum N = 200 NFL prop picks (shadow log) before considering go-live.**

Rationale:
- Sports betting literature: need 200–300 bets minimum before trusting CLV signal for a new model
- NFL accumulates ~5–15 picks per week (depending on slate size and stat cap)
- At 10 picks/week average: 200 picks = 20 weeks = roughly 1.2 seasons
- This means NFL shadow mode will likely span **the entire first NFL season (2026 regular season)** and go live in **2027 season Week 1** unless early results are exceptionally clean

**CLV exit gate (NFL-specific):**
- NBA used ~100 CLV rows as the go-live gate — but NBA accumulates CLV daily
- NFL accumulates CLV weekly (daemon runs T-30 to T+3 around each game)
- Use **a minimum of 100 CLV rows AND positive mean CLV (+0.5% or better)** as the exit gate
- At 10 picks/week, 100 CLV rows ≈ 10 weeks of shadow
- Secondary check: win rate ≥ 52% over the shadow sample (not just CLV)

**Fast-track scenario:** If Week 1–4 shows consistently positive CLV (+1.5%+) AND win rate ≥ 55% AND pick volumes are stable, the go-live gate can be reduced to 75 CLV rows with manual review. This would allow a mid-season go-live (Week 8–10 of 2026 season).

---

### CLV accumulation rate (NFL vs NBA)

| Sport | Games/week | Picks/week (est.) | CLV rows/week |
|-------|------------|-------------------|---------------|
| NBA   | 5–12 games | 8–15 picks        | 8–15/week     |
| MLB   | 15–20 games| 5–12 picks        | 5–12/week     |
| NHL   | 5–8 games  | 5–10 picks        | 5–10/week     |
| NFL   | 1 slate    | 8–14 picks        | 8–14/week     |

NFL CLV accumulates at ~1 data point per week per pick (picks settle Sunday, CLV captured T+3 = Sunday night). The daemon's existing daily polling architecture works for NFL without modification — the T-30 window will fire on Sunday morning before 1pm kickoffs.

---

## SUMMARY TABLE

| Parameter                    | NBA value         | NFL recommendation      |
|-----------------------------|-------------------|-------------------------|
| SPORT_UNIT_CAP              | 8u/pick           | 4u/pick                 |
| KILLSHOT win_prob floor      | 0.65              | 0.70                    |
| KILLSHOT weekly cap          | 2/week            | 1/week                  |
| KILLSHOT odds range          | [-200, +110]      | [-200, +110]            |
| Salary/DK floor (skip)       | N/A (minutes-based)| DK < $4,000 = skip      |
| RB2 tier routing             | N/A               | cap at T2               |
| TE1 tier routing             | N/A               | cap at T2               |
| Kicker picks                 | N/A               | skip entirely           |
| D/ST player props            | N/A               | skip Phase 1            |
| Team sacks props             | N/A               | Phase 2 (NB, r≈3.0)    |
| Shadow min picks             | ~100 CLV rows     | 200 props + 100 CLV rows|
| Shadow min weeks             | N/A               | 6 weeks minimum         |
| STAT_CAP PASS_YARDS          | N/A               | 4                       |
| STAT_CAP RUSH_YARDS          | N/A               | 5                       |
| STAT_CAP REC_YARDS           | N/A               | 8                       |
| STAT_CAP RECEPTIONS          | N/A               | 6                       |
| STAT_CAP TD stats            | N/A               | 3 each (PASS/RUSH/REC)  |
| STAT_CAP INT                 | N/A               | 2                       |
| Max picks per Sunday run     | N/A               | 20 total                |
| KILLSHOT eligible stats      | PTS,AST,SOG,3PM   | PASS_YARDS,RUSH_YARDS,REC_YARDS,SPREAD |
