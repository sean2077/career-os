from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from pydantic import BaseModel, ConfigDict, Field
from pypdf import PdfReader, PdfWriter


class SecretPattern(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    regex: str


@dataclass(frozen=True)
class PrivacyReport:
    pages: int
    text_characters: int
    images: int
    checks: tuple[str, ...]

    def as_dict(self) -> dict[str, int | list[str]]:
        payload = asdict(self)
        payload["checks"] = list(self.checks)
        return payload


_FORBIDDEN_TEX = {
    "attachment": re.compile(r"\\(?:attachfile|embeddedfile)\b", re.IGNORECASE),
    "image": re.compile(r"\\includegraphics\b", re.IGNORECASE),
    "pdf-include": re.compile(r"\\includepdf\b", re.IGNORECASE),
    "file-primitive": re.compile(r"\\(?:include|openin|read)\b", re.IGNORECASE),
    "shell-or-pdf-primitive": re.compile(
        r"\\(?:write18|immediate|special|pdfextension|pdfobj|pdfinfo)\b",
        re.IGNORECASE,
    ),
}
_INPUT = re.compile(r"\\input\s*\{([^{}]+)\}", re.IGNORECASE)
_ANY_INPUT = re.compile(r"\\input\b", re.IGNORECASE)
_RESERVED_DEFINITION = re.compile(
    r"\\(?:def|gdef|edef|xdef|newcommand|renewcommand|providecommand)\s*"
    r"(?:\{)?\\(?:CareerOS(?!(?:FullName|Email|Phone|Location|"
    r"(?:LatinBody|LatinDisplay|CJKBody|CJKDisplay|CJKMono)"
    r"(?:FontPath|RegularFont|BoldFont|ItalicFont|BoldItalicFont))\b)|ResumeExport)",
    re.IGNORECASE,
)


def load_secret_patterns(project_root: Path) -> list[SecretPattern]:
    path = project_root / "system/resume/secret-patterns.json"
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        raise ValueError("secret-patterns.json must contain an array")
    patterns = [SecretPattern.model_validate(item) for item in loaded]
    for pattern in patterns:
        re.compile(pattern.regex)
    return patterns


def audit_tex_source(project_root: Path, text: str) -> tuple[str, ...]:
    searchable = _strip_tex_comments(text)
    failures = [name for name, pattern in _FORBIDDEN_TEX.items() if pattern.search(searchable)]
    if _ANY_INPUT.search(searchable):
        failures.append("file-input")
    failures.extend(f"secret:{item}" for item in _matching_secrets(project_root, searchable))
    if failures:
        raise ValueError("resume source failed export checks: " + ", ".join(failures))
    return (
        "source-links-confined-to-final-pdf-sanitization",
        "source-no-attachments-or-images",
        "source-no-file-or-shell-primitives",
        "source-no-configured-secrets",
    )


def audit_tex_bundle(
    project_root: Path,
    texts: dict[str, str],
    *,
    declared_inputs: set[str],
) -> tuple[str, ...]:
    failures: list[str] = []
    observed_inputs: set[str] = set()
    for relative, text in texts.items():
        searchable = _strip_tex_comments(text)
        for name, pattern in _FORBIDDEN_TEX.items():
            if pattern.search(searchable):
                failures.append(f"{name}:{relative}")
        inputs = _INPUT.findall(searchable)
        if len(inputs) != len(_ANY_INPUT.findall(searchable)):
            failures.append(f"file-input-syntax:{relative}")
        if _RESERVED_DEFINITION.search(searchable):
            failures.append(f"reserved-export-macro:{relative}")
        for raw in inputs:
            normalized = raw.strip()
            if not normalized.lower().endswith(".tex"):
                normalized += ".tex"
            input_path = PurePosixPath(normalized)
            if (
                not normalized
                or "\\" in normalized
                or input_path.is_absolute()
                or ".." in input_path.parts
            ):
                failures.append(f"file-input-path:{relative}")
            else:
                observed_inputs.add(normalized.replace("\\", "/"))
        failures.extend(
            f"secret:{item}:{relative}"
            for item in _matching_secrets(project_root, searchable)
        )
    undeclared = observed_inputs - declared_inputs
    unused = declared_inputs - observed_inputs
    failures.extend(f"undeclared-input:{item}" for item in sorted(undeclared))
    failures.extend(f"unused-dependency:{item}" for item in sorted(unused))
    if failures:
        raise ValueError("resume source bundle failed export checks: " + ", ".join(failures))
    return (
        "source-dependencies-declared-and-used",
        "source-links-confined-to-final-pdf-sanitization",
        "source-no-attachments-or-images",
        "source-no-undeclared-file-or-shell-primitives",
        "source-no-configured-secrets",
    )


def audit_pdf(
    project_root: Path, source: Path | bytes, *, expected_images: int = 0
) -> PrivacyReport:
    reader = _reader(source)
    if reader.is_encrypted:
        raise ValueError("encrypted PDFs cannot be exported")

    failures: list[str] = []
    if reader.attachments:
        failures.append("embedded-files")
    if reader.xmp_metadata is not None:
        failures.append("xmp-metadata")
    metadata: Any = reader.metadata or {}
    for key in ("/Author", "/Title", "/Subject", "/Keywords"):
        if str(metadata.get(key, "")).strip():
            failures.append(f"metadata:{key[1:].lower()}")
    catalog = _resolve(reader.trailer.get("/Root"))
    if hasattr(catalog, "get"):
        if catalog.get("/OpenAction") is not None or catalog.get("/AA") is not None:
            failures.append("document-action")
        names = _resolve(catalog.get("/Names"))
        if hasattr(names, "get") and names.get("/JavaScript") is not None:
            failures.append("document-javascript")

    image_count = 0
    for index, page in enumerate(reader.pages, start=1):
        page_images = len(page.images)
        image_count += page_images
        annotations = page.get("/Annots", [])
        for reference in annotations:
            annotation = _resolve(reference)
            if not hasattr(annotation, "get"):
                continue
            subtype = str(annotation.get("/Subtype", ""))
            action = _resolve(annotation.get("/A"))
            if subtype == "/FileAttachment":
                failures.append(f"attachment-annotation:page-{index}")
            if subtype == "/Link" or annotation.get("/Dest") is not None:
                failures.append(f"link:page-{index}")
            if hasattr(action, "get") or annotation.get("/AA") is not None:
                failures.append(f"action:page-{index}")

    text = extract_pdf_text(source)
    if image_count != expected_images:
        failures.append(f"images:expected-{expected_images}:actual-{image_count}")
    failures.extend(f"secret:{item}" for item in _matching_secrets(project_root, text))
    if failures:
        raise ValueError("PDF failed export checks: " + ", ".join(sorted(set(failures))))
    return PrivacyReport(
        pages=len(reader.pages),
        text_characters=len(text),
        images=image_count,
        checks=(
            "pdf-no-unsafe-document-metadata",
            "pdf-no-xmp-metadata",
            "pdf-no-external-links",
            "pdf-expected-image-count",
            "pdf-no-configured-secrets",
        ),
    )


def extract_pdf_text(source: Path | bytes) -> str:
    try:
        pdftotext = resolve_pdf_tool("pdftotext")
    except ValueError:
        pdftotext = None
    if pdftotext is not None:
        payload = source.read_bytes() if isinstance(source, Path) else source
        try:
            completed = subprocess.run(
                [pdftotext, "-enc", "UTF-8", "-", "-"],
                input=payload,
                check=False,
                capture_output=True,
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
        else:
            if completed.returncode == 0:
                return completed.stdout.decode("utf-8", errors="replace")
    reader = _reader(source)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def sanitize_pdf(source: Path) -> bytes:
    reader = PdfReader(source)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.remove_links()
    writer.add_metadata({"/Creator": "Career OS", "/Producer": "Career OS"})
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def pdf_tool_candidates(name: str) -> list[Path]:
    executable_name = f"{name}.exe" if os.name == "nt" else name
    candidates: list[Path] = []
    xelatex_names = ("xelatex.exe", "xelatex") if os.name == "nt" else ("xelatex",)
    for xelatex_name in xelatex_names:
        xelatex = shutil.which(xelatex_name)
        if xelatex:
            candidates.append(Path(xelatex).resolve().with_name(executable_name))
            break
    path_names = (f"{name}.exe", name) if os.name == "nt" else (name,)
    for path_name in path_names:
        resolved = shutil.which(path_name)
        if resolved:
            candidates.append(Path(resolved).resolve())
    existing: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen or not candidate.is_file():
            continue
        seen.add(candidate)
        existing.append(candidate)
    return existing


def pdf_tool_is_poppler_compatible(path: Path) -> bool:
    try:
        completed = subprocess.run(
            [str(path), "-v"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "poppler" in f"{completed.stdout}\n{completed.stderr}".casefold()


def resolve_pdf_tool(name: str) -> str:
    rejected: list[Path] = []
    for candidate in pdf_tool_candidates(name):
        if pdf_tool_is_poppler_compatible(candidate):
            return str(candidate)
        rejected.append(candidate)
    suffix = (
        "; rejected incompatible tool(s): " + ", ".join(map(str, rejected))
        if rejected
        else ""
    )
    raise ValueError(f"required Poppler PDF inspection tool is unavailable: {name}{suffix}")


def _reader(source: Path | bytes) -> PdfReader:
    if isinstance(source, Path):
        return PdfReader(source)
    handle: BinaryIO = io.BytesIO(source)
    return PdfReader(handle)


def _resolve(value: Any) -> Any:
    if hasattr(value, "get_object"):
        return value.get_object()
    return value


def _strip_tex_comments(text: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in text.splitlines())


def _matching_secrets(project_root: Path, text: str) -> list[str]:
    return [
        pattern.id
        for pattern in load_secret_patterns(project_root)
        if re.search(pattern.regex, text, flags=re.MULTILINE)
    ]
