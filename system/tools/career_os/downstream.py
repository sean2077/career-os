from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from career_os.config import ProjectConfig, ProjectPaths, serialize_project_config
from career_os.git_safety import inspect_downstream_git_safety

SourceKind = Literal["local", "upstream"]
ReferenceKind = Literal["commit", "tag"]

_FULL_COMMIT = re.compile(r"^[0-9a-fA-F]{40}$")
_SHA256 = r"^[0-9a-f]{64}$"
_ALWAYS_PROTECTED = (".career-os", ".git", ".obsidian", "build", "career", "runtime")
_TRUNK_BRANCHES = {"main", "master", "trunk"}


@dataclass(frozen=True)
class TreeEntry:
    mode: str
    object_type: str
    object_id: str
    path: str


class DownstreamSyncPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    id: UUID
    action: Literal["downstream.sync"] = "downstream.sync"
    created_at: datetime
    target_root: str
    target_head: str
    target_branch: str
    target_system_version: str
    source_kind: SourceKind
    source_location: str
    reference_kind: ReferenceKind
    requested_reference: str
    source_object: str
    source_commit: str
    source_system_version: str
    desired_tree: str
    patch_file: str
    patch_sha256: str = Field(pattern=_SHA256)
    changed_paths: list[str]
    plan_sha256: str = Field(pattern=_SHA256)
    applied_at: datetime | None = None
    rolled_back_at: datetime | None = None


class DownstreamSyncValidationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: Literal["passed"] = "passed"
    detail: str


class DownstreamSyncValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    control_type: Literal["downstream-sync-validation"] = "downstream-sync-validation"
    status: Literal["passed"] = "passed"
    source_tag: str
    tag_object: str
    source_commit: str
    target_branch: str
    target_head: str
    desired_tree: str
    plan_sha256: str = Field(pattern=_SHA256)
    patch_sha256: str = Field(pattern=_SHA256)
    applied_at: datetime
    validated_at: datetime
    checks: list[DownstreamSyncValidationCheck]
    external_actions_performed: list[str] = Field(default_factory=list, max_length=0)


def downstream_sync_validation_json_schema() -> dict[str, Any]:
    schema = DownstreamSyncValidation.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://career-os.dev/schemas/downstream-sync-validation.schema.json"
    schema["title"] = "Career OS Downstream Sync Validation"
    return schema


def create_downstream_sync_plan(
    paths: ProjectPaths,
    *,
    source_kind: SourceKind,
    source_root: Path | None,
    commit: str | None,
    tag: str | None,
) -> tuple[DownstreamSyncPlan, Path]:
    _require_split_downstream(paths)
    target_root = paths.project_root.resolve()
    _require_git_root(target_root)
    _require_downstream_safety(
        target_root, require_upstream=source_kind == "upstream"
    )
    _require_no_git_operation(target_root)
    target_branch = _require_isolated_sync_branch(target_root)
    reference_kind, requested_reference = _select_reference(commit, tag)
    target_head = _git_text(target_root, "rev-parse", "HEAD")

    if source_kind == "local":
        if source_root is None:
            raise ValueError("local synchronization requires --source-root")
        source_location_path = source_root.resolve()
        _require_git_root(source_location_path)
        if source_location_path == target_root:
            raise ValueError("local source repository must differ from the downstream target")
        source_object, source_commit = _resolve_local_reference(
            source_location_path, reference_kind, requested_reference
        )
        _git(
            target_root,
            "fetch",
            "--no-tags",
            "--no-write-fetch-head",
            str(source_location_path),
            source_object,
        )
        source_location = str(source_location_path)
    elif source_kind == "upstream":
        if source_root is not None:
            raise ValueError("upstream synchronization does not accept --source-root")
        source_object, source_commit = _resolve_upstream_reference(
            target_root, reference_kind, requested_reference
        )
        source_location = "upstream"
    else:
        raise ValueError(f"unsupported synchronization source: {source_kind}")

    _require_object_type(target_root, source_object, "tag" if reference_kind == "tag" else "commit")
    resolved_commit = _git_text(target_root, "rev-parse", f"{source_object}^{{commit}}")
    if resolved_commit != source_commit:
        raise ValueError("fetched source object resolves to a different commit")

    protected = _protected_prefixes(paths)
    source_entries = _tree_entries(target_root, source_commit)
    _validate_source_snapshot(target_root, source_commit, source_entries, protected)
    source_entries = _adapt_source_config(
        target_root,
        target_head,
        source_commit,
        source_entries,
    )
    target_entries = _tree_entries(target_root, target_head)
    target_managed = [entry for entry in target_entries if not _is_protected(entry.path, protected)]
    desired_tree = _build_desired_tree(
        target_root,
        paths.local_state_root,
        target_head,
        target_managed,
        source_entries,
    )
    changed_paths = _git_paths(
        target_root,
        "diff",
        "--name-only",
        "-z",
        "--no-renames",
        target_head,
        desired_tree,
    )
    protected_changes = [path for path in changed_paths if _is_protected(path, protected)]
    if protected_changes:
        raise ValueError(
            "synchronization plan crosses a protected path: " + ", ".join(protected_changes)
        )
    _require_paths_clean(target_root, changed_paths)

    patch = _git(
        target_root,
        "diff",
        "--binary",
        "--full-index",
        "--no-ext-diff",
        "--no-renames",
        target_head,
        desired_tree,
    )
    if _git_text(target_root, "rev-parse", "HEAD") != target_head:
        raise ValueError("downstream HEAD changed while the synchronization plan was created")

    plan_id = uuid4()
    plan_dir = paths.local_state_root / "plans"
    plan_path = plan_dir / f"downstream-sync-{plan_id}.json"
    patch_path = plan_dir / f"downstream-sync-{plan_id}.patch"
    plan_dir.mkdir(parents=True, exist_ok=True)
    patch_path.write_bytes(patch)
    plan = DownstreamSyncPlan(
        id=plan_id,
        created_at=datetime.now(UTC),
        target_root=str(target_root),
        target_head=target_head,
        target_branch=target_branch,
        target_system_version=_system_version(target_root, target_head),
        source_kind=source_kind,
        source_location=source_location,
        reference_kind=reference_kind,
        requested_reference=requested_reference,
        source_object=source_object,
        source_commit=source_commit,
        source_system_version=_system_version(target_root, source_commit),
        desired_tree=desired_tree,
        patch_file=patch_path.name,
        patch_sha256=_sha256_bytes(patch),
        changed_paths=changed_paths,
        plan_sha256="0" * 64,
    )
    plan = _rehash(plan)
    write_downstream_sync_plan(plan, plan_path)
    return plan, plan_path


def apply_downstream_sync_plan(
    plan_path: Path, paths: ProjectPaths
) -> DownstreamSyncPlan:
    _require_split_downstream(paths)
    plan = _load_current_plan(plan_path, paths.project_root)
    if plan.rolled_back_at is not None:
        raise ValueError("synchronization plan has already been rolled back")
    target_root = paths.project_root.resolve()
    _require_downstream_safety(
        target_root, require_upstream=plan.source_kind == "upstream"
    )
    _require_no_git_operation(target_root)
    _require_planned_branch(target_root, plan.target_branch)
    patch_path = _verified_patch_path(plan, plan_path)
    _require_target_head(target_root, plan.target_head)
    _verify_patch_tree(target_root, plan, patch_path)

    if plan.applied_at is not None:
        _require_paths_match_tree(target_root, plan.changed_paths, plan.desired_tree)
        return plan

    _require_paths_clean(target_root, plan.changed_paths)
    if plan.changed_paths:
        _git(target_root, "apply", "--check", "--binary", str(patch_path))
        _git(target_root, "apply", "--binary", str(patch_path))
        try:
            _require_paths_match_tree(target_root, plan.changed_paths, plan.desired_tree)
        except ValueError:
            _git(target_root, "apply", "--reverse", "--binary", str(patch_path))
            raise

    updated = plan.model_copy(update={"applied_at": datetime.now(UTC)})
    updated = _rehash(updated)
    write_downstream_sync_plan(updated, plan_path)
    return updated


def rollback_downstream_sync_plan(
    plan_path: Path, paths: ProjectPaths
) -> DownstreamSyncPlan:
    _require_split_downstream(paths)
    plan = _load_current_plan(plan_path, paths.project_root)
    if plan.applied_at is None:
        raise ValueError("synchronization plan has not been applied")
    target_root = paths.project_root.resolve()
    _require_downstream_safety(
        target_root, require_upstream=plan.source_kind == "upstream"
    )
    _require_no_git_operation(target_root)
    _require_planned_branch(target_root, plan.target_branch)
    patch_path = _verified_patch_path(plan, plan_path)
    _require_target_head(target_root, plan.target_head)
    _verify_patch_tree(target_root, plan, patch_path)

    if plan.rolled_back_at is not None:
        _require_paths_match_tree(target_root, plan.changed_paths, plan.target_head)
        return plan

    _require_paths_match_tree(target_root, plan.changed_paths, plan.desired_tree)
    if plan.changed_paths:
        _git(target_root, "apply", "--check", "--reverse", "--binary", str(patch_path))
        _git(target_root, "apply", "--reverse", "--binary", str(patch_path))
        _require_paths_match_tree(target_root, plan.changed_paths, plan.target_head)

    updated = plan.model_copy(update={"rolled_back_at": datetime.now(UTC)})
    updated = _rehash(updated)
    write_downstream_sync_plan(updated, plan_path)
    return updated


def validate_downstream_sync_plan(
    plan_path: Path,
    output_path: Path,
    paths: ProjectPaths,
) -> DownstreamSyncValidation:
    _require_split_downstream(paths)
    plan = _load_current_plan(plan_path, paths.project_root)
    if plan.reference_kind != "tag":
        raise ValueError("completion evidence requires an exact annotated-tag plan")
    if plan.applied_at is None:
        raise ValueError("synchronization plan has not been applied")
    if plan.rolled_back_at is not None:
        raise ValueError("synchronization plan has already been rolled back")

    target_root = paths.project_root.resolve()
    _require_downstream_safety(
        target_root, require_upstream=plan.source_kind == "upstream"
    )
    _require_no_git_operation(target_root)
    _require_planned_branch(target_root, plan.target_branch)
    _require_target_head(target_root, plan.target_head)
    patch_path = _verified_patch_path(plan, plan_path)
    _verify_patch_tree(target_root, plan, patch_path)
    _require_paths_match_tree(target_root, plan.changed_paths, plan.desired_tree)
    _require_object_type(target_root, plan.source_object, "tag")
    peeled = _git_text(target_root, "rev-parse", f"{plan.source_object}^{{commit}}")
    if peeled != plan.source_commit:
        raise ValueError("annotated tag resolves to a different source commit")
    protected = _protected_prefixes(paths)
    forbidden = [path for path in plan.changed_paths if _is_protected(path, protected)]
    if forbidden:
        raise ValueError(
            "synchronization validation found protected paths: "
            + ", ".join(sorted(forbidden))
        )

    output = output_path.resolve()
    data_root = paths.data_root.resolve()
    if not output.is_relative_to(data_root) or output.suffix.lower() != ".json":
        raise ValueError("synchronization validation output must be a JSON file under data_root")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError(f"synchronization validation output already exists: {output}")

    validation = DownstreamSyncValidation(
        source_tag=plan.requested_reference,
        tag_object=plan.source_object,
        source_commit=plan.source_commit,
        target_branch=plan.target_branch,
        target_head=plan.target_head,
        desired_tree=plan.desired_tree,
        plan_sha256=plan.plan_sha256,
        patch_sha256=plan.patch_sha256,
        applied_at=plan.applied_at,
        validated_at=datetime.now(UTC),
        checks=[
            DownstreamSyncValidationCheck(
                id="remote-safety",
                detail=(
                    "canonical public upstream is fetch-only"
                    if plan.source_kind == "upstream"
                    else "optional public upstream is absent or safely configured"
                ),
            ),
            DownstreamSyncValidationCheck(
                id="isolated-branch",
                detail=f"current branch matches {plan.target_branch}",
            ),
            DownstreamSyncValidationCheck(
                id="target-head",
                detail=f"HEAD remains {plan.target_head}",
            ),
            DownstreamSyncValidationCheck(
                id="annotated-tag",
                detail=f"{plan.requested_reference} peels to {plan.source_commit}",
            ),
            DownstreamSyncValidationCheck(
                id="plan-and-patch",
                detail="plan and binary patch hashes match",
            ),
            DownstreamSyncValidationCheck(
                id="desired-tree",
                detail=f"changed paths reconstruct {plan.desired_tree}",
            ),
            DownstreamSyncValidationCheck(
                id="protected-paths",
                detail="no protected user or local path is present",
            ),
        ],
    )
    try:
        with output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(validation.model_dump(mode="json"), indent=2) + "\n")
    except FileExistsError as error:
        raise ValueError(f"synchronization validation output already exists: {output}") from error
    return validation


def write_downstream_sync_plan(plan: DownstreamSyncPlan, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(plan.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def _require_split_downstream(paths: ProjectPaths) -> None:
    if paths.development_topology != "split-downstream":
        raise ValueError(
            "downstream synchronization requires development_topology = "
            '"split-downstream"; integrated-workbench changes are developed in place'
        )


def load_downstream_sync_plan(path: Path) -> DownstreamSyncPlan:
    plan = DownstreamSyncPlan.model_validate_json(path.read_text(encoding="utf-8"))
    dumped = plan.model_dump(mode="json")
    expected = dumped.pop("plan_sha256")
    if _payload_hash(dumped) != expected:
        raise ValueError("downstream synchronization plan hash does not match its contents")
    return plan


def _select_reference(commit: str | None, tag: str | None) -> tuple[ReferenceKind, str]:
    if (commit is None) == (tag is None):
        raise ValueError("specify exactly one of --commit or --tag")
    if commit is not None:
        if not _FULL_COMMIT.fullmatch(commit):
            raise ValueError("--commit must be a full 40-character Git commit SHA")
        return "commit", commit.lower()
    assert tag is not None
    if not tag.strip() or tag != tag.strip():
        raise ValueError("--tag must be a non-empty exact tag name")
    return "tag", tag


def _resolve_local_reference(
    source_root: Path, reference_kind: ReferenceKind, reference: str
) -> tuple[str, str]:
    if reference_kind == "commit":
        _require_object_type(source_root, reference, "commit")
        return reference, reference
    _validate_tag_name(source_root, reference)
    try:
        source_object = _git_text(
            source_root, "show-ref", "--verify", "--hash", f"refs/tags/{reference}"
        )
    except ValueError as error:
        raise ValueError(f"local source tag does not exist: {reference}") from error
    _require_object_type(source_root, source_object, "tag")
    source_commit = _git_text(source_root, "rev-parse", f"{source_object}^{{commit}}")
    return source_object, source_commit


def _resolve_upstream_reference(
    target_root: Path, reference_kind: ReferenceKind, reference: str
) -> tuple[str, str]:
    if reference_kind == "commit":
        _git(
            target_root,
            "fetch",
            "--no-tags",
            "--no-write-fetch-head",
            "upstream",
            reference,
        )
        _require_object_type(target_root, reference, "commit")
        return reference, reference

    _validate_tag_name(target_root, reference)
    remote_ref = f"refs/tags/{reference}"
    try:
        advertised = _git_text(
            target_root,
            "ls-remote",
            "--exit-code",
            "--refs",
            "upstream",
            remote_ref,
        )
    except ValueError as error:
        raise ValueError(f"upstream tag does not exist: {reference}") from error
    lines = [line for line in advertised.splitlines() if line.strip()]
    if len(lines) != 1:
        raise ValueError(f"upstream tag did not resolve exactly once: {reference}")
    source_object, resolved_ref = lines[0].split(maxsplit=1)
    if resolved_ref != remote_ref or not _FULL_COMMIT.fullmatch(source_object):
        raise ValueError(f"upstream returned an invalid tag object for: {reference}")
    _git(
        target_root,
        "fetch",
        "--no-tags",
        "--no-write-fetch-head",
        "upstream",
        source_object,
    )
    _require_object_type(target_root, source_object, "tag")
    source_commit = _git_text(target_root, "rev-parse", f"{source_object}^{{commit}}")
    return source_object, source_commit


def _validate_tag_name(repo_root: Path, tag: str) -> None:
    _git(repo_root, "check-ref-format", f"refs/tags/{tag}")


def _validate_source_snapshot(
    repo_root: Path,
    source_commit: str,
    source_entries: list[TreeEntry],
    protected: tuple[str, ...],
) -> None:
    paths = {entry.path for entry in source_entries}
    if "career-os.toml" not in paths:
        raise ValueError("source commit is not a Career OS snapshot: career-os.toml is missing")
    if not any(path.startswith("system/tools/career_os/") for path in paths):
        raise ValueError("source commit is not a Career OS snapshot: CLI implementation is missing")
    forbidden = sorted(path for path in paths if _is_protected(path, protected))
    if forbidden:
        raise ValueError(
            "source commit tracks protected private or local state: " + ", ".join(forbidden)
        )
    unsupported = sorted(entry.path for entry in source_entries if entry.object_type != "blob")
    if unsupported:
        raise ValueError(
            "source commit contains unsupported tracked object types: " + ", ".join(unsupported)
        )


def _protected_prefixes(paths: ProjectPaths) -> tuple[str, ...]:
    protected = set(_ALWAYS_PROTECTED)
    project_root = paths.project_root.resolve()
    for candidate in (
        paths.data_root,
        paths.runtime_root,
        paths.build_root,
        paths.local_state_root,
    ):
        resolved = candidate.resolve()
        if resolved.is_relative_to(project_root):
            relative = resolved.relative_to(project_root).as_posix()
            if relative and relative != ".":
                protected.add(relative)
    return tuple(sorted(protected))


def _is_protected(path: str, protected: tuple[str, ...]) -> bool:
    normalized = PurePosixPath(path).as_posix()
    return any(normalized == prefix or normalized.startswith(f"{prefix}/") for prefix in protected)


def _build_desired_tree(
    repo_root: Path,
    state_root: Path,
    target_head: str,
    target_managed: list[TreeEntry],
    source_entries: list[TreeEntry],
) -> str:
    temporary_parent = state_root / "tmp"
    temporary_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="downstream-sync-", dir=temporary_parent) as directory:
        index_path = Path(directory) / "index"
        environment = {"GIT_INDEX_FILE": str(index_path)}
        _git(repo_root, "read-tree", target_head, environment=environment)
        if target_managed:
            remove_payload = b"".join(
                entry.path.encode("utf-8", errors="surrogateescape") + b"\0"
                for entry in target_managed
            )
            _git(
                repo_root,
                "update-index",
                "--force-remove",
                "-z",
                "--stdin",
                input_bytes=remove_payload,
                environment=environment,
            )
        if source_entries:
            add_payload = b"".join(
                f"{entry.mode} {entry.object_id}\t".encode()
                + entry.path.encode("utf-8", errors="surrogateescape")
                + b"\0"
                for entry in source_entries
            )
            _git(
                repo_root,
                "update-index",
                "-z",
                "--index-info",
                input_bytes=add_payload,
                environment=environment,
            )
        return _git_text(repo_root, "write-tree", environment=environment)


def _adapt_source_config(
    repo_root: Path,
    target_head: str,
    source_commit: str,
    source_entries: list[TreeEntry],
) -> list[TreeEntry]:
    source_config = _project_config_at(repo_root, source_commit)
    target_config = _project_config_at(repo_root, target_head)
    adapted_config = ProjectConfig.model_validate(
        {
            **source_config.model_dump(),
            "development_topology": "split-downstream",
            "data_root": target_config.data_root,
            "runtime_root": target_config.runtime_root,
            "build_root": target_config.build_root,
            "preferred_language": target_config.preferred_language,
        }
    )
    object_id = _git(
        repo_root,
        "hash-object",
        "-w",
        "--stdin",
        input_bytes=serialize_project_config(adapted_config).encode("utf-8"),
    ).decode().strip()
    return [
        (
            TreeEntry(
                mode=entry.mode,
                object_type=entry.object_type,
                object_id=object_id,
                path=entry.path,
            )
            if entry.path == "career-os.toml"
            else entry
        )
        for entry in source_entries
    ]


def _verify_patch_tree(
    repo_root: Path, plan: DownstreamSyncPlan, patch_path: Path
) -> None:
    temporary_parent = Path(plan.target_root) / ".career-os" / "tmp"
    temporary_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="downstream-verify-", dir=temporary_parent
    ) as directory:
        index_path = Path(directory) / "index"
        environment = {"GIT_INDEX_FILE": str(index_path)}
        _git(repo_root, "read-tree", plan.target_head, environment=environment)
        if plan.changed_paths:
            _git(
                repo_root,
                "apply",
                "--cached",
                "--binary",
                str(patch_path),
                environment=environment,
            )
        reconstructed = _git_text(repo_root, "write-tree", environment=environment)
    if reconstructed != plan.desired_tree:
        raise ValueError("synchronization patch does not reconstruct the planned Git tree")


def _tree_entries(repo_root: Path, treeish: str) -> list[TreeEntry]:
    output = _git(repo_root, "ls-tree", "-r", "-z", treeish)
    entries: list[TreeEntry] = []
    for record in output.split(b"\0"):
        if not record:
            continue
        header, raw_path = record.split(b"\t", 1)
        mode, object_type, object_id = header.decode().split(" ", 2)
        entries.append(
            TreeEntry(
                mode=mode,
                object_type=object_type,
                object_id=object_id,
                path=raw_path.decode("utf-8", errors="surrogateescape"),
            )
        )
    return entries


def _system_version(repo_root: Path, commit: str) -> str:
    return _project_config_at(repo_root, commit).system_version


def _project_config_at(repo_root: Path, commit: str) -> ProjectConfig:
    content = _git(repo_root, "show", f"{commit}:career-os.toml")
    try:
        parsed = tomllib.loads(content.decode("utf-8"))
        return ProjectConfig.model_validate(parsed)
    except (UnicodeDecodeError, ValueError) as error:
        raise ValueError(f"{commit} has an invalid career-os.toml") from error


def _require_paths_clean(repo_root: Path, paths: list[str]) -> None:
    if not paths:
        return
    changed = set(paths)
    dirty = _dirty_paths(repo_root) & changed
    if dirty:
        raise ValueError(
            "downstream system paths have uncommitted changes: " + ", ".join(sorted(dirty))
        )


def _dirty_paths(repo_root: Path) -> set[str]:
    return set(
        _git_paths(repo_root, "diff", "--name-only", "-z")
        + _git_paths(repo_root, "diff", "--cached", "--name-only", "-z")
        + _git_paths(repo_root, "ls-files", "--others", "--exclude-standard", "-z")
    )


def _require_paths_match_tree(repo_root: Path, paths: list[str], treeish: str) -> None:
    if not paths:
        return
    temporary_parent = repo_root / ".career-os" / "tmp"
    temporary_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="downstream-worktree-", dir=temporary_parent
    ) as directory:
        index_path = Path(directory) / "index"
        environment = {"GIT_INDEX_FILE": str(index_path)}
        _git(repo_root, "read-tree", treeish, environment=environment)
        tracked_differences = _decode_paths(
            _git(
                repo_root,
                "diff",
                "--name-only",
                "-z",
                environment=environment,
            )
        )
        unexpected_files = _decode_paths(
            _git(
                repo_root,
                "ls-files",
                "--others",
                "--exclude-standard",
                "-z",
                environment=environment,
            )
        )
    differences = set(tracked_differences + unexpected_files) & set(paths)
    if differences:
        raise ValueError(
            "downstream system paths differ from the planned tree: "
            + ", ".join(sorted(differences))
        )


def _load_current_plan(plan_path: Path, project_root: Path) -> DownstreamSyncPlan:
    plan = load_downstream_sync_plan(plan_path)
    if plan.action != "downstream.sync":
        raise ValueError("plan action must be downstream.sync")
    if Path(plan.target_root).resolve() != project_root.resolve():
        raise ValueError("synchronization plan belongs to a different downstream root")
    return plan


def _verified_patch_path(plan: DownstreamSyncPlan, plan_path: Path) -> Path:
    if Path(plan.patch_file).name != plan.patch_file:
        raise ValueError("synchronization patch path must be beside the plan")
    patch_path = plan_path.resolve().parent / plan.patch_file
    if not patch_path.is_file():
        raise ValueError(f"synchronization patch is missing: {patch_path}")
    if _sha256_bytes(patch_path.read_bytes()) != plan.patch_sha256:
        raise ValueError("synchronization patch hash does not match the plan")
    return patch_path


def _require_target_head(repo_root: Path, expected: str) -> None:
    actual = _git_text(repo_root, "rev-parse", "HEAD")
    if actual != expected:
        raise ValueError("downstream HEAD changed after the synchronization plan was created")


def _require_git_root(repo_root: Path) -> None:
    actual = Path(_git_text(repo_root, "rev-parse", "--show-toplevel")).resolve()
    if actual != repo_root.resolve():
        raise ValueError(f"path is not a Git repository root: {repo_root}")


def _require_object_type(repo_root: Path, object_id: str, expected: str) -> None:
    try:
        actual = _git_text(repo_root, "cat-file", "-t", object_id)
    except ValueError as error:
        raise ValueError(f"Git object does not exist: {object_id}") from error
    if actual != expected:
        raise ValueError(f"Git object must be {expected}, found {actual}: {object_id}")


def _require_downstream_safety(
    project_root: Path, *, require_upstream: bool
) -> None:
    issues = inspect_downstream_git_safety(project_root, initialized=True)
    failures = [f"{issue.id}: {issue.detail}" for issue in issues if issue.status == "fail"]
    if failures:
        raise ValueError("downstream remote safety check failed: " + "; ".join(failures))
    if require_upstream:
        required = {
            issue.id: issue.status
            for issue in issues
            if issue.id in {"git.public-upstream-name", "git.public-upstream-push"}
        }
        if required != {
            "git.public-upstream-name": "pass",
            "git.public-upstream-push": "pass",
        }:
            details = ["canonical fetch-only upstream is not fully configured"]
            raise ValueError(
                "downstream remote safety check failed: " + "; ".join(details)
            )


def _require_no_git_operation(repo_root: Path) -> None:
    for marker in (
        "MERGE_HEAD",
        "CHERRY_PICK_HEAD",
        "REVERT_HEAD",
        "BISECT_LOG",
        "rebase-apply",
        "rebase-merge",
    ):
        raw = _git_text(repo_root, "rev-parse", "--git-path", marker)
        path = Path(raw)
        if not path.is_absolute():
            path = repo_root / path
        if path.exists():
            raise ValueError(f"cannot synchronize during an in-progress Git operation: {marker}")


def _require_isolated_sync_branch(repo_root: Path) -> str:
    try:
        branch = _git_text(repo_root, "symbolic-ref", "--quiet", "--short", "HEAD")
    except ValueError as error:
        raise ValueError(
            "downstream synchronization requires an isolated local branch; HEAD is detached"
        ) from error
    upstream = _git_text(
        repo_root,
        "for-each-ref",
        "--format=%(upstream:short)",
        f"refs/heads/{branch}",
    )
    if branch in _TRUNK_BRANCHES or upstream:
        detail = f"branch {branch!r}"
        if upstream:
            detail += f" tracks {upstream!r}"
        raise ValueError(
            "downstream synchronization requires an isolated non-trunk branch without an "
            f"upstream; {detail} is not isolated"
        )
    return branch


def _require_planned_branch(repo_root: Path, expected: str) -> None:
    actual = _require_isolated_sync_branch(repo_root)
    if actual != expected:
        raise ValueError(
            "downstream branch changed after the synchronization plan was created: "
            f"expected {expected!r}, found {actual!r}"
        )


def _git_paths(repo_root: Path, *arguments: str) -> list[str]:
    return _decode_paths(_git(repo_root, *arguments))


def _decode_paths(output: bytes) -> list[str]:
    return [
        item.decode("utf-8", errors="surrogateescape")
        for item in output.split(b"\0")
        if item
    ]


def _git_text(
    repo_root: Path,
    *arguments: str,
    environment: dict[str, str] | None = None,
) -> str:
    return _git(repo_root, *arguments, environment=environment).decode(
        "utf-8", errors="replace"
    ).strip()


def _git(
    repo_root: Path,
    *arguments: str,
    input_bytes: bytes | None = None,
    environment: dict[str, str] | None = None,
) -> bytes:
    command_environment = os.environ.copy()
    if environment:
        command_environment.update(environment)
    completed = subprocess.run(
        ["git", "-C", str(repo_root), *arguments],
        input=input_bytes,
        check=False,
        capture_output=True,
        env=command_environment,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        detail = stderr.splitlines()[-1] if stderr else f"exit {completed.returncode}"
        raise ValueError(f"git {arguments[0]} failed: {detail}")
    return completed.stdout


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _payload_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _rehash(plan: DownstreamSyncPlan) -> DownstreamSyncPlan:
    dumped = plan.model_dump(mode="json")
    dumped.pop("plan_sha256")
    return plan.model_copy(update={"plan_sha256": _payload_hash(dumped)})
