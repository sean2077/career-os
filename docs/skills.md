# Skill Catalog

Career OS exposes seven authority-aligned Career Skills. The Agent selects and composes them from natural-language outcomes; modes are internal workflow variants rather than separate discovery entries.

| Career Skill | Canonical authority | Modes |
| --- | --- | --- |
| `career-evidence` | Career Evidence | capture, debrief, consolidate |
| `career-strategy` | Career Strategy | position, plan, align |
| `role-market` | Role Market | discover, ingest, screen, compare, review |
| `opportunity-decision` | Opportunity Decision | research, scope, track, decide |
| `career-outlook` | Career Outlook | scan, synthesize, review |
| `capability-readiness` | Capability Readiness | diagnose, learn, study-paper, practice, assess, retest |
| `career-communication` | Career Communication | compose, tailor, validate, export |

## Read-only reviewers

Career Skills remain the workflow orchestrators and canonical record owners.
Three project subagents provide independent, read-only review:

| Subagent | Input boundary | Result |
| --- | --- | --- |
| `blind-interviewer` | Public Interview Packet only | `resume-interview-probe/1` |
| `evidence-auditor` | Internal Evidence Packet and explicit references | `resume-evidence-audit/1` |
| `career-strategy-advisor` | Dated stable authority references and attributable external sources | Source-layered decision brief |

Validate either JSON reviewer before use:

```text
career-os skills validate-reviewer <evidence|probe> [PATH|-]
```

Omitting `PATH` or using `-` reads stdin. A valid result exits `0`, including a
valid result that blocks readiness. Invalid JSON or contract output exits `2`
and fails closed with `blocks_readiness: true`. The validator reports only
`valid`, `blocks_readiness`, and `errors`; it never echoes the packet. An
unavailable reviewer, invalid result, or leaked packet triggers the owning
Skill's fallback and cannot grant readiness, claim approval, or strategy
acceptance.

The opportunity flow deliberately keeps JD screening, company/opportunity
decision, application tracking, resume tailoring/export, and interview
preparation/retest as five independently authoritative blocks.

Bundled companion Skills `conventional-commit` and `agent-scaffold` come from [sean2077/skills](https://github.com/sean2077/skills). Optional recommendations from that project are `semver-release`, `project-docs-organizer`, and `tooling-conventions`.

Bundled Obsidian Skills `obsidian-markdown`, `obsidian-bases`, `json-canvas`, `obsidian-cli`, and `defuddle` come from [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills).

The single bundled OpenCLI Skill `opencli-usage` comes from
[jackwener/OpenCLI](https://github.com/jackwener/OpenCLI). It provides live
adapter discovery only. `opportunity-decision` remains the company-research
orchestrator and may combine OpenCLI with official sources, ordinary web
research, direct URLs, user-provided material, and offline evidence. The
project deliberately does not bundle `smart-search`, raw browser, sitemap,
adapter-authoring, or autofix Skills.

The OpenCLI v1.8.6 package manifest declares Node.js 20 or newer, while the
locked upstream `opencli-usage` prose says Node.js 21. The snapshot remains
unmodified; installation guidance and `career-os doctor` use the package
manifest as the runtime authority.

Exact revisions, source paths, licenses, and tree hashes live in `skills-lock.json`. Bundled external Skill content is not modified.

`career-os skills verify` checks the exact 15-Skill inventory, required
frontmatter, locked external trees, real Claude projections, and the absence of a
`.codex/skills` projection. The canonical tree digest hashes each sorted POSIX
relative path together with the SHA-256 of its file bytes.

Promotion and attribution are confined to this catalog, the root README,
`NOTICE`, and the lock file. They are never injected into career records,
resumes, framework views, or Agent output.

The synthetic selection prompts and hidden oracle are separate files under
`system/tests/fixtures/`. The prompt packet contains only case IDs and natural
language; it contains no expected Skill, mode, or gate result. The oracle covers
every declared mode, adjacent multi-Skill composition, the five independent
opportunity blocks, and the three prompt-time hard gates without adding a router
or workflow DSL.

The report's authorization flag means the Agent must stop for a new approval.
Approval already stated in the current prompt satisfies the preview-export gate;
it must not cause redundant confirmation. Public/application export and external
account or irrecoverable actions remain explicit gates.

Ordinary unit tests validate packet/oracle isolation, coverage, and the report
evaluator. They do **not** claim that an Agent passed a blind behavioral run. To
run that acceptance, give an independent Agent only
`skill-selection-prompts.json`, collect a report with the documented case IDs,
selected Skill/mode pairs, and authorization decisions, then run:

```text
career-os skills verify --selection-report <agent-report.json>
```

Without that independently produced report, verification records the behavioral
gate as `attention`, not `pass`.
