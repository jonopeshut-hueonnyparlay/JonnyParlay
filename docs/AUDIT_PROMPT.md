# JonnyParlay Full System Audit Prompt

Paste into a fresh Claude Code session. This covers every layer of the engine.
Read CLAUDE.md first for system context before starting.

---

## PROMPT

You are performing a comprehensive technical audit of the JonnyParlay sports betting engine.
This is a production system posting picks to Discord daily with real money on the line.
We are monetizing soon. The model must be correct. Be thorough and unsparing.

Read `CLAUDE.md` in full before starting — it contains the authoritative system spec.

**The three failure modes we most want to catch:**
1. Math or logic that produces wrong probabilities silently
2. Gates or rules built on insufficient data (n too small to trust)
3. Changes that were implemented without adequate empirical validation

---

## TRACK A — Probability Pipeline (highest priority)

Read `engine/run_picks.py` in full. Audit every probability calculation.

### A1. Distribution model correctness

For each stat in `POISSON_STATS`, `NB_STATS`, `COMBO_STATS`, and everything using `SIGMA`:
- Is the chosen distribution (Poisson / NB / Normal / combo-Normal) mathematically correct for that stat?
- For NB stats: is the `NB_R` value empirically calibrated or a guess? What data was used? How many player-seasons?
- For Poisson stats: is Poisson actually a good fit (var ≈ mean)? What is the evidence?
- For Normal stats: are the `SIGMA` multiplier/min values empirically calibrated or guesses? When last updated?
- Are there any stats where the distribution model has never been validated?

### A2. Platt scaling

- Find `PLATT_A`, `PLATT_B` constants. What is the current formula?
- Is it raw-probability space `sigmoid(A*p + B)` or logit-space `sigmoid(A*logit(p) + B)`?
- Which formula is mathematically correct for Platt scaling? (Answer: logit-space)
- What is the H3 gate status — how many `over_p_raw` rows exist in `data/pick_log.csv`?
- Is `calibrate_platt.py` using logit-space? Does it have the `--force` and `--native-only` flags?

### A3. over_p calculation

- Trace `over_p` from raw projection through to the logged `over_p_raw` column.
- Is `over_p_raw` being logged BEFORE Platt calibration is applied? Verify.
- Is `win_prob` (the field used for gates and sizing) being computed AFTER Platt? Verify.
- Can `over_p_raw` ever equal the post-Platt value? If so, that contaminates future refits.

### A4. Confidence scalar (I6)

- Find `conf` / `adj_edge` / `adj_wp` in `evaluate_props()`.
- Is the confidence scalar applied to BOTH `adj_edge` AND `win_prob`? It must be — asymmetric application inflates pick_score for low-GP players.
- Are the GP thresholds (10 / 20 games) reasonable? Is there empirical justification?

### A5. Gate logic audit

For every gate in `check_game_gates()` and `check_prop_gates()`:
- What is the gate testing?
- What empirical evidence supports it? What was the n? Is n ≥ 30 for any stat-direction block?
- Are any gates contradictory (gate A passes what gate B blocks)?
- Are any gates redundant (one subsumes another)?
- G8D specifically: is 3PM over ≤1.5 blocked? Check empirical data — 1.5-line 3PM over has -23.8pp gap (n=13). Is n=13 sufficient to block permanently?
- G8C specifically: is SOG under ≤2.5 AND ≤3.5 blocked? What was the n for each threshold?
- TEAM_TOTAL over: is this blocked? What was the n that justified blocking? (n=11 is very thin — flag if so)
- Is MIN_WIN_PROB meaningful? The 0.55-0.60 bucket has 33.3% WR (worse than 0.50-0.55 at 43.6%) — is the floor set correctly?

### A6. Edge calculation

- Trace `raw_edge` from `nv_prob` to final value.
- Is vig removal correct? Is the formula `p_implied = 1/(1 + 100/abs(odds))` for favorites and `p_implied = odds/(100 + odds)` for underdogs? Verify both branches.
- Is the no-vig probability calculated correctly from the two-sided market?
- Any case where `nv_prob` is used raw (without vig removal)?

### A7. Combo stat probability

- For COMBO stats (PRA, PR, PA, RA): how is the joint probability computed?
- Is correlation between components modeled? If not, is the independence assumption documented?
- Are the combo sigma values based on the correlated joint distribution or the sum of individual sigmas?

---

## TRACK B — Gate & Rule Empirical Validation

Load `data/pick_log.csv`. Reference `docs/research/EMPIRICAL_ANALYSIS_2026-05-24.md` (n=182 settled primary/bonus picks).

**For every finding in this track, state the n and flag anything with n < 30 as "THIN SAMPLE — monitor, do not act."**

### B1. Sample size audit of all gates
For every rule, filter, or block in the engine that was derived from pick_log data:
- What was the n at the time the rule was implemented?
- Is the current n still below 30? If so, flag the rule as provisional.
- Is there a reversal risk — i.e., with more data, does this rule flip?

### B2. Stat-direction performance
Cross-reference every (stat, direction) pair with n ≥ 10 against the model WP:
- Which pairs have model WP > 10pp above actual WR?
- Which are systematic losers (negative units)?
- Are these pairs currently blocked, or still allowed through?
- For any pair that is blocked: was n ≥ 30 when the block was added?

### B3. Tier performance
- T1 is -3.75u with 46.6% WR. T2 is +12.00u with 60.3% WR.
- Is T1 genuinely the highest-quality tier by model definition? If T1 is empirically losing to T2, investigate whether the tier assignment criteria are correct.
- Is n large enough per tier (≥30) to draw conclusions?

### B4. Pick score predictive validity
- Using Section 7 (Pick Score Bucket): scores <40 have ≤40% WR. Scores 60+ have ≥66% WR.
- Is `MIN_PICK_SCORE` set appropriately? Is there a missing gate at score ≥40?
- What is the n per score bucket? Are any buckets too thin to act on?

### B5. Odds bucket performance
- +100 to +149 range picks are losing (-4.5u combined, n=48). Is there a gate on plus-money odds?
- Should overs at long-plus odds be blocked? What is the theoretical vs empirical case?

---

## TRACK C — Scoring & Sizing

### C1. pick_score formula
- Read `pick_score()` function. What inputs does it use?
- Is `win_prob` post-Platt or pre-Platt at the time `pick_score` is called?
- Does pick_score use `adj_wp` (confidence-adjusted) or raw `win_prob`?
- Is the formula documented with an empirical basis or is it a heuristic?

### C2. KILLSHOT gate
- Read the KILLSHOT qualification criteria. Cross-reference with CLAUDE.md:
  - tier=T1 strict, pick_score≥65, win_prob≥0.65, odds ∈ [-200,+110], stat ∈ {PTS, AST, SOG}
- Is each criterion actually enforced in code? Find the exact check.
- Weekly cap: is the counter properly reset each week? What's the reset logic?
- Is there a way KILLSHOT fires even when win_prob is the pre-confidence adj_wp? It shouldn't.

### C3. Unit sizing
- VAKE sizing: trace from `win_prob` to final `size`. What fraction of Kelly is being used?
- Daily cap (12u): is it enforced across ALL run_types, or just primary/bonus?
- Sport caps (NBA=8u, NHL=5u): applied before or after daily cap check?
- SGP sizing: is 0.25u/0.50u correct given average SGP WR?

---

## TRACK D — Grading, CLV & Output Layer

Read `engine/grade_picks.py`, `engine/capture_clv.py`, `engine/clv_report.py`, `engine/weekly_recap.py`, `engine/results_graphic.py`.

### D1. Grading correctness
- Is the result (W/L/VOID) logic correct for every run_type?
- For overs: does W require `actual > line`? Or `actual >= line`? (half-point lines make this matter)
- For unders: same — is the boundary correct?
- Are VOID conditions (player DNP, game cancelled) handled correctly?
- Can a single pick be graded twice (double-write risk)?

### D2. CLV capture
- Capture window: what is the T-window? Is it correct for each sport?
- Game matching: can the wrong game get matched to a pick?
- Side matching: can the wrong side (over vs under) get a CLV value?
- Is the CLV write safe against corrupting existing pick_log rows?
- Does the daemon correctly handle the 18h MAX_UPTIME guard?

### D3. Posting & deduplication
- Every webhook post: is there a guard preventing double-posts on reruns?
- Discord guard file (`discord_posted.json`): is it checked before every post?
- For grade_picks.py: is `--repost` the only path that bypasses the guard?
- Weekly recap: is the "already posted this week" guard correct?
- Can a Discord embed overflow the 6000-char limit or 1024-char field limit?

### D4. SGP builder (`engine/sgp_builder.py`)
- Are all allowed books checked (FanDuel, BetMGM, DraftKings, theScore, Caesars, Fanatics, Hard Rock)?
- Is the odds range enforced (+200 to +450)?
- Is the 3-4 leg count enforced?
- Is composite pool_score sort correct?

---

## TRACK E — Data Quality

### E1. pick_log.csv integrity
Run these checks on `data/pick_log.csv`:
- Column count = 29 for every row (no schema drift mid-file)
- `result` values ∈ {W, L, VOID, NaN} — no typos
- `win_prob` in [0, 1] for all non-null rows
- `edge` in [-0.5, 0.5] for all non-null rows
- `over_p_raw` in [0, 1] for all non-null rows — these are raw probabilities
- `direction` ∈ {over, under, win} for all non-null rows
- `run_type` ∈ {primary, bonus, manual, daily_lay, sgp, longshot} for all rows
- Rows with `result=NaN` — are these picks from today (expected) or old ungraded picks (bug)?
- Rows where `tier=T1` but `win_prob < 0.55` — should these exist?
- SGP rows: do all have a valid `legs` JSON array?
- Are there any rows with `win_prob > 0.85`? These are extreme and likely miscalibrated.

### E2. Sample size snapshot — flag thin-data rules
For every rule implemented since 2026-04-14 (start of pick_log), check the n at implementation time:
- List every rule where n < 30 at time of implementation
- List every rule where n is still < 30 today
- These are provisional — not necessarily wrong, but must be monitored

### E3. over_p_raw tracking
- Current count of non-null over_p_raw in settled primary/bonus rows
- Compare to H3 gate requirement (100 rows)
- Are there rows that SHOULD have over_p_raw but don't (primary props logged after 2026-05-05)?

---

## TRACK F — Code Quality & Architecture

### F1. Constants consistency
- Are `PLATT_A`, `PLATT_B` defined in exactly one place? Or scattered?
- Is `NB_R` defined in one place only?
- Are there any hardcoded odds, thresholds, or probabilities outside of the constants section?
- Does CLAUDE.md accurately reflect the current constant values?

### F2. Dead code
- Any function defined but never called
- Any commented-out code blocks that are not documented as intentionally preserved
- Any feature flag that is always True/False (effectively dead branch)

### F3. Magic numbers
- Any numeric literal in a probability/sizing calculation that has no constant name or comment
- Any threshold in a gate that is not tied to an empirical basis comment

### F4. Error handling at boundaries
- File I/O: what happens if pick_log.csv is missing? Locked? Corrupted header?
- API calls: what happens if the Odds API returns malformed JSON? Rate-limit error?

### F5. File lock safety
- `filelock` usage: is it applied everywhere pick_log.csv is written? (run_picks, grade_picks, capture_clv all write it)
- Is the lock timeout set appropriately?

---

## TRACK G — Documentation vs Reality

Read `CLAUDE.md` and verify every claim against the actual code:
- `PLATT_A = 1.4988, PLATT_B = -0.8102` — confirm these match `engine/run_picks.py`
- `NB_R["3PM"]` and `NB_R["AST"]` — confirm current values match the code
- H3 gate count — current count from pick_log?
- CLV gate count — current count from pick_log_custom.csv?
- Any file or function referenced in CLAUDE.md that no longer exists
- Any constant value in CLAUDE.md that is stale

---

## OUTPUT FORMAT

For each finding:
```
TRACK: [A-G]
FILE: engine/xxx.py  (or data/pick_log.csv etc.)
LINE: ~NNN
SEVERITY: CRITICAL | HIGH | MEDIUM | LOW
N: [sample size if empirical, or "N/A" if logic-only]
ISSUE: [what is wrong — be specific]
IMPACT: [what breaks in production]
FIX: [exact change needed, with code if applicable]
```

Severity:
- **CRITICAL**: wrong probability output, wrong grades, money miscounted, data corrupted
- **HIGH**: silent wrong result, systematic bias, pick_log corruption risk
- **MEDIUM**: wrong output under specific conditions, stale calibration with measurable bias, thin-sample rule that may be wrong
- **LOW**: inconsistency, undocumented assumption, minor inefficiency

**For any finding where N < 30: automatically cap severity at MEDIUM regardless of apparent impact. Small samples reverse.**

At the end:
1. Prioritized fix list (CRITICAL → HIGH → MEDIUM)
2. List of every rule/gate that is provisional (N < 30) — label clearly as "monitor, do not change"
3. List every CLAUDE.md line that is stale or wrong
4. One paragraph: the single biggest structural risk in the current model
