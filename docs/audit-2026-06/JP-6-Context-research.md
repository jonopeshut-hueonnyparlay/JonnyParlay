# AUDIT 2026-06 — JP-6 Context research (JonnyParlay)

Files audited (3 read): context_research_v2.py, context_research.py, context_prep.py

**Findings (final, excl. refuted): C=0 H=0 M=3 I=6** | constants extracted: 22 | not-done: 6

## Findings

| ID | File:line | Sev | Status | Cat | Known | Title |
|----|-----------|-----|--------|-----|-------|-------|
| F7 | context_prep.py:40 | M | confirmed | code |  | Hardcoded ODDS_API_KEY fallback literal committed in source |
| F2 | context_research_v2.py:173 | M | confirmed | statistical |  | Wind OUT/IN direction sets appear inverted vs meteorological 'direction-from' convention |
| F9 | context_research_v2.py:1463 | M | confirmed | completeness |  | Umpire factor is effectively a stub — JSON source unverified and HTML fallback always returns None |
| F6 | context_prep.py:66 | I | confirmed | completeness |  | context_prep prompt template emits 'conflicts' verdict and '>60%' aggregation — schema-incompatible with canonical 'fades'/thresho |
| F10 | context_prep.py:183 | I | refuted | code |  | Emoji in print() can raise UnicodeEncodeError on legacy Windows console and abort the helper |
| F1 | context_research_v2.py:1226 | I | confirmed | code |  | MLB injury verdicts are marked data_quality='stale' and then force-overridden to neutral — the weight-3 MLB injury signal is dead |
| F3 | context_research_v2.py:367 | I | refuted | statistical |  | Cross-axis conflation: factors on incompatible axes (total over/under vs home/away side) are linearly summed into one confirms/fad |
| F4 | context_research_v2.py:1198 | I | refuted | statistical |  | line_move threshold drift (v2=1.0 vs v1 prompt=1.5) and MLB-scale thresholds applied unscaled to NBA/WNBA totals |
| F5 | context_research_v2.py:380 | I | refuted | statistical |  | confidence = max(wc,wf)/MAX_POSSIBLE overstates confidence on near-ties and diverges from documented abs-difference formula |
| F8 | context_research_v2.py:1322 | I | confirmed | statistical |  | FIP formula omits HBP term and uses constant 3.10 (low vs ~3.15-3.20) |
| F12 | context_research_v2.py:1769 | I | refuted | statistical |  | division==same → 'confirms' is an unfounded directional mapping |
| F14 | context_research_v2.py:108 | I | refuted | statistical |  | Tampa Bay Rays hardcoded as domed → weather force-neutral, but Rays are playing outdoors (Steinbrenner Field) due to Tropicana roo |
| F16 | context_research_v2.py:1266 | I | unverified | completeness |  | rlm hook is dead code — keyed branch is a bare 'pass' |
| F13 | context_research_v2.py:1778 | I | unverified | code |  | Per-factor try/except containment + quality override make the daily run crash-resistant |
| F11 | context_research_v2.py:1562 | I | unverified | statistical |  | Pythagorean exponents are defensible (NBA/WNBA 16.5 = Hollinger; MLB 2.0 = classic James) |

## C/H/M detail

### [M] F7 — Hardcoded ODDS_API_KEY fallback literal committed in source
`C:/Dev/JonnyParlay/context_prep.py:40-40` · code · status=confirmed

**Evidence:** API_KEY=os.getenv('ODDS_API_KEY','fe2a128f9a93210ea4a4556f9f33a1e3') — a real Odds API key literal is committed as a fallback. Per project memory the active key is a Windows env var overriding a stale .env key; this embedded key is a credential leak in source control and will be used if the env var is unset.

**Recommendation:** Remove the literal default; fail closed (sys.exit) when ODDS_API_KEY is unset, as the other entrypoints do.

**Verifier (confirmed):** Code confirmed: C:/Dev/JonnyParlay/context_prep.py line 40 reads `API_KEY = os.getenv("ODDS_API_KEY", "fe2a128f9a93210ea4a4556f9f33a1e3")`, and the value is consumed in a real request at line 95 (`urlencode({"apiKey": API_KEY, ...})`). The file is git-tracked and the literal was committed (git log -S found it in commit 0cd6052), so this is a credential committed to source control, not a runtime-only value. The fallback path IS reachable: if ODDS_API_KEY is absent from both the process env and th

### [M] F2 — Wind OUT/IN direction sets appear inverted vs meteorological 'direction-from' convention
`C:/Dev/JonnyParlay/engine/context_research_v2.py:173-174` · statistical · status=confirmed

**Evidence:** _PARK_WIND_OUT={N,NNE,NE,NNW,NW}, _PARK_WIND_IN={S,SSE,SE,SSW,SW} with comment 'home-plate-south orientation: OUT toward center field, IN toward home plate'. wttr.in winddir16Point reports the direction the wind blows FROM (standard meteorology). With home plate south and CF north, 'blowing out toward CF (north)' requires wind FROM the south = a 'S' direction, not 'N'. As written, a northerly wind (from CF toward home, i.e. blowing IN) is classified OUT→'confirms' over, inverting the weather signal (lines 1433-1438). The all-parks-face-south assumption is itself a strong oversimplification.

**Recommendation:** Swap the OUT/IN sets (or invert the comparison), and ideally store per-park orientation rather than assuming home-plate-south for all 30 parks.

**Verifier (confirmed):** Confirmed both in code and against the meteorological benchmark. Lines 173-174 define _PARK_WIND_OUT={N,NNE,NE,NNW,NW} / _PARK_WIND_IN={S,SSE,SE,SSW,SW} with the comment 'home-plate-south orientation: OUT toward center field, IN toward home plate.' These feed _factor_weather (lines 1433-1438), where OUT->'confirms' (over) and IN->'fades.' The path is live: _factor_weather is one of 15 factors in research_game_v2 (line 1789), fired for outdoor MLB games when wind_kmph>=16 and winddir16Point is pr

### [M] F9 — Umpire factor is effectively a stub — JSON source unverified and HTML fallback always returns None
`C:/Dev/JonnyParlay/engine/context_research_v2.py:1463-1481` · completeness · status=confirmed

**Evidence:** _fetch_ump_stats tries umpscorecards.com/api/umpires/ (endpoint existence/shape unverified) then, in the bs4 branch, explicitly 'do not guess a brittle selector here. Return None' (lines 1474-1481). With no pre-populated cache, the umpire factor degrades to stale→neutral on every run, so the factor contributes nothing in practice.

**Recommendation:** Either implement a working umpire run-environment source or document the umpire factor as intentionally inert; currently it advertises a capability it does not deliver.

**Verifier (confirmed):** Confirmed and reachable. _fetch_ump_stats (context_research_v2.py:1463-1481) always returns None: the bs4 fallback returns None in both the present and ImportError branches. The JSON path is also broken — I probed the live endpoint https://umpscorecards.com/api/umpires/ (HTTP 200, application/json) and found three independent defects: (1) it returns {"rows":[...]} (a dict), so isinstance(api,list) at line 1467 is False and the loop never runs; (2) the umpire key is "umpire" not "name", so the u.


## Confirmed-correct / coverage notes

- **Crash resistance (daily run):** Every `_factor_*` in v2 is wrapped in try/except → `_failed_factor()`, `_get_json` never raises, and `research_game_v2`/`main` are linear. A single failing source degrades to neutral, not an aborted run. This module is also documented display-only ('never blocks picks or affects sizing', gate 50+ context-graded picks), so even biased verdicts cannot mis-price/mis-size live money today — this caps realistic severity at M.
- **Weight bookkeeping correct:** `_WEIGHTS` sums to exactly 25 (`_MAX_POSSIBLE`), 3+3+3 + 2+2+2+2 + 1×8. `aggregate_verdict` threshold-of-4 net logic is symmetric for confirms/fades.
- **Quality override is sound (in isolation):** `_apply_quality_override` correctly forces stale/failed → neutral and tags neutral_reason; the only problem is upstream factors mislabeling real signals as 'stale' (F1).
- **Pythag exponents are published values:** NBA/WNBA 16.5 (Hollinger), MLB 2.0 (classic James); ratio-based per-team computation is correct and robust to differing games-played.
- **Wind speed unit conversion is right:** 16 km/h ≈ 9.94 mph, matching the v1 prompt's 10 mph threshold; precip and heat branches are ordered sensibly (precip first).
- **Rest/travel gap logic:** the comment correctly identifies that a window ending yesterday makes min gap = 1, so B2B==1 / rested>=2 is the right reachable encoding; travel eastward (phase-advance) disadvantage is consistent with circadian research even though it intentionally diverges from the v1 prompt's westward wording.
- **Team maps:** Athletics correctly handled as outdoor (West Sacramento) in both city and tz maps; LA-team canonicalization (`_canon_team`) consistently applied across standings, name-match, and aliases.
- **Cache/merge:** `_write_merged` prunes prior-day entries and preserves today's other-sport entries keyed by game string; `_split_cache`/`_partition_games` honor `--refresh`. No race (v2 is single-threaded; v1's ThreadPool only touches per-task results, no shared mutable module cache).

## Not-Done / incomplete (this module)

| Kind | File | Detail |
|------|------|--------|
| flag-gated | context_research_v2.py | _factor_rlm and _factor_public_sharp permanently return stale-neutral (weight 5/25 dead) until ACTION_NETWORK_PRO_KEY is added; documented in module docstring l |
| stub | context_research_v2.py | _factor_rlm keyed branch (lines 1268-1270) is a bare 'pass' — even with a key set, RLM is never computed. |
| stub | context_research_v2.py | _fetch_ump_stats HTML scrape fallback (lines 1474-1481) intentionally returns None ('do not guess a brittle selector'); umpire factor inert without a working JS |
| partial-feature | context_research_v2.py | WNBA standings lack last10 and home/road splits, so _factor_form and _factor_home_away always degrade to stale-neutral for WNBA (lines 1594,1638); NHL has no st |
| dead-code | context_research.py | v1 paid-Opus path (claude-opus-4-8 web_search) is superseded by the free v2 implementation per the v2 docstring; retained but not the active producer. |
| deferred | context_research_v2.py | opening-line snapshot captures home_ml/away_ml (line 755) but _factor_line_move only consumes 'total'; moneyline movement captured-but-unused. |
