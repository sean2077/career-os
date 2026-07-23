# Resume Assets

This system-owned directory contains:

- `career-os.cls`, `career-os-style.sty`, and `linespacing_fix.sty`: the single legacy-calibrated XeLaTeX visual implementation, profile-aware identity, watermark, avatar, and footer style;
- `latexmkrc`: the shared LaTeX Workshop/XeLaTeX configuration for ignored editor previews;
- `templates/single-column.tex`: the direct user-source template;
- `fixtures/`: synthetic English, Simplified Chinese, and bilingual compile/export fixtures;
- `fonts.json`: exact Source Han Serif SC 2.003 and Noto Sans CJK SC 2.004 roles, URLs, sizes, and SHA-256 values; and
- `secret-patterns.json`: conservative export leak patterns.

`career-os resume new` copies direct source into the user-owned Career
Communication authority. Font binaries, builds, sanitized exports used for QA,
and receipts remain in ignored local state.

`career-os resume list` discovers handwritten roots from
`\documentclass{career-os}`. The source stem, or the parent directory for a
file named `resume.tex`, is the CLI name. The adjacent `identity.tex` and an
optional local avatar complete the fixed source convention; no resume manifest
or template selector is required.

Personal roots may override the class font filename macros before
`\documentclass`. Owner-provided binaries stay only in ignored
`.career-os/fonts/`, which the CLI and `latexmkrc` search recursively.
