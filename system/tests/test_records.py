from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from career_os.config import resolve_paths
from career_os.records import (
    KIND_LIFECYCLES,
    load_record,
    record_json_schema,
    validate_record_envelope,
    validate_record_transition,
)
from career_os.records.models import EvidenceWork
from career_os.records.semantics import check_record_semantics
from pydantic import ValidationError


def _work(*, status: str, updated_at: datetime) -> EvidenceWork:
    return EvidenceWork.model_validate(
        {
            "id": "11111111-1111-4111-8111-111111111111",
            "kind": "evidence.work",
            "schema_version": 3,
            "created_at": "2026-07-24T00:00:00Z",
            "updated_at": updated_at,
            "visibility": "private",
            "status": status,
            "contribution_scope": "individual",
            "evidence_strength": "strong",
            "evidence_summary": "Synthetic evidence.",
        }
    )


def test_git_relative_lifecycle_requires_initial_and_updated_timestamp() -> None:
    now = datetime(2026, 7, 24, tzinfo=UTC)
    draft = _work(status="draft", updated_at=now)
    grounded = _work(status="grounded", updated_at=now + timedelta(minutes=1))

    validate_record_transition(None, draft)
    validate_record_transition(draft, grounded)

    with pytest.raises(ValueError, match="must start"):
        validate_record_transition(None, grounded)
    with pytest.raises(ValueError, match="advance updated_at"):
        validate_record_transition(draft, _work(status="grounded", updated_at=now))
    with pytest.raises(ValueError, match="forbidden"):
        validate_record_transition(draft, _work(status="verified", updated_at=now + timedelta(1)))


def test_schema3_rejects_legacy_arrays_unknown_fields_and_bad_wikilinks() -> None:
    payload = _work(
        status="draft", updated_at=datetime(2026, 7, 24, tzinfo=UTC)
    ).model_dump(mode="json")
    for field in ("refs", "host_refs", "status_history", "unexpected"):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            validate_record_envelope({**payload, field: []})
    with pytest.raises(ValidationError, match="String should match pattern"):
        validate_record_envelope({**payload, "company": "../not-a-wikilink"})


def test_migration_review_is_temporary_and_fail_closed() -> None:
    payload = _work(
        status="draft", updated_at=datetime(2026, 7, 24, tzinfo=UTC)
    ).model_dump(mode="json")
    reviewed = validate_record_envelope(
        {
            **payload,
            "migration_review": "required",
            "legacy_fields": {"old_key": "preserved"},
        }
    )
    assert reviewed.migration_review == "required"
    with pytest.raises(ValidationError, match="legacy_fields require"):
        validate_record_envelope({**payload, "legacy_fields": {"old_key": "orphaned"}})


def test_company_supports_bilingual_display_names() -> None:
    company = validate_record_envelope(
        {
            "id": "22222222-2222-4222-8222-222222222222",
            "kind": "opportunity.company",
            "schema_version": 3,
            "created_at": "2026-07-24T00:00:00Z",
            "updated_at": "2026-07-24T00:00:00Z",
            "visibility": "private",
            "status": "pending-review",
            "canonical_name": "示例科技有限公司",
            "display_name_zh": "示例科技",
            "display_name_en": "Example Technology",
            "fact_state": "fact",
            "refreshed_at": "2026-07-24",
            "freshness_days": 30,
        }
    )

    assert company.display_name_zh == "示例科技"
    assert company.display_name_en == "Example Technology"


def test_workspace_covers_all_kinds_and_wikilink_semantics() -> None:
    paths = resolve_paths(Path(__file__).resolve().parents[2])
    records = [
        load_record(path)
        for path in sorted(paths.data_root.rglob("*.md"))
        if path.name != "README.md" and "_templates" not in path.parts
    ]
    workspace_kinds = {record.envelope.kind for record in records}
    assert workspace_kinds <= set(KIND_LIFECYCLES)
    assert set(record_json_schema()["discriminator"]["mapping"]) == set(KIND_LIFECYCLES)
    assert not [
        issue
        for issue in check_record_semantics(records, paths)
        if issue.status == "fail"
    ]
    for record in records:
        raw = record.raw_frontmatter
        assert raw["schema_version"] == 3
        assert not {"refs", "host_refs", "status_history"}.intersection(raw)
