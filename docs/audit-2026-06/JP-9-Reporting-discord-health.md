# AUDIT 2026-06 — JP-9 Reporting/discord/health (JonnyParlay)

Files audited (10 read): discord_post.py, discord_guard.py, webhook_fallback.py, weekly_recap.py, health_check.py, output_format.py, diagnostics.py, brand.py, book_names.py, weekly_recap.py

**Findings (final, excl. refuted): C=0 H=0 M=1 I=7** | constants extracted: 28 | not-done: 4

## Findings

| ID | File:line | Sev | Status | Cat | Known | Title |
|----|-----------|-----|--------|-----|-------|-------|
| JP9-01 | health_check.py:252 | M | confirmed | code |  | EdgeModel constant checks are bare substring matches, not bound to the constant name/value |
| JP9-02 | discord_post.py:837 | I | confirmed | code |  | 12.0-unit daily exposure cap is a hardcoded magic literal duplicated across files (drift risk on a live sizing gate) |
| JP9-04 | discord_post.py:270 | I | confirmed | code | Y | ReadTimeout-after-delivery plus guard release can re-post premium card with @everyone on the next run |
| JP9-06 | discord_post.py:453 | I | unverified | code |  | POTD failure path releases guard but does not fire the fallback alert (inconsistent with premium card) |
| JP9-07 | discord_post.py:121 | I | unverified | code |  | Guard TTL prune cutoff uses ET in discord_post fallback but UTC in the shared discord_guard module |
| JP9-09 | discord_post.py:307 | I | unverified | code |  | Dead local: `tier` computed but never used in premium/POTD embeds |
| JP9-05 | health_check.py:155 | I | refuted | code |  | Frozen-constant checks use exact-whitespace string matches that can false-FAIL (exit 1) on cosmetic reformatting |
| JP9-03 | weekly_recap.py:69 | I | refuted | completeness |  | COUNTED_RUN_TYPES omits 'killshot' — 3u KILLSHOT bets may be excluded from weekly/monthly P&L |
| JP9-08 | weekly_recap.py:475 | I | unverified | code |  | Month-so-far rollup attributes a month-straddling week entirely to the Sunday's month |
| JP9-10 | weekly_recap.py:102 | I | unverified | statistical |  | compute_pl American-odds payout math verified correct (W/L/push/VOID handling) |

## C/H/M detail

### [M] JP9-01 — EdgeModel constant checks are bare substring matches, not bound to the constant name/value
`C:/Dev/JonnyParlay/engine/health_check.py:252-260` · code · status=confirmed

**Evidence:** Section 9 verifies EdgeModel constants with unbound substring tests: `check("EdgeModel LEAGUE_AVG_TOTAL=229", "229" in nbap)` (L252), `"0.128" in nbap` (L254), `"0.305" in nbap` (L254-255), `"0.07" in nbap` (L255), `"25" in nbap` (STL span, L257). These pass if the digit string appears ANYWHERE in nba_projector.py — `"25"`/`"229"`/`"0.07"` will almost always be present regardless of the actual assignment. The label claims a value check but the test does not bind to `LEAGUE_AVG_TOTAL=`, `STL` span=, etc. Same weakness L256 (`check("...EFOLD_TIME=1.5", "DAYS_REST_EFOLD_TIME" in nbap)`) verifies only the NAME, not the value 1.5. Result: silent value drift in EdgeModel constants would NOT be caught while reporting a green PASS.

**Recommendation:** Match anchored assignments, e.g. regex `LEAGUE_AVG_TOTAL\s*=\s*229` and `DAYS_REST_EFOLD_TIME\s*=\s*1.5`, mirroring the stronger style used for thresholds.py/calibrated.py (which grep `"total": 4.6` etc.).

**Verifier (confirmed):** Code verified at C:/Dev/JonnyParlay/engine/health_check.py L249-260. Section 9 checks EdgeModel constants with bare substring tests against the whole nba_projector.py source: check("EdgeModel LEAGUE_AVG_TOTAL=229", "229" in nbap), "0.128" in nbap, "0.305" in nbap, "0.07" in nbap, "25" in nbap, and DAYS_REST_EFOLD_TIME name-only. None bind to the assignment (LEAGUE_AVG_TOTAL= / span= / =1.5). The label asserts a VALUE check the code does not perform.

Materiality is concretely demonstrated, not h


## Confirmed-correct / coverage notes

- **discord_guard.py** is solid: claim_post is a true atomic test-and-set inside one FileLock (L239-255), release_post un-claims only on failure, and _load_unlocked recovers keys from corrupted JSON via regex (L117-179) rather than returning {} and re-spamming @everyone (audit C2). Lock-timeout fallbacks degrade to unlocked I/O with explicit duplicate-post/clobber warnings — acceptable and documented.
- **webhook_fallback.notify_fallback** never raises (L139-142 swallows everything), reads the URL at call time (L69-78), caps content at MAX_CONTENT_LEN=400 (<Discord 2000), and is a silent no-op when DISCORD_FALLBACK_WEBHOOK is unset. Correct paging-without-masking design.
- **weekly_recap.compute_pl / daily_stats** are statistically correct: American-odds payout signs are right, and P/VOID are excluded from BOTH the P&L numerator and the risked denominator so ROI is consistent (audit H-5). win-rate denominator is w/(w+l), excluding pushes. _parse_clv distinguishes 'not captured' (None) from 0.0, and _format_clv_block surfaces coverage gaps loudly so a partial CLV week can't read as full edge.
- **weekly_recap.week_range** correctly returns the most-recently-completed Mon–Sun (and current week on Sundays); week_range_containing and _fmt_week_label are correct and locale-independent (uses MONTH_NAMES / explicit AM/PM, audit M-17/M-22).
- **_webhook_post** (discord_post) splits connect/read timeouts (5,10), parses Retry-After via http_utils.retry_after_secs so a non-JSON 429 body can't crash it, and deliberately does not retry ReadTimeout to avoid in-call duplicates (the cross-run repost edge is noted separately as JP9-04).
- **post_to_discord / posters** all use claim_post before posting and release on failure, preventing double-posts on re-run; force=True (--force-card) releases-then-claims as intended.
- **book_names.py** has a load-time invariant asserting CO_LEGAL_BOOKS ⊆ BOOK_DISPLAY (L82-85); display_book falls back to region-stripping then key.title() so no raw API keys leak. norm_book only strips when the base is a known CO book.
- **brand.py** is a pure side-effect-free constants module (single tagline/handle/emoji source). The root **weekly_recap.py** is a correct runpy shim to engine/weekly_recap.py.
- **output_format.format_output** guards division-by-zero on empty pick days (L310-315), and its verification checklist re-derives the daily-cap total including KILLSHOT + parlay units (M7/16.3). The G8/G11/G14/G15 gate checks mirror the live gating logic for display.
- **health_check** sections 16-21 (WNBA σ keying, Platt space↔formula consistency, NBA/MLB SGP ρ provenance+regression, reliability curve, Platt freshness) are genuine import-time invariant exercisers with statistically sound advisory thresholds (2·binomial-SE drift band, n≥30/bin) — these are strong checks, in contrast to the weak substring checks in section 9.

## Not-Done / incomplete (this module)

| Kind | File | Detail |
|------|------|--------|
| flag-gated | diagnostics.py | Entire redistribution + Vegas-vs-240 diagnostic module is a no-op unless JONNYPARLAY_DIAG_REDISTRIB / JONNYPARLAY_DIAG_VEGAS_VS_240 env vars are set (L42-43,L14 |
| deferred | health_check.py | Section 7 documents NRFI/YRFI/TEAM_TOTAL CLV capture as deferred — checks assert NRFI remains in capture_clv.SKIP_STATS (L237-242), i.e. CLV is intentionally no |
| partial-feature | health_check.py | Section 9 EdgeModel constant checks (L252-260) are unbound substring matches that do not actually validate constant values/names — effective coverage is much we |
| partial-feature | weekly_recap.py | COUNTED_RUN_TYPES (L69) is hand-maintained and explicitly must be kept in sync with grade_picks.py; it omits 'killshot' and 'manual'. KILLSHOT inclusion in week |
