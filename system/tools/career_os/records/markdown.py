from __future__ import annotations

import re

_LEVEL_TWO_HEADING = re.compile(r"^##[ \t]+(.+?)[ \t]*$")


def extract_markdown_section(body: str, heading: str) -> str:
    """Return one level-two Markdown section body with stable boundary whitespace."""

    lines = body.splitlines(keepends=True)
    matches = [
        index
        for index, line in enumerate(lines)
        if (match := _LEVEL_TWO_HEADING.fullmatch(line.rstrip("\r\n")))
        and match.group(1) == heading
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one level-two Markdown heading {heading!r}, "
            f"found {len(matches)}"
        )
    start = matches[0] + 1
    end = next(
        (
            index
            for index in range(start, len(lines))
            if _LEVEL_TWO_HEADING.fullmatch(lines[index].rstrip("\r\n"))
        ),
        len(lines),
    )
    section = "".join(lines[start:end]).strip("\r\n")
    if not section.strip():
        raise ValueError(f"Markdown section {heading!r} must not be empty")
    return section + "\n"
