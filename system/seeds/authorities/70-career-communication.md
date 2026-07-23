# Career Communication

This user-owned authority maintains audience copy, profile policy, resume roots,
dated communication audits, validation state, and export receipts. It projects
supported facts without owning Evidence, Positioning, JD screening, application
state, or readiness.

## Key Terms

- **Profile**: audience and identity policy for career communication.
- **Claim projection**: bounded wording derived from an approved Claim.
- **Resume Root**: maintained buildable source with an audience/export contract.
- **Communication Audit**: dated, fingerprinted review of communication roots;
  findings never grant readiness or approve a Claim.
- **Publication gate**: evidence, visibility, privacy, and attribution checks.
- **Export**: authorized artifact receipt; generation does not authorize sending.

## Authority Map

| Record | Kind | Suggested location |
| --- | --- | --- |
| Audience Profile | `communication.profile` | `profiles/` |
| Resume Root | `communication.resume` | `resumes/` |
| Communication Audit | `communication.audit` | `audits/` |
| Export receipt | `communication.export` | `exports/` |

## Lifecycle

```text
Profile: draft -> approved -> superseded
Resume: draft -> validated -> application-ready -> superseded
Audit: draft -> reviewed -> superseded
Export: planned -> generated -> released | revoked
```

Validated resumes require `uses-claim` references to approved Claims. An
application-ready Resume and application Export require a reviewed target JD.
Generated exports require explicit authorization and an artifact checksum.

## Change Rules

Keep wording proportional to evidence and contribution boundaries. Do not expose
private-sensitive material, unsupported metrics, hidden attribution, external links,
or application state. Editing or exporting locally never authorizes sending, upload,
platform mutation, or application.

## Completion Gate

Communication work is complete only when Claim support, visibility, audience,
privacy, target references, audit fingerprints, artifact policy, and export
validation pass. A reviewed Audit does not imply formal readiness.
