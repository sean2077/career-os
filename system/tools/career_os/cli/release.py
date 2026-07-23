from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Annotated

import typer

from career_os.config import load_project_config, resolve_paths
from career_os.public_privacy import (
    PublicPrivacyError,
    audit_public_repository,
)
from career_os.release_notes import (
    ReleaseNotesError,
    extract_release_notes,
    write_release_notes,
)

app = typer.Typer(help="Prepare fail-closed repository release metadata.")


@app.command("privacy")
def privacy_command(
    root: Annotated[Path, typer.Option(help="Path inside the public Career OS project.")] = Path(
        "."
    ),
    ref: Annotated[str, typer.Option(help="Complete Git ref to audit.")] = "HEAD",
    history: Annotated[
        bool,
        typer.Option("--history", help="Audit every Git blob reachable from the selected ref."),
    ] = False,
    private_root: Annotated[
        Path | None,
        typer.Option(
            "--private-root",
            help="Optional private Career Home root for exact redacted cross-comparison.",
        ),
    ] = None,
) -> None:
    """Fail closed on unreviewed fixtures, obvious secrets, or private-value matches."""

    try:
        paths = resolve_paths(root)
        report = audit_public_repository(
            paths.project_root,
            ref=ref,
            include_history=history,
            private_root=private_root,
        )
    except (FileNotFoundError, OSError, PublicPrivacyError, ValueError) as error:
        typer.echo(json.dumps({"ok": False, "error": str(error)}, indent=2))
        raise typer.Exit(1) from error

    typer.echo(json.dumps(report.as_dict(), indent=2))
    if not report.ok:
        raise typer.Exit(1)


@app.command("notes")
def notes_command(
    tag: Annotated[str, typer.Option("--tag", help="Exact complete Git tag.")],
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Optional destination notes file; omit for stdout."),
    ] = None,
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
    changelog: Annotated[
        Path,
        typer.Option(help="Project-relative or absolute committed changelog path."),
    ] = Path("CHANGELOG.md"),
) -> None:
    """Extract the one changelog section matching the configured release tag."""

    paths = resolve_paths(root)
    config = load_project_config(paths.project_root)
    expected_tag = f"v{config.system_version}"
    if tag != expected_tag:
        raise typer.BadParameter(
            f"tag {tag!r} does not match configured release tag {expected_tag!r}"
        )

    changelog_path = _resolve_project_path(paths.project_root, changelog)
    try:
        if output is None:
            notes = extract_release_notes(
                changelog_path.read_text(encoding="utf-8"),
                tag,
            )
        else:
            output_path = _resolve_project_path(paths.project_root, output)
            write_release_notes(changelog_path, tag, output_path)
    except ReleaseNotesError as error:
        raise typer.BadParameter(str(error)) from error

    if output is None:
        typer.echo(notes, nl=False)
        return

    typer.echo(
        json.dumps(
            {
                "ok": True,
                "tag": tag,
                "changelog": str(changelog_path),
                "output": str(output_path),
                "sha256": sha256(output_path.read_bytes()).hexdigest(),
            },
            indent=2,
        )
    )


def _resolve_project_path(project_root: Path, path: Path) -> Path:
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()
