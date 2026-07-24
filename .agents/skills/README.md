# .agents/skills/ — project skill SSOT

Project-authored Skills and project-approved locked third-party snapshots live
here. Claude Code discovers matching real symlinks under `.claude/skills/`;
Codex reads `.agents/skills/` directly.

## Change a project skill

1. Edit `.agents/skills/<name>/SKILL.md` and any local resources.
2. Run `bash .agents/relink-skills.sh`.
3. Commit the source and `.claude/skills/<name>` symlink together.

Rules:

- Do not hand-edit `.claude/skills/` projections.
- Locked third-party Skills use this SSOT plus `skills-lock.json`, `NOTICE`,
  `system/licenses/`, and the deterministic SBOM; do not install a parallel
  project copy through a Host-native directory.
- Prefix support-only directories with `_`; the relinker skips them.
- The relinker preserves unrelated entries, but a same-name project and third-party skill is an ownership conflict.

For full authoring conventions, naming, and third-party policy details, load the
`agent-scaffold` skill's `references/harness-layout.md` on demand.
