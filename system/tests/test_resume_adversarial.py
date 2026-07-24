from __future__ import annotations

import base64
import re
from pathlib import Path

import pytest
from career_os.config import ProjectPaths
from career_os.resume.service import (
    BuildResult,
    ExportContext,
    _BuiltResume,
    _export_context,
    export_resume,
    validate_resume_source,
)
from pypdf import PdfWriter

_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


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


def _create_root(
    paths: ProjectPaths,
    *,
    name: str,
    avatar: str = "",
    language: str | None = None,
) -> Path:
    root = paths.data_root / f"70-career-communication/resumes/{name}"
    root.mkdir(parents=True)
    source = root / "resume.tex"
    class_options = f"[language={language}]" if language is not None else ""
    source.write_text(
        f"\\documentclass{class_options}{{career-os}}\n"
        "\\input{identity}\n"
        "\\begin{document}Synthetic resume.\\end{document}\n",
        encoding="utf-8",
    )
    (root / "identity.tex").write_text(
        "\\newcommand{\\ResumeFullName}{Alex Morgan}\n"
        "\\newcommand{\\ResumeEmail}{alex\\_morgan@example.test}\n"
        "\\newcommand{\\ResumePhone}{+65 0000 0000}\n"
        f"\\newcommand{{\\ResumeAvatarAsset}}{{{avatar}}}\n",
        encoding="utf-8",
    )
    return source


def test_source_outside_owned_roots_is_rejected(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_privacy_patterns(tmp_path)
    source = tmp_path / "outside/resume.tex"
    source.parent.mkdir()
    source.write_text("\\documentclass{career-os}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="outside the user resume or system fixture roots"):
        validate_resume_source(paths, source)


def test_identity_symlink_escape_is_rejected(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_privacy_patterns(tmp_path)
    source = _create_root(paths, name="symlink")
    identity = source.with_name("identity.tex")
    outside = tmp_path / "outside-identity.tex"
    outside.write_bytes(identity.read_bytes())
    identity.unlink()
    try:
        identity.symlink_to(outside)
    except OSError as error:
        pytest.skip(f"local platform does not permit test symlinks: {error}")

    with pytest.raises(ValueError, match="identity is missing"):
        validate_resume_source(paths, source)


def test_malformed_and_ambiguous_avatar_files_are_rejected(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_privacy_patterns(tmp_path)
    source = _create_root(paths, name="avatar", avatar="avatar")
    avatar = source.with_name("avatar.png")
    avatar.write_bytes(b"\x89PNG\r\n\x1a\nnot-a-complete-png")
    with pytest.raises(ValueError, match="PNG has an invalid chunk length"):
        validate_resume_source(paths, source)

    avatar.write_bytes(_PNG_1X1)
    source.with_name("avatar.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    with pytest.raises(ValueError, match="avatar stem is ambiguous"):
        validate_resume_source(paths, source)


def test_resume_language_defaults_to_en_and_rejects_invalid_tags(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_privacy_patterns(tmp_path)
    default_source = _create_root(paths, name="default-language")
    validate_resume_source(paths, default_source)

    explicit_source = _create_root(paths, name="explicit-language", language="zh-CN")
    validate_resume_source(paths, explicit_source)

    invalid_source = _create_root(paths, name="invalid-language", language="../zh-CN")
    with pytest.raises(ValueError, match="one BCP 47 tag"):
        validate_resume_source(paths, invalid_source)


def test_export_context_uses_four_character_id_and_rejects_invalid_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "career_os.resume.service.secrets.token_hex",
        lambda byte_count: "a1b2" if byte_count == 2 else pytest.fail("unexpected ID size"),
    )
    context = _export_context(
        "preview",
        recipient=None,
        purpose=None,
        watermark=None,
    )
    assert re.fullmatch(r"HC-\d{8}-A1B2", context.export_id)

    with pytest.raises(ValueError, match="unsafe TeX"):
        _export_context(
            "preview",
            recipient=r"Acme\input{secret}",
            purpose="Review",
            watermark=None,
        )
    with pytest.raises(ValueError, match="120 characters"):
        _export_context(
            "preview",
            recipient="A" * 121,
            purpose="Review",
            watermark=None,
        )


def test_receipt_failure_removes_shareable_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    _write_privacy_patterns(tmp_path)
    source = _create_root(paths, name="receipt-failure", language="zh-CN")
    built = tmp_path / "built.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with built.open("wb") as handle:
        writer.write(handle)

    monkeypatch.setattr(
        "career_os.resume.service._build_resume_root",
        lambda *_args, **_kwargs: _BuiltResume(
            BuildResult(
                "receipt-failure", str(source), str(built), str(tmp_path / "build.log")
            ),
            "0" * 64,
            "1" * 64,
            None,
        ),
    )
    monkeypatch.setattr(
        "career_os.resume.service._validate_export_projection",
        lambda *_args, **_kwargs: None,
    )
    context = ExportContext(
        profile="preview",
        recipient="",
        purpose="",
        watermark="",
        export_date="2026-07-24",
        export_id="HC-20260724-A1B2",
    )
    monkeypatch.setattr(
        "career_os.resume.service._export_context",
        lambda *_args, **_kwargs: context,
    )
    output = (
        paths.build_root
        / "share"
        / "Alex-Morgan-ReceiptFailure-HC-zh-CN-20260724-A1B2.pdf"
    )
    original_write_text = Path.write_text

    def fail_receipt(path: Path, *args: object, **kwargs: object) -> int:
        if path.parent.name == "export-receipts":
            assert output.is_file()
            raise OSError("synthetic receipt failure")
        return original_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_receipt)
    with pytest.raises(OSError, match="synthetic receipt failure"):
        export_resume(
            paths,
            resume="receipt-failure",
            profile="preview",
            confirm_application=False,
        )
    assert not output.exists()
