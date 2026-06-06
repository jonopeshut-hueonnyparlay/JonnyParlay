# MARKET FOUNDATIONS — Plan 9 Audit

**Date:** 2026-06-06
**Scope:** Market-facing assumptions of the betting engine — NRFI/YRFI model, anti-correlation filters, CLV methodology, SLOW_BOOKS exploitation, parlay construction (Daily Lay / Longshot / SGP), tier system, hard card rules, daily cap structure.
**Method:** Each section's constants/assumptions verified from source (`engine/run_picks.py`, `engine/mlb_sgp_builder.py`, `engine/capture_clv.py`, `engine/clv_report.py`), then validated against published research via 6 parallel Opus web-search agents.
**Companion doc:** `docs/research/STATISTICAL_FOUNDATIONS.md` (Plans 1–6: distributions and projection constants).

**Verdict taxonomy:**
- **LOCKED** — validated; leave alone. Changes must cite evidence overriding this doc.
- **PERIODIC_RECAL** — validated but refit on a stated schedule.
- **DATA_GATED** — cannot validate without more data; gate defined.
- **NEEDS_CHANGE** — evidence contradicts current implementation; fix stated.

---

## Summary Verdict Table

*(populated as sections complete)*

| § | Item | Current | Verdict | Action |
|---|------|---------|---------|--------|

---

## Code-vs-plan-doc corrections (Phase 0 verification, 2026-06-06)

Before research, every constant in the Plan 9 spec was re-read from source. Corrections vs the plan document:

| Item | Plan doc said | Code actually says |
|---|---|---|
| `MIN_LEG_WIN_PROB` (MLB SGP) | 0.60 | **0.65** (mlb_sgp_builder.py:70) |
| `CLV_REFORM_DATE` | in capture_clv.py | **clv_report.py:57** = "2026-05-31" |
| `--late-run` flag | run_picks.py | lives in **EdgeModel** generate_projections.py; only the `SLOW_BOOKS` frozenset is in run_picks.py:795 |
| Daily Lay leg count | 3-leg | code builds **2–4 legs** (run_picks.py:4250–4299) |
| X2 filter (K over + HITS over) | "verify status" | **confirmed retired/absent** — only X1 exists in filter_cross_type_correlations() |

All other plan-doc values matched code exactly (NRFI constants, YRFI min_edge, Daily Lay thresholds, longshot caps, tier mults, 12u/sport caps, SGP odds window, CLV capture windows).

---

## §9A — NRFI Model

**Current implementation** (run_picks.py:3523–3647):
- Poisson λ model: `λ_team = BASE_LAMBDA_1ST × (pitcher_blended_rate / 0.477) × (team_runs / 4.45)`; `P(NRFI) = exp(−λ_away − λ_home)`
- `BASE_LAMBDA_1ST = 0.32` (avg matchup → P(NRFI) ≈ 53%); `_LEAGUE_AVG_BLENDED_RATE = 0.477` (0.40×ERA/9 + 0.60×FIP/9); `_LEAGUE_AVG_RUNS = 4.45`
- Park factor intentionally omitted (SaberSim team-run inputs already park-adjusted)

*(findings pending — agent A)*

---

## §9I — YRFI Model

**Current implementation** (run_picks.py:3648, 3694, 3888–3890):
- `p_yrfi = 1.0 − p_nrfi`; YRFI min_edge = 0.08 vs NRFI min_edge = 0.06 (T3 floor)
- R5 dedup: NRFI + YRFI same game never both posted (lower pick_score dropped)

*(findings pending — agent A)*

---

## §9B — MLB Anti-Correlation Filter (X1)

**Current implementation** (run_picks.py:3933–3978):
- X1 (HARD): pitcher HA/ER UNDER + opposing TEAM_TOTAL OVER same game → pair killed from parlay/longshot pool (assumed ρ ≈ −0.65 to −0.75)
- X2 retired with K stat. SGP-module kills (R2_MLB) are separate.

### Q1 — Is ρ ≈ −0.65 to −0.75 the right magnitude?
No published source gives the exact game-level corr(SP HA/ER, opp full-game runs) — DFS correlation tools and SGP pricing keep it behind paywalls. Variance decomposition bounds it:
- SP innings share: **5.22 IP/start (2024)** ≈ 58% of a 9-inning game ([AP/FanGraphs](https://blogs.fangraphs.com/a-deeper-dive-into-pitcher-usage-trends/)); ρ(runs-off-SP, total runs) ≈ √0.58 ≈ 0.76 (opposing adjustments — early hooks vs shared run environment — roughly cancel).
- Hits→runs linkage: season-level BA→runs r≈0.82 ([Bucknell study](https://www.eg.bucknell.edu/~bvollmay/baseball/runs1.html)); game-level conventionally ~0.65–0.75 (sequencing noise).
- **ER**: ρ ≈ 0.95 × 0.76 ≈ **0.65–0.75** ✅ — engine's band is plausible for ER.
- **HA**: extra hits→runs translation step ⇒ ρ ≈ 0.70 × 0.76 ≈ **0.45–0.60** ❌ — engine's band overstated by ~0.10–0.20 for HA.
- Materiality: **zero for behavior** — X1 is a hard block, and even ρ=−0.45 destroys parlay joint EV at engine edge scale (Q4). Note: the in-house DB can settle this exactly — `mlb_pitcher_game_stats` (69k rows) × `mlb_games` final scores in one query.

**Verdict: LOCKED** (ER band) / **PERIODIC_RECAL** (HA band — re-document as ≈ −0.45 to −0.60; fit empirically in-house at July refit; no behavior change).

### Q2 — Sign + hard-block treatment
Sign confirmed. Books historically blocked correlated parlays outright and now reprice them inside SGP engines via copulas ([Wizard of Odds — SGP correlation math](https://wizardofodds.com/article/same-game-parlays-the-mathematics-of-correlation/), OpticOdds, USPTO 12,080,130). Crucially, books do **not** pay proportionally higher odds for negatively correlated combos — so a bettor-side pool pricing payout as independent-product while true joint prob is copula-reduced is structurally −EV on such pairs. Hard exclusion is the correct bettor-side treatment. **Verdict: LOCKED.**

### Q3 — Other anti-correlation candidates (unblocked)
- **(a) OUTS over + same-SP HA over**: exposure effect (more BF → more hits) vs the hook (high hit rates → pulled early) largely cancel; expected |ρ| < 0.2. **DATA_GATED** — compute corr(outs, hits_allowed) on 16k starts in-house before any rule; likely no rule needed.
- **(b) OUTS under + opp TT over**: **positively** correlated (~+0.3–0.4 — SP knocked out early *because* opp scoring). Independence **understates** joint prob → engine under-ranks/under-sizes a combo that's actually better than modeled. Conservative, not dangerous. Key asymmetry: independence on negative-ρ pairs overstates EV (must block — X1 does); on positive-ρ pairs it understates EV (safe to allow). **NEEDS_CHANGE (minor, optional)**: add a +ρ term to the longshot joint-prob estimate for ranking honesty, mirroring mlb_sgp_builder's OUTS-over/HITS-under=+0.30. Never block.
- **(c) ER under + same team ML**: positive ρ ~+0.35–0.45 (NFL analogue: Team Win ↔ QB over ρ=0.35, Wizard of Odds). Independence conservative. **DATA_GATED** — fit in-house, fold into copula when convenient; no block.
- **(d) NBA player PTS/3PM over + same-game TOTAL under** (ρ ≈ −0.2 to −0.4): the most material *unblocked negative* pair if NBA props and totals co-occur in the longshot pool. **DATA_GATED** — check pick_log for actual co-occurrence in longshot legs before adding an NBA X2; per-game cap of 2 bounds exposure. NHL pairs weak/moot (SOG suspended).

### Q4 — Hard block vs copula soft-pricing
Two contexts, and the engine's architecture already splits them correctly:
1. **Parlay (multiplicative payoff)**: at ρ=−0.5, two p=0.60 legs have joint 0.30 vs 0.36 independent (damage ≈0.81) → each leg needs **>~11% edge** to survive; at ρ=−0.65/−0.75, **~16–20% edge**. Engine prop edges run 3–8% — an order below breakeven. A copula soft gate would re-admit essentially zero pairs while adding model risk.
2. **Straight-bet portfolio**: negative correlation *reduces* variance — simultaneous-Kelly theory ([Whitrow 2007 JRSS-C](https://vegapit.com/article/numerically_solve_kelly_criterion_multiple_simultaneous_bets/); Baker & McHale 2013) says negatively correlated straights can size *up*. X1 kills the pair only from the parlay pool while both legs stay available as straights — exactly the optimal split. (Corollary: straight-pick Kelly treats same-game positive-ρ picks as independent, slightly oversizing — swamped by the 0.25u quantization and ~1/16.7 Kelly scaling.)

**Verdict: LOCKED** — hard block is not too conservative at this engine's edge scale.

### §9B Verdicts

| Item | Current | Verdict | Action |
|---|---|---|---|
| X1 hard block (HA/ER under + opp TT over) | HARD kill | LOCKED | None — sign correct, treatment standard, optimal at engine edge scale |
| X1 documented ρ for ER | −0.65 to −0.75 | LOCKED | Plausible (0.95 × 0.76 ≈ 0.72) |
| X1 documented ρ for HA | −0.65 to −0.75 | PERIODIC_RECAL | Overstated; true ≈ −0.45 to −0.60. Re-document + in-house fit at July refit. No behavior change |
| OUTS over + same-SP HA over | Unblocked | DATA_GATED | In-house corr on 16k starts; expected \|ρ\|<0.2 → no rule |
| OUTS under + opp TT over | Independent | NEEDS_CHANGE (minor) | Positive ρ understates joint prob (conservative). Optional +ρ in longshot joint-prob; never block |
| ER under + same team ML | Independent | DATA_GATED | ρ ~+0.35–0.45; fit in-house, fold into copula later |
| NBA player-over + TOTAL-under | Unblocked | DATA_GATED | Check pick_log co-occurrence before adding NBA X2 |
| Hard block vs copula | Hard block | LOCKED | Breakeven needs 11–20% per-leg edges; engine has 3–8% |

---

## §9C — CLV Capture Methodology

**Current implementation** (capture_clv.py:16–18, 168–171; clv_report.py:57):
- Window: T−45 min → T+3 min capture; CLV written only within T−10 of start; 2-min poll
- Post-reform (CLV_REFORM_DATE=2026-05-31): CLV = vig-free closing prob − raw vigged entry implied. Vig-free computed on the closing side only (proportional devig over both sides of the closing market).

### Q1 — Window and write gate
Published consensus (Miller/Davidow *The Logic of Sports Betting*; Buchdahl's Pinnacle efficiency study, 87,960 odds pairs): the close = the last price before the event starts. No published standard exists for a T+3 tail — it's a pragmatic guard against feed/clock skew. With a 120s poll, the last pre-suspension snapshot is within ~2 min of the true close — well inside literature precision. The T−10 write gate captures exactly the window the literature treats as the close.
**One real risk**: markets that flip to in-play at start (totals/spreads especially) — a T+0→T+3 snapshot can return **live odds**, which are not the close. Props are usually delisted at start (benign failure: missing close), but game lines are not.
**Verdict: LOCKED**, with one hardening item: discard (or use only as last-resort fallback) any snapshot with capture_time > commence_time.

### Q2 — Mixed devig formula: NOT a pitfall (the suspected defect is inverted)
The plan hypothesized that devigged-close-minus-raw-entry systematically shifts CLV positive. **The premise is inverted — the current formula is the methodologically correct EV estimator, and it shifts CLV *negative* (conservative).**
- Math: realized EV per unit = p_true × d_entry − 1 > 0 ⟺ p_true > raw vigged entry implied. Best estimate of p_true = devigged close. So **CLV = devig(close) − raw(entry)** has its zero point exactly at zero EV — the engine's post-reform formula.
- Buchdahl: "if you are beating the closing no-vig-price, your bets should hold expected value" — validated on his ~20,000-bet record (realized 3.4% vs expected 4.0%). [Unabated "Getting Precise About CLV"](https://unabated.com/articles/getting-precise-about-closing-line-value): "If you don't compare your bet against a vig-free closing line, you're misrepresenting your CLV" — i.e., the pitfall is raw-vs-raw, and **devig-both would be the error** (puts the zero at "no line movement", overstating edge by the entry vig share ~2.3pp at −110).
- A bet whose line never moves shows CLV ≈ −2.4pp under the current formula — correctly flagging that betting into a static vigged market is −EV by the vig.
- Bookkeeping caveat: pre-reform rows (raw close) sit ~+2–2.5pp relative to post-reform rows — **never pool across CLV_REFORM_DATE** in one mean; the go-live count should include only post-reform rows.
**Verdict: LOCKED.** No formula change.

### Q3 — Devig method (multiplicative vs power vs Shin)
Methods diverge with odds asymmetry, not vig level. At −110/−110 identical; at −150/+120 (~5.4% overround) mult vs power differ ~0.3pp. Published ~1pp divergences come from 1.25/4.20-style lopsided markets — far beyond any priced prop. **Verdict: LOCKED** for the prop/total population; **PERIODIC_RECAL trigger**: switch to power devig if CLV is ever computed on |odds| ≥ 200 markets (ML dogs, alt lines).

### Q4 — Significance at small n (the math)
Buchdahl/Pinnacle: CLV separates skill from noise far faster than W/L ("as few as 50 bets" — but conditional on ~4% effect size). For this engine, in probability points (t = x̄√n/σ):

| avg CLV | σ/bet | n | t | p (two-sided) |
|---|---|---|---|---|
| +0.004 | 0.025 | 63 | 1.27 | 0.21 |
| +0.004 | 0.025 | 100 | 1.60 | 0.11 |
| +0.004 | 0.020 | 100 | 2.00 | 0.046 ✓ |
| +0.010 | 0.025 | 100 | 4.00 | <0.001 ✓ |

n for t=1.96 at x̄=+0.4pp: **96 / 150 / 216** at σ = 2.0/2.5/3.0pp — the 100-row gate sits exactly at the edge. Caveats: same-slate picks have correlated line moves (deflates effective n; t is anti-conservative), and the statistic must use post-reform rows only.
**Verdict: DATA_GATED** — at gate time, augment the fixed n=100 with a one-sided t-test (t ≥ ~1.7) on post-reform rows. At +0.4pp expect ~150–200 rows needed; at +1pp, ~25–40.

### Q5 — Prop CLV vs soft-book closes
The weakest link, well documented. Jack Andrews (Unabated): "**CLV doesn't mean anything in props**… very few market-making books… not a lot of sharp money… that makes it less efficient." Buchdahl's slope≈1.00 CLV→realized-EV result was proven on **Pinnacle soccer mainlines**; no equivalent validation exists for DK/FD/MGM prop closes. Counterweight: FD has sharpened on props via volume, and prop closes do absorb injury news — soft-book prop CLV is *directionally* informative but noisy. Implications: (a) per-bet CLV SD larger → Q4 t-test is a floor; (b) graded shadow W/L must carry ≥ equal weight in the go-live decision (parallel shadow grading already does this); (c) a **multi-book consensus devigged close** is strictly better than single-book when ≥2 books quote the prop.
**Verdict: PERIODIC_RECAL** — keep capturing; treat the CLV gate as supporting evidence subordinate to graded W/L; consider consensus-close upgrade.

### §9C Verdicts

| Item | Current | Verdict | Action |
|---|---|---|---|
| Capture window | T−45→T+3, write T−10, 120s poll | LOCKED | Harden: discard post-commence snapshots (live-odds contamination on game lines) |
| CLV formula | devig(close) − raw(entry) | LOCKED | None — published best practice; zero point = zero EV. Keep pre/post-reform rows segregated |
| Devig method | Multiplicative, close side | LOCKED | Power devig only if \|odds\| ≥ 200 markets enter CLV; immaterial at prop odds |
| Go-live gate | n=100 CLV rows | DATA_GATED | Add one-sided t-test (t ≥ ~1.7) on post-reform rows at gate; +0.4pp avg ⇒ ~150–200 rows |
| Prop CLV validity | Soft-book closes | PERIODIC_RECAL | Subordinate to graded W/L; consider multi-book consensus close |

---

## §9D — SLOW_BOOKS Exploitation

**Current implementation** (run_picks.py:795):
- `SLOW_BOOKS = {"fanatics", "hardrockbet", "betrivers"}` — assumed 15–40 min injury-news repricing lag; exploited via EdgeModel `--late-run` re-fetch. Lag estimates assumed, not measured.

### Q1 — Do operators demonstrably differ in repricing speed?
The two-tier structure (market-makers originate, retail follows with delay) is real and well-documented; the lag magnitude for **props** is plausibly 20–40 min, but for major game lines it has shrunk to seconds–minutes. The specific 3-book membership of SLOW_BOOKS is NOT validated by any public source.
- **Levitt (2004)**, *Economic Journal* 114(495): bookmakers announce a price, after which "adjustments are small and infrequent" — retail books are *price-setters with sticky prices*, not continuous repricers. Staleness is endogenous to their business model. ([PDF](http://pricetheory.uchicago.edu/levitt/Papers/LevittWhyAreGamblingMarkets2004.pdf))
- **Ottaviani & Sørensen (2005–2009)**: posted prices systematically deviate from fair value; informed bets cluster late — theoretical support for the `--late-run` window. ([Timing of Bets and the FLB](https://web.econ.ku.dk/sorensen/Papers/tobaflb.pdf))
- **Croxson & Reade (2014)**, *EJ* 124(575): exchange prices incorporate major news within seconds — the efficiency benchmark retail lag is measured against.
- Post-PASPA practitioner consensus (Unabated, EdgeSlip, Outlier): market-makers (Pinnacle/Circa) originate; retail follows — but **major game line lag is now <60s**; a Princeton live-NBA-arb thesis found arb windows averaging ~13 seconds.
- **Player props after injury news are the genuine slow lane**: practitioner sources describe books that "lag by 20 to 40 minutes" on props ([Shurzy](https://content.shurzy.com/post/comparing-player-prop-odds-across-sportsbooks)) — consistent with the engine's 15–40 min assumption *for props specifically*.
- **Counter-evidence on membership**: Fanatics is reviewed as "extremely quick on line movements" with *lower* avg prop vig (4.74%) than BetRivers (5.94%) ([OddsAssist](https://oddsassist.com/sports-betting/sportsbooks/fanatics/)); it runs the former PointsBet tech stack. No public source ranks Fanatics/Hard Rock/BetRivers as the three slowest.

**Verdict: PERIODIC_RECAL** (premise — structurally sound, props-specific) / **DATA_GATED** (membership + lag numbers).

### Q2 — Sustainability
The edge is durable at the **market** level but self-eroding at the **account** level. Books respond with limits, not faster tech — and limits arrive fast:
- Classic "top-down"/steam-chasing pattern; some books ban/limit steam-chasers *before* traditional sharps (SportsBettingDime, Boyd's, betstamp).
- Rose-Berman ("[The Truth About Limits](https://howgamblingworks.substack.com/p/the-truth-about-limits)"): winners identified "within hours of signing up"; limited users capped ~$200 majors, **~$50 props**. ESPN documents operators defending the practice; Spanky's saga (The Ringer 2019); MA Gaming Commission data shows limiting concentrated on winners.
- Hard Rock specifically noted for limiting consistent winners (OddsAssist).
- Two erosion vectors: per-account ($50 prop limits neuter the strategy) and secular (retail latency shrinking; props lag persists only because prop volume is small and trading-desk attention rationed).

**Verdict: PERIODIC_RECAL.** Action: log per-book bet-acceptance/limit events as a first-class signal; a SLOW_BOOKS book that limits the account is effectively removed from the exploit set.

### Q3 — Legality / ToS (Colorado)
Betting on **public** injury news before a book reprices is legal in Colorado. No insider-trading analogue exists in sports betting.
- CO prohibited-conduct rules (1 CCR 207-2; C.R.S. 44-30-1506) target prohibited participants (athletes, officials, insiders) and proxy betting — not speed-of-reaction to public news. ([CO Division of Gaming rules](https://sbg.colorado.gov/sites/sbg/files/documents/1CCR%20207-2%20SB%20Combined%20Rules%20061424.pdf))
- Even courtsiding (live in-venue data relay) is not US-illegal — venue ToS issue only. The engine's behavior is more benign: pre-game, public, published news.
- **Commercial risk 1 — limiting**: fully legal in CO. **SB26-131** (signed 2026-06-02, effective **2026-08-12**) is consumer-protection only: credit-card deposit ban + max 6 deposits/24h — operationally relevant to bankroll funding from August; does NOT restrict limiting.
- **Commercial risk 2 — obvious-error voiding**: CO Rule 6.10 lets operators void wagers on "obvious error" per their house rules. A stale line hit right after major injury news is the textbook voidable case — expect occasional voids on the best late-run hits (P&L haircut, not legal exposure).

**Verdict: LOCKED** (legality). Document the commercial-risk pair as known costs.

### Q4 — Measurement protocol (lag is assumed, not measured)
No per-operator lag measurement exists publicly; the engine is unusually well-positioned to produce one:
1. **Events**: timestamped material injury changes (top-3-usage OUT/IN flips, late scratches) from official NBA injury report + first-reporter timestamps.
2. **Odds**: extend the existing 2-min CLV daemon to snapshot all CO books on watched events; backfill via The Odds API historical endpoint (5-min snapshots, props from May 2023).
3. **Lag definition**: time from the *sharp-reference move* (Pinnacle first repricing/pull — not the tweet) to the book's first move ≥ threshold or suspension. Isolates follower latency from news-detection latency.
4. **Sample**: ≥30 material events per book; stratify props vs game lines.
5. **Cheap passive validation now**: pick_log.csv already has `book` + `clv` — compare CLV of late-run picks at SLOW_BOOKS vs other books; ~50 graded late-run rows/book gives a first read with zero new infrastructure.
6. **Decision rule**: keep a book in SLOW_BOOKS only if median prop lag ≥ 10 min AND late-run CLV > 0. Fanatics is the most likely member to fail.

**Verdict: DATA_GATED** — both the 15–40 min values and per-book membership. Until measured, SLOW_BOOKS is a hypothesis, not a constant.

### §9D Verdicts

| Item | Current | Verdict | Action |
|---|---|---|---|
| Slow-books premise (retail prop-repricing lag) | Assumed | PERIODIC_RECAL | Literature-backed for props; game lines now reprice in seconds. Re-check annually — latency windows shrinking. |
| SLOW_BOOKS membership {fanatics, hardrockbet, betrivers} | run_picks.py:795 | DATA_GATED | No source validates these three; Fanatics has counter-evidence. Gate on Q4 measurement. |
| 15–40 min lag estimate | Assumed | DATA_GATED | Event-study ≥30 events/book; passive gate ~50 late-run CLV rows/book from pick_log. |
| Edge sustainability | Assumed durable | PERIODIC_RECAL | Account-eroding (limits, ~$50 prop caps documented). Log per-book limit events; drop limited books. |
| Legality (CO, public news) | — | LOCKED | Legal under 1 CCR 207-2. Known commercial risks: limiting + Rule 6.10 obvious-error voids. |
| SB26-131 ops impact (2026-08-12) | Untracked | NEEDS_CHANGE (ops) | Credit-card deposit ban + 6 deposits/24h cap — adjust bankroll funding workflow before Aug 12, 2026. Not a code change. |

---

## §9E — Daily Lay Architecture

**Current implementation** (run_picks.py:192–199, 4250–4299, 5140–5165):
- 2–4 leg alt-spread parlay; MIN_DAILY_LAY_PROB=0.50 (combined); per-leg edge ≥0.025, cover_prob ≥0.58, projected margin ≥4.0; max combined odds +100; quarter-Kelly sizing clamped 0.25–0.75u

*(findings pending — agent E)*

---

## §9F — Tier System Design

**Current implementation** (run_picks.py:729, 1214–1221):
- T1 (AST/SOG/REC/HRR) min_edge=0.03 mult=0.90 · T1B (REB/HITS/HA high-line unders) 0.03/0.93 · T2 (PTS/PRA/OUTS/SV/…) 0.05/1.00 · T3 (3PM/GOALS/NRFI/YRFI/ML_DOG/…) 0.06/0.95
- pick_score = 0.40·wp_n + 0.60·e_n, e_n capped at 100 (15% edge ceiling)
- Performance (2026-05 gate audit, plan-supplied): T1 46.6% WR/−10.2% ROI · T1B 46.9%/+1.7% · T2 60.3%/+14.0% · T3 51.5%/+5.3%

*(findings pending — agent F)*

---

## §9G — Longshot Parlay Construction

**Current implementation** (run_picks.py:200–202, 4136–4233):
- 6 legs, safest-by-win_prob descending; max 2 legs/game, 1 leg/player; flat 0.25u; legs treated as independent (no copula). VALUE_PARLAY 5-leg fallback, same caps, 0.25u.

*(findings pending — agent E)*

---

## §9H — SGP Thresholds

**Current implementation** (mlb_sgp_builder.py:65–71, 199–223, 303–318):
- 3–4 legs; per-leg WP ≥0.65 (OUTS ≥0.62); combined odds +200–+450; Gaussian copula joint prob (ρ table: OUTS-over+opp-HITS-under=0.30, same-team batters=0.15, two pitchers=0.10, cross-team batters=0.08, default 0.02)
- Premium 0.50u iff copula EV margin ≥0.10 AND avg_edge ≥0.035; else 0.25u. R2_MLB kill: OUTS-under + HITS-under same game.

*(findings pending — agent E)*

---

## §9J — Hard Rules (R4/R7/R9/R10/R12)

**Current implementation** (run_picks.py:1544–1750, 1602, 6723–6730):
- R4: REB overs (and REB unders ≤2.5) → shadow log, not posted
- R7: max 2 picks/game per card (default arg)
- R9: directional balance — if ≥3 overs passed gates but 0 on premium card, force best over in
- R10: max 1 pick per stat on Premium 5
- R12: 5-day cooldown on players whose pick lost (auto-merged from pick_log)

*(findings pending — agent F)*

---

## §9K — Daily Unit Cap Structure

**Current implementation** (run_picks.py:733, 1763–1782):
- Daily total cap 12u (all run types); SPORT_UNIT_CAP per pick: NBA=8, MLB=8, NHL=5, NFL=5, WNBA=4; STAT_CAP default 2/run (SOG 6)
- KELLY_FRACTION=6.0 on 100u convention ⇒ ≈1/16.7 Kelly; sizes rounded 0.25u, floor 0.50u (0.25u T3)

*(findings pending — agent F)*
