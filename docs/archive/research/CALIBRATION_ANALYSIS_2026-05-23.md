# Calibration Analysis — 2026-05-23
*n=182 graded primary+bonus picks (Apr 14 – May 23)*

---

## Headline Findings

### 1. WP Bucket Calibration — Critical Gap at 0.5-0.6 and 0.7-0.8

| WP Range | Actual WR | Model WR | Gap | n |
|----------|-----------|----------|-----|---|
| 0.50–0.60 | **39.3%** | ~55% | **−15.7pp** | 61 |
| 0.60–0.70 | 63.6% | ~65% | −1.4pp ✅ | 66 |
| 0.70–0.80 | 54.2% | ~75% | **−20.8pp** | 48 |

**The 0.6–0.7 bucket is well-calibrated. Both the low and high ends are badly over-predicted.**

The 0.5–0.6 bucket (n=61, the largest) is hitting at 39.3%. At standard −110 juice,
break-even is ~52.4%. These picks are losing at an alarming rate and there is
currently no MIN_WIN_PROB floor in the engine (only TB had one, and TB is now dead).

The 0.7–0.8 over-prediction is the Platt over-inflation issue — high raw probabilities
get inflated further. Only the H3 Platt refit fixes this structurally.

**Recommended action:** Add a global MIN_WIN_PROB floor of **0.55** for primary picks.
This cuts the bottom portion of the 0.5–0.6 bucket. Setting it at 0.60 would eliminate
the entire bucket but risks reducing card volume significantly.

---

### 2. Over vs Under Directional Gap — Persistent

| Direction | WR | ROI | Model Pred | Gap | n |
|-----------|----|-----|------------|-----|---|
| Under | 55.4% | +11.7% | 60.9% | −5.5pp | 112 |
| Over | **49.2%** | −11.4% | 62.8% | **−13.6pp** | 61 |

Overs are still massively over-predicted (−13.6pp gap). Unders are also over-predicted
but much less so and are profitable. G8B/G8C removed the worst over bleeds; residual
over calibration gap is structural and awaits H3 Platt refit.

---

### 3. 3PM Over at Line 1.5 — Gate Recommended (G8D)

| Bucket | WR | ROI | Model | Gap | n |
|--------|----|-----|-------|-----|---|
| 3PM over ≤1.5 | 50.0% | −15%ish | 70.4% | **−20.4pp** | 16 |
| 3PM over 1.6+ | 0% | — | 68.9% | — | 1 |

50% WR at −110 juice loses money. 20pp calibration gap. n=16, consistent signal.
Was "too noisy" in the May 13 analysis at n=8-9. Now at n=16, the pattern holds.
Recommend gate: ban 3PM overs at line ≤1.5 (G8D).

---

### 4. SOG Under at 3.1–3.5 — Partial Residual After G8C

| Bucket | WR | ROI | Model | Gap | n |
|--------|----|-----|-------|-----|---|
| SOG under ≤2.5 | 51.9% | −0.99u | 58.0% | −6.1pp | 27 |
| SOG under 3.1–3.5 | **42.9%** | +0.29u | 63.7% | **−20.8pp** | 14 |

G8C (shipped today) eliminates ≤2.5. The ≤2.5 historical record (51.9%) wasn't
catastrophic — it was losing at juice but not by much. The 3.1–3.5 range is
worse (42.9%, model 63.7%). n=14 is thin but the gap is large.

Possible action: extend G8C to ≤3.5. Decision: wait for more data (n<20) or act now.

---

### 5. T1 Tier — SOG and AST Driving Losses

| Cohort | WR | Units | Model | n |
|--------|----|-------|-------|---|
| T1 overall | 46.6% | −6.36u | 58.9% | 58 |
| T1 over | **33.3%** | −5.47u | 66.3% | 12 |
| T1 under | 50.0% | −0.89u | 62.6% | 46 |
| T1 SOG | 47.6% | −3.56u | 62.7% | 42 |
| T1 AST | 42.9% | −2.44u | 63.9% | 14 |

T1 is almost entirely SOG + AST picks (56/58 picks = 97%). Both are over-predicted.
T1 overs specifically at 33.3% are the worst subset. The structural fix is H3 Platt
refit. Short-term lever: raise T1 score floor or add a MIN_WIN_PROB that
disproportionately cuts the low end of T1.

---

### 6. Stat Summary (primary+bonus, n≥5)

| Stat + Dir | WR | Units | Model | n |
|------------|----|-------|-------|---|
| Under PTS | **76.9%** | +5.23u | 63.6% | 13 |
| Under AST | 71.4% | +5.53u | 64.0% | 7 |
| Over PTS | 65.0% | +4.21u | 67.7% | 20 |
| Under 3PM | 60.0% | +2.45u | 59.4% | 15 |
| Under REB | 53.8% | +2.08u | 62.0% | 26 |
| Over TEAM_TOTAL | 45.5% | −1.64u | 56.5% | 11 |
| Under SOG | 48.8% | −0.70u | 63.0% | 41 |
| Over 3PM | 47.1% | −2.95u | 70.4% | 17 |
| Over TEAM_TOTAL | 45.5% | −1.64u | 56.5% | 11 |
| Over AST | **25.0%** | −5.21u | 65.3% | 8 |

PTS (both directions) and AST/3PM unders are healthy. SOG unders and 3PM/AST overs
are the problem areas.

---

## Priority Actions

| # | Action | Confidence | Effort |
|---|--------|-----------|--------|
| 1 | Add MIN_WIN_PROB = 0.55 global floor | High (n=61) | Low |
| 2 | Gate 3PM overs ≤1.5 (G8D) | High (n=16) | Low |
| 3 | Extend G8C to SOG under ≤3.5 | Medium (n=14) | Low |
| 4 | H3 Platt refit | Structural fix | Data-gated (~300 rows) |

---

## What's Well-Calibrated (no action needed)

- **Over PTS**: 65.0% actual vs 67.7% model — close to perfect ✅
- **Under 3PM**: 60.0% vs 59.4% — textbook ✅
- **WP 0.60–0.70 bucket**: 63.6% vs ~65% ✅
- **T2 tier**: 58.3% vs 60.2% ✅
- **Bonus run type**: 62.5% actual vs 68.9% predicted — slightly over but profitable ✅
