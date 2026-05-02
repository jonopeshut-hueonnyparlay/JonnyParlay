"""Quick diagnostic: check team_def_splits avg ratio for pts."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from projections_db import get_conn

conn = get_conn()
rows = conn.execute("""
    SELECT season, position_group, stat,
           ROUND(AVG(ratio),4)  AS avg_ratio,
           ROUND(MIN(ratio),4)  AS min_ratio,
           ROUND(MAX(ratio),4)  AS max_ratio,
           COUNT(*)             AS n_teams
    FROM team_def_splits
    WHERE stat = 'pts'
    GROUP BY season, position_group, stat
    ORDER BY season, position_group
""").fetchall()

print(f"\n{'Season':<10} {'PosGrp':<8} {'AvgRatio':>10} {'Min':>8} {'Max':>8} {'N':>4}")
print("-" * 48)
for r in rows:
    d = dict(r)
    print(f"{d['season']:<10} {d['position_group']:<8} {d['avg_ratio']:>10.4f} "
          f"{d['min_ratio']:>8.4f} {d['max_ratio']:>8.4f} {d['n_teams']:>4}")

conn.close()
