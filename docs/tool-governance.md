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
target conflicts, provenance, and rollback; in-place migration owns schema
transitions inside the configured data root. They share private plan helpers
but remain separate public jobs.

The complete verification surface is CLI help, machine-readable output, pytest at the CLI/file seams, lint/type checks, structural placement checks, temporary real-Vault fixtures, and release validation.

Reviewer output validation is one read-only job under the existing
`career-os skills` command family. Its pure contract module centralizes the two
JSON state machines and readiness-blocking decision; the CLI adapter owns only
file/stdin input, safe JSON output, and exit codes. No Skill-local script,
second executable, compatibility shim, or rollback path is warranted because
the command never mutates state.

Resume tooling has one authoritative human and automation entry:
`career-os resume`. `list` is read-only recursive discovery; `doctor` and
`build` own diagnostics and internal artifacts; `export` owns the confirmed,
atomic, no-overwrite publication boundary; and `work-experience` owns an
ignored temporary copy aid. XeLaTeX, PDF, font, and extraction helpers remain
private under `system/tools/career_os/resume/`; no retired standalone command
or Make compatibility surface is retained.
