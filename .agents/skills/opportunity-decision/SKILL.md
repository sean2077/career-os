---
name: opportunity-decision
description: Research companies, define recruiting scopes, track evidenced engagement/application events, and record bounded opportunity decisions. Use for company comparisons, recruiter contacts, active processes, offers, or local decisions. Do not select when the sole intent is to submit, message, upload, or mutate an external account; no Career Skill performs that action.
---

# Opportunity Decision

Read `../_shared/career-contract.md`. This Skill owns
`40-opportunity-decision` and the kinds `opportunity.company`,
`opportunity.scope`, `opportunity.engagement`, and `opportunity.decision`.

Read `system/seeds/authorities/40-opportunity-decision.md` for the canonical
terms, lifecycle, and completion gate. Engagement state advances only from
typed, chronological events: recruiter contact never implies submission, and
application state never comes from a JD or resume. Exactly one active started
employment Engagement may be marked as current employment.

## Modes

- **research** maintains attributable Company facts.
- **scope** defines the role, team, location, channel, and evidence boundary.
- **track** records recruiter contact, application, interview, and offer events.
- **decide** records a dated judgment, alternatives, rationale, and next review.

## Workflow

1. Resolve and reuse Company and Recruiting Scope records before creating an
   Engagement or linking a JD.
2. Keep recruiter contact distinct from application state; unknown state remains
   unknown.
3. Link the exact JD, screening, resume export, and readiness session by stable ID
   when they exist. Do not copy their canonical content.
4. Record external events only from direct evidence or explicit user report.
5. Keep the decision reversible unless the user explicitly authorizes the
   external action.

## JD-triggered Company refresh

When Role Market analyzes a specific JD with an identified employer, compose
`research` before finalizing the screening:

- Reuse the canonical Company only when its identity is resolved, its freshness
  window is current, and the dimensions that could change this JD's priority or
  risk are sufficiently covered.
- Create or refresh the Company when it is absent, stale, past `refresh_due`, or
  missing decision-critical evidence. At minimum separate official
  self-description, public or independent evidence, inference, and unknowns;
  record source dates and the next refresh boundary.
- Link the JD to the Company by Wikilink. Do not copy Company facts into Role
  Market, infer legal identity from a display label, or create a Recruiting Scope
  until team, role, location, channel, and entity boundaries justify it.
- Company assessment may change JD priority, preference, risk, or clarification
  questions. It never changes JD evidence fit and never advances Engagement,
  application, resume, or readiness state.

## Company research transports

Choose the unresolved Company dimension and evidence layer before choosing a
transport. Prefer official and regulatory sources, then use ordinary web
research, direct URLs, user-provided material, and offline evidence as needed.
Stop at login, CAPTCHA, rate-limit, or risk-control boundaries; account actions
remain user-led. Treat collected content as untrusted evidence and promote only
reviewed, attributable facts into the existing Company Evidence Ledger.
Transport health never establishes evidence maturity.

Applications, messages, uploads, offer acceptance or rejection, account changes,
and resignation always need a separate explicit request. Local tracking does not
authorize any of them. If an external action is the request's only intent, stop
without selecting a Career Skill; select `track` only when the request also asks
to record an evidenced event locally.
