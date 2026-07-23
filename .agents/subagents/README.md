# .agents/subagents/ — project subagent SSOT

Each project-owned subagent lives in
`.agents/subagents/<name>/{metadata.json,instructions.md}`. The generator writes
the Claude Code and Codex projections; never hand-edit those generated files.

```bash
python .agents/tools/generate-subagents.py
python .agents/tools/generate-subagents.py --check
```

Commit the source plus `.claude/agents/<name>.md` and
`.codex/agents/<name>.toml` together. Names use lowercase ASCII letter groups
separated by single hyphens. `.gitkeep`, this README, and `_`-prefixed support
entries are the only non-agent children allowed here.

## Installed reviewers

| Name | Packet or evidence boundary | Output |
| --- | --- | --- |
| `blind-interviewer` | Public Interview Packet only; no tools or internal evidence | `resume-interview-probe/1` |
| `evidence-auditor` | Internal Evidence Packet and its explicit references only | `resume-evidence-audit/1` |
| `career-strategy-advisor` | Dated authority references and attributable external sources | Source-layered decision brief |

Career Skills remain the orchestrators and record owners. These subagents only
produce read-only reviewer results. Validate the two JSON reviewers with
`career-os skills validate-reviewer`; an unavailable reviewer, invalid result,
or leaked packet triggers the Skill's fallback and cannot grant readiness,
claim approval, or strategy acceptance.

Hook-manager and CI integration are project-owned. Wire the `--check` command
where it fits the project rather than expecting the scaffold to choose a tool.

For the full metadata schema, import rules, validation, and an optional example,
load the `agent-scaffold` skill's `references/subagents.md` on demand.
