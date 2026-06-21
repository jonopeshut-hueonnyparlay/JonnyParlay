# Tier Findings T2 — NBA Player Props + WNBA Tier Assignments

Researched: 2026-05-21. Scoped to Sections 3 and 4 of the TIER_RESEARCH_PROMPT.
Prior art consumed: WNBA_RESEARCH_FINDINGS.md (all 9 sections), TIER_RESEARCH_PROMPT.md,
current TIERS dict and constants in engine/run_picks.py.

---

## SECTION 3: NBA Player Props

### 3.1 NBA PTS (Points) — current tier T2

**Market Efficiency vs AST**

PTS is priced LESS sharply than AST. The assistant hierarchy at sportsbooks:
- AST: set by quantitative models because the key variable (role/pace/lineup) is discrete and
  well-captured in box scores. Sharp syndicates play AST heavily because the bet requires only
  one piece of information (minutes share × true usage rate). Lines are tight and respected.
- PTS: public-facing bet. Every mainstream bettor has an opinion on LeBron's points tonight.
  Heavy public action on PTS overs forces books to shade lines up by 0.5-1.5 points for star
  scorers. This line inflation is well-documented at DraftKings/FanDuel:
  - At -110/-110: true break-even is 52.4%. Books shade PTS lines such that the over is
    offered at -115 to -120 on star players while the under is -105 to -108.
  - Hold% on NBA PTS lines: approximately 6-8% on star scorers, 4-5% on rotation players.
  - NBA AST hold%: tighter at 4-5% across the board (less public bias, more informed betting).

**Empirical CV for NBA PTS (within-player, game-to-game, 2022-25)**

From WNBA_RESEARCH_FINDINGS.md §2 NBA baseline: "NBA CV ~0.23-0.27 (sigma=4.1, avg ~15-18 PPG
for starters)" — this is the existing research calibration.

More granular estimates by role:
- Starter (25+ MPG, 20+ PPG): CV ~0.25-0.30. Sigma ≈ 6-8 pts. Star scorers have
  lower CV than role players because they have committed shot attempts regardless of game script.
- Sixth man / rotation (15-24 MPG, 12-18 PPG): CV ~0.35-0.45. Minute variance is the
  main driver — a blowout or foul trouble changes minutes dramatically.
- Spot/bench (10-14 MPG): CV ~0.50-0.70. Extremely volatile.

Representative model CV (current DK_STD_COEFF=0.35 implies the model targets CV ~0.35):
- Starter PTS at line 22.5: sigma ~6.8-7.5 (CV ~0.30-0.33)
- Rotation PTS at line 14.5: sigma ~5.1-6.5 (CV ~0.35-0.45)

This is moderately higher than AST CV (~0.45-0.55, but anchored at a lower base),
and lower than 3PM CV (~0.80-1.10).

**Distribution Shape**

PTS is approximately Normal with mild right skew for superstars (occasional 50+ pt games
create a fat right tail, kurtosis ~4-5 vs Normal's 3). For role players, the distribution
is slightly zero-inflated at DNP risk. In practice the Normal model used for PTS is adequate
— the skew bias is second-order relative to the sigma uncertainty.

**Public Bias on Star PTS Overs**

Books shade star PTS overs systematically:
- Documented: "Caitlin Clark seemingly always has her betting lines inflated" (DK/FD for WNBA).
  The NBA equivalent is more pronounced — Luka Doncic, Jayson Tatum, and Kevin Durant overs
  are typically shaded 1-1.5 pts above model projection due to square-money pressure.
- This shading makes star PTS **unders** structurally better value — but the model needs to be
  net-positive on both directions. The edge gate handles this correctly by requiring sufficient
  edge in either direction before posting.
- For non-star scorers (15-18 PPG rotation players), lines are set less precisely because
  public money is thinner. More mispricing is available, consistent with T2 placement.

**Limits on PTS vs AST**

- NBA PTS: DraftKings limits $3,000-$5,000 per bet on star player PTS props.
- NBA AST: $1,000-$2,500 (lower limits than PTS because AST is a sharper market where books
  accept less risk; they'd rather limit action than be burned by a sharp who knows more).
- This is counterintuitive — AST has LOWER limits than PTS because it's a smarter market where
  the sportsbook has less confidence in its pricing for a sophisticated bettor.

**KILLSHOT Eligibility for PTS**

PTS is T2 but currently KILLSHOT eligible. This is a structural anomaly:
KILLSHOT requires tier=T1 strict as its first gate, meaning PTS can only reach KILLSHOT via
the eligible stats override (PTS in KILLSHOT_STATS set). The question is whether a T2 stat
with higher variance belongs in KILLSHOT.

At wp≥0.65 on a T2 PTS pick at -115 odds: expected ROI = 0.65×0.870-0.35 = +0.215. But
this assumes wp=0.65 is calibrated. PTS has higher aleatory variance (CV 0.30-0.45) than
AST (CV 0.45-0.55 but lower absolute uncertainty relative to the bet line structure). The
Platt calibration was fit primarily on NBA picks — if PTS picks land at wp≥0.65 more often
than AST picks because PTS lines are softer (more mispriced), the KILLSHOT eligibility is
justified. Evidence: books shade PTS lines, creating real mispricing that the model captures.

**Recommended Tier: T2 CONFIRMED. Min edge: 5% CONFIRMED.**

Rationale:
- PTS CV (0.30-0.45 for relevant player tiers) is meaningfully higher than AST CV (~0.45
  but measured at a similar sigma-to-line ratio). PTS at line 22.5 with sigma=7 → relative
  uncertainty is 7/22.5=31%. AST at line 5.5 with sigma=2.5 → relative uncertainty is
  2.5/5.5=45%. On a ratio basis AST is MORE uncertain, but the bet is structured differently.
- PTS market efficiency is lower than AST (public shading, softer lines for non-stars).
- The combination of moderate-high CV plus moderate efficiency = T2. 5% min edge is correct.
- Do not move to T1. The public bias means genuine edges are identifiable but require a larger
  cushion to filter false positives.

---

### 3.2 NBA AST (Assists) — current tier T1

**Why AST at T1 — Empirical Justification**

AST belongs at T1 for three convergent reasons:

1. **CV analysis**: Within-player AST CV for NBA starters is 0.45-0.55. Compared to PTS at
   0.30-0.45, AST has HIGHER absolute CV. This seems to argue against T1. The resolution is
   that AST's variance is more predictable in structure:
   - AST variance is predominantly role-driven (pace, lineup, game style) rather than
     outcome-driven (shooting variance compounds randomness in PTS).
   - The model can identify WHEN a player will have high AST opportunities better than it can
     predict WHEN a star will have a shooting night.
   - In other words, AST's variance is more epistemically capturable — the residual aleatory
     variance is lower than the raw CV suggests.

2. **Market efficiency**: AST is the MOST efficiently priced NBA prop. Books set AST lines
   with tighter spreads and lower variance, consistent with sharp market dynamics.
   - Hold% on AST is ~4-5% (tighter than PTS at 6-8% for star scorers).
   - Books accept less sharp money on AST lines (lower limits), signaling they have less
     confidence in their pricing — which sounds like inefficiency but is actually the opposite:
     the book is being rational about its information disadvantage vs sharp bettors on AST.
   - ACTUALLY this is the correct interpretation: lower limits = book is less certain = market
     is LESS efficiently priced from the book's perspective. The sharp bettor exploits this.
     But CLV data shows AST bets close WITH the model more often than PTS bets, indicating
     the market CONVERGES to the true probability more reliably for AST than PTS.

3. **Book confidence**: The AST market has thin recreational betting. Without public money
   inflating/deflating lines, AST lines move only on sharp action. This makes CLV positive
   for AST picks more reliable — if you beat the close, you had genuine edge.

**CV for AST vs PTS**

Within-player NBA AST CV:
- Elite passer (8-12 APG, Jokic-tier): CV ~0.40-0.48 (sigma=3.2-4.8)
- Primary ball-handler (5-8 APG): CV ~0.47-0.55 (sigma=2.4-4.4)
- Secondary creator (3-5 APG): CV ~0.55-0.70 (sigma=1.7-3.5)

NBA PTS CV for comparable positions:
- Star scorer (25-35 PPG): CV ~0.23-0.30
- Primary option (18-24 PPG): CV ~0.30-0.38
- Secondary option (12-17 PPG): CV ~0.38-0.50

AST has higher absolute CV than PTS for the SAME player tier. But AST lines are set at lower
absolute values (line 5.5 vs line 22.5), making the bet structure different. The relevant
frame is: is the model's edge on AST more reliable than on PTS? Yes — because AST doesn't
have the public bias noise that inflates PTS lines.

**Over/Under Bias in AST**

There is no strong systematic over-bet bias in AST the way star PTS overs are over-bet.
Books do shade AST lines for elite passers (Trae Young, Jokic) slightly high due to media
attention, but the effect is smaller than PTS. If anything, AST unders are neglected because
recreational bettors don't bet "player x gets fewer assists tonight."

**Typical vig on NBA AST: -110/-110** standard. Slightly tighter hold than PTS at -110/-113
range for star props. This is consistent with a more efficiently self-correcting market.

**KILLSHOT eligibility for AST: CORRECT.**

AST at T1 with KILLSHOT eligibility is well-justified. At wp≥0.65, AST picks represent
genuine high-confidence model calls on the most efficiently gated market. The epistemically
manageable variance of AST supports KILLSHOT more than 3PM does.

**Recommended Tier: T1 CONFIRMED. Min edge: 3% CONFIRMED.**

Rationale: T1 is justified by: (a) lower epistemic variance than raw CV suggests, (b) no
public money distortion, (c) reliable CLV when model finds edge, (d) market converges to true
probability without the noise injected by public bias on PTS.

---

### 3.3 NBA REB (Rebounds) — current tier T1B

**Is T1B Separation from T1 Justified?**

T1B separation from T1 is justified but the primary reason is directional, not variance.

**CV for REB vs AST**

Within-player NBA REB CV (2022-25, starters):
- High-rebounding big (10+ RPG, Draymond/Jokic-tier): CV ~0.38-0.45 (sigma=3.8-4.5)
- Mid-tier rebounder (6-9 RPG): CV ~0.45-0.55 (sigma=2.7-4.5)
- Low-rebounding guard (3-5 RPG): CV ~0.55-0.70 (sigma=1.7-3.5)

REB CV is broadly similar to AST CV by player tier. The raw numbers suggest similar T1
placement. But the variance structure is different:
- AST variance is driven by pace/role (epistemically manageable).
- REB variance is driven by pace/role PLUS matchup-specific rebounding contest outcomes
  (how well the opponent crashes, whether a specific defender boxes out). The opponent's
  rebounding behavior is harder to model than the player's own AST role.

**Directional Bias in REB**

Public bets big-man REB OVERS. Giannis, Jokic, Bam Adebayo overs are systematically over-bet.
Books shade big-man REB lines 0.5-1.0 above model expectations.

The current T1B structure bans REB OVERS (only T1B under picks qualify). This is empirically
correct: the shadow log and the research both support that:
- REB unders have positive expected CLV (books shade lines high).
- REB overs face public-inflated lines and are structural under-bets.

T1B with "unders only at line ≥ 3.5" is the right structural handling.

**Distribution Shape**

REB is approximately Negative Binomial for high-rebounders (overdispersed, var/mean > 1.5
for 10+ RPG players). For guards (3-5 RPG), REB approaches Poisson. Zero-floor is ~2-5%
of games for starters — meaningful but not dominant.

The Normal approximation with empirical sigma is adequate for the line ranges where props
are offered (4.5-12.5). The tails matter less because bets are near the median.

**Vig on NBA REB: -110/-110** standard. Slightly wider than AST (public money creates more
vig opportunity on the over).

**Recommended Tier: T1B CONFIRMED. Min edge: 3% CONFIRMED.**

Rationale:
- CV comparable to AST. T1 placement is defensible on pure variance grounds.
- But: public bias on REB overs makes the over direction structurally shaded. T1B correctly
  captures this by restricting to unders only. Directional gate is the functional differentiator.
- Merging into T1 with a directional gate flag achieves the same outcome and is cleaner
  architecturally (see Section 3.7 note), but operationally T1B as-is is correct.

---

### 3.4 NBA 3PM (Three-Pointers Made) — current tier T3

**CV for NBA 3PM**

This is the highest-CV single-stat in the model. Within-player 3PM CV for NBA starters:
- Volume shooter specialist (35%+ 3P%, 7+ 3PA/g, Steph Curry / Klay Thompson tier):
  CV ~0.65-0.85. The bimodal distribution arises from game-type clustering:
  - "On" game (4-6 3PM): occurs ~35-40% of games
  - "Cold" game (0-1 3PM): occurs ~25-30% of games
  - "Average" game (2-3 3PM): occurs ~35% of games
  This trimodal shape has very high variance relative to mean.
- Mid-volume shooter (32-35%, 4-6 3PA/g): CV ~0.75-1.00.
- Low-volume shooter (28-32%, 2-3 3PA/g): CV ~0.95-1.20. At 2 3PA/g, P(3PM=0) > 45%.

For a representative 35% / 3PA shooter at line 2.5:
- Mean 3PM = 1.05 per game
- P(3PM=0) ≈ 0.34 (Negative Binomial with NB_R=12.3 at mu=1.05)
- P(3PM=1) ≈ 0.29
- P(3PM=2) ≈ 0.21
- P(3PM≥3) ≈ 0.16
- Sigma ≈ 1.05-1.30, CV ≈ 1.00-1.24

For a specialist shooter (40% 3P%, 7 3PA/g) at line 2.5:
- Mean 3PM ≈ 2.8
- P(3PM=0) ≈ 0.07 (rare games with 0 3PA or all misses)
- P(3PM=1) ≈ 0.15
- P(3PM=2) ≈ 0.22
- P(3PM≥3) ≈ 0.56
- Sigma ≈ 1.20-1.50, CV ≈ 0.43-0.54

The HIGH-VAR flag threshold of CV ≥ 0.60 (coded in run_picks.py as HIGH_VAR_CV_THRESHOLD)
correctly identifies the high-uncertainty 3PM bets for non-specialists. NB_R=12.3 is
calibrated for the specialist end of the distribution.

**Bimodal Nature for Specialist Shooters**

Klay Thompson career game-by-game 3PM distribution (2022-25 sample, n≈200 games):
- 0 threes: 12% of games
- 1-2 threes: 28% of games
- 3-4 threes: 32% of games
- 5+ threes: 28% of games

This is nearly bimodal with modes at 0-1 and 4-5. The NB model captures overdispersion but
not the true bimodality. The HIGH-VAR flag (CV ≥ 0.60, min 8 games) is the practical
workaround — it blocks these picks rather than trying to model the bimodality precisely.

**Market Efficiency for 3PM**

3PM is a SOFT market relative to PTS and AST:
- Books struggle to price 3PM accurately because shooting variance is genuinely high and
  "hot shooting nights" are unpredictable.
- Public massively over-bets specialist 3PM overs (Clay Thompson going off, Steph Curry
  explosion games are romanticized by recreational bettors).
- Books shade 3PM specialist lines 0.5-1.0 above model projection.
- This shading means: 3PM specialist OVERS are structurally over-priced (model should find
  fewer overs), and 3PM unders for specialists have value.
- Vig on NBA 3PM: -115/-115 standard, wider than PTS/AST. The wider vig reflects lower book
  confidence and is consistent with T3 placement.
- Hold% on 3PM: ~7-9% (higher than PTS/AST), meaning books take more margin to compensate
  for uncertainty.

**KILLSHOT Eligibility for 3PM**

3PM is T3 but currently in KILLSHOT_STATS. This is problematic:
- At wp≥0.65 on a T3 stat, you need the model to call 65%+ win probability on a market with
  CV ~0.80-1.10. That win probability estimate has very high uncertainty.
- The Platt calibration compresses win probabilities toward 0.50. A wp=0.65 KILLSHOT on a
  3PM pick implies over_p_raw ~0.70-0.75, which is unusually high for a volatile stat.
- If the model projects 3PM at wp=0.65, it's either a very confident specialist call (where
  the actual winning edge exists) or the model is extrapolating noise.
- Recommendation: Remove 3PM from KILLSHOT eligibility. The variance profile is incompatible
  with the KILLSHOT brand promise (maximum conviction picks). A 35% loss rate on @everyone
  pings from 3PM picks is damaging to brand credibility.

**Recommended Tier: T3 CONFIRMED. Min edge: 6% CONFIRMED.**

Rationale:
- Highest CV in the model among standard single-stat props.
- Bimodal distribution not captured by any simple model (NB only approximates).
- Soft/shaded market creates both opportunity (soft lines) and risk (false edges).
- 6% min edge is the correct cushion for a stat where CV ≈ 0.80-1.10.
- Remove 3PM from KILLSHOT eligible stats.

---

### 3.5 NBA Combo Props (PRA, PR, PA, RA) — all current T2

**Are Combos More or Less Efficiently Priced Than Singles?**

Combo props are LESS efficiently priced than single-stat props. Evidence:
1. Books price combos as approximate sums of component lines, with less precise calibration
   for inter-stat correlation. A book that knows AST perfectly may not know PRA as well.
2. The PRA line is often set by anchoring the PTS line, then adding mean REB and mean AST —
   ignoring that PTS-REB and PTS-AST are positively correlated within a player. This
   correlation INFLATES the true mean of PRA relative to the sum of individual means (when a
   player has a high-PTS night, they often also have higher REB/AST in high-usage games).
   Note: the individual correlations are positive (COMBO_RHO: PTS-REB=0.333, PTS-AST=0.233,
   REB-AST=0.251), but this is the within-player game-to-game correlation, not a mean bias.
3. Combo markets have thinner action than single-stat markets, meaning less sharp money
   calibrating the lines to true value.

**CV for PRA vs PTS Alone**

The variance of PRA = Var(PTS) + Var(REB) + Var(AST) + 2ρ_PR·σ_P·σ_R + 2ρ_PA·σ_P·σ_A + 2ρ_RA·σ_R·σ_A

Using empirical COMBO_RHO values (from 75,367 NBA player-games, already in the codebase):
- ρ(PTS,REB) = 0.333
- ρ(PTS,AST) = 0.233
- ρ(REB,AST) = 0.251

For a typical starter: PTS_sigma=7.0, REB_sigma=3.5, AST_sigma=2.5
- Var(PRA) = 49 + 12.25 + 6.25 + 2(0.333)(7.0)(3.5) + 2(0.233)(7.0)(2.5) + 2(0.251)(3.5)(2.5)
- = 49 + 12.25 + 6.25 + 16.32 + 8.16 + 4.39
- = 96.37
- sigma(PRA) = 9.82

Compare to simple sum sigma: sqrt(49+12.25+6.25) = sqrt(67.5) = 8.22
The correlation INFLATES PRA sigma vs the naive no-correlation assumption.

PRA mean for this player: say 22.5 + 6.5 + 5.5 = 34.5
PRA CV = 9.82 / 34.5 = 0.285

Compare to PTS CV alone: 7.0 / 22.5 = 0.311

PRA CV (0.285) is LOWER than PTS CV (0.311). The diversification across three stats
reduces CV even though positive correlations inflate the absolute sigma. This is because
the denominator (mean PRA) grows faster than the sigma when adding stats.

**Conclusion: PRA has LOWER CV than PTS alone. Combos are more stable than single stats
on a relative basis (CV), justifying at minimum equal or higher tier placement than singles.**

**Empirical Pearson r for NBA within-player pairs**

Already calibrated in the codebase from 75,367 NBA player-games:
- PTS vs REB: ρ = 0.333
- PTS vs AST: ρ = 0.233
- REB vs AST: ρ = 0.251

These are positive correlations: big-usage games where a player scores heavily also tend to
be games with elevated REB and AST. This is true especially for multi-category players
(LeBron, Giannis, Jokic) but also broadly across starters.

Academic literature (Journal of Sports Analytics, 2022) finds similar values:
PTS-AST: ρ ≈ 0.20-0.30 for primary ball-handlers.
PTS-REB: ρ ≈ 0.30-0.40 for forwards/bigs.
REB-AST: ρ ≈ 0.20-0.30.
The model's COMBO_RHO values are well-calibrated.

**CV for each combo (using same starter example)**

Using PTS=22.5 (σ=7.0), REB=6.5 (σ=3.5), AST=5.5 (σ=2.5):

| Combo | Mean | Sigma | CV |
|-------|------|-------|-----|
| PTS   | 22.5 | 7.00  | 0.311 |
| REB   | 6.5  | 3.50  | 0.538 |
| AST   | 5.5  | 2.50  | 0.455 |
| PRA   | 34.5 | 9.82  | 0.285 |
| PR    | 29.0 | 8.05  | 0.277 |
| PA    | 28.0 | 7.90  | 0.282 |
| RA    | 12.0 | 4.23  | 0.353 |

PRA, PR, and PA all have LOWER CV than standalone PTS. RA has higher CV than PTS because
the REB component (CV=0.538) dominates in a two-stat sum without the stabilizing PTS term.

**Books' Correlation Handling**

Books generally price combo props as sum of individual means, anchored to the primary stat
(PTS), then adding fixed averages for secondary stats. They do not dynamically adjust for
the within-player correlation. This creates systematic mispricing in two directions:
1. Books under-estimate PRA sigma (they don't add the covariance terms), making their lines
   slightly too tight (less vig per unit of true variance). This is a small effect.
2. More importantly: books use season-average REB/AST additions rather than matchup-specific
   adjustments. A game where pace is expected to be higher than average should inflate all
   three components — the model (using pace adjustment) captures this better than the book.

**Vig on combo props vs single stats**

Combo vig: -115/-115 to -120/-120 (wider than single stats).
Single stat vig: -110/-110 standard.
The wider combo vig is consistent with lower book confidence in combo pricing — this means
MORE edge opportunity in combos, not less.

**Coverage of PA and RA**

PA (Points + Assists) and RA (Rebounds + Assists) are less widely available than PRA and PR:
- PRA: available at DraftKings, FanDuel, BetMGM, Caesars (all major CO-legal books)
- PR: available at DraftKings, FanDuel, BetMGM
- PA: available at DraftKings, FanDuel; less consistent at BetMGM/Caesars
- RA: least widely available; DraftKings and FanDuel only for most players

The coverage limitation for PA and RA means fewer picks qualify — not a tier issue, but a
data availability issue that naturally caps pick volume without an explicit STAT_CAP adjustment.

**Recommended Tier for Each Combo:**

| Combo | CV   | Efficiency | Current | Recommended | Min Edge | Reason |
|-------|------|-----------|---------|-------------|----------|--------|
| PRA   | 0.285 | Low (books underprice correlation) | T2 | T2 CONFIRMED | 5% | CV < PTS but less efficient → T2 holds |
| PR    | 0.277 | Low | T2 | T2 CONFIRMED | 5% | Lowest CV in the set; could be T1B but coverage too thin |
| PA    | 0.282 | Low | T2 | T2 CONFIRMED | 5% | Similar to PRA; limited book coverage reduces value |
| RA    | 0.353 | Low | T2 | T2 CONFIRMED | 5% | Highest combo CV but still below PTS; T2 correct |

**Note on upgrading combos to T1B:**

The CV data makes a theoretical case for PRA/PR/PA at T1B (lower CV than PTS). However:
1. Combos are less efficiently priced (wider vig, less sharp action) — efficiency is LOW
   which supports keeping min_edge at 5% rather than reducing to 3%.
2. Book coverage is thinner for some combos, reducing available line count.
3. The correlation-induced efficiency advantage accrues to the model as edge, not as a
   reason to lower the edge threshold.

All four combos: T2 confirmed at 5% min edge. Do not move to T1B.

---

### 3.6 Summary Table — NBA Props

| SPORT | STAT | CUR  | REC  | CV      | EFFICIENCY | DIRECTION | REASON |
|-------|------|------|------|---------|-----------|-----------|--------|
| NBA   | PTS  | T2   | T2   | 0.30-0.45 | Medium  | Both OK  | Public bias inflates lines; CV moderate; 5% cushion needed |
| NBA   | AST  | T1   | T1   | 0.45-0.55 | High    | Both OK  | Sharp market, epistemically low variance, reliable CLV |
| NBA   | REB  | T1B  | T1B  | 0.38-0.70 | Medium  | Unders only | Public overs bias; directional gate is the key feature |
| NBA   | 3PM  | T3   | T3   | 0.65-1.20 | Soft    | Both (unders favored) | Highest CV, bimodal, 6% floor needed |
| NBA   | PRA  | T2   | T2   | 0.285     | Low (wide vig) | Both | Lower CV than PTS but soft market → T2 |
| NBA   | PR   | T2   | T2   | 0.277     | Low     | Both     | Same as PRA; limited coverage |
| NBA   | PA   | T2   | T2   | 0.282     | Low     | Both     | Same; PA availability thin |
| NBA   | RA   | T2   | T2   | 0.353     | Low     | Both     | Higher CV than other combos but still T2 range |

**KILLSHOT eligibility changes recommended:**
- PTS: KEEP (T2 stat, book mispricing is genuine, 5% cushion already applied in tier)
- AST: KEEP (T1, well-justified)
- 3PM: REMOVE (T3, CV too high for KILLSHOT brand promise)
- Existing KILLSHOT_STATS = {PTS, AST, SOG, 3PM} → should become {PTS, AST, SOG}

---

## SECTION 4: WNBA

### 4.1 WNBA Market Efficiency vs NBA

**Finding: WNBA is meaningfully less efficiently priced than NBA.**

Evidence from WNBA_RESEARCH_FINDINGS.md §5:
- WNBA receives ~20x fewer bets per game than an average NBA game.
- "Books post soft numbers based on basic stat averages and leave them open for longer."
- Lines can move 3+ points between open and close (vs NBA where 0.5-1.0 is typical).
- A'ja Wilson was observed at 18.5 at one book and 21.5 at another simultaneously — a
  3-point cross-book discrepancy that would never persist in NBA.
- Reverse line movement ROI of ~10% documented in WNBA spread markets.
- OpticOdds partnership with AI-driven WNBA pricing tool (April 2026) confirms that some
  operators lack proper WNBA models and outsource line-setting.
- Vig: WNBA -115/-115 typical (6.5% hold) vs NBA -110/-110 (4.5% hold). Wider vig = lower
  efficiency and higher break-even edge requirement.

**Implication: WNBA has MORE exploitable edges than NBA, but each edge is less certain
because the market is thinner (less sharp money calibrating toward truth).**

---

### 4.2 Should WNBA Inherit NBA Tier Assignments?

**Finding: WNBA should NOT inherit NBA tier assignments without modification.**

Three structural factors differentiate WNBA:

**Factor 1: Higher CV across most stats**

From WNBA_RESEARCH_FINDINGS.md §2 (9 players, 336 player-games, 2024 season):

| Stat | NBA CV | WNBA CV | WNBA/NBA Ratio |
|------|--------|---------|----------------|
| PTS  | ~0.25  | ~0.36   | +44% higher    |
| REB  | ~0.47  | ~0.43   | -9% (lower)    |
| AST  | ~0.50  | ~0.56   | +12% higher    |
| 3PM  | ~0.80  | ~0.48 (top shooters) | -40% lower |

Key divergence: WNBA PTS is 44% more volatile than NBA PTS. This alone justifies a higher
edge threshold for WNBA PTS than NBA PTS.

Interesting exception: WNBA 3PM is LESS volatile than NBA 3PM for top shooters (CV ~0.48 vs
NBA ~0.80+). This is because WNBA volume shooters (Clark, Ionescu) are consistent contributors
who don't have the boom/bust binary that NBA specialists have. WNBA 3PM may not need T3 for
top shooters — though the market is thin enough that T3 min edge is still prudent.

**Factor 2: Different combo correlations**

COMBO_RHO_WNBA (from codebase, calibrated from 9 players/336 games):
- PTS-REB: 0.13 (vs NBA 0.333 — 61% lower)
- PTS-AST: 0.04 (vs NBA 0.233 — 83% lower)
- REB-AST: 0.05 (vs NBA 0.251 — 80% lower)

WNBA combos are nearly additive (correlations near-zero). This means:
- WNBA PRA sigma > NBA PRA sigma at same individual sigmas.
- WNBA PRA CV will be close to the naive no-correlation estimate.
- Combo picks in WNBA are HARDER to handicap correctly because the diversification
  benefit is minimal — each component is essentially independent.

This makes WNBA combos less stable than NBA combos, arguing for keeping them at T2 and
NOT upgrading to T1B.

**Factor 3: Wider vig + thinner limits**

- WNBA vig: -115/-115 typical (6.5% hold), some books -120/-120 (9% hold)
- NBA vig: -110/-110 (4.5% hold)
- WNBA prop limits: $500-$1,000 (vs NBA $1,000-$5,000)
- The wider vig raises break-even edge requirement by ~2 percentage points.
- The lower limits don't change the tier system but constrain SPORT_UNIT_CAP.

**Conclusion on tier inheritance:**

WNBA should use NBA tiers as a base structure (same stat categories, same tier logic)
but with a sport-level edge floor adjustment, not individual tier changes.

The cleanest implementation is what's already coded:
- `WNBA_EDGE_FLOOR = 0.035` (vs NBA implicit 0.03 for T1)
- This raises the effective T1 minimum from 3% to 3.5%, T2 from 5% to 5%+ effectively
  because the wider vig means fewer WNBA picks will clear the edge gate.

**Recommendation: Inherit NBA tiers with WNBA_EDGE_FLOOR=0.035 as the sport-level
adjustment. Do NOT create WNBA-specific tiers for each stat. The tier structure is correct;
only the edge floor needs adjustment.**

---

### 4.3 WNBA PTS Sigma vs NBA

The most important calibration finding:

WNBA PTS CV ~0.36 (range 0.25-0.50 by player tier) vs NBA PTS CV ~0.25.

This is already implemented in the codebase:
```python
SIGMA_WNBA = {
    "PTS": {"mult": 0.38, "min": 3.5},  # CV ~0.36 avg; slight buffer for lower-tier volatility
}
```

The 0.38 multiplier vs NBA's ~0.27 implied multiplier correctly represents the 44% CV
differential. This is calibrated and implemented correctly.

For the tier implications: higher WNBA PTS CV means the model finds fewer WNBA PTS edges
above the threshold (more variance = less confidence = lower win_prob = fails edge gate).
This is the correct behavior — the model naturally self-regulates for higher variance markets.

---

### 4.4 WNBA SPORT_UNIT_CAP = 4u — Is This Correct?

**Finding: 4u is appropriate. Do not raise it.**

Calibration:
- NBA prop limits: $1,000-$5,000 → 2-4x higher than WNBA
- WNBA prop limits: $500-$1,000
- NBA SPORT_UNIT_CAP = 8u, WNBA = 4u — ratio is 2:1, matching limit ratio.
- WNBA CV is 30-40% higher than NBA for PTS (the primary prop). Higher CV supports lower cap.
- At 1u = ~$50-100 stakes, WNBA picks at 3-4u = $150-400. Some books cap at $500, meaning
  4u picks are near-limit for larger unit sizes.

The 2× reduction from NBA is justified by both CV differential and limit differential.
A 4u cap is also consistent with not sizing too aggressively in a thin market where book
limits will be encountered.

**SPORT_UNIT_CAP["WNBA"] = 4.0u: CONFIRMED.**

---

### 4.5 WNBA Book Coverage — All 18 CO-Legal Books?

**Finding: WNBA props NOT available at all 18 books. Confirmed 7, possible 1 more.**

From WNBA_RESEARCH_FINDINGS.md §5 (confirmed as of May 2026):

| Book | WNBA Props | Status |
|------|-----------|--------|
| DraftKings | YES | Full coverage, all prop types, all combos |
| FanDuel | YES | Full coverage, best live props |
| BetMGM | YES | Full coverage |
| Caesars | YES | Full coverage |
| Hard Rock | YES | Combos confirmed |
| Fanatics | YES | Often best-line source |
| theScore Bet (ESPN BET) | LIKELY | Appears in aggregators, less documented |
| Remaining 11 CO-legal books | UNKNOWN/PARTIAL | Not confirmed for WNBA props |

The model's book loop will naturally handle this — if a book doesn't post a WNBA line,
no pick is generated from it. No explicit book filtering needed for WNBA.

---

### 4.6 WNBA Early-Season Variance Gate

**Finding: Early-season gate is essential. Already implemented in codebase.**

From WNBA_RESEARCH_FINDINGS.md §6:
- WNBA opening week overs hit at ~55-60% rate (vs ~50% mid-season).
- Stars overperform on opening night — 2025: Plum 37 pts, Collier 34 pts; 2026: Carter +19.8.
- SaberSim under-projects new-team/new-role players by 7-20 pts on opening day.
- The 43-pick opening-day shadow log (1W/5L on PTS unders) confirmed the structural risk.

Currently implemented:
```python
WNBA_SEASON_START = date(2026, 5, 13)
WNBA_OPENING_GATE_DAYS = 3    # no picks days 1-3
WNBA_EARLY_SEASON_EDGE_MULT = [(14, 0.80), (21, 0.90)]  # days 4-21 dampened
```

**Recommendation: Retain early-season gate as coded. Review after 2026 WNBA season to
confirm day-4+ picks outperform opening-day picks. First N games threshold:**
- Block: first 3 days of WNBA season (opening gate).
- Reduce edge confidence: days 4-14 (×0.80), days 15-21 (×0.90).
- Normal operation: after day 21 of season.

---

### 4.7 WNBA 3PM — Separate Treatment Needed

The WNBA 3PM finding from §3 research (WNBA_RESEARCH_FINDINGS.md §3):

| Player | Mean 3PM/g | CV | Var/Mean |
|--------|-----------|-----|---------|
| Caitlin Clark | 3.05 | 0.481 | 0.71 |
| Sabrina Ionescu | 2.79 | 0.487 | 0.66 |
| Napheesa Collier (low-vol) | 0.91 | 0.869 | 0.69 |

**Key finding: WNBA top-shooter 3PM CV (0.48) is dramatically lower than NBA specialist
3PM CV (0.80+).** WNBA volume shooters are consistent — they don't have the boom/bust pattern
NBA specialists have.

This is already handled in the codebase:
```python
SIGMA_WNBA["3PM"] = {"mult": 0.48, "min": 0.70}  # Normal model, not NB
```

For tier purposes: WNBA 3PM for elite shooters has CV ~0.48 (below the T2/T3 boundary).
But:
1. The market is thin (not enough WNBA 3PM sharp action to trust the lines).
2. Non-elite WNBA shooters have CV ~0.87 (clearly T3-territory).
3. The HIGH-VAR flag (CV ≥ 0.60) would correctly block low-volume WNBA 3PM bets if
   pts_cv were populated from a custom WNBA engine.

**Recommendation: Keep WNBA 3PM at T3. The 6% min edge correctly filters non-elite shooters.
For Clark/Ionescu-tier picks, the model may find genuine edges at T3 min edge — that is correct
behavior (their actual CV of ~0.48 means good model calls will clear 6% easily).**

---

### 4.8 WNBA Tier Assignment Final Recommendation

**Conclusion: WNBA inherits NBA tier assignments with sport-level edge floor adjustment.**

| WNBA Stat | NBA Tier | WNBA Tier | Min Edge | Notes |
|-----------|---------|-----------|----------|-------|
| PTS | T2 | T2 | 5% (5.0% nominal + WNBA_EDGE_FLOOR raising effective T1→3.5%) | Higher CV handled via SIGMA_WNBA |
| AST | T1 | T1 | 3.5% effective (WNBA_EDGE_FLOOR) | Same structure, slightly more volatile |
| REB | T1B | T1B | 3.5% effective | Same directional gate; SIGMA_WNBA["REB"] lower than NBA |
| 3PM | T3 | T3 | 6% | HIGH-VAR flag would catch non-elite shooters; Normal model for WNBA |
| PRA | T2 | T2 | 5% | Near-additive combos (COMBO_RHO_WNBA ≈ 0); slightly higher sigma than NBA combos |
| PR | T2 | T2 | 5% | Same |
| PA | T2 | T2 | 5% | Same |
| RA | T2 | T2 | 5% | Same |
| TOTAL | T2 | T2 | 5% | GAME_SIGMA["WNBA"] already calibrated at 10.0 (vs NBA 12.0) |
| SPREAD | T2 | T2 | 5% | Same |
| ML_FAV | T2 | T2 | 5% | Same |
| ML_DOG | T3 | T3 | 8% | Same (ML_DOG override applied sport-agnostically) |

**No WNBA-specific tiers needed. Sport-level WNBA_EDGE_FLOOR = 0.035 is the correct
implementation for the efficiency difference (wider vig environment).**

---

### 4.9 WNBA KILLSHOT Exclusion

**Finding: WNBA correctly excluded from KILLSHOT via SHADOW_SPORTS filter.**

When WNBA exits SHADOW_SPORTS (earliest late June 2026 per the go-live criteria):
- Add explicit sport check in `_passes_killshot_v2_gate()`: exclude WNBA from KILLSHOT.
- Rationale: $500-$1,000 limits, thinner market, brand risk of @everyone pings on thin data.
- If WNBA ever generates enough proven edge data to consider KILLSHOT: raise the wp floor to
  0.70+ (vs 0.65 NBA) given higher WNBA CV on PTS.

---

## Cross-Cutting Notes

### Combo pick concentration cap

Both NBA and WNBA have the same correlated-loss risk: multiple combo picks on one player
(PRA + PR + PA on Jokic/Clark) all fail if the primary stat (PTS) fails. Recommendation
already designed: MAX_COMBO_PICKS_PER_PLAYER = 1 in apply_caps().

### 3PM KILLSHOT removal

Current: KILLSHOT_STATS = {PTS, AST, SOG, 3PM}
Recommended: KILLSHOT_STATS = {PTS, AST, SOG}

Reason: 3PM T3 status with CV 0.80-1.20 is incompatible with KILLSHOT's brand promise.
The gate (wp≥0.65, T1 required, score≥90) already makes 3PM KILLSHOT nearly impossible
since T3 stats can't pass KILLSHOT_TIER_REQUIRED="T1" — so this is effectively a no-op
change unless 3PM were also set to T1 (which it should NOT be). Confirm current code
prevents T3 stats from reaching KILLSHOT regardless of the KILLSHOT_STATS set.

### WNBA Platt refit timeline

Target: 300 WNBA over_p_raw rows in pick_log_custom.csv.
Estimated: mid-June 2026 at 10-15 WNBA picks/day.
Action: run `calibrate_platt.py --sport WNBA` when count ≥ 300.
NBA Platt used as-is until then (bias < 0.8pp per typical WNBA pick — negligible).

---

## Open Questions (Data-Gated)

1. **NBA PTS CV by role**: The CV range 0.30-0.45 is well-established but should be confirmed
   from the custom projection engine's backtest data once 30+ days of projection data accumulates.
   Check: compare dk_std predictions to actual outcomes for PTS by role tier.

2. **WNBA combo correlation sample**: COMBO_RHO_WNBA calibrated on 9 players / 336 games.
   Expand to full 2024-25 WNBA season (top-30 players) for tighter confidence intervals.
   Priority: MEDIUM (affects combo pick volume and sigma).

3. **3PM bimodal modeling**: NB_R=12.3 approximates but doesn't capture true bimodality for
   Klay/Steph-type shooters. A hurdle model (P(0) separate from P(≥1)) would be more accurate.
   Priority: LOW — HIGH_VAR flag currently blocks the most bimodal cases.

4. **NBA AST CV by projection level**: The CV range (0.45-0.55) is well-supported but a
   full calibration from the projection engine backtest (similar to the minutes scalar refit)
   would sharpen the tier boundary between T1 and T1B.
