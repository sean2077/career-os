from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from career_os.config import resolve_paths
from career_os.migrations import create_record_migration_plan, verify_migration_definition
from career_os.operations import (
    OperationPlan,
    apply_plan,
    load_plan,
    rollback_plan,
    verify_plan_state,
)
from career_os.operations.plans import write_plan

app = typer.Typer(help="Plan, apply, verify, and roll back user-data schema migrations.")


@app.command("plan")
def plan_migration(
    target: Annotated[int, typer.Option("--to", min=1, help="Target record schema version.")],
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
) -> None:
    paths = resolve_paths(root)
    try:
        plan = create_record_migration_plan(paths, target)
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error), param_hint="--to") from error
    plan_path = (
        paths.local_state_root / "migrations" / "plans" / f"migration-{plan.id}.json"
    )
    write_plan(plan, plan_path)
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "plan": str(plan_path),
                "source_version": plan.source_version,
                "target_version": plan.target_version,
                "operations": len(plan.operations),
                "metadata": plan.metadata,
            },
            indent=2,
        )
    )


@app.command("apply")
def apply_migration(
    plan: Annotated[Path, typer.Option(exists=True, dir_okay=False, help="Migration plan JSON.")],
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
) -> None:
    paths = resolve_paths(root)
    parsed = _load_current_migration_plan(plan, paths.project_root)
    verify_migration_definition(parsed)
    applied = apply_plan(plan, paths.local_state_root / "migrations")
    if applied.applied_at is None:
        raise RuntimeError("applied plan is missing its completion timestamp")
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "plan": str(plan),
                "operations": len(applied.operations),
                "applied_at": applied.applied_at.isoformat(),
            },
            indent=2,
        )
    )


@app.command("rollback")
def rollback_migration(
    plan: Annotated[
        Path,
        typer.Option(exists=True, dir_okay=False, help="Applied migration plan JSON."),
    ],
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
) -> None:
    paths = resolve_paths(root)
    parsed = _load_current_migration_plan(plan, paths.project_root)
    verify_migration_definition(parsed)
    rolled_back = rollback_plan(plan, paths.local_state_root / "migrations")
    if rolled_back.rolled_back_at is None:
        raise RuntimeError("rolled-back plan is missing its completion timestamp")
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "plan": str(plan),
                "operations": len(rolled_back.operations),
                "rolled_back_at": rolled_back.rolled_back_at.isoformat(),
            },
            indent=2,
        )
    )


@app.command("verify")
def verify_migration(
    plan: Annotated[
        Path,
        typer.Option(exists=True, dir_okay=False, help="Migration plan JSON."),
    ],
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
) -> None:
    paths = resolve_paths(root)
    parsed = _load_current_migration_plan(plan, paths.project_root)
    try:
        verify_migration_definition(parsed)
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


def _load_current_migration_plan(plan_path: Path, project_root: Path) -> OperationPlan:
    parsed = load_plan(plan_path)
    if parsed.action != "migrate":
        raise typer.BadParameter("plan action must be migrate", param_hint="--plan")
    planned_root = Path(parsed.roots.get("project", "")).resolve()
    if planned_root != project_root.resolve():
        raise typer.BadParameter(
            "migration plan belongs to a different project root", param_hint="--plan"
        )
    return parsed
