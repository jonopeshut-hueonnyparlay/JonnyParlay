# EdgeModel Foundations — Projection Architecture (Plan 7)
# Last validated: 2026-06-06
# All values verified against EdgeModel/engine/nba_projector.py (1,914 lines) on 2026-06-06
# Research model: claude-opus-4-8 with web search (one research agent per section)

---

## HOW TO USE THIS DOCUMENT

Before changing any projection-architecture decision, constant, or methodology
in EdgeModel/engine/nba_projector.py:
1. Find the relevant section below.
2. Read the VERDICT and the Condition to Revisit.
3. Provide evidence that the condition is met before making any change.

If a NEEDS_CHANGE verdict exists, that section's change has priority.

Audit methodology: every constant below was read from source on 2026-06-06
(not assumed from docs); each section was researched by a dedicated
claude-opus-4-8 agent with mandatory web search; every verdict cites at least
one published source. Companion doc: docs/research/STATISTICAL_FOUNDATIONS.md
(Plan 6 — run_picks.py distributions and market math).

---

## VERDICT SUMMARY

| § | Topic | Verdict |
|---|---|---|
| 7A | EWMA recency weighting + per-stat spans | MIXED — EWMA form LOCKED; spans PERIODIC_RECAL; **STL/BLK span=8 NEEDS_CHANGE (should be ~18-25)** |
| 7B | Role-specific minute scalars | MIXED — scalars PERIODIC_RECAL; **spot=1.6124 NEEDS_CHANGE (structural)**; cold-start PO DATA_GATED; OT cap LOCKED |
| 7C | Vegas team-total constraint | MIXED — architecture LOCKED; **AST not Vegas-anchored NEEDS_CHANGE (move AST to _base_pf)** |
| 7D | Stat scalars + playoff deflators | MIXED — multiplicative form LOCKED; values PERIODIC_RECAL; **BLK=1.152 DATA_GATED (likely ~1.05; do NOT lock — C01 confirmed)** |
| 7E | DK_STD model + HIGH_VAR flag | MIXED — coeff 0.35 + Vegas-scaling exclusion LOCKED; floors PERIODIC_RECAL; CV flag NEEDS_RELABEL (statistic kept) |
| 7F | 3PM architecture post-PAD_3P | CONFIRMED — −0.26 "shared bias" is ~⅔ frame mismatch, ~⅓ real (minutes + EWMA trend-lag); scalar compensation correct form; PAD_3P=242 verified |
| 7G | Stat-specific blend alphas | LOCKED — all four alphas + architecture; flat loss surface under high error correlation; offseason refits NOT recommended |
| 7H | Position-specific AST EWMA spans | **NEEDS_CHANGE** — span ordering inverts sampling principle (same error as STL/BLK); fix: uniform span=13 or invert+lengthen |
| 7I | EWMA_SPAN_SHOOTING + OT_MIN_CAP | MIXED — USG%/FG3A-rate/FT% spans + OT cap LOCKED; **FG% span-10 NEEDS_CHANGE (P3, test-gated: PAD_FG≈103)** |

---

## LOCKED ASSUMPTIONS
*These should not change unless the sport or model architecture fundamentally changes. "Feeling" is not sufficient to change them.*

| Assumption | Value | Source(s) | Condition to Revisit |
|---|---|---|---|
| EWMA functional form (vs Kalman/ridge/GP) | per-stat EWMA + Bayesian blend | Hyndman SSOE (EWMA = steady-state Kalman); DARKO uses per-stat exp decay | Published NBA head-to-head showing Kalman/GP beats tuned exp decay (none exists) |
| span→α = 2/(span+1) | pandas convention | pandas.DataFrame.ewm docs | Never |
| FG3M span=10 + shooting span=10 (except FG%) | 10 | Miller & Sanjurjo hot-hand; Medvedovsky padding table (USG 72 poss, FG3A-rate 3.6 FGA, FT% 24 FTA) | FG3A-rate responsiveness issue post-trade |
| Minutes span=8 | 8 | Minutes shifts are coach decisions (regime changes), not noise — kmedved | — |
| OT_MIN_CAP=44.0 | 44.0 | OT ~5.9% of games, +0.3 min EV; 6+ min above league MPG leader (37.6) | NBA OT format change, or any projected mean >42 |
| Vegas total as pace prior (`_base_pf`) | implied_total / LEAGUE_AVG_TOTAL | Štrumbelj & Robnik-Šikonja 2010; Sauer 1998; closing-line absence studies | Model's own totals beat Vegas on Brier at n≥200 (don't expect it) |
| STL/BLK on historical pace (NOT Vegas) | ^0.30 each | Oliver pace/efficiency separation — Vegas total confounds pace with efficiency | Possession-specific market signal becomes available |
| Lineup-protected 240-min reconciliation | top-5 immutable | Zhang et al. 2023 immutable-forecast reconciliation; MinT variance-weighting logic | Starter proj_min MAE exceeds bench MAE in season-scale backtest |
| Dual-path playoff scalar (Vegas path skips ×0.963) | — | Market prices embed playoff pace; double-count otherwise | Never |
| Multiplicative (vs additive) stat-scalar form | proj × scalar | Mincer-Zarnowitz decomposition; zero-bounded bias-correction practice | MZ intercept \|t\|>2 for any stat at next refit |
| Blend alphas PTS=0.50 / REB=0.45 / AST=0.40 / FG3M=0.65 | as listed | Forecast combination puzzle (Smith & Wallis 2009; Elliott 2011) — loss surface flat, refits are churn | Structural change to either path; path decorrelation; blended MAE loses to best single path |
| Two-path blend architecture | decomp + baseline | Bates & Granger 1969; Clemen 1989; RotoGrinders two-projection practice | — |
| DK_STD_COEFF=0.35 | 0.35 | Implies NB r≈8.2, matching engine's own fits; published CV range 0.28–1.1 | League scoring shift moves implied r outside ~6–10 |
| dk_std excluded from 240-min scaling | — | NB variance falls slower than μ²; minutes squeezes add rotation uncertainty | Never |
| PAD_3P=242, career-to-date | 242.0 | Medvedovsky 2020 primary source (242.61); supersedes Blackport 750 | Consider decayed-attempts denominator for >2,000 career 3PA + talent change |
| Single playoff deflator across rounds | — | Round effects unidentifiable at n=1,071 | Pooled playoff n≥3,000 |

---

## PERIODIC RECALIBRATION
*Correct methodology. Parameter values should be updated each offseason (or per the stated frequency).*

| Assumption | Current Value | Method | Notes |
|---|---|---|---|
| Per-stat EWMA spans (PTS/REB/AST/TOV) | 15/12/13/10 | DARKO-style: optimize per-stat decay vs rest-of-season MAE on 3-season backtest | Only deploy changes >0.5% MAE improvement; differences in 12–15 range likely immaterial |
| Role minute scalars (RS + PO, non-spot) | starter 1.0667/1.075 etc. | actual/projected ratio per tier | Refit after ANY change to EWMA span, tier thresholds, or sampling frame |
| REGULAR_SEASON_STAT_SCALAR | pts 1.0019 … blk 1.0608 | ratio of means | **Add split-half temporal holdout** (current "bias≈0" is tautological) + per-stat MZ intercept test; fix comment/fit-basis docs (AST/BLK comment arithmetic inconsistent) |
| PLAYOFF_RATE_DEFLATORS pts/ast/fg3m | 0.934/0.845/0.948 | playoff backtest ratio | Refit at ≥2 pooled postseasons (~2,500 player-games); check Vegas-total efficiency double-count (PTS expected to drift toward ~0.97) |
| DK_STD_FLOOR | 4.0/4.0/3.5/3.0/3.0 | regress \|error\| on projection by role | Rotation/spot floors look ~1–2 pts low vs MAE-implied σ; harmless while informational |
| LG_FG3A_RATE | 0.420 | league 3PA/FGA from B-Ref | Verify exact 2025-26 figure at July refit; adjust if \|Δ\|>0.01 |
| FG3M stat scalar drift | 1.0231 | — | Expect +1–2%/season drift while league 3PA rises; if flat-3PA league and scalar still rising → different mechanism, investigate |

---

## DATA-GATED
*Correct methodology. Waiting for enough data to finalize parameters.*

| Assumption | Current Value | Gate | Notes |
|---|---|---|---|
| PLAYOFF_RATE_DEFLATORS BLK (C01) | 1.152 — **do NOT lock** | Per-possession decomposition + leave-one-player-out (exclude >2 BPG) before 2027 playoffs | League per-possession playoff block rate ≈ flat (+1–3%); defensible value ≈1.04–1.06; 95% CI [1.04, 1.26] from single postseason likely dominated by Wembanyama (5.6 BPG). If LOPO <1.10 → shrink to ~1.05 |
| COLD_START_PLAYOFF_SCALAR | taxi/ext_abs 0.400, returner 0.700, new_acq 0.750 | n≥50 playoff cold-start player-games | Direction matches rotation compression (7–9 players); taxi/ext_abs likely still over-projects (modal outcome = DNP) but priced exposure ≈0. If >40% DNP rate → replace 0.400 with play-probability gate |
| HIGH_VAR flag behavioral use | CV≥0.60, n≥8 (informational) | If G15 ever becomes blocking | Raise HIGH_VAR_MIN_GAMES to ≥20 + add 2-window persistence first; CV at n=8 carries ±33% relative SE |

---

## NEEDS_CHANGE (priority order)

| # | Item | Section | Problem | Fix | Gate/Priority |
|---|---|---|---|---|---|
| 1 | **STL/BLK EWMA span=8** | 7A | Logic inverted: lowest-frequency stats stabilize slowest and need the LONGEST spans; at span=8 the STL estimate is ~50% noise (sampling SD ≈0.37 rivals between-player talent SD ≈0.4) | Grid-search spans {8,12,15,20,25} on existing 30-date backtest harness; expect optimum 18–25; or equivalently heavier Bayesian-prior weight | Next backtest window with ≥1,500 STL/BLK rows (July refit). Low downside risk |
| 2 | **_AST_EWMA_SPAN position table** | 7H | Same inverted-sampling error as #1, per position: noisiest position (C, span=5) gets least smoothing; deployed reality is flat {guards 8, SF/PF 6, C 5} — ALL below generic span 13 (PG cell is dead code, API never assigns PG) | (a) Delete table, use uniform span=13 (simplest); or (b) invert+lengthen: guards ≈13, SF/PF ≈15, C ≈18–20. Validate per-position AST MAE on 30-date backtest. Evaluate jointly with AST_ALPHA=0.40 | July refit. Severity moderated by AST_ALPHA down-weighting (60/40 toward baseline) |
| 3 | **AST not Vegas-anchored** | 7C | AST mechanically coupled to made FGs (AST/FGM ≈0.60–0.63 stable) → implied scoring-environment elasticity ≈0.7–0.9, current design assigns 0; ~0.25–0.45 AST systematic miss on 8% Vegas-vs-pace divergence; incoherent with COMBO_RHO_PTS_AST=0.233 downstream | One-line change: AST joins the pts/fg3m/reb `_base_pf` branch at its existing ^0.50 elasticity; consider ^0.70 at next refit | Backtest-gated: bucket graded AST props by Vegas-vs-pace divergence quintile; ship if top-vs-bottom bias spread >0.15 AST |
| 4 | **RS spot minute scalar = 1.6124** | 7B | Band-aid over incidental truncation (Heckman-class selection): spot players priced only on real-role nights while EWMA averages DNP-adjacent games; PO 0.948 vs RS 1.612 sign flip confirms scalar encodes sample composition, not role behavior | Root fix: exclude games <10 min from spot-tier EWMA (industry standard) or two-stage hurdle model. At next refit, fit both ways; if filtered-EWMA scalar drops below ~1.30, selection mechanism confirmed — replace scalar with filtered input | Next RS scalar refit. Interim value may stand (empirically calibrated, CI excludes 1.0) |
| 5 | **FG% on span-10 EWMA (no padding)** | 7I | FG% stabilizes at ~103 FGA ≈ the span-10 window's entire volume → unshrunk EWMA FG% is ~50% noise vs empirical-Bayes optimum | Apply the PAD_3P pattern: PAD_FG≈103 FGA (PAD_2P≈127) career-padded blend on the PTS decomp path | P3, test-gated at July refit: deploy only on PTS MAE improvement (3P% precedent says shared-path bias may dominate — then mark LOCKED and close) |
| 6 | **HIGH_VAR flag mislabeled** | 7E | CV measures dispersion, not bimodality; "bimodal 3PT specialist" label overstates what the statistic detects | Rename to high-variance flag (comment/docs only); keep CV statistic — dip test/BC are powerless at n=8 | Cosmetic; bundle with next nba_projector.py edit |
| 7 | **evaluate_projector.py frame mismatch** | 7F | The −0.26 "shared 3PM bias" headline is ~⅔ measurement artifact: scalar arithmetic (1.0365×1.0231 ≈ 1.06 lift on 1.34 mean ≈ −0.08) cannot produce −0.26; the extra ~−0.18 is frame/selection disagreement vs the production backtest (likely conditioning on realized outcomes) | Align evaluate frame with production (same population, scalars toggleable); add log-space minutes×rate bias decomposition | Diagnostic, not a model change. If shared bias remains ≤−0.20 after alignment, selection hypothesis falsified — escalate |

---

## SECTION DETAIL

---

## SECTION 7A — EWMA as the Recency Weighting Method

**Question:** Is EWMA the right functional form for daily NBA player projection vs Kalman/state-space, ridge-toward-prior, or GP alternatives? Are the per-stat spans (PTS=15, REB=12, AST=13, FG3M=10, STL/BLK=8, TOV=10, shooting=10, minutes=8) consistent with published stabilization literature? Is span→α=2/(span+1) standard? Critically: does span=8 on low-frequency STL/BLK amplify noise?

**Code ground truth:** `EWMA_SPAN_STAT` in `engine/nba_projector.py` applies per-stat pandas-style EWMA (α=2/(span+1)) to per-minute rates, multiplied by projected minutes, then role scalars, blend paths, and bias scalars. Spans: pts 15, reb 12, ast 13, fg3m 10, stl 8, blk 8, tov 10; shooting rates 10; minutes 8. Effective half-lives: span 15 → 5.2 games, span 10 → 3.5 games, span 8 → 2.8 games.

**Findings:**

1. **EWMA is mathematically a special case of the Kalman filter, not a competitor to it.** The steady-state Kalman filter for the local-level (random-walk-plus-noise) state-space model reduces exactly to simple exponential smoothing with smoothing constant α = steady-state Kalman gain ([Hyndman et al., "The Case for the Single Source of Error State Space Approach," Monash/robjhyndman.com](https://robjhyndman.com/papers/SSOE.pdf); [Duran-Martin, "A robust exponentially-weighted moving average," grdm.io, 2023](https://grdm.io/posts/wolf-ewma/)). The practical difference is only that a full Kalman filter adapts its gain when observation uncertainty varies (e.g., a 4-minute garbage-time game vs a 38-minute game) and during burn-in; a fixed-α EWMA does not. EdgeModel's separate Bayesian-prior blend and cold_start tier system partially substitutes for the adaptive-gain behavior.

2. **The closest published NBA analog — DARKO (Medvedovsky) — is literally per-stat exponential decay plus a Kalman/regression layer.** DARKO ("Daily Adjusted and Regressed Kalman Optimized") weights every past game by β^t (t in days), with **β optimized separately for each box-score stat** via differential evolution, then layers Bayesian/Kalman regression and cross-stat correlation updating on top ([NBAstuffer, "DARKO (DPM) Explained"](https://www.nbastuffer.com/analytics101/darko-daily-plus-minus/); [darko.app](https://www.darko.app/); [The Power Rank podcast with Medvedovsky, 2022](https://thepowerrank.com/2022/05/27/podcast-kostya-medvedovsky-on-the-darko-nba-player-projections/)). So per-stat exponential decay is the published state of the art's own recency core; EdgeModel's structure (per-stat EWMA → Bayesian prior blend → bias scalars) is a recognizable simplification of it. Two structural differences worth noting: DARKO decays in **calendar days** (so layoffs decay information; a game-indexed EWMA treats a game 3 days ago and 3 weeks ago identically if both are "3 games back"), and DARKO's decay constants are **empirically optimized**, not hand-set.

3. **Full Kalman filtering is also used in production by sportsbook/DFS operators**, e.g., DraftKings Engineering's published player-rating system ([Barnes, "Kalman Filters For NBA Player Ratings," DraftKings Engineering on Medium](https://medium.com/draftkings-engineering/kalman-filters-for-nba-player-ratings-d3bb9365221b)), and state-space skill tracking goes back to [Glickman & Stern, "A State-Space Model for National Football League Scores," JASA 1998](https://www.glicko.net/research/nfl-chapter.pdf) (AR(1) team strengths, Kalman-style updating). No published head-to-head shows Kalman materially beating a well-tuned EWMA-plus-prior for daily box-score projection; the documented advantages are adaptive uncertainty and principled handling of uneven samples. Practitioner DFS guidance likewise treats decay-weighted recent games over per-minute rates as best practice ([Quadratic, "NBA DFS Projections"](https://www.quadratichq.com/use-cases/nba-dfs-projections-crafting-accurate-player-values)).

4. **span→α = 2/(span+1) is confirmed as the standard pandas parameterization.** Pandas defines span decay as α=2/(span+1), span≥1, alongside com (α=1/(1+com)) and halflife forms ([pandas.DataFrame.ewm documentation](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.ewm.html)). No issue.

5. **Per-stat span differentiation is directionally supported, but the specific values have no direct literature anchor — and the STL/BLK ordering inverts the stabilization literature.** Medvedovsky's stabilization/padding study (differential evolution over ~750K player-game rows) found minutes are the *most* stable quantity (coach-controlled), 3P% needs ~242 attempts (~40+ games of volume) before performance is mostly signal ([Medvedovsky, "NBA Stabilization Rates and the Padding Approach," kmedved.com, 2020](https://kmedved.com/2020/08/06/nba-stabilization-rates-and-the-padding-approach/)). Franks et al.'s meta-analytics framework (JQAS 2016) found rebounds, blocks, and assists are highly *discriminative and stable* — large between-player variance relative to within-player noise ([Franks, D'Amour, Cervone & Bornn, arXiv:1609.09830](https://arxiv.org/abs/1609.09830)). Practitioner literature is explicit that "block and steal rates come with way more variance than other rate statistics (usage, assist, rebound) mainly because they happen in games far less frequently" ([RotoGrinders, "Understanding NBA Advanced Stats"](https://rotogrinders.com/lessons/understanding-nba-advanced-stats-the-core-drivers-of-dfs-expectation-3335820)). Low frequency ⇒ high sampling variance ⇒ *slow* stabilization ⇒ the optimal estimator uses a **longer** effective window (or heavier prior shrinkage), not a shorter one. The code comment "high variance, event-driven → span=8" reverses this: high *sampling* variance is noise to be averaged out, not signal to be chased. Quantified with EdgeModel's own calibration (STL var/μ=1.072, ≈Poisson at μ≈1.0/game): steady-state EWMA sampling SD = √(α/(2−α)·σ²); at span=8 (α=0.222) that is ≈0.37 steals/game — comparable to the entire between-player talent spread (~0.4 SD league-wide), i.e., the span-8 STL estimate is roughly half noise. Span=20 cuts that noise variance by ~60% (SD≈0.23). The same logic applies to BLK (var/μ=1.113), with the caveat that BLK has genuine regime shifts (role/scheme changes) and EdgeModel's PF_high BLK tier prior absorbs some of this.

6. **FG3M span=10 is defensible.** Bias-corrected hot-hand research finds real streak effects in three-point shooting (+6–8pp in Miller & Sanjurjo's corrected 3-Point Contest analyses; smaller but nonzero in-game effects) ([Miller & Sanjurjo, NBER w29468](https://www.nber.org/system/files/working_papers/w29468/w29468.pdf); [NBER w26510](https://www.nber.org/system/files/working_papers/w26510/revisions/w26510.rev1.pdf)), and 3PA *volume* is role-driven and genuinely nonstationary. Critically, EdgeModel already routes FG3M efficiency through the career-padded path (PAD_3P=242 — the exact Medvedovsky padding constant) blended at FG3M_BLEND_ALPHA=0.65, so the short-window EWMA is not the sole 3PM estimator. This division of labor (long-memory padded efficiency + moderate-recency volume) matches the literature.

7. **PTS=15 > AST=13 > REB=12 ordering is plausible but unvalidated.** No published per-game span table exists to check 15/13/12 directly; Franks et al. would, if anything, suggest REB/AST (most stable, most discriminative) tolerate *longer* spans than PTS (usage-driven, role-sensitive). The differences among 12–15 are small (half-lives 4.2–5.2 games) and almost certainly immaterial next to the minutes-projection error term, which the same DFS literature identifies as the dominant variance source. Minutes span=8 is the one *short* span the literature affirmatively supports: minutes changes are real coach decisions (regime shifts), not sampling noise, so fast tracking is correct.

**VERDICT:** Per-item table —

| Item | Verdict | Basis |
|---|---|---|
| EWMA functional form (vs Kalman/ridge/GP) | **LOCKED** | EWMA = steady-state Kalman of local-level model (Hyndman SSOE); DARKO's own recency core is per-stat exponential decay; Bayesian-prior blend covers most of full-Kalman's marginal value |
| span→α = 2/(span+1) | **LOCKED** | Standard pandas parameterization, confirmed |
| Per-stat spans PTS=15 / REB=12 / AST=13 / TOV=10 | **PERIODIC_RECAL** | Directionally consistent; never empirically optimized — DARKO precedent is to fit decay per stat via differential evolution against rest-of-season MAE; differences in this range are likely immaterial vs minutes error |
| FG3M=10 + shooting=10 | **LOCKED** (given PAD_3P=242 blend) | Hot-hand effects real (Miller & Sanjurjo); long-memory efficiency handled by career padding path; short window only governs volume/recency component |
| Minutes span=8 | **LOCKED** | Minutes shifts are regime changes (coach decisions), not noise — fast tracking is the correct response per kmedved stabilization findings |
| **STL/BLK span=8** | **NEEDS_CHANGE** | Logic inverted: lowest-frequency stats have the highest sampling variance and stabilize slowest (RotoGrinders; Franks et al.; kmedved padding framework), so they need the *longest* spans or heaviest prior shrinkage. At span=8 the STL EWMA sampling SD (≈0.37/game) rivals the league's between-player talent SD (≈0.4) — the estimator is ~50% noise. Recommend span 18–25 (grid-search 15/20/25 via the existing 30-date backtest harness), or equivalently heavier Bayesian-prior weight. Expected impact: ~60% reduction in estimator noise variance at span=20; modest Brier/MAE improvement on STL/BLK props, larger effect on tail probabilities since noisy λ feeds Poisson prop pricing in both directions. Downside risk is low — true within-season STL/BLK skill drift is small, and real role shifts are already captured through the minutes path. |

Overall section verdict: **PERIODIC_RECAL** for the architecture, with one **NEEDS_CHANGE** sub-item (STL/BLK spans).

**Condition to Revisit:**
1. **STL/BLK span fix (actionable now):** run the existing projection backtest with STL/BLK spans ∈ {8, 12, 15, 20, 25}; deploy the MAE/Brier-optimal value. Trigger: next backtest window with ≥1,500 STL/BLK player-game rows.
2. **Span optimization for remaining stats:** at the July offseason refit, replicate the DARKO approach — optimize each span (or switch to day-based decay) against rest-of-season prediction error on the 3-season backtest set; only deploy changes exceeding a 0.5% MAE improvement to avoid overfitting.
3. **Form re-evaluation (EWMA → Kalman):** revisit only if (a) cold_start/returner projection error remains materially worse than veteran error after the span refit (adaptive-gain territory), or (b) a published NBA comparison demonstrates Kalman/GP beating tuned exponential decay on box-score projection — none exists as of June 2026.

---

## SECTION 7B — Minute Projection Scalars

**Question:** Are the role-specific minute scalars (playoff + regular-season + cold-start playoff + OT cap) theoretically sound, and is RS `spot=1.6124` a calibrated patch over a structural selection problem?

**Code ground truth:** Scalars multiply an EWMA(span=8) minutes projection, fit as actual/projected ratios per role tier from backtests. `PLAYOFF_MINUTES_SCALAR` starter=1.075 / sixth_man=0.960 / rotation=0.924 / spot=0.948 / cold_start=0.400 (n=3,925). `REGULAR_SEASON_MINUTES_SCALAR` starter=1.0667 / sixth_man=1.0462 / rotation=1.0854 / **spot=1.6124** (CI [1.57,1.83]) / cold_start=1.0880 (n=4,653). `COLD_START_PLAYOFF_SCALAR` taxi=0.400 / extended_absence=0.400 / returner=0.700 / new_acquisition=0.750. `OT_MIN_CAP=44.0`.

**Findings:**

1. **Theoretical basis — the scalars are a regression/calibration correction, not a structural model, and this matches (but lags) industry practice.** Published DFS methodology uniformly identifies minutes as "the most volatile variable" while per-minute production is stable ([RotoGrinders — Projected Minutes: The Most Critical Opportunity Stat](https://rotogrinders.com/lessons/projected-minutes-the-most-critical-opportunity-stat-in-nba-dfs-3147006); [Quadratic — NBA DFS Projections](https://www.quadratichq.com/use-cases/nba-dfs-projections-crafting-accurate-player-values)). No published production system uses static role-tier multipliers on a recency-weighted mean; the industry standard is either (a) human-curated depth-chart minutes continuously updated to news ([Establish The Run NBA projections](https://establishtherun.com/draftkings-nba-projections/) — proprietary model + minutes team with intraday updates), or (b) daily Bayesian/Kalman updating per player ([DARKO](https://apanalytics.shinyapps.io/DARKO/), [DARKO explained — NBAstuffer](https://www.nbastuffer.com/analytics101/darko-daily-plus-minus/): exponential-decay weights with per-player, per-stat update gains, projecting minutes as one of its outputs). The EdgeModel approach — pooled tier-level correction factors on top of EWMA — is a coarse approximation of DARKO's per-player adaptive gain. It is empirically defensible but the correction being *systematically* >1.0 for every RS tier (1.046–1.088 even for starters) is a diagnostic that the EWMA mean is the wrong location estimator: NBA minutes distributions are left-skewed (occasional blowout benchings, foul trouble, ejections, early injury exits drag the mean below the typical healthy-game value). RotoGrinders' published methodology explicitly excludes sub-5-minute and garbage-time games from baselines rather than rescaling the contaminated mean ([Quadratic methodology](https://www.quadratichq.com/use-cases/nba-dfs-projections-crafting-accurate-player-values); [RotoGrinders — Accurately Predicting Minutes](https://rotogrinders.com/fantasy/lessons/accurately-predicting-minutes-nba-dfs)). Root cause named: the scalars are correcting input contamination, not role structure.

2. **RS `spot=1.6124` is a band-aid over a selection/conditional-distribution problem — explicitly.** The hypothesis is correct and the statistical literature names the mechanism. Spot players (5–12 trailing MPG) enter the priced/backtest sample only on nights they actually receive meaningful minutes (injury elevation, rotation change), while their EWMA averages over DNP-adjacent and garbage-time appearances. This is textbook **incidental truncation**: the outcome is observed only for a non-randomly selected subsample, the exact setting of the Heckman selection model ([Heckman correction — Wikipedia](https://en.wikipedia.org/wiki/Heckman_correction); [endogenous sample selection — Nguyen, A Guide on Data Analysis](https://bookdown.org/mike/data_analysis/sec-endogenous-sample-selection.html)). The correct structural form is a **two-stage hurdle / zero-inflated model**: P(plays meaningful minutes tonight) × E[minutes | plays], where the count component is estimated conditional on non-zero outcomes ([Two-Stage Hurdle Models — Towards Data Science](https://towardsdatascience.com/two-stage-hurdle-models-predicting-zero-inflated-outcomes/); [Zero-Inflated and Hurdle Models — UCLA OARC](https://stats.oarc.ucla.edu/wp-content/uploads/2024/03/Zero_inf_2024_2.html)). Multiplying a mixture mean by 1.61 reproduces the conditional mean *on average* but gets every individual spot player wrong in both directions: it over-projects spot players whose recent games were genuine low-minute appearances and under-projects those whose EWMA is diluted by several near-DNPs around one real role change. RotoGrinders' published warning about exactly this population — bench-minute spikes from blowouts are not role changes ([landyourbets — How to Make NBA Minutes Projections](https://landyourbets.com/how-to-make-nba-minutes-projections)) — is the editorial version of the same point. The scalar is empirically calibrated (CI excludes 1.0 decisively) and acceptable as a stopgap, but the root cause is that the EWMA input for this tier is an average over a bimodal distribution. Practical fixes, in increasing rigor: (a) exclude games <8–10 minutes from the spot-tier EWMA (industry practice), (b) hurdle model with a play-probability stage, (c) full Heckman-style selection equation. Note also the playoff spot scalar is 0.948 on n=109 — the sign flip vs RS (0.95 vs 1.61) is itself evidence the scalar is absorbing sample-composition effects rather than a stable role property.

3. **Hierarchical/Bayesian playing-time literature: thin, and nothing contradicts the current approach — but the academic toolkit exists.** Academic basketball work models *performance conditional on minutes*, not minutes themselves: Casals & Martínez (2013) used mixed-effects models with player random effects and found minutes played the dominant covariate of scoring output ([Modelling player performance in basketball through mixed models, IJPAS 13(1)](https://www.tandfonline.com/doi/abs/10.1080/24748668.2013.11868632)); hierarchical Gaussian-process work borrows strength across players of similar position/usage/minutes for career curves ([Page et al., JQAS — production curves](https://page.byu.edu/docs/files/Publications/JQASSelfArchive.pdf)); Bayesian hierarchical player metrics use minutes as exposure ([EPAA, arXiv:2405.10453](https://arxiv.org/html/2405.10453v2)). The only public system that projects minutes daily with a principled Bayesian update is DARKO (Kalman filter, exponential decay, per-player gains) ([darko.app](https://www.darko.app/); [The Power Rank podcast w/ Medvedovsky](https://thepowerrank.com/2022/05/27/podcast-kostya-medvedovsky-on-the-darko-nba-player-projections/)). There is no published peer-reviewed "hierarchical Bayes NBA minutes" model to benchmark against; EdgeModel's EWMA+scalar approach is not contradicted by literature, only dominated in principle by per-player state-space updating.

4. **COLD_START_PLAYOFF_SCALAR direction is right; taxi/extended_absence=0.400 is likely not aggressive enough, but exposure is near-zero.** Published rotation data: playoff rotations compress to 7–9 players, with 8 the typical floor ([NBA Now and Then — Eight, Maybe Nine](https://www.nbanowandthen.com/post/eight-maybe-nine-rotations-come-playoff-time); [Pace and Space — Importance of Shortened Playoff Rotations](https://paceandspacehoops.com/the-importance-of-shortened-nba-playoff-rotations/); [Striveon — NBA Bench Rotation Explained](https://joinstriveon.com/blog/nba-bench-rotation-explained): regular-season 32-MPG starters log 38–42 in series, 1–3 bench players total get regular playoff minutes). Bleacher Report's quantified check: 84 players (2.8/team) averaged 30+ MPG in the regular season vs 62 (3.9/team) in the playoffs — minutes concentrate sharply upward in the top 8 ([Bleacher Report — Which NBA Playoff Myths Are Actually True](https://bleacherreport.com/articles/2708178-nba-metrics-101-which-nba-playoff-myths-are-actually-true)). A taxi/extended-absence player is by construction outside the top 9, so the *modal* playoff outcome is 0 minutes — 0.400× a low EWMA still projects positive minutes for players whose true expectation is a DNP-CD. This is the same conditional-distribution problem as item 2 (the scalar approximates a mean over {DNP, garbage time}). Mitigants: such players are almost never priced by books, and returner=0.700/new_acquisition=0.750 are consistent with documented minute-restriction ramp behavior on injury returns ([SI — Zion Williamson minutes restriction](https://www.si.com/nba/2020/01/23/zion-williamson-adam-silver-pelicans-minutes-restriction)).

5. **OT_MIN_CAP=44.0 is reasonable for a pre-game projection cap; OT is correctly treated as noise, not signal.** NBA overtime frequency is stable at ~5.9–6.3% of games ([Binomial Basketball — Probability of NBA overtime](https://www.binomialbasketball.com/p/probability-of-nba-overtime-over): 5.9% over 24 years, CI 5.6–6.1%; recent seasons 6.2–6.4%; 6.26% of games tied at end of regulation per [82games](https://www.82games.com/random21.htm)). Each OT adds 5 minutes ([NBA Rule 5](https://official.nba.com/rule-no-5-scoring-and-timing/)), and multi-OT games are an order of magnitude rarer still. Expected-value OT contribution to a heavy starter's projected minutes ≈ 0.063 × 5 × (starter OT share ~0.8–0.9) ≈ **+0.25–0.30 min** — well inside projection sigma; explicitly modeling it is immaterial. The 44.0 cap applies to the *projected mean*, which for even the most extreme workloads tops out around 40–42 expected minutes (2026 playoff per-game leader: 44.0 actual MPG — the cap binds only at the absolute playoff extreme, which is the correct behavior for a mean). Single-game actuals of 50+ in 2OT/3OT are realizations, not expectations, and do not argue for a higher cap on a pre-game mean. One nit: the cap's comment ("covers overtime") mislabels its function — it is a sanity ceiling on projected means, not an OT allowance.

**VERDICT:** per-item —

| Item | Verdict | Rationale |
|---|---|---|
| Role-scalar architecture (RS + PO, starter/sixth_man/rotation) | **PERIODIC_RECAL** | Empirically fit, consistent with published rotation-shortening and minutes-volatility findings; values are sample-dependent regression corrections, not constants. Refit each season and after any EWMA/tier-definition change. |
| RS `spot=1.6124` | **NEEDS_CHANGE** (structural; current value may stand as interim) | Explicitly a band-aid: corrects a selection/incidental-truncation problem (Heckman-class) and a bimodal conditional-minutes distribution (hurdle-class) with a single mean multiplier. Root fix: exclude sub-threshold-minute games from spot-tier EWMA (cheap, industry-standard) or two-stage hurdle model (correct). The 0.948 (PO) vs 1.612 (RS) sign flip for the same tier confirms the scalar encodes sample composition, not role behavior. |
| `COLD_START_PLAYOFF_SCALAR` | **DATA_GATED** | Direction matches published playoff rotation compression (7–9 players); taxi/extended_absence=0.400 probably still over-projects (modal outcome is DNP), but priced exposure ≈ 0. Revisit at n≥50 playoff cold-start player-games. |
| `OT_MIN_CAP=44.0` | **LOCKED** | OT rate ~6%, EV contribution ~+0.3 min — immaterial. Cap on projected means is sound; fix the misleading comment only. |

**Condition to Revisit:**
- **spot=1.6124:** at next RS scalar refit, fit the spot tier two ways — (a) current EWMA, (b) EWMA excluding games <10 min. If (b) moves the fitted scalar toward 1.0 by more than half its distance (i.e., below ~1.30), the selection mechanism is confirmed; replace the scalar with the filtered-EWMA input. Also trigger immediately if spot-tier minute projection MAE in any monthly backtest exceeds 1.5× the rotation tier's.
- **Role scalars:** refit each offseason and after any change to EWMA span, tier thresholds, or the backtest sampling frame (changing which player-nights are priced changes the selection effect the scalars absorb).
- **COLD_START_PLAYOFF_SCALAR:** revisit at n≥50 playoff cold-start player-games; if taxi/extended_absence actuals show >40% DNP rate, replace the 0.400 scalar with a play-probability gate.
- **OT_MIN_CAP:** no trigger; revisit only if a projected mean ever reaches 43+ for multiple players (would indicate upstream inflation, not a cap problem).

---

## SECTION 7C — Vegas Team-Total Constraint

**Question:** Is the Vegas team-total anchoring architecture in `nba_projector.py` — (1) Vegas implied total as the pace-factor prior, (2) asymmetric anchoring (PTS/3PM/REB on `_base_pf`, AST/STL/BLK on historical pace), (3) lineup-protected 240-minute reconciliation, (4) dual-path playoff pace logic — supported by published market-efficiency and forecast-reconciliation literature?

**Code ground truth:** `_base_pf = implied_total / LEAGUE_AVG_TOTAL` when a Vegas total exists, else historical pace ratio (with ~0.963 playoff scalar applied only on the no-Vegas path). Elasticities: pts^0.90, fg3m^0.78, reb^0.25 on `_base_pf`; ast^0.50, stl^0.30, blk^0.30 on historical `game_pace` only. 240-min constraint: top 5 by proj_min immutable, bench scaled uniformly. `COMBO_RHO_PTS_AST=0.233` consumes both stats downstream.

**Findings:**

1. **Vegas total as prior — strongly supported.** [Štrumbelj & Robnik-Šikonja (2010, *IJF* 26(3):482–488)](https://www.sciencedirect.com/science/article/abs/pii/S0169207009001733) showed bookmaker odds are well-calibrated probability forecasts whose forecasting effectiveness has *increased over time* across 10,699 matches. [Sauer (1998)](https://sharpsportsbettors.com/betting-blog/f/the-efficient-market-hypothesis-and-closing-line-value-in-sports) found NBA point-spread prices aggregate scarce information from diverse sources and are "almost invariably unbiased estimators" — average spread error under 0.25 points over six seasons. NBA-specific: [Paul et al. closing-line studies](https://www.researchgate.net/publication/24131329_Is_the_NBA_betting_market_efficient) (1990–2006) could not reject closing-line efficiency, and [line movement open→close significantly improves forecast accuracy](https://www.researchgate.net/publication/372441761_Inefficient_Forecasts_at_the_Sportsbook_An_Analysis_of_Real-Time_Betting_Line_Movement) with no profitable strategy at the close. Critically for player projections, [player-absence research (Finance Research Letters)](https://www.sciencedirect.com/science/article/abs/pii/S1544612315000227) shows closing lines fully incorporate lineup/absence information (closing line is a 50-50 bet even in absence games) — information a trailing-average pace model structurally lacks. Anchoring to the Vegas total is also standard industry practice in DFS projection systems ([Fantasy Projection Lab](https://fantasyprojectionlab.com/vegas-lines-and-fantasy-projections), [Stokastic](https://www.stokastic.com/nba/how-to-use-vegas-odds-in-dfs-player-props-betting-insights-ac11/)). **One documented caveat:** [Learning, price formation and the early season bias in the NBA (Finance Research Letters, 2007)](https://www.sciencedirect.com/science/article/abs/pii/S1544612307000177) — NBA *totals* (unlike sides) are significantly biased high in the season's opening weeks (58.2% unders in Week 1; a close-line under strategy won 56.7%). The anchor inherits this small early-season bias.

2. **AST asymmetry — real inconsistency, material, and the mechanical-coupling evidence supports anchoring AST.** Every assist requires a made field goal by definition; league AST/FGM is stable around 0.60–0.63 (per-game AST ≈ 26 on FGM ≈ 42), and shot-type data shows 73% of dunks, 63% of jump shots, and 47% of close shots are assisted ([82games.com assisted-FGM data](https://www.82games.com/random9.htm); [The Conversation, assisted-shot value analysis](https://theconversation.com/data-reveals-the-value-of-an-assist-in-basketball-113893)). Team assist totals correlate r = .42–.71 with team success and scoring ([PubMed: Team Assists & NBA Win-Loss Record](https://pubmed.ncbi.nlm.nih.gov/11361327/)). Since FGM scales near-proportionally with points (PTS/FGM ≈ 2.7 is stable) and AST/FGM is stable, AST elasticity to the scoring environment is ≈ 0.7–0.9 — comparable to the pts^0.90 already coded, and well above the ast^0.50 pace elasticity. **Quantification:** a Vegas total 8% above pace-implied moves PTS +7.2% (1.08^0.90) but AST 0%. Even granting only the coded ^0.50 elasticity, AST should move +3.9% (1.08^0.50); the coupling evidence supports more. On a 6.0-AST projection that is a 0.25–0.45 assist systematic miss, sign-correlated with game environment — large relative to half-point AST prop lines and it corrupts PTS-AST combo coherence (the engine prices ρ=0.233 co-movement downstream while the projection layer forces zero co-movement through the Vegas channel). **STL/BLK are different:** they track possessions and missed shots, not points — a high Vegas total confounds pace with efficiency (an efficient slow game has a high total but *fewer* steals/blocks opportunities). Dean Oliver's framework explicitly separates pace from efficiency ([Basketball on Paper possession framework](https://coachsclimb.com/2020/04/01/basketball-on-paper-how-it-works/)); keeping defensive counting stats on a pure possession (historical pace) driver is therefore defensible, while AST — coupled to *made* baskets, i.e., pace × efficiency — belongs on the Vegas-anchored path with PTS/3PM.

3. **Lineup protection — published analogue exists and supports the design.** [Zhang, Kang, Panagiotelis & Li, "Optimal reconciliation with immutable forecasts" (EJOR 2023; arXiv:2204.09231)](https://arxiv.org/abs/2204.09231) formalizes exactly this: reconciling a hierarchy to coherence while a pre-specified subset of base forecasts is held fixed, distributing the adjustment over the mutable remainder. The engine's top-5-immutable / bench-scaled scheme is a crude instance. It is also directionally consistent with MinT logic ([Wickramasuriya, Athanasopoulos & Hyndman, MinT](https://robjhyndman.com/papers/MinT.pdf)): optimal reconciliation adjusts each series inversely to its error variance, and starter minutes are the lowest-variance forecasts in the hierarchy (confirmed starters, stable rotations), so an optimal weighting would also concentrate adjustment on the bench. Pure proportional scaling of everyone would push correction onto the *best-estimated* components — worse than the current scheme. Residual risk is the stated one: a genuinely over-projected starter is never corrected; but the 240 constraint is a minutes identity, not a skill estimate, and starter minute errors are better fixed at the projection layer (role tiers, lineup fetcher) than the reconciliation layer.

4. **Dual-path playoff logic — correct.** Per Sauer (1998) and the efficiency literature above, market prices already aggregate all public information — including playoff pace compression — so a Vegas total *is* a playoff-pace-adjusted quantity. Multiplying a Vegas-derived `_base_pf` by an additional 0.963 playoff scalar would double-count information the market has already priced. Applying the scalar only on the no-Vegas fallback path is the theoretically sound design.

5. **Reconciliation-literature analogue — yes.** The architecture is bottom-up player forecasts (preserving granular information, per [FPP3 ch. 11](https://otexts.com/fpp3/reconciliation.html): bottom-up "loses no information due to aggregation") reconciled to two top-level anchors (240 minutes hard; Vegas total as multiplicative pace prior) — i.e., top-down disaggregation by *forecast proportions* combined with an immutable subset, both published methods (FPP3; Zhang et al. 2023). Hyndman, Ahmed et al. (2011) proved any top-down method introduces some bias at disaggregated levels even from unbiased base forecasts — acceptable here because the top-level anchor (the market total) is demonstrably more accurate than the aggregated bottom-up sum, which is precisely the regime where top-down anchoring wins. A MinT upgrade is the published optimum but requires the full error-covariance matrix across ~10 player series per team — over-engineered for this constraint's purpose.

**VERDICT:**

| Item | Verdict | Note |
|---|---|---|
| Vegas total as pace prior (`_base_pf`) | **LOCKED** | Market efficiency literature unambiguous; early-season totals bias (FRL 2007) is small and inherited, not introduced |
| PTS^0.90 / 3PM^0.78 / REB^0.25 on `_base_pf` | **LOCKED** | Standard DFS/industry practice; elasticities are separately calibrated constants (out of scope here) |
| AST^0.50 on historical pace (not Vegas-anchored) | **NEEDS_CHANGE** | Move AST to `_base_pf` with its existing ^0.50 elasticity (one-line change: AST joins the pts/fg3m/reb branch). Mechanical AST↔FGM coupling (AST/FGM ≈ 0.60–0.63, stable) implies AST elasticity to scoring environment ≈ 0.7–0.9; current design assigns 0. Expected systematic error ~0.1–0.45 AST on Vegas-vs-pace divergences of 3–8%, sign-correlated with environment, and incoherent with COMBO_RHO_PTS_AST=0.233 downstream. Backtest AST bias vs Vegas-divergence quintiles before shipping; consider raising elasticity toward ~0.7 at the next refit |
| STL^0.30 / BLK^0.30 on historical pace | **LOCKED** | Theoretically correct: defensive events track possessions, not points; Vegas total confounds pace with efficiency (Oliver pace/efficiency separation). Do NOT blanket-anchor these with AST |
| Lineup-protected 240-min reconciliation | **LOCKED** | Published analogue (immutable-forecast reconciliation, Zhang et al. 2023); variance-weighting logic of MinT independently favors adjusting bench over starters |
| Dual-path playoff scalar (Vegas path skips ×0.963) | **LOCKED** | Market prices already embed playoff pace; applying both would double-count |

**Condition to Revisit:**
- **AST anchoring (the NEEDS_CHANGE):** ship after a backtest showing AST projection bias is positive in games where `implied_total/LEAGUE_AVG_TOTAL > game_pace/LEAGUE_AVG_PACE` (and negative in the reverse) — bucket graded AST props by Vegas-vs-pace divergence quintile; if the top-vs-bottom quintile bias spread exceeds ~0.15 AST, the fix is confirmed. Re-grid the AST elasticity (0.50 vs 0.70) on the same backtest.
- **Vegas prior:** revisit only if shadow CLV / graded data ever show the model's own pace-implied totals beating Vegas totals on Brier/MAE over n ≥ 200 games, or if entering a league/market with thin totals liquidity (WNBA early season — where the FRL early-season totals-bias result suggests extra caution).
- **Lineup protection:** revisit if starter-minute projection error (top-5 proj_min MAE) is shown to exceed bench MAE in a season-scale backtest — that would invert the variance-weighting argument.
- **STL/BLK:** revisit only if a possession-specific market signal becomes available (e.g., derived possessions from total+spread+efficiency priors), which would be the correct anchor for defensive counting stats — not the raw total.

---

## SECTION 7D — Stat Scalars and Playoff Deflators

**Question:** Are `REGULAR_SEASON_STAT_SCALAR` (multiplicative per-stat bias corrections, 7 params fit on 4,653 player-games) and `PLAYOFF_RATE_DEFLATORS` (PTS 0.934 / AST 0.845 / FG3M 0.948 / BLK 1.152, fit on 1,071 playoff player-games) statistically sound? Five sub-questions: multiplicative vs additive form; in-sample overfit risk; the BLK=1.152 inflator (open question C01); the AST=0.845 deflator magnitude; round-specificity of a single deflator.

**Code ground truth:** Scalars are pure multiplicative corrections applied after playoff pace handling (Vegas total or pace scalar 100.22→96.5). Deflators were refit 2026-05-10 from a 20-date backtest covering Apr 18–May 8 2026 — i.e., a **single postseason** (2026 R1 + early R2). Post-fix biases ≈ 0 on the fitting set.

**Findings:**

1. **Multiplicative form is correct for zero-bounded count stats — supported by two independent literatures.** The [Mincer–Zarnowitz (1969) regression framework](https://www2.nau.edu/PinNg/working/AsymmetricLossForecast.pdf) (realized = α + β·forecast; unbiasedness = joint test α=0, β=1) explicitly decomposes forecast bias into an additive component (α) and a proportional component (β). The EdgeModel scalar is a pure β-correction (α constrained to 0). Verification-metrics documentation ([scores: Additive vs Multiplicative Bias](https://scores.readthedocs.io/en/stable/tutorials/Additive_and_multiplicative_bias.html)) states multiplicative bias correction "is well suited for forecasts and observations that have 0 as an upper or lower bound" — exactly the case for count stats. Climate bias-correction practice ([UTCDW Guidebook §4.2](https://utcdw.physics.utoronto.ca/UTCDW_Guidebook/Chapter4/section4.2_bias_correction_methods.html)) uses the same split: multiplicative scaling for zero-bounded variables (precipitation), additive for unbounded (temperature). For EWMA under-projection proportional to player volume, multiplicative is the right form; an additive shift would over-correct low-volume players (+0.028 BLK added to a 0.05-BLK spot player is a 56% distortion; ×1.06 is uniform). *Caveat worth one cheap check:* the scalar form **assumes** α=0 without testing it — add a per-stat MZ regression at the next refit. Also note an internal-documentation inconsistency: PTS comment arithmetic checks out exactly (−0.022/11.599 → 1.0019 ✓) but AST (−0.019/2.679 → implies 1.0071, not 1.0120) and BLK (−0.008/0.462 → implies 1.017, not 1.0608) do not — the fit basis (pre- vs post-fix, weighted vs raw) should be documented uniformly at the next refit.

2. **In-sample overfit risk is negligible for the RS scalars; the real issue is evaluation tautology.** 7 parameters on 4,653 observations ≈ 665 obs/parameter, vastly above the ≥10–20 obs-per-parameter floor in the prediction-model literature ([Subramanian & Simon, Overfitting in prediction models](https://brb.nci.nih.gov/techreport/Subramanian-Overfitting.pdf)). SE of a mean-ratio scalar ≈ CV/√n: for PTS (CV≈0.7) SE≈0.010; for BLK (CV≈1.7) SE≈0.025. The genuine methodological gap: "post-fix bias ≈ 0" on the *fitting* backtest is true **by construction** (a ratio-of-means correction zeroes the fitting-set bias identically); it is not evidence of out-of-sample improvement. Cross-validation guidance ([Yates et al. 2023, Ecological Monographs](https://esajournals.onlinelibrary.wiley.com/doi/10.1002/ecm.1557)) recommends a temporal holdout; a simple split-half (fit on odd dates, evaluate on even) costs nothing and breaks the tautology.

3. **C01 — BLK=1.152 is NOT supported at league level; per-possession playoff block rates are approximately flat.** Reconstructed comparison: 2025 playoffs, 16 playoff teams averaged **4.88 BPG** ([Land of Basketball, 2025 playoffs](https://www.landofbasketball.com/team_rankings_by_year/2025_fewest_blocks_pg_pl.htm)) vs those same teams' **5.04 BPG** in the 2024-25 RS ([Land of Basketball, RS](https://www.landofbasketball.com/team_rankings_by_year/2025_fewest_blocks_pg_rs.htm)) → per-game ratio **0.968**; 2024 playoffs ratio ≈0.97. Playoff pace runs ~4–6% below RS (96.3 vs 100.2 possessions in 2026; [NBA.com](https://www.nba.com/news/power-rankings-2025-26-playoffs-conference-finals); [Sportico playoff analytics](https://www.sportico.com/feature/nba-playoffs-postseason-stats-analytics-data-viz-1234848952/)). Per-possession block ratio = 0.968/0.961 ≈ **1.01–1.03**. The half-court-defense hypothesis has the right *sign* but supports roughly **+1–3%**, not +15.2%. Sportico additionally reports paint touches "consistently declined in the postseason throughout the player tracking era" — fewer rim attempts argues *against* a large block inflator. What CAN legitimately exceed the league number: the deflator corrects **model** residuals — if the Vegas-total path deflates projections by the full scoring decline (pace −3.9% × efficiency −2.8% ≈ −6.6%) while blocks scale only with pace, BLK is spuriously over-deflated ~2.8%, justifying ~1.03 on top of the ~1.01–1.03 real effect → defensible inflator ≈ **1.04–1.06**. The remaining gap to 1.152 is most plausibly sample artifact: the fit window is a **single postseason** in which Victor Wembanyama averaged **5.6 BPG** — flirting with the all-time postseason record (Eaton/Bol 5.8). With BLK mean 0.462 and t=−2.74, the 95% CI on the inflator is roughly **[1.04, 1.26]** — the data cannot distinguish 1.05 from 1.15. **Recommendation: keep the C01 gate; do not lock 1.152.** Run per-possession decomposition with Wembanyama (and any >2 BPG player) held out and the Vegas-total over-deflation quantified; expected outcome: shrink to ~1.04–1.06.

4. **AST=0.845 is directionally and roughly quantitatively consistent with published playoff data.** Mechanism documented league-wide: slower pace, more isolation (iso frequency rose every postseason since 2016, averaging 9.3% from 2016–23), fewer passes and assists ([Sportico](https://www.sportico.com/feature/nba-playoffs-postseason-stats-analytics-data-viz-1234848952/); [Bruin Sports Analytics — e.g. Trae Young 9.7→6.0 APG](https://www.bruinsportsanalytics.com/post/nba_postseason_change)). Quantitatively: 2025 playoff teams averaged **22.1 APG** vs same teams' **26.4 APG** in RS ([Land of Basketball](https://www.landofbasketball.com/team_rankings_by_year/2025_fewest_assists_pg_pl.htm)) → ratio **0.837**; removing pace (÷0.961) leaves pace-independent **~0.87** (−13%). The model's post-pace 0.845 (−15.5%) is ~2.5pp stronger than league-wide — within sampling noise of the 1,071-game fit, plausibly explained by the priced population skewing toward high-assist creators who absorb the iso shift most.

5. **Round-specificity: a single deflator is acceptable; round-split estimation is not identifiable at current n.** Effects *escalate* by round (rotations tighten, matchup intensity rises — [Pace and Space](https://paceandspacehoops.com/the-importance-of-shortened-nba-playoff-rotations/); [NBA.com](https://www.nba.com/news/power-rankings-2025-26-playoffs-conference-semifinals)), but splitting 1,071 player-games into 4 rounds gives ~150–400 games/round — SEs ±5–10% per stat per round, larger than any plausible round effect. The minutes side of round escalation is already handled by `PLAYOFF_MINUTES_SCALAR`. Revisit at pooled n≥3,000.

6. **Cross-check on PTS=0.934:** 2026 playoff scoring decomposition (pace 96.3/100.2 = 0.961; ORtg 111.6/114.8 = 0.972) gives a combined PPG ratio of 0.934 — numerically identical to the deflator. Since the deflator applies *after* pace handling, the expected post-pace residual from league data alone is ~0.97; the fitted 0.934 is stronger, consistent with the priced population (stars facing playoff-keyed defenses; 72% of playoff teams since 2010 shot worse from three — [Sportico](https://www.sportico.com/feature/nba-playoffs-postseason-stats-analytics-data-viz-1234848952/)). Flag: if the Vegas-total path already embeds the efficiency decline, part of 0.934 may double-count it — fold into the same C01 decomposition (mirror image of the BLK over-deflation question).

**VERDICT:**

| Item | Verdict | Basis |
|---|---|---|
| Multiplicative (vs additive) scalar form | **LOCKED** | MZ framework + zero-bounded-variable bias-correction literature. Add per-stat MZ intercept check at next refit (cheap). |
| `REGULAR_SEASON_STAT_SCALAR` values | **PERIODIC_RECAL** | ~665 obs/param, overfit negligible; but "post-fix bias≈0" is tautological — add split-half temporal holdout at next refit. Fix comment/fit-basis documentation (AST/BLK comment arithmetic inconsistent with scalar values). |
| `PLAYOFF_RATE_DEFLATORS` PTS=0.934 | **PERIODIC_RECAL** | Direction + magnitude match published playoff pace/efficiency decline; check Vegas-total double-count in C01 decomposition. |
| `PLAYOFF_RATE_DEFLATORS` AST=0.845 | **PERIODIC_RECAL** | League per-possession playoff AST drop ~−13%; model −15.5% post-pace within noise and population-consistent. |
| `PLAYOFF_RATE_DEFLATORS` FG3M=0.948 | **PERIODIC_RECAL** | Consistent with 72%-of-teams-shoot-worse playoff 3P% finding; small magnitude, low risk. |
| `PLAYOFF_RATE_DEFLATORS` BLK=1.152 (C01) | **DATA_GATED — keep gate, do NOT lock 1.152** | League per-possession playoff block rate ≈ flat (+1–3%), not +15%. Defensible value ≈1.04–1.06 (real effect + Vegas-total over-deflation correction). 95% CI [1.04, 1.26] from a single postseason likely dominated by Wembanyama (5.6 BPG). Required before locking: leave-one-player-out refit + per-possession decomposition. |
| Single deflator across rounds | **LOCKED (at current n)** | Round effects real but unidentifiable at 1,071 games; minutes side already handled by PLAYOFF_MINUTES_SCALAR. Revisit at pooled n≥3,000. |

**Condition to Revisit:**
- **C01 gate (BLK):** before the 2027 playoffs, run per-possession decomposition + leave-one-player-out (exclude >2 BPG players). If LOPO estimate <1.10, shrink to the decomposition-supported value (~1.05); if ≥1.10, retain 1.152 and document the population-concentration mechanism.
- **RS scalars:** re-fit each July on a fresh 30-date window with split-half holdout; alert if any scalar moves >2×SE (PTS ±0.02, BLK ±0.05) between refits.
- **Playoff deflators:** refit when pooled playoff sample reaches ≥2 full postseasons (~2,500+ player-games); at ≥3,000, test round-split (R1 vs R2+) deflators.
- **MZ intercept check:** at next RS refit, regress actual on projection per stat; if any intercept |t|>2, the pure-multiplicative assumption fails for that stat and a two-parameter (α, β) correction is warranted.
- **PTS/Vegas-total interaction:** if the C01 decomposition shows the Vegas-total path already embeds the playoff efficiency decline, re-derive PTS deflator net of it (expected drift toward ~0.97).

---

## SECTION 7E — DK_STD Model and HIGH_VAR Flag

**Question:** Is `dk_std = max(0.35×proj_pts, role_floor, rolling_std)` a defensible points-uncertainty estimator, and is `CV ≥ 0.60 @ n≥8` a defensible bimodality detector?

**Code ground truth:** `DK_STD_COEFF=0.35`; role floors 4.0/4.0/3.5/3.0/3.0; third arm = observed rolling PTS std at ≥8 clean games; excluded from 240-min Vegas scaling. `HIGH_VAR_CV_THRESHOLD=0.60`, `HIGH_VAR_MIN_GAMES=8`. Both informational/flagging only — not the prop-pricing sigma.

**Findings:**

1. **The max() formula is an upward-biased estimator — but conservatism is the correct direction for an uncertainty flag.** By Jensen's inequality, E[max(X₁,X₂,X₃)] ≥ max(E[X₁],E[X₂],E[X₃]): always selecting the largest of three noisy estimates systematically overstates σ, and the rolling-std arm at n≈8–10 is itself very noisy (Finding 4), so it will frequently "win" the max by sampling error alone. The statistically optimal alternative is precision-weighted shrinkage of the observed std toward the model value — standard empirical-Bayes/James–Stein machinery ([Hoff, Duke STA732 shrinkage notes](https://www2.stat.duke.edu/~pdh10/Teaching/732/Notes/shrinkage.pdf); [Rasmusen, Understanding Shrinkage Estimators](https://www.rasmusen.org/papers/shrinkage-rasmusen.pdf)). However, MSE-optimality is the right loss function for a *pricing* sigma; for a purely informational uncertainty tag, the asymmetric loss (underestimating risk is worse) makes the deliberate upward bias defensible. Since the betting engine prices props with its own SIGMA/NB-r calibrations, the bias has no P&L path.

2. **The 0.35 coefficient is consistent with published NBA scoring variability — and the functional form is an implicit negative-binomial approximation.** Published NBA points CVs span roughly 0.28 (most consistent stars) to >1.1 (volatile role players), with a clear negative mean–CV relationship ([Beyond Averages, 2025, via Gelman's blog](https://statmodeling.stat.columbia.edu/2025/08/06/beyond-averages-measuring-consistency-and-volatility-in-nba-player-and-team-offense/)). A constant 0.35 sits at the low (starter) end — correct, because the role floors supply the extra relative dispersion for low-projection players (floor 3.5 on a 7-pt projection = effective CV 0.50). NBA point totals are overdispersed relative to Poisson and best fit by negative binomial ([Poisson model limits in NBA basketball, Physica A](https://www.sciencedirect.com/science/article/abs/pii/S0378437116304599); [Bayesian home-advantage paper, PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC8282683/)). Under NB, CV² = 1/μ + 1/r, so CV → 1/√r for high scorers: **CV=0.35 asymptotically implies r ≈ 8.2 — squarely in the range of the engine's own NB fits.** `max(0.35μ, floor)` is therefore a crude piecewise approximation of NB sd = √(μ + μ²/r): proportional at high μ, floored at low μ. Cross-check vs reported MAEs (σ = MAE×√(π/2) for Normal): starter MAE 5.38 → implied σ ≈ 6.7 vs 0.35×(18–22) = 6.3–7.7 — match. But rotation MAE 4.77 → implied σ ≈ 6.0 while a 9-pt rotation player gets max(3.15, 3.5, obs) — the formula arms understate unless `pts_std_recent` rescues it ([RotoGrinders NBA Stat Variance](https://rotogrinders.com/lessons/nba-stat-variance-209254): pooled σ ≈ 6.1). Net behavior for low-minute roles is under-, not over-stated, despite the "upward-biased" max().

3. **CV ≥ 0.60 is not a bimodality detector — but no formal bimodality test works at n=8, so CV is the defensible proxy; the fix is the label, not the statistic.** Published bimodality measures are Sarle's bimodality coefficient (BC, benchmark 0.555) and Hartigan's dip test. BC misclassifies skewed *unimodal* distributions as bimodal ([Pfister et al. 2013, Frontiers in Psychology](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2013.00700/full)); the dip test is the preferred formal test ([Freeman & Dale 2013, Behavior Research Methods](https://link.springer.com/article/10.3758/s13428-012-0225-x)) but has essentially no power at n=8 (dip statistic scales ~a/√n; [diptest CRAN docs](https://cran.r-project.org/web/packages/diptest/diptest.pdf)). Meanwhile CV does capture the right players: an equal-weight 0/8-point mixture has CV=1.0 and a 2/14 mixture CV=0.75 (both flag), while a consistent 25-ppg star would need σ=15 to flag (correctly never fires). For the downstream use (variance-risk tag feeding G15), high relative dispersion is the operative property regardless of modality. The flag is mislabeled, not malfunctioning.

4. **At n=8 the CV estimate carries ±25–35% sampling error — the flag is unavoidably noisy at the gate minimum.** SE(s) ≈ s/√(2(n−1)) = s/√14 ≈ 0.27s for Normal data; the CV estimator adds mean-estimation noise on top (SE(ĈV) ≈ ±33% relative at CV=0.6, n=8). Published sample-size guidance for *precise* CV estimation wants dozens to hundreds of observations ([Kelley 2007, Behavior Research Methods](https://link.springer.com/article/10.3758/BF03192966)). A true-CV-0.45 player will sometimes flag and a true-CV-0.75 player sometimes won't, early in a season. Tolerable only because the flag is informational; n=8 is "earliest possible signal," not "stable estimate."

5. **Excluding dk_std from the 240-min Vegas scaling is correct.** The 240-min constraint rescales mean projections multiplicatively. For overdispersed count data (NB: var = μ + μ²/r), variance falls *slower* than μ², so proportional σ-scaling would over-shrink uncertainty exactly when minutes get squeezed. Moreover, a minutes squeeze adds *rotation uncertainty* — predictive σ should if anything rise. Floored, non-shrinking dk_std is the right design.

**VERDICT:**

| Item | Verdict | Basis |
|---|---|---|
| max() formula vs shrinkage blend | **ACCEPTABLE (documented bias)** — upward-biased by Jensen's inequality vs an EB blend, but conservatism is the correct loss direction for an informational flag; net effect for low-minute roles is actually understatement vs MAE-implied σ | Hoff; Rasmusen; MAE cross-check |
| 0.35 coefficient | **LOCKED** — matches starter-end of published CV range; implies NB r≈8.2, consistent with engine's own NB fits; max(0.35μ, floor) ≈ piecewise NB sd | Beyond Averages 2025; RotoGrinders; Physica A |
| Role floors (4.0/4.0/3.5/3.0/3.0) | **PERIODIC_RECAL** — rotation/spot floors look ~1–2 pts low vs MAE-implied predictive σ (≈6.0/5.2) when `pts_std_recent` is unavailable; harmless while informational | MAE math; RotoGrinders pooled σ≈6.1 |
| CV ≥ 0.60 as "bimodality" detector | **NEEDS_RELABEL, keep statistic** — CV measures dispersion, not modality; but dip test/BC are both powerless or unreliable at n=8, and high dispersion is the operative property for G15. Rename to high-variance flag; reserve dip test for n≥30 if true modality classification is ever needed | Pfister 2013; Freeman & Dale 2013 |
| n=8 minimum for CV | **ACCEPTABLE (known noise)** — ±25–35% relative SE at the gate minimum; fine for an informational tag, never promote to behavioral gating at n=8 | Kelley 2007; SE(s) math |
| Exclusion from 240-min scaling | **LOCKED** — proportional σ-scaling would over-shrink under NB variance structure, and minutes squeezes add rotation uncertainty | Physica A; NB var-mean relation |

**Condition to Revisit:**
1. **If dk_std ever becomes a pricing input** (feeds win_prob, Kelly, or any gate threshold beyond a binary tag): the max() bias becomes P&L-relevant — replace with precision-weighted blend `σ̂² = w·s²_recent + (1−w)·(0.35μ)²`, w = (n−1)/(n−1+n₀), n₀≈10, and recalibrate floors against MAE-implied σ per role.
2. **Floors:** at next backtest refresh, regress |error| on projection by role; if rotation/spot MAE-implied σ exceeds delivered dk_std by >1.5 pts for players lacking `pts_std_recent`, raise those floors.
3. **HIGH_VAR flag:** if G15 ever moves from display to blocking, raise `HIGH_VAR_MIN_GAMES` to ≥20 and add persistence (flag must hold across 2 consecutive windows); only consider a dip test at n≥30–50.
4. **Coefficient:** re-check 0.35 if league scoring environment shifts materially (current implied r≈8.2 should stay within ~6–10).

---

## SECTION 7F — 3PM Architecture Post-PAD_3P

**Question:** Post-PAD_3P-fix validation of the 3PM projection stack: (1) is `LG_FG3A_RATE=0.420` current? (2) is the two-path (FGA-decomp + per-minute) blend at α=0.65 a defensible architecture? (3) does `PAD_3P=242` match Medvedovsky (2020), and is career-to-date the right denominator? (4) what is the root cause of the −0.26 shared under-projection bias, and is a multiplicative stat scalar the correct compensator? (5) what residual should the next checkpoint expect?

**Code ground truth:** `PAD_3P=242` (career-to-date 3PA denominator), `LG_FG3A_RATE=0.420`, `FG3M_BLEND_ALPHA=0.65` (re-grid n=1,936, MAE flat 0.55–0.70). Path 1: team FGA × pace^0.78 → USG share → fg3a_rate → padded 3P% → matchup. Path 2: per-minute fg3m EWMA × proj_min. Post-fix FGA-path bias −0.265; baseline-path bias −0.247; production backtest (scalars applied) −0.005.

**Findings:**

1. **LG_FG3A_RATE=0.420 — consistent with the current era; update was correct.** League-wide 3PA hit a record 37.6/game in 2024-25 (up from 22.4 in 2014-15), and Sportico reported teams attempting **42.4% of all shots from three** in 2024-25 — the first season the rate exceeded 40% ([Sportico](https://www.sportico.com/leagues/basketball/2025/nba-3-pointer-record-rate-stats-1234822888/); [StatMuse 3PA by year](https://www.statmuse.com/nba/ask/nba-league-wide-three-point-attempts-per-game-by-year-since-2000-to-2025)). With league FGA ~88–89/game, final 2024-25 3PAr ≈ 0.42. The old 0.385 was 2–3 seasons stale; 0.420 matches within ±0.005. The precise final 2025-26 figure was not retrievable this session — verify at the July refit.

2. **Two-path blend — sound and better-grounded than either path alone.** The published landscape spans exactly EdgeModel's two poles: (a) standard DFS architecture is per-minute rate × projected minutes enriched with usage/pace/team-total multipliers — RotoGrinders' canonical inputs piece explicitly averages **two parallel projections** (a weighted-input projection and a per-minute × minutes projection), i.e., a two-path blend is itself practitioner-published practice ([RotoGrinders key inputs](https://rotogrinders.com/lessons/key-inputs-in-an-nba-projections-system-1144825)); (b) the state-of-the-art public system, DARKO, is per-stat Bayesian state-space ([DARKO explainer](https://www.nbastuffer.com/analytics101/darko-daily-plus-minus/)); (c) forecast-combination theory (Bates & Granger 1969; the "forecast combination puzzle") shows combining imperfect forecasts reduces MSE and **simple/near-equal weights are robustly hard to beat** — estimated "optimal" weights routinely underperform out of sample ([Elliott, Averaging and Optimal Combination of Forecasts](https://econweb.ucsd.edu/~grelliott/AveragingOptimal.pdf)). Given the empirically flat MAE curve over 0.55–0.70, α=0.65 is within the noise band of equal-ish weighting — α is not the lever that matters here.

3. **PAD_3P=242 — confirmed against the primary source, with two caveats.** Medvedovsky (2020) gives the 3P% stabilization/padding value as **240–242** (the article uses 240 in the Duncan Robinson worked example `(17 + 240×.355)/(34 + 240) = .373` and 242 in the text; secondary coverage — Owen Phillips' F5 — cites 242). It explicitly supersedes Blackport's 750 (2014), confirming the Plan 6 §12 fix direction ([Medvedovsky 2020](https://kmedved.com/2020/08/06/nba-stabilization-rates-and-the-padding-approach/); [The F5](https://thef5.substack.com/p/isthatgood)). Caveat 1 — **no uncertainty band is published**: values came from differential evolution on ~750K rows; treat 242 as a point estimate good to maybe ±20%. Caveat 2 — **denominator frame**: 242 was optimized against **season-to-date** attempts predicting rest-of-season, *not* career-to-date. Career-to-date is defensible (more signal, strictly better than the old 30-game window) but weights a shooter's year-one attempts equally with current-season attempts, ignoring talent drift — the very problem DARKO solves with exponential decay on attempts. With a career-to-date denominator the *effectively optimal* pad is plausibly somewhat larger than 242. Refinement, not error.

4. **Root cause of the −0.26 shared bias — frame mismatch is the DOMINANT driver (~−0.18); minutes under-projection + EWMA trend-lag are real but explain only ~−0.08. The arithmetic forces this conclusion.** The production compensators are multiplicative — minutes scalars (overall ratio 1.0365) × fg3m stat scalar (1.0231) ≈ **1.060 combined lift**. On a ~1.34 mean, removing a 1.06 lift produces an expected pre-scalar bias of only ≈ −0.08, not −0.26. Since production shows ≈0 *with* scalars and the evaluate frame shows −0.26 *without* them, roughly **−0.08 is the genuine mechanism and ≈ −0.18 is frame disagreement** — different population, dates, or conditioning between the n=1,936 evaluate frame and the 30-date/4,653-game production frame. Prime structural suspect: **conditioning on realized outcomes** — if the evaluate frame conditions on games actually played (or actual minutes/3PA thresholds), it selects player-games where realized volume exceeded projection, mechanically inflating actual fg3m vs projection — a selection bias no scalar should "fix." On the genuine mechanisms: (a) **minutes under-projection is the canonical dominant error source** (practitioner literature unanimous — "minutes are king"; [RotoGrinders Projected Minutes](https://rotogrinders.com/lessons/projected-minutes-the-most-critical-opportunity-stat-in-nba-dfs-3147006)); EdgeModel's own RS minute scalars all >1 confirm it; (b) **EWMA lag on a trending series is a textbook systematic bias** — simple exponential smoothing "always lags behind the trend," which is why Holt's method exists ([FPP3 §8.2](https://otexts.com/fpp3/holt.html)); league 3PA trended 22.4 → 37.6/game over 2015→2025, so an EWMA of per-minute fg3m rate under-projects by low single-digit percent — consistent with the fg3m scalar of 1.0231, *not* with 19%.

5. **Is the multiplicative stat scalar the correct compensator? Yes for the genuine mechanisms — but it is currently also masking the frame artifact.** Multiplicative bias correction is appropriate when the variable is zero-bounded and the error source scales with magnitude — both true: minutes shortfall scales fg3m proportionally, and EWMA trend-lag is a proportional rate shortfall ([scores: additive vs multiplicative bias](https://scores.readthedocs.io/en/stable/tutorials/Additive_and_multiplicative_bias.html)). So `REGULAR_SEASON_STAT_SCALAR[fg3m]=1.0231` is the right functional form, and production −0.005 bias is legitimate evidence it works in the deployed frame. The hazard is interpretive, not operational: quoting "−0.26 FGA-path bias" as a model defect overstates the real defect ~3×. **Separating diagnostic:** on identical rows, decompose in logs — `log(actual_fg3m+ε) − log(proj_fg3m+ε) ≈ [minutes-bias component] + [rate-bias component]` — run once with production scalars off and once on, on the production-frame population. If minutes ≈ −3.5% and rate ≈ −2.5%, mechanism confirmed and the evaluate frame's extra −0.18 is formally attributed to selection/frame.

6. **Expected post-fix residual at next checkpoint:** Production frame (scalars on) should stay within ±0.02 of zero, with slow upward drift of the needed scalar (~+1–2%/season) as long as league 3PA keeps rising — the EWMA-lag component renews itself every season the trend continues. If league 3PA plateaus, the rate-lag component decays and the fg3m scalar should drift back toward ~1.00. The evaluate frame (scalars off) should show ≈ −0.08 ± 0.03 *after* the frame mismatch is fixed; if it still shows ≈ −0.26 after aligning populations, the selection-bias hypothesis is wrong and a real unmodeled mechanism exists — escalate.

**VERDICT:**

| Item | Verdict | Basis |
|---|---|---|
| `LG_FG3A_RATE=0.420` | **CONFIRMED (PERIODIC_RECAL)** | 2024-25 actual ≈ 0.42 (42.4% per Sportico); confirm exact 2025-26 figure at July refit |
| Two-path blend architecture | **CONFIRMED** | Two-path averaging is published practitioner practice (RotoGrinders); combination theory (Bates–Granger) supports blending; DARKO validates per-stat rate path |
| `FG3M_BLEND_ALPHA=0.65` | **CONFIRMED (weak preference)** | MAE curve flat 0.55–0.70; combination-puzzle literature says near-equal weights are robust — α is not a meaningful lever |
| `PAD_3P=242` | **CONFIRMED** | Medvedovsky 2020 primary source: 240–242, supersedes Blackport 750 |
| Career-to-date denominator | **ACCEPTABLE, NOT EXACT** | 242 was optimized on *season-to-date*; career-to-date ignores talent drift — effective optimal pad likely >242 under this denominator; consider decayed attempts at next architecture pass |
| −0.26 shared bias root cause | **FRAME MISMATCH dominant (~−0.18); minutes under-proj + EWMA trend-lag real (~−0.08)** | Scalar arithmetic: 1.0365×1.0231 ≈ 1.06 lift ≈ −0.08 on 1.34 mean; cannot produce −0.26 |
| Multiplicative stat scalar | **CORRECT FORM, partially masking** | Correct for proportional mechanisms per bias-correction practice; the evaluate-frame −0.26 headline conflates a measurement artifact with model error |

**Condition to Revisit:**
- July refit: pull final 2025-26 league 3PAr from Basketball-Reference; adjust `LG_FG3A_RATE` if |actual − 0.420| > 0.01.
- Run the log-space minutes×rate bias decomposition on production-frame rows (scalars off); if rate-component bias > 4% or minutes-component > 6%, the EWMA needs a trend term (Holt-style or DARKO-style decay) rather than a bigger scalar.
- Align evaluate_projector.py frame with production (same population, scalars toggleable); if shared bias remains ≤ −0.20 after alignment, selection hypothesis is falsified — open a new investigation.
- If league 3PA/game is flat or down in 2026-27, expect `REGULAR_SEASON_STAT_SCALAR[fg3m]` to need *reduction* toward 1.00; a scalar still rising in a flat-3PA league indicates a different mechanism.
- If a player's career-to-date 3PA exceeds ~2,000 with a documented talent change (role/mechanics), the career-to-date pad denominator materially staleness-biases 3P% — consider exponentially-decayed attempts (DARKO-style) as the denominator at the next architecture pass.

---

## SECTION 7G — Stat-Specific Blend Alphas

**Question:** Are the four stat-specific blend alphas (PTS=0.50, REB=0.45, AST=0.40, FG3M=0.65) defensible per forecast-combination literature? Does provenance (heuristic vs grid-search) matter? Should they be refit each offseason, fixed at 0.5, or left as-is?

**Code ground truth:** `proj = α × decomposed_path + (1−α) × EWMA_baseline` per stat. PTS (0.50) and FG3M (0.65) grid-search calibrated with flat MAE curves (FG3M flat across 0.55–0.70, n=1,936). REB (0.45) and AST (0.40) provenance undocumented; the AST comment ("lean toward baseline until rates stabilise") reads as judgment. Both paths share the projected-minutes input, so forecast errors are strongly positively correlated (plausibly ρ ≥ 0.7).

**Findings:**

1. **The two-path blend is the canonical published architecture, not an idiosyncrasy.** Combining a structural/causal forecast with a time-series extrapolation baseline is exactly the setting [Bates & Granger (1969)](https://rdrr.io/cran/GeomComb/man/comb_BG.html) formalized, and [Clemen's (1989) review](https://ideas.repec.org/a/eee/intfor/v24y2008i1p163-169.html) found "virtually unanimous" evidence that combining forecasts improves accuracy, with the largest gains from combining *structurally different* methods. NBA-specific practice matches: [DARKO](https://www.nbastuffer.com/analytics101/darko-daily-plus-minus/) blends an exponential-decay component with a Kalman component (weights varying by stat), and the standard DFS approach is per-minute rates × projected minutes with structural adjustments layered on ([RotoGrinders methodology](https://rotogrinders.com/fantasy/lessons/nba-player-projections)).

2. **The Bates–Granger optimal weight is w\* = (σ²_b − σ_ab)/(σ²_a + σ²_b − 2σ_ab), but the loss surface around it is extremely flat when errors are highly correlated.** Analytically, with roughly equal path error SDs and correlation ρ, combined error variance is σ²(w) = σ²[1 − 2w(1−w)(1−ρ)]. The penalty for using w instead of the 0.5 optimum is **0.08(1−ρ)/[1−0.5(1−ρ)]** in variance at the extreme of w ∈ {0.3, 0.7}. At ρ = 0.7 that is a **2.8% variance penalty ≈ 1.4% RMSE/MAE penalty at the worst edge of the 0.3–0.7 window**, and only **~0.35% RMSE at w = 0.4 vs 0.5**. At ρ = 0.8 the figures halve again. This is why the observed grid-search MAE curves for PTS and FG3M are flat — it is the mathematically expected shape, not a calibration artifact.

3. **Provenance of REB=0.45/AST=0.40 therefore does not matter.** Whether heuristic or calibrated, any value in 0.3–0.7 is within ~1% MAE of optimal given the shared-minutes error correlation; 0.40–0.45 are within ~0.5%. The literature explicitly warns against estimating these weights precisely: [Smith & Wallis (2009)](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1468-0084.2008.00541.x) show finite-sample estimation error in combining weights typically exceeds the gain from optimal weighting — the "forecast combination puzzle" ([Wang, Hyndman et al., 50-year review](https://arxiv.org/pdf/2205.04216)). [Elliott (2011)](https://econweb.ucsd.edu/~grelliott/AveragingOptimal.pdf) bounds the expected gains from optimal over equal weights and shows they are "often too small to balance estimation error," with the bound shrinking as error correlation rises.

4. **The alpha family (0.40–0.65) is effectively equal weighting, and the literature says that is the right place to be.** Estimated Bates–Granger weights "do not appear to work well in practice" across decades of studies; simple combinations that ignore error correlations "often dominate more refined combination schemes" ([Timmermann 2006, Handbook of Economic Forecasting ch. 4](https://ideas.repec.org/h/eee/ecofch/1-04.html)). Clustering near 0.5 with mild stat-level tilts is precisely the robust configuration the puzzle literature recommends.

5. **Forcing all four to exactly 0.5 would be churn, not improvement.** FG3M's measured flat region is 0.55–0.70; snapping it to 0.50 moves it marginally *outside* its own calibrated plateau for zero expected gain. The puzzle literature's prescription is "don't chase precision," not "all weights must equal 0.5." Annual refits would re-estimate parameters whose sampling noise exceeds their signal on n in the low thousands.

**VERDICT:**

| Item | Value | Verdict | Rationale |
|---|---|---|---|
| PTS_BLEND_ALPHA | 0.50 | **LOCKED** | Grid-calibrated, flat curve; equal weight is the literature-robust point (Smith & Wallis 2009; Elliott 2011). |
| REB_ALPHA | 0.45 | **LOCKED** | Provenance immaterial: ≤~0.5% MAE from optimum anywhere in 0.4–0.6 under ρ≈0.7. Do not spend a grid search on it. |
| AST_ALPHA | 0.40 | **LOCKED** | Same flat-surface argument; mild baseline tilt is harmless and within the plateau. |
| FG3M_BLEND_ALPHA | 0.65 | **LOCKED** | Freshly grid-calibrated (2026-06-05), flat 0.55–0.70. Do NOT snap to 0.50 — that exits its measured plateau. |
| Two-path blend architecture | — | **LOCKED** | Canonical Bates–Granger/Clemen design; matches DARKO and industry NBA practice. |
| Offseason alpha refits | — | **NOT RECOMMENDED** (no PERIODIC_RECAL) | Flat curves + combination puzzle: refit cost > expected gain. Calibration effort is better spent on the paths themselves (minutes model, sigma calibration), where errors actually live. |

**Condition to Revisit:** (1) **Structural change to either path** — if the decomposed path for a stat is redesigned or the EWMA baseline's decay changes, the error-variance ratio and correlation shift, so re-run one grid search for that stat only. (2) **Path decorrelation** — if a future path stops sharing projected minutes (e.g., a possession-based path with independent minutes), error correlation drops, the loss surface steepens, and weight estimation starts to pay; re-derive w\* then. (3) **Empirical trigger** — if any stat's blended MAE exceeds the better single path's MAE over a ≥1,500-row backtest window (combination should never lose to its best component by more than noise), investigate the blend. (4) **n ≥ ~10,000 paired residuals per stat** — only at that scale does estimated-weight sampling error shrink enough that a non-flat curve, if one exists, becomes detectable; even then expect ≤1% MAE upside.

---

## SECTION 7H — Position-Specific AST EWMA Spans

**Question:** Are the position-specific AST EWMA spans `{PG: 10, SG: 8, SF: 6, PF: 6, C: 5}` in `compute_ast_rate` supported by published research — specifically the rationale that "PG assist rates are more stable and need longer history; C assist rates are more variable" (therefore shorter span)?

**Code ground truth:** `_AST_EWMA_SPAN = {"PG": 10, "SG": 8, "SF": 6, "PF": 6, "C": 5}` on the position-conditional AST rate path (general `EWMA_SPAN_STAT` AST span = 13; path down-weighted by `AST_ALPHA=0.40`). API mapping never assigns PG, so deployed reality is `{all guards: 8, SF: 6, PF: 6, C: 5}`.

**Findings:**

1. **The span ordering inverts the universally published sampling principle: rarer events require LARGER samples to stabilize, not smaller.** Russell Carleton's stabilization research (the canonical reference, ported to the NBA by Blackport/Narsu/Medvedovsky) shows sample requirements scale inversely with event frequency and directly with noise in the generating process — e.g., K% stabilizes at 60 PA while rarer/noisier HBP rate needs 240 PA and BABIP needs 820 BIP ([FanGraphs Sample Size library](https://library.fangraphs.com/principles/sample-size/); [kmedved, NBA Stabilization Rates and the Padding Approach](https://kmedved.com/2020/08/06/nba-stabilization-rates-and-the-padding-approach/)). A center at ~1.5–2.5 AST/game observed through a span-5 EWMA has an effective sample of roughly 8–12 assist events (relative SE ≈ 30%); a PG at ~7–9 AST/game through span-10 has ~70–90 events (relative SE ≈ 11%). The code gives the noisiest estimate ~3× less smoothing — statistically backwards. No published source supporting shorter windows for low-frequency positions was found in any search.

2. **The stated rationale is also self-contradicting.** "C assist rates are more variable" is precisely the argument for a LONGER span: higher sampling variance → more regression/smoothing needed. This is the same error pattern the STL/BLK span audit flagged (§7A), applied to the lowest-frequency assist position. Bayesian shrinkage treatments confirm the direction: the empirical-Bayes AST% prior exists exactly because small assist samples must be regressed harder, not trusted faster ([tothemean, Empirical Bayes-ketball](https://www.tothemean.com/2020/09/06/empirical-bayes.html)).

3. **Optimized decay rates in published projection systems imply far LONGER memory than any of these spans — and are fit per stat, never hand-set per position.** DARKO weights each game by β^t with β fit per stat via differential-evolution optimization; "in practice, with a few exceptions, values of β tend to be 0.98 or higher" per day ([NBAstuffer, DARKO explained](https://www.nbastuffer.com/analytics101/darko-daily-plus-minus/)). At ~2.1 days/game, β=0.98/day ≈ 0.958/game ≈ EWMA span ~46 games — an order of magnitude longer than span 5–10. Even the engine's own generic AST span of 13 is short by this benchmark; the positional path makes it shorter still. No published projection system was found that conditions decay rate on position.

4. **Published stability/reliability work treats assists as among the MOST stable, discriminative box-score stats — with no positional reliability split.** Franks, D'Amour, Cervone & Bornn find assists, rebounds, and blocks "highly discriminative and stable because of the relatively large between-player variance" ([Franks et al. 2016, arXiv:1609.09830](https://arxiv.org/abs/1609.09830)). Note the subtlety: high between-player stability of AST is mostly a role/position effect, which says nothing about within-player short-window estimation — the relevant quantity here — where event-count math (Finding 1) dominates. Additionally, assists carry scorekeeper subjectivity noise ([van Bommel & Bornn, Adjusting for Scorekeeper Bias in NBA Box Scores, arXiv:1602.08754](https://arxiv.org/pdf/1602.08754)) — measurement noise that argues for more smoothing across all positions, never less.

5. **The PG-mapping caveat makes the deployed config worse, not better.** Since the NBA API maps G→SG, true point guards — the highest-volume, most reliably estimated playmakers — get span 8, barely half the generic AST span of 13. Deployed, the table is a flat "shorten everyone, shorten bigs most" — every position gets less memory than the generic path, with the biggest haircut on the noisiest estimates.

6. **The static positional stereotype behind the ordering is empirically eroding.** Center playmaking has risen league-wide: average center AST% up 3.58 points since 2014-15 (centers now assist ~12.8% of team FGs), and center passes per 100 possessions rose 16.76% in 2014-18 alone ([Berkeley SAG, Point Centers](https://sportsanalytics.studentorg.berkeley.edu/articles/point-centers.html); [NBA.com on Jokić leading the league in assists](https://www.nba.com/news/nikola-jokic-first-player-lead-nba-assists-rebounds)). Modern high-usage hub centers have PG-like assist volumes; a hand-set span keyed to a 2010s positional stereotype misclassifies exactly the centers most likely to carry priced AST props.

**VERDICT:**

| Item | Verdict | Basis |
|---|---|---|
| Shorter spans for non-primary playmakers | **NEEDS_CHANGE** — no support found; ordering inverts the Carleton/Blackport/Medvedovsky sampling principle (rarer events → larger samples) | FanGraphs sample-size library; kmedved 2020; tothemean EB priors |
| Empirical autocorrelation support for spans 5–10 | **NEEDS_CHANGE** — optimized per-stat decays (DARKO β≥0.98/day ≈ span ~45+ games) imply far longer memory; no published positional decay split exists | NBAstuffer DARKO; kmedved 2020 |
| PG-never-assigned caveat | **Worsens the assessment** — deployed table is flat {guards 8, SF/PF 6, C 5}, all below the generic span 13; the only long-span cell is unreachable | Code ground truth + Franks et al. |
| Position-conditioning vs uniform | **NEEDS_CHANGE (overfitting risk)** — spans hand-set, never fit; the stereotype is eroding (center AST% +3.58pp since 2014-15); if conditioned at all, the ordering should be inverted | Franks et al. 2016; Berkeley point-centers data |

**Recommended fix:** Either (a) **delete `_AST_EWMA_SPAN` and use the generic AST span 13 uniformly** (simplest, removes an unfitted hand-set table), or (b) **invert and lengthen**: PG/SG ≈ 13, SF/PF ≈ 15, C ≈ 18–20, then validate by per-position AST MAE/bias backtest. Severity is moderated by `AST_ALPHA=0.40` (the decomposed path is down-weighted 60/40 against the baseline path) and by Bayesian priors downstream — a real but partially absorbed error, largest for low-minute bigs and modern playmaking centers. Any fitted replacement should be optimized (per-stat decay à la DARKO), not hand-ordered by position.

**Condition to Revisit:**
- Backtest trigger: run the 30-date RS backtest with uniform span=13 vs current table; adopt uniform if per-position AST MAE is flat or better for C/PF (expected: improvement concentrated in C).
- Data trigger: if a future PG mapping lands, do NOT activate span 10 for PG without refitting — the whole table needs refitting, not just the PG cell.
- Monitoring trigger: graded AST prop bias by player position — if C/PF AST picks show win-rate or projection-bias divergence vs guards at n≥30 per group, prioritize fix (b) with a fitted span grid.
- Interaction check: any change to `_AST_EWMA_SPAN` should be evaluated jointly with `AST_ALPHA=0.40`, since lengthening spans reduces path variance and may justify raising alpha.

---

## SECTION 7I — EWMA_SPAN_SHOOTING and OT_MIN_CAP

**Question:** Is a single span-10 EWMA appropriate for the four efficiency/rate inputs it governs (FG%, FT%, FG3A rate, USG%), given published per-stat stabilization points? And does published data independently confirm 7B's LOCKED verdict on OT_MIN_CAP=44.0?

**Code ground truth:** `EWMA_SPAN_SHOOTING = 10` (α = 2/11 ≈ 0.182; ~87% of weight on last 10 games; half-life ≈ 3.5 games). Applies to FG%, FT%, FG3A rate, USG%. 3P% is exempt — it routes through the PAD_3P=242 career-padded stabilizer. `OT_MIN_CAP = 44.0` caps projected minute means.

**Findings:**

1. **The authoritative published per-stat numbers exist — Medvedovsky 2020 padding table** ([kmedved.com, "NBA Stabilization Rates and the Padding Approach"](https://kmedved.com/2020/08/06/nba-stabilization-rates-and-the-padding-approach/), fit by differential evolution on ~750k player-game rows, 2001–2020). Exact values relevant here:

   | Metric | Padding | Denominator |
   |---|---|---|
   | minutes | 1.52 | games |
   | **fg3_ar (3PA/FGA rate)** | **3.64** | FGA |
   | **ft_pct** | **24.11** | FTA |
   | **usg_pct** | **72.41** | possessions |
   | **fg_pct (all FGA)** | **102.92** | FGA |
   | fg2_pct | 127.33 | 2PA |
   | fg3_pct | 242.61 | 3PA |
   | pm_100 (+/-) | 1,007.21 | possessions |

   The fg3_pct value 242.61 confirms the engine's PAD_3P=242 is the correct published number.

2. **FT% needs far less smoothing than baseball-style intuition suggests — span-10 is fine.** Medvedovsky's empirical-Bayes padding for FT% is only **24.11 FTA** — the smallest of any shooting percentage — because padding reflects the noise-to-skill-spread ratio, and FT% has an enormous between-player skill spread (~50%–90%). Franks et al. (2016, [Meta-Analytics, arXiv:1609.09830](https://arxiv.org/pdf/1609.09830)) corroborate: FT% is "very stable over time." A span-10 window contains ~20–50 FTA for rotation players — at or above the 24-FTA padding scale. No action needed.

3. **USG% is among the fastest-stabilizing stats in basketball — span 10 is more smoothing than needed, which is harmless.** Padding is **72.41 possessions ≈ roughly one game**. Nylon Calculus's stabilization work ([team-stats noise analysis](https://fansided.com/2017/12/21/nylon-calculus-team-stats-noise-stabilization-thunder/)) finds stylistic/volume metrics trustworthy within a handful of games. A span-10 EWMA carries ~700 effective possessions → observed-data weight ~0.91 vs the padding prior. Only cost is a 3.5-game half-life lag after genuine role changes — acceptable, partially covered by the injury-redistribution layer.

4. **FG3A rate stabilizes near-instantly — span 10 is reasonable.** Padding is **3.64 FGA**, the second-fastest stat in the table after minutes, because attempt share is a role/shot-diet choice, not a noisy conversion outcome. The design constraint is responsiveness to rotation/scheme changes — span 10's 3.5-game half-life tracks those within a week.

5. **FG% is the one input where span-10 EWMA is roughly half noise — the material finding.** A 10-effective-game window holds ~80–150 FGA; Medvedovsky's FG% padding is **102.92 FGA** (127.33 for 2P% alone). At 100 observed FGA against a 103-FGA prior, the data weight in a proper shrinkage estimate is ~0.49 — an *unshrunk* EWMA FG% over-weights recent conversion luck by roughly 2× relative to the empirical-Bayes optimum. Published literature is unanimous that raw short-window FG% is noise-dominated ([Daly-Grafstein & Bornn, Rao-Blackwellizing Field Goal Percentage, arXiv:1808.04871](https://arxiv.org/pdf/1808.04871)). Two mitigations: (a) the EWMA retains decaying pre-window weight, anchoring established players near their own season mean; (b) the matchup/USG/minutes structure carries most of the PTS decomp signal. Still, the literature-aligned upgrade is exactly the treatment 3P% already received: a career-padded stabilizer with **PAD_FG≈103 FGA** (or PAD_2P≈127 if the path separates twos), blended like FG3M.

6. **Single shared span: defensible simplification.** The four stats' stabilization points span two orders of magnitude (3.6 → 103 FGA-equivalent), but the asymmetry is benign in one direction: over-smoothing fast stats costs only responsiveness lag, while under-smoothing slow stats injects noise. The architecture already handles this correctly in principle — the slow stat that matters most (3P%, padding 242) got a padding stabilizer rather than a per-stat span. The remaining gap is FG% (Finding 5). Per-stat EWMA spans are NOT the right fix; padding is, because padding adapts to each player's attempt volume while a span is volume-blind.

7. **OT_MIN_CAP=44.0 — independently confirmed.** (a) OT frequency ~5.9% of RS games, trending *down* since 2000 ([Binomial Basketball](https://www.binomialbasketball.com/p/probability-of-nba-overtime-over)) — at 5 min/OT this is ~+0.3 expected minutes, matching 7B's figure exactly. (b) Headroom: the 2024-25 league minutes leader averaged 37.6–37.7 MPG ([NBA.com](https://www.nba.com/news/nba-fantasy-minnutes-per-game-leaders-from-2024-25)) — a 44.0 cap on projected *means* sits ~6.3 minutes above the most extreme real workload and can only bind on data errors. 7B's LOCKED verdict stands.

**VERDICT:**

| Item | Verdict | Basis |
|---|---|---|
| EWMA span=10 for USG% | **LOCKED** | Stabilizes at ~72 poss ≈ 1 game; span 10 is conservative smoothing, no harm |
| EWMA span=10 for FG3A rate | **LOCKED** | Padding 3.64 FGA — near-instant; 3.5-game half-life tracks role changes adequately |
| EWMA span=10 for FT% | **LOCKED** | Published padding is 24.11 FTA, not ~250 — within the span-10 window's volume; minor decomp input regardless |
| EWMA span=10 for FG% | **NEEDS_CHANGE (P3, test-gated)** | Padding 102.92 FGA ≈ the window's entire effective volume → unshrunk EWMA is ~50% noise vs the EB optimum; apply the PAD_3P pattern: PAD_FG≈103 FGA (PAD_2P≈127) career-padded blend. Deploy only if backtest PTS MAE improves — the 3P% precedent showed shared-path bias may dominate, in which case keep as-is |
| Single shared span (4 stats) | **LOCKED** (conditional) | Heterogeneity correctly resolved by padding slow stats, not per-stat spans; condition = FG% padding item above |
| OT_MIN_CAP=44.0 | **LOCKED** (confirms 7B) | OT ~5.9% of games and declining; +0.3 min EV; 6+ min above the league MPG leader (37.6) |

**Condition to Revisit:**
- **FG% padding test:** at the July offseason refit, run the FG3M-style grid for a PAD_FG=103 (or PAD_2P=127) career-padded blend on the FG%/PTS decomp path; deploy only on MAE/bias improvement over span-10 EWMA alone. If, as with 3P%, the residual bias proves shared across blend components, mark FG% LOCKED and close.
- **FG3A-rate responsiveness:** if post-trade/rotation-change FG3M projection lag is observed (systematic mis-projection in a player's first ~4 games after a confirmed role change), consider a shorter span or a role-change reset for FG3A rate only.
- **OT_MIN_CAP:** revisit only if the NBA changes OT format, or if any projected minute mean ever exceeds ~42 (would indicate an upstream minutes-model error, not a cap problem).

---
---

# PLAN 8 — Player Context Adjustments (2026-06-06)
# Files: EdgeModel/engine/nba_projector.py + EdgeModel/engine/injury_parser.py
# Research model: claude-opus-4-8 with web search (one agent per section)

Validates every player-context adjustment — home/away deltas, blowout model,
days-rest model, Bayesian REB priors, role classification, cold-start treatment,
injury redistribution, and injury status probabilities — against published
sports-analytics and sports-science literature. Same format and verdict
vocabulary as Plan 7 above.

### Code ground-truth corrections found during source verification
Documented here because the planning doc (plans_7_8_9.md) stated otherwise or omitted them:

- **8C:** `DAYS_REST_HALF_LIFE=1.5` is an **e-folding time**, not a half-life. The decay is `exp(−days_rest/1.5)` → true half-life ≈ 1.04 days. (Already flagged in STATISTICAL_FOUNDATIONS ground-truths; restated because 8C evaluates the recovery curve directly.)
- **8D:** there are **two** REB prior systems, not one. (1) per-minute **baseline** path priors `_REB_RATE_PRIOR_RS/PO` with `_REB_RATE_PRIOR_N=12`; (2) decomposed **OREB/DREB** path priors `_REB_POS_{O,D}REB_PRIOR_{RS,PO}` with `_REB_PRIOR_N_OREB=_REB_PRIOR_N_DREB=5` (12 was tried and rolled back as too aggressive). The plan doc only mentioned N=12. **Further discovery (8D agent):** the N=12 baseline prior is applied *only* at `_reb_n_games==0` (cold-start) — for any player with real data the raw observed rate is used, so N=12 never partial-pools; it is effectively a dead parameter and the prior *value* is the entire cold-start anchor. And that value is **deflated ~1.8–2.4×** by a per-game-vs-per-36 units error in its derivation (see §8D NEEDS_CHANGE).
- **8A:** STL is **deliberately excluded** from `_HOME_AWAY_DELTA` — measured within-player delta was −1.59% (away > home, unexpected direction, judged noise). Not an omission.
- **8G:** `_POS_FLOW` PG column is always 0.00 because the NBA API never returns position=PG; PG receiver weight was folded into SG (2026-05-10 fix). Flow weights are renormalized to position groups that actually have eligible players; M05 adds a C-fallback at a 5.0-min threshold when no backup C qualifies at 8.0; bumps are M16-clamped to 48.0 and per-player capped by `ROLE_MAX_MIN`.
- **8H:** binary in/out (`questionable`/`GTD`/`probable` → play_prob 1.00) is a deliberate product decision (2026-05-06) grounded in void-grading: NBA props at all major CO books VOID on DNP, so probabilistic discounting generates structurally −EV unders against Q-listed players.

### Verified source values (read 2026-06-06)

| § | Constants | Location |
|---|---|---|
| 8A | `_HOME_AWAY_DELTA`: pts +0.0235, reb +0.0088, ast +0.0333, fg3m +0.0452, blk +0.0439, tov −0.0122 (multiplicative half-deltas: home ×(1+δ), away ×(1−δ)); STL excluded | nba_projector.py:352-359 |
| 8B | Margins 15/25; weights bench 0.55/0.75, star 0.75/0.90; `_BLOWOUT_MIN_VALID_GAMES=12`; sigmoid k=0.15, mid=20.0, max_reduction=0.19 (refit 2026-05-06, 24,600 rows, MSE 0.00008) | nba_projector.py:139-202, 564-617, 1102-1105 |
| 8C | `DAYS_REST_MAX_REDUCTION=0.10`, `DAYS_REST_HALF_LIFE=1.5` (e-folding); role scalars 1.0/0.95/0.90/0.75/0.90; formula `0.10 × role_scalar × exp(−days_rest/1.5)`; comment: "calibrated from NBA literature (~3 games data)" | nba_projector.py:205-222, 1060-1063 |
| 8D | Baseline path `_REB_RATE_PRIOR_RS` PG=.053/SG=.057/SF=.079/PF=.111/C=.165 (N=12, cold-start only); decomposed OREB/DREB priors RS & PO (N=5); `REB_ALPHA=0.45` | nba_projector.py:385-398, 1466-1494 |
| 8E | starter: sr≥0.60 AND avg_min≥26; sixth_man ≥20; rotation ≥12; spot ≥5; else cold_start. Trailing-10-game window. Refit 2026-05-09 on 76,604 snapshots | nba_projector.py:488-518 |
| 8F | taxi cap 12.0; returner (≥180d) min(career,22) else 14; ext_absence (60–179d) min(career×0.70,25) else 14; new_acq (<60d) min(career,28) else 16; `COLD_START_PLAYOFF_SCALAR` .400/.400/.700/.750; `MIN_GAMES_FOR_TIER=10` | nba_projector.py:278-283, 1158-1198 |
| 8G | `_POS_FLOW` (PG col dead); `REDISTRIB_PRIMARY_SHARE=0.50`, `REDISTRIB_EFFICIENCY=0.90`, `REDISTRIB_MIN_ELIGIBLE=8.0`, C-fallback 5.0 | injury_parser.py:74-88, 363-402 |
| 8H | `_STATUS_MAP`: out=(O,0.00), doubtful=(O,0.10), questionable=(Q,1.00), GTD=(GTD,1.00), probable=(P,1.00); `_TRADED_AWAY_DAYS=30` | injury_parser.py:16, 44-59 |

### VERDICT SUMMARY (sections 8A–8H)

| § | Topic | Verdict |
|---|---|---|
| 8A | Home court advantage deltas | MIXED — AST/BLK/TOV/REB CONFIRMED; PTS CONFIRMED_WITH_CAVEAT; **FG3M PERIODIC_RECAL** (9% spread exceeds published ~3%); STL exclusion CONFIRMED_WITH_CAVEAT; deltas-as-set PERIODIC_RECAL (secular HCA decline) |
| 8B | Blowout adjustment | MIXED — cutpoints 15/25 + star weights + sigmoid (k/mid) CONFIRMED/LOCKED; bench weights + min-games ACCEPTABLE; max_reduction PERIODIC_RECAL; PBP filtering DATA_GATED upgrade |
| 8C | Days-rest model | **MIXED — `max_reduction=0.10` NEEDS_CHANGE (overstates played-game effect); travel/altitude/density omissions NEEDS_CHANGE (material); naming mislabel NEEDS_CHANGE (cosmetic)**; decay form CONFIRMED; role gradient + channel CONFIRMED_WITH_CAVEAT |
| 8D | Bayesian REB priors | **MIXED — `_REB_RATE_PRIOR` (System 2) NEEDS_CHANGE (deflated ~2×, all positions — extends H01)**; decomposed priors + N=5 + denominator CONFIRMED; PO-vs-RS CONFIRMED_WITH_CAVEAT (SF over-deflated); REB_ALPHA LOCKED |
| 8E | Role classification thresholds | *(batch 2)* |
| 8F | Cold start treatment | *(batch 2)* |
| 8G | Injury redistribution model | *(batch 2)* |
| 8H | Injury status probabilities | *(batch 2)* |

---

## SECTION 8A — Home Court Advantage Deltas

**Question:** Are the six `_HOME_AWAY_DELTA` half-deltas (PTS +2.35%, REB +0.88%, AST +3.33%, FG3M +4.52%, BLK +4.39%, TOV −1.22%), the multiplicative symmetric form, the STL exclusion, and the same-delta-RS-and-playoffs assumption consistent with published NBA home-court-advantage and scorekeeper-bias research?

**Code ground truth:** `nba_projector.py:345-359` — within-player empirical deltas `(home_avg − away_avg)/player_avg`, averaged across players, applied multiplicatively and symmetrically: `home_proj = proj × (1+δ)`, `away_proj = proj × (1−δ)`. Implied full home-vs-away spreads: PTS ~4.7%, REB ~1.8%, AST ~6.7%, FG3M ~9.0%, BLK ~8.8%, TOV ~−2.4%. STL measured at −1.59% and excluded. Same deltas in RS and playoffs.

**Findings:**

1. **Team-level HCA baseline matches direction; PTS magnitude is on the high side.** Published team splits: home teams scored ~3.4% more and committed ~3.1% fewer turnovers (2003–2011, [Bleacher Report](https://bleacherreport.com/articles/1520496-how-important-is-home-court-advantage-in-the-nba)); an all-time-leaders study found players scored 2.8% more at home ([Jeffrey Fan, "Biased Stats in the NBA"](https://jeffreyfan.com/2019/12/08/biased-stats-in-the-nba/)). Modern HCA has shrunk to <2 net points ([Marc Stein](https://marcstein.substack.com/p/what-has-happened-to-homecourt-advantage); [Sparkle Technologies 43-yr analysis](https://sparkletechnologies.com/blog/nba-disappearing-home-court-advantage)). The model's ~4.7% PTS full spread is ~1.4–2× the published 2.8–3.4% team gap — legitimately inflatable by an *unweighted within-player* mean (bench players show outsized relative home boosts, [NBC Sports](https://www.nbcsports.com/fantasy/basketball/news/article-numbers-game-home-vs-away-fantasy-splits-0)), but warrants an SE check at refit.

2. **AST +6.67% spread is squarely confirmed.** Career-leader analysis found assists carry a 6.4% relative home bias on top of the ~2.8% scoring baseline ([Fan](https://jeffreyfan.com/2019/12/08/biased-stats-in-the-nba/)); other analyses put home assist inflation at "nearly 8 percent" ([Daily Thunder](https://www.dailythunder.com/nba-scorekeepers-inflated-stats-and-the-thunder/)); 2019-20 league data confirm superior home assists ([systematic review, PMC11503446](https://pmc.ncbi.nlm.nih.gov/articles/PMC11503446/)). Model 6.67% is in-range, slightly conservative.

3. **BLK +8.78% spread is directionally confirmed and conservative.** Home block inflation is the largest of any stat: 12.3% relative bias ([Fan](https://jeffreyfan.com/2019/12/08/biased-stats-in-the-nba/)), "more than 15 percent" in scorekeeper analyses ([Daily Thunder](https://www.dailythunder.com/nba-scorekeepers-inflated-stats-and-the-thunder/)). Blocks and assists are exactly the two stats van Bommel & Bornn identify as most scorekeeper-discretionary ([arXiv:1602.08754](https://arxiv.org/abs/1602.08754); [DMKD 2017](https://link.springer.com/article/10.1007/s10618-017-0497-y)).

4. **TOV −2.4% spread and REB +1.76% spread both match published splits.** Home teams committed 3.1% fewer turnovers (refs call fewer discretionary turnovers on home teams — Moskowitz & Wertheim *Scorecasting*, via [Chicago Booth Review](https://www.chicagobooth.edu/review/home-field-advantage-facts-and-fiction)); rebounds show the lowest home bias of any stat (~1.4% relative, [Fan](https://jeffreyfan.com/2019/12/08/biased-stats-in-the-nba/)).

5. **FG3M +9.04% spread is the least externally corroborated constant.** Published shooting splits show road teams shoot only ~1 pp worse from three (~3% relative on makes; [Marc Stein](https://marcstein.substack.com/p/what-has-happened-to-homecourt-advantage)), and FT% is essentially identical home/away (*Scorecasting*) — arguing against large *real* crowd shooting effects. A 9% FG3M gap likely combines an attempt-ecology effect (home teams generate 12.7% more fast-break points → more assisted/transition threes, [Bleacher Report](https://bleacherreport.com/articles/1520496-how-important-is-home-court-advantage-in-the-nba)) with low-count noise (small per-game FG3M makes within-player ratios high-variance). Direction confirmed; magnitude needs SE verification.

6. **STL exclusion is defensible but the measured sign is anomalous.** Published steal home bias is small-*positive* (+3.2% relative, [Fan](https://jeffreyfan.com/2019/12/08/biased-stats-in-the-nba/)); steals are far less scorekeeper-discretionary than AST/BLK (van Bommel & Bornn model only assists and blocks, [project page](https://www.matthewvanbommel.com/projects/nba_scorekeeper_bias.html)). The model's −1.59% conflicts in sign with the small published positive; applying zero is the correct conservative call when the measured sign contradicts the literature and the magnitude is marginal.

7. **Playoff stability: HCA *strengthens* in playoffs, so a flat delta is conservative, never anti-directional.** RS HCA ~2.7 points rises to ~4.5 in playoffs ([SportsHandle](https://sportshandle.com/court-advantage-nba-playoffs/); [SI](https://www.si.com/nba/what-does-home-court-advantage-mean-historically-nba-playoffs)); scorekeeper bias persists in playoffs (home-hired scorekeepers, season-to-season generosity r≥0.776, [van Bommel & Bornn](https://www.matthewvanbommel.com/projects/nba_scorekeeper_bias.html)). But secular decline is real (home win% 66.2% in the 1980s → ~55% in the 2020s; COVID empty-arena natural experiment showed ~2 crowd-driven points, [AIP](https://www.aip.org/inside-science/the-subtle-biases-that-influence-home-court-advantage)) — trailing-window fits track this only if refit.

8. **CRITICAL — scorekeeper artifact validates the adjustment rather than invalidating it.** AST/BLK home inflation is substantially a *recording* artifact (one player's potential assists 27.41% more likely to be credited; persistence r≥0.776, [van Bommel & Bornn 2017](https://link.springer.com/article/10.1007/s10618-017-0497-y)). Player props settle on the **official recorded box score**, so the model *should* predict recorded stats, artifact and all — the +3.33% AST and +4.39% BLK deltas are correct in kind *because* of the artifact, not despite it. One refinement left on the table: scorekeeper bias is venue-specific, so a league-average delta blurs real per-arena variance.

**VERDICT:**

| Item | Verdict | Basis |
|---|---|---|
| AST +3.33% | CONFIRMED | Published home assist inflation 6.4–9% full spread; model conservative |
| BLK +4.39% | CONFIRMED | Published 12–15% full spread; model conservative; scorekeeper literature directly supports |
| TOV −1.22% | CONFIRMED | Published −3.1%/game turnover reduction; discretionary-call mechanism |
| REB +0.88% | CONFIRMED | Published rebound home bias smallest of all stats (~1.4% rel) |
| PTS +2.35% | CONFIRMED_WITH_CAVEAT | Direction solid; 4.7% spread ~1.4–2× team-level 2.8–3.4%; verify SE at refit |
| FG3M +4.52% | PERIODIC_RECAL | Direction confirmed; 9% spread exceeds published ~3% shooting-split; low-count noise — re-estimate with SE |
| Multiplicative symmetric form | ACCEPTABLE | Standard projection practice; equal relative / larger absolute for stars is fair |
| STL exclusion | CONFIRMED_WITH_CAVEAT | Published bias small-positive vs model's −1.59%; zero is right conservative call; re-measure each refit |
| Same delta RS vs PO | ACCEPTABLE | Playoff HCA *stronger*; flat delta conservative, never anti-directional |
| Deltas as a set (refit cadence) | PERIODIC_RECAL | NBA HCA declining secularly; trailing-window fits track only if refit annually |

**Condition to Revisit:**
1. **July 2026 refit:** re-estimate all six deltas on the trailing 3-season window with SEs; flag FG3M specifically — if its spread stays >7% with SE excluding ~3–4%, decompose attempt-volume vs accuracy before keeping 0.0452.
2. **STL re-measurement each refit:** add it if the within-player delta turns positive >+1.5% with |t|>2; if it stays negative at |t|>2 across two refits, audit home/away game tagging.
3. **Playoff-specific deltas:** once the playoff sample reaches ~2,500 player-games, test whether PO deltas exceed RS (literature predicts they do); a separate PO set is justified if PTS/AST PO deltas exceed RS by >50% relative.
4. **Venue-specific scorekeeper adjustment (DATA_GATED):** if per-arena AST/BLK prop samples reach ~100 player-games/venue, evaluate per-arena coefficients (persistence r≥0.776 makes venue effects stable enough to fit).
5. **HCA regime change:** league-wide home win% <53% or >58% for a full season triggers an out-of-cycle delta refit.

---

## SECTION 8B — Blowout Adjustment

**Question:** Are the model's two blowout mechanisms — (1) historical down-weighting of blowout games in the EWMA baseline, and (2) forward-looking sigmoid minutes reduction keyed to the Vegas spread — consistent with published garbage-time research and spread-to-margin distributions?

**Code ground truth:** Mechanism 1 (`nba_projector.py:139-202`): final margin ≥25 ("heavy") / ≥15 ("light") down-weights the game in the EWMA — bench 0.55/0.75, starters 0.75/0.90 — only when ≥12 non-blowout games remain. Mechanism 2 (`:564-617, 1102-1105`): today's projected minutes reduced by `0.19 / (1 + exp(−0.15·(|spread| − 20)))` — refit 2026-05-06 on 24,600 player-games (MSE 0.00008) against margin-conditional anchors (20–25: 11.2%, 25–30: 13.8%, 35+: 18.9%). The sigmoid input is the pre-game **spread**, calibrated to **final-margin** anchors — correct, because margin ≈ Normal(spread, σ≈12), so the spread response must be flatter.

**Findings:**

1. **Cutpoints 15/25 match the industry-standard garbage-time definition.** Cleaning the Glass / Ben Falk use margin ≥25 at start of Q4 as the canonical garbage-time threshold ([CTG garbage-time guide](https://cleaningtheglass.com/stats/guide/garbage_time); [NBA-in-R implementation](https://nbainrstats.netlify.app/post/identifying-garbage-time-on-nba-play-by-play/)). The model's **25-pt heavy cutpoint matches exactly**; the 15-pt light cutpoint matches the published coach-rest threshold entering Q4 ([The Wager Theorem](https://thewagertheorem.com/nba-player-props-risk-adjustment/); [LSports](https://www.lsports.eu/blog/the-30-point-problem-how-basketball-blowouts-expose-trading-vulnerabilities/)). [Kubatko et al. 2007](https://www.degruyter.com/abstract/j/jqas.2007.3.3/jqas.2007.3.3.1070/jqas.2007.3.3.1070.xml) grounds the per-minute normalization; CTG is the operative garbage-time standard.

2. **Star weight 0.75 in 25+ games brackets the data.** A starter typically loses the entire Q4 (~12 min, ~33%) once a blowout is established entering Q4 ([Wager Theorem](https://thewagertheorem.com/nba-player-props-risk-adjustment/)), but averaged over all 25+ *final-margin* games (many close until late) the model's own refit found 13.8–18.9% average reduction. A 25% information discount sits between the average and the worst case — a minutes-proportional discount. Bench 0.55 is also directionally supported (bench more present in garbage time, largest distortions, [82games](http://www.82games.com/comm14.htm); [VDG Sports](https://vdgsports.com/player-efficiency-rating/)).

3. **Sigmoid k=0.15, mid=20 reproduces the correct Bayesian expectation.** Final margin ≈ Normal(spread, σ≈12) (Winston first-principles, [waynewinston.com](https://waynewinston.com/wordpress/p_2333/); Stern normal-margin framework, [arXiv:1902.10067](https://arxiv.org/pdf/1902.10067)). Under N(spread,12): P(margin≥25) = 4.8% at spread 5, 10.6% at 10, 20.2% at 15, 33.9% at 20. Marginalizing the model's margin-conditional anchors over this distribution gives E[reduction|spread] ≈ 3.5%/5.7%/8–9% at spreads 10/15/20 — the sigmoid outputs 3.5%/6.1%/9.5%. The shallow shape is *mathematically required*, not a tuning artifact; the old steep k=0.40/mid=12 would have double-counted realization risk. ([Boyd's Bets](https://www.boydsbets.com/ats-margin-standard-deviations-by-point-spread/): ATS variance doesn't grow with NBA spread, so a single σ is safe.)

4. **max_reduction=0.19 matches the 18.9% margin-35+ asymptote and is conservative on a spread input** (sigmoid output only ~12.9% at spread 25, ~17.1% at spread 35 — spreads that essentially never print). Blowout base rates are *rising* (34% of April 2026 games decided by 20+, [Sportico](https://www.sportico.com/leagues/basketball/2026/nba-tanking-data-draft-lottery-odds-1234890511/); [ESPN "20 is the old 12"](https://www.espn.com/nba/story/_/id/39698420/no-lead-safe-nba-big-comebacks-blown-leads)) — if anything the cap may drift slightly low, not high.

5. **MIN_VALID_GAMES=12 prevents the filter from amplifying small-sample noise** — consistent with the stabilization/padding literature's small-sample warnings ([Medvedovsky](https://kmedved.com/2020/08/06/nba-stabilization-rates-and-the-padding-approach/)). No published value for this exact guard; 12 is a reasonable convention. The model down-weights rather than excludes, so even when active the sample shrinks by at most ~25–45% of the blowout games' weight.

6. **Whole-game down-weighting is the correct-direction second-best; PBP stint exclusion is the published upgrade.** Garbage time inflates counting-stat *rates*, not just minutes (PER "artificially inflated", [VDG](https://vdgsports.com/player-efficiency-rating/); fantasy "volume up, efficiency down", [PFF](https://www.pff.com/news/fantasy-composting-digging-into-garbage-time)) — exactly what matters for PTS/REB/AST props. CTG's best practice drops the garbage-time *possessions* and keeps the rest of the game at full weight; whole-game down-weighting (a) discounts the competitive 36 min along with the contaminated 6, and (b) uses final margin as a noisy proxy for *when* the game went non-competitive. Defensible given the engine consumes box scores, not PBP.

**VERDICT:**

| Item | Verdict | Basis |
|---|---|---|
| Margin cutpoints 15/25 | CONFIRMED | 25 = CTG start-of-Q4 garbage-time threshold exactly; 15 = published coach-rest threshold |
| Star weights 0.75/0.90 | CONFIRMED | 25% discount brackets empirical 13.8–18.9% avg loss + ~33% full-Q4 tail |
| Bench weights 0.55/0.75 | CONFIRMED_WITH_CAVEAT | Direction/asymmetry supported; exact magnitudes are judgment values — validate vs held-out bench MAE |
| Sigmoid k=0.15, mid=20.0 | LOCKED | Reproduces E[reduction\|spread] under margin~N(spread,12) to within ~1pp; flattening is required, not tuned |
| max_reduction=0.19 | PERIODIC_RECAL | Matches 18.9% anchor; conservative on spread input; recalibrate with rising league blowout rate |
| MIN_VALID_GAMES=12 | ACCEPTABLE | Consistent with small-sample stabilization warnings; convention, not a calibrated constant |
| Down-weighting vs PBP filtering | DATA_GATED (upgrade) | Correct-direction second-best; PBP stint exclusion is published best practice, gated on acquiring PBP data |

**Condition to Revisit:**
1. If the 20+-margin game rate stays ≥25–30% over a full season, re-run the 24.6k-row sigmoid refit (anchors and cap shift upward).
2. Sigmoid shape is conditional on σ≈12; if realized margin SD exceeds ~13.5–14 (pace/3PT), re-derive the E[reduction|spread] convolution (curve flattens further).
3. If play-by-play feeds are ever ingested, replace Mechanism 1 with CTG-style stint exclusion.
4. At next minutes-scalar refit, test the 0.55/0.75 bench weights vs held-out bench MAE (only weights lacking a direct empirical anchor).
5. If books regularly post spreads ≥22–25 (tanking matchups), verify the sigmoid tail against realized starter minutes — current fit has almost no training mass there.

---

## SECTION 8C — Days-Rest / Fatigue Model

**Question:** Does the days-rest adjustment — 10% max minutes reduction at 0 days rest decaying as `exp(−days/1.5)`, scaled by a role gradient (starter 1.0 → spot 0.75) — match published NBA back-to-back, recovery-kinetics, role-sensitivity, and travel/altitude/density evidence?

**Code ground truth:** `reduction = 0.10 × role_scalar × exp(−days_rest/1.5)`, applied to projected **minutes** only (stats scale downstream). The 1.5 constant is labeled "half-life" but is an **e-folding time** (true half-life = 1.5·ln2 ≈ 1.04 d): 10.0% at 0 days, 5.1% at 1, 2.6% at 2, 1.4% at 3. Role gradient starter 1.0 / sixth_man 0.95 / rotation 0.90 / spot 0.75 / cold_start 0.90. Comment: "calibrated from NBA literature (~3 games data)."

**Findings:**

1. **Team-level B2B scoring effect is small and the modern increase is DNP-driven, not fatigue.** Second-night penalty ~0.5–1.0 pts in the mid-2010s, rising to ~1.0 (home)/~2.5 (road) by 2022-23 — attributed to **strategic star rest (DNP), not played-game fatigue** ([The Data Jocks](https://thedatajocks.com/the-stats-behind-back-to-back-nba-games/); [HeatCheckHQ](https://heatcheckhq.io/blog/nba-back-to-back-rest-analysis)). Efficiency splits tiny: 4th-in-5 ≈ −1.0 pts/100, 3rd-in-4 ≈ −0.1, 2-days-rest ≈ +0.3 ([NBAstuffer](https://www.nbastuffer.com/how-rest-day-stats-can-give-you-the-edge-in-your-nba-predictions/)).

2. **Peer-reviewed congestion effects on PLAYED performance are real but tiny and live in efficiency, not minutes.** Esteves et al. (2021, *Eur J Sport Sci*) found shooting-efficacy stats carried the B2B-vs-rest discrimination ([Tandfonline](https://www.tandfonline.com/doi/abs/10.1080/17461391.2020.1736179)); the 1,230-game congestion study found paint/3PT higher with rest but **trivial effect sizes (Cohen's d ≈ 0.05–0.08)**, possession-normalized, and did **not analyze minutes** ([PMC7925613](https://pmc.ncbi.nlm.nih.gov/articles/PMC7925613/)). Teramoto & Cross (2016): B2B alone did not raise injury rate; away + B2B did ([PubMed 27622705](https://pubmed.ncbi.nlm.nih.gov/27622705/)).

3. **A direct fatigue-modeling paper argues the effect is overstated.** "Tired of Misattribution: Modeling Player Fatigue in the NBA" concluded cumulative fatigue's impact on outcomes is **minimal and overstated** once existing rest management is accounted for ([arXiv:2112.14649](https://arxiv.org/abs/2112.14649)).

4. **Recovery-kinetics literature supports the exponential decay FORM with a ~1-day functional half-life.** Neuromuscular decrements (CMJ) are largest within 24h and **largely recover by ~48h**; biochemical markers (CK) persist ≥72h ([PMC5841509](https://pmc.ncbi.nlm.nih.gov/articles/PMC5841509/)). The Banister fitness-fatigue model is itself two exponential decays with the fatigue constant the shorter ([Humankinetics IJSPP](https://journals.humankinetics.com/view/journals/ijspp/17/5/article-p810.xml)). The model's 1.04-day half-life (~50% by 1 day, ~94% by 4) is consistent; the residual 2.6% at 2 days is mildly high but within noise.

5. **Role gradient direction (starters > bench) is supported; the mechanism risks double-counting.** DFS data: premium ($7k+) players posted −0.44 Plus/Minus on 1-day rest vs +0.72 for the general pool ([FantasyLabs](https://www.fantasylabs.com/articles/nba-the-numbers-on-back-to-backs/)). But much of the star effect is **full DNP-rest (handled by injury status, not this scalar)**; among games stars actually play, the minutes change is modest — so a 10% minutes haircut on a played starter may double-count what the DNP path already removed.

6. **Omitted factors are MATERIAL — several rival or exceed the 10% B2B effect.** Roy & Forest (2018, *J Sleep Res*): NBA road teams traveling eastward won 45.4% vs 36.2% westward — a **~9pp swing** ([Wiley](https://onlinelibrary.wiley.com/doi/abs/10.1111/jsr.12565)); Charest et al. (2021, *JCSM*): eastward travel significantly raises B2B win probability ([JCSM](https://jcsm.aasm.org/doi/10.5664/jcsm.9446)); Denver altitude produces the **largest home edge in major sports (~67% win prob), ~5 days to acclimate** ([Sportico](https://www.sportico.com/leagues/basketball/2024/denver-nuggets-home-court-advantage-1234777526/)). 4th-in-5 ≈ −1 pt/100 ([NBAstuffer](https://www.nbastuffer.com/rest-days-factor-nba-scheduling/)). The model intentionally omits all three.

**VERDICT:**

| Item | Verdict | Basis |
|---|---|---|
| `max_reduction=0.10` (minutes) | **NEEDS_CHANGE** (likely too high for *played* games) | Published played-game B2B effects ~0.5–1 pt / d≈0.05–0.08; "Tired of Misattribution" finds impact minimal; most of the visible 10%+ swing is DNP-driven (handled elsewhere) |
| Decay FORM (exponential) | CONFIRMED | Banister fitness-fatigue + team-sport recovery kinetics are exponential |
| 1.5 e-folding / ~1.04-d half-life | CONFIRMED_WITH_CAVEAT | Implied curve (~50% by 1d, ~94% by 4d) consistent with neuromuscular recovery by ~48h; 2.6% at 2 days mildly high |
| Role gradient (starter 1.0 > spot 0.75) | CONFIRMED_WITH_CAVEAT | DFS data confirm direction; star effect largely realized as DNP → double-count risk on played starters |
| Minutes-only channel | CONFIRMED_WITH_CAVEAT | Minutes (coach rest-mgmt) is the dominant box-score channel; tiny per-minute shooting decline uncaptured (acceptable given effect size) |
| Travel / altitude / density omissions | **NEEDS_CHANGE** (material) | Westward ~9pp swing; Denver altitude largest HCA in sports; 4-in-5 ≈ −1 pt/100 — each rivals the modeled B2B effect |
| "half_life" naming | **NEEDS_CHANGE** (cosmetic/doc) | Constant is e-folding time, not half-life (off by ln2); rename or convert |
| Overall calibration ("~3 games data") | DATA_GATED | Literature-derived prior defensible *as a prior*; in-sample validation essentially absent |

**Condition to Revisit:**
1. **Validate at n≥500 B2B player-games:** regress actual-minus-projected MINUTES residual by days-rest bucket (0/1/2/3+), restricting to players who appeared (exclude DNPs to avoid double-counting the injury path). If the played-game 0-day residual is materially below 10%, cut `max_reduction` toward the empirical value.
2. **Decompose the channel:** check per-minute PTS/3PM efficiency residuals by rest bucket; if non-trivial, add a small per-minute efficiency multiplier rather than loading everything onto minutes.
3. **Re-examine the role gradient** at n≥100/role on *played-game* residuals; compress the spread if it flattens (star rest absorbed by DNP).
4. **Add the material omissions:** altitude flag (Denver/Utah), eastward/westward travel term, 3-in-4 / 4-in-6 density. Prioritize altitude and westward travel.
5. **Rename `DAYS_REST_HALF_LIFE`** to e-folding semantics (or `/ln2` to a true half-life) at the next calibration touch.
6. Immediate review if a graded-pick audit shows systematic over/under on B2B props keyed to days_rest, or after any Player Participation Policy change.

---

## SECTION 8D — Bayesian Positional REB Priors

**Question:** Do the two Bayesian rebounding prior systems — the decomposed OREB%/DREB% path (System 1, N=5) and the per-minute total-REB baseline path (System 2, N=12, cold-start only) — match published positional rates, stabilization/padding research, and standard ORB%/DRB% decomposition?

**Code ground truth:** `proj_reb = 0.45·decomposed + 0.55·baseline`. System 1 (`nba_projector.py:675-725`) shrinks an EWMA(span=10) of `oreb/(team_misses·min/48)` and `dreb/(opp_misses·min/48)` toward positional priors **for every player**: `rate = (n·ewma + 5·prior)/(n+5)`. System 2 (`:1466-1494`) applies `_REB_RATE_PRIOR` **only at `_reb_n_games==0`** (cold-start) — so N=12 never partial-pools and the prior value is the entire cold-start anchor. Implied per-36 from System 2: PG 1.91 / SG 2.05 / SF 2.84 / PF 4.00 / C 5.94.

**Findings:**

1. **System 2 per-minute priors are deflated ~1.8–2.4× by a per-game-vs-per-36 units error — broader than the H01 "C needs re-query" note.** Real positional REB/36 ([StatMuse 2024-25](https://www.statmuse.com/nba/ask/average-rebounds-per-36-minutes-by-position-in-the-2024-25-regular-season)): PG 4.6 / SG 4.75 / SF 6.04 / PF 7.57 / **C 11.17**; 2023-24 and 2025-26 nearly identical. Model implied per-36: 1.91 / 2.05 / 2.84 / 4.00 / **5.94** — roughly half. The model's own DB (per-player, min≥10, equal-weight) confirms reality not the prior: SG 4.67 / SF 6.60 / PF 10.07 / **C 11.36 per-36** — bench inclusion does *not* explain the gap. The code comment's "REB/36: PG=2.6…C=6.0" matches StatMuse's **per-game** column, not per-36 — i.e. per-game figures were treated as per-36 and divided by 36. **All five positions** are deflated; C should be ≈0.30, not 0.165. Blast radius is bounded (value feeds only cold-start n=0 players' baseline path at 0.55 weight) but it under-projects rebounds for those players, worst for bigs.

2. **N=5 (decomposed, live) is consistent with published REB% stabilization; 12→5 rollback correct; N=12 (baseline) is moot.** [kmedved's padding table](https://kmedved.com/2020/08/06/nba-stabilization-rates-and-the-padding-approach/): orb_pct padding = 98.55 possessions, drb_pct = 108.26 (vs fg3_pct 242.61) — rebounding stabilizes *fast*, ≈1.3–1.8 games of league-average prior at ~60–75 poss/game. Rebounding evaluable in [~8–10 games](https://www.breakthroughbasketball.com/stats/rebounding-stats). N=5 sits slightly above kmedved's ~1.5-game equivalent — defensible, mildly conservative. N=12 on System 2 is academic (n>0 bypasses it).

3. **Playoff direction correct in aggregate (centers/PF down, guards flat-to-up), with one positional miss.** Per-36 RS→PO ([2025 PO](https://www.statmuse.com/nba/ask/average-rebounds-per-36-minutes-by-position-in-the-2024-playoffs)): C 11.17→9.82 (−12%), PF 7.57→6.85 (−10%), SF 6.04→6.03 (flat), SG 4.75→5.0 (+5%), PG ~flat. Model PO/RS ratios: C −19%, PF −17%, **SF −16% (but SF is empirically flat)**, SG +5% (spot-on), PG +6% (slightly high). Mechanism (lower playoff pace → fewer chances/min for bigs; guard gang-rebounding rises) is real and borne out, except SF is over-deflated.

4. **Uniform N=5 across positions is acceptable, not optimal.** Hierarchical theory shrinks ∝ within-player-noise/between-player-signal; bigs have larger between-player rebounding variance → theory favors *lower* N for C. But published practice uses a single per-stat padding ([kmedved](https://kmedved.com/2020/08/06/nba-stabilization-rates-and-the-padding-approach/)), and the [Bayesian two-stage rebounding paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12671482/) uses a uniform prior SD with no position split. At N=5 with ~20-game samples the prior is only ~20% of the estimate — second-order.

5. **REB_ALPHA=0.45 — nothing rebounding-specific overturns Plan 7 §7G LOCKED.** Shared minutes input → correlated errors → flat combination-loss surface. The only nuance (baseline path mis-anchored for cold-start) is fixed by correcting the prior value, not by retuning a global alpha.

6. **Opportunity-denominator design is the published standard.** Basketball-Reference defines ORB% over `Tm ORB + Opp DRB` (team misses) and DRB% over `Tm DRB + Opp ORB` (opponent misses), per Oliver/Kubatko ([B-Ref glossary](https://www.basketball-reference.com/about/glossary.html)). The code's `team_misses = tm_fga − tm_fgm + 0.44·tm_fta` scaled by `min/48` is precisely the missed-FG-equivalent availability pool. Separate OREB/DREB rates with distinct timescales also match kmedved.

**VERDICT:**

| Item | Verdict | Basis |
|---|---|---|
| System 1 OREB%/DREB% prior values | CONFIRMED | C OREB 0.070 / DREB 0.172 plausible vs kmedved league avg orb 0.051 / drb 0.148; rate-basis calibration unaffected by the per-game mislabel |
| System 2 per-minute prior values (incl. H01) | **NEEDS_CHANGE** | Deflated ~1.8–2.4× vs true per-36 (C 5.94 vs ~11.2); quoted "REB/36" ratios are actually per-game; **all five positions** need re-derivation, not just C |
| N=5 (decomposed, live) | CONFIRMED | kmedved orb/drb padding ≈100 poss (~1.5 games); 12→5 rollback evidence-backed |
| N=12 (baseline path) | ACCEPTABLE | Dead parameter — only n=0 hits this branch, where shrunk≡prior |
| PO-vs-RS direction | CONFIRMED_WITH_CAVEAT | C/PF down, SG up confirmed (SG +5% spot-on); model drops SF −16% but SF is empirically flat; PG slightly high |
| Uniform-N across positions | ACCEPTABLE | Theory mildly favors lower-N for bigs; published practice uses single per-stat padding; second-order at N=5 |
| Opportunity-denominator design | CONFIRMED | Matches Oliver/Kubatko ORB%/DRB% (B-Ref glossary); 0.44·FTA missed-shot pool standard |
| REB_ALPHA=0.45 | LOCKED (upheld) | No rebounding-specific factor overturns §7G combination-puzzle verdict |

**Condition to Revisit:**
1. **Fix System 2 (this is the real content of H01, broadened to all positions):** re-derive `_REB_RATE_PRIOR_RS/PO` from true positional **per-36** (RS ≈ PG 0.128, SG 0.132, SF 0.168, PF 0.210, **C 0.305** per-minute; recompute PO by the existing G×1.054/F×0.832/C×0.806 scalars). Backtest cold-start (taxi/returner) REB bias before/after — the 0.55 baseline weight makes the current under-projection real for those players.
2. Re-query StatMuse positional **per-36** (not per-game) and fix the mislabeled code comment at line 395.
3. July refit: re-fit System 1 OREB/DREB priors on the latest 2-season DB (min≥10); re-confirm N=5 against an updated kmedved-style padding fit on the model's own data.
4. If a cold-start-REB backtest shows the decomposed path materially better-calibrated than the corrected baseline for n=0 players, consider a cold-start-specific REB_ALPHA bump (not a global change).
5. Revisit the SF playoff deflator — model −16% vs empirical ~flat; re-fit PO priors when the playoff sample grows.

---
