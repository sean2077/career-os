from __future__ import annotations

from pathlib import Path

import pytest
from career_os.cli import app
from career_os.config import ProjectPaths
from career_os.resume import list_resumes
from rich.text import Text
from typer.testing import CliRunner


def _paths(root: Path) -> ProjectPaths:
    return ProjectPaths(
        project_root=root,
        data_root=root / "career",
        runtime_root=root / ".career-os/runtime",
        build_root=root / "build",
        local_state_root=root / ".career-os",
        vault_root=root,
        mode="standalone",
    )


def _write_root(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\\documentclass{career-os}\n\\input{identity}\n"
        "\\begin{document}Synthetic.\\end{document}\n",
        encoding="utf-8",
    )
    path.with_name("identity.tex").write_text(
        "\\newcommand{\\ResumeFullName}{Alex Morgan}\n"
        "\\newcommand{\\ResumeEmail}{alex@example.test}\n"
        "\\newcommand{\\ResumePhone}{+65 0000 0000}\n"
        "\\newcommand{\\ResumeAvatarAsset}{}\n",
        encoding="utf-8",
    )


def test_resume_list_discovers_recursive_tex_roots_without_registry(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    root = paths.data_root / "70-career-communication/resumes"
    _write_root(root / "alpha/resume.tex")
    _write_root(root / "nested/beta.tex")
    _write_root(root / "nested/gamma/resume.tex")
    (root / "nested/not-a-root.tex").write_text("Fragment only.\n", encoding="utf-8")

    items = list_resumes(paths)

    assert [item.name for item in items] == ["alpha", "beta", "gamma"]
    assert all(item.profiles == ("application", "preview") for item in items)
    assert all(item.source.endswith(".tex") for item in items)


def test_resume_list_rejects_duplicate_derived_names(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    root = paths.data_root / "70-career-communication/resumes"
    _write_root(root / "one/shared.tex")
    _write_root(root / "two/shared.tex")

    with pytest.raises(ValueError, match="duplicate resume name 'shared'"):
        list_resumes(paths)


def test_export_cli_uses_resume_name_and_fixed_profiles() -> None:
    result = CliRunner().invoke(app, ["resume", "export", "--help"])
    help_text = Text.from_ansi(result.stdout).plain

    assert result.exit_code == 0
    assert "--resume" in help_text
    assert "--profile" in help_text
    assert "--variant" not in help_text
    assert "--manifest" not in help_text


def test_repository_keeps_tex_roots_as_the_only_resume_authority() -> None:
    project_root = Path(__file__).resolve().parents[2]
    resume_root = project_root / "career/70-career-communication/resumes"

    assert not list(resume_root.rglob("*.resume.json"))
    assert not (project_root / "system/schemas/resume-manifest.schema.json").exists()
    assert not (project_root / "system/schemas/font-profile.schema.json").exists()
    assert (project_root / "system/resume/fonts.json").is_file()
