// Connects to the web app's WebSocket, subscribes to one session, and relays
// every field update to the content script on the scheduler tab.
//
// Message contract (server -> extension):
//   { type: "fields", session_id, fields: { owner_name, owner_email, ... } }

let ws = null;
let cfg = { wsUrl: "ws://localhost:3000/api/ws", sessionId: "" };

async function loadCfg() {
  const s = await chrome.storage.local.get(["wsUrl", "sessionId"]);
  cfg = { ...cfg, ...s };
}

function connect() {
  if (!cfg.sessionId) return;
  if (ws && ws.readyState <= 1) ws.close();

  ws = new WebSocket(cfg.wsUrl);
  ws.onopen = () => {
    ws.send(JSON.stringify({ type: "subscribe", session_id: cfg.sessionId }));
    setBadge("on");
  };
  ws.onmessage = (ev) => {
    let msg;
    try { msg = JSON.parse(ev.data); } catch { return; }
    if (msg.type === "fields" && msg.session_id === cfg.sessionId) {
      broadcast(msg.fields || {});
      chrome.storage.local.set({ lastFields: msg.fields || {} });
    }
  };
  ws.onclose = () => { setBadge("off"); setTimeout(connect, 2000); };
  ws.onerror = () => ws.close();
}

async function broadcast(fields) {
  const tabs = await chrome.tabs.query({ url: ["*://*/demo-scheduler*"] });
  for (const t of tabs) {
    chrome.tabs.sendMessage(t.id, { type: "fill", fields }).catch(() => {});
  }
}

function setBadge(state) {
  chrome.action.setBadgeText({ text: state === "on" ? "●" : "" });
  chrome.action.setBadgeBackgroundColor({ color: "#16a34a" });
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "reconnect") {
    loadCfg().then(() => { connect(); sendResponse({ ok: true }); });
    return true;
  }
});

chrome.storage.onChanged.addListener((changes) => {
  if (changes.sessionId || changes.wsUrl) loadCfg().then(connect);
});

loadCfg().then(connect);
