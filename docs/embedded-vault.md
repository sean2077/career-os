# Embedded Vaults

This page is the authority for Vault placement, host-owned mounts, attach/detach plans, shared Obsidian views, and the optional QuickAdd adapter. Repository visibility, remote guards, and framework updates belong to [Private Downstream Installation](private-downstream.md).

Career OS can be the Vault root or a nested project inside an existing Obsidian Vault. In every layout, canonical user data remains under the project's fixed `career/` root and native wikilinks can connect it to surrounding notes.

## Before attaching a real Vault

1. Establish a private Career Home and safe remote policy.
2. Install the core dependencies and initialize the intended mode.
3. Confirm the host layout below rather than improvising an ignore rule, junction, bare gitlink, or absolute symlink.
4. Review every emitted attach or detach plan before applying it.

See [Installation](installation.md) for dependency and live-Obsidian readiness. Career OS never tracks an active `.obsidian` directory or performs an unsolicited full-Vault scan.

## Supported layouts

| Layout | Repository behavior | Data root |
| --- | --- | --- |
| Standalone | Career OS root is the Vault root | `career/` |
| Independent sibling downstream (recommended) | The host tracks one relative directory symlink as mode `120000`; the target remains an independent private repository | `career/` inside the sibling repository |
| Independent nested downstream | The host receives one exact ignore entry through an attach plan | `career/` inside the nested repository |
| Standard submodule | Existing `.gitmodules` and gitlink are preserved | Fixed `career/` inside the project; never put real records in a public framework checkout |
| Non-Git host | No Git configuration is created | Fixed `career/` inside the project |

A gitlink without a matching `.gitmodules` entry is an unsupported bare gitlink. Career OS reports it and does not silently convert or repair it.

The project root must either resolve physically inside the selected Vault or project through one configured `vault_mount`. The mount is a Vault-relative POSIX path whose final component is a directory symlink resolving to the external Career OS root. Stored host references remain Vault-relative POSIX paths, including on Windows.

## Independent sibling downstream (recommended)

Keep the private Career Home and Vault as sibling repositories. The Vault owns the portable relative directory symlink; the Career Home owns every target file:

```text
<workspace>/
├─ career-home/
└─ obsidian-vault/
   └─ Career/
      └─ career-home -> ../../career-home
```

Create the link from the workspace root. On Linux or macOS:

```text
mkdir -p obsidian-vault/Career
ln -s ../../career-home obsidian-vault/Career/career-home
git -C obsidian-vault add -- Career/career-home
```

On Windows, enable Developer Mode or use a terminal with symbolic-link privilege, then make sure the host checkout uses real symlinks:

```powershell
git -C obsidian-vault config core.symlinks true
New-Item -ItemType Directory -Force -Path obsidian-vault/Career
New-Item -ItemType SymbolicLink -Path obsidian-vault/Career/career-home -Target ../../career-home
git -C obsidian-vault add -- Career/career-home
```

Verify that Git stores a symlink rather than a directory, junction, submodule, or plain target-text file:

```text
git -C obsidian-vault ls-files --stage -- Career/career-home
git -C obsidian-vault cat-file -p :Career/career-home
```

The first command must show mode `120000`; the second must print `../../career-home`. The relative target remains portable while the sibling layout and mount depth remain unchanged.

## Attach and detach

For a project located physically inside the Vault, initialize and create an attach plan:

```text
uv run career-os init --mode embedded --root . --vault-root <vault> --languages en,zh-CN
uv run career-os vault plan --action attach --root . --vault-root <vault>
# Review the emitted plan, then:
uv run career-os vault apply --root . --plan <emitted-plan.json>
```

For the sibling layout, create and stage the relative symlink first, then initialize with its Vault-relative path:

```text
uv run career-os init --mode embedded --root . --vault-root <vault> --vault-mount Career/career-home --languages en,zh-CN
uv run career-os vault plan --action attach --root . --vault-root <vault>
# Review the emitted plan, then:
uv run career-os vault apply --root . --plan <emitted-plan.json>
```

Initialization rejects absolute, drive-qualified, backslash, traversal, plain directory, dangling, and wrong-target mounts. In a Git host, attach reports the mount unless the index records it as mode `120000`. Attach never creates, ignores, or deletes the host-owned link.

The plan records resolved roots, current and result hashes, ordered file operations, repository mode, warnings, and backup locations. Apply refuses a stale target. Reapplying the same plan is idempotent; planning attach again after a healthy installation produces a no-op plan.

Detach uses installed hashes and attach backups:

```text
uv run career-os vault plan --action detach --root . --vault-root <vault>
# Review the emitted plan, then:
uv run career-os vault apply --root . --plan <emitted-plan.json>
```

Detach removes only files created by attach and restores only configurations changed by attach. A post-attach edit blocks detach instead of being overwritten. Repository-owned views are never copied, adopted, or deleted, and a sibling mount remains host-owned after detach.

## Shared Obsidian framework views

Root `Career Home.md`, `职业主页.md`, and portable assets under `system/obsidian/` are tracked framework projections over canonical Markdown records. The current inventory includes bilingual Workbench entry points and authority views, Recent Changes, a generic record inventory, a lightweight dashboard, and explanatory Canvases.

Do not duplicate the exact inventory in host notes or install instructions. `uv run career-os views build` is the read-only authority that lists and validates the tracked assets; `uv run career-os check` verifies homepage locks, Base inventory, localization parity, and semantic contracts. Initialization never creates or overwrites a homepage or Base, and neither command produces a second view tree under `career/` or `.career-os/runtime/`.

The views are navigation and presentation only. Markdown frontmatter and records remain canonical. Framework homepages, the dashboard, and Canvases use filename-only wikilinks; host notes may use the full actual Vault-relative path when linking an asset. Keep framework view filenames unique within the surrounding Vault. See the [Obsidian internal-links documentation](https://obsidian.md/help/links).

Live CLI use requires the Obsidian version declared in `career-os.toml`, the CLI enabled, and the app running. Filesystem validation continues without live access. See the [official Obsidian CLI documentation](https://obsidian.md/help/cli).

## Optional QuickAdd adapter

`--with-quickadd` requires an installed QuickAdd manifest matching `obsidian.quickadd_version` in [`career-os.toml`](../career-os.toml). Career OS validates the plugin ID, version, and existing choice conflicts, then generates three reviewable choices under `.career-os/obsidian/quickadd/`:

- `capture-choice.json` captures raw text into the Career Evidence inbox; it never creates an approved claim automatically.
- `jd-review-choice.json` invokes the tracked `system/obsidian/quickadd/review-jd.js` User Script for the active schema-3 JD, Company, or Engagement.
- `engagement-event-choice.json` invokes the tracked `system/obsidian/quickadd/record-engagement-event.js` User Script for the active Engagement.

Generate the bundle during a new attachment:

```text
uv run career-os vault plan --action attach --root . --vault-root <vault> --with-quickadd
# Review the emitted plan and generated choice JSON, then:
uv run career-os vault apply --root . --plan <emitted-plan.json>
```

Career OS does not install QuickAdd or edit the host-owned `.obsidian/plugins/quickadd/data.json` or `.obsidian/hotkeys.json`. Those files may contain unrelated choices and shortcuts. On an already attached installation, configure the Macros directly from the tracked scripts rather than detaching solely to change the adapter:

1. Open **Settings → QuickAdd** and create a Macro choice named `Career OS: Review active record`.
2. Enable the choice as a command.
3. Add the Vault-visible `system/obsidian/quickadd/review-jd.js` User Script. For a sibling layout, its path starts with the configured Vault mount.
4. Create `Career OS: Record engagement event`, enable it as a command, and add `system/obsidian/quickadd/record-engagement-event.js`.
5. In **Settings → Hotkeys**, review conflicts before assigning `Alt+J` to the review command and `Alt+I` to the event command. Keep `Alt+E` unchanged; the recommended mapping reserves it for Templater.

For an existing JD-only installation, retain choice ID `8d0e6c70-b092-4e56-a18c-f631ca6b87f2` and its nested macro/command IDs. Rename `Career OS: Review active JD` to `Career OS: Review active record`, keep the `Alt+J` binding, and add the event choice using IDs from generated JSON rather than inventing new IDs.

Open a canonical record before invoking review. JD review preserves the A–F semantics; Company review refuses blocked, stale, overdue, or incomplete assessments; Engagement review checks Company/JD relationships and the event ledger. The command shows the proposed write, checks for concurrent changes, and can rescan the same record type after success without persisting a queue.

Open an Engagement before invoking the event command. It records one explicit user-reported contact, referral, application, interview, offer, or closure event; proposes editable summary states; and optionally updates a full-date `review_on` checkpoint plus `next_action`. The event and projection are one transaction and reset `review_status` to `pending`. Missing prerequisites, chronological regressions, cancellation, invalid projections, and concurrent changes write nothing.

The Engagement Decisions views show open application pipelines with Company, JD, localized phase, factual states, role/team, checkpoint, next action, review state, and update time. `review_on` is a date-level checkpoint, not an exact appointment. Keep round details, interviewers, and feedback in the event note or a Capability Readiness Session.

Neither adapter submits an application, sends a message, uploads a file, changes an account, accepts or declines an offer externally, or resigns. Run `uv run career-os check` after a review or event batch before committing user-owned records.

Agents must validate generated paths and ID/name conflicts. They must not overwrite a user's QuickAdd settings, choose an A–F review signal, or invent an external event. Editing host configuration requires an explicit request, and record assertions remain the user's decision.
