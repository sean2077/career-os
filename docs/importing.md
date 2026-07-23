# Legacy Repository Imports

`career-os import` migrates reviewed files from a clean legacy Git repository
into the configured user-owned data root. It is intentionally separate from
`career-os migrate`, which upgrades records already inside one Career OS data
root.

## Manifest contract

Before authoring import batches, `LegacyInventoryRuleSet` classifies every
tracked entry at one clean source commit. Rules are reviewed in order and the
first matching portable POSIX glob supplies the one recorded asset type and
disposition. A tracked path without a matching rule fails. Schema-version 2
rules are segment-aware: `*`, `?`, and character classes match inside one path
segment, while a complete `**` segment matches zero or more segments. For
example, `docs/10-career-evidence/*` does not match
`docs/10-career-evidence/project/README.md`; use
`docs/10-career-evidence/**` for descendants. Schema-version 1 rules retain
their historical `fnmatch` behavior, including `*` matching `/`, so committed
inventories remain reproducible. The resulting
`LegacyMigrationInventory` is deterministic and records the path, SHA-256,
byte size, Git mode/OID, hash basis, matched rule, and disposition. Regular
files hash their worktree bytes; symlinks hash the canonical Git link payload;
gitlinks hash their pinned object ID. This allows projections and unsupported
gitlinks to remain accountable without following them or importing them.

```text
career-os import inventory --source-root <legacy-repository> --rules <rules.json> --output <data-root>/.provenance/migration-inventory.json
career-os import verify-inventory --source-root <legacy-repository> --rules <rules.json> --inventory <data-root>/.provenance/migration-inventory.json
```

Inventory output must be JSON inside the configured data root. The command is
idempotent when the existing bytes are identical and refuses to overwrite a
different file. Verification regenerates the inventory from the clean source
and reviewed rules and requires an exact match.

## Semantic file review

The semantic-review control keeps one item per frozen source asset. It may point
to one or more real target files and optional Obsidian heading/block anchors;
sections are not promoted into separate review records or a second Career
authority. One-to-many targets are valid only when canonical authority, record
kind, or independent lifecycle actually differs.

```text
career-os import verify-review --source-root <legacy-repository> --rules <rules.json> --inventory <inventory.json> --review <data-root>/.provenance/semantic-file-review.json --public-root . --root .
```

`public-framework` identifies system-owned targets in the public
`standalone-framework` checkout. In `split-downstream` mode, that scope resolves
against the separately reviewed framework repository; it never includes
`career/`, identity, attachments, or local fonts.

An import batch begins with a `LegacyImportManifest` that pins the source repository
commit and the SHA-256 of every classified source file. Each entry has exactly
one disposition:

- `migrate-exact` copies the source bytes to exactly one declared output;
- `migrate-transform` copies one or more separately prepared, hash-pinned
  outputs while retaining one source disposition and hash in provenance;
- `replace-by-public` records the system-owned, public-bound replacement;
- `retain-archive-only` preserves the source only in the legacy archive;
- `upstream-gap` records a blocking or deferred public capability identifier;
- `retire` records an intentionally discontinued asset.

Source, prepared, target, and provenance paths are relative POSIX paths. An
absolute path, backslash, traversal segment, duplicate source, duplicate target,
changed source commit, dirty source worktree, or hash mismatch fails before a
plan is written.

Prepared transformed files live in ignored local state such as
`.career-os/import-staging/`; the tracked manifest contains hashes and mapping
metadata, never a second copy of private record bodies.

Multiple outputs are necessary when a legacy monolith contains authorities
that the current schemas keep separate, such as one note containing both a JD
and a Company diligence record. JD source and screening judgment remain one
`market.jd` output with separate Markdown sections. Every output declares its
own target path, prepared path/hash, and optional target kind/UUID. The importer
never selects a lifecycle state itself. Exact imports remain one-to-one.

Schema-version 2 manifests are correction batches. They require a non-empty,
unique `supersedes_manifest_ids` list identifying the reviewed manifests whose
outputs are being corrected, and may declare `retire_targets`. Every retired
target has a Vault-relative `target_path`, the exact `expected_sha256` reviewed
during planning, and a non-empty reason. A correction can write replacement
outputs, retire wrong outputs, or do both; the same path cannot be both written
and retired. Schema-version 1 manifests remain loadable with their original
contract and produce schema-version 1 provenance.

## Plan, apply, and rollback

```text
career-os import plan --source-root <legacy-repository> --manifest <manifest.json>
career-os import apply --plan <emitted-plan.json>
career-os import rollback --plan <applied-plan.json>
```

Planning is read-only. It verifies the clean source commit and every classified
file, then emits an ignored `OperationPlan`. For a correction, planning also
requires every retired target to exist at its declared hash. Applying rechecks
the manifest, source commit, source/prepared hashes, and expected target hashes
before the first write or delete. Text, binary, and retired files use the same
backup and rollback boundary. A concurrent change produces a stale-target
failure before mutation. Reapplying an applied plan is idempotent; rollback
restores retired files from the plan backup and refuses a written target changed
after apply.

The final operation writes `MigrationProvenanceMap` JSON under the user data
root. It connects source repository, commit, path, and hash to the resulting
target path/record ID or non-migration disposition. JSON provenance is not a
career record and is not parsed as Markdown authority. Correction provenance is
schema-version 2 and additionally records `supersedes_manifest_ids` plus every
retired target path, expected hash, reason, and hash-verification mode. It does
not rewrite the superseded manifest or provenance file.

An import never infers record kind, lifecycle status, evidence maturity,
readiness, application state, current employment, or visibility. A human or
Agent prepares schema-valid transformed records before planning.
