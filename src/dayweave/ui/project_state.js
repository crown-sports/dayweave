import { shiftDay } from "./calendar.js";

export function nowLocal(timezone, roundUp = false) {
  const date = new Date(Date.now() + (roundUp ? 60000 : 0));
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const get = (key) => parts.find((part) => part.type === key).value;
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}`;
}

export function monday() {
  const today = nowLocal("Asia/Shanghai").slice(0, 10);
  const weekday = new Date(today + "T12:00:00Z").getUTCDay();
  return shiftDay(today, -((weekday + 6) % 7));
}

export function buildPlanInput(project) {
  const done = new Set(
    project.tasks.filter((task) => task.done).map((task) => task.id),
  );
  const tasks = project.tasks
    .filter((task) => !task.done)
    .map((task) => {
      if (!Number.isInteger(task.duration) || task.duration < 1)
        throw new Error(`请先填写“${task.title}”的预计时长。`);
      const result = {
        id: task.id,
        title: task.title,
        duration: task.duration,
        completed_minutes: task.completed_minutes || 0,
        priority: task.priority || 3,
        required: task.required !== false,
        after: (task.after || []).filter((key) => !done.has(key)),
        locked: task.locked || [],
      };
      if (task.release) result.release = task.release;
      if (task.deadline) result.deadline = task.deadline;
      if (task.chunk) result.chunk = task.chunk;
      return result;
    });
  const result = {
    timezone: project.timezone,
    start: project.start,
    end: project.end,
    available: project.available,
    tasks,
    appointments: project.appointments,
    previous: project.previous || [],
    not_before: project.not_before || project.start,
  };
  if (!project.example) {
    const now = nowLocal(project.timezone, true);
    if (now > result.end.slice(0, 16))
      throw new Error(
        "这个规划时段已经结束，请在“可以安排的时间”里修改日期和空闲时段。",
      );
    if (now > result.start.slice(0, 16)) result.not_before = now;
  }
  return result;
}

/** Accept renderable project data; imported results must be recomputed before use or export. */
export function restoreProject(value) {
  const fail = () => {
    throw new Error(
      "项目内容不完整或格式不正确，请打开 DayWeave 保存的项目文件。",
    );
  };
  const date = (item) =>
    typeof item === "string" &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::00)?(?:Z|[+-]\d{2}:\d{2})?$/.test(
      item,
    ) &&
    Number.isFinite(Date.parse(item));
  const id = (item) =>
    typeof item === "string" && /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(item);
  const title = (item) =>
    typeof item === "string" && item.trim().length > 0 && item.length <= 200;
  if (
    !value ||
    !date(value.start) ||
    !date(value.end) ||
    typeof value.timezone !== "string"
  )
    fail();
  try {
    new Intl.DateTimeFormat("en-CA", { timeZone: value.timezone });
  } catch {
    fail();
  }
  for (const [key, limit] of [
    ["tasks", 60],
    ["available", 100],
    ["appointments", 200],
  ])
    if (!Array.isArray(value[key]) || value[key].length > limit) fail();
  if (value.available.some((w) => !w || !date(w.start) || !date(w.end))) fail();
  if (
    value.appointments.some(
      (e) =>
        !e || !id(e.id) || !title(e.title) || !date(e.start) || !date(e.end),
    )
  )
    fail();
  const tasks = value.tasks.map((task) => {
    if (
      !task ||
      !id(task.id) ||
      !title(task.title) ||
      (task.duration != null &&
        (!Number.isInteger(task.duration) ||
          task.duration < 1 ||
          task.duration > 1440))
    )
      fail();
    if (
      (task.deadline && !date(task.deadline)) ||
      (task.release && !date(task.release))
    )
      fail();
    if (
      task.completed_minutes != null &&
      (!Number.isInteger(task.completed_minutes) || task.completed_minutes < 0 ||
        (task.duration == null ? task.completed_minutes !== 0 : task.completed_minutes > task.duration))
    ) fail();
    if (task.after && (!Array.isArray(task.after) || !task.after.every(id)))
      fail();
    if (
      task.locked &&
      (!Array.isArray(task.locked) ||
        task.locked.length > 12 ||
        !task.locked.every(date))
    )
      fail();
    if (
      task.chunk != null &&
      (!Number.isInteger(task.chunk) || task.chunk < 1 || task.chunk > 1440)
    )
      fail();
    if (
      task.priority != null &&
      (!Number.isInteger(task.priority) ||
        task.priority < 1 ||
        task.priority > 5)
    )
      fail();
    return {
      id: task.id,
      title: task.title,
      duration: task.duration ?? null,
      completed_minutes: task.completed_minutes || 0,
      priority: task.priority || 3,
      required: task.required !== false,
      after: task.after || [],
      locked: task.locked || [],
      release: task.release || null,
      deadline: task.deadline || null,
      chunk: task.chunk || null,
      done: task.done === true || (task.duration != null && task.completed_minutes === task.duration),
      source:
        typeof task.source === "string" ? task.source.slice(0, 500) : null,
    };
  });
  if (new Set(tasks.map((task) => task.id)).size !== tasks.length) fail();
  const previous = value.previous || [];
  if (
    !Array.isArray(previous) ||
    previous.length > 300 ||
    previous.some(
      (slot) =>
        !slot ||
        !id(slot.task) ||
        !Number.isInteger(slot.part) ||
        slot.part < 0 ||
        slot.part > 11 ||
        !date(slot.start) ||
        !Number.isInteger(slot.duration) ||
        slot.duration < 1 ||
        slot.duration > 1440,
    )
  )
    fail();
  return {
    timezone: value.timezone,
    start: value.start,
    end: value.end,
    tasks,
    available: value.available.map(({ start, end }) => ({ start, end })),
    appointments: value.appointments.map(({ id, title, start, end }) => ({
      id,
      title,
      start,
      end,
    })),
    previous,
    example: !!value.example,
    dirty: true,
    result: null,
  };
}
