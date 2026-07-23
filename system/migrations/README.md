# Migrations

Migration definitions are system-owned and version-paired. A migration is never selected by directory order: `career-os migrate plan --to VERSION` resolves one explicit source/target pair and emits a hash-bound plan before user data changes.

`record-envelope-1-to-2.json` selects the built-in conservative schema-1 to
schema-2 transform. Planning reads every user record and emits an ordered
operation for each schema-1 file. The transform preserves the body and unknown
legacy fields, resets maturity to a safe initial status, and marks semantic
review as required. Apply and rollback verify the source/result file hashes,
plan hash, project root, and migration-definition hash.

The same plan upgrades an initialized authority README only when its bytes still
represent the exact schema-1 generic template. Customized READMEs are counted in
plan metadata and left untouched; the migration never guesses how to merge
user-owned documentation.
