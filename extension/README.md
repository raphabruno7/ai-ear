# call-copilot Chrome extension (MV3)

Fills a scheduling form live from the copilot's extracted fields.

## Load it
1. `chrome://extensions` → enable Developer mode → **Load unpacked** → select this folder.
2. Click the extension icon → set **WebSocket URL** (`ws://localhost:8765`) and
   **Session ID** (the LiveKit room name) → **Connect**. Badge shows ● when live.
3. Open `http://localhost:3000/demo-scheduler` — inputs fill as fields arrive.

## Message contract (web → extension)
```json
{ "type": "fields", "session_id": "demo-1", "fields": { "owner_name": "Kathleen", "owner_email": "k@x.com" } }
```
The `/api/ws` endpoint (Fase 2, `web/`) broadcasts these; each field maps to a
`[data-copilot-field="<name>"]` element on the page.
