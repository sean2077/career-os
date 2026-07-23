# Semantic Contract Audit

This audit records the public framework contracts frozen for `v0.1.0`. It
describes the `standalone-framework` implementation only. It is not an
installation or prerelease-upgrade guide, and no personal Career Home data was
used as public fixture content.

## Completed contracts

| Area | Deterministic contract |
| --- | --- |
| Seven authorities | Career Evidence, Career Strategy, Role Market, Opportunity Decision, Career Outlook, Capability Readiness, and Career Communication remain distinct record authorities linked by stable references. |
| Record model | Schema 2 is a discriminated union with kind-specific lifecycles, complete status histories for promoted states, strict timestamps, and unknown top-level fields rejected. |
| Evidence | Approved Claims require grounded Work or reviewed Story support; raw Captures cannot grant approval. |
| Strategy and Outlook | Strategy cannot consume pending Outlook authority. Reviewed Outlook requires personal-fit, market-revealed, and verified independent-external signals. |
| Role Market | Channel and Direction records are distinct authorities. A JD stores source fidelity and screening state in one `market.jd` note whose `JD 原文` hash and `重新评价` section are checked. |
| Opportunity | Company, Scope, Engagement, Decision, events, stage, and application state stay separate. Recruiter contact never implies application. |
| Readiness | Knowledge and practice gaps close only through a verified passing Retest; production-evidence gaps require grounded Work evidence. |
| Communication | Profiles, Audits, Resumes, and Exports have independent lifecycles. Validated Resumes consume approved Claims; preview export removes contact identity and avatar before final PDF checks. |
| Reviewers | Project subagents are read-only reviewers. Their packet contracts and generated host projections are validated, and unavailable or invalid review cannot grant readiness, claim approval, or strategy acceptance. |
| Obsidian | Root English and Chinese homepages, two shared views, two Canvas files, one dashboard, and ten paired Workbench Bases are tracked static framework assets. `views build` validates and lists all sixteen assets without rendering private data. |
| Downstream safety | Split-downstream synchronization uses reviewed exact tags, hash-bound plans, protected paths, rollback receipts, and a fetch-only public `upstream`. |
| Supply chain | Locked Python packages, bundled Skills, downloadable fonts, notices, schemas, subagent projections, and the CycloneDX SBOM are checked from committed sources. |

## Public data and view boundary

The configured data root is user-owned. The public repository ships no starter
career dataset; all committed examples are isolated synthetic test fixtures.
Identity, attachments, font binaries, active `.obsidian/` state, `career/`,
`runtime/`, `build/`, and `.career-os/` are outside the public release snapshot.

The root homepages and common Obsidian assets are static system files.
Initialization never creates or overwrites either homepage or any Base.

## Acceptance evidence boundary

The automated golden journey proves deterministic clean initialization, record
validation, cross-authority references, wikilinks, static view projection, and
synthetic preview-export privacy. It does not claim that a real Codex session,
Claude Code session, or live Obsidian interaction was run.

Hosted cross-platform jobs and the tag-triggered publisher remain publication
gates. Local completion does not establish hosted success, create a tag, or
publish a GitHub Release.

Applications, messages, uploads, account changes, offer decisions, and
resignation always require a separate explicit request and are never inferred
from green tooling.
