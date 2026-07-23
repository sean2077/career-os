# Installation Requirements

> **v0.1.0 boundary:** install from a clean public checkout. This stable release
> does not support in-place upgrades from `v0.1.0-rc.*`.

Career OS separates core, live Obsidian, and resume readiness. A successful
core check does not imply that the optional Obsidian CLI or XeLaTeX resume
toolchain is ready.

## Dependency levels

| Capability | Required dependencies | Readiness command |
| --- | --- | --- |
| Core records, Skills, schemas, plans, and filesystem checks | Git, `uv`, and Python 3.12 or newer | `uv run career-os doctor --json` |
| Live Obsidian CLI operations | Core plus Obsidian 1.12.7 or newer, CLI enabled, and the application running | `uv run career-os doctor --json` |
| Resume build and export | Core plus `latexmk`, XeLaTeX, the required TeX packages, and the default or TeX-named local fonts | `uv run career-os resume doctor --json` |
| Optional high-fidelity PDF inspection | Resume stack plus `pdftoppm`, `pdfinfo`, and `pdftotext` from Poppler | `uv run career-os resume doctor --json` |

Install Git from the [official Git downloads](https://git-scm.com/downloads)
and `uv` from the [official installation guide](https://docs.astral.sh/uv/getting-started/installation/).
`uv` can provision the required Python version when it is not already
installed. The project itself requires Python 3.12 or newer.

For an end-user checkout, install the locked runtime dependencies:

```text
uv sync --locked
```

Contributors who run Ruff, mypy, or pytest need the development group:

```text
uv sync --locked --all-groups
```

Neither command installs Git, Obsidian, TeX, Poppler, or the resume fonts.

## Core and Obsidian readiness

Core commands operate on local files and do not require Obsidian to be open.
Live CLI operations require the Obsidian 1.12.7+ installer, **Settings →
General → Command line interface** enabled, PATH registration completed, and
the desktop application running. Follow the
[official Obsidian CLI instructions](https://obsidian.md/help/cli).

The recommended sibling-repository layout also requires directory-symlink
support. On Windows, enable Developer Mode or use a terminal with symbolic-link
privilege and set `core.symlinks=true` before checkout. Linux and macOS normally
materialize tracked relative symlinks directly. See
[Private Downstream Installation](private-downstream.md).

Run the core diagnosis after initialization:

```text
uv run career-os doctor --json
uv run career-os check
```

Initialization creates a missing data-root `README.md` from the system-owned
Career Home seed. It does not create, copy, render, or overwrite any Base.
Paired English/Chinese Workbench Bases are tracked system assets under
`system/obsidian/bases/` and query schema-2 records by `kind`; `career-os check`
reports inventory, localization-parity, or semantic drift for review.

Missing optional Obsidian, LaTeX, or PDF commands appear as `attention` in the
core doctor. They do not block filesystem-only career workflows.

## XeLaTeX resume toolchain

Career OS verifies TeX Live on Ubuntu CI and TeX Live 2025 on the Windows
release workstation. The macOS core runs in CI, but the macOS resume toolchain
is not yet a release gate. Other TeX distributions may work but are not a
verified compatibility promise.

Install TeX Live using the
[TeX Users Group installation documentation](https://tug.org/texlive/quickinstall.html).
The resume class requires these commands and packages:

- commands: `latexmk`, `xelatex`;
- packages: `fontspec`, `xeCJK`, `geometry`, `xcolor`, `enumitem`, `etoolbox`,
  `fancyhdr`, `graphicx`, `lastpage`, and `draftwatermark`.

The Ubuntu CI-equivalent packages are:

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

`pdftoppm`, `pdfinfo`, and `pdftotext` support external visual, metadata, and
high-fidelity text inspection. Their absence is reported as `attention` rather
than a universal hard dependency. `resume doctor` executes a minimal isolated
XeLaTeX compilation through `latexmk` and version probes the remaining reported
TeX and Poppler commands, so a stale or broken PATH wrapper does not count as
ready. Export falls back to its in-process PDF
extractor, but a locally selected font whose PDF lacks a usable Unicode map may
still require `pdftotext` for the final identity-projection gate.

## Resume fonts

Font binaries are intentionally absent from Git. The tracked
`system/resume/fonts.json` manifest pins four role-specific files by URL, byte
size, and SHA-256: Source Han Serif SC Regular and Bold 2.003 for body text,
and Noto Sans CJK SC Regular and Bold 2.004 for display text. Together the
downloads are 83,504,676 bytes. Both packages use the SIL Open Font License
1.1, so the public system can reproduce the designed typography without a
private font dependency.

Fetch them once while online:

```text
uv run career-os resume fonts fetch
uv run career-os resume doctor --json
```

The command downloads only the pinned files from `raw.githubusercontent.com`
into `.career-os/fonts/career-os-resume-fonts-1/`, verifies each file before
installation, and refuses to overwrite an unverified existing file. The cache
is local and ignored by Git, so every new checkout or machine needs its own
fetch.

`career-os init` never downloads fonts implicitly. A fresh offline clone can
use the core system, but it cannot build a resume until the verified font files
are available.

For owner-provided fonts, place the binaries below ignored
`.career-os/fonts/` and name them in the handwritten TeX root before
`\documentclass{career-os}`. The CLI and project `latexmkrc` search that
directory recursively. Do not commit or redistribute the files. A missing
filename fails during XeLaTeX compilation; Career OS has no personal font
descriptor or fallback layer.

The release fixtures cover English, Simplified Chinese, and one mixed-language
resume. User data remains Unicode and BCP-47 capable, but the fixed Source Han
Serif SC and Noto Sans CJK SC stack is not a promise of correct typography for
every writing system.

## Final readiness check

For a checkout that will use every local capability:

```text
git --version
uv --version
uv sync --locked
uv run career-os doctor --json
uv run career-os check
uv run career-os resume fonts fetch
uv run career-os resume doctor --json
```

Run `resume fonts fetch` only after network access is available. A passing
`career-os check` validates the tracked default font manifest and confirms that
font binaries did not leak into Git. `career-os resume doctor` proves the
default font bundle and TeX commands are ready; compiling a personal root is
the definitive check for any font filenames configured by that root.
