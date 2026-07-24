from __future__ import annotations

import hashlib
import json
import subprocess
import tomllib
from pathlib import Path

import pytest
from career_os.public_privacy import (
    POLICY_PATH,
    PublicPrivacyError,
    audit_public_repository,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _repository(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.name", "Synthetic Tester")
    _git(root, "config", "user.email", "tester@example.test")


def _write_policy(root: Path, approved: dict[str, list[str]]) -> None:
    path = root / POLICY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "approved_blob_sha256": approved,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _commit_all(root: Path, message: str) -> None:
    _git(root, "add", ".")
    _git(root, "commit", "-m", message)


def test_guarded_history_rejects_a_deleted_unapproved_resume_test_blob(
    tmp_path: Path,
) -> None:
    _repository(tmp_path)
    guarded = tmp_path / "system/tests/test_resume.py"
    guarded.parent.mkdir(parents=True)
    safe = b'def test_pdf_text():\n    assert "synthetic" == "synthetic"\n'
    guarded.write_bytes(safe)
    _write_policy(
        tmp_path,
        {"system/tests/test_resume.py": [_sha256(safe)]},
    )
    _commit_all(tmp_path, "test: add reviewed synthetic fixture")

    assert audit_public_repository(tmp_path, include_history=True).ok

    guarded.write_text(
        'def test_pdf_text():\n    assert "林虚构\\n云舟·北岸" != ""\n',
        encoding="utf-8",
        newline="\n",
    )
    _commit_all(tmp_path, "test: add unreviewed identity text")
    guarded.write_bytes(safe)
    _commit_all(tmp_path, "test: remove unreviewed identity text")

    report = audit_public_repository(tmp_path, include_history=True)

    assert not report.ok
    assert {finding.kind for finding in report.findings} == {
        "guarded-blob-unapproved"
    }
    assert all(finding.path == "system/tests/test_resume.py" for finding in report.findings)


def test_private_cross_comparison_catches_short_cjk_identity_and_locations(
    tmp_path: Path,
) -> None:
    public = tmp_path / "public"
    private = tmp_path / "private"
    _repository(public)
    _write_policy(public, {})
    public.joinpath("README.md").write_text(
        "Synthetic parser sample: 林虚构\nLocation variants: 云舟·北岸 / 北岸\n",
        encoding="utf-8",
        newline="\n",
    )
    _commit_all(public, "test: add accidental private literals")

    private.joinpath("career/profile").mkdir(parents=True)
    private.joinpath("career-os.toml").write_text(
        'schema_version = 2\n',
        encoding="utf-8",
        newline="\n",
    )
    private.joinpath("career/profile/profile.md").write_text(
        "full_name: 林虚构\nlocation: 云舟·北岸\ncity: 北岸\n",
        encoding="utf-8",
        newline="\n",
    )
    private.joinpath("career/profile/identity.tex").write_text(
        "\\newcommand{\\ResumeFullName}{林虚构}\n",
        encoding="utf-8",
        newline="\n",
    )

    report = audit_public_repository(
        public,
        include_history=True,
        private_root=private,
    )
    payload = json.dumps(report.as_dict(), ensure_ascii=False)

    assert not report.ok
    matches = [finding for finding in report.findings if finding.kind == "private-value-match"]
    assert len({finding.fingerprint for finding in matches}) == 3
    assert "林虚构" not in payload
    assert "云舟·北岸" not in payload
    assert "北岸" not in payload


def test_exact_public_seed_copy_does_not_become_a_private_candidate(
    tmp_path: Path,
) -> None:
    public = tmp_path / "public"
    private = tmp_path / "private"
    _repository(public)
    _write_policy(public, {})
    seed = public / "system/seeds/authorities/40-opportunity-decision.md"
    seed.parent.mkdir(parents=True)
    seed.write_text(
        "company: Synthetic Framework Collective\n",
        encoding="utf-8",
        newline="\n",
    )
    _commit_all(public, "test: add public framework seed")

    private.joinpath("career/40-opportunity-decision").mkdir(parents=True)
    private.joinpath("career-os.toml").write_text(
        'schema_version = 2\n',
        encoding="utf-8",
        newline="\n",
    )
    private.joinpath("career/40-opportunity-decision/README.md").write_bytes(
        seed.read_bytes()
    )

    report = audit_public_repository(
        public,
        include_history=True,
        private_root=private,
    )

    assert report.ok
    assert report.private_candidate_count == 0


def test_obvious_public_patterns_fail_without_echoing_values(tmp_path: Path) -> None:
    _repository(tmp_path)
    _write_policy(tmp_path, {})
    tmp_path.joinpath("README.md").write_text(
        "path=C:\\Users\\actualperson\\career-home\n"
        "contact=person@company.dev\n"
        "token=ghp_123456789012345678901234567890\n",
        encoding="utf-8",
        newline="\n",
    )
    _commit_all(tmp_path, "test: add unsafe public text")

    report = audit_public_repository(tmp_path)
    payload = json.dumps(report.as_dict())

    assert not report.ok
    assert {finding.kind for finding in report.findings} == {
        "absolute-windows-user-path",
        "credential-token",
        "non-fixture-email",
    }
    assert "actualperson" not in payload
    assert "person@company.dev" not in payload
    assert "ghp_" not in payload


def test_public_history_audit_requires_clean_complete_git_state(tmp_path: Path) -> None:
    _repository(tmp_path)
    _write_policy(tmp_path, {})
    _commit_all(tmp_path, "test: initialize policy")
    tmp_path.joinpath("dirty.txt").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(PublicPrivacyError, match="clean worktree"):
        audit_public_repository(tmp_path, include_history=True)

    with pytest.raises(PublicPrivacyError, match="cannot resolve ref"):
        audit_public_repository(tmp_path, include_history=True, ref="missing")


def test_public_privacy_policy_fails_closed_on_invalid_entries(tmp_path: Path) -> None:
    _repository(tmp_path)
    _write_policy(tmp_path, {"README.md": ["not-a-hash"]})
    _commit_all(tmp_path, "test: add invalid policy")

    with pytest.raises(PublicPrivacyError, match="unguarded path"):
        audit_public_repository(tmp_path)


def test_repository_snapshot_matches_public_fixture_policy() -> None:
    config = tomllib.loads(
        REPOSITORY_ROOT.joinpath("career-os.toml").read_text(encoding="utf-8")
    )
    if config["development_topology"] != "standalone-framework":
        pytest.skip("repository snapshot privacy audit applies only to the public topology")

    report = audit_public_repository(REPOSITORY_ROOT)

    assert report.ok, report.as_dict()
