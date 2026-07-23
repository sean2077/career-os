from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from career_os.cli import app
from career_os.config import ProjectPaths
from career_os.imports import (
    LegacyImportEntry,
    LegacyImportManifest,
    LegacyImportManifestV2,
    LegacyImportOutput,
    LegacyImportRetiredTarget,
    LegacyInventoryRule,
    LegacyInventoryRuleSet,
    LegacyMigrationInventory,
    MigrationProvenanceMap,
    MigrationProvenanceMapV2,
    create_import_plan,
    create_migration_inventory,
    load_import_manifest,
    merge_reviewed_correction,
    verify_import_plan,
    verify_migration_inventory,
)
from career_os.operations import apply_plan, rollback_plan
from career_os.operations.plans import sha256_file, write_plan
from pydantic import ValidationError
from typer.testing import CliRunner


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _source_repository(tmp_path: Path) -> tuple[Path, str]:
    source = tmp_path / "legacy"
    source.mkdir()
    _git(source, "init")
    _git(source, "config", "user.name", "Career OS Test")
    _git(source, "config", "user.email", "career-os@example.test")
    (source / "record.md").write_text("legacy record\n", encoding="utf-8")
    (source / "asset.bin").write_bytes(b"\x00career-os\xff")
    (source / "retired.txt").write_text("retire me\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "test: add legacy fixture")
    return source, _git(source, "rev-parse", "HEAD")


def _source_repository_with_symlink(tmp_path: Path) -> tuple[Path, str]:
    source, _commit = _source_repository(tmp_path)
    _git(source, "config", "core.symlinks", "false")
    link = source / "record-link"
    link.write_text("record.md", encoding="utf-8", newline="")
    oid = _git(source, "hash-object", "-w", "record-link")
    _git(source, "update-index", "--add", "--cacheinfo", f"120000,{oid},record-link")
    _git(source, "commit", "-m", "test: add portable symlink fixture")
    assert not _git(source, "status", "--porcelain", "--untracked-files=all")
    return source, _git(source, "rev-parse", "HEAD")


def _source_repository_with_gitlink(tmp_path: Path) -> tuple[Path, str, str]:
    source, commit = _source_repository(tmp_path)
    submodule = source / "vendor/submodule"
    submodule.parent.mkdir()
    subprocess.run(
        ["git", "clone", "--no-local", "--no-checkout", str(source), str(submodule)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    _git(submodule, "checkout", "--detach", commit)
    _git(
        source,
        "update-index",
        "--add",
        "--cacheinfo",
        f"160000,{commit},vendor/submodule",
    )
    _git(source, "commit", "-m", "test: add pinned gitlink fixture")
    assert not _git(source, "status", "--porcelain", "--untracked-files=all")
    return source, _git(source, "rev-parse", "HEAD"), commit


def _source_repository_with_nested_docs(tmp_path: Path) -> tuple[Path, str]:
    source, _commit = _source_repository(tmp_path)
    authority = source / "docs/10-career-evidence"
    nested = authority / "projects/example"
    nested.mkdir(parents=True)
    (authority / "README.md").write_text("authority\n", encoding="utf-8")
    (nested / "README.md").write_text("project index\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "test: add nested documentation fixtures")
    return source, _git(source, "rev-parse", "HEAD")


def _paths(tmp_path: Path) -> ProjectPaths:
    project = tmp_path / "target"
    data = project / "career"
    data.mkdir(parents=True)
    return ProjectPaths(
        project_root=project,
        data_root=data,
        runtime_root=project / "runtime",
        build_root=project / "build",
        local_state_root=project / ".career-os",
        vault_root=tmp_path,
        mode="embedded",
    )


def _write_project_config(project: Path) -> None:
    project.joinpath("career-os.toml").write_text(
        """schema_version = 1
system_version = "0.1.0-rc.2"
data_root = "career"
runtime_root = "runtime"
build_root = "build"
preferred_language = "en"

[obsidian]
minimum_version = "1.12.7"
quickadd_version = "2.12.3"

[resume]
engine = "xelatex"
""",
        encoding="utf-8",
    )


def test_import_plan_copies_binary_and_transformed_files_with_provenance(
    tmp_path: Path,
) -> None:
    source, commit = _source_repository(tmp_path)
    paths = _paths(tmp_path)
    prepared = paths.project_root / ".career-os/import-staging/record.md"
    prepared.parent.mkdir(parents=True)
    prepared.write_text("---\nschema_version: 2\n---\ntransformed\n", encoding="utf-8")
    prepared_direction = paths.project_root / ".career-os/import-staging/direction.md"
    prepared_direction.write_text("---\nschema_version: 2\n---\ndirection\n", encoding="utf-8")
    record_id = uuid4()
    direction_id = uuid4()
    manifest = LegacyImportManifest(
        id=uuid4(),
        source_repository="fixture://legacy",
        source_commit=commit,
        entries=[
            LegacyImportEntry(
                source_path="asset.bin",
                source_sha256=sha256_file(source / "asset.bin"),
                asset_type="attachment",
                disposition="migrate-exact",
                outputs=[
                    LegacyImportOutput(target_path="70-career-communication/attachments/asset.bin")
                ],
            ),
            LegacyImportEntry(
                source_path="record.md",
                source_sha256=sha256_file(source / "record.md"),
                asset_type="record",
                disposition="migrate-transform",
                outputs=[
                    LegacyImportOutput(
                        target_path="10-career-evidence/record.md",
                        target_id=record_id,
                        target_kind="evidence.capture",
                        prepared_path=".career-os/import-staging/record.md",
                        prepared_sha256=sha256_file(prepared),
                    ),
                    LegacyImportOutput(
                        target_path="30-role-market/direction.md",
                        target_id=direction_id,
                        target_kind="market.direction",
                        prepared_path=".career-os/import-staging/direction.md",
                        prepared_sha256=sha256_file(prepared_direction),
                    ),
                ],
                transformation_note="Converted by the reviewed fixture mapping.",
            ),
            LegacyImportEntry(
                source_path="retired.txt",
                source_sha256=sha256_file(source / "retired.txt"),
                asset_type="tool",
                disposition="retire",
                transformation_note="Replaced by the public CLI.",
            ),
        ],
    )
    manifest_path = paths.project_root / "career/.provenance/import-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")

    plan = create_import_plan(paths, source, manifest_path)

    assert plan.action == "import"
    assert len(plan.operations) == 4
    assert sum(operation.op == "copy_file" for operation in plan.operations) == 3
    verify_import_plan(plan)
    plan_path = write_plan(plan, paths.local_state_root / "plans/import.json")
    applied = apply_plan(plan_path, paths.local_state_root)
    assert applied.applied_at is not None
    assert (
        paths.data_root / "70-career-communication/attachments/asset.bin"
    ).read_bytes() == b"\x00career-os\xff"
    assert (
        (paths.data_root / "10-career-evidence/record.md")
        .read_text(encoding="utf-8")
        .endswith("transformed\n")
    )
    provenance = MigrationProvenanceMap.model_validate_json(
        (paths.data_root / ".provenance/resume-migration.json").read_text(encoding="utf-8")
    )
    assert provenance.source_commit == commit
    assert provenance.entries[1].outputs[0].target_id == record_id
    assert provenance.entries[1].outputs[1].target_id == direction_id
    assert provenance.entries[2].disposition == "retire"

    assert apply_plan(plan_path, paths.local_state_root).applied_at == applied.applied_at
    rolled_back = rollback_plan(plan_path, paths.local_state_root)
    assert rolled_back.rolled_back_at is not None
    assert not (paths.data_root / "10-career-evidence/record.md").exists()
    assert not (paths.data_root / ".provenance/resume-migration.json").exists()


def test_correction_manifest_retires_hash_pinned_target_and_rolls_back(
    tmp_path: Path,
) -> None:
    source, commit = _source_repository(tmp_path)
    paths = _paths(tmp_path)
    wrong_target = paths.data_root / "10-career-evidence/projects/example/_record.md"
    wrong_target.parent.mkdir(parents=True)
    wrong_target.write_text("wrong imported index\n", encoding="utf-8")
    wrong_hash = sha256_file(wrong_target)
    assert wrong_hash is not None

    prepared = paths.project_root / ".career-os/import-staging/example-readme.md"
    prepared.parent.mkdir(parents=True)
    prepared.write_text("project index\n", encoding="utf-8")
    superseded_ids = [uuid4(), uuid4()]
    manifest = LegacyImportManifestV2(
        schema_version=2,
        id=uuid4(),
        supersedes_manifest_ids=superseded_ids,
        source_repository="fixture://legacy",
        source_commit=commit,
        provenance_path=".provenance/import-correction.json",
        entries=[
            LegacyImportEntry(
                source_path="record.md",
                source_sha256=sha256_file(source / "record.md"),
                asset_type="documentation",
                disposition="migrate-transform",
                outputs=[
                    LegacyImportOutput(
                        target_path="10-career-evidence/projects/example/README.md",
                        prepared_path=".career-os/import-staging/example-readme.md",
                        prepared_sha256=sha256_file(prepared),
                    )
                ],
                transformation_note="Restore a directory index as documentation.",
            )
        ],
        retire_targets=[
            LegacyImportRetiredTarget(
                target_path="10-career-evidence/projects/example/_record.md",
                expected_sha256=wrong_hash,
                reason="The prior manifest misclassified a directory index as a work record.",
            )
        ],
    )
    manifest_path = paths.project_root / "correction-manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    plan = create_import_plan(paths, source, manifest_path)

    assert [operation.op for operation in plan.operations] == [
        "copy_file",
        "delete",
        "write_text",
    ]
    assert plan.metadata["supersedes_manifest_ids"] == ",".join(
        str(manifest_id) for manifest_id in superseded_ids
    )
    assert plan.operations[1].expected_sha256 == wrong_hash
    plan_path = write_plan(plan, paths.local_state_root / "plans/correction.json")
    apply_plan(plan_path, paths.local_state_root)
    assert not wrong_target.exists()
    restored_index = paths.data_root / "10-career-evidence/projects/example/README.md"
    assert restored_index.read_text(encoding="utf-8") == "project index\n"
    provenance = MigrationProvenanceMapV2.model_validate_json(
        (paths.data_root / ".provenance/import-correction.json").read_text(encoding="utf-8")
    )
    assert provenance.supersedes_manifest_ids == superseded_ids
    assert provenance.retired_targets[0].target_path.endswith("/_record.md")
    assert provenance.retired_targets[0].expected_sha256 == wrong_hash

    rollback_plan(plan_path, paths.local_state_root)
    assert wrong_target.read_text(encoding="utf-8") == "wrong imported index\n"
    assert not restored_index.exists()
    assert not (paths.data_root / ".provenance/import-correction.json").exists()


def test_correction_retirement_rejects_overwrite_conflicts(tmp_path: Path) -> None:
    source, commit = _source_repository(tmp_path)
    paths = _paths(tmp_path)
    wrong_target = paths.data_root / "10-career-evidence/wrong.md"
    wrong_target.parent.mkdir(parents=True)
    wrong_target.write_text("reviewed old output\n", encoding="utf-8")
    reviewed_hash = sha256_file(wrong_target)
    assert reviewed_hash is not None
    manifest = LegacyImportManifestV2(
        schema_version=2,
        id=uuid4(),
        supersedes_manifest_ids=[uuid4()],
        source_repository="fixture://legacy",
        source_commit=commit,
        entries=[],
        retire_targets=[
            LegacyImportRetiredTarget(
                target_path="10-career-evidence/wrong.md",
                expected_sha256=reviewed_hash,
                reason="Wrong output from the superseded manifest.",
            )
        ],
    )
    manifest_path = paths.project_root / "correction-manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    plan = create_import_plan(paths, source, manifest_path)
    plan_path = write_plan(plan, paths.local_state_root / "plans/correction.json")

    wrong_target.write_text("concurrent user edit\n", encoding="utf-8")

    with pytest.raises(ValueError, match="changed after planning"):
        verify_import_plan(plan)
    with pytest.raises(ValueError, match="stale operation target"):
        apply_plan(plan_path, paths.local_state_root)
    assert wrong_target.read_text(encoding="utf-8") == "concurrent user edit\n"


def test_import_plan_rejects_dirty_or_changed_source(tmp_path: Path) -> None:
    source, commit = _source_repository(tmp_path)
    paths = _paths(tmp_path)
    manifest = LegacyImportManifest(
        id=uuid4(),
        source_repository="fixture://legacy",
        source_commit=commit,
        entries=[
            LegacyImportEntry(
                source_path="record.md",
                source_sha256=sha256_file(source / "record.md"),
                asset_type="record",
                disposition="migrate-exact",
                outputs=[
                    LegacyImportOutput(
                        target_path="10-career-evidence/record.md",
                        target_id=uuid4(),
                        target_kind="evidence.capture",
                    )
                ],
            )
        ],
    )
    manifest_path = paths.project_root / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    plan = create_import_plan(paths, source, manifest_path)
    (source / "record.md").write_text("changed\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must be clean"):
        verify_import_plan(plan)


def test_import_manifest_rejects_escaping_and_duplicate_paths() -> None:
    digest = "a" * 64
    with pytest.raises(ValidationError, match="escape"):
        LegacyImportEntry(
            source_path="../private.md",
            source_sha256=digest,
            asset_type="record",
            disposition="retain-archive-only",
        )

    entry = LegacyImportEntry(
        source_path="same.md",
        source_sha256=digest,
        asset_type="record",
        disposition="retain-archive-only",
    )
    with pytest.raises(ValidationError, match="must be unique"):
        LegacyImportManifest(
            id=uuid4(),
            source_repository="fixture://legacy",
            source_commit="b" * 40,
            entries=[entry, entry],
        )

    with pytest.raises(ValidationError, match="both imported and retired"):
        LegacyImportManifestV2(
            schema_version=2,
            id=uuid4(),
            supersedes_manifest_ids=[uuid4()],
            source_repository="fixture://legacy",
            source_commit="b" * 40,
            entries=[
                LegacyImportEntry(
                    source_path="same.md",
                    source_sha256=digest,
                    asset_type="attachment",
                    disposition="migrate-exact",
                    outputs=[LegacyImportOutput(target_path="same.md")],
                )
            ],
            retire_targets=[
                LegacyImportRetiredTarget(
                    target_path="same.md",
                    expected_sha256=digest,
                    reason="wrong prior output",
                )
            ],
        )

    superseded_id = uuid4()
    with pytest.raises(ValidationError):
        LegacyImportManifestV2(
            schema_version=2,
            id=uuid4(),
            supersedes_manifest_ids=[],
            source_repository="fixture://legacy",
            source_commit="b" * 40,
            entries=[entry],
        )
    with pytest.raises(ValidationError, match="must be unique"):
        LegacyImportManifestV2(
            schema_version=2,
            id=uuid4(),
            supersedes_manifest_ids=[superseded_id, superseded_id],
            source_repository="fixture://legacy",
            source_commit="b" * 40,
            entries=[entry],
        )


def test_reviewed_correction_three_way_merge_preserves_non_overlapping_edits() -> None:
    assert (
        merge_reviewed_correction(
            migrated="compressed body",
            current="compressed body",
            corrected="restored source body",
            label="company body",
        )
        == "restored source body"
    )
    assert (
        merge_reviewed_correction(
            migrated={"status": "draft", "note": "old"},
            current={"status": "reviewed", "note": "old"},
            corrected={"status": "draft", "note": "old"},
            label="lifecycle",
        )
        == {"status": "reviewed", "note": "old"}
    )


def test_reviewed_correction_three_way_merge_stops_on_same_value_conflict() -> None:
    with pytest.raises(ValueError, match="post-migration edit: JD analysis"):
        merge_reviewed_correction(
            migrated="compressed body",
            current="user supplement",
            corrected="restored source body",
            label="JD analysis",
        )


def test_import_provenance_is_plain_json_not_a_record(tmp_path: Path) -> None:
    source, commit = _source_repository(tmp_path)
    paths = _paths(tmp_path)
    manifest_payload = {
        "schema_version": 1,
        "id": str(uuid4()),
        "source_repository": "fixture://legacy",
        "source_commit": commit,
        "entries": [
            {
                "source_path": "retired.txt",
                "source_sha256": sha256_file(source / "retired.txt"),
                "asset_type": "tool",
                "disposition": "retire",
            }
        ],
    }
    manifest_path = paths.project_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")

    plan = create_import_plan(paths, source, manifest_path)

    assert plan.operations[-1].path.endswith(".json")
    assert plan.operations[-1].op == "write_text"


def test_inventory_covers_every_tracked_entry_with_first_explicit_rule(
    tmp_path: Path,
) -> None:
    source, commit = _source_repository(tmp_path)
    rules = LegacyInventoryRuleSet(
        source_repository="fixture://legacy",
        source_commit=commit,
        rules=[
            LegacyInventoryRule(
                id="binary-attachment",
                pattern="*.bin",
                asset_type="attachment",
                disposition="migrate-exact",
            ),
            LegacyInventoryRule(
                id="markdown-record",
                pattern="*.md",
                asset_type="record",
                disposition="migrate-transform",
            ),
            LegacyInventoryRule(
                id="retired-tool",
                pattern="*",
                asset_type="tool",
                disposition="retire",
                note="No maintained downstream behavior.",
            ),
        ],
    )
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(rules.model_dump_json(indent=2) + "\n", encoding="utf-8")

    inventory = create_migration_inventory(source, rules_path)

    assert [entry.source_path for entry in inventory.entries] == [
        "asset.bin",
        "record.md",
        "retired.txt",
    ]
    assert inventory.entries[0].rule_id == "binary-attachment"
    assert inventory.entries[1].disposition == "migrate-transform"
    assert inventory.entries[2].rule_id == "retired-tool"
    assert all(entry.hash_basis == "worktree-file" for entry in inventory.entries)

    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(inventory.model_dump_json(indent=2) + "\n", encoding="utf-8")
    assert verify_migration_inventory(source, rules_path, inventory_path) == inventory


def test_inventory_v2_globs_are_segment_aware_and_globstar_is_recursive(
    tmp_path: Path,
) -> None:
    source, commit = _source_repository_with_nested_docs(tmp_path)
    rules = LegacyInventoryRuleSet(
        schema_version=2,
        source_repository="fixture://legacy",
        source_commit=commit,
        rules=[
            LegacyInventoryRule(
                id="authority-child",
                pattern="docs/10-career-evidence/*",
                asset_type="documentation",
                disposition="retain-archive-only",
            ),
            LegacyInventoryRule(
                id="authority-descendant",
                pattern="docs/10-career-evidence/**",
                asset_type="documentation",
                disposition="retain-archive-only",
            ),
            LegacyInventoryRule(
                id="all-remaining",
                pattern="**",
                asset_type="other",
                disposition="retain-archive-only",
            ),
        ],
    )
    rules_path = tmp_path / "rules-v2.json"
    rules_path.write_text(rules.model_dump_json(indent=2), encoding="utf-8")

    inventory = create_migration_inventory(source, rules_path)
    matched = {entry.source_path: entry.rule_id for entry in inventory.entries}

    assert matched["docs/10-career-evidence/README.md"] == "authority-child"
    assert (
        matched["docs/10-career-evidence/projects/example/README.md"]
        == "authority-descendant"
    )


def test_inventory_v1_glob_and_manifest_loading_remain_compatible(tmp_path: Path) -> None:
    source, commit = _source_repository_with_nested_docs(tmp_path)
    rules = LegacyInventoryRuleSet(
        source_repository="fixture://legacy",
        source_commit=commit,
        rules=[
            LegacyInventoryRule(
                id="historical-cross-segment-star",
                pattern="docs/10-career-evidence/*",
                asset_type="record",
                disposition="migrate-transform",
            ),
            LegacyInventoryRule(
                id="historical-catch-all",
                pattern="*",
                asset_type="other",
                disposition="retain-archive-only",
            ),
        ],
    )
    rules_path = tmp_path / "rules-v1.json"
    rules_path.write_text(rules.model_dump_json(indent=2), encoding="utf-8")

    inventory = create_migration_inventory(source, rules_path)
    nested = next(
        entry
        for entry in inventory.entries
        if entry.source_path == "docs/10-career-evidence/projects/example/README.md"
    )
    assert nested.rule_id == "historical-cross-segment-star"

    manifest_path = tmp_path / "manifest-v1-with-default-version.json"
    manifest_path.write_text(
        json.dumps(
            {
                "id": str(uuid4()),
                "source_repository": "fixture://legacy",
                "source_commit": commit,
                "entries": [
                    {
                        "source_path": "retired.txt",
                        "source_sha256": sha256_file(source / "retired.txt"),
                        "asset_type": "tool",
                        "disposition": "retire",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    assert isinstance(load_import_manifest(manifest_path), LegacyImportManifest)


def test_inventory_rejects_unclassified_and_stale_inputs(tmp_path: Path) -> None:
    source, commit = _source_repository(tmp_path)
    incomplete = LegacyInventoryRuleSet(
        source_repository="fixture://legacy",
        source_commit=commit,
        rules=[
            LegacyInventoryRule(
                id="markdown-only",
                pattern="*.md",
                asset_type="record",
                disposition="migrate-transform",
            )
        ],
    )
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(incomplete.model_dump_json(indent=2), encoding="utf-8")
    with pytest.raises(ValueError, match="no inventory disposition"):
        create_migration_inventory(source, rules_path)

    complete = incomplete.model_copy(
        update={
            "rules": [
                LegacyInventoryRule(
                    id="all",
                    pattern="*",
                    asset_type="other",
                    disposition="retain-archive-only",
                )
            ]
        }
    )
    rules_path.write_text(complete.model_dump_json(indent=2), encoding="utf-8")
    inventory = create_migration_inventory(source, rules_path)
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(inventory.model_dump_json(indent=2), encoding="utf-8")
    parsed = LegacyMigrationInventory.model_validate_json(
        inventory_path.read_text(encoding="utf-8")
    )
    inventory_path.write_text(
        parsed.model_copy(update={"entries": parsed.entries[:-1]}).model_dump_json(indent=2),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="differs"):
        verify_migration_inventory(source, rules_path, inventory_path)


def test_non_migrating_symlink_is_hashed_without_following_it(tmp_path: Path) -> None:
    source, commit = _source_repository_with_symlink(tmp_path)
    paths = _paths(tmp_path)
    rules = LegacyInventoryRuleSet(
        source_repository="fixture://legacy",
        source_commit=commit,
        rules=[
            LegacyInventoryRule(
                id="all",
                pattern="*",
                asset_type="other",
                disposition="retain-archive-only",
            )
        ],
    )
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(rules.model_dump_json(indent=2), encoding="utf-8")
    inventory = create_migration_inventory(source, rules_path)
    link_entry = next(entry for entry in inventory.entries if entry.source_path == "record-link")
    assert link_entry.hash_basis == "git-symlink-payload"
    assert link_entry.source_sha256 == hashlib.sha256(b"record.md").hexdigest()

    manifest = LegacyImportManifest(
        id=uuid4(),
        source_repository="fixture://legacy",
        source_commit=commit,
        entries=[
            LegacyImportEntry(
                source_path="record-link",
                source_sha256=link_entry.source_sha256,
                asset_type="skill",
                disposition="replace-by-public",
                replacement="public projection",
            )
        ],
    )
    manifest_path = paths.project_root / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    plan = create_import_plan(paths, source, manifest_path)
    assert [operation.op for operation in plan.operations] == ["write_text"]

    exact = manifest.model_copy(
        update={
            "entries": [
                LegacyImportEntry(
                    source_path="record-link",
                    source_sha256=link_entry.source_sha256,
                    asset_type="attachment",
                    disposition="migrate-exact",
                    outputs=[LegacyImportOutput(target_path="attachments/record-link")],
                )
            ]
        }
    )
    manifest_path.write_text(exact.model_dump_json(indent=2), encoding="utf-8")
    with pytest.raises(ValueError, match="regular files"):
        create_import_plan(paths, source, manifest_path)


def test_gitlink_inventory_hashes_the_pinned_object_without_checkout(
    tmp_path: Path,
) -> None:
    source, commit, gitlink_oid = _source_repository_with_gitlink(tmp_path)
    rules = LegacyInventoryRuleSet(
        source_repository="fixture://legacy",
        source_commit=commit,
        rules=[
            LegacyInventoryRule(
                id="all",
                pattern="*",
                asset_type="other",
                disposition="retain-archive-only",
            )
        ],
    )
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(rules.model_dump_json(indent=2), encoding="utf-8")

    inventory = create_migration_inventory(source, rules_path)

    gitlink = next(
        entry for entry in inventory.entries if entry.source_path == "vendor/submodule"
    )
    assert gitlink.source_git_mode == "160000"
    assert gitlink.source_git_oid == gitlink_oid
    assert gitlink.hash_basis == "gitlink-oid"
    assert gitlink.source_size == 40
    assert gitlink.source_sha256 == hashlib.sha256(gitlink_oid.encode("ascii")).hexdigest()

    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(inventory.model_dump_json(indent=2), encoding="utf-8")
    assert verify_migration_inventory(source, rules_path, inventory_path) == inventory


def test_inventory_cli_refuses_unsafe_or_conflicting_output(tmp_path: Path) -> None:
    source, commit = _source_repository(tmp_path)
    paths = _paths(tmp_path)
    _write_project_config(paths.project_root)
    rules = LegacyInventoryRuleSet(
        source_repository="fixture://legacy",
        source_commit=commit,
        rules=[
            LegacyInventoryRule(
                id="all",
                pattern="*",
                asset_type="other",
                disposition="retain-archive-only",
            )
        ],
    )
    rules_path = paths.project_root / "rules.json"
    rules_path.write_text(rules.model_dump_json(indent=2), encoding="utf-8")
    runner = CliRunner()
    outside = tmp_path / "outside.json"
    unsafe = runner.invoke(
        app,
        [
            "import",
            "inventory",
            "--source-root",
            str(source),
            "--rules",
            str(rules_path),
            "--output",
            str(outside),
            "--root",
            str(paths.project_root),
        ],
    )
    assert unsafe.exit_code == 2
    assert not outside.exists()

    conflicting = paths.data_root / ".provenance/inventory.json"
    conflicting.parent.mkdir(parents=True)
    conflicting.write_text("{}\n", encoding="utf-8")
    conflict = runner.invoke(
        app,
        [
            "import",
            "inventory",
            "--source-root",
            str(source),
            "--rules",
            str(rules_path),
            "--output",
            str(conflicting),
            "--root",
            str(paths.project_root),
        ],
    )
    assert conflict.exit_code == 2
    assert conflicting.read_text(encoding="utf-8") == "{}\n"
