from __future__ import annotations

import os
import re
import tempfile
from contextlib import suppress
from datetime import date
from pathlib import Path

_CANONICAL_HEADING = re.compile(r"^ — (?P<date>\d{4}-\d{2}-\d{2})[ \t]*$")
_LEVEL_TWO_HEADING = re.compile(r"^##(?:[ \t]+|$)")
_FENCE_OPEN = re.compile(r"^[ ]{0,3}(?P<fence>`{3,}|~{3,})(?P<info>.*)$")


class ReleaseNotesError(ValueError):
    """The changelog does not satisfy the release-note extraction contract."""


LineRecord = tuple[int, int, str, bool]


def _scan_lines(text: str) -> list[LineRecord]:
    records: list[LineRecord] = []
    offset = 0
    fence_character: str | None = None
    fence_size = 0

    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        outside_fence = fence_character is None
        records.append((offset, offset + len(raw_line), line, outside_fence))

        if fence_character is None:
            match = _FENCE_OPEN.match(line)
            if match:
                marker = match.group("fence")
                info = match.group("info")
                if marker[0] == "`" and "`" in info:
                    offset += len(raw_line)
                    continue
                fence_character = marker[0]
                fence_size = len(marker)
        else:
            closing_fence = re.fullmatch(
                rf"^[ ]{{0,3}}{re.escape(fence_character)}{{{fence_size},}}[ \t]*$",
                line,
            )
            if closing_fence:
                fence_character = None
                fence_size = 0
        offset += len(raw_line)

    return records


def extract_release_notes(text: str, exact_tag: str) -> str:
    """Extract one exact, non-empty release section without its heading."""

    if not exact_tag or any(character in exact_tag for character in ("\x00", "\r", "\n")):
        raise ReleaseNotesError("the exact tag must be one non-empty line without NUL")

    records = _scan_lines(text)
    target_prefix = f"## [{exact_tag}]"
    matches = [
        (index, record)
        for index, record in enumerate(records)
        if record[3] and record[2].startswith(target_prefix)
    ]
    if not matches:
        raise ReleaseNotesError(f"no level-two changelog heading matches {exact_tag!r}")
    if len(matches) != 1:
        raise ReleaseNotesError(f"multiple changelog headings match {exact_tag!r}")

    target_index, (_, body_start, heading, _) = matches[0]
    canonical = _CANONICAL_HEADING.fullmatch(heading[len(target_prefix) :])
    if canonical is None:
        raise ReleaseNotesError(
            f"heading for {exact_tag!r} must be '## [{exact_tag}] — YYYY-MM-DD'"
        )
    try:
        date.fromisoformat(canonical.group("date"))
    except ValueError as error:
        raise ReleaseNotesError(
            f"heading for {exact_tag!r} has an invalid calendar date"
        ) from error

    body_end = len(text)
    for start, _, line, outside_fence in records[target_index + 1 :]:
        if outside_fence and _LEVEL_TWO_HEADING.match(line):
            body_end = start
            break

    body = text[body_start:body_end].strip()
    if not body:
        raise ReleaseNotesError(f"changelog section for {exact_tag!r} is empty")
    return body + "\n"


def write_release_notes(changelog: Path, exact_tag: str, output: Path) -> None:
    """Validate completely, then atomically replace the requested notes file."""

    if changelog.resolve() == output.resolve():
        raise ReleaseNotesError("the notes output must not overwrite the changelog")
    if not output.parent.is_dir():
        raise ReleaseNotesError(f"notes output directory does not exist: {output.parent}")

    try:
        text = changelog.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise ReleaseNotesError(f"cannot read changelog {changelog}: {error}") from error

    notes = extract_release_notes(text, exact_tag)
    temporary_name: str | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=str(output.parent),
            prefix=f".{output.name}.",
            suffix=".tmp",
            text=True,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(notes)
        os.replace(temporary_name, output)
        temporary_name = None
    except OSError as error:
        raise ReleaseNotesError(f"cannot write release notes {output}: {error}") from error
    finally:
        if temporary_name is not None:
            with suppress(FileNotFoundError):
                Path(temporary_name).unlink()
