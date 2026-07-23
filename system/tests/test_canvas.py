from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from career_os.checks import _validate_canvas, _validate_canvas_semantics

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CANVAS_ROOT = REPOSITORY_ROOT / "system/obsidian"
TASK_FIELDS = (
    "**Say:**",
    "**Agent:**",
    "**Skills:**",
    "**Authority:**",
    "**Result:**",
    "**Gate:**",
    "**Verify:**",
)
README_CANVAS_IMAGES = (
    (
        "system/obsidian/career-map.canvas",
        "docs/assets/career-map.png",
    ),
    (
        "system/obsidian/career-guide.canvas",
        "docs/assets/career-guide.png",
    ),
)


def _load(name: str) -> dict[str, Any]:
    loaded = json.loads((CANVAS_ROOT / name).read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_repository_dual_canvas_contract_is_complete_and_bidirectional() -> None:
    overview = _load("career-map.canvas")
    guide = _load("career-guide.canvas")

    _validate_canvas(overview)
    _validate_canvas_semantics("career-map.canvas", overview)
    _validate_canvas(guide)
    _validate_canvas_semantics("career-guide.canvas", guide)
    assert not any(node.get("type") == "file" for node in overview["nodes"])
    assert not any(node.get("type") == "file" for node in guide["nodes"])

    cards = [
        node["text"]
        for node in guide["nodes"]
        if node.get("type") == "text"
        and all(field in node.get("text", "") for field in TASK_FIELDS)
    ]
    assert len([card for card in cards if card.startswith("## Single-domain")]) == 7
    assert len([card for card in cards if card.startswith("## Cross-domain")]) == 4


def test_readme_uses_native_full_canvas_png_projections() -> None:
    readme = REPOSITORY_ROOT.joinpath("README.md").read_text(encoding="utf-8")

    assert len(README_CANVAS_IMAGES) == 2
    for source, output in README_CANVAS_IMAGES:
        image = (REPOSITORY_ROOT / output).read_bytes()
        assert image[:8] == b"\x89PNG\r\n\x1a\n"
        assert image[12:16] == b"IHDR"
        width = int.from_bytes(image[16:20], "big")
        height = int.from_bytes(image[20:24], "big")
        assert width >= 4000
        assert height >= 2000
        assert width > height
        assert f"]({output})" in readme
        assert f"]({source})" in readme


def test_canvas_structure_rejects_duplicate_ids_and_traversal() -> None:
    duplicate = _load("career-map.canvas")
    duplicate["edges"][0]["id"] = duplicate["nodes"][0]["id"]
    with pytest.raises(ValueError, match="IDs must be unique"):
        _validate_canvas(duplicate)

    traversal = _load("career-map.canvas")
    traversal["nodes"].append(
        {
            "id": "ffffffffffffffff",
            "type": "file",
            "file": "../private.md",
            "x": 0,
            "y": 0,
            "width": 100,
            "height": 100,
        }
    )
    with pytest.raises(ValueError, match="escapes the Vault"):
        _validate_canvas(traversal)


def test_canvas_semantics_reject_incomplete_cards_and_non_english_framework_text() -> None:
    guide = _load("career-guide.canvas")
    incomplete = copy.deepcopy(guide)
    card = next(
        node
        for node in incomplete["nodes"]
        if node.get("type") == "text" and "**Say:**" in node.get("text", "")
    )
    card["text"] = card["text"].replace("**Verify:**", "**Check:**")
    with pytest.raises(ValueError, match="seven single-domain and four cross-domain"):
        _validate_canvas_semantics("career-guide.canvas", incomplete)

    translated = copy.deepcopy(guide)
    translated["nodes"][3]["text"] += "\n系统说明"
    with pytest.raises(ValueError, match="framework prose in English"):
        _validate_canvas_semantics("career-guide.canvas", translated)


def test_canvas_semantics_rejects_visual_sprawl_and_unstable_routing() -> None:
    guide = _load("career-guide.canvas")

    sprawling = copy.deepcopy(guide)
    sprawling["nodes"][4]["x"] -= 1200
    with pytest.raises(ValueError, match="compact landscape layout"):
        _validate_canvas_semantics("career-guide.canvas", sprawling)

    verbose = copy.deepcopy(guide)
    task_card = max(
        (
            node
            for node in verbose["nodes"]
            if node.get("type") == "text" and "**Say:**" in node.get("text", "")
        ),
        key=lambda node: len(node["text"]),
    )
    task_card["text"] += " x" * 20
    with pytest.raises(ValueError, match="task cards must stay within 700 characters"):
        _validate_canvas_semantics("career-guide.canvas", verbose)

    unrouted = copy.deepcopy(guide)
    unrouted["edges"][0].pop("fromSide")
    with pytest.raises(ValueError, match="must pin both sides"):
        _validate_canvas_semantics("career-guide.canvas", unrouted)

    overlapping = copy.deepcopy(guide)
    first = overlapping["nodes"][4]
    second = overlapping["nodes"][5]
    second["x"], second["y"] = first["x"], first["y"]
    with pytest.raises(ValueError, match="content nodes .* overlap"):
        _validate_canvas_semantics("career-guide.canvas", overlapping)
