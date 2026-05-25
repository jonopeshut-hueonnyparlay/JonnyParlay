import csv
from collections import defaultdict

path = "C:/Users/jono4/Documents/JonnyParlay/data/pick_log.csv"
out_path = "C:/Users/jono4/Documents/JonnyParlay/docs/research/EMPIRICAL_ANALYSIS_2026-05-24.md"

rows = []
with open(path, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get('result') not in ('W', 'L'):
            continue
        if row.get('run_type') not in ('primary', 'bonus'):
            continue
        rows.append(row)

def wp(row):
    v = row.get('win_prob', '')
    return float(v) if v else None

def won(row):
    return row['result'] == 'W'

def size_val(row):
    v = row.get('size', '')
    return float(v) if v else 0

def odds_val(row):
    v = row.get('odds', '')
    return float(v) if v else None

def be_wr(avg_odds):
    if avg_odds is None:
        return None
    if avg_odds < 0:
        return abs(avg_odds) / (abs(avg_odds) + 100) * 100
    return 100 / (avg_odds + 100) * 100

def summarize(groups, min_n=3):
    out = []
    for key, rws in sorted(groups.items(), key=lambda x: -len(x[1])):
        n = len(rws)
        if n < min_n:
            continue
        wins = sum(1 for r in rws if won(r))
        wr = wins / n * 100
        wps = [wp(r) for r in rws if wp(r) is not None]
        avg_wp = sum(wps) / len(wps) * 100 if wps else 0
        units = sum((size_val(r) if won(r) else -size_val(r)) for r in rws)
        gap = wr - avg_wp
        out.append({
            'key': key, 'n': n, 'wins': wins, 'wr': wr,
            'avg_wp': avg_wp, 'gap': gap, 'units': units
        })
    return out

lines = []
lines.append("# Empirical Analysis — 2026-05-24")
lines.append(f"*n={len(rows)} qualifying graded picks (primary + bonus, W/L only)*\n")

# 1. Stat + direction
groups = defaultdict(list)
for r in rows:
    groups[(r['stat'], r['direction'])].append(r)
lines.append("## 1. Win Rate by Stat + Direction (n≥5)")
lines.append("| Stat+Dir | n | W | WR% | ModelWP% | Gap | Units |")
lines.append("|---------|---|---|-----|---------|-----|-------|")
for row in summarize(groups, min_n=5):
    k = f"{row['key'][0]} {row['key'][1]}"
    lines.append(f"| {k} | {row['n']} | {row['wins']} | {row['wr']:.1f}% | {row['avg_wp']:.1f}% | {row['gap']:+.1f}pp | {row['units']:+.2f}u |")

# 2. WP buckets
def wp_bucket(r):
    w = wp(r)
    if w is None:
        return None
    if w < 0.55: return "0.50-0.55"
    if w < 0.60: return "0.55-0.60"
    if w < 0.65: return "0.60-0.65"
    if w < 0.70: return "0.65-0.70"
    if w < 0.80: return "0.70-0.80"
    return "0.80+"

groups2 = defaultdict(list)
for r in rows:
    b = wp_bucket(r)
    if b:
        groups2[b].append(r)

lines.append("\n## 2. Win Rate by WP Bucket")
lines.append("| Bucket | n | W | WR% | AvgModelWP% | Gap |  Units |")
lines.append("|--------|---|---|-----|------------|-----|--------|")
for key in ["0.50-0.55", "0.55-0.60", "0.60-0.65", "0.65-0.70", "0.70-0.80", "0.80+"]:
    rws = groups2.get(key, [])
    if not rws:
        continue
    n = len(rws)
    wins = sum(1 for r in rws if won(r))
    wr = wins / n * 100
    wps = [wp(r) for r in rws if wp(r) is not None]
    avg_wp = sum(wps) / len(wps) * 100 if wps else 0
    units = sum((size_val(r) if won(r) else -size_val(r)) for r in rws)
    lines.append(f"| {key} | {n} | {wins} | {wr:.1f}% | {avg_wp:.1f}% | {wr-avg_wp:+.1f}pp | {units:+.2f}u |")

# 3. Tier
groups3 = defaultdict(list)
for r in rows:
    groups3[r['tier']].append(r)
lines.append("\n## 3. Win Rate by Tier")
lines.append("| Tier | n | W | WR% | AvgModelWP% | Gap | Units |")
lines.append("|------|---|---|-----|------------|-----|-------|")
for row in summarize(groups3, min_n=3):
    lines.append(f"| {row['key']} | {row['n']} | {row['wins']} | {row['wr']:.1f}% | {row['avg_wp']:.1f}% | {row['gap']:+.1f}pp | {row['units']:+.2f}u |")

# 4. Direction
groups4 = defaultdict(list)
for r in rows:
    groups4[r['direction']].append(r)
lines.append("\n## 4. Win Rate by Direction")
lines.append("| Direction | n | W | WR% | AvgModelWP% | Gap | Units |")
lines.append("|-----------|---|---|-----|------------|-----|-------|")
for row in summarize(groups4, min_n=3):
    lines.append(f"| {row['key']} | {row['n']} | {row['wins']} | {row['wr']:.1f}% | {row['avg_wp']:.1f}% | {row['gap']:+.1f}pp | {row['units']:+.2f}u |")

# 5. Sport
groups5 = defaultdict(list)
for r in rows:
    groups5[r['sport']].append(r)
lines.append("\n## 5. Win Rate by Sport")
lines.append("| Sport | n | W | WR% | AvgModelWP% | Gap | Units |")
lines.append("|-------|---|---|-----|------------|-----|-------|")
for row in summarize(groups5, min_n=3):
    lines.append(f"| {row['key']} | {row['n']} | {row['wins']} | {row['wr']:.1f}% | {row['avg_wp']:.1f}% | {row['gap']:+.1f}pp | {row['units']:+.2f}u |")

# 6. Odds bucket
def odds_bucket(r):
    o = odds_val(r)
    if o is None:
        return None
    if o <= -130: return "a_<=−130"
    if o <= -110: return "b_−129 to −110"
    if o <= -101: return "c_−109 to −101"
    if o <= 119:  return "d_+100 to +119"
    if o <= 149:  return "e_+120 to +149"
    return "f_+150+"

groups6 = defaultdict(list)
for r in rows:
    b = odds_bucket(r)
    if b:
        groups6[b].append(r)
lines.append("\n## 6. Win Rate by Odds Bucket")
lines.append("| Odds Bucket | n | WR% | BE_WR% | Units |")
lines.append("|-------------|---|-----|--------|-------|")
for key in sorted(groups6.keys()):
    rws = groups6[key]
    n = len(rws)
    wins = sum(1 for r in rws if won(r))
    wr = wins / n * 100
    oddslist = [odds_val(r) for r in rws if odds_val(r) is not None]
    avg_o = sum(oddslist) / len(oddslist) if oddslist else 0
    be = be_wr(avg_o)
    units = sum((size_val(r) if won(r) else -size_val(r)) for r in rws)
    label = key[2:]
    lines.append(f"| {label} | {n} | {wr:.1f}% | {be:.1f}% | {units:+.2f}u |")

# 7. Pick score bucket
def ps_bucket(r):
    ps = r.get('pick_score', '')
    if not ps:
        return None
    ps = float(ps)
    if ps < 30: return "a_<30"
    if ps < 40: return "b_30-40"
    if ps < 50: return "c_40-50"
    if ps < 60: return "d_50-60"
    if ps < 70: return "e_60-70"
    return "f_70+"

groups7 = defaultdict(list)
for r in rows:
    b = ps_bucket(r)
    if b:
        groups7[b].append(r)
lines.append("\n## 7. Win Rate by Pick Score Bucket (does score predict WR?)")
lines.append("| PS Bucket | n | W | WR% | Units |")
lines.append("|-----------|---|---|-----|-------|")
for key in sorted(groups7.keys()):
    rws = groups7[key]
    n = len(rws)
    wins = sum(1 for r in rws if won(r))
    wr = wins / n * 100
    units = sum((size_val(r) if won(r) else -size_val(r)) for r in rws)
    label = key[2:]
    lines.append(f"| {label} | {n} | {wins} | {wr:.1f}% | {units:+.2f}u |")

# 8a. SOG by line + direction
sog_rows = [r for r in rows if r['stat'] == 'SOG']
def sog_bucket(r):
    l = float(r['line'])
    if l <= 2.5: return "a_≤2.5"
    if l <= 3.5: return "b_2.6-3.5"
    if l <= 4.5: return "c_3.6-4.5"
    return "d_4.6+"

g8a = defaultdict(list)
for r in sog_rows:
    g8a[(sog_bucket(r), r['direction'])].append(r)
lines.append("\n## 8a. SOG by Line Bucket + Direction")
lines.append("| Bucket | Dir | n | WR% | ModelWP% | Gap | Units |")
lines.append("|--------|-----|---|-----|---------|-----|-------|")
for key in sorted(g8a.keys()):
    rws = g8a[key]
    n = len(rws)
    if n < 3: continue
    wins = sum(1 for r in rws if won(r))
    wr = wins / n * 100
    wps = [wp(r) for r in rws if wp(r) is not None]
    avg_wp = sum(wps) / len(wps) * 100 if wps else 0
    units = sum((size_val(r) if won(r) else -size_val(r)) for r in rws)
    lines.append(f"| {key[0][2:]} | {key[1]} | {n} | {wr:.1f}% | {avg_wp:.1f}% | {wr-avg_wp:+.1f}pp | {units:+.2f}u |")

# 8b. AST by line + direction
ast_rows = [r for r in rows if r['stat'] == 'AST']
def ast_bucket(r):
    l = float(r['line'])
    if l <= 2.5: return "a_≤2.5"
    if l <= 4.5: return "b_2.6-4.5"
    if l <= 6.5: return "c_4.6-6.5"
    return "d_6.6+"

g8b = defaultdict(list)
for r in ast_rows:
    g8b[(ast_bucket(r), r['direction'])].append(r)
lines.append("\n## 8b. AST by Line Bucket + Direction")
lines.append("| Bucket | Dir | n | WR% | ModelWP% | Gap | Units |")
lines.append("|--------|-----|---|-----|---------|-----|-------|")
for key in sorted(g8b.keys()):
    rws = g8b[key]
    n = len(rws)
    if n < 3: continue
    wins = sum(1 for r in rws if won(r))
    wr = wins / n * 100
    wps = [wp(r) for r in rws if wp(r) is not None]
    avg_wp = sum(wps) / len(wps) * 100 if wps else 0
    units = sum((size_val(r) if won(r) else -size_val(r)) for r in rws)
    lines.append(f"| {key[0][2:]} | {key[1]} | {n} | {wr:.1f}% | {avg_wp:.1f}% | {wr-avg_wp:+.1f}pp | {units:+.2f}u |")

# 8c. PTS by line + direction
pts_rows = [r for r in rows if r['stat'] == 'PTS']
def pts_bucket(r):
    l = float(r['line'])
    if l <= 12.5: return "a_≤12.5"
    if l <= 17.5: return "b_13-17.5"
    if l <= 22.5: return "c_18-22.5"
    return "d_23+"

g8c = defaultdict(list)
for r in pts_rows:
    g8c[(pts_bucket(r), r['direction'])].append(r)
lines.append("\n## 8c. PTS by Line Bucket + Direction")
lines.append("| Bucket | Dir | n | WR% | ModelWP% | Gap | Units |")
lines.append("|--------|-----|---|-----|---------|-----|-------|")
for key in sorted(g8c.keys()):
    rws = g8c[key]
    n = len(rws)
    if n < 3: continue
    wins = sum(1 for r in rws if won(r))
    wr = wins / n * 100
    wps = [wp(r) for r in rws if wp(r) is not None]
    avg_wp = sum(wps) / len(wps) * 100 if wps else 0
    units = sum((size_val(r) if won(r) else -size_val(r)) for r in rws)
    lines.append(f"| {key[0][2:]} | {key[1]} | {n} | {wr:.1f}% | {avg_wp:.1f}% | {wr-avg_wp:+.1f}pp | {units:+.2f}u |")

# 8d. 3PM by line + direction
tpm_rows = [r for r in rows if r['stat'] == '3PM']
def tpm_bucket(r):
    l = float(r['line'])
    if l <= 0.5: return "a_0.5"
    if l <= 1.5: return "b_1.5"
    if l <= 2.5: return "c_2.5"
    return "d_3.5+"

g8d = defaultdict(list)
for r in tpm_rows:
    g8d[(tpm_bucket(r), r['direction'])].append(r)
lines.append("\n## 8d. 3PM by Line Bucket + Direction")
lines.append("| Bucket | Dir | n | WR% | ModelWP% | Gap | Units |")
lines.append("|--------|-----|---|-----|---------|-----|-------|")
for key in sorted(g8d.keys()):
    rws = g8d[key]
    n = len(rws)
    if n < 3: continue
    wins = sum(1 for r in rws if won(r))
    wr = wins / n * 100
    wps = [wp(r) for r in rws if wp(r) is not None]
    avg_wp = sum(wps) / len(wps) * 100 if wps else 0
    units = sum((size_val(r) if won(r) else -size_val(r)) for r in rws)
    lines.append(f"| {key[0][2:]} | {key[1]} | {n} | {wr:.1f}% | {avg_wp:.1f}% | {wr-avg_wp:+.1f}pp | {units:+.2f}u |")

# 9. over_p_raw analysis
raw_rows = [r for r in rows if r.get('over_p_raw') and r['over_p_raw'].strip()]
def raw_p(r):
    raw = float(r['over_p_raw'])
    if r['direction'] == 'under':
        return 1.0 - raw
    return raw

def raw_bucket(r):
    p = raw_p(r)
    if p < 0.55: return "a_<0.55"
    if p < 0.60: return "b_0.55-0.60"
    if p < 0.65: return "c_0.60-0.65"
    if p < 0.70: return "d_0.65-0.70"
    if p < 0.80: return "e_0.70-0.80"
    return "f_0.80+"

groups9 = defaultdict(list)
for r in raw_rows:
    groups9[raw_bucket(r)].append(r)

lines.append(f"\n## 9. Pre-Platt (over_p_raw) Calibration — n={len(raw_rows)}")
lines.append("| Raw WP Bucket | n | WR% | AvgRaw% | AvgCalibrated% | Platt shift |")
lines.append("|--------------|---|-----|---------|---------------|------------|")
for key in sorted(groups9.keys()):
    rws = groups9[key]
    n = len(rws)
    if n < 3: continue
    wins = sum(1 for r in rws if won(r))
    wr = wins / n * 100
    avg_raw = sum(raw_p(r) for r in rws) / n * 100
    wps = [wp(r) for r in rws if wp(r) is not None]
    avg_cal = sum(wps) / len(wps) * 100 if wps else 0
    lines.append(f"| {key[2:]} | {n} | {wr:.1f}% | {avg_raw:.1f}% | {avg_cal:.1f}% | {avg_cal-avg_raw:+.1f}pp |")

# Pre-Platt by direction
lines.append(f"\n### 9b. Pre-Platt by Direction (n={len(raw_rows)})")
lines.append("| Direction | n | Actual WR% | Avg Raw WP% | Avg Calibrated WP% | Raw Gap | Cal Gap |")
lines.append("|-----------|---|-----------|------------|------------------|---------|---------|")
for d in ('over', 'under'):
    dr = [r for r in raw_rows if r['direction'] == d]
    if not dr: continue
    n = len(dr)
    wins = sum(1 for r in dr if won(r))
    wr = wins / n * 100
    avg_raw = sum(raw_p(r) for r in dr) / n * 100
    wps = [wp(r) for r in dr if wp(r) is not None]
    avg_cal = sum(wps) / len(wps) * 100 if wps else 0
    lines.append(f"| {d} | {n} | {wr:.1f}% | {avg_raw:.1f}% | {avg_cal:.1f}% | {wr-avg_raw:+.1f}pp | {wr-avg_cal:+.1f}pp |")

# 10. Edge buckets
def edge_bucket(r):
    e = r.get('edge', '')
    if not e: return None
    e = float(e)
    if e < 0.05: return "a_0.03-0.05"
    if e < 0.07: return "b_0.05-0.07"
    if e < 0.09: return "c_0.07-0.09"
    return "d_0.09+"

groups10b = defaultdict(list)
for r in rows:
    b = edge_bucket(r)
    if b:
        groups10b[b].append(r)
lines.append("\n## 10. Win Rate by Edge Bucket (does edge predict WR?)")
lines.append("| Edge Bucket | n | W | WR% | Units |")
lines.append("|-------------|---|---|-----|-------|")
for key in sorted(groups10b.keys()):
    rws = groups10b[key]
    n = len(rws)
    wins = sum(1 for r in rws if won(r))
    wr = wins / n * 100
    units = sum((size_val(r) if won(r) else -size_val(r)) for r in rws)
    lines.append(f"| {key[2:]} | {n} | {wins} | {wr:.1f}% | {units:+.2f}u |")

# 11. REB line breakdown
reb_rows = [r for r in rows if r['stat'] == 'REB']
def reb_bucket(r):
    l = float(r['line'])
    if l <= 4.5: return "a_≤4.5"
    if l <= 6.5: return "b_4.6-6.5"
    if l <= 8.5: return "c_6.6-8.5"
    return "d_8.6+"

g_reb = defaultdict(list)
for r in reb_rows:
    g_reb[(reb_bucket(r), r['direction'])].append(r)
lines.append("\n## 11. REB by Line + Direction")
lines.append("| Bucket | Dir | n | WR% | ModelWP% | Gap | Units |")
lines.append("|--------|-----|---|-----|---------|-----|-------|")
for key in sorted(g_reb.keys()):
    rws = g_reb[key]
    n = len(rws)
    if n < 3: continue
    wins = sum(1 for r in rws if won(r))
    wr = wins / n * 100
    wps = [wp(r) for r in rws if wp(r) is not None]
    avg_wp = sum(wps) / len(wps) * 100 if wps else 0
    units = sum((size_val(r) if won(r) else -size_val(r)) for r in rws)
    lines.append(f"| {key[0][2:]} | {key[1]} | {n} | {wr:.1f}% | {avg_wp:.1f}% | {wr-avg_wp:+.1f}pp | {units:+.2f}u |")

# 12. PRA combo
pra_rows = [r for r in rows if r['stat'] == 'PRA']
g_pra = defaultdict(list)
for r in pra_rows:
    g_pra[r['direction']].append(r)
if pra_rows:
    lines.append(f"\n## 12. PRA (combo) by Direction — n={len(pra_rows)}")
    lines.append("| Dir | n | WR% | ModelWP% | Gap | Units |")
    lines.append("|-----|---|-----|---------|-----|-------|")
    for key, rws in g_pra.items():
        n = len(rws)
        if n < 3: continue
        wins = sum(1 for r in rws if won(r))
        wr = wins / n * 100
        wps = [wp(r) for r in rws if wp(r) is not None]
        avg_wp = sum(wps) / len(wps) * 100 if wps else 0
        units = sum((size_val(r) if won(r) else -size_val(r)) for r in rws)
        lines.append(f"| {key} | {n} | {wr:.1f}% | {avg_wp:.1f}% | {wr-avg_wp:+.1f}pp | {units:+.2f}u |")

out = "\n".join(lines)
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(out)
print(f"Written: {out_path}")
print(f"Total rows analyzed: {len(rows)}")
