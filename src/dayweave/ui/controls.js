import { element } from "./calendar.js";

let labelCounter = 0;

export function inputField(label, type, value, onChange) {
  const wrapper = element("label", "", label);
  const input = document.createElement("input");
  input.id = `field-${++labelCounter}`;
  input.type = type;
  input.value = value ?? "";
  input.setAttribute("aria-label", label);
  input.addEventListener("change", () => onChange(input.value, input));
  wrapper.append(input);
  return wrapper;
}

export function action(label, callback, className = "quiet small") {
  const button = element("button", className, label);
  button.type = "button";
  button.addEventListener("click", callback);
  return button;
}
