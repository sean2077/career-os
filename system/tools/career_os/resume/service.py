from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import struct
import subprocess
import tempfile
import zlib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from career_os.config import ProjectPaths
from career_os.records import ParsedRecord, load_record
from career_os.records.markdown import extract_markdown_section
from career_os.records.models import (
    CommunicationProfile,
    CommunicationResume,
    EvidenceClaim,
    MarketJD,
)
from career_os.resume.fonts import verify_fonts
from career_os.resume.privacy import (
    PrivacyReport,
    audit_pdf,
    audit_tex_bundle,
    extract_pdf_text,
    resolve_pdf_tool,
    sanitize_pdf,
)

ExportProfile = Literal["preview", "application"]
BuildProfile = Literal["internal", "preview", "application"]


@dataclass(frozen=True)
class ResumeDoctorCheck:
    id: str
    status: str
    path: str | None
    detail: str

    def as_dict(self) -> dict[str, str | None]:
        return asdict(self)


@dataclass(frozen=True)
class BuildResult:
    resume: str
    source: str
    pdf: str
    log: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ExportResult:
    profile: str
    output: str
    sha256: str
    receipt: str
    privacy: PrivacyReport
    export_id: str
    recipient: str
    purpose: str
    watermark: str

    def as_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "output": self.output,
            "sha256": self.sha256,
            "receipt": self.receipt,
            "privacy": self.privacy.as_dict(),
            "export_id": self.export_id,
            "recipient": self.recipient,
            "purpose": self.purpose,
            "watermark": self.watermark,
        }


@dataclass(frozen=True)
class ExportContext:
    profile: BuildProfile
    recipient: str
    purpose: str
    watermark: str
    export_date: str
    export_id: str


@dataclass(frozen=True)
class ResumeIdentity:
    full_name: str
    email: str
    phone: str
    avatar_asset: str | None


@dataclass(frozen=True)
class ResumeListItem:
    name: str
    source: str
    profiles: tuple[str, ...] = ("application", "preview")

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "source": self.source,
            "profiles": list(self.profiles),
        }


@dataclass(frozen=True)
class ResolvedResumeRoot:
    name: str
    source_root: Path
    source: Path
    identity: Path
    avatar: Path | None


@dataclass(frozen=True)
class _BuiltResume:
    result: BuildResult
    source_sha256: str
    identity_sha256: str
    avatar_sha256: str | None


_DOCUMENT_CLASS = re.compile(
    r"\\documentclass(?:\s*\[[^\]]*\])?\s*\{career-os\}", re.IGNORECASE
)
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_CLAIM = re.compile(r"\\CareerClaim\s*\{([^{}]+)\}")
_CLAIMS = re.compile(r"\\CareerClaims\s*\{([^{}]+)\}")
_BULLET = re.compile(r"\\(?:resumebullet|CareerBullet)\s*\{")
_IDENTITY_MACRO = re.compile(
    r"\\(?:newcommand|renewcommand|providecommand)\s*"
    r"\{\\(?P<name>(?:CareerOS(?:FullName|Email|Phone|Location)|"
    r"Resume(?:FullName|Email|Phone|AvatarAsset)))\}\s*"
    r"\{(?P<value>[^{}]*)\}"
)
_CONTEXT_CONTROL = re.compile(r"[\\%#{}\x00-\x1f\x7f]")
_IDENTITY_DEFINITION = re.compile(
    r"\\(?:newcommand|renewcommand|providecommand)\s*"
    r"\{\\(?:CareerOS(?:FullName|Email|Phone|Location)|"
    r"Resume(?:FullName|Email|Phone|AvatarAsset))\}"
)
_IDENTITY_ESCAPE = re.compile(r"\\([_%#&])")
_IDENTITY_UNSAFE_ESCAPE = re.compile(r"\\(?![_%#&])")
_IDENTITY_UNESCAPED_SPECIAL = re.compile(r"(?<!\\)[$%#&_~^]")
_EXPORT_ID = re.compile(r"^(?:HC|AP)-\d{8}-[A-F0-9]{8}$")
_AVATAR_SUFFIXES = (".png", ".jpg", ".jpeg")


def new_resume(paths: ProjectPaths, *, name: str) -> Path:
    if not _SAFE_NAME.fullmatch(name) or name in {".", ".."}:
        raise ValueError("resume name must be one safe path segment")
    template_root = paths.project_root / "system/resume/templates"
    source_text = (template_root / "single-column.tex").read_text(encoding="utf-8")
    identity_text = (template_root / "identity.tex").read_text(encoding="utf-8")
    communication_root = paths.data_root / "70-career-communication"
    if not communication_root.is_dir():
        raise ValueError("Career data is not initialized; run career-os init first")
    target = communication_root / "resumes" / name
    if target.exists():
        raise ValueError(f"resume target already exists: {target}")
    target.mkdir(parents=True, exist_ok=False)
    source_path = target / "resume.tex"
    identity_path = target / "identity.tex"
    try:
        source_path.write_text(source_text, encoding="utf-8", newline="\n")
        identity_path.write_text(identity_text, encoding="utf-8", newline="\n")
    except OSError:
        source_path.unlink(missing_ok=True)
        identity_path.unlink(missing_ok=True)
        target.rmdir()
        raise
    return source_path


def resume_doctor(paths: ProjectPaths) -> list[ResumeDoctorCheck]:
    checks: list[ResumeDoctorCheck] = [
        _probe_latexmk(),
        _probe_command(
            "xelatex",
            version_args=("--version",),
            missing_status="fail",
            purpose="required",
        ),
    ]
    for command in ("pdftoppm", "pdfinfo", "pdftotext", "pdftohtml"):
        checks.append(_probe_poppler(command))
    for status in verify_fonts(paths):
        checks.append(
            ResumeDoctorCheck(
                id=f"font.{status.name}",
                status=status.status,
                path=status.path,
                detail=status.detail,
            )
        )
    for relative in (
        "system/resume/career-os.cls",
        "system/resume/career-os-style.sty",
        "system/resume/linespacing_fix.sty",
        "system/resume/templates/single-column.tex",
        "system/resume/templates/identity.tex",
        "system/licenses/SIL-OFL-1.1.txt",
    ):
        target = paths.project_root / relative
        checks.append(
            ResumeDoctorCheck(
                id="asset.resume",
                status="pass" if target.is_file() else "fail",
                path=str(target),
                detail="present" if target.is_file() else "missing",
            )
        )
    return checks


def _probe_latexmk() -> ResumeDoctorCheck:
    command = "latexmk"
    try:
        resolved_command = _resolve_latexmk_command(Path.cwd())
    except ValueError as error:
        return ResumeDoctorCheck(
            id=f"command.{command}", status="fail", path=None, detail=f"required; {error}"
        )
    resolved = resolved_command[-1]
    try:
        environment = _tool_environment()
        with tempfile.TemporaryDirectory(prefix="career-os-latexmk-doctor-") as temporary:
            root = Path(temporary)
            source = root / "probe.tex"
            source.write_text(
                "\\documentclass{article}\n"
                "\\begin{document}\n"
                "Career OS resume toolchain probe.\n"
                "\\end{document}\n",
                encoding="utf-8",
                newline="\n",
            )
            completed = subprocess.run(
                [
                    *resolved_command,
                    "-xelatex",
                    "-no-shell-escape",
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    "-file-line-error",
                    str(source),
                ],
                cwd=root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            produced_pdf = source.with_suffix(".pdf").is_file()
    except (OSError, subprocess.TimeoutExpired) as error:
        return ResumeDoctorCheck(
            id=f"command.{command}",
            status="fail",
            path=resolved,
            detail=f"required; compilation probe failed: {error}",
        )
    if completed.returncode != 0 or not produced_pdf:
        return ResumeDoctorCheck(
            id=f"command.{command}",
            status="fail",
            path=resolved,
            detail=f"required; compilation probe exited {completed.returncode}",
        )
    return ResumeDoctorCheck(
        id=f"command.{command}",
        status="pass",
        path=resolved,
        detail="required; XeLaTeX compilation probe passed",
    )


def _probe_command(
    command: str,
    *,
    version_args: tuple[str, ...],
    missing_status: Literal["fail", "attention"],
    purpose: str,
) -> ResumeDoctorCheck:
    resolved = shutil.which(command)
    if resolved is None:
        return ResumeDoctorCheck(
            id=f"command.{command}",
            status=missing_status,
            path=None,
            detail=f"{purpose}; command not found",
        )
    try:
        completed = subprocess.run(
            [resolved, *version_args],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return ResumeDoctorCheck(
            id=f"command.{command}",
            status=missing_status,
            path=resolved,
            detail=f"{purpose}; execution probe failed: {error}",
        )
    if completed.returncode != 0:
        return ResumeDoctorCheck(
            id=f"command.{command}",
            status=missing_status,
            path=resolved,
            detail=f"{purpose}; version probe exited {completed.returncode}",
        )
    return ResumeDoctorCheck(
        id=f"command.{command}",
        status="pass",
        path=resolved,
        detail=f"{purpose}; executable probe passed",
    )


def _probe_poppler(command: str) -> ResumeDoctorCheck:
    try:
        resolved = resolve_pdf_tool(command)
    except ValueError as error:
        return ResumeDoctorCheck(
            id=f"command.{command}",
            status="attention" if command == "pdftoppm" else "fail",
            path=None,
            detail=str(error),
        )
    return ResumeDoctorCheck(
        id=f"command.{command}",
        status="pass",
        path=resolved,
        detail="Poppler-compatible executable probe passed",
    )


def _tool_environment() -> dict[str, str]:
    environment = os.environ.copy()
    if os.name == "nt":
        system_root = (
            environment.get("SystemRoot")
            or environment.get("SYSTEMROOT")
            or environment.get("WINDIR")
            or r"C:\WINDOWS"
        )
        environment.setdefault("SystemRoot", system_root)
        environment.setdefault("WINDIR", system_root)
    return environment


def _command_for_latexmk_path(path: Path) -> list[str]:
    if path.suffix.lower() == ".pl":
        perl = shutil.which("perl")
        if perl is None:
            raise ValueError("perl is required to run latexmk.pl")
        return [perl, str(path)]
    return [str(path)]


def _latexmk_command_works(command: list[str], *, source_dir: Path) -> bool:
    try:
        completed = subprocess.run(
            [*command, "-version"],
            cwd=source_dir,
            env=_tool_environment(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def _resolve_latexmk_command(source_dir: Path) -> list[str]:
    environment = _tool_environment()
    configured = environment.get("LATEXMK_PL")
    if configured:
        candidate = Path(configured).expanduser().resolve()
        if not candidate.is_file():
            raise ValueError(f"LATEXMK_PL does not exist: {candidate}")
        command = _command_for_latexmk_path(candidate)
        if not _latexmk_command_works(command, source_dir=source_dir):
            raise ValueError(f"LATEXMK_PL is not runnable: {candidate}")
        return command

    candidates: list[Path] = []
    latexmk = shutil.which("latexmk")
    if latexmk:
        executable = Path(latexmk).resolve()
        candidates.append(executable)
        if len(executable.parents) >= 3:
            candidates.append(
                executable.parents[2]
                / "texmf-dist"
                / "scripts"
                / "latexmk"
                / "latexmk.pl"
            )
    candidates.append(
        Path.home()
        / "Workspace"
        / "_tools"
        / "texlive"
        / "2025"
        / "texmf-dist"
        / "scripts"
        / "latexmk"
        / "latexmk.pl"
    )
    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen or not candidate.is_file():
            continue
        seen.add(candidate)
        command = _command_for_latexmk_path(candidate)
        if _latexmk_command_works(command, source_dir=source_dir):
            return command
    raise ValueError("latexmk is unavailable; install TeX Live or set LATEXMK_PL")


def list_resumes(paths: ProjectPaths) -> list[ResumeListItem]:
    return [
        ResumeListItem(name=_resume_name(source), source=str(source))
        for source in _discover_resume_sources(_user_resume_root(paths))
    ]


def build_resume(paths: ProjectPaths, resume: str) -> BuildResult:
    root = _resolve_named_resume(paths, resume)
    return _build_resume_root(paths, root, profile="internal", context=None).result


def export_resume(
    paths: ProjectPaths,
    *,
    resume: str,
    profile: ExportProfile,
    output: Path,
    confirm_application: bool,
    recipient: str | None = None,
    purpose: str | None = None,
    watermark: str | None = None,
) -> ExportResult:
    root = _resolve_named_resume(paths, resume)
    if output.suffix.lower() != ".pdf":
        raise ValueError("resume export destination must use the .pdf extension")
    if output.exists():
        raise ValueError(f"resume export refuses to overwrite: {output}")
    source_text = root.source.read_text(encoding="utf-8-sig")
    record_id = _validate_claim_boundary(
        paths,
        root.name,
        source_text,
        profile=profile,
        confirm_application=confirm_application,
    )
    context = _export_context(
        profile,
        recipient=recipient,
        purpose=purpose,
        watermark=watermark,
    )
    built = _build_resume_root(paths, root, profile=profile, context=context)
    sanitized = sanitize_pdf(Path(built.result.pdf))
    expected_images = 1 if profile == "application" and root.avatar is not None else 0
    privacy = audit_pdf(paths.project_root, sanitized, expected_images=expected_images)
    identity = _read_identity(root)
    _validate_export_projection(
        extract_pdf_text(sanitized),
        profile=profile,
        identity=identity,
        context=context,
    )

    digest = hashlib.sha256(sanitized).hexdigest()
    receipt_root = paths.local_state_root / "export-receipts"
    receipt = receipt_root / f"{uuid4()}.json"
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    created_output = False
    try:
        _publish_without_overwrite(sanitized, output)
        created_output = True
        receipt_root.mkdir(parents=True, exist_ok=True)
        receipt.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    "resume": root.name,
                    "profile": profile,
                    "export_date": context.export_date,
                    "export_id": context.export_id,
                    "recipient": context.recipient,
                    "purpose": context.purpose,
                    "watermark": context.watermark,
                    "resume_record_id": str(record_id) if record_id is not None else None,
                    "template": "career-os",
                    "output": str(output),
                    "sha256": digest,
                    "source": {
                        "path": _display_path(paths, root.source),
                        "sha256": built.source_sha256,
                    },
                    "identity": {
                        "path": _display_path(paths, root.identity),
                        "sha256": built.identity_sha256,
                    },
                    "avatar": (
                        {
                            "path": _display_path(paths, root.avatar),
                            "sha256": built.avatar_sha256,
                        }
                        if root.avatar is not None and built.avatar_sha256 is not None
                        else None
                    ),
                    "privacy": privacy.as_dict(),
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except OSError:
        if created_output:
            output.unlink(missing_ok=True)
        receipt.unlink(missing_ok=True)
        raise
    return ExportResult(
        profile=profile,
        output=str(output),
        sha256=digest,
        receipt=str(receipt),
        privacy=privacy,
        export_id=context.export_id,
        recipient=context.recipient,
        purpose=context.purpose,
        watermark=context.watermark,
    )


def validate_resume_source(paths: ProjectPaths, source: Path) -> None:
    _resolve_resume_source(paths, source)


def _user_resume_root(paths: ProjectPaths) -> Path:
    return (paths.data_root / "70-career-communication/resumes").resolve()


def _discover_resume_sources(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    sources: list[Path] = []
    by_name: dict[str, Path] = {}
    for candidate in sorted(root.rglob("*.tex")):
        if candidate.is_symlink() or not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if not resolved.is_relative_to(root):
            raise ValueError(f"resume source resolves outside the resume root: {candidate}")
        text = resolved.read_text(encoding="utf-8-sig")
        if not _DOCUMENT_CLASS.search(_strip_tex_comments(text)):
            continue
        name = _resume_name(resolved)
        previous = by_name.get(name)
        if previous is not None:
            raise ValueError(
                f"duplicate resume name {name!r}: {previous} and {resolved}"
            )
        by_name[name] = resolved
        sources.append(resolved)
    return sources


def _resume_name(source: Path) -> str:
    name = source.parent.name if source.stem == "resume" else source.stem
    if not _SAFE_NAME.fullmatch(name) or name in {".", ".."}:
        raise ValueError(f"resume source produces an invalid name: {source}")
    return name


def _resolve_named_resume(paths: ProjectPaths, name: str) -> ResolvedResumeRoot:
    if not _SAFE_NAME.fullmatch(name) or name in {".", ".."}:
        raise ValueError("resume name must be one safe path segment")
    matches = [
        source
        for source in _discover_resume_sources(_user_resume_root(paths))
        if _resume_name(source) == name
    ]
    if not matches:
        fixture_root = (paths.project_root / "system/resume/fixtures").resolve()
        matches = [
            source
            for source in _discover_resume_sources(fixture_root)
            if _resume_name(source) == name
        ]
    if not matches:
        available = ", ".join(item.name for item in list_resumes(paths)) or "none"
        raise ValueError(f"unknown resume {name!r}; available: {available}")
    return _resolve_resume_source(paths, matches[0])


def _resolve_resume_source(paths: ProjectPaths, source: Path) -> ResolvedResumeRoot:
    source = source.resolve()
    allowed_roots = (
        _user_resume_root(paths),
        (paths.project_root / "system/resume/fixtures").resolve(),
    )
    boundary = next((root for root in allowed_roots if source.is_relative_to(root)), None)
    if boundary is None:
        raise ValueError("resume source is outside the user resume or system fixture roots")
    if not source.is_file() or source.suffix.lower() != ".tex":
        raise ValueError(f"resume source is missing or is not TeX: {source}")
    source_text = source.read_text(encoding="utf-8-sig")
    if not _DOCUMENT_CLASS.search(_strip_tex_comments(source_text)):
        raise ValueError(f"resume source must use \\documentclass{{career-os}}: {source}")
    identity = source.parent / "identity.tex"
    if not identity.is_file() or identity.is_symlink():
        raise ValueError(f"resume identity is missing: {identity}")
    identity = identity.resolve()
    if not identity.is_relative_to(boundary):
        raise ValueError("resume identity resolves outside its owned resume boundary")
    texts = {
        source.name: source_text,
        "identity.tex": identity.read_text(encoding="utf-8-sig"),
    }
    audit_tex_bundle(paths.project_root, texts, declared_inputs={"identity.tex"})
    temporary = ResolvedResumeRoot(
        name=_resume_name(source),
        source_root=source.parent,
        source=source,
        identity=identity,
        avatar=None,
    )
    parsed_identity = _parse_identity(temporary, texts)
    avatar = _resolve_avatar(source.parent, parsed_identity.avatar_asset)
    if avatar is not None:
        _verify_avatar(avatar)
    return ResolvedResumeRoot(
        name=temporary.name,
        source_root=temporary.source_root,
        source=temporary.source,
        identity=temporary.identity,
        avatar=avatar,
    )


def _resolve_avatar(root: Path, value: str | None) -> Path | None:
    if value is None:
        return None
    if (
        not value
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or ":" in value
        or "\x00" in value
    ):
        raise ValueError("ResumeAvatarAsset must be one local filename stem or image filename")
    supplied = Path(value)
    candidates = (
        [root / value]
        if supplied.suffix.lower() in _AVATAR_SUFFIXES
        else [root / f"{value}{suffix}" for suffix in _AVATAR_SUFFIXES]
    )
    existing = [candidate.resolve() for candidate in candidates if candidate.is_file()]
    if not existing:
        raise ValueError(f"resume avatar is missing for ResumeAvatarAsset={value!r}")
    if len(existing) > 1:
        raise ValueError(f"resume avatar stem is ambiguous: {value}")
    avatar = existing[0]
    if not avatar.is_relative_to(root.resolve()):
        raise ValueError("resume avatar resolves outside its resume root")
    return avatar


def _verify_avatar(path: Path) -> None:
    data = path.read_bytes()
    if len(data) > 10 * 1024 * 1024:
        raise ValueError(f"resume avatar exceeds the 10 MiB safety limit: {path}")
    if path.suffix.lower() == ".png":
        _verify_png_avatar(data, path)
    elif path.suffix.lower() in {".jpg", ".jpeg"}:
        _verify_jpeg_avatar(data, path)
    else:
        raise ValueError(f"resume avatar must be PNG or JPEG: {path}")


def _verify_png_avatar(data: bytes, path: Path) -> None:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"resume asset content does not match image/png: {path}")
    offset = 8
    saw_header = False
    saw_data = False
    saw_end = False
    forbidden_metadata = {b"eXIf", b"iTXt", b"tEXt", b"tIME", b"zTXt"}
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError(f"resume PNG has a truncated chunk: {path}")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_end = offset + 12 + length
        if chunk_end > len(data):
            raise ValueError(f"resume PNG has an invalid chunk length: {path}")
        payload = data[offset + 8 : offset + 8 + length]
        expected_crc = struct.unpack(">I", data[offset + 8 + length : chunk_end])[0]
        if zlib.crc32(chunk_type + payload) & 0xFFFFFFFF != expected_crc:
            raise ValueError(f"resume PNG has a corrupt chunk checksum: {path}")
        if chunk_type in forbidden_metadata:
            raise ValueError(f"resume PNG contains disallowed metadata: {path}")
        if not saw_header:
            if chunk_type != b"IHDR" or length != 13:
                raise ValueError(f"resume PNG must begin with one IHDR chunk: {path}")
            width, height = struct.unpack(">II", payload[:8])
            _verify_avatar_dimensions(width, height, path)
            saw_header = True
        elif chunk_type == b"IHDR":
            raise ValueError(f"resume PNG contains more than one IHDR chunk: {path}")
        if chunk_type == b"IDAT":
            saw_data = True
        if chunk_type == b"IEND":
            if length != 0 or chunk_end != len(data):
                raise ValueError(f"resume PNG has an invalid IEND boundary: {path}")
            saw_end = True
        offset = chunk_end
    if not (saw_header and saw_data and saw_end):
        raise ValueError(f"resume PNG is missing required image chunks: {path}")


def _verify_jpeg_avatar(data: bytes, path: Path) -> None:
    if not (data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9")):
        raise ValueError(f"resume asset content does not match image/jpeg: {path}")
    offset = 2
    dimensions: tuple[int, int] | None = None
    saw_scan = False
    standalone = {0x01, *range(0xD0, 0xD8)}
    sof_markers = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
    while offset < len(data) - 2:
        if data[offset] != 0xFF:
            raise ValueError(f"resume JPEG has an invalid marker boundary: {path}")
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            break
        marker = data[offset]
        offset += 1
        if marker in standalone:
            continue
        if offset + 2 > len(data):
            raise ValueError(f"resume JPEG has a truncated marker: {path}")
        length = struct.unpack(">H", data[offset : offset + 2])[0]
        if length < 2 or offset + length > len(data):
            raise ValueError(f"resume JPEG has an invalid marker length: {path}")
        payload = data[offset + 2 : offset + length]
        if marker == 0xFE or 0xE1 <= marker <= 0xED or marker == 0xEF:
            raise ValueError(f"resume JPEG contains disallowed metadata: {path}")
        if marker in sof_markers:
            if len(payload) < 5:
                raise ValueError(f"resume JPEG has a truncated frame header: {path}")
            height, width = struct.unpack(">HH", payload[1:5])
            dimensions = (width, height)
        if marker == 0xDA:
            saw_scan = True
            break
        offset += length
    if dimensions is None or not saw_scan:
        raise ValueError(f"resume JPEG is missing frame or scan data: {path}")
    _verify_avatar_dimensions(*dimensions, path)


def _verify_avatar_dimensions(width: int, height: int, path: Path) -> None:
    if width < 1 or height < 1 or width > 8192 or height > 8192 or width * height > 25_000_000:
        raise ValueError(f"resume avatar dimensions exceed safe bounds: {path}")


def _read_identity(root: ResolvedResumeRoot) -> ResumeIdentity:
    return _parse_identity(
        root,
        {
            root.source.name: root.source.read_text(encoding="utf-8-sig"),
            "identity.tex": root.identity.read_text(encoding="utf-8-sig"),
        },
    )


def _parse_identity(
    root: ResolvedResumeRoot, texts: dict[str, str]
) -> ResumeIdentity:
    for relative, text in texts.items():
        if relative != "identity.tex" and _IDENTITY_DEFINITION.search(
            _strip_tex_comments(text)
        ):
            raise ValueError("resume identity macros may be defined only in identity.tex")
    observed: dict[str, str] = {}
    for match in _IDENTITY_MACRO.finditer(_strip_tex_comments(texts["identity.tex"])):
        name = match.group("name")
        if name in observed:
            raise ValueError(f"resume identity defines {name} more than once")
        raw = match.group("value")
        if name == "ResumeAvatarAsset" and not raw.strip():
            observed[name] = ""
        else:
            observed[name] = _normalize_identity_value(name, raw)
    legacy_required = {"ResumeFullName", "ResumeEmail", "ResumePhone"}
    current_required = {"CareerOSFullName", "CareerOSEmail", "CareerOSPhone"}
    if legacy_required.issubset(observed):
        return ResumeIdentity(
            full_name=observed["ResumeFullName"],
            email=observed["ResumeEmail"],
            phone=observed["ResumePhone"],
            avatar_asset=observed.get("ResumeAvatarAsset") or None,
        )
    if current_required.issubset(observed):
        return ResumeIdentity(
            full_name=observed["CareerOSFullName"],
            email=observed["CareerOSEmail"],
            phone=observed["CareerOSPhone"],
            avatar_asset=None,
        )
    missing = sorted(legacy_required - observed.keys())
    raise ValueError("resume identity is missing macros: " + ", ".join(missing))


def _build_resume_root(
    paths: ProjectPaths,
    root: ResolvedResumeRoot,
    *,
    profile: BuildProfile,
    context: ExportContext | None,
) -> _BuiltResume:
    if profile != "internal" and context is None:
        raise ValueError("preview and application builds require an export context")
    build_context = context or _internal_build_context()
    if build_context.profile != profile:
        raise ValueError("resume build context profile does not match the requested profile")
    latexmk = _resolve_latexmk_command(paths.project_root)
    if shutil.which("xelatex") is None:
        raise ValueError("resume build requires latexmk and XeLaTeX")

    source_sha256 = _sha256_file(root.source)
    identity_sha256 = _sha256_file(root.identity)
    avatar_sha256 = _sha256_file(root.avatar) if root.avatar is not None else None
    build_base = (paths.build_root / "resume").resolve()
    build_base.mkdir(parents=True, exist_ok=True)
    build_root = (build_base / root.name / str(uuid4())).resolve()
    if not build_root.is_relative_to(build_base):
        raise ValueError("resume build path escapes the configured build root")
    build_root.mkdir(parents=True, exist_ok=False)
    isolated_root = build_root / "source"
    isolated_root.mkdir()
    isolated_source = isolated_root / root.source.name
    isolated_identity = isolated_root / "identity.tex"
    shutil.copyfile(root.source, isolated_source)
    shutil.copyfile(root.identity, isolated_identity)
    _verify_hash(isolated_source, source_sha256, label="isolated resume source")
    _verify_hash(isolated_identity, identity_sha256, label="isolated resume identity")
    avatar: Path | None = None
    if profile != "preview" and root.avatar is not None:
        avatar = isolated_root / root.avatar.name
        shutil.copyfile(root.avatar, avatar)
        assert avatar_sha256 is not None
        _verify_hash(avatar, avatar_sha256, label="isolated resume avatar")

    wrapper = build_root / "career-os-build.tex"
    wrapper.write_text(
        _build_wrapper(isolated_source, build_context, avatar),
        encoding="utf-8",
        newline="\n",
    )
    environment = _tool_environment()
    texinputs = os.pathsep.join(
        (str(isolated_root), str(paths.project_root / "system/resume"), "")
    )
    if environment.get("TEXINPUTS"):
        texinputs += environment["TEXINPUTS"]
    environment["TEXINPUTS"] = texinputs
    opentypefonts = os.pathsep.join((f"{paths.local_state_root / 'fonts'}//", ""))
    if environment.get("OPENTYPEFONTS"):
        opentypefonts += environment["OPENTYPEFONTS"]
    environment["OPENTYPEFONTS"] = opentypefonts
    completed = subprocess.run(
        [
            *latexmk,
            "-xelatex",
            "-no-shell-escape",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            f"-outdir={build_root}",
            str(wrapper),
        ],
        cwd=build_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    log_path = build_root / "career-os-build.log"
    pdf_path = build_root / "career-os-build.pdf"
    if completed.returncode != 0 or not pdf_path.is_file():
        output = "\n".join((completed.stdout + "\n" + completed.stderr).splitlines()[-60:])
        raise ValueError(f"resume build failed; inspect {log_path}\n{output}")
    return _BuiltResume(
        result=BuildResult(
            resume=root.name,
            source=str(root.source),
            pdf=str(pdf_path),
            log=str(log_path),
        ),
        source_sha256=source_sha256,
        identity_sha256=identity_sha256,
        avatar_sha256=avatar_sha256,
    )


def _verify_hash(path: Path, expected: str, *, label: str) -> None:
    if _sha256_file(path) != expected:
        raise ValueError(f"{label} hash mismatch: {path}")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _publish_without_overwrite(payload: bytes, destination: Path) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.stem}-",
            suffix=".pdf.tmp",
            dir=destination.parent,
            delete=False,
        ) as handle:
            handle.write(payload)
            temporary = Path(handle.name)
        os.link(temporary, destination)
    except FileExistsError as error:
        raise ValueError(f"resume export refuses to overwrite: {destination}") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _internal_build_context() -> ExportContext:
    now = datetime.now(UTC)
    return ExportContext(
        profile="internal",
        recipient="Internal owner",
        purpose="Internal build",
        watermark="INTERNAL BUILD - NOT FOR DISTRIBUTION",
        export_date=now.date().isoformat(),
        export_id="INTERNAL",
    )


def _export_context(
    profile: ExportProfile,
    *,
    recipient: str | None,
    purpose: str | None,
    watermark: str | None,
) -> ExportContext:
    recipient_value = _normalize_export_field("recipient", recipient)
    purpose_value = _normalize_export_field("purpose", purpose)
    watermark_value = _normalize_export_field("watermark", watermark)
    now = datetime.now(UTC)
    prefix = "HC" if profile == "preview" else "AP"
    export_id = f"{prefix}-{now:%Y%m%d}-{secrets.token_hex(4).upper()}"
    if not _EXPORT_ID.fullmatch(export_id):
        raise ValueError("generated export ID is invalid")
    return ExportContext(
        profile=profile,
        recipient=recipient_value,
        purpose=purpose_value,
        watermark=watermark_value,
        export_date=now.date().isoformat(),
        export_id=export_id,
    )


def _normalize_export_field(name: str, value: str | None) -> str:
    normalized = re.sub(r"\s+", " ", (value or "").strip())
    if len(normalized) > 120:
        raise ValueError(f"resume export {name} must not exceed 120 characters")
    if _CONTEXT_CONTROL.search(normalized):
        raise ValueError(f"resume export {name} contains unsafe TeX or control characters")
    return normalized


def _normalize_identity_value(name: str, value: str) -> str:
    if _IDENTITY_UNSAFE_ESCAPE.search(value) or _IDENTITY_UNESCAPED_SPECIAL.search(value):
        raise ValueError(f"resume identity {name} contains unsafe TeX content")
    literal = re.sub(r"\s+", " ", _IDENTITY_ESCAPE.sub(r"\1", value).strip())
    if not literal:
        raise ValueError(f"resume identity {name} is empty")
    unsafe_control = any(ord(character) < 32 or ord(character) == 127 for character in literal)
    if len(literal) > 120 or unsafe_control:
        raise ValueError(f"resume identity {name} contains unsafe content")
    return literal


def _validate_export_projection(
    pdf_text: str,
    *,
    profile: ExportProfile,
    identity: ResumeIdentity,
    context: ExportContext,
) -> None:
    required = {"full name": identity.full_name, "export ID": context.export_id}
    required.update(
        (name, value)
        for name, value in (
            ("recipient", context.recipient),
            ("purpose", context.purpose),
            ("watermark", context.watermark),
        )
        if value
    )
    if profile == "application":
        required.update({"email": identity.email, "phone": identity.phone})
    missing = [
        name for name, value in required.items() if not _projection_contains(pdf_text, value)
    ]
    if missing:
        raise ValueError("resume PDF is missing required projection fields: " + ", ".join(missing))
    if profile == "preview":
        leaked = [
            name
            for name, value in (("email", identity.email), ("phone", identity.phone))
            if _projection_contains(pdf_text, value)
        ]
        if leaked:
            raise ValueError("resume preview leaked private identity fields: " + ", ".join(leaked))


def _projection_contains(text: str, expected: str) -> bool:
    normalized_text = _normalize_projection_text(text)
    normalized_expected = _normalize_projection_text(expected)
    if normalized_expected in normalized_text:
        return True
    return re.sub(r"\s+", "", normalized_expected) in re.sub(r"\s+", "", normalized_text)


def _normalize_projection_text(value: str) -> str:
    hyphens = dict.fromkeys(map(ord, "‐‑‒–—―−\u00ad"), "-")
    return re.sub(r"\s+", " ", value.translate(hyphens)).strip()


def _build_wrapper(
    source: Path,
    context: ExportContext,
    avatar: Path | None,
) -> str:
    source_text = _safe_tex_path(source)
    avatar_text = _safe_tex_path(avatar) if avatar is not None else ""
    return (
        f"\\def\\ResumeExportProfile{{{context.profile}}}\n"
        f"\\def\\ResumeExportRecipient{{\\detokenize{{{_safe_tex_literal(context.recipient)}}}}}\n"
        f"\\def\\ResumeExportPurpose{{\\detokenize{{{_safe_tex_literal(context.purpose)}}}}}\n"
        f"\\def\\ResumeExportWatermark{{\\detokenize{{{_safe_tex_literal(context.watermark)}}}}}\n"
        f"\\def\\ResumeExportDate{{{context.export_date}}}\n"
        f"\\def\\ResumeExportId{{{context.export_id}}}\n"
        f"\\def\\ResumeHasAvatar{{{'1' if avatar is not None else '0'}}}\n"
        f"\\def\\ResumeAvatarPath{{\\detokenize{{{avatar_text}}}}}\n"
        f"\\def\\CareerOSSourcePath{{\\detokenize{{{source_text}}}}}\n"
        "\\input{\\CareerOSSourcePath}\n"
    )


def _safe_tex_path(path: Path) -> str:
    value = path.resolve().as_posix()
    if any(character in value for character in "%#{}"):
        raise ValueError(f"resume paths cannot contain TeX control characters: {path}")
    return value


def _safe_tex_literal(value: str) -> str:
    if _CONTEXT_CONTROL.search(value):
        raise ValueError("resume export context contains unsafe TeX or control characters")
    return value


def _validate_claim_boundary(
    paths: ProjectPaths,
    resume_name: str,
    source_text: str,
    *,
    profile: ExportProfile,
    confirm_application: bool,
) -> UUID | None:
    searchable = _strip_tex_comments(source_text)
    claimed: list[UUID] = []
    for raw in _raw_claim_ids(searchable):
        try:
            claimed.append(UUID(raw.strip()))
        except ValueError as error:
            raise ValueError(f"invalid resume claim ID: {raw}") from error
    used = set(claimed)
    records = _record_index(paths)
    resume_record = _find_resume_record(records, resume_name)
    if resume_record is not None:
        envelope = resume_record.envelope
        assert isinstance(envelope, CommunicationResume)
        approved = {
            reference.target_id
            for reference in envelope.refs
            if reference.required and reference.relation == "uses-claim"
        }
        unsupported = used - approved
        unused = approved - used
        if unsupported:
            raise ValueError(
                "resume uses claims not approved by its communication.resume record: "
                + _ids(unsupported)
            )
        if unused:
            raise ValueError(
                "communication.resume approves claims not present in source: " + _ids(unused)
            )
        if profile == "preview" and envelope.status not in {"validated", "application-ready"}:
            raise ValueError("preview export requires a validated communication.resume record")
    elif used:
        raise ValueError(
            f"resume {resume_name!r} uses claims but has no matching communication.resume record"
        )

    for claim_id in sorted(used, key=str):
        claim = records.get(claim_id)
        if claim is None:
            raise ValueError(f"approved claim record is missing: {claim_id}")
        if claim.envelope.kind != "evidence.claim":
            raise ValueError(f"approved claim ID is not an evidence.claim: {claim_id}")
        if claim.envelope.status != "approved":
            raise ValueError(f"claim is not approved: {claim_id}")
        if claim.envelope.visibility not in {"shareable", "public"}:
            raise ValueError(f"claim is not shareable: {claim_id}")
        if not isinstance(claim.envelope, EvidenceClaim):
            raise ValueError(f"approved claim ID has an invalid payload: {claim_id}")
        required_uses = (
            {"application"} if profile == "application" else {"resume", "recruiter", "public"}
        )
        if not required_uses.intersection(claim.envelope.allowed_uses):
            raise ValueError(f"claim is not approved for the {profile} export profile: {claim_id}")
        supporting = [
            reference
            for reference in claim.envelope.refs
            if reference.required and reference.relation == "supported-by"
        ]
        if not supporting:
            raise ValueError(f"claim has no required supported-by evidence: {claim_id}")
        for reference in supporting:
            evidence = records.get(reference.target_id)
            if evidence is None or not (
                evidence.envelope.kind == "evidence.work"
                and evidence.envelope.status in {"grounded", "verified"}
                or evidence.envelope.kind == "evidence.story"
                and evidence.envelope.status == "reviewed"
            ):
                raise ValueError(f"claim support is missing or invalid: {reference.target_id}")

    if profile == "application":
        if not confirm_application:
            raise ValueError("application export requires --confirm-application")
        if resume_record is None:
            raise ValueError("application export requires a matching communication.resume record")
        envelope = resume_record.envelope
        assert isinstance(envelope, CommunicationResume)
        if envelope.status != "application-ready" or envelope.export_policy != "application":
            raise ValueError(
                "application export requires an application-ready communication.resume record"
            )
        _validate_application_bullets(searchable)
        if not claimed:
            raise ValueError("application export requires at least one approved claim")
        target_jd_id = _one_required_ref(envelope, "target-jd")
        identity_profile_id = _one_required_ref(envelope, "identity-profile")
        jd = _require_record_kind(records, target_jd_id, "market.jd")
        if not isinstance(jd.envelope, MarketJD) or jd.envelope.status != "reviewed":
            raise ValueError("application export requires a reviewed target JD")
        source_body = extract_markdown_section(jd.body, "JD 原文")
        source_body_sha256 = hashlib.sha256(source_body.encode("utf-8")).hexdigest()
        if source_body_sha256 != jd.envelope.source_body_sha256:
            raise ValueError("application target JD source body has changed")
        profile_record = _require_record_kind(
            records, identity_profile_id, "communication.profile"
        )
        if not isinstance(profile_record.envelope, CommunicationProfile) or (
            profile_record.envelope.status != "approved"
            or profile_record.envelope.identity_policy != "application"
        ):
            raise ValueError("application export requires an approved application identity")
    return resume_record.envelope.id if resume_record is not None else None


def _find_resume_record(
    records: dict[UUID, ParsedRecord], resume_name: str
) -> ParsedRecord | None:
    matches = [
        record
        for record in records.values()
        if isinstance(record.envelope, CommunicationResume)
        and record.envelope.root_name == resume_name
        and record.envelope.status != "superseded"
    ]
    if len(matches) > 1:
        raise ValueError(
            f"multiple active communication.resume records use root_name={resume_name!r}"
        )
    return matches[0] if matches else None


def _one_required_ref(envelope: CommunicationResume, relation: str) -> UUID:
    values = {
        reference.target_id
        for reference in envelope.refs
        if reference.required and reference.relation == relation
    }
    if len(values) != 1:
        raise ValueError(f"application resume requires exactly one required {relation} reference")
    return next(iter(values))


def _record_index(paths: ProjectPaths) -> dict[UUID, ParsedRecord]:
    records: dict[UUID, ParsedRecord] = {}
    if not paths.data_root.is_dir():
        return records
    for path in sorted(paths.data_root.rglob("*.md")):
        relative = path.relative_to(paths.data_root)
        if path.name == "README.md" or any(part.startswith("_") for part in relative.parts[:-1]):
            continue
        record = load_record(path)
        if record.envelope.id in records:
            raise ValueError(f"duplicate record ID: {record.envelope.id}")
        records[record.envelope.id] = record
    return records


def _require_record_kind(
    records: dict[UUID, ParsedRecord], record_id: UUID, kind: str
) -> ParsedRecord:
    record = records.get(record_id)
    if record is None or record.envelope.kind != kind:
        raise ValueError(f"{kind} record is missing or invalid: {record_id}")
    return record


def _ids(values: set[UUID]) -> str:
    return ", ".join(str(item) for item in sorted(values, key=str))


def _strip_tex_comments(text: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in text.splitlines())


def _validate_application_bullets(source_text: str) -> None:
    items = list(_BULLET.finditer(source_text))
    if not items:
        raise ValueError("application resume source contains no evidence-bound bullets")
    for index, item in enumerate(items):
        end = items[index + 1].start() if index + 1 < len(items) else len(source_text)
        if not _raw_claim_ids(source_text[item.end() : end]):
            raise ValueError(
                "every application resume experience bullet must bind one or more claim IDs"
            )


def _raw_claim_ids(source_text: str) -> list[str]:
    values = [raw.strip() for raw in _CLAIM.findall(source_text)]
    for raw_group in _CLAIMS.findall(source_text):
        values.extend(item.strip() for item in raw_group.split(",") if item.strip())
    return values


def _display_path(paths: ProjectPaths, path: Path) -> str:
    resolved = path.resolve()
    for root in (paths.data_root.resolve(), paths.project_root.resolve()):
        if resolved.is_relative_to(root):
            return resolved.relative_to(root).as_posix()
    return str(resolved)
