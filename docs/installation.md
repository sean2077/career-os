# Install and Verify Career OS

Career OS has separate readiness levels for its local record system, live Obsidian integration, and XeLaTeX resume pipeline. A passing core check does not imply that optional Obsidian, TeX, PDF, font, or auxiliary Skill dependencies are ready.

This page describes current installation requirements. Historical release boundaries and candidate evidence belong in the [release index](releases/README.md).

## Choose the capability you need

| Capability | Required dependencies | Readiness command |
| --- | --- | --- |
| Core records, Skills, schemas, plans, and filesystem checks | Git, `uv`, and Python 3.12 or newer | `uv run career-os doctor --json` |
| Live Obsidian CLI operations | Core plus the configured minimum Obsidian version, CLI enabled, and the app running | `uv run career-os doctor --json` |
| Resume build and export | Core plus `latexmk`, XeLaTeX, required TeX packages, and resolved fonts | `uv run career-os resume doctor --json` |
| High-fidelity PDF inspection | Resume stack plus Poppler's `pdftoppm`, `pdfinfo`, and `pdftotext` | `uv run career-os resume doctor --json` |
| Framework development | Core plus the locked development dependency group | `uv run career-os check --fast` |

The exact Obsidian and QuickAdd minimum versions are declared in [`career-os.toml`](../career-os.toml). Python compatibility and Python dependency ranges are declared in [`pyproject.toml`](../pyproject.toml). Do not repeat those values in a second installation checklist.

## Core setup

Install Git from the [official Git downloads](https://git-scm.com/downloads) and `uv` from the [official installation guide](https://docs.astral.sh/uv/getting-started/installation/). `uv` can provision a compatible Python when one is not already installed.

From the repository root, install the locked runtime dependencies:

```text
uv sync --locked
```

Contributors who run Ruff, mypy, or pytest need the development group:

```text
uv sync --locked --all-groups
```

Neither command installs Git, Obsidian, TeX, Poppler, resume fonts, or optional Agent Skills.

### Evaluate the public framework

The public checkout is data-free. Verify its core mechanisms without creating personal records:

```text
uv run career-os doctor --json
uv run career-os check --fast
```

A missing optional tool is reported as `attention`; it does not block filesystem-only workflows.

### Initialize a personal Career Home

Before adding real data, establish the private repository and remote boundary in [Private Downstream Installation](private-downstream.md). Then initialize either standalone mode:

```text
uv run career-os init --mode standalone --root . --languages en
uv run career-os doctor --json
uv run career-os check
```

or the reviewed embedded flow in [Embedded Vaults](embedded-vault.md). Do not invent a mount, ignore rule, or host configuration outside that plan/apply flow.

Initialization creates a missing `career/README.md` from the system-owned seed. It never creates, copies, renders, or overwrites a root homepage or Obsidian Base.

## Existing installations

Current project configuration uses schema 2 and canonical career records use schema 3. Legacy `data_root` and `runtime_root` aliases are rejected rather than silently mapped to the fixed `career/` and `.career-os/runtime/` locations.

For an older split downstream, review the exact release notes and create the required migration or downstream plan before changing files. Schema migrations are hash-bound, reviewable, explicitly applied, and separate from framework updates. See the [data model](data-model.md), [private downstream update flow](private-downstream.md#update-from-an-exact-reviewed-release), and [tooling guide](tooling.md).

## Optional Agent Skills

The tracked Career Skills are part of the repository. Optional Obsidian and contributor Skills are local tools, not runtime dependencies, and the CLI never installs or downloads them.

Inspect the current recommendation and installation state:

```text
uv run career-os skills status --json
uv run career-os skills status --audience contributor --json
```

Only when the report has `requires_user_choice: true` should an Agent explain the reviewed source and ask for project, global, or skip plus the target Host. Installation uses the argument arrays emitted from the reviewed recommendation manifest with telemetry disabled. After the selected Skills are visible to every selected Host, record the local decision, for example:

```text
uv run career-os skills configure --group obsidian --scope project --agent codex
```

Use `--scope global`, repeat `--agent` for both supported Hosts, choose `--scope skip`, or reset with `--reset` as appropriate. Configuration records ignored local state only; it does not install, delete, or repair a Skill. The complete source, digest, relinking, duplicate, and verification contract lives in [Career Skills](skills.md).

## Obsidian readiness

Core commands operate on local files and do not require Obsidian to be open. Live CLI operations require all of the following:

1. an Obsidian installation meeting the minimum in `career-os.toml`;
2. **Settings → General → Command line interface** enabled;
3. the CLI registered on `PATH`; and
4. the desktop application running.

Follow the [official Obsidian CLI instructions](https://obsidian.md/help/cli). Run `uv run career-os doctor --json` again after enabling the integration.

The recommended sibling-repository layout also requires directory-symlink support. On Windows, enable Developer Mode or use a terminal with symbolic-link privilege and make sure the host checkout materializes real symlinks. Linux and macOS normally materialize tracked relative symlinks directly. The complete cross-platform mount procedure belongs to [Embedded Vaults](embedded-vault.md#supported-layouts).

After attaching a real Vault, verify both project and host boundaries:

```text
uv run career-os doctor --json
uv run career-os check
uv run career-os check --host
uv run career-os views build
```

## XeLaTeX resume toolchain

Career OS verifies TeX Live in Ubuntu CI and TeX Live 2025 on the Windows release workstation. The macOS core runs in CI, but the macOS resume toolchain is not yet a release gate. Other TeX distributions may work but are not a verified compatibility promise.

Install TeX Live using the [TeX Users Group documentation](https://tug.org/texlive/quickinstall.html). The resume class requires these commands and packages:

- commands: `latexmk` and `xelatex`;
- packages: `fontspec`, `xeCJK`, `geometry`, `xcolor`, `enumitem`, `etoolbox`, `fancyhdr`, `graphicx`, `lastpage`, and `draftwatermark`.

Ubuntu's CI-equivalent package set is:

```text
sudo apt-get install --no-install-recommends \
  fonts-texgyre \
  latexmk \
  poppler-utils \
  texlive-fonts-recommended \
  texlive-lang-chinese \
  texlive-latex-extra \
  texlive-plain-generic \
  texlive-xetex
```

Poppler supports external visual, metadata, and high-fidelity text inspection. Its absence is normally `attention`, not a universal hard dependency. Resume doctor performs an isolated XeLaTeX compilation and probes the reported TeX and PDF commands, so a stale or broken `PATH` wrapper does not count as ready.

## Resume fonts

Font binaries are intentionally absent from Git. The tracked [`system/resume/fonts.json`](../system/resume/fonts.json) manifest is the authority for downloadable default files, URLs, sizes, hashes, roles, and licenses. Fetch and verify the default bundle once per checkout or machine:

```text
uv run career-os resume fonts fetch
uv run career-os resume fonts verify
uv run career-os resume doctor --json
```

The files are installed under ignored `.career-os/fonts/`. Existing unverified files are not overwritten, and initialization never downloads fonts implicitly. A fresh offline clone can use the core system but cannot build a resume until all unoverridden roles resolve.

Owner-provided fonts belong below the ignored directory configured by `[resume.fonts]` in `career-os.toml`; optional role filenames live under `[resume.fonts.roles]`. Do not commit or redistribute those binaries. Missing files fail before XeLaTeX; invalid or incompatible files fail during compilation. There is no per-resume font descriptor or silent substitution layer.

The fixed default stack covers the release fixtures, not every writing system. Read [Resume System](resume.md) before building or exporting personal material.

## Final readiness recipes

### Core-only installation

```text
uv sync --locked
uv run career-os doctor --json
uv run career-os check
```

### Resume-capable installation

```text
uv run career-os resume fonts fetch
uv run career-os resume fonts verify
uv run career-os resume doctor --json
uv run career-os resume list --json
```

Run `resume fonts fetch` only when an unoverridden role needs the downloadable default bundle. A passing project check confirms framework and privacy mechanisms, while `resume doctor` proves the selected fonts and commands are ready. Building every handwritten resume root remains the definitive rendering check on a new machine.

Framework maintainers should continue with the full verification sequence in [CONTRIBUTING.md](../CONTRIBUTING.md#verification) and the task-specific gates in [Tooling](tooling.md).
