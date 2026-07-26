# Changelog

All notable changes to Career OS are documented here.

## [Unreleased]

## [v0.6.0] — 2026-07-26

### Added

- Added optional QuickAdd choices for reviewing the active JD, Company, or
  Engagement and for recording one explicit Engagement event. The scripts
  preview the complete write, detect concurrent changes, fail closed on missing
  prerequisites, and never send an application, message, upload, account
  change, Offer decision, or resignation.
- Added localized interview-pipeline views for open applied, interviewing, and
  Offer-stage Engagements.

### Changed

- Split the monolithic checker into focused internal modules while preserving
  the public CLI, added project-relative paths to reported issues, and reduced
  full-check Git reads from one process per record to two batched calls.
- Replaced duplicated homepage prose in the checker with fail-closed SHA-256
  locks under `system/homepage-lock.json`.
- Let linked Git worktrees inherit the primary checkout's read-only Vault
  install context while mapping project-mounted paths back to the current
  worktree.
- Made signed-in BOSS browsing explicitly user-operated. Role Market accepts a
  user-selected URL, anonymously accessible content, pasted JD text, or
  screenshots; it does not control the signed-in page or handle session
  material.
- Made human-readable check output escape unrepresentable Unicode paths instead
  of failing on restricted Windows console encodings.

## [v0.5.0] — 2026-07-25

### Changed

- Renamed the root Obsidian entry points to `Career Home.md` and `职业主页.md`
  so they are not mistaken for the surrounding Vault's own homepage.
- Clarified that no-argument `resume export` selects the resume named
  `general` and exports it with the `preview` profile.

### Migration

- Update external Obsidian links or embeds that target `Home.md` or `主页.md`
  to the new filenames. Career OS initialization still never creates,
  overwrites, or renames either system-owned homepage.

### Boundaries

- The filename change affects system-owned navigation assets only. It does not
  migrate or rewrite user-owned career records.

## [v0.4.0] — 2026-07-25

### Added

- Added one source-owned BCP 47 language per resume root through the optional
  `language` document-class setting, defaulting to `en`.
- Added portable automatic export filenames that bind the human-facing name,
  resume track, preview/application profile, source language, UTC date, and
  four-character uppercase hexadecimal random ID.

### Changed

- Made `resume export` default to the `general` preview under `build/share/`;
  `resume export application` is now the explicit application-grade CLI
  confirmation, while the former flags remain hidden compatibility inputs.
- Tightened Career Communication guidance around content-first pagination and
  the distinction between internal builds and shareable exports.
- Linked README previews directly to their full-size reviewed PNG assets while
  preserving the tracked Canvas sources.

### Fixed

- Preserved reviewed HTTPS, application-profile `mailto:`, and internal PDF
  links in exported resumes while rejecting attachments, additional actions,
  unsafe URI schemes, and preview-profile mail links.
- Unified the automatic filename, projected PDF export ID, and receipt on the
  same four-character random segment.

### Security

- Re-reviewed the three changed resume test blobs as synthetic-only and
  appended their exact hashes to the guarded fixture policy.
- Re-ran the complete public-history audit and redacted comparison against the
  private Career Home before publication.

### Boundaries

- Raw `resume build` output remains internal. A successful export does not
  authorize sending, uploading, applying, messaging, or changing an external
  account.

## [v0.3.1] — 2026-07-24

### Fixed

- Removed a stale release-workflow invocation of the deleted redundant
  `system/tests/test_golden_journey.py` wrapper. The workflow still runs the
  complete Python suite, enforces a clean checkout, and executes all repository,
  privacy, Skill, harness, and synthetic resume gates.

### Security

- Re-reviewed the changed release workflow as synthetic-only and appended its
  exact blob hash to the guarded fixture policy.

### Boundaries

- The published `v0.3.0` annotated tag remains immutable. Its failed workflow
  did not create a GitHub Release; this patch is the roll-forward release
  boundary and does not move, delete, or reuse that tag.

## [v0.3.0] — 2026-07-24

### Added

- Added localized Recent Changes Bases to both root homepages. They show the
  ten most recently modified Markdown notes inside the current project without
  treating filesystem timestamps as career evidence or Git history.
- Linked identified-employer JD screening to canonical Company research through
  explicit Role Market and Opportunity Decision composition.

### Changed

- Normalized the paired Obsidian Base YAML while preserving presentation-only
  localization parity and canonical record authority.
- Consolidated redundant downstream tests and documented a maintained test-cost
  budget without weakening project, privacy, resume, or release gates.
- Extended public extraction evidence as an immutable cumulative supplement
  over the original v0.1.0 manifest.

### Fixed

- Preserved schema-2 relationship semantics when field names changed in schema
  3, retired obsolete machine relations without deleting narrative Wikilinks,
  and allowed Market Channel records to omit the optional Career Lane relation.

### Removed

- Removed the Defuddle and OpenCLI Skills, configuration, transport, tests,
  licenses, supply-chain entries, and documentation. Career research now uses
  the seven canonical Career Skills and separately attributable sources.

### Security

- Re-reviewed the changed public CI workflow as synthetic-only and appended its
  exact blob hash to the guarded fixture policy.
- Re-ran the complete public-history audit and redacted comparison against the
  private Career Home before publication.

### Boundaries

- This is a breaking pre-1.0 release. Existing `[research.opencli]`
  configuration is no longer accepted and must be removed before validation.
- Recent Changes is a local navigation view only; it does not grant evidence
  maturity, readiness, application, outreach, or account authority.

## [v0.2.0] — 2026-07-24

### Added

- Added top-level `career-os cleanup`, a dry-run-first command that enumerates
  only known reproducible build, distribution, cache, generated, and temporary
  roots, with human and JSON reports, explicit `--apply`, and content-drift
  protection.
- Added a generated JSON Schema for `career-os.toml` plus explicit schema-2
  project and installation state.
- Added the record-envelope 2-to-3 migration and schema-3 lifecycle validation.
- Added optional, disabled-by-default OpenCLI acquisition for Opportunity
  Decision. Only configured commands that the live registry marks read-only are
  callable; browser, external, plugin, write, and self-repair surfaces remain
  prohibited.

### Changed

- Fixed user data at project-relative `career/` and local runtime state at
  `.career-os/runtime/`; `paths --json` retains both stable output keys.
- Upgraded project configuration and installation state to schema 2 without
  root aliases, and unified initialization, imports, migrations, privacy,
  downstream, resume, and Obsidian adapters on the fixed roots.
- Owner-provided resume font overrides are now resolved by filename without
  configured checksums, so replacing a same-name file requires no configuration
  update. Downloaded system-default fonts remain integrity-verified.
- Replaced generic record reference arrays with schema-owned relation fields,
  Git-relative lifecycle validation, and simpler migration provenance.
- Displayed relationship links by basename in Obsidian Bases and added
  bilingual company names to the company portfolio.
- Extended public extraction evidence so reviewed file deletions are
  hash-bound rather than silently falling outside the snapshot.

### Fixed

- Installed the XeLaTeX packages required by the resume class in public CI.
- Made public-only snapshot tests topology-aware and documented the
  ancestry-independent downstream plan/apply flow for existing private Career
  Home histories.
- Kept superseded migration completions verifiable after an intentional
  downstream topology or Git-history rewrite without mutating historical
  hash-bound evidence.
- Prevented lifecycle transition labels such as `Company: draft -> reviewed`
  from becoming false-positive private company candidates while retaining
  exact matching for labeled identity, company, location, and contact values.
- Made the removed `--data-root` regression assertion portable across
  ANSI-styled Typer/Rich CI output.
- Removed obsolete `v0.1.0-rc.*` release notes now that the clean-install-only
  stable MVP is the sole published release line.

### Removed

- Removed `ProjectConfig.data_root`, `ProjectConfig.runtime_root`,
  `InstallState.data_root`, and `init --data-root`; legacy fields fail closed
  and require reinitialization or an explicit local-state rewrite.
- Removed the semantic-review sidecar subsystem, redundant install/vault state
  schemas, and obsolete legacy inventory schemas in favor of record-owned
  schema-3 state and hash-bound operation plans.

### Security

- Re-reviewed every changed guarded resume/privacy test and privacy
  implementation blob against synthetic-only fixtures, then updated the
  append-only fixture policy.
- Re-ran the complete public-history audit and exact, redacted comparison
  against the private Career Home before publication.

### Boundaries

- This is a breaking pre-1.0 release. Legacy project-root aliases fail closed;
  existing records require the explicit schema-2-to-3 migration before full
  validation.
- OpenCLI remains optional and disabled in the public configuration. The
  integration does not grant write, outreach, application, or account authority.

## [v0.1.0] — 2026-07-24

### Added

- Added the Agent-native, local-first Career OS framework with seven distinct
  career authorities, schema-2 records, typed internal and Obsidian references,
  kind-specific lifecycles, deterministic checks, and isolated synthetic
  fixtures.
- Added read-only `blind-interviewer`, `evidence-auditor`, and
  `career-strategy-advisor` subagents with generated Claude Code and Codex
  projections, strict packet contracts, committed JSON Schemas, and
  `career-os skills validate-reviewer`.
- Added single-note JD capture and screening through `market.jd`, including a
  preserved `JD 原文` fingerprint, a required `重新评价` section for screened
  states, and separate Channel and Direction authorities.
- Added root English and Chinese Career Home pages, two common views, two
  Canvas files, one dashboard, and ten paired English/Chinese Workbench Bases.
- Added handwritten XeLaTeX resume roots discovered by name, adjacent
  `identity.tex`, fixed preview/application profiles, a fixed system class, and
  English, Chinese, and multilingual synthetic build fixtures.
- Added hash-bound `downstream plan/apply/validate/rollback` operations,
  protected private paths, exact-tag validation, rollback receipts, and
  fetch-only public-remote safety checks.
- Added a clean-install automated golden journey covering the seven authorities,
  static Obsidian projections, and synthetic preview-export privacy.
- Added deterministic CycloneDX SBOM, notice, Skill lock, font lock, schema,
  release-note, and tag-triggered GitHub Release validation.

### Changed

- Declared the public repository as
  `development_topology = "standalone-framework"`; real career records and
  local identity state remain outside the public snapshot.
- `views build` keeps its existing fields and also reports both root homepages
  and all sixteen static system assets without generating data-root or runtime
  copies.
- Resume commands use `--resume NAME` and the TeX root plus adjacent
  `identity.tex` as the only per-resume configuration surface.
- Cross-platform release gates normalize ANSI-styled CLI help, use a pinned
  minimal TeX Live 2026 package set with automatic CI caching, and materialize
  configurable font filenames before `fontspec` loads the resume class.
- CI runs on `main` and pull requests rather than tags; publication waits for
  successful `main` CI before pushing the release tag, so tag validation restores
  the trusted TeX cache without launching a duplicate tag CI run.
- The canonical public remote is optional in a private downstream; when present
  it must be named `upstream` with push URL exactly `DISABLED`.
- Downstream synchronization adapts the standalone public configuration to the
  existing private installation while preserving its data, runtime, build, and
  language roots.

### Removed

- Removed the `market.screening` record kind; screening belongs to the
  corresponding `market.jd` note.
- Removed per-resume JSON manifests, personal font-profile records, template
  selectors, and their schemas without deprecated compatibility shims.
- Removed the product-level starter dataset. Synthetic records remain confined
  to test fixtures.

### Security

- Preview exports fail closed if email, phone, avatar, external links,
  attachments, images, unsafe metadata, secrets, undeclared TeX inputs, or path
  escapes survive the source and final-PDF projections.
- Application exports remain separately authorized and require approved Claims,
  an unchanged reviewed JD, approved identity policy, and an explicit
  confirmation.
- Public extraction is allowlisted and hash-bound; `career/`, identity,
  attachments, local fonts, `.obsidian/`, `runtime/`, `build/`, and
  `.career-os/` are prohibited.
- Rebuilt the stable release as a single-root MVP history after a privacy audit
  found real identity text in a pre-release PDF-extraction test commit.
- Added a complete-history privacy audit, reviewed guarded-blob policy, redacted
  private Career Home cross-comparison, and CI/release gates that reject short
  CJK identity/location values even if the offending test is later deleted.
- Release publication fails closed on missing, duplicate, malformed,
  mismatched, calendar-invalid, or empty exact changelog notes.

### Boundaries

- `v0.1.0` supports clean installations only. It does not provide compatibility
  with `v0.1.0-rc.*` interfaces.
- Automated validation did not run a real Codex session, Claude Code session,
  or live Obsidian interaction and must not be described as interactive
  experience validation.
- Publication pushes the clean-root `main` before its annotated `v0.1.0` tag;
  the tag-triggered workflow exclusively owns GitHub Release creation. No
  external career or recruiting action is part of the release.
