import { element } from "./calendar.js";
import { inputField } from "./controls.js";

const $ = (id) => document.getElementById(id);

/** Read the review form at confirmation so the last focused field cannot lose an edit. */
export function readCaptureSheet(drafts) {
  [...$("drafts").children].forEach((card, index) => {
    const draft = drafts[index];
    draft.title = card.querySelector("input[type=text]").value;
    const duration = card.querySelector("input[type=number]").value;
    draft.duration = duration === "" ? null : Number(duration);
    draft.deadline =
      card.querySelector("input[type=datetime-local]").value || null;
    draft.selected = card.querySelector("input[type=checkbox]").checked;
    const weekEnd = card.querySelectorAll("input[type=checkbox]")[1];
    draft.weekEnd = !!weekEnd?.checked;
  });
}

export function renderCaptureSheet(result) {
  const drafts = result.items;
  $("drafts").replaceChildren();
  $("accept-drafts").hidden = !drafts.length;
  drafts.forEach((draft, index) => {
    const card = element("div", "draft-card");
    draft.selected = true;
    const selection = element("label", "form-row");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = true;
    checkbox.setAttribute("aria-label", `加入待确认事项 ${index + 1}`);
    checkbox.addEventListener("change", () => {
      draft.selected = checkbox.checked;
      card
        .querySelectorAll("input:not([type=checkbox])")
        .forEach((input) => (input.disabled = !draft.selected));
    });
    selection.append(checkbox, element("span", "", "加入这件事"));
    card.append(selection);
    card.append(
      inputField(
        `待确认事项 ${index + 1} 名称`,
        "text",
        draft.title,
        (value) => (draft.title = value),
      ),
    );
    const row = element("div", "form-row");
    const duration = inputField(
      `待确认事项 ${index + 1} 时长`,
      "number",
      draft.duration,
      (value) => (draft.duration = Number(value)),
    );
    duration.querySelector("input").min = "1";
    duration.querySelector("input").max = "1440";
    duration.querySelector("input").required = true;
    row.append(
      duration,
      inputField(
        `待确认事项 ${index + 1} 期限`,
        "datetime-local",
        draft.deadline?.slice(0, 16),
        (value) => (draft.deadline = value),
      ),
    );
    card.append(row);
    if (!draft.deadline) {
      const label = element("label", "form-row");
      const check = document.createElement("input");
      check.type = "checkbox";
      check.setAttribute("aria-label", `确认“${draft.title}”以本周结束为目标`);
      check.addEventListener("change", () => (draft.weekEnd = check.checked));
      label.append(
        check,
        element("span", "", "未写完整期限：我确认以本周结束为目标"),
      );
      card.append(label);
    }
    if (!draft.duration)
      card.append(element("p", "hint", "原文没有明确时长，请填写你的估计。"));
    const source = element("details", "");
    source.append(element("summary", "", "查看原文依据"));
    for (const [key, quote] of Object.entries(draft.quotes))
      if (quote)
        source.append(
          element(
            "p",
            "",
            `${key === "title_quote" ? "事项" : key === "duration_quote" ? "时长" : "期限"}：${quote}`,
          ),
        );
    card.append(source);
    $("drafts").append(card);
  });
  $("capture-provider").textContent = result.rejection
    ? `模型输入整理未通过校验，已改用离线逐行识别。${result.rejection}`
    : result.provider === "local_model"
      ? "已使用你配置的本地模型选择原文。请核对事项和对应时间。"
      : "已逐行识别。所有未写完整的时间都需要你确认。";
  return drafts;
}
