# MASTER SEVERITY TABLE — JonnyParlay (audit 2026-06-26)

Final (excl. refuted): **C=0 · H=1 · M=22 · I=83**. Refuted/downgraded findings listed in the appendix.

| ID | Module | File:line | Sev | Status | Known | Title |
|----|--------|-----------|-----|--------|-------|-------|
| JP3-01 | JP-3 | sgp_builder.py:219 | H | confirmed | Y | SGP/MLB-SGP leg win-probs bypass the Platt/temperature calibration that straight props receive |
| F-4 | JP-7 | analyze_game_lines.py:259 | M | confirmed |  | team_total_odds matches team abbreviation as substring of full team-name description — fails for ~half of MLB/NBA teams |
| F-5 | JP-7 | analyze_game_lines.py:266 | M | confirmed |  | team_total_odds keeps last-seen price per side, not best odds, and first book's name |
| F-6 | JP-7 | analyze_game_lines.py:118 | M | confirmed |  | Matchup-specific sigma scaling and per-team NB r are dead code — analyze_*() use flat league SIGMA |
| F-8 | JP-7 | analyze_game_lines.py:152 | M | confirmed |  | Hardcoded MLB_PROJS/NBA_PROJS are a stale fixed slate used as fallback when CSV auto-find fails |
| F7 | JP-6 | context_prep.py:40 | M | confirmed |  | Hardcoded ODDS_API_KEY fallback literal committed in source |
| JP10-F1 | JP-10 | calibrate_distributions.py:434 | M | confirmed |  | wnba-3pm recommends POOLED NB dispersion r, contradicting the within-player method used everywhere else |
| JP2-02 | JP-2 | calibrated.py:165 | M | confirmed | Y | Platt scaling fit on n=76 one-directional props compresses every prop win_prob into [0.308, 0.666] |
| CLV-3 | JP-4 | capture_clv.py:410 | M | confirmed |  | ±0.25 line-match filter on spreads/totals records CLV only when the line did NOT move → selection bias |
| JP-RF-1 | RE-FIND | capture_clv.py:1882 | M | confirmed |  | Partial-capture games are never STALE-marked or retired — give-up condition is unreachable |
| CLV-2 | JP-4 | clv_report.py:182 | M | confirmed | Y | avg_clv mixes vigged (pre-reform) and vig-free (post-reform) CLV and reads raw `clv` (vigged-entry biased), not clv_corr |
| F2 | JP-6 | context_research_v2.py:173 | M | confirmed |  | Wind OUT/IN direction sets appear inverted vs meteorological 'direction-from' convention |
| F9 | JP-6 | context_research_v2.py:1463 | M | confirmed |  | Umpire factor is effectively a stub — JSON source unverified and HTML fallback always returns None |
| JP1-03 | JP-1 | evaluators.py:100 | M | confirmed |  | I6 early-season confidence penalty is inert on the SaberSim CSV path (GP never parsed) |
| JP-RF-4 | RE-FIND | evaluators.py:111 | M | confirmed |  | Early-season confidence penalty applied twice — once to prob, again to edge |
| JP5-02 | JP-5 | grade_picks.py:1941 | M | confirmed |  | Lost-update race: grade_picks reads all rows under lock, releases lock during (slow) network grading, then rewrites the  |
| JP5-04 | JP-5 | grade_picks.py:1360 | M | confirmed |  | grade_prop weak fuzzy fallback grades on last-name-only when no first+last match — can settle on the wrong same-surname  |
| JP5-06 | JP-5 | grade_picks.py:987 | M | confirmed |  | _resolve_pick_is_home legacy fallback accepts len>=2 token substring match — common letter pairs false-positive on the w |
| JP5-07 | JP-5 | grade_picks.py:1493 | M | confirmed |  | compute_pl / daily_stats match result with exact =="W"/"L"/"P" (no strip/upper), contradicting the module's own TERMINAL |
| JP-RF-6 | RE-FIND | grade_picks.py:1360 | M | confirmed |  | Last-name-only fuzzy player match can settle the wrong player's stat |
| JP9-01 | JP-9 | health_check.py:252 | M | confirmed |  | EdgeModel constant checks are bare substring matches, not bound to the constant name/value |
| JP3-03 | JP-3 | mlb_sgp_builder.py:390 | M | confirmed |  | MLB _size_mlb_sgp omits the cohesion>=0.55 gate that NBA size_sgp enforces, despite docstring claiming parity |
| JP3-05 | JP-3 | sgp_builder.py:591 | M | confirmed |  | NBA candidate dropped when its global-best book is not allowed, even if an allowed book also offers the leg |
| F6 | JP-6 | context_prep.py:66 | I | confirmed |  | context_prep prompt template emits 'conflicts' verdict and '>60%' aggregation — schema-incompatible with canonical 'fade |
| JP12-04 | JP-12 | analyze_picks.py:116 | I | confirmed |  | Calibration display dilutes predicted WP by averaging over picks with win_prob==0 |
| JP10-F5 | JP-10 | calibrate_winprob.py:174 | I | confirmed |  | Win-prob CV is non-time-ordered standard k-fold (future leakage) yet labelled 'use for go/no-go' |
| F1 | JP-6 | context_research_v2.py:1226 | I | confirmed |  | MLB injury verdicts are marked data_quality='stale' and then force-overridden to neutral — the weight-3 MLB injury signa |
| F8 | JP-6 | context_research_v2.py:1322 | I | confirmed |  | FIP formula omits HBP term and uses constant 3.10 (low vs ~3.15-3.20) |
| JP9-02 | JP-9 | discord_post.py:837 | I | confirmed |  | 12.0-unit daily exposure cap is a hardcoded magic literal duplicated across files (drift risk on a live sizing gate) |
| JP9-04 | JP-9 | discord_post.py:270 | I | confirmed | Y | ReadTimeout-after-delivery plus guard release can re-post premium card with @everyone on the next run |
| JP1-01 | JP-1 | evaluators.py:100 | I | confirmed |  | Confidence (conf) is applied twice to the prop edge (probability shrink + edge multiply) |
| JP5-08 | JP-5 | grade_picks.py:1175 | I | confirmed |  | NRFI/YRFI can only return W or L — a postponed/rained-out game (inning 1 never completes) stays ungraded forever, no VOI |
| JP-RF-5 | RE-FIND | grade_picks.py:876 | I | confirmed |  | Voided/pushed parlay legs drop but P&L is still computed at the original full-parlay odds |
| JP3-08 | JP-3 | mlb_sgp_builder.py:560 | I | confirmed |  | MLB candidate filter has no upper odds bound (NBA rejects odds > -115); plus-money / low-juice legs can enter MLB SGPs |
| JP8-2 | JP-8 | pick_log_schema.py:628 | I | confirmed |  | Module invariant block asserts v1-v4 column subsets but omits _V5_COLUMNS |
| JP8-1 | JP-8 | pick_log_writers.py:266 | I | confirmed |  | log_picks positional writer omits clv_corrected -> 29-field rows under a 30-col header (schema drift on the live primary |
| JP1-04 | JP-1 | run_picks.py:1314 | I | confirmed |  | _ks_sport_cap and the 12.0 daily cap are hardcoded duplicates of rules.py SPORT_UNIT_CAP / total cap (lockstep drift ris |
| JP1-05 | JP-1 | run_picks.py:1570 | I | confirmed |  | --repost rebuild does float()/int() on CSV cells that can be empty strings -> ValueError |
| JP10-F7 | JP-10 | sabersim_backtest.py:405 | I | confirmed |  | Unicode glyphs in stdout can crash under cp1252-redirected output |
| JP3-04 | JP-3 | sgp_builder.py:423 | I | confirmed |  | NBA SGP _api_get has no 429/Retry-After handling (MLB has one); a transient rate-limit drops the entire NBA SGP slate |
| JP3-07 | JP-3 | sgp_builder.py:660 | I | confirmed |  | NBA _score_sgp runs full 1000-sample MC copula for every searched combo; module header claims the fast equicorr approx i |
| JP11-1 | JP-11 | diag_h6_pool.py:20 | I | confirmed |  | 6/9 tools ImportError in this repo — they import EdgeModel-only modules (projections_db / nba_projector / generate_proje |
| JP5-05 | JP-5 | post_nrfi_bonus.py:73 | I | confirmed |  | post_nrfi_bonus posts a hardcoded NRFI pick with fabricated win_prob/edge/proj when run with no args — not derived from  |
| F-10 | JP-7 | analyze_game_lines.py:311 | I | unverified |  | kelly_stake floors a rounded-to-zero positive Kelly to 0.25u |
| F-12 | JP-7 | analyze_game_lines.py:781 | I | unverified |  | 'MLB DAILY CAP (8.0u)' warning printed for any sport including NBA |
| F-13 | JP-7 | analyze_game_lines.py:35 | I | unverified |  | BOOKS_STR includes retired 'pointsbetus' book |
| F-15 | JP-7 | analyze_game_lines.py:82 | I | unverified |  | SIGMA['MLB']['ml']=4.75 is unused — MLB ML uses NB direct sum |
| F-16 | JP-7 | analyze_game_lines.py:873 | I | unverified |  | f-string with nested same-quote (size formatting) requires Python >=3.12 |
| F-17 | JP-7 | analyze_game_lines.py:949 | I | unverified |  | No analyze_nhl despite NHL SIGMA and NHL legend line |
| JP12-05 | JP-12 | analyze_picks.py:216 | I | unverified |  | streak_analysis prints 'Current: 0None' when the set is all pushes |
| JP12-06 | JP-12 | analyze_picks.py:100 | I | unverified |  | American-odds payout math and ROI denominator are correct |
| JP10-F13 | JP-10 | calibrate_distributions.py:105 | I | unverified |  | Crude integer-index percentile helpers (acceptable for advisory output) |
| JP10-F6 | JP-10 | calibrate_platt.py:38 | I | unverified | Y | Platt fit is logit-space but the live run_picks formula is raw-probability space (KNOWN/superseded) |
| JP-RF-9 | RE-FIND | calibrate_platt.py:38 | I | unverified | Y | calibrate_platt fits in logit-space but the live run_picks formula is raw-probability space (KNOWN/superseded) |
| JP-RF-8 | RE-FIND | calibrate_winprob.py:176 | I | unverified |  | 5-fold CV leaves the remainder rows out of all validation folds |
| CLV-7 | JP-4 | capture_clv.py:1206 | I | unverified |  | Game-line ML/SPREAD side resolution falls through to away on any non-'home' direction |
| CLV-8 | JP-4 | capture_clv.py:1098 | I | unverified |  | clv_corrected proxy math verified correct against the -110/-110 hold |
| F16 | JP-6 | context_research_v2.py:1266 | I | unverified |  | rlm hook is dead code — keyed branch is a bare 'pass' |
| F13 | JP-6 | context_research_v2.py:1778 | I | unverified |  | Per-factor try/except containment + quality override make the daily run crash-resistant |
| F11 | JP-6 | context_research_v2.py:1562 | I | unverified |  | Pythagorean exponents are defensible (NBA/WNBA 16.5 = Hollinger; MLB 2.0 = classic James) |
| JP9-06 | JP-9 | discord_post.py:453 | I | unverified |  | POTD failure path releases guard but does not fire the fallback alert (inconsistent with premium card) |
| JP9-07 | JP-9 | discord_post.py:121 | I | unverified |  | Guard TTL prune cutoff uses ET in discord_post fallback but UTC in the shared discord_guard module |
| JP9-09 | JP-9 | discord_post.py:307 | I | unverified |  | Dead local: `tier` computed but never used in premium/POTD embeds |
| JP10-F12 | JP-10 | empirical_analysis.py:4 | I | unverified |  | empirical_analysis.py is a frozen one-off with hardcoded absolute user paths |
| JP14-6 | JP-14 | engine_logger.py:105 | I | unverified |  | Cached get_logger call ignores a changed stream/level argument |
| JP-RF-7 | RE-FIND | evaluate_projector.py:218 | I | unverified |  | project_3pm alpha=0.65 hardcoded as a default rather than imported from EdgeModel |
| JP1-07 | JP-1 | evaluators.py:55 | I | unverified |  | evaluate_props cooldown_players parameter is never used |
| JP1-08 | JP-1 | evaluators.py:228 | I | unverified |  | evaluate_game_lines output (TOTAL/SPREAD/ML/TEAM_TOTAL) is dropped from the live card by design — math here is shadow/co |
| JP1-10 | JP-1 | evaluators.py:115 | I | unverified | Y | WNBA props calibrated with NBA+NHL Platt coefficients (known approximation) |
| JP13-07 | JP-13 | gate_check.py:39 | I | unverified |  | gate_check reads pick_log.csv without the shared pick_log lock |
| JP13-08 | JP-13 | gates.py:166 | I | unverified |  | G14 evaluated twice for WNBA 3PM (idempotent, safe) |
| JP13-09 | JP-13 | gates.py:55 | I | unverified |  | G8B fires for NHL AST-over low-line before G_NHL_AST (attribution only) |
| JP5-09 | JP-5 | grade_picks.py:1264 | I | unverified |  | GOLF_WIN intentionally returns None (manual grading) — acceptable stub, documented |
| JP5-10 | JP-5 | grade_picks.py:1476 | I | unverified |  | compute_pl American-odds payout math is correct |
| JP5-11 | JP-5 | grade_picks.py:490 | I | unverified |  | MLB derived-stat math (TB, HRR, IP->outs) is correct |
| JP5-12 | JP-5 | grade_picks.py:694 | I | unverified |  | grade_daily_lay push/loss/win fall-through invariants hold |
| JP14-8 | JP-14 | http_utils.py:67 | I | unverified |  | Retry-After clamp window [0.5, 30.0] and default 2.0 — confirmed sensible |
| JP14-10 | JP-14 | io_utils.py:42 | I | unverified |  | atomic_write_json is correct (same-dir tmp, fsync, os.replace, best-effort cleanup) |
| JP3-14 | JP-3 | killshot.py:135 | I | unverified |  | KILLSHOT weekly-cap counter fails SAFE (returns full cap on read error) |
| JP14-9 | JP-14 | log_setup.py:125 | I | unverified |  | preemptive_rotate shift logic is correct and bounded to backup_count |
| JP3-12 | JP-3 | mlb_sgp_builder.py:225 | I | unverified | Y | MLB rho 0.30 (OUTS-over x opposing-HITS-under) is an unfit structural prior, refit-gated at n=160 |
| JP14-11 | JP-14 | name_utils.py:50 | I | unverified |  | fold_name / name_key folding contract correct, suffix stripping bounded |
| JP10-F8 | JP-10 | nb_calibrate.py:27 | I | unverified |  | Dead CURRENT dict and relative DB_PATH in nb_calibrate.py |
| F-18 | JP-7 | odds_io.py:229 | I | unverified |  | Cache day key uses ET while today's-game window uses MT (Denver) |
| JP3-13 | JP-3 | parlays.py:67 | I | unverified | Y | build_safest6 ranks by hit-frequency (win_prob), not EV — intentional product decision, documented |
| JP14-7 | JP-14 | paths.py:101 | I | unverified |  | PICK_LOG_PATH from env var is not expanduser'd |
| JP8-3 | JP-8 | pick_log_schema.py:11 | I | unverified |  | Stale docstring/comment: '29-column schema' and 'Canonical schema (v4)' but module is v5/30 cols |
| JP8-9 | JP-8 | pick_log_writers.py:439 | I | unverified |  | Parlay appenders (_log_daily_lay/_log_longshot/_log_value_parlay) never write a header; a 0-byte pick_log would get head |
| JP2-10 | JP-2 | prob_core.py:113 | I | unverified |  | WNBA early-season sigma inflation also applies when sigma_override (dk_std) is supplied |
| JP2-13 | JP-2 | prob_core.py:202 | I | unverified | Y | pick_score wp_n is uncapped and unreachable above ~66 due to Platt ceiling — win_prob is structurally under-weighted |
| JP10-F9 | JP-10 | projection_accuracy.py:223 | I | unverified |  | Unused variable 'today' in rolling-trend block |
| JP2-12 | JP-2 | odds.py:59 | I | unverified |  | prob_to_american returns a float, decimal_to_american returns int — inconsistent return types |
| JP13-06 | JP-13 | rules.py:144 | I | unverified |  | Stale comment in can_add: claims score<25 / overs 40+ but constants are 15/15 |
| JP3-10 | JP-3 | sgp_builder.py:57 | I | unverified |  | IDEAL_LEG_WIN_PROB defined but never referenced (dead constant) |
| JP3-11 | JP-3 | sgp_builder.py:286 | I | unverified | Y | NBA SGP pairwise rho table is hardcoded with n_observations 'unrecorded' (self-acknowledged audit gap) |
| JP2-11 | JP-2 | sizing.py:157 | I | unverified |  | size_daily_lay hardcodes 0.25 quarter-Kelly instead of importing KELLY_FRACTION |
| JP14-4 | JP-14 | team_resolve.py:54 | I | unverified |  | n_games >= 20 stabilization gate for using team-specific sigma |
| JP13-10 | JP-13 | thresholds.py:124 | I | unverified |  | thresholds.toml override surface can mutate live sizing/gating tunables without code review |
| JP13-11 | JP-13 | thresholds.py:83 | I | unverified |  | WNBA_EV_FLOOR=0.0955 derivation verified consistent |
| JP13-12 | JP-13 | thresholds.py:87 | I | unverified |  | F5_SCALAR=0.540 is plausible vs innings-fraction benchmark |
| JP11-5 | JP-11 | calibration_dashboard.py:69 | I | unverified |  | Reliability significance uses predicted-prob Wald SE — acceptable advisory choice |
| JP11-7 | JP-11 | diag_h1_constraint_chain.py:81 | I | unverified |  | diag_h1 driver is safe-by-construction (persist=False) but re-invokes the full projection pipeline incl. Odds-API |
| JP11-6 | JP-11 | export_pick_log_xlsx.py:80 | I | unverified |  | export_pick_log_xlsx odds/profit math is correct; read-only Excel export |
| JP9-08 | JP-9 | weekly_recap.py:475 | I | unverified |  | Month-so-far rollup attributes a month-straddling week entirely to the Sunday's month |
| JP9-10 | JP-9 | weekly_recap.py:102 | I | unverified |  | compute_pl American-odds payout math verified correct (W/L/push/VOID handling) |
| F-11 | JP-7 | mlb_starter_fetcher.py:71 | I | unverified |  | _norm_name is dead code |

## Appendix — refuted / downgraded-to-Info (kept for transparency)

| ID | File:line | orig→final | Why refuted |
|----|-----------|------------|-------------|
| F-1 | analyze_game_lines.py:83 | H→I | The code facts are accurate (SIGMA["NBA"] spread=ml=12.5 at analyze_game_lines.py:85; comment cites margin residual=15.27 at line 84; normal_cdf used  |
| F-2 | analyze_game_lines.py:84 | M→I | The constant 18.5 in analyze_game_lines.py:85 mirrors the canonical frozen GAME_SIGMA in engine/calibrated.py:184. That canonical block (calibrated.py |
| F-3 | analyze_game_lines.py:32 | H→I | The code fact is real (analyze_game_lines.py:32 hardcodes API_KEY="adb07e9742307895c8d7f14264f52aee", git-tracked; odds_io.py:21 + secrets_config.py:9 |
| F-7 | analyze_game_lines.py:489 | M→I | The code at C:/Dev/JonnyParlay/analyze_game_lines.py:489-501 does literally do what the finding describes mechanically: it requests the market `h2h_1s |
| F10 | context_prep.py:183 | M→I | The code does contain emojis in print() (line 183 ✅, line 101 ⚠), but the finding is not material and its mechanism is mis-stated. (1) On an interacti |
| JP12-02 | analyze_blend.py:16 | M→I | The code-level observations are factually true: analyze_blend.py:24 hardcodes BLEND_ALPHA = 0.25 rather than importing from thresholds.py:95 (which is |
| JP12-03 | analyze_blend.py:28 | M→I | The code divergence described is factually accurate: analyze_blend.py (C:/Dev/JonnyParlay/engine/analyze_blend.py) L28-33 builds os.path.join(project_ |
| JP10-F2 | calibrate_distributions.py:156 | M→I | The finding's central claim is factually false. In mode_mlb_team_runs (C:/Dev/JonnyParlay/engine/calibrate_distributions.py), the headline recommendat |
| JP2-01 | calibrated.py:225 | H→I | The finding's load-bearing claim — "The dict is multiplied onto projected runs for F5 and NRFI" — is false. A whole-repo grep for MLB_PARK_FACTORS and |
| JP2-03 | calibrated.py:23 | H→I | Code confirmed: SIGMA['PTS']={'mult':0.35,'min':5.0} at C:/Dev/JonnyParlay/engine/calibrated.py:23; PTS is absent from POISSON_STATS (line 52) and NB_ |
| JP2-07 | calibrated.py:187 | M→I | CODE IS AS DESCRIBED + REACHABLE. C:/Dev/JonnyParlay/engine/calibrated.py:187 sets GAME_SIGMA["MLB"]={total:4.6, spread:4.2, team:3.0, ml:4.2} with th |
| JP2-08 | calibrated.py:308 | M→I | The code literal is accurate (calibrated.py:308, ('WNBA','REB',None):0.10) and the path is reachable for real money (SHADOW_SPORTS is now empty; WNBA  |
| JP2-09 | calibrated.py:84 | M→I | The finding restates, almost verbatim, the in-code comment that already documents the issue and its fix. calibrated.py:84 explicitly notes: starts-onl |
| CLV-1 | capture_clv.py:1882 | M→I | The dead-branch observation is technically correct: inside the capture block (entered only when the line-1752 window guard -CAPTURE_AFTER_SECS<=secs_t |
| CLV-4 | capture_clv.py:1075 | M→I | Code is described accurately: get_closing_odds_for_pick returns the highest price across CO_LEGAL_BOOKS for the bet side (capture_clv.py:1012, 1058),  |
| CLV-6 | capture_clv.py:170 | M→I | The line exists (capture_clv.py:170, STAT_TO_MARKET["YARDS"]="player_reception_yards"), but the claimed harm cannot occur. (1) No pick is ever labeled |
| JP-RF-2 | capture_clv.py:1075 | M→I | The MECHANICAL claim is correct: in both the prop path (capture_clv.py L1840-1850 → get_closing_odds_for_pick L1032-1062) and the game-line path (L133 |
| F3 | context_research_v2.py:367 | M→I | The technical observation is accurate: aggregate_verdict (context_research_v2.py:367-381) linearly sums _WEIGHTS over confirms/fades values that encod |
| F4 | context_research_v2.py:1198 | M→I | The two factual claims are code-true: v2 _factor_line_move uses a single un-scaled threshold (abs<0.5 flat, >=1.0 confirms, <=-1.0 fades, docstring 'M |
| F5 | context_research_v2.py:380 | M→I | Code claim is literally true: context_research_v2.py:380 computes confidence=round(max(wc,wf)/_MAX_POSSIBLE,2) (_MAX_POSSIBLE=25, _VERDICT_THRESHOLD=4 |
| F12 | context_research_v2.py:1769 | M→I | Code claim is accurate: _factor_division (context_research_v2.py:1761-1773) returns "confirms" for any same-division/conference matchup ("familiarity" |
| F14 | context_research_v2.py:108 | M→I | Code is as described: _DOMED_HOME_TEAMS (lines 108-116) contains "Tampa Bay Rays", and _is_indoor()/_factor_weather() (lines 318-323, 1401-1407) short |
| JP10-F11 | evaluate_projector.py:215 | M→I | The finding is technically true that evaluate_projector.py (lines 215-409) assembles the FGA-decomp/blend logic inline rather than calling project_pla |
| JP1-02 | evaluators.py:104 | M→I | The crash is unreachable. proj_player at evaluators.py:104 is always a dict produced by parse_csv (odds_io.py), reached via match_props_to_projections |
| JP1-09 | evaluators.py:843 | M→I | Code matches the description exactly (evaluators.py 843-886: BASE_LAMBDA_1ST=0.32, NRFI_GAMMA=0.65, _LEAGUE_AVG_RUNS=4.45, _LEAGUE_AVG_BLENDED_RATE=0. |
| JP-RF-3 | evaluators.py:860 | M→I | Code claim is accurate but the path is NOT a live-money path, so the finding is immaterial. evaluators.py:860 `_LEAGUE_AVG_RUNS=4.45` is the denominat |
| JP13-01 | gates.py:199 | M→I | The mechanical claim is accurate: in C:/Dev/JonnyParlay/engine/gates.py, G9 (line 141, `if edge < 0.05: return False, "G9"`) is unconditional, and `ed |
| JP13-02 | gates.py:193 | M→I | The code matches the description (gates.py:195 `if _cv and float(_cv) >= 0.60`, no try/except), but the claimed crash path is unreachable in productio |
| JP13-04 | gates.py:51 | M→I | Factual claims verified accurate: every cited gate/line exists as described (gates.py G8B n=8 L51, G8C n=14 L69, G8D n=16 L75, G13 "1-3 record" L148;  |
| JP5-01 | grade_picks.py:1125 | H→I | Code claim is literally accurate: grade_game_line (C:/Dev/JonnyParlay/engine/grade_picks.py) sets direction = pick["direction"] at line 1099 with no n |
| JP5-03 | grade_picks.py:1644 | M→I | Code reading is accurate: grade_picks.py:1644 `p.get("player","").split()[-1]` raises IndexError on a blank player, and the recap path (build_recap_em |
| JP9-05 | health_check.py:155 | M→I | Code behavior is accurately described and reachable. health_check.py L155-192 matches literal whitespace-aligned substrings ('KILLSHOT_SIZE_BASE       |
| JP10-F3 | historical_backtest.py:386 | M→I | Code claim is literally true: C:\Dev\JonnyParlay\engine\historical_backtest.py line 387 computes the headline `mean_ratio = sum(ratios)/len(ratios)` ( |
| JP3-09 | mlb_sgp_builder.py:596 | M→I | Code behavior is accurately described and reachable (run_mlb_sgp_builder -> build_mlb_sgp:596-600; fail-open at 944-948), but it is a deliberate conse |
| JP10-F10 | nb_calibrate.py:14 | M→I | The finding is materially inaccurate on its central claim and otherwise restates already-documented, already-gated backlog state.  (1) K r=5.0 is NOT  |
| F-14 | odds_io.py:353 | M→I | The finding claims totals_1st_1_innings is fetched and stored under {eid}_nrfi but never consumed, implying paid-for-but-unused API data. This is fals |
| JP8-6 | pick_log_io.py:173 | M→I | The factual claims are all accurate: pick_log_io.py:173 opens the reader with encoding='utf-8' and no newline='' (DictReader on line 174); writers in  |
| JP8-4 | pick_log_writers.py:295 | M→I | The factual core is accurate but immaterial, and one half of the finding is wrong. (1) Accurate: validate_is_home_for_stat (pick_log_schema.py:329) is |
| JP8-5 | pick_log_writers.py:627 | M→I | Code-level claim is accurate: _log_value_parlay (C:/Dev/JonnyParlay/engine/pick_log_writers.py line 627) writes tier="LONGSHOT" while run_type="value_ |
| JP8-7 | pick_log_writers.py:278 | M→I | The code pattern is accurately described: f"{p.get('win_prob', 0):.4f}" (line 278), the same in _log_bonus_pick (698), and round(p.get('win_prob',0),4 |
| JP8-8 | pick_log_writers.py:404 | M→I | The finding is hypothetical, not an actual divergence. In post_daily_lay() (discord_post.py:461-522), the posted size is DAILY_LAY_SIZE = size_daily_l |
| JP2-06 | copula.py:146 | M→I | The finding's core mechanism claim is false. The callee cholesky() (copula.py:96-111) does NOT raise on a non-PSD matrix — it clips via math.sqrt(max( |
| JP3-02 | copula.py:114 | M→I | Code facts confirmed: copula_joint_prob is a t-copula with COPULA_DF=6 (copula.py:22,114) feeding the NBA EV gate (_joint_ev_ok, sgp_builder.py:1018-1 |
| JP2-05 | derived.py:43 | M→I | Code claim is technically accurate but immaterial. In calc_tb_prob (derived.py:44,64), threshold=floor(line)+1, so for an integer line L over_p=P(TB>= |
| JP1-06 | run_picks.py:1121 | M→I | The factual premise is accurate — evaluators.py:181 stores over_p_raw = over_p (P(over)) on BOTH the over and under direction picks, and run_picks.py: |
| JP10-F4 | sabersim_backtest.py:244 | M→I | The code mechanism is real but the finding's materiality/reachability claims fail. Verified facts: sabersim_backtest.py:246-251 calls run_projections( |
| JP14-1 | secrets_config.py:93 | M→I | The code fact is real but the materiality is overstated/false. secrets_config.py:93-96 does default EDGEMODEL_DB_PATH to C:\Users\jono4\Documents\Edge |
| JP14-5 | secrets_config.py:1 | M→I | The factual observation is TRUE: C:/Dev/JonnyParlay/engine/secrets_config.py is saved double-encoded. Raw bytes confirm a UTF-8 BOM (EF BB BF) followe |
| JP3-06 | sgp_builder.py:707 | M→I | The factual core is correct: Gate 2 (copula_joint − product(fair) ≥ 0.015) rarely binds. Decomposing, copula_joint − no_vig_independent = (Gate-1 marg |
| JP2-04 | sizing.py:117 | M→I | The code-level observation is literally correct: size_picks_vake (C:/Dev/JonnyParlay/engine/sizing.py:117-119) only does final=min(round_units(raw),1. |
| JP14-2 | team_resolve.py:75 | M→I | The finding's load-bearing premise is factually false. It claims get_game_sigma/get_game_sigma_team pass an already-abbreviated team (e.g. 'DEN') into |
| JP14-3 | team_resolve.py:44 | M→I | Code matches verbatim (team_resolve.py:45,65), but the fallback is unreachable in production. GAME_SIGMA (calibrated.py:173-188) is fully populated fo |
| JP13-03 | thresholds.py:72 | M→I | Code confirmed and reachable: WNBA_EARLY_SEASON_EDGE_MULT=[(14,0.80),(21,0.90)] at thresholds.py:72-75 feeds wnba_gate._wnba_early_season_factor(), wh |
| JP13-05 | thresholds.py:15 | M→I | The finding mis-models EV. It computes 0.50 (model gate) × 2.00 (+100 cap) = break-even, but true parlay EV = combined_prob / book_implied_combined −  |
| JP11-4 | analyze_playoff_scalars.py:183 | M→I | The code claim is literally true: at line 183 `csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))` raises IndexError if out_rows is empty, and _su |
| JP11-2 | diag_blowout_buckets.py:136 | M→I | The factual code claim is accurate: C:/Dev/JonnyParlay/engine/tools/diag_blowout_buckets.py line 136 hardcodes 'current model: max_reduction=0.200 mid |
| JP11-3 | diag_blowout_buckets.py:73 | M→I | Code claims are factually correct but the finding is not material. (1) Unreachable: diag_blowout_buckets.py is an explicitly-labeled advisory "D2 diag |
| JP9-03 | weekly_recap.py:69 | M→I | The finding assumes KILLSHOT picks are logged with run_type='killshot', which is false. KILLSHOT is a TIER, not a run_type. KILLSHOT picks are written |
| F-9 | mlb_starter_fetcher.py:52 | M→I | The finding's causal mechanism is unsupported by any reachable code path. is_confirmed() has exactly two callers, and BOTH operate within the SaberSim |
| CLV-5 | retro_correct_clv.py:79 | M→I | Code facts are accurate: retro_correct_clv.py:79 does pd.read_csv(PICK_LOG_PATH) with no FileLock, while engine/pick_log_io.py provides the canonical  |
| JP12-01 | save_context.py:57 | M→I | The mechanical claim is accurate: save_context.py `_merge` (L57-68) starts `kept = [e for e in existing if e.get("date") == today]`, so on each write  |
