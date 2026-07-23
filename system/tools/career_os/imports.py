from __future__ import annotations

import fnmatch
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal, TypedDict
from uuid import UUID, uuid4

from pydantic import (
    UUID4,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

from career_os.config import ProjectPaths
from career_os.operations import FileOperation, OperationPlan, create_plan
from career_os.operations.models import SourceRoot
from career_os.operations.plans import sha256_file, sha256_text

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
_GIT_MODE_PATTERN = r"^[0-7]{6}$"

HashBasis = Literal["worktree-file", "git-symlink-payload", "gitlink-oid"]


class _TrackedEntry(TypedDict):
    source_path: str
    source_sha256: str
    source_size: int
    source_git_mode: str
    source_git_oid: str
    hash_basis: HashBasis


def _portable_relative_path(value: str) -> str:
    if not value or "\\" in value or any(character in value for character in "\x00\r\n"):
        raise ValueError("path must be a non-empty Vault-relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or value in {".", ".."} or ".." in path.parts:
        raise ValueError("path must not be absolute or escape its root")
    return value


def _portable_glob(value: str) -> str:
    if not value or "\\" in value or any(character in value for character in "\x00\r\n"):
        raise ValueError("pattern must be a non-empty portable POSIX glob")
    path = PurePosixPath(value)
    if path.is_absolute() or value in {".", ".."} or ".." in path.parts:
        raise ValueError("pattern must not be absolute or escape its root")
    return value


class LegacyInventoryRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    pattern: str
    asset_type: ImportAssetType
    disposition: ImportDisposition
    replacement: str | None = None
    note: str | None = None

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, value: str) -> str:
        return _portable_glob(value)

    @model_validator(mode="after")
    def validate_disposition_contract(self) -> LegacyInventoryRule:
        if self.disposition in {"replace-by-public", "upstream-gap"} and not self.replacement:
            raise ValueError(f"{self.disposition} requires replacement")
        return self


class LegacyInventoryRuleSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1, 2] = 1
    source_repository: str = Field(min_length=1)
    source_commit: str = Field(pattern=_COMMIT_PATTERN)
    rules: list[LegacyInventoryRule] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_rule_ids(self) -> LegacyInventoryRuleSet:
        rule_ids = [rule.id for rule in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("inventory rule IDs must be unique")
        return self


class LegacyMigrationInventoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    source_sha256: str = Field(pattern=_SHA256_PATTERN)
    source_size: int = Field(ge=0)
    source_git_mode: str = Field(pattern=_GIT_MODE_PATTERN)
    source_git_oid: str = Field(pattern=_COMMIT_PATTERN)
    hash_basis: HashBasis
    asset_type: ImportAssetType
    disposition: ImportDisposition
    rule_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    replacement: str | None = None
    note: str | None = None

    @field_validator("source_path")
    @classmethod
    def validate_source_path(cls, value: str) -> str:
        return _portable_relative_path(value)

    @model_validator(mode="after")
    def validate_disposition_contract(self) -> LegacyMigrationInventoryEntry:
        if self.disposition in {"replace-by-public", "upstream-gap"} and not self.replacement:
            raise ValueError(f"{self.disposition} requires replacement")
        return self


class LegacyMigrationInventory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    source_repository: str = Field(min_length=1)
    source_commit: str = Field(pattern=_COMMIT_PATTERN)
    rules_sha256: str = Field(pattern=_SHA256_PATTERN)
    entries: list[LegacyMigrationInventoryEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_sorted_paths(self) -> LegacyMigrationInventory:
        paths = [entry.source_path for entry in self.entries]
        if len(paths) != len(set(paths)):
            raise ValueError("inventory source paths must be unique")
        if paths != sorted(paths):
            raise ValueError("inventory source paths must be sorted")
        return self


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
    def validate_relative_path(cls, value: str) -> str:
        return _portable_relative_path(value)

    @model_validator(mode="after")
    def validate_disposition_contract(self) -> LegacyImportEntry:
        if self.disposition == "migrate-exact":
            if len(self.outputs) != 1:
                raise ValueError("migrate-exact requires exactly one output")
            output = self.outputs[0]
            if output.prepared_path is not None or output.prepared_sha256 is not None:
                raise ValueError("migrate-exact cannot define a prepared file")
        elif self.disposition == "migrate-transform":
            if not self.outputs:
                raise ValueError("migrate-transform requires at least one output")
            if any(
                output.prepared_path is None or output.prepared_sha256 is None
                for output in self.outputs
            ):
                raise ValueError(
                    "every migrate-transform output requires prepared_path and prepared_sha256"
                )
        else:
            if self.outputs:
                raise ValueError(f"{self.disposition} cannot define import outputs")
        if self.asset_type == "record" and any(
            output.target_id is None or output.target_kind is None for output in self.outputs
        ):
            raise ValueError("record outputs require target_id and target_kind")
        if self.disposition == "replace-by-public" and not self.replacement:
            raise ValueError("replace-by-public requires replacement")
        if self.disposition == "upstream-gap" and not self.replacement:
            raise ValueError("upstream-gap requires a gap identifier in replacement")
        return self


class LegacyImportManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    id: UUID4
    source_repository: str = Field(min_length=1)
    source_commit: str = Field(pattern=_COMMIT_PATTERN)
    provenance_path: str = ".provenance/resume-migration.json"
    entries: list[LegacyImportEntry] = Field(min_length=1)

    @field_validator("provenance_path")
    @classmethod
    def validate_provenance_path(cls, value: str) -> str:
        return _portable_relative_path(value)

    @model_validator(mode="after")
    def validate_unique_paths(self) -> LegacyImportManifest:
        sources = [entry.source_path for entry in self.entries]
        if len(sources) != len(set(sources)):
            raise ValueError("manifest source_path values must be unique")
        targets = [output.target_path for entry in self.entries for output in entry.outputs]
        if len(targets) != len(set(targets)):
            raise ValueError("manifest target_path values must be unique")
        if self.provenance_path in targets:
            raise ValueError("provenance_path cannot also be an import target")
        return self


class LegacyImportRetiredTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_path: str
    expected_sha256: str = Field(pattern=_SHA256_PATTERN)
    reason: str = Field(min_length=1)

    @field_validator("target_path")
    @classmethod
    def validate_target_path(cls, value: str) -> str:
        return _portable_relative_path(value)


class LegacyImportManifestV2(BaseModel):
    """Correction manifest that can supersede and retire prior outputs safely."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2]
    id: UUID4
    source_repository: str = Field(min_length=1)
    source_commit: str = Field(pattern=_COMMIT_PATTERN)
    provenance_path: str = ".provenance/resume-migration.json"
    supersedes_manifest_ids: list[UUID4] = Field(
        min_length=1, json_schema_extra={"uniqueItems": True}
    )
    entries: list[LegacyImportEntry] = Field(default_factory=list)
    retire_targets: list[LegacyImportRetiredTarget] = Field(default_factory=list)

    @field_validator("provenance_path")
    @classmethod
    def validate_provenance_path(cls, value: str) -> str:
        return _portable_relative_path(value)

    @model_validator(mode="after")
    def validate_correction_contract(self) -> LegacyImportManifestV2:
        if len(self.supersedes_manifest_ids) != len(set(self.supersedes_manifest_ids)):
            raise ValueError("supersedes_manifest_ids values must be unique")
        sources = [entry.source_path for entry in self.entries]
        if len(sources) != len(set(sources)):
            raise ValueError("manifest source_path values must be unique")
        imported = [output.target_path for entry in self.entries for output in entry.outputs]
        if len(imported) != len(set(imported)):
            raise ValueError("manifest target_path values must be unique")
        if self.provenance_path in imported:
            raise ValueError("provenance_path cannot also be an import target")
        retired = [target.target_path for target in self.retire_targets]
        if len(retired) != len(set(retired)):
            raise ValueError("retired target_path values must be unique")
        overlap = set(imported).intersection(retired)
        if overlap:
            raise ValueError(
                "a target path cannot be both imported and retired: " + ", ".join(sorted(overlap))
            )
        if self.provenance_path in retired:
            raise ValueError("provenance_path cannot also be a retired target")
        if not self.entries and not self.retire_targets:
            raise ValueError("a correction manifest requires entries or retire_targets")
        return self


type LoadedLegacyImportManifest = Annotated[
    LegacyImportManifest | LegacyImportManifestV2,
    Field(discriminator="schema_version"),
]
_IMPORT_MANIFEST_ADAPTER: TypeAdapter[LoadedLegacyImportManifest] = TypeAdapter(
    LoadedLegacyImportManifest
)


class MigrationProvenanceOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_path: str
    target_id: UUID4 | None = None
    target_kind: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9.-]*$")
    target_sha256: str = Field(pattern=_SHA256_PATTERN)

    @field_validator("target_path")
    @classmethod
    def validate_target_path(cls, value: str) -> str:
        return _portable_relative_path(value)

    @model_validator(mode="after")
    def validate_target_identity(self) -> MigrationProvenanceOutput:
        if (self.target_id is None) != (self.target_kind is None):
            raise ValueError("target_id and target_kind must be declared together")
        return self


class MigrationProvenanceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    source_sha256: str = Field(pattern=_SHA256_PATTERN)
    asset_type: ImportAssetType
    disposition: ImportDisposition
    outputs: list[MigrationProvenanceOutput] = Field(default_factory=list)
    replacement: str | None = None
    transformation_note: str | None = None
    verification: Literal["hash-checked-at-apply"] = "hash-checked-at-apply"


class MigrationProvenanceMap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    manifest_id: UUID4
    plan_id: UUID
    source_repository: str
    source_commit: str = Field(pattern=_COMMIT_PATTERN)
    entries: list[MigrationProvenanceEntry]


class MigrationProvenanceRetiredTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_path: str
    expected_sha256: str = Field(pattern=_SHA256_PATTERN)
    reason: str = Field(min_length=1)
    verification: Literal["hash-checked-at-apply"] = "hash-checked-at-apply"

    @field_validator("target_path")
    @classmethod
    def validate_target_path(cls, value: str) -> str:
        return _portable_relative_path(value)


class MigrationProvenanceMapV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = 2
    manifest_id: UUID4
    supersedes_manifest_ids: list[UUID4] = Field(
        min_length=1, json_schema_extra={"uniqueItems": True}
    )
    plan_id: UUID
    source_repository: str
    source_commit: str = Field(pattern=_COMMIT_PATTERN)
    entries: list[MigrationProvenanceEntry]
    retired_targets: list[MigrationProvenanceRetiredTarget]

    @model_validator(mode="after")
    def validate_unique_superseded_manifests(self) -> MigrationProvenanceMapV2:
        if len(self.supersedes_manifest_ids) != len(set(self.supersedes_manifest_ids)):
            raise ValueError("supersedes_manifest_ids values must be unique")
        return self


type LoadedMigrationProvenanceMap = Annotated[
    MigrationProvenanceMap | MigrationProvenanceMapV2,
    Field(discriminator="schema_version"),
]
_MIGRATION_PROVENANCE_ADAPTER: TypeAdapter[LoadedMigrationProvenanceMap] = TypeAdapter(
    LoadedMigrationProvenanceMap
)


def merge_reviewed_correction(
    *, migrated: Any, current: Any, corrected: Any, label: str
) -> Any:
    """Preserve post-migration edits unless they conflict with a reviewed correction."""

    if current in (migrated, corrected):
        return corrected
    if corrected == migrated:
        return current
    raise ValueError(f"semantic correction conflicts with a post-migration edit: {label}")


def import_manifest_json_schema() -> dict[str, Any]:
    schema = _IMPORT_MANIFEST_ADAPTER.json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://career-os.dev/schemas/legacy-import-manifest.schema.json"
    schema["title"] = "Career OS Legacy Import Manifest"
    return schema


def inventory_rules_json_schema() -> dict[str, Any]:
    schema = LegacyInventoryRuleSet.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://career-os.dev/schemas/legacy-inventory-rules.schema.json"
    schema["title"] = "Career OS Legacy Inventory Rules"
    return schema


def migration_inventory_json_schema() -> dict[str, Any]:
    schema = LegacyMigrationInventory.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://career-os.dev/schemas/legacy-migration-inventory.schema.json"
    schema["title"] = "Career OS Legacy Migration Inventory"
    return schema


def migration_provenance_json_schema() -> dict[str, Any]:
    schema = _MIGRATION_PROVENANCE_ADAPTER.json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://career-os.dev/schemas/migration-provenance.schema.json"
    schema["title"] = "Career OS Migration Provenance Map"
    return schema


def load_import_manifest(path: Path) -> LegacyImportManifest | LegacyImportManifestV2:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("import manifest must be a JSON object")
    schema_version = payload.get("schema_version", 1)
    if schema_version == 1:
        return LegacyImportManifest.model_validate(payload)
    if schema_version == 2:
        return LegacyImportManifestV2.model_validate(payload)
    raise ValueError(f"unsupported import manifest schema_version: {schema_version}")


def load_migration_provenance(
    path: Path,
) -> MigrationProvenanceMap | MigrationProvenanceMapV2:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("migration provenance must be a JSON object")
    schema_version = payload.get("schema_version", 1)
    if schema_version == 1:
        return MigrationProvenanceMap.model_validate(payload)
    if schema_version == 2:
        return MigrationProvenanceMapV2.model_validate(payload)
    raise ValueError(f"unsupported migration provenance schema_version: {schema_version}")


def load_inventory_rules(path: Path) -> LegacyInventoryRuleSet:
    return LegacyInventoryRuleSet.model_validate_json(path.read_text(encoding="utf-8"))


def load_migration_inventory(path: Path) -> LegacyMigrationInventory:
    return LegacyMigrationInventory.model_validate_json(path.read_text(encoding="utf-8"))


def create_migration_inventory(source_root: Path, rules_path: Path) -> LegacyMigrationInventory:
    source_root = source_root.resolve()
    rules_path = rules_path.resolve()
    rules = load_inventory_rules(rules_path)
    _verify_source_repository(source_root, rules.source_commit)
    entries: list[LegacyMigrationInventoryEntry] = []

    for tracked in _tracked_entries(source_root):
        rule = next(
            (
                candidate
                for candidate in rules.rules
                if _inventory_rule_matches(
                    tracked["source_path"], candidate.pattern, rules.schema_version
                )
            ),
            None,
        )
        if rule is None:
            raise ValueError(
                f"tracked source path has no inventory disposition: {tracked['source_path']}"
            )
        entries.append(
            LegacyMigrationInventoryEntry(
                **tracked,
                asset_type=rule.asset_type,
                disposition=rule.disposition,
                rule_id=rule.id,
                replacement=rule.replacement,
                note=rule.note,
            )
        )

    if not entries:
        raise ValueError("source repository has no tracked entries")
    return LegacyMigrationInventory(
        source_repository=rules.source_repository,
        source_commit=rules.source_commit,
        rules_sha256=_required_hash(sha256_file(rules_path), "inventory rules"),
        entries=entries,
    )


def verify_migration_inventory(
    source_root: Path, rules_path: Path, inventory_path: Path
) -> LegacyMigrationInventory:
    inventory = load_migration_inventory(inventory_path)
    expected = create_migration_inventory(source_root, rules_path)
    if inventory != expected:
        raise ValueError("migration inventory differs from the clean source repository or rules")
    return inventory


def _inventory_rule_matches(source_path: str, pattern: str, schema_version: int) -> bool:
    if schema_version == 1:
        return fnmatch.fnmatchcase(source_path, pattern)
    return _segment_glob_matches(source_path.split("/"), pattern.split("/"))


def _segment_glob_matches(path_parts: list[str], pattern_parts: list[str]) -> bool:
    """Match a v2 glob where only a complete ``**`` segment crosses ``/``."""

    memo: dict[tuple[int, int], bool] = {}

    def matches(path_index: int, pattern_index: int) -> bool:
        key = (path_index, pattern_index)
        if key in memo:
            return memo[key]
        if pattern_index == len(pattern_parts):
            result = path_index == len(path_parts)
        elif pattern_parts[pattern_index] == "**":
            result = matches(path_index, pattern_index + 1) or (
                path_index < len(path_parts) and matches(path_index + 1, pattern_index)
            )
        else:
            result = path_index < len(path_parts) and fnmatch.fnmatchcase(
                path_parts[path_index], pattern_parts[pattern_index]
            ) and matches(path_index + 1, pattern_index + 1)
        memo[key] = result
        return result

    return matches(0, 0)


def create_import_plan(
    paths: ProjectPaths, source_root: Path, manifest_path: Path
) -> OperationPlan:
    source_root = source_root.resolve()
    manifest_path = manifest_path.resolve()
    manifest = load_import_manifest(manifest_path)
    _verify_source_repository(source_root, manifest.source_commit)
    manifest_hash = _required_hash(sha256_file(manifest_path), "manifest")
    plan_id = uuid4()
    operations: list[FileOperation] = []
    provenance_entries: list[MigrationProvenanceEntry] = []
    provenance_retired_targets: list[MigrationProvenanceRetiredTarget] = []
    already_current = 0
    tracked_by_path = {item["source_path"]: item for item in _tracked_entries(source_root)}

    for entry in manifest.entries:
        tracked = _verify_manifest_source(entry, tracked_by_path)

        provenance_outputs: list[MigrationProvenanceOutput] = []
        if entry.disposition in {"migrate-exact", "migrate-transform"}:
            for output in entry.outputs:
                if entry.disposition == "migrate-exact":
                    if tracked["hash_basis"] != "worktree-file":
                        raise ValueError(
                            "migrate-exact supports only tracked regular files: "
                            f"{entry.source_path}"
                        )
                    copy_root: SourceRoot = "source"
                    copy_path = entry.source_path
                    desired_hash = entry.source_sha256
                else:
                    if output.prepared_path is None or output.prepared_sha256 is None:
                        raise ValueError("transformed output is missing its prepared file")
                    prepared = _resolve_within(paths.project_root, output.prepared_path, "prepared")
                    if sha256_file(prepared) != output.prepared_sha256:
                        raise ValueError(f"prepared file hash differs from manifest: {prepared}")
                    copy_root = "project"
                    copy_path = output.prepared_path
                    desired_hash = output.prepared_sha256

                target = _resolve_within(paths.data_root, output.target_path, "target")
                current_hash = sha256_file(target)
                if current_hash == desired_hash:
                    already_current += 1
                else:
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
                provenance_outputs.append(
                    MigrationProvenanceOutput(
                        target_path=output.target_path,
                        target_id=output.target_id,
                        target_kind=output.target_kind,
                        target_sha256=desired_hash,
                    )
                )

        provenance_entries.append(
            MigrationProvenanceEntry(
                source_path=entry.source_path,
                source_sha256=entry.source_sha256,
                asset_type=entry.asset_type,
                disposition=entry.disposition,
                outputs=provenance_outputs,
                replacement=entry.replacement,
                transformation_note=entry.transformation_note,
            )
        )

    if isinstance(manifest, LegacyImportManifestV2):
        for retired in manifest.retire_targets:
            target = _resolve_within(paths.data_root, retired.target_path, "retired target")
            current_hash = sha256_file(target)
            if current_hash != retired.expected_sha256:
                raise ValueError(
                    "retired target hash differs from manifest: "
                    f"{retired.target_path} (expected {retired.expected_sha256}, "
                    f"found {current_hash or 'missing'})"
                )
            operations.append(
                FileOperation(
                    op="delete",
                    root="data",
                    path=retired.target_path,
                    expected_sha256=retired.expected_sha256,
                )
            )
            provenance_retired_targets.append(
                MigrationProvenanceRetiredTarget(
                    target_path=retired.target_path,
                    expected_sha256=retired.expected_sha256,
                    reason=retired.reason,
                )
            )

        provenance: MigrationProvenanceMap | MigrationProvenanceMapV2 = (
            MigrationProvenanceMapV2(
                manifest_id=manifest.id,
                supersedes_manifest_ids=manifest.supersedes_manifest_ids,
                plan_id=plan_id,
                source_repository=manifest.source_repository,
                source_commit=manifest.source_commit,
                entries=provenance_entries,
                retired_targets=provenance_retired_targets,
            )
        )
    else:
        provenance = MigrationProvenanceMap(
            manifest_id=manifest.id,
            plan_id=plan_id,
            source_repository=manifest.source_repository,
            source_commit=manifest.source_commit,
            entries=provenance_entries,
        )
    provenance_content = (
        json.dumps(provenance.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    )
    provenance_target = _resolve_within(paths.data_root, manifest.provenance_path, "provenance")
    provenance_hash = sha256_text(provenance_content)
    if sha256_file(provenance_target) != provenance_hash:
        operations.append(
            FileOperation(
                op="write_text",
                root="data",
                path=manifest.provenance_path,
                expected_sha256=sha256_file(provenance_target),
                result_sha256=provenance_hash,
                content=provenance_content,
            )
        )

    metadata = {
        "manifest": str(manifest_path),
        "manifest_id": str(manifest.id),
        "manifest_sha256": manifest_hash,
        "source_commit": manifest.source_commit,
        "source_repository": manifest.source_repository,
        "provenance_path": manifest.provenance_path,
        "entries": str(len(manifest.entries)),
        "outputs": str(sum(len(entry.outputs) for entry in manifest.entries)),
        "already_current": str(already_current),
    }
    if isinstance(manifest, LegacyImportManifestV2):
        metadata.update(
            {
                "manifest_schema_version": "2",
                "supersedes_manifest_ids": ",".join(
                    str(manifest_id) for manifest_id in manifest.supersedes_manifest_ids
                ),
                "retired_targets": str(len(manifest.retire_targets)),
            }
        )

    return create_plan(
        action="import",
        source_version=f"git:{manifest.source_commit}",
        target_version="career-os:record-schema-2",
        roots={
            "project": paths.project_root,
            "data": paths.data_root,
            "source": source_root,
        },
        metadata=metadata,
        operations=operations,
        plan_id=plan_id,
    )


def verify_import_plan(
    plan: OperationPlan,
) -> LegacyImportManifest | LegacyImportManifestV2:
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
    tracked_by_path = {item["source_path"]: item for item in _tracked_entries(source_root)}
    for entry in manifest.entries:
        tracked = _verify_manifest_source(entry, tracked_by_path)
        if entry.disposition == "migrate-exact" and tracked["hash_basis"] != "worktree-file":
            raise ValueError(
                f"migrate-exact source changed to a non-regular entry: {entry.source_path}"
            )
        if entry.disposition == "migrate-transform":
            project_root = Path(plan.roots.get("project", "")).resolve()
            for output in entry.outputs:
                if output.prepared_path is None or output.prepared_sha256 is None:
                    raise ValueError("transformed output is missing its prepared file")
                prepared = _resolve_within(project_root, output.prepared_path, "prepared")
                if sha256_file(prepared) != output.prepared_sha256:
                    raise ValueError(f"prepared file changed after planning: {prepared}")
    if isinstance(manifest, LegacyImportManifestV2):
        data_root = Path(plan.roots.get("data", "")).resolve()
        for retired in manifest.retire_targets:
            target = _resolve_within(data_root, retired.target_path, "retired target")
            if sha256_file(target) != retired.expected_sha256:
                raise ValueError(f"retired target changed after planning: {target}")
    return manifest


def _verify_source_repository(source_root: Path, source_commit: str) -> None:
    if not source_root.is_dir():
        raise ValueError(f"source root does not exist: {source_root}")
    top_level = _git(source_root, "rev-parse", "--show-toplevel")
    if Path(top_level).resolve() != source_root:
        raise ValueError("source root must be the Git repository root")
    head = _git(source_root, "rev-parse", "HEAD")
    if head != source_commit:
        raise ValueError(f"source repository HEAD is {head}; input requires {source_commit}")
    status = _git(source_root, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise ValueError("source repository must be clean before planning or applying an import")


def _git(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f"cannot inspect source Git repository: {error}") from error
    return completed.stdout.strip()


def _git_bytes(root: Path, *args: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f"cannot inspect source Git repository: {error}") from error
    return completed.stdout


def _tracked_entries(source_root: Path) -> list[_TrackedEntry]:
    raw = _git_bytes(source_root, "ls-files", "--stage", "-z")
    entries: list[_TrackedEntry] = []
    for record in raw.split(b"\x00"):
        if not record:
            continue
        try:
            metadata, path_bytes = record.split(b"\t", 1)
            mode_bytes, oid_bytes, stage_bytes = metadata.split(b" ", 2)
            source_path = path_bytes.decode("utf-8")
            source_git_mode = mode_bytes.decode("ascii")
            source_git_oid = oid_bytes.decode("ascii")
            stage = stage_bytes.decode("ascii")
        except (UnicodeDecodeError, ValueError) as error:
            raise ValueError("source Git index contains an unsupported entry") from error
        _portable_relative_path(source_path)
        if stage != "0":
            raise ValueError(f"source Git index has an unmerged entry: {source_path}")

        if source_git_mode in {"100644", "100755"}:
            source = source_root.joinpath(*PurePosixPath(source_path).parts)
            if source.is_symlink() or not source.is_file():
                raise ValueError(
                    f"tracked source file is missing or has changed type: {source_path}"
                )
            source_sha256 = _required_hash(sha256_file(source), "tracked source")
            source_size = source.stat().st_size
            hash_basis: HashBasis = "worktree-file"
        elif source_git_mode == "120000":
            payload = _git_bytes(source_root, "cat-file", "blob", source_git_oid)
            source_sha256 = hashlib.sha256(payload).hexdigest()
            source_size = len(payload)
            hash_basis = "git-symlink-payload"
        elif source_git_mode == "160000":
            payload = source_git_oid.encode("ascii")
            source_sha256 = hashlib.sha256(payload).hexdigest()
            source_size = len(payload)
            hash_basis = "gitlink-oid"
        else:
            raise ValueError(
                f"source Git index mode is unsupported: {source_git_mode} {source_path}"
            )

        entries.append(
            {
                "source_path": source_path,
                "source_sha256": source_sha256,
                "source_size": source_size,
                "source_git_mode": source_git_mode,
                "source_git_oid": source_git_oid,
                "hash_basis": hash_basis,
            }
        )
    return sorted(entries, key=lambda entry: entry["source_path"])


def _verify_manifest_source(
    entry: LegacyImportEntry, tracked_by_path: dict[str, _TrackedEntry]
) -> _TrackedEntry:
    tracked = tracked_by_path.get(entry.source_path)
    if tracked is None:
        raise ValueError(f"source path is not tracked at the required commit: {entry.source_path}")
    if tracked["source_sha256"] != entry.source_sha256:
        raise ValueError(f"source hash differs from manifest: {entry.source_path}")
    return tracked


def _resolve_within(root: Path, relative: str, label: str) -> Path:
    portable = PurePosixPath(_portable_relative_path(relative))
    root = root.resolve()
    resolved = root.joinpath(*portable.parts).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"{label} path escapes its root: {relative}")
    if label in {"source", "prepared"} and not resolved.is_file():
        raise ValueError(f"{label} file is missing: {resolved}")
    return resolved


def _required_hash(value: str | None, label: str) -> str:
    if value is None:
        raise ValueError(f"{label} hash is missing")
    return value
