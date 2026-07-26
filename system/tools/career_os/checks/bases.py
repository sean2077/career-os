from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from career_os.checks._contracts import (
    _BASE_CONTRACTS,
    _CHINESE_LOCALIZED_BASES,
    _CHINESE_WORKBENCH_BASES,
    _CJK_TEXT,
    _ENGLISH_LOCALIZED_BASES,
    _ENGLISH_WORKBENCH_BASES,
)


def _validate_base(name: str, base: Any, *, data_root: str | None = None) -> None:
    if not isinstance(base, dict) or not isinstance(base.get("views"), list):
        raise ValueError("Base must define a views list")
    views = base["views"]
    if not all(isinstance(view, dict) and isinstance(view.get("name"), str) for view in views):
        raise ValueError(f"{name} views must be named mappings")
    names = [view["name"] for view in views]
    if len(names) != len(set(names)):
        raise ValueError(f"{name} view names must be unique")
    if name in _ENGLISH_LOCALIZED_BASES | _CHINESE_LOCALIZED_BASES:
        _validate_workbench_base_presentation(name, base)
    if name in _ENGLISH_WORKBENCH_BASES | _CHINESE_WORKBENCH_BASES:
        _validate_workbench_base_portability(name, base)

    contract = _BASE_CONTRACTS.get(name)
    if contract is None:
        return

    required_views = set(contract["views"])
    actual_views = set(names)
    if actual_views != required_views:
        missing = sorted(required_views - actual_views)
        unexpected = sorted(actual_views - required_views)
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unexpected:
            details.append("unexpected " + ", ".join(unexpected))
        raise ValueError(f"{name} required views mismatch: {'; '.join(details)}")

    global_filter_list = _base_filter_expressions(base.get("filters"))
    global_filters = set(global_filter_list)
    expected_global_filters = tuple(
        _normalize_base_expression(_render_base_contract_expression(expression, data_root))
        for expression in contract.get("global_filters", ())
    )
    if contract.get("exact_global_filters") and tuple(global_filter_list) != (
        expected_global_filters
    ):
        raise ValueError(f"{name} global filters do not exactly match the contract")
    missing_filters = [
        _render_base_contract_expression(expression, data_root)
        for expression in contract.get("global_filters", ())
        if _normalize_base_expression(
            _render_base_contract_expression(expression, data_root)
        )
        not in global_filters
    ]
    if missing_filters:
        raise ValueError(f"{name} global filter is missing: {', '.join(missing_filters)}")

    formulas = base.get("formulas")
    formula_contract = contract.get("formula_tokens", {})
    if formula_contract and not isinstance(formulas, dict):
        raise ValueError(f"{name} must define formulas")
    formulas = formulas if isinstance(formulas, dict) else {}
    for formula_name, expected_expression in contract.get(
        "formula_expressions", {}
    ).items():
        expression = formulas.get(formula_name)
        if not isinstance(expression, str) or _normalize_base_expression(
            expression
        ) != _normalize_base_expression(expected_expression):
            raise ValueError(
                f"{name} formula {formula_name} does not match the contract"
            )
    for formula_name, tokens in formula_contract.items():
        expression = formulas.get(formula_name)
        if not isinstance(expression, str):
            raise ValueError(f"{name} is missing formula: {formula_name}")
        missing_tokens = [token for token in tokens if token not in expression]
        if missing_tokens:
            raise ValueError(
                f"{name} formula {formula_name} is missing semantic tokens: "
                + ", ".join(missing_tokens)
            )

    properties = base.get("properties")
    if not isinstance(properties, dict):
        raise ValueError(f"{name} must define semantic properties")
    missing_properties = sorted(set(contract.get("properties", ())) - set(properties))
    if missing_properties:
        raise ValueError(
            f"{name} is missing semantic properties: " + ", ".join(missing_properties)
        )
    if contract.get("exact_properties") and set(properties) != set(
        contract.get("properties", ())
    ):
        raise ValueError(f"{name} properties do not exactly match the contract")
    for property_name, expected_label in contract.get("property_labels", {}).items():
        configuration = properties.get(property_name)
        actual_label = (
            configuration.get("displayName") if isinstance(configuration, dict) else None
        )
        if actual_label != expected_label:
            raise ValueError(
                f"{name} property {property_name} displayName must be {expected_label}"
            )

    views_by_name = {view["name"]: view for view in views}
    for view_name, view_contract in contract["views"].items():
        view = views_by_name[view_name]
        expected_type = view_contract.get("type")
        if expected_type is not None and view.get("type") != expected_type:
            raise ValueError(
                f"{name} view {view_name} type must be {expected_type}"
            )
        expected_limit = view_contract.get("limit")
        if expected_limit is not None and view.get("limit") != expected_limit:
            raise ValueError(
                f"{name} view {view_name} limit must be {expected_limit}"
            )
        view_filter_list = _base_filter_expressions(view.get("filters"))
        filters = set(view_filter_list)
        expected_view_filters = tuple(
            _normalize_base_expression(
                _render_base_contract_expression(expression, data_root)
            )
            for expression in view_contract.get("filters", ())
        )
        if view_contract.get("exact_filters") and tuple(view_filter_list) != (
            expected_view_filters
        ):
            raise ValueError(
                f"{name} view {view_name} filters do not exactly match the contract"
            )
        missing_view_filters = [
            _render_base_contract_expression(expression, data_root)
            for expression in view_contract.get("filters", ())
            if _normalize_base_expression(
                _render_base_contract_expression(expression, data_root)
            )
            not in filters
        ]
        if missing_view_filters:
            raise ValueError(
                f"{name} view {view_name} required filters are missing: "
                + ", ".join(missing_view_filters)
            )

        order = view.get("order")
        if not isinstance(order, list) or not all(isinstance(item, str) for item in order):
            raise ValueError(f"{name} view {view_name} must define an order list")
        expected_order = view_contract.get("order")
        if expected_order is not None and tuple(order) != expected_order:
            raise ValueError(f"{name} view {view_name} column order does not match the contract")
        missing_columns = sorted(set(view_contract.get("columns", ())) - set(order))
        if missing_columns:
            raise ValueError(
                f"{name} view {view_name} is missing required columns: "
                + ", ".join(missing_columns)
            )

        expected_column_sizes = view_contract.get("column_sizes")
        if expected_column_sizes is not None:
            actual_column_sizes = view.get("columnSize")
            if actual_column_sizes != expected_column_sizes:
                raise ValueError(
                    f"{name} view {view_name} columnSize does not match the contract"
                )

        expected_group = view_contract.get("group_by")
        group = view.get("groupBy")
        actual_group = (
            (group.get("property"), group.get("direction"))
            if isinstance(group, dict)
            else None
        )
        if view_contract.get("exact_group_by"):
            if actual_group != expected_group:
                raise ValueError(
                    f"{name} view {view_name} groupBy does not exactly match the contract"
                )
        elif expected_group is not None and actual_group != expected_group:
            raise ValueError(
                f"{name} view {view_name} groupBy must be "
                f"{expected_group[0]} {expected_group[1]}"
            )

        expected_sort = view_contract.get("sort", ())
        if expected_sort:
            sort = view.get("sort")
            if not isinstance(sort, list):
                raise ValueError(f"{name} view {view_name} must define required sort keys")
            actual_sort = [
                (item.get("property"), item.get("direction"))
                for item in sort
                if isinstance(item, dict)
            ]
            sort_matches = (
                tuple(actual_sort) == expected_sort
                if view_contract.get("exact_sort")
                else _ordered_subsequence(expected_sort, actual_sort)
            )
            if not sort_matches:
                rendered = ", ".join(f"{prop} {direction}" for prop, direction in expected_sort)
                raise ValueError(
                    f"{name} view {view_name} is missing required sort keys: {rendered}"
                )


def _validate_base_pair(
    english_name: str,
    english: Any,
    chinese_name: str,
    chinese: Any,
) -> None:
    _validate_base(english_name, english)
    _validate_base(chinese_name, chinese)
    localized_formulas = (
        {"interview_phase"}
        if english_name.endswith("Engagement Decisions.base")
        else set()
    )
    if _base_semantic_projection(
        english, localized_formulas
    ) != _base_semantic_projection(chinese, localized_formulas):
        raise ValueError(
            f"{english_name} and {chinese_name} may differ only in "
            "properties.*.displayName, views[].name, and approved formula output"
        )


def _base_semantic_projection(
    base: Any, localized_formulas: set[str] | None = None
) -> Any:
    projected = deepcopy(base)
    formulas = projected.get("formulas")
    for formula_name in localized_formulas or set():
        if isinstance(formulas, dict) and formula_name in formulas:
            formulas[formula_name] = "__LOCALIZED_FORMULA_OUTPUT__"
    properties = projected.get("properties")
    if isinstance(properties, dict):
        for configuration in properties.values():
            if isinstance(configuration, dict):
                configuration.pop("displayName", None)
    views = projected.get("views")
    if isinstance(views, list):
        for index, view in enumerate(views):
            if isinstance(view, dict):
                view["name"] = f"localized-view-{index}"
    return projected


def _validate_workbench_base_presentation(name: str, base: dict[str, Any]) -> None:
    properties = base.get("properties")
    views = base.get("views")
    if not isinstance(properties, dict) or not isinstance(views, list):
        raise ValueError(f"{name} must define localized properties and views")
    labels: list[str] = []
    for property_name, configuration in properties.items():
        label = (
            configuration.get("displayName")
            if isinstance(configuration, dict)
            else None
        )
        if not isinstance(label, str) or not label.strip():
            raise ValueError(
                f"{name} property {property_name} must define a non-empty displayName"
            )
        labels.append(label)
    view_names = [str(view["name"]) for view in views]
    if name in _ENGLISH_LOCALIZED_BASES:
        formulas = base.get("formulas")
        formula_values = formulas.values() if isinstance(formulas, dict) else ()
        visible = (*labels, *view_names, *formula_values)
        if any(_CJK_TEXT.search(value) for value in visible if isinstance(value, str)):
            raise ValueError(f"{name} must keep English presentation and formula output")
    else:
        untranslated = [
            value for value in (*labels, *view_names) if not _CJK_TEXT.search(value)
        ]
        if untranslated:
            raise ValueError(
                f"{name} must provide Chinese display names and view names: "
                + ", ".join(untranslated)
            )


def _validate_workbench_base_portability(name: str, base: dict[str, Any]) -> None:
    formulas = base.get("formulas")
    expressions = _base_filter_expressions(base.get("filters"))
    for view in base.get("views", []):
        if isinstance(view, dict):
            expressions.extend(_base_filter_expressions(view.get("filters")))
    if isinstance(formulas, dict):
        expressions.extend(value for value in formulas.values() if isinstance(value, str))
    forbidden = (
        "__CAREER_OS_",
        "file.inFolder(",
        "../",
        "..\\",
        "career/",
        "career\\",
        "system/",
        "system\\",
    )
    if any(token in expression for expression in expressions for token in forbidden):
        raise ValueError(f"{name} must not depend on data-root placeholders or fixed paths")
    if any(re.search(r"\.asLink\(\s*\)", expression) for expression in expressions):
        raise ValueError(f"{name} relationship links must display basename-only labels")
    if any(re.search(r'["\'][A-Za-z]:[\\/]', expression) for expression in expressions):
        raise ValueError(f"{name} must not contain an absolute data-root path")


def _base_filter_expressions(value: Any) -> list[str]:
    if isinstance(value, str):
        return [_normalize_base_expression(value)]
    if isinstance(value, list):
        return [expression for item in value for expression in _base_filter_expressions(item)]
    if isinstance(value, dict):
        return [
            expression
            for item in value.values()
            for expression in _base_filter_expressions(item)
        ]
    return []


def _normalize_base_expression(value: str) -> str:
    return " ".join(value.split())


def _render_base_contract_expression(value: str, data_root: str | None) -> str:
    placeholder = "__CAREER_OS_DATA_ROOT__"
    if placeholder not in value:
        return value
    if data_root is None:
        raise ValueError("data-root-aware Base validation requires a Vault-relative data root")
    return value.replace(placeholder, data_root)


def _ordered_subsequence(
    expected: tuple[tuple[str, str], ...], actual: list[tuple[object, object]]
) -> bool:
    position = 0
    for item in expected:
        try:
            position = actual.index(item, position) + 1
        except ValueError:
            return False
    return True
