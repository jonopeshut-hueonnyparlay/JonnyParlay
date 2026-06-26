# AUDIT 2026-06 — JP-4 CLV (JonnyParlay)

Files audited (6 read): capture_clv.py, clv_report.py, clv_weekly_export.py, capture_clv.py, clv_report.py, retro_correct_clv.py

**Findings (final, excl. refuted): C=0 H=0 M=2 I=2** | constants extracted: 13 | not-done: 6

## Findings

| ID | File:line | Sev | Status | Cat | Known | Title |
|----|-----------|-----|--------|-----|-------|-------|
| CLV-3 | capture_clv.py:410 | M | confirmed | statistical |  | ±0.25 line-match filter on spreads/totals records CLV only when the line did NOT move → selection bias |
| CLV-2 | clv_report.py:182 | M | confirmed | statistical | Y | avg_clv mixes vigged (pre-reform) and vig-free (post-reform) CLV and reads raw `clv` (vigged-entry biased), not clv_corrected |
| CLV-1 | capture_clv.py:1882 | I | refuted | code |  | STALE/give-up conditions inside the capture-window block are unreachable; missed non-graded picks past tip never STALE-marked |
| CLV-4 | capture_clv.py:1075 | I | refuted | statistical |  | No-vig close uses best-of-CO-books prices on each side independently → not a coherent single-book de-vig |
| CLV-6 | capture_clv.py:170 | I | refuted | completeness | Y | YARDS stat hard-maps to player_reception_yards only — rushing/passing-yards picks would close against the wrong market |
| CLV-7 | capture_clv.py:1206 | I | unverified | code |  | Game-line ML/SPREAD side resolution falls through to away on any non-'home' direction |
| CLV-8 | capture_clv.py:1098 | I | unverified | statistical |  | clv_corrected proxy math verified correct against the -110/-110 hold |
| CLV-5 | retro_correct_clv.py:79 | I | refuted | code |  | retro_correct_clv reads pick_log via pd.read_csv with no FileLock (bypasses the audited locked-read contract) |

## C/H/M detail

### [M] CLV-3 — ±0.25 line-match filter on spreads/totals records CLV only when the line did NOT move → selection bias
`C:/Dev/JonnyParlay/engine/capture_clv.py:410-412` · statistical · status=confirmed

**Evidence:** best_price() and the spread/total branches require `abs(point - line) <= 0.25` (lines 412, 931/957, 1010, 1051, 1229). For player props this is the correct same-number convention. But for SPREAD/TOTAL/F5_* the entire point of CLV is to capture line movement; any closing line that moved >0.25 from the bet line fails the match → `no closing odds found` → the pick is eventually STALE'd. The captured spread/total CLV population is therefore biased toward games where the number was stable, and CLV only ever reflects the price (odds) component at a fixed number, never the line move.

**Recommendation:** For spreads/totals, capture the closing line at its actual (moved) number and price the line+price delta, or at minimum record the moved line rather than discarding it; flag line-moved picks distinctly instead of dropping them.

**Verifier (confirmed):** Code claims verified and the path is reachable in production. The ±0.25 line-match filter is enforced for spreads/totals in best_price (capture_clv.py:412), the SPREAD/F5_SPREAD branch (931/957), TEAM_TOTAL (1010), and get_game_line_closing_odds (1229). The closing snapshot uses the MAIN markets ('spreads'/'totals'/'*_1st_5_innings' via GAME_LINE_CLV_MARKET:211-219 and GAME_LINE_MARKET:174-192), which return only the consensus line per book — no alternate lines. So when the closing main number m

### [M] CLV-2 — avg_clv mixes vigged (pre-reform) and vig-free (post-reform) CLV and reads raw `clv` (vigged-entry biased), not clv_corrected
`C:/Dev/JonnyParlay/engine/clv_report.py:182-292` · statistical · status=confirmed · KNOWN open gate

**Evidence:** analyze() averages the raw `clv` column (line 182, 208). Per the header (line 61-62, 262) rows before CLV_REFORM_DATE=2026-05-31 are vigged CLV and after are vig-free closing side — these are averaged together with no reweighting. Default --days=30 with today=2026-06-25 → cutoff 2026-05-26 pulls in ~5 pre-reform days. Additionally the entry side is left vigged in calc_clv (capture_clv.py:1087-1095), a documented ~-2.4pp negative bias; clv_report never reads the `clv_corrected` column that the daemon writes, so clv_grade() thresholds (0.04 Strong / 0.02 Solid) are applied to a structurally depressed metric.

**Recommendation:** Either restrict averaging to post-CLV_REFORM_DATE rows, or surface clv_corrected alongside clv so the de-vigged-entry value is what is graded; document that pre-reform rows are methodologically different.

**Verifier (confirmed):** The code matches the finding precisely (path is the malformed-but-real C:/Dev/JonnyParlay/engine/clv_report.py).

1) analyze() reads the raw `clv` column at line 182 (clv_raw = safe_float(pick.get("clv"))) and averages it at line 208 (avg_clv = sum(clvs)/len(clvs)); clv_grade()/clv_report apply the 0.04 Strong / 0.02 Solid thresholds (lines 105-116, 289-292) to that raw value. grep for "clv_corrected" in clv_report.py returns ZERO hits — it never reads the de-vigged-entry column the daemon write


## Confirmed-correct / coverage notes

- **calc_clv sign + de-vig verified correct** (capture_clv.py:1075-1095): returns no_vig_close_implied - your_implied; positive ⇒ your odds longer than the de-vigged close ⇒ you beat the close. no_vig_close = a/(a+opp) is the standard proportional two-way de-vig. None-guarded on both implieds.
- **clv_corrected math verified** (capture_clv.py:1098-1118 and retro_correct_clv.py:41-59): proxy correction = p·hold/(1+hold) exactly equals entry_vigged - entry_vigged/(1+hold); with hold=0.0476 the -110 fair prob 0.5 is recovered exactly. The two files are in lockstep. Sign always raises CLV (removes entry vig), which is correct.
- **0.0476 constant is internally consistent** with the /(1+hold) formula even though the docstring loosely calls it 'hold' (it is the overround); the math is right.
- **implied_prob delegation** is single-source via quant.odds.implied_prob_or_none (None-guarded for 0/NaN/inf/non-numeric) — capture, report, and retro all import the same helper (audit P0.6 honored).
- **best_price picks highest American odds** (line 416) = best payout for bettor for both your side and opposite; using best-available close is the conservative CLV convention (harder to show +CLV).
- **STALE values excluded from CLV averages**: STALE rows have empty clv, safe_float→None, dropped from clvs (clv_report.py:200-201); picks_needing_clv also excludes 'STALE' so they aren't re-fetched.
- **Concurrency/atomicity in the write path is solid**: _do_write_closing_odds uses tmp+fsync+os.replace under a 30s FileLock (772-789), refreshes the schema sidecar, and only writes rows whose closing_odds is still blank (won't clobber a prior capture).
- **Quota handling** (L-8): x-requests-remaining=0 and HTTP 401 OUT_OF_USAGE_CREDITS both park the daemon until next UTC midnight; is_quota_exhausted() self-heals after rollover.
- **Daemon is a standalone process with a top-level try/except → logs traceback (1963-1970); it does not run inside generate_projections and cannot crash the daily projection run.** CLV here is measurement only; USE_NO_VIG_ANCHOR carded sizing remains gated off (n≥150), so none of these findings change a live price or stake today.
- **clv_weekly_export interface matches weekly_recap.compute_clv_summary** (avg_clv returned as a decimal and multiplied by 100 in both export:93 and weekly_recap:354 — consistent; the summary docstring line 166 saying 'percentage point' is doc-only and contradicted by the decimal-returning code, no functional impact).
- **F5 / first-inning / team-total market keys corrected (2026-06-09 audit)**: F5_* now map to *_1st_5_innings (prop + game-line paths), NRFI/YRFI to totals_1st_1_innings; prevents the prior STALE-everything / wrong-moneyline failure mode.

## Not-Done / incomplete (this module)

| Kind | File | Detail |
|------|------|--------|
| deferred | capture_clv.py | GAME_LINE_CLV_MARKET omits TEAM_TOTAL: 'TEAM_TOTAL: deferred — needs team-filtered matching in team_totals market' (line 218); get_game_line_closing_odds return |
| flag-gated | capture_clv.py | ENABLE_SHADOW_CLV=False (line 320) — MLB shadow log CLV capture disabled until MLB goes live; SHADOW_LOGS={} when off. |
| dead-code | capture_clv.py | Unreachable give-up/STALE conditions secs_to_start<-STALE_AFTER_SECS (1782,1889) and secs_to_start<-CAPTURE_AFTER_SECS (1895) inside the in-window block; the en |
| partial-feature | capture_clv.py | YARDS→player_reception_yards only (line 170, 'NFL — best available'); rushing/passing yards not distinguishable. NFL data path known-deferred. |
| flag-gated | capture_clv.py | SKIP_STATS={GOLF_WIN,PARLAY,GA,PC} (line 200) — no Odds API market; intentionally never CLV-captured. |
| stub | capture_clv.py | clv_corrected written by the daemon (1862,1869,1347) is consumed by nothing in the read files; clv_report.py never reads the clv_corrected column, and retro_cor |
