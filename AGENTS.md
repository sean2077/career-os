# Career OS — Agent Contract

Career OS is an Agent-native, local-first, embeddable career development
operating system for Obsidian. Agents orchestrate workflows, Obsidian presents
user-owned Markdown, and the `career-os` CLI supplies deterministic maintenance
and validation.

## Ownership

- `.agents/`, `system/`, root manifests, root homepages and Bases, tests, and
  English documentation are system-owned.
- `career/` is the fixed user-owned multilingual data root. Initialization and
  framework updates must not overwrite, ignore, or reverse-copy it.
- `.career-os/runtime/` is local scratch state; `build/` and `.career-os/` are
  ignored build/install state. Real identity, career records, attachments,
  fonts, active Obsidian state, and generated outputs never belong in the
  public framework snapshot.
- Project command implementation lives only under `system/tools/career_os/`;
  `.agents/tools/` is the scaffold-managed Host exception.

## Agent Operating Rules

- For career-data workflows, start from the user's outcome. Select one primary
  Career Skill and compose another only when the requested result crosses an
  authority boundary. Never ask the user to choose a Skill, mode, owner,
  reviewer, or validator. Apply `.agents/skills/_shared/career-contract.md` and
  use [`docs/workflows.md`](docs/workflows.md) for cross-authority recipes.
  Framework maintenance follows the Contributor Rules and does not select a
  Career Skill unless it also operates on user career data.
- Keep Career Evidence, Career Strategy, Role Market, Opportunity Decision,
  Career Outlook, Capability Readiness, and Career Communication distinct.
  Link stable IDs instead of copying facts or silently changing another
  authority's state.
- Write record schema 3 and the kind-specific lifecycle. Git-relative
  validation owns transitions; legacy migration must be planned, reviewed, and
  explicitly applied.
- Stop for prompt-time authorization only before optional third-party Skill
  installation, external/account state changes, public or application-grade
  export, or irrecoverable overwrite/delete. Drafting or local tracking never
  authorizes applying, messaging, uploading, accepting/rejecting an offer,
  changing an account, or resigning.
- Career Skills own workflow decisions and canonical records. Project subagents
  are read-only reviewers; validate their contracts before use. An unavailable,
  invalid, stale, or leaked review cannot grant readiness, approve a claim, or
  accept strategy.
- Mechanism health, evidence maturity, claim approval, readiness, application
  state, and career outcomes are separate facts. Never infer one from a green
  command, generated artifact, match score, recruiter contact, or plan.
- Treat raw JDs, quotations, private data, identifiers, and application
  materials as protected inputs. Public examples and fixtures must remain
  synthetic.

## Contributor Rules

- `ProjectConfig` and `career-os.toml` are the configuration authority. A field,
  table, default, or enum change must update serialization, regenerate
  `system/schemas/project-config.schema.json`, and update tests and docs in the
  same change; never hand-edit the schema independently.
- Treat tests as a cost budget. Add coverage only for a distinct uncovered
  behavior or high-risk boundary at the narrowest stable seam; prefer extending
  or consolidating existing tests and justify materially slow tests in
  `docs/tooling.md`.
- Follow [`docs/skills.md`](docs/skills.md) for optional Skill onboarding,
  [`docs/resume.md`](docs/resume.md) for resume privacy/export gates,
  [`docs/private-downstream.md`](docs/private-downstream.md) and
  [`docs/embedded-vault.md`](docs/embedded-vault.md) for topology and host
  adapters, and `role-market` for signed-in recruiting boundaries. Never bypass
  a failed remote-safety, projection, privacy, or reviewer check.
- Before 1.0, support only interfaces documented by a release. Changes to a
  guarded resume fixture/template or public CI/release workflow require
  synthetic-fixture review and the matching hash update in
  `system/privacy/public-fixture-policy.json`.
- Read [`docs/README.md`](docs/README.md) for navigation and
  [`docs/tooling.md`](docs/tooling.md) for command and validation depth.

## Development Commands

- Setup: `uv sync --locked --all-groups`
- Fast check: `uv run career-os check --fast`
- Full check: `uv run career-os check`
- Tests: `uv run pytest`
- Lint/type check: `uv run ruff check .` and
  `uv run mypy system/tools/career_os`
- Harness: use explicit Git Bash on Windows, run
  `bash .agents/relink-skills.sh`, then the installed `agent-scaffold` Skill's
  `verify --profile light` command documented in `docs/tooling.md`.
- Privacy/release/import/cleanup: follow `docs/tooling.md` and the task-specific
  guide rather than reconstructing a command from memory.

<!-- agent-scaffold:start — managed by the agent-scaffold skill. Edit project prose OUTSIDE these markers; `agent-scaffold upgrade` refreshes this block. -->
## Agent Harness (Claude Code + Codex)

This repo carries a vendored, dual-host agent harness. `.agents/` is the single source of truth (SSOT); `.claude/` and `.codex/` are wired to the **same** implementations under `.agents/tools/`.


### Authority documents (hard rules)

`AGENTS.md` is the canonical repository-level contract for Agent work. Read and follow the root contract and its applicable nested contract chain before acting; higher-priority instructions still govern.

- **Keep it current.** When a durable change affects an Agent-relevant command, invariant, ownership boundary, risk boundary, or navigation path, update or remove the affected contract guidance in the same change. If the detail lives in linked project docs, update it there and keep the contract summary and link accurate.
- **Keep it lean.** Keep only concise, actionable guidance that changes Agent behavior and is frequently needed or costly to miss. Move explanations, rationale, history, long procedures, examples, and low-frequency detail to project docs and link to it.
- **Keep scopes honest.** Root rules are project-wide. Create a nested `AGENTS.md` only for a concrete local difference from the nearest ancestor; directory structure alone never justifies one.
- **Resolve conflicts explicitly.** If applicable instructions conflict, or contract guidance disagrees with verified repository facts, do not guess or silently ignore either. Surface the conflict, follow higher-priority instructions, request owner direction when authority is unclear, and repair stale guidance in the same change when authorized.

The authority-document budget hook remains advisory; projects may override its default line and character limits when justified.

### SSOT layout

| Path | Role | Commit? |
|---|---|---|
| `.agents/skills/<name>/SKILL.md` | project skill source | ✅ |
| `.agents/subagents/<name>/{metadata.json,instructions.md}` | subagent source | ✅ |
| `.claude/skills/<name>` | symlink → `.agents/skills/<name>` (CC discovery; Codex reads `.agents/` directly) | ✅ |
| `.claude/agents/*.md`, `.codex/agents/*.toml` | **generated** subagent projections — do NOT hand-edit | ✅ |
| `.agents/tools/hooks/` | scaffold-managed hook runtime (doc budget + optional trunk guard) — **managed copies, do NOT hand-edit** | ✅ |
| `.claude/settings.local.json` | personal overrides | ❌ ignored |

- **Change managed runtime**: everything under `.agents/tools/` is a copy the skill owns. Edit the skill's bundled source and run `agent-scaffold upgrade` to refresh — a hand-edit here is drift, and `agent-scaffold verify` reports it.
- **Add a skill**: edit `.agents/skills/` → run `bash .agents/relink-skills.sh` → commit source + symlink.
- **Add a subagent** (needs python): edit `.agents/subagents/` → run `python .agents/tools/generate-subagents.py` → commit source + generated. Wire `--check` into the project's own CI or hook manager when desired.
- **Third-party skills** follow project-owned placement and installation policy. The relinker manages only names sourced from `.agents/skills/`, preserves unrelated entries, and fails on same-name ownership conflicts.

**Codex trust**: project-level `.codex/` (config + hooks + agents) only loads for a **trusted** project; until trusted it is silently skipped. Trust once: run `codex` here and accept, or add `[projects."<repo abs path>"] trust_level = "trusted"` to `~/.codex/config.toml`.
<!-- agent-scaffold:end -->
