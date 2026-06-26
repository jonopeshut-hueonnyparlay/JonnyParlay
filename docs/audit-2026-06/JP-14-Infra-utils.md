# AUDIT 2026-06 — JP-14 Infra/utils (JonnyParlay)

Files audited (10 read): engine_logger.py, http_utils.py, io_utils.py, log_setup.py, month_names.py, name_norm.py, name_utils.py, paths.py, secrets_config.py, team_resolve.py

**Findings (final, excl. refuted): C=0 H=0 M=0 I=7** | constants extracted: 10 | not-done: 2

## Findings

| ID | File:line | Sev | Status | Cat | Known | Title |
|----|-----------|-----|--------|-----|-------|-------|
| JP14-6 | engine_logger.py:105 | I | unverified | code |  | Cached get_logger call ignores a changed stream/level argument |
| JP14-8 | http_utils.py:67 | I | unverified | statistical |  | Retry-After clamp window [0.5, 30.0] and default 2.0 — confirmed sensible |
| JP14-10 | io_utils.py:42 | I | unverified | code |  | atomic_write_json is correct (same-dir tmp, fsync, os.replace, best-effort cleanup) |
| JP14-9 | log_setup.py:125 | I | unverified | code |  | preemptive_rotate shift logic is correct and bounded to backup_count |
| JP14-11 | name_utils.py:50 | I | unverified | code |  | fold_name / name_key folding contract correct, suffix stripping bounded |
| JP14-7 | paths.py:101 | I | unverified | code |  | PICK_LOG_PATH from env var is not expanduser'd |
| JP14-1 | secrets_config.py:93 | I | refuted | code |  | EDGEMODEL_DB_PATH default points at Documents path, not the real C:\Dev\EdgeModel checkout |
| JP14-5 | secrets_config.py:1 | I | refuted | code |  | File stored with double-encoded (mojibake) bytes in docstring/comments |
| JP14-2 | team_resolve.py:75 | I | refuted | code |  | resolve_team_abbrev substring matching can mis-resolve; called with already-abbreviated input by sigma accessors |
| JP14-3 | team_resolve.py:44 | I | refuted | statistical |  | Hard fallback sigma of 10.0 for unknown market / missing team data |
| JP14-4 | team_resolve.py:54 | I | unverified | statistical |  | n_games >= 20 stabilization gate for using team-specific sigma |

## Confirmed-correct / coverage notes

- **http_utils.retry_after_secs**: precedence (header float -> HTTP-date -> JSON body -> default) is correct, never raises, past-date deltas fall through, and clamp [0.5,30.0] neutralizes a rogue retry_after. default_headers merges extra over UA correctly.
- **io_utils.atomic_write_json**: same-directory tmp (atomic os.replace), flush+fsync before replace, tmp unlinked on failure with original exception re-raised, parent dir created. Correct durable-write helper.
- **log_setup.preemptive_rotate / attach_rotating_handler**: rotation shift is bounded to backup_count (no orphan path.N+1), idempotent handler attachment via samefile with abspath fallback, plain-FileHandler collision returns None instead of silently double-attaching. Correct.
- **month_names**: locale-independent hardcoded tuple with index-0 placeholder for 1-based indexing; month_name/month_name_short validate range and raise ValueError. Correct.
- **name_utils.fold_name / name_key & name_norm.normalize_name**: NFKD accent strip + lowercase + [^a-z\\s] filter + whitespace collapse; suffix stripping bounded to len>2; single source of truth re-exported by name_norm. 'Dončić'=='Doncic' contract holds. Correct.
- **engine_logger.get_logger**: idempotent on (name, normalized log_path), propagate=False prevents double-emit, stderr stream handler keeps warnings on the daemon terminal. Correct for production; only a test-ergonomics gap on changed stream/level after first config.
- **paths._resolve_project_root**: env override -> parent-first project heuristic (anchored on data/ dir, deliberately NOT on pick_log_schema.py to avoid engine/ self-identifying) -> Documents fallback. Sound.
- **team_resolve.get_game_sigma**: relative-scaler formula sigma_league*sqrt((sh^2+sa^2)/(2*meansq)) is unit-correct and neutral (=1) for average teams, sidestepping the dropped home/away covariance the old independence-sum had; WNBA routed through WNBA_TEAM_ABBREV (P0.2 fix). Logic correct; concerns are the 10.0 fallback and the substring resolver, noted above.

## Not-Done / incomplete (this module)

| Kind | File | Detail |
|------|------|--------|
| partial-feature | engine_logger.py | Docstring (M-28) states the print->logging migration is deliberately incomplete: 'doesn't rip out every print overnight'; most engine entry points still use bar |
| deferred | secrets_config.py | EDGEMODEL_DB_PATH default is a Documents-folder path that does not match the real C:\Dev\EdgeModel checkout; relies on .env override and has no existence check  |
