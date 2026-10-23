/** Update editor nodes in place so a change event cannot discard the next click or Tab target. */
function key(node) {
  return node.nodeType === 1 ? node.getAttribute("data-editor-key") : null;
}

function compatible(current, next) {
  return current && current.nodeType === next.nodeType &&
    current.nodeName === next.nodeName && key(current) === key(next);
}

function update(current, next) {
  if (current.nodeType === 3) {
    if (current.data !== next.data) current.data = next.data;
    return;
  }
  for (const attribute of [...current.attributes]) {
    if (!next.hasAttribute(attribute.name)) current.removeAttribute(attribute.name);
  }
  for (const attribute of next.attributes) {
    if (current.getAttribute(attribute.name) !== attribute.value)
      current.setAttribute(attribute.name, attribute.value);
  }
  // Child options may be moved out of the draft tree during reconciliation.
  const value = next.value;
  // Fresh handlers point at the current project after undo, import or example replacement.
  current.onclick = next.onclick;
  current.onchange = next.onchange;
  updateEditor(current, next);
  if (current instanceof HTMLInputElement || current instanceof HTMLSelectElement) {
    if (current.value !== value) current.value = value;
    current.disabled = next.disabled;
    if (current instanceof HTMLInputElement) current.checked = next.checked;
  }
}

export function updateEditor(container, next) {
  const children = [...next.childNodes];
  children.forEach((child, index) => {
    let current = container.childNodes[index];
    const childKey = key(child);
    if (childKey && !compatible(current, child)) {
      const retained = [...container.childNodes].slice(index + 1)
        .find((node) => compatible(node, child));
      if (retained) {
        container.insertBefore(retained, current || null);
        current = retained;
      }
    }
    if (compatible(current, child)) update(current, child);
    else container.insertBefore(child, current || null);
  });
  while (container.childNodes.length > children.length) container.lastChild.remove();
}
