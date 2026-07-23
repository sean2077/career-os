from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from career_os.records.frontmatter import ParsedRecord
from career_os.records.markdown import extract_markdown_section
from career_os.records.models import (
    CommunicationExport,
    CommunicationResume,
    EvidenceCapture,
    EvidenceClaim,
    EvidenceStory,
    EvidenceWork,
    MarketChannel,
    MarketJD,
    OpportunityDecision,
    OpportunityEngagement,
    OpportunityScope,
    OutlookReview,
    OutlookThesis,
    ReadinessAssessment,
    ReadinessGap,
    ReadinessNote,
)


@dataclass(frozen=True)
class RecordSemanticIssue:
    status: str
    path: Path
    detail: str


def check_record_semantics(records: list[ParsedRecord]) -> list[RecordSemanticIssue]:
    by_id = {record.envelope.id: record for record in records}
    issues: list[RecordSemanticIssue] = []
    current_employment: list[ParsedRecord] = []

    for record in records:
        envelope = record.envelope
        _check_host_ref_internal_ref_parity(issues, record)
        referenced_ids = {reference.target_id for reference in envelope.refs}
        for transition in envelope.status_history:
            for evidence_id in transition.evidence_ref_ids:
                if evidence_id not in by_id:
                    _fail(
                        issues,
                        record,
                        f"status transition evidence record is missing: {evidence_id}",
                    )
                elif evidence_id not in referenced_ids:
                    _fail(
                        issues,
                        record,
                        f"status transition evidence must also be an internal ref: {evidence_id}",
                    )
        if envelope.migration_review == "required":
            issues.append(
                RecordSemanticIssue(
                    "attention",
                    record.path,
                    "source-migrated record requires a human semantic review",
                )
            )
        if isinstance(envelope, EvidenceCapture) and envelope.status == "archived":
            _require_targets(
                issues,
                record,
                by_id,
                "represented-by",
                {"evidence.work"},
                allowed_statuses={"grounded", "verified"},
            )
        elif isinstance(envelope, EvidenceStory) and envelope.status == "reviewed":
            _require_targets(
                issues,
                record,
                by_id,
                "derived-from",
                {"evidence.work"},
                allowed_statuses={"grounded", "verified"},
            )
        elif isinstance(envelope, EvidenceClaim) and envelope.status == "approved":
            _check_approved_claim(issues, record, by_id, envelope)
        elif envelope.kind.startswith("strategy."):
            _check_strategy_outlook_refs(issues, record, by_id)
        elif isinstance(envelope, MarketJD):
            try:
                source_body = extract_markdown_section(record.body, "JD 原文")
            except ValueError as error:
                _fail(issues, record, str(error))
                continue
            actual = hashlib.sha256(source_body.encode("utf-8")).hexdigest()
            if actual != envelope.source_body_sha256:
                _fail(issues, record, "JD source body differs from its preserved SHA-256")
            if envelope.status in {"screened", "reviewed"}:
                try:
                    extract_markdown_section(record.body, "重新评价")
                except ValueError as error:
                    _fail(issues, record, str(error))
            if envelope.direction_key is not None:
                _require_targets(
                    issues,
                    record,
                    by_id,
                    "market-direction",
                    {"market.direction"},
                )
            if envelope.career_lane_key is not None:
                _require_targets(
                    issues,
                    record,
                    by_id,
                    "career-lane",
                    {"strategy.lane"},
                )
            if envelope.recruiting_scope_key is not None:
                _require_targets(
                    issues,
                    record,
                    by_id,
                    "recruiting-scope",
                    {"opportunity.scope"},
                )
        elif isinstance(envelope, MarketChannel) and any(
            reference.required and reference.relation == "career-lane"
            for reference in envelope.refs
        ):
            _require_targets(
                issues,
                record,
                by_id,
                "career-lane",
                {"strategy.lane"},
            )
        elif isinstance(envelope, OpportunityScope) and envelope.status in {
            "verified",
            "conservative",
        }:
            _require_targets(
                issues, record, by_id, "company", {"opportunity.company"}
            )
        elif isinstance(envelope, OpportunityEngagement):
            _check_engagement(issues, record, by_id, envelope)
            if envelope.is_current_employment:
                current_employment.append(record)
        elif isinstance(envelope, OpportunityDecision) and envelope.status == "decided":
            _require_targets(
                issues,
                record,
                by_id,
                "engagement",
                {"opportunity.engagement"},
            )
        elif isinstance(envelope, OutlookReview) and envelope.status == "reviewed":
            _check_review_signal_gate(issues, record, by_id)
        elif isinstance(envelope, OutlookThesis) and envelope.status == "reviewed":
            _require_targets(
                issues,
                record,
                by_id,
                "derived-from-review",
                {"outlook.review"},
                allowed_statuses={"reviewed"},
            )
        elif isinstance(envelope, ReadinessGap) and envelope.status == "closed":
            _check_closed_gap(issues, record, by_id, envelope)
        elif isinstance(envelope, ReadinessNote) and envelope.status == "reviewed":
            _require_targets(
                issues, record, by_id, "target-gap", {"readiness.gap"}
            )
        elif isinstance(envelope, CommunicationResume) and envelope.status in {
            "validated",
            "application-ready",
        }:
            _check_communication_resume(issues, record, by_id, envelope)
        elif isinstance(envelope, CommunicationExport) and envelope.status in {
            "generated",
            "released",
        }:
            _check_communication_export(issues, record, by_id, envelope)

    if len(current_employment) > 1:
        paths = ", ".join(str(record.path) for record in current_employment)
        for record in current_employment:
            issues.append(
                RecordSemanticIssue(
                    "fail",
                    record.path,
                    f"current employment must be unique; active records: {paths}",
                )
            )
    return issues


def _check_host_ref_internal_ref_parity(
    issues: list[RecordSemanticIssue], record: ParsedRecord
) -> None:
    internal_refs = {
        (reference.relation, reference.target_id, reference.required)
        for reference in record.envelope.refs
    }
    for host_ref in record.envelope.host_refs:
        if host_ref.target_id is None:
            continue
        expected = (host_ref.relation, host_ref.target_id, host_ref.required)
        if expected not in internal_refs:
            _fail(
                issues,
                record,
                "host_ref with target_id must match refs relation, target_id, and required: "
                f"{host_ref.relation} -> {host_ref.target_id}",
            )


def _check_approved_claim(
    issues: list[RecordSemanticIssue],
    record: ParsedRecord,
    by_id: dict[UUID, ParsedRecord],
    envelope: EvidenceClaim,
) -> None:
    if envelope.visibility not in {"shareable", "public"}:
        _fail(issues, record, "approved claims must be shareable or public")
    if not set(envelope.allowed_uses) - {"internal"}:
        _fail(issues, record, "approved claims require at least one external allowed use")
    targets = _required_relation_targets(record, by_id, "supported-by")
    supported = any(
        (
            isinstance(target.envelope, EvidenceWork)
            and target.envelope.status in {"grounded", "verified"}
        )
        or (
            isinstance(target.envelope, EvidenceStory)
            and target.envelope.status == "reviewed"
        )
        for target in targets
    )
    if not supported:
        _fail(
            issues,
            record,
            "approved claims require a grounded Work or reviewed Story; "
            "raw Captures are insufficient",
        )


def _check_strategy_outlook_refs(
    issues: list[RecordSemanticIssue],
    record: ParsedRecord,
    by_id: dict[UUID, ParsedRecord],
) -> None:
    for target in _all_targets(record, by_id):
        if (
            target.envelope.kind in {"outlook.review", "outlook.thesis"}
            and target.envelope.status != "reviewed"
        ):
            _fail(
                issues,
                record,
                f"Strategy cannot consume pending outlook authority: {target.envelope.id}",
            )


def _check_engagement(
    issues: list[RecordSemanticIssue],
    record: ParsedRecord,
    by_id: dict[UUID, ParsedRecord],
    envelope: OpportunityEngagement,
) -> None:
    _require_targets(issues, record, by_id, "company", {"opportunity.company"})
    if envelope.application_state not in {"not-applied", "unknown"}:
        _require_targets(issues, record, by_id, "target-jd", {"market.jd"})


def _check_review_signal_gate(
    issues: list[RecordSemanticIssue],
    record: ParsedRecord,
    by_id: dict[UUID, ParsedRecord],
) -> None:
    _require_targets(
        issues,
        record,
        by_id,
        "personal-fit",
        {"evidence.work", "evidence.story", "strategy.positioning", "strategy.lane"},
    )
    _require_targets(
        issues,
        record,
        by_id,
        "market-revealed",
        {"market.jd", "opportunity.engagement"},
    )
    _require_targets(
        issues,
        record,
        by_id,
        "independent-external",
        {"outlook.signal"},
        allowed_statuses={"verified"},
    )


def _check_closed_gap(
    issues: list[RecordSemanticIssue],
    record: ParsedRecord,
    by_id: dict[UUID, ParsedRecord],
    envelope: ReadinessGap,
) -> None:
    if not envelope.closure_note:
        _fail(issues, record, "closed readiness gaps require closure_note")
    if envelope.gap_type in {"knowledge", "practice"}:
        targets = _required_relation_targets(record, by_id, "closed-by-retest")
        valid = any(
            isinstance(target.envelope, ReadinessAssessment)
            and target.envelope.status == "assessed"
            and target.envelope.assessment_type == "retest"
            and target.envelope.result == "pass"
            and target.envelope.reviewer_status == "verified"
            for target in targets
        )
        if not valid:
            _fail(
                issues,
                record,
                "knowledge and practice gaps close only through a verified passing Retest",
            )
        return
    targets = _required_relation_targets(record, by_id, "closed-by-evidence")
    valid = any(
        isinstance(target.envelope, EvidenceWork)
        and target.envelope.status in {"grounded", "verified"}
        and target.envelope.evidence_strength in {"medium", "strong"}
        for target in targets
    )
    if not valid:
        _fail(
            issues,
            record,
            "production-evidence gaps close only through medium or strong formal Work evidence",
        )


def _check_communication_resume(
    issues: list[RecordSemanticIssue],
    record: ParsedRecord,
    by_id: dict[UUID, ParsedRecord],
    envelope: CommunicationResume,
) -> None:
    claims = _required_relation_targets(record, by_id, "uses-claim")
    if not claims or any(
        not isinstance(target.envelope, EvidenceClaim)
        or target.envelope.status != "approved"
        for target in claims
    ):
        _fail(issues, record, "validated resumes may use only approved Claim records")
    if envelope.status == "application-ready":
        if envelope.export_policy != "application":
            _fail(issues, record, "application-ready resumes require application export_policy")
        _require_targets(
            issues,
            record,
            by_id,
            "target-jd",
            {"market.jd"},
            allowed_statuses={"reviewed"},
        )


def _check_communication_export(
    issues: list[RecordSemanticIssue],
    record: ParsedRecord,
    by_id: dict[UUID, ParsedRecord],
    envelope: CommunicationExport,
) -> None:
    resumes = _required_relation_targets(record, by_id, "export-of")
    if not resumes or any(
        not isinstance(target.envelope, CommunicationResume) for target in resumes
    ):
        _fail(issues, record, "generated exports require an export-of Resume reference")
    if envelope.profile == "application":
        _require_targets(
            issues,
            record,
            by_id,
            "target-jd",
            {"market.jd"},
            allowed_statuses={"reviewed"},
        )
        if not any(
            isinstance(target.envelope, CommunicationResume)
            and target.envelope.status == "application-ready"
            for target in resumes
        ):
            _fail(issues, record, "application exports require an application-ready Resume")


def _require_targets(
    issues: list[RecordSemanticIssue],
    record: ParsedRecord,
    by_id: dict[UUID, ParsedRecord],
    relation: str,
    kinds: set[str],
    *,
    allowed_statuses: set[str] | None = None,
) -> None:
    targets = _required_relation_targets(record, by_id, relation)
    valid = [target for target in targets if target.envelope.kind in kinds]
    if allowed_statuses is not None:
        valid = [target for target in valid if target.envelope.status in allowed_statuses]
    if valid:
        return
    status_detail = (
        f" in status {', '.join(sorted(allowed_statuses))}" if allowed_statuses else ""
    )
    _fail(
        issues,
        record,
        f"requires relation {relation!r} to {', '.join(sorted(kinds))}{status_detail}",
    )


def _required_relation_targets(
    record: ParsedRecord,
    by_id: dict[UUID, ParsedRecord],
    relation: str,
) -> list[ParsedRecord]:
    return [
        by_id[reference.target_id]
        for reference in record.envelope.refs
        if reference.required
        and reference.relation == relation
        and reference.target_id in by_id
    ]


def _all_targets(
    record: ParsedRecord, by_id: dict[UUID, ParsedRecord]
) -> Iterable[ParsedRecord]:
    for reference in record.envelope.refs:
        target = by_id.get(reference.target_id)
        if target is not None:
            yield target


def _fail(
    issues: list[RecordSemanticIssue], record: ParsedRecord, detail: str
) -> None:
    issues.append(RecordSemanticIssue("fail", record.path, detail))
