# Career Outlook

This user-owned authority maintains dated external signals, reviews, and reviewed
career theses. It informs Strategy by reference but never owns personal evidence,
market queues, opportunity state, or plans.

## Key Terms

- **External Signal**: dated policy, labour, industry, or technology evidence.
- **Outlook Review**: time-bounded synthesis across three independent gates.
- **Reviewed Thesis**: accepted judgment with confidence, horizon, and invalidation.
- **Invalidation condition**: evidence or elapsed condition requiring review.
- **Pending**: watchlist state outside current strategic authority.

## Authority Map

| Record | Kind | Suggested location |
| --- | --- | --- |
| External Signal | `outlook.signal` | `signals/` |
| Dated Review | `outlook.review` | `reviews/` |
| Thesis | `outlook.thesis` | `theses/` |

## Lifecycle

```text
Signal: captured -> verified | rejected; verified -> stale
Review: pending -> reviewed | rejected; reviewed -> superseded
Thesis: candidate -> reviewed | rejected; reviewed -> superseded
```

A reviewed Review requires `personal-fit`, `market-revealed`, and
`independent-external` gates to be satisfied with corresponding required references.
A reviewed Thesis requires a reviewed source Review. Both reviewed states require
`review_authority: user`; no Agent self-promotes pending Outlook into Strategy.

## Change Rules

Record event date, publication date, retrieval date, source class, uncertainty,
scope, confidence, and disconfirming evidence. One headline, benchmark, Company, or
JD can enter a watchlist but cannot independently justify a career pivot.

## Completion Gate

Outlook work is complete when as-of boundaries, freshness, all three evidence gates,
confidence, rationale, invalidation conditions, review state, and references validate.
