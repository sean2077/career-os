# .agents/skills/ — project skill SSOT

The seven project-authored Career Skills live here. Claude Code discovers
matching real symlinks under `.claude/skills/`; Codex reads `.agents/skills/`
directly.

## Change a project skill

1. Edit `.agents/skills/<name>/SKILL.md` and any local resources.
2. Run `bash .agents/relink-skills.sh`.
3. Commit the source and `.claude/skills/<name>` symlink together.

Rules:

- Do not hand-edit `.claude/skills/` projections.
- Optional third-party Skills are local installations described by
  `system/skills/recommendations.json`; their six known source and projection
  paths plus the installer-owned root `skills-lock.json` are ignored.
- After a user-authorized project installation, run the relinker to establish
  or repair Claude Code projections. Never treat installation as Career
  evidence or readiness.
- Prefix support-only directories with `_`; the relinker skips them.
- The relinker preserves unrelated entries, but a same-name project and
  third-party Skill is an ownership conflict.

For full authoring conventions, naming, and third-party policy details, load the
installed `agent-scaffold` Skill's `references/harness-layout.md` on demand.
