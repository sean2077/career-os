---
name: career-strategy
description: Define or review career positioning, durable lanes, constraints, preferences, and aligned plans. Use for career direction, annual planning, role focus, tradeoffs between paths, or alignment between current work and longer-term goals.
---

# Career Strategy

Read `../_shared/career-contract.md`. This Skill owns `20-career-strategy` and
the kinds `strategy.positioning`, `strategy.lane`, and `strategy.plan`.

Read `system/seeds/authorities/20-career-strategy.md` for the canonical terms,
lifecycle, and completion gate. Strategy may consume only reviewed Outlook
authority, and accepted or active state requires an explicit lifecycle history;
neither a pending thesis nor a completed task proves strategic acceptance.

## Modes

- **position** maintains stable positioning, preferences, constraints, and
  narrative boundaries.
- **plan** turns a chosen horizon into dated, reviewable actions and signals.
- **align** compares plans with current evidence, opportunities, readiness, and
  reviewed outlook without copying their authority.

## Workflow

1. Read current positioning and active lanes before proposing a new one.
2. Cite Career Evidence, Role Market, Opportunity, Outlook, and Readiness records
   by stable ID; do not restate their facts as strategy-owned truth.
3. For a material horizon decision, the Skill may dispatch
   `career-strategy-advisor` with a dated packet of stable Strategy, Outlook,
   Market, Opportunity, and Readiness references. Treat its brief as an
   independent read-only review, not an accepted recommendation. If it is
   unavailable, stale, or malformed, use the Skill's own source-layered fallback.
4. Make tradeoffs, constraints, confidence, review date, and disconfirming
   signals visible.
5. Prefer revising an existing plan over creating parallel plans for the same
   horizon.
6. Treat a plan as intent, not evidence of execution or a guaranteed outcome.

Write only Career Strategy records. Use other authority Skills for new market
research, evidence capture, readiness assessment, or communication artifacts.
