---
name: career-communication
description: Compose, tailor, validate, and export evidence-backed career communication, including resumes and audience-specific profiles. Use for resume writing, JD tailoring, recruiter language, publication-safe claims, or shareable PDF exports.
---

# Career Communication

Read `../_shared/career-contract.md`. This Skill owns
`70-career-communication` and the kinds `communication.profile`,
`communication.resume`, `communication.audit`, and `communication.export`.

Read `system/seeds/authorities/70-career-communication.md` for the canonical
terms, lifecycle, and completion gate. Validated resumes use only approved Claim
records. Application-ready resumes also require an exact reviewed target JD;
generated exports require explicit authorization, a content hash, and the
appropriate preview or application policy.

## Modes

- **compose** creates audience-specific wording from approved evidence.
- **tailor** selects and reorders supported claims for a target JD.
- **validate** checks claim support, visibility, privacy, and artifact policy.
- **audit** preserves a dated, fingerprinted review of one or more maintained
  communication roots without granting readiness or claim approval.
- **export** invokes the deterministic resume export boundary.

## Workflow

1. Resolve the intended audience and read approved Career Evidence claims by ID.
2. Keep wording proportional to the underlying evidence and contribution
   boundary. Never invent metrics, ownership, production use, or application
   state.
3. For one project, keep target routing and candidate wording in one
   `profiles/project-projections/<project-key>.md` living profile when purpose,
   audience/identity policy, and lifecycle are the same. Split only when those
   boundaries can change independently; keep Claims, Audits, Resume Roots, and
   Export receipts separate.
4. Resolve overflow, page-count, and weak-pagination problems through
   evidence-backed content selection, ordering, or wording before changing
   presentation. Do not add export-profile-specific font size, line spacing,
   margins, or page-break exceptions solely to force a page count; profile
   differences are limited to explicit identity, privacy, watermark, and export
   policy.
5. In validate or audit mode, the Skill may dispatch `evidence-auditor` with an
   Internal Evidence Packet. Validate `resume-evidence-audit/1` before use; the
   reviewer reports boundaries and blockers, while this Skill alone adjudicates
   wording and owns Communication records. Invalid or unavailable review falls
   back without approving any claim.
6. Keep tailoring separate from JD screening, opportunity decisions, application
   tracking, and interview readiness.
7. Use `career-os resume build` for internal preview. Use `career-os resume
   export` only after explicit approval to create a shareable preview artifact;
   it defaults to the `general` root and an automatic `build/share/` destination.
   Approval stated in the current request satisfies this preview gate; do not
   ask for duplicate authorization. Public publication and application export
   remain separate hard gates.
8. Application export requires explicit prompt-time authorization followed by
   `career-os resume export application`, plus a matching application-ready
   Resume record with approved evidence-backed claims, target JD, and identity
   profile. A successful PDF build is not permission to send or upload it.

Write only Career Communication records and generated exports. Never place Skill
attribution, promotional text, or framework branding inside user resumes.
