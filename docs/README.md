# Career OS Framework Documentation

This directory documents the Career OS framework; it contains no personal
career records. User-owned data lives in the configured data root (`career/` by
default), while implementation and portable runtime assets live under
`system/`. Root [`Home.md`](../Home.md) and [`主页.md`](../主页.md) are the
Git-tracked English and Chinese Workbench entry points. `career-os init` creates the data-root
`README.md` once as a user-owned text index and never overwrites that note or
manages either root homepage.

## Use Career OS

- [Installation requirements](installation.md): core, Obsidian CLI, XeLaTeX, Poppler, fonts, and verified platform boundaries.
- [Embedded Vaults](embedded-vault.md): standalone, nested repository, and submodule modes.
- [Private downstream installation](private-downstream.md): the supported split topology, optional fetch-only public upstream, exact-tag updates, and Agent safety rules.
- [Skills](skills.md): project-owned and bundled Agent Skills.
- [Resume system](resume.md): direct XeLaTeX sources and privacy-safe exports.
- [Legacy repository imports](importing.md): exhaustive classification, hash-bound copy/transform plans, provenance, and rollback.

## Understand the Framework

- [Architecture](architecture.md): layer ownership, stable interfaces, and authority model.
- [Data model](data-model.md): records, references, visibility, and multilingual content.

The seven canonical domain contracts are versioned as initialization seeds and
copied once into a user-owned data root. System updates may change the seeds but
never overwrite an initialized README.

| Authority | Framework contract |
| --- | --- |
| Career Evidence | [`system/seeds/authorities/10-career-evidence.md`](../system/seeds/authorities/10-career-evidence.md) |
| Career Strategy | [`system/seeds/authorities/20-career-strategy.md`](../system/seeds/authorities/20-career-strategy.md) |
| Role Market | [`system/seeds/authorities/30-role-market.md`](../system/seeds/authorities/30-role-market.md) |
| Opportunity Decision | [`system/seeds/authorities/40-opportunity-decision.md`](../system/seeds/authorities/40-opportunity-decision.md) |
| Career Outlook | [`system/seeds/authorities/50-career-outlook.md`](../system/seeds/authorities/50-career-outlook.md) |
| Capability Readiness | [`system/seeds/authorities/60-capability-readiness.md`](../system/seeds/authorities/60-capability-readiness.md) |
| Career Communication | [`system/seeds/authorities/70-career-communication.md`](../system/seeds/authorities/70-career-communication.md) |

## Maintain Career OS

- [Tooling](tooling.md): development commands, command contracts, and verification depth.
- [Tool governance](tool-governance.md): authoritative command placement and job contracts.
- [Semantic migration audit](semantic-migration.md): completed mappings, deliberate compression, and independent acceptance gaps.
- [Supply chain](supply-chain.md): dependency locks, SBOM, licenses, and attribution.

## Release Evidence

- [Releases](releases/README.md): publication contract, release notes, and verification evidence.
