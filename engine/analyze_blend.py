"""
BLEND_ALPHA empirical CLV analysis.

Reconstructs raw model disagreement from blended proj values in pick_log.csv,
bins by quintile, and reports mean CLV per bin.

Decision thresholds:
  - CLV monotonically increases with disagreement AND n >= 50 per quintile
    → model has signal; consider raising BLEND_ALPHA
  - CLV flat across quintiles
    → model has no edge over market; keep or lower BLEND_ALPHA
  - CLV decreases with disagreement
    → model diverges from sharp money; lower BLEND_ALPHA
  - n < 50 per quintile (or < 250 total) → inconclusive; set gate at n=100

BLEND_ALPHA = 0.25 at engine/run_picks.py line 520.
Raw disagreement = abs((blended_proj - line) / 0.25)
"""

import csv
import os
import sys

BLEND_ALPHA = 0.25
GAME_LINE_STATS = {"TOTAL", "TEAM_TOTAL", "ML_FAV", "ML_DOG", "SPREAD",
                   "F5_TOTAL", "F5_SPREAD", "F5_ML"}

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
log_path = os.path.join(project_root, "data", "pick_log.csv")

with open(log_path, newline="", encoding="utf-8") as f:
    picks = list(csv.DictReader(f))

rows = []
for p in picks:
    if p.get("stat") not in GAME_LINE_STATS:
        continue
    if not p.get("proj") or not p.get("line") or not p.get("clv"):
        continue
    try:
        blended = float(p["proj"])
        line = float(p["line"])
        clv = float(p["clv"])
    except (ValueError, TypeError):
        continue
    rows.append({
        **p,
        "raw_disagreement": abs((blended - line) / BLEND_ALPHA),
        "clv_float": clv,
    })

print(f"Game-line picks with CLV: {len(rows)}")
print(f"Decision requires n >= 50 per quintile ({50 * 5} total minimum)\n")

if not rows:
    print("No qualifying rows — cannot run analysis.")
    sys.exit(0)

rows.sort(key=lambda r: r["raw_disagreement"])
n = len(rows)

print(f"{'Quintile':<10} {'Disagreement range':<26} {'Mean CLV':>10} {'CLV>0%':>8} {'n':>5}")
print("-" * 65)

prev_mean = None
monotonic = True
all_ge_50 = True

for i in range(5):
    chunk = rows[i * n // 5:(i + 1) * n // 5]
    clvs = [r["clv_float"] for r in chunk]
    if not clvs:
        continue
    mean_clv = sum(clvs) / len(clvs)
    pct_pos = sum(1 for c in clvs if c > 0) / len(clvs)
    lo = chunk[0]["raw_disagreement"]
    hi = chunk[-1]["raw_disagreement"]
    print(f"Q{i+1:<9} {lo:.2f}–{hi:.2f}{'':<14} {mean_clv:>+10.4f} {pct_pos:>8.1%} {len(clvs):>5}")

    if len(clvs) < 50:
        all_ge_50 = False
    if prev_mean is not None and mean_clv < prev_mean:
        monotonic = False
    prev_mean = mean_clv

print()
print("--- Decision ---")
if all_ge_50 and monotonic:
    print("ACTIONABLE: CLV monotonically increases and n >= 50 per quintile.")
    print("Consider raising BLEND_ALPHA or making sport-specific.")
elif all_ge_50 and not monotonic:
    print("ACTIONABLE (non-monotonic): Sufficient data but no clear signal.")
    print("CLV does not increase monotonically — keep BLEND_ALPHA as-is.")
else:
    print(f"INCONCLUSIVE: n={len(rows)} total game-line picks with CLV (need 250+).")
    print("Gate: re-evaluate at n=100 graded game-line CLV rows. No code change.")
