from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, cast

import typer

from career_os.config import discover_project_root
from career_os.reviewer_contracts import ReviewerValidation, validate_reviewer
from career_os.skill_onboarding import (
    Audience,
    InstallScope,
    build_skill_onboarding_report,
    configure_onboarding,
)
from career_os.skills import verify_skills

app = typer.Typer(
    help="Inspect optional Skill onboarding, verify project Skills, and validate reviewers."
)


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


@app.command("status")
def status_command(
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
    audience: Annotated[
        str,
        typer.Option(help="Recommendation audience: user or contributor."),
    ] = "user",
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    """Report optional Skill placement without installing or changing anything."""

    if audience not in {"user", "contributor"}:
        raise typer.BadParameter(
            "audience must be user or contributor", param_hint="--audience"
        )
    try:
        project_root = discover_project_root(root)
        report = build_skill_onboarding_report(
            project_root,
            audience=cast(Audience, audience),
        )
    except (OSError, ValueError) as error:
        typer.echo(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        raise typer.Exit(2) from error

    if json_output:
        typer.echo(json.dumps({"ok": True, **report}, ensure_ascii=False, indent=2))
        return
    groups = cast(list[dict[str, object]], report["groups"])
    for group in groups:
        typer.echo(
            f"{str(group['status']).upper():9} {group['id']}: "
            f"{'choice required' if group['requires_user_choice'] else 'resolved'}"
        )
        for detail in cast(list[str], group["attention"]):
            typer.echo(f"ATTENTION {detail}")
    typer.echo(
        "Career OS optional Skill onboarding: "
        + ("CHOICE REQUIRED" if report["requires_user_choice"] else "RESOLVED")
    )


@app.command("configure")
def configure_command(
    group: Annotated[
        str,
        typer.Option("--group", help="Recommendation group to configure."),
    ],
    scope: Annotated[
        str | None,
        typer.Option("--scope", help="Install scope: project, global, or skip."),
    ] = None,
    agent: Annotated[
        list[str] | None,
        typer.Option(
            "--agent",
            help="Target Agent Host; repeat for codex and claude-code.",
        ),
    ] = None,
    reset: Annotated[
        bool,
        typer.Option("--reset", help="Forget this group's prior choice."),
    ] = False,
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
) -> None:
    """Record one verified local onboarding choice; never install a Skill."""

    if scope is not None and scope not in {"project", "global", "skip"}:
        raise typer.BadParameter(
            "scope must be project, global, or skip", param_hint="--scope"
        )
    try:
        project_root = discover_project_root(root)
        result = configure_onboarding(
            project_root,
            group_id=group,
            scope=cast(InstallScope | None, scope),
            agents=agent or [],
            reset=reset,
        )
    except (OSError, ValueError) as error:
        typer.echo(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        raise typer.Exit(2) from error
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


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
