import sys
sys.path.insert(0, 'engine')
from run_picks import run_context_check, run_pregame_scan
from datetime import datetime

today = datetime.now().strftime('%Y-%m-%d')

picks = [
    {'sport': 'NBA', 'player': 'Devin Booker',  'stat': 'PTS', 'line': 25.5, 'direction': 'over', 'game': 'Golden State Warriors @ Phoenix Suns'},
    {'sport': 'NBA', 'player': 'LaMelo Ball',    'stat': '3PM', 'line': 4.5,  'direction': 'over', 'game': 'Charlotte Hornets @ Orlando Magic'},
    {'sport': 'NBA', 'player': 'Paolo Banchero', 'stat': 'PTS', 'line': 22.5, 'direction': 'over', 'game': 'Charlotte Hornets @ Orlando Magic'},
    {'sport': 'NBA', 'player': 'Jalen Green',    'stat': 'PTS', 'line': 18.5, 'direction': 'over', 'game': 'Golden State Warriors @ Phoenix Suns'},
    {'sport': 'NBA', 'player': 'Stephen Curry',  'stat': 'PTS', 'line': 26.5, 'direction': 'over', 'game': 'Golden State Warriors @ Phoenix Suns'},
]

# Step 1: pre-scan injury/lineup news
sports = list({p['sport'] for p in picks})
print(f"--- Pregame scan ({today}) ---")
bulletins = run_pregame_scan(sports, today)
for sport, text in bulletins.items():
    snippet = text[:150].replace('\n', ' ') if text else '(empty)'
    print(f"  [{sport}] {snippet}...")

# Step 2: individual sanity checks
print(f"\n--- Sanity checks ---")
print(f"{'Player':<22} {'Stat':<5} {'Verdict':<10}  Reason")
print("-" * 65)
for p in picks:
    notes = bulletins.get(p['sport'], '')
    verdict, reason, score = run_context_check(p, today, pregame_notes=notes)
    icon = {'conflicts': '❌ CUT', 'supports': '✅ GOOD', 'neutral': '—  PASS'}.get(verdict, '—  PASS')
    print(f"{p['player']:<22} {p['stat']:<5} {icon:<12}  {reason}")
