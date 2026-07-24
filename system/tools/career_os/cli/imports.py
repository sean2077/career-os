from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from career_os.config import resolve_paths
from career_os.imports import create_import_plan, verify_import_plan
from career_os.operations import (
    OperationPlan,
    apply_plan,
    load_plan,
    rollback_plan,
    verify_plan_state,
)
from career_os.operations.plans import write_plan

app = typer.Typer(help="Plan, apply, verify, and roll back hash-bound legacy imports.")


@app.command("plan")
def plan_import(
    source_root: Annotated[
        Path,
        typer.Option(exists=True, file_okay=False, help="Clean legacy Git repository root."),
    ],
    manifest: Annotated[
        Path,
        typer.Option(exists=True, dir_okay=False, help="Reviewed import manifest JSON."),
    ],
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
) -> None:
    paths = resolve_paths(root)
    try:
        plan = create_import_plan(paths, source_root, manifest)
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error), param_hint="--manifest") from error
    plan_path = paths.local_state_root / "migrations" / "plans" / f"import-{plan.id}.json"
    write_plan(plan, plan_path)
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "plan": str(plan_path),
                "source_version": plan.source_version,
                "target_version": plan.target_version,
                "entries": int(plan.metadata["entries"]),
                "outputs": int(plan.metadata["outputs"]),
                "already_current": int(plan.metadata["already_current"]),
                "operations": [
                    {
                        "source": operation.source_path,
                        "target": operation.path,
                        "before_sha256": operation.expected_sha256,
                        "after_sha256": operation.result_sha256,
                    }
                    for operation in plan.operations
                ],
            },
            indent=2,
        )
    )


@app.command("apply")
def apply_import(
    plan: Annotated[Path, typer.Option(exists=True, dir_okay=False, help="Import plan JSON.")],
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
) -> None:
    paths = resolve_paths(root)
    parsed = _load_current_import_plan(plan, paths.project_root)
    try:
        if parsed.applied_at is None:
            verify_import_plan(parsed)
        applied = apply_plan(plan, paths.local_state_root / "migrations")
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error), param_hint="--plan") from error
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "plan": str(plan),
                "operations": len(applied.operations),
                "applied_at": (
                    applied.applied_at.isoformat() if applied.applied_at is not None else None
                ),
            },
            indent=2,
        )
    )


@app.command("verify")
def verify_import(
    plan: Annotated[Path, typer.Option(exists=True, dir_okay=False, help="Import plan JSON.")],
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
) -> None:
    paths = resolve_paths(root)
    parsed = _load_current_import_plan(plan, paths.project_root)
    try:
        verify_import_plan(parsed)
        verify_plan_state(parsed)
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error), param_hint="--plan") from error
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "plan": str(plan),
                "operations": len(parsed.operations),
                "state": (
                    "rolled-back"
                    if parsed.rolled_back_at is not None
                    else "applied"
                    if parsed.applied_at is not None
                    else "planned"
                ),
            },
            indent=2,
        )
    )


@app.command("rollback")
def rollback_import(
    plan: Annotated[
        Path,
        typer.Option(exists=True, dir_okay=False, help="Applied import plan JSON."),
    ],
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
) -> None:
    paths = resolve_paths(root)
    _load_current_import_plan(plan, paths.project_root)
    try:
        rolled_back = rollback_plan(plan, paths.local_state_root / "migrations")
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error), param_hint="--plan") from error
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "plan": str(plan),
                "operations": len(rolled_back.operations),
                "rolled_back_at": (
                    rolled_back.rolled_back_at.isoformat()
                    if rolled_back.rolled_back_at is not None
                    else None
                ),
            },
            indent=2,
        )
    )


def _load_current_import_plan(plan_path: Path, project_root: Path) -> OperationPlan:
    try:
        parsed = load_plan(plan_path)
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error), param_hint="--plan") from error
    if parsed.action != "import":
        raise typer.BadParameter("plan action must be import", param_hint="--plan")
    planned_root = Path(parsed.roots.get("project", "")).resolve()
    if planned_root != project_root.resolve():
        raise typer.BadParameter(
            "import plan belongs to a different project root", param_hint="--plan"
        )
    return parsed
