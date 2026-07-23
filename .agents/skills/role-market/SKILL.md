---
name: role-market
description: Discover, ingest, screen, compare, and review role directions and job descriptions using attributable market evidence. Use for JD searches, fit screening, comparable-role analysis, market channel evidence, or corrections to a prior screening.
---

# Role Market

Read `../_shared/career-contract.md`. This Skill owns `30-role-market` and the
kinds `market.channel`, `market.direction`, and `market.jd`.

Read `system/seeds/authorities/30-role-market.md` for the canonical terms,
lifecycle, and completion gate. Every JD records source fidelity, channel,
capture time, missing sections, and the SHA-256 of its exact `## JD 原文`
section. Screening metadata and `## 重新评价` live in that same JD Note; they
cannot advance application or readiness state.

## Modes

- **discover** identifies role directions or candidate JDs.
- **channel** maintains a dated, ranked market-access channel without turning it
  into Company, application, or outcome authority.
- **ingest** preserves a specific JD and its source metadata.
- **screen** evaluates requirements, signals, gaps, and uncertainty.
- **compare** contrasts comparable JDs without collapsing them into one source.
- **review** corrects an existing screening while preserving the prior evidence.

## Workflow

1. Distinguish a role direction from a dated JD instance.
2. Reuse a Channel record when one exists; preserve source URL or channel,
   retrieval date, quotations, and missing fields.
3. Keep explicit requirements in `## JD 原文` and interpretation in
   `## 重新评价`; never create a second Screening Note for the same JD.
4. Link evidence and readiness records by ID; do not infer readiness from a match
   score or mechanism check.
5. Keep screening independent from company decisions, application state, resume
   tailoring, and interview preparation.

Signed-in or fragile channels require user-prepared access and read-only work.
Stop at login, security, redirect, blank, stale, refresh, or ambiguous state.
Never apply, message, or mutate an account through this Skill.
