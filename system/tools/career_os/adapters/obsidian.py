from __future__ import annotations

import configparser
import json
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from career_os.config import (
    INSTALL_STATE,
    ProjectPaths,
    load_install_state,
    load_project_config,
    portable_path,
    serialize_install_state,
)
from career_os.operations import FileOperation, OperationPlan, create_plan
from career_os.operations.plans import sha256_file, sha256_text, write_plan

VAULT_STATE = Path(".career-os/vault-install.json")
QUICKADD_CHOICE_ID = "ca2ee657-1ec2-46b4-9d35-1ab0a58d68f8"
QUICKADD_CHOICE_NAME = "Career OS: Capture evidence"

RootName = Literal["project", "vault", "data", "runtime", "host_repo"]

class ManagedChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root: RootName
    path: str
    operation_index: int = Field(ge=0)
    original_sha256: str | None
    installed_sha256: str


class VaultInstallState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    attach_plan_id: UUID
    system_version: str
    vault_root: str
    vault_mount: str | None = None
    data_root: str
    repository_mode: str
    with_quickadd: bool
    roots: dict[str, str]
    changes: list[ManagedChange]
    warnings: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class RepositoryContext:
    mode: str
    host_repo_root: Path | None
    ignore_entry: str | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class VaultPlanResult:
    plan: OperationPlan
    path: Path
    repository_mode: str
    warnings: tuple[str, ...]


def effective_vault_paths(paths: ProjectPaths, vault_root: Path) -> ProjectPaths:
    vault_root = vault_root.resolve()
    if not vault_root.is_dir():
        raise ValueError(f"Vault root is not an existing directory: {vault_root}")
    if paths.mode == "standalone" and vault_root != paths.project_root:
        raise ValueError("standalone mode requires the project root to be the Vault root")
    effective = replace(paths, vault_root=vault_root)
    if paths.mode == "embedded":
        _vault_relative(effective, paths.project_root, "project root")
    _vault_relative(effective, paths.data_root, "data root")
    return effective


def framework_view_assets(paths: ProjectPaths) -> tuple[Path, ...]:
    homepage = paths.project_root / "Home.md"
    chinese_homepage = paths.project_root / "主页.md"
    source_root = paths.project_root / "system/obsidian"
    _vault_relative(paths, homepage, "framework homepage")
    _vault_relative(paths, chinese_homepage, "framework Chinese homepage")
    _vault_relative(paths, source_root, "framework view root")
    return (
        homepage,
        chinese_homepage,
        *(
            source_root / name
            for name in (
                "dashboard.md",
                "records.base",
                "career-map.canvas",
                "career-guide.canvas",
                "bases/en/Recruiting Channels.base",
                "bases/en/JD Screening.base",
                "bases/en/Company Portfolio.base",
                "bases/en/Engagement Decisions.base",
                "bases/en/Capability Readiness.base",
                "bases/zh-CN/招聘渠道.base",
                "bases/zh-CN/JD 筛选工作台.base",
                "bases/zh-CN/公司组合.base",
                "bases/zh-CN/招聘互动决策.base",
                "bases/zh-CN/能力准备度.base",
            )
        ),
    )


def build_views(paths: ProjectPaths) -> list[Path]:
    assets = framework_view_assets(paths)
    for path in assets:
        if not path.is_file():
            raise ValueError(f"framework view asset is missing: {path}")
        if "__CAREER_OS_" in path.read_text(encoding="utf-8"):
            raise ValueError(f"framework view contains an unresolved placeholder: {path}")
    return list(assets)


def render_quickadd_assets(paths: ProjectPaths) -> dict[PurePosixPath, str]:
    source_root = paths.project_root / "system/obsidian/quickadd"
    choice = _render_quickadd_choice(paths)
    return {
        PurePosixPath(".career-os/obsidian/quickadd/capture-choice.json"): (
            json.dumps(choice, indent=2, ensure_ascii=False) + "\n"
        ),
        PurePosixPath(".career-os/obsidian/quickadd/README.md"): source_root.joinpath(
            "README.md"
        ).read_text(encoding="utf-8"),
    }


def validate_quickadd(paths: ProjectPaths) -> tuple[str, ...]:
    config = load_project_config(paths.project_root)
    plugin_root = paths.vault_root / ".obsidian/plugins/quickadd"
    manifest_path = plugin_root / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("QuickAdd is not installed in the selected Vault")
    manifest = _load_json(manifest_path)
    if manifest.get("id") != "quickadd":
        raise ValueError("QuickAdd manifest has an unexpected plugin id")
    version = manifest.get("version")
    if version != config.obsidian.quickadd_version:
        raise ValueError(
            f"QuickAdd {config.obsidian.quickadd_version} is required; found {version!r}"
        )

    data_path = plugin_root / "data.json"
    if not data_path.is_file():
        return ("QuickAdd has no data.json yet; review the generated choice after startup.",)
    data = _load_json(data_path)
    choices = data.get("choices", [])
    if not isinstance(choices, list):
        raise ValueError("QuickAdd data.json has an invalid choices list")
    expected = _render_quickadd_choice(paths)
    warnings: list[str] = []
    for choice in choices:
        if not isinstance(choice, dict):
            raise ValueError("QuickAdd data.json contains a non-object choice")
        if choice.get("id") == QUICKADD_CHOICE_ID:
            if not _contains_mapping(choice, expected):
                raise ValueError("QuickAdd choice id conflicts with the Career OS adapter")
            warnings.append("The Career OS QuickAdd choice is already configured.")
        elif choice.get("name") == QUICKADD_CHOICE_NAME:
            raise ValueError("QuickAdd choice name conflicts with the Career OS adapter")
    return tuple(warnings)


def plan_vault_operation(
    paths: ProjectPaths,
    *,
    action: Literal["attach", "detach"],
    vault_root: Path,
    with_quickadd: bool = False,
) -> VaultPlanResult:
    effective = effective_vault_paths(paths, vault_root)
    if action == "attach":
        return _plan_attach(effective, with_quickadd=with_quickadd)
    if with_quickadd:
        raise ValueError("--with-quickadd is valid only for attach plans")
    return _plan_detach(effective)


def detect_repository_context(paths: ProjectPaths) -> RepositoryContext:
    if paths.mode == "standalone":
        return RepositoryContext("standalone", paths.project_root, None)

    result = subprocess.run(
        ["git", "-C", str(paths.vault_root), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return RepositoryContext("non-git-host", None, None)
    host_repo = Path(result.stdout.strip()).resolve()
    projected_project = _vault_projection(paths, paths.project_root, "project Git path")
    try:
        project_relative = projected_project.relative_to(host_repo)
    except ValueError as error:
        raise ValueError(
            f"project Git path must remain inside the host repository: {projected_project}"
        ) from error
    project_posix = project_relative.as_posix()
    gitlink = _is_gitlink(host_repo, project_posix)
    module_paths = _gitmodule_paths(host_repo / ".gitmodules")
    if project_posix in module_paths:
        warnings = () if gitlink else (".gitmodules entry exists without a matching gitlink.",)
        return RepositoryContext("standard-submodule", host_repo, None, warnings)
    if gitlink:
        return RepositoryContext(
            "bare-gitlink",
            host_repo,
            None,
            ("Unsupported bare gitlink detected; no .gitmodules repair was attempted.",),
        )
    if paths.vault_mount_root is not None:
        tracked = _git_index_mode(host_repo, project_posix) == "120000"
        warnings = (
            ()
            if tracked
            else (
                "External Vault mount is not tracked by the host repository as mode 120000.",
            )
        )
        return RepositoryContext("independent-sibling-symlink", host_repo, None, warnings)
    if (paths.project_root / ".git").exists():
        return RepositoryContext(
            "independent-nested-repository",
            host_repo,
            _literal_gitignore_entry(project_posix),
        )
    return RepositoryContext("embedded-directory", host_repo, None)


def load_vault_state(project_root: Path) -> VaultInstallState | None:
    path = project_root / VAULT_STATE
    if not path.is_file():
        return None
    return VaultInstallState.model_validate_json(path.read_text(encoding="utf-8"))


def _plan_attach(paths: ProjectPaths, *, with_quickadd: bool) -> VaultPlanResult:
    existing = load_vault_state(paths.project_root)
    if existing is not None:
        if Path(existing.vault_root).resolve() != paths.vault_root:
            raise ValueError("Career OS is already attached to a different Vault; detach first")
        if existing.with_quickadd != with_quickadd:
            raise ValueError("the existing attach uses a different QuickAdd option; detach first")
        if existing.vault_mount != _configured_vault_mount(paths):
            raise ValueError("the configured Vault mount changed; detach first")
        _verify_vault_state(existing)
        return _write_vault_plan(
            paths,
            action="vault.attach",
            operations=[],
            roots={key: Path(value) for key, value in existing.roots.items()},
            repository_mode=existing.repository_mode,
            warnings=tuple(existing.warnings),
        )

    install = load_install_state(paths.project_root)
    if install is None:
        raise ValueError("run career-os init before planning a Vault attachment")
    quickadd_warnings = validate_quickadd(paths) if with_quickadd else ()
    context = detect_repository_context(paths)
    roots: dict[str, Path] = {
        "project": paths.project_root,
        "vault": paths.vault_root,
        "data": paths.data_root,
    }
    if context.host_repo_root is not None:
        roots["host_repo"] = context.host_repo_root

    operations: list[FileOperation] = []
    if with_quickadd:
        for relative, content in render_quickadd_assets(paths).items():
            operation = _new_file_operation("project", paths.project_root, relative, content)
            if operation is not None:
                operations.append(operation)

    if context.ignore_entry and context.host_repo_root:
        ignore_path = context.host_repo_root / ".gitignore"
        original = _read_preserved_text(ignore_path) if ignore_path.is_file() else ""
        installed = _append_line(original, context.ignore_entry)
        if installed != original:
            operations.append(
                FileOperation(
                    op="write_text",
                    root="host_repo",
                    path=".gitignore",
                    expected_sha256=sha256_file(ignore_path),
                    result_sha256=sha256_text(installed),
                    content=installed,
                )
            )

    updated_install = install.model_copy(
        update={"vault_root": portable_path(paths.project_root, paths.vault_root)}
    )
    install_content = serialize_install_state(updated_install)
    install_path = paths.project_root / INSTALL_STATE
    if sha256_file(install_path) != sha256_text(install_content):
        operations.append(
            FileOperation(
                op="write_text",
                root="project",
                path=INSTALL_STATE.as_posix(),
                expected_sha256=sha256_file(install_path),
                result_sha256=sha256_text(install_content),
                content=install_content,
            )
        )

    plan_id = uuid4()
    warnings = (*context.warnings, *quickadd_warnings)
    changes = [
        ManagedChange(
            root=operation.root,
            path=operation.path,
            operation_index=index,
            original_sha256=operation.expected_sha256,
            installed_sha256=_required_hash(operation.result_sha256),
        )
        for index, operation in enumerate(operations)
        if operation.op == "write_text"
    ]
    state = VaultInstallState(
        attach_plan_id=plan_id,
        system_version=load_project_config(paths.project_root).system_version,
        vault_root=str(paths.vault_root),
        vault_mount=_configured_vault_mount(paths),
        data_root=str(paths.data_root),
        repository_mode=context.mode,
        with_quickadd=with_quickadd,
        roots={key: str(value.resolve()) for key, value in roots.items()},
        changes=changes,
        warnings=list(warnings),
    )
    state_content = json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    operations.append(
        FileOperation(
            op="write_text",
            root="project",
            path=VAULT_STATE.as_posix(),
            expected_sha256=None,
            result_sha256=sha256_text(state_content),
            content=state_content,
        )
    )
    return _write_vault_plan(
        paths,
        action="vault.attach",
        operations=operations,
        roots=roots,
        repository_mode=context.mode,
        warnings=warnings,
        plan_id=plan_id,
    )


def _plan_detach(paths: ProjectPaths) -> VaultPlanResult:
    state = load_vault_state(paths.project_root)
    if state is None:
        raise ValueError("Career OS is not attached to a Vault")
    if Path(state.vault_root).resolve() != paths.vault_root:
        raise ValueError("detach Vault does not match the recorded attachment")
    _verify_vault_state(state)
    roots = {key: Path(value).resolve() for key, value in state.roots.items()}
    operations: list[FileOperation] = []
    backup_root = paths.local_state_root / "backups" / str(state.attach_plan_id)
    for change in reversed(state.changes):
        if change.original_sha256 is None:
            operations.append(
                FileOperation(
                    op="delete",
                    root=change.root,
                    path=change.path,
                    expected_sha256=change.installed_sha256,
                )
            )
            continue
        backup = backup_root / f"{change.operation_index:04d}" / change.path
        if sha256_file(backup) != change.original_sha256:
            raise ValueError(f"attach backup is missing or changed: {backup}")
        original = _read_preserved_text(backup)
        operations.append(
            FileOperation(
                op="write_text",
                root=change.root,
                path=change.path,
                expected_sha256=change.installed_sha256,
                result_sha256=change.original_sha256,
                content=original,
            )
        )

    state_path = paths.project_root / VAULT_STATE
    operations.append(
        FileOperation(
            op="delete",
            root="project",
            path=VAULT_STATE.as_posix(),
            expected_sha256=sha256_file(state_path),
        )
    )
    return _write_vault_plan(
        paths,
        action="vault.detach",
        operations=operations,
        roots=roots,
        repository_mode=state.repository_mode,
        warnings=tuple(state.warnings),
    )


def _write_vault_plan(
    paths: ProjectPaths,
    *,
    action: str,
    operations: list[FileOperation],
    roots: dict[str, Path],
    repository_mode: str,
    warnings: tuple[str, ...],
    plan_id: UUID | None = None,
) -> VaultPlanResult:
    config = load_project_config(paths.project_root)
    plan = create_plan(
        action=action,
        source_version=config.system_version,
        target_version=config.system_version,
        roots=roots,
        operations=operations,
        plan_id=plan_id,
    )
    action_name = action.rsplit(".", maxsplit=1)[-1]
    plan_path = paths.local_state_root / "plans" / f"vault-{action_name}-{plan.id}.json"
    write_plan(plan, plan_path)
    return VaultPlanResult(plan, plan_path, repository_mode, warnings)


def _verify_vault_state(state: VaultInstallState) -> None:
    roots = {key: Path(value).resolve() for key, value in state.roots.items()}
    for change in state.changes:
        target = _resolve_managed_path(roots, change.root, change.path)
        if sha256_file(target) != change.installed_sha256:
            raise ValueError(f"attached artifact changed after apply: {target}")


def _resolve_managed_path(roots: dict[str, Path], root_name: str, value: str) -> Path:
    if root_name not in roots:
        raise ValueError(f"Vault state does not define root: {root_name}")
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"managed path escapes its root: {value}")
    root = roots[root_name]
    target = root.joinpath(*relative.parts).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"managed path escapes its root: {value}")
    return target


def _new_file_operation(
    root_name: RootName,
    root: Path,
    relative: PurePosixPath,
    content: str,
) -> FileOperation | None:
    target = root.joinpath(*relative.parts)
    current_hash = sha256_file(target)
    result_hash = sha256_text(content)
    if current_hash == result_hash:
        return None
    if current_hash is not None:
        raise ValueError(f"attach target already exists with different content: {target}")
    return FileOperation(
        op="write_text",
        root=root_name,
        path=relative.as_posix(),
        expected_sha256=None,
        result_sha256=result_hash,
        content=content,
    )


def _render_quickadd_choice(paths: ProjectPaths) -> dict[str, object]:
    capture_path = _vault_relative(
        paths,
        paths.data_root / "10-career-evidence/_inbox/quickadd.md",
        "QuickAdd capture path",
    ).as_posix()
    source = paths.project_root / "system/obsidian/quickadd/capture-choice.json"
    rendered = source.read_text(encoding="utf-8").replace(
        "__CAREER_OS_CAPTURE_PATH__", capture_path
    )
    loaded = json.loads(rendered)
    if not isinstance(loaded, dict):
        raise ValueError("QuickAdd adapter source must be a JSON object")
    return loaded


def _contains_mapping(actual: dict[str, object], expected: dict[str, object]) -> bool:
    return all(key in actual and actual[key] == value for key, value in expected.items())


def _load_json(path: Path) -> dict[str, object]:
    loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(loaded, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return loaded


def _vault_relative(paths: ProjectPaths, target: Path, label: str) -> PurePosixPath:
    projected = _vault_projection(paths, target, label)
    relative = projected.relative_to(paths.vault_root.resolve())
    return PurePosixPath(relative.as_posix() or ".")


def _vault_projection(paths: ProjectPaths, target: Path, label: str) -> Path:
    vault_root = paths.vault_root.resolve()
    target = target.resolve()
    if target.is_relative_to(vault_root):
        return target

    mount = paths.vault_mount_root
    if mount is None:
        raise ValueError(f"{label} must remain inside the selected Vault: {target}")
    try:
        project_relative = target.relative_to(paths.project_root.resolve())
    except ValueError as error:
        raise ValueError(
            f"{label} is outside both the selected Vault and its configured project mount: "
            f"{target}"
        ) from error
    projected = mount.joinpath(*project_relative.parts)
    if projected.resolve() != target:
        raise ValueError(f"{label} does not resolve through the configured Vault mount: {target}")
    try:
        projected.relative_to(vault_root)
    except ValueError as error:
        raise ValueError(f"configured Vault mount escapes the selected Vault: {mount}") from error
    return projected


def _configured_vault_mount(paths: ProjectPaths) -> str | None:
    if paths.vault_mount_root is None:
        return None
    return _vault_relative(paths, paths.project_root, "project root").as_posix()


def _read_preserved_text(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _append_line(content: str, line: str) -> str:
    if line in {item.rstrip("\r") for item in content.splitlines()}:
        return content
    newline = "\r\n" if "\r\n" in content else "\n"
    prefix = content
    if prefix and not prefix.endswith(("\n", "\r")):
        prefix += newline
    return f"{prefix}{line}{newline}"


def _literal_gitignore_entry(relative: str) -> str:
    escaped = "".join(f"\\{char}" if char in "*?[]\\" else char for char in relative)
    return f"/{escaped.rstrip('/')}/"


def _gitmodule_paths(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(path, encoding="utf-8")
    return {
        parser.get(section, "path").replace("\\", "/").strip("/")
        for section in parser.sections()
        if parser.has_option(section, "path")
    }


def _is_gitlink(host_repo: Path, relative: str) -> bool:
    return _git_index_mode(host_repo, relative) == "160000"


def _git_index_mode(host_repo: Path, relative: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(host_repo), "ls-files", "--stage", "--", relative],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"could not inspect host Git index: {result.stderr.strip()}")
    modes = {line.split(maxsplit=1)[0] for line in result.stdout.splitlines() if line.strip()}
    return next(iter(modes)) if len(modes) == 1 else None


def _required_hash(value: str | None) -> str:
    if value is None:
        raise ValueError("write operation is missing its result hash")
    return value
