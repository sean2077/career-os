---
name: capability-readiness
description: Diagnose capability gaps, guide focused learning and paper study, run interview practice, assess evidence-backed readiness, and retest blockers. Use for preparation, active recall, mock interviews, learning plans, or readiness decisions.
---

# Capability Readiness

Read `../_shared/career-contract.md`. This Skill owns
`60-capability-readiness` and the kinds `readiness.gap`, `readiness.note`,
`readiness.session`, and `readiness.assessment`.

Read `system/seeds/authorities/60-capability-readiness.md` for the canonical
terms, lifecycle, and completion gate. Knowledge and practice gaps close only
through a verified passing Retest assessment. Production-evidence gaps close
only through medium or strong grounded Work evidence; learning, papers, labs,
and interview scores cannot substitute for it.

## Modes

- **diagnose** defines a specific gap against a target.
- **learn** uses active recall and practice to close one gap.
- **study-paper** records a source-grounded technical note tied to a gap.
- **practice** runs a coached or strict interview session.
- **assess** evaluates readiness against explicit criteria and evidence.
- **retest** checks previously identified blockers with fresh work.

## Workflow

1. Name the target baseline or JD delta and the evidence required to pass.
2. Keep knowledge notes, practice artifacts, and production evidence distinct.
3. For strict practice or assessment, dispatch `evidence-auditor` with only the
   Internal Evidence Packet and `blind-interviewer` with only the Public
   Interview Packet. Validate each JSON result with `career-os skills
   validate-reviewer` before adjudication.
4. Preserve questions, answers, scoring criteria, reviewer results, and
   unresolved blockers. Do not repair an answer after the fact. If either
   reviewer is unavailable, invalid, or receives leaked internal material,
   continue only through an explicit fallback that cannot produce `ready`.
5. Derive readiness only when the configured baseline, target delta, required
   sessions, reviewers, and evidence are present.
6. A green tool or completed lab never proves formal interview readiness.

Write only Capability Readiness records. Send new attributable work facts to
Career Evidence and application decisions to Opportunity Decision.
