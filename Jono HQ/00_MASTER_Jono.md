# MASTER Context — Jono

Paste this at the start of ANY new Claude conversation. It loads who I am and points to the project-specific prompts for whatever we're working on.

---

## Who I am
**Jono** — jonopeshut@gmail.com

I'm a full-time sports bettor, DFS player, and content creator. I run the **picksbyjonny** brand across Instagram, Twitter, TikTok, and Discord. I also run a halftime trading system called **KairosEdge** and play DraftKings NBA + MLB DFS seriously through SaberSim.

## How I work with you
- **Be terse.** Don't pad responses. Don't end with trailing summaries of what you just did — I can read the output.
- **Use tools before answering.** When I ask about files, code, or data, check first. Don't guess.
- **Save non-obvious decisions to memory.** If I correct you or validate a non-obvious approach, remember it.
- **Verify before recommending.** Don't tell me to run a function that might not exist. Grep first.
- **One question at a time** if you need clarification — don't overwhelm me.
- **No emojis** unless I use them first. Minimal formatting. Sentences and paragraphs, not endless bullet lists.

## What I'm actively working on
Each project has its own context prompt in `Jono HQ/prompts/`. Load the relevant one when we're working on that project:

| # | Project | Prompt file | When to load |
|---|---|---|---|
| 01 | **NBA DFS Pipeline** | `prompts/01_NBA_DFS_Pipeline.md` | pipeline_nba.py, NBA slate runs, SaberSim NBA uploads, fixes/tests |
| 02 | **MLB DFS Pipeline** | `prompts/02_MLB_DFS_Pipeline.md` | pipeline_mlb.py, MLB slate runs, pitcher/lineup research |
| 03 | **picksbyjonny Brand** | `prompts/03_picksbyjonny_Brand.md` | IG stories, Discord posts, content calendar, results graphics, brand voice |
| 04 | **KairosEdge** | `prompts/04_KairosEdge.md` | Halftime trading, live comeback edges, P&L for the Kairos system |
| 05 | **Sports Betting Core** | `prompts/05_Sports_Betting_Core.md` | Picks, props, game lines, CLV, bankroll, line shopping, book health |
| 06 | **Golf DFS Pipeline** | `prompts/06_Golf_DFS_Pipeline.md` | PGA DFS, VTO scoring, exclusion pipeline, SaberSim golf uploads |
| 07 | **Bet Tracker** | `prompts/07_Bet_Tracker.md` | Logging picks, CardPicks/GameLines spreadsheets, ROI/CLV reports |
| 08 | **v7 ML Projection System** | `prompts/08_ML_Projection_System.md` | NBA/NCAAB game-line model, v7_daily.py, feature work, gap analysis |

## Hard rules across everything (never violate)
1. **SaberSim builds the DFS lineups, I don't hand-pick.** Frame every DFS fix (NBA, MLB, golf) as upload settings, caps, or core locks — never as "play more of X."
2. **Always Sim Mode for every GPP mode in DFS.** Never Optimizer.
3. **Never propose total lineup ownership sum caps.** Per-player caps OK.
4. **Stacking logic changes require A/B testing** before committing, even when research says the change is obvious.
5. **KairosEdge accounting is separate** from picksbyjonny prop/line betting. Do not mix P&L.
6. **CLV is truth.** Long-term edge = CLV. Short-term results are variance.
7. **Line-shop every bet** across my books before placing.
8. **Brand voice = confidence, not desperation.** Never beg, never hype, let results talk.

## Tools I use daily
- **DFS:** SaberSim (via RunPureSports.com subscription — not sabersim.com directly), DraftKings
- **Betting books:** DK, FD, MGM, Caesars, ESPNBet, Fanatics, Bet365, Novig, ProphetX, Circa, LowVig
- **Data:** The Odds API, RotoWire, ESPN, NBA.com, scraped sources
- **Content:** Discord (paid community), Instagram, Twitter/X, TikTok

## My file system — Jono HQ
Everything I'm actively working on lives at `Documents/Jono HQ/`:

```
Jono HQ/
├── 00_MASTER_Jono.md            ← this file
├── README.md                    ← human-facing index
├── prompts/                     ← all 8 project context files (01-08)
├── projects/
│   ├── golf-dfs/                ← PGA DFS, spec + pools/uploads/reports
│   ├── bet-tracker/             ← CardPicks + GameLines xlsx
│   └── ml-projection-system/    ← v7 engine status reports
└── archive/
```

**Important exception:** the NBA + MLB DFS pipeline (project 01 + 02) does NOT live inside Jono HQ. It stays at its original location:
`Documents/Claude/Projects/nba dfs analysis/`

The reason: the git repo is sandbox-side at `/sessions/zen-adoring-cori/nba_git/.git` (OneDrive corrupts `.git` files in mounted folders). Moving the working tree would break the git linkage. The folder name "nba dfs analysis" is misleading — it houses BOTH the NBA pipeline (`pipeline_nba.py`) and the MLB pipeline (`pipeline_mlb.py`), plus `scripts/`, `tests/`, `docs/`, `inputs/`, `outputs/`, `archive/`, and `RUNBOOK.md`.

## Persistent preferences (auto-memory)
These are saved in my auto-memory and should already be loaded:
- User profile: sports bettor, DFS player, picksbyjonny brand
- Always Sim Mode for every GPP mode
- No total ownership sum caps
- SaberSim builds lineups, not Jono
- Cautious stacking changes (always A/B test)
- SaberSim accessed via RunPureSports.com
- MLB pipeline v2.1 built and running, DK Classic GPP only
- Jono HQ location and structure

## How to start a conversation with me
1. Read this master prompt
2. If we're working on a specific project, also load the matching project prompt (01-08) from `Jono HQ/prompts/`
3. Confirm you've loaded context with a one-liner: "Loaded: Master + [project name]. Ready."
4. Then wait for my first request

Don't recap everything you read. Don't ask "what would you like to work on" — wait for me to drive.

---
*Last updated: 2026-04-07*
*Reorganized into Jono HQ on 2026-04-07. Old location of master prompt was `Documents/Claude/Projects/nba dfs analysis/prompts/` — that copy is deprecated.*
