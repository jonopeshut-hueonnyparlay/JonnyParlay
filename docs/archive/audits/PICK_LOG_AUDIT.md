# Pick Log Audit — JonnyParlay

**Audit date:** 2026-04-19
**Files covered:** `data/pick_log.csv`, `data/pick_log_manual.csv`, `data/pick_log_mlb.csv`, `data/pick_log.backup-pre-manual-split.csv`, `data/clv_checkpoint.json`, `data/discord_posted.json`, `data/clv_daemon.log`, `data/jonnyparlay.log`.
**Schema reference:** CLAUDE.md, 27 columns.

This is the data-layer companion to `AUDIT_REPORT.md`. It focuses on what's actually in the CSVs and JSON files right now — every schema violation, truncation, leakage, and cross-log inconsistency I found on disk.

---

## Schema of record

Per CLAUDE.md and `post_nrfi_bonus.py` line 53-58, a valid row is 27 fields in this order:

```
date, run_time, run_type, sport, player, team, stat, line, direction,
proj, win_prob, edge, odds, book, tier, pick_score, size, game, mode,
result, closing_odds, clv, card_slot, is_home,
context_verdict, context_reason, context_score
```

Valid enumerations:
- `run_type` ∈ {primary, bonus, manual, daily_lay}
- `tier` ∈ {T1, T1B, T2, T3, KILLSHOT, DAILY_LAY}
- `stat` ∈ {SOG, PTS, REB, AST, 3PM, SPREAD, ML_FAV, ML_DOG, TOTAL, TEAM_TOTAL, F5_ML, F5_SPREAD, F5_TOTAL, PARLAY, NRFI, YRFI}
- `result` ∈ {W, L, P, VOID, ""} (empty = ungraded)
- `is_home` ∈ {"True", "False", ""}

Everything below is a deviation from that spec.

---

## CRITICAL

### C-1 · `data/pick_log.csv` line 40 truncated (17 of 27 fields)
- **Row:** `2026-04-19,15:14,daily_lay,,Daily Lay 3-leg,,PARLAY,,cover,,,,-121,theScore Bet,DAILY_LAY,,0.5`
- **Field count:** 17 commas present → 17 fields + 1 truncated. No trailing newline.
- **Missing columns:** `game, mode, result, closing_odds, clv, card_slot, is_home, context_verdict, context_reason, context_score`
- **Root cause:** The writer process (likely `run_picks.py` appending on 2026-04-19 at 15:14) did not complete its write. No `fsync` before file handle release combined with `filelock` being absent on the host (see AUDIT_REPORT C-1 / C-2) explains the partial write.
- **Impact:** Every downstream reader that doesn't pad missing fields will either error or silently drop the row. `grade_picks.py` in particular cannot grade a row without a `result` column, so this row will never resolve.
- **Fix:** Manually re-pad the row with 10 empty commas ending in a newline: `...,theScore Bet,DAILY_LAY,,0.5,,,,,,,,,,\n` — and commit a proper atomic writer before the next run.

### C-2 · `data/pick_log_mlb.csv` line 703 truncated (10 of 27 fields)
- **Row:** `2026-04-19,15:14,primary,MLB,Texas Rangers Team Total,TEXAS RANGERS,TEAM_TOTAL,3.5,over,3`
- **Field count:** 9 commas → 10 fields. No trailing newline.
- **Same root cause as C-1.** Both truncations happened at 15:14 on 2026-04-19 — likely the same `run_picks.py` invocation partially wrote both logs before something killed the process (Ctrl-C, disconnect, OOM, whatever).
- **Fix:** Same as C-1. Pad with 17 empty commas + newline.

### C-3 · `data/clv_checkpoint.json` truncated mid-key
- **Actual bytes on disk:** `{\r\n  "date": "2026-04-19",\r\n  "captured_games"`
- **No value for `captured_games`. No closing brace.**
- **Impact:** On daemon startup, `json.loads` raises `JSONDecodeError`. The daemon's fallback is "empty checkpoint, re-scan everything" — which sounds safe but causes it to double-count API requests against every game it already captured, burning quota (see `clv_daemon.log` showing `Only got 0/20 closing odds after 3 attempts`).
- **Fix:** Replace with `{}` and let the daemon rebuild. Better: restore from backup if one exists.

### C-4 · `data/discord_posted.json` missing closing brace
- **Last bytes on disk:** `"preview:2026-04-19": true,\r\n` — no `}`.
- **Impact:** `_load_guard()` catches `JSONDecodeError` and returns `{}`, which means every guarded Discord post (daily recap, POTD, premium card, KILLSHOT, preview) would re-fire on next run. The `@everyone` ping would go twice.
- **Fix:** Manually append `}\n` — then repair the atomic write path so this doesn't recur. See AUDIT_REPORT C-3.

---

## HIGH

### H-1 · `data/pick_log.csv` has MLB row in main log (shadow-sport leakage)
- **Row:** the NRFI bonus posted by `post_nrfi_bonus.py` at 2026-04-19 15:xx — `sport=MLB, player=NRFI, team=TOR@ARI, stat=NRFI, line=0.5, direction=under, odds=+108, book=fanduel, tier=T2, size=0.50, run_type=bonus`.
- **Expected:** MLB is in `SHADOW_SPORTS` per CLAUDE.md. MLB picks go to `pick_log_mlb.csv`. They should never appear in the main log.
- **Why it happened:** `post_nrfi_bonus.py` line 12 hardcodes `PICK_LOG = Path(__file__).parent / "data" / "pick_log.csv"` — not shadow-aware.
- **Downstream impact:** `capture_clv.py` will skip this row (it filters shadow sports out by sport name). `grade_picks.py` will grade it. `results_graphic.py` will include it in the public card. This is a public leak of a shadow-sport pick.
- **Fix:** Move this row to `pick_log_mlb.csv`. Patch `post_nrfi_bonus.py` to route by `sport in SHADOW_SPORTS`.

### H-2 · Book name inconsistencies across rows
Row sample from `pick_log.csv`:

| row | book field | canonical display |
|-----|------------|-------------------|
| 3 | `hardrockbet` | Hard Rock Bet |
| 11 | `hardrock` | Hard Rock Bet |
| 17 | `hardrockbet_fl` | Hard Rock Bet |
| 21 | `Caesars` | Caesars |
| 24 | `caesars` | Caesars |
| 29 | `espnbet` | theScore Bet (per CLAUDE.md) |
| 32 | `theScore Bet` | theScore Bet (direct display name leaked into data) |

- **Impact:** Any `GROUP BY book` yields 3 separate groups for Hard Rock Bet, 2 for Caesars, 2 for theScore Bet. `analyze_picks.py` breakdown-by-book ROI is meaningless.
- **Root cause mix:** `run_picks.py` writes the API key (`espnbet`, `hardrockbet`, `hardrockbet_fl`) directly. Manual entries (`post_nrfi_bonus.py`, the manual log) sometimes write display names. Somewhere a writer title-cased a key.
- **Fix:**
  1. **Normalize at write time** — always write the lowercased API key, never the display name.
  2. **Strip region suffixes** (`_fl`, `_nj`, `_pa`) before writing.
  3. **One-shot backfill** — script that rewrites existing rows to the canonical key.
  4. Add a pre-save validator: if `row["book"]` is not in `CO_LEGAL_BOOKS`, refuse the write.

### H-3 · `+105` vs `105` odds formatting inconsistency
- **Locations:** `pick_log_manual.csv` uses `+105`, main log uses `105` for positive odds.
- **Impact:** `grade_picks.py` and `weekly_recap.py` use `int(float(str(odds_str).replace("+", "")))` which tolerates both — so this is a silent tolerance, not a real break. But `analyze_picks.py` `odds_num = int(row.get("odds", 0))` at root line 51 does NOT strip the `+` — so a `+105` entry crashes with `ValueError` and falls through to `odds_num = 0`. That row gets computed as zero profit.
- **Fix:** Normalize odds at write time (always sign-prefixed string, or never sign-prefixed). Either is fine; consistency matters.
  - Recommended: always sign-prefixed (`+105`, `-110`) — matches how odds are displayed in Discord.

### H-4 · `pick_log_manual.csv` has rows with blank `book`
- **Rows:** 3 of 6 rows have `book=""`.
- **Impact:** `display_book("")` returns `""`. Discord xlsx has a blank book column. `analyze_picks.py` groups blank books under key `""`.
- **Fix:** Validator: reject manual rows missing required fields (`book`, `size`, `odds`). `run_picks.py --log-manual` should prompt for every required field.

### H-5 · `run_type` can be empty string in older rows
- **Cause:** Backfilled rows pre-dating the `run_type` column addition.
- **Impact:** Most loaders treat empty string as primary (see `morning_preview.py::get_today_picks`, `weekly_recap.py::COUNTED_RUN_TYPES` includes `""`). Works today but fragile.
- **Fix:** One-shot backfill: rewrite empty `run_type` to `primary` for legacy rows. Then make `run_type` non-nullable.

### H-6 · Tier on daily_lay PARLAY rows is `DAILY_LAY`, not T1/T2/T3
- **Not a bug** — per CLAUDE.md this is intentional. Tier enum includes `DAILY_LAY`.
- **But** `morning_preview.py` TIER_ORDER (`["KILLSHOT", "PREMIUM", "POTD", "BONUS", "T1", "T2", "T3"]`) does not include `DAILY_LAY`, so these rows fall to the "unknown tier" bucket in the morning preview embed.
- **Fix:** Add `DAILY_LAY` to `TIER_ORDER`. See AUDIT_REPORT M-11.

---

## MEDIUM

### M-1 · `context_*` columns always blank
- **Observation:** Every row in `pick_log.csv` has empty `context_verdict`, `context_reason`, `context_score`.
- **Cause:** `--context` not used on any recent run (per CLAUDE.md the flag defaults off).
- **Impact:** None today, but three columns of dead weight.
- **Fix:** Either drop the columns from the default schema and reintroduce them only when `--context` is enabled, or start writing `"disabled"` / `"neutral"` so the column is meaningful.

### M-2 · `closing_odds` and `clv` columns populated unevenly
- **Observation:** Some rows from 2026-04-16 and earlier have `closing_odds` filled, `clv` filled. Rows from 2026-04-18 have neither.
- **Cause:** CLV daemon hasn't run recently enough (or ran but failed — `clv_daemon.log` shows "Only got 0/20 closing odds" failures).
- **Impact:** CLV-based reporting for recent days is incomplete.
- **Fix:** After fixing the atomic-write bugs and quota-handling, run a backfill pass to fill in missing CLV for games that are now well past their `commence_time`.

### M-3 · `is_home` column has inconsistent boolean representation
- Mostly `True`/`False` strings, some blank.
- CLAUDE.md says blank for props, `True`/`False` for SPREAD/ML/F5.
- Spot-check confirms blanks align with props and `True`/`False` align with team-based picks. OK.
- But there are a handful of rows where `is_home` is blank on an ML_DOG pick. Either the enum is not perfectly enforced or the writer skipped it.
- **Fix:** Validator on write: `is_home` must be non-blank when `stat in {SPREAD, ML_FAV, ML_DOG, F5_*}`.

### M-4 · `card_slot` column mostly blank
- **Observation:** `card_slot` appears only populated for `primary` picks that made the 5-pick premium card. Bonus/daily_lay/manual rows have blank.
- **Intent unclear:** Is `card_slot` the 1-5 position in the premium embed, or something else?
- **Fix:** Document the semantics in CLAUDE.md. If it's only relevant for primary, the column should be `NULL` (blank) for other types and validation should enforce that.

### M-5 · `mode` column mostly blank
- **Observation:** `mode` is blank in virtually every row.
- **Intent unclear:** What is `mode` supposed to carry? Could be pre-game vs live? Retired feature?
- **Fix:** If retired, drop the column. Otherwise document and populate.

### M-6 · Duplicate rows possible without schema-level constraint
- **Check:** Scanning `data/pick_log.csv` for identical `(date, player, stat, line, direction)` tuples — no exact dupes found today, but nothing in the writer prevents them. `post_nrfi_bonus.py` explicitly has no idempotency check.
- **Fix:** Before append, compute a hash of the logical key `(date, run_type, sport, player, stat, line, direction)` and skip duplicates (or error).

### M-7 · `data/pick_log.backup-pre-manual-split.csv` — 37 rows, older than main log
- **Check:** File timestamp 2026-04-18 23:54 per earlier inspection.
- **Not a bug.** This is the intended pre-split backup.
- **But:** It's not read by any loader. Should it be archived off the live data dir so it can't accidentally be opened by a tool? The `data/` dir contains only live files elsewhere.
- **Fix:** Move to `data/archive/` or rename with `.bak` suffix that every loader explicitly ignores.

### M-8 · MLB log has 702 rows vs main log's 38
- **Observation:** `pick_log_mlb.csv` is dramatically larger — 702 rows to main's 38.
- **Explanation:** MLB has been in shadow longer and has more games per day. Not a bug, but worth verifying nothing is double-writing MLB to the shadow log (e.g., `run_picks.py` doesn't accidentally write the same MLB pick twice — once as primary, once as shadow).
- **Fix:** Grep for `SHADOW_SPORTS` usage in `run_picks.py`; confirm shadow path excludes the main log write. Given C-1 / C-2 happened at the same timestamp, this is not a theoretical concern.

### M-9 · Odds format spans American and decimal across files?
- **Check:** Spot-sampled 30 rows. All American odds. No decimal odds found.
- **Not a bug today** — consistent. Keeping the line as confirmation.

### M-10 · `size` formatting: `0.50` vs `0.5`
- **Observation:** Main log has `0.50` and `0.5` both appearing for the same 0.5u size.
- **Impact:** `float()` casting handles both, so no functional break. But a sort-by-size-as-string would interleave them oddly.
- **Fix:** Normalize to `0.50` (two decimal places) at write time. Same for `1.00`, `2.00`, etc.

### M-11 · `proj` column sometimes has 4 decimals, sometimes 1
- Cosmetic.
- Normalize to 2 decimals.

### M-12 · `edge` column: decimal vs percentage
- **Observation:** All rows show `edge` as a decimal (0.2130 = 21.30%). Consistent.
- **But:** A reader who sees `0.2130` without context could read it as "21% edge" or "0.2 percent". Adding a `%` notation in the display layer would remove ambiguity. The data itself is fine.

### M-13 · `pick_log.csv` has no schema-version metadata
- **Impact:** If the schema ever changes, existing tools cannot tell which schema version a row belongs to.
- **Fix:** Either version the file via header row metadata (`# schema_version: 2`), or migrate to SQLite with a versioned table.

### M-14 · `data/jonnyparlay.log` warnings repeating
- Three identical `filelock not installed` warnings visible.
- See AUDIT_REPORT C-1.

### M-15 · `data/clv_daemon.log` tail shows pattern of failure
- **Observation:** Tail shows 164 pending captures, "Only got 0/20 closing odds after 3 attempts", "another instance holding lock".
- **Cause:** Combined effect of AUDIT_REPORT C-8 (attempt dict grows), C-11 (no 429 handling), H-10 (SIGTERM doesn't release lock).
- **Fix:** See AUDIT_REPORT fixes. In the meantime, manually delete `data/clv_daemon.lock` if the daemon is stuck.

---

## LOW

### L-1 · Team names are a mix of full names and abbrevs
- Some rows have `TEXAS RANGERS`, others have `ARI`, others have `TOR@ARI`.
- Not a functional bug since each stat has its own expected form, but inconsistent.

### L-2 · `game` column format inconsistent
- `Charlotte Hornets @ Orlando Magic` vs `Toronto Blue Jays @ Arizona Diamondbacks` vs `MIN @ UTA`.
- Pick one — prefer full team names.

### L-3 · `direction` case inconsistent
- `over` / `under` / `cover` / `OVER` all appear.
- Normalize to lowercase at write time.

### L-4 · `player` column has three different purposes
- For props: player name.
- For game lines: team name.
- For parlays: label like "Daily Lay 3-leg".
- This overloading is the existing design per CLAUDE.md. Keeping the line as a note that `player` is context-dependent.

### L-5 · `run_time` is host-local not ET
- See AUDIT_REPORT H-2. Fix at the same time.

### L-6 · `pick_log_manual.csv` trailing newline: present
- Confirmed. No truncation on this file.

### L-7 · Pick score decimal precision
- Some rows `85.0`, some `82`, some `88.55`.
- Normalize to 1 decimal.

---

## Concrete cleanup script (run once, in order)

```
# 1. Take a backup
cp data/pick_log.csv data/pick_log.backup-$(date +%Y%m%d-%H%M%S).csv

# 2. Fix line 40 of pick_log.csv — re-pad to 27 fields
# (needs manual edit: append 10 empty commas + newline to the truncated row)

# 3. Fix line 703 of pick_log_mlb.csv — re-pad to 27 fields
# (needs manual edit: append 17 empty commas + newline)

# 4. Fix clv_checkpoint.json
echo '{}' > data/clv_checkpoint.json

# 5. Fix discord_posted.json
# (needs manual edit: append closing brace)

# 6. Install filelock on Windows
pip install filelock --break-system-packages

# 7. Remove stale lockfiles
rm -f data/pick_log.csv.lock data/discord_posted.json.lock data/clv_daemon.lock

# 8. Run a backfill pass for book name normalization (after the normalization code lands)
python tools/normalize_books.py  # does not exist yet — would need to be written

# 9. Move MLB NRFI row to pick_log_mlb.csv (manual edit)

# 10. Archive the pre-split backup
mkdir -p data/archive
mv data/pick_log.backup-pre-manual-split.csv data/archive/
```

---

## Verification checklist (post-cleanup)

- [ ] `python -c "import csv; rows=list(csv.DictReader(open('data/pick_log.csv'))); print(f'{len(rows)} rows'); assert all(len(r) == 27 for r in rows), 'short rows'; print('all 27 cols OK')"` passes
- [ ] Same for `pick_log_mlb.csv` and `pick_log_manual.csv`
- [ ] `python -c "import json; print(json.load(open('data/clv_checkpoint.json')))"` does not raise
- [ ] `python -c "import json; print(json.load(open('data/discord_posted.json')))"` does not raise
- [ ] `python engine/analyze_picks.py --shadow` runs without argparse error (after C-7 sync)
- [ ] No MLB rows in `pick_log.csv` (after H-1 fix)
- [ ] `GROUP BY book` on `pick_log.csv` yields at most 18 groups (the CO_LEGAL_BOOKS list), not 20+
- [ ] `filelock` imports succeed on the Windows box (`python -c "import filelock; print(filelock.__version__)"`)

End of pick log audit.
