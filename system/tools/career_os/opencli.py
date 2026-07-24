from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

from career_os.config import RUNTIME_ROOT, OpenCLIConfig, ProjectConfig

DoctorCheck = dict[str, str | None]
_NODE_MINIMUM = (20, 0, 0)
_VERSION = re.compile(r"(?<!\d)(\d+)\.(\d+)\.(\d+)(?!\d)")


def opencli_doctor_checks(
    project_root: Path, project_config: ProjectConfig
) -> list[DoctorCheck]:
    config = project_config.research.opencli
    if not config.enabled:
        return [
            {
                "id": "research.opencli-config",
                "status": "pass",
                "path": "career-os.toml",
                "detail": "disabled; optional capability",
            }
        ]

    capture_root = _capture_root(project_root, config)
    checks: list[DoctorCheck] = [
        {
            "id": "research.opencli-config",
            "status": "pass",
            "path": "career-os.toml",
            "detail": (
                f"enabled for {len(config.sources)} source(s); "
                f"raw captures stay under {capture_root}"
            ),
        }
    ]

    node = shutil.which("node")
    checks.append(_node_check(project_root, node))

    executable = shutil.which("opencli")
    if executable is None:
        checks.extend(
            [
                {
                    "id": "command.opencli",
                    "status": "attention",
                    "path": None,
                    "detail": "enabled optional capability is not installed",
                },
                {
                    "id": "research.opencli-registry",
                    "status": "attention",
                    "path": None,
                    "detail": "not checked because opencli is unavailable",
                },
                _bridge_check(),
            ]
        )
        return checks

    checks.append(_opencli_version_check(project_root, executable))
    checks.append(_registry_check(project_root, executable, config))
    checks.append(_bridge_check())
    return checks


def _capture_root(project_root: Path, config: OpenCLIConfig) -> Path:
    relative = PurePosixPath(config.capture_subdir)
    return (project_root / RUNTIME_ROOT).joinpath(*relative.parts)


def _node_check(project_root: Path, executable: str | None) -> DoctorCheck:
    if executable is None:
        return {
            "id": "command.node",
            "status": "attention",
            "path": None,
            "detail": "enabled OpenCLI requires Node.js 20 or newer",
        }
    try:
        completed = _run([executable, "--version"], project_root, timeout=5)
        output = (completed.stdout or completed.stderr).strip()
        version = _parse_version(output)
        if version is None:
            raise ValueError(f"unrecognized version output: {output!r}")
        supported = version >= _NODE_MINIMUM
        return {
            "id": "command.node",
            "status": "pass" if supported else "fail",
            "path": executable,
            "detail": (
                ".".join(str(item) for item in version)
                if supported
                else f"expected 20.0.0 or newer; found {output}"
            ),
        }
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        return {
            "id": "command.node",
            "status": "attention",
            "path": executable,
            "detail": f"version probe failed: {error}",
        }


def _opencli_version_check(project_root: Path, executable: str) -> DoctorCheck:
    try:
        completed = _run([executable, "--version"], project_root, timeout=5)
        output = (completed.stdout or completed.stderr).strip()
        if not output:
            raise ValueError("empty version output")
        return {
            "id": "command.opencli",
            "status": "pass",
            "path": executable,
            "detail": output,
        }
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        return {
            "id": "command.opencli",
            "status": "attention",
            "path": executable,
            "detail": f"version probe failed: {error}",
        }


def _registry_check(
    project_root: Path, executable: str, config: OpenCLIConfig
) -> DoctorCheck:
    try:
        completed = _run(
            [executable, "list", "-f", "json"],
            project_root,
            timeout=config.timeout_seconds,
        )
        entries = _registry_entries(completed.stdout)
        configured = {
            (site, command)
            for site, commands in config.sources.items()
            for command in commands
        }
        discovered: dict[tuple[str, str], str | None] = {}
        duplicates: set[tuple[str, str]] = set()
        for entry in entries:
            site = entry.get("site")
            command = entry.get("name")
            if not isinstance(site, str) or not isinstance(command, str):
                continue
            key = (site, command)
            if key in discovered:
                duplicates.add(key)
            discovered[key] = entry.get("access") if isinstance(entry.get("access"), str) else None

        missing = sorted(configured - set(discovered))
        non_read = sorted(
            (site, command, discovered[(site, command)])
            for site, command in configured & set(discovered)
            if discovered[(site, command)] != "read"
        )
        relevant_duplicates = sorted(configured & duplicates)
        if missing or non_read or relevant_duplicates:
            details: list[str] = []
            if missing:
                details.append(
                    "missing: " + ", ".join(f"{site}/{command}" for site, command in missing)
                )
            if non_read:
                details.append(
                    "not read-only: "
                    + ", ".join(
                        f"{site}/{command} ({access or 'missing access'})"
                        for site, command, access in non_read
                    )
                )
            if relevant_duplicates:
                details.append(
                    "duplicate: "
                    + ", ".join(f"{site}/{command}" for site, command in relevant_duplicates)
                )
            return {
                "id": "research.opencli-registry",
                "status": "fail",
                "path": executable,
                "detail": "; ".join(details),
            }
        return {
            "id": "research.opencli-registry",
            "status": "pass",
            "path": executable,
            "detail": f"{len(configured)} configured command(s) exist and declare access=read",
        }
    except (
        json.JSONDecodeError,
        OSError,
        ValueError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ) as error:
        return {
            "id": "research.opencli-registry",
            "status": "fail",
            "path": executable,
            "detail": f"live registry is unavailable or invalid: {error}",
        }


def _registry_entries(output: str) -> list[dict[str, Any]]:
    payload = json.loads(output)
    if isinstance(payload, dict):
        for key in ("data", "commands"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                payload = candidate
                break
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError("opencli list -f json must return a command array")
    return payload


def _bridge_check() -> DoctorCheck:
    raw_port = os.environ.get("OPENCLI_DAEMON_PORT", "19825")
    path = f"127.0.0.1:{raw_port}"
    try:
        port = int(raw_port)
        if not 1 <= port <= 65535:
            raise ValueError("port is outside 1..65535")
        connection = socket.create_connection(("127.0.0.1", port), timeout=0.25)
        connection.close()
        return {
            "id": "research.opencli-bridge",
            "status": "pass",
            "path": path,
            "detail": "loopback bridge is already listening",
        }
    except (OSError, ValueError) as error:
        return {
            "id": "research.opencli-bridge",
            "status": "attention",
            "path": path,
            "detail": f"not running; doctor did not launch it ({error})",
        }


def _run(
    arguments: list[str], project_root: Path, *, timeout: int
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _parse_version(output: str) -> tuple[int, int, int] | None:
    match = _VERSION.search(output)
    if match is None:
        return None
    major, minor, patch = (int(item) for item in match.groups())
    return major, minor, patch
