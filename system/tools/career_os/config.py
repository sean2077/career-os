from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CONFIG_NAME = "career-os.toml"
PROJECT_CONFIG_SCHEMA_DIRECTIVE = "#:schema ./system/schemas/project-config.schema.json"
INSTALL_STATE = Path(".career-os/install.toml")
DATA_ROOT = Path("career")
LOCAL_STATE_ROOT = Path(".career-os")
RUNTIME_ROOT = LOCAL_STATE_ROOT / "runtime"
DevelopmentTopology = Literal[
    "standalone-framework",
    "integrated-workbench",
    "split-downstream",
]
_OPENCLI_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_OPENCLI_PROFILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_OPENCLI_FORBIDDEN_SITES = frozenset({"browser", "external", "plugin"})
_FONT_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _font_role(description: str) -> Any:
    return Field(default=None, description=description)


class ObsidianConfig(BaseModel):
    """Obsidian integration version requirements."""

    model_config = ConfigDict(extra="forbid")

    minimum_version: str = Field(
        default="1.12.7",
        description="Minimum supported Obsidian version.",
    )
    quickadd_version: str = Field(
        default="2.12.3",
        description="QuickAdd version expected by the optional Obsidian integration.",
    )


class ResumeFontRoles(BaseModel):
    """Optional project-wide overrides for the fixed resume font roles."""

    model_config = ConfigDict(extra="forbid")

    latin_body_regular: str | None = _font_role("Latin body regular font filename.")
    latin_body_bold: str | None = _font_role("Latin body bold font filename.")
    latin_body_italic: str | None = _font_role("Latin body italic font filename.")
    latin_body_bold_italic: str | None = _font_role(
        "Latin body bold italic font filename."
    )
    latin_display_regular: str | None = _font_role(
        "Latin display regular font filename."
    )
    latin_display_bold: str | None = _font_role("Latin display bold font filename.")
    latin_display_italic: str | None = _font_role(
        "Latin display italic font filename."
    )
    latin_display_bold_italic: str | None = _font_role(
        "Latin display bold italic font filename."
    )
    cjk_body_regular: str | None = _font_role("CJK body regular font filename.")
    cjk_body_bold: str | None = _font_role("CJK body bold font filename.")
    cjk_body_italic: str | None = _font_role("CJK body italic font filename.")
    cjk_body_bold_italic: str | None = _font_role(
        "CJK body bold italic font filename."
    )
    cjk_display_regular: str | None = _font_role(
        "CJK display regular font filename."
    )
    cjk_display_bold: str | None = _font_role("CJK display bold font filename.")
    cjk_display_italic: str | None = _font_role(
        "CJK display italic font filename."
    )
    cjk_display_bold_italic: str | None = _font_role(
        "CJK display bold italic font filename."
    )
    cjk_mono_regular: str | None = _font_role("CJK monospace regular font filename.")
    cjk_mono_bold: str | None = _font_role("CJK monospace bold font filename.")
    cjk_mono_italic: str | None = _font_role("CJK monospace italic font filename.")
    cjk_mono_bold_italic: str | None = _font_role(
        "CJK monospace bold italic font filename."
    )

    @field_validator("*")
    @classmethod
    def validate_font_filename(cls, value: str | None) -> str | None:
        if value is not None and not _FONT_FILENAME.fullmatch(value):
            raise ValueError("resume font overrides must be safe font filenames")
        return value

    def configured(self) -> dict[str, str]:
        return {
            name: value
            for name, value in self.model_dump().items()
            if value is not None
        }


class ResumeFontsConfig(BaseModel):
    """Project-wide local font directory and role overrides."""

    model_config = ConfigDict(extra="forbid")

    directory: str = Field(
        default=".career-os/fonts",
        description="Portable project-relative directory containing local resume fonts.",
    )
    roles: ResumeFontRoles = Field(
        default_factory=ResumeFontRoles,
        description="Optional fixed resume font role overrides.",
    )

    @field_validator("directory")
    @classmethod
    def validate_directory(cls, value: str) -> str:
        normalized = normalize_portable_subdir(value, field_name="resume.fonts.directory")
        path = PurePosixPath(normalized)
        required = PurePosixPath(".career-os/fonts")
        if path != required and required not in path.parents:
            raise ValueError("resume.fonts.directory must be inside .career-os/fonts/")
        return normalized


class ResumeConfig(BaseModel):
    """Resume build configuration."""

    model_config = ConfigDict(extra="forbid")

    engine: str = Field(
        default="xelatex",
        description="TeX engine used to build Career OS resumes.",
    )
    fonts: ResumeFontsConfig = Field(
        default_factory=ResumeFontsConfig,
        description="Project-wide local resume font overrides.",
    )


class OpenCLIConfig(BaseModel):
    """Allowlisted OpenCLI research integration settings."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(
        default=False,
        description="Whether read-only OpenCLI research commands are enabled.",
    )
    profile: str = Field(
        default="career-research",
        description="Portable OpenCLI profile alias used for research commands.",
    )
    timeout_seconds: int = Field(
        default=60,
        ge=1,
        le=300,
        description="Maximum execution time for one OpenCLI command, in seconds.",
    )
    capture_subdir: str = Field(
        default="research/opencli",
        description=(
            "Portable POSIX subdirectory under the fixed local runtime root for "
            "captured research."
        ),
    )
    sources: dict[str, list[str]] = Field(
        default_factory=dict,
        description=(
            "Allowlist mapping each OpenCLI site name to its permitted read commands."
        ),
    )

    @field_validator("profile")
    @classmethod
    def validate_profile(cls, value: str) -> str:
        if not _OPENCLI_PROFILE.fullmatch(value):
            raise ValueError(
                "OpenCLI profile must be a portable alias using letters, numbers, '.', '_', or '-'"
            )
        return value

    @field_validator("capture_subdir")
    @classmethod
    def validate_capture_subdir(cls, value: str) -> str:
        return normalize_portable_subdir(value, field_name="research.opencli.capture_subdir")

    @field_validator("sources")
    @classmethod
    def validate_sources(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        for site, commands in value.items():
            if not _OPENCLI_IDENTIFIER.fullmatch(site):
                raise ValueError(f"OpenCLI site name is invalid: {site!r}")
            if site in _OPENCLI_FORBIDDEN_SITES:
                raise ValueError(f"OpenCLI raw command namespace is forbidden: {site}")
            if not commands:
                raise ValueError(f"OpenCLI site must allow at least one command: {site}")
            if len(commands) != len(set(commands)):
                raise ValueError(f"OpenCLI commands must be unique for site: {site}")
            invalid = [item for item in commands if not _OPENCLI_IDENTIFIER.fullmatch(item)]
            if invalid:
                raise ValueError(
                    f"OpenCLI command name is invalid for {site}: {invalid[0]!r}"
                )
        return value

    @model_validator(mode="after")
    def require_sources_when_enabled(self) -> OpenCLIConfig:
        if self.enabled and not self.sources:
            raise ValueError("enabled OpenCLI research requires at least one configured source")
        return self


class ResearchConfig(BaseModel):
    """Optional external research integration settings."""

    model_config = ConfigDict(extra="forbid")

    opencli: OpenCLIConfig = Field(
        default_factory=OpenCLIConfig,
        description="Read-only OpenCLI research integration.",
    )


class ProjectConfig(BaseModel):
    """Career OS project configuration stored in career-os.toml."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = Field(
        description="Version of the Career OS project configuration schema.",
    )
    system_version: str = Field(
        description="Career OS system version expected by this project.",
    )
    development_topology: DevelopmentTopology = Field(
        default="standalone-framework",
        description=(
            "Repository topology: a public standalone framework, an integrated "
            "private workbench, or a split downstream."
        ),
    )
    build_root: str = Field(
        default="build",
        description="Path for generated build artifacts.",
    )
    preferred_language: str = Field(
        default="en",
        description="Preferred language code for Career OS content and output.",
    )
    obsidian: ObsidianConfig = Field(
        default_factory=ObsidianConfig,
        description="Obsidian integration settings.",
    )
    resume: ResumeConfig = Field(
        default_factory=ResumeConfig,
        description="Resume build settings.",
    )
    research: ResearchConfig = Field(
        default_factory=ResearchConfig,
        description="Optional external research integrations.",
    )


def project_config_json_schema() -> dict[str, Any]:
    schema = ProjectConfig.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://career-os.dev/schemas/project-config.schema.json"
    schema["title"] = "Career OS Project Configuration"
    return schema


class InstallState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = 2
    mode: Literal["standalone", "embedded"]
    project_root: str
    vault_root: str
    vault_mount: str | None = None
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
    data_root = _fixed_project_path(project_root, DATA_ROOT)
    runtime_root = _fixed_project_path(project_root, RUNTIME_ROOT)

    if state is None:
        vault_root = project_root
        mode = "standalone"
    else:
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
        runtime_root=runtime_root,
        build_root=_resolve_configured_path(project_root, config.build_root),
        local_state_root=project_root / LOCAL_STATE_ROOT,
        vault_root=vault_root,
        mode=mode,
        vault_mount_root=vault_mount_root,
        development_topology=config.development_topology,
    )


def _fixed_project_path(project_root: Path, relative: Path) -> Path:
    candidate = project_root / relative
    if candidate.resolve() != candidate:
        raise ValueError(
            f"fixed project path must not be a symlink, junction, or external alias: {relative}"
        )
    return candidate


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
        f"system_version = {json.dumps(state.system_version)}",
        "languages = [" + ", ".join(json.dumps(item) for item in state.languages) + "]",
        "",
    ]
    if state.vault_mount is not None:
        lines.insert(4, f"vault_mount = {json.dumps(state.vault_mount)}")
    return "\n".join(lines)


def serialize_project_config(config: ProjectConfig) -> str:
    lines = [
        PROJECT_CONFIG_SCHEMA_DIRECTIVE,
        f"schema_version = {config.schema_version}",
        f"system_version = {json.dumps(config.system_version)}",
        (
            "development_topology = "
            f"{json.dumps(config.development_topology)}"
        ),
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
        "[resume.fonts]",
        f"directory = {json.dumps(config.resume.fonts.directory)}",
        "",
        "[resume.fonts.roles]",
    ]
    lines.extend(
        f"{role} = {json.dumps(filename)}"
        for role, filename in sorted(config.resume.fonts.roles.configured().items())
    )
    lines.extend(
        [
        "",
        "[research.opencli]",
        f"enabled = {str(config.research.opencli.enabled).lower()}",
        f"profile = {json.dumps(config.research.opencli.profile)}",
        f"timeout_seconds = {config.research.opencli.timeout_seconds}",
        f"capture_subdir = {json.dumps(config.research.opencli.capture_subdir)}",
        "",
        "[research.opencli.sources]",
        ]
    )
    lines.extend(
        f"{site} = [{', '.join(json.dumps(command) for command in commands)}]"
        for site, commands in sorted(config.research.opencli.sources.items())
    )
    lines.append("")
    return "\n".join(lines)


def normalize_vault_mount(configured: str) -> str:
    if not configured or "\\" in configured:
        raise ValueError("vault_mount must be a non-empty Vault-relative POSIX path")
    if len(configured) >= 2 and configured[0].isalpha() and configured[1] == ":":
        raise ValueError("vault_mount must not contain a drive path")
    relative = PurePosixPath(configured)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError("vault_mount must be a non-traversing Vault-relative POSIX path")
    return relative.as_posix()


def normalize_portable_subdir(configured: str, *, field_name: str) -> str:
    if not configured or "\\" in configured:
        raise ValueError(f"{field_name} must be a non-empty relative POSIX path")
    if len(configured) >= 2 and configured[0].isalpha() and configured[1] == ":":
        raise ValueError(f"{field_name} must not contain a drive path")
    relative = PurePosixPath(configured)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError(f"{field_name} must be a non-traversing relative POSIX path")
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
