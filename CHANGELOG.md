# Changelog

All notable changes to Career OS are documented here.

## [Unreleased]

### Added

- Added top-level `career-os cleanup`, a dry-run-first command that enumerates
  only known reproducible build, distribution, cache, generated, and temporary
  roots, with human and JSON reports, explicit `--apply`, and content-drift
  protection.

### Changed

- Fixed user data at project-relative `career/` and local runtime state at
  `.career-os/runtime/`; `paths --json` retains both stable output keys.
- Upgraded project configuration and installation state to schema 2 without
  root aliases, and unified initialization, imports, migrations, privacy,
  downstream, resume, and Obsidian adapters on the fixed roots.
- Owner-provided resume font overrides are now resolved by filename without
  configured checksums, so replacing a same-name file requires no configuration
  update. Downloaded system-default fonts remain integrity-verified.

### Fixed

- Made public-only snapshot tests topology-aware and documented the
  ancestry-independent downstream plan/apply flow for existing private Career
  Home histories.
- Kept superseded migration completions verifiable after an intentional
  downstream topology or Git-history rewrite without mutating historical
  hash-bound evidence.
- Removed obsolete `v0.1.0-rc.*` release notes now that the clean-install-only
  stable MVP is the sole published release line.

### Removed

- Removed `ProjectConfig.data_root`, `ProjectConfig.runtime_root`,
  `InstallState.data_root`, and `init --data-root`; legacy fields fail closed
  and require reinitialization or an explicit local-state rewrite.

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
