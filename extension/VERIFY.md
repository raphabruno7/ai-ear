# Extension — verification

## Verified 2026-09-02 (programmatic, no cloud)

The WS-fan-out → message-contract → React-form-fill path was exercised end-to-end
against the real `/demo-scheduler` page and the real `ws_push.py` server:

1. `listener/.venv/bin/python ws_push.py --session demo-1 --interval 2`
2. `cd web && npm run dev` → open `/demo-scheduler`
3. Replayed `background.js` (WS client, `subscribe` by `session_id`, relay) +
   `content.js` (`setValue` native-setter + bubbling `input`/`change`) in the
   page context.

**Result:** all 7 fields filled — `owner_name`, `owner_phone`, `owner_email`,
`pet_name`, `visit_type`, `preferred_time`, and the `clinical_notes` **textarea**
(the `HTMLTextAreaElement` branch of `setValue`). `copilot-filled` class applied
(green highlight). Values survived subsequent React re-renders → the `onChange`
fired and state took, not just the DOM. Screenshot: `../docs/extension-fill-verified.jpg`.

**Not covered by this run:** the MV3 shell itself — `manifest.json` permissions,
service-worker lifecycle, `chrome.storage.local`, `chrome.tabs.query` matching
`*/demo-scheduler*`. Lower risk (≈40 lines of standard MV3), but do the manual
pass below once before demoing.

## Manual pass (one-time)

1. `chrome://extensions` → Developer mode → **Load unpacked** → select `extension/`.
2. Extension icon → set WS URL `ws://localhost:8765`, Session ID `demo-1` → Connect.
   Badge shows ● when live.
3. Start `ws_push.py --session demo-1`, open `http://localhost:3000/demo-scheduler`.
4. Fields fill as messages arrive; badge stays ●.
