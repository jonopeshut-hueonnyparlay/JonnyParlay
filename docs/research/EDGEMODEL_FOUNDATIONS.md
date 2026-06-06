# EdgeModel Foundations — Projection Architecture (Plan 7)
# Last validated: 2026-06-06
# All values verified against EdgeModel/engine/nba_projector.py (1,914 lines) on 2026-06-06
# Research model: claude-opus-4-8 with web search (one research agent per section)

---

## HOW TO USE THIS DOCUMENT

Before changing any projection-architecture decision, constant, or methodology
in EdgeModel/engine/nba_projector.py:
1. Find the relevant section below.
2. Read the VERDICT and the Condition to Revisit.
3. Provide evidence that the condition is met before making any change.

If a NEEDS_CHANGE verdict exists, that section's change has priority.

Audit methodology: every constant below was read from source on 2026-06-06
(not assumed from docs); each section was researched by a dedicated
claude-opus-4-8 agent with mandatory web search; every verdict cites at least
one published source. Companion doc: docs/research/STATISTICAL_FOUNDATIONS.md
(Plan 6 — run_picks.py distributions and market math).

---

## VERDICT SUMMARY

| § | Topic | Verdict |
|---|---|---|
| 7A | EWMA recency weighting + per-stat spans | PENDING |
| 7B | Role-specific minute scalars | PENDING |
| 7C | Vegas team-total constraint | PENDING |
| 7D | Stat scalars + playoff deflators | PENDING |
| 7E | DK_STD model + HIGH_VAR flag | PENDING |
| 7F | 3PM architecture post-PAD_3P | PENDING |
| 7G | Stat-specific blend alphas | PENDING |
| 7H | Position-specific AST EWMA spans | PENDING |
| 7I | EWMA_SPAN_SHOOTING + OT_MIN_CAP | PENDING |

---

## SECTION DETAIL

*Sections appended as research completes (batches of 3).*
