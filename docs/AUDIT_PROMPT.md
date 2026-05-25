# JonnyParlay Full System Audit Prompt

Paste into a fresh Claude Code session. This covers every layer of the engine.
Read CLAUDE.md first for system context before starting.

**Scope:** `engine/run_picks.py`, `engine/grade_picks.py`, `engine/capture_clv.py`,
`engine/clv_report.py`, `engine/sgp_builder.py`, `engine/weekly_recap.py`,
`engine/results_graphic.py`, `engine/analyze_picks.py`, `engine/pick_log_schema.py`,
`engine/pick_log_io.py`, `engine/name_utils.py`, `engine/book_names.py`,
`engine/calibrate_platt.py`, `engine/calibrate_winprob.py`, `engine/nb_calibrate.py`,
`engine/empirical_analysis.py`, `data/pick_log.csv`.

**Out of scope:** `engine/nba_projector.py`, `engine/projections_db.py`,
`engine/injury_parser.py`, `engine/generate_projections.py`, `engine/backtest_projections.py`,
`engine/lineup_fetcher.py` — projection system is audited separately.

**Crash protection — mandatory:** After completing each track, immediately write findings
to `docs/audits/audit_YYYY-MM-DD_trackX.md` and run `git add -A && git commit -m "audit: track X findings"`.
Do not wait until all tracks are done. If the session crashes, completed tracks must be recoverable.

---

## CORE PRINCIPLES (read before starting)

**No band-aids.** A gate is never a substitute for fixing the model. If a stat/direction loses because the model gives wrong probabilities, the fix is the model. Only block when the market is structurally unbeatable regardless of model accuracy, or when the stat's distribution is fundamentally wrong and cannot be parameterized correctly.

**No thin-sample rules.** Any rule derived from pick_log data with n < 30 at time of implementation is provisional. Flag it — do not change it, but document it.

**Calibration must be circular-free.** A constant cannot be fitted and validated on the same dataset.

---

## TRACK A — Numerical Correctness (foundation)

The distribution functions are the mathematical foundation. If they are wrong, every probability is wrong.

### A1. CDF / PMF implementations
Read `poisson_pmf`, `poisson_cdf`, `negbinom_pmf`, `negbinom_cdf`, `normal_cdf` in `run_picks.py`.
- Is each implementation mathematically correct? Verify against textbook formulas.
- `poisson_pmf` uses `math.factorial(k)` and `lam ** k` — at what k does this overflow? What is the largest k ever passed in production (SOG line ≤ 8.5, so max k ~ 8 — is that safe)?
- `negbinom_pmf` uses log-space arithmetic — verify the log PMF formula is correct: `lgamma(k+r) - lgamma(r) - lgamma(k+1) + r*log(p) + k*log(1-p)`.
- `negbinom_cdf` loops from 0 to k — is there a convergence guard? For fat-tailed NB distributions, does the loop terminate with correct precision?
- `normal_cdf` uses `math.erf` — is this numerically stable at the tails?
- What happens when proj = 0? When line = 0? When sigma = 0?

### A2. Implied probability and vig removal
- `implied_prob(odds)`: verify both branches (positive and negative odds). Edge cases: odds=0, odds=-100, odds=+100.
- `no_vig(imp1, imp2)`: this is the additive vig removal method. Is this the correct method? The multiplicative (Pinnacle/Shin) method is industry standard for asymmetric juice — does the difference matter?
- Is vig removal applied identically in edge calculation AND CLV calculation? If one uses additive and the other uses multiplicative, CLV and edge are not comparable.
- What happens when only one side of the market is available (missing_side=True)? Is the single-sided edge calculation correct?

### A3. Push handling (integer lines)
- For integer lines, the push mass is excluded and over/under are renormalized. Is the formula correct: `over_p = strict_over / (1 - push)`?
- Does this apply consistently to Poisson, NB, and Normal paths?
- What happens when push probability is very high (e.g., line exactly at mean)? Does `1 - push` approach zero safely?

### A4. Combo stat probability
- For COMBO stats (PRA, PR, PA, RA): the joint prob uses correlated Normal. Is the correlation formula correct?
- Specifically: is the joint sigma computed as `sqrt(var1 + var2 + 2*rho*sigma1*sigma2)`? Verify.
- Is COMBO_RHO applied correctly — is it the Pearson correlation, and is it used in the right formula?
- What happens for a combo stat where one component is in NB_STATS (e.g., AST)? Does the combo path still route to Normal? If so, is that correct?

---

## TRACK B — Probability Pipeline

### B1. Distribution routing
For every stat that can appear as a pick, trace which distribution path it takes:
- PTS: Normal (SIGMA). REB: Normal. SOG: Poisson. 3PM: NB. AST: NB. REC: Normal. HITS: Poisson. OUTS: Normal. HA: Normal. K: NB. HRR: NB.
- Is every stat correctly routed? Are there any stats that fall through to the default fallback `{"mult": 0.40, "min": 2.0}`? If so, flag those — uncalibrated fallback directly affects win_prob.
- For WNBA: which stats route differently (3PM → Normal in WNBA, AST → NB everywhere)?

### B2. Platt scaling pipeline
- Trace `over_p_raw` → `_platt_calibrate_prop()` → `win_prob`. Is `over_p_raw` logged BEFORE Platt? Is `win_prob` computed AFTER Platt?
- Is the formula in `_platt_calibrate_prop()` raw-probability space or logit-space? Are the constants consistent with that space?
- Read the migration note in the constants block. Is it accurate and complete?
- `calibrate_winprob.py` fits on post-Platt `win_prob` — the file itself warns this is double-calibration if used to update constants. Is there any path where someone could accidentally paste its output into run_picks.py? Is the warning sufficient?
- Is there a Platt calibration for game lines (SPREAD, ML, TOTAL)? If not, are game line probabilities systematically miscalibrated?

### B3. Confidence scalar (I6)
- Find `conf` / `adj_edge` / `adj_wp` in `evaluate_props()`.
- Is `conf` applied to BOTH `adj_edge` AND `adj_wp`? Asymmetric application inflates pick_score.
- Are the GP thresholds (10 / 20 games) empirically based or guesses?
- When `sigma_override > 0` (dk_std from custom engine), is `conf` still applied? Could this create a case where Platt is applied to a dk_std-derived prob that wasn't computed the same way as the normal SIGMA path?

### B4. Gate logic — band-aid test
For every gate in `check_game_gates()` and `check_prop_gates()`:
- What is the gate testing?
- **Band-aid test:** Is this gate compensating for model miscalibration, or blocking something that is structurally unbeatable? Which one is it?
- **Market efficiency test:** Would this gate still be needed if the underlying model were perfectly calibrated?
- What was the n at time of implementation? Flag anything with n < 30 as provisional.
- G8D (3PM over ≤1.5): n=13. With NB_R now updated to 9.15, does the updated model still produce edge on this pick? If not, was G8D a band-aid that the NB_R fix now makes redundant?
- G8C (SOG under ≤2.5, ≤3.5): n=27 and n=14 respectively. Band-aid or structural?
- TEAM_TOTAL over block: n=11 — provisional. Is there a theoretical reason overs are harder (market prices in public over-bias)?
- MIN_WIN_PROB=0.55: 0.55-0.60 bucket has 33.3% WR (n=24). Is this the right threshold? The 0.50-0.55 bucket (blocked) has 43.6% WR — worse WP picks are currently passing while better ones are blocked.

### B5. Edge calculation
- Trace `raw_edge` from `nv_prob` to final value. Is `raw_edge = model_p - nv_prob` (over side) correct?
- Is `nv_prob` the no-vig market probability or the raw implied probability? Verify.
- For missing_side picks: is the single-sided edge calculation documented and correct?

---

## TRACK C — Data Integration & Name Matching

This is a silent-failure risk. A name mismatch produces no error — the pick just disappears.

### C1. Player name matching
- Read `engine/name_utils.py`. What normalization is applied to player names?
- Is the same normalization applied to both the SaberSim CSV and the Odds API response?
- What happens when a name doesn't match? Silent skip, or logged warning?
- Are there known mismatches (e.g., "LeBron James" vs "Lebron James", Jr./III suffixes, accented characters)?
- What is the test coverage for name normalization edge cases?

### C2. Game/team matching
- How is a player's game identified from the SaberSim CSV vs the Odds API?
- How is `is_home` determined? Could home/away be swapped?
- For TEAM_TOTAL picks: how is the team matched to the API game? Could the wrong team's total be used?
- What happens when the Odds API returns a game that SaberSim doesn't have (or vice versa)?

### C3. Odds API line matching
- For prop picks: how is the correct stat/line matched from the API response? Could an alternate line (e.g., 1.5 instead of 2.5) be used instead of the standard line?
- For multi-book picks: does the engine correctly select the best price across books?
- What happens when a stat exists in the CSV projection but has no line on any book?

### C4. Stale odds cache
- The Odds API has an 11-minute cache (`--no-cache` bypasses it). 
- What is the maximum line movement in 11 minutes for typical props? Is 11 minutes safe, or could a major injury/news event move lines significantly in that window?
- Is there any staleness check at bet-finalization time?
- When `--no-cache` is used, does the full pipeline re-fetch, or just some parts?

---

## TRACK D — Sport-Specific Logic

Each sport has distinct code paths. Audit them separately.

### D1. NBA-specific
- Is `PLAYOFF_MODE` detected correctly? Is it based on date, schedule data, or a manual flag?
- When in playoff mode, are the correct scalars applied everywhere? Are there any places that still use RS scalars during playoffs?
- Is the blowout sigmoid applied in playoff mode? Is that correct?
- NBA-specific stats: PTS, REB, AST, 3PM, PRA, PR, PA, RA. Are all correctly handled?

### D2. NHL-specific
- SOG: Poisson distribution. Is the Poisson cutoff (8.5) appropriate for SOG lines?
- Is there any NHL-specific Platt or calibration separate from NBA?
- Do NHL game lines (SPREAD, ML, TOTAL) use the same probability path as NBA?

### D3. MLB-specific
- MLB stats: K, OUTS, HA, HITS, HRR, TB (killed). Are all correctly routed?
- MLB has only 11 picks in empirical data. Are MLB-specific assumptions (SIGMA["OUTS"], SIGMA["HA"]) calibrated from game data, or carried over from basketball?
- F5 (first 5 innings) lines: are these processed differently from full-game lines?
- MLB pitcher vs batter correlation groups: is `MLB_CORR_GROUPS` enforced correctly (max 1 per group per card)?
- Is the MLB season start date correct for the current season?

### D4. WNBA-specific
- WNBA picks are shadow-only (not posted to Discord). Is `SHADOW_SPORTS` enforced in every Discord posting path?
- SIGMA_WNBA: are these values calibrated from 2024 WNBA game logs, or estimates?
- WNBA 3PM uses Normal (not NB) — is this because 3PM is underdispersed in WNBA? Verify the evidence.
- Early-season edge multiplier: is `WNBA_SEASON_START` updated for the 2026 season?
- Is pick_log_wnba.csv being written correctly with the same 29-column schema?

---

## TRACK E — Gate Empirical Validation

Load `data/pick_log.csv`. Reference `docs/research/EMPIRICAL_ANALYSIS_2026-05-24.md` (n=182 settled primary/bonus picks).

**For every finding: state n and flag anything with n < 30 as provisional.**

### E1. Sample size audit of all rules
For every gate, filter, or rule derived from pick_log empirical data:
- What was n at implementation time?
- What is n today?
- Is n ≥ 30? If not, label provisional.
- Is there a reversal risk?

### E2. Stat-direction performance (n ≥ 10)
- Which stat-direction pairs have model WP > 10pp above actual WR?
- Which are systematic unit losers?
- Are losing pairs blocked, or still allowed?
- For any blocked pair with n < 30: was the block premature?

### E3. Tier performance
- T1: 46.6% WR, -3.75u. T2: 60.3% WR, +12.00u.
- Why is T1 empirically losing to T2? Is the tier assignment logic correct?
- Is n per tier sufficient to draw conclusions?

### E4. Pick score predictive validity
- Score < 40: ≤40% WR. Score ≥ 60: ≥66% WR.
- Is MIN_PICK_SCORE set correctly? Should it be raised?
- Are any score buckets too thin to act on?

### E5. Odds bucket performance
- +100 to +149 losing picks (-4.5u, n=48). Sufficient n to act?
- Is there a theoretical case (market efficiency at plus-money) supporting a gate?

### E6. Calibration check
- Overall WR = 53.3% (n=182). Model mean WP = ~63%. Gap = ~10pp.
- Is this gap consistent with systematic over-prediction, or within expected variance?
- Does the gap vary by sport? By stat? By line size?

---

## TRACK F — Scoring & Sizing

### F1. pick_score formula
- What inputs does `pick_score()` use?
- Is `win_prob` post-Platt when `pick_score` is called?
- Does it use `adj_wp` (confidence-adjusted) or raw `win_prob`?
- Is the formula empirically derived or a heuristic?

### F2. KILLSHOT gate
- Verify every criterion is enforced in code: tier=T1 strict, score≥65, win_prob≥0.65, odds ∈ [-200,+110], stat ∈ {PTS, AST, SOG}.
- Is `win_prob` used here the confidence-adjusted `adj_wp`? It must be.
- Weekly cap: how is the counter stored and reset? Is there a race condition if two sports run simultaneously?

### F3. Kelly fraction / VAKE sizing
- Trace from `win_prob` to final `size`. What fraction of full Kelly is being used?
- Is the Kelly formula correct: `f = (b*p - q) / b` where `b = decimal_odds - 1`?
- Daily cap 12u: is it enforced atomically across concurrent sport runs?
- Sport caps (NBA=8u, NHL=5u): applied before or after daily cap check?
- KILLSHOT sizing (3u default, 4u if wp≥0.70 AND edge≥0.06): is this applied correctly?

### F4. SGP / parlay / daily_lay sizing and probability
- How are leg probabilities combined for daily_lay and longshot? Simple multiplication (independence assumption)?
- For SGP: the leg probabilities come from the model. Are same-game legs treated as correlated?
- Is the independence assumption documented and justified?
- SGP sizing: 0.25u default, 0.50u premium (avg_wp≥0.70 AND cohesion≥0.55 AND avg_edge≥0.035). Verify.
- Daily_lay odds cap (+100 maximum): is this enforced?

---

## TRACK G — Portfolio & Correlation Risk

### G1. Same-game correlation
- Can multiple picks from the same game appear on the same card?
- If yes: these are correlated (blowout, pace outlier, injury). Is there a per-game pick cap?
- Is there a `LONGSHOT_MAX_PER_GAME` cap? Does it apply to primary/bonus picks too?
- Could a player appear in primary, bonus, AND as a daily_lay leg on the same day? Is double/triple exposure tracked?

### G2. SGP leg correlation
- SGP legs within a game are explicitly correlated (they share game outcome, pace, etc.). Is this modeled?
- Does the SGP builder adjust composite probability for within-game correlation?
- What is the actual WR on SGP picks so far? Is the model's predicted probability calibrated?

### G3. Concurrent run race conditions
- If `go.ps1 nba` and `go.ps1 nhl` run simultaneously:
  - Is the daily unit cap read-modify-write protected with a file lock?
  - Could both sessions read "10u used" and both add 2u, ending at 12u instead of 14u?
  - Could pick_log.csv be written by both simultaneously, corrupting a row?
- Is `filelock` applied to every pick_log write path?

---

## TRACK H — Grading, CLV & Output Layer

### H1. Grading correctness
- For overs: is W defined as `actual > line` or `actual >= line`? DK rules: push at line = refund, so W requires strict `>`. Verify.
- For unders: `actual < line`? Same logic.
- Are VOID conditions (DNP, game cancelled, line withdrawn) handled correctly for all run_types?
- Can a single pick be graded twice (double-write to pick_log)?
- What happens when a game goes to OT and grade_picks.py runs during OT?

### H2. CLV capture
- Capture window: what is T-start and T-end for each sport? Is it correct?
- Game matching: can the wrong event get matched to a pick?
- Side matching: can the CLV be captured for the wrong side (over vs under, home vs away)?
- Is the CLV write to pick_log.csv protected with filelock?
- `MAX_DAEMON_UPTIME_SECS=18h`: what happens if a game is posted very late and the daemon has already exited?

### H3. Discord posting
- Every webhook post: is there a guard preventing double-posts on reruns?
- `discord_posted.json`: is it checked before every single post type (card, bonus, POTD, recap, KILLSHOT)?
- Is `--repost` the only path that bypasses the guard?
- Can a Discord embed field exceed 1024 chars? Can total embed exceed 6000 chars? What happens if it does?
- If two sports run simultaneously, could both try to post at the same time and hit Discord rate limits?

### H4. CLV report and analyze_picks
- `clv_report.py`: is CLV calculated correctly (vig-free closing - vig-free open)?
- `analyze_picks.py`: are all stats computed correctly? Is there any off-by-one in date filtering?
- Is there any metric in the reports that is computed differently from how the engine computes it?

---

## TRACK I — Calibration Methodology

### I1. SIGMA values
- `SIGMA["PTS"]` mult=0.35, min=4.5 — what is the calibration basis? Script? Data source?
- `SIGMA["REB"]` mult=0.58, min=2.5 — same.
- `SIGMA["REC"]` mult=0.50, min=1.2 — same.
- `SIGMA["OUTS"]` mult=0.30, min=3.0 — "recalibrated 2024 data" — what script? What data?
- `SIGMA["HA"]` mult=0.50, min=2.5 — same.
- `SIGMA_WNBA`: calibrated from 2024 WNBA season logs — is there a script? What data?
- **For any SIGMA value with no documented calibration script: flag HIGH.** These directly affect win_prob for every prop.
- Should there be a `calibrate_sigma.py` (analogous to `nb_calibrate.py`) that derives these from projections.db within-player variance?

### I2. Platt formula / space alignment
- What formula is in `_platt_calibrate_prop()`? Raw-probability or logit-space?
- Were PLATT_A/B fitted in the same space as the production formula?
- Read the migration note. Is it correct and complete?
- `calibrate_winprob.py` produces a second set of A/B — these are double-calibration if used in production. Is the warning in the file sufficient? Could they accidentally get used?

### I3. NB_R values
- 3PM: 1246 player-seasons (projections.db). Script: `engine/nb_calibrate.py`. ✓ Verify.
- AST: 1395 player-seasons. Same script. ✓ Verify.
- HRR: shadow log WR at line 1.5 (n=1810). Verify the calibration logic.
- K: r=5.0 — described as an estimate. Has this been validated? What data would validate it?
- Is there a recalibration schedule for NB_R?

### I4. Circular calibration check
- For each calibration constant: what data was it fitted from?
- Is any constant fitted from pick_log.csv WR data? If so, is it validated on independent data?
- Are the SIGMA values derived from projections.db (independent of pick_log) or from observed WR (circular)?
- Is the Platt fit using `over_p_raw` (pre-Platt — correct) or `win_prob` (post-Platt — double-calibration)?

### I5. Sport-specific calibration gaps
- Is the same Platt used for NBA and NHL combined? Should they be separate?
- Is MLB Platt the same as NBA/NHL? MLB has different stat distributions and vigorish structures.
- Is the COMBO_RHO (75k player-games) stable across seasons and teams?
- WNBA COMBO_RHO from 9 players / 336 games — confidence interval on each value?

---

## TRACK J — Sharp Process & Industry Standards

Research any of these where the answer is not obvious from the code.

### J1. CLV as primary edge signal
- Is CLV tracked as the primary edge signal (positive CLV = model beat the close)?
- What is the current mean CLV across all settled picks with CLV data?
- Industry standard: WR alone cannot diagnose model edge at n=182. CLV is the right metric. Is CLV used that way here?

### J2. Vig removal method
- The engine uses additive vig removal (`no_vig = imp1/total, imp2/total`). 
- The Pinnacle/multiplicative method is industry standard for asymmetric juice. At -110/-110 the difference is ~0.3pp. At -130/+110 it's ~1pp.
- Is the same method used everywhere (edge calculation, CLV calculation, Platt fitting basis)?
- Does the method matter at the juice levels typically seen in production picks?

### J3. Kelly fraction correctness
- Is the Kelly formula implemented correctly?
- What effective fraction of Kelly is VAKE? (compute: typical size / full-Kelly size for a 60% WP pick at -110)
- Is this fraction appropriate given win_prob estimation uncertainty?

### J4. Sample size adequacy
- n=182 settled picks. What can and cannot be concluded?
- What is the 95% CI on overall WR (53.3%)?
- Which stat-direction breakdowns have n ≥ 30 (sufficient) vs n < 30 (preliminary)?
- Industry minimum for model assessment: ~500 picks. Are any decisions being made prematurely?

### J5. Market timing
- When are picks generated relative to line movement? (T-120 min default per CLAUDE.md)
- Are earlier bets showing better CLV than later bets? Is there CLV data to check this?
- Do any stats have a better timing window (e.g., injury news tends to move certain lines more)?

### J6. SGP correlation vs books
- Books adjust SGP odds for within-game correlation. The engine treats legs as independent.
- If the engine says a 4-leg SGP is worth +350 based on independent probabilities, but the book offers +280 (correlation-adjusted), the true edge is less than computed.
- Is SGP edge computed against the book's actual offered odds, or against a model-derived fair value?

### J7. Sharp vs square books
- Are there books in CO_LEGAL_BOOKS that sharpen quickly (limit winners) vs stay soft?
- Is Pinnacle or Circa available in the Odds API? If yes, are they in CO_LEGAL_BOOKS?
- Should a "best available on sharp book" signal be treated differently from "only available on soft book"?

### J8. Model vs market reconciliation
- Is there any process for investigating when the model shows >15pp edge? That gap often means the market has information the model doesn't (injury, lineup change, weather).
- Should very large edges (>15%) trigger a manual review before the pick is posted?

---

## TRACK K — Operational Safety

### K1. Concurrent run safety
- Are all pick_log.csv writes protected with `filelock`? List every write path.
- Are all Discord guard file reads/writes atomic?
- If `go.ps1 nba` and `go.ps1 nhl` run within seconds of each other, can either corrupt the other's work?

### K2. Stale odds / cache safety
- 11-minute Odds API cache: what is the risk of acting on a stale line?
- Is there a "line moved significantly since cache" check before finalizing a pick?
- Does `--no-cache` guarantee a fresh fetch of all odds, or just some?

### K3. Security
- Is `.env` gitignored? Run `git check-ignore -v .env` to verify.
- Are API keys or Discord webhooks ever printed to logs, stdout, or pick_log?
- Does any exception handler expose credentials in error messages?
- Are webhook URLs treated as secrets (not hardcoded, not logged)?

### K4. Invalid / extreme inputs
- What happens if the Odds API returns obviously invalid odds (e.g., odds=0, odds=99999)?
- What happens if a SaberSim CSV row has proj=0.0 or proj=NaN?
- What happens if pick_log.csv has a malformed row (wrong column count)?
- Are there guards on extreme win_prob values (wp > 0.95 or wp < 0.05)?

### K5. Windows-specific issues
- Are all file paths using `pathlib.Path` or `os.path.join`? Any hardcoded backslashes?
- Is file encoding consistently UTF-8 (not cp1252/Windows-1252)?
- The `start_clv_daemon.bat` file must be ASCII-only (cmd.exe crashes on non-ASCII). Is this enforced?

### K6. Error recovery
- If run_picks.py crashes mid-run (after some picks are logged but not all), is the state recoverable?
- Is there a re-run guard that prevents duplicate posts if the script is re-run on the same day?
- What happens if grade_picks.py runs on a day with no graded picks?

---

## TRACK L — Documentation vs Reality

Read `CLAUDE.md` and verify every claim against the actual code:
- `PLATT_A = 1.4988, PLATT_B = -0.8102` — confirm in `engine/run_picks.py`
- Formula space note (raw-probability) — confirm in `_platt_calibrate_prop()`
- `NB_R["3PM"] = 9.15`, `NB_R["AST"] = 9.68` — confirm
- `SIGMA` dict — confirm AST/SOG/HITS/TB have been removed (dead code cleaned up)
- H3 gate count — current count from pick_log?
- CLV gate count — current count from pick_log_custom.csv?
- Every scalar listed under "Active Scalars" — skip (projection system, out of scope)
- Any file referenced in CLAUDE.md that no longer exists
- Any feature described as "disabled" that actually still has live code

---

## OUTPUT FORMAT

For each finding:
```
TRACK: [A-L]
FILE: engine/xxx.py  (or data/pick_log.csv etc.)
LINE: ~NNN
SEVERITY: CRITICAL | HIGH | MEDIUM | LOW
N: [sample size if empirical, or "N/A" if logic-only]
ISSUE: [what is wrong — be specific]
IMPACT: [what breaks in production]
FIX: [exact change needed, with code if applicable]
```

Severity definitions:
- **CRITICAL**: wrong probability, wrong grades, money miscounted, data corrupted, security breach
- **HIGH**: silent wrong result, systematic bias, circular calibration, uncalibrated constant affecting win_prob, race condition that can corrupt state
- **MEDIUM**: wrong output under specific conditions, stale calibration with measurable impact, thin-sample provisional rule, industry-standard gap with quantifiable EV impact
- **LOW**: inconsistency, undocumented assumption, minor operational risk, industry-standard gap with small EV impact

**N < 30 rule: cap severity at MEDIUM for any empirical finding. Small samples reverse.**

---

## END SUMMARY (required)

1. **Fix list** — CRITICAL first, then HIGH, then MEDIUM. Each item: track, file, line, one-line description.
2. **Provisional rules** — every gate/rule with N < 30. Label: "monitor only, do not change yet."
3. **Calibration debt** — every constant with no documented calibration script or independent validation.
4. **CLAUDE.md corrections** — every stale or wrong line.
5. **Biggest structural gap** — one paragraph comparing this engine to what a professional sharp quant operation would do differently.
