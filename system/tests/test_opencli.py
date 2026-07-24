from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from career_os.config import ProjectConfig
from career_os.opencli import opencli_doctor_checks


def _config(sources: dict[str, list[str]]) -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "schema_version": 2,
            "system_version": "0.1.0",
            "research": {
                "opencli": {
                    "enabled": True,
                    "profile": "career-research",
                    "timeout_seconds": 60,
                    "capture_subdir": "research/opencli",
                    "sources": sources,
                }
            },
        }
    )


class _Connection:
    def close(self) -> None:
        return None


def test_opencli_doctor_checks_live_read_only_registry_without_running_workflows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invocations: list[list[str]] = []
    registry = [
        {"site": "weixin", "name": "search", "access": "read"},
        {"site": "xiaohongshu", "name": "note", "access": "read"},
        {"site": "xiaohongshu", "name": "publish", "access": "write"},
    ]

    monkeypatch.setattr(
        "career_os.opencli.shutil.which", lambda name: f"C:/tools/{name}.exe"
    )

    def fake_run(
        arguments: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        invocations.append(arguments)
        if arguments[0].endswith("node.exe"):
            return subprocess.CompletedProcess(arguments, 0, stdout="v20.18.0\n", stderr="")
        if arguments[1:] == ["--version"]:
            return subprocess.CompletedProcess(arguments, 0, stdout="1.8.6\n", stderr="")
        return subprocess.CompletedProcess(
            arguments, 0, stdout=json.dumps(registry), stderr=""
        )

    monkeypatch.setattr("career_os.opencli.subprocess.run", fake_run)
    monkeypatch.setattr(
        "career_os.opencli.socket.create_connection",
        lambda *_args, **_kwargs: _Connection(),
    )

    checks = opencli_doctor_checks(
        tmp_path,
        _config({"weixin": ["search"], "xiaohongshu": ["note"]}),
    )

    by_id = {item["id"]: item for item in checks}
    assert by_id["command.node"]["status"] == "pass"
    assert by_id["command.opencli"]["status"] == "pass"
    assert by_id["research.opencli-registry"]["status"] == "pass"
    assert by_id["research.opencli-bridge"]["status"] == "pass"
    assert [item[1:] for item in invocations] == [
        ["--version"],
        ["--version"],
        ["list", "-f", "json"],
    ]


def test_opencli_doctor_fails_closed_for_missing_or_write_registry_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = [{"site": "weixin", "name": "search", "access": "write"}]
    monkeypatch.setattr(
        "career_os.opencli.shutil.which", lambda name: f"C:/tools/{name}.exe"
    )

    def fake_run(
        arguments: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if arguments[0].endswith("node.exe"):
            return subprocess.CompletedProcess(arguments, 0, stdout="v20.18.0\n", stderr="")
        if arguments[1:] == ["--version"]:
            return subprocess.CompletedProcess(arguments, 0, stdout="1.8.6\n", stderr="")
        return subprocess.CompletedProcess(
            arguments, 0, stdout=json.dumps(registry), stderr=""
        )

    monkeypatch.setattr("career_os.opencli.subprocess.run", fake_run)
    monkeypatch.setattr(
        "career_os.opencli.socket.create_connection",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("not listening")),
    )

    checks = opencli_doctor_checks(
        tmp_path,
        _config({"weixin": ["search", "download"]}),
    )

    registry_check = next(
        item for item in checks if item["id"] == "research.opencli-registry"
    )
    assert registry_check["status"] == "fail"
    assert "missing: weixin/download" in str(registry_check["detail"])
    assert "not read-only: weixin/search (write)" in str(registry_check["detail"])
    bridge = next(item for item in checks if item["id"] == "research.opencli-bridge")
    assert bridge["status"] == "attention"


def test_opencli_doctor_keeps_missing_optional_runtime_nonfatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("career_os.opencli.shutil.which", lambda _name: None)
    monkeypatch.setattr(
        "career_os.opencli.socket.create_connection",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("not listening")),
    )

    checks = opencli_doctor_checks(tmp_path, _config({"weixin": ["search"]}))

    assert not any(item["status"] == "fail" for item in checks)
    assert {
        item["id"] for item in checks if item["status"] == "attention"
    } == {
        "command.node",
        "command.opencli",
        "research.opencli-registry",
        "research.opencli-bridge",
    }


def test_opencli_doctor_does_nothing_when_capability_is_disabled(tmp_path: Path) -> None:
    checks = opencli_doctor_checks(
        tmp_path,
        ProjectConfig(schema_version=2, system_version="0.1.0"),
    )

    assert checks == [
        {
            "id": "research.opencli-config",
            "status": "pass",
            "path": "career-os.toml",
            "detail": "disabled; optional capability",
        }
    ]
