# Role Market

This user-owned authority maintains market channels, role directions, and dated
JD Notes. Each JD Note keeps protected source text and screening judgment in
separate sections. Original text, quotations, external IDs, URLs, and provenance
remain protected source evidence.

## Key Terms

- **Channel**: ranked and dated access path for discovering roles; it never proves
  Company quality, application state, or an outcome.
- **Role Direction**: stable responsibility cluster for discovery and comparison.
- **JD**: dated external role instance whose one Note contains source fidelity,
  screening metadata, a protected source-text section, and a reassessment section.
- **Screening**: the evidence-fit, preference, priority, gaps, and next-action
  activity within a JD Note; it is not a separate record.
- **Frozen source**: retained as-of provenance that does not own current policy.
- **Stale**: age state independent from screening quality or application state.

## Authority Map

| Record | Kind | Suggested location |
| --- | --- | --- |
| Market Channel | `market.channel` | `channels/` |
| Role Direction | `market.direction` | `directions/` |
| JD instance | `market.jd` | `jds/YYYY-MM/` |

Company quality and application progress belong to Opportunity Decision. Readiness
and resume tailoring remain separate downstream judgments.

## Lifecycle

```text
Channel: active -> stale | retired; stale -> active | retired
Direction: candidate -> reviewed -> active | rejected -> superseded
JD: captured -> screened -> reviewed | skipped
```

Each JD records its collection, employer label, location and compensation when
the source explicitly provides them. `is_stale` records age independently from
the screening lifecycle. When a Recruiting Scope has been resolved, the JD
carries a `recruiting-scope` reference; an absent reference remains unresolved
and cannot be guessed from display names.
Source status is one of `full`, `partial`, `summary-only`, or `unavailable`;
incomplete sources explicitly name their missing sections. Every JD stores the
SHA-256 of the exact protected source-text section so later source drift is
detected while the reassessment section remains editable.

## Change Rules

Do not rewrite source prose to fit a preferred narrative. Separate explicit
requirements from interpretation. Never derive Company identity, application state,
readiness, or Strategy from a display name or match score.

## Completion Gate

Market work is complete when channel freshness, source fidelity, dates,
direction, evidence fit, priority, gaps, references, and review state are explicit
and internally valid in the same JD Note. Dedicated Bases are retrieval views
only; they never create a second factual authority.
