from __future__ import annotations

from pathlib import Path

import pytest
from career_os.config import ProjectPaths
from career_os.resume import work_experience as work


class FakeConverter:
    def __init__(self, markdown: str) -> None:
        self.markdown = markdown
        self.layout: bool | None = None
        self.path = ""
        self.options: dict[str, object] = {}

    def use_layout(self, enabled: bool) -> None:
        self.layout = enabled

    def to_markdown(self, path: str, **options: object) -> str:
        self.path = path
        self.options = options
        return self.markdown


def _paths(root: Path) -> ProjectPaths:
    return ProjectPaths(
        project_root=root,
        data_root=root / "career",
        runtime_root=root / ".career-os/runtime",
        build_root=root / "build",
        local_state_root=root / ".career-os",
        vault_root=root,
        mode="standalone",
    )


def test_missing_dependency_points_to_locked_repository_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        work.importlib,
        "import_module",
        lambda _name: (_ for _ in ()).throw(ModuleNotFoundError("pymupdf4llm")),
    )
    with pytest.raises(ValueError, match="uv sync --locked"):
        work.load_converter()


def test_pdf_conversion_forces_stable_legacy_reading_order() -> None:
    converter = FakeConverter("# 工作经历\n\n- result\n\n# 教育背景\n")
    path = Path("fixture.pdf")

    result = work.pdf_to_markdown(path, converter)

    assert result == converter.markdown
    assert converter.layout is False
    assert converter.path == str(path)
    assert converter.options["ignore_images"] is True
    assert converter.options["ignore_graphics"] is True
    assert converter.options["margins"] == (0, 0, 0, 20)


def test_extracts_only_work_experience_and_repairs_soft_wraps() -> None:
    raw = """
## Example Name

### 工作经历 Example **Robotics** | 机器人 高级工程师 2025.01 – 至今

平台建设 技术负责人 2025.01 – 至今

- **职责范围**: 负责[机器人数据系统](https://example.com/system)与核
心平台。

- 代表结果: 将端到端延迟由 200 ms 降至
30 ms。

### Earlier Company | 智慧交通 算法工程师 2020.01 – 2024.12

- __性能优化__: 单节点吞吐提升 20+ 倍。

### 教育背景

Example University
"""

    result = work.extract_work_experience(raw)

    assert "# 工作经历" in result
    assert "## Example Robotics" in result
    assert "## Earlier Company" in result
    assert "1. 职责范围: 负责机器人数据系统与核心平台。" in result
    assert "2. 代表结果: 将端到端延迟由 200 ms 降至 30 ms。" in result
    assert "1. 性能优化: 单节点吞吐提升 20+ 倍。" in result
    assert not work.BOLD_MARKER.search(result)
    assert "https://" not in result
    assert "Example Name" not in result
    assert "Example University" not in result


@pytest.mark.parametrize(
    "markdown",
    [
        "# 工作经历\n\n- result\n",
        "# 工作经历\n\n- one\n\n# 工作经历\n\n- two\n\n# 教育背景\n",
        "# 教育背景\n",
    ],
)
def test_section_boundaries_fail_closed(markdown: str) -> None:
    with pytest.raises(ValueError):
        work.extract_work_experience(markdown)


@pytest.mark.parametrize(
    "markdown",
    [
        "# 工作经历\n\n## Company\n\n1. email private@example.com\n",
        "# 工作经历\n\n## Company\n\n1. phone +86 138 0000 0000\n",
        "# 工作经历\n\n## Company\n\n1. INTERNAL BUILD\n",
        "# 工作经历\n\n## Company\n\n1. 正式简历\n",
        "# 工作经历\n\n## Company\n\n1. AP-20260719-A31F\n",
    ],
)
def test_sensitive_or_footer_content_is_rejected(markdown: str) -> None:
    with pytest.raises(ValueError):
        work.validate_projection(markdown)


def test_output_is_restricted_to_ignored_non_share_build_path(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.build_root.mkdir()
    assert work.resolve_output_path(paths, Path("build/custom-copy.md")) == (
        paths.build_root / "custom-copy.md"
    ).resolve()
    for value in ("README.md", "build/share/copy.md", "build/copy.txt"):
        with pytest.raises(ValueError):
            work.resolve_output_path(paths, Path(value))


def test_temporary_publish_intentionally_overwrites_atomically(tmp_path: Path) -> None:
    destination = tmp_path / "build/copy.md"
    work.publish_temporary_markdown("first\n", destination)
    work.publish_temporary_markdown("second\n", destination)
    assert destination.read_text(encoding="utf-8") == "second\n"
