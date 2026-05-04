"""calibrate_platt.py -- Fit Platt scaling parameters for prop win_prob.

Reads settled primary/bonus picks from pick_log.csv, fits a logistic
regression on the over_p basis, and prints the constants to paste into
run_picks.py (PLATT_A, PLATT_B).

Usage:
    python engine/calibrate_platt.py [--log PATH] [--sport NBA|NHL|all]

P9 Phase timeline:
    Phase 1 (76-300 picks): Platt scaling (this script)
    Phase 2 (300+ picks):   Isotonic regression (P19)

Fitting basis:
    over_p is recovered from the logged directional win_prob:
        over bet  -> over_p = win_prob
        under bet -> over_p = 1 - win_prob
    Calibration: cal_over_p = sigmoid(a * over_p + b)
    under_p derived as 1 - cal_over_p (preserves complementarity).
    Loss: negative log-likelihood of outcomes given calibrated p_win.
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit as sigmoid

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent

DEFAULT_LOG = _ROOT / "data" / "pick_log.csv"


def load_settled_props(log_path: Path, sport: str = "all") -> pd.DataFrame:
    df = pd.read_csv(log_path)
    mask = (
        df["run_type"].isin(["primary", "bonus"])
        & df["result"].isin(["W", "L"])
        & df["win_prob"].notna()
    )
    # Props only — game lines have a different distribution model
    prop_stats = {"PTS", "AST", "REB", "3PM", "SOG", "K", "OUTS", "HA", "HITS", "TB", "HRR", "REC"}
    mask &= df["stat"].isin(prop_stats)
    if sport != "all":
        mask &= df["sport"].str.upper() == sport.upper()
    return df[mask].copy()


def recover_over_p(df: pd.DataFrame) -> np.ndarray:
    """Recover over_p from logged directional win_prob."""
    over_p = np.where(
        df["direction"].str.lower() == "over",
        df["win_prob"].values,
        1.0 - df["win_prob"].values,
    )
    return over_p.astype(float)


def fit_platt(over_p: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """DEPRECATED — use _fit_nll_exact() instead (L9).

    This function approximates the bet direction via ``over_p > 0.5``,
    which is less accurate than using the actual direction flag.
    main() already calls _fit_nll_exact() correctly.
    Kept for reference; do not use in new code.
    """
    def nll(params: list[float]) -> float:
        a, b = params
        logit = np.clip(a * over_p + b, -30.0, 30.0)
        cal_over = sigmoid(logit)
        is_over = over_p > 0.5   # approximate — exact direction would need the column
        p_win = np.where(is_over, cal_over, 1.0 - cal_over)
        return -np.mean(y * np.log(p_win + 1e-15) + (1 - y) * np.log(1 - p_win + 1e-15))

    res = minimize(
        nll, x0=[1.0, 0.0], method="Nelder-Mead",
        options={"xatol": 1e-9, "fatol": 1e-9, "maxiter": 100_000},
    )
    return float(res.x[0]), float(res.x[1])


def _fit_nll_exact(over_p: np.ndarray, is_over: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Fit using exact direction flag (more accurate than over_p > 0.5 heuristic)."""
    def nll(params: list[float]) -> float:
        a, b = params
        logit = np.clip(a * over_p + b, -30.0, 30.0)
        cal_over = sigmoid(logit)
        p_win = np.where(is_over, cal_over, 1.0 - cal_over)
        return -np.mean(y * np.log(p_win + 1e-15) + (1 - y) * np.log(1 - p_win + 1e-15))

    res = minimize(
        nll, x0=[1.0, 0.0], method="Nelder-Mead",
        options={"xatol": 1e-9, "fatol": 1e-9, "maxiter": 100_000},
    )
    return float(res.x[0]), float(res.x[1])


def brier_score(p_win: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p_win - y) ** 2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Fit Platt scaling for prop win_prob")
    parser.add_argument("--log",   default=str(DEFAULT_LOG), help="Path to pick_log.csv")
    parser.add_argument("--sport", default="all", help="all | NBA | NHL | MLB")
    args = parser.parse_args()

    log_path = Path(args.log)
    if not log_path.exists():
        print(f"ERROR: pick_log not found at {log_path}", file=sys.stderr)
        sys.exit(1)

    df = load_settled_props(log_path, args.sport)
    if len(df) < 50:  # L16: raised from 30 → 50; CV folds are too small below this
        print(f"WARNING: only {len(df)} settled picks — Platt fit requires ≥50 for reliable CV.")
        print("Continue anyway? [y/N] ", end="", flush=True)
        if input().strip().lower() != "y":
            sys.exit(0)

    y = (df["result"] == "W").astype(float).values
    over_p = recover_over_p(df)
    is_over = (df["direction"].str.lower() == "over").values

    a, b = _fit_nll_exact(over_p, is_over, y)

    # In-sample evaluation (biased — fit and eval on same data)
    raw_p_win = np.where(is_over, over_p, 1.0 - over_p)
    logit_cal = np.clip(a * over_p + b, -30.0, 30.0)
    cal_over = sigmoid(logit_cal)
    cal_p_win = np.where(is_over, cal_over, 1.0 - cal_over)

    brier_raw = brier_score(raw_p_win, y)
    brier_cal = brier_score(cal_p_win, y)
    brier_pct = (brier_raw - brier_cal) / brier_raw * 100

    # H27: 5-fold cross-validated Brier to detect in-sample overfit.
    # With < 50 picks, CV folds are tiny — treat OOS Brier as indicative only.
    n = len(y)
    k_folds = 5
    fold_size = max(1, n // k_folds)
    idx = np.arange(n)
    oos_raw_scores: list[float] = []
    oos_cal_scores: list[float] = []
    for fold in range(k_folds):
        val_idx = idx[fold * fold_size: (fold + 1) * fold_size]
        if len(val_idx) == 0:
            continue
        train_idx = np.concatenate([idx[:fold * fold_size], idx[(fold + 1) * fold_size:]])
        if len(train_idx) == 0:
            continue
        a_cv, b_cv = _fit_nll_exact(over_p[train_idx], is_over[train_idx], y[train_idx])
        raw_val = np.where(is_over[val_idx], over_p[val_idx], 1.0 - over_p[val_idx])
        logit_cv = np.clip(a_cv * over_p[val_idx] + b_cv, -30.0, 30.0)
        cal_val = np.where(is_over[val_idx], sigmoid(logit_cv), 1.0 - sigmoid(logit_cv))
        oos_raw_scores.append(brier_score(raw_val, y[val_idx]))
        oos_cal_scores.append(brier_score(cal_val, y[val_idx]))
    brier_oos_raw = float(np.mean(oos_raw_scores)) if oos_raw_scores else float("nan")
    brier_oos_cal = float(np.mean(oos_cal_scores)) if oos_cal_scores else float("nan")
    brier_oos_pct = (
        (brier_oos_raw - brier_oos_cal) / brier_oos_raw * 100
        if brier_oos_raw > 0 else float("nan")
    )

    print()
    print(f"  Picks fitted:          {len(df)}  (sport={args.sport})")
    print(f"  Actual win rate:       {y.mean():.4f}")
    print(f"  Raw mean win_prob:     {raw_p_win.mean():.4f}")
    print(f"  Calibrated mean:       {cal_p_win.mean():.4f}")
    print()
    print(f"  Platt a (slope):       {a:.4f}")
    print(f"  Platt b (intercept):   {b:.4f}")
    print()
    print(f"  Brier raw (in-sample): {brier_raw:.4f}  [NOTE: in-sample, biased low]")
    print(f"  Brier cal  (in-sample):{brier_cal:.4f}  [NOTE: in-sample, biased low]")
    print(f"  Brier improvement IS:  {brier_pct:.1f}%")
    print(f"  Brier raw  (5-fold CV):{brier_oos_raw:.4f}")
    print(f"  Brier cal  (5-fold CV):{brier_oos_cal:.4f}")
    print(f"  Brier improvement OOS: {brier_oos_pct:.1f}%  <-- use this for go/no-go")
    print()
    print("  ── Bucket check ─────────────────────────────────────────")
    edges = np.array([0.55, 0.60, 0.65, 0.70, 0.75, 0.80])
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (raw_p_win >= lo) & (raw_p_win < hi)
        if mask.sum() == 0:
            continue
        print(f"  [{lo:.2f},{hi:.2f})  n={mask.sum():3d}  "
              f"actual={y[mask].mean():.3f}  "
              f"raw={raw_p_win[mask].mean():.3f}  "
              f"cal={cal_p_win[mask].mean():.3f}")
    print()
    print("  ── Paste into run_picks.py ───────────────────────────────")
    print(f"  PLATT_A = {a:.4f}   # slope")
    print(f"  PLATT_B = {b:.4f}  # intercept")
    print()
    # M16: hard exit when OOS Brier improvement is negative — do NOT paste bad constants
    if not (brier_oos_pct != brier_oos_pct):  # check not NaN
        if brier_oos_pct < 0:
            print("  ⚠  OOS Brier improvement is NEGATIVE — calibration hurts out-of-sample.")
            print("  Do NOT update PLATT_A/PLATT_B.  Keep existing constants.")
            print("  Root causes: double-calibration bias, too few picks, or distribution shift.")
            sys.exit(1)


if __name__ == "__main__":
    main()
