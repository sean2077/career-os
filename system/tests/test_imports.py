from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from career_os.config import ProjectPaths
from career_os.imports import create_import_plan, verify_import_plan
from career_os.operations import apply_plan, rollback_plan, verify_plan_state
from career_os.operations.plans import write_plan


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _paths(root: Path) -> ProjectPaths:
    return ProjectPaths(
        project_root=root,
        data_root=root / "career",
        runtime_root=root / ".career-os/runtime",
        build_root=root / "build",
        local_state_root=root / ".career-os",
        vault_root=root,
        mode="standalone",
    )


def _source_repo(root: Path) -> tuple[Path, str, str]:
    source = root / "legacy"
    source.mkdir()
    _git(source, "init")
    _git(source, "config", "user.name", "Synthetic")
    _git(source, "config", "user.email", "synthetic@example.test")
    payload = b"synthetic import\n"
    source.joinpath("record.md").write_bytes(payload)
    _git(source, "add", "record.md")
    _git(source, "commit", "-m", "fixture")
    return source, _git(source, "rev-parse", "HEAD"), hashlib.sha256(payload).hexdigest()


def test_import_plan_apply_verify_and_rollback_use_local_migration_state(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    paths.data_root.mkdir()
    source, commit, digest = _source_repo(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": str(uuid4()),
                "source_repository": "synthetic",
                "source_commit": commit,
                "entries": [
                    {
                        "source_path": "record.md",
                        "source_sha256": digest,
                        "asset_type": "record",
                        "disposition": "migrate-exact",
                        "outputs": [
                            {
                                "target_path": "10-career-evidence/record.md",
                                "target_id": str(uuid4()),
                                "target_kind": "evidence.work",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    plan = create_import_plan(paths, source, manifest)
    plan_path = paths.local_state_root / "migrations/plans/import.json"
    write_plan(plan, plan_path)
    verify_import_plan(plan)
    verify_plan_state(plan)

    applied = apply_plan(plan_path, paths.local_state_root / "migrations")
    verify_plan_state(applied)
    assert paths.data_root.joinpath("10-career-evidence/record.md").read_bytes() == (
        b"synthetic import\n"
    )
    assert not paths.data_root.joinpath(".provenance").exists()
    assert paths.local_state_root.joinpath(
        "migrations/backups", str(plan.id)
    ).is_dir() is False

    rolled_back = rollback_plan(plan_path, paths.local_state_root / "migrations")
    verify_plan_state(rolled_back)
    assert not paths.data_root.joinpath("10-career-evidence/record.md").exists()


def test_import_refuses_changed_source(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.data_root.mkdir()
    source, commit, digest = _source_repo(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": str(uuid4()),
                "source_repository": "synthetic",
                "source_commit": commit,
                "entries": [
                    {
                        "source_path": "record.md",
                        "source_sha256": "0" * 64,
                        "asset_type": "documentation",
                        "disposition": "retain-archive-only",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    assert digest != "0" * 64
    with pytest.raises(ValueError, match="source hash differs"):
        create_import_plan(paths, source, manifest)
