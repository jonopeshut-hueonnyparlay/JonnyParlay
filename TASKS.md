# Tasks

## 🟢 Backlog

- [ ] **MLB go-live** — remove from SHADOW_SPORTS when sample is large enough *(Jono will call this)*

## ✅ Done

- [x] Golf fully removed from run_picks.py (archived to archived_golf_code.py)
- [x] CO_LEGAL_BOOKS constant defined (18 books, espnbet→theScore Bet display)
- [x] Bonus drops scaffolded (single highest-scoring new pick, max 5/day, own webhook)
- [x] POTD standalone embed (posts after premium card, same webhook/channel)
- [x] Alt spread parlay → #daily-lay webhook wired
- [x] KILLSHOT trigger logic + sizing math — score floor 90 (auto) / 75 (manual), weekly cap 3, sizing table (3–5u by score band)
- [x] BRAND_LOGO — real Discord CDN URL set in run_picks.py + grade_picks.py
- [x] Discord overhaul designed (master plan + build reference locked)
- [x] All 4 Discord webhooks configured in run_picks.py
- [x] Discord Phase 2 manual server build complete (channels, permissions, Carl-bot)
- [x] Carl-bot auto-DM configured — welcome DM live for new members
- [x] grade_picks.py fully rebuilt with Apr 13 features (ZoneInfo UTC→ET, dual-log, recap bug fix, --test/--repost, display_book, logo thumbnails, fmt_date)
- [x] run_picks.py deep audit complete — 6 bugs fixed (run_type column alignment, BRAND_LOGO constant, logo thumbnails, --test/--repost flags, suppress_ping wiring)
- [x] weekly_recap.py — full rewrite (xlsx attachment, guard, correct webhook, embed with day-by-day + tier breakdown)
- [x] results_graphic.py — new Pillow PNG card auto-posted after grade_picks.py recap
- [x] morning_preview.py — picks teaser auto-posted from run_picks.py
- [x] SPREAD double-line bug fixed in results_graphic.py + grade_picks.py
- [x] Streak announcements — P/L + W/L record + milestone copy (2/3/5/7+ day tiers)
