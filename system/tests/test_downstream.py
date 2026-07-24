from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from career_os import downstream
from career_os.config import load_project_config, resolve_paths
from career_os.downstream import (
    apply_downstream_sync_plan,
    create_downstream_sync_plan,
    downstream_sync_validation_json_schema,
    rollback_downstream_sync_plan,
    validate_downstream_sync_plan,
)


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _write_source(root: Path) -> str:
    root.mkdir()
    _git(root, "init", "--initial-branch=main")
    _git(root, "config", "user.name", "Career OS Test")
    _git(root, "config", "user.email", "career-os@example.invalid")
    _git(root, "config", "core.autocrlf", "false")
    root.joinpath("career-os.toml").write_text(
        """#:schema ./system/schemas/project-config.schema.json
schema_version = 2
system_version = "1.0.0"
development_topology = "standalone-framework"
build_root = "build"
preferred_language = "en"

[obsidian]
minimum_version = "1.12.7"
quickadd_version = "2.12.3"

[resume]
engine = "xelatex"
""",
        encoding="utf-8",
        newline="\n",
    )
    root.joinpath("README.md").write_text("base\n", encoding="utf-8")
    root.joinpath(".gitignore").write_text(".career-os/\n", encoding="utf-8")
    implementation = root / "system/tools/career_os"
    implementation.mkdir(parents=True)
    implementation.joinpath("marker.py").write_text('VALUE = "base"\n', encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "feat: initialize source")
    return _git(root, "rev-parse", "HEAD")


def _clone_downstream(source: Path, target: Path) -> None:
    subprocess.run(
        ["git", "clone", "--no-local", str(source), str(target)],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(target, "config", "user.name", "Career Home Test")
    _git(target, "config", "user.email", "career-home@example.invalid")
    _git(target, "config", "core.autocrlf", "false")
    _git(target, "remote", "rename", "origin", "upstream")
    _git(target, "remote", "set-url", "--push", "upstream", "DISABLED")
    config = target / "career-os.toml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            'development_topology = "standalone-framework"',
            'development_topology = "split-downstream"',
        ),
        encoding="utf-8",
        newline="\n",
    )
    private = target / "career/private.md"
    private.parent.mkdir()
    private.write_text("private\n", encoding="utf-8")
    _git(target, "add", "career-os.toml", "career/private.md")
    _git(target, "commit", "-m", "chore: initialize private downstream")
    _git(target, "switch", "-c", "sync/test")


def test_integrated_workbench_rejects_downstream_sync(
    repositories: tuple[Path, Path],
) -> None:
    source, target = repositories
    source_commit = _update_source(source)
    config = target / "career-os.toml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            'development_topology = "split-downstream"',
            'development_topology = "integrated-workbench"',
        ),
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(ValueError, match="integrated-workbench changes are developed in place"):
        create_downstream_sync_plan(
            resolve_paths(target),
            source_kind="local",
            source_root=source,
            commit=source_commit,
            tag=None,
        )


def _update_source(source: Path) -> str:
    source.joinpath("README.md").write_text("updated\n", encoding="utf-8")
    source.joinpath("system/tools/career_os/marker.py").write_text(
        'VALUE = "updated"\n', encoding="utf-8"
    )
    source.joinpath("system/new.txt").write_text("new\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "feat: update system snapshot")
    return _git(source, "rev-parse", "HEAD")


@pytest.fixture
def repositories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path]:
    source = tmp_path / "career-os"
    target = tmp_path / "career-home"
    _write_source(source)
    _clone_downstream(source, target)
    monkeypatch.setattr(
        downstream, "_require_downstream_safety", lambda _root, **_kwargs: None
    )
    return source, target


def test_local_source_sync_does_not_require_public_upstream(tmp_path: Path) -> None:
    source = tmp_path / "career-os"
    target = tmp_path / "career-home"
    _write_source(source)
    _clone_downstream(source, target)
    _git(target, "remote", "remove", "upstream")
    source_commit = _update_source(source)

    plan, plan_path = create_downstream_sync_plan(
        resolve_paths(target),
        source_kind="local",
        source_root=source,
        commit=source_commit,
        tag=None,
    )
    applied = apply_downstream_sync_plan(plan_path, resolve_paths(target))
    rolled_back = rollback_downstream_sync_plan(plan_path, resolve_paths(target))

    assert plan.source_kind == "local"
    assert applied.applied_at is not None
    assert rolled_back.rolled_back_at is not None


def test_local_source_sync_supports_unrelated_git_histories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "career-os"
    target = tmp_path / "career-home"
    _write_source(source)
    _write_source(target)
    _git(target, "commit", "--amend", "-m", "chore: create independent home root")

    config = target / "career-os.toml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            'development_topology = "standalone-framework"',
            'development_topology = "split-downstream"',
        ),
        encoding="utf-8",
        newline="\n",
    )
    private = target / "career/private.md"
    private.parent.mkdir()
    private.write_text("private\n", encoding="utf-8")
    _git(target, "add", "career-os.toml", "career/private.md")
    _git(target, "commit", "-m", "chore: initialize independent private downstream")
    _git(target, "switch", "-c", "sync/test")
    monkeypatch.setattr(
        downstream, "_require_downstream_safety", lambda _root, **_kwargs: None
    )

    source_commit = _update_source(source)
    plan, plan_path = create_downstream_sync_plan(
        resolve_paths(target),
        source_kind="local",
        source_root=source,
        commit=source_commit,
        tag=None,
    )
    merge_base = subprocess.run(
        ["git", "-C", str(target), "merge-base", "HEAD", source_commit],
        check=False,
        capture_output=True,
        text=True,
    )
    assert merge_base.returncode == 1

    apply_downstream_sync_plan(plan_path, resolve_paths(target))

    assert target.joinpath("system/new.txt").read_text(encoding="utf-8") == "new\n"
    assert private.read_text(encoding="utf-8") == "private\n"


def test_sync_adapts_standalone_source_config_to_downstream_installation(
    repositories: tuple[Path, Path],
) -> None:
    source, target = repositories
    target_config = target / "career-os.toml"
    target_config.write_text(
        target_config.read_text(encoding="utf-8")
        .replace('build_root = "build"', 'build_root = "local-build"')
        .replace('preferred_language = "en"', 'preferred_language = "zh-CN"')
        + """

[research.opencli]
enabled = true
profile = "career-research"
timeout_seconds = 45
capture_subdir = "research/opencli"

[research.opencli.sources]
weixin = ["search"]
""",
        encoding="utf-8",
        newline="\n",
    )
    _git(target, "add", "career-os.toml")
    _git(target, "commit", "-m", "chore: configure private installation")

    source_config = source / "career-os.toml"
    source_config.write_text(
        source_config.read_text(encoding="utf-8")
        .replace('system_version = "1.0.0"', 'system_version = "1.1.0"')
        .replace('minimum_version = "1.12.7"', 'minimum_version = "1.13.0"'),
        encoding="utf-8",
        newline="\n",
    )
    _git(source, "add", "career-os.toml")
    _git(source, "commit", "-m", "feat: update framework configuration")
    _git(source, "tag", "-a", "v1.1.0", "-m", "release v1.1.0")

    plan, plan_path = create_downstream_sync_plan(
        resolve_paths(target),
        source_kind="local",
        source_root=source,
        commit=None,
        tag="v1.1.0",
    )
    apply_downstream_sync_plan(plan_path, resolve_paths(target))

    adapted = load_project_config(target)
    assert adapted.system_version == "1.1.0"
    assert adapted.development_topology == "split-downstream"
    assert adapted.build_root == "local-build"
    assert adapted.preferred_language == "zh-CN"
    assert adapted.research.opencli.enabled is True
    assert adapted.research.opencli.timeout_seconds == 45
    assert adapted.research.opencli.sources == {"weixin": ["search"]}
    assert adapted.obsidian.minimum_version == "1.13.0"
    assert adapted.resume.engine == "xelatex"
    assert target_config.read_text(encoding="utf-8").startswith(
        "#:schema ./system/schemas/project-config.schema.json\n"
    )

    validation = validate_downstream_sync_plan(
        plan_path,
        target / ".career-os/downstream/downstream-sync.json",
        resolve_paths(target),
    )
    assert plan.target_system_version == "1.0.0"
    assert plan.source_system_version == "1.1.0"
    assert validation.status == "passed"


def test_local_commit_plan_apply_and_rollback_preserve_private_data(
    repositories: tuple[Path, Path],
) -> None:
    source, target = repositories
    source_commit = _update_source(source)
    target_head = _git(target, "rev-parse", "HEAD")

    plan, plan_path = create_downstream_sync_plan(
        resolve_paths(target),
        source_kind="local",
        source_root=source,
        commit=source_commit,
        tag=None,
    )

    assert plan.source_commit == source_commit
    assert set(plan.changed_paths) == {
        "README.md",
        "career-os.toml",
        "system/new.txt",
        "system/tools/career_os/marker.py",
    }
    assert target.joinpath("README.md").read_text(encoding="utf-8") == "base\n"

    applied = apply_downstream_sync_plan(plan_path, resolve_paths(target))

    assert applied.applied_at is not None
    assert _git(target, "rev-parse", "HEAD") == target_head
    assert target.joinpath("README.md").read_text(encoding="utf-8") == "updated\n"
    assert target.joinpath("career/private.md").read_text(encoding="utf-8") == "private\n"
    assert set(_git(target, "diff", "--name-only").splitlines()) == {
        "README.md",
        "career-os.toml",
        "system/tools/career_os/marker.py",
    }
    assert _git(target, "ls-files", "--others", "--exclude-standard") == "system/new.txt"

    reapplied = apply_downstream_sync_plan(plan_path, resolve_paths(target))
    assert reapplied.applied_at == applied.applied_at

    rolled_back = rollback_downstream_sync_plan(plan_path, resolve_paths(target))

    assert rolled_back.rolled_back_at is not None
    assert _git(target, "status", "--short") == ""
    assert target.joinpath("career/private.md").read_text(encoding="utf-8") == "private\n"

    rerolled = rollback_downstream_sync_plan(plan_path, resolve_paths(target))
    assert rerolled.rolled_back_at == rolled_back.rolled_back_at


@pytest.mark.parametrize("reference_kind", ["commit", "tag"])
def test_upstream_supports_exact_commit_and_annotated_tag(
    repositories: tuple[Path, Path], reference_kind: str
) -> None:
    source, target = repositories
    source_commit = _update_source(source)
    commit: str | None = source_commit
    tag: str | None = None
    if reference_kind == "tag":
        tag = "v1.0.0"
        commit = None
        _git(source, "tag", "-a", tag, "-m", "release v1.0.0")

    plan, _plan_path = create_downstream_sync_plan(
        resolve_paths(target),
        source_kind="upstream",
        source_root=None,
        commit=commit,
        tag=tag,
    )

    assert plan.source_kind == "upstream"
    assert plan.reference_kind == reference_kind
    assert plan.source_commit == source_commit
    if tag is not None:
        local_tag = subprocess.run(
            ["git", "-C", str(target), "show-ref", "--verify", f"refs/tags/{tag}"],
            check=False,
            capture_output=True,
            text=True,
        )
        assert local_tag.returncode != 0


@pytest.mark.parametrize(
    "protected_path",
    [
        "career/private.md",
        ".career-os/private.json",
        ".obsidian/workspace.json",
        "runtime/cache.txt",
        "build/output.txt",
    ],
)
def test_source_commit_rejects_every_reserved_private_or_local_root(
    repositories: tuple[Path, Path], protected_path: str,
) -> None:
    source, target = repositories
    private = source / protected_path
    private.parent.mkdir()
    private.write_text("must not sync\n", encoding="utf-8")
    _git(source, "add", "-f", protected_path)
    _git(source, "commit", "-m", "bad: add private data")

    with pytest.raises(ValueError, match="tracks protected private or local state"):
        create_downstream_sync_plan(
            resolve_paths(target),
            source_kind="local",
            source_root=source,
            commit=_git(source, "rev-parse", "HEAD"),
            tag=None,
        )


def test_plan_rejects_dirty_system_paths(repositories: tuple[Path, Path]) -> None:
    source, target = repositories
    source_commit = _update_source(source)
    target.joinpath("README.md").write_text("local edit\n", encoding="utf-8")

    with pytest.raises(ValueError, match="system paths have uncommitted changes"):
        create_downstream_sync_plan(
            resolve_paths(target),
            source_kind="local",
            source_root=source,
            commit=source_commit,
            tag=None,
        )


def test_apply_rejects_stale_downstream_head(repositories: tuple[Path, Path]) -> None:
    source, target = repositories
    source_commit = _update_source(source)
    _plan, plan_path = create_downstream_sync_plan(
        resolve_paths(target),
        source_kind="local",
        source_root=source,
        commit=source_commit,
        tag=None,
    )
    target.joinpath("career/second.md").write_text("private\n", encoding="utf-8")
    _git(target, "add", "career/second.md")
    _git(target, "commit", "-m", "chore: advance private data")

    with pytest.raises(ValueError, match="HEAD changed"):
        apply_downstream_sync_plan(plan_path, resolve_paths(target))


def test_local_tag_must_be_annotated(repositories: tuple[Path, Path]) -> None:
    source, target = repositories
    _update_source(source)
    _git(source, "tag", "lightweight")

    with pytest.raises(ValueError, match="must be tag, found commit"):
        create_downstream_sync_plan(
            resolve_paths(target),
            source_kind="local",
            source_root=source,
            commit=None,
            tag="lightweight",
        )


def test_local_annotated_tag_does_not_create_target_tag(
    repositories: tuple[Path, Path],
) -> None:
    source, target = repositories
    source_commit = _update_source(source)
    _git(source, "tag", "-a", "v1.0.0", "-m", "release v1.0.0")

    plan, _plan_path = create_downstream_sync_plan(
        resolve_paths(target),
        source_kind="local",
        source_root=source,
        commit=None,
        tag="v1.0.0",
    )

    assert plan.source_commit == source_commit
    local_tag = subprocess.run(
        ["git", "-C", str(target), "show-ref", "--verify", "refs/tags/v1.0.0"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert local_tag.returncode != 0


def test_plan_requires_one_exact_reference(repositories: tuple[Path, Path]) -> None:
    source, target = repositories
    source_commit = _update_source(source)

    with pytest.raises(ValueError, match="full 40-character"):
        create_downstream_sync_plan(
            resolve_paths(target),
            source_kind="local",
            source_root=source,
            commit=source_commit[:12],
            tag=None,
        )
    with pytest.raises(ValueError, match="exactly one"):
        create_downstream_sync_plan(
            resolve_paths(target),
            source_kind="local",
            source_root=source,
            commit=source_commit,
            tag="v1.0.0",
        )


def test_apply_rejects_tampered_patch(repositories: tuple[Path, Path]) -> None:
    source, target = repositories
    source_commit = _update_source(source)
    plan, plan_path = create_downstream_sync_plan(
        resolve_paths(target),
        source_kind="local",
        source_root=source,
        commit=source_commit,
        tag=None,
    )
    patch_path = plan_path.parent / plan.patch_file
    patch_path.write_bytes(patch_path.read_bytes() + b"tampered\n")

    with pytest.raises(ValueError, match="patch hash"):
        apply_downstream_sync_plan(plan_path, resolve_paths(target))


def test_plan_requires_an_isolated_non_trunk_branch(
    repositories: tuple[Path, Path],
) -> None:
    source, target = repositories
    source_commit = _update_source(source)
    _git(target, "switch", "main")

    with pytest.raises(ValueError, match="isolated non-trunk branch"):
        create_downstream_sync_plan(
            resolve_paths(target),
            source_kind="local",
            source_root=source,
            commit=source_commit,
            tag=None,
        )


def test_apply_rejects_branch_or_path_drift(
    repositories: tuple[Path, Path],
) -> None:
    source, target = repositories
    source_commit = _update_source(source)
    _plan, plan_path = create_downstream_sync_plan(
        resolve_paths(target),
        source_kind="local",
        source_root=source,
        commit=source_commit,
        tag=None,
    )

    _git(target, "switch", "-c", "sync/other")
    with pytest.raises(ValueError, match="branch changed"):
        apply_downstream_sync_plan(plan_path, resolve_paths(target))

    _git(target, "switch", "sync/test")
    target.joinpath("system/new.txt").write_text("drifted\n", encoding="utf-8")
    with pytest.raises(ValueError, match="system paths have uncommitted changes"):
        apply_downstream_sync_plan(plan_path, resolve_paths(target))


def test_apply_rejects_tampered_plan(repositories: tuple[Path, Path]) -> None:
    source, target = repositories
    source_commit = _update_source(source)
    _plan, plan_path = create_downstream_sync_plan(
        resolve_paths(target),
        source_kind="local",
        source_root=source,
        commit=source_commit,
        tag=None,
    )
    payload = plan_path.read_text(encoding="utf-8").replace(
        '"target_branch": "sync/test"', '"target_branch": "sync/tampered"'
    )
    plan_path.write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match="plan hash"):
        apply_downstream_sync_plan(plan_path, resolve_paths(target))


def test_validate_archives_applied_annotated_tag_evidence(
    repositories: tuple[Path, Path],
) -> None:
    source, target = repositories
    source_commit = _update_source(source)
    _git(source, "tag", "-a", "v1.0.0", "-m", "release v1.0.0")
    plan, plan_path = create_downstream_sync_plan(
        resolve_paths(target),
        source_kind="local",
        source_root=source,
        commit=None,
        tag="v1.0.0",
    )
    apply_downstream_sync_plan(plan_path, resolve_paths(target))
    output = target / ".career-os/downstream/downstream-sync.json"

    validation = validate_downstream_sync_plan(plan_path, output, resolve_paths(target))

    assert validation.status == "passed"
    assert validation.source_tag == "v1.0.0"
    assert validation.source_commit == source_commit
    assert validation.target_branch == "sync/test"
    assert validation.desired_tree == plan.desired_tree
    assert len(validation.checks) == 7
    assert validation.external_actions_performed == []
    assert output.is_file()
    assert downstream_sync_validation_json_schema()["$id"].endswith(
        "downstream-sync-validation.schema.json"
    )

    with pytest.raises(ValueError, match="already exists"):
        validate_downstream_sync_plan(plan_path, output, resolve_paths(target))


def test_validate_rejects_commit_plan_unapplied_plan_and_external_output(
    repositories: tuple[Path, Path],
) -> None:
    source, target = repositories
    source_commit = _update_source(source)
    _commit_plan, commit_plan_path = create_downstream_sync_plan(
        resolve_paths(target),
        source_kind="local",
        source_root=source,
        commit=source_commit,
        tag=None,
    )
    with pytest.raises(ValueError, match="annotated-tag plan"):
        validate_downstream_sync_plan(
            commit_plan_path,
            target / ".career-os/downstream/commit.json",
            resolve_paths(target),
        )

    _git(source, "tag", "-a", "v1.0.0", "-m", "release v1.0.0")
    _tag_plan, tag_plan_path = create_downstream_sync_plan(
        resolve_paths(target),
        source_kind="local",
        source_root=source,
        commit=None,
        tag="v1.0.0",
    )
    with pytest.raises(ValueError, match="has not been applied"):
        validate_downstream_sync_plan(
            tag_plan_path,
            target / ".career-os/downstream/unapplied.json",
            resolve_paths(target),
        )

    apply_downstream_sync_plan(tag_plan_path, resolve_paths(target))
    with pytest.raises(ValueError, match=r"under \.career-os/downstream"):
        validate_downstream_sync_plan(
            tag_plan_path,
            target / "outside.json",
            resolve_paths(target),
        )
