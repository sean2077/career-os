# Data Model

Every canonical Markdown record uses record schema 3: a shared Pydantic
envelope plus a kind-specific payload and lifecycle. Bodies and filenames are
free-form Unicode; enum values, relation keys, and schema keys remain English.

## Record envelope

Every record has a UUID4 `id`, `kind`, `schema_version: 3`, timezone-aware
`created_at` and `updated_at`, `visibility`, and its current typed `status`.
`languages`, `title`, `tags`, and `aliases` remain optional and are omitted
when empty. Unknown top-level fields are rejected.

The 25 record kinds remain divided among Career Evidence, Career Strategy,
Role Market, Opportunity Decision, Career Outlook, Capability Readiness, and
Career Communication. Their complete fields and enums are generated from the
runtime Pydantic models into `system/schemas/record-envelope.schema.json`.

An `opportunity.company` may carry `display_name_zh` and `display_name_en` for
language-specific Workbench presentation. These labels may match when a brand
has no localized form. `canonical_name` remains the entity-resolution
authority and may include a legal or group name that is unsuitable as a short
table label.

## Lifecycle validation

Each kind retains its initial states, transition graph, and semantic gates.
A new Git path must begin in one of that kind's initial states. For an existing
schema-3 path, `career-os check` compares the worktree record to `HEAD`: a
status change must be an allowed edge and must advance `updated_at`.

Git history is the persistent status history. Records no longer duplicate it
in a `status_history` array. Domain-specific reasons and evidence remain in
the body or owning fields.

Cross-record checks still enforce the important boundaries: approved Claims
need grounded Work or a reviewed Story; Strategy cannot consume pending Outlook
authority; reviewed Outlook gates need the three independent signal classes;
readiness closure remains fail-closed; only one active started employment can
be current; and application exports require reviewed targets, identity policy,
approved Claims, and explicit authorization.

## Obsidian relation properties

Relations are kind-specific top-level properties whose names use `snake_case`.
One-to-one relations are quoted Wikilink scalars; one-to-many relations are
quoted Wikilink lists:

```yaml
target_jd: "[[career/30-role-market/jds/example-role]]"
uses_claim:
  - "[[career/10-career-evidence/claims/example-claim]]"
```

The target record supplies its UUID, so the referring record does not repeat a
`target_id`. The Pydantic model owns cardinality; `career-os check` resolves the
Wikilink from the configured Vault, verifies the target kind and required
status, and rejects missing or escaping targets. Links in the Markdown body
remain useful narrative navigation but are not a second machine contract.
Obsidian Bases can display the domain properties directly and use `file.links`
for outgoing-link views.

## Resume roots and claim support

A `communication.resume` identifies a handwritten TeX root by `root_name` and
owns its audience, export policy, `uses_claim`, `target_jd`, and
`identity_profile` relations. Every exported Claim must be approved, externally
usable, shareable or public, and linked through `supported_by` to grounded Work
or a reviewed Story. Supporting evidence may remain private.

## Migration review

`career-os migrate plan --to 3` creates a hash-bound `OperationPlan` under
`.career-os/migrations/`. `apply`, `verify`, and `rollback` share the same
ignored backup and receipt boundary. The schema-2-to-3 transform removes
duplicated reference arrays and status history, converts relation names to
top-level Wikilinks, and preserves the Markdown body except for the retired
machine-owned `## Authority links` section.

Unresolved imported data may temporarily carry `migration_review: required`
and `legacy_fields`. Confirmation removes both fields; no `completed` marker
or tracked provenance ledger is written. Successful tooling proves only that
the declared operation and schemas are consistent, not that a semantic
judgment is correct.
