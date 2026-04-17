# Sports Betting Core — Current State

**Last updated:** 2026-04-07 (stub — needs Jono to fill in real numbers)

## Sizing mode
**Mode:** TODO — Standard / Conservative / Aggressive
**Trigger for switch:** 20+ consecutive negative-CLV bets → Conservative (per Hard Rule #1 in prompt 05)
**Bets since last mode change:** TODO

## CLV trend
- Last 10 bets avg CLV: TODO
- Last 30 bets avg CLV: TODO
- Last 100 bets avg CLV: TODO
- Rolling negative-CLV streak: TODO

Use the `clv-dashboard` skill to refresh these numbers from `projects/bet-tracker/`.

## Account health (book limits)
| Book | Status | Max bet | Notes |
|---|---|---|---|
| DraftKings | TODO | TODO | |
| FanDuel | TODO | TODO | |
| BetMGM | TODO | TODO | |
| Caesars | TODO | TODO | |
| ESPNBet | TODO | TODO | |
| Fanatics | TODO | TODO | |
| Bet365 | TODO | TODO | |
| Novig | TODO | TODO | sharp |
| ProphetX | TODO | TODO | sharp |
| Circa | TODO | TODO | sharp |
| LowVig | TODO | TODO | sharp |

Use the `book-limit-tracker` skill to keep this current.

## Open threads
- TODO: any bets that need a postmortem after recent results
- TODO: skill calibration check — is `sports-betting` v9.2 still pricing edges accurately?
