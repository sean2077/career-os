---
name: career-communication
description: Compose, tailor, validate, audit, and export evidence-backed career communication, including resumes, profiles, cover letters, application answers, recruiter or networking messages, unsent negotiation wording, and interview-facing public surfaces. Use for audience-specific wording, JD tailoring, publication-safe claims, or shareable PDF exports.
---

# Career Communication

Apply `../_shared/career-contract.md`. This Skill owns
`70-career-communication` and `communication.profile`, `communication.resume`,
`communication.audit`, and `communication.export`. Before a canonical write or
gate judgment, load
`system/seeds/authorities/70-career-communication.md`. Validated resumes use
approved Claims; application-ready resumes also require the exact reviewed JD.
Exports require the appropriate authorization, policy, and content hash.

## Modes

- **compose** creates audience-specific wording from approved evidence.
- **tailor** selects and orders supported claims for an exact target JD.
- **validate** checks support, contribution boundaries, visibility, and privacy.
- **audit** preserves a dated, fingerprinted review of maintained communication
  roots without granting readiness or claim approval.
- **export** invokes the deterministic resume export boundary.

## Workflow

1. Resolve audience, purpose, and the smallest approved Claim set by ID. For an
   unsent cover letter, application answer, recruiter, networking, follow-up, or
   negotiation draft, stay answer-only unless the wording is reusable as a
   maintained Profile or the user asks to save it.
2. Keep wording proportional to evidence and personal contribution. Never invent
   metrics, ownership, production use, application state, or relationship state.
3. In `tailor`, start from the reviewed JD's highest-priority requirements and
   select only claims that materially improve fit; do not rewrite every claim or
   create a projection per JD.
4. Keep one project projection at
   `profiles/project-projections/<project-key>.md` when purpose,
   audience/identity policy, and lifecycle match. Claims, Audits, Resume roots,
   and Export receipts remain separate.
5. Resolve page pressure through evidence-backed selection, order, or wording
   before presentation changes. Do not add profile-specific typography or
   page-break exceptions solely to force a page count.
6. Use `evidence-auditor` for application/public validation, a disputed claim,
   or a material audit—not routine wording or formatting. Validate its result;
   the reviewer reports blockers while this Skill alone adjudicates wording.
7. Build an internal preview only when layout or rendering must be inspected.
   `career-os resume export` needs explicit preview approval; authorization in
   the current request is sufficient and must not be requested twice.
8. Application export additionally needs prompt-time authorization and a
   matching application-ready Resume with approved claims, exact JD, and
   identity profile. A successful PDF is never permission to send or upload it.

Keep JD screening, opportunity decisions, application events, and readiness in
their own authorities. Write only Career Communication records and generated
exports; never place framework branding or Skill attribution in user materials.
