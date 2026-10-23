import { element, renderCalendar, shiftDay } from "./calendar.js";
import { action } from "./controls.js";
import {
  buildPlanInput,
  restoreProject,
  nowLocal,
  monday,
} from "./project_state.js";
import {
  renderTasks as renderTaskEditor,
  renderSettings as renderTimeEditor,
} from "./input_editor.js";
import { renderCaptureSheet, readCaptureSheet } from "./capture_sheet.js";

const $ = (id) => document.getElementById(id);
const storageKey = "dayweave.project.v1";
let project;
let token;
let revision = 0;
let pending = false;
let history = [];
let drafts = [];

async function api(path, body) {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers:
      body === undefined
        ? {}
        : { "Content-Type": "application/json", "X-DayWeave-Token": token },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response
      .json()
      .catch(() => ({ error: "服务暂时不可用，请重试。" }));
    const translations = {
      "Unknown IANA timezone":
        "时区不正确，请填写 Asia/Shanghai 这样的时区名称。",
      "Task release and deadline times must lie inside the horizon":
        "事项的最早开始时间和期限必须在本次规划日期内，请调整日期或事项详情。",
      "Available windows must lie inside the planning horizon":
        "空闲时段必须在本次规划日期内，请检查开始日期和空闲时间。",
      "Task dependencies contain a cycle":
        "前置事项形成了循环，请在事项详情里调整先后关系。",
      "Reload this local page to establish a session":
        "服务已经重新启动，请刷新页面后重试。",
      "This local time is ambiguous; provide an explicit UTC offset":
        "这个时间位于夏令时重复时段，请在 JSON 输入中写明 UTC 偏移。",
    };
    throw new Error(
      translations[payload.error] || payload.error || "请求没有完成。",
    );
  }
  return response;
}

function notice(message, kind = "") {
  $("notice").className = "notice" + (kind ? " " + kind : "");
  $("notice").querySelector("p").textContent = message;
}

function remember() {
  localStorage.setItem(storageKey, JSON.stringify(project));
}

function snapshot() {
  history.push(JSON.stringify(project));
  if (history.length > 20) history.shift();
}

function changed(render = true) {
  revision++;
  project.dirty = true;
  remember();
  if (render) renderAll();
  else renderResult();
  notice("内容已修改。点击“重新安排”，日程会按新条件更新。", "warn");
}

function mutate(callback) {
  snapshot();
  callback();
  changed();
}

function planInput() {
  return buildPlanInput(project);
}
function renderTasks() {
  renderTaskEditor(project, mutate);
}
function renderSettings() {
  renderTimeEditor(project, mutate);
}
function renderDrafts(result) {
  drafts = renderCaptureSheet(result);
}

function renderResult() {
  const result = project.result;
  const view = result?.state === "conflict" ? result.alternative : result;
  const slots = view?.slots || [];
  $("week-label").textContent =
    `${project.start.slice(5, 10).replace("-", "月")}日 — ${shiftDay(project.start, 6).slice(5, 10).replace("-", "月")}日`;
  $("example-notice").textContent = project.example
    ? "示例体验：修改后仍按示例时间计算。安排自己的事情，请点击“新建自己的计划”。"
    : "时长是你的估计；安排后也可以继续调整。";
  $("solve").textContent = pending
    ? "正在寻找可执行安排…"
    : result
      ? "重新安排 ↗"
      : "安排这一周 ↗";
  $("solve").disabled = pending;
  $("undo").disabled = !history.length || pending;
  $("interrupt").disabled =
    pending || project.dirty || result?.state !== "scheduled" || !slots.length;
  $("export").disabled =
    pending ||
    project.dirty ||
    result?.state !== "scheduled" ||
    !result?.validated;
  const status = $("plan-status");
  status.className =
    "status " +
    (result?.state === "scheduled" && !project.dirty
      ? "ready"
      : result?.state === "conflict"
        ? "conflict"
        : "neutral");
  status.textContent = project.dirty
    ? "等待重新安排"
    : result?.state === "scheduled"
      ? "时间条件已检查"
      : result?.state === "conflict"
        ? "需要做个取舍"
        : result?.state === "unknown"
          ? "尚未找到安排"
          : "等待安排";
  const count = new Set(slots.map((slot) => slot.task)).size;
  $("metric-tasks").textContent = result
    ? `${count} / ${project.tasks.filter((task) => !task.done).length}`
    : "—";
  $("metric-tasks-note").textContent =
    result?.state === "conflict"
      ? "下方是建议草案，尚未采用"
      : "所有必做事项须满足期限";
  const minutes = slots.reduce((sum, slot) => sum + slot.duration, 0);
  $("metric-time").textContent = result
    ? `${Math.round((minutes / 60) * 10) / 10} 小时`
    : "—";
  $("metric-change").textContent = result
    ? `${view?.movement?.changed_count || 0} 件`
    : "—";
  $("metric-change-note").textContent = view?.movement?.changed_count
    ? `开始时间偏移合计 ${view.movement.displacement_minutes} 分钟`
    : "已有安排和固定任务优先保留";
  $("conflict").replaceChildren();
  $("conflict").hidden = result?.state !== "conflict";
  if (result?.state === "conflict") {
    const box = $("conflict");
    box.append(element("h3", "", "这一组事情，暂时放不进你的时间里。"));
    if (result.capacity) {
      const c = result.capacity;
      box.append(
        element(
          "p",
          "",
          `${c.start.slice(5, 16).replace("T", " ")} — ${c.end.slice(5, 16).replace("T", " ")}：需要 ${c.required_minutes} 分钟，只有 ${c.available_minutes} 分钟可用，少了 ${c.shortfall_minutes} 分钟。`,
        ),
      );
    } else
      box.append(
        element("p", "", "可能是连续时段、先后顺序或固定时间相互冲突。"),
      );
    const list = element("ul", "");
    for (const item of result.conflict.items)
      list.append(
        element(
          "li",
          "",
          item.title +
            (item.kind === "appointment"
              ? "（已约安排）"
              : item.kind === "locked_task"
                ? "（已固定）"
                : ""),
        ),
      );
    box.append(list);
    box.append(
      element(
        "p",
        "",
        result.conflict.subset_minimal
          ? "这一组合已确认冲突；放松其中任一条件，这个组合就可行。其他事项仍需整体重算。"
          : "这一组合已确认冲突；目前未完成逐项简化。",
      ),
    );
    const omitted = view?.postponed || [];
    if (view?.validated && omitted.length) {
      box.append(
        element(
          "p",
          "",
          `一个可执行的取舍：允许推迟 ${omitted.map((item) => item.title).join("、")}。也可以自行增加空闲时段、改期限或允许拆开做。`,
        ),
      );
      box.append(
        action(
          "允许这些事项推迟，再安排一次",
          async () => {
            mutate(() => {
              const ids = new Set(omitted.map((item) => item.id));
              project.tasks.forEach((task) => {
                if (ids.has(task.id)) task.required = false;
              });
            });
            await solve();
          },
          "primary",
        ),
      );
    } else
      box.append(
        element(
          "p",
          "",
          "固定条件仍有冲突，或搜索时间不足。请先调整标出的安排再试。",
        ),
      );
  }
  $("postponed").hidden = !view?.postponed?.length;
  $("postponed").textContent = view?.postponed?.length
    ? `未安排的事项：${view.postponed.map((item) => item.title).join("、")}。${result.state === "conflict" ? "这只是建议，需你确认取舍。" : "这些事项已被你设为可推迟，不代表已经完成。"}`
    : "";
  $("explanation-body").replaceChildren();
  if (view?.validated) {
    const explanation = element(
      "p",
      "",
      `按你填写的时长、空闲时段、期限、前置事项和固定时间检查安排。先保留重要事项，再尽量减少原计划改动，最后让事情尽早完成、减少拆分间隔。`,
    );
    $("explanation-body").append(explanation);
    $("explanation-body").append(
      element(
        "p",
        "",
        view.optimal
          ? "当前输入下，各项优化目标已证明最优。时长估计是否符合实际，仍取决于你。"
          : "这是一份已检查的可行方案；搜索时间内未证明所有优化目标最优。",
      ),
    );
    if (project.previous?.length && view.movement?.changed_tasks?.length) {
      const titles = view.movement.changed_tasks.map(
        (id) => project.tasks.find((task) => task.id === id)?.title || id,
      );
      $("explanation-body").append(
        element(
          "p",
          "",
          `本次调整：${titles.join("、")}。已完成事项由你勾选，程序不会自行标记完成。`,
        ),
      );
    }
  } else
    $("explanation-body").append(
      element("p", "", "安排之后，这里会说明被满足的条件和本次调整。"),
    );
  const display = {
    ...project,
    tasks: project.tasks.filter((task) => !task.done),
  };
  renderCalendar($("calendar"), display, result, showSlot);
}

function renderAll() {
  renderTasks();
  renderSettings();
  renderResult();
}

async function solve() {
  if (pending) return;
  try {
    const input = planInput();
    const version = revision;
    pending = true;
    renderResult();
    notice("正在把事情放进真实空闲时段，并检查期限与先后顺序。");
    const response = await api("/api/solve", input);
    const result = await response.json();
    if (version !== revision) {
      notice("求解过程中内容已改变，请按最新条件重新安排。", "warn");
      return;
    }
    project.result = result;
    project.lastInput = structuredClone(input);
    project.dirty = false;
    if (result.state === "scheduled")
      project.previous = result.slots.map(
        ({ task, part, start, duration }) => ({ task, part, start, duration }),
      );
    remember();
    renderAll();
    if (result.state === "scheduled")
      notice(
        result.postponed.length
          ? "必做事项都已安排。你允许推迟的事项已单独列出。"
          : "每个必做事项都已放进空闲时段，期限、依赖和固定时间均已检查。",
      );
    else if (result.state === "conflict")
      notice(
        "当前所有承诺不能同时满足。请查看具体冲突和可选择的取舍。",
        "warn",
      );
    else
      notice(
        "搜索时间内没有找到安排，也没有证明排不下。可以减少事项或调整条件后重试。",
        "warn",
      );
  } catch (error) {
    notice(error.message, "error");
  } finally {
    pending = false;
    renderResult();
  }
}

function showSlot(item, isEvent) {
  $("slot-title").textContent = item.title;
  $("slot-content").replaceChildren();
  const rows = [
    [
      "时间",
      `${item.start.slice(5, 16).replace("T", " ")} — ${item.end.slice(5, 16).replace("T", " ")}`,
    ],
    ["类型", isEvent ? "已约好的安排" : "待办事项"],
  ];
  if (!isEvent) {
    const task = project.tasks.find((task) => task.id === item.task);
    rows.push(
      ["这段投入", `${item.duration} 分钟`],
      ["完成期限", task?.deadline?.slice(5, 16).replace("T", " ") || "本周内"],
      [
        "前置事项",
        (task?.after || [])
          .map((id) => project.tasks.find((t) => t.id === id)?.title || id)
          .join("、") || "无",
      ],
    );
    if (task?.source) rows.push(["来自输入", task.source]);
    rows.push([
      "时间能否改动",
      item.locked ? "你已固定这个安排" : "临时插入事情时可重新安排",
    ]);
  }
  for (const [label, value] of rows) {
    const row = element("div", "slot-info-row");
    row.append(element("span", "", label), element("span", "", value));
    $("slot-content").append(row);
  }
  $("slot-dialog").showModal();
}

function offerDownload(response, name) {
  const path = response.headers.get("X-DayWeave-Download");
  if (!path || !/^\/download\/[A-Za-z0-9_-]+$/.test(path))
    throw new Error("文件生成后没有获得下载地址，请重试。");
  const link = element("a", "", `保存 ${name}`);
  link.href = path;
  link.download = name;
  $("notice").querySelector("p").append(" ", link);
  link.click();
}

async function loadExample() {
  if (project) snapshot();
  const day = $("week-start").value || monday();
  const timezone = $("timezone").value || "Asia/Shanghai";
  project = await (
    await api(
      `/api/example/${$("example").value}?day=${encodeURIComponent(day)}&timezone=${encodeURIComponent(timezone)}`,
    )
  ).json();
  project.dirty = false;
  revision++;
  remember();
  renderAll();
  notice(
    "这是可编辑的示例。点击“安排这一周”即可实际计算，之后可插入新安排再试。",
  );
}

/** Start a personal plan with editable daytime windows and the actual current-time boundary. */
async function newProject() {
  let empty = await (
    await api(`/api/example/balanced?day=${monday()}&timezone=Asia%2FShanghai`)
  ).json();
  const now = nowLocal(empty.timezone);
  const nextWeek = empty.available.every((window) => window.end.slice(0, 16) <= now);
  if (nextWeek) {
    const day = shiftDay(empty.start, 7);
    empty = await (
      await api(`/api/example/balanced?day=${day}&timezone=Asia%2FShanghai`)
    ).json();
  }
  if (project) snapshot();
  project = {
    ...empty,
    tasks: [],
    appointments: [],
    previous: [],
    example: false,
  };
  changed();
  notice(nextWeek
    ? "本周的默认空闲时段已经结束，已创建下周计划。填写事项后可调整日期和空闲时间。"
    : "新计划已建立。先填写你的事项，再按实际情况调整可以安排的时间。");
}

$("solve").addEventListener("click", solve);
$("load-example").addEventListener("click", () =>
  loadExample().catch((error) => notice(error.message, "error")),
);
$("new-project").addEventListener("click", () =>
  newProject().catch((error) => notice(error.message, "error")),
);
$("add-task").addEventListener("click", () =>
  mutate(() =>
    project.tasks.push({
      id: "t_" + crypto.randomUUID().replaceAll("-", ""),
      title: "新的事项",
      duration: null,
      priority: 3,
      required: true,
      after: [],
      open: true,
    }),
  ),
);
$("add-window").addEventListener("click", () =>
  mutate(() =>
    project.available.push({
      start: project.start.slice(0, 10) + "T19:00",
      end: project.start.slice(0, 10) + "T21:00",
    }),
  ),
);
$("add-event").addEventListener("click", () =>
  mutate(() =>
    project.appointments.push({
      id: "e_" + crypto.randomUUID().replaceAll("-", ""),
      title: "新的安排",
      start: project.start.slice(0, 10) + "T15:00",
      end: project.start.slice(0, 10) + "T16:00",
    }),
  ),
);
$("week-start").addEventListener("change", () =>
  mutate(() => {
    const next = $("week-start").value;
    if (!next) return;
    const delta = Math.round(
      (Date.parse(next + "T12:00Z") -
        Date.parse(project.start.slice(0, 10) + "T12:00Z")) /
        86400000,
    );
    const shifted = (value) =>
      value ? shiftDay(value, delta) + value.slice(10) : value;
    project.available.forEach((w) => {
      w.start = shifted(w.start);
      w.end = shifted(w.end);
    });
    if (project.example) {
      project.tasks.forEach((task) => {
        task.release = shifted(task.release);
        task.deadline = shifted(task.deadline);
        task.locked = [];
      });
      project.appointments.forEach((e) => {
        e.start = shifted(e.start);
        e.end = shifted(e.end);
      });
      project.previous = [];
      project.result = null;
    }
    project.start = next + "T00:00";
    project.end = shiftDay(project.start, 7) + "T00:00";
    project.not_before = project.start;
  }),
);
$("timezone").addEventListener("change", () =>
  mutate(() => (project.timezone = $("timezone").value)),
);
$("undo").addEventListener("click", () => {
  if (history.length) {
    project = JSON.parse(history.pop());
    revision++;
    remember();
    renderAll();
    notice("已撤销最近一次内容改动。");
  }
});
$("interrupt").addEventListener("click", async () => {
  const slots = project.result?.slots || [];
  const slot = slots.find((s) => !s.locked && s.duration >= 30);
  if (!slot) {
    notice("没有可用来模拟插入的任务时段，请手动添加已有安排。", "warn");
    return;
  }
  mutate(() =>
    project.appointments.push({
      id: "new_" + crypto.randomUUID().replaceAll("-", ""),
      title: "临时插入的预约",
      start: slot.start,
      end: slot.end,
    }),
  );
  await solve();
});
$("export").addEventListener("click", async () => {
  try {
    const response = await api("/api/export", {
      plan: project.lastInput,
      slots: project.result.slots,
    });
    notice(
      "日历文件已生成，浏览器会保存文件。你可以自行导入常用日历；原有安排不会重复导出。",
    );
    offerDownload(response, "dayweave.ics");
  } catch (error) {
    notice(error.message, "error");
  }
});
$("backup").addEventListener("click", async () => {
  try {
    const response = await api("/api/backup", { project });
    notice(
      "项目备份已生成，包含事项、时间条件和原安排。下载链接五分钟内有效。",
    );
    offerDownload(response, "dayweave-project.json");
  } catch (error) {
    notice(error.message, "error");
  }
});
$("restore").addEventListener("click", () => $("project-file").click());
$("project-file").addEventListener("change", async (event) => {
  try {
    const file = event.target.files[0];
    if (!file) return;
    if (file.size > 2097152) throw new Error("项目文件不能超过 2 MiB。");
    const restored = restoreProject(JSON.parse(await file.text()));
    snapshot();
    project = restored;
    changed();
    notice("项目已打开。请检查内容并重新安排。");
  } catch (error) {
    notice(error.message, "error");
  } finally {
    event.target.value = "";
  }
});
$("import-calendar").addEventListener("click", () =>
  $("calendar-file").click(),
);
$("calendar-file").addEventListener("change", async (event) => {
  try {
    const file = event.target.files[0];
    if (!file) return;
    if (file.size > 1048576) throw new Error("日历文件不能超过 1 MiB。");
    const response = await api("/api/calendar", {
      plan: {
        timezone: project.timezone,
        start: project.start,
        end: project.end,
        tasks: [],
      },
      text: await file.text(),
    });
    const imported = await response.json();
    mutate(() => {
      const ids = new Set(project.appointments.map((item) => item.id));
      project.appointments.push(
        ...imported.appointments.filter((item) => !ids.has(item.id)),
      );
    });
    notice(
      `已导入 ${imported.appointments.length} 个本周安排。${imported.warnings.join(" ")} 请重新安排事项。`,
    );
  } catch (error) {
    notice(error.message, "error");
  } finally {
    event.target.value = "";
  }
});
$("paste").addEventListener("click", () => {
  $("drafts").replaceChildren();
  $("accept-drafts").hidden = true;
  $("capture-dialog").showModal();
});
$("close-capture").addEventListener("click", () => $("capture-dialog").close());
$("close-slot").addEventListener("click", () => $("slot-dialog").close());
$("capture-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("capture-submit").disabled = true;
  try {
    const response = await api("/api/capture", {
      text: $("note").value,
      anchor: nowLocal(project.timezone),
      timezone: project.timezone,
    });
    renderDrafts(await response.json());
  } catch (error) {
    $("capture-provider").textContent = error.message;
  } finally {
    $("capture-submit").disabled = false;
  }
});
$("accept-drafts").addEventListener("click", () => {
  readCaptureSheet(drafts);
  for (const input of $("drafts").querySelectorAll("input[type=number]"))
    if (!input.reportValidity()) return;
  const selected = drafts.filter((draft) => draft.selected);
  if (!selected.length) {
    $("capture-provider").textContent = "请至少选择一件要加入的事情。";
    return;
  }
  const unresolved = selected.find(
    (draft) => !draft.deadline && !draft.weekEnd,
  );
  if (unresolved) {
    $("capture-provider").textContent =
      `请给“${unresolved.title}”填写期限，或确认以本周结束为目标。`;
    return;
  }
  mutate(() =>
    selected.forEach((draft) =>
      project.tasks.push({
        id: "t_" + crypto.randomUUID().replaceAll("-", ""),
        title: draft.title,
        duration: draft.duration,
        deadline: draft.deadline || project.end,
        required: true,
        priority: 3,
        after: [],
        source: draft.quotes.title_quote,
      }),
    ),
  );
  $("capture-dialog").close();
});

try {
  const session = await (await api("/api/session")).json();
  token = session.token;
  if (session.model_enabled)
    $("capture-provider").textContent =
      "已配置本地模型辅助整理。时间信息仍需你核对。";
  const saved = localStorage.getItem(storageKey);
  if (saved) {
    project = restoreProject(JSON.parse(saved));
    renderAll();
    notice(
      "已恢复保存的事项和原安排。点击“安排这一周”，会按当前时间重新检查。",
      "warn",
    );
  } else await loadExample();
} catch (error) {
  notice(`无法打开本地规划器：${error.message}`, "error");
}
