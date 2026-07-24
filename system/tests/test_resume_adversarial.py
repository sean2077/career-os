from __future__ import annotations

import base64
from pathlib import Path

import pytest
from career_os.config import ProjectPaths
from career_os.resume.service import (
    BuildResult,
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


def _create_root(paths: ProjectPaths, *, name: str, avatar: str = "") -> Path:
    root = paths.data_root / f"70-career-communication/resumes/{name}"
    root.mkdir(parents=True)
    source = root / "resume.tex"
    source.write_text(
        "\\documentclass{career-os}\n"
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


def test_export_context_rejects_injection_and_oversize() -> None:
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
    source = _create_root(paths, name="receipt-failure")
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
    original_write_text = Path.write_text

    def fail_receipt(path: Path, *args: object, **kwargs: object) -> int:
        if path.parent.name == "export-receipts":
            raise OSError("synthetic receipt failure")
        return original_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_receipt)
    output = tmp_path / "shareable.pdf"
    with pytest.raises(OSError, match="synthetic receipt failure"):
        export_resume(
            paths,
            resume="receipt-failure",
            profile="preview",
            output=output,
            confirm_application=False,
        )
    assert not output.exists()
