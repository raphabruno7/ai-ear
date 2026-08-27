// Fills form inputs tagged with data-copilot-field="<field_name>".
// A React-controlled input needs the native value setter + a bubbling 'input'
// event, otherwise React overwrites it on the next render.

function setValue(el, value) {
  const proto = el.tagName === "TEXTAREA"
    ? window.HTMLTextAreaElement.prototype
    : window.HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
  setter.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
  el.classList.add("copilot-filled");
}

function fill(fields) {
  for (const [name, value] of Object.entries(fields)) {
    if (value == null || value === "") continue;
    const el = document.querySelector(`[data-copilot-field="${CSS.escape(name)}"]`);
    if (el && el.value !== String(value)) setValue(el, String(value));
  }
}

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "fill") fill(msg.fields || {});
});

// pick up whatever was last received before this tab existed
chrome.storage.local.get("lastFields").then((s) => s.lastFields && fill(s.lastFields));
