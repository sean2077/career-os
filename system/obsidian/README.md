# Obsidian Framework Assets

The root `Career Home.md` and `职业主页.md`, plus the generic Base, lightweight dashboard, two
explanatory Canvas files, ten authority Workbench Bases, and two localized
Recent Changes Bases under `bases/`, are public, Git-tracked framework assets.
Each pair has an English and Chinese presentation over the same query. Only
filenames, view names, and column `displayName` values differ between paired
files; neither language variant becomes a Career fact authority. `career-os
init` never creates, renders, copies, or overwrites a Base.

Relationship formulas retain full Vault-relative paths as stable references but
render links with each target's basename. Dedicated views must not expose those
raw paths as user-facing columns.

The Recent Changes pair follows the same native filter shape as other Bases:
it selects only Markdown files inside the current project, sorts by
`file.mtime`, and limits the view to ten rows. It does not represent Git history
or include source code, caches, Bases, Canvases, or attachments.

The paired root homepages are the primary user entry points:

- one native Agent-first callout provides four framework links;
- each homepage expands the Recent Changes view followed by the five authority
  Workbench views in its own language and links the other homepage;
- `Authority Contracts` keeps the seven domain contracts available as a
  lower-frequency reference;
- filename-only targets and selected view fragments keep the configured data
  root and Vault mount portable;
- visible framework copy stays English, while Chinese Base filenames and view
  names remain inside wikilink targets.

The homepage uses only native Markdown, wikilinks, callouts, and core Base
embeds. It has no CSS, theme, community-plugin, `.obsidian`, or personal-data
dependency. `dashboard.md` remains a lightweight overview with the generic All
Records Base, the two explanatory Canvases, and the Authority links; it does not
duplicate the six homepage Base embeds.

The two Canvas files have distinct explanatory jobs:

- `career-map.canvas` explains the Agent-native workflow, seven authorities,
  deterministic interfaces, lifecycle separation, and safety boundaries.
- `career-guide.canvas` starts from eleven representative user outcomes: seven
  single-authority workflows and four cross-authority compositions.

All of these files are views and navigation, not career authority. Initialized
user records remain under fixed `career/`. The explanatory Canvas
layouts stay landscape-oriented and keep every edge explicitly anchored.

`career-os views build` verifies and lists all eighteen framework assets but does
not write `career/` or `.career-os/runtime/` copies. The two README previews under `docs/assets/`
remain reviewed native Obsidian Full canvas PNG exports of the explanatory
Canvas files; the Markdown homepages add no third README PNG. The Canvas files
remain canonical for those two diagrams, and the repository check validates the
existing PNG projections and README links. The only install-specific Obsidian
output is an optional QuickAdd adapter bundle under ignored
`.career-os/obsidian/quickadd/`, produced only after QuickAdd `2.12.3` is
detected. The bundle contains an Evidence inbox Capture choice and an active-JD
manual-review Macro choice backed by the tracked `quickadd/review-jd.js`
script. Career OS never installs the plugin or tracks a personal `.obsidian`
directory.
