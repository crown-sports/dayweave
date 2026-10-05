export function element(tag, className, value) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (value !== undefined) node.textContent = value;
  return node;
}

export const localDate = (value) => value.slice(0, 10);
export const clock = (value) => value.slice(11, 16);
export function shiftDay(value, delta) {
  const parsed = new Date(value.slice(0, 10) + "T12:00:00Z");
  parsed.setUTCDate(parsed.getUTCDate() + delta);
  return parsed.toISOString().slice(0, 10);
}

function daySpan(item, day) {
  const minute = (value) =>
    Number(value.slice(11, 13)) * 60 + Number(value.slice(14, 16));
  if (localDate(item.start) > day || localDate(item.end) < day) return null;
  const start = localDate(item.start) < day ? 0 : minute(item.start);
  const end = localDate(item.end) > day ? 1440 : minute(item.end);
  return end > start ? [start, end] : null;
}

/** Render local wall-clock days, clipping every interval at midnight without hiding continuations. */
export function renderCalendar(container, input, result, onSlot) {
  container.replaceChildren();
  const view = result?.state === "conflict" ? result.alternative : result;
  const slots = view?.slots || [];
  const events = result?.appointments || input.appointments || [];
  const windows = result?.available || input.available;
  const days = Array.from({ length: 7 }, (_, i) => shiftDay(input.start, i));
  const timedEvents = events.filter(
    (e) => clock(e.start) !== "00:00" || clock(e.end) !== "00:00",
  );
  const hours = days.flatMap((day) =>
    [...slots, ...windows, ...timedEvents].flatMap((item) => {
      const span = daySpan(item, day);
      return span ? span.map((minute) => minute / 60) : [];
    }),
  );
  const firstHour = Math.max(
    0,
    Math.floor(Math.min(9, ...(hours.length ? hours : [9]))),
  );
  const lastHour = Math.min(
    24,
    Math.max(18, Math.ceil(Math.max(...(hours.length ? hours : [18])))),
  );
  const height = (lastHour - firstHour) * 48;
  container.append(element("div", "day-head time-head", "时间"));
  const weekdays = ["日", "一", "二", "三", "四", "五", "六"];
  days.forEach((day) => {
    const weekday = new Date(day + "T12:00:00Z").getUTCDay();
    const head = element(
      "div",
      "day-head" + ([0, 6].includes(weekday) ? " weekend" : ""),
    );
    head.append(
      element("span", "", `周${weekdays[weekday]}`),
      element("strong", "", day.slice(8)),
    );
    container.append(head);
  });
  const axis = element("div", "hour-axis");
  axis.style.height = `${height}px`;
  for (let hour = firstHour; hour < lastHour; hour++) {
    const label = element(
      "span",
      "hour-label",
      String(hour).padStart(2, "0") + ":00",
    );
    label.style.top = `${(hour - firstHour) * 48 + 2}px`;
    axis.append(label);
  }
  container.append(axis);
  const colors = new Map(
    input.tasks.map((task, index) => [task.id, index % 4]),
  );
  const changed = new Set(view?.movement?.changed_tasks || []);
  days.forEach((day) => {
    const column = element("div", "day-column");
    column.style.height = `${height}px`;
    let cursor = firstHour * 60;
    const available = windows
      .map((w) => daySpan(w, day))
      .filter(Boolean)
      .sort((a, b) => a[0] - b[0]);
    for (const [left, right] of available) {
      const start = Math.max(firstHour * 60, left);
      const end = Math.min(lastHour * 60, right);
      if (start > cursor)
        shade(column, cursor, Math.min(start, lastHour * 60), firstHour);
      cursor = Math.max(cursor, end);
    }
    if (cursor < lastHour * 60) shade(column, cursor, lastHour * 60, firstHour);
    for (const event of events) {
      if (localDate(event.start) <= day && localDate(event.end) >= day)
        addBlock(
          column,
          event,
          true,
          day,
          firstHour,
          lastHour,
          false,
          0,
          onSlot,
        );
    }
    for (const slot of slots.filter((s) => daySpan(s, day)))
      addBlock(
        column,
        slot,
        false,
        day,
        firstHour,
        lastHour,
        changed.has(slot.task),
        colors.get(slot.task) || 0,
        onSlot,
      );
    container.append(column);
  });
}

function shade(column, start, end, firstHour) {
  if (end <= start) return;
  const block = element("div", "available-shade");
  block.style.top = `${(start - firstHour * 60) * 0.8}px`;
  block.style.height = `${(end - start) * 0.8}px`;
  column.append(block);
}

function addBlock(
  column,
  item,
  event,
  day,
  firstHour,
  lastHour,
  moved,
  color,
  onSlot,
) {
  const minute = (value) =>
    Number(value.slice(11, 13)) * 60 + Number(value.slice(14, 16));
  let start = localDate(item.start) < day ? 0 : minute(item.start);
  let end = localDate(item.end) > day ? 1440 : minute(item.end);
  start = Math.max(start, firstHour * 60);
  end = Math.min(end, lastHour * 60);
  if (end <= start) return;
  const block = element(
    "button",
    "slot" +
      (event ? " event" : ` color-${color}`) +
      (moved ? " moved" : "") +
      (item.locked ? " locked" : ""),
  );
  block.style.top = `${(start - firstHour * 60) * 0.8 + 1}px`;
  block.style.height = `${Math.max(15, (end - start) * 0.8 - 2)}px`;
  block.setAttribute(
    "aria-label",
    `${item.title}，${clock(item.start)} 至 ${clock(item.end)}${moved ? "，本次调整" : ""}`,
  );
  if (end - start >= 30)
    block.append(
      element(
        "small",
        "",
        `${clock(item.start)}—${clock(item.end)}${moved ? " · 调整" : ""}`,
      ),
    );
  block.append(
    element("strong", "", item.title + (item.part > 0 ? " · 续" : "")),
  );
  block.addEventListener("click", () => onSlot(item, event));
  column.append(block);
}
