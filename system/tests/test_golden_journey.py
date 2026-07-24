from __future__ import annotations

from pathlib import Path

from career_os.checks import run_checks
from career_os.config import resolve_paths


def test_integrated_workbench_full_check_has_no_failures() -> None:
    paths = resolve_paths(Path(__file__).resolve().parents[2])
    issues = run_checks(paths, fast=False, host=False)
    assert not [issue for issue in issues if issue.status == "fail"]
