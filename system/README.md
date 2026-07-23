# System Layer

`system/` contains every Career OS-owned executable module and portable runtime asset.

- `tools/career_os/` implements the single `career-os` CLI.
- `schemas/` owns public data and plan schemas.
- `obsidian/` owns portable Obsidian assets; host-specific generated state goes to `runtime/`.
- `resume/` owns XeLaTeX templates, styles, and font metadata.
- `seeds/` owns blank initialization material, never user records.
- `migrations/` owns explicit schema migrations.
- `tests/` exercises public CLI and file interfaces.

Do not add executable project commands elsewhere. `.agents/tools/` is the only exception and is owned by the dual-host Agent scaffold.
