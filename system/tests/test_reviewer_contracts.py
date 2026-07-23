from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from career_os.cli import app
from career_os.reviewer_contracts import validate_reviewer
from typer.testing import CliRunner


def _evidence_payload(status: str = "supported") -> dict[str, Any]:
    blocking = status in {
        "needs-confirmation",
        "unsupported",
        "conflicting/stale",
    }
    return {
        "schema": "resume-evidence-audit/1",
        "claims": [
            {
                "claim": "Representative public claim",
                "status": status,
                "risk": "Ownership and metric scope could be challenged.",
                "evidence": [] if blocking else ["evidence.work:work-1"],
                "boundary": (
                    "Only the measured scenario is supported."
                    if status == "bounded"
                    else None
                ),
                "conflicts": (
                    ["The current metric differs from the archived value."]
                    if status == "conflicting/stale"
                    else []
                ),
                "confirmation_question": (
                    "Please confirm the current source and scope." if blocking else None
                ),
                "handoff": "evidence-repair" if blocking else "none",
            }
        ],
    }


def _probe_payload(
    *,
    packet_status: str = "accepted",
    question: str | None = None,
    outcome: str | None = "passed",
) -> dict[str, Any]:
    return {
        "schema": "resume-interview-probe/1",
        "packet_status": packet_status,
        "branch": "metric-scope-1",
        "claim": "Latency improved in the measured scenario.",
        "current_question": question,
        "target_dimensions": ["fact-boundary", "technical-depth"],
        "follow_up_triggers": ["The measurement boundary is missing."],
        "outcome": outcome,
    }


@pytest.mark.parametrize("status", ["supported", "bounded"])
def test_valid_nonblocking_evidence_statuses(status: str) -> None:
    result = validate_reviewer("evidence", _evidence_payload(status))

    assert result.valid
    assert not result.blocks_readiness
    assert result.errors == ()


@pytest.mark.parametrize(
    "status",
    ["needs-confirmation", "unsupported", "conflicting/stale"],
)
def test_valid_blocking_evidence_statuses(status: str) -> None:
    result = validate_reviewer("evidence", _evidence_payload(status))

    assert result.valid
    assert result.blocks_readiness
    assert result.errors == ()


def _add_unknown(payload: dict[str, Any]) -> None:
    payload["unexpected"] = True


def _remove_risk(payload: dict[str, Any]) -> None:
    payload["claims"][0].pop("risk")


def _duplicate_claim(payload: dict[str, Any]) -> None:
    payload["claims"].append(payload["claims"][0].copy())


def _set_illegal_status(payload: dict[str, Any]) -> None:
    payload["claims"][0]["status"] = "approved"


def _add_nonblocking_action(payload: dict[str, Any]) -> None:
    payload["claims"][0]["confirmation_question"] = "Is this current?"


@pytest.mark.parametrize(
    ("mutate", "marker"),
    [
        (_add_unknown, "Extra inputs are not permitted"),
        (_remove_risk, "Field required"),
        (_duplicate_claim, "duplicates an earlier claim"),
        (_set_illegal_status, "Input should be"),
        (
            _add_nonblocking_action,
            "non-blocking status cannot carry an unresolved action",
        ),
    ],
)
def test_evidence_contract_fails_closed(
    mutate: Callable[[dict[str, Any]], None],
    marker: str,
) -> None:
    payload = _evidence_payload()
    mutate(payload)

    result = validate_reviewer("evidence", payload)

    assert not result.valid
    assert result.blocks_readiness
    assert any(marker in error for error in result.errors)


def test_evidence_state_machine_rejects_missing_action_and_false_boundary() -> None:
    missing_action = _evidence_payload("unsupported")
    missing_action["claims"][0]["confirmation_question"] = None
    missing_action["claims"][0]["handoff"] = "none"
    result = validate_reviewer("evidence", missing_action)
    assert not result.valid
    assert any(
        "requires a confirmation question or handoff" in item
        for item in result.errors
    )

    false_boundary = _evidence_payload("supported")
    false_boundary["claims"][0]["boundary"] = "Narrower than the public claim."
    result = validate_reviewer("evidence", false_boundary)
    assert not result.valid
    assert any(
        "only a bounded claim may carry a boundary" in item
        for item in result.errors
    )


@pytest.mark.parametrize(
    ("payload", "blocked"),
    [
        (_probe_payload(), False),
        (_probe_payload(question="How was latency measured?", outcome=None), True),
        (_probe_payload(outcome="gap"), True),
        (_probe_payload(outcome="blocking-red-flag"), True),
        (_probe_payload(outcome="explicitly-skipped"), True),
        (
            _probe_payload(
                packet_status="rejected-leakage",
                question=None,
                outcome=None,
            ),
            True,
        ),
        (_probe_payload(packet_status="invalid", question=None, outcome=None), True),
    ],
)
def test_probe_valid_active_closed_and_packet_states(
    payload: dict[str, Any],
    blocked: bool,
) -> None:
    result = validate_reviewer("probe", payload)

    assert result.valid
    assert result.blocks_readiness is blocked


@pytest.mark.parametrize(
    ("payload", "marker"),
    [
        (
            _probe_payload(question=None, outcome=None),
            "active accepted branch requires current_question",
        ),
        (
            _probe_payload(question="Question?", outcome="passed"),
            "closed branch must set current_question to null",
        ),
        (
            _probe_payload(
                packet_status="rejected-leakage",
                question="Leaked question?",
                outcome=None,
            ),
            "non-accepted packet must not emit a question or outcome",
        ),
    ],
)
def test_probe_state_machine_fails_closed(
    payload: dict[str, Any],
    marker: str,
) -> None:
    result = validate_reviewer("probe", payload)

    assert not result.valid
    assert result.blocks_readiness
    assert any(marker in error for error in result.errors)


def test_probe_rejects_missing_unknown_duplicate_and_illegal_values() -> None:
    payload = _probe_payload()
    payload.pop("claim")
    assert not validate_reviewer("probe", payload).valid

    payload = _probe_payload()
    payload["unknown"] = "value"
    assert not validate_reviewer("probe", payload).valid

    payload = _probe_payload()
    payload["target_dimensions"] = ["fact-boundary", "fact-boundary"]
    assert not validate_reviewer("probe", payload).valid

    payload = _probe_payload()
    payload["outcome"] = "ready"
    assert not validate_reviewer("probe", payload).valid


def test_cli_validates_file_and_stdin_with_stable_exit_semantics(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(_evidence_payload("unsupported")),
        encoding="utf-8",
    )

    file_result = runner.invoke(
        app,
        ["skills", "validate-reviewer", "evidence", str(evidence_path)],
    )
    assert file_result.exit_code == 0, file_result.stdout
    assert json.loads(file_result.stdout) == {
        "valid": True,
        "blocks_readiness": True,
        "errors": [],
    }

    stdin_result = runner.invoke(
        app,
        ["skills", "validate-reviewer", "probe", "-"],
        input=json.dumps(_probe_payload()) + "\n",
    )
    assert stdin_result.exit_code == 0, stdin_result.stdout
    assert json.loads(stdin_result.stdout) == {
        "valid": True,
        "blocks_readiness": False,
        "errors": [],
    }


def test_cli_invalid_input_exits_two_without_packet_leakage() -> None:
    runner = CliRunner()
    secret = "SECRET_INTERNAL_PACKET_VALUE"

    invalid_json = runner.invoke(
        app,
        ["skills", "validate-reviewer", "evidence"],
        input=f'{{"secret":"{secret}"',
    )
    assert invalid_json.exit_code == 2
    payload = json.loads(invalid_json.stdout)
    assert payload["valid"] is False
    assert payload["blocks_readiness"] is True
    assert secret not in invalid_json.stdout

    invalid_contract = runner.invoke(
        app,
        ["skills", "validate-reviewer", "unknown"],
        input=json.dumps({"secret": secret}),
    )
    assert invalid_contract.exit_code == 2
    assert secret not in invalid_contract.stdout

    invalid_schema = _evidence_payload()
    invalid_schema["claims"][0]["secret"] = secret
    invalid_output = runner.invoke(
        app,
        ["skills", "validate-reviewer", "evidence"],
        input=json.dumps(invalid_schema),
    )
    assert invalid_output.exit_code == 2
    assert secret not in invalid_output.stdout
