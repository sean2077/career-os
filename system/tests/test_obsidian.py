from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path, PurePosixPath

import pytest
from career_os.adapters.obsidian import (
    build_views,
    detect_repository_context,
    framework_view_assets,
    plan_vault_operation,
    render_quickadd_assets,
    validate_quickadd,
)
from career_os.checks import _check_obsidian_sources
from career_os.cli import app
from career_os.config import (
    InstallState,
    ProjectPaths,
    resolve_paths,
    resolve_vault_path,
    write_install_state,
)
from career_os.operations import apply_plan
from career_os.seed import initialize_data_root
from typer.testing import CliRunner

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

RECENT_BASE_PAIR = (
    Path("en/Recent Changes.base"),
    Path("zh-CN/最近改动.base"),
)
BASE_PAIRS = (
    RECENT_BASE_PAIR,
    (Path("en/Recruiting Channels.base"), Path("zh-CN/招聘渠道.base")),
    (Path("en/JD Screening.base"), Path("zh-CN/JD 筛选工作台.base")),
    (Path("en/Company Portfolio.base"), Path("zh-CN/公司组合.base")),
    (Path("en/Engagement Decisions.base"), Path("zh-CN/招聘互动决策.base")),
    (Path("en/Capability Readiness.base"), Path("zh-CN/能力准备度.base")),
)


def _write_project_config(project: Path) -> None:
    project.joinpath("career-os.toml").write_text(
        """schema_version = 2
system_version = "0.1.0-rc.1"
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


def _copy_framework_assets(project: Path) -> None:
    shutil.copy2(REPOSITORY_ROOT / "Career Home.md", project / "Career Home.md")
    shutil.copy2(REPOSITORY_ROOT / "职业主页.md", project / "职业主页.md")
    shutil.copytree(
        REPOSITORY_ROOT / "system/obsidian",
        project / "system/obsidian",
    )


def _fixture_paths(
    tmp_path: Path, *, host_git: bool = True, nested_git: bool = True
) -> ProjectPaths:
    vault = tmp_path / "vault"
    project = vault / "career-os"
    project.mkdir(parents=True)
    _copy_framework_assets(project)
    _write_project_config(project)
    data = project / "career"
    initialize_data_root(data)
    paths = ProjectPaths(
        project_root=project,
        data_root=data,
        runtime_root=project / ".career-os/runtime",
        build_root=project / "build",
        local_state_root=project / ".career-os",
        vault_root=vault,
        mode="embedded",
    )
    write_install_state(
        project,
        InstallState(
            mode="embedded",
            project_root=".",
            vault_root=str(vault),
            system_version="0.1.0-rc.1",
            languages=["en", "zh-CN"],
        ),
    )
    if host_git:
        _git(vault, "init")
    if nested_git:
        _git(project, "init")
    return paths


def _external_mount_paths(tmp_path: Path) -> ProjectPaths:
    vault = tmp_path / "vault"
    project = tmp_path / "career-home"
    vault.mkdir(parents=True)
    project.mkdir()
    _copy_framework_assets(project)
    _write_project_config(project)
    initialize_data_root(project / "career")
    _git(vault, "init")
    _git(vault, "config", "core.symlinks", "true")
    _git(project, "init")
    mount = vault / "career-home"
    try:
        mount.symlink_to("../career-home", target_is_directory=True)
    except OSError as error:
        pytest.skip(f"local platform does not permit directory symlinks: {error}")
    _git(vault, "add", "career-home")
    assert _git(vault, "cat-file", "-p", ":career-home") == "../career-home"
    write_install_state(
        project,
        InstallState(
            mode="embedded",
            project_root=".",
            vault_root=str(vault),
            vault_mount="career-home",
            system_version="0.1.0-rc.1",
            languages=["en", "zh-CN"],
        ),
    )
    paths = resolve_paths(project)
    return paths


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_framework_views_are_tracked_portable_and_not_generated(tmp_path: Path) -> None:
    paths = _fixture_paths(tmp_path, host_git=False)

    expected = framework_view_assets(paths)
    first = build_views(paths)
    second = build_views(paths)
    assert first == second == list(expected)
    assert len(expected) == 18
    assert expected[0] == paths.project_root / "Career Home.md"
    assert expected[1] == paths.project_root / "职业主页.md"
    assert all(path.is_file() for path in first)
    assert all("__CAREER_OS_" not in path.read_text(encoding="utf-8") for path in first)
    base = paths.project_root / "system/obsidian/records.base"
    base_text = base.read_text(encoding="utf-8")
    assert "name: All records" in base_text
    assert "name: Migration review" in base_text
    assert "file.links" in base_text
    assert "Host reference health" not in base_text
    assert "name: JD screening" not in base_text
    assert "name: Same-company application decision" not in base_text
    assert not paths.runtime_root.exists()


def test_views_build_reports_root_homepage_and_no_generated_assets(tmp_path: Path) -> None:
    paths = _fixture_paths(tmp_path, host_git=False)

    result = CliRunner().invoke(
        app,
        ["views", "build", "--root", str(paths.project_root)],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["asset_root"] == str(paths.project_root / "system/obsidian")
    assert payload["homepage"] == str(paths.project_root / "Career Home.md")
    assert payload["homepages"] == [
        str(paths.project_root / "Career Home.md"),
        str(paths.project_root / "职业主页.md"),
    ]
    assert payload["assets"] == [str(path) for path in framework_view_assets(paths)]
    assert payload["generated"] == []


def test_localized_system_bases_are_portable_and_not_materialized(
    tmp_path: Path,
) -> None:
    paths = _fixture_paths(tmp_path, host_git=False)
    base_root = paths.project_root / "system/obsidian/bases"
    bases = [base_root / relative for pair in BASE_PAIRS for relative in pair]
    authority_bases = [
        base_root / relative for pair in BASE_PAIRS[1:] for relative in pair
    ]
    recent_bases = [base_root / relative for relative in RECENT_BASE_PAIR]

    assert all(path.is_file() for path in bases)
    assert all("__CAREER_OS_" not in path.read_text(encoding="utf-8") for path in bases)
    assert all(
        "file.inFolder(" not in path.read_text(encoding="utf-8")
        for path in authority_bases
    )
    assert all(
        "schema_version == 3" in path.read_text(encoding="utf-8")
        for path in authority_bases
    )
    assert all(
        'file.ext == "md"'
        in path.read_text(encoding="utf-8")
        for path in recent_bases
    )
    assert all(
        'file.inFolder(file("Career Home.md").folder)'
        in path.read_text(encoding="utf-8")
        for path in recent_bases
    )
    assert all(
        "system/obsidian/bases" not in path.read_text(encoding="utf-8")
        for path in recent_bases
    )
    assert not any(paths.data_root.rglob("*.base"))


def test_dedicated_bases_pass_semantic_contracts(tmp_path: Path) -> None:
    paths = _fixture_paths(tmp_path, host_git=False)

    base_issues = [
        issue
        for issue in _check_obsidian_sources(paths)
        if issue.path is not None and issue.path.endswith(".base")
    ]

    assert base_issues
    failures = [issue for issue in base_issues if issue.status != "pass"]
    assert not failures, [(issue.path, issue.detail) for issue in failures]


@pytest.mark.parametrize(
    "relative",
    ["zh-CN/JD 筛选工作台.base", "zh-CN/最近改动.base"],
)
def test_dedicated_base_inventory_is_fail_closed(
    tmp_path: Path, relative: str
) -> None:
    paths = _fixture_paths(tmp_path, host_git=False)
    base = paths.project_root / "system/obsidian/bases" / relative
    base.unlink()

    failures = [issue for issue in _check_obsidian_sources(paths) if issue.status == "fail"]

    assert any("missing required localized Base" in issue.detail for issue in failures)


@pytest.mark.parametrize("filename", ["Career Home.md", "职业主页.md"])
def test_root_homepage_inventory_is_fail_closed(
    tmp_path: Path, filename: str
) -> None:
    paths = _fixture_paths(tmp_path, host_git=False)
    paths.project_root.joinpath(filename).unlink()

    failures = [issue for issue in _check_obsidian_sources(paths) if issue.status == "fail"]

    assert any("missing required root" in issue.detail for issue in failures)


@pytest.mark.parametrize(
    ("relative", "before", "after", "expected"),
    [
        (
            "en/JD Screening.base",
            'kind == "market.jd"',
            'kind == "market.channel"',
            "global filter",
        ),
        (
            "en/JD Screening.base",
            "property: formula.recruiting_scope",
            "property: priority",
            "groupBy",
        ),
        (
            "en/Company Portfolio.base",
            "      - formula.related_engagements\n",
            "",
            "required columns",
        ),
        (
            "en/Recruiting Channels.base",
            "value.asFile().asLink(value.asFile().basename)",
            "value.asFile().asLink()",
            "basename-only",
        ),
        (
            "en/Capability Readiness.base",
            "name: Retest Queue",
            "name: Missing",
            "required views",
        ),
        (
            "en/Recent Changes.base",
            "limit: 10",
            "limit: 11",
            "limit must be 10",
        ),
        (
            "en/Recent Changes.base",
            "file.inFolder",
            "file.hasLink",
            "global filters do not exactly match",
        ),
        (
            "en/Recent Changes.base",
            'file.ext == "md"',
            'file.ext == "base"',
            "global filters do not exactly match",
        ),
        (
            "en/Recent Changes.base",
            "property: file.mtime\n        direction: DESC",
            "property: file.mtime\n        direction: ASC",
            "missing required sort keys",
        ),
    ],
)
def test_dedicated_base_semantics_fail_closed(
    tmp_path: Path, relative: str, before: str, after: str, expected: str
) -> None:
    paths = _fixture_paths(tmp_path, host_git=False)
    base = paths.project_root / "system/obsidian/bases" / relative
    original = base.read_text(encoding="utf-8")
    assert before in original
    base.write_text(original.replace(before, after, 1), encoding="utf-8")

    failures = [issue for issue in _check_obsidian_sources(paths) if issue.status == "fail"]

    assert any(expected in issue.detail for issue in failures)


@pytest.mark.parametrize(
    ("relative", "before", "after", "expected"),
    [
        (
            "zh-CN/招聘渠道.base",
            "displayName: 渠道",
            "displayName: Channel",
            "Chinese display names",
        ),
        (
            "zh-CN/JD 筛选工作台.base",
            "file.name: 288",
            "file.name: 289",
            "columnSize",
        ),
        (
            "zh-CN/公司组合.base",
            '"pending"',
            '"queued"',
            "may differ only",
        ),
        (
            "zh-CN/招聘互动决策.base",
            'kind == "opportunity.engagement"',
            'file.inFolder("career/40-opportunity-decision/engagements")',
            "fixed paths",
        ),
        (
            "zh-CN/最近改动.base",
            "displayName: 文件",
            "displayName: File",
            "Chinese display names",
        ),
    ],
)
def test_localized_base_pairs_fail_closed_on_presentation_or_semantic_drift(
    tmp_path: Path,
    relative: str,
    before: str,
    after: str,
    expected: str,
) -> None:
    paths = _fixture_paths(tmp_path, host_git=False)
    base = paths.project_root / "system/obsidian/bases" / relative
    original = base.read_text(encoding="utf-8")
    assert before in original
    base.write_text(original.replace(before, after, 1), encoding="utf-8")

    failures = [issue for issue in _check_obsidian_sources(paths) if issue.status == "fail"]

    assert any(expected in issue.detail for issue in failures)


def test_localized_base_pair_rejects_unexpected_view(tmp_path: Path) -> None:
    paths = _fixture_paths(tmp_path, host_git=False)
    base = paths.project_root / "system/obsidian/bases/en/Recruiting Channels.base"
    original = base.read_text(encoding="utf-8")
    assert "name: Current Channels" in original
    base.write_text(
        original.replace("name: Current Channels", "name: Extra", 1),
        encoding="utf-8",
    )

    failures = [issue for issue in _check_obsidian_sources(paths) if issue.status == "fail"]

    assert any("required views mismatch" in issue.detail for issue in failures)


def test_nested_attach_is_idempotent_and_detach_restores_host(tmp_path: Path) -> None:
    paths = _fixture_paths(tmp_path)

    attach = plan_vault_operation(
        paths, action="attach", vault_root=paths.vault_root, with_quickadd=False
    )
    assert attach.repository_mode == "independent-nested-repository"
    assert any(operation.path == ".gitignore" for operation in attach.plan.operations)
    applied = apply_plan(attach.path, paths.local_state_root)
    assert applied.applied_at is not None
    assert (paths.vault_root / ".gitignore").read_text(encoding="utf-8") == "/career-os/\n"
    assert not paths.runtime_root.exists()
    assert all(path.is_file() for path in framework_view_assets(paths))

    repeated = plan_vault_operation(
        paths, action="attach", vault_root=paths.vault_root, with_quickadd=False
    )
    assert repeated.plan.operations == []

    detach = plan_vault_operation(
        paths, action="detach", vault_root=paths.vault_root, with_quickadd=False
    )
    detached = apply_plan(detach.path, paths.local_state_root)
    assert detached.applied_at is not None
    assert not (paths.vault_root / ".gitignore").exists()
    assert all(path.is_file() for path in framework_view_assets(paths))
    assert not (paths.project_root / ".career-os/vault-install.json").exists()


def test_external_sibling_symlink_mount_is_portable_and_reversible(tmp_path: Path) -> None:
    paths = _external_mount_paths(tmp_path)

    assert paths.vault_mount_root == paths.vault_root / "career-home"
    assert build_views(paths) == list(framework_view_assets(paths))
    context = detect_repository_context(paths)
    assert context.mode == "independent-sibling-symlink"
    assert context.warnings == ()

    attach = plan_vault_operation(
        paths, action="attach", vault_root=paths.vault_root, with_quickadd=False
    )
    assert attach.repository_mode == "independent-sibling-symlink"
    assert all(operation.path != ".gitignore" for operation in attach.plan.operations)
    applied = apply_plan(attach.path, paths.local_state_root)
    assert applied.applied_at is not None

    repeated = plan_vault_operation(
        paths, action="attach", vault_root=paths.vault_root, with_quickadd=False
    )
    assert repeated.plan.operations == []

    detach = plan_vault_operation(
        paths, action="detach", vault_root=paths.vault_root, with_quickadd=False
    )
    apply_plan(detach.path, paths.local_state_root)
    assert paths.vault_mount_root.is_symlink()
    assert not (paths.project_root / ".career-os/vault-install.json").exists()


def test_linked_worktree_inherits_install_context_and_projects_current_files(
    tmp_path: Path,
) -> None:
    primary = _external_mount_paths(tmp_path)
    _git(
        primary.project_root,
        "add",
        "career-os.toml",
        "Career Home.md",
        "职业主页.md",
        "career",
        "system",
    )
    _git(
        primary.project_root,
        "-c",
        "user.name=Career OS Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-m",
        "fixture",
    )
    worktree = tmp_path / "career-home-worktree"
    _git(
        primary.project_root,
        "worktree",
        "add",
        "-b",
        "test-worktree",
        str(worktree),
    )

    assert not (worktree / ".career-os/install.toml").exists()
    paths = resolve_paths(worktree)
    assert paths.project_root == worktree.resolve()
    assert paths.vault_root == primary.vault_root
    assert paths.vault_mount_root == primary.vault_mount_root
    assert paths.mode == "embedded"
    assert resolve_vault_path(
        paths, "career-home/career/README.md"
    ) == worktree.joinpath("career/README.md").resolve()
    assert detect_repository_context(paths).mode == "independent-sibling-symlink"


def test_attach_plan_rejects_stale_host_configuration(tmp_path: Path) -> None:
    paths = _fixture_paths(tmp_path)
    attach = plan_vault_operation(
        paths, action="attach", vault_root=paths.vault_root, with_quickadd=False
    )
    paths.vault_root.joinpath(".gitignore").write_text("changed\n", encoding="utf-8")

    with pytest.raises(ValueError, match="stale operation target"):
        apply_plan(attach.path, paths.local_state_root)


def test_detach_restores_existing_ignore_bytes(tmp_path: Path) -> None:
    paths = _fixture_paths(tmp_path)
    original = b"# host rules\r\n"
    paths.vault_root.joinpath(".gitignore").write_bytes(original)
    attach = plan_vault_operation(
        paths, action="attach", vault_root=paths.vault_root, with_quickadd=False
    )
    apply_plan(attach.path, paths.local_state_root)
    assert paths.vault_root.joinpath(".gitignore").read_bytes().endswith(b"/career-os/\r\n")

    detach = plan_vault_operation(
        paths, action="detach", vault_root=paths.vault_root, with_quickadd=False
    )
    apply_plan(detach.path, paths.local_state_root)
    assert paths.vault_root.joinpath(".gitignore").read_bytes() == original


def test_attach_never_manages_runtime_view_copies(tmp_path: Path) -> None:
    paths = _fixture_paths(tmp_path, host_git=False)
    target = paths.runtime_root / "obsidian/records.base"
    target.parent.mkdir(parents=True)
    target.write_text("unmanaged\n", encoding="utf-8")

    plan = plan_vault_operation(
        paths, action="attach", vault_root=paths.vault_root, with_quickadd=False
    )
    assert all(operation.root != "runtime" for operation in plan.plan.operations)
    assert target.read_text(encoding="utf-8") == "unmanaged\n"


@pytest.mark.skipif(
    shutil.which("node") is None,
    reason="Node.js is required to exercise the tracked QuickAdd script",
)
def test_quickadd_review_accepts_month_partitioned_jd_paths() -> None:
    script = REPOSITORY_ROOT / "system/obsidian/quickadd/review-jd.js"
    javascript = r"""
const { validateBaseRecord } = require(process.argv[1]);
const frontmatter = {
  kind: "market.jd",
  schema_version: 3,
  updated_at: "2026-07-28T12:00:00+08:00",
};

for (const path of [
  "career-home/career/30-role-market/jds/example.md",
  "career-home/career/30-role-market/jds/2026-07/example.md",
]) {
  validateBaseRecord({ path, extension: "md" }, frontmatter);
}

for (const path of [
  "career-home/career/30-role-market/jds/archive/example.md",
  "career-home/career/30-role-market/jds/2026-07/archive/example.md",
]) {
  try {
    validateBaseRecord({ path, extension: "md" }, frontmatter);
  } catch (error) {
    if (error.message.includes("不在规范目录")) {
      continue;
    }
    throw error;
  }
  throw new Error(`non-canonical JD path was accepted: ${path}`);
}
"""
    result = subprocess.run(
        ["node", "-e", javascript, str(script)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_quickadd_version_and_choice_conflicts_are_fail_closed(tmp_path: Path) -> None:
    paths = _fixture_paths(tmp_path, host_git=False)
    plugin = paths.vault_root / ".obsidian/plugins/quickadd"
    with pytest.raises(ValueError, match="not installed"):
        validate_quickadd(paths)
    plugin.mkdir(parents=True)
    plugin.joinpath("manifest.json").write_text(
        json.dumps({"id": "quickadd", "version": "2.12.2"}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="2.12.3 is required"):
        validate_quickadd(paths)

    plugin.joinpath("manifest.json").write_text(
        json.dumps({"id": "quickadd", "version": "2.12.3"}), encoding="utf-8"
    )
    assert validate_quickadd(paths)
    quickadd_plan = plan_vault_operation(
        paths, action="attach", vault_root=paths.vault_root, with_quickadd=True
    )
    assert any(
        operation.path == ".career-os/obsidian/quickadd/capture-choice.json"
        for operation in quickadd_plan.plan.operations
    )
    assert any(
        operation.path == ".career-os/obsidian/quickadd/jd-review-choice.json"
        for operation in quickadd_plan.plan.operations
    )
    assert any(
        operation.path == ".career-os/obsidian/quickadd/engagement-event-choice.json"
        for operation in quickadd_plan.plan.operations
    )
    assets = render_quickadd_assets(paths)
    assert PurePosixPath(".career-os/obsidian/quickadd/capture-choice.json") in assets
    review_choice = json.loads(
        assets[PurePosixPath(".career-os/obsidian/quickadd/jd-review-choice.json")]
    )
    assert review_choice["name"] == "Career OS: Review active record"
    assert review_choice["macro"]["commands"] == [
        {
            "id": "21328192-ce35-457e-adbb-536d01edb11b",
            "name": "review-jd",
            "type": "UserScript",
            "path": "career-os/system/obsidian/quickadd/review-jd.js",
            "settings": {},
        }
    ]
    event_choice = json.loads(
        assets[
            PurePosixPath(
                ".career-os/obsidian/quickadd/engagement-event-choice.json"
            )
        ]
    )
    assert event_choice["id"] == "ef9c05a5-0143-4c84-8a45-2d3f85618849"
    assert event_choice["name"] == "Career OS: Record engagement event"
    assert event_choice["macro"]["commands"] == [
        {
            "id": "49638cc3-c3d2-447e-a56d-637724b53fb8",
            "name": "record-engagement-event",
            "type": "UserScript",
            "path": (
                "career-os/system/obsidian/quickadd/"
                "record-engagement-event.js"
            ),
            "settings": {},
        }
    ]
    assert not plugin.joinpath("data.json").exists()

    plugin.joinpath("data.json").write_text(
        json.dumps({"choices": [review_choice]}),
        encoding="utf-8",
    )
    assert validate_quickadd(paths) == (
        "QuickAdd choice 'Career OS: Review active record' is already configured.",
    )

    stale_review_choice = dict(review_choice)
    stale_review_choice["name"] = "Career OS: Review active JD"
    plugin.joinpath("data.json").write_text(
        json.dumps({"choices": [stale_review_choice]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="choice id conflicts"):
        validate_quickadd(paths)

    plugin.joinpath("data.json").write_text(
        json.dumps(
            {
                "choices": [
                    {
                        "id": "different",
                        "name": "Career OS: Capture evidence",
                        "type": "Capture",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="choice name conflicts"):
        validate_quickadd(paths)


def test_repository_modes_cover_non_git_submodule_and_bare_gitlink(tmp_path: Path) -> None:
    non_git = _fixture_paths(tmp_path / "plain", host_git=False, nested_git=False)
    assert detect_repository_context(non_git).mode == "non-git-host"

    submodule = _fixture_paths(tmp_path / "submodule")
    _git(submodule.project_root, "add", ".")
    _git(
        submodule.project_root,
        "-c",
        "user.name=Career OS Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-m",
        "fixture",
    )
    commit = _git(submodule.project_root, "rev-parse", "HEAD")
    _git(
        submodule.vault_root,
        "update-index",
        "--add",
        "--cacheinfo",
        f"160000,{commit},career-os",
    )
    submodule.vault_root.joinpath(".gitmodules").write_text(
        '[submodule "career-os"]\n\tpath = career-os\n\turl = ../career-os.git\n',
        encoding="utf-8",
    )
    assert detect_repository_context(submodule).mode == "standard-submodule"

    submodule.vault_root.joinpath(".gitmodules").unlink()
    bare = detect_repository_context(submodule)
    assert bare.mode == "bare-gitlink"
    assert "no .gitmodules repair" in bare.warnings[0]
