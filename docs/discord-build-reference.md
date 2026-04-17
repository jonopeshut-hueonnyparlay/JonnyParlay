# Discord Build Reference — Phase 2
### picksbyjonny · edge > everything

**Purpose:** Everything you need to execute the manual Discord server build. Print this or keep it open alongside Discord. Work top to bottom.

---

## FINAL SIDEBAR (What you're building toward)

```
WELCOME
  # welcome          ← Pit Boss auto-greet channel (bot join messages)
  # start-here       ← read-only, 2 pinned messages (welcome content + Jono's intro)
  # announcements    ← read-only

PICKS
  # premium-portfolio  ← webhook-only (bot posts)
  # bonus-drops        ← webhook-only (bot posts)
  # daily-lay         ← webhook-only (bot posts)
  # killshot           ← webhook-only (bot posts) 🔒 LOCKED

RESULTS
  # daily-recap        ← webhook-only (bot posts)
  # monthly-tracker    ← read-only (mods post)
  # winning-slips      ← open (members post)

COMMUNITY
  # general
  # questions
  # community-picks
  # testimonials
  🔊 gaming

RESOURCES
  # glossary           ← read-only (pinned post)
  # sports-news        ← bot-only (NEWS-ALERTS-B)
  # affiliates         ← read-only

MODS  (hidden from @everyone)
  # mods
  # modlog

ARCHIVE ▸ (collapsed)
  ... (all old channels)
```

---

## STEP 1 — Create New Channels

Do this first so you have targets to work with.

| Create channel | In category | Type |
|---|---|---|
| `start-here` | WELCOME | Text |
| `premium-portfolio` | PICKS | Text |
| `bonus-drops` | PICKS | Text |
| `daily-lay` | PICKS | Text |
| `killshot` | PICKS | Text |
| `daily-recap` | RESULTS | Text |

Also create a new **RESOURCES** category (doesn't exist yet).
Also create a **MODS** category if mods aren't already in a hidden private category.

---

## STEP 2 — Rename Existing Channels (Remove All Emojis)

Right-click channel → Edit Channel → change the name.

| Current name | New name |
|---|---|
| 💛 WELCOME (or similar) | `welcome` (keep as Pit Boss join channel — no rename needed if it's already clean) |
| announcements- 🎺 | `announcements` |
| winning-slips- 🏆 | `winning-slips` |
| monthly-tracker- 📊 | `monthly-tracker` |
| questions- ❓ | `questions` |
| sports-chat- 💬 | `general` |
| community-picks 🟢 | `community-picks` |
| testimonials- 📋 | `testimonials` |
| affiliates- 🧑‍🤝‍🧑 | `affiliates` |
| glossary- 📓 | `glossary` |
| gaming- 🎮 | `gaming` |
| daily-card- 💸 | `daily-card` (leave name, just move to ARCHIVE) |

Also rename categories:
- "START HERE" → `WELCOME`

---

## STEP 3 — Move Channels to Correct Categories

Drag channels into place:

| Channel | Move to |
|---|---|
| `glossary` | RESOURCES |
| `sports-news` | RESOURCES (KEEP bot active — do NOT archive) |
| `affiliates` | RESOURCES |
| `mods` | MODS (hidden) |
| `modlog` | MODS (hidden) |
| `daily-card` | ARCHIVE |
| `how-to-use-this-server` | ARCHIVE |
| `about-me` | ARCHIVE |
| `community-rules` | ARCHIVE |
| `help-desk` | ARCHIVE |

---

## STEP 4 — Order Channels Within Each Category

Drag into this exact order top-to-bottom:

**WELCOME:** welcome → start-here → announcements

**PICKS:** premium-portfolio → bonus-drops → daily-lay → killshot

**RESULTS:** daily-recap → monthly-tracker → winning-slips

**COMMUNITY:** general → questions → community-picks → testimonials → gaming (voice)

**RESOURCES:** glossary → sports-news → affiliates

---

## STEP 5 — Set Permissions

### Locked (read-only) — @everyone can VIEW but NOT send messages

Go to: Edit Channel → Permissions → @everyone → toggle Send Messages to ❌

Apply to all of these:
- `welcome` (Pit Boss join channel — lock sending so only the bot posts)
- `start-here`
- `announcements`
- `premium-portfolio`
- `bonus-drops`
- `daily-lay`
- `killshot`
- `daily-recap`
- `monthly-tracker`
- `glossary`
- `affiliates`

**For the PICKS channels (premium-portfolio, bonus-drops, daily-lay, killshot, daily-recap):** Also make sure Create Public Threads ❌ and Create Private Threads ❌. Reactions ✅ (let members react to picks).

### Open — @everyone can VIEW and SEND (default, no changes needed)
- `general`
- `questions`
- `community-picks`
- `testimonials`
- `winning-slips`
- `gaming` (voice)

### Hidden — @everyone CANNOT VIEW
- MODS category: set @everyone → View Channel ❌
- Then add your Mods role → View Channel ✅

---

## STEP 6 — Set Channel Topics

Right-click channel → Edit Channel → Topic field.

| Channel | Topic |
|---|---|
| `welcome` | New member greetings. |
| `start-here` | Start here. Read the pinned messages before anything else. |
| `announcements` | Major updates, new features, and milestones. |
| `premium-portfolio` | Daily Premium 5 positions · Model-driven, VAKE-sized · Bot posts only |
| `bonus-drops` | Late-market edges not on the original card · Bot posts only |
| `daily-lay` | 3-leg alt spread parlay · Model-identified mispriced lines · Bot posts only |
| `killshot` | Maximum-conviction plays · 🎯 Bot posts only · Ping @Killshot Alerts to get notified |
| `daily-recap` | Every pick graded, every result tracked · Full transparency · Bot posts only |
| `monthly-tracker` | Running P&L, win rates, and performance dashboards |
| `winning-slips` | Share your Ws — screenshots of winning tickets |
| `general` | Main chat — sports, betting, life |
| `questions` | Questions about picks, the model, or betting strategy |
| `community-picks` | Share your own plays and analysis |
| `testimonials` | Share your results and experience |
| `glossary` | Betting terms, model terminology, and key definitions |
| `sports-news` | Live sports headlines and breaking news (NEWS-ALERTS-B bot) |
| `affiliates` | Partner deals and promo codes |

---

## STEP 7 — Create Webhooks

For each channel below, do this:
1. Right-click channel → Edit Channel → Integrations → Webhooks → New Webhook
2. Name: **PicksByJonny** (capital P, capital B, capital J — exact)
3. Copy the URL immediately — paste it somewhere safe (notes app)

| Channel | Paste URL into |
|---|---|
| `premium-portfolio` | `run_picks.py` → `DISCORD_WEBHOOK_URL = "..."` |
| `bonus-drops` | `run_picks.py` → `DISCORD_BONUS_WEBHOOK = "..."` |
| `daily-lay` | `run_picks.py` → `DISCORD_ALT_PARLAY_WEBHOOK = "..."` |
| `daily-recap` | `run_picks.py` → `DISCORD_RECAP_WEBHOOK = "..."` AND `grade_picks.py` → `DISCORD_RECAP_WEBHOOK = "..."` |
| `killshot` | `run_picks.py` → `DISCORD_KILLSHOT_WEBHOOK = "..."` |

**These 5 webhook vars are already in run_picks.py waiting for URLs — just paste them in.**

The variables are near the top of the file, look like:
```python
DISCORD_WEBHOOK_URL       = ""   # → #premium-portfolio
DISCORD_BONUS_WEBHOOK     = ""   # → #bonus-drops
DISCORD_ALT_PARLAY_WEBHOOK = ""  # → #daily-lay
DISCORD_RECAP_WEBHOOK     = ""   # → #daily-recap
DISCORD_KILLSHOT_WEBHOOK  = ""   # → #killshot
```

---

## STEP 8 — Post & Pin Content

### Welcome message — post in `#start-here`, then pin it

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PICKS BY JONNY

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Model-driven sports betting.
Every pick is data-backed, VAKE-sized, and fully tracked.

I treat this like a trading business —
because that's exactly what it is.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HOW IT WORKS

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔒 #premium-portfolio
The daily card. 5 positions, model-ranked by Pick Score.
The #1 pick is the Pick of the Day (POTD).
Posted daily before first tip-off.

💎 #bonus-drops
Late-market edges that surface after the main card.
Same model, same sizing — just later timing.

🎲 #daily-lay
3-leg alt spread parlay. The model identifies mispriced alt lines
and builds one ticket daily.

🎯 #killshot
Maximum-conviction plays only. Rare. When it fires — pay attention.
Join @Killshot Alerts to get pinged.

📊 #daily-recap
Every pick graded against real box scores.
Win, loss, or push — full transparency, no hiding.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HOW TO READ A PICK

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Player (TEAM) · O/U Line STAT · Odds
Size (units) · Book · Tier · Pick Score

— Size: 1u = 1% of bankroll. Max position 1.25u.
— Tier: T1 (highest conviction) → T3 (lowest)
— Pick Score: Model confidence rating (higher = stronger edge)
— Book: Where to place the bet for best available line

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BANKROLL MANAGEMENT

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

— 1 unit = 1% of your bankroll
— Never risk more than the suggested unit size
— The model sizes bets based on edge and variance
— Losing days happen. Trust the process over sample size.

Discipline > emotion.
Capital preservation > ego.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

THE RULES

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. No sharing picks outside the server.
2. No spam, self-promo, or solicitation.
3. No money lending, no chasing, no tilt.
4. Be respectful. Disagreements are fine — toxicity isn't.
5. Don't ask "what's the pick" — check the channels.
6. Questions about the model or strategy go in #questions.

Betting is optional. Real life is not.
If it stops being fun or starts costing more than you can lose,
walk away. We bet to win — not to feel something.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

edge > everything

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### Jono's intro — post in `#start-here` as SECOND message, then pin it (below the main one)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

I'M JONO

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Profitable sports bettor and DFS guy.
I treat this like a trading business —
because that's exactly what it is.

Every pick that drops here goes through
the same model, the same gates, the same
sizing rules. No vibes. No hot takes.

If you're here, you're here to win.
Let's eat.

— Jono
```

---

### Glossary — post in `#glossary`, pin it (delete old pin first)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GLOSSARY

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

THE BASICS

Bankroll — The total amount of money set aside for betting.
Never bet money you can't afford to lose.

Unit (u) — 1u = 1% of bankroll. Standard sizing metric.
Keeps risk consistent regardless of bankroll size.

Stake — The actual dollar amount risked on a single bet.

Line — The point spread, total, or prop number set by the book.

Juice (Vig) — The book's commission, baked into the odds.
Standard juice is -110 on both sides of a market.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BET TYPES

Moneyline (ML) — Pick the straight-up winner.

Spread — Pick a team to win or lose by a specific margin.

Total (O/U) — Bet on combined points scored, over or under.

Prop — Bet on a player or team-specific stat (points, assists, etc.).

Parlay — Multiple bets combined. All must hit to win.

SGP (Same-Game Parlay) — Parlay using legs from one game.

Alt Line / Alt Spread — Adjusted version of a standard line at different odds.

Buy-to — Paying juice to move a line to a more favorable number.

Ladder — Multiple bets on the same player/market at increasing thresholds.

Longshot — A high-payout, low-probability bet.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

THE MODEL

POTD — Pick of the Day. The #1 ranked pick on the daily card.

Premium 5 — The top 5 model-ranked positions posted daily.

Bonus Drops — Additional edges found after the main card posts.

Alt Parlay — 3-leg parlay using alt spreads the model flags as mispriced.

KILLSHOT — Maximum-conviction play. Rare, high-size. When it fires, it fires.

Pick Score — Model confidence rating. Higher = stronger edge signal.

Tier (T1/T2/T3) — Conviction level.
  T1 = Strongest edge (7%+ model edge)
  T2 = Solid edge (5–7%)
  T3 = Thin but playable (3–5%)

VAKE Sizing — Volatility-Adjusted Kelly Edge.
How the model calculates unit size based on edge and variance.

Mode — The model's risk setting for the day.
  Default = Standard sizing
  Aggressive = Larger positions on high-conviction spots
  Conservative = Smaller positions, triggered by negative CLV streaks

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

THE EDGE METRICS

Edge — The difference between the model's projected probability
and the implied odds from the book. Our entire reason for betting.

+EV (Positive Expected Value) — A bet where true probability of
winning exceeds the implied probability from the odds.

CLV (Closing Line Value) — Whether we beat the closing number.
The single best predictor of long-term profit. Beating CLV
consistently means the model is identifying true edge.

Correlation — When the outcomes of two bets are linked.
The model adjusts SGP and parlay sizing for correlation.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

edge > everything

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## STEP 9 — Carl-bot: Welcome DM + Killshot Alerts Role

### Welcome DM (Carl-bot → Welcome module → DM new members)

Go to carl.gg → Welcome → DM → paste:

```
Hey, welcome to Picks By Jonny 👋

Here's what you need to know:

📌 Start in #start-here — read the pinned message. It tells you exactly how the server works, how to read a pick, and the bankroll rules.

🔒 #premium-portfolio — The daily card drops here. 5 positions, VAKE-sized, model-ranked.

💎 #bonus-drops — Extra edges after the main card. Same model, later timing.

📊 #daily-recap — Every pick graded. Full transparency.

The model does the work. You just need to be disciplined enough to follow it.

edge > everything — Jono
```

### @Killshot Alerts role

1. Create a new role called `Killshot Alerts` in Server Settings → Roles
2. Set up a Carl-bot reaction role in a channel (or use the Carl-bot dashboard)
3. Members who want KILLSHOT pings self-assign the role via reaction
4. When KILLSHOT fires, the embed pings @Killshot Alerts + @everyone

---

## STEP 10 — Final Visual Check

- [ ] Scroll sidebar top to bottom — no emojis in channel names, correct order
- [ ] Every channel has a topic set
- [ ] Locked channels show "You do not have permission to send messages" to members
- [ ] MODS channels are invisible to regular members
- [ ] ARCHIVE is collapsed
- [ ] All 5 webhook URLs are pasted into `run_picks.py`
- [ ] `daily-recap` webhook also pasted into `grade_picks.py`
- [ ] Send a test message in `#general` — confirm community channels work
- [ ] Verify The Pit Boss bot still fires on new member join (test with alt account or check bot settings)

---

## WEBHOOK URL TRACKING (fill in as you go)

| Channel | Webhook URL |
|---|---|
| premium-portfolio | |
| bonus-drops | |
| daily-lay | |
| daily-recap | |
| killshot | |

Once you have these URLs, paste them into the 5 webhook variables at the top of `run_picks.py`. That's the only code edit needed after this phase.

---

*picksbyjonny · edge > everything*
