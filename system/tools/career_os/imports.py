from __future__ import annotations

import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Literal
from uuid import uuid4

from pydantic import UUID4, BaseModel, ConfigDict, Field, field_validator, model_validator

from career_os.config import ProjectPaths
from career_os.operations import FileOperation, OperationPlan, create_plan
from career_os.operations.models import SourceRoot
from career_os.operations.plans import sha256_file

ImportDisposition = Literal[
    "migrate-exact",
    "migrate-transform",
    "replace-by-public",
    "retain-archive-only",
    "upstream-gap",
    "retire",
]
ImportAssetType = Literal[
    "record",
    "attachment",
    "resume",
    "view",
    "skill",
    "tool",
    "documentation",
    "other",
]

_SHA256_PATTERN = r"^[a-f0-9]{64}$"
_COMMIT_PATTERN = r"^[a-f0-9]{40}$"


def _portable_relative_path(value: str) -> str:
    if not value or "\\" in value or any(character in value for character in "\x00\r\n"):
        raise ValueError("path must be a non-empty relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or value in {".", ".."} or ".." in path.parts:
        raise ValueError("path must not be absolute or escape its root")
    return value


class LegacyImportOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_path: str
    target_id: UUID4 | None = None
    target_kind: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9.-]*$")
    prepared_path: str | None = None
    prepared_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)

    @field_validator("target_path", "prepared_path")
    @classmethod
    def validate_relative_path(cls, value: str | None) -> str | None:
        return None if value is None else _portable_relative_path(value)

    @model_validator(mode="after")
    def validate_target_identity(self) -> LegacyImportOutput:
        if (self.target_id is None) != (self.target_kind is None):
            raise ValueError("target_id and target_kind must be declared together")
        return self


class LegacyImportEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    source_sha256: str = Field(pattern=_SHA256_PATTERN)
    asset_type: ImportAssetType
    disposition: ImportDisposition
    outputs: list[LegacyImportOutput] = Field(default_factory=list)
    replacement: str | None = None
    transformation_note: str | None = None

    @field_validator("source_path")
    @classmethod
    def validate_source_path(cls, value: str) -> str:
        return _portable_relative_path(value)

    @model_validator(mode="after")
    def validate_disposition(self) -> LegacyImportEntry:
        if self.disposition == "migrate-exact":
            if len(self.outputs) != 1:
                raise ValueError("migrate-exact requires exactly one output")
            if self.outputs[0].prepared_path is not None:
                raise ValueError("migrate-exact cannot define a prepared file")
        elif self.disposition == "migrate-transform":
            if not self.outputs or any(
                output.prepared_path is None or output.prepared_sha256 is None
                for output in self.outputs
            ):
                raise ValueError(
                    "migrate-transform requires prepared_path and prepared_sha256 outputs"
                )
        elif self.outputs:
            raise ValueError(f"{self.disposition} cannot define import outputs")
        if self.asset_type == "record" and any(
            output.target_id is None or output.target_kind is None for output in self.outputs
        ):
            raise ValueError("record outputs require target_id and target_kind")
        if self.disposition in {"replace-by-public", "upstream-gap"} and not self.replacement:
            raise ValueError(f"{self.disposition} requires replacement")
        return self


class LegacyImportManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    id: UUID4
    source_repository: str = Field(min_length=1)
    source_commit: str = Field(pattern=_COMMIT_PATTERN)
    entries: list[LegacyImportEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_paths(self) -> LegacyImportManifest:
        sources = [entry.source_path for entry in self.entries]
        targets = [output.target_path for entry in self.entries for output in entry.outputs]
        if len(sources) != len(set(sources)):
            raise ValueError("manifest source_path values must be unique")
        if len(targets) != len(set(targets)):
            raise ValueError("manifest target_path values must be unique")
        return self


def import_manifest_json_schema() -> dict[str, Any]:
    schema = LegacyImportManifest.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://career-os.dev/schemas/legacy-import-manifest.schema.json"
    schema["title"] = "Career OS Legacy Import Manifest"
    return schema


def load_import_manifest(path: Path) -> LegacyImportManifest:
    return LegacyImportManifest.model_validate_json(path.read_text(encoding="utf-8"))


def create_import_plan(
    paths: ProjectPaths, source_root: Path, manifest_path: Path
) -> OperationPlan:
    source_root = source_root.resolve()
    manifest_path = manifest_path.resolve()
    manifest = load_import_manifest(manifest_path)
    _verify_source_repository(source_root, manifest.source_commit)
    manifest_hash = _required_hash(sha256_file(manifest_path), "manifest")
    operations: list[FileOperation] = []
    already_current = 0

    for entry in manifest.entries:
        source = _resolve_within(source_root, entry.source_path, "source")
        if sha256_file(source) != entry.source_sha256:
            raise ValueError(f"source hash differs from manifest: {entry.source_path}")
        if entry.disposition not in {"migrate-exact", "migrate-transform"}:
            continue
        for output in entry.outputs:
            if entry.disposition == "migrate-exact":
                copy_root: SourceRoot = "source"
                copy_path = entry.source_path
                desired_hash = entry.source_sha256
            else:
                assert output.prepared_path is not None
                assert output.prepared_sha256 is not None
                prepared = _resolve_within(
                    paths.project_root, output.prepared_path, "prepared"
                )
                if sha256_file(prepared) != output.prepared_sha256:
                    raise ValueError(f"prepared file hash differs from manifest: {prepared}")
                copy_root = "project"
                copy_path = output.prepared_path
                desired_hash = output.prepared_sha256
            target = _resolve_within(paths.data_root, output.target_path, "target")
            current_hash = sha256_file(target)
            if current_hash == desired_hash:
                already_current += 1
                continue
            operations.append(
                FileOperation(
                    op="copy_file",
                    root="data",
                    path=output.target_path,
                    expected_sha256=current_hash,
                    result_sha256=desired_hash,
                    source_root=copy_root,
                    source_path=copy_path,
                    source_sha256=desired_hash,
                )
            )

    return create_plan(
        action="import",
        source_version=f"git:{manifest.source_commit}",
        target_version="career-os:record-schema-3",
        roots={
            "project": paths.project_root,
            "data": paths.data_root,
            "source": source_root,
        },
        metadata={
            "manifest": str(manifest_path),
            "manifest_id": str(manifest.id),
            "manifest_sha256": manifest_hash,
            "source_commit": manifest.source_commit,
            "source_repository": manifest.source_repository,
            "entries": str(len(manifest.entries)),
            "outputs": str(sum(len(entry.outputs) for entry in manifest.entries)),
            "already_current": str(already_current),
        },
        operations=operations,
        plan_id=uuid4(),
    )


def verify_import_plan(plan: OperationPlan) -> LegacyImportManifest:
    if plan.action != "import":
        raise ValueError("plan action must be import")
    manifest_name = plan.metadata.get("manifest")
    expected_hash = plan.metadata.get("manifest_sha256")
    if not manifest_name or not expected_hash:
        raise ValueError("import plan is missing manifest metadata")
    manifest_path = Path(manifest_name).resolve()
    if sha256_file(manifest_path) != expected_hash:
        raise ValueError("import manifest changed after planning")
    manifest = load_import_manifest(manifest_path)
    if str(manifest.id) != plan.metadata.get("manifest_id"):
        raise ValueError("import manifest identity differs from the plan")
    source_root = Path(plan.roots.get("source", "")).resolve()
    _verify_source_repository(source_root, manifest.source_commit)
    for entry in manifest.entries:
        source = _resolve_within(source_root, entry.source_path, "source")
        if sha256_file(source) != entry.source_sha256:
            raise ValueError(f"source changed after planning: {entry.source_path}")
        for output in entry.outputs:
            if output.prepared_path is None:
                continue
            prepared = _resolve_within(
                Path(plan.roots["project"]), output.prepared_path, "prepared"
            )
            if sha256_file(prepared) != output.prepared_sha256:
                raise ValueError(f"prepared file changed after planning: {prepared}")
    return manifest


def _verify_source_repository(source_root: Path, source_commit: str) -> None:
    if not (source_root / ".git").exists():
        raise ValueError(f"legacy source is not a Git repository: {source_root}")
    head = _git(source_root, "rev-parse", "HEAD")
    if head != source_commit:
        raise ValueError(f"legacy source HEAD is {head}; manifest expects {source_commit}")
    if _git(source_root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ValueError("legacy source repository must be clean")


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise ValueError(completed.stderr.strip() or "Git command failed")
    return completed.stdout.strip()


def _resolve_within(root: Path, relative: str, label: str) -> Path:
    root = root.resolve()
    path = PurePosixPath(_portable_relative_path(relative))
    target = root.joinpath(*path.parts).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"{label} path escapes its root: {relative}")
    return target


def _required_hash(value: str | None, label: str) -> str:
    if value is None:
        raise ValueError(f"{label} hash is missing")
    return value
