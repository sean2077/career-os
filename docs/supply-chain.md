# Supply Chain and Attribution

Career OS separates project-owned MIT work, reproducible external assets, and optional tools that are only recommended.

- `uv.lock` owns exact Python dependency resolution.
- `system/skills/recommendations.json` records the two optional Skill groups, authoritative upstream repositories, licenses, reviewed revisions and tree hashes, and the installer version used to verify the workflow. It is not an installation lock, and the recommended Skills are not distributed by Career OS.
- A root `skills-lock.json` or global `.agents/.skill-lock.json` is owned by the external installer. The project lock and known project Skill paths are ignored local state; neither enters public extraction or the SBOM.
- `system/resume/fonts.json` owns the exact Source Han Serif SC 2.003 and Noto Sans CJK SC 2.004 roles, URLs, sizes, and SHA-256 values. Font binaries remain outside Git.
- Owner-provided font binaries may be named directly by personal TeX roots. They remain under ignored `.career-os/fonts/`, are not public dependencies, and do not enter the project SBOM or NOTICE.
- `NOTICE` and `system/licenses/` preserve human-readable attribution and license texts for assets and runtime boundaries actually distributed by the project.
- `system/sbom.cdx.json` is a deterministic CycloneDX 1.5 inventory of the runtime Python closure and optional reproducible font files.

`career-os check --fast` regenerates the expected SBOM model in memory and fails if the tracked SBOM is stale relative to `uv.lock` or the font manifest. It separately validates the Skill recommendation manifest and its generated schema. The same gate rejects any font binary visible to Git anywhere in the repository, missing notices, executable project tooling outside `system/`, generated state in Git, an active `.obsidian` directory, or an invalid Agent harness symlink.

External dependencies retain their upstream terms. The Career OS license does not relicense the Source Han and Noto font bundle. Optional Skills retain their own upstream terms if a user chooses to install them; their inclusion in the recommendation manifest is not redistribution. Career OS does not grant rights to owner-provided local fonts or redistribute them.

The temporary resume work-experience projection is backed by the exact PyMuPDF4LLM/PyMuPDF/PyMuPDF Layout closure in `uv.lock`. Upstream metadata offers PyMuPDF4LLM and PyMuPDF under AGPL-3.0 or an Artifex commercial license, and PyMuPDF Layout under PolyForm Noncommercial or an Artifex commercial license. `NOTICE` calls out this boundary explicitly; the project MIT license does not override those terms.
