from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from career_os.config import ProjectPaths, resolve_paths

CleanupAction = Literal["delete", "keep", "blocked"]
_CACHE_PARTS = {
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
}
_FIXED_ROOTS = (
    Path(".career-os/generated"),
    Path(".career-os/tmp"),
    Path(".mypy_cache"),
    Path(".pytest_cache"),
    Path(".ruff_cache"),
    Path("dist"),
    Path("htmlcov"),
)
_FIXED_FILES = (Path(".coverage"), Path("coverage.xml"))
_GLOB_PATHSPECS = (
    ":(glob)system/tests/**/__pycache__/**",
    ":(glob)system/tools/career_os/**/__pycache__/**",
    ":(glob)system/tools/*.egg-info/**",
)


class CleanupError(RuntimeError):
    """Raised when known cleanup targets cannot be handled safely."""


@dataclass(frozen=True)
class CleanupEntry:
    path: str
    category: str
    action: CleanupAction
    reason: str
    size: int
    fingerprint: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": self.path,
            "category": self.category,
            "action": self.action,
            "reason": self.reason,
            "bytes": self.size,
        }
        if self.fingerprint is not None:
            payload["sha256"] = self.fingerprint
        return payload


@dataclass(frozen=True)
class CleanupReport:
    root: Path
    mode: Literal["dry-run", "apply"]
    entries: tuple[CleanupEntry, ...]
    deleted: tuple[str, ...] = ()
    deleted_bytes: int = 0
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        categories: dict[tuple[str, CleanupAction, str], dict[str, Any]] = {}
        for entry in self.entries:
            key = (entry.category, entry.action, entry.reason)
            summary = categories.setdefault(
                key,
                {
                    "category": entry.category,
                    "action": entry.action,
                    "reason": entry.reason,
                    "files": 0,
                    "bytes": 0,
                },
            )
            summary["files"] += 1
            summary["bytes"] += entry.size
        action_totals = {
            action: {
                "files": sum(1 for entry in self.entries if entry.action == action),
                "bytes": sum(
                    entry.size for entry in self.entries if entry.action == action
                ),
            }
            for action in ("delete", "keep", "blocked")
        }
        return {
            "ok": self.ok,
            "mode": self.mode,
            "root": str(self.root),
            "summary": action_totals,
            "categories": sorted(
                categories.values(),
                key=lambda item: (item["action"], item["category"], item["reason"]),
            ),
            "candidates": [
                entry.as_dict() for entry in self.entries if entry.action == "delete"
            ],
            "preserved": [
                entry.as_dict()
                for entry in self.entries
                if entry.action in {"keep", "blocked"}
            ],
            "deleted": list(self.deleted),
            "deleted_bytes": self.deleted_bytes,
            "errors": list(self.errors),
        }


def cleanup_project(root: Path, *, apply: bool = False) -> CleanupReport:
    """Report or remove ignored files under product-owned reproducible roots."""
    report = _scan(root)
    if not apply:
        return report

    candidates = [entry for entry in report.entries if entry.action == "delete"]
    errors = _preflight(report.root, candidates)
    if errors:
        return CleanupReport(
            root=report.root,
            mode="apply",
            entries=report.entries,
            errors=tuple(errors),
        )

    deleted: list[str] = []
    deleted_bytes = 0
    deleted_paths: list[Path] = []
    for entry in candidates:
        path = _safe_candidate_path(report.root, entry.path)
        try:
            path.unlink()
        except OSError as error:
            errors.append(f"{entry.path}: {error}")
            continue
        deleted.append(entry.path)
        deleted_bytes += entry.size
        deleted_paths.append(path)

    _remove_empty_candidate_directories(report.root, deleted_paths)
    return CleanupReport(
        root=report.root,
        mode="apply",
        entries=report.entries,
        deleted=tuple(deleted),
        deleted_bytes=deleted_bytes,
        errors=tuple(errors),
    )


def _scan(root: Path) -> CleanupReport:
    try:
        paths = resolve_paths(root)
    except (FileNotFoundError, OSError, ValueError) as error:
        raise CleanupError(str(error)) from error
    project_root = paths.project_root.resolve()
    git_root = _git_root(project_root)
    if git_root != project_root:
        raise CleanupError(
            f"project root must be the Git worktree root: {project_root} != {git_root}"
        )

    entries: list[CleanupEntry] = []
    for relative in _ignored_untracked_files(project_root, _known_pathspecs(paths)):
        path = _safe_candidate_path(project_root, relative)
        try:
            info = os.lstat(path)
        except OSError as error:
            raise CleanupError(f"cannot inspect cleanup target {relative}: {error}") from error
        link_reason = _unsafe_link_reason(project_root, path)
        if link_reason is not None:
            entries.append(
                CleanupEntry(
                    relative,
                    "protected-links",
                    "keep",
                    link_reason,
                    info.st_size,
                )
            )
            continue
        if not stat.S_ISREG(info.st_mode):
            entries.append(
                CleanupEntry(
                    relative,
                    "protected-special",
                    "keep",
                    "non-regular entries are never removed",
                    info.st_size,
                )
            )
            continue
        nested_repo = _nested_repository_ancestor(project_root, path)
        if nested_repo is not None:
            entries.append(
                CleanupEntry(
                    relative,
                    "protected-nested-repository",
                    "keep",
                    f"belongs to nested repository at {nested_repo}",
                    info.st_size,
                )
            )
            continue

        category, reason = _classify(relative, paths)
        entries.append(
            CleanupEntry(
                relative,
                category,
                "delete",
                reason,
                info.st_size,
                _sha256(path),
            )
        )

    return CleanupReport(
        root=project_root,
        mode="dry-run",
        entries=tuple(sorted(entries, key=lambda entry: entry.path)),
    )


def _known_pathspecs(paths: ProjectPaths) -> tuple[str, ...]:
    pathspecs = {path.as_posix() for path in (*_FIXED_ROOTS, *_FIXED_FILES)}
    pathspecs.update(_GLOB_PATHSPECS)
    try:
        build = paths.build_root.resolve().relative_to(paths.project_root).as_posix()
    except ValueError:
        pass
    else:
        if build != ".":
            pathspecs.add(build)
    return tuple(sorted(pathspecs))


def _ignored_untracked_files(
    project_root: Path, pathspecs: tuple[str, ...]
) -> list[str]:
    result = _git(
        project_root,
        "ls-files",
        "--others",
        "--ignored",
        "--exclude-standard",
        "-z",
        "--",
        *pathspecs,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise CleanupError(f"Git cleanup-target enumeration failed: {detail}")
    relative_paths: list[str] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        relative = os.fsdecode(raw).replace("\\", "/")
        _validate_relative(relative)
        relative_paths.append(relative)
    return sorted(set(relative_paths))


def _classify(relative: str, paths: ProjectPaths) -> tuple[str, str]:
    pure = PurePosixPath(relative)
    parts = set(pure.parts)
    if _under_root(relative, paths.project_root, paths.build_root):
        return "build-artifacts", "configured build output is reproducible"
    if relative.startswith((".career-os/generated/", ".career-os/tmp/")):
        return "generated-state", "explicit generated or temporary state is reproducible"
    if parts & _CACHE_PARTS or pure.suffix.lower() in {".pyc", ".pyo"}:
        return "development-caches", "Python and verification caches are reproducible"
    if (
        pure.parts[0] in {"dist", "htmlcov"}
        or relative in {".coverage", "coverage.xml"}
        or any(part.endswith(".egg-info") for part in pure.parts)
    ):
        return (
            "distribution-artifacts",
            "distribution and coverage output is reproducible",
        )
    raise CleanupError(f"Git returned a path outside known cleanup roots: {relative}")


def _under_root(relative: str, project_root: Path, root: Path) -> bool:
    try:
        root_relative = root.resolve().relative_to(project_root).as_posix()
    except ValueError:
        return False
    return relative == root_relative or relative.startswith(f"{root_relative}/")


def _preflight(project_root: Path, candidates: list[CleanupEntry]) -> list[str]:
    errors: list[str] = []
    for entry in candidates:
        path = _safe_candidate_path(project_root, entry.path)
        current = _regular_file_fingerprint(project_root, path)
        if current != (entry.size, entry.fingerprint):
            errors.append(f"{entry.path}: content changed during preflight")
    errors.extend(_verify_git_state(project_root, [entry.path for entry in candidates]))
    return errors


def _verify_git_state(project_root: Path, relatives: list[str]) -> list[str]:
    if not relatives:
        return []
    tracked = _git(project_root, "ls-files", "-z", "--", *relatives)
    if tracked.returncode != 0:
        return ["Git tracking preflight failed"]
    tracked_paths = {
        os.fsdecode(raw).replace("\\", "/")
        for raw in tracked.stdout.split(b"\0")
        if raw
    }
    errors = [f"{path}: became tracked during preflight" for path in sorted(tracked_paths)]

    payload = b"".join(os.fsencode(path) + b"\0" for path in relatives)
    ignored = _git(
        project_root,
        "check-ignore",
        "-z",
        "--stdin",
        input_bytes=payload,
    )
    if ignored.returncode not in {0, 1}:
        errors.append("Git ignore preflight failed")
        return errors
    ignored_paths = {
        os.fsdecode(raw).replace("\\", "/")
        for raw in ignored.stdout.split(b"\0")
        if raw
    }
    errors.extend(
        f"{path}: is no longer ignored during preflight"
        for path in relatives
        if path not in ignored_paths
    )
    return errors


def _regular_file_fingerprint(
    project_root: Path, path: Path
) -> tuple[int, str | None] | None:
    if _unsafe_link_reason(project_root, path) is not None:
        return None
    try:
        info = os.lstat(path)
    except OSError:
        return None
    if not stat.S_ISREG(info.st_mode):
        return None
    return info.st_size, _sha256(path)


def _safe_candidate_path(project_root: Path, relative: str) -> Path:
    _validate_relative(relative)
    return project_root.joinpath(*PurePosixPath(relative).parts)


def _validate_relative(relative: str) -> None:
    pure = PurePosixPath(relative)
    if not relative or pure.is_absolute() or ".." in pure.parts or "." in pure.parts:
        raise CleanupError(f"Git returned an unsafe cleanup path: {relative!r}")


def _unsafe_link_reason(project_root: Path, path: Path) -> str | None:
    try:
        relative = path.relative_to(project_root)
    except ValueError:
        return "path escapes the project root"
    current = project_root
    for part in relative.parts:
        current /= part
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            continue
        except OSError as error:
            return f"path component cannot be inspected: {error}"
        attributes = int(getattr(info, "st_file_attributes", 0))
        reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
        if stat.S_ISLNK(info.st_mode) or attributes & reparse_flag:
            return "symbolic links and junctions are never followed or removed"
    return None


def _nested_repository_ancestor(project_root: Path, path: Path) -> Path | None:
    current = path.parent
    while current != project_root:
        if (current / ".git").exists():
            return current
        current = current.parent
    return None


def _remove_empty_candidate_directories(
    project_root: Path, deleted_paths: list[Path]
) -> None:
    protected = {
        project_root,
        project_root / ".career-os",
        project_root / "system",
        project_root / "system/tests",
        project_root / "system/tools",
        project_root / "system/tools/career_os",
    }
    candidates = {
        parent
        for path in deleted_paths
        for parent in path.parents
        if parent.is_relative_to(project_root) and parent not in protected
    }
    for directory in sorted(candidates, key=lambda item: len(item.parts), reverse=True):
        if _unsafe_link_reason(project_root, directory) is not None:
            continue
        try:
            directory.rmdir()
        except OSError:
            continue


def _git_root(path: Path) -> Path:
    result = _git(path, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise CleanupError(f"path is not in an identifiable Git repository: {path}: {detail}")
    return Path(os.fsdecode(result.stdout).strip()).resolve()


def _git(
    path: Path, *arguments: str, input_bytes: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", "-C", str(path), *arguments],
            input=input_bytes,
            check=False,
            capture_output=True,
        )
    except OSError as error:
        raise CleanupError(f"cannot run Git: {error}") from error


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
