# Audit 2026-05-25 — Track J: Sharp Process & Industry Standards

Auditor: Claude Sonnet 4.6 (automated)
Research sources: VSiN, Sharp Football Analysis, OddsJam, Outlier, Wizard of Odds, academic literature on Kelly criterion and sample size
Data: data/pick_log.csv

---

## J1. CLV as Primary Edge Signal

### Empirical data from pick_log.csv (n=53 rows with non-empty CLV)
- **Mean CLV: −0.758%** (95% CI: −1.643% to +0.128%)
- **Beat rate: 11/53 = 20.8%** (random expectation ≈ 50%)
- CLV by run type: primary n=45 mean=−0.96%; bonus n=8 mean=+0.38%
- CLV by hour: 15:xx → +1.03% (n=6); 18:xx → +0.05% (n=10); 19:xx → −1.52% (n=26)

### J-1 (CRITICAL) — Mean CLV negative; market consistently disagrees with model

```
TRACK: J
FILE: data/pick_log.csv
LINE: N/A (data)
SEVERITY: CRITICAL
N: 53
ISSUE: Mean CLV = −0.758% over 53 samples. Beat rate 20.8% vs expected 50%. The 95% CI
barely includes zero. Professional sharp literature (VSiN, OddsJam, Sharp Football Analysis)
is unambiguous: consistently negative CLV over 50+ samples is the strongest available
evidence that a betting process does NOT have edge. Lines are moving against picks after
placement in 79.2% of cases — the inverse of sharp behavior.
The model's self-reported mean edge of 12.5% is contradicted by every market signal available.
IMPACT: Negative CLV is a leading indicator of long-run losses. The win rate of 45.9%
(below 52.38% break-even) is consistent with this. Primary pick WR of 53.3% is marginally
above break-even but CLV data suggests this will not hold at scale.
FIX: Treat CLV as the primary diagnostic, not WR or model edge. Investigate WHY lines move
against positions. Likely causes in priority order:
(1) Late bet timing — 47% of picks placed at 19:xx (near tip); see J-5.
(2) Model using stale/wrong projection data already priced by the market.
(3) Systematic over-prediction (confirmed by E6 — 10pp gap outside 95% CI).
Until CLV turns reliably positive over 200+ samples, treat all model edge estimates
as unreliable.
```

---

## J2. Vig Removal Method

**Production formula (run_picks.py ~line 626):**
```python
def no_vig(imp1, imp2):
    total = imp1 + imp2
    return imp1 / total, imp2 / total   # additive/proportional method
```

**CLV formula (capture_clv.py ~line 874):**
```python
return implied_prob(closing_odds) - implied_prob(your_odds)   # vigged, not vig-free
```

### J-2 (MEDIUM) — Edge is no-vig; CLV is vigged — not directly comparable

```
TRACK: J
FILE: engine/run_picks.py + engine/capture_clv.py
LINE: ~626 (edge), ~874 (CLV)
SEVERITY: MEDIUM
N: N/A
ISSUE: Edge is computed using no-vig probabilities (correct for edge measurement). CLV is
computed using raw vigged implied probabilities (correct for CLV convention). These metrics
use different probability bases, so "model edge = 12.5%" vs "mean CLV = −0.76%" are NOT
directly comparable — CLV magnitude is compressed by ~0.5–1pp vs no-vig CLV in asymmetric
markets. The sign and direction are preserved, so beat rate is unaffected.
IMPACT: Reports that compare edge and CLV on the same scale are slightly misleading.
FIX: Document in clv_report.py output: "Note: CLV uses vigged implied; edge uses no-vig.
These metrics are directionally comparable but not magnitude-comparable."
```

### J-3 (LOW) — Additive vig removal is acceptable but Power method is marginally more accurate

```
TRACK: J
FILE: engine/run_picks.py
LINE: ~626–631
SEVERITY: LOW
N: N/A
ISSUE: The additive (proportional) method is used. The Power/Shin methods are more accurate
for asymmetric markets by accounting for favorite-longshot bias. At -110/-110 (symmetric):
difference = 0. At -130/+110: difference ~1pp on the favorite side. Published research
(Outlier, Betherosports) recommends the Power method as the best general default for
two-sided sports markets.
IMPACT: Marginal. Most NBA/NHL props are at or near -110/-110, making the difference zero.
Matters more for NHL/MLB moneylines with heavy chalk.
FIX: No urgent change. If ever evaluating sharp two-sided markets with heavy chalk consistently,
upgrade to the Power method. Current additive method is acceptable.
```

---

## J3. Kelly Fraction

**VAKE effective fraction (WP=0.60, -110 odds, edge=9%):**
- Full Kelly: `f = (0.909×0.60 − 0.40)/0.909 = 16.0%` of bankroll
- Quarter-Kelly: 4.0% of bankroll
- VAKE at edge=9%, T1: 1.25u base × ~0.85 var × ~0.90 tier ≈ 0.95u → ~1.0u = **1.0% of bankroll**
- Effective fraction: **~1/16th of full Kelly, or ~1/4 of quarter-Kelly**

**`size_daily_lay()`**: Explicit quarter-Kelly (`kelly_full * 0.25 * 100.0`), capped 0.25–0.75u. ✓

### J-4 (LOW) — VAKE is ~1/16th Kelly — very conservative, but currently protective

```
TRACK: J
FILE: engine/run_picks.py
LINE: ~410–414
SEVERITY: LOW
N: N/A
ISSUE: VAKE is substantially more conservative than even quarter-Kelly (industry minimum).
At the current CLV data showing negative edge, this conservatism is PROTECTIVE — true
Kelly would be negative or zero if the model has no edge. VAKE conservatism limits losses
on a model that currently shows negative CLV.
IMPACT: If the model is ever genuinely sharp (positive CLV >+1.5% sustained), VAKE will
severely under-bet and leave EV on the table. But at the current evidence level, this is
not a concern.
FIX: No immediate action. Document that VAKE is a flat-table size system, NOT a Kelly system.
When/if CLV turns reliably positive over 200+ samples, consider calibrating stake sizes to
a fraction of full Kelly for high-conviction picks.
```

---

## J4. Sample Size Adequacy

**Statistical summary:**
- n=182 settled singles (primary+bonus), WR=53.3%, 95% CI [46.0%, 60.5%]
- n=244 all graded (including SGP/parlay), WR=45.9%, 95% CI [39.6%, 52.2%]
- Break-even at -110: 52.38% — above the upper CI bound for all-graded WR
- CLV n=53 — inadequate for reliable calibration conclusions
- Stat-direction buckets with n≥30: only 2 (SOG under n=41, parlay n=52)

### J-5 (HIGH) — n=244 insufficient for reliable model assessment; premature conclusions being drawn

```
TRACK: J
FILE: data/pick_log.csv
LINE: N/A (data)
SEVERITY: HIGH
N: 244 total / 182 singles
ISSUE: n=244 total graded is below the 500-pick minimum cited in professional betting
literature for reliable model assessment. Across meaningful sub-segments (sport × stat ×
direction), almost no bucket reaches n≥30. The all-graded WR of 45.9% with 95% CI
[39.6%, 52.2%] is below break-even even at the upper bound — statistically significant
underperformance. However, the source (parlays dragging it down vs singles at 53.3%)
requires more data to disentangle.
IMPACT: Any segment-level conclusions (e.g., "NBA unders are our edge", "3PM is weak")
are not statistically reliable at current sample size. Gates being added based on n<30
empirical patterns carry reversal risk.
FIX: Run analyze_picks.py weekly. Target 500 W/L graded singles before drawing calibration
conclusions. CLV needs 200+ samples before it's conclusive. Do not change tier structures
or stat selection based on sub-100-sample data.
```

### J-6 (MEDIUM) — Parlay WR mixed into headline overall WR

```
TRACK: J
FILE: engine/analyze_picks.py + engine/clv_report.py
LINE: headline stats computation
SEVERITY: MEDIUM
N: N/A
ISSUE: The overall WR of 45.9% conflates parlay WR (23.1% for SGP/longshot — approximately
expected for these payout structures) with singles WR (53.3%). This creates a misleadingly
pessimistic headline figure. The clv_report.py daily_lay exclusion is correct but
SGP/longshot are still included in overall stats.
IMPACT: Misleads any assessment based on top-level WR. Could drive premature interventions
on a model that is marginally positive on singles.
FIX: Break out primary+bonus WR vs SGP+longshot separately in headline stats in both
clv_report.py and analyze_picks.py. Current BY RUN TYPE breakdowns exist but are not
surfaced as the primary number.
```

---

## J5. Market Timing

**Pick timing distribution (pick_log.csv):**
- 15:xx — 21 picks (8.4%), mean CLV +1.03%, beat rate 50%
- 17:xx — 39 picks (15.6%), mean CLV −1.76%, beat rate 40%
- 18:xx — 34 picks (13.6%), mean CLV +0.05%, beat rate 10%
- 19:xx — 118 picks (47.2%), mean CLV −1.52%, beat rate 15%
- 20:xx — 30 picks (12%), mean CLV +0.40%, beat rate 25%

### J-7 (HIGH) — 47% of picks placed at 19:xx (near tip); CLV strongly worse late

```
TRACK: J
FILE: data/pick_log.csv + engine/run_picks.py (timing)
LINE: N/A (data + ops)
SEVERITY: HIGH
N: 53 CLV samples across time buckets
ISSUE: 47% of picks are placed at 19:xx ET — within 30–60 minutes of NBA tip-off. CLV
at 19:xx = −1.52% with only 15% beat rate. CLV at 15:xx = +1.03% with 50% beat rate.
Sharp literature consensus: bet as early as possible after lines open (typically noon ET
for same-day NBA), not near tip-off. By tip-off, sharps have already moved lines in the
correct direction. Late bets compete against a market that has priced in information
the model doesn't have.
The ~2.5pp CLV difference between 15:xx and 19:xx is meaningful. Moving the run to
midday may dramatically improve CLV even without any model changes.
IMPACT: The late-timing CLV gap is the single most actionable hypothesis for improving
results without touching the model.
FIX: (1) Move daily run to ~noon ET (after lines open) when possible. (2) Track CLV
separately for early-day vs near-tip runs by adding a run_hour column to pick_log.csv.
(3) For --late-run: document that this is expected to produce worse CLV and should only
be used when projections change (injury, lineup).
```

---

## J6. SGP Correlation vs Books

**SGP implementation:** Gaussian copula with empirically calibrated pairwise ρ values. NOT a naive product. ✓

### J-8 (MEDIUM) — SGP edge computed vs book's correlation-adjusted price

```
TRACK: J
FILE: engine/sgp_builder.py
LINE: ~610–618
SEVERITY: MEDIUM
N: N/A
ISSUE: Books adjust SGP odds for within-game correlation — the posted SGP price already
embeds the book's correlation model. The engine computes edge as model fair value vs book
SGP price. This means the copula model is being compared against the book's correlation
model, not against "wrong" independent pricing. Industry research (Wizard of Odds) confirms
SGP house edges run 15–25% vs 4–5% for singles. The BetMGM preference note acknowledges
2–3% better SGP pricing, but this still embeds correlation discounts.
The true edge on SGP is: your_copula_value - books_correlation_adjusted_price.
If your copula is more accurate than the book's, you have edge. If less accurate, you don't.
IMPACT: SGP edge estimates assume the model's copula is better than the book's correlation
model. No empirical validation exists (SGP CLV is not tracked — CLV daemon skips PARLAY stat).
FIX: (a) Once SGP Platt gate fires (100 slips, currently 43/100), apply sport-specific
calibration. (b) Add post-hoc check: compare posted SGP odds vs naive independent-leg
product — the gap reveals the book's correlation discount. If the copula is below the
naive product, genuine value identified. (c) Store copula joint probability in win_prob
field of SGP log rows (currently blank).
```

---

## J7. Sharp vs Square Books

**CO_LEGAL_BOOKS top usage (pick_log.csv):** espnbet (66 picks), draftkings (50), betmgm (36), hardrockbet (27), fanduel (17). Circa Sports: 0 picks.

### J-9 (MEDIUM) — Circa Sports (sharpest CO book) never used; CLV benchmarked vs soft books only

```
TRACK: J
FILE: engine/run_picks.py
LINE: CO_LEGAL_BOOKS list
SEVERITY: MEDIUM
N: N/A
ISSUE: Circa Sports IS in CO_LEGAL_BOOKS but appears in 0 picks in the log. The most-used
books (espnbet, DraftKings, BetMGM) are soft books that limit winners and lag on sharp
action. CLV captured by the daemon uses the same soft-book closing lines as the benchmark.
CLV vs soft-book closing is a softer benchmark than CLV vs Pinnacle (the gold standard).
A pick that beats DraftKings close may still be behind the sharp money close.
Pinnacle is not available in Colorado (not CO-legal). Circa is sharp but apparently
not offering competitive lines on the markets this system bets.
IMPACT: CLV of −0.758% measured against soft-book closes. True CLV vs sharp close would
likely be even more negative by 0.5–1.5pp. This makes the evidence of negative edge even
stronger than the current CLV suggests.
FIX: Consider adding LowVig or Novig as reference-only lines in the CLV daemon (tracking
but not betting). These track Pinnacle-adjacent action. Document that current CLV
benchmark is soft-book, not sharp-book.
```

---

## J8. Model vs Market Reconciliation

**G2 gate (run_picks.py):** Blocks edge ≥ 20% (28% for soft O0.5 markets). ✓
**GG1 gate (game lines):** Blocks edge ≥ 10%. ✓
**Current distribution:** 65 picks (26%) with model edge ≥ 15%. Mean model edge: 12.5%.

### J-10 (HIGH) — No manual review trigger for edges 10–20%

```
TRACK: J
FILE: engine/run_picks.py
LINE: no trigger exists
SEVERITY: HIGH
N: 65 picks with edge ≥ 15%
ISSUE: There is no process or code trigger for investigating picks with edge 10–20%.
With mean model edge 12.5% and 65 picks above 15%, these high-edge picks are posted
without any reconciliation step. Sharp professional practice at edges >10–15%: manually
verify whether the market has information the model doesn't (injury, lineup change, weather,
sharp reverse-line movement). The CLV data shows lines moving AGAINST picks at 19:xx —
suggesting these large edges are projection errors or stale data already arbitraged away
by the market, not genuine edge.
G2 blocks only ≥20% (the most extreme cases). The 10–20% range (most of the model's
high-edge output) is unbounded for human review.
IMPACT: Posting 15%+ edge picks when mean CLV is −1.52% near tip strongly suggests
these edges are model errors. G2 blocks the worst outliers but not the systematic problem.
FIX: Add a warning log for picks with edge ≥ 15% flagged as "[LARGE-EDGE: verify lineup]"
in terminal output. Document: any pick showing model edge > 15% should be cross-referenced
against the most recent injury report and starting lineup before accepting. This is a
process fix — takes 60 seconds per flagged pick but could prevent posting bad edges.
```
