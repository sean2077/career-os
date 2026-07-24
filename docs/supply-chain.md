# Supply Chain and Attribution

Career OS separates project-owned MIT work from locked external assets.

- `uv.lock` owns exact Python dependency resolution.
- `skills-lock.json` owns source repositories, exact revisions, source paths,
  licenses, attribution, and canonical tree SHA-256 values for bundled Skills.
- `system/resume/fonts.json` owns the exact Source Han Serif SC 2.003 and Noto
  Sans CJK SC 2.004 roles, URLs, sizes, and SHA-256 values. Font binaries
  remain outside Git.
- Owner-provided font binaries may be named directly by personal TeX roots.
  They remain under ignored `.career-os/fonts/`, are not public dependencies,
  and do not enter the project SBOM or NOTICE.
- `NOTICE` and `system/licenses/` preserve human-readable attribution and
  license texts.
- `system/sbom.cdx.json` is a deterministic CycloneDX 1.5 inventory of the
  runtime Python closure, bundled Skill trees, and optional font files.

`career-os check --fast` regenerates the expected SBOM model in memory and
fails if the tracked SBOM is stale relative to any lock. The same gate rejects
any font binary visible to Git anywhere in the repository, missing notices,
executable project tooling
outside `system/`, generated state in Git, an active `.obsidian` directory, or
an invalid Agent harness symlink.

External dependencies retain their upstream terms. The Career OS license does
not relicense bundled Skills or the Source Han and Noto font bundle.
Career OS does not grant rights to owner-provided local fonts or redistribute
them.

The bundled `opencli-usage` Skill is an unmodified snapshot from
jackwener/OpenCLI and retains the Apache License 2.0. The OpenCLI executable,
Browser Bridge extension, browser profile, and login state are per-device
optional dependencies; they are not vendored into this repository or its SBOM.

The temporary resume work-experience projection is backed by the exact
PyMuPDF4LLM/PyMuPDF/PyMuPDF Layout closure in `uv.lock`. Upstream metadata
offers PyMuPDF4LLM and PyMuPDF under AGPL-3.0 or an Artifex commercial license,
and PyMuPDF Layout under PolyForm Noncommercial or an Artifex commercial
license. `NOTICE` calls out this boundary explicitly; the project MIT license
does not override those terms.
