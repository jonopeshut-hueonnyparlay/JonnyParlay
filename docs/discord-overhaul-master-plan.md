# PICKS BY JONNY — Discord Server Overhaul Master Plan

**Brand:** Luxury · Sharp · Analytical
**Tagline:** edge > everything

---

## CURRENT STATE → NEW STATE (Summary)

| Current | Problem | New |
|---------|---------|-----|
| START HERE (9 channels) | Cluttered, redundant | WELCOME (2 channels) |
| PICKS (1 channel) | Everything jammed in daily-card | PICKS (3 webhook channels) |
| RESULTS (2 channels) | No daily recap channel | RESULTS (3 channels) |
| COMMUNITY (6 channels) | Messy names, random emojis | COMMUNITY (5 channels) |
| No resources section | Glossary/affiliates buried | RESOURCES (2 channels) |
| ARCHIVE (18+ channels) | Visible, cluttered | ARCHIVE (collapsed, same) |

---

## FINAL SERVER STRUCTURE

Listed top-to-bottom exactly as they should appear in the sidebar.

---

### Category 1: WELCOME

| # | Channel Name | Type | Permissions | Topic / Description |
|---|-------------|------|-------------|---------------------|
| 1 | `welcome` | Text | Read-only (members can't post) | Welcome to Picks By Jonny. Read the pinned message to get started. |
| 2 | `announcements` | Text | Read-only (members can't post) | Major updates, new features, and milestones. |

**What to do:**
- Rename category "START HERE" → `WELCOME`
- Rename "💛 WELCOME" → `welcome` (remove emoji from name)
- Rename "announcements- 🎺" → `announcements` (remove emoji)
- **BEFORE archiving these, extract content** (see "CONTENT MIGRATION" section below):
  - `how-to-use-this-server` → best lines folded into new welcome pinned message
  - `about-me` → Jono's intro + photo become a `#about` channel OR pinned in `welcome`
  - `community-rules` → discipline/bankroll content folded into new welcome pinned
- Move to ARCHIVE: `how-to-use-this-server`, `about-me`, `community-rules`, `help-desk`
- **KEEP `sports-news`** — has NEWS-ALERTS-B bot driving engagement. Move to RESOURCES instead.
- **KEEP The Pit Boss** auto-welcome bot — works alongside new `welcome` pinned message
- Move `mods` to a hidden MODS category (or keep as-is if already private)
- Lock both channels: @everyone can read but not send messages

---

### Category 2: PICKS

| # | Channel Name | Type | Permissions | Topic / Description |
|---|-------------|------|-------------|---------------------|
| 1 | `premium-portfolio` | Text | Read-only (webhook-only) | Daily Premium 5 positions · Model-driven, VAKE-sized · Bot posts only |
| 2 | `bonus-drops` | Text | Read-only (webhook-only) | Late-market edges not on the original card · Bot posts only |
| 3 | `alt-parlay` | Text | Read-only (webhook-only) | 3-leg alt spread parlay · Model-identified mispriced lines · Bot posts only |

**What to do:**
- **CREATE** three new channels: `premium-portfolio`, `bonus-drops`, `alt-parlay`
- Move old `daily-card- 💸` to ARCHIVE (it has the old-format posts, don't delete it)
- Lock all 3 channels: @everyone can read but not send messages
- Create a webhook for each channel (instructions in Section 7 below)

---

### Category 3: RESULTS

| # | Channel Name | Type | Permissions | Topic / Description |
|---|-------------|------|-------------|---------------------|
| 1 | `daily-recap` | Text | Read-only (webhook-only) | Every pick graded, every result tracked · Full transparency · Bot posts only |
| 2 | `monthly-tracker` | Text | Read-only | Running P&L, win rates, and performance dashboards |
| 3 | `winning-slips` | Text | Open (members can post) | Share your Ws — screenshots of winning tickets |

**What to do:**
- **CREATE** `daily-recap` channel
- Rename "winning-slips- 🏆" → `winning-slips` (remove emoji)
- Rename "monthly-tracker- 📊" → `monthly-tracker` (remove emoji)
- Lock `daily-recap` and `monthly-tracker`: @everyone can read but not send
- `winning-slips` stays open for members to post
- Create a webhook for `daily-recap` (instructions in Section 7)

---

### Category 4: COMMUNITY

| # | Channel Name | Type | Permissions | Topic / Description |
|---|-------------|------|-------------|---------------------|
| 1 | `general` | Text | Open | Main chat — sports, betting, life |
| 2 | `questions` | Text | Open | Questions about picks, the model, or betting strategy |
| 3 | `community-picks` | Text | Open | Share your own plays and analysis |
| 4 | `testimonials` | Text | Open | Share your results and experience |
| 5 | `gaming` | Voice | Open | Voice chat |

**What to do:**
- Rename "sports-chat- 💬" → `general` (this becomes the main chat)
- Rename "questions- ❓" → `questions` (remove emoji)
- Rename "community-picks 🟢" → `community-picks` (remove emoji)
- Rename "testimonials- 📋" → `testimonials` (remove emoji)
- Rename "gaming- 🎮" → `gaming` (remove emoji)
- All channels stay open for members to post

---

### Category 5: RESOURCES

| # | Channel Name | Type | Permissions | Topic / Description |
|---|-------------|------|-------------|---------------------|
| 1 | `glossary` | Text | Read-only | Betting terms, model terminology, and key definitions |
| 2 | `sports-news` | Text | Bot-only | Live sports headlines and breaking news (NEWS-ALERTS-B bot) |
| 3 | `affiliates` | Text | Read-only | Partner deals and promo codes |

**What to do:**
- **CREATE** new category called `RESOURCES`
- Move `glossary` here from START HERE, rename "glossary- 📓" → `glossary`
- Move `sports-news` here from START HERE — keep the NEWS-ALERTS-B bot active
- Move `affiliates` here from COMMUNITY, rename "affiliates- 🧑‍🤝‍🧑" → `affiliates`
- Lock all three: @everyone can read but not send

---

### Category 6: MODS (Private / Hidden)

| # | Channel Name | Type | Permissions | Topic / Description |
|---|-------------|------|-------------|---------------------|
| 1 | `mods` | Text | Mods-only | Internal mod discussion |
| 2 | `modlog` | Text | Mods-only | Bot logs and moderation actions |

**What to do:**
- If these aren't already in their own hidden category, create a `MODS` category
- Set category permissions: hidden from @everyone, visible only to mod role
- Move `mods` and `modlog` here

---

### Category 7: ARCHIVE (Collapsed)

Keep everything that's already in ARCHIVE. **Add** these channels to ARCHIVE:

- `daily-card` (the old all-in-one picks channel — keep for history)
- `how-to-use-this-server`
- `about-me` (the old START HERE one)
- `community-rules`
- `help-desk`
- `sports-news`

**What to do:**
- Move all the channels listed above into ARCHIVE
- Collapse the ARCHIVE category so it's not visible by default
- Don't delete anything — just archive it

---

## CONTENT MIGRATION — DO THIS BEFORE ARCHIVING

Your old channels have valuable content. Pull this out FIRST, then archive.

### From `community-rules` → into new `welcome` pinned message
The strongest brand lines are already incorporated into the new welcome message above:
- "Discipline > emotion. Capital preservation > ego."
- "Betting is optional. Real life is not."
- "No money lending, no chasing, no tilt."
✅ Already done — these are in the new welcome pinned message.

### From `about-me` → consider keeping as `#about` OR pinning in `welcome`
Your existing about-me has your photo and intro: "I'm Jono. Profitable sports bettor/DFS guy. I treat this like a trading biz."

**Option A (recommended):** Pin a shorter version of this as a SECOND pinned message in `#welcome` (right below the main one). Keeps the personal touch without needing a separate channel.

**Option B:** Add `about` as a new channel in WELCOME category. More clicks for new members but gives the intro its own home.

**Pinned `#welcome` second message (Option A):**
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

### From `how-to-use-this-server` → archive (content is now in `welcome`)
The new welcome pinned message replaces this. Just archive the channel.

### From `glossary` → MERGE existing terms with new model terms
Already done — the new glossary content above includes your existing terms (Bankroll, Stake, Juice, Buy-to, Ladder, etc.) PLUS the model-specific terms (Pick Score, VAKE, POTD, etc.).

### From `testimonials` → KEEP as-is, don't touch the existing posts
The testimonials from Bomw, Payday47, frank, Soapyhands, Grayson are real social proof. Just remove the emoji from the channel name.

### From `winning-slips` → KEEP as-is
Active members posting Ws is exactly what you want. Just clean the name.

### From `monthly-tracker` → KEEP as-is
Your xlsx P&L drops are doing the work. Just clean the name and lock posting to mods.

### From `sports-news` → KEEP — move to RESOURCES
NEWS-ALERTS-B bot is free engagement. Don't touch it.

### From `help-desk` → archive (low activity)
Replace with: members can DM mods or post in `#questions` for support.

---

## CHANNEL NAMING RULES

- **No emojis in channel names.** Ever. Clean, professional names only.
- **All lowercase**, words separated by hyphens
- **No trailing punctuation** or decorative characters
- Examples: `premium-portfolio`, `daily-recap`, `general`

---

## WEBHOOK SETUP (Section 7)

You need **4 webhooks** total — one for each bot-posting channel:

### How to create a webhook:
1. Right-click the channel → Edit Channel
2. Go to **Integrations** → **Webhooks**
3. Click **New Webhook**
4. Name it: `picksbyjonny`
5. Copy the webhook URL
6. Paste it into the config in the code (see below)

### Webhook mapping:

| Channel | Webhook Name | Where to paste the URL |
|---------|-------------|----------------------|
| `premium-portfolio` | picksbyjonny | `run_picks.py` line ~68 → `DISCORD_WEBHOOK_URL = "..."` |
| `bonus-drops` | picksbyjonny | `run_picks.py` line ~68 → `DISCORD_WEBHOOK_URL = "..."` (same as above — premium & bonus use the same webhook var but post to the same channel currently. **See note below.**) |
| `alt-parlay` | picksbyjonny | `run_picks.py` line ~71 → `DISCORD_ALT_PARLAY_WEBHOOK = "..."` |
| `daily-recap` | picksbyjonny | `run_picks.py` line ~74 → `DISCORD_RECAP_WEBHOOK = "..."` AND `grade_picks.py` line ~28 → `DISCORD_RECAP_WEBHOOK = "..."` |

### IMPORTANT — Premium vs. Bonus webhook split:

Right now, `post_to_discord()` (Premium) and `post_extras_to_discord()` (Bonus) both use the same `DISCORD_WEBHOOK_URL`. To send them to **separate channels**, we need to add a new webhook variable. After creating the server:

1. Create webhook for `premium-portfolio` → paste URL as `DISCORD_WEBHOOK_URL`
2. Create webhook for `bonus-drops` → paste URL as a NEW variable: `DISCORD_BONUS_WEBHOOK`

**I will update run_picks.py to add `DISCORD_BONUS_WEBHOOK` and route `post_extras_to_discord()` to it.**

---

## CHANNEL PERMISSIONS CHEAT SHEET

### Locked channels (bot/webhook only):
For each locked channel, set these permissions for @everyone:
- ✅ View Channel
- ❌ Send Messages
- ❌ Create Public Threads
- ❌ Create Private Threads
- ❌ Add Reactions (optional — you might want to allow reactions so members can react to picks)

**Apply to:** `welcome`, `announcements`, `premium-portfolio`, `bonus-drops`, `alt-parlay`, `daily-recap`, `monthly-tracker`, `glossary`, `affiliates`

### Open channels (members can post):
For each open channel, keep default permissions:
- ✅ View Channel
- ✅ Send Messages
- ✅ Add Reactions

**Apply to:** `general`, `questions`, `community-picks`, `testimonials`, `winning-slips`

### Hidden channels (mods only):
- ❌ View Channel for @everyone
- ✅ View Channel for Mods role

**Apply to:** `mods`, `modlog`

---

## WELCOME CHANNEL PINNED MESSAGE

Post this in `#welcome` and **pin it**. This replaces the old welcome, how-to-use, about-me, and community-rules channels — and pulls in the strongest brand lines from your existing community-rules pinned post.

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

🎲 #alt-parlay
3-leg alt spread parlay. The model identifies mispriced alt lines
and builds one ticket daily.

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

## GLOSSARY CHANNEL CONTENT

Your existing glossary already has the basics (Bankroll, Unit, Stake, Line, Juice, EV, CLV, Buy-to, Alt line, Parlay, Longshot, SGP, Ladder, Correlation). **Don't delete it.** Replace the existing pinned message with this combined version that keeps everything you have AND adds the model-specific terms:

Post this in `#glossary` and **pin it** (delete the old pin first):

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

Pick Score — Model confidence rating. Higher = stronger edge signal.

Tier (T1/T2/T3) — Conviction level.
  T1 = Strongest edge (7%+ model edge)
  T2 = Solid edge (5-7%)
  T3 = Thin but playable (3-5%)

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

## EXECUTION CHECKLIST

Do these in order:

### Phase 1: Create new stuff
- [ ] Create category: `RESOURCES`
- [ ] Create category: `MODS` (if not already separate and hidden)
- [ ] Create channel: `premium-portfolio` in PICKS
- [ ] Create channel: `bonus-drops` in PICKS
- [ ] Create channel: `alt-parlay` in PICKS
- [ ] Create channel: `daily-recap` in RESULTS

### Phase 2: Rename channels (remove all emojis)
- [ ] "💛 WELCOME" → `welcome`
- [ ] "announcements- 🎺" → `announcements`
- [ ] "winning-slips- 🏆" → `winning-slips`
- [ ] "monthly-tracker- 📊" → `monthly-tracker`
- [ ] "questions- ❓" → `questions`
- [ ] "sports-chat- 💬" → `general`
- [ ] "community-picks 🟢" → `community-picks`
- [ ] "testimonials- 📋" → `testimonials`
- [ ] "affiliates- 🧑‍🤝‍🧑" → `affiliates`
- [ ] "glossary- 📓" → `glossary`
- [ ] "gaming- 🎮" → `gaming`

### Phase 3: Rename categories
- [ ] "START HERE" → `WELCOME`
- [ ] Keep `PICKS`, `RESULTS`, `COMMUNITY`, `ARCHIVE` as-is

### Phase 4: Move channels to correct categories
- [ ] Move `glossary` → RESOURCES
- [ ] Move `sports-news` → RESOURCES (KEEP — bot active)
- [ ] Move `affiliates` → RESOURCES
- [ ] Move `mods` → MODS (hidden)
- [ ] Move `modlog` → MODS (hidden)
- [ ] Move `daily-card- 💸` → ARCHIVE
- [ ] Move `how-to-use-this-server` → ARCHIVE (after extracting content)
- [ ] Move `about-me` → ARCHIVE (after extracting Jono's intro)
- [ ] Move `community-rules` → ARCHIVE (after extracting brand lines)
- [ ] Move `help-desk` → ARCHIVE

### Phase 5: Set channel order within each category
Drag channels into the exact order listed in the structure above.

### Phase 6: Set permissions
- [ ] Lock `welcome`: @everyone → Send Messages ❌
- [ ] Lock `announcements`: @everyone → Send Messages ❌
- [ ] Lock `premium-portfolio`: @everyone → Send Messages ❌
- [ ] Lock `bonus-drops`: @everyone → Send Messages ❌
- [ ] Lock `alt-parlay`: @everyone → Send Messages ❌
- [ ] Lock `daily-recap`: @everyone → Send Messages ❌
- [ ] Lock `monthly-tracker`: @everyone → Send Messages ❌
- [ ] Lock `glossary`: @everyone → Send Messages ❌
- [ ] Lock `affiliates`: @everyone → Send Messages ❌
- [ ] Hide `mods`: @everyone → View Channel ❌, Mods role → View ✅
- [ ] Hide `modlog`: @everyone → View Channel ❌, Mods role → View ✅

### Phase 7: Set channel topics
For each channel, right-click → Edit Channel → set the topic text from the tables above.

### Phase 8: Create webhooks
- [ ] `premium-portfolio` → Create webhook "picksbyjonny" → copy URL
- [ ] `bonus-drops` → Create webhook "picksbyjonny" → copy URL
- [ ] `alt-parlay` → Create webhook "picksbyjonny" → copy URL
- [ ] `daily-recap` → Create webhook "picksbyjonny" → copy URL

### Phase 9: Content migration + pinned posts
- [ ] Copy "Discipline > emotion" lines from old community-rules pin → already in new welcome
- [ ] Screenshot/save Jono's about-me content before archiving (just in case)
- [ ] Delete OLD pinned messages in `#welcome`, `#glossary` (clean slate)
- [ ] Post NEW welcome pinned message in `#welcome` → pin it
- [ ] Post Jono's intro as SECOND pinned message in `#welcome` → pin it
- [ ] Post NEW glossary content in `#glossary` → pin it
- [ ] Verify The Pit Boss bot still auto-greets new members (check bot settings)

### Phase 10: Update the code
- [ ] Paste `premium-portfolio` webhook URL into `run_picks.py` → `DISCORD_WEBHOOK_URL`
- [ ] Paste `bonus-drops` webhook URL into `run_picks.py` → `DISCORD_BONUS_WEBHOOK` (I need to add this variable — tell me when you have the URL)
- [ ] Paste `alt-parlay` webhook URL into `run_picks.py` → `DISCORD_ALT_PARLAY_WEBHOOK`
- [ ] Paste `daily-recap` webhook URL into `run_picks.py` → `DISCORD_RECAP_WEBHOOK`
- [ ] Paste `daily-recap` webhook URL into `grade_picks.py` → `DISCORD_RECAP_WEBHOOK`

### Phase 11: Collapse ARCHIVE
- [ ] Click the ARCHIVE category arrow to collapse it
- [ ] Members won't see the clutter unless they expand it

### Phase 12: Final visual check
- [ ] Scroll through entire sidebar — clean, no emojis in names, correct order
- [ ] Check every channel topic is set
- [ ] Verify locked channels show "You do not have permission to send messages"
- [ ] Verify MODS channels are invisible to regular members
- [ ] Send a test message in `#general` to confirm community channels work

---

## WHAT THE FINAL SIDEBAR LOOKS LIKE

```
WELCOME
  # welcome
  # announcements

PICKS
  # premium-portfolio
  # bonus-drops
  # alt-parlay

RESULTS
  # daily-recap
  # monthly-tracker
  # winning-slips

COMMUNITY
  # general
  # questions
  # community-picks
  # testimonials
  🔊 gaming

RESOURCES
  # glossary
  # sports-news
  # affiliates

ARCHIVE ▸ (collapsed)
  # daily-card
  # how-to-use-this-server
  # about-me
  # community-rules
  # help-desk
  # andrews-futures
  # game-lines
  # full-card
  # posted-picks-alerts
  # halftime-buy-alerts
  # longshot-parlays
  # ladder-challenge
  # parlays
  # ladders-sgp
  # archived-premiere-picks
  # archived-questions
  # announcements (old)
  # archived-money-makers
  # archived-winning-slips
  # archived-extra-picks
  # glossary (old)
  # archived-sports-chat
```

---

## CODE CHANGE NEEDED

Once you have the bonus-drops webhook URL, send it to me and I'll add `DISCORD_BONUS_WEBHOOK` to `run_picks.py` and route the `post_extras_to_discord()` function to it. Right now both Premium and Bonus post to the same webhook — we need to split them.

---

*picksbyjonny · edge > everything*
