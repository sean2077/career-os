from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath

from ruamel.yaml.error import YAMLError

from career_os.checks._contracts import (
    _CJK_TEXT,
    _HOMEPAGE_AUTHORITY_LINKS,
    _HOMEPAGE_CHINESE_AUTHORITY_LINKS,
    _HOMEPAGE_CHINESE_FRAMEWORK_LINKS,
    _HOMEPAGE_CHINESE_SECONDARY_VIEW_LINKS,
    _HOMEPAGE_CHINESE_WORKBENCH_LINKS,
    _HOMEPAGE_FRAMEWORK_LINKS,
    _HOMEPAGE_HEADINGS,
    _HOMEPAGE_LOCK,
    _HOMEPAGE_MARKDOWNS,
    _HOMEPAGE_SECONDARY_VIEW_LINKS,
    _HOMEPAGE_WORKBENCH_FILES,
    _HOMEPAGE_WORKBENCH_LINKS,
    _LOCALIZED_BASE_PAIRS,
    _MARKDOWN_WIKILINK,
    _README_CANVAS_IMAGES,
    _REQUIRED_CANVAS_ASSETS,
    _yaml,
)
from career_os.checks._issue import CheckIssue
from career_os.checks.bases import _validate_base, _validate_base_pair
from career_os.checks.canvas import _validate_canvas, _validate_canvas_semantics
from career_os.config import ProjectPaths


def _text_digest(normalized: str) -> str:
    """Digest one already newline-normalized text, so the lock is EOL-agnostic."""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _load_homepage_digests(project_root: Path) -> dict[str, str]:
    """Read the canonical homepage digests, or an empty map when unreadable."""
    try:
        loaded = json.loads((project_root / _HOMEPAGE_LOCK).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    homepages = loaded.get("homepages") if isinstance(loaded, dict) else None
    if not isinstance(homepages, dict):
        return {}
    return {
        str(name): str(digest)
        for name, digest in homepages.items()
        if isinstance(digest, str)
    }


def _check_obsidian_sources(paths: ProjectPaths) -> list[CheckIssue]:
    issues: list[CheckIssue] = []
    source_root = paths.project_root / "system/obsidian"
    homepage_digests = _load_homepage_digests(paths.project_root)
    for locale, filename in _HOMEPAGE_MARKDOWNS.items():
        homepage = paths.project_root / filename
        if not homepage.is_file():
            issues.append(
                CheckIssue(
                    "obsidian.homepage-inventory",
                    "fail",
                    str(homepage),
                    f"missing required root {locale} Career Home",
                )
            )
            continue
        digest = homepage_digests.get(filename)
        if digest is None:
            issues.append(
                CheckIssue(
                    "obsidian.homepage-lock",
                    "fail",
                    _HOMEPAGE_LOCK,
                    f"no canonical digest for {filename}; the copy freeze cannot be enforced",
                )
            )
        try:
            _validate_homepage_markdown(
                homepage.read_text(encoding="utf-8"),
                locale=locale,
                canonical_digest=digest,
            )
            issues.append(CheckIssue("obsidian.source", "pass", str(homepage), "valid"))
        except (OSError, ValueError, YAMLError) as error:
            issues.append(CheckIssue("obsidian.source", "fail", str(homepage), str(error)))
    for name, purpose in _REQUIRED_CANVAS_ASSETS.items():
        path = source_root / name
        if not path.is_file():
            issues.append(
                CheckIssue(
                    "obsidian.canvas-inventory",
                    "fail",
                    str(path),
                    f"missing required {purpose}",
                )
            )
    for path in sorted(source_root.rglob("*")):
        if not path.is_file():
            continue
        try:
            if path.suffix == ".base":
                loaded = _yaml.load(path.read_text(encoding="utf-8"))
                key = path.relative_to(paths.project_root).as_posix()
                _validate_base(key, loaded)
            elif path.suffix == ".canvas":
                canvas = json.loads(path.read_text(encoding="utf-8"))
                _validate_canvas(canvas)
                _validate_canvas_semantics(path.name, canvas)
            elif path.name == "dashboard.md":
                _validate_dashboard_markdown(path.read_text(encoding="utf-8"))
            elif path.suffix == ".json":
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(loaded, dict):
                    raise ValueError("adapter JSON must contain an object")
            else:
                continue
            issues.append(CheckIssue("obsidian.source", "pass", str(path), "valid"))
        except (OSError, ValueError, json.JSONDecodeError, YAMLError) as error:
            issues.append(CheckIssue("obsidian.source", "fail", str(path), str(error)))
    for english_relative, chinese_relative in _LOCALIZED_BASE_PAIRS:
        english_path = paths.project_root / english_relative
        chinese_path = paths.project_root / chinese_relative
        missing = [
            str(path.relative_to(paths.project_root))
            for path in (english_path, chinese_path)
            if not path.is_file()
        ]
        if missing:
            issues.append(
                CheckIssue(
                    "obsidian.base-inventory",
                    "fail",
                    str(source_root / "bases"),
                    "missing required localized Base: " + ", ".join(missing),
                )
            )
            continue
        try:
            english = _yaml.load(english_path.read_text(encoding="utf-8"))
            chinese = _yaml.load(chinese_path.read_text(encoding="utf-8"))
            _validate_base_pair(
                english_relative,
                english,
                chinese_relative,
                chinese,
            )
            issues.append(
                CheckIssue(
                    "obsidian.base-pair",
                    "pass",
                    f"{english_path} <-> {chinese_path}",
                    "presentation-only localization parity is valid",
                )
            )
        except (OSError, ValueError, YAMLError) as error:
            issues.append(
                CheckIssue(
                    "obsidian.base-pair",
                    "fail",
                    f"{english_path} <-> {chinese_path}",
                    str(error),
                )
            )
    issues.extend(_check_readme_canvas_images(paths))
    return issues


def _check_readme_canvas_images(paths: ProjectPaths) -> list[CheckIssue]:
    problems: list[str] = []
    try:
        readme = paths.project_root.joinpath("README.md").read_text(encoding="utf-8")
        for source, output in _README_CANVAS_IMAGES:
            path = paths.project_root / output
            if not path.is_file():
                problems.append(f"missing {output}")
            else:
                image = path.read_bytes()
                if len(image) < 24 or image[:8] != b"\x89PNG\r\n\x1a\n" or image[12:16] != b"IHDR":
                    problems.append(f"invalid PNG {output}")
                else:
                    width = int.from_bytes(image[16:20], "big")
                    height = int.from_bytes(image[20:24], "big")
                    if width < 4000 or height < 2000 or width <= height:
                        problems.append(
                            f"{output} is not a full-canvas landscape export ({width}x{height})"
                        )
            if f"]({output})" not in readme:
                problems.append(f"README.md does not embed {output}")
            if f"]({source})" not in readme:
                problems.append(f"README.md does not link {source}")
    except OSError as error:
        problems.append(str(error))

    return [
        CheckIssue(
            "obsidian.readme-images",
            "fail" if problems else "pass",
            "README.md",
            "; ".join(problems)
            if problems
            else "two native full-canvas PNG projections and README links are valid",
        )
    ]


def _validate_homepage_markdown(
    text: str, *, locale: str = "en", canonical_digest: str | None = None
) -> None:
    """Validate one homepage's structure, and freeze its copy when locked.

    The structural rules below own every framework invariant. `canonical_digest`
    additionally freezes the prose between them, which is what keeps personal
    facts out of a system-owned note that Obsidian lets the user edit freely.
    Callers that only exercise structure may omit it; `run_checks` always
    supplies the locked digest.
    """
    if locale not in _HOMEPAGE_MARKDOWNS:
        raise ValueError(f"unsupported homepage locale: {locale}")
    homepage_name = _HOMEPAGE_MARKDOWNS[locale]
    workbench_links = (
        _HOMEPAGE_WORKBENCH_LINKS
        if locale == "en"
        else _HOMEPAGE_CHINESE_WORKBENCH_LINKS
    )
    framework_links = (
        _HOMEPAGE_FRAMEWORK_LINKS
        if locale == "en"
        else _HOMEPAGE_CHINESE_FRAMEWORK_LINKS
    )
    authority_links = (
        _HOMEPAGE_AUTHORITY_LINKS
        if locale == "en"
        else _HOMEPAGE_CHINESE_AUTHORITY_LINKS
    )
    secondary_view_links = (
        _HOMEPAGE_SECONDARY_VIEW_LINKS
        if locale == "en"
        else _HOMEPAGE_CHINESE_SECONDARY_VIEW_LINKS
    )
    link_aliases = dict(
        (*workbench_links, *secondary_view_links, *framework_links, *authority_links)
    )
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---\n"):
        raise ValueError(f"{homepage_name} must begin with YAML frontmatter")
    frontmatter_end = normalized.find("\n---\n", 4)
    if frontmatter_end < 0:
        raise ValueError(f"{homepage_name} frontmatter is not terminated")
    frontmatter = _yaml.load(normalized[4:frontmatter_end])
    if not isinstance(frontmatter, dict):
        raise ValueError(f"{homepage_name} frontmatter must be a mapping")
    if "cssclasses" in frontmatter:
        raise ValueError(f"{homepage_name} must not depend on CSS classes")
    if frontmatter != {"tags": ["career-os", "framework-view"]}:
        raise ValueError(
            f"{homepage_name} frontmatter must contain only the canonical framework tags"
        )

    body = normalized[frontmatter_end + 5 :]
    headings = tuple(re.findall(r"(?m)^#{1,3} [^\n]+$", body))
    if headings != _HOMEPAGE_HEADINGS[locale]:
        raise ValueError(
            f"{homepage_name} sections must remain in the canonical Workbench-first order"
        )

    callouts = re.findall(r"(?m)^>\s*\[![^\]\n]+\][+-]?(?:\s+.*)?$", body)
    expected_callout = "> [!tip] Agent-first" if locale == "en" else "> [!tip] Agent 优先"
    if callouts != [expected_callout]:
        raise ValueError(
            f"{homepage_name} permits only the native, non-folding Agent-first callout"
        )
    if re.search(r"(?m)^\s*(?:```|~~~)", body):
        raise ValueError(f"{homepage_name} must not contain code or plugin-dependent blocks")
    if re.search(r"<\s*/?\s*[A-Za-z][^>]*>", body):
        raise ValueError(f"{homepage_name} must not contain raw HTML or scripts")
    if re.search(r"!?\[[^\]\n]*\]\([^)]+\)", body):
        raise ValueError(f"{homepage_name} must not contain external Markdown links or images")

    direct_counts: dict[str, int] = {}
    embed_counts: dict[str, int] = {}
    workbench_views = dict(workbench_links)
    allowed_views_by_file: dict[str, set[str]] = {}
    for target, _alias in (*workbench_links, *secondary_view_links):
        allowed_views_by_file.setdefault(
            target.split("#", maxsplit=1)[0], set()
        ).add(target)
    for match in _MARKDOWN_WIKILINK.finditer(body):
        raw = match.group("content")
        parts = [part.strip() for part in raw.split("|")]
        if len(parts) not in {1, 2} or not all(parts):
            raise ValueError(
                f"{homepage_name} wikilinks must use a target and at most one explicit alias"
            )
        target = parts[0]
        alias = parts[1] if len(parts) == 2 else None
        filename = target.split("#", maxsplit=1)[0]
        if (
            "/" in filename
            or "\\" in filename
            or PurePosixPath(filename).name != filename
        ):
            raise ValueError(
                f"{homepage_name} target must be filename-only and remain inside the Vault: "
                f"{target}"
            )
        allowed_views = allowed_views_by_file.get(filename)
        if allowed_views is not None and target not in allowed_views:
            raise ValueError(
                f"{homepage_name} Workbench {filename} must target the canonical view "
                "inventory"
            )
        expected_alias = link_aliases.get(target)
        if expected_alias is None:
            raise ValueError(
                f"{homepage_name} target is outside the known framework/data inventory: {target}"
            )

        if match.group("embed") is not None:
            if target not in workbench_views:
                raise ValueError(
                    f"{homepage_name} permits embeds only for its six canonical Workbenches"
                )
            if alias is not None:
                raise ValueError(f"{homepage_name} Workbench embeds must not use aliases")
            line_start = body.rfind("\n", 0, match.start()) + 1
            line_end = body.find("\n", match.end())
            if line_end < 0:
                line_end = len(body)
            if body[line_start:line_end] != f"![[{target}]]":
                raise ValueError(
                    f"{homepage_name} Workbench embeds must be standalone and expanded by default"
                )
            embed_counts[target] = embed_counts.get(target, 0) + 1
        else:
            if alias != expected_alias:
                raise ValueError(
                    f"{homepage_name} target {target} must use alias {expected_alias!r}"
                )
            direct_counts[target] = direct_counts.get(target, 0) + 1

    for target, _alias in workbench_links:
        if direct_counts.get(target, 0) != 1 or embed_counts.get(target, 0) != 1:
            raise ValueError(
                f"{homepage_name} Workbench {target} requires exactly one open link "
                "and one live embed"
            )
    for target, _alias in secondary_view_links:
        if direct_counts.get(target, 0) != 1 or embed_counts.get(target, 0) != 0:
            raise ValueError(
                f"{homepage_name} secondary view {target} requires exactly one direct link"
            )
    for target, _alias in (*framework_links, *authority_links):
        if direct_counts.get(target, 0) != 1 or embed_counts.get(target, 0) != 0:
            raise ValueError(
                f"{homepage_name} navigation target {target} must appear exactly once "
                "as a direct link"
            )

    visible_prose = _MARKDOWN_WIKILINK.sub("", body)
    if locale == "en" and _CJK_TEXT.search(visible_prose):
        raise ValueError(
            "Career Home.md must keep visible framework prose and link aliases in English"
        )
    if locale == "zh-CN" and not _CJK_TEXT.search(visible_prose):
        raise ValueError("职业主页.md must keep visible framework prose in Chinese")
    if (
        "__CAREER_OS_" in visible_prose
        or "/" in visible_prose
        or "\\" in visible_prose
    ):
        raise ValueError(
            f"{homepage_name} visible prose must not contain placeholders or configured paths"
        )
    if canonical_digest is not None and _text_digest(normalized) != canonical_digest:
        raise ValueError(
            f"{homepage_name} must contain only canonical static framework copy; "
            "personal facts and custom presentation are forbidden"
        )


def _validate_dashboard_markdown(text: str) -> None:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if (
        normalized.count("[[Career Home.md|Open Career Home]]") != 1
        or "Home.canvas" in normalized
    ):
        raise ValueError("dashboard.md must link exactly once to the root Markdown homepage")
    if "[[职业主页.md" in normalized:
        raise ValueError("dashboard.md must leave language switching to the homepage")
    for match in _MARKDOWN_WIKILINK.finditer(normalized):
        if match.group("embed") is None:
            continue
        target = match.group("content").split("|", maxsplit=1)[0].strip()
        filename = target.split("#", maxsplit=1)[0]
        if filename in _HOMEPAGE_WORKBENCH_FILES:
            raise ValueError("dashboard.md must not duplicate dedicated Workbench embeds")
    for target in ("records.base#All records", "career-map.canvas", "career-guide.canvas"):
        if normalized.count(f"![[{target}]]") != 1:
            raise ValueError(f"dashboard.md must retain exactly one {target} embed")
    for target, alias in _HOMEPAGE_AUTHORITY_LINKS:
        if normalized.count(f"[[{target}|{alias}]]") != 1:
            raise ValueError(
                f"dashboard.md must retain exactly one Authority link for {target}"
            )
