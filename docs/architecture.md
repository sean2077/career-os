# Architecture

Career OS separates career authority, framework behavior, and reproducible
local state. This public checkout is the data-free `standalone-framework`;
private Career Homes can use the same framework through the other documented
development topologies.

## Ownership layers

| Layer | Canonical contents | Update rule |
| --- | --- | --- |
| User-owned | Multilingual records and handwritten resume roots under fixed `career/` | Eligible for the user's private Git history; initialization and framework updates never overwrite it |
| System-owned | `.agents/`, `system/`, root manifests, root homepages, tests, and English docs | Changed through reviewed framework work and deterministic checks |
| Local/generated | `.career-os/`, `build/`, downloaded fonts, plans, receipts, backups, and scratch state | Ignored, reproducible or machine-local, and never a career fact authority |

`.career-os/runtime/` is the only active scratch root. Root `runtime/` remains
ignored solely as a protected legacy boundary and has no producer.

## Development topologies

`career-os.toml` selects one framework-development relationship. It does not
change the fixed `career/` data root or the physical Vault placement.

| Topology | Intended use | Framework update boundary |
| --- | --- | --- |
| `standalone-framework` | This public, data-free Career OS repository | Contains only public-bound framework assets, synthetic fixtures, and release evidence |
| `integrated-workbench` | A private Career Home where framework changes and career practice share one private history | Develop and validate locally; a public release is not required for local work |
| `split-downstream` | A private installation consuming reviewed public snapshots | Use `career-os downstream plan/apply/validate/rollback` with an exact reviewed source |

Vault placement is a separate concern. A private Career Home may be the Vault
root or a sibling project mounted through a Vault-relative directory symlink.
See [Embedded Vaults](embedded-vault.md).

## Runtime flow and stable seams

Agents are the primary workflow surface. An Agent selects or composes the
seven Career Skills, reads and writes through the owning authority, and leaves
canonical facts in Markdown records. Obsidian renders tracked homepages, Bases,
dashboards, and Canvases over those records. The `career-os` CLI provides
deterministic initialization, diagnosis, validation, plans, migrations, resume
build/export, and framework-view checks.

Before `v1.0`, the stable seams are:

- the `career-os` CLI and its documented file effects;
- `career-os.toml` ProjectConfig schema 2;
- canonical career-record schema 3 and operation-plan schemas;
- tracked Obsidian and resume assets; and
- generated receipts and validation reports where a command documents them.

Python modules below `system/tools/career_os/` are private implementation
details.

## Authority model

Career Evidence, Career Strategy, Role Market, Opportunity Decision, Career
Outlook, Capability Readiness, and Career Communication each own a distinct
record family and lifecycle. Cross-authority workflows use typed Wikilinks
rather than duplicated facts.

Role Market owns JD and role-fit evidence. When a JD identifies an employer,
Opportunity Decision separately owns the canonical Company and engagement
assessment. Likewise, a successful check, export, or reviewer response cannot
promote evidence maturity, readiness, application state, or career outcomes.

Record status transitions are Git-relative. Schema changes use reviewed,
hash-bound migration plans; `migrate apply` is explicit and backups remain
local.

## Visible system layer

There is no product root `src/`, `tools/`, or `scripts/` directory.
`pyproject.toml` exposes the package rooted at `system/tools` as the single
`career-os` command.
Schemas, migrations, root `Career Home.md` and `职业主页.md`, other Obsidian
assets, resume assets, blank seeds, and their tests remain visibly
system-owned beside the implementation.

- `system/tools/career_os/` owns executable framework behavior.
- `system/schemas/` owns generated public schemas.
- `system/obsidian/` and the two root homepages own portable Obsidian views.
- `system/resume/` owns the fixed class, templates, and downloadable-font lock.
- `system/seeds/` owns blank initialization material, never user records.
- `system/migrations/` owns explicit data migrations.
- `system/tests/` owns the maintained automated coverage.

The dual-host Agent harness is the only command-placement exception:
`.agents/` is its source of truth, with generated or symlinked host projections.

## Obsidian projections

The tracked view inventory contains eighteen assets: two root homepages, a
dashboard, a generic Base, two explanatory Canvases, five English/Chinese
Workbench Base pairs, and one English/Chinese Recent Changes pair. The
homepages embed the localized Recent Changes view and five operational
Workbenches.

These files are projections only. Bases query stable record properties;
Recent Changes uses local file modification time for navigation only.
`career-os init` never creates or overwrites a homepage or Base.
`career-os views build` verifies and lists the assets without generating
copies under `career/` or `.career-os/runtime/`.

Structural homepage rules live in code. The prose between them is frozen by
SHA-256 digests in `system/homepage-lock.json`, so an unreviewed homepage edit
fails `career-os check` without duplicating a second copy in Python.

An external sibling project is mounted only through a configured
Vault-relative POSIX directory symlink. The host repository owns the mode
`120000` link; the target Career Home owns every project file. A linked Git
worktree may inherit the primary checkout's read-only Vault install context,
but its mutable `.career-os/`, generated output, and runtime scratch stay local
to that worktree.

## Update and publication boundaries

This public repository accepts only public-bound framework assets, synthetic
fixtures, and release evidence. `career/`, identity, attachments, local fonts,
`.obsidian/`, root legacy runtime, `build/`, and `.career-os/` must never enter
its tree or history.

Before a public push or tag, maintainers run the complete-history privacy audit
from a clean, non-shallow public checkout and pass the private Career Home as
`--private-root`. No private Home commit or parent becomes reachable here;
Home-first work crosses the boundary only as a reviewed, path-limited tree
diff.

A split downstream consumes an exact reviewed public snapshot without
overwriting `career/`. Its public remote is optional; when present it remains
fetch-only as `upstream` with `remote.upstream.pushurl=DISABLED`.
