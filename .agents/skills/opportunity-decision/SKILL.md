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

1. Reuse Company and Recruiting Scope records before creating an Engagement.
2. Keep recruiter contact distinct from application state; unknown state remains
   unknown.
3. Link the exact JD, screening, resume export, and readiness session by stable ID
   when they exist. Do not copy their canonical content.
4. Record external events only from direct evidence or explicit user report.
5. Keep the decision reversible unless the user explicitly authorizes the
   external action.

Applications, messages, uploads, offer acceptance or rejection, account changes,
and resignation always need a separate explicit request. Local tracking does not
authorize any of them. If an external action is the request's only intent, stop
without selecting a Career Skill; select `track` only when the request also asks
to record an evidenced event locally.
