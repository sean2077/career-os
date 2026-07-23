from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from career_os.checks import _validate_dashboard_markdown, _validate_homepage_markdown

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKBENCH_LINKS = (
    ("Recruiting Channels.base#Current Channels", "Open Recruiting Channels"),
    ("JD Screening.base#Current Candidates", "Open JD Screening"),
    ("Company Portfolio.base#Portfolio", "Open Company Portfolio"),
    ("Engagement Decisions.base#Decision Overview", "Open Engagement Decisions"),
    ("Capability Readiness.base#Latest Strict", "Open Capability Readiness"),
)
CHINESE_WORKBENCH_LINKS = (
    ("招聘渠道.base#当前渠道", "打开招聘渠道"),
    ("JD 筛选工作台.base#当前候选", "打开 JD 筛选"),
    ("公司组合.base#总表", "打开公司组合"),
    ("招聘互动决策.base#决策总表", "打开招聘互动决策"),
    ("能力准备度.base#最新严格评估", "打开能力准备度"),
)
FRAMEWORK_LINKS = (
    ("主页.md", "Open Chinese Home"),
    ("records.base", "Open All Records"),
    ("dashboard.md", "Open Text Dashboard"),
    ("career-map.canvas", "Open Architecture Map"),
    ("career-guide.canvas", "Open Workflow Guide"),
)
CHINESE_FRAMEWORK_LINKS = (
    ("Home.md", "English Home"),
    ("records.base", "全部记录"),
    ("dashboard.md", "文本仪表盘"),
    ("career-map.canvas", "架构图"),
    ("career-guide.canvas", "工作流指南"),
)
AUTHORITY_LINKS = (
    ("10-career-evidence.md", "Career Evidence"),
    ("20-career-strategy.md", "Career Strategy"),
    ("30-role-market.md", "Role Market"),
    ("40-opportunity-decision.md", "Opportunity Decision"),
    ("50-career-outlook.md", "Career Outlook"),
    ("60-capability-readiness.md", "Capability Readiness"),
    ("70-career-communication.md", "Career Communication"),
)
CHINESE_AUTHORITY_LINKS = (
    ("10-career-evidence.md", "职业证据"),
    ("20-career-strategy.md", "职业策略"),
    ("30-role-market.md", "职位市场"),
    ("40-opportunity-decision.md", "机会决策"),
    ("50-career-outlook.md", "职业展望"),
    ("60-capability-readiness.md", "能力准备度"),
    ("70-career-communication.md", "职业沟通"),
)


def _homepage(locale: str = "en") -> str:
    filename = "Home.md" if locale == "en" else "主页.md"
    return REPOSITORY_ROOT.joinpath(filename).read_text(encoding="utf-8")


def test_repository_homepage_is_native_live_workbench_panel() -> None:
    homepage = _homepage()

    _validate_homepage_markdown(homepage)

    assert homepage.startswith("---\ntags: [career-os, framework-view]\n---\n# Career Home\n")
    assert homepage.count("> [!tip] Agent-first") == 1
    assert "cssclasses" not in homepage
    assert "Home.canvas" not in homepage
    for target, alias in WORKBENCH_LINKS:
        assert homepage.count(f"[[{target}|{alias}]]") == 1
        assert homepage.count(f"![[{target}]]") == 1
    for target, alias in (*FRAMEWORK_LINKS, *AUTHORITY_LINKS):
        assert homepage.count(f"[[{target}|{alias}]]") == 1
        assert homepage.count(f"![[{target}]]") == 0
    for target, _alias in CHINESE_WORKBENCH_LINKS:
        assert target not in homepage
    headings = (
        "# Career Home",
        "## Discover",
        "### Recruiting Channels",
        "### JD Screening",
        "## Decide",
        "### Company Portfolio",
        "### Engagement Decisions",
        "## Prepare",
        "### Capability Readiness",
        "## Authority Contracts",
    )
    assert [homepage.index(heading) for heading in headings] == sorted(
        homepage.index(heading) for heading in headings
    )


def test_repository_chinese_homepage_expands_only_chinese_workbenches() -> None:
    homepage = _homepage("zh-CN")

    _validate_homepage_markdown(homepage, locale="zh-CN")

    assert homepage.startswith(
        "---\ntags: [career-os, framework-view]\n---\n# 职业主页\n"
    )
    assert homepage.count("> [!tip] Agent 优先") == 1
    for target, alias in CHINESE_WORKBENCH_LINKS:
        assert homepage.count(f"[[{target}|{alias}]]") == 1
        assert homepage.count(f"![[{target}]]") == 1
    for target, alias in (*CHINESE_FRAMEWORK_LINKS, *CHINESE_AUTHORITY_LINKS):
        assert homepage.count(f"[[{target}|{alias}]]") == 1
        assert homepage.count(f"![[{target}]]") == 0
    for target, _alias in WORKBENCH_LINKS:
        assert target not in homepage


def test_homepage_rejects_missing_and_duplicate_navigation_targets() -> None:
    homepage = _homepage()
    records = "[[records.base|Open All Records]]"

    missing = homepage.replace(records, "Open All Records", 1)
    with pytest.raises(ValueError, match="navigation target records.base"):
        _validate_homepage_markdown(missing)

    duplicate = homepage.replace(records, f"{records} · {records}", 1)
    with pytest.raises(ValueError, match="navigation target records.base"):
        _validate_homepage_markdown(duplicate)


def test_homepage_rejects_missing_duplicate_wrong_or_collapsed_workbench_embeds() -> None:
    homepage = _homepage()
    target = "Recruiting Channels.base#Current Channels"
    embed = f"![[{target}]]"

    missing = homepage.replace(embed, "Recruiting Channels", 1)
    with pytest.raises(ValueError, match="requires exactly one open link and one live embed"):
        _validate_homepage_markdown(missing)

    duplicate = homepage.replace(embed, f"{embed}\n\n{embed}", 1)
    with pytest.raises(ValueError, match="requires exactly one open link and one live embed"):
        _validate_homepage_markdown(duplicate)

    wrong_view = homepage.replace(target, "Recruiting Channels.base#All", 1)
    with pytest.raises(ValueError, match="must target the canonical view"):
        _validate_homepage_markdown(wrong_view)

    collapsed = homepage.replace(embed, f"> [!info]- Recruiting Channels\n> {embed}", 1)
    with pytest.raises(ValueError, match="non-folding Agent-first callout"):
        _validate_homepage_markdown(collapsed)


def test_homepage_rejects_misordered_sections_paths_placeholders_and_personal_copy() -> None:
    homepage = _homepage()

    misordered = homepage.replace("## Discover", "## Explore", 1)
    with pytest.raises(ValueError, match="canonical Workbench-first order"):
        _validate_homepage_markdown(misordered)

    escaped = homepage.replace("records.base", "../career/records.base", 1)
    with pytest.raises(ValueError, match="filename-only and remain inside the Vault"):
        _validate_homepage_markdown(escaped)

    placeholder = homepage + "\n__CAREER_OS_DATA_ROOT__\n"
    with pytest.raises(ValueError, match="placeholders or configured paths"):
        _validate_homepage_markdown(placeholder)

    personal = homepage + "\nCandidate: Ada\n"
    with pytest.raises(ValueError, match="personal facts and custom presentation"):
        _validate_homepage_markdown(personal)

    translated = homepage + "\n个人首页\n"
    with pytest.raises(ValueError, match="visible framework prose"):
        _validate_homepage_markdown(translated)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda text: text.replace(
                "tags: [career-os, framework-view]",
                "tags: [career-os, framework-view]\ncssclasses: [homepage]",
                1,
            ),
            "CSS classes",
        ),
        (lambda text: text + "\n<div>Custom layout</div>\n", "raw HTML or scripts"),
        (
            lambda text: text + "\n![Remote](https://example.com/home.png)\n",
            "external Markdown links or images",
        ),
        (
            lambda text: text + "\n```dataview\nTABLE status\n```\n",
            "code or plugin-dependent blocks",
        ),
    ],
)
def test_homepage_rejects_non_native_presentation(
    mutation: Callable[[str], str],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _validate_homepage_markdown(mutation(_homepage()))


def test_dashboard_remains_a_lightweight_markdown_fallback() -> None:
    dashboard = REPOSITORY_ROOT.joinpath("system/obsidian/dashboard.md").read_text(
        encoding="utf-8"
    )

    _validate_dashboard_markdown(dashboard)

    assert dashboard.count("[[Home.md|Open Career Home]]") == 1
    assert "[[主页.md" not in dashboard
    assert "Home.canvas" not in dashboard
    for target, _alias in (*WORKBENCH_LINKS, *CHINESE_WORKBENCH_LINKS):
        filename = target.split("#", maxsplit=1)[0]
        assert f"![[{filename}" not in dashboard

    duplicated = dashboard + "\n![[JD Screening.base#Current Candidates]]\n"
    with pytest.raises(ValueError, match="must not duplicate dedicated Workbench embeds"):
        _validate_dashboard_markdown(duplicated)
