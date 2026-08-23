# Career OS Documentation

This directory documents the public, data-free framework. User-owned records live under the fixed project-relative `career/` root; framework implementation and portable assets live under `system/`. Root [`Career Home.md`](<../Career Home.md>) and [`职业主页.md`](../职业主页.md) are tracked Workbench entry points, while `career/README.md` is a user-owned text index created once during initialization.

## Find the right page

| Task | Authoritative page |
| --- | --- |
| Check prerequisites or diagnose a machine | [Install and Verify Career OS](installation.md) |
| Create a private Career Home or manage remotes and updates | [Private Downstream Installation](private-downstream.md) |
| Attach to an existing Obsidian Vault or configure QuickAdd | [Embedded Vaults](embedded-vault.md) |
| Route an outcome across career authorities | [Outcome-First Workflows](workflows.md) |
| Understand Skill ownership or optional Skill onboarding | [Career Skills](skills.md) |
| Build, validate, or export a resume | [Resume System](resume.md) |
| Import a legacy repository | [Legacy Repository Imports](importing.md) |
| Understand ownership, topology, and stable seams | [Architecture](architecture.md) |
| Understand schemas, lifecycles, and references | [Data Model](data-model.md) |
| Develop, test, or release the framework | [CONTRIBUTING.md](../CONTRIBUTING.md) and [Tooling](tooling.md) |
| Review dependency and command ownership | [Supply Chain](supply-chain.md) and [Tool Governance](tool-governance.md) |
| Inspect historical release evidence | [Release Index](releases/README.md) |

## Typical reading paths

### First installation

1. Read [Installation](installation.md) for core requirements and readiness levels.
2. Establish the private repository and remote boundary in [Private Downstream Installation](private-downstream.md).
3. For an existing Vault, continue with [Embedded Vaults](embedded-vault.md).
4. Run the final core checks before adding or committing personal data.

### Daily use

1. Start from the requested outcome, not a Skill name.
2. Use [Outcome-First Workflows](workflows.md) only when ownership or a cross-authority handoff is unclear.
3. Open [Career Skills](skills.md) for the selected authority's operating and reviewer boundaries.
4. Read the [Data Model](data-model.md) before a schema, lifecycle, or relation decision.

### Framework maintenance

1. Read [CONTRIBUTING.md](../CONTRIBUTING.md).
2. Use [Tooling](tooling.md) for the narrowest applicable verification depth.
3. Use [Tool Governance](tool-governance.md) before adding command placement or CI behavior.
4. Use [Supply Chain](supply-chain.md) before changing dependencies, external Skills, fonts, licensing, or the SBOM.
5. Treat [release notes](releases/README.md) as historical evidence, not as the current installation guide.

## Documentation ownership contract

Keep changing facts in one place and link to them elsewhere:

| Fact or procedure | Authority |
| --- | --- |
| Product positioning and shortest safe entry paths | Root [`README.md`](../README.md) |
| Dependencies, compatibility, and readiness commands | [`installation.md`](installation.md) |
| Private remotes, update flow, and downstream safety | [`private-downstream.md`](private-downstream.md) |
| Vault layouts, attach/detach, views, and QuickAdd | [`embedded-vault.md`](embedded-vault.md) |
| Skill routing, onboarding, and reviewers | [`skills.md`](skills.md) |
| Current workflow composition rules | [`workflows.md`](workflows.md) |
| Maintainer commands and verification depth | [`tooling.md`](tooling.md) |
| Historical scope and release evidence | [`releases/`](releases/README.md) and root [`CHANGELOG.md`](../CHANGELOG.md) |

Current how-to pages should describe current behavior without accumulating old release boundaries. Release-specific migrations and compatibility decisions belong in release evidence, with a stable current requirement linked from the relevant authority page. Prefer relative links, copyable commands from the repository root, and links to machine-owned manifests or schemas instead of repeating volatile versions, hashes, byte counts, or inventory totals.

## Domain authority contracts

The seven canonical domain contracts are versioned initialization seeds. They are copied once into `career/` and never overwrite an initialized user-owned file:

- [Career Evidence](../system/seeds/authorities/10-career-evidence.md)
- [Career Strategy](../system/seeds/authorities/20-career-strategy.md)
- [Role Market](../system/seeds/authorities/30-role-market.md)
- [Opportunity Decision](../system/seeds/authorities/40-opportunity-decision.md)
- [Career Outlook](../system/seeds/authorities/50-career-outlook.md)
- [Capability Readiness](../system/seeds/authorities/60-capability-readiness.md)
- [Career Communication](../system/seeds/authorities/70-career-communication.md)
