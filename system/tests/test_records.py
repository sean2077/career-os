from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from career_os.checks import _check_host_ref_wikilinks, _check_host_refs
from career_os.config import ProjectPaths
from career_os.records import EngagementEvent, HostRef, load_record, validate_record_envelope
from career_os.records.markdown import extract_markdown_section
from career_os.records.semantics import check_record_semantics
from pydantic import ValidationError


def test_multilingual_record_and_host_reference(tmp_path: Path) -> None:
    record_path = _write_record(
        tmp_path / "经验.md",
        _work(
            "12345678-1234-4234-9234-123456789abc",
            languages=["en", "zh-CN"],
            host_refs=[
                {
                    "relation": "context",
                    "path": "Projects/机器人.md",
                    "anchor": "#Results",
                    "required": True,
                }
            ],
        ),
        "# 机器人数据闭环\n\nSee [[Projects/机器人#Results]].\n",
    )

    record = load_record(record_path)

    assert record.envelope.languages == ["en", "zh-CN"]
    assert record.envelope.host_refs[0].path == "Projects/机器人.md"
    assert "机器人数据闭环" in record.body
    assert all(issue.status == "pass" for issue in _check_host_ref_wikilinks([record]))


@pytest.mark.parametrize("path", ["../secret.md", "/absolute.md", r"Folder\Note.md"])
def test_host_reference_rejects_escaping_or_native_paths(path: str) -> None:
    with pytest.raises(ValidationError):
        HostRef(relation="context", path=path, required=True)


def test_host_reference_resolves_identity_heading_and_block(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    target_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    target = vault / "Projects/Atlas.md"
    target.parent.mkdir()
    target.write_text(
        f"---\nid: {target_id}\n---\n# Experiment notes\n\nResult. ^result-1\n",
        encoding="utf-8",
    )
    record_path = _write_record(
        tmp_path / "record.md",
        _work(
            "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            host_refs=[
                {
                    "relation": "context",
                    "path": "Projects/Atlas.md",
                    "target_id": target_id,
                    "anchor": "#Experiment notes",
                    "required": True,
                },
                {
                    "relation": "result",
                    "path": "Projects/Atlas.md",
                    "anchor": "#^result-1",
                    "required": True,
                },
            ],
        ),
        "See [[Projects/Atlas#Experiment notes]] and [[Projects/Atlas#^result-1]].\n",
    )
    record = load_record(record_path)
    paths = ProjectPaths(
        project_root=tmp_path,
        data_root=tmp_path,
        runtime_root=tmp_path / "runtime",
        build_root=tmp_path / "build",
        local_state_root=tmp_path / ".career-os",
        vault_root=vault,
        mode="embedded",
    )

    assert all(issue.status == "pass" for issue in _check_host_refs(paths, [record]))

    remounted = ProjectPaths(**{**paths.__dict__, "vault_root": tmp_path / "other-vault"})
    issues = _check_host_refs(remounted, [record])
    assert all(issue.status == "fail" for issue in issues)


def test_host_reference_target_identity_must_match_internal_reference(
    tmp_path: Path,
) -> None:
    target_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    source_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    target = _write_record(tmp_path / "target.md", _work(target_id))
    source_payload = _work(
        source_id,
        refs=[{"relation": "context", "target_id": target_id, "required": True}],
        host_refs=[
            {
                "relation": "different-context",
                "path": "target.md",
                "target_id": target_id,
                "required": True,
            }
        ],
    )
    source = _write_record(tmp_path / "source.md", source_payload)

    issues = check_record_semantics([load_record(target), load_record(source)])

    assert any("must match refs relation" in issue.detail for issue in issues)

    source_payload["host_refs"] = [
        {
            "relation": "context",
            "path": "target.md",
            "target_id": target_id,
            "required": True,
        }
    ]
    source = _write_record(tmp_path / "source.md", source_payload)

    issues = check_record_semantics([load_record(target), load_record(source)])

    assert not [issue for issue in issues if "must match refs relation" in issue.detail]


def test_status_history_rejects_forbidden_promotion() -> None:
    payload = _work("11111111-1111-4111-8111-111111111111")
    payload.update(
        {
            "status": "verified",
            "status_history": [
                _transition("draft", "verified", "2026-07-21T00:30:00Z")
            ],
        }
    )

    with pytest.raises(ValidationError, match="forbidden evidence.work transition"):
        validate_record_envelope(payload)


def test_migration_review_has_no_implicit_default() -> None:
    payload = _work("12121212-1212-4212-8212-121212121212")
    payload.pop("migration_review")

    with pytest.raises(ValidationError, match="migration_review"):
        validate_record_envelope(payload)


def test_approved_claim_cannot_promote_a_raw_capture(tmp_path: Path) -> None:
    capture_id = "11111111-1111-4111-8111-111111111111"
    claim_id = "22222222-2222-4222-8222-222222222222"
    capture = _write_record(
        tmp_path / "capture.md",
        {
            **_base(capture_id, "evidence.capture", "ready-to-archive"),
            "source_type": "user-report",
            "captured_at": "2026-07-21T00:00:00Z",
            "provenance": "Synthetic user report.",
            "attribution": "user",
            "sensitivity": "none",
        },
    )
    claim = _write_record(
        tmp_path / "claim.md",
        {
            **_base(claim_id, "evidence.claim", "approved"),
            "visibility": "shareable",
            "allowed_uses": ["resume"],
            "claim_risk": "low",
            "status_history": [
                _transition("draft", "reviewed", "2026-07-21T00:10:00Z"),
                _transition("reviewed", "approved", "2026-07-21T00:20:00Z"),
            ],
            "refs": [
                {"relation": "supported-by", "target_id": capture_id, "required": True}
            ],
        },
    )

    issues = check_record_semantics([load_record(capture), load_record(claim)])

    assert any("raw Captures are insufficient" in issue.detail for issue in issues)


def test_production_evidence_gap_cannot_close_through_retest(tmp_path: Path) -> None:
    assessment_id = "33333333-3333-4333-8333-333333333333"
    gap_id = "44444444-4444-4444-8444-444444444444"
    assessment = _write_record(
        tmp_path / "assessment.md",
        {
            **_base(assessment_id, "readiness.assessment", "assessed"),
            "status_history": [
                _transition("draft", "assessed", "2026-07-21T00:10:00Z")
            ],
            "assessment_type": "retest",
            "result": "pass",
            "reviewer_status": "verified",
            "input_fingerprint": "sha256:synthetic",
        },
    )
    gap = _write_record(
        tmp_path / "gap.md",
        {
            **_base(gap_id, "readiness.gap", "closed"),
            "status_history": [
                _transition("open", "blocked", "2026-07-21T00:10:00Z"),
                _transition("blocked", "closed", "2026-07-21T00:20:00Z"),
            ],
            "gap_type": "production-evidence",
            "target": "Operate a production data loop.",
            "closure_note": "Synthetic retest passed.",
            "refs": [
                {
                    "relation": "closed-by-retest",
                    "target_id": assessment_id,
                    "required": True,
                }
            ],
        },
    )

    issues = check_record_semantics([load_record(assessment), load_record(gap)])

    assert any("formal Work evidence" in issue.detail for issue in issues)


def test_recruiter_contact_does_not_imply_application() -> None:
    event = {
        "id": "55555555-5555-4555-8555-555555555555",
        "event_type": "recruiter-contacted",
        "occurred_at": "2026-07-21T00:10:00Z",
        "source": "user-report",
    }
    payload = {
        **_base(
            "66666666-6666-4666-8666-666666666666",
            "opportunity.engagement",
            "active",
        ),
        "engagement_type": "recruiter-contact",
        "stage": "contacted",
        "application_state": "not-applied",
        "is_current_employment": False,
        "events": [event],
    }

    assert validate_record_envelope(payload).application_state == "not-applied"
    payload["application_state"] = "applied"
    with pytest.raises(ValidationError, match="application-submitted"):
        validate_record_envelope(payload)


def test_engagement_event_preserves_partial_date_precision() -> None:
    payload = {
        "id": "55555555-5555-4555-8555-555555555555",
        "event_type": "employment-started",
        "occurred_at": "2026-02-01T00:00:00+08:00",
        "occurred_at_precision": "month",
        "source": "user-report",
    }

    assert EngagementEvent.model_validate(payload).occurred_at_precision == "month"
    payload["occurred_at"] = "2026-02-02T00:00:00+08:00"
    with pytest.raises(ValidationError, match="first day"):
        EngagementEvent.model_validate(payload)


def test_engagement_rejects_event_order_and_stage_drift() -> None:
    payload = {
        **_base(
            "77777777-7777-4777-8777-777777777777",
            "opportunity.engagement",
            "active",
        ),
        "engagement_type": "offer",
        "stage": "offer",
        "application_state": "accepted",
        "is_current_employment": False,
        "events": [
            {
                "id": "88888888-8888-4888-8888-888888888888",
                "event_type": "offer-accepted",
                "occurred_at": "2026-07-21T00:10:00Z",
                "source": "user-report",
            },
            {
                "id": "99999999-9999-4999-8999-999999999999",
                "event_type": "offer-received",
                "occurred_at": "2026-07-21T00:20:00Z",
                "source": "user-report",
            },
        ],
    }

    with pytest.raises(ValidationError, match="requires an earlier"):
        validate_record_envelope(payload)

    payload["events"] = [payload["events"][1]]
    payload["application_state"] = "offer"
    payload["stage"] = "identified"
    with pytest.raises(ValidationError, match="stage"):
        validate_record_envelope(payload)


def test_current_employment_is_unique_across_engagements(tmp_path: Path) -> None:
    company_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    company = _write_record(
        tmp_path / "company.md",
        {
            **_base(company_id, "opportunity.company", "pending-review"),
            "canonical_name": "Synthetic Company",
            "fact_state": "unknown",
            "refreshed_at": "2026-07-21",
            "freshness_days": 30,
        },
    )
    engagements = []
    for index, record_id in enumerate(
        (
            "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        ),
        start=1,
    ):
        engagements.append(
            _write_record(
                tmp_path / f"employment-{index}.md",
                {
                    **_base(record_id, "opportunity.engagement", "active"),
                    "engagement_type": "employment",
                    "stage": "employed",
                    "application_state": "not-applied",
                    "is_current_employment": True,
                    "events": [
                        {
                            "id": f"dddddddd-dddd-4ddd-8dd{index}-ddddddddddd{index}",
                            "event_type": "employment-started",
                            "occurred_at": f"2026-07-{10 + index:02d}T00:00:00Z",
                            "source": "user-report",
                        }
                    ],
                    "refs": [
                        {"relation": "company", "target_id": company_id, "required": True}
                    ],
                },
            )
        )

    records = [load_record(company), *(load_record(path) for path in engagements)]
    issues = check_record_semantics(records)

    duplicate_current = [
        issue for issue in issues if "current employment must be unique" in issue.detail
    ]
    assert len(duplicate_current) == 2


def test_outlook_cannot_self_promote_to_reviewed() -> None:
    payload = {
        **_base(
            "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
            "outlook.review",
            "reviewed",
        ),
        "status_history": [
            _transition("pending", "reviewed", "2026-07-21T00:10:00Z")
        ],
        "as_of": "2026-07-21",
        "personal_fit": "satisfied",
        "market_revealed": "satisfied",
        "independent_external": "satisfied",
        "confidence": "medium",
        "rationale": "Synthetic three-gate review.",
        "invalidation_conditions": ["A gate no longer holds."],
    }

    with pytest.raises(ValidationError, match="explicit user review"):
        validate_record_envelope(payload)

    payload["review_authority"] = "user"
    assert validate_record_envelope(payload).status == "reviewed"


def test_multilingual_cross_reference_fixture_satisfies_v2_semantics() -> None:
    project_root = Path(__file__).resolve().parents[2]
    fixture_root = project_root / "system/tests/fixtures/records/multilingual-cross-reference"
    records = [
        load_record(path)
        for path in sorted(fixture_root.rglob("*.md"))
    ]

    assert len(records) == 2
    assert not [issue for issue in check_record_semantics(records) if issue.status == "fail"]
    assert not [
        issue
        for issue in _check_host_ref_wikilinks(records)
        if issue.status == "fail"
    ]


def test_jd_source_body_fingerprint_detects_rewrite(tmp_path: Path) -> None:
    original_body = (
        "# Synthetic role\n\n"
        "## JD 原文\n\n"
        "Synthetic immutable JD body.\n\n"
        "## 重新评价\n\n"
        "Synthetic mutable assessment.\n"
    )
    source_body = extract_markdown_section(original_body, "JD 原文")
    path = _write_record(
        tmp_path / "jd.md",
        {
            **_base(
                "ffffffff-ffff-4fff-8fff-ffffffffffff",
                "market.jd",
                "captured",
            ),
            "source_status": "full",
            "source_channel": "synthetic-fixture",
            "captured_at": "2026-07-21T00:00:00Z",
            "missing_sections": [],
            "source_body_sha256": hashlib.sha256(source_body.encode()).hexdigest(),
        },
        original_body,
    )
    assert not check_record_semantics([load_record(path)])

    text = path.read_text(encoding="utf-8").replace("mutable assessment", "changed assessment")
    path.write_text(text, encoding="utf-8")
    assert not check_record_semantics([load_record(path)])

    text = path.read_text(encoding="utf-8").replace("immutable", "changed")
    path.write_text(text, encoding="utf-8")
    issues = check_record_semantics([load_record(path)])

    assert any("JD source body differs" in issue.detail for issue in issues)


def test_jd_screening_state_and_freshness_are_independent(tmp_path: Path) -> None:
    jd_id = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
    source_only_body = "# Synthetic role\n\n## JD 原文\n\nSynthetic source.\n"
    source_hash = hashlib.sha256(
        extract_markdown_section(source_only_body, "JD 原文").encode()
    ).hexdigest()
    source_fields = {
        "source_status": "full",
        "source_channel": "synthetic-fixture",
        "captured_at": "2026-07-21T00:00:00Z",
        "missing_sections": [],
        "source_body_sha256": source_hash,
    }
    captured_payload = {
        **_base(jd_id, "market.jd", "captured"),
        **source_fields,
        "is_stale": True,
    }

    captured = validate_record_envelope(captured_payload)
    captured_path = _write_record(
        tmp_path / "captured.md", captured_payload, source_only_body
    )

    assert captured.status == "captured"
    assert captured.is_stale is True
    assert not check_record_semantics([load_record(captured_path)])

    screened_payload = {
        **_base(jd_id, "market.jd", "screened"),
        **source_fields,
        "status_history": [
            _transition("captured", "screened", "2026-07-21T00:10:00Z")
        ],
        "is_stale": True,
    }
    with pytest.raises(ValidationError, match="screening fields"):
        validate_record_envelope(screened_payload)

    screened_payload.update(
        evidence_fit=4,
        preference="medium",
        priority="p1",
        next_action="candidate",
    )
    screened = validate_record_envelope(screened_payload)
    screened_path = _write_record(
        tmp_path / "screened.md", screened_payload, source_only_body
    )
    issues = check_record_semantics([load_record(screened_path)])

    assert screened.status == "screened"
    assert screened.is_stale is True
    assert any("重新评价" in issue.detail for issue in issues)

    screened_body = (
        source_only_body + "\n## 重新评价\n\nSynthetic screening summary.\n"
    )
    screened_path = _write_record(
        tmp_path / "screened.md", screened_payload, screened_body
    )
    assert not check_record_semantics([load_record(screened_path)])


def test_reviewed_jd_requires_review_date() -> None:
    body = "# Synthetic role\n\n## JD 原文\n\nSynthetic source.\n"
    payload = {
        **_base(
            "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
            "market.jd",
            "reviewed",
        ),
        "status_history": [
            _transition("captured", "screened", "2026-07-21T00:10:00Z"),
            _transition("screened", "reviewed", "2026-07-21T00:20:00Z"),
        ],
        "source_status": "full",
        "source_channel": "synthetic-fixture",
        "captured_at": "2026-07-21T00:00:00Z",
        "missing_sections": [],
        "source_body_sha256": hashlib.sha256(
            extract_markdown_section(body, "JD 原文").encode()
        ).hexdigest(),
        "evidence_fit": 4,
        "preference": "medium",
        "priority": "p1",
        "next_action": "candidate",
    }

    with pytest.raises(ValidationError, match="reviewed_at"):
        validate_record_envelope(payload)

    payload["reviewed_at"] = "2026-07-21"
    assert validate_record_envelope(payload).status == "reviewed"


def test_schema_expand_accepts_market_channel_and_resume_audit() -> None:
    channel = validate_record_envelope(
        {
            **_base(
                "11111111-2222-4333-8444-555555555555",
                "market.channel",
                "active",
            ),
            "rank": 1,
            "tier": "core",
            "role": "Synthetic JD discovery channel.",
            "url": "https://example.invalid/jobs",
            "last_verified_at": "2026-07-22",
        }
    )
    audit = validate_record_envelope(
        {
            **_base(
                "22222222-3333-4444-8555-666666666666",
                "communication.audit",
                "blocked",
            ),
            "status_history": [_transition("draft", "blocked", "2026-07-21T00:30:00Z")],
            "audit_date": "2026-07-21",
            "scope": "full-baseline",
            "career_lane": "shared",
            "source_fingerprint": (
                "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
            ),
            "target_jd_fingerprint": None,
            "evidence_fingerprint": (
                "sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
            ),
            "blocking_findings": 2,
            "confirmation_count": 1,
            "reviewer_status": "complete",
            "user_confirmed": False,
        }
    )

    assert channel.kind == "market.channel"
    assert channel.rank == 1
    assert audit.kind == "communication.audit"
    assert audit.blocking_findings == 2


def test_schema_expand_rejects_invalid_operational_metadata() -> None:
    channel = {
        **_base(
            "23232323-4545-4678-8989-010101010101",
            "market.channel",
            "active",
        ),
        "rank": 0,
        "tier": "core",
        "role": "Synthetic JD discovery channel.",
        "last_verified_at": "2026-07-22",
    }
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        validate_record_envelope(channel)

    company = {
        **_base(
            "34343434-5656-4789-8a8a-121212121212",
            "opportunity.company",
            "pending-review",
        ),
        "canonical_name": "Synthetic Company",
        "fact_state": "unknown",
        "refreshed_at": "2026-07-22",
        "freshness_days": 30,
        "review_status": "reviewed",
    }
    with pytest.raises(ValidationError, match="reviewed_at"):
        validate_record_envelope(company)


def test_schema_expand_preserves_optional_legacy_dimensions() -> None:
    jd = validate_record_envelope(
        {
            **_base(
                "33333333-4444-4555-8666-777777777777",
                "market.jd",
                "captured",
            ),
            "source_status": "full",
            "source_channel": "synthetic-fixture",
            "captured_at": "2026-07-21T00:00:00Z",
            "missing_sections": [],
            "source_body_sha256": "0" * 64,
            "collection": "2026-07",
            "employer_name": "Synthetic Company",
            "location": "Shenzhen",
            "compensation": "synthetic-range",
            "source_origin": "user-provided",
            "recruiting_scope_key": "synthetic-company-experienced",
            "is_stale": True,
            "evidence_fit": 4,
            "preference": "medium",
            "priority": "p1",
            "next_action": "clarify",
            "gaps": ["Synthetic evidence gap."],
            "gap_summary": "Synthetic evidence gap.",
            "direction_key": "ai-agent-platform-harness",
            "career_lane_key": "ai-engineering",
            "user_review_signal": "B boundary check",
            "growth_signal": "high-value challenge",
            "preference_signal": "neutral-positive",
            "next_action_detail": "Clarify team ownership.",
            "duplicate_group": "synthetic-company-agent",
            "case_target": "boundary",
            "review_note": "Preserved source judgment.",
        }
    )
    company = validate_record_envelope(
        {
            **_base(
                "55555555-6666-4777-8888-999999999999",
                "opportunity.company",
                "pending-review",
            ),
            "canonical_name": "Synthetic Company",
            "fact_state": "mixed",
            "refreshed_at": "2026-07-21",
            "freshness_days": 30,
            "watch_state": "target",
            "company_lifecycle": "venture-startup",
            "research_level": "deep",
            "assessment_status": "current",
            "strength": "strong",
            "business_outlook": "positive",
            "employer_quality": "unknown",
            "career_alignment": "positive",
            "risk": "medium",
            "confidence": "medium",
            "trend": "improving",
            "review_status": "reviewed",
            "reviewed_at": "2026-07-21",
            "last_researched_at": "2026-07-21",
            "refresh_due": "2026-08-20",
            "next_action": "Clarify the role boundary.",
        }
    )
    engagement = validate_record_envelope(
        {
            **_base(
                "66666666-7777-4888-8999-aaaaaaaaaaaa",
                "opportunity.engagement",
                "active",
            ),
            "engagement_type": "recruiter-contact",
            "stage": "identified",
            "application_state": "unknown",
            "is_current_employment": False,
            "events": [],
            "decision_state": "clarify",
            "role": "Synthetic role",
            "team": "unknown",
            "started_on": "2026-02-01",
            "review_on": "2026-08",
            "strategy_fit": "positive",
            "opportunity_quality": "unknown",
            "confidence": "low",
            "review_status": "pending",
            "reviewed_at": None,
            "next_action": "Ask for a complete JD.",
        }
    )

    assert jd.collection == "2026-07"
    assert jd.direction_key == "ai-agent-platform-harness"
    assert jd.preference_signal == "neutral-positive"
    assert jd.is_stale is True
    assert company.watch_state == "target"
    assert engagement.decision_state == "clarify"
    assert engagement.started_on == "2026-02-01"
    assert engagement.application_state == "unknown"


def test_schema_expand_preserves_readiness_inputs_without_inferring_readiness() -> None:
    story = validate_record_envelope(
        {
            **_base(
                "77777777-8888-4999-8aaa-bbbbbbbbbbbb",
                "evidence.story",
                "draft",
            ),
            "sensitive_boundary": "Synthetic internal detail.",
            "story_role": "primary",
            "readiness_state": "content-ready",
        }
    )
    gap = validate_record_envelope(
        {
            **_base(
                "88888888-9999-4aaa-8bbb-cccccccccccc",
                "readiness.gap",
                "open",
            ),
            "gap_type": "knowledge",
            "target": "Explain a synthetic mechanism.",
            "priority": "p1",
        }
    )
    session = validate_record_envelope(
        {
            **_base(
                "99999999-aaaa-4bbb-8ccc-dddddddddddd",
                "readiness.session",
                "planned",
            ),
            "session_type": "strict",
            "outcome": "unscored",
            "reviewer_status": "missing",
            "session_date": "2026-07-22",
            "target": "jd",
            "scope": "system-design",
            "attempt": 0,
            "fact_boundary": "strong",
            "technical_depth": "ready",
            "answer_structure": "ready",
            "tradeoff_resilience": "strong",
            "blocking_red_flag": False,
            "verdict": "unscored",
        }
    )

    assert story.story_role == "primary"
    assert gap.priority == "p1"
    assert session.verdict == "unscored"
    assert session.outcome == "unscored"


def test_jd_direction_key_requires_direction_authority_ref(tmp_path: Path) -> None:
    jd_id = "12121212-3434-4567-8787-909090909090"
    direction_id = "45454545-6767-4890-8b8b-232323232323"
    body = "# Synthetic role\n\n## JD 原文\n\nSynthetic source.\n"
    payload = {
        **_base(jd_id, "market.jd", "captured"),
        "source_status": "full",
        "source_channel": "synthetic-fixture",
        "captured_at": "2026-07-21T00:00:00Z",
        "missing_sections": [],
        "source_body_sha256": hashlib.sha256(
            extract_markdown_section(body, "JD 原文").encode()
        ).hexdigest(),
        "direction_key": "ai-agent-platform-harness",
    }
    jd = _write_record(
        tmp_path / "jd.md",
        payload,
        body,
    )

    issues = check_record_semantics([load_record(jd)])

    assert any("market-direction" in issue.detail for issue in issues)

    direction = _write_record(
        tmp_path / "direction.md",
        {
            **_base(direction_id, "market.direction", "candidate"),
            "review_on": "2026-08-22",
        },
    )
    payload["refs"] = [
        {"relation": "market-direction", "target_id": direction_id, "required": True}
    ]
    jd = _write_record(tmp_path / "jd.md", payload, body)

    issues = check_record_semantics([load_record(direction), load_record(jd)])

    assert not [issue for issue in issues if "market-direction" in issue.detail]


def test_engagement_decision_dimensions_cannot_bypass_event_derived_application() -> None:
    payload = {
        **_base(
            "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
            "opportunity.engagement",
            "active",
        ),
        "engagement_type": "application",
        "stage": "applied",
        "application_state": "applied",
        "is_current_employment": False,
        "events": [],
        "decision_state": "apply-recommended",
        "opportunity_quality": "strong",
    }

    with pytest.raises(ValidationError, match="application-submitted"):
        validate_record_envelope(payload)


def _base(record_id: str, kind: str, status: str) -> dict[str, object]:
    return {
        "id": record_id,
        "kind": kind,
        "schema_version": 2,
        "created_at": "2026-07-21T00:00:00Z",
        "updated_at": "2026-07-21T01:00:00Z",
        "status": status,
        "refs": [],
        "host_refs": [],
        "migration_review": "not-applicable",
    }


def _work(record_id: str, **updates: object) -> dict[str, object]:
    payload = {
        **_base(record_id, "evidence.work", "draft"),
        "contribution_scope": "individual",
        "evidence_strength": "medium",
        "evidence_summary": "Synthetic evidence.",
    }
    payload.update(updates)
    return payload


def _transition(from_status: str, to_status: str, at: str) -> dict[str, object]:
    return {
        "from_status": from_status,
        "to_status": to_status,
        "at": at,
        "reason": "Synthetic transition.",
        "evidence_ref_ids": [],
    }


def _write_record(
    path: Path, envelope: dict[str, object], body: str = "Synthetic record.\n"
) -> Path:
    path.write_text(
        "---\n" + json.dumps(envelope, indent=2, ensure_ascii=False) + "\n---\n" + body,
        encoding="utf-8",
    )
    return path
