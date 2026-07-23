# Obsidian Framework Assets

The root `Home.md` and `主页.md`, plus the generic Base, lightweight dashboard, two
explanatory Canvas files, and ten Workbench Bases under `bases/`, are public,
Git-tracked framework assets. Each Workbench has an English and Chinese
presentation over the same schema-2 `kind` queries. Only filenames, view names,
and column `displayName` values differ between the paired files; neither
language variant becomes a Career fact authority. `career-os init` never
creates, renders, copies, or overwrites a Base.

Relationship formulas retain full Vault-relative paths as stable references but
render links with each target's basename. Dedicated views must not expose those
raw paths as user-facing columns.

The paired root homepages are the primary user entry points:

- one native Agent-first callout provides four framework links;
- each homepage expands the five Workbench views in its own language and links
  the other homepage;
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
duplicate the five dedicated Workbench embeds.

The two Canvas files have distinct explanatory jobs:

- `career-map.canvas` explains the Agent-native workflow, seven authorities,
  deterministic interfaces, lifecycle separation, and safety boundaries.
- `career-guide.canvas` starts from eleven representative user outcomes: seven
  single-authority workflows and four cross-authority compositions.

All of these files are views and navigation, not career authority. Initialized
user records remain under the configured data root. The explanatory Canvas
layouts stay landscape-oriented and keep every edge explicitly anchored.

`career-os views build` verifies and lists all sixteen framework assets but does
not write data-root or `runtime/` copies. The two README previews under `docs/assets/`
remain reviewed native Obsidian Full canvas PNG exports of the explanatory
Canvas files; the Markdown homepages add no third README PNG. The Canvas files
remain canonical for those two diagrams, and the repository check validates the
existing PNG projections and README links. The only install-specific Obsidian
output is an optional QuickAdd import file under ignored
`.career-os/obsidian/quickadd/`, produced only after QuickAdd `2.12.3` is
detected. Career OS never installs the plugin or tracks a personal `.obsidian`
directory.
