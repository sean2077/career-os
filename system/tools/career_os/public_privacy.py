from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import subprocess
import tomllib
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

POLICY_PATH = Path("system/privacy/public-fixture-policy.json")
GUARDED_PATTERNS = (
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    "system/resume/fixtures/**/*.tex",
    "system/resume/templates/*.tex",
    "system/resume/templates/**/*.tex",
    "system/tests/test_public_privacy.py",
    "system/tests/test_resume*.py",
    "system/tools/career_os/cli/release.py",
    "system/tools/career_os/public_privacy.py",
)
EXCLUDED_PRIVATE_PARTS = {
    ".career-os",
    ".git",
    ".obsidian",
    ".venv",
    "build",
    "node_modules",
    "runtime",
    "system",
}

_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_EMAIL_RE = re.compile(
    r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
    re.IGNORECASE,
)
_PHONE_RE = re.compile(
    r"(?:phone|mobile|tel(?:ephone)?|电话|手机)\s*[:=]\s*[\"']?"
    r"([+()\d][\d\s().-]{6,30})",
    re.IGNORECASE | re.MULTILINE,
)
_LABELED_VALUE_RE = re.compile(
    r"^\s*(?:[-*]\s*)?"
    r"(full[_ -]?name|legal[_ -]?name|display[_ -]?name|person[_ -]?name|姓名|"
    r"company|employer|organization|client|公司|雇主|组织|客户|project|项目|"
    r"location|city|地点|城市)\s*[:=]\s*[\"']?([^\n\r\"']{2,180})",
    re.IGNORECASE | re.MULTILINE,
)
_PROFILE_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:github\.com|linkedin\.com|linktr\.ee|about\.me)/"
    r"[^\s<>\"')]+",
    re.IGNORECASE,
)
_TEX_IDENTITY_RE = re.compile(
    r"\\(?:newcommand|def)\s*\{?\\[^}\s]*"
    r"(name|email|phone|mobile|linkedin|github|website)[^}\s]*\}?\s*"
    r"\{([^}\n]{2,180})\}",
    re.IGNORECASE,
)
_PUBLIC_GITHUB_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/sean2077"
    r"(?:/(?:career-os|skills)(?:\.git)?)?/?$",
    re.IGNORECASE,
)
_WINDOWS_USER_PATH_RE = re.compile(
    rb"(?i)\b[A-Z]:[\\/]+Users[\\/]+"
    rb"(?!(?:example|runneradmin|user|username)(?:[\\/]|\\b))[^\\/\s]+"
)
_POSIX_HOME_PATH_RE = re.compile(
    rb"(?i)/home/(?!(?:example|runner|user|username)(?:/|\\b))[^/\s]+"
)
_PRIVATE_KEY_RE = re.compile(rb"BEGIN [A-Z ]*PRIVATE KEY", re.IGNORECASE)
_TOKEN_RE = re.compile(
    rb"(?:gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|"
    rb"AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,})"
)


class PublicPrivacyError(ValueError):
    pass


@dataclass(frozen=True)
class PrivacyFinding:
    kind: str
    path: str | None
    fingerprint: str | None
    categories: tuple[str, ...] = ()
    object_id: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "path": self.path,
            "fingerprint": self.fingerprint,
            "categories": list(self.categories),
            "object_id": self.object_id,
        }


@dataclass(frozen=True)
class PrivacyReport:
    ref: str
    history_scanned: bool
    private_root_scanned: bool
    private_candidate_count: int
    guarded_blob_count: int
    scanned_blob_count: int
    findings: tuple[PrivacyFinding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "ref": self.ref,
            "history_scanned": self.history_scanned,
            "private_root_scanned": self.private_root_scanned,
            "private_candidate_count": self.private_candidate_count,
            "guarded_blob_count": self.guarded_blob_count,
            "scanned_blob_count": self.scanned_blob_count,
            "findings": [finding.as_dict() for finding in self.findings],
        }


def audit_public_repository(
    project_root: Path,
    *,
    ref: str = "HEAD",
    include_history: bool = False,
    private_root: Path | None = None,
) -> PrivacyReport:
    project_root = project_root.resolve()
    _require_git_repository(project_root)
    policy = _load_policy(project_root)
    current_files = _current_tracked_files(project_root)
    findings: list[PrivacyFinding] = []

    if include_history:
        _require_complete_clean_history(project_root, ref)

    guarded_findings, guarded_blob_count = _audit_guarded_blobs(
        project_root,
        current_files,
        policy,
        ref=ref,
        include_history=include_history,
    )
    findings.extend(guarded_findings)

    blobs: list[tuple[str, bytes, str | None]]
    if include_history:
        blobs = _history_blobs(project_root, ref)
    else:
        blobs = [(path, data, None) for path, data in current_files.items()]
    findings.extend(_audit_obvious_public_patterns(blobs))

    candidates: dict[str, set[str]] = {}
    if private_root is not None:
        candidates = _private_candidates(
            private_root.resolve(),
            public_file_hashes={_sha256(data) for data in current_files.values()},
        )
        findings.extend(_match_private_candidates(blobs, candidates))

    return PrivacyReport(
        ref=ref,
        history_scanned=include_history,
        private_root_scanned=private_root is not None,
        private_candidate_count=len(candidates),
        guarded_blob_count=guarded_blob_count,
        scanned_blob_count=len(blobs),
        findings=tuple(_deduplicate_findings(findings)),
    )


def _load_policy(project_root: Path) -> dict[str, frozenset[str]]:
    path = project_root / POLICY_PATH
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PublicPrivacyError(f"invalid public privacy policy: {error}") from error
    if not isinstance(raw, dict) or set(raw) != {"schema_version", "approved_blob_sha256"}:
        raise PublicPrivacyError("public privacy policy has invalid top-level keys")
    if raw["schema_version"] != 1 or not isinstance(raw["approved_blob_sha256"], dict):
        raise PublicPrivacyError("public privacy policy has invalid schema")

    approved: dict[str, frozenset[str]] = {}
    for raw_path, raw_hashes in raw["approved_blob_sha256"].items():
        if not isinstance(raw_path, str) or not _is_guarded_path(raw_path):
            raise PublicPrivacyError("public privacy policy contains an unguarded path")
        if (
            not isinstance(raw_hashes, list)
            or not raw_hashes
            or not all(isinstance(item, str) and _SHA256_RE.fullmatch(item) for item in raw_hashes)
            or len(raw_hashes) != len(set(raw_hashes))
        ):
            raise PublicPrivacyError(
                f"public privacy policy has invalid hashes for {raw_path}"
            )
        approved[raw_path] = frozenset(raw_hashes)
    return approved


def _audit_guarded_blobs(
    project_root: Path,
    current_files: dict[str, bytes],
    policy: dict[str, frozenset[str]],
    *,
    ref: str,
    include_history: bool,
) -> tuple[list[PrivacyFinding], int]:
    findings: list[PrivacyFinding] = []
    seen: set[tuple[str, str]] = set()

    def inspect(path: str, data: bytes, object_id: str | None) -> None:
        digest = _sha256(data)
        key = (path, digest)
        if key in seen:
            return
        seen.add(key)
        approved = policy.get(path)
        if approved is None:
            findings.append(
                PrivacyFinding(
                    kind="guarded-path-unapproved",
                    path=path,
                    fingerprint=f"sha256:{digest}",
                    object_id=object_id,
                )
            )
        elif digest not in approved:
            findings.append(
                PrivacyFinding(
                    kind="guarded-blob-unapproved",
                    path=path,
                    fingerprint=f"sha256:{digest}",
                    object_id=object_id,
                )
            )

    for path, data in current_files.items():
        if _is_guarded_path(path):
            inspect(path, data, None)

    if include_history:
        historical_paths = _historical_paths(project_root, ref)
        for path in sorted(item for item in historical_paths if _is_guarded_path(item)):
            commits = _git_lines(project_root, "log", "--format=%H", ref, "--", path)
            for commit in commits:
                object_id = _git_optional_text(project_root, "rev-parse", f"{commit}:{path}")
                if object_id is None:
                    continue
                inspect(path, _git_bytes(project_root, "cat-file", "blob", object_id), object_id)

    return findings, len(seen)


def _audit_obvious_public_patterns(
    blobs: list[tuple[str, bytes, str | None]],
) -> list[PrivacyFinding]:
    findings: list[PrivacyFinding] = []
    for path, data, object_id in blobs:
        if _is_guarded_path(path):
            continue
        fingerprint = f"sha256:{_sha256(data)}"
        for kind, pattern in (
            ("absolute-windows-user-path", _WINDOWS_USER_PATH_RE),
            ("absolute-posix-home-path", _POSIX_HOME_PATH_RE),
            ("private-key-material", _PRIVATE_KEY_RE),
            ("credential-token", _TOKEN_RE),
        ):
            if pattern.search(data):
                findings.append(
                    PrivacyFinding(
                        kind=kind,
                        path=path,
                        fingerprint=fingerprint,
                        object_id=object_id,
                    )
                )
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if any(not _allowed_public_email(email) for email in _EMAIL_RE.findall(text)):
            findings.append(
                PrivacyFinding(
                    kind="non-fixture-email",
                    path=path,
                    fingerprint=fingerprint,
                    object_id=object_id,
                )
            )
    return findings


def _private_candidates(
    private_root: Path,
    *,
    public_file_hashes: set[str],
) -> dict[str, set[str]]:
    config_path = private_root / "career-os.toml"
    try:
        tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise PublicPrivacyError(f"private root has invalid career-os.toml: {error}") from error

    data_root = (private_root / "career").resolve()
    if not data_root.is_relative_to(private_root) or not data_root.is_dir():
        raise PublicPrivacyError("private data_root is missing or escapes the private root")

    result: dict[str, set[str]] = {}
    for path in sorted(item for item in data_root.rglob("*") if item.is_file()):
        relative_parts = {part.lower() for part in path.relative_to(private_root).parts}
        if relative_parts & EXCLUDED_PRIVATE_PARTS:
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if _sha256(data) in public_file_hashes or len(data) > 2_000_000:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for value in _EMAIL_RE.findall(text):
            _add_private_candidate(result, "email", value)
        for value in _PHONE_RE.findall(text):
            _add_private_candidate(result, "phone", value)
        for key, value in _LABELED_VALUE_RE.findall(text):
            _add_private_candidate(result, key.lower().replace(" ", "_"), value)
        for value in _PROFILE_URL_RE.findall(text):
            _add_private_candidate(result, "profile_url", value)
        for key, value in _TEX_IDENTITY_RE.findall(text):
            _add_private_candidate(result, f"identity_{key.lower()}", value)
    return result


def _add_private_candidate(
    result: dict[str, set[str]],
    category: str,
    raw_value: str,
) -> None:
    value = raw_value.strip().strip("`[](){}.,; ")
    has_cjk = bool(re.search(r"[\u3400-\u9fff]", value))
    if len(value) < (2 if has_cjk else 4):
        return
    if "->" in value:
        return
    if _allowed_public_email(value) or _PUBLIC_GITHUB_RE.fullmatch(value):
        return
    digits = "".join(re.findall(r"\d", value))
    if "phone" in category and len(digits) >= 7 and digits.endswith("0" * 7):
        return
    result.setdefault(value, set()).add(category)


def _match_private_candidates(
    blobs: list[tuple[str, bytes, str | None]],
    candidates: dict[str, set[str]],
) -> list[PrivacyFinding]:
    findings: list[PrivacyFinding] = []
    encoded = {
        value: value.encode("utf-8")
        for value in candidates
    }
    for path, data, object_id in blobs:
        for value, needle in encoded.items():
            if needle not in data:
                continue
            findings.append(
                PrivacyFinding(
                    kind="private-value-match",
                    path=path,
                    fingerprint=f"sha256:{_sha256(needle)}",
                    categories=tuple(sorted(candidates[value])),
                    object_id=object_id,
                )
            )
    return findings


def _current_tracked_files(project_root: Path) -> dict[str, bytes]:
    raw = _git_bytes(project_root, "ls-files", "-z")
    result: dict[str, bytes] = {}
    for item in raw.decode("utf-8").split("\0"):
        if not item:
            continue
        path = project_root / item
        try:
            if path.is_symlink():
                result[item] = os.readlink(path).encode("utf-8")
            else:
                result[item] = path.read_bytes()
        except OSError as error:
            raise PublicPrivacyError(f"cannot read tracked path {item}: {error}") from error
    return result


def _history_blobs(project_root: Path, ref: str) -> list[tuple[str, bytes, str | None]]:
    object_paths: dict[str, str] = {}
    for line in _git_lines(project_root, "rev-list", "--objects", ref):
        object_id, separator, path = line.partition(" ")
        if separator:
            object_paths.setdefault(object_id, path)
    blob_ids = [
        object_id
        for object_id in object_paths
        if _git_text(project_root, "cat-file", "-t", object_id) == "blob"
    ]
    contents = _cat_file_batch(project_root, blob_ids)
    return [
        (object_paths[object_id], contents[object_id], object_id)
        for object_id in blob_ids
    ]


def _cat_file_batch(project_root: Path, object_ids: list[str]) -> dict[str, bytes]:
    if not object_ids:
        return {}
    try:
        completed = subprocess.run(
            ["git", "-C", str(project_root), "cat-file", "--batch"],
            input=("\n".join(object_ids) + "\n").encode("ascii"),
            capture_output=True,
            check=False,
        )
    except OSError as error:
        raise PublicPrivacyError("cannot start git cat-file") from error
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", "replace").strip()
        raise PublicPrivacyError(f"git cat-file failed: {stderr}")

    stream = BytesIO(completed.stdout)
    result: dict[str, bytes] = {}
    for expected in object_ids:
        header = stream.readline().decode("ascii").strip()
        parts = header.split()
        if len(parts) != 3 or parts[0] != expected or parts[1] != "blob":
            raise PublicPrivacyError(f"cannot read Git blob {expected}")
        size = int(parts[2])
        result[expected] = stream.read(size)
        if stream.read(1) != b"\n":
            raise PublicPrivacyError(f"malformed Git blob stream for {expected}")
    return result


def _historical_paths(project_root: Path, ref: str) -> set[str]:
    return {
        line
        for line in _git_lines(project_root, "log", "--format=", "--name-only", ref)
        if line
    }


def _require_git_repository(project_root: Path) -> None:
    if _git_optional_text(project_root, "rev-parse", "--show-toplevel") is None:
        raise PublicPrivacyError("public privacy audit requires a Git repository")


def _require_complete_clean_history(project_root: Path, ref: str) -> None:
    if _git_optional_text(project_root, "rev-parse", "--verify", f"{ref}^{{commit}}") is None:
        raise PublicPrivacyError(f"public privacy audit cannot resolve ref {ref!r}")
    if _git_text(project_root, "rev-parse", "--is-shallow-repository") == "true":
        raise PublicPrivacyError("public privacy history audit rejects shallow repositories")
    if _git_bytes(project_root, "status", "--porcelain=v1").strip():
        raise PublicPrivacyError("public privacy history audit requires a clean worktree and index")


def _allowed_public_email(value: str) -> bool:
    if value.lower() == "git@github.com":
        return True
    if "@" not in value:
        return False
    domain = value.rsplit("@", 1)[1].lower()
    return (
        domain in {"example.com", "example.net", "example.org", "example.test"}
        or domain.endswith((".example", ".invalid", ".localhost", ".test"))
        or domain == "users.noreply.github.com"
    )


def _is_guarded_path(path: str) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in GUARDED_PATTERNS)


def _deduplicate_findings(findings: list[PrivacyFinding]) -> list[PrivacyFinding]:
    result: list[PrivacyFinding] = []
    seen: set[tuple[object, ...]] = set()
    for finding in sorted(
        findings,
        key=lambda item: (
            item.kind,
            item.path or "",
            item.fingerprint or "",
            item.object_id or "",
            item.categories,
        ),
    ):
        key = (
            finding.kind,
            finding.path,
            finding.fingerprint,
            finding.categories,
            finding.object_id,
        )
        if key not in seen:
            seen.add(key)
            result.append(finding)
    return result


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _git_lines(project_root: Path, *args: str) -> list[str]:
    output = _git_text(project_root, *args)
    return [line for line in output.splitlines() if line]


def _git_text(project_root: Path, *args: str) -> str:
    return _git_bytes(project_root, *args).decode("utf-8").strip()


def _git_optional_text(project_root: Path, *args: str) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(project_root), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def _git_bytes(project_root: Path, *args: str) -> bytes:
    try:
        return subprocess.run(
            ["git", "-C", str(project_root), *args],
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise PublicPrivacyError(f"git {' '.join(args)} failed") from error
