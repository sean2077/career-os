# Private Downstream Installation

This guide describes the supported `split-downstream` topology for a private
Career Home that consumes the public `standalone-framework` repository.
`v0.1.0` is clean-install-only; this guide does not define a prerelease upgrade
path. An `upstream` remote is optional for local OS work. If one is configured,
keep it fetch-only; do not treat an upstream sync as a prerequisite for local
work.

In split mode, the recommended real-world installation is a private downstream
repository. Its optional remote roles are:

| Remote | Purpose | Push policy |
| --- | --- | --- |
| `upstream` | Optional source of reviewed Career OS releases | Explicitly disabled when configured |
| `origin` | Optional user-owned private repository | Allowed only after the owner confirms its visibility |

This layout keeps `system/`, the Agent harness, Skills, schemas, and English
documentation updateable while `career/` remains user-owned multilingual data in
the same private Git history.

## Do not use a public fork for private career data

GitHub states that every fork of a public repository is public and that a fork's
visibility cannot be changed. Create a separate private repository for `origin`
instead of assuming a public Career OS fork can hold private data. See
[GitHub's fork visibility documentation](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/about-permissions-and-visibility-of-forks).

Career OS can verify local remote names and push URLs without network access. It
cannot prove that an arbitrary hosted `origin` is private. The owner must confirm
that visibility before the first push.

## Bootstrap the downstream

Cloning the public framework initially creates a pushable public `origin`.
Before initializing user data, either retain it as a guarded optional
`upstream`:

```text
git clone https://github.com/sean2077/career-os.git career-home
cd career-home
git remote rename origin upstream
git remote set-url --push upstream DISABLED
git remote get-url upstream
git remote get-url --push upstream
```

The final command must print `DISABLED`. Git supports separate fetch and push URLs
through `git remote set-url --push`; the deliberately invalid push target is a
local safety guard. See the [Git remote documentation](https://git-scm.com/docs/git-remote).

Or remove the public remote after cloning:

```text
git clone https://github.com/sean2077/career-os.git career-home
cd career-home
git remote remove origin
```

Do not leave the public repository configured as a pushable personal `origin`.

## Mount the downstream into an existing Vault

Keep the private downstream and Vault as sibling repositories. The Vault owns a
portable relative directory symlink; Career Home owns every target file:

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

On Windows, enable Developer Mode or use a terminal with symbolic-link
privilege, and ensure the Vault checkout uses real symlinks:

```powershell
git -C obsidian-vault config core.symlinks true
New-Item -ItemType Directory -Force -Path obsidian-vault/Career
New-Item -ItemType SymbolicLink -Path obsidian-vault/Career/career-home -Target ../../career-home
git -C obsidian-vault add -- Career/career-home
```

Verify that Git stores a symlink rather than a directory, gitlink, junction, or
plain target-text file:

```text
git -C obsidian-vault ls-files --stage -- Career/career-home
git -C obsidian-vault cat-file -p :Career/career-home
```

The first command must show mode `120000`; the second must print
`../../career-home`. The relative target is platform-independent as long as the
sibling layout and mount depth remain unchanged.

Initialize Career OS only after choosing one of the public-remote policies above
and creating the mount:

```text
uv sync --locked
uv run career-os init --mode embedded --root . --vault-root ../obsidian-vault --vault-mount Career/career-home --languages en,zh-CN
uv run career-os vault plan --action attach --root . --vault-root ../obsidian-vault
# Review the emitted plan before applying it.
uv run career-os vault apply --root . --plan <emitted-plan.json>
uv run career-os doctor
uv run career-os check
uv run career-os check --host
uv run career-os views build
```

The mount path is always Vault-relative POSIX text, even on Windows. Career OS
validates the real link target and the host Git index but does not create,
ignore, rewrite, or remove the host-owned link. Use `--mode standalone` when the
downstream root is itself the Vault root.

## Add the optional private origin

Create a separate private repository using the hosting provider's normal UI or
API, confirm its visibility, and only then configure it:

```text
git remote add origin <private-repository-url>
git config remote.pushDefault origin
git push -u origin main
```

Repository creation and the first push are external account actions. An Agent
must obtain an explicit request and visibility confirmation immediately before
performing either action. When `upstream` is configured, plain
`git push upstream` remains blocked even for a user who has write access to the
public project.

## Update from an exact reviewed release

Do not pull an unreviewed moving branch into private data. Fetch tags, inspect one
exact annotated release, and merge it on an isolated sync branch:

```text
git status --short
git fetch upstream --tags
git cat-file -t vX.Y.Z
git switch -c sync/vX.Y.Z
git merge --no-edit vX.Y.Z
uv sync --locked
uv run career-os skills verify
uv run career-os check --fast
uv run career-os check
uv run career-os check --host
git switch main
git merge --ff-only sync/vX.Y.Z
```

This command sequence is the optional remote-based update path and therefore
requires a configured fetch-only `upstream`. Without that remote, use
`career-os downstream plan --source local --source-root <reviewed-career-os-checkout>`
with an exact commit or annotated tag from a separate reviewed local checkout.

`git cat-file -t` must report `tag`. Review that release's notes and system diff
before the merge. Resolve system-owned conflicts deliberately; never accept a
change that overwrites or deletes user-owned `career/` data. Push the updated
`main` only to a confirmed private `origin` and only when the user explicitly
requests it.

## Deterministic safety checks

After initialization, both `career-os doctor` and `career-os check` inspect local
Git configuration:

- no public Career OS remote is a valid configuration;
- when the canonical public repository is configured, it must be named
  `upstream`;
- a configured `remote.upstream.pushurl` must be exactly `DISABLED`;
- `origin` must not point back to the public Career OS repository; and
- an arbitrary `origin` receives an attention result until the owner confirms
  its hosted visibility.

These checks never contact, create, or mutate a remote. System updates never
overwrite `career/`; runtime, build, install state, backups, and downloaded fonts
remain ignored local state.

## Agent operating contract

For a private downstream, Agents must:

1. discover roots with `career-os paths --json` instead of embedding machine paths;
2. treat `career/` as user authority and the remaining tracked framework surfaces
   as system authority;
3. fetch only when the user asks for an update, using either an optional
   fetch-only `upstream` or a reviewed local source, then select an exact commit
   or annotated tag;
4. when `upstream` is configured, refuse any push to it and stop if the push
   guard is missing;
5. require explicit authorization and confirmed private visibility before the
   first `origin` push; and
6. run the deterministic gates before merging a sync branch into `main`.
