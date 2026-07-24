# Career OS — Agent Contract

Career OS is an Agent-native, local-first, embeddable career development operating system for Obsidian. Agent workflows are the primary interaction surface; Obsidian supplies content and views; the `career-os` CLI supplies deterministic maintenance and validation.

## Ownership

- `.agents/`, `system/`, root manifests, root `Home.md` and `主页.md`, tests, and English documentation are system-owned.
- `career/` is the fixed user-owned multilingual data root. It is eligible for the user's Git history; system updates and initialization must not overwrite or ignore it.
- `.career-os/runtime/` is the fixed local scratch root. Root `runtime/` remains ignored only as a protected legacy boundary and has no producer. Root `Home.md` and `主页.md`, common Obsidian views, and the paired English/Chinese Workbench Bases under `system/obsidian/bases/` are tracked system assets, not runtime or data-root copies. `career-os init` never creates, copies, renders, or overwrites either homepage or any Base. `build/` and `.career-os/` remain ignored build/install state.
- Project command implementation lives only under `system/tools/career_os/`. `.agents/tools/` is the scaffold-managed Host exception.

## Working Rules

- Start from the user's natural-language outcome and select or compose the seven Career Skills. Never ask the user to choose a Skill, mode, owner, worker, or validator.
- Keep Career Evidence, Career Strategy, Role Market, Opportunity Decision, Career Outlook, Capability Readiness, and Career Communication as distinct canonical authorities. Cross-authority workflows use stable references rather than copied facts.
- Career Skills remain workflow and record owners. Project subagents are read-only reviewers; validate their JSON contracts before use, and treat unavailable, invalid, or leaked review as fallback that cannot grant readiness, claim approval, or strategy acceptance.
- OpenCLI is an optional read-only acquisition transport for Opportunity Decision, never a research authority or default router. Call only configured adapter commands that the live registry also marks `access: read`; do not use its raw browser, external, plugin, write, or self-repair surfaces in company research.
- Write record schema 3 and its kind-specific lifecycle. Git-relative validation owns lifecycle transitions; plan, review, and explicitly apply migrations for older user records.
- `ProjectConfig` is the `career-os.toml` authority. Any field, table, default, or enum change must update its serializer, regenerate `system/schemas/project-config.schema.json`, and update related tests and documentation in the same change; never hand-edit the schema independently.
- Prompt-time authorization is limited to external/account state changes, public or application-grade export, and irrecoverable overwrite/delete.
- Applications, messages, uploads, account changes, offer decisions, and resignation always require a separate explicit request.
- Never infer evidence maturity, readiness, application success, or career outcomes from successful tooling or generated artifacts.
- Resume TeX roots under `career/` are user-owned. Personal font filenames are configured in `career-os.toml` and resolved by name without content pins; generated TeX remains ignored local state, and every font binary must stay under `.career-os/fonts/` and never enter Git.
- Do not reintroduce per-resume JSON manifests, personal font-profile records, or template selectors. Handwritten TeX roots, adjacent `identity.tex`, fixed preview/application profiles, and the fixed system class are the resume configuration surface; `system/resume/fonts.json` only locks downloadable system defaults.
- Raw `resume build` PDFs are internal. Only `resume export` may create a shareable PDF, and application export requires the explicit confirmation and evidence gates documented in `docs/resume.md`.
- Resume roots are discovered from `\documentclass{career-os}`, use the fixed system class and adjacent `identity.tex`, and support fixed preview/application profiles by resume name. Missing named fonts fail during XeLaTeX compilation. Preview export must exclude email, phone, and avatar; never bypass the source-bundle or final-PDF projection checks.
- In `standalone-framework`, framework work is implemented and validated without real career records, personal identity, attachments, local fonts, active `.obsidian/` state, `runtime/`, `build/`, or `.career-os/` in the tracked snapshot. In a private `integrated-workbench` or `split-downstream`, `career/` is eligible for that private Git history but must never be pushed or reverse-copied to this public repository.
- A personal Career Home may configure this canonical repository as optional `upstream`. When configured in that downstream, it must remain fetch-only with `remote.upstream.pushurl=DISABLED`; the public repository must never remain a pushable personal `origin`, and failed remote-safety checks must not be bypassed.
- The recommended embedded downstream is a sibling repository projected into the Vault by a host-tracked relative directory symlink. Configure its Vault-relative POSIX path with `--vault-mount`; never replace it with an absolute link or an ignored nested copy.
- `career-os cleanup` is dry-run by default and enumerates only product-owned,
  reproducible roots: configured build output, standard root development and
  distribution caches, `.career-os/generated/`, `.career-os/tmp/`, and Python
  caches under `system/tests/` and `system/tools/`. All other ignored state,
  including `.venv/`, fonts, migrations, runtime acquisitions, and unknown
  paths, is outside its scan; use `--apply` only after reviewing the report.
- Exact reviewed annotated-tag synchronization applies only to an initialized `split-downstream` installation. Never reverse-copy `career/` or any other private/local path into this repository.
- Before 1.0, do not invent backward-compatibility or user-data migration promises. The schema-2 project configuration and schema-3 record boundary in `v0.2.0` is intentionally fail-closed for legacy fields and requires explicit migration or reinitialization.
- Any change to a guarded resume test, resume TeX fixture/template, or public CI/release workflow requires deliberate synthetic-fixture review and an updated blob hash in `system/privacy/public-fixture-policy.json`. Never approve a guarded blob containing real identity or career data, and never expose matched private values in audit output.
- Read `docs/README.md` for navigation and `docs/tooling.md` for commands and validation depth.

## Development Commands

- Setup: `uv sync --locked --all-groups`
- Legacy import: review `career-os import plan`, then explicitly run `import apply`; never infer dispositions or record state.
- Fast check: `uv run career-os check --fast`
- Full check: `uv run career-os check`
- Tests: `uv run pytest`
- Lint/type check: `uv run ruff check .` and `uv run mypy system/tools/career_os`
- Harness: use explicit Git Bash on Windows, then run `bash .agents/relink-skills.sh` and the scaffold `verify --profile light` command documented in `docs/tooling.md`.
- Privacy: `uv run career-os release privacy --root . --ref HEAD --history --private-root <private-career-home>`
- Releases: synchronize all version authorities, add one exact `## [vX.Y.Z] — YYYY-MM-DD` changelog section, and validate it with `career-os release notes`. Push `main`, wait for its CI to succeed, then push the annotated tag; CI runs only for `main` and pull requests, while the tag-triggered workflow exclusively owns GitHub Release publication.

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
| `.agents/tools/hooks/` | scaffold-managed hook runtime (doc budget + optional trunk guard) | ✅ |
| `.claude/settings.local.json` | personal overrides | ❌ ignored |

- **Add a skill**: edit `.agents/skills/` → run `bash .agents/relink-skills.sh` → commit source + symlink.
- **Add a subagent** (needs python): edit `.agents/subagents/` → run `python .agents/tools/generate-subagents.py` → commit source + generated. Wire `--check` into the project's own CI or hook manager when desired.
- **Third-party skills** follow project-owned placement and installation policy. The relinker manages only names sourced from `.agents/skills/`, preserves unrelated entries, and fails on same-name ownership conflicts.

**Codex trust**: project-level `.codex/` (config + hooks + agents) only loads for a **trusted** project; until trusted it is silently skipped. Trust once: run `codex` here and accept, or add `[projects."<repo abs path>"] trust_level = "trusted"` to `~/.codex/config.toml`.
<!-- agent-scaffold:end -->
