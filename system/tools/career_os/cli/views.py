from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from career_os.adapters.obsidian import build_views
from career_os.config import resolve_paths

app = typer.Typer(help="Verify Git-tracked Obsidian framework views.")


@app.command("build")
def build_command(
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
) -> None:
    paths = resolve_paths(root)
    try:
        assets = build_views(paths)
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "asset_root": str(paths.project_root / "system/obsidian"),
                "homepage": str(paths.project_root / "Home.md"),
                "homepages": [
                    str(paths.project_root / "Home.md"),
                    str(paths.project_root / "主页.md"),
                ],
                "assets": [str(path) for path in assets],
                "generated": [],
            },
            indent=2,
        )
    )
