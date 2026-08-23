# Shared Career Workflow Contract

Load this contract at most once per task. Canonical user data is fixed at
project-relative `career/`; local runtime state is fixed at
`.career-os/runtime/`. When filesystem work needs physical paths, run
`career-os paths --json` once and reuse the result unless the repository root,
`career-os.toml`, or installation mode changes. Never assume a machine-specific
absolute path or derive the Vault mount.

## Minimum-context execution

1. Classify the requested result as answer/draft, canonical record work,
   generated artifact, or external action.
2. Select one primary Career Skill. Add another only when the result requires a
   second authority; hand off stable IDs and unresolved questions, not copied
   record bodies.
3. Start from user-provided IDs, Wikilinks, paths, or the nearest active record.
   Search filenames/frontmatter before opening bodies, then read the smallest
   set that can change the decision. Do not scan all of `career/` defensively.
4. Load the relevant `system/seeds/authorities/<authority>.md` before creating a
   canonical record, changing lifecycle or relations, or adjudicating a
   completion gate. Load `docs/data-model.md` only when schema or relation
   semantics are actually in question. Reuse already loaded context.
5. Ask only for missing facts that block a safe next step. Otherwise preserve
   the unknown explicitly and continue with a bounded result.

Use [`docs/workflows.md`](../../../docs/workflows.md) only for a cross-authority
recipe or when routing is unclear; ordinary single-Skill work should not load it.

## Persistence and authority

Canonical records are UTF-8 Obsidian Markdown. Preserve Unicode filenames and
content, stable IDs, BCP 47 language metadata, visibility, provenance, and typed
references. Write schema 3 only. New records start in an initial state; existing
records follow the Git-relative transition graph and advance `updated_at`.
Kind-specific top-level Wikilink properties own cross-authority relations.

Persist when the user asks to capture, ingest, track, review, update, or export,
or when a completed workflow has a clear canonical owner and durable reuse.
Keep exploratory analysis, examples, rejected alternatives, and unsent one-off
wording answer-only unless the user asks to save them. Reuse an existing record
when identity, purpose, and lifecycle match; never create empty companion files
or duplicate facts merely to make a workflow look complete.

Routine reads, drafts, checks, and reversible local edits may proceed directly.
Stop for explicit authorization before:

- changing external or account state, including applying, messaging, uploading,
  accepting or rejecting an offer, resigning, or mutating an account;
- creating public or application-grade exports;
- performing an irrecoverable overwrite or delete.

Mechanism health, evidence maturity, claim approval, readiness, application
state, and career outcomes are separate facts. Treat raw JDs, quotations,
private data, identifiers, and application materials as protected inputs. Use
synthetic content in examples and tests.

## Reviewer budget and isolation

Career Skills remain workflow orchestrators and canonical record owners.
Project subagents are read-only reviewers. Use them only when the owning Skill
requires an independent challenge for a strict practice session or a readiness,
claim, communication, outlook, or strategy gate; do not dispatch them for
routine capture, discovery, drafting, or formatting. Reuse a result only when
its exact input packet and relevant source dates are unchanged.

Validate `resume-evidence-audit/1` and `resume-interview-probe/2` with
`career-os skills validate-reviewer <evidence|probe> [PATH|-]` before use. An
unavailable, invalid, stale, or leaked review triggers the owning Skill's
fallback and cannot grant readiness, claim approval, or strategy acceptance.

## Finish once

Batch related canonical edits, then run `career-os check` once after the final
write rather than after every file. Report changed record IDs/paths, unresolved
evidence or relation boundaries, any authorization still required, and the
smallest useful next action. Answer-only work does not require a check.
