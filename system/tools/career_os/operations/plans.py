from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid4

from career_os.operations.models import FileOperation, OperationPlan


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def create_plan(
    *,
    action: str,
    source_version: str,
    target_version: str,
    roots: dict[str, Path],
    operations: list[FileOperation],
    metadata: dict[str, str] | None = None,
    plan_id: UUID | None = None,
) -> OperationPlan:
    payload = {
        "schema_version": 1,
        "id": str(plan_id or uuid4()),
        "action": action,
        "created_at": datetime.now(UTC).isoformat(),
        "source_version": source_version,
        "target_version": target_version,
        "roots": {key: str(value.resolve()) for key, value in sorted(roots.items())},
        "metadata": dict(sorted((metadata or {}).items())),
        "operations": [item.model_dump(mode="json") for item in operations],
        "applied_at": None,
        "rolled_back_at": None,
    }
    plan = OperationPlan.model_validate({**payload, "plan_sha256": ""})
    return _rehash(plan)


def write_plan(plan: OperationPlan, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(plan.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def load_plan(path: Path) -> OperationPlan:
    plan = OperationPlan.model_validate_json(path.read_text(encoding="utf-8"))
    dumped = plan.model_dump(mode="json")
    expected = dumped.pop("plan_sha256")
    if _payload_hash(dumped) != expected:
        raise ValueError("operation plan hash does not match its contents")
    return plan


def apply_plan(plan_path: Path, state_root: Path) -> OperationPlan:
    plan = load_plan(plan_path)
    if plan.applied_at is not None:
        return plan
    backup_root = state_root / "backups" / str(plan.id)
    roots = {key: Path(value).resolve() for key, value in plan.roots.items()}

    for index, operation in enumerate(plan.operations):
        target = _resolve_operation_path(roots, operation)
        if operation.op == "copy_file":
            source = _resolve_copy_source(roots, operation)
            if sha256_file(source) != operation.source_sha256:
                raise ValueError(f"stale operation source: {source}")
        current_hash = sha256_file(target)
        if current_hash != operation.expected_sha256:
            raise ValueError(f"stale operation target: {target}")
        backup = backup_root / f"{index:04d}" / operation.path
        if target.is_file():
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)

    try:
        for operation in plan.operations:
            target = _resolve_operation_path(roots, operation)
            if operation.op == "mkdir":
                target.mkdir(parents=True, exist_ok=True)
            elif operation.op == "write_text":
                if operation.content is None:
                    raise ValueError("write_text operation is missing content")
                if sha256_text(operation.content) != operation.result_sha256:
                    raise ValueError("write_text operation result hash is invalid")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(operation.content, encoding="utf-8", newline="\n")
            elif operation.op == "copy_file":
                source = _resolve_copy_source(roots, operation)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                if sha256_file(target) != operation.result_sha256:
                    raise ValueError(f"copy_file result hash is invalid: {target}")
            elif operation.op == "delete":
                if target.is_file() or target.is_symlink():
                    target.unlink()
                elif target.is_dir() and not any(target.iterdir()):
                    target.rmdir()
    except Exception:
        _restore_preapply(plan, roots, backup_root)
        raise

    updated = plan.model_copy(update={"applied_at": datetime.now(UTC)})
    updated = _rehash(updated)
    write_plan(updated, plan_path)
    return updated


def rollback_plan(plan_path: Path, state_root: Path) -> OperationPlan:
    plan = load_plan(plan_path)
    if plan.applied_at is None:
        raise ValueError("operation plan has not been applied")
    if plan.rolled_back_at is not None:
        return plan
    roots = {key: Path(value).resolve() for key, value in plan.roots.items()}
    backup_root = state_root / "backups" / str(plan.id)

    for operation in plan.operations:
        target = _resolve_operation_path(roots, operation)
        if operation.op in {"write_text", "copy_file"} and sha256_file(
            target
        ) != operation.result_sha256:
            raise ValueError(f"rollback target changed after apply: {target}")
        if operation.op == "delete" and (target.exists() or target.is_symlink()):
            raise ValueError(f"rollback target changed after apply: {target}")

    for index, operation in reversed(list(enumerate(plan.operations))):
        target = _resolve_operation_path(roots, operation)
        backup = backup_root / f"{index:04d}" / operation.path
        if backup.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, target)
        elif operation.op in {"write_text", "copy_file"} and target.is_file():
            target.unlink()
        elif operation.op == "mkdir" and target.is_dir() and not any(target.iterdir()):
            target.rmdir()

    updated = plan.model_copy(update={"rolled_back_at": datetime.now(UTC)})
    updated = _rehash(updated)
    write_plan(updated, plan_path)
    return updated


def _resolve_operation_path(roots: dict[str, Path], operation: FileOperation) -> Path:
    if operation.root not in roots:
        raise ValueError(f"plan does not define root: {operation.root}")
    relative = PurePosixPath(operation.path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"operation path escapes its root: {operation.path}")
    root = roots[operation.root]
    target = root.joinpath(*relative.parts).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"operation path escapes its root: {operation.path}")
    return target


def _resolve_copy_source(roots: dict[str, Path], operation: FileOperation) -> Path:
    if operation.source_root is None or operation.source_path is None:
        raise ValueError("copy_file operation is missing its source")
    if operation.source_root not in roots:
        raise ValueError(f"plan does not define source root: {operation.source_root}")
    relative = PurePosixPath(operation.source_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"operation source path escapes its root: {operation.source_path}")
    root = roots[operation.source_root]
    source = root.joinpath(*relative.parts).resolve()
    if not source.is_relative_to(root):
        raise ValueError(f"operation source path escapes its root: {operation.source_path}")
    if not source.is_file():
        raise ValueError(f"operation source is missing: {source}")
    return source


def _payload_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _rehash(plan: OperationPlan) -> OperationPlan:
    dumped = plan.model_dump(mode="json")
    dumped.pop("plan_sha256")
    return plan.model_copy(update={"plan_sha256": _payload_hash(dumped)})


def _restore_preapply(plan: OperationPlan, roots: dict[str, Path], backup_root: Path) -> None:
    for index, operation in reversed(list(enumerate(plan.operations))):
        target = _resolve_operation_path(roots, operation)
        backup = backup_root / f"{index:04d}" / operation.path
        if backup.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, target)
        elif operation.expected_sha256 is None and (target.is_file() or target.is_symlink()):
            target.unlink()
        elif operation.op == "mkdir" and target.is_dir() and not any(target.iterdir()):
            target.rmdir()
