from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from career_os.checks._issue import CheckIssue, _issue_detail
from career_os.config import ProjectPaths
from career_os.resume.fonts import load_font_manifest
from career_os.resume.privacy import load_secret_patterns
from career_os.resume.service import list_resumes, validate_resume_source


def _check_resume_assets(paths: ProjectPaths) -> list[CheckIssue]:
    root = paths.project_root / "system/resume"
    issues: list[CheckIssue] = []
    for relative in (
        "career-os.cls",
        "career-os-style.sty",
        "templates/identity.tex",
        "templates/single-column.tex",
        "fonts.json",
        "secret-patterns.json",
    ):
        path = root / relative
        issues.append(
            CheckIssue(
                "resume.asset",
                "pass" if path.is_file() else "fail",
                str(path),
                "present" if path.is_file() else "required resume asset is missing",
            )
        )
    try:
        manifest = load_font_manifest(paths.project_root)
        for package in manifest.packages:
            license_path = paths.project_root / package.license_path
            if not license_path.is_file():
                raise ValueError(f"font license is missing: {package.license_path}")
        if len(manifest.iter_assets()) != 4:
            raise ValueError("font manifest must pin all four resume font roles")
        issues.append(CheckIssue("resume.font-manifest", "pass", str(root / "fonts.json"), "valid"))
    except (OSError, ValueError, ValidationError) as error:
        issues.append(
            CheckIssue(
                "resume.font-manifest",
                "fail",
                str(root / "fonts.json"),
                _issue_detail(error),
            )
        )
    try:
        patterns = load_secret_patterns(paths.project_root)
        if not patterns:
            raise ValueError("at least one configured secret pattern is required")
        issues.append(
            CheckIssue(
                "resume.secret-patterns",
                "pass",
                str(root / "secret-patterns.json"),
                f"{len(patterns)} patterns",
            )
        )
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as error:
        issues.append(
            CheckIssue(
                "resume.secret-patterns",
                "fail",
                str(root / "secret-patterns.json"),
                _issue_detail(error),
            )
        )

    fixtures = sorted((root / "fixtures").glob("*/resume.tex"))
    for source_path in fixtures:
        try:
            validate_resume_source(paths, source_path)
            issues.append(CheckIssue("resume.fixture", "pass", str(source_path), "valid"))
        except (OSError, ValueError, ValidationError) as error:
            issues.append(
                CheckIssue("resume.fixture", "fail", str(source_path), _issue_detail(error))
            )
    expected_fixture_names = {"en", "multilingual", "zh-CN"}
    fixture_names = {source_path.parent.name for source_path in fixtures}
    if fixture_names != expected_fixture_names:
        issues.append(
            CheckIssue(
                "resume.fixture-inventory",
                "fail",
                str(root / "fixtures"),
                "expected en, multilingual, and zh-CN fixtures; "
                f"found {', '.join(sorted(fixture_names)) or 'none'}",
            )
        )
    else:
        issues.append(
            CheckIssue(
                "resume.fixture-inventory",
                "pass",
                str(root / "fixtures"),
                "en, multilingual, and zh-CN fixtures present",
            )
        )
    try:
        user_resumes = list_resumes(paths)
        for item in user_resumes:
            validate_resume_source(paths, Path(item.source))
            issues.append(CheckIssue("resume.user-source", "pass", item.source, "valid"))
    except (OSError, ValueError, ValidationError) as error:
        issues.append(CheckIssue("resume.user-source", "fail", None, _issue_detail(error)))
    return issues
