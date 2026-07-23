from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal, cast

import typer

from career_os.adapters.obsidian import plan_vault_operation
from career_os.config import resolve_paths
from career_os.operations import apply_plan, load_plan

app = typer.Typer(help="Plan and apply reversible Obsidian Vault attachments.")


@app.command("plan")
def plan_command(
    action: Annotated[str, typer.Option(help="Attachment action: attach or detach.")],
    vault_root: Annotated[
        Path, typer.Option(exists=True, file_okay=False, help="Host Obsidian Vault root.")
    ],
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
    with_quickadd: Annotated[
        bool, typer.Option(help="Include the reviewed QuickAdd 2.12.3 adapter bundle.")
    ] = False,
) -> None:
    if action not in {"attach", "detach"}:
        raise typer.BadParameter("action must be attach or detach", param_hint="--action")
    paths = resolve_paths(root)
    try:
        result = plan_vault_operation(
            paths,
            action=cast(Literal["attach", "detach"], action),
            vault_root=vault_root,
            with_quickadd=with_quickadd,
        )
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "action": result.plan.action,
                "plan": str(result.path),
                "operations": len(result.plan.operations),
                "repository_mode": result.repository_mode,
                "warnings": list(result.warnings),
            },
            indent=2,
        )
    )


@app.command("apply")
def apply_command(
    plan: Annotated[
        Path, typer.Option(exists=True, dir_okay=False, help="Reviewed Vault plan JSON.")
    ],
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
) -> None:
    paths = resolve_paths(root)
    parsed = load_plan(plan)
    if parsed.action not in {"vault.attach", "vault.detach"}:
        raise typer.BadParameter("plan action must be vault.attach or vault.detach")
    if Path(parsed.roots.get("project", "")).resolve() != paths.project_root:
        raise typer.BadParameter("plan project root does not match this Career OS repository")
    try:
        applied = apply_plan(plan, paths.local_state_root)
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error
    if applied.applied_at is None:
        raise RuntimeError("applied Vault plan is missing its completion timestamp")
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "action": applied.action,
                "plan": str(plan),
                "applied_at": applied.applied_at.isoformat(),
            },
            indent=2,
        )
    )
