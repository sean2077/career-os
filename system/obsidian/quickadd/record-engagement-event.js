const EVENT_OPTIONS = [
  ["recruiter-contacted", "联系人 / 招聘方已联系"],
  ["referral-created", "内推关系已建立"],
  ["application-submitted", "已提交申请"],
  ["application-withdrawn", "已撤回申请"],
  ["application-rejected", "申请被拒"],
  ["interview-scheduled", "已安排面试"],
  ["interview-completed", "已完成面试"],
  ["offer-received", "已收到 Offer"],
  ["offer-accepted", "已接受 Offer"],
  ["offer-declined", "已拒绝 Offer"],
  ["process-closed", "流程已关闭"],
].map(([eventType, label]) => ({ eventType, label }));

const STAGES = [
  "identified",
  "contacted",
  "scoped",
  "applied",
  "interviewing",
  "offer",
  "employed",
  "closed",
];
const APPLICATION_STATES = [
  "not-applied",
  "unknown",
  "applied",
  "withdrawn",
  "rejected",
  "offer",
  "accepted",
  "declined",
];
const STATUSES = ["active", "paused", "closed"];

function localTimestamp(now = new Date()) {
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
  return `${date}T${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(
    now.getSeconds(),
  )}${offset}`;
}

function uuid() {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (value) => {
    const random = Math.floor(Math.random() * 16);
    return (value === "x" ? random : (random & 0x3) | 0x8).toString(16);
  });
}

function clone(value) {
  if (value === undefined) {
    return undefined;
  }
  return JSON.parse(JSON.stringify(value));
}

function rankAtLeast(current, proposed) {
  return STAGES[Math.max(STAGES.indexOf(current), STAGES.indexOf(proposed))];
}

function proposedProjection(frontmatter, eventType) {
  const proposed = {
    stage: frontmatter.stage,
    application_state: frontmatter.application_state,
    status: frontmatter.status,
  };
  const stage = {
    "recruiter-contacted": "contacted",
    "application-submitted": "applied",
    "interview-scheduled": "interviewing",
    "interview-completed": "interviewing",
    "offer-received": "offer",
    "offer-accepted": "offer",
  }[eventType];
  if (stage) {
    proposed.stage = rankAtLeast(frontmatter.stage, stage);
  }
  const applicationState = {
    "application-submitted": "applied",
    "application-withdrawn": "withdrawn",
    "application-rejected": "rejected",
    "offer-received": "offer",
    "offer-accepted": "accepted",
    "offer-declined": "declined",
  }[eventType];
  if (applicationState) {
    proposed.application_state = applicationState;
  }
  if (
    [
      "application-withdrawn",
      "application-rejected",
      "offer-declined",
      "process-closed",
    ].includes(eventType)
  ) {
    proposed.stage = "closed";
    proposed.status = "closed";
  }
  return proposed;
}

function eventTypes(frontmatter) {
  return new Set((frontmatter.events ?? []).map((event) => event.event_type));
}

function validateEventPrerequisite(frontmatter, eventType) {
  const prerequisite = {
    "application-withdrawn": "application-submitted",
    "application-rejected": "application-submitted",
    "interview-completed": "interview-scheduled",
    "offer-accepted": "offer-received",
    "offer-declined": "offer-received",
  }[eventType];
  if (prerequisite && !eventTypes(frontmatter).has(prerequisite)) {
    throw new Error(`${eventType} 需要更早的 ${prerequisite} 事件`);
  }
}

function validateEngagement(frontmatter) {
  if (
    frontmatter.kind !== "opportunity.engagement" ||
    frontmatter.schema_version !== 3
  ) {
    throw new Error("当前文件不是 schema 3 opportunity.engagement");
  }
  if (!STATUSES.includes(frontmatter.status)) {
    throw new Error(`无效 status：${frontmatter.status ?? "空"}`);
  }
  if (!STAGES.includes(frontmatter.stage)) {
    throw new Error(`无效 stage：${frontmatter.stage ?? "空"}`);
  }
  if (!APPLICATION_STATES.includes(frontmatter.application_state)) {
    throw new Error(
      `无效 application_state：${frontmatter.application_state ?? "空"}`,
    );
  }
  if (!Array.isArray(frontmatter.events)) {
    throw new Error("events 必须是列表");
  }

  const ids = new Set();
  let previousTimestamp = Number.NEGATIVE_INFINITY;
  for (const event of frontmatter.events) {
    const eventId = String(event?.id ?? "");
    if (!eventId || ids.has(eventId)) {
      throw new Error("事件 ID 缺失或重复");
    }
    ids.add(eventId);
    const timestamp = Date.parse(String(event.occurred_at ?? ""));
    if (!Number.isFinite(timestamp)) {
      throw new Error("事件时间无效");
    }
    if (timestamp < previousTimestamp) {
      throw new Error("事件必须按时间顺序排列");
    }
    previousTimestamp = timestamp;
  }

  const types = eventTypes(frontmatter);
  const requiredApplicationEvent = {
    applied: "application-submitted",
    withdrawn: "application-withdrawn",
    rejected: "application-rejected",
    offer: "offer-received",
    accepted: "offer-accepted",
    declined: "offer-declined",
  }[frontmatter.application_state];
  if (requiredApplicationEvent && !types.has(requiredApplicationEvent)) {
    throw new Error(
      `application_state ${frontmatter.application_state} 需要 ${requiredApplicationEvent}`,
    );
  }
  if (
    frontmatter.application_state === "not-applied" &&
    [
      "application-submitted",
      "application-withdrawn",
      "application-rejected",
      "offer-received",
      "offer-accepted",
      "offer-declined",
    ].some((type) => types.has(type))
  ) {
    throw new Error("not-applied 不能包含申请或 Offer 事件");
  }

  const requiredStageEvent = {
    contacted: "recruiter-contacted",
    applied: "application-submitted",
    interviewing: "interview-scheduled",
    offer: "offer-received",
    employed: "employment-started",
  }[frontmatter.stage];
  if (requiredStageEvent && !types.has(requiredStageEvent)) {
    throw new Error(`stage ${frontmatter.stage} 需要 ${requiredStageEvent}`);
  }

  const eventStage = {
    "recruiter-contacted": "contacted",
    "application-submitted": "applied",
    "interview-scheduled": "interviewing",
    "interview-completed": "interviewing",
    "offer-received": "offer",
    "offer-accepted": "offer",
    "offer-declined": "offer",
    "employment-started": "employed",
  };
  const furthest = Math.max(
    0,
    ...[...types]
      .filter((type) => eventStage[type])
      .map((type) => STAGES.indexOf(eventStage[type])),
  );
  if (STAGES.indexOf(frontmatter.stage) < furthest) {
    throw new Error("stage 不能落后于已记录事件");
  }
  if (
    ["withdrawn", "rejected", "declined"].includes(
      frontmatter.application_state,
    ) &&
    frontmatter.stage !== "closed"
  ) {
    throw new Error(
      `application_state ${frontmatter.application_state} 要求 closed stage`,
    );
  }

  for (const event of frontmatter.events) {
    validateEventPrerequisite(
      {
        events: frontmatter.events.slice(
          0,
          frontmatter.events.indexOf(event),
        ),
      },
      event.event_type,
    );
  }
}

function engagementRevision(frontmatter) {
  const revision = clone(frontmatter);
  delete revision.position;
  return JSON.stringify(revision);
}

function applyEngagementEvent(
  frontmatter,
  event,
  projection,
  reviewOn,
  nextAction,
  now = new Date(),
) {
  const planned = clone(frontmatter);
  planned.events = [...planned.events, clone(event)];
  planned.stage = projection.stage;
  planned.application_state = projection.application_state;
  planned.status = projection.status;
  planned.review_status = "pending";
  planned.updated_at = localTimestamp(now);
  if (reviewOn) {
    planned.review_on = reviewOn;
  } else {
    delete planned.review_on;
  }
  if (nextAction) {
    planned.next_action = nextAction;
  } else {
    delete planned.next_action;
  }
  validateEngagement(planned);
  return planned;
}

function changedFields(before, after) {
  const keys = [
    "events",
    "stage",
    "application_state",
    "status",
    "review_on",
    "next_action",
    "review_status",
    "reviewed_at",
    "updated_at",
  ];
  return keys
    .filter(
      (key) =>
        JSON.stringify(before[key]) !== JSON.stringify(after[key]),
    )
    .map((key) => {
      if (key === "events") {
        const event = after.events.at(-1);
        return `event: ${event.event_type} @ ${event.occurred_at}${
          event.note ? ` — ${event.note}` : ""
        }`;
      }
      return `${key}: ${JSON.stringify(before[key] ?? null)} → ${JSON.stringify(
        after[key] ?? null,
      )}`;
    });
}

function assignPlan(frontmatter, before, planned) {
  const keys = new Set([...Object.keys(before), ...Object.keys(planned)]);
  for (const key of keys) {
    if (JSON.stringify(before[key]) === JSON.stringify(planned[key])) {
      continue;
    }
    if (key in planned) {
      frontmatter[key] = clone(planned[key]);
    } else {
      delete frontmatter[key];
    }
  }
}

async function chooseValue(quickAddApi, label, options, proposed) {
  const ordered = [proposed, ...options.filter((value) => value !== proposed)];
  return quickAddApi.suggester(
    ordered.map((value) => `${value}${value === proposed ? "（建议）" : ""}`),
    ordered,
    `确认或修改 ${label}`,
  );
}

module.exports = async ({ app, quickAddApi, obsidian }) => {
  const notice = (message) => new obsidian.Notice(`Career OS：${message}`, 7000);
  const file = app.workspace.getActiveFile();
  if (
    !file ||
    file.extension !== "md" ||
    !/(^|\/)career\/40-opportunity-decision\/engagements\/[^/]+\.md$/.test(
      file.path,
    )
  ) {
    notice("请先打开规范目录中的 Engagement");
    return;
  }

  const cached = app.metadataCache.getFileCache(file)?.frontmatter;
  try {
    validateEngagement(cached);
  } catch (error) {
    notice(error.message);
    return;
  }

  const selected = await quickAddApi.suggester(
    EVENT_OPTIONS.map((option) => option.label),
    EVENT_OPTIONS,
    "记录已发生的招聘互动或面试事件",
  );
  if (!selected) {
    return;
  }
  try {
    validateEventPrerequisite(cached, selected.eventType);
  } catch (error) {
    notice(error.message);
    return;
  }

  const occurredAt = await quickAddApi.inputPrompt(
    "事件时间（RFC 3339，必须含时区）",
    "例如 2026-07-25T14:30:00+08:00",
    localTimestamp(),
  );
  if (occurredAt == null) {
    return;
  }
  if (
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})$/.test(
      occurredAt,
    ) ||
    Number.isNaN(Date.parse(occurredAt))
  ) {
    notice("事件时间必须是含时区的 RFC 3339 时间");
    return;
  }
  const lastEvent = cached.events.at(-1);
  if (
    lastEvent &&
    Date.parse(occurredAt) < Date.parse(String(lastEvent.occurred_at))
  ) {
    notice("事件时间早于现有最后一条事件；请先按时间顺序整理记录");
    return;
  }

  const noteInput = await quickAddApi.inputPrompt(
    "事件备注（可选）",
    "只记录用户报告或直接证据，不推断投递或结果",
    "",
  );
  if (noteInput == null) {
    return;
  }

  const proposal = proposedProjection(cached, selected.eventType);
  const stage = await chooseValue(quickAddApi, "stage", STAGES, proposal.stage);
  if (!stage) {
    return;
  }
  const applicationState = await chooseValue(
    quickAddApi,
    "application_state",
    APPLICATION_STATES,
    proposal.application_state,
  );
  if (!applicationState) {
    return;
  }
  const status = await chooseValue(
    quickAddApi,
    "status",
    STATUSES,
    proposal.status,
  );
  if (!status) {
    return;
  }

  const reviewOnInput = await quickAddApi.inputPrompt(
    "下次检查日期（YYYY-MM-DD，可留空清除）",
    "日期级检查点，不是预约时间",
    cached.review_on ?? "",
  );
  if (reviewOnInput == null) {
    return;
  }
  const reviewOn = reviewOnInput.trim();
  if (reviewOn && !/^\d{4}-\d{2}-\d{2}$/.test(reviewOn)) {
    notice("review_on 必须是 YYYY-MM-DD 或留空");
    return;
  }

  const nextActionInput = await quickAddApi.inputPrompt(
    "下一动作（可留空清除）",
    "例如：准备一面、确认面试时间、等待反馈",
    cached.next_action ?? "",
  );
  if (nextActionInput == null) {
    return;
  }
  const nextAction = nextActionInput.trim();
  const event = {
    id: uuid(),
    event_type: selected.eventType,
    occurred_at: occurredAt,
    occurred_at_precision: "instant",
    source: "user-report",
  };
  if (noteInput.trim()) {
    event.note = noteInput.trim();
  }

  const snapshot = engagementRevision(cached);
  let planned;
  try {
    planned = applyEngagementEvent(
      cached,
      event,
      { stage, application_state: applicationState, status },
      reviewOn,
      nextAction,
    );
  } catch (error) {
    notice(`事件与状态组合无效。${error.message}`);
    return;
  }

  const summary = [
    `记录 Engagement 事件：${file.basename}`,
    "",
    ...changedFields(cached, planned),
    "",
    "这只更新本地记录，不执行投递、消息、账号或 Offer 决策。",
  ].join("\n");
  if (!(await quickAddApi.yesNoPrompt("确认写入", summary))) {
    return;
  }

  try {
    await app.fileManager.processFrontMatter(file, (frontmatter) => {
      if (engagementRevision(frontmatter) !== snapshot) {
        throw new Error("Engagement 在确认后发生变化；请重新记录");
      }
      assignPlan(frontmatter, cached, planned);
    });
  } catch (error) {
    notice(`事件未写入。${error.message}`);
    return;
  }
  notice(`已记录 ${selected.eventType}，并重置人工复核状态。`);
};

module.exports.EVENT_OPTIONS = EVENT_OPTIONS;
module.exports.STAGES = STAGES;
module.exports.APPLICATION_STATES = APPLICATION_STATES;
module.exports.STATUSES = STATUSES;
module.exports.applyEngagementEvent = applyEngagementEvent;
module.exports.engagementRevision = engagementRevision;
module.exports.proposedProjection = proposedProjection;
module.exports.validateEngagement = validateEngagement;
module.exports.validateEventPrerequisite = validateEventPrerequisite;
