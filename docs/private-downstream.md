# Private Downstream Installation

This page is the authority for the supported `split-downstream` topology: a private Career Home consumes reviewed snapshots from the public, data-free `standalone-framework` repository. It owns the remote-safety and exact update procedures. Vault mounts and host adapters belong to [Embedded Vaults](embedded-vault.md).

This is not the Home-first `integrated-workbench` development flow, and `career-os downstream` is not a mechanism for returning private work to the public repository.

## Safety invariants

Before adding personal data:

1. use a separate private repository or no hosted personal remote;
2. remove the public push target or retain it only as fetch-only `upstream`;
3. confirm any personal `origin` is private before its first push;
4. keep real records, identity, attachments, fonts, active Obsidian state, and generated output out of every public fork and public history; and
5. use an exact reviewed release or commit for framework updates, never an unreviewed moving branch.

Current installations use project-config schema 2 and record schema 3. Review [Existing installations](installation.md#existing-installations) before updating an older Home.

## Remote model

Both remotes are optional for local work:

| Remote | Purpose | Push policy |
| --- | --- | --- |
| `upstream` | Fetch reviewed public Career OS releases | Must have `remote.upstream.pushurl=DISABLED` |
| `origin` | User-owned private repository | Allowed only after the owner confirms hosted visibility |

A private downstream keeps framework assets and user-owned `career/` records in one private Git history. System updates remain reviewable and must never overwrite the user authority.

### Do not use a public fork for private data

GitHub documents that forks of a public repository are public and that their visibility cannot be changed. Create a separate private repository instead of assuming a fork can hold personal data. See [GitHub's fork visibility documentation](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/about-permissions-and-visibility-of-forks).

Career OS can inspect local remote names and push URLs without network access. It cannot prove the hosted visibility of an arbitrary `origin`; the owner must confirm that before the first push.

## Bootstrap the private checkout

Cloning the public framework initially creates a pushable public `origin`. Choose one policy before initialization.

### Keep a guarded update remote

```text
git clone https://github.com/sean2077/career-os.git career-home
cd career-home
git remote rename origin upstream
git remote set-url --push upstream DISABLED
git remote get-url upstream
git remote get-url --push upstream
```

The final command must print `DISABLED`. Git supports separate fetch and push URLs through `git remote set-url --push`; the deliberately invalid push target is a local guard. See the [Git remote documentation](https://git-scm.com/docs/git-remote).

### Keep no public remote

```text
git clone https://github.com/sean2077/career-os.git career-home
cd career-home
git remote remove origin
```

Do not leave the public repository configured as a pushable personal `origin`. A public remote is optional for local Career OS work.

## Initialize standalone or embedded mode

For a standalone Career Home that is itself the Obsidian Vault root:

```text
uv sync --locked
uv run career-os init --mode standalone --root . --languages en,zh-CN
uv run career-os doctor --json
uv run career-os check
uv run career-os views build
```

For an existing Vault, continue with the complete cross-platform sibling layout and reviewed attach procedure in [Embedded Vaults](embedded-vault.md#independent-sibling-downstream-recommended). That page is the sole authority for mount creation, host Git validation, attach/detach plans, shared views, and QuickAdd.

## Add the optional private origin

Create a separate private repository through the hosting provider, confirm its visibility, and only then configure it:

```text
git remote add origin <private-repository-url>
git config remote.pushDefault origin
git push -u origin main
```

Repository creation and the first push are external account actions. An Agent must obtain an explicit request and visibility confirmation immediately before either action. A configured `upstream` remains non-pushable even when the user has write access to the public project.

## Update from an exact reviewed release

Do not pull an unreviewed moving branch into private data. Use one exact annotated release on an isolated sync branch:

```text
git status --short
git fetch upstream --tags
git cat-file -t vX.Y.Z
git switch -c sync/vX.Y.Z
uv run career-os downstream plan --source upstream --tag vX.Y.Z
# Review the emitted JSON and binary patch, then:
uv run career-os downstream apply --plan <emitted-plan.json>
uv sync --locked
uv run career-os skills verify
uv run career-os check --fast
uv run career-os check
uv run career-os check --host
uv run career-os downstream validate --plan <emitted-plan.json> --output .career-os/downstream/downstream-sync-vX.Y.Z.json
git add -- <reviewed-system-paths>
git commit -m "chore(framework): sync Career OS vX.Y.Z"
git switch main
git merge --ff-only sync/vX.Y.Z
```

`git cat-file -t` must report `tag`. Review that release's notes and system diff before apply. The command rejects protected user/local paths, dirty managed paths, stale HEAD or branch state, and a changed or tampered plan.

This tree-and-patch workflow does not require common Git ancestry between the public framework and private Home, so it is also the cutover path for an independent existing history. Without a configured `upstream`, use a separately reviewed local checkout:

```text
uv run career-os downstream plan --source local --source-root <reviewed-career-os-checkout> --commit <full-40-character-source-commit>
```

Use `--tag vX.Y.Z` instead only for an exact annotated tag in that checkout. Push the updated `main` only to a confirmed private `origin` and only on explicit request.

## Deterministic safety checks

After initialization, `doctor` and `check` inspect local Git configuration:

- a downstream with no public Career OS remote is valid;
- the canonical public repository, when configured, must be named `upstream`;
- `remote.upstream.pushurl` must be exactly `DISABLED`;
- `origin` must not point to the public Career OS repository; and
- an arbitrary `origin` remains `attention` until the owner confirms its hosted visibility.

These checks never contact, create, or mutate a remote. System updates never overwrite `career/`; runtime state, build output, plans, backups, install state, and downloaded fonts remain ignored local data.

## Agent operating contract

For a private downstream, Agents must:

1. discover roots with `uv run career-os paths --json` instead of embedding machine paths;
2. treat `career/` as user authority and tracked framework surfaces as system authority;
3. fetch only when the user requests an update, then select an exact reviewed commit or annotated tag;
4. refuse any push to `upstream` and stop when its push guard is missing;
5. require explicit authorization and confirmed private visibility before the first `origin` push; and
6. run the deterministic gates before merging a sync branch into `main`.
