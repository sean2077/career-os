# Legacy Repository Imports

`career-os import` copies reviewed, hash-pinned files from a clean legacy Git
repository. It remains separate from `career-os migrate`, which upgrades
records already inside fixed `career/`.

## One reviewed manifest

An operator-written `LegacyImportManifest` pins the source repository, clean
commit, source path and SHA-256, asset type, disposition, and any declared
outputs. Supported dispositions are `migrate-exact`, `migrate-transform`,
`replace-by-public`, `retain-archive-only`, `upstream-gap`, and `retire`.

Exact imports have one output. Transformed imports reference separately
prepared, hash-pinned files, normally under ignored `.career-os/import-staging/`.
The importer never chooses record kind, status, evidence maturity, readiness,
visibility, application state, or current employment.

Portable relative POSIX paths are required. Absolute paths, backslashes,
traversal, duplicate sources or targets, a dirty or changed source repository,
and any hash mismatch fail before a plan is written.

## Plan, apply, verify, and rollback

```text
career-os import plan --source-root <legacy-repository> --manifest <manifest.json>
career-os import apply --plan <plan.json>
career-os import verify --plan <plan.json>
career-os import rollback --plan <plan.json>
```

Planning is read-only and prints each source, target, disposition boundary,
before hash, and after hash through the resulting operation list. Plans,
backups, results, and verification state live only under
`.career-os/migrations/`.

Apply rechecks the manifest, source commit, source/prepared hashes, and every
expected target hash before mutation. Verify checks the currently planned,
applied, or rolled-back state. Rollback restores replaced files from the
ignored backup and refuses to overwrite a target changed after apply.

The operation does not create a tracked inventory, semantic attestation,
provenance map, or completion ledger. Git stores long-term business-record
history. A successful import only proves byte-level execution of the reviewed
manifest; it never asserts semantic correctness.
