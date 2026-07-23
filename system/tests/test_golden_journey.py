from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from career_os.checks import _check_host_ref_wikilinks, _check_host_refs
from career_os.cli import app
from career_os.config import resolve_paths
from career_os.records import load_record
from career_os.records.markdown import extract_markdown_section
from career_os.records.semantics import check_record_semantics
from typer.testing import CliRunner

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CREATED_AT = "2026-07-23T00:00:00Z"
UPDATED_AT = "2026-07-23T01:00:00Z"

IDS = {
    "work": "11111111-1111-4111-8111-111111111111",
    "claim": "22222222-2222-4222-8222-222222222222",
    "lane": "33333333-3333-4333-8333-333333333333",
    "channel": "44444444-4444-4444-8444-444444444444",
    "direction": "55555555-5555-4555-8555-555555555555",
    "jd": "66666666-6666-4666-8666-666666666666",
    "company": "77777777-7777-4777-8777-777777777777",
    "scope": "88888888-8888-4888-8888-888888888888",
    "engagement": "99999999-9999-4999-8999-999999999999",
    "decision": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "signal": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    "outlook_review": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    "assessment": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    "gap": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    "profile": "ffffffff-ffff-4fff-8fff-ffffffffffff",
    "audit": "12121212-3434-4567-8787-909090909090",
    "resume": "23232323-4545-4678-8989-010101010101",
    "export": "34343434-5656-4789-8a8a-121212121212",
}

PATHS = {
    "work": "10-career-evidence/work.md",
    "claim": "10-career-evidence/claim.md",
    "lane": "20-career-strategy/lane.md",
    "channel": "30-role-market/channel.md",
    "direction": "30-role-market/direction.md",
    "jd": "30-role-market/jd.md",
    "company": "40-opportunity-decision/company.md",
    "scope": "40-opportunity-decision/scope.md",
    "engagement": "40-opportunity-decision/engagement.md",
    "decision": "40-opportunity-decision/decision.md",
    "signal": "50-career-outlook/signal.md",
    "outlook_review": "50-career-outlook/review.md",
    "assessment": "60-capability-readiness/retest.md",
    "gap": "60-capability-readiness/gap.md",
    "profile": "70-career-communication/profile.md",
    "audit": "70-career-communication/audit.md",
    "resume": "70-career-communication/resume.md",
    "export": "70-career-communication/export.md",
}


def test_clean_install_golden_journey_spans_all_seven_authorities(
    tmp_path: Path,
) -> None:
    project = tmp_path / "career-os"
    _copy_framework(project)
    runner = CliRunner()
    arguments = [
        "init",
        "--mode",
        "standalone",
        "--root",
        str(project),
        "--languages",
        "en,zh-CN",
    ]

    first = runner.invoke(app, arguments)
    second = runner.invoke(app, arguments)

    assert first.exit_code == 0, first.stdout
    assert second.exit_code == 0, second.stdout
    assert json.loads(first.stdout)["created"]
    assert json.loads(second.stdout)["created"] == []

    record_paths = _write_golden_graph(project / "career")
    records = [load_record(path) for path in record_paths]
    by_id = {str(record.envelope.id): record for record in records}

    assert len(records) == len(IDS)
    assert {record.envelope.kind.split(".", maxsplit=1)[0] for record in records} == {
        "evidence",
        "strategy",
        "market",
        "opportunity",
        "outlook",
        "readiness",
        "communication",
    }
    assert all(
        str(reference.target_id) in by_id
        for record in records
        for reference in record.envelope.refs
    )
    assert not check_record_semantics(records)

    paths = resolve_paths(project)
    assert not [
        issue for issue in _check_host_refs(paths, records) if issue.status == "fail"
    ]
    assert not [
        issue
        for issue in _check_host_ref_wikilinks(records)
        if issue.status == "fail"
    ]

    views = runner.invoke(app, ["views", "build", "--root", str(project)])
    assert views.exit_code == 0, views.stdout
    projection = json.loads(views.stdout)
    assert projection["homepage"] == str(project / "Home.md")
    assert projection["homepages"] == [
        str(project / "Home.md"),
        str(project / "主页.md"),
    ]
    assert len(projection["assets"]) == 16
    assert projection["generated"] == []
    assert not list(project.joinpath("career").rglob("*.base"))

    assert by_id[IDS["work"]].envelope.status == "verified"
    assert by_id[IDS["claim"]].envelope.status == "approved"
    assert by_id[IDS["lane"]].envelope.status == "accepted"
    assert by_id[IDS["jd"]].envelope.status == "reviewed"
    assert by_id[IDS["engagement"]].envelope.application_state == "not-applied"
    assert by_id[IDS["gap"]].envelope.status == "closed"
    assert by_id[IDS["resume"]].envelope.status == "validated"
    assert by_id[IDS["export"]].envelope.profile == "preview"


def _copy_framework(project: Path) -> None:
    project.mkdir()
    shutil.copy2(REPOSITORY_ROOT / "career-os.toml", project / "career-os.toml")
    shutil.copy2(REPOSITORY_ROOT / "Home.md", project / "Home.md")
    shutil.copy2(REPOSITORY_ROOT / "主页.md", project / "主页.md")
    shutil.copytree(REPOSITORY_ROOT / "system/seeds", project / "system/seeds")
    shutil.copytree(REPOSITORY_ROOT / "system/obsidian", project / "system/obsidian")


def _write_golden_graph(data_root: Path) -> list[Path]:
    jd_body = (
        "# Fictional Agent Systems Engineer\n\n"
        "## JD 原文\n\n"
        "Build local-first tools for a fictional robotics laboratory.\n\n"
        "## 重新评价\n\n"
        "Strong evidence fit; keep the opportunity at candidate priority.\n"
    )
    source_hash = hashlib.sha256(
        extract_markdown_section(jd_body, "JD 原文").encode("utf-8")
    ).hexdigest()
    records: dict[str, tuple[dict[str, object], str]] = {
        "work": (
            {
                **_base("work", "evidence.work", "verified"),
                "visibility": "private",
                "contribution_scope": "individual",
                "evidence_strength": "strong",
                "evidence_summary": "Synthetic grounded work evidence.",
                "status_history": [
                    _transition("draft", "grounded", "00:10"),
                    _transition("grounded", "verified", "00:20"),
                ],
            },
            "Synthetic work used only by the golden journey.\n",
        ),
        "claim": (
            {
                **_base("claim", "evidence.claim", "approved"),
                "visibility": "shareable",
                "allowed_uses": ["resume"],
                "claim_risk": "low",
                "status_history": [
                    _transition("draft", "reviewed", "00:10"),
                    _transition("reviewed", "approved", "00:20"),
                ],
                **_relations(("supported-by", "work")),
            },
            "Synthetic approved claim.\n",
        ),
        "lane": (
            {
                **_base("lane", "strategy.lane", "accepted"),
                "confidence": "high",
                "review_on": "2026-10-23",
                "disconfirming_signals": ["Synthetic demand disappears."],
                "status_history": [
                    _transition("candidate", "reviewed", "00:10"),
                    _transition("reviewed", "accepted", "00:20"),
                ],
                **_relations(("supported-by-outlook", "outlook_review")),
            },
            "Accepted fictional Agent systems lane.\n",
        ),
        "channel": (
            {
                **_base("channel", "market.channel", "active"),
                "rank": 1,
                "tier": "core",
                "role": "Synthetic role discovery channel.",
                "url": "https://example.invalid/jobs",
                "last_verified_at": "2026-07-23",
            },
            "Active synthetic recruiting channel.\n",
        ),
        "direction": (
            {
                **_base("direction", "market.direction", "active"),
                "review_on": "2026-10-23",
                "status_history": [
                    _transition("candidate", "reviewed", "00:10"),
                    _transition("reviewed", "active", "00:20"),
                ],
                **_relations(("career-lane", "lane")),
            },
            "Active synthetic market direction.\n",
        ),
        "jd": (
            {
                **_base("jd", "market.jd", "reviewed"),
                "source_status": "full",
                "source_channel": "synthetic-fixture",
                "source_url": "https://example.invalid/jobs/agent-systems",
                "captured_at": CREATED_AT,
                "missing_sections": [],
                "source_body_sha256": source_hash,
                "evidence_fit": 5,
                "preference": "high",
                "priority": "p1",
                "next_action": "candidate",
                "direction_key": "fictional-agent-systems",
                "career_lane_key": "agent-systems",
                "reviewed_at": "2026-07-23",
                "status_history": [
                    _transition("captured", "screened", "00:10"),
                    _transition("screened", "reviewed", "00:20"),
                ],
                **_relations(
                    ("source-channel", "channel"),
                    ("market-direction", "direction"),
                    ("career-lane", "lane"),
                ),
            },
            jd_body,
        ),
        "company": (
            {
                **_base("company", "opportunity.company", "reviewed"),
                "canonical_name": "Northstar Fictional Labs",
                "fact_state": "fact",
                "refreshed_at": "2026-07-23",
                "freshness_days": 30,
                "review_status": "reviewed",
                "reviewed_at": "2026-07-23",
                "status_history": [
                    _transition("pending-review", "reviewed", "00:10"),
                ],
            },
            "Reviewed fictional company.\n",
        ),
        "scope": (
            {
                **_base("scope", "opportunity.scope", "verified"),
                "team": "Agent Systems",
                "role": "Platform Engineer",
                "location": "Remote",
                "channel": "synthetic-fixture",
                "status_history": [
                    _transition("draft", "verified", "00:10"),
                ],
                **_relations(("company", "company")),
            },
            "Verified fictional recruiting scope.\n",
        ),
        "engagement": (
            {
                **_base("engagement", "opportunity.engagement", "active"),
                "engagement_type": "recruiter-contact",
                "stage": "scoped",
                "application_state": "not-applied",
                "is_current_employment": False,
                "events": [],
                "decision_state": "hold",
                "review_status": "reviewed",
                "reviewed_at": "2026-07-23",
                **_relations(
                    ("company", "company"),
                    ("recruiting-scope", "scope"),
                    ("target-jd", "jd"),
                ),
            },
            "Reviewed fictional engagement with no application event.\n",
        ),
        "decision": (
            {
                **_base("decision", "opportunity.decision", "decided"),
                "decision": "hold",
                "rationale": "Remain not-applied while clarifying scope.",
                "review_on": "2026-08-23",
                "triggers": ["Scope becomes explicit."],
                "status_history": [
                    _transition("draft", "reviewed", "00:10"),
                    _transition("reviewed", "decided", "00:20"),
                ],
                **_relations(("engagement", "engagement")),
            },
            "Decision remains explicitly not-applied.\n",
        ),
        "signal": (
            {
                **_base("signal", "outlook.signal", "verified"),
                "source_class": "technology",
                "event_date": "2026-07-22",
                "published_at": "2026-07-22",
                "retrieved_at": "2026-07-23",
                "source_url": "https://example.invalid/research",
                "status_history": [
                    _transition("captured", "verified", "00:10"),
                ],
            },
            "Verified fictional external signal.\n",
        ),
        "outlook_review": (
            {
                **_base("outlook_review", "outlook.review", "reviewed"),
                "as_of": "2026-07-23",
                "personal_fit": "satisfied",
                "market_revealed": "satisfied",
                "independent_external": "satisfied",
                "confidence": "medium",
                "rationale": "Three synthetic signal classes agree.",
                "invalidation_conditions": ["The synthetic JD is withdrawn."],
                "review_authority": "user",
                "status_history": [
                    _transition("pending", "reviewed", "00:20"),
                ],
                **_relations(
                    ("personal-fit", "work"),
                    ("market-revealed", "jd"),
                    ("independent-external", "signal"),
                ),
            },
            "Reviewed fictional outlook.\n",
        ),
        "assessment": (
            {
                **_base("assessment", "readiness.assessment", "assessed"),
                "assessment_type": "retest",
                "result": "pass",
                "reviewer_status": "verified",
                "input_fingerprint": "sha256:golden-journey-retest",
                "status_history": [
                    _transition("draft", "assessed", "00:10"),
                ],
            },
            "Verified passing synthetic Retest.\n",
        ),
        "gap": (
            {
                **_base("gap", "readiness.gap", "closed"),
                "gap_type": "practice",
                "target": "Explain the fictional recovery mechanism.",
                "closure_note": "Verified synthetic Retest passed.",
                "priority": "p1",
                "status_history": [
                    _transition("open", "practice", "00:05"),
                    _transition("practice", "retest", "00:10"),
                    _transition("retest", "closed", "00:20"),
                ],
                **_relations(("closed-by-retest", "assessment")),
            },
            "Closed fictional practice gap.\n",
        ),
        "profile": (
            {
                **_base("profile", "communication.profile", "approved"),
                "audience": "synthetic preview",
                "identity_policy": "preview",
                "status_history": [
                    _transition("draft", "approved", "00:10"),
                ],
            },
            "Approved preview-only synthetic profile.\n",
        ),
        "audit": (
            {
                **_base("audit", "communication.audit", "reviewed"),
                "audit_date": "2026-07-23",
                "scope": "golden-journey-preview",
                "career_lane": "agent-systems",
                "source_fingerprint": f"sha256:{'1' * 64}",
                "target_jd_fingerprint": f"sha256:{source_hash}",
                "evidence_fingerprint": f"sha256:{'2' * 64}",
                "blocking_findings": 0,
                "confirmation_count": 1,
                "reviewer_status": "complete",
                "user_confirmed": True,
                "status_history": [
                    _transition("draft", "reviewed", "00:10"),
                ],
                **_relations(
                    ("audits-profile", "profile"),
                    ("audits-claim", "claim"),
                    ("target-jd", "jd"),
                ),
            },
            "Reviewed synthetic communication audit.\n",
        ),
        "resume": (
            {
                **_base("resume", "communication.resume", "validated"),
                "root_name": "en",
                "audience": "synthetic preview",
                "export_policy": "preview",
                "status_history": [
                    _transition("draft", "validated", "00:10"),
                ],
                **_relations(
                    ("uses-claim", "claim"),
                    ("identity-profile", "profile"),
                    ("reviewed-by", "audit"),
                ),
            },
            "Validated synthetic preview Resume.\n",
        ),
        "export": (
            {
                **_base("export", "communication.export", "generated"),
                "profile": "preview",
                "authorization": "explicit",
                "artifact_sha256": "3" * 64,
                "status_history": [
                    _transition("planned", "generated", "00:10"),
                ],
                **_relations(("export-of", "resume")),
            },
            "Synthetic preview export receipt.\n",
        ),
    }

    written: list[Path] = []
    for key, (envelope, body) in records.items():
        links = _wikilinks(envelope)
        if links:
            body = body.rstrip() + "\n\n## Related\n\n" + links + "\n"
        path = data_root / PATHS[key]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\n"
            + json.dumps(envelope, indent=2, ensure_ascii=False)
            + "\n---\n"
            + body,
            encoding="utf-8",
            newline="\n",
        )
        written.append(path)
    return written


def _base(key: str, kind: str, status: str) -> dict[str, object]:
    return {
        "id": IDS[key],
        "kind": kind,
        "schema_version": 2,
        "created_at": CREATED_AT,
        "updated_at": UPDATED_AT,
        "title": f"Synthetic {key.replace('_', ' ')}",
        "status": status,
        "refs": [],
        "host_refs": [],
        "migration_review": "not-applicable",
    }


def _transition(from_status: str, to_status: str, time: str) -> dict[str, object]:
    return {
        "from_status": from_status,
        "to_status": to_status,
        "at": f"2026-07-23T{time}:00Z",
        "reason": "Synthetic golden-journey transition.",
        "evidence_ref_ids": [],
    }


def _relations(*relations: tuple[str, str]) -> dict[str, object]:
    refs = []
    host_refs = []
    for relation, target in relations:
        refs.append(
            {
                "relation": relation,
                "target_id": IDS[target],
                "required": True,
            }
        )
        host_refs.append(
            {
                "relation": relation,
                "path": f"career/{PATHS[target]}",
                "target_id": IDS[target],
                "required": True,
            }
        )
    return {"refs": refs, "host_refs": host_refs}


def _wikilinks(envelope: dict[str, object]) -> str:
    host_refs = envelope.get("host_refs", [])
    assert isinstance(host_refs, list)
    return "\n".join(
        f"- [[{reference['path']}|{reference['relation']}]]"
        for reference in host_refs
        if isinstance(reference, dict)
    )
