from __future__ import annotations

import hashlib
import io
import json
import urllib.request
from pathlib import Path

import pytest
from career_os.config import ProjectPaths
from career_os.resume.fonts import fetch_fonts, verify_system_fonts
from career_os.resume.privacy import (
    audit_pdf,
    audit_tex_bundle,
    audit_tex_source,
    extract_pdf_text,
    sanitize_pdf,
)
from career_os.resume.service import (
    _probe_command,
    _probe_latexmk,
    _validate_claim_boundary,
    list_resumes,
    new_resume,
    validate_resume_source,
)
from pypdf import PdfWriter


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
    target.write_text(
        '[{"id":"test-token","regex":"TOKEN_[A-Z0-9]{12}"}]\n',
        encoding="utf-8",
    )


def test_new_resume_creates_only_editable_tex_and_refuses_overwrite(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_privacy_patterns(tmp_path)
    paths.data_root.joinpath("70-career-communication").mkdir(parents=True)
    template = tmp_path / "system/resume/templates/single-column.tex"
    template.parent.mkdir(parents=True)
    template.write_text(
        "\\documentclass{career-os}\n"
        "\\input{identity}\n"
        "\\begin{document}中文内容\\end{document}\n",
        encoding="utf-8",
    )
    (template.parent / "identity.tex").write_text(
        "\\newcommand{\\ResumeFullName}{Your Name}\n"
        "\\newcommand{\\ResumeEmail}{email@example.test}\n"
        "\\newcommand{\\ResumePhone}{+00 000 0000}\n"
        "\\newcommand{\\ResumeAvatarAsset}{}\n",
        encoding="utf-8",
    )

    source = new_resume(paths, name="zh-general")

    assert source.parent.name == "zh-general"
    assert "中文内容" in source.read_text(encoding="utf-8")
    assert source.with_name("identity.tex").is_file()
    assert not list(source.parent.glob("*.json"))
    validate_resume_source(paths, source)
    source.write_text(source.read_text(encoding="utf-8") + "% edit freely\n", encoding="utf-8")
    validate_resume_source(paths, source)
    assert [item.name for item in list_resumes(paths)] == ["zh-general"]
    with pytest.raises(ValueError, match="already exists"):
        new_resume(paths, name="zh-general")


def test_font_fetch_verifies_hash_and_refuses_changed_existing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    payload = b"synthetic-font"
    manifest_path = tmp_path / "system/resume/fonts.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "bundle": "test-fonts",
                "revision": 1,
                "packages": [
                    {
                        "family": "Test Serif",
                        "version": "1.0",
                        "source": "https://example.test/serif",
                        "license": "OFL-1.1",
                        "license_path": "LICENSE",
                        "assets": [
                            {
                                "name": "TestSerif-Regular.otf",
                                "role": "body-regular",
                                "url": "https://example.test/TestSerif-Regular.otf",
                                "sha256": hashlib.sha256(payload).hexdigest(),
                                "size": len(payload),
                            },
                            {
                                "name": "TestSerif-Bold.otf",
                                "role": "body-bold",
                                "url": "https://example.test/TestSerif-Bold.otf",
                                "sha256": hashlib.sha256(payload).hexdigest(),
                                "size": len(payload),
                            },
                        ],
                    },
                    {
                        "family": "Test Sans",
                        "version": "1.0",
                        "source": "https://example.test/sans",
                        "license": "OFL-1.1",
                        "license_path": "LICENSE",
                        "assets": [
                            {
                                "name": "TestSans-Regular.otf",
                                "role": "display-regular",
                                "url": "https://example.test/TestSans-Regular.otf",
                                "sha256": hashlib.sha256(payload).hexdigest(),
                                "size": len(payload),
                            },
                            {
                                "name": "TestSans-Bold.otf",
                                "role": "display-bold",
                                "url": "https://example.test/TestSans-Bold.otf",
                                "sha256": hashlib.sha256(payload).hexdigest(),
                                "size": len(payload),
                            },
                        ],
                    },
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    def fake_urlopen(_url: str, *, timeout: int) -> io.BytesIO:
        assert timeout == 60
        return io.BytesIO(payload)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert all(item.status == "pass" for item in fetch_fonts(paths))
    target = Path(verify_system_fonts(paths)[0].path)
    target.write_bytes(b"changed")
    with pytest.raises(ValueError, match="refusing to overwrite"):
        fetch_fonts(paths)


def test_privacy_checks_reject_source_secrets_and_pdf_metadata(tmp_path: Path) -> None:
    _write_privacy_patterns(tmp_path)
    assert "source-links-confined-to-final-pdf-sanitization" in audit_tex_source(
        tmp_path, r"\href{https://example.test}{link}"
    )
    with pytest.raises(ValueError, match="secret:test-token"):
        audit_tex_source(tmp_path, "TOKEN_ABCDEF123456")

    unsafe = tmp_path / "unsafe.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_metadata({"/Author": "Private Person"})
    with unsafe.open("wb") as handle:
        writer.write(handle)
    with pytest.raises(ValueError, match="metadata:author"):
        audit_pdf(tmp_path, unsafe)

    clean = sanitize_pdf(unsafe)
    report = audit_pdf(tmp_path, clean)
    assert report.pages == 1
    assert report.images == 0


def test_pdf_text_extraction_prefers_poppler_for_cjk_fonts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Completed:
        returncode = 0
        stdout = "林晨\n示例城市\n".encode()

    monkeypatch.setattr("career_os.resume.privacy.resolve_pdf_tool", lambda _name: "pdftotext")
    monkeypatch.setattr(
        "career_os.resume.privacy.subprocess.run", lambda *_args, **_kwargs: Completed()
    )
    assert extract_pdf_text(b"synthetic-pdf") == "林晨\n示例城市\n"


def test_resume_command_probes_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    class Broken:
        returncode = 3

    monkeypatch.setattr("career_os.resume.service.shutil.which", lambda _name: "broken.cmd")
    monkeypatch.setattr(
        "career_os.resume.service.subprocess.run", lambda *_args, **_kwargs: Broken()
    )
    result = _probe_command(
        "pdftoppm",
        version_args=("-v",),
        missing_status="attention",
        purpose="visual inspection",
    )
    assert result.status == "attention"
    assert result.detail == "visual inspection; version probe exited 3"

    class NoPdf:
        returncode = 0

    monkeypatch.setattr(
        "career_os.resume.service._resolve_latexmk_command", lambda _source_dir: ["latexmk"]
    )
    monkeypatch.setattr(
        "career_os.resume.service.subprocess.run", lambda *_args, **_kwargs: NoPdf()
    )
    latexmk = _probe_latexmk()
    assert latexmk.status == "fail"
    assert latexmk.detail == "required; compilation probe exited 0"


def test_bundle_audit_allows_only_fixed_identity_input(tmp_path: Path) -> None:
    _write_privacy_patterns(tmp_path)
    valid = {
        "resume.tex": "\\documentclass{career-os}\n\\input{identity}\n",
        "identity.tex": "\\newcommand{\\ResumeFullName}{Alex Morgan}\n",
    }
    assert "source-dependencies-declared-and-used" in audit_tex_bundle(
        tmp_path, valid, declared_inputs={"identity.tex"}
    )
    with pytest.raises(ValueError, match="undeclared-input:extra.tex"):
        audit_tex_bundle(
            tmp_path,
            {**valid, "resume.tex": "\\input{identity}\\input{extra}\n"},
            declared_inputs={"identity.tex"},
        )
    with pytest.raises(ValueError, match="unused-dependency:identity.tex"):
        audit_tex_bundle(
            tmp_path,
            {**valid, "resume.tex": "\\documentclass{career-os}\n"},
            declared_inputs={"identity.tex"},
        )


def test_application_policy_comes_from_communication_resume_record(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    work_id = "11111111-1111-4111-8111-111111111111"
    claim_id = "22222222-2222-4222-8222-222222222222"
    jd_id = "33333333-3333-4333-8333-333333333333"
    profile_id = "44444444-4444-4444-8444-444444444444"
    resume_id = "55555555-5555-4555-8555-555555555555"
    _write_record(
        paths.data_root / "10-career-evidence/work.md",
        record_id=work_id,
        kind="evidence.work",
        visibility="private",
        status="verified",
    )
    _write_record(
        paths.data_root / "10-career-evidence/claim.md",
        record_id=claim_id,
        kind="evidence.claim",
        visibility="shareable",
        status="approved",
        relations={"supported_by": ["[[career/10-career-evidence/work]]"]},
    )
    _write_record(
        paths.data_root / "30-role-market/jd.md",
        record_id=jd_id,
        kind="market.jd",
        visibility="private",
        status="reviewed",
    )
    _write_record(
        paths.data_root / "70-career-communication/profile.md",
        record_id=profile_id,
        kind="communication.profile",
        visibility="private",
        status="approved",
    )
    _write_record(
        paths.data_root / "70-career-communication/resumes/target.md",
        record_id=resume_id,
        kind="communication.resume",
        visibility="private",
        status="application-ready",
        relations={
            "target_jd": "[[career/30-role-market/jd]]",
            "identity_profile": "[[career/70-career-communication/profile]]",
            "uses_claim": ["[[career/10-career-evidence/claim]]"],
        },
    )
    source = (
        "\\begin{itemize}\n"
        f"\\resumebullet{{Outcome}}{{\\CareerClaim{{{claim_id}}}{{Evidence-backed.}}}}\n"
        "\\end{itemize}\n"
    )

    with pytest.raises(ValueError, match="confirm-application"):
        _validate_claim_boundary(
            paths,
            "target",
            source,
            profile="application",
            confirm_application=False,
        )
    assert (
        str(
            _validate_claim_boundary(
                paths,
                "target",
                source,
                profile="application",
                confirm_application=True,
            )
        )
        == resume_id
    )

    jd = paths.data_root / "30-role-market/jd.md"
    jd.write_text(
        jd.read_text(encoding="utf-8").replace("Synthetic record.", "Changed source."),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="source body has changed"):
        _validate_claim_boundary(
            paths,
            "target",
            source,
            profile="application",
            confirm_application=True,
        )


def test_every_application_bullet_requires_a_claim(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    work_id = "11111111-1111-4111-8111-111111111111"
    claim_id = "22222222-2222-4222-8222-222222222222"
    jd_id = "33333333-3333-4333-8333-333333333333"
    profile_id = "44444444-4444-4444-8444-444444444444"
    _write_minimal_application_records(paths, work_id, claim_id, jd_id, profile_id)
    source = (
        "\\resumebullet{Draft}{Unbound text.}\n"
        f"\\resumebullet{{Bound}}{{\\CareerClaim{{{claim_id}}}{{Bound text.}}}}\n"
    )
    with pytest.raises(ValueError, match="must bind one or more claim IDs"):
        _validate_claim_boundary(
            paths,
            "target",
            source,
            profile="application",
            confirm_application=True,
        )


def _write_minimal_application_records(
    paths: ProjectPaths, work_id: str, claim_id: str, jd_id: str, profile_id: str
) -> None:
    _write_record(
        paths.data_root / "10-career-evidence/work.md",
        record_id=work_id,
        kind="evidence.work",
        visibility="private",
        status="verified",
    )
    _write_record(
        paths.data_root / "10-career-evidence/claim.md",
        record_id=claim_id,
        kind="evidence.claim",
        visibility="shareable",
        status="approved",
        relations={"supported_by": ["[[career/10-career-evidence/work]]"]},
    )
    _write_record(
        paths.data_root / "30-role-market/jd.md",
        record_id=jd_id,
        kind="market.jd",
        visibility="private",
        status="reviewed",
    )
    _write_record(
        paths.data_root / "70-career-communication/profile.md",
        record_id=profile_id,
        kind="communication.profile",
        visibility="private",
        status="approved",
    )
    _write_record(
        paths.data_root / "70-career-communication/resumes/target.md",
        record_id="55555555-5555-4555-8555-555555555555",
        kind="communication.resume",
        visibility="private",
        status="application-ready",
        relations={
            "target_jd": "[[career/30-role-market/jd]]",
            "identity_profile": "[[career/70-career-communication/profile]]",
            "uses_claim": ["[[career/10-career-evidence/claim]]"],
        },
    )


def _write_record(
    path: Path,
    *,
    record_id: str,
    kind: str,
    visibility: str,
    status: str,
    relations: dict[str, object] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    jd_body = (
        "# Synthetic role\n\n"
        "## JD 原文\n\n"
        "Synthetic record.\n\n"
        "## 重新评价\n\n"
        "Synthetic reviewed assessment.\n"
    )
    fields: dict[str, object] = {
        "evidence.work": {
            "contribution_scope": "individual",
            "evidence_strength": "strong",
            "evidence_summary": "Synthetic grounded evidence.",
        },
        "evidence.claim": {
            "allowed_uses": ["resume", "application"],
            "claim_risk": "low",
        },
        "market.jd": {
            "source_status": "full",
            "source_channel_name": "synthetic-fixture",
            "captured_at": "2026-07-21T00:00:00Z",
            "missing_sections": [],
            "source_body_sha256": hashlib.sha256(b"Synthetic record.\n").hexdigest(),
            "evidence_fit": 4,
            "preference": "medium",
            "priority": "p1",
            "next_action": "candidate",
            "reviewed_at": "2026-07-21",
        },
        "communication.profile": {
            "audience": "synthetic application",
            "identity_policy": "application",
        },
        "communication.resume": {
            "root_name": "target",
            "audience": "synthetic application",
            "export_policy": "application",
        },
    }[kind]
    envelope = {
        "id": record_id,
        "kind": kind,
        "schema_version": 3,
        "created_at": "2026-07-21T00:00:00Z",
        "updated_at": "2026-07-21T01:00:00Z",
        "visibility": visibility,
        "status": status,
        **fields,
        **(relations or {}),
    }
    body = jd_body if kind == "market.jd" else "Synthetic record.\n"
    path.write_text(
        "---\n" + json.dumps(envelope, indent=2) + "\n---\n" + body,
        encoding="utf-8",
    )
