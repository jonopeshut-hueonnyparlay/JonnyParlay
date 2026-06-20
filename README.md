# JonnyParlay

Automated sports-betting pick engine — prices player props, SGPs, and game lines against
book odds, sizes them with fractional Kelly, and posts a daily card. Projections are
produced by the separate **EdgeModel** engine (`C:\Dev\EdgeModel`) and consumed here via
`projections.db` (`EDGEMODEL_DB_PATH`).

> New here? Read `CLAUDE.md` (authoritative project instructions) first. This README is a
> map; the detailed contracts live in `docs/` and the audit/fix-plan files.

## Data flow

```
EdgeModel  ──projections.db──▶  run_picks.py  ──prices vs book odds──▶  daily card (Discord)
                                     │
                                     ▼
                              pick_log.csv  ──▶ capture_clv.py (closing lines / CLV)
                                     │                    │
                                     ▼                    ▼
                              grade_picks.py        clv_report.py / clv_weekly_export.py
                              (W/L/P/VOID)           weekly_recap.py / gate_check.py
```

## Key entry points (`engine/`)

| Script | Role |
|---|---|
| `run_picks.py` | Daily: build + price + size + post the card. Runs `health_check.py` first (pre-run gate). |
| `grade_picks.py` | Grade logged picks against results (W/L/P/VOID). |
| `capture_clv.py` | Long-running daemon: capture closing lines → CLV (registered via Task Scheduler). |
| `weekly_recap.py` | Mon–Sun performance recap (Discord + xlsx). |
| `clv_report.py` / `clv_weekly_export.py` | CLV dashboards / weekly CSV export. |
| `gate_check.py` | Status of the open data gates (Platt refits, calibration days, etc.). |
| `health_check.py` | Invariant checks; blocks `run_picks` on failure. |

## Daily ops

- **CLV daemon**: registered once via `setup_clv_task.ps1` (Run as Administrator) → Task
  Scheduler runs `start_clv_daemon.bat` daily 10:00 + at startup. Logs rotate
  (`engine/log_setup.py`, 5 MB × 5).
- **Picks**: `python engine/run_picks.py` (see `--help`).
- **Grade**: `python engine/grade_picks.py` after games settle.

## Development

```bash
python -m pytest --basetemp=C:/Dev/JonnyParlay/.pytest_tmp -m "not network"   # test suite
python replay/run_replay.py          # determinism gate — must stay byte-identical
python -m ruff check .               # lint (blocking in CI)
python engine/health_check.py        # invariant checks
pip install pre-commit && pre-commit install   # local ruff hook (.pre-commit-config.yaml)
```

CI runs ruff + the non-network suite on every push (`.github/workflows/ci.yml`,
windows-latest). The **replay diff is the trust anchor**: any code change must reproduce a
byte-identical pick list against the `replay/snapshots/` baseline, or the change moved
pricing and needs review.

## Layout & config

- `engine/` — pricing, sizing, gating, daemons, calibration. `quant/` — pure math
  (odds, distributions, copula). `replay/` — determinism harness + snapshots.
- `paths.py` — portable path resolution (`JONNYPARLAY_HOME` / `EDGEMODEL_DB_PATH`).
- `secrets_config.py` + `.env` — webhooks / API keys.
- `thresholds.py` — tunable constants. **Frozen during correctness work** — see the
  anti-patterns in `JonnyParlay_Fix_Plan_v2.md` and the sizing/cap reference in
  `docs/staking.md`.

## Docs

- `CLAUDE.md` — project instructions (start here).
- `docs/staking.md` — sizing + unit-cap math. `docs/research/MARKET_FOUNDATIONS.md` —
  market pricing / vig / BM shrinkage. `docs/BACKLOG.md` — open ideas.
- `JonnyParlay_Fix_Plan_v2.md` + `FIX_PLAN_PROGRESS.md` — audit fix plan + execution log.
