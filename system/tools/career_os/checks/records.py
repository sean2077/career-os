from __future__ import annotations

import subprocess
from pathlib import Path

from pydantic import ValidationError
from ruamel.yaml.error import YAMLError

from career_os.checks._contracts import _yaml
from career_os.checks._issue import CheckIssue, _issue_detail
from career_os.config import ProjectPaths
from career_os.records import (
    ParsedRecord,
    load_record,
    split_frontmatter,
    validate_record_envelope,
    validate_record_transition,
)
from career_os.records.models import authority_directory
from career_os.records.semantics import check_record_semantics


def _check_records(paths: ProjectPaths) -> tuple[list[ParsedRecord], list[CheckIssue]]:
    records: list[ParsedRecord] = []
    issues: list[CheckIssue] = []
    if not paths.data_root.exists():
        return records, [
            CheckIssue("records.data-root", "pass", str(paths.data_root), "not initialized")
        ]
    for path in sorted(paths.data_root.rglob("*.md")):
        if path.name == "README.md" or "_templates" in path.parts:
            continue
        try:
            record = load_record(path)
            expected = authority_directory(record.envelope.kind)
            relative = path.relative_to(paths.data_root)
            if not relative.parts or relative.parts[0] != expected:
                raise ValueError(f"{record.envelope.kind} belongs under {expected}")
            records.append(record)
            issues.append(CheckIssue("records.envelope", "pass", str(path), "valid"))
        except (OSError, ValueError, ValidationError) as error:
            issues.append(CheckIssue("records.envelope", "fail", str(path), _issue_detail(error)))
    return records, issues


def _head_blobs(project_root: Path, wanted: set[str], scope: str) -> dict[str, str]:
    """Read the HEAD text of every wanted path under one scope in two Git calls.

    Records are compared against HEAD one by one, so a per-record `git show`
    costs one process per record. Listing the scope and streaming the blobs
    keeps that at two processes for the whole data root.
    """
    listing = subprocess.run(
        ["git", "-C", str(project_root), "ls-tree", "-r", "-z", "HEAD", "--", scope],
        check=False,
        capture_output=True,
    )
    if listing.returncode != 0:
        return {}
    by_sha: dict[str, list[str]] = {}
    for entry in listing.stdout.split(b"\0"):
        if not entry:
            continue
        info, _tab, raw_path = entry.partition(b"\t")
        fields = info.split(b" ")
        if len(fields) != 3 or fields[1] != b"blob":
            continue
        relative = raw_path.decode("utf-8", errors="replace")
        if relative in wanted:
            by_sha.setdefault(fields[2].decode("ascii"), []).append(relative)
    if not by_sha:
        return {}
    contents = subprocess.run(
        ["git", "-C", str(project_root), "cat-file", "--batch"],
        input="".join(f"{sha}\n" for sha in by_sha).encode("ascii"),
        check=False,
        capture_output=True,
    )
    if contents.returncode != 0:
        return {}
    blobs: dict[str, str] = {}
    stream = contents.stdout
    offset = 0
    for sha in by_sha:
        end = stream.find(b"\n", offset)
        if end < 0:
            break
        header = stream[offset:end].split(b" ")
        offset = end + 1
        if len(header) != 3 or header[1] != b"blob" or not header[2].isdigit():
            continue
        length = int(header[2])
        text = stream[offset : offset + length].decode("utf-8", errors="replace")
        offset += length + 1
        for relative in by_sha[sha]:
            blobs[relative] = text
    return blobs


def _check_record_transitions(
    paths: ProjectPaths, records: list[ParsedRecord]
) -> list[CheckIssue]:
    issues: list[CheckIssue] = []
    project_root = paths.project_root.resolve()
    relatives = {
        record.path: record.path.resolve().relative_to(project_root).as_posix()
        for record in records
    }
    head_texts = _head_blobs(
        paths.project_root,
        set(relatives.values()),
        paths.data_root.resolve().relative_to(project_root).as_posix(),
    )
    for record in records:
        committed = head_texts.get(relatives[record.path])
        previous = None
        if committed is not None:
            try:
                frontmatter, _body = split_frontmatter(committed)
                raw = _yaml.load(frontmatter)
                if isinstance(raw, dict) and raw.get("schema_version") == 3:
                    previous = validate_record_envelope(raw)
            except (ValueError, ValidationError, YAMLError):
                previous = None
        try:
            if committed is None or previous is not None:
                validate_record_transition(previous, record.envelope)
            issues.append(
                CheckIssue(
                    "records.lifecycle",
                    "pass",
                    str(record.path),
                    "status matches its Git-relative lifecycle contract",
                )
            )
        except ValueError as error:
            issues.append(
                CheckIssue("records.lifecycle", "fail", str(record.path), str(error))
            )
    return issues


def _check_record_semantics(
    paths: ProjectPaths, records: list[ParsedRecord]
) -> list[CheckIssue]:
    return [
        CheckIssue("records.semantic", issue.status, str(issue.path), issue.detail)
        for issue in check_record_semantics(records, paths)
    ]
