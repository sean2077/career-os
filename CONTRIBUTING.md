# Contributing to Career OS

Career OS separates user-owned career data from a public, data-free framework. Contributions must preserve that boundary while keeping commands, schemas, documentation, and release evidence aligned.

## Before editing

- Read [`AGENTS.md`](AGENTS.md) for repository-wide ownership, safety, and Agent rules.
- Use the [documentation map](docs/README.md) to find the authority for the behavior being changed.
- Keep real career records, identity data, personal resume sources, attachments, local fonts, `.obsidian/`, `.career-os/`, and generated output out of the public tree and history.
- Do not hand-edit generated schemas or Host projections. Change their source and use the documented generator or relinker.

## Development setup

Career OS requires Git, `uv`, and Python 3.12 or newer. Install the locked runtime and development dependencies from the repository root:

```text
uv sync --locked --all-groups
```

Optional Obsidian, XeLaTeX, Poppler, fonts, and auxiliary Skills have separate readiness gates. Install only the capability needed for the change; see [Installation](docs/installation.md).

## Make a focused change

1. Identify the canonical owner for the behavior, schema, command, or document.
2. Read the narrowest relevant implementation, tests, and authority page.
3. Change generated artifacts only through their source and documented command.
4. Extend tests only for a distinct uncovered behavior or high-risk boundary; prefer the narrowest stable seam.
5. Update every affected contract, example, and navigation link in the same change, but do not duplicate low-frequency procedures into `AGENTS.md` or the root README.
6. Review the diff for private data, unrelated formatting churn, stale examples, and generated files that should remain local.

## Documentation changes

Use one authoritative page for each changing fact. The root README should stay a concise product and navigation entry point. Installation, downstream, Vault, Skill, resume, tooling, and release details belong to their pages listed in the [documentation ownership contract](docs/README.md#documentation-ownership-contract).

Current how-to pages describe current behavior. Historical version boundaries, release-specific migration evidence, and candidate verification results belong under `docs/releases/` or in `CHANGELOG.md`. Prefer relative links and commands that can be copied from the repository root with `uv run`.

For a documentation-only change, at minimum verify local links, fenced code blocks, command consistency, and the affected facts against source manifests, schemas, or CLI help. Do not add an automated test solely to restate prose when an existing contract or deterministic check already owns the behavior.

## Verification

Start with the narrowest checks that can expose a mistake, then run the complete project gates required by the affected boundary. The common sequence is:

```text
uv run career-os check --fast
uv run pytest <focused-test-path-or-expression>
uv run ruff check .
uv run mypy system/tools/career_os
uv run career-os check
```

Use `uv run pytest` when the change is broad or no focused target is sufficient. Host, resume, migration, downstream, privacy, package, harness, and release changes require the additional commands documented in [`docs/tooling.md`](docs/tooling.md); do not reconstruct those procedures from memory.

## Commit and review checklist

- The change has one clear purpose and no private or generated local data.
- Public examples and fixtures are synthetic.
- Ownership, authorization, privacy, and lifecycle boundaries remain explicit.
- Configuration changes update serialization, generated schema, tests, and docs together.
- User-owned `career/` content is never overwritten, ignored, or reverse-copied.
- The narrow and full applicable checks pass, with any documented `attention` result explained rather than hidden.
- The final diff contains no unrelated rewrites or duplicated authority text.
