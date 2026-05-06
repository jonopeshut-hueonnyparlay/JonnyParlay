"""H1 audit diagnostic driver — Vegas team-total constraint vs 240-min protection.

Re-runs engine.generate_projections.run() across NBA 2025-26 playoff dates
with JONNYPARLAY_DIAG_VEGAS_VS_240=1, then aggregates the per-team JSON
sidecars under data/diagnostics/vegas_constraint_*.json into headline
metrics for the H1 fix policy decision.

Outputs a single stdout summary covering:
  - Top-5 minute-ratio distribution (post_vegas / post_240) per team-game
  - Frequency of |top-5 ratio - 1| > 0.05 (the headline number)
  - Frequency at which Vegas hit clip floor 0.80 / ceiling 1.20
  - Mean / p95 minutes lost off a 36-min reference star
  - Per-rank breakdown (rank-1..rank-5)
  - Sum-of-minutes deflation per team-game

Usage:
    python engine/diag_h1_constraint_chain.py [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--no-rerun]

The driver does not modify any persistent state — generate_projections.run()
is called with persist=False so the projections DB is untouched. The only
side effects are JSON sidecars under data/diagnostics/.

Pattern matches engine/diag_h6_pool.py / engine/diag_blowout_buckets.py.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path
from statistics import mean, median

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from paths import DATA_DIR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _percentile(values: list, q: float):
    """q in [0, 1]. Linear-interp percentile. Returns None on empty input."""
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    frac = pos - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def _date_range(start: str, end: str) -> list:
    sd = _dt.date.fromisoformat(start)
    ed = _dt.date.fromisoformat(end)
    out = []
    d = sd
    while d <= ed:
        out.append(d.isoformat())
        d += _dt.timedelta(days=1)
    return out


def _sidecar_path(game_date: str) -> Path:
    return DATA_DIR / "diagnostics" / f"vegas_constraint_{game_date}.json"


def _run_one_date(game_date: str) -> bool:
    """Re-run generate_projections for one date with vegas diag enabled.

    Returns True iff a sidecar was produced.
    """
    os.environ["JONNYPARLAY_DIAG_VEGAS_VS_240"] = "1"
    # Import inside the function so an Odds-API misconfig on import doesn't
    # tank the whole driver before we even start.
    from generate_projections import run as gp_run

    print(f"[{game_date}] re-running projections (persist=False) ...", flush=True)
    try:
        gp_run(game_date=game_date, persist=False, no_constraint=False)
    except Exception as e:
        print(f"[{game_date}] FAILED: {type(e).__name__}: {e}", flush=True)
        return False
    return _sidecar_path(game_date).exists()


def _load_sidecar(game_date: str):
    p = _sidecar_path(game_date)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception as e:
        print(f"[{game_date}] sidecar parse error: {e}", flush=True)
        return None


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _aggregate(sidecars: list) -> dict:
    """Build aggregate stats across (date, payload) sidecars."""
    n_teams = 0
    n_short_circuit = 0
    n_clip_floor_hit = 0
    n_clip_ceil_hit = 0
    n_scale_down = 0
    n_scale_up = 0

    top5_ratios = []
    top5_outside_5pct = 0
    rank_ratios = {1: [], 2: [], 3: [], 4: [], 5: []}
    star36_loss = []     # rank-1, only when ratio<1
    sum_top5_loss = []   # absolute minutes lost across top-5 (down-only)

    for _game_date, payload in sidecars:
        for _tid, rec in payload.items():
            if "raw_scale" not in rec:
                continue
            n_teams += 1
            raw = float(rec["raw_scale"])
            clipped = float(rec["clipped_scale"])
            if abs(clipped - 1.0) < 1e-4:
                n_short_circuit += 1
            if raw < 0.80:
                n_clip_floor_hit += 1
            if raw > 1.20:
                n_clip_ceil_hit += 1
            if clipped < 1.0 - 1e-4:
                n_scale_down += 1
            elif clipped > 1.0 + 1e-4:
                n_scale_up += 1

            top5_pre = rec.get("top5_min_pre", []) or []
            top5_post = rec.get("top5_min_post", []) or []
            if not top5_pre or len(top5_post) < len(top5_pre):
                continue

            pre_sum = 0.0
            post_sum = 0.0
            for i, (a, b) in enumerate(zip(top5_pre, top5_post)):
                if a > 0:
                    ratio = float(b) / float(a)
                    top5_ratios.append(ratio)
                    if abs(ratio - 1.0) > 0.05:
                        top5_outside_5pct += 1
                    rank = i + 1
                    if rank in rank_ratios:
                        rank_ratios[rank].append(ratio)
                    if rank == 1 and ratio < 1.0:
                        star36_loss.append(36.0 * (1.0 - ratio))
                pre_sum += float(a)
                post_sum += float(b)

            loss = max(0.0, pre_sum - post_sum)
            sum_top5_loss.append(loss)

    n_dates = len({d for d, _ in sidecars if _})

    return {
        "n_dates": n_dates,
        "n_teams": n_teams,
        "n_short_circuit": n_short_circuit,
        "n_clip_floor_hit": n_clip_floor_hit,
        "n_clip_ceil_hit": n_clip_ceil_hit,
        "n_scale_down": n_scale_down,
        "n_scale_up": n_scale_up,
        "top5_total_observations": len(top5_ratios),
        "top5_ratio_mean": (mean(top5_ratios) if top5_ratios else None),
        "top5_ratio_p50": (median(top5_ratios) if top5_ratios else None),
        "top5_ratio_p95": _percentile(top5_ratios, 0.95),
        "top5_ratio_min": (min(top5_ratios) if top5_ratios else None),
        "top5_outside_5pct": top5_outside_5pct,
        "rank_ratios_mean": {r: (mean(v) if v else None) for r, v in rank_ratios.items()},
        "rank_ratios_min":  {r: (min(v)  if v else None) for r, v in rank_ratios.items()},
        "star36_loss_mean": (mean(star36_loss) if star36_loss else None),
        "star36_loss_p95":  _percentile(star36_loss, 0.95),
        "sum_top5_loss_mean": (mean(sum_top5_loss) if sum_top5_loss else None),
        "sum_top5_loss_p95":  _percentile(sum_top5_loss, 0.95),
    }


def _fmt(x) -> str:
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:.4f}"
    return str(x)


def _pct(num: int, denom: int) -> str:
    if not denom:
        return "n/a"
    return f"{(num / denom * 100):.1f}%"


def _print_summary(agg: dict) -> None:
    n = agg["n_teams"] or 0
    obs = agg["top5_total_observations"] or 0

    print()
    print("=" * 64)
    print("H1 AUDIT — Vegas team-total constraint vs 240-min protection")
    print("=" * 64)
    print(f"Dates with sidecars:        {agg['n_dates']}")
    print(f"Team-game records:          {n}")
    print(f"Top-5 player observations:  {obs}")
    print("-" * 64)
    print(f"Scale-down  (clipped < 1.0):    {agg['n_scale_down']:>4}  {_pct(agg['n_scale_down'], n)}")
    print(f"Scale-up    (clipped > 1.0):    {agg['n_scale_up']:>4}  {_pct(agg['n_scale_up'], n)}")
    print(f"Short-circuit (|c-1|<eps):      {agg['n_short_circuit']:>4}  {_pct(agg['n_short_circuit'], n)}")
    print(f"Clip floor hit  (raw < 0.80):   {agg['n_clip_floor_hit']:>4}  {_pct(agg['n_clip_floor_hit'], n)}")
    print(f"Clip ceil hit  (raw > 1.20):    {agg['n_clip_ceil_hit']:>4}  {_pct(agg['n_clip_ceil_hit'], n)}")
    print("-" * 64)
    print("Top-5 minute ratio (post_vegas / post_240) distribution:")
    print(f"  mean: {_fmt(agg['top5_ratio_mean'])}   p50: {_fmt(agg['top5_ratio_p50'])}")
    print(f"  p95:  {_fmt(agg['top5_ratio_p95'])}   min: {_fmt(agg['top5_ratio_min'])}")
    print(f"|top5 ratio - 1| > 0.05:  {agg['top5_outside_5pct']:>4} of {obs}   {_pct(agg['top5_outside_5pct'], obs)}")
    print("-" * 64)
    print("Per-rank mean ratio (rank-1 = highest proj_min):")
    for r in (1, 2, 3, 4, 5):
        print(f"  rank-{r}: mean={_fmt(agg['rank_ratios_mean'].get(r))}   "
              f"min={_fmt(agg['rank_ratios_min'].get(r))}")
    print("-" * 64)
    print("36-min reference star — minutes lost (down-only):")
    print(f"  mean: {_fmt(agg['star36_loss_mean'])}   p95: {_fmt(agg['star36_loss_p95'])}")
    print("Sum top-5 minutes lost per team-game (down-only):")
    print(f"  mean: {_fmt(agg['sum_top5_loss_mean'])}   p95: {_fmt(agg['sum_top5_loss_p95'])}")
    print("=" * 64)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="H1 audit diagnostic driver")
    parser.add_argument("--start", default="2026-04-19", help="First date (inclusive)")
    parser.add_argument("--end",   default="2026-05-06", help="Last date (inclusive)")
    parser.add_argument("--no-rerun", action="store_true",
                        help="Aggregate existing sidecars only; skip generate_projections re-runs")
    args = parser.parse_args()

    dates = _date_range(args.start, args.end)
    print(f"H1 diag: {len(dates)} dates  {args.start} .. {args.end}", flush=True)

    if not args.no_rerun:
        for d in dates:
            _run_one_date(d)

    sidecars = []
    for d in dates:
        payload = _load_sidecar(d)
        if payload:
            sidecars.append((d, payload))
        else:
            print(f"[{d}] no sidecar found", flush=True)

    if not sidecars:
        print("No sidecars to aggregate.  Run without --no-rerun, or check the date range.")
        return

    agg = _aggregate(sidecars)
    _print_summary(agg)


if __name__ == "__main__":
    main()
