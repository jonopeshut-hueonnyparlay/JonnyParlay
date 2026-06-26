# AUDIT 2026-06 — JP-8 Pick log schema/writers (JonnyParlay)

Files audited (5 read): pick_log_io.py, pick_log_lock.py, pick_log_schema.py, pick_log_writers.py, pick_labels.py

**Findings (final, excl. refuted): C=0 H=0 M=0 I=4** | constants extracted: 11 | not-done: 6

## Findings

| ID | File:line | Sev | Status | Cat | Known | Title |
|----|-----------|-----|--------|-----|-------|-------|
| JP8-6 | pick_log_io.py:173 | I | refuted | code |  | read_rows_locked opens CSV with encoding='utf-8' and no newline='' — inconsistent with migrate_file (utf-8-sig) and writers (newli |
| JP8-2 | pick_log_schema.py:628 | I | confirmed | completeness |  | Module invariant block asserts v1-v4 column subsets but omits _V5_COLUMNS |
| JP8-3 | pick_log_schema.py:11 | I | unverified | completeness |  | Stale docstring/comment: '29-column schema' and 'Canonical schema (v4)' but module is v5/30 cols |
| JP8-1 | pick_log_writers.py:266 | I | confirmed | code |  | log_picks positional writer omits clv_corrected -> 29-field rows under a 30-col header (schema drift on the live primary ledger) |
| JP8-4 | pick_log_writers.py:295 | I | refuted | completeness |  | is_home/manual validators exist (validate_is_home_for_stat, assert_manual_row_valid) but no writer in this module invokes them |
| JP8-5 | pick_log_writers.py:627 | I | refuted | code |  | _log_value_parlay writes tier='LONGSHOT' for run_type='value_parlay' (likely copy-paste from _log_longshot) |
| JP8-7 | pick_log_writers.py:278 | I | refuted | code |  | win_prob/pick_score/over_p_raw f-string formatting assumes numeric non-None; a None value crashes the daily write |
| JP8-8 | pick_log_writers.py:404 | I | refuted | code |  | _log_daily_lay re-derives logged size from size_daily_lay(combined_prob, parlay_odds) instead of recording the actually-posted siz |
| JP8-9 | pick_log_writers.py:439 | I | unverified | code |  | Parlay appenders (_log_daily_lay/_log_longshot/_log_value_parlay) never write a header; a 0-byte pick_log would get headerless row |

## Confirmed-correct / coverage notes

- **Locking is correct and consistent.** pick_log_lock._pick_log_lock raises on timeout (never yields unlocked, CRIT-1, lock.py:31-32), while the *reader* pick_log_io paths intentionally fall through with a loud stderr warning on timeout (io.py:182-188, 367-372) — a defensible read-side trade-off (stale read > broken reporting). Both writers and io use the same `<path>.lock` convention (io.py:76, lock.py:30).
- **Atomic rewrites are done correctly** everywhere a file is rewritten: tmp + flush + os.fsync + os.replace, with tmp cleanup on failure — log_picks header-drift rewrite (writers:212-228), migrate_file (schema:548-562), write_schema_sidecar (schema:457-463). Appends also fsync before releasing the lock (writers:307-308,444-445,567-568,722-723).
- **normalize_american_odds** (schema:229-267) correctly handles int/float/str, strips a stray leading '+', re-derives sign, renders 0 as '0', and returns '' for None/empty/unparseable — fixing the H-3 bare-'105' bug that made analyze_picks int() choke. _normalize_odds is applied on every odds and parlay-odds write path.
- **DictWriter parlay/bonus paths are width-safe**: _log_daily_lay/_log_longshot/_log_value_parlay and _log_bonus_pick use DictWriter(fieldnames=CANONICAL_HEADER, restval='') (writers:440,565,657,683-ish), so the v5 clv_corrected and the legs key (bonus) are auto blank-filled to the full 30 columns — the JP8-1 drift is isolated to the one positional csv.writer in log_picks.
- **Dedup logic is sound**: keyed on (date, player.lower, stat, line, direction); existing_keys only populated for today's rows (writers:197-206), intra-run dupes guarded by adding new keys as they are appended (writers:246), direction-flip logs a new row by design.
- **Sidecar fail-fast** (_check_sidecar_version, io:117-142) only hard-fails when a sidecar declares schema_version strictly greater than this build; missing/corrupt/non-int sidecars are tolerated — correct forward-incompat guard.
- **migrate_row** guarantees canonical keys, preserves on-disk blanks (no magic backfill), None->'' coercion, drops unknowns consistent with extrasaction='ignore' (schema:142-163).
- **load_rows** centralizes read+filter with correct AND semantics, ISO-lexicographic date compares, case-insensitive sport/stat/tier and case-sensitive run_type matching mirroring legacy callers (io:234-346).
- **pick_labels GAME_LINE_STATS** includes PARLAY (line 41) so aggregate daily_lay rows render correctly; short_label degrades gracefully on empty player and strips name suffixes (jr/sr/ii…) for the prop branch (labels:97-100).
- **KNOWN open items confirmed present, not regressions**: clv_corrected is the Track-B Sprint-1 diagnostic-only column (schema:75-77) — its blank/empty state across writers is consistent with 'filled by capture_clv.py'; context system frozen-disabled as documented.

## Not-Done / incomplete (this module)

| Kind | File | Detail |
|------|------|--------|
| partial-feature | pick_log_writers.py | clv_corrected (v5 column) is only blank-filled by the DictWriter parlay/bonus paths; the positional log_picks writer never emits it, so primary rows are 29 fiel |
| dead-code | pick_log_schema.py | _MIGRATIONS registry + register_migration/migrate_row_chain framework (lines 178-208) has zero registered transforms today; it is a pure pass-through equal to m |
| partial-feature | pick_log_schema.py | validate_is_home_for_stat (line 329) and assert_manual_row_valid/validate_manual_row (lines 568-602) are defined and exported but no writer in pick_log_writers. |
| stub | pick_log_schema.py | migrate_row source_header param (line 142) and normalize_is_home stat param (line 285) are accepted but unused ('reserved for future'). No current behavior depe |
| flag-gated | pick_log_schema.py | migrate_file defaults dry_run=True (line 491) — never rewrites a file unless explicitly invoked with dry_run=False; on-disk migration is a manual operator actio |
| deferred | pick_log_schema.py | context_verdict column is frozen/disabled ('context system removed 2026-05-23; existing rows carry "disabled"', line 63); context_reason/context_score retained  |
