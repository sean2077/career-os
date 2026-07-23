# Documentation Images

The two PNG files in this directory are reviewed documentation projections of
the canonical Obsidian Canvas sources:

| PNG projection | Canonical source |
| --- | --- |
| `career-map.png` | `system/obsidian/career-map.canvas` |
| `career-guide.png` | `system/obsidian/career-guide.canvas` |

Export them with Obsidian 1.12.7 or newer using the native **Export as image**
flow and these settings:

- Frame: **Full canvas**
- Show logo: **Off**
- Privacy mode: **Off** because these framework Canvases contain no user data
- Format: PNG

The Obsidian CLI may open each Canvas and invoke the active Canvas's native
exporter through `obsidian eval`. This is maintainer automation around the
built-in exporter, not a Career OS rendering implementation. Do not add a
parallel SVG, HTML, or raster renderer to product tooling.

After an intentional Canvas change, inspect both PNGs at full size, replace the
tracked projections, and run `uv run career-os check`. The check validates the
PNG format, minimum full-canvas dimensions, and README links; human review owns
visual fidelity because Obsidian remains the renderer.
