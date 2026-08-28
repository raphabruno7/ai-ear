const $ = (id) => document.getElementById(id);

async function load() {
  const s = await chrome.storage.local.get(["wsUrl", "sessionId", "lastFields"]);
  $("wsUrl").value = s.wsUrl || "ws://localhost:8765";
  $("sessionId").value = s.sessionId || "";
  renderFields(s.lastFields || {});
}

function renderFields(fields) {
  $("fields").innerHTML = Object.entries(fields)
    .map(([k, v]) => `<div><span>${k}</span><span>${v ?? ""}</span></div>`)
    .join("");
}

$("save").addEventListener("click", async () => {
  await chrome.storage.local.set({
    wsUrl: $("wsUrl").value.trim(),
    sessionId: $("sessionId").value.trim(),
  });
  const res = await chrome.runtime.sendMessage({ type: "reconnect" });
  $("status").textContent = res?.ok ? "connecting…" : "error";
});

chrome.storage.onChanged.addListener((c) => {
  if (c.lastFields) renderFields(c.lastFields.newValue || {});
});

load();
