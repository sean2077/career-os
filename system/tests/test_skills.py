from __future__ import annotations

import json
from pathlib import Path

from career_os.skills import (
    MODE_MATRIX,
    PROJECT_SKILLS,
    canonical_tree_sha256,
    evaluate_skill_selection_report,
    verify_skills,
)


def test_canonical_tree_hash_is_path_and_content_sensitive(tmp_path: Path) -> None:
    first = tmp_path / "first"
    first.mkdir()
    first.joinpath("a.txt").write_text("one", encoding="utf-8")
    baseline = canonical_tree_sha256(first)

    first.joinpath("a.txt").write_text("two", encoding="utf-8")
    assert canonical_tree_sha256(first) != baseline

    second = tmp_path / "second"
    second.mkdir()
    second.joinpath("b.txt").write_text("one", encoding="utf-8")
    assert canonical_tree_sha256(second) != baseline


def test_repository_skill_inventory_and_locks_are_valid() -> None:
    project_root = Path(__file__).resolve().parents[2]

    failures = [item for item in verify_skills(project_root) if item.status == "fail"]

    assert not failures


def test_selection_packet_is_isolated_from_oracle_and_covers_contract() -> None:
    fixtures = Path(__file__).with_name("fixtures")
    prompts = json.loads(
        (fixtures / "skill-selection-prompts.json").read_text(encoding="utf-8")
    )
    oracle = json.loads(
        (fixtures / "skill-selection-oracle.json").read_text(encoding="utf-8")
    )
    assert all(set(case) == {"id", "prompt"} for case in prompts["cases"])
    assert {case["id"] for case in prompts["cases"]} == {
        case["id"] for case in oracle["cases"]
    }
    covered: dict[str, set[str]] = {skill: set() for skill in PROJECT_SKILLS}
    for case in oracle["cases"]:
        for expected in case["selected"]:
            covered[expected["skill"]].add(expected["mode"])

    assert covered == MODE_MATRIX
    assert [item["name"] for item in oracle["opportunity_blocks"]] == [
        "jd-screening",
        "company-opportunity-decision",
        "application-tracking",
        "resume-tailoring-safe-export",
        "interview-preparation-retest",
    ]
    assert len(oracle["hard_gate_case_ids"]) == 3


def test_selection_report_evaluator_is_separate_from_behavioral_run(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    oracle = json.loads(
        (
            project_root / "system/tests/fixtures/skill-selection-oracle.json"
        ).read_text(encoding="utf-8")
    )
    report = tmp_path / "selection-report.json"
    report.write_text(
        json.dumps({"schema_version": 1, "cases": oracle["cases"]}),
        encoding="utf-8",
    )

    result = evaluate_skill_selection_report(project_root, report)

    assert result.status == "pass"
    default_checks = verify_skills(project_root)
    blind = next(item for item in default_checks if item.id == "skills.blind-selection")
    assert blind.status == "attention"
    assert "career-os skills verify --selection-report" in blind.detail
