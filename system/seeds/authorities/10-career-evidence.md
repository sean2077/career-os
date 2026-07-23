# Career Evidence

This user-owned authority records what happened, what the user contributed, and
what supports a reusable story or claim. Record bodies and filenames may use any
language; schema keys, relation names, and enum values remain English.

## Key Terms

- **Capture**: provenance-preserving raw material that is not yet formal evidence.
- **Work Record**: attributable account of work, contribution boundaries, and support.
- **Experience Story**: reusable account of decisions, tradeoffs, and failure handling.
- **Claim**: audience-eligible statement with explicit support, risk, and allowed uses.
- **Evidence strength**: support for a Work Record, separate from claim approval.

## Authority Map

| Record | Kind | Suggested location |
| --- | --- | --- |
| Raw Capture | `evidence.capture` | `_inbox/` |
| Work Record | `evidence.work` | `work/` |
| Experience Story | `evidence.story` | `stories/` |
| Claim | `evidence.claim` | `claims/` |

Bases, Canvas files, dashboards, summaries, and backlinks are views only. They
never become evidence or claim authority.

Collection and project `README.md` files are navigation only. Importers must not
classify them as Work merely because they live below `work/`; only an attributable
account with contribution and support satisfies the Work interface.

## Lifecycle

```text
Capture: needs-debrief <-> ready-to-archive -> archived
Work: draft -> grounded -> verified
Story: draft -> reviewed
Claim: draft -> reviewed -> approved | rejected
                         approved -> withdrawn
```

An archived Capture requires a `represented-by` reference to grounded Work. An
approved Claim requires a `supported-by` reference to grounded Work or a reviewed
Story, shareable/public visibility, and an external allowed use. Raw Capture alone
cannot approve a Claim.

## Change Rules

Preserve provenance, attribution, dates, contribution boundaries, sensitivity,
and raw material. Do not turn plans, learning, interview fluency, generated output,
or team results into personal production evidence. Cross-authority consumers link
stable IDs instead of copying facts.

## Completion Gate

Evidence work is complete only when ownership, support, uncertainty, visibility,
references, and lifecycle state validate without inventing magnitude or impact.
