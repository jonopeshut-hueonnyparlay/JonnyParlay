"""pick_log_schema.py — single source of truth for the pick_log CSV contract.

Before consolidation (audit H-3), `HEADER` lived as a local variable in
`run_picks.log_picks()` and `BONUS_HEADER` was copy-pasted a few thousand
lines down in `log_single_bonus_pick()`. Any time a new column was added,
both definitions had to be updated in lockstep, and reader modules
(grade_picks, capture_clv, weekly_recap, analyze_picks) had no way to
know whether an on-disk row was from an older schema version.

This module:
  1. Exports `CANONICAL_HEADER` — the 29-column schema as of SCHEMA_VERSION.
  2. Defines migration rules so old-schema rows (e.g. pre-CLV, pre-context)
     can be read alongside current-schema rows without silent data loss.
  3. Gives every reader one helper — `migrate_row()` — to get a canonical
     dict back regardless of what shape the CSV on disk is in.

SCHEMA HISTORY
  v1 (deprecated)  : original 20-col schema, pre-CLV, pre-context
                     date..result
  v2 (deprecated)  : adds closing_odds, clv, card_slot, is_home,
                     context_verdict, context_reason, context_score (27 cols)
  v3 (deprecated)  : adds legs — JSON parlay leg detail (28 cols)
  v4 (deprecated)  : adds over_p_raw — pre-Platt over probability (29 cols).
                     Enables proper Platt refit without double-calibration bias
                     (Research Brief 8 / Walsh & Joshi 2024). Blank for legacy
                     rows and non-prop picks (game lines, parlays).
  v5 (current)     : adds source, model_version, run_id — per-bet SOURCE PROVENANCE
                     (32 cols). `source` = which source drove the live price
                     ('sabersim' by default; 'edgemodel'/'blend:<w>' once a market
                     is promoted via the coverage_manifest). `model_version` =
                     pricing/model tag (blank for the live source). `run_id` ties
                     the bet to its run (cross-refs the run_manifest / projection
                     contract in projections.db). Append-only; blank-fills for
                     legacy rows. Powers the bet_lineage reconstruction.

Bumping the schema:
  - Add new columns to the end of CANONICAL_HEADER (append-only keeps
    on-disk compatibility simple).
  - Bump SCHEMA_VERSION.
  - No changes needed to migrate_row() unless the new column has a
    non-empty default — if so, wire it into _DEFAULTS.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, Mapping

# ─────────────────────────────────────────────────────────────────
# Canonical schema (v4)
# ─────────────────────────────────────────────────────────────────

SCHEMA_VERSION = 5

# Default `source` label for the live pricing source (SaberSim CSV). A bet carries
# this unless the resolver promoted its market off 'shadow' (then 'edgemodel' or
# 'blend:<w>'). Single source of truth so every writer agrees.
LIVE_SOURCE = "sabersim"

CANONICAL_HEADER: list[str] = [
    "date", "run_time", "run_type", "sport", "player", "team", "stat", "line",
    # M-11: proj is 2-decimal float string (see normalize_proj).
    # M-12: edge is 4-decimal DECIMAL (0.0500 = 5%); display layers render as %.
    "direction", "proj", "win_prob", "edge", "odds", "book",
    # M-10: size is 2-decimal float string (see normalize_size).
    "tier", "pick_score", "size", "game", "mode", "result",
    "closing_odds",      # v2: CLV capture target (filled by capture_clv.py)
    "clv",               # v2: closing_implied − your_implied
    "card_slot",         # v2: 1-5 if posted on premium card; blank otherwise
    # M-3: is_home is canonical "True"/"False"/"" — set for SPREAD/ML_FAV/ML_DOG/
    # F5_SPREAD/F5_ML/TEAM_TOTAL, blank for props (see normalize_is_home).
    "is_home",
    "context_verdict",   # disabled (frozen — context system removed 2026-05-23; existing rows carry "disabled")
    "context_reason",    # v2: ≤12-word reason string
    "context_score",     # v2: 0-3 confluence count
    # v3: parlay leg detail — JSON array for longshot/sgp/daily_lay rows.
    # Each element: {"player","direction","line","stat","sport","game"}.
    # Blank for single-leg picks (primary, bonus, manual, gameline).
    "legs",
    # v4: raw over_p before Platt calibration. Enables proper calibrate_platt.py
    # refit without the double-calibration bias where win_prob (already Platt-
    # transformed) was mistakenly fed back as input. Blank for legacy rows,
    # non-prop picks (game lines, parlays), and manual entries.
    "over_p_raw",
    # v5: per-bet source provenance.
    "source",          # which source drove the price: 'sabersim'|'edgemodel'|'blend:<w>'
    "model_version",   # pricing/model tag (blank for the live source)
    "run_id",          # ties the bet to its run (cross-refs run_manifest / projection contract)
]

# Fast membership checks.
KNOWN_COLUMNS: frozenset[str] = frozenset(CANONICAL_HEADER)

# Columns that existed in SCHEMA v1 (pre-CLV / pre-context).
_V1_COLUMNS: frozenset[str] = frozenset([
    "date", "run_time", "run_type", "sport", "player", "team", "stat", "line",
    "direction", "proj", "win_prob", "edge", "odds", "book",
    "tier", "pick_score", "size", "game", "mode", "result",
])

# Columns added in v2 (CLV + context columns).
_V2_COLUMNS: frozenset[str] = frozenset([
    "closing_odds", "clv", "card_slot", "is_home",
    "context_verdict", "context_reason", "context_score",
])

# Columns added in v3 (parlay leg detail).
_V3_COLUMNS: frozenset[str] = frozenset(["legs"])

# Columns added in v4 (pre-Platt over probability for calibration fidelity).
_V4_COLUMNS: frozenset[str] = frozenset(["over_p_raw"])

# Columns added in v5 (per-bet source provenance).
_V5_COLUMNS: frozenset[str] = frozenset(["source", "model_version", "run_id"])

# Default value for any canonical column that's missing from an input row.
# Empty string is what writers emit for "not applicable" / "not yet filled",
# so using "" preserves the existing "blank means nothing here" contract.
_DEFAULTS: dict[str, str] = {col: "" for col in CANONICAL_HEADER}


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def detect_schema_version(on_disk_header: Iterable[str] | None) -> int:
    """Infer which schema version an on-disk pick_log was written under.

    Returns:
      5 — header includes any v5-only column (source/model_version/run_id)
      4 — header includes any v4-only column (over_p_raw)
      3 — header includes any v3-only column (legs)
      2 — header includes any v2-only column (CLV/context)
      1 — header is a subset of _V1_COLUMNS (legacy)
      0 — header is empty / None / indecipherable
    """
    if not on_disk_header:
        return 0
    cols = set(on_disk_header)
    if cols & _V5_COLUMNS:
        return 5
    if cols & _V4_COLUMNS:
        return 4
    if cols & _V3_COLUMNS:
        return 3
    if cols & _V2_COLUMNS:
        return 2
    if cols and cols.issubset(_V1_COLUMNS):
        return 1
    return 0


def migrate_row(row: Mapping[str, object], source_header: Iterable[str] | None = None) -> dict[str, str]:
    """Return a dict keyed by CANONICAL_HEADER, filling missing cols with "".

    Args:
      row: the raw dict from csv.DictReader (keys = on-disk header, values = strings).
      source_header: optional — the fieldnames seen on disk. Currently unused
        for per-column defaulting, but passed through so future schema versions
        can dispatch on source_header without breaking the call site.

    Guarantees:
      - Every key in CANONICAL_HEADER is present in the output.
      - Values that were empty on disk stay empty (no magic backfill).
      - Unknown columns are dropped (silent — writers use extrasaction="ignore"
        anyway, so retaining them would just cause a drift-vs-truncate mismatch
        downstream).
    """
    _ = source_header  # reserved for future schema migrations
    out: dict[str, str] = {}
    for col in CANONICAL_HEADER:
        val = row.get(col, _DEFAULTS[col]) if row else _DEFAULTS[col]
        out[col] = "" if val is None else str(val)
    return out


# ─────────────────────────────────────────────────────────────────
# Migration framework (P2.12) — registry + chain + file runner
# ─────────────────────────────────────────────────────────────────
# v1→v4 bumps were all APPEND-ONLY, so migrate_row() (blank-fill) upgrades them
# losslessly with no registered transforms. This framework exists for v5+ bumps
# that need a real TRANSFORM (rename a column, split one into two, compute a
# non-blank default from sibling columns) — register a per-version upgrade fn
# and the chain runner applies it. With no registered migrations (today's state)
# everything below is a pure pass-through: NO data change.

# Maps from_version -> a fn(row_dict) -> row_dict that upgrades a single row by
# exactly one schema version. Append-only versions need no entry.
_MIGRATIONS: dict[int, Callable[[dict], dict]] = {}


def register_migration(from_version: int, fn: Callable[[dict], dict]) -> None:
    """Register a per-version upgrade transform: from_version -> from_version+1.

    Call at import time (e.g. when bumping to v5, register_migration(4, fn) that
    maps a v4 row to a v5 row). Only needed when the bump is NOT append-only;
    append-only bumps are handled by migrate_row()'s blank-fill. Re-registering
    the same from_version overwrites the prior fn (last write wins).
    """
    _MIGRATIONS[from_version] = fn


def migrate_row_chain(row: Mapping[str, object], from_version: int,
                      source_header: Iterable[str] | None = None) -> dict[str, str]:
    """Upgrade a single row from `from_version` to the current SCHEMA_VERSION.

    Applies each registered per-version transform in order (from_version,
    from_version+1, …), then canonicalizes via migrate_row() (which fills any
    still-missing columns with "" and drops unknowns). For append-only history
    (no registered transforms) this is exactly migrate_row().
    """
    cur: dict = dict(row) if row else {}
    v = from_version
    while v < SCHEMA_VERSION:
        fn = _MIGRATIONS.get(v)
        if fn is not None:
            cur = fn(cur)
        v += 1
    return migrate_row(cur, source_header=source_header)


# ─────────────────────────────────────────────────────────────────
# Write-time normalization (PICK_LOG_AUDIT H-3, H-4)
# ─────────────────────────────────────────────────────────────────

# Fields that must be non-blank on a manual-entered row (PICK_LOG H-4).
# Model-generated rows (run_picks.py primary/bonus/daily_lay) are trusted —
# they come from the engine, which fills these unconditionally.
MANUAL_REQUIRED_FIELDS: tuple[str, ...] = (
    "date", "sport", "stat", "line", "direction",
    "odds", "book", "size",
)


class ManualRowValidationError(ValueError):
    """Raised when a manual-entered pick_log row is missing required fields.
    See PICK_LOG_AUDIT H-4."""


def normalize_american_odds(odds) -> str:
    """Canonical American-odds string: always sign-prefixed ("+105", "-110").

    PICK_LOG_AUDIT H-3: ``run_picks.py`` historically wrote ``105`` for positive
    odds while ``post_nrfi_bonus.py`` and manual entries wrote ``+105``.
    ``analyze_picks.py`` ``int(row["odds"])`` chokes on the ``+``-prefixed form
    and silently reports zero profit for that row.

    Contract:
      - Accepts int, float, or string. Strips whitespace and existing sign.
      - Positive numbers get a leading ``+``.
      - Negative numbers keep their ``-``.
      - Zero renders as ``"0"`` (no sign — zero is neither plus nor minus).
      - Empty / None / unparseable input returns ``""`` (callers decide what
        to do — grader tolerates blanks, result graphic hides blank rows).

    Examples::

        normalize_american_odds(105)     -> "+105"
        normalize_american_odds(-110)    -> "-110"
        normalize_american_odds("+108")  -> "+108"
        normalize_american_odds("105")   -> "+105"
        normalize_american_odds("")      -> ""
        normalize_american_odds(None)    -> ""
    """
    if odds is None:
        return ""
    s = str(odds).strip()
    if not s:
        return ""
    # Strip any leading + so we re-derive the sign consistently.
    candidate = s.lstrip("+")
    try:
        n = int(float(candidate))
    except (TypeError, ValueError):
        return ""
    if n == 0:
        return "0"
    return f"+{n}" if n > 0 else str(n)


# ─────────────────────────────────────────────────────────────────
# Numeric + boolean normalizers (PICK_LOG_AUDIT M-3, M-10, M-11, M-12)
# ─────────────────────────────────────────────────────────────────

# Stats where is_home MUST be set to True or False. For everything else —
# props (PTS/REB/AST/SOG/etc.) and PARLAY rows — is_home is blank.
# TOTAL and F5_TOTAL intentionally excluded: they are combined-score bets where
# home/away distinction is irrelevant for grading and CLV tracking.
_IS_HOME_REQUIRED_STATS: frozenset[str] = frozenset({
    "SPREAD", "ML_FAV", "ML_DOG",
    "F5_SPREAD", "F5_ML",
    "TEAM_TOTAL",
})


def normalize_is_home(is_home, stat: str = "") -> str:
    """Canonical is_home representation: "True" | "False" | "".

    PICK_LOG_AUDIT M-3: spot-check of ``pick_log.csv`` found is_home as a mix
    of ``"True"``, ``"False"``, bare ``"1"``/``"0"``, blank, and occasionally
    ``"true"`` (lowercase, from a stray write path). grade_picks.py parses
    it with ``str(val).lower() == "true"`` which quietly treats ``"1"`` as
    False and thereby grades the wrong team.

    Contract:
      - bool True/False → "True"/"False" (Python repr).
      - "true"/"True"/"1"/"t"/"yes" → "True".
      - "false"/"False"/"0"/"f"/"no" → "False".
      - ""/None/unparseable → "" (blank — only legal for non-team stats).
      - stat arg is informational: callers that set stat to a team-based
        stat and still pass blank get a blank back (validation is a
        separate helper — this one never raises).

    Examples::

        normalize_is_home(True)        -> "True"
        normalize_is_home("1")         -> "True"
        normalize_is_home("False")     -> "False"
        normalize_is_home(0)           -> "False"
        normalize_is_home("")          -> ""
        normalize_is_home(None)        -> ""
    """
    _ = stat  # reserved for future stat-aware tightening
    if is_home is None:
        return ""
    if isinstance(is_home, bool):
        return "True" if is_home else "False"
    s = str(is_home).strip().lower()
    if not s:
        return ""
    if s in ("true", "1", "t", "yes", "y"):
        return "True"
    if s in ("false", "0", "f", "no", "n"):
        return "False"
    # Anything else (corrupt data) collapses to blank rather than inventing
    # a truth value — blank means "can't grade", which is the safer default.
    return ""


def validate_is_home_for_stat(is_home, stat: str) -> bool:
    """Return True iff is_home is legal for the given stat.

    PICK_LOG_AUDIT M-3 validator:
      - stat in _IS_HOME_REQUIRED_STATS ⇒ is_home must be "True" or "False".
      - all other stats ⇒ is_home must be blank.

    Call at write time before appending. A False return means the row is
    inconsistent and should be rejected (or at least logged loudly).
    """
    norm = normalize_is_home(is_home, stat)
    stat_up = (stat or "").strip().upper()
    if stat_up in _IS_HOME_REQUIRED_STATS:
        return norm in ("True", "False")
    # Non-team stats: blank is the only legal value.
    return norm == ""


def normalize_size(size) -> str:
    """Canonical size string: always 2 decimals ("0.50", "1.00", "2.50").

    PICK_LOG_AUDIT M-10: the log mixed "0.5" and "0.50" for the same value.
    ``float()`` readers don't care, but string-sorting / grouping and the
    xlsx recap's formatting both break when the same underlying number is
    spelled two ways.

    Contract:
      - int/float/numeric-string → ``f"{n:.2f}"``.
      - ""/None/garbage → "".
      - Never raises.
    """
    if size is None:
        return ""
    s = str(size).strip()
    if not s:
        return ""
    try:
        n = float(s)
    except (TypeError, ValueError):
        return ""
    return f"{n:.2f}"


def normalize_proj(proj) -> str:
    """Canonical proj string: always 2 decimals.

    PICK_LOG_AUDIT M-11: some rows carry 4-decimal projections (``22.3917``)
    and some carry 1-decimal (``22.4``). Cosmetic but annoying — the xlsx
    recap's column width shifts per row and analyze_picks's rounding
    bucket boundaries misbehave.

    Blank input → blank (daily_lay PARLAY rows have no proj).
    """
    if proj is None:
        return ""
    s = str(proj).strip()
    if not s:
        return ""
    try:
        n = float(s)
    except (TypeError, ValueError):
        return ""
    return f"{n:.2f}"


def normalize_edge(edge) -> str:
    """Canonical edge string: decimal form, 4 decimals (``0.0500`` = 5%).

    PICK_LOG_AUDIT M-12: every current row is already decimal, but the
    writer previously allowed bare floats of varying precision. Locking
    to 4 decimals means downstream consumers can always do
    ``float(row["edge"])`` without losing precision on sub-percent edges.

    Display layers multiply by 100 for percentage rendering.
    """
    if edge is None:
        return ""
    s = str(edge).strip()
    if not s:
        return ""
    try:
        n = float(s)
    except (TypeError, ValueError):
        return ""
    return f"{n:.4f}"


# ─────────────────────────────────────────────────────────────────
# Schema-version sidecar (PICK_LOG_AUDIT M-13)
# ─────────────────────────────────────────────────────────────────

# Sidecar filename convention: pick_log.csv → pick_log.schema.json, etc.
# Keeps the version metadata out of the CSV body so pandas/csv.DictReader
# don't need a special leading-comment skip.
def schema_sidecar_path(csv_path) -> Path:
    """Return the sidecar JSON path for a given pick_log CSV.

    ``data/pick_log.csv``         -> ``data/pick_log.schema.json``
    ``data/pick_log_manual.csv``  -> ``data/pick_log_manual.schema.json``
    ``data/pick_log_mlb.csv``     -> ``data/pick_log_mlb.schema.json``
    """
    p = Path(csv_path)
    # Swap ``.csv`` for ``.schema.json`` — use with_name to avoid double suffix.
    return p.with_name(p.stem + ".schema.json")


def write_schema_sidecar(csv_path) -> None:
    """Write a sidecar JSON recording the current SCHEMA_VERSION + header.

    PICK_LOG_AUDIT M-13 fix — without a version marker, future schema bumps
    have no way to tell v1 rows from v2 rows except by column sniffing.

    Writes atomically (tmp + fsync + replace) so a crash mid-write leaves
    either the old sidecar or the new one, never a partial file.
    """
    import json
    import os
    from pathlib import Path

    p = schema_sidecar_path(csv_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "canonical_header": list(CANONICAL_HEADER),
        "note": "auto-written by pick_log_schema.write_schema_sidecar — "
                "do not hand-edit. Sidecar lets tools verify the on-disk "
                "schema without sniffing the CSV header.",
    }
    tmp = p.with_suffix(p.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except Exception:
        # Don't leave orphaned .tmp files if the write fails.
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def read_schema_sidecar(csv_path) -> dict | None:
    """Read the sidecar JSON for a given CSV, or None if absent/corrupt.

    Readers can use this to decide how to interpret the rows — e.g. if the
    sidecar says v1, migrate via ``migrate_row`` before handing rows to
    downstream code.
    """
    import json
    p = schema_sidecar_path(csv_path)
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def migrate_file(csv_path, *, dry_run: bool = True, make_backup: bool = True) -> dict:
    """Migrate an on-disk pick_log CSV to the current SCHEMA_VERSION (P2.12).

    Lightweight file-level runner around migrate_row_chain(). Detects the
    on-disk version (sidecar first, header sniff as fallback), and:
      - returns ``status="absent"`` if the file doesn't exist;
      - returns ``status="current"`` (no write) if the header already matches
        CANONICAL_HEADER at SCHEMA_VERSION — so it's a safe no-op today (v4);
      - otherwise migrates every row and either reports (``dry_run=True``,
        ``status="would_migrate"``) or rewrites the file atomically
        (``status="migrated"``).

    DEFAULTS to dry_run=True — it never touches a file unless asked. On a real
    migration it writes a one-time backup (``<name>.v<old>.bak.csv``), rewrites
    via tmp+fsync+os.replace, and refreshes the schema sidecar.

    Returns a summary dict (path, status, from/to version, row count, the
    added/dropped columns) for logging / health surfacing.
    """
    import csv
    import os
    import shutil

    p = Path(csv_path)
    if not p.exists():
        return {"path": str(p), "status": "absent"}

    with open(p, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames or [])
        rows = list(reader)

    sidecar = read_schema_sidecar(p)
    on_disk_version = (sidecar or {}).get("schema_version") or detect_schema_version(header)

    if on_disk_version == SCHEMA_VERSION and header == CANONICAL_HEADER:
        return {"path": str(p), "status": "current",
                "schema_version": SCHEMA_VERSION, "rows": len(rows)}

    missing, unknown = validate_header(header)
    summary = {
        "path": str(p),
        "status": "would_migrate" if dry_run else "migrated",
        "from_version": on_disk_version,
        "to_version": SCHEMA_VERSION,
        "rows": len(rows),
        "added_columns": missing,
        "dropped_columns": unknown,
    }
    if dry_run:
        return summary

    migrated = [migrate_row_chain(r, on_disk_version, source_header=header) for r in rows]

    if make_backup:
        shutil.copy2(p, p.with_name(f"{p.stem}.v{on_disk_version}.bak{p.suffix}"))

    tmp = p.with_suffix(p.suffix + ".tmp")
    try:
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CANONICAL_HEADER, extrasaction="ignore")
            w.writeheader()
            w.writerows(migrated)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    write_schema_sidecar(p)
    return summary


def validate_manual_row(row: Mapping[str, object]) -> list[str]:
    """Return a list of required fields that are missing/blank on a manual row.

    PICK_LOG_AUDIT H-4: three of six rows in ``pick_log_manual.csv`` had
    ``book=""``. Blank book means ``display_book("")`` returns empty, the xlsx
    recap shows a blank book column, and ``analyze_picks.py`` buckets those
    rows under key ``""`` — breaking per-book ROI.

    Empty list == row is valid. A non-empty list contains the fields that
    must be filled before the row is allowed to persist.
    """
    missing: list[str] = []
    for field in MANUAL_REQUIRED_FIELDS:
        val = row.get(field, "") if row else ""
        if val is None:
            val = ""
        if str(val).strip() == "":
            missing.append(field)
    return missing


def assert_manual_row_valid(row: Mapping[str, object]) -> None:
    """Raise ``ManualRowValidationError`` if a manual-entered row is incomplete.

    Intended call site: ``run_picks.py`` ``--log-manual`` flow, right before
    the row is appended to ``pick_log_manual.csv``. Manual entries are the
    one place where a human types the row directly, so this is where bad
    data gets in. Model-generated rows bypass this check.
    """
    missing = validate_manual_row(row)
    if missing:
        raise ManualRowValidationError(
            f"manual row missing required fields: {missing}. "
            f"Provided keys: {sorted(row.keys()) if row else '[]'}"
        )


def validate_header(on_disk_header: Iterable[str] | None) -> tuple[list[str], list[str]]:
    """Compare on-disk header against CANONICAL_HEADER.

    Returns:
      (missing_columns, unknown_columns)
        missing_columns — canonical cols that aren't on disk (will be filled "")
        unknown_columns — on-disk cols that aren't canonical (will be dropped)

    Readers can use this to emit a one-time warning when an old-schema log
    is first opened, without halting the read.
    """
    if not on_disk_header:
        return list(CANONICAL_HEADER), []
    on_disk = set(on_disk_header)
    missing = [c for c in CANONICAL_HEADER if c not in on_disk]
    unknown = [c for c in on_disk_header if c not in KNOWN_COLUMNS]
    return missing, unknown


# ─────────────────────────────────────────────────────────────────
# Invariants — these protect us from accidental drift inside this module.
# ─────────────────────────────────────────────────────────────────

assert len(CANONICAL_HEADER) == len(set(CANONICAL_HEADER)), (
    "CANONICAL_HEADER has duplicate columns"
)
assert _V1_COLUMNS.issubset(KNOWN_COLUMNS), (
    "Legacy v1 columns must all be part of the canonical schema"
)
assert _V2_COLUMNS.issubset(KNOWN_COLUMNS), (
    "v2 columns must all be part of the canonical schema"
)
assert _V3_COLUMNS.issubset(KNOWN_COLUMNS), (
    "v3 columns must all be part of the canonical schema"
)
assert _V4_COLUMNS.issubset(KNOWN_COLUMNS), (
    "v4 columns must all be part of the canonical schema"
)
assert _V5_COLUMNS.issubset(KNOWN_COLUMNS), (
    "v5 columns must all be part of the canonical schema"
)


__all__ = [
    "SCHEMA_VERSION",
    "LIVE_SOURCE",
    "CANONICAL_HEADER",
    "KNOWN_COLUMNS",
    "MANUAL_REQUIRED_FIELDS",
    "ManualRowValidationError",
    "detect_schema_version",
    "migrate_row",
    "register_migration",
    "migrate_row_chain",
    "migrate_file",
    "normalize_american_odds",
    "normalize_is_home",
    "normalize_size",
    "normalize_proj",
    "normalize_edge",
    "validate_is_home_for_stat",
    "schema_sidecar_path",
    "write_schema_sidecar",
    "read_schema_sidecar",
    "validate_header",
    "validate_manual_row",
    "assert_manual_row_valid",
]
