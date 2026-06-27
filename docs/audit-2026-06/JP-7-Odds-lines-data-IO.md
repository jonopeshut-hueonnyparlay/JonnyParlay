# AUDIT 2026-06 — JP-7 Odds/lines/data IO (JonnyParlay)

Files audited (3 read): odds_io.py, mlb_starter_fetcher.py, analyze_game_lines.py

**Findings (final, excl. refuted): C=0 H=0 M=4 I=8** | constants extracted: 18 | not-done: 5

## Findings

| ID | File:line | Sev | Status | Cat | Known | Title |
|----|-----------|-----|--------|-----|-------|-------|
| F-4 | analyze_game_lines.py:259 | M | confirmed | code |  | team_total_odds matches team abbreviation as substring of full team-name description — fails for ~half of MLB/NBA teams |
| F-5 | analyze_game_lines.py:266 | M | confirmed | code |  | team_total_odds keeps last-seen price per side, not best odds, and first book's name |
| F-6 | analyze_game_lines.py:118 | M | confirmed | completeness |  | Matchup-specific sigma scaling and per-team NB r are dead code — analyze_*() use flat league SIGMA |
| F-8 | analyze_game_lines.py:152 | M | confirmed | completeness |  | Hardcoded MLB_PROJS/NBA_PROJS are a stale fixed slate used as fallback when CSV auto-find fails |
| F-1 | analyze_game_lines.py:83 | I | refuted | statistical |  | NBA spread/ml sigma=12.5 contradicts the file's own stated margin-residual SD of 15.27 (too tight -> overconfident) |
| F-2 | analyze_game_lines.py:84 | I | refuted | statistical |  | NBA total sigma=18.5 below the stated residual SD 19.33 |
| F-3 | analyze_game_lines.py:32 | I | refuted | code |  | Hardcoded Odds API key + books string in source; diverges from odds_io's secrets_config |
| F-7 | analyze_game_lines.py:489 | I | refuted | statistical |  | F5 moneyline modeled as 2-way Normal P(margin>0), ignoring draw mass and de-vigging only 2 of 3 outcomes |
| F-10 | analyze_game_lines.py:311 | I | unverified | statistical |  | kelly_stake floors a rounded-to-zero positive Kelly to 0.25u |
| F-12 | analyze_game_lines.py:781 | I | unverified | code |  | 'MLB DAILY CAP (8.0u)' warning printed for any sport including NBA |
| F-13 | analyze_game_lines.py:35 | I | unverified | code |  | BOOKS_STR includes retired 'pointsbetus' book |
| F-15 | analyze_game_lines.py:82 | I | unverified | statistical |  | SIGMA['MLB']['ml']=4.75 is unused — MLB ML uses NB direct sum |
| F-16 | analyze_game_lines.py:873 | I | unverified | code |  | f-string with nested same-quote (size formatting) requires Python >=3.12 |
| F-17 | analyze_game_lines.py:949 | I | unverified | completeness |  | No analyze_nhl despite NHL SIGMA and NHL legend line |
| F-14 | odds_io.py:353 | I | refuted | completeness |  | NRFI (totals_1st_1_innings) fetched and stored under _nrfi key but no extractor consumes it here |
| F-18 | odds_io.py:229 | I | unverified | code |  | Cache day key uses ET while today's-game window uses MT (Denver) |
| F-9 | mlb_starter_fetcher.py:52 | I | refuted | code |  | Athletics abbrev mismatch: starter fetcher emits OAK, analyze_game_lines uses ATH |
| F-11 | mlb_starter_fetcher.py:71 | I | unverified | completeness |  | _norm_name is dead code |

## C/H/M detail

### [M] F-4 — team_total_odds matches team abbreviation as substring of full team-name description — fails for ~half of MLB/NBA teams
`C:/Dev/JonnyParlay/analyze_game_lines.py:259-277` · code · status=confirmed

**Evidence:** desc = out.get('description','').upper() is the full team name (odds_io.extract_team_totals confirms description is the team NAME, storing full names and filtering 'Over'/'Under'). The check `if abbr not in desc` (line 270) only succeeds when the abbrev is a literal substring of the city: 'PIT' in 'PITTSBURGH' works, but 'NYY' not in 'NEW YORK YANKEES', 'LAD' not in 'LOS ANGELES DODGERS', 'SD'/'SF'/'KC'/'TB'/'CWS' all miss. Team-total (TT) edges are silently dropped for those teams in analyze_mlb/analyze_nba.

**Recommendation:** Map description full-name -> abbrev via MLB_NAME_MAP/NBA_NAME_MAP (as find_outcome does) instead of substring matching.

**Verifier (confirmed):** Verified against C:/Dev/JonnyParlay/analyze_game_lines.py:259-277. team_total_odds matches via `if abbr not in desc` where desc=out['description'].upper() and abbr is the team abbreviation from [away_abbr, home_abbr]. The team_totals market's `description` field holds the FULL team NAME, not the abbreviation — independently corroborated by the sibling engine/capture_clv.py:976-1008, which comments 'team_totals outcomes: name=Over/Under, description=team name' and deliberately word-matches the fu

### [M] F-5 — team_total_odds keeps last-seen price per side, not best odds, and first book's name
`C:/Dev/JonnyParlay/analyze_game_lines.py:266-276` · code · status=confirmed

**Evidence:** `result[abbr][f'{side}_odds'] = out['price']` (line 274) overwrites with each successive bookmaker's price, so the LAST book's price wins rather than the best (highest) odds; the book label is fixed to the first book seen (line 273). odds_io.extract_team_totals correctly keeps best odds per direction. TT model edges here are computed against suboptimal/last prices.

**Recommendation:** Select best odds per side and record the corresponding book, mirroring extract_team_totals.

**Verifier (confirmed):** Code confirmed verbatim: in team_total_odds (C:/Dev/JonnyParlay/analyze_game_lines.py:259-277), line 274 unconditionally overwrites result[abbr][f'{side}_odds'] each bookmaker iteration, so the LAST book's price per side wins (not best/highest), and lines 272-273 fix the 'book' label to the FIRST book seen. Over and under odds can even come from different last-seen books while the recorded book matches neither. Reachable in production: per CLAUDE.md, game lines were decoupled from run_picks on 2

### [M] F-6 — Matchup-specific sigma scaling and per-team NB r are dead code — analyze_*() use flat league SIGMA
`C:/Dev/JonnyParlay/analyze_game_lines.py:118-149` · completeness · status=confirmed

**Evidence:** get_game_sigma (118), get_game_sigma_team (140), get_mlb_team_run_r (147) and the startup load _load_team_sigmas_agl() (98/116) are defined but never called: analyze_mlb uses `sig = SIGMA['MLB']` (367), analyze_nba uses `sig = SIGMA['NBA']` (556), and mlb_tt_prob uses the global MLB_TEAM_RUN_R (342-358). The 'Plan 6 relative-variability scaler' and per-team NB dispersion are therefore never applied; every game uses league-average sigma despite the implemented per-team variance.

**Recommendation:** Either wire get_game_sigma()/get_mlb_team_run_r() into analyze_mlb/analyze_nba (and TT) or delete the dead loader and helpers.

**Verifier (confirmed):** All factual claims verified against C:/Dev/JonnyParlay/analyze_game_lines.py. (1) get_game_sigma (118), get_game_sigma_team (140), get_mlb_team_run_r (147) and the startup loader _load_team_sigmas_agl (defined 98, called 116) are defined but never invoked anywhere in the file — a full-file grep returns only their definitions; the populated dicts _TEAM_SIGMAS_AGL/_TEAM_SIGMAS_MEANSQ_AGL are read solely by the dead helpers. (2) analyze_mlb uses sig=SIGMA['MLB'] (367) -> sig['spread']/sig['total'] 

### [M] F-8 — Hardcoded MLB_PROJS/NBA_PROJS are a stale fixed slate used as fallback when CSV auto-find fails
`C:/Dev/JonnyParlay/analyze_game_lines.py:152-168` · completeness · status=confirmed

**Evidence:** MLB_PROJS (152-165) and NBA_PROJS (166-168) are a specific historical matchup slate with fixed projections. _build_projs returns {} when no CSV is found (line 736), and analyze_*() then fall back to these hardcoded maps (377/569). If the SaberSim CSV is missing/old, the script silently analyzes a stale slate against today's odds.

**Recommendation:** Fail loudly (or skip) when no fresh CSV projections are available rather than falling back to a stale hardcoded slate.

**Verifier (confirmed):** Code confirms the claim and the path is reachable in production. analyze_game_lines.py __main__ (lines 953-954) calls _build_projs("MLB")/("NBA"), which returns {} (line 736) whenever no SaberSim CSV is auto-found in Downloads within the 12h window (43200s, line 721) or the found CSV has no valid Saber Team values. With team_projs falsy, analyze_mlb (line 377) and analyze_nba (line 569) build proj_map from the hardcoded MLB_PROJS/NBA_PROJS (lines 152-168) — a specific historical matchup slate wi


## Confirmed-correct / coverage notes

- odds_io.OddsFetcher._get retry/backoff is sound: 200 returns json, 422 returns [] (no-prop event), 401 sys.exit(1) (key invalid — intentional hard stop), other statuses backoff 2**attempt then return [] (odds_io.py 205-222).
- odds_io cache write uses json.dump(default=str) and _load_cache only swallows json.JSONDecodeError (logs and re-fetches), letting real I/O errors propagate — the H10 fix is correctly scoped (lines 233-241).
- parse_csv detects sport with filename-wins-over-headers (WNBA vs NBA identical headers), aborts on empty CSV with sys.exit(1) instead of silently defaulting to NBA, and dedupes Showdown CSVs by name_key (lines 63-195). Looks correct.
- MLB TB computed as 1*1B + 2*2B + 3*3B + 4*HR (line 164) — total bases correct. HRR = H+R+RBI (line 169) correct.
- extract_player_props / extract_game_lines / extract_alt_spreads correctly strip region suffix for CO_LEGAL_BOOKS gating, skip is_decimal_leak prices, and keep best (max american) odds per direction (odds_io.py 466-570, 699-718).
- extract_team_totals two-pass design (best odds, then count books offering BOTH sides to pick the main line by book consensus, tie-break by most-negative under) is reasonable and the book_over/book_under keys are consistent between write (620-625) and read (673-674).
- mlb_tt_prob integer-line push adjustment is mathematically correct: over = P(X>k)/(1-P(X=k)), under = P(X<k)/(1-P(X=k)); half-line uses plain NB CDF (analyze_game_lines.py 342-358).
- mlb_ml_from_nb correctly splits ties 50/50 via sum of P(home=k)*(P(away<k)+0.5*P(away=k)) (lines 67-77).
- Spread/total/ML CDF signs verified correct: cover_h = 1 - normal_cdf(-sp_line, margin, sigma) = P(margin > -line); total over = 1 - cdf(tline, total, sigma); ML home = 1 - cdf(0, margin, sigma).
- mlb_starter_fetcher: 30-team ID->abbrev map is complete (108-147 + 158), doubleheaders handled via list-per-team (setdefault().append), graceful {} on network/parse error, is_confirmed uses fuzzy name_key matching. Solid except the OAK/ATH abbrev divergence (F-9).
- _write_game_line_bets uses FileLock when available, writes the canonical 29-col schema with extrasaction='ignore', and fsyncs — robust logging path; _line_from_label/_parse_label_meta correctly recover line/stat/direction from the rendered edge label.
- F5_SCALAR 0.540 is close to the 5/9=0.556 fraction of a 9-inning game (slightly lower, consistent with starters pitching the first 5) — acceptable.
- MLB total sigma 4.6 / spread 4.2 are consistent with NB-implied per-team run var (mean ~4.3, var/mu~2.26 => margin/total SD ~4.3-4.5).

## Not-Done / incomplete (this module)

| Kind | File | Detail |
|------|------|--------|
| dead-code | analyze_game_lines.py | get_game_sigma / get_game_sigma_team / get_mlb_team_run_r and _load_team_sigmas_agl()+_TEAM_SIGMAS_AGL are defined and loaded at import but never called; analyz |
| dead-code | mlb_starter_fetcher.py | _norm_name() (lines 71-83) is never called; is_confirmed uses name_key(). |
| partial-feature | analyze_game_lines.py | No analyze_nhl despite NHL entry in SIGMA and NHL mention in the closing legend; __main__ only handles MLB and NBA (lines 949-1006). |
| partial-feature | odds_io.py | totals_1st_1_innings is fetched and stored under {eid}_nrfi (line 354/396) but no extractor in odds_io consumes the _nrfi key (extract_f5_lines only handles 'f5 |
| stub | analyze_game_lines.py | MLB_PROJS/NBA_PROJS hardcoded slate is a stale fallback (lines 152-168); when no fresh SaberSim CSV is found _build_projs returns {} and analyze_*() silently fa |
