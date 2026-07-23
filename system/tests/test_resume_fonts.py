from __future__ import annotations

from pathlib import Path

from career_os.config import ProjectPaths
from career_os.resume.service import ExportContext, _build_wrapper, validate_resume_source


def _paths(root: Path) -> ProjectPaths:
    return ProjectPaths(
        project_root=root,
        data_root=root / "career",
        runtime_root=root / "runtime",
        build_root=root / "build",
        local_state_root=root / ".career-os",
        vault_root=root,
        mode="standalone",
    )


def _write_privacy_patterns(root: Path) -> None:
    target = root / "system/resume/secret-patterns.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("[]\n", encoding="utf-8")


def test_tex_root_owns_font_choice_without_a_profile_manifest(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_privacy_patterns(tmp_path)
    root = paths.data_root / "70-career-communication/resumes/personal"
    root.mkdir(parents=True)
    source = root / "resume.tex"
    source.write_text(
        "\\newcommand{\\CareerOSCJKBodyRegularFont}{OwnerSong-Regular.otf}\n"
        "\\newcommand{\\CareerOSCJKBodyBoldFont}{OwnerHei-Regular.otf}\n"
        "\\documentclass{career-os}\n"
        "\\input{identity}\n"
        "\\begin{document}Synthetic.\\end{document}\n",
        encoding="utf-8",
    )
    (root / "identity.tex").write_text(
        "\\newcommand{\\ResumeFullName}{Alex Morgan}\n"
        "\\newcommand{\\ResumeEmail}{alex@example.test}\n"
        "\\newcommand{\\ResumePhone}{+65 0000 0000}\n"
        "\\newcommand{\\ResumeAvatarAsset}{}\n",
        encoding="utf-8",
    )

    validate_resume_source(paths, source)


def test_build_wrapper_injects_only_export_context_not_fonts(tmp_path: Path) -> None:
    source = tmp_path / "resume.tex"
    source.write_text("Synthetic.\n", encoding="utf-8")
    wrapper = _build_wrapper(
        source,
        ExportContext(
            "internal",
            "Owner",
            "Internal build",
            "INTERNAL",
            "2026-07-22",
            "INTERNAL",
        ),
        None,
    )

    assert "CareerOSCJKBodyRegularFont" not in wrapper
    assert "CareerOSLatinBodyRegularFont" not in wrapper
    assert "\\def\\ResumeExportProfile{internal}" in wrapper
    assert "\\input{\\CareerOSSourcePath}" in wrapper


def test_system_class_materializes_font_filenames_for_fontspec_28() -> None:
    project_root = Path(__file__).resolve().parents[2]
    class_text = (project_root / "system/resume/career-os.cls").read_text(encoding="utf-8")

    for setup in (
        "CareerOSSetMainFont",
        "CareerOSSetSansFont",
        "CareerOSSetCJKMainFont",
        "CareerOSSetCJKSansFont",
        "CareerOSSetCJKMonoFont",
    ):
        assert f"\\edef\\{setup}" in class_text
        assert f"\\{setup}" in class_text
    assert "Path=\\CareerOS" not in class_text
