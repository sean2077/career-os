# Data Model

Every canonical Markdown record uses record schema 2: a shared envelope plus a
kind-specific payload and lifecycle. The body is free-form Unicode content;
enum values, relation keys, and schema keys remain English for portability.

Identity is an opaque UUID and never depends on a filename. Internal references use stable IDs. References to notes outside the Career OS data root use Vault-relative POSIX paths through typed `host_refs`.

The default visibility is `private`. A record or claim must be explicitly marked `shareable` or `public` before an export may consume it.

## Record envelope

Every record has a UUID4 `id`, English `kind`, `schema_version: 2`, RFC 3339
timestamps, optional BCP 47 `languages`, `visibility`, internal `refs`, and
Vault-facing `host_refs`. It also has a typed `status` and, after leaving an
initial state, a complete ordered `status_history` whose transitions must be
legal for that kind. Filenames and bodies may use any Unicode language;
identity survives a file move. Unknown top-level fields are rejected.

Initial kinds are grouped by authority:

| Authority | Kinds |
| --- | --- |
| Career Evidence | capture, work, story, claim |
| Career Strategy | positioning, lane, plan |
| Role Market | channel, direction, JD |
| Opportunity Decision | company, scope, engagement, decision |
| Career Outlook | signal, thesis, review |
| Capability Readiness | gap, note, session, assessment |
| Career Communication | profile, resume, audit, export |

The complete English enum values live in `system/schemas/record-envelope.schema.json`.
That schema is generated from and checked for exact equality with the runtime
Pydantic model, so the public contract and implementation cannot silently drift.

Kind-specific fields make critical distinctions machine-checkable: Captures
carry provenance and attribution; Work carries contribution scope and evidence
strength; Channels carry rank and a last-verified date; JDs carry source fidelity
and a fingerprint of the exact `## JD 原文` section together with screening fit,
preference, priority, manual signal, growth, gaps, and next action. Source age is
an orthogonal `is_stale` value rather than a review status. Engagements carry typed
chronological events, including explicit
`instant`/`day`/`month`/`year` precision when a legacy or external source is
less precise; Outlook Reviews carry three signal
gates; Readiness records carry gap, reviewer, and fingerprint state;
communication records carry audience, dated audit fingerprints, and export
authorization.

## Lifecycle and cross-record gates

The full lifecycle tables live in the seven authority contracts linked from
`docs/README.md`. Deterministic checks additionally enforce cross-record gates:

- archived Captures point to grounded Work, and approved Claims point to
  grounded Work or reviewed Stories; raw Captures cannot approve a Claim;
- Strategy cannot consume pending Outlook authority;
- screened JDs, Company/Scope/Engagement relationships, and decided
  opportunities retain their typed authority references;
- a reviewed Outlook Review satisfies personal-fit, market-revealed, and
  independent-external gates and records explicit user review authority;
- knowledge/practice gaps close through a verified passing Retest, while
  production-evidence gaps close only through medium/strong grounded Work;
- recruiter contact stays `not-applied` until an `application-submitted` event,
  and only one active started employment Engagement can be current.

## Reference behavior

An internal reference uses an English relation key and target UUID. A host
reference uses a Vault-relative POSIX path, optional target UUID, and optional
heading (`#Heading`) or block (`#^block-id`) anchor. Absolute paths, native
backslashes, empty targets, and traversal are invalid. `career-os check` validates
syntax, internal identities, and a matching native wikilink in the Markdown
body. `career-os check --host` additionally resolves the current
Vault path, identity, and anchor. Remounting therefore changes only the resolved
Vault root, not canonical record IDs.

Evidence, approved claims, mechanism health, formal readiness, application
state, and career outcomes are intentionally separate. No validator promotes
one state into another.

When an internal relation must be followed by an Obsidian Base, `refs` remains
the canonical identity and a same-relation `host_refs` entry acts as the Vault
adapter. Both entries agree on target ID, and the Markdown body carries the
matching native wikilink. A Base never copies fields from the target record into
the referring authority.

## Resume roots and claim support

A `communication.resume` record identifies a handwritten TeX root by
`root_name` and owns its audience, export policy, and required `uses-claim`
references. This avoids duplicating the same IDs in a sidecar manifest. Every
exported claim must resolve to an `evidence.claim` record with `status:
approved`, shareable or public visibility, an external allowed use, and at
least one required `supported-by` reference to grounded Work or a reviewed
Story. The supporting evidence may remain private; a raw Capture is never
sufficient.

An application-ready Resume additionally has one required `target-jd` and one
required `identity-profile` reference. Those records do not imply an
application state, readiness result, or career outcome.

## Schema migration

`career-os migrate plan --to 2` reads the version-paired migration definition
and emits concrete file operations with expected and result hashes. It preserves
the Markdown body and unknown schema-1 fields, selects conservative initial
states rather than inferring maturity, and marks every migrated record
`migration_review: required`. Apply and rollback verify both plan hashes and the
pinned migration-definition hash. Exact unmodified schema-1 authority README
templates are upgraded in the same reviewed plan; customized user READMEs are
reported and never overwritten.

`migration_review` is explicit: native schema-2 records use `not-applicable`, and
source-derived records remain `required` until the user confirms the semantic
mapping. Omission never means completed review.
