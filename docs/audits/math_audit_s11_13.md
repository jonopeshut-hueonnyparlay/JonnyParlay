# Math Audit — Sections 11–13
**Date:** 2026-05-22  
**Auditor:** Claude Sonnet 4.6  
**Scope:** engine/run_picks.py, engine/mlb_starter_fetcher.py  
**Focus:** MLB math (S11), WNBA math (S12), NHL math (S13)

---

## Section 11 — MLB-Specific Math

### Finding 11.1: CORRECT — HRR projection built correctly from SaberSim columns

**File:** `engine/run_picks.py:1588-1611`  
**Code:**
```python
h = float(clean.get("H", 0) or 0)
r = float(clean.get("R", 0) or 0)
rbi = float(clean.get("RBI", 0) or 0)
p["HRR"] = h + r + rbi  # Hits + Runs + RBIs
```
**Verdict:** Projection is a direct sum of three SaberSim columns (H + R + RBI). SaberSim already projects these as expected-value quantities, so simple addition gives the correct HRR mean projection. No weighting or transformation needed at this stage — correct.

---

### Finding 11.2: CORRECT — HRR uses Negative Binomial distribution (NB r=1.5), not Normal

**File:** `engine/run_picks.py:292-302, 716-734`  
**Code:**
```python
# NB_R calibration note:
# HRR: r=1.5 calibrated from shadow log: NB(r=1.5, μ=2.0) gives P(X≥2)=47.8% matching empirical 48% WR.
# Normal was giving 63% for same projection — structural zero-inflation (batter 0-H/R/RBI ~37% of games).
NB_STATS = {"3PM", "HRR", "K"}
NB_R = {"HRR": 1.5, ...}

elif stat in NB_STATS and not (sport == "WNBA" and stat == "3PM"):
    r = NB_R[stat]
    k = math.floor(line)
    ...
    under_p = negbinom_cdf(k, proj, r)
    over_p = 1.0 - negbinom_cdf(k, proj, r)
```
**Verdict:** The NB parameterisation is correct. NB(mu, r) with `p = r/(r+mu)` is standard. r=1.5 is a low dispersion parameter, producing a heavy tail appropriate for a count stat with structural zero-inflation (~37% batter games with 0 H/R/RBI). The Normal model's overcooking (63% vs actual 48% at line 1.5) was the documented motivation for the switch, which is calibrated on n=1810 shadow rows.

---

### Finding 11.3: ISSUE — 25%+ HRR edge on O0.5 is plausible but relies on NB model still over-predicting

**File:** `engine/run_picks.py:992-1002, 1044-1048`  
**Code:**
```python
# G13B: HRR line-specific WP floors.
# Line 0.5: WP≥0.58 (empirical 57.4% WR, promising but NB inflated to ~72%).
if stat == "HRR":
    if line <= 0.5 and prob < 0.58:
        return False, "G13B"

# G2: model error — but O0.5 HRR/TB/HITS are soft markets with legitimately large edges
_is_soft_o05 = (stat in ("HRR", "TB", "HITS") and line <= 0.5 and direction == "over")
g2_threshold = 0.28 if _is_soft_o05 else 0.20
if edge >= g2_threshold:
    return False, "G2"
```
**Verdict:** The G13B comment itself acknowledges the NB model inflates P(X≥1) to ~72% vs actual 57.4%. At the boosted G2 threshold of 0.28 (28% edge cap), a pick must have a model WP of ~72% vs a market no-vig of ~44% to produce 28% edge — which is exactly what a mis-calibrated NB model would generate. The `_is_soft_o05` exemption and the elevated 0.28 G2 threshold together allow picks where the model is known to inflate probability. This is a documented and gated risk, not a silent overcooking, but it means 25%+ edge on HRR O0.5 is structurally expected from NB inflation, not necessarily from real model insight. The G13B WP floor of 0.58 is the correct constraint given the empirical 57.4% WR. Risk is managed but noted.

---

### Finding 11.4: CORRECT — K and OUTS use NB/Normal distributions appropriately with confirmed-starter gate

**File:** `engine/run_picks.py:2217-2220`  
**Code:**
```python
# MLB pitcher confirmation gate: skip K/OUTS/HA when SP is unconfirmed (TBD)
if stat in PITCHER_STATS and prop.get("proj_player", {}).get("is_pitcher"):
    if prop.get("proj_player", {}).get("status", "").lower() != "confirmed":
        continue
```
**Verdict:** The confirmation gate correctly blocks K/OUTS/HA picks when the SaberSim CSV hasn't confirmed the starter. K uses NB(r=5.0) for overdispersion (bimodal early-hook vs deep-start), and has a structural direction ban (unders blocked via G_K_NO_UNDERS, line floor ≥6.0 via G_K_MIN_LINE). OUTS uses Normal with mult=0.30. HA uses Normal with mult=0.50. All three are gated by `PITCHER_STATS` set. Correct.

**When starter API fails:** The exception handler at line 6113-6117 prints a warning, and the fallback is the SaberSim "confirmed" status column. If both fail, pitcher props are blocked (no unconfirmed pitcher K/OUTS/HA passes through). This is the safe outcome.

---

### Finding 11.5: CORRECT — NRFI combined probability uses independence assumption correctly

**File:** `engine/run_picks.py:3026, 3137-3141`  
**Code:**
```python
BASE_SCORING_RATE = 0.1633  # 1 - sqrt(0.70): actual 2024-25 MLB 1st-inning NRFI baseline is 70%
...
p_away_scores = min(0.45, max(0.05, BASE_SCORING_RATE * home_pitch_factor * off_away))
p_home_scores = min(0.45, max(0.05, BASE_SCORING_RATE * away_pitch_factor * off_home))
p_nrfi = (1.0 - p_away_scores) * (1.0 - p_home_scores)
p_yrfi = 1.0 - p_nrfi
```
**Verdict:** The BASE_SCORING_RATE derivation is mathematically sound: if baseline P(NRFI)=0.70 with symmetric teams, then `(1-p)^2 = 0.70` → `p = 1 - sqrt(0.70) = 0.1633`. The independence assumption P(NRFI) = P(away doesn't score) × P(home doesn't score) is standard and appropriate since the two half-innings are independent events. The pitcher/offense assignment is correctly crossed: away team bats vs home pitcher (`home_pitch_factor` applies to `p_away_scores`), home team bats vs away pitcher (`away_pitch_factor` applies to `p_home_scores`). Probability bounds (0.05–0.45) prevent degenerate inputs.

---

### Finding 11.6: ISSUE — NRFI BASE_SCORING_RATE is a per-team 1st-inning rate, but `off_away/off_home` factors use FULL-GAME runs

**File:** `engine/run_picks.py:3027, 3134-3135`  
**Code:**
```python
_LEAGUE_AVG_RUNS = 4.39  # 2024-25 MLB average runs/game/team
off_away = _team_runs(away) / _LEAGUE_AVG_RUNS
off_home = _team_runs(home) / _LEAGUE_AVG_RUNS
```
**Verdict:** The `off_away/off_home` factors normalise a team's full-game projected runs against `_LEAGUE_AVG_RUNS=4.39` (a full-9-inning rate). These factors then scale `BASE_SCORING_RATE` which is a 1st-inning-only rate (0.1633). This produces the right shape of adjustment (above-average offense → higher factor → higher scoring rate), but the scaling is imprecise: a team projecting 5.50 runs/game would get a factor of 1.25, scaling a 1st-inning rate as if full-game run rates translate 1:1 to 1st-inning rates. In practice 1st-inning run rates are driven more by the starting pitcher's quality than the team's full-game offense, so this is a secondary correction that is directionally correct. However, using `saber_team` (full-game) as a proxy for 1st-inning offense is an approximation — if the model is calibrated to the 70% baseline, it works empirically, but a team-specific 1st-inning run rate would be more precise. **This is a minor model approximation, not a math error.** Low severity.

---

### Finding 11.7: CORRECT — NRFI no-vig probability calculated correctly

**File:** `engine/run_picks.py:3161-3186`  
**Code:**
```python
# FIX M2: Compute no-vig from both sides (same as every other market)
if nrfi_under and nrfi_over:
    imp_nrfi = implied_prob(nrfi_under["odds"])
    imp_yrfi = implied_prob(nrfi_over["odds"])
    nv_nrfi, nv_yrfi = no_vig(imp_nrfi, imp_yrfi)
else:
    nv_nrfi, nv_yrfi = None, None

...
raw_edge = win_prob - nv_prob
```
**Verdict:** Edge is computed as `model_prob - no_vig_market_prob`, using a two-sided no-vig calculation when both sides are available. This is identical to the approach used for all other markets. Fallback to single-side vigged probability when one side is missing is documented and acceptable. Correct.

---

### Finding 11.8: CORRECT — F5 total projection uses 0.503 scaling factor with market anchoring

**File:** `engine/run_picks.py:2840-2843`  
**Code:**
```python
proj = game_total_proj * 0.503  # F5 is ~50.3% of full game (2024 data: 4.41/8.76 = 0.5034)
# FIX: Anchor F5 projection to market line (same as full-game BLEND_ALPHA)
proj = line + BLEND_ALPHA * (proj - line)
sigma = sigmas["total"]  # F5_SIGMA["total"] = 2.6
```
**Verdict:** The 0.503 factor is empirically derived (4.41/8.76 from 2024 data). The market anchoring `BLEND_ALPHA=0.25` is applied consistently with all other markets. F5_SIGMA["total"]=2.6 is appropriate for a 5-inning partial game (smaller than full-game sigma). The logic `proj = line + 0.25*(raw_proj - line)` correctly compresses model disagreement toward market.

---

### Finding 11.9: CORRECT — F5 ML derives win probability from team projected run difference

**File:** `engine/run_picks.py:2895-2907`  
**Code:**
```python
f5_t1 = t1_proj * 0.503
f5_t2 = t2_proj * 0.503
margin = f5_t1 - f5_t2
sigma = sigmas["spread"]  # F5_SIGMA["spread"] = 2.75

nv1, nv2 = no_vig(implied_prob(odds1), implied_prob(odds2))
t1_wp_raw = 1.0 - normal_cdf(0, margin, sigma)
t2_wp_raw = normal_cdf(0, margin, sigma)
t1_wp = nv1 + BLEND_ALPHA * (t1_wp_raw - nv1)
```
**Verdict:** `P(team1 wins F5) = P(margin > 0) = 1 - Phi(0; margin, sigma) = Phi(margin/sigma)` is correct. Market anchoring using ML no-vig (only viable anchor for F5 ML since there's no independent spread line) is the right approach. BLEND_ALPHA=0.25 consistent. F5_SIGMA["spread"]=2.75 is larger than total sigma, appropriate since run-differential variance exceeds total variance for partial games. The note explains the F5 ML has no independent margin anchor — correct. Note the 0.503 scaling is applied to both teams, so it cancels out in the margin calculation (`(t1 - t2) * 0.503 = 0.503 * (t1 - t2)`). This is numerically equivalent to scaling by 1 on margin — the 0.503 has no actual effect on the F5 ML result, only on the raw `proj` stored. This is harmless but worth noting.

---

### Finding 11.10: CORRECT — F5 spread uses market-anchored margin correctly

**File:** `engine/run_picks.py:2977-2983`  
**Code:**
```python
raw_f5_margin = (t_proj - o_proj) * 0.503
market_f5_margin = -sp_line  # sp_line is from team perspective: negative = fav
f5_margin = market_f5_margin + BLEND_ALPHA * (raw_f5_margin - market_f5_margin)
sigma = sigmas["spread"]
cover_p = 1.0 - normal_cdf(-sp_line, f5_margin, sigma)
```
**Verdict:** `P(cover) = P(margin > -sp_line) = 1 - Phi(-sp_line; f5_margin, sigma)`. With spread conventions: sp_line is negative for the favored team (e.g. -1.5). `-sp_line = 1.5` means the team must win by more than 1.5. Correct. Market anchoring applied consistently. BLEND_ALPHA=0.25.

---

### Finding 11.11: ISSUE — MLB starter API `fetch_confirmed_starters` has wrong return type annotation in docstring

**File:** `engine/mlb_starter_fetcher.py:94`  
**Code:**
```python
def fetch_confirmed_starters(game_date: str | None = None) -> dict[str, str]:
    """Return {team_abbrev: pitcher_full_name} for today's probable starters.
    ...
    """
    ...
    result: dict[str, list[str]] = {}  # actual type
    ...
    return result
```
**Verdict:** The function signature says `-> dict[str, str]` but the implementation builds and returns `dict[str, list[str]]` (to support doubleheaders). The `is_confirmed()` function correctly accepts `dict[str, list[str]]` and iterates the list. The call site in `run_picks.py` (line 6105) passes the result directly to `_mlb_confirmed(...)` which handles the list correctly. **No runtime bug** — but the docstring type annotation is wrong. Low severity.

---

### Finding 11.12: ISSUE — NRFI pitcher building: `er_per_ip` unguarded against IP=0

**File:** `engine/run_picks.py:3035-3036`  
**Code:**
```python
ip = p.get("IP", 1)        # default=1, but p["IP"] was set to 0.0 at parse time if column missing
er_per_ip = p.get("ER", 0) / ip  # ZeroDivisionError if ip==0
```
**Verdict:** `parse_csv` sets `p["IP"] = float(clean.get("IP", 0) or 0)` (line 1591/1601) — if SaberSim omits the IP column or provides `IP=0`, `p["IP"] = 0.0`. Then `p.get("IP", 1)` returns `0.0` (key exists), and `er_per_ip = 0 / 0` raises `ZeroDivisionError`. The `fip_raw` formula at line 3042 has an `if ip > 0 else 4.50` guard, but `er_per_ip` at line 3036 does not. In practice, confirmed starters always have IP > 0 from SaberSim, so this has never fired. However, a defensive `ip = p.get("IP", 1) or 1.0` would close this theoretical gap.

---

### Finding 11.13: CORRECT — NRFI skips when no confirmed pitchers are available for either team

**File:** `engine/run_picks.py:3124-3125`  
**Code:**
```python
if not home_pitcher or not away_pitcher:
    continue
```
**Verdict:** If either team's confirmed starter isn't found in `pitcher_map`, the game is skipped for NRFI evaluation entirely. Correct defensive behavior — does not fall back to league-average pitching, which would produce systematically inaccurate NRFI probabilities.

---

### Finding 11.14: CORRECT — G14 projection clearance does NOT apply to HRR (NB stat, comment stale)

**File:** `engine/run_picks.py:1004-1017`  
**Code:**
```python
# G14 comment says: "Normal/SIGMA stats (PTS, OUTS, HA, TB, HRR): proj must clear line by ≥0.10σ"
if stat in SIGMA and stat not in POISSON_STATS:  # HRR NOT in SIGMA → gate skipped
    ...
```
**Verdict:** G14 checks `if stat in SIGMA`. HRR was removed from SIGMA and moved to NB_STATS (line 279 comment: "HRR not here — moved to NB_STATS"). So HRR correctly skips G14 — the NB distribution handles probability calibration. However, the G14 comment at line 1005 still lists HRR as a SIGMA/Normal stat, which is stale. G13B (WP floors: ≥0.58 at line≤0.5, ≥0.65 at line>0.5) serves as HRR's explicit gate. The code is correct; the comment needs updating.

---

### Finding 11.15: CORRECT — HITS in SIGMA is an orphaned entry (Poisson path takes precedence)

**File:** `engine/run_picks.py:277, 284`  
**Code:**
```python
SIGMA = { ..., "HITS": {"mult": 0.90, "min": 0.7}, ... }
POISSON_STATS = {"AST", "REB", "SOG", "REC", "HITS"}
```
**Verdict:** HITS is in both `SIGMA` and `POISSON_STATS`. The `calc_prop_prob` function checks `POISSON_STATS` first (line 700), so HITS always uses Poisson. `SIGMA["HITS"]` is never reached in `calc_prop_prob`. The G14 check `if stat in SIGMA and stat not in POISSON_STATS` also correctly excludes HITS (it's in POISSON_STATS). The orphaned SIGMA["HITS"] entry causes no bugs but is dead config. Low severity.

---

### Finding 11.16: CORRECT — FIP formula correct, FIP constant appropriate

**File:** `engine/run_picks.py:3042-3044`  
**Code:**
```python
fip_raw = ((13 * hr + 3 * bb - 2 * k_val) / ip) + 3.17 if ip > 0 else 4.50
fip_per_ip = fip_raw / 9.0  # Convert FIP (per 9) to per-inning rate
blended_rate = 0.40 * er_per_ip + 0.60 * fip_per_ip
```
**Verdict:** The FIP formula `(13×HR + 3×BB - 2×K) / IP + constant` is standard (note: HBP excluded since SaberSim data typically doesn't project HBP separately). The FIP constant 3.17 is cited as matching 2024 lgERA=4.08, which is a reasonable approximation of the 2024 constant (~3.17–3.20). The 60/40 blend (FIP dominant) is a sensible bias toward the more regressive, stable measure. The `er_per_ip` ERA proxy represents same-game-projection ER, not historical ERA, giving a more direct but noisier signal. Blend logic is sound.

---

### Finding 11.17: CORRECT — MLB OUTS gate (unders blocked) is consistent with NB model

**File:** `engine/run_picks.py:980-982`  
**Code:**
```python
if stat == "OUTS" and direction == "under":
    return False, "G_OUTS_UNDER"
```
**Verdict:** The comment explains SaberSim projects conservative median IP, so market prices to mode IP → OUTS unders are structurally negative EV. OUTS uses Normal distribution (SIGMA["OUTS"]: mult=0.30, min=3.0). Blocking all unders removes a documented structural losing direction. Correct directional gate.

---

## Section 12 — WNBA-Specific Math

### Finding 12.1: CORRECT — WNBA_EARLY_SEASON_EDGE_MULT formula and loop logic correct

**File:** `engine/run_picks.py:345-348, 965-969`  
**Code:**
```python
WNBA_EARLY_SEASON_EDGE_MULT = [
    (14, 0.80),   # days 4-14: effective edge × 0.80
    (21, 0.90),   # days 15-21: effective edge × 0.90
]
...
effective_edge = edge
for day_cap, mult in WNBA_EARLY_SEASON_EDGE_MULT:
    if 0 < season_day <= day_cap:
        effective_edge = edge * mult
        break
```
**Verdict:** The loop iterates the list in ascending order. Day 4–14: first entry `0 < day <= 14` matches → mult=0.80, break. Day 15–21: first entry fails `day <= 14`, second entry `0 < day <= 21` matches → mult=0.90, break. Day 22+: neither entry matches, `effective_edge = edge` (no reduction). Day 1–3 is blocked by `G_WNBA_OPEN` gate before this code runs. The logic correctly implements the intended three-tier schedule. Correct.

---

### Finding 12.2: CORRECT — WNBA_EDGE_FLOOR=0.035 applied correctly vs standard edge floor

**File:** `engine/run_picks.py:349, 970-971`  
**Code:**
```python
WNBA_EDGE_FLOOR = 0.035
...
if effective_edge < WNBA_EDGE_FLOOR:
    return False, "G_WNBA_EDGE"
```
**Verdict:** The standard G9 gate (`if edge < 0.03`) still runs after this block. `WNBA_EDGE_FLOOR=0.035 > 0.03` means WNBA has a 3.5% floor vs the standard 3.0%. The early-season multipliers compound this: at mult=0.80, a pick needs raw edge ≥ 0.035/0.80 = 0.04375 to pass during days 4–14. At mult=0.90, the raw edge needed is 0.035/0.90 = 0.03889. The 3.5% floor is justified by wider WNBA vig (~-115/-115 vs NBA -110), which structurally reduces expected CLV. Correct and well-reasoned.

---

### Finding 12.3: CORRECT — WNBA_OPENING_GATE_DAYS=3 date arithmetic correct

**File:** `engine/run_picks.py:343, 954-960`  
**Code:**
```python
WNBA_SEASON_START = date(2026, 5, 13)
WNBA_OPENING_GATE_DAYS = 3
...
today_date = datetime.now().date()
season_day = (today_date - WNBA_SEASON_START).days + 1  # day 1 = opening day
if 1 <= season_day <= WNBA_OPENING_GATE_DAYS:
    return False, "G_WNBA_OPEN"
```
**Verdict:** `(today - season_start).days + 1` correctly makes opening day = day 1. `1 <= season_day <= 3` blocks days 1, 2, and 3 (May 13, 14, 15). Day 4 = May 16 is the first day picks are allowed (with 0.80 multiplier). `datetime.now().date()` uses local time, not ET. On a machine in ET this is correct; if the machine is in a different timezone, season_day could be off by ±1 for games near midnight. In practice, picks run pre-game in the afternoon so this is a very minor risk.

---

### Finding 12.4: UNCERTAIN — WNBA pre-season not blocked by G_WNBA_OPEN

**File:** `engine/run_picks.py:959`  
**Code:**
```python
if 1 <= season_day <= WNBA_OPENING_GATE_DAYS:
    return False, "G_WNBA_OPEN"
```
**Verdict:** If `season_day <= 0` (before `WNBA_SEASON_START`), neither G_WNBA_OPEN nor the multiplier loop applies. A WNBA CSV from before May 13 2026 would pass through with only the base 3.5% floor. In practice, SaberSim only generates WNBA CSVs on WNBA game days, so this is a theoretical edge case. If WNBA_SEASON_START is not updated next year, pre-season picks could slip through. Low risk but worth noting for annual maintenance.

---

### Finding 12.5: CORRECT — G_WNBA_EDGE gate threshold correct

**File:** `engine/run_picks.py:962-971`  
**Code:**
```python
# G_WNBA_EDGE: higher edge floor to compensate for wider WNBA vig (~-115/-115 vs NBA -110)
effective_edge = edge
for day_cap, mult in WNBA_EARLY_SEASON_EDGE_MULT:
    if 0 < season_day <= day_cap:
        effective_edge = edge * mult
        break
if effective_edge < WNBA_EDGE_FLOOR:
    return False, "G_WNBA_EDGE"
```
**Verdict:** The gate correctly applies the multiplier first, then checks against the floor. Using `effective_edge` (post-multiplier) rather than `edge` (raw) means G_WNBA_EDGE has compounding effects during early season — correct design intent (less aggressive early season). Correct.

---

### Finding 12.6: CORRECT — SIGMA_WNBA fallback values appropriate

**File:** `engine/run_picks.py:326-331`  
**Code:**
```python
SIGMA_WNBA = {
    "PTS": {"mult": 0.38, "min": 3.5},
    "AST": {"mult": 0.55, "min": 1.1},
    "REB": {"mult": 0.45, "min": 2.0},
    "3PM": {"mult": 0.48, "min": 0.70},  # Normal model; NB_R not used for WNBA
}
```
**Verdict:** The comments cite research: WNBA PTS CV ~0.36 (+44% vs NBA ~0.25); AST CV ~0.56 (+12%); REB CV ~0.43 (-9%). PTS mult=0.38 vs NBA 0.35 (slightly wider, correct direction for higher CV). AST mult=0.55 vs NBA 0.45 (wider, correct). REB mult=0.45 vs NBA 0.58 (narrower, consistent with CV being 9% lower). 3PM mult=0.48 with min=0.70 for Normal model (not NB, since WNBA 3PM is underdispersed var/mean ~0.70). The minimum floors are appropriate for low-mean WNBA stats. The sigma selection logic correctly prefers SIGMA_WNBA for WNBA picks and falls through to SIGMA for stats not in SIGMA_WNBA (e.g. REC if it were ever a WNBA market).

---

### Finding 12.7: CORRECT — COMBO_RHO_WNBA correlations applied correctly

**File:** `engine/run_picks.py:335-339, 797-810`  
**Code:**
```python
COMBO_RHO_WNBA = {
    ("PTS", "REB"): 0.13,
    ("PTS", "AST"): 0.04,
    ("REB", "AST"): 0.05,
}
...
rho_table = COMBO_RHO_WNBA if sport == "WNBA" else COMBO_RHO
...
var += 2.0 * rho * sigmas[i] * sigmas[j]
```
**Verdict:** The combo variance formula `Var(X+Y+Z) = Var(X) + Var(Y) + Var(Z) + 2ρ_XY σ_X σ_Y + 2ρ_XZ σ_X σ_Z + 2ρ_YZ σ_Y σ_Z` is correctly implemented in the nested loop. WNBA correlations (~0.04–0.13 vs NBA 0.23–0.33) reflect the 9-player/336-game calibration note. The very low WNBA correlations (nearly additive) mean the combo variance is approximately the sum of individual variances — reasonable given smaller WNBA sample. Fallback rho of 0.10 for missing pairs (line 809) is the correct default for WNBA. Correct.

---

### Finding 12.8: CORRECT — WNBA 3PM correctly routes to Normal (not NB)

**File:** `engine/run_picks.py:716, 326-331`  
**Code:**
```python
elif stat in NB_STATS and not (sport == "WNBA" and stat == "3PM"):
    # WNBA 3PM falls through to Normal below
    ...
else:
    s = (SIGMA_WNBA.get(stat) if sport == "WNBA" else None) or SIGMA.get(stat)
    sigma = max(proj * s["mult"], s["min"])
```
**Verdict:** The exception `not (sport == "WNBA" and stat == "3PM")` correctly routes WNBA 3PM to the Normal branch. SIGMA_WNBA["3PM"] = {mult:0.48, min:0.70} is applied. The comment explains this: WNBA 3PM var/mean ~0.70 (underdispersed, i.e., more regular than Poisson), making Normal appropriate. NB has var/mean > 1 by construction for r < ∞, so NB would be wrong for underdispersed data. Correct distribution choice.

---

### Finding 12.9: CORRECT — WNBA uses SIGMA_WNBA in G14 clearance gate

**File:** `engine/run_picks.py:1012-1014`  
**Code:**
```python
if stat in SIGMA and stat not in POISSON_STATS:
    _s = (SIGMA_WNBA.get(stat) if sport == "WNBA" else None) or SIGMA[stat]
    _sigma = max(proj * _s["mult"], _s["min"])
    _z = (line - proj) / _sigma if direction == "under" else (proj - line) / _sigma
    if _z < 0.10:
        return False, "G14"
```
**Verdict:** G14 correctly uses SIGMA_WNBA for WNBA picks in the same branch as calc_prop_prob. The sigma computation is identical, ensuring G14 uses the same model parameters as the probability calculation itself. Consistent and correct.

---

## Section 13 — NHL-Specific Math

### Finding 13.1: CORRECT — SOG uses Poisson distribution, appropriate for shot counts

**File:** `engine/run_picks.py:284, 700-715`  
**Code:**
```python
POISSON_STATS = {"AST", "REB", "SOG", "REC", "HITS"}

# In calc_prop_prob:
if stat in POISSON_STATS and line <= POISSON_CUTOFF:
    k = math.floor(line)
    # Integer line: push-adjusted; half-integer: standard CDF
    ...
    under_p = poisson_cdf(k, proj)
    over_p = 1.0 - poisson_cdf(k, proj)
```
**Verdict:** Poisson is the standard distribution for count data like shots on goal. SOG per game for a typical NHL forward projects to 2–5 shots, with Poisson being appropriate at these scales (the Poisson cutoff of 8.5 means all practical SOG lines use this model). NHL shots are a count process: each opportunity yields a shot with some probability. Poisson is the standard model and is appropriate here. NHL forwards typically have Poisson-like shot distributions (goal-scorer vs point-getter profiles aside).

---

### Finding 13.2: ISSUE — SIGMA["SOG"] entry is dead config (Poisson takes precedence)

**File:** `engine/run_picks.py:269, 284`  
**Code:**
```python
SIGMA = {
    ...
    "SOG": {"mult": 0.55, "min": 1.2},
    ...
}
POISSON_STATS = {"AST", "REB", "SOG", "REC", "HITS"}
```
**Verdict:** SOG is in both `SIGMA` and `POISSON_STATS`. In `calc_prop_prob`, the `POISSON_STATS` branch is checked first, so `SIGMA["SOG"]` is never used. Additionally, the G14 gate (`if stat in SIGMA and stat not in POISSON_STATS`) also excludes SOG. `SIGMA["SOG"]` is a dead configuration entry. It would only become active if SOG were removed from POISSON_STATS. This is the same issue as SIGMA["HITS"] (Finding 11.15). Low severity — no runtime impact.

---

### Finding 13.3: CORRECT — No goalie/save props modeled; goalies filtered at parse time

**File:** `engine/run_picks.py:1573-1576`  
**Code:**
```python
elif sport == "NHL":
    # Filter goalies
    if p["pos"].upper() == "G":
        continue
    p["SOG"] = float(clean.get("SOG", clean.get("sog", 0)) or 0)
    p["AST"] = float(clean.get("A", clean.get("a", clean.get("AST", 0))) or 0)
```
**Verdict:** Goalies (pos="G") are filtered out at CSV parse time. Only SOG and AST are loaded for NHL skaters. There are no goalie save/goals-against props in `PROP_MARKETS["NHL"]` (only `player_shots_on_goal` and `player_assists`). There is no goalie-specific math to audit. The absence of saves modeling is correct — goalie save props have extremely high vig and are not in scope. Correct.

---

### Finding 13.4: CORRECT — NHL AST correctly routed to T3 (not T1)

**File:** `engine/run_picks.py:892-893`  
**Code:**
```python
if stat == "AST" and sport == "NHL":
    return "T3"  # Binary-adjacent at 0.5 line; CV >1.0; 20%+ hold
```
**Verdict:** NHL assists typically bet at 0.5 line (binary: 0 vs 1+ assists), making them Bernoulli-distributed rather than Poisson. The Poisson model applied to AST at the 0.5 line is appropriate (P(X≥1) for Poisson is 1 - e^(-λ)), but the market has 20%+ hold on these binary props, making them structurally worse than NBA AST (which trades at higher lines like 5.5 where the Poisson model is more informative). T3 tier (6% min edge) is the correct higher bar for these. Correct.

---

### Finding 13.5: CORRECT — NHL SOG unit cap (6 picks/run) and SPORT_UNIT_CAP (5u) correct

**File:** `engine/run_picks.py:1296-1300`  
**Code:**
```python
# NHL SOG gets 6 per stat, everything else 2
STAT_CAP = defaultdict(lambda: 2)
STAT_CAP["SOG"] = 6

SPORT_UNIT_CAP = {"NBA": 8.0, "WNBA": 4.0, "NHL": 5.0, "NFL": 5.0, "MLB": 8.0}
```
**Verdict:** NHL SOG at 6 picks/run recognises that SOG is the primary (and often only practical) NHL prop market, and players are independent across games. The 5.0u sport cap is appropriate given NHL picks typically size at 0.5–0.75u. The STAT_CAP["SOG"]=6 vs default=2 for other stats is consistent with the documented NHL SOG cap in CLAUDE.md. Correct.

---

### Finding 13.6: CORRECT — G8 binary fragility gate has SOG-specific exception for high-conviction unders

**File:** `engine/run_picks.py:937-943`  
**Code:**
```python
# G8: binary fragility (FIX M3: extended to MLB low-count stats)
# Exception: SOG ≤ 1.5 UNDER passes if model is very confident (WP ≥ 0.80 AND edge ≥ 0.15)
if stat in ("AST", "REB", "SOG", "K", "HA", "HITS") and line <= 1.5:
    if stat == "SOG" and direction == "under" and prob >= 0.80 and edge >= 0.15:
        pass  # High-conviction SOG under exception — allow through
    else:
        return False, "G8"
```
**Verdict:** The G8 gate blocks low-count stats at lines ≤1.5 to prevent binary-fragility picks. The SOG exception (WP≥0.80 AND edge≥0.15) is a deliberate carve-out for high-conviction unders where the Poisson model shows strong signal (e.g. injured player returning, fourth-line grinder). The combined gate is mathematically sound — Poisson at line 1.5 for SOG: P(X≤1) ≥ 0.80 requires λ ≤ ~1.4 shots. At typical SOG lines of 2.5–3.5 this gate is irrelevant. Correct.

---

### Finding 13.7: CORRECT — NHL game sigma (ml: 4.0) calibrated appropriately for moneyline

**File:** `engine/run_picks.py:375`  
**Code:**
```python
"NHL":  {"total": 1.2, "spread": 1.5, "team": 1.8, "ml": 4.0},
```
**Verdict:** The comment explains the design: `NHL puck-line spread sigma (1.5 goals) inflates ML win probs to 80%+ when used for P(margin > 0). Need a wider sigma (~4.0) to produce realistic 55-65% win probs for typical NHL favorites.` The total sigma of 1.2 goals is appropriate for NHL (average total ~6 goals, σ ≈ 1.2). The spread sigma of 1.5 is appropriate for the puck-line (±1.5 goal margin). Using a distinct ML sigma (4.0) instead of reusing the spread sigma is the correct approach for NHL, where the puck-line is a fixed derivative of the ML (not an independent margin signal). Correct.

---

### Finding 13.8: CORRECT — NHL puck-line correctly classified as fixed-spread (not blended)

**File:** `engine/run_picks.py:379-382`  
**Code:**
```python
# Sports where the spread is always a fixed ±1.5 line (MLB runline, NHL puck line).
_FIXED_SPREAD_SPORTS = {"MLB", "NHL"}
```
**Verdict:** For variable-spread sports (NBA, NFL), the market spread line carries independent information about the projected margin, so BLEND_ALPHA anchoring against the spread is appropriate. For NHL/MLB, the spread is always ±1.5 and is derived from the ML — it carries no independent margin information. Treating it as a fixed-spread sport and anchoring ML win probability to the ML no-vig (not the spread) is mathematically correct. This prevents the model from treating the puck-line as a 1.5-goal handicap insight. Correct.

---

### Finding 13.9: CORRECT — INJURY_TRIGGER_BONUS for SOG is consistent with other stats

**File:** `engine/run_picks.py:472-474`  
**Code:**
```python
INJURY_TRIGGER_BONUS = {
    ...
    "SOG": 8,  # NHL SOG replacement, similar lag profile to PTS
    ...
}
```
**Verdict:** SOG=8 is between AST=10 (highest book-lag) and REB=7 (default). The comment notes similarity to PTS (also 8), reflecting that when a key NHL forward is scratched, the replacement's SOG bump has similar book-update lag to an NBA scorer's PTS bump. No mathematical error. Correct.

---

### Finding 13.10: CORRECT — KILLSHOT allows SOG but correctly excludes NHL-specific edge cases

**File:** `engine/run_picks.py:200`  
**Code:**
```python
KILLSHOT_STAT_ALLOW = frozenset({"PTS", "AST", "SOG"})
```
**Verdict:** SOG is allowed in KILLSHOT. The KILLSHOT gates (tier=T1, score≥65, win_prob≥0.65, odds∈[-200,+110]) are sufficiently strict that a KILLSHOT SOG pick requires T1 tier, which requires min_edge≥0.03. The T1 classification is correct for SOG (line 398: `"T1": {"stats": {"AST", "SOG", ...}}`). The win_prob≥0.65 floor (from Platt-calibrated probabilities) provides an additional quality bar for binary/Poisson props like SOG. No mathematical issues.

---

## Summary Table

| # | Section | Stat | Verdict | Severity |
|---|---------|------|---------|----------|
| 11.1 | MLB | HRR projection | CORRECT | — |
| 11.2 | MLB | HRR distribution (NB r=1.5) | CORRECT | — |
| 11.3 | MLB | 25%+ HRR edge at O0.5 | ISSUE | Low (documented, gated) |
| 11.4 | MLB | K/OUTS confirmed-starter gate | CORRECT | — |
| 11.5 | MLB | NRFI independence assumption | CORRECT | — |
| 11.6 | MLB | NRFI full-game runs as 1st-inning proxy | ISSUE | Low (approximation) |
| 11.7 | MLB | NRFI no-vig edge calculation | CORRECT | — |
| 11.8 | MLB | F5 total 0.503 scaling + blend | CORRECT | — |
| 11.9 | MLB | F5 ML margin model | CORRECT | — |
| 11.10 | MLB | F5 spread cover probability | CORRECT | — |
| 11.11 | MLB | mlb_starter_fetcher type annotation | ISSUE | Low (doc-only) |
| 11.12 | MLB | NRFI er_per_ip ZeroDivisionError | ISSUE | Low (theoretical) |
| 11.13 | MLB | NRFI missing pitcher guard | CORRECT | — |
| 11.14 | MLB | G14 HRR stale comment | ISSUE | Low (comment-only) |
| 11.15 | MLB | SIGMA["HITS"] dead entry | ISSUE | Low (dead config) |
| 11.16 | MLB | FIP formula | CORRECT | — |
| 11.17 | MLB | OUTS under gate | CORRECT | — |
| 12.1 | WNBA | WNBA_EARLY_SEASON_EDGE_MULT loop | CORRECT | — |
| 12.2 | WNBA | WNBA_EDGE_FLOOR=0.035 | CORRECT | — |
| 12.3 | WNBA | WNBA_OPENING_GATE_DAYS date arithmetic | CORRECT | — |
| 12.4 | WNBA | Pre-season not blocked | UNCERTAIN | Low |
| 12.5 | WNBA | G_WNBA_EDGE threshold | CORRECT | — |
| 12.6 | WNBA | SIGMA_WNBA fallback values | CORRECT | — |
| 12.7 | WNBA | COMBO_RHO_WNBA application | CORRECT | — |
| 12.8 | WNBA | WNBA 3PM → Normal (not NB) | CORRECT | — |
| 12.9 | WNBA | G14 uses SIGMA_WNBA for WNBA | CORRECT | — |
| 13.1 | NHL | SOG Poisson distribution | CORRECT | — |
| 13.2 | NHL | SIGMA["SOG"] dead entry | ISSUE | Low (dead config) |
| 13.3 | NHL | No goalie saves props | CORRECT | — |
| 13.4 | NHL | NHL AST → T3 | CORRECT | — |
| 13.5 | NHL | SOG STAT_CAP=6 + 5u unit cap | CORRECT | — |
| 13.6 | NHL | G8 SOG under exception | CORRECT | — |
| 13.7 | NHL | GAME_SIGMA["NHL"]["ml"]=4.0 | CORRECT | — |
| 13.8 | NHL | NHL as fixed-spread sport | CORRECT | — |
| 13.9 | NHL | INJURY_TRIGGER_BONUS["SOG"] | CORRECT | — |
| 13.10 | NHL | KILLSHOT allows SOG | CORRECT | — |

---

## Critical Issues (require immediate fix)
None found.

## Medium Issues (should fix)
- **11.12** — `er_per_ip` has no guard against `ip=0.0`. Fix: `ip = p.get("IP", 1) or 1.0` (one character change closes a theoretical ZeroDivisionError path).

## Low/Cosmetic Issues (deferred OK)
- **11.3** — 25%+ HRR edge at O0.5 is model inflation per G13B's own comment. Document and monitor; do not widen G2 further without more shadow data.
- **11.11** — `fetch_confirmed_starters` docstring says `-> dict[str, str]` but returns `dict[str, list[str]]`. Update the type hint.
- **11.14** — G14 comment lists HRR as a SIGMA stat. Update comment to remove HRR.
- **11.15** / **13.2** — SIGMA["HITS"] and SIGMA["SOG"] are dead entries (both stats use Poisson). Remove or add `# dead: POISSON_STATS takes priority` comment.
- **12.4** — Pre-season WNBA not explicitly blocked. Add `or season_day <= 0` guard to WNBA gate block (or rely on SaberSim never generating pre-season CSVs).
