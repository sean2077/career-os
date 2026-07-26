"""Deterministic validation of one Career OS installation.

`run_checks` is the single entry point; `CheckIssue` is the reported unit. The
submodules own one validation domain each, and `_contracts` holds the
declarative Obsidian view data they interpret. Names re-exported here are the
seam that `career_os.cli` and the tests import.
"""

from __future__ import annotations

from career_os.checks._issue import CheckIssue, _issue_detail
from career_os.checks.bases import (
    _base_semantic_projection,
    _validate_base,
    _validate_base_pair,
)
from career_os.checks.canvas import (
    _validate_canvas,
    _validate_canvas_layout,
    _validate_canvas_semantics,
)
from career_os.checks.records import (
    _check_record_semantics,
    _check_record_transitions,
    _check_records,
)
from career_os.checks.resume import _check_resume_assets
from career_os.checks.structure import (
    _check_authority_seeds,
    _check_configuration,
    _check_layout,
    _check_public_privacy_policy,
    _check_repository_structure,
    _check_schemas,
    _check_subagent_projections,
    _check_supply_chain,
)
from career_os.checks.views import (
    _check_obsidian_sources,
    _check_readme_canvas_images,
    _text_digest,
    _validate_dashboard_markdown,
    _validate_homepage_markdown,
)
from career_os.config import INSTALL_STATE, ProjectPaths
from career_os.git_safety import inspect_downstream_git_safety
from career_os.skills import verify_skills

__all__ = [
    "CheckIssue",
    "has_failures",
    "run_checks",
    # Validation helpers the test suite drives directly with synthetic input.
    "_base_semantic_projection",
    "_check_obsidian_sources",
    "_check_readme_canvas_images",
    "_check_repository_structure",
    "_check_schemas",
    "_issue_detail",
    "_text_digest",
    "_validate_base",
    "_validate_base_pair",
    "_validate_canvas",
    "_validate_canvas_layout",
    "_validate_canvas_semantics",
    "_validate_dashboard_markdown",
    "_validate_homepage_markdown",
]


def run_checks(paths: ProjectPaths, *, fast: bool, host: bool) -> list[CheckIssue]:
    issues: list[CheckIssue] = []
    issues.extend(_check_layout(paths))
    issues.extend(_check_configuration(paths))
    issues.extend(
        CheckIssue(item.id, item.status, item.path, item.detail)
        for item in inspect_downstream_git_safety(
            paths.project_root,
            initialized=(paths.project_root / INSTALL_STATE).is_file(),
        )
    )
    issues.extend(_check_subagent_projections(paths))
    issues.extend(_check_schemas(paths))
    issues.extend(_check_authority_seeds(paths))
    issues.extend(_check_repository_structure(paths))
    issues.extend(_check_public_privacy_policy(paths))
    issues.extend(_check_resume_assets(paths))
    issues.extend(_check_supply_chain(paths))
    issues.extend(
        CheckIssue(item.id, item.status, item.path, item.detail)
        for item in verify_skills(paths.project_root)
    )
    if not fast:
        records, record_issues = _check_records(paths)
        issues.extend(record_issues)
        issues.extend(_check_record_transitions(paths, records))
        issues.extend(_check_record_semantics(paths, records))
        issues.extend(_check_obsidian_sources(paths))
    return issues


def has_failures(issues: list[CheckIssue]) -> bool:
    return any(issue.status == "fail" for issue in issues)
