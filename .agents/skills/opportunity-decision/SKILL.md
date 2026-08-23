---
name: opportunity-decision
description: Research companies, define recruiting scopes, track evidenced engagement or application events, and record bounded opportunity decisions. Use for company comparisons, networking context, recruiter contacts, active processes, offers, pipeline reviews, or local decisions. Do not select when the sole intent is to submit, message, upload, or mutate an external account.
---

# Opportunity Decision

Apply `../_shared/career-contract.md`. This Skill owns
`40-opportunity-decision` and `opportunity.company`, `opportunity.scope`,
`opportunity.engagement`, and `opportunity.decision`. Before a canonical write
or gate judgment, load
`system/seeds/authorities/40-opportunity-decision.md`. Engagement state advances
only through typed chronological events; recruiter contact, a JD, or a resume
never implies submission. Exactly one active started employment Engagement may
be current employment.

## Modes

- **research** maintains attributable Company facts.
- **scope** defines role, team, location, channel, and entity boundaries.
- **track** records recruiter contact, application, interview, offer, and other
  evidenced engagement events.
- **decide** records a dated judgment, alternatives, rationale, and next review.

## Workflow

1. Resolve Company and Recruiting Scope identity before creating an Engagement.
   Reuse existing records and read only current status, due next action, and
   decision-critical history before expanding into older events.
2. Record external events only from direct evidence or explicit user report.
   Unknown remains unknown; local tracking never authorizes the external act.
3. Link exact JD, screening, resume export, and readiness session IDs when they
   exist. Do not copy their canonical content or infer one state from another.
4. For Company research, define the unresolved dimension first. Prefer
   official and regulatory sources, then add independent evidence when material;
   expand only for
   disagreement, staleness, legal-entity ambiguity, or decision-critical gaps,
   and stop at login, CAPTCHA, rate limit, or risk-control boundaries.
5. In a pipeline review, prioritize active Engagements with overdue or missing
   next actions; do not manufacture activity to fill a dashboard.
6. In `decide`, show the leading option, alternative, rationale, uncertainty,
   reversibility, next review, and the smallest authorized next step.

When Role Market analyzes an identified-employer JD, reuse a fresh,
decision-complete Company; otherwise refresh it and link the JD. Company quality
may change priority, preference, risk, or questions, but never JD evidence fit,
application state, resume state, or readiness.

Use Career Communication `compose` for an unsent outreach, follow-up, negotiation,
or recruiter draft. Record an event here only after it occurred or the user
explicitly reports it. Applying, messaging, uploading, account changes, offer
acceptance/rejection, and resignation always require a separate explicit request.
