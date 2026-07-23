from __future__ import annotations

import subprocess
from pathlib import Path

from career_os.git_safety import inspect_downstream_git_safety


def _git(root: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )


def _issues(root: Path) -> dict[str, str]:
    return {
        item.id: item.status
        for item in inspect_downstream_git_safety(root, initialized=True)
    }


def test_initialized_downstream_allows_no_public_upstream(tmp_path: Path) -> None:
    _git(tmp_path, "init")

    issues = _issues(tmp_path)

    assert issues["git.public-upstream"] == "pass"
    assert issues["git.personal-origin"] == "pass"
    assert "git.public-upstream-name" not in issues
    assert "git.public-upstream-push" not in issues


def test_configured_public_upstream_requires_non_pushable_url(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "remote", "add", "upstream", "https://github.com/sean2077/career-os.git")

    assert _issues(tmp_path)["git.public-upstream-push"] == "fail"

    _git(tmp_path, "remote", "set-url", "--push", "upstream", "DISABLED")

    assert _issues(tmp_path)["git.public-upstream-push"] == "pass"


def test_public_repository_cannot_remain_personal_origin(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "remote", "add", "origin", "git@github.com:sean2077/career-os.git")
    _git(tmp_path, "remote", "set-url", "--push", "origin", "DISABLED")

    issues = _issues(tmp_path)

    assert issues["git.public-upstream-name"] == "fail"
    assert issues["git.personal-origin"] == "fail"


def test_uninitialized_public_source_checkout_does_not_enforce_downstream_policy(
    tmp_path: Path,
) -> None:
    issues = inspect_downstream_git_safety(tmp_path, initialized=False)

    assert [(item.id, item.status) for item in issues] == [
        ("git.downstream-remote-safety", "pass")
    ]
