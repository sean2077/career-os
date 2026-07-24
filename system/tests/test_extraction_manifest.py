from __future__ import annotations

import hashlib
import json
import subprocess
import tomllib
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = "docs/releases/v0.1.0-extraction.json"
SUPPLEMENT_PATHS = (
    "docs/releases/v0.1.0-mvp.json",
    "docs/releases/v0.3.0-extraction.json",
    "docs/releases/v0.3.1-extraction.json",
)


def test_public_extraction_manifest_is_complete_and_hash_bound() -> None:
    config = tomllib.loads(
        REPOSITORY_ROOT.joinpath("career-os.toml").read_text(encoding="utf-8")
    )
    if config["development_topology"] != "standalone-framework":
        pytest.skip("public extraction manifest applies only to the public topology")

    manifest = json.loads(
        REPOSITORY_ROOT.joinpath(MANIFEST_PATH).read_text(encoding="utf-8")
    )
    entries = manifest["entries"]
    by_path = {entry["path"]: entry for entry in entries}
    supplements = [
        json.loads(REPOSITORY_ROOT.joinpath(path).read_text(encoding="utf-8"))
        for path in SUPPLEMENT_PATHS
    ]

    assert len(by_path) == len(entries)
    assert MANIFEST_PATH not in by_path
    assert supplements[0] == {
        "schema_version": 1,
        "release": "v0.1.0",
        "base_extraction_manifest": MANIFEST_PATH,
        "history_shape": "single-root-mvp",
        "self_exclusion": SUPPLEMENT_PATHS[0],
        "entries": supplements[0]["entries"],
    }
    assert supplements[1] == {
        "schema_version": 1,
        "release": "v0.3.0",
        "base_extraction_manifest": MANIFEST_PATH,
        "previous_supplement": SUPPLEMENT_PATHS[0],
        "history_shape": "home-roundtrip",
        "home_freeze": "15628ed54661b26d16fb083f5f8bc74ff5671017",
        "public_base": "d0bfb1fa5bf8e139b2ec5f9d2417a3344151da92",
        "self_exclusion": SUPPLEMENT_PATHS[1],
        "entries": supplements[1]["entries"],
    }
    assert supplements[2] == {
        "schema_version": 1,
        "release": "v0.3.1",
        "base_extraction_manifest": MANIFEST_PATH,
        "previous_supplement": SUPPLEMENT_PATHS[1],
        "history_shape": "release-roll-forward",
        "failed_tag": "v0.3.0",
        "public_base": "bc635b6ee28986b80772e93abd1ead8e8a80bfc3",
        "self_exclusion": SUPPLEMENT_PATHS[2],
        "entries": supplements[2]["entries"],
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
    effective = {
        entry["path"]: entry["result_sha256"]
        for entry in entries
        if entry["result_sha256"] is not None
    }
    latest_previous_effective: dict[str, str] | None = None
    latest_by_path: dict[str, dict[str, str | None]] = {}
    for index, (supplement_path, supplement) in enumerate(
        zip(SUPPLEMENT_PATHS, supplements, strict=True)
    ):
        supplement_entries = supplement["entries"]
        supplement_by_path = {
            entry["path"]: entry for entry in supplement_entries
        }
        assert len(supplement_by_path) == len(supplement_entries)
        assert supplement_path not in supplement_by_path
        previous_effective = dict(effective)
        for entry in supplement_entries:
            assert set(entry) == {"path", "result_sha256", "reason"}
            assert entry["reason"] in {
                "downstream-adaptation",
                "mvp-security-hardening",
                "release-evidence",
            }
            result = entry["result_sha256"]
            if result is None:
                effective.pop(entry["path"], None)
            else:
                assert len(result) == 64
                assert set(result) <= set("0123456789abcdef")
                effective[entry["path"]] = result
        if index == len(supplements) - 1:
            latest_previous_effective = previous_effective
            latest_by_path = supplement_by_path

    current_paths = tracked - {MANIFEST_PATH, *SUPPLEMENT_PATHS}
    assert set(effective) == current_paths
    for path in current_paths:
        assert effective[path] == _sha256(_index_bytes(path)), path

    assert latest_previous_effective is not None
    required_latest = {
        path
        for path in current_paths
        if latest_previous_effective.get(path) != _sha256(_index_bytes(path))
    } | (set(latest_previous_effective) - current_paths)
    assert set(latest_by_path) == required_latest

    for entry in entries:
        result = entry["result_sha256"]
        disposition = entry["disposition"]
        if disposition == "delete":
            assert result is None
            continue

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
