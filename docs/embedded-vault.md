# Embedded Vaults

Career OS can be the Vault root or a nested project inside an existing Obsidian
Vault. In both cases the system repository and user data remain separately
owned, while native wikilinks can connect career records to surrounding notes.

For personal use, the recommended layout is an independent private downstream.
Configuring the public Career OS repository as a non-pushable `upstream` is
optional and is needed only for the remote-based exact-tag update workflow.
Follow the repository and mount boundaries in the
[private downstream setup](private-downstream.md) before attaching the
repository to a real Vault.

## Supported layouts

| Layout | Repository behavior | Data root |
| --- | --- | --- |
| Standalone | Career OS root is the Vault root | `career/` |
| Independent sibling downstream (recommended) | Outer Git tracks one relative directory symlink as mode `120000`; the target repository remains private, with an optional fetch-only public `upstream` | `career/` inside the sibling repository |
| Independent nested downstream | Outer Git receives one exact ignore entry through an attach plan | `career/` inside the nested repository |
| Standard submodule | Existing `.gitmodules` and gitlink are preserved | Fixed `career/` inside the project; keep real records out of a public framework checkout |
| Non-Git host | No Git configuration is created | Fixed `career/` inside the project |

A gitlink without a matching `.gitmodules` entry is reported as an unsupported
bare gitlink. Career OS does not repair it or silently convert it into another
layout.

The project root must either resolve physically inside the selected Vault or
project through one configured `vault_mount`; `career/` always remains inside
that project. A mount is a
Vault-relative POSIX path whose final component is a directory symlink resolving
to the external Career OS project root. Paths stored in host references remain
Vault-relative POSIX paths. User data remains a normal, Git-eligible directory;
Career OS never ignores data or the sibling mount.

## Attach and detach

Initialize first, then create a plan:

```text
career-os init --mode embedded --root . --vault-root <vault> --languages en,zh-CN
career-os vault plan --action attach --root . --vault-root <vault>
career-os vault apply --root . --plan <emitted-plan.json>
```

For the recommended sibling layout, create and stage the relative symlink in
the host repository first, then initialize with its Vault-relative path:

```text
career-os init --mode embedded --root . --vault-root <vault> --vault-mount Career/career-home --languages en,zh-CN
```

Initialization rejects absolute, drive-qualified, backslash, traversal, plain
directory, dangling, and wrong-target mounts. In a Git host, attach reports the
mount unless the host index records it as mode `120000`. Attach never creates,
ignores, or deletes this host-owned link.

The attach plan records absolute resolved roots, current and result hashes,
ordered file operations, repository mode, warnings, and backup locations. Apply
refuses a stale target. Reapplying the same plan is idempotent; planning attach
again after a healthy attachment produces a no-op plan.

Detach uses the recorded installed hashes and attach backups:

```text
career-os vault plan --action detach --root . --vault-root <vault>
career-os vault apply --root . --plan <emitted-plan.json>
```

Detach removes only files created by attach and restores only configurations
changed by attach. Any post-attach edit blocks detach instead of being
overwritten. The framework views are repository files, so attach and detach do
not copy, adopt, or delete them. A sibling mount likewise remains host-owned
after detach.

## Shared Obsidian framework views

Root `Home.md`, `主页.md`, and portable assets under `system/obsidian/` are versioned
directly:

- paired native Markdown Workbench homepages, each with five expanded
  language-matched Base views and seven Authority links;
- a lightweight Markdown dashboard with the generic Base and two explanatory
  Canvas embeds;
- an Obsidian Base with domain workbenches for evidence, strategy, JD screening,
  same-company application decisions grouped by typed Recruiting Scope references,
  Companies/Engagements, application events, Outlook, Readiness, and communication;
- an architecture Canvas showing the Agent-native workflow, seven authorities,
  deterministic interfaces, and hard safety boundaries;
- a usage-guide Canvas with seven single-authority and four cross-authority
  outcome cards;
- five paired English/Chinese Workbench Bases for JD screening, recruiting
  channels, Company Portfolio, Engagement Decisions, and Capability Readiness.

The generic Base and all ten Workbench Bases discover notes through stable
`schema_version`, `kind`, and kind-specific properties. The paired files differ
only in filename, view names, and column display names. Initialization never
creates, copies, renders, or overwrites either root homepage or any Base. A host note
can link or embed the framework assets. `career-os views build` is an
idempotent read-only verifier for all sixteen assets; `career-os check` also
verifies both homepages, Base inventory, presentation-only pair parity, and
semantic contracts. Neither command creates a data-root or runtime view tree.
The homepages, Bases, and Canvas files are views only; Markdown frontmatter and
authority records remain canonical.

The homepages, dashboard, and explanatory Canvas files use filename-only
wikilinks for navigation; each homepage adds only its selected Base view fragment.
They do not bake in the repository's mount directory or physical `career/` path.
Keep these framework and dedicated-Base filenames unique within the surrounding
Vault; host notes may use the full actual Vault-relative path when linking an
asset. See the
[Obsidian internal-links documentation](https://obsidian.md/help/links).

Career OS never tracks an active `.obsidian` directory and never performs an
unsolicited full-Vault scan. Explicit searches may use the bundled
`obsidian-cli` Skill. Live CLI use requires Obsidian 1.12.7 or newer, the CLI
enabled, and the application running; filesystem validation continues without
live access. See the
[official Obsidian CLI documentation](https://obsidian.md/help/cli).

## Optional QuickAdd adapter

`--with-quickadd` requires an installed QuickAdd manifest at exactly `2.12.3`.
Career OS validates ID, version, and existing choice conflicts, then generates a
reviewable Capture choice under `.career-os/obsidian/quickadd/`. It does not install
the plugin or edit QuickAdd's `data.json`, which may contain host-owned settings.
The choice captures raw text into the Career Evidence inbox; it never creates an
approved claim automatically.
