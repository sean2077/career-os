from __future__ import annotations

from pathlib import Path

import pytest
from career_os.config import ProjectPaths
from career_os.migrations import (
    _serialize_record,
    create_record_migration_plan,
    verify_migration_definition,
)
from career_os.operations import (
    FileOperation,
    apply_plan,
    create_plan,
    load_plan,
    rollback_plan,
)
from career_os.operations.plans import sha256_file, sha256_text, write_plan
from career_os.records import load_record


def test_record_serialization_does_not_add_trailing_whitespace() -> None:
    serialized = _serialize_record(
        {
            "path": "2B 职业发展/" + "long-segment-" * 20,
            "review_note": "Agent Runtime " * 40,
        },
        "# Body\n",
    )

    assert all(line == line.rstrip() for line in serialized.splitlines())


def test_plan_apply_and_rollback(tmp_path: Path) -> None:
    content = "hello\n"
    plan = create_plan(
        action="test",
        source_version="0",
        target_version="1",
        roots={"project": tmp_path},
        operations=[
            FileOperation(
                op="write_text",
                root="project",
                path="nested/file.txt",
                result_sha256=sha256_text(content),
                content=content,
            )
        ],
    )
    plan_path = write_plan(plan, tmp_path / "plan.json")

    applied = apply_plan(plan_path, tmp_path / ".state")
    assert applied.applied_at is not None
    assert (tmp_path / "nested/file.txt").read_text(encoding="utf-8") == content

    rolled_back = rollback_plan(plan_path, tmp_path / ".state")
    assert rolled_back.rolled_back_at is not None
    assert not (tmp_path / "nested/file.txt").exists()


def test_apply_rejects_stale_target(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("changed", encoding="utf-8")
    plan = create_plan(
        action="test",
        source_version="0",
        target_version="1",
        roots={"project": tmp_path},
        operations=[
            FileOperation(
                op="write_text",
                root="project",
                path="file.txt",
                expected_sha256=None,
                result_sha256=sha256_text("new"),
                content="new",
            )
        ],
    )
    plan_path = write_plan(plan, tmp_path / "plan.json")

    with pytest.raises(ValueError, match="stale operation target"):
        apply_plan(plan_path, tmp_path / ".state")


def test_load_rejects_tampered_plan(tmp_path: Path) -> None:
    plan = create_plan(
        action="test",
        source_version="0",
        target_version="1",
        roots={"project": tmp_path},
        operations=[],
    )
    plan_path = write_plan(plan, tmp_path / "plan.json")
    plan_path.write_text(
        plan_path.read_text(encoding="utf-8").replace('"action": "test"', '"action": "other"'),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="plan hash"):
        load_plan(plan_path)


def test_rollback_rejects_changed_result(tmp_path: Path) -> None:
    content = "managed\n"
    plan = create_plan(
        action="test",
        source_version="0",
        target_version="1",
        roots={"project": tmp_path},
        operations=[
            FileOperation(
                op="write_text",
                root="project",
                path="managed.txt",
                result_sha256=sha256_text(content),
                content=content,
            )
        ],
    )
    plan_path = write_plan(plan, tmp_path / "plan.json")
    apply_plan(plan_path, tmp_path / ".state")
    (tmp_path / "managed.txt").write_text("user change\n", encoding="utf-8")

    with pytest.raises(ValueError, match="changed after apply"):
        rollback_plan(plan_path, tmp_path / ".state")


def test_delete_rollback_rejects_recreated_target(tmp_path: Path) -> None:
    target = tmp_path / "retired.txt"
    target.write_text("reviewed prior output\n", encoding="utf-8")
    original_hash = sha256_file(target)
    assert original_hash is not None
    plan = create_plan(
        action="test",
        source_version="0",
        target_version="1",
        roots={"project": tmp_path},
        operations=[
            FileOperation(
                op="delete",
                root="project",
                path="retired.txt",
                expected_sha256=original_hash,
            )
        ],
    )
    plan_path = write_plan(plan, tmp_path / "plan.json")
    apply_plan(plan_path, tmp_path / ".state")
    target.write_text("user-created replacement\n", encoding="utf-8")

    with pytest.raises(ValueError, match="changed after apply"):
        rollback_plan(plan_path, tmp_path / ".state")

    assert target.read_text(encoding="utf-8") == "user-created replacement\n"


def test_record_migration_plans_conservative_v2_and_rolls_back(tmp_path: Path) -> None:
    definition = tmp_path / "system/migrations/record-envelope-1-to-2.json"
    definition.parent.mkdir(parents=True)
    definition.write_text(
        (Path(__file__).resolve().parents[1] / "migrations" / definition.name).read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    data_root = tmp_path / "career"
    data_root.mkdir()
    authority_readme = data_root / "10-career-evidence/README.md"
    authority_readme.parent.mkdir()
    authority_seed = tmp_path / "system/seeds/authorities/10-career-evidence.md"
    authority_seed.parent.mkdir(parents=True)
    authority_seed.write_text(
        (
            Path(__file__).resolve().parents[1]
            / "seeds/authorities/10-career-evidence.md"
        ).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    legacy_readme = """# Career Evidence

This directory contains user-owned canonical records for this authority. Record
bodies may use any language; schema keys and enum values remain English.
"""
    authority_readme.write_text(legacy_readme, encoding="utf-8")
    record_path = data_root / "旧记录.md"
    original = """---
id: 77777777-7777-4777-8777-777777777777
kind: evidence.work
schema_version: 1
created_at: 2026-07-20T00:00:00Z
updated_at: 2026-07-21T00:00:00Z
status: verified
private_note: preserve me
---
# 旧记录

The body remains byte-for-byte meaningful.
"""
    record_path.write_text(original, encoding="utf-8")
    jd_path = data_root / "旧岗位.md"
    original_jd = """---
id: 88888888-8888-4888-8888-888888888888
kind: market.jd
schema_version: 1
created_at: 2026-07-20T00:00:00Z
updated_at: 2026-07-21T00:00:00Z
status: reviewed
---
# Synthetic role

## JD 原文

Synthetic preserved JD source.
"""
    jd_path.write_text(original_jd, encoding="utf-8")
    paths = ProjectPaths(
        project_root=tmp_path,
        data_root=data_root,
        runtime_root=tmp_path / "runtime",
        build_root=tmp_path / "build",
        local_state_root=tmp_path / ".career-os",
        vault_root=tmp_path,
        mode="standalone",
    )

    plan = create_record_migration_plan(paths, 2)

    assert len(plan.operations) == 3
    assert plan.metadata["authority_readme_updates"] == "1"
    verify_migration_definition(plan)
    plan_path = write_plan(plan, tmp_path / ".career-os/plans/migration.json")
    apply_plan(plan_path, paths.local_state_root)
    migrated = load_record(record_path)
    assert migrated.envelope.schema_version == 2
    assert migrated.envelope.status == "draft"
    assert migrated.envelope.migration_review == "required"
    assert migrated.envelope.legacy_fields == {
        "status": "verified",
        "private_note": "preserve me",
    }
    assert "The body remains byte-for-byte meaningful." in migrated.body
    migrated_jd = load_record(jd_path)
    assert migrated_jd.envelope.source_body_sha256 == sha256_text(
        "Synthetic preserved JD source.\n"
    )
    migrated_readme = authority_readme.read_text(encoding="utf-8")
    assert "## Key Terms" in migrated_readme
    assert "## Completion Gate" in migrated_readme

    rollback_plan(plan_path, paths.local_state_root)
    assert record_path.read_text(encoding="utf-8") == original
    assert jd_path.read_text(encoding="utf-8") == original_jd
    assert authority_readme.read_text(encoding="utf-8") == legacy_readme
