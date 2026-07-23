from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from copy import deepcopy
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from career_os import __version__
from career_os.config import INSTALL_STATE, ProjectPaths, load_project_config
from career_os.downstream import downstream_sync_validation_json_schema
from career_os.git_safety import inspect_downstream_git_safety
from career_os.imports import (
    import_manifest_json_schema,
    inventory_rules_json_schema,
    migration_inventory_json_schema,
    migration_provenance_json_schema,
)
from career_os.public_privacy import PublicPrivacyError, audit_public_repository
from career_os.records import (
    ParsedRecord,
    load_record,
    record_json_schema,
)
from career_os.records.models import authority_directory
from career_os.records.semantics import check_record_semantics
from career_os.resume.fonts import (
    font_manifest_json_schema,
    load_font_manifest,
)
from career_os.resume.privacy import load_secret_patterns
from career_os.resume.service import list_resumes, validate_resume_source
from career_os.reviewer_contracts import (
    evidence_audit_json_schema,
    interview_probe_json_schema,
)
from career_os.sbom import verify_sbom
from career_os.semantic_review import (
    load_semantic_file_review,
    semantic_file_review_json_schema,
    semantic_review_amendment_json_schema,
    semantic_review_completion_json_schema,
    semantic_review_supersession_json_schema,
    verify_semantic_file_review,
    verify_semantic_review_amendment,
    verify_semantic_review_completion,
    verify_semantic_review_supersession,
)
from career_os.skills import verify_skills

_yaml = YAML(typ="safe")

_CANVAS_ID = re.compile(r"^[0-9a-f]{16}$")
_CJK_TEXT = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_CANVAS_COLORS = {"1", "2", "3", "4", "5", "6"}
_CANVAS_NODE_TYPES = {"text", "file", "link", "group"}
_CANVAS_SIDES = {"top", "right", "bottom", "left"}
_CANVAS_ENDS = {"none", "arrow"}
_WIKILINK = re.compile(r"!?\[\[([^\]\n]+)\]\]")
_MARKDOWN_WIKILINK = re.compile(r"(?P<embed>!)?\[\[(?P<content>[^\]\n]+)\]\]")
_HOMEPAGE_MARKDOWNS = {"en": "Home.md", "zh-CN": "主页.md"}
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
        "formula_tokens": {
            "required_internal_refs": ("refs", "value.required == true", ".length"),
            "required_host_refs": ("host_refs", "value.required == true", ".length"),
            "host_reference_state": (
                "formula.required_internal_refs",
                "formula.required_host_refs",
            ),
        },
        "properties": {
            "kind",
            "status",
            "visibility",
            "migration_review",
            "refs",
            "host_refs",
            "formula.host_reference_state",
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
            "Host reference health": {
                "filters": (
                    "formula.required_internal_refs > 0",
                    "formula.required_host_refs > 0",
                ),
                "columns": {
                    "file.name",
                    "kind",
                    "formula.host_reference_state",
                    "refs",
                    "host_refs",
                },
                "sort": (
                    ("formula.host_reference_state", "ASC"),
                    ("kind", "ASC"),
                ),
            },
        },
    },
    "data/30-role-market/JD 筛选工作台.base": {
        "global_filters": (
            'file.inFolder("__CAREER_OS_DATA_ROOT__/30-role-market/jds")',
            'file.ext == "md"',
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
            'kind == "market.channel"',
            'status == "active"',
        ),
        "formula_tokens": {
            "career_lanes": (
                'value.relation == "career-lane"',
                "file(value.path).asLink(file(value.path).basename)",
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
                "career/40-opportunity-decision/engagements",
                "value.asLink(value.basename)",
            ),
        },
        "properties": {
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
            'kind == "opportunity.engagement"',
        ),
        "formula_tokens": {
            "company_path": ("host_refs", 'value.relation == "company"', "value.path"),
            "company": (
                "file(formula.company_path)",
                ".asLink(file(formula.company_path).basename)",
            ),
            "target_jd_path": ('value.relation == "target-jd"', "value.path"),
            "target_jd": (
                "file(formula.target_jd_path)",
                ".asLink(file(formula.target_jd_path).basename)",
            ),
            "effective_review_state": ("review_status", "reviewed_at", "updated_at"),
            "relationship_issues": (
                "formula.company_path",
                'properties.kind != "opportunity.company"',
                'properties.kind != "market.jd"',
            ),
        },
        "properties": {
            "formula.company",
            "formula.target_jd",
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
                    "formula.company",
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
                    "formula.company",
                    "formula.target_jd",
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
                    "formula.company",
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
        },
    },
    "data/60-capability-readiness/Capability Readiness.base": {
        "global_filters": (
            'file.ext == "md"',
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
            "target_jd_path": ('value.relation == "target-jd"', "value.path"),
            "target_jd": (
                "file(formula.target_jd_path)",
                ".asLink(file(formula.target_jd_path).basename)",
            ),
            "career_lanes": (
                'value.relation == "career-lane"',
                "file(value.path).asLink(file(value.path).basename)",
            ),
            "experience_stories": (
                'value.relation == "experience-story"',
                "file(value.path).asLink(file(value.path).basename)",
            ),
            "resume_audit_path": ('value.relation == "resume-audit"', "value.path"),
            "resume_audit": (
                "file(formula.resume_audit_path)",
                ".asLink(file(formula.resume_audit_path).basename)",
            ),
            "last_retest": (
                'value.relation == "last-retest"',
                "file(value.path).asLink(file(value.path).basename)",
            ),
            "closure_evidence": (
                'value.relation == "closure-evidence"',
                "file(value.path).asLink(file(value.path).basename)",
            ),
            "resume_roots": (
                'value.relation == "resume-root"',
                "file(value.path).asLink(file(value.path).basename)",
            ),
        },
        "properties": {
            "formula.readiness_kind",
            "session_date",
            "formula.session_age_days",
            "formula.career_lanes",
            "target",
            "formula.target_jd",
            "formula.experience_stories",
            "formula.resume_audit",
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
            "formula.last_retest",
            "formula.closure_evidence",
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
                    "formula.target_jd",
                    "formula.experience_stories",
                    "formula.resume_audit",
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
                    "formula.target_jd",
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
                    "formula.target_jd",
                    "formula.last_retest",
                    "formula.closure_evidence",
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
                    "formula.last_retest",
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
            "schema_version == 2",
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
        ('file.ext == "md"', "schema_version == 2", 'kind == "market.jd"'),
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
            "schema_version == 2",
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
        ),
        (
            'file.ext == "md"',
            "schema_version == 2",
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
            "schema_version == 2",
            'kind.startsWith("readiness.")',
            'kind == "evidence.story"',
            'kind == "communication.audit"',
        ),
    ),
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
            'value.properties.kind == "opportunity.engagement"',
            "value.asLink(value.basename)",
        )
    _BASE_CONTRACTS[_english_path] = _english_contract

    _chinese_contract = deepcopy(_english_contract)
    _chinese_contract["views"] = {
        chinese_name: _chinese_contract["views"][english_name]
        for _legacy_name, english_name, chinese_name in _view_names
    }
    _BASE_CONTRACTS[_chinese_path] = _chinese_contract

_ENGLISH_WORKBENCH_BASES = frozenset(pair[1] for pair in _WORKBENCH_BASE_PAIRS)
_CHINESE_WORKBENCH_BASES = frozenset(pair[2] for pair in _WORKBENCH_BASE_PAIRS)
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
    ("Recruiting Channels.base#Current Channels", "Open Recruiting Channels"),
    ("JD Screening.base#Current Candidates", "Open JD Screening"),
    ("Company Portfolio.base#Portfolio", "Open Company Portfolio"),
    ("Engagement Decisions.base#Decision Overview", "Open Engagement Decisions"),
    ("Capability Readiness.base#Latest Strict", "Open Capability Readiness"),
)
_HOMEPAGE_CHINESE_WORKBENCH_LINKS = (
    ("招聘渠道.base#当前渠道", "打开招聘渠道"),
    ("JD 筛选工作台.base#当前候选", "打开 JD 筛选"),
    ("公司组合.base#总表", "打开公司组合"),
    ("招聘互动决策.base#决策总表", "打开招聘互动决策"),
    ("能力准备度.base#最新严格评估", "打开能力准备度"),
)
_HOMEPAGE_FRAMEWORK_LINKS = (
    ("主页.md", "Open Chinese Home"),
    ("records.base", "Open All Records"),
    ("dashboard.md", "Open Text Dashboard"),
    ("career-map.canvas", "Open Architecture Map"),
    ("career-guide.canvas", "Open Workflow Guide"),
)
_HOMEPAGE_CHINESE_FRAMEWORK_LINKS = (
    ("Home.md", "English Home"),
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
    )
)
_HOMEPAGE_HEADINGS = {
    "en": (
    "# Career Home",
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
_HOMEPAGE_CANONICAL_TEXT = {
    "en": (
    """---
tags: [career-os, framework-view]
---
# Career Home

> [!tip] Agent-first
> Tell an Agent the outcome you want. Then open the workbench that owns the next decision.
> Views navigate canonical records; they do not own career facts.
>
> [[主页.md|Open Chinese Home]]
>
> """
    "[[records.base|Open All Records]] · "
    "[[dashboard.md|Open Text Dashboard]] · "
    "[[career-map.canvas|Open Architecture Map]] · "
    "[[career-guide.canvas|Open Workflow Guide]]\n"
    """
## Discover

### Recruiting Channels

Review dated sources and channel quality.

[[Recruiting Channels.base#Current Channels|Open Recruiting Channels]]

![[Recruiting Channels.base#Current Channels]]

### JD Screening

Compare role fit without promoting readiness or evidence.

[[JD Screening.base#Current Candidates|Open JD Screening]]

![[JD Screening.base#Current Candidates]]

## Decide

### Company Portfolio

Compare companies independently from role fit and engagement state.

[[Company Portfolio.base#Portfolio|Open Company Portfolio]]

![[Company Portfolio.base#Portfolio]]

### Engagement Decisions

Review bounded recruiting scopes, contacts, processes, and decisions.

[[Engagement Decisions.base#Decision Overview|Open Engagement Decisions]]

![[Engagement Decisions.base#Decision Overview]]

## Prepare

### Capability Readiness

Inspect evidence-backed gaps, practice, and retest status.

[[Capability Readiness.base#Latest Strict|Open Capability Readiness]]

![[Capability Readiness.base#Latest Strict]]

## Authority Contracts

- [[10-career-evidence.md|Career Evidence]]
- [[20-career-strategy.md|Career Strategy]]
- [[30-role-market.md|Role Market]]
- [[40-opportunity-decision.md|Opportunity Decision]]
- [[50-career-outlook.md|Career Outlook]]
- [[60-capability-readiness.md|Capability Readiness]]
- [[70-career-communication.md|Career Communication]]
"""
    ),
    "zh-CN": """---
tags: [career-os, framework-view]
---
# 职业主页

> [!tip] Agent 优先
> 告诉 Agent 你想达成的结果，再打开负责下一项决策的工作台。
> 视图用于导航规范记录，不拥有职业事实。
>
> [[Home.md|English Home]]
>
> [[records.base|全部记录]] · [[dashboard.md|文本仪表盘]]
> [[career-map.canvas|架构图]] · [[career-guide.canvas|工作流指南]]

## 发现机会

### 招聘渠道

查看有日期依据的来源及渠道质量。

[[招聘渠道.base#当前渠道|打开招聘渠道]]

![[招聘渠道.base#当前渠道]]

### JD 筛选

比较职位匹配度，不据此提升准备度或证据成熟度。

[[JD 筛选工作台.base#当前候选|打开 JD 筛选]]

![[JD 筛选工作台.base#当前候选]]

## 做出决策

### 公司组合

独立于职位匹配度和招聘互动状态比较公司。

[[公司组合.base#总表|打开公司组合]]

![[公司组合.base#总表]]

### 招聘互动决策

审阅有边界的招聘范围、联系人、流程和决策。

[[招聘互动决策.base#决策总表|打开招聘互动决策]]

![[招聘互动决策.base#决策总表]]

## 准备能力

### 能力准备度

检查有证据支撑的差距、练习和复测状态。

[[能力准备度.base#最新严格评估|打开能力准备度]]

![[能力准备度.base#最新严格评估]]

## 权威契约

- [[10-career-evidence.md|职业证据]]
- [[20-career-strategy.md|职业策略]]
- [[30-role-market.md|职位市场]]
- [[40-opportunity-decision.md|机会决策]]
- [[50-career-outlook.md|职业展望]]
- [[60-capability-readiness.md|能力准备度]]
- [[70-career-communication.md|职业沟通]]
""",
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


@dataclass(frozen=True)
class CheckIssue:
    id: str
    status: str
    path: str | None
    detail: str

    def as_dict(self) -> dict[str, str | None]:
        return asdict(self)


def run_checks(paths: ProjectPaths, *, fast: bool, host: bool) -> list[CheckIssue]:
    issues: list[CheckIssue] = []
    issues.extend(_check_layout(paths))
    issues.extend(_check_configuration(paths))
    issues.extend(
        CheckIssue(item.id, item.status, item.path, item.detail)
        for item in inspect_downstream_git_safety(
            paths.project_root,
            initialized=(paths.project_root / INSTALL_STATE).is_file(),
        )
    )
    issues.extend(_check_subagent_projections(paths))
    issues.extend(_check_schemas(paths))
    issues.extend(_check_authority_seeds(paths))
    issues.extend(_check_repository_structure(paths))
    issues.extend(_check_public_privacy_policy(paths))
    issues.extend(_check_resume_assets(paths))
    issues.extend(_check_supply_chain(paths))
    issues.extend(_check_semantic_review_controls(paths))
    issues.extend(
        CheckIssue(item.id, item.status, item.path, item.detail)
        for item in verify_skills(paths.project_root)
    )
    if not fast:
        records, record_issues = _check_records(paths)
        issues.extend(record_issues)
        issues.extend(_check_internal_refs(records))
        issues.extend(_check_record_semantics(records))
        issues.extend(_check_host_ref_wikilinks(records))
        if host:
            issues.extend(_check_host_refs(paths, records))
        issues.extend(_check_obsidian_sources(paths))
    return issues


def has_failures(issues: list[CheckIssue]) -> bool:
    return any(issue.status == "fail" for issue in issues)


def _check_public_privacy_policy(paths: ProjectPaths) -> list[CheckIssue]:
    if paths.development_topology != "standalone-framework":
        return []
    try:
        report = audit_public_repository(paths.project_root)
    except (OSError, PublicPrivacyError, ValueError) as error:
        return [
            CheckIssue(
                "repository.public-privacy",
                "fail",
                str(paths.project_root / "system/privacy/public-fixture-policy.json"),
                str(error),
            )
        ]
    if not report.ok:
        return [
            CheckIssue(
                "repository.public-privacy",
                "fail",
                str(paths.project_root / "system/privacy/public-fixture-policy.json"),
                f"{len(report.findings)} redacted finding(s)",
            )
        ]
    return [
        CheckIssue(
            "repository.public-privacy",
            "pass",
            str(paths.project_root / "system/privacy/public-fixture-policy.json"),
            f"{report.guarded_blob_count} guarded blob(s) approved",
        )
    ]


def _check_layout(paths: ProjectPaths) -> list[CheckIssue]:
    issues: list[CheckIssue] = []
    required = [
        "AGENTS.md",
        "Home.md",
        ".agents",
        "system/tools/career_os",
        "system/tools/career_os/adapters",
        "system/tools/career_os/cli",
        "system/tools/career_os/operations",
        "system/tools/career_os/records",
        "system/tools/career_os/resume",
        "system/schemas",
        "system/obsidian",
        "system/resume",
        "system/seeds",
        "system/migrations",
        "system/tests",
    ]
    for relative in required:
        path = paths.project_root / relative
        issues.append(
            CheckIssue(
                id=f"layout.{relative.replace('/', '.')}",
                status="pass" if path.exists() else "fail",
                path=relative,
                detail="present" if path.exists() else "required system path is missing",
            )
        )
    for forbidden in ("src", "tools", "scripts", ".codex/skills"):
        path = paths.project_root / forbidden
        if path.exists():
            issues.append(
                CheckIssue(
                    id=f"layout.forbidden.{forbidden.replace('/', '.')}",
                    status="fail",
                    path=forbidden,
                    detail="product tooling must remain under system/tools",
                )
            )
    claude = paths.project_root / "CLAUDE.md"
    agents = paths.project_root / "AGENTS.md"
    valid_claude = claude.is_symlink() and claude.resolve() == agents.resolve()
    issues.append(
        CheckIssue(
            "layout.CLAUDE.md",
            "pass" if valid_claude else "fail",
            "CLAUDE.md",
            "real relative symlink to AGENTS.md" if valid_claude else "missing or invalid symlink",
        )
    )
    return issues


def _check_configuration(paths: ProjectPaths) -> list[CheckIssue]:
    try:
        config = load_project_config(paths.project_root)
        with (paths.project_root / "pyproject.toml").open("rb") as handle:
            pyproject = tomllib.load(handle)
        project = pyproject.get("project")
        if not isinstance(project, dict) or not isinstance(project.get("version"), str):
            raise ValueError("pyproject.toml project version is missing")
        normalized = config.system_version.replace("-rc.", "rc")
        if normalized != project["version"] or normalized != __version__:
            raise ValueError(
                "version mismatch among career-os.toml, pyproject.toml, and career_os.__version__"
            )
    except (OSError, ValueError, ValidationError) as error:
        return [CheckIssue("config.project", "fail", "career-os.toml", str(error))]
    return [
        CheckIssue("config.project", "pass", "career-os.toml", "valid"),
        CheckIssue("version.consistency", "pass", None, config.system_version),
    ]


def _check_subagent_projections(paths: ProjectPaths) -> list[CheckIssue]:
    relative = Path(".agents/tools/generate-subagents.py")
    generator = paths.project_root / relative
    if not generator.is_file():
        return [
            CheckIssue(
                "agents.subagent-projections",
                "fail",
                relative.as_posix(),
                "subagent projection generator is missing",
            )
        ]
    try:
        completed = subprocess.run(
            [sys.executable, str(generator), "--check"],
            cwd=paths.project_root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return [
            CheckIssue(
                "agents.subagent-projections",
                "fail",
                relative.as_posix(),
                f"unable to check subagent projections: {error}",
            )
        ]
    output = "\n".join(
        part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
    )
    detail = " | ".join(output.splitlines()) or "projection check produced no result"
    return [
        CheckIssue(
            "agents.subagent-projections",
            "pass" if completed.returncode == 0 else "fail",
            ".agents/subagents",
            detail,
        )
    ]


def _check_schemas(paths: ProjectPaths) -> list[CheckIssue]:
    schema_root = paths.project_root / "system/schemas"
    issues: list[CheckIssue] = []
    runtime_schemas = {
        "downstream-sync-validation.schema.json": downstream_sync_validation_json_schema,
        "legacy-import-manifest.schema.json": import_manifest_json_schema,
        "legacy-inventory-rules.schema.json": inventory_rules_json_schema,
        "legacy-migration-inventory.schema.json": migration_inventory_json_schema,
        "migration-provenance.schema.json": migration_provenance_json_schema,
        "semantic-file-review.schema.json": semantic_file_review_json_schema,
        "semantic-review-amendment.schema.json": semantic_review_amendment_json_schema,
        "semantic-review-completion.schema.json": semantic_review_completion_json_schema,
        "semantic-review-supersession.schema.json": semantic_review_supersession_json_schema,
        "reviewer-evidence-audit.schema.json": evidence_audit_json_schema,
        "reviewer-interview-probe.schema.json": interview_probe_json_schema,
        "record-envelope.schema.json": record_json_schema,
        "font-manifest.schema.json": font_manifest_json_schema,
    }
    for path in sorted(schema_root.glob("*.json")):
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict) or "$schema" not in loaded:
                raise ValueError("schema must be a JSON object with $schema")
            runtime_schema = runtime_schemas.get(path.name)
            if runtime_schema is not None and loaded != runtime_schema():
                raise ValueError(f"committed {path.name} does not match the runtime model")
            issues.append(CheckIssue("schema.json", "pass", str(path), "valid JSON Schema"))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            issues.append(CheckIssue("schema.json", "fail", str(path), str(error)))
    if not issues:
        issues.append(CheckIssue("schema.inventory", "fail", str(schema_root), "no schemas found"))
    return issues


def _check_semantic_review_controls(paths: ProjectPaths) -> list[CheckIssue]:
    provenance_root = paths.data_root / ".provenance"
    review_path = provenance_root / "semantic-file-review.json"
    completion_path = provenance_root / "semantic-review-completion.json"
    supersession_path = provenance_root / "semantic-review-supersession.json"
    amendment_path = provenance_root / "semantic-review-subagent-amendment.json"
    if not review_path.exists():
        orphan = next(
            (
                path
                for path in (completion_path, supersession_path, amendment_path)
                if path.exists()
            ),
            None,
        )
        if orphan is not None:
            return [
                CheckIssue(
                    "migration.semantic-review",
                    "fail",
                    str(orphan),
                    f"{orphan.name} exists without semantic-file-review.json",
                )
            ]
        return [
            CheckIssue(
                "migration.semantic-review",
                "pass",
                None,
                "not configured for this installation",
            )
        ]
    framework_root = (
        paths.project_root
        if paths.development_topology == "integrated-workbench"
        else None
    )
    try:
        issues: list[CheckIssue] = []
        tracking_paths: list[Path]
        if supersession_path.exists():
            supersession = verify_semantic_review_supersession(
                paths,
                supersession_path=supersession_path,
                public_root=framework_root,
            )
            tracking_paths = [
                review_path,
                completion_path,
                supersession_path,
                paths.data_root.joinpath(
                    *PurePosixPath(supersession.correction_manifest_path).parts
                ),
                paths.data_root.joinpath(
                    *PurePosixPath(supersession.correction_provenance_path).parts
                ),
            ]
            issues.extend(
                [
                    CheckIssue(
                        "migration.semantic-review",
                        "pass",
                        str(review_path),
                        (
                            "historical review preserved byte-for-byte after a "
                            "schema-2 correction"
                        ),
                    ),
                    CheckIssue(
                        "migration.semantic-review-completion",
                        "pass",
                        str(completion_path),
                        (
                            "historical completion retained; superseded by correction "
                            f"{supersession.correction_manifest_id}"
                        ),
                    ),
                ]
            )
        else:
            control = load_semantic_file_review(review_path)
            inventory_path = paths.data_root.joinpath(
                *PurePosixPath(control.inventory_path).parts
            )
            verified = verify_semantic_file_review(
                paths,
                inventory_path=inventory_path,
                review_path=review_path,
                public_root=framework_root,
            )
            issues.append(
                CheckIssue(
                    "migration.semantic-review",
                    "pass",
                    str(review_path),
                    f"{len(control.entries)} source files closed; "
                    f"target tree {verified.target_tree_sha256}",
                )
            )
            tracking_paths = [review_path]
            if completion_path.exists():
                completion = verify_semantic_review_completion(
                    paths,
                    completion_path=completion_path,
                    public_root=framework_root,
                )
                issues.append(
                    CheckIssue(
                        "migration.semantic-review-completion",
                        "pass",
                        str(completion_path),
                        f"{completion.status} ({completion.development_topology})",
                    )
                )
                tracking_paths.append(completion_path)
            else:
                issues.append(
                    CheckIssue(
                        "migration.semantic-review-completion",
                        "attention",
                        str(completion_path),
                        "review is valid but no completion control is present",
                    )
                )

        uncommitted = [
            path for path in tracking_paths if not _path_matches_head(paths.project_root, path)
        ]
        if supersession_path.exists():
            tracking_detail = (
                "semantic supersession controls are not committed at HEAD: "
                + ", ".join(str(path) for path in uncommitted)
                if uncommitted
                else "semantic supersession controls are committed"
            )
        else:
            tracking_detail = (
                "review controls are not committed at HEAD: "
                + ", ".join(path.name for path in uncommitted)
                if uncommitted
                else "review controls match HEAD"
            )
        issues.append(
            CheckIssue(
                "migration.semantic-review-tracking",
                "attention" if uncommitted else "pass",
                str(provenance_root),
                tracking_detail,
            )
        )

        if amendment_path.exists():
            amendment = verify_semantic_review_amendment(
                paths,
                amendment_path=amendment_path,
                public_root=framework_root,
            )
            issues.append(
                CheckIssue(
                    "migration.semantic-review-amendment",
                    "pass",
                    str(amendment_path),
                    (
                        f"{len(amendment.entries)} source mappings corrected by "
                        f"{amendment.issue_id}"
                    ),
                )
            )
        else:
            issues.append(
                CheckIssue(
                    "migration.semantic-review-amendment",
                    "pass",
                    None,
                    "no additive semantic-review amendment configured",
                )
            )
        return issues
    except (OSError, ValueError, ValidationError) as error:
        return [
            CheckIssue(
                "migration.semantic-review",
                "fail",
                str(review_path),
                str(error),
            )
        ]


def _path_matches_head(project_root: Path, path: Path) -> bool:
    root = project_root.resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        return False
    relative = resolved.relative_to(root).as_posix()
    try:
        exists = subprocess.run(
            ["git", "-C", str(root), "cat-file", "-e", f"HEAD:{relative}"],
            check=False,
            capture_output=True,
        )
        if exists.returncode != 0:
            return False
        clean = subprocess.run(
            ["git", "-C", str(root), "diff", "--quiet", "HEAD", "--", relative],
            check=False,
            capture_output=True,
        )
        return clean.returncode == 0
    except OSError:
        return False


def _check_repository_structure(paths: ProjectPaths) -> list[CheckIssue]:
    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(paths.project_root),
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            check=True,
            capture_output=True,
        )
        tracked = [item.decode("utf-8") for item in completed.stdout.split(b"\0") if item]
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError) as error:
        return [CheckIssue("layout.git-inventory", "fail", None, str(error))]

    executable_suffixes = {".bat", ".cmd", ".js", ".ps1", ".py", ".sh", ".ts"}
    harness_root_files = {".agents/relink-skills.sh", ".agents/symlink-manager.py"}
    misplaced = []
    for relative in tracked:
        suffix = PurePosixPath(relative).suffix.lower()
        if suffix not in executable_suffixes:
            continue
        allowed = (
            relative.startswith("system/")
            or relative.startswith(".agents/tools/")
            or relative.startswith(".agents/skills/")
            or relative in harness_root_files
        )
        if not allowed:
            misplaced.append(relative)
    unsafe_state = [
        relative
        for relative in tracked
        if relative.startswith(("runtime/", "build/", ".career-os/"))
        or "/.obsidian/" in f"/{relative}/"
    ]
    font_binaries = [
        relative
        for relative in tracked
        if PurePosixPath(relative).suffix.lower() in {".otf", ".ttf", ".ttc"}
    ]
    issues = [
        CheckIssue(
            "layout.executable-placement",
            "fail" if misplaced else "pass",
            None,
            ", ".join(misplaced)
            if misplaced
            else "project executables remain under system; Host and Skill bundles are isolated",
        ),
        CheckIssue(
            "layout.generated-state",
            "fail" if unsafe_state else "pass",
            None,
            ", ".join(unsafe_state)
            if unsafe_state
            else "generated state and active Obsidian configuration are untracked",
        ),
        CheckIssue(
            "resume.font-binaries",
            "fail" if font_binaries else "pass",
            None,
            ", ".join(font_binaries)
            if font_binaries
            else "font binaries are confined to ignored local state",
        ),
    ]
    try:
        data_relative = paths.data_root.relative_to(paths.project_root).as_posix()
    except ValueError:
        issues.append(
            CheckIssue(
                "layout.data-git-boundary",
                "pass",
                str(paths.data_root),
                "external data root remains under its host repository policy",
            )
        )
    else:
        ignored = subprocess.run(
            [
                "git",
                "-C",
                str(paths.project_root),
                "check-ignore",
                "--no-index",
                "--quiet",
                "--",
                data_relative,
            ],
            check=False,
            capture_output=True,
        )
        git_check_failed = ignored.returncode not in {0, 1}
        issues.append(
            CheckIssue(
                "layout.data-git-boundary",
                "fail" if ignored.returncode == 0 or git_check_failed else "pass",
                data_relative,
                (
                    "configured user data is ignored by Git"
                    if ignored.returncode == 0
                    else (
                        ignored.stderr.decode("utf-8", errors="replace").strip()
                        if git_check_failed
                        else "configured user data is eligible for Git tracking"
                    )
                ),
            )
        )
    return issues


def _check_authority_seeds(paths: ProjectPaths) -> list[CheckIssue]:
    required_sections = {
        "## Key Terms",
        "## Authority Map",
        "## Lifecycle",
        "## Change Rules",
        "## Completion Gate",
    }
    issues: list[CheckIssue] = []
    for relative in sorted(_AUTHORITY_CONTRACT_PATHS):
        path = paths.project_root / relative
        try:
            text = path.read_text(encoding="utf-8")
            missing = sorted(section for section in required_sections if section not in text)
            if missing:
                raise ValueError(f"missing authority sections: {', '.join(missing)}")
            if _CJK_TEXT.search(text):
                raise ValueError("framework authority seed must use English prose")
            issues.append(CheckIssue("seed.authority", "pass", str(path), "complete"))
        except (OSError, ValueError) as error:
            issues.append(CheckIssue("seed.authority", "fail", str(path), str(error)))
    return issues


def _check_supply_chain(paths: ProjectPaths) -> list[CheckIssue]:
    sbom_ok, sbom_detail = verify_sbom(paths.project_root)
    issues = [
        CheckIssue(
            "supply-chain.sbom",
            "pass" if sbom_ok else "fail",
            "system/sbom.cdx.json",
            sbom_detail,
        )
    ]
    notice_path = paths.project_root / "NOTICE"
    try:
        notice = notice_path.read_text(encoding="utf-8")
        required = {
            "93667c5a5eec5f68cd1097574e27c29994b6c3f2",
            "553ef99aa3306dd23f268e1ba9af752577684f69",
            "system/licenses/sean2077-skills-MIT.txt",
            "system/licenses/kepano-obsidian-skills-MIT.txt",
        }
        font_manifest = load_font_manifest(paths.project_root)
        required.update(package.license_path for package in font_manifest.packages)
        required.update(asset.sha256 for _package, asset in font_manifest.iter_assets())
        missing = sorted(item for item in required if item not in notice)
        issues.append(
            CheckIssue(
                "supply-chain.notice",
                "fail" if missing else "pass",
                "NOTICE",
                "missing: " + ", ".join(missing) if missing else "required attribution present",
            )
        )
    except OSError as error:
        issues.append(CheckIssue("supply-chain.notice", "fail", "NOTICE", str(error)))
    return issues


def _check_resume_assets(paths: ProjectPaths) -> list[CheckIssue]:
    root = paths.project_root / "system/resume"
    issues: list[CheckIssue] = []
    for relative in (
        "career-os.cls",
        "career-os-style.sty",
        "templates/identity.tex",
        "templates/single-column.tex",
        "fonts.json",
        "secret-patterns.json",
    ):
        path = root / relative
        issues.append(
            CheckIssue(
                "resume.asset",
                "pass" if path.is_file() else "fail",
                str(path),
                "present" if path.is_file() else "required resume asset is missing",
            )
        )
    try:
        manifest = load_font_manifest(paths.project_root)
        for package in manifest.packages:
            license_path = paths.project_root / package.license_path
            if not license_path.is_file():
                raise ValueError(f"font license is missing: {package.license_path}")
        if len(manifest.iter_assets()) != 4:
            raise ValueError("font manifest must pin all four resume font roles")
        issues.append(CheckIssue("resume.font-manifest", "pass", str(root / "fonts.json"), "valid"))
    except (OSError, ValueError, ValidationError) as error:
        issues.append(
            CheckIssue("resume.font-manifest", "fail", str(root / "fonts.json"), str(error))
        )
    try:
        patterns = load_secret_patterns(paths.project_root)
        if not patterns:
            raise ValueError("at least one configured secret pattern is required")
        issues.append(
            CheckIssue(
                "resume.secret-patterns",
                "pass",
                str(root / "secret-patterns.json"),
                f"{len(patterns)} patterns",
            )
        )
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as error:
        issues.append(
            CheckIssue(
                "resume.secret-patterns",
                "fail",
                str(root / "secret-patterns.json"),
                str(error),
            )
        )

    fixtures = sorted((root / "fixtures").glob("*/resume.tex"))
    for source_path in fixtures:
        try:
            validate_resume_source(paths, source_path)
            issues.append(CheckIssue("resume.fixture", "pass", str(source_path), "valid"))
        except (OSError, ValueError, ValidationError) as error:
            issues.append(CheckIssue("resume.fixture", "fail", str(source_path), str(error)))
    expected_fixture_names = {"en", "multilingual", "zh-CN"}
    fixture_names = {source_path.parent.name for source_path in fixtures}
    if fixture_names != expected_fixture_names:
        issues.append(
            CheckIssue(
                "resume.fixture-inventory",
                "fail",
                str(root / "fixtures"),
                "expected en, multilingual, and zh-CN fixtures; "
                f"found {', '.join(sorted(fixture_names)) or 'none'}",
            )
        )
    else:
        issues.append(
            CheckIssue(
                "resume.fixture-inventory",
                "pass",
                str(root / "fixtures"),
                "en, multilingual, and zh-CN fixtures present",
            )
        )
    try:
        user_resumes = list_resumes(paths)
        for item in user_resumes:
            validate_resume_source(paths, Path(item.source))
            issues.append(CheckIssue("resume.user-source", "pass", item.source, "valid"))
    except (OSError, ValueError, ValidationError) as error:
        issues.append(CheckIssue("resume.user-source", "fail", None, str(error)))
    return issues


def _check_records(paths: ProjectPaths) -> tuple[list[ParsedRecord], list[CheckIssue]]:
    records: list[ParsedRecord] = []
    issues: list[CheckIssue] = []
    if not paths.data_root.exists():
        return records, [
            CheckIssue("records.data-root", "pass", str(paths.data_root), "not initialized")
        ]
    for path in sorted(paths.data_root.rglob("*.md")):
        if path.name == "README.md" or "_templates" in path.parts:
            continue
        try:
            record = load_record(path)
            expected = authority_directory(record.envelope.kind)
            relative = path.relative_to(paths.data_root)
            if not relative.parts or relative.parts[0] != expected:
                raise ValueError(f"{record.envelope.kind} belongs under {expected}")
            records.append(record)
            issues.append(CheckIssue("records.envelope", "pass", str(path), "valid"))
        except (OSError, ValueError, ValidationError) as error:
            issues.append(CheckIssue("records.envelope", "fail", str(path), str(error)))
    return records, issues


def _check_internal_refs(records: list[ParsedRecord]) -> list[CheckIssue]:
    issues: list[CheckIssue] = []
    by_id: dict[object, ParsedRecord] = {}
    for record in records:
        if record.envelope.id in by_id:
            issues.append(
                CheckIssue(
                    "records.duplicate-id",
                    "fail",
                    str(record.path),
                    f"duplicate id also used by {by_id[record.envelope.id].path}",
                )
            )
        by_id[record.envelope.id] = record
    for record in records:
        for reference in record.envelope.refs:
            status = "pass" if reference.target_id in by_id or not reference.required else "fail"
            issues.append(
                CheckIssue(
                    "records.internal-ref",
                    status,
                    str(record.path),
                    f"{reference.relation} -> {reference.target_id}",
                )
            )
    return issues


def _check_record_semantics(records: list[ParsedRecord]) -> list[CheckIssue]:
    return [
        CheckIssue("records.semantic", issue.status, str(issue.path), issue.detail)
        for issue in check_record_semantics(records)
    ]


def _check_host_ref_wikilinks(records: list[ParsedRecord]) -> list[CheckIssue]:
    issues: list[CheckIssue] = []
    for record in records:
        links = {
            match.group(1).split("|", maxsplit=1)[0].strip()
            for match in _WIKILINK.finditer(record.body)
        }
        for reference in record.envelope.host_refs:
            anchor = reference.anchor or ""
            path_without_extension = (
                reference.path[:-3] if reference.path.lower().endswith(".md") else reference.path
            )
            expected = f"{path_without_extension}{anchor}"
            accepted = {expected, f"{reference.path}{anchor}"}
            status = "pass" if links & accepted else "fail"
            issues.append(
                CheckIssue(
                    "records.host-ref-wikilink",
                    status,
                    str(record.path),
                    f"{reference.relation}: [[{expected}]]"
                    if status == "pass"
                    else f"typed host_ref requires matching native wikilink [[{expected}]]",
                )
            )
    return issues


def _check_host_refs(paths: ProjectPaths, records: list[ParsedRecord]) -> list[CheckIssue]:
    issues: list[CheckIssue] = []
    for record in records:
        for reference in record.envelope.host_refs:
            target = paths.vault_root.joinpath(*PurePosixPath(reference.path).parts).resolve()
            if not target.is_relative_to(paths.vault_root):
                issues.append(
                    CheckIssue(
                        "records.host-ref",
                        "fail",
                        str(record.path),
                        f"{reference.path}: escapes the Vault root",
                    )
                )
                continue
            exists = target.is_file()
            status = "pass" if exists or not reference.required else "fail"
            detail = f"{reference.path}: {'resolved' if exists else 'missing'}"
            if exists and reference.anchor and not _host_anchor_exists(target, reference.anchor):
                status = "fail"
                detail = f"{reference.path}{reference.anchor}: anchor is missing"
            if exists and reference.target_id and not _host_id_matches(target, reference.target_id):
                status = "fail"
                detail = f"{reference.path}: target id does not match"
            issues.append(
                CheckIssue(
                    "records.host-ref",
                    status,
                    str(record.path),
                    detail,
                )
            )
    return issues


def _host_anchor_exists(path: Path, anchor: str) -> bool:
    if path.suffix.lower() != ".md":
        return False
    text = path.read_text(encoding="utf-8-sig")
    target = anchor[1:]
    if target.startswith("^"):
        block = target[1:]
        return any(line.rstrip().endswith(f" ^{block}") for line in text.splitlines())
    heading = target.rsplit("#", maxsplit=1)[-1]
    return any(
        line.lstrip().startswith("#") and line.lstrip("# ").strip() == heading
        for line in text.splitlines()
    )


def _host_id_matches(path: Path, expected: object) -> bool:
    if path.suffix.lower() != ".md":
        return False
    try:
        text = path.read_text(encoding="utf-8-sig")
        if not text.startswith("---\n"):
            return False
        end = text.find("\n---\n", 4)
        if end < 0:
            return False
        frontmatter = _yaml.load(text[4:end])
        return isinstance(frontmatter, dict) and str(frontmatter.get("id")) == str(expected)
    except (OSError, ValueError):
        return False


def _check_obsidian_sources(paths: ProjectPaths) -> list[CheckIssue]:
    issues: list[CheckIssue] = []
    source_root = paths.project_root / "system/obsidian"
    for locale, filename in _HOMEPAGE_MARKDOWNS.items():
        homepage = paths.project_root / filename
        if not homepage.is_file():
            issues.append(
                CheckIssue(
                    "obsidian.homepage-inventory",
                    "fail",
                    str(homepage),
                    f"missing required root {locale} Career Home",
                )
            )
        else:
            try:
                _validate_homepage_markdown(
                    homepage.read_text(encoding="utf-8"), locale=locale
                )
                issues.append(CheckIssue("obsidian.source", "pass", str(homepage), "valid"))
            except (OSError, ValueError, YAMLError) as error:
                issues.append(CheckIssue("obsidian.source", "fail", str(homepage), str(error)))
    for name, purpose in _REQUIRED_CANVAS_ASSETS.items():
        path = source_root / name
        if not path.is_file():
            issues.append(
                CheckIssue(
                    "obsidian.canvas-inventory",
                    "fail",
                    str(path),
                    f"missing required {purpose}",
                )
            )
    for path in sorted(source_root.rglob("*")):
        if not path.is_file():
            continue
        try:
            if path.suffix == ".base":
                loaded = _yaml.load(path.read_text(encoding="utf-8"))
                key = path.relative_to(paths.project_root).as_posix()
                _validate_base(key, loaded)
            elif path.suffix == ".canvas":
                canvas = json.loads(path.read_text(encoding="utf-8"))
                _validate_canvas(canvas)
                _validate_canvas_semantics(path.name, canvas)
            elif path.name == "dashboard.md":
                _validate_dashboard_markdown(path.read_text(encoding="utf-8"))
            elif path.suffix == ".json":
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(loaded, dict):
                    raise ValueError("adapter JSON must contain an object")
            else:
                continue
            issues.append(CheckIssue("obsidian.source", "pass", str(path), "valid"))
        except (OSError, ValueError, json.JSONDecodeError, YAMLError) as error:
            issues.append(CheckIssue("obsidian.source", "fail", str(path), str(error)))
    for _legacy, english_relative, chinese_relative, _views, _filters in (
        _WORKBENCH_BASE_PAIRS
    ):
        english_path = paths.project_root / english_relative
        chinese_path = paths.project_root / chinese_relative
        missing = [
            str(path.relative_to(paths.project_root))
            for path in (english_path, chinese_path)
            if not path.is_file()
        ]
        if missing:
            issues.append(
                CheckIssue(
                    "obsidian.base-inventory",
                    "fail",
                    str(source_root / "bases"),
                    "missing required localized Base: " + ", ".join(missing),
                )
            )
            continue
        try:
            english = _yaml.load(english_path.read_text(encoding="utf-8"))
            chinese = _yaml.load(chinese_path.read_text(encoding="utf-8"))
            _validate_base_pair(
                english_relative,
                english,
                chinese_relative,
                chinese,
            )
            issues.append(
                CheckIssue(
                    "obsidian.base-pair",
                    "pass",
                    f"{english_path} <-> {chinese_path}",
                    "presentation-only localization parity is valid",
                )
            )
        except (OSError, ValueError, YAMLError) as error:
            issues.append(
                CheckIssue(
                    "obsidian.base-pair",
                    "fail",
                    f"{english_path} <-> {chinese_path}",
                    str(error),
                )
            )
    issues.extend(_check_readme_canvas_images(paths))
    return issues


def _check_readme_canvas_images(paths: ProjectPaths) -> list[CheckIssue]:
    problems: list[str] = []
    try:
        readme = paths.project_root.joinpath("README.md").read_text(encoding="utf-8")
        for source, output in _README_CANVAS_IMAGES:
            path = paths.project_root / output
            if not path.is_file():
                problems.append(f"missing {output}")
            else:
                image = path.read_bytes()
                if len(image) < 24 or image[:8] != b"\x89PNG\r\n\x1a\n" or image[12:16] != b"IHDR":
                    problems.append(f"invalid PNG {output}")
                else:
                    width = int.from_bytes(image[16:20], "big")
                    height = int.from_bytes(image[20:24], "big")
                    if width < 4000 or height < 2000 or width <= height:
                        problems.append(
                            f"{output} is not a full-canvas landscape export ({width}x{height})"
                        )
            if f"]({output})" not in readme:
                problems.append(f"README.md does not embed {output}")
            if f"]({source})" not in readme:
                problems.append(f"README.md does not link {source}")
    except OSError as error:
        problems.append(str(error))

    return [
        CheckIssue(
            "obsidian.readme-images",
            "fail" if problems else "pass",
            "README.md",
            "; ".join(problems)
            if problems
            else "two native full-canvas PNG projections and README links are valid",
        )
    ]


def _validate_base(name: str, base: Any, *, data_root: str | None = None) -> None:
    if not isinstance(base, dict) or not isinstance(base.get("views"), list):
        raise ValueError("Base must define a views list")
    views = base["views"]
    if not all(isinstance(view, dict) and isinstance(view.get("name"), str) for view in views):
        raise ValueError(f"{name} views must be named mappings")
    names = [view["name"] for view in views]
    if len(names) != len(set(names)):
        raise ValueError(f"{name} view names must be unique")
    if name in _ENGLISH_WORKBENCH_BASES | _CHINESE_WORKBENCH_BASES:
        _validate_workbench_base_presentation(name, base)
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
    if not isinstance(formulas, dict):
        raise ValueError(f"{name} must define formulas")
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
    if _base_semantic_projection(english) != _base_semantic_projection(chinese):
        raise ValueError(
            f"{english_name} and {chinese_name} may differ only in "
            "properties.*.displayName and views[].name"
        )


def _base_semantic_projection(base: Any) -> Any:
    projected = deepcopy(base)
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
    if name in _ENGLISH_WORKBENCH_BASES:
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


def _validate_canvas(canvas: Any) -> None:
    if not isinstance(canvas, dict):
        raise ValueError("Canvas must be an object")
    nodes = canvas.get("nodes", [])
    edges = canvas.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("Canvas nodes and edges must be arrays")
    node_ids: set[str] = set()
    all_ids: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("Canvas node must be an object")
        node_id = _canvas_object_id(node, "node")
        if node_id in all_ids:
            raise ValueError("Canvas IDs must be unique")
        node_ids.add(node_id)
        all_ids.add(node_id)
        node_type = node.get("type")
        if node_type not in _CANVAS_NODE_TYPES:
            raise ValueError(f"Canvas node has an invalid type: {node_type!r}")
        for field in ("x", "y", "width", "height"):
            value = node.get(field)
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"Canvas node {node_id} has a non-integer {field}")
        if node["width"] <= 0 or node["height"] <= 0:
            raise ValueError(f"Canvas node {node_id} must have positive dimensions")
        _validate_canvas_color(node.get("color"), f"node {node_id}")
        if node_type == "text":
            if not isinstance(node.get("text"), str) or not node["text"].strip():
                raise ValueError(f"Canvas text node {node_id} is missing text")
        elif node_type == "file":
            _validate_canvas_file_path(node.get("file"), f"file node {node_id}")
            subpath = node.get("subpath")
            if subpath is not None and (
                not isinstance(subpath, str) or not subpath.startswith("#")
            ):
                raise ValueError(f"Canvas file node {node_id} has an invalid subpath")
        elif node_type == "link":
            if not isinstance(node.get("url"), str) or not node["url"].strip():
                raise ValueError(f"Canvas link node {node_id} is missing a URL")
        else:
            label = node.get("label")
            if label is not None and not isinstance(label, str):
                raise ValueError(f"Canvas group node {node_id} has an invalid label")
            background = node.get("background")
            if background is not None:
                _validate_canvas_file_path(background, f"group node {node_id} background")
            if node.get("backgroundStyle") not in {None, "cover", "ratio", "repeat"}:
                raise ValueError(f"Canvas group node {node_id} has an invalid background style")

    for edge in edges:
        if not isinstance(edge, dict):
            raise ValueError("Canvas edge must be an object")
        edge_id = _canvas_object_id(edge, "edge")
        if edge_id in all_ids:
            raise ValueError("Canvas IDs must be unique")
        all_ids.add(edge_id)
        if edge.get("fromNode") not in node_ids:
            raise ValueError("Canvas edge has an invalid fromNode")
        if edge.get("toNode") not in node_ids:
            raise ValueError("Canvas edge has an invalid toNode")
        if edge.get("fromSide") not in _CANVAS_SIDES | {None}:
            raise ValueError(f"Canvas edge {edge_id} has an invalid fromSide")
        if edge.get("toSide") not in _CANVAS_SIDES | {None}:
            raise ValueError(f"Canvas edge {edge_id} has an invalid toSide")
        if edge.get("fromEnd") not in _CANVAS_ENDS | {None}:
            raise ValueError(f"Canvas edge {edge_id} has an invalid fromEnd")
        if edge.get("toEnd") not in _CANVAS_ENDS | {None}:
            raise ValueError(f"Canvas edge {edge_id} has an invalid toEnd")
        label = edge.get("label")
        if label is not None and not isinstance(label, str):
            raise ValueError(f"Canvas edge {edge_id} has an invalid label")
        _validate_canvas_color(edge.get("color"), f"edge {edge_id}")


def _canvas_object_id(item: dict[str, Any], item_type: str) -> str:
    value = item.get("id")
    if not isinstance(value, str) or not _CANVAS_ID.fullmatch(value):
        raise ValueError(f"Canvas {item_type} ID must be 16 lowercase hexadecimal characters")
    return value


def _validate_canvas_color(value: Any, context: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or (
        value not in _CANVAS_COLORS and re.fullmatch(r"#[0-9a-fA-F]{6}", value) is None
    ):
        raise ValueError(f"Canvas {context} has an invalid color")


def _validate_canvas_file_path(value: Any, context: str) -> None:
    if not isinstance(value, str) or not value or "\\" in value or value.endswith("/"):
        raise ValueError(f"Canvas {context} has an invalid file path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Canvas {context} file path escapes the Vault")


def _validate_canvas_semantics(name: str, canvas: dict[str, Any]) -> None:
    if name not in _REQUIRED_CANVAS_ASSETS:
        return
    nodes = canvas["nodes"]
    semantic_text: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("type") == "text":
            semantic_text.append(str(node["text"]))
        elif node.get("type") == "group" and isinstance(node.get("label"), str):
            semantic_text.append(str(node["label"]))
    text = "\n".join(semantic_text)
    navigation_targets = {
        str(node["file"]) for node in nodes if isinstance(node, dict) and node.get("type") == "file"
    }
    navigation_targets.update(
        match.group(1).split("|", maxsplit=1)[0].strip()
        for value in semantic_text
        for match in _WIKILINK.finditer(value)
    )
    if _CJK_TEXT.search(text):
        raise ValueError(f"{name} must keep framework prose in English")
    _validate_canvas_layout(name, canvas)
    missing_authorities = sorted(
        suffix
        for suffix in _AUTHORITY_CONTRACT_PATHS
        if Path(suffix).name not in navigation_targets
    )
    if missing_authorities:
        raise ValueError(f"{name} is missing authority entries: {', '.join(missing_authorities)}")

    if name == "career-map.canvas":
        required_fragments = {
            "Agent-native workflow",
            "Natural-language outcome",
            "Seven canonical authorities",
            "Derived views are not authority",
            "State separation",
            "Public or application-grade export",
            "External and account actions",
            "Irrecoverable overwrite or delete",
            "Five independent opportunity blocks",
            "Ownership layers",
        }
        missing = sorted(fragment for fragment in required_fragments if fragment not in text)
        if missing:
            detail = ", ".join(missing)
            raise ValueError(f"career-map.canvas is missing semantic sections: {detail}")
        if "career-guide.canvas" not in navigation_targets:
            raise ValueError("career-map.canvas must link the workflow guide")
        return

    cards = [
        str(node["text"])
        for node in nodes
        if isinstance(node, dict)
        and node.get("type") == "text"
        and all(field in str(node.get("text", "")) for field in _TASK_CARD_FIELDS)
    ]
    single = [card for card in cards if card.startswith("## Single-domain")]
    cross = [card for card in cards if card.startswith("## Cross-domain")]
    if len(cards) != 11 or len(single) != 7 or len(cross) != 4:
        raise ValueError(
            "career-guide.canvas must contain seven single-domain and four cross-domain cards"
        )
    required_skills = {
        "career-evidence",
        "career-strategy",
        "role-market",
        "opportunity-decision",
        "career-outlook",
        "capability-readiness",
        "career-communication",
    }
    missing_skills = sorted(skill for skill in required_skills if f"`{skill}`" not in text)
    if missing_skills:
        raise ValueError(f"career-guide.canvas is missing Skills: {', '.join(missing_skills)}")
    if "career-map.canvas" not in navigation_targets:
        raise ValueError("career-guide.canvas must link the architecture overview")


def _validate_homepage_markdown(text: str, *, locale: str = "en") -> None:
    if locale not in _HOMEPAGE_MARKDOWNS:
        raise ValueError(f"unsupported homepage locale: {locale}")
    homepage_name = _HOMEPAGE_MARKDOWNS[locale]
    workbench_links = (
        _HOMEPAGE_WORKBENCH_LINKS
        if locale == "en"
        else _HOMEPAGE_CHINESE_WORKBENCH_LINKS
    )
    framework_links = (
        _HOMEPAGE_FRAMEWORK_LINKS
        if locale == "en"
        else _HOMEPAGE_CHINESE_FRAMEWORK_LINKS
    )
    authority_links = (
        _HOMEPAGE_AUTHORITY_LINKS
        if locale == "en"
        else _HOMEPAGE_CHINESE_AUTHORITY_LINKS
    )
    link_aliases = dict((*workbench_links, *framework_links, *authority_links))
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---\n"):
        raise ValueError(f"{homepage_name} must begin with YAML frontmatter")
    frontmatter_end = normalized.find("\n---\n", 4)
    if frontmatter_end < 0:
        raise ValueError(f"{homepage_name} frontmatter is not terminated")
    frontmatter = _yaml.load(normalized[4:frontmatter_end])
    if not isinstance(frontmatter, dict):
        raise ValueError(f"{homepage_name} frontmatter must be a mapping")
    if "cssclasses" in frontmatter:
        raise ValueError(f"{homepage_name} must not depend on CSS classes")
    if frontmatter != {"tags": ["career-os", "framework-view"]}:
        raise ValueError(
            f"{homepage_name} frontmatter must contain only the canonical framework tags"
        )

    body = normalized[frontmatter_end + 5 :]
    headings = tuple(re.findall(r"(?m)^#{1,3} [^\n]+$", body))
    if headings != _HOMEPAGE_HEADINGS[locale]:
        raise ValueError(
            f"{homepage_name} sections must remain in the canonical Workbench-first order"
        )

    callouts = re.findall(r"(?m)^>\s*\[![^\]\n]+\][+-]?(?:\s+.*)?$", body)
    expected_callout = "> [!tip] Agent-first" if locale == "en" else "> [!tip] Agent 优先"
    if callouts != [expected_callout]:
        raise ValueError(
            f"{homepage_name} permits only the native, non-folding Agent-first callout"
        )
    if re.search(r"(?m)^\s*(?:```|~~~)", body):
        raise ValueError(f"{homepage_name} must not contain code or plugin-dependent blocks")
    if re.search(r"<\s*/?\s*[A-Za-z][^>]*>", body):
        raise ValueError(f"{homepage_name} must not contain raw HTML or scripts")
    if re.search(r"!?\[[^\]\n]*\]\([^)]+\)", body):
        raise ValueError(f"{homepage_name} must not contain external Markdown links or images")

    direct_counts: dict[str, int] = {}
    embed_counts: dict[str, int] = {}
    workbench_views = dict(workbench_links)
    workbench_view_by_file = {
        target.split("#", maxsplit=1)[0]: target for target in workbench_views
    }
    for match in _MARKDOWN_WIKILINK.finditer(body):
        raw = match.group("content")
        parts = [part.strip() for part in raw.split("|")]
        if len(parts) not in {1, 2} or not all(parts):
            raise ValueError(
                f"{homepage_name} wikilinks must use a target and at most one explicit alias"
            )
        target = parts[0]
        alias = parts[1] if len(parts) == 2 else None
        filename = target.split("#", maxsplit=1)[0]
        if (
            "/" in filename
            or "\\" in filename
            or PurePosixPath(filename).name != filename
        ):
            raise ValueError(
                f"{homepage_name} target must be filename-only and remain inside the Vault: "
                f"{target}"
            )
        expected_view = workbench_view_by_file.get(filename)
        if expected_view is not None and target != expected_view:
            raise ValueError(
                f"{homepage_name} Workbench {filename} must target the canonical view "
                f"{expected_view}"
            )
        expected_alias = link_aliases.get(target)
        if expected_alias is None:
            raise ValueError(
                f"{homepage_name} target is outside the known framework/data inventory: {target}"
            )

        if match.group("embed") is not None:
            if target not in workbench_views:
                raise ValueError(
                    f"{homepage_name} permits embeds only for its five canonical Workbenches"
                )
            if alias is not None:
                raise ValueError(f"{homepage_name} Workbench embeds must not use aliases")
            line_start = body.rfind("\n", 0, match.start()) + 1
            line_end = body.find("\n", match.end())
            if line_end < 0:
                line_end = len(body)
            if body[line_start:line_end] != f"![[{target}]]":
                raise ValueError(
                    f"{homepage_name} Workbench embeds must be standalone and expanded by default"
                )
            embed_counts[target] = embed_counts.get(target, 0) + 1
        else:
            if alias != expected_alias:
                raise ValueError(
                    f"{homepage_name} target {target} must use alias {expected_alias!r}"
                )
            direct_counts[target] = direct_counts.get(target, 0) + 1

    for target, _alias in workbench_links:
        if direct_counts.get(target, 0) != 1 or embed_counts.get(target, 0) != 1:
            raise ValueError(
                f"{homepage_name} Workbench {target} requires exactly one open link "
                "and one live embed"
            )
    for target, _alias in (*framework_links, *authority_links):
        if direct_counts.get(target, 0) != 1 or embed_counts.get(target, 0) != 0:
            raise ValueError(
                f"{homepage_name} navigation target {target} must appear exactly once "
                "as a direct link"
            )

    visible_prose = _MARKDOWN_WIKILINK.sub("", body)
    if locale == "en" and _CJK_TEXT.search(visible_prose):
        raise ValueError(
            "Home.md must keep visible framework prose and link aliases in English"
        )
    if locale == "zh-CN" and not _CJK_TEXT.search(visible_prose):
        raise ValueError("主页.md must keep visible framework prose in Chinese")
    if (
        "__CAREER_OS_" in visible_prose
        or "/" in visible_prose
        or "\\" in visible_prose
    ):
        raise ValueError(
            f"{homepage_name} visible prose must not contain placeholders or configured paths"
        )
    if normalized != _HOMEPAGE_CANONICAL_TEXT[locale]:
        raise ValueError(
            f"{homepage_name} must contain only canonical static framework copy; "
            "personal facts and custom presentation are forbidden"
        )


def _validate_dashboard_markdown(text: str) -> None:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if normalized.count("[[Home.md|Open Career Home]]") != 1 or "Home.canvas" in normalized:
        raise ValueError("dashboard.md must link exactly once to the root Markdown homepage")
    if "[[主页.md" in normalized:
        raise ValueError("dashboard.md must leave language switching to the homepage")
    for match in _MARKDOWN_WIKILINK.finditer(normalized):
        if match.group("embed") is None:
            continue
        target = match.group("content").split("|", maxsplit=1)[0].strip()
        filename = target.split("#", maxsplit=1)[0]
        if filename in _HOMEPAGE_WORKBENCH_FILES:
            raise ValueError("dashboard.md must not duplicate dedicated Workbench embeds")
    for target in ("records.base#All records", "career-map.canvas", "career-guide.canvas"):
        if normalized.count(f"![[{target}]]") != 1:
            raise ValueError(f"dashboard.md must retain exactly one {target} embed")
    for target, alias in _HOMEPAGE_AUTHORITY_LINKS:
        if normalized.count(f"[[{target}|{alias}]]") != 1:
            raise ValueError(
                f"dashboard.md must retain exactly one Authority link for {target}"
            )


def _validate_canvas_layout(name: str, canvas: dict[str, Any]) -> None:
    max_width, max_height, min_aspect, max_aspect, min_density, max_text = _CANVAS_LAYOUT_LIMITS[
        name
    ]
    content_nodes = [node for node in canvas["nodes"] if node["type"] != "group"]
    if not content_nodes:
        raise ValueError(f"{name} must contain visible content nodes")

    min_x = min(node["x"] for node in content_nodes)
    min_y = min(node["y"] for node in content_nodes)
    max_x = max(node["x"] + node["width"] for node in content_nodes)
    max_y = max(node["y"] + node["height"] for node in content_nodes)
    width = max_x - min_x
    height = max_y - min_y
    aspect = width / height
    occupied_area = sum(node["width"] * node["height"] for node in content_nodes)
    density = occupied_area / (width * height)
    if width > max_width or height > max_height or not min_aspect <= aspect <= max_aspect:
        raise ValueError(
            f"{name} must keep a compact landscape layout; "
            f"found {width}x{height} with aspect {aspect:.2f}"
        )
    if density < min_density:
        raise ValueError(f"{name} leaves too much empty space; content density is {density:.2f}")

    text_size = sum(len(str(node["text"])) for node in content_nodes if node["type"] == "text")
    if text_size > max_text:
        raise ValueError(f"{name} exceeds its concise text budget: {text_size}/{max_text}")
    if name == "career-guide.canvas":
        task_cards = [
            str(node["text"])
            for node in content_nodes
            if node["type"] == "text"
            and all(field in str(node["text"]) for field in _TASK_CARD_FIELDS)
        ]
        if any(len(card) > 700 for card in task_cards):
            raise ValueError("career-guide.canvas task cards must stay within 700 characters")

    for edge in canvas["edges"]:
        if edge.get("fromSide") is None or edge.get("toSide") is None:
            raise ValueError(f"{name} edge {edge['id']} must pin both sides for stable routing")

    for index, left in enumerate(content_nodes):
        for right in content_nodes[index + 1 :]:
            if _canvas_nodes_overlap(left, right):
                raise ValueError(f"{name} content nodes {left['id']} and {right['id']} overlap")


def _canvas_nodes_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_x = int(left["x"])
    left_y = int(left["y"])
    left_width = int(left["width"])
    left_height = int(left["height"])
    right_x = int(right["x"])
    right_y = int(right["y"])
    right_width = int(right["width"])
    right_height = int(right["height"])
    return (
        left_x < right_x + right_width
        and right_x < left_x + left_width
        and left_y < right_y + right_height
        and right_y < left_y + left_height
    )
