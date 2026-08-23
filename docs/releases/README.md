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

- [v0.7.1](v0.7.1.md): reduces default Agent context, adds outcome-first workflow routing, and aligns the complete Skill mode matrix with executable blind-selection coverage.
- [v0.7.0](v0.7.0.md): makes auxiliary Skills optional and provenance-checked, consolidates same-purpose project preparation records, and grounds every Blind Interviewer question in a visible resume, JD, or prior-answer basis.
- [v0.6.0](v0.6.0.md): adds guarded QuickAdd record workflows and interview views, decomposes and accelerates checks, supports linked-worktree Vault context, and makes signed-in BOSS explicitly user-operated.
- [v0.5.0](v0.5.0.md): disambiguates the root homepage filenames across Obsidian assets, deterministic tooling, tests, and documentation.
- [v0.4.0](v0.4.0.md): adds safer shareable-resume defaults, language-aware filenames, audited link preservation, and unified four-character export IDs.
- [v0.3.1](v0.3.1.md): rolls forward the immutable v0.3.0 tag after removing a stale deleted-test path from the release workflow and revalidating the complete release boundary.
- [v0.3.0](v0.3.0.md): removes Defuddle/OpenCLI, adds localized Recent Changes views and JD-to-Company composition, consolidates test cost, and records an immutable Home-to-public extraction supplement.
- [v0.2.0](v0.2.0.md): fixed state roots, schema-3 records, deterministic cleanup, optional read-only OpenCLI acquisition, filename-based resume fonts, and reviewed Home-to-public extraction.
- [v0.1.0](v0.1.0.md): clean-install MVP, Home-led public extraction, seven-authority golden journey, handwritten TeX resumes, bilingual Workbenches, and stable privacy/release gates.
