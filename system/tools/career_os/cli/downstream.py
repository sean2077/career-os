from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from career_os.config import resolve_paths
from career_os.downstream import (
    apply_downstream_sync_plan,
    create_downstream_sync_plan,
    rollback_downstream_sync_plan,
    validate_downstream_sync_plan,
)


class SyncSource(StrEnum):
    local = "local"
    upstream = "upstream"


app = typer.Typer(
    help=(
        "Plan, apply, validate, and roll back exact system snapshots in a "
        "split-downstream installation."
    )
)


@app.command("plan")
def plan_sync(
    source: Annotated[
        SyncSource,
        typer.Option(help="Read the exact ref from a local repository or upstream."),
    ],
    commit: Annotated[
        str | None,
        typer.Option(help="Full 40-character source commit SHA."),
    ] = None,
    tag: Annotated[
        str | None,
        typer.Option(help="Exact annotated source tag."),
    ] = None,
    source_root: Annotated[
        Path | None,
        typer.Option(help="Local Career OS Git root; valid only with --source local."),
    ] = None,
    root: Annotated[
        Path,
        typer.Option(help="Path inside the private Career OS downstream."),
    ] = Path("."),
) -> None:
    paths = resolve_paths(root)
    try:
        plan, plan_path = create_downstream_sync_plan(
            paths,
            source_kind=source.value,
            source_root=source_root,
            commit=commit,
            tag=tag,
        )
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "plan": str(plan_path),
                "patch": str(plan_path.parent / plan.patch_file),
                "source": plan.source_kind,
                "reference_kind": plan.reference_kind,
                "requested_reference": plan.requested_reference,
                "source_commit": plan.source_commit,
                "target_head": plan.target_head,
                "target_branch": plan.target_branch,
                "source_system_version": plan.source_system_version,
                "target_system_version": plan.target_system_version,
                "operations": len(plan.changed_paths),
                "changed_paths": plan.changed_paths,
            },
            indent=2,
        )
    )


@app.command("apply")
def apply_sync(
    plan: Annotated[
        Path,
        typer.Option(exists=True, dir_okay=False, help="Reviewed downstream sync plan JSON."),
    ],
    root: Annotated[
        Path,
        typer.Option(help="Path inside the private Career OS downstream."),
    ] = Path("."),
) -> None:
    paths = resolve_paths(root)
    try:
        applied = apply_downstream_sync_plan(plan, paths)
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error), param_hint="--plan") from error
    if applied.applied_at is None:
        raise RuntimeError("applied synchronization plan is missing its completion timestamp")
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "plan": str(plan),
                "source_commit": applied.source_commit,
                "operations": len(applied.changed_paths),
                "applied_at": applied.applied_at.isoformat(),
            },
            indent=2,
        )
    )


@app.command("rollback")
def rollback_sync(
    plan: Annotated[
        Path,
        typer.Option(exists=True, dir_okay=False, help="Applied downstream sync plan JSON."),
    ],
    root: Annotated[
        Path,
        typer.Option(help="Path inside the private Career OS downstream."),
    ] = Path("."),
) -> None:
    paths = resolve_paths(root)
    try:
        rolled_back = rollback_downstream_sync_plan(plan, paths)
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error), param_hint="--plan") from error
    if rolled_back.rolled_back_at is None:
        raise RuntimeError("rolled-back synchronization plan is missing its completion timestamp")
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "plan": str(plan),
                "operations": len(rolled_back.changed_paths),
                "rolled_back_at": rolled_back.rolled_back_at.isoformat(),
            },
            indent=2,
        )
    )


@app.command("validate")
def validate_sync(
    plan: Annotated[
        Path,
        typer.Option(exists=True, dir_okay=False, help="Applied downstream sync plan JSON."),
    ],
    output: Annotated[
        Path,
        typer.Option(help="New validation JSON under the private data root."),
    ],
    root: Annotated[
        Path,
        typer.Option(help="Path inside the private Career OS downstream."),
    ] = Path("."),
) -> None:
    paths = resolve_paths(root)
    try:
        validation = validate_downstream_sync_plan(plan, output, paths)
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "output": str(output.resolve()),
                "source_tag": validation.source_tag,
                "source_commit": validation.source_commit,
                "target_branch": validation.target_branch,
                "checks": len(validation.checks),
                "validated_at": validation.validated_at.isoformat(),
            },
            indent=2,
        )
    )
