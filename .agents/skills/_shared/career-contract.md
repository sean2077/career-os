# Shared Career Workflow Contract

Use `career-os paths --json` to resolve the project, data, Vault, runtime, and
build roots. Never assume `career/` or a machine-specific absolute path.

Canonical user records are UTF-8 Obsidian Markdown. Preserve Unicode filenames
and content, stable record IDs, BCP 47 language metadata, visibility, and typed
references. Framework authority contracts live under `system/seeds/authorities`;
initialized user copies live in the corresponding data-root README. Read both
`docs/data-model.md` and the relevant authority contract before a write.
Cross-authority work links stable IDs; it does not copy or silently move facts
between authorities.

Write record schema 2 only. Preserve a complete `status_history` whenever a
record has left its initial state, and use only the declared kind lifecycle. If
schema-1 records exist, create and review a `career-os migrate plan --to 2`
before applying it. A migrated record stays `migration_review: required` until
the user has confirmed its conservative defaults and preserved legacy fields.
Every typed `host_ref` must have a matching native wikilink in the Markdown body.

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

After an authorized write, run `career-os check`; add `--host` only when the
actual surrounding Vault must resolve host references. Report changed canonical
records and any unresolved evidence, authorization, or reference boundary.
