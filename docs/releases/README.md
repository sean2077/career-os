# Releases

## Publication contract

Career OS uses exact `v`-prefixed Git tags and a committed changelog. Each
release synchronizes `career-os.toml`, the Python package version, and the
runtime version mirror, then adds one canonical
`## [vX.Y.Z] — YYYY-MM-DD` changelog section. The hidden
`career-os release notes` contributor command validates and extracts that
section without a generated-notes fallback.

After the release commit is clean and verified, maintainers push `main` before
its annotated tag. `.github/workflows/release.yml` re-runs the repository and
resume gates, revalidates the exact notes, and exclusively creates the matching
GitHub Release. A successful local tag or branch push alone is not a published
release.

## Release evidence

- [v0.1.0](v0.1.0.md): clean-install MVP, Home-led public extraction, seven-authority golden journey, handwritten TeX resumes, bilingual Workbenches, and stable privacy/release gates.
