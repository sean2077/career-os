from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal, cast

import typer
from pydantic import ValidationError

from career_os.config import resolve_paths
from career_os.resume import (
    build_resume,
    export_resume,
    fetch_fonts,
    list_resumes,
    new_resume,
    prepare_resume_fonts,
    resume_doctor,
    write_work_experience,
)

app = typer.Typer(help="Create, build, inspect, and safely export direct XeLaTeX resumes.")
fonts_app = typer.Typer(help="Manage local resume fonts.")
app.add_typer(fonts_app, name="fonts")


@app.command("new")
def new_command(
    name: Annotated[str, typer.Argument(help="User-owned resume directory name.")],
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
) -> None:
    """Create one handwritten TeX resume root in Career Communication."""
    try:
        source = new_resume(resolve_paths(root), name=name)
        typer.echo(
            json.dumps(
                {"ok": True, "source": str(source)},
                indent=2,
                ensure_ascii=False,
            )
        )
    except (OSError, ValueError, ValidationError) as error:
        _fail(error)


@app.command("doctor")
def doctor_command(
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    """Check the local TeX toolchain, default fonts, and resume assets."""
    try:
        checks = resume_doctor(resolve_paths(root))
    except (OSError, ValueError, ValidationError) as error:
        _fail(error)
    ok = not any(item.status == "fail" for item in checks)
    if json_output:
        typer.echo(json.dumps({"ok": ok, "checks": [item.as_dict() for item in checks]}, indent=2))
    else:
        for check in checks:
            typer.echo(f"{check.status.upper():9} {check.id}: {check.detail}")
        typer.echo(f"Career OS resume doctor: {'PASS' if ok else 'FAIL'}")
    if not ok:
        raise typer.Exit(1)


@app.command("list")
def list_command(
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    """Discover handwritten Career OS TeX roots recursively."""
    try:
        items = list_resumes(resolve_paths(root))
    except (OSError, ValueError, ValidationError) as error:
        _fail(error)
    if json_output:
        typer.echo(
            json.dumps(
                {"ok": True, "resumes": [item.as_dict() for item in items]},
                indent=2,
                ensure_ascii=False,
            )
        )
        return
    for item in items:
        profiles = ", ".join(item.profiles)
        typer.echo(f"{item.name}: {item.source} [{profiles}]")


@app.command("build")
def build_command(
    resume: Annotated[str, typer.Option(help="Discovered resume name.")],
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
) -> None:
    """Compile an internal PDF with latexmk and XeLaTeX."""
    try:
        result = build_resume(resolve_paths(root), resume)
        typer.echo(json.dumps({"ok": True, **result.as_dict()}, indent=2, ensure_ascii=False))
    except (OSError, ValueError, ValidationError) as error:
        _fail(error)


@app.command("export")
def export_command(
    resume: Annotated[str, typer.Option(help="Discovered resume name.")],
    profile: Annotated[str, typer.Option(help="Fixed export profile: preview or application.")],
    output: Annotated[Path, typer.Option(help="New shareable PDF destination.")],
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
    confirm_application: Annotated[
        bool,
        typer.Option(
            "--confirm-application",
            help="Confirm this explicit application-grade export request.",
        ),
    ] = False,
    recipient: Annotated[
        str | None,
        typer.Option(help="Optional recipient printed into the export context."),
    ] = None,
    purpose: Annotated[
        str | None,
        typer.Option(help="Optional purpose printed into the export context."),
    ] = None,
    watermark: Annotated[
        str | None,
        typer.Option(help="Override the fixed profile's default watermark."),
    ] = None,
) -> None:
    """Build, validate, sanitize, and write a new shareable PDF."""
    if profile not in {"preview", "application"}:
        raise typer.BadParameter("profile must be preview or application", param_hint="--profile")
    selected = cast(Literal["preview", "application"], profile)
    try:
        result = export_resume(
            resolve_paths(root),
            resume=resume,
            profile=selected,
            output=output,
            confirm_application=confirm_application,
            recipient=recipient,
            purpose=purpose,
            watermark=watermark,
        )
        typer.echo(json.dumps({"ok": True, **result.as_dict()}, indent=2, ensure_ascii=False))
    except (OSError, ValueError, ValidationError) as error:
        _fail(error)


@app.command("work-experience")
def work_experience_command(
    input_path: Annotated[
        Path | None,
        typer.Option("--input", help="Existing internal resume PDF."),
    ] = None,
    resume: Annotated[
        str | None,
        typer.Option(help="Discovered resume to build internally before extraction."),
    ] = None,
    output: Annotated[
        Path,
        typer.Option(help="Ignored temporary Markdown path under build/ (not build/share)."),
    ] = Path("build/boss-work-experience.md"),
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
) -> None:
    """Extract only 工作经历 into an ignored temporary Markdown copy aid."""
    if (input_path is None) == (resume is None):
        raise typer.BadParameter("provide exactly one of --input or --resume")
    try:
        paths = resolve_paths(root)
        source = input_path
        if resume is not None:
            source = Path(build_resume(paths, resume).pdf)
        assert source is not None
        destination = write_work_experience(
            paths,
            input_path=source,
            output_path=output,
        )
        typer.echo(
            json.dumps(
                {"ok": True, "input": str(source.resolve()), "output": str(destination)},
                indent=2,
                ensure_ascii=False,
            )
        )
    except (OSError, ValueError, ValidationError) as error:
        _fail(error)


@fonts_app.command("fetch")
def fonts_fetch_command(
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
) -> None:
    """Fetch the pinned Career OS resume font bundle and verify every hash."""
    try:
        statuses = fetch_fonts(resolve_paths(root))
        typer.echo(
            json.dumps(
                {"ok": True, "fonts": [item.as_dict() for item in statuses]},
                indent=2,
                ensure_ascii=False,
            )
        )
    except (OSError, ValueError, ValidationError) as error:
        _fail(error)


@fonts_app.command("verify")
def fonts_verify_command(
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
) -> None:
    """Verify configured fonts and refresh the generated TeX projection."""
    try:
        generated, statuses = prepare_resume_fonts(resolve_paths(root))
        typer.echo(
            json.dumps(
                {
                    "ok": True,
                    "generated": str(generated),
                    "fonts": [item.as_dict() for item in statuses],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    except (OSError, ValueError, ValidationError) as error:
        _fail(error)


@fonts_app.command("prepare", hidden=True)
def fonts_prepare_command(
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
) -> None:
    """Internal editor hook for refreshing the generated TeX projection."""
    try:
        generated, _statuses = prepare_resume_fonts(resolve_paths(root))
        typer.echo(str(generated))
    except (OSError, ValueError, ValidationError) as error:
        _fail(error)


def _fail(error: Exception) -> None:
    typer.echo(json.dumps({"ok": False, "error": str(error)}, indent=2, ensure_ascii=False))
    raise typer.Exit(1) from error
