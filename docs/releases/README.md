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
- [v0.1.0-rc.5](v0.1.0-rc.5.md): private sibling downstreams, complete installation boundaries, and typed same-company comparison.
- [v0.1.0-rc.4](v0.1.0-rc.4.md): application-policy Claim gates remain fail-closed for preview exports.
- [v0.1.0-rc.3](v0.1.0-rc.3.md): clean-room import, closed resume bundles, and verified Skill selection gates.
- [v0.1.0-rc.2](v0.1.0-rc.2.md): schema-2 semantic migration, native Canvas guides, and first public prerelease.
- [v0.1.0-rc.1](v0.1.0-rc.1.md): initial local release candidate and verification evidence.
