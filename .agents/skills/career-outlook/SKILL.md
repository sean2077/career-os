---
name: career-outlook
description: Scan dated external signals, synthesize evidence-backed career theses, and review whether prior outlook claims still hold. Use for technology, market, policy, or industry horizon questions that could affect career strategy.
---

# Career Outlook

Read `../_shared/career-contract.md`. This Skill owns `50-career-outlook` and
the kinds `outlook.signal`, `outlook.thesis`, and `outlook.review`.

Read `system/seeds/authorities/50-career-outlook.md` for the canonical terms,
lifecycle, and completion gate. A reviewed Outlook Review requires personal-fit,
market-revealed, and independent-external signal gates, each backed by the
corresponding typed references. Strategy cannot consume a pending review or
candidate thesis. Set `review_authority: user` only after explicit user review;
the Skill cannot self-promote its own synthesis.

## Modes

- **scan** captures dated external signals with primary sources.
- **synthesize** builds a bounded thesis from multiple signals.
- **review** tests an existing thesis against newer evidence and records what
  changed.

## Workflow

1. Browse current primary sources when the conclusion depends on changing facts.
2. Record event date, publication date, source, scope, and retrieval date.
3. Separate source claims, inference, uncertainty, time horizon, and
   disconfirming evidence.
4. The Skill may ask `career-strategy-advisor` for a dated, source-layered
   challenge brief that references Strategy, Outlook, Market, Opportunity, and
   Readiness records by stable ID. The brief remains advisory; an unavailable,
   stale, or malformed review uses the Skill fallback and cannot promote an
   Outlook review or accept strategy.
5. Prefer updating a review chain over silently rewriting the historical thesis.
6. Link strategy implications by ID; do not change Strategy records from this
   Skill alone.

An outlook is decision input, not a forecast guarantee or evidence of personal
readiness.
