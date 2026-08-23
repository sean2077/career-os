# Security and Privacy

Career OS is local-first, but local ownership does not make every checkout or export safe by default. Personal career records, identity, attachments, resume sources, fonts, active Obsidian state, and generated output belong only in an owner-controlled private environment.

## Report a vulnerability privately

Do not open a public issue containing exploit details, personal data, access tokens, private repository URLs, real resumes, or career records. Contact the maintainer through a private channel and include only the minimum information needed to reproduce the problem:

- the release tag or exact commit;
- affected command, file boundary, or workflow;
- expected and observed behavior;
- a synthetic reproduction or redacted steps;
- impact and whether data may have crossed a public, export, or external-action boundary; and
- relevant logs with names, paths, URLs, tokens, and record contents removed.

Do not test a suspected vulnerability against another person's repository, Vault, account, or external service.

## Data and repository boundaries

The public framework must contain only framework assets, synthetic fixtures, and release evidence. Real data must not enter a public fork or public Git history. For a personal installation, use the guarded remote and update model in [Private Downstream Installation](docs/private-downstream.md).

Career OS stores no account credentials and does not require credentials for core filesystem workflows. Optional external tools and signed-in services keep their own credentials and policies; do not copy them into records, prompts, plans, receipts, logs, or bug reports.

## Action and export boundaries

The CLI does not send applications or messages, upload files, modify accounts, accept or reject offers, or resign. Drafting, tracking, validation, and local artifact generation do not authorize any external action.

Public and application-grade resume exports require an explicit command and pass deterministic identity, link, attachment, metadata, and evidence gates before publication. A successful check proves the implemented mechanism ran; it does not prove that the underlying career claim, recipient choice, or external action is correct.

Before `v1.0`, use the interface and security boundary documented by the exact release being operated. Historical verification evidence is indexed under [`docs/releases/`](docs/releases/README.md).
