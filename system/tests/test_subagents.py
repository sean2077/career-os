from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parents[2]
SUBAGENT_ROOT = PROJECT_ROOT / ".agents/subagents"
EXPECTED_SUBAGENTS = {
    "blind-interviewer",
    "career-strategy-advisor",
    "evidence-auditor",
}


def _read_agent(name: str) -> tuple[dict[str, Any], str]:
    root = SUBAGENT_ROOT / name
    return (
        json.loads((root / "metadata.json").read_text(encoding="utf-8")),
        (root / "instructions.md").read_text(encoding="utf-8"),
    )


def test_exact_subagent_inventory_is_read_only_and_model_unpinned() -> None:
    actual = {path.name for path in SUBAGENT_ROOT.iterdir() if path.is_dir()}
    assert actual == EXPECTED_SUBAGENTS

    for name in EXPECTED_SUBAGENTS:
        metadata, _ = _read_agent(name)
        assert metadata["name"] == name
        assert metadata["codex"]["sandbox_mode"] == "read-only"
        assert metadata["codex"]["model_reasoning_effort"] == "high"
        assert metadata["codex"]["nickname_candidates"]
        assert "model" not in metadata["codex"]
        assert "model" not in metadata.get("claude", {})


def test_blind_interviewer_enforces_public_packet_isolation() -> None:
    metadata, instructions = _read_agent("blind-interviewer")
    assert "claude" not in metadata
    for marker in (
        "Use only the Public Interview Packet",
        "Do not call tools",
        "Internal Evidence Packet",
        "rejected-leakage",
        "resume-interview-probe/1",
        "never exceed six",
        "passed",
        "gap",
        "blocking-red-flag",
        "explicitly-skipped",
    ):
        assert marker in instructions


def test_evidence_auditor_is_internal_packet_only_and_report_only() -> None:
    _metadata, instructions = _read_agent("evidence-auditor")
    for marker in (
        "Review only the supplied Internal Evidence Packet",
        "resume-evidence-audit/1",
        "supported",
        "bounded",
        "needs-confirmation",
        "unsupported",
        "conflicting/stale",
        "never repair",
        "Never create, edit, move, rename, or delete",
    ):
        assert marker in instructions


def test_strategy_advisor_uses_current_authorities_without_route_pins() -> None:
    _metadata, instructions = _read_agent("career-strategy-advisor")
    for marker in (
        "fact",
        "inference",
        "recommendation",
        "unknown",
        "as_of",
        "Career Strategy",
        "Career Outlook",
        "Role Market",
        "Opportunity Decision",
        "Capability Readiness",
        "pending-review",
    ):
        assert marker in instructions
    for obsolete in (
        "$career-model",
        "$plan-review",
        "$jd-screening",
        "$company-model",
        "robotics engineering + Agent engineering",
    ):
        assert obsolete not in instructions


def test_subagent_prompts_do_not_restore_retired_reviewer_commands() -> None:
    prompts = "\n".join(
        _read_agent(name)[1] for name in sorted(EXPECTED_SUBAGENTS)
    )
    assert "validate_reviewer_output.py" not in prompts
    assert "uv run --locked obsidian-content" not in prompts


def test_all_six_host_projections_are_generated_and_in_sync() -> None:
    assert {
        path.stem for path in (PROJECT_ROOT / ".claude/agents").glob("*.md")
    } == EXPECTED_SUBAGENTS
    assert {
        path.stem for path in (PROJECT_ROOT / ".codex/agents").glob("*.toml")
    } == EXPECTED_SUBAGENTS

    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / ".agents/tools/generate-subagents.py"),
            "--check",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "6 file(s) in sync (3 subagent(s))" in completed.stdout
