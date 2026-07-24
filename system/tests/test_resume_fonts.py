from __future__ import annotations

from pathlib import Path

import pytest
from career_os.config import ProjectConfig, ProjectPaths
from career_os.resume.fonts import prepare_resume_fonts, verify_fonts
from career_os.resume.service import ExportContext, _build_wrapper, validate_resume_source


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


def _write_privacy_patterns(root: Path) -> None:
    target = root / "system/resume/secret-patterns.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("[]\n", encoding="utf-8")


def test_project_font_config_defaults_and_partial_override() -> None:
    default = ProjectConfig.model_validate(
        {"schema_version": 2, "system_version": "0.1.0"}
    )
    assert default.resume.fonts.directory == ".career-os/fonts"
    assert default.resume.fonts.roles.configured() == {}

    partial = ProjectConfig.model_validate(
        {
            "schema_version": 2,
            "system_version": "0.1.0",
            "resume": {
                "fonts": {
                    "directory": ".career-os/fonts/private",
                    "roles": {"latin_body_regular": "Latin-Regular.otf"},
                }
            },
        }
    )
    assert partial.resume.fonts.roles.latin_body_regular == "Latin-Regular.otf"
    assert partial.resume.fonts.roles.cjk_body_regular is None


@pytest.mark.parametrize(
    "directory",
    ["fonts", "../.career-os/fonts", "C:/fonts", ".career-os\\fonts"],
)
def test_project_font_config_rejects_unsafe_directories(directory: str) -> None:
    with pytest.raises(ValueError, match="resume.fonts.directory"):
        ProjectConfig.model_validate(
            {
                "schema_version": 2,
                "system_version": "0.1.0",
                "resume": {"fonts": {"directory": directory}},
            }
        )


def test_project_font_config_rejects_obsolete_checksums() -> None:
    with pytest.raises(ValueError, match="checksums"):
        ProjectConfig.model_validate(
            {
                "schema_version": 2,
                "system_version": "0.1.0",
                "resume": {
                    "fonts": {
                        "roles": {"cjk_body_regular": "OwnerSong-Regular.otf"},
                        "checksums": {"OwnerSong-Regular.otf": "a" * 64},
                    }
                },
            }
        )


def test_tex_root_cannot_override_project_font_roles(tmp_path: Path) -> None:
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

    with pytest.raises(ValueError, match="configured in career-os.toml"):
        validate_resume_source(paths, source)


def test_font_verification_accepts_same_name_replacement_and_writes_one_projection(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    roles = (
        "cjk_body_regular",
        "cjk_body_bold",
        "cjk_body_italic",
        "cjk_body_bold_italic",
        "cjk_display_regular",
        "cjk_display_bold",
        "cjk_display_italic",
        "cjk_display_bold_italic",
        "cjk_mono_regular",
        "cjk_mono_bold",
        "cjk_mono_italic",
        "cjk_mono_bold_italic",
    )
    role_lines = "\n".join(f'{role} = "OwnerCJK.otf"' for role in roles)
    tmp_path.joinpath("career-os.toml").write_text(
        f"""schema_version = 2
system_version = "0.1.0"

[resume.fonts]
directory = ".career-os/fonts/private"

[resume.fonts.roles]
{role_lines}
""",
        encoding="utf-8",
    )
    manifest = tmp_path / "system/resume/fonts.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes(
        Path(__file__).resolve().parents[2].joinpath(
            "system/resume/fonts.json"
        ).read_bytes()
    )

    missing = verify_fonts(paths)
    assert len(missing) == 1
    assert missing[0].status == "fail"
    assert missing[0].detail == "missing"

    font = tmp_path / ".career-os/fonts/private/OwnerCJK.otf"
    font.parent.mkdir(parents=True)
    font.write_bytes(b"synthetic-project-font-v1")
    generated, statuses = prepare_resume_fonts(paths)
    assert all(status.status == "pass" for status in statuses)
    assert statuses[0].detail == "present"
    assert generated == tmp_path / ".career-os/generated/resume-fonts.tex"
    projection = generated.read_text(encoding="utf-8")
    assert projection.count("\\newcommand") == len(roles)
    assert "\\CareerOSCJKBodyRegularFont}{OwnerCJK.otf}" in projection
    assert "CareerOSLatin" not in projection

    font.write_bytes(b"synthetic-project-font-v2")
    replacement_statuses = verify_fonts(paths)
    assert len(replacement_statuses) == 1
    assert replacement_statuses[0].status == "pass"
    assert replacement_statuses[0].detail == "present"


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
    assert "\\InputIfFileExists{resume-fonts.tex}{}{}" in class_text
    assert "Path=\\CareerOS" not in class_text
