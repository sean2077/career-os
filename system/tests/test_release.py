from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from career_os.cli import app
from career_os.release_notes import (
    ReleaseNotesError,
    extract_release_notes,
    write_release_notes,
)
from ruamel.yaml import YAML
from typer.testing import CliRunner

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
UPSTREAM_REPOSITORY_GUARD = "github.repository == 'sean2077/career-os'"


def _write_config(root: Path, version: str = "0.1.0-rc.2") -> None:
    root.joinpath("career-os.toml").write_text(
        f'''schema_version = 2
system_version = "{version}"
build_root = "build"
preferred_language = "en"

[obsidian]
minimum_version = "1.12.7"
quickadd_version = "2.12.3"

[resume]
engine = "xelatex"
''',
        encoding="utf-8",
    )


def test_extract_release_notes_matches_one_exact_heading_outside_fences() -> None:
    changelog = """# Changelog

```markdown
## [v0.1.0-rc.2] — 2026-07-21
not release notes
```

## [v0.1.0-rc.2] — 2026-07-21

### Added

- Real release notes.

## [v0.1.0-rc.1] — 2026-07-20

- Earlier notes.
"""

    assert extract_release_notes(changelog, "v0.1.0-rc.2") == (
        "### Added\n\n- Real release notes.\n"
    )


@pytest.mark.parametrize(
    ("heading", "message"),
    [
        ("## [v0.1.0-rc.3] — 2026-07-21", "no level-two"),
        ("## [v0.1.0-rc.2] - 2026-07-21", "must be"),
        ("## [v0.1.0-rc.2] — 2026-02-30", "invalid calendar"),
        ("## [v0.1.0-rc.2] — 2026-07-21", "empty"),
    ],
)
def test_extract_release_notes_fails_closed(heading: str, message: str) -> None:
    text = f"# Changelog\n\n{heading}\n"
    with pytest.raises(ReleaseNotesError, match=message):
        extract_release_notes(text, "v0.1.0-rc.2")


def test_extract_release_notes_rejects_duplicate_exact_sections() -> None:
    section = "## [v0.1.0-rc.2] — 2026-07-21\n\n- Notes.\n"
    with pytest.raises(ReleaseNotesError, match="multiple"):
        extract_release_notes(f"# Changelog\n\n{section}\n{section}", "v0.1.0-rc.2")


def test_write_release_notes_preserves_existing_output_on_failure(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    output = tmp_path / "notes.md"
    changelog.write_text("# Changelog\n", encoding="utf-8")
    output.write_text("sentinel\n", encoding="utf-8")

    with pytest.raises(ReleaseNotesError):
        write_release_notes(changelog, "v0.1.0-rc.2", output)

    assert output.read_text(encoding="utf-8") == "sentinel\n"


def test_release_notes_cli_joins_tag_config_and_changelog(tmp_path: Path) -> None:
    _write_config(tmp_path)
    tmp_path.joinpath("CHANGELOG.md").write_text(
        "# Changelog\n\n## [v0.1.0-rc.2] — 2026-07-21\n\n- Ready.\n",
        encoding="utf-8",
    )
    output = tmp_path / "notes.md"

    result = CliRunner().invoke(
        app,
        [
            "release",
            "notes",
            "--tag",
            "v0.1.0-rc.2",
            "--output",
            str(output),
            "--root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["tag"] == "v0.1.0-rc.2"
    assert output.read_text(encoding="utf-8") == "- Ready.\n"

    mismatch = CliRunner().invoke(
        app,
        [
            "release",
            "notes",
            "--tag",
            "v0.1.0-rc.3",
            "--output",
            str(tmp_path / "wrong.md"),
            "--root",
            str(tmp_path),
        ],
    )
    assert mismatch.exit_code != 0
    assert not tmp_path.joinpath("wrong.md").exists()


def test_release_notes_cli_validates_to_stdout_without_output(tmp_path: Path) -> None:
    _write_config(tmp_path, version="0.1.0")
    tmp_path.joinpath("CHANGELOG.md").write_text(
        "# Changelog\n\n## [v0.1.0] — 2026-07-23\n\n- Stable notes.\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        ["release", "notes", "--tag", "v0.1.0", "--root", str(tmp_path)],
    )

    assert result.exit_code == 0, result.stdout
    assert result.stdout == "- Stable notes.\n"


def test_release_workflow_is_tag_triggered_pinned_and_fail_closed() -> None:
    workflow = YAML(typ="safe").load(
        REPOSITORY_ROOT.joinpath(".github/workflows/release.yml").read_text(encoding="utf-8")
    )
    assert isinstance(workflow, dict)
    assert workflow["on"]["push"]["tags"] == ["v*"]
    assert workflow["permissions"] == {"contents": "read"}

    jobs: dict[str, Any] = workflow["jobs"]
    assert all(job["if"] == UPSTREAM_REPOSITORY_GUARD for job in jobs.values())
    assert jobs["publish"]["needs"] == "validate"
    assert jobs["publish"]["permissions"] == {"contents": "write"}
    all_steps = [*jobs["validate"]["steps"], *jobs["publish"]["steps"]]
    action_refs = [step["uses"] for step in all_steps if "uses" in step]
    assert action_refs
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", ref) for ref in action_refs)

    validate_runs = "\n".join(str(step.get("run", "")) for step in jobs["validate"]["steps"])
    publish_runs = "\n".join(str(step.get("run", "")) for step in jobs["publish"]["steps"])
    validate_checkout = next(
        step for step in jobs["validate"]["steps"] if str(step.get("uses", "")).startswith(
            "actions/checkout@"
        )
    )
    assert validate_checkout["with"]["fetch-depth"] == 0
    assert "career-os release privacy" in validate_runs
    assert "--history" in validate_runs
    assert "career-os release privacy" in publish_runs
    texlive_step = next(
        step
        for step in jobs["validate"]["steps"]
        if str(step.get("uses", "")).startswith("TeX-Live/setup-texlive-action@")
    )
    assert texlive_step["uses"] == (
        "TeX-Live/setup-texlive-action@"
        "eb78d21f41941476d9121e3a0abcab73265c876f"
    )
    assert texlive_step["with"]["version"] == "2026"
    assert texlive_step["with"]["cache"] is True
    texlive_packages = set(texlive_step["with"]["packages"].splitlines())
    assert {
        "scheme-basic",
        "ctex",
        "ifmtarg",
        "latexmk",
        "l3packages",
        "realscripts",
        "tex-gyre",
        "xecjk",
        "xetex",
    } <= texlive_packages
    assert "poppler-utils" in validate_runs
    assert "texlive-" not in validate_runs
    assert "career-os release notes" in validate_runs
    assert "career-os release notes" in publish_runs
    assert 'gh release create "${release_args[@]}"' in publish_runs
    assert "--notes-file" in publish_runs
    assert "--generate-notes" not in publish_runs


def test_ci_jobs_are_guarded_to_upstream_repository() -> None:
    workflow = YAML(typ="safe").load(
        REPOSITORY_ROOT.joinpath(".github/workflows/ci.yml").read_text(encoding="utf-8")
    )
    assert isinstance(workflow, dict)
    assert workflow["on"]["push"] == {"branches": ["main"]}
    assert workflow["on"]["pull_request"] is None

    jobs: dict[str, Any] = workflow["jobs"]
    assert jobs
    assert all(job["if"] == UPSTREAM_REPOSITORY_GUARD for job in jobs.values())
    core_checkout = next(
        step for step in jobs["core"]["steps"] if str(step.get("uses", "")).startswith(
            "actions/checkout@"
        )
    )
    assert core_checkout["with"]["fetch-depth"] == 0
    core_runs = "\n".join(str(step.get("run", "")) for step in jobs["core"]["steps"])
    assert "career-os release privacy" in core_runs
    assert "--history" in core_runs
    resume_runs = "\n".join(str(step.get("run", "")) for step in jobs["resume"]["steps"])
    texlive_step = next(
        step
        for step in jobs["resume"]["steps"]
        if str(step.get("uses", "")).startswith("TeX-Live/setup-texlive-action@")
    )
    assert texlive_step["with"]["version"] == "2026"
    assert texlive_step["with"]["cache"] is True
    texlive_packages = set(texlive_step["with"]["packages"].splitlines())
    assert {
        "scheme-basic",
        "ctex",
        "ifmtarg",
        "latexmk",
        "l3packages",
        "realscripts",
        "tex-gyre",
        "xecjk",
        "xetex",
    } <= texlive_packages
    assert "poppler-utils" in resume_runs
    assert "texlive-" not in resume_runs
