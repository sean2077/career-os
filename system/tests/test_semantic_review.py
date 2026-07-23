from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from career_os.checks import _check_semantic_review_controls
from career_os.config import DevelopmentTopology, ProjectPaths
from career_os.imports import (
    LegacyInventoryRule,
    LegacyInventoryRuleSet,
    create_migration_inventory,
)
from career_os.operations.plans import sha256_file
from career_os.semantic_review import (
    SemanticBehaviorScenario,
    SemanticFileReviewControl,
    SemanticReviewAmendment,
    SemanticReviewCompletion,
    semantic_file_review_json_schema,
    semantic_review_amendment_json_schema,
    verify_semantic_file_review,
    verify_semantic_review_amendment,
    verify_semantic_review_completion,
)

_PUBLIC_SCENARIO_FIXTURE = (
    Path(__file__).parent / "fixtures/semantic-review/scenario-matrix.json"
)


def test_public_scenario_matrix_covers_seven_domains_and_four_behavior_families() -> None:
    payload = json.loads(_PUBLIC_SCENARIO_FIXTURE.read_text(encoding="utf-8"))
    scenarios = [
        SemanticBehaviorScenario.model_validate(item) for item in payload["scenarios"]
    ]

    assert {scenario.family for scenario in scenarios} == {
        "domain-workflow",
        "cross-authority-guard",
        "host-adapter",
        "platform-operation",
    }
    assert {scenario.career_domain for scenario in scenarios if scenario.career_domain} == {
        "career-evidence",
        "career-strategy",
        "role-market",
        "opportunity-decision",
        "career-outlook",
        "capability-readiness",
        "career-communication",
    }
    project_root = Path(__file__).parents[2]
    for scenario in scenarios:
        assert scenario.success_outcome
        assert scenario.failure_closure
        assert scenario.forbidden_inferences
        assert scenario.forbidden_external_actions
        assert all((project_root / evidence.path).is_file() for evidence in scenario.evidence)


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _fixture(
    tmp_path: Path,
    *,
    topology: DevelopmentTopology = "integrated-workbench",
) -> tuple[ProjectPaths, Path, Path, Path, Path]:
    source = tmp_path / "legacy"
    source.mkdir()
    _git(source, "init")
    _git(source, "config", "user.name", "Career OS Test")
    _git(source, "config", "user.email", "career-os@example.test")
    (source / "个人经历.md").write_text("# 个人经历\n", encoding="utf-8")
    (source / "tool.py").write_text("print('legacy')\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "test: add semantic review fixture")
    commit = _git(source, "rev-parse", "HEAD")

    project = tmp_path / "target"
    data = project / "career"
    data.mkdir(parents=True)
    paths = ProjectPaths(
        project_root=project,
        data_root=data,
        runtime_root=project / "runtime",
        build_root=project / "build",
        local_state_root=project / ".career-os",
        vault_root=project,
        mode="standalone",
        development_topology=topology,
    )
    (project / "docs").mkdir()
    (project / "docs/public-contract.md").write_text(
        "# Public contract\n\n## Authorization guard\n\nNo external action.\n",
        encoding="utf-8",
    )
    (project / "system/tests").mkdir(parents=True)
    (project / "system/tests/public-contract-test.md").write_text(
        "# Synthetic evidence\n", encoding="utf-8"
    )
    (data / "10-career-evidence").mkdir()
    (data / "10-career-evidence/个人经历.md").write_text(
        "# 个人经历\n\n迁移后的多语言记录。\n", encoding="utf-8"
    )

    rules_path = data / ".provenance/rules.json"
    rules_path.parent.mkdir()
    rules = LegacyInventoryRuleSet(
        source_repository="legacy://synthetic-resume",
        source_commit=commit,
        rules=[
            LegacyInventoryRule(
                id="record",
                pattern="*.md",
                asset_type="record",
                disposition="migrate-transform",
            ),
            LegacyInventoryRule(
                id="tool",
                pattern="*.py",
                asset_type="tool",
                disposition="replace-by-public",
                replacement="career-os import verify-review",
            ),
        ],
    )
    rules_path.write_text(rules.model_dump_json(indent=2) + "\n", encoding="utf-8")
    inventory = create_migration_inventory(source, rules_path)
    inventory_path = data / ".provenance/inventory.json"
    inventory_path.write_text(inventory.model_dump_json(indent=2) + "\n", encoding="utf-8")

    by_path = {entry.source_path: entry for entry in inventory.entries}
    common_contract = {
        "user_result": "The requested outcome remains available.",
        "canonical_authority": "Career Evidence or deterministic platform operation.",
        "lifecycle": "Lifecycle state is explicit and never inferred from tooling success.",
        "references": "Stable file and anchor references remain resolvable.",
        "safety": "Invalid or incomplete input fails closed.",
        "authorization": "No external action is performed without a separate request.",
    }
    scenarios = json.loads(_PUBLIC_SCENARIO_FIXTURE.read_text(encoding="utf-8"))[
        "scenarios"
    ]
    for scenario in scenarios:
        scenario["evidence"] = [
            {
                "scope": "public-framework",
                "path": "docs/public-contract.md",
                "kind": "scenario",
                "assertion": "Synthetic standalone scenario evidence is resolvable.",
            }
        ]
    review_payload = {
        "schema_version": 1,
        "control_type": "semantic-file-review",
        "source_repository": inventory.source_repository,
        "source_commit": inventory.source_commit,
        "inventory_path": ".provenance/inventory.json",
        "inventory_sha256": sha256_file(inventory_path),
        "expected_source_assets": 2,
        "scenarios": scenarios,
        "residual_gaps": [],
        "entries": [
            {
                **by_path["tool.py"].model_dump(mode="json"),
                "target_refs": [
                    {
                        "scope": "public-framework",
                        "path": "docs/public-contract.md",
                        "anchor": "#Authorization guard",
                        "relation": "replaced-by",
                    }
                ],
                "behavior_families": ["platform-operation"],
                "career_domains": [],
                "outcome_contracts": [common_contract],
                "evidence": [
                    {
                        "scope": "public-framework",
                        "path": "system/tests/public-contract-test.md",
                        "kind": "outcome-test",
                        "assertion": "The reusable behavior has public-only evidence.",
                    }
                ],
                "scenario_ids": ["platform-deterministic-operations"],
                "review_status": "closed",
                "gap_ids": [],
            },
            {
                **by_path["个人经历.md"].model_dump(mode="json"),
                "target_refs": [
                    {
                        "scope": "personal-instance",
                        "path": "10-career-evidence/个人经历.md",
                        "anchor": "#个人经历",
                        "relation": "migrated-to",
                    }
                ],
                "behavior_families": ["domain-workflow", "cross-authority-guard"],
                "career_domains": ["career-evidence"],
                "outcome_contracts": [common_contract],
                "evidence": [
                    {
                        "scope": "personal-instance",
                        "path": "10-career-evidence/个人经历.md",
                        "anchor": "#个人经历",
                        "kind": "target",
                        "assertion": "The transformed record retains the source meaning.",
                    }
                ],
                "scenario_ids": ["domain-career-evidence", "guard-cross-authority"],
                "review_status": "closed",
                "gap_ids": [],
            },
        ],
    }
    review_path = data / ".provenance/semantic-file-review.json"
    review_path.write_text(
        json.dumps(review_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return paths, source, rules_path, inventory_path, review_path


def test_semantic_review_verifies_exact_inventory_targets_and_public_evidence(
    tmp_path: Path,
) -> None:
    paths, source, rules_path, inventory_path, review_path = _fixture(tmp_path)

    result = verify_semantic_file_review(
        paths,
        inventory_path=inventory_path,
        review_path=review_path,
        source_root=source,
        rules_path=rules_path,
    )

    assert result.control.expected_source_assets == 2
    assert result.target_tree_sha256
    assert result.disposition_counts == {
        "migrate-transform": 1,
        "replace-by-public": 1,
    }
    assert semantic_file_review_json_schema()["$id"].endswith(
        "semantic-file-review.schema.json"
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda payload: payload["entries"][0].update(source_path="missing.py"),
            "exactly cover the inventory",
        ),
        (
            lambda payload: payload["entries"][0].update(source_sha256="0" * 64),
            "source identity differs from inventory",
        ),
        (
            lambda payload: payload["entries"][0].update(review_status="open"),
            "review remains open",
        ),
        (
            lambda payload: payload["entries"][0]["target_refs"][0].update(
                anchor="#Missing heading"
            ),
            "anchor does not exist",
        ),
        (
            lambda payload: payload["entries"][0].update(evidence=[]),
            "at least 1 item",
        ),
    ],
)
def test_semantic_review_fails_closed(
    tmp_path: Path, mutation: object, message: str
) -> None:
    paths, source, rules_path, inventory_path, review_path = _fixture(tmp_path)
    payload = json.loads(review_path.read_text(encoding="utf-8"))
    assert callable(mutation)
    mutation(payload)
    review_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match=message):
        verify_semantic_file_review(
            paths,
            inventory_path=inventory_path,
            review_path=review_path,
            source_root=source,
            rules_path=rules_path,
        )


def test_semantic_review_model_rejects_unjustified_one_to_many(tmp_path: Path) -> None:
    _paths, _source, _rules_path, _inventory_path, review_path = _fixture(tmp_path)
    payload = json.loads(review_path.read_text(encoding="utf-8"))
    personal = payload["entries"][1]
    personal["target_refs"].append(
        {
            "scope": "personal-instance",
            "path": "10-career-evidence/个人经历.md",
            "relation": "duplicated-to",
        }
    )

    with pytest.raises(Exception, match="one-to-many"):
        SemanticFileReviewControl.model_validate(payload)


def test_migrate_transform_can_bind_a_distinct_public_template_lifecycle(
    tmp_path: Path,
) -> None:
    paths, source, rules_path, inventory_path, review_path = _fixture(tmp_path)
    payload = json.loads(review_path.read_text(encoding="utf-8"))
    personal = payload["entries"][1]
    personal["target_refs"][0].update(
        authority="career-evidence",
        lifecycle_id="10-career-evidence/个人经历.md",
    )
    personal["target_refs"].insert(
        0,
        {
            "scope": "public-framework",
            "path": "docs/public-contract.md",
            "relation": "canonical-template",
            "authority": "career-evidence",
            "lifecycle_id": "docs/public-contract.md",
        },
    )
    personal["evidence"].append(
        {
            "scope": "public-framework",
            "path": "system/tests/public-contract-test.md",
            "kind": "outcome-test",
            "assertion": "The public template is exercised without personal data.",
        }
    )
    review_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    result = verify_semantic_file_review(
        paths,
        inventory_path=inventory_path,
        review_path=review_path,
        source_root=source,
        rules_path=rules_path,
    )

    assert result.control.entries[1].target_refs[0].scope == "public-framework"


def test_semantic_review_migrate_exact_requires_identical_target_bytes(
    tmp_path: Path,
) -> None:
    paths, source, rules_path, inventory_path, review_path = _fixture(tmp_path)
    rules = LegacyInventoryRuleSet.model_validate_json(
        rules_path.read_text(encoding="utf-8")
    )
    rules.rules[0].disposition = "migrate-exact"
    rules_path.write_text(rules.model_dump_json(indent=2) + "\n", encoding="utf-8")
    inventory = create_migration_inventory(source, rules_path)
    inventory_path.write_text(
        inventory.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    payload = json.loads(review_path.read_text(encoding="utf-8"))
    exact = next(entry for entry in payload["entries"] if entry["source_path"].endswith(".md"))
    inventory_exact = next(
        entry for entry in inventory.entries if entry.source_path.endswith(".md")
    )
    for key, value in inventory_exact.model_dump(mode="json").items():
        exact[key] = value
    payload["inventory_sha256"] = sha256_file(inventory_path)
    review_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="target bytes differ"):
        verify_semantic_file_review(
            paths,
            inventory_path=inventory_path,
            review_path=review_path,
            source_root=source,
            rules_path=rules_path,
        )

    target = paths.data_root / "10-career-evidence/个人经历.md"
    target.write_bytes((source / "个人经历.md").read_bytes())
    verify_semantic_file_review(
        paths,
        inventory_path=inventory_path,
        review_path=review_path,
        source_root=source,
        rules_path=rules_path,
    )


def test_semantic_review_requires_full_matrix_and_entry_alignment(tmp_path: Path) -> None:
    _paths, _source, _rules_path, _inventory_path, review_path = _fixture(tmp_path)
    payload = json.loads(review_path.read_text(encoding="utf-8"))
    payload["scenarios"] = [
        scenario
        for scenario in payload["scenarios"]
        if scenario["family"] != "host-adapter"
    ]

    with pytest.raises(Exception, match="all four behavior families"):
        SemanticFileReviewControl.model_validate(payload)

    payload = json.loads(review_path.read_text(encoding="utf-8"))
    evidence_entry = next(
        entry for entry in payload["entries"] if entry["source_path"].endswith(".md")
    )
    evidence_entry["scenario_ids"] = ["domain-role-market", "guard-cross-authority"]

    with pytest.raises(Exception, match="Career authorities"):
        SemanticFileReviewControl.model_validate(payload)


def test_completion_binds_validation_and_clean_round_evidence(tmp_path: Path) -> None:
    paths, source, rules_path, inventory_path, review_path = _fixture(tmp_path)
    verified = verify_semantic_file_review(
        paths,
        inventory_path=inventory_path,
        review_path=review_path,
        source_root=source,
        rules_path=rules_path,
    )
    provenance = paths.data_root / ".provenance"
    public_result = provenance / "validation-public.txt"
    personal_result = provenance / "validation-personal.txt"
    host_result = provenance / "validation-host.txt"
    forward_report = provenance / "round-forward.json"
    reverse_report = provenance / "round-reverse.json"
    public_verified_at = "2026-07-22T12:00:00+00:00"
    personal_verified_at = "2026-07-22T12:10:00+00:00"
    forward_reviewed_at = "2026-07-22T12:20:00+00:00"
    reverse_reviewed_at = "2026-07-22T12:30:00+00:00"

    public_payload: dict[str, object] = {
        "control_type": "semantic-validation-result",
        "scope": "public-framework",
        "status": "passed",
        "verified_at": public_verified_at,
        "commands": [{"id": "check", "status": "passed"}],
        "external_actions_performed": [],
    }
    personal_payload: dict[str, object] = {
        "control_type": "semantic-validation-result",
        "scope": "personal-instance",
        "status": "passed",
        "verified_at": personal_verified_at,
        "commands": [{"id": "check", "status": "passed"}],
        "external_actions_performed": [],
    }
    forward_payload: dict[str, object] = {
        "control_type": "semantic-review-round-report",
        "lens": "source-to-target",
        "source_repository": verified.control.source_repository,
        "source_commit": verified.control.source_commit,
        "reviewed_at": forward_reviewed_at,
        "reviewed_items": 2,
        "new_material_gaps": 0,
        "material_gaps": [],
        "assertions": [{"id": "coverage", "status": "passed"}],
    }
    reverse_payload: dict[str, object] = {
        **forward_payload,
        "lens": "target-to-source-adversarial",
        "reviewed_at": reverse_reviewed_at,
    }
    _write_json(public_result, public_payload)
    _write_json(personal_result, personal_payload)
    _write_json(forward_report, forward_payload)
    _write_json(reverse_report, reverse_payload)

    _git(paths.project_root, "init")
    _git(paths.project_root, "config", "user.name", "Career OS Test")
    _git(paths.project_root, "config", "user.email", "career-os@example.test")
    _git(paths.project_root, "add", ".")
    _git(paths.project_root, "commit", "-m", "test: add completion fixture")
    target_commit = _git(paths.project_root, "rev-parse", "HEAD")
    completed_at = "2026-07-22T13:00:00+00:00"
    completion_payload = {
        "schema_version": 2,
        "control_type": "semantic-review-completion",
        "development_topology": "integrated-workbench",
        "status": "local-candidate-complete",
        "source_repository": verified.control.source_repository,
        "source_commit": verified.control.source_commit,
        "inventory_path": ".provenance/inventory.json",
        "inventory_sha256": sha256_file(inventory_path),
        "review_path": ".provenance/semantic-file-review.json",
        "review_sha256": sha256_file(review_path),
        "framework_target_commit": target_commit,
        "personal_target_commit": target_commit,
        "target_tree_sha256": verified.target_tree_sha256,
        "validation_runs": [
            {
                "id": "public-full",
                "scope": "public-framework",
                "command": "career-os check",
                "status": "passed",
                "result_path": ".provenance/validation-public.txt",
                "result_sha256": sha256_file(public_result),
                "verified_at": public_verified_at,
            },
            {
                "id": "personal-full",
                "scope": "personal-instance",
                "command": "career-os check --root downstream",
                "status": "passed",
                "result_path": ".provenance/validation-personal.txt",
                "result_sha256": sha256_file(personal_result),
                "verified_at": personal_verified_at,
            },
        ],
        "review_rounds": [
            {
                "lens": "source-to-target",
                "report_path": ".provenance/round-forward.json",
                "report_sha256": sha256_file(forward_report),
                "reviewed_items": 2,
                "new_material_gaps": 0,
                "reviewed_at": forward_reviewed_at,
            },
            {
                "lens": "target-to-source-adversarial",
                "report_path": ".provenance/round-reverse.json",
                "report_sha256": sha256_file(reverse_report),
                "reviewed_items": 2,
                "new_material_gaps": 0,
                "reviewed_at": reverse_reviewed_at,
            },
        ],
        "residual_gaps": [],
        "completed_at": completed_at,
    }
    completion = SemanticReviewCompletion.model_validate(completion_payload)
    completion_path = provenance / "completion.json"
    completion_path.write_text(completion.model_dump_json(indent=2) + "\n", encoding="utf-8")

    verify_semantic_review_completion(
        paths,
        completion_path=completion_path,
        source_root=source,
        rules_path=rules_path,
        public_root=paths.project_root,
    )

    host_verified_at = "2026-07-22T12:15:00+00:00"
    _write_json(
        host_result,
        {
            "control_type": "semantic-validation-result",
            "scope": "host",
            "status": "passed",
            "verified_at": host_verified_at,
            "commands": [{"id": "host-check", "status": "passed"}],
            "query_failures": 0,
            "launch_or_reload_performed": False,
            "external_actions_performed": [],
        },
    )
    completion_payload["status"] = "complete"
    completion_payload["validation_runs"].append(
        {
            "id": "host",
            "scope": "host",
            "command": "read-only host check",
            "status": "passed",
            "result_path": ".provenance/validation-host.txt",
            "result_sha256": sha256_file(host_result),
            "verified_at": host_verified_at,
        }
    )
    completion_path.write_text(
        SemanticReviewCompletion.model_validate(completion_payload).model_dump_json(indent=2)
        + "\n",
        encoding="utf-8",
    )
    _git(paths.project_root, "add", "career/.provenance")
    _git(paths.project_root, "commit", "-m", "test: attest completed review")
    assert _git(paths.project_root, "rev-parse", "HEAD") != target_commit

    verify_semantic_review_completion(
        paths,
        completion_path=completion_path,
        source_root=source,
        rules_path=rules_path,
        public_root=paths.project_root,
    )

    review_target = paths.data_root / "10-career-evidence/个人经历.md"
    original_target = review_target.read_bytes()
    review_target.write_text("# 个人经历\n\nmaterial drift\n", encoding="utf-8")
    with pytest.raises(ValueError, match="semantic review is reopened"):
        verify_semantic_review_completion(
            paths,
            completion_path=completion_path,
            source_root=source,
            rules_path=rules_path,
            public_root=paths.project_root,
        )
    review_target.write_bytes(original_target)

    public_result.write_text("drifted validation output\n", encoding="utf-8")
    with pytest.raises(ValueError, match="validation-run evidence has drifted"):
        verify_semantic_review_completion(
            paths,
            completion_path=completion_path,
            source_root=source,
            rules_path=rules_path,
            public_root=paths.project_root,
        )

    public_payload["status"] = "failed"
    _write_json(public_result, public_payload)
    completion_payload["validation_runs"][0]["result_sha256"] = sha256_file(public_result)
    completion_path.write_text(
        SemanticReviewCompletion.model_validate(completion_payload).model_dump_json(indent=2)
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="evidence is not passed"):
        verify_semantic_review_completion(
            paths,
            completion_path=completion_path,
            source_root=source,
            rules_path=rules_path,
            public_root=paths.project_root,
        )

    public_payload["status"] = "passed"
    _write_json(public_result, public_payload)
    completion_payload["validation_runs"][0]["result_sha256"] = sha256_file(public_result)
    forward_payload["reviewed_items"] = 1
    _write_json(forward_report, forward_payload)
    completion_payload["review_rounds"][0]["report_sha256"] = sha256_file(forward_report)
    completion_path.write_text(
        SemanticReviewCompletion.model_validate(completion_payload).model_dump_json(indent=2)
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="review-round evidence differs"):
        verify_semantic_review_completion(
            paths,
            completion_path=completion_path,
            source_root=source,
            rules_path=rules_path,
            public_root=paths.project_root,
        )


def test_split_downstream_complete_status_requires_post_sync_annotated_tag_evidence() -> None:
    public_commit = "a" * 40
    payload = {
        "schema_version": 2,
        "control_type": "semantic-review-completion",
        "development_topology": "split-downstream",
        "status": "complete",
        "source_repository": "legacy://resume",
        "source_commit": "b" * 40,
        "inventory_path": ".provenance/inventory.json",
        "inventory_sha256": "c" * 64,
        "review_path": ".provenance/review.json",
        "review_sha256": "d" * 64,
        "framework_target_commit": public_commit,
        "personal_target_commit": "e" * 40,
        "target_tree_sha256": "f" * 64,
        "validation_runs": [
            {
                "id": "public",
                "scope": "public-framework",
                "command": "public check",
                "status": "passed",
                "result_path": ".provenance/public.json",
                "result_sha256": "1" * 64,
                "verified_at": "2026-07-22T12:00:00+00:00",
            },
            {
                "id": "personal",
                "scope": "personal-instance",
                "command": "personal check",
                "status": "passed",
                "result_path": ".provenance/personal.json",
                "result_sha256": "2" * 64,
                "verified_at": "2026-07-22T12:30:00+00:00",
            },
            {
                "id": "host",
                "scope": "host",
                "command": "host check",
                "status": "passed",
                "result_path": ".provenance/host.json",
                "result_sha256": "3" * 64,
                "verified_at": "2026-07-22T12:30:00+00:00",
            },
        ],
        "review_rounds": [
            {
                "lens": "source-to-target",
                "report_path": ".provenance/forward.json",
                "report_sha256": "4" * 64,
                "reviewed_items": 495,
                "new_material_gaps": 0,
                "reviewed_at": "2026-07-22T12:40:00+00:00",
            },
            {
                "lens": "target-to-source-adversarial",
                "report_path": ".provenance/reverse.json",
                "report_sha256": "5" * 64,
                "reviewed_items": 495,
                "new_material_gaps": 0,
                "reviewed_at": "2026-07-22T12:50:00+00:00",
            },
        ],
        "residual_gaps": [],
        "completed_at": "2026-07-22T13:00:00+00:00",
    }

    with pytest.raises(Exception, match="annotated-tag synchronization"):
        SemanticReviewCompletion.model_validate(payload)

    payload["downstream_sync"] = {
        "source_tag": "v1.0.0",
        "tag_object": "6" * 40,
        "source_commit": public_commit,
        "target_branch": "sync/career-os-v1.0.0",
        "target_head": "e" * 40,
        "desired_tree": "7" * 40,
        "plan_sha256": "8" * 64,
        "patch_sha256": "9" * 64,
        "result_path": ".provenance/downstream-sync.json",
        "result_sha256": "0" * 64,
        "applied_at": "2026-07-22T12:10:00+00:00",
        "validated_at": "2026-07-22T12:20:00+00:00",
    }
    completion = SemanticReviewCompletion.model_validate(payload)
    assert completion.downstream_sync is not None


def test_integrated_workbench_complete_status_needs_no_downstream_sync() -> None:
    shared_commit = "a" * 40
    payload: dict[str, object] = {
        "schema_version": 2,
        "control_type": "semantic-review-completion",
        "development_topology": "integrated-workbench",
        "status": "complete",
        "source_repository": "legacy://resume",
        "source_commit": "b" * 40,
        "inventory_path": ".provenance/inventory.json",
        "inventory_sha256": "c" * 64,
        "review_path": ".provenance/review.json",
        "review_sha256": "d" * 64,
        "framework_target_commit": shared_commit,
        "personal_target_commit": shared_commit,
        "target_tree_sha256": "f" * 64,
        "validation_runs": [
            {
                "id": "framework",
                "scope": "public-framework",
                "command": "framework check",
                "status": "passed",
                "result_path": ".provenance/framework.json",
                "result_sha256": "1" * 64,
                "verified_at": "2026-07-22T12:00:00+00:00",
            },
            {
                "id": "personal",
                "scope": "personal-instance",
                "command": "personal check",
                "status": "passed",
                "result_path": ".provenance/personal.json",
                "result_sha256": "2" * 64,
                "verified_at": "2026-07-22T12:10:00+00:00",
            },
            {
                "id": "host",
                "scope": "host",
                "command": "host check",
                "status": "passed",
                "result_path": ".provenance/host.json",
                "result_sha256": "3" * 64,
                "verified_at": "2026-07-22T12:20:00+00:00",
            },
        ],
        "review_rounds": [
            {
                "lens": "source-to-target",
                "report_path": ".provenance/forward.json",
                "report_sha256": "4" * 64,
                "reviewed_items": 495,
                "new_material_gaps": 0,
                "reviewed_at": "2026-07-22T12:30:00+00:00",
            },
            {
                "lens": "target-to-source-adversarial",
                "report_path": ".provenance/reverse.json",
                "report_sha256": "5" * 64,
                "reviewed_items": 495,
                "new_material_gaps": 0,
                "reviewed_at": "2026-07-22T12:40:00+00:00",
            },
        ],
        "residual_gaps": [],
        "completed_at": "2026-07-22T13:00:00+00:00",
    }

    completion = SemanticReviewCompletion.model_validate(payload)
    assert completion.development_topology == "integrated-workbench"
    assert completion.downstream_sync is None

    payload["personal_target_commit"] = "e" * 40
    with pytest.raises(Exception, match="one shared framework/personal commit"):
        SemanticReviewCompletion.model_validate(payload)

    payload["personal_target_commit"] = shared_commit
    payload["downstream_sync"] = {
        "source_tag": "v1.0.0",
        "tag_object": "6" * 40,
        "source_commit": shared_commit,
        "target_branch": "sync/career-os-v1.0.0",
        "target_head": shared_commit,
        "desired_tree": "7" * 40,
        "plan_sha256": "8" * 64,
        "patch_sha256": "9" * 64,
        "result_path": ".provenance/downstream-sync.json",
        "result_sha256": "0" * 64,
        "applied_at": "2026-07-22T12:05:00+00:00",
        "validated_at": "2026-07-22T12:15:00+00:00",
    }
    with pytest.raises(Exception, match="must not claim downstream synchronization"):
        SemanticReviewCompletion.model_validate(payload)


def test_complete_verification_accepts_committed_post_sync_proof(tmp_path: Path) -> None:
    paths, source, rules_path, inventory_path, review_path = _fixture(
        tmp_path,
        topology="split-downstream",
    )
    verified = verify_semantic_file_review(
        paths,
        inventory_path=inventory_path,
        review_path=review_path,
        source_root=source,
        rules_path=rules_path,
    )
    provenance = paths.data_root / ".provenance"
    _git(paths.project_root, "init")
    _git(paths.project_root, "config", "user.name", "Career OS Test")
    _git(paths.project_root, "config", "user.email", "career-os@example.test")
    _git(paths.project_root, "add", ".")
    _git(paths.project_root, "commit", "-m", "test: add synchronized target")
    target_commit = _git(paths.project_root, "rev-parse", "HEAD")
    desired_tree = _git(paths.project_root, "rev-parse", f"{target_commit}^{{tree}}")
    _git(paths.project_root, "tag", "-a", "v1.0.0", "-m", "reviewed release")
    tag_object = _git(paths.project_root, "rev-parse", "refs/tags/v1.0.0")

    public_result = provenance / "public.json"
    personal_result = provenance / "personal.json"
    host_result = provenance / "host.json"
    sync_result = provenance / "downstream-sync.json"
    forward_report = provenance / "forward.json"
    reverse_report = provenance / "reverse.json"
    _write_json(
        public_result,
        {
            "control_type": "semantic-validation-result",
            "scope": "public-framework",
            "status": "passed",
            "verified_at": "2026-07-22T11:00:00+00:00",
            "commands": [{"id": "check", "status": "passed"}],
            "external_actions_performed": [],
        },
    )
    _write_json(
        personal_result,
        {
            "control_type": "semantic-validation-result",
            "scope": "personal-instance",
            "status": "passed",
            "verified_at": "2026-07-22T12:20:00+00:00",
            "commands": [{"id": "check", "status": "passed"}],
            "external_actions_performed": [],
        },
    )
    _write_json(
        host_result,
        {
            "control_type": "semantic-review-host-acceptance",
            "scope": "host",
            "status": "passed",
            "verified_at": "2026-07-22T12:20:00+00:00",
            "queries": [{"id": "base", "status": "passed"}],
            "query_failures": 0,
            "launch_or_reload_performed": False,
            "external_actions_performed": [],
        },
    )
    sync_payload: dict[str, object] = {
        "control_type": "downstream-sync-validation",
        "status": "passed",
        "source_tag": "v1.0.0",
        "tag_object": tag_object,
        "source_commit": target_commit,
        "target_branch": "sync/career-os-v1.0.0",
        "target_head": target_commit,
        "desired_tree": desired_tree,
        "plan_sha256": "1" * 64,
        "patch_sha256": "2" * 64,
        "applied_at": "2026-07-22T12:00:00+00:00",
        "validated_at": "2026-07-22T12:10:00+00:00",
        "checks": [{"id": "desired-tree", "status": "passed"}],
        "external_actions_performed": [],
    }
    _write_json(sync_result, sync_payload)
    round_common: dict[str, object] = {
        "control_type": "semantic-review-round-report",
        "source_repository": verified.control.source_repository,
        "source_commit": verified.control.source_commit,
        "reviewed_items": 2,
        "new_material_gaps": 0,
        "material_gaps": [],
        "assertions": [{"id": "coverage", "status": "passed"}],
    }
    _write_json(
        forward_report,
        {
            **round_common,
            "lens": "source-to-target",
            "reviewed_at": "2026-07-22T12:30:00+00:00",
        },
    )
    _write_json(
        reverse_report,
        {
            **round_common,
            "lens": "target-to-source-adversarial",
            "reviewed_at": "2026-07-22T12:40:00+00:00",
        },
    )

    completion_payload = {
        "schema_version": 2,
        "control_type": "semantic-review-completion",
        "development_topology": "split-downstream",
        "status": "complete",
        "source_repository": verified.control.source_repository,
        "source_commit": verified.control.source_commit,
        "inventory_path": ".provenance/inventory.json",
        "inventory_sha256": sha256_file(inventory_path),
        "review_path": ".provenance/semantic-file-review.json",
        "review_sha256": sha256_file(review_path),
        "framework_target_commit": target_commit,
        "personal_target_commit": target_commit,
        "target_tree_sha256": verified.target_tree_sha256,
        "validation_runs": [
            {
                "id": "public",
                "scope": "public-framework",
                "command": "public check",
                "status": "passed",
                "result_path": ".provenance/public.json",
                "result_sha256": sha256_file(public_result),
                "verified_at": "2026-07-22T11:00:00+00:00",
            },
            {
                "id": "personal",
                "scope": "personal-instance",
                "command": "personal check",
                "status": "passed",
                "result_path": ".provenance/personal.json",
                "result_sha256": sha256_file(personal_result),
                "verified_at": "2026-07-22T12:20:00+00:00",
            },
            {
                "id": "host",
                "scope": "host",
                "command": "host check",
                "status": "passed",
                "result_path": ".provenance/host.json",
                "result_sha256": sha256_file(host_result),
                "verified_at": "2026-07-22T12:20:00+00:00",
            },
        ],
        "review_rounds": [
            {
                "lens": "source-to-target",
                "report_path": ".provenance/forward.json",
                "report_sha256": sha256_file(forward_report),
                "reviewed_items": 2,
                "new_material_gaps": 0,
                "reviewed_at": "2026-07-22T12:30:00+00:00",
            },
            {
                "lens": "target-to-source-adversarial",
                "report_path": ".provenance/reverse.json",
                "report_sha256": sha256_file(reverse_report),
                "reviewed_items": 2,
                "new_material_gaps": 0,
                "reviewed_at": "2026-07-22T12:40:00+00:00",
            },
        ],
        "downstream_sync": {
            "source_tag": "v1.0.0",
            "tag_object": tag_object,
            "source_commit": target_commit,
            "target_branch": "sync/career-os-v1.0.0",
            "target_head": target_commit,
            "desired_tree": desired_tree,
            "plan_sha256": "1" * 64,
            "patch_sha256": "2" * 64,
            "result_path": ".provenance/downstream-sync.json",
            "result_sha256": sha256_file(sync_result),
            "applied_at": "2026-07-22T12:00:00+00:00",
            "validated_at": "2026-07-22T12:10:00+00:00",
        },
        "residual_gaps": [],
        "completed_at": "2026-07-22T12:50:00+00:00",
    }
    completion_path = provenance / "completion.json"
    completion_path.write_text(
        SemanticReviewCompletion.model_validate(completion_payload).model_dump_json(indent=2)
        + "\n",
        encoding="utf-8",
    )
    _git(paths.project_root, "add", "career/.provenance")
    _git(paths.project_root, "commit", "-m", "test: add committed completion proof")

    verified_completion = verify_semantic_review_completion(
        paths,
        completion_path=completion_path,
        source_root=source,
        rules_path=rules_path,
        public_root=paths.project_root,
    )

    assert verified_completion.status == "complete"


def _amendment_fixture(
    tmp_path: Path,
) -> tuple[
    ProjectPaths,
    Path,
    dict[str, Any],
    Path,
    Path,
    Path,
]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    paths, _source, _rules_path, inventory_path, review_path = _fixture(tmp_path)
    review = SemanticFileReviewControl.model_validate_json(
        review_path.read_text(encoding="utf-8")
    )
    target = paths.project_root / "docs/amended-contract.md"
    target.write_text("# Restored reviewer contract\n", encoding="utf-8")

    completion_payload = {
        "schema_version": 2,
        "control_type": "semantic-review-completion",
        "development_topology": "integrated-workbench",
        "status": "local-candidate-complete",
        "source_repository": review.source_repository,
        "source_commit": review.source_commit,
        "inventory_path": ".provenance/inventory.json",
        "inventory_sha256": sha256_file(inventory_path),
        "review_path": ".provenance/semantic-file-review.json",
        "review_sha256": sha256_file(review_path),
        "framework_target_commit": "a" * 40,
        "personal_target_commit": "a" * 40,
        "target_tree_sha256": "b" * 64,
        "validation_runs": [
            {
                "id": "public",
                "scope": "public-framework",
                "command": "public check",
                "status": "passed",
                "result_path": ".provenance/public.json",
                "result_sha256": "c" * 64,
                "verified_at": "2026-07-23T10:00:00+00:00",
            },
            {
                "id": "personal",
                "scope": "personal-instance",
                "command": "personal check",
                "status": "passed",
                "result_path": ".provenance/personal.json",
                "result_sha256": "d" * 64,
                "verified_at": "2026-07-23T10:00:00+00:00",
            },
        ],
        "review_rounds": [
            {
                "lens": "source-to-target",
                "report_path": ".provenance/forward.json",
                "report_sha256": "e" * 64,
                "reviewed_items": 2,
                "new_material_gaps": 0,
                "reviewed_at": "2026-07-23T10:10:00+00:00",
            },
            {
                "lens": "target-to-source-adversarial",
                "report_path": ".provenance/reverse.json",
                "report_sha256": "f" * 64,
                "reviewed_items": 2,
                "new_material_gaps": 0,
                "reviewed_at": "2026-07-23T10:20:00+00:00",
            },
        ],
        "residual_gaps": [],
        "completed_at": "2026-07-23T10:30:00+00:00",
    }
    completion = SemanticReviewCompletion.model_validate(completion_payload)
    completion_path = paths.data_root / ".provenance/semantic-review-completion.json"
    completion_path.write_text(
        completion.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )

    source_entry = next(
        entry for entry in review.entries if entry.source_path == "tool.py"
    )
    amendment_payload: dict[str, Any] = {
        "schema_version": 1,
        "control_type": "semantic-review-amendment",
        "id": "0f1e2d3c-4b5a-4678-9abc-def012345678",
        "issue_id": "subagent-migration-omission",
        "review_path": ".provenance/semantic-file-review.json",
        "review_sha256": sha256_file(review_path),
        "completion_path": ".provenance/semantic-review-completion.json",
        "completion_sha256": sha256_file(completion_path),
        "source_repository": review.source_repository,
        "source_commit": review.source_commit,
        "status": "complete",
        "reason": "Restore a source behavior omitted by the original mapping.",
        "entries": [
            {
                "source_path": source_entry.source_path,
                "source_sha256": source_entry.source_sha256,
                "prior_disposition": source_entry.disposition,
                "corrected_targets": [
                    {
                        "scope": "public-framework",
                        "path": "docs/amended-contract.md",
                        "target_sha256": sha256_file(target),
                        "relation": "restored-by",
                    }
                ],
                "resolution": "The independent behavior is restored and hash-bound.",
            }
        ],
        "residual_gaps": [],
        "corrected_at": "2026-07-23T11:00:00+00:00",
    }
    amendment = SemanticReviewAmendment.model_validate(amendment_payload)
    amendment_path = (
        paths.data_root / ".provenance/semantic-review-subagent-amendment.json"
    )
    amendment_path.write_text(
        amendment.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return (
        paths,
        amendment_path,
        amendment_payload,
        review_path,
        completion_path,
        target,
    )


def test_semantic_review_amendment_binds_base_and_current_targets(
    tmp_path: Path,
) -> None:
    paths, amendment_path, _payload, _review, _completion, _target = (
        _amendment_fixture(tmp_path)
    )

    amendment = verify_semantic_review_amendment(
        paths,
        amendment_path=amendment_path,
        public_root=paths.project_root,
    )

    assert amendment.issue_id == "subagent-migration-omission"
    assert len(amendment.entries) == 1
    assert semantic_review_amendment_json_schema()["$id"].endswith(
        "semantic-review-amendment.schema.json"
    )


@pytest.mark.parametrize(
    ("control", "message"),
    [
        ("review", "semantic review hash has drifted"),
        ("completion", "semantic completion hash has drifted"),
    ],
)
def test_semantic_review_amendment_rejects_base_hash_drift(
    tmp_path: Path,
    control: str,
    message: str,
) -> None:
    paths, amendment_path, _payload, review_path, completion_path, _target = (
        _amendment_fixture(tmp_path)
    )
    drifted = review_path if control == "review" else completion_path
    drifted.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        verify_semantic_review_amendment(
            paths,
            amendment_path=amendment_path,
            public_root=paths.project_root,
        )


def test_semantic_review_amendment_rejects_duplicate_and_unknown_sources(
    tmp_path: Path,
) -> None:
    paths, amendment_path, payload, _review, _completion, _target = (
        _amendment_fixture(tmp_path)
    )
    payload["entries"].append(payload["entries"][0].copy())
    _write_json(amendment_path, payload)
    with pytest.raises(ValueError, match="source paths must be unique"):
        verify_semantic_review_amendment(
            paths,
            amendment_path=amendment_path,
            public_root=paths.project_root,
        )

    paths, amendment_path, payload, _review, _completion, _target = (
        _amendment_fixture(tmp_path / "unknown")
    )
    payload["entries"][0]["source_path"] = "unknown.py"
    _write_json(amendment_path, payload)
    with pytest.raises(ValueError, match="source is unknown"):
        verify_semantic_review_amendment(
            paths,
            amendment_path=amendment_path,
            public_root=paths.project_root,
        )


def test_semantic_review_amendment_rejects_target_escape_missing_and_drift(
    tmp_path: Path,
) -> None:
    paths, amendment_path, payload, _review, _completion, _target = (
        _amendment_fixture(tmp_path)
    )
    payload["entries"][0]["corrected_targets"][0]["path"] = "../escape.md"
    _write_json(amendment_path, payload)
    with pytest.raises(ValueError, match="escape its root"):
        verify_semantic_review_amendment(
            paths,
            amendment_path=amendment_path,
            public_root=paths.project_root,
        )

    paths, amendment_path, _payload, _review, _completion, target = (
        _amendment_fixture(tmp_path / "missing")
    )
    target.unlink()
    with pytest.raises(ValueError, match="target is missing"):
        verify_semantic_review_amendment(
            paths,
            amendment_path=amendment_path,
            public_root=paths.project_root,
        )

    paths, amendment_path, _payload, _review, _completion, target = (
        _amendment_fixture(tmp_path / "drift")
    )
    target.write_text("# Drifted target\n", encoding="utf-8")
    with pytest.raises(ValueError, match="target hash has drifted"):
        verify_semantic_review_amendment(
            paths,
            amendment_path=amendment_path,
            public_root=paths.project_root,
        )


def test_check_validates_supersession_and_amendment_cumulatively(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    provenance = project / "career/.provenance"
    provenance.mkdir(parents=True)
    for name in (
        "semantic-file-review.json",
        "semantic-review-completion.json",
        "semantic-review-supersession.json",
        "semantic-review-subagent-amendment.json",
    ):
        (provenance / name).write_text("{}\n", encoding="utf-8")
    paths = ProjectPaths(
        project_root=project,
        data_root=project / "career",
        runtime_root=project / "runtime",
        build_root=project / "build",
        local_state_root=project / ".career-os",
        vault_root=project,
        mode="standalone",
        development_topology="integrated-workbench",
    )
    calls: list[str] = []

    def verify_supersession(*_args: object, **_kwargs: object) -> SimpleNamespace:
        calls.append("supersession")
        return SimpleNamespace(
            correction_manifest_path=".provenance/correction-manifest.json",
            correction_provenance_path=".provenance/correction-provenance.json",
            correction_manifest_id="manifest-id",
        )

    def verify_amendment(*_args: object, **_kwargs: object) -> SimpleNamespace:
        calls.append("amendment")
        return SimpleNamespace(
            entries=[object()],
            issue_id="subagent-migration-omission",
        )

    monkeypatch.setattr(
        "career_os.checks.verify_semantic_review_supersession",
        verify_supersession,
    )
    monkeypatch.setattr(
        "career_os.checks.verify_semantic_review_amendment",
        verify_amendment,
    )
    monkeypatch.setattr("career_os.checks._path_matches_head", lambda *_args: True)

    issues = _check_semantic_review_controls(paths)

    assert calls == ["supersession", "amendment"]
    assert {issue.id for issue in issues} >= {
        "migration.semantic-review-completion",
        "migration.semantic-review-amendment",
    }
