from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PUBLIC_UPSTREAM_URL = "https://github.com/sean2077/career-os.git"
BLOCKED_PUSH_URL = "DISABLED"


@dataclass(frozen=True)
class GitSafetyIssue:
    id: str
    status: Literal["pass", "attention", "fail"]
    path: str | None
    detail: str


def inspect_downstream_git_safety(
    project_root: Path, *, initialized: bool
) -> list[GitSafetyIssue]:
    """Inspect local remotes without contacting or changing any remote repository."""
    if not initialized:
        return [
            GitSafetyIssue(
                "git.downstream-remote-safety",
                "pass",
                None,
                "not an initialized personal downstream; remote guard is not applicable",
            )
        ]

    try:
        remotes = _git_lines(project_root, "remote")
        fetch_urls = {
            remote: _git_lines(project_root, "remote", "get-url", "--all", remote)
            for remote in remotes
        }
    except (OSError, subprocess.CalledProcessError) as error:
        return [GitSafetyIssue("git.remote-inventory", "fail", None, str(error))]

    public_remotes = sorted(
        remote
        for remote, urls in fetch_urls.items()
        if any(_is_public_upstream(url) for url in urls)
    )
    issues: list[GitSafetyIssue] = []
    if not public_remotes:
        issues.append(
            GitSafetyIssue(
                "git.public-upstream",
                "pass",
                None,
                "optional public Career OS upstream is not configured",
            )
        )
    elif public_remotes != ["upstream"]:
        issues.append(
            GitSafetyIssue(
                "git.public-upstream-name",
                "fail",
                ", ".join(public_remotes),
                "when configured, the public Career OS remote must be named upstream",
            )
        )
    else:
        issues.append(
            GitSafetyIssue(
                "git.public-upstream-name",
                "pass",
                "upstream",
                "canonical public remote is named upstream",
            )
        )
        try:
            push_urls = _git_config_values(project_root, "remote.upstream.pushurl")
        except (OSError, subprocess.CalledProcessError) as error:
            issues.append(
                GitSafetyIssue(
                    "git.public-upstream-push", "fail", "upstream", str(error)
                )
            )
        else:
            blocked = push_urls == [BLOCKED_PUSH_URL]
            issues.append(
                GitSafetyIssue(
                    "git.public-upstream-push",
                    "pass" if blocked else "fail",
                    "upstream",
                    (
                        "public upstream has an explicit non-push URL"
                        if blocked
                        else "public upstream is pushable; run: git remote set-url "
                        "--push upstream DISABLED"
                    ),
                )
            )

    if "origin" not in remotes:
        issues.append(
            GitSafetyIssue(
                "git.personal-origin",
                "pass",
                None,
                "no personal push remote is configured",
            )
        )
    elif any(_is_public_upstream(url) for url in fetch_urls["origin"]):
        issues.append(
            GitSafetyIssue(
                "git.personal-origin",
                "fail",
                "origin",
                "origin points to the public Career OS repository; remove it or rename "
                "it to upstream and disable its push URL",
            )
        )
    else:
        issues.append(
            GitSafetyIssue(
                "git.personal-origin",
                "attention",
                "origin",
                "remote visibility cannot be verified offline; confirm that origin is "
                "private before the first push",
            )
        )
    return issues


def _git_lines(project_root: Path, *arguments: str) -> list[str]:
    completed = subprocess.run(
        ["git", "-C", str(project_root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _git_config_values(project_root: Path, key: str) -> list[str]:
    completed = subprocess.run(
        ["git", "-C", str(project_root), "config", "--get-all", key],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 1:
        return []
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(
            completed.returncode,
            completed.args,
            output=completed.stdout,
            stderr=completed.stderr,
        )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _is_public_upstream(url: str) -> bool:
    normalized = url.strip().lower().replace("\\", "/")
    normalized = normalized.rstrip("/").removesuffix(".git")
    return normalized in {
        PUBLIC_UPSTREAM_URL.lower().removesuffix(".git"),
        "git@github.com:sean2077/career-os",
        "ssh://git@github.com/sean2077/career-os",
    }
