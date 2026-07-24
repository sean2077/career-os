# Architecture

Career OS has three ownership layers:

1. The **system-owned layer** contains the Agent harness, CLI implementation, schemas, Obsidian assets, migrations, tests, and English documentation.
2. The **user-owned layer** contains multilingual career data at the fixed project-relative `career/` root. It is intended to be versioned in the user's Git history, independently of framework updates.
3. The **local/generated layer** contains install state, backups, downloaded fonts, build artifacts, and optional scratch files. It never contains canonical career data.

The stable seams are the `career-os` CLI, public file schemas, operation plans, and generated artifacts. Python imports under `system/tools/career_os/` are private before v1.0.

The seven domain authorities each own one class of canonical records. Agent workflows may read across authorities but write through the owning Skill and use stable references rather than copied facts.

`career-os check` fails if Git ignore rules exclude `career/`. The complete
private Career Home, including that data root, may itself be an external sibling
repository projected into the Vault; the mount moves the project, not the data
authority within it.

Root `Home.md` and `主页.md`, the generic Obsidian Base and dashboard, two
explanatory Canvas files, and ten paired English/Chinese Workbench Bases are
system-owned, Git-tracked assets. Each homepage is a native Markdown live panel:
the English page embeds the five English Base views, while the Chinese page
embeds the five Chinese views. Both language variants query
schema-2 records by `kind`, while only filenames, view names, and column display
names differ. Initialization never creates or overwrites either homepage or any
Base. Bases remain projections over stable record properties, not factual
authorities.
`.career-os/runtime/` is the single local scratch root. Root `runtime/` remains
ignored only to protect legacy raw state and has no current producer.

An embedded project may live outside the Vault only through an explicitly
configured relative directory symlink. Career OS keeps the physical project
separate from the lexical Vault mount, validates that the mount resolves to the
project, and maps framework and fixed `career/` paths through it for Obsidian.
The host repository owns only the portable mode-`120000` link; the target
repository owns its system and private data history.

## Visible system layer

There is no root `src/`, product `tools/`, or product `scripts/` directory.
`pyproject.toml` treats `system/tools` as the package root and exposes only the
`career-os` command. Schemas, migrations, root `Home.md` and `主页.md`, other Obsidian
assets, resume assets, blank seeds, and their tests remain visibly system-owned
beside that private implementation.

The harness is the sole placement exception: `.agents/tools/` contains
scaffold-managed Host infrastructure, while project and bundled Skills live in
`.agents/skills/`. User data never depends on those physical paths; Agents call
`career-os paths --json` before resolving physical project or Vault paths.

## Update boundary

System updates arrive as reviewed Git tags or as an updated submodule. They may
replace system-owned files but never initialized user records. A data schema
change is represented by a hash-bound migration plan and requires explicit
`migrate apply`; rollback uses the plan's recorded backups.
