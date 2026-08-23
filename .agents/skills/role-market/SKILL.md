---
name: role-market
description: Discover, ingest, screen, compare, and review role directions and job descriptions using attributable market evidence. Use for JD searches, fit screening, comparable-role analysis, market channel evidence, or corrections to a prior screening.
---

# Role Market

Apply `../_shared/career-contract.md`. This Skill owns `30-role-market` and
`market.channel`, `market.direction`, and `market.jd`. Before a canonical write
or gate judgment, load `system/seeds/authorities/30-role-market.md`. Every JD
preserves source fidelity, channel, capture time, missing sections, and the
SHA-256 of its exact `## JD 原文`; screening and `## 重新评价` remain in that same
record and never advance application or readiness state.

## Modes

- **discover** identifies role directions or candidate JDs.
- **channel** maintains a dated, ranked access channel.
- **ingest** preserves a specific JD and source metadata.
- **screen** evaluates requirements, signals, gaps, and uncertainty.
- **compare** contrasts comparable JDs without collapsing their sources.
- **review** corrects an existing screening while preserving history.

## Workflow

1. Distinguish a durable role direction from a dated JD instance. In `discover`,
   return a small decision-ready shortlist and persist only selected leads or a
   reusable Channel, not every search result.
2. Reuse a Channel or JD by identity. Preserve URL/channel, retrieval date,
   quotations, missing fields, and exact JD text; never create a second
   screening note for the same JD.
3. Screen against explicit requirements and linked evidence. Separate fit,
   preference, risk, and unknowns; a score or mechanism check never proves
   readiness.
4. For an identified employer, inspect the canonical Company freshness and
   decision-critical dimensions first. Compose Opportunity Decision `research`
   only when the Company is absent, stale, ambiguous, or insufficient, then link
   it by Wikilink without copying Company facts.
5. Research until the decision-critical requirements and material uncertainty
   are covered; stop when additional sources are duplicative. Preserve partial
   status rather than guessing unavailable sections.
6. Finish with fit signals, blocking gaps, material risks, clarifying questions,
   and one next action. Do not tailor a resume, create application state, or
   grant readiness here.

Signed-in recruiting channels are user-operated. Accept user-provided URLs and
anonymous content; otherwise use pasted text or screenshots. Never control a
signed-in page, replay authenticated requests, handle session material, apply,
message, or mutate an account.
