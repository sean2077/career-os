from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field

from career_os.config import load_project_config
from career_os.resume.fonts import FontAsset, FontPackage, load_font_manifest
from career_os.skills import SkillLock, load_skill_locks


class LockedDependency(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str


class LockedPackage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    version: str
    dependencies: list[LockedDependency] = Field(default_factory=list)


def build_sbom(project_root: Path) -> dict[str, Any]:
    config = load_project_config(project_root)
    packages = _locked_packages(project_root)
    project = packages.get("career-os")
    if project is None:
        raise ValueError("uv.lock does not contain the career-os project package")
    normalized_version = config.system_version.replace("-rc.", "rc")
    if project.version != normalized_version:
        raise ValueError("uv.lock project version does not match career-os.toml")
    runtime_names = _dependency_closure(packages, project.dependencies)
    root_ref = f"career-os@{config.system_version}"

    python_components = [_python_component(packages[name]) for name in sorted(runtime_names)]
    skill_locks = load_skill_locks(project_root).skills
    skill_components = [
        _skill_component(item) for item in sorted(skill_locks, key=lambda item: item.name)
    ]
    font_manifest = load_font_manifest(project_root)
    font_components = [
        _font_component(package, asset)
        for package, asset in sorted(font_manifest.iter_assets(), key=lambda item: item[1].name)
    ]
    components = python_components + skill_components + font_components

    direct_python = [
        _python_ref(packages[dependency.name])
        for dependency in project.dependencies
        if dependency.name in runtime_names
    ]
    root_dependencies = sorted(
        direct_python
        + [str(component["bom-ref"]) for component in skill_components]
        + [str(component["bom-ref"]) for component in font_components]
    )
    dependencies: list[dict[str, object]] = [{"ref": root_ref, "dependsOn": root_dependencies}]
    for name in sorted(runtime_names):
        package = packages[name]
        depends_on = sorted(
            _python_ref(packages[item.name])
            for item in package.dependencies
            if item.name in runtime_names
        )
        dependency: dict[str, object] = {"ref": _python_ref(package)}
        if depends_on:
            dependency["dependsOn"] = depends_on
        dependencies.append(dependency)
    dependencies.extend(
        {"ref": str(component["bom-ref"])} for component in skill_components + font_components
    )

    serial = uuid5(NAMESPACE_URL, f"https://career-os.dev/releases/{config.system_version}")
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "bom-ref": root_ref,
                "name": "career-os",
                "version": config.system_version,
                "licenses": [{"license": {"id": "MIT"}}],
                "properties": [
                    {"name": "career-os:interface", "value": "cli-and-file-schemas"},
                    {"name": "career-os:data-ownership", "value": "user-owned"},
                ],
            }
        },
        "components": components,
        "dependencies": dependencies,
    }


def verify_sbom(project_root: Path) -> tuple[bool, str]:
    path = project_root / "system/sbom.cdx.json"
    try:
        actual = json.loads(path.read_text(encoding="utf-8"))
        expected = build_sbom(project_root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return False, str(error)
    if actual != expected:
        return False, "SBOM is stale relative to uv.lock, skills-lock.json, or fonts.json"
    return True, f"{len(expected['components'])} locked components"


def _locked_packages(project_root: Path) -> dict[str, LockedPackage]:
    with (project_root / "uv.lock").open("rb") as handle:
        raw = tomllib.load(handle)
    entries = raw.get("package")
    if not isinstance(entries, list):
        raise ValueError("uv.lock package inventory is invalid")
    packages = [LockedPackage.model_validate(item) for item in entries]
    by_name = {package.name: package for package in packages}
    if len(by_name) != len(packages):
        raise ValueError("multiple locked versions of one package are not supported in the SBOM")
    return by_name


def _dependency_closure(
    packages: dict[str, LockedPackage], initial: list[LockedDependency]
) -> set[str]:
    pending = [dependency.name for dependency in initial]
    discovered: set[str] = set()
    while pending:
        name = pending.pop()
        if name in discovered:
            continue
        package = packages.get(name)
        if package is None:
            raise ValueError(f"uv.lock dependency is missing: {name}")
        discovered.add(name)
        pending.extend(item.name for item in package.dependencies)
    return discovered


def _python_ref(package: LockedPackage) -> str:
    normalized = package.name.replace("_", "-")
    return f"pkg:pypi/{normalized}@{package.version}"


def _python_component(package: LockedPackage) -> dict[str, object]:
    reference = _python_ref(package)
    return {
        "type": "library",
        "bom-ref": reference,
        "name": package.name.replace("_", "-"),
        "version": package.version,
        "purl": reference,
        "scope": "required",
    }


def _skill_component(skill: SkillLock) -> dict[str, object]:
    reference = f"skill:{skill.name}@{skill.revision}"
    return {
        "type": "data",
        "bom-ref": reference,
        "name": skill.name,
        "version": skill.revision,
        "hashes": [{"alg": "SHA-256", "content": skill.tree_sha256}],
        "licenses": [{"license": {"id": skill.license}}],
        "externalReferences": [
            {"type": "vcs", "url": f"{skill.source_repository}#{skill.revision}"}
        ],
        "properties": [
            {"name": "career-os:source-path", "value": skill.source_path},
            {"name": "career-os:attribution", "value": skill.attribution},
        ],
    }


def _font_component(package: FontPackage, asset: FontAsset) -> dict[str, object]:
    reference = f"font:{asset.name}@{package.version}"
    return {
        "type": "file",
        "bom-ref": reference,
        "name": asset.name,
        "version": package.version,
        "hashes": [{"alg": "SHA-256", "content": asset.sha256}],
        "licenses": [{"license": {"id": "OFL-1.1"}}],
        "externalReferences": [
            {"type": "distribution", "url": str(asset.url)},
            {"type": "release-notes", "url": str(package.source)},
        ],
        "properties": [
            {"name": "career-os:bundled", "value": "false"},
            {"name": "career-os:expected-size", "value": str(asset.size)},
            {"name": "career-os:font-family", "value": package.family},
            {"name": "career-os:font-role", "value": asset.role},
        ],
    }
