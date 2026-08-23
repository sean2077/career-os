---
name: career-outlook
description: Scan dated external signals, synthesize evidence-backed career theses, and review whether prior outlook claims still hold. Use for technology, market, policy, or industry horizon questions that could affect career strategy.
---

# Career Outlook

Apply `../_shared/career-contract.md`. This Skill owns `50-career-outlook` and
`outlook.signal`, `outlook.thesis`, and `outlook.review`. Before a canonical
write or gate judgment, load
`system/seeds/authorities/50-career-outlook.md`. A reviewed Outlook Review needs
personal-fit, market-revealed, and independent-external signal gates with typed
references. Strategy cannot consume a pending thesis, and
`review_authority: user` requires explicit user review.

## Modes

- **scan** captures dated external signals with primary sources.
- **synthesize** builds a bounded thesis from multiple signals.
- **review** tests a prior thesis against newer evidence and records the delta.

## Workflow

1. Start from the existing thesis or decision question. Browse only when the
   conclusion depends on changing facts or a material evidence gap.
2. Prefer primary sources, then add independent evidence for interpretation or
   challenge. Record event date, publication date, retrieval date, scope, and
   source; expand only when sources disagree or a decision-critical dimension
   remains unresolved.
3. Separate source claims, inference, confidence, horizon, uncertainty, and
   disconfirming evidence. Avoid broad trend summaries that cannot change a
   career decision.
4. Use `career-strategy-advisor` only when an independent source-layered
   challenge can materially alter the thesis or strategy implication. A stale,
   unavailable, or malformed brief cannot promote an Outlook review or accept
   strategy.
5. Update the review chain rather than rewriting history. Link implications by
   stable Strategy ID, but leave Strategy changes to Career Strategy.
6. Stop with what changed, what would falsify the thesis, its review date, and
   one bounded implication.

An outlook is decision input, not a forecast guarantee or evidence of personal
readiness.
