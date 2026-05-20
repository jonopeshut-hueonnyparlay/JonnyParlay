# picksbyjonny — Priority Action List
# 15 most important decisions before going paid, ranked by impact

Research date: 2026-05-20  
Synthesized from 17-section research agenda (paid_s1_s2 through paid_s17)

---

## The 15 Decisions

---

### #1 — Choose and negotiate your platform before building anything else

**Decision:** Winible vs Whop as the subscription and access management layer.

**Right answer:** Winible — purpose-built for sports betting cappers, native Discord + Telegram gating with zero third-party tools, SMS pick delivery included, sports-specific marketplace discovery. Whop is the fallback if organic marketplace traffic materially matters at launch.

**Action:** Before signing, get three things in writing from Winible: (1) the exact fee percentage at your volume, (2) payout timeline, (3) their chargeback policy. The chargeback policy is the single confirmed structural risk — Winible does not fight fraudulent chargebacks on creator's behalf. Know this before a $150 chargeback happens.

**What goes wrong if you skip this:** Building Discord roles, Telegram channels, and pick delivery workflows on assumptions about the platform, then discovering the integration doesn't work the way you expected. One week of subscriber access chaos at launch kills retention permanently.

---

### #2 — Set your price before launch and price above $50

**Decision:** Core tier price point and tier structure.

**Right answer:** Three tiers. Free (2 picks/week public) → Core ($79/month, full daily card, Discord VIP) → VIP ($149/month, KILLSHOT access, exclusive alerts channel). Launch with monthly billing; add annual (15% discount, ~$799/year) within 60 days.

**Psychological note:** $79 sits in the proven market sweet spot — above the "too cheap = low quality" floor ($25) and below the "show me 2 years of verified records" resistance ceiling ($150+). VIP at $149 anchors Core as the obvious choice. Use $97/$147 if A/B testing — specific numbers outperform round ones.

**$10K/month math:** 127 subscribers at $79 = $10,033 MRR. That is achievable at 12–18 months from a standing start with an existing Discord community and a verified projection engine.

**What goes wrong:** Pricing at $29 to attract initial subscribers signals low quality to the analytical audience picksbyjonny is targeting, attracts "The Bettor" archetype (high churn, blames service for losses), and makes it mathematically impossible to build a sustainable business without mass-market scale.

---

### #3 — Build the Telegram channel before launch day

**Decision:** Telegram as primary picks delivery channel, Discord as community.

**Right answer:** Telegram channel (admin-only broadcast, paid-gated via Winible) for every pick drop. Discord for community discussion, analysis, free tier, wins channel, recaps. Winible auto-admits paying subscribers to both simultaneously.

**Action:** Create the Telegram channel, add Winible Bot as admin, connect to Winible subscription plan, test the access grant and removal workflow with a test account before going live. Enable "Restrict Saving Content" immediately to activate native anti-leak protection.

**What goes wrong:** Delivering picks only via Discord means a meaningful percentage of subscribers will miss time-sensitive picks because server notifications are routinely muted. If a subscriber misses 3-4 picks because of notification fatigue, they churn — not because picks are bad but because the delivery mechanism failed. This is the most common complaint in picks service reviews.

---

### #4 — Define the losing streak communication protocol before the first cold week hits

**Decision:** What you post, when, and in what tone when the service goes on a losing run.

**Right answer:** Pre-write three templates before launch: (a) standard losing day — brief results note, one sentence of context; (b) 3-5 losing days — proactive community message reiterating the edge thesis with CLV data showing the model is still beating the close; (c) extended cold streak (7+ days) — full accountability post with P&L to date, process explanation, CLV summary, no excuses.

**The rule:** Never go silent during a cold run. Silence is interpreted as guilt. The services that retain through cold streaks post more during them, not less.

**What goes wrong:** No protocol means improvising under emotional pressure during the worst possible moment. Improvised defensive responses ("it's variance," "bad beats," "model is fine trust me") read as excuse-making. A pre-written calibrated response reads as confidence. The cold streak is coming — the question is whether you're ready for it.

---

### #5 — Publish a verified pick log from day one, publicly

**Decision:** How to establish and communicate your track record.

**Right answer:** The pick_log.csv + daily Discord results + weekly_recap.py output is the infrastructure. The missing piece is making it human-readable and public-facing. Minimum viable public record: a pinned Discord post updated weekly with running unit P&L (wins, losses, total units, ROI) and CLV summary. Stretch goal: Juice Reel listing with sportsbook sync (the industry's hardest-to-fake verification standard).

**Do from day one:** post every result — wins AND losses — with equal visibility. Cherry-picking is the #1 trust-destroying behavior in this industry. The willingness to show all picks including losing streaks is the primary differentiator from 95% of services.

**What goes wrong:** Starting paid without a public-facing record means every new subscriber is buying on faith. Faith erodes on the first cold streak. A subscriber who joined because they trusted a verified record survives a losing week; one who joined on a vibe does not.

---

### #6 — Write the onboarding document before the first subscriber

**Decision:** What new subscribers are told about what they're paying for before they experience any picks.

**Right answer:** A brief written "what you're paying for" agreement — one page, required acknowledgment at signup. Key language: (1) what the service provides (best-available edge and process, not guaranteed profits); (2) what variance looks like (losing streaks of 5-10 days are normal within a positive long-run edge); (3) what VAKE/unit sizing means and why betting 1-2% of bankroll per unit matters; (4) the verified record and CLV standard. This eliminates 80% of "I was misled" cancellation complaints.

**What goes wrong:** A subscriber who joins without this framing hits their first losing week and cancels with a negative review ("this service cost me $200 betting their picks"). A subscriber who acknowledged the onboarding document hits the same losing week and sends a DM asking if the model is still working.

---

### #7 — Complete the brand kit before any subscriber sees a single post

**Decision:** Visual identity — color palette, fonts, pick card template, logo.

**Right answer:** Dark anchor palette (onyx black or midnight navy covering 60-70% of visual space) + one metallic accent (gold preferred for luxury positioning). Two fonts maximum. One vector wordmark. One Canva pick card template that includes: sport/date, player/stat/line, direction/odds/book, **projection vs. line** (the single most visible signal of a model-driven service), confidence tier, brand footer. Apply identically across Discord, Telegram, X, Winible.

**The one mandatory field:** projection vs. line on every prop card. "Proj: 27.4 | Line: 24.5" is the visual proof of model-driven edge. No amateur service does this. It costs zero extra effort from the existing engine output and is the most credible single design element available.

**What goes wrong:** Inconsistent visuals across platforms signal disorganization and undermine the luxury brand before a single pick is evaluated. First impressions are formed on brand, not results.

---

### #8 — Build the annual content calendar now

**Decision:** How to manage subscriber retention through sports calendar transitions and the offseason cliff.

**Key dates for picksbyjonny 2026:**
- NBA Finals end: ~June 19. Stanley Cup Finals end: ~June 24. **The cliff — two-sport simultaneous end.**
- Only WNBA + MLB remain for ~10 weeks (June 25–September 1).
- NFL kickoff: September 2026. WNBA regular season ends: September 24.
- October: NBA/NHL openers + MLB playoffs + NFL mid-season = **peak acquisition window of the year**.

**Right answer:** Communicate the MLB/WNBA slate 2 weeks before NBA/NHL end ("Here's what's coming next"). Develop NFL model during the July–August development window. Announce NFL addition 4-6 weeks before September kickoff, grandfather existing subscribers. Never reduce price seasonally — instead pre-sell the next sport before the current one ends. Flat monthly pricing maintained year-round.

**What goes wrong:** Not communicating the upcoming schedule change before NBA/NHL end causes subscribers to cancel preemptively at season end. The churn is not inevitable — it is a communication failure.

---

### #9 — Get compliant with affiliate disclosure before posting a single book link

**Decision:** How to incorporate book affiliate links legally.

**Right answer:** (1) Start with DFS affiliate (DraftKings DFS, FanDuel DFS) — no state licensing requirement in most states. (2) CPA deals only for sportsbook links while checking Colorado Limited Gaming Control Commission requirements for rev-share. (3) FTC disclosure on every post containing an affiliate link — clear, prominent, before the link ("I earn a commission if you sign up through this link"). No fine print. Each non-compliant post is a separate potential $53,000 violation.

**Natural integration approach:** dedicate one Discord channel (#affiliates) and one pinned post to book recommendations. Mention recommended books in picks when relevant ("best line on DraftKings this week — link in affiliates"). Do not rotate "recommended book" based on who's paying more. The analytical audience is uniquely sensitive to perceived conflicts of interest.

**What goes wrong:** Running sportsbook rev-share links in Colorado without a license is a regulatory violation. Running undisclosed affiliate links with embedded promotions is an FTC violation. One enforcement action ends the business. The compliance cost is two steps: a licensing check and a disclosure template.

---

### #10 — Define the subscriber archetype you want and filter for it in marketing

**Decision:** Who picksbyjonny is for, stated explicitly in marketing materials.

**Right answer:** "Designed for bettors who use unit-based bankroll management, understand that edge compounds over hundreds of picks, and accept short-term variance as part of a long-run positive expectation strategy." This is a filter, not a deterrent.

**Three subscriber archetypes exist:**
- The Bettor: subscribed to win money; blames service on losses; cancels in 2-5 days. **High churn, leaves negative reviews.**
- The Student: subscribed to learn; tolerates variance with explanation; churns on trust violation not results.
- The Sharp Player: betting experience; subscribes for edge on top of their own process; lowest churn if methodology holds.

The sharp/analytical brand is already filtering correctly — the goal is to make it explicit. Subscribers who ignore the "designed for unit bettors" framing and join undercapitalized will have a bad experience regardless of pick quality.

**What goes wrong:** Attracting Bettors at scale produces high churn, negative reviews, and "I lost money on your picks" complaints that damage the brand publicly.

---

### #11 — Decide whether to list on Juice Reel for verified track record

**Decision:** Which third-party verification platform (if any) to use as the tamper-proof pick record.

**Right answer:** Evaluate Juice Reel as a Winible complement, not a replacement. Juice Reel requires sportsbook account sync — every pick is pulled directly from your book's bet history, making retroactive editing impossible. This is the hardest-to-fake trust signal in the market and the primary thing that separates legitimate services from touts in 2026. CapperTek is the older, lower-bar alternative (manual tracking). Either is meaningfully better than Discord-only timestamps for the analytical audience.

**The minimum viable approach:** pick_log.csv + weekly public P&L with CLV summary is sufficient to launch. Juice Reel listing is the credibility upgrade path once 30-60 days of paid-service records are established.

**What goes wrong:** Launching without any third-party verification is fine if CLV and P&L are published transparently on Discord. The risk is that the analytical audience — the highest-LTV segment — specifically looks for verifiable records before subscribing. A single sentence on the Winible listing ("Full verified record available on request") costs nothing and filters for the right subscribers.

---

### #12 — Prepare a "WNBA is our edge" narrative before WNBA season

**Decision:** How to differentiate picksbyjonny from the market on sport-specific edge.

**Right answer:** WNBA is an underexploited structural differentiator with documented line inefficiencies. Betting volume grew 150% at BetMGM and 108% at ESPN BET in 2024. Multiple sharp sources describe WNBA prop lines as "all over the place between books" and "pretty easy to beat right now." Almost no analytically-serious individual picks service applies a calibrated projection model to WNBA. Name this explicitly: "Our model finds more edge per pick in WNBA than anywhere else in our coverage — because the lines are the least efficient in major sports right now." This is specific, verifiable, and nearly impossible for a competitor without a real model to replicate.

**What goes wrong:** Treating WNBA as a secondary sport in marketing misses a genuine moat. A picks service that explicitly names WNBA as an edge source with results to back it up occupies a position no large service can credibly take.

---

### #13 — Add the DFS lineup upsell within 30 days of launch

**Decision:** First upsell product beyond the core subscription.

**Right answer:** DFS lineup output — the projection engine already produces the inputs. A DFS tier ($20–$50/month add-on) that delivers optimizer-ready player projections or pre-built DFS lineups for DraftKings/FanDuel is the highest-ROI additional revenue stream available with near-zero incremental build cost. The engine already runs daily. The output already exists in generate_projections.py.

**VIP consultation cap:** 5–10 slots at $300–$500/month for subscribers who want direct model access / bankroll strategy. Cap is mandatory — scarcity is an asset and time is finite.

**What goes wrong:** Not packaging the DFS output as a product means leaving revenue on the table from the subset of subscribers (likely 20-30%) who also play DFS contests. The build cost is a CSV export or lightweight presentation layer on existing engine output.

---

### #14 — Launch on X (Twitter) consistently before going paid

**Decision:** Social media strategy and platform priority.

**Right answer:** X (Twitter) is the only mandatory social platform for a picks service. Post real-time picks with brief rationale every day — the same picks going to paid subscribers, posted free, immediately after the card goes live. This is the primary acquisition funnel. Free social pick → free Discord → free tier → paid conversion. Consistency matters more than volume: one substantive post per day outperforms three engagement-bait posts.

**High-ROI content types for picksbyjonny specifically:** (1) pick post with projection vs. line ("Model: 27.4 | Line: 24.5 | Proj edge: 4.1%") — no other account posts this; (2) CLV summary posts ("Beat the close 11/14 this week — the market confirmed our lines"); (3) winning slip shares with honest P&L context (not cherry-picked wins).

**TikTok/Instagram:** Do not build these at launch. TikTok's content policy actively restricts sports betting promotion and requires licensing for monetized content. Instagram Reels has a three-second hook requirement that misaligns with analytical content. Start these 6+ months in if at all.

**What goes wrong:** Not building a social presence before going paid means the Winible storefront has zero external traffic driving to it. The paid launch without an existing warm audience is a cold start with no funnel.

---

### #15 — Publish a "How the model works" page before the first subscriber joins

**Decision:** How much of the methodology to make public.

**Right answer:** Publish a brief methodology explanation (300-500 words, public Discord channel, Winible listing, eventually a landing page) covering: what data the engine uses (game logs, lineup data, injury reports, Vegas totals), what the pick score measures, what "edge" means in context, what tier thresholds are, and what CLV proves about the model's accuracy. Do not publish the specific scalar values, calibration weights, or Platt parameters. The goal is to signal rigor, not hand over IP.

**The simple test:** Can a new subscriber understand WHY to trust the model in two minutes? If no, the methodology page needs to exist.

**What goes wrong:** Operating as a black box ("trust the model") is the primary complaint of analytically-oriented subscribers about existing services. picksbyjonny's moat is exactly this — a real model with explainable inputs. Not explaining it at all is equivalent to owning a $40K projection engine and keeping it in a closet.

---

## Priority Ranking Summary

| # | Decision | Impact if wrong | Urgency |
|---|----------|----------------|---------|
| 1 | Platform (Winible) — negotiate fees + chargeback policy | Access management failure at launch | Before launch |
| 2 | Price at $79+ / 3-tier structure | Wrong subscriber archetype, unscalable revenue | Before launch |
| 3 | Telegram channel (picks delivery) | Missed picks, churn from notification failures | Before launch |
| 4 | Losing streak protocol | Silent during cold streak = mass cancellations | Before launch |
| 5 | Public verified pick log | No trust foundation; analytical audience won't subscribe | Before launch |
| 6 | Onboarding document | "I was misled" complaints; high early churn | Before launch |
| 7 | Brand kit (dark/gold, projection-on-card) | Undermines luxury brand immediately | Before launch |
| 8 | Annual content calendar (seasonal cliff plan) | June subscriber cliff is avoidable with 2 weeks notice | Before June |
| 9 | Affiliate compliance (DFS first, CO license check) | FTC/regulatory violation on first book link | Before affiliate |
| 10 | Target subscriber filter in marketing | Attracts wrong archetype, negative reviews | Before launch |
| 11 | Juice Reel listing decision | Leaves most credible trust signal untapped | 30–60 days post-launch |
| 12 | "WNBA is our edge" narrative | Misses a genuine, defensible market position | Before WNBA season |
| 13 | DFS upsell product | Revenue left on table from existing engine output | 30 days post-launch |
| 14 | X/Twitter pre-launch presence | Zero funnel to Winible storefront at paid launch | Before launch |
| 15 | Methodology page (public) | Black box = no analytical trust; analytical audience won't convert | Before launch |

---

*Research note: Items 1–7 and 14–15 are true pre-launch gates — completing them is the condition for a clean paid launch. Items 8–13 are time-bound actions with a specific deadline window. The three hardest to reverse if wrong: pricing (#2), platform negotiation (#1), and the losing streak protocol (#4) — because subscriber expectations are set at first experience and are very difficult to reset.*
