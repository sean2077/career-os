from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator
from ruamel.yaml import YAML

RECOMMENDATIONS_PATH = Path("system/skills/recommendations.json")
ONBOARDING_STATE_PATH = Path(".career-os/skill-onboarding.json")
SUPPORTED_AGENTS = ("codex", "claude-code")

AgentHost = Literal["codex", "claude-code"]
InstallScope = Literal["project", "global", "skip"]
Audience = Literal["user", "contributor"]

OBSIDIAN_RECOMMENDED_SKILLS = frozenset(
    {"json-canvas", "obsidian-bases", "obsidian-cli", "obsidian-markdown"}
)
CONTRIBUTOR_RECOMMENDED_SKILLS = frozenset(
    {"agent-scaffold", "conventional-commit"}
)
RECOMMENDATION_POLICY: dict[
    str,
    tuple[Audience, str, str, frozenset[str]],
] = {
    "obsidian": (
        "user",
        "https://github.com/kepano/obsidian-skills",
        "MIT",
        OBSIDIAN_RECOMMENDED_SKILLS,
    ),
    "contributor": (
        "contributor",
        "https://github.com/sean2077/skills",
        "MIT",
        CONTRIBUTOR_RECOMMENDED_SKILLS,
    ),
}

_yaml = YAML(typ="safe")


class InstallerRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package: Literal["skills"]
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    telemetry_environment: dict[str, str]

    @model_validator(mode="after")
    def telemetry_is_disabled(self) -> InstallerRecommendation:
        if self.telemetry_environment != {"DISABLE_TELEMETRY": "1"}:
            raise ValueError("Skill installer telemetry must be disabled")
        return self


class RecommendedSkill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    source_path: str
    tree_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SkillRecommendationGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    audience: Audience
    source: str
    source_repository: str
    ref: str
    reviewed_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    license: str
    attribution: str
    skills: list[RecommendedSkill] = Field(min_length=1)

    @model_validator(mode="after")
    def skill_names_are_unique(self) -> SkillRecommendationGroup:
        names = [skill.name for skill in self.skills]
        if len(names) != len(set(names)):
            raise ValueError(f"group {self.id} contains duplicate Skill names")
        return self


class SkillRecommendationManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    revision: int = Field(ge=1)
    installer: InstallerRecommendation
    groups: list[SkillRecommendationGroup] = Field(min_length=1)

    @model_validator(mode="after")
    def groups_follow_recommendation_policy(self) -> SkillRecommendationManifest:
        group_ids = [group.id for group in self.groups]
        if len(group_ids) != len(set(group_ids)):
            raise ValueError("recommendation group IDs must be unique")
        names = [skill.name for group in self.groups for skill in group.skills]
        if len(names) != len(set(names)):
            raise ValueError("a Skill may belong to only one recommendation group")
        if set(group_ids) != set(RECOMMENDATION_POLICY):
            raise ValueError("recommendation groups must be obsidian and contributor")
        for group in self.groups:
            audience, repository, license_id, skill_names = RECOMMENDATION_POLICY[
                group.id
            ]
            if (
                group.audience != audience
                or group.source_repository != repository
                or group.license != license_id
                or {skill.name for skill in group.skills} != skill_names
            ):
                raise ValueError(f"group {group.id} does not match its authority policy")
            slug = group.source_repository.removeprefix(
                "https://github.com/"
            ).rstrip("/")
            if group.source != f"{slug}#{group.ref}":
                raise ValueError(f"group {group.id} source does not match its repository/ref")
            if any(
                skill.source_path != f"skills/{skill.name}"
                for skill in group.skills
            ):
                raise ValueError(f"group {group.id} contains an invalid source path")
        refs = {group.id: group.ref for group in self.groups}
        if refs["obsidian"] != "main":
            raise ValueError("the Obsidian recommendation must use main")
        if re.fullmatch(r"v\d+\.\d+\.\d+", refs["contributor"]) is None:
            raise ValueError("the contributor recommendation must use a stable SemVer tag")
        return self


class SkillOnboardingChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: InstallScope
    agents: list[AgentHost] = Field(default_factory=list)
    recommendation_revision: int = Field(ge=1)

    @model_validator(mode="after")
    def scope_matches_agents(self) -> SkillOnboardingChoice:
        if self.scope == "skip" and self.agents:
            raise ValueError("skip preferences must not name Agent Hosts")
        if self.scope != "skip" and not self.agents:
            raise ValueError("project and global preferences require at least one Agent Host")
        if len(self.agents) != len(set(self.agents)):
            raise ValueError("Agent Hosts must be unique")
        return self


class SkillOnboardingState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    groups: dict[str, SkillOnboardingChoice] = Field(default_factory=dict)


def recommendation_manifest_json_schema() -> dict[str, Any]:
    schema = SkillRecommendationManifest.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://career-os.dev/schemas/skill-recommendations.schema.json"
    schema["title"] = "Career OS Skill Recommendations"
    return schema


def load_recommendation_manifest(project_root: Path) -> SkillRecommendationManifest:
    path = project_root / RECOMMENDATIONS_PATH
    return SkillRecommendationManifest.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def load_onboarding_state(project_root: Path) -> SkillOnboardingState:
    path = project_root / ONBOARDING_STATE_PATH
    if not path.is_file():
        return SkillOnboardingState()
    return SkillOnboardingState.model_validate_json(path.read_text(encoding="utf-8"))


def write_onboarding_state(
    project_root: Path, state: SkillOnboardingState
) -> Path:
    path = project_root / ONBOARDING_STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(
            state.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
        os.replace(temporary_name, path)
    finally:
        with suppress(FileNotFoundError):
            Path(temporary_name).unlink()
    return path


def canonical_tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(
        (
            (path.relative_to(root).as_posix(), path)
            for path in root.rglob("*")
            if path.is_file()
        ),
        key=lambda item: item[0],
    )
    for relative, path in files:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def build_skill_onboarding_report(
    project_root: Path,
    *,
    audience: Audience = "user",
    home_root: Path | None = None,
) -> dict[str, object]:
    project_root = project_root.resolve()
    selected_home = (home_root or Path.home()).resolve()
    manifest = load_recommendation_manifest(project_root)
    state = load_onboarding_state(project_root)
    groups = [
        _group_report(project_root, selected_home, manifest, state, group)
        for group in manifest.groups
        if group.audience == audience
    ]
    return {
        "schema": "career-os-skill-onboarding/1",
        "schema_version": 1,
        "recommendation_revision": manifest.revision,
        "audience": audience,
        "supported_agents": list(SUPPORTED_AGENTS),
        "groups": groups,
        "requires_user_choice": any(
            bool(group["requires_user_choice"]) for group in groups
        ),
    }


def configure_onboarding(
    project_root: Path,
    *,
    group_id: str,
    scope: InstallScope | None,
    agents: list[str],
    reset: bool,
    home_root: Path | None = None,
) -> dict[str, object]:
    project_root = project_root.resolve()
    selected_home = (home_root or Path.home()).resolve()
    manifest = load_recommendation_manifest(project_root)
    group = _manifest_group(manifest, group_id)
    state = load_onboarding_state(project_root)

    if reset:
        if scope is not None or agents:
            raise ValueError("--reset cannot be combined with --scope or --agent")
        state.groups.pop(group_id, None)
    else:
        if scope is None:
            raise ValueError("--scope is required unless --reset is used")
        normalized_agents = _normalize_agents(agents)
        if scope == "skip":
            if normalized_agents:
                raise ValueError("--agent is not valid with --scope skip")
        else:
            if not normalized_agents:
                raise ValueError(
                    "--scope project and --scope global require at least one --agent"
                )
            _require_verified_installation(
                project_root,
                selected_home,
                group,
                scope,
                normalized_agents,
            )
        state.groups[group_id] = SkillOnboardingChoice(
            scope=scope,
            agents=normalized_agents,
            recommendation_revision=manifest.revision,
        )

    state_path = write_onboarding_state(project_root, state)
    report = build_skill_onboarding_report(
        project_root,
        audience=group.audience,
        home_root=selected_home,
    )
    return {
        "ok": True,
        "state": str(state_path),
        "group": group_id,
        "skill_onboarding": report,
    }


def _group_report(
    project_root: Path,
    home_root: Path,
    manifest: SkillRecommendationManifest,
    state: SkillOnboardingState,
    group: SkillRecommendationGroup,
) -> dict[str, object]:
    lock_sources = {
        "project": _installer_lock_sources(project_root / "skills-lock.json"),
        "global": _installer_lock_sources(home_root / ".agents/.skill-lock.json"),
    }
    skill_reports: list[dict[str, object]] = []
    complete: dict[str, dict[str, bool]] = {
        scope: {agent: True for agent in SUPPORTED_AGENTS}
        for scope in ("project", "global")
    }
    combined_complete = {agent: True for agent in SUPPORTED_AGENTS}
    duplicates: list[str] = []
    attention: list[str] = []

    for skill in group.skills:
        scopes: dict[str, object] = {}
        visible_by_scope: dict[str, dict[str, bool]] = {}
        present_scopes: list[str] = []
        for scope in ("project", "global"):
            canonical = _canonical_skill_path(
                project_root, home_root, scope, skill.name
            )
            valid = _valid_skill_directory(canonical, skill.name)
            visible = {
                agent: valid
                and _visible_to_agent(
                    project_root,
                    home_root,
                    scope,
                    cast(AgentHost, agent),
                    canonical,
                )
                for agent in SUPPORTED_AGENTS
            }
            visible_by_scope[scope] = visible
            for agent, is_visible in visible.items():
                complete[scope][agent] = complete[scope][agent] and is_visible
            if valid:
                present_scopes.append(scope)
            actual_hash = canonical_tree_sha256(canonical) if valid else None
            source_status = _source_status(
                lock_sources[scope].get(skill.name),
                group.source_repository,
                skill.source_path,
            )
            if valid and actual_hash != skill.tree_sha256:
                attention.append(f"{skill.name}: {scope} content differs from reviewed tree")
            if valid and source_status != "verified":
                attention.append(f"{skill.name}: {scope} source is {source_status}")
            scopes[scope] = {
                "path": str(canonical),
                "present": valid,
                "visible": visible,
                "source_status": source_status if valid else "absent",
                "tree_sha256": actual_hash,
                "reviewed_tree_sha256": skill.tree_sha256,
                "reviewed": actual_hash == skill.tree_sha256 if valid else False,
            }
        for agent in SUPPORTED_AGENTS:
            combined_complete[agent] = combined_complete[agent] and any(
                visible_by_scope[scope][agent] for scope in ("project", "global")
            )
        if len(present_scopes) == 2:
            duplicates.append(skill.name)
        skill_reports.append({"name": skill.name, "scopes": scopes})

    if duplicates:
        attention.append(
            "project/global duplicates: " + ", ".join(sorted(duplicates))
        )

    preference = state.groups.get(group.id)
    stale_preference = (
        preference is not None
        and preference.recommendation_revision != manifest.revision
    )
    if stale_preference:
        status = "stale"
        requires_choice = True
    elif preference is not None and preference.scope == "skip":
        status = "skipped"
        requires_choice = False
    elif preference is not None:
        installed = all(
            complete[preference.scope][agent] for agent in preference.agents
        )
        source_verified = _all_sources_verified(
            skill_reports, preference.scope
        )
        content_verified = _all_content_reviewed(
            skill_reports, preference.scope
        )
        if installed and source_verified and (group.ref == "main" or content_verified):
            status = "installed"
        elif installed and source_verified:
            status = "drift"
        else:
            status = "partial"
        requires_choice = status != "installed"
    elif (
        any(combined_complete.values())
        and _any_scope_sources_verified(skill_reports)
        and (group.ref == "main" or _any_scope_content_reviewed(skill_reports))
    ):
        status = "installed"
        requires_choice = False
    elif any(
        bool(scope["present"])
        for skill in skill_reports
        for scope in cast(dict[str, dict[str, object]], skill["scopes"]).values()
    ):
        status = "partial"
        requires_choice = True
    else:
        status = "missing"
        requires_choice = True

    return {
        "id": group.id,
        "audience": group.audience,
        "source": group.source,
        "source_repository": group.source_repository,
        "ref": group.ref,
        "reviewed_revision": group.reviewed_revision,
        "license": group.license,
        "attribution": group.attribution,
        "skills": skill_reports,
        "complete": complete,
        "combined_complete": combined_complete,
        "duplicates": sorted(duplicates),
        "duplicate": bool(duplicates),
        "attention": sorted(set(attention)),
        "preference": preference.model_dump(mode="json") if preference else None,
        "preference_stale": stale_preference,
        "status": status,
        "requires_user_choice": requires_choice,
        "install": _install_contract(manifest, group),
    }


def _install_contract(
    manifest: SkillRecommendationManifest,
    group: SkillRecommendationGroup,
) -> dict[str, object]:
    base_args = [
        "npx",
        "--yes",
        f"{manifest.installer.package}@{manifest.installer.version}",
        "add",
        group.source,
        "--skill",
        *(skill.name for skill in group.skills),
    ]
    return {
        "environment": dict(manifest.installer.telemetry_environment),
        "base_args": base_args,
        "scope_args": {"project": [], "global": ["--global"]},
        "agent_args": {
            "codex": ["--agent", "codex"],
            "claude-code": ["--agent", "claude-code"],
            "codex+claude-code": ["--agent", "codex", "claude-code"],
        },
        "confirmation_args": ["-y"],
    }


def _manifest_group(
    manifest: SkillRecommendationManifest, group_id: str
) -> SkillRecommendationGroup:
    for group in manifest.groups:
        if group.id == group_id:
            return group
    raise ValueError(f"unknown Skill recommendation group: {group_id}")


def _normalize_agents(values: list[str]) -> list[AgentHost]:
    unknown = sorted(set(values) - set(SUPPORTED_AGENTS))
    if unknown:
        raise ValueError("unsupported Agent Host(s): " + ", ".join(unknown))
    return [
        cast(AgentHost, agent)
        for agent in SUPPORTED_AGENTS
        if agent in set(values)
    ]


def _require_verified_installation(
    project_root: Path,
    home_root: Path,
    group: SkillRecommendationGroup,
    scope: Literal["project", "global"],
    agents: list[AgentHost],
) -> None:
    lock_path = (
        project_root / "skills-lock.json"
        if scope == "project"
        else home_root / ".agents/.skill-lock.json"
    )
    sources = _installer_lock_sources(lock_path)
    failures: list[str] = []
    for skill in group.skills:
        canonical = _canonical_skill_path(
            project_root, home_root, scope, skill.name
        )
        if not _valid_skill_directory(canonical, skill.name):
            failures.append(f"{skill.name}: missing or invalid {scope} Skill")
            continue
        if (
            group.ref != "main"
            and canonical_tree_sha256(canonical) != skill.tree_sha256
        ):
            failures.append(
                f"{skill.name}: content differs from the reviewed stable tree"
            )
        for agent in agents:
            if not _visible_to_agent(
                project_root, home_root, scope, agent, canonical
            ):
                failures.append(
                    f"{skill.name}: not visible to {agent} in {scope} scope"
                )
        source_status = _source_status(
            sources.get(skill.name),
            group.source_repository,
            skill.source_path,
        )
        if source_status != "verified":
            failures.append(f"{skill.name}: installer source is {source_status}")
    if failures:
        raise ValueError("; ".join(failures))


def _canonical_skill_path(
    project_root: Path,
    home_root: Path,
    scope: Literal["project", "global"],
    name: str,
) -> Path:
    root = project_root if scope == "project" else home_root
    return root / ".agents/skills" / name


def _visible_to_agent(
    project_root: Path,
    home_root: Path,
    scope: Literal["project", "global"],
    agent: AgentHost,
    canonical: Path,
) -> bool:
    if agent == "codex":
        return True
    root = project_root if scope == "project" else home_root
    projection = root / ".claude/skills" / canonical.name
    if not projection.exists():
        return False
    if scope == "project" and not projection.is_symlink():
        return False
    try:
        return projection.resolve() == canonical.resolve()
    except OSError:
        return False


def _valid_skill_directory(path: Path, expected_name: str) -> bool:
    skill_file = path / "SKILL.md"
    if not skill_file.is_file():
        return False
    try:
        text = skill_file.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        if not text.startswith("---\n"):
            return False
        end = text.find("\n---\n", 4)
        if end < 0:
            return False
        loaded = _yaml.load(text[4:end])
        return isinstance(loaded, dict) and loaded.get("name") == expected_name
    except (OSError, UnicodeError, ValueError):
        return False


def _installer_lock_sources(path: Path) -> dict[str, dict[str, str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    raw_skills = payload.get("skills")
    if not isinstance(raw_skills, dict):
        return {}
    result: dict[str, dict[str, str]] = {}
    for name, raw in raw_skills.items():
        if not isinstance(name, str) or not isinstance(raw, dict):
            continue
        result[name] = {
            key: value
            for key in ("source", "sourceUrl", "skillPath")
            if isinstance((value := raw.get(key)), str)
        }
    return result


def _source_status(
    source: dict[str, str] | None,
    expected_repository: str,
    expected_path: str,
) -> Literal["verified", "unknown", "mismatch"]:
    if source is None:
        return "unknown"
    source_path = source.get("skillPath", "").removesuffix("/SKILL.md").strip("/")
    if not source_path:
        return "unknown"
    if source_path != expected_path.strip("/"):
        return "mismatch"
    expected = expected_repository.removesuffix(".git").rstrip("/")
    source_url = source.get("sourceUrl", "").removesuffix(".git").rstrip("/")
    if source_url:
        return "verified" if source_url == expected else "mismatch"
    shorthand = source.get("source", "")
    if expected.endswith("/" + shorthand):
        return "verified"
    return "mismatch"


def _all_sources_verified(
    skill_reports: list[dict[str, object]], scope: str
) -> bool:
    return all(
        cast(dict[str, dict[str, object]], skill["scopes"])[scope]["source_status"]
        == "verified"
        for skill in skill_reports
    )


def _any_scope_sources_verified(
    skill_reports: list[dict[str, object]],
) -> bool:
    return any(
        all(
            cast(dict[str, dict[str, object]], skill["scopes"])[scope]["source_status"]
            == "verified"
            for skill in skill_reports
        )
        for scope in ("project", "global")
    )


def _all_content_reviewed(
    skill_reports: list[dict[str, object]], scope: str
) -> bool:
    return all(
        cast(dict[str, dict[str, object]], skill["scopes"])[scope]["reviewed"]
        is True
        for skill in skill_reports
    )


def _any_scope_content_reviewed(
    skill_reports: list[dict[str, object]],
) -> bool:
    return any(
        _all_content_reviewed(skill_reports, scope)
        for scope in ("project", "global")
    )
