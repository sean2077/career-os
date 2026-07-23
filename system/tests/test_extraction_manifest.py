from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = "docs/releases/v0.1.0-extraction.json"
SUPPLEMENT_PATH = "docs/releases/v0.1.0-mvp.json"


def test_public_extraction_manifest_is_complete_and_hash_bound() -> None:
    manifest = json.loads(
        REPOSITORY_ROOT.joinpath(MANIFEST_PATH).read_text(encoding="utf-8")
    )
    entries = manifest["entries"]
    by_path = {entry["path"]: entry for entry in entries}
    supplement = json.loads(
        REPOSITORY_ROOT.joinpath(SUPPLEMENT_PATH).read_text(encoding="utf-8")
    )
    supplement_entries = supplement["entries"]
    supplement_by_path = {entry["path"]: entry for entry in supplement_entries}

    assert len(by_path) == len(entries)
    assert len(supplement_by_path) == len(supplement_entries)
    assert MANIFEST_PATH not in by_path
    assert SUPPLEMENT_PATH not in supplement_by_path
    assert supplement == {
        "schema_version": 1,
        "release": "v0.1.0",
        "base_extraction_manifest": MANIFEST_PATH,
        "history_shape": "single-root-mvp",
        "self_exclusion": SUPPLEMENT_PATH,
        "entries": supplement_entries,
    }
    assert not [
        entry
        for entry in entries
        if any(
            entry["path"].startswith(prefix)
            for prefix in manifest["prohibited_roots"]
        )
    ]

    tracked = _tracked_public_paths(manifest["allowed_roots"])
    extraction_result_paths = {
        entry["path"] for entry in entries if entry["result_sha256"] is not None
    }
    current_paths = tracked - {MANIFEST_PATH, SUPPLEMENT_PATH}
    assert current_paths == extraction_result_paths | set(supplement_by_path)

    required_supplement = {
        path
        for path in current_paths
        if path not in by_path
        or by_path[path]["result_sha256"] != _sha256(_index_bytes(path))
    }
    assert set(supplement_by_path) == required_supplement

    for entry in entries:
        result = entry["result_sha256"]
        disposition = entry["disposition"]
        if disposition == "delete":
            assert result is None
            continue

        if entry["path"] not in supplement_by_path:
            assert result == _sha256(_index_bytes(entry["path"])), entry["path"]
        if disposition == "exact-copy":
            assert result == entry["source_sha256"]
        elif disposition == "retain-target":
            assert entry["source_sha256"] is None
            assert result == entry["target_sha256"]
        else:
            assert disposition == "public-adaptation"
            assert result != entry["source_sha256"]
            assert not (
                entry["source_sha256"] is None
                and entry["target_sha256"] is not None
                and result == entry["target_sha256"]
            )

    for entry in supplement_entries:
        assert set(entry) == {"path", "result_sha256", "reason"}
        assert entry["reason"] in {
            "downstream-adaptation",
            "mvp-security-hardening",
            "release-evidence",
        }
        assert entry["result_sha256"] == _sha256(_index_bytes(entry["path"]))

    assert manifest["source_snapshot"]["public_snapshot_sha256"] == _snapshot_digest(
        entries, "source_sha256"
    )
    assert manifest["target_baseline"]["public_snapshot_sha256"] == _snapshot_digest(
        entries, "target_sha256"
    )
    assert manifest["result_snapshot"]["public_snapshot_sha256"] == _snapshot_digest(
        entries, "result_sha256"
    )


def _tracked_public_paths(allowed_roots: list[str]) -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", *allowed_roots],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    )
    return {
        item
        for item in result.stdout.decode("utf-8").split("\0")
        if item
    }


def _index_bytes(relative: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f":{relative}"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    )
    return result.stdout


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _snapshot_digest(entries: list[dict[str, object]], field: str) -> str:
    digest = hashlib.sha256()
    for entry in entries:
        value = entry[field]
        if value is None:
            continue
        digest.update(str(entry["path"]).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(value).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()
