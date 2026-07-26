"""Declarative contracts for the tracked Obsidian view assets.

These describe what a committed Base, Canvas, or homepage must contain. They are
specifications interpreted by the check modules, not copies of the assets: the
Base rules are subset assertions with explicit exact-match opt-ins, so Obsidian
may reformat a file without breaking them. Homepage prose is frozen separately
by digest in `system/homepage-lock.json`.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from ruamel.yaml import YAML

_yaml = YAML(typ="safe")

_CANVAS_ID = re.compile(r"^[0-9a-f]{16}$")
_CJK_TEXT = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_CANVAS_COLORS = {"1", "2", "3", "4", "5", "6"}
_CANVAS_NODE_TYPES = {"text", "file", "link", "group"}
_CANVAS_SIDES = {"top", "right", "bottom", "left"}
_CANVAS_ENDS = {"none", "arrow"}
_WIKILINK = re.compile(r"!?\[\[([^\]\n]+)\]\]")
_MARKDOWN_WIKILINK = re.compile(r"(?P<embed>!)?\[\[(?P<content>[^\]\n]+)\]\]")
_HOMEPAGE_MARKDOWNS = {"en": "Career Home.md", "zh-CN": "职业主页.md"}
_HOMEPAGE_LOCK = "system/homepage-lock.json"
_REQUIRED_CANVAS_ASSETS = {
    "career-map.canvas": "Agent-native architecture overview",
    "career-guide.canvas": "outcome-first workflow guide",
}
_README_CANVAS_IMAGES = (
    (
        "system/obsidian/career-map.canvas",
        "docs/assets/career-map.png",
    ),
    (
        "system/obsidian/career-guide.canvas",
        "docs/assets/career-guide.png",
    ),
)
_BASE_CONTRACTS: dict[str, dict[str, Any]] = {
    "system/obsidian/records.base": {
        "global_filters": (
            'kind.startsWith("evidence.")',
            'kind.startsWith("strategy.")',
            'kind.startsWith("market.")',
            'kind.startsWith("opportunity.")',
            'kind.startsWith("outlook.")',
            'kind.startsWith("readiness.")',
            'kind.startsWith("communication.")',
        ),
        "formula_tokens": {},
        "properties": {
            "kind",
            "status",
            "visibility",
            "migration_review",
            "file.links",
            "updated_at",
        },
        "views": {
            "All records": {
                "columns": {
                    "file.name",
                    "kind",
                    "status",
                    "visibility",
                    "migration_review",
                    "updated_at",
                }
            },
            "Migration review": {
                "filters": ('migration_review == "required"',),
                "columns": {"file.name", "kind", "migration_review", "updated_at"},
                "sort": (("kind", "ASC"), ("updated_at", "DESC")),
            },
        },
    },
    "data/30-role-market/JD 筛选工作台.base": {
        "global_filters": (
            'file.inFolder("__CAREER_OS_DATA_ROOT__/30-role-market/jds")',
            'file.ext == "md"',
            "schema_version == 3",
            'kind == "market.jd"',
        ),
        "exact_global_filters": True,
        "formula_tokens": {
            "priority_rank": ('priority == "p0"', 'priority == "p1"', 'priority == "p2"'),
            "priority_label": ('priority == "p0"', '"P0"', '"Reject"'),
            "evidence_fit_rank": ("evidence_fit == 5", "evidence_fit == 3"),
            "evidence_fit_label": ("evidence_fit == 5", '"⭐⭐⭐⭐⭐"', '"⭐"'),
            "recruiting_scope": ("recruiting_scope_key", '"待核 · "', "employer_name"),
            "is_current": ("is_stale", "false", "true"),
            "stale_label": ("is_stale", '"过时"', '"当前"'),
            "stale_rank": ("is_stale", "1", "0"),
            "gaps_label": ("gap_summary", "gaps", '.join("; ")'),
        },
        "properties": {
            "file.name",
            "collection",
            "employer_name",
            "recruiting_scope_key",
            "formula.recruiting_scope",
            "formula.priority_label",
            "formula.evidence_fit_label",
            "direction_key",
            "career_lane_key",
            "user_review_signal",
            "duplicate_group",
            "preference_signal",
            "growth_signal",
            "next_action_detail",
            "location",
            "compensation",
            "formula.gaps_label",
            "review_note",
            "status",
            "formula.stale_label",
            "file.mtime",
        },
        "exact_properties": True,
        "property_labels": {
            "file.name": "JD",
            "collection": "月份",
            "employer_name": "公司",
            "recruiting_scope_key": "招聘范围 ID",
            "formula.recruiting_scope": "招聘范围",
            "formula.priority_label": "优先级",
            "formula.evidence_fit_label": "经历匹配度",
            "direction_key": "方向",
            "career_lane_key": "Career Lane",
            "user_review_signal": "人工信号",
            "duplicate_group": "近重复组",
            "preference_signal": "偏好",
            "growth_signal": "成长性",
            "next_action_detail": "下一步",
            "location": "地点",
            "compensation": "薪资",
            "formula.gaps_label": "Gap",
            "review_note": "备注",
            "status": "复核状态",
            "formula.stale_label": "当前/过时",
            "file.mtime": "修改时间",
        },
        "views": {
            "当前候选": {
                "filters": (
                    "formula.is_current == true",
                    'status == "reviewed"',
                    '(priority == "p0" || priority == "p1" || priority == "p2")',
                    "evidence_fit >= 1",
                ),
                "exact_filters": True,
                "group_by": ("direction_key", "ASC"),
                "exact_group_by": True,
                "order": (
                    "file.name",
                    "formula.priority_label",
                    "formula.evidence_fit_label",
                    "direction_key",
                    "user_review_signal",
                    "next_action_detail",
                    "location",
                    "compensation",
                    "formula.gaps_label",
                    "review_note",
                ),
                "sort": (
                    ("compensation", "DESC"),
                    ("user_review_signal", "ASC"),
                    ("formula.priority_rank", "ASC"),
                    ("formula.evidence_fit_rank", "ASC"),
                ),
                "exact_sort": True,
                "column_sizes": {
                    "file.name": 288,
                    "formula.priority_label": 52,
                    "formula.evidence_fit_label": 133,
                    "note.direction_key": 216,
                    "note.user_review_signal": 112,
                    "note.next_action_detail": 94,
                    "note.location": 153,
                },
            },
            "同公司投递决策": {
                "filters": (
                    "formula.is_current == true",
                    'status == "reviewed"',
                    '(priority == "p0" || priority == "p1" || priority == "p2")',
                    "evidence_fit >= 3",
                ),
                "exact_filters": True,
                "group_by": ("formula.recruiting_scope", "ASC"),
                "exact_group_by": True,
                "order": (
                    "file.name",
                    "formula.priority_label",
                    "formula.evidence_fit_label",
                    "direction_key",
                    "compensation",
                    "user_review_signal",
                    "preference_signal",
                    "growth_signal",
                    "next_action_detail",
                    "location",
                    "formula.gaps_label",
                    "review_note",
                ),
                "sort": (
                    ("compensation", "DESC"),
                    ("formula.priority_rank", "ASC"),
                    ("formula.evidence_fit_rank", "ASC"),
                ),
                "exact_sort": True,
                "column_sizes": {
                    "file.name": 288,
                    "formula.priority_label": 52,
                    "formula.evidence_fit_label": 133,
                    "note.direction_key": 216,
                    "note.career_lane_key": 120,
                    "note.user_review_signal": 112,
                    "note.duplicate_group": 192,
                    "note.preference_signal": 72,
                    "note.growth_signal": 112,
                    "note.next_action_detail": 94,
                    "note.location": 153,
                    "formula.gaps_label": 240,
                    "note.review_note": 440,
                },
            },
            "待人工复核": {
                "filters": ("formula.is_current == true", 'status == "screened"'),
                "exact_filters": True,
                "exact_group_by": True,
                "order": (
                    "file.name",
                    "formula.priority_label",
                    "formula.evidence_fit_label",
                    "direction_key",
                    "user_review_signal",
                    "next_action_detail",
                    "location",
                    "compensation",
                    "review_note",
                ),
                "sort": (("file.mtime", "DESC"), ("formula.priority_rank", "ASC")),
                "exact_sort": True,
                "column_sizes": {
                    "file.name": 288,
                    "direction_key": 240,
                    "review_note": 440,
                },
            },
            "暂不推进": {
                "filters": (
                    "formula.is_current == true",
                    'status == "reviewed"',
                    '(priority == "p3" || priority == "reject")',
                ),
                "exact_filters": True,
                "exact_group_by": True,
                "order": (
                    "file.name",
                    "formula.priority_label",
                    "formula.evidence_fit_label",
                    "direction_key",
                    "user_review_signal",
                    "next_action_detail",
                    "location",
                    "compensation",
                    "formula.gaps_label",
                    "review_note",
                ),
                "sort": (
                    ("formula.evidence_fit_rank", "ASC"),
                    ("file.mtime", "DESC"),
                ),
                "exact_sort": True,
                "column_sizes": {
                    "file.name": 288,
                    "formula.priority_label": 89,
                    "formula.evidence_fit_label": 133,
                    "note.direction_key": 216,
                    "note.user_review_signal": 112,
                    "note.next_action_detail": 94,
                    "note.location": 153,
                    "formula.gaps_label": 240,
                    "note.review_note": 440,
                },
            },
            "全部": {
                "filters": (),
                "exact_filters": True,
                "exact_group_by": True,
                "order": (
                    "file.name",
                    "formula.priority_label",
                    "formula.evidence_fit_label",
                    "direction_key",
                    "user_review_signal",
                    "next_action_detail",
                    "location",
                    "compensation",
                    "collection",
                    "formula.stale_label",
                    "status",
                    "file.mtime",
                ),
                "sort": (
                    ("formula.stale_rank", "ASC"),
                    ("collection", "DESC"),
                    ("formula.priority_rank", "ASC"),
                    ("file.mtime", "DESC"),
                ),
                "exact_sort": True,
                "column_sizes": {"file.name": 288, "direction_key": 240},
            },
        },
    },
    "data/30-role-market/招聘渠道.base": {
        "global_filters": (
            'file.inFolder("__CAREER_OS_DATA_ROOT__/30-role-market/channels")',
            'file.ext == "md"',
            "schema_version == 3",
            'kind == "market.channel"',
            'status == "active"',
        ),
        "formula_tokens": {
            "career_lanes": (
                "list(career_lane)",
                "value.asFile().asLink(value.asFile().basename)",
            )
        },
        "properties": {
            "tier",
            "role",
            "formula.career_lanes",
            "last_verified_at",
            "url",
            "rank",
        },
        "views": {
            "当前渠道": {
                "columns": {
                    "file.name",
                    "tier",
                    "role",
                    "formula.career_lanes",
                    "last_verified_at",
                    "url",
                },
                "sort": (("rank", "ASC"),),
            }
        },
    },
    "data/40-opportunity-decision/Company Portfolio.base": {
        "global_filters": (
            'file.inFolder("__CAREER_OS_DATA_ROOT__/40-opportunity-decision/companies")',
            'file.ext == "md"',
            "schema_version == 3",
            'kind == "opportunity.company"',
        ),
        "formula_tokens": {
            "effective_review_state": (
                "review_status",
                "last_researched_at",
                "assessment_status",
                "refresh_due",
            ),
            "metadata_issues": ("last_researched_at", "refresh_due", "reviewed_at"),
            "related_engagements": (
                "file.backlinks",
                'value.asFile().properties.kind == "opportunity.engagement"',
                "value.asFile().asLink(value.asFile().basename)",
            ),
        },
        "properties": {
            "display_name_zh",
            "display_name_en",
            "watch_state",
            "company_lifecycle",
            "research_level",
            "assessment_status",
            "strength",
            "business_outlook",
            "employer_quality",
            "career_alignment",
            "risk",
            "confidence",
            "trend",
            "review_status",
            "reviewed_at",
            "last_researched_at",
            "refresh_due",
            "next_action",
            "formula.related_engagements",
        },
        "views": {
            "总表": {
                "group_by": ("watch_state", "ASC"),
                "columns": {
                    "file.name",
                    "display_name_zh",
                    "display_name_en",
                    "company_lifecycle",
                    "research_level",
                    "assessment_status",
                    "formula.effective_review_state",
                    "strength",
                    "business_outlook",
                    "employer_quality",
                    "career_alignment",
                    "risk",
                    "confidence",
                    "trend",
                    "last_researched_at",
                    "refresh_due",
                    "next_action",
                    "formula.related_engagements",
                },
                "sort": (
                    ("formula.watch_rank", "ASC"),
                    ("formula.risk_rank", "ASC"),
                    ("refresh_due", "ASC"),
                ),
            },
            "比较": {
                "columns": {
                    "file.name",
                    "display_name_zh",
                    "display_name_en",
                    "watch_state",
                    "strength",
                    "business_outlook",
                    "employer_quality",
                    "career_alignment",
                    "risk",
                    "confidence",
                    "trend",
                    "research_level",
                    "assessment_status",
                    "formula.effective_review_state",
                },
                "sort": (
                    ("formula.watch_rank", "ASC"),
                    ("formula.risk_rank", "ASC"),
                    ("file.name", "ASC"),
                ),
            },
            "审核": {
                "filters": (
                    'formula.effective_review_state != "reviewed"',
                    "!formula.metadata_issues.isEmpty()",
                ),
                "columns": {
                    "file.name",
                    "display_name_zh",
                    "display_name_en",
                    "watch_state",
                    "assessment_status",
                    "formula.effective_review_state",
                    "review_status",
                    "reviewed_at",
                    "last_researched_at",
                    "refresh_due",
                    "risk",
                    "confidence",
                    "formula.metadata_issues",
                    "next_action",
                },
                "sort": (
                    ("formula.effective_review_state", "ASC"),
                    ("refresh_due", "ASC"),
                ),
            },
        },
    },
    "data/40-opportunity-decision/Engagement Decisions.base": {
        "global_filters": (
            'file.inFolder("__CAREER_OS_DATA_ROOT__/40-opportunity-decision/engagements")',
            'file.ext == "md"',
            "schema_version == 3",
            'kind == "opportunity.engagement"',
        ),
        "formula_tokens": {
            "company_link": (
                "company.asFile()",
                "company.asFile().asLink(company.asFile().basename)",
            ),
            "target_jd_link": (
                "target_jd.asFile()",
                "target_jd.asFile().asLink(target_jd.asFile().basename)",
            ),
            "company_business_outlook": ("company.asFile()", "business_outlook"),
            "company_employer_quality": ("company.asFile()", "employer_quality"),
            "company_risk": ("company.asFile()", "properties.risk"),
            "company_confidence": ("company.asFile()", "properties.confidence"),
            "effective_review_state": ("review_status", "reviewed_at", "updated_at"),
            "interview_phase": (
                'stage == "applied"',
                'stage == "interviewing"',
                'stage == "offer"',
            ),
            "interview_phase_rank": (
                'stage == "applied"',
                'stage == "interviewing"',
                'stage == "offer"',
            ),
            "checkpoint_rank": ("review_on.isEmpty()",),
            "relationship_issues": (
                "file.links",
                'properties.kind != "opportunity.company"',
                'properties.kind != "market.jd"',
            ),
        },
        "properties": {
            "formula.company_link",
            "formula.target_jd_link",
            "formula.interview_phase",
            "engagement_type",
            "stage",
            "application_state",
            "decision_state",
            "role",
            "team",
            "started_on",
            "review_on",
            "strategy_fit",
            "opportunity_quality",
            "confidence",
            "review_status",
            "reviewed_at",
            "next_action",
            "updated_at",
        },
        "views": {
            "决策总表": {
                "group_by": ("decision_state", "ASC"),
                "columns": {
                    "file.name",
                    "formula.company_link",
                    "engagement_type",
                    "stage",
                    "role",
                    "team",
                    "started_on",
                    "review_on",
                    "formula.effective_review_state",
                    "strategy_fit",
                    "opportunity_quality",
                    "confidence",
                    "formula.company_business_outlook",
                    "formula.company_employer_quality",
                    "formula.company_risk",
                    "formula.company_confidence",
                    "next_action",
                    "updated_at",
                },
                "sort": (("updated_at", "DESC"), ("file.name", "ASC")),
            },
            "审核": {
                "filters": (
                    'formula.effective_review_state != "reviewed"',
                    "!formula.metadata_issues.isEmpty()",
                    "!formula.relationship_issues.isEmpty()",
                    "!formula.company_attention.isEmpty()",
                ),
                "columns": {
                    "file.name",
                    "formula.company_link",
                    "formula.target_jd_link",
                    "decision_state",
                    "formula.effective_review_state",
                    "review_status",
                    "reviewed_at",
                    "updated_at",
                    "formula.relationship_issues",
                    "formula.metadata_issues",
                    "formula.company_attention",
                    "next_action",
                },
                "sort": (
                    ("formula.effective_review_state", "ASC"),
                    ("updated_at", "DESC"),
                ),
            },
            "Application tracking": {
                "filters": ('application_state != "not-applied"',),
                "columns": {
                    "file.name",
                    "formula.company_link",
                    "status",
                    "engagement_type",
                    "stage",
                    "application_state",
                    "role",
                    "team",
                    "next_action",
                    "updated_at",
                },
                "sort": (("updated_at", "DESC"),),
            },
            "面试进度": {
                "filters": (
                    'status != "closed"',
                    'stage == "applied"',
                    'stage == "interviewing"',
                    'stage == "offer"',
                ),
                "exact_filters": True,
                "order": (
                    "file.name",
                    "formula.company_link",
                    "formula.target_jd_link",
                    "formula.interview_phase",
                    "status",
                    "application_state",
                    "engagement_type",
                    "role",
                    "team",
                    "review_on",
                    "next_action",
                    "formula.effective_review_state",
                    "updated_at",
                ),
                "sort": (
                    ("formula.interview_phase_rank", "ASC"),
                    ("formula.checkpoint_rank", "ASC"),
                    ("review_on", "ASC"),
                    ("updated_at", "DESC"),
                    ("file.name", "ASC"),
                ),
                "exact_sort": True,
            },
        },
    },
    "data/60-capability-readiness/Capability Readiness.base": {
        "global_filters": (
            'file.ext == "md"',
            "schema_version == 3",
            'kind.startsWith("readiness.")',
            'kind == "evidence.story"',
            'kind == "communication.audit"',
        ),
        "formula_tokens": {
            "session_age_days": ("session_date", ".days"),
            "readiness_kind": (
                'kind == "communication.audit"',
                'kind == "readiness.session"',
                'kind == "readiness.gap"',
                'kind == "evidence.story"',
            ),
            "target_jd_link": (
                "list(target_jd)",
                "value.asFile().asLink(value.asFile().basename)",
            ),
            "career_lanes": (
                "list(career_lane)",
                "value.asFile().asLink(value.asFile().basename)",
            ),
            "experience_stories": (
                "list(experience_story)",
                "value.asFile().asLink(value.asFile().basename)",
            ),
            "resume_audit_link": (
                "list(resume_audit)",
                "value.asFile().asLink(value.asFile().basename)",
            ),
            "last_retest_links": (
                "list(last_retest)",
                "value.asFile().asLink(value.asFile().basename)",
            ),
            "closure_evidence_links": (
                "list(closure_evidence)",
                "value.asFile().asLink(value.asFile().basename)",
            ),
            "resume_roots": (
                "list(resume_root)",
                "value.asFile().asLink(value.asFile().basename)",
            ),
        },
        "properties": {
            "formula.readiness_kind",
            "session_date",
            "formula.session_age_days",
            "formula.career_lanes",
            "target",
            "formula.target_jd_link",
            "formula.experience_stories",
            "formula.resume_audit_link",
            "session_type",
            "scope",
            "fact_boundary",
            "technical_depth",
            "answer_structure",
            "tradeoff_resilience",
            "blocking_red_flag",
            "verdict",
            "attempt",
            "gap_type",
            "status",
            "priority",
            "formula.last_retest_links",
            "formula.closure_evidence_links",
            "story_role",
            "readiness_state",
            "audit_date",
            "career_lane",
            "formula.resume_roots",
            "source_fingerprint",
            "blocking_findings",
            "confirmation_count",
            "user_confirmed",
        },
        "views": {
            "最新 Strict": {
                "filters": (
                    'kind == "readiness.session"',
                    'session_type == "strict"',
                    'verdict != "historical"',
                ),
                "columns": {
                    "file.name",
                    "session_date",
                    "formula.session_age_days",
                    "formula.career_lanes",
                    "target",
                    "formula.target_jd_link",
                    "formula.experience_stories",
                    "formula.resume_audit_link",
                    "scope",
                    "verdict",
                    "fact_boundary",
                    "technical_depth",
                    "answer_structure",
                    "tradeoff_resilience",
                    "blocking_red_flag",
                },
                "sort": (("session_date", "DESC"),),
            },
            "JD 准备输入": {
                "filters": ('target == "jd"', 'kind == "readiness.gap"'),
                "columns": {
                    "file.name",
                    "formula.readiness_kind",
                    "formula.target_jd_link",
                    "formula.career_lanes",
                    "session_type",
                    "verdict",
                    "session_date",
                    "attempt",
                    "priority",
                    "gap_type",
                    "status",
                },
                "sort": (("session_date", "DESC"),),
            },
            "Open/Blocked Gaps": {
                "filters": (
                    'kind == "readiness.gap"',
                    '(status == "open" || status == "learning" || '
                    'status == "practice" || status == "retest" || '
                    'status == "blocked")',
                ),
                "columns": {
                    "file.name",
                    "formula.career_lanes",
                    "priority",
                    "gap_type",
                    "status",
                    "formula.target_jd_link",
                    "formula.last_retest_links",
                    "formula.closure_evidence_links",
                },
                "sort": (("priority", "ASC"), ("updated_at", "DESC")),
            },
            "Retest Queue": {
                "filters": (
                    'kind == "readiness.gap" && status == "retest"',
                    'kind == "readiness.session" && verdict == "not-ready"',
                ),
                "columns": {
                    "file.name",
                    "formula.readiness_kind",
                    "formula.career_lanes",
                    "scope",
                    "attempt",
                    "formula.last_retest_links",
                    "gap_type",
                    "status",
                    "updated_at",
                },
                "sort": (("updated_at", "DESC"),),
            },
            "Primary Experience Stories": {
                "filters": ('kind == "evidence.story"', 'story_role == "primary"'),
                "columns": {
                    "file.name",
                    "formula.career_lanes",
                    "story_role",
                    "readiness_state",
                    "updated_at",
                },
                "sort": (("file.name", "ASC"),),
            },
            "当前 Resume Audit": {
                "filters": ('kind == "communication.audit"',),
                "columns": {
                    "file.name",
                    "audit_date",
                    "scope",
                    "career_lane",
                    "formula.resume_roots",
                    "source_fingerprint",
                    "status",
                    "blocking_findings",
                    "confirmation_count",
                    "user_confirmed",
                },
                "sort": (("audit_date", "DESC"),),
            },
            "Claim 确认队列": {
                "filters": ('kind == "communication.audit"', "confirmation_count > 0"),
                "columns": {
                    "file.name",
                    "career_lane",
                    "status",
                    "confirmation_count",
                    "updated_at",
                },
                "sort": (("updated_at", "DESC"),),
            },
            "Experience Story 压测队列": {
                "filters": (
                    'kind == "evidence.story"',
                    'story_role == "primary"',
                    'readiness_state != "ready"',
                ),
                "columns": {
                    "file.name",
                    "formula.career_lanes",
                    "story_role",
                    "readiness_state",
                    "updated_at",
                },
                "sort": (("file.name", "ASC"),),
            },
        },
    },
}
_WORKBENCH_BASE_PAIRS = (
    (
        "data/30-role-market/招聘渠道.base",
        "system/obsidian/bases/en/Recruiting Channels.base",
        "system/obsidian/bases/zh-CN/招聘渠道.base",
        (("当前渠道", "Current Channels", "当前渠道"),),
        (
            'file.ext == "md"',
            "schema_version == 3",
            'kind == "market.channel"',
            'status == "active"',
        ),
    ),
    (
        "data/30-role-market/JD 筛选工作台.base",
        "system/obsidian/bases/en/JD Screening.base",
        "system/obsidian/bases/zh-CN/JD 筛选工作台.base",
        (
            ("当前候选", "Current Candidates", "当前候选"),
            (
                "同公司投递决策",
                "Same-Company Application Decisions",
                "同公司投递决策",
            ),
            ("待人工复核", "Manual Review", "待人工复核"),
            ("暂不推进", "On Hold", "暂不推进"),
            ("全部", "All", "全部"),
        ),
        ('file.ext == "md"', "schema_version == 3", 'kind == "market.jd"'),
    ),
    (
        "data/40-opportunity-decision/Company Portfolio.base",
        "system/obsidian/bases/en/Company Portfolio.base",
        "system/obsidian/bases/zh-CN/公司组合.base",
        (
            ("总表", "Portfolio", "总表"),
            ("比较", "Compare", "比较"),
            ("审核", "Review", "审核"),
        ),
        (
            'file.ext == "md"',
            "schema_version == 3",
            'kind == "opportunity.company"',
        ),
    ),
    (
        "data/40-opportunity-decision/Engagement Decisions.base",
        "system/obsidian/bases/en/Engagement Decisions.base",
        "system/obsidian/bases/zh-CN/招聘互动决策.base",
        (
            ("决策总表", "Decision Overview", "决策总表"),
            ("审核", "Review", "审核"),
            ("Application tracking", "Application Tracking", "申请进展"),
            ("面试进度", "Interview Pipeline", "面试进度"),
        ),
        (
            'file.ext == "md"',
            "schema_version == 3",
            'kind == "opportunity.engagement"',
        ),
    ),
    (
        "data/60-capability-readiness/Capability Readiness.base",
        "system/obsidian/bases/en/Capability Readiness.base",
        "system/obsidian/bases/zh-CN/能力准备度.base",
        (
            ("最新 Strict", "Latest Strict", "最新严格评估"),
            ("JD 准备输入", "JD Preparation Inputs", "JD 准备输入"),
            ("Open/Blocked Gaps", "Open/Blocked Gaps", "待补或阻塞差距"),
            ("Retest Queue", "Retest Queue", "复测队列"),
            (
                "Primary Experience Stories",
                "Primary Experience Stories",
                "主要经历故事",
            ),
            ("当前 Resume Audit", "Current Resume Audit", "当前简历审核"),
            ("Claim 确认队列", "Claim Confirmation Queue", "主张确认队列"),
            (
                "Experience Story 压测队列",
                "Experience Story Stress-Test Queue",
                "经历故事压测队列",
            ),
        ),
        (
            'file.ext == "md"',
            "schema_version == 3",
            'kind.startsWith("readiness.")',
            'kind == "evidence.story"',
            'kind == "communication.audit"',
        ),
    ),
)
_RECENT_BASE_PAIR = (
    "system/obsidian/bases/en/Recent Changes.base",
    "system/obsidian/bases/zh-CN/最近改动.base",
)
_RECENT_BASE_PROJECT_FILTER = (
    'file.inFolder(file("Career Home.md").folder)'
)

for (
    _legacy_path,
    _english_path,
    _chinese_path,
    _view_names,
    _global_filters,
) in _WORKBENCH_BASE_PAIRS:
    _english_contract = _BASE_CONTRACTS.pop(_legacy_path)
    _english_contract["global_filters"] = _global_filters
    _english_contract["exact_global_filters"] = True
    _english_contract.pop("property_labels", None)
    _english_contract["views"] = {
        english_name: _english_contract["views"][legacy_name]
        for legacy_name, english_name, _chinese_name in _view_names
    }
    if _english_path.endswith("JD Screening.base"):
        _english_contract["formula_tokens"]["recruiting_scope"] = (
            "recruiting_scope_key",
            '"Pending review · "',
            "employer_name",
        )
        _english_contract["formula_tokens"]["stale_label"] = (
            "is_stale",
            '"Stale"',
            '"Current"',
        )
    if _english_path.endswith("Company Portfolio.base"):
        _english_contract["formula_tokens"]["related_engagements"] = (
            "file.backlinks",
            'value.asFile().properties.kind == "opportunity.engagement"',
            "value.asFile().asLink(value.asFile().basename)",
        )
    if _english_path.endswith("Engagement Decisions.base"):
        _english_contract["formula_tokens"]["interview_phase"] = (
            'stage == "applied"',
            'stage == "interviewing"',
            'stage == "offer"',
            '"Awaiting interview"',
            '"Interviewing"',
            '"Offer"',
        )
    _BASE_CONTRACTS[_english_path] = _english_contract

    _chinese_contract = deepcopy(_english_contract)
    _chinese_contract["views"] = {
        chinese_name: _chinese_contract["views"][english_name]
        for _legacy_name, english_name, chinese_name in _view_names
    }
    if _chinese_path.endswith("招聘互动决策.base"):
        _chinese_contract["formula_tokens"]["interview_phase"] = (
            'stage == "applied"',
            'stage == "interviewing"',
            'stage == "offer"',
            '"待面试"',
            '"面试中"',
            '"Offer"',
        )
    _BASE_CONTRACTS[_chinese_path] = _chinese_contract

_ENGLISH_WORKBENCH_BASES = frozenset(pair[1] for pair in _WORKBENCH_BASE_PAIRS)
_CHINESE_WORKBENCH_BASES = frozenset(pair[2] for pair in _WORKBENCH_BASE_PAIRS)
_ENGLISH_LOCALIZED_BASES = _ENGLISH_WORKBENCH_BASES | {_RECENT_BASE_PAIR[0]}
_CHINESE_LOCALIZED_BASES = _CHINESE_WORKBENCH_BASES | {_RECENT_BASE_PAIR[1]}
_LOCALIZED_BASE_PAIRS = tuple(
    (english_path, chinese_path)
    for _legacy_path, english_path, chinese_path, _views, _filters in (
        _WORKBENCH_BASE_PAIRS
    )
) + (_RECENT_BASE_PAIR,)
_RECENT_BASE_CONTRACT: dict[str, Any] = {
    "global_filters": (
        'file.ext == "md"',
        _RECENT_BASE_PROJECT_FILTER,
    ),
    "exact_global_filters": True,
    "formula_tokens": {},
    "properties": {
        "file.name",
        "file.folder",
        "file.mtime",
    },
    "exact_properties": True,
    "property_labels": {
        "file.name": "File",
        "file.folder": "Folder",
        "file.mtime": "Modified",
    },
    "views": {
        "Recent 10": {
            "type": "table",
            "limit": 10,
            "order": (
                "file.name",
                "file.folder",
                "file.mtime",
            ),
            "sort": (
                ("file.mtime", "DESC"),
                ("file.path", "ASC"),
            ),
            "exact_sort": True,
        }
    },
}
_BASE_CONTRACTS[_RECENT_BASE_PAIR[0]] = _RECENT_BASE_CONTRACT
_RECENT_BASE_CHINESE_CONTRACT = deepcopy(_RECENT_BASE_CONTRACT)
_RECENT_BASE_CHINESE_CONTRACT["property_labels"] = {
    "file.name": "文件",
    "file.folder": "目录",
    "file.mtime": "修改时间",
}
_RECENT_BASE_CHINESE_CONTRACT["views"] = {
    "最近 10 个": _RECENT_BASE_CHINESE_CONTRACT["views"].pop("Recent 10")
}
_BASE_CONTRACTS[_RECENT_BASE_PAIR[1]] = _RECENT_BASE_CHINESE_CONTRACT
_AUTHORITY_CONTRACT_PATHS = {
    "system/seeds/authorities/10-career-evidence.md",
    "system/seeds/authorities/20-career-strategy.md",
    "system/seeds/authorities/30-role-market.md",
    "system/seeds/authorities/40-opportunity-decision.md",
    "system/seeds/authorities/50-career-outlook.md",
    "system/seeds/authorities/60-capability-readiness.md",
    "system/seeds/authorities/70-career-communication.md",
}
_HOMEPAGE_WORKBENCH_LINKS = (
    ("Recent Changes.base#Recent 10", "Open Recent Changes"),
    ("Recruiting Channels.base#Current Channels", "Open Recruiting Channels"),
    ("JD Screening.base#Current Candidates", "Open JD Screening"),
    ("Company Portfolio.base#Portfolio", "Open Company Portfolio"),
    ("Engagement Decisions.base#Decision Overview", "Open Engagement Decisions"),
    ("Capability Readiness.base#Latest Strict", "Open Capability Readiness"),
)
_HOMEPAGE_CHINESE_WORKBENCH_LINKS = (
    ("最近改动.base#最近 10 个", "打开最近改动"),
    ("招聘渠道.base#当前渠道", "打开招聘渠道"),
    ("JD 筛选工作台.base#当前候选", "打开 JD 筛选"),
    ("公司组合.base#总表", "打开公司组合"),
    ("招聘互动决策.base#决策总表", "打开招聘互动决策"),
    ("能力准备度.base#最新严格评估", "打开能力准备度"),
)
_HOMEPAGE_SECONDARY_VIEW_LINKS = (
    ("Engagement Decisions.base#Interview Pipeline", "Open Interview Pipeline"),
)
_HOMEPAGE_CHINESE_SECONDARY_VIEW_LINKS = (
    ("招聘互动决策.base#面试进度", "打开面试进度"),
)
_HOMEPAGE_FRAMEWORK_LINKS = (
    ("职业主页.md", "Open Chinese Home"),
    ("records.base", "Open All Records"),
    ("dashboard.md", "Open Text Dashboard"),
    ("career-map.canvas", "Open Architecture Map"),
    ("career-guide.canvas", "Open Workflow Guide"),
)
_HOMEPAGE_CHINESE_FRAMEWORK_LINKS = (
    ("Career Home.md", "English Home"),
    ("records.base", "全部记录"),
    ("dashboard.md", "文本仪表盘"),
    ("career-map.canvas", "架构图"),
    ("career-guide.canvas", "工作流指南"),
)
_HOMEPAGE_AUTHORITY_LINKS = (
    ("10-career-evidence.md", "Career Evidence"),
    ("20-career-strategy.md", "Career Strategy"),
    ("30-role-market.md", "Role Market"),
    ("40-opportunity-decision.md", "Opportunity Decision"),
    ("50-career-outlook.md", "Career Outlook"),
    ("60-capability-readiness.md", "Capability Readiness"),
    ("70-career-communication.md", "Career Communication"),
)
_HOMEPAGE_CHINESE_AUTHORITY_LINKS = (
    ("10-career-evidence.md", "职业证据"),
    ("20-career-strategy.md", "职业策略"),
    ("30-role-market.md", "职位市场"),
    ("40-opportunity-decision.md", "机会决策"),
    ("50-career-outlook.md", "职业展望"),
    ("60-capability-readiness.md", "能力准备度"),
    ("70-career-communication.md", "职业沟通"),
)
_HOMEPAGE_WORKBENCH_FILES = frozenset(
    target.split("#", maxsplit=1)[0]
    for target, _alias in (
        *_HOMEPAGE_WORKBENCH_LINKS,
        *_HOMEPAGE_CHINESE_WORKBENCH_LINKS,
        *_HOMEPAGE_SECONDARY_VIEW_LINKS,
        *_HOMEPAGE_CHINESE_SECONDARY_VIEW_LINKS,
    )
)
_HOMEPAGE_HEADINGS = {
    "en": (
    "# Career Home",
    "## Recent Changes",
    "## Discover",
    "### Recruiting Channels",
    "### JD Screening",
    "## Decide",
    "### Company Portfolio",
    "### Engagement Decisions",
    "## Prepare",
    "### Capability Readiness",
    "## Authority Contracts",
    ),
    "zh-CN": (
        "# 职业主页",
        "## 最近改动",
        "## 发现机会",
        "### 招聘渠道",
        "### JD 筛选",
        "## 做出决策",
        "### 公司组合",
        "### 招聘互动决策",
        "## 准备能力",
        "### 能力准备度",
        "## 权威契约",
    ),
}
_TASK_CARD_FIELDS = (
    "**Say:**",
    "**Agent:**",
    "**Skills:**",
    "**Authority:**",
    "**Result:**",
    "**Gate:**",
    "**Verify:**",
)
_CANVAS_LAYOUT_LIMITS: dict[str, tuple[int, int, float, float, float, int]] = {
    "career-map.canvas": (3600, 1850, 1.85, 2.10, 0.54, 3000),
    "career-guide.canvas": (3900, 1900, 1.90, 2.15, 0.62, 8000),
}
