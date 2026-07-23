"""Strict, pure contracts for read-only Career OS reviewer outputs."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

EVIDENCE_AUDIT_SCHEMA = "resume-evidence-audit/1"
INTERVIEW_PROBE_SCHEMA = "resume-interview-probe/1"

EvidenceStatus = Literal[
    "supported",
    "bounded",
    "needs-confirmation",
    "unsupported",
    "conflicting/stale",
]
ProbePacketStatus = Literal["accepted", "rejected-leakage", "invalid"]
ProbeOutcome = Literal[
    "passed",
    "gap",
    "blocking-red-flag",
    "explicitly-skipped",
]
ProbeTargetDimension = Literal[
    "fact-boundary",
    "technical-depth",
    "answer-structure",
    "tradeoff-resilience",
]
ReviewerContract = Literal["evidence", "probe"]
NonEmptyString = Annotated[str, StringConstraints(min_length=1)]

EVIDENCE_BLOCKING_STATUSES = {
    "needs-confirmation",
    "unsupported",
    "conflicting/stale",
}


def _nonblank(value: str, field: str) -> str:
    if not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _optional_nonblank(value: str | None, field: str) -> str | None:
    if value is not None:
        _nonblank(value, field)
    return value


def _unique_nonblank_strings(values: list[str], field: str) -> list[str]:
    normalized: set[str] = set()
    for value in values:
        _nonblank(value, f"{field} item")
        key = " ".join(value.split()).casefold()
        if key in normalized:
            raise ValueError(f"{field} must not contain duplicates")
        normalized.add(key)
    return values


def _has_action(value: str | None) -> bool:
    return value is not None and value.strip().casefold() != "none"


class EvidenceClaim(BaseModel):
    """One atomized public claim and its evidence boundary."""

    model_config = ConfigDict(extra="forbid", strict=True)

    claim: NonEmptyString
    status: EvidenceStatus
    risk: NonEmptyString
    evidence: list[NonEmptyString]
    boundary: NonEmptyString | None
    conflicts: list[NonEmptyString]
    confirmation_question: NonEmptyString | None
    handoff: NonEmptyString | None

    @field_validator("claim", "risk")
    @classmethod
    def validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return _nonblank(value, info.field_name or "value")

    @field_validator("boundary", "confirmation_question", "handoff")
    @classmethod
    def validate_optional_text(
        cls, value: str | None, info: ValidationInfo
    ) -> str | None:
        return _optional_nonblank(value, info.field_name or "value")

    @field_validator("evidence", "conflicts")
    @classmethod
    def validate_string_lists(
        cls, value: list[str], info: ValidationInfo
    ) -> list[str]:
        return _unique_nonblank_strings(value, info.field_name or "value")

    @model_validator(mode="after")
    def validate_status_contract(self) -> EvidenceClaim:
        if self.status == "supported" and not self.evidence:
            raise ValueError("supported claim requires evidence")
        if self.status == "bounded" and (not self.evidence or self.boundary is None):
            raise ValueError("bounded claim requires evidence and boundary")
        if self.status != "bounded" and self.boundary is not None:
            raise ValueError("only a bounded claim may carry a boundary")
        if self.status == "conflicting/stale" and not self.conflicts:
            raise ValueError("conflicting/stale claim requires conflicts")
        if self.status != "conflicting/stale" and self.conflicts:
            raise ValueError("only a conflicting/stale claim may carry conflicts")

        unresolved = _has_action(self.confirmation_question) or _has_action(self.handoff)
        if self.status in {"supported", "bounded"} and unresolved:
            raise ValueError("non-blocking status cannot carry an unresolved action")
        if self.status in EVIDENCE_BLOCKING_STATUSES and not unresolved:
            raise ValueError(
                "blocking status requires a confirmation question or handoff"
            )
        return self


class EvidenceAudit(BaseModel):
    """The complete output of the Evidence Auditor."""

    model_config = ConfigDict(extra="forbid", strict=True)

    contract_schema: Literal["resume-evidence-audit/1"] = Field(alias="schema")
    claims: list[EvidenceClaim] = Field(min_length=1)

    @model_validator(mode="after")
    def reject_duplicate_claims(self) -> EvidenceAudit:
        seen: dict[str, int] = {}
        for index, item in enumerate(self.claims):
            normalized = " ".join(item.claim.split()).casefold()
            if normalized in seen:
                raise ValueError(
                    "claims["
                    f"{index}].claim duplicates an earlier claim at claims[{seen[normalized]}]"
                )
            seen[normalized] = index
        return self


class InterviewProbe(BaseModel):
    """One active or closed branch returned by the Blind Interviewer."""

    model_config = ConfigDict(extra="forbid", strict=True)

    contract_schema: Literal["resume-interview-probe/1"] = Field(alias="schema")
    packet_status: ProbePacketStatus
    branch: NonEmptyString
    claim: NonEmptyString
    current_question: NonEmptyString | None
    target_dimensions: list[ProbeTargetDimension] = Field(min_length=1)
    follow_up_triggers: list[NonEmptyString]
    outcome: ProbeOutcome | None

    @field_validator("branch", "claim")
    @classmethod
    def validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return _nonblank(value, info.field_name or "value")

    @field_validator("current_question")
    @classmethod
    def validate_question(cls, value: str | None) -> str | None:
        return _optional_nonblank(value, "current_question")

    @field_validator("follow_up_triggers")
    @classmethod
    def validate_triggers(cls, value: list[str]) -> list[str]:
        return _unique_nonblank_strings(value, "follow_up_triggers")

    @field_validator("target_dimensions")
    @classmethod
    def validate_dimensions(
        cls, value: list[ProbeTargetDimension]
    ) -> list[ProbeTargetDimension]:
        if len(value) != len(set(value)):
            raise ValueError("target_dimensions must not contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_branch_state(self) -> InterviewProbe:
        if self.packet_status != "accepted":
            if self.current_question is not None or self.outcome is not None:
                raise ValueError(
                    "non-accepted packet must not emit a question or outcome"
                )
            return self
        if self.outcome is None and self.current_question is None:
            raise ValueError("an active accepted branch requires current_question")
        if self.outcome is not None and self.current_question is not None:
            raise ValueError("a closed branch must set current_question to null")
        return self


@dataclass(frozen=True)
class ReviewerValidation:
    """Stable machine result returned by both the pure API and CLI adapter."""

    valid: bool
    blocks_readiness: bool
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, bool | list[str]]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def _validation_errors(error: ValidationError) -> tuple[str, ...]:
    formatted: list[str] = []
    for item in error.errors(include_url=False, include_context=False, include_input=False):
        location = ".".join(str(part) for part in item["loc"]) or "payload"
        message = str(item["msg"]).removeprefix("Value error, ")
        formatted.append(f"{location}: {message}")
    return tuple(formatted)


def validate_reviewer(contract: str, payload: Any) -> ReviewerValidation:
    """Validate one reviewer output without reading or writing external state."""

    if contract == "evidence":
        model: type[EvidenceAudit] | type[InterviewProbe] = EvidenceAudit
    elif contract == "probe":
        model = InterviewProbe
    else:
        return ReviewerValidation(
            valid=False,
            blocks_readiness=True,
            errors=("contract must be evidence or probe",),
        )

    try:
        validated = model.model_validate(payload)
    except ValidationError as error:
        return ReviewerValidation(
            valid=False,
            blocks_readiness=True,
            errors=_validation_errors(error),
        )

    if isinstance(validated, EvidenceAudit):
        blocked = any(
            claim.status in EVIDENCE_BLOCKING_STATUSES for claim in validated.claims
        )
    else:
        blocked = (
            validated.packet_status != "accepted" or validated.outcome != "passed"
        )
    return ReviewerValidation(valid=True, blocks_readiness=blocked, errors=())


def evidence_audit_json_schema() -> dict[str, Any]:
    schema = EvidenceAudit.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://career-os.dev/schemas/reviewer-evidence-audit.schema.json"
    schema["title"] = "Career OS Evidence Auditor Output"
    return schema


def interview_probe_json_schema() -> dict[str, Any]:
    schema = InterviewProbe.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://career-os.dev/schemas/reviewer-interview-probe.schema.json"
    schema["title"] = "Career OS Blind Interviewer Output"
    return schema
