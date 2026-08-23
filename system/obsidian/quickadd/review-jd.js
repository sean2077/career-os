const REVIEW_OPTIONS = [
  {
    key: "A",
    label: "A 主投正例",
    caseTarget: "positive",
    nextAction: "candidate",
    nextActionDetail: "进入候选；按同公司投递组合门槛决定是否准备投递",
  },
  {
    key: "B",
    label: "B 边界确认",
    caseTarget: "boundary",
    allowedNextActions: ["clarify", "observe"],
    defaultNextAction: "clarify",
    nextActionDetail: "确认职责边界",
  },
  {
    key: "C",
    label: "C 高价值挑战",
    caseTarget: "boundary",
    allowedNextActions: ["clarify", "observe"],
    defaultNextAction: "observe",
    nextActionDetail: "低成本观察；补足证据或偏好条件后复核",
  },
  {
    key: "D",
    label: "D 市场观察",
    caseTarget: "observe",
    nextAction: "observe",
    nextActionDetail: "市场观察",
  },
  {
    key: "E",
    label: "E 反例排除",
    caseTarget: "negative",
    nextAction: "reject",
    nextActionDetail: "排除",
  },
  {
    key: "F",
    label: "F 跳过 / 重复",
    skipped: true,
  },
];

const RECORD_TYPES = {
  "market.jd": {
    label: "JD",
    path:
      /(^|\/)career\/30-role-market\/jds\/(?:\d{4}-(?:0[1-9]|1[0-2])\/)?[^/]+\.md$/,
  },
  "opportunity.company": {
    label: "Company",
    path: /(^|\/)career\/40-opportunity-decision\/companies\/[^/]+\.md$/,
  },
  "opportunity.engagement": {
    label: "Engagement",
    path: /(^|\/)career\/40-opportunity-decision\/engagements\/[^/]+\.md$/,
  },
};

function localDateAndTimestamp(now = new Date()) {
  const pad = (value) => String(value).padStart(2, "0");
  const date = [
    now.getFullYear(),
    pad(now.getMonth() + 1),
    pad(now.getDate()),
  ].join("-");
  const offsetMinutes = -now.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absoluteOffset = Math.abs(offsetMinutes);
  const offset = `${sign}${pad(Math.floor(absoluteOffset / 60))}:${pad(
    absoluteOffset % 60,
  )}`;
  const time = [
    pad(now.getHours()),
    pad(now.getMinutes()),
    pad(now.getSeconds()),
  ].join(":");
  return { date, timestamp: `${date}T${time}${offset}` };
}

function reviewedNextAction(frontmatter, option) {
  if (option.nextAction) {
    return option.nextAction;
  }
  if (option.allowedNextActions.includes(frontmatter.next_action)) {
    return frontmatter.next_action;
  }
  return option.defaultNextAction;
}

function applyReview(frontmatter, option, now = new Date()) {
  const { date, timestamp } = localDateAndTimestamp(now);
  frontmatter.user_review_signal = option.label;
  frontmatter.updated_at = timestamp;

  if (option.skipped) {
    frontmatter.status = "skipped";
    delete frontmatter.reviewed_at;
    delete frontmatter.case_target;
    return;
  }

  const previousNextAction = frontmatter.next_action;
  const nextAction = reviewedNextAction(frontmatter, option);
  frontmatter.status = "reviewed";
  frontmatter.reviewed_at = date;
  frontmatter.case_target = option.caseTarget;
  frontmatter.next_action = nextAction;
  if (previousNextAction !== nextAction || !frontmatter.next_action_detail) {
    frontmatter.next_action_detail = option.nextActionDetail;
  }
}

function effectiveReviewState(frontmatter) {
  if (
    frontmatter.review_status !== "reviewed" ||
    !frontmatter.reviewed_at
  ) {
    return "pending";
  }
  const updatedDate = String(frontmatter.updated_at ?? "").slice(0, 10);
  return updatedDate > String(frontmatter.reviewed_at)
    ? "needs-review"
    : "reviewed";
}

function validateBaseRecord(file, frontmatter) {
  if (!file || file.extension !== "md") {
    throw new Error("请先打开一条待人工复核的 JD、Company 或 Engagement");
  }
  if (frontmatter?.schema_version !== 3 || !RECORD_TYPES[frontmatter?.kind]) {
    throw new Error("当前文件不是可复核的 schema 3 JD、Company 或 Engagement");
  }
  if (!RECORD_TYPES[frontmatter.kind].path.test(file.path)) {
    throw new Error(`当前 ${RECORD_TYPES[frontmatter.kind].label} 不在规范目录中`);
  }
  if (!frontmatter.updated_at) {
    throw new Error("记录缺少 updated_at");
  }
}

function validateJD(frontmatter) {
  if (frontmatter.status !== "screened") {
    throw new Error(
      `只能复核 screened JD；当前状态为 ${frontmatter.status ?? "空"}`,
    );
  }
  if (frontmatter.is_stale === true) {
    throw new Error("该 JD 已过期，请先刷新证据");
  }
}

function validateCompany(frontmatter, today) {
  if (!["pending-review", "reviewed"].includes(frontmatter.status)) {
    throw new Error(
      `Company 状态 ${frontmatter.status ?? "空"} 不支持人工复核`,
    );
  }
  if (frontmatter.assessment_status !== "current") {
    throw new Error(
      `Company assessment_status 必须为 current；当前为 ${
        frontmatter.assessment_status ?? "空"
      }`,
    );
  }
  if (!frontmatter.last_researched_at || !frontmatter.refresh_due) {
    throw new Error("Company 缺少 last_researched_at 或 refresh_due");
  }
  if (String(frontmatter.refresh_due) < today) {
    throw new Error("Company 研究已过期，请先刷新公司证据");
  }
  if (effectiveReviewState(frontmatter) === "reviewed") {
    throw new Error("Company 已是最新 reviewed 状态");
  }
}

function validateEngagementShape(frontmatter) {
  if (!["active", "paused", "closed"].includes(frontmatter.status)) {
    throw new Error(`Engagement status 无效：${frontmatter.status ?? "空"}`);
  }
  if (!Array.isArray(frontmatter.events)) {
    throw new Error("Engagement events 必须是列表");
  }
  const ids = new Set();
  let previous = "";
  for (const event of frontmatter.events) {
    if (!event?.id || ids.has(String(event.id))) {
      throw new Error("Engagement 事件 ID 缺失或重复");
    }
    ids.add(String(event.id));
    const occurredAt = String(event.occurred_at ?? "");
    if (!occurredAt || Number.isNaN(Date.parse(occurredAt))) {
      throw new Error("Engagement 事件时间无效");
    }
    if (previous && Date.parse(occurredAt) < Date.parse(previous)) {
      throw new Error("Engagement 事件未按时间顺序排列");
    }
    previous = occurredAt;
  }
}

function reviewRevision(frontmatter) {
  const revision = cloneFrontmatter(frontmatter);
  delete revision.position;
  return JSON.stringify(revision);
}

function cloneFrontmatter(frontmatter) {
  if (frontmatter === undefined) {
    return undefined;
  }
  return JSON.parse(JSON.stringify(frontmatter));
}

function buildReviewPlan(frontmatter, option, now = new Date()) {
  const planned = cloneFrontmatter(frontmatter);
  const { date, timestamp } = localDateAndTimestamp(now);
  if (frontmatter.kind === "market.jd") {
    applyReview(planned, option, now);
  } else if (frontmatter.kind === "opportunity.company") {
    planned.status = "reviewed";
    planned.review_status = "reviewed";
    planned.reviewed_at = date;
    planned.updated_at = timestamp;
  } else {
    planned.review_status = "reviewed";
    planned.reviewed_at = date;
    planned.updated_at = timestamp;
  }
  return planned;
}

function changedFields(before, after) {
  const keys = new Set([...Object.keys(before), ...Object.keys(after)]);
  return [...keys]
    .filter(
      (key) =>
        JSON.stringify(before[key]) !== JSON.stringify(after[key]),
    )
    .sort()
    .map(
      (key) =>
        `${key}: ${JSON.stringify(before[key] ?? null)} → ${JSON.stringify(
          after[key] ?? null,
        )}`,
    );
}

function wikilinkTarget(value) {
  const match = String(value ?? "").match(/^\[\[([^|\]#]+)(?:#[^|\]]+)?(?:\|[^\]]+)?\]\]$/);
  return match ? match[1] : null;
}

function resolveLinkedRecord(app, value, sourcePath) {
  const target = wikilinkTarget(value);
  return target
    ? app.metadataCache.getFirstLinkpathDest(target, sourcePath)
    : null;
}

async function validateEngagementRelationships(app, file, frontmatter, today) {
  validateEngagementShape(frontmatter);
  if (!frontmatter.company) {
    throw new Error("Engagement 缺少 Company 关系");
  }
  const companyFile = resolveLinkedRecord(
    app,
    frontmatter.company,
    file.path,
  );
  const company = companyFile
    ? app.metadataCache.getFileCache(companyFile)?.frontmatter
    : null;
  if (company?.kind !== "opportunity.company" || company?.schema_version !== 3) {
    throw new Error("Engagement 的 Company 关系损坏");
  }
  if (
    company.assessment_status !== "current" ||
    !company.refresh_due ||
    String(company.refresh_due) < today
  ) {
    throw new Error("Engagement 的 Company 评估受阻、过期或不完整");
  }
  if (frontmatter.target_jd) {
    const jdFile = resolveLinkedRecord(
      app,
      frontmatter.target_jd,
      file.path,
    );
    const jd = jdFile
      ? app.metadataCache.getFileCache(jdFile)?.frontmatter
      : null;
    if (jd?.kind !== "market.jd" || jd?.schema_version !== 3) {
      throw new Error("Engagement 的 target_jd 关系损坏");
    }
  }
  if (effectiveReviewState(frontmatter) === "reviewed") {
    throw new Error("Engagement 已是最新 reviewed 状态");
  }
}

async function validateReviewable(app, file, frontmatter, now = new Date()) {
  validateBaseRecord(file, frontmatter);
  const { date } = localDateAndTimestamp(now);
  if (frontmatter.kind === "market.jd") {
    validateJD(frontmatter);
  } else if (frontmatter.kind === "opportunity.company") {
    validateCompany(frontmatter, date);
  } else {
    await validateEngagementRelationships(app, file, frontmatter, date);
  }
}

function assignPlan(frontmatter, before, planned) {
  const keys = new Set([...Object.keys(before), ...Object.keys(planned)]);
  for (const key of keys) {
    if (JSON.stringify(before[key]) === JSON.stringify(planned[key])) {
      continue;
    }
    if (key in planned) {
      frontmatter[key] = cloneFrontmatter(planned[key]);
    } else {
      delete frontmatter[key];
    }
  }
}

function queueSort(kind, left, right) {
  const leftFrontmatter = left.frontmatter;
  const rightFrontmatter = right.frontmatter;
  if (kind === "opportunity.company") {
    return (
      String(leftFrontmatter.refresh_due).localeCompare(
        String(rightFrontmatter.refresh_due),
      ) || left.file.path.localeCompare(right.file.path)
    );
  }
  const updatedOrder = String(rightFrontmatter.updated_at).localeCompare(
    String(leftFrontmatter.updated_at),
  );
  return (
    updatedOrder ||
    right.file.stat.mtime - left.file.stat.mtime ||
    left.file.path.localeCompare(right.file.path)
  );
}

async function nextReviewable(app, currentFile, kind) {
  const candidates = [];
  for (const file of app.vault.getMarkdownFiles()) {
    if (file.path === currentFile.path) {
      continue;
    }
    const frontmatter = app.metadataCache.getFileCache(file)?.frontmatter;
    if (frontmatter?.kind !== kind || frontmatter?.schema_version !== 3) {
      continue;
    }
    try {
      await validateReviewable(app, file, frontmatter);
      candidates.push({ file, frontmatter });
    } catch {
      // Blocked or already-current records do not enter the transient queue.
    }
  }
  candidates.sort((left, right) => queueSort(kind, left, right));
  return candidates[0]?.file ?? null;
}

module.exports = async ({ app, quickAddApi, obsidian }) => {
  const notice = (message) => new obsidian.Notice(`Career OS：${message}`, 7000);
  let file = app.workspace.getActiveFile();

  while (file) {
    const cached = app.metadataCache.getFileCache(file)?.frontmatter;
    try {
      await validateReviewable(app, file, cached);
    } catch (error) {
      notice(error.message);
      return;
    }

    let selected = null;
    if (cached.kind === "market.jd") {
      selected = await quickAddApi.suggester(
        REVIEW_OPTIONS.map((option) => option.label),
        REVIEW_OPTIONS,
        "人工复核：A–E 转为 reviewed，F 转为 skipped",
      );
      if (!selected) {
        return;
      }
    }

    const snapshot = reviewRevision(cached);
    const planned = buildReviewPlan(cached, selected);
    const summary = [
      `复核 ${RECORD_TYPES[cached.kind].label}：${file.basename}`,
      "",
      ...changedFields(cached, planned),
      "",
      "确认后将一次写入；如记录已变化则拒绝写入。",
    ].join("\n");
    if (!(await quickAddApi.yesNoPrompt("确认复核", summary))) {
      return;
    }

    try {
      await app.fileManager.processFrontMatter(file, (frontmatter) => {
        if (reviewRevision(frontmatter) !== snapshot) {
          throw new Error("记录在确认后发生变化；请重新复核");
        }
        assignPlan(frontmatter, cached, planned);
      });
    } catch (error) {
      notice(`复核未写入。${error.message}`);
      return;
    }

    notice(
      selected?.skipped
        ? `已将 ${file.basename} 标记为 skipped。`
        : `已将 ${file.basename} 标记为 reviewed。`,
    );
    if (
      !(await quickAddApi.yesNoPrompt(
        "继续复核",
        `继续复核下一条 ${RECORD_TYPES[cached.kind].label}？`,
      ))
    ) {
      return;
    }
    const next = await nextReviewable(app, file, cached.kind);
    if (!next) {
      notice(`没有更多可复核的 ${RECORD_TYPES[cached.kind].label}。`);
      return;
    }
    await app.workspace.getLeaf(false).openFile(next);
    file = next;
  }
};

module.exports.REVIEW_OPTIONS = REVIEW_OPTIONS;
module.exports.applyReview = applyReview;
module.exports.buildReviewPlan = buildReviewPlan;
module.exports.effectiveReviewState = effectiveReviewState;
module.exports.reviewRevision = reviewRevision;
module.exports.validateBaseRecord = validateBaseRecord;
