from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from career_os.cli import app
from career_os.skill_onboarding import (
    ONBOARDING_STATE_PATH,
    build_skill_onboarding_report,
    canonical_tree_sha256,
    configure_onboarding,
    load_recommendation_manifest,
)
from career_os.skills import (
    AUXILIARY_SKILLS,
    MODE_MATRIX,
    PROJECT_SKILLS,
    evaluate_skill_selection_report,
    verify_skills,
)
from typer.testing import CliRunner

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _copy_recommendations(project_root: Path) -> None:
    target = project_root / "system/skills/recommendations.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PROJECT_ROOT / "system/skills/recommendations.json", target)


def _write_skill(root: Path, name: str) -> Path:
    skill = root / ".agents/skills" / name
    skill.mkdir(parents=True, exist_ok=True)
    skill.joinpath("SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Synthetic test Skill.\n---\n",
        encoding="utf-8",
    )
    return skill


def _write_projection(root: Path, name: str) -> None:
    projection = root / ".claude/skills" / name
    projection.parent.mkdir(parents=True, exist_ok=True)
    try:
        projection.symlink_to(
            Path("../../.agents/skills") / name,
            target_is_directory=True,
        )
    except OSError as error:
        pytest.skip(f"local platform does not permit directory symlinks: {error}")


def _write_installer_lock(
    root: Path,
    *,
    scope: str,
    names: list[str],
    source: str,
    source_repository: str,
) -> None:
    lock = (
        root / "skills-lock.json"
        if scope == "project"
        else root / ".agents/.skill-lock.json"
    )
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(
        json.dumps(
            {
                "version": 3,
                "skills": {
                    name: {
                        "source": source,
                        "sourceUrl": source_repository + ".git",
                        "skillPath": f"skills/{name}/SKILL.md",
                    }
                    for name in names
                },
            }
        ),
        encoding="utf-8",
    )


def _install_group(
    project_root: Path,
    home_root: Path,
    *,
    group_id: str,
    scope: str,
    claude_projection: bool = False,
) -> list[str]:
    manifest = load_recommendation_manifest(project_root)
    group = next(group for group in manifest.groups if group.id == group_id)
    names = [skill.name for skill in group.skills]
    install_root = project_root if scope == "project" else home_root
    for name in names:
        _write_skill(install_root, name)
        if claude_projection:
            _write_projection(install_root, name)
    _write_installer_lock(
        install_root,
        scope=scope,
        names=names,
        source=group.source.split("#", 1)[0],
        source_repository=group.source_repository,
    )
    return names


def test_canonical_tree_hash_is_portable_and_content_sensitive(tmp_path: Path) -> None:
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

    lf = tmp_path / "lf"
    crlf = tmp_path / "crlf"
    lf.mkdir()
    crlf.mkdir()
    lf.joinpath("text.md").write_bytes(b"one\ntwo\n")
    crlf.joinpath("text.md").write_bytes(b"one\r\ntwo\r\n")
    assert canonical_tree_sha256(lf) == canonical_tree_sha256(crlf)

    lf.joinpath("binary.dat").write_bytes(b"\0one\ntwo\n")
    crlf.joinpath("binary.dat").write_bytes(b"\0one\r\ntwo\r\n")
    assert canonical_tree_sha256(lf) != canonical_tree_sha256(crlf)


def test_clean_skill_onboarding_is_read_only_and_argument_structured(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    home = tmp_path / "home"
    project.mkdir()
    home.mkdir()
    _copy_recommendations(project)

    report = build_skill_onboarding_report(
        project,
        audience="user",
        home_root=home,
    )

    assert report["schema"] == "career-os-skill-onboarding/1"
    assert report["schema_version"] == 1
    assert report["recommendation_revision"] == 1
    assert report["requires_user_choice"] is True
    assert [group["id"] for group in report["groups"]] == ["obsidian"]
    group = report["groups"][0]
    assert group["status"] == "missing"
    assert group["requires_user_choice"] is True
    assert group["install"]["environment"] == {"DISABLE_TELEMETRY": "1"}
    assert isinstance(group["install"]["base_args"], list)
    assert group["install"]["base_args"][:4] == [
        "npx",
        "--yes",
        "skills@1.5.20",
        "add",
    ]
    assert group["install"]["base_args"].count("--skill") == 1
    assert group["install"]["base_args"][-4:] == [
        "json-canvas",
        "obsidian-bases",
        "obsidian-cli",
        "obsidian-markdown",
    ]
    assert group["install"]["scope_args"] == {
        "project": [],
        "global": ["--global"],
    }
    assert group["install"]["agent_args"]["codex+claude-code"] == [
        "--agent",
        "codex",
        "claude-code",
    ]
    assert not project.joinpath(ONBOARDING_STATE_PATH).exists()

    contributor = build_skill_onboarding_report(
        project,
        audience="contributor",
        home_root=home,
    )
    assert [group["id"] for group in contributor["groups"]] == ["contributor"]


def test_recommendation_manifest_rejects_changed_source_or_unreviewed_contributor_ref(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _copy_recommendations(project)
    manifest_path = project / "system/skills/recommendations.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["groups"][0]["source"] = "untrusted/skills#main"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="source does not match"):
        load_recommendation_manifest(project)

    _copy_recommendations(project)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    contributor = next(
        group for group in manifest["groups"] if group["id"] == "contributor"
    )
    contributor["source"] = "sean2077/skills#develop"
    contributor["ref"] = "develop"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="stable SemVer tag or the reviewed main branch"):
        load_recommendation_manifest(project)


@pytest.mark.parametrize(
    ("scope", "agents", "claude_projection"),
    [
        ("project", ["codex"], False),
        ("global", ["codex"], False),
        ("project", ["codex", "claude-code"], True),
        ("global", ["claude-code"], True),
    ],
)
def test_configure_records_only_a_complete_verified_scope(
    tmp_path: Path,
    scope: str,
    agents: list[str],
    claude_projection: bool,
) -> None:
    project = tmp_path / "project"
    home = tmp_path / "home"
    project.mkdir()
    home.mkdir()
    _copy_recommendations(project)
    _install_group(
        project,
        home,
        group_id="obsidian",
        scope=scope,
        claude_projection=claude_projection,
    )

    result = configure_onboarding(
        project,
        group_id="obsidian",
        scope=scope,  # type: ignore[arg-type]
        agents=agents,
        reset=False,
        home_root=home,
    )

    report = result["skill_onboarding"]
    assert report["requires_user_choice"] is False
    assert report["groups"][0]["status"] == "installed"
    state = json.loads(project.joinpath(ONBOARDING_STATE_PATH).read_text(encoding="utf-8"))
    assert state["groups"]["obsidian"] == {
        "scope": scope,
        "agents": agents,
        "recommendation_revision": 1,
    }


def test_configure_rejects_missing_host_projection_and_wrong_source(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    home = tmp_path / "home"
    project.mkdir()
    home.mkdir()
    _copy_recommendations(project)
    names = _install_group(project, home, group_id="obsidian", scope="project")

    with pytest.raises(ValueError, match="not visible to claude-code"):
        configure_onboarding(
            project,
            group_id="obsidian",
            scope="project",
            agents=["claude-code"],
            reset=False,
            home_root=home,
        )
    assert not project.joinpath(ONBOARDING_STATE_PATH).exists()

    _write_installer_lock(
        project,
        scope="project",
        names=names,
        source="kepano/obsidian-skills",
        source_repository="https://github.com/wrong/source",
    )
    with pytest.raises(ValueError, match="installer source is mismatch"):
        configure_onboarding(
            project,
            group_id="obsidian",
            scope="project",
            agents=["codex"],
            reset=False,
            home_root=home,
        )
    assert not project.joinpath(ONBOARDING_STATE_PATH).exists()


def test_pinned_contributor_drift_cannot_be_recorded(tmp_path: Path) -> None:
    project = tmp_path / "project"
    home = tmp_path / "home"
    project.mkdir()
    home.mkdir()
    _copy_recommendations(project)
    _install_group(project, home, group_id="contributor", scope="project")

    report = build_skill_onboarding_report(
        project,
        audience="contributor",
        home_root=home,
    )
    assert report["groups"][0]["status"] == "partial"
    assert report["requires_user_choice"] is True
    with pytest.raises(ValueError, match="reviewed pinned tree"):
        configure_onboarding(
            project,
            group_id="contributor",
            scope="project",
            agents=["codex"],
            reset=False,
            home_root=home,
        )
    assert not project.joinpath(ONBOARDING_STATE_PATH).exists()

    manifest_path = project / "system/skills/recommendations.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    contributor = next(
        group for group in manifest["groups"] if group["id"] == "contributor"
    )
    for skill in contributor["skills"]:
        skill["tree_sha256"] = canonical_tree_sha256(
            project / ".agents/skills" / skill["name"]
        )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    configured = configure_onboarding(
        project,
        group_id="contributor",
        scope="project",
        agents=["codex"],
        reset=False,
        home_root=home,
    )
    assert configured["skill_onboarding"]["groups"][0]["status"] == "installed"

    project.joinpath(
        ".agents/skills",
        contributor["skills"][0]["name"],
        "changed.txt",
    ).write_text("drift", encoding="utf-8")
    drift = build_skill_onboarding_report(
        project,
        audience="contributor",
        home_root=home,
    )
    assert drift["groups"][0]["status"] == "drift"
    assert drift["requires_user_choice"] is True


def test_onboarding_reports_partial_review_drift_and_duplicates(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    home = tmp_path / "home"
    project.mkdir()
    home.mkdir()
    _copy_recommendations(project)
    manifest = load_recommendation_manifest(project)
    group = next(group for group in manifest.groups if group.id == "obsidian")
    first = group.skills[0].name
    _write_skill(project, first)
    _write_installer_lock(
        project,
        scope="project",
        names=[first],
        source="kepano/obsidian-skills",
        source_repository=group.source_repository,
    )

    partial = build_skill_onboarding_report(project, home_root=home)
    assert partial["groups"][0]["status"] == "partial"
    assert partial["requires_user_choice"] is True

    names = _install_group(project, home, group_id="obsidian", scope="project")
    project.joinpath(".agents/skills", names[0], "local-note.txt").write_text(
        "local drift",
        encoding="utf-8",
    )
    drift = build_skill_onboarding_report(project, home_root=home)
    assert drift["groups"][0]["status"] == "installed"
    assert drift["requires_user_choice"] is False
    assert any(
        "content differs from reviewed tree" in item
        for item in drift["groups"][0]["attention"]
    )

    _install_group(project, home, group_id="obsidian", scope="global")
    duplicate = build_skill_onboarding_report(project, home_root=home)
    assert duplicate["groups"][0]["duplicate"] is True
    assert duplicate["groups"][0]["duplicates"] == sorted(names)
    assert duplicate["requires_user_choice"] is False


def test_skip_revision_change_and_reset_control_reprompting(tmp_path: Path) -> None:
    project = tmp_path / "project"
    home = tmp_path / "home"
    project.mkdir()
    home.mkdir()
    _copy_recommendations(project)

    skipped = configure_onboarding(
        project,
        group_id="obsidian",
        scope="skip",
        agents=[],
        reset=False,
        home_root=home,
    )
    assert skipped["skill_onboarding"]["groups"][0]["status"] == "skipped"
    assert skipped["skill_onboarding"]["requires_user_choice"] is False

    manifest_path = project / "system/skills/recommendations.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["revision"] = 2
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    stale = build_skill_onboarding_report(project, home_root=home)
    assert stale["groups"][0]["status"] == "stale"
    assert stale["requires_user_choice"] is True

    reset = configure_onboarding(
        project,
        group_id="obsidian",
        scope=None,
        agents=[],
        reset=True,
        home_root=home,
    )
    assert reset["skill_onboarding"]["groups"][0]["status"] == "missing"
    assert reset["skill_onboarding"]["requires_user_choice"] is True
    state = json.loads(project.joinpath(ONBOARDING_STATE_PATH).read_text(encoding="utf-8"))
    assert state["groups"] == {}


def test_skills_status_and_skip_configuration_cli(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    project.joinpath("career-os.toml").write_text("", encoding="utf-8")
    _copy_recommendations(project)
    runner = CliRunner()

    status = runner.invoke(
        app,
        ["skills", "status", "--json", "--root", str(project)],
    )
    configured = runner.invoke(
        app,
        [
            "skills",
            "configure",
            "--group",
            "obsidian",
            "--scope",
            "skip",
            "--root",
            str(project),
        ],
    )

    assert status.exit_code == 0, status.stdout
    assert json.loads(status.stdout)["schema"] == "career-os-skill-onboarding/1"
    assert configured.exit_code == 0, configured.stdout
    assert json.loads(configured.stdout)["skill_onboarding"]["requires_user_choice"] is False


def test_repository_skill_inventory_and_recommendations_are_valid() -> None:
    project_root = PROJECT_ROOT

    failures = [item for item in verify_skills(project_root) if item.status == "fail"]

    assert not failures
    actual = {
        path.name
        for path in project_root.joinpath(".agents/skills").iterdir()
        if path.joinpath("SKILL.md").is_file()
    }
    assert actual == PROJECT_SKILLS
    assert not project_root.joinpath("skills-lock.json").exists()
    ignored = project_root.joinpath(".gitignore").read_text(encoding="utf-8").splitlines()
    for name in AUXILIARY_SKILLS:
        assert f"/.agents/skills/{name}/" in ignored
        assert f"/.claude/skills/{name}" in ignored
    assert "/skills-lock.json" in ignored


def test_skill_verify_allows_known_optional_subset_but_rejects_unknown(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _copy_recommendations(project)
    fixture_target = project / "system/tests/fixtures"
    fixture_target.mkdir(parents=True)
    for name in ("skill-selection-prompts.json", "skill-selection-oracle.json"):
        shutil.copy2(PROJECT_ROOT / "system/tests/fixtures" / name, fixture_target / name)
    for name in sorted(PROJECT_SKILLS | {"json-canvas"}):
        _write_skill(project, name)
        _write_projection(project, name)

    known_failures = [
        item for item in verify_skills(project) if item.status == "fail"
    ]
    assert not known_failures

    _write_skill(project, "unknown-extra")
    _write_projection(project, "unknown-extra")
    unknown = next(
        item for item in verify_skills(project) if item.id == "skills.inventory"
    )
    assert unknown.status == "fail"
    assert "unknown-extra" in unknown.detail


def test_retired_research_skills_are_absent() -> None:
    project_root = Path(__file__).resolve().parents[2]
    opencli_skills = {
        path.name
        for path in project_root.joinpath(".agents/skills").glob("opencli-*")
        if path.is_dir()
    }
    assert not opencli_skills
    assert not project_root.joinpath(".agents/skills/defuddle").exists()
    opportunity = project_root.joinpath(
        ".agents/skills/opportunity-decision/SKILL.md"
    ).read_text(encoding="utf-8")
    assert "OpenCLI" not in opportunity
    assert "official and regulatory sources" in opportunity


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
    multi_authority_cases = [
        case
        for case in oracle["cases"]
        if len({item["skill"] for item in case["selected"]}) > 1
    ]
    assert len(multi_authority_cases) >= 6
    assert (
        sum(
            len({item["skill"] for item in case["selected"]}) >= 3
            for case in multi_authority_cases
        )
        >= 3
    )
    assert {
        item["skill"]
        for case in multi_authority_cases
        for item in case["selected"]
    } == PROJECT_SKILLS
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
    single_skill_cases = [
        (
            {**case, "selected": case["selected"][:1]}
            if case["id"] == "compose-offer-horizon-wording"
            else case
        )
        for case in oracle["cases"]
    ]
    report.write_text(
        json.dumps({"schema_version": 1, "cases": single_skill_cases}),
        encoding="utf-8",
    )
    single_skill_result = evaluate_skill_selection_report(project_root, report)
    assert single_skill_result.status == "fail"
    assert single_skill_result.detail == (
        "mismatched cases: compose-offer-horizon-wording"
    )

    default_checks = verify_skills(project_root)
    blind = next(item for item in default_checks if item.id == "skills.blind-selection")
    assert blind.status == "attention"
    assert "career-os skills verify --selection-report" in blind.detail
