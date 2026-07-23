# Resume System

Career OS keeps the interface small: people write TeX, and the system owns one
fixed `career-os` class plus safe build/export tooling.

- `system/resume/` owns the fixed legacy-calibrated class, style, compiler
  sandbox, default font bundle, and synthetic fixtures.
- `career/70-career-communication/resumes/` owns personal TeX roots,
  `identity.tex`, and an optional avatar.
- No per-resume JSON manifest or template selector is used. Git already owns
  source versions; export receipts compute input and PDF hashes automatically.

## Setup

```text
uv run career-os resume fonts fetch
uv run career-os resume doctor --json
uv run career-os resume new my-resume
```

The default Source Han Serif SC and Noto Sans CJK SC files are verified against
`system/resume/fonts.json` and installed under ignored `.career-os/fonts/`.
Font binaries never enter Git.

### Personal fonts

Put owner-supplied font files anywhere below ignored `.career-os/fonts/`, then
set their filenames before `\documentclass{career-os}` in the handwritten root:

```tex
\newcommand{\CareerOSCJKBodyRegularFont}{OwnerSong-Regular.otf}
\newcommand{\CareerOSCJKBodyBoldFont}{OwnerHei-Regular.otf}
\newcommand{\CareerOSCJKBodyItalicFont}{OwnerKai-Regular.otf}
\newcommand{\CareerOSCJKBodyBoldItalicFont}{OwnerHei-Regular.otf}
\documentclass{career-os}
```

The CLI and `system/resume/latexmkrc` search `.career-os/fonts/` recursively.
The remaining overridable family macros are declared together at the top of
`system/resume/career-os.cls`. A missing named font fails during XeLaTeX
compilation; there is no profile descriptor or silent substitution layer.

### VS Code

The project recommends `james-yu.latex-workshop`. Its default recipe loads
`system/resume/latexmkrc`, builds with XeLaTeX on save, and writes ignored
editor previews under `build/vscode/`. Editor PDFs remain internal; only
`career-os resume export` may create a shareable PDF.

## Multiple handwritten roots

`resume list` recursively finds `.tex` files containing
`\documentclass{career-os}`. Each root uses the adjacent `identity.tex`.

- `general.tex` is named `general`.
- `agent-platform.tex` is named `agent-platform`.
- `my-resume/resume.tex` is named `my-resume`.
- Derived names must be unique.

```text
uv run career-os resume list --json
uv run career-os resume build --resume general
uv run career-os resume build --resume agent-platform
```

`resume build` copies only the root TeX, adjacent identity, and the optional
application avatar into a unique ignored directory. It invokes `latexmk` with
XeLaTeX, shell escape disabled, the fixed system class path, and the local font
search path. The resulting PDF is internal and must not be shared.

The root is ordinary handwritten LaTeX using `\section`, `\jobsection`,
`\projectsection`, `\edusection`, `\skillitem`, and `\resumebullet`.
`\CareerClaim{uuid}{text}` and `\CareerClaims{uuid1,uuid2}{text}` are
render-transparent evidence bindings.

## Fixed output profiles

The two supported PDF profiles are fixed in the tool:

```text
uv run career-os resume export --resume general --profile preview --output <new-preview.pdf>
uv run career-os resume export --resume general --profile application --output <new-application.pdf> --confirm-application
```

Use different output paths to keep any number of generated PDF versions.
`--recipient`, `--purpose`, and `--watermark` add one invocation's export
context. Destinations are published atomically and never overwritten.

Preview includes the name and reviewed public links but excludes email, phone,
mailto links, and the avatar. Application includes the approved full identity
and an optional PNG or JPEG named by `\ResumeAvatarAsset` in `identity.tex`.
The final exporter removes PDF links and unsafe metadata, audits the sanitized
artifact, and writes an ignored receipt containing computed source, identity,
avatar, and PDF hashes.

The matching `communication.resume` record remains the policy authority. Its
required `uses-claim`, `target-jd`, and `identity-profile` references replace
the duplicated IDs formerly stored beside TeX. Application export additionally
requires an application-ready record, `--confirm-application`, a reviewed
target JD with unchanged source body, an approved application identity, and
approved evidence-backed claims. Every application experience bullet must bind
at least one claim.

Creating a PDF never authorizes sending, uploading, applying, messaging, or
changing an external account.

## Temporary work-experience projection

```text
uv run career-os resume work-experience --resume general --output build/boss-work-experience.md
uv run career-os resume work-experience --input <internal.pdf> --output build/boss-work-experience.md
```

This extracts only `工作经历`, strips link targets and formatting, rejects
identity/footer leakage, and writes ignored scratch Markdown. It is neither a
resume source nor a shareable export.

## Fixtures and ownership

Synthetic English, Simplified Chinese, and bilingual TeX roots under
`system/resume/fixtures/` exercise validation and compilation. System updates
may change the fixed class and fixtures but must never rewrite personal TeX,
identity, avatar, or local font files.
