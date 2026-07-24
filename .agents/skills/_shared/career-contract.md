# Shared Career Workflow Contract

Canonical user data is fixed at project-relative `career/`, and local runtime
state is fixed at `.career-os/runtime/`. Use `career-os paths --json` to
discover the physical project, fixed roots, build root, and Vault mount; never
assume a machine-specific absolute path or derive the Vault-relative mount.

Canonical user records are UTF-8 Obsidian Markdown. Preserve Unicode filenames
and content, stable record IDs, BCP 47 language metadata, visibility, and typed
references. Framework authority contracts live under `system/seeds/authorities`;
initialized user copies live in the corresponding `career/` README. Read both
`docs/data-model.md` and the relevant authority contract before a write.
Cross-authority work links stable IDs; it does not copy or silently move facts
between authorities.

Write record schema 3 only and use the declared kind lifecycle. New records
start in an initial state; changes to an existing record follow the Git-relative
transition graph and advance `updated_at`. Store cross-authority relations in
kind-specific top-level Wikilink properties. A migrated record may keep
`migration_review: required` and `legacy_fields` only until the user confirms
the mapping.

Routine local reads, drafts, checks, and reversible edits can proceed directly.
Stop for explicit authorization before:

- changing external or account state, including applying, messaging, uploading,
  accepting an offer, resigning, or mutating an account;
- creating public or application-grade exports;
- performing an irrecoverable overwrite or delete.

Mechanism health, evidence maturity, claim approval, readiness, application
state, and career outcomes are separate facts. Never infer one from another.
Treat raw JDs, direct quotations, private data, external identifiers, and
application materials as protected inputs. Use synthetic content in examples
and tests.

## Read-only reviewer boundary

Career Skills remain workflow orchestrators and canonical record owners.
Project subagents under `.agents/subagents/` are read-only reviewers: they may
return an evidence audit, interview probe, or dated strategy brief, but they do
not write records, approve claims, grant readiness, accept strategy, or
authorize an action.

Keep Public Interview Packets isolated from Internal Evidence Packets. Before
using `resume-evidence-audit/1` or `resume-interview-probe/1`, run
`career-os skills validate-reviewer <evidence|probe> [PATH|-]`. An unavailable
reviewer, invalid output, or leaked packet triggers the owning Skill's
documented fallback. Fallback work may continue, but it cannot grant readiness,
claim approval, or strategy acceptance.

After an authorized write, run `career-os check`. Report changed canonical
records and any unresolved evidence, authorization, or relation boundary.
