# CROSS-REPO INTERFACE (X-1) — EdgeModel ⇄ JonnyParlay (audit 2026-06-26)

How projections cross the boundary, and what the audit established about the contract. The
authoritative trace is finding **EM1-01** (adversarially verified) plus the EM-3 / JP-1 modules.

## The actual data path (verified, and it is NOT uniform across sports)

| Sport | EdgeModel writes | JonnyParlay reads | Verified by |
|-------|------------------|-------------------|-------------|
| **NBA** | SaberSim-style CSV (post 240-min + Vegas-anchor constraints) **and** `projections.db` (PRE-constraint values) | the **CSV** via `run_picks.py:742-768 → parse_csv` | EM1-01 verdict |
| **WNBA** | `projections.db` only (constraint applied BEFORE persist — correct order) | the **DB** via the EdgeModel DB adapter | EM1-01 verdict, wnba_projector:412-428 |
| calibration / backtest | `projections.db` projections table | `sabersim_backtest.py:129`, `calibrated.py` (offline σ reconstruction), `wnba_gate.py` (row counts) | EM1-01 verdict |

**Key correctness fact:** for NBA, `projections.db` stores *un-constrained, non-Vegas-anchored*
values because `run_projections()` upserts+commits before the 240-min constraint and
`constrain_team_totals()` run, and neither re-persists. This was filed as a High but **verified
down to Informational** because live NBA pricing reads the CSV (which is correct); only the
offline NBA backtest reads the divergent DB rows. WNBA orders it correctly. **No live-money
mispricing crosses the interface.**

> ⚠️ Latent risk to watch: if anything in the live NBA path is ever switched from the CSV to
> `EDGEMODEL_DB_PATH`, it would silently read pre-constraint numbers. Worth a one-line re-upsert
> (or constrain-before-persist, as WNBA already does) to remove the trap. Tracked as EM1-01.

## Schema contract
- `projections.db` is EdgeModel-local, anchored on `EDGEMODEL_ROOT` (never `DATA_DIR`) — matches
  CLAUDE.md. Path resolution via `EDGEMODEL_DB_PATH` env/.env.
- The WNBA write path and the JonnyParlay DB-read adapter agree on columns; no column/unit
  mismatches were found at the DB boundary in this audit.
- `dk_std` (per-player points σ) is persisted (`projections_db.py:207,2196`) and is the σ that
  flows into JonnyParlay over/under pricing — this is the carrier of the known overconfidence
  gate (EM1-02). It is a genuine *cross-repo* statistical dependency.

## Memory/doc reconciliation triggered by this trace
- CLAUDE.md states flatly "JonnyParlay reads projections.db via EDGEMODEL_DB_PATH." **True only
  for WNBA + calibration**; NBA live pricing reads the SaberSim CSV. Recommend tightening that
  line so a future change doesn't assume the DB is the NBA live source.
