from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from career_os.config import ProjectPaths
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


_RELATION_TARGET_KINDS: dict[tuple[str, str], frozenset[str] | None] = {
    ("evidence.capture", "represented_by"): frozenset({"evidence.work"}),
    ("evidence.work", "company"): frozenset({"opportunity.company"}),
    ("evidence.work", "company_context"): frozenset({"evidence.work"}),
    ("evidence.work", "work_context"): None,
    ("evidence.story", "career_lane"): frozenset({"strategy.lane"}),
    ("evidence.story", "derived_from"): frozenset({"evidence.work"}),
    ("evidence.claim", "context"): frozenset({"evidence.capture"}),
    ("evidence.claim", "supported_by"): frozenset({"evidence.work", "evidence.story"}),
    ("strategy.positioning", "defines_lane"): frozenset({"strategy.lane"}),
    ("strategy.positioning", "outlook_input"): frozenset(
        {"outlook.review", "outlook.thesis"}
    ),
    ("strategy.lane", "derived_from_positioning"): frozenset({"strategy.positioning"}),
    ("strategy.lane", "outlook_input"): frozenset({"outlook.review", "outlook.thesis"}),
    ("strategy.plan", "derived_from_positioning"): frozenset({"strategy.positioning"}),
    ("strategy.plan", "opportunity_baseline"): frozenset({"opportunity.engagement"}),
    ("strategy.plan", "outlook_input"): frozenset({"outlook.review", "outlook.thesis"}),
    ("market.channel", "career_lane"): frozenset({"strategy.lane"}),
    ("market.jd", "career_lane"): frozenset({"strategy.lane"}),
    ("market.jd", "company"): frozenset({"opportunity.company"}),
    ("market.jd", "engagement"): frozenset({"opportunity.engagement"}),
    ("market.jd", "market_direction"): frozenset({"market.direction"}),
    ("market.jd", "recruiting_scope"): frozenset({"opportunity.scope"}),
    ("market.jd", "source_channel"): frozenset({"market.channel"}),
    ("opportunity.scope", "company"): frozenset({"opportunity.company"}),
    ("opportunity.engagement", "company"): frozenset({"opportunity.company"}),
    ("opportunity.engagement", "recruiting_scope"): frozenset({"opportunity.scope"}),
    ("opportunity.engagement", "source_work"): None,
    ("opportunity.engagement", "target_jd"): frozenset({"market.jd"}),
    ("opportunity.decision", "engagement"): frozenset({"opportunity.engagement"}),
    ("outlook.thesis", "derived_from_review"): frozenset({"outlook.review"}),
    ("outlook.review", "personal_fit"): frozenset(
        {"evidence.work", "evidence.story", "strategy.positioning", "strategy.lane"}
    ),
    ("outlook.review", "market_revealed"): frozenset(
        {"market.jd", "opportunity.engagement"}
    ),
    ("outlook.review", "independent_external"): frozenset({"outlook.signal"}),
    ("outlook.review", "superseded_by"): frozenset({"outlook.review"}),
    ("outlook.review", "supersedes"): frozenset({"outlook.review"}),
    ("readiness.gap", "career_lane"): frozenset({"strategy.lane"}),
    ("readiness.gap", "closed_by_evidence"): frozenset({"evidence.work"}),
    ("readiness.gap", "closed_by_retest"): frozenset({"readiness.assessment"}),
    ("readiness.gap", "closure_evidence"): frozenset(
        {"evidence.work", "readiness.assessment"}
    ),
    ("readiness.gap", "experience_story"): frozenset({"evidence.story"}),
    ("readiness.gap", "last_retest"): frozenset(
        {"readiness.assessment", "readiness.session"}
    ),
    ("readiness.gap", "resume_audit"): frozenset({"communication.audit"}),
    ("readiness.gap", "resume_root"): frozenset({"communication.resume"}),
    ("readiness.gap", "target_jd"): frozenset({"market.jd"}),
    ("readiness.note", "target_gap"): frozenset({"readiness.gap"}),
    ("readiness.session", "career_lane"): frozenset({"strategy.lane"}),
    ("communication.profile", "claim_evidence"): frozenset(
        {"evidence.capture", "evidence.work", "evidence.story", "evidence.claim"}
    ),
    ("communication.profile", "current_employment"): frozenset(
        {"opportunity.engagement"}
    ),
    ("communication.audit", "resume_root"): frozenset({"communication.profile"}),
    ("communication.resume", "identity_profile"): frozenset({"communication.profile"}),
    ("communication.resume", "target_jd"): frozenset({"market.jd"}),
    ("communication.resume", "uses_claim"): frozenset({"evidence.claim"}),
    ("communication.export", "export_of"): frozenset({"communication.resume"}),
    ("communication.export", "target_jd"): frozenset({"market.jd"}),
}


def check_record_semantics(
    records: list[ParsedRecord], paths: ProjectPaths
) -> list[RecordSemanticIssue]:
    issues: list[RecordSemanticIssue] = []
    resolved = _resolve_relation_targets(records, paths, issues)
    current_employment: list[ParsedRecord] = []

    for record in records:
        envelope = record.envelope
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
                resolved,
                "represented_by",
                {"evidence.work"},
                allowed_statuses={"grounded", "verified"},
            )
        elif isinstance(envelope, EvidenceStory) and envelope.status == "reviewed":
            _require_targets(
                issues,
                record,
                resolved,
                "derived_from",
                {"evidence.work"},
                allowed_statuses={"grounded", "verified"},
            )
        elif isinstance(envelope, EvidenceClaim) and envelope.status == "approved":
            _check_approved_claim(issues, record, resolved, envelope)
        elif envelope.kind.startswith("strategy."):
            _check_strategy_outlook_refs(issues, record, resolved)
        elif isinstance(envelope, MarketJD):
            _check_jd(issues, record, resolved, envelope)
        elif isinstance(envelope, MarketChannel) and envelope.career_lane is not None:
            _require_targets(
                issues, record, resolved, "career_lane", {"strategy.lane"}
            )
        elif isinstance(envelope, OpportunityScope) and envelope.status in {
            "verified",
            "conservative",
        }:
            _require_targets(
                issues, record, resolved, "company", {"opportunity.company"}
            )
        elif isinstance(envelope, OpportunityEngagement):
            _check_engagement(issues, record, resolved, envelope)
            if envelope.is_current_employment:
                current_employment.append(record)
        elif isinstance(envelope, OpportunityDecision) and envelope.status == "decided":
            _require_targets(
                issues,
                record,
                resolved,
                "engagement",
                {"opportunity.engagement"},
            )
        elif isinstance(envelope, OutlookReview) and envelope.status == "reviewed":
            _check_review_signal_gate(issues, record, resolved)
        elif isinstance(envelope, OutlookThesis) and envelope.status == "reviewed":
            _require_targets(
                issues,
                record,
                resolved,
                "derived_from_review",
                {"outlook.review"},
                allowed_statuses={"reviewed"},
            )
        elif isinstance(envelope, ReadinessGap) and envelope.status == "closed":
            _check_closed_gap(issues, record, resolved, envelope)
        elif isinstance(envelope, ReadinessNote) and envelope.status == "reviewed":
            _require_targets(
                issues, record, resolved, "target_gap", {"readiness.gap"}
            )
        elif isinstance(envelope, CommunicationResume) and envelope.status in {
            "validated",
            "application-ready",
        }:
            _check_communication_resume(issues, record, resolved, envelope)
        elif isinstance(envelope, CommunicationExport) and envelope.status in {
            "generated",
            "released",
        }:
            _check_communication_export(issues, record, resolved, envelope)

    if len(current_employment) > 1:
        active = ", ".join(str(record.path) for record in current_employment)
        for record in current_employment:
            _fail(issues, record, f"current employment must be unique; active records: {active}")
    return issues


def _resolve_relation_targets(
    records: list[ParsedRecord],
    paths: ProjectPaths,
    issues: list[RecordSemanticIssue],
) -> dict[tuple[Path, str], list[ParsedRecord]]:
    by_path = {record.path.resolve(): record for record in records}
    resolved: dict[tuple[Path, str], list[ParsedRecord]] = {}
    for record in records:
        for (kind, relation), allowed_kinds in _RELATION_TARGET_KINDS.items():
            if record.envelope.kind != kind:
                continue
            links = _links(record, relation)
            if len(links) != len(set(links)):
                _fail(issues, record, f"{relation} must not contain duplicate Wikilinks")
            targets: list[ParsedRecord] = []
            for link in links:
                try:
                    target_path = _resolve_wikilink(paths.vault_root, link)
                except ValueError as error:
                    _fail(issues, record, f"{relation}: {error}")
                    continue
                target = by_path.get(target_path)
                if allowed_kinds is None:
                    if not target_path.is_file():
                        _fail(issues, record, f"{relation} target is missing: {link}")
                    continue
                if target is None:
                    _fail(issues, record, f"{relation} target is not a Career record: {link}")
                    continue
                if target.envelope.kind not in allowed_kinds:
                    _fail(
                        issues,
                        record,
                        f"{relation} target kind {target.envelope.kind!r} is not one of "
                        + ", ".join(sorted(allowed_kinds)),
                    )
                    continue
                targets.append(target)
            resolved[(record.path.resolve(), relation)] = targets
    return resolved


def _resolve_wikilink(vault_root: Path, link: str) -> Path:
    if not (link.startswith("[[") and link.endswith("]]")):
        raise ValueError(f"invalid Wikilink: {link!r}")
    target = link[2:-2].split("|", maxsplit=1)[0].split("#", maxsplit=1)[0]
    if "\\" in target:
        raise ValueError("Wikilink targets must use POSIX separators")
    relative = PurePosixPath(target)
    if (
        not target
        or relative.is_absolute()
        or ".." in relative.parts
        or relative == PurePosixPath(".")
    ):
        raise ValueError("Wikilink target must remain relative to the Vault root")
    candidate = vault_root.joinpath(*relative.parts)
    if candidate.suffix.lower() != ".md":
        candidate = Path(str(candidate) + ".md")
    root = vault_root.resolve()
    if not candidate.absolute().is_relative_to(root):
        raise ValueError("Wikilink target escapes the Vault root")
    return candidate.resolve()


def _links(record: ParsedRecord, relation: str) -> list[str]:
    value = getattr(record.envelope, relation)
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _targets(
    record: ParsedRecord,
    resolved: dict[tuple[Path, str], list[ParsedRecord]],
    relation: str,
) -> list[ParsedRecord]:
    return resolved.get((record.path.resolve(), relation), [])


def _check_jd(
    issues: list[RecordSemanticIssue],
    record: ParsedRecord,
    resolved: dict[tuple[Path, str], list[ParsedRecord]],
    envelope: MarketJD,
) -> None:
    try:
        source_body = extract_markdown_section(record.body, "JD 原文")
    except ValueError as error:
        _fail(issues, record, str(error))
        return
    actual = hashlib.sha256(source_body.encode("utf-8")).hexdigest()
    if actual != envelope.source_body_sha256:
        _fail(issues, record, "JD source body differs from its preserved SHA-256")
    if envelope.status in {"screened", "reviewed"}:
        try:
            extract_markdown_section(record.body, "重新评价")
        except ValueError as error:
            _fail(issues, record, str(error))
    for key, relation, kind in (
        (envelope.direction_key, "market_direction", "market.direction"),
        (envelope.career_lane_key, "career_lane", "strategy.lane"),
        (envelope.recruiting_scope_key, "recruiting_scope", "opportunity.scope"),
    ):
        if key is not None:
            _require_targets(issues, record, resolved, relation, {kind})


def _check_approved_claim(
    issues: list[RecordSemanticIssue],
    record: ParsedRecord,
    resolved: dict[tuple[Path, str], list[ParsedRecord]],
    envelope: EvidenceClaim,
) -> None:
    if envelope.visibility not in {"shareable", "public"}:
        _fail(issues, record, "approved claims must be shareable or public")
    if not set(envelope.allowed_uses) - {"internal"}:
        _fail(issues, record, "approved claims require at least one external allowed use")
    supported = any(
        (
            isinstance(target.envelope, EvidenceWork)
            and target.envelope.status in {"grounded", "verified"}
        )
        or (
            isinstance(target.envelope, EvidenceStory)
            and target.envelope.status == "reviewed"
        )
        for target in _targets(record, resolved, "supported_by")
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
    resolved: dict[tuple[Path, str], list[ParsedRecord]],
) -> None:
    for target in _all_targets(record, resolved):
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
    resolved: dict[tuple[Path, str], list[ParsedRecord]],
    envelope: OpportunityEngagement,
) -> None:
    _require_targets(issues, record, resolved, "company", {"opportunity.company"})
    if envelope.application_state not in {"not-applied", "unknown"}:
        _require_targets(issues, record, resolved, "target_jd", {"market.jd"})


def _check_review_signal_gate(
    issues: list[RecordSemanticIssue],
    record: ParsedRecord,
    resolved: dict[tuple[Path, str], list[ParsedRecord]],
) -> None:
    _require_targets(
        issues,
        record,
        resolved,
        "personal_fit",
        {"evidence.work", "evidence.story", "strategy.positioning", "strategy.lane"},
    )
    _require_targets(
        issues,
        record,
        resolved,
        "market_revealed",
        {"market.jd", "opportunity.engagement"},
    )
    _require_targets(
        issues,
        record,
        resolved,
        "independent_external",
        {"outlook.signal"},
        allowed_statuses={"verified"},
    )


def _check_closed_gap(
    issues: list[RecordSemanticIssue],
    record: ParsedRecord,
    resolved: dict[tuple[Path, str], list[ParsedRecord]],
    envelope: ReadinessGap,
) -> None:
    if not envelope.closure_note:
        _fail(issues, record, "closed readiness gaps require closure_note")
    if envelope.gap_type in {"knowledge", "practice"}:
        valid = any(
            isinstance(target.envelope, ReadinessAssessment)
            and target.envelope.status == "assessed"
            and target.envelope.assessment_type == "retest"
            and target.envelope.result == "pass"
            and target.envelope.reviewer_status == "verified"
            for target in _targets(record, resolved, "closed_by_retest")
        )
        if not valid:
            _fail(
                issues,
                record,
                "knowledge and practice gaps close only through a verified passing Retest",
            )
        return
    valid = any(
        isinstance(target.envelope, EvidenceWork)
        and target.envelope.status in {"grounded", "verified"}
        and target.envelope.evidence_strength in {"medium", "strong"}
        for target in _targets(record, resolved, "closed_by_evidence")
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
    resolved: dict[tuple[Path, str], list[ParsedRecord]],
    envelope: CommunicationResume,
) -> None:
    claims = _targets(record, resolved, "uses_claim")
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
            resolved,
            "target_jd",
            {"market.jd"},
            allowed_statuses={"reviewed"},
        )


def _check_communication_export(
    issues: list[RecordSemanticIssue],
    record: ParsedRecord,
    resolved: dict[tuple[Path, str], list[ParsedRecord]],
    envelope: CommunicationExport,
) -> None:
    resumes = _targets(record, resolved, "export_of")
    if not resumes:
        _fail(issues, record, "generated exports require an export_of Resume reference")
    if envelope.profile == "application":
        _require_targets(
            issues,
            record,
            resolved,
            "target_jd",
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
    resolved: dict[tuple[Path, str], list[ParsedRecord]],
    relation: str,
    kinds: set[str],
    *,
    allowed_statuses: set[str] | None = None,
) -> None:
    targets = _targets(record, resolved, relation)
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


def _all_targets(
    record: ParsedRecord,
    resolved: dict[tuple[Path, str], list[ParsedRecord]],
) -> Iterable[ParsedRecord]:
    for (path, _relation), targets in resolved.items():
        if path == record.path.resolve():
            yield from targets


def _fail(
    issues: list[RecordSemanticIssue], record: ParsedRecord, detail: str
) -> None:
    issues.append(RecordSemanticIssue("fail", record.path, detail))
