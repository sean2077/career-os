from __future__ import annotations

import json
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Literal, cast

import typer
from pydantic import ValidationError

from career_os import __version__
from career_os.checks import has_failures, run_checks
from career_os.config import (
    INSTALL_STATE,
    InstallState,
    discover_project_root,
    load_install_state,
    load_project_config,
    normalize_vault_mount,
    portable_path,
    resolve_paths,
    resolve_vault_mount,
    write_install_state,
)
from career_os.git_safety import inspect_downstream_git_safety
from career_os.records.models import StrategyPositioning
from career_os.seed import initialize_data_root


def init_command(
    mode: Annotated[str, typer.Option(help="Installation mode: standalone or embedded.")],
    root: Annotated[Path, typer.Option(help="Career OS project root.")] = Path("."),
    vault_root: Annotated[Path | None, typer.Option(help="Host Obsidian Vault root.")] = None,
    vault_mount: Annotated[
        str | None,
        typer.Option(
            help="Vault-relative POSIX path of a directory symlink to an external project root."
        ),
    ] = None,
    data_root: Annotated[Path | None, typer.Option(help="User-owned data root.")] = None,
    languages: Annotated[str, typer.Option(help="Comma-separated BCP 47 language tags.")] = "en",
) -> None:
    """Initialize user-owned data without overwriting existing records."""
    root = root.resolve()
    if mode not in {"standalone", "embedded"}:
        raise typer.BadParameter("mode must be standalone or embedded", param_hint="--mode")
    selected_mode = cast(Literal["standalone", "embedded"], mode)
    if not (root / "career-os.toml").is_file():
        raise typer.BadParameter("root must contain career-os.toml", param_hint="--root")
    config = load_project_config(root)
    selected_vault = (vault_root or root).resolve()
    if mode == "embedded" and vault_root is None:
        raise typer.BadParameter("embedded mode requires --vault-root", param_hint="--vault-root")
    if not selected_vault.is_dir():
        raise typer.BadParameter(
            "Vault root must be an existing directory", param_hint="--vault-root"
        )

    selected_mount: str | None = None
    if vault_mount is not None:
        if selected_mode != "embedded":
            raise typer.BadParameter(
                "--vault-mount is valid only in embedded mode", param_hint="--vault-mount"
            )
        try:
            selected_mount = normalize_vault_mount(vault_mount)
            resolve_vault_mount(root, selected_vault, selected_mount)
        except ValueError as error:
            raise typer.BadParameter(str(error), param_hint="--vault-mount") from error
    elif selected_mode == "embedded" and not root.is_relative_to(selected_vault):
        raise typer.BadParameter(
            "an embedded project outside the Vault requires --vault-mount",
            param_hint="--vault-mount",
        )

    selected_data = data_root or Path(config.data_root)
    if not selected_data.is_absolute():
        selected_data = root / selected_data
    selected_data = selected_data.resolve()
    parsed_languages = [item.strip() for item in languages.split(",") if item.strip()]
    try:
        StrategyPositioning.model_validate(
            {
                "id": "00000000-0000-4000-8000-000000000000",
                "kind": "strategy.positioning",
                "schema_version": 2,
                "created_at": "2000-01-01T00:00:00Z",
                "updated_at": "2000-01-01T00:00:00Z",
                "languages": parsed_languages,
                "status": "candidate",
                "migration_review": "not-applicable",
                "confidence": "low",
                "review_on": "2000-01-01",
                "disconfirming_signals": [],
            }
        )
    except ValidationError as error:
        raise typer.BadParameter(str(error), param_hint="--languages") from error

    existing = load_install_state(root)
    state = InstallState(
        mode=selected_mode,
        project_root=".",
        vault_root=portable_path(root, selected_vault),
        vault_mount=selected_mount,
        data_root=portable_path(root, selected_data),
        system_version=config.system_version,
        languages=parsed_languages,
    )
    if existing is not None and existing != state:
        raise typer.BadParameter(
            "installation already exists with different settings; inspect .career-os/install.toml"
        )
    created = initialize_data_root(selected_data, root / "system/seeds")
    state_path = write_install_state(root, state)
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "mode": mode,
                "data_root": str(selected_data),
                "vault_root": str(selected_vault),
                "vault_mount": selected_mount,
                "created": [str(item) for item in created],
                "install_state": str(state_path),
            },
            indent=2,
        )
    )


def paths_command(
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    """Resolve project, data, runtime, build, and Vault roots."""
    _ = json_output
    try:
        paths = resolve_paths(root)
    except (FileNotFoundError, OSError, ValueError, ValidationError) as error:
        typer.echo(json.dumps({"ok": False, "error": str(error)}, indent=2))
        raise typer.Exit(1) from error
    typer.echo(json.dumps({"ok": True, **paths.as_dict()}, indent=2))


def doctor_command(
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    """Check local prerequisites without changing project or user state."""
    try:
        project_root = discover_project_root(root)
    except FileNotFoundError as error:
        _emit_doctor([{"id": "project", "status": "fail", "detail": str(error)}], json_output)
        raise typer.Exit(1) from error

    commands = {
        "git": "required",
        "latexmk": "resume",
        "xelatex": "resume",
        "pdftoppm": "resume-visual-check",
        "pdfinfo": "resume-inspection",
    }
    checks: list[dict[str, str | None]] = [
        {
            "id": "project",
            "status": "pass",
            "path": str(project_root),
            "detail": "career-os.toml found",
        },
        {
            "id": "python",
            "status": "pass" if sys.version_info >= (3, 12) else "fail",
            "path": sys.executable,
            "detail": sys.version.split()[0],
        },
    ]
    for command, capability in commands.items():
        resolved = shutil.which(command)
        required = command in {"git"}
        checks.append(
            {
                "id": f"command.{command}",
                "status": "pass" if resolved else ("fail" if required else "attention"),
                "path": resolved,
                "detail": capability,
            }
        )
    checks.extend(
        {
            "id": item.id,
            "status": item.status,
            "path": item.path,
            "detail": item.detail,
        }
        for item in inspect_downstream_git_safety(
            project_root,
            initialized=(project_root / INSTALL_STATE).is_file(),
        )
    )
    checks.extend(_obsidian_doctor_checks(project_root))
    try:
        git_root = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        checks.append(
            {"id": "git.repository", "status": "pass", "path": git_root, "detail": "valid"}
        )
    except (OSError, subprocess.CalledProcessError) as error:
        checks.append(
            {"id": "git.repository", "status": "fail", "path": None, "detail": str(error)}
        )
    _emit_doctor(checks, json_output)
    if any(item["status"] == "fail" for item in checks):
        raise typer.Exit(1)


def check_command(
    root: Annotated[Path, typer.Option(help="Path inside the Career OS project.")] = Path("."),
    fast: Annotated[
        bool, typer.Option("--fast", help="Skip user records and host-aware checks.")
    ] = False,
    host: Annotated[
        bool, typer.Option("--host", help="Resolve typed references in the host Vault.")
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    """Validate system structure, schemas, records, references, and assets."""
    try:
        paths = resolve_paths(root)
        issues = run_checks(paths, fast=fast, host=host)
    except (FileNotFoundError, OSError, ValueError, ValidationError) as error:
        issues_payload = [
            {"id": "check.bootstrap", "status": "fail", "path": None, "detail": str(error)}
        ]
        if json_output:
            typer.echo(
                json.dumps(
                    {"ok": False, "status": "fail", "checks": issues_payload}, indent=2
                )
            )
        else:
            typer.echo(f"FAIL check.bootstrap: {error}")
        raise typer.Exit(1) from error
    ok = not has_failures(issues)
    status = "fail" if not ok else (
        "attention" if any(issue.status == "attention" for issue in issues) else "pass"
    )
    payload = {
        "ok": ok,
        "status": status,
        "checks": [item.as_dict() for item in issues],
    }
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
    else:
        for issue in issues:
            typer.echo(f"{issue.status.upper():9} {issue.id}: {issue.detail}")
        typer.echo(f"Career OS check: {status.upper()}")
    if not payload["ok"]:
        raise typer.Exit(1)


def _emit_doctor(checks: list[dict[str, str | None]], json_output: bool) -> None:
    ok = not any(item["status"] == "fail" for item in checks)
    if json_output:
        typer.echo(json.dumps({"ok": ok, "version": __version__, "checks": checks}, indent=2))
        return
    for check in checks:
        status = str(check["status"]).upper()
        typer.echo(f"{status:9} {check['id']}: {check['detail']}")


def _obsidian_doctor_checks(project_root: Path) -> list[dict[str, str | None]]:
    config = load_project_config(project_root)
    executable = shutil.which("obsidian")
    running = _obsidian_process_running()
    checks: list[dict[str, str | None]] = [
        {
            "id": "obsidian.cli-registration",
            "status": "pass" if executable else "attention",
            "path": executable,
            "detail": "registered on PATH" if executable else "optional live CLI is not registered",
        },
        {
            "id": "obsidian.app-running",
            "status": "pass" if running else "attention",
            "path": None,
            "detail": "running" if running else "not running; live checks were not invoked",
        },
    ]
    if not executable or not running:
        checks.append(
            {
                "id": "obsidian.version",
                "status": "attention",
                "path": executable,
                "detail": f"requires Obsidian {config.obsidian.minimum_version}+ with CLI enabled",
            }
        )
        return checks
    try:
        completed = subprocess.run(
            [executable, "version"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = (completed.stdout or completed.stderr).strip()
        version = _parse_version(output)
        supported = version is not None and _version_at_least(
            version, config.obsidian.minimum_version
        )
        checks.extend(
            [
                {
                    "id": "obsidian.cli-enabled",
                    "status": "pass",
                    "path": executable,
                    "detail": "CLI responded from the running application",
                },
                {
                    "id": "obsidian.version",
                    "status": "pass" if supported else "attention",
                    "path": executable,
                    "detail": (
                        version
                        if supported
                        else f"expected {config.obsidian.minimum_version}+; output was {output!r}"
                    ),
                },
            ]
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        checks.extend(
            [
                {
                    "id": "obsidian.cli-enabled",
                    "status": "attention",
                    "path": executable,
                    "detail": f"CLI did not respond: {error}",
                },
                {
                    "id": "obsidian.version",
                    "status": "attention",
                    "path": executable,
                    "detail": f"requires Obsidian {config.obsidian.minimum_version}+",
                },
            ]
        )
    return checks


def _obsidian_process_running() -> bool:
    system = platform.system()
    command = (
        ["tasklist", "/FI", "IMAGENAME eq Obsidian.exe", "/FO", "CSV", "/NH"]
        if system == "Windows"
        else ["pgrep", "-x", "Obsidian" if system == "Darwin" else "obsidian"]
    )
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if system == "Windows":
        return completed.returncode == 0 and '"Obsidian.exe"' in completed.stdout
    return completed.returncode == 0 and bool(completed.stdout.strip())


def _parse_version(output: str) -> str | None:
    match = re.search(r"(?<!\d)(\d+\.\d+\.\d+)(?!\d)", output)
    return match.group(1) if match else None


def _version_at_least(actual: str, minimum: str) -> bool:
    return tuple(int(item) for item in actual.split(".")) >= tuple(
        int(item) for item in minimum.split(".")
    )
