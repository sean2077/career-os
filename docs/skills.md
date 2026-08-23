# Skill Catalog

Career OS exposes seven authority-aligned Career Skills. The Agent selects and composes them from natural-language outcomes; modes are internal workflow variants rather than separate discovery entries. Keep one primary owner, then load only the additional Skills whose distinct authority outputs can materially change the deliverable. Follow [`workflows.md`](workflows.md) for bounded cross-authority recipes.

| Career Skill | Canonical authority | Modes |
| --- | --- | --- |
| `career-evidence` | Career Evidence | capture, debrief, consolidate |
| `career-strategy` | Career Strategy | position, plan, align |
| `role-market` | Role Market | discover, channel, ingest, screen, compare, review |
| `opportunity-decision` | Opportunity Decision | research, scope, track, decide |
| `career-outlook` | Career Outlook | scan, synthesize, review |
| `capability-readiness` | Capability Readiness | diagnose, learn, study-paper, practice, assess, retest |
| `career-communication` | Career Communication | compose, tailor, validate, audit, export |

## Execution model

- Load the shared contract once, then the selected Skill and the smallest decision-relevant record set. Authority seeds are required before canonical writes or lifecycle/gate judgments, not for every exploratory answer.
- Keep transient analysis and unsent one-off wording answer-only. Persist only an owned durable outcome; reuse existing records by identity, purpose, and lifecycle.
- Search narrow metadata and stable references before opening bodies. Compose additional authorities one at a time only while their results can change the deliverable; stop when the primary owner has enough to finish.
- Batch canonical writes and run `uv run career-os check` once at the end. Reviewers are escalation tools for material gates, not default workers.

## Read-only reviewers

Career Skills remain the workflow orchestrators and canonical record owners. Three project subagents provide independent, read-only review:

| Subagent | Input boundary | Result |
| --- | --- | --- |
| `blind-interviewer` | Public Interview Packet only; causally grounded current question | `resume-interview-probe/2` |
| `evidence-auditor` | Internal Evidence Packet and explicit references | `resume-evidence-audit/1` |
| `career-strategy-advisor` | Dated stable authority references and attributable external sources | Source-layered decision brief |

Validate either JSON reviewer before use:

```text
uv run career-os skills validate-reviewer <evidence|probe> [PATH|-]
```

Omitting `PATH` or using `-` reads stdin. A valid result exits `0`, including a valid result that blocks readiness. Invalid JSON or contract output exits `2` and fails closed with `blocks_readiness: true`. The validator reports only `valid`, `blocks_readiness`, and `errors`; it never echoes the packet. An unavailable reviewer, invalid result, or leaked packet triggers the owning Skill's fallback and cannot grant readiness, claim approval, or strategy acceptance.

The Blind Interviewer classifies each current question as `public-surface`, `industry-standard`, or `candidate-answer` and returns the exact visible resume/JD/answer excerpt that makes it available. Industry-standard questions may probe ordinary ownership, mechanism, tradeoff, measurement, failure, or recovery for a publicly named domain; they may not introduce private project nouns or implementation details.

The opportunity flow deliberately keeps JD screening, company/opportunity decision, application tracking, resume tailoring/export, and interview preparation/retest as five independently authoritative blocks. Screening an identified-employer JD reuses the canonical Company when it is fresh and decision-complete, and composes `opportunity-decision` only when Company resolution or refresh is needed. Company quality may affect priority or risk but never evidence fit or application state.

## Optional auxiliary Skills

The tracked framework contains only the seven Career Skills. Six auxiliary Skills are recommendations, not redistributed snapshots:

| Group | Audience | Skills | Reviewed upstream |
| --- | --- | --- | --- |
| `obsidian` | ordinary Career OS use | `obsidian-markdown`, `obsidian-bases`, `json-canvas`, `obsidian-cli` | [`kepano/obsidian-skills`](https://github.com/kepano/obsidian-skills) |
| `contributor` | framework maintenance only | `agent-scaffold`, `conventional-commit` | [`sean2077/skills`](https://github.com/sean2077/skills) |

`system/skills/recommendations.json` is the authority for group membership, audience, upstream repository, license, reviewed revision and tree hashes, and the verified `skills` installer version. It is a reviewed recommendation manifest, not an installation lock and not a claim that upstream content will remain unchanged. Each reviewed tree digest hashes every sorted POSIX-relative path together with the SHA-256 of its content. UTF-8 text normalizes CRLF to LF so the same reviewed source has one digest across Host checkouts; binary content retains its exact bytes. Contributor recommendations use either a stable SemVer tag or the explicitly reviewed `main` branch. Unlike ordinary Obsidian `main` recommendations, contributor installs must still match the reviewed revision's tree digests, so later upstream changes fail closed until this manifest is reviewed again.

`career-os init` preserves its existing JSON fields and adds `skill_onboarding` for the ordinary `obsidian` audience. The same read-only contract is available at any time:

```text
uv run career-os skills status --json
uv run career-os skills status --audience contributor --json
```

The report detects each recommended Skill at project and global scope for Codex and Claude Code. It reports missing or partial groups, reviewed-content drift, source mismatches, stale preferences, and project/global duplicates. Duplicates and `main` content drift are `attention`; Career OS never deletes either copy. A changed recommendation revision, an invalid installation, or an explicit reset makes the group unresolved again.

Only when `requires_user_choice` is true does the Agent explain the source and ask for `project`, `global`, or `skip` plus the target Host(s). After a user chooses installation, the Agent executes the report's argument arrays with telemetry disabled and explicit Skill and Host values. The CLI itself never uses the network, prompts, or invokes `npx`. A project installation is followed by `bash .agents/relink-skills.sh`, then status verification. The preference is recorded only after every Skill is visible to every selected Host:

```text
uv run career-os skills configure --group obsidian --scope project --agent codex
uv run career-os skills configure --group obsidian --scope global --agent codex --agent claude-code
uv run career-os skills configure --group obsidian --scope skip
uv run career-os skills configure --group obsidian --reset
```

The ignored `.career-os/skill-onboarding.json` holds the local choice. Known project Skill paths, their Claude projections, and the installer-owned root `skills-lock.json` are also ignored, so project scope is deliberately checkout-local even though the upstream installer commonly treats it as team-shared state.

`career-os skills verify` requires the seven core Skills, their real Claude projections, the recommendation manifest, and the isolated selection fixtures. Any known auxiliary subset is allowed; a missing auxiliary Skill does not affect the core check. Unknown additional Skills, invalid frontmatter, bad projections, or a `.codex/skills` projection still fail.

The synthetic selection prompts and hidden oracle are separate files under `system/tests/fixtures/`. The prompt packet contains only case IDs and natural language; it contains no expected Skill, mode, or gate result. The oracle covers every declared mode, the five independent opportunity blocks, and the three prompt-time hard gates. It also preserves multi-authority cases, including requests that span three or more Skills and use outcome language instead of simply repeating mode names. This directly catches the under-routing failure where a complex request receives only its most obvious Skill, without adding a router or workflow DSL.

The report's authorization flag means the Agent must stop for a new approval. Approval already stated in the current prompt satisfies the preview-export gate; it must not cause redundant confirmation. Public/application export and external account or irrecoverable actions remain explicit gates.

Ordinary unit tests validate packet/oracle isolation, coverage, and the report evaluator. They do **not** claim that an Agent passed a blind behavioral run. To run that acceptance, give an independent Agent only `skill-selection-prompts.json`, collect a report with the documented case IDs, selected Skill/mode pairs, and authorization decisions, then run:

```text
uv run career-os skills verify --selection-report <agent-report.json>
```

Without that independently produced report, verification records the behavioral gate as `attention`, not `pass`.
