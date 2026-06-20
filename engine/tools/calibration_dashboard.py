#!/usr/bin/env python3
"""calibration_dashboard.py — rolling reliability per stat (audit S4d-X).

Read-only calibration view: bins graded prop picks by predicted `win_prob` and compares
to the observed win rate, **per stat** and overall, over a look-back window. Surfaces
which markets are miscalibrated (and in which direction) as the calibration log accrues.
A bin is flagged when its miss is statistically significant (|obs−pred| > 2·binomial-SE)
AND it has enough volume (n ≥ min-n) — the same advisory rule as health_check §20 (P2.5),
just sliced per stat and rendered as a table. No pricing/threshold touch.

Usage:
    python engine/tools/calibration_dashboard.py
    python engine/tools/calibration_dashboard.py --days 60 --min-n 20
    python engine/tools/calibration_dashboard.py --stat PTS
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

_ENGINE = Path(__file__).resolve().parents[1]
if str(_ENGINE) not in sys.path:
    sys.path.insert(0, str(_ENGINE))

# win_prob buckets — match health_check §20 so the dashboard and the smoke test agree.
RELI_BUCKETS = [
    (0.0, 0.55, "50-55%"), (0.55, 0.60, "55-60%"), (0.60, 0.65, "60-65%"),
    (0.65, 0.70, "65-70%"), (0.70, 1.01, "70%+"),
]
DEFAULT_MIN_N = 30


def bin_reliability(picks: list[dict], buckets=RELI_BUCKETS, min_n: int = DEFAULT_MIN_N) -> list[dict]:
    """Bin graded prop picks (result W/L, 0<win_prob<1) and return per-bucket metrics.

    Each entry: label, n, pred, obs, gap (obs−pred), significant (|gap|>2·SE AND n≥min_n).
    Non-props (win_prob 0), ungraded (P/VOID/blank), and unparseable rows are excluded.
    """
    acc = {lbl: {"n": 0, "wins": 0, "pred_sum": 0.0} for _, _, lbl in buckets}
    for p in picks:
        res = (p.get("result") or "").strip().upper()
        if res not in ("W", "L"):
            continue
        try:
            wp = float(p.get("win_prob") or 0)
        except (TypeError, ValueError):
            continue
        if not (0.0 < wp < 1.0):
            continue
        for lo, hi, lbl in buckets:
            if lo <= wp < hi:
                b = acc[lbl]
                b["n"] += 1
                b["wins"] += 1 if res == "W" else 0
                b["pred_sum"] += wp
                break
    out = []
    for _, _, lbl in buckets:
        b = acc[lbl]
        if b["n"] == 0:
            out.append({"label": lbl, "n": 0, "pred": None, "obs": None,
                        "gap": None, "significant": False})
            continue
        pred = b["pred_sum"] / b["n"]
        obs = b["wins"] / b["n"]
        se = (pred * (1.0 - pred) / b["n"]) ** 0.5
        out.append({"label": lbl, "n": b["n"], "pred": pred, "obs": obs,
                    "gap": obs - pred,
                    "significant": b["n"] >= min_n and abs(obs - pred) > 2 * se})
    return out


def per_stat_reliability(picks: list[dict], buckets=RELI_BUCKETS,
                         min_n: int = DEFAULT_MIN_N) -> dict[str, list[dict]]:
    """{stat: bin_reliability(...)} for each stat present (graded props only)."""
    by_stat: dict[str, list[dict]] = defaultdict(list)
    for p in picks:
        by_stat[(p.get("stat") or "?").upper()].append(p)
    return {stat: bin_reliability(ps, buckets, min_n) for stat, ps in sorted(by_stat.items())}


def _print_table(title: str, bins: list[dict]) -> None:
    rows = [b for b in bins if b["n"] > 0]
    if not rows:
        return
    print(f"\n{title}")
    print(f"  {'bucket':<8}{'n':>5}{'pred':>8}{'obs':>8}{'gap':>8}  flag")
    for b in rows:
        flag = "  <-- drift >2sigma" if b["significant"] else ""
        print(f"  {b['label']:<8}{b['n']:>5}{b['pred']:>7.1%}{b['obs']:>8.1%}"
              f"{b['gap']:>+8.1%}{flag}")


def main():
    from paths import PICK_LOG_PATH  # noqa: E402
    from pick_log_io import load_rows  # noqa: E402

    ap = argparse.ArgumentParser(description="Rolling reliability per stat (calibration drift)")
    ap.add_argument("--days", type=int, default=90, help="look-back window (default 90)")
    ap.add_argument("--stat", help="filter to one stat")
    ap.add_argument("--min-n", type=int, default=DEFAULT_MIN_N, help="min n to flag a bucket")
    args = ap.parse_args()

    cutoff = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")
    picks = load_rows([PICK_LOG_PATH], since=cutoff, graded_only=True,
                      exclude_run_types=["daily_lay", "sgp", "longshot"],
                      exclude_stats=["PARLAY"])
    if args.stat:
        picks = [p for p in picks if (p.get("stat") or "").upper() == args.stat.upper()]

    print(f"Calibration reliability — last {args.days}d "
          f"({sum(1 for p in picks if (p.get('result') or '').upper() in ('W', 'L'))} graded props)")
    _print_table("OVERALL", bin_reliability(picks, min_n=args.min_n))
    for stat, bins in per_stat_reliability(picks, min_n=args.min_n).items():
        _print_table(f"{stat}", bins)
    print("\n(advisory — drift flags = under-sampled or genuinely miscalibrated; "
          "investigate, do not auto-tune)")


if __name__ == "__main__":
    main()
