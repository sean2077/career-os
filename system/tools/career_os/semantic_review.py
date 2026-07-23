from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import UUID4, BaseModel, ConfigDict, Field, field_validator, model_validator
from ruamel.yaml import YAML

from career_os.config import ProjectPaths
from career_os.imports import (
    HashBasis,
    ImportAssetType,
    ImportDisposition,
    LegacyImportManifestV2,
    LegacyMigrationInventoryEntry,
    MigrationProvenanceMapV2,
    load_import_manifest,
    load_migration_inventory,
    load_migration_provenance,
    verify_migration_inventory,
)
from career_os.operations.plans import sha256_file

_SHA256_PATTERN = r"^[a-f0-9]{64}$"
_COMMIT_PATTERN = r"^[a-f0-9]{40}$"
_GIT_MODE_PATTERN = r"^[0-7]{6}$"
_ID_PATTERN = r"^[a-z0-9][a-z0-9._-]*$"
_ANCHOR_PATTERN = re.compile(r"^#(?:\^[A-Za-z0-9][A-Za-z0-9_-]*|[^#\r\n].*)$")
_BLOCK_ID_PATTERN = re.compile(r"(?:^|\s)\^([A-Za-z0-9][A-Za-z0-9_-]*)\s*$")
_HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+?)(?:\s+#+)?\s*$")
_yaml = YAML(typ="safe")

TargetScope = Literal["public-framework", "personal-instance"]
BehaviorFamily = Literal[
    "domain-workflow",
    "cross-authority-guard",
    "host-adapter",
    "platform-operation",
]
CareerDomain = Literal[
    "career-evidence",
    "career-strategy",
    "role-market",
    "opportunity-decision",
    "career-outlook",
    "capability-readiness",
    "career-communication",
]
ReviewStatus = Literal["open", "closed"]

_REQUIRED_BEHAVIOR_FAMILIES = {
    "domain-workflow",
    "cross-authority-guard",
    "host-adapter",
    "platform-operation",
}
_REQUIRED_CAREER_DOMAINS = {
    "career-evidence",
    "career-strategy",
    "role-market",
    "opportunity-decision",
    "career-outlook",
    "capability-readiness",
    "career-communication",
}


def _portable_relative_path(value: str) -> str:
    if not value or "\\" in value or any(character in value for character in "\x00\r\n"):
        raise ValueError("path must be a non-empty root-relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or value in {".", ".."} or ".." in path.parts:
        raise ValueError("path must not be absolute or escape its root")
    return value


class SemanticTargetReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: TargetScope
    path: str
    anchor: str | None = None
    relation: str = Field(min_length=1)
    target_id: str | None = Field(default=None, pattern=_ID_PATTERN + r"|^[a-f0-9-]{36}$")
    target_kind: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9.-]*$")
    target_status: str | None = Field(default=None, min_length=1)
    authority: CareerDomain | None = None
    lifecycle_id: str | None = Field(default=None, min_length=1)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _portable_relative_path(value)

    @field_validator("anchor")
    @classmethod
    def validate_anchor(cls, value: str | None) -> str | None:
        if value is not None and not _ANCHOR_PATTERN.fullmatch(value):
            raise ValueError("anchor must be an Obsidian heading or block anchor")
        return value

    @model_validator(mode="after")
    def validate_record_identity(self) -> SemanticTargetReference:
        record_identity = (self.target_id, self.target_kind, self.target_status)
        if any(value is not None for value in record_identity) and any(
            value is None for value in record_identity
        ):
            raise ValueError(
                "record target identity requires target_id, target_kind, and target_status together"
            )
        if self.target_id is not None and (
            self.authority is None or self.lifecycle_id is None
        ):
            raise ValueError("record target identity requires authority and lifecycle_id")
        return self


class SemanticReviewEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: TargetScope
    path: str
    anchor: str | None = None
    kind: Literal[
        "target",
        "outcome-test",
        "schema",
        "validator",
        "scenario",
        "archive",
        "retirement",
    ]
    assertion: str = Field(min_length=1)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _portable_relative_path(value)

    @field_validator("anchor")
    @classmethod
    def validate_anchor(cls, value: str | None) -> str | None:
        if value is not None and not _ANCHOR_PATTERN.fullmatch(value):
            raise ValueError("anchor must be an Obsidian heading or block anchor")
        return value


class OutcomeContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_result: str = Field(min_length=1)
    canonical_authority: str = Field(min_length=1)
    lifecycle: str = Field(min_length=1)
    references: str = Field(min_length=1)
    safety: str = Field(min_length=1)
    authorization: str = Field(min_length=1)


class RetirementEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1)
    unique_semantics_proof: str = Field(min_length=1)
    archive_locator: str | None = Field(default=None, min_length=1)


class SemanticGap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=_ID_PATTERN)
    material: bool
    status: Literal["open", "closed"]
    description: str = Field(min_length=1)
    resolution: str | None = Field(default=None, min_length=1)
    evidence: list[SemanticReviewEvidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_resolution(self) -> SemanticGap:
        if self.status == "closed" and (self.resolution is None or not self.evidence):
            raise ValueError("a closed gap requires a resolution and evidence")
        if self.status == "open" and self.resolution is not None:
            raise ValueError("an open gap cannot claim a resolution")
        return self


class SemanticBehaviorScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=_ID_PATTERN)
    family: BehaviorFamily
    career_domain: CareerDomain | None = None
    success_outcome: str = Field(min_length=1)
    failure_closure: str = Field(min_length=1)
    forbidden_inferences: list[str] = Field(min_length=1)
    forbidden_external_actions: list[str] = Field(min_length=1)
    evidence: list[SemanticReviewEvidence] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_domain(self) -> SemanticBehaviorScenario:
        if (self.family == "domain-workflow") != (self.career_domain is not None):
            raise ValueError("only domain-workflow scenarios declare career_domain")
        return self


class SemanticFileReviewEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    source_sha256: str = Field(pattern=_SHA256_PATTERN)
    source_size: int = Field(ge=0)
    source_git_mode: str = Field(pattern=_GIT_MODE_PATTERN)
    source_git_oid: str = Field(pattern=_COMMIT_PATTERN)
    hash_basis: HashBasis
    asset_type: ImportAssetType
    disposition: ImportDisposition
    rule_id: str = Field(pattern=_ID_PATTERN)
    replacement: str | None = None
    note: str | None = None
    target_refs: list[SemanticTargetReference] = Field(min_length=1)
    behavior_families: list[BehaviorFamily] = Field(min_length=1)
    career_domains: list[CareerDomain] = Field(default_factory=list)
    outcome_contracts: list[OutcomeContract] = Field(min_length=1)
    evidence: list[SemanticReviewEvidence] = Field(min_length=1)
    scenario_ids: list[str] = Field(min_length=1)
    review_status: ReviewStatus
    gap_ids: list[str] = Field(default_factory=list)
    retirement: RetirementEvidence | None = None
    notes: str | None = None

    @field_validator("source_path")
    @classmethod
    def validate_source_path(cls, value: str) -> str:
        return _portable_relative_path(value)

    @field_validator("behavior_families", "career_domains", "scenario_ids", "gap_ids")
    @classmethod
    def validate_unique_lists(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("review classification lists must contain unique values")
        return value

    @model_validator(mode="after")
    def validate_review_contract(self) -> SemanticFileReviewEntry:
        if ("domain-workflow" in self.behavior_families) != bool(self.career_domains):
            raise ValueError("domain-workflow reviews require one or more career_domains")
        if self.review_status == "closed" and self.gap_ids:
            raise ValueError("a closed file review cannot retain gap_ids")
        if self.disposition == "upstream-gap" and self.review_status == "closed":
            raise ValueError("an upstream-gap disposition cannot be closed")
        if self.disposition == "replace-by-public":
            if any(ref.scope != "public-framework" for ref in self.target_refs):
                raise ValueError("replace-by-public targets must be public-framework files")
            if not any(item.scope == "public-framework" for item in self.evidence):
                raise ValueError("replace-by-public requires standalone public evidence")
            if not any(item.kind == "outcome-test" for item in self.evidence):
                raise ValueError("replace-by-public requires a standalone public outcome test")
        if self.disposition in {"migrate-exact", "migrate-transform"}:
            if not any(ref.scope == "personal-instance" for ref in self.target_refs):
                raise ValueError("migrated assets must retain a personal-instance target")
            public_targets = [
                ref for ref in self.target_refs if ref.scope == "public-framework"
            ]
            if public_targets and not any(
                item.scope == "public-framework" and item.kind == "outcome-test"
                for item in self.evidence
            ):
                raise ValueError(
                    "a migrated asset with public framework targets requires a public outcome test"
                )
        if self.disposition == "migrate-exact" and len(self.target_refs) != 1:
            raise ValueError("migrate-exact requires exactly one target reference")
        if self.disposition in {"retain-archive-only", "retire"}:
            if self.retirement is None:
                raise ValueError(f"{self.disposition} requires retirement evidence")
            if self.disposition == "retain-archive-only" and not self.retirement.archive_locator:
                raise ValueError("retain-archive-only requires an archive_locator")
            if not any(item.kind in {"archive", "retirement"} for item in self.evidence):
                raise ValueError("retired and archive-only reviews require explicit evidence")
        elif self.retirement is not None:
            raise ValueError("retirement evidence is valid only for archive-only or retired assets")
        if len(self.target_refs) > 1:
            if any(
                ref.authority is None or ref.lifecycle_id is None for ref in self.target_refs
            ):
                raise ValueError(
                    "one-to-many target mappings require explicit authority and lifecycle identity"
                )
            lifecycle_keys = [
                (ref.authority, ref.target_kind or "artifact", ref.lifecycle_id)
                for ref in self.target_refs
            ]
            if len(lifecycle_keys) != len(set(lifecycle_keys)):
                raise ValueError(
                    "one-to-many targets must differ by authority, kind, or independent lifecycle"
                )
        return self

    def inventory_identity(self) -> tuple[Any, ...]:
        return (
            self.source_path,
            self.source_sha256,
            self.source_size,
            self.source_git_mode,
            self.source_git_oid,
            self.hash_basis,
            self.asset_type,
            self.disposition,
            self.rule_id,
            self.replacement,
            self.note,
        )


class SemanticFileReviewControl(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    control_type: Literal["semantic-file-review"] = "semantic-file-review"
    source_repository: str = Field(min_length=1)
    source_commit: str = Field(pattern=_COMMIT_PATTERN)
    inventory_path: str
    inventory_sha256: str = Field(pattern=_SHA256_PATTERN)
    expected_source_assets: int = Field(ge=1)
    scenarios: list[SemanticBehaviorScenario] = Field(min_length=1)
    residual_gaps: list[SemanticGap] = Field(default_factory=list)
    entries: list[SemanticFileReviewEntry] = Field(min_length=1)

    @field_validator("inventory_path")
    @classmethod
    def validate_inventory_path(cls, value: str) -> str:
        return _portable_relative_path(value)

    @model_validator(mode="after")
    def validate_control(self) -> SemanticFileReviewControl:
        paths = [entry.source_path for entry in self.entries]
        if len(paths) != len(set(paths)):
            raise ValueError("source file reviews must be unique")
        if paths != sorted(paths):
            raise ValueError("source file reviews must be sorted by source_path")
        if len(self.entries) != self.expected_source_assets:
            raise ValueError("expected_source_assets must equal the number of file reviews")
        scenario_ids = [scenario.id for scenario in self.scenarios]
        if len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("behavior scenario IDs must be unique")
        scenario_families = {scenario.family for scenario in self.scenarios}
        if scenario_families != _REQUIRED_BEHAVIOR_FAMILIES:
            raise ValueError("behavior scenarios must cover all four behavior families")
        scenario_domains = {
            scenario.career_domain
            for scenario in self.scenarios
            if scenario.career_domain is not None
        }
        if scenario_domains != _REQUIRED_CAREER_DOMAINS:
            raise ValueError("domain scenarios must cover all seven Career authorities")
        known_scenarios = set(scenario_ids)
        scenario_by_id = {scenario.id: scenario for scenario in self.scenarios}
        for entry in self.entries:
            unknown = set(entry.scenario_ids) - known_scenarios
            if unknown:
                raise ValueError(
                    f"file review references unknown scenarios: {entry.source_path}: "
                    + ", ".join(sorted(unknown))
                )
            referenced = [scenario_by_id[scenario_id] for scenario_id in entry.scenario_ids]
            referenced_families = {scenario.family for scenario in referenced}
            missing_families = set(entry.behavior_families) - referenced_families
            if missing_families:
                raise ValueError(
                    f"file review lacks scenarios for its behavior families: "
                    f"{entry.source_path}: {', '.join(sorted(missing_families))}"
                )
            referenced_domains = {
                scenario.career_domain
                for scenario in referenced
                if scenario.career_domain is not None
            }
            missing_domains = set(entry.career_domains) - referenced_domains
            if missing_domains:
                raise ValueError(
                    f"file review lacks scenarios for its Career authorities: "
                    f"{entry.source_path}: {', '.join(sorted(missing_domains))}"
                )
        gap_ids = [gap.id for gap in self.residual_gaps]
        if len(gap_ids) != len(set(gap_ids)):
            raise ValueError("residual gap IDs must be unique")
        known_gaps = set(gap_ids)
        for entry in self.entries:
            unknown = set(entry.gap_ids) - known_gaps
            if unknown:
                raise ValueError(
                    f"file review references unknown residual gaps: {entry.source_path}: "
                    + ", ".join(sorted(unknown))
                )
        return self


class SemanticValidationRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=_ID_PATTERN)
    scope: Literal["public-framework", "personal-instance", "host"]
    command: str = Field(min_length=1)
    status: Literal["passed"]
    result_path: str
    result_sha256: str = Field(pattern=_SHA256_PATTERN)
    verified_at: datetime

    @field_validator("result_path")
    @classmethod
    def validate_result_path(cls, value: str) -> str:
        return _portable_relative_path(value)

    @field_validator("verified_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("validation timestamps require a timezone")
        return value


class SemanticReviewRound(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lens: Literal["source-to-target", "target-to-source-adversarial"]
    report_path: str
    report_sha256: str = Field(pattern=_SHA256_PATTERN)
    reviewed_items: int = Field(ge=1)
    new_material_gaps: Literal[0] = 0
    reviewed_at: datetime

    @field_validator("report_path")
    @classmethod
    def validate_report_path(cls, value: str) -> str:
        return _portable_relative_path(value)

    @field_validator("reviewed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("review timestamps require a timezone")
        return value


class SemanticDownstreamSyncEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_tag: str = Field(min_length=1)
    tag_object: str = Field(pattern=_COMMIT_PATTERN)
    source_commit: str = Field(pattern=_COMMIT_PATTERN)
    target_branch: str = Field(min_length=1)
    target_head: str = Field(pattern=_COMMIT_PATTERN)
    desired_tree: str = Field(pattern=_COMMIT_PATTERN)
    plan_sha256: str = Field(pattern=_SHA256_PATTERN)
    patch_sha256: str = Field(pattern=_SHA256_PATTERN)
    result_path: str
    result_sha256: str = Field(pattern=_SHA256_PATTERN)
    applied_at: datetime
    validated_at: datetime

    @field_validator("source_tag", "target_branch")
    @classmethod
    def validate_names(cls, value: str) -> str:
        if value != value.strip() or any(character.isspace() for character in value):
            raise ValueError("tag and branch names must be exact and contain no whitespace")
        return value

    @field_validator("result_path")
    @classmethod
    def validate_result_path(cls, value: str) -> str:
        return _portable_relative_path(value)

    @field_validator("applied_at", "validated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("downstream synchronization timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def validate_timeline(self) -> SemanticDownstreamSyncEvidence:
        if self.validated_at < self.applied_at:
            raise ValueError("downstream validation cannot precede apply")
        return self


class SemanticReviewCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = 2
    control_type: Literal["semantic-review-completion"] = "semantic-review-completion"
    development_topology: Literal["integrated-workbench", "split-downstream"]
    status: Literal["local-candidate-complete", "complete"]
    source_repository: str = Field(min_length=1)
    source_commit: str = Field(pattern=_COMMIT_PATTERN)
    inventory_path: str
    inventory_sha256: str = Field(pattern=_SHA256_PATTERN)
    review_path: str
    review_sha256: str = Field(pattern=_SHA256_PATTERN)
    framework_target_commit: str = Field(pattern=_COMMIT_PATTERN)
    personal_target_commit: str = Field(pattern=_COMMIT_PATTERN)
    target_tree_sha256: str = Field(pattern=_SHA256_PATTERN)
    validation_runs: list[SemanticValidationRun] = Field(min_length=1)
    review_rounds: list[SemanticReviewRound] = Field(min_length=2)
    downstream_sync: SemanticDownstreamSyncEvidence | None = None
    residual_gaps: list[SemanticGap] = Field(default_factory=list)
    completed_at: datetime

    @field_validator("inventory_path", "review_path")
    @classmethod
    def validate_control_path(cls, value: str) -> str:
        return _portable_relative_path(value)

    @field_validator("completed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("completion timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def validate_completion(self) -> SemanticReviewCompletion:
        if self.residual_gaps:
            raise ValueError("a completion record cannot contain residual gaps")
        last_two = [round_.lens for round_ in self.review_rounds[-2:]]
        if last_two != ["source-to-target", "target-to-source-adversarial"]:
            raise ValueError("completion requires the two ordered independent clean review lenses")
        scopes = {run.scope for run in self.validation_runs}
        if not {"public-framework", "personal-instance"}.issubset(scopes):
            raise ValueError("completion requires public and personal validation runs")
        validation_ids = [run.id for run in self.validation_runs]
        if len(validation_ids) != len(set(validation_ids)):
            raise ValueError("completion validation run IDs must be unique")
        evidence_times = [
            *(run.verified_at for run in self.validation_runs),
            *(round_.reviewed_at for round_ in self.review_rounds),
        ]
        if self.downstream_sync is not None:
            evidence_times.extend(
                [self.downstream_sync.applied_at, self.downstream_sync.validated_at]
            )
        if any(timestamp > self.completed_at for timestamp in evidence_times):
            raise ValueError("completion cannot precede its validation or review evidence")
        forward, reverse = self.review_rounds[-2:]
        if reverse.reviewed_at <= forward.reviewed_at:
            raise ValueError("the adversarial clean round must follow the source-to-target round")
        if self.development_topology == "integrated-workbench":
            if self.framework_target_commit != self.personal_target_commit:
                raise ValueError(
                    "integrated-workbench completion requires one shared framework/personal commit"
                )
            if self.downstream_sync is not None:
                raise ValueError(
                    "integrated-workbench completion must not claim downstream synchronization"
                )
        if self.status == "complete":
            if "host" not in scopes:
                raise ValueError("complete status requires an explicit host validation run")
            if self.development_topology == "split-downstream":
                if self.downstream_sync is None:
                    raise ValueError(
                        "split-downstream complete status requires reviewed annotated-tag "
                        "synchronization"
                    )
                if self.downstream_sync.source_commit != self.framework_target_commit:
                    raise ValueError(
                        "downstream source commit must equal the framework target commit"
                    )
                if forward.reviewed_at < self.downstream_sync.validated_at:
                    raise ValueError("final clean rounds must follow downstream synchronization")
                post_sync_scopes = {
                    run.scope
                    for run in self.validation_runs
                    if run.verified_at >= self.downstream_sync.validated_at
                }
                if not {"personal-instance", "host"}.issubset(post_sync_scopes):
                    raise ValueError(
                        "split-downstream complete status requires post-sync personal and host "
                        "validation"
                    )
        return self


class SemanticReviewSupersession(BaseModel):
    """Bind an immutable migration review to the correction that replaced its targets."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    control_type: Literal["semantic-review-supersession"] = (
        "semantic-review-supersession"
    )
    review_path: str
    review_sha256: str = Field(pattern=_SHA256_PATTERN)
    completion_path: str
    completion_sha256: str = Field(pattern=_SHA256_PATTERN)
    correction_manifest_id: UUID4
    supersedes_manifest_id: UUID4
    correction_manifest_path: str
    correction_provenance_path: str
    reason: str = Field(min_length=1)

    @field_validator(
        "review_path",
        "completion_path",
        "correction_manifest_path",
        "correction_provenance_path",
    )
    @classmethod
    def validate_control_path(cls, value: str) -> str:
        return _portable_relative_path(value)


class SemanticAmendmentTarget(BaseModel):
    """One current file that restores, validates, or documents corrected semantics."""

    model_config = ConfigDict(extra="forbid")

    scope: TargetScope
    path: str
    target_sha256: str = Field(pattern=_SHA256_PATTERN)
    relation: Literal["restored-by", "validated-by", "documented-by"]

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _portable_relative_path(value)


class SemanticReviewAmendmentEntry(BaseModel):
    """Correct one source mapping without rewriting the historical review."""

    model_config = ConfigDict(extra="forbid")

    source_path: str
    source_sha256: str = Field(pattern=_SHA256_PATTERN)
    prior_disposition: ImportDisposition
    corrected_targets: list[SemanticAmendmentTarget] = Field(min_length=1)
    resolution: str = Field(min_length=1)

    @field_validator("source_path")
    @classmethod
    def validate_source_path(cls, value: str) -> str:
        return _portable_relative_path(value)

    @model_validator(mode="after")
    def validate_targets(self) -> SemanticReviewAmendmentEntry:
        identities = [
            (target.scope, target.path, target.relation)
            for target in self.corrected_targets
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("corrected targets must be unique within an amendment entry")
        return self


class SemanticReviewAmendment(BaseModel):
    """Append-only correction for material mappings in an immutable review."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    control_type: Literal["semantic-review-amendment"] = "semantic-review-amendment"
    id: UUID4
    issue_id: str = Field(pattern=_ID_PATTERN)
    review_path: str
    review_sha256: str = Field(pattern=_SHA256_PATTERN)
    completion_path: str
    completion_sha256: str = Field(pattern=_SHA256_PATTERN)
    source_repository: str = Field(min_length=1)
    source_commit: str = Field(pattern=_COMMIT_PATTERN)
    status: Literal["complete"]
    reason: str = Field(min_length=1)
    entries: list[SemanticReviewAmendmentEntry] = Field(min_length=1)
    residual_gaps: list[str] = Field(max_length=0)
    corrected_at: datetime

    @field_validator("review_path", "completion_path")
    @classmethod
    def validate_control_path(cls, value: str) -> str:
        return _portable_relative_path(value)

    @field_validator("corrected_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("amendment timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def validate_entries(self) -> SemanticReviewAmendment:
        source_paths = [entry.source_path for entry in self.entries]
        if len(source_paths) != len(set(source_paths)):
            raise ValueError("amendment source paths must be unique")
        return self


@dataclass(frozen=True)
class SemanticReviewVerification:
    control: SemanticFileReviewControl
    target_tree_sha256: str
    disposition_counts: dict[str, int]
    target_files: int


def semantic_file_review_json_schema() -> dict[str, Any]:
    schema = SemanticFileReviewControl.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://career-os.dev/schemas/semantic-file-review.schema.json"
    schema["title"] = "Career OS Semantic File Review"
    return schema


def semantic_review_completion_json_schema() -> dict[str, Any]:
    schema = SemanticReviewCompletion.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://career-os.dev/schemas/semantic-review-completion.schema.json"
    schema["title"] = "Career OS Semantic Review Completion"
    return schema


def semantic_review_supersession_json_schema() -> dict[str, Any]:
    schema = SemanticReviewSupersession.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://career-os.dev/schemas/semantic-review-supersession.schema.json"
    schema["title"] = "Career OS Semantic Review Supersession"
    return schema


def semantic_review_amendment_json_schema() -> dict[str, Any]:
    schema = SemanticReviewAmendment.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://career-os.dev/schemas/semantic-review-amendment.schema.json"
    schema["title"] = "Career OS Semantic Review Amendment"
    return schema


def load_semantic_file_review(path: Path) -> SemanticFileReviewControl:
    return SemanticFileReviewControl.model_validate_json(path.read_text(encoding="utf-8"))


def load_semantic_review_completion(path: Path) -> SemanticReviewCompletion:
    return SemanticReviewCompletion.model_validate_json(path.read_text(encoding="utf-8"))


def load_semantic_review_supersession(path: Path) -> SemanticReviewSupersession:
    return SemanticReviewSupersession.model_validate_json(path.read_text(encoding="utf-8"))


def load_semantic_review_amendment(path: Path) -> SemanticReviewAmendment:
    return SemanticReviewAmendment.model_validate_json(path.read_text(encoding="utf-8"))


def verify_semantic_file_review(
    paths: ProjectPaths,
    *,
    inventory_path: Path,
    review_path: Path,
    source_root: Path | None = None,
    rules_path: Path | None = None,
    public_root: Path | None = None,
) -> SemanticReviewVerification:
    inventory_path = inventory_path.resolve()
    review_path = review_path.resolve()
    inventory = load_migration_inventory(inventory_path)
    control = load_semantic_file_review(review_path)

    if (source_root is None) != (rules_path is None):
        raise ValueError("source_root and rules_path must be supplied together")
    if source_root is not None and rules_path is not None:
        verified_inventory = verify_migration_inventory(source_root, rules_path, inventory_path)
        if verified_inventory != inventory:
            raise ValueError("verified source inventory changed during review")

    expected_inventory = _resolve_control_path(paths.data_root, control.inventory_path)
    if expected_inventory != inventory_path:
        raise ValueError("review inventory_path does not identify the supplied inventory")
    if sha256_file(inventory_path) != control.inventory_sha256:
        raise ValueError("review inventory_sha256 differs from the supplied inventory")
    if control.source_repository != inventory.source_repository:
        raise ValueError("review source_repository differs from inventory")
    if control.source_commit != inventory.source_commit:
        raise ValueError("review source_commit differs from inventory")
    if control.expected_source_assets != len(inventory.entries):
        raise ValueError("review expected_source_assets differs from inventory")

    inventory_by_path = {entry.source_path: entry for entry in inventory.entries}
    review_by_path = {entry.source_path: entry for entry in control.entries}
    if set(inventory_by_path) != set(review_by_path):
        missing = sorted(set(inventory_by_path) - set(review_by_path))
        extra = sorted(set(review_by_path) - set(inventory_by_path))
        raise ValueError(
            "file reviews must exactly cover the inventory"
            + (f"; missing: {', '.join(missing)}" if missing else "")
            + (f"; extra: {', '.join(extra)}" if extra else "")
        )

    for source_path, review in review_by_path.items():
        if review.inventory_identity() != _inventory_identity(inventory_by_path[source_path]):
            raise ValueError(f"source identity differs from inventory: {source_path}")
        if review.review_status != "closed":
            raise ValueError(f"source file review remains open: {source_path}")

    open_material = [
        gap.id for gap in control.residual_gaps if gap.material and gap.status == "open"
    ]
    if open_material:
        raise ValueError("material residual gaps remain open: " + ", ".join(open_material))

    resolved_files: dict[tuple[str, str], Path] = {}
    for scenario in control.scenarios:
        for evidence in scenario.evidence:
            resolved_files[(evidence.scope, evidence.path)] = _verify_reference(
                paths, evidence, public_root=public_root
            )
    for entry in control.entries:
        exact_target: Path | None = None
        for target in entry.target_refs:
            resolved = _verify_reference(
                paths, target, public_root=public_root
            )
            resolved_files[(target.scope, target.path)] = resolved
            if entry.disposition == "migrate-exact":
                exact_target = resolved
        if entry.disposition == "migrate-exact" and (
            exact_target is None or sha256_file(exact_target) != entry.source_sha256
        ):
            raise ValueError(
                f"migrate-exact target bytes differ from the frozen source: {entry.source_path}"
            )
        for evidence in entry.evidence:
            resolved_files[(evidence.scope, evidence.path)] = _verify_reference(
                paths, evidence, public_root=public_root
            )
        if entry.retirement is not None:
            for target in entry.target_refs:
                if target.relation not in {
                    "replaced-by",
                    "retained-by",
                    "archived-by",
                    "documented-by",
                    "superseded-by",
                }:
                    raise ValueError(
                        f"retired/archive-only review lacks a replacement relation: "
                        f"{entry.source_path}"
                    )

    digest = hashlib.sha256()
    for (scope, relative), resolved in sorted(resolved_files.items()):
        file_hash = sha256_file(resolved)
        if file_hash is None:
            raise ValueError(f"review target is missing: {scope}:{relative}")
        digest.update(f"{scope}\0{relative}\0{file_hash}\n".encode())

    disposition_counts: dict[str, int] = {}
    for entry in control.entries:
        disposition_counts[entry.disposition] = disposition_counts.get(entry.disposition, 0) + 1
    return SemanticReviewVerification(
        control=control,
        target_tree_sha256=digest.hexdigest(),
        disposition_counts=dict(sorted(disposition_counts.items())),
        target_files=len(resolved_files),
    )


def verify_semantic_review_completion(
    paths: ProjectPaths,
    *,
    completion_path: Path,
    source_root: Path | None = None,
    rules_path: Path | None = None,
    public_root: Path | None = None,
) -> SemanticReviewCompletion:
    completion = load_semantic_review_completion(completion_path)
    if completion.development_topology != paths.development_topology:
        raise ValueError(
            "completion development topology differs from career-os.toml: "
            f"{completion.development_topology} != {paths.development_topology}"
        )
    inventory_path = _resolve_control_path(paths.data_root, completion.inventory_path)
    review_path = _resolve_control_path(paths.data_root, completion.review_path)
    if sha256_file(inventory_path) != completion.inventory_sha256:
        raise ValueError("completion inventory hash has drifted")
    if sha256_file(review_path) != completion.review_sha256:
        raise ValueError("completion review hash has drifted")
    verified = verify_semantic_file_review(
        paths,
        inventory_path=inventory_path,
        review_path=review_path,
        source_root=source_root,
        rules_path=rules_path,
        public_root=public_root,
    )
    if completion.source_repository != verified.control.source_repository:
        raise ValueError("completion source_repository differs from review")
    if completion.source_commit != verified.control.source_commit:
        raise ValueError("completion source_commit differs from review")
    if completion.target_tree_sha256 != verified.target_tree_sha256:
        raise ValueError("completion target tree has drifted; semantic review is reopened")
    _verify_personal_target_commit(paths, completion.personal_target_commit)
    evidence_paths = [completion_path.resolve(), inventory_path, review_path]
    for run in completion.validation_runs:
        result_path = _resolve_control_path(paths.data_root, run.result_path)
        evidence_paths.append(result_path)
        if sha256_file(result_path) != run.result_sha256:
            raise ValueError(f"validation-run evidence has drifted: {run.result_path}")
        _verify_validation_result(run, result_path)
    for round_ in completion.review_rounds:
        report_path = _resolve_control_path(paths.data_root, round_.report_path)
        evidence_paths.append(report_path)
        if sha256_file(report_path) != round_.report_sha256:
            raise ValueError(f"review-round evidence has drifted: {round_.report_path}")
        _verify_review_round(
            round_,
            report_path,
            source_repository=completion.source_repository,
            source_commit=completion.source_commit,
            expected_items=len(verified.control.entries),
        )
    if completion.downstream_sync is not None:
        evidence_paths.append(
            _resolve_control_path(paths.data_root, completion.downstream_sync.result_path)
        )
        _verify_downstream_sync_evidence(
            completion.downstream_sync,
            paths=paths,
            public_root=public_root,
            framework_target_commit=completion.framework_target_commit,
        )
    if (
        completion.development_topology == "integrated-workbench"
        and completion.status == "local-candidate-complete"
    ):
        if _git_head(paths.project_root.resolve()) != completion.framework_target_commit:
            raise ValueError("completion integrated framework target commit has drifted")
    elif (
        public_root is not None
        and completion.status == "local-candidate-complete"
        and _git_head(public_root.resolve()) != completion.framework_target_commit
    ):
        raise ValueError("completion framework target commit has drifted")
    if completion.status == "complete":
        _require_evidence_committed(paths.project_root, evidence_paths)
    return completion


def verify_semantic_review_supersession(
    paths: ProjectPaths,
    *,
    supersession_path: Path,
    public_root: Path | None = None,
) -> SemanticReviewSupersession:
    """Verify an immutable completed review and the correction that superseded it.

    A completed migration review describes the target tree that existed at its
    recorded commit. Later schema-2 corrections must not rewrite that history.
    This receipt preserves the old controls byte-for-byte while binding them to
    the reviewed correction manifest and generated provenance that replaced
    their live targets.
    """

    data_root = paths.data_root.resolve()
    supersession_path = supersession_path.resolve()
    if not supersession_path.is_relative_to(data_root) or not supersession_path.is_file():
        raise ValueError("semantic-review supersession must be a file under the data root")
    supersession = load_semantic_review_supersession(supersession_path)

    review_path = _resolve_control_path(data_root, supersession.review_path)
    completion_path = _resolve_control_path(data_root, supersession.completion_path)
    manifest_path = _resolve_control_path(data_root, supersession.correction_manifest_path)
    provenance_path = _resolve_control_path(
        data_root, supersession.correction_provenance_path
    )
    if sha256_file(review_path) != supersession.review_sha256:
        raise ValueError("superseded semantic review hash has drifted")
    if sha256_file(completion_path) != supersession.completion_sha256:
        raise ValueError("superseded semantic completion hash has drifted")

    control = load_semantic_file_review(review_path)
    completion = load_semantic_review_completion(completion_path)
    if completion.development_topology != paths.development_topology:
        raise ValueError(
            "superseded completion development topology differs from career-os.toml"
        )
    if completion.review_path != supersession.review_path:
        raise ValueError("supersession review_path differs from completion")
    if completion.review_sha256 != supersession.review_sha256:
        raise ValueError("supersession review hash differs from completion")

    inventory_path = _resolve_control_path(data_root, control.inventory_path)
    inventory = load_migration_inventory(inventory_path)
    if completion.inventory_path != control.inventory_path:
        raise ValueError("superseded completion inventory_path differs from review")
    if sha256_file(inventory_path) != control.inventory_sha256:
        raise ValueError("superseded review inventory hash has drifted")
    if completion.inventory_sha256 != control.inventory_sha256:
        raise ValueError("superseded completion inventory hash differs from review")
    if completion.source_repository != control.source_repository:
        raise ValueError("superseded completion source_repository differs from review")
    if completion.source_commit != control.source_commit:
        raise ValueError("superseded completion source_commit differs from review")
    if control.source_repository != inventory.source_repository:
        raise ValueError("superseded review source_repository differs from inventory")
    if control.source_commit != inventory.source_commit:
        raise ValueError("superseded review source_commit differs from inventory")
    if control.expected_source_assets != len(inventory.entries):
        raise ValueError("superseded review source count differs from inventory")
    inventory_by_path = {entry.source_path: entry for entry in inventory.entries}
    review_by_path = {entry.source_path: entry for entry in control.entries}
    if set(inventory_by_path) != set(review_by_path):
        raise ValueError("superseded review no longer exactly covers its inventory")
    for source_path, review in review_by_path.items():
        if review.inventory_identity() != _inventory_identity(inventory_by_path[source_path]):
            raise ValueError(
                f"superseded review source identity differs from inventory: {source_path}"
            )
        if review.review_status != "closed":
            raise ValueError(f"superseded review remains open: {source_path}")
    if any(gap.material and gap.status == "open" for gap in control.residual_gaps):
        raise ValueError("superseded semantic review contains an open material gap")

    manifest = load_import_manifest(manifest_path)
    provenance = load_migration_provenance(provenance_path)
    if not isinstance(manifest, LegacyImportManifestV2):
        raise ValueError("semantic-review supersession requires a schema-2 correction manifest")
    if not isinstance(provenance, MigrationProvenanceMapV2):
        raise ValueError("semantic-review supersession requires schema-2 correction provenance")
    if manifest.id != supersession.correction_manifest_id:
        raise ValueError("supersession correction manifest ID differs from manifest")
    if provenance.manifest_id != supersession.correction_manifest_id:
        raise ValueError("supersession correction manifest ID differs from provenance")
    if manifest.provenance_path != supersession.correction_provenance_path:
        raise ValueError("supersession provenance path differs from manifest")
    if manifest.supersedes_manifest_ids != provenance.supersedes_manifest_ids:
        raise ValueError("correction manifest and provenance supersession sets differ")
    if supersession.supersedes_manifest_id not in manifest.supersedes_manifest_ids:
        raise ValueError("correction does not supersede the declared prior manifest")
    if manifest.source_repository != provenance.source_repository:
        raise ValueError("correction source repository differs from provenance")
    if manifest.source_commit != provenance.source_commit:
        raise ValueError("correction source commit differs from provenance")

    relative_supersession = supersession_path.relative_to(data_root).as_posix()
    supersession_sha256 = sha256_file(supersession_path)
    manifest_outputs = [
        output
        for entry in manifest.entries
        for output in entry.outputs
        if output.target_path == relative_supersession
    ]
    provenance_outputs = [
        output
        for entry in provenance.entries
        for output in entry.outputs
        if output.target_path == relative_supersession
    ]
    if len(manifest_outputs) != 1 or len(provenance_outputs) != 1:
        raise ValueError("correction must bind exactly one semantic-review supersession output")
    if manifest_outputs[0].prepared_sha256 != supersession_sha256:
        raise ValueError("correction manifest does not bind the supersession bytes")
    if provenance_outputs[0].target_sha256 != supersession_sha256:
        raise ValueError("correction provenance does not bind the supersession bytes")

    _verify_recorded_commit_ancestor(
        paths.project_root.resolve(),
        completion.personal_target_commit,
        "personal",
    )
    framework_root = (
        (public_root or paths.project_root)
        if completion.development_topology == "integrated-workbench"
        else public_root
    )
    if framework_root is not None:
        _verify_recorded_commit_ancestor(
            framework_root.resolve(),
            completion.framework_target_commit,
            "framework",
        )

    evidence_paths = [
        completion_path,
        inventory_path,
        review_path,
    ]
    for run in completion.validation_runs:
        result_path = _resolve_control_path(data_root, run.result_path)
        evidence_paths.append(result_path)
        if sha256_file(result_path) != run.result_sha256:
            raise ValueError(f"validation-run evidence has drifted: {run.result_path}")
        _verify_validation_result(run, result_path)
    for round_ in completion.review_rounds:
        report_path = _resolve_control_path(data_root, round_.report_path)
        evidence_paths.append(report_path)
        if sha256_file(report_path) != round_.report_sha256:
            raise ValueError(f"review-round evidence has drifted: {round_.report_path}")
        _verify_review_round(
            round_,
            report_path,
            source_repository=completion.source_repository,
            source_commit=completion.source_commit,
            expected_items=len(control.entries),
        )
    if completion.downstream_sync is not None:
        evidence_paths.append(
            _resolve_control_path(data_root, completion.downstream_sync.result_path)
        )
        _verify_downstream_sync_evidence(
            completion.downstream_sync,
            paths=paths,
            public_root=public_root,
            framework_target_commit=completion.framework_target_commit,
        )
    if completion.status == "complete":
        _require_evidence_committed(paths.project_root, evidence_paths)
    return supersession


def verify_semantic_review_amendment(
    paths: ProjectPaths,
    *,
    amendment_path: Path,
    public_root: Path | None = None,
) -> SemanticReviewAmendment:
    """Verify an append-only correction against immutable review bytes and live targets."""

    data_root = paths.data_root.resolve()
    amendment_path = amendment_path.resolve()
    if not amendment_path.is_relative_to(data_root) or not amendment_path.is_file():
        raise ValueError("semantic-review amendment must be a file under the data root")
    amendment = load_semantic_review_amendment(amendment_path)

    review_path = _resolve_control_path(data_root, amendment.review_path)
    completion_path = _resolve_control_path(data_root, amendment.completion_path)
    if sha256_file(review_path) != amendment.review_sha256:
        raise ValueError("amendment semantic review hash has drifted")
    if sha256_file(completion_path) != amendment.completion_sha256:
        raise ValueError("amendment semantic completion hash has drifted")

    review = load_semantic_file_review(review_path)
    completion = load_semantic_review_completion(completion_path)
    if amendment.source_repository != review.source_repository:
        raise ValueError("amendment source_repository differs from semantic review")
    if amendment.source_commit != review.source_commit:
        raise ValueError("amendment source_commit differs from semantic review")
    if completion.source_repository != amendment.source_repository:
        raise ValueError("amendment source_repository differs from completion")
    if completion.source_commit != amendment.source_commit:
        raise ValueError("amendment source_commit differs from completion")
    if completion.review_path != amendment.review_path:
        raise ValueError("amendment review_path differs from completion")
    if completion.review_sha256 != amendment.review_sha256:
        raise ValueError("amendment review hash differs from completion")

    review_by_path = {entry.source_path: entry for entry in review.entries}
    for entry in amendment.entries:
        prior = review_by_path.get(entry.source_path)
        if prior is None:
            raise ValueError(f"amendment source is unknown: {entry.source_path}")
        if prior.review_status != "closed":
            raise ValueError(f"amendment source review is not closed: {entry.source_path}")
        if prior.source_sha256 != entry.source_sha256:
            raise ValueError(f"amendment source hash differs: {entry.source_path}")
        if prior.disposition != entry.prior_disposition:
            raise ValueError(f"amendment prior disposition differs: {entry.source_path}")

        for target in entry.corrected_targets:
            root = (
                (public_root or paths.project_root)
                if target.scope == "public-framework"
                else paths.data_root
            ).resolve()
            resolved = root.joinpath(*PurePosixPath(target.path).parts).resolve()
            if not resolved.is_relative_to(root):
                raise ValueError(f"amendment target escapes its root: {target.path}")
            if not resolved.is_file():
                raise ValueError(
                    f"amendment target is missing: {target.scope}:{target.path}"
                )
            if sha256_file(resolved) != target.target_sha256:
                raise ValueError(
                    f"amendment target hash has drifted: {target.scope}:{target.path}"
                )
    return amendment


def _verify_recorded_commit_ancestor(root: Path, expected: str, label: str) -> None:
    actual = _git_head(root)
    if actual == expected:
        return
    if not _git_succeeds(root, "merge-base", "--is-ancestor", expected, actual):
        raise ValueError(
            f"superseded semantic completion {label} target commit is not an ancestor of HEAD"
        )


def _verify_validation_result(run: SemanticValidationRun, path: Path) -> None:
    payload = _load_json_evidence(path, "validation-run")
    if payload.get("status") != "passed":
        raise ValueError(f"validation-run evidence is not passed: {run.result_path}")
    if _evidence_datetime(payload, "verified_at", path) != run.verified_at:
        raise ValueError(f"validation-run timestamp differs from evidence: {run.result_path}")
    declared_scope = payload.get("scope")
    if (
        declared_scope in {"public-framework", "personal-instance", "host"}
        and declared_scope != run.scope
    ):
        raise ValueError(f"validation-run scope differs from evidence: {run.result_path}")

    collections = [
        payload.get("commands"),
        payload.get("checks"),
        payload.get("queries"),
    ]
    present = [collection for collection in collections if isinstance(collection, list)]
    if not present or not any(present):
        raise ValueError(f"validation-run evidence has no executed checks: {run.result_path}")
    for collection in present:
        if any(
            not isinstance(item, dict) or item.get("status") != "passed"
            for item in collection
        ):
            raise ValueError(f"validation-run evidence contains a failed check: {run.result_path}")
    if payload.get("external_actions_performed", []) != []:
        raise ValueError(f"validation-run performed an external action: {run.result_path}")
    if run.scope == "host":
        if payload.get("query_failures") != 0:
            raise ValueError(f"host validation contains query failures: {run.result_path}")
        if payload.get("launch_or_reload_performed") is not False:
            raise ValueError(f"host validation launched or reloaded Obsidian: {run.result_path}")


def _verify_review_round(
    round_: SemanticReviewRound,
    path: Path,
    *,
    source_repository: str,
    source_commit: str,
    expected_items: int,
) -> None:
    payload = _load_json_evidence(path, "review-round")
    expected = {
        "control_type": "semantic-review-round-report",
        "lens": round_.lens,
        "source_repository": source_repository,
        "source_commit": source_commit,
        "reviewed_items": expected_items,
        "new_material_gaps": 0,
    }
    mismatches = {
        key: (payload.get(key), value)
        for key, value in expected.items()
        if payload.get(key) != value
    }
    if round_.reviewed_items != expected_items:
        mismatches["completion.reviewed_items"] = (
            round_.reviewed_items,
            expected_items,
        )
    if mismatches:
        raise ValueError(
            f"review-round evidence differs from completion: {path.name}: {mismatches}"
        )
    if _evidence_datetime(payload, "reviewed_at", path) != round_.reviewed_at:
        raise ValueError(f"review-round timestamp differs from evidence: {round_.report_path}")
    if payload.get("material_gaps") != []:
        raise ValueError(f"review-round evidence contains material gaps: {round_.report_path}")
    assertions = payload.get("assertions")
    if not isinstance(assertions, list) or not assertions:
        raise ValueError(f"review-round evidence has no assertions: {round_.report_path}")
    if any(
        not isinstance(assertion, dict) or assertion.get("status") != "passed"
        for assertion in assertions
    ):
        raise ValueError(f"review-round evidence contains a failed assertion: {round_.report_path}")


def _verify_downstream_sync_evidence(
    sync: SemanticDownstreamSyncEvidence,
    *,
    paths: ProjectPaths,
    public_root: Path | None,
    framework_target_commit: str,
) -> None:
    result_path = _resolve_control_path(paths.data_root, sync.result_path)
    if sha256_file(result_path) != sync.result_sha256:
        raise ValueError("downstream synchronization evidence has drifted")
    payload = _load_json_evidence(result_path, "downstream-sync")
    expected: dict[str, Any] = {
        "control_type": "downstream-sync-validation",
        "status": "passed",
        "source_tag": sync.source_tag,
        "tag_object": sync.tag_object,
        "source_commit": sync.source_commit,
        "target_branch": sync.target_branch,
        "target_head": sync.target_head,
        "desired_tree": sync.desired_tree,
        "plan_sha256": sync.plan_sha256,
        "patch_sha256": sync.patch_sha256,
    }
    mismatches = {
        key: (payload.get(key), value)
        for key, value in expected.items()
        if payload.get(key) != value
    }
    if mismatches:
        raise ValueError(f"downstream synchronization result differs from completion: {mismatches}")
    if _evidence_datetime(payload, "applied_at", result_path) != sync.applied_at:
        raise ValueError("downstream synchronization apply timestamp differs from evidence")
    if _evidence_datetime(payload, "validated_at", result_path) != sync.validated_at:
        raise ValueError("downstream synchronization validation timestamp differs from evidence")
    checks = payload.get("checks")
    if not isinstance(checks, list) or not checks or any(
        not isinstance(check, dict) or check.get("status") != "passed" for check in checks
    ):
        raise ValueError("downstream synchronization evidence has incomplete checks")
    if payload.get("external_actions_performed", []) != []:
        raise ValueError("downstream synchronization evidence performed an external action")
    if sync.source_commit != framework_target_commit:
        raise ValueError("downstream synchronization source differs from framework target commit")
    if public_root is not None:
        root = public_root.resolve()
        if _git_text(root, "cat-file", "-t", sync.tag_object) != "tag":
            raise ValueError("downstream synchronization source object is not an annotated tag")
        peeled = _git_text(root, "rev-parse", f"{sync.tag_object}^{{commit}}")
        if peeled != sync.source_commit:
            raise ValueError("downstream synchronization tag resolves to a different commit")


def _verify_personal_target_commit(paths: ProjectPaths, expected: str) -> None:
    root = paths.project_root.resolve()
    actual = _git_head(root)
    if actual == expected:
        return
    if not _git_succeeds(root, "merge-base", "--is-ancestor", expected, actual):
        raise ValueError("completion personal target commit is not an ancestor of HEAD")
    data_root = paths.data_root.resolve()
    if not data_root.is_relative_to(root):
        raise ValueError("completion personal target commit has drifted")
    provenance_prefix = data_root.relative_to(root).joinpath(".provenance").as_posix()
    changed = _git_paths(root, "diff", "--name-only", "-z", expected, actual)
    forbidden = [
        path
        for path in changed
        if path != provenance_prefix and not path.startswith(f"{provenance_prefix}/")
    ]
    if forbidden:
        raise ValueError(
            "completion personal target commit has non-provenance descendants: "
            + ", ".join(sorted(forbidden))
        )


def _require_evidence_committed(project_root: Path, evidence_paths: list[Path]) -> None:
    root = project_root.resolve()
    failures: list[str] = []
    for path in sorted(set(path.resolve() for path in evidence_paths)):
        if not path.is_relative_to(root):
            failures.append(f"outside downstream Git root: {path}")
            continue
        relative = path.relative_to(root).as_posix()
        if not _git_succeeds(root, "cat-file", "-e", f"HEAD:{relative}"):
            failures.append(f"not committed: {relative}")
            continue
        if not _git_succeeds(root, "diff", "--quiet", "HEAD", "--", relative):
            failures.append(f"differs from HEAD: {relative}")
    if failures:
        raise ValueError(
            "complete status requires committed completion evidence: " + "; ".join(failures)
        )


def _load_json_evidence(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} evidence is not valid JSON: {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{label} evidence must be a JSON object: {path}")
    return payload


def _evidence_datetime(payload: dict[str, Any], key: str, path: Path) -> datetime:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"evidence timestamp is missing: {path}: {key}")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"evidence timestamp is invalid: {path}: {key}") from error
    if parsed.tzinfo is None:
        raise ValueError(f"evidence timestamp requires a timezone: {path}: {key}")
    return parsed


def _inventory_identity(entry: LegacyMigrationInventoryEntry) -> tuple[Any, ...]:
    return (
        entry.source_path,
        entry.source_sha256,
        entry.source_size,
        entry.source_git_mode,
        entry.source_git_oid,
        entry.hash_basis,
        entry.asset_type,
        entry.disposition,
        entry.rule_id,
        entry.replacement,
        entry.note,
    )


def _resolve_control_path(root: Path, relative: str) -> Path:
    root = root.resolve()
    resolved = root.joinpath(*PurePosixPath(_portable_relative_path(relative)).parts).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"control path escapes its root: {relative}")
    if not resolved.is_file():
        raise ValueError(f"control file is missing: {relative}")
    return resolved


def _verify_reference(
    paths: ProjectPaths,
    reference: SemanticTargetReference | SemanticReviewEvidence,
    *,
    public_root: Path | None,
) -> Path:
    root = (
        (public_root or paths.project_root)
        if reference.scope == "public-framework"
        else paths.data_root
    ).resolve()
    resolved = root.joinpath(*PurePosixPath(reference.path).parts).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"review reference escapes its root: {reference.path}")
    if not resolved.is_file():
        raise ValueError(f"review reference target is missing: {reference.scope}:{reference.path}")
    if reference.anchor is not None:
        _verify_anchor(resolved, reference.anchor)
    if isinstance(reference, SemanticTargetReference) and reference.target_id is not None:
        _verify_record_identity(resolved, reference)
    return resolved


def _verify_anchor(path: Path, anchor: str) -> None:
    if path.suffix.lower() != ".md":
        raise ValueError(f"anchors require a Markdown target: {path}")
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    requested = anchor[1:]
    if requested.startswith("^"):
        block_id = requested[1:]
        found = any(
            match is not None and match.group(1) == block_id
            for match in (_BLOCK_ID_PATTERN.search(line) for line in text.splitlines())
        )
    else:
        found = any(
            match is not None and match.group(1).strip() == requested
            for match in (_HEADING_PATTERN.match(line) for line in text.splitlines())
        )
    if not found:
        raise ValueError(f"anchor does not exist in {path}: {anchor}")


def _verify_record_identity(path: Path, reference: SemanticTargetReference) -> None:
    try:
        text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        if not text.startswith("---\n"):
            raise ValueError("record must begin with YAML frontmatter")
        end = text.find("\n---\n", 4)
        if end < 0:
            raise ValueError("record frontmatter is not terminated")
        loaded = _yaml.load(text[4:end])
        if not isinstance(loaded, dict):
            raise ValueError("record frontmatter must be a mapping")
        record_id = str(loaded["id"])
        kind = str(loaded["kind"])
        status = str(loaded["status"])
    except (KeyError, OSError, ValueError) as error:
        raise ValueError(f"review record target is invalid: {path}: {error}") from error
    authority_prefix = kind.split(".", maxsplit=1)[0]
    authority_directories = {
        "evidence": "10-career-evidence",
        "strategy": "20-career-strategy",
        "market": "30-role-market",
        "opportunity": "40-opportunity-decision",
        "outlook": "50-career-outlook",
        "readiness": "60-capability-readiness",
        "communication": "70-career-communication",
    }
    if authority_prefix not in authority_directories:
        raise ValueError(f"review record target has an unknown authority: {path}")
    expected_authority = authority_directories[authority_prefix]
    authority_map = {
        "10-career-evidence": "career-evidence",
        "20-career-strategy": "career-strategy",
        "30-role-market": "role-market",
        "40-opportunity-decision": "opportunity-decision",
        "50-career-outlook": "career-outlook",
        "60-capability-readiness": "capability-readiness",
        "70-career-communication": "career-communication",
    }
    actual = (
        record_id,
        kind,
        status,
        authority_map[expected_authority],
        record_id,
    )
    expected = (
        reference.target_id,
        reference.target_kind,
        reference.target_status,
        reference.authority,
        reference.lifecycle_id,
    )
    if actual != expected:
        raise ValueError(f"review target record identity differs from YAML: {path}")
    if PurePosixPath(reference.path).parts[0] != expected_authority:
        raise ValueError(f"review target record is outside its canonical authority: {path}")


def _git_head(root: Path) -> str:
    return _git_text(root, "rev-parse", "HEAD")


def _git_text(root: Path, *arguments: str) -> str:
    return _git_bytes(root, *arguments).decode("utf-8", errors="replace").strip()


def _git_bytes(root: Path, *arguments: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f"cannot inspect target Git repository: {root}: {error}") from error
    return completed.stdout


def _git_succeeds(root: Path, *arguments: str) -> bool:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=False,
            capture_output=True,
        )
    except OSError as error:
        raise ValueError(f"cannot inspect target Git repository: {root}: {error}") from error
    return completed.returncode == 0


def _git_paths(root: Path, *arguments: str) -> list[str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f"cannot inspect target Git repository: {root}: {error}") from error
    return [
        item.decode("utf-8", errors="surrogateescape")
        for item in completed.stdout.split(b"\0")
        if item
    ]
