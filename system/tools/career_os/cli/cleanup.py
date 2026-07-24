from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from career_os.cleanup import CleanupError, CleanupReport, cleanup_project


def cleanup_command(
    root: Annotated[
        Path,
        typer.Option(help="Path inside the Career OS project."),
    ] = Path("."),
    apply: Annotated[
        bool,
        typer.Option(
            "--apply",
            help="Delete candidates from the known reproducible roots.",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Report or remove known reproducible ignored project state."""
    try:
        report = cleanup_project(root, apply=apply)
    except CleanupError as error:
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "ok": False,
                        "mode": "apply" if apply else "dry-run",
                        "root": str(root.resolve()),
                        "summary": {},
                        "categories": [],
                        "candidates": [],
                        "preserved": [],
                        "deleted": [],
                        "deleted_bytes": 0,
                        "errors": [str(error)],
                    },
                    indent=2,
                )
            )
        else:
            typer.echo(f"cleanup failed: {error}", err=True)
        raise typer.Exit(1) from error

    if json_output:
        typer.echo(json.dumps(report.as_dict(), indent=2))
    else:
        _emit_human(report)
    if not report.ok:
        raise typer.Exit(1)


def _emit_human(report: CleanupReport) -> None:
    payload = report.as_dict()
    typer.echo(f"Career OS cleanup ({report.mode})")
    typer.echo(f"Root: {report.root}")
    for category in payload["categories"]:
        typer.echo(
            f"- {category['action']:7} {category['category']}: "
            f"{category['files']} files, {category['bytes']} bytes "
            f"({category['reason']})"
        )
    if report.mode == "dry-run":
        delete = payload["summary"]["delete"]
        typer.echo(
            f"Would delete {delete['files']} files ({delete['bytes']} bytes). "
            "Run with --apply to execute."
        )
    else:
        typer.echo(
            f"Deleted {len(report.deleted)} files ({report.deleted_bytes} bytes)."
        )
    for error in report.errors:
        typer.echo(f"ERROR: {error}", err=True)
