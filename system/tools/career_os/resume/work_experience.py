"""Create a temporary BOSS paste aid from an internal resume PDF."""

from __future__ import annotations

import importlib
import re
import tempfile
from pathlib import Path
from typing import Protocol, cast

from career_os.config import ProjectPaths

START_HEADING = re.compile(r"(?im)^[ \t]{0,3}#{1,6}[ \t]*工作经历[ \t]*")
END_HEADING = re.compile(r"(?im)^[ \t]{0,3}#{1,6}[ \t]*(?:教育背景|教育经历)[ \t]*$")
MARKDOWN_HEADING = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+(.+?)\s*$")
LIST_ITEM = re.compile(r"^[ \t]*(?:[-*+]|•)[ \t]+(.+?)\s*$")
EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
CN_MOBILE = re.compile(r"(?<!\d)(?:\+?86[ \t-]*)?1[3-9](?:[ \t-]*\d){9}(?!\d)")
EXPORT_ID = re.compile(r"\b(?:AP|HC)-\d{8}-[A-Z0-9]{4,12}\b", re.IGNORECASE)
BOLD_MARKER = re.compile(r"(?<!\\)(?:\*\*|__)")
INLINE_LINK = re.compile(r"(?<!!)\[([^\]\n]+)\]\((?:\\.|[^)\n])*\)")
REFERENCE_LINK = re.compile(r"(?<!!)\[([^\]\n]+)\]\[[^\]\n]*\]")
AUTOLINK = re.compile(r"(?i)<(?:https?://|mailto:)[^>\n]+>")
BARE_URL = re.compile(r"(?i)\bhttps?://[^\s<>\])，。；！？,;]+")
LINK_DEFINITION = re.compile(r"(?im)^[ \t]{0,3}\[[^\]\n]+\]:[ \t]+\S+.*$")
LINK_MARKER = re.compile(r"(?i)(?:https?://|mailto:|(?<!!)\[[^\]\n]+\]\()")
FORBIDDEN_MARKERS = (
    "internal build",
    "do not share",
    "不构成投递授权",
    "猎头预览",
    "正式简历",
)


class MarkdownConverter(Protocol):
    def to_markdown(self, path: str, **options: object) -> object: ...


def resolve_input_path(paths: ProjectPaths, value: Path) -> Path:
    candidate = value.expanduser()
    path = (candidate if candidate.is_absolute() else paths.project_root / candidate).resolve()
    if not path.is_file():
        raise ValueError(f"input PDF does not exist: {path}")
    if path.suffix.casefold() != ".pdf":
        raise ValueError(f"input must be a PDF: {path}")
    return path


def resolve_output_path(paths: ProjectPaths, value: Path) -> Path:
    candidate = value.expanduser()
    path = (candidate if candidate.is_absolute() else paths.project_root / candidate).resolve()
    build_root = paths.build_root.resolve()
    share_root = (build_root / "share").resolve()
    if path == build_root or not path.is_relative_to(build_root):
        raise ValueError(
            f"temporary Markdown output must stay under the ignored build directory: {build_root}"
        )
    if path == share_root or path.is_relative_to(share_root):
        raise ValueError("temporary Markdown must not be placed in build/share")
    if path.suffix.casefold() != ".md":
        raise ValueError(f"output must use the .md extension: {path}")
    return path


def load_converter() -> MarkdownConverter:
    try:
        return cast(MarkdownConverter, importlib.import_module("pymupdf4llm"))
    except Exception as error:
        raise ValueError(
            "PyMuPDF4LLM is unavailable; from the repository root run `uv sync --locked`"
        ) from error


def pdf_to_markdown(path: Path, converter: MarkdownConverter | None = None) -> str:
    engine = load_converter() if converter is None else converter
    use_layout = getattr(engine, "use_layout", None)
    if callable(use_layout):
        use_layout(False)
    try:
        markdown = engine.to_markdown(
            str(path),
            ignore_images=True,
            ignore_graphics=True,
            margins=(0, 0, 0, 20),
            show_progress=False,
        )
    except Exception as error:
        raise ValueError(f"PyMuPDF4LLM could not convert {path}: {error}") from error
    if not isinstance(markdown, str) or not markdown.strip():
        raise ValueError(f"PyMuPDF4LLM returned no Markdown for {path}")
    return markdown.replace("\x00", "")


def join_soft_wrapped(lines: list[str]) -> str:
    parts = [part.strip() for part in lines if part.strip()]
    if not parts:
        return ""
    text = parts[0]
    for part in parts[1:]:
        left = text[-1]
        right = part[0]
        joiner = ""
        if not (
            ("\u3400" <= left <= "\u9fff" and "\u3400" <= right <= "\u9fff")
            or left in "，。；：、！？（([/"
            or right in "，。；：、！？）)]"
        ):
            joiner = " "
        text += joiner + part
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+([，。；：、！？,.;:!?）\]])", r"\1", text)
    text = re.sub(r"([（\[])\s+", r"\1", text)
    return text.strip()


def parse_blocks(section: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    current_kind = ""
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_kind, current_lines
        if current_lines:
            text = join_soft_wrapped(current_lines)
            if text:
                blocks.append((current_kind, text))
        current_kind = ""
        current_lines = []

    for raw_line in [*section.splitlines(), ""]:
        line = raw_line.strip()
        if not line:
            flush()
            continue
        heading = MARKDOWN_HEADING.match(line)
        if heading:
            flush()
            current_kind = "heading"
            current_lines = [heading.group(1)]
            continue
        item = LIST_ITEM.match(line)
        if item:
            flush()
            current_kind = "list"
            current_lines = [item.group(1)]
            continue
        if not current_lines:
            current_kind = "paragraph"
        current_lines.append(line)
    if blocks and blocks[0][0] == "paragraph":
        blocks[0] = ("heading", blocks[0][1])
    return blocks


def render_blocks(blocks: list[tuple[str, str]]) -> str:
    lines = ["# 工作经历", ""]
    previous_kind = ""
    list_number = 0

    def separate() -> None:
        if lines and lines[-1] != "":
            lines.append("")

    for kind, text in blocks:
        if kind == "list":
            if previous_kind != "list":
                separate()
                list_number = 1
            else:
                list_number += 1
            lines.append(f"{list_number}. {text}")
        elif kind == "heading":
            separate()
            lines.extend((f"## {text}", ""))
            list_number = 0
        else:
            separate()
            lines.extend((text, ""))
            list_number = 0
        previous_kind = kind
    return "\n".join(lines).rstrip() + "\n"


def strip_bold_markers(markdown: str) -> str:
    return BOLD_MARKER.sub("", markdown)


def strip_links(markdown: str) -> str:
    text = INLINE_LINK.sub(r"\1", markdown)
    text = REFERENCE_LINK.sub(r"\1", text)
    text = LINK_DEFINITION.sub("", text)
    text = AUTOLINK.sub("", text)
    return BARE_URL.sub("", text)


def extract_work_experience(markdown: str) -> str:
    starts = list(START_HEADING.finditer(markdown))
    if len(starts) != 1:
        raise ValueError(
            f"expected exactly one Markdown heading named 工作经历, found {len(starts)}"
        )
    start = starts[0]
    ends = [match for match in END_HEADING.finditer(markdown) if match.start() > start.end()]
    if len(ends) != 1:
        raise ValueError(
            "expected exactly one 教育背景/教育经历 heading after 工作经历, "
            f"found {len(ends)}"
        )
    section = markdown[start.end() : ends[0].start()].strip()
    blocks = parse_blocks(section)
    if not blocks:
        raise ValueError("工作经历 section is empty after PDF extraction")
    projection = strip_links(strip_bold_markers(render_blocks(blocks)))
    validate_projection(projection)
    return projection


def validate_projection(markdown: str) -> None:
    if not re.search(r"(?m)^##[ \t]+\S", markdown):
        raise ValueError("temporary Markdown contains no work-experience heading")
    if not re.search(r"(?m)^1\.[ \t]+\S", markdown):
        raise ValueError("temporary Markdown contains no work-experience result list")
    if BOLD_MARKER.search(markdown):
        raise ValueError("temporary Markdown contains a bold marker")
    if LINK_MARKER.search(markdown):
        raise ValueError("temporary Markdown contains a link target")
    folded = markdown.casefold()
    leaked = [marker for marker in FORBIDDEN_MARKERS if marker in folded]
    if leaked:
        raise ValueError(f"refusing output containing PDF watermark/footer text: {leaked[0]}")
    if EMAIL.search(markdown) or "mailto:" in folded:
        raise ValueError("refusing output containing an email address")
    if CN_MOBILE.search(markdown):
        raise ValueError("refusing output containing a Chinese mobile number")
    if EXPORT_ID.search(markdown):
        raise ValueError("refusing output containing a resume export identifier")


def publish_temporary_markdown(markdown: str, destination: Path) -> None:
    temporary: Path | None = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{destination.stem}-",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as handle:
            handle.write(markdown)
            temporary = Path(handle.name)
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_work_experience(
    paths: ProjectPaths,
    *,
    input_path: Path,
    output_path: Path,
) -> Path:
    source = resolve_input_path(paths, input_path)
    destination = resolve_output_path(paths, output_path)
    projection = extract_work_experience(pdf_to_markdown(source))
    publish_temporary_markdown(projection, destination)
    return destination
