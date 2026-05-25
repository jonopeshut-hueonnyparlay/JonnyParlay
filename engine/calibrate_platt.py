"""calibrate_platt.py -- Fit Platt scaling parameters for prop win_prob.

Reads settled primary/bonus picks from pick_log.csv, fits a logistic
regression on the logit(over_p) basis (standard Platt scaling), and prints
the constants to paste into run_picks.py (PLATT_A, PLATT_B).

Usage:
    python engine/calibrate_platt.py [--log PATH] [--sport NBA|NHL|all] [--force]

    --force  Bypass the H3 data gate (use during development; n<100 is noisy)

P9 Phase timeline:
    Phase 1 (49-300 picks): Platt scaling (this script)
    Phase 2 (300+ picks):   Isotonic regression (P19)

Fitting basis:
    over_p is read from the v4 pick_log column 'over_p_raw' (pre-Platt, stored
    since schema v4 / Research Brief 8).  For legacy rows that predate v4, it
    is recovered from the logged directional win_prob as a fallback:
        over bet  -> over_p = win_prob   (= already-calibrated — biased)
        under bet -> over_p = 1 - win_prob
    Calibration: cal_over_p = sigmoid(a * logit(over_p) + b)
    This is standard Platt scaling in logit-space (superior tail compression
    vs raw-probability-space — see PROBABILITY_PIPELINE_AUDIT_2026-05-24.md).
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
    """Return pre-Platt over_p for each row.

    Prefers the v4 'over_p_raw' column (schema_version=4) which stores the
    raw model output before Platt calibration.  Falls back to recovering
    over_p from the directional win_prob for legacy rows (schema v1-v3) where
    over_p_raw is blank — those rows carry already-calibrated win_probs, which
    introduces a double-calibration bias, but we keep the fallback so the
    script stays usable on old logs.
    """
    has_raw = "over_p_raw" in df.columns
    if has_raw:
        raw_vals = pd.to_numeric(df["over_p_raw"], errors="coerce")
        has_value = raw_vals.notna()
        legacy_over_p = np.where(
            df["direction"].str.lower() == "over",
            df["win_prob"].values.astype(float),
            1.0 - df["win_prob"].values.astype(float),
        )
        over_p = np.where(has_value, raw_vals.values, legacy_over_p)
        n_legacy = int((~has_value).sum())
        if n_legacy > 0:
            print(f"  NOTE: {n_legacy} legacy rows use win_prob fallback (pre-v4 schema) — "
                  "refit accuracy improves once those rows age out.")
    else:
        over_p = np.where(
            df["direction"].str.lower() == "over",
            df["win_prob"].values,
            1.0 - df["win_prob"].values,
        )
    return over_p.astype(float)




def _logit(p: np.ndarray) -> np.ndarray:
    """Logit transform with clipping to avoid log(0)."""
    p = np.clip(p, 1e-6, 1.0 - 1e-6)
    return np.log(p / (1.0 - p))


def _fit_nll_exact(over_p: np.ndarray, is_over: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Fit standard logit-space Platt: sigmoid(a * logit(over_p) + b).

    Uses logit(over_p) as the feature — this is standard Platt scaling.
    The logit transform compresses tails more aggressively than raw-probability
    input, fixing the persistent 0.70-0.80 WP over-inflation.
    """
    logit_p = _logit(over_p)

    def nll(params: list[float]) -> float:
        a, b = params
        linear = np.clip(a * logit_p + b, -30.0, 30.0)
        cal_over = sigmoid(linear)
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
    parser.add_argument("--force", action="store_true", help="Bypass H3 data gate (noisy but usable for development)")
    parser.add_argument("--native-only", action="store_true", help="Use only rows with native over_p_raw (no legacy win_prob fallback)")
    args = parser.parse_args()

    log_path = Path(args.log)
    if not log_path.exists():
        print(f"ERROR: pick_log not found at {log_path}", file=sys.stderr)
        sys.exit(1)

    df = load_settled_props(log_path, args.sport)

    # H3 gate: require ≥100 native over_p_raw rows (schema v4+) before trusting fit.
    # Legacy fallback rows use already-calibrated win_prob, introducing double-calibration
    # bias. Below 100 real rows the fit is noisy AND contaminated.
    if "over_p_raw" in df.columns:
        n_raw = int(pd.to_numeric(df["over_p_raw"], errors="coerce").notna().sum())
    else:
        n_raw = 0

    # --native-only: drop legacy rows to eliminate double-calibration bias
    if getattr(args, "native_only", False) and "over_p_raw" in df.columns:
        native_mask = pd.to_numeric(df["over_p_raw"], errors="coerce").notna()
        df = df[native_mask].copy()
        print(f"  --native-only: using {len(df)} rows with true over_p_raw (dropped {(~native_mask).sum()} legacy rows)")

    if n_raw < 100 and not args.force:
        print(f"H3 GATE: only {n_raw}/100 required over_p_raw rows — Platt refit blocked.")
        print("         Use --force to bypass (noisy fit; re-run at 100+ rows for stable coefficients).")
        print(f"         (Total settled: {len(df)}, but {n_raw} native rows)")
        sys.exit(0)
    if n_raw < 100 and args.force:
        print(f"  NOTE: --force active. Fitting on {n_raw} native rows (gate is 100). Coefficients will be noisy.")
        print(f"        Re-run without --force when n_raw >= 100 for a stable fit.")

    if len(df) < 50 and not args.force:  # L16: raised from 30 → 50; CV folds are too small below this
        print(f"WARNING: only {len(df)} settled picks -- Platt fit requires >=50 for reliable CV.")
        print("Continue anyway? [y/N] ", end="", flush=True)
        if input().strip().lower() != "y":
            sys.exit(0)

    y = (df["result"] == "W").astype(float).values
    over_p = recover_over_p(df)
    is_over = (df["direction"].str.lower() == "over").values

    a, b = _fit_nll_exact(over_p, is_over, y)

    # In-sample evaluation (biased — fit and eval on same data)
    raw_p_win = np.where(is_over, over_p, 1.0 - over_p)
    logit_p = _logit(over_p)
    logit_cal = np.clip(a * logit_p + b, -30.0, 30.0)
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
        logit_cv = np.clip(a_cv * _logit(over_p[val_idx]) + b_cv, -30.0, 30.0)
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
    print("  -- Bucket check ---------------------------------------------")
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
    # M16: hard exit when OOS Brier improvement is negative — do NOT paste bad constants
    if not (brier_oos_pct != brier_oos_pct):  # check not NaN
        if brier_oos_pct < 0:
            print("  WARNING: OOS Brier improvement is NEGATIVE -- calibration hurts out-of-sample.")
            print("  Do NOT update PLATT_A/PLATT_B.  Keep existing constants.")
            print("  Root causes: double-calibration bias, too few picks, or distribution shift.")
            sys.exit(1)
    print("  -- H3 MIGRATION — paste BOTH blocks atomically ---------------")
    print("  Step 1: update _platt_calibrate_prop() in run_picks.py:")
    print("    raw = PLATT_A * logit(over_p) + PLATT_B   # logit-space (H3)")
    print("    (remove the logit() call comments; update the space label)")
    print()
    print("  Step 2: update constants in run_picks.py:")
    print(f"    PLATT_A = {a:.4f}   # slope  (logit-space — H3)")
    print(f"    PLATT_B = {b:.4f}   # intercept  (logit-space — H3)")
    print()
    print("  ⚠  NEVER paste Step 2 without Step 1 — raw-space formula with")
    print("     logit-space constants shifts win_prob by ±12–18pp on every prop.")
    print("  ---------------------------------------------------------------")


if __name__ == "__main__":
    main()
