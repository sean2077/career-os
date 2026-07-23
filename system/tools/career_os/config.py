from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CONFIG_NAME = "career-os.toml"
INSTALL_STATE = Path(".career-os/install.toml")
DevelopmentTopology = Literal[
    "standalone-framework",
    "integrated-workbench",
    "split-downstream",
]


class ObsidianConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum_version: str = "1.12.7"
    quickadd_version: str = "2.12.3"


class ResumeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine: str = "xelatex"


class ProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1)
    system_version: str
    development_topology: DevelopmentTopology = "standalone-framework"
    data_root: str = "career"
    runtime_root: str = "runtime"
    build_root: str = "build"
    preferred_language: str = "en"
    obsidian: ObsidianConfig = Field(default_factory=ObsidianConfig)
    resume: ResumeConfig = Field(default_factory=ResumeConfig)


class InstallState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    mode: Literal["standalone", "embedded"]
    project_root: str
    vault_root: str
    vault_mount: str | None = None
    data_root: str
    system_version: str
    languages: list[str]


@dataclass(frozen=True)
class ProjectPaths:
    project_root: Path
    data_root: Path
    runtime_root: Path
    build_root: Path
    local_state_root: Path
    vault_root: Path
    mode: str
    vault_mount_root: Path | None = None
    development_topology: DevelopmentTopology = "standalone-framework"

    def as_dict(self) -> dict[str, str | None]:
        return {
            "project_root": str(self.project_root),
            "data_root": str(self.data_root),
            "runtime_root": str(self.runtime_root),
            "build_root": str(self.build_root),
            "local_state_root": str(self.local_state_root),
            "vault_root": str(self.vault_root),
            "mode": self.mode,
            "development_topology": self.development_topology,
            "vault_mount_root": (
                str(self.vault_mount_root) if self.vault_mount_root is not None else None
            ),
        }


def discover_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / CONFIG_NAME).is_file():
            return candidate
    raise FileNotFoundError(f"Could not find {CONFIG_NAME} from {current}")


def load_project_config(root: Path) -> ProjectConfig:
    with (root / CONFIG_NAME).open("rb") as handle:
        return ProjectConfig.model_validate(tomllib.load(handle))


def load_install_state(root: Path) -> InstallState | None:
    path = root / INSTALL_STATE
    if not path.is_file():
        return None
    with path.open("rb") as handle:
        return InstallState.model_validate(tomllib.load(handle))


def resolve_paths(root: Path | None = None) -> ProjectPaths:
    project_root = discover_project_root(root)
    config = load_project_config(project_root)
    state = load_install_state(project_root)

    if state is None:
        data_root = _resolve_configured_path(project_root, config.data_root)
        vault_root = project_root
        mode = "standalone"
    else:
        data_root = _resolve_configured_path(project_root, state.data_root)
        vault_root = _resolve_configured_path(project_root, state.vault_root)
        mode = state.mode

    vault_mount_root: Path | None = None
    if state is not None and mode == "embedded":
        if state.vault_mount is not None:
            vault_mount_root = resolve_vault_mount(
                project_root, vault_root, state.vault_mount
            )
        elif not project_root.is_relative_to(vault_root):
            raise ValueError(
                "embedded project outside the Vault requires a configured vault_mount"
            )

    return ProjectPaths(
        project_root=project_root,
        data_root=data_root,
        runtime_root=_resolve_configured_path(project_root, config.runtime_root),
        build_root=_resolve_configured_path(project_root, config.build_root),
        local_state_root=project_root / ".career-os",
        vault_root=vault_root,
        mode=mode,
        vault_mount_root=vault_mount_root,
        development_topology=config.development_topology,
    )


def write_install_state(root: Path, state: InstallState) -> Path:
    path = root / INSTALL_STATE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize_install_state(state), encoding="utf-8", newline="\n")
    return path


def serialize_install_state(state: InstallState) -> str:
    lines = [
        f"schema_version = {state.schema_version}",
        f"mode = {json.dumps(state.mode)}",
        f"project_root = {json.dumps(state.project_root)}",
        f"vault_root = {json.dumps(state.vault_root)}",
        f"data_root = {json.dumps(state.data_root)}",
        f"system_version = {json.dumps(state.system_version)}",
        "languages = [" + ", ".join(json.dumps(item) for item in state.languages) + "]",
        "",
    ]
    if state.vault_mount is not None:
        lines.insert(4, f"vault_mount = {json.dumps(state.vault_mount)}")
    return "\n".join(lines)


def serialize_project_config(config: ProjectConfig) -> str:
    return "\n".join(
        [
            f"schema_version = {config.schema_version}",
            f"system_version = {json.dumps(config.system_version)}",
            (
                "development_topology = "
                f"{json.dumps(config.development_topology)}"
            ),
            f"data_root = {json.dumps(config.data_root)}",
            f"runtime_root = {json.dumps(config.runtime_root)}",
            f"build_root = {json.dumps(config.build_root)}",
            f"preferred_language = {json.dumps(config.preferred_language)}",
            "",
            "[obsidian]",
            f"minimum_version = {json.dumps(config.obsidian.minimum_version)}",
            f"quickadd_version = {json.dumps(config.obsidian.quickadd_version)}",
            "",
            "[resume]",
            f"engine = {json.dumps(config.resume.engine)}",
            "",
        ]
    )


def normalize_vault_mount(configured: str) -> str:
    if not configured or "\\" in configured:
        raise ValueError("vault_mount must be a non-empty Vault-relative POSIX path")
    if len(configured) >= 2 and configured[0].isalpha() and configured[1] == ":":
        raise ValueError("vault_mount must not contain a drive path")
    relative = PurePosixPath(configured)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError("vault_mount must be a non-traversing Vault-relative POSIX path")
    return relative.as_posix()


def resolve_vault_mount(project_root: Path, vault_root: Path, configured: str) -> Path:
    relative = PurePosixPath(normalize_vault_mount(configured))
    mount = vault_root.joinpath(*relative.parts)
    if not mount.is_symlink():
        raise ValueError(f"vault_mount must be a directory symbolic link: {mount}")
    resolved = mount.resolve()
    if resolved != project_root.resolve():
        raise ValueError(
            f"vault_mount must resolve to the Career OS project root: {mount} -> {resolved}"
        )
    return mount


def portable_path(project_root: Path, target: Path) -> str:
    target = target.resolve()
    try:
        relative = target.relative_to(project_root.resolve())
    except ValueError:
        return str(target)
    return relative.as_posix() or "."


def _resolve_configured_path(project_root: Path, configured: str) -> Path:
    path = Path(configured)
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()
