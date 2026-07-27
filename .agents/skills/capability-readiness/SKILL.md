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

## Interview preparation model

- **Public Surface** points to the current Career Communication claim/profile
  and optional JD. Resolve exact wording when practice starts; do not make a
  Readiness note a second claim authority.
- **Minimum Credible Narrative** is a default 60–90 second opening covering the
  problem, personal responsibility, key tradeoff, result, and boundary, with
  at most two or three deliberate **Disclosure Hooks**.
- Rank hooks by role relevance, contribution differentiation, and available
  support. Evidence posture changes wording and confidence, not eligibility:
  user-confirmed real work may be practiced without a complete artifact trail,
  but inference and unknowns must remain explicit.
- **Universal First Questions** come from the public surface or ordinary
  industry expectations for its named domain. **Triggered Follow-up Branches**
  may use project-specific nouns and mechanisms only after an exact hook or
  prior candidate answer makes them visible.
- Put formulas, defaults, source locations, and low-probability details in a
  **Detail Appendix**. They are available on demand, not presumed interviewer
  knowledge.

## Workflow

1. Name the target baseline or JD delta and the evidence required to pass.
2. Keep one living draft at `notes/projects/<project-key>.md` for reusable
   preparation about one independent system project. Use a stable project key,
   not a date, and merge only material with the same purpose and lifecycle.
   Keep papers, technical topics, cross-project routing, dated Sessions,
   Assessments, and Gaps as separate records. A living draft never grants
   readiness.
3. Build each project living draft as Public Surface, Minimum Credible
   Narrative, Universal First Questions, Disclosure Hooks, Triggered Follow-up
   Branches, and Detail Appendix. Keep knowledge notes, practice artifacts, and
   production evidence distinct.
4. Select zero to three hooks for the current target instead of cloning a note
   per JD. Preserve the linked Evidence posture internally, but never send it,
   expected answers, private notes, or hidden rubrics to the Blind Interviewer.
5. For strict practice or assessment, dispatch `evidence-auditor` with only the
   Internal Evidence Packet and `blind-interviewer` with only the Public
   Interview Packet. Validate each JSON result with `career-os skills
   validate-reviewer` before adjudication.
6. Preserve questions, answers, scoring criteria, reviewer results, and
   unresolved blockers. Do not repair an answer after the fact. If either
   reviewer is unavailable, invalid, or receives leaked internal material,
   continue only through an explicit fallback that cannot produce `ready`.
7. Derive readiness only when the configured baseline, target delta, required
   sessions, reviewers, and evidence are present.
8. A green tool or completed lab never proves formal interview readiness.

Write only Capability Readiness records. Send new attributable work facts to
Career Evidence and application decisions to Opportunity Decision.
