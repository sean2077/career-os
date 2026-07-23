from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from career_os.config import discover_project_root
from career_os.reviewer_contracts import ReviewerValidation, validate_reviewer
from career_os.skills import verify_skills

app = typer.Typer(help="Verify Agent Skills and validate read-only reviewer outputs.")


def _emit_reviewer_result(result: ReviewerValidation) -> None:
    typer.echo(json.dumps(result.as_dict(), ensure_ascii=False, sort_keys=True))


@app.command("verify")
def verify_command(
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
    selection_report: Annotated[
        Path | None,
        typer.Option(
            "--selection-report",
            exists=True,
            dir_okay=False,
            help="Independent blind-selection report JSON to score against the hidden oracle.",
        ),
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    project_root = discover_project_root(root)
    checks = verify_skills(project_root, selection_report)
    ok = not any(item.status == "fail" for item in checks)
    if json_output:
        typer.echo(json.dumps({"ok": ok, "checks": [item.as_dict() for item in checks]}, indent=2))
    else:
        for item in checks:
            typer.echo(f"{item.status.upper():9} {item.id}: {item.detail}")
        typer.echo(f"Career OS Skill verification: {'PASS' if ok else 'FAIL'}")
    if not ok:
        raise typer.Exit(1)


@app.command("validate-reviewer")
def validate_reviewer_command(
    contract: Annotated[
        str,
        typer.Argument(
            metavar="CONTRACT",
            help="Reviewer contract: evidence or probe.",
        ),
    ],
    path: Annotated[
        str | None,
        typer.Argument(
            metavar="[PATH]",
            help="JSON file to read; omit or use - for stdin.",
        ),
    ] = None,
) -> None:
    """Validate one reviewer JSON response without echoing its packet."""

    if contract not in {"evidence", "probe"}:
        result = validate_reviewer(contract, {})
        _emit_reviewer_result(result)
        raise typer.Exit(2)

    try:
        raw = (
            sys.stdin.read()
            if path is None or path == "-"
            else Path(path).read_text(encoding="utf-8")
        )
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        result = ReviewerValidation(
            valid=False,
            blocks_readiness=True,
            errors=(
                f"invalid JSON at line {error.lineno} column {error.colno}",
            ),
        )
        _emit_reviewer_result(result)
        raise typer.Exit(2) from None
    except (OSError, UnicodeError) as error:
        result = ReviewerValidation(
            valid=False,
            blocks_readiness=True,
            errors=(f"unable to read reviewer output: {error}",),
        )
        _emit_reviewer_result(result)
        raise typer.Exit(2) from None

    result = validate_reviewer(contract, payload)
    _emit_reviewer_result(result)
    if not result.valid:
        raise typer.Exit(2)
