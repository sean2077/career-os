# Capability Readiness

This user-owned authority maintains gaps, learning/practice notes, sessions,
assessments, retests, and derived readiness. It never rewrites Experience Stories
or converts study and demonstrations into production ownership.

## Key Terms

- **Gap**: missing knowledge, practice result, or production evidence against a target.
- **Session**: coached, strict, or retest interaction with preserved inputs and outcome.
- **Assessment**: evaluation against explicit criteria and an input fingerprint.
- **Retest**: fresh targeted assessment of a previously identified blocker.
- **Production-evidence gap**: missing real-world ownership that learning cannot close.

## Authority Map

| Record | Kind | Suggested location |
| --- | --- | --- |
| Gap | `readiness.gap` | `gaps/` |
| Learning / paper / practice note | `readiness.note` | `notes/` |
| Interview / retest session | `readiness.session` | `sessions/` |
| Assessment | `readiness.assessment` | `assessments/` |

## Lifecycle

```text
Gap: open -> learning | practice | blocked
learning / practice -> retest -> open | closed
blocked -> open | closed
Note: draft -> reviewed
Session: planned -> completed | invalidated
Assessment: draft -> assessed -> superseded
```

Knowledge and practice gaps close only through a verified passing Retest.
Production-evidence gaps close only through medium/strong grounded Work evidence.
Fallback reviewers, green tooling, labs, demos, and fluency cannot close those gates.

Sessions preserve their date, target, scope, attempt, scored dimensions, verdict,
reviewer state, fingerprint, and blockers. Gaps preserve priority and typed closure
references. A Capability Base may join these records to Evidence Stories and
Communication Audits by reference but cannot promote either authority.

## Change Rules

Preserve strict questions, answers, criteria, reviewer state, fingerprint, and
blockers. Reference Evidence-owned stories without repairing them after an
assessment. Keep knowledge, practice, and production evidence distinct.

## Completion Gate

Readiness work is complete when target, gap type, parent refs, reviewer/fingerprint,
closure evidence, and retest outcome validate. Unmet production ownership stays open.
