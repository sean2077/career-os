from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import (
    UUID4,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

Visibility = Literal["private", "shareable", "public"]

_BCP47_PATTERN = r"^(?=.{2,35}$)(?:[A-Za-z]{2,8})(?:-[A-Za-z0-9]{1,8})*$"
_BCP47 = re.compile(_BCP47_PATTERN, re.ASCII)
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_PREFIXED_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
_PROFILE_ID_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
_WIKILINK_PATTERN = r"^\[\[[^\]\r\n|]+(?:#[^\]\r\n|]+)?(?:\|[^\]\r\n]+)?\]\]$"
Wikilink = Annotated[str, Field(pattern=_WIKILINK_PATTERN)]


@dataclass(frozen=True)
class LifecycleContract:
    initial: frozenset[str]
    transitions: frozenset[tuple[str, str]]


def _lifecycle(
    initial: set[str], transitions: set[tuple[str, str]]
) -> LifecycleContract:
    return LifecycleContract(frozenset(initial), frozenset(transitions))


KIND_LIFECYCLES: dict[str, LifecycleContract] = {
    "evidence.capture": _lifecycle(
        {"needs-debrief", "ready-to-archive"},
        {
            ("needs-debrief", "ready-to-archive"),
            ("ready-to-archive", "needs-debrief"),
            ("ready-to-archive", "archived"),
        },
    ),
    "evidence.work": _lifecycle(
        {"draft"}, {("draft", "grounded"), ("grounded", "verified")}
    ),
    "evidence.story": _lifecycle({"draft"}, {("draft", "reviewed")}),
    "evidence.claim": _lifecycle(
        {"draft"},
        {
            ("draft", "reviewed"),
            ("reviewed", "approved"),
            ("reviewed", "rejected"),
            ("approved", "withdrawn"),
        },
    ),
    "strategy.positioning": _lifecycle(
        {"candidate"},
        {
            ("candidate", "reviewed"),
            ("reviewed", "accepted"),
            ("reviewed", "rejected"),
            ("reviewed", "deferred"),
            ("accepted", "superseded"),
        },
    ),
    "strategy.lane": _lifecycle(
        {"candidate"},
        {
            ("candidate", "reviewed"),
            ("reviewed", "accepted"),
            ("reviewed", "rejected"),
            ("reviewed", "deferred"),
            ("accepted", "superseded"),
        },
    ),
    "strategy.plan": _lifecycle(
        {"draft"},
        {
            ("draft", "active"),
            ("active", "paused"),
            ("paused", "active"),
            ("active", "completed"),
            ("active", "superseded"),
            ("paused", "superseded"),
        },
    ),
    "market.direction": _lifecycle(
        {"candidate"},
        {
            ("candidate", "reviewed"),
            ("reviewed", "active"),
            ("reviewed", "rejected"),
            ("active", "superseded"),
        },
    ),
    "market.channel": _lifecycle(
        {"active"},
        {
            ("active", "stale"),
            ("stale", "active"),
            ("active", "retired"),
            ("stale", "retired"),
        },
    ),
    "market.jd": _lifecycle(
        {"captured"},
        {
            ("captured", "screened"),
            ("captured", "skipped"),
            ("screened", "reviewed"),
            ("screened", "skipped"),
        },
    ),
    "opportunity.company": _lifecycle(
        {"pending-review"},
        {
            ("pending-review", "reviewed"),
            ("reviewed", "stale"),
            ("stale", "pending-review"),
        },
    ),
    "opportunity.scope": _lifecycle(
        {"draft"},
        {
            ("draft", "verified"),
            ("draft", "conservative"),
            ("verified", "superseded"),
            ("conservative", "superseded"),
        },
    ),
    "opportunity.engagement": _lifecycle(
        {"active"},
        {
            ("active", "paused"),
            ("paused", "active"),
            ("active", "closed"),
            ("paused", "closed"),
        },
    ),
    "opportunity.decision": _lifecycle(
        {"draft"},
        {
            ("draft", "reviewed"),
            ("reviewed", "decided"),
            ("decided", "superseded"),
        },
    ),
    "outlook.signal": _lifecycle(
        {"captured"},
        {
            ("captured", "verified"),
            ("captured", "rejected"),
            ("verified", "stale"),
        },
    ),
    "outlook.thesis": _lifecycle(
        {"candidate"},
        {
            ("candidate", "reviewed"),
            ("candidate", "rejected"),
            ("reviewed", "superseded"),
        },
    ),
    "outlook.review": _lifecycle(
        {"pending"},
        {
            ("pending", "reviewed"),
            ("pending", "rejected"),
            ("reviewed", "superseded"),
        },
    ),
    "readiness.gap": _lifecycle(
        {"open"},
        {
            ("open", "learning"),
            ("open", "practice"),
            ("open", "blocked"),
            ("learning", "retest"),
            ("practice", "retest"),
            ("retest", "open"),
            ("retest", "closed"),
            ("blocked", "open"),
            ("blocked", "closed"),
        },
    ),
    "readiness.note": _lifecycle({"draft"}, {("draft", "reviewed")}),
    "readiness.session": _lifecycle(
        {"planned"}, {("planned", "completed"), ("planned", "invalidated")}
    ),
    "readiness.assessment": _lifecycle(
        {"draft"}, {("draft", "assessed"), ("assessed", "superseded")}
    ),
    "communication.profile": _lifecycle(
        {"draft"}, {("draft", "approved"), ("approved", "superseded")}
    ),
    "communication.audit": _lifecycle(
        {"draft"},
        {
            ("draft", "reviewed"),
            ("draft", "blocked"),
            ("draft", "stale"),
            ("reviewed", "stale"),
            ("blocked", "reviewed"),
            ("blocked", "stale"),
        },
    ),
    "communication.resume": _lifecycle(
        {"draft"},
        {
            ("draft", "validated"),
            ("validated", "application-ready"),
            ("validated", "superseded"),
            ("application-ready", "superseded"),
        },
    ),
    "communication.export": _lifecycle(
        {"planned"},
        {
            ("planned", "generated"),
            ("generated", "released"),
            ("generated", "revoked"),
            ("released", "revoked"),
        },
    ),
}

RECORD_KINDS = frozenset(KIND_LIFECYCLES)


class RecordEnvelopeBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID4
    kind: str
    schema_version: Literal[3]
    created_at: datetime
    updated_at: datetime
    languages: list[str] | None = None
    visibility: Visibility = "private"
    title: str | None = None
    status: str
    tags: list[str] | None = None
    aliases: list[str] | None = None
    migration_review: Literal["required"] | None = None
    legacy_fields: dict[str, Any] | None = None

    @field_validator("created_at", "updated_at")
    @classmethod
    def require_timestamp_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("record timestamps must include a timezone")
        return value

    @field_validator("languages")
    @classmethod
    def validate_languages(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if not value:
            raise ValueError("languages must be omitted or contain at least one BCP 47 tag")
        invalid = [item for item in value if not _BCP47.fullmatch(item)]
        if invalid:
            raise ValueError(f"invalid BCP 47 language tags: {', '.join(invalid)}")
        if len(value) != len(set(value)):
            raise ValueError("languages must not contain duplicates")
        return value

    @field_validator("tags", "aliases")
    @classmethod
    def validate_optional_unique_text(
        cls, value: list[str] | None
    ) -> list[str] | None:
        if value is None:
            return None
        if not value or any(not item.strip() for item in value):
            raise ValueError("tags and aliases must be omitted or contain non-empty values")
        if len(value) != len(set(value)):
            raise ValueError("tags and aliases must not contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_common_contract(self) -> RecordEnvelopeBase:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        if self.migration_review != "required" and self.legacy_fields is not None:
            raise ValueError("legacy_fields require migration_review: required")
        return self


def validate_record_transition(
    previous: RecordEnvelopeBase | None,
    current: RecordEnvelopeBase,
) -> None:
    """Validate lifecycle state against the previous Git version of one record."""
    lifecycle = KIND_LIFECYCLES[current.kind]
    if previous is None:
        if current.status not in lifecycle.initial:
            raise ValueError(
                f"new {current.kind} record must start in one of: "
                + ", ".join(sorted(lifecycle.initial))
            )
        return
    if previous.id != current.id or previous.kind != current.kind:
        raise ValueError("record identity and kind cannot change")
    if previous.status == current.status:
        return
    if (previous.status, current.status) not in lifecycle.transitions:
        raise ValueError(
            f"forbidden {current.kind} transition: {previous.status} -> {current.status}"
        )
    if current.updated_at <= previous.updated_at:
        raise ValueError("status changes must advance updated_at")


class EvidenceCapture(RecordEnvelopeBase):
    kind: Literal["evidence.capture"]
    status: Literal["needs-debrief", "ready-to-archive", "archived"]
    source_type: Literal["user-report", "document", "host-note", "external", "unknown"]
    captured_at: datetime
    provenance: str = Field(min_length=1)
    attribution: Literal["user", "team", "third-party", "mixed", "unknown"]
    sensitivity: Literal["none", "internal", "private-sensitive", "third-party", "unknown"]
    represented_by: list[Wikilink] = Field(default_factory=list)

    @field_validator("captured_at")
    @classmethod
    def require_capture_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("capture timestamp must include a timezone")
        return value


class EvidenceWork(RecordEnvelopeBase):
    kind: Literal["evidence.work"]
    status: Literal["draft", "grounded", "verified"]
    contribution_scope: Literal["individual", "shared", "team", "unknown"]
    evidence_strength: Literal["weak", "medium", "strong"]
    evidence_summary: str = Field(min_length=1)
    company: Wikilink | None = None
    company_context: Wikilink | None = None
    work_context: list[Wikilink] = Field(default_factory=list)


class EvidenceStory(RecordEnvelopeBase):
    kind: Literal["evidence.story"]
    status: Literal["draft", "reviewed"]
    sensitive_boundary: str = Field(min_length=1)
    story_role: Literal["primary", "supporting", "candidate"] | None = None
    readiness_state: Literal["content-ready", "ready", "needs-work", "blocked"] | None = None
    career_lane: Wikilink | None = None
    derived_from: Wikilink | None = None


class EvidenceClaim(RecordEnvelopeBase):
    kind: Literal["evidence.claim"]
    status: Literal["draft", "reviewed", "approved", "rejected", "withdrawn"]
    allowed_uses: list[Literal["internal", "resume", "recruiter", "application", "public"]]
    claim_risk: Literal["low", "medium", "high"]
    context: list[Wikilink] = Field(default_factory=list)
    supported_by: list[Wikilink] = Field(default_factory=list)

    @field_validator("allowed_uses")
    @classmethod
    def validate_allowed_uses(cls, value: list[str]) -> list[str]:
        if not value or len(value) != len(set(value)):
            raise ValueError("allowed_uses must be non-empty and unique")
        return value


class StrategyPositioning(RecordEnvelopeBase):
    kind: Literal["strategy.positioning"]
    status: Literal["candidate", "reviewed", "accepted", "rejected", "deferred", "superseded"]
    confidence: Literal["low", "medium", "high"]
    review_on: date
    disconfirming_signals: list[str]
    defines_lane: list[Wikilink] = Field(default_factory=list)
    outlook_input: Wikilink | None = None


class StrategyLane(RecordEnvelopeBase):
    kind: Literal["strategy.lane"]
    status: Literal["candidate", "reviewed", "accepted", "rejected", "deferred", "superseded"]
    confidence: Literal["low", "medium", "high"]
    review_on: date
    disconfirming_signals: list[str]
    derived_from_positioning: Wikilink | None = None
    outlook_input: Wikilink | None = None


class StrategyPlan(RecordEnvelopeBase):
    kind: Literal["strategy.plan"]
    status: Literal["draft", "active", "paused", "completed", "superseded"]
    horizon_start: date
    horizon_end: date
    review_on: date
    derived_from_positioning: Wikilink | None = None
    opportunity_baseline: Wikilink | None = None
    outlook_input: Wikilink | None = None

    @model_validator(mode="after")
    def validate_horizon(self) -> StrategyPlan:
        if self.horizon_end < self.horizon_start:
            raise ValueError("strategy plan horizon_end must not precede horizon_start")
        return self


class MarketDirection(RecordEnvelopeBase):
    kind: Literal["market.direction"]
    status: Literal["candidate", "reviewed", "active", "rejected", "superseded"]
    review_on: date


class MarketChannel(RecordEnvelopeBase):
    kind: Literal["market.channel"]
    status: Literal["active", "stale", "retired"]
    rank: int = Field(ge=1)
    tier: str = Field(min_length=1)
    role: str = Field(min_length=1)
    url: str | None = Field(default=None, min_length=1)
    last_verified_at: date
    career_lane: list[Wikilink] = Field(default_factory=list)


class MarketJD(RecordEnvelopeBase):
    kind: Literal["market.jd"]
    status: Literal["captured", "screened", "reviewed", "skipped"]
    source_status: Literal["full", "partial", "summary-only", "unavailable"]
    source_channel_name: str = Field(min_length=1)
    source_origin: str | None = Field(default=None, min_length=1)
    source_url: str | None = None
    captured_at: datetime
    missing_sections: list[str]
    source_body_sha256: str = Field(pattern=_SHA256_PATTERN)
    collection: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    employer_name: str | None = Field(default=None, min_length=1)
    location: str | None = Field(default=None, min_length=1)
    compensation: str | None = Field(default=None, min_length=1)
    recruiting_scope_key: str | None = Field(default=None, pattern=_PROFILE_ID_PATTERN)
    is_stale: bool = False
    evidence_fit: int | None = Field(default=None, ge=0, le=5)
    preference: Literal["low", "medium", "high", "unknown"] | None = None
    priority: Literal["p0", "p1", "p2", "p3", "reject", "unknown"] | None = None
    next_action: Literal["observe", "clarify", "candidate", "reject"] | None = None
    gaps: list[str] = Field(default_factory=list)
    gap_summary: str | None = Field(default=None, min_length=1)
    direction_key: str | None = Field(default=None, pattern=_PROFILE_ID_PATTERN)
    career_lane_key: str | None = Field(default=None, pattern=_PROFILE_ID_PATTERN)
    user_review_signal: str | None = Field(default=None, min_length=1)
    growth_signal: str | None = Field(default=None, min_length=1)
    preference_signal: str | None = Field(default=None, min_length=1)
    next_action_detail: str | None = Field(default=None, min_length=1)
    duplicate_group: str | None = Field(default=None, min_length=1)
    case_target: Literal["positive", "boundary", "observe", "negative"] | None = None
    review_note: str | None = Field(default=None, min_length=1)
    reviewed_at: date | None = None
    career_lane: Wikilink | None = None
    company: Wikilink | None = None
    engagement: Wikilink | None = None
    market_direction: Wikilink | None = None
    recruiting_scope: Wikilink | None = None
    source_channel: Wikilink | None = None

    @field_validator("captured_at")
    @classmethod
    def require_capture_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("JD capture timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_source_fidelity(self) -> MarketJD:
        if self.source_status == "full" and self.missing_sections:
            raise ValueError("a full JD source cannot declare missing_sections")
        if (
            self.source_status in {"partial", "summary-only", "unavailable"}
            and not self.missing_sections
        ):
            raise ValueError("an incomplete JD source must declare missing_sections")
        if self.status in {"screened", "reviewed"}:
            required = {
                "evidence_fit": self.evidence_fit,
                "preference": self.preference,
                "priority": self.priority,
                "next_action": self.next_action,
            }
            missing = [name for name, value in required.items() if value is None]
            if missing:
                raise ValueError(
                    "screened and reviewed JDs require screening fields: "
                    + ", ".join(missing)
                )
        if self.status == "reviewed" and self.reviewed_at is None:
            raise ValueError("reviewed JDs require reviewed_at")
        return self


class OpportunityCompany(RecordEnvelopeBase):
    kind: Literal["opportunity.company"]
    status: Literal["pending-review", "reviewed", "stale"]
    canonical_name: str = Field(min_length=1)
    display_name_zh: str | None = Field(default=None, min_length=1)
    display_name_en: str | None = Field(default=None, min_length=1)
    fact_state: Literal["fact", "inference", "unknown", "mixed"]
    refreshed_at: date
    freshness_days: int = Field(ge=1)
    watch_state: Literal["current", "target", "watch", "avoid", "unknown"] | None = None
    company_lifecycle: Literal["listed", "mature-private", "venture-startup", "unknown"] | None = (
        None
    )
    research_level: Literal["lead", "standard", "deep", "update", "unknown"] | None = None
    assessment_status: Literal["draft", "current", "stale", "blocked"] | None = None
    strength: Literal["weak", "mixed", "positive", "strong", "unknown"] | None = None
    business_outlook: Literal["negative", "mixed", "positive", "strong", "unknown"] | None = None
    employer_quality: Literal["negative", "mixed", "positive", "strong", "unknown"] | None = None
    career_alignment: Literal["negative", "mixed", "positive", "strong", "unknown"] | None = None
    risk: Literal["low", "medium", "high", "critical", "unknown"] | None = None
    confidence: Literal["low", "medium", "high", "unknown"] | None = None
    trend: Literal["declining", "mixed", "improving", "unknown"] | None = None
    review_status: Literal["pending", "reviewed"] | None = None
    reviewed_at: date | None = None
    last_researched_at: date | None = None
    refresh_due: date | None = None
    next_action: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_review_metadata(self) -> OpportunityCompany:
        if self.review_status == "reviewed" and self.reviewed_at is None:
            raise ValueError("reviewed companies require reviewed_at")
        return self


class OpportunityScope(RecordEnvelopeBase):
    kind: Literal["opportunity.scope"]
    status: Literal["draft", "verified", "conservative", "superseded"]
    team: str | None = None
    role: str | None = None
    location: str | None = None
    channel: str = Field(min_length=1)
    company: Wikilink | None = None


EngagementEventType = Literal[
    "recruiter-contacted",
    "referral-created",
    "application-submitted",
    "application-withdrawn",
    "application-rejected",
    "interview-scheduled",
    "interview-completed",
    "offer-received",
    "offer-accepted",
    "offer-declined",
    "process-closed",
    "employment-started",
    "employment-ended",
]


class EngagementEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID4
    event_type: EngagementEventType
    occurred_at: datetime
    occurred_at_precision: Literal["instant", "day", "month", "year"] = "instant"
    source: Literal["user-report", "external-record"]
    note: str | None = None

    @field_validator("occurred_at")
    @classmethod
    def require_event_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("engagement event timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_event_precision(self) -> EngagementEvent:
        normalized_time = (
            self.occurred_at.hour,
            self.occurred_at.minute,
            self.occurred_at.second,
            self.occurred_at.microsecond,
        )
        if self.occurred_at_precision != "instant" and normalized_time != (0, 0, 0, 0):
            raise ValueError("non-instant engagement events must use midnight as a sort key")
        if self.occurred_at_precision == "month" and self.occurred_at.day != 1:
            raise ValueError("month-precision engagement events must use the first day")
        if self.occurred_at_precision == "year" and (
            self.occurred_at.month != 1 or self.occurred_at.day != 1
        ):
            raise ValueError("year-precision engagement events must use January 1")
        return self


class OpportunityEngagement(RecordEnvelopeBase):
    kind: Literal["opportunity.engagement"]
    status: Literal["active", "paused", "closed"]
    engagement_type: Literal[
        "employment",
        "recruiter-contact",
        "referral",
        "application",
        "interview",
        "offer",
        "unknown",
    ]
    stage: Literal[
        "identified",
        "contacted",
        "scoped",
        "applied",
        "interviewing",
        "offer",
        "employed",
        "closed",
    ]
    application_state: Literal[
        "not-applied",
        "unknown",
        "applied",
        "withdrawn",
        "rejected",
        "offer",
        "accepted",
        "declined",
    ]
    is_current_employment: bool
    events: list[EngagementEvent]
    decision_state: str | None = Field(default=None, min_length=1)
    role: str | None = Field(default=None, min_length=1)
    team: str | None = Field(default=None, min_length=1)
    started_on: str | None = Field(default=None, pattern=r"^\d{4}(?:-\d{2}(?:-\d{2})?)?$")
    review_on: str | None = Field(default=None, pattern=r"^\d{4}(?:-\d{2}(?:-\d{2})?)?$")
    strategy_fit: Literal["negative", "mixed", "positive", "strong", "unknown"] | None = None
    opportunity_quality: Literal["negative", "mixed", "positive", "strong", "unknown"] | None = None
    confidence: Literal["low", "medium", "high", "unknown"] | None = None
    review_status: Literal["pending", "reviewed"] | None = None
    reviewed_at: date | None = None
    next_action: str | None = Field(default=None, min_length=1)
    company: Wikilink | None = None
    recruiting_scope: Wikilink | None = None
    source_work: list[Wikilink] = Field(default_factory=list)
    target_jd: Wikilink | None = None

    @model_validator(mode="after")
    def validate_engagement_events(self) -> OpportunityEngagement:
        if self.review_status == "reviewed" and self.reviewed_at is None:
            raise ValueError("reviewed engagements require reviewed_at")
        if len({event.id for event in self.events}) != len(self.events):
            raise ValueError("engagement events must have unique IDs")
        if self.events != sorted(self.events, key=lambda event: event.occurred_at):
            raise ValueError("engagement events must be chronological")
        event_types = {event.event_type for event in self.events}
        required_application_event = {
            "applied": "application-submitted",
            "withdrawn": "application-withdrawn",
            "rejected": "application-rejected",
            "offer": "offer-received",
            "accepted": "offer-accepted",
            "declined": "offer-declined",
        }.get(self.application_state)
        if (
            required_application_event is not None
            and required_application_event not in event_types
        ):
            raise ValueError(
                f"application_state {self.application_state!r} requires "
                f"an {required_application_event!r} event"
            )
        progressed_events = event_types & {
            "application-submitted",
            "application-withdrawn",
            "application-rejected",
            "offer-received",
            "offer-accepted",
            "offer-declined",
        }
        if self.application_state == "not-applied" and progressed_events:
            raise ValueError("not-applied cannot contain application or offer events")
        required_stage_event = {
            "contacted": "recruiter-contacted",
            "applied": "application-submitted",
            "interviewing": "interview-scheduled",
            "offer": "offer-received",
            "employed": "employment-started",
        }.get(self.stage)
        if required_stage_event is not None and required_stage_event not in event_types:
            raise ValueError(f"stage {self.stage!r} requires a {required_stage_event!r} event")
        stage_rank = {
            "identified": 0,
            "contacted": 1,
            "scoped": 2,
            "applied": 3,
            "interviewing": 4,
            "offer": 5,
            "employed": 6,
            "closed": 7,
        }
        event_stage = {
            "recruiter-contacted": "contacted",
            "application-submitted": "applied",
            "interview-scheduled": "interviewing",
            "interview-completed": "interviewing",
            "offer-received": "offer",
            "offer-accepted": "offer",
            "offer-declined": "offer",
            "employment-started": "employed",
        }
        furthest_event_rank = max(
            (stage_rank[event_stage[item]] for item in event_types if item in event_stage),
            default=0,
        )
        if stage_rank[self.stage] < furthest_event_rank:
            raise ValueError("engagement stage cannot trail its recorded events")
        if self.application_state in {"withdrawn", "rejected", "declined"} and (
            self.stage != "closed"
        ):
            raise ValueError(f"application_state {self.application_state!r} requires closed stage")
        self._validate_event_order()
        if self.is_current_employment and (
            self.engagement_type != "employment"
            or self.stage != "employed"
            or self.status != "active"
            or "employment-started" not in event_types
            or "employment-ended" in event_types
        ):
            raise ValueError("current employment must be one active, started employment engagement")
        return self

    def _validate_event_order(self) -> None:
        indexed = list(enumerate(self.events))

        def require_before(event_type: str, prerequisite: str) -> None:
            for index, event in indexed:
                if event.event_type != event_type:
                    continue
                if not any(
                    prior.event_type == prerequisite
                    for prior_index, prior in indexed
                    if prior_index < index
                ):
                    raise ValueError(
                        f"{event_type!r} requires an earlier {prerequisite!r} event"
                    )

        require_before("application-withdrawn", "application-submitted")
        require_before("application-rejected", "application-submitted")
        require_before("interview-completed", "interview-scheduled")
        require_before("offer-accepted", "offer-received")
        require_before("offer-declined", "offer-received")
        require_before("employment-ended", "employment-started")


class OpportunityDecision(RecordEnvelopeBase):
    kind: Literal["opportunity.decision"]
    status: Literal["draft", "reviewed", "decided", "superseded"]
    decision: Literal["continue", "hold", "decline", "accept", "reject", "unknown"]
    rationale: str = Field(min_length=1)
    review_on: date
    triggers: list[str]
    engagement: Wikilink | None = None


class OutlookSignal(RecordEnvelopeBase):
    kind: Literal["outlook.signal"]
    status: Literal["captured", "verified", "stale", "rejected"]
    source_class: Literal["policy", "labour", "industry", "technology", "unknown"]
    event_date: date
    published_at: date
    retrieved_at: date
    source_url: str | None = None


class OutlookThesis(RecordEnvelopeBase):
    kind: Literal["outlook.thesis"]
    status: Literal["candidate", "reviewed", "rejected", "superseded"]
    confidence: Literal["low", "medium", "high"]
    horizon: str = Field(min_length=1)
    invalidation_conditions: list[str] = Field(min_length=1)
    review_authority: Literal["user"] | None = None
    derived_from_review: Wikilink | None = None

    @model_validator(mode="after")
    def validate_review_authority(self) -> OutlookThesis:
        if self.status == "reviewed" and self.review_authority != "user":
            raise ValueError("a reviewed outlook thesis requires explicit user review")
        return self


class OutlookReview(RecordEnvelopeBase):
    kind: Literal["outlook.review"]
    status: Literal["pending", "reviewed", "rejected", "superseded"]
    as_of: date
    personal_fit_gate: Literal["missing", "partial", "satisfied"]
    market_revealed_gate: Literal["missing", "partial", "satisfied"]
    independent_external_gate: Literal["missing", "partial", "satisfied"]
    confidence: Literal["low", "medium", "high"]
    rationale: str = Field(min_length=1)
    invalidation_conditions: list[str] = Field(min_length=1)
    review_authority: Literal["user"] | None = None
    personal_fit: list[Wikilink] = Field(default_factory=list)
    market_revealed: list[Wikilink] = Field(default_factory=list)
    independent_external: list[Wikilink] = Field(default_factory=list)
    superseded_by: Wikilink | None = None
    supersedes: Wikilink | None = None

    @model_validator(mode="after")
    def validate_review_gate(self) -> OutlookReview:
        gates = {
            self.personal_fit_gate,
            self.market_revealed_gate,
            self.independent_external_gate,
        }
        if self.status == "reviewed" and gates != {"satisfied"}:
            raise ValueError("a reviewed outlook requires all three signal gates")
        if self.status == "reviewed" and self.review_authority != "user":
            raise ValueError("a reviewed outlook requires explicit user review")
        return self


class ReadinessGap(RecordEnvelopeBase):
    kind: Literal["readiness.gap"]
    status: Literal["open", "learning", "practice", "blocked", "retest", "closed"]
    gap_type: Literal["knowledge", "practice", "production-evidence", "unknown"]
    target: str = Field(min_length=1)
    closure_note: str | None = None
    priority: Literal["p0", "p1", "p2"] | None = None
    career_lane: Wikilink | None = None
    closed_by_evidence: list[Wikilink] = Field(default_factory=list)
    closed_by_retest: list[Wikilink] = Field(default_factory=list)
    closure_evidence: list[Wikilink] = Field(default_factory=list)
    experience_story: list[Wikilink] = Field(default_factory=list)
    last_retest: list[Wikilink] = Field(default_factory=list)
    resume_audit: Wikilink | None = None
    resume_root: list[Wikilink] = Field(default_factory=list)
    target_jd: Wikilink | None = None


class ReadinessNote(RecordEnvelopeBase):
    kind: Literal["readiness.note"]
    status: Literal["draft", "reviewed"]
    note_type: Literal["learning", "paper", "practice", "unknown"]
    source_title: str | None = None
    target_gap: list[Wikilink] = Field(default_factory=list)


class ReadinessSession(RecordEnvelopeBase):
    kind: Literal["readiness.session"]
    status: Literal["planned", "completed", "invalidated"]
    session_type: Literal["coach", "strict", "retest", "unknown"]
    outcome: Literal["pass", "fail", "blocked", "unscored"]
    reviewer_status: Literal["verified", "fallback", "missing"]
    input_fingerprint: str | None = None
    session_date: date | None = None
    target: Literal["lane", "jd", "historical"] | None = None
    scope: str | None = Field(default=None, min_length=1)
    attempt: int | None = Field(default=None, ge=0, le=2)
    fact_boundary: Literal["unscored", "not-ready", "weak", "ready", "strong"] | None = None
    technical_depth: Literal["unscored", "not-ready", "weak", "ready", "strong"] | None = None
    answer_structure: Literal["unscored", "not-ready", "weak", "ready", "strong"] | None = None
    tradeoff_resilience: Literal["unscored", "not-ready", "weak", "ready", "strong"] | None = None
    blocking_red_flag: bool | None = None
    verdict: Literal["unscored", "not-ready", "ready", "blocked", "stale", "historical"] | None = (
        None
    )
    career_lane: Wikilink | None = None

    @model_validator(mode="after")
    def validate_session_evidence(self) -> ReadinessSession:
        if (
            self.status == "completed"
            and self.session_type in {"strict", "retest"}
            and not self.input_fingerprint
        ):
            raise ValueError("completed strict and retest sessions require input_fingerprint")
        return self


class ReadinessAssessment(RecordEnvelopeBase):
    kind: Literal["readiness.assessment"]
    status: Literal["draft", "assessed", "superseded"]
    assessment_type: Literal["baseline", "jd-delta", "retest", "unknown"]
    result: Literal["pass", "fail", "blocked"]
    reviewer_status: Literal["verified", "fallback", "missing"]
    input_fingerprint: str = Field(min_length=1)


class CommunicationProfile(RecordEnvelopeBase):
    kind: Literal["communication.profile"]
    status: Literal["draft", "approved", "superseded"]
    audience: str = Field(min_length=1)
    identity_policy: Literal["anonymous", "preview", "application", "public"]
    claim_evidence: list[Wikilink] = Field(default_factory=list)
    current_employment: Wikilink | None = None


class CommunicationAudit(RecordEnvelopeBase):
    kind: Literal["communication.audit"]
    status: Literal["draft", "reviewed", "blocked", "stale"]
    audit_date: date
    scope: str = Field(min_length=1)
    career_lane: str | None = Field(default=None, min_length=1)
    source_fingerprint: str = Field(pattern=_PREFIXED_SHA256_PATTERN)
    target_jd_fingerprint: str | None = Field(default=None, pattern=_PREFIXED_SHA256_PATTERN)
    evidence_fingerprint: str | None = Field(default=None, pattern=_PREFIXED_SHA256_PATTERN)
    blocking_findings: int = Field(ge=0)
    confirmation_count: int = Field(ge=0)
    reviewer_status: Literal["complete", "fallback", "missing"]
    user_confirmed: bool
    resume_root: Wikilink | None = None

    @model_validator(mode="after")
    def validate_audit_state(self) -> CommunicationAudit:
        if self.status == "blocked" and self.blocking_findings == 0:
            raise ValueError("blocked communication audits require blocking_findings")
        return self


class CommunicationResume(RecordEnvelopeBase):
    kind: Literal["communication.resume"]
    status: Literal["draft", "validated", "application-ready", "superseded"]
    root_name: str = Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    audience: str = Field(min_length=1)
    export_policy: Literal["preview", "application"]
    identity_profile: Wikilink | None = None
    target_jd: Wikilink | None = None
    uses_claim: list[Wikilink] = Field(default_factory=list)


class CommunicationExport(RecordEnvelopeBase):
    kind: Literal["communication.export"]
    status: Literal["planned", "generated", "released", "revoked"]
    profile: Literal["preview", "application"]
    authorization: Literal["missing", "explicit"]
    artifact_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    destination: str | None = None
    export_of: Wikilink | None = None
    target_jd: Wikilink | None = None

    @model_validator(mode="after")
    def validate_export_state(self) -> CommunicationExport:
        if self.status in {"generated", "released"}:
            if self.authorization != "explicit":
                raise ValueError("generated exports require explicit authorization")
            if self.artifact_sha256 is None:
                raise ValueError("generated exports require artifact_sha256")
        if self.status == "released" and not self.destination:
            raise ValueError("released exports require a destination record")
        return self


type RecordEnvelope = Annotated[
    EvidenceCapture
    | EvidenceWork
    | EvidenceStory
    | EvidenceClaim
    | StrategyPositioning
    | StrategyLane
    | StrategyPlan
    | MarketDirection
    | MarketChannel
    | MarketJD
    | OpportunityCompany
    | OpportunityScope
    | OpportunityEngagement
    | OpportunityDecision
    | OutlookSignal
    | OutlookThesis
    | OutlookReview
    | ReadinessGap
    | ReadinessNote
    | ReadinessSession
    | ReadinessAssessment
    | CommunicationProfile
    | CommunicationAudit
    | CommunicationResume
    | CommunicationExport,
    Field(discriminator="kind"),
]

RECORD_ADAPTER: TypeAdapter[RecordEnvelope] = TypeAdapter(RecordEnvelope)


def validate_record_envelope(value: object) -> RecordEnvelope:
    return RECORD_ADAPTER.validate_python(value)


def record_json_schema() -> dict[str, Any]:
    schema = RECORD_ADAPTER.json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://career-os.dev/schemas/record-envelope.schema.json"
    schema["title"] = "Career OS Kind-Specific Record"
    return schema


AUTHORITY_DIRECTORIES = {
    "evidence": "10-career-evidence",
    "strategy": "20-career-strategy",
    "market": "30-role-market",
    "opportunity": "40-opportunity-decision",
    "outlook": "50-career-outlook",
    "readiness": "60-capability-readiness",
    "communication": "70-career-communication",
}


def authority_directory(kind: str) -> str:
    return AUTHORITY_DIRECTORIES[kind.split(".", maxsplit=1)[0]]
