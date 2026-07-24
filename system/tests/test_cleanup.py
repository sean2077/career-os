from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from career_os import cleanup
from career_os.cleanup import CleanupError, cleanup_project
from career_os.cli import app
from career_os.config import resolve_paths
from typer.testing import CliRunner


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _project(tmp_path: Path, *, build_root: str = "build") -> Path:
    root = tmp_path / "project"
    root.mkdir()
    _git(root, "init", "--initial-branch=main")
    _git(root, "config", "user.name", "Cleanup Test")
    _git(root, "config", "user.email", "cleanup@example.invalid")
    _git(root, "config", "core.autocrlf", "false")
    root.joinpath("career-os.toml").write_text(
        f"""schema_version = 2
system_version = "0.1.0"
build_root = "{build_root}"
""",
        encoding="utf-8",
        newline="\n",
    )
    root.joinpath(".gitignore").write_text(
        f""".career-os/
.venv/
.oma/
.obsidian/
{build_root}/
career/ignored-local.md
runtime/
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.pyc
""",
        encoding="utf-8",
        newline="\n",
    )
    root.joinpath("career").mkdir()
    root.joinpath("career/tracked.md").write_text("tracked\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "test: initialize cleanup project")
    return root


def _write_state(root: Path, *, build_root: str = "build") -> dict[str, Path]:
    paths = {
        "build": root / f"{build_root}/output.bin",
        "cache": root / "system/tools/career_os/pkg/__pycache__/module.pyc",
        "generated": root / ".career-os/generated/projection.tex",
        "temporary": root / ".career-os/tmp/work.txt",
        "font": root / ".career-os/fonts/Reusable.otf",
        "venv": root / ".venv/Lib/site.py",
        "unknown": root / ".career-os/mystery.bin",
        "migration": root / ".career-os/migrations/plans/active.json",
        "data": root / "career/ignored-local.md",
        "runtime": root / "runtime/raw.json",
        "local": root / ".oma/session.json",
    }
    for name, path in paths.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode())
    return paths


def test_cleanup_only_handles_known_reproducible_roots(tmp_path: Path) -> None:
    root = _project(tmp_path)
    paths = _write_state(root)
    tracked_build = root / "build/tracked.txt"
    tracked_build.write_text("tracked build exception\n", encoding="utf-8")
    _git(root, "add", "-f", "build/tracked.txt")
    _git(root, "commit", "-m", "test: track protected build fixture")

    dry_run = cleanup_project(root)

    assert dry_run.mode == "dry-run"
    assert {entry.path for entry in dry_run.entries if entry.action == "delete"} == {
        ".career-os/generated/projection.tex",
        ".career-os/tmp/work.txt",
        "build/output.bin",
        "system/tools/career_os/pkg/__pycache__/module.pyc",
    }
    assert all(path.exists() for path in paths.values())
    assert all(entry.action == "delete" for entry in dry_run.entries)

    applied = cleanup_project(root, apply=True)

    assert applied.ok
    assert set(applied.deleted) == {
        ".career-os/generated/projection.tex",
        ".career-os/tmp/work.txt",
        "build/output.bin",
        "system/tools/career_os/pkg/__pycache__/module.pyc",
    }
    assert tracked_build.read_text(encoding="utf-8") == "tracked build exception\n"
    for name in ("font", "venv", "unknown", "migration", "data", "runtime", "local"):
        assert paths[name].is_file()
    assert cleanup_project(root, apply=True).deleted == ()


def test_cleanup_uses_configured_build_root(tmp_path: Path) -> None:
    root = _project(tmp_path, build_root="output")
    target = root / "output/output.bin"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"output")

    report = cleanup_project(root)

    assert {entry.path for entry in report.entries} == {"output/output.bin"}
    assert target.is_file()


def test_cleanup_reports_json_and_human_output_for_known_cache(tmp_path: Path) -> None:
    root = _project(tmp_path)
    cache = root / ".pytest_cache/state"
    cache.parent.mkdir()
    cache.write_text("cache", encoding="utf-8")

    json_result = CliRunner().invoke(
        app,
        ["cleanup", "--root", str(root), "--json"],
    )
    human_result = CliRunner().invoke(app, ["cleanup", "--root", str(root)])

    assert json_result.exit_code == 0, json_result.stdout
    payload = json.loads(json_result.stdout)
    assert payload["mode"] == "dry-run"
    assert payload["summary"]["delete"] == {"files": 1, "bytes": 5}
    assert payload["candidates"][0]["path"] == ".pytest_cache/state"
    assert payload["preserved"] == []
    assert human_result.exit_code == 0, human_result.stdout
    assert "Would delete 1 files (5 bytes)" in human_result.stdout
    assert cache.is_file()


def test_cleanup_keeps_links_inside_known_roots(tmp_path: Path) -> None:
    root = _project(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    link = root / ".career-os/tmp/outside-link"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(outside)
    except OSError as error:
        pytest.skip(f"local platform does not permit symlinks: {error}")

    report = cleanup_project(root, apply=True)

    entry = next(item for item in report.entries if item.path.endswith("outside-link"))
    assert entry.category == "protected-links"
    assert entry.action == "keep"
    assert link.is_symlink()
    assert outside.read_text(encoding="utf-8") == "outside\n"


def test_cleanup_rejects_escaped_git_enumeration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    monkeypatch.setattr(
        "career_os.cleanup._ignored_untracked_files",
        lambda _root, _pathspecs: ["../outside.txt"],
    )

    with pytest.raises(CleanupError, match="unsafe cleanup path"):
        cleanup_project(root)


def test_cleanup_aborts_before_delete_when_candidate_fingerprint_drifts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    target = root / "build/output.bin"
    target.parent.mkdir()
    target.write_text("first", encoding="utf-8")
    original = cleanup._regular_file_fingerprint
    changed = False

    def drifting_fingerprint(
        project_root: Path, path: Path
    ) -> tuple[int, str | None] | None:
        nonlocal changed
        if path == target and not changed:
            changed = True
            target.write_text("second", encoding="utf-8")
        return original(project_root, path)

    monkeypatch.setattr(cleanup, "_regular_file_fingerprint", drifting_fingerprint)

    report = cleanup_project(root, apply=True)

    assert not report.ok
    assert report.deleted == ()
    assert target.read_text(encoding="utf-8") == "second"
    assert "content changed during preflight" in report.errors[0]


def test_cleanup_reports_delete_failures_and_remains_retryable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    target = root / "build/locked.bin"
    target.parent.mkdir()
    target.write_text("locked", encoding="utf-8")
    original_unlink = Path.unlink

    def locked_unlink(path: Path, *args: object, **kwargs: object) -> None:
        if path == target:
            raise PermissionError("file is locked")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", locked_unlink)

    report = cleanup_project(root, apply=True)

    assert not report.ok
    assert report.deleted == ()
    assert target.is_file()
    assert "file is locked" in report.errors[0]


def test_cleanup_pathspecs_exclude_private_and_migration_state(tmp_path: Path) -> None:
    root = _project(tmp_path)
    paths = resolve_paths(root)

    pathspecs = cleanup._known_pathspecs(paths)

    assert "." not in pathspecs
    assert all(".venv" not in path for path in pathspecs)
    assert all("migrations" not in path for path in pathspecs)
    assert all("fonts" not in path for path in pathspecs)
    assert ".career-os/generated" in pathspecs
    assert ".career-os/tmp" in pathspecs
    assert "build" in pathspecs
