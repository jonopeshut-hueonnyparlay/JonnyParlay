# Paid Picks Service Launch Research — Sections 1 & 2
**Date:** 2026-05-20  
**Research scope:** Winible platform mechanics + Telegram vs Discord platform selection  
**Context:** picksbyjonny launch — sharp/analytical brand, Winible as payment platform, Telegram vs Discord for delivery

---

## Section 1 — Winible as a Platform

### Key Findings

**What Winible Is**
- Winible is a creator monetization platform built exclusively for sports betting cappers — self-described as "created by cappers for cappers." It is the closest direct competitor to Whop in the picks-service niche.
- Raised a $6M seed round (2024) led by Inspired Capital (~$900M AUM) with ~24 investors including Ray Lewis, a former FanDuel executive, and several professional cappers. This is a legitimate, funded company, not a fly-by-night tool.
- Platform stats: ~75,000 active subscribers, ~$30M in bets placed, ~100 sports betting influencers on platform (figures from the Sportico seed article, 2024 — likely higher now).
- Business model: revenue-sharing with creators. They make money when you do.

**Fee Structure**
- Platform fee is not publicly disclosed as a fixed percentage. The help center FAQ states: "We take a platform fee (including payment processing) that ranges based on your volume. This rate drops as you scale. Your Winible success partner will work with you to determine the best rate based on your size and needs."
- INFERENCE: Given the "free to start" pitch and volume-based sliding scale, the rate is likely in the 5-12% range for small/new operators, dropping for larger volume — similar to Whop's starting rate. Exact numbers require a direct sales conversation.
- There is zero public documentation of the specific percentage. This is a deliberate opacity — common in early-stage platforms competing for creator relationships.

**How It Works for Creators**
- Operators create a customizable mobile-friendly storefront on winible.com.
- Can sell picks as individual purchases OR recurring subscriptions (weekly, monthly, annual).
- Free tier subscriptions explicitly encouraged as a top-of-funnel tool.
- Delivery options: SMS, email, Discord, Telegram — subscribers select their preference at sign-up.
- Tools include: subscription management, free trial management, custom discount codes, CRM/sales intelligence, text alert capabilities.
- Approval process: within 24 hours of application.
- Affiliate/referral program: creators earn 3% of referred cappers' earnings via unique referral link (located in Earnings page). Referred cappers also get prioritized for acceptance.

**Discord Integration (Native)**
- Winible natively integrates with Discord via a bot. The integration:
  - Automatically grants Discord server access to paying subscribers.
  - Assigns roles based on subscription tier at subscription start.
  - Removes or reassigns roles when subscriptions expire (configurable: can remove from server or downgrade to a free role for re-engagement).
  - Setup: operator links subscription plan to Discord server via Winible settings panel, promotes Winible Bot to top of role hierarchy, configures role assignments per plan lifecycle event.
- This is fully native — no third-party Zapier/webhook required for Discord role management.

**Telegram Integration (Native)**
- Winible also natively gates Telegram channels and groups via the Winible Bot.
- Setup: operator adds Winible Bot as admin to their Telegram channel/group, generates a case-sensitive code in Winible, posts it to Telegram, completes the connection.
- On subscription expiry: configurable via checkbox — "Remove subscribers on subscription end" (checked = kicked; unchecked = stays in channel indefinitely).
- Both channel (broadcast-only) and group (interactive) formats are supported.
- Limitation: documentation does not detail capacity limits, error handling, or analytics within Telegram.

**Analytics / What Requires Third-Party Tools**
- Winible provides native: storefront analytics, subscription management dashboard, earnings tracking, CRM-lite.
- Does NOT natively provide: advanced audience analytics, pick performance tracking/verification, affiliate marketing beyond the 3% referral structure, content scheduling tools.
- Verified performance tracking (for social proof/credibility) requires third-party tools or manual posting.

**Buyer Experience / Marketplace Discovery**
- The Winible app (iOS available) provides subscribers a discovery feed: browse featured and trending cappers, get real-time push notifications the moment a pick drops, and view all picks in a single scrollable feed.
- Discovery uses a leaderboard system across NFL, NBA, MLB, WNBA, PGA, NCAAF.
- The marketplace drives some organic discovery — subscribers searching by sport can find new cappers.
- INFERENCE: Organic marketplace traffic on Winible is lower than Whop's (Whop has 18M+ users). Winible's discovery is more niche/sports-specific but also more qualified.
- Picks are delivered to subscribers via SMS and email in real-time — native to the platform regardless of Discord/Telegram choice.

**ToS / Payment Processor Restrictions**
- Winible's ToS URL exists (winible.com/terms) but was blocked from direct fetch. No public summary of gambling-content restrictions found.
- INFERENCE: Because the platform is purpose-built for sports betting cappers and is funded by sports/gambling executives, there are likely no restrictions on picks/betting advice content as this is the core use case. Payment processor risk is managed by Winible as the intermediary.
- The chargeback complaint (see below) suggests they use a standard card processor rather than crypto/ACH, and that processor health is a platform-level concern rather than creator-level.
- Subscribers pay by credit/debit card. Subscriptions auto-renew and can be cancelled from the Subscriptions page.

**Known Complaints / Failure Modes**
- **Chargeback dispute refusal (CONFIRMED, Threads post by @_thesheet):** Operator reported a fraudulent customer chargeback — Winible acknowledged it was fraudulent but refused to cover it or allow the operator to dispute it. Stated reason: "disputes hurt their payment credit score for the platform." This is the single most serious structural concern — Winible absorbs no chargeback risk and the operator bears all loss.
- **Auto-charge transparency failures (Trustpilot, multiple reviews):** Subscribers complained that "free day" offers charged them if they'd already used a free trial, with insufficient notification that the free offer is new-customers-only.
- **Pick quality responsibility:** Platform takes no responsibility for capper pick quality. Negative reviews often conflate pick losses with platform failure.
- **Payout timeline:** Not publicly documented. The Winible payout page (winibleaffiliatepayouts) was inaccessible. No confirmed data on how fast earnings land.
- **Platform maturity:** At ~100 cappers and ~75K subscribers (2024 figures), Winible is early-stage. Bug risk is higher than Whop, and support responsiveness is less proven at scale.
- **Trustpilot rating:** 3.8/5 based on 68 reviews — "Great" designation. Mixed but not alarming for a young platform.

**How Winible Compares to Alternatives**

| Platform | Fee | Sports picks native? | Discord | Telegram | Marketplace traffic | Notes |
|----------|-----|----------------------|---------|----------|---------------------|-------|
| **Winible** | Variable, undisclosed (~5-12% est.) | Yes — built for cappers | Native bot | Native bot | Small but qualified | Purpose-built; chargeback risk on creator |
| **Whop** | 3% (your traffic) / up to 30% (Whop traffic) + 2.7%+$0.30 Stripe = ~6-7% effective | Yes — large sports niche | Native | Native | Very large (18M+ users) | Broader platform; stronger marketplace discovery |
| **DubClub** | Not disclosed | Yes — picks-focused | Not confirmed | Not confirmed | Smaller | 1.5M fans; focused on follow/tail model |
| **Patreon** | 8-12% + payment processing = 13-16% total | No | No native integration | No | General; not picks-specific | Higher fees; no sports-native tools |
| **Substack** | 10% + Stripe = ~13% | No | No | No | General newsletter | No real-time delivery; wrong format for picks |
| **Memberful** | ~10% + processing | No | No | No | None | Requires own website; technical lift |
| **Direct Stripe** | 2.9% + $0.30 | No | Manual | Manual | None | Lowest fees; maximum DIY work |

**Conclusion on platform hierarchy for picks services:**
- Highest-revenue picks services (e.g., GoldBoys with 30K+ members, TrustMySystem with 70K+ free / 10K+ VIP) are predominantly on **Whop** — which has a proven, scaled marketplace and strong discovery.
- Winible is the sharper, more sports-specific alternative with native SMS delivery, but lacks Whop's marketplace reach.
- The critical chargeback issue means operators should maintain cash reserves for potential disputes.

**Does Winible Have a Referral/Affiliate Program for Subscribers?**
- Creators earn 3% of referred cappers' earnings (capper-to-capper referral).
- No public documentation of a subscriber-facing affiliate program where subscribers earn commissions for recruiting other subscribers. INFERENCE: Not available natively — would require manual discount code sharing.

### What This Means for picksbyjonny

Winible is a legitimate, purpose-built choice for a sharp picks service. The Discord + Telegram native integrations reduce setup friction significantly. The fee opacity is a minor concern — get the rate in writing before signing anything, and benchmark it against Whop's transparent 3% (+processing) structure.

The chargeback non-protection is the one hard risk: Winible will not fight fraudulent chargebacks on your behalf and the loss falls on the creator. For a high-ticket service ($99+/month), one fraudulent subscriber doing a chargeback costs the creator the full amount. Mitigate by keeping monthly pricing (harder to do a large lump-sum chargeback) and monitoring for chargeback patterns.

The marketplace discovery benefit is lower than Whop's at current scale. Do not rely on Winible organic traffic — treat it as a payment/access layer and drive all traffic externally (social, Discord free tier, X/Twitter). Whop would give better organic uplift if marketplace discovery matters.

For a luxury analytical brand like picksbyjonny, Winible's positioning ("created by cappers for cappers," leaderboard-driven, sports-specific) is a better brand fit than Whop's broad creator marketplace. The SMS pick delivery is a meaningful differentiator — subscribers get picks directly on their phone without opening an app.

Recommendation: **Winible is viable.** Negotiate the fee rate explicitly, confirm payout timeline, and set chargeback policy expectations before go-live. If Whop organic discovery is important, run both in parallel initially (Winible for Telegram/Discord integration, Whop for marketplace presence) — though this adds operational complexity.

### Sources/Basis

- Sportico seed funding article: https://www.sportico.com/business/finance/2024/winible-seed-funding-ray-lewis-1234771353/
- Winible Creator FAQ (Intercom help center): https://intercom.help/winible/en/articles/9883292-frequently-asked-questions-for-creators
- Winible Introduction for Creators: https://intercom.help/winible/en/articles/9827833-introduction-to-winible-for-creators
- Winible Discord Integration docs: https://intercom.help/winible/en/articles/9113319-winible-discord-integration
- Winible Telegram Integration docs: https://intercom.help/winible/en/articles/9278158-winible-telegram-integration
- Winible Subscriber FAQ: https://intercom.help/winible/en/articles/9883280-frequently-asked-questions-for-subscribers
- Trustpilot reviews (3.8/5, 68 reviews): https://www.trustpilot.com/review/www.winible.com
- Chargeback complaint (@_thesheet on Threads): https://www.threads.com/@_thesheet/post/DEsrRZOxMQi
- Pickscouts Winible vs Whop: https://pickscouts.com/winible-vs-whop/
- Whop top sports betting communities (pricing/member data): https://whop.com/blog/sports-picks-community/
- Whop fee breakdown: https://dodopayments.com/blogs/whop-fees-explained
- Crunchbase: https://www.crunchbase.com/organization/winible
- Apple App Store: https://apps.apple.com/us/app/winible-expert-sports-picks/id6748405452

---

## Section 2 — Platform Selection: Telegram vs Discord vs Alternatives

### Key Findings

**Why Telegram Is Frequently Cited as Superior for Paid Picks Services**
- Telegram is a **broadcast-first, mobile-first** platform. Channels allow only admins to post — picks land cleanly without being buried in member chat noise.
- Push notifications are near-instantaneous. Telegram maintains a persistent socket connection to its own servers and delivers without relying on FCM/APNs round-trips — sub-100ms delivery is documented. For a picks service where line movement matters within seconds, this is material.
- Zero algorithmic filtering. Unlike Discord (which groups unreads by server and drowns picks in other notifications), Telegram channel notifications appear individually in the phone's notification bar — identical to a text message.
- Simpler UX for subscribers: no server join, no verification, no role system to navigate. Receive a link, tap it, done.
- Telegram groups scale to 200,000 members. Channels are unlimited.

**Why Discord Is Better for Community Building**
- Discord provides granular role/channel architecture: multiple channels, locked VIP sections, public free tier, voice rooms, events, forum threads.
- AutoMod and bot-driven moderation is more sophisticated than Telegram's keyword-based moderation.
- Better for long-form community engagement: discussion, questions, analysis threads.
- Scales to tens of millions of server members.
- The existing picksbyjonny Discord is a real asset — Discord's community tooling makes it the right home for a social/engagement community.

**Concrete Feature Differences (Picks Service Lens)**

| Feature | Telegram | Discord |
|---------|----------|---------|
| Notification delivery | Individual push per message — near-instant | Grouped by server; often missed or delayed |
| Mobile UX | Native, app-like simplicity | Heavier; navigation required |
| Broadcast (picks channel) | Channel format — admin-only posts, no noise | Announcement channel works but buried in server |
| Community discussion | Group format; limited threading | Superior — threads, forums, roles |
| Search | Poor — Telegram search is shallow | Stronger within server |
| Bot ecosystem | Large — ManyBot, InviteMember, BotSubscription | Very large — Whop bot, Winible bot, Carl-bot |
| Pinning | Channel pinning works; no thread pinning | Full pin/thread management |
| Permission management | Limited — admin or not; no role tiers | Full role hierarchy with granular channel perms |
| Payment gating | Requires Winible bot / LaunchPass / InviteMember | Winible native / Whop native |
| Anti-leak (forwarding block) | Native "Restrict Saving Content" blocks forwarding, screenshots, downloads in channels/groups | No equivalent native forwarding block |
| Media | Excellent — high-quality image/video without compression | Compresses images; worse for graphics |

**What Paying Subscribers Prefer**
- INFERENCE (no hard survey data found): The dominant industry view from multiple sources is that subscribers prefer Telegram for picks delivery because they actually see the pick in time. Discord notification fatigue is a well-documented problem — users disable server notifications entirely after a few weeks.
- Telegram's text-message-like notification behavior makes it harder to ignore. For a time-sensitive pick (line moving pre-game), this is the core operational argument for Telegram.
- Community discussion and engagement still favors Discord — subscribers who want to talk about picks, ask questions, and interact with others prefer Discord's structure.

**Winible + Telegram Gating — Does It Work Natively?**
- YES. Winible's Telegram integration is native. The Winible Bot is added as admin to your Telegram channel/group, subscribers who purchase a Winible plan are automatically granted access, and expired subscribers are automatically removed (if the "remove on expiry" checkbox is enabled).
- No separate bot subscription or third-party tool required.
- This means: Winible handles payment, Telegram handles delivery. The access gate is automated.

**Alternative Telegram Bots for Paid Community Management**
- **InviteMember**: Dedicated paid Telegram membership bot. Handles payment processing, subscriber access, renewal reminders, trial periods. Often used when not using a platform like Winible.
- **LaunchPass**: Full service — connects Stripe/PayPal to Telegram (and Discord/Slack). Simpler than Winible but no sports-specific features.
- **BotSubscription**: Another dedicated paid Telegram channel tool.
- For picksbyjonny using Winible, none of these are needed — Winible's native bot handles access management.
- **Auto-posting bots**: For scheduled or templated pick delivery, operators use bots built on Telegram Bot API to post at specific times or when triggered by a webhook. Winible's own SMS/email delivery also covers this at the subscriber level.

**Anti-Leak: Telegram vs Discord**
- **Telegram** has a native content protection feature: "Restrict Saving Content" on channels/groups prevents forwarding, copying, downloading, and on-device screenshots (at the OS level on iOS/Android when supported). This is the most effective native anti-leak tool available on any platform.
  - Bypass exists: physical screen photography. Not preventable by software.
  - Also: screen recording apps and modified Telegram clients can bypass the restriction.
- **Discord** has no native forwarding restriction. Content can be copied, screenshot, and shared freely.
  - Anti-leak on Discord relies on: image watermarking (burning subscriber usernames/IDs into pick images), Discord roles requiring phone verification, and monitoring bots (e.g., MEE6) for suspicious link posting.
  - Watermarking is the gold standard — even if leaked, the pick is traced back to the subscriber who leaked it.
- **INFERENCE:** Telegram has structurally better anti-leak architecture for pick delivery. Discord's open copy/screenshot model requires active countermeasures. For a premium-tier service, watermarking pick images is recommended regardless of platform.

**Hybrid Model: Winible + Telegram Delivery + Discord Community**
- This is the dominant structure among sophisticated picks services in 2025-26.
- Model: Telegram channel (admin-only broadcast) for picks delivery → Discord server for community, questions, analysis, free-tier engagement → Winible as the payment/access layer that gates both.
- Influencer marketing hub and other sources confirm: "Most high-growth projects run both — Telegram for reach and Discord for depth."
- Operational structure: Winible auto-admits paid subscribers to both Telegram channel AND Discord VIP role simultaneously. Free Discord tier (ungated) feeds top-of-funnel. Telegram channel is strictly paid-only.
- This approach maximizes: notification reliability (Telegram), community stickiness (Discord), free-tier conversion funnel (Discord public channels), and pick-security (Telegram's content restriction).

**Notification Open Rates**
- No independently verified open-rate survey data was found for Telegram vs Discord in picks-service context.
- Documented technical advantage: Telegram delivers via persistent socket — sub-100ms notification delivery vs Discord's reliance on FCM/APNs which introduces delay and OS-level batching.
- Practical consensus: industry practitioners uniformly state that Telegram picks get acted on faster. Discord picks are commonly missed because server notifications are routinely muted.

**Top Picks Services on Telegram (Confirmed Operating)**
From Whop's Telegram sports betting article and other sources:

| Service | Pricing | Sports | Notes |
|---------|---------|--------|-------|
| Mazi Picks | $200-$20,000/month | NFL, NBA, MLB, UFC | Premium positioning; six-figure personal wagers |
| Sean Perry Wins | $999-$14,999/month | NFL, NBA, MLB, UFC | Former poker pro; single bets emphasis |
| GOAT Sports Bets | $35-$1,500 | All major leagues | 650+ reviews, 4.96/5 |
| SITHLORDCHAMBA | $19.99-$9,999 | All sports | 24/7 support; tiered structure |
| Major Wagers | $28.99-$799.99/year | NFL, NBA, MLB + soccer | Educational courses included |
| The Sweepers | $39.99-$999 lifetime | Multiple | Community chatting channels |
| Vegas Ninja | $87-$175/quarter | All sports | 20+ years experience |
| High Limit Sports | $20-$65/month | American + international | 4 founding cappers |
| Almost Perfect Picks | $5-$250/year | Multiple | Algorithm-based |
| Profitic Sports Bets | Not listed | Multiple | 9K+ members across Telegram + Discord |
| Platinum Sports Picks | $59.99/week or $199/month | Multiple | Free tier with few free plays daily |

**Services That Have Migrated Between Platforms**
- No specific well-documented public case of a major service migrating fully from Discord → Telegram or vice versa was found. The trend in 2025 is maintaining both, not replacing one with the other.
- Profitic Sports Bets maintains 9K+ members across both Telegram and Discord — exemplifying the hybrid approach.
- INFERENCE: Services that tried to operate Discord-only and lost subscribers to notification fatigue have added Telegram channels. Reverse migrations (Telegram → Discord-only) are not documented.

**X Communities, Substack, WhatsApp**
- **X Communities:** No documented picks service successfully using X Communities as primary delivery. X's algorithmic feed makes time-sensitive pick delivery unreliable. Viable only as a discovery/marketing layer, not delivery.
- **Substack:** Wrong format entirely — newsletter cadence, not real-time. No push notification behavior comparable to Telegram. One sports newsletter might cite a Substack as supplementary analysis, but it cannot serve as a picks delivery platform.
- **WhatsApp:** Groups cap at 1,024 members; Communities up to 5,000. No payment gating native. Privacy concerns (Meta data policies). Used informally for small, relationship-based picks sharing but not viable for a scaled paid service. Also: group messages are cluttered; no channel-style admin-only broadcast.
- **Skool / Mighty Networks:** Community platforms with subscription gating but no real-time notification urgency. Better fit for educational content than time-sensitive picks.

**Do the Sharpest Analytical Services Correlate with a Specific Platform?**
- The most analytically rigorous services (algorithm-based, model-driven, transparent tracking) appear on both Whop and Telegram, with no single platform monopoly.
- Examples: NicksProvenPicks (statistics background, custom betting models) on Whop/Discord; Almost Perfect Picks (algorithm-based) on Telegram; AI Bet Scanner (three algorithms) on Whop.
- DubClub's model (follow-and-tail with performance tracking) is the most structured verification approach — 1.5M fans, fourth anniversary with record profitability — and operates on its own platform.
- INFERENCE: Platform choice among sharp services is driven by operational preference, not a marker of analytical quality. The brand signals sharpness; the platform delivers it.

### What This Means for picksbyjonny

**Recommended structure:** Winible (payment/access) + Telegram channel (picks delivery, paid-only) + Discord (community, free tier + VIP sections).

Rationale:
1. Telegram channel for picks: subscribers will see every pick in time. Notification reliability is the single most important operational factor for a picks service — if a subscriber misses a pick because Discord notifications were off, that is a churn driver regardless of pick quality.
2. Discord for community: picksbyjonny already has a Discord server. Keep it. It is the right platform for the free-to-paid funnel, community questions, analysis discussion, and brand stickiness. The luxury/analytical brand communicates better in a structured Discord environment.
3. Winible gates both simultaneously: one payment, auto-admits to Telegram + Discord VIP role. No manual access management.
4. Enable Telegram's "Restrict Saving Content" immediately — it is the best available anti-leak measure on any platform. Supplement with watermarked pick images (burn subscriber handle into the image) for Discord posts.
5. Do not use X, WhatsApp, or Substack as primary delivery. They are marketing channels, not picks channels.

On pricing positioning: the Telegram picks-service market supports $30-$200/month for well-branded analytical services. The Mazi Picks / Sean Perry pricing ($999+/month) requires established social proof with verified track records and large followings. Starting at $49-$99/month for a premium tier and $149-$199/month for an exclusive/KILLSHOT tier is consistent with comparable services at early growth stage.

### Sources/Basis

- Whop's top sports betting Telegram channels article: https://whop.com/blog/sports-betting-telegram/
- Whop's Telegram vs Discord comparison: https://whop.com/blog/telegram-vs-discord/
- Influencer Marketing Hub Telegram + Discord playbook: https://influencermarketinghub.com/telegram-and-discord-playbook/
- Mighty Networks Telegram vs Discord 2026: https://www.mightynetworks.com/resources/telegram-vs-discord
- LaunchPass Discord/Telegram comparison: https://www.launchpass.com/blog/discord-telegram-or-slack-choosing-your-paid-community-platform/
- LaunchPass help center: https://help.launchpass.com/en/articles/5089779-discord-vs-telegram-vs-slack-which-platform-should-you-choose-for-your-paid-community
- Winible Telegram Integration docs: https://intercom.help/winible/en/articles/9278158-winible-telegram-integration
- Telegram push notification architecture: https://trtc.io/blog/telegram-push-notifications-developer-lessons
- Telegram content protection (anti-leak): https://www.such.chat/blog/stop-telegram-content-theft-all-about-telegram-content-protection
- Hashtag Investing best sports betting Telegrams: https://www.hashtaginvesting.com/blog/sports-betting-telegrams
- SmartBettingGuide Telegram groups: https://smartbettingguide.com/telegram-sports-betting-groups/
- Whop sports picks communities (Discord-side examples): https://whop.com/blog/sports-picks-community/
- Whop sell sports picks guide: https://whop.com/blog/sell-sports-picks/
- InviteMember Telegram monetization: https://blog.invitemember.com/discord-vs-telegram-how-to-monetize-your-community/
- Profitic Sports Bets (hybrid platform example): https://whop.com/blog/free-expert-sports-picks/

---

*Research confidence note: All platform statistics (Winible subscriber counts, Whop revenue, service member counts) are sourced from platform-reported figures or third-party journalism and are subject to change. Fee structures that were not publicly documented (particularly Winible's exact percentage) are flagged as INFERENCE throughout. No independently audited pick win-rate data for any named service was verified — treat all "70% win rate" style claims from service marketing as unconfirmed.*
