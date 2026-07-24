from __future__ import annotations

from pathlib import Path

from career_os.checks import _check_repository_structure
from career_os.config import resolve_paths
from career_os.sbom import build_sbom, verify_sbom

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_sbom_matches_all_runtime_locks_and_external_assets() -> None:
    valid, detail = verify_sbom(PROJECT_ROOT)
    sbom = build_sbom(PROJECT_ROOT)

    assert valid, detail
    assert len(sbom["components"]) == 39
    references = {component["bom-ref"] for component in sbom["components"]}
    assert "pkg:pypi/pydantic@2.13.4" in references
    assert "pkg:pypi/pymupdf4llm@1.28.0" in references
    assert any(str(item).startswith("skill:agent-scaffold@") for item in references)
    assert any(str(item).startswith("skill:opencli-usage@") for item in references)
    assert "font:NotoSansCJKsc-Regular.otf@2.004" in references
    assert "font:SourceHanSerifSC-Regular.otf@2.003" in references


def test_repository_executable_and_generated_state_boundaries() -> None:
    issues = _check_repository_structure(resolve_paths(PROJECT_ROOT))

    assert issues
    assert all(issue.status == "pass" for issue in issues)
