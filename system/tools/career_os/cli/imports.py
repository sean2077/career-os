from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from career_os.config import resolve_paths
from career_os.imports import (
    create_import_plan,
    create_migration_inventory,
    verify_import_plan,
    verify_migration_inventory,
)
from career_os.operations import OperationPlan, apply_plan, load_plan, rollback_plan
from career_os.operations.plans import sha256_text, write_plan
from career_os.semantic_review import verify_semantic_file_review

app = typer.Typer(help="Plan, apply, and roll back hash-bound legacy repository imports.")


@app.command("inventory")
def inventory_import(
    source_root: Annotated[
        Path,
        typer.Option(exists=True, file_okay=False, help="Clean legacy Git repository root."),
    ],
    rules: Annotated[
        Path,
        typer.Option(exists=True, dir_okay=False, help="Reviewed inventory rules JSON."),
    ],
    output: Annotated[
        Path,
        typer.Option(help="New JSON inventory path inside the configured data root."),
    ],
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
) -> None:
    paths = resolve_paths(root)
    try:
        output_path = _data_control_path(output, paths.data_root)
        inventory = create_migration_inventory(source_root, rules)
        content = json.dumps(inventory.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
        if output_path.exists():
            if not output_path.is_file() or output_path.read_text(encoding="utf-8") != content:
                raise ValueError("inventory output already exists with different contents")
            changed = False
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8", newline="\n")
            changed = True
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error), param_hint="--output") from error
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "output": str(output_path),
                "sha256": sha256_text(content),
                "source_commit": inventory.source_commit,
                "entries": len(inventory.entries),
                "dispositions": _inventory_counts(
                    [entry.disposition for entry in inventory.entries]
                ),
                "asset_types": _inventory_counts([entry.asset_type for entry in inventory.entries]),
                "changed": changed,
            },
            indent=2,
        )
    )


@app.command("verify-inventory")
def verify_inventory_import(
    source_root: Annotated[
        Path,
        typer.Option(exists=True, file_okay=False, help="Clean legacy Git repository root."),
    ],
    rules: Annotated[
        Path,
        typer.Option(exists=True, dir_okay=False, help="Reviewed inventory rules JSON."),
    ],
    inventory: Annotated[
        Path,
        typer.Option(exists=True, dir_okay=False, help="Migration inventory JSON."),
    ],
) -> None:
    try:
        verified = verify_migration_inventory(source_root, rules, inventory)
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error), param_hint="--inventory") from error
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "inventory": str(inventory.resolve()),
                "source_commit": verified.source_commit,
                "entries": len(verified.entries),
            },
            indent=2,
        )
    )


@app.command("verify-review")
def verify_review_import(
    source_root: Annotated[
        Path,
        typer.Option(exists=True, file_okay=False, help="Clean legacy Git repository root."),
    ],
    rules: Annotated[
        Path,
        typer.Option(exists=True, dir_okay=False, help="Reviewed inventory rules JSON."),
    ],
    inventory: Annotated[
        Path,
        typer.Option(exists=True, dir_okay=False, help="Frozen migration inventory JSON."),
    ],
    review: Annotated[
        Path,
        typer.Option(exists=True, dir_okay=False, help="Semantic file review control JSON."),
    ],
    public_root: Annotated[
        Path | None,
        typer.Option(
            exists=True,
            file_okay=False,
            help=(
                "Optional framework checkout used to resolve public-bound target evidence; "
                "omit it only when the configured topology resolves the framework locally."
            ),
        ),
    ] = None,
    root: Annotated[Path, typer.Option(help="Path inside the target Career OS project.")] = Path(
        "."
    ),
) -> None:
    paths = resolve_paths(root)
    try:
        verified = verify_semantic_file_review(
            paths,
            inventory_path=inventory,
            review_path=review,
            source_root=source_root,
            rules_path=rules,
            public_root=public_root,
        )
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error), param_hint="--review") from error
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "review": str(review.resolve()),
                "source_commit": verified.control.source_commit,
                "entries": len(verified.control.entries),
                "dispositions": verified.disposition_counts,
                "target_files": verified.target_files,
                "target_tree_sha256": verified.target_tree_sha256,
                "residual_gaps": len(verified.control.residual_gaps),
            },
            indent=2,
        )
    )


@app.command("plan")
def plan_import(
    source_root: Annotated[
        Path,
        typer.Option(exists=True, file_okay=False, help="Clean legacy Git repository root."),
    ],
    manifest: Annotated[
        Path,
        typer.Option(exists=True, dir_okay=False, help="Legacy import manifest JSON."),
    ],
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
) -> None:
    paths = resolve_paths(root)
    try:
        plan = create_import_plan(paths, source_root, manifest)
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error), param_hint="--manifest") from error
    plan_path = paths.local_state_root / "plans" / f"import-{plan.id}.json"
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
                "operations": len(plan.operations),
                "provenance_path": plan.metadata["provenance_path"],
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
        applied = apply_plan(plan, paths.local_state_root)
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error), param_hint="--plan") from error
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
        rolled_back = rollback_plan(plan, paths.local_state_root)
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error), param_hint="--plan") from error
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


def _data_control_path(output: Path, data_root: Path) -> Path:
    data_root = data_root.resolve()
    output_path = output.resolve()
    if not output_path.is_relative_to(data_root):
        raise ValueError("inventory output must be inside the configured data root")
    if output_path.suffix.lower() != ".json":
        raise ValueError("inventory output must be a JSON file")
    return output_path


def _inventory_counts(values: list[str]) -> dict[str, int]:
    return {value: values.count(value) for value in sorted(set(values))}
