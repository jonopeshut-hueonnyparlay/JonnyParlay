# System Context — JonnyParlay

## Runtime Environment

| Item | Path |
|------|------|
| **Scripts folder (run from here)** | `C:\Users\jono4\Documents\JonnyParlay\` |
| **Cowork mount** | `/sessions/.../mnt/JonnyParlay/` |
| **Source of truth** | `engine/run_picks.py` (I edit here) |
| **Run target** | root `run_picks.py` (auto-synced from engine/ after every edit) |
| **Projections (SaberSim CSVs)** | `C:\Users\jono4\Downloads\projections\` |
| **Output / picks** | `C:\Users\jono4\Documents\JonnyParlay\data\picks\` |
| **Pick log** | `C:\Users\jono4\Documents\JonnyParlay\data\pick_log.csv` |
| **MLB shadow log** | `C:\Users\jono4\Documents\JonnyParlay\data\pick_log_mlb.csv` |
| **Odds cache** | `C:\Users\jono4\Documents\JonnyParlay\data\picks\cache\` |

## RETIRED
- `C:\Users\jono4\Downloads\mbp\` — old scripts folder, no longer used. Do not reference.

## Standard Run Commands

```powershell
# Normal daily run
cd C:\Users\jono4\Documents\JonnyParlay
python run_picks.py C:\Users\jono4\Downloads\projections\<CSV>.csv

# Test run (no Discord, no log, no save, includes already-started games)
python run_picks.py C:\Users\jono4\Downloads\projections\<CSV>.csv --no-discord --no-save --no-context --force

# Conservative mode (cold streak)
python run_picks.py C:\Users\jono4\Downloads\projections\<CSV>.csv --mode Conservative
```

## Edit → Deploy Workflow
1. Edit `engine/run_picks.py` (or any engine/ script) in Cowork
2. After every edit session, sync: `cp engine/run_picks.py run_picks.py` (I do this automatically)
3. User runs from `C:\Users\jono4\Documents\JonnyParlay\` — picks up the synced root copy

## Discord Webhooks (all configured in run_picks.py)
- `#premium-portfolio` → DISCORD_WEBHOOK_URL
- `#bonus-drops` → DISCORD_BONUS_WEBHOOK
- `#daily-lay` → DISCORD_ALT_PARLAY_WEBHOOK
- `#daily-recap` → DISCORD_RECAP_WEBHOOK
- `#killshot` → DISCORD_KILLSHOT_WEBHOOK

## Key Decisions (locked, do not re-ask)
- Premium tier: always 5 picks
- Bonus drop: single highest-scoring NEW pick per run, max 5/day
- CO_LEGAL_BOOKS: 18 books, `espnbet` API key → display "theScore Bet"
- Golf: fully removed, archived to archived_golf_code.py
- KILLSHOT: scaffold live, @everyone + @Killshot Alerts role ping, mutually exclusive with POTD same day
- Discord bot name: PicksByJonny on all webhooks
- Carl-bot for auto-DM (new member welcome)
