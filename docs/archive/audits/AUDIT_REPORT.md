# JonnyParlay Engine — Full Audit Report

**Audit date:** 2026-04-19 (original); **2026-04-24 (supplemental sections 61-69)**
**Scope:** every file reachable from `run_picks.py`, `grade_picks.py`, `capture_clv.py`, plus every support script, launcher, and data file under `data/`.
**Method:** line-by-line read of each file plus parallel sub-audits of the three largest modules, cross-file consistency checks, and a direct inspection of every data artifact on disk.
**Read:** this report is the punch list, not the fix list. Nothing has been changed on disk.

Findings are ordered by severity and then by the file they touch. Every row gives file/line, the current behaviour, why it's wrong, and a suggested fix.

A companion report, **`PICK_LOG_AUDIT.md`**, covers the pick log CSVs specifically. That file has more detail on ledger integrity, schema violations, and cross-log leakage than this one does.

---

## Executive summary

There are four things that really need attention this week, in this order:

1. **`filelock` is not installed on the Windows box that runs the engine.** `data/jonnyparlay.log` shows three `WARNING [grade_picks] filelock not installed — pick_log write is not atomic` entries. This is almost certainly the root cause of every data-integrity finding below (truncated CSV rows, truncated JSON, stale checkpoint). `preflight.bat` and `go.ps1` try to auto-install it, but neither has been run recently enough. Run `pip install filelock --break-system-packages` on Windows before the next pick run.
2. **Atomic writers in the engine are not actually atomic.** `capture_clv.py` writes the checkpoint JSON with `open → json.dump → os.replace`, with no `f.flush()` / `os.fsync()` before the replace. `discord_posted.json` has the same pattern in `morning_preview.py`, `weekly_recap.py`, and `grade_picks.py`. Windows has returned from `close()` without the data hitting disk on every single one of these files — `clv_checkpoint.json` is currently truncated mid-key, `discord_posted.json` is missing its closing `}`, and two of the three pick logs have a truncated final row.
3. **`analyze_picks.py` is out of sync between root and `engine/`.** Root is 318 lines, engine is 371 lines — 53-line drift, including the `--shadow`, `--model-only`, and sample-size warning features that CLAUDE.md says exist. `go.ps1` checks three other pairs but misses this one.
4. **The context system leaks blank `context_*` columns into `pick_log.csv` on every run** even when `--context` is not passed. CLAUDE.md says context is disabled by default, and the columns are in the schema, but the `context_verdict`/`context_reason`/`context_score` cells on every row should be empty strings, not written with `""` through a code path that also writes during context-disabled runs. Check — they are empty strings in the data, but the code in `run_picks.py` unconditionally writes the three columns, which is fine today but hides the fact that `--context` toggling has no observable output in the log. Low risk but worth noting.

The rest of this report is the full punch list, organized by severity.

---

## CRITICAL

### C-1 · `filelock` dependency missing on production Windows install
- **File:** host environment (see `data/jonnyparlay.log`)
- **Evidence:** Three entries, all 2026-04-18 and 2026-04-19, reading `WARNING [grade_picks] filelock not installed — pick_log write is not atomic. Install with: pip install filelock --break-system-packages`
- **Impact:** `run_picks.py` appending, `capture_clv.py` rewriting, and `grade_picks.py` rewriting all race each other against `pick_log.csv`. All three soft-fall-back to non-locked writes. This is the root cause of pick log row truncation (see PICK_LOG_AUDIT C-1 / C-2).
- **Suggested fix:** Install the package, make it a hard dependency in `run_picks.py`/`grade_picks.py`/`capture_clv.py` (fail-fast on `ImportError` instead of falling back), and extend `preflight.bat`/`go.ps1` to refuse to continue if the import fails.

### C-2 · `capture_clv.py` atomic checkpoint write has no `fsync`
- **File:** `engine/capture_clv.py` lines 179-186 (`_save_checkpoint`)
- **Now:** `with open(tmp, "w") ... json.dump(ckpt, f, indent=2); os.replace(tmp, CHECKPOINT_FILE)`
- **Why wrong:** Windows `open(...).close()` returns before the OS has flushed pages to the disk cache. If the daemon crashes or the box reboots between `close()` and flush — which is exactly what happened to produce the current `{\r\n  "date": "2026-04-19",\r\n  "captured_games"` fragment — `os.replace` renames a half-written temp file on top of the real one.
- **Suggested fix:** Inside the `with` block, `f.flush(); os.fsync(f.fileno())` before `os.replace`. Same fix applies to every "tmp + replace" site.

### C-3 · Same no-`fsync` pattern on `discord_posted.json` (three copies)
- **Files:** `engine/morning_preview.py` lines 94-115 (`_save_guard`), `engine/weekly_recap.py` lines 342-363 (`_save_guard`), and the equivalent writer inside `engine/grade_picks.py` (see that module's guard helpers).
- **Now:** `tempfile.mkstemp → json.dump → os.replace` with no flush/fsync.
- **Why wrong:** `data/discord_posted.json` on disk right now ends `"preview:2026-04-19": true,\r\n` — no closing `}` — which means a writer closed the file with the data still in user-space buffers. Any reader hitting `json.loads` gets a `JSONDecodeError` and the guard silently resets to `{}`, re-posting every Discord embed for the day.
- **Suggested fix:** Same as C-2. Also harden `_load_guard` to log-and-preserve the broken file (move it to `.corrupt.<ts>`) instead of silently returning `{}`.

### C-4 · Three guard writers share one file with no cross-process locking
- **Files:** `engine/morning_preview.py`, `engine/weekly_recap.py`, `engine/grade_picks.py`, `engine/run_picks.py` all write to `~/Documents/JonnyParlay/data/discord_posted.json` through their own `_save_guard`.
- **Now:** Each writer does its own tmp-replace with zero coordination. A recap and a preview running at the same second can clobber each other.
- **Why wrong:** The runs are not serialized. Windows Task Scheduler fires `grade_picks.py` while `capture_clv.py` is live and while a manual `run_picks.py` is mid-run; a `@everyone` ping that should have been suppressed by the guard can fire twice.
- **Suggested fix:** Centralize guard I/O in one helper module, take a `filelock.FileLock("discord_posted.json.lock")` around every read-modify-write, fsync, done.

### C-5 · Hardcoded Odds API key in three files
- **Files:** `engine/run_picks.py` line 71, `engine/capture_clv.py` line 57, and implicitly through CLAUDE.md.
- **Now:** `ODDS_API_KEY = "adb07e9742307895c8d7f14264f52aee"` baked into source.
- **Why wrong:** (a) a leak in one file leaks in both, (b) rotating the key requires editing source and re-syncing root↔engine, (c) the key is also checked into whatever git history this repo has. The same API key is in `marketing/` / `docs/` if those folders exist.
- **Suggested fix:** Read from `os.getenv("ODDS_API_KEY")` with a fail-fast error when unset. Keep a fallback of `""` for tests, never for prod.

### C-6 · Hardcoded Discord webhook URLs in every poster
- **Files:**
  - `engine/morning_preview.py` line 34 — `DISCORD_ANNOUNCE_WEBHOOK`
  - `engine/weekly_recap.py` line 40 — same announce webhook
  - `engine/results_graphic.py` — `DISCORD_RECAP_WEBHOOK`
  - `post_nrfi_bonus.py` line 11 — bonus drop webhook
  - `engine/run_picks.py` and `engine/grade_picks.py` — premium card / POTD / KILLSHOT / recap webhooks (multiple)
- **Why wrong:** Rotating any one of these requires finding every occurrence. There's no inventory, so there's no guarantee that rotation covers every poster. Webhook URLs are secrets — each one is a standing `@everyone` ping right to the community.
- **Suggested fix:** One `webhooks.py` constants module that reads from env (or a local `.env` + `python-dotenv`). Replace every string literal.

### C-7 · `run_picks.py` + `engine/run_picks.py` same-size, grade_picks same-size, but `analyze_picks.py` drift
- **Files:** root `analyze_picks.py` (318 lines) vs `engine/analyze_picks.py` (371 lines).
- **Now:** root is stale. Missing `--shadow`, `--model-only`, `exclude_run_types`, `_parse_odds`/`_parse_float`, `MIN_SAMPLE_NOTE`, `odds_bucket`, `calibration_section`, and the MLB shadow log path. The Cowork instructions in CLAUDE.md reference `engine/analyze_picks.py` but `go.ps1`'s sync check (lines 128-146) only checks `run_picks.py`, `grade_picks.py`, and `capture_clv.py`. If Jono runs `python analyze_picks.py` from the root directory (which the file's own docstring shows as the canonical example) he gets the old code.
- **Suggested fix:** `copy engine\analyze_picks.py analyze_picks.py` on Windows, and extend `$syncPairs` in `go.ps1` to cover every Python file that has both a root and engine copy: `analyze_picks.py`, `clv_report.py`, `morning_preview.py`, `weekly_recap.py`, `results_graphic.py`.

### C-8 · `capture_clv.py` unbounded `capture_attempts` dict
- **File:** `engine/capture_clv.py` lines 677, 776-777, 842-843
- **Now:** The per-pick attempt counter dict is populated but never pruned. A long-lived daemon (S4U logon, 12-hour execution cap per `setup_clv_task.ps1`) grows this unboundedly across days, and the ghost-game startup eviction does not touch it.
- **Why wrong:** Memory leak in the long-running process. Also masks stuck pick rows — if a game's attempt counter sticks at 3, the daemon keeps skipping it forever without ever evicting.
- **Suggested fix:** Key by `(date, game)` and evict on date rollover, same as the checkpoint map. Alternatively, cap to last N=500 entries and evict oldest.

### C-9 · `grade_picks.py` reads `pick_log.csv` with no filelock
- **File:** `engine/grade_picks.py` around lines 1429-1431 (initial CSV read before the locked rewrite).
- **Now:** Reads the file without holding the lock, then acquires the lock, computes, and rewrites. A concurrent append from `run_picks.py` between "read" and "lock" ends up overwritten by the grade-phase rewrite.
- **Why wrong:** Classic read-modify-write race. It's the lock-ordering bug that would explain how a complete row from `run_picks.py` vanishes after a grade run.
- **Suggested fix:** Take the lock before the read. The pattern should be one `with FileLock(...)` that covers the entire read-grade-write cycle.

### C-10 · `grade_picks.py` daily-lay parlay all-loss evaluator returns `W`
- **File:** `engine/grade_picks.py` around lines 483-485
- **Now:** When every leg of a daily-lay parlay loses, the aggregator falls through to a default that resolves the parlay as `W`.
- **Why wrong:** An all-loss parlay is never a win. This silently credits a win and a payout for what should be a -0.50u loss.
- **Suggested fix:** Explicit `if all_legs_lost: return "L"` at the top of the aggregator, before any other branch.

### C-11 · `capture_clv.py` does not handle HTTP 429 from Odds API
- **File:** `engine/capture_clv.py` lines 255-261 (request helper)
- **Now:** Retries on network exceptions but treats 429 as a normal response, burning through the quota.
- **Why wrong:** Under rate-limit pressure, the daemon hammers the API, gets nothing useful, and burns the daily quota that `clv_daemon.log` already shows going to zero. The log entry `Only got 0/20 closing odds after 3 attempts — giving up` is at least partly this.
- **Suggested fix:** Check `resp.status_code == 429`; sleep `retry_after` (header) or exponential backoff; respect `x-requests-remaining` from the Odds API to brake preemptively.

---

## HIGH

### H-1 · Naive datetime comparison in guard TTL pruning
- **Files:** `engine/morning_preview.py` line 69, `engine/weekly_recap.py` line 317, and the grade_picks guard equivalent.
- **Now:** `cutoff = datetime.now(ZoneInfo("America/New_York")).replace(tzinfo=None) - timedelta(days=90)` and later `dt = datetime.strptime(p, "%Y-%m-%d")` which is naive.
- **Why wrong:** Mixing aware and naive datetimes is a footgun. The `.replace(tzinfo=None)` strips timezone info but the result is still "ET wall time" while the strptime result is ambiguous. A DST boundary inside the 90-day window can cause off-by-one-day pruning.
- **Suggested fix:** Parse the date string into an aware datetime using `ZoneInfo("America/New_York")`, or compare date-only (`datetime.date`).

### H-2 · Multiple naive `datetime.now()` inside `run_picks.py`
- **File:** `engine/run_picks.py` lines 1151, 1168, 3088, 3540, 4561, 4632, 4771, 4833
- **Now:** Uses `datetime.now()` (host local time) for operations that should be ET-anchored.
- **Why wrong:** If the Windows box ever drifts from ET (travel, time zone change, DST), these call sites silently file picks against the wrong calendar date. `run_time` fields in the ledger are host-local, not ET, even though the rest of the system treats ET as canonical.
- **Suggested fix:** Use `datetime.now(ZoneInfo("America/New_York"))` at every call site. Grep for `datetime.now()` and make this the house style.

### H-3 · `normalize_name` strips accents
- **File:** `engine/run_picks.py` `normalize_name` + `engine/grade_picks.py` `_norm` lines 746-747
- **Now:** `unicodedata.normalize("NFKD", s).encode("ascii", "ignore")` — drops every combining character.
- **Why wrong:** `Łuka Dončić` → `Luka Doncic` in one file and `Luka Doncic` in another, but any API that returns `Dončić` unmodified gets mismatched. `Nikola Jokić` similarly. The project has NBA exposure, so this is a live concern.
- **Suggested fix:** Use NFKC folding, lowercase, strip punctuation — but keep the glyph. Match on the folded form on both sides.

### H-4 · 2-letter team abbrev `LA` ambiguous
- **File:** `engine/grade_picks.py` lines 454-461
- **Now:** The grader accepts two-letter team codes; `LA` collides between the two Los Angeles teams per sport (Lakers/Clippers in NBA, Rams/Chargers in NFL, Dodgers/Angels in MLB, Kings NHL).
- **Why wrong:** A two-letter code is ambiguous. Any row that carries `LA` as its team matches the wrong game half the time.
- **Suggested fix:** Accept three-letter codes only (`LAL`, `LAC`, `LAR`, etc.). Map two-letter inputs to an error rather than a best-guess match.

### H-5 · Weekly recap `compute_pl` doesn't handle push-but-W fringes
- **File:** `engine/weekly_recap.py` lines 84-94
- **Now:** Pushes return 0 correctly, but the function has no branch for `V` (void). `grade_picks.py` uses `VOID` for canceled games.
- **Why wrong:** A VOID row is counted as P&L of 0 and will appear in the weekly xlsx with a blank result cell that still pulls a green color. Worse, `risked` in `daily_stats` excludes only `P` rows, so a VOID row distorts ROI.
- **Suggested fix:** Filter `result == "VOID"` out of `week_picks` entirely (same as you already do for ungraded rows) or add an explicit VOID branch to `compute_pl`.

### H-6 · `results_graphic.py` reads both main and manual logs for the graphic
- **File:** `engine/results_graphic.py` `_load_day_picks`
- **Now:** Union of `pick_log.csv` and `pick_log_manual.csv`, filtered by `run_type in {primary, bonus, daily_lay, manual}`.
- **Why wrong:** CLAUDE.md says manual picks never appear in Discord output. The graphic posts to `DISCORD_RECAP_WEBHOOK`, so any day with a manual pick leaks it into the public results card.
- **Suggested fix:** Drop `manual` from the run_type set for the graphic. Either filter out `pick_log_manual.csv` entirely, or only include its rows for internal reports.

### H-7 · Hardcoded weekly announce webhook + brand logo with zero fallback
- **File:** `engine/morning_preview.py` lines 34-35, `engine/weekly_recap.py` lines 40-41
- **Now:** If the Discord channel is deleted or rotated, the posters fail silently (`_webhook_post` returns `False` and prints a `⚠`).
- **Why wrong:** No alert. Jono finds out the next day when nobody mentions the card. The guard is still recorded as posted, so re-runs don't help.
- **Suggested fix:** On a failed post, do not set the guard key (already the case — good), but also raise a loud notification: a non-zero exit code plus a Windows Event Log write, plus a secondary fallback webhook.

### H-8 · `load_pick_log` in morning_preview and `load_picks` in weekly_recap do not hold the filelock
- **Files:** `engine/morning_preview.py` lines 46-51, `engine/weekly_recap.py` lines 105-117
- **Now:** Open CSV, read, close. No filelock. They run while `capture_clv.py` may be rewriting the file.
- **Why wrong:** A rewrite in progress can present a partial file to the reader. The reader doesn't notice; it builds an embed with partial data.
- **Suggested fix:** Take the same filelock as the writers for the duration of the read.

### H-9 · `run_picks.py` bonus sizing edge cases
- **File:** `engine/run_picks.py` (bonus-sizing block around line 3088 per sub-audit)
- **Now:** Bonus sizing can produce 0 or negative values under rare win_prob / edge combinations, then clamps to 0.25u. At 0.25u the pick is effectively a push if it wins once.
- **Why wrong:** The clamp hides an upstream edge miscalculation. Better to refuse to log the pick than log a 0.25u dust bet.
- **Suggested fix:** If the computed size is below `BONUS_MIN_SIZE`, drop the pick (log a warning), do not clamp and ship.

### H-10 · `capture_clv.py` SIGTERM does not release filelock
- **File:** `engine/capture_clv.py` (signal handling section)
- **Now:** Catches KeyboardInterrupt but not SIGTERM. Windows Task Scheduler stops the task with SIGTERM after its 12h limit. Filelock is held by the dying process. Lock file not cleaned up.
- **Why wrong:** Next daemon start sees the stale lock, refuses to acquire it, and the start message "another instance detected" is misleading — there is no other instance.
- **Suggested fix:** Register a signal handler for SIGTERM and SIGINT that releases the lock before exit. Alternatively, use `filelock.FileLock(..., thread_local=False)` with a `try/finally` around the whole `main`.

### H-11 · Context columns unconditionally appended
- **File:** `engine/run_picks.py` (pick-logging block)
- **Now:** Every logged row has `context_verdict, context_reason, context_score` fields written, even when `--context` is not enabled (CLAUDE.md default). They are blank strings, which is fine, but the code path writes them through the same CSV writer call as if the context system were live.
- **Why wrong:** When the context system is re-enabled later, a logging bug on the context side will silently poison the ledger instead of failing loudly. Also makes schema migration hard — there's no way to tell "context disabled, blank by default" from "context enabled, neutral verdict, blank reason".
- **Suggested fix:** Either write `"disabled"` in `context_verdict` when `--context` is off, or gate the three columns behind the `--context` flag and fall back to a shorter row on disabled runs (with a schema versioning bump).

### H-12 · `analyze_picks.py` (root) has no `--shadow` flag
- **File:** root `analyze_picks.py`
- **Now:** `engine/analyze_picks.py` supports `--shadow` to include MLB. Root version does not. CLAUDE.md lists `--shadow` as a supported flag and the canonical path to the file is root-level.
- **Why wrong:** Jono runs `python analyze_picks.py --shadow --export` and gets an argparse error.
- **Suggested fix:** See C-7. Sync root from engine, and add `analyze_picks.py` to the `go.ps1` sync pair list.

### H-13 · Book name normalization chaos
- **Files:** `data/pick_log.csv`, `data/pick_log_manual.csv`, `engine/weekly_recap.py` `_BOOK_DISPLAY`, `engine/run_picks.py` CO_LEGAL_BOOKS map.
- **Now:** The log contains `hardrockbet`, `hardrock`, `hardrockbet_fl`, and `Hard Rock Bet` all referring to the same sportsbook. `Caesars` and `caesars` for the same book. `espnbet` is written as-is instead of `theScore Bet` per CLAUDE.md.
- **Why wrong:** Every downstream group-by-book analysis splits the same book into multiple groups. `analyze_picks.py` `breakdown(picks, ..., "BY BOOK")` will report `hardrock` separately from `hardrockbet`. The weekly xlsx uses `display_book` and gets it right, but CSV-based queries get it wrong.
- **Suggested fix:** Normalize at write time (lowercase, strip `_fl`/`_nj`/`_pa`, map `espnbet → theScore Bet`) and backfill existing rows with a one-shot cleanup script. Better: store the API key verbatim in the log, display-map only at presentation time — but enforce that the API key is used everywhere in the log.

### H-14 · Shadow sport leakage in main `pick_log.csv`
- **File:** `data/pick_log.csv` (the MLB NRFI row added by `post_nrfi_bonus.py` on 2026-04-19)
- **Now:** An MLB row sits in the primary ledger.
- **Why wrong:** CLAUDE.md says MLB picks go to `pick_log_mlb.csv`, not the main log; the `capture_clv.py` filter (`ENABLE_SHADOW_CLV = False`) also skips MLB in the main log, so this row will never get CLV.
- **Suggested fix:** Update `post_nrfi_bonus.py` to respect the shadow routing. Move the existing row to `pick_log_mlb.csv` or tag it so `grade_picks.py` knows to skip Discord posting.

### H-15 · Open HTTP writers in `weekly_recap.py` build full xlsx in memory
- **File:** `engine/weekly_recap.py` `build_weekly_xlsx`
- **Now:** Entire workbook materialized in `io.BytesIO`. For a year's worth of data this is fine, but if `week_picks` ever grows unchecked (a backfill or replay job) this will OOM.
- **Why wrong:** Not urgent — the weekly slice is small — but the same pattern in `build_monthly_xlsx` (if/when it exists) is a bigger risk.
- **Suggested fix:** Cap `week_picks` at a sane upper bound and emit a warning if it's hit.

---

## MEDIUM

### M-1 · `analyze_picks.py` no filelock on CSV read (concurrency)
- **Files:** root and engine `analyze_picks.py`
- **Why:** Can race with `capture_clv.py` rewrites. Most analysis runs are ad-hoc, but the engine version used in automation (for monthly reports) would hit it.
- **Fix:** Optional `--no-lock` flag; default lock the file for the duration of the read.

### M-2 · `clv_report.py` no filelock on CSV read
- **File:** `engine/clv_report.py`
- **Why:** Same as M-1.
- **Fix:** Same as M-1.

### M-3 · `morning_preview.py` guard prune uses string-slice date detection
- **File:** `engine/morning_preview.py` lines 69-84
- **Now:** Looks for `p[4] == "-" and p[7] == "-"` within colon-split key pieces.
- **Why:** Fragile. Any future guard key format change silently breaks pruning.
- **Fix:** Parse the key with an explicit regex like `^(\w+):(\d{4}-\d{2}-\d{2})$` and extract the date deterministically.

### M-4 · `_webhook_post` uses `time.sleep(float(r.json().get(...)))` without handling bad JSON
- **Files:** `engine/morning_preview.py` line 127, equivalents in `weekly_recap.py`, `results_graphic.py`
- **Now:** If Discord returns 429 with an HTML body (rare but observed during outages), `r.json()` raises and the retry loop blows up.
- **Fix:** Wrap the sleep duration parse in try/except, default to 2s.

### M-5 · `results_graphic.py` font loading fallback chain
- **File:** `engine/results_graphic.py` lines 105-118
- **Now:** Tries Windows font first, then Linux, then macOS. If all fail, uses default bitmap font — graphic becomes illegible.
- **Fix:** If no font resolves, refuse to produce the graphic (log + return None) instead of shipping an embarrassing output.

### M-6 · Unicode characters in source files
- **Files:** Various. `engine/morning_preview.py` line 208 literally contains U+2501 box drawing characters (`━━━...`).
- **Now:** Works fine today but Windows console in legacy code pages will mangle them in log output.
- **Fix:** `start_clv_daemon.bat` already sets `chcp 65001` — good. `go.ps1` does not. Set `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` early in go.ps1.

### M-7 · `go.ps1` sync check missing several files
- **File:** `go.ps1` lines 128-146
- **Now:** `$syncPairs = run_picks, grade_picks, capture_clv`
- **Why:** `analyze_picks.py` (C-7), `clv_report.py`, `morning_preview.py`, `weekly_recap.py`, `results_graphic.py` all have root copies that could drift.
- **Fix:** Add all five to `$syncPairs`.

### M-8 · `preflight.bat` does not install or verify openpyxl
- **File:** `preflight.bat`
- **Now:** Checks python, filelock, requests, pillow. Misses `openpyxl` (required by `weekly_recap.py` for the xlsx attachment).
- **Fix:** Add openpyxl to the dependency list.

### M-9 · `go.ps1` does not verify openpyxl either
- **File:** `go.ps1` line 78
- **Now:** `$depMap = @{ "filelock"="filelock"; "requests"="requests"; "PIL"="pillow" }`
- **Fix:** Add `"openpyxl"="openpyxl"`.

### M-10 · `capture_clv.py` hardcoded 20-pick-per-game closing-odds expectation
- **File:** `engine/capture_clv.py` (`Only got 0/20 closing odds after 3 attempts` message)
- **Now:** 20 is baked in. Doesn't match the actual pick count per game (1 in props most of the time).
- **Fix:** Log expected vs actual with the real pick count, not a magic number.

### M-11 · `morning_preview.py` `TIER_ORDER` missing `T1B` and `DAILY_LAY`
- **File:** `engine/morning_preview.py` line 42
- **Now:** `["KILLSHOT", "PREMIUM", "POTD", "BONUS", "T1", "T2", "T3"]`
- **Why:** `pick_log.csv` contains `T1B` and `DAILY_LAY` tiers per CLAUDE.md schema.
- **Fix:** Add `T1B` between T1 and T2, add `DAILY_LAY` at the end. Also note that `PREMIUM`/`POTD`/`BONUS` are not tiers, they're run types — this whole ordering list mixes two axes.

### M-12 · `weekly_recap.py` `GAME_LINE_STATS` missing `PARLAY` handling
- **File:** `engine/weekly_recap.py` line 43
- **Now:** PARLAY rows (daily_lay legs summary) are treated as props by `_pick_short_label` — the branch falls to the else clause, which splits a non-existent player name.
- **Fix:** Add `PARLAY` to `GAME_LINE_STATS` and give it a specific short-label format.

### M-13 · `analyze_picks.py` (engine) bucket overlap
- **File:** `engine/analyze_picks.py` `pick_score_bucket`
- **Now:** Buckets `< 3`, `3-5`, `5-8`, `8-12`, `12+`. CLAUDE.md KILLSHOT sizing references Pick Score tiers 90-100, 100-110, 110+.
- **Why:** These are radically different scales. The buckets look tuned to an older Pick Score scale (pre-0-120).
- **Fix:** Decide on the canonical Pick Score scale, document it, and align the bucket thresholds to it.

### M-14 · `grade_picks.py` accent fold inconsistency
- **File:** `engine/grade_picks.py` lines 746-747 (`_norm`)
- **Why:** See H-3. Same accent-stripping bug in a different file, doubling the pain.
- **Fix:** Share one `normalize_name` helper between `run_picks.py` and `grade_picks.py`.

### M-15 · `capture_clv.py` load_picks not locked at lines 309-316
- **File:** `engine/capture_clv.py`
- **Why:** Reads the CSV at startup and on each sweep without the lock.
- **Fix:** Lock around the read.

### M-16 · No `User-Agent` on API calls
- **File:** `engine/grade_picks.py` and `engine/capture_clv.py` `requests.get` sites
- **Why:** Some stats providers (ESPN, NBA.com) return 403 for requests with the default python-requests UA. The `post_nrfi_bonus.py` script already sets a Mozilla UA for exactly this reason against Cloudflare.
- **Fix:** Set a `"PicksByJonny/1.0"` User-Agent globally.

### M-17 · `weekly_recap.py` `now_str` uses `%I` without `%p` consistency check on Windows
- **File:** `engine/weekly_recap.py` line 233
- **Now:** `strftime("%I:%M %p ET")` — on Windows, `%I` returns a zero-padded 12-hour. That's fine, but the rest of the codebase uses `dt.day` (no leading zero) to explicitly avoid `%d`. Inconsistent.
- **Fix:** Decide a house style. If avoiding zero padding, use `str(dt.hour % 12 or 12)`. Otherwise accept `%I` as fine and document it.

### M-18 · `go.ps1` waits 15 min for SaberSim CSV without a hard exit code
- **File:** `go.ps1` lines 286-290
- **Now:** Timeout prints a warning and `break`s out of the wait loop. Script continues.
- **Why:** If Jono walks away for 16 minutes, the engine runs with whatever partial set of CSVs it has.
- **Fix:** Exit non-zero on timeout; make the user re-run deliberately.

### M-19 · `post_nrfi_bonus.py` writes directly to `data/pick_log.csv` with no filelock
- **File:** `post_nrfi_bonus.py` lines 72-78
- **Why:** Bypasses every guard and lock. Runs while `capture_clv.py` may be rewriting the same file.
- **Fix:** Use filelock, or refactor the bonus post into a mode of `run_picks.py` (`--log-manual` already exists).

### M-20 · `post_nrfi_bonus.py` hardcodes schema column order inline
- **File:** `post_nrfi_bonus.py` lines 53-58
- **Why:** Duplicates the 27-column header. If `pick_log.csv` schema evolves, this file silently misaligns.
- **Fix:** Import `HEADER` from `run_picks.py` (or a shared `schema.py`).

### M-21 · `test_context.py` runs against live production from Python path
- **File:** `test_context.py` line 2
- **Now:** `sys.path.insert(0, 'engine')` and imports from `run_picks`. No mock, no dry-run flag.
- **Why:** Executes real API calls with real Anthropic credentials against real game context. Racks up spend on every `python test_context.py` invocation.
- **Fix:** Add a `--mock` flag and don't hit the Anthropic API by default. Stub `run_pregame_scan` / `run_context_check` with canned responses.

### M-22 · `calendar.month_name[dt.month]` locale-sensitive
- **File:** `engine/weekly_recap.py` line 292
- **Why:** On a non-en-US Windows install this returns localized month names (e.g. "April" → "Avril") which look wrong in a public Discord post.
- **Fix:** Hardcode an English month name array.

### M-23 · `grade_picks.py` VOID idempotency
- **File:** `engine/grade_picks.py` (grade path for canceled games)
- **Now:** Grading a VOID row again on a re-run can flip it back to blank (ungraded) under some branches.
- **Fix:** Treat VOID as a terminal state same as W/L.

### M-24 · No log rotation on `data/clv_daemon.log`
- **File:** The file itself.
- **Why:** The daemon appends forever. Logs grow unbounded. The log file reads today are fine but a year from now they'll be huge.
- **Fix:** `RotatingFileHandler` in the daemon's Python code, or a scheduled task that rotates weekly.

### M-25 · No log rotation on `data/jonnyparlay.log`
- Same as M-24.

### M-26 · `clv_report.py` relative paths vs. other tools' absolute paths
- **File:** `engine/clv_report.py` uses `Path(__file__).resolve().parent`
- **Why:** Works from Cowork and from Windows. But it's inconsistent with the hardcoded `~/Documents/JonnyParlay/` pattern used everywhere else. A `python clv_report.py` invoked from the root directory on Windows resolves to `engine/../data/pick_log.csv` — which is fine — but any move of the engine folder breaks it.
- **Fix:** Pick one path strategy and enforce it. The `Path(__file__).resolve().parent / "data"` approach is the more portable one; propagate it across the codebase, including the Cowork symlink workaround in CLAUDE.md.

### M-27 · `engine/run_picks.py` hardcoded ~4700-line claim in CLAUDE.md
- **File:** CLAUDE.md vs. actual file
- **Now:** CLAUDE.md says `~4700 lines`. Actual is 4980.
- **Fix:** Update CLAUDE.md or stop citing a line count.

### M-28 · Many `print` calls, no `logging` module
- **All engine files.**
- **Why:** Print goes to stdout and is captured by the bat file's `>> "%LOG%" 2>&1` redirection. But you lose levels (INFO vs WARNING), timestamps on every line, and the ability to silence debug output in production.
- **Fix:** Migrate to `logging` with a consistent format. Not urgent, but the next debugging session will be easier.

---

## LOW

### L-1 · Mixed emoji styles in Discord embeds
- `morning_preview.py` uses `🎯`, `🏒`, `🏀`, `🏈`, `⚾`; `weekly_recap.py` uses `📅`, `✅`, `❌`, `➖`, `🏆`, `💀`.
- Consistency.

### L-2 · `morning_preview.py` prints `⏭️` emoji in log (line 240)
- Windows console (non-UTF-8) mangles it. `chcp 65001` helps but not every caller sets it.
- Replace with an ASCII string in console output.

### L-3 · `weekly_recap.py` `_pick_short_label` duplicates logic from `analyze_picks.py`
- Two different ways to short-label a pick.
- Factor out.

### L-4 · Commented-out ghost code in `engine/run_picks.py`
- Per sub-audit. TODO: enumerate specific line numbers on next sweep.

### L-5 · `preflight.bat` uses `python --version` without pinning 3.10+
- Preflight just reports the version; doesn't fail on Python 3.9.
- Add a version gate.

### L-6 · `start_clv_daemon.bat` sets `PYTHONIOENCODING=utf-8` but `go.ps1` doesn't
- Minor. Only matters under error paths.
- Set it in go.ps1's startup block.

### L-7 · `morning_preview.py` footer says `edge > everything` twice in the codebase
- Brand tagline is duplicated. Fine today, potential drift if the brand changes.
- Centralize `BRAND_TAGLINE = "edge > everything"`.

### L-8 · `capture_clv.py` no graceful quota-exhausted stop
- When `x-requests-remaining == 0`, the daemon keeps polling until it hits 429.
- Stop polling until tomorrow when quota hits 0.

### L-9 · `post_nrfi_bonus.py` defaults `game` to long team names but `team` to "TOR@ARI"
- Inconsistent — everywhere else `team` is the single team name.
- Normalize.

### L-10 · `test_context.py` has no shebang, no docstring, no error handling
- 33-line script with `print` debug output.
- Add a shebang, a `if __name__ == "__main__":` guard, argparse for `--mock`.

### L-11 · `results_graphic.py` no retry on file upload `5xx`
- Actually it does — 3 attempts with backoff (same pattern as `_webhook_post`). Good.
- (non-issue, keeping line as confirmation)

### L-12 · `weekly_recap.py` `--test` flag suppresses @everyone but still writes guard
- Actually, on line 432-435 guard is only written if `not suppress_ping`. Good.
- (non-issue, keeping line as confirmation)

### L-13 · `preflight.bat` checks for `data\pick_log.csv.lock` but not `clv_daemon.lock`, `discord_posted.json.lock`
- Stale lockfile cleanup is incomplete.
- Add all three.

### L-14 · `go.ps1` uses Copy-Item to auto-sync root from engine
- Good sync direction per CLAUDE.md — engine is source of truth. No fix.

### L-15 · `morning_preview.py` says "picks locked in" in description
- Jono's brand is "edge > everything". "Locked in" is on-brand but subtle drift from the canonical tagline.
- Non-issue, keeping for audit trail.

### L-16 · `compute_pl` rounds to 4 decimals then 2 for display
- `compute_pl` returns `round(... , 4)` then `daily_stats` rounds to 2. Double rounding is fine for 2 decimals but smells.
- Trust the 2-decimal boundary, drop the inner round.

---

## Cross-file / architectural notes

1. **Source of truth is `engine/` — but auto-sync only runs during `go.ps1`.** Running `run_picks.py` directly on Windows (without `go.bat`) skips the sync check, which is how drift happens. Move the sync check into the head of each Python file (compare `__file__` against its counterpart, warn on mismatch) rather than relying on the launcher.

2. **Three different guard-file save paths reimplement the same tmp-replace logic.** Consolidate into one helper: `atomic_write_json(path, data)` in a shared `io_utils.py`. Fix fsync once.

3. **Five different "load pick log" functions** exist across `analyze_picks.py`, `clv_report.py`, `morning_preview.py`, `weekly_recap.py`, `results_graphic.py`. They all accept subtly different filter combinations. Consolidate into one `load_picks(paths=[...], run_types={...}, date_range=(..), graded_only=bool, lock=True)`.

4. **Two canonical paths for the data directory** — `~/Documents/JonnyParlay/data/` (absolute) vs `Path(__file__).resolve().parent / "data"` (relative). Pick one. The relative one is more portable; the absolute one is the CLAUDE.md contract. The Cowork symlink workaround in CLAUDE.md already creates friction here — doing it via relative paths makes the symlink unnecessary.

5. **Schema versioning.** `pick_log.csv` has 27 columns, `pick_log_manual.csv` has 27, `pick_log_mlb.csv` has 27 — per `post_nrfi_bonus.py`'s HEADER constant. But this contract is enforced nowhere. Add a `schema_version` metadata row at the top of each CSV and fail-fast on mismatch. Alternatively, migrate to a one-row-per-bet SQLite DB. See M-28 for the long-term arc.

6. **Webhook inventory is not centralized.** There are at least 5 live webhooks referenced in code: announce, premium, POTD, KILLSHOT, recap, bonus. Rotation of any one requires `grep -rn "discord.com/api/webhooks" .` every time. Centralize.

7. **CLAUDE.md says MLB is in SHADOW_SPORTS** but the MLB NRFI post in `post_nrfi_bonus.py` writes to the main `pick_log.csv`. Either MLB is shadow or it isn't. Pick a lane and enforce it programmatically (don't let a human decide per-post).

8. **Two different "now()" idioms throughout the codebase** — `datetime.now(ZoneInfo("America/New_York"))` in 80% of files, naive `datetime.now()` in `run_picks.py`. Grep every `datetime.now()` and fix.

---

## Questions to resolve before any fix goes in

1. Is MLB going live this week or staying shadow? If going live, H-14 + the `ENABLE_SHADOW_CLV` flag both need to flip together.
2. Are the weekly_recap `compute_pl`'s VOID semantics tested? H-5 is low-probability but bites once during a canceled-game week.
3. Is there a staging Discord server? Every webhook rotation suggestion above assumes testing in a non-production channel.
4. Was `clv_checkpoint.json` truncation discovered today or before? The file is visibly corrupt right now — has the daemon been running with an empty checkpoint for days?

---

## Order-of-operations recommendation

If I were fixing this in one sitting, the order would be:

1. Install `filelock` on the Windows box (C-1)
2. Add `f.flush(); os.fsync(f.fileno())` before every `os.replace` (C-2, C-3)
3. Repair `data/clv_checkpoint.json` and `data/discord_posted.json` by hand (see PICK_LOG_AUDIT.md for the byte-level state)
4. Sync root `analyze_picks.py` from `engine/analyze_picks.py` (C-7)
5. Fix `grade_picks.py` daily-lay all-loss branch (C-10)
6. Rotate the hardcoded API key and webhooks into env vars (C-5, C-6)
7. Everything else in priority order.

End of Apr 19 audit.

---

## SUPPLEMENTAL AUDIT — Sections 61-69 (Apr 24 2026)

**Focus:** SGP builder, longshot parlay, gameline run_type, pick_log v3 schema migration, KILLSHOT v2 rules, new webhook secrets, file sync verification.

### CRITICAL

**SEC61-1 · Undefined variable in `_log_longshot()` causes NameError**
- **File:** `engine/run_picks.py:3713`
- **Now:** `header = reader.fieldnames or list(HEADER)`
- **Issue:** `HEADER` is undefined in function scope. CANONICAL_HEADER is imported at module level (line 126) but this function references undefined `HEADER`, causing `NameError` at runtime when CSV fieldnames are missing (edge case but blocks longshot logging).
- **Fix:** Change to `header = reader.fieldnames or list(CANONICAL_HEADER)`
- **Impact:** CRITICAL — blocks longshot feature if pick_log.csv header ever becomes empty

### HIGH

**SEC61-2 · Bare except clause swallows all exceptions**
- **File:** `engine/run_picks.py:4778-4779`
- **Now:** `except: continue` in CSV collector loop
- **Issue:** Catches KeyboardInterrupt and SystemExit, preventing graceful shutdown
- **Fix:** Change to `except (IOError, OSError, UnicodeDecodeError): continue`

**SEC62-1 · Missing Discord guard for SGP posts**
- **File:** `engine/sgp_builder.py:post_sgp()` (called from run_picks.py:5424)
- **Now:** Posts SGP without checking `discord_posted.json` guard
- **Issue:** Violates audit category 10. Will double-post if `post_sgp()` called twice same day. All other parlay types (bonus, daily_lay, longshot) check guard.
- **Fix:** Add guard key before posting: `guard_key = f"sgp:{today}"`; check and update guard

**SEC65-1 · Grading dispatch missing explicit handler for gameline run_type**
- **File:** `engine/grade_picks.py:1831-1840`
- **Now:** Dispatch logic: `if run_type in (longshot, sgp) → parlay`, `elif run_type == daily_lay → daily_lay`, `elif stat in GAME_LINE_STATS → game_line`, `else → prop`
- **Issue:** If run_type="gameline" but stat not in GAME_LINE_STATS (typo), falls to `else` and tries `grade_prop()`, which fails for spreads/MLs. No explicit gameline handler.
- **Fix:** Add `elif run_type == "gameline"` before the stat check

### MEDIUM

**SEC62-2 · `grade_parlay_legs()` doesn't validate JSON structure**
- **File:** `engine/grade_picks.py:625-678`
- **Now:** Parses legs JSON and grades each leg without validating required fields
- **Issue:** No check that each leg has (player, direction, line, stat, sport). Malformed legs fail silently or produce wrong grades.
- **Fix:** Validate before grading: `if not all(leg.get(k) for k in ["player","direction","line","stat","sport"]): return None`

**SEC68-1 · File sync — root copies may diverge**
- **Files:** `engine/run_picks.py` vs `run_picks.py` (and grade_picks.py, sgp_builder.py)
- **Issue:** Manual `cp engine/X.py X.py` is error-prone. Critical bugs could exist in only one copy (see SEC61-1).
- **Fix:** Add pre-commit hook or startup check to verify engine/ ↔ root byte-for-byte parity. Currently no automation.

**SEC62-3 · Schema field count mismatch risk**
- **Now:** `CANONICAL_HEADER` in `pick_log_schema.py:41` has 28 fields for v3. `pick_log.csv` verified to have 28 fields. All writers should produce 28.
- **Issue:** No assertion at writer time that row has exactly 28 fields before append.
- **Fix:** Add: `assert len(row) == 28, f"Row has {len(row)} fields, expected 28"`

### LOW

**SEC61-3 · KILLSHOT `_player_matches()` substring matching too loose**
- **File:** `engine/run_picks.py:4099`
- **Now:** Allows `tok in full_lower` substring match; "son" matches "Anderson"
- **Issue:** Manual --killshot overrides could match unintended players
- **Fix:** Require word-boundary match

**SEC63-1 · SGP builder missing save parameter**
- **File:** `engine/sgp_builder.py`
- **Status:** PASS — `run_sgp_builder()` signature has `save=True` parameter (line 697), `post_sgp()` has `save=True` (line 628), correctly passed from run_picks.py:5429. No issue.

### Constants Verification (Section 17)

All KILLSHOT v2 constants match CLAUDE.md:
- KILLSHOT_SCORE_FLOOR = 90.0 (line 175) ✓
- KILLSHOT_TIER_REQUIRED = "T1" strict (line 176) ✓
- KILLSHOT_WIN_PROB_FLOOR = 0.65 (line 177) ✓
- KILLSHOT_ODDS_MIN = -200, KILLSHOT_ODDS_MAX = 110 (lines 178-179) ✓
- KILLSHOT_STAT_ALLOW = {PTS, REB, AST, SOG, 3PM} (line 180) ✓
- KILLSHOT_WEEKLY_CAP = 2 (line 183) ✓
- KILLSHOT_SIZE_BASE = 3.0, KILLSHOT_SIZE_BUMP = 4.0 (lines 185-186) ✓

**All constants verified. No drift.**

### Schema Integrity (Sections 62, 69)

- pick_log.csv header: 28 columns (correct for v3) ✓
- Column order: matches CANONICAL_HEADER ✓
- Sample rows (lines 2-5): all 28 fields present ✓
- SCHEMA_VERSION: correctly set to 3 in pick_log_schema.py:39 ✓
- Legs column (v3): present at position 28, blank for non-parlay rows ✓

### Open Questions

1. **Does CLV daemon skip SGP/longshot rows?** Audit section 63 says SGP has no individual closing line. Verify `capture_clv.py` skips run_type in (sgp, longshot).
2. **Is legs JSON format validated before grading?** `_legs_json()` called in run_picks.py but logic not examined. Verify it produces valid JSON.
3. **Do parlay VOIDs propagate?** If leg is VOID, should whole parlay be VOID? Current code treats VOID like "L". Confirm business logic.

### Recommended Fix Priority

**P0 (deploy before longshot feature):**
1. SEC61-1: Fix undefined HEADER → CANONICAL_HEADER
2. SEC61-2: Fix bare except clause
3. SEC62-1: Add SGP Discord guard

**P1 (before next session):**
4. SEC65-1: Add explicit gameline dispatcher
5. SEC62-2: Add legs JSON validation
6. SEC68-1: Verify file sync with diffs

**P2 (refactor, not urgent):**
7. SEC61-3: Restrict substring matching
8. SEC62-3: Add field-count assertion

End of Apr 24 supplemental audit.
