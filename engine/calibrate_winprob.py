"""calibrate_winprob.py -- Platt scaling calibration for win_prob estimates.

Usage:
    python engine/calibrate_winprob.py [--log PATH] [--run-types primary,bonus]
                                       [--out docs/calibration/]

What this does:
    1. Loads graded picks from pick_log.csv (W/L only, with win_prob).
    2. Fits a Platt scaling model (logistic regression) on win_prob -> outcome.
    3. Plots a reliability diagram (10 equal-width bins).
    4. Reports Brier score (raw and calibrated).
    5. Optionally writes calibration coefficients to docs/calibration/.

Platt scaling formula:
    calibrated_prob = sigmoid(a * model_prob + b)
    where a and b are fitted by logistic regression on outcomes.

If a < 1.0: model is over-confident (predicts too high). Shrink toward 0.50.
If a > 1.0: model is under-confident.
Intercept b shifts the overall probability level up or down.

Phase guidance (deep research report 2026-05-01):
    - Phase 1 (now, n~76):  Platt scaling -- fit here. Reliability diagram in 10 bins.
    - Phase 2 (300+ picks): Isotonic regression -- non-parametric, more flexible.
    - Phase 3 (500+ picks): Per-sport / per-tier stratified calibration.

Tracking:
    Brier score target < 0.23 for a well-calibrated prop-picking system.
    Flag if calibration slope drifts > 10% month-over-month.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent

# ---------------------------------------------------------------------------
# Minimal sklearn-free Platt scaling via scipy (no heavy dep required)
# ---------------------------------------------------------------------------

def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def _fit_platt(model_probs: np.ndarray, outcomes: np.ndarray):
    """Fit Platt scaling via logistic regression (slope + intercept).

    Uses scipy.optimize.minimize to avoid sklearn dependency.
    Returns (a, b) where calibrated = sigmoid(a * model_prob + b).
    """
    from scipy.optimize import minimize

    def nll(params):
        a, b = params
        p = _sigmoid(a * model_probs + b)
        p = np.clip(p, 1e-9, 1 - 1e-9)
        return -np.mean(outcomes * np.log(p) + (1 - outcomes) * np.log(1 - p))

    result = minimize(nll, x0=[1.0, 0.0], method="Nelder-Mead",
                      options={"xatol": 1e-6, "fatol": 1e-6, "maxiter": 5000})
    a, b = result.x
    return float(a), float(b)


def brier_score(probs: np.ndarray, outcomes: np.ndarray) -> float:
    return float(np.mean((probs - outcomes) ** 2))


def reliability_diagram(model_probs: np.ndarray,
                        calibrated_probs: np.ndarray,
                        outcomes: np.ndarray,
                        n_bins: int = 10) -> dict:
    """Bin predictions and compute mean predicted vs. mean actual per bin."""
    bins = np.linspace(0, 1, n_bins + 1)
    raw_mean_pred, raw_mean_actual, cal_mean_pred, cal_mean_actual, counts = (
        [], [], [], [], []
    )
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (model_probs >= lo) & (model_probs < hi)
        n = mask.sum()
        counts.append(int(n))
        if n == 0:
            raw_mean_pred.append(None)
            raw_mean_actual.append(None)
            cal_mean_pred.append(None)
            cal_mean_actual.append(None)
        else:
            raw_mean_pred.append(round(float(model_probs[mask].mean()), 4))
            raw_mean_actual.append(round(float(outcomes[mask].mean()), 4))
            cal_mean_pred.append(round(float(calibrated_probs[mask].mean()), 4))
            cal_mean_actual.append(round(float(outcomes[mask].mean()), 4))
    return {
        "bin_edges": [round(float(b), 2) for b in bins],
        "raw_mean_pred": raw_mean_pred,
        "raw_mean_actual": raw_mean_actual,
        "cal_mean_pred": cal_mean_pred,
        "cal_mean_actual": cal_mean_actual,
        "counts": counts,
    }


def _text_reliability_diagram(diag: dict) -> str:
    """ASCII reliability diagram for terminal output."""
    lines = []
    lines.append("\n{:>14}  {:>5}  {:>10}  {:>8}  {:>10}  {:>8}".format(
        "Bin", "N", "Raw pred", "Actual", "Cal pred", "Cal err"))
    lines.append("-" * 70)
    edges = diag["bin_edges"]
    for i, (rp, ra, cp, ca, n) in enumerate(zip(
            diag["raw_mean_pred"], diag["raw_mean_actual"],
            diag["cal_mean_pred"], diag["cal_mean_actual"],
            diag["counts"])):
        label = "[{:.2f}, {:.2f})".format(edges[i], edges[i+1])
        if n == 0:
            lines.append("{:>14}  {:>5}  {:>10}  {:>8}  {:>10}  {:>8}".format(
                label, n, "--", "--", "--", "--"))
        else:
            cal_err = (cp - ca) if cp is not None and ca is not None else None
            err_str = "{:+.3f}".format(cal_err) if cal_err is not None else "--"
            lines.append("{:>14}  {:>5}  {:>10.3f}  {:>8.3f}  {:>10.3f}  {:>8}".format(
                label, n, rp, ra, cp, err_str))
    return "\n".join(lines)


def load_picks(log_path: Path, run_types: List[str]) -> pd.DataFrame:
    df = pd.read_csv(log_path)
    df = df[df["result"].isin(["W", "L"])].copy()
    df = df[df["run_type"].isin(run_types)].copy()
    df = df[df["win_prob"].notna()].copy()
    df["outcome"] = (df["result"] == "W").astype(float)
    return df.reset_index(drop=True)


def run_calibration(
    log_path: Path,
    run_types: List[str],
    out_dir: Path | None,
) -> dict:
    df = load_picks(log_path, run_types)
    n = len(df)
    if n < 20:
        print("ERROR: only {} graded picks with win_prob -- need >= 20 for calibration.".format(n))
        sys.exit(1)
    if n < 50:  # L16: warn that CV folds are unreliable below 50 picks
        print("WARNING: only {} picks — 5-fold CV is unreliable below 50. "
              "OOS Brier improvement should be treated as indicative only.".format(n))

    model_probs = df["win_prob"].values.astype(float)
    outcomes    = df["outcome"].values

    a, b = _fit_platt(model_probs, outcomes)
    calibrated  = _sigmoid(a * model_probs + b)

    # In-sample Brier (biased — fit and eval on same data)
    brier_raw = brier_score(model_probs, outcomes)
    brier_cal = brier_score(calibrated, outcomes)

    # H28: 5-fold cross-validated Brier to detect in-sample overfit.
    k_folds = 5
    fold_sz = max(1, n // k_folds)
    idx = np.arange(n)
    oos_raw_list: list = []
    oos_cal_list: list = []
    for fold in range(k_folds):
        val_idx = idx[fold * fold_sz: (fold + 1) * fold_sz]
        if len(val_idx) == 0:
            continue
        tr_idx = np.concatenate([idx[:fold * fold_sz], idx[(fold + 1) * fold_sz:]])
        if len(tr_idx) == 0:
            continue
        a_cv, b_cv = _fit_platt(model_probs[tr_idx], outcomes[tr_idx])
        cal_cv = _sigmoid(a_cv * model_probs[val_idx] + b_cv)
        oos_raw_list.append(brier_score(model_probs[val_idx], outcomes[val_idx]))
        oos_cal_list.append(brier_score(cal_cv, outcomes[val_idx]))
    brier_oos_raw = float(np.mean(oos_raw_list)) if oos_raw_list else float("nan")
    brier_oos_cal = float(np.mean(oos_cal_list)) if oos_cal_list else float("nan")
    brier_oos_pct = (
        (brier_oos_raw - brier_oos_cal) / brier_oos_raw * 100
        if brier_oos_raw > 0 else float("nan")
    )

    diag = reliability_diagram(model_probs, calibrated, outcomes, n_bins=10)

    overall_win_rate  = float(outcomes.mean())
    overall_mean_pred = float(model_probs.mean())
    bias              = overall_mean_pred - overall_win_rate

    result = {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "n_picks": int(n),
        "run_types": run_types,
        "overall_win_rate": round(overall_win_rate, 4),
        "overall_mean_pred": round(overall_mean_pred, 4),
        "systematic_bias_raw": round(bias, 4),
        "platt_slope_a":  round(a, 4),
        "platt_intercept_b": round(b, 4),
        "brier_score_raw": round(brier_raw, 4),
        "brier_score_calibrated": round(brier_cal, 4),
        "brier_improvement_pct": round((brier_raw - brier_cal) / brier_raw * 100, 1),
        "brier_score_raw_cv": round(brier_oos_raw, 4),
        "brier_score_cal_cv": round(brier_oos_cal, 4),
        "brier_improvement_pct_cv": round(brier_oos_pct, 1),
        "reliability_diagram": diag,
        "interpretation": _interpret(a, b, bias, brier_raw, n),
    }

    print("\n{}".format("=" * 60))
    print("Win probability calibration -- {} picks".format(n))
    print("{}".format("=" * 60))
    print("  Actual win rate:     {:.1%}".format(overall_win_rate))
    print("  Mean model win_prob: {:.1%}".format(overall_mean_pred))
    print("  Systematic bias:     {:+.4f}  ({})".format(
        bias, "over-confident" if bias > 0 else "under-confident"))
    print("\n  Platt a (slope):     {:.4f}  (1.0 = perfect calibration)".format(a))
    print("  Platt b (intercept): {:.4f}  (0.0 = no shift)".format(b))
    print("\n  Brier (raw, in-sample):   {:.4f}  [NOTE: biased low]".format(brier_raw))
    print("  Brier (cal, in-sample):   {:.4f}  [NOTE: biased low]".format(brier_cal))
    print("  Brier improvement IS:     {:.1f}%".format(result["brier_improvement_pct"]))
    print("  Brier (raw, 5-fold CV):   {:.4f}".format(brier_oos_raw))
    print("  Brier (cal, 5-fold CV):   {:.4f}".format(brier_oos_cal))
    print("  Brier improvement OOS:    {:.1f}%  <-- use this for go/no-go".format(brier_oos_pct))
    print("\n  Target: Brier < 0.23  ({})".format(
        "PASS" if brier_raw < 0.23 else "FAIL -- investigate"))
    print("\n{}".format(_text_reliability_diagram(diag)))
    print("\nInterpretation:\n{}".format(result["interpretation"]))

    # M17: hard exit when OOS Brier improvement is negative — caller must not paste new constants
    if brier_oos_pct == brier_oos_pct and brier_oos_pct < 0:  # brier_oos_pct != NaN
        print("\n  ⚠  OOS Brier improvement is NEGATIVE ({:.1f}%) — "
              "calibration hurts out-of-sample.".format(brier_oos_pct))
        print("  Do NOT update PLATT_A/PLATT_B.  Keep existing constants.")
        sys.exit(1)

    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "winprob_calibration.json"
        out_file.write_text(json.dumps(result, indent=2))
        print("\nSaved: {}".format(out_file))

    return result


def _interpret(a: float, b: float, bias: float, brier: float, n: int) -> str:
    lines = []

    if a <= 0:
        lines.append(
            "WARNING: Platt slope a={:.2f} is negative -- slope estimate is unreliable. "
            "This indicates the win_prob values are too narrowly clustered for Platt "
            "to fit a meaningful slope (selection filter truncates the distribution). "
            "Do NOT apply the Platt slope correction at this sample size. "
            "Use the bias correction only (see below).".format(a)
        )
    elif abs(a - 1.0) < 0.05 and abs(b) < 0.02:
        lines.append("Calibration is close to ideal (a~1, b~0). No urgent recalibration needed.")
    elif a < 0.80:
        lines.append(
            "Significant over-confidence (slope={:.2f}). The model assigns probabilities "
            "that are too spread from 0.5. "
            "Root cause: CV values likely still too low, or win_prob formula needs review.".format(a)
        )
    elif a < 0.95:
        lines.append(
            "Moderate over-confidence (slope={:.2f}). Apply Platt correction before using "
            "win_prob for bet sizing. Re-fit after 300+ picks for isotonic regression.".format(a)
        )
    else:
        lines.append("Calibration slope a={:.2f} is within acceptable range.".format(a))

    if abs(bias) > 0.05:
        direction = "over-predicts" if bias > 0 else "under-predicts"
        lines.append(
            "Systematic bias: model {} by {:.1%}. "
            "Actionable: shift all win_prob values by {:+.4f} as a flat "
            "correction until slope becomes estimable. "
            "Partial explanation: selection filter (only posting picks above a "
            "win_prob threshold) is expected to create upward truncation bias.".format(
                direction, abs(bias), -bias)
        )

    if brier >= 0.23:
        lines.append(
            "Brier score {:.4f} >= 0.23 target. With n={} and a narrow "
            "win_prob range, this may reflect small-sample variance. "
            "Re-evaluate at n=300 with a wider win_prob spread.".format(brier, n)
        )
    else:
        lines.append("Brier score {:.4f} is below the 0.23 target.".format(brier))

    lines.append(
        "n={}: Platt scaling is appropriate at this sample size but slope is "
        "unreliable with a truncated distribution. Upgrade to isotonic regression "
        "at n>=300. Track Brier score monthly; flag if it drifts >10pct "
        "month-over-month.".format(n)
    )
    return "  " + "\n  ".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Win probability calibration (Platt scaling)")
    ap.add_argument("--log",       default=None,
                    help="Path to pick_log.csv (default: auto-detect via paths.py)")
    ap.add_argument("--run-types", default="primary,bonus",
                    help="Comma-separated run_types to include (default: primary,bonus)")
    ap.add_argument("--out",       default=None,
                    help="Directory to write calibration JSON (default: docs/calibration/)")
    args = ap.parse_args()

    sys.path.insert(0, str(_HERE))
    try:
        from paths import PICK_LOG_PATH as PICK_LOG, PROJECT_ROOT as ROOT  # L1
        log_path = PICK_LOG if args.log is None else Path(args.log)
        out_dir  = ROOT / "docs" / "calibration" if args.out is None else Path(args.out)
    except ImportError:
        log_path = (_ROOT / "data" / "pick_log.csv") if args.log is None else Path(args.log)
        out_dir  = (_ROOT / "docs" / "calibration") if args.out is None else Path(args.out)

    run_types = [t.strip() for t in args.run_types.split(",")]
    run_calibration(log_path, run_types, out_dir)


if __name__ == "__main__":
    main()
