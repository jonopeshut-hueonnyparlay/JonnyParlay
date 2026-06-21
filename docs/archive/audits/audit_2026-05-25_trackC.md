# Audit 2026-05-25 — Track C: Data Integration & Name Matching

Auditor: Claude Sonnet 4.6 (automated)
Scope: engine/name_utils.py, engine/run_picks.py — name matching, game/team matching, odds line matching, cache

---

## C1. Player Name Matching

### Normalization contract

`name_utils.fold_name()` (~lines 50–71): NFKD + ASCII encode (strips all combining marks/accents), lowercase, strips everything except `[a-z\s]` (removes apostrophes, hyphens, periods), collapses whitespace. Correctly handles Dončić→doncic, D'Angelo→dangelo.

`name_key()` (~lines 74–92): builds `"lastname_firstN"` key, strips Jr/Sr/II/III/IV/V suffixes before extracting last name.

Both SaberSim CSV and Odds API names go through same `name_key()` path. Normalization is symmetric.

---

### C-1 (MEDIUM) — Local name_key in run_picks.py not imported from name_utils

```
TRACK: C
FILE: engine/run_picks.py
LINE: ~1490–1503
SEVERITY: MEDIUM
N: N/A
ISSUE: run_picks.py defines its own local name_key() function (line ~1490) that is
functionally identical to name_utils.name_key() but NOT imported from there. Only
fold_name is imported from name_utils. If name_utils.name_key() is ever updated
(suffix stripping, key format change), the local copy will silently diverge — causing
systematic match failures with zero warning.
IMPACT: Silent drift risk. Name mismatch = prop silently skipped. No error logged.
FIX: Import name_key from name_utils: `from name_utils import fold_name as _fold_name, name_key`
and remove the local name_key definition at ~line 1490.
```

### C-2 (LOW) — No logging for unmatched props

```
TRACK: C
FILE: engine/run_picks.py
LINE: ~2188–2208
SEVERITY: LOW
N: N/A
ISSUE: match_props_to_projections() silently drops unmatched props. Only a summary count
is printed ("N prop lines found, M matched to projections"). No detail on which players
failed to match.
IMPACT: Silent name-format mismatches produce no diagnostic. Impossible to detect without
adding debug prints.
FIX: Add: `missed = [p["player"] for p in props if p["player_key"] not in player_map]`
and log at debug level when missed is non-empty.
```

### C-3 (LOW) — name_key dict collision takes last entry silently

```
TRACK: C
FILE: engine/run_picks.py
LINE: ~2190
SEVERITY: LOW
N: N/A
ISSUE: `player_map = {p["name_key"]: p for p in players}` takes the last player for
any colliding name_key. Two players with same first-3+lastname (e.g. two "Mike Williams"
from different sports) would silently shadow each other.
IMPACT: Theoretical. Single-sport CSVs make genuine collisions rare.
FIX: Low priority. Could warn on collision.
```

---

## C2. Game / Team Matching

### C-4 (MEDIUM) — Cross-sport team abbreviation collisions in flat TEAM_ABBREV

```
TRACK: C
FILE: engine/run_picks.py
LINE: ~457–500
SEVERITY: MEDIUM
N: N/A
ISSUE: TEAM_ABBREV is a flat dict shared across NBA, NHL, and MLB. Multiple abbreviations
map identically across sports: BOS (Celtics + Bruins + Red Sox), CHI (Bulls + Blackhawks),
TOR (Raptors + Maple Leafs + Blue Jays), PHI (76ers + Flyers + Phillies), ATL (Hawks + Braves),
MIA (Heat + Marlins), MIN (T-Wolves + Wild + Twins), DAL (Mavs + Stars), DET (Pistons +
Red Wings + Tigers), PIT (Penguins + Pirates), SEA (Kraken + Mariners), COL (Avalanche +
Rockies), ARI (Coyotes + D-backs), STL (Blues + Cardinals), UTA (Jazz + Utah HC).
evaluate_game_lines() builds a raw team_proj dict keyed only by bare team abbreviation
(no sport prefix), making cross-sport contamination possible on a concurrent NBA+NHL day
if players are not sport-filtered upstream.
IMPACT: On a multi-sport day, NHL team projection could overwrite NBA team projection in
the game-lines probability calc. Race depends on dict construction order.
FIX: Verify players list passed to evaluate_game_lines() is always pre-filtered by sport.
If confirmed, this is a documentation gap, not a live bug. If not, add sport-keyed dict.
```

### C-5 (LOW) — Game total team lookup uses raw substring match

```
TRACK: C
FILE: engine/run_picks.py
LINE: ~2413–2418
SEVERITY: LOW
N: N/A
ISSUE: The projection lookup for game totals uses `tk in home_name or home_name in tk`
where tk is a 3-letter CSV abbreviation and home_name is the full API team name.
"ANA" in "INDIANA PACERS" is True — known collision risk. The guarded find_team_proj()
function with last-word fallback is NOT used here.
IMPACT: Could match wrong team for game totals on slates with short-abbreviation collisions.
FIX: Replace the raw substring loop at ~2410–2418 with a call to find_team_proj().
```

### C-6 (LOW) — is_home fallback fragile on short/shared city names

```
TRACK: C
FILE: engine/run_picks.py
LINE: ~2520–2522
SEVERITY: LOW
N: N/A
ISSUE: is_home fallback uses `team_name.lower() in home_name.lower()`. For "Utah Jazz" vs
"Utah Hockey Club" both contain "utah" — could return True for both. Primary resolve_team_abbrev
path is correct (both return "UTA" which is unambiguous in context), but the fallback is fragile.
IMPACT: Wrong is_home on teams missing from TEAM_ABBREV. Could swap team margin sign,
inverting spread win_prob.
FIX: Log a warning when fallback fires. Verify all current team names are in TEAM_ABBREV.
```

---

## C3. Odds API Line Matching

### C-7 (HIGH) — Multiple lines per player/stat all flow through independently

```
TRACK: C
FILE: engine/run_picks.py
LINE: ~1927–1962
SEVERITY: HIGH
N: N/A
ISSUE: The best-odds dict is keyed by (player, line). If Book A offers a prop at 24.5
and Book B offers the same stat at 25.5, the engine creates TWO separate prop entries.
Both flow through match_props_to_projections() and evaluate_props(). Both can qualify
as picks. The final card deduplication keys on date+player+stat+line+direction — so
picks at different lines for the same stat both pass through.
IMPACT: Engine may evaluate and post alternate lines, not the market-consensus line.
A lowered alternate line (e.g. 24.5 vs standard 25.5) inflates win_prob and edge —
the model gets doubled positive bias. The pick posted may not be bettable at those odds
because the alternate line has lower availability or has already moved.
FIX: Add a line-selection step before building the best-odds dict: select the line
offered by the most books (consensus line), or the highest-limit line. If intent is
line-shopping, document explicitly. Currently the behavior is neither — it evaluates
all lines and takes whichever scores highest, which is not documented.
```

### C-8 (MEDIUM) — Best over and best under can be from different books

```
TRACK: C
FILE: engine/run_picks.py
LINE: ~1955–1962
SEVERITY: MEDIUM
N: N/A
ISSUE: book_over and book_under can be different books. calc_edge() uses over_odds (best
over from Book A) and under_odds (best under from Book B) together to compute the no-vig
probability anchor. The pick's book field shows only the side being played.
IMPACT: No-vig anchor uses mixed-book data. Users see pick labeled "FanDuel" and bet there,
but the vig-removal math may have used DraftKings' under. Acceptable for single-direction bets
since users only bet one side. The over_odds used for the bet are correctly Book A's odds.
FIX: Acceptable as-is. Add comment documenting cross-book no-vig calculation.
```

### C-9 (LOW) — Single-sided markets silently dropped

```
TRACK: C
FILE: engine/run_picks.py
LINE: ~2229
SEVERITY: LOW
N: N/A
ISSUE: When only one side is offered (over_odds populated but under_odds is None, or vice
versa), the pick is silently skipped at line ~2229 (continue). No log, no count.
IMPACT: Players where only one side is offered (common with sharp books) are invisibly dropped.
FIX: Add debug-level log when both sides unavailable.
```

---

## C4. Stale Odds Cache

### C-10 (MEDIUM) — 15-minute cache with no post-evaluation freshness check

```
TRACK: C
FILE: engine/run_picks.py
LINE: ~1685–1702
SEVERITY: MEDIUM
N: N/A
ISSUE: Cache TTL is 15 minutes (code) — CLAUDE.md says "11-minute cache" (MISMATCH).
There is no staleness check at bet-finalization time. After picks are evaluated and
posted to Discord, odds are not re-fetched. A line that moved during the 15-minute
window produces a stale pick.
IMPACT: In a fast-moving market (injury news, sharp action), 15 minutes is enough for
a 5–10 cent line move (~3–4pp implied probability). For a 3% edge pick, this can flip
from +EV to -EV before the user bets.
FIX: Add staleness warning when cache age > 10 minutes: print a caution before posting.
On --late-run, consider tightening to 5-minute TTL. Update CLAUDE.md: "15-minute cache".
```

### C-11 (LOW) — Cache open() calls missing encoding="utf-8"

```
TRACK: C
FILE: engine/run_picks.py
LINE: ~1695, ~1711
SEVERITY: LOW
N: N/A
ISSUE: open(cache_file, "r") and open(cache_file, "w") lack encoding="utf-8". On Windows
with non-UTF-8 locale, player names with non-ASCII chars (accents) could be mangled in
cache. A UnicodeDecodeError fallback triggers a re-fetch (benign), but a partial mangle
that still parses could produce garbled player names → missed prop matches.
IMPACT: Low on Jono's machine (PYTHONIOENCODING=utf-8 in .bat file). Defensive fix.
FIX: Add encoding="utf-8" to both cache open() calls.
```
