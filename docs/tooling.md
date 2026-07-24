# Tooling

## Setup and checks

End-user runtime setup:

```text
uv sync --locked
uv run career-os doctor --json
uv run career-os check
uv run career-os cleanup
```

Contributor and release setup:

```text
uv sync --locked --all-groups
uv run career-os doctor --json
uv run career-os check --fast
uv run career-os check
uv run career-os cleanup --json
# Review the dry-run report before:
uv run career-os cleanup --apply
uv run career-os skills verify
uv run career-os skills validate-reviewer <evidence|probe> [PATH|-]
uv run career-os views build
uv run career-os release privacy --root . --ref HEAD --history
uv run career-os release privacy --root . --ref HEAD --history --private-root <private-career-home>
uv run career-os release notes --tag vX.Y.Z --output .career-os/release-notes.md
uv run career-os import plan --source-root <legacy-repository> --manifest <manifest.json>
uv run career-os import apply --plan <plan.json>
uv run career-os import verify --plan <plan.json>
uv run career-os import rollback --plan <plan.json>
uv run career-os migrate plan --to 3
uv run career-os migrate apply --plan <plan.json>
uv run career-os migrate verify --plan <plan.json>
uv run career-os migrate rollback --plan <plan.json>
uv run career-os resume fonts fetch
uv run career-os resume fonts verify
uv run career-os resume doctor --json
uv run pytest
uv run ruff check .
uv run mypy system/tools/career_os
```

## Development topology

`career-os.toml` declares `development_topology`. The public repository uses
`standalone-framework`: it contains framework code, synthetic fixtures, and
release evidence, but no personal Career Home data.

`integrated-workbench` is available to private Career Home repositories that
implement system-owned OS work and user-owned career practice in one private
Git history. The public repository itself remains `standalone-framework`.

`career-os downstream plan/apply/validate/rollback` is available for an
initialized `split-downstream` installation. Only that topology requires an
exact reviewed annotated tag for a complete synchronization proof.

System-package, Obsidian CLI, XeLaTeX, Poppler, font-download, offline, and
platform-support boundaries are defined in the
[installation requirements](installation.md). The core doctor and resume doctor
represent different readiness levels.

## Agent harness on Windows

Use Git Bash explicitly rather than the Windows `bash.exe` shim:

```text
"C:\\Program Files\\Git\\bin\\bash.exe" .agents/relink-skills.sh
"C:\\Program Files\\Git\\bin\\bash.exe" .agents/skills/agent-scaffold/agent-scaffold.sh verify --profile light --json
```

The second command runs the installed `agent-scaffold` verifier with the light
profile; worktree and trunk-guard governance are intentionally disabled.

## Validation depth

- `check --fast` validates configuration, schemas, static structure, Skill
  inventory, and generated subagent projection drift.
- `check` also validates Git-relative kind lifecycles, top-level Wikilink
  relations, cross-record semantic gates, tracked Obsidian assets, discovered
  resume TeX roots, and dependency locks.
- `check --host` retains the same full validation surface for compatibility;
  record Wikilinks are resolved by the full check.
- `paths --json` reports `vault_mount_root` when an external sibling project is projected through a configured Vault-relative symlink.

Both check depths validate the deterministic CycloneDX SBOM, notices, real
Agent harness symlinks, ignored-state boundary, and executable placement. CI
runs the core gate on Windows, Ubuntu, and macOS; an Ubuntu job additionally
fetches verified fonts and compiles/exports both resume fixtures. Every CI and
release job is guarded to `sean2077/career-os`, so workflows copied into forks
skip their jobs until the fork owner deliberately replaces that repository guard.
CI accepts `main` pushes and pull requests, not tag pushes. Release maintainers
wait for the pushed `main` commit's CI to succeed before creating its annotated
tag, allowing the tag-triggered release validation to restore the trusted TeX
Live cache without launching a duplicate tag CI run.

The hidden contributor command `release privacy` is the public-history boundary.
It requires a clean, non-shallow repository for `--history`, scans every blob
reachable from the selected ref, and validates reviewed hashes for resume tests,
resume TeX fixtures/templates, and CI/release workflows. Guarded hashes are
append-only while their blobs remain reachable. CI runs the public-only form;
before a public push or tag, maintainers also pass `--private-root` so labeled
names (including two- or three-character CJK values), locations, contact fields,
and profile URLs from the private Career Home are compared exactly against the
public tree and history. Reports contain only public paths, object IDs, and
SHA-256 fingerprints; they never echo matched private values.

The remote guard applies to initialized personal downstreams. Configuring the
canonical public Career OS remote there is optional. When it is configured,
both depths fail unless it is named `upstream` and its explicit push URL is
`DISABLED`; they also fail if the public repository remains a personal
`origin`. An arbitrary non-public `origin` is reported as `attention` because
hosted visibility cannot be proven offline. See the
[private downstream guide](private-downstream.md).

## Command ownership

One `career-os` executable owns initialization, path discovery, diagnosis,
checking, conservative ignored-state cleanup, framework-view verification, Vault plan/apply, legacy import
plan/apply/verify/rollback, in-place schema migration
plan/apply/verify/rollback, Skill
verification, reviewer-contract validation, and resume jobs. Operation plans
never select a mutating default for unknown input. Product implementation
helpers remain private under `system/tools/career_os/`.

`skills validate-reviewer` is the only reviewer-output command. It reads one
`evidence` or `probe` JSON object from a file or stdin, performs no writes, and
always emits `{"valid","blocks_readiness","errors"}`. A structurally valid
blocking review exits `0`; malformed JSON or an invalid contract exits `2` and
sets `blocks_readiness` to true. The pure contract implementation and schemas
remain private under `system/tools/career_os/` and `system/schemas/`; no retired
Skill-local validator script is retained.

`views build` remains a read-only verifier for root `Home.md` and `主页.md`, the four generic
assets, and ten paired English/Chinese Workbench Bases under
`system/obsidian/`. Its JSON retains `asset_root`, reports the root file
separately as `homepage`, adds both roots as `homepages`, lists sixteen
`assets`, and keeps `generated: []`.
`init` never creates or manages a Base. `check` validates the native Markdown
section order, canonical copy, filename-only navigation, five expanded
language-matched views per homepage, and absence of custom presentation
dependencies, plus schema/kind portability and presentation-only parity for
each Base pair. The two README previews remain
reviewed native Obsidian Full canvas PNG exports under `docs/assets/`;
The two Markdown homepages add no third image. Maintainers may drive Obsidian's built-in
exporter through `obsidian eval`; Career OS intentionally ships no parallel
renderer. See `docs/assets/README.md` for the export contract.

`import plan` consumes one operator-reviewed manifest and is read-only.
`import apply` copies only hash-pinned exact or prepared files into the
fixed `career/` root; `verify` checks the current plan state and `rollback`
uses the same ignored operation-plan backups. It never guesses a record kind
or state and never writes a tracked provenance ledger.
See `docs/importing.md`.

`cleanup` gives Git an allowlist of known reproducible roots instead of scanning
the whole ignored tree. The list contains configured build output, standard
root development/distribution caches, `.career-os/generated/`,
`.career-os/tmp/`, and Python caches under `system/tests/` and
`system/tools/`. It does not inspect `.venv/`, `career/`, fonts, migrations,
runtime acquisitions, editor state, or unknown ignored paths.

The command does not write unless `--apply` is present. Apply uses the dry-run
selection, then batch-checks Git state and verifies candidate fingerprints
before unlinking. Links, junctions, nested repositories, drift, locks, and
deletion errors are preserved or reported nonzero; a retry is safe.

`release notes` is a hidden contributor command consumed by the tag-triggered
GitHub Release workflow. It requires the exact configured `v`-prefixed tag and
atomically extracts one non-empty `## [vX.Y.Z] — YYYY-MM-DD` section from the
committed changelog. The workflow publishes no generated or fallback notes.

Resume commands use user-owned handwritten TeX sources. `resume list` discovers
roots containing `\documentclass{career-os}` recursively; `resume build
--resume NAME` creates only ignored internal output. `resume export --resume
NAME --profile preview|application` is the atomic no-overwrite publication
boundary; application also requires approved claims, target and identity
records, plus `--confirm-application`. The fixed source convention permits only
the root, adjacent `identity.tex`, and an optional application avatar. Preview
exports exclude contact details and avatars, and every export receives an ID
plus a receipt with hashes computed from the inputs actually built. `resume
work-experience` writes only an ignored temporary Markdown copy aid. The class
owns default fonts; optional project-wide filenames live in `career-os.toml`
and resolve without content pins, generated macros live under
`.career-os/generated/`, and font binaries remain under ignored
`.career-os/fonts/`.

`doctor` performs only non-mutating prerequisite checks. It verifies live
Obsidian version and CLI response only when the executable is registered and an
Obsidian process is already running, so diagnosis never launches the app. A
missing or stopped optional Obsidian CLI is `attention`; filesystem checks still
run. When OpenCLI research is enabled, doctor validates Node.js, the OpenCLI
version response, the configured allowlist against `opencli list -f json`, and
an already-running loopback bridge. It never launches the bridge, browser, or a
research command. It also reports the same local downstream remote-safety state
as `check`, including a clean pass when no public update remote is configured.

`skills verify` always validates inventory, projections, locks, and the isolated
selection prompt/oracle fixtures. A true blind behavioral run additionally
passes an Agent-produced `--selection-report`; without one, the command reports
that gate as `attention` rather than claiming it passed.
