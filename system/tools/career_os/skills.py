from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from ruamel.yaml import YAML

PROJECT_SKILLS = frozenset(
    {
        "career-evidence",
        "career-strategy",
        "role-market",
        "opportunity-decision",
        "career-outlook",
        "capability-readiness",
        "career-communication",
    }
)
SEAN_SKILLS = frozenset({"agent-scaffold", "conventional-commit"})
OBSIDIAN_SKILLS = frozenset(
    {"obsidian-markdown", "obsidian-bases", "json-canvas", "obsidian-cli", "defuddle"}
)
BUNDLED_SKILLS = SEAN_SKILLS | OBSIDIAN_SKILLS
EXPECTED_SKILLS = PROJECT_SKILLS | BUNDLED_SKILLS
MODE_MATRIX = {
    "career-evidence": {"capture", "debrief", "consolidate"},
    "career-strategy": {"position", "plan", "align"},
    "role-market": {"discover", "ingest", "screen", "compare", "review"},
    "opportunity-decision": {"research", "scope", "track", "decide"},
    "career-outlook": {"scan", "synthesize", "review"},
    "capability-readiness": {
        "diagnose",
        "learn",
        "study-paper",
        "practice",
        "assess",
        "retest",
    },
    "career-communication": {"compose", "tailor", "validate", "export"},
}

_yaml = YAML(typ="safe")


class SkillLock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    source_repository: str
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_path: str
    tree_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    license: str
    attribution: str


class SkillLockFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1)
    skills: list[SkillLock]


class SkillSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill: str
    mode: str


class OpportunityBlock(SkillSelection):
    name: str


class SkillSelectionPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    prompt: str = Field(min_length=1)


class SkillSelectionPromptPacket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    cases: list[SkillSelectionPrompt]


class SkillSelectionExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    selected: list[SkillSelection]
    requires_explicit_authorization: bool = False


class SkillSelectionOracle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    cases: list[SkillSelectionExpectation]
    opportunity_blocks: list[OpportunityBlock]
    hard_gate_case_ids: list[str]


class SkillSelectionReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    cases: list[SkillSelectionExpectation]


@dataclass(frozen=True)
class SkillCheck:
    id: str
    status: str
    path: str | None
    detail: str

    def as_dict(self) -> dict[str, str | None]:
        return asdict(self)


def canonical_tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(
        ((path.relative_to(root).as_posix(), path) for path in root.rglob("*") if path.is_file()),
        key=lambda item: item[0],
    )
    for relative, path in files:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def load_skill_locks(project_root: Path) -> SkillLockFile:
    path = project_root / "skills-lock.json"
    return SkillLockFile.model_validate_json(path.read_text(encoding="utf-8"))


def verify_skills(
    project_root: Path, selection_report: Path | None = None
) -> list[SkillCheck]:
    skills_root = project_root / ".agents/skills"
    actual = {
        path.name
        for path in skills_root.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    }
    checks = [
        SkillCheck(
            "skills.inventory",
            "pass" if actual == EXPECTED_SKILLS else "fail",
            ".agents/skills",
            _inventory_detail(actual),
        )
    ]

    for name in sorted(actual):
        skill_file = skills_root / name / "SKILL.md"
        try:
            frontmatter = _skill_frontmatter(skill_file)
            declared_name = frontmatter.get("name")
            description = frontmatter.get("description")
            if declared_name != name or not isinstance(description, str) or not description:
                raise ValueError("frontmatter name or description is invalid")
            checks.append(SkillCheck("skills.frontmatter", "pass", str(skill_file), "valid"))
        except (OSError, ValueError) as error:
            checks.append(SkillCheck("skills.frontmatter", "fail", str(skill_file), str(error)))

    try:
        lock_file = load_skill_locks(project_root)
    except (OSError, ValueError) as error:
        checks.append(SkillCheck("skills.lock", "fail", "skills-lock.json", str(error)))
        return checks

    locks = {item.name: item for item in lock_file.skills}
    checks.append(
        SkillCheck(
            "skills.lock-inventory",
            "pass" if set(locks) == BUNDLED_SKILLS else "fail",
            "skills-lock.json",
            f"expected {len(BUNDLED_SKILLS)} bundled locks; found {len(locks)}",
        )
    )
    if len(locks) != len(lock_file.skills):
        checks.append(
            SkillCheck("skills.lock-duplicates", "fail", "skills-lock.json", "duplicate names")
        )

    for name in sorted(BUNDLED_SKILLS & set(locks)):
        source = skills_root / name
        actual_hash = canonical_tree_sha256(source) if source.is_dir() else "missing"
        expected_hash = locks[name].tree_sha256
        checks.append(
            SkillCheck(
                "skills.tree-hash",
                "pass" if actual_hash == expected_hash else "fail",
                str(source),
                f"{name}: {actual_hash}",
            )
        )

    projection_root = project_root / ".claude/skills"
    for name in sorted(EXPECTED_SKILLS):
        projection = projection_root / name
        source = skills_root / name
        valid = projection.is_symlink() and projection.resolve() == source.resolve()
        checks.append(
            SkillCheck(
                "skills.projection",
                "pass" if valid else "fail",
                str(projection),
                "real symlink to .agents source" if valid else "missing or incorrect symlink",
            )
        )
    codex_skills = project_root / ".codex/skills"
    checks.append(
        SkillCheck(
            "skills.codex-projection",
            "fail" if codex_skills.exists() else "pass",
            ".codex/skills",
            "must not exist" if codex_skills.exists() else "absent",
        )
    )
    checks.extend(_verify_skill_selection(project_root, selection_report))
    return checks


def evaluate_skill_selection_report(project_root: Path, report_path: Path) -> SkillCheck:
    fixture_root = project_root / "system/tests/fixtures"
    oracle = SkillSelectionOracle.model_validate_json(
        (fixture_root / "skill-selection-oracle.json").read_text(encoding="utf-8")
    )
    report = SkillSelectionReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    expected = {case.id: case for case in oracle.cases}
    actual = {case.id: case for case in report.cases}
    if len(actual) != len(report.cases) or set(actual) != set(expected):
        return SkillCheck(
            "skills.blind-selection",
            "fail",
            str(report_path),
            "report case IDs must exactly match the hidden oracle",
        )
    mismatches = [
        case_id
        for case_id, expectation in expected.items()
        if actual[case_id].model_dump() != expectation.model_dump()
    ]
    return SkillCheck(
        "skills.blind-selection",
        "fail" if mismatches else "pass",
        str(report_path),
        (
            "mismatched cases: " + ", ".join(sorted(mismatches))
            if mismatches
            else "independent report matches every hidden expectation"
        ),
    )


def _verify_skill_selection(
    project_root: Path, selection_report: Path | None
) -> list[SkillCheck]:
    fixture_root = project_root / "system/tests/fixtures"
    prompts_path = fixture_root / "skill-selection-prompts.json"
    oracle_path = fixture_root / "skill-selection-oracle.json"
    checks: list[SkillCheck] = []
    try:
        prompts = SkillSelectionPromptPacket.model_validate_json(
            prompts_path.read_text(encoding="utf-8")
        )
        oracle = SkillSelectionOracle.model_validate_json(
            oracle_path.read_text(encoding="utf-8")
        )
        prompt_ids = [case.id for case in prompts.cases]
        oracle_ids = [case.id for case in oracle.cases]
        if len(prompt_ids) != len(set(prompt_ids)) or len(oracle_ids) != len(set(oracle_ids)):
            raise ValueError("selection case IDs must be unique")
        if set(prompt_ids) != set(oracle_ids):
            raise ValueError("prompt packet and oracle case IDs differ")
        for case in oracle.cases:
            for selection in case.selected:
                if selection.mode not in MODE_MATRIX.get(selection.skill, set()):
                    raise ValueError(
                        f"invalid selection expectation: {selection.skill}/{selection.mode}"
                    )
        covered: dict[str, set[str]] = {skill: set() for skill in PROJECT_SKILLS}
        for case in oracle.cases:
            for selection in case.selected:
                covered[selection.skill].add(selection.mode)
        if covered != MODE_MATRIX:
            raise ValueError("selection oracle does not cover every declared Skill mode")
        expected_blocks = [
            "jd-screening",
            "company-opportunity-decision",
            "application-tracking",
            "resume-tailoring-safe-export",
            "interview-preparation-retest",
        ]
        if [item.name for item in oracle.opportunity_blocks] != expected_blocks:
            raise ValueError("selection oracle must preserve five opportunity blocks")
        hard_gates = {case.id for case in oracle.cases if case.requires_explicit_authorization}
        if hard_gates != set(oracle.hard_gate_case_ids) or len(hard_gates) != 3:
            raise ValueError("selection oracle must define exactly three hard-gate cases")
        checks.append(
            SkillCheck(
                "skills.selection-fixtures",
                "pass",
                str(prompts_path),
                "prompt packet is schema-isolated from the hidden oracle",
            )
        )
    except (OSError, ValueError) as error:
        return [
            SkillCheck(
                "skills.selection-fixtures",
                "fail",
                str(fixture_root),
                str(error),
            )
        ]
    if selection_report is None:
        checks.append(
            SkillCheck(
                "skills.blind-selection",
                "attention",
                None,
                "not run; use `career-os skills verify --selection-report <path>` with a "
                "report from an Agent shown only the prompt packet",
            )
        )
    else:
        try:
            checks.append(evaluate_skill_selection_report(project_root, selection_report))
        except (OSError, ValueError) as error:
            checks.append(
                SkillCheck(
                    "skills.blind-selection",
                    "fail",
                    str(selection_report),
                    str(error),
                )
            )
    return checks


def _skill_frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md must start with YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("SKILL.md frontmatter is not terminated")
    loaded = _yaml.load(text[4:end])
    if not isinstance(loaded, dict):
        raise ValueError("SKILL.md frontmatter must be a mapping")
    return dict(loaded)


def _inventory_detail(actual: set[str]) -> str:
    missing = sorted(EXPECTED_SKILLS - actual)
    extra = sorted(actual - EXPECTED_SKILLS)
    if not missing and not extra:
        return "exactly 7 Career, 2 Sean, and 5 Obsidian Skills"
    return json.dumps({"missing": missing, "extra": extra}, sort_keys=True)
