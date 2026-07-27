from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path, PurePosixPath

from pydantic import ValidationError

from career_os import __version__
from career_os.checks._contracts import (
    _AUTHORITY_CONTRACT_PATHS,
    _CJK_TEXT,
)
from career_os.checks._issue import CheckIssue, _issue_detail
from career_os.config import (
    ProjectPaths,
    load_project_config,
    project_config_json_schema,
)
from career_os.downstream import downstream_sync_validation_json_schema
from career_os.imports import import_manifest_json_schema
from career_os.operations import operation_plan_json_schema
from career_os.public_privacy import PublicPrivacyError, audit_public_repository
from career_os.records import record_json_schema
from career_os.resume.fonts import font_manifest_json_schema, load_font_manifest
from career_os.reviewer_contracts import (
    evidence_audit_json_schema,
    interview_probe_json_schema,
)
from career_os.sbom import verify_sbom
from career_os.skill_onboarding import recommendation_manifest_json_schema


def _check_public_privacy_policy(paths: ProjectPaths) -> list[CheckIssue]:
    if paths.development_topology != "standalone-framework":
        return []
    try:
        report = audit_public_repository(paths.project_root)
    except (OSError, PublicPrivacyError, ValueError) as error:
        return [
            CheckIssue(
                "repository.public-privacy",
                "fail",
                str(paths.project_root / "system/privacy/public-fixture-policy.json"),
                str(error),
            )
        ]
    if not report.ok:
        return [
            CheckIssue(
                "repository.public-privacy",
                "fail",
                str(paths.project_root / "system/privacy/public-fixture-policy.json"),
                f"{len(report.findings)} redacted finding(s)",
            )
        ]
    return [
        CheckIssue(
            "repository.public-privacy",
            "pass",
            str(paths.project_root / "system/privacy/public-fixture-policy.json"),
            f"{report.guarded_blob_count} guarded blob(s) approved",
        )
    ]


def _check_layout(paths: ProjectPaths) -> list[CheckIssue]:
    issues: list[CheckIssue] = []
    required = [
        "AGENTS.md",
        "Career Home.md",
        ".agents",
        "system/tools/career_os",
        "system/tools/career_os/adapters",
        "system/tools/career_os/cli",
        "system/tools/career_os/operations",
        "system/tools/career_os/records",
        "system/tools/career_os/resume",
        "system/schemas",
        "system/obsidian",
        "system/resume",
        "system/seeds",
        "system/migrations",
        "system/tests",
    ]
    for relative in required:
        path = paths.project_root / relative
        issues.append(
            CheckIssue(
                id=f"layout.{relative.replace('/', '.')}",
                status="pass" if path.exists() else "fail",
                path=relative,
                detail="present" if path.exists() else "required system path is missing",
            )
        )
    for forbidden in ("src", "tools", "scripts", ".codex/skills"):
        path = paths.project_root / forbidden
        if path.exists():
            issues.append(
                CheckIssue(
                    id=f"layout.forbidden.{forbidden.replace('/', '.')}",
                    status="fail",
                    path=forbidden,
                    detail="product tooling must remain under system/tools",
                )
            )
    claude = paths.project_root / "CLAUDE.md"
    agents = paths.project_root / "AGENTS.md"
    valid_claude = claude.is_symlink() and claude.resolve() == agents.resolve()
    issues.append(
        CheckIssue(
            "layout.CLAUDE.md",
            "pass" if valid_claude else "fail",
            "CLAUDE.md",
            "real relative symlink to AGENTS.md" if valid_claude else "missing or invalid symlink",
        )
    )
    return issues


def _check_configuration(paths: ProjectPaths) -> list[CheckIssue]:
    try:
        config = load_project_config(paths.project_root)
        with (paths.project_root / "pyproject.toml").open("rb") as handle:
            pyproject = tomllib.load(handle)
        project = pyproject.get("project")
        if not isinstance(project, dict) or not isinstance(project.get("version"), str):
            raise ValueError("pyproject.toml project version is missing")
        normalized = config.system_version.replace("-rc.", "rc")
        if normalized != project["version"] or normalized != __version__:
            raise ValueError(
                "version mismatch among career-os.toml, pyproject.toml, and career_os.__version__"
            )
    except (OSError, ValueError, ValidationError) as error:
        return [CheckIssue("config.project", "fail", "career-os.toml", _issue_detail(error))]
    return [
        CheckIssue("config.project", "pass", "career-os.toml", "valid"),
        CheckIssue("version.consistency", "pass", None, config.system_version),
    ]


def _check_subagent_projections(paths: ProjectPaths) -> list[CheckIssue]:
    relative = Path(".agents/tools/generate-subagents.py")
    generator = paths.project_root / relative
    if not generator.is_file():
        return [
            CheckIssue(
                "agents.subagent-projections",
                "fail",
                relative.as_posix(),
                "subagent projection generator is missing",
            )
        ]
    try:
        completed = subprocess.run(
            [sys.executable, str(generator), "--check"],
            cwd=paths.project_root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return [
            CheckIssue(
                "agents.subagent-projections",
                "fail",
                relative.as_posix(),
                f"unable to check subagent projections: {error}",
            )
        ]
    output = "\n".join(
        part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
    )
    detail = " | ".join(output.splitlines()) or "projection check produced no result"
    return [
        CheckIssue(
            "agents.subagent-projections",
            "pass" if completed.returncode == 0 else "fail",
            ".agents/subagents",
            detail,
        )
    ]


def _check_schemas(paths: ProjectPaths) -> list[CheckIssue]:
    schema_root = paths.project_root / "system/schemas"
    issues: list[CheckIssue] = []
    runtime_schemas = {
        "downstream-sync-validation.schema.json": downstream_sync_validation_json_schema,
        "font-manifest.schema.json": font_manifest_json_schema,
        "legacy-import-manifest.schema.json": import_manifest_json_schema,
        "operation-plan.schema.json": operation_plan_json_schema,
        "project-config.schema.json": project_config_json_schema,
        "record-envelope.schema.json": record_json_schema,
        "reviewer-evidence-audit.schema.json": evidence_audit_json_schema,
        "reviewer-interview-probe.schema.json": interview_probe_json_schema,
        "skill-recommendations.schema.json": recommendation_manifest_json_schema,
    }
    actual = {path.name for path in schema_root.glob("*.json")}
    expected = set(runtime_schemas)
    if actual != expected:
        missing = sorted(expected - actual)
        orphaned = sorted(actual - expected)
        detail: list[str] = []
        if missing:
            detail.append("missing: " + ", ".join(missing))
        if orphaned:
            detail.append("orphaned: " + ", ".join(orphaned))
        issues.append(
            CheckIssue("schema.inventory", "fail", str(schema_root), "; ".join(detail))
        )
    for path in sorted(schema_root.glob("*.json")):
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict) or "$schema" not in loaded:
                raise ValueError("schema must be a JSON object with $schema")
            runtime_schema = runtime_schemas.get(path.name)
            if runtime_schema is None:
                continue
            if loaded != runtime_schema():
                raise ValueError(f"committed {path.name} does not match the runtime model")
            issues.append(CheckIssue("schema.json", "pass", str(path), "valid JSON Schema"))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            issues.append(CheckIssue("schema.json", "fail", str(path), str(error)))
    if not issues:
        issues.append(CheckIssue("schema.inventory", "fail", str(schema_root), "no schemas found"))
    return issues


def _check_repository_structure(paths: ProjectPaths) -> list[CheckIssue]:
    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(paths.project_root),
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            check=True,
            capture_output=True,
        )
        tracked = [item.decode("utf-8") for item in completed.stdout.split(b"\0") if item]
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError) as error:
        return [CheckIssue("layout.git-inventory", "fail", None, str(error))]

    executable_suffixes = {".bat", ".cmd", ".js", ".ps1", ".py", ".sh", ".ts"}
    harness_root_files = {".agents/relink-skills.sh", ".agents/symlink-manager.py"}
    misplaced = []
    for relative in tracked:
        suffix = PurePosixPath(relative).suffix.lower()
        if suffix not in executable_suffixes:
            continue
        allowed = (
            relative.startswith("system/")
            or relative.startswith(".agents/tools/")
            or relative.startswith(".agents/skills/")
            or relative in harness_root_files
        )
        if not allowed:
            misplaced.append(relative)
    unsafe_state = [
        relative
        for relative in tracked
        if relative.startswith(("runtime/", "build/", ".career-os/"))
        or "/.obsidian/" in f"/{relative}/"
    ]
    font_binaries = [
        relative
        for relative in tracked
        if PurePosixPath(relative).suffix.lower() in {".otf", ".ttf", ".ttc"}
    ]
    issues = [
        CheckIssue(
            "layout.executable-placement",
            "fail" if misplaced else "pass",
            None,
            ", ".join(misplaced)
            if misplaced
            else "project executables remain under system; Host and Skill bundles are isolated",
        ),
        CheckIssue(
            "layout.generated-state",
            "fail" if unsafe_state else "pass",
            None,
            ", ".join(unsafe_state)
            if unsafe_state
            else "generated state and active Obsidian configuration are untracked",
        ),
        CheckIssue(
            "resume.font-binaries",
            "fail" if font_binaries else "pass",
            None,
            ", ".join(font_binaries)
            if font_binaries
            else "font binaries are confined to ignored local state",
        ),
    ]
    data_relative = paths.data_root.relative_to(paths.project_root).as_posix()
    ignored = subprocess.run(
        [
            "git",
            "-C",
            str(paths.project_root),
            "check-ignore",
            "--no-index",
            "--quiet",
            "--",
            data_relative,
        ],
        check=False,
        capture_output=True,
    )
    git_check_failed = ignored.returncode not in {0, 1}
    issues.append(
        CheckIssue(
            "layout.data-git-boundary",
            "fail" if ignored.returncode == 0 or git_check_failed else "pass",
            data_relative,
            (
                "fixed user data root is ignored by Git"
                if ignored.returncode == 0
                else (
                    ignored.stderr.decode("utf-8", errors="replace").strip()
                    if git_check_failed
                    else "fixed user data root is eligible for Git tracking"
                )
            ),
        )
    )
    return issues


def _check_authority_seeds(paths: ProjectPaths) -> list[CheckIssue]:
    required_sections = {
        "## Key Terms",
        "## Authority Map",
        "## Lifecycle",
        "## Change Rules",
        "## Completion Gate",
    }
    issues: list[CheckIssue] = []
    for relative in sorted(_AUTHORITY_CONTRACT_PATHS):
        path = paths.project_root / relative
        try:
            text = path.read_text(encoding="utf-8")
            missing = sorted(section for section in required_sections if section not in text)
            if missing:
                raise ValueError(f"missing authority sections: {', '.join(missing)}")
            if _CJK_TEXT.search(text):
                raise ValueError("framework authority seed must use English prose")
            issues.append(CheckIssue("seed.authority", "pass", str(path), "complete"))
        except (OSError, ValueError) as error:
            issues.append(CheckIssue("seed.authority", "fail", str(path), str(error)))
    return issues


def _check_supply_chain(paths: ProjectPaths) -> list[CheckIssue]:
    sbom_ok, sbom_detail = verify_sbom(paths.project_root)
    issues = [
        CheckIssue(
            "supply-chain.sbom",
            "pass" if sbom_ok else "fail",
            "system/sbom.cdx.json",
            sbom_detail,
        )
    ]
    notice_path = paths.project_root / "NOTICE"
    try:
        notice = notice_path.read_text(encoding="utf-8")
        required: set[str] = set()
        font_manifest = load_font_manifest(paths.project_root)
        required.update(package.license_path for package in font_manifest.packages)
        required.update(asset.sha256 for _package, asset in font_manifest.iter_assets())
        missing = sorted(item for item in required if item not in notice)
        issues.append(
            CheckIssue(
                "supply-chain.notice",
                "fail" if missing else "pass",
                "NOTICE",
                "missing: " + ", ".join(missing) if missing else "required attribution present",
            )
        )
    except OSError as error:
        issues.append(CheckIssue("supply-chain.notice", "fail", "NOTICE", str(error)))
    return issues
