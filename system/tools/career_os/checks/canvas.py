from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any

from career_os.checks._contracts import (
    _AUTHORITY_CONTRACT_PATHS,
    _CANVAS_COLORS,
    _CANVAS_ENDS,
    _CANVAS_ID,
    _CANVAS_LAYOUT_LIMITS,
    _CANVAS_NODE_TYPES,
    _CANVAS_SIDES,
    _CJK_TEXT,
    _REQUIRED_CANVAS_ASSETS,
    _TASK_CARD_FIELDS,
    _WIKILINK,
)


def _validate_canvas(canvas: Any) -> None:
    if not isinstance(canvas, dict):
        raise ValueError("Canvas must be an object")
    nodes = canvas.get("nodes", [])
    edges = canvas.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("Canvas nodes and edges must be arrays")
    node_ids: set[str] = set()
    all_ids: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("Canvas node must be an object")
        node_id = _canvas_object_id(node, "node")
        if node_id in all_ids:
            raise ValueError("Canvas IDs must be unique")
        node_ids.add(node_id)
        all_ids.add(node_id)
        node_type = node.get("type")
        if node_type not in _CANVAS_NODE_TYPES:
            raise ValueError(f"Canvas node has an invalid type: {node_type!r}")
        for field in ("x", "y", "width", "height"):
            value = node.get(field)
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"Canvas node {node_id} has a non-integer {field}")
        if node["width"] <= 0 or node["height"] <= 0:
            raise ValueError(f"Canvas node {node_id} must have positive dimensions")
        _validate_canvas_color(node.get("color"), f"node {node_id}")
        if node_type == "text":
            if not isinstance(node.get("text"), str) or not node["text"].strip():
                raise ValueError(f"Canvas text node {node_id} is missing text")
        elif node_type == "file":
            _validate_canvas_file_path(node.get("file"), f"file node {node_id}")
            subpath = node.get("subpath")
            if subpath is not None and (
                not isinstance(subpath, str) or not subpath.startswith("#")
            ):
                raise ValueError(f"Canvas file node {node_id} has an invalid subpath")
        elif node_type == "link":
            if not isinstance(node.get("url"), str) or not node["url"].strip():
                raise ValueError(f"Canvas link node {node_id} is missing a URL")
        else:
            label = node.get("label")
            if label is not None and not isinstance(label, str):
                raise ValueError(f"Canvas group node {node_id} has an invalid label")
            background = node.get("background")
            if background is not None:
                _validate_canvas_file_path(background, f"group node {node_id} background")
            if node.get("backgroundStyle") not in {None, "cover", "ratio", "repeat"}:
                raise ValueError(f"Canvas group node {node_id} has an invalid background style")

    for edge in edges:
        if not isinstance(edge, dict):
            raise ValueError("Canvas edge must be an object")
        edge_id = _canvas_object_id(edge, "edge")
        if edge_id in all_ids:
            raise ValueError("Canvas IDs must be unique")
        all_ids.add(edge_id)
        if edge.get("fromNode") not in node_ids:
            raise ValueError("Canvas edge has an invalid fromNode")
        if edge.get("toNode") not in node_ids:
            raise ValueError("Canvas edge has an invalid toNode")
        if edge.get("fromSide") not in _CANVAS_SIDES | {None}:
            raise ValueError(f"Canvas edge {edge_id} has an invalid fromSide")
        if edge.get("toSide") not in _CANVAS_SIDES | {None}:
            raise ValueError(f"Canvas edge {edge_id} has an invalid toSide")
        if edge.get("fromEnd") not in _CANVAS_ENDS | {None}:
            raise ValueError(f"Canvas edge {edge_id} has an invalid fromEnd")
        if edge.get("toEnd") not in _CANVAS_ENDS | {None}:
            raise ValueError(f"Canvas edge {edge_id} has an invalid toEnd")
        label = edge.get("label")
        if label is not None and not isinstance(label, str):
            raise ValueError(f"Canvas edge {edge_id} has an invalid label")
        _validate_canvas_color(edge.get("color"), f"edge {edge_id}")


def _canvas_object_id(item: dict[str, Any], item_type: str) -> str:
    value = item.get("id")
    if not isinstance(value, str) or not _CANVAS_ID.fullmatch(value):
        raise ValueError(f"Canvas {item_type} ID must be 16 lowercase hexadecimal characters")
    return value


def _validate_canvas_color(value: Any, context: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or (
        value not in _CANVAS_COLORS and re.fullmatch(r"#[0-9a-fA-F]{6}", value) is None
    ):
        raise ValueError(f"Canvas {context} has an invalid color")


def _validate_canvas_file_path(value: Any, context: str) -> None:
    if not isinstance(value, str) or not value or "\\" in value or value.endswith("/"):
        raise ValueError(f"Canvas {context} has an invalid file path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Canvas {context} file path escapes the Vault")


def _validate_canvas_semantics(name: str, canvas: dict[str, Any]) -> None:
    if name not in _REQUIRED_CANVAS_ASSETS:
        return
    nodes = canvas["nodes"]
    semantic_text: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("type") == "text":
            semantic_text.append(str(node["text"]))
        elif node.get("type") == "group" and isinstance(node.get("label"), str):
            semantic_text.append(str(node["label"]))
    text = "\n".join(semantic_text)
    navigation_targets = {
        str(node["file"]) for node in nodes if isinstance(node, dict) and node.get("type") == "file"
    }
    navigation_targets.update(
        match.group(1).split("|", maxsplit=1)[0].strip()
        for value in semantic_text
        for match in _WIKILINK.finditer(value)
    )
    if _CJK_TEXT.search(text):
        raise ValueError(f"{name} must keep framework prose in English")
    _validate_canvas_layout(name, canvas)
    missing_authorities = sorted(
        suffix
        for suffix in _AUTHORITY_CONTRACT_PATHS
        if Path(suffix).name not in navigation_targets
    )
    if missing_authorities:
        raise ValueError(f"{name} is missing authority entries: {', '.join(missing_authorities)}")

    if name == "career-map.canvas":
        required_fragments = {
            "Agent-native workflow",
            "Natural-language outcome",
            "Seven canonical authorities",
            "Derived views are not authority",
            "State separation",
            "Public or application-grade export",
            "External and account actions",
            "Irrecoverable overwrite or delete",
            "Five independent opportunity blocks",
            "Ownership layers",
        }
        missing = sorted(fragment for fragment in required_fragments if fragment not in text)
        if missing:
            detail = ", ".join(missing)
            raise ValueError(f"career-map.canvas is missing semantic sections: {detail}")
        if "career-guide.canvas" not in navigation_targets:
            raise ValueError("career-map.canvas must link the workflow guide")
        return

    cards = [
        str(node["text"])
        for node in nodes
        if isinstance(node, dict)
        and node.get("type") == "text"
        and all(field in str(node.get("text", "")) for field in _TASK_CARD_FIELDS)
    ]
    single = [card for card in cards if card.startswith("## Single-domain")]
    cross = [card for card in cards if card.startswith("## Cross-domain")]
    if len(cards) != 11 or len(single) != 7 or len(cross) != 4:
        raise ValueError(
            "career-guide.canvas must contain seven single-domain and four cross-domain cards"
        )
    required_skills = {
        "career-evidence",
        "career-strategy",
        "role-market",
        "opportunity-decision",
        "career-outlook",
        "capability-readiness",
        "career-communication",
    }
    missing_skills = sorted(skill for skill in required_skills if f"`{skill}`" not in text)
    if missing_skills:
        raise ValueError(f"career-guide.canvas is missing Skills: {', '.join(missing_skills)}")
    if "career-map.canvas" not in navigation_targets:
        raise ValueError("career-guide.canvas must link the architecture overview")


def _validate_canvas_layout(name: str, canvas: dict[str, Any]) -> None:
    max_width, max_height, min_aspect, max_aspect, min_density, max_text = _CANVAS_LAYOUT_LIMITS[
        name
    ]
    content_nodes = [node for node in canvas["nodes"] if node["type"] != "group"]
    if not content_nodes:
        raise ValueError(f"{name} must contain visible content nodes")

    min_x = min(node["x"] for node in content_nodes)
    min_y = min(node["y"] for node in content_nodes)
    max_x = max(node["x"] + node["width"] for node in content_nodes)
    max_y = max(node["y"] + node["height"] for node in content_nodes)
    width = max_x - min_x
    height = max_y - min_y
    aspect = width / height
    occupied_area = sum(node["width"] * node["height"] for node in content_nodes)
    density = occupied_area / (width * height)
    if width > max_width or height > max_height or not min_aspect <= aspect <= max_aspect:
        raise ValueError(
            f"{name} must keep a compact landscape layout; "
            f"found {width}x{height} with aspect {aspect:.2f}"
        )
    if density < min_density:
        raise ValueError(f"{name} leaves too much empty space; content density is {density:.2f}")

    text_size = sum(len(str(node["text"])) for node in content_nodes if node["type"] == "text")
    if text_size > max_text:
        raise ValueError(f"{name} exceeds its concise text budget: {text_size}/{max_text}")
    if name == "career-guide.canvas":
        task_cards = [
            str(node["text"])
            for node in content_nodes
            if node["type"] == "text"
            and all(field in str(node["text"]) for field in _TASK_CARD_FIELDS)
        ]
        if any(len(card) > 700 for card in task_cards):
            raise ValueError("career-guide.canvas task cards must stay within 700 characters")

    for edge in canvas["edges"]:
        if edge.get("fromSide") is None or edge.get("toSide") is None:
            raise ValueError(f"{name} edge {edge['id']} must pin both sides for stable routing")

    for index, left in enumerate(content_nodes):
        for right in content_nodes[index + 1 :]:
            if _canvas_nodes_overlap(left, right):
                raise ValueError(f"{name} content nodes {left['id']} and {right['id']} overlap")


def _canvas_nodes_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_x = int(left["x"])
    left_y = int(left["y"])
    left_width = int(left["width"])
    left_height = int(left["height"])
    right_x = int(right["x"])
    right_y = int(right["y"])
    right_width = int(right["width"])
    right_height = int(right["height"])
    return (
        left_x < right_x + right_width
        and right_x < left_x + left_width
        and left_y < right_y + right_height
        and right_y < left_y + left_height
    )
