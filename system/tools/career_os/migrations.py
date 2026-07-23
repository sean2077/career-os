from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from ruamel.yaml import YAML

from career_os.config import ProjectPaths
from career_os.operations import FileOperation, OperationPlan, create_plan
from career_os.operations.plans import sha256_file, sha256_text
from career_os.records import split_frontmatter, validate_record_envelope
from career_os.records.markdown import extract_markdown_section
from career_os.records.models import AUTHORITY_DIRECTORIES

_safe_yaml = YAML(typ="safe")


class MigrationDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    source_record_schema: int = Field(ge=1)
    target_record_schema: int = Field(ge=1)
    transform: Literal["record-envelope-v1-to-v2"]


def create_record_migration_plan(paths: ProjectPaths, target: int) -> OperationPlan:
    definition_path = (
        paths.project_root
        / "system/migrations"
        / f"record-envelope-1-to-{target}.json"
    )
    definition = _load_definition(definition_path)
    if definition.target_record_schema != target:
        raise ValueError(f"migration definition does not target record schema {target}")

    operations, customized_readmes = _authority_readme_operations(paths)
    observed_versions: set[int] = set()
    for path in _record_paths(paths.data_root):
        text = path.read_text(encoding="utf-8-sig")
        frontmatter_text, body = split_frontmatter(text)
        raw = _safe_yaml.load(frontmatter_text)
        if not isinstance(raw, dict):
            raise ValueError(f"record frontmatter must be a mapping: {path}")
        version = raw.get("schema_version")
        if not isinstance(version, int):
            raise ValueError(f"record schema_version must be an integer: {path}")
        observed_versions.add(version)
        if version == target:
            validate_record_envelope(raw)
            continue
        if version != definition.source_record_schema:
            raise ValueError(
                f"record {path} uses unsupported schema {version}; "
                f"expected {definition.source_record_schema} or {target}"
            )
        migrated = _migrate_v1_to_v2(raw, body)
        content = _serialize_record(migrated, body)
        operations.append(
            FileOperation(
                op="write_text",
                root="data",
                path=path.relative_to(paths.data_root).as_posix(),
                expected_sha256=sha256_file(path),
                result_sha256=sha256_text(content),
                content=content,
            )
        )

    source = "+".join(str(item) for item in sorted(observed_versions)) or "none"
    return create_plan(
        action="migrate",
        source_version=f"record-schema:{source}",
        target_version=f"record-schema:{target}",
        roots={
            "project": paths.project_root,
            "data": paths.data_root,
            "vault": paths.vault_root,
        },
        metadata={
            "definition": definition_path.relative_to(paths.project_root).as_posix(),
            "definition_sha256": _required_hash(sha256_file(definition_path)),
            "migration_id": definition.id,
            "authority_readme_updates": str(
                sum(operation.path.endswith("/README.md") for operation in operations)
            ),
            "customized_authority_readmes": str(customized_readmes),
        },
        operations=operations,
    )


def verify_migration_definition(plan: OperationPlan) -> None:
    definition_name = plan.metadata.get("definition")
    expected_hash = plan.metadata.get("definition_sha256")
    project_root = Path(plan.roots["project"]).resolve()
    if not definition_name or not expected_hash:
        raise ValueError("migration plan is missing definition metadata")
    definition_path = project_root.joinpath(*Path(definition_name).parts).resolve()
    if not definition_path.is_relative_to(project_root):
        raise ValueError("migration definition escapes the project root")
    if sha256_file(definition_path) != expected_hash:
        raise ValueError("migration definition changed after planning")
    _load_definition(definition_path)


def _load_definition(path: Path) -> MigrationDefinition:
    if not path.is_file():
        raise ValueError(f"no migration definition is available: {path}")
    return MigrationDefinition.model_validate_json(path.read_text(encoding="utf-8"))


def _record_paths(data_root: Path) -> list[Path]:
    if not data_root.exists():
        return []
    return [
        path
        for path in sorted(data_root.rglob("*.md"))
        if path.name != "README.md" and "_templates" not in path.parts
    ]


def _authority_readme_operations(paths: ProjectPaths) -> tuple[list[FileOperation], int]:
    operations: list[FileOperation] = []
    customized = 0
    for directory in sorted(AUTHORITY_DIRECTORIES.values()):
        target = paths.data_root / directory / "README.md"
        if not target.is_file():
            continue
        seed = paths.project_root / "system/seeds/authorities" / f"{directory}.md"
        if not seed.is_file():
            raise ValueError(f"authority seed is missing: {seed}")
        current = target.read_text(encoding="utf-8-sig")
        replacement = seed.read_text(encoding="utf-8")
        title = replacement.splitlines()[0].removeprefix("# ")
        legacy = (
            f"# {title}\n\n"
            "This directory contains user-owned canonical records for this authority. Record\n"
            "bodies may use any language; schema keys and enum values remain English.\n"
        )
        if current == replacement:
            continue
        if current != legacy:
            customized += 1
            continue
        operations.append(
            FileOperation(
                op="write_text",
                root="data",
                path=target.relative_to(paths.data_root).as_posix(),
                expected_sha256=sha256_file(target),
                result_sha256=sha256_text(replacement),
                content=replacement,
            )
        )
    return operations, customized


def _migrate_v1_to_v2(raw: dict[str, Any], body: str) -> dict[str, Any]:
    common_keys = {
        "id",
        "kind",
        "schema_version",
        "created_at",
        "updated_at",
        "languages",
        "visibility",
        "refs",
        "host_refs",
        "title",
        "tags",
        "aliases",
    }
    kind = raw.get("kind")
    if not isinstance(kind, str):
        raise ValueError("schema-1 record kind must be a string")
    migrated = {key: value for key, value in raw.items() if key in common_keys}
    migrated["schema_version"] = 2
    migrated.setdefault("visibility", "private")
    migrated.setdefault("refs", [])
    migrated.setdefault("host_refs", [])
    migrated.setdefault("tags", [])
    migrated.setdefault("aliases", [])
    migrated["migration_review"] = "required"
    migrated["legacy_fields"] = {
        key: value for key, value in raw.items() if key not in common_keys
    }
    migrated.update(_safe_defaults(kind, raw, body))
    validated = validate_record_envelope(migrated)
    return validated.model_dump(mode="json", exclude_none=True)


def _safe_defaults(kind: str, raw: dict[str, Any], body: str) -> dict[str, Any]:
    created_at = raw.get("created_at")
    updated_at = raw.get("updated_at")
    as_of = str(updated_at or created_at)[:10]
    title = str(raw.get("title") or "Migration review required")
    jd_source_body = (
        extract_markdown_section(body, "JD 原文") if kind == "market.jd" else ""
    )
    defaults: dict[str, dict[str, Any]] = {
        "evidence.capture": {
            "status": "needs-debrief",
            "source_type": "unknown",
            "captured_at": created_at,
            "provenance": "Migrated from record schema 1; provenance review required.",
            "attribution": "unknown",
            "sensitivity": "unknown",
        },
        "evidence.work": {
            "status": "draft",
            "contribution_scope": "unknown",
            "evidence_strength": "weak",
            "evidence_summary": "Migration review required; no evidence strength was inferred.",
        },
        "evidence.story": {
            "status": "draft",
            "sensitive_boundary": (
                "Migration review required; no publication boundary was inferred."
            ),
        },
        "evidence.claim": {
            "status": "draft",
            "allowed_uses": ["internal"],
            "claim_risk": "high",
        },
        "strategy.positioning": {
            "status": "candidate",
            "confidence": "low",
            "review_on": as_of,
            "disconfirming_signals": [],
        },
        "strategy.lane": {
            "status": "candidate",
            "confidence": "low",
            "review_on": as_of,
            "disconfirming_signals": [],
        },
        "strategy.plan": {
            "status": "draft",
            "horizon_start": as_of,
            "horizon_end": as_of,
            "review_on": as_of,
        },
        "market.direction": {"status": "candidate", "review_on": as_of},
        "market.jd": {
            "status": "captured",
            "source_status": "unavailable",
            "source_channel": "unknown",
            "captured_at": created_at,
            "missing_sections": ["Schema-1 record requires source-fidelity review."],
            "source_body_sha256": sha256_text(jd_source_body),
        },
        "opportunity.company": {
            "status": "pending-review",
            "canonical_name": title,
            "fact_state": "unknown",
            "refreshed_at": as_of,
            "freshness_days": 1,
        },
        "opportunity.scope": {"status": "draft", "channel": "unknown"},
        "opportunity.engagement": {
            "status": "active",
            "engagement_type": "unknown",
            "stage": "identified",
            "application_state": "unknown",
            "is_current_employment": False,
            "events": [],
        },
        "opportunity.decision": {
            "status": "draft",
            "decision": "unknown",
            "rationale": "Migration review required; no decision was inferred.",
            "review_on": as_of,
            "triggers": [],
        },
        "outlook.signal": {
            "status": "captured",
            "source_class": "unknown",
            "event_date": as_of,
            "published_at": as_of,
            "retrieved_at": as_of,
        },
        "outlook.thesis": {
            "status": "candidate",
            "confidence": "low",
            "horizon": "unknown",
            "invalidation_conditions": ["Migration review required."],
        },
        "outlook.review": {
            "status": "pending",
            "as_of": as_of,
            "personal_fit": "missing",
            "market_revealed": "missing",
            "independent_external": "missing",
            "confidence": "low",
            "rationale": "Migration review required; no outlook judgment was inferred.",
            "invalidation_conditions": ["Migration review required."],
        },
        "readiness.gap": {
            "status": "open",
            "gap_type": "unknown",
            "target": "Migration review required.",
        },
        "readiness.note": {"status": "draft", "note_type": "unknown"},
        "readiness.session": {
            "status": "planned",
            "session_type": "unknown",
            "outcome": "unscored",
            "reviewer_status": "missing",
        },
        "readiness.assessment": {
            "status": "draft",
            "assessment_type": "unknown",
            "result": "blocked",
            "reviewer_status": "missing",
            "input_fingerprint": "migration-review-required",
        },
        "communication.profile": {
            "status": "draft",
            "audience": "unknown",
            "identity_policy": "anonymous",
        },
        "communication.resume": {
            "status": "draft",
            "root_name": "migrated-resume",
            "audience": "unknown",
            "export_policy": "preview",
        },
        "communication.export": {
            "status": "planned",
            "profile": "preview",
            "authorization": "missing",
        },
    }
    if kind not in defaults:
        raise ValueError(f"unsupported schema-1 record kind: {kind}")
    return defaults[kind]


def _serialize_record(frontmatter: dict[str, Any], body: str) -> str:
    yaml = YAML()
    yaml.allow_unicode = True
    yaml.default_flow_style = False
    yaml.width = 4096
    stream = StringIO()
    yaml.dump(frontmatter, stream)
    return f"---\n{stream.getvalue()}---\n{body}"


def _required_hash(value: str | None) -> str:
    if value is None:
        raise ValueError("migration definition hash is missing")
    return value
