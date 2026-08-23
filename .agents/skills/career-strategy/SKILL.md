---
name: career-strategy
description: Define or review career positioning, durable lanes, constraints, preferences, and aligned plans. Use for career direction, annual or quarterly planning, role focus, tradeoffs between paths, or alignment between current work and longer-term goals.
---

# Career Strategy

Apply `../_shared/career-contract.md`. This Skill owns `20-career-strategy` and
`strategy.positioning`, `strategy.lane`, and `strategy.plan`. Before a canonical
write or gate judgment, load
`system/seeds/authorities/20-career-strategy.md`. Strategy may consume only
reviewed Outlook authority; accepted or active state requires explicit lifecycle
history, not a completed task or pending thesis.

## Modes

- **position** maintains stable positioning, preferences, constraints, and
  narrative boundaries.
- **plan** turns a chosen horizon into dated, reviewable actions and signals.
- **align** compares current plans with evidence, opportunities, readiness, and
  reviewed outlook without copying their authority.

## Workflow

1. Start from current positioning and the active lane or plan for the relevant
   horizon. Do not read every historical strategy record.
2. For exploratory direction, return bounded options and tradeoffs without
   creating parallel plans. Persist only a chosen positioning, plan, or material
   review outcome.
3. Pull only the Evidence, Market, Opportunity, Outlook, and Readiness IDs that
   could alter the decision. Preserve their facts in their source authorities.
4. Use `career-strategy-advisor` only for a material, high-uncertainty horizon
   decision where an independent challenge can change the choice. Its dated
   brief is advisory and must not self-accept strategy.
5. Make the leading option, credible alternative, constraints, confidence,
   disconfirming signals, next review date, and smallest next action visible.
6. Revise the existing plan when purpose and horizon match. A plan records
   intent, not execution or a guaranteed outcome.

Write only Career Strategy records. Compose another Skill only to obtain or
update its missing authority, not to make the strategy record self-contained.
