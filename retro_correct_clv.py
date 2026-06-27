"""retro_correct_clv.py -- one-pass CLV de-vig correction for historical picks.

Track-B Sprint 1 (Problem 2). The live `calc_clv` compares a VIGGED entry implied
against a DE-VIGGED close, a structural ~-2.4pp bias (see capture_clv.py:1071 docstring:
"Opening side uses vigged implied"). This script recomputes a de-vigged-both-sides CLV
on the existing pick_log and writes it to data/clv_corrections.csv for analysis and as
the input the kill-rule (Sprint 3) consumes.

READ-ONLY w.r.t. pick_log.csv (file_guard protected) -- it only reads it and writes a
SEPARATE clv_corrections.csv. Reversible: delete the output file.

Entry de-vig:
  exact  : if an `entry_odds_opposite` column exists -> proportional de-vig.
  proxy  : else symmetric hold -> entry_no_vig = entry_vigged / (1 + hold),
           so clv_corrected = clv + entry_vigged * hold/(1+hold).

Usage:  python retro_correct_clv.py [--hold 0.0476]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ENGINE = _HERE / "engine"
for _p in (_HERE, _ENGINE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from paths import PICK_LOG_PATH  # noqa: E402  (canonical resolution; never the literal path)
from quant.odds import implied_prob  # noqa: E402  (single-source vig math, audit P0.6)

_OUTPUT = Path(PICK_LOG_PATH).with_name("clv_corrections.csv")
DEFAULT_HOLD = 0.0476  # standard -110/-110 two-way hold


def correct(df: pd.DataFrame, hold: float = DEFAULT_HOLD) -> pd.DataFrame:
    """Add clv_corrected (de-vigged entry). Exact if entry_odds_opposite present, else proxy."""
    df = df.copy()
    odds = pd.to_numeric(df["odds"], errors="coerce")
    df["clv"] = pd.to_numeric(df["clv"], errors="coerce")
    entry_vigged = odds.map(lambda o: implied_prob(o) if pd.notna(o) else np.nan)

    if "entry_odds_opposite" in df.columns:
        opp = pd.to_numeric(df["entry_odds_opposite"], errors="coerce")
        opp_vig = opp.map(lambda o: implied_prob(o) if pd.notna(o) else np.nan)
        exact = entry_vigged / (entry_vigged + opp_vig)            # proportional de-vig
        proxy = entry_vigged / (1.0 + hold)
        entry_no_vig = exact.where(opp_vig.notna(), proxy)
    else:
        entry_no_vig = entry_vigged / (1.0 + hold)                 # symmetric proxy

    df["entry_vigged"] = entry_vigged
    df["clv_corrected"] = df["clv"] + (entry_vigged - entry_no_vig)
    return df


def _summary(df: pd.DataFrame, hold: float) -> None:
    g = df[df["clv"].notna()]
    print(f"rows with CLV: {len(g)}")
    print(f"  raw       mean={g['clv'].mean():+.4f}  positive={(g['clv']>0).mean():.0%}")
    c = correct(g, hold)
    print(f"  corrected mean={c['clv_corrected'].mean():+.4f}  positive={(c['clv_corrected']>0).mean():.0%}  (hold={hold:.2%})")
    print("\nsensitivity:")
    for h in (0.040, 0.0476, 0.055, 0.065):
        cc = correct(g, h)["clv_corrected"]
        print(f"  hold={h:.2%}  mean={cc.mean():+.4f}  positive={(cc>0).mean():.0%}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hold", type=float, default=DEFAULT_HOLD)
    args = ap.parse_args()

    df = pd.read_csv(PICK_LOG_PATH)
    graded = df[df["result"].isin(["W", "L"])].copy()
    _summary(graded, args.hold)

    out = correct(graded, args.hold)
    cols = [c for c in ("date", "sport", "player", "stat", "line", "direction",
                        "odds", "result", "clv", "clv_corrected") if c in out.columns]
    out[cols].to_csv(_OUTPUT, index=False)
    print(f"\nwrote {_OUTPUT.name} ({out['clv_corrected'].notna().sum()} corrected rows)")


if __name__ == "__main__":
    main()
