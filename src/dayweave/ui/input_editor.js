import { element, clock } from "./calendar.js";
import { inputField, action } from "./controls.js";

const $ = (id) => document.getElementById(id);

export function renderTasks(project, mutate) {
  $("tasks").replaceChildren();
  $("task-count").textContent = project.tasks.filter(
    (task) => !task.done,
  ).length;
  for (const task of project.tasks) {
    const card = element("div", "task-card" + (task.done ? " done" : ""));
    const head = element("div", "task-summary");
    const done = document.createElement("input");
    done.type = "checkbox";
    done.checked = !!task.done;
    done.setAttribute("aria-label", `标记“${task.title}”已完成`);
    done.addEventListener("change", () =>
      mutate(() => {
        task.done = done.checked;
      }),
    );
    const info = element("div", "task-info");
    info.append(element("div", "task-name", task.title));
    const sub = element("div", "task-sub");
    sub.append(
      element("span", "", task.duration ? `${task.duration} 分钟` : "时长待填"),
    );
    if (task.deadline)
      sub.append(
        element(
          "span",
          "",
          `${task.deadline.slice(5, 10)} ${clock(task.deadline)} 前`,
        ),
      );
    if (task.required === false)
      sub.append(element("span", "priority", "可推迟"));
    else if ((task.priority || 3) >= 4)
      sub.append(element("span", "priority", "优先"));
    info.append(sub);
    const buttons = element("div", "task-actions");
    buttons.append(
      action(task.open ? "收起" : "调整详情", () => {
        task.open = !task.open;
        renderTasks(project, mutate);
      }),
    );
    const pin = action(task.locked?.length ? "⌑ 已固定" : "固定安排", () =>
      mutate(() => {
        if (task.locked?.length) task.locked = [];
        else {
          task.locked = (project.previous || [])
            .filter((slot) => slot.task === task.id)
            .sort((a, b) => a.part - b.part)
            .map((slot) => slot.start);
          task.required = true;
        }
      }),
    );
    pin.disabled =
      !task.locked?.length &&
      !(project.previous || []).some((slot) => slot.task === task.id);
    buttons.append(
      pin,
      action(
        "删除",
        () =>
          mutate(() => {
            project.tasks = project.tasks.filter((item) => item.id !== task.id);
            project.tasks.forEach(
              (item) =>
                (item.after = (item.after || []).filter(
                  (key) => key !== task.id,
                )),
            );
          }),
        "quiet small delete",
      ),
    );
    info.append(buttons);
    head.append(done, info);
    card.append(head);
    if (task.open) {
      const detail = element("div", "task-detail");
      detail.append(
        inputField("事项名称", "text", task.title, (value) =>
          mutate(() => (task.title = value)),
        ),
      );
      const row = element("div", "form-row");
      const duration = inputField(
        "预计时长（分钟）",
        "number",
        task.duration,
        (value) =>
          mutate(() => {
            task.duration = Number(value);
            task.locked = [];
            if (task.chunk > task.duration) task.chunk = task.duration;
          }),
      );
      duration.querySelector("input").min = "1";
      duration.querySelector("input").max = "1440";
      const priorityLabel = element("label", "", "重要程度");
      const priority = document.createElement("select");
      for (let value = 1; value <= 5; value++) {
        const option = element(
          "option",
          "",
          ["", "低", "一般", "重要", "很重要", "最高"][value],
        );
        option.value = value;
        priority.append(option);
      }
      priority.value = task.priority || 3;
      priority.setAttribute("aria-label", "重要程度");
      priority.addEventListener("change", () =>
        mutate(() => (task.priority = Number(priority.value))),
      );
      priorityLabel.append(priority);
      row.append(duration, priorityLabel);
      detail.append(row);
      detail.append(
        inputField(
          "最早开始（可留空）",
          "datetime-local",
          task.release?.slice(0, 16),
          (value) => mutate(() => (task.release = value)),
        ),
        inputField(
          "完成期限（空白表示本周内）",
          "datetime-local",
          task.deadline?.slice(0, 16),
          (value) => mutate(() => (task.deadline = value)),
        ),
      );
      const parentLabel = element("label", "", "必须先完成");
      const parents = document.createElement("select");
      parents.setAttribute("aria-label", "必须先完成");
      parents.append(element("option", "", "无前置事项"));
      parents.firstChild.value = "";
      for (const other of project.tasks.filter(
        (item) => item.id !== task.id && !item.done,
      )) {
        const option = element("option", "", other.title);
        option.value = other.id;
        parents.append(option);
      }
      parents.value = task.after?.[0] || "";
      parents.addEventListener("change", () =>
        mutate(() => (task.after = parents.value ? [parents.value] : [])),
      );
      parentLabel.append(parents);
      detail.append(parentLabel);
      const required = element("label", "form-row");
      const requiredBox = document.createElement("input");
      requiredBox.type = "checkbox";
      requiredBox.checked = task.required !== false;
      requiredBox.addEventListener("change", () =>
        mutate(() => {
          task.required = requiredBox.checked;
          if (!task.required) task.locked = [];
        }),
      );
      required.append(requiredBox, element("span", "", "这件事必须安排进去"));
      detail.append(required);
      const split = element("label", "form-row");
      const splitBox = document.createElement("input");
      splitBox.type = "checkbox";
      splitBox.checked = !!task.chunk && task.chunk < task.duration;
      splitBox.addEventListener("change", () =>
        mutate(() => {
          task.chunk = splitBox.checked
            ? Math.min(60, task.duration)
            : task.duration;
          task.locked = [];
        }),
      );
      split.append(splitBox, element("span", "", "允许拆成较短的时段"));
      detail.append(split);
      if (splitBox.checked)
        detail.append(
          inputField("每段最长（分钟）", "number", task.chunk, (value) =>
            mutate(() => {
              task.chunk = Number(value);
              task.locked = [];
            }),
          ),
        );
      if (task.source)
        detail.append(element("p", "hint", `来自事项输入：${task.source}`));
      card.append(detail);
    }
    $("tasks").append(card);
  }
}

export function renderSettings(project, mutate) {
  $("week-start").value = project.start.slice(0, 10);
  $("timezone").value = project.timezone;
  $("available-list").replaceChildren();
  project.available.forEach((window, index) => {
    const row = element("div", "window-row");
    row.append(element("span", "", `空闲时段 ${index + 1}`));
    const fields = element("div", "form-row");
    fields.append(
      inputField(
        `空闲 ${index + 1} 开始`,
        "datetime-local",
        window.start.slice(0, 16),
        (value) => mutate(() => (window.start = value)),
      ),
      inputField(
        `空闲 ${index + 1} 结束`,
        "datetime-local",
        window.end.slice(0, 16),
        (value) => mutate(() => (window.end = value)),
      ),
      action(
        "×",
        () => mutate(() => project.available.splice(index, 1)),
        "delete",
      ),
    );
    row.append(fields);
    $("available-list").append(row);
  });
  $("appointment-count").textContent = `${project.appointments.length} 件`;
  $("appointments").replaceChildren();
  project.appointments.forEach((event, index) => {
    const row = element("div", "appointment-row");
    row.append(
      inputField(`已有安排 ${index + 1} 名称`, "text", event.title, (value) =>
        mutate(() => (event.title = value)),
      ),
    );
    const fields = element("div", "form-row");
    fields.append(
      inputField(
        `已有安排 ${index + 1} 开始`,
        "datetime-local",
        event.start.slice(0, 16),
        (value) => mutate(() => (event.start = value)),
      ),
      inputField(
        `已有安排 ${index + 1} 结束`,
        "datetime-local",
        event.end.slice(0, 16),
        (value) => mutate(() => (event.end = value)),
      ),
      action(
        "×",
        () => mutate(() => project.appointments.splice(index, 1)),
        "delete",
      ),
    );
    row.append(fields);
    $("appointments").append(row);
  });
}
