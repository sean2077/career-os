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
- **Public Surface**: the current public claim/profile and optional JD an
  interviewer can see before the candidate answers.
- **Visible Basis**: the exact resume/JD excerpt or prior candidate-answer
  excerpt that makes one current question causally available.
- **Minimum Credible Narrative**: a 60–90 second project opening covering
  problem, responsibility, tradeoff, result, and boundary, with at most two or
  three deliberate Disclosure Hooks.
- **Triggered Follow-up Branch**: a question sequence opened by an exact public
  surface, disclosure hook, or prior candidate answer.

## Authority Map

| Record | Kind | Suggested location |
| --- | --- | --- |
| Gap | `readiness.gap` | `gaps/` |
| Learning / paper / practice note | `readiness.note` | `notes/` |
| Interview / retest session | `readiness.session` | `sessions/` |
| Assessment | `readiness.assessment` | `assessments/` |

Reusable preparation for one independent system project lives in one stable
`notes/projects/<project-key>.md` living draft. Merge only material with the same
purpose and lifecycle. Papers, technical topics, cross-project routing, dated
Sessions, Assessments, and Gaps remain separate records. A living draft never
grants readiness.

## Interview Preparation Model

A project living draft is a **Project Interview Map**, ordered as Public
Surface, Minimum Credible Narrative, Universal First Questions, Disclosure
Hooks, Triggered Follow-up Branches, and Detail Appendix.

Public Surface references the current Career Communication profile and optional
JD rather than copying mutable public wording into Readiness. Universal First
Questions are available from that surface or ordinary industry expectations for
the named domain. Project-specific modules, parameters, mechanisms, and internal
nouns belong only in a branch opened by an exact candidate phrase or prior
answer. Formulae, defaults, source locations, and low-probability details remain
available in the appendix without being treated as likely first questions.

Choose up to two or three hooks by role relevance, contribution
differentiation, and available support. Support is a descriptive **Evidence
Posture**, not a hard speaking gate: user-confirmed real work may be practiced
when artifacts are incomplete, while source-backed facts, user confirmation,
engineering inference, and unknowns retain distinct wording and boundaries.
Evidence posture, private notes, expected answers, and hidden rubrics never
enter a Public Interview Packet.

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
This formal closure gate does not prohibit practicing a user-confirmed
experience whose artifact trail is incomplete.

Sessions preserve their date, target, scope, attempt, scored dimensions, verdict,
reviewer state, fingerprint, and blockers. Gaps preserve priority and typed closure
references. A Capability Base may join these records to Evidence Stories and
Communication Audits by reference but cannot promote either authority.

## Change Rules

Preserve strict questions, answers, criteria, reviewer state, fingerprint, and
blockers. Reference Evidence-owned stories without repairing them after an
assessment. Keep knowledge, practice, and production evidence distinct. Resolve
the exact public wording when practice starts, ask universal questions only
from a visible public/domain basis, and require an explicit hook or prior answer
before entering a project-specific branch.

## Completion Gate

Readiness work is complete when target, gap type, parent refs, reviewer/fingerprint,
closure evidence, and retest outcome validate. Unmet production ownership stays open.
