from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from career_os.records.models import RecordEnvelope, validate_record_envelope

_yaml = YAML(typ="safe")


@dataclass(frozen=True)
class ParsedRecord:
    path: Path
    envelope: RecordEnvelope
    body: str
    raw_frontmatter: dict[str, Any]


def load_record(path: Path) -> ParsedRecord:
    text = path.read_text(encoding="utf-8-sig")
    frontmatter, body = split_frontmatter(text)
    loaded = _yaml.load(frontmatter)
    if not isinstance(loaded, dict):
        raise ValueError("frontmatter must be a YAML mapping")
    return ParsedRecord(
        path=path,
        envelope=validate_record_envelope(loaded),
        body=body,
        raw_frontmatter=dict(loaded),
    )


def split_frontmatter(text: str) -> tuple[str, str]:
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        raise ValueError("record must begin with YAML frontmatter")
    end = normalized.find("\n---\n", 4)
    if end < 0:
        raise ValueError("record frontmatter is not terminated")
    return normalized[4:end], normalized[end + 5 :]
