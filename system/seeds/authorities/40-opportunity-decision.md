# Opportunity Decision

This user-owned authority maintains Companies, Recruiting Scopes, Engagements,
events, and bounded decisions. Local tracking never authorizes an application,
message, upload, account change, offer action, or resignation.

## Key Terms

- **Company**: canonical attributable fact base with freshness and uncertainty.
- **Recruiting Scope**: verified or conservative team/role/location/channel boundary.
- **Engagement**: one employment, contact, referral, application, interview, or offer relationship.
- **Application state**: event-backed state distinct from recruiter contact.
- **Decision**: dated local posture with rationale, triggers, and next review.

## Authority Map

| Record | Kind | Suggested location |
| --- | --- | --- |
| Company | `opportunity.company` | `companies/` |
| Recruiting Scope | `opportunity.scope` | `scopes/` |
| Engagement / events | `opportunity.engagement` | `engagements/` |
| Decision | `opportunity.decision` | `decisions/` |

JD bodies remain in Role Market. Work facts remain in Career Evidence.

## Lifecycle

```text
Company: pending-review -> reviewed -> stale -> pending-review
Scope: draft -> verified | conservative -> superseded
Engagement: active <-> paused -> closed
Decision: draft -> reviewed -> decided -> superseded
```

An Engagement requires a Company reference. `application_state: applied` requires
an `application-submitted` event; a recruiter-contact event cannot imply it. Exactly
one active Engagement may set `is_current_employment: true`.

Company portfolio/research dimensions and Engagement decision/review dimensions
remain typed Opportunity fields. They are independent from event-backed
application state and may be displayed through dedicated Bases without becoming
a second authority.

## Change Rules

Separate fact, inference, and unknown. Record external events only from direct
evidence or explicit user report. Keep Company freshness, Engagement stage,
application state, and decision state independent.

## Completion Gate

Opportunity work is complete when entity resolution, event chronology, application
state, current-employment uniqueness, decision rationale, blockers, and references
validate. External action remains separately authorized.
