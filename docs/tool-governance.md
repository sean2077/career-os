# Tool Governance Decision

## Observed state

Career OS began as a clean repository with no historical command paths or consumers. The project vocabulary distinguishes system-owned implementation from user-owned data and generated state.

## Selected methods

- Task/journey identifies independently invokable CLI jobs.
- State/artifact and hazard/recovery keep Vault apply, cross-repository import,
  in-place migration, resume discovery/internal build, shareable resume export,
  and temporary work-experience extraction as separate subcommands.
- Distribution keeps one installed `career-os` entry.
- Provenance keeps scaffold runtime under `.agents/tools/` and project implementation under `system/tools/`.

Directory nouns alone do not define command jobs. A root script collection, one executable per helper, and a public Python import interface were rejected.

## Placement and contracts

`system/tools/career_os/` is the only product implementation root.
`pyproject.toml` exposes one CLI entry and all helpers remain private. Commands
validate unknown input, provide JSON where automation consumes results, and use
hash-bound plans for persistent host or user-state mutation. Cross-repository
import owns a clean source commit, classified files, binary or text copy,
target conflicts, hash-bound recovery state, and rollback; in-place migration owns schema
transitions inside fixed `career/`. They share private plan helpers
but remain separate public jobs.

The complete verification surface is CLI help, machine-readable output, pytest at the CLI/file seams, lint/type checks, structural placement checks, temporary real-Vault fixtures, and release validation.

Reviewer output validation is one read-only job under the existing
`career-os skills` command family. Its pure contract module centralizes the two
JSON state machines and readiness-blocking decision; the CLI adapter owns only
file/stdin input, safe JSON output, and exit codes. No Skill-local script,
second executable, compatibility shim, or rollback path is warranted because
the command never mutates state.

OpenCLI prerequisite and live-registry validation aggregate into the existing
read-only `career-os doctor` job because they diagnose one configured optional
capability and own no persistent state. Adapter execution remains an external
`opencli` contract called directly by `opportunity-decision`; Career OS adds no
research runner, browser wrapper, provider registry, or compatibility command.
Raw captures remain ignored `.career-os/runtime/` state, while reviewed Company
facts remain owned by Opportunity Decision.

Ignored-state reclamation is one independent top-level job:
`career-os cleanup`. Its default is a read-only dry run; `--apply` is the sole
mutation boundary. The private cleanup module owns the product allowlist, Git
enumeration limited to that allowlist, classification, link and path safety,
fingerprint/Git preflight, deletion, and retryable partial-error reporting. The
CLI adapter owns only options and human/JSON presentation. There is no full
ignored-tree scan, migration-state interpretation, `--all`, unknown-state
override, external-root scan, `.venv/` traversal, rollback promise, or second
executable.

Resume tooling has one authoritative human and automation entry:
`career-os resume`. `list` is read-only recursive discovery; `doctor` and
`build` own diagnostics and internal artifacts; `export` owns the confirmed,
atomic, no-overwrite publication boundary; and `work-experience` owns an
ignored temporary copy aid. XeLaTeX, PDF, font, and extraction helpers remain
private under `system/tools/career_os/resume/`; no retired standalone command
or Make compatibility surface is retained.
